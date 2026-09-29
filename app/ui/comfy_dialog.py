"""ComfyUI einrichten, aus der Anwendung heraus (Bauplan §27, §36).

**Der Schritt, der bisher in einem Satz stand.** Wer ComfyUI installiert hatte,
fand die Mesh-Erzeugung weiterhin ausgegraut: Es fehlen die Knoten, die der
Ablauf anspricht, und das Modell, das sie laden. Die Auskunft dazu lautete
„Einzurichten ist sie mit «python tools/setup_comfyui.py»" — an einen Kunden
gerichtet, auf dessen Rechner es diese Datei nicht gibt, weil ``tools/`` im
Paket nicht mitreist.

Der Dialog tut die vier Schritte, die dort standen, und zeigt sie einzeln:
Knoten hinlegen, TripoSG holen, zwei Stellen richten, Pakete nachziehen — und
auf Wunsch die Gewichte, rund 7,5 GB. Abgebrochen wird zwischen den Schritten;
was schon da ist, bleibt, und ein neuer Lauf setzt fort.
"""

from __future__ import annotations

import time
from contextlib import suppress
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.backends import comfy_setup
from app.core.errors import InternalError
from app.core.log import get_logger
from app.i18n import format_decimal, tr
from app.ui.dialogs import show_error
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.style import NORMAL, WIDE, make_primary, set_role

_log = get_logger(__name__)

#: Wie oft die Laufzeit des laufenden Schritts nachgezogen wird. Einer davon
#: lädt 7,5 GB — ohne die Zeit daneben ist ein unbestimmter Balken von einem
#: Hänger nicht zu unterscheiden.
TICK_MS = 1000


class _Worker(Worker):
    """Die Einrichtung: git, pip, und ein Download von 7,5 GB — auf Wunsch zwei."""

    done = Signal(object)
    failed = Signal(str)
    step = Signal(str)

    def __init__(self, comfyui: str, weights: bool, image_model: bool) -> None:
        super().__init__()
        self._comfyui = comfyui
        self._weights = weights
        self._image_model = image_model
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    def work(self) -> None:
        try:
            result = comfy_setup.setup(
                self._comfyui or None,
                weights=self._weights,
                image_model=self._image_model,
                progress=lambda entry: self.step.emit(str(entry)),
                cancelled=lambda: self._stop,
            )
        except comfy_setup.SetupFailed as problem:
            self.failed.emit(str(problem))
            return
        self.done.emit(result)


class ComfySetupDialog(QDialog):
    """Knoten, Quelltext, Pakete und Gewichte — in einem Lauf."""

    def __init__(self, parent: QWidget | None = None, *, image_model: bool | None = None) -> None:
        """``image_model`` belegt das Häkchen fürs Bildmodell vor.

        ``None`` heißt: an, wenn keines da ist. Wer aus dem Erzeugungsdialog
        kommt, weil ihm für den Weg aus Text genau dieses Modell fehlt, will
        es; wer nur die Knoten nachzieht, sieht das Häkchen und entscheidet.
        """
        super().__init__(parent)
        self.setWindowTitle(tr("ComfyUI einrichten"))
        self.setMinimumWidth(560)
        self._worker: _Worker | None = None
        self._leash = WorkerLeash(self)
        self._step = ""
        """Der Schritt, der gerade läuft — für die Zeile mit der Laufzeit."""
        self._started_at = 0.0
        self._tick = QTimer(self)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._show_elapsed)

        intro = QLabel(
            tr(
                "ComfyUI erzeugt das 3D-Modell. Dafür braucht der Ablauf zusätzliche "
                "Bausteine (Knoten) und ein Erzeugungsmodell — beides richtet Solidon "
                "hier ein. ComfyUI selbst wird nicht verändert und danach einmal neu "
                "gestartet."
            ),
            self,
        )
        intro.setWordWrap(True)

        self.folder = QLineEdit(self)
        self.folder.setPlaceholderText(tr("Ordner, in dem „custom_nodes“ steht"))
        self.choose = QPushButton(tr("Ordner wählen …"), self)
        self.choose.clicked.connect(self._choose_folder)

        #: Vorbelegt mit dem, was die Suche findet — eine leere Zeile wäre eine
        #: Frage an jemanden, der die Antwort meist nicht auswendig weiß.
        try:
            found = comfy_setup.find_comfyui()
        except comfy_setup.SetupFailed:
            found = None
        if found is not None:
            self.folder.setText(str(found))

        self.weights = QCheckBox(tr("Modell laden — rund 7,5 GB"), self)
        self.weights.setChecked(found is None or not comfy_setup.weights_present(found))
        if found is not None and comfy_setup.weights_present(found):
            self.weights.setText(tr("Modell ist schon da"))
            self.weights.setEnabled(False)
        # **Das Bildmodell als eigenes Häkchen** (21.09.2026). Es braucht nur
        # der Weg aus Text, und es sind sieben Gigabyte — deshalb nicht still
        # mit den Gewichten, sondern benannt, mit Größe, abwählbar. Robert
        # tippte einen Satz und las, dass ein Bild verlangt wird: Bis dahin
        # holte Solidon dieses Modell gar nicht.
        self.image_model = QCheckBox(
            tr("Bildmodell für den Weg aus Text laden — rund {size} GB").format(
                size=format_decimal(comfy_setup.IMAGE_MODEL_GIGABYTES, 1)
            ),
            self,
        )
        image_model_there = found is not None and comfy_setup.image_model_present(found)
        self.image_model.setChecked(not image_model_there if image_model is None else image_model)
        if image_model_there:
            self.image_model.setText(tr("Bildmodell ist schon da"))
            self.image_model.setEnabled(False)

        self.state = QLabel(self)
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)

        self.start_button = QPushButton(tr("Einrichten"), self)
        self.start_button.clicked.connect(self._start)
        # **Der Akzent lag auf „Ordner wählen …", und niemand hatte ihn dorthin
        # gesetzt.** ``QDialog`` macht beim ersten ``show()`` den ersten Knopf
        # mit ``autoDefault`` zum Default; das ist hier die Zeile über der
        # Handlung. Gemessen am angezeigten Fenster: „Ordner wählen …" trug den
        # Akzent, „Einrichten" nichts — der Hinweis zeigte auf die Vorbereitung
        # statt auf die Sache (Befund D3).
        make_primary(self.start_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(self.folder, stretch=1)
        row.addWidget(self.choose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        layout.addWidget(intro)
        layout.addLayout(row)
        layout.addWidget(self.weights)
        layout.addWidget(self.image_model)
        layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.progress)
        layout.addWidget(self.state)
        layout.addStretch(1)
        layout.addWidget(buttons)

        if found is None:
            # **Der Satz nennt das Kennzeichen.** „Nicht gefunden — der Ordner
            # gehört hier hinein" schickt jemanden suchen, ohne zu sagen,
            # wonach: ComfyUI liegt in einem Ordner, in dem „custom_nodes"
            # steht, und das ist die ganze Auskunft, die es braucht.
            set_role(
                self.state,
                "info",
                tr(
                    "ComfyUI ist an den üblichen Stellen nicht gefunden worden. "
                    "Gesucht wird der Ordner, in dem „custom_nodes“ und „main.py“ "
                    "liegen — bei der tragbaren Version steckt er in "
                    "„ComfyUI_windows_portable“."
                ),
            )

    def _choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, tr("ComfyUI wählen"), self.folder.text() or str(Path.home())
        )
        if chosen:
            self.folder.setText(chosen)

    # --- laufen -----------------------------------------------------------------

    def _start(self) -> None:
        """Einrichten — oder, während es läuft, abbrechen."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.state.setText(tr("Wird abgebrochen — der laufende Schritt läuft aus."))
            return
        self.progress.setVisible(True)
        self.start_button.setText(tr("Abbrechen"))
        self.choose.setEnabled(False)
        self._step = str(tr("Wird eingerichtet …"))
        self._started_at = time.monotonic()
        self._show_elapsed()
        self._tick.start()

        worker = _Worker(
            self.folder.text().strip(),
            self.weights.isChecked(),
            self.image_model.isChecked() and self.image_model.isEnabled(),
        )
        worker.step.connect(self._note_step)
        worker.done.connect(self._finished)
        worker.failed.connect(self._refused)
        # **Und das Unerwartete.** Ohne diese Zeile stand der Dialog nach einem
        # ``PermissionError`` — ComfyUI unter ``Program Files`` — für immer auf
        # „Wird eingerichtet …", mit laufendem Balken.
        worker.crashed.connect(self._crashed)
        worker.finished.connect(lambda done=worker: self._worker_done(done))
        self._worker = worker
        self._leash.start(worker)

    def wait_for_setup(self, milliseconds: int = 30_000) -> bool:
        """Auf den Lauf warten. Beim Schließen und in Tests."""
        worker = self._worker
        return worker.wait(milliseconds) if worker is not None else True

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieses Fenster außerhalb von Qt hält.

        Warum der Name, warum die eigene Frist: :mod:`app.ui.leash`.
        """
        self.wait_for_setup()
        self._leash.wait_all(timeout_ms)

    def _note_step(self, step: str) -> None:
        """Welcher Schritt gerade läuft. Vier bis fünf, und einer dauert lange.

        Die Zeit beginnt je Schritt neu: „Gewichte laden — rund 7,5 GB (240 s)"
        sagt mehr als eine Gesamtzeit, denn nur dieser eine Schritt dauert.
        """
        self._step = step
        self._started_at = time.monotonic()
        self._show_elapsed()

    def _show_elapsed(self) -> None:
        """Der Schritt und wie lange er schon läuft.

        Die Rolle steht **hier** und nicht beim Start: Der Zeitgeber schreibt
        die Zeile jede Sekunde neu, und ein einmal gesetztes Zeichen wäre beim
        ersten Takt wieder weg. Wer einen Text laufend erneuert, erneuert seine
        Bedeutung mit.
        """
        seconds = time.monotonic() - self._started_at
        set_role(self.state, "info", f"{self._step} ({seconds:.0f} s)")

    def _finished(self, result: object) -> None:
        assert isinstance(result, comfy_setup.Result)
        self._idle()
        if not result.done:
            set_role(self.state, "warning", str(result.reason))
            return
        # Der Neustart ist kein Detail: ComfyUI liest seine Knoten beim Start,
        # und ohne ihn bleibt die Mesh-Erzeugung ausgegraut, obwohl alles liegt.
        set_role(
            self.state,
            "ok",
            tr("Eingerichtet. ComfyUI einmal neu starten, dann geht „Modell erzeugen“."),
        )
        _log.info("comfyui set up in %s", result.comfyui)

    def _refused(self, reason: str) -> None:
        self._idle()
        set_role(self.state, "warning", reason)

    def _crashed(self, detail: str) -> None:
        """Womit niemand gerechnet hat — und der Weg aus dem Wartezustand."""
        self._idle()
        _log.warning("comfy setup crashed: %s", detail)
        error = InternalError(detail=detail)
        set_role(self.state, "warning", f"{error.title!s} {detail}")
        show_error(error, self)

    def _idle(self) -> None:
        self._tick.stop()
        self.progress.setVisible(False)
        self.start_button.setText(tr("Einrichten"))
        self.choose.setEnabled(True)

    def _worker_done(self, worker: object) -> None:
        if self._worker is worker:
            self._worker = None
        self._leash.hold_until_done(worker)

    def reject(self) -> None:
        """Schließen bricht den Lauf ab — und wartet nicht auf ihn.

        Abgebrochen wird zwischen den Schritten und im Download je Block: ein
        halb kopierter Knotenordner wäre schlimmer als ein Vorgang, der
        ausläuft. Hier stand danach ``wait(2000)``, zwei Sekunden stehendes
        Fenster auf Esc hin, ohne Balken und ohne Zeile. Den Thread hält die
        Halteleine über den Dialog hinaus (:mod:`app.ui.leash`); seine
        Signale werden getrennt, damit eine späte Antwort keinen
        geschlossenen Dialog mehr anfasst.
        """
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            for signal in (worker.step, worker.done, worker.failed, worker.crashed):
                with suppress(RuntimeError, TypeError):
                    signal.disconnect()
            self._idle()
        super().reject()
