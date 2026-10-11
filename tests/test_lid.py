"""Der Deckel über einer Öffnung (§25, §14, §40).

Eine Box mit bekannten Maßen, damit sich jede Zahl nachprüfen lässt, mit der
der Deckel herauskommt: der Kragen ist der Hohlraum minus zweimal das Spiel,
und der Beweis, dass er passt, ist, dass Deckel und Gehäuse gar kein Volumen
teilen.
"""

from __future__ import annotations

import dataclasses
import math
import warnings

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import shared_volume
from app.core.geom.lid import CAP_THREAD_FEATURE, NECK_THREAD_FEATURE
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject
from app.core.units import EPS_GEOM, exact_cos_degrees, exact_sin_degrees
from tests.helpers import exact_kernel

load_operations()

#: Das Gehäuse, gegen das jeder Test misst: 60 x 40 x 30 außen, 3 mm Wände,
#: 1,5 mm Boden, oben offen. Hohlraum 54 x 34.
OUTER = (60.0, 40.0, 30.0)
CAVITY = (54.0, 34.0)


@pytest.mark.parametrize("angle", [0.0, 37.0, 90.0])
@pytest.mark.parametrize("offset", [0.0, 1_000_000.0])
@pytest.mark.parametrize("as_points", [False, True])
def test_opening_width_needs_no_geos_rectangle_reconstruction(
    monkeypatch: pytest.MonkeyPatch, angle: float, offset: float, as_points: bool
) -> None:
    """Gültige Rechtecke bleiben trotz des GEOS-Warnungsfehlers messbar.

    Auf macOS/arm64 meldet die Rechteckrekonstruktion bereits bei einer
    normalen Box Division durch null (Shapely #2215, GEOS #1235). Die Sonde
    stellt diese Bibliotheksantwort auch auf Windows her. Netzpolygon und
    Randpunkte einer exakten Öffnung müssen dieselbe reale Weite liefern.
    """
    import shapely
    from shapely.geometry import MultiPoint, Polygon

    from app.core.geom.lid import _short_side

    def warned(*_args: object, **_kwargs: object) -> None:
        warnings.warn(
            "divide by zero encountered in oriented_envelope", RuntimeWarning, stacklevel=2
        )

    monkeypatch.setattr(shapely.lib, "oriented_envelope", warned)
    cosine, sine = exact_cos_degrees(angle), exact_sin_degrees(angle)
    corners = [
        (offset + x * cosine - y * sine, -offset + x * sine + y * cosine)
        for x, y in [(0.0, 0.0), (54.0, 0.0), (54.0, 34.0), (0.0, 34.0)]
    ]
    shape = MultiPoint(corners) if as_points else Polygon(corners)

    assert _short_side(shape) == pytest.approx(34.0, abs=EPS_GEOM, rel=0.0)


def test_opening_width_belongs_to_the_minimum_area_rectangle() -> None:
    """Die kürzeste Seite allein wählt nicht das flächenkleinste Rechteck.

    Achsparallel: Fläche 50, Weite 5. An der langen schrägen Kante wäre die
    Weite 50/sqrt(106) kleiner, die Fläche 5500/106 aber größer als 50.
    """
    from shapely.geometry import Polygon

    from app.core.geom.lid import _short_side

    shape = Polygon([(0.0, 0.0), (0.0, 4.0), (1.0, 5.0), (10.0, 0.0)])

    assert _short_side(shape) == pytest.approx(5.0, abs=EPS_GEOM, rel=0.0)


def test_opening_width_keeps_tiny_hull_edges_when_moving_the_origin() -> None:
    """Nahe Randpunkte aus dem exakten Kern können lokal zusammenrunden."""
    from shapely.geometry import MultiPoint

    from app.core.geom.lid import _short_side

    points = [(-10.0, 0.0), (0.0, 10.0), (math.ulp(10.0) / 4.0, 10.0), (10.0, 0.0), (0.0, -10.0)]

    assert _short_side(MultiPoint(points)) == pytest.approx(math.sqrt(200.0), abs=EPS_GEOM, rel=0.0)


@pytest.mark.parametrize("kind", ["empty", "point", "line"])
def test_degenerate_openings_have_no_rectangle_width(kind: str) -> None:
    """Leerer Umriss, Punkt und Linie werden nicht zu einer Rechteckbreite."""
    from shapely.geometry import LineString, Point, Polygon

    from app.core.geom.lid import _short_side

    shape = {"empty": Polygon(), "point": Point(3.0, 4.0), "line": LineString([(0, 0), (5, 5)])}
    assert _short_side(shape[kind]) is None


def housing(material: str | None = None) -> SceneObject:
    outer = trimesh.creation.box(extents=OUTER)
    outer.apply_translation((0.0, 0.0, OUTER[2] / 2.0))
    inner = trimesh.creation.box(extents=(CAVITY[0], CAVITY[1], 27.0))
    inner.apply_translation((0.0, 0.0, 16.5))
    body = trimesh.boolean.difference([outer, inner])
    return SceneObject(id="obj_1", name="Gehäuse", mesh=MeshData.of(body), material=material)


def make_lid(entry: SceneObject, profile: Profile, **params: object):
    spec = REGISTRY.get("create_lid")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_the_lid_covers_the_opening(profile: Profile) -> None:
    """Ein Deckel mit einem Loch darin ist kein Deckel — das eigene Loch des
    Schnitts wird gefüllt.
    """
    result = make_lid(housing(), profile, thickness=2.4, collar=4.0)
    body = result.outputs[1].mesh

    plate = OUTER[0] * OUTER[1] * 2.4
    assert body.bounds.size[0] == pytest.approx(OUTER[0])
    assert body.bounds.size[1] == pytest.approx(OUTER[1])
    assert body.volume > plate, "the plate is solid, plus a collar"
    assert body.is_watertight


def test_the_collar_is_the_cavity_less_the_clearance(profile: Profile) -> None:
    """§12: die Zahl kommt aus dem Materialprofil, nicht aus der Datei."""
    result = make_lid(housing(), profile, thickness=2.4, collar=4.0)
    body = result.outputs[1].mesh.raw

    # Halbes Spiel je Seite: ``clearance`` ist ein Durchmessermaß, wie bei
    # jedem Passstift auch. Hier stand einmal eine feste Zugabe von 0,2 mm
    # daneben, und die machte aus 0,25 mm Spiel 0,90 mm.
    gap = profiles.material("petg").clearance / 2.0
    collar = body.slice_plane([0.0, 0.0, 29.0], [0.0, 0.0, -1.0])
    width = collar.bounds[1][:2] - collar.bounds[0][:2]

    assert width[0] == pytest.approx(CAVITY[0] - 2.0 * gap, abs=0.01)
    assert width[1] == pytest.approx(CAVITY[1] - 2.0 * gap, abs=0.01)


def test_the_lid_really_goes_in(profile: Profile) -> None:
    """Die eine Messung, auf die es ankommt: Deckel und Gehäuse teilen kein
    Volumen.
    """
    entry = housing()
    body = make_lid(entry, profile, thickness=2.4, collar=4.0).outputs[1].mesh

    assert shared_volume(body.raw, entry.mesh.raw) < 1e-6


def test_the_lid_sits_on_the_rim(profile: Profile) -> None:
    result = make_lid(housing(), profile, thickness=2.4, collar=4.0)
    body = result.outputs[1].mesh

    assert body.bounds.minimum[2] == pytest.approx(OUTER[2] - 4.0), "the collar reaches down"
    assert body.bounds.maximum[2] == pytest.approx(OUTER[2] + 2.4), "the plate sits on top"


def test_a_softer_lid_gets_more_room(profile: Profile) -> None:
    """§12 noch einmal: der Deckel eines TPU-Gehäuses ist nicht der eines
    PETG-Gehäuses.
    """
    stiff = make_lid(housing(), profile, collar=4.0).findings[0].values["clearance_mm"]
    soft = make_lid(housing("tpu-95a"), profile, collar=4.0).findings[0].values["clearance_mm"]

    assert soft > stiff
    assert soft == pytest.approx(profiles.material("tpu-95a").clearance)


@pytest.mark.parametrize("op", ["create_lid", "screw_lid"])
def test_an_opening_below_the_bed_keeps_its_stated_height(profile: Profile, op: str) -> None:
    """Die Höhe der Öffnung ist eine Welthöhe, und ein Körper darf unter dem Bett liegen.

    Für den Namen der Null („Oberkante“) bekam das Feld ``minimum=0``; ein
    Projekt aus 0.5.2 mit eingetippter negativer Höhe hielt danach am Schritt
    an — „Der Wert liegt unter dem zulässigen Mindestwert“ (Durchsicht 0.5.3,
    Fund 9). Seit RM-526 heißt der leere Zustand „Oberkante“; die Grenze trägt
    alte Projekte.
    """
    from app.core.registry.params import validate

    assert validate(REGISTRY.get(op).params, {"z": -10.0}).z == pytest.approx(-10.0)
    if op != "create_lid":
        return
    below = housing()
    moved = below.mesh.raw.copy()
    moved.apply_translation((0.0, 0.0, -40.0))
    entry = dataclasses.replace(below, mesh=MeshData.of(moved))

    body = make_lid(entry, profile, thickness=2.4, collar=4.0, z=-10.0).outputs[1].mesh

    assert body.bounds.maximum[2] == pytest.approx(OUTER[2] - 40.0 + 2.4), "auf dem Rand"


@pytest.mark.parametrize("op", ["create_lid", "screw_lid"])
def test_an_empty_height_is_the_top_edge_and_zero_is_the_bed(profile: Profile, op: str) -> None:
    """Leer heißt Oberkante, und die Null ist eine Höhe wie jede andere (RM-526).

    Bis Format 46 hieß ``z = 0`` „Oberkante“; eine Öffnung auf Höhe des Betts ließ
    sich deshalb nicht sagen. Ein Gehäuse 20 mm unter dem Bett schneidet die
    Ebene null mitten im Hohlraum: Leer bekommt es den Deckel auf seinem Rand bei
    10 mm, mit null auf Höhe des Betts.
    """
    from app.core.registry.params import validate

    spec = REGISTRY.get(op).params
    assert validate(spec, {}).z is None, "die Vorgabe ist leer"
    assert validate(spec, {"z": None}).z is None
    assert validate(spec, {"z": 0.0}).z == 0.0, "die Null bleibt eine Zahl"
    if op != "create_lid":
        return
    below = housing()
    moved = below.mesh.raw.copy()
    moved.apply_translation((0.0, 0.0, -20.0))
    entry = dataclasses.replace(below, mesh=MeshData.of(moved))

    top = make_lid(entry, profile, thickness=2.4, collar=4.0).outputs[1].mesh
    bed = make_lid(entry, profile, thickness=2.4, collar=4.0, z=0.0).outputs[1].mesh

    assert top.bounds.maximum[2] == pytest.approx(OUTER[2] - 20.0 + 2.4), "auf dem Rand"
    assert bed.bounds.maximum[2] == pytest.approx(2.4), "auf Höhe des Betts"


def test_a_lid_without_a_collar_is_a_plate(profile: Profile) -> None:
    result = make_lid(housing(), profile, thickness=2.4, collar=0.0)
    body = result.outputs[1].mesh

    assert body.volume == pytest.approx(OUTER[0] * OUTER[1] * 2.4, rel=0.001)
    assert body.bounds.minimum[2] == pytest.approx(OUTER[2])


def test_a_solid_body_has_nothing_to_close(profile: Profile) -> None:
    block = trimesh.creation.box(extents=(40.0, 40.0, 20.0))
    block.apply_translation((0.0, 0.0, 10.0))
    entry = SceneObject(id="obj_1", name="Klotz", mesh=MeshData.of(block))

    with pytest.raises(ValidationError) as problem:
        make_lid(entry, profile, collar=4.0)

    assert problem.value.constraint == "no_cavity"


def test_a_screw_hole_is_not_an_opening(profile: Profile) -> None:
    """Eine 4-mm-Bohrung ist eine Bohrung. Ein Kragen darin wäre ein Stift,
    nach dem niemand gefragt hat.
    """
    plate = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    plate.apply_translation((0.0, 0.0, 5.0))
    bore = trimesh.creation.cylinder(radius=2.0, height=30.0, sections=64)
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=MeshData.of(trimesh.boolean.difference([plate, bore]))
    )

    with pytest.raises(ValidationError) as problem:
        make_lid(entry, profile, collar=4.0)

    assert problem.value.constraint == "no_cavity"


def test_two_compartments_get_two_collars(profile: Profile) -> None:
    """Eine unterteilte Box: ein Kragen je Fach ist das, was den Deckel vom
    Verdrehen abhält.
    """
    outer = trimesh.creation.box(extents=(80.0, 40.0, 20.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    cut = []
    for offset in (-20.0, 20.0):
        pocket = trimesh.creation.box(extents=(30.0, 34.0, 18.0))
        pocket.apply_translation((offset, 0.0, 11.0))
        cut.append(pocket)
    body = trimesh.boolean.difference([outer, *cut])
    entry = SceneObject(id="obj_1", name="Kasten", mesh=MeshData.of(body))

    result = make_lid(entry, profile, thickness=2.0, collar=3.0)

    assert result.findings[0].values["cavities"] == 2
    lid_body = result.outputs[1].mesh
    assert lid_body.is_watertight
    assert shared_volume(lid_body.raw, body) < 1e-6


def test_the_lid_carries_the_material_of_the_body_it_closes(profile: Profile) -> None:
    result = make_lid(housing("tpu-95a"), profile, collar=4.0)

    assert result.outputs[1].material == "tpu-95a"


def test_a_screw_post_bore_is_not_a_compartment(profile: Profile) -> None:
    """Der echte Nachbar einer Öffnung: M3-Löcher in den Ecksäulen.

    Acht Quadratmillimeter gegen achtzehnhundert — ein Kragen in einem davon
    wäre ein Stift im Weg der Schraube. Die absolute Grenze entscheidet das,
    ohne die Hohlräume gegeneinander zu messen; das würfe ein kleines Fach weg,
    in das ein Kragen bestens passt.
    """
    body = housing().mesh.raw.copy()
    posts = []
    for x in (-26.0, 26.0):
        for y in (-16.0, 16.0):
            bore = trimesh.creation.cylinder(radius=1.6, height=40.0, sections=32)
            bore.apply_translation((x, y, 20.0))
            posts.append(bore)
    entry = SceneObject(
        id="obj_1", name="Gehäuse", mesh=MeshData.of(trimesh.boolean.difference([body, *posts]))
    )

    result = make_lid(entry, profile, thickness=2.0, collar=3.0)

    assert result.findings[0].values["cavities"] == 1, "the box, not the four bores"


def test_a_small_compartment_still_gets_a_collar(profile: Profile) -> None:
    """Ein Stiftfach von 12 x 12 neben einem Fach fünfzehnmal seiner Größe."""
    outer = trimesh.creation.box(extents=(80.0, 40.0, 20.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    big = trimesh.creation.box(extents=(50.0, 34.0, 18.0))
    big.apply_translation((-12.0, 0.0, 11.0))
    small = trimesh.creation.box(extents=(12.0, 12.0, 18.0))
    small.apply_translation((25.0, 0.0, 11.0))
    body = trimesh.boolean.difference([outer, big, small])
    entry = SceneObject(id="obj_1", name="Kasten", mesh=MeshData.of(body))

    result = make_lid(entry, profile, thickness=2.0, collar=3.0)

    assert result.findings[0].values["cavities"] == 2
    assert shared_volume(result.outputs[1].mesh.raw, body) < 1e-6


# --- der exakte Deckel ----------------------------------------------------------

#: Das Spiel der exakten Deckeltests, ausdrücklich statt aus dem Profil: Die
#: Sollwerte rechnen damit, und ein neu kalibriertes PETG soll sie nicht
#: verschieben.
EXACT_PLAY = 0.3


def exact_box_housing(
    outer: tuple[float, float, float],
    pockets: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    *,
    outer_radius: float = 0.0,
    pocket_radius: float = 0.0,
    material: str | None = None,
) -> SceneObject:
    """Ein exaktes Gehäuse: ein Quader, aus dem Taschen (Maße, Mitte unten) ausgespart sind."""
    exact_kernel()
    from app.core.brep import edit
    from app.core.brep.features import features_of

    body = edit.box(*outer)
    if outer_radius:
        body = edit.fillet(body, outer_radius, "vertical")
    for size, bottom in pockets:
        pocket = edit.moved(edit.box(*size), bottom)
        if pocket_radius:
            pocket = edit.fillet(pocket, pocket_radius, "vertical")
        body = edit.boolean("difference", [body, pocket])
    return SceneObject(
        id="obj_1",
        name="Gehäuse",
        mesh=body,
        kind="brep",
        material=material,
        features=features_of(body),
    )


def _shared_exact_volume(first, second) -> float:
    """Das gemeinsame Volumen zweier exakter Körper — unabhängig vom Prüfling gerechnet."""
    exact_kernel()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(BRepAlgoAPI_Common(first.shape, second.shape).Shape(), props)
    return abs(float(props.Mass()))


def _cylinder_faces(solid) -> int:
    exact_kernel()
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder

    return sum(BRepAdaptor_Surface(face).GetType() == GeomAbs_Cylinder for face in solid.faces())


def test_an_exact_housing_gets_an_exact_lid(profile: Profile) -> None:
    """Am exakten Gehäuse entsteht der Deckel exakt (P2.8: die Bearbeitung fragt den Körper).

    Bis zum 23.09.2026 kam er als Netz neben einem exakten Gehäuse heraus —
    ohne STEP, ohne Verrundung an den eigenen Kanten, und sein Kragen war aus
    der Vernetzung des Gehäuses geschnitten statt aus dessen Flächen. Die
    Sollwerte sind geschlossen: Platte 60 × 40 × 2,4, Kragen um das halbe
    Spiel je Seite eingezogen, 4 tief.
    """
    exact_kernel()
    from app.core.brep import kernel, step
    from app.core.geom.lid import CAVITY_FEATURE, COLLAR_FEATURE

    entry = exact_box_housing((60.0, 40.0, 30.0), [((54.0, 34.0, 28.0), (0.0, 0.0, 3.0))])
    result = make_lid(entry, profile, thickness=2.4, collar=4.0, clearance=EXACT_PLAY)
    housing_out, lid = result.outputs

    assert housing_out.kind == "brep" and housing_out.mesh is entry.mesh
    assert lid.kind == "brep"
    assert isinstance(lid.mesh, kernel.Solid)
    assert lid.mesh.is_closed and lid.mesh.solid_count == 1
    expected = 60.0 * 40.0 * 2.4 + (54.0 - EXACT_PLAY) * (34.0 - EXACT_PLAY) * 4.0
    assert lid.mesh.volume == pytest.approx(expected, rel=1e-9)
    assert lid.mesh.bounds.minimum == pytest.approx((-30.0, -20.0, 26.0), abs=1e-6)
    assert lid.mesh.bounds.maximum == pytest.approx((30.0, 20.0, 32.4), abs=1e-6)
    assert _shared_exact_volume(lid.mesh, entry.mesh) < 1e-9
    assert lid.features[COLLAR_FEATURE].params["diameter"] == pytest.approx(34.0 - EXACT_PLAY)
    assert housing_out.features[CAVITY_FEATURE].params["diameter"] == pytest.approx(34.0)
    assert any(
        feature.kind == "face" for name, feature in lid.features.items() if name != COLLAR_FEATURE
    )
    assert step.read(step.write(lid.mesh)).volume == pytest.approx(lid.mesh.volume, rel=1e-9)


def test_the_exact_collar_keeps_the_arcs_of_a_rounded_housing(profile: Profile) -> None:
    """Eine gerundete Dose: Platte und Kragen tragen echte Viertelkreise.

    Außen r = 6, innen r = 3; der Kragen ist die Tasche um das halbe Spiel
    eingezogen, also mit r = 3 − Spiel/2 an den Ecken. Ein Vieleck aus der
    Vernetzung träfe die geschlossene Fläche nicht auf 10⁻⁹.
    """
    exact_kernel()
    entry = exact_box_housing(
        (60.0, 40.0, 30.0),
        [((54.0, 34.0, 28.0), (0.0, 0.0, 3.0))],
        outer_radius=6.0,
        pocket_radius=3.0,
    )
    lid = make_lid(entry, profile, thickness=2.4, collar=4.0, clearance=EXACT_PLAY).outputs[1]

    corner = 4.0 - math.pi
    plate = 60.0 * 40.0 - corner * 6.0**2
    collar = (54.0 - EXACT_PLAY) * (34.0 - EXACT_PLAY) - corner * (3.0 - EXACT_PLAY / 2.0) ** 2
    assert lid.mesh.volume == pytest.approx(plate * 2.4 + collar * 4.0, rel=1e-9)
    assert _cylinder_faces(lid.mesh) == 8, "vier Ecken der Platte, vier des Kragens"
    assert _shared_exact_volume(lid.mesh, entry.mesh) < 1e-9


def test_the_exact_lid_closes_a_side_opening(profile: Profile) -> None:
    """RM-087 am exakten Körper: die Front als Deckel, gebaut nach oben und zurückgedreht."""
    exact_kernel()
    entry = exact_box_housing((40.0, 30.0, 20.0), [((40.0, 26.0, 16.0), (2.0, 0.0, 2.0))])
    front = next(
        name
        for name, feature in entry.features.items()
        if feature.kind == "face"
        and feature.params["normal"][0] > 0.99
        and feature.params["centre"][0] == pytest.approx(20.0)
    )
    result = make_lid(
        entry, profile, thickness=2.4, collar=4.0, clearance=EXACT_PLAY, at_feature=front
    )
    lid = result.outputs[1].mesh

    expected = 30.0 * 20.0 * 2.4 + (26.0 - EXACT_PLAY) * (16.0 - EXACT_PLAY) * 4.0
    assert lid.volume == pytest.approx(expected, rel=1e-9)
    assert lid.bounds.minimum == pytest.approx((16.0, -15.0, 0.0), abs=1e-6)
    assert lid.bounds.maximum == pytest.approx((22.4, 15.0, 20.0), abs=1e-6)
    assert result.findings[0].values["opening"] == "+x"
    assert _shared_exact_volume(lid, entry.mesh) < 1e-9


def test_two_exact_compartments_get_two_collars(profile: Profile) -> None:
    """Zwei Fächer, zwei Kragen, ein Körper — wie am Netz."""
    exact_kernel()
    entry = exact_box_housing(
        (80.0, 40.0, 20.0),
        [((30.0, 34.0, 18.0), (-20.0, 0.0, 2.0)), ((30.0, 34.0, 18.0), (20.0, 0.0, 2.0))],
    )
    result = make_lid(entry, profile, thickness=2.0, collar=3.0, clearance=EXACT_PLAY)
    lid = result.outputs[1].mesh

    assert result.findings[0].values["cavities"] == 2
    assert lid.solid_count == 1
    expected = 80.0 * 40.0 * 2.0 + 2.0 * (30.0 - EXACT_PLAY) * (34.0 - EXACT_PLAY) * 3.0
    assert lid.volume == pytest.approx(expected, rel=1e-9)


def test_a_solid_exact_body_has_nothing_to_close(profile: Profile) -> None:
    """Derselbe Satz wie am Netz, wenn der exakte Körper auf der Höhe massiv ist."""
    exact_kernel()
    entry = exact_box_housing((40.0, 40.0, 20.0), [])

    with pytest.raises(ValidationError) as problem:
        make_lid(entry, profile, collar=4.0, clearance=EXACT_PLAY)

    assert problem.value.constraint == "no_cavity"


# --- der Kragen und die Wand darunter -------------------------------------------

#: Ein Gehäuse mit einer Stufe am Rand: die Tasche 54 x 34, darüber 2 mm tief
#: eine Aufnahme 56 x 36 — ein Deckelsitz, wie ihn viele Kästen haben. Der
#: Schnitt knapp unter dem Rand liegt in der Aufnahme; vier Millimeter tiefer
#: ist die Öffnung die Tasche.
STEPPED = [((54.0, 34.0, 28.0), (0.0, 0.0, 3.0)), ((56.0, 36.0, 3.0), (0.0, 0.0, 28.0))]

#: Eine Leiste mitten in der Kragentiefe: die Tasche 54 x 34, aber zwischen
#: 27 und 28 mm Höhe nur 50 x 30. Oben und unten ist die Öffnung dieselbe —
#: die Leiste sieht nur, wer den Kragen gegen den Körper prüft.
LEDGE = [
    ((54.0, 34.0, 24.0), (0.0, 0.0, 3.0)),
    ((50.0, 30.0, 1.0), (0.0, 0.0, 27.0)),
    ((54.0, 34.0, 3.0), (0.0, 0.0, 28.0)),
]


def mesh_box_housing(
    outer: tuple[float, float, float],
    pockets: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
) -> SceneObject:
    """Dasselbe Gehäuse wie :func:`exact_box_housing`, als Netz."""
    body = trimesh.creation.box(extents=outer)
    body.apply_translation((0.0, 0.0, outer[2] / 2.0))
    cutters = []
    for size, bottom in pockets:
        pocket = trimesh.creation.box(extents=size)
        pocket.apply_translation((bottom[0], bottom[1], bottom[2] + size[2] / 2.0))
        cutters.append(pocket)
    return SceneObject(
        id="obj_1",
        name="Gehäuse",
        mesh=MeshData.of(trimesh.boolean.difference([body, *cutters])),
    )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_stepped_rim_takes_the_collar_from_below(profile: Profile, kind: str) -> None:
    """Der Kragen folgt der engsten Öffnung über seine Tiefe, nicht dem Schnitt am Rand.

    Bis zum 23.09.2026 wurde er aus dem Schnitt 0,1 mm unter dem Rand
    geschnitten — bei einem Deckelsitz, einer gefasten oder verrundeten
    Innenkante oder einer Formschräge ist das die weiteste Stelle, und der
    Kragen ragte darunter in die Wand: an der Wanne ``build_tray_v3.step``
    3860 mm³ Überschneidung, am Netz wie am exakten Körper, ohne ein Wort.
    Jetzt schneidet die Öffnung am Kragenboden mit: Der Kragen ist die
    Tasche 54 × 34, eingezogen um das halbe Spiel.
    """
    if kind == "brep":
        exact_kernel()
        entry = exact_box_housing((60.0, 40.0, 30.0), STEPPED)
    else:
        entry = mesh_box_housing((60.0, 40.0, 30.0), STEPPED)
    from app.core.geom.lid import COLLAR_FEATURE

    result = make_lid(entry, profile, thickness=2.4, collar=4.0, clearance=EXACT_PLAY)
    lid = result.outputs[1]

    expected = 60.0 * 40.0 * 2.4 + (54.0 - EXACT_PLAY) * (34.0 - EXACT_PLAY) * 4.0
    assert lid.mesh.volume == pytest.approx(expected, rel=1e-9)
    if kind == "brep":
        assert _shared_exact_volume(lid.mesh, entry.mesh) < 1e-9
    else:
        assert shared_volume(lid.mesh.raw, entry.mesh.raw) < 1e-6
    assert lid.features[COLLAR_FEATURE].params["diameter"] == pytest.approx(34.0 - EXACT_PLAY)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_ledge_in_the_collar_depth_is_refused_with_the_free_depth(
    profile: Profile, kind: str
) -> None:
    """Was der Schnitt oben und unten nicht sieht, fängt die Prüfung gegen den Körper.

    Ein Kragen, der in die Wand ragt, passt nicht — und wurde bis zum
    23.09.2026 trotzdem ausgegeben. Jetzt sagt die Operation, bis zu welcher
    Tiefe der Kragen frei ist: Die Leiste beginnt 2 mm unter dem Rand. Mit
    1,9 mm entsteht der Deckel.
    """
    if kind == "brep":
        exact_kernel()
        entry = exact_box_housing((60.0, 40.0, 30.0), LEDGE)
    else:
        entry = mesh_box_housing((60.0, 40.0, 30.0), LEDGE)

    with pytest.raises(ValidationError) as problem:
        make_lid(entry, profile, thickness=2.4, collar=4.0, clearance=EXACT_PLAY)

    assert problem.value.field == "collar"
    assert problem.value.constraint == "collar_hits_wall"
    assert problem.value.values["free_depth_mm"] == pytest.approx(2.0, abs=0.01)
    lid = make_lid(entry, profile, thickness=2.4, collar=1.9, clearance=EXACT_PLAY).outputs[1]
    expected = 60.0 * 40.0 * 2.4 + (54.0 - EXACT_PLAY) * (34.0 - EXACT_PLAY) * 1.9
    assert lid.mesh.volume == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_collar_deeper_than_the_tray_is_refused_not_dropped(profile: Profile, kind: str) -> None:
    """Eine flache Schale, 3 mm tief, und ein Kragen von 4 mm: Absage, kein stiller flacher Deckel.

    Der Schnitt am Kragenboden liegt dann im Boden der Schale, und der
    Grundriss „Hohlraum minus Material unten" wäre leer. Ohne Kragen käme eine
    Platte heraus, ohne dass jemand gefragt hätte — der Hohlraum bleibt
    deshalb der Grundriss, und die Prüfung gegen den Körper nennt die freie
    Tiefe.
    """
    tray = [((54.0, 34.0, 4.0), (0.0, 0.0, 7.0))]
    if kind == "brep":
        exact_kernel()
        entry = exact_box_housing((60.0, 40.0, 10.0), tray)
    else:
        entry = mesh_box_housing((60.0, 40.0, 10.0), tray)

    with pytest.raises(ValidationError) as problem:
        make_lid(entry, profile, thickness=2.0, collar=4.0, clearance=EXACT_PLAY)

    assert problem.value.constraint == "collar_hits_wall"
    assert problem.value.values["free_depth_mm"] == pytest.approx(3.0, abs=0.01)


# --- der Drehdeckel -------------------------------------------------------------


def jar(radius: float = 20.0, wall: float = 3.0, height: float = 60.0) -> SceneObject:
    """Eine runde Dose, oben offen: die Form, auf die ein Drehdeckel gehört."""
    outer = trimesh.creation.cylinder(radius=radius, height=height, sections=96)
    outer.apply_translation((0.0, 0.0, height / 2.0))
    inner = trimesh.creation.cylinder(radius=radius - wall, height=height - wall, sections=96)
    inner.apply_translation((0.0, 0.0, height / 2.0 + wall / 2.0 + 0.1))
    return SceneObject(
        id="obj_1", name="Dose", mesh=MeshData.of(trimesh.boolean.difference([outer, inner]))
    )


def make_screw_lid(entry: SceneObject, profile: Profile, **params: object):
    spec = REGISTRY.get("screw_lid")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def radii(body: MeshData, low: float, high: float) -> tuple[float, float]:
    """Kleinster und größter Abstand von der Achse innerhalb eines
    Höhenbandes.
    """
    points = np.asarray(body.raw.vertices)
    inside = points[(points[:, 2] > low) & (points[:, 2] < high)]
    lengths = np.linalg.norm(inside[:, :2], axis=1)
    lengths = lengths[lengths > 1e-9]
    return float(lengths.min()), float(lengths.max())


def test_the_neck_and_the_lid_are_one_thread(profile: Profile) -> None:
    """Die Messung, die es entscheidet: greift der Deckel, oder rutscht er ab?

    Der Deckel ist vom Kerndurchmesser plus Spiel geschnitten, sein Material
    reicht also ins Tal des Halses. Stattdessen vom Außendurchmesser
    geschnitten — der Fehler, den die Mutter der Bausteinbibliothek gemacht
    hat — wäre er eine Hülse.
    """
    result = make_screw_lid(jar(), profile, height=8.0, pitch=3.0)
    neck, lid = result.outputs[0].mesh, result.outputs[1].mesh

    neck_core, neck_crest = radii(neck, 60.5, 67.5)
    lid_core, lid_crest = radii(lid, 1.0, 8.0)

    assert lid_core > neck_core, "the lid has to reach into the valley of the neck"
    assert lid_crest > neck_crest, "and clear its crest"
    gap = profiles.material("petg").clearance
    assert lid_crest - neck_crest == pytest.approx(gap / 2.0, abs=0.02)


def test_both_halves_come_out_closed(profile: Profile) -> None:
    result = make_screw_lid(jar(), profile, height=8.0, pitch=3.0)

    assert result.outputs[0].mesh.is_watertight, "the tin with its neck"
    assert result.outputs[1].mesh.is_watertight, "and the lid"


def test_the_neck_keeps_the_diameter_of_the_opening(profile: Profile) -> None:
    """Ein Hals breiter als die Dose ist ein Deckel, der über die Wand
    hinaussteht, auf der er sitzt.
    """
    result = make_screw_lid(jar(radius=20.0), profile, height=8.0, pitch=3.0)

    assert result.findings[0].values["neck_mm"] == pytest.approx(40.0, abs=0.5)
    assert result.outputs[0].mesh.bounds.size[0] == pytest.approx(40.0, abs=0.1)


def test_the_threaded_neck_keeps_the_container_open_and_names_both_threads(
    profile: Profile,
) -> None:
    """Der einfache Behälterweg baut einen Ring, keinen massiven Gewindebolzen."""
    result = make_screw_lid(jar(radius=20.0, wall=3.0), profile, height=8.0, pitch=3.0)
    container, lid = result.outputs

    cut = container.mesh.raw.section(
        plane_origin=[0.0, 0.0, 64.0],
        plane_normal=[0.0, 0.0, 1.0],
    )
    assert cut is not None
    planar, _ = cut.to_2D()
    # ``polygons_full`` baut einen räumlichen Index und zieht dadurch die
    # optionale Bibliothek rtree in eine reine Geometrieprüfung. Die einzelnen
    # geschlossenen Konturen tragen dieselbe Aussage ohne neue Abhängigkeit.
    # Sehr kleine Konturen entstehen, wenn die Schnittebene genau auf einer
    # Gewindenaht liegt; für Wand und Öffnung sind nur Flächen > 1 mm² relevant.
    areas = [abs(float(trimesh.path.polygons.Polygon(ring).area)) for ring in planar.discrete]
    sections = [area for area in areas if area > 1.0]
    assert len(sections) == 2, "der Schnitt braucht genau Wand und Öffnung"
    assert min(sections) > np.pi * 15.0**2, (
        "der Gewindehals verschließt die Öffnung statt sie ringförmig fortzuführen"
    )
    assert not container.features[NECK_THREAD_FEATURE].params["internal"]
    assert lid.features[CAP_THREAD_FEATURE].params["internal"]
    assert container.features[NECK_THREAD_FEATURE].params["handedness"] == "right"
    assert lid.features[CAP_THREAD_FEATURE].params["handedness"] == "right"


def test_the_lid_stands_on_its_open_end(profile: Profile) -> None:
    """§25: andersherum gedruckt braucht eine Kappe Stützen im eigenen
    Gewinde.
    """
    lid = make_screw_lid(jar(), profile, height=8.0, pitch=3.0).outputs[1].mesh

    assert lid.bounds.minimum[2] == pytest.approx(0.0, abs=0.01)


def test_the_skirt_is_taller_than_the_neck(profile: Profile) -> None:
    """Sonst setzt der Deckel auf dem Gewindeende auf statt auf dem Rand."""
    result = make_screw_lid(jar(), profile, height=8.0, pitch=3.0, thickness=2.4)
    lid = result.outputs[1].mesh

    assert lid.bounds.size[2] > 8.0 + 2.4


def test_the_screw_cap_ceiling_stays_closed(profile: Profile) -> None:
    """Die Gewindenut endet an der Schürze und frisst nicht die Deckeldecke.

    ``thread_body`` reicht um ``pitch * RIDGE_END`` über seine angegebene Höhe
    hinaus. Auf die volle Schürzenhöhe geschnitten, durchbrach die Nut die
    Decke, sobald ``pitch * RIDGE_END`` die Deckelstärke erreichte: bei Steigung
    4 mm ein Loch von rund 25 mm², ab dann ein offener Deckel. Gemessen am
    Querschnitt knapp unter der Deckeloberseite — er muss die volle Scheibe sein.
    """
    lid = make_screw_lid(jar(), profile, height=8.0, pitch=4.0, thickness=2.4).outputs[1].mesh
    top = float(lid.bounds.maximum[2])

    section = lid.raw.section(plane_origin=[0.0, 0.0, top - 0.05], plane_normal=[0.0, 0.0, 1.0])
    assert section is not None, "knapp unter der Decke steht Material"
    planar, _ = section.to_2D()
    outer_radius = float(lid.bounds.size[0]) / 2.0
    full_disk = float(np.pi) * outer_radius**2
    assert full_disk - planar.area < 5.0, "die Decke ist voll, kein Loch der Gewindenut"


def test_a_thin_wall_cannot_carry_a_coarse_thread(profile: Profile) -> None:
    """Zwei Gangtiefen bei 5 mm Steigung passen nicht in eine Wand von 1,5."""
    with pytest.raises(ValidationError) as problem:
        make_screw_lid(jar(radius=20.0, wall=1.5), profile, height=8.0, pitch=5.0)

    assert problem.value.constraint == "too_coarse"


def test_a_softer_material_gets_more_play(profile: Profile) -> None:
    """§12: das Spiel des Gewindes gehört dem Material, wie jedes andere auch."""
    stiff = make_screw_lid(jar(), profile, pitch=3.0).findings[0].values["clearance_mm"]
    soft_jar = jar()
    soft_jar.material = "tpu-95a"
    soft = make_screw_lid(soft_jar, profile, pitch=3.0).findings[0].values["clearance_mm"]

    assert soft > stiff


def test_the_ceiling_of_a_cavity_is_not_an_opening(profile: Profile) -> None:
    """Der Fund der Durchsicht: flach war nicht genug, sie muss nach oben
    schauen.

    Eine unten offene Box hat eine Innendecke — flach, nach unten zeigend, mit
    einem Mittelpunkt bei 26,9 von 30 mm. Als Öffnung gewählt baute sie einen
    Deckel ins Innere der Box, und kein Schritt beschwerte sich, denn ein
    Schnitt unter dieser Ebene trifft ja eine Wand.
    """
    outer = trimesh.creation.box(extents=(60.0, 40.0, 30.0))
    outer.apply_translation((0.0, 0.0, 15.0))
    inner = trimesh.creation.box(extents=(54.0, 34.0, 27.0))
    inner.apply_translation((0.0, 0.0, 13.4))
    body = MeshData.of(trimesh.boolean.difference([outer, inner]))
    features = detect(body)
    ceiling = next(
        entry
        for entry in features.values()
        if entry.kind == "face"
        and entry.params["normal"][2] < -0.9
        and entry.params["centre"][2] > 1
    )
    entry = SceneObject(id="obj_1", name="Kasten", mesh=body, features=features)

    with pytest.raises(ValidationError) as problem:
        make_lid(entry, profile, collar=4.0, at_feature=ceiling.id)

    # Seit RM-087 darf ein Deckel auch nach unten zeigen — was die Innendecke
    # ausschließt, ist nicht mehr ihre Richtung, sondern dass sie innen liegt.
    assert problem.value.constraint == "not_outside"


def test_a_chosen_rim_decides_the_height(profile: Profile) -> None:
    """Und andersherum: die angeklickte Fläche ist die, die zählt."""
    entry = housing()
    entry.features = detect(entry.mesh)
    rim = next(
        feature
        for feature in entry.features.values()
        if feature.kind == "face"
        and feature.params["normal"][2] > 0.9
        and feature.params["centre"][2] == pytest.approx(OUTER[2])
    )

    result = make_lid(entry, profile, collar=4.0, at_feature=rim.id)

    assert result.findings[0].values["z_mm"] == pytest.approx(OUTER[2])


def test_screw_neck_follows_the_translated_opening(profile):
    import dataclasses

    entry = jar()
    shifted = entry.mesh.raw.copy()
    shifted.apply_translation((50, -20, 0))
    entry = dataclasses.replace(entry, mesh=MeshData.of(shifted))
    result = make_screw_lid(entry, profile, height=8, pitch=3)
    neck = result.outputs[0]
    assert neck.mesh.component_count == 1
    assert neck.mesh.bounds.minimum[0] >= 30 - 1e-6
    assert neck.mesh.bounds.maximum[0] <= 70 + 1e-6
    from app.core.geom.lid import NECK_THREAD_FEATURE

    assert neck.features[NECK_THREAD_FEATURE].params["centre"][:2] == pytest.approx((50, -20))


@pytest.mark.parametrize("height,pitch", [(8.0, 3.0), (7.3, 2.0), (5.0, 4.0)])
def test_screw_cap_accepts_the_entire_neck_without_intersection(profile, height, pitch):
    from app.core.geom.boolean import shared_volume

    result = make_screw_lid(jar(wall=5), profile, height=height, pitch=pitch)
    neck, cap = (entry.mesh for entry in result.outputs)
    assembled = cap.raw.copy()
    assembled.apply_translation((0, 0, 60))
    assert shared_volume(neck.raw, assembled) < 1e-5
    assert neck.bounds.maximum[2] == pytest.approx(60 + height, abs=1e-5)


@pytest.mark.parametrize("diameter", [60.0, 100.0, 300.0])
@pytest.mark.parametrize("height,pitch", [(8.0, 3.0), (7.3, 2.0)])
def test_wide_screw_caps_use_the_same_angular_stations_as_the_neck(
    profile, diameter, height, pitch
):
    """Unterschiedlich lange Wendeln dürfen das Spiel nicht durch andere Sehnen aufbrauchen.

    Ø 300 liegt über der alten Grenze der Facettenregel: Gang und Rundkörper
    bekommen dort mehr Sehnen (``lid.turn_sections``), Hals und Kappe dieselben.
    """
    from app.core.geom.lid import turn_sections
    from app.core.units import MAX_FACET_SAG

    result = make_screw_lid(jar(radius=diameter / 2, wall=3), profile, height=height, pitch=pitch)
    neck, cap = (entry.mesh for entry in result.outputs)
    assembled = cap.raw.copy()
    assembled.apply_translation((0, 0, 60))
    assert shared_volume(neck.raw, assembled) < 1e-5
    clearance = result.findings[0].values["clearance_mm"]
    turn, sections = turn_sections(diameter, clearance)
    radius = diameter / 2.0 + clearance
    assert radius * (1.0 - np.cos(np.pi / turn)) <= MAX_FACET_SAG
    assert sections % turn == 0 or turn % sections == 0, "Gang und Rundkörper teilen die Winkel"


def test_a_turned_opening_is_measured_across_its_narrow_side(profile: Profile) -> None:
    """Die Weite einer Öffnung ist ihre schmale Seite, nicht die ihres Hüllrechtecks.

    Die Passung zwischen Deckel und Schachtel prüft zwei Weiten
    (``lid_cavity``, ``lid_collar``). Bis zum 22.09.2026 kamen sie aus dem
    achsparallelen Hüllrechteck — an einem um 45 Grad gedrehten quadratischen
    Fach von 30 mm stand damit 42,4 mm da, die Diagonale, und die Passung
    maß ein Maß, das es am Teil nicht gibt.
    """
    outer = trimesh.creation.box(extents=(70.0, 70.0, 30.0))
    outer.apply_translation((0.0, 0.0, 15.0))
    inner = trimesh.creation.box(extents=(30.0, 30.0, 27.0))
    inner.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 4.0, (0, 0, 1)))
    inner.apply_translation((0.0, 0.0, 16.5))
    body = trimesh.boolean.difference([outer, inner])
    entry = SceneObject(id="obj_1", name="Schachtel", mesh=MeshData.of(body))

    result = make_lid(entry, profile, thickness=2.4, collar=4.0)

    cavity = result.outputs[0].features["lid_cavity"].params["diameter"]
    collar = result.outputs[1].features["lid_collar"].params["diameter"]
    gap = profiles.material("petg").clearance
    assert cavity == pytest.approx(30.0, abs=0.01)
    assert collar == pytest.approx(30.0 - gap, abs=0.01)


def test_a_neck_on_a_turned_square_stays_on_its_wall(profile: Profile) -> None:
    """Der Hals richtet sich nach der schmalen Seite — auch an einer gedrehten Dose.

    ``neck_diameters`` las Außen- und Bohrungsmaß aus dem achsparallelen
    Hüllrechteck. An einer um 45 Grad gedrehten quadratischen Dose von 50 mm
    ist das die Diagonale, 70,7 mm: Der Hals hätte zehn Millimeter über jede
    Seite gestanden. Die schmale Seite ist 50 mm.
    """
    outer = trimesh.creation.box(extents=(50.0, 50.0, 40.0))
    outer.apply_translation((0.0, 0.0, 20.0))
    inner = trimesh.creation.box(extents=(44.0, 44.0, 38.0))
    inner.apply_translation((0.0, 0.0, 22.0))
    body = trimesh.boolean.difference([outer, inner])
    body.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 4.0, (0, 0, 1)))
    entry = SceneObject(id="obj_1", name="Dose", mesh=MeshData.of(body))

    result = make_screw_lid(entry, profile, height=8.0, pitch=3.0)

    neck = result.findings[0].values["neck_mm"]
    assert neck == pytest.approx(50.0, abs=0.01), f"der Hals misst {neck} mm auf 50 mm Wand"


#: Eine Vierteldrehung halbiert um Z — ``edit.transformed`` nimmt die Matrix.
_TURNED_45 = (
    (math.sqrt(0.5), -math.sqrt(0.5), 0.0, 0.0),
    (math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0),
    (0.0, 0.0, 1.0, 0.0),
    (0.0, 0.0, 0.0, 1.0),
)


def test_a_turned_opening_of_an_exact_housing_is_measured_across_its_narrow_side(
    profile: Profile,
) -> None:
    """Die schmale Seite gilt auch am exakten Gehäuse — nicht die Diagonale.

    Zwei Fassungen trafen beim Zusammenführen der Durchsicht 0.5.0 aufeinander:
    die schmale Seite in jeder Drehung (am Netz, ``_narrowest``) und der
    exakte Deckel, der aus dem achsparallelen Hüllrechteck seiner Flächen
    maß. Ein um 45 Grad gedrehtes quadratisches Fach von 30 mm stünde exakt
    wieder mit 42,4 mm in der Passung. Sollwert: die Seite des Fachs.
    """
    exact_kernel()
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.lid import CAVITY_FEATURE, COLLAR_FEATURE

    pocket = edit.moved(edit.transformed(edit.box(30.0, 30.0, 27.0), _TURNED_45), (0, 0, 3.0))
    body = edit.boolean("difference", [edit.box(70.0, 70.0, 30.0), pocket])
    entry = SceneObject(
        id="obj_1", name="Schachtel", mesh=body, kind="brep", features=features_of(body)
    )

    housing_out, lid = make_lid(
        entry, profile, thickness=2.4, collar=4.0, clearance=EXACT_PLAY
    ).outputs

    assert lid.kind == "brep"
    assert housing_out.features[CAVITY_FEATURE].params["diameter"] == pytest.approx(30.0, abs=1e-3)
    assert lid.features[COLLAR_FEATURE].params["diameter"] == pytest.approx(
        30.0 - EXACT_PLAY, abs=1e-3
    )


def test_an_exact_neck_on_a_turned_square_stays_on_its_wall(profile: Profile) -> None:
    """Der exakte Hals richtet sich nach der schmalen Seite der gedrehten Dose.

    Wie :func:`test_a_neck_on_a_turned_square_stays_on_its_wall`, am exakten
    Körper: Das Hüllrechteck der Umrissflächen hätte 70,7 mm gesagt, die
    schmale Seite ist 50 mm.
    """
    exact_kernel()
    from app.core.brep import edit
    from app.core.brep.features import features_of

    jar = edit.boolean(
        "difference",
        [edit.box(50.0, 50.0, 40.0), edit.moved(edit.box(44.0, 44.0, 38.0), (0.0, 0.0, 2.0))],
    )
    body = edit.transformed(jar, _TURNED_45)
    entry = SceneObject(id="obj_1", name="Dose", mesh=body, kind="brep", features=features_of(body))

    result = make_screw_lid(entry, profile, height=8.0, pitch=3.0, clearance=EXACT_PLAY)

    assert result.outputs[0].kind == "brep"
    neck = result.findings[0].values["neck_mm"]
    assert neck == pytest.approx(50.0, abs=1e-3), f"der Hals misst {neck} mm auf 50 mm Wand"


# --- der exakte Drehdeckel ------------------------------------------------------


def exact_jar(
    radius: float = 20.0,
    wall: float = 3.0,
    height: float = 60.0,
    centre: tuple[float, float] = (0.0, 0.0),
) -> SceneObject:
    """Die Dose von :func:`jar` als exakter Körper — Zylinder minus Zylinder."""
    exact_kernel()
    from app.core.brep import edit
    from app.core.brep.features import features_of

    outer = edit.cylinder(2.0 * radius, height)
    inner = edit.moved(edit.cylinder(2.0 * (radius - wall), height), (0.0, 0.0, wall))
    body = edit.boolean("difference", [outer, inner])
    if centre != (0.0, 0.0):
        body = edit.moved(body, (centre[0], centre[1], 0.0))
    return SceneObject(id="obj_1", name="Dose", mesh=body, kind="brep", features=features_of(body))


def _ridge(diameter: float, pitch: float, *, internal: bool = False) -> tuple[float, float]:
    """Fläche und Schwerpunktradius des Gangprofils — unabhängig vom Prüfling gerechnet.

    Ein Trapez mit den Grundseiten entlang der Achse: am Fuß 0,8 Steigungen
    breit, am Kamm 0,3, die Tiefe 0,55 Steigungen (``shapes.RIDGE_*``, hier
    ausgeschrieben). Außen liegt der Fuß eine Tiefe unter dem Durchmesser,
    innen auf ihm.
    """
    depth = 0.55 * pitch
    root = diameter / 2.0 if internal else diameter / 2.0 - depth
    wide, narrow = 0.8 * pitch, 0.3 * pitch
    area = (wide + narrow) / 2.0 * depth
    return area, root + depth * (wide + 2.0 * narrow) / (3.0 * (wide + narrow))


@pytest.mark.parametrize(("height", "pitch"), [(8.0, 3.0), (5.0, 4.0)])
def test_an_exact_jar_gets_an_exact_screw_lid(
    profile: Profile, height: float, pitch: float
) -> None:
    """Am exakten Gehäuse entstehen Hals und Kappe exakt (P2.8: die Bearbeitung fragt den Körper).

    Bis zum 23.09.2026 kam beides als Netz heraus — auch das Gehäuse selbst
    verlor Flächen, Kanten und den STEP-Export. Die Sollwerte sind
    geschlossen: Der Hals ist ein Ring von der Bohrung zum Kern plus dem Gang,
    dessen Volumen über die Höhe h nach Pappus 2π·r̄·A·h/p ist (die
    Schnittebenen halten den waagerechten Querschnitt konstant); die Kappe
    ist der Zylinder minus Kernbohrung minus Nut. Und sie geht ganz über den
    Hals: gleiche Steigung, gleiche Phase, kein gemeinsames Volumen.
    """
    exact_kernel()
    from OCP.BRepCheck import BRepCheck_Analyzer

    from app.core.brep import edit, kernel, step
    from app.core.geom.lid import SKIRT_RELIEF

    entry = exact_jar()
    result = make_screw_lid(entry, profile, height=height, pitch=pitch, clearance=EXACT_PLAY)
    container, cap = result.outputs
    assert container.kind == cap.kind == "brep"
    for body in (container.mesh, cap.mesh):
        assert isinstance(body, kernel.Solid)
        assert body.is_closed and body.solid_count == 1
        assert BRepCheck_Analyzer(body.shape).IsValid()

    major, bore, depth = 40.0, 34.0, 0.55 * pitch
    area, centroid = _ridge(major, pitch)
    neck = math.pi * ((major / 2.0 - depth) ** 2 - (bore / 2.0) ** 2) * height
    neck += 2.0 * math.pi * centroid * area * height / pitch
    assert container.mesh.volume - entry.mesh.volume == pytest.approx(neck, rel=1e-6)

    skirt = height + SKIRT_RELIEF
    inside = major - 2.0 * depth + EXACT_PLAY
    outer = major + 2.0 * EXACT_PLAY + 2.0 * 2.4
    groove_area, groove_centroid = _ridge(inside, pitch, internal=True)
    expected = math.pi * (outer / 2.0) ** 2 * (skirt + 2.4)
    expected -= math.pi * (inside / 2.0) ** 2 * skirt
    expected -= 2.0 * math.pi * groove_centroid * groove_area * skirt / pitch
    assert cap.mesh.volume == pytest.approx(expected, rel=1e-6)

    assert container.mesh.bounds.maximum[2] == pytest.approx(60.0 + height, abs=1e-6)
    assert cap.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)
    assembled = edit.moved(cap.mesh, (0.0, 0.0, 60.0))
    assert _shared_exact_volume(container.mesh, assembled) < 1e-6

    neck_thread = container.features[NECK_THREAD_FEATURE]
    cap_thread = cap.features[CAP_THREAD_FEATURE]
    assert neck_thread.face_indices and cap_thread.face_indices
    assert not neck_thread.params["internal"] and cap_thread.params["internal"]
    threads = [feature for feature in container.features.values() if feature.kind == "thread"]
    assert threads == [neck_thread], "der Hals ist ein Gewinde, kein zweites daneben"
    assert step.read(step.write(container.mesh)).volume == pytest.approx(
        container.mesh.volume, rel=1e-9
    )


@pytest.mark.parametrize(("clearance", "violated"), [(0.0, False), (0.1, True)])
def test_the_exact_screw_lid_fits_its_own_neck(
    profile: Profile, clearance: float, violated: bool
) -> None:
    """Am exakten Kern dasselbe wie am Netz (RM-393): Die Kappe nennt den
    Durchmesser, auf den sie geschnitten ist, und die Passung misst das
    gebaute Spiel — mit dem Spiel aus dem Material ohne Befund, verengt mit."""
    from app.core.scene.fits import check as check_fits
    from app.core.types import FeatureRef, Fit, Scene

    exact_kernel()
    container, cap = make_screw_lid(
        exact_jar(), profile, height=8.0, pitch=3.0, clearance=clearance
    ).outputs
    assert container.kind == cap.kind == "brep"
    cap = dataclasses.replace(cap, id="obj_2")
    played = clearance or profile.material.clearance
    assert cap.features[CAP_THREAD_FEATURE].params["diameter"] == pytest.approx(40.0 + played)
    scene = Scene(
        objects={container.id: container, cap.id: cap},
        fits=[
            Fit(
                name="deckel",
                a=FeatureRef(container.id, NECK_THREAD_FEATURE),
                b=FeatureRef(cap.id, CAP_THREAD_FEATURE),
            )
        ],
    )

    codes = [entry.code for entry in check_fits(scene, profile)]

    assert ("fit.violated" in codes) is violated, codes


def test_the_exact_neck_follows_the_translated_opening(profile: Profile) -> None:
    """Wie am Netz: Der Hals steht über der verschobenen Öffnung, das Merkmal auch."""
    exact_kernel()
    entry = exact_jar(centre=(50.0, -20.0))
    neck = make_screw_lid(entry, profile, height=8.0, pitch=3.0, clearance=EXACT_PLAY).outputs[0]

    assert neck.mesh.solid_count == 1
    assert neck.mesh.bounds.minimum[0] >= 30.0 - 1e-6
    assert neck.mesh.bounds.maximum[0] <= 70.0 + 1e-6
    assert neck.features[NECK_THREAD_FEATURE].params["centre"][:2] == pytest.approx((50.0, -20.0))


@pytest.mark.parametrize(
    ("values", "pitch", "handedness", "starts"),
    [
        ({"form": "whitworth", "tpi": 11.0}, 25.4 / 11.0, "right", 1),
        ({"form": "unified", "tpi": 0.0}, None, "right", 1),
        ({"pitch": 3.0, "starts": 3}, 3.0, "right", 3),
        ({"pitch": 3.0, "left_hand": True}, 3.0, "left", 1),
    ],
    ids=["whitworth", "unified-automatisch", "dreigaengig", "links"],
)
def test_a_screw_lid_takes_inch_forms_starts_and_left_hand(
    profile, values, pitch, handedness, starts
):
    """*Drehdeckel erzeugen* (RM-544): Gänge je Zoll, Whitworth, Gangzahl, Linksgewinde.

    Hals und Deckel kommen aus derselben Gewindeform, und der Deckel geht über den
    ganzen Hals, ohne irgendwo Material zu treffen. Null Gänge je Zoll nimmt die
    Reihe der Form beim Halsdurchmesser.
    """
    from app.core.geom.boolean import shared_volume
    from app.core.geom.lid import CAP_THREAD_FEATURE, NECK_THREAD_FEATURE

    result = make_screw_lid(jar(wall=5), profile, height=8.0, **values)
    container, lid = result.outputs
    neck_thread = container.features[NECK_THREAD_FEATURE].params
    cap_thread = lid.features[CAP_THREAD_FEATURE].params
    if pitch is not None:
        assert neck_thread["pitch"] == pytest.approx(pitch, abs=1e-4)
    assert neck_thread["pitch"] == pytest.approx(cap_thread["pitch"])
    assert neck_thread["handedness"] == cap_thread["handedness"] == handedness
    assert int(neck_thread.get("starts", 1)) == int(cap_thread.get("starts", 1)) == starts
    assembled = lid.mesh.raw.copy()
    assembled.apply_translation((0, 0, 60))
    assert shared_volume(container.mesh.raw, assembled) < 1e-5
