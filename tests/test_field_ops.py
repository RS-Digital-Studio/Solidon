"""Feldschnitt gegen unabhängige Volumen, Schnittlagen und tatsächliche Bohrungen."""

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.brep import profiles
from app.core.errors import ValidationError
from app.core.geom.field_ops import FieldCutParams, field_cut
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import bore_diameter
from app.core.knowledge.profiles import for_object
from app.core.scene.cancel import NeverCancelled
from app.core.sketch import shapes
from app.core.sketch.profile import profile_of
from app.core.sketch.serialize import sketch_to_text
from app.core.sketch.solver import solve_sketch
from app.core.types import OpContext, Parameter, Scene, SceneObject


def source(kind):
    if kind == "mesh":
        raw = trimesh.load_mesh(Path(__file__).parent / "data/meshes/cube_clean.stl")
        return SceneObject(id="body", name="Würfel", mesh=MeshData(raw))
    body = profiles.extrude(profile_of(solve_sketch(shapes.rectangle(20, 20))), 20)
    from app.core.brep.edit import moved

    return SceneObject(id="body", name="Würfel", kind="brep", mesh=moved(body, (0, 0, -10)))


def run(entry, *, profile=None, quality="fine", parameters=None, **changes):
    params = FieldCutParams(
        **{
            "region_sketch": sketch_to_text(shapes.rectangle(18, 18)),
            "diameter": 2,
            "spacing": 6,
            "margin": 1,
            "web": 1,
            "depth": 4,
            **changes,
        }
    )
    return field_cut(
        OpContext(
            scene=Scene(objects={entry.id: entry}, parameters=parameters or {}),
            inputs=[entry],
            params=params,
            profile=profile,
            quality=quality,
            seed=None,
            progress=lambda *args: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_nine_blind_bores_have_the_requested_depth_and_diameter(kind, quality):
    entry = source(kind)
    before = entry.mesh.volume
    result = run(entry, quality=quality)
    output = result.outputs[0]
    area = math.pi if kind == "brep" else 36 * math.sin(math.tau / 72)
    assert before - output.mesh.volume == pytest.approx(9 * area * 4, rel=1e-7)
    assert entry.mesh.volume == pytest.approx(8000)
    assert output.kind == kind
    mesh = as_mesh_data(output.mesh)
    assert mesh.is_watertight and mesh.component_count == 1
    holes = [feature for feature in output.features.values() if feature.kind == "hole"]
    assert len(holes) == 9
    assert all(feature.params["diameter"] == pytest.approx(2) for feature in holes)
    assert all(feature.params["depth"] == pytest.approx(4) for feature in holes)
    assert all(not feature.params["through"] for feature in holes)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("plane", ["plane:xy", "plane:xz", "plane:yz"])
def test_through_field_obeys_the_drawing_plane_and_excluded_area(kind, plane):
    entry = source(kind)
    drawing = replace(shapes.rectangle(18, 18), plane=plane)
    excluded = replace(shapes.circle(3), plane=plane)
    result = run(
        entry,
        region_sketch=sketch_to_text(drawing),
        exclusion_sketch=sketch_to_text(excluded),
        through=True,
    )
    area = math.pi if kind == "brep" else 36 * math.sin(math.tau / 72)
    assert 8000 - result.outputs[0].mesh.volume == pytest.approx(8 * area * 20, rel=1e-7)
    holes = [f for f in result.outputs[0].features.values() if f.kind == "hole"]
    assert len(holes) == 8 and all(f.params["through"] for f in holes)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_height_override_cuts_from_that_plane_instead_of_the_top(kind):
    result = run(source(kind), z=12, depth=4)
    holes = [f for f in result.outputs[0].features.values() if f.kind == "hole"]
    # Zwei Millimeter des Werkzeugs liegen über dem Körper, zwei schneiden ihn.
    assert len(holes) == 9
    assert all(f.params["depth"] == pytest.approx(2) for f in holes)
    area = math.pi if kind == "brep" else 36 * math.sin(math.tau / 72)
    assert 8000 - result.outputs[0].mesh.volume == pytest.approx(9 * area * 2, rel=1e-7)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_compensation_is_explicit_and_uses_the_object_material(kind, profile):
    entry = source(kind)
    entry.material = "pla"
    compensated = run(entry, profile=profile, compensate=True)
    diameter = bore_diameter(2, for_object(profile, entry), True)
    holes = [f for f in compensated.outputs[0].features.values() if f.kind == "hole"]
    assert len(holes) == 9
    assert all(f.params["diameter"] == pytest.approx(diameter) for f in holes)
    assert any(f.code == "bore.compensated" for f in compensated.findings)
    plain = run(entry, profile=profile)
    assert not any(f.code == "bore.compensated" for f in plain.findings)


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("shape", ["slot", "hexagon"])
def test_slot_and_hexagon_remove_their_full_profile(kind, shape):
    result = run(source(kind), shape=shape, slot_length=3)
    circle = math.pi
    area = 2 + circle if shape == "slot" else 3 * math.sqrt(3) / 2
    removed = 8000 - result.outputs[0].mesh.volume
    if kind == "mesh" and shape == "slot":
        # Der vorhandene Fünf-Grad-Vertrag teilt Halbkreise in 36 bis 37 Segmente.
        low = 9 * 4 * (2 + 36 * math.sin(math.pi / 36))
        high = 9 * 4 * (2 + 37 * math.sin(math.pi / 37))
        assert low <= removed <= high
    else:
        assert removed == pytest.approx(9 * area * 4, rel=1e-7)


def test_different_exclusion_plane_and_missing_region_are_actionable_errors():
    entry = source("mesh")
    with pytest.raises(ValidationError) as error:
        run(entry, exclusion_sketch=sketch_to_text(replace(shapes.circle(3), plane="plane:yz")))
    assert error.value.suggestions
    with pytest.raises(ValidationError):
        run(entry, region_sketch="")


def test_region_is_required_by_the_shared_parameter_schema():
    from app.core.registry.params import validate

    assert next(spec for spec in FieldCutParams.spec() if spec.name == "region_sketch").required
    with pytest.raises(ValidationError) as error:
        validate(FieldCutParams, {})
    assert error.value.suggestions
    params = validate(FieldCutParams, {"region_sketch": sketch_to_text(shapes.rectangle(18, 18))})
    assert params.exclusion_sketch == ""


def test_region_expressions_change_the_real_grid_and_preserve_the_drawing():
    sketch = shapes.rectangle(18, 18)
    constraints = tuple(
        replace(c, value="=@width") if c.kind == "distance" and c.targets == (0, 1) else c
        for c in sketch.constraints
    )
    assert any(c.value == "=@width" for c in constraints)
    text = sketch_to_text(replace(sketch, constraints=constraints))
    entry = source("mesh")
    before = run(entry, region_sketch=text, parameters={"width": Parameter("width", 18)})
    after = run(entry, region_sketch=text, parameters={"width": Parameter("width", 10)})
    assert before.outputs[0].mesh.volume < after.outputs[0].mesh.volume
    assert "=@width" in text


def test_a_field_that_only_crosses_an_existing_void_invents_no_hole():
    entry = source("mesh")
    outside = sketch_to_text(
        replace(
            shapes.rectangle(6, 6),
            elements=tuple(
                replace(element, points=tuple((x + 30, y) for x, y in element.points))
                for element in shapes.rectangle(6, 6).elements
            ),
        )
    )
    # Ein unverändertes fixiertes Profil außerhalb; der Solver darf es nicht zurückziehen.
    from app.core.sketch.serialize import sketch_from_text

    drawing = sketch_from_text(outside)
    drawing = replace(drawing, constraints=())
    result = run(entry, region_sketch=sketch_to_text(drawing), through=True)
    assert result.outputs[0].mesh.volume == pytest.approx(entry.mesh.volume)
    assert not any(f.kind == "hole" for f in result.outputs[0].features.values())
    assert any(f.code == "boolean.without_effect" for f in result.findings)


def test_identical_inputs_have_identical_geometry_and_named_features():
    entry = source("mesh")
    left, right = run(entry).outputs[0], run(entry).outputs[0]
    np.testing.assert_array_equal(left.mesh.raw.vertices, right.mesh.raw.vertices)
    np.testing.assert_array_equal(left.mesh.raw.faces, right.mesh.raw.faces)
    assert left.features == right.features


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_cut_uses_both_boolean_stages_and_preserves_the_fallback_report(monkeypatch, quality):
    from app.core.geom import boolean
    from app.core.types import Finding, SolverInfo

    actual = boolean.boolean
    calls = []

    def recorded(kind, meshes, **options):
        calls.append((kind, options))
        result = actual(kind, meshes, **options)
        if kind == "union":
            return replace(
                result,
                solver=SolverInfo("jittered"),
                findings=[Finding(code="test.fallback", severity="warning", message="Testbefund")],
            )
        return result

    monkeypatch.setattr(boolean, "boolean", recorded)
    result = run(source("mesh"), quality=quality)
    assert [kind for kind, _ in calls] == ["union", "difference"]
    assert all(options["quality"] == quality and "cancelled" in options for _, options in calls)
    assert result.solver.strategy == "jittered"
    assert any(f.code == "test.fallback" for f in result.findings)
    assert not any(f.provenance == "generated" for f in result.outputs[0].features.values())


def test_cancel_before_sketch_preparation_does_not_build_geometry(monkeypatch):
    from app.core.errors import OperationCancelled
    from app.core.sketch import ops

    class Cancelled:
        def raise_if_cancelled(self):
            raise OperationCancelled()

    def forbidden(*args, **kwargs):
        pytest.fail("cancelled field reached geometry")

    monkeypatch.setattr(ops, "cut_regions", forbidden)
    entry = source("mesh")
    context = OpContext(
        scene=Scene(objects={entry.id: entry}),
        inputs=[entry],
        params=FieldCutParams(region_sketch=sketch_to_text(shapes.rectangle(18, 18))),
        profile=None,
        quality="fine",
        seed=None,
        progress=lambda *args: None,
        ask=lambda question, choices: choices[0],
        cancelled=Cancelled(),
    )
    with pytest.raises(OperationCancelled):
        field_cut(context)


def test_second_field_does_not_reuse_the_first_fields_feature_names():
    first = run(source("mesh"), spacing=8, origin_x=-2, origin_y=-2).outputs[0]
    second = run(first, spacing=8, origin_x=2, origin_y=2).outputs[0]
    old = {name for name in first.features if name.startswith("field_")}
    new = {name for name in second.features if name.startswith("field_")}
    assert old and new and not old & new


def test_hexagon_choice_ignores_the_inactive_round_hole_compensation(profile):
    entry = source("mesh")
    ordinary = run(entry, shape="hexagon", profile=profile)
    inactive = run(entry, shape="hexagon", profile=profile, compensate=True)
    assert ordinary.outputs[0].mesh.volume == pytest.approx(inactive.outputs[0].mesh.volume)
    assert not any(f.code == "bore.compensated" for f in inactive.findings)


def test_generated_bore_dimensions_survive_evaluation_cache_and_a_parameter_change(profile):
    from app.core.bootstrap import load_operations
    from app.core.scene import ResultCache, evaluate
    from app.core.types import Document, Operation

    load_operations()
    document = Document(
        format_version=25,
        app_version="0.0.0",
        ops=[
            Operation(
                id="box",
                op="create_box",
                inputs=(),
                outputs=("body",),
                params={"width": 20, "depth": 20, "height": 20},
            ),
            Operation(
                id="holes",
                op="field_cut",
                inputs=("body",),
                outputs=("cut",),
                params={
                    "region_sketch": sketch_to_text(shapes.rectangle(18, 18)),
                    "diameter": "=@diameter",
                    "spacing": 6,
                    "depth": 4,
                    "margin": 1,
                    "web": 1,
                },
            ),
        ],
        parameters={"diameter": Parameter("diameter", 2)},
    )
    cache = ResultCache()
    before = evaluate(document, profile=profile, cache=cache)
    remembered = evaluate(document, profile=profile, cache=cache)
    assert before.stopped_at is None and remembered.stopped_at is None
    holes = [f for f in remembered.scene.objects["cut"].features.values() if f.kind == "hole"]
    assert len(holes) == 9
    assert all(f.params["diameter"] == pytest.approx(2) for f in holes)
    document.parameters["diameter"] = Parameter("diameter", 2.5)
    enlarged = evaluate(document, profile=profile, cache=cache)
    assert enlarged.stopped_at is None
    new_holes = [f for f in enlarged.scene.objects["cut"].features.values() if f.kind == "hole"]
    assert len(new_holes) == 9
    assert all(f.params["diameter"] == pytest.approx(2.5) for f in new_holes)
    assert {f.id for f in holes} == {f.id for f in new_holes}


def test_mesh_field_respects_the_shared_limit_for_global_recognition(monkeypatch):
    from app.core.perceive import features, local

    monkeypatch.setattr(local, "FEATURE_LIMIT_TRIANGLES", 1)

    def forbidden(*args, **kwargs):
        pytest.fail("large field forced global recognition")

    monkeypatch.setattr(features, "detect", forbidden)
    result = run(source("mesh"))
    assert result.outputs[0].mesh.volume < 8000
    assert not result.outputs[0].features


def test_field_on_a_tilted_mesh_face_obeys_its_real_frame():
    from app.core.perceive.features import detect

    entry = source("mesh")
    entry.mesh.raw.apply_transform(
        trimesh.transformations.rotation_matrix(math.radians(31), (1, 2, 3))
    )
    entry.features = detect(entry.mesh)
    face = max(
        (f for f in entry.features.values() if f.kind == "face"),
        key=lambda f: f.params["normal"][2],
    )
    drawing = replace(shapes.rectangle(18, 18), plane=f"feature:{entry.id}:{face.id}")
    result = run(entry, region_sketch=sketch_to_text(drawing))
    holes = [f for f in result.outputs[0].features.values() if f.kind == "hole"]
    assert len(holes) == 9
    assert all(f.params["depth"] == pytest.approx(4) for f in holes)
    assert all(
        abs(np.dot(f.params["axis"], face.params["normal"])) == pytest.approx(1) for f in holes
    )
    area = 36 * math.sin(math.tau / 72)
    assert 8000 - result.outputs[0].mesh.volume == pytest.approx(9 * area * 4, rel=1e-7)
