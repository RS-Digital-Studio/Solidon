"""Profilketten gegen unterscheidbare Hersteller- und Nutzerbestände prüfen."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.errors import ExternalToolError
from app.core.export import slicer_profiles as sp
from app.core.knowledge.profiles import printer_profiles


def _write(path: Path, **values: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_user_chain_keeps_the_vendor_of_its_installed_parent(tmp_path: Path) -> None:
    root = tmp_path / "resources" / "profiles"
    _write(root / "Z-Bolt" / "process" / "base.json", name="common", speed="wrong")
    _write(root / "BBL" / "process" / "base.json", name="common", speed="correct")
    _write(root / "BBL" / "process" / "middle.json", name="A1", inherits="common")
    child = _write(tmp_path / "user" / "process" / "own.json", inherits="A1", flow="1.1")

    assert sp.resolve_values(child, (root / "Z-Bolt", root)) == {"speed": "correct", "flow": "1.1"}


def test_includes_apply_between_inheritance_and_local_values(tmp_path: Path) -> None:
    root = tmp_path / "machine"
    _write(root / "base.json", name="base", machine_start_gcode="generic", speed="10")
    _write(root / "middle.json", name="middle", inherits="base", machine_end_gcode="park")
    _write(root / "nested.json", name="nested", machine_start_gcode="vendor", speed="20")
    _write(root / "first.json", name="first", include=["nested"], speed="30")
    _write(root / "second.json", name="second", speed="40", layer_change_gcode="layer")
    child = _write(root / "child.json", inherits="middle", include=["first", "second"], speed="50")
    assert sp.resolve_values(child) == {
        "machine_start_gcode": "vendor",
        "machine_end_gcode": "park",
        "layer_change_gcode": "layer",
        "speed": "50",
    }


@pytest.mark.parametrize("cycle", [False, True])
def test_unresolved_includes_cannot_be_flattened_as_success(tmp_path: Path, cycle: bool) -> None:
    child = _write(tmp_path / "machine" / "child.json", name="child", include=["template"])
    if cycle:
        _write(child.parent / "template.json", name="template", include=["child"])
    with pytest.raises(ExternalToolError) as caught:
        sp.resolve_values(child)
    assert caught.value.suggestions


def test_hidden_bases_filter_incompatible_processes(tmp_path: Path) -> None:
    root = tmp_path / "resources" / "profiles"
    _write(root / "Anker" / "process" / "base.json", name="base", compatible_printers=["M5 .2"])
    _write(
        root / "Anker" / "process" / "fine.json",
        name="Fine",
        inherits="base",
        instantiation="true",
    )
    executable = root.parent.parent / "orca.exe"
    available = sp.find_profiles(executable, "orca")
    machine = sp.SlicerProfile(tmp_path / "machine.json", "M5 .4", "machine")
    assert sp.processes(available, machine) == []


@pytest.mark.parametrize(
    ("name", "identifier"),
    [
        ("Original Prusa MK4S 0.4 nozzle", "prusa-mk4s"),
        ("Original Prusa MINI IS 0.4 nozzle", "prusa-mini"),
        ("Original Prusa XL 0.4 nozzle", "prusa-xl"),
    ],
)
def test_official_prusa_names_match_the_solidon_printer(name: str, identifier: str) -> None:
    assert sp.printer_for(name, printer_profiles()) == identifier


def test_actual_json_identity_wins_over_filename_and_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installed = tmp_path / "resources" / "profiles"
    user = tmp_path / "user"
    name = "SUNLU PLA Marble @BBL A1"
    _write(installed / "BBL" / "filament" / f"{name}.json", name=name)
    own = _write(user / "filament" / "SUNLU Marble PLA.json", name=name, **{"from": "User"})
    monkeypatch.setattr(sp, "install_root", lambda _exe: installed)
    monkeypatch.setattr(sp, "user_roots", lambda _flavour, _exe: [user])
    assert sp._named_profile(tmp_path / "orca.exe", "orca", name, "filament") == own


def _text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


@pytest.fixture
def native_prusa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    executable = tmp_path / "PrusaSlicer" / "prusa-slicer.exe"
    root = executable.parent / "resources" / "profiles"
    _text(root / "Alien.ini", "[filament:*common*]\nfilament_type = ABS\n")
    _text(
        root / "PrusaResearch.ini",
        "[vendor]\nname = Prusa Research\n"
        "[printer_model:MK4S]\nname = Original Prusa MK4S\n"
        "[printer:*common*]\nstart_gcode = G28\\nG1 Z5\nend_gcode = M84\n"
        "gcode_flavor = marlin2\nnozzle_diameter = 0.4\n"
        "[printer:Original Prusa MK4S 0.4 nozzle]\ninherits = *common*\nprinter_model = MK4S\n"
        "[filament:*common*]\nfilament_type = PLA\nfilament_density = 1.24\n"
        "filament_diameter = 1.75\ntemperature = 210\n"
        "[filament:*fast*]\ntemperature = 220\nfilament_max_volumetric_speed = 15\n"
        "[filament:Prusament PLA]\ninherits = *common*; *fast*\nfilament_colour = #FFA500\n"
        "[filament:Prusament PLA Silk]\ninherits = *common*\ntemperature = 217\n"
        "filament_max_volumetric_speed = 5\n"
        "[print:0.20 SPEED]\nlayer_height = 0.2\n",
    )
    config = tmp_path / "config"
    _text(
        config / "PrusaSlicer" / "PrusaSlicer.ini",
        "[presets]\nfilament = Prusament PLA\nfilament_1 = Prusament PLA\n",
    )
    _text(
        config / "PrusaSlicer" / "filament" / "Prusament PLA.ini",
        "inherits = Prusament PLA\ntemperature = 225\n",
    )
    monkeypatch.setattr(sp, "config_home", lambda _platform: str(config))
    return executable


def test_prusa_bundle_and_user_delta_resolve_all_parents(native_prusa: Path) -> None:
    profile = sp.profile_by_name(native_prusa, "prusa", "Prusament PLA", "filament")
    assert profile is not None and profile.from_user
    roots = sp.profile_roots("prusa", native_prusa)
    values = sp.resolve_profile(profile, roots)
    assert values["temperature"] == "225"
    assert values["filament_type"] == "PLA"
    assert values["filament_max_volumetric_speed"] == "15"
    assert "inherits" not in values
    assert sp.filament_values(profile, roots) == {
        "temperature.nozzle": 225,
        "filament.density": pytest.approx(1.24),
        "filament.diameter": pytest.approx(1.75),
        "filament.max_flow": pytest.approx(15),
    }


@pytest.mark.parametrize(
    ("name", "temperature", "max_flow"),
    [("Prusament PLA", 225, 15), ("Prusament PLA Silk", 217, 5)],
)
def test_prusa_selected_filament_reaches_the_written_configuration(
    native_prusa: Path, tmp_path: Path, name: str, temperature: int, max_flow: int
) -> None:
    """Die Ausgabe behält den gewählten Bündelabschnitt und den Vorrang eigener Profile."""
    from app.core.export import handover
    from app.core.knowledge import print_settings, profiles
    from app.core.types import MaterialSlot

    profile = profiles.make_profile("prusa-mk4s", "pla")
    setup = handover.SlicerSetup(native_prusa, "prusa")
    slot = MaterialSlot(0, "Spule", material=name, material_type="PLA")

    config = handover.write_config(
        print_settings.resolve(profile), profile, setup, tmp_path, (slot,)
    )

    values = dict(
        line.split(" = ", 1)
        for line in config.process.read_text(encoding="utf-8").splitlines()
        if " = " in line
    )
    assert values["temperature"] == str(temperature)
    assert values["filament_max_volumetric_speed"] == str(max_flow)
    assert values["filament_density"] == "1.24"
    assert config.written["temperature"] == str(temperature)


def test_prusa_profiles_retain_section_and_inherited_machine_knowledge(native_prusa: Path) -> None:
    found = sp.find_profiles(native_prusa, "prusa")
    machine = next(item for item in found if item.kind == "machine")
    assert machine.section == "printer:Original Prusa MK4S 0.4 nozzle"
    assert machine.printer_model == "Original Prusa MK4S"
    assert machine.nozzle == pytest.approx(0.4)
    assert sp.resolve_profile(machine)["start_gcode"] == r"G28\nG1 Z5"
    assert not any("*common*" in item.name for item in found)


def test_prusa_configured_slots_keep_repeated_profile_and_vendor_values(native_prusa: Path) -> None:
    found = sp.configured_filaments("prusa", native_prusa)
    assert len(found) == 2
    assert all(item.material_type == "PLA" and item.colour == "#FFA500" for item in found)


def test_prusa_pending_vendor_updates_do_not_replace_active_profiles(native_prusa: Path) -> None:
    config = sp.prusa_config(native_prusa)
    assert config is not None
    _text(
        config.parent / "cache" / "vendor" / "PrusaResearch.ini",
        "[filament:Prusament PLA]\nfilament_type = ABS\n",
    )
    profile = sp.profile_by_name(native_prusa, "prusa", "Prusament PLA", "filament")
    assert profile is not None
    assert (
        sp.resolve_profile(profile, sp.profile_roots("prusa", native_prusa))["filament_type"]
        == "PLA"
    )


def test_incomplete_prusa_profile_does_not_hide_the_remaining_store(native_prusa: Path) -> None:
    _text(
        native_prusa.parent / "resources" / "profiles" / "Broken.ini",
        "[filament:Broken]\ninherits = *missing*\n",
    )
    found = sp.find_profiles(native_prusa, "prusa", ("filament",))
    assert "Broken" not in {item.name for item in found}
    assert "Prusament PLA" in {item.name for item in found}


@pytest.fixture
def native_cura(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    executable = tmp_path / "UltiMaker Cura 5.13.0" / "CuraEngine.exe"
    root = executable.parent / "share" / "cura" / "resources"
    _write(
        root / "definitions" / "fdmprinter.def.json",
        name="Base",
        metadata={"visible": False},
        settings={
            "machine": {
                "children": {
                    "machine_start_gcode": {"default_value": "G28"},
                    "machine_nozzle_size": {"default_value": 0.4},
                    "machine_width": {"default_value": 220},
                }
            }
        },
    )
    _write(
        root / "definitions" / "ender3.def.json",
        name="Creality Ender-3",
        inherits="fdmprinter",
        overrides={
            "machine_start_gcode": {"default_value": "G28\nG1 Z5"},
            "machine_height": {"default_value": 250},
            "machine_depth": {"default_value": 220, "value": "machine_width"},
        },
    )
    material = (
        '<fdmmaterial xmlns="http://www.ultimaker.com/material"><metadata><name>'
        "<brand>Generic</brand><material>PLA</material><color>Generic</color></name>"
        "<GUID>pla-guid</GUID><color_code>#ffc924</color_code></metadata>"
        "<properties><density>1.24</density><diameter>2.85</diameter></properties>"
        '<settings><setting key="print temperature">200</setting>'
        '<setting key="heated bed temperature">60</setting>'
        '<machine><machine_identifier product="Different machine"/>'
        '<setting key="print temperature">280</setting></machine></settings></fdmmaterial>'
    )
    _text(root / "materials" / "generic_pla.xml.fdm_material", material)
    config = tmp_path / "config"
    _text(
        config / "cura" / "5.13" / "materials" / "own_pla.xml.fdm_material",
        material.replace(">200<", ">215<").replace(">2.85<", ">1.75<"),
    )
    _text(
        config / "cura" / "5.13" / "quality_changes" / "own.inst.cfg",
        "[general]\nname = My quality\ndefinition = ender3\n"
        "[metadata]\ntype = quality_changes\n[values]\nlayer_height = 0.16\n"
        "speed_print = =__import__('os').system('should never run')\n",
    )
    monkeypatch.setattr(sp, "config_home", lambda _platform: str(config))
    return executable


def test_cura_machine_inherits_data_without_evaluating_expressions(native_cura: Path) -> None:
    profile = sp.profile_by_name(native_cura, "cura", "Creality Ender-3", "machine")
    assert profile is not None
    values = sp.resolve_profile(profile, sp.profile_roots("cura", native_cura))
    assert values["machine_start_gcode"] == "G28\nG1 Z5"
    assert values["machine_nozzle_size"] == pytest.approx(0.4)
    assert values["machine_height"] == 250
    assert "machine_depth" not in values


def test_cura_user_material_values_override_installation_without_wrong_machine_values(
    native_cura: Path,
) -> None:
    profile = sp.profile_by_name(native_cura, "cura", "Generic PLA", "filament")
    assert profile is not None and profile.from_user
    assert sp.filament_values(profile) == {
        "temperature.nozzle": 215,
        "temperature.bed": 60,
        "filament.density": pytest.approx(1.24),
        "filament.diameter": pytest.approx(1.75),
    }
    assert sp.resolve_profile(profile)["filament_colour"] == "#ffc924"


def test_cura_user_quality_values_keep_unknown_expressions_unknown(native_cura: Path) -> None:
    profile = sp.profile_by_name(native_cura, "cura", "My quality", "process")
    assert profile is not None and profile.from_user
    assert sp.resolve_profile(profile) == {"layer_height": "0.16"}


def test_same_cura_material_name_with_two_diameters_is_not_silently_chosen(
    native_cura: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = native_cura.parent / "share" / "cura" / "resources" / "materials"
    source = root / "generic_pla.xml.fdm_material"
    _text(
        root / "generic_pla_175.xml.fdm_material",
        source.read_text(encoding="utf-8").replace(">2.85<", ">1.75<"),
    )
    monkeypatch.setattr(sp, "user_roots", lambda _flavour, _executable: [])
    assert len(sp.find_profiles(native_cura, "cura", ("filament",))) == 2
    assert sp.profile_by_name(native_cura, "cura", "Generic PLA", "filament") is None


def test_one_broken_template_does_not_hide_unrelated_printers(tmp_path: Path) -> None:
    """Beschädigte Profile bleiben isoliert; gültige Maschinen bleiben auswählbar."""
    root = tmp_path / "resources" / "profiles" / "Vendor" / "machine"
    _write(root / "Good.json", name="Good", instantiation="true", printer_model="Good")
    _write(root / "Base.json", name="Base", instantiation="false")
    broken = _write(
        root / "Broken.json",
        name="Broken",
        instantiation="true",
        inherits="Base",
        include=["Missing"],
    )
    available = sp.find_profiles(tmp_path / "slicer.exe", "orca", ("machine",))
    assert [profile.name for profile in available] == ["Good"]
    with pytest.raises(ExternalToolError):
        sp.resolve_values(broken)


@pytest.mark.parametrize("sandboxed", [False, True])
def test_cura_data_profiles_use_host_home_inside_flatpak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sandboxed: bool
) -> None:
    """Solidons eigener Datenordner ist kein Cura-Nutzerbestand."""
    user_home = tmp_path / "user"
    normal = tmp_path / "chosen-data"
    fallback = user_home / ".local" / "share"
    expected = (fallback if sandboxed else normal) / "cura" / "5.13"
    (expected / "materials").mkdir(parents=True)
    monkeypatch.setenv("XDG_DATA_HOME", str(normal))
    monkeypatch.setattr(sp.Path, "home", classmethod(lambda cls: user_home))
    monkeypatch.setattr(sp.discover, "in_flatpak", lambda: sandboxed)
    roots = sp._cura_user_roots(
        tmp_path / "Cura5.13" / "CuraEngine", tmp_path / "config", platform="linux"
    )
    assert roots == [expected]
