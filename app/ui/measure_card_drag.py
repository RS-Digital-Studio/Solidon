"""Die Maßkarte am Titel oder auf freiem Grund verschieben, ohne ihre Felder zu übernehmen."""

from __future__ import annotations

import weakref

from PySide6.QtCore import QEvent, QMetaObject, QObject, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)
from shiboken6 import isValid

from app.ui import app_events, cursors
from app.ui.leash import stop_watching_the_dying
from app.ui.overlay import CardPlace, card_rect, dropped_place


class MeasureCardDrag(QObject):
    """Ein Nutzerplatz je Maßauftrag; Parken darf keinen alten Fluss festhalten.

    Der Besitzer verbindet ``positionChanged`` wie seine übrigen Kartensignale
    und trennt es beim Parken. ``reset`` beginnt einen neuen Auftrag. Nach der
    Größenrechnung liefert ``update_room`` den freien Raum in Elternkoordinaten;
    ``placed_rect`` ersetzt nur nach einem Zug die automatische Platzierung.
    Begrenzungen beim Wachsen ändern den gespeicherten Platz nicht.
    """

    positionChanged = Signal()

    def __init__(self, card: QWidget) -> None:
        super().__init__(card)
        self._card = card
        self._room = QRect()
        self._place: CardPlace | None = None
        self._placed_width = card.width()
        self._placed_room = QRect()
        self._pressed: QPoint | None = None
        self._start = QRect()
        self._moving: QRect | None = None
        self._receiver: QWidget | None = None
        self._receiver_link: QMetaObject.Connection | None = None
        self._cursor_state: tuple[QCursor, bool] | None = None
        card.installEventFilter(self)
        owner = weakref.ref(self)

        def release() -> None:
            # Der Helfer kann vor der weiterlebenden Karte verschwinden.
            # Kein Qt-Aufruf am sterbenden Helfer und keine Kartenbewegung.
            live = owner()
            if live is not None:
                live._finish(commit=False, notify=False, restore=False)

        self.destroyed.connect(release)

    def update_room(self, room: QRect) -> None:
        """Den aktuellen Raum und auch neu eingebaute Feldgruppen übernehmen."""
        self._room = QRect(room)
        for widget in self._card.findChildren(QWidget):
            widget.installEventFilter(self)

    def placed_rect(self) -> QRect | None:
        """Nutzerort mit aktueller Kartengröße; ohne Nutzerzug bleibt die Vorgabe frei."""
        if self._moving is not None:
            return self._bounded(QRect(self._moving.topLeft(), self._card.size()))
        if self._place is None or self._room.isEmpty():
            return None
        size = self._card.size()
        room = self._room
        if not self._place.edge:
            # Beim freien Platz bleibt auch links der abgelegte Anker stehen,
            # wenn ein neuer Feldinhalt die Karte breiter macht.
            size = QSize(self._placed_width, size.height())
            # Ein später freigewordener Bildstreifen verschiebt den abgelegten
            # Anker nicht. Der aktuelle Raum begrenzt ihn erst darunter.
            room = self._placed_room
        rect = card_rect(self._place, room.width(), room.height(), size)
        rect.translate(room.topLeft())
        # Die Maßgruppe rollt bereits in ihrem eigenen Größenweg. Ihre gesamte
        # Karte bleibt erreichbar; der Kartenhelfer kürzt hier keinen Inhalt.
        return self._bounded(QRect(rect.topLeft(), self._card.size()))

    def reset(self) -> None:
        """Einen neuen Auftrag ohne übernommene Lage oder begonnenen Zug starten."""
        self._finish(commit=False, notify=False)
        self._place = None

    def _bounded(self, rect: QRect) -> QRect:
        """Die ganze, vom Besitzer bereits bemessene Karte im freien Raum halten."""
        rect.moveLeft(
            max(self._room.left(), min(rect.left(), self._room.right() - rect.width() + 1))
        )
        rect.moveTop(
            max(self._room.top(), min(rect.top(), self._room.bottom() - rect.height() + 1))
        )
        return rect

    def _free_at(self, global_pos: QPoint) -> bool:
        """Auch bei hochgereichten Mausereignissen gehört ein Feld weiter dem Feld."""
        local = self._card.mapFromGlobal(global_pos)
        if not self._card.rect().contains(local):
            return False
        widget = self._card.childAt(local)
        while widget is not None and widget is not self._card:
            if isinstance(
                widget,
                (
                    QAbstractButton,
                    QAbstractItemView,
                    QAbstractSlider,
                    QAbstractSpinBox,
                    QComboBox,
                    QLineEdit,
                    QPlainTextEdit,
                    QTextEdit,
                ),
            ):
                return False
            if isinstance(widget, QGroupBox) and widget.isCheckable():
                return False
            if isinstance(widget, QLabel) and (
                widget.buddy() is not None
                or widget.textInteractionFlags()
                & (
                    Qt.TextInteractionFlag.TextSelectableByMouse
                    | Qt.TextInteractionFlag.TextSelectableByKeyboard
                )
                or "<a " in widget.text().lower()
            ):
                return False
            widget = widget.parentWidget()
        return True

    def _finish(self, *, commit: bool, notify: bool = True, restore: bool = True) -> None:
        """Die vorübergehende Anmeldung und den eigenen Widgetcursor zurückgeben."""
        if self._pressed is None:
            return
        self._pressed = None
        app_events.forget(self)
        receiver, self._receiver = self._receiver, None
        link, self._receiver_link = self._receiver_link, None
        state, self._cursor_state = self._cursor_state, None
        moving, self._moving = self._moving, None
        if link is not None:
            QObject.disconnect(link)
        if receiver is not None and state is not None and isValid(receiver) and isValid(self._card):
            previous, owned = state
            if owned:
                receiver.setCursor(previous)
            else:
                receiver.unsetCursor()
        if moving is None:
            return
        if commit:
            rect = self._bounded(moving).translated(-self._room.topLeft())
            self._place = dropped_place(rect, self._room.width(), self._room.height())
            self._placed_width = self._card.width()
            self._placed_room = QRect(self._room)
        elif restore:
            self._card.move(self._start.topLeft())
        if notify:
            self.positionChanged.emit()

    def _receiver_gone(self) -> None:
        """Auch direkter Elternabbau endet ohne Zugriff auf den sterbenden Baum."""
        self._receiver = None
        self._cursor_state = None
        self._finish(commit=False, notify=False, restore=False)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        try:
            if stop_watching_the_dying(self, watched, event):
                if watched is self._card or watched is self._receiver:
                    self._receiver_gone()
                return False
            kind = event.type()
            if self._pressed is not None:
                if isinstance(event, QKeyEvent) and event.key() == Qt.Key.Key_Escape:
                    if kind == QEvent.Type.ShortcutOverride:
                        event.accept()
                        return True
                    if kind == QEvent.Type.KeyPress:
                        self._finish(commit=False)
                        return True
                if kind == QEvent.Type.ParentChange and (
                    watched is self._card or watched is self._receiver
                ):
                    self._finish(commit=False, notify=False, restore=False)
                    return False
                if kind == QEvent.Type.Hide and (
                    watched is self._card or watched is self._receiver
                ):
                    self._finish(commit=False, notify=False)
                elif (kind == QEvent.Type.WindowDeactivate and watched is self._card.window()) or (
                    kind == QEvent.Type.FocusOut
                    and isinstance(watched, QWidget)
                    and (watched is self._card or self._card.isAncestorOf(watched))
                ):
                    self._finish(commit=False)
                # Qt muss den Fenstertransport erst zustellen und beim Loslassen
                # seinen Druckempfänger lösen, bevor der Widgetfilter übernimmt.
                if isinstance(event, QMouseEvent) and isinstance(watched, QWidget):
                    if kind == QEvent.Type.MouseMove:
                        delta = event.globalPosition().toPoint() - self._pressed
                        if self._moving is None:
                            if delta.manhattanLength() < QApplication.startDragDistance():
                                return True
                            receiver = self._receiver
                            if receiver is None or not isValid(receiver):
                                self._receiver_gone()
                                return False
                            self._cursor_state = (
                                QCursor(receiver.cursor()),
                                receiver.testAttribute(Qt.WidgetAttribute.WA_SetCursor),
                            )
                            # Qts Druckempfänger behält auch außerhalb der Karte
                            # den Zug. Sein Cursor verändert keinen globalen Stapel.
                            receiver.setCursor(cursors.cursor("move", receiver))
                        self._moving = self._bounded(self._start.translated(delta))
                        self._card.move(self._moving.topLeft())
                        self.positionChanged.emit()
                        return True
                    if (
                        kind == QEvent.Type.MouseButtonRelease
                        and event.button() == Qt.MouseButton.LeftButton
                    ):
                        self._finish(commit=True)
                        return True
            elif (
                kind == QEvent.Type.MouseButtonPress
                and isinstance(event, QMouseEvent)
                and event.button() == Qt.MouseButton.LeftButton
                and isinstance(watched, QWidget)
                and (watched is self._card or self._card.isAncestorOf(watched))
                and not self._room.isEmpty()
                and self._free_at(event.globalPosition().toPoint())
            ):
                self._pressed = event.globalPosition().toPoint()
                self._start = self._card.geometry()
                self._receiver = watched
                self._receiver_link = watched.destroyed.connect(self._receiver_gone)
                if not app_events.listen(
                    self,
                    (
                        QEvent.Type.MouseMove,
                        QEvent.Type.MouseButtonRelease,
                        QEvent.Type.ShortcutOverride,
                        QEvent.Type.KeyPress,
                        QEvent.Type.Hide,
                        QEvent.Type.FocusOut,
                        QEvent.Type.WindowDeactivate,
                        QEvent.Type.ParentChange,
                        QEvent.Type.Destroy,
                        QEvent.Type.DeferredDelete,
                    ),
                ):
                    self._finish(commit=False, notify=False)
                    return False
                return True
            return False
        except Exception:
            # Fehler bleiben Fehler; Anmeldung und Cursor dürfen sie nicht
            # überleben. Keine zweite Geometrieänderung auf dem Fehlerweg.
            self._finish(commit=False, notify=False, restore=False)
            raise
