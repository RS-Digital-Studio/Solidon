"""Die Schnittfläche ist geschlossen (Bauplan §18.2).

Geprüft durch Messen, nicht durch Pixelvergleich: ein gedeckelter Schnitt durch
einen Vollkörper ist wasserdicht und hat genau das Volumen, das die Geometrie
sagt. Ein Bild könnte das nicht von einer hohlen Schale unterscheiden.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

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


@pytest.mark.parametrize("second", [False, True])
def test_an_empty_body_is_cut_to_nothing_instead_of_failing(second: bool) -> None:
    """Ein leerer Körper hat nichts zu schneiden — und bricht die Vorschau nicht ab.

    Die Vorschau einer aufgeweiteten Bohrung trägt einen leeren Körper „dazu“
    (``added``); sobald ein Ansichtsschnitt stand, riss ``cut`` an seinem
    Hüllquader, und die ganze Vorschau hieß „nicht verfügbar“ — mit gesperrtem
    Übernehmen, bis ein Wert geändert wurde (Durchsicht 0.5.1, Wabenhalter).
    """
    empty = solid().replacing(trimesh.Trimesh())
    plane = SectionPlane.along("z", 0.0)

    result = cut(empty, plane, plane.flipped() if second else None)

    assert result.mesh.triangle_count == 0
    assert result.capped, "ohne Körper bleibt keine Schnittfläche offen"


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


def touching_blocks():
    """Zwei Würfel zu 20 mm, die sich an einer Fläche berühren — zwei Schalen.

    So hinterlässt das Einlesen Teile, die sich nur berühren (``repair.weld``:
    „Zwei Körper, die sich berühren, bleiben zwei"): Jede Schale hat ihre
    eigenen Ecken, auch dort, wo sie an derselben Stelle liegen wie die der
    anderen.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    first = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second.apply_translation((20.0, 0.0, 0.0))
    return MeshData(trimesh.util.concatenate([first, second]))


@pytest.mark.parametrize(("axis", "position", "volume"), [("z", 0.0, 8000.0), ("y", 3.0, 10400.0)])
def test_two_bodies_that_touch_stay_two_closed_bodies_after_a_cut(
    axis: str, position: float, volume: float
) -> None:
    """Ein Schnitt quer zur Berührfläche verbindet die zwei Schalen nicht.

    Der Deckel legte dafür **alle** gleichen Ecken zusammen, nicht nur die der
    Schnittkante — und damit auch die Ecken, an denen sich die zwei Teile
    berühren. Die Berührflächen teilten danach ihre Kanten, vier Flächen an
    einer Kante, und die Hälfte war kein Körper mehr: Am Laptopständer
    (``parametric-laptop-riser.stl``, 21 Teile) trug jede Hälfte 89 bis 500
    verzweigte Kanten, und *Modell teilen* scheiterte an den Stiften
    (KUNDE-10). Die Sollwerte sind die zweier Würfel: je 20 × 20 × 10 unter
    z = 0, je 20 × 13 × 20 unter y = 3.
    """
    from app.core.geom.repair import branching_edge_count, open_edge_count

    result = cut(touching_blocks(), SectionPlane.along(axis, position))  # type: ignore[arg-type]

    assert result.capped
    assert result.mesh.is_watertight, "each half is still two closed blocks"
    assert branching_edge_count(result.mesh) == 0
    assert open_edge_count(result.mesh) == 0
    assert result.mesh.component_count == 2, "touching is not joining"
    assert result.mesh.volume == pytest.approx(volume, rel=1e-9)


@pytest.mark.parametrize("level", [12.5, 39.4184852544278])
@pytest.mark.parametrize("side", ["below", "above"])
def test_a_seam_just_beside_the_plane_is_capped(level: float, side: str) -> None:
    """Ecken, die ``trimesh`` zur Ebene zählt, bekommen einen geschlossenen Deckel.

    ``trimesh`` zählt eine Ecke bis ``_ON_PLANE`` neben der Ebene zu ihr und
    lässt sie stehen, wo sie ist; die geschnittenen Nachbardreiecke legen ihre
    Kopie genau auf die Ebene. Der Deckel legte beide über gerundete
    Koordinaten zusammen und verfehlte sie, sobald eine Rundungsgrenze sie
    trennte: Der Rand zerfiel in offene Ketten, beide Hälften blieben offen,
    und ``capped`` sagte ja, weil es den Eingang fragt. Aufgefallen an Bob
    (CC0) an der Mitte seines Hüllquaders, 39,4184852544278 mm, wo danach die
    Stifte von *Teilen* scheiterten.

    Soll aus der Symmetrie: Jede Hälfte trägt das halbe Volumen der Kugel;
    das Rauschen der Naht verschiebt es um weniger als ein Milliardstel.
    """
    from app.core.geom.repair import open_edge_count
    from tests.helpers import mirror_seam_sphere

    body = mirror_seam_sphere(level)
    plane = SectionPlane.along("z", level)

    result = cut(body, plane if side == "below" else plane.flipped())

    assert result.mesh.is_watertight, "die Schnittkante ist in offene Ketten zerfallen"
    assert open_edge_count(result.mesh) == 0
    assert result.mesh.volume == pytest.approx(body.volume / 2.0, rel=1e-9)


def test_an_open_model_is_cut_but_reported_as_uncapped() -> None:
    """Ein offener Körper lässt sich nicht ehrlich deckeln — also wird es
    nicht vorgetäuscht (§18.2).
    """
    body = normalise(
        read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm", mend=False
    ).mesh
    result = cut(body, SectionPlane.along("z", 0.0))

    assert not result.capped
    assert result.mesh.triangle_count > 0


def test_the_original_body_is_left_alone() -> None:
    body = solid()
    before = body.triangle_count
    cut(body, SectionPlane.along("z", 0.0))
    assert body.triangle_count == before, "cutting returns a new body, it does not change one"


@pytest.mark.parametrize(
    "normal", [(1.0, 1.0, 1.0), (0.3, -0.2, 0.9), (-1.0, 0.5, 0.0), (0.0, 0.0, -1.0)]
)
def test_an_oblique_cut_through_the_centre_halves_the_cube(normal) -> None:
    """Jede Ebene durch die Mitte eines punktsymmetrischen Körpers halbiert ihn.

    Seit dem 22.09.2026 schneidet und deckelt ``section`` in einem Rahmen, in
    dem die Ebene waagerecht liegt, und baut den Deckel selbst (RM-187: der
    Deckel von ``trimesh`` lag über eine SVD in der Ebene). Die Probe dafür
    ist die Analytik, nicht der alte Weg.
    """
    import math

    length = math.hypot(*normal)
    plane = SectionPlane(normal=tuple(value / length for value in normal), position=0.0)

    result = cut(solid(), plane)

    assert result.capped
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-9)


def test_an_oblique_cut_caps_a_ring_around_its_hole() -> None:
    """Ein Rohr schräg geschnitten: Der Deckel ist ein Ring, das Loch bleibt offen."""
    import math

    from app.core.geom import lathe
    from app.core.geom.mesh import MeshData

    tube = MeshData.of(lathe.annulus(r_min=10.0, r_max=20.0, height=30.0, sections=96))
    normal = (0.2, 0.1, 0.97)
    length = math.hypot(*normal)

    result = cut(tube, SectionPlane(normal=tuple(v / length for v in normal), position=0.0))

    assert result.capped
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(tube.volume / 2.0, rel=1e-9)
    assert result.mesh.component_count == 1
