"""Zahlen, Einheiten und die drei benannten Toleranzen (Bauplan §11).

Der Kern rechnet in Millimetern und doppelter Genauigkeit, immer. Eine andere
Anzeigeeinheit ist Sache der Oberfläche und erreicht den Kern nie; umgerechnet
wird genau zweimal: beim Import (§17.1) und bei der Anzeige.

Fließkommawerte werden nie mit ``==`` verglichen (AGENTS.md Regel 6) — dafür
gibt es :func:`is_close`, :func:`is_zero`, :func:`is_greater` und
:func:`is_less`.
"""

from __future__ import annotations

import math
from typing import Final, Literal

# --- Die drei benannten Toleranzen (§11.2) -------------------------------------

#: Zusammenfallende Punkte, Null-Flächen, Verschweißen. Absolut, fürs Fertigen.
EPS_GEOM: Final[float] = 1e-6

#: Rundung für Maße, Steckbrief und Berichte. Absolut, für die Anzeige.
EPS_DISPLAY: Final[float] = 0.01

#: Merkmalsvergleich. Relativ zur Modelldiagonale — siehe :func:`match_tolerance`.
EPS_MATCH_RELATIVE: Final[float] = 0.005

#: Untergrenze der abgeleiteten Vergleichstoleranz, damit winzige Modelle
#: vergleichbar bleiben.
EPS_MATCH_MINIMUM: Final[float] = EPS_DISPLAY

# --- Einheiten -------------------------------------------------------------------

LengthUnit = Literal["mm", "cm", "m", "in"]

#: Skalierungsfaktor nach Millimetern. STL trägt keine Einheit, daher die
#: Heuristik in §17.1.
UNIT_TO_MM: Final[dict[LengthUnit, float]] = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
}

#: Nachkommastellen je Einheit, so gewählt, dass die gezeigte Genauigkeit
#: EPS_DISPLAY entspricht.
_UNIT_DECIMALS: Final[dict[LengthUnit, int]] = {"mm": 2, "cm": 3, "m": 5, "in": 4}

#: Einheiten, die die Oberfläche anbietet (§19.3). Der Kern bleibt bei Millimetern.
DISPLAY_UNITS: Final[tuple[LengthUnit, ...]] = ("mm", "in")


def to_mm(value: float, unit: LengthUnit) -> float:
    """Rechnet eine ankommende Länge in die Kerneinheit um."""
    return value * UNIT_TO_MM[unit]


def from_mm(value_mm: float, unit: LengthUnit) -> float:
    """Rechnet eine Kernlänge in eine Anzeigeeinheit um."""
    return value_mm / UNIT_TO_MM[unit]


# --- Vergleich -------------------------------------------------------------------


def is_close(a: float, b: float, eps: float = EPS_GEOM) -> bool:
    """True, wenn zwei Längen innerhalb von ``eps`` gleich sind."""
    return abs(a - b) <= eps


def is_zero(value: float, eps: float = EPS_GEOM) -> bool:
    return abs(value) <= eps


def is_greater(a: float, b: float, eps: float = EPS_GEOM) -> bool:
    """True, wenn ``a`` um mehr als ``eps`` größer ist als ``b``."""
    return a - b > eps


def is_less(a: float, b: float, eps: float = EPS_GEOM) -> bool:
    return b - a > eps


def clamp(value: float, minimum: float, maximum: float) -> float:
    if minimum > maximum:
        raise ValueError("minimum must not exceed maximum")
    return max(minimum, min(maximum, value))


# --- Abgeleitete Toleranzen ------------------------------------------------------


def match_tolerance(diagonal_mm: float) -> float:
    """Die Vergleichsschwelle der Merkmalszuordnung für ein Modell dieser
    Größe (§21.2).

    Relativ fürs Vergleichen, absolut fürs Fertigen — das ist die Faustregel
    hinter den drei Toleranzen.
    """
    return max(EPS_MATCH_MINIMUM, abs(diagonal_mm) * EPS_MATCH_RELATIVE)


def weld_tolerance(diagonal_mm: float) -> float:
    """Der Verschweißabstand für Eckpunkte, skaliert mit der
    Modellgröße (§17.1 Schritt 2)."""
    return max(EPS_GEOM, abs(diagonal_mm) * 1e-6)


# --- Anzeige -------------------------------------------------------------------


def quantize(value: float, step: float = EPS_DISPLAY) -> float:
    """Rundet auf ein Vielfaches von ``step``, halbe weg von null.

    Nur für die Anzeige. Gerundete Werte fließen nie in Geometrie
    zurück (§11.2).
    """
    if step <= 0.0:
        raise ValueError("step must be positive")
    rounded = math.floor(abs(value) / step + 0.5) * step
    return math.copysign(rounded, value) if rounded else 0.0


def round_display(value_mm: float) -> float:
    """Rundet einen Millimeterwert auf Anzeigegenauigkeit."""
    return quantize(value_mm, EPS_DISPLAY)


def format_volume(value_mm3: float, unit: LengthUnit = "mm") -> str:
    """Ein Volumen in der Einheit, die zur Anzeigelänge passt (§19.3).

    In Millimetern rechnet niemand ein Volumen — Kubikzentimeter sind das
    Maß, in dem Filament verkauft und Verbrauch angegeben wird. Zu Zoll
    gehören Kubikzoll, und der Unterschied ist zu groß, um ihn zu übergehen.
    """
    if unit == "in":
        return f"{value_mm3 / UNIT_TO_MM['in'] ** 3:.2f} in³"
    return f"{value_mm3 / 1000.0:.1f} cm³"


def format_length(value_mm: float, unit: LengthUnit = "mm", with_unit: bool = True) -> str:
    """Formatiert eine Kernlänge für die Anzeige in der gewünschten Einheit.

    Das Dezimaltrennzeichen bleibt hier ein Punkt; lokalisiert wird in der
    Oberfläche, nicht im Kern.
    """
    decimals = _UNIT_DECIMALS[unit]
    converted = from_mm(value_mm, unit)
    text = f"{converted:.{decimals}f}"
    if text.startswith("-") and float(text) == 0.0:
        text = text[1:]
    return f"{text} {unit}" if with_unit else text
