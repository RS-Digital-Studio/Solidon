"""Slicer-Fehlerhandlungen mit eingefrorener Objektbindung, ohne Qt-Fenster."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import numpy as np
import pytest
import trimesh

from app.core import activation
from app.core.errors import (
    OPEN_PRINT_SETTINGS,
    PLACE_ON_BED,
    SHOW_LOCATIONS,
    SHOW_SLICER_OUTPUT,
    ExternalToolError,
    FileWriteError,
    OperationCancelled,
)
from app.core.export import handover
from app.core.geom.mesh import MeshData
from app.core.ingest import threemf
from app.core.knowledge import print_settings, profiles
from app.core.scene.cancel import CancelSignal
from app.core.types import Finding, MaterialSlot, SceneObject
from app.i18n import _, source_text
from app.ui import main_window as mw
from app.ui import print_settings_dialog as pd
from app.ui.settings import UiSettings


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        monkeypatch.setenv(variable, str(tmp_path / "userdata"))
    monkeypatch.setattr(activation, "require", lambda *_args, **_kwargs: None)


def box(x=0):
    raw = trimesh.creation.box(extents=(8, 8, 8))
    raw.apply_translation((x, 0, 4))
    return MeshData.of(raw)


def problem(name="Cat", *, object_id=None):
    result = ExternalToolError(
        detail=_(
            "Die erste Schicht des Teils „{name}“ ist leer. Setzen Sie das Teil auf das Bett "
            "oder prüfen Sie Brim, Raft und die Höhe der ersten Schicht.",
            name=name,
        ),
        values={"constraint": "empty_first_layer", "part_name": name, "field": "adhesion.kind"},
        suggestions=(SHOW_LOCATIONS, PLACE_ON_BED, OPEN_PRINT_SETTINGS, SHOW_SLICER_OUTPUT),
    )
    assert result is not None
    result.object_id = object_id
    return result


class SignalLog:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


def plate_job(tmp_path, objects, *, flavour="prusa", for_window=False):
    profile = profiles.make_profile("prusa-mini", "pla")
    return pd._PlateJob(
        objects=tuple(objects),
        plates=tuple(sorted({entry.plate for entry in objects})),
        folder=tmp_path,
        name="RM483",
        setup=handover.SlicerSetup(tmp_path / "PrusaSlicer.exe", flavour),
        settings=print_settings.resolve(profile),
        profile=profile,
        slot_profiles={},
        with_settings=False,
        for_window=for_window,
    )


def test_cli_export_names_are_exact_unique_frozen_and_leave_scene_untouched(tmp_path, monkeypatch):
    names = [
        "Cat",
        "Cat",
        "cat",
        "Cat [a]",
        "Line\nTwo",
        "Line Two [e]",
        "",
        "  Cat  ",
        _("Körper"),
        "End\n",
        "CR\r\nLF",
    ]
    objects = tuple(
        SceneObject(
            chr(97 + index),
            name,
            box(index * 12),
            features={"feature": SimpleNamespace(id="feature")},
            material_slots=[
                MaterialSlot(
                    index=0, name="PLA", colour=(18 / 255, 52 / 255, 86 / 255), material="pla"
                )
            ],
        )
        for index, name in enumerate(names)
    )
    elsewhere = SceneObject("other", "Cat", box(), plate=1)
    previous = [
        (entry.name, entry.mesh.raw.vertices.copy(), entry.features, entry.material_slots)
        for entry in objects
    ]
    captured = []
    real_writer = pd.write_assembly

    def capture(written, *args, **kwargs):
        captured.extend(written)
        return real_writer(written, *args, **kwargs)

    monkeypatch.setattr(pd, "write_assembly", capture)
    run = pd._prepare_plate(plate_job(tmp_path, (*objects, elsewhere)), 0)
    written = threemf.read_objects(run.model.read_bytes())
    with ZipFile(run.model) as archive:
        xml = ET.fromstring(archive.read("3D/3dmodel.model"))
        prusa = ET.fromstring(archive.read("Metadata/Slic3r_PE_model.config"))
    namespace = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    export_names = [
        entry.get("name", "") for entry in xml.findall("m:resources/m:object", namespace)
    ]
    assert [
        entry.get("value") for entry in prusa.findall("object/metadata[@key='name']")
    ] == export_names
    assert len(export_names) == len(set(export_names)) == len(objects), (
        "Doppelte CLI-Namen sind nicht eindeutig"
    )
    assert all(len(name.splitlines()) == 1 for name in export_names)
    bindings = getattr(run, "name_bindings", ())
    assert tuple(binding.object_id for binding in bindings) == tuple(entry.id for entry in objects)
    assert [binding.exported_name for binding in bindings] == export_names
    assert [binding.original_name for binding in bindings] == [source_text(name) for name in names]
    assert export_names[2] == "cat" and export_names[3] == "Cat [a]"
    assert export_names[5] == "Line Two [e]" and export_names[7] == "  Cat  "
    assert export_names[8] == "Körper"
    assert "other" not in run.object_ids
    for original, copied, snapshot, roundtrip in zip(
        objects, captured, previous, written, strict=True
    ):
        name, vertices, features, slots = snapshot
        assert original.name == name
        assert copied is not original
        assert copied.mesh is original.mesh
        assert copied.features is features is original.features
        assert copied.material_slots is slots is original.material_slots
        assert copied.id == original.id
        np.testing.assert_array_equal(original.mesh.raw.vertices, vertices)
        assert roundtrip.slots[0].colour[:3] == pytest.approx((18 / 255, 52 / 255, 86 / 255))
    with pytest.raises(FrozenInstanceError):
        bindings[0].object_id = "later"
    linked, _calls = worker(monkeypatch, tmp_path, [run], [problem(export_names[4])])
    delivered = linked.failed.calls[0][0]
    assert delivered.object_id == "e"
    assert "Line\nTwo" in str(delivered.detail)
    assert delivered.values["part_name"] == "Line\nTwo"


@pytest.mark.parametrize("with_settings", [False, True])
def test_cli_aliases_keep_each_face_on_its_original_material(tmp_path, with_settings):
    slots = [
        MaterialSlot(index=0, name="Red", colour=(1.0, 0.0, 0.0), material="pla"),
        MaterialSlot(index=1, name="Blue", colour=(0.0, 0.0, 1.0), material="pla"),
    ]
    a = SceneObject("red-blue", "Same", replace(box(), slots=(0, 1) * 6), material_slots=slots)
    b = SceneObject("blue-red", "Same", replace(box(20), slots=(1, 0) * 6), material_slots=slots)
    job = plate_job(tmp_path, (a, b))
    # Die explizite Projektfarbe gehört zu Slot null und stimmt hier mit
    # dessen Szenezuordnung überein; geprüft wird nur die CLI-Namensänderung.
    settings = print_settings.with_path(job.settings, "filament.colour", "#FF0000")
    run = pd._prepare_plate(replace(job, settings=settings, with_settings=with_settings), 0)
    actual = threemf.read_objects(run.model.read_bytes())
    bindings = getattr(run, "name_bindings", ())
    assert len(bindings) == 2, (
        "Die Materialprüfung braucht die tatsächlich exportierten Namensbindungen"
    )
    assert [binding.object_id for binding in bindings] == ["red-blue", "blue-red"]
    with ZipFile(run.model) as archive:
        prusa = ET.fromstring(archive.read("Metadata/Slic3r_PE_model.config"))
    assert [entry.get("value") for entry in prusa.findall("object/metadata[@key='name']")] == [
        binding.exported_name for binding in bindings
    ]
    for original, written in zip((a, b), actual, strict=True):
        original_colours = [
            original.material_slots[index].colour[:3] for index in original.mesh.slots
        ]
        written_colours = [written.slots[index].colour[:3] for index in written.mesh.slots]
        assert written_colours == original_colours
    assert a.name == b.name == "Same"


@pytest.mark.parametrize("flavour,for_window", [("prusa", True), ("orca", False), ("cura", False)])
def test_names_outside_prusa_cli_are_unchanged(tmp_path, monkeypatch, flavour, for_window):
    objects = (SceneObject("a", "Same\nName", box()), SceneObject("b", "Same\nName", box(12)))
    captured = []
    monkeypatch.setattr(
        pd,
        "write_assembly",
        lambda entries, *_args, **_kwargs: (captured.extend(entries) or tmp_path / "file.3mf", []),
    )
    run = pd._prepare_plate(plate_job(tmp_path, objects, flavour=flavour, for_window=for_window), 0)
    assert captured == list(objects)
    assert getattr(run, "name_bindings", ()) == ()


def worker(monkeypatch, tmp_path, runs, responses, *, cancelled=False):
    profile = profiles.make_profile("prusa-mini", "pla")
    calls = []

    def respond(files, *_args, **_kwargs):
        calls.append(files)
        answer = responses[len(calls) - 1]
        if isinstance(answer, BaseException):
            raise answer
        return answer

    monkeypatch.setattr(handover, "slice_model", respond)
    host = SimpleNamespace(
        _runs=runs,
        _settings=print_settings.resolve(profile),
        _profile=profile,
        _setup=handover.SlicerSetup(tmp_path / "PrusaSlicer.exe", "prusa"),
        _usage={},
        cancelled=CancelSignal(),
        step=SignalLog(),
        failed=SignalLog(),
        done=SignalLog(),
        usageReady=SignalLog(),
    )
    if cancelled:
        host.cancelled.cancel()
    pd._SliceWorker.work(host)
    return host, calls


def fake_run(tmp_path, plate, bindings):
    return SimpleNamespace(
        plate=plate,
        model=tmp_path / f"plate{plate}.3mf",
        meshes=(box(),),
        object_ids=(f"plate{plate}",),
        slots=(),
        keep_arrangement=False,
        model_height=8,
        used_tools=(),
        findings=(),
        name_bindings=tuple(
            SimpleNamespace(exported_name=name, object_id=identity, original_name=original)
            for name, identity, original in bindings
        ),
    )


@pytest.mark.parametrize(
    "native,bindings,wanted",
    [
        ("Cat", [("Cat", "one", "Customer")], "one"),
        ("cat", [("Cat", "one", "Upper"), ("cat", "two", "Lower")], "two"),
        ("  Cat  ", [("  Cat  ", "space", "  Cat  ")], "space"),
        ("Cat [a] [2]", [("Cat [a] [2]", "a", "Cat"), ("Cat [a]", "b", "Cat [a]")], "a"),
        ("Line Two [a]", [("Line Two [a]", "a", "Line\nTwo")], "a"),
        ("Cat", [("cat", "one", "Cat")], None),
        ("Cat", [("Cat", "one", "A"), ("Cat", "two", "B")], None),
        ("Cat", [("Cat", "", "A")], None),
        ("Cat", [], None),
    ],
)
def test_worker_uses_exact_frozen_cli_name_not_current_selection(
    tmp_path, monkeypatch, native, bindings, wanted
):
    refusal = problem(native, object_id="unrelated-old-object")
    host, calls = worker(monkeypatch, tmp_path, [fake_run(tmp_path, 0, bindings)], [refusal])
    assert len(calls) == 1
    delivered = host.failed.calls[0][0]
    assert delivered.object_id == wanted
    actions = {action.id for action in delivered.suggestions}
    assert {"show_locations", "place_on_bed"}.issubset(actions) is (wanted is not None)
    assert {"open_print_settings", "show_output"} <= actions
    if wanted:
        original = next(original for _, identity, original in bindings if identity == wanted)
        assert original in str(delivered.detail)
        assert original in str(delivered)
    assert not host.done.calls


def test_worker_binds_only_the_failing_plate_and_keeps_success_private(tmp_path, monkeypatch):
    from app.core.slice.gcode import GcodeMetrics

    first = fake_run(tmp_path, 0, [("Cat", "first", "First")])
    second = fake_run(tmp_path, 1, [("Cat", "second", "Second")])
    third = fake_run(tmp_path, 2, [("Cat", "third", "Third")])
    outcome = handover.SliceOutcome(tmp_path / "one.gcode", GcodeMetrics())
    host, calls = worker(monkeypatch, tmp_path, [first, second, third], [outcome, problem()])
    assert len(calls) == 2
    assert host.failed.calls[0][0].object_id == "second"
    assert not host.done.calls


@pytest.mark.parametrize("before", [False, True])
def test_cancelled_worker_emits_no_failure_or_partial_success(tmp_path, monkeypatch, before):
    host, calls = worker(
        monkeypatch,
        tmp_path,
        [fake_run(tmp_path, 0, [("Cat", "first", "Cat")])],
        [OperationCancelled()],
        cancelled=before,
    )
    assert len(calls) == (0 if before else 1)
    assert not host.failed.calls and not host.done.calls


@pytest.mark.parametrize("constraint", ["slicer_build_volume", "empty_first_layer"])
def test_first_layer_failure_racing_with_cancel_is_suppressed(tmp_path, monkeypatch, constraint):
    profile = profiles.make_profile("prusa-mini", "pla")
    host = SimpleNamespace(
        _runs=[fake_run(tmp_path, 0, [("Cat", "affected", "Cat")])],
        _settings=print_settings.resolve(profile),
        _profile=profile,
        _setup=handover.SlicerSetup(tmp_path / "PrusaSlicer.exe", "prusa"),
        _usage={},
        cancelled=CancelSignal(),
        step=SignalLog(),
        failed=SignalLog(),
        done=SignalLog(),
    )

    def cancelled_refusal(*args, **kwargs):
        host.cancelled.cancel()
        refusal = problem()
        refusal.values["constraint"] = constraint
        raise refusal

    monkeypatch.setattr(handover, "slice_model", cancelled_refusal)
    pd._SliceWorker.work(host)
    assert not host.failed.calls and not host.done.calls


def dialog_host(context, events):
    return SimpleNamespace(
        _job_context=context[0],
        _print_context=lambda: context[0],
        _settling=False,
        scene_action=None,
        _scene_action_context=None,
        parentWidget=lambda: None,
        _failed_save_copies=None,
        _show_slicer_output=lambda *_: events.append("output"),
        _open_printer_choice=lambda *_: None,
        _open_slicer_section=lambda: events.append("profiles"),
        _lift=lambda path: events.append(("lift", path)),
        reject=lambda: events.append("close-requested"),
    )


@pytest.mark.parametrize("changed", [False, True])
def test_empty_layer_print_action_lifts_local_adhesion_and_never_opens_nested_dialog(
    monkeypatch, changed
):
    events = []
    context = [("old",)]
    host = dialog_host(context, events)
    monkeypatch.setattr(
        pd,
        "handlers_of",
        lambda _: {"open_print_settings": lambda error: events.append("nested-dialog")},
    )
    handlers = pd.PrintSettingsDialog.error_handlers(host)
    host._job_context = None  # finished während des Fehlerdialogs
    if changed:
        context[0] = ("new",)
    handlers["open_print_settings"](problem())
    assert events == ([] if changed else [("lift", "adhesion.kind")])
    assert host.scene_action is None


def test_unrelated_print_settings_action_keeps_its_existing_handler(monkeypatch):
    events = []
    host = dialog_host([("old",)], events)
    monkeypatch.setattr(
        pd,
        "handlers_of",
        lambda _: {"open_print_settings": lambda error: events.append("existing")},
    )
    pd.PrintSettingsDialog.error_handlers(host)["open_print_settings"](ExternalToolError())
    assert events == ["existing"]


@pytest.mark.parametrize("action", ["show_locations", "place_on_bed"])
@pytest.mark.parametrize("when_changed", ["never", "before_click", "while_closing", "missing_job"])
def test_scene_actions_run_after_modal_completion_only_for_unchanged_job(
    monkeypatch, action, when_changed
):
    events = []
    context = [("old",)]
    host = dialog_host(context, events)
    if when_changed == "missing_job":
        host._job_context = None
    parent_handlers = {action: lambda error: events.append(("parent", error.object_id))}
    monkeypatch.setattr(pd, "handlers_of", lambda _: parent_handlers)
    handlers = pd.PrintSettingsDialog.error_handlers(host)
    host._job_context = None
    if when_changed == "before_click":
        context[0] = ("new",)
    refusal = problem(object_id="affected")
    handlers[action](refusal)
    if when_changed in {"before_click", "missing_job"}:
        assert events == [] and host.scene_action is None
        return
    assert events == ["close-requested"]
    assert host.scene_action == (action, refusal)
    events.append("modal-returned")
    if when_changed == "while_closing":
        context[0] = ("new",)
    pending = pd.PrintSettingsDialog.take_scene_action(host)
    if pending is not None:
        parent_handlers[pending[0]](pending[1])
    assert events == ["close-requested", "modal-returned"] + (
        [] if when_changed == "while_closing" else [("parent", "affected")]
    )
    assert pd.PrintSettingsDialog.take_scene_action(host) is None


@pytest.mark.parametrize(
    "job,settling", [(None, False), (("old",), False), (("new",), True), (("new",), False)]
)
def test_old_or_cancelled_first_layer_failure_is_not_displayed(monkeypatch, job, settling):
    events = []
    host = SimpleNamespace(
        _job_context=job,
        _print_context=lambda: ("new",),
        _settling=settling,
        _worker=None,
        _failed_save_copies=None,
        reported=SignalLog(),
        state=SimpleNamespace(setText=lambda text: events.append(("state", text))),
    )
    monkeypatch.setattr(pd, "show_error", lambda error, _: events.append(("error", error)))
    pd.PrintSettingsDialog._slice_failed(host, problem(), [Finding("kept", "info", "Befund")])
    valid = job == ("new",) and not settling
    assert len(events) == (2 if valid else 0)
    assert len(host.reported.calls) == (1 if valid else 0)


def test_file_write_error_still_displays_without_slice_context(monkeypatch):
    events = []
    host = SimpleNamespace(
        _settling=False,
        _worker=None,
        _job_context=None,
        _failed_save_copies=None,
        state=SimpleNamespace(setText=lambda text: None),
    )
    monkeypatch.setattr(pd, "show_error", lambda error, _: events.append(error))
    error = FileWriteError()
    pd.PrintSettingsDialog._slice_failed(host, error)
    assert events == [error]


@pytest.mark.parametrize("constraint", ["slicer_build_volume", "empty_first_layer"])
def test_queued_first_layer_failure_after_cancel_button_is_suppressed(monkeypatch, constraint):
    events = []
    cancelled = CancelSignal()
    cancelled.cancel()
    host = SimpleNamespace(
        _settling=False,
        _worker=SimpleNamespace(cancelled=cancelled),
        _job_context=("same",),
        _print_context=lambda: ("same",),
        _failed_save_copies=None,
        state=SimpleNamespace(setText=lambda text: events.append(text)),
    )
    monkeypatch.setattr(pd, "show_error", lambda error, _: events.append(error))
    refusal = problem()
    refusal.values["constraint"] = constraint
    pd.PrintSettingsDialog._slice_failed(host, refusal)
    assert events == []


def main_host(*, deleted=False, current=True):
    affected = SceneObject("affected", "Affected", box())
    other = SceneObject("other", "Other", box(12))
    events = []
    selection = ["other"]
    host = SimpleNamespace(
        session=SimpleNamespace(
            last_result=SimpleNamespace(
                scene=SimpleNamespace(
                    objects={"other": other, **({} if deleted else {"affected": affected})}
                )
            ),
            result_current=current,
            apply=lambda title, drafts: events.append(("apply", drafts)),
        ),
        _quiet_command_allowed=lambda: current,
        object_tree=SimpleNamespace(
            selected_objects=lambda: selection[:],
            selected=lambda: selection[0],
            select_object=lambda identity: (
                selection.__setitem__(0, identity),
                events.append(("select", identity)),
            ),
        ),
        tools=SimpleNamespace(activate=lambda tool: events.append(("tool", tool))),
        analysis_bar=SimpleNamespace(show_map=lambda kind: events.append(("map", kind))),
        _analysis_map=lambda *args: events.append(("analysis", args)),
        # Wählt der Bericht, bleibt er vorn (``_SelectionPage.held``).
        feature_dock=SimpleNamespace(held=nullcontext),
    )
    host._object_of = lambda error: mw.MainWindow._object_of(host, error)
    host._entry_of = lambda error: mw.MainWindow._entry_of(host, error)
    host._show_layers_after_error = lambda error: mw.MainWindow._show_layers_after_error(
        host, error
    )
    return host, events


def test_no_name_binding_has_no_current_selection_fallback():
    host, _ = main_host()
    assert mw.MainWindow._object_of(host, problem()) is None
    assert mw.MainWindow._object_of(host, ExternalToolError()) == "other"


@pytest.mark.parametrize("deleted,current", [(False, True), (True, True), (False, False)])
def test_show_locations_opens_layers_for_the_affected_object_only(deleted, current):
    host, events = main_host(deleted=deleted, current=current)
    mw.MainWindow._show_error_location(host, problem(object_id="affected"))
    assert events == (
        [("select", "affected"), ("tool", "layers")] if current and not deleted else []
    )


@pytest.mark.parametrize(
    "identity,deleted,current",
    [
        ("affected", False, True),
        (None, False, True),
        ("affected", True, True),
        ("affected", False, False),
    ],
)
def test_place_on_bed_uses_the_existing_undo_operation_and_never_other_selection(
    identity, deleted, current
):
    host, events = main_host(deleted=deleted, current=current)
    mw.MainWindow._place_on_bed_after_error(host, problem(object_id=identity))
    if identity and not deleted and current:
        assert len(events) == 1 and events[0][0] == "apply"
        drafts = events[0][1]
        assert len(drafts) == 1 and drafts[0].op == "place_on_bed"
        assert drafts[0].inputs == ("affected",) and drafts[0].params == {}
        assert mw.REGISTRY.get(drafts[0].op).reversible
    else:
        assert events == []


@pytest.mark.parametrize("action", ["show_locations", "place_on_bed"])
def test_real_main_dispatches_after_exec_and_delete_scheduling(monkeypatch, action):
    events = []
    context = [("job",)]
    dialog = dialog_host(context, events)
    signal = SimpleNamespace(connect=lambda *_: None)
    profile = profiles.make_profile("prusa-mini", "pla")
    dialog.settings = print_settings.resolve(profile)
    for name in ("sliced", "reported", "handedOver", "setupRequested", "filamentsRequested"):
        setattr(dialog, name, signal)
    dialog.usage_notice = SimpleNamespace(changed=signal, requests={})
    dialog.has_changes = lambda: False
    dialog.deleteLater = lambda: events.append("delete-scheduled")
    dialog.take_scene_action = lambda: pd.PrintSettingsDialog.take_scene_action(dialog)
    handlers = {action: lambda error: events.append(("handled", error.object_id))}
    window = SimpleNamespace(
        session=SimpleNamespace(request_fine=lambda: None),
        settings=UiSettings(),
        filaments=SimpleNamespace(return_to_print_button=SimpleNamespace(hide=lambda: None)),
        usage_notice=SimpleNamespace(offer=lambda *_args, **_kwargs: None),
        _end_inserting_for_output=lambda: None,
        _gcode_returned=lambda *_: None,
        _slicer_findings=lambda *_: None,
        _count_delivery=lambda *_: None,
        _refresh_inventory=lambda: None,
        _store_settings=lambda: None,
        _offer_support=lambda: None,
        error_handlers=lambda: handlers,
    )

    def execute():
        events.append("exec")
        pd.PrintSettingsDialog.error_handlers(dialog)[action](problem(object_id="affected"))
        assert events == ["exec", "close-requested"]
        events.append("settled")
        return 0

    dialog.exec = execute
    monkeypatch.setattr(pd, "handlers_of", lambda _: handlers)
    monkeypatch.setattr(mw, "PrintSettingsDialog", lambda *_: dialog)
    monkeypatch.setattr(mw, "waiting", nullcontext)
    monkeypatch.setattr(mw, "ensure_print_disclosure", lambda *_: None)
    mw.MainWindow.action_print_settings(window)
    assert events == [
        "exec",
        "close-requested",
        "settled",
        "delete-scheduled",
        ("handled", "affected"),
    ]
