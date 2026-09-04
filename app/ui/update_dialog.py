"""Der Dialog zur neuen Version (Bauplan §37.2).

Hier stand vorher eine Zeile in der Statusleiste. Sie trug alles, was man
wissen musste — Version und Adresse —, und war trotzdem nutzlos: Die Adresse
war kein Verweis, sondern Text, und die nächste Meldung überschrieb sie. Wer
nicht in dem Moment hinsah, in dem sie erschien, erfuhr nie davon.

Drei Schritte, und jeder ist ein Klick: **sehen**, was neu ist; **holen**,
mit Fortschritt und Abbrechen; **starten**, nachdem die Prüfsumme gestimmt
hat. Nichts davon geschieht von allein — das ist die Grenze aus §37.2, und
sie liegt nicht beim Vorgang, sondern beim Auslöser.

Was dieser Dialog **nicht** tut, ist beenden. Ob das offene Dokument
gespeichert werden muss, weiß das Hauptfenster; es hört auf
:attr:`UpdateDialog.installRequested` und entscheidet dort.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_VERSION, WEBSITE_URL, website_page_url
from app.core import updates
from app.core.errors import AppError, OperationCancelled
from app.core.scene.cancel import CancelSignal
from app.i18n import get_language, tr
from app.ui.changes_dialog import groups_html
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.style import make_primary

#: Wie hoch die Liste der Neuerungen beim Öffnen ist, bevor sie rollt — eine
#: **Anfangshöhe**, kein Deckel: Als ``setMaximumHeight`` am Rollbereich ging
#: jeder gezogene Bildpunkt in Leere statt in die Liste (derselbe Fund wie im
#: Neuerungen-Dialog, Robert 26.08.2026). Den Bildschirmrand schützt die
#: Größe beim Öffnen; was der Nutzer zieht, gehört der Liste.
CHANGES_START_HEIGHT = 240


class _DownloadWorker(Worker):
    """Das Paket holen, abseits des Oberflächen-Threads (§2.8).

    Zweihundert Megabyte über eine Leitung, die niemand kennt: Ein Fenster,
    das währenddessen nicht reagiert, sieht aus wie ein abgestürztes.
    """

    done = Signal(object)
    failed = Signal(object)
    step = Signal(float, str)
    stopped = Signal()

    def __init__(self, package: updates.Package) -> None:
        super().__init__()
        self._package = package
        self.cancelled = CancelSignal()

    def work(self) -> None:
        try:
            file = updates.download(
                self._package,
                progress=self._report,
                cancelled=self.cancelled,
            )
        except OperationCancelled:
            # Kein Fehler und nie als einer gezeigt (§15.6).
            self.stopped.emit()
            return
        except AppError as error:
            self.failed.emit(error)
            return
        self.done.emit(file)

    def _report(self, share: float, text: str) -> None:
        self.step.emit(share, text)


class UpdateDialog(QDialog):
    """Was neu ist, und der Weg dorthin."""

    installRequested = Signal(object)
    """Das geprüfte Paket (``Path``). Wer zuhört, beendet und startet es."""

    def __init__(self, release: updates.Release, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Neue Version"))
        self.setMinimumWidth(520)

        self._release = release
        self._package = release.startable()
        self._file: Path | None = None
        self._worker: _DownloadWorker | None = None
        self._leash = WorkerLeash(self)

        self.headline = QLabel(self)
        self.headline.setWordWrap(True)
        self.headline.setText(
            tr("Solidon {new} ist da — Sie haben {old}.").format(
                new=release.version, old=APP_VERSION
            )
        )

        # **Auch der Hinweis steht in Kundensprache** — er ist die Überschrift
        # über der übersetzten Punkteliste darunter, und die beiden aus zwei
        # Sprachen zu setzen wäre schlechter als gar kein Hinweis.
        note = release.note()
        self.notes = QLabel(note, self)
        self.notes.setWordWrap(True)
        self.notes.setTextFormat(Qt.TextFormat.PlainText)
        self.notes.setVisible(bool(note))

        # **Was neu ist, in Kundensprache** — die Auswahl steht in
        # ``changelog/<sprache>.md`` und kommt über die Versionsdatei hierher.
        # ``PlainText`` ist keine Vorsicht zu viel: Der Text kommt von einem
        # Server, und ein Label, das Auszeichnung liest, lädt auch, was darin
        # als Bild steht.
        self.changes = QLabel(self)
        self.changes.setWordWrap(True)
        # **Ausgezeichnet und nicht mehr flach.** Die Punkte stehen in der
        # Versionsdatei seit dieser Fassung gegliedert; gezeigt werden sie in
        # derselben Bauweise wie unter *Hilfe → Neuerungen*
        # (``changes_dialog.groups_html``), damit dieselbe Auskunft nicht an
        # zwei Stellen verschieden aussieht.
        #
        # Der Rückfall liegt im Kern und nicht hier: ``Release.grouped`` gibt
        # die flache Liste als **eine** Gruppe ohne Titel zurück, wenn eine
        # Versionsdatei keine Gruppen mitbringt. Das Fenster muss deshalb nur
        # einen Weg kennen.
        self.changes.setTextFormat(Qt.TextFormat.RichText)
        self.changes.setAlignment(Qt.AlignmentFlag.AlignTop)
        # **Keine Verweise nach draußen — und hier zählt das mehr als nebenan.**
        # ``changes_dialog`` nennt diese Zurückhaltung sein Vorbild („dieselbe
        # wie beim Update-Fenster"), und sie stand hier nicht: Solange der
        # Kasten Klartext zeigte, konnte ohnehin kein Verweis wirken. Mit der
        # Auszeichnung ändert sich das — und anders als der Verlauf, der aus
        # dem eigenen Paket liest, zeigt dieses Fenster einen Text **vom
        # Server**. ``groups_html`` maskiert jeden Punkt, also entsteht dort
        # kein ``<a>``; der Schalter ist die zweite Linie und kostet nichts.
        self.changes.setOpenExternalLinks(False)
        # Markieren und kopieren wie im Verlauf: Wer eine Neuerung nachschlagen
        # will, nimmt den Satz mit. Zwei Fenster, die dieselbe Auskunft zeigen,
        # sollen sich auch gleich anfassen lassen.
        self.changes.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        points = release.points()
        self.changes.setText(groups_html(release.grouped()))

        # Ein Rollbereich mit Deckel: Acht Punkte passen, zwanzig nicht, und
        # ein Fenster, das über den Bildschirmrand wächst, verliert seine
        # Knöpfe nach unten.
        self.scroller = QScrollArea(self)
        self.scroller.setWidget(self.changes)
        self.scroller.setWidgetResizable(True)
        self.scroller.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroller.setVisible(bool(points))

        # **Der Verweis auf den vollständigen Changelog** — nur, wenn wirklich
        # etwas fehlt. Die Versionsdatei muss unter der Lesegrenze der
        # ausgelieferten Fassungen bleiben und trägt deshalb eine Auswahl;
        # ohne diesen Satz sähe sie aus wie die ganze Liste. In 0.3.0 wäre
        # genau der Punkt weggefallen, der einem Kunden gehörte, der uns den
        # Absturz gemeldet hatte.
        #
        # Anders als die Liste darüber trägt dieses Label **unseren eigenen**
        # Text: Die Adresse baut die Anwendung aus ihrer Sprache, vom Server
        # kommt allein die Zahl, und die geht als Zahl in den Satz. Deshalb
        # darf hier ein Verweis wirken, wo er nebenan abgeschaltet ist.
        self.more = QLabel(self)
        self.more.setWordWrap(True)
        self.more.setTextFormat(Qt.TextFormat.RichText)
        self.more.setOpenExternalLinks(True)
        omitted = release.omitted()
        if omitted:
            self.more.setText(
                tr("Gezeigt sind {shown} von {total} Punkten.").format(
                    shown=len(points), total=release.changes_total
                )
                + ' <a href="'
                + website_page_url("changelog.html", get_language())
                + f'">{tr("Vollständige Liste auf der Website")}</a>'
            )
        self.more.setVisible(bool(omitted))

        self.state = QLabel(self)
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.TextFormat.PlainText)

        # **Kein unbestimmter Balken.** Die Größe steht in der Versionsdatei,
        # also ist der Anteil bekannt — und ein Balken, der bei einer langen
        # Leitung nur hin und her läuft, sagt weniger als „62 von 179 MB".
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)

        self.get_button = QPushButton(self)
        make_primary(self.get_button)
        self.get_button.clicked.connect(self._start)

        self.page_button = QPushButton(tr("Download-Seite öffnen"), self)
        self.page_button.clicked.connect(self.open_page)

        self.buttons = QDialogButtonBox(self)
        self.buttons.addButton(self.get_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.addButton(self.page_button, QDialogButtonBox.ButtonRole.ActionRole)
        self.later_button = self.buttons.addButton(
            tr("Später"), QDialogButtonBox.ButtonRole.RejectRole
        )
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.headline)
        layout.addWidget(self.notes)
        # Stretch 1: Ein größer gezogenes Fenster gibt jeden Bildpunkt der
        # Liste, nicht der Leere zwischen den Zeilen darunter.
        layout.addWidget(self.scroller, 1)
        layout.addWidget(self.more)
        layout.addWidget(self.progress)
        layout.addWidget(self.state)
        layout.addWidget(self.buttons)
        if points:
            self.resize(self.sizeHint().width(), self.sizeHint().height() + CHANGES_START_HEIGHT)

        self._show_offer()

    # --- die vier Zustände ----------------------------------------------------------

    def _show_offer(self) -> None:
        """Was zu Beginn dasteht — und was nicht.

        Ohne startbares Paket gibt es hier nichts zu holen: unter Linux, weil
        sich Flatpak und AppImage nicht von innen ersetzen lassen, und aus den
        Quellen, weil es dann gar keine Installation gibt, die ein Installer
        anfassen könnte. Dann trägt der Weg zur Seite den Hauptknopf, statt
        einen zweiten anzubieten, der nichts kann.
        """
        if self._package is None:
            self.get_button.setVisible(False)
            make_primary(self.page_button)
            self.state.setText(
                tr("Das Paket für dieses System wird auf der Download-Seite angeboten.")
            )
            return
        self.get_button.setVisible(True)
        self.get_button.setText(tr("Herunterladen und installieren"))
        self.state.setText(
            tr("{size} MB werden geladen und geprüft, bevor etwas gestartet wird.").format(
                size=round(self._package.size / 1_048_576)
            )
        )

    def _show_running(self) -> None:
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.get_button.setText(tr("Abbrechen"))
        self.page_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.state.setText(tr("Wird geladen …"))

    def _show_ready(self) -> None:
        """Geholt und geprüft — und erst jetzt ist von Einspielen die Rede.

        **Zwei Sätze, weil es zwei Abläufe gibt.** Unter Windows und im Flatpak
        läuft das Einspielen ohne eine einzige Frage durch, und Solidon kommt
        danach von selbst zurück; auf dem Mac öffnet sich Apples Installer und
        will durchgeklickt werden. Ein Satz für beides müsste einen der beiden
        Fälle falsch beschreiben — und wer „dann startet das
        Installationsprogramm" liest und nichts sieht, hält das Update für
        gescheitert.

        **„Prüfsumme" stand hier und ist herausgeflogen** (Robert, 28.08.2026):
        Sie interessiert einen Kunden nicht. Was ihn interessiert, ist, dass
        geprüft *wurde* — das Verfahren ist unsere Sache, und §37.2 beschreibt
        es an der Stelle, an der es hingehört.
        """
        self.progress.setVisible(False)
        self.get_button.setText(tr("Jetzt installieren"))
        self.page_button.setEnabled(True)
        self.later_button.setEnabled(True)
        self.state.setText(
            tr(
                "Das Paket ist geladen und geprüft. "
                "Solidon wird beendet, spielt das Update ein und startet danach wieder."
            )
            if updates.runs_unattended()
            else tr(
                "Das Paket ist geladen und geprüft. "
                "Solidon wird beendet, dann startet das Installationsprogramm."
            )
        )

    def _show_problem(self, text: str) -> None:
        self.progress.setVisible(False)
        self.get_button.setText(tr("Erneut versuchen"))
        self.get_button.setVisible(True)
        self.page_button.setEnabled(True)
        self.later_button.setEnabled(True)
        self.state.setText(text)

    # --- die Schritte ---------------------------------------------------------------

    def _start(self) -> None:
        """Der eine Knopf, der je nach Stand drei Dinge tut.

        Holen, abbrechen, starten — es ist immer derselbe Ort und immer die
        Handlung, die gerade ansteht. Drei Knöpfe nebeneinander, von denen
        zwei nichts tun, wären dieselbe Auskunft mit mehr Suchen.
        """
        if self._worker is not None:
            self.cancel()
            return
        if self._file is not None:
            self.installRequested.emit(self._file)
            return
        if self._package is None:
            self.open_page()
            return

        worker = _DownloadWorker(self._package)
        worker.step.connect(self._stepped)
        worker.done.connect(self._downloaded)
        worker.failed.connect(self._failed)
        worker.stopped.connect(self._was_cancelled)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(self._worker_done)
        self._worker = worker
        self._show_running()
        self._leash.start(worker)

    def cancel(self) -> None:
        """Abbrechen heißt hier: die halbe Datei fällt weg, nicht der Dialog."""
        if self._worker is not None:
            self._worker.cancelled.cancel()
            self.state.setText(tr("Wird abgebrochen …"))

    def open_page(self) -> None:
        QDesktopServices.openUrl(QUrl(self._release.url or WEBSITE_URL))

    # --- was der Arbeiter meldet ----------------------------------------------------

    def _stepped(self, share: float, text: str) -> None:
        self.progress.setValue(int(share * 100))
        # Der Anteil steht im Balken, die Megabyte daneben: Ein Balken ohne
        # Zahl sagt nicht, ob noch eine Minute kommt oder zehn.
        self.state.setText(tr("Wird geladen: {done}").format(done=text))

    def _downloaded(self, file: object) -> None:
        self._file = Path(str(file))
        self._show_ready()

    def _failed(self, error: object) -> None:
        detail = getattr(error, "detail", "") or getattr(error, "title", "")
        self._show_problem(str(detail))

    def _was_cancelled(self) -> None:
        self._file = None
        self._show_problem(tr("Abgebrochen — es liegt nichts halb Geladenes herum."))

    def _crashed(self, text: str) -> None:
        """Auch das Unerwartete löst den Wartezustand auf (siehe
        :mod:`app.ui.leash`)."""
        self._show_problem(tr("Das Laden ist unerwartet abgebrochen: {reason}").format(reason=text))

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieser Dialog außerhalb von Qt hält.

        Ein laufender Download wird abgebrochen und nicht abgewartet: Er
        kann Minuten dauern, und ein Fenster, das beim Schließen minutenlang
        steht, ist schlimmer als ein abgebrochener Download.

        Warum der Name, warum die eigene Frist: :mod:`app.ui.leash`.
        """
        worker = self._worker
        if worker is not None:
            worker.cancelled.cancel()
        self._leash.wait_all(timeout_ms)

    def _worker_done(self) -> None:
        self._worker = None
        if self._file is None and not self.state.text():
            self._show_offer()
