"""Der Bogen im Rückmeldungsdialog (§37.2) und die zwei Einladungen über der Ansicht.

Kein eigenes Fenster und kein eigener Sendeknopf: Was hier steht, ist der
obere Teil von :class:`app.ui.support_dialog.SupportDialog`, wenn er als
Bogen geöffnet wird. Der Grund steht in :mod:`app.core.feedback` und ist die
Grenze zur verbotenen Telemetrie — **es gibt genau einen Weg hinaus**, und
einen zweiten zu bauen, nur weil er bequemer wäre, hieße sie aufzugeben.

Die Fragen selbst stehen nicht hier, sondern im Kern. Diese Datei zeigt sie
an und sammelt die Antworten ein; was gefragt wird, ist eine Entscheidung
über das Produkt und keine über ein Widget.

Dazu die beiden Einladungen, die je Version einmal über der Ansicht stehen:
die Frage nach einer Rückmeldung (:class:`SurveyNotice`) und die Zeile zur
freiwilligen Unterstützung (:class:`SupportNotice`). Beide sind
:class:`ViewNotice` — derselbe Ort oben mittig, dieselbe ruhige Kante und
dieselbe Regel, wie sie einander und dem Vorschauband ausweichen. Zwei
Karten, die das je für sich regelten, lägen beim ersten Zusammentreffen
übereinander.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core import feedback
from app.core.log import get_logger
from app.ui import app_events
from app.ui.icons import icon
from app.ui.leash import stop_watching_the_dying
from app.ui.style import NORMAL, ROOMY, SPACE, TIGHT, make_primary
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
        if not self._watching and app_events.listen(self, WORK_EVENTS):
            self._watching = True
        self._timer.start()

    def running(self) -> bool:
        """Ob noch gezählt wird. Das Fenster fragt danach, wenn es aufräumt —
        und ein Test, statt in den Zeitgeber zu greifen."""
        return self._timer.isActive()

    def stop(self) -> None:
        """Hält an und hängt sich wieder aus."""
        self._timer.stop()
        if self._watching:
            app_events.forget(self)
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

#: Wie schmal die Rückfragekarte höchstens werden darf, bevor sie lieber oben
#: in der Mitte steht. Schmaler als ihre zwei Knöpfe nebeneinander wird sie
#: ohnehin nie (:meth:`SurveyNotice.width_for`).
NOTICE_MIN_WIDTH = 240

#: Wie weit von oben. Dieselbe Zahl wie beim Vorschaubanner
#: (``viewport.BANNER_TOP``) — zwei Karten an derselben Stelle sollen an
#: derselben Stelle stehen, und wo sie zusammentreffen, weicht diese nach
#: unten aus.
NOTICE_TOP = 12

#: Wie breit die Zeile zur Unterstützung höchstens und mindestens wird. Breit
#: genug für den Satz in einer Zeile neben Knopf und Kreuz, schmal genug, um
#: zwischen linker und rechter Karte zu bleiben. Wird der freie Raum kleiner,
#: bricht der Satz um, statt unter eine Karte zu rutschen.
SUPPORT_WIDTH = 720
SUPPORT_MIN_WIDTH = 300

#: Was unten frei bleibt: das Achsenkreuz der Ansicht (``ORIENTATION_SIZE``
#: samt Rand in ``viewport.py``) sitzt links unten und ist kein Widget, dem
#: man ausweichen könnte — also bleibt der Streifen darüber frei.
BOTTOM_ROOM = 64


class ViewNotice(QFrame):
    """Eine Einladung über der Ansicht: oben mittig, und nie über einer anderen.

    **Oben mittig, weil unten alles belegt ist.** Unten mittig sitzt die
    Werkzeugzeile der Karten, unten links das Achsenkreuz, unten rechts die
    Ansichtsleiste; die Statuszeile trägt nach einem Export gerade dann
    *Ordner zeigen* und das Band der Wartezeit. Oben steht nur, was flüchtig
    ist — das Vorschauband und die Ziehwert-Leiste —, und dem weicht die
    Einladung nach unten aus, statt es zu verdecken.

    **Zwischen den Karten, nicht unter ihnen.** Die schwebenden Karten liegen
    über der Ansicht, und eine Einladung darunter ist nicht zu sehen — gemessen
    an einem 1024 Punkte breiten Fenster: Zwischen Objektbaum und Prüfbericht
    blieben 101 Punkte, und die Zeile lag vollständig unter beiden. Gesucht
    wird deshalb die oberste freie Stelle, die keine gemeldete Karte
    (:meth:`keep_clear_of`) berührt: zuerst oben zwischen den Karten, sonst
    unter der kürzeren von beiden in ihrer Spalte, über Werkzeugzeile und
    Ansichtsleiste. Erst wenn das Fenster nirgends Platz hat, steht sie oben
    in der Mitte — eine Einladung außerhalb des Bildes sähe niemand.

    Nicht modal, kein Fokus beim Erscheinen, und sie verschwindet **nicht von
    selbst** — sie bleibt, bis jemand einen ihrer Knöpfe drückt.
    """

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(name)
        self._clear_of: list[QWidget] = []
        self.hide()
        if parent is not None:
            # Der eigene Filter statt einer Zeile im ``resizeEvent`` der
            # Ansicht: Die Karte weiß selbst, wo sie hingehört, und wer sie
            # anderswo einhängt, muss dort nichts nachtragen.
            parent.installEventFilter(self)
            for attribute in ("banner", "drag_bar"):
                obstacle = getattr(parent, attribute, None)
                if isinstance(obstacle, QWidget):
                    self.keep_clear_of(obstacle)

    def keep_clear_of(self, other: QWidget) -> None:
        """Dieser Karte weicht die Einladung aus — und rückt nach, wenn sie geht."""
        if other is self or other in self._clear_of:
            return
        self._clear_of.append(other)
        other.installEventFilter(self)

    def card_rules(self, theme: str) -> str:
        """Fläche, Kante und Schrift der Karte — für beide Einladungen dieselben.

        **Die Kante trägt die Linienfarbe, nicht den Akzent.** Eine Karte ist
        eine Fläche und keine Aufforderung; dass sie eine Karte ist, sagt ihre
        Kante auch in Grau. Den Akzent trägt höchstens ein Knopf darin.

        Hier stand einmal Bernstein, und die Karte war damit eine von vier
        Stellen, die leuchteten, **ohne** dass der Kunde etwas getan hatte (B6
        der Design-Durchsicht). Vier Dauerleuchten machen aus einem Signal eine
        Tapete; die Begründung steht in
        ``konzepte/konzept-akzentfarben-haushalt-2026-08.md``.

        Mit Kennung geschrieben und nie typlos: Eine Regel ohne Selektor gälte
        für jeden Knopf darin und nähme ihm die Farben des Anwendungs-
        Stylesheets (`fenster.md`, „Ein typloses Stylesheet am Vorfahren").
        """
        colours = THEMES["light" if theme == "light" else "dark"]
        name = self.objectName()
        return (
            f"#{name} {{ background: {colours['window']};"
            f" border: 1px solid {colours['line']}; border-radius: 6px; }}"
            f"#{name} QLabel {{ color: {colours['text']}; background: transparent; }}"
        )

    def set_theme(self, theme: str) -> None:
        """Farben aus dem Thema — die Karte liegt auf beiden Hintergründen."""
        self.setStyleSheet(self.card_rules(theme))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt gibt den Namen
        """Bleibt an ihrem Platz, wenn die Ansicht ihre Größe ändert oder eine
        andere Karte oben erscheint, wächst oder geht."""
        if stop_watching_the_dying(self, watched, event):
            if watched in self._clear_of:
                self._clear_of.remove(watched)
            return False
        kind = event.type()
        if watched is self.parentWidget():
            if kind == QEvent.Type.Resize and self.isVisible():
                self.place()
        elif (
            watched in self._clear_of
            and kind in (QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.Move, QEvent.Type.Resize)
            and self.isVisible()
        ):
            self.place()
        return super().eventFilter(watched, event)

    def width_for(self, room: int) -> int | None:
        """Wie breit die Karte in einem freien Streifen von ``room`` Punkten wird —
        oder ``None``, wenn sie dort nicht hineinpasst. Die Rückfragekarte hält
        ihre feste Breite."""
        return self.width() if room >= self.width() + 2 * ROOMY else None

    def height_for(self, width: int) -> int:
        """Wie hoch die Karte bei dieser Breite wird — samt ihrer Kante.

        Über die Frage an das Widget und nicht an sein Layout: Die Kante aus
        dem Stylesheet nimmt dem Inhalt oben und unten je einen Punkt, und das
        Layout allein rechnete ohne sie. Gemessen an der Zeile zur
        Unterstützung: zwei Zeilen Text wollten 32 Punkte und bekamen 30.
        """
        self.ensurePolished()
        layout = self.layout()
        if layout is not None and layout.hasHeightForWidth():
            frame = self.height() - self.contentsRect().height()
            inner = self.width() - self.contentsRect().width()
            wanted = layout.totalHeightForWidth(width - inner) + frame
            return max(wanted, layout.totalMinimumSize().height() + frame)
        return self.sizeHint().height()

    def _obstacles(self) -> list[QRect]:
        """Die sichtbaren Karten, denen ausgewichen wird, in Koordinaten der Ansicht."""
        parent = self.parentWidget()
        if parent is None:
            return []
        found = []
        for other in self._clear_of:
            if not other.isVisible():
                continue
            corner = parent.mapFromGlobal(other.mapToGlobal(QPoint(0, 0)))
            found.append(QRect(corner, other.size()))
        return found

    def spot(self) -> QRect:
        """Die oberste freie Stelle für diese Karte — die Rechnung ohne das Setzen.

        Versucht werden die Höhen, an denen etwas endet: die Oberkante selbst
        und jede Unterkante einer gemeldeten Karte. Auf jeder Höhe zählen die
        freien Streifen zwischen den Karten, die in das Band der Einladung
        ragen; der Streifen, der der Mitte am nächsten liegt, gewinnt. Das Band
        ist so hoch wie die Einladung bei ihrer Breite dort — schmaler heißt
        höher, und dann wird mit dem höheren Band noch einmal gefragt.
        Gerechnet wird nur mit Rechtecken, die schon stehen, nie mit der
        eigenen alten Lage.

        Gibt es keine freie Stelle, steht die Karte oben in der Mitte — dann
        liegt sie unter den Karten (:meth:`has_room` sagt es vorher).
        """
        parent = self.parentWidget()
        if parent is None:
            return self.geometry()
        free = self._free_spot()
        if free is not None:
            return free
        width = parent.width()
        chosen = self.width_for(width) or self.width()
        return QRect(max((width - chosen) // 2, 0), NOTICE_TOP, chosen, self.height_for(chosen))

    def has_room(self) -> bool:
        """Ob es über der Ansicht eine Stelle gibt, an der die Karte zu sehen ist."""
        return self.parentWidget() is not None and self._free_spot() is not None

    def _free_spot(self) -> QRect | None:
        """Die oberste freie Stelle — ``None``, wenn keine Höhe einen Streifen hat."""
        parent = self.parentWidget()
        assert parent is not None
        width, height = parent.width(), parent.height()
        bottom = height - BOTTOM_ROOM
        obstacles = self._obstacles()
        heights = sorted({NOTICE_TOP, *(area.bottom() + 1 + ROOMY for area in obstacles)})
        centre = width / 2
        widest = self.width_for(width) or self.width()
        band = self.height_for(widest)
        for top in heights:
            if top + band > bottom:
                break
            best: QRect | None = None
            reach = band
            # Höchstens drei Anläufe: einzeilig, zweizeilig, dreizeilig.
            for _attempt in range(3):
                taller = reach
                for left, right in self._free_spans(obstacles, top, top + reach, width):
                    chosen = self.width_for(right - left)
                    if chosen is None:
                        continue
                    tall = self.height_for(chosen)
                    if tall > reach:
                        taller = max(taller, tall)
                        continue
                    # Mittig in der Lücke, nicht in der Ansicht: Die Mitte des
                    # sichtbaren Modells ist die Mitte zwischen den Karten.
                    x = left + (right - left - chosen) // 2
                    candidate = QRect(x, top, chosen, tall)
                    if candidate.bottom() > bottom:
                        continue
                    if best is None or abs(candidate.center().x() - centre) < abs(
                        best.center().x() - centre
                    ):
                        best = candidate
                if best is not None or taller == reach:
                    break
                reach = taller
            if best is not None:
                return best
        return None

    @staticmethod
    def _free_spans(
        obstacles: list[QRect], top: int, bottom: int, width: int
    ) -> list[tuple[int, int]]:
        """Die waagerechten Lücken im Band von ``top`` bis ``bottom``.

        Eine Karte, die in dieses Band ragt, sperrt ihre Spalte; eine Karte
        darüber oder darunter nicht — die Werkzeugzeile unten mittig lässt die
        Mitte oben frei.
        """
        blocked = sorted(
            (area.left(), area.right() + 1)
            for area in obstacles
            if area.bottom() >= top and area.top() <= bottom
        )
        spans = []
        cursor = 0
        for left, right in blocked:
            if left > cursor:
                spans.append((cursor, left))
            cursor = max(cursor, right)
        if cursor < width:
            spans.append((cursor, width))
        return spans

    def place(self) -> None:
        """An die oberste freie Stelle — Breite und Höhe folgen dem Platz dort."""
        if self.parentWidget() is None:
            return
        target = self.spot()
        if target.width() != self.width():
            self.setFixedWidth(target.width())
        if target.height() != self.height():
            self.setFixedHeight(target.height())
        self.move(target.topLeft())


class SurveyNotice(ViewNotice):
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
    """*Nein danke*. Eine Antwort, und sie gilt für diese Version."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("surveyNotice", parent)
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

    def set_theme(self, theme: str) -> None:
        """Farben aus dem Thema — die Karte liegt auf beiden Hintergründen.

        Die zweite Kodierung (Regel 18) ist die halbfette Überschrift — die
        Karte sagt in Worten, was sie ist, und hing nie an ihrer Farbe.
        """
        colours = THEMES["light" if theme == "light" else "dark"]
        self.setStyleSheet(
            self.card_rules(theme)
            + "#surveyNotice #surveyTitle { font-weight: 600; }"
            # **Der Hauptknopf trägt seine Farben hier und nicht aus dem
            # Anwendungs-Stylesheet.** Dort hängen sie an ``QPushButton:default``,
            # und diese Regel verliert jeder Knopf, über dem ein **typloses**
            # Stylesheet liegt — eine Zeile wie ``background: …`` ohne Selektor
            # gilt für alle Nachkommen und ersetzt dort die Regeln der
            # Anwendung. Der Knopf stand deshalb mit Rahmen und ohne lesbare
            # Beschriftung da. Die Regel oben ist mit Kennung geschrieben und
            # trifft nur ihr Ziel; ``make_primary`` bleibt, denn es rechnet die
            # Breite gegen die halbfette Schrift.
            + f"#surveyNotice #surveyGive {{ background: {colours['highlight']};"
            f" color: {colours['highlight_text']}; border: 1px solid {colours['highlight']}; }}"
        )

    def width_for(self, room: int) -> int | None:
        """So breit wie :data:`NOTICE_WIDTH`, schmaler nur, wenn der Streifen es verlangt.

        **Die feste Breite hielt die Karte in einem schmalen Fenster unter den
        Karten** (RM-233): Zwischen Objektbaum und Prüfbericht war kein
        Streifen 520 Punkte breit, also stand sie oben in der Mitte — dort,
        wo die Karten liegen, und darunter nicht zu sehen. Jetzt nimmt sie den
        freien Streifen bis hinunter zu :data:`NOTICE_MIN_WIDTH`; der Text
        bricht um, und die Höhe folgt (:meth:`ViewNotice.height_for`). Nie
        schmaler als die zwei Knöpfe nebeneinander — der Grund, aus dem sie
        überhaupt eine feste Breite bekam: Ein Knopf ohne Wort ist ein Rätsel.
        """
        usable = room - 2 * ROOMY
        least = max(NOTICE_MIN_WIDTH, self._buttons_width())
        if usable < least:
            return None
        return min(NOTICE_WIDTH, usable)

    def _buttons_width(self) -> int:
        """Die Breite, in der beide Knöpfe mit ganzer Beschriftung nebeneinander passen."""
        self.ensurePolished()
        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else None
        sides = margins.left() + margins.right() if margins is not None else 2 * ROOMY
        frame = self.width() - self.contentsRect().width()
        return self.no.sizeHint().width() + SPACE + self.give.sizeHint().width() + sides + frame

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
        Einladung, die niemand gesehen hat, soll diese Version nicht erledigen.
        """
        self.show()
        self.adjustSize()
        self.place()
        self.raise_()
        feedback.mark_invited()


class SupportNotice(ViewNotice):
    """Die eine Zeile zur freiwilligen Unterstützung (Entscheidung Robert, 23.09.2026).

    Sie erscheint einmal je Version nach dem dritten erfolgreichen Export oder
    Slicer-Start — wann, entscheidet :func:`app.core.feedback.support_due`.
    **Eine Zeile und keine Karte mit Überschrift:** ein Herz, ein Satz, ein
    Knopf, ein Kreuz. Sie unterbricht nichts und nimmt keinen Fokus, und ihr
    Knopf öffnet nur den lokalen Dialog; hinaus geht erst dessen Knopf.

    **Ohne Akzent.** Der Hauptknopf eines Fensters ist die Handlung, um die es
    dort geht, und in der Arbeitsfläche ist das nie das Unterstützen. Die
    Zeile bleibt leise: dieselbe Kante wie die Rückfragekarte, der Knopf in
    der Form jedes Nebenknopfs.

    **Zweite Kodierung überall** (Regel 18): Das Herz steht neben einem Satz,
    das Kreuz trägt Namen, Tooltip und Statuszeile („Hinweis schließen"), und
    ein Bildschirmleser findet den Satz als Beschreibung der Zeile und ihres
    Knopfs. Mit der Tabulatortaste ist sie erreichbar, denn sie steht in der
    Fokuskette hinter der Ansicht, auf der sie liegt.
    """

    accepted = Signal()
    """*Unterstützen …* — das Fenster öffnet den Dialog."""

    dismissed = Signal()
    """Das Kreuz. Gilt wie der Klick: In dieser Version kommt sie nicht wieder."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("supportNotice", parent)
        line = str(feedback.SUPPORT_LINE)
        self.setAccessibleName(str(feedback.SUPPORT_ACCEPT).rstrip(" …."))
        self.setAccessibleDescription(line)

        self.heart = QLabel(self)
        self.heart.setObjectName("supportHeart")
        self.heart.setFixedSize(QSize(20, 20))
        self.heart.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text = QLabel(line, self)
        self.text.setObjectName("supportLine")
        self.text.setWordWrap(True)

        self.give = QPushButton(str(feedback.SUPPORT_ACCEPT), self)
        self.give.setObjectName("supportGive")
        self.give.setAutoDefault(False)
        self.give.setAccessibleDescription(line)
        self.give.clicked.connect(self._accept)

        hint = str(feedback.SUPPORT_CLOSE_HINT)
        self.close_button = QToolButton(self)
        self.close_button.setObjectName("supportClose")
        self.close_button.setAccessibleName(str(feedback.SUPPORT_CLOSE))
        self.close_button.setAccessibleDescription(hint)
        self.close_button.setToolTip(hint)
        self.close_button.setStatusTip(hint)
        self.close_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.close_button.clicked.connect(self._dismiss)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(ROOMY, NORMAL, NORMAL, NORMAL)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.heart, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.text, 1)
        layout.addWidget(self.give, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addSpacing(TIGHT)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.set_theme("dark")

    def set_theme(self, theme: str) -> None:
        """Dieselbe ruhige Karte wie die Rückfrage; Herz und Kreuz in der Textfarbe."""
        super().set_theme(theme)
        self.heart.setPixmap(icon("support", self.heart).pixmap(QSize(18, 18)))
        self.close_button.setIcon(icon("cancel", self.close_button))

    def width_for(self, room: int) -> int | None:
        """So breit wie ihr Inhalt in einer Zeile — höchstens so breit, wie der
        freie Streifen erlaubt, und nie breiter als :data:`SUPPORT_WIDTH`.

        Die Höhe folgt der Breite (:meth:`ViewNotice.height_for`): Wird es eng,
        bricht der Satz um, und die Zeile wird zweizeilig, statt Knopf oder
        Kreuz abzuschneiden. Wird es weit, bleibt sie so schmal wie ihr Satz;
        eine Lücke zwischen Satz und Knopf sähe nach einem fehlenden Wort aus.
        """
        usable = room - 2 * ROOMY
        if usable < SUPPORT_MIN_WIDTH:
            return None
        return max(min(SUPPORT_WIDTH, usable, self._natural_width()), SUPPORT_MIN_WIDTH)

    def _natural_width(self) -> int:
        """Die Breite, bei der Herz, Satz, Knopf und Kreuz in eine Zeile passen."""
        self.ensurePolished()
        layout = self.layout()
        margins = layout.contentsMargins() if layout is not None else None
        spacing = layout.spacing() if layout is not None else NORMAL
        frame = self.width() - self.contentsRect().width()
        words = self.text.fontMetrics().horizontalAdvance(self.text.text())
        parts = (
            self.heart.width(),
            words,
            self.give.sizeHint().width(),
            TIGHT,
            self.close_button.sizeHint().width(),
        )
        edges = margins.left() + margins.right() if margins is not None else 0
        # Ein paar Punkte Luft: QLabel rundet beim Umbruch auf ganze Punkte,
        # und ohne sie bräche der Satz genau an seinem letzten Wort um.
        return sum(parts) + spacing * 3 + edges + frame + SPACE

    def _accept(self) -> None:
        self.hide()
        self.accepted.emit()

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()

    def offer(self) -> None:
        """Zeigt die Zeile und merkt sich, dass sie in dieser Version zu sehen war.

        Gemerkt wird beim Zeigen und nicht erst beim Klick: „Geschlossen oder
        geklickt zählt beides als gesehen" (Robert, 23.09.2026), und wer sie
        stehen lässt und das Programm beendet, hat sie ebenso gesehen. Den
        Fokus nimmt sie nicht — wer gerade tippt, tippt weiter.
        """
        self.show()
        self.place()
        self.raise_()
        feedback.mark_support_invited()
