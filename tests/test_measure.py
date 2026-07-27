"""Measuring against a body whose dimensions are known (Bauplan §18.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.geom.measure import (
    Measurement,
    MeasurementList,
    angle_between,
    bounding_box_of,
    distance,
    snap,
    volume_of,
    wall_thickness,
)
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import normalise

MESHES = Path(__file__).parent / "data" / "meshes"


def cube():
    """20 mm cube, centred on the origin, welded and watertight."""
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def test_point_to_point_distance() -> None:
    assert distance((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)) == pytest.approx(5.0)
    assert distance((1.0, 1.0, 1.0), (1.0, 1.0, 1.0)) == pytest.approx(0.0)


def test_angles_are_reported_as_the_smaller_one() -> None:
    assert angle_between((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)) == pytest.approx(90.0)
    assert angle_between((1.0, 0.0, 0.0), (1.0, 1.0, 0.0)) == pytest.approx(45.0)
    assert angle_between((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)) == pytest.approx(0.0)
    assert angle_between((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)) == pytest.approx(0.0)


def test_a_click_near_a_corner_snaps_onto_it() -> None:
    """§18.3: snapping is what makes a measurement reproducible."""
    result = snap(cube(), (10.2, 9.8, 10.1))

    assert result.kind == "vertex"
    assert result.point == pytest.approx((10.0, 10.0, 10.0))
    assert result.distance < 0.5


def test_a_click_along_an_edge_snaps_onto_the_edge() -> None:
    result = snap(cube(), (0.0, 10.1, 10.2))

    assert result.kind == "edge"
    assert result.point[1] == pytest.approx(10.0, abs=1e-6)
    assert result.point[2] == pytest.approx(10.0, abs=1e-6)


def test_a_click_far_from_the_body_stays_where_it_is() -> None:
    result = snap(cube(), (100.0, 100.0, 100.0))

    assert result.kind == "free"
    assert result.point == pytest.approx((100.0, 100.0, 100.0))


def test_measuring_the_cube_edge_after_snapping() -> None:
    body = cube()
    first = snap(body, (-9.9, -10.1, -9.8)).point
    second = snap(body, (10.1, -9.9, -10.2)).point

    assert distance(first, second) == pytest.approx(20.0, abs=1e-9), "an edge of the cube"


def test_wall_thickness_of_a_solid_cube() -> None:
    """From the middle of a face straight through: 20 mm of material."""
    assert wall_thickness(cube(), (0.0, 0.0, 10.0)) == pytest.approx(20.0, abs=1e-3)


def test_wall_thickness_in_a_given_direction() -> None:
    assert wall_thickness(cube(), (0.0, 0.0, -10.0), (0.0, 0.0, 1.0)) == pytest.approx(
        20.0, abs=1e-3
    )


def test_wall_thickness_says_nothing_where_it_cannot_tell() -> None:
    """A ray that leaves the body reports nothing instead of a made up number."""
    assert wall_thickness(cube(), (0.0, 0.0, 10.0), (0.0, 0.0, 1.0)) is None


def test_bounds_and_volume_of_a_selection() -> None:
    body = cube()
    box = bounding_box_of([body])

    assert box.size == pytest.approx((20.0, 20.0, 20.0))
    assert box.centre == pytest.approx((0.0, 0.0, 0.0))
    assert volume_of([body]) == pytest.approx(8000.0)
    assert volume_of([body, body]) == pytest.approx(16000.0)


def test_an_empty_selection_has_no_size() -> None:
    box = bounding_box_of([])
    assert box.size == (0.0, 0.0, 0.0)
    assert volume_of([]) == 0.0


def test_dimensions_stay_until_they_are_deleted() -> None:
    """§18.3: dimensions remain until deleted."""
    dimensions = MeasurementList()
    dimensions.add(Measurement(kind="distance", value=20.0004))
    dimensions.add(Measurement(kind="thickness", value=2.4))

    assert len(dimensions) == 2
    assert dimensions.entries[0].shown == pytest.approx(20.0), "shown rounded to EPS_DISPLAY"
    assert dimensions.entries[0].value == pytest.approx(20.0004), "stored unrounded"

    dimensions.remove(0)
    assert len(dimensions) == 1
    dimensions.clear()
    assert len(dimensions) == 0
