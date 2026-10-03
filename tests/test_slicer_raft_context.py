"""Der neue Cura-Rückweg gilt ausschließlich für den unveränderten Auftrag."""

from types import SimpleNamespace

import pytest

from app.core.errors import AppError, ExternalToolError, FileWriteError
from app.core.export import handover
from app.core.knowledge import print_settings, profiles
from app.core.scene.cancel import CancelSignal
from app.ui import print_settings_dialog as dialog


def refusal():
    try:
        handover._cura_raft_overlap(
            {"layer_0_z_overlap": "layer_height * 2"}, {"raft_airgap": "0.16"}, "Cura"
        )
    except AppError as problem:
        return problem
    raise AssertionError("Die unbekannte Abhängigkeit braucht ihren belegten Fehler.")


@pytest.mark.parametrize("state", ["current", "changed", "missing", "cancelled", "settling"])
def test_raft_failure_is_shown_only_for_current_job(monkeypatch, state):
    calls = []
    cancelled = CancelSignal()
    if state == "cancelled":
        cancelled.cancel()
    host = SimpleNamespace(
        _settling=state == "settling",
        _worker=SimpleNamespace(cancelled=cancelled),
        _job_context=None if state == "missing" else "job",
        _print_context=lambda: "other" if state == "changed" else "job",
        _failed_save_copies=None,
        state=SimpleNamespace(setText=lambda text: calls.append(text)),
    )
    monkeypatch.setattr(dialog, "show_error", lambda error, owner: calls.append(error))
    dialog.PrintSettingsDialog._slice_failed(host, refusal())
    assert len(calls) == (2 if state == "current" else 0)


def test_worker_suppresses_raft_failure_after_cancel(monkeypatch, tmp_path):
    calls = []
    profile = profiles.make_profile()
    run = SimpleNamespace(
        model=tmp_path / "part.3mf",
        meshes=None,
        slots=(),
        keep_arrangement=False,
        model_height=None,
        used_tools=frozenset({0}),
        findings=(),
    )
    host = SimpleNamespace(
        _runs=[run],
        _settings=print_settings.resolve(profile),
        _profile=profile,
        _setup=handover.SlicerSetup(tmp_path / "CuraEngine.exe", "cura"),
        _usage={},
        cancelled=CancelSignal(),
        step=SimpleNamespace(emit=lambda *args: None),
        failed=SimpleNamespace(emit=lambda *args: calls.append(args)),
        done=SimpleNamespace(emit=lambda *args: calls.append(args)),
    )

    def cancelled_refusal(*args, **kwargs):
        host.cancelled.cancel()
        raise refusal()

    monkeypatch.setattr(handover, "slice_model", cancelled_refusal)
    dialog._SliceWorker.work(host)
    assert calls == []


def test_file_save_error_keeps_its_existing_context_free_route(monkeypatch):
    calls = []
    host = SimpleNamespace(
        _settling=False,
        _worker=None,
        _job_context=None,
        _failed_save_copies=None,
        state=SimpleNamespace(setText=lambda text: None),
    )
    problem = FileWriteError()
    monkeypatch.setattr(dialog, "show_error", lambda error, owner: calls.append(error))
    dialog.PrintSettingsDialog._slice_failed(host, problem)
    assert calls == [problem]


@pytest.mark.parametrize(
    "constraint,field",
    [
        ("raft_gap_dependency", "adhesion.raft_gap"),
        ("empty_first_layer", "adhesion.kind"),
        ("different_error", "parent"),
    ],
)
@pytest.mark.parametrize("changed", [False, True])
def test_both_local_actions_and_unrelated_parent_survive_composition(
    monkeypatch, constraint, field, changed
):
    calls = []
    context = ["job"]
    monkeypatch.setattr(
        dialog,
        "handlers_of",
        lambda owner: {"open_print_settings": lambda error: calls.append("parent")},
    )
    host = SimpleNamespace(
        parentWidget=lambda: None,
        _job_context=context[0],
        _print_context=lambda: context[0],
        _failed_save_copies=None,
        _show_slicer_output=lambda error: None,
        _open_slicer_section=lambda: None,
        _open_printer_choice=lambda error: None,
        _lift=lambda path: calls.append(path),
    )
    handler = dialog.PrintSettingsDialog.error_handlers(host)["open_print_settings"]
    host._job_context = None
    if changed:
        context[0] = "other"
    handler(ExternalToolError(values={"constraint": constraint}))
    assert calls == ([] if changed and constraint != "different_error" else [field])
