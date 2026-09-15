"""Projektparameter wirken nur über lesende Felder im aktuellen Operationsstapel."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.core.bootstrap import load_operations
from app.core.errors import AppError, ValidationError
from app.core.scene.parameter_usage import ParameterUse, parameter_uses
from app.core.sketch.serialize import sketch_to_text
from app.core.types import Document, Operation, Parameter, Sketch, SketchConstraint


@pytest.fixture(autouse=True)
def operations() -> None:
    load_operations()


def _parameter(name: str, expression: str | None = None) -> Parameter:
    return Parameter(name=name, value=10.0, expression=expression)


def test_parameter_chains_without_an_operation_are_unused(document: Document) -> None:
    document.parameters = {
        "width": _parameter("width"),
        "half": _parameter("half", "=@width/2"),
        "quarter": _parameter("quarter", "=@half/2"),
    }
    assert parameter_uses(document) == {"width": (), "half": (), "quarter": ()}


def test_evaluation_carries_usage_without_replacing_a_stopped_result(document, profile) -> None:
    """Auch ein angehaltener Lauf unterscheidet unbekannte von ungenutzten Maßen."""
    from app.core.scene.evaluate import evaluate

    document.parameters = {"width": _parameter("width")}
    document.ops = [
        Operation(id=1, op="create_box", params={"width": "=@width"}, outputs=("obj_1",))
    ]
    result = evaluate(document, profile)
    assert result.complete and result.parameter_usage_error is None
    assert result.parameter_usage == {"width": (ParameterUse(1, "width"),)}
    document.ops[0] = Operation(
        id=1, op="create_box", params={"width": "=@missing"}, outputs=("obj_1",)
    )
    broken = evaluate(document, profile)
    assert broken.stopped_at == 1
    assert broken.parameter_usage is None
    assert isinstance(broken.parameter_usage_error, AppError)
    assert broken.scene.report.findings


def test_direct_fields_and_transitive_parameters_keep_their_locations(document: Document) -> None:
    document.parameters = {
        "width": _parameter("width"),
        "half": _parameter("half", "=@width/2"),
        "quarter": _parameter("quarter", "=@half/2"),
        "spare": _parameter("spare", "=@width/3"),
    }
    document.ops = [
        Operation(
            id=7,
            op="create_box",
            params={"width": "=@half+@width+@half", "height": "=@quarter/@quarter"},
        ),
        Operation(id=3, op="translate_object", params={"dx": "@half"}),
    ]
    before = deepcopy(document)

    uses = parameter_uses(document)

    assert uses["width"] == (
        ParameterUse(7, "height", direct=False, via=("quarter",)),
        ParameterUse(7, "width", direct=True, via=("half",)),
        ParameterUse(3, "dx", direct=False, via=("half",)),
    )
    assert uses["half"] == (
        ParameterUse(7, "height", direct=False, via=("quarter",)),
        ParameterUse(7, "width"),
        ParameterUse(3, "dx"),
    )
    assert uses["quarter"] == (ParameterUse(7, "height"),)
    assert uses["spare"] == ()
    assert document == before


def test_text_containing_an_at_sign_does_not_become_an_expression(document: Document) -> None:
    document.parameters = {"width": _parameter("width"), "name": _parameter("name")}
    document.ops = [Operation(id=1, op="create_box", params={"name": "Teil @name"})]
    assert parameter_uses(document) == {"width": (), "name": ()}


def test_organizer_dimensions_read_only_inside_the_layout_invalidate_cached_geometry(
    document: Document, profile
) -> None:
    """Ein Fachmaß bleibt wirksam, auch wenn kein gewöhnliches Zahlenfeld es liest."""
    from dataclasses import replace

    from app.core.organizer.serialize import grid_layout, layout_to_text
    from app.core.scene.cache import ResultCache
    from app.core.scene.evaluate import evaluate

    document.parameters = {"inner": _parameter("inner"), "unused": _parameter("unused")}
    layout = layout_to_text(
        grid_layout(1, 2, cell_width="=@inner", cell_depth=20, wall=3, radius=0, basis="inner")
    )
    document.ops = [
        Operation(
            id=1,
            op="create_organizer",
            params={
                "layout": layout,
                "wall": 3,
                "height": 20,
                "floor": 2,
                "radius": 0,
            },
            outputs=("obj_1",),
        )
    ]
    cache = ResultCache()
    first = evaluate(document, profile, cache=cache)
    assert first.complete
    assert first.scene.objects["obj_1"].mesh.bounds.size[0] == pytest.approx(29.0)
    assert first.parameter_usage == {
        "inner": (ParameterUse(1, "layout"),),
        "unused": (),
    }
    document.parameters["inner"] = replace(document.parameters["inner"], value=20.0)
    second = evaluate(document, profile, cache=cache)
    assert second.complete
    assert second.scene.objects["obj_1"].mesh.bounds.size[0] == pytest.approx(49.0)
    assert first.object_hashes["obj_1"] != second.object_hashes["obj_1"]
    document.parameters["inner"] = replace(document.parameters["inner"], value=10.0)
    restored = evaluate(document, profile, cache=cache)
    assert restored.complete
    assert restored.object_hashes["obj_1"] == first.object_hashes["obj_1"]


def test_sketch_and_pose_share_the_nested_reference_collectors(document: Document) -> None:
    document.parameters = {
        "width": _parameter("width"),
        "angle": _parameter("angle"),
        "half": _parameter("half", "=@width/2"),
        "unused": _parameter("unused"),
    }
    sketch = Sketch(
        plane="plane:xy",
        elements=(),
        constraints=(SketchConstraint(kind="distance", targets=(0, 1), value="=@half + 2"),),
    )
    document.ops = [
        Operation(id=4, op="sketch_extrude", params={"sketch": sketch_to_text(sketch)}),
        Operation(
            id=9,
            op="pose_armature",
            params={
                "armature": '[{"n":"joint","h":[0,0,0],"t":[0,0,10],"p":""}]',
                "pose": '{"joint":[0,"=@angle + @half",0]}',
            },
        ),
    ]

    uses = parameter_uses(document)

    assert uses["width"] == (
        ParameterUse(4, "sketch", direct=False, via=("half",)),
        ParameterUse(9, "pose", direct=False, via=("half",)),
    )
    assert uses["half"] == (ParameterUse(4, "sketch"), ParameterUse(9, "pose"))
    assert uses["angle"] == (ParameterUse(9, "pose"),)
    assert uses["unused"] == ()


@pytest.mark.parametrize(
    ("operation", "field", "value"),
    [
        ("create_box", "width", "=@width +"),
        ("sketch_extrude", "sketch", "{kaputt"),
        (
            "sketch_extrude",
            "sketch",
            '{"constraints":[{"kind":"distance","targets":[0],"value":"=@width +"}]}',
        ),
        ("pose_armature", "pose", "{kaputt"),
        ("pose_armature", "pose", '{"joint": null}'),
        ("pose_armature", "pose", '{"joint":[0,"=@width +",0]}'),
    ],
)
def test_unreadable_fields_cannot_claim_parameters_are_unused(
    document: Document, operation: str, field: str, value: str
) -> None:
    document.parameters = {"width": _parameter("width")}
    document.ops = [Operation(id=1, op=operation, params={field: value})]
    with pytest.raises(AppError):
        parameter_uses(document)


@pytest.mark.parametrize("expression", ["=@missing", "=@loop"])
def test_invalid_parameter_dependencies_are_not_reported_as_unused(
    document: Document, expression: str
) -> None:
    document.parameters = {"loop": _parameter("loop", expression)}
    with pytest.raises(ValidationError):
        parameter_uses(document)


def test_an_operation_cannot_hide_an_unknown_parameter(document: Document) -> None:
    document.ops = [Operation(id=2, op="create_box", params={"width": "=@missing"})]
    with pytest.raises(ValidationError) as caught:
        parameter_uses(document)
    assert caught.value.values["missing"] == ["missing"]
    assert caught.value.field == "ops.2.width"


def test_an_unknown_operation_does_not_claim_to_have_no_parameter_uses(document: Document) -> None:
    document.ops = [Operation(id=1, op="unknown", params={"nested": '{"value":"@width"}'})]
    with pytest.raises(AppError):
        parameter_uses(document)


def test_a_non_text_sketch_is_not_reported_as_unused(document: Document) -> None:
    document.parameters = {"width": _parameter("width")}
    document.ops = [Operation(id=1, op="sketch_extrude", params={"sketch": {"value": "@width"}})]
    with pytest.raises(ValidationError):
        parameter_uses(document)


def test_undo_removes_the_last_operation_that_reads_a_parameter(document: Document) -> None:
    from app.core.scene.history import History, OperationDraft

    document.parameters = {"width": _parameter("width")}
    history = History(document)
    history.apply("Körper", [OperationDraft(op="create_box", params={"width": "@width"})])
    assert parameter_uses(document)["width"] == (ParameterUse(1, "width"),)

    history.undo()

    assert parameter_uses(document)["width"] == ()


def test_blank_poses_are_valid_and_do_not_use_parameters(document: Document) -> None:
    document.parameters = {"width": _parameter("width")}
    document.ops = [Operation(id=1, op="pose_armature", params={"pose": "  "})]
    assert parameter_uses(document)["width"] == ()


def test_each_nested_payload_is_parsed_once(
    document: Document, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from app.core.scene.evaluate import nested_references

    nested_references(strict=True)
    document.parameters = {"width": _parameter("width")}
    sketch = '{"constraints":[{"kind":"distance","targets":[0],"value":"@width"}]}'
    pose = '{"joint":[0,"@width",0]}'
    document.ops = [
        Operation(id=1, op="sketch_extrude", params={"sketch": sketch}),
        Operation(id=2, op="pose_armature", params={"armature": "[]", "pose": pose}),
    ]
    reads = []
    original = json.loads

    def counted(text, *args, **kwargs):
        reads.append(text)
        return original(text, *args, **kwargs)

    monkeypatch.setattr(json, "loads", counted)

    uses = parameter_uses(document)

    assert uses["width"] == (ParameterUse(1, "sketch"), ParameterUse(2, "pose"))
    assert reads == [sketch, "[]", pose]
