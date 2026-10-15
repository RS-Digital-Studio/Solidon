"""Platzbedarf und Notanordnung der Maßfelder, ohne Fenster gerechnet (FD-84).

Die Rechnung steht in ``app.ui.measure_field_places``; wie ``PlacementFlow``
sie im echten Maßfluss nutzt, prüft ``tests/test_measure_card_placement.py``.
"""

from itertools import combinations

from PySide6.QtCore import QPoint, QRect, QSize

from app.ui.measure_field_places import (
    distance_reserve,
    emergency_places,
    grown_place,
    rows_height,
)
from app.ui.style import SPACE


def test_the_rows_of_the_fields_grow_when_they_do_not_fit_side_by_side() -> None:
    """Eine Zeile ist die alte feste Freihaltung; was nicht passt, braucht die nächste."""
    assert rows_height([], 1000) == 0
    assert rows_height([QSize(300, 29)], 1000) == 29 + SPACE
    # Vier Felder füllen 1000 Punkte genau, das fünfte beginnt eine niedrigere Zeile.
    four = [QSize(247, 29)] * 4
    assert rows_height(four, 4 * 247 + 3 * SPACE) == 29 + SPACE
    assert rows_height([*four, QSize(247, 12)], 4 * 247 + 3 * SPACE) == 29 + SPACE + 12 + SPACE
    # Ein Feld breiter als der Raum steht trotzdem in einer eigenen Zeile.
    assert rows_height([QSize(1200, 20), QSize(10, 20)], 1000) == 2 * (20 + SPACE)


def test_the_card_keeps_at_least_one_row_and_otherwise_as_many_as_the_fields_need() -> None:
    """Die Freihaltung unter der Karte fällt nie unter die eine alte Zeile."""
    assert distance_reserve(29, 0) == 29 + SPACE
    assert distance_reserve(29, 29 + SPACE) == 29 + SPACE
    assert distance_reserve(29, 2 * (29 + SPACE)) == 2 * (29 + SPACE)


def test_the_emergency_places_stay_in_view_and_give_up_distance_before_freedom() -> None:
    """Die Notanordnung hält das Bild immer, Karte, Griff und Setzpunkt so lange es geht.

    Bis FD-84 brachen die Notreihen das letzte Feld unter den Bildrand um und
    wichen dem Bewegungsgriff gar nicht aus.
    """
    bounds = QRect(0, 0, 400, 300)
    field = QSize(100, 20)
    # Die Karte bleibt frei, und kein Feld verlässt das Bild — auch das fünfte nicht.
    card = QRect(0, 0, 400, 240)
    places = emergency_places([field] * 5, bounds, [card], ([],))
    assert all(bounds.contains(place) for place in places)
    assert not any(place.intersects(card) for place in places)
    assert len({place.y() for place in places}) == 2
    for first, second in combinations(places, 2):
        assert not first.adjusted(-SPACE, -SPACE, SPACE, SPACE).intersects(second)
    # Mit Abstand passt das Feld nur unter den Griff; ohne Abstand darüber.
    comfort = QRect(0, 10, 400, 260)
    bare = QRect(0, 50, 400, 200)
    (place,) = emergency_places([field], bounds, [], ([comfort], [bare], []))
    assert place.y() > comfort.bottom()
    (place,) = emergency_places([QSize(100, 40)], bounds, [], ([comfort], [bare], []))
    assert not place.intersects(bare) and place.bottom() < bare.top()
    # Füllt der Griff alles, steht das Feld trotzdem im Bild — überdeckend.
    (place,) = emergency_places([field], bounds, [], ([bounds], [bounds], []))
    assert place == QRect(bounds.topLeft(), field)
    # Selbst ohne jeden freien Platz bleibt es im Bild und nicht darunter.
    (place,) = emergency_places([field], bounds, [bounds], ([],))
    assert bounds.contains(place)


def test_a_field_without_room_covers_another_field_rather_than_the_card() -> None:
    """Unter der vom Kunden gelegten Karte verschwände ein Kantenmaß ganz. Ist neben
    der Karte kein freier Platz mehr, steht ein Feld deshalb versetzt über den Feldern
    — aber nie genau auf einem: Kein Feld deckt ein anderes ganz (Schlussreview D0,
    RF-12, RF-16; bis RF-16 lag das zweite Feld deckungsgleich auf dem ersten).

    Unter der Karte bleibt eine Zeile für genau ein Feld: Das erste nimmt sie, das
    zweite findet weder mit noch ohne Abstand Platz und rückt an den unteren
    Bildrand. Im Streifen für fünf Felder stehen das sechste und siebte je über der
    Fuge zweier Felder.
    """
    bounds = QRect(0, 0, 400, 300)
    card = QRect(0, 0, 400, 240)
    field = QSize(400, 40)
    first, second = emergency_places([field, field], bounds, [card], ([],))
    below = card.bottom() + SPACE + 1
    assert first == QRect(QPoint(0, below), field)
    assert second == QRect(QPoint(0, bounds.bottom() - field.height() + 1), field)
    assert not second.intersects(card)

    strip = QRect(0, 0, 770, 520)
    places = emergency_places([QSize(150, 26)] * 7, strip, [QRect(0, 0, 770, 490)], ([],))
    assert all(strip.contains(place) and place.top() > 489 for place in places)
    for one, other in combinations(places, 2):
        assert one.intersected(other) not in (one, other), (one, other)
    sixth, seventh = places[5:]
    assert sixth.left() == places[0].left() + 75 and seventh.left() == places[1].left() + 75


def test_a_grown_card_keeps_its_corner_and_moves_only_as_far_as_it_must() -> None:
    """Die gewachsene Karte bleibt stehen und rückt nur um das Nötige (FD-87).

    Bis dahin verlor sie mit der neuen Größe ihren Platz und sprang an den
    nächsten freien, oft an den anderen Bildrand.
    """
    bounds = QRect(0, 0, 1000, 800)
    card = QRect(300, 500, 400, 200)
    # Passt sie, bleibt die Ecke oben links.
    assert grown_place(card, QSize(400, 280), bounds, []) == QRect(300, 500, 400, 280)
    # Ragt sie unten hinaus, rückt sie genau um den Überstand hoch.
    assert grown_place(card, QSize(400, 350), bounds, []) == QRect(300, 450, 400, 350)
    # Ein Hindernis im Weg schiebt sie nur bis an seinen Rand, mit Abstand.
    grip = QRect(300, 460, 100, 50)
    assert grown_place(card, QSize(400, 350), bounds, [grip]) == QRect(
        300 + 100 + SPACE, 450, 400, 350
    )
    # Was nirgends frei ist, behält keinen Platz.
    assert grown_place(card, QSize(400, 350), bounds, [bounds]) is None
    # Größer als der Raum findet sie keinen.
    assert grown_place(card, QSize(1200, 200), bounds, []) is None
