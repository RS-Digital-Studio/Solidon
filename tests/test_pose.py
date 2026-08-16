"""Posing (Konzept P16.8, Entscheidung I).

Drei Streichungen machen das gegenüber einem Animationsprogramm klein, und
alle drei werden hier geprüft: eine Pose statt einer Bewegung,
Vorwärtskinematik statt inverser, gerechnete Gewichte statt gespeicherter.

Der vierte Punkt ist der, an dem Posing hierher gehört und nicht zu Blender —
ein Gelenkwinkel darf ein Projektparameter sein. Das prüft die
Ausdrucksauflösung der Szene, nicht diese Datei; hier steht, dass die
Operation eine gewöhnliche Zahl bekommt und nichts Besonderes daraus macht.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.geom.pose import (
    armature_from_text,
    armature_to_text,
    pose_from_text,
    pose_to_text,
    posed,
    transforms,
    weights,
)
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Bone, OpContext, OpResult, Pose, Profile, Scene, SceneObject


def arm() -> MeshData:
    """Ein liegender Stab entlang X, fein genug zum Beugen."""
    body = trimesh.creation.cylinder(radius=3.0, height=40.0, sections=24)
    body.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
    vertices, faces = trimesh.remesh.subdivide_to_size(
        np.asarray(body.vertices, dtype=float), np.asarray(body.faces, dtype=np.int64), 2.0
    )
    fine = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    fine.merge_vertices()
    return MeshData.of(fine)


def two_bones() -> list[Bone]:
    """Ober- und Unterarm, das Kind am Fuß des Elternteils."""
    return [
        Bone(name="upper", head=(-20.0, 0.0, 0.0), tail=(0.0, 0.0, 0.0)),
        Bone(name="lower", head=(0.0, 0.0, 0.0), tail=(20.0, 0.0, 0.0), parent="upper"),
    ]


def run(entry: SceneObject, profile: Profile, **params: object) -> OpResult:
    spec = REGISTRY.get("pose_armature")
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


# --- die Gewichte ---------------------------------------------------------------


def test_every_vertex_belongs_somewhere() -> None:
    """Zeilenweise auf eins normiert — ein Eckpunkt, der nirgends hängt,
    bliebe beim Beugen stehen, während sein Nachbar mitgeht.
    """
    field = weights(arm(), two_bones())

    assert field.shape[1] == 2
    assert np.allclose(field.sum(axis=1), 1.0)
    assert (field >= 0.0).all()


def test_a_vertex_belongs_to_the_bone_it_sits_on() -> None:
    """Nah heißt stark. Ohne das wäre die Rechnung eine beliebige Verteilung."""
    body = arm()
    field = weights(body, two_bones())
    points = np.asarray(body.raw.vertices, dtype=float)

    left = points[:, 0] < -10.0
    right = points[:, 0] > 10.0
    assert field[left, 0].mean() > field[left, 1].mean(), "links hängt am Oberarm"
    assert field[right, 1].mean() > field[right, 0].mean(), "rechts am Unterarm"


def test_the_distance_is_to_the_segment_not_the_axis() -> None:
    """Ein Knochen hat zwei Enden, und dazwischen liegt er.

    Auf einer unendlichen Achse bände der Oberarm die Fußspitze an sich,
    sobald beide zufällig auf einer Geraden liegen.
    """
    far = MeshData.of(trimesh.creation.icosphere(subdivisions=1, radius=1.0))
    moved = far.raw.copy()
    moved.apply_translation((200.0, 0.0, 0.0))

    field = weights(MeshData.of(moved), two_bones())

    assert field[:, 1].mean() > field[:, 0].mean(), "der nähere Knochen gewinnt"


# --- Vorwärtskinematik ----------------------------------------------------------


def test_a_child_inherits_what_its_parent_did() -> None:
    """Wer den Oberarm hebt, hebt den Unterarm mit, ohne ihn zu nennen.

    Das *ist* Vorwärtskinematik, und ohne sie bliebe der Unterarm stehen,
    während der Oberarm sich dreht.
    """
    matrices = transforms(two_bones(), {"upper": (0.0, 90.0, 0.0)})

    # Die Spitze liegt 40 mm vom Kopf des Oberarms entfernt. Um 90 Grad um Y
    # gedreht steht sie senkrecht darunter — bei x des Kopfes, nicht bei null:
    # Gedreht wird um den Kopf, und der sitzt bei x = -20.
    tip = np.array([20.0, 0.0, 0.0, 1.0])
    moved = matrices["lower"] @ tip
    assert moved[0] == pytest.approx(-20.0, abs=1e-6), "der Unterarm ist mitgedreht"
    assert moved[2] == pytest.approx(-40.0, abs=1e-6)


def test_a_bone_turns_about_its_own_head() -> None:
    """Um den Kopf des Knochens, nicht um den Weltursprung.

    Ein Arm, der sich um den Ursprung dreht, fliegt vom Körper weg — der
    klassische erste Fehler beim Skinning.
    """
    matrices = transforms(two_bones(), {"upper": (0.0, 90.0, 0.0)})

    head = np.array([-20.0, 0.0, 0.0, 1.0])
    assert np.allclose((matrices["upper"] @ head)[:3], head[:3], atol=1e-9)


def test_bones_are_ordered_parents_first_whatever_the_list_says() -> None:
    """Die Reihenfolge in der Datei ist keine Zusage über den Baum."""
    reversed_order = list(reversed(two_bones()))

    matrices = transforms(reversed_order, {"upper": (0.0, 90.0, 0.0)})

    tip = np.array([20.0, 0.0, 0.0, 1.0])
    assert (matrices["lower"] @ tip)[0] == pytest.approx(-20.0, abs=1e-6)


def test_a_bone_hanging_on_itself_is_refused() -> None:
    """Ein Zyklus hält an, statt endlos zu laufen — mit einem Vorschlag."""
    circular = [
        Bone(name="a", head=(0.0, 0.0, 0.0), tail=(1.0, 0.0, 0.0), parent="b"),
        Bone(name="b", head=(1.0, 0.0, 0.0), tail=(2.0, 0.0, 0.0), parent="a"),
    ]

    with pytest.raises(ValidationError) as raised:
        transforms(circular, {})

    assert raised.value.suggestions


# --- was mit dem Körper passiert ------------------------------------------------


def test_bending_moves_the_far_end_and_leaves_the_near_one(profile: Profile) -> None:
    """Der Zweck, an einer Form, deren Ergebnis sich vorhersagen lässt."""
    body = arm()
    entry = SceneObject(id="obj_1", name="Arm", mesh=body)

    result = run(
        entry,
        profile,
        armature=armature_to_text(two_bones()),
        pose=pose_to_text([Pose(bone="lower", angles=(0.0, 45.0, 0.0))]),
    )

    after = result.outputs[0].mesh
    before_points = np.asarray(body.raw.vertices, dtype=float)
    after_points = np.asarray(after.raw.vertices, dtype=float)
    moved = np.linalg.norm(after_points - before_points, axis=1)
    assert moved[before_points[:, 0] > 15.0].mean() > 1.0, "das ferne Ende geht mit"
    assert moved[before_points[:, 0] < -15.0].mean() < 0.5, "das nahe bleibt"
    assert after.triangle_count == body.triangle_count


def test_an_empty_pose_leaves_the_body_alone(profile: Profile) -> None:
    """Der Nullpunkt — alle Winkel null heißt: nichts tun."""
    body = arm()
    entry = SceneObject(id="obj_1", name="Arm", mesh=body)

    result = run(
        entry,
        profile,
        armature=armature_to_text(two_bones()),
        pose=pose_to_text([Pose(bone="lower", angles=(0.0, 0.0, 0.0))]),
    )

    assert np.array_equal(
        np.asarray(result.outputs[0].mesh.raw.vertices), np.asarray(body.raw.vertices)
    )


def test_posing_twice_gives_the_same_body(profile: Profile) -> None:
    """Zweimal auswerten muss identisch sein."""
    entry = SceneObject(id="obj_1", name="Arm", mesh=arm())
    text = armature_to_text(two_bones())
    stance = pose_to_text([Pose(bone="lower", angles=(0.0, 30.0, 0.0))])

    once = run(entry, profile, armature=text, pose=stance)
    twice = run(entry, profile, armature=text, pose=stance)

    assert np.array_equal(
        np.asarray(once.outputs[0].mesh.raw.vertices),
        np.asarray(twice.outputs[0].mesh.raw.vertices),
    )


def test_without_an_armature_it_says_what_is_missing(profile: Profile) -> None:
    """„Nichts zu tun" ist ein Ergebnis und gehört gesagt."""
    entry = SceneObject(id="obj_1", name="Arm", mesh=arm())

    result = run(entry, profile, armature="", pose="")

    assert {f.code for f in result.findings} == {"pose.no_armature"}


def test_a_hard_bend_reports_the_pinch(profile: Profile) -> None:
    """Lineares Blend-Skinning schnürt ein — das ist bekannt und gehört gesagt.

    Das Volumen ist die Zahl, an der es auffällt, bevor jemand das Ergebnis
    von Hand nachmisst.
    """
    entry = SceneObject(id="obj_1", name="Arm", mesh=arm())

    result = run(
        entry,
        profile,
        armature=armature_to_text(two_bones()),
        pose=pose_to_text([Pose(bone="lower", angles=(0.0, 150.0, 0.0))]),
    )

    assert "pose.pinched" in {finding.code for finding in result.findings}


def test_a_gentle_bend_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst warnt jede Stellung und keine Warnung zählt."""
    entry = SceneObject(id="obj_1", name="Arm", mesh=arm())

    result = run(
        entry,
        profile,
        armature=armature_to_text(two_bones()),
        pose=pose_to_text([Pose(bone="lower", angles=(0.0, 15.0, 0.0))]),
    )

    assert "pose.pinched" not in {finding.code for finding in result.findings}


# --- die runde Reise ------------------------------------------------------------


def test_the_armature_survives_the_round_trip() -> None:
    """Eine der fünf Eigenschaften aus Regel 2."""
    bones = two_bones()

    again = armature_from_text(armature_to_text(bones))

    assert [bone.name for bone in again] == ["upper", "lower"]
    assert again[1].parent == "upper"
    assert again[0].head == pytest.approx(bones[0].head)


def test_the_pose_survives_the_round_trip() -> None:
    poses = [Pose(bone="lower", angles=(1.5, -30.0, 0.0))]

    again = pose_from_text(pose_to_text(poses))

    assert len(again) == 1
    assert again[0].bone == "lower"
    assert again[0].angles == pytest.approx((1.5, -30.0, 0.0))


def test_no_bones_no_movement() -> None:
    """Der Helfer ohne Operation herum, an seinem entartetsten Fall."""
    body = arm()

    assert posed(body, [], []) is body
    assert posed(body, two_bones(), []) is body


# --- fremde Eingabe -------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "b1: 0,30,0",
        "{kaputt",
        '["kein", "objekt"]',
        '{"b1": [0, 30]}',
        '{"b1": "keine liste"}',
    ],
)
def test_an_unreadable_pose_is_a_validation_error(text: str) -> None:
    """Die naheliegendste Handeingabe ist kein JSON — sie bekommt einen Satz
    mit der erwarteten Form (Regel 17), keinen toten Auswertungs-Thread."""
    with pytest.raises(ValidationError) as caught:
        pose_from_text(text)

    assert caught.value.suggestions
    assert caught.value.field == "pose"


@pytest.mark.parametrize(
    "text",
    [
        "{kaputt",
        '{"n": "kein array"}',
        '[{"n": "b1"}]',
        '[{"n": "b1", "h": [0, 0], "t": [1, 0, 0]}]',
    ],
)
def test_an_unreadable_armature_is_a_validation_error(text: str) -> None:
    with pytest.raises(ValidationError) as caught:
        armature_from_text(text)

    assert caught.value.suggestions
    assert caught.value.field == "armature"
