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
from app.core.log import get_logger
from app.i18n import tr
from app.ui.labels import UNEXPECTED_CRASH
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.style import set_level

_log = get_logger(__name__)

#: Wie oft die Laufzeit des laufenden Schritts nachgezogen wird. Einer davon
#: lädt 7,5 GB — ohne die Zeit daneben ist ein unbestimmter Balken von einem
#: Hänger nicht zu unterscheiden.
TICK_MS = 1000


class _Worker(Worker):
    """Die Einrichtung: git, pip, und ein Download von 7,5 GB."""

    done = Signal(object)
    failed = Signal(str)
    step = Signal(str)

    def __init__(self, comfyui: str, weights: bool) -> None:
        super().__init__()
        self._comfyui = comfyui
        self._weights = weights
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    def work(self) -> None:
        try:
            result = comfy_setup.setup(
                self._comfyui or None,
                weights=self._weights,
                progress=lambda entry: self.step.emit(str(entry)),
                cancelled=lambda: self._stop,
            )
        except comfy_setup.SetupFailed as problem:
            self.failed.emit(str(problem))
            return
        self.done.emit(result)


class ComfySetupDialog(QDialog):
    """Knoten, Quelltext, Pakete und Gewichte — in einem Lauf."""

    def __init__(self, parent: QWidget | None = None) -> None:
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

        self.state = QLabel(self)
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)

        self.start_button = QPushButton(tr("Einrichten"), self)
        self.start_button.clicked.connect(self._start)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(self.folder, stretch=1)
        row.addWidget(self.choose)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(row)
        layout.addWidget(self.weights)
        layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.progress)
        layout.addWidget(self.state)
        layout.addWidget(buttons)

        if found is None:
            # **Der Satz nennt das Kennzeichen.** „Nicht gefunden — der Ordner
            # gehört hier hinein" schickt jemanden suchen, ohne zu sagen,
            # wonach: ComfyUI liegt in einem Ordner, in dem „custom_nodes"
            # steht, und das ist die ganze Auskunft, die es braucht.
            self.state.setText(
                tr(
                    "ComfyUI ist an den üblichen Stellen nicht gefunden worden. "
                    "Gesucht wird der Ordner, in dem „custom_nodes“ und „main.py“ "
                    "liegen — bei der tragbaren Version steckt er in "
                    "„ComfyUI_windows_portable“."
                )
            )
            set_level(self.state, "info")

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
        set_level(self.state, "info")

        worker = _Worker(self.folder.text().strip(), self.weights.isChecked())
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

        **Ein Name für den Aufräumbefehl, auf allen Klassen, die Arbeiter
        halten.** Es waren fünf — ``release``, ``wait_for_workers``,
        ``wait_for_survey``, ``wait_for_look``, ``wait_for_setup`` —, und wer
        eine Testfixture darauf baute, sammelte sie nacheinander ein: erst
        zwei, dann drei, dann vier. Der fünfte fehlte, und der Prozess starb
        beim Abbau an einem Thread, der sein Fenster überlebt hatte.

        Der fachliche Name daneben bleibt: ``wait_for_setup`` gibt zurück, **ob** der Lauf
        fertig wurde,
        und wird beim Schließen gefragt. Aufräumen fragt nicht, es wartet.

        **Die Frist der fachlichen Methode bleibt ihre eigene.** Hier stand
        zuerst ``wait_for_setup(timeout_ms)`` — und damit bekam eine Erhebung, für die
        30 Sekunden vorgesehen sind, die 2 Sekunden, die für das Einsammeln
        der Leine gedacht sind. Gemessen an ``test_chat_ui``: zwei von vier
        Läufen starben danach beim Abbau, gegen null von vier davor. Der
        Parameter gilt der Leine, nicht der Sache.
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
        """Der Schritt und wie lange er schon läuft."""
        seconds = time.monotonic() - self._started_at
        self.state.setText(f"{self._step} ({seconds:.0f} s)")

    def _finished(self, result: object) -> None:
        assert isinstance(result, comfy_setup.Result)
        self._idle()
        if not result.done:
            self.state.setText(str(result.reason))
            set_level(self.state, "warning")
            return
        # Der Neustart ist kein Detail: ComfyUI liest seine Knoten beim Start,
        # und ohne ihn bleibt die Mesh-Erzeugung ausgegraut, obwohl alles liegt.
        self.state.setText(
            tr("Eingerichtet. ComfyUI einmal neu starten, dann geht „Modell erzeugen“.")
        )
        set_level(self.state, "ok")
        _log.info("comfyui set up in %s", result.comfyui)

    def _refused(self, reason: str) -> None:
        self._idle()
        self.state.setText(reason)
        set_level(self.state, "warning")

    def _crashed(self, detail: str) -> None:
        """Womit niemand gerechnet hat — und der Weg aus dem Wartezustand."""
        self._idle()
        _log.warning("comfy setup crashed: %s", detail)
        self.state.setText(f"{UNEXPECTED_CRASH!s} {detail}")
        set_level(self.state, "warning")

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
        worker = self._worker
        if worker is not None and worker.isRunning():
            # Abgebrochen wird zwischen den Schritten: ein halb kopierter
            # Knotenordner wäre schlimmer als ein Vorgang, der ausläuft.
            worker.cancel()
            worker.wait(2000)
        super().reject()
