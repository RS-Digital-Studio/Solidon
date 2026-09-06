"""Rückmeldung senden — Vorschlag, Fehler, Frage (Bauplan §37.2).

Der Weg, den es vorher nicht gab. Ein Fehlerbericht war ein Ordner, den
jemand finden, an eine Mail hängen und abschicken musste; drei Schritte, von
denen jeder einzelne der letzte sein kann. Was hier steht, ist derselbe
Bericht mit einem Knopf daran.

**Von allein geht nichts.** Der Nutzer schreibt, sieht in der Vorschau, was
mitgeht, und drückt *Senden* — das ist der Unterschied zur verbotenen
Telemetrie, und er ist keine Formulierung, sondern der Aufbau dieser Datei:
:func:`app.core.support.send` hat genau einen Aufrufer, und der hängt an einem
Knopf.

Geht der Versand nicht durch, endet das nicht mit „fehlgeschlagen" (Regel 17):
Der Bericht lässt sich ablegen und die Mail von Hand öffnen — zwei Wege, die
ohne die Leitung auskommen, die gerade nicht wollte.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any, Final

from PySide6.QtCore import QBuffer, QIODevice, QRect, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.branding import SUPPORT_ADDRESS
from app.core import feedback, support
from app.core import report as reports
from app.core.errors import CANCEL, AppError, FileWriteError
from app.core.log import get_logger, log_path
from app.core.paths import ensure_dir, user_data_dir
from app.core.support import (
    KIND_BUG,
    KIND_CRASH,
    KIND_IDEA,
    KIND_QUESTION,
    KIND_SURVEY,
    Receipt,
    Ticket,
)
from app.i18n import tr
from app.ui.labels import localised
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.panels import collapsible
from app.ui.style import make_primary
from app.ui.survey import FIELD_HEIGHT, SurveyForm

_log = get_logger(__name__)

#: Kantenmaß, auf das ein Bildschirmfoto vor dem Senden geht. Ein 4K-Fenster
#: wiegt als PNG mehrere Megabyte, und lesbar ist auf dem Support-Bildschirm
#: auch die halbe Breite — die Sendung soll durch jeden Posteingang passen.
MAX_SHOT_WIDTH: Final = 1600

#: Wie viel Protokoll mitreist. Dieselbe Zahl wie im abgelegten Bericht: es
#: sind dieselben Zeilen, nur auf einem anderen Weg.
LOG_LINES: Final = reports.LOG_LINES

#: Wie lange das Schließen auf den Arbeiter wartet, bevor es loslässt.
WAIT_MILLISECONDS: Final = 50

#: Die Reihenfolge im Auswahlfeld. Programmfehler und Bogen stehen nicht dabei
#: — den einen setzt der Fehlerdialog, den anderen der Bogen selbst; ein Nutzer
#: wählt keinen von beiden. Ein Bogen, den jemand aus einem Aufklappmenü wählt,
#: wäre ein Formular ohne Anlass.
KINDS: Final = (KIND_IDEA, KIND_BUG, KIND_QUESTION)

#: Arten, die es nur mit ihrem Anlass gibt — nicht in der Auswahl, aber im Feld.
#:
#: Ein Absturzbericht entsteht aus einem Absturz, ein Bogen aus dreißig Minuten
#: Arbeit. Wer sie aus einem Aufklappmenü wählen könnte, bekäme ein Formular
#: ohne Anlass; wer sie im gefüllten Feld liest, weiß, warum er hier ist.
OCCASION_KINDS: Final = (KIND_CRASH, KIND_SURVEY)


def _paint_viewports(picture: Any, widget: QWidget) -> None:
    """Malt jede 3D-Ansicht in das Bild, das ``grab`` von ihr nicht bekommt.

    **Warum es diesen zweiten Durchgang braucht.** ``QWidget.grab`` malt Qts
    eigenen Puffer ab. Der Viewport zeichnet aber in ein natives
    OpenGL-Kindfenster, und das steht dort nicht drin — auf dem Bild blieb
    genau die Fläche leer, in der das Modell liegt. Ein Kunde, der einen
    Fehler an seinem Teil meldete, schickte ein Bild ohne sein Teil.

    Jede Ansicht rendert sich deshalb selbst (:meth:`Viewport.snapshot`), und
    das Ergebnis wird an ihren Platz im Fensterbild gesetzt. Ihre Lage kommt
    aus ``mapTo`` und ist damit dieselbe, die auch ``grab`` gesehen hat.

    Skaliert wird auf die Widgetgröße: Auf einem Bildschirm mit erhöhter
    Skalierung ist das gerenderte Bild um den Gerätefaktor größer als das
    Widget, und ungefragt eingesetzt läge es über der halben Oberfläche.
    """
    from PySide6.QtGui import QPainter

    from app.ui.overlay import OverlayHost
    from app.ui.viewport import Viewport

    # **Erst die Bilder, dann der Maler.** Ein ``QPainter`` auf dem Abbild zu
    # öffnen, wo es nichts einzusetzen gibt, ist nicht folgenlos: Offscreen gibt
    # es keinen Renderer, jede Ansicht liefert ``None``, und der Maler liefe über
    # ein Bild, das niemand ändert. In der Suite endete das nach einigen Dutzend
    # Fenstern in einer Speicherverletzung — an wandernder Stelle, also nicht
    # dort, wo sie entstand.
    rendered = [
        (view, image)
        for view in widget.findChildren(Viewport)
        if view.isVisible() and (image := view.snapshot()) is not None
    ]
    if not rendered:
        return
    painter = QPainter(picture)
    try:
        for view, image in rendered:
            corner = view.mapTo(widget, view.rect().topLeft())
            painter.drawImage(
                QRect(corner, view.size()),
                image,
                QRect(0, 0, image.width(), image.height()),
            )
            # **Und dann alles wieder darüber, was über der Ansicht lag.** Die
            # Bedienleisten liegen im ``OverlayHost`` und stehen per ``raise_``
            # vor dem Viewport; ``grab`` hatte sie schon richtig im Bild, das
            # eingesetzte Rechteck deckt sie aber zu. Ohne diesen Schritt zeigt
            # das Bild ein Modell und keine Oberfläche — Objektbaum, Parameter
            # und Prüfbericht wären weg, also gerade das, was dem Support sagt,
            # wo der Kunde stand.
            #
            # **Gesucht wird der Host, nicht der direkte Elternteil.** Der
            # Viewport steckt in einem ``QStackedWidget`` darin; wer dort nach
            # Geschwistern fragt, findet nur ihn selbst und malt nichts nach.
            host: QWidget | None = view.parentWidget()
            while host is not None and not isinstance(host, OverlayHost):
                host = host.parentWidget()
            if host is None:
                continue
            for above in host.findChildren(
                QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
            ):
                # Der Stapel, in dem die Ansicht selbst sitzt, gehört nicht
                # dazu — ihn zu malen hieße, das gerade Eingesetzte wieder
                # zuzudecken.
                if not above.isVisible() or above is view or above.isAncestorOf(view):
                    continue
                above.render(painter, above.mapTo(widget, above.rect().topLeft()))
    finally:
        painter.end()


def window_shot(widget: QWidget | None) -> bytes:
    """Ein Bildschirmfoto des Fensters als PNG.

    ``grab`` und nicht der ganze Bildschirm: Was neben Solidon offen ist,
    geht den Support nichts an, und wer ein Bild seines Desktops verschickt,
    verschickt mehr, als er zeigen wollte.

    Was ``grab`` nicht sieht, holt :func:`_paint_viewports` nach — die 3D-
    Ansicht ist ein natives Fenster und bliebe sonst leer. Beides zusammen
    ergibt das Bild, das der Kunde vor sich hat, und nichts darüber hinaus.
    """
    if widget is None:
        return b""
    picture = widget.grab().toImage()
    _paint_viewports(picture, widget)
    if picture.width() > MAX_SHOT_WIDTH:
        picture = picture.scaledToWidth(MAX_SHOT_WIDTH, Qt.TransformationMode.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    # Zur Laufzeit nimmt PySide hier eine Zeichenkette; die Stubs behaupten
    # bytes — der Laufzeit wird geglaubt, den Stubs widersprochen.
    picture.save(buffer, "PNG")  # type: ignore[call-overload]
    return bytes(buffer.data().data())


def session_bytes(session: Any, folder: Path) -> bytes:
    """Die laufende Sitzung als Projektcontainer.

    Der Container ist der Verlauf: Operationsstapel, Parameter, Passungen,
    Transaktionen und der Chat stehen darin, und damit reproduziert er den
    Fehler statt ihn zu beschreiben (§16.2). Gespeichert wird in einen
    eigenen Ordner und nicht über die Datei des Nutzers — eine Rückmeldung
    schreibt nichts an seiner Arbeit fest.
    """
    from app.core.scene.project import save

    target = folder / "sitzung.p3d"
    save(session.project, target)
    return target.read_bytes()


def log_tail() -> bytes:
    """Das Ende des Protokolls. Es hat den Rechner nie verlassen, und jetzt
    nur, weil jemand es selbst angehängt hat (§33.2)."""
    source = log_path()
    if not source.is_file():
        return b""
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()[-LOG_LINES:]
    return "\n".join(lines).encode("utf-8")


class _SendWorker(Worker):
    """Der Versand, abseits des Oberflächen-Threads.

    Ein Hochladen von ein paar Megabyte über eine schlechte Leitung dauert
    Sekunden bis zum Zeitlimit; im Hauptthread stünde das Fenster so lange
    (§2.8).

    Dieser Arbeiter fing schon vor der Basisklasse alles und machte daraus ein
    ``SendFailed`` — von dreiundzwanzig war er der einzige. Das bleibt, weil es
    besser ist: Ein Versand, der scheitert, ist ein Fehler mit Vorschlägen und
    nicht bloß eine Zeile für „Details". ``crashed`` ist danach eine Sicherung,
    die nie greifen sollte.
    """

    done = Signal(object)
    failed = Signal(object)

    def __init__(self, ticket: Ticket, url: str, sender: Any | None) -> None:
        super().__init__()
        self._ticket = ticket
        self._url = url
        self._sender = sender

    def work(self) -> None:
        try:
            receipt = support.send(self._ticket, self._url, self._sender)
        except AppError as problem:
            self.failed.emit(problem)
            return
        except Exception as problem:  # pragma: no cover - der Kern fängt breit
            self.failed.emit(support.SendFailed(values={"reason": str(problem)[:200]}))
            return
        self.done.emit(receipt)


class SupportDialog(QDialog):
    """Schreiben, sehen was mitgeht, senden.

    ``attachments`` kommen als Funktionen herein und nicht als Bytes: Ein
    Bildschirmfoto, das beim Öffnen des Dialogs entsteht, zeigt den Dialog;
    eine Sitzung, die niemand anhängt, muss nicht gespeichert werden. Beides
    passiert erst, wenn das Kästchen steht.
    """

    def __init__(
        self,
        kind: str = KIND_IDEA,
        *,
        message: str = "",
        detail: str = "",
        error: BaseException | None = None,
        screenshot: bytes | None = None,
        session: Any | None = None,
        contact: str = "",
        url: str = support.SUPPORT_URL,
        sender: Any | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._session = session
        self._url = url
        self._sender = sender
        self._shot = screenshot if screenshot is not None else b""
        self._session_data: bytes | None = None
        self._worker: _SendWorker | None = None
        self._leash = WorkerLeash(self)
        self.receipt: Receipt | None = None
        self.written: Path | None = None
        """Wohin der Bericht abgelegt wurde, falls jemand diesen Weg nahm."""

        self.detail = detail or ("".join(traceback.format_exception(error)) if error else "")

        self.setWindowTitle(tr("Fehlerbericht") if kind == KIND_CRASH else tr("Rückmeldung senden"))
        self.setMinimumWidth(620)

        # §33.1: Ein Programmfehler darf nie wie ein Fehler des Nutzers
        # aussehen. Also steht über einem Absturz ein anderer Satz als über
        # einem Vorschlag — derselbe Dialog, andere Ansage.
        if kind == KIND_CRASH:
            opening = tr(
                "Das war ein Programmfehler, nicht Ihre Schuld. Was Sie hier schreiben, "
                "hilft ihn zu finden. Die Meldung geht an {address}; "
                "gesendet wird nur, was unten steht."
            )
        elif kind == KIND_SURVEY:
            # Der dritte Fall, und er unterscheidet sich vom zweiten in der
            # Richtung: Dort meldet sich jemand von sich aus, hier ist er
            # gefragt worden. Der Satz steht im Kern, weil er zur Frage gehört
            # und nicht zum Fenster.
            opening = str(feedback.OPENING)
        else:
            opening = tr(
                "Was fehlt, was hakt, was besser sein könnte — schreiben Sie es auf. "
                "Die Nachricht geht an {address}; gesendet wird nur, was unten steht."
            )
        self._opening = opening
        self._crashes = 1
        """Wie viele Programmfehler dieser Bericht trägt (§2.7)."""
        self.headline = QLabel(opening.replace("{address}", SUPPORT_ADDRESS), self)
        self.headline.setWordWrap(True)

        self.kind = QComboBox(self)
        for entry in KINDS:
            self.kind.addItem(str(support.KIND_NAMES[entry]), entry)
        if kind in OCCASION_KINDS:
            # **Zwei Arten, die man nicht wählt, sondern bekommt.** Der
            # Fehlerbericht kommt aus einem Absturz, der Bogen aus dreißig
            # Minuten Nutzung — beide stehen in der Liste, damit das Feld nicht
            # leer aussieht, und in keiner Auswahl, weil sie ohne ihren Anlass
            # nicht existieren.
            self.kind.addItem(str(support.KIND_NAMES[kind]), kind)
        index = self.kind.findData(kind)
        self.kind.setCurrentIndex(max(index, 0))

        self.survey = SurveyForm(self) if kind == KIND_SURVEY else None
        """Die Fragen des Bogens, oder ``None`` — dann ist dies der gewöhnliche
        Rückmeldungsdialog (§37.2)."""

        self.message = QPlainTextEdit(self)
        self.message.setPlaceholderText(
            tr("Was in den Feldern darüber keinen Platz hatte.")
            if self.survey is not None
            else tr("Was haben Sie getan, was ist passiert, was hatten Sie erwartet?")
        )
        self.message.setPlainText(message)
        if self.survey is not None:
            # **Fest und so hoch wie die Felder darüber.** Als dehnbares Feld
            # nahm es allen Platz, den der Dialog übrig hatte, und war damit
            # doppelt so groß wie die beiden Fragen — der Nachtrag sah aus wie
            # die Hauptsache.
            self.message.setFixedHeight(FIELD_HEIGHT)
        else:
            self.message.setMinimumHeight(120)
        # Sonst nimmt das Feld den Tabulator als Zeichen, und wer ohne Maus
        # arbeitet, kommt aus ihm nicht mehr heraus (``tests/test_style.py``).
        self.message.setTabChangesFocus(True)

        self.contact = QLineEdit(contact, self)
        self.contact.setPlaceholderText(tr("Nur nötig, wenn Sie eine Antwort möchten"))

        form = QFormLayout()
        kind_row = QLabel(tr("Art"), self)
        form.addRow(kind_row, self.kind)
        if self.survey is not None:
            # **Im Bogen steht die Art nicht zur Wahl.** Sie ist Teil des
            # Anlasses und nicht der Nachricht — und ein Aufklappmenü als
            # erste Zeile einer Frage lädt dazu ein, etwas einzustellen, statt
            # zu antworten. Gesetzt bleibt sie trotzdem: ``ticket()`` liest
            # ``currentData()``, und das tut ein verborgenes Feld auch. Wer
            # einen Fehler melden will, hat *Hilfe → Rückmeldung senden*.
            kind_row.setVisible(False)
            self.kind.setVisible(False)
            # Über beide Spalten: Der Bogen bringt seine eigenen
            # Beschriftungen mit, und eine Zeilenbeschriftung davor wäre eine
            # Überschrift über einer Überschrift.
            form.addRow(self.survey)
            # Ohne diese Zeile zeigt die Vorschau etwas anderes als die
            # Sendung — und „nichts ungesehen" ist eine der vier Zusagen
            # dieses Dialogs.
            self.survey.changed.connect(self._refresh)
        form.addRow(
            tr("Sonst noch etwas") if self.survey is not None else tr("Ihre Rückmeldung"),
            self.message,
        )
        form.addRow(tr("Rückadresse"), self.contact)

        self.with_shot = QCheckBox(tr("Bildschirmfoto anhängen"), self)
        self.with_shot.setChecked(bool(self._shot))
        self.with_shot.setEnabled(bool(self._shot))
        self.with_session = QCheckBox(
            tr("Sitzung mit Verlauf anhängen — sie enthält Ihr Modell und den Chat"), self
        )
        self.with_session.setEnabled(session is not None)
        self.with_log = QCheckBox(
            tr("Protokoll anhängen — es kann Dateipfade Ihres Rechners enthalten"), self
        )
        self.with_log.setChecked(True)

        for box in (self.with_shot, self.with_session, self.with_log):
            box.toggled.connect(self._refresh)

        self.preview = QTextBrowser(self)
        self.preview.setMinimumHeight(160)
        self.previews = collapsible(tr("Was gesendet wird"), self.preview, open_now=False)

        self.state = QLabel(self)
        self.state.setWordWrap(True)
        self.progress = QProgressBar(self)
        # Ein Hochladen kennt keinen Fortschritt, den dieser Dialog sähe:
        # ``urlopen`` meldet keinen, und ein Balken, der eine Zahl erfindet,
        # ist eine Zusage, die niemand einlöst. Also der laufende Balken —
        # er sagt „es läuft" und behauptet nichts über „wie lange" (§2.8).
        self.progress.setRange(0, 0)
        # Auch ein laufender Balken schreibt keine Zahl in seine Füllung: Qt
        # zeigt hier nichts, aber die Regel gilt für alle vier Balken der
        # Oberfläche, und ein Bereich, der später doch zählt, hätte sie sonst
        # stillschweigend gerissen (tests/test_style.py).
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)

        self.buttons = QDialogButtonBox(self)
        self.send = self.buttons.addButton(tr("Senden"), QDialogButtonBox.ButtonRole.AcceptRole)
        make_primary(self.send)
        # Der Weg von §37.2 bleibt ein Weg und wird kein Notausgang: Wer ohne
        # Netz sitzt oder nichts aus der Hand geben will, legt den Bericht ab
        # und entscheidet selbst, was damit geschieht. Er steht deshalb
        # dauerhaft da und nicht erst, wenn etwas schiefging.
        self.save_folder = self.buttons.addButton(
            str(support.SAVE_REPORT.label), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.save_folder.clicked.connect(self._write_folder)
        self.buttons.addButton(str(CANCEL.label), QDialogButtonBox.ButtonRole.RejectRole)
        self.buttons.accepted.connect(self._start)
        self.buttons.rejected.connect(self.reject)

        # Die Mail von Hand steht erst da, wenn der Versand sie braucht: ein
        # zweiter Weg neben dem Knopf, der gerade funktioniert, liest sich wie
        # eine Warnung vor dem Senden.
        self.by_mail = QPushButton(str(support.SEND_BY_MAIL.label), self)
        self.by_mail.setVisible(False)
        self.by_mail.clicked.connect(self._open_mail)

        layout = QVBoxLayout(self)
        layout.addWidget(self.headline)
        layout.addLayout(form)
        layout.addWidget(self.with_shot)
        layout.addWidget(self.with_session)
        layout.addWidget(self.with_log)
        layout.addWidget(self.previews)
        layout.addWidget(self.state)
        layout.addWidget(self.by_mail)
        layout.addWidget(self.progress)
        layout.addWidget(self.buttons)

        self.message.textChanged.connect(self._update_send)
        self.kind.currentIndexChanged.connect(self._refresh)
        self._refresh()

    # --- Zustand ----------------------------------------------------------------

    def ticket(self) -> Ticket:
        """Die Sendung, wie sie gerade dasteht."""
        return Ticket(
            kind=str(self.kind.currentData() or KIND_IDEA),
            # Der Bogen setzt seine Antworten zum Nachrichtentext zusammen —
            # im Kern, damit die Vorschau darunter genau das zeigt, was ankommt.
            # Das freie Feld hängt sich an, statt den Bogen zu ersetzen.
            message=(
                self.survey.text(self.message.toPlainText())
                if self.survey is not None
                else self.message.toPlainText()
            ),
            contact=self.contact.text().strip(),
            detail=self.detail,
            attachments=self._attachments(),
        )

    def _attachments(self) -> list[support.Attachment]:
        """Was angehakt ist — und erst dann gebaut wird."""
        found: list[support.Attachment] = []
        if self.with_shot.isChecked() and self._shot:
            found.append(
                support.Attachment("bildschirmfoto.png", self._shot, tr("Das Fenster von Solidon"))
            )
        if self.with_session.isChecked():
            data = self._session_container()
            if data:
                found.append(support.Attachment("sitzung.p3d", data, self._session_note()))
        if self.with_log.isChecked():
            data = log_tail()
            if data:
                found.append(support.Attachment("protokoll.txt", data, tr("Die letzten Zeilen")))
        return found

    def _session_note(self) -> str:
        """Was am Sitzungsanhang steht — und die eine Warnung, die dazugehört.

        **Hier und nicht beim Speichern (§24.5, Regel 13).** Ein eigener
        Baustein reist nie in einer Projektdatei mit; wer an so einem Projekt
        arbeitet, speichert es zwanzigmal am Abend, und eine Meldung dabei wird
        beim einundzwanzigsten Mal weggeklickt wie die zwanzig davor. Der
        Schaden entsteht erst, wenn die Datei **zu jemand anderem** geht — und
        von hier geht sie zum Support.

        Ohne den Satz bekommt er ein Projekt, das er nicht rechnen kann, und
        merkt es beim Öffnen: mit einer Ursache auf einem Rechner, an den dann
        niemand mehr herankommt.

        Der Hinweis steht an der Beschreibung des Anhangs, weil er genau ihm
        gilt — ``Ticket.as_text`` trägt sie in die Sendung, die Vorschau zeigt
        sie, und der abgelegte Ordner nimmt denselben Text. Ein Ort, alle drei
        Wege hinaus.
        """
        note = tr("Modell, Operationsstapel und Chat-Verlauf")
        if self._session is None:
            return note
        try:
            from app.core.knowledge.parts import check as part_check

            findings = part_check.check_outgoing(self._session.project.document)
        except (AppError, OSError) as problem:
            # Dieselbe Haltung wie beim Anhang selbst: Was sich nicht sagen
            # lässt, nimmt der Rückmeldung nicht den Sinn.
            _log.warning("outgoing check failed: %s", problem)
            return note
        parts = ", ".join(
            str(finding.values.get("parts", "")) for finding in findings if finding.values
        )
        return f"{note} — {tr('Braucht eigene Bausteine')}: {parts}" if parts else note

    def _session_container(self) -> bytes:
        """Die Sitzung, einmal gespeichert und dann behalten.

        Zweimal speichern hieße, den Container zwischen Vorschau und Versand
        neu zu schreiben — und dann stünde in der Vorschau eine andere Größe
        als in der Sendung.
        """
        if self._session_data is not None:
            return self._session_data
        if self._session is None:
            self._session_data = b""
            return self._session_data
        try:
            folder = ensure_dir(user_data_dir() / reports.REPORT_DIRNAME)
            self._session_data = session_bytes(self._session, folder)
        except (AppError, OSError) as problem:
            # Eine Sitzung, die sich nicht speichern lässt, nimmt der
            # Rückmeldung nicht den Sinn — sie nimmt ihr einen Anhang.
            _log.warning("session could not be attached: %s", problem)
            self.state.setText(tr("Die Sitzung ließ sich nicht anhängen — der Rest geht trotzdem."))
            self._session_data = b""
        return self._session_data

    def add_crash(self, detail: str) -> None:
        """Ein zweiter Programmfehler, während dieser Bericht schon offen steht.

        **Nicht ein zweites Fenster.** Zwei modale Dialoge übereinander heißen
        zweimal wegklicken, und der zweite Fehler ist oft der eigentliche — der
        erste ist die Folge, die zuerst auffällt. Unterdrücken verlöre ihn,
        bloßes Zählen ließe ihn unerreichbar: Eine Ausnahme ohne Weg zu ihrem
        Inhalt trägt keinen Handlungsvorschlag mehr (Regel 17).

        Ein Bericht ist ohnehin ein Sammelbehälter — Bildschirmfoto, Sitzung,
        Rückadresse. Zwei Berichte für einen Absturzmoment sind zwei halbe, und
        der Kunde schickt einen davon.

        **Das Bildschirmfoto bleibt das des ersten Fehlers**, und das ist keine
        Sparsamkeit: Es entsteht vor dem Dialog, damit es zeigt, was darunter
        schiefging. Beim zweiten Fehler steht der Bericht schon offen — ein
        neues Foto zeigte ihn selbst.
        """
        self._crashes += 1
        trenner = f"--- {tr('Fehler')} {self._crashes} ---"
        self.detail = "\n\n".join((self.detail, trenner, detail))
        gezaehlt = f"{tr('Seitdem sind weitere Fehler aufgetreten')}: {self._crashes}"
        self.headline.setText(
            self._opening.replace("{address}", SUPPORT_ADDRESS) + "\n\n" + gezaehlt
        )
        self._refresh()

    def _refresh(self) -> None:
        """Vorschau und Größen nachziehen — nach jedem Kästchen."""
        ticket = self.ticket()
        lines = [ticket.as_text()]
        # „Vorher sieht er, was mitgeht" galt nicht fürs vorangekreuzte
        # Protokoll: In der Vorschau standen Name und Größe, mitgereist wären
        # die Zeilen — samt Dateipfaden, in denen der Windows-Kontoname steht
        # (Gesamtreview L-12). Textanhänge stehen deshalb im Wortlaut da; für
        # Bild und Sitzung bleibt es bei Name und Größe, mehr zeigte nichts.
        for entry in ticket.attachments:
            if not entry.name.endswith(".txt"):
                continue
            lines.extend(["", f"--- {entry.name} ---", entry.data.decode("utf-8", "replace")])
        size = ticket.total_bytes
        if size:
            lines.append("")
            lines.append(
                f"{tr('Größe der Sendung')}: " + localised(f"{size / (1024 * 1024):.1f} MB")
            )
        self.preview.setPlainText("\n".join(lines))
        self._update_send()

    def _update_send(self) -> None:
        """*Senden* gilt erst, wenn etwas dasteht (§2.7 — kein toter Knopf).

        „Etwas" ist der geschriebene Satz **oder** der Stapelabzug: Nach einem
        Absturz trägt der Bericht sich selbst, und ein gesperrter Knopf wäre
        dort die Sackgasse hinter dem Programmfehler.
        """
        running = self._worker is not None and self._worker.isRunning()
        # Der Bogen baut seinen Text aus Bewertung, Antworten und dem freien
        # Nachtrag. Die Felder sind ausdrücklich optional; „optional" heißt
        # aber nicht, dass eine einzelne Antwort im unsichtbaren Teil des
        # Formulars den Senden-Knopf nicht freischaltet. Maßgeblich ist daher
        # dieselbe Sendung, die ``_start`` anschließend prüft und verschickt.
        has_content = bool(self.ticket().message.strip() or self.detail.strip())
        self.send.setEnabled(has_content and not running)

    # --- Senden -----------------------------------------------------------------

    def _start(self) -> None:
        """Der eine Knopf, an dem der Versand hängt."""
        ticket = self.ticket()
        try:
            support.check(ticket)
        except AppError as problem:
            self._show_problem(problem, ways=False)
            return

        self.state.setText(tr("Wird gesendet …"))
        self.progress.setVisible(True)
        self.save_folder.setVisible(False)
        self.by_mail.setVisible(False)

        worker = _SendWorker(ticket, self._url, self._sender)
        worker.done.connect(self._sent)
        worker.failed.connect(self._not_sent)
        # Der Arbeiter fängt selbst breit und macht ein ``SendFailed`` daraus;
        # diese Zeile ist die Sicherung dahinter und sollte nie greifen.
        worker.crashed.connect(
            lambda detail: self._not_sent(support.SendFailed(values={"reason": detail[:200]}))
        )
        worker.finished.connect(self._thread_done)
        self._worker = worker
        self._leash.start(worker)
        self._update_send()

    def _sent(self, receipt: object) -> None:
        assert isinstance(receipt, Receipt)
        self.receipt = receipt
        self.progress.setVisible(False)
        reference = f" {tr('Vorgang')}: {receipt.reference}" if receipt.reference else ""
        self.state.setText(tr("Angekommen. Danke — das hilft wirklich.") + reference)
        _log.info("support ticket sent, reference=%s", receipt.reference or "-")
        if self.survey is not None:
            # Wer geantwortet hat, wird nicht noch einmal gefragt. Erst hier
            # und nicht beim Öffnen: Ein Bogen, den jemand zumacht, ohne ihn
            # abzuschicken, ist keine Antwort — die Einladung ist beim Zeigen
            # gezählt worden, und davon gibt es drei.
            feedback.mark_answered()
        self.send.setEnabled(False)
        self.accept()

    def _not_sent(self, problem: object) -> None:
        """Kein „fehlgeschlagen": zwei Wege, die ohne diese Leitung gehen."""
        self.progress.setVisible(False)
        if isinstance(problem, AppError):
            self._show_problem(problem, ways=True)
        else:  # pragma: no cover - der Arbeiter verpackt alles als AppError
            self.state.setText(str(problem))
        self._update_send()

    def _show_problem(self, problem: AppError, *, ways: bool) -> None:
        lines = [str(problem.title)]
        if problem.detail is not None:
            lines.append(str(problem.detail))
        reason = problem.values.get("reason")
        if reason:
            lines.append(str(reason))
        self.state.setText("\n".join(lines))
        self.save_folder.setVisible(ways)
        self.by_mail.setVisible(ways)

    def _thread_done(self) -> None:
        # `finished` heißt „`run` ist zurück", nicht „das Objekt darf weg" —
        # das Loslassen übernimmt die Halteleine.
        worker = self._worker
        self._worker = None
        if worker is not None:
            self._leash.hold_until_done(worker)
        self._update_send()

    # --- Die Wege ohne Netz -----------------------------------------------------

    def report(self) -> reports.ErrorReport:
        """Der Bericht, wie er abgelegt würde.

        Als eigene Auskunft und nicht nur im ``_write_folder``: Was hinausgeht,
        gehört an einer Stelle zusammengebaut und prüfbar — sonst prüft ein
        Test den Ordner auf der Platte statt den Inhalt.
        """
        ticket = self.ticket()
        # **Nicht ``ticket.as_text()``.** Der baut denselben Rahmen wie
        # ``reports.as_text`` — Betreff, Zeitstempel, Systemblock — und wer ihn
        # als ``detail`` einsetzt, bekommt alles zweimal: erst den Kopf, dann
        # den ganzen Ticket-Text mit eigenem Kopf und eigenem Systemblock, dann
        # den Steckbrief, dann den Systemblock ein zweites Mal. Gesehen, als
        # der Steckbrief dazukam und der Bericht zum ersten Mal ausgedruckt
        # dastand.
        #
        # Die Teile gehören in die Felder, die sie meinen: Der Fehlertext ist
        # der ``traceback``, die Nachricht das ``detail``, und den Rahmen baut
        # ``reports.as_text`` — einmal.
        lines = [ticket.message.strip()]
        if ticket.contact:
            lines.extend(["", f"{tr('Rückantwort an')}: {ticket.contact}"])
        if ticket.attachments:
            lines.extend(["", "--- anhänge ---"])
            lines.extend(
                f"{entry.name} ({entry.size // 1024} KB)"
                + (f" — {entry.description}" if entry.description else "")
                for entry in ticket.attachments
            )
        return reports.ErrorReport(
            summary=ticket.subject,
            detail="\n".join(lines),
            traceback=self.detail,
            digest=self._scene_digest(),
            include_log=self.with_log.isChecked(),
        )

    def _scene_digest(self) -> str:
        """Der Steckbrief der Szene — Maße, Merkmale, Verlauf, als Text.

        **Ohne ihn lässt sich ein Kundenfehler oft nicht entscheiden.** Am
        23.08.2026 stand im Protokoll des ersten Kunden neunzehnmal derselbe
        Abbruch, und ob drei erkannte Wülste drei Kanten waren oder eine
        dreimal erkannte, war gar nicht zu beantworten: Die Maße standen
        nirgends.

        **Der Steckbrief und nicht die Projektdatei.** Er nennt Objekte mit
        Maßen, Merkmale, Parameter, Passungen und den Verlauf mit seinen
        Werten. Die Projektdatei sagte alles, enthält aber die Geometrie und
        reist deshalb nur auf ausdrücklichen Wunsch mit (§37.2) — der
        Mittelweg gibt uns die Diagnose und dem Kunden sein Modell.

        Scheitert er, bleibt er leer: Der Fehlerbericht ist der Weg, den jemand
        nimmt, wenn schon etwas kaputt ist, und er darf an einer fehlenden
        Auskunft nicht selbst scheitern — dieselbe Haltung wie beim
        Bausteinabgleich zwei Methoden weiter.
        """
        session = self._session
        result = session.last_result if session is not None else None
        if session is None or result is None:
            return ""
        try:
            from app.core.perceive.digest import digest

            return digest(result.scene, session.project.document)
        except (AppError, OSError, ValueError) as problem:
            _log.warning("digest for the report failed: %s", problem)
            return ""

    def _write_folder(self) -> bool:
        """Denselben Inhalt als Ordner ablegen — der Weg von vorher."""
        ticket = self.ticket()
        written: Path | None = None
        try:
            written = reports.write(self.report())
            for entry in ticket.attachments:
                (written / entry.name).write_bytes(entry.data)
        except AppError as problem:
            self._show_problem(problem, ways=True)
            return False
        except OSError as problem:
            target = written or self.written or user_data_dir()
            self._show_problem(
                FileWriteError(str(target), detail=str(problem)),
                ways=True,
            )
            return False
        assert written is not None
        self.written = written
        self.state.setText(f"{tr('Abgelegt unter')}: {self.written}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.written)))
        return True

    def _open_mail(self) -> None:
        """Die vorbereitete Mail im Mailprogramm des Nutzers.

        Anhänge kann ein ``mailto`` nicht tragen. Also wird zuerst abgelegt,
        wenn das noch niemand getan hat — sonst stünde im Mailfenster ein
        Text, der auf Dateien verweist, die es nicht gibt.
        """
        if self.written is None and not self._write_folder():
            return
        QDesktopServices.openUrl(QUrl(support.mail_link(self.ticket())))

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieser Dialog außerhalb von Qt hält.

        ``reject`` wartet auf denselben Arbeiter — dort, weil ein Abbruch
        ihn nicht laufen lassen soll; hier, weil ihn sonst niemand aufhält.

        Warum der Name, warum die eigene Frist: :mod:`app.ui.leash`.
        """
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(timeout_ms)
        self._leash.wait_all(timeout_ms)

    def reject(self) -> None:
        """Abbrechen wartet auf den Arbeiter, statt ihn laufen zu lassen."""
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(WAIT_MILLISECONDS)
        super().reject()
