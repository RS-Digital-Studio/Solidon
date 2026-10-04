"""Die Ladeanzeige über der Ansicht (Bauplan §2.8).

Ein Projekt zu öffnen heißt, seinen Operationsstapel von vorn zu rechnen. Bis
das durch ist, gibt es nichts zu zeigen: der Objektbaum ist leer, die Ansicht
ist leer, und die einzige Auskunft darüber, dass überhaupt etwas geschieht,
war ein hundertachtzig Pixel breiter Balken unten rechts in der Statusleiste.
Wer auf die Mitte des Fensters sieht — und dorthin sieht man —, findet ihn
nicht. Das Fenster wirkte hängengeblieben, während es arbeitete.

Diese Anzeige legt sich deshalb dorthin, wo der Blick ohnehin liegt: über die
Ansicht und **unter** die schwebenden Karten. Der Balken unten bleibt, wo er
ist; er ist nicht falsch, er ist nur allein zu wenig.

**Nur wenn nichts zu verdecken ist.** §2.8 verlangt, dass die letzte gültige
Darstellung stehenbleibt — steht ein Modell im Bild, wird nichts darübergelegt,
egal wie lange gerechnet wird. Wer entscheidet das, steht im Hauptfenster
(``_update_veil``); dieses Modul zeigt nur an.

**Deckend, nicht durchscheinend.** Gezeichnet wird der Verlauf der leeren
Ansicht selbst, aus denselben Themenfarben, die der Renderer bekommt. Damit
sieht die Fläche aus wie die Ansicht, in der gleich das Modell steht, statt
wie ein Panel, das sich davorgeschoben hat — und es entsteht kein
halbdurchsichtiges Qt-Widget über einem OpenGL-Fenster, bei dem am Ende die
Fensterfarbe durchscheint statt der Ansicht.

Das Bild ist dasselbe wie beim Start: das Anwendungssymbol wird gedruckt,
Schicht um Schicht, mit dem Druckkopf an der Aufbaukante
(``icons.paint_printed_mark``). Zwei Wartezeiten, eine Sprache.
"""

from __future__ import annotations

import time
from typing import Literal

from PySide6.QtCore import QByteArray, QObject, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton, QWidget

from app.i18n import format_decimal, tr
from app.ui.icons import application_icon_source, paint_printed_mark
from app.ui.motion import EASING, FRAME_MS, animations_enabled
from app.ui.style import ROOMY, WIDE
from app.ui.theme import THEMES, Theme

#: Wie lange ein Lauf dauern muss, bevor die Anzeige kommt.
#:
#: §2.8 sagt „unter 0,2 s nichts". Ein leeres Projekt ist in Millisekunden
#: gerechnet, und eine Anzeige, die dabei aufblitzt, ist Unruhe ohne Auskunft.
DELAY_MS = 200

#: Ab wann Fortschrittsbalken und Abbrechen erscheinen (Bauplan §2.8).
#:
#: Die Stufe darunter zeigt Zeiger und Statuszeile; erst darüber will man
#: wissen, wie weit es ist. Die Zahl steht hier und nicht im Fenster, weil sie
#: dieselbe Tabelle beantwortet wie ``DELAY_MS`` darüber — zwei Schwellen einer
#: Zusage, an zwei Orten gepflegt, laufen auseinander.
BAR_AFTER_MS = 2000

#: Ab wann eine Wartezeit eine Schätzung bekommt (Bauplan §2.8).
#:
#: Vorher wäre sie geraten: Die ersten Sekunden eines Laufs sagen wenig über
#: seinen Rest, weil der Anfang oft billiger ist als die Mitte. Eine Zahl, die
#: erst „noch 40 Sekunden" und dann „noch zwei Minuten" sagt, ist schlechter
#: als keine.
ESTIMATE_AFTER_S = 10.0

#: Wie weit ein Lauf sein muss, bevor aus ihm hochgerechnet wird. Bei drei
#: Prozent ist der Hochrechnungsfehler größer als die Aussage.
ESTIMATE_FROM = 0.08

#: Kantenlänge des gezeichneten Symbols.
#:
#: Größer als auf dem Ladebildschirm im Verhältnis zu dessen Karte: dort steht
#: es auf 460 mal 300 Pixeln, hier auf dem ganzen Fenster. Bei 96 war es ein
#: Fleck in der Mitte einer leeren Fläche — nachgesehen, nicht geschätzt.
MARK_SIZE = 140

#: Deckkraft des noch nicht Gedruckten. Genug, um die Form zu erkennen, zu
#: wenig, um sie mit dem fertigen Teil zu verwechseln — sonst wäre der
#: Fortschritt nicht mehr abzulesen.
GHOST = 0.16

#: Breite der Textspalte unter dem Symbol. Breit genug für den Titel einer
#: Operation, schmal genug, dass der Block als Block gelesen wird.
COLUMN = 360

#: Abstand zwischen den Teilen des Blocks.
GAP = ROOMY * 2

#: Höhen der Teile unter dem Symbol.
HEADLINE_HEIGHT = 26
RAIL_HEIGHT = 3
DETAIL_HEIGHT = 20
BUTTON_HEIGHT = 28

#: Wie hoch der ganze Block ist — gebraucht, um ihn mittig zu setzen, bevor
#: irgendetwas davon gezeichnet ist.
BLOCK_HEIGHT = (
    MARK_SIZE
    + GAP
    + HEADLINE_HEIGHT
    + GAP
    + RAIL_HEIGHT
    + ROOMY
    + DETAIL_HEIGHT
    + ROOMY
    + DETAIL_HEIGHT
    + GAP
    + BUTTON_HEIGHT
)


def remaining_time(
    started: float | None, fraction: float, *, now: float | None = None, since: float = 0.0
) -> str:
    """Was von einer Wartezeit noch aussteht — leer, solange es geraten wäre.

    §2.8 verlangt die Schätzung erst über zehn Sekunden, und das ist keine
    Willkür: Die ersten Sekunden eines Laufs sagen wenig über seinen Rest.
    Aus verstrichener Zeit und Anteil hochgerechnet, linear — genauer geht es
    nicht, denn wie viel Arbeit hinter den nächsten Prozent steckt, weiß nur
    die Operation selbst.

    **Freie Funktion und keine Methode**, weil sie an zwei Orten gebraucht
    wird und lange nur an einem stand: Sie gehörte dem Ladeschleier, und den
    gibt es nur bei **leerem** Bild. Steht ein Körper da — bei jeder langen
    Rechnung an einem geladenen Modell also —, bleibt allein die Statusleiste,
    und die zeigte Prozent ohne jede Zeitangabe. Die Zeile aus §2.8, die es
    über zehn Sekunden verlangt, galt damit für genau den Fall nicht, für den
    sie geschrieben ist.

    ``since`` ist der Anteil, der zu ``started`` bereits erreicht war. Für die
    Rate zählt nur der seither hinzugekommene Anteil
    (``fraction - since``), nicht eine Spanne mit anderem Anfang. Die Uhr in
    ``ProgressTiming`` verschiebt ``started`` um Antwortpausen; diese Zeit geht
    nicht in die Restschätzung ein.
    """
    if started is None or fraction < ESTIMATE_FROM or fraction - since <= 0.0:
        return ""
    passed = (time.monotonic() if now is None else now) - started
    if passed < ESTIMATE_AFTER_S:
        return ""
    left = passed * (1.0 - fraction) / (fraction - since)
    if left < 5.0:
        return tr("gleich fertig")
    if left < 90.0:
        return tr("noch etwa {seconds} s").format(seconds=round(left / 5.0) * 5)
    return tr("noch etwa {minutes} min").format(minutes=round(left / 60.0))


def elapsed_time(started: float, *, now: float | None = None) -> str:
    """Verstrichene Zeit bleibt auch bei langen Läufen sekundengenau lesbar."""
    passed = (time.monotonic() if now is None else now) - started
    minutes, seconds = divmod(int(max(0.0, passed)), 60)
    if minutes:
        return tr("Verstrichen: {minutes} min {seconds} s").format(
            minutes=format_decimal(minutes, 0), seconds=format_decimal(seconds, 0)
        )
    return tr("Verstrichen: {seconds} s").format(seconds=format_decimal(seconds, 0))


def veil_reason(*, busy: bool, bodies: bool, preparing: bool) -> Literal["", "view", "run"]:
    """Wofür die Ladeanzeige steht: für einen Lauf, für das Bild oder gar nicht.

    ``bodies`` heißt, das Ergebnis hat Körper; ``preparing``, dass die Ansicht
    noch nichts zeigt und ihr Arbeiter das erste Bild vorbereitet. **Gelesen
    ist nicht gezeigt:** Am Mausoleum-Drachen stand die Ansicht sonst
    sechseinhalb Sekunden leer und ohne Wort (Fensterabnahme RM-366).
    """
    if preparing and (bodies or not busy):
        return "view"
    if busy and not bodies:
        return "run"
    return ""


class ProgressTiming(QObject):
    """Eine Uhr und eine Zeitangabe für Schleier und Statuszeile.

    Der Sekundentakt gehört zum laufenden Vorgang, unabhängig von dessen
    Fortschrittsmeldungen und von Animationen. Antwortzeit zählt als
    verstrichen, geht aber nicht in die Hochrechnung der Rechenzeit ein.

    **Die verstrichene Zeit gehört dem Vorgang, die Restschätzung der
    Teilrechnung.** Ein Vorgang besteht aus mehreren Rechnungen, die ihren
    Anteil je von vorn zählen — Einleseplan, Auswertung, darin das
    Normalisieren und die Erkennung. Beginnt der Anteil wieder kleiner, beginnt
    eine neue, und hochgerechnet wird nur ihre eigene Zeit.

    **Und eine Rechnung, die bei null stand, gibt ihre Zeit nicht weiter.**
    Meldet eine Zeile ihren Anfang bei 0 % und nie mehr, und die nächste Zeile
    kommt gleich mit 20 %, sinkt der Anteil nicht — die Zeit der ersten Zeile
    ging trotzdem in die Hochrechnung der zweiten ein. Gemessen am
    Mausoleum-Drachen: 16 s „Modell einfügen · 0 %“, dann „Punkte
    verschweißen · 20 %“ mit „noch etwa 70 s“ und zwei Sekunden später
    „noch etwa 15 s“ (Durchsicht 0.5.1). Wechselt die Zeile, während der
    Anteil noch bei null stand, zählt die Schätzung deshalb ab dem ersten
    gemessenen Anteil der neuen Zeile, und hochgerechnet wird nur, was seitdem
    dazukam.
    """

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.started: float | None = None
        self.fraction = 0.0
        self.detail = ""
        self.time_text = ""
        self._waiting_since: float | None = None
        self._waited = 0.0
        """Antwortzeit der laufenden Teilrechnung — sie zählt nicht als Rechenzeit."""
        self._moved_at: float | None = None
        """Wann der gemessene Anteil zuletzt gewachsen ist."""
        self._counted_from: float | None = None
        """Seit wann der Anteil der laufenden Teilrechnung zählt.

        Grundlage der Restschätzung. Aus dem Anfang des ganzen Vorgangs
        hochgerechnet, ergäben eine Minute Einleseplan und danach zehn Prozent
        Auswertung „noch etwa 9 min" (60 s · 0,9 / 0,1), gleich wie kurz die
        Auswertung wirklich ist."""
        self._counted_fraction = 0.0
        """Der Anteil, bei dem die Zählung der laufenden Teilrechnung begann."""
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self.refresh)

    def begin(self) -> None:
        """Startet eine neue Uhr; ein laufender Vorgang behält seinen Anfang."""
        if self.started is not None:
            return
        self.started = time.monotonic()
        self.fraction = 0.0
        self.detail = ""
        self._waiting_since = None
        self._waited = 0.0
        self._moved_at = self.started
        self._counted_from = self.started
        self._counted_fraction = 0.0
        self._tick.start()
        self.refresh()

    def step(self, fraction: float, detail: str) -> None:
        """Übernimmt gemessenen Fortschritt; die Uhr erfindet keinen Anteil."""
        self.begin()
        fraction = max(0.0, min(1.0, fraction))
        now = time.monotonic()
        # Die vorige Zeile stand bei null und ist vorbei: Ihre Zeit war keine
        # Rechnung an diesem Anteil (siehe Klassenbeschreibung). Gezählt wird
        # ab dem ersten gemessenen Anteil der neuen Zeile.
        after_zero = self.fraction <= 0.0 < fraction and bool(self.detail) and detail != self.detail
        if fraction > self.fraction:
            self._moved_at = now
        if fraction < self.fraction or after_zero:
            # Ein kleinerer Anteil beginnt eine neue Teilrechnung: Ihre
            # Schätzung zählt ab hier, die verstrichene Zeit läuft weiter.
            self._counted_from = now
            self._counted_fraction = fraction if after_zero else 0.0
            self._waited = 0.0
            if self._waiting_since is not None:
                self._waiting_since = now
        self.fraction = fraction
        self.detail = detail
        self.refresh()

    def set_waiting(self, waiting: bool) -> None:
        """Eine Kernfrage hält die Restschätzung an, nicht die verstrichene Zeit."""
        now = time.monotonic()
        if waiting and self._waiting_since is None:
            self._waiting_since = now
        elif not waiting and self._waiting_since is not None:
            self._waited += now - self._waiting_since
            # Die Antwortzeit ist kein Stillstand der Rechnung.
            if self._moved_at is not None:
                self._moved_at += now - self._waiting_since
            self._waiting_since = None
        self.refresh()

    def remaining(self, *, now: float | None = None) -> str:
        """Nur tatsächlich gerechnete Zeit wird auf den Rest hochgerechnet."""
        if self.started is None or self._waiting_since is not None:
            return ""
        # **Pausen ohne Fortschrittsanteil zählen nicht als Rechenzeit.** Bei
        # einer offenen Kernfrage wird die Antwortzeit separat gesammelt und
        # aus der Hochrechnung herausgerechnet; steht der Anteil anderweitig,
        # verwirft die Altersprüfung unten die veraltete Rate.
        moment = time.monotonic() if now is None else now
        if self._moved_at is not None and moment - self._moved_at > ESTIMATE_AFTER_S:
            return ""
        counted_from = self.started if self._counted_from is None else self._counted_from
        return remaining_time(
            counted_from + self._waited, self.fraction, now=now, since=self._counted_fraction
        )

    def refresh(self) -> None:
        """Meldet dieselbe Zeitangabe auch ohne neue Fortschrittsmessung."""
        if self.started is None:
            return
        now = time.monotonic()
        elapsed = elapsed_time(self.started, now=now)
        remaining = self.remaining(now=now)
        self.time_text = f"{elapsed}  ·  {remaining}" if remaining else elapsed
        self.changed.emit()

    def end(self) -> None:
        """Beendet den Takt auch bei Abbruch, Fehler und Fensterabbau."""
        self._tick.stop()
        self.started = None
        self.time_text = ""
        self._waiting_since = None
        self._waited = 0.0
        self._counted_from = None
        self._counted_fraction = 0.0


class LoadingVeil(QWidget):
    """Was über der Ansicht steht, solange sie nichts zeigen kann.

    Drei Kodierungen für denselben Fortschritt, weil Regel 18 auch für eine
    Wartezeit gilt: die Bauhöhe des Symbols, die Länge der Linie darunter und
    die Zahl daneben. Wer die eine nicht liest, liest die andere.
    """

    cancelRequested = Signal()
    """Der Knopf wurde gedrückt. Was abgebrochen wird, weiß das Hauptfenster."""

    appeared = Signal()
    """Die Anzeige steht wirklich — erst jetzt, nicht schon bei ``begin``.

    Das Hauptfenster verbirgt daraufhin die Ansicht. Verdecken allein reicht
    nicht: Das Ansichtsfenster ist ein natives Fenster (die Grafikfläche des
    Renderers), und ein natives Kind liegt auf dem Bildschirm über jedem
    gemalten Geschwister, egal was die Qt-Stapelung sagt. Solange es gezeigt
    und noch nie gerendert ist,
    stehen dort alte Pixel — beim Öffnen von Weg 1 sechs Sekunden lang der
    Startbildschirm bzw. Schwarz, und Robert hielt es zweimal für einen
    Absturz, während dieser Schleier unsichtbar darunter lag."""

    ended = Signal()
    """Die Anzeige ist weg — die Ansicht darf zurückkommen.

    Gesendet nur, wenn sie wirklich stand: ``end`` läuft nach jedem Lauf,
    auch wenn die Verzögerung die Anzeige nie hat erscheinen lassen."""

    def __init__(
        self, parent: QWidget | None = None, *, timing: ProgressTiming | None = None
    ) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(QByteArray(application_icon_source().encode("utf-8")))
        self._theme: Theme = "dark"
        self._headline = ""
        self._detail = ""
        #: Ob ein Lauf hinter der Anzeige steht (``begin(running=…)``).
        self._running = True
        self._owns_timing = timing is None
        self.timing = timing if timing is not None else ProgressTiming(self)
        self.timing.changed.connect(self._timing_changed)
        self._target = 0.0
        """Der gemessene Anteil — was die Zahl sagt."""
        self._shown = 0.0
        """Der gezeigte Anteil — was das Symbol zeigt, auf dem Weg dorthin."""

        # §2.8: über zwei Sekunden gehört ein Abbrechen dazu. Er steht hier und
        # nicht nur unten in der Statusleiste, weil hier hinsieht, wer wartet.
        self.cancel = QPushButton(tr("Abbrechen"), self)
        self.cancel.clicked.connect(self.cancelRequested)

        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.timeout.connect(self._appear)

        self._frames = QTimer(self)
        self._frames.setInterval(FRAME_MS)
        self._frames.timeout.connect(self._advance)

        # **Der Schleier deckt, was unter ihm liegt** — der Verlauf füllt jedes
        # Pixel. Ohne diese Angabe malte Qt bei jedem Neuzeichnen zuerst das
        # ganze Fenster darunter, Tafeln und Baum eingeschlossen (RM-258).
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.hide()

    # --- Zustand ---------------------------------------------------------

    @property
    def showing(self) -> bool:
        """Ob die Anzeige steht.

        Nicht ``isVisible``: das ist falsch, solange kein Fenster offen ist —
        offscreen also immer, und ein Test darauf prüfte nie etwas.
        """
        return not self.isHidden()

    def set_theme(self, theme: str) -> None:
        """Hintergrundverlauf und Schriftfarbe folgen dem Anwendungsthema."""
        if theme in THEMES:
            self._theme = theme
            self.update()

    def begin(self, headline: str, at_once: bool = False, *, running: bool = True) -> None:
        """Ein Lauf hat begonnen — die Anzeige kommt, wenn er dauert.

        Mehrfach aufzurufen ist gefahrlos: der zweite Aufruf schreibt nur die
        Überschrift um und lässt eine laufende Verzögerung laufen.

        ``at_once`` überspringt die Verzögerung. Sie schützt vor einem
        Aufblitzen bei Läufen unter 200 ms — beim Öffnen eines Projekts mit
        Schritten ist die Wartezeit aber sicher, und jede unbedeckte
        Millisekunde gehört dem nativen Ansichtsfenster mit seinen alten
        Pixeln (siehe ``appeared``). Dort muss die Anzeige vor dem ersten
        Bild stehen, nicht 200 ms danach.

        ``running=False``: Hinter der Anzeige rechnet kein Lauf mehr, die
        Ansicht bereitet nur ihr erstes Bild vor. Dann gibt es nichts
        abzubrechen und keinen Anteil zu zeigen — Linie, Schrittzeile und
        *Abbrechen* fallen weg, statt den letzten Stand des Laufs stehen zu
        lassen („Merkmale erkennen 0 %“).
        """
        self._headline = headline
        # Was ein Bildschirmleser vorliest. Der Text hier ist gemalt und kein
        # Label — ohne das wäre die Fläche für ihn stumm.
        self.setAccessibleName(headline)
        self._running = running
        self.cancel.setVisible(running)
        if self.showing:
            self.update()
            return
        if self._delay.isActive():
            if at_once:
                self._delay.stop()
                self._appear()
            else:
                self.update()
            return
        self._detail = ""
        self._target = 0.0
        self._shown = 0.0
        self.timing.begin()
        self._timing_changed()
        if at_once or not animations_enabled():
            # Offscreen sieht niemand ein Aufblitzen, und ein Test, der auf
            # einen Zeitgeber wartet, prüft die Uhr statt das Verhalten.
            self._appear()
            return
        self._delay.start(DELAY_MS)

    def remaining(self) -> str:
        """Was von der Wartezeit noch aussteht — leer, solange es geraten wäre."""
        return self.timing.remaining()

    def step(self, fraction: float, detail: str) -> None:
        """Wie weit der Lauf ist und woran er gerade rechnet."""
        self.timing.step(fraction, detail)

    def _timing_changed(self) -> None:
        """Zeittext und gemessener Anteil kommen gemeinsam von der laufenden Uhr."""
        self._target = self.timing.fraction
        self._detail = self.timing.detail
        description = "  ·  ".join(
            part
            for part in (self._detail, f"{round(self._target * 100)} %", self.timing.time_text)
            if part
        )
        if self.accessibleDescription() != description:
            self.setAccessibleDescription(description)
        if not self.showing:
            return
        if not animations_enabled():
            self._shown = self._target
        self.update(self._block_rect())

    def end(self) -> None:
        """Der Lauf ist vorbei — auch, wenn die Anzeige nie kam."""
        stood = self.showing
        self._delay.stop()
        self._frames.stop()
        if self._owns_timing:
            self.timing.end()
        self.hide()
        if stood:
            self.ended.emit()

    def _appear(self) -> None:
        # Kein ``raise_``: die Stapelung setzt ``OverlayHost.set_veil`` einmal,
        # und sie ist der ganze Punkt — über der Ansicht, unter den Karten.
        # Hier gehoben, lag der Schleier über der Werkzeugzeile.
        self.show()
        self._place_button()
        if animations_enabled():
            self._frames.start()
        else:
            self._shown = self._target
        self.update()
        self.appeared.emit()

    def _advance(self) -> None:
        """Ein Bild weiter auf dem Weg zur gemessenen Höhe."""
        if abs(self._target - self._shown) < 0.002:
            self._shown = self._target
            return
        self._shown += (self._target - self._shown) * EASING
        self.update(self._block_rect())

    # --- Anordnung -------------------------------------------------------

    def resizeEvent(self, event: object) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._place_button()

    def _block_top(self) -> float:
        """Wo der Block anfängt — mittig, solange er hineinpasst."""
        return max((self.height() - BLOCK_HEIGHT) / 2.0, float(WIDE))

    def _column(self) -> QRectF:
        """Die Spalte, in der Überschrift, Linie und Text stehen."""
        width = min(float(COLUMN), max(self.width() - 2.0 * WIDE, 1.0))
        return QRectF((self.width() - width) / 2.0, 0.0, width, 0.0)

    def _block_rect(self) -> QRect:
        """Was Sekundentakt und Fortschritt neu malen: der Block, nicht die Fläche.

        **Ein Neuzeichnen kostet neben einem rechnenden Arbeiter je Widget einen
        Griff nach dem GIL** (``leash.GIL_SWITCH_S``). Mit dem ganzen Schleier
        malte der Sekundentakt jedes Mal das ganze Fenster — rund fünfzig
        Widgets, am Mausoleum-Drachen stand der Qt-Takt dabei bis 2 s
        (``konzepte/nachweise-release-0.5.1/sonden/3mf/p01_nativ.py``). Symbol,
        Überschrift, Linie und die beiden
        Textzeilen liegen in diesem Rechteck; der Verlauf darum ändert sich nie.
        """
        width = max(self._column().width(), float(MARK_SIZE))
        left = (self.width() - width) / 2.0
        return QRectF(left, self._block_top(), width, BLOCK_HEIGHT).toAlignedRect()

    def _place_button(self) -> None:
        width = max(self.cancel.sizeHint().width(), 96)
        top = self._block_top() + BLOCK_HEIGHT - BUTTON_HEIGHT
        self.cancel.setGeometry(int((self.width() - width) / 2), int(top), width, BUTTON_HEIGHT)

    # --- Zeichnen --------------------------------------------------------

    def paintEvent(self, event: object) -> None:  # noqa: N802 — Qt-Name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colours = THEMES[self._theme]
        text = QColor(colours["text"])

        # Der Verlauf der leeren Ansicht, aus denselben Farben, die der
        # Renderer bekommt (``theme.viewport_colours``). Oben hell, unten
        # dunkel — genau andersherum wäre eine andere Ansicht.
        gradient = QLinearGradient(0.0, 0.0, 0.0, float(self.height()))
        gradient.setColorAt(0.0, QColor(colours["viewport_top"]))
        gradient.setColorAt(1.0, QColor(colours["viewport_bottom"]))
        painter.fillRect(self.rect(), gradient)

        top = self._block_top()
        column = self._column()
        paint_printed_mark(
            painter,
            self._renderer,
            QRectF((self.width() - MARK_SIZE) / 2.0, top, MARK_SIZE, MARK_SIZE),
            self._shown,
            GHOST,
        )

        line = top + MARK_SIZE + GAP
        self._paint_headline(painter, QRectF(column.left(), line, column.width(), HEADLINE_HEIGHT))

        line += HEADLINE_HEIGHT + GAP
        if not self._running:
            painter.end()
            return
        self._paint_rail(painter, QRectF(column.left(), line, column.width(), RAIL_HEIGHT), text)

        line += RAIL_HEIGHT + ROOMY
        self._paint_detail(
            painter, QRectF(column.left(), line, column.width(), DETAIL_HEIGHT), text
        )
        line += DETAIL_HEIGHT + ROOMY
        painter.drawText(
            QRectF(column.left(), line, column.width(), DETAIL_HEIGHT),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            self.timing.time_text,
        )
        painter.end()

    def _paint_headline(self, painter: QPainter, area: QRectF) -> None:
        font = QFont(self.font())
        font.setPointSizeF(font.pointSizeF() * 1.35)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(THEMES[self._theme]["text"]))
        painter.drawText(
            area,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            self._headline,
        )

    def _paint_rail(self, painter: QPainter, area: QRectF, text: QColor) -> None:
        """Die Fortschrittslinie — zweite Kodierung neben der Bauhöhe."""
        rail = QColor(text)
        rail.setAlpha(38)
        painter.fillRect(area, rail)
        done = QRectF(area)
        done.setWidth(area.width() * self._shown)
        painter.fillRect(done, QColor(THEMES[self._theme]["highlight"]))

    def _paint_detail(self, painter: QPainter, area: QRectF, text: QColor) -> None:
        """Links, woran gerechnet wird; rechts, wie weit.

        Die Zahl kommt aus dem **gemessenen** Wert und nicht aus dem gezeigten:
        die weiche Annäherung ist eine Sache der Anzeige, die Prozentangabe
        eine Auskunft.
        """
        font = QFont(self.font())
        font.setPointSizeF(max(font.pointSizeF() * 0.92, 7.0))
        painter.setFont(font)
        faded = QColor(text)
        faded.setAlpha(170)
        painter.setPen(faded)

        # Die eigene Zeitzeile hält den laufenden Schritt auch bei langen
        # Zeitangaben lesbar. Prozent bleibt beim gemessenen Anteil.
        percent = f"{round(self._target * 100)} %"
        metrics = QFontMetrics(font)
        room = area.width() - metrics.horizontalAdvance(percent) - ROOMY
        painter.drawText(
            QRectF(area.left(), area.top(), max(room, 0.0), area.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(self._detail, Qt.TextElideMode.ElideRight, int(max(room, 0.0))),
        )
        painter.drawText(
            area,
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            percent,
        )
