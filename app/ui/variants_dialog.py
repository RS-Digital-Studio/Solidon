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

from contextlib import suppress
from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError, InternalError
from app.core.export.writer import plan_export, write_plan
from app.core.log import get_logger
from app.core.scene import build_variants
from app.core.scene.cancel import CancelSignal
from app.core.scene.project import ProjectSources
from app.core.scene.variants import MAX_VARIANTS
from app.core.types import Finding
from app.i18n import tr
from app.ui.dialogs import show_error
from app.ui.labels import NumberSpin, localised_value
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.session import Session
from app.ui.style import NORMAL, WIDE, make_primary

_log = get_logger(__name__)


class _VariantWorker(Worker):
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

    done = Signal(object, object)
    """Der Variantensatz und die geschriebenen Dateien — leer, wenn nichts
    geschrieben wurde (abgebrochen, lückenhaft oder ohne Körper)."""
    failed = Signal(object)
    progressed = Signal(float, str)
    """Der Fortschritt, **als Signal**: ``build_variants`` ruft seinen Rückruf
    synchron aus dem Arbeits-Thread, und der Rückruf war die gebundene
    Widgetmethode — ``QProgressBar`` und ``QLabel`` wurden aus einem fremden
    Thread gesetzt, gemessen an den Thread-Kennungen (Gesamtreview 05.09.2026,
    UI-14). Ein Signal stellt die Meldung über die Ereignisschleife zu."""

    def __init__(
        self, cancel: CancelSignal, target: Path, project_name: str, **arguments: Any
    ) -> None:
        super().__init__()
        self._cancel = cancel
        self._target = target
        self._project_name = project_name
        self._arguments = arguments

    def _report(self, share: float, text: str) -> None:
        self.progressed.emit(share, text)

    def work(self) -> None:
        """Rechnen **und** schreiben — beides abseits des Oberflächen-Threads.

        Geschrieben wurde im Slot danach, also im Oberflächen-Thread, und ein
        Schreibfehler lief dort ohne Satz aus dem Slot heraus (Regel 17). Ein
        Abbruch vor dem Schreiben schreibt nichts: gefragt wird das Token
        unmittelbar davor.
        """
        try:
            made = build_variants(**self._arguments, progress=self._report, cancelled=self._cancel)
            written: list[Path] = []
            if made.complete and not self._cancel.is_cancelled:
                profile = self._arguments["profile"]
                objects = list(made.scene(profile).objects.values())
                if objects:
                    plan = plan_export(objects, project_name=self._project_name, profile=profile)
                    written = write_plan(plan, self._target)
        except AppError as error:
            self.failed.emit(error)
            return
        self.done.emit(made, written)


class VariantsDialog(QDialog):
    """Einen Parameter und eine Schrittweite wählen, eine Platte voller
    Varianten bekommen.
    """

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self._leash = WorkerLeash(self)
        self.setWindowTitle(tr("Varianten erzeugen"))
        self.setMinimumWidth(460)

        document = session.project.document
        self.parameter = QComboBox(self)
        for name, entry in sorted(document.parameters.items()):
            self.parameter.addItem(f"{entry.title or name} ({name})", name)

        self.first = NumberSpin(self)
        self.first.setRange(-1000.0, 1000.0)
        self.first.setDecimals(3)
        self.step = NumberSpin(self)
        self.step.setRange(-100.0, 100.0)
        self.step.setDecimals(3)
        self.step.setValue(0.05)
        self.count = QSpinBox(self)
        self.count.setRange(2, MAX_VARIANTS)
        self.count.setValue(4)

        # **Der erste Wert folgt dem Parameter.** Er wurde nur beim Aufbau
        # gesetzt; wer danach einen anderen Parameter wählte, bekam eine Reihe
        # ab dem Wert des ersten — Varianten eines Maßes, das es so nicht gab.
        self._take_parameter_value()
        self.parameter.currentIndexChanged.connect(self._take_parameter_value)

        # **Die Zahl gehört ins Teil und nicht nur in den Namen.** Vier
        # Varianten derselben Toleranz sehen einander zum Verwechseln ähnlich;
        # die Szene weiß, welche welche ist, und die ist zu, sobald die Teile
        # vom Bett kommen. Der Haken steht an, weil das der Zweck des ganzen
        # Laufs ist — aus schaltet ihn, wem die Oberseite seines Teils heilig
        # ist.
        self.mark = QCheckBox(tr("Wert in die Oberseite gravieren"), self)
        self.mark.setChecked(True)
        marking = tr(
            "Jedes Teil trägt seinen Wert eingelassen auf der Oberseite — nach dem "
            "Druck ist das die einzige Stelle, an der er noch steht. Wo kein Platz "
            "dafür ist, sagt es der Bericht."
        )
        # Drei Kanäle, weil ein Satz, den nur die Maus findet, für einen
        # Bildschirmleser keiner ist (Regel 18).
        self.mark.setToolTip(marking)
        self.mark.setStatusTip(marking)
        self.mark.setAccessibleDescription(marking)

        form = QFormLayout()
        form.addRow(tr("Parameter"), self.parameter)
        form.addRow(tr("Erster Wert"), self.first)
        form.addRow(tr("Schrittweite"), self.step)
        form.addRow(tr("Anzahl"), self.count)
        form.addRow("", self.mark)
        for field in (self.parameter, self.first, self.step, self.count):
            caption = form.labelForField(field)
            if isinstance(caption, QLabel):
                caption.setBuddy(field)
                field.setAccessibleName(caption.text())

        self.state = QLabel(
            tr("Die Varianten stehen nebeneinander auf einer Platte und werden exportiert."),
            self,
        )
        self.state.setWordWrap(True)

        # §2.8: über zwei Sekunden ein Fortschritt — und er ist erst da, wenn er
        # gebraucht wird. Ein Balken, der von Anfang an auf null steht, sagt
        # nichts und nimmt Platz.
        self.progress = QProgressBar(self)
        # Die Zahl steht nicht auf der Füllung: Bei 45 Prozent liegt sie halb
        # auf Bernstein und halb auf der Spur, ab 60 ganz auf Bernstein — mit
        # 1,69 Kontrast. Dieselbe Begründung wie an den drei Balken daneben, und
        # ``tests/test_style.py`` hält sie an allen vier.
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Erzeugen"))
        make_primary(self.buttons.button(QDialogButtonBox.StandardButton.Ok))
        self.buttons.accepted.connect(self._build)
        self.buttons.rejected.connect(self._stop_or_close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        layout.addLayout(form)
        layout.addWidget(self.state)
        layout.addWidget(self.progress)
        layout.addStretch(1)
        layout.addWidget(self.buttons)

        self._worker: _VariantWorker | None = None
        self._cancel = CancelSignal()
        self._target: Path | None = None
        self.written: list[Path] = []
        """Was der Lauf geschrieben hat — das Fenster nennt es nach dem Schließen."""
        self.findings: list[Finding] = []
        """Was der Lauf zu sagen hat: eine Gravur ohne Platz, eine Variante ohne
        Ergebnis. „Wo kein Platz dafür ist, sagt es der Bericht" verspricht der
        Haken — der Bericht bekam es nie."""

        if not document.parameters:
            # Der Satz steht in der Zustandszeile **und** am Knopf: Wer auf einen
            # grauen Knopf zeigt, fragt ihn und nicht die Zeile darüber. Dieselbe
            # Zusage wie im Druckdialog (`test_dialog_buttons.py`), und derselbe
            # Satz — zwei Formulierungen über dieselbe Lage laufen auseinander.
            why = tr("Dieses Projekt hat keine Parameter — ohne einen gibt es nichts zu variieren.")
            self.state.setText(why)
            self._lock_build(why)
            # Und die Felder gehen, solange nichts zu variieren ist: Ein leeres
            # Auswahlfeld mit Startwert, Schrittweite und Anzahl darunter stand
            # bedienbar da und bewirkte nichts.
            hidden: tuple[QWidget, ...] = (
                self.parameter,
                self.first,
                self.step,
                self.count,
                self.mark,
            )
            for row in hidden:
                form.setRowVisible(row, False)

    def _take_parameter_value(self, *_index: object) -> None:
        """Den Startwert auf den heutigen Wert des gewählten Parameters setzen."""
        chosen = self.parameter.currentData()
        parameters = self.session.project.document.parameters
        if chosen is not None and chosen in parameters:
            self.first.setValue(float(parameters[chosen].value))

    def _lock_build(self, why: str) -> None:
        """Den Erzeugen-Knopf sperren und sagen, warum — oder ihn freigeben.

        Ein leerer Grund gibt frei. Alle drei Kanäle, weil ein Grund, den nur
        die Maus findet, für einen Bildschirmleser keiner ist (Regel 18).
        """
        button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        button.setEnabled(not why)
        button.setToolTip(why)
        button.setStatusTip(why)
        button.setAccessibleDescription(why)

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
        title = self.session.path.stem if self.session.path else tr("Varianten")
        self._cancel.reset()
        self.progress.setValue(0)
        self.progress.setVisible(True)
        running = tr("Die Varianten werden gerechnet …")
        self.state.setText(running)
        self._lock_build(running)

        worker = _VariantWorker(
            self._cancel,
            self._target,
            f"{title}_{name}",
            document=project.document,
            profile=self.session.profile,
            parameter=str(name),
            first=self.first.value(),
            step=self.step.value(),
            count=self.count.value(),
            mark=self.mark.isChecked(),
            sources=ProjectSources(project),
        )
        worker.progressed.connect(self._advance)
        worker.done.connect(self._finished)
        worker.failed.connect(self._broke)
        worker.crashed.connect(self._crashed)
        # Das Feld ist danach die Antwort auf „läuft gerade einer" und nicht
        # mehr die einzige Referenz: Gehalten wird über die Leine, ab dem
        # Start. Fiele das Feld weg, während der Arbeiter läuft — ein Test
        # lässt den Dialog fallen —, zerstörte der Speicherbereiniger sonst
        # das C++-Objekt unter einem laufenden Thread. Losgelassen wird er
        # weiterhin in ``_release``.
        self._worker = worker
        self._leash.start(worker)

    def _advance(self, share: float, text: str) -> None:
        """Fortschritt, angekommen im Oberflächen-Thread.

        Zugestellt über ``_VariantWorker.progressed`` und nicht von seinem
        Thread aus: ein Widget aus einem fremden Thread anzufassen ist der
        Absturz, der erst in der zehnten Wiederholung auffällt — und genau so
        stand es hier, mit einem Kommentar, der das Signal behauptete, das es
        nicht gab (UI-14).
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

    def _crashed(self, detail: str) -> None:
        self._broke(InternalError(detail=detail))

    def _broke(self, error: object) -> None:
        self._release()
        if isinstance(error, AppError):
            # Der Satz steht auch im Dialog: Nach dem Fehlerfenster stand dort
            # weiter „Die Varianten werden gerechnet …".
            self.state.setText(str(error.title))
            show_error(error, self)

    def _finished(self, made: Any, written: Any) -> None:
        """Was gerechnet und geschrieben wurde — und was dabei auffiel."""
        self._release()
        written = list(written or ())
        self.findings = [entry for entry in made.findings if entry.code.startswith("variants.")]
        if self._cancel.is_cancelled and not written:
            self.state.setText(tr("Abgebrochen — es wurde nichts geschrieben."))
            return
        if not made.complete:
            # §28.3: ein Satz mit einer Lücke darin ist kein Kalibrierdruck —
            # und bis zum 05.09.2026 wurde er trotzdem geschrieben: ein Satz
            # Statustext, dann Export und accept(), und nach dem Schließen
            # stand die Lücke nirgends mehr (Gesamtreview, UI-13). Der Dialog
            # bleibt offen und nennt die Werte ohne Ergebnis; der Kunde ändert
            # die Reihe und rechnet neu.
            stopped = [entry for entry in made.findings if entry.code == "variants.stopped"]
            # Zahlen in der Schreibweise der Oberfläche (``localised``): Im
            # deutschen Fenster stand „-0.1" neben „0,2 mm" im Feld darüber.
            values = ", ".join(localised_value(entry.values.get("value", "")) for entry in stopped)
            text = tr("Nicht jede Variante ließ sich rechnen — nichts wurde geschrieben.")
            if values:
                text = f"{text} {tr('Ohne Ergebnis')}: {values}"
            # Regel 17: der Weg nach vorn, und der Cursor steht schon dort.
            text = f"{text}\n" + tr(
                "Wählen Sie einen anderen ersten Wert oder eine kleinere Schrittweite "
                "und erzeugen Sie erneut."
            )
            self.state.setText(text)
            self.first.setFocus()
            return

        if not written:
            self.state.setText(tr("Es ist keine Variante übrig geblieben."))
            return
        _log.info("wrote %d variant file(s)", len(written))
        # Das Fenster sagt nach dem Schließen, wie viele wohin, mit *Ordner
        # zeigen* daneben (``MainWindow.action_variants``). Hier stand
        # „4 Dateien geschrieben" — in einem Dialog, der sich in derselben
        # Zeile schloss, also von niemandem gelesen.
        self.written = written
        self.accept()

    def _release(self) -> None:
        """Den Arbeiter loslassen, aber erst, wenn er wirklich fertig ist.

        ``finished`` kommt, während Qt den Thread noch abräumt; ihn dort schon
        freizugeben ist die Zugriffsverletzung ohne Zeile. Gewartet wird
        deshalb hier, und zwar mit Frist (siehe unten).

        **Die Leine ersetzt das nicht, sie kommt dazu.** Hier stand, sie
        brauche es nur „für mehrere gleichzeitig" — und das war der falsche
        Maßstab: Sie hält einen Arbeiter ab dem *Start*, während dieses Feld
        ihn erst hält, wenn jemand es setzt, und ihn verliert, sobald der
        Dialog weggeräumt wird. Dazu kommt, was erst am 23.08.2026 auffiel:
        Was an der Leine vorbei startet, steht nicht in ``leash._alive`` und
        ist damit für ``leash.wait_for_all`` unsichtbar — die Aufräumhilfe der
        Suite kann einen solchen Arbeiter weder abwarten noch melden.

        **Mit Frist.** Hier stand ``wait()`` ohne Grenze, und aus
        :meth:`closeEvent` heraus war das ein Fenster, das beim Schließen
        einfriert: Der Abbruch greift zwischen zwei Auswertungen, eine einzelne
        aber läuft zu Ende, und solange sie das tut, steht der
        Oberflächen-Thread still — ohne Balken, ohne Abbrechen, ohne Zeile.
        Dieselbe Grenze wie an der Halteleine, und derselbe Umgang damit: nicht
        erzwingen, sondern aufschreiben.
        """
        self._worker = None
        self.progress.setVisible(False)
        self._lock_build("")

    def _let_go(self) -> None:
        """Den laufenden Lauf abbrechen und loslassen, ohne auf ihn zu warten.

        **Das Schließen wartete bis zu zwei Sekunden** (``_release`` mit
        ``wait``): Der Abbruch greift zwischen zwei Auswertungen, und eine
        begonnene läuft zu Ende — so lange stand das Fenster auf Esc hin
        still, ohne Balken und ohne Zeile. Die Halteleine hält den Thread
        über den Dialog hinaus (:mod:`app.ui.leash`); die Signale werden
        getrennt, damit eine späte Antwort keinen geschlossenen Dialog mehr
        bewegt. Geschrieben wird dann auch nichts mehr: Der Arbeiter fragt
        das Token unmittelbar vor dem Schreiben.
        """
        worker = self._worker
        self._cancel.cancel()
        self._release()
        if worker is None:
            return
        for name in ("done", "failed", "progressed", "crashed"):
            signal = getattr(worker, name, None)
            if signal is not None:
                with suppress(RuntimeError, TypeError):
                    signal.disconnect()

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieser Dialog außerhalb von Qt hält.

        ``closeEvent`` bricht denselben Lauf ab — der Weg über das Kreuz.
        Hier steht der Weg über das Wegräumen, den es bisher nicht gab.

        Warum der Name, warum die eigene Frist: :mod:`app.ui.leash`.
        """
        if self._worker is not None:
            self._cancel.cancel()
        self._leash.wait_all(timeout_ms)

    def reject(self) -> None:
        """Escape nimmt denselben Weg wie der Knopf und das Kreuz.

        ``QDialog.reject`` schloss den Dialog, ohne die Rechnung anzuhalten:
        Sie lief weiter, und ``_finished`` schrieb danach die Dateien in den
        gewählten Ordner, während der Dialog längst weg war (Gesamtreview
        05.09.2026, UI-34).
        """
        if self._worker is not None:
            self._let_go()
        super().reject()

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Ein laufender Arbeiter überlebt seinen Dialog nicht.

        Ohne das rechnet der Thread weiter, sendet sein Signal in ein
        zerstörtes C++-Objekt und nimmt den Prozess mit.
        """
        if self._worker is not None:
            self._let_go()
        super().closeEvent(event)
