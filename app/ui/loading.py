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
Ansicht selbst, aus denselben Themenfarben, die der Plotter bekommt. Damit
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

from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QPushButton, QWidget

from app.i18n import tr
from app.ui.icons import application_icon_source, paint_printed_mark
from app.ui.motion import animations_enabled
from app.ui.style import ROOMY, WIDE
from app.ui.theme import THEMES, Theme

#: Wie lange ein Lauf dauern muss, bevor die Anzeige kommt.
#:
#: §2.8 sagt „unter 0,2 s nichts". Ein leeres Projekt ist in Millisekunden
#: gerechnet, und eine Anzeige, die dabei aufblitzt, ist Unruhe ohne Auskunft.
DELAY_MS = 200

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

#: Bildabstand der Animation in Millisekunden.
FRAME_MS = 16

#: Wie schnell sich die gezeigte Höhe der gemessenen annähert, je Bild.
#: Klein genug für eine weiche Bewegung, groß genug, dass der letzte Schritt
#: nicht sichtbar nachhinkt.
EASING = 0.18

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
    + GAP
    + BUTTON_HEIGHT
)


def remaining_time(started: float | None, fraction: float) -> str:
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
    """
    if started is None or fraction < ESTIMATE_FROM:
        return ""
    passed = time.monotonic() - started
    if passed < ESTIMATE_AFTER_S:
        return ""
    left = passed * (1.0 - fraction) / fraction
    if left < 5.0:
        return tr("gleich fertig")
    if left < 90.0:
        return tr("noch etwa {sekunden} s").format(sekunden=round(left / 5.0) * 5)
    return tr("noch etwa {minuten} min").format(minuten=round(left / 60.0))


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
    nicht: Das Ansichtsfenster ist ein natives Fenster (VTK), und ein natives
    Kind liegt auf dem Bildschirm über jedem gemalten Geschwister, egal was
    die Qt-Stapelung sagt. Solange es gezeigt und noch nie gerendert ist,
    stehen dort alte Pixel — beim Öffnen von Weg 1 sechs Sekunden lang der
    Startbildschirm bzw. Schwarz, und Robert hielt es zweimal für einen
    Absturz, während dieser Schleier unsichtbar darunter lag."""

    ended = Signal()
    """Die Anzeige ist weg — die Ansicht darf zurückkommen.

    Gesendet nur, wenn sie wirklich stand: ``end`` läuft nach jedem Lauf,
    auch wenn die Verzögerung die Anzeige nie hat erscheinen lassen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = QSvgRenderer(QByteArray(application_icon_source().encode("utf-8")))
        self._theme: Theme = "dark"
        self._headline = ""
        self._detail = ""
        self._started: float | None = None
        """Wann dieser Lauf begonnen hat — Grundlage der Restschätzung."""
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

    def begin(self, headline: str, at_once: bool = False) -> None:
        """Ein Lauf hat begonnen — die Anzeige kommt, wenn er dauert.

        Mehrfach aufzurufen ist gefahrlos: der zweite Aufruf schreibt nur die
        Überschrift um und lässt eine laufende Verzögerung laufen.

        ``at_once`` überspringt die Verzögerung. Sie schützt vor einem
        Aufblitzen bei Läufen unter 200 ms — beim Öffnen eines Projekts mit
        Schritten ist die Wartezeit aber sicher, und jede unbedeckte
        Millisekunde gehört dem nativen Ansichtsfenster mit seinen alten
        Pixeln (siehe ``appeared``). Dort muss die Anzeige vor dem ersten
        Bild stehen, nicht 200 ms danach.
        """
        self._headline = headline
        # Was ein Bildschirmleser vorliest. Der Text hier ist gemalt und kein
        # Label — ohne das wäre die Fläche für ihn stumm.
        self.setAccessibleName(headline)
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
        self._started = time.monotonic()
        if at_once or not animations_enabled():
            # Offscreen sieht niemand ein Aufblitzen, und ein Test, der auf
            # einen Zeitgeber wartet, prüft die Uhr statt das Verhalten.
            self._appear()
            return
        self._delay.start(DELAY_MS)

    def remaining(self) -> str:
        """Was von der Wartezeit noch aussteht — leer, solange es geraten wäre."""
        return remaining_time(self._started, self._target)

    def step(self, fraction: float, detail: str) -> None:
        """Wie weit der Lauf ist und woran er gerade rechnet."""
        self._target = max(0.0, min(1.0, fraction))
        self._detail = detail
        if not self.showing:
            return
        if not animations_enabled():
            self._shown = self._target
        self.update()

    def end(self) -> None:
        """Der Lauf ist vorbei — auch, wenn die Anzeige nie kam."""
        stood = self.showing
        self._delay.stop()
        self._frames.stop()
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
        self.update()

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
        # Plotter bekommt (``theme.viewport_colours``). Oben hell, unten
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
        self._paint_rail(painter, QRectF(column.left(), line, column.width(), RAIL_HEIGHT), text)

        line += RAIL_HEIGHT + ROOMY
        self._paint_detail(
            painter, QRectF(column.left(), line, column.width(), DETAIL_HEIGHT), text
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

        # Prozent sagt, wie weit; die Schätzung sagt, wie lange noch. Beide
        # rechts, damit der laufende Schritt links seine Breite behält.
        left_over = self.remaining()
        percent = f"{round(self._target * 100)} %"
        if left_over:
            percent = f"{percent}  ·  {left_over}"
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
