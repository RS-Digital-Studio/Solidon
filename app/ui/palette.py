"""Colour that never carries meaning alone (Bauplan §19.1).

The difference view is the most important view in the application — and in red
and green it would be the worst possible combination for colour blindness. So
blue and orange are the default, red/green and greyscale are alternatives, and
**every** pair carries a pattern and a symbol besides its colour.

Analysis maps use a perceptually uniform ramp (Viridis kind), never a rainbow:
a rainbow invents edges where the data has none, and it loses its order entirely
in greyscale.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from app.ui.theme import relative_luminance

DiffPalette = Literal["blue_orange", "red_green", "greyscale"]


@dataclass(frozen=True, slots=True)
class Encoding:
    """One meaning: colour plus at least one more channel (§19.1)."""

    colour: str
    pattern: str
    """``solid``, ``forward``, ``backward``, ``dots`` — hatching for print and for
    anyone who cannot tell the colours apart."""
    symbol: str
    """A single character shown in legends and labels."""
    label_key: str
    """Message id of the caption, so the legend is readable without colours."""


@dataclass(frozen=True, slots=True)
class DifferenceColours:
    """Added and removed volume in the difference view (§18.7)."""

    added: Encoding
    removed: Encoding
    unchanged: Encoding


#: Blue and orange by default — distinguishable under every common colour vision
#: deficiency, and still distinguishable in greyscale by luminance.
DIFF_PALETTES: dict[DiffPalette, DifferenceColours] = {
    "blue_orange": DifferenceColours(
        added=Encoding("#3b82c4", "forward", "+", "Hinzugefügt"),
        removed=Encoding("#e08a3c", "backward", "-", "Entfernt"),
        unchanged=Encoding("#9aa3ae", "solid", "=", "Unverändert"),
    ),
    "red_green": DifferenceColours(
        added=Encoding("#2f9e44", "forward", "+", "Hinzugefügt"),
        removed=Encoding("#c92a2a", "backward", "-", "Entfernt"),
        unchanged=Encoding("#9aa3ae", "solid", "=", "Unverändert"),
    ),
    "greyscale": DifferenceColours(
        added=Encoding("#d9d9d9", "forward", "+", "Hinzugefügt"),
        removed=Encoding("#4a4a4a", "backward", "-", "Entfernt"),
        unchanged=Encoding("#9aa3ae", "solid", "=", "Unverändert"),
    ),
}

#: Viridis, sampled. Monotonically rising luminance is what makes it readable
#: for everyone and printable in greyscale.
VIRIDIS: tuple[str, ...] = (
    "#440154",
    "#472d7b",
    "#3b528b",
    "#2c728e",
    "#21918c",
    "#28ae80",
    "#5ec962",
    "#addc30",
    "#fde725",
)

#: Severity markers. The report shows them next to the text, never colour alone.
SEVERITY_ENCODING: dict[str, Encoding] = {
    "info": Encoding("#6da3d6", "solid", "·", "Hinweis"),
    "warning": Encoding("#e0a33c", "dots", "!", "Warnung"),
    "error": Encoding("#d05a5a", "backward", "X", "Fehler"),
}


def map_colour(fraction: float, ramp: tuple[str, ...] = VIRIDIS) -> str:
    """Colour for a value between 0 and 1 on a perceptually uniform ramp."""
    if not ramp:
        raise ValueError("a ramp needs at least one colour")
    position = min(max(fraction, 0.0), 1.0) * (len(ramp) - 1)
    return ramp[round(position)]


def is_monotonic(ramp: tuple[str, ...]) -> bool:
    """True when luminance rises step by step — the property a rainbow lacks."""
    values = [relative_luminance(colour) for colour in ramp]
    return all(later > earlier for earlier, later in pairwise(values))


def distinguishable_without_colour(first: Encoding, second: Encoding) -> bool:
    """Two meanings stay apart even if the colours cannot be told apart (§19.1)."""
    return first.pattern != second.pattern and first.symbol != second.symbol
