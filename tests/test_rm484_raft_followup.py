"""Raft-Folgefälle: native Priorität und Rückwege ohne Qt-Fenster."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.core.errors import AppError, ExternalToolError
from app.core.export import handover, manufacturer
from app.core.knowledge import print_settings, profiles
from app.ui import print_settings_dialog as dialog


@pytest.mark.parametrize("flavour", ("prusa", "orca"))
def test_zero_layers_search_points_to_layer_count(monkeypatch, flavour):
    settings = print_settings.resolve(profiles.make_profile())
    settings = replace(settings, adhesion=replace(settings.adhesion, kind="raft", raft_layers=0))
    host = SimpleNamespace(
        settings=settings,
        session=SimpleNamespace(profile=profiles.make_profile()),
        _fields={field.path: field for field in dialog.FIELDS},
        _editors={"adhesion.kind": "raft", "support.style": "none"},
        _current_flavour=lambda: flavour,
        _foundation_for_current_setup=lambda: None,
    )
    monkeypatch.setattr(dialog, "_setting_editor_value", lambda editor, field: editor)
    host._inactive_paths = lambda: dialog.PrintSettingsDialog._inactive_paths(host)
    assert "adhesion.raft_gap" in host._inactive_paths()
    assert (
        dialog.PrintSettingsDialog._inactive_search_control(host, "adhesion.raft_gap")
        == "adhesion.raft_layers"
    )


@pytest.mark.parametrize("context", ("same", "stale", "missing"))
def test_unknown_cura_overlap_stays_in_its_current_dialog(monkeypatch, context):
    with pytest.raises(AppError) as raised:
        handover._cura_raft_overlap(
            {"layer_0_z_overlap": "layer_height * 2"}, {"raft_airgap": "0.16"}, "Cura"
        )
    calls = []
    monkeypatch.setattr(
        dialog,
        "handlers_of",
        lambda parent: {"open_print_settings": lambda error: calls.append("parent")},
    )
    host = SimpleNamespace(
        parentWidget=lambda: None,
        _job_context=None if context == "missing" else "job",
        _print_context=lambda: "other" if context == "stale" else "job",
        _failed_save_copies=None,
        _show_slicer_output=lambda error: None,
        _open_slicer_section=lambda: None,
        _open_printer_choice=lambda error: None,
        _lift=lambda field: calls.append(field),
    )
    handler = dialog.PrintSettingsDialog.error_handlers(host)["open_print_settings"]
    handler(raised.value)
    assert calls == (["adhesion.raft_gap"] if context == "same" else [])
    assert {key: raised.value.values[key] for key in ("constraint", "field")} == {
        "constraint": "raft_gap_dependency",
        "field": "adhesion.raft_gap",
    }


def test_other_print_settings_action_keeps_its_existing_handler(monkeypatch):
    calls = []
    monkeypatch.setattr(
        dialog,
        "handlers_of",
        lambda parent: {"open_print_settings": lambda error: calls.append(error)},
    )
    host = SimpleNamespace(
        parentWidget=lambda: None,
        _job_context="job",
        _print_context=lambda: "job",
        _failed_save_copies=None,
        _show_slicer_output=lambda error: None,
        _open_slicer_section=lambda: None,
        _open_printer_choice=lambda error: None,
        _lift=lambda field: calls.append(field),
    )
    problem = ExternalToolError(detail="Andere Einstellung")
    dialog.PrintSettingsDialog.error_handlers(host)["open_print_settings"](problem)
    assert calls == [problem]


@pytest.mark.parametrize("brim_type", ("auto_brim", "outer_only", "no_brim", None))
def test_native_orca_raft_precedes_independent_brim_setting(brim_type):
    native = {"raft_layers": "2", "raft_contact_distance": "0.15"}
    if brim_type is not None:
        native["brim_type"] = brim_type
    read, _foreign = manufacturer._read_process(native, manufacturer._Context(0.4), {})
    assert read["adhesion.kind"] == "raft"
    settings = print_settings.resolve(profiles.make_profile())
    for path, value in read.items():
        settings = print_settings.with_path(settings, path, value)
    settings = print_settings.with_choice(settings, "adhesion.raft_gap", 0.16)
    written = handover.as_mapping(settings, "orca", paths=settings.explicit)
    assert written.get("raft_contact_distance") == "0.16"


@pytest.mark.parametrize("raft_layers", (None, "0", "-1", "unbekannt"))
@pytest.mark.parametrize(("brim_type", "kind"), (("auto_brim", "auto"), ("outer_only", "brim")))
def test_missing_positive_native_raft_keeps_brim_choice(raft_layers, brim_type, kind):
    native = {"brim_type": brim_type}
    if raft_layers is not None:
        native["raft_layers"] = raft_layers
    read, _foreign = manufacturer._read_process(
        native, manufacturer._Context(0.4), {"raft_layers": "3"}
    )
    assert read["adhesion.kind"] == kind
