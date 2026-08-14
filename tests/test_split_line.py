"""Trennen entlang einer gezeichneten Linie (Bauplan §25, §14).

Der Unterschied zu ``split_pinned`` ist eine einzige Sache: die Ebene hängt an
keiner Achse. Alles, was daran hängt, wird hier gemessen — die Ebene aus zwei
Punkten und einer Blickrichtung, die Stifte auf einer schiefen Fläche, und die
Zusage, dass eine schiefe Trennung dasselbe leistet wie eine gerade.

Gemessen wird gegen analytische Körper, nicht gegen ein selbst erzeugtes
Ergebnis: Bei einer Ebene durch die Mitte eines Quaders ist jedes Volumen
vorher bekannt.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom import pins
from app.core.geom.mesh import MeshData
from app.core.geom.prepare import split_at_plane
from app.core.geom.section import SectionPlane, plane_through
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject

#: Ein Körper, dessen Volumen jeder ausrechnen kann. Groß genug, dass zwei
#: Stifte samt Wand auf jede Schnittfläche passen.
BLOCK = (80.0, 60.0, 40.0)


def block() -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=BLOCK))


def run(op: str, entry: SceneObject, profile: Profile, **params: object):
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


# --- die Ebene aus der gezeichneten Linie -----------------------------------------


def test_a_line_across_the_screen_becomes_an_upright_plane() -> None:
    """Eine waagerecht gezeichnete Linie, von vorn betrachtet, trennt oben von
    unten."""
    plane = plane_through((-10.0, 0.0, 5.0), (10.0, 0.0, 5.0), view=(0.0, 1.0, 0.0))

    assert plane is not None
    assert abs(plane.normal[2]) == pytest.approx(1.0), "die Ebene liegt waagerecht"
    assert abs(plane.position) == pytest.approx(5.0), "und auf der Höhe der Linie"


def test_the_plane_holds_both_drawn_points() -> None:
    """Was gezeichnet wurde, liegt danach *in* der Ebene — sonst trennt sie
    woanders, als der Strich stand."""
    first = (3.0, -7.0, 11.0)
    second = (-5.0, 2.0, 4.0)

    plane = plane_through(first, second, view=(1.0, 1.0, -2.0))

    assert plane is not None
    for point in (first, second):
        distance = float(np.dot(plane.normal, point)) - plane.position
        assert distance == pytest.approx(0.0, abs=1e-9)


def test_a_line_along_the_view_spans_no_plane() -> None:
    """Regel 21: lieber nichts als eine geratene Ebene.

    Zwei Punkte genau hintereinander sehen im Bild aus wie einer. Daraus eine
    Ebene zu erfinden hieße, eine Richtung zu behaupten, die niemand gezeigt
    hat.
    """
    assert plane_through((0.0, 0.0, 0.0), (0.0, 4.0, 0.0), view=(0.0, 1.0, 0.0)) is None
    assert plane_through((1.0, 2.0, 3.0), (1.0, 2.0, 3.0), view=(0.0, 1.0, 0.0)) is None


# --- der Schnitt ------------------------------------------------------------------


def test_a_slanted_cut_halves_the_block(profile: Profile) -> None:
    """Eine Ebene diagonal durch die Mitte: beide Hälften geschlossen, beide
    halb so groß."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())
    whole = float(np.prod(BLOCK))

    result = run(
        "split_line",
        entry,
        profile,
        normal_x=1.0,
        normal_y=1.0,
        normal_z=0.0,
        position=0.0,
        pins=0,
    )

    assert [output.name for output in result.outputs] == ["Klotz A", "Klotz B"]
    assert all(output.mesh.is_watertight for output in result.outputs)
    volumes = [float(output.mesh.volume) for output in result.outputs]
    assert sum(volumes) == pytest.approx(whole, rel=1e-6)
    assert volumes[0] == pytest.approx(whole / 2.0, rel=1e-6)


def test_the_pins_stand_perpendicular_on_a_slanted_face(profile: Profile) -> None:
    """Der Grund, warum die Stifte eine Richtung führen statt eines
    Achsenbuchstabens.

    Ein Stift, der entlang der nächstgelegenen Achse aufgestellt wird, steht
    auf einer 45-Grad-Fläche schief in ihr — er lässt sich nicht fügen, ohne
    die Bohrung aufzureiben.
    """
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())
    expected = np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0)

    result = run(
        "split_line",
        entry,
        profile,
        normal_x=1.0,
        normal_y=1.0,
        normal_z=0.0,
        position=0.0,
        pins=2,
    )

    axis = np.asarray(result.outputs[0].features["pin_1"].params["axis"], dtype=float)
    assert np.allclose(axis, expected), "die Stiftachse ist die Normale der Trennebene"
    assert all(output.mesh.is_watertight for output in result.outputs)
    assert "bore_1" in result.outputs[1].features


def test_the_pins_sit_in_the_cut_face(profile: Profile) -> None:
    """Auf der Ebene, nicht daneben: gemessen als Abstand zur Ebene."""
    plane = SectionPlane(normal=(1.0, 1.0, 0.0), position=0.0)

    plan = pins.plan_pins(block(), plane)

    assert plan.count == 2
    unit = np.asarray(plane.normal, dtype=float) / np.linalg.norm(plane.normal)
    for position in plan.positions:
        assert float(np.dot(unit, position)) == pytest.approx(0.0, abs=1e-6)


def test_a_slanted_seam_gains_and_loses_the_same_material(profile: Profile) -> None:
    """Stift und Bohrung sind dasselbe Loch, einmal voll und einmal leer —
    bis auf Spiel und Freistich."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())
    plane = SectionPlane(normal=(1.0, 1.0, 0.0), position=0.0)
    first, second, _findings = split_at_plane(block(), plane)

    result = run("split_line", entry, profile, normal_x=1.0, normal_y=1.0, position=0.0, pins=2)

    assert float(result.outputs[0].mesh.volume) > float(first.volume), "Stifte tragen auf"
    assert float(result.outputs[1].mesh.volume) < float(second.volume), "Bohrungen nehmen weg"


def test_the_same_plane_gives_the_same_result_as_the_axis_version(profile: Profile) -> None:
    """Ein senkrecht stehender Schnitt ist derselbe, gleich über welchen der
    beiden Wege er kommt.

    Der Test hält die zwei Operationen aneinander: Wenn ``split_line`` je
    anders rechnete als ``split_pinned``, gäbe es zwei Wahrheiten über
    denselben Schnitt.
    """
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())

    drawn = run("split_line", entry, profile, normal_z=1.0, position=5.0, pins=2)
    axial = run("split_pinned", entry, profile, axis="z", position=5.0, pins=2)

    for one, other in zip(drawn.outputs, axial.outputs, strict=True):
        assert float(one.mesh.volume) == pytest.approx(float(other.mesh.volume), rel=1e-9)


def test_the_same_cut_twice_is_the_same_body(profile: Profile) -> None:
    """§11.2: zweimal auswerten muss identisch sein."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())
    values = {"normal_x": 1.0, "normal_y": 0.4, "normal_z": 0.2, "position": 3.0, "pins": 2}

    first = run("split_line", entry, profile, **values)
    second = run("split_line", entry, profile, **values)

    assert [round(o.mesh.volume, 6) for o in first.outputs] == [
        round(o.mesh.volume, 6) for o in second.outputs
    ]


# --- was nicht geht, sagt es -------------------------------------------------------


def test_a_plane_beside_the_body_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())

    with pytest.raises(ValidationError) as problem:
        run("split_line", entry, profile, normal_z=1.0, position=9999.0, pins=0)

    assert problem.value.field == "position"
    assert problem.value.suggestions, "Regel 17: jede Ausnahme trägt einen Vorschlag"


def test_a_direction_of_zero_length_is_a_user_error(profile: Profile) -> None:
    """Drei Nullen sind keine Richtung — und die Meldung sagt das, statt an
    einer Division zu scheitern."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())

    with pytest.raises(ValidationError) as problem:
        run("split_line", entry, profile, normal_x=0.0, normal_y=0.0, normal_z=0.0)

    assert problem.value.field == "normal_z"
    assert problem.value.suggestions
