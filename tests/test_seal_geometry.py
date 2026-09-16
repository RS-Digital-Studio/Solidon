"""Dichtquerschnitte gegen unabhängige Ringmaße und echte Durchgängigkeit."""

import math

import numpy as np
import pytest
from shapely.geometry import Point

from app.core.errors import ValidationError
from app.core.geom.seal import seal_geometry
from app.core.sketch import shapes
from app.core.sketch.profile import profile_of
from app.core.sketch.solver import solve_sketch
from app.core.slice.analysis import cross_section


def path(sketch=None):
    return profile_of(solve_sketch(sketch or shapes.circle(40)))


@pytest.mark.parametrize("section", ["rectangle", "round"])
def test_circle_seal_has_measured_width_depth_protrusion_and_analytic_volume(section):
    result = seal_geometry(
        path(),
        groove_width=3,
        groove_depth=2,
        protrusion=0.4,
        gasket_width=2.6,
        section=section,
    )
    assert result.groove.is_watertight and result.gasket.is_watertight
    assert result.groove.component_count == result.gasket.component_count == 1
    assert result.groove.volume == pytest.approx(240 * math.pi, rel=0.001)
    assert result.groove.bounds.minimum[2] == pytest.approx(-2)
    assert result.groove.bounds.maximum[2] == pytest.approx(0)
    assert result.gasket.bounds.minimum[2] == pytest.approx(-2)
    assert result.gasket.bounds.maximum[2] == pytest.approx(0.4)
    if section == "rectangle":
        assert result.gasket.volume == pytest.approx(249.6 * math.pi, rel=0.001)
        assert result.gasket.bounds.size[:2] == pytest.approx((42.6, 42.6), abs=0.02)
        assert result.clearance == pytest.approx(0.2)
    else:
        assert result.gasket.volume == pytest.approx(57.6 * math.pi**2, rel=0.012)
        assert result.gasket.bounds.size[:2] == pytest.approx((42.4, 42.4), abs=0.02)
        assert result.clearance == pytest.approx(0.3)
    # Der gemeinsame Innenraum bleibt über die ganze Höhe offen.
    for z in (-1.0, 0.0):
        sliced = cross_section(result.gasket, z)
        assert sliced is not None and not sliced.contains(Point(0, 0))


@pytest.mark.parametrize("section", ["rectangle", "round"])
def test_rectangular_path_keeps_a_closed_hole_and_does_not_round_the_path_away(section):
    result = seal_geometry(
        path(shapes.rectangle(40, 30)),
        groove_width=3,
        groove_depth=2,
        protrusion=0.4,
        gasket_width=2.6,
        section=section,
    )
    assert result.groove.is_watertight and result.gasket.is_watertight
    assert result.groove.component_count == result.gasket.component_count == 1
    assert result.groove.bounds.size == pytest.approx((43, 33, 2), abs=0.02)
    sliced = cross_section(result.gasket, -1)
    assert sliced is not None and not sliced.contains(Point(0, 0))


def test_signed_path_offset_changes_both_rings_by_the_same_normal_distance():
    original = seal_geometry(
        path(), groove_width=3, groove_depth=2, protrusion=0.4, gasket_width=2.6
    )
    moved = seal_geometry(
        path(), groove_width=3, groove_depth=2, protrusion=0.4, gasket_width=2.6, offset=5
    )
    assert np.array(moved.groove.bounds.size[:2]) - original.groove.bounds.size[
        :2
    ] == pytest.approx((10, 10), abs=0.02)
    assert np.array(moved.gasket.bounds.size[:2]) - original.gasket.bounds.size[
        :2
    ] == pytest.approx((10, 10), abs=0.02)
    assert moved.clearance == pytest.approx(original.clearance)


@pytest.mark.parametrize(
    "changes",
    [
        {"groove_width": 0},
        {"groove_depth": 0},
        {"protrusion": -0.1},
        {"gasket_width": 4},
        {"groove_width": 2, "section": "round"},
        {"offset": -25},
        {"groove_width": 50},
        {"groove_depth": float("inf")},
        {"section": "unknown"},
    ],
)
def test_invalid_or_collapsed_seals_are_explained(changes):
    with pytest.raises(ValidationError) as caught:
        seal_geometry(
            path(),
            **{
                "groove_width": 3,
                "groove_depth": 2,
                "protrusion": 0.4,
                "gasket_width": 2.6,
                **changes,
            },
        )
    assert caught.value.suggestions


def test_build_checks_cancellation_before_preparing_geometry():
    def stop():
        raise InterruptedError("cancelled")

    with pytest.raises(InterruptedError, match="cancelled"):
        seal_geometry(
            path(),
            groove_width=3,
            groove_depth=2,
            protrusion=0.4,
            gasket_width=2.6,
            check_cancelled=stop,
        )


@pytest.mark.parametrize("height", [1.2, 12.0])
def test_round_sweep_does_not_leave_short_inner_walls_or_intersections_at_capsule_seams(height):
    from app.core.knowledge.parts.range_check import has_self_intersections, local_wall_thickness

    result = seal_geometry(
        path(),
        groove_width=height,
        groove_depth=height,
        protrusion=0,
        gasket_width=height,
        section="round",
        offset=5,
    )
    assert local_wall_thickness(result.gasket) > height * 0.9
    assert not has_self_intersections(result.gasket)
