"""Millimetres, double precision, and never a bare ``==`` (Bauplan §11)."""

from __future__ import annotations

import pytest

from app.core.units import (
    EPS_DISPLAY,
    EPS_GEOM,
    clamp,
    format_length,
    from_mm,
    is_close,
    is_greater,
    is_less,
    is_zero,
    match_tolerance,
    quantize,
    round_display,
    to_mm,
    weld_tolerance,
)


def test_import_conversion_hits_the_core_unit() -> None:
    assert to_mm(1.0, "in") == pytest.approx(25.4)
    assert to_mm(1.0, "cm") == pytest.approx(10.0)
    assert to_mm(1.0, "m") == pytest.approx(1000.0)
    assert to_mm(3.5, "mm") == pytest.approx(3.5)


def test_display_conversion_is_the_exact_inverse() -> None:
    for unit in ("mm", "cm", "m", "in"):
        assert from_mm(to_mm(7.25, unit), unit) == pytest.approx(7.25)


def test_comparisons_use_the_geometry_tolerance() -> None:
    assert is_close(1.0, 1.0 + EPS_GEOM / 2)
    assert not is_close(1.0, 1.0 + EPS_GEOM * 10)
    assert is_zero(EPS_GEOM / 2)
    assert is_greater(1.0, 1.0 - 10 * EPS_GEOM)
    assert not is_greater(1.0, 1.0)
    assert is_less(1.0 - 10 * EPS_GEOM, 1.0)


def test_clamp_keeps_the_range() -> None:
    assert clamp(5.0, 0.0, 1.0) == 1.0
    assert clamp(-5.0, 0.0, 1.0) == 0.0
    assert clamp(0.5, 0.0, 1.0) == 0.5
    with pytest.raises(ValueError):
        clamp(0.5, 1.0, 0.0)


def test_match_tolerance_scales_with_the_model() -> None:
    assert match_tolerance(1000.0) == pytest.approx(5.0)
    # Small models never fall below the display tolerance.
    assert match_tolerance(0.1) == pytest.approx(EPS_DISPLAY)


def test_weld_tolerance_never_drops_below_the_geometry_tolerance() -> None:
    assert weld_tolerance(0.0) == EPS_GEOM
    assert weld_tolerance(100.0) == pytest.approx(1e-4)


def test_rounding_happens_only_for_display() -> None:
    assert round_display(4.19999) == pytest.approx(4.2)
    assert round_display(-4.19999) == pytest.approx(-4.2)
    assert quantize(0.005) == pytest.approx(0.01)
    assert quantize(-0.005) == pytest.approx(-0.01)
    with pytest.raises(ValueError):
        quantize(1.0, 0.0)


def test_formatting_matches_the_display_precision() -> None:
    assert format_length(4.2) == "4.20 mm"
    assert format_length(25.4, "in") == "1.0000 in"
    assert format_length(4.2, with_unit=False) == "4.20"
    assert not format_length(-0.001).startswith("-")
