"""Raft-Abstand: feste Cura-Werte und native Formeln bleiben unterscheidbar."""

import json
from pathlib import Path

import pytest

from app.core.errors import ExternalToolError
from app.core.export import handover, manufacturer, slicer_profiles
from app.core.knowledge import print_settings, profiles


def definition(tmp_path, *, overlap="raft_airgap / 2", child=None):
    base = tmp_path / "base.def.json"
    base.write_text(
        json.dumps(
            {
                "settings": {
                    "raft_airgap": {"default_value": 0.3},
                    "machine_nozzle_size": {"default_value": 0.4},
                    "layer_0_z_overlap": {"default_value": 0.22, "value": overlap},
                    "machine_start_gcode": {"default_value": ""},
                    "machine_end_gcode": {"default_value": ""},
                }
            }
        ),
        encoding="utf-8",
    )
    if child is None:
        return base
    target = tmp_path / "child.def.json"
    target.write_text(json.dumps({"inherits": "base", "overrides": child}), encoding="utf-8")
    return target


@pytest.mark.parametrize("mode", ("direct", "path", "profile"))
def test_existing_reader_keeps_unexecuted_contact_expression(tmp_path, mode):
    path = definition(tmp_path)
    contact = {}
    if mode == "direct":
        values = slicer_profiles._cura_definition_values(path, (), cura_raft_contact=contact)
    elif mode == "path":
        values = slicer_profiles.resolve_values(path, cura_raft_contact=contact)
    else:
        entry = slicer_profiles.SlicerProfile(path, "Printer", "machine")
        values = slicer_profiles.resolve_profile(entry, cura_raft_contact=contact)
    assert "layer_0_z_overlap" not in values
    assert values["raft_airgap"] == pytest.approx(0.3)
    assert contact == {"raft_airgap": 0.3, "layer_0_z_overlap": "raft_airgap / 2"}


@pytest.mark.parametrize("value", (0.07, "0.07", "raft_airgap / 3"))
def test_child_override_keeps_its_own_meaning(tmp_path, value):
    path = definition(tmp_path, child={"layer_0_z_overlap": {"value": value}})
    contact = {}
    slicer_profiles.resolve_values(path, cura_raft_contact=contact)
    assert contact["layer_0_z_overlap"] == value


def machine_for(monkeypatch, path):
    monkeypatch.setattr(handover, "_cura_base", lambda exe: str(path))
    monkeypatch.setattr(handover, "_cura_printer_definition", lambda exe, profile: "")
    monkeypatch.setattr(handover, "_profile_roots", lambda setup: ())
    monkeypatch.setattr(handover, "profile_source", lambda *args: None)
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *args: ())
    monkeypatch.setattr(slicer_profiles, "match", lambda *args, **kwargs: (None, None))
    return handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura")


@pytest.mark.parametrize("formula", ("raft_airgap / 2", "raft_airgap/2"))
def test_machine_uses_only_the_proven_native_formula(tmp_path, monkeypatch, formula):
    setup = machine_for(monkeypatch, definition(tmp_path, overlap=formula))
    result = handover._cura_machine(setup, profiles.make_profile(), {"raft_airgap": "0.16"})
    assert float(result.settings["layer_0_z_overlap"]) == pytest.approx(0.08)


@pytest.mark.parametrize("value", (0.07, "0.07"))
def test_machine_preserves_fixed_native_overlap(tmp_path, monkeypatch, value):
    setup = machine_for(monkeypatch, definition(tmp_path, overlap=value))
    result = handover._cura_machine(setup, profiles.make_profile(), {"raft_airgap": "0.16"})
    assert float(result.settings["layer_0_z_overlap"]) == pytest.approx(0.07)


@pytest.mark.parametrize("formula", ("raft_airgap / 3", "unknown_setting", "=raft_airgap/2"))
def test_unknown_formula_refuses_own_gap_before_process_start(tmp_path, monkeypatch, formula):
    setup = machine_for(monkeypatch, definition(tmp_path, overlap=formula))
    with pytest.raises(ExternalToolError) as caught:
        handover._cura_machine(setup, profiles.make_profile(), {"raft_airgap": "0.16"})
    assert caught.value.suggestions


def test_unknown_formula_does_not_refuse_unchanged_native_gap(tmp_path, monkeypatch):
    setup = machine_for(monkeypatch, definition(tmp_path, overlap="other_formula"))
    result = handover._cura_machine(setup, profiles.make_profile(), {})
    assert "layer_0_z_overlap" not in result.settings


def test_cura_without_full_foundation_keeps_previous_process_handoff(monkeypatch):
    settings = print_settings.resolve(profiles.make_profile())
    setup = handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura")
    base = manufacturer.base_settings(profiles.make_profile(), "standard", setup)
    assert not base.has_profile
    assert manufacturer.written_paths(settings, base) is None


@pytest.mark.parametrize("raw", ("0.07", "raft_airgap / 3"))
def test_selected_machine_container_keeps_its_contact_override(tmp_path, raw):
    definitions = tmp_path / "resources" / "definitions"
    definitions.mkdir(parents=True)
    path = definition(definitions)
    config = tmp_path / "config"
    instances = config / "machine_instances"
    instances.mkdir(parents=True)
    users = config / "user"
    users.mkdir()
    for name, overlap in (("alpha", "0.09"), ("beta", raw)):
        (instances / f"{name}.global.cfg").write_text(
            f"[general]\nid = {name}\nname = {name}\n[containers]\n0 = {name}_user\n7 = base\n",
            encoding="utf-8",
        )
        (users / f"{name}_user.inst.cfg").write_text(
            f"[general]\nname = {name}_user\n[values]\nlayer_0_z_overlap = {overlap}\n",
            encoding="utf-8",
        )
    source = slicer_profiles.SlicerProfile(
        path, "beta", "machine", section="beta", cura_instance=instances / "beta.global.cfg"
    )
    contact = {"raft_airgap": 999, "layer_0_z_overlap": "stale"}
    values = slicer_profiles.resolve_profile(
        source, (tmp_path / "resources", config), cura_raft_contact=contact
    )
    assert contact == {"raft_airgap": 0.3, "layer_0_z_overlap": raw}
    assert values["layer_0_z_overlap"] == raw
