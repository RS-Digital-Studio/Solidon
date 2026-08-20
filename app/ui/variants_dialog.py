"""Der Variantengenerator, mit einem Weg hinein (Bauplan §28.3, §25).

Derselbe Stapel, ein paar Mal mit einer gestuften Zahl gerechnet, nebeneinander
auf einer Platte angeordnet: so wird eine Toleranz gemessen statt geraten —
die Reihe drucken, die nehmen, die passt, ihren Wert von der Beschriftung
ablesen.

Die Varianten sind mit Absicht **keine** Szenenobjekte. Die Szene ist, was der
Stapel erzeugt (§15.1), und vier Kopien davon sind keine vier Objekte — sie
sind ein Druckauftrag. Also werden sie gebaut, als Anzahl gezeigt und
herausgeschrieben; das Projekt bleibt, wie es war.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError
from app.core.export.writer import plan_export, write_plan
from app.core.log import get_logger
from app.core.scene import build_variants
from app.core.scene.cancel import CancelSignal
from app.core.scene.project import ProjectSources
from app.core.scene.variants import MAX_VARIANTS
from app.i18n import tr
from app.ui.dialogs import show_error
from app.ui.session import Session

_log = get_logger(__name__)


class _VariantWorker(QThread):
    """Die Varianten rechnen, abseits des Oberflächen-Threads (§2.8).

    Gerechnet wurde in der Ereignisschleife: bis zu zwölf vollständige
    Auswertungen desselben Stapels, hintereinander, mit stehendem Fenster und
    ohne ein Zeichen dafür, dass überhaupt etwas läuft. §2.8 verlangt über zwei
    Sekunden einen Fortschritt **mit Abbrechen** und eine Oberfläche, die
    bedienbar bleibt.

    **Mit Abbrechen, anders als beim Export.** Dort gibt es keinen sauberen
    Haltepunkt, weil eine halb geschriebene Datei entstünde; hier ist der
    Haltepunkt die Grenze zwischen zwei Auswertungen, und die Auswertung selbst
    fragt das Token ohnehin ab (§15.6). Was fertig war, kommt zurück — geprüft
    wird danach, ob der Satz vollständig ist.
    """

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, cancel: CancelSignal, **arguments: Any) -> None:
        super().__init__()
        self._cancel = cancel
        self._arguments = arguments

    def run(self) -> None:
        try:
            made = build_variants(**self._arguments, cancelled=self._cancel)
        except AppError as error:
            self.failed.emit(error)
            return
        self.done.emit(made)


class VariantsDialog(QDialog):
    """Einen Parameter und eine Schrittweite wählen, eine Platte voller
    Varianten bekommen.
    """

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle(tr("Varianten erzeugen"))
        self.setMinimumWidth(460)

        document = session.project.document
        self.parameter = QComboBox(self)
        for name, entry in sorted(document.parameters.items()):
            self.parameter.addItem(f"{entry.title or name} ({name})", name)

        self.first = QDoubleSpinBox(self)
        self.first.setRange(-1000.0, 1000.0)
        self.first.setDecimals(3)
        self.step = QDoubleSpinBox(self)
        self.step.setRange(-100.0, 100.0)
        self.step.setDecimals(3)
        self.step.setValue(0.05)
        self.count = QSpinBox(self)
        self.count.setRange(2, MAX_VARIANTS)
        self.count.setValue(4)

        chosen = self.parameter.currentData()
        if chosen is not None:
            self.first.setValue(float(document.parameters[chosen].value))

        form = QFormLayout()
        form.addRow(tr("Parameter"), self.parameter)
        form.addRow(tr("Erster Wert"), self.first)
        form.addRow(tr("Schrittweite"), self.step)
        form.addRow(tr("Anzahl"), self.count)

        self.state = QLabel(
            tr("Die Varianten stehen nebeneinander auf einer Platte und werden exportiert."),
            self,
        )
        self.state.setWordWrap(True)

        # §2.8: über zwei Sekunden ein Fortschritt — und er ist erst da, wenn er
        # gebraucht wird. Ein Balken, der von Anfang an auf null steht, sagt
        # nichts und nimmt Platz.
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Erzeugen"))
        self.buttons.accepted.connect(self._build)
        self.buttons.rejected.connect(self._stop_or_close)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.state)
        layout.addWidget(self.progress)
        layout.addWidget(self.buttons)

        self._worker: _VariantWorker | None = None
        self._cancel = CancelSignal()
        self._target: Path | None = None

        if not document.parameters:
            self.state.setText(
                tr("Dieses Projekt hat keine Parameter — ohne einen gibt es nichts zu variieren.")
            )
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _build(self) -> None:
        """Rechnen lassen und dabei zusehen können.

        **Der Ordner wird vorher gefragt.** Er wurde danach gefragt, und damit
        war jede abgebrochene Ordnerwahl bis zu zwölf weggeworfene Auswertungen
        — ein Dialog, der erst eine Minute rechnet und dann fragt, wohin,
        bestraft die Antwort „doch nicht".
        """
        name = self.parameter.currentData()
        if name is None or self._worker is not None:
            return

        directory = QFileDialog.getExistingDirectory(self, tr("Varianten exportieren"))
        if not directory:
            return
        self._target = Path(directory)

        project = self.session.project
        self._cancel.reset()
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.state.setText(tr("Die Varianten werden gerechnet …"))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

        worker = _VariantWorker(
            self._cancel,
            document=project.document,
            profile=self.session.profile,
            parameter=str(name),
            first=self.first.value(),
            step=self.step.value(),
            count=self.count.value(),
            sources=ProjectSources(project),
            progress=self._advance,
        )
        worker.done.connect(self._finished)
        worker.failed.connect(self._broke)
        # Der Arbeiter hängt an dieser Referenz und an keinem Qt-Elternteil:
        # fällt sie weg, während er läuft, zerstört der Speicherbereiniger das
        # C++-Objekt unter ihm. Losgelassen wird er in ``_release``.
        self._worker = worker
        worker.start()

    def _advance(self, share: float, text: str) -> None:
        """Fortschritt, gemeldet aus dem Arbeits-Thread.

        Gesetzt wird über ein Signal des Arbeiters und nicht von seinem Thread
        aus: ein Widget aus einem fremden Thread anzufassen ist der Absturz, der
        erst in der zehnten Wiederholung auffällt.
        """
        self.progress.setValue(int(max(0.0, min(1.0, share)) * 100))
        if text:
            self.state.setText(text)

    def _stop_or_close(self) -> None:
        """Ein Knopf, zwei Bedeutungen — je nachdem, ob etwas läuft.

        Läuft eine Rechnung, hält er sie an; läuft keine, schließt er den
        Dialog. Andersherum wäre er während der Rechnung eine Sackgasse: der
        Dialog ginge zu, und der Thread rechnete weiter.
        """
        if self._worker is None:
            self.reject()
            return
        self._cancel.cancel()
        self.state.setText(tr("Wird abgebrochen …"))

    def _broke(self, error: object) -> None:
        self._release()
        if isinstance(error, AppError):
            show_error(error, self)

    def _finished(self, made: Any) -> None:
        """Was fertig gerechnet wurde, wird geschrieben."""
        self._release()
        if self._cancel.is_cancelled:
            self.state.setText(tr("Abgebrochen — es wurde nichts geschrieben."))
            return
        if not made.complete:
            # §28.3: ein Satz mit einer Lücke darin ist kein Kalibrierdruck.
            self.state.setText(tr("Nicht jede Variante ließ sich rechnen — siehe Prüfbericht."))

        objects = list(made.scene(self.session.profile).objects.values())
        if not objects:
            self.state.setText(tr("Es ist keine Variante übrig geblieben."))
            return
        if self._target is None:
            return

        name = self.parameter.currentData()
        title = self.session.path.stem if self.session.path else tr("Varianten")
        plan = plan_export(objects, project_name=f"{title}_{name}", profile=self.session.profile)
        written = write_plan(plan, self._target)
        _log.info("wrote %d variant file(s)", len(written))
        self.state.setText(f"{len(written)} {tr('Dateien geschrieben')}")
        self.accept()

    def _release(self) -> None:
        """Den Arbeiter loslassen, aber erst, wenn er wirklich fertig ist.

        ``finished`` kommt, während Qt den Thread noch abräumt; ihn dort schon
        freizugeben ist die Zugriffsverletzung ohne Zeile. Gewartet wird
        deshalb — und weil dieser Dialog modal ist und genau einen Arbeiter
        führt, genügt das hier. Die Halteleine des Hauptfensters
        (``_hold_until_done``) braucht es für mehrere gleichzeitig.
        """
        worker = self._worker
        self._worker = None
        self.progress.setVisible(False)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)
        if worker is not None:
            worker.wait()

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Ein laufender Arbeiter überlebt seinen Dialog nicht.

        Ohne das rechnet der Thread weiter, sendet sein Signal in ein
        zerstörtes C++-Objekt und nimmt den Prozess mit.
        """
        if self._worker is not None:
            self._cancel.cancel()
            self._release()
        super().closeEvent(event)
