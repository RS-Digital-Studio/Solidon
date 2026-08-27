"""Der Ladebildschirm beim Start (Bauplan §2.8).

Das Anwendungssymbol wird gedruckt, während die Anwendung lädt: es wächst von
unten nach oben, und an der Aufbaukante läuft eine helle Linie mit — der
Druckkopf. Wenn der Körper fertig ist, steht das Fenster.

Die Höhe folgt dem **echten** Fortschritt, nicht einer Uhr. Ein Balken, der
gleichmäßig läuft, während dahinter etwas ungleichmäßig lädt, ist eine
Behauptung; dieser hier ist eine Anzeige. Zwischen zwei Stufen wird weich
interpoliert, damit es nicht springt — die Zahl bleibt trotzdem die gemessene.

Warum überhaupt: Das Register zu füllen und Qt zu starten dauert auf einer
kalten Maschine über zwei Sekunden. Nach §2.8 gehört ab zwei Sekunden eine
Anzeige hin, und ein leerer Bildschirm mit wartendem Mauszeiger ist keine.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget

from app.branding import APP_NAME, APP_VERSION
from app.ui.icons import application_icon_source, paint_printed_mark

#: Maße des Fensters in logischen Pixeln. Breit genug für den Namen, flach
#: genug, dass es nicht wie ein Dialog wirkt.
WIDTH = 460
HEIGHT = 300

#: Kantenlänge des gezeichneten Symbols.
MARK_SIZE = 116

#: Wie schnell sich die gezeigte Höhe der gemessenen annähert, je Bild.
#: Klein genug für eine weiche Bewegung, groß genug, dass der letzte Schritt
#: nicht sichtbar nachhinkt.
EASING = 0.18

#: Bildabstand der Animation in Millisekunden.
FRAME_MS = 16


class SplashScreen(QWidget):
    """Das Fenster, das während des Ladens steht.

    Es ist bewusst kein ``QSplashScreen``: dessen ``showMessage`` zeichnet Text
    über ein Pixmap, und für den schichtweisen Aufbau braucht es eigenes
    Zeichnen mit Beschnitt.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(WIDTH, HEIGHT)

        self._renderer = QSvgRenderer(QByteArray(application_icon_source().encode("utf-8")))
        self._target = 0.0
        self._shown = 0.0
        self._message = ""

        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._advance)

        self._centre_on_screen()

    def _centre_on_screen(self) -> None:
        # Gefragt wird über ``screens()`` und nicht über ``primaryScreen()``:
        # die Stubs geben dort ``QScreen`` ohne ``None`` an, und eine Prüfung
        # darauf gilt mypy als unerreichbar. Die leere Liste ist derselbe Fall,
        # nur typsauber — unter ``QT_QPA_PLATFORM=offscreen`` gibt es keinen
        # Bildschirm, und dort sieht auch niemand hin.
        if not QApplication.screens():
            return
        area = QApplication.primaryScreen().availableGeometry()
        self.move(area.center().x() - WIDTH // 2, area.center().y() - HEIGHT // 2)

    def step(self, message: str, progress: float) -> None:
        """Sagt, was gerade geschieht und wie weit es ist.

        ``progress`` ist der Anteil zwischen 0 und 1. Die Anzeige nähert sich
        ihm an, statt zu springen; wer die Ereignisschleife danach nicht
        erreicht, sieht trotzdem den Text — deshalb das ``processEvents`` hier
        und nicht beim Aufrufer, der es sonst vergisst.
        """
        self._message = message
        self._target = max(0.0, min(1.0, progress))
        if not self._timer.isActive():
            self._timer.start()
        self.repaint()
        QApplication.processEvents()

    def finish(self, window: QWidget | None = None) -> None:
        """Schließt den Ladebildschirm, sobald das Fenster steht."""
        self._timer.stop()
        if window is not None:
            window.raise_()
            window.activateWindow()
        self.close()

    def _advance(self) -> None:
        if abs(self._target - self._shown) < 0.002:
            self._shown = self._target
            if self._target >= 1.0:
                self._timer.stop()
            return
        self._shown += (self._target - self._shown) * EASING
        self.update()

    # -- Zeichnen ---------------------------------------------------------

    def paintEvent(self, event: object) -> None:  # noqa: N802  (Qt-Namensschema)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = QApplication.palette()
        background = palette.window().color()
        text_colour = palette.windowText().color()

        card = QRectF(0, 0, WIDTH, HEIGHT)
        path = QPainterPath()
        path.addRoundedRect(card, 14, 14)
        painter.fillPath(path, background)
        painter.setPen(QPen(QColor(text_colour.red(), text_colour.green(), text_colour.blue(), 40)))
        painter.drawPath(path)

        self._paint_mark(painter)
        self._paint_texts(painter, text_colour)
        self._paint_bar(painter, text_colour)
        painter.end()

    def _paint_mark(self, painter: QPainter) -> None:
        """Zeichnet das Symbol so weit, wie es „gedruckt" ist."""
        left = (WIDTH - MARK_SIZE) / 2
        paint_printed_mark(
            painter, self._renderer, QRectF(left, 46.0, MARK_SIZE, MARK_SIZE), self._shown
        )

    def _paint_texts(self, painter: QPainter, colour: QColor) -> None:
        name_font = QFont(self.font())
        name_font.setPointSizeF(name_font.pointSizeF() * 1.7)
        name_font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(name_font)
        painter.setPen(colour)
        painter.drawText(
            QRectF(0, 178, WIDTH, 34),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            APP_NAME,
        )

        small = QFont(self.font())
        small.setPointSizeF(max(small.pointSizeF() * 0.92, 7.0))
        painter.setFont(small)
        faded = QColor(colour)
        faded.setAlpha(150)
        painter.setPen(faded)
        painter.drawText(
            QRectF(0, 210, WIDTH, 20),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            APP_VERSION,
        )
        painter.drawText(
            QRectF(24, 238, WIDTH - 48, 20),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            self._message,
        )

    def _paint_bar(self, painter: QPainter, colour: QColor) -> None:
        """Die Fortschrittslinie — zweite Kodierung neben der Bauhöhe.

        Regel 18 gilt auch hier: Wer den Farbunterschied am Symbol nicht sieht,
        liest den Fortschritt an der Länge dieser Linie ab.
        """
        track = QRectF(40, 272, WIDTH - 80, 3)
        rail = QColor(colour)
        rail.setAlpha(38)
        painter.fillRect(track, rail)
        done = QRectF(track)
        done.setWidth(track.width() * self._shown)
        painter.fillRect(done, QColor("#e08b4e"))
