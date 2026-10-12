"""Eingabe am Ort — eine Farbe am Farbknopf, ein Maß an seiner Karte (FD-22, Z5).

``QColorDialog.getColor`` öffnete mitten im Ablauf den Farbdialog des
Betriebssystems, ``QInputDialog.getText`` ein Fenster ohne Raster mit *OK* und
*Cancel* — beide fern der Stelle, an der der Kunde gerade war. Hier steht die
Eingabe dort, wo er geklickt hat: als ``Qt.Popup`` wie die Filamentliste der
Kopfzeile, das Escape und ein Klick daneben schließen und das niemanden
aufhält — ``show`` statt ``exec``, offscreen steht damit keine Suite.

:class:`ColourPopup` ist der Farbwähler: Regalfarben als Felder, jede mit
ihrem Namen (Regel 18), und darunter der genaue Farbwert zum Eintippen.
:class:`ValuePopup` ist ein Feld mit Beschriftung und *Übernehmen*. Beide
tragen ihr Kennzeichen im Wortschatz (``message:<sache>``), und die
Funktionsliste findet sie über :func:`choose_colour` und :func:`edit_value`
(``tools/function_scan.MESSAGE_BUILDERS``).

Fragen ohne Ort — eine Adresse, eine Wahl unter Gleichwertigem — stellt
:mod:`app.ui.input_dialog`.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, QRegularExpression, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QEnterEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import guides
from app.i18n import tr
from app.ui.labels import colour_name
from app.ui.palette import readable_on
from app.ui.style import NORMAL, TIGHT, make_primary, set_level
from app.ui.theme import THEMES, current_theme

#: Wie groß ein Farbfeld steht, in logischen Punkten — groß genug zum Treffen,
#: klein genug, dass 27 Felder unter einen Knopf passen.
SWATCH_SIZE: Final = 24

#: Die Farbtöne der Regalfarben in Grad, je einer für jedes Wort aus
#: ``labels._HUES``: Rot, Orange, Gelb, Grün, Türkis, Blau, Violett, Magenta.
SHELF_HUES: Final = (0, 30, 55, 120, 180, 220, 275, 320)

#: Je Reihe Sättigung und Helligkeit: hell, kräftig, dunkel. Dunkles Orange
#: heißt Braun (:func:`labels.colour_name`) — ein eigener Braunton fehlt nicht.
SHELF_SHADES: Final = ((0.75, 0.75), (0.85, 0.5), (0.8, 0.28))

#: Die Spalte ohne Farbton, in derselben Reihenfolge von hell nach dunkel.
SHELF_NEUTRALS: Final = ("#ffffff", "#9e9e9e", "#1a1a1a")


def shelf_colours() -> tuple[tuple[str, ...], ...]:
    """Die Regalfarben als Reihen von ``#rrggbb`` — hell, kräftig, dunkel."""
    return tuple(
        (
            *(QColor.fromHslF(hue / 360.0, saturation, lightness).name() for hue in SHELF_HUES),
            neutral,
        )
        for (saturation, lightness), neutral in zip(SHELF_SHADES, SHELF_NEUTRALS, strict=True)
    )


def shelf_names(rows: tuple[tuple[str, ...], ...]) -> dict[str, str]:
    """Der Name jedes Farbfelds, wie er vorgelesen wird — keiner doppelt.

    Der Name ist der des Farbknopfs (:func:`labels.colour_name`). Tragen zwei
    Felder denselben, sagt die Reihe, welches gemeint ist: „Blau, hell“, „Blau“,
    „Blau, dunkel“.
    """
    plain = {colour: colour_name(colour) for row in rows for colour in row}
    count: dict[str, int] = {}
    for name in plain.values():
        count[name] = count.get(name, 0) + 1
    named: dict[str, str] = {}
    for number, row in enumerate(rows):
        for colour in row:
            name = plain[colour]
            if count[name] > 1 and number == 0:
                name = tr("{colour}, hell", colour=name)
            elif count[name] > 1 and number == len(rows) - 1:
                name = tr("{colour}, dunkel", colour=name)
            named[colour] = str(name)
    return named


def typed_colour(text: str) -> str:
    """``#rrggbb`` aus dem, was im Feld steht — oder leer, wenn es keine Farbe ist."""
    digits = text.strip().removeprefix("#")
    if len(digits) != 6 or any(sign not in "0123456789abcdefABCDEF" for sign in digits):
        return ""
    return f"#{digits.lower()}"


class PlacePopup(QFrame):
    """Ein kleines Fenster an der Stelle, an der gefragt wird.

    Ein ``Qt.Popup``: Escape und ein Klick daneben schließen es. ``once``
    räumt es danach weg — eine Eingabe am Ort ist eine Geste, kein Fenster,
    das man wieder öffnet.
    """

    def __init__(self, parent: QWidget, *, name: str, target: str = "", once: bool = True) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        # Wie ein Menü: Grundfläche und Linie aus dem Stylesheet (``style.py``).
        self.setObjectName("placePopup")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAutoFillBackground(True)
        self.setAccessibleName(name)
        if target:
            self.setProperty(guides.TARGET_PROPERTY, target)
        if once:
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._anchor: QWidget | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 — Qt-Name
        """Ein Druck auf den Knopf, der das Fenster öffnete, schließt es nur — wie ``QMenu``.

        Qt schließt ein Popup beim Druck daneben. Unter X11 spielt es den
        Druck danach dem Widget darunter zu, und der Knopf öffnete es sofort
        wieder; unter Windows und offscreen bleibt der Druck beim Popup.
        """
        anchor = self._anchor
        if anchor is not None and anchor.isVisible():
            where = anchor.mapFromGlobal(event.globalPosition().toPoint())
            if anchor.rect().contains(where):
                self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay, True)
        super().mousePressEvent(event)

    def place_below(self, anchor: QWidget, *, width: int = 0, flush_right: bool = False) -> None:
        """Unter ``anchor``, oder darüber, wenn unten der Platz fehlt — nie über den Schirmrand.

        ``flush_right`` legt die rechten Kanten aufeinander (ein Knopf am
        rechten Rand der Kopfzeile), sonst die linken.
        """
        self._anchor = anchor
        self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay, False)
        screen = anchor.screen().availableGeometry()
        self.adjustSize()
        wide = min(screen.width(), max(self.sizeHint().width(), width))
        high = min(self.sizeHint().height(), screen.height())
        below = anchor.mapToGlobal(QPoint(0, anchor.height()))
        above = anchor.mapToGlobal(QPoint(0, 0))
        top = below.y() if below.y() + high <= screen.bottom() + 1 else above.y() - high
        left = below.x() + anchor.width() - wide if flush_right else below.x()
        self._settle(QRect(left, top, wide, high), screen)

    def show_at(self, point: QPoint, anchor: QWidget) -> None:
        """Mit der linken oberen Ecke an ``point`` (global), im Fenster von ``anchor``.

        Passt es hinein, bleibt das Feld im Fenster, in dem gefragt wurde — es
        gehört zur Zeile darunter und ragt nicht über den Rand hinaus.
        """
        self._anchor = None
        self.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay, False)
        screen = anchor.screen().availableGeometry()
        self.adjustSize()
        wide = min(screen.width(), self.sizeHint().width())
        high = min(self.sizeHint().height(), screen.height())
        window = anchor.window().geometry().intersected(screen)
        fits = wide <= window.width() and high <= window.height()
        self._settle(QRect(point.x(), point.y(), wide, high), window if fits else screen)

    def _settle(self, wanted: QRect, bounds: QRect) -> None:
        left = min(max(wanted.left(), bounds.left()), bounds.right() - wanted.width() + 1)
        top = min(max(wanted.top(), bounds.top()), bounds.bottom() - wanted.height() + 1)
        self.setGeometry(left, top, wanted.width(), wanted.height())
        self.show()


class _Swatch(QAbstractButton):
    """Ein Farbfeld: die Farbe als Fläche, der Name als Kurzhilfe und vorgelesen.

    Gewählt heißt ein Ring in Schriftfarbe um das Feld (Form, nicht nur Farbe,
    Regel 18), Fokus ein gestrichelter Ring in der Fokusfarbe wie an jedem
    Eingabefeld.
    """

    def __init__(self, colour: str, name: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.colour = colour
        self.setCheckable(True)
        self.setFixedSize(SWATCH_SIZE, SWATCH_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(name)
        self.setAccessibleDescription(colour.upper())
        self.setToolTip(f"{name} · {colour.upper()}")

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 — Qt-Name
        colours = THEMES[current_theme()]
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            field = QRectF(self.rect()).adjusted(3.5, 3.5, -3.5, -3.5)
            painter.setPen(QPen(QColor(colours["line"]), 1.0))
            filled = QColor(self.colour)
            # Ohne gültige Farbe bleibt das Feld leer, nicht schwarz.
            painter.setBrush(filled if filled.isValid() else QColor(0, 0, 0, 0))
            painter.drawRoundedRect(field, 3.0, 3.0)
            if self.isChecked() or self.underMouse():
                ring = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(colours["text"]), 2.0))
                painter.drawRoundedRect(ring, 4.0, 4.0)
            if self.isChecked():
                # Der Haken in der Schrift, die auf dieser Farbe lesbar bleibt.
                painter.setPen(QPen(QColor(readable_on(self.colour)), 1.6))
                middle = field.center()
                painter.drawPolyline(
                    [
                        middle + QPoint(-4, 0).toPointF(),
                        middle + QPoint(-1, 3).toPointF(),
                        middle + QPoint(4, -3).toPointF(),
                    ]
                )
            if self.hasFocus():
                ring = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
                dashed = QPen(QColor(colours["accent_line"]), 1.0)
                dashed.setStyle(Qt.PenStyle.DashLine)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(dashed)
                painter.drawRoundedRect(ring, 4.0, 4.0)
        finally:
            painter.end()

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802 — Qt-Name
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event: QEvent) -> None:  # noqa: N802 — Qt-Name
        super().leaveEvent(event)
        self.update()


#: Pfeiltaste → Schritt in Reihen und Spalten der Farbfelder.
_MOVES: Final = (
    (Qt.Key.Key_Left, 0, -1),
    (Qt.Key.Key_Right, 0, 1),
    (Qt.Key.Key_Up, -1, 0),
    (Qt.Key.Key_Down, 1, 0),
)


class ColourPopup(PlacePopup):
    """Der Farbwähler am Farbknopf: Regalfarben und der genaue Farbwert.

    Ein Klick auf ein Feld nimmt die Farbe und schließt; Pfeiltasten gehen
    durch die Felder, Enter und Leertaste nehmen. Der Farbwert darunter nimmt
    sechs Hexstellen — die Zahl, die auf der Spule oder im Shop steht —, Enter
    oder *Übernehmen* nehmen ihn. :attr:`chosen` meldet ``#rrggbb``.
    """

    chosen = Signal(str)

    def __init__(self, parent: QWidget, *, title: str, current: str, target: str) -> None:
        super().__init__(parent, name=title, target=target)
        heading = QLabel(title, self)
        heading.setTextFormat(Qt.TextFormat.PlainText)
        set_level(heading, "section")

        rows = shelf_colours()
        names = shelf_names(rows)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(TIGHT)
        self.swatches: list[list[_Swatch]] = []
        now = typed_colour(current)
        for row, colours in enumerate(rows):
            line: list[_Swatch] = []
            for column, colour in enumerate(colours):
                swatch = _Swatch(colour, names[colour], self)
                swatch.setChecked(colour == now)
                swatch.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
                swatch.clicked.connect(self._take_swatch)
                swatch.installEventFilter(self)
                grid.addWidget(swatch, row, column)
                line.append(swatch)
            self.swatches.append(line)

        caption = QLabel(tr("Farbwert"), self)
        self.field = QLineEdit(now.upper() if now else current.strip().upper(), self)
        self.field.setValidator(
            QRegularExpressionValidator(QRegularExpression("#?[0-9A-Fa-f]{0,6}"), self.field)
        )
        self.field.setAccessibleName(tr("Farbwert"))
        caption.setBuddy(self.field)
        # Was der Farbwert zeigt, bevor er genommen wird — ein Tippfehler fällt hier auf.
        self.preview = _Swatch("", "", self)
        self.preview.setCheckable(False)
        self.preview.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.preview.unsetCursor()
        self.take = QPushButton(tr("Übernehmen"), self)
        make_primary(self.take)
        self.field.textChanged.connect(self._follow_field)
        self.field.returnPressed.connect(self._take_typed)
        self.take.clicked.connect(self._take_typed)
        typed = QHBoxLayout()
        typed.setContentsMargins(0, 0, 0, 0)
        typed.setSpacing(NORMAL)
        typed.addWidget(caption)
        typed.addWidget(self.field, 1)
        typed.addWidget(self.preview)
        typed.addWidget(self.take)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.setSpacing(NORMAL)
        layout.addWidget(heading)
        layout.addLayout(grid)
        layout.addLayout(typed)

        self._entry = self._swatch_of(now) or self.swatches[1][0]
        self._enter_with(self._entry)
        self._follow_field()

    def _swatch_of(self, colour: str) -> _Swatch | None:
        return next(
            (swatch for line in self.swatches for swatch in line if swatch.colour == colour), None
        )

    def _enter_with(self, swatch: _Swatch) -> None:
        """Tab führt in die Felder genau über eines — das gewählte oder zuletzt besuchte."""
        self._entry.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        swatch.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._entry = swatch
        QWidget.setTabOrder(swatch, self.field)
        QWidget.setTabOrder(self.field, self.take)

    def start(self) -> None:
        """Der Fokus: im gewählten Feld, sonst im Farbwert, wenn der eine eigene Farbe trägt."""
        if self._swatch_of(typed_colour(self.field.text())) is None and self.field.text():
            self.field.setFocus(Qt.FocusReason.PopupFocusReason)
            self.field.selectAll()
        else:
            self._entry.setFocus(Qt.FocusReason.PopupFocusReason)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        """Pfeiltasten wandern durch die Felder, Enter nimmt das Feld unter dem Fokus."""
        if not isinstance(watched, _Swatch) or event.type() != QEvent.Type.KeyPress:
            return False
        assert isinstance(event, QKeyEvent)
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            watched.click()
            return True
        step = next((move for named, *move in _MOVES if key == named), None)
        if step is None:
            return False
        row, column = next(
            (number, line.index(watched))
            for number, line in enumerate(self.swatches)
            if watched in line
        )
        down, across = step
        row = min(max(row + down, 0), len(self.swatches) - 1)
        column = min(max(column + across, 0), len(self.swatches[row]) - 1)
        target = self.swatches[row][column]
        self._enter_with(target)
        target.setFocus(Qt.FocusReason.TabFocusReason)
        return True

    def _follow_field(self) -> None:
        """*Übernehmen* geht nur mit sechs Hexstellen — und sagt sonst, was fehlt."""
        typed = typed_colour(self.field.text())
        valid = bool(typed)
        self.preview.colour = typed
        named = colour_name(typed) if valid else ""
        self.preview.setAccessibleName(named)
        self.preview.setToolTip(f"{named} · {typed.upper()}" if valid else "")
        self.preview.update()
        self.take.setEnabled(valid)
        why = "" if valid else str(tr("Sechs Stellen aus 0 bis 9 und A bis F, etwa #FF8800."))
        self.take.setToolTip(why)
        self.take.setAccessibleDescription(why)

    def _take_swatch(self) -> None:
        swatch = self.sender()
        if isinstance(swatch, _Swatch):
            self._take(swatch.colour)

    def _take_typed(self) -> None:
        if colour := typed_colour(self.field.text()):
            self._take(colour)

    def _take(self, colour: str) -> None:
        self.chosen.emit(colour)
        self.close()


class ValuePopup(PlacePopup):
    """Ein Wert am Ort: Beschriftung, Feld, *Übernehmen*.

    Enter und *Übernehmen* nehmen den Wert, Escape und ein Klick daneben lassen
    alles, wie es war. :attr:`submitted` meldet den Text ohne Rand; ein leeres
    Feld nimmt nichts, und *Übernehmen* sagt es.
    """

    submitted = Signal(str)

    def __init__(
        self, parent: QWidget, *, title: str, caption: str, text: str, note: str, target: str
    ) -> None:
        super().__init__(parent, name=title, target=target)
        label = QLabel(caption, self)
        label.setTextFormat(Qt.TextFormat.PlainText)
        self.field = QLineEdit(text, self)
        self.field.setAccessibleName(caption)
        self.field.setAccessibleDescription(note)
        self.field.setToolTip(note)
        label.setToolTip(note)
        label.setBuddy(self.field)
        self.take = QPushButton(tr("Übernehmen"), self)
        make_primary(self.take)
        self.field.textChanged.connect(self._follow_field)
        self.field.returnPressed.connect(self._submit)
        self.take.clicked.connect(self._submit)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, NORMAL, NORMAL, NORMAL)
        layout.setSpacing(NORMAL)
        layout.addWidget(label)
        layout.addWidget(self.field, 1)
        layout.addWidget(self.take)
        self._follow_field()

    def start(self) -> None:
        self.field.setFocus(Qt.FocusReason.PopupFocusReason)
        self.field.selectAll()

    def _follow_field(self) -> None:
        filled = bool(self.field.text().strip())
        self.take.setEnabled(filled)
        why = "" if filled else str(tr("Erst einen Wert eintragen."))
        self.take.setToolTip(why)
        self.take.setAccessibleDescription(why)

    def _submit(self) -> None:
        if entered := self.field.text().strip():
            self.submitted.emit(entered)
            self.close()


def choose_colour(anchor: QWidget, current: str, *, title: str, target: str) -> ColourPopup:
    """Öffnet den Farbwähler unter ``anchor``; wer die Farbe will, hört auf ``chosen``."""
    popup = ColourPopup(anchor, title=title, current=current, target=target)
    popup.place_below(anchor)
    popup.start()
    return popup


def gesture_point(near: QWidget) -> QPoint:
    """Wo die Geste war, die nach einem Wert fragt — global.

    Hat eine Liste in ``near`` den Fokus, ist es ihre aktuelle Zeile (Tastatur,
    Doppelklick); sonst der Zeiger, solange er über dem Fenster steht
    (Doppelklick auf eine Maßkarte, Kontextmenü); sonst die Mitte von ``near``.
    """
    focused = QApplication.focusWidget()
    if (
        isinstance(focused, QAbstractItemView)
        and (focused is near or near.isAncestorOf(focused))
        and focused.currentIndex().isValid()
    ):
        row = focused.visualRect(focused.currentIndex())
        return focused.viewport().mapToGlobal(row.bottomLeft())
    pointer = QCursor.pos()
    if near.window().frameGeometry().contains(pointer):
        return pointer
    return near.mapToGlobal(near.rect().center())


def edit_value(
    anchor: QWidget, *, title: str, caption: str, text: str, note: str, target: str
) -> ValuePopup:
    """Öffnet ein Wertfeld an der Stelle der Geste (:func:`gesture_point`)."""
    popup = ValuePopup(anchor, title=title, caption=caption, text=text, note=note, target=target)
    popup.show_at(gesture_point(anchor), anchor)
    popup.start()
    return popup
