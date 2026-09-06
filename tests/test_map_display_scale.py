"""Der physische Wert und seine Farbdarstellung bleiben zwei Verträge."""

from __future__ import annotations

import math

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive.maps import AnalysisMap, MapScale, curvature_map
from app.core.units import EPS_DISPLAY


def _map(
    values: tuple[float, ...],
    *,
    low: float,
    high: float,
    display_scale: MapScale = "linear",
) -> AnalysisMap:
    return AnalysisMap(
        kind="curvature",
        title="Krümmung",
        values=values,
        unit="mm",
        low=low,
        high=high,
        highlighted=(1, 3),
        display_scale=display_scale,
    )


def test_linear_maps_keep_their_values_and_ticks() -> None:
    analysis = _map((math.nan, 1.0, 2.5, 4.0), low=1.0, high=4.0)

    shown = analysis.display_values()

    assert math.isnan(float(shown[0]))
    np.testing.assert_array_equal(shown[1:], np.asarray((1.0, 2.5, 4.0)))
    assert analysis.display_limits == (1.0, 4.0)
    assert [analysis.value_at_display_fraction(step / 4) for step in range(5)] == [
        1.0,
        1.75,
        2.5,
        3.25,
        4.0,
    ]
    assert analysis.highlighted == (1, 3)


def test_only_the_curvature_result_chooses_the_asinh_scale() -> None:
    analysis = curvature_map(MeshData.of(trimesh.creation.box()))

    assert analysis.display_scale == "asinh"
    assert _map((0.0, 1.0), low=0.0, high=1.0).display_scale == "linear"


def test_asinh_scale_is_finite_at_zero_and_invertible_at_every_legend_tick() -> None:
    physical = (math.nan, 0.0, 1.0, 3.0, 5.5, 6508.77)
    analysis = _map(physical, low=0.0, high=6508.77, display_scale="asinh")

    shown = analysis.display_values()

    assert math.isnan(float(shown[0]))
    assert np.isfinite(shown[1:]).all()
    assert np.all(np.diff(shown[1:]) > 0.0)
    assert analysis.display_limits == pytest.approx((0.0, math.asinh(analysis.high / EPS_DISPLAY)))
    low, high = analysis.display_limits
    for step in range(5):
        fraction = step / 4
        value = analysis.value_at_display_fraction(fraction)
        assert math.asinh(value / EPS_DISPLAY) == pytest.approx(low + (high - low) * fraction)
    assert analysis.value_at_display_fraction(0.0) == pytest.approx(analysis.low)
    assert analysis.value_at_display_fraction(1.0) == pytest.approx(analysis.high)
    assert analysis.highlighted == (1, 3)


def test_garden_hole_radii_no_longer_collapse_into_the_first_colour() -> None:
    """Ø2, Ø6 und Ø11 lagen linear in den ersten 0,1 Prozent der Rampe."""
    radii = (1.0, 3.0, 5.5)
    analysis = _map(radii, low=0.0, high=6508.77, display_scale="asinh")
    low, high = analysis.display_limits

    fractions = (analysis.display_values() - low) / (high - low)

    assert fractions[0] > 0.3
    assert fractions[-1] - fractions[0] > 0.1
    assert np.all(np.diff(fractions) > 0.0)


def test_a_degenerate_range_keeps_its_single_physical_value() -> None:
    analysis = _map((math.nan,), low=0.0, high=0.0, display_scale="asinh")

    assert analysis.display_limits == (0.0, 0.0)
    assert [analysis.value_at_display_fraction(step / 4) for step in range(5)] == [0.0] * 5
