"""Der Analyse-Schneider gegen Körper mit bekannten Zahlen (§22, §40).

Ein Würfel, ein Zylinder und ein Kegel haben Querschnitte, die sich mit einem
Bleistift ausrechnen lassen — der Schneider lässt sich also auf ein Prozent
festnageln statt auf ein Gefühl.
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
    cross_section,
    island_layers,
    minimum_width,
    narrowest,
    slice_body,
    total_overhang,
)

MESHES = Path(__file__).parent / "data" / "meshes"

#: Was §40 verlangt: Fläche und Stützvolumen auf ein Prozent genau.
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
    """Spitze nach oben: der Radius schrumpft linear, die Fläche also
    quadratisch.
    """
    body = trimesh.creation.cone(radius=10.0, height=20.0, sections=256)
    result = slice_body(on_bed(body), 0.5)

    for layer in result.layers:
        radius = 10.0 * (1.0 - layer.z / 20.0)
        assert layer.area == pytest.approx(math.pi * radius**2, rel=0.03, abs=0.5)


def test_a_straight_body_needs_no_support() -> None:
    """Die erste Schicht liegt auf der Platte, alles darüber auf der Schicht
    darunter.
    """
    result = slice_body(on_bed(trimesh.creation.box(extents=(20.0, 20.0, 20.0))), 0.2)

    assert total_overhang(result) == pytest.approx(0.0, abs=1.0)
    assert result.support_volume == pytest.approx(0.0, abs=1.0)


def test_a_shallow_cone_needs_no_support_even_on_its_tip() -> None:
    """Eine Wand mit 27 Grad druckt sich selbst — die 45-Grad-Regel aus §39."""
    body = trimesh.creation.cone(radius=10.0, height=20.0, sections=128)
    body.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))

    assert slice_body(on_bed(body), 0.5).support_volume == pytest.approx(0.0, abs=1.0)


def test_a_steep_cone_on_its_tip_costs_support() -> None:
    """Eine Wand mit 63 Grad nicht — und für diesen Unterschied gibt es §22."""
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
    # Der Block spannt von 20 bis 30 mm; die Brücke erreicht ihn erst bei 25 mm,
    # sie hängt also fünf Millimeter frei.
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
    """§22.2 fragt, ob etwas zu dünn ist, nicht wie dick eine dicke Wand ist.

    Die Suche dort oben kostete mehr als der Rest der Schichtanalyse zusammen —
    eine breite Schicht wird also als „mindestens das" gemeldet, und das steht
    da, statt wie eine Messung auszusehen.
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
    """§22.5: nie mit einer aus G-Code gemessenen Größe vermischt."""
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


# --- Ein Schnitt mit einem Loch mitten darin ------------------------------------


def hollow_box() -> MeshData:
    """Eine oben offene Box: 60 × 40 × 30 außen, 3 mm Wände, 1,5 mm Boden."""
    outer = trimesh.creation.box(extents=(60.0, 40.0, 30.0))
    outer.apply_translation((0.0, 0.0, 15.0))
    inner = trimesh.creation.box(extents=(54.0, 34.0, 27.0))
    inner.apply_translation((0.0, 0.0, 16.5))
    return MeshData.of(trimesh.boolean.difference([outer, inner]))


def test_a_wall_ring_is_a_section_and_not_nothing() -> None:
    """Die Regression: ein zentrierter Hohlraum ließ den ganzen Schnitt
    verschwinden.

    Die Verschachtelung fragte, ob ein Stück in einem anderen liegt, indem sie
    einen Punkt seiner *Außenlinie* nahm. Bei einer Box ist diese Außenlinie
    das äußere Rechteck, und dessen Mitte liegt im Hohlraum — Wand und Hohlraum
    erklärten einander also zum jeweiligen Loch, beide zählten als Loch, und
    ein Schnitt, den es offensichtlich gibt, kam als ``None`` zurück. Jede
    Schicht jedes hohlen Körpers war betroffen; der bestehende Korpus verbarg
    es, weil seine Bohrungen außermittig sitzen.
    """
    box = hollow_box()

    for z in (5.0, 15.0, 29.9):
        section = cross_section(box, z)
        assert section is not None, f"the wall at z={z} is material"
        assert section.area == pytest.approx(60.0 * 40.0 - 54.0 * 34.0, rel=TOLERANCE)
        assert len(section.interiors) == 1, "the cavity is the hole of the ring"


def test_a_solid_layer_stays_solid() -> None:
    """Unter dem Hohlraum ist derselbe Körper ein volles Rechteck — kein Loch
    erfunden.
    """
    section = cross_section(hollow_box(), 1.0)

    assert section is not None
    assert section.area == pytest.approx(2400.0, rel=TOLERANCE)
    assert not section.interiors


def test_a_centred_bore_is_a_hole_not_a_disappearance() -> None:
    """Derselbe Fehler in seiner kleinsten Form: eine Platte, eine Bohrung, in
    der Mitte.
    """
    plate = trimesh.creation.box(extents=(40.0, 40.0, 8.0))
    bore = trimesh.creation.cylinder(radius=5.0, height=20.0, sections=128)
    body = MeshData.of(trimesh.boolean.difference([plate, bore]))

    section = cross_section(body, 0.0)

    assert section is not None
    assert section.area == pytest.approx(1600.0 - math.pi * 25.0, rel=0.02)


def test_a_hole_touching_its_own_wall_does_not_stop_the_slicer() -> None:
    """Eine Tasche, die exakt bis an die Außenwand reicht.

    Das Loch trifft die Hülle dann in einem Punkt, das Polygon ist ungültig,
    und GEOS wirft bei der nächsten Operation darüber — nicht hier, sondern
    drei Ebenen höher, mit einer Koordinate und ohne Namen. Drei Modelle des
    Korpus tun genau das.
    """
    plate = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    plate.apply_translation((0.0, 0.0, 5.0))
    pocket = trimesh.creation.box(extents=(20.0, 20.0, 6.0))
    # Ihre rechte Fläche sitzt exakt auf der rechten Fläche der Platte.
    pocket.apply_translation((10.0, 0.0, 7.0))
    body = MeshData.of(trimesh.boolean.difference([plate, pocket]))

    section = cross_section(body, 6.0)

    assert section is not None
    assert section.is_valid, "a section that cannot be measured is worse than none"
    assert section.area == pytest.approx(1600.0 - 20.0 * 20.0, rel=TOLERANCE)
