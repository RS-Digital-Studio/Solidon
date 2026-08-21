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
from typing import Final, Literal

from app.i18n import _
from app.ui.theme import contrast_ratio, relative_luminance

DiffPalette = Literal["blue_orange", "red_green", "greyscale"]

Role = Literal[
    "select",
    "measure",
    "info",
    "warning",
    "error",
    "layer",
    "island",
    "overhang",
    "feature",
    "backface",
    "axis_x",
    "axis_y",
]

#: Die Farbe je Bedeutung — die eine Stelle, an der eine Rolle ihren Wert
#: bekommt.
#:
#: Vorher hatte „Warnung" drei: ``#e0a33c`` im Prüfbericht und für Inseln,
#: ``#d99048`` in dunklen Zeichnungen, ``#b4611c`` in hellen. „Hinweis" hatte
#: fünf. Gleiche Bedeutung, verschiedene Werte, weil jedes Modul seine eigenen
#: Konstanten führte — und keiner davon war falsch, sie kannten einander nur
#: nicht.
#:
#: **Bernstein ist die Auswahl, und das mit Absicht.** Der Objektbaum färbte
#: blau (Qts Vorgabe), der Viewport orange: dieselbe Handlung, zwei Farben,
#: nichts verband sie. Genommen ist der Ton des Anwendungssymbols — er
#: unterscheidet Solidon vom Qt-Standardblau, das jede zweite Desktop-
#: Anwendung trägt, und er passt zu warmem Filament.
ROLES: dict[Role, str] = {
    "select": "#f0a54a",
    "measure": "#f0a54a",
    "info": "#6da3d6",
    "warning": "#e0a33c",
    "error": "#d05a5a",
    "layer": "#7fb2e5",
    "island": "#e0a33c",
    "overhang": "#d05a5a",
    "feature": "#cfe3f5",
    "backface": "#8b3a3a",
    # Die Achsen einer Skizze. Rot für X, grün für Y — dieselbe Zuordnung wie
    # im Viewport-Würfel und in jedem CAD, das jemand vorher benutzt hat. Sie
    # tragen keine Bedeutung allein über die Farbe: an ihnen steht ihr
    # Buchstabe (Regel 18).
    "axis_x": "#d05a5a",
    "axis_y": "#5aa564",
}


#: Dieselben Bedeutungen, so weit abgedunkelt, wie eine helle Fläche es
#: verlangt.
#:
#: Die Werte in :data:`ROLES` sind für den dunklen Untergrund gewählt, auf dem
#: die Anwendung startet, und dort stimmen sie. Als **Schrift auf Weiß**
#: stimmen sie nicht: Bernstein bringt 2,22, das Hinweisblau 2,67, das
#: Fehlerrot 3,97 — WCAG AA verlangt 4,5. Im Prüfbericht, wo jede Zeile ihre
#: Rollenfarbe trägt, war damit im hellen Thema der gesamte Text unterhalb der
#: Lesbarkeitsgrenze.
#:
#: Der Farbton bleibt, nur die Helligkeit geht so weit herunter, bis 4,5 gegen
#: Weiß steht. Es ist dieselbe Farbe im Sinne der Bedeutung — genau die
#: Rechnung, die ``theme._ACCENT_LINE`` für die Akzentkante schon macht.
ROLES_ON_LIGHT: dict[Role, str] = {
    "info": "#3479ba",
    "warning": "#9d6c19",
    "error": "#cb4a4a",
}

#: Und dieselbe Rechnung in die andere Richtung.
#:
#: Das Fehlerrot ist nicht nur auf Weiß zu schwach — auf der dunklen Liste, mit
#: der die Anwendung startet, bringt es 4,17. Knapp unter der Grenze, und
#: ausgerechnet beim Schweregrad, der am dringendsten gelesen werden will.
#: Aufgehellt sind es 4,52. Die anderen beiden stehen dunkel gut (7,46 und
#: 6,19) und bleiben, wie sie sind.
ROLES_ON_DARK: dict[Role, str] = {
    "error": "#d36363",
}

#: Ab welcher Luminanz eine Fläche als hell gilt. 0,5 ist die Mitte zwischen
#: Schwarz und Weiß; die Flächen beider Themen liegen weit davon entfernt
#: (0,013 gegen 1,0), die Grenze muss also nichts Feines entscheiden.
_LIGHT_SURFACE: Final = 0.5


def text_colour(role: Role, background: str) -> str:
    """Die Farbe einer Rolle, wo sie als **Schrift** auf ``background`` steht.

    Entschieden wird an der Helligkeit des Untergrunds und nicht am Namen des
    Themas: Der Aufrufer kennt die Fläche, auf die er schreibt, immer — sein
    eigenes Widget sagt sie ihm —, das eingestellte Thema kennt er nur über
    Umwege. Und eine Fläche, die aus einem anderen Grund hell ist, bekommt so
    von selbst die richtige Schrift.
    """
    if relative_luminance(background) >= _LIGHT_SURFACE:
        return ROLES_ON_LIGHT.get(role, ROLES[role])
    return ROLES_ON_DARK.get(role, ROLES[role])


#: Die zwei Schriftfarben, zwischen denen eine Beschriftung auf einem Farbfeld
#: wählt.
ON_LIGHT_FIELD: Final = "#101418"
ON_DARK_FIELD: Final = "#f2f4f7"


def readable_on(colour: str) -> str:
    """Dunkle oder helle Schrift — was auf diesem Feld lesbar bleibt (§19.3).

    **Gerechnet statt geschätzt.** Die Entscheidung hing an einer festen
    Luminanzschwelle von 0,35, und eine feste Zahl ist immer nur für eine
    Rampe richtig: Über den mittleren Tönen von Viridis kippte sie auf die
    schlechtere der beiden Schriften — 3,47 bei ``#21918c``, 2,56 bei
    ``#28ae80``. Verglichen wird jetzt, was der Vergleich entscheiden soll.
    """
    if contrast_ratio(ON_LIGHT_FIELD, colour) >= contrast_ratio(ON_DARK_FIELD, colour):
        return ON_LIGHT_FIELD
    return ON_DARK_FIELD


#: Wie dick die drei Rollen der Schichtansicht gezeichnet werden.
#:
#: **Drei Werte, keine zwei gleichen** — das ist die zweite Kodierung, die
#: Regel 18 verlangt. Insel und Überhang lagen beide auf 3: zwei gleich dicke
#: Ringe übereinander, unterschieden allein durch die Farbe, und ausgerechnet
#: bei den zwei Rollen, die eine Handlung nach sich ziehen. Wer Rot und Gelb
#: nicht auseinanderhält, sah eine Schicht voller Ringe und nicht, welcher
#: davon ihn etwas angeht.
#:
#: Sie stehen hier und nicht im Viewport, weil die Leiste dieselbe Zahl für
#: ihre Legende braucht — und eine Legende, die andere Stärken zeigt als das
#: Bild, ist schlimmer als keine.
LAYER_WIDTHS: dict[Role, int] = {"layer": 2, "island": 3, "overhang": 5}


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
    """Message-ID der Beschriftung — so bleibt die Legende ohne Farbe lesbar."""


@dataclass(frozen=True, slots=True)
class DifferenceColours:
    """Hinzugekommenes und entferntes Volumen in der
    Differenzansicht (§18.7).
    """

    added: Encoding
    removed: Encoding
    unchanged: Encoding


#: Die drei Beschriftungen der Legende. Aufgelöst werden sie erst dort, wo sie
#: hingehören — ``tr(encoding.label_key)`` im Viewport. Der Einsammler sieht
#: aber nur Literale, die unmittelbar an ``_`` oder ``tr`` gehen (§37.2), und
#: ein Schlüssel, der nur als Feldwert dasteht, gilt ihm als aufgegeben. Also
#: werden sie hier einmal angemeldet und behalten ihre Message-ID.
ADDED_LABEL: Final = _("Hinzugefügt").msgid
REMOVED_LABEL: Final = _("Entfernt").msgid
UNCHANGED_LABEL: Final = _("Unverändert").msgid

#: Blau und Orange als Vorgabe — unter jeder verbreiteten Farbschwäche
#: unterscheidbar, und in Graustufen über die Helligkeit weiterhin auch.
DIFF_PALETTES: dict[DiffPalette, DifferenceColours] = {
    "blue_orange": DifferenceColours(
        added=Encoding("#3b82c4", "forward", "+", ADDED_LABEL),
        removed=Encoding("#e08a3c", "backward", "-", REMOVED_LABEL),
        unchanged=Encoding("#9aa3ae", "solid", "=", UNCHANGED_LABEL),
    ),
    "red_green": DifferenceColours(
        added=Encoding("#2f9e44", "forward", "+", ADDED_LABEL),
        removed=Encoding("#c92a2a", "backward", "-", REMOVED_LABEL),
        unchanged=Encoding("#9aa3ae", "solid", "=", UNCHANGED_LABEL),
    ),
    "greyscale": DifferenceColours(
        added=Encoding("#d9d9d9", "forward", "+", ADDED_LABEL),
        removed=Encoding("#4a4a4a", "backward", "-", REMOVED_LABEL),
        unchanged=Encoding("#9aa3ae", "solid", "=", UNCHANGED_LABEL),
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
    "info": Encoding(ROLES["info"], "solid", "·", "Hinweis"),
    "warning": Encoding(ROLES["warning"], "dots", "!", "Warnung"),
    "error": Encoding(ROLES["error"], "backward", "X", "Fehler"),
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
