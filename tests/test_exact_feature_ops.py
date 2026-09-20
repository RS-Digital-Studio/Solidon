"""Merkmalsoperationen am exakten Körper bleiben exakt (P2.4).

Bis zum 20.09.2026 liefen Versetzen, Verdoppeln, Drehen und Entfernen einer
Bohrung an einem B-Rep-Körper über das Netz, und der Körper kam als Netz
zurück — Fase, Formschräge und STEP-Export waren danach fort, und der
Bericht sagte ``evaluate.exact_became_mesh``. Hier steht, was jetzt gilt:
Das Ergebnis ist ein exakter Körper mit analytisch bekanntem Volumen, seine
Merkmale kommen aus der nativen Topologie, die Kennung reist belegt mit, und
ein STEP-Umlauf verliert nichts.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.types import Profile, SceneObject
from tests.test_missing_ops import run

PLATE = (60.0, 40.0, 10.0)
RADIUS = 3.0
BORE_AREA = math.pi * RADIUS * RADIUS


def _kernel() -> Any:
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit

    return edit


def _bored_plate() -> SceneObject:
    """Platte 60 × 40 × 10 mit einer durchgehenden Bohrung Ø 6 in der Mitte."""
    edit = _kernel()
    from app.core.brep.features import features_of

    body = edit.cut_bore(
        edit.box(*PLATE),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=2.0 * RADIUS,
        depth=10.0,
    )
    assert body.volume == pytest.approx(24000.0 - BORE_AREA * 10.0, rel=1e-9)
    return SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="brep", features=features_of(body)
    )


def _slotted_plate() -> SceneObject:
    """Dieselbe Platte mit einem Langloch Ø 6 auf 20 mm längs x."""
    edit = _kernel()
    from app.core.brep.features import features_of

    body = edit.slot_bore(
        edit.box(*PLATE),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=2.0 * RADIUS,
        depth=10.0,
        length=20.0,
        angle_deg=0.0,
        overlap=0.0,
    )
    assert body.volume == pytest.approx(
        24000.0 - (BORE_AREA + 2.0 * RADIUS * 14.0) * 10.0, rel=1e-9
    )
    return SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="brep", features=features_of(body)
    )


def _the_one(entry: SceneObject, kind: str) -> Any:
    found = [feature for feature in entry.features.values() if feature.kind == kind]
    assert len(found) == 1, sorted((f.id, f.kind) for f in entry.features.values())
    return found[0]


def _exact_and_proven(result: Any, source: SceneObject, feature_id: str) -> SceneObject:
    """Exakt geblieben, geschlossen, ohne Umwandlungsbefund, mit belegtem Übergang."""
    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep"
    assert solid.is_closed
    assert not any(finding.converts_exact_body for finding in result.findings)
    continued = {
        (entry.source.feature_id, entry.target)
        for group in result.feature_continuations
        for entry in group
    }
    assert (feature_id, feature_id) in continued, continued
    assert output.mesh is not source.mesh, "ein neuer Körper, der Eingang bleibt unangetastet"
    return output


def _round_trip_volume(solid: Any) -> float:
    from app.core.brep import step

    return step.read(step.write(solid)).volume


def test_moving_a_bore_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _bored_plate()
    hole = _the_one(source, "hole")

    result = run("move_feature", source, profile, at_feature=hole.id, x=15.0, y=8.0, z=5.0)

    output = _exact_and_proven(result, source, hole.id)
    assert output.mesh.volume == pytest.approx(24000.0 - BORE_AREA * 10.0, rel=1e-9)
    moved = _the_one(output, "hole")
    assert moved.id == hole.id
    assert moved.params["centre"] == pytest.approx((15.0, 8.0, 5.0), abs=1e-9)
    assert moved.params["diameter"] == pytest.approx(2.0 * RADIUS, abs=1e-9)
    assert moved.params["through"] is True
    assert moved.measure_sources["diameter"] == "native"
    assert not [f for f in result.findings if f.severity != "info"], [
        f.code for f in result.findings
    ]
    assert _round_trip_volume(output.mesh) == pytest.approx(output.mesh.volume, rel=1e-9)


def test_duplicating_a_bore_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _bored_plate()
    hole = _the_one(source, "hole")

    result = run("duplicate_feature", source, profile, at_feature=hole.id, x=20.0, y=0.0, z=5.0)

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert output.mesh.volume == pytest.approx(24000.0 - 2.0 * BORE_AREA * 10.0, rel=1e-9)
    holes = {f.id: f for f in output.features.values() if f.kind == "hole"}
    assert set(holes) == {hole.id, "hole_2"}, sorted(holes)
    assert holes[hole.id].params["centre"] == pytest.approx((0.0, 0.0, 5.0), abs=1e-9)
    assert holes["hole_2"].params["centre"] == pytest.approx((20.0, 0.0, 5.0), abs=1e-9)
    assert "hole_2" in output.reserved_feature_ids
    assert not any(finding.converts_exact_body for finding in result.findings)


def test_rotating_a_bore_keeps_the_body_exact(profile: Profile) -> None:
    """90° um X: die Bohrung läuft danach längs y durch die ganze Platte."""
    load_operations()
    source = _bored_plate()
    hole = _the_one(source, "hole")

    result = run("rotate_feature", source, profile, at_feature=hole.id, axis="x", angle=90.0)

    output = _exact_and_proven(result, source, hole.id)
    assert output.mesh.volume == pytest.approx(24000.0 - BORE_AREA * 40.0, rel=1e-9)
    turned = _the_one(output, "hole")
    assert abs(turned.params["axis"][1]) == pytest.approx(1.0, abs=1e-9)
    assert turned.params["centre"] == pytest.approx((0.0, 0.0, 5.0), abs=1e-9)
    assert turned.params["through"] is True


def test_removing_a_bore_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _bored_plate()
    hole = _the_one(source, "hole")

    result = run("remove_feature", source, profile, at_feature=hole.id)

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert output.mesh.volume == pytest.approx(24000.0, rel=1e-9)
    assert not [f for f in output.features.values() if f.kind == "hole"]
    assert hole.id in output.reserved_feature_ids
    assert {f.code for f in result.findings} == {"remove_feature.gone"}
    assert solid.face_count == 6, "eine Platte ohne Loch hat sechs Flächen"


def test_moving_a_slot_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _slotted_plate()
    slot = _the_one(source, "slot")

    result = run("move_feature", source, profile, at_feature=slot.id, x=10.0, y=10.0, z=5.0)

    output = _exact_and_proven(result, source, slot.id)
    assert output.mesh.volume == pytest.approx(
        24000.0 - (BORE_AREA + 2.0 * RADIUS * 14.0) * 10.0, rel=1e-9
    )
    moved = _the_one(output, "slot")
    assert moved.params["centre"] == pytest.approx((10.0, 10.0, 5.0), abs=1e-9)
    assert moved.params["length"] == pytest.approx(20.0, abs=1e-9)
    assert abs(moved.params["direction"][0]) == pytest.approx(1.0, abs=1e-9)


def test_removing_a_slot_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _slotted_plate()
    slot = _the_one(source, "slot")

    result = run("remove_feature", source, profile, at_feature=slot.id)

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert output.mesh.volume == pytest.approx(24000.0, rel=1e-9)
    assert not [f for f in output.features.values() if f.kind == "slot"]
