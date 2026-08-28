"""Der Deckel über einer Öffnung (§25, §14, §40).

Eine Box mit bekannten Maßen, damit sich jede Zahl nachprüfen lässt, mit der
der Deckel herauskommt: der Kragen ist der Hohlraum minus zweimal das Spiel,
und der Beweis, dass er passt, ist, dass Deckel und Gehäuse gar kein Volumen
teilen.
"""

from __future__ import annotations

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

load_operations()

#: Das Gehäuse, gegen das jeder Test misst: 60 x 40 x 30 außen, 3 mm Wände,
#: 1,5 mm Boden, oben offen. Hohlraum 54 x 34.
OUTER = (60.0, 40.0, 30.0)
CAVITY = (54.0, 34.0)


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
    assert len(planar.polygons_full) == 1
    openings = [
        abs(float(trimesh.path.polygons.Polygon(ring).area))
        for ring in planar.polygons_full[0].interiors
    ]
    assert openings and max(openings) > np.pi * 15.0**2, (
        "der Gewindehals verschließt die Öffnung statt sie ringförmig fortzuführen"
    )
    assert not container.features[NECK_THREAD_FEATURE].params["internal"]
    assert lid.features[CAP_THREAD_FEATURE].params["internal"]


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

    assert problem.value.constraint == "not_upright"


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
