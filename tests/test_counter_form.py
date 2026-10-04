"""Gegenformeinsatz: Taschen für ausgewählte Teile in einen Einsatz (RM-184, Audit §8).

Werkzeugbox der Werkstatt (Familie 10): ein Einsatz, in dem jedes Werkzeug seine
Tasche hat. Die Tasche ist der Umriss des Teils in Entnahmerichtung, um das halbe
Spiel aus dem Materialprofil je Seite geweitet, vom tiefsten Punkt des Teils bis
durch die Oberseite des Einsatzes — so lässt es sich gerade herausnehmen.

Die Sollwerte stehen gegen analytische Körper: ein Quader 30 × 15 × 10 als
Werkzeug gibt eine Tasche genau ``(30 + s) × (15 + s)``, ein Zylinder Ø 20 eine
um das Spiel weitere Rundung.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.boolean import shared_volume
from app.core.geom.mesh import MeshData
from app.core.geom.prepare import check_join_path
from app.core.registry import REGISTRY, VARIABLE
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject
from tests.helpers import exact_kernel


def _block() -> SceneObject:
    body = trimesh.creation.box(extents=(100.0, 60.0, 30.0))
    body.apply_translation((0.0, 0.0, 15.0))
    return SceneObject(id="obj_1", name="Einsatz", mesh=MeshData.of(body))


def _bar(at: tuple[float, float, float] = (25.0, 0.0, 27.0)) -> SceneObject:
    """Ein Werkzeug 30 × 15 × 10, zur Hälfte in den Einsatz gelegt (Boden bei z 22)."""
    body = trimesh.creation.box(extents=(30.0, 15.0, 10.0))
    body.apply_translation(at)
    return SceneObject(id="obj_2", name="Feile", mesh=MeshData.of(body))


def _round() -> SceneObject:
    body = trimesh.creation.cylinder(radius=10.0, height=40.0, sections=128)
    body.apply_translation((-20.0, 0.0, 35.0))
    return SceneObject(id="obj_3", name="Dose", mesh=MeshData.of(body))


def _run(entries: list[SceneObject], profile: Profile, **params: object) -> Any:
    spec = REGISTRY.get("cut_counter_form")
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


def test_the_insert_and_its_tools_stay_the_same_bodies() -> None:
    spec = REGISTRY.get("cut_counter_form")
    assert spec.consumes == VARIABLE and spec.minimum_inputs == 2
    assert spec.produces == VARIABLE


def test_a_bar_gets_a_pocket_exactly_its_size_plus_the_clearance(profile: Profile) -> None:
    """Rechteck: Fläche (30 + s)(15 + s), Tiefe von 22 − s/2 bis zur Oberseite 30."""
    block, bar = _block(), _bar()
    play = profile.material.clearance
    result = _run([block, bar], profile)
    insert, tool = result.outputs
    assert [entry.id for entry in result.outputs] == ["obj_1", "obj_2"]
    assert tool.mesh.volume == pytest.approx(bar.mesh.volume, rel=1e-12), "das Werkzeug bleibt"
    assert insert.mesh.is_watertight
    removed = block.mesh.volume - insert.mesh.volume
    expected = (30.0 + play) * (15.0 + play) * (30.0 - (22.0 - play / 2.0))
    assert removed == pytest.approx(expected, rel=1e-9)
    assert shared_volume(insert.mesh.raw, tool.mesh.raw) == pytest.approx(0.0, abs=1e-6)


def test_every_tool_lifts_straight_out_of_its_pocket(profile: Profile) -> None:
    """Der Prüfweg: Jedes Werkzeug gerade nach oben heraus, ohne anzustoßen."""
    block, bar, can = _block(), _bar(), _round()
    result = _run([block, bar, can], profile)
    insert = result.outputs[0].mesh
    for tool in result.outputs[1:]:
        found = check_join_path(tool.mesh, insert, (0.0, 0.0, -1.0), 40.0, steps=10)
        assert [finding.code for finding in found] == ["join.clear"], (tool.name, found)
    cylinder = math.pi * (10.0 + profile.material.clearance / 2.0) ** 2 * 15.0
    bar_pocket = (30.0 + profile.material.clearance) * (15.0 + profile.material.clearance)
    assert block.mesh.volume - insert.volume > cylinder * 0.99 + bar_pocket * 8.0


def test_a_finger_notch_opens_the_pocket_at_its_side(profile: Profile) -> None:
    block, bar = _block(), _bar()
    plain = _run([block, bar], profile).outputs[0].mesh
    notched = _run([block, bar], profile, grip=16.0).outputs[0].mesh
    assert notched.volume < plain.volume - 100.0, "die Mulde nimmt Material neben der Tasche"


def test_a_tool_beside_the_insert_is_named(profile: Profile) -> None:
    block = _block()
    far = _bar(at=(300.0, 0.0, 27.0))
    with pytest.raises(ValidationError) as problem:
        _run([block, far], profile)
    assert problem.value.constraint == "outside"
    assert "Feile" in str(problem.value.values.get("object", ""))


def test_a_pocket_through_the_floor_is_said(profile: Profile) -> None:
    block = _block()
    deep = _bar(at=(25.0, 0.0, 3.0))
    codes = {finding.code for finding in _run([block, deep], profile).findings}
    assert "counter_form.through_floor" in codes


def test_the_exact_insert_stays_exact_and_takes_the_same_pocket(profile: Profile) -> None:
    edit = exact_kernel()
    block = SceneObject(
        id="obj_1",
        name="Einsatz",
        mesh=edit.moved(edit.box(100.0, 60.0, 30.0), (0.0, 0.0, 0.0)),
        kind="brep",
    )
    result = _run([block, _bar()], profile)
    insert = result.outputs[0]
    assert insert.kind == "brep"
    play = profile.material.clearance
    expected = (30.0 + play) * (15.0 + play) * (30.0 - (22.0 - play / 2.0))
    assert block.mesh.volume - insert.mesh.volume == pytest.approx(expected, rel=1e-6)
