"""Die Körper einer STEP-Baugruppe wählen, bevor sie übernommen werden (P7.4).

Der Kunde sieht jeden Körper der Datei mit Namen, Maßen und Farben und wählt,
welche er übernimmt; die Vorschau zeigt, wo in der Baugruppe der gerade
gewählte sitzt. Im Dokument steht danach nur die Liste der Körperkennungen
(``load_step.bodies``). Lesen und Zeichnen laufen im Arbeiter.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QByteArray, QSignalBlocker, QSize, Qt, QTimer, Signal
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
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
from app.core.errors import AppError, InternalError, OperationCancelled
from app.core.ingest.plan import BodyChoice, choice_of, selection
from app.core.registry.params import body_keys
from app.i18n import tr
from app.ui.dialogs import ErrorNotice
from app.ui.filament_picker import swatch
from app.ui.labels import colour_name, length
from app.ui.leash import DIALOG_WAIT_MS, WAIT_TIMEOUT_MS, Worker, WorkerLeash, weak_slot
from app.ui.outline_dialog import ContourField
from app.ui.style import ROOMY, SPACE, WIDE, make_primary, no_primary, set_level
from app.ui.theme import Theme, current_theme

#: Wie groß die Vorschau gezeichnet wird, in Pixeln (die längere Seite).
_PREVIEW_PIXELS = 480

#: Seitenlänge des Farbfelds an jeder Zeile der Liste.
_SWATCH = 18


class StepBodiesField(ContourField):
    """Zusammenfassung der Körperauswahl im Operationsdialog, ohne den JSON-Text.

    Erbt vom Konturfeld, weil beide dieselbe Aufgabe haben — eine gespeicherte
    Auswahl zeigen und auf Klick die Wahl öffnen —, und weil der
    Operationsdialog Gültigkeit, Wert und Signale an dieser Art abfragt. Der
    leere Wert ist der Stand vor P7.4: die ganze Datei als ein Körper.
    """

    def __init__(self, start: Any = "", parent: QWidget | None = None) -> None:
        super().__init__(start, parent)
        self.button.setText(tr("Körper wählen …"))
        self.setAccessibleName(tr("Körperauswahl"))

    def set_value(self, value: Any) -> None:
        self._value = str(value) if value is not None else ""
        try:
            keys = body_keys(self._value)
        except AppError:
            self.valid = False
            text = tr("Wählen Sie mindestens einen Körper der Datei.")
        else:
            self.valid = True
            text = (
                tr("Ausgewählte Körper: {count}").format(count=len(keys))
                if keys
                else tr("Ganze Datei als ein Körper · bisherige Auswahl")
            )
        self.summary.setText(text)
        self.setAccessibleDescription(text)
        self.valueChanged.emit()
        self.validityChanged.emit()


class _Interruption:
    """Der Abbruchwunsch eines Arbeiters als Token für den Kern (``CancelToken``)."""

    def __init__(self, worker: Worker) -> None:
        self._worker = worker

    @property
    def is_cancelled(self) -> bool:
        return bool(self._worker.isInterruptionRequested())

    def raise_if_cancelled(self) -> None:
        if self._worker.isInterruptionRequested():
            raise OperationCancelled


class _ReadWorker(Worker):
    """Liest die Körper einer STEP-Datei für die Auswahl — ohne Form, nur Auskunft."""

    ready = Signal(object)
    failed = Signal(object)

    def __init__(self, payload: bytes, stem: str) -> None:
        super().__init__()
        self.payload, self.stem = payload, stem

    def work(self) -> None:
        from app.core.brep import step

        try:
            assembly = step.read_assembly(self.payload, self.stem, cancelled=_Interruption(self))
            if not self.isInterruptionRequested():
                self.ready.emit(tuple(choice_of(body) for body in assembly.bodies))
        except OperationCancelled:
            return
        except AppError as problem:
            self.failed.emit(problem.with_traceback(None))

    def release_finished_references(self) -> None:
        del self.payload
        super().release_finished_references()


@dataclass(frozen=True, slots=True)
class _Scene:
    """Was die Vorschau zeichnet: die gewählten Körper und der gerade betrachtete."""

    chosen: tuple[BodyChoice, ...]
    current: BodyChoice | None


class _RenderWorker(Worker):
    """Zeichnet die Baugruppe als Hüllquader, den betrachteten Körper hervorgehoben.

    **Quader, nicht die Form.** Die Vorschau soll zeigen, wo ein Körper sitzt
    und wie groß er ist — gemessen an 200 gerundeten Teilen kostete die echte
    Vernetzung 5,9 s und das Bild daraus 3,6 s (33 MB SVG). Hüllquader aus den
    Maßen der Auswahl kosten nichts, und die Form des einzelnen Körpers zeigt
    nach der Übernahme die Ansicht.
    """

    ready = Signal(int, str)

    def __init__(self, scene: _Scene, revision: int, theme: Theme) -> None:
        super().__init__()
        self.scene, self.revision, self.theme = scene, revision, theme

    def work(self) -> None:
        import numpy as np
        import trimesh

        bodies = list(self.scene.chosen)
        current = self.scene.current
        if current is not None and current not in bodies:
            bodies.append(current)
        if not bodies:
            self.ready.emit(self.revision, "")
            return
        boxes: list[trimesh.Trimesh] = []
        highlighted: list[int] = []
        for body in bodies:
            size = np.maximum(np.asarray(body.size, dtype=float), 1e-3)
            box = trimesh.creation.box(extents=size)
            box.apply_translation(np.asarray(body.low, dtype=float) + size / 2.0)
            if body == current:
                start = int(sum(len(entry.faces) for entry in boxes))
                highlighted.extend(range(start, start + len(box.faces)))
            boxes.append(box)
            if self.isInterruptionRequested():
                return
        joined = trimesh.util.concatenate(boxes)
        if not isinstance(joined, trimesh.Trimesh):
            return
        svg = drawing.project(
            joined,
            size=_PREVIEW_PIXELS,
            theme=self.theme,
            edges=True,
            highlight_faces=highlighted,
        )
        if not self.isInterruptionRequested():
            self.ready.emit(self.revision, svg)


class StepBodiesDialog(QDialog):
    """Wählt die Körper einer STEP-Baugruppe; ``values`` passen in ``load_step``.

    Ein neuer Import beginnt mit allen Körpern gewählt; eine gespeicherte
    Auswahl wird wiederhergestellt. ``choices`` kommen aus dem Einleseplan und
    füllen die Liste sofort; ohne sie liest der Dialog die Datei selbst. Der
    Besitzer ruft beim Aufräumen ``release`` auf, auch nach Abbrechen.
    """

    valuesChanged = Signal()

    def __init__(
        self,
        payload: bytes,
        stem: str,
        parent: QWidget | None = None,
        values: dict[str, Any] | None = None,
        *,
        choices: Sequence[BodyChoice] = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("STEP laden"))
        self.resize(900, 600)
        self._initial = dict(values or {})
        self._leash = WorkerLeash(self)
        self._reader: _ReadWorker | None = None
        self._renderer: _RenderWorker | None = None
        self._choices: tuple[BodyChoice, ...] = ()
        self._revision = 0
        self._closed = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._render)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(ROOMY)
        note = QLabel(
            tr("Wählen Sie die Körper, die Sie übernehmen. Namen und Farben kommen aus der Datei."),
            self,
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        middle = QHBoxLayout()
        left = QVBoxLayout()
        title = QLabel(tr("Körper"), self)
        set_level(title, "section")
        left.addWidget(title)
        self.bodies = QListWidget(self)
        self.bodies.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.bodies.setAccessibleName(tr("Körper"))
        self.bodies.setWordWrap(True)
        self.bodies.setIconSize(QSize(_SWATCH, _SWATCH))
        self.bodies.setMinimumWidth(300)
        self.bodies.itemChanged.connect(self._changed)
        self.bodies.currentRowChanged.connect(self._current_changed)
        left.addWidget(self.bodies, 1)
        buttons_row = QHBoxLayout()
        self.select_all = QPushButton(tr("Alle"), self)
        self.select_none = QPushButton(tr("Keine"), self)
        self.select_all.clicked.connect(self._all)
        self.select_none.clicked.connect(self._none)
        buttons_row.addWidget(self.select_all)
        buttons_row.addWidget(self.select_none)
        left.addLayout(buttons_row)
        self.summary = QLabel("", self)
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        left.addWidget(self.summary)
        middle.addLayout(left, 1)
        right = QVBoxLayout()
        placed_title = QLabel(tr("Lage in der Baugruppe"), self)
        set_level(placed_title, "section")
        right.addWidget(placed_title)
        self.preview = QSvgWidget(self)
        self.preview.setAccessibleName(tr("Lage in der Baugruppe"))
        self.preview.setMinimumSize(320, 280)
        right.addWidget(self.preview, 1)
        self.detail = QLabel("", self)
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        right.addWidget(self.detail)
        middle.addLayout(right, 1)
        layout.addLayout(middle, 1)
        self.state = ErrorNotice(self)
        layout.addWidget(self.state)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        self.accept_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.accept_button.setText(tr("Übernehmen"))
        self.accept_button.setEnabled(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Abbrechen"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        no_primary(self)
        make_primary(self.accept_button)
        if choices:
            self.progress.hide()
            self._fill(tuple(choices))
        else:
            self.state.setText(tr("Die Körper der Datei werden gelesen …"))
            reader = _ReadWorker(payload, stem)
            reader.ready.connect(self._read)
            reader.failed.connect(self._failed)
            reader.crashed.connect(self._crashed)
            reader.finished.connect(self._reader_finished)
            self._reader = reader
            self._leash.start(reader)

    # --- Liste ------------------------------------------------------------------

    def _read(self, choices: tuple[BodyChoice, ...]) -> None:
        if self._closed:
            return
        self.progress.hide()
        self.state.setText("")
        self._fill(choices)

    def _fill(self, choices: tuple[BodyChoice, ...]) -> None:
        self._choices = choices
        try:
            wanted = set(body_keys(self._initial.get("bodies", "")))
        except AppError:
            wanted = set()
        if not wanted or wanted == {"*"}:
            wanted = {choice.key for choice in choices}
        repeats: dict[str, int] = {}
        for choice in choices:
            repeats[choice.part] = repeats.get(choice.part, 0) + 1
        with QSignalBlocker(self.bodies):
            self.bodies.clear()
            for choice in choices:
                size = tr("{x} × {y} × {z}").format(
                    **dict(zip(("x", "y", "z"), (length(v) for v in choice.size), strict=True))
                )
                lines = [choice.name, size]
                if choice.mirrored:
                    lines.append(tr("Gespiegelt eingesetzt"))
                if not choice.solid:
                    lines.append(tr("Offene Flächen, kein geschlossener Körper"))
                item = QListWidgetItem(
                    swatch(choice.colours, _SWATCH, ring_when_empty=True),
                    "\n".join(lines),
                    self.bodies,
                )
                item.setData(Qt.ItemDataRole.UserRole, choice.key)
                # Regel 18: Die Farbe steht auch als Wort da, nicht nur im Feld.
                hints = [
                    tr("Farben: {colours}").format(
                        colours=", ".join(colour_name(colour) for colour in choice.colours)
                    )
                    if choice.colours
                    else tr("Ohne Farbe in der Datei")
                ]
                if repeats[choice.part] > 1:
                    hints.append(
                        tr("Dasselbe Teil steht {count}-mal in der Datei.").format(
                            count=repeats[choice.part]
                        )
                    )
                item.setToolTip("\n".join(hints))
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(
                    Qt.CheckState.Checked if choice.key in wanted else Qt.CheckState.Unchecked
                )
        if choices:
            self.bodies.setCurrentRow(0)
        self._changed()

    def keys(self) -> list[str]:
        """Die gewählten Kennungen in der Reihenfolge der Datei."""
        return [
            str(self.bodies.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.bodies.count())
            if self.bodies.item(index).checkState() == Qt.CheckState.Checked
        ]

    def values(self) -> dict[str, Any]:
        """Nur der Operationswert; Quelle und Name bleiben beim Besitzer."""
        return {"bodies": selection(self.keys())}

    def _changed(self, *_args: Any) -> None:
        if self._closed:
            return
        chosen = self.keys()
        total = len(self._choices)
        self.summary.setText(
            tr("Ausgewählt: {count} von {total} Körpern").format(count=len(chosen), total=total)
        )
        self.accept_button.setEnabled(bool(chosen))
        if total and not chosen:
            self.state.setText(tr("Wählen Sie mindestens einen Körper der Datei."))
        elif self._reader is None:
            self.state.setText("")
        self._schedule()
        self.valuesChanged.emit()

    def _current_changed(self, row: int) -> None:
        if 0 <= row < len(self._choices):
            choice = self._choices[row]
            self.detail.setText(
                tr("{name} · {x} × {y} × {z}").format(
                    name=choice.name,
                    **dict(zip(("x", "y", "z"), (length(v) for v in choice.size), strict=True)),
                )
            )
        self._schedule()

    def _set_selection(self, checked: bool) -> None:
        with QSignalBlocker(self.bodies):
            for index in range(self.bodies.count()):
                self.bodies.item(index).setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
        self._changed()

    def _all(self) -> None:
        self._set_selection(True)

    def _none(self) -> None:
        self._set_selection(False)

    # --- Vorschau ---------------------------------------------------------------

    def _schedule(self) -> None:
        if not self._closed and self._choices:
            self._revision += 1
            self._timer.start()

    def _render(self) -> None:
        if self._closed or self._renderer is not None:
            return
        chosen = set(self.keys())
        row = self.bodies.currentRow()
        scene = _Scene(
            chosen=tuple(choice for choice in self._choices if choice.key in chosen),
            current=self._choices[row] if 0 <= row < len(self._choices) else None,
        )
        renderer = _RenderWorker(scene, self._revision, current_theme())
        renderer.ready.connect(self._rendered)
        renderer.crashed.connect(self._crashed)
        renderer.finished.connect(self._renderer_finished)
        self._renderer = renderer
        self._leash.start(renderer)

    def _rendered(self, revision: int, svg: str) -> None:
        if self._closed or revision != self._revision:
            return
        self.preview.load(QByteArray(svg.encode("utf-8")))

    def _renderer_finished(self) -> None:
        if self.sender() is self._renderer:
            self._renderer = None
        # Was sich während des Zeichnens geändert hat, wird nachgezeichnet.
        if not self._closed and self._choices:
            self._timer.start()

    def _reader_finished(self) -> None:
        if self.sender() is self._reader:
            self._reader = None

    # --- Fehler und Ende ------------------------------------------------------------

    def _failed(self, problem: object) -> None:
        if not self._closed:
            self._error(problem)

    def _crashed(self, detail: str) -> None:
        if not self._closed:
            self._error(InternalError(detail=detail))

    def _error(self, problem: object) -> None:
        self.progress.hide()
        self.accept_button.setEnabled(False)
        self.state.set_error(
            problem, {"correct_input": weak_slot(self, StepBodiesDialog._focus_list)}
        )

    def _focus_list(self) -> None:
        self.bodies.setFocus()

    def accept(self) -> None:
        if not self._closed and self.accept_button.isEnabled() and self.keys():
            super().accept()

    def done(self, result: int) -> None:
        self.release(DIALOG_WAIT_MS)
        super().done(result)

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Verwirft späte Ergebnisse und hält laufende Arbeiter bis zum Ende."""
        self._closed = True
        self._timer.stop()
        for worker in (self._reader, self._renderer):
            if worker is not None:
                worker.requestInterruption()
        self._leash.wait_all(timeout_ms)
