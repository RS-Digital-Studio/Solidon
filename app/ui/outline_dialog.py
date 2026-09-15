"""Konturen einer Zeichnung wählen und ihre echte Extrusion ansehen (§19.2).

Einlesen, Prüfung, Zeichenpfade und Projektion entstehen im Arbeiter. Im
Dokument stehen anschließend nur Konturkennungen, Höhe und Zielbreite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QByteArray, QPointF, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QMouseEvent, QPainter, QPainterPath, QPen, QResizeEvent
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import drawing
from app.core.errors import AppError, InternalError
from app.core.ingest import outline
from app.core.ingest.ops import LoadOutlineParams
from app.i18n import tr
from app.ui.dialogs import ErrorNotice
from app.ui.labels import LengthSpin, area, length
from app.ui.leash import DIALOG_WAIT_MS, WAIT_TIMEOUT_MS, Worker, WorkerLeash, weak_slot
from app.ui.style import ROOMY, make_primary, no_primary, set_level
from app.ui.theme import Theme, current_theme


@dataclass(frozen=True, slots=True)
class _ProfileDisplay:
    """Fertiger Zeichenpfad und Maße, damit Qt keine Konturgeometrie rechnet."""

    profile: outline.OutlineProfile
    reason: str
    path: QPainterPath
    label_at: QPointF
    width: float
    height: float
    area: float


class _ReadWorker(Worker):
    ready = Signal(object)
    failed = Signal(object)
    progress = Signal(int, int)

    def __init__(self, payload: bytes, suffix: str) -> None:
        super().__init__()
        self.payload, self.suffix = payload, suffix

    def work(self) -> None:
        try:
            profiles = outline.read_profiles(self.payload, self.suffix)
            result = []
            for number, entry in enumerate(profiles):
                if self.isInterruptionRequested():
                    return
                reason = outline.profile_reason(entry)
                path = QPainterPath()
                path.setFillRule(Qt.FillRule.OddEvenFill)
                for ring in (entry.polygon.exterior, *entry.polygon.interiors):
                    points = list(ring.coords)
                    path.moveTo(float(points[0][0]), -float(points[0][1]))
                    for x, y in points[1:]:
                        path.lineTo(float(x), -float(y))
                    path.closeSubpath()
                centre = entry.polygon.representative_point()
                x0, y0, x1, y1 = entry.polygon.bounds
                result.append(
                    _ProfileDisplay(
                        entry,
                        reason,
                        path,
                        QPointF(centre.x, -centre.y),
                        float(x1 - x0),
                        float(y1 - y0),
                        float(entry.polygon.area),
                    )
                )
                self.progress.emit(number + 1, len(profiles))
            if not self.isInterruptionRequested():
                self.ready.emit(tuple(result))
        except AppError as problem:
            self.failed.emit(problem.with_traceback(None))


class _PreviewWorker(Worker):
    ready = Signal(int, object, str)
    failed = Signal(int, object)

    def __init__(
        self,
        profiles: tuple[outline.OutlineProfile, ...],
        values: dict[str, Any],
        revision: int,
        theme: Theme,
    ) -> None:
        super().__init__()
        self.profiles, self.values, self.revision, self.theme = profiles, values, revision, theme

    def work(self) -> None:
        try:
            result = outline.extrude_profiles(
                self.profiles,
                self.values["height"],
                self.values["width"],
                contours=self.values["contours"],
            )
            if self.isInterruptionRequested():
                return
            svg = drawing.project(result.mesh.raw, size=512, theme=self.theme, edges=True)
            if not self.isInterruptionRequested():
                self.ready.emit(self.revision, result, svg)
        except AppError as problem:
            self.failed.emit(self.revision, problem.with_traceback(None))


class _ProfileView(QGraphicsView):
    """Bildklick und Liste tragen dieselbe Kennung; Löcher bleiben durchsichtige Stellen."""

    chosen = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMinimumSize(280, 250)
        self.setAccessibleName(tr("Konturvorschau"))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt
        super().resizeEvent(event)
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item is not None and item.data(0):
                self.chosen.emit(str(item.data(0)))
                event.accept()
                return
        super().mousePressEvent(event)


class ContourField(QWidget):
    """Zusammenfassung einer gespeicherten Wahl, ohne den JSON-Text zu zeigen."""

    valueChanged = Signal()
    validityChanged = Signal()
    choiceRequested = Signal()

    def __init__(self, start: Any = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = ""
        self.valid = True
        self.summary = QLabel("", self)
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.button = QPushButton(tr("Konturen wählen …"), self)
        self.button.clicked.connect(self.choiceRequested)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.summary, 1)
        layout.addWidget(self.button)
        self.setFocusProxy(self.button)
        self.setAccessibleName(tr("Konturauswahl"))
        self.set_value(start)

    def value(self) -> str:
        return self._value

    def set_value(self, value: Any) -> None:
        """Bewahrt auch unbekannte Daten bis zur ausdrücklichen neuen Wahl."""
        self._value = str(value) if value is not None else ""
        self.valid = not self._value
        if not self._value:
            text = tr("Alle Konturen · bisherige Auswahl")
        else:
            try:
                selected = json.loads(self._value)
            except ValueError, TypeError:
                selected = None
            if (
                isinstance(selected, list)
                and selected
                and all(isinstance(entry, str) and entry for entry in selected)
            ):
                self.valid = True
                text = tr("Ausgewählte Konturen: {count}").format(count=len(set(selected)))
            else:
                text = tr("Wählen Sie mindestens eine gültige Kontur.")
        self.summary.setText(text)
        self.setAccessibleDescription(text)
        self.valueChanged.emit()
        self.validityChanged.emit()


class OutlineDialog(QDialog):
    """Wählt gespeicherte Profile; ``values`` passen direkt in ``load_outline``.

    Neue Importe beginnen mit allen geprüften Profilen sichtbar ausgewählt.
    Die explizite Auswahl eines bestehenden Schritts wird wiederhergestellt.
    Der Besitzer ruft beim Aufräumen ``release`` auf, auch nach Abbrechen.
    """

    valuesChanged = Signal()

    def __init__(
        self,
        payload: bytes,
        suffix: str,
        parent: QWidget | None = None,
        values: dict[str, Any] | None = None,
        *,
        selection_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Zeichnung hochziehen"))
        self.resize(1050, 650)
        self._initial = dict(values or {})
        self._leash = WorkerLeash(self)
        self._worker: _ReadWorker | _PreviewWorker | None = None
        self._profiles: tuple[_ProfileDisplay, ...] = ()
        self._items: dict[str, QGraphicsPathItem] = {}
        self._revision = 0
        self._ready_revision = -1
        self._closed = False
        self._pending = False
        self.result_preview: outline.OutlineResult | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._preview)

        layout = QVBoxLayout(self)
        layout.setSpacing(ROOMY)
        note = QLabel(tr("Wählen Sie die Flächen für Ihr Teil. Innenringe bleiben Löcher."), self)
        note.setWordWrap(True)
        layout.addWidget(note)
        middle = QHBoxLayout()
        left = QVBoxLayout()
        title = QLabel(tr("Konturen"), self)
        set_level(title, "section")
        left.addWidget(title)
        self.profiles = QListWidget(self)
        self.profiles.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.profiles.setAccessibleName(tr("Konturen"))
        self.profiles.setWordWrap(True)
        self.profiles.setMinimumWidth(245)
        self.profiles.itemChanged.connect(self._changed)
        self.profiles.currentRowChanged.connect(self._current_changed)
        left.addWidget(self.profiles, 1)
        selection = QHBoxLayout()
        self.select_all = QPushButton(tr("Alle gültigen"), self)
        self.select_none = QPushButton(tr("Keine"), self)
        self.select_all.clicked.connect(self._all)
        self.select_none.clicked.connect(self._none)
        selection.addWidget(self.select_all)
        selection.addWidget(self.select_none)
        left.addLayout(selection)
        self.detail = QLabel("", self)
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        left.addWidget(self.detail)
        middle.addLayout(left, 1)
        images = QVBoxLayout()
        images.addWidget(QLabel(tr("Konturvorschau"), self))
        self.contour_view = _ProfileView(self)
        self.contour_view.chosen.connect(self._toggle)
        images.addWidget(self.contour_view, 1)
        middle.addLayout(images, 1)
        preview = QVBoxLayout()
        preview.addWidget(QLabel(tr("So sieht Ihr Teil aus"), self))
        self.preview = QSvgWidget(self)
        self.preview.setAccessibleName(tr("Ergebnisvorschau"))
        self.preview.setMinimumSize(280, 250)
        preview.addWidget(self.preview, 1)
        self.measurement = QLabel("", self)
        self.measurement.setWordWrap(True)
        preview.addWidget(self.measurement)
        middle.addLayout(preview, 1)
        layout.addLayout(middle, 1)
        form = QFormLayout()
        self._fields: dict[str, LengthSpin] = {}
        for spec in LoadOutlineParams.spec():
            if spec.name not in ("height", "width"):
                continue
            field = LengthSpin(self)
            assert spec.minimum is not None and spec.maximum is not None
            field.set_range_mm(float(spec.minimum), float(spec.maximum))
            field.set_value_mm(float(self._initial.get(spec.name, spec.default)))
            if spec.name == "width":
                field.setSpecialValueText(tr("Originalbreite"))
            field.setAccessibleName(str(spec.title))
            field.setAccessibleDescription(str(spec.doc))
            field.setToolTip(str(spec.doc))
            field.setStatusTip(str(spec.doc))
            field.setEnabled(not selection_only)
            form.addRow(str(spec.title), field)
            label = form.labelForField(field)
            label.setToolTip(str(spec.doc))
            field.valueChangedMm.connect(self._changed)
            self._fields[spec.name] = field
        layout.addLayout(form)
        if selection_only:
            explanation = QLabel(tr("Höhe und Breite ändern Sie im Operationsdialog."), self)
            explanation.setWordWrap(True)
            layout.addWidget(explanation)
        self.state = ErrorNotice(self)
        self.state.setText(tr("Konturen werden gelesen und geprüft …"))
        layout.addWidget(self.state)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.accept_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.accept_button.setText(tr("Zeichnung hochziehen"))
        self.accept_button.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Abbrechen"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        # Fokus auf einer Nebenhandlung ändert nicht die empfohlene Handlung.
        no_primary(self)
        make_primary(self.accept_button)
        worker = _ReadWorker(payload, suffix)
        worker.ready.connect(self._read)
        worker.failed.connect(self._read_failed)
        worker.progress.connect(self._read_progress)
        self._start(worker)

    def _start(self, worker: _ReadWorker | _PreviewWorker) -> None:
        self._worker = worker
        worker.crashed.connect(self._crashed)
        worker.finished.connect(self._finished)
        self._leash.start(worker)

    def _read_progress(self, done: int, total: int) -> None:
        if not self._closed:
            self.progress.setRange(0, total)
            self.progress.setValue(done)

    def _read(self, profiles: tuple[_ProfileDisplay, ...]) -> None:
        if self._closed:
            return
        self._profiles = profiles
        raw = tuple(entry.profile for entry in profiles)
        try:
            selected = {
                entry.id
                for entry in outline.selected_profiles(raw, str(self._initial.get("contours", "")))
            }
        except AppError:
            selected = set()
        with QSignalBlocker(self.profiles):
            scene = self.contour_view.scene()
            for number, entry in enumerate(profiles, 1):
                title = tr("Kontur {number}").format(number=number)
                text = tr("{title} · {width} × {height}").format(
                    title=title, width=length(entry.width), height=length(entry.height)
                )
                if entry.reason:
                    text += "\n" + tr("Nicht extrudierbar")
                item = QListWidgetItem(text, self.profiles)
                item.setData(Qt.ItemDataRole.UserRole, entry.profile.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, text)
                item.setToolTip(entry.reason or tr("Innenringe bleiben Löcher."))
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                if not entry.reason:
                    flags |= Qt.ItemFlag.ItemIsUserCheckable
                item.setFlags(flags)
                if not entry.reason:
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if entry.profile.id in selected
                        else Qt.CheckState.Unchecked
                    )
                shape = scene.addPath(entry.path)
                shape.setData(0, entry.profile.id)
                shape.setToolTip(text)
                self._items[entry.profile.id] = shape
                label = scene.addSimpleText(str(number))
                label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                label.setPos(entry.label_at)
                label.setBrush(self.palette().text())
                label.setData(0, entry.profile.id)
                label.setZValue(2)
        scene.setSceneRect(scene.itemsBoundingRect())
        self.contour_view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.profiles.setCurrentRow(
            next((index for index, entry in enumerate(profiles) if not entry.reason), 0)
        )
        self._changed()

    def _selected(self) -> list[str]:
        return [
            str(self.profiles.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.profiles.count())
            if self.profiles.item(i).checkState() == Qt.CheckState.Checked
        ]

    def values(self) -> dict[str, Any]:
        """Nur reproduzierbare Operationswerte; Quelle und Name bleiben beim Besitzer."""
        return {
            **{name: field.value_mm() for name, field in self._fields.items()},
            "contours": json.dumps(self._selected(), separators=(",", ":")),
        }

    def _changed(self, *_args: Any) -> None:
        if self._closed:
            return
        self._revision += 1
        self.accept_button.setEnabled(False)
        self._paint_selection()
        selected = self._selected()
        self._pending = bool(selected)
        if self._worker is not None and isinstance(self._worker, _PreviewWorker):
            self._worker.requestInterruption()
        self.state.setText(
            tr("Vorschau wird berechnet …")
            if selected
            else tr("Wählen Sie mindestens eine gültige Kontur.")
        )
        self.progress.setRange(0, 0)
        self.progress.setVisible(bool(selected))
        self._timer.start()
        self.valuesChanged.emit()

    def _paint_selection(self) -> None:
        selected = set(self._selected())
        with QSignalBlocker(self.profiles):
            for index, entry in enumerate(self._profiles):
                shape = self._items[entry.profile.id]
                chosen = entry.profile.id in selected
                item = self.profiles.item(index)
                text = str(item.data(Qt.ItemDataRole.UserRole + 1))
                if not entry.reason:
                    text += "\n" + (tr("Wird extrudiert") if chosen else tr("Nicht ausgewählt"))
                item.setText(text)
                pen = QPen(
                    self.palette().highlight().color() if chosen else self.palette().text().color()
                )
                pen.setCosmetic(True)
                pen.setWidth(3 if chosen else 1)
                if entry.reason:
                    pen.setStyle(Qt.PenStyle.DashLine)
                shape.setPen(pen)
                shape.setBrush(
                    self.palette().highlight() if chosen else QBrush(Qt.BrushStyle.NoBrush)
                )

    def _current_changed(self, row: int) -> None:
        if 0 <= row < len(self._profiles):
            entry = self._profiles[row]
            self.detail.setText(
                entry.reason
                or tr("Fläche: {area} · Innenringe: {count}").format(
                    area=area(entry.area), count=len(entry.profile.polygon.interiors)
                )
            )

    def _toggle(self, identifier: str) -> None:
        for index in range(self.profiles.count()):
            item = self.profiles.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == identifier:
                self.profiles.setCurrentItem(item)
                if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    item.setCheckState(
                        Qt.CheckState.Unchecked
                        if item.checkState() == Qt.CheckState.Checked
                        else Qt.CheckState.Checked
                    )
                return

    def _set_selection(self, checked: bool) -> None:
        with QSignalBlocker(self.profiles):
            for index in range(self.profiles.count()):
                item = self.profiles.item(index)
                if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    item.setCheckState(
                        Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                    )
        self._changed()

    def _all(self) -> None:
        self._set_selection(True)

    def _none(self) -> None:
        self._set_selection(False)

    def _preview(self) -> None:
        if self._closed or not self._pending or self._worker is not None:
            return
        self._pending = False
        worker = _PreviewWorker(
            tuple(entry.profile for entry in self._profiles),
            self.values(),
            self._revision,
            current_theme(),
        )
        worker.ready.connect(self._preview_ready)
        worker.failed.connect(self._preview_failed)
        self._start(worker)

    def _preview_ready(self, revision: int, result: outline.OutlineResult, svg: str) -> None:
        if self._closed or revision != self._revision:
            return
        self.result_preview = result
        self._ready_revision = revision
        self.preview.load(QByteArray(svg.encode("utf-8")))
        self.measurement.setText(
            tr("{x} × {y} × {z}").format(
                **dict(
                    zip(("x", "y", "z"), (length(v) for v in result.mesh.bounds.size), strict=True)
                )
            )
        )
        self.state.setText(
            tr("Ausgewählte Konturen: {count}. Die Vorschau zeigt das Ergebnis.").format(
                count=result.contours
            )
        )
        self.progress.hide()
        self.accept_button.setEnabled(True)

    def _read_failed(self, problem: object) -> None:
        if not self._closed:
            self._error(problem)

    def _preview_failed(self, revision: int, problem: object) -> None:
        if not self._closed and revision == self._revision:
            self._error(problem)

    def _crashed(self, detail: str) -> None:
        worker = self.sender()
        if self._closed or (
            isinstance(worker, _PreviewWorker) and worker.revision != self._revision
        ):
            return
        self._error(InternalError(detail=detail))

    def _error(self, problem: object) -> None:
        self.progress.hide()
        self.accept_button.setEnabled(False)
        self.state.set_error(
            problem,
            {
                "correct_input": weak_slot(self, OutlineDialog._focus_selection),
            },
        )

    def _focus_selection(self) -> None:
        self.profiles.setFocus()

    def _finished(self) -> None:
        if self.sender() is self._worker:
            self._worker = None
        if not self._closed and self._pending:
            self._timer.start()

    def accept(self) -> None:
        if (
            not self._closed
            and self.accept_button.isEnabled()
            and self._ready_revision == self._revision
        ):
            super().accept()

    def done(self, result: int) -> None:
        self.release(DIALOG_WAIT_MS)
        super().done(result)

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Verwirft späte Ergebnisse und hält den laufenden Arbeiter bis zum Ende."""
        self._closed = True
        self._timer.stop()
        if self._worker is not None:
            self._worker.requestInterruption()
        self._leash.wait_all(timeout_ms)
