"""Der Behälter-Assistent erzeugt passende Teile und einen rücknehmbaren Entwurf."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.geom import transform
from app.core.geom.boolean import shared_volume
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge import profiles
from app.core.lid_flow import plan_container
from app.core.scene import History, evaluate
from app.core.scene.project import ProjectSources, load, new_project, save
from app.core.types import Parameter


@pytest.fixture(autouse=True)
def available_kernel(request):
    """Der optionale exakte Kern wird nur für die entsprechenden Fälle benötigt."""
    if "kernel" in request.fixturenames and request.getfixturevalue("kernel") == "brep":
        from tests.helpers import exact_kernel

        exact_kernel()


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("shape", ["round", "rectangular"])
@pytest.mark.parametrize("lid", ["push", "screw", "hinged"])
def test_container_is_one_transaction_with_real_fit(kernel: str, shape: str, lid: str) -> None:
    """Zwei geschlossene Körper und belegte Passung, gemeinsam mit allen Hauptmaßen."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    plan = plan_container(document, {"kernel": kernel, "shape": shape, "lid": lid})
    assert not document.ops and not document.parameters and not document.fits
    history = History(document)
    history.apply(plan.title, plan.drafts, changes=plan.changes)
    assert len(document.transactions) == 1
    assert document.parameters
    assert len(document.fits) == 1
    result = evaluate(document, profiles.make_profile("centauri-carbon-2", "petg"))
    assert result.complete, result.scene.report.findings
    assert len(result.scene.objects) == 2
    assert all(body.kind == kernel for body in result.scene.objects.values())
    assert all(as_mesh_data(body.mesh).is_watertight for body in result.scene.objects.values())
    for fit in document.fits:
        assert fit.a.feature_id in result.scene.objects[fit.a.object_id].features
        assert fit.b.feature_id in result.scene.objects[fit.b.object_id].features
    assert not [
        finding for finding in result.scene.report.findings if finding.code.startswith("fit.")
    ]
    history.undo()
    assert not document.ops and not document.parameters and not document.fits
    history.redo()
    repeated = evaluate(document, profiles.make_profile("centauri-carbon-2", "petg"))
    assert repeated.complete
    assert [body.mesh.volume for body in repeated.scene.objects.values()] == pytest.approx(
        [body.mesh.volume for body in result.scene.objects.values()], abs=1e-6
    )


@pytest.mark.parametrize("shape", ["round", "rectangular"])
@pytest.mark.parametrize("lid", ["screw", "push", "hinged"])
def test_container_names_only_active_front_dimensions(shape, lid):
    """Unwirksame und zusätzliche Millimeterfelder bleiben gespeicherte Operationswerte."""
    load_operations()
    document = new_project("centauri-carbon-2", "petg").document
    plan = plan_container(document, {"shape": shape, "lid": lid, "pitch": 4, "rows": 2})
    names = {"container_height", "container_wall"}
    names |= {"container_diameter"} if shape == "round" else {"container_width", "container_depth"}
    assert set(plan.parameters) == names
    assert plan.drafts[0].params["pitch"] == 4
    assert plan.drafts[0].params["rows"] == 2


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("insert", [False, True])
def test_new_container_keeps_explicit_expressions_for_additional_and_inactive_fields(
    kernel, insert, tmp_path
):
    """Zusätzliche Maße behalten ihre Bindung, auch wenn sie erst später wirksam werden."""
    from app.core.scene.history import change_for

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.parameters.update(
        base=Parameter("base", 3.0),
        future_width=Parameter("future_width", 80.0),
        thread_step=Parameter("thread_step", 3.0),
        division_count=Parameter("division_count", 2.0),
    )
    plan = plan_container(
        document,
        {
            "kernel": kernel,
            "lid": "push",
            "insert": insert,
            "floor": "=@base",
            "width": "=@future_width",
            "pitch": "=@thread_step",
            "rows": "=@division_count",
        },
    )
    for name, expression in (
        ("floor", "=@base"),
        ("width", "=@future_width"),
        ("pitch", "=@thread_step"),
    ):
        assert plan.drafts[0].params[name] == expression
    assert plan.drafts[-1].params["rows"] == "=@division_count"
    assert set(plan.parameters) == {"container_diameter", "container_height", "container_wall"}
    history = History(document)
    history.apply(plan.title, plan.drafts, changes=plan.document_change)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    before = evaluate(document, profile)
    assert before.complete, before.scene.report.findings
    history.apply(
        "Bodenstärke", (), changes=change_for(document, parameters={"base": Parameter("base", 5.0)})
    )
    thicker = evaluate(document, profile)
    assert thicker.complete, thicker.scene.report.findings
    assert thicker.scene.objects["obj_1"].mesh.volume > before.scene.objects["obj_1"].mesh.volume
    history.undo()
    assert document.parameters["base"].value == 3.0
    history.redo()
    target = tmp_path / "bound-floor.p3d"
    save(project, target)
    reopened = load(target)
    repeated = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert repeated.complete
    assert reopened.document.ops[0].params["floor"] == "=@base"
    assert repeated.scene.objects["obj_1"].mesh.volume == pytest.approx(
        thicker.scene.objects["obj_1"].mesh.volume, abs=1e-6
    )


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_newly_active_container_dimensions_follow_edit_undo_reload(kernel, tmp_path):
    """Der Formwechsel ergänzt die Hauptmaße ohne alte oder manuelle Parameter zu löschen."""
    from app.core.lid_flow import plan_container_edit

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.parameters["manual"] = Parameter("manual", 123.0)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    history = History(document)
    plan = plan_container(document, {"kernel": kernel, "shape": "round", "lid": "screw"})
    history.apply(plan.title, plan.drafts, changes=plan.document_change)
    before = dict(document.parameters)
    operation = document.ops[0]
    edit = plan_container_edit(
        document, operation, {"shape": "rectangular", "lid": "push", "rows": 2}
    )
    assert dict(document.parameters) == before
    assert edit.values["width"] == "=@container_width"
    assert edit.values["depth"] == "=@container_depth"
    history.change_params(operation.id, edit.values, changes=edit.document_change)
    assert set(document.parameters) == {*before, "container_width", "container_depth"}
    assert all(document.parameters[key] == value for key, value in before.items())
    result = evaluate(document, profile)
    assert result.complete, result.scene.report.findings
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((80, 60, 40), abs=1e-5)
    history.undo()
    assert document.parameters == before and document.ops[0] == operation
    history.redo()
    path = tmp_path / "changed-container.p3d"
    save(project, path)
    reopened = load(path)
    result = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert result.complete
    assert reopened.document.parameters == document.parameters
    back = plan_container_edit(reopened.document, reopened.document.ops[0], {"shape": "round"})
    assert back.values["diameter"] == operation.params["diameter"]
    assert not back.document_change.after.parameters
    History(reopened.document).change_params(
        operation.id, back.values, changes=back.document_change
    )
    assert evaluate(reopened.document, profile, sources=ProjectSources(reopened)).complete


def test_new_container_dimensions_preserve_manual_expressions_and_name_collisions():
    """Eine neue Hauptmaßbindung überschreibt keinen inzwischen belegten Projektnamen."""
    from app.core.lid_flow import plan_container_edit
    from app.core.scene.history import change_for

    load_operations()
    document = new_project("centauri-carbon-2", "petg").document
    history = History(document)
    plan = plan_container(document, {"shape": "round"})
    history.apply(plan.title, plan.drafts, changes=plan.document_change)
    shared = {
        "container_width": Parameter("container_width", 123.0),
        "custom_depth": Parameter("custom_depth", 55.0),
    }
    history.apply("Eigene Maße", (), changes=change_for(document, parameters=shared))
    before = dict(document.parameters)
    operation = document.ops[0]
    edit = plan_container_edit(
        document,
        operation,
        {"shape": "rectangular", "width": 80.0, "depth": "=@custom_depth"},
    )
    assert edit.values["width"] == "=@container_width_2"
    assert edit.values["depth"] == "=@custom_depth"
    history.change_params(operation.id, edit.values, changes=edit.document_change)
    assert set(document.parameters) == {*before, "container_width_2"}
    assert all(document.parameters[key] == value for key, value in before.items())
    history.undo()
    assert document.parameters == before and document.ops[0] == operation
    history.redo()
    assert document.ops[0].params["depth"] == "=@custom_depth"
    assert document.parameters["container_width"] == shared["container_width"]


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_rectangular_body_has_analytic_volume(kernel: str) -> None:
    """80 × 60 × 40 mm außen, 3 mm Wand und Boden, ohne Rundung und Einbauten."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    plan = plan_container(
        project.document, {"kernel": kernel, "shape": "rectangular", "lid": "push", "radius": 0}
    )
    History(project.document).apply(plan.title, plan.drafts, changes=plan.changes)
    result = evaluate(project.document, profiles.make_profile("centauri-carbon-2", "petg"))
    assert result.complete, result.scene.report.findings
    body = result.scene.objects[project.document.ops[0].outputs[0]]
    assert body.mesh.volume == pytest.approx(80 * 60 * 40 - 74 * 54 * 37, abs=1e-5)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("shape", ["round", "rectangular"])
def test_hinged_lid_has_clearance_through_the_whole_motion(kernel: str, shape: str) -> None:
    """Beide Laschen bleiben verbunden und alle Öffnungswinkel frei von Materialkontakt."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    plan = plan_container(
        project.document, {"kernel": kernel, "shape": shape, "lid": "hinged", "opening_angle": 0.0}
    )
    History(project.document).apply(plan.title, plan.drafts, changes=plan.changes)
    result = evaluate(project.document, profile)
    assert result.complete, result.scene.report.findings
    body, cap = result.scene.objects.values()
    assert body.mesh.component_count == cap.mesh.component_count == 1
    from app.core.geom.lid_hinge import HINGE_PIN_FEATURE

    axis = body.features[HINGE_PIN_FEATURE].params["centre"]
    body_mesh, closed = as_mesh_data(body.mesh), as_mesh_data(cap.mesh)
    for angle in (0, 1, 2, 3, 5, 15, 30, 45, 90, 135, 180):
        opened = transform.apply(closed, transform.rotation_about((1.0, 0.0, 0.0), axis, -angle))
        assert shared_volume(body_mesh.raw, opened.raw) == pytest.approx(0.0, abs=1e-5), angle
        assert opened.volume == pytest.approx(closed.volume, abs=1e-5)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("shape", ["round", "rectangular"])
@pytest.mark.parametrize("lid", ["push", "screw", "hinged"])
@pytest.mark.parametrize("insert", [False, True])
def test_compartments_insert_and_sprinkler_holes_remain_separate(
    kernel: str,
    shape: str,
    lid: str,
    insert: bool,
) -> None:
    """Einbauten schneiden weder Boden noch Deckel und ein Einsatz bleibt herausnehmbar."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    plan = plan_container(
        project.document,
        {
            "kernel": kernel,
            "shape": shape,
            "lid": lid,
            "insert": insert,
            "rows": 2,
            "columns": 3,
            "holes": True,
        },
    )
    History(project.document).apply(plan.title, plan.drafts, changes=plan.changes)
    result = evaluate(project.document, profile)
    assert result.complete, result.scene.report.findings
    objects = list(result.scene.objects.values())
    assert len(objects) == (3 if insert else 2)
    assert all(body.mesh.is_watertight and body.mesh.component_count == 1 for body in objects)
    for index, body in enumerate(objects):
        for other in objects[index + 1 :]:
            assert shared_volume(
                as_mesh_data(body.mesh).raw, as_mesh_data(other.mesh).raw
            ) == pytest.approx(0.0, abs=1e-4)
    assert not [
        finding for finding in result.scene.report.findings if finding.code.startswith("fit.")
    ]


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_container_dimensions_survive_cache_save_and_following_operation(
    kernel: str,
    quality: str,
    tmp_path: Path,
) -> None:
    """Benannte Maße erreichen Körper und Deckel trotz warmem Cache und Speicherrundreise."""
    from app.core.geom.mesh import MeshCodec
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.history import OperationDraft

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    project.document.parameters["outside"] = Parameter("outside", 60.0)
    plan = plan_container(
        project.document,
        {
            "kernel": kernel,
            "diameter": "=@outside",
            "lid": "push",
            "insert": True,
            "rows": 2,
            "columns": 2,
        },
    )
    history = History(project.document)
    history.apply(plan.title, plan.drafts, changes=plan.changes)
    cache = ResultCache(disk=DiskCache(directory=tmp_path / "cache", codec=MeshCodec()))
    before = evaluate(project.document, profile, quality=quality, cache=cache)
    assert before.complete, before.scene.report.findings
    project.document.parameters["outside"] = dataclasses.replace(
        project.document.parameters["outside"], value=80.0
    )
    after = evaluate(project.document, profile, quality=quality, cache=cache)
    assert after.complete, after.scene.report.findings
    assert after.scene.objects["obj_1"].mesh.bounds.size[:2] == pytest.approx((80, 80), abs=0.01)
    assert after.scene.objects["obj_1"].mesh.volume > before.scene.objects["obj_1"].mesh.volume
    history.apply(
        "Verschieben", [OperationDraft("translate_object", inputs=("obj_2",), params={"x": 100.0})]
    )
    shifted = evaluate(project.document, profile, quality=quality, cache=cache)
    assert shifted.complete, shifted.scene.report.findings
    path = tmp_path / "container.p3d"
    save(project, path)
    loaded = load(path)
    repeated = evaluate(loaded.document, profile, quality=quality, sources=ProjectSources(loaded))
    assert repeated.complete, repeated.scene.report.findings
    assert {key: body.mesh.volume for key, body in repeated.scene.objects.items()} == pytest.approx(
        {key: body.mesh.volume for key, body in shifted.scene.objects.items()}, abs=1e-5
    )


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize(
    "original,changed", [("screw", "push"), ("push", "hinged"), ("hinged", "screw")]
)
def test_changing_lid_kind_updates_the_fit_and_insert_in_one_undo(kernel, original, changed):
    """Der gespeicherte Folgeschritt und seine Passung folgen der neuen Deckelart."""
    from app.core.lid_flow import change_for_container_edit

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    plan = plan_container(document, {"kernel": kernel, "lid": original, "insert": True})
    assert all(draft.seed is not None for draft in plan.drafts)
    history = History(document)
    history.apply(plan.title, plan.drafts, changes=plan.document_change)
    first = evaluate(document, profile)
    assert first.complete, first.scene.report.findings
    fit_before = document.fits[0]
    operation = document.ops[0]
    values = {**operation.params, "lid": changed}
    change = change_for_container_edit(document, operation, values)
    assert document.fits[0] == fit_before
    history.change_params(operation.id, values, changes=change)
    result = evaluate(document, profile)
    assert result.complete, result.scene.report.findings
    assert not [
        finding for finding in result.scene.report.findings if finding.code.startswith("fit.")
    ]
    objects = list(result.scene.objects.values())
    for index, body in enumerate(objects):
        for other in objects[index + 1 :]:
            assert shared_volume(
                as_mesh_data(body.mesh).raw, as_mesh_data(other.mesh).raw
            ) == pytest.approx(0.0, abs=1e-4)
    assert document.fits[0].name == fit_before.name
    history.undo()
    assert document.fits[0] == fit_before
    assert document.ops[0].params["lid"] == original
    history.redo()
    assert document.ops[0].params["lid"] == changed


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("changed", [{"diameter": 80.0}, {"shape": "rectangular"}])
def test_editing_parent_dimensions_updates_its_insert_in_the_same_undo(kernel, changed):
    """Direkte Verlaufsänderungen folgen auch ohne gemeinsamen Parameterausdruck."""
    from app.core.lid_flow import change_for_container_edit

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    plan = plan_container(document, {"kernel": kernel, "lid": "push", "insert": True})
    history = History(document)
    history.apply(plan.title, plan.drafts, changes=plan.document_change)
    parent, insert = document.ops
    values = {**parent.params, **changed}
    change = change_for_container_edit(document, parent, values)
    assert document.ops[1] == insert
    history.change_params(parent.id, values, changes=change)
    result = evaluate(document, profile)
    assert result.complete, result.scene.report.findings
    body = result.scene.objects[insert.outputs[-1]]
    expected_width = 80.0 - 2 * 3.0 - profile.material.clearance
    assert body.mesh.bounds.size[0] == pytest.approx(expected_width, abs=1e-5)
    assert document.ops[1].params["shape"] == changed.get("shape", "round")
    history.undo()
    assert document.ops[1] == insert
    history.redo()
    assert document.ops[1].params["shape"] == changed.get("shape", "round")


@pytest.mark.parametrize(
    "values",
    [
        {"wall": 31.0},
        {"floor": 40.0},
        {"shape": "rectangular", "radius": 50.0},
        {"lid": "hinged", "hinge_width": 58.0},
        {"lid": "hinged", "hinge_reach": 4.0},
        {"rows": 50},
        {"columns": 2, "divider_height": 38.0},
        {"holes": True, "hole_radius": 30.0},
        {"holes": True, "hole_count": 64},
    ],
)
def test_unbuildable_dimensions_stop_with_an_action(values):
    """Ungültige Kombinationen werden nicht durch still verkleinerte Maße gerettet."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    plan = plan_container(project.document, {"kernel": "mesh", **values})
    History(project.document).apply(plan.title, plan.drafts, changes=plan.document_change)
    result = evaluate(project.document, profiles.make_profile("centauri-carbon-2", "petg"))
    assert not result.complete
    assert not result.scene.objects
    errors = [finding for finding in result.scene.report.findings if finding.severity == "error"]
    assert errors and all(finding.suggestions for finding in errors)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("stage", ["_housing", "_perforated", "_hinged"])
def test_cancellation_never_publishes_half_a_container(kernel, stage, monkeypatch):
    """Ein Abbruch nach einem geometrischen Teilergebnis veröffentlicht keinen Körper."""
    from app.core.errors import OperationCancelled
    from app.core.geom import container_ops
    from app.core.scene.cache import ResultCache
    from app.core.scene.cancel import CancelSignal

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    plan = plan_container(project.document, {"kernel": kernel, "lid": "hinged", "holes": True})
    History(project.document).apply(plan.title, plan.drafts, changes=plan.document_change)
    signal = CancelSignal()
    original = getattr(container_ops, stage)

    def cancelled_after(*args, **kwargs):
        result = original(*args, **kwargs)
        signal.cancel()
        return result

    monkeypatch.setattr(container_ops, stage, cancelled_after)
    cache = ResultCache()
    progress = []
    with pytest.raises(OperationCancelled):
        evaluate(
            project.document,
            profiles.make_profile("centauri-carbon-2", "petg"),
            cancelled=signal,
            cache=cache,
            progress=lambda fraction, text: progress.append((fraction, text)),
        )
    assert len(cache) == 0
    assert (1.0, "") not in progress
    assert len(project.document.ops) == 1
    assert len(project.document.fits) == 1
