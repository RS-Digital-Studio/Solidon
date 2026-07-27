"""Numbers, units and the three named tolerances (Bauplan §11).

The core computes in millimetres and double precision, always. A different
display unit is a surface concern and never reaches the core; conversion happens
exactly twice: on import (§17.1) and on display.

Floating point values are never compared with ``==`` (AGENTS.md rule 6) — use
:func:`is_close`, :func:`is_zero`, :func:`is_greater` or :func:`is_less`.
"""

from __future__ import annotations

import math
from typing import Final, Literal

# --- The three named tolerances (§11.2) --------------------------------------

#: Coincident points, zero-area faces, welding. Absolute, for manufacturing.
EPS_GEOM: Final[float] = 1e-6

#: Rounding for dimensions, digest and reports. Absolute, for display.
EPS_DISPLAY: Final[float] = 0.01

#: Feature comparison. Relative to the model diagonal — see :func:`match_tolerance`.
EPS_MATCH_RELATIVE: Final[float] = 0.005

#: Lower bound for the derived match tolerance, so tiny models stay comparable.
EPS_MATCH_MINIMUM: Final[float] = EPS_DISPLAY

# --- Units ---------------------------------------------------------------------

LengthUnit = Literal["mm", "cm", "m", "in"]

#: Scale factor into millimetres. STL carries no unit, hence the heuristic in §17.1.
UNIT_TO_MM: Final[dict[LengthUnit, float]] = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
}

#: Decimal places per unit, chosen so the shown precision matches EPS_DISPLAY.
_UNIT_DECIMALS: Final[dict[LengthUnit, int]] = {"mm": 2, "cm": 3, "m": 5, "in": 4}

#: Units offered in the surface (§19.3). The core stays on millimetres.
DISPLAY_UNITS: Final[tuple[LengthUnit, ...]] = ("mm", "in")


def to_mm(value: float, unit: LengthUnit) -> float:
    """Convert an incoming length into the core unit."""
    return value * UNIT_TO_MM[unit]


def from_mm(value_mm: float, unit: LengthUnit) -> float:
    """Convert a core length into a display unit."""
    return value_mm / UNIT_TO_MM[unit]


# --- Comparison ----------------------------------------------------------------


def is_close(a: float, b: float, eps: float = EPS_GEOM) -> bool:
    """True if two lengths are the same within ``eps``."""
    return abs(a - b) <= eps


def is_zero(value: float, eps: float = EPS_GEOM) -> bool:
    return abs(value) <= eps


def is_greater(a: float, b: float, eps: float = EPS_GEOM) -> bool:
    """True if ``a`` is larger than ``b`` by more than ``eps``."""
    return a - b > eps


def is_less(a: float, b: float, eps: float = EPS_GEOM) -> bool:
    return b - a > eps


def clamp(value: float, minimum: float, maximum: float) -> float:
    if minimum > maximum:
        raise ValueError("minimum must not exceed maximum")
    return max(minimum, min(maximum, value))


# --- Derived tolerances --------------------------------------------------------


def match_tolerance(diagonal_mm: float) -> float:
    """Feature matching threshold for a model of this size (§21.2).

    Relative for comparisons, absolute for manufacturing — that is the rule of
    thumb behind the three tolerances.
    """
    return max(EPS_MATCH_MINIMUM, abs(diagonal_mm) * EPS_MATCH_RELATIVE)


def weld_tolerance(diagonal_mm: float) -> float:
    """Vertex welding distance, scaled to the model size (§17.1 step 2)."""
    return max(EPS_GEOM, abs(diagonal_mm) * 1e-6)


# --- Display -------------------------------------------------------------------


def quantize(value: float, step: float = EPS_DISPLAY) -> float:
    """Round to a multiple of ``step``, half away from zero.

    Used for display only. Rounded values never flow back into geometry (§11.2).
    """
    if step <= 0.0:
        raise ValueError("step must be positive")
    rounded = math.floor(abs(value) / step + 0.5) * step
    return math.copysign(rounded, value) if rounded else 0.0


def round_display(value_mm: float) -> float:
    """Round a millimetre value to display precision."""
    return quantize(value_mm, EPS_DISPLAY)


def format_length(value_mm: float, unit: LengthUnit = "mm", with_unit: bool = True) -> str:
    """Format a core length for display in the requested unit.

    The decimal separator stays a point here; localisation happens in the
    surface, not in the core.
    """
    decimals = _UNIT_DECIMALS[unit]
    converted = from_mm(value_mm, unit)
    text = f"{converted:.{decimals}f}"
    if text.startswith("-") and float(text) == 0.0:
        text = text[1:]
    return f"{text} {unit}" if with_unit else text
