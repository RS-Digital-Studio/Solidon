"""Wo die Quittung über der Ansicht steht — ohne Fenster (FD-108, FD-162).

``free_spot`` sucht die freie Stelle nächst dem Ort der Handlung; eine Karte
darf sie nie verdecken. Gerechnet wird mit Rechtecken als Tupeln.
"""

from __future__ import annotations

from app.ui.action_notice import free_spot

ROOM = (1600, 900)
REPORT = (1200, 0, 400, 900)
"""Die rechte Karte mit dem Prüfbericht, über die volle Höhe."""


def _overlaps(spot: tuple[int, int], size: tuple[int, int], rect: tuple[int, ...]) -> bool:
    left, top = spot
    return (
        left < rect[0] + rect[2]
        and rect[0] < left + size[0]
        and top < rect[1] + rect[3]
        and rect[1] < top + size[1]
    )


def test_a_click_in_the_report_puts_the_reply_beside_it() -> None:
    size = (300, 40)
    anchor = (1400, 450)
    spot = free_spot(size, anchor, ROOM, [REPORT], gap=12)
    assert spot is not None
    assert not _overlaps(spot, size, REPORT), "nie über der Karte"
    assert spot[0] + size[0] <= REPORT[0] - 12, "links daneben, mit Abstand"
    assert abs(spot[1] + size[1] // 2 - anchor[1]) <= size[1], "auf der Höhe der Handlung"


def test_a_reply_in_the_free_view_stays_at_the_pointer() -> None:
    size = (300, 40)
    spot = free_spot(size, (600, 300), ROOM, [REPORT], gap=12)
    assert spot == (600, 312)


def test_a_card_in_the_view_is_an_obstacle_too() -> None:
    size = (300, 40)
    card = (500, 250, 420, 300)
    anchor = (700, 400)
    spot = free_spot(size, anchor, ROOM, [REPORT, card], gap=12)
    assert spot is not None
    assert not any(_overlaps(spot, size, rect) for rect in (REPORT, card))


def test_without_room_there_is_no_bubble() -> None:
    assert free_spot((300, 40), (100, 100), (200, 100), []) is None
    full = [(0, 0, 1600, 900)]
    assert free_spot((300, 40), (100, 100), ROOM, full) is None
