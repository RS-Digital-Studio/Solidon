"""Farbe, die nie allein Bedeutung trägt (Bauplan §19.1).

Die Differenzansicht ist die wichtigste Ansicht der Anwendung — und in Rot und
Grün wäre sie die denkbar schlechteste Kombination für Farbenblindheit. Also
sind Blau und Orange die Vorgabe, Rot/Grün und Graustufen sind Alternativen,
und **jedes** Paar trägt neben seiner Farbe ein Muster und ein Symbol.

Analysekarten benutzen eine wahrnehmungsgleiche Rampe (Viridis-Art), nie einen
Regenbogen: ein Regenbogen erfindet Kanten, wo die Daten keine haben, und in
Graustufen verliert er seine Ordnung ganz.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Literal

from app.ui.theme import relative_luminance

DiffPalette = Literal["blue_orange", "red_green", "greyscale"]


@dataclass(frozen=True, slots=True)
class Encoding:
    """Eine Bedeutung: Farbe plus mindestens ein weiterer Kanal (§19.1)."""

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
    """Hinzugekommenes und entferntes Volumen in der
    Differenzansicht (§18.7).
    """

    added: Encoding
    removed: Encoding
    unchanged: Encoding


#: Blau und Orange als Vorgabe — unter jeder verbreiteten Farbschwäche
#: unterscheidbar, und in Graustufen über die Helligkeit weiterhin auch.
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

#: Viridis, abgetastet. Die monoton steigende Helligkeit ist es, die es für
#: alle lesbar und in Graustufen druckbar macht.
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

#: Zeichen für die Schweregrade. Der Prüfbericht zeigt sie neben dem Text,
#: nie als Farbe allein.
SEVERITY_ENCODING: dict[str, Encoding] = {
    "info": Encoding("#6da3d6", "solid", "·", "Hinweis"),
    "warning": Encoding("#e0a33c", "dots", "!", "Warnung"),
    "error": Encoding("#d05a5a", "backward", "X", "Fehler"),
}


def map_colour(fraction: float, ramp: tuple[str, ...] = VIRIDIS) -> str:
    """Farbe für einen Wert zwischen 0 und 1 auf einer wahrnehmungsgleichen
    Rampe.
    """
    if not ramp:
        raise ValueError("a ramp needs at least one colour")
    position = min(max(fraction, 0.0), 1.0) * (len(ramp) - 1)
    return ramp[round(position)]


def is_monotonic(ramp: tuple[str, ...]) -> bool:
    """True, wenn die Helligkeit Schritt für Schritt steigt — die
    Eigenschaft, die einem Regenbogen fehlt.
    """
    values = [relative_luminance(colour) for colour in ramp]
    return all(later > earlier for earlier, later in pairwise(values))


def distinguishable_without_colour(first: Encoding, second: Encoding) -> bool:
    """Zwei Bedeutungen bleiben auseinander, auch wenn sich die Farben nicht
    unterscheiden lassen (§19.1).
    """
    return first.pattern != second.pattern and first.symbol != second.symbol
