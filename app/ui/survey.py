"""Der Bogen im Rückmeldungsdialog (§37.2).

Kein eigenes Fenster und kein eigener Sendeknopf: Was hier steht, ist der
obere Teil von :class:`app.ui.support_dialog.SupportDialog`, wenn er als
Bogen geöffnet wird. Der Grund steht in :mod:`app.core.feedback` und ist die
Grenze zur verbotenen Telemetrie — **es gibt genau einen Weg hinaus**, und
einen zweiten zu bauen, nur weil er bequemer wäre, hieße sie aufzugeben.

Die Fragen selbst stehen nicht hier, sondern im Kern. Diese Datei zeigt sie
an und sammelt die Antworten ein; was gefragt wird, ist eine Entscheidung
über das Produkt und keine über ein Widget.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.core import feedback
from app.core.log import get_logger
from app.ui.leash import stop_watching_the_dying
from app.ui.style import ROOMY, SPACE, make_primary
from app.ui.theme import THEMES

_log = get_logger(__name__)

#: Wie oft die Uhr nachsieht. Eine Minute ist die Auflösung, in der auch
#: gezählt wird — feiner wäre eine Genauigkeit, die niemand braucht, und
#: gröber verschenkte die letzte Minute vor der Frage.
TICK_SECONDS = 60

#: Woran Arbeit erkannt wird. Absichtlich **keine** Mausbewegung: Ein Zeiger,
#: der über ein Fenster streicht, ist keine Nutzung, und ein Fenster, das über
#: Nacht offen steht, hätte damit acht Stunden „gearbeitet".
WORK_EVENTS = frozenset(
    {
        QEvent.Type.KeyPress,
        QEvent.Type.MouseButtonPress,
        QEvent.Type.Wheel,
        QEvent.Type.Drop,
    }
)

#: Wie hoch ein Antwortfeld ist. Drei Zeilen: genug, dass ein Satz nicht
#: eingeklemmt wirkt, und wenig genug, dass zwei davon plus Nachrichtenfeld in
#: den Dialog passen, ohne dass jemand scrollt.
FIELD_HEIGHT = 64


class SurveyForm(QWidget):
    """Die Fragen des Bogens, über dem Nachrichtenfeld des Dialogs.

    Kein Feld ist Pflicht. Wer nur eine Stufe anklickt, hat etwas gesagt; wer
    zwei Sätze schreibt, hat mehr gesagt — und wer nichts ausfüllt, bekommt
    dieselbe Absage wie bei jeder leeren Rückmeldung, nämlich die aus
    :func:`app.core.support.check` mit ihrem Vorschlag.
    """

    changed = Signal()
    """Etwas wurde angeklickt oder getippt. Der Dialog zieht daran seine
    Vorschau nach — was gesendet wird, muss zu sehen sein, bevor es geht."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE)

        self.rating_label = QLabel(str(feedback.RATING_LABEL), self)
        self.rating_label.setWordWrap(True)
        layout.addWidget(self.rating_label)

        # **Die Zahl am Knopf, die Wörter an den Enden.** Der erste Entwurf
        # schrieb „2 — Mit Mühe" an jeden der fünf, und das war in vier von
        # sechs Sprachen zu breit: Portugiesisch brauchte 635 Punkte, wo 598
        # da waren, und Qt schnitt die Beschriftungen ab — derselbe Fehler wie
        # auf dem Hauptknopf des Trennwerkzeugs, nur fünffach.
        #
        # Die Stufen bleiben trotzdem benannt: Jeder Knopf trägt sein Wort im
        # Tooltip **und** im Barrierefreiheitsnamen, und die Sendung schreibt
        # es aus („3/5 (Geht so)"). Was verschwindet, ist die Wiederholung im
        # Bild — nicht die Auskunft.
        self.ratings = QButtonGroup(self)
        steps = QHBoxLayout()
        steps.setSpacing(SPACE)
        self.lowest = QLabel(str(feedback.RATINGS[0][1]), self)
        steps.addWidget(self.lowest)
        for step, label in feedback.RATINGS:
            button = QRadioButton(str(step), self)
            named = f"{step} — {label}"
            button.setToolTip(named)
            button.setAccessibleName(named)
            self.ratings.addButton(button, step)
            steps.addWidget(button)
        self.highest = QLabel(str(feedback.RATINGS[-1][1]), self)
        steps.addWidget(self.highest)
        steps.addStretch(1)
        layout.addLayout(steps)
        self.ratings.idToggled.connect(self._touched)

        self.fields: dict[str, QPlainTextEdit] = {}
        for question in feedback.QUESTIONS:
            title = QLabel(str(question.label), self)
            title.setWordWrap(True)
            field = QPlainTextEdit(self)
            field.setPlaceholderText(str(question.hint))
            field.setFixedHeight(FIELD_HEIGHT)
            # Sonst nimmt das Feld den Tabulator als Zeichen, und wer ohne
            # Maus arbeitet, kommt aus ihm nicht mehr heraus
            # (``tests/test_style.py``).
            field.setTabChangesFocus(True)
            field.setAccessibleName(str(question.label))
            title.setBuddy(field)
            field.textChanged.connect(self._touched)
            layout.addWidget(title)
            layout.addWidget(field)
            self.fields[question.key] = field

    def _touched(self, *_ignored: object) -> None:
        self.changed.emit()

    def rating(self) -> int | None:
        """Die angeklickte Stufe, oder ``None``, wenn keine angeklickt wurde.

        ``QButtonGroup`` gibt ``-1`` zurück, solange nichts gewählt ist; das
        ist keine Stufe und darf keine werden.
        """
        chosen = self.ratings.checkedId()
        return chosen if chosen > 0 else None

    def answers(self) -> dict[str, str]:
        """Was in den Feldern steht, unter den Schlüsseln des Kerns."""
        return {key: field.toPlainText() for key, field in self.fields.items()}

    def text(self, extra: str = "") -> str:
        """Der Nachrichtentext der Sendung.

        Gebaut wird er im Kern (:func:`app.core.feedback.compose`), damit die
        Vorschau des Dialogs genau das zeigen kann, was ankommt. ``extra`` ist
        das freie Nachrichtenfeld darunter — was jemand dort schreibt, hängt
        sich an, statt den Bogen zu ersetzen.
        """
        return feedback.compose(self.rating(), self.answers(), extra)


class UsageClock(QObject):
    """Zählt gearbeitete Zeit und sagt Bescheid, wenn der Bogen fällig ist.

    **Sie zählt Arbeit, nicht Laufzeit.** Eine Minute zählt nur, wenn in ihr
    etwas getippt, geklickt, gescrollt oder abgelegt wurde — sonst erschiene
    der Bogen jemandem, der gerade vom Kaffee zurückkommt und noch nichts
    getan hat. Das ist der Unterschied, an dem „Nutzungsdauer" sonst
    zerbricht: Ein offenes Fenster ist keine Nutzung.

    Sie hält an, sobald sie ihr Signal gegeben hat oder die Sache erledigt
    ist. Eine Uhr, die weiterläuft, obwohl niemand mehr gefragt wird, schreibt
    jede Minute eine Datei, die niemand mehr liest.

    **Sie sendet nichts.** Sie macht sichtbar, dass gefragt wird; alles
    Weitere hängt an einem Klick (§37.2).
    """

    due = Signal()
    """Die Zeit ist zusammen. Das Fenster zeigt daraufhin seinen Streifen —
    es öffnet keinen Dialog, denn niemand hat darum gebeten."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_SECONDS * 1000)
        # Eine gebundene Methode, kein Lambda: Qt hält jene schwach und dieses
        # stark, und ein stark gehaltener Zeitgeber überlebt sein Fenster.
        self._timer.timeout.connect(self.tick)
        self._worked = False
        self._watching = False

    def start(self) -> None:
        """Beginnt zu zählen — wenn es überhaupt noch etwas zu fragen gibt."""
        if not feedback.enabled():
            return
        application = QApplication.instance()
        if application is not None and not self._watching:
            application.installEventFilter(self)
            self._watching = True
        self._timer.start()

    def running(self) -> bool:
        """Ob noch gezählt wird. Das Fenster fragt danach, wenn es aufräumt —
        und ein Test, statt in den Zeitgeber zu greifen."""
        return self._timer.isActive()

    def stop(self) -> None:
        """Hält an und hängt sich wieder aus."""
        self._timer.stop()
        application = QApplication.instance()
        if application is not None and self._watching:
            application.removeEventFilter(self)
        self._watching = False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt gibt den Namen
        """Merkt sich, dass in dieser Minute gearbeitet wurde.

        Der Filter urteilt nicht und verschluckt nichts: Er setzt einen
        Wahrheitswert und gibt das Ereignis weiter.
        """
        if event.type() in WORK_EVENTS:
            self._worked = True
        return super().eventFilter(watched, event)

    def tick(self) -> None:
        """Eine Minute ist herum. Zählt sie, wenn in ihr etwas geschah."""
        if not self._worked:
            return
        self._worked = False
        progress = feedback.record(TICK_SECONDS)
        if not feedback.enabled(progress):
            self.stop()
            return
        if feedback.due(progress):
            # **Sie hält hier nicht selbst an.** Das Fenster kann gerade
            # rechnen, und dann fragt niemand — es meldet sich in einer Minute
            # wieder, statt die Einladung für die ganze Sitzung zu verlieren.
            # Angehalten wird sie von dem, der die Karte wirklich zeigt.
            _log.info("survey is due after %d minutes of work", int(progress.used_seconds // 60))
            self.due.emit()


#: Wie breit die Karte höchstens wird. Ein Streifen über die volle Fensterbreite
#: verdeckt genau das, worüber der Kunde gerade nachdenkt; zwei Sätze brauchen
#: nicht mehr als das hier.
NOTICE_WIDTH = 520

#: Wie weit von oben. Dieselbe Zahl wie beim Vorschaubanner
#: (``viewport.BANNER_TOP``) — zwei Karten an derselben Stelle sollen an
#: derselben Stelle stehen, und wo sie zusammentreffen, weicht diese nach
#: unten aus.
NOTICE_TOP = 12


class SurveyNotice(QFrame):
    """Die Frage, ob der Kunde gefragt werden möchte — über der Ansicht.

    **Nicht modal, und das ist der ganze Punkt.** Der Update-Hinweis kommt
    beim Start, dieser mitten in die Arbeit: Ein Fenster, das dort alles
    anhält, wird weggeklickt, ohne gelesen zu werden, und die Rückmeldung, die
    es holen sollte, ist damit verloren. Die Karte steht daneben, sie hält
    nichts an, und sie verschwindet **nicht von selbst** — sie bleibt, bis
    jemand einen der beiden Knöpfe drückt.

    Sie liegt über der Ansicht und nicht in der Statuszeile: Eine Zeile, die
    die nächste Meldung überschreibt, ist für eine Frage der falsche Ort.
    Weicht dem Vorschaubanner aus, wenn beide zugleich dastehen — zwei Karten
    übereinander sind eine unlesbare Karte.
    """

    accepted = Signal()
    """*Rückmeldung geben* — das Fenster öffnet den Bogen."""

    declined = Signal()
    """*Nein danke*. Eine Antwort, und sie gilt dauerhaft."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("surveyNotice")
        # **Fest und nicht „höchstens".** Mit einer Obergrenze nahm
        # ``adjustSize`` die *kleinste* Breite, bei der der Text noch umbricht:
        # 257 Punkte, vier Zeilen Fließtext — und der Hauptknopf daneben wurde
        # so schmal, dass seine Beschriftung vollständig verschwand. Ein Knopf
        # ohne Wort ist keine Handlung mehr, sondern ein Rätsel.
        self.setFixedWidth(NOTICE_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        layout.setSpacing(SPACE)

        self.title = QLabel(str(feedback.INVITATION_TITLE), self)
        self.title.setObjectName("surveyTitle")
        self.title.setWordWrap(True)
        self.body = QLabel(str(feedback.INVITATION_BODY), self)
        self.body.setWordWrap(True)

        self.give = QPushButton(str(feedback.INVITATION_ACCEPT), self)
        self.give.setObjectName("surveyGive")
        make_primary(self.give)
        self.give.clicked.connect(self._accept)
        self.no = QPushButton(str(feedback.INVITATION_DECLINE), self)
        self.no.clicked.connect(self._decline)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE)
        buttons.addStretch(1)
        buttons.addWidget(self.no)
        buttons.addWidget(self.give)

        layout.addWidget(self.title)
        layout.addWidget(self.body)
        layout.addLayout(buttons)

        self.set_theme("dark")
        self.hide()
        if parent is not None:
            # Der eigene Filter statt einer Zeile im ``resizeEvent`` der
            # Ansicht: Die Karte weiß selbst, wo sie hingehört, und wer sie
            # anderswo einhängt, muss dort nichts nachtragen.
            parent.installEventFilter(self)

    def set_theme(self, theme: str) -> None:
        """Farben aus dem Thema — die Karte liegt auf beiden Hintergründen.

        Der Rahmen ist durchgezogen und trägt die Akzentfarbe: Anders als
        beim Vorschaubanner ist hier nichts vorläufig, sondern etwas gefragt.
        Die zweite Kodierung (Regel 18) ist die halbfette Überschrift — die
        Karte sagt in Worten, was sie ist, und hinge nie an ihrer Farbe.
        """
        colours = THEMES["light" if theme == "light" else "dark"]
        self.setStyleSheet(
            f"#surveyNotice {{ background: {colours['window']};"
            f" border: 1px solid {colours['highlight']}; border-radius: 6px; }}"
            f"#surveyNotice QLabel {{ color: {colours['text']}; background: transparent; }}"
            f"#surveyNotice #surveyTitle {{ font-weight: 600; }}"
            # **Der Hauptknopf trägt seine Farben hier und nicht aus dem
            # Anwendungs-Stylesheet.** Dort hängen sie an ``QPushButton:default``,
            # und diese Regel verliert jeder Knopf, über dem ein **typloses**
            # Stylesheet liegt — eine Zeile wie ``background: …`` ohne Selektor
            # gilt für alle Nachkommen und ersetzt dort die Regeln der
            # Anwendung. Der Knopf stand deshalb mit Rahmen und ohne lesbare
            # Beschriftung da. Die Regel oben ist mit Kennung geschrieben und
            # trifft nur ihr Ziel; ``make_primary`` bleibt, denn es rechnet die
            # Breite gegen die halbfette Schrift.
            f"#surveyNotice #surveyGive {{ background: {colours['highlight']};"
            f" color: {colours['highlight_text']}; border: 1px solid {colours['highlight']}; }}"
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt gibt den Namen
        """Bleibt an seinem Platz, wenn das Fenster seine Größe ändert."""
        if stop_watching_the_dying(self, watched, event):
            return False
        if event.type() == QEvent.Type.Resize and watched is self.parentWidget():
            self.place()
        return super().eventFilter(watched, event)

    def _accept(self) -> None:
        self.hide()
        self.accepted.emit()

    def _decline(self) -> None:
        self.hide()
        feedback.mark_declined()
        self.declined.emit()

    def ask(self) -> None:
        """Zeigt die Karte und zählt die Einladung.

        Gezählt wird **hier** und nicht, wenn die Uhr sich meldet: Eine
        Einladung, die niemand gesehen hat, soll keine der drei verbrauchen.
        """
        self.show()
        self.adjustSize()
        self.place()
        self.raise_()
        feedback.mark_invited()

    def place(self) -> None:
        """Oben mittig — und unter dem Vorschaubanner, wenn das dasteht."""
        parent = self.parentWidget()
        if parent is None:
            return
        top = NOTICE_TOP
        banner = getattr(parent, "banner", None)
        if banner is not None and banner.isVisible():
            top = banner.geometry().bottom() + ROOMY
        self.move(max((parent.width() - self.width()) // 2, 0), top)
