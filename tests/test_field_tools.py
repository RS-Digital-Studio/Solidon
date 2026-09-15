"""Begrenzte Lochfelder erhalten Innenringe, Ausschlüsse und volle Randabstände."""

from __future__ import annotations

from dataclasses import replace

import pytest
from shapely.geometry import Polygon

from app.core.errors import ValidationError
from app.core.geom.field_ops import field_tools
from app.core.geom.sketch_solid import outline_points
from app.core.sketch import shapes
from app.core.sketch.profile import Profile, profile_of, shifted
from app.core.sketch.solver import solve_sketch


def rectangle(width=60, depth=60):
    return profile_of(solve_sketch(shapes.rectangle(width, depth)))


def test_circle_field_keeps_the_full_foot_exclusion_and_perimeter():
    field = field_tools(
        (rectangle(),), (Profile(circle=((0, 0), 6)),), diameter=6, spacing=10, margin=2, web=1
    )
    assert len(field.profiles) == 20
    assert (0, 0) not in field.centres
    assert all(abs(x) <= 20 and abs(y) <= 20 for x, y in field.centres)
    assert field == field_tools(
        (rectangle(),), (Profile(circle=((0, 0), 6)),), diameter=6, spacing=10, margin=2, web=1
    )


def test_inner_ring_stays_a_hole_and_separate_regions_do_not_get_joined():
    ring = replace(rectangle(), holes=(Profile(circle=((0, 0), 8)),))
    remote = shifted(rectangle(20, 20), 80, 0)
    field = field_tools((ring, remote), (), diameter=6, spacing=10, margin=2, web=1)
    assert any(x >= 70 for x, _ in field.centres)
    assert all(x * x + y * y >= 100 for x, y in field.centres)
    assert not any(30 < x < 70 for x, _ in field.centres)


@pytest.mark.parametrize(
    "shape,pattern", [("circle", "grid"), ("slot", "grid"), ("hexagon", "staggered")]
)
def test_every_shape_keeps_full_outline_and_web(shape, pattern):
    field = field_tools(
        (rectangle(60, 40),),
        (),
        diameter=6,
        spacing=12,
        margin=2,
        web=1,
        shape=shape,
        pattern=pattern,
        slot_length=9,
    )
    region = Polygon(outline_points(rectangle(60, 40))).buffer(-2)
    polygons = [Polygon(outline_points(profile)) for profile in field.profiles]
    assert polygons
    assert all(region.covers(poly) for poly in polygons)
    assert all(
        a.distance(b) >= 1 for index, a in enumerate(polygons) for b in polygons[index + 1 :]
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"spacing": 6},
        {"diameter": float("nan")},
        {"web": -1},
        {"shape": "code"},
        {"pattern": "random"},
        {"spacing": 0.01},
    ],
)
def test_invalid_or_overlapping_field_is_rejected_before_geometry(changes):
    with pytest.raises(ValidationError):
        field_tools(
            (rectangle(),), (), **{"diameter": 6, "spacing": 10, "margin": 2, "web": 1, **changes}
        )


def test_window_changes_preserve_grid_phase_and_origin():
    before = field_tools(
        (rectangle(),), (), diameter=6, spacing=10, margin=2, web=1, origin=(2, -3)
    )
    after = field_tools(
        (rectangle(80, 70),), (), diameter=6, spacing=10, margin=2, web=1, origin=(2, -3)
    )
    assert set(before.centres) < set(after.centres)


@pytest.mark.parametrize("pattern", ["grid", "staggered"])
def test_nonzero_origin_is_applied_once_to_each_grid_axis(pattern):
    import math

    field = field_tools(
        (rectangle(60, 60),),
        (),
        diameter=2,
        spacing=10,
        margin=1,
        web=1,
        origin=(2, 3),
        pattern=pattern,
    )
    pitch = 10 if pattern == "grid" else 5 * math.sqrt(3)
    # Unabhängige ganzzahlige Gitterkoordinaten; keine Rasterhelfer wiederverwenden.
    expected = sorted(
        (2 + 10 * column + (5 if pattern == "staggered" and row % 2 else 0), 3 + row * pitch)
        for row in range(-4, 4)
        for column in range(-4, 4)
        if abs(2 + 10 * column + (5 if pattern == "staggered" and row % 2 else 0)) < 28
        and abs(3 + row * pitch) < 28
    )
    assert len(field.centres) == len(expected)
    for actual, desired in zip(sorted(field.centres), expected, strict=True):
        assert actual == pytest.approx(desired)
    assert (2, 3) in field.centres


def test_curved_boundary_is_checked_against_the_full_circle_not_only_its_center():
    import math

    field = field_tools((Profile(circle=((0, 0), 25)),), (), diameter=6, spacing=8, margin=2, web=1)
    assert all(math.hypot(x, y) + 3 <= 23 for x, y in field.centres)
    assert (16, 16) not in field.centres


@pytest.mark.parametrize("exact", [False, True])
def test_spline_region_uses_the_corresponding_cutting_boundary(exact):
    from app.core.sketch.profile import ProfileSegment

    profile = Profile(
        segments=(
            ProfileSegment(
                "spline", (-30, 0), (30, 0), through=((-30, 0), (-10, 16), (10, 16), (30, 0))
            ),
            ProfileSegment("line", (30, 0), (30, -20)),
            ProfileSegment("line", (30, -20), (-30, -20)),
            ProfileSegment("line", (-30, -20), (-30, 0)),
        )
    )
    field = field_tools((profile,), (), diameter=4, spacing=8, margin=2, web=1, exact=exact)
    if exact:
        from app.core.brep import edit, profiles

        allowed = profiles.extrude(profile, 1)
        for cut in field.profiles:
            tool = profiles.extrude(cut, 1)
            assert edit.boolean("difference", [tool, allowed]).volume == pytest.approx(0)
    else:
        allowed = Polygon(outline_points(profile)).buffer(-2)
        assert all(allowed.covers(Polygon(outline_points(tool))) for tool in field.profiles)
