"""Der native Läufer liest den Zugzeiger am Fenster des Druckempfängers (FD-164).

Die Maßkarte trägt ein eigenes natives Fenster, und Qt setzt einen
Widgetzeiger am nächsten nativen Vorfahren. Die erste Fassung des Außenzugs las
das Hauptfenster; dort steht ein anderer Zeiger, und ihre Bedingung war am
echten Schirm an der falschen Stelle rot (Zusatzlauf 2b). Hier offscreen
nachgestellt: der echte ``MeasureCardDrag``, derselbe Fenstertransport wie im
Läufer (``QTest`` am Hauptfenster, vier gehaltene Bewegungen bis außerhalb der
Karte) — einmal mit nativem Kartenfenster und als Gegenprobe ohne. Die
Urteile des Läufers selbst (:func:`holds_move_cursor`, :func:`returns_cursor`,
:func:`transport_of`) prüfen die Tests darunter ohne Fenster.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QWidget

from app.ui.cursors import cursor
from app.ui.measure_card_drag import MeasureCardDrag
from app.ui.theme import apply_theme, current_theme
from tests import qt_roots
from tools.native_measure_card import (
    LEFT,
    cursor_form,
    cursor_sample,
    holds_move_cursor,
    native_window_of,
    returns_cursor,
    transport_of,
)

roots = qt_roots.roots

MOVE = {"shape": "SizeAllCursor", "hotspot": [0, 0], "pixels": [0, 0], "bitmap": None}
ARROW = {"shape": "ArrowCursor", "hotspot": [0, 0], "pixels": [0, 0], "bitmap": None}


@pytest.fixture
def card_scene(
    qt_app: QApplication, roots: Callable[[Any], Any]
) -> Iterator[Callable[[bool], tuple[Any, ...]]]:
    """Hauptfenster, Karte mit Titel und Feld, der Zug des Produkts; die Karte wahlweise nativ."""
    before = current_theme()
    apply_theme(qt_app, "light")

    def build(native: bool) -> tuple[Any, ...]:
        view = roots(QWidget())
        view.resize(1200, 900)
        card = QWidget(view)
        if native:
            card.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        card.setGeometry(620, 100, 320, 300)
        title = QLabel("Bohrung ändern", card)
        title.setGeometry(15, 15, 280, 35)
        field = QLineEdit(card)
        field.setGeometry(15, 80, 200, 30)
        drag = MeasureCardDrag(card)
        drag.update_room(QRect(40, 50, 1040, 780))
        view.show()
        view.activateWindow()
        qt_app.processEvents()
        return view, card, title, field, drag

    yield build
    apply_theme(qt_app, before)


def drag_outside(qt_app: QApplication, view: Any, title: Any) -> tuple[Any, Any]:
    """Drückt am Titel und zieht in vier Schritten bis außerhalb der Karte — wie der Läufer."""
    handle = view.windowHandle()
    start = title.mapToGlobal(title.rect().center())
    end = view.mapToGlobal(QPoint(view.width() - 5, view.height() - 5))
    QTest.mouseMove(handle, handle.mapFromGlobal(start))
    qt_app.processEvents()
    QTest.mousePress(
        handle,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        handle.mapFromGlobal(start),
    )
    for part in (1, 2, 3, 4):
        point = start + QPoint(
            round((end.x() - start.x()) * part / 4), round((end.y() - start.y()) * part / 4)
        )
        QTest.mouseMove(handle, handle.mapFromGlobal(point))
        qt_app.processEvents()
    return handle, end


@pytest.mark.parametrize("native", [True, False], ids=["natives Kartenfenster", "ohne natives"])
def test_the_move_cursor_is_read_where_qt_puts_it(
    qt_app: QApplication, card_scene: Callable[[bool], tuple[Any, ...]], native: bool
) -> None:
    """Beim Halten trägt das Fenster des Druckempfängers den Zugzeiger, danach nicht mehr."""
    view, card, title, field, drag = card_scene(native)
    receiver_window = native_window_of(title)
    if native:
        assert receiver_window is card.windowHandle()
        assert receiver_window is not view.windowHandle()
    else:
        assert receiver_window is view.windowHandle()
    expected = cursor_form(cursor("move", title))
    assert expected is not None and expected["shape"] == "SizeAllCursor"
    before = cursor_sample(title, top=view.windowHandle())
    handle, end = drag_outside(qt_app, view, title)
    try:
        held = cursor_sample(title, top=handle)
        assert held["buttons"] & LEFT
        assert not card.geometry().contains(view.mapFromGlobal(end))
        assert holds_move_cursor(held, expected), held
        # Gegenprobe: So las die erste Fassung — am Hauptfenster. Mit nativer
        # Karte steht dort ein anderer Zeiger; ohne ist es dasselbe Fenster.
        first_version = {**held, "receiver_window": held["main_window"]}
        assert holds_move_cursor(first_version, expected) is not native, held
    finally:
        QTest.mouseRelease(
            handle,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            handle.mapFromGlobal(end),
        )
        qt_app.processEvents()
    after = cursor_sample(title, top=handle)
    assert returns_cursor(
        before, after, pressed_after=drag._pressed is not None, expected=expected
    ), (before, after)
    # Die nächste Kundengeste: Überfahren eines Felds der Karte.
    QTest.mouseMove(handle, handle.mapFromGlobal(field.mapToGlobal(field.rect().center())))
    qt_app.processEvents()
    at_field = cursor_form(native_window_of(field).cursor())
    assert at_field != expected
    assert at_field == cursor_form(field.cursor())


def sample(**changed: Any) -> dict[str, Any]:
    """Ein gehaltener Zug, wie der Läufer ihn liest — mit einzelnen Abweichungen."""
    return {
        "receiver_window": MOVE,
        "main_window": ARROW,
        "override": None,
        "press_widget": MOVE,
        "press_owns_cursor": True,
        "outside_widget": ARROW,
        "outside_owns_cursor": False,
        "buttons": LEFT,
        **changed,
    }


@pytest.mark.parametrize(
    "changed",
    [
        {"receiver_window": ARROW},
        {"press_widget": ARROW},
        {"press_owns_cursor": False},
        {"override": MOVE},
        {"buttons": 0},
    ],
    ids=["Fenster", "Widget", "Besitz", "Override", "Taste"],
)
def test_the_held_judgement_needs_every_part(changed: dict[str, Any]) -> None:
    """Jede einzelne Abweichung macht das Halteurteil falsch; der unveränderte Zug besteht."""
    assert holds_move_cursor(sample(), MOVE)
    assert not holds_move_cursor(sample(**changed), MOVE)
    assert not holds_move_cursor(sample(), None)


@pytest.mark.parametrize(
    "changed, pressed",
    [
        ({}, True),
        ({"buttons": LEFT}, False),
        ({"receiver_window": MOVE}, False),
        ({"override": MOVE}, False),
        ({"press_widget": MOVE}, False),
        ({"press_owns_cursor": True}, False),
        ({"outside_widget": MOVE}, False),
    ],
    ids=["Druck", "Taste", "Fenster", "Override", "Widget", "Besitz", "Außenwidget"],
)
def test_the_return_judgement_needs_every_part(changed: dict[str, Any], pressed: bool) -> None:
    """Nach dem Release muss alles zurück sein; jede einzelne Abweichung ist rot."""
    before = sample(receiver_window=ARROW, press_widget=ARROW, press_owns_cursor=False, buttons=0)
    returned = {**before}
    assert returns_cursor(before, returned, pressed_after=False, expected=MOVE)
    assert not returns_cursor(before, {**before, **changed}, pressed_after=pressed, expected=MOVE)


def event(level: str, name: str, point: list[int], *, buttons: int, release: bool = False) -> dict:
    row: dict[str, Any] = {
        "receiver_level": level,
        "event_name": name,
        "point": point,
        "buttons": buttons,
    }
    if release:
        row["button"] = str(Qt.MouseButton.LeftButton)
    return row


def test_the_transport_needs_four_held_moves_and_a_release_on_each_level() -> None:
    """Je Ebene vier gehaltene Bewegungen in Folge und danach das Release am letzten Punkt."""
    targets = [[10, 10], [20, 20], [30, 30], [40, 40]]
    events = []
    for point in targets:
        events.append(event("window", "MouseMove", point, buttons=LEFT))
        events.append(event("widget", "MouseMove", point, buttons=LEFT))
    events.append(event("window", "MouseButtonRelease", targets[-1], buttons=0, release=True))
    events.append(event("widget", "MouseButtonRelease", targets[-1], buttons=0, release=True))
    transport = transport_of(events, targets)
    assert transport["window"] == {"move_indices": [0, 2, 4, 6], "release_index": 8}
    assert transport["widget"] == {"move_indices": [1, 3, 5, 7], "release_index": 9}
    # Gegenprobe: eine Bewegung ohne gehaltene Taste und ein Release an anderer Stelle zählen nicht.
    events[3]["buttons"] = 0
    events[9]["point"] = [41, 40]
    broken = transport_of(events, targets)
    assert broken["widget"]["move_indices"] == [1]
    assert broken["widget"]["release_index"] is None
    assert broken["window"] == transport["window"]
