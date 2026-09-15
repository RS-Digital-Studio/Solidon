"""Gezeichnete Klemmsitze behalten die wirkliche Kurve innerhalb des Sehnenbudgets."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import LineString, Point

from app.core.errors import ValidationError
from app.core.geom import sketch_solid
from app.core.sketch.profile import Profile, ProfileSegment
from app.core.units import EPS_GEOM, MAX_FACET_SAG


@pytest.fixture
def spline_profile():
    case = json.loads(
        (Path(__file__).parent / "data/profile_clamp_reference.json").read_text(encoding="utf-8")
    )
    through = tuple(tuple(point) for point in case["spline_points"])
    return Profile(
        segments=(
            ProfileSegment("spline", through[0], through[-1], through=through),
            ProfileSegment("line", through[-1], through[0]),
        )
    )


def test_spline_sampling_follows_the_curve_instead_of_the_control_polygon(spline_profile):
    """Unabhängige Catmull-Rom-Polynome messen gegen die erzeugten Sehnen."""
    sag = MAX_FACET_SAG / 8.0
    points = sketch_solid.outline_points(spline_profile, max_sag=sag)
    sampled = LineString(points)
    legacy = LineString(sketch_solid.outline_points(spline_profile))
    through = np.asarray(spline_profile.segments[0].through)
    reference = []
    for index in range(len(through) - 1):
        a = through[max(0, index - 1)]
        b, c = through[index : index + 2]
        d = through[min(len(through) - 1, index + 2)]
        for t in np.linspace(0.0, 1.0, 301):
            reference.append(
                0.5
                * (
                    2 * b
                    + (-a + c) * t
                    + (2 * a - 5 * b + 4 * c - d) * t**2
                    + (-a + 3 * b - 3 * c + d) * t**3
                )
            )
    assert max(sampled.distance(Point(point)) for point in reference) <= sag + EPS_GEOM
    assert max(legacy.distance(Point(point)) for point in reference) > MAX_FACET_SAG


@pytest.mark.parametrize("radius", [0.1, 8.0, 1000.0])
def test_circle_sampling_uses_the_requested_actual_sag(radius):
    sag = MAX_FACET_SAG / 8.0
    profile = Profile(circle=((0.0, 0.0), radius))
    points = np.asarray(sketch_solid.outline_points(profile, max_sag=sag))
    midpoints = (points + np.roll(points, 1, axis=0)) / 2.0
    assert np.linalg.norm(points, axis=1) == pytest.approx(radius, abs=EPS_GEOM)
    assert (radius - np.linalg.norm(midpoints, axis=1)).max() <= sag + EPS_GEOM
    assert len(sketch_solid.outline_points(profile)) == sketch_solid.ARC_STEPS


def test_arc_sampling_keeps_the_directed_long_arc():
    profile = Profile(
        segments=(
            ProfileSegment("arc", (10.0, 0.0), (0.0, 10.0), via=(-10.0, 0.0)),
            ProfileSegment("line", (0.0, 10.0), (10.0, 0.0)),
        )
    )
    points = sketch_solid.outline_points(profile, max_sag=MAX_FACET_SAG / 8.0)
    sampled = LineString(points)
    reference = [
        Point(10 * math.cos(theta), 10 * math.sin(theta))
        for theta in np.linspace(0, -3 * math.pi / 2, 501)
    ]
    assert max(sampled.distance(point) for point in reference) <= MAX_FACET_SAG / 8 + EPS_GEOM


@pytest.mark.parametrize("curve", ["circle", "spline"])
def test_sampling_has_a_point_budget_even_for_difficult_curves(monkeypatch, spline_profile, curve):
    monkeypatch.setattr(sketch_solid, "MAX_OUTLINE_POINTS", 20, raising=False)
    profile = Profile(circle=((0.0, 0.0), 1000.0)) if curve == "circle" else spline_profile
    with pytest.raises(ValidationError, match="Vereinfachen"):
        sketch_solid.outline_points(profile, max_sag=MAX_FACET_SAG / 8.0)


def test_sampling_checks_cancellation_while_subdividing(spline_profile):
    calls = 0

    def check():
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("abgebrochene Konturprobe")

    with pytest.raises(RuntimeError, match="abgebrochene Konturprobe"):
        sketch_solid.outline_points(
            spline_profile, max_sag=MAX_FACET_SAG / 8.0, check_cancelled=check
        )
    assert calls == 3


def _square_profile(width, reverse=False, holes=()):
    points = [(0.0, 0.0), (width, 0.0), (width, width), (0.0, width)]
    if reverse:
        points.reverse()
    return Profile(
        segments=tuple(
            ProfileSegment("line", point, points[(i + 1) % len(points)])
            for i, point in enumerate(points)
        ),
        holes=holes,
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_contour_conversion_preserves_holes_independently_of_winding(reverse):
    from app.core.geom.contours import offset_section, polygons_of, section_of

    hole = Profile(circle=((2.0, 2.0), 0.5))
    section = section_of(_square_profile(4.0, reverse, holes=(hole,)))
    polygons = polygons_of(section)
    assert len(polygons) == 1 and len(polygons[0].interiors) == 1
    assert not polygons[0].contains(Point(2.0, 2.0))
    assert polygons[0].contains(Point(0.25, 0.25))
    larger = polygons_of(offset_section(section, 0.2, max_sag=0.005))[0]
    assert larger.bounds == pytest.approx((-0.2, -0.2, 4.2, 4.2), abs=EPS_GEOM)
    assert len(larger.interiors) == 1
    assert Point(2.0, 2.0).distance(LineString(larger.interiors[0])) < 0.3 + MAX_FACET_SAG
    assert polygons_of(offset_section(section, -2.0)) == ()


def test_disconnected_offset_results_remain_separate_and_visible():
    from app.core.geom.contours import offset_section, polygons_of, section_of

    points = [
        (-4.0, -2.0),
        (-1.0, -2.0),
        (-1.0, -0.2),
        (1.0, -0.2),
        (1.0, -2.0),
        (4.0, -2.0),
        (4.0, 2.0),
        (1.0, 2.0),
        (1.0, 0.2),
        (-1.0, 0.2),
        (-1.0, 2.0),
        (-4.0, 2.0),
    ]
    profile = Profile(
        segments=tuple(
            ProfileSegment("line", point, points[(i + 1) % len(points)])
            for i, point in enumerate(points)
        )
    )
    pieces = polygons_of(offset_section(section_of(profile), -0.3))
    assert len(pieces) == 2
    assert all(not piece.interiors and piece.area > 0 for piece in pieces)


def test_invalid_hole_is_rejected_before_a_fill_rule_can_reinterpret_it():
    from app.core.geom.contours import section_of

    with pytest.raises(ValidationError, match="Kontur"):
        section_of(_square_profile(4.0, holes=(Profile(circle=((10.0, 10.0), 1.0)),)))
