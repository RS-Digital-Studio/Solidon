"""Drehender und kombinierter Fügeweg (RM-184, Audit §9 „Verschlusspaar“).

Der lineare Fügeweg fragt, ob ein Teil geradeaus in seine Endlage kommt. Ein
Bajonett kommt so nicht hinein: Es wird axial eingesetzt und dann gedreht, ein
Klappdeckel schwenkt um seine Achse. Geprüft wird hier, dass *Fügeweg prüfen*
beide Bewegungen kennt — an der Quelle des Audits (Filterkäfig, drei Nocken,
Einführtiefe 6, Drehweg 13°) und an kleinen analytischen Körpern.
"""

from __future__ import annotations

from typing import Any

import pytest
import trimesh

from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import check_join_path
from app.core.knowledge.parts import PARTS, shapes
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject

#: Der Filterkäfig aus dem Audit (Familie 3, ``kartuschen_kaefig.py``).
FILTER_CAGE: dict[str, Any] = {
    "diameter": 75.0,
    "lugs": 3,
    "lug_width": 6.0,
    "lug_height": 3.5,
    "entry": 6.0,
    "turn": 13.0,
    "wall": 2.0,
}


def _bayonet(profile: Profile) -> tuple[MeshData, MeshData, dict[str, float]]:
    """Aufnahme und Kragen in Endlage: eingesetzt und um den Drehweg gedreht."""
    from app.core.knowledge.parts.closures import bayonet_frame

    spec = PARTS.get("bayonet")
    play = profile.material.clearance
    socket = spec.fn(spec.params(kind="socket", play=play, **FILTER_CAGE)).mesh
    plug_params = spec.params(kind="plug", play=play, **FILTER_CAGE)
    frame = bayonet_frame(plug_params)
    plug = spec.fn(plug_params).mesh
    inserted = shapes.moved(shapes.turned(plug, 180.0, (1.0, 0.0, 0.0)), (0.0, 0.0, frame["rim"]))
    locked = shapes.turned(inserted, FILTER_CAGE["turn"])
    return as_mesh_data(locked), as_mesh_data(socket), frame


def test_a_bayonet_needs_the_combined_way_and_the_check_knows_it(profile: Profile) -> None:
    """Axial einsetzen, dann um 13° drehen: frei. Geradeaus in die Endlage: nicht.

    Beide Ausgänge gehören zur Aussage — eine Prüfung, die jeden Weg frei
    nennt, bestünde den ersten Teil auch.
    """
    locked, socket, frame = _bayonet(profile)
    distance = frame["collar"] + 2.0

    combined = check_join_path(
        locked,
        socket,
        (0.0, 0.0, -1.0),
        distance,
        steps=8,
        turn=FILTER_CAGE["turn"],
        turn_axis=(0.0, 0.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )
    assert [finding.code for finding in combined] == ["join.clear"], combined
    clear = combined[0]
    assert clear.values["motion"] == "slide_turn"
    assert clear.values["angle_deg"] == pytest.approx(13.0)
    assert clear.values["length_mm"] == pytest.approx(distance)
    assert "13" in str(clear.message), "der Drehwinkel steht im Satz"

    straight = check_join_path(locked, socket, (0.0, 0.0, -1.0), distance, steps=8)
    assert [finding.code for finding in straight] == ["join.interference"], (
        "geradeaus in die verriegelte Lage stoßen die Nocken durch die Wand"
    )


def test_a_turn_alone_is_checked_over_its_whole_angle(profile: Profile) -> None:
    """Nur gedreht: aus der Einsetzstellung um den Drehweg frei — darüber hinaus nicht.

    Die Endlage über den Anschlag hinaus ist besetzt: Das ist eine Sperre,
    gleich was auf dem Weg geschah.
    """
    locked, socket, frame = _bayonet(profile)
    turned = check_join_path(
        locked,
        socket,
        (0.0, 0.0, -1.0),
        0.0,
        steps=6,
        turn=FILTER_CAGE["turn"],
        turn_axis=(0.0, 0.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )
    assert [finding.code for finding in turned] == ["join.clear"], turned
    assert turned[0].values["motion"] == "turn"
    assert "length_mm" not in turned[0].values, "ohne Schub keine Strecke"

    beyond = as_mesh_data(shapes.turned(locked, frame["margin"] + 4.0))
    blocked = check_join_path(
        beyond,
        socket,
        (0.0, 0.0, -1.0),
        0.0,
        turn=FILTER_CAGE["turn"] + frame["margin"] + 4.0,
        turn_axis=(0.0, 0.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )
    assert [finding.code for finding in blocked] == ["join.blocked"], blocked


def test_a_swing_that_sweeps_through_a_post_is_found_on_the_way() -> None:
    """Analytisch: eine Klappe, die beim Schwenken über einen Pfosten streicht.

    Klappe 40 × 4 × 2 an einer Achse in Z durch den Ursprung, Endlage entlang
    +X. Steht ein Pfosten bei 45° im Schwenkbereich, ist die Endlage frei, der
    Weg nicht — und der Befund nennt den Winkel, an dem es eng wird. Steht er
    außerhalb, ist der Weg frei.
    """
    flap = trimesh.creation.box(extents=(40.0, 4.0, 2.0))
    flap.apply_translation((20.0, 0.0, 0.0))
    post = trimesh.creation.box(extents=(4.0, 4.0, 10.0))
    post.apply_translation((20.0, 20.0, 0.0))

    found = check_join_path(
        MeshData.of(flap),
        MeshData.of(post),
        (0.0, 0.0, 1.0),
        0.0,
        steps=18,
        turn=-90.0,
        turn_axis=(0.0, 0.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )
    assert [finding.code for finding in found] == ["join.interference"], found
    at = found[0].values["at_deg"]
    assert 35.0 <= at <= 55.0, f"der Pfosten steht bei 45°, gemeldet {at}°"

    away = post.copy()
    away.apply_translation((0.0, -40.0, 0.0))
    clear = check_join_path(
        MeshData.of(flap),
        MeshData.of(away),
        (0.0, 0.0, 1.0),
        0.0,
        steps=18,
        turn=-90.0,
        turn_axis=(0.0, 0.0, 1.0),
        pivot=(0.0, 0.0, 0.0),
    )
    assert [finding.code for finding in clear] == ["join.clear"], clear


def _run(entries: list[SceneObject], profile: Profile, **params: object) -> Any:
    spec = REGISTRY.get("check_join_path")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in entries}),
            inputs=entries,
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_the_operation_turns_about_the_chosen_centre_and_keeps_old_steps(
    profile: Profile,
) -> None:
    """Die Operation: ``motion`` wählt die Bewegung, ``cx/cy/cz`` die Drehmitte.

    Ein alter Schritt ohne die neuen Felder bleibt der lineare Weg von damals;
    eine leere Drehmitte wird einmal aus dem bewegten Körper genommen und
    festgehalten.
    """
    locked, socket, frame = _bayonet(profile)
    moving = SceneObject(id="obj_1", name="Kragen", mesh=locked)
    fixed = SceneObject(id="obj_2", name="Aufnahme", mesh=socket)

    result = _run(
        [moving, fixed],
        profile,
        motion="slide_turn",
        axis="z",
        reverse=True,
        distance=frame["collar"] + 2.0,
        angle=13.0,
        steps=8,
        cx=0.0,
        cy=0.0,
        cz=0.0,
    )
    assert [finding.code for finding in result.findings] == ["join.clear"]
    assert [entry.id for entry in result.outputs] == ["obj_1", "obj_2"], "nichts geändert"
    assert not result.answered, "eine genannte Mitte wird nicht überschrieben"

    old = _run([moving, fixed], profile, axis="z", reverse=True, distance=frame["collar"] + 2.0)
    assert [finding.code for finding in old.findings] == ["join.interference"], (
        "ohne Bewegungsart bleibt es der lineare Weg"
    )
    assert not old.answered, "ein linearer Weg braucht keine Drehmitte"

    centred = _run([moving, fixed], profile, motion="turn", axis="z", angle=5.0, steps=4)
    centre = as_mesh_data(locked).bounds.centre
    assert centred.answered == pytest.approx({"cx": centre[0], "cy": centre[1], "cz": centre[2]}), (
        "die Körpermitte wird einmal genommen und gespeichert"
    )


def test_old_steps_have_no_motion_and_the_schema_says_linear() -> None:
    """Die neuen Felder haben Vorgaben, die den alten Schritt unverändert lassen."""
    spec = REGISTRY.get("check_join_path")
    defaults = {entry.name: entry.default for entry in spec.params.spec()}
    assert defaults["motion"] == "slide"
    assert defaults["angle"] == pytest.approx(90.0), "ein Klappdeckel schwenkt um einen rechten"
    assert defaults["cx"] is None and defaults["cy"] is None and defaults["cz"] is None
