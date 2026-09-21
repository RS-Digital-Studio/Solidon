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


def test_the_widening_of_a_through_bore_is_not_through_in_either_kernel(profile: Profile) -> None:
    """Die Aufweitung einer Durchgangsbohrung endet am Übergang — beide Kerne sagen es.

    Am exakten Körper fragte ``through`` nur die Achse, und über der Achse der
    Aufweitung Ø 9 liegt nichts: Sie hieß durchgehend, während das Netz die
    Ringe in der Mündung fragt (``THROUGH_RINGS``) und den Übergangskegel
    findet (Kreuzbefund Paket C, 22.09.2026). Mit dem Flag hätte
    ``prepare_ops._exact_cavity_cut`` an einer allein stehenden Aufweitung die
    ganze Zielhülle als Tiefe genommen. Dieselben Ringe an beiden Kernen: Bei
    Ø 5 in Ø 9 liegt der äußere Ring (0,6) auf dem Kegel; die Bohrung selbst
    bleibt durchgehend.
    """
    edit = _kernel()
    load_operations()
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare import drill_outline
    from app.core.perceive.features import detect
    from app.core.sketch.planes import frame_of

    outline = drill_outline(
        diameter=5.0,
        depth=12.0,
        profile=profile,
        compensate=False,
        widening_diameter=9.0,
        widening_depth=2.0,
        transition_angle=90.0,
    )
    body = edit.bore_profile(edit.box(*PLATE), outline, frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 10.0)))
    exact = {
        round(feature.params["diameter"], 6): feature.params["through"]
        for feature in features_of(body).values()
        if feature.kind == "hole"
    }
    assert exact == {5.0: True, 9.0: False}, exact
    # Der Netz-Zwilling: dieselbe Bohrung, am Netz gebohrt und am Netz gelesen.
    twin = run(
        "drill_hole",
        run("create_box", None, profile, width=PLATE[0], depth=PLATE[1], height=PLATE[2]).outputs[
            0
        ],
        profile,
        diameter=5.0,
        x=0.0,
        y=0.0,
        z=PLATE[2],
        axis="z",
        depth=0.0,
        widening_diameter=9.0,
        widening_depth=2.0,
        anchor="mouth",
        compensate=False,
    ).outputs[0]
    meshed = {
        round(feature.params["diameter"], 1): feature.params["through"]
        for feature in detect(as_mesh_data(twin.mesh)).values()
        if feature.kind == "hole"
    }
    assert meshed == exact, meshed


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


# --- Materialmerkmale: Zapfen, Kuppe, Kegelstumpf ------------------------------------

PIN_VOLUME = BORE_AREA * 8.0
DOME_VOLUME = 2.0 / 3.0 * math.pi * 4.0**3
TAPER_VOLUME = math.pi * 6.0 / 3.0 * (25.0 + 10.0 + 4.0)


def _material_plate(kind: str) -> SceneObject:
    """Die Platte mit genau einem Materialmerkmal auf der Oberseite.

    ``pin``: Zylinder Ø 6 × 8 mittig. ``sphere``: Halbkugel r = 4 bei x = 20.
    ``cone``: Kegelstumpf r 5 → 2 über 6 mm bei x = −20. Volumen analytisch.
    """
    edit = _kernel()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeSphere
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    plate = edit.box(*PLATE)
    if kind == "pin":
        part = edit.moved(edit.cylinder(2.0 * RADIUS, 8.0), (0.0, 0.0, 10.0))
        added = PIN_VOLUME
    elif kind == "sphere":
        part = Solid(BRepPrimAPI_MakeSphere(gp_Pnt(20.0, 0.0, 10.0), 4.0).Shape())
        added = DOME_VOLUME
    else:
        part = Solid(
            BRepPrimAPI_MakeCone(
                gp_Ax2(gp_Pnt(-20.0, 0.0, 10.0), gp_Dir(0.0, 0.0, 1.0)), 5.0, 2.0, 6.0
            ).Shape()
        )
        added = TAPER_VOLUME
    body = edit.boolean("union", [plate, part])
    assert body.volume == pytest.approx(24000.0 + added, rel=1e-9)
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="brep", features=features_of(body)
    )
    assert [f.kind for f in entry.features.values() if f.kind != "face"] == [kind]
    return entry


def test_moving_a_pin_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _material_plate("pin")
    pin = _the_one(source, "pin")
    assert pin.params["centre"] == pytest.approx((0.0, 0.0, 14.0), abs=1e-9)

    result = run("move_feature", source, profile, at_feature=pin.id, x=15.0, y=8.0, z=14.0)

    output = _exact_and_proven(result, source, pin.id)
    assert output.mesh.volume == pytest.approx(24000.0 + PIN_VOLUME, rel=1e-9)
    moved = _the_one(output, "pin")
    assert moved.params["centre"] == pytest.approx((15.0, 8.0, 14.0), abs=1e-9)
    assert moved.params["diameter"] == pytest.approx(2.0 * RADIUS, abs=1e-9)
    assert _round_trip_volume(output.mesh) == pytest.approx(output.mesh.volume, rel=1e-9)


def test_duplicating_a_pin_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _material_plate("pin")
    pin = _the_one(source, "pin")

    result = run("duplicate_feature", source, profile, at_feature=pin.id, x=20.0, y=0.0, z=14.0)

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert output.mesh.volume == pytest.approx(24000.0 + 2.0 * PIN_VOLUME, rel=1e-9)
    pins = {f.id: f for f in output.features.values() if f.kind == "pin"}
    assert set(pins) == {pin.id, "pin_2"}, sorted(pins)
    assert pins["pin_2"].params["centre"] == pytest.approx((20.0, 0.0, 14.0), abs=1e-9)
    assert not any(finding.converts_exact_body for finding in result.findings)


def test_removing_a_pin_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _material_plate("pin")
    pin = _the_one(source, "pin")

    result = run("remove_feature", source, profile, at_feature=pin.id)

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert output.mesh.volume == pytest.approx(24000.0, rel=1e-9)
    assert solid.face_count == 6, "eine Platte ohne Zapfen hat sechs Flächen"
    assert not [f for f in output.features.values() if f.kind == "pin"]


def test_rotating_a_pin_keeps_it_rooted_in_the_plate(profile: Profile) -> None:
    """30° um X: der gekippte Zapfen bleibt ein Stück mit der Platte, nichts schwebt.

    Um seine Mitte gekippt höbe die Zylinderbasis auf einer Seite von der
    Platte ab; der exakte Zweig reicht deshalb unter die Mitte so weit, wie
    die Neigung verlangt. Der Sollwert kommt aus dem Netzweg derselben
    Operation, mit der Facettentoleranz.
    """
    load_operations()
    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect

    source = _material_plate("pin")
    pin = _the_one(source, "pin")

    result = run("rotate_feature", source, profile, at_feature=pin.id, axis="x", angle=30.0)

    output = _exact_and_proven(result, source, pin.id)
    solid: Any = output.mesh
    assert solid.solid_count == 1, "der gekippte Zapfen bleibt ein Stück mit der Platte"
    turned = _the_one(output, "pin")
    axis = turned.params["axis"]
    assert abs(abs(axis[1]) - 0.5) < 1e-9 and abs(abs(axis[2]) - math.sqrt(0.75)) < 1e-9
    assert output.mesh.volume > 24000.0 + PIN_VOLUME * 0.9

    tessellated = MeshData.of(source.mesh.to_mesh(deflection=0.02).raw)
    meshed_source = SceneObject(
        id="obj_1", name="Platte", mesh=tessellated, kind="mesh", features=detect(tessellated)
    )
    meshed_pin = _the_one(meshed_source, "pin")
    meshed = run(
        "rotate_feature", meshed_source, profile, at_feature=meshed_pin.id, axis="x", angle=30.0
    )
    assert output.mesh.volume == pytest.approx(meshed.outputs[0].mesh.volume, rel=1e-2)


def test_moving_a_dome_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _material_plate("sphere")
    dome = _the_one(source, "sphere")

    result = run("move_feature", source, profile, at_feature=dome.id, x=0.0, y=5.0, z=10.0)

    output = _exact_and_proven(result, source, dome.id)
    assert output.mesh.volume == pytest.approx(24000.0 + DOME_VOLUME, rel=1e-9)
    moved = _the_one(output, "sphere")
    assert moved.params["centre"] == pytest.approx((0.0, 5.0, 10.0), abs=1e-9)
    assert moved.params["diameter"] == pytest.approx(8.0, abs=1e-9)


def test_removing_a_taper_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _material_plate("cone")
    taper = _the_one(source, "cone")
    assert taper.params["recess"] is False

    result = run("remove_feature", source, profile, at_feature=taper.id)

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert output.mesh.volume == pytest.approx(24000.0, rel=1e-9)
    assert solid.face_count == 6
    assert not [f for f in output.features.values() if f.kind == "cone"]


def test_duplicating_a_taper_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _material_plate("cone")
    taper = _the_one(source, "cone")
    centre = taper.params["centre"]

    result = run(
        "duplicate_feature",
        source,
        profile,
        at_feature=taper.id,
        x=centre[0] + 30.0,
        y=centre[1],
        z=centre[2],
    )

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert output.mesh.volume == pytest.approx(24000.0 + 2.0 * TAPER_VOLUME, rel=1e-9)
    cones = {f.id: f for f in output.features.values() if f.kind == "cone"}
    assert set(cones) == {taper.id, "cone_2"}, sorted(cones)


# --- Nur das gewählte Merkmal einer Kette; die Senkung allein ------------------------

SINK_VOLUME = COUNTERSUNK_CAVITY - BORE_AREA * 7.0


def test_removing_only_the_countersink_keeps_the_bore_exact(profile: Profile) -> None:
    """Nur die Senkung geht; die Bohrung bleibt und geht bis zur Oberseite durch."""
    load_operations()
    source = _countersunk_plate(profile)
    hole, cone = _chain_of(source)

    result = run("remove_feature", source, profile, at_feature=cone.id, sections="single")

    output = _exact_and_proven(result, source, hole.id)
    solid: Any = output.mesh
    assert output.mesh.volume == pytest.approx(24000.0 - BORE_AREA * 10.0, rel=1e-9)
    assert solid.face_count == 7, "sechs Flächen und der Mantel einer durchgehenden Bohrung"
    kept = _the_one(output, "hole")
    assert kept.id == hole.id
    assert kept.params["centre"] == pytest.approx((0.0, 0.0, 5.0), abs=1e-9)
    assert kept.params["depth"] == pytest.approx(10.0, abs=1e-9)
    assert kept.params["through"] is True
    assert not [f for f in output.features.values() if f.kind == "cone"]
    assert cone.id in output.reserved_feature_ids
    (gone,) = [f for f in result.findings if f.code == "remove_feature.gone"]
    assert gone.feature_ids == (cone.id,)
    assert _round_trip_volume(output.mesh) == pytest.approx(output.mesh.volume, rel=1e-9)


def test_removing_only_the_bore_leaves_the_countersink_exact(profile: Profile) -> None:
    """Nur die Bohrung geht: die Senkung bleibt als Kegelstumpf mit ebenem Boden.

    Und danach steht sie allein — und geht denselben exakten Weg wie ein Zapfen:
    aus ihren Flächen gefüllt, sechs Flächen bleiben.
    """
    load_operations()
    source = _countersunk_plate(profile)
    hole, cone = _chain_of(source)

    result = run("remove_feature", source, profile, at_feature=hole.id, sections="single")

    output = _exact_and_proven(result, source, cone.id)
    solid: Any = output.mesh
    assert output.mesh.volume == pytest.approx(24000.0 - SINK_VOLUME, rel=1e-9)
    assert solid.face_count == 8, "sechs Flächen, der Kegelmantel und sein ebener Boden"
    kept = _the_one(output, "cone")
    assert kept.id == cone.id and kept.params["recess"] is True
    assert kept.params["diameter"] == pytest.approx(12.0, abs=1e-9)
    assert not [f for f in output.features.values() if f.kind == "hole"]
    assert hole.id in output.reserved_feature_ids

    gone = run("remove_feature", output, profile, at_feature=cone.id)
    plate = gone.outputs[0]
    full: Any = plate.mesh
    assert plate.kind == "brep" and full.is_closed
    assert full.volume == pytest.approx(24000.0, rel=1e-9)
    assert full.face_count == 6
    assert not any(finding.converts_exact_body for finding in gone.findings)
    assert not [f for f in plate.features.values() if f.kind in ("hole", "cone")]


def test_a_standalone_countersink_moves_and_copies_exactly(profile: Profile) -> None:
    """Die Bohrung ist gefüllt; ihre Senkung wird aus ihren Flächen versetzt und verdoppelt."""
    load_operations()
    source = _countersunk_plate(profile)
    hole, _cone = _chain_of(source)
    alone = run("remove_feature", source, profile, at_feature=hole.id, sections="single").outputs[0]
    sink = _the_one(alone, "cone")
    centre = sink.params["centre"]
    assert centre == pytest.approx((0.0, 0.0, 10.0), abs=1e-9), "die Senkung sitzt an der Mündung"

    moved = run(
        "move_feature",
        alone,
        profile,
        at_feature=sink.id,
        x=centre[0] + 12.0,
        y=centre[1] - 6.0,
        z=centre[2],
    )
    output = _exact_and_proven(moved, alone, sink.id)
    shifted: Any = output.mesh
    assert shifted.volume == pytest.approx(24000.0 - SINK_VOLUME, rel=1e-9)
    assert shifted.face_count == 8
    assert _the_one(output, "cone").params["centre"] == pytest.approx((12.0, -6.0, 10.0), abs=1e-9)
    assert _round_trip_volume(shifted) == pytest.approx(shifted.volume, rel=1e-9)

    copied = run(
        "duplicate_feature",
        alone,
        profile,
        at_feature=sink.id,
        x=centre[0] - 15.0,
        y=centre[1],
        z=centre[2],
    )
    twice = copied.outputs[0]
    doubled: Any = twice.mesh
    assert twice.kind == "brep" and doubled.is_closed
    assert doubled.volume == pytest.approx(24000.0 - 2.0 * SINK_VOLUME, rel=1e-9)
    cones = {f.id: f for f in twice.features.values() if f.kind == "cone"}
    assert set(cones) == {sink.id, "cone_2"}, sorted(cones)
    assert cones["cone_2"].params["centre"] == pytest.approx((-15.0, 0.0, 10.0), abs=1e-9)
    assert not any(finding.converts_exact_body for finding in copied.findings)


# --- Kegel kippen: Kegelstumpf und allein stehende Senkung ---------------------------


def _cone_past(radius: float, half_angle: float, tilt: float) -> float:
    """Die Weiterführung über das weite Ende hinaus — die Formel der Operation nachgerechnet.

    Gekippt um ``tilt`` steigt der tiefe Rand eines Kegels je Millimeter
    Weiterführung nur um ``cos(tilt) − tan(half) · sin(tilt)``; der Rand des
    weiten Endes liegt ``radius · sin(tilt)`` zu hoch. Der Quotient ist der Weg.
    """
    climb = math.cos(math.radians(tilt)) - math.tan(math.radians(half_angle)) * math.sin(
        math.radians(tilt)
    )
    return radius * math.sin(math.radians(tilt)) / climb


def _cone_solid(
    base: tuple[float, float, float],
    direction: tuple[float, float, float],
    base_radius: float,
    top_radius: float,
    height: float,
) -> Any:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.kernel import Solid

    frame = gp_Ax2(gp_Pnt(*base), gp_Dir(*direction))
    return Solid(BRepPrimAPI_MakeCone(frame, base_radius, top_radius, height).Shape())


def test_rotating_a_taper_keeps_it_rooted_in_the_plate(profile: Profile) -> None:
    """30° um X: der Kegelstumpf bleibt ein Stück mit der Platte, nichts schwebt, nichts fehlt.

    Der Sollwert ist unabhängig gebaut: derselbe Kegel aus den Maßen des
    Prüfstücks (r 5 → 2 über 6 mm), um seine Grundmitte gekippt und unter sie so
    weit weitergeführt, wie die Formel verlangt — und davon zählt, was über der
    Platte steht. Unter der Oberseite fehlt nichts, und die Erkennung nennt den
    Kegel an seinem weitesten Rand, dem Ende der Weiterführung.
    """
    load_operations()
    edit = _kernel()
    source = _material_plate("cone")
    taper = _the_one(source, "cone")
    assert taper.params["centre"] == pytest.approx((-20.0, 0.0, 10.0), abs=1e-9)

    result = run("rotate_feature", source, profile, at_feature=taper.id, axis="x", angle=30.0)

    output = _exact_and_proven(result, source, taper.id)
    solid: Any = output.mesh
    assert solid.solid_count == 1, "der gekippte Kegelstumpf bleibt ein Stück mit der Platte"
    slope = 0.5
    reach = _cone_past(5.0, math.degrees(math.atan(slope)), 30.0)
    sine, cosine = math.sin(math.radians(30.0)), math.cos(math.radians(30.0))
    direction = (0.0, -sine, cosine)
    base = (-20.0, sine * reach, 10.0 - cosine * reach)
    tool = _cone_solid(base, direction, 5.0 + reach * slope, 2.0, reach + 6.0)
    above = edit.boolean(
        "intersection", [tool, edit.moved(edit.box(200.0, 200.0, 100.0), (0.0, 0.0, 10.0))]
    )
    assert solid.volume == pytest.approx(24000.0 + above.volume, rel=1e-9)
    assert above.volume > TAPER_VOLUME, "der Keil unter der gekippten Grundfläche ist gefüllt"
    below = edit.boolean("intersection", [solid, edit.box(200.0, 200.0, 10.0)])
    assert below.volume == pytest.approx(24000.0, rel=1e-9), "unter der Oberseite fehlt nichts"
    turned = _the_one(output, "cone")
    axis = turned.params["axis"]
    assert abs(abs(axis[1]) - sine) < 1e-9 and abs(abs(axis[2]) - cosine) < 1e-9
    assert turned.params["recess"] is False
    assert turned.params["diameter"] == pytest.approx(2.0 * (5.0 + reach * slope), abs=1e-9)
    assert turned.params["centre"] == pytest.approx(base, abs=1e-9)


def test_rotating_a_standalone_countersink_stays_open(profile: Profile) -> None:
    """30° um X: die Senkung ohne Bohrung darunter kippt, bleibt zur Oberseite offen, exakt.

    Um ihre Mündungsmitte gekippt behielte die Senkung eine Decke; das
    Werkzeug führt den Kegel deshalb ins Freie weiter, und was davon in der
    Platte liegt, ist genau das, was fehlt.
    """
    load_operations()
    edit = _kernel()
    source = _countersunk_plate(profile)
    hole, _cone = _chain_of(source)
    alone = run("remove_feature", source, profile, at_feature=hole.id, sections="single").outputs[0]
    sink = _the_one(alone, "cone")

    result = run("rotate_feature", alone, profile, at_feature=sink.id, axis="x", angle=30.0)

    output = _exact_and_proven(result, alone, sink.id)
    solid: Any = output.mesh
    assert solid.solid_count == 1
    reach = _cone_past(6.0, 45.0, 30.0)
    sine, cosine = math.sin(math.radians(30.0)), math.cos(math.radians(30.0))
    direction = (0.0, sine, -cosine)
    base = (0.0, -sine * reach, 10.0 + cosine * reach)
    tool = _cone_solid(base, direction, 6.0 + reach, 3.0, reach + 3.0)
    inside = edit.boolean("intersection", [tool, edit.box(200.0, 200.0, 10.0)])
    assert solid.volume == pytest.approx(24000.0 - inside.volume, rel=1e-9)
    assert inside.volume > SINK_VOLUME, "die gekippte Senkung nimmt mehr mit als die gerade"
    assert solid.face_count == 8, "sechs Flächen, der Kegelmantel und sein ebener Boden"
    turned = _the_one(output, "cone")
    assert turned.params["recess"] is True
    assert turned.params["diameter"] == pytest.approx(2.0 * (6.0 + reach), abs=1e-9)
    assert turned.params["centre"] == pytest.approx(base, abs=1e-9)
    assert _round_trip_volume(solid) == pytest.approx(solid.volume, rel=1e-7)


# --- Senken und Verschließen ---------------------------------------------------------------


def test_countersinking_an_exact_bore_keeps_the_body_exact(profile: Profile) -> None:
    """Senken an der Mündung einer exakten Bohrung: der Hohlraum des exakten Bohrens mit Senkung.

    Die Position liegt in der Bohrung, der Bezug ist die Mündung — dort landet
    der Kegel, oben, weil die Hüllquader-Regel es sagt. Volumen und Merkmale
    sind die der Platte, die ``drill_outline`` mit derselben Senkung bohrt.
    """
    load_operations()
    source = _bored_plate()
    hole = _the_one(source, "hole")

    result = run(
        "countersink_hole",
        source,
        profile,
        diameter=12.0,
        angle=90.0,
        x=0.0,
        y=0.0,
        z=5.0,
        axis="z",
        anchor="mouth",
    )

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert not any(finding.converts_exact_body for finding in result.findings)
    assert solid.volume == pytest.approx(24000.0 - COUNTERSUNK_CAVITY, rel=1e-9)
    assert solid.face_count == 8
    kinds = sorted(f.kind for f in output.features.values() if f.kind != "face")
    assert kinds == ["cone", "hole"], kinds
    sink = _the_one(output, "cone")
    assert sink.params["diameter"] == pytest.approx(12.0, abs=1e-9)
    assert sink.params["angle"] == pytest.approx(90.0, abs=1e-9)
    assert sink.params["recess"] is True
    assert sink.params["centre"] == pytest.approx((0.0, 0.0, 10.0), abs=1e-9)
    kept = _the_one(output, "hole")
    assert kept.id == hole.id, "die Bohrung bleibt dieselbe, nur kürzer"
    assert kept.params["depth"] == pytest.approx(7.0, abs=1e-9)
    assert kept.params["centre"] == pytest.approx((0.0, 0.0, 3.5), abs=1e-9)
    assert _round_trip_volume(solid) == pytest.approx(solid.volume, rel=1e-9)


def test_countersinking_into_solid_material_says_so_and_stays_exact(profile: Profile) -> None:
    """Mitten im Material gibt es keine Mündung: der Befund kommt, der Körper bleibt exakt.

    Der Kegel Ø 12/90° ist 6 mm hoch; von z = 8 aus reicht er bis z = 2 und
    bleibt ganz in der Platte — ein Einschluss, den der Befund benennt. Sein
    Volumen ist das des um den Überstand weitergeführten Kegels.
    """
    load_operations()
    source = _bored_plate()

    result = run(
        "countersink_hole",
        source,
        profile,
        diameter=12.0,
        angle=90.0,
        x=20.0,
        y=10.0,
        z=8.0,
        axis="z",
        anchor="centre",
    )

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert [finding.code for finding in result.findings] == ["bore.sink_buried"]
    from app.core.geom.prepare import FEATURE_OVERLAP

    grown = 6.0 + FEATURE_OVERLAP
    assert solid.volume == pytest.approx(
        24000.0 - BORE_AREA * 10.0 - math.pi * grown * grown * grown / 3.0, rel=1e-9
    )
    assert [f.kind for f in output.features.values() if f.kind == "void"], (
        "der vergrabene Kegel ist ein Einschluss"
    )


def test_plugging_an_exact_bore_by_its_feature_keeps_the_body_exact(profile: Profile) -> None:
    load_operations()
    source = _bored_plate()
    hole = _the_one(source, "hole")

    result = run("plug_hole", source, profile, at_feature=hole.id)

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed
    assert not any(finding.converts_exact_body for finding in result.findings)
    assert solid.volume == pytest.approx(24000.0, rel=1e-9)
    assert solid.face_count == 6
    assert not [f for f in output.features.values() if f.kind == "hole"]
    assert hole.id in output.reserved_feature_ids


def test_plugging_an_exact_bore_by_numbers_keeps_the_body_exact(profile: Profile) -> None:
    """Ohne Merkmal: der Stopfen aus Zahlen, an der Hülle beschnitten — durch und zur Hälfte."""
    load_operations()
    source = _bored_plate()

    through = run(
        "plug_hole",
        source,
        profile,
        at_feature="",
        diameter=6.0,
        x=0.0,
        y=0.0,
        z=10.0,
        axis="z",
        depth=0.0,
        compensate=False,
    )
    whole = through.outputs[0]
    full: Any = whole.mesh
    assert whole.kind == "brep" and full.is_closed
    assert not any(finding.converts_exact_body for finding in through.findings)
    assert full.volume == pytest.approx(24000.0, rel=1e-9)
    assert full.face_count == 6, "nichts wächst aus der Platte heraus"

    partly = run(
        "plug_hole",
        source,
        profile,
        at_feature="",
        diameter=6.0,
        x=0.0,
        y=0.0,
        z=10.0,
        axis="z",
        depth=4.0,
        anchor="mouth",
        compensate=False,
    )
    half = partly.outputs[0]
    part: Any = half.mesh
    assert half.kind == "brep" and part.is_closed
    assert part.volume == pytest.approx(24000.0 - BORE_AREA * 6.0, rel=1e-9)
    assert part.face_count == 8, "die Bohrung ist jetzt ein Sackloch von unten: Mantel und Boden"
    left = _the_one(half, "hole")
    assert left.params["through"] is False
    assert left.params["depth"] == pytest.approx(6.0, abs=1e-9)
    assert left.params["centre"] == pytest.approx((0.0, 0.0, 3.0), abs=1e-9)


# --- Der Einschluss: Luft ohne Rand ------------------------------------------------------


def _pocketed_block(*, island: bool) -> SceneObject:
    """Block 40 × 30 × 20 mit Ø 6 × 8 Luft in der Mitte, auf Wunsch mit Kugel R 1 darin.

    Derselbe Aufbau wie in ``test_brep_voids.py``: Die Kugel ist eine
    Materialinsel im Einschluss — ein zweiter Körper im selben Verbund.
    """
    from OCP.BRep import BRep_Builder
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCylinder,
        BRepPrimAPI_MakeSphere,
    )
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.TopoDS import TopoDS_Compound

    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid, boolean_builder

    _kernel()
    stock = BRepPrimAPI_MakeBox(gp_Pnt(-20, -15, 0), 40, 30, 20).Shape()
    tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, 6), gp_Dir(0, 0, 1)), 3, 8)
    builder = boolean_builder("difference", stock, tool.Shape())
    builder.Build()
    hollow = builder.Shape()
    if island:
        compound = TopoDS_Compound()
        maker = BRep_Builder()
        maker.MakeCompound(compound)
        maker.Add(compound, hollow)
        maker.Add(compound, BRepPrimAPI_MakeSphere(gp_Pnt(0, 0, 10), 1).Shape())
        hollow = compound
    body = Solid(hollow)
    return SceneObject(id="obj_1", name="Block", mesh=body, kind="brep", features=features_of(body))


AIR_VOLUME = math.pi * 9.0 * 8.0
ISLAND_VOLUME = 4.0 / 3.0 * math.pi


@pytest.mark.parametrize("island", [False, True], ids=["leer", "mit_insel"])
def test_filling_a_void_keeps_the_body_exact(profile: Profile, island: bool) -> None:
    """Entfernen füllt den Einschluss aus seinen Schalen — die Insel geht im Material auf."""
    load_operations()
    source = _pocketed_block(island=island)
    air = _the_one(source, "void")
    expected_air = AIR_VOLUME - (ISLAND_VOLUME if island else 0.0)
    assert air.params["volume"] == pytest.approx(expected_air, rel=1e-9)

    result = run("remove_feature", source, profile, at_feature=air.id)

    output = result.outputs[0]
    solid: Any = output.mesh
    assert output.kind == "brep" and solid.is_closed and solid.solid_count == 1
    assert not any(finding.converts_exact_body for finding in result.findings)
    assert solid.volume == pytest.approx(24000.0, rel=1e-9)
    assert solid.face_count == 6, "ein voller Block hat sechs Flächen"
    assert not [f for f in output.features.values() if f.kind == "void"]
    assert air.id in output.reserved_feature_ids


@pytest.mark.parametrize("island", [False, True], ids=["leer", "mit_insel"])
def test_moving_a_void_keeps_the_body_exact_and_takes_the_island_along(
    profile: Profile, island: bool
) -> None:
    """Versetzen füllt die alte Luft und schneidet sie neu — um die Insel herum."""
    load_operations()
    source = _pocketed_block(island=island)
    air = _the_one(source, "void")
    assert air.params["centre"] == pytest.approx((0.0, 0.0, 10.0), abs=1e-9)

    result = run("move_feature", source, profile, at_feature=air.id, x=8.0, y=0.0, z=10.0)

    output = _exact_and_proven(result, source, air.id)
    solid: Any = output.mesh
    assert solid.volume == pytest.approx(source.mesh.volume, rel=1e-9)
    assert solid.solid_count == (2 if island else 1), "die Insel reist mit und bleibt ein Körper"
    moved = _the_one(output, "void")
    assert moved.id == air.id
    assert moved.params["centre"] == pytest.approx((8.0, 0.0, 10.0), abs=1e-9)
    assert moved.params["volume"] == pytest.approx(air.params["volume"], rel=1e-9)
    assert _round_trip_volume(solid) == pytest.approx(solid.volume, rel=1e-9)
