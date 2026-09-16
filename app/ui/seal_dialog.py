"""Dichtweg als bestätigte Zeichnung oder sichtbare Öffnung wählen (§19.2)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPathItem,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError, InternalError, OperationCancelled, ValidationError
from app.core.geom.seal import MAX_OPENING_SIGNATURE, OpeningChoice, match_opening, opening_choices
from app.core.types import FeatureRef, Parameter, SceneObject
from app.i18n import _, tr
from app.ui.labels import area, feature_label
from app.ui.leash import DIALOG_WAIT_MS, WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.outline_dialog import _ProfileView
from app.ui.sketch_editor import SketchEditorDialog, Surroundings
from app.ui.style import make_primary, no_primary

_FIELDS = ("path_sketch", "support_feature", "opening_signature", "counterface")


def _reference(text: str) -> FeatureRef:
    """Eine gespeicherte Flächenangabe als korrigierbare Eingabe lesen."""
    try:
        return FeatureRef.parse(text)
    except ValueError as problem:
        raise ValidationError(
            "support_feature",
            _("Wählen Sie eine vorhandene Fläche zusammen mit ihrem Körper."),
        ) from problem


def selection_status(values: Mapping[str, Any]) -> tuple[bool, str]:
    """Leichte Datenprüfung; die geometrische Bestätigung gehört in den Arbeiter."""
    drawing, support, signature, counter = (str(values.get(key, "")) for key in _FIELDS)
    for reference in (support, counter):
        if reference:
            try:
                _reference(reference)
            except ValidationError:
                return False, tr("Wählen Sie eine vorhandene Fläche zusammen mit ihrem Körper.")
    if drawing:
        if support or signature:
            return False, tr("Wählen Sie entweder eine Zeichnung oder eine Öffnung als Dichtweg.")
        from app.core.sketch.serialize import sketch_from_text

        try:
            if not sketch_from_text(drawing).elements:
                return False, tr("Zeichnen Sie einen geschlossenen Dichtweg.")
        except AppError:
            return False, tr("Öffnen und korrigieren Sie die Zeichnung für den Dichtweg.")
        return True, tr("Dichtweg: Zeichnung")
    if not support or not signature:
        return False, tr("Wählen oder zeichnen Sie einen geschlossenen Dichtweg.")
    if len(signature) > MAX_OPENING_SIGNATURE:
        return False, tr("Wählen Sie die gewünschte Öffnung erneut.")
    try:
        data = json.loads(signature)
    except ValueError, RecursionError:
        data = None
    if (
        not isinstance(data, dict)
        or set(data) != {"version", "topology", "carrier", "ring"}
        or type(data.get("version")) is not int
        or data["version"] != 1
    ):
        return False, tr("Wählen Sie die gewünschte Öffnung erneut.")
    return True, tr("Dichtweg: bestätigte Öffnung")


class SealPathField(QWidget):
    """Vier zusammengehörige Werte mit einer sichtbaren Zusammenfassung."""

    valueChanged = Signal()
    validityChanged = Signal()
    choiceRequested = Signal()

    def __init__(self, start: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._values = dict.fromkeys(_FIELDS, "")
        self._values["opening_signature"] = start
        self.valid = False
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.button = QPushButton(tr("Dichtweg wählen …"), self)
        # Ein Nebenknopf im Operationsdialog: Mit Fokus würde Qt ihn sonst zum
        # Default machen und *Übernehmen* seine Akzentfarbe nehmen.
        self.button.setAutoDefault(False)
        self.button.clicked.connect(self.choiceRequested)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.summary, 1)
        layout.addWidget(self.button)
        self.setFocusProxy(self.button)
        self.setAccessibleName(tr("Dichtweg"))
        self.set_selection(self._values)

    def value(self) -> str:
        return self._values["opening_signature"]

    def set_value(self, value: str) -> None:
        self.set_selection({**self._values, "opening_signature": value})

    def selection(self) -> dict[str, str]:
        return dict(self._values)

    def set_selection(self, values: Mapping[str, Any]) -> None:
        self._values = {key: str(values.get(key, "")) for key in _FIELDS}
        self.valid, text = selection_status(self._values)
        self.summary.setText(text)
        self.setAccessibleDescription(text)
        self.valueChanged.emit()
        self.validityChanged.emit()


def _path(polygon: Any) -> QPainterPath:
    result = QPainterPath()
    result.setFillRule(Qt.FillRule.OddEvenFill)
    for ring in (polygon.exterior, *polygon.interiors):
        points = list(ring.coords)
        result.moveTo(float(points[0][0]), -float(points[0][1]))
        for x, y in points[1:]:
            result.lineTo(float(x), -float(y))
        result.closeSubpath()
    return result


@dataclass(frozen=True, slots=True)
class _Display:
    choices: tuple[OpeningChoice, ...]
    paths: tuple[QPainterPath, ...]
    carrier: QPainterPath
    selected: int


class _ReadWorker(Worker):
    ready = Signal(int, object)
    failed = Signal(int, object)

    def __init__(
        self,
        source: SceneObject,
        objects: Sequence[SceneObject],
        values: dict[str, str],
        parameters: dict[str, float],
        revision: int,
    ) -> None:
        super().__init__()
        self.source, self.objects, self.values = source, tuple(objects), values
        self.parameters, self.revision = parameters, revision

    def _check(self) -> None:
        if self.isInterruptionRequested():
            raise OperationCancelled()

    def work(self) -> None:
        from app.core.geom.contours import polygons_of, section_of
        from app.core.geom.seal import support_geometry
        from app.core.sketch.profile import profile_of
        from app.core.sketch.serialize import sketch_from_text
        from app.core.sketch.solver import solve_sketch

        try:
            self._check()
            counter = self.values["counterface"]
            if counter:
                ref = _reference(counter)
                other = next((obj for obj in self.objects if obj.id == ref.object_id), None)
                if other is None or other.id == self.source.id:
                    raise ValidationError(
                        "counterface",
                        _("Wählen Sie eine Gegenfläche an einem anderen vorhandenen Körper."),
                    )
                support_geometry(other, ref, check_cancelled=self._check)
            drawing = self.values["path_sketch"]
            if drawing:
                solved = solve_sketch(sketch_from_text(drawing), self.parameters)
                profile = profile_of(solved)
                polygons = polygons_of(section_of(profile, check_cancelled=self._check))
                if len(polygons) != 1 or polygons[0].interiors:
                    raise ValidationError(
                        "path_sketch",
                        _("Zeichnen Sie genau einen geschlossenen Dichtweg ohne Innenringe."),
                    )
                display = _Display((), (_path(polygons[0]),), QPainterPath(), 0)
            else:
                ref = _reference(self.values["support_feature"])
                choices = opening_choices(self.source, ref, check_cancelled=self._check)
                if not choices:
                    raise ValidationError(
                        "support_feature",
                        _(
                            "Diese Fläche hat keine geschlossene Öffnung. Wählen Sie eine "
                            "andere Fläche oder zeichnen Sie den Dichtweg."
                        ),
                    )
                selected = None
                if self.values["opening_signature"]:
                    try:
                        selected = match_opening(choices, self.values["opening_signature"])
                    except ValidationError:
                        # Die neue sichtbare Wahl ist der Rückweg aus einer
                        # nicht mehr lesbaren gespeicherten Antwort.
                        selected = None
                carrier = QPainterPath()
                for part in getattr(choices[0].carrier, "geoms", (choices[0].carrier,)):
                    carrier.addPath(_path(part))
                display = _Display(
                    choices,
                    tuple(_path(choice.ring) for choice in choices),
                    carrier,
                    next((i for i, choice in enumerate(choices) if choice is selected), -1),
                )
            self._check()
            self.ready.emit(self.revision, display)
        except OperationCancelled:
            return
        except AppError as problem:
            self.failed.emit(self.revision, problem.with_traceback(None))


class SealPathDialog(QDialog):
    """Sammelt nur vier Parameterwerte; Übernehmen erzeugt keinen Dokumentzustand."""

    def __init__(
        self,
        source: SceneObject,
        objects: Sequence[SceneObject],
        values: Mapping[str, Any],
        *,
        parameters: Mapping[str, Parameter] | None = None,
        parent: QWidget | None = None,
        surroundings: Surroundings | None = None,
    ) -> None:
        super().__init__(parent)
        self.source, self.objects = source, tuple(objects)
        self._surroundings = surroundings
        self._parameters = {name: item.value for name, item in (parameters or {}).items()}
        self._values = {key: str(values.get(key, "")) for key in _FIELDS}
        self._worker: _ReadWorker | None = None
        self._leash = WorkerLeash(self)
        self._revision, self._ready_revision = 0, -1
        self._closed, self._pending = False, False
        self._display: _Display | None = None
        self._items: list[QGraphicsPathItem] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start)
        self.setWindowTitle(tr("Dichtweg wählen"))
        self.resize(860, 580)
        layout = QVBoxLayout(self)
        self.mode = QComboBox(self)
        self.mode.addItem(tr("Zeichnung"), userData="drawn")
        self.mode.addItem(tr("Öffnung am Körper"), userData="opening")
        self.mode.setCurrentIndex(1 if self._values["support_feature"] else 0)
        self.support = QComboBox(self)
        self.support.addItem(tr("Trägerfläche wählen …"), userData="")
        self.counterface = QComboBox(self)
        self.counterface.addItem(tr("Keine Gegenfläche prüfen"), userData="")
        for obj in self.objects:
            for key, feature in obj.features.items():
                if feature.kind != "face":
                    continue
                text = f"{obj.name} · {feature_label(key, feature)}"
                target = self.support if obj.id == source.id else self.counterface
                target.addItem(text, userData=str(FeatureRef(obj.id, key)))
        for combo, key in ((self.support, "support_feature"), (self.counterface, "counterface")):
            index = combo.findData(self._values[key])
            if index < 0:
                combo.addItem(
                    tr("Gespeicherte Fläche fehlt — neu wählen"), userData=self._values[key]
                )
                index = combo.count() - 1
            combo.setCurrentIndex(index)
        self.sketch_button = QPushButton(tr("Dichtweg zeichnen …"), self)
        self.sketch_button.clicked.connect(self._draw)
        form = QFormLayout()
        form.addRow(tr("Dichtweg aus"), self.mode)
        form.addRow(tr("Trägerfläche"), self.support)
        form.addRow(tr("Zeichnung"), self.sketch_button)
        form.addRow(tr("Gegenfläche"), self.counterface)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.contours = QListWidget(self)
        self.contours.setAccessibleName(tr("Erkannte Öffnungen"))
        self.contours.setMinimumWidth(220)
        self.contour_view = _ProfileView(self)
        self.contour_view.setAccessibleName(tr("Dichtweg in der Trägerfläche"))
        self.contour_view.chosen.connect(self._image_chosen)
        row.addWidget(self.contours, 1)
        row.addWidget(self.contour_view, 2)
        layout.addLayout(row, 1)
        self.status = QLabel(self)
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setAccessibleName(tr("Dichtweg wird geprüft"))
        layout.addWidget(self.progress)
        hint = QLabel(
            tr(
                "Diese Wahl legt den Verlauf fest. Nutmaße, Materialien und das vollständige "
                "Ergebnis prüfen Sie anschließend im Operationsdialog."
            ),
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.accept_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.accept_button.setText(tr("Dichtweg übernehmen"))
        self.accept_button.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Abbrechen"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        no_primary(self)
        make_primary(self.accept_button)
        self.mode.currentIndexChanged.connect(self._request)
        self.support.currentIndexChanged.connect(self._support_changed)
        self.counterface.currentIndexChanged.connect(self._request)
        self.contours.currentRowChanged.connect(self._chosen)
        self._request()

    def values(self) -> dict[str, str]:
        result = dict(self._values)
        result["counterface"] = str(self.counterface.currentData())
        if self.mode.currentData() == "drawn":
            result["support_feature"] = result["opening_signature"] = ""
        else:
            result["path_sketch"] = ""
            result["support_feature"] = str(self.support.currentData())
        return result

    def _support_changed(self) -> None:
        self._values["opening_signature"] = ""
        self._request()

    def _request(self) -> None:
        if self._closed:
            return
        self._revision += 1
        self._ready_revision = -1
        self.accept_button.setEnabled(False)
        opening = self.mode.currentData() == "opening"
        self.support.setEnabled(opening)
        self.sketch_button.setEnabled(not opening)
        self.contours.setEnabled(False)
        self.contour_view.setEnabled(False)
        self.status.setText(tr("Dichtweg wird geprüft …"))
        self.progress.show()
        self._pending = True
        if self._worker is not None:
            self._worker.requestInterruption()
        else:
            self._timer.start(0)

    def _start(self) -> None:
        if self._closed or not self._pending or self._worker is not None:
            return
        self._pending = False
        values = self.values()
        if not values["path_sketch"] and not values["support_feature"]:
            self.progress.hide()
            self.status.setText(tr("Wählen oder zeichnen Sie einen geschlossenen Dichtweg."))
            return
        worker = _ReadWorker(self.source, self.objects, values, self._parameters, self._revision)
        self._worker = worker
        worker.ready.connect(self._read)
        worker.failed.connect(self._failed)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(self._finished)
        self._leash.start(worker)

    def _read(self, revision: int, display: _Display) -> None:
        if self._closed or revision != self._revision:
            return
        self._display = display
        self._ready_revision = revision
        self.progress.hide()
        with QSignalBlocker(self.contours):
            self.contours.clear()
            scene = self.contour_view.scene()
            scene.clear()
            self._items = []
            pen = QPen(self.palette().text().color())
            pen.setCosmetic(True)
            scene.addPath(display.carrier, pen, QBrush(self.palette().mid().color()))
            for index, path in enumerate(display.paths):
                item = scene.addPath(path, pen)
                item.setData(0, str(index))
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
                self._items.append(item)
                text = tr("Kontur {number}", number=index + 1)
                if display.choices:
                    text += f" · {area(display.choices[index].area)}"
                self.contours.addItem(text)
            scene.setSceneRect(scene.itemsBoundingRect())
            self.contour_view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.contours.setCurrentRow(display.selected)
        self.contours.setEnabled(bool(display.choices))
        self.contour_view.setEnabled(bool(display.choices))
        self._chosen(display.selected)

    def _image_chosen(self, key: str) -> None:
        if self._ready_revision == self._revision:
            self.contours.setCurrentRow(int(key))

    def _chosen(self, index: int) -> None:
        if self._display is None or self._ready_revision != self._revision:
            return
        valid = 0 <= index < len(self._display.paths)
        for row, item in enumerate(self._items):
            active = valid and row == index
            colour = self.palette().highlight().color() if active else self.palette().text().color()
            pen = QPen(colour, 3 if active else 1)
            pen.setCosmetic(True)
            item.setPen(pen)
            item.setSelected(active)
            fill = QColor(colour)
            fill.setAlpha(60 if active else 0)
            item.setBrush(QBrush(fill))
        if valid and self._display.choices:
            self._values["opening_signature"] = self._display.choices[index].signature
            self.status.setText(
                tr(
                    "Gewählt: Kontur {number}. Der hervorgehobene Umriss bestimmt den Dichtweg.",
                    number=index + 1,
                )
            )
        elif valid:
            self.status.setText(tr("Gewählt: die geschlossene Zeichnung."))
        else:
            self._values["opening_signature"] = ""
            self.status.setText(
                tr("Klicken Sie auf die gewünschte Öffnung im Bild oder in der Liste.")
            )
        self.accept_button.setEnabled(valid)

    def _failed(self, revision: int, problem: AppError) -> None:
        if not self._closed and revision == self._revision:
            self.progress.hide()
            self.status.setText(str(problem.detail or problem.title))
            self.accept_button.setEnabled(False)

    def _crashed(self, problem: InternalError) -> None:
        if self.sender() is self._worker:
            assert self._worker is not None
            self._failed(self._worker.revision, problem)

    def _finished(self) -> None:
        if self.sender() is self._worker:
            self._worker = None
        if not self._closed and self._pending:
            self._timer.start(0)

    def _draw(self) -> None:
        dialog = SketchEditorDialog(
            self._values["path_sketch"], self._parameters, self, self._surroundings
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._values["path_sketch"] = dialog.sketch_text()
            self._request()
        dialog.deleteLater()

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
        self._closed = True
        self._timer.stop()
        if self._worker is not None:
            self._worker.requestInterruption()
        self._leash.wait_all(timeout_ms)
