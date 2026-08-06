"""Weg 3 aus dem Fenster: beschreiben oder ein Bild fallen lassen, einen
Körper bekommen (§2.2, §27).

Der Dialog ist mit Absicht dünn. Alles, was er tut, lebt in
:mod:`app.core.generate`; was hier passiert, ist nach einem Satz zu fragen, zu
zeigen, ob überhaupt ein Generator läuft, und das Fenster bedienbar zu halten,
während eine Grafikkarte eine Minute lang nachdenkt.

Läuft nichts, sagt der Dialog das und bietet keinen Knopf zum Drücken —
ausgegraut, wie der Chat ohne Schlüssel (§27). Er versucht nicht, etwas zu
starten, und er versteckt den Eintrag auch nicht: eine Aktion, die verschwindet,
sieht aus wie ein Fehler; eine, die sich erklärt, nicht.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.backends.mesh import ComfyBackend, GeneratedMesh, MeshBackend
from app.core.errors import AppError
from app.core.log import get_logger
from app.i18n import tr
from app.ui.panels import collapsible

_log = get_logger(__name__)

#: Was sich als Ausgangsbild hineinziehen lässt. Die Endungen stehen für sich,
#: getrennt von der Beschriftung: der Dateidialog zeigt einen übersetzten Text,
#: das Erkennen einer abgelegten Datei darf davon nicht abhängen.
IMAGE_SUFFIXES: Final = (".png", ".jpg", ".jpeg", ".webp")


def image_filter() -> str:
    """Der Filter für den Dateidialog, in der Sprache des Nutzers (Regel 20).

    Als Funktion und nicht als Konstante: ``tr()`` löst sofort auf, und eine
    Konstante auf Modulebene stünde in der Sprache, die beim Import galt.
    """
    return f"{tr('Bilder')} ({' '.join('*' + suffix for suffix in IMAGE_SUFFIXES)})"


#: Obergrenze des Startwerts, den der Dialog anbietet. Derselbe Wert liefert
#: dasselbe Ergebnis, soweit das Modell auf der anderen Seite es zulässt
#: (§11.3).
MAX_SEED = 2**31 - 1

#: Wie lange das Schließen auf den Arbeiter wartet, bevor es loslässt.
WAIT_MILLISECONDS = 50


class _Worker(QThread):
    """Eine Erzeugung, abseits des Oberflächen-Threads.

    Ein Diffusionsmodell braucht Minuten; das in der Ereignisschleife zu tun
    fröre das Fenster ein — samt jeder Fortschrittszeile, die es zeigen
    soll (§31).
    """

    done = Signal(object)
    failed = Signal(object)
    step = Signal(float, str)

    def __init__(self, backend: MeshBackend, prompt: str, image: bytes | None, seed: int) -> None:
        super().__init__()
        self._backend = backend
        self._prompt = prompt
        self._image = image
        self._seed = seed

    def run(self) -> None:
        try:
            if self._image is not None:
                result = self._backend.image_to_mesh(
                    self._image, seed=self._seed, progress=self._progress
                )
            else:
                result = self._backend.text_to_mesh(
                    self._prompt, seed=self._seed, progress=self._progress
                )
        except AppError as problem:
            self.failed.emit(problem)
            return
        self.done.emit(result)

    def _progress(self, fraction: float, text: str) -> None:
        self.step.emit(fraction, text)


class GenerateDialog(QDialog):
    """Fragt nach einer Beschreibung oder einem Bild und gibt einen erzeugten
    Körper zurück.
    """

    def __init__(self, backend: MeshBackend | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.backend: MeshBackend = backend or ComfyBackend()
        self.result_mesh: GeneratedMesh | None = None
        self._image: bytes | None = None
        self._worker: _Worker | None = None
        self.tries: list[GeneratedMesh] = []
        """Was bisher entstanden ist (Konzept P15, E8).

        Meshy rät, mehrere Varianten zu erzeugen und die sauberste zu nehmen —
        die Generierung enthält Zufall, und der erste Wurf ist selten der
        beste. Vier davon **gleichzeitig** zu starten ist dort richtig, wo ein
        Rechenzentrum wartet; hier läuft ComfyUI auf derselben Grafikkarte, an
        der jemand sitzt, und vier parallele Läufe wären vierfache Wartezeit
        für drei Ergebnisse, die niemand bestellt hat.

        Also nacheinander: der erste kommt nach der gewohnten Zeit, und wer
        will, lässt einen weiteren folgen."""

        self.setWindowTitle(tr("Modell erzeugen"))
        self.setMinimumWidth(480)

        self.prompt = QLineEdit(self)
        self.prompt.setPlaceholderText(tr("Was soll entstehen?"))

        self.seed = QSpinBox(self)
        self.seed.setRange(0, MAX_SEED)
        self.seed.setToolTip(
            tr("Derselbe Startwert liefert dasselbe Modell, solange das Modell dasselbe bleibt.")
        )

        self.picture = QPushButton(tr("Bild wählen …"), self)
        self.picture.clicked.connect(self._choose_image)
        self.picture_label = QLabel(tr("Kein Bild gewählt"), self)

        form = QFormLayout()
        form.addRow(tr("Beschreibung"), self.prompt)
        form.addRow(tr("Bild"), self.picture)
        form.addRow("", self.picture_label)

        # §2.4: vorn die zwei Werte, die man ändert; hinten alles andere. Der
        # Startwert stand an dritter Stelle über allem, was jemand hier tun
        # will — er entscheidet nichts, solange man ihn nicht wiederholen
        # will, und genau dafür ist er da.
        advanced = QWidget(self)
        advanced_form = QFormLayout(advanced)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.addRow(tr("Startwert"), self.seed)
        self.advanced = collapsible(tr("Weitere Einstellungen"), advanced, open_now=False)

        self.state = QLabel(self)
        self.state.setWordWrap(True)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Erzeugen"))
        self.buttons.accepted.connect(self._accept_or_start)
        self.buttons.rejected.connect(self.reject)

        # Die Versuche und der Weg zu einem weiteren — beide unsichtbar, bis
        # der erste da ist: ein leeres Feld über einem leeren Knopf sagt
        # nichts (§2.5).
        self.attempts = QListWidget(self)
        self.attempts.setVisible(False)
        self.attempts.setMaximumHeight(120)
        self.again = QPushButton(tr("Noch ein Versuch"), self)
        self.again.setVisible(False)
        self.again.clicked.connect(self._try_again)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.advanced)
        # Der Platz sammelt sich hier, nicht zwischen den Feldern: sonst
        # stand der Hinweis, warum „Erzeugen“ gesperrt ist, dreihundert Pixel
        # von dem Knopf entfernt, den er erklärt.
        layout.addStretch(1)
        layout.addWidget(self.state)
        layout.addWidget(self.attempts)
        layout.addWidget(self.again)
        layout.addWidget(self.progress)
        layout.addWidget(self.buttons)

        self.prompt.textChanged.connect(self._update_state)
        self._update_state()

    # --- state ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return bool(self.backend.available)

    def _update_state(self) -> None:
        if not self.available:
            self.state.setText(
                tr(
                    "Es läuft kein Generator. Formwerk spricht lokal mit ComfyUI — "
                    "ohne das bleibt dieser Weg zu, alles andere funktioniert weiter."
                )
            )
        else:
            self.state.setText(tr("Bereit. Das kann einige Minuten dauern."))
        ready = self.available and bool(self.prompt.text().strip() or self._image)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ready)

    def _choose_image(self) -> None:
        name, _filter = QFileDialog.getOpenFileName(self, tr("Bild wählen"), "", image_filter())
        if not name:
            return
        self.set_image(Path(name))

    def set_image(self, path: Path) -> None:
        """Ein Bild vorbelegen, ohne den Dateidialog.

        Der Weg für ein Bild, das jemand ins Chatfenster gezogen hat: es ist
        schon gewählt, also wäre ein Dialog, der noch einmal danach fragt, ein
        Schritt zu viel (Konzept P15, E8).
        """
        self._image = path.read_bytes()
        self.picture_label.setText(path.name)
        self._update_state()

    # --- running ----------------------------------------------------------------

    def _accept_or_start(self) -> None:
        """Derselbe Knopf: erst erzeugen, danach übernehmen.

        Zwei Knöpfe nebeneinander, von denen immer einer tot ist, wären eine
        Frage mehr als nötig — und welcher gilt, sagt der Zustand, nicht der
        Benutzer.
        """
        if self.tries:
            self.result_mesh = self.chosen()
            self.accept()
            return
        self._start()

    def _start(self) -> None:
        if not self.available:
            return
        self.buttons.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        worker = _Worker(self.backend, self.prompt.text().strip(), self._image, self.seed.value())
        worker.done.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.step.connect(self._on_step)
        worker.finished.connect(self._on_thread_done)
        self._worker = worker
        worker.start()

    def _on_step(self, fraction: float, text: str) -> None:
        self.progress.setValue(int(max(0.0, min(1.0, fraction)) * 100))
        if text:
            self.state.setText(text)

    def _on_done(self, result: object) -> None:
        assert isinstance(result, GeneratedMesh)
        self.tries.append(result)
        self.result_mesh = result
        _log.info("generated %d triangles", result.mesh.triangle_count)
        self.progress.setVisible(False)
        self.buttons.setEnabled(True)
        self._show_tries()

    def _show_tries(self) -> None:
        """Die Versuche mit den Zahlen, an denen man sie unterscheidet.

        Dreiecke, Volumen und ob der Körper geschlossen ist — dieselben drei,
        die auch der Steckbrief nennt. Sie entscheiden, welcher Wurf brauchbar
        ist, und ein Bild daneben entschiede es nicht besser: ein offenes Netz
        sieht aus wie ein geschlossenes.
        """
        self.attempts.clear()
        for index, entry in enumerate(self.tries, start=1):
            mesh = entry.mesh
            closed = tr("geschlossen") if mesh.is_watertight else tr("offen")
            item = QListWidgetItem(
                f"{index}. {mesh.triangle_count} {tr('Dreiecke')} · "
                f"{mesh.volume / 1000.0:.1f} cm³ · {closed}"
            )
            self.attempts.addItem(item)
        self.attempts.setCurrentRow(len(self.tries) - 1)
        self.attempts.setVisible(True)
        self.again.setVisible(True)
        self.state.setText(
            tr("Der Zufall spielt mit — ein weiterer Versuch kostet nichts als Zeit.")
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Übernehmen"))

    def _try_again(self) -> None:
        """Noch einen Wurf, mit dem nächsten Startwert.

        Der Startwert wird hochgezählt und nicht gewürfelt: derselbe Dialog
        zweimal geöffnet soll dieselbe Reihe liefern (Regel 9).
        """
        self.seed.setValue(min(self.seed.value() + 1, MAX_SEED))
        self._start()

    def chosen(self) -> GeneratedMesh | None:
        """Der ausgewählte Versuch — der zuletzt erzeugte, wenn keiner
        angeklickt wurde."""
        row = self.attempts.currentRow()
        if 0 <= row < len(self.tries):
            return self.tries[row]
        return self.result_mesh

    def _on_failed(self, problem: object) -> None:
        self.progress.setVisible(False)
        self.buttons.setEnabled(True)
        text = str(problem.title) if isinstance(problem, AppError) else str(problem)
        self.state.setText(text)

    def _on_thread_done(self) -> None:
        self._worker = None

    def reject(self) -> None:
        """Abbrechen wartet auf den Thread, statt ihn laufen zu lassen.

        Die Anfrage selbst läuft auf der anderen Seite weiter — die
        Schnittstelle aus §27 hat keinen Aufruf, sie zurückzunehmen, und einen
        zu erfinden, der lügt, wäre schlechter, als nichts zu sagen.
        """
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(WAIT_MILLISECONDS)
        super().reject()
