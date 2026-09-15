"""Projektmaße einer Bausteinskizze erreichen Vorschau und echten Bau (§24)."""

from __future__ import annotations

from typing import cast

import pytest

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.geom.sketch_solid import extrude_profile
from app.core.knowledge.parts import ops
from app.core.knowledge.parts.build import face
from app.core.knowledge.parts.registry import PartRegistry, PartSpec
from app.core.knowledge.profiles import make_profile
from app.core.registry import Registry, op_params, param, validate
from app.core.sketch import serialize
from app.core.sketch.profile import profile_of
from app.core.sketch.solver import solve_sketch
from app.core.types import BaseParams, OpContext, Parameter, PartResult, PlaneFrame, Scene
from tests.test_sketch import rectangle


@op_params
class DrawnPartParams(BaseParams):
    outline: str = param(title="Zeichnung", kind="sketch", default="")
    note: str = param(title="Text", default="=@unchanged")


def drawn_part(params: BaseParams) -> PartResult:
    """Ein eigenes Prisma misst die gelöste Kontur, ohne Projektkontext zu kennen."""
    values = cast(DrawnPartParams, params)
    sketch = serialize.sketch_from_text(values.outline)
    contour = profile_of(solve_sketch(sketch))
    frame = PlaneFrame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    raw = extrude_profile(contour, 4.0, frame)
    top = face(
        "top",
        float(raw.extents[0] * raw.extents[1]),
        (float(raw.centroid[0]), float(raw.centroid[1]), 4.0),
    )
    return PartResult(mesh=MeshData.of(raw), features=dict([top]))


@pytest.fixture
def spec() -> PartSpec:
    return PartSpec(
        "drawn_context",
        "Gezeichnetes Prüfteil",
        "structure",
        DrawnPartParams,
        drawn_part,
        standalone=True,
        features=("top",),
    )


@pytest.fixture
def drawing() -> str:
    return serialize.sketch_to_text(rectangle("=@outer/@count", "@inner"))


def test_temporary_sketch_values_keep_original_geometry_and_expressions(drawing: str) -> None:
    """Nur die Bedingungen werden numerisch; der Löser bleibt für die Geometrie zuständig."""
    original = serialize.sketch_from_text(drawing)
    resolved = serialize.resolve_sketch_values(drawing, {"outer": 60, "count": 2, "inner": 12})
    changed = serialize.sketch_from_text(resolved)
    assert changed.elements == original.elements
    assert changed.plane == original.plane
    assert serialize.sketch_parameter_references(resolved) == frozenset()
    assert serialize.sketch_parameter_references(drawing) == {"outer", "count", "inner"}
    assert sorted(c.value for c in changed.constraints if c.value) == ["12.0", "30.0"]


@pytest.mark.parametrize("parameters", [None, {}, {"outer": 60, "count": 2}])
def test_missing_sketch_parameters_are_not_assumed_zero(drawing: str, parameters) -> None:
    with pytest.raises(ValidationError) as caught:
        serialize.resolve_sketch_values(drawing, parameters)
    assert caught.value.constraint == "unknown_parameter"
    assert caught.value.suggestions


def test_literal_sketch_needs_no_project_context() -> None:
    drawing = serialize.sketch_to_text(rectangle("3*4", "5"))
    resolved = serialize.sketch_from_text(serialize.resolve_sketch_values(drawing))
    assert sorted(c.value for c in resolved.constraints if c.value) == ["12.0", "5.0"]


def test_part_and_placement_share_the_resolved_measure(spec: PartSpec, drawing: str) -> None:
    profile = make_profile("centauri-carbon-2", "petg")
    values = {"outline": drawing}
    params = validate(ops.build_params(spec, standalone=True), values)
    context = {"outer": 60.0, "count": 2.0, "inner": 12.0}
    built_params, result = ops._built_part(spec, params, profile, "fine", parameters=context)
    preview, extra = ops.placement_tools(spec, values, profile, standalone=True, parameters=context)
    assert result.mesh.raw.extents == pytest.approx((30, 12, 4))
    assert preview.raw.extents == pytest.approx((30, 12, 4))
    assert result.mesh.volume == pytest.approx(1440)
    assert preview.volume == pytest.approx(result.mesh.volume)
    assert extra is None
    assert params.outline == drawing
    assert built_params.note == "=@unchanged"
    assert built_params.outline != drawing


def test_surface_placement_passes_the_sketch_context(
    spec: PartSpec, drawing: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Platzierungsanschluss liest dieselben gebundenen Maße wie der echte Baustein."""
    from app.core.scene import placement

    registry = Registry()
    parts = PartRegistry()
    parts.register(spec)
    ops.register_all(parts, registry)
    operation = registry.get("create_drawn_context")
    monkeypatch.setattr(ops, "part_of", lambda name: spec if name == operation.name else None)
    profile = make_profile("centauri-carbon-2", "petg")
    values = {"outline": drawing}
    context = {"outer": 60.0, "count": 2.0, "inner": 12.0}
    tool = placement.prepare_tool(operation, values, profile, parameters=context)
    assert tool.mesh.bounds.size == pytest.approx((30, 12, 4))
    context["outer"] = 80.0
    changed = placement.placement_tool(operation, values, profile, parameters=context)
    assert changed.bounds.size == pytest.approx((40, 12, 4))
    assert values["outline"] == drawing


def test_registered_creator_reads_resolved_scene_parameters(spec: PartSpec, drawing: str) -> None:
    """Der echte Erzeuger muss auch abhängige Projektwerte vor dem PartFn auflösen."""
    from app.core.scene.cancel import NeverCancelled

    registry = Registry()
    parts = PartRegistry()
    parts.register(spec)
    ops.register_all(parts, registry)
    operation = registry.get("create_drawn_context")
    context = OpContext(
        scene=Scene(
            parameters={
                "base": Parameter("base", 30),
                "outer": Parameter("outer", 0, expression="=@base*2"),
                "count": Parameter("count", 2),
                "inner": Parameter("inner", 12),
            }
        ),
        inputs=[],
        params=validate(operation.params, {"outline": drawing}),
        profile=make_profile("centauri-carbon-2", "petg"),
        quality="fine",
        seed=None,
        progress=lambda *_: None,
        ask=lambda *_: "",
        cancelled=NeverCancelled(),
    )
    result = operation.fn(context)
    assert result.outputs[0].mesh.raw.extents == pytest.approx((30, 12, 4))
    assert context.params.outline == drawing


def test_parameter_change_invalidates_part_cache_and_keeps_usage(
    spec: PartSpec, drawing: str, document
) -> None:
    """Ein frei benannter Skizzenparameter liest Maß, Cache und Verwendung gemeinsam."""
    from app.core.scene.cache import ResultCache
    from app.core.scene.evaluate import evaluate
    from app.core.scene.parameter_usage import ParameterUse
    from app.core.types import Operation

    registry = Registry()
    parts = PartRegistry()
    parts.register(spec)
    ops.register_all(parts, registry)
    document.parameters = {
        "outer": Parameter("outer", 60),
        "count": Parameter("count", 2),
        "inner": Parameter("inner", 12),
    }
    document.ops = [
        Operation(1, "create_drawn_context", outputs=("obj_1",), params={"outline": drawing})
    ]
    profile = make_profile("centauri-carbon-2", "petg")
    cache = ResultCache()
    first = evaluate(document, profile, registry=registry, cache=cache)
    assert first.complete, first.scene.report.findings
    assert first.scene.objects["obj_1"].mesh.raw.extents == pytest.approx((30, 12, 4))
    assert first.parameter_usage == {
        name: (ParameterUse(1, "outline"),) for name in ("outer", "count", "inner")
    }
    assert evaluate(document, profile, registry=registry, cache=cache).complete
    assert cache.statistics.hits == 1
    document.parameters["outer"] = Parameter("outer", 80)
    second = evaluate(document, profile, registry=registry, cache=cache)
    assert second.complete, second.scene.report.findings
    assert second.scene.objects["obj_1"].mesh.raw.extents == pytest.approx((40, 12, 4))
    assert document.ops[0].params["outline"] == drawing
