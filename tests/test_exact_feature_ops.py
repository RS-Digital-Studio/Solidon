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


# --- Ketten: Bohrung mit Senkung ------------------------------------------------------


def _countersunk_plate(profile: Profile) -> SceneObject:
    """Platte 60 × 40 × 10, Bohrung Ø 6 mit 90°-Senkung Ø 12 an der Oberseite.

    Das Profil kommt aus ``drill_outline`` wie beim exakten Bohren; der Kegel
    von Ø 12 auf Ø 6 misst 3 mm Höhe, das Volumen ist analytisch bekannt:
    π·3²·(10 − 3) für den Schaft, π·3·(6² + 6·3 + 3²)/3 für den Stumpf.
    """
    edit = _kernel()
    from app.core.brep.features import features_of
    from app.core.geom.prepare import drill_outline
    from app.core.sketch.planes import frame_of

    outline = drill_outline(
        diameter=2.0 * RADIUS,
        depth=12.0,
        profile=profile,
        compensate=False,
        widening_diameter=12.0,
        widening_depth=0.0,
        transition_angle=90.0,
    )
    body = edit.bore_profile(edit.box(*PLATE), outline, frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 10.0)))
    assert body.volume == pytest.approx(24000.0 - COUNTERSUNK_CAVITY, rel=1e-9)
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="brep", features=features_of(body)
    )
    kinds = sorted(feature.kind for feature in entry.features.values())
    assert kinds == ["cone"] + ["face"] * 6 + ["hole"], kinds
    return entry


COUNTERSUNK_CAVITY = BORE_AREA * 7.0 + math.pi * 3.0 * (36.0 + 18.0 + 9.0) / 3.0


def _chain_of(entry: SceneObject) -> tuple[Any, Any]:
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.relations import cavity_chain_state_at

    hole = _the_one(entry, "hole")
    state = cavity_chain_state_at(hole, entry.features, as_mesh_data(entry.mesh))
    assert state.chain is not None and len(state.chain) == 2, state
    return hole, _the_one(entry, "cone")


def test_moving_a_countersunk_bore_keeps_the_body_exact(profile: Profile) -> None:
    """Bohrung **und** Senkung wandern, beide Kennungen bleiben belegt, das Volumen auch."""
    load_operations()
    source = _countersunk_plate(profile)
    hole, cone = _chain_of(source)

    height = hole.params["centre"][2]
    assert height == pytest.approx(3.5, abs=1e-9), "der Schaft unter der Senkung ist 7 mm hoch"
    result = run("move_feature", source, profile, at_feature=hole.id, x=15.0, y=8.0, z=height)

    output = _exact_and_proven(result, source, hole.id)
    assert output.mesh.volume == pytest.approx(source.mesh.volume, rel=1e-9)
    moved_hole, moved_cone = _chain_of(output)
    assert moved_hole.id == hole.id and moved_cone.id == cone.id
    assert moved_hole.params["centre"] == pytest.approx((15.0, 8.0, height), abs=1e-9)
    assert moved_cone.params["centre"][:2] == pytest.approx((15.0, 8.0), abs=1e-9)
    assert moved_cone.params["diameter"] == pytest.approx(12.0, abs=1e-9)
    assert moved_hole.params["through"] is True
    assert _round_trip_volume(output.mesh) == pytest.approx(output.mesh.volume, rel=1e-9)


def test_moving_a_countersunk_bore_from_its_sink_takes_the_bore_along(profile: Profile) -> None:
    """Gewählt ist die Senkung: der Hohlraum wandert als Ganzes um denselben Weg."""
    load_operations()
    source = _countersunk_plate(profile)
    _hole, cone = _chain_of(source)
    sink_centre = cone.params["centre"]

    result = run(
        "move_feature",
        source,
        profile,
        at_feature=cone.id,
        x=sink_centre[0] + 10.0,
        y=sink_centre[1] - 5.0,
        z=sink_centre[2],
    )

    output = _exact_and_proven(result, source, cone.id)
    assert output.mesh.volume == pytest.approx(source.mesh.volume, rel=1e-9)
    moved_hole, _moved_cone = _chain_of(output)
    assert moved_hole.params["centre"] == pytest.approx((10.0, -5.0, 3.5), abs=1e-9)


def test_duplicating_a_countersunk_bore_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _countersunk_plate(profile)
    hole, cone = _chain_of(source)

    result = run("duplicate_feature", source, profile, at_feature=hole.id, x=20.0, y=0.0, z=3.5)

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert output.mesh.volume == pytest.approx(24000.0 - 2.0 * COUNTERSUNK_CAVITY, rel=1e-9)
    holes = {f.id: f for f in output.features.values() if f.kind == "hole"}
    cones = {f.id: f for f in output.features.values() if f.kind == "cone"}
    assert set(holes) == {hole.id, "hole_2"} and set(cones) == {cone.id, "cone_2"}
    assert holes["hole_2"].params["centre"] == pytest.approx((20.0, 0.0, 3.5), abs=1e-9)
    assert cones["cone_2"].params["centre"][:2] == pytest.approx((20.0, 0.0), abs=1e-9)
    assert {"hole_2", "cone_2"} <= set(output.reserved_feature_ids)
    assert not any(finding.converts_exact_body for finding in result.findings)


def test_removing_a_countersunk_bore_closes_the_whole_cavity_exactly(profile: Profile) -> None:
    load_operations()
    source = _countersunk_plate(profile)
    hole, cone = _chain_of(source)

    result = run("remove_feature", source, profile, at_feature=hole.id, sections="chain")

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert output.mesh.volume == pytest.approx(24000.0, rel=1e-9)
    assert solid.face_count == 6, "eine Platte ohne Loch hat sechs Flächen"
    assert not [f for f in output.features.values() if f.kind in ("hole", "cone")]
    assert {hole.id, cone.id} <= set(output.reserved_feature_ids)
    (gone,) = [f for f in result.findings if f.code == "remove_feature.gone"]
    assert set(gone.feature_ids) == {hole.id, cone.id}


def test_rotating_a_countersunk_bore_keeps_the_body_exact(profile: Profile) -> None:
    """30° um X an der Bohrung: gekippte Senkung über gekippter, durchgehender Bohrung.

    Der Sollwert des Volumens kommt aus dem Netzweg derselben Operation an der
    tessellierten Platte — eine unabhängige Rechnung mit Facettenfehler, daher
    die halbe Prozent Toleranz; die exakte Antwort liegt darin.
    """
    load_operations()
    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect

    source = _countersunk_plate(profile)
    hole, _cone = _chain_of(source)

    result = run("rotate_feature", source, profile, at_feature=hole.id, axis="x", angle=30.0)

    output = _exact_and_proven(result, source, hole.id)
    turned_hole, turned_cone = _chain_of(output)
    for turned in (turned_hole, turned_cone):
        axis = turned.params["axis"]
        assert (
            abs(axis[0]) < 1e-9
            and abs(abs(axis[1]) - 0.5) < 1e-9
            and abs(abs(axis[2]) - math.sqrt(0.75)) < 1e-9
        )
    assert turned_hole.params["through"] is True

    tessellated = MeshData.of(source.mesh.to_mesh(deflection=0.02).raw)
    meshed_source = SceneObject(
        id="obj_1", name="Platte", mesh=tessellated, kind="mesh", features=detect(tessellated)
    )
    meshed_hole = _the_one(meshed_source, "hole")
    meshed = run(
        "rotate_feature", meshed_source, profile, at_feature=meshed_hole.id, axis="x", angle=30.0
    )
    assert output.mesh.volume == pytest.approx(meshed.outputs[0].mesh.volume, rel=5e-3)
    # Ein gekippter Kegel geht als B-Spline-Fläche durch STEP; die neunte
    # Stelle bleibt dabei nicht, die siebte schon.
    assert _round_trip_volume(output.mesh) == pytest.approx(output.mesh.volume, rel=1e-7)
