"""Aushöhlen mit wählbarer offener Seite und der Deckel davor (RM-087).

Roberts Beispiel vom 02.09.2026: ein Puppenhaus, Räume ausgehöhlt, die
Vorderseite offen. *Oben öffnen* nahm nur die Decke; der Weg zur offenen Seite
war Aushöhlen plus eine Tasche oder ein Schnitt durch die Wand. Jetzt trägt
sich die angeklickte Fläche als ``open_at`` ein, und *Deckel erzeugen* baut
den Deckel vor genau diese Öffnung.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.autosplit import upright_normal
from app.core.geom.hollow import hollow
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.scene.placement import values_for
from app.core.slice.analysis import cross_section
from app.core.types import Feature, OpContext, Profile, Scene, SceneObject, Vec3

SIZE = (60.0, 40.0, 30.0)

#: Die sechs Achsrichtungen, in die sich ein Hohlraum öffnen lässt.
DIRECTIONS: tuple[Vec3, ...] = (
    (0.0, 0.0, 1.0),
    (0.0, 0.0, -1.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
)


def box() -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=SIZE))


def run(op: str, entry: SceneObject, profile: Profile, **params: Any) -> Any:
    """Eine Operation so fahren, wie die Auswertung sie fährt."""
    load_operations()
    spec = REGISTRY.get(op)
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


def holes_facing(mesh: MeshData, direction: Vec3) -> int:
    """Wie viele Löcher der Querschnitt einen Millimeter hinter der Außenwand
    in ``direction`` hat — null heißt geschlossen, eins heißt offen.

    Gemessen im aufgerichteten Raum, damit derselbe Schnitt für jede der sechs
    Richtungen gilt: ``upright_normal`` dreht die Richtung nach oben, und
    ``cross_section`` schneidet bei z.
    """
    turned = mesh.raw.copy()
    turned.apply_transform(upright_normal(direction))
    top = float(turned.bounds[1][2])
    shape = cross_section(MeshData.of(turned), top - 1.0)
    assert shape is not None and not shape.is_empty, "der Schnitt trifft die Wand"
    parts = list(getattr(shape, "geoms", [shape]))
    return sum(len(part.interiors) for part in parts)


@pytest.mark.parametrize("direction", DIRECTIONS)
def test_the_hollow_opens_towards_the_chosen_side_and_nowhere_else(direction: Vec3) -> None:
    """Die Öffnung liegt an der gewählten Seite, die Gegenseite bleibt zu.

    Gemessen am Schnitt einen Millimeter hinter der Wand: An der Öffnung ist
    der Schnitt ein Ring (die Wand mit dem Hohlraum als Loch), gegenüber eine
    volle Fläche. Wasserdicht bleibt es in jeder Richtung — eine Öffnung ist
    ein Loch im Körper, kein Loch im Netz.
    """
    result = hollow(box(), 3.0, vents=0, open_towards=direction)

    assert result.mesh.raw.is_watertight
    assert holes_facing(result.mesh, direction) == 1, "an der Öffnung ist die Wand ein Ring"
    opposite: Vec3 = (-direction[0], -direction[1], -direction[2])
    assert holes_facing(result.mesh, opposite) == 0, "gegenüber ist die Wand geschlossen"
    done = next(finding for finding in result.findings if finding.code == "hollow.done")
    axis = int(np.argmax(np.abs(direction)))
    assert done.values["opening"] == ("+" if direction[axis] > 0 else "-") + "xyz"[axis]
    assert done.values["vents"] == 0, "eine offene Seite braucht keine Entlüftung"


def test_open_top_is_the_same_as_opening_upwards() -> None:
    """Der alte Haken und die neue Richtung sind eine Sache — bitgleich."""
    with_flag = hollow(box(), 3.0, vents=0, open_top=True).mesh.raw
    with_direction = hollow(box(), 3.0, vents=0, open_towards=(0.0, 0.0, 1.0)).mesh.raw

    assert with_flag.volume == pytest.approx(with_direction.volume)
    assert np.array_equal(with_flag.vertices, with_direction.vertices)


def test_a_direction_beats_the_flag() -> None:
    """Gesetzt schlägt ``open_towards`` das ``open_top`` — nicht beides."""
    result = hollow(box(), 3.0, vents=0, open_top=True, open_towards=(0.0, -1.0, 0.0))

    assert holes_facing(result.mesh, (0.0, -1.0, 0.0)) == 1
    assert holes_facing(result.mesh, (0.0, 0.0, 1.0)) == 0, "die Decke bleibt zu"


# --- die Operation: die angeklickte Fläche trägt sich ein ---------------------------


def house() -> SceneObject:
    body = trimesh.creation.box(extents=(120.0, 80.0, 90.0))
    body.apply_translation((0.0, 0.0, 45.0))
    mesh = MeshData.of(body)
    return SceneObject(id="obj_1", name="Haus", mesh=mesh, features=detect(mesh))


def face_towards(entry: SceneObject, direction: Vec3) -> str:
    """Die Außenfläche des Körpers, die in diese Richtung zeigt."""
    axis = int(np.argmax(np.abs(direction)))
    edge = (entry.mesh.bounds.maximum if direction[axis] > 0 else entry.mesh.bounds.minimum)[axis]
    return next(
        key
        for key, feature in entry.features.items()
        if feature.kind == "face"
        and float(np.dot(feature.params["normal"], direction)) > 0.9
        and abs(float(feature.params["centre"][axis]) - float(edge)) < 0.5
    )


def test_the_dollhouse_opens_at_its_front(profile: Profile) -> None:
    """Roberts Beispiel: die Vorderseite offen, der Rest geschlossen.

    Die Fläche kommt als ``obj_1:face_n``, so wie ein Klick sie einträgt; die
    nackte Kennung geht ebenso.
    """
    entry = house()
    front = face_towards(entry, (0.0, -1.0, 0.0))

    qualified = run("hollow_object", entry, profile, wall=3.0, vents=0, open_at=f"obj_1:{front}")
    bare = run("hollow_object", entry, profile, wall=3.0, vents=0, open_at=front)

    for result in (qualified, bare):
        opened = result.outputs[0].mesh
        assert holes_facing(opened, (0.0, -1.0, 0.0)) == 1, "vorn offen"
        assert holes_facing(opened, (0.0, 0.0, 1.0)) == 0, "die Decke bleibt zu"
        assert holes_facing(opened, (0.0, 1.0, 0.0)) == 0, "die Rückwand bleibt zu"
    assert qualified.outputs[0].mesh.raw.volume == pytest.approx(bare.outputs[0].mesh.raw.volume)


def test_a_clicked_face_fills_the_opening_field_and_a_bore_does_not(profile: Profile) -> None:
    """Der Puppenhaus-Weg ist ein Klick: Fläche wählen, Strg+H, Übernehmen.

    ``values_for`` trägt eine Fläche als Ziel ein — und eine Bohrung nicht,
    denn an einer Bohrung lässt sich nichts öffnen.
    """
    load_operations()
    spec = REGISTRY.get("hollow_object")
    entry = house()
    front = face_towards(entry, (0.0, -1.0, 0.0))

    assert values_for(spec, entry.features[front], "obj_1").get("open_at") == f"obj_1:{front}"

    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"diameter": 5.0, "centre": (0.0, 0.0, 90.0), "axis": (0.0, 0.0, 1.0)},
    )
    assert "open_at" not in values_for(spec, bore, "obj_1")


@pytest.mark.parametrize(
    ("open_at", "constraint"),
    [
        ("obj_2:face_1", "foreign_feature"),
        ("face_999", "unknown_feature"),
        ("hole_1", "not_a_face"),
        ("face_slanted", "not_axis_aligned"),
    ],
)
def test_every_refusal_of_the_opening_face_names_its_reason(
    profile: Profile, open_at: str, constraint: str
) -> None:
    """Vier Absagen, jede mit Grund und Handlungsvorschlag (Regel 17)."""
    entry = house()
    features = dict(entry.features)
    features["hole_1"] = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"diameter": 5.0, "centre": (0.0, 0.0, 90.0), "axis": (0.0, 0.0, 1.0)},
    )
    features["face_slanted"] = Feature(
        id="face_slanted",
        kind="face",
        provenance="detected",
        params={"area": 100.0, "centre": (0.0, 0.0, 90.0), "normal": (0.6, 0.0, 0.8)},
    )
    entry = SceneObject(id="obj_1", name="Haus", mesh=entry.mesh, features=features)

    with pytest.raises(ValidationError) as caught:
        run("hollow_object", entry, profile, wall=3.0, vents=0, open_at=open_at)

    assert caught.value.constraint == constraint
    assert caught.value.field == "open_at"
    assert caught.value.suggestions, "eine Absage ohne Weg nach vorn ist keine (Regel 17)"


# --- der Deckel vor der Seitenöffnung ---------------------------------------------


def opened_house(profile: Profile, direction: Vec3) -> tuple[SceneObject, str]:
    """Das Haus, in diese Richtung geöffnet, samt der Fläche seines Rands."""
    entry = house()
    opened = run(
        "hollow_object",
        entry,
        profile,
        wall=3.0,
        vents=0,
        open_at=face_towards(entry, direction),
    ).outputs[0]
    hollowed = SceneObject(id="obj_1", name="Haus", mesh=opened.mesh, features=detect(opened.mesh))
    return hollowed, face_towards(hollowed, direction)


@pytest.mark.parametrize("direction", [(0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0)])
def test_the_lid_sits_in_front_of_the_side_opening(profile: Profile, direction: Vec3) -> None:
    """Der Deckel liegt vor der Öffnung, in der Richtung, in die sie zeigt.

    Platte außen, Kragen innen — gemessen an den Grenzen des Deckels entlang
    der Öffnungsrichtung: Er beginnt eine Kragentiefe innerhalb der Wand und
    endet eine Plattenstärke davor. Kragen und Hohlraummerkmal tragen die
    Richtung als Normale, damit eine Passung sie prüfen kann.
    """
    hollowed, rim = opened_house(profile, direction)
    axis = int(np.argmax(np.abs(direction)))
    sign = 1.0 if direction[axis] > 0 else -1.0
    edge = float((hollowed.mesh.bounds.maximum if sign > 0 else hollowed.mesh.bounds.minimum)[axis])

    result = run("create_lid", hollowed, profile, thickness=2.4, collar=4.0, at_feature=rim)

    lid = result.outputs[1]
    assert lid.mesh.raw.is_watertight
    low, high = lid.mesh.raw.bounds[0][axis], lid.mesh.raw.bounds[1][axis]
    outer, inner = (high, low) if sign > 0 else (low, high)
    assert outer == pytest.approx(edge + sign * 2.4, abs=1e-6), "die Platte steht davor"
    assert inner == pytest.approx(edge - sign * 4.0, abs=1e-6), "der Kragen greift hinein"
    collar = lid.features["lid_collar"]
    assert tuple(collar.params["normal"]) == pytest.approx(direction)
    assert float(collar.params["centre"][axis]) == pytest.approx(edge, abs=1e-6)
    cavity = result.outputs[0].features["lid_cavity"]
    assert tuple(cavity.params["normal"]) == pytest.approx(direction)
    done = next(finding for finding in result.findings if finding.code == "parts.lid")
    assert done.values["opening"] == ("+" if sign > 0 else "-") + "xyz"[axis]


def test_the_lid_at_the_top_is_built_as_before(profile: Profile) -> None:
    """Die Decke geht denselben Weg wie vor RM-087 — ohne Drehung, gleiche Zahlen."""
    hollowed, rim = opened_house(profile, (0.0, 0.0, 1.0))

    result = run("create_lid", hollowed, profile, thickness=2.4, collar=4.0, at_feature=rim)

    lid = result.outputs[1]
    assert lid.mesh.raw.bounds[1][2] == pytest.approx(90.0 + 2.4)
    assert lid.mesh.raw.bounds[0][2] == pytest.approx(90.0 - 4.0)
    assert tuple(lid.features["lid_collar"].params["normal"]) == (0.0, 0.0, 1.0)


def test_the_inner_wall_is_refused_as_a_lid_opening(profile: Profile) -> None:
    """Die Rückwand-Innenseite zeigt nach vorn wie die Öffnung — und liegt innen.

    Sie ist die größte Fläche in dieser Richtung, und wer sie nähme, setzte den
    Deckel mitten ins Haus. Dieselbe Falle wie die Hohlraumdecke bei
    ``plane_of``, hier in jeder Richtung gehalten.
    """
    hollowed, _rim = opened_house(profile, (0.0, -1.0, 0.0))
    inner = max(
        (
            (key, feature)
            for key, feature in hollowed.features.items()
            if feature.kind == "face" and feature.params["normal"][1] < -0.9
        ),
        key=lambda item: float(item[1].params.get("area", 0.0)),
    )[0]
    assert float(hollowed.features[inner].params["centre"][1]) > 0.0, "sonst prüft das nichts"

    with pytest.raises(ValidationError) as caught:
        run("create_lid", hollowed, profile, thickness=2.4, collar=4.0, at_feature=inner)

    assert caught.value.constraint == "not_outside"


def test_the_screw_lid_grows_its_neck_out_of_the_side_opening(profile: Profile) -> None:
    """Der Drehdeckel geht denselben Weg: Der Hals wächst aus der Seitenöffnung.

    Gemessen am Gehäuse mit Hals — es reicht um die Halshöhe über die
    Vorderseite hinaus, und das Gewindemerkmal des Halses zeigt in die
    Öffnungsrichtung. Die Kappe bleibt am Ursprung, wie beim Deckel nach oben.
    """
    hollowed, rim = opened_house(profile, (0.0, -1.0, 0.0))
    front = float(hollowed.mesh.bounds.minimum[1])

    result = run(
        "screw_lid",
        hollowed,
        profile,
        height=8.0,
        pitch=2.0,
        wall=2.0,
        thickness=3.0,
        at_feature=rim,
    )

    with_neck = result.outputs[0]
    assert with_neck.mesh.bounds.minimum[1] == pytest.approx(front - 8.0, abs=0.2), (
        "der Hals steht um seine Höhe vor der Vorderseite"
    )
    assert with_neck.mesh.bounds.maximum[2] == pytest.approx(90.0, abs=1e-6), "oben wächst nichts"
    thread = with_neck.features["lid_neck_thread"]
    assert tuple(thread.params["axis"]) == pytest.approx((0.0, -1.0, 0.0))
    assert float(thread.params["centre"][1]) == pytest.approx(front - 4.0, abs=1e-6)
    assert result.outputs[1].mesh.raw.is_watertight, "die Kappe ist ein Körper"


def test_reason_against_frees_the_side_of_an_open_house_and_keeps_the_inside_grey(
    profile: Profile,
) -> None:
    """Die Auswahlkarte fragt ``reason_against`` vor dem Klick — und seit RM-087
    sagt es an der Seitenöffnung nichts mehr, an der Innenwand weiter „innen".
    """
    from app.core.geom.lid import reason_against

    hollowed, rim = opened_house(profile, (0.0, -1.0, 0.0))
    inner = max(
        (
            (key, feature)
            for key, feature in hollowed.features.items()
            if feature.kind == "face" and feature.params["normal"][1] < -0.9
        ),
        key=lambda item: float(item[1].params.get("area", 0.0)),
    )[0]

    assert reason_against(hollowed, rim) is None, "die Seitenöffnung ist frei"
    assert "Inneren" in (reason_against(hollowed, inner) or "")
    solid = house()
    assert "massiv" in (reason_against(solid, face_towards(solid, (0.0, -1.0, 0.0))) or "")
