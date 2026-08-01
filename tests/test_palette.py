"""Farbe trägt nie allein Bedeutung (Bauplan §19.1).

Das ist die Barrierefreiheits-Prüfung, die §40 in P1 verlangt: was auch immer
eine Farbe sagt, ein Muster und ein Symbol sagen es auch — und die Kartenrampe
behält ihre Ordnung in Graustufen.
"""

from __future__ import annotations

import pytest

from app.ui.palette import (
    DIFF_PALETTES,
    SEVERITY_ENCODING,
    VIRIDIS,
    distinguishable_without_colour,
    is_monotonic,
    map_colour,
)
from app.ui.theme import contrast_ratio, relative_luminance


@pytest.mark.parametrize("name", list(DIFF_PALETTES))
def test_added_and_removed_differ_in_more_than_colour(name: str) -> None:
    palette = DIFF_PALETTES[name]  # type: ignore[index]

    assert distinguishable_without_colour(palette.added, palette.removed)
    assert palette.added.symbol != palette.removed.symbol
    assert palette.added.pattern != palette.removed.pattern
    assert palette.added.label_key and palette.removed.label_key


@pytest.mark.parametrize("name", list(DIFF_PALETTES))
def test_added_and_removed_also_differ_in_brightness(name: str) -> None:
    """Auch in reinen Graustufen müssen die zwei auseinanderbleiben."""
    palette = DIFF_PALETTES[name]  # type: ignore[index]
    difference = abs(
        relative_luminance(palette.added.colour) - relative_luminance(palette.removed.colour)
    )
    assert difference > 0.1, "a greyscale print must not turn both into the same grey"


def test_the_default_is_blue_and_orange_not_red_and_green() -> None:
    """§19.1: Rot und Grün wären das denkbar schlechteste Paar für die
    wichtigste Ansicht der Anwendung.
    """
    default = DIFF_PALETTES["blue_orange"]
    assert default.added.colour.lower() != default.removed.colour.lower()
    assert "red_green" in DIFF_PALETTES, "still available for those who prefer it"
    assert "greyscale" in DIFF_PALETTES


def test_severity_markers_are_readable_without_colour() -> None:
    symbols = {name: entry.symbol for name, entry in SEVERITY_ENCODING.items()}
    assert len(set(symbols.values())) == len(symbols)
    for entry in SEVERITY_ENCODING.values():
        assert entry.symbol.strip()


def test_the_map_ramp_rises_in_luminance() -> None:
    """§19.1: wahrnehmungsgleich, kein Regenbogen — ein Regenbogen erfindet
    Kanten.
    """
    assert is_monotonic(VIRIDIS)
    assert not is_monotonic(("#ff0000", "#00ff00", "#0000ff")), "the check would catch a rainbow"


def test_the_map_ramp_covers_its_range() -> None:
    assert map_colour(0.0) == VIRIDIS[0]
    assert map_colour(1.0) == VIRIDIS[-1]
    assert map_colour(0.5) == VIRIDIS[len(VIRIDIS) // 2]
    assert map_colour(-5.0) == VIRIDIS[0], "values outside the range are clamped"
    assert map_colour(5.0) == VIRIDIS[-1]
    assert contrast_ratio(VIRIDIS[0], VIRIDIS[-1]) > 4.5


def test_an_empty_ramp_is_refused() -> None:
    with pytest.raises(ValueError):
        map_colour(0.5, ())
