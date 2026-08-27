"""Die Schnittfläche ist geschlossen (Bauplan §18.2).

Geprüft durch Messen, nicht durch Pixelvergleich: ein gedeckelter Schnitt durch
einen Vollkörper ist wasserdicht und hat genau das Volumen, das die Geometrie
sagt. Ein Bild könnte das nicht von einer hohlen Schale unterscheiden.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.geom.mesh import read_mesh
from app.core.geom.section import SectionPlane, cut, section_volume
from app.core.ingest.loader import normalise

MESHES = Path(__file__).parent / "data" / "meshes"


def solid(name: str = "cube_clean.stl"):
    """A welded cube: 20 mm edge, 8000 mm³, watertight."""
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def test_a_cut_through_the_middle_leaves_half_the_volume() -> None:
    body = solid()
    assert body.volume == pytest.approx(8000.0)

    result = cut(body, SectionPlane.along("z", 0.0))

    assert result.capped
    assert result.mesh.is_watertight, "an uncapped cut would leave an open shell"
    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-6)


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_every_axis_cuts_the_same_way(axis: str) -> None:
    result = cut(solid(), SectionPlane.along(axis, 0.0))  # type: ignore[arg-type]
    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-6)
    assert result.mesh.is_watertight


def test_moving_the_plane_moves_the_cut() -> None:
    body = solid()
    assert section_volume(body, SectionPlane.along("z", 5.0)) == pytest.approx(6000.0, rel=1e-6)
    assert section_volume(body, SectionPlane.along("z", -5.0)) == pytest.approx(2000.0, rel=1e-6)


def test_a_plane_outside_the_body_changes_nothing() -> None:
    body = solid()
    assert section_volume(body, SectionPlane.along("z", 50.0)) == pytest.approx(8000.0, rel=1e-6)


def test_a_plane_beyond_the_body_leaves_nothing() -> None:
    result = cut(solid(), SectionPlane.along("z", -50.0))
    assert result.mesh.triangle_count == 0


def test_two_planes_leave_a_slice() -> None:
    """§18.2: eine optionale zweite Ebene macht aus dem Schnitt eine Scheibe."""
    body = solid()
    result = cut(body, SectionPlane.along("z", 5.0), SectionPlane.along("z", -5.0).flipped())

    assert result.capped
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-6), "a 10 mm slice of a 20 mm cube"


def test_a_free_plane_works_like_an_axis_plane() -> None:
    body = solid()
    free = SectionPlane(normal=(0.0, 0.0, 2.0), position=0.0)
    assert section_volume(body, free) == pytest.approx(4000.0, rel=1e-6)


def test_a_plate_with_holes_is_capped_around_the_holes() -> None:
    """Der Fall, der es entscheidet: die Schnittfläche hat einen Umriss und
    vier Löcher darin.
    """
    plate = solid("plate_holes.stl")
    result = cut(plate, SectionPlane.along("z", 0.0))

    assert result.capped
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(plate.volume / 2.0, rel=1e-3)


def test_an_open_model_is_cut_but_reported_as_uncapped() -> None:
    """Ein offener Körper lässt sich nicht ehrlich deckeln — also wird es
    nicht vorgetäuscht (§18.2).
    """
    body = normalise(read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm").mesh
    result = cut(body, SectionPlane.along("z", 0.0))

    assert not result.capped
    assert result.mesh.triangle_count > 0


def test_the_original_body_is_left_alone() -> None:
    body = solid()
    before = body.triangle_count
    cut(body, SectionPlane.along("z", 0.0))
    assert body.triangle_count == before, "cutting returns a new body, it does not change one"
