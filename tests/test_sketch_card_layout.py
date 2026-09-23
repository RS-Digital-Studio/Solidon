"""Karten im Skizzenmodus liegen nie übereinander.

Gefunden an der Website-Aufnahme für 0.5.0: In der Draufsicht standen
„Hochziehen" und „Abtragen" deckungsgleich in der Kreismitte und lasen sich
als „Hablziehen". Die beiden Anker des Ziehgriffs unterscheiden sich nur
entlang der Ebenennormalen, und die ist in der Draufsicht die Blickrichtung.
Dasselbe trifft jede Maßkarte, die an denselben Ort fällt.

Alle Tests hier kommen ohne Fenster aus: Die Platzierung ist eine reine
Rechnung in Bildpunkten, die Umrechnung in Weltpunkte läuft über das
Renderer-Doppel.
"""

from itertools import combinations

import pytest

from app.ui.viewport import place_sketch_cards, spread_sketch_cards
from tests.render_fakes import RecordingRenderer


def card(centre: tuple[float, float], size: tuple[float, float]) -> tuple[float, ...]:
    """Das Lesefeld einer Karte, deren Text mittig auf ``centre`` steht."""
    return (
        centre[0] - size[0] / 2.0,
        centre[1] - size[1] / 2.0,
        centre[0] + size[0] / 2.0,
        centre[1] + size[1] / 2.0,
    )


def overlaps(first: tuple[float, ...], second: tuple[float, ...]) -> bool:
    """Ob zwei Lesefelder mehr als ihren Rand gemeinsam haben."""
    return (
        first[0] < second[2]
        and first[2] > second[0]
        and first[1] < second[3]
        and first[3] > second[1]
    )


def test_two_cards_at_the_same_spot_stand_apart() -> None:
    """Der Befund in Reinform: zwei Karten, ein Anker — beide lesbar."""
    sizes = [(90.0, 22.0), (80.0, 22.0)]
    centres = spread_sketch_cards([(400.0, 300.0), (400.0, 300.0)], sizes, gap=4.0)
    assert not overlaps(card(centres[0], sizes[0]), card(centres[1], sizes[1]))
    # Die erste bleibt, wo sie hingehört; die zweite rückt nur so weit wie nötig.
    assert centres[0] == pytest.approx((400.0, 300.0))
    assert abs(centres[1][0] - 400.0) + abs(centres[1][1] - 300.0) <= 22.0 + 4.0 + 1e-9


def test_cards_that_do_not_touch_stay_on_their_anchors() -> None:
    """Wer Platz hat, wird nicht verschoben — die Maßkarte bleibt auf ihrer Linie."""
    anchors = [(100.0, 100.0), (300.0, 100.0), (100.0, 300.0)]
    centres = spread_sketch_cards(anchors, [(60.0, 20.0)] * 3, gap=4.0)
    for centre, anchor in zip(centres, anchors, strict=True):
        assert centre == pytest.approx(anchor)


def test_many_cards_in_one_spot_never_overlap() -> None:
    """Auch ein dichtes Bündel wird aufgefächert, keine Karte fällt weg."""
    sizes = [(70.0 + 5.0 * index, 20.0) for index in range(12)]
    anchors = [(500.0 + index % 3, 400.0) for index in range(12)]
    centres = spread_sketch_cards(anchors, sizes, gap=4.0)
    assert len(centres) == 12
    fields = [card(centre, size) for centre, size in zip(centres, sizes, strict=True)]
    assert not any(overlaps(first, second) for first, second in combinations(fields, 2))


def test_a_card_that_only_grazes_its_neighbour_moves_off_it() -> None:
    """Halb überdeckt ist genauso unlesbar wie ganz überdeckt."""
    sizes = [(80.0, 20.0), (80.0, 20.0)]
    centres = spread_sketch_cards([(200.0, 200.0), (240.0, 206.0)], sizes, gap=4.0)
    assert not overlaps(card(centres[0], sizes[0]), card(centres[1], sizes[1]))


def test_the_pull_labels_of_a_top_view_land_on_two_readable_spots() -> None:
    """Die Anker des Ziehgriffs: gleiches x und y, nur die Höhe verschieden.

    Das Doppel bildet wie die Draufsicht ab — ``world_to_display`` sieht die
    Höhe nicht. Ohne Platzierung stünden beide Karten auf demselben Bildpunkt.
    """
    renderer = RecordingRenderer(size=(800, 600), scale=2.0)
    outward = (12.0, 0.0, 6.0)
    inward = (12.0, 0.0, -6.0)
    sizes = [(90.0, 22.0), (80.0, 22.0)]
    points = place_sketch_cards(renderer, [outward, inward], sizes, gap=4.0)
    shown = [renderer.world_to_display(point)[:2] for point in points]
    assert not overlaps(card(shown[0], sizes[0]), card(shown[1], sizes[1]))
    # Die erste Karte bleibt genau an ihrem Weltpunkt.
    assert points[0] == pytest.approx(outward)
    # Verschoben wird nur im Bild, die Tiefe des Ankers bleibt dieselbe.
    assert points[1][2] == pytest.approx(inward[2])


def test_without_cards_nothing_is_placed() -> None:
    """Leere Skizze, leere Liste — kein Sonderfall im Aufrufer."""
    assert spread_sketch_cards([], [], gap=4.0) == []
    assert place_sketch_cards(RecordingRenderer(), [], [], gap=4.0) == []
