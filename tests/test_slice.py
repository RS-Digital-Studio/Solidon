"""The analysis slicer against bodies whose numbers are known (§22, §40).

A cube, a cylinder and a cone have cross-sections anyone can work out with a
pencil — so the slicer can be held to one percent instead of to a feeling.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import place_on_bed
from app.core.ingest.loader import normalise
from app.core.slice.analysis import (
    island_layers,
    minimum_width,
    narrowest,
    slice_body,
    total_overhang,
)

MESHES = Path(__file__).parent / "data" / "meshes"

#: What §40 asks for: area and support volume within one percent.
TOLERANCE = 0.01


def on_bed(body: trimesh.Trimesh) -> MeshData:
    return place_on_bed(MeshData.of(body))


def corpus(name: str) -> MeshData:
    return place_on_bed(normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh)


# --- against analytically known bodies ------------------------------------------


def test_a_cube_has_the_same_cross_section_all_the_way_up() -> None:
    result = slice_body(on_bed(trimesh.creation.box(extents=(20.0, 20.0, 20.0))), 0.2)

    assert len(result.layers) == pytest.approx(100, abs=1)
    for layer in result.layers:
        assert layer.area == pytest.approx(400.0, rel=TOLERANCE)
    assert result.first_layer_area == pytest.approx(400.0, rel=TOLERANCE)


def test_a_cylinder_matches_pi_r_squared() -> None:
    body = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=256)
    result = slice_body(on_bed(body), 0.2)

    expected = math.pi * 10.0**2
    for layer in result.layers:
        assert layer.area == pytest.approx(expected, rel=TOLERANCE)


def test_a_cone_narrows_the_way_geometry_says() -> None:
    """Point up: the radius shrinks linearly, so the area shrinks quadratically."""
    body = trimesh.creation.cone(radius=10.0, height=20.0, sections=256)
    result = slice_body(on_bed(body), 0.5)

    for layer in result.layers:
        radius = 10.0 * (1.0 - layer.z / 20.0)
        assert layer.area == pytest.approx(math.pi * radius**2, rel=0.03, abs=0.5)


def test_a_straight_body_needs_no_support() -> None:
    """The first layer rests on the plate, everything above on the layer below."""
    result = slice_body(on_bed(trimesh.creation.box(extents=(20.0, 20.0, 20.0))), 0.2)

    assert total_overhang(result) == pytest.approx(0.0, abs=1.0)
    assert result.support_volume == pytest.approx(0.0, abs=1.0)


def test_a_shallow_cone_needs_no_support_even_on_its_tip() -> None:
    """A wall at 27 degrees prints itself — the 45 degree rule from §39."""
    body = trimesh.creation.cone(radius=10.0, height=20.0, sections=128)
    body.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))

    assert slice_body(on_bed(body), 0.5).support_volume == pytest.approx(0.0, abs=1.0)


def test_a_steep_cone_on_its_tip_costs_support() -> None:
    """A wall at 63 degrees does not — and the difference is what §22 is for."""
    steep = trimesh.creation.cone(radius=20.0, height=10.0, sections=128)
    steep.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))
    upright = trimesh.creation.cone(radius=20.0, height=10.0, sections=128)

    on_tip = slice_body(on_bed(steep), 0.5)
    standing = slice_body(on_bed(upright), 0.5)

    assert on_tip.support_volume > 100.0
    assert standing.support_volume == pytest.approx(0.0, abs=1.0)


# --- islands --------------------------------------------------------------------


def test_the_island_tower_is_recognised() -> None:
    """§40: island_tower.stl is recognised."""
    result = slice_body(corpus("island_tower.stl"), 0.5)
    heights = island_layers(result)

    assert heights, "the floating block starts in mid-air and has to be found"
    # The block spans 20 to 30 mm; the bridge only reaches it at 25 mm, so it
    # hangs free for five millimetres.
    assert min(heights) == pytest.approx(20.0, abs=1.0)
    assert max(heights) < 26.0, "from the bridge upwards it is carried"
    assert result.support_volume > 0.0


def test_a_solid_body_has_no_islands_above_the_plate() -> None:
    result = slice_body(on_bed(trimesh.creation.box(extents=(20.0, 20.0, 20.0))), 0.5)
    above = [z for z in island_layers(result) if z > 1.0]

    assert not above, "nothing starts in mid-air in a cube"


# --- widths ---------------------------------------------------------------------


def test_the_smallest_structure_width_is_measured() -> None:
    from shapely.geometry import box as shapely_box

    assert minimum_width(shapely_box(0.0, 0.0, 10.0, 0.6)) == pytest.approx(0.6, rel=0.05)
    assert minimum_width(shapely_box(0.0, 0.0, 10.0, 2.0)) == pytest.approx(2.0, rel=0.05)


def test_above_the_interesting_width_it_stops_measuring() -> None:
    """§22.2 asks whether something is too thin, not how thick a thick wall is.

    The search up there cost more than the rest of the layer analysis together,
    so a wide layer is reported as "at least this" — and that is written down
    rather than looking like a measurement.
    """
    from shapely.geometry import box as shapely_box

    from app.core.slice.analysis import WIDTH_INTERESTING

    wide = minimum_width(shapely_box(0.0, 0.0, 40.0, 30.0))

    assert wide == pytest.approx(WIDTH_INTERESTING), "a lower bound, not the real 30 mm"
    assert minimum_width(shapely_box(0.0, 0.0, 40.0, 30.0), interesting_below=0.0) > 20.0


def test_a_thin_wall_is_found_across_the_body() -> None:
    wall = trimesh.creation.box(extents=(40.0, 0.8, 20.0))
    result = slice_body(on_bed(wall), 0.5)

    assert narrowest(result) == pytest.approx(0.8, rel=0.1)


# --- the contract ---------------------------------------------------------------


def test_every_figure_is_marked_as_internal() -> None:
    """§22.5: never mixed with a figure measured from G-code."""
    result = slice_body(on_bed(trimesh.creation.box(extents=(10.0, 10.0, 10.0))), 0.5)
    assert result.source == "internal"


def test_the_contours_carry_their_holes() -> None:
    result = slice_body(corpus("plate_holes.stl"), 1.0)
    layer = result.layers[len(result.layers) // 2]

    assert layer.contours
    assert sum(len(contour.holes) for contour in layer.contours) == 4, "four bores, four holes"
    assert layer.area == pytest.approx(80.0 * 50.0 - 4 * math.pi * 2.6**2, rel=0.02)


def test_an_empty_body_slices_to_nothing() -> None:
    result = slice_body(MeshData.of(trimesh.Trimesh()), 0.2)
    assert result.layers == ()
    assert result.support_volume == 0.0


def test_a_layer_height_of_zero_is_refused() -> None:
    with pytest.raises(ValueError):
        slice_body(on_bed(trimesh.creation.box(extents=(10.0, 10.0, 10.0))), 0.0)
