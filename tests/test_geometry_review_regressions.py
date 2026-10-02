"""Kleine Gegenproben für die geometrischen Kundenwege des Gesamtreviews."""

import importlib
import math
from dataclasses import replace

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.geom.transform import decompose_transform, rotation, scaling, translation
from app.core.sketch import solver
from app.core.sketch.edit import extend
from app.core.sketch.planes import feature_plane
from app.core.sketch.serialize import sketch_to_text
from app.core.sketch.shapes import rectangle
from app.core.types import Sketch, SketchConstraint, SketchElement
from tests.helpers import exact_kernel


@pytest.mark.parametrize(
    "operation,params",
    [
        ("translate_object", {"dx": 3.0}),
        ("rotate_object", {"angle": 30.0}),
        ("scale_object", {"fx": 2.0, "fy": 3.0, "fz": 1.0}),
        ("fit_to_size", {"largest": 60.0}),
        ("mirror_object", {"axis": "x"}),
        ("place_on_bed", {}),
        ("pattern", {"count": 2}),
        ("create_brep_box", {}),
        ("create_brep_cylinder", {}),
        # Der kleinste Bolzen, den das Schema zulässt: drei Umläufe reichen, um
        # den Abbruch bis in die Transformation zu tragen.
        ("thread_exact", {"diameter": 10.0, "pitch": 1.0, "length": 3.0}),
    ],
)
def test_exact_transform_operations_forward_cancellation_to_native_work(
    profile, monkeypatch, operation, params
):
    """Abbrechen erreicht die native Maßrechnung, nicht erst den folgenden Operationsschritt."""
    from app.core.brep import edit
    from app.core.errors import OperationCancelled
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import CancelSignal
    from app.core.types import OpContext, Scene, SceneObject

    exact_kernel()
    load_operations()
    source = SceneObject(
        id="obj_1", name="Grundkörper", mesh=edit.box(20.0, 16.0, 10.0), kind="brep"
    )
    token = CancelSignal()
    reached = []

    def native(_solid, _matrix, *, cancelled=None):
        assert cancelled is token
        reached.append(cancelled)
        token.cancel()
        cancelled.raise_if_cancelled()

    monkeypatch.setattr(edit, "transformed_with_faces", native)
    spec = REGISTRY.get(operation)
    context = OpContext(
        scene=Scene(objects={source.id: source}),
        inputs=[] if spec.consumes == 0 else [source],
        params=spec.params(**params),
        profile=profile,
        quality="fine",
        seed=None,
        progress=lambda _fraction, _text: None,
        ask=lambda _question, choices: choices[0],
        cancelled=token,
    )
    with pytest.raises(OperationCancelled):
        spec.fn(context)
    assert reached == [token]
    assert source.mesh.bounds.size == pytest.approx((20.0, 16.0, 10.0))


@pytest.fixture
def review_run(profile):
    """Ruft die echte Operation mit dem isolierten Druckprofil auf."""
    from tests.test_brep import run

    def execute(op, entry=None, **params):
        return run(op, entry, profile, **params)

    return execute


@pytest.fixture
def bore_review_body():
    """Dieselbe analytische Platte als exakter Körper oder als importierbares Netz."""
    exact_kernel()
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    def make(solid, kind):
        mesh = solid if kind == "brep" else as_mesh_data(solid)
        features = features_of(solid) if kind == "brep" else detect(mesh)
        return SceneObject(id="obj_1", name="Prüfplatte", mesh=mesh, kind=kind, features=features)

    return make


@pytest.mark.parametrize("kind", ["brep", "mesh"])
@pytest.mark.parametrize("round_cut", [True, False])
@pytest.mark.parametrize("depth", [4.0, 10.0])
@pytest.mark.parametrize("turned", [False, True])
def test_open_round_cut_and_open_slot_are_detected_slots(
    kind, round_cut, depth, turned, bore_review_body
):
    """Beide Randöffnungen bleiben ohne gespeicherte Herkunft bearbeitbare Langlöcher."""
    from app.core.brep import edit

    body = edit.box(40.0, 30.0, 10.0)
    if round_cut:
        body = edit.cut_bore(
            body,
            position=(19.0, 0.0, 10.0 - depth / 2.0),
            direction=(0.0, 0.0, 1.0),
            diameter=6.0,
            depth=depth,
        )
    else:
        body = edit.slot_bore(
            body,
            position=(17.0, 0.0, 10.0 - depth / 2.0),
            direction=(0.0, 0.0, 1.0),
            diameter=6.0,
            depth=depth,
            length=18.0,
            angle_deg=0.0,
            overlap=0.0,
        )
    if turned:
        body = edit.transformed(body, rotation("x", 37.0) @ rotation("z", 23.0))
    entry = bore_review_body(body, kind)
    slots = [feature for feature in entry.features.values() if feature.kind == "slot"]
    assert len(slots) == 1
    assert slots[0].params["open"] is True
    assert slots[0].params["diameter"] == pytest.approx(6.0, abs=0.01)
    assert slots[0].params["depth"] == pytest.approx(depth, abs=0.01)
    assert slots[0].params["through"] == (depth == 10.0)
    assert slots[0].face_indices
    assert slots[0].recognised


@pytest.mark.parametrize("diameter", [16.0, 50.0])
def test_filling_foreign_bore_removes_its_entire_wall(diameter, review_run):
    """Ein anders tesselliertes Loch lässt nach dem Füllen keine Wandreste zurück."""
    from app.core.geom.boolean import boolean
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    plate = MeshData.of(trimesh.creation.box(extents=(100.0, 100.0, 10.0)))
    cutter = trimesh.creation.cylinder(radius=diameter / 2.0, height=12.0, sections=96)
    cutter.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 96.0, (0, 0, 1)))
    body = boolean("difference", [plate, MeshData.of(cutter)]).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features=detect(body))
    hole = next(f for f in entry.features.values() if f.kind == "hole")
    out = review_run("remove_feature", entry, at_feature=hole.id).outputs[0]
    assert out.mesh.volume == pytest.approx(100000.0, abs=0.01)
    assert not any(f.kind in {"hole", "pin", "fillet", "slot"} for f in detect(out.mesh).values())


@pytest.mark.parametrize("diameter,depth", [(8.0, 6.0), (12.0, 6.0), (12.0, 8.0)])
def test_blind_countersunk_bore_has_one_unambiguous_chain(profile, review_run, diameter, depth):
    """Der Sacklochboden ist keine zweite Verbindung zwischen Bohrung und Senkung."""
    from app.core.geom.prepare import countersink, drill
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chain_state_at
    from app.core.types import SceneObject

    plate = MeshData.of(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    body = drill(
        plate,
        position=(0.0, 0.0, 5.0),
        axis="z",
        diameter=6.0,
        depth=depth,
        profile=profile,
        compensate=False,
    ).mesh
    body = countersink(
        body, position=(0.0, 0.0, 5.0), axis="z", diameter=diameter, profile=profile
    ).mesh
    features = detect(body)
    cone = next(f for f in features.values() if f.kind == "cone")
    chain = cavity_chain_state_at(cone, features, body).chain
    assert chain is not None
    assert {f.kind for f in chain} == {"hole", "cone"}
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features=features)
    out = review_run("remove_feature", entry, at_feature=cone.id, sections="single").outputs[0]
    bores = [f for f in detect(out.mesh).values() if f.kind == "hole"]
    assert len(bores) == 1
    assert not bores[0].params["through"]
    assert bores[0].params["depth"] == pytest.approx(depth, abs=0.01)


@pytest.mark.parametrize("kind", ["brep", "mesh"])
@pytest.mark.parametrize("round_cut", [True, False])
def test_open_slot_can_be_pulled_and_moved_without_an_outside_plug(
    kind,
    round_cut,
    bore_review_body,
    review_run,
):
    """Nachziehen und Versetzen verwenden für beide Randöffnungen denselben Weg."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare_ops import slot_angle_of
    from app.core.perceive.features import detect

    body = edit.box(60.0, 40.0, 10.0)
    args = {
        "position": (29.0, 0.0, 5.0),
        "direction": (0.0, 0.0, 1.0),
        "diameter": 6.0,
        "depth": 10.0,
    }
    body = (
        edit.cut_bore(body, **args)
        if round_cut
        else edit.slot_bore(body, **args, length=18.0, angle_deg=0.0, overlap=0.0)
    )
    entry = bore_review_body(body, kind)
    slot = next(f for f in entry.features.values() if f.kind == "slot")
    result = review_run(
        "slot_hole",
        entry,
        at_feature=slot.id,
        slot_length=slot.params["length"] + 4.0,
        slot_angle=slot_angle_of(slot, slot.params["axis"]),
    )
    assert not any(f.code.endswith("feature_lost") for f in result.findings)
    entry = result.outputs[0]
    slot = next(f for f in entry.features.values() if f.kind == "slot")
    result = review_run(
        "slot_hole",
        entry,
        at_feature=slot.id,
        slot_length=slot.params["length"] + 4.0,
        slot_angle=slot_angle_of(slot, slot.params["axis"]),
        x=-10.0,
        z=5.0,
    )
    out = result.outputs[0]
    assert out.mesh.bounds.size == pytest.approx((60.0, 40.0, 10.0), abs=0.01)
    detected = features_of(out.mesh) if kind == "brep" else detect(as_mesh_data(out.mesh))
    assert len([f for f in detected.values() if f.kind == "slot"]) == 1
    assert not any(f.params.get("open") for f in detected.values())
    assert not any(f.code.endswith("feature_lost") for f in result.findings)


@pytest.mark.parametrize("kind", ["brep", "mesh"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_open_bore_survives_project_round_trip_and_undo(kind, quality, profile, tmp_path):
    """Die Randöffnung bleibt nach Laden und Rücknahme ein echtes bearbeitbares Merkmal."""
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import load, new_project, save

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Platte und Bohrung",
        [
            OperationDraft(
                op="create_brep_box" if kind == "brep" else "create_box",
                params={"width": 40.0, "depth": 30.0, "height": 10.0},
            ),
            OperationDraft(
                op="drill_brep_hole" if kind == "brep" else "drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.0, "compensate": False, "x": 15.0, "z": 10.0},
            ),
        ],
    )
    result = evaluate(project.document, profile, quality=quality)
    assert result.complete
    bore = next(f for f in result.scene.objects["obj_1"].features.values() if f.kind == "hole")
    history.apply(
        "Zum Rand öffnen",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={
                    "at_feature": bore.id,
                    "diameter": 8.0,
                    "compensate": False,
                    "x": 19.0,
                    "z": 5.0,
                },
            )
        ],
    )
    reopened = load(save(project, tmp_path / "randloch.p3d"))
    result = evaluate(reopened.document, profile, quality=quality)
    assert result.complete
    slot = next(f for f in result.scene.objects["obj_1"].features.values() if f.kind == "slot")
    assert slot.recognised and slot.face_indices and slot.params["open"]
    history = History(reopened.document)
    history.undo()
    result = evaluate(reopened.document, profile, quality=quality)
    assert result.complete
    assert any(f.kind == "hole" for f in result.scene.objects["obj_1"].features.values())
    history.redo()
    history.apply(
        "Öffnung schließen",
        [
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 10.0}),
            OperationDraft(op="union_objects", inputs=("obj_1", "obj_2")),
        ],
    )
    result = evaluate(reopened.document, profile, quality=quality)
    assert result.complete
    assert not any(f.params.get("open") for f in result.scene.objects["obj_1"].features.values())


def test_exact_bore_on_curved_surface_uses_the_real_flank(bore_review_body, review_run):
    """Die vom Ansichtsnetz gelieferte Normale löst am exakten Zylinder keine Fehlwarnung aus."""
    from app.core.brep import edit
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene.placement import original_surface_hit

    solid = edit.cylinder(15.0, 40.0)
    mesh = as_mesh_data(solid)
    hit = original_surface_hit(mesh, (60.0, 0.0, 20.0), (-1.0, 0.0, 0.0))
    assert hit is not None
    index, point = hit
    normal = mesh.raw.face_normals[index]
    result = review_run(
        "drill_brep_hole",
        bore_review_body(solid, "brep"),
        diameter=3.0,
        compensate=False,
        x=point[0],
        y=point[1],
        z=point[2],
        nx=normal[0],
        ny=normal[1],
        nz=normal[2],
    )
    assert not any(f.code == "bore.over_the_edge" for f in result.findings)
    assert result.outputs[0].mesh.volume < solid.volume - 1.0


@pytest.mark.parametrize("kind", ["brep", "mesh"])
def test_moving_existing_slot_fills_its_whole_old_outline(kind, bore_review_body, review_run):
    """An der alten Stelle bleibt weder ein Loch noch ein herausragender Stopfen."""
    from app.core.brep import edit
    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import as_mesh_data

    solid = edit.slot_bore(
        edit.box(100.0, 80.0, 10.0),
        position=(-20.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=10.0,
        length=20.0,
        angle_deg=35.0,
        overlap=0.0,
    )
    entry = bore_review_body(solid, kind)
    feature = next(f for f in entry.features.values() if f.kind == "slot")
    result = review_run(
        "slot_hole",
        entry,
        at_feature=feature.id,
        slot_length=22.0,
        slot_angle=35.0,
        x=20.0,
        y=0.0,
        z=5.0,
    )
    out = result.outputs[0]
    window = edit.moved(edit.box(30.0, 30.0, 10.0), (-20.0, 0.0, 0.0))
    if kind == "brep":
        filled = edit.boolean("intersection", [out.mesh, window]).volume
    else:
        filled = boolean("intersection", [as_mesh_data(out.mesh), as_mesh_data(window)]).mesh.volume
    assert filled == pytest.approx(30.0 * 30.0 * 10.0, abs=0.01)
    assert out.mesh.bounds.size == pytest.approx((100.0, 80.0, 10.0), abs=0.01)


@pytest.mark.parametrize("kind", ["brep", "mesh"])
@pytest.mark.parametrize("operation", ["resize_hole", "slot_hole"])
@pytest.mark.parametrize("through", [True, False])
def test_moving_bore_to_thicker_material_keeps_depth_intent(
    kind,
    operation,
    through,
    bore_review_body,
    review_run,
):
    """Durchgang bleibt durchgehend; ein Sackloch behält seine Tiefe und Kennung."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect

    solid = edit.boolean(
        "union",
        [edit.box(100.0, 80.0, 10.0), edit.moved(edit.box(30.0, 80.0, 20.0), (30.0, 0.0, 0.0))],
    )
    depth = 10.0 if through else 6.0
    solid = edit.cut_bore(
        solid,
        position=(-20.0, 0.0, 10.0 - depth / 2.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=depth,
    )
    entry = bore_review_body(solid, kind)
    feature = next(f for f in entry.features.values() if f.kind == "hole")
    params = (
        {"diameter": 6.0, "compensate": False}
        if operation == "resize_hole"
        else {"slot_length": 20.0}
    )
    result = review_run(
        operation, entry, at_feature=feature.id, x=30.0, y=0.0, z=20.0 - depth / 2.0, **params
    )
    out = result.outputs[0]
    detected = features_of(out.mesh) if kind == "brep" else detect(as_mesh_data(out.mesh))
    wanted = "hole" if operation == "resize_hole" else "slot"
    bore = next(f for f in detected.values() if f.kind == wanted)
    assert bore.params["through"] is through
    assert bore.params["depth"] == pytest.approx(20.0 if through else 6.0, abs=0.01)
    assert not any(f.code.endswith("feature_lost") for f in result.findings)
    if operation == "resize_hole":
        assert feature.id in out.features
        assert out.features[feature.id].params["centre"] == pytest.approx(
            bore.params["centre"], abs=0.01
        )


@pytest.mark.parametrize("kind", ["brep", "mesh"])
def test_slot_zero_and_half_turn_cut_the_same_geometry(kind, bore_review_body, review_run):
    """Null ist ein ausdrücklich gewählter Winkel und kein Ersatz für die alte Richtung."""
    from app.core.brep import edit

    solid = edit.slot_bore(
        edit.box(100.0, 80.0, 10.0),
        position=(-20.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=10.0,
        length=20.0,
        angle_deg=45.0,
        overlap=0.0,
    )
    entry = bore_review_body(solid, kind)
    feature = next(f for f in entry.features.values() if f.kind == "slot")
    zero = review_run("slot_hole", entry, at_feature=feature.id, slot_length=22.0, slot_angle=0.0)
    half = review_run("slot_hole", entry, at_feature=feature.id, slot_length=22.0, slot_angle=180.0)
    assert zero.outputs[0].mesh.volume == pytest.approx(half.outputs[0].mesh.volume, abs=0.01)


@pytest.mark.parametrize(
    "params,expected",
    [
        ({"x": 10.0, "z": 10.0, "nx": 1.0, "depth": 5.0}, math.pi * 20.0),
        (
            {
                "z": 20.0,
                "depth": 10.0,
                "widening_diameter": 8.0,
                "widening_depth": 3.0,
                "transition_angle": 180.0,
            },
            math.pi * 76.0,
        ),
    ],
)
def test_exact_drill_keeps_normal_and_widening(params, expected, review_run) -> None:
    """Die exakte Bohrung schneidet die gespeicherte Richtung und Aufweitung."""
    run = review_run

    load_operations()
    source = run("create_brep_box", width=20.0, depth=20.0, height=20.0).outputs[0]
    result = run("drill_brep_hole", source, diameter=4.0, compensate=False, **params)
    assert source.mesh.volume - result.outputs[0].mesh.volume == pytest.approx(expected)


def test_exact_drill_uses_object_material(profile) -> None:
    """Das Material des Zielkörpers bestimmt die Lochkompensation."""
    from app.core.knowledge.profiles import for_object
    from tests.test_brep import run

    load_operations()
    source = run("create_brep_box", None, profile, width=20.0, depth=20.0, height=20.0).outputs[0]
    source = replace(source, material="pla")
    result = run("drill_brep_hole", source, profile, diameter=4.0, z=20.0, compensate=True)
    diameter = 4.0 + for_object(profile, source).material.hole_compensation
    assert source.mesh.volume - result.outputs[0].mesh.volume == pytest.approx(
        math.pi * diameter**2 * 5.0
    )


def test_pocket_upper_edge_is_identical_for_mesh_and_exact(review_run) -> None:
    """Eine innen liegende Oberkante bekommt keine zusätzliche Schnitttiefe."""
    run = review_run

    load_operations()
    for op in ("create_box", "create_brep_box"):
        source = run(op, width=20.0, depth=20.0, height=20.0).outputs[0]
        result = run("sketch_pocket", source, length=4.0, width=4.0, depth=2.0, z=10.0)
        assert source.mesh.volume - result.outputs[0].mesh.volume == pytest.approx(32.0)


@pytest.mark.parametrize("op", ["union_objects", "subtract_objects", "intersect_objects"])
def test_user_boolean_preserves_exact_bodies(document, profile, op) -> None:
    """Nach dem Nutzerbefehl bleibt eine exakte Kante weiter verrundbar."""
    from app.core.scene import History, OperationDraft, evaluate

    load_operations()
    history = History(document)
    for x in (0.0, 5.0):
        history.apply(
            "Quader",
            [
                OperationDraft(
                    op="create_brep_box",
                    params={"width": 20.0, "depth": 20.0, "height": 20.0, "x": x},
                )
            ],
        )
    history.apply("Boolesch", [OperationDraft(op=op, inputs=("obj_1", "obj_2"))])
    result = evaluate(document, profile)
    assert result.stopped_at is None
    assert result.scene.objects["obj_1"].kind == "brep"
    expected = {"union_objects": 10000.0, "subtract_objects": 2000.0, "intersect_objects": 6000.0}
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(expected[op])
    history.apply(
        "Rundung", [OperationDraft(op="fillet_edges", inputs=("obj_1",), params={"radius": 0.5})]
    )
    assert evaluate(document, profile).stopped_at is None


@pytest.mark.parametrize("mode", ["linear", "circular"])
def test_pattern_copies_remain_exact(document, profile, mode) -> None:
    """Reihe und Kranz erhalten für jede Kopie die exakte Körperart."""
    from app.core.scene import History, OperationDraft, evaluate

    load_operations()
    history = History(document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 10.0, "depth": 10.0, "height": 10.0}
            )
        ],
    )
    history.apply(
        "Muster",
        [
            OperationDraft(
                op="pattern", inputs=("obj_1",), params={"kind": mode, "count": 2, "spacing": 20.0}
            )
        ],
    )
    result = evaluate(document, profile)
    assert result.stopped_at is None
    assert [obj.kind for obj in result.scene.objects.values()] == ["brep", "brep"]
    history.apply(
        "Rundung", [OperationDraft(op="fillet_edges", inputs=("obj_2",), params={"radius": 1.0})]
    )
    assert evaluate(document, profile).stopped_at is None


def test_colouring_preserves_the_hollow_space(review_run) -> None:
    """Ganze Farbe und einzelne Flächen lassen die Innenraumgeometrie bestehen."""
    from app.core.geom.paint import fill_feature

    run = review_run

    load_operations()
    source = run("create_box", width=12.0, depth=12.0, height=12.0).outputs[0]
    hollow = run("hollow_object", source, wall=2.0, open_top=True, vents=False).outputs[0]
    assert hollow.mesh.cavity is not None
    painted = run("assign_slot", hollow, slot=0, colour="#ff0000").outputs[0]
    assert painted.mesh.cavity is hollow.mesh.cavity
    filled = fill_feature(hollow.mesh, (0, 1), 1).mesh
    assert filled.cavity is hollow.mesh.cavity
    result = run("lattice_fill", painted, structure="cubic", cell=5.0, wall=1.0)
    assert len(result.outputs) == 1
    output = result.outputs[0].mesh
    assert output.volume > painted.mesh.volume
    assert output.bounds.minimum == pytest.approx(painted.mesh.bounds.minimum)
    assert output.bounds.maximum == pytest.approx(painted.mesh.bounds.maximum)
    from app.core.geom.boolean import boolean

    missing_shell = boolean("difference", [painted.mesh, output], allow_empty=True)
    assert missing_shell.mesh.volume < 1e-6
    assert "boolean.parts_not_united" not in [finding.code for finding in result.findings]


def test_inner_floor_sketch_grows_into_the_cavity(review_run) -> None:
    """Die nach außen gerichtete Innenbodennormale zeigt in den Hohlraum."""
    run = review_run

    load_operations()
    source = replace(
        run("create_brep_box", width=20.0, depth=20.0, height=20.0).outputs[0], id="obj_1"
    )
    hollow = run("shell_exact", source, wall=2.0).outputs[0]
    floor = next(
        f
        for f in hollow.features.values()
        if f.kind == "face"
        and abs(float(f.params["centre"][2]) - 2.0) < 1e-5
        and float(f.params["normal"][2]) > 0.9
    )
    text = sketch_to_text(replace(rectangle(4.0, 4.0), plane=feature_plane(hollow.id, floor.id)))
    raised = run("sketch_extrude", hollow, sketch=text, height=3.0).outputs[0]
    assert raised.mesh.bounds.minimum[2] == pytest.approx(2.0)
    assert raised.mesh.bounds.maximum[2] == pytest.approx(5.0)
    pocket = run("sketch_pocket", hollow, sketch=text, depth=1.0).outputs[0]
    assert hollow.mesh.volume - pocket.mesh.volume == pytest.approx(16.0)


def test_drawn_free_dof_reaches_the_operation_report(review_run) -> None:
    """Freie Maße bleiben nach dem Schließen des Editors als Befund sichtbar —
    an einer Zeichnung, die **bemaßt** ist und trotzdem noch wandern kann."""
    run = review_run

    load_operations()
    circle = SketchElement("circle", ((0.0, 0.0), (2.0, 0.0)))
    sketch = Sketch(
        plane="plane:xy",
        elements=(circle,),
        constraints=(SketchConstraint("diameter", (0, 1), "4"),),
    )
    result = run("sketch_extrude", sketch=sketch_to_text(sketch), height=3.0)
    finding = next(f for f in result.findings if f.code == "sketch.underconstrained")
    assert finding.values["free_dof"] == solver.solve_sketch(sketch).free_dof > 0


def test_a_freehand_drawing_without_any_measure_is_no_finding(review_run) -> None:
    """KUNDE-08, entschieden in der Durchsicht v0.5.1 (rest-kunde): Ein frei
    gezogenes Rechteck ohne ein einziges Maß bekommt keinen Hinweis.

    Wer kein Maß anlegt, zeichnet frei und druckt, was er sieht — genau das,
    was der Satz verspricht. Als Zeile im Prüfbericht las er sich nach jeder
    freien Zeichnung wie ein Mangel, ohne Handlung. Wer bemaßt hat, will eine
    bestimmte Form; ihm sagt der Hinweis, dass noch etwas wandern kann (Test
    darüber). Der Skizzeneditor zeigt die offenen Maße weiter beim Zeichnen.
    """
    run = review_run

    load_operations()
    drawn = rectangle(6.0, 4.0)
    # Wie mit dem Rechteckwerkzeug gezogen: Ecken und Richtungen hängen
    # zusammen, eine Zahl steht nirgends.
    unmeasured = replace(
        drawn,
        constraints=tuple(
            entry
            for entry in drawn.constraints
            if entry.kind not in {"distance", "radius", "diameter", "angle"}
        ),
    )
    for sketch in (
        Sketch(plane="plane:xy", elements=(SketchElement("circle", ((0.0, 0.0), (2.0, 0.0))),)),
        unmeasured,
    ):
        assert solver.solve_sketch(sketch).free_dof > 0, "sonst prüft der Test nichts"
        result = run("sketch_extrude", sketch=sketch_to_text(sketch), height=3.0)
        assert "sketch.underconstrained" not in {f.code for f in result.findings}


def test_g05_mesh_pocket_on_an_offset_face() -> None:
    """Die gewählte Fläche legt die Tasche in beiden Kernen an dieselbe Stelle."""
    from tests.helpers import run_with_parameters as run

    load_operations()
    entry = run("create_brep_box", width=40.0, depth=30.0, height=20.0).outputs[0]
    entry.id = "obj_1"
    face_id = max(entry.features, key=lambda key: entry.features[key].params["centre"][2])
    sketch = replace(rectangle(6.0, 6.0), plane=feature_plane(entry.id, face_id))
    text = sketch_to_text(sketch)
    for source in (entry, replace(entry, kind="mesh", mesh=MeshData.of(entry.mesh.raw.copy()))):
        result = run("sketch_pocket", source, sketch=text, depth=4.0)
        assert source.mesh.volume - result.outputs[0].mesh.volume == pytest.approx(144.0)


def test_g06_all_box_face_normals_point_outwards() -> None:
    """Auch umgekehrt orientierte OCC-Flächen liefern die äußere Normale."""
    from tests.helpers import run_with_parameters as run

    load_operations()
    entry = run("create_brep_box", width=40.0, depth=30.0, height=20.0).outputs[0]
    for face in entry.features.values():
        normal = np.asarray(face.params["normal"])
        away = np.asarray(face.params["centre"]) - entry.mesh.bounds.centre
        assert np.dot(normal, away) > 0.0


def test_g06_dragging_the_left_face_changes_the_left_side() -> None:
    """Die unveränderte UI-Projektion muss tatsächlich die gewählte Seite ziehen."""
    from tests.helpers import run_with_parameters as run

    load_operations()
    entry = run("create_brep_box", width=40.0, depth=30.0, height=20.0).outputs[0]
    entry.id = "obj_1"
    face = min(entry.features.values(), key=lambda feature: feature.params["centre"][0])
    normal = face.params["normal"]
    distance = float(np.dot(normal, (-5.0, 0.0, 0.0)))
    result = run("push_face", entry, nx=normal[0], ny=normal[1], nz=normal[2], distance=distance)
    assert result.outputs[0].mesh.bounds.minimum[0] == pytest.approx(-25.0)
    assert result.outputs[0].mesh.bounds.maximum[0] == pytest.approx(20.0)
    assert result.outputs[0].mesh.volume == pytest.approx(27000.0)


@pytest.mark.parametrize(
    "kind,points",
    [
        ("circle", ((0.0, 0.0), (5.0, 0.0))),
        ("arc", ((0.0, 0.0), (5.0, 0.0), (0.0, 5.0))),
        ("spline", ((0.0, 0.0), (5.0, 0.0), (8.0, 2.0))),
        ("point", ((0.0, 0.0),)),
    ],
)
def test_g07_extending_other_elements_preserves_the_sketch(kind, points) -> None:
    """Ein ungeeigneter Treffer darf weder Element noch Bedingungen zerstören."""
    sketch = Sketch(
        "plane:xy",
        elements=(SketchElement(kind, points), SketchElement("line", ((12.0, -5.0), (12.0, 5.0)))),
        constraints=(SketchConstraint("fixed", (0,)),),
    )
    with pytest.raises(ValidationError) as failure:
        extend(sketch, 0, (5.0, 0.0))
    assert failure.value.suggestions
    assert sketch.elements[0].kind == kind
    assert len(sketch.constraints) == 1


def test_g09_circle_gauges_count_towards_the_dense_budget(monkeypatch) -> None:
    """Schon zwei freie Kreise brauchen eine 2×8-Matrix für ihren Rang."""
    sketch = Sketch(
        "plane:xy",
        elements=(
            SketchElement("circle", ((0.0, 0.0), (1.0, 0.0))),
            SketchElement("circle", ((4.0, 0.0), (5.0, 0.0))),
        ),
    )
    monkeypatch.setattr(solver, "MAX_JACOBIAN_BYTES", 64)
    with pytest.raises(ValidationError) as failure:
        solver.solve_sketch(sketch)
    assert failure.value.constraint == "too_large"


@pytest.mark.parametrize("axis", ["x", "y", "z"])
@pytest.mark.parametrize("angle", [-180.0, -120.0, -90.1, 90.1, 120.0, 180.0])
def test_g11_gizmo_rotation_roundtrips_past_ninety_degrees(axis, angle) -> None:
    """Achse und Winkel müssen dieselbe sichtbare Drehung rekonstruieren."""
    matrix = translation((1.0, 2.0, 3.0)) @ rotation(axis, angle) @ scaling((1.5,) * 3)
    steps = decompose_transform(matrix)
    rebuilt = (
        translation(steps.offset) @ rotation(steps.axis, steps.angle) @ scaling((steps.scale,) * 3)
    )
    np.testing.assert_allclose(rebuilt, matrix, atol=1e-10)


def test_g12_equal_face_counts_do_not_prove_equal_material_assignment() -> None:
    """Eine halbierte Box hat wieder zwölf Dreiecke, aber andere Flächen."""
    bo = importlib.import_module("app.core.geom.boolean")
    raw = trimesh.creation.box(extents=(10.0,) * 3)
    source = MeshData.of(raw, tuple(1 if normal[0] < -0.5 else 0 for normal in raw.face_normals))
    tool = trimesh.creation.box(extents=(10.0, 20.0, 20.0))
    tool.apply_translation((5.0, 0.0, 0.0))
    result = bo.boolean("difference", [source, MeshData.of(tool)], cut_slot=2).mesh
    assert result.triangle_count == source.triangle_count
    for slot, normal in zip(result.slots, result.raw.face_normals, strict=True):
        assert slot == (1 if normal[0] < -0.5 else 2 if normal[0] > 0.5 else 0)


def test_g13_voxel_cell_budget_does_not_overflow(monkeypatch) -> None:
    """Nur die Arithmetik läuft; die eigentliche Rasterallokation ist gesperrt."""
    bo = importlib.import_module("app.core.geom.boolean")
    raw = trimesh.creation.box(extents=(1.0,) * 3)
    far = raw.copy()
    far.apply_translation((104857.6,) * 3)

    def forbidden(*args):
        pytest.fail("budget must reject before raster allocation")

    monkeypatch.setattr(bo, "_rasterise", forbidden)
    assert bo._voxel("union", [MeshData.of(raw), MeshData.of(far)]) is None


def test_g14_same_volume_and_bounds_still_show_a_moved_hole() -> None:
    """Die Differenzansicht muss beide Lochpositionen sichtbar machen."""
    from app.core.geom.boolean import boolean
    from app.core.geom.difference import compare_scenes
    from tests.test_difference import scene_with

    plate = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 2.0)))

    def cut(x):
        tool = trimesh.creation.box(extents=(2.0, 2.0, 4.0))
        tool.apply_translation((x, 0.0, 0.0))
        return boolean("difference", [plate, MeshData.of(tool)]).mesh

    difference = compare_scenes(scene_with(obj_1=cut(-4.0)), scene_with(obj_1=cut(4.0)))
    assert difference.added_volume == pytest.approx(8.0)
    assert difference.removed_volume == pytest.approx(8.0)


def test_g17_wall_scale_remains_ordered_when_every_wall_exceeds_the_cap(profile) -> None:
    """Gedeckelte Wandkarten brauchen dieselben Grenzen in Bild und Legende.

    Bis zum 06.09.2026 prüfte der Test nur die Ordnung der drei Zahlen. Der
    Befund war aber, dass Bild und Legende verschiedene Skalen zeigten — also
    gehört hierher, wo die Skala beginnt, wo der Deckel liegt und dass die
    Legende den Deckel auch nennt.
    """
    import math

    from app.core.perceive.maps import WALL_SCALE_FACTOR, wall_thickness_map

    mesh = MeshData.of(trimesh.creation.box(extents=(20.0,) * 3))
    minimum = profile.minimum_wall_thickness
    result = wall_thickness_map(mesh, minimum=minimum)
    known = [value for value in result.values if not math.isnan(value)]
    assert max(known) > minimum * WALL_SCALE_FACTOR, "der Würfel muss den Deckel überschreiten"
    assert result.low == 0.0
    assert result.high == pytest.approx(minimum * WALL_SCALE_FACTOR)
    assert result.threshold == minimum
    assert result.low < result.threshold < result.high
    assert result.note == (
        "Untergrenze sind zwei Extrusionsbreiten. Die Skala endet weit darüber; "
        "alles Dickere trägt dieselbe Farbe."
    )


@pytest.mark.parametrize("angle", [15.0, 45.0, 105.0, 225.0])
def test_g03_small_holes_near_the_circular_rim_stay_holes(angle) -> None:
    """Ein inskribiertes Zwölfeck darf den Rand eines Kreises nicht ersetzen."""
    import math

    from app.core.sketch.profile import regions_of
    from tests.helpers import run_with_parameters as run

    load_operations()
    centre = (9.5 * math.cos(math.radians(angle)), 9.5 * math.sin(math.radians(angle)))
    sketch = Sketch(
        "plane:xy",
        elements=(
            SketchElement("circle", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("circle", (centre, (centre[0] + 0.3, centre[1]))),
        ),
    )
    regions = regions_of(solver.solve_sketch(sketch))
    assert len(regions) == 1 and len(regions[0].holes) == 1
    result = run("sketch_extrude", sketch=sketch_to_text(sketch), height=2.0)
    assert result.outputs[0].mesh.volume == pytest.approx(math.pi * (100.0 - 0.09) * 2.0)


@pytest.mark.parametrize(
    "centre,radius", [((-6.0, 0.0), 5.0), ((5.0, 0.0), 5.0), ((0.0, 0.0), 10.0)]
)
def test_g04_crossing_touching_and_duplicate_rings_are_rejected(centre, radius) -> None:
    """Aus mehrdeutigen Randringen darf kein ungültiger Körper entstehen."""
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    sketch = Sketch(
        "plane:xy",
        elements=(
            SketchElement("circle", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("circle", (centre, (centre[0] + radius, centre[1]))),
        ),
    )
    with pytest.raises(GeometryError) as failure:
        regions_of(solver.solve_sketch(sketch))
    assert failure.value.suggestions


def test_g08_exact_spline_matches_every_preview_sample() -> None:
    """Beide Wege benutzen dieselben kubischen Stücke, auch zwischen den Punkten."""
    from app.core.brep.profiles import _lift_xy, _spline_curve
    from app.core.sketch.profile import _along_spline

    points = ((0.0, 0.0), (2.0, 6.0), (7.0, -3.0), (11.0, 2.0))
    curve = _spline_curve(points, _lift_xy)
    preview = _along_spline(points)
    for index, point in enumerate(preview):
        parameter = curve.FirstParameter() + (
            curve.LastParameter() - curve.FirstParameter()
        ) * index / (len(preview) - 1)
        actual = curve.Value(parameter)
        np.testing.assert_allclose((actual.X(), actual.Y()), point, atol=1e-9)


def test_g04_crossing_line_and_circle_boundaries_are_rejected() -> None:
    """Die Grenzprüfung gilt auch zwischen verschiedenen Kurvenarten."""
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    square = rectangle(8.0, 8.0)
    sketch = replace(
        square, elements=(*square.elements, SketchElement("circle", ((4.0, 0.0), (7.0, 0.0))))
    )
    with pytest.raises(GeometryError, match="schneiden oder berühren"):
        regions_of(solver.solve_sketch(sketch))


def test_g08_the_old_crossing_interpolation_is_a_valid_drawn_outline() -> None:
    """Dieser Umriss kreuzte nur die fremde Interpolation, nicht die Vorschau."""
    from OCP.BRepCheck import BRepCheck_Analyzer

    from app.core.sketch.profile import regions_of, signed_area
    from tests.helpers import run_with_parameters as run

    points = ((-10.0, -5.0), (0.0, 5.0), (-6.0, 0.0), (-9.0, 0.0))
    sketch = Sketch(
        "plane:xy",
        elements=(SketchElement("spline", points), SketchElement("line", (points[-1], points[0]))),
    )
    profile = regions_of(solver.solve_sketch(sketch))[0]
    result = run("sketch_extrude", sketch=sketch_to_text(sketch), height=2.0).outputs[0].mesh
    assert BRepCheck_Analyzer(result.shape).IsValid()
    assert result.volume == pytest.approx(abs(signed_area(profile)) * 2.0)


def _feature_run(name, entry, profile, **params):
    """Derselbe registrierte Aufruf wie im Merkmalsdialog."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    load_operations()
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=1,
            progress=lambda *_: None,
            ask=lambda _, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_an_absurd_diameter_is_rejected_before_any_tool_is_built(profile) -> None:
    """Die Durchmesserfelder haben keine feste Obergrenze (ein gemessenes Maß darf
    nicht geklemmt werden), aber ein Werkzeug von tausend Metern baut niemand."""
    from app.core.geom.prepare import drill
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    base = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))
    bored = drill(
        base,
        position=(0.0, 0.0, 10.0),
        axis="z",
        diameter=8.0,
        depth=0.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject("obj_1", "Platte", bored, features=detect(bored))
    hole = next(feature for feature in entry.features.values() if feature.kind == "hole")
    with pytest.raises(ValidationError) as caught:
        _feature_run("resize_hole", entry, profile, at_feature=hole.id, diameter=1_000_000.0)
    assert caught.value.field == "diameter"
    assert caught.value.constraint == "maximum"
    # Ein großes, aber echtes Maß geht weiter durch.
    result = _feature_run("resize_hole", entry, profile, at_feature=hole.id, diameter=30.0)
    assert result.outputs


def test_g34_shallow_wide_hole_copy_preserves_depth(profile) -> None:
    """Der Durchmesser ist kein Ersatz für die gemessene Sacklochtiefe."""
    from app.core.geom.prepare import drill
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    base = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))
    bored = drill(
        base,
        position=(-15.0, 0.0, 10.0),
        axis="z",
        diameter=12.0,
        depth=2.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject("obj_1", "Platte", bored, features=detect(bored))
    hole = next(feature for feature in entry.features.values() if feature.kind == "hole")
    copied = _feature_run(
        "duplicate_feature",
        entry,
        profile,
        at_feature=hole.id,
        x=15.0,
        y=0.0,
        z=float(hole.params["centre"][2]),
    ).outputs[0]
    assert bored.volume - copied.mesh.volume == pytest.approx(base.volume - bored.volume, rel=0.02)


def test_g38_sideways_move_into_a_thicker_wall_reports_lost_throughness(profile) -> None:
    """Eine seitliche Bewegung kann den Durchgang genauso verlieren wie eine axiale."""
    from app.core.geom.boolean import boolean
    from app.core.geom.prepare import drill
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    base = trimesh.creation.box(extents=(60.0, 40.0, 10.0))
    base.apply_translation((0.0, 0.0, 5.0))
    raised = trimesh.creation.box(extents=(30.0, 40.0, 20.0))
    raised.apply_translation((15.0, 0.0, 10.0))
    stepped = boolean("union", [MeshData.of(base), MeshData.of(raised)]).mesh
    bored = drill(
        stepped,
        position=(-15.0, 0.0, 10.0),
        axis="z",
        diameter=6.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject("obj_1", "Stufenplatte", bored, features=detect(bored))
    hole = next(feature for feature in entry.features.values() if feature.kind == "hole")
    assert hole.params["through"]
    moved = _feature_run(
        "move_feature",
        entry,
        profile,
        at_feature=hole.id,
        x=15.0,
        y=0.0,
        z=float(hole.params["centre"][2]),
    )
    assert any(finding.code == "move_feature.no_longer_through" for finding in moved.findings)
    assert moved.outputs[0].features[hole.id].params["through"] is False


def test_g35_removed_highest_id_stays_reserved_after_an_intermediate_op_and_cache(
    profile, tmp_path
) -> None:
    """Entfernen, Verschieben und erneutes Kopieren bleiben auch mit Plattencache eindeutig."""
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import ProjectSources, new_project

    project = new_project(profile.printer.id, profile.material.id)
    history = History(project.document)
    history.apply(
        "Platte",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 40.0, "height": 10.0})],
    )
    for x in (-25.0, 0.0, 25.0):
        history.apply(
            "Bohrung",
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=("obj_1",),
                    params={"x": x, "z": 10.0, "diameter": 6.0, "compensate": False},
                )
            ],
        )
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources)
    assert before.complete
    holes = sorted(
        name
        for name, feature in before.scene.objects["obj_1"].features.items()
        if feature.kind == "hole"
    )
    assert len(holes) == 3
    history.apply(
        "Entfernen",
        [OperationDraft(op="remove_feature", inputs=("obj_1",), params={"at_feature": holes[-1]})],
    )
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 1.0})],
    )
    cache = ResultCache(disk=DiskCache(MeshCodec(), directory=tmp_path / "cache"))
    removed = evaluate(project.document, profile, sources=sources, cache=cache)
    assert removed.complete
    entry = removed.scene.objects["obj_1"]
    history.apply(
        "Kopieren",
        [
            OperationDraft(
                op="duplicate_feature",
                inputs=("obj_1",),
                params={
                    "at_feature": holes[0],
                    "x": -12.0,
                    "y": 0.0,
                    "z": entry.features[holes[0]].params["centre"][2],
                },
            )
        ],
    )
    replay_cache = ResultCache(disk=DiskCache(MeshCodec(), directory=tmp_path / "cache"))
    replayed = evaluate(
        project.document,
        profile,
        sources=sources,
        cache=replay_cache,
    )
    assert replayed.complete
    assert replay_cache.statistics.disk_hits > 0
    copied = replayed.scene.objects["obj_1"]
    assert holes[-1] not in copied.features
    assert "hole_4" in copied.features
    assert holes[-1] in copied.reserved_feature_ids


def test_cavity_follows_transforms_cache_budget_and_object_identity(tmp_path) -> None:
    """Der exakte Innenraum muss dieselbe Lage und Cacheidentität behalten."""
    import json

    from app.core.geom.mesh import MeshCodec
    from app.core.geom.transform import apply
    from app.core.scene.cache import CachedResult, DiskCache, ResultCache
    from app.core.scene.hashing import object_hash
    from app.core.types import SceneObject

    body = MeshData.of(trimesh.creation.box(extents=(10.0,) * 3))
    cavity = MeshData.of(trimesh.creation.box(extents=(8.0,) * 3))
    source = replace(body, cavity=cavity)
    matrix = translation((11.0, 4.0, 3.0)) @ rotation("y", 120.0) @ scaling((1.0, 2.0, 3.0))
    moved = apply(source, matrix)
    assert moved.cavity is not None
    np.testing.assert_allclose(moved.cavity.raw.vertices, apply(cavity, matrix).raw.vertices)
    cached = CachedResult(objects=(SceneObject("obj_1", "Hohlkörper", moved),))
    assert cached.cost == body.triangle_count + cavity.triangle_count
    disk = DiskCache(MeshCodec(), directory=tmp_path / "cache")
    disk.put("cavity", cached)
    restored = disk.get("cavity")
    assert restored is not None
    np.testing.assert_allclose(
        restored.objects[0].mesh.cavity.raw.vertices, moved.cavity.raw.vertices
    )
    assert object_hash("op", 0, cavity=cavity) != object_hash("op", 0, cavity=moved.cavity)
    assert object_hash("op", 0) != object_hash("op", 0, cavity=cavity)
    memory = ResultCache(triangle_budget=36)
    memory.put("one", cached)
    memory.put("two", cached)
    assert memory.statistics.evictions == 1
    metadata = next((tmp_path / "cache").rglob("objects.json"))
    old = json.loads(metadata.read_text(encoding="utf-8"))
    old.pop("format_version")
    metadata.write_text(json.dumps(old), encoding="utf-8")
    assert disk.get("cavity") is None


@pytest.mark.parametrize("sections", [48, 96])
@pytest.mark.parametrize("remove_all", [False, True])
def test_large_foreign_countersink_preserves_the_unselected_section(
    sections, remove_all, review_run
):
    """Ein weiter Kegel bleibt maßhaltig; beim vollständigen Entfernen bleibt nichts."""
    from app.core.geom.boolean import boolean
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    plate = MeshData.of(trimesh.creation.box(extents=(100.0, 100.0, 30.0)))
    widening = trimesh.creation.revolve([[0, -2], [8, -2], [25, 15], [0, 15]], sections=sections)
    bore = trimesh.creation.cylinder(radius=8, height=32, sections=sections)
    body = boolean("difference", [plate, MeshData.of(widening), MeshData.of(bore)]).mesh
    entry = SceneObject(id="obj_1", name="Prüfplatte", mesh=body, features=detect(body))
    hole = next(f for f in entry.features.values() if f.kind == "hole")
    out = review_run(
        "remove_feature", entry, at_feature=hole.id, sections="chain" if remove_all else "single"
    ).outputs[0]
    expected = 300000.0 if remove_all else 300000.0 - widening.volume
    assert out.mesh.volume == pytest.approx(expected, abs=0.02)
    found = detect(out.mesh)
    assert not any(f.kind in {"hole", "pin"} for f in found.values())
    assert sum(f.kind == "cone" for f in found.values()) == (0 if remove_all else 1)


def test_open_slot_metadata_follows_a_rigid_body_transform(bore_review_body):
    """Die freie Mündung bleibt nach Drehen und Verschieben am tatsächlichen Rand."""
    from app.core.brep import edit
    from app.core.perceive.matching import moved_features

    body = edit.cut_bore(
        edit.box(40.0, 30.0, 10.0),
        position=(19.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=10.0,
    )
    entry = bore_review_body(body, "mesh")
    feature = next(f for f in entry.features.values() if f.kind == "slot")
    moved = moved_features(
        {feature.id: feature}, translation((4.0, 3.0, 2.0)) @ rotation("z", 90.0)
    )[feature.id]
    assert moved.params["arc_centre"] == pytest.approx((4.0, 22.0, 7.0), abs=0.01)
    assert moved.params["mouth_centre"] == pytest.approx((4.0, 23.0, 7.0), abs=0.01)
    assert moved.params["opening_normal"] == pytest.approx((0.0, 1.0, 0.0), abs=0.01)
    assert moved.params["direction"] == pytest.approx((0.0, 1.0, 0.0), abs=0.01)


def test_unexpected_cavity_answer_does_not_silently_remove_one_section() -> None:
    """Eine fremde Rückfrageantwort entscheidet nicht still über den Hohlraum."""
    from types import SimpleNamespace

    import pytest

    from app.core.errors import InternalError
    from app.core.geom.prepare_ops import _asked_about_sections

    with pytest.raises(InternalError):
        _asked_about_sections(SimpleNamespace(ask=lambda *_: "unexpected"), [])


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("change", ["mirror", "uniform", "anisotropic", "fit"])
def test_p0_box_transforms_keep_six_current_faces(document, profile, kind, quality, change):
    """Sechs benannte Seiten behalten nach jeder Transformation ihre wirklichen Maße."""
    from app.core.scene import History, OperationDraft, evaluate

    if kind == "brep":
        exact_kernel()
    load_operations()
    history = History(document)
    history.apply(
        "Asymmetrischer Quader",
        [
            OperationDraft(
                op="create_brep_box" if kind == "brep" else "create_box",
                params={
                    "width": 10.0,
                    "depth": 6.0,
                    "height": 4.0,
                    "x": 17.0,
                    "y": -9.0,
                    "z": 11.0,
                },
            )
        ],
    )
    initial = evaluate(document, profile, quality=quality)
    assert initial.complete
    original = initial.scene.objects["obj_1"]
    assert len(original.features) == 6
    assert all(feature.kind == "face" for feature in original.features.values())
    sides = {}
    for name, feature in original.features.items():
        normal = np.asarray(feature.params["normal"])
        axis = int(np.argmax(np.abs(normal)))
        side = 1 if normal[axis] > 0 else -1
        sides[name] = (axis, side)
    assert set(sides.values()) == {(axis, side) for axis in range(3) for side in (-1, 1)}

    def assert_faces(entry, factors):
        # Die Konstruktion setzt die Unterseite bei Z=11: die Mitte liegt bei Z=13.
        centre = np.array((17.0, -9.0, 13.0)) * factors
        size = np.array((10.0, 6.0, 4.0)) * np.abs(factors)
        assert entry.mesh.bounds.centre == pytest.approx(centre, abs=1e-6)
        assert entry.mesh.bounds.size == pytest.approx(size, abs=1e-6)
        assert entry.mesh.volume == pytest.approx(float(np.prod(size)), abs=1e-5)
        assert len(entry.features) == 6
        assert set(entry.features) == set(sides)
        for name, (axis, side) in sides.items():
            feature = entry.features[name]
            normal = np.zeros(3)
            normal[axis] = side * np.sign(factors[axis])
            place = centre + normal * size / 2.0
            area = float(np.prod(np.delete(size, axis)))
            assert feature.kind == "face"
            assert feature.params["centre"] == pytest.approx(place, abs=1e-6)
            assert feature.params["normal"] == pytest.approx(normal, abs=1e-6)
            assert feature.params["area"] == pytest.approx(area, abs=1e-5)
            assert feature.created_by == original.features[name].created_by
            assert feature.provenance == original.features[name].provenance
            assert feature.recognised == original.features[name].recognised
            assert feature.face_indices
            # Die Auswahl muss dieselbe Seite zeigen wie ihre Maße. Gerade ein
            # exakter Körper kann nach einer Transformation anders tesselliert sein.
            raw = entry.mesh.raw
            selected = raw.vertices[raw.faces[list(feature.face_indices)]]
            assert selected[:, :, axis] == pytest.approx(place[axis], abs=1e-6)

    assert_faces(original, (1.0, 1.0, 1.0))
    op, params, factors = {
        "mirror": ("mirror_object", {"axis": "x", "about": "origin"}, (-1.0, 1.0, 1.0)),
        "uniform": ("scale_object", {"factor": 2.0, "about": "origin"}, (2.0, 2.0, 2.0)),
        "anisotropic": (
            "scale_object",
            {"fx": 2.0, "fy": 1.0, "fz": 1.0, "about": "origin"},
            (2.0, 1.0, 1.0),
        ),
        "fit": ("fit_to_size", {"largest": 20.0, "about": "origin"}, (2.0, 2.0, 2.0)),
    }[change]
    history.apply("Transformieren", [OperationDraft(op=op, inputs=("obj_1",), params=params)])
    transformed = evaluate(document, profile, quality=quality)
    assert transformed.complete
    assert transformed.scene.objects["obj_1"].kind == kind
    assert_faces(transformed.scene.objects["obj_1"], factors)
    if change == "mirror":
        history.apply("Zurückspiegeln", [OperationDraft(op=op, inputs=("obj_1",), params=params)])
        restored = evaluate(document, profile, quality=quality)
        assert restored.complete
        assert_faces(restored.scene.objects["obj_1"], (1.0, 1.0, 1.0))


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("mode", ["linear", "circular"])
def test_p0_pattern_copies_keep_all_six_feature_locations(document, profile, kind, mode):
    """Jede Kopie führt die Namen, Maße und tatsächlichen Orte aller sechs Seiten mit."""
    from app.core.scene import History, OperationDraft, evaluate

    if kind == "brep":
        exact_kernel()
    load_operations()
    history = History(document)
    history.apply(
        "Asymmetrischer Quader",
        [
            OperationDraft(
                op="create_brep_box" if kind == "brep" else "create_box",
                params={
                    "width": 10.0,
                    "depth": 6.0,
                    "height": 4.0,
                    "x": 17.0,
                    "y": -9.0,
                    "z": 11.0,
                },
            )
        ],
    )
    before = evaluate(document, profile)
    assert before.complete
    original = before.scene.objects["obj_1"]
    assert len(original.features) == 6
    assert all(feature.kind == "face" for feature in original.features.values())
    history.apply(
        "Vier Kopien",
        [
            OperationDraft(
                op="pattern",
                inputs=("obj_1",),
                params={"kind": mode, "count": 4, "spacing": 20.0, "dx": 0.0, "dy": 1.0},
            )
        ],
    )
    after = evaluate(document, profile)
    assert after.complete
    assert len(after.scene.objects) == 4

    def turn(value, index):
        x, y, z = value
        return ((x, y, z), (-y, x, z), (-x, -y, z), (y, -x, z))[index]

    for index, entry in enumerate(after.scene.objects.values()):
        centre = (
            (17.0, -9.0 + 20.0 * index, 13.0)
            if mode == "linear"
            else turn((17.0, -9.0, 13.0), index)
        )
        assert entry.mesh.bounds.centre == pytest.approx(centre, abs=1e-6)
        assert entry.mesh.volume == pytest.approx(10.0 * 6.0 * 4.0, abs=1e-5)
        assert entry.kind == kind
        assert len(entry.features) == 6
        assert set(entry.features) == set(original.features)
        for name, old in original.features.items():
            current = entry.features[name]
            axis = int(np.argmax(np.abs(old.params["normal"])))
            initial_normal = np.zeros(3)
            initial_normal[axis] = np.sign(old.params["normal"][axis])
            x, y, z = np.array((17.0, -9.0, 13.0)) + initial_normal * (5.0, 3.0, 2.0)
            place = (x, y + 20.0 * index, z) if mode == "linear" else turn((x, y, z), index)
            normal = initial_normal if mode == "linear" else turn(initial_normal, index)
            assert current.kind == "face"
            assert current.params["centre"] == pytest.approx(place, abs=1e-6)
            assert current.params["normal"] == pytest.approx(normal, abs=1e-6)
            assert current.params["area"] == pytest.approx((24.0, 40.0, 60.0)[axis], abs=1e-5)
            assert current.created_by == old.created_by
            assert current.provenance == old.provenance
            assert current.recognised == old.recognised
            assert current.face_indices
            assert name in entry.reserved_feature_ids


@pytest.mark.parametrize("replay", ["warm", "disk", "reopen", "undo_redo"])
def test_p0_scaled_mesh_faces_survive_cache_project_and_history(profile, tmp_path, replay):
    """Nachspielen einer Transformation erhält aktuelle Maße und die ursprünglichen Namen."""
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import ProjectSources, load, new_project, save

    load_operations()
    project = new_project(profile.printer.id, profile.material.id)
    history = History(project.document)
    history.apply(
        "Asymmetrischer Quader",
        [
            OperationDraft(
                op="create_box",
                params={
                    "width": 10.0,
                    "depth": 6.0,
                    "height": 4.0,
                    "x": 17.0,
                    "y": -9.0,
                    "z": 11.0,
                },
            )
        ],
    )
    source = evaluate(project.document, profile, sources=ProjectSources(project))
    assert source.complete
    original = source.scene.objects["obj_1"]
    assert len(original.features) == 6
    assert all(feature.kind == "face" for feature in original.features.values())
    history.apply(
        "Spiegeln und skalieren",
        [
            OperationDraft(
                op="mirror_object", inputs=("obj_1",), params={"axis": "x", "about": "origin"}
            ),
            OperationDraft(
                op="mirror_object", inputs=("obj_1",), params={"axis": "x", "about": "origin"}
            ),
            OperationDraft(
                op="scale_object", inputs=("obj_1",), params={"factor": 2.0, "about": "origin"}
            ),
        ],
    )
    directory = tmp_path / "cache"
    cache = ResultCache(disk=DiskCache(MeshCodec(), directory=directory))
    first = evaluate(project.document, profile, sources=ProjectSources(project), cache=cache)
    assert first.complete
    if replay == "disk":
        cache = ResultCache(disk=DiskCache(MeshCodec(), directory=directory))
    elif replay in {"reopen", "undo_redo"}:
        project = load(save(project, tmp_path / "transformierter-quader.p3d"))
        cache = None
        if replay == "undo_redo":
            history = History(project.document)
            history.undo()
            undone = evaluate(project.document, profile, sources=ProjectSources(project))
            assert undone.complete
            restored = undone.scene.objects["obj_1"]
            assert restored.mesh.bounds.size == pytest.approx((10.0, 6.0, 4.0), abs=1e-6)
            assert restored.mesh.bounds.centre == pytest.approx((17.0, -9.0, 13.0), abs=1e-6)
            assert restored.features == original.features
            history.redo()
    result = evaluate(project.document, profile, sources=ProjectSources(project), cache=cache)
    assert result.complete
    if replay == "warm":
        assert cache.statistics.hits >= 4
        assert cache.statistics.disk_hits == 0
    elif replay == "disk":
        assert cache.statistics.disk_hits >= 4
    final = result.scene.objects["obj_1"]
    assert final.mesh.bounds.centre == pytest.approx((34.0, -18.0, 26.0), abs=1e-6)
    assert final.mesh.bounds.size == pytest.approx((20.0, 12.0, 8.0), abs=1e-6)
    assert final.mesh.volume == pytest.approx(20.0 * 12.0 * 8.0, abs=1e-5)
    assert len(final.features) == 6
    assert set(final.features) == set(original.features)
    for name, old in original.features.items():
        feature = final.features[name]
        axis = int(np.argmax(np.abs(old.params["normal"])))
        assert feature.kind == "face"
        assert feature.params["centre"] == pytest.approx(
            np.asarray(old.params["centre"]) * 2.0, abs=1e-6
        )
        assert feature.params["normal"] == pytest.approx(old.params["normal"], abs=1e-6)
        assert feature.params["area"] == pytest.approx((96.0, 160.0, 240.0)[axis], abs=1e-5)
        assert feature.created_by == old.created_by
        assert feature.provenance == old.provenance
        assert feature.face_indices
        assert name in final.reserved_feature_ids


def test_p0_multiple_orientations_keep_existing_mesh_feature_names(document, profile, monkeypatch):
    """Zwei eigene Drehungen führen auch erkannte Merkmale vorhandener Objektkennungen mit."""
    from types import SimpleNamespace

    from app.core.geom import prepare_ops
    from app.core.scene import History, OperationDraft, evaluate

    load_operations()
    history = History(document)
    history.apply(
        "Zwei stehende Quader",
        [
            OperationDraft(
                op="create_box", params={"width": 4.0, "depth": 6.0, "height": 10.0, "x": x}
            )
            for x in (17.0, 57.0)
        ],
    )
    before = evaluate(document, profile)
    assert before.complete
    assert len(before.scene.objects) == 2
    assert all(len(entry.features) == 6 for entry in before.scene.objects.values())
    # Nur die Auswahl der günstigen Lage ist festgelegt. Die echte Operation
    # bewegt beide Körper selbst und meldet ausdrücklich keine gemeinsame Matrix.
    matrices = iter(
        (
            ((1, 0, 0, 0), (0, 0, -1, 5), (0, 1, 0, 3), (0, 0, 0, 1)),
            ((0, 0, 1, 52), (0, 1, 0, 0), (-1, 0, 0, 59), (0, 0, 0, 1)),
        )
    )
    monkeypatch.setattr(
        prepare_ops,
        "orient_for_print",
        lambda *_args, **_kwargs: SimpleNamespace(
            transform=np.asarray(next(matrices), dtype=float), findings=[]
        ),
    )
    history.apply(
        "Gemeinsam hinlegen",
        [
            OperationDraft(
                op="orient_for_print",
                inputs=("obj_1", "obj_2"),
                params={"thorough": False, "arrange": False},
            )
        ],
    )
    after = evaluate(document, profile)
    assert after.complete
    expected = (
        ("obj_1", (17.0, 0.0, 3.0), (4.0, 10.0, 6.0)),
        ("obj_2", (57.0, 0.0, 2.0), (10.0, 6.0, 4.0)),
    )
    for index, (identifier, centre, size) in enumerate(expected):
        entry = after.scene.objects[identifier]
        original = before.scene.objects[identifier]
        assert entry.mesh.bounds.centre == pytest.approx(centre, abs=1e-6)
        assert entry.mesh.bounds.size == pytest.approx(size, abs=1e-6)
        assert set(entry.features) == set(original.features)
        for name, old in original.features.items():
            x, y, z = old.params["normal"]
            normal = (x, -z, y) if index == 0 else (z, y, -x)
            axis = int(np.argmax(np.abs((x, y, z))))
            current = entry.features[name]
            assert current.params["normal"] == pytest.approx(normal, abs=1e-6)
            assert current.params["centre"] == pytest.approx(
                np.asarray(centre) + np.asarray(normal) * np.asarray(size) / 2.0, abs=1e-6
            )
            assert current.params["area"] == pytest.approx((60.0, 40.0, 24.0)[axis], abs=1e-5)
            assert current.created_by == old.created_by
            assert current.provenance == old.provenance


def test_p0_deformed_thread_does_not_hide_a_real_spherical_surface(monkeypatch):
    """Ein ungültiger Gewinde-Suchkandidat darf echte neu erkannte Oberflächen nicht entfernen."""
    from app.core.knowledge.parts.build import thread
    from app.core.knowledge.parts.shapes import thread_body
    from app.core.scene.evaluate import _with_features
    from app.core.types import Feature, Operation, SceneObject

    threaded = thread_body(6.0, 1.0, 8.0)
    ellipsoid = trimesh.creation.icosphere(radius=0.3, subdivisions=2)
    ellipsoid.vertices[:, 0] *= 2.0
    ellipsoid.apply_translation((6.0, 0.0, 4.0))
    source = MeshData.of(trimesh.util.concatenate((threaded.raw, ellipsoid)))
    changed = source.raw.copy()
    changed.vertices[:, 0] *= 0.5
    moved = MeshData.of(changed)
    identifier, known = thread("made_thread", 6.0, 1.0, (0.0, 0.0, 4.0), length=8.0)
    known = replace(known, created_by=2)
    previous = {identifier: known}
    sphere_faces = tuple(range(threaded.triangle_count, moved.triangle_count))
    sphere_points = moved.raw.triangles[list(sphere_faces)].reshape(-1, 3)
    # Die vorher abseits liegende Ellipsoidfläche ist nach X/2 eine echte
    # Kugel. Sie liegt zugleich innerhalb der VERALTETEN Gewindehülle.
    assert np.linalg.norm(sphere_points - (3.0, 0.0, 4.0), axis=1) == pytest.approx(0.3, abs=1e-10)
    assert np.hypot(sphere_points[:, 0], sphere_points[:, 1]).min() > 2.0
    assert np.hypot(sphere_points[:, 0], sphere_points[:, 1]).max() < 3.5
    measured = Feature(
        id="sphere_probe",
        kind="sphere",
        provenance="detected",
        params={"centre": (3.0, 0.0, 4.0), "diameter": 0.6},
        face_indices=sphere_faces,
    )
    # Die Messung selbst wird hier nicht geprüft, sondern die nachfolgende
    # Unterdrückung. Ihre Fläche ist durch die unabhängige Radiusprobe belegt.
    evaluation = importlib.import_module("app.core.scene.evaluate")
    monkeypatch.setattr(evaluation, "detect", lambda *_args, **_kwargs: {measured.id: measured})
    findings = []
    result = _with_features(
        SceneObject("obj_1", "Gewinde mit Außenfläche", moved, features=previous),
        previous,
        Operation(
            id=3, op="scale_object", inputs=("obj_1",), outputs=("obj_1",), params={"fx": 0.5}
        ),
        lambda _question, choices: choices[0],
        findings,
        ((0.5, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        source.bounds,
        referenced={identifier},
    )
    assert identifier not in result.features
    assert any(finding.code == "perceive.generated_lost" for finding in findings)
    assert measured.id in result.features
    assert result.features[measured.id].params["diameter"] == pytest.approx(0.6)
    assert result.features[measured.id].face_indices == sphere_faces


@pytest.mark.parametrize("recognition", ["global", "budget", "local"])
def test_p0_rotated_tetrahedral_void_keeps_measured_bounds(monkeypatch, recognition):
    """Die Hülle eines gedrehten Tetraeders ist nicht die gedrehte alte Quaderhülle."""
    from app.core.perceive.features import detect_voids
    from app.core.perceive.matching import transformed_features
    from app.core.scene.evaluate import _with_features
    from app.core.types import Operation, SceneObject

    outer = trimesh.creation.box(extents=(30.0, 30.0, 30.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    tetrahedron = trimesh.Trimesh(
        vertices=((2.0, 3.0, 4.0), (8.0, 3.0, 4.0), (2.0, 7.0, 4.0), (2.0, 3.0, 6.0)),
        faces=((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)),
        process=False,
    )
    assert tetrahedron.volume == pytest.approx(6.0 * 4.0 * 2.0 / 6.0)
    tetrahedron.invert()
    source = MeshData.of(trimesh.util.concatenate((outer, tetrahedron)))
    found = detect_voids(source)
    assert len(found) == 1
    known = replace(found[0], params={**found[0].params, "local_search_radius": 100.0})
    assert known.params["size"] == pytest.approx((6.0, 4.0, 2.0))
    assert known.params["centre"] == pytest.approx((5.0, 5.0, 5.0))
    previous = {known.id: known}
    sine = math.sqrt(0.5)
    changed = source.raw.copy()
    points = np.asarray(source.raw.vertices)
    changed.vertices = np.column_stack(
        ((points[:, 0] - points[:, 1]) * sine, (points[:, 0] + points[:, 1]) * sine, points[:, 2])
    )
    moved = MeshData.of(changed)
    transform = (
        (sine, -sine, 0.0, 0.0),
        (sine, sine, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    assert known.id not in transformed_features(previous, transform).exact
    evaluation = importlib.import_module("app.core.scene.evaluate")
    if recognition == "budget":
        monkeypatch.setattr(evaluation, "FEATURE_LIMIT_COUNT", 1)
    elif recognition == "local":
        monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", 1)
    findings = []
    result = _with_features(
        SceneObject("obj_1", "Tetraeder im Material", moved, features=previous),
        previous,
        Operation(
            id=2,
            op="rotate_object",
            inputs=("obj_1",),
            outputs=("obj_1",),
            params={"axis": "z", "angle": 45.0},
        ),
        lambda _question, choices: choices[0],
        findings,
        transform,
        source.bounds,
    )
    if recognition == "budget":
        assert any(finding.code == "perceive.too_many" for finding in findings)
    elif recognition == "local":
        assert any(finding.code == "perceive.too_large" for finding in findings)
    current = result.features[known.id]
    assert current.kind == "void"
    assert current.params["size"] == pytest.approx((10.0 * sine, 6.0 * sine, 2.0), abs=1e-6)
    assert current.params["centre"] == pytest.approx((0.0, 8.0 * sine, 5.0), abs=1e-6)
    assert current.params["volume"] == pytest.approx(8.0, abs=1e-5)
    assert current.face_indices


@pytest.mark.parametrize("operation", ["scale_object", "fit_to_size"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("replay", ["warm", "reopen", "undo_redo"])
def test_p21_exact_round_selection_survives_retessellation(
    profile, tmp_path, operation, quality, replay
):
    """Neue Manteldreiecke behalten Namen, Maße und Auswahl auch beim Nachspielen."""
    import math

    from app.core.brep.kernel import Solid
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import ResultCache
    from app.core.scene.project import ProjectSources, load, new_project, save

    exact_kernel()
    load_operations()
    project = new_project(profile.printer.id, profile.material.id)
    history = History(project.document)
    history.apply(
        "Rundkörper",
        [
            OperationDraft(
                op="create_brep_cylinder",
                params={"diameter": 6.0, "height": 8.0, "x": 13.0, "y": -7.0, "z": 5.0},
            )
        ],
    )
    before = evaluate(project.document, profile, quality=quality)
    assert before.complete
    original = before.scene.objects["obj_1"]
    assert len(original.features) == 3
    original_triangles = original.mesh.triangle_count
    params = {
        "about": "origin",
        **({"factor": 4.0} if operation == "scale_object" else {"largest": 32.0}),
    }
    history.apply("Vergrößern", [OperationDraft(op=operation, inputs=("obj_1",), params=params)])
    cache = ResultCache()
    first = evaluate(project.document, profile, cache=cache, quality=quality)
    assert first.complete
    if replay != "warm":
        project = load(save(project, tmp_path / "rundkoerper.p3d"))
        cache = ResultCache()
        if replay == "undo_redo":
            history = History(project.document)
            history.undo()
            undone = evaluate(project.document, profile, quality=quality)
            assert undone.complete
            restored = undone.scene.objects["obj_1"]
            assert restored.kind == "brep"
            assert restored.mesh.bounds.size == pytest.approx((6.0, 6.0, 8.0), abs=1e-6)
            assert set(restored.features) == set(original.features)
            history.redo()
    result = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, quality=quality
    )
    assert result.complete
    if replay == "warm":
        assert cache.statistics.hits >= 2
        assert cache.statistics.disk_hits == 0
    final = result.scene.objects["obj_1"]
    assert final.kind == "brep"
    assert isinstance(final.mesh, Solid)
    assert final.mesh.is_closed
    assert final.mesh.solid_count == 1
    assert final.mesh.volume == pytest.approx(math.pi * 12.0**2 * 32.0, abs=1e-7)
    assert final.mesh.bounds.centre == pytest.approx((52.0, -28.0, 36.0), abs=1e-6)
    assert final.mesh.bounds.size == pytest.approx((24.0, 24.0, 32.0), abs=1e-6)
    assert final.mesh.triangle_count > original_triangles
    assert set(final.features) == set(original.features)
    assert not any(f.code == "evaluate.exact_became_mesh" for f in result.scene.report.findings)

    raw = final.mesh.raw
    for name, feature in final.features.items():
        assert feature.created_by == original.features[name].created_by
        assert feature.provenance == original.features[name].provenance
        assert feature.face_indices
        points = raw.vertices[raw.faces[list(feature.face_indices)]].reshape(-1, 3)
        if feature.kind == "pin":
            assert feature.params["diameter"] == pytest.approx(24.0, abs=1e-8)
            assert feature.params["centre"] == pytest.approx((52.0, -28.0, 36.0), abs=1e-6)
            assert np.linalg.norm(points[:, :2] - (52.0, -28.0), axis=1) == pytest.approx(
                12.0, abs=1e-6
            )
        else:
            assert feature.kind == "face"
            height = 52.0 if feature.params["normal"][2] > 0 else 20.0
            assert feature.params["area"] == pytest.approx(math.pi * 12.0**2, abs=1e-7)
            assert points[:, 2] == pytest.approx(height, abs=1e-6)
    assert original.mesh.bounds.size == pytest.approx((6.0, 6.0, 8.0), abs=1e-6)
    assert original.mesh.triangle_count == original_triangles


def test_p02_split_conversion_names_both_descendants(document, profile):
    """Eine behaltene Kennung unterschlägt nicht den zweiten vernetzten Teilkörper."""
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.cache import ResultCache

    exact_kernel()
    history = _p21_boolean_history(document, ("brep", "brep"))
    history.change_params(document.ops[1].id, {"x": 100.0})
    history.apply(
        "Zwei getrennte Volumen",
        [OperationDraft(op="union_objects", inputs=("obj_1", "obj_2"))],
    )
    before = evaluate(document, profile, quality="fine")
    assert before.complete
    assert before.scene.objects["obj_1"].kind == "brep"
    assert before.scene.objects["obj_1"].mesh.component_count == 2
    history.apply(
        "In Einzelteile zerlegen",
        [OperationDraft(op="split_bodies", inputs=("obj_1",), params={"count": 2})],
    )
    cache = ResultCache()
    for _ in range(2):
        result = evaluate(document, profile, cache=cache, quality="fine")
        assert result.complete, result.scene.report.findings
        assert set(result.scene.objects) == {"obj_1", "obj_3"}
        assert all(entry.kind == "mesh" for entry in result.scene.objects.values())
        assert sorted(
            entry.mesh.volume for entry in result.scene.objects.values()
        ) == pytest.approx((8000.0, 24000.0), abs=1e-6)
        notices = [
            f for f in result.scene.report.findings if f.code == "evaluate.exact_became_mesh"
        ]
        assert len(notices) == 1
        assert notices[0].values["input_object"] == "obj_1"
        assert notices[0].values["outputs"] == "obj_1 obj_3"


def _p21_boolean_history(document, kinds, third=None):
    """Analytische Quader mit belegtem Überlappungsvolumen in den echten Verlauf setzen."""
    from app.core.scene import History, OperationDraft

    load_operations()
    dimensions = [
        {"width": 40.0, "depth": 30.0, "height": 20.0},
        {"width": 20.0, "depth": 20.0, "height": 20.0, "x": 20.0},
    ]
    if third is not None:
        dimensions.append(third)
    assert len(kinds) == len(dimensions)
    history = History(document)
    history.apply(
        "Überlappende Quader",
        [
            OperationDraft(
                op="create_brep_box" if kind == "brep" else "create_box",
                params={**size, "name": chr(ord("A") + index)},
            )
            for index, (kind, size) in enumerate(zip(kinds, dimensions, strict=True))
        ],
    )
    return history


@pytest.mark.parametrize(
    ("kinds", "expected_kind"),
    [
        (("mesh", "mesh"), "mesh"),
        (("mesh", "brep"), "mesh"),
        (("brep", "mesh"), "mesh"),
        (("brep", "brep"), "brep"),
    ],
)
@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize(
    ("op", "reverse", "expected_volume", "expected_bounds"),
    [
        ("union_objects", False, 28000.0, ((-20.0, -15.0, 0.0), (30.0, 15.0, 20.0))),
        ("subtract_objects", False, 20000.0, ((-20.0, -15.0, 0.0), (20.0, 15.0, 20.0))),
        ("subtract_objects", True, 4000.0, ((20.0, -10.0, 0.0), (30.0, 10.0, 20.0))),
        ("intersect_objects", False, 4000.0, ((10.0, -10.0, 0.0), (20.0, 10.0, 20.0))),
    ],
)
def test_p21_boolean_kind_matrix(
    document, profile, kinds, expected_kind, quality, op, reverse, expected_volume, expected_bounds
):
    """Beide Auswahlreihenfolgen rechnen wirklich und erhalten das erklärte Ergebnis."""
    from app.core.brep.kernel import Solid
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.cache import ResultCache

    exact_kernel()
    history = _p21_boolean_history(document, kinds)
    inputs = ("obj_2", "obj_1") if reverse else ("obj_1", "obj_2")
    history.apply("Boolesche Änderung", [OperationDraft(op=op, inputs=inputs)])
    cache = ResultCache()
    for _ in range(2):
        result = evaluate(document, profile, quality=quality, cache=cache)
        assert result.complete, result.scene.report.findings
        assert set(result.scene.objects) == {inputs[0]}
        final = result.scene.objects[inputs[0]]
        assert final.name == ("B" if reverse else "A")
        assert final.kind == expected_kind
        assert isinstance(final.mesh, Solid if expected_kind == "brep" else MeshData)
        assert final.mesh.is_watertight
        assert final.mesh.component_count == 1
        assert final.mesh.volume == pytest.approx(expected_volume, abs=1e-6)
        assert final.mesh.bounds.minimum == pytest.approx(expected_bounds[0], abs=1e-6)
        assert final.mesh.bounds.maximum == pytest.approx(expected_bounds[1], abs=1e-6)
    assert cache.statistics.hits >= 3


@pytest.mark.parametrize(
    "kinds",
    [(a, b, c) for a in ("mesh", "brep") for b in ("mesh", "brep") for c in ("mesh", "brep")],
)
@pytest.mark.parametrize(
    ("op", "third", "expected_volume"),
    [
        ("union_objects", {"width": 20.0, "depth": 10.0, "height": 20.0, "x": 30.0}, 30000.0),
        ("subtract_objects", {"width": 10.0, "depth": 10.0, "height": 20.0, "x": -10.0}, 18000.0),
        ("intersect_objects", {"width": 10.0, "depth": 10.0, "height": 20.0, "x": 20.0}, 1000.0),
    ],
)
def test_p21_boolean_third_input_changes_the_result(
    document, profile, kinds, op, third, expected_volume
):
    """Der dritte Körper verändert das Ergebnis in jeder Kombination der beiden Kerne."""
    from app.core.brep.kernel import Solid
    from app.core.scene import OperationDraft, evaluate

    exact_kernel()
    history = _p21_boolean_history(document, kinds, third)
    history.apply("Drei Körper", [OperationDraft(op=op, inputs=("obj_1", "obj_2", "obj_3"))])
    result = evaluate(document, profile, quality="fine")
    assert result.complete, result.scene.report.findings
    assert set(result.scene.objects) == {"obj_1"}
    final = result.scene.objects["obj_1"]
    expected_kind = "brep" if kinds == ("brep", "brep", "brep") else "mesh"
    assert final.kind == expected_kind
    assert isinstance(final.mesh, Solid if expected_kind == "brep" else MeshData)
    assert final.mesh.is_watertight
    assert final.mesh.component_count == 1
    assert final.mesh.volume == pytest.approx(expected_volume, abs=1e-6)


@pytest.mark.parametrize("kinds", [(a, b) for a in ("mesh", "brep") for b in ("mesh", "brep")])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_p21_blended_union_states_and_measures_its_raster(document, profile, kinds, quality):
    """Der vierte Boolesche Weg bleibt als Rasterverfahren kenntlich und verändert die Kehle."""
    from app.core.scene import OperationDraft, evaluate

    exact_kernel()
    history = _p21_boolean_history(document, kinds)
    volumes = []
    for radius in (0.0, 4.0):
        history.apply(
            "Weicher Übergang",
            [
                OperationDraft(
                    op="blend_union", inputs=("obj_1", "obj_2"), params={"radius": radius}
                )
            ],
        )
        result = evaluate(document, profile, quality=quality)
        assert result.complete, result.scene.report.findings
        assert set(result.scene.objects) == {"obj_1"}
        final = result.scene.objects["obj_1"]
        assert final.kind == "mesh"
        assert isinstance(final.mesh, MeshData)
        assert final.mesh.is_watertight
        assert final.mesh.component_count == 1
        raster = [f for f in result.scene.report.findings if f.code == "blend.rastered"]
        assert len(raster) == 1
        assert raster[0].values["radius_mm"] == radius
        grid = raster[0].values["grid_mm"]
        assert grid > 0.0
        assert np.all(
            np.asarray(final.mesh.bounds.minimum) >= np.array((-20.0, -15.0, 0.0)) - radius - grid
        )
        assert np.all(
            np.asarray(final.mesh.bounds.maximum) <= np.array((30.0, 15.0, 20.0)) + radius + grid
        )
        volumes.append(final.mesh.volume)
        history.undo()
    assert volumes[0] == pytest.approx(28000.0, rel=0.015)
    assert volumes[1] > volumes[0] + 20.0


@pytest.mark.parametrize("kinds", [(a, b) for a in ("mesh", "brep") for b in ("mesh", "brep")])
@pytest.mark.parametrize(
    "op", ["union_objects", "subtract_objects", "intersect_objects", "blend_union"]
)
def test_p02_boolean_conversion_names_every_exact_input(document, profile, kinds, op):
    """Auch das zweite exakte Werkzeug erhält seinen eigenen, eindeutigen Umwandlungsbefund."""
    from app.core.registry import REGISTRY
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.cache import ResultCache

    exact_kernel()
    history = _p21_boolean_history(document, kinds)
    history.apply("Boolesche Änderung", [OperationDraft(op=op, inputs=("obj_1", "obj_2"))])
    cache = ResultCache()
    expected = (
        {
            f"obj_{index}": chr(ord("A") + index - 1)
            for index, kind in enumerate(kinds, 1)
            if kind == "brep"
        }
        if op == "blend_union" or kinds != ("brep", "brep")
        else {}
    )
    for _ in range(2):
        result = evaluate(document, profile, quality="fine", cache=cache)
        assert result.complete, result.scene.report.findings
        notices = [
            f for f in result.scene.report.findings if f.code == "evaluate.exact_became_mesh"
        ]
        assert len(notices) == len(expected)
        assert {
            f.values.get("input_object"): f.values.get("input_name") for f in notices
        } == expected
        assert all(f.object_id == "obj_1" and f.values["object"] == "obj_1" for f in notices)
        assert all(f.op_id == document.ops[-1].id and f.values["op"] == op for f in notices)
        assert all(f.severity == "info" for f in notices)
        assert all(str(REGISTRY.get(op).title) in str(f.message) for f in notices)
        assert all(str(f.values["input_name"]) in str(f.message) for f in notices)
        assert all("Rückgängig" in str(f.message) for f in notices)


@pytest.mark.parametrize("kinds", [(a, b) for a in ("mesh", "brep") for b in ("mesh", "brep")])
@pytest.mark.parametrize("op", ["subtract_objects", "intersect_objects"])
def test_p21_empty_boolean_preserves_both_inputs(document, profile, kinds, op):
    """Leere Ergebnisse halten mit Handlungsvorschlag an und verbrauchen keinen Körper."""
    from app.core.scene import OperationDraft, evaluate

    exact_kernel()
    history = _p21_boolean_history(document, kinds)
    history.change_params(
        document.ops[1].id,
        {
            "width": 100.0,
            "depth": 100.0,
            "height": 100.0,
            "x": 0.0 if op == "subtract_objects" else 200.0,
        },
    )
    initial = evaluate(document, profile, quality="fine")
    assert initial.complete
    history.apply("Leeres Ergebnis", [OperationDraft(op=op, inputs=("obj_1", "obj_2"))])
    result = evaluate(document, profile, quality="fine")
    assert not result.complete
    assert result.stopped_at == document.ops[-1].id
    assert set(result.scene.objects) == {"obj_1", "obj_2"}
    for name, original in initial.scene.objects.items():
        final = result.scene.objects[name]
        assert final.kind == original.kind
        assert final.mesh.volume == pytest.approx(original.mesh.volume, abs=1e-6)
        assert final.mesh.bounds == original.mesh.bounds
    errors = [f for f in result.scene.report.findings if f.severity == "error"]
    assert len(errors) == 1
    assert errors[0].suggestions
    assert not any(f.code == "evaluate.exact_became_mesh" for f in result.scene.report.findings)


def test_p02_explicit_conversion_has_one_complete_notice(document, profile):
    """Die Auswertung ergänzt den direkten Kernbefund, ohne die Aussage zu verdoppeln."""
    from app.core.registry import REGISTRY
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import ResultCache

    exact_kernel()
    history = History(document)
    history.apply(
        "Grundkörper und Umwandlung",
        [
            OperationDraft(op="create_brep_box", params={"name": "Gehäuse"}),
            OperationDraft(op="brep_to_mesh", inputs=("obj_1",)),
        ],
    )
    cache = ResultCache()
    for _ in range(2):
        result = evaluate(document, profile, cache=cache)
        assert result.complete
        notices = [f for f in result.scene.report.findings if f.converts_exact_body]
        assert len(notices) == 1
        assert notices[0].values["input_object"] == "obj_1"
        assert notices[0].op_id == 2
        text = str(notices[0].message)
        assert str(REGISTRY.get("brep_to_mesh").title) in text
        assert "Gehäuse" in text and "Rückgängig" in text
        assert "bleiben bearbeitbar" in text


def test_p21_an_unchanged_exact_body_keeps_a_partial_surface_feature():
    """Ein unveränderter Vorschauwert verlangt keine neue Flächenzuordnung."""
    import dataclasses

    from app.core.brep.edit import box
    from app.core.brep.features import features_of
    from app.core.geom.transform import moved_object
    from app.core.types import SceneObject

    exact_kernel()
    solid = box(20.0, 16.0, 10.0)
    full = next(feature for feature in features_of(solid).values() if feature.kind == "face")
    partial = dataclasses.replace(full, id="selected_region", face_indices=full.face_indices[:1])
    source = SceneObject(
        id="obj_1", name="Teilfläche", mesh=solid, kind="brep", features={partial.id: partial}
    )
    result = moved_object(source, np.eye(4))
    assert result.mesh is source.mesh
    assert result.features == source.features
    assert source.features[partial.id].face_indices == full.face_indices[:1]
