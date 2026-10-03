"""Der gewählte Cura-Prozess erhält festen Raftkontakt neben seinen Jerk-Werten."""

import json

import pytest

from app.core.errors import ExternalToolError
from app.core.export import handover, slicer_profiles


def instance(tmp_path, containers, *, train_contact=None):
    resources = tmp_path / "resources"
    definitions = resources / "definitions"
    definitions.mkdir(parents=True)
    path = definitions / "base.def.json"
    path.write_text(
        json.dumps(
            {
                "settings": {
                    "raft_airgap": {"default_value": 0.3},
                    "layer_0_z_overlap": {"default_value": 0.22, "value": "raft_airgap / 2"},
                    "machine_nozzle_size": {"default_value": 0.4},
                    "machine_extruder_count": {"default_value": 1},
                    "jerk_enabled": {"default_value": True},
                    "jerk_travel_enabled": {"default_value": True},
                    "jerk_print": {"default_value": 8},
                    "jerk_travel": {"value": "jerk_print * 2"},
                }
            }
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config"
    machines = config / "machine_instances"
    machines.mkdir(parents=True)
    positions = {"user": "0", "quality_changes": "1", "intent": "2", "quality": "3"}
    lines = ["[general]", "id = chosen", "name = chosen", "[containers]", "7 = base"]
    for folder, values in containers:
        directory = config / folder
        directory.mkdir(exist_ok=True)
        key = "chosen_" + folder
        lines.append(positions[folder] + " = " + key)
        (directory / (key + ".inst.cfg")).write_text(
            "[general]\nname = "
            + key
            + "\n[values]\n"
            + "\n".join(f"{key} = {value}" for key, value in values.items())
            + "\n",
            encoding="utf-8",
        )
    machine = machines / "chosen.global.cfg"
    machine.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if train_contact is not None:
        extruders = resources / "extruders"
        extruders.mkdir()
        (extruders / "tool.def.json").write_text(
            json.dumps(
                {
                    "settings": {
                        "machine_nozzle_size": {"default_value": 0.4},
                        "layer_0_z_overlap": {"default_value": train_contact},
                    }
                }
            ),
            encoding="utf-8",
        )
        trains = config / "extruders"
        trains.mkdir()
        (trains / "chosen.extruder.cfg").write_text(
            "[general]\nid = tool\n[metadata]\nmachine = chosen\nposition = 0\n"
            "[containers]\n7 = tool\n",
            encoding="utf-8",
        )
    profile = slicer_profiles.SlicerProfile(
        path,
        "chosen",
        "machine",
        section="chosen",
        cura_instance=machine,
    )
    return profile, (resources, config)


@pytest.mark.parametrize("folder", ("user", "quality", "intent", "quality_changes"))
@pytest.mark.parametrize("motion", (False, True))
def test_contact_uses_selected_process_container(tmp_path, folder, motion):
    profile, roots = instance(
        tmp_path,
        [
            (
                folder,
                {
                    "layer_0_z_overlap": "0.07",
                    "raft_airgap": "0.18",
                    "jerk_print": "11",
                },
            )
        ],
    )
    contact = {"stale": "forbidden"}
    native = slicer_profiles.resolve_profile(
        profile,
        roots,
        cura_motion=motion,
        cura_raft_contact=contact,
    )
    assert contact == {"raft_airgap": "0.18", "layer_0_z_overlap": "0.07"}
    assert handover._cura_raft_overlap(contact, {"raft_airgap": "0.16"}, "Cura") == {
        "layer_0_z_overlap": "0.07"
    }
    if motion:
        assert native["jerk_print"] == pytest.approx(11)
        assert native["jerk_travel"] == pytest.approx(22)


def test_user_contact_wins_and_extruder_cannot_overwrite_it(tmp_path):
    profile, roots = instance(
        tmp_path,
        [
            ("quality", {"layer_0_z_overlap": "0.12", "jerk_print": "11"}),
            ("user", {"layer_0_z_overlap": "0.07", "jerk_print": "13"}),
        ],
        train_contact=0.99,
    )
    contact = {}
    native = slicer_profiles.resolve_profile(
        profile,
        roots,
        cura_motion=True,
        cura_raft_contact=contact,
    )
    assert contact == {"raft_airgap": 0.3, "layer_0_z_overlap": "0.07"}
    assert native["jerk_print"] == pytest.approx(13)
    assert native["jerk_travel"] == pytest.approx(26)


def test_contact_inspection_does_not_change_unrelated_process_values(tmp_path):
    profile, roots = instance(
        tmp_path,
        [
            (
                "quality",
                {
                    "layer_0_z_overlap": "0.07",
                    "speed_print": "99",
                    "jerk_print": "11",
                },
            )
        ],
    )
    plain = slicer_profiles.resolve_profile(profile, roots, cura_motion=True)
    contact = {}
    inspected = slicer_profiles.resolve_profile(
        profile,
        roots,
        cura_motion=True,
        cura_raft_contact=contact,
    )
    assert plain == inspected
    assert "speed_print" not in inspected
    assert inspected["jerk_print"] == pytest.approx(11)


@pytest.mark.parametrize("overlap", ("0", "raft_airgap / 3", "unknown_setting"))
def test_process_contact_preserves_zero_and_unrecognized_expression(tmp_path, overlap):
    profile, roots = instance(tmp_path, [("quality", {"layer_0_z_overlap": overlap})])
    contact = {}
    slicer_profiles.resolve_profile(profile, roots, cura_motion=True, cura_raft_contact=contact)
    assert contact["layer_0_z_overlap"] == overlap
    if overlap == "0":
        assert handover._cura_raft_overlap(contact, {"raft_airgap": "0.16"}, "Cura") == {
            "layer_0_z_overlap": "0"
        }
    else:
        with pytest.raises(ExternalToolError):
            handover._cura_raft_overlap(contact, {"raft_airgap": "0.16"}, "Cura")


def test_process_order_uses_nearest_contact_value(tmp_path):
    profile, roots = instance(
        tmp_path,
        [
            ("quality", {"layer_0_z_overlap": "0.12", "raft_airgap": "0.4"}),
            ("intent", {"layer_0_z_overlap": "0.1"}),
            ("quality_changes", {"layer_0_z_overlap": "0.07"}),
        ],
    )
    contact = {}
    slicer_profiles.resolve_profile(profile, roots, cura_motion=True, cura_raft_contact=contact)
    assert contact == {"raft_airgap": "0.4", "layer_0_z_overlap": "0.07"}
