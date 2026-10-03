"""Das Herstellerprofil ist die Grundlage (Konzept Herstellerprofil, 27.09.2026).

Solidon schreibt dem Slicer nur, was vom Profil des Herstellers abweichen
soll: die eigene Wahl, den übernommenen Vorschlag, das Gemessene. Diese Tests
halten die drei Teile davon fest — die Herkunft je Wert, die Rücklesung des
Herstellerprofils in Solidons Felder und die Übergabe, die nur die
Abweichung schreibt. Gegen einen nachgebauten Bestand im Temp-Ordner, nicht
gegen ein installiertes Programm.
"""

from __future__ import annotations

import json
import math
import zipfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.core.errors import ValidationError
from app.core.export import handover, manufacturer, slicer_keys
from app.core.knowledge import print_settings, profiles
from app.core.scene import serialise
from app.core.scene.project import load
from app.core.slice import advise
from app.core.types import BoundingBox, MaterialSlot, PrintSettings, Profile, SlotOverride


def _write(path: Path, document: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


# --- Herkunft je Wert -------------------------------------------------------------


def test_a_choice_and_an_accepted_suggestion_are_told_apart() -> None:
    """Eine eigene Wahl und ein übernommener Vorschlag werden getrennt geführt
    — die Wahl gilt der Platte, der Vorschlag soll dem Körper gelten, der ihn
    verlangt (Entscheidung G) —, und wer einen Vorschlag von Hand ändert, macht
    ihn zu seiner Wahl."""
    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))

    chosen = print_settings.with_choice(settings, "shell.wall_count", 4)
    assert chosen.chosen == {"shell.wall_count"} and not chosen.accepted
    accepted = print_settings.with_accepted(chosen, "support.style", "auto")
    assert accepted.accepted == {"support.style"}
    again = print_settings.with_choice(accepted, "support.style", "tree")
    assert again.chosen == {"shell.wall_count", "support.style"} and not again.accepted
    assert again.explicit == {"shell.wall_count", "support.style"}


def test_a_reset_returns_to_the_base_and_forgets_the_origin() -> None:
    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))
    base = print_settings.with_path(settings, "shell.wall_count", 2)
    chosen = print_settings.with_choice(settings, "shell.wall_count", 5)

    back = print_settings.without_choice(chosen, "shell.wall_count", base)

    assert back.shell.wall_count == 2 and not back.explicit


def test_the_effective_settings_are_the_base_with_only_the_deviations() -> None:
    """Ein gespeicherter Wert ohne Herkunft war Grundlage und ist es nicht mehr,
    wenn sich die Grundlage geändert hat — ein anderer Prozess, ein Update."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    stored = print_settings.with_choice(print_settings.resolve(profile), "infill.density", 0.4)
    stored = print_settings.with_path(stored, "shell.bottom_layers", 9)  # ohne Herkunft
    stored = replace(stored, handover="open", inventory_project_id="p-1")
    base = print_settings.resolve(profile, "fine")

    effective = print_settings.on_base(stored, base)

    assert effective.infill.density == pytest.approx(0.4), "die eigene Wahl bleibt"
    assert effective.shell.bottom_layers == base.shell.bottom_layers, "der Rest ist Grundlage"
    assert effective.layers.layer_height == pytest.approx(base.layers.layer_height)
    assert (effective.handover, effective.inventory_project_id) == ("open", "p-1")
    assert effective.chosen == {"infill.density"}


def test_an_older_file_keeps_only_what_someone_set() -> None:
    """Entscheidung E: Als eigene Wahl gilt, was weder der heutigen Auflösung
    noch der Vorgabe der Dataclass gleicht — die alten 40 mm/s (RM-256) und die
    45 Grad der Faustregel fallen heraus, vier Wände bleiben."""
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    reference = print_settings.resolve(profile)
    stored = print_settings.with_path(reference, "shell.wall_count", 4)
    stored = print_settings.with_path(stored, "speed.outer_wall", 40.0)
    stored = print_settings.with_path(stored, "support.threshold_angle", 45.0)

    assert print_settings.legacy_choices(stored, reference) == {"shell.wall_count"}


def test_a_file_from_0_5_0_keeps_what_someone_set() -> None:
    """Dieselbe Einordnung an einer Datei, die Solidon 0.5.0 selbst gespeichert
    hat (Format 33, Stufe „Fein" am Centauri Carbon 2): Vier Wände und 25 %
    Füllung waren eine Wahl. Die Tempi von damals — 30/45/60 mm/s, aus der
    Stufe allein — waren es nicht; sie kommen jetzt aus dem Profil des
    Herstellers (RM-256). Bis zum Review der Stufe A+B lag hier eine
    nachgebaute Datei mit heutigen Werten, und die Einordnung machte an allen
    72 Sätzen von 0.5.0 mit Fein, Entwurf und Belastbar die Tempi zur Wahl."""
    project = load(Path(__file__).parent / "data" / "projects" / "print_settings_v33.p3d")
    settings = project.document.print_settings
    assert settings is not None

    assert project.document.app_version == "0.5.0"
    assert settings.quality == "fine"
    assert settings.speed.outer_wall == pytest.approx(30.0), "so hat 0.5.0 gespeichert"
    assert settings.chosen == {"shell.wall_count", "infill.density"}
    assert not settings.accepted


def test_the_resolution_of_0_5_0_lays_the_first_line_as_0_5_0_did() -> None:
    """Seit Stufe D ist die erste Bahn so breit wie beim Hersteller, am
    Centauri Carbon 2 0,5 mm. Die Nachbildung von 0.5.0 rechnet weiter mit
    1,07 Bahnbreiten: Beim Zusammenführen beider Stufen hielt die Einordnung
    die 0,449 mm der Datei von 0.5.0 sonst für eine eigene Wahl und schrieb sie
    über Elegoos Profil."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")

    today = print_settings.resolve(profile)
    then = print_settings.resolve(profile, legacy=True)

    assert today.layers.first_layer_line_width == pytest.approx(0.5)
    assert then.layers.first_layer_line_width == pytest.approx(0.449)


def _older_project(tmp_path: Path, mutate: Callable[[dict[str, Any]], None]) -> Path:
    """Die Beispieldatei in Format 35, im Projektinhalt verändert."""
    source = Path(__file__).parent / "data" / "projects" / "example_v35.p3d"
    target = tmp_path / "aelter.p3d"
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as copy:
        for item in original.infolist():
            payload = original.read(item.filename)
            if item.filename == "project.json":
                document = json.loads(payload)
                assert document["format_version"] == 35
                mutate(document)
                payload = json.dumps(document).encode("utf-8")
            copy.writestr(item, payload)
    return target


def test_a_damaged_older_file_is_damaged_not_a_program_error(tmp_path: Path) -> None:
    """Review Stufe A+B, R1: Eine Gruppe als Text endete in der Einordnung als
    ``AttributeError`` — ein Programmierfehler mit Fehlerbericht. Die
    Einordnung lässt den Satz jetzt stehen, und die Schemaprüfung danach sagt,
    was er ist: beschädigt."""
    settings = serialise.print_settings_to_data(print_settings.resolve(_cc2()))

    def damage(document: dict[str, Any]) -> None:
        document["print_settings"] = {**settings, "layers": "x"}

    with pytest.raises(ValidationError) as raised:
        load(_older_project(tmp_path, damage))

    assert raised.value.constraint == "damaged"


def test_a_carried_printer_is_compared_with_itself(tmp_path: Path) -> None:
    """Review Stufe A+B, R2: Ein Drucker, den nur das Projekt mitbringt, war in
    der Einordnung unbekannt — dann galt ``PrintSettings()`` als Vergleich, und
    die ganze Materialtabelle wurde eigene Wahl. Jetzt zählt seine
    Beschreibung aus der Datei, ohne dass er im Bestand angemeldet wird."""
    p1s = profiles.make_profile("bambu-p1s", "pla")
    carried = {"printers": {"meine-p1s": profiles.printer_definition(p1s.printer)}}
    settings = serialise.print_settings_to_data(print_settings.resolve(p1s))

    def carry(document: dict[str, Any]) -> None:
        document["scene"]["printer"] = "meine-p1s"
        document["scene"]["material"] = "pla"
        document["carried_profiles"] = carried
        document["print_settings"] = settings

    project = load(_older_project(tmp_path, carry))

    assert project.document.print_settings is not None
    assert not project.document.print_settings.chosen
    assert "meine-p1s" not in profiles.printer_profiles(), "die Migration meldet nichts an"


def test_a_project_profile_reads_a_carried_printer_without_registering_it() -> None:
    p1s = profiles.make_profile("bambu-p1s", "pla")
    carried = {"printers": {"meine-p1s": profiles.printer_definition(p1s.printer)}}

    profile = profiles.project_profile("meine-p1s", "pla", carried)

    assert profile.printer.build_volume == p1s.printer.build_volume
    assert profile.printer.speed_outer_wall == p1s.printer.speed_outer_wall
    assert "meine-p1s" not in profiles.printer_profiles()
    unknown = profiles.project_profile("gibt-es-nicht", "pla", None)
    assert unknown.printer.id == profiles.scene_profile("gibt-es-nicht", "pla").printer.id


# --- Rücklesung -------------------------------------------------------------------


@pytest.fixture
def bestand(tmp_path: Path) -> Path:
    """Ein Elegoo-Bestand in der Staffelung, die der Hersteller wirklich nutzt."""
    root = tmp_path / "ElegooSlicer" / "resources" / "profiles"
    _write(
        root / "Elegoo" / "machine" / "fdm_machine_common.json",
        {
            "type": "machine",
            "name": "fdm_machine_common",
            "retraction_length": ["0.8"],
            "retraction_speed": ["30"],
            "z_hop": ["0.4"],
            "wipe": ["1"],
            "default_bed_type": "4",
            "nozzle_diameter": ["0.4"],
        },
    )
    _write(
        root / "Elegoo" / "machine" / "ECC2" / "cc2.json",
        {
            "type": "machine",
            "name": "Elegoo Centauri Carbon 2 0.4 nozzle",
            "inherits": "fdm_machine_common",
            "instantiation": "true",
            "printer_model": "Elegoo Centauri Carbon 2",
            "default_print_profile": "0.20mm Standard @CC2",
        },
    )
    _write(
        root / "Elegoo" / "process" / "fdm_process_common.json",
        {
            "type": "process",
            "name": "fdm_process_common",
            "layer_height": "0.2",
            "initial_layer_print_height": "0.2",
            "line_width": "0.42",
            "initial_layer_line_width": "0.5",
            "wall_loops": "2",
            "top_shell_layers": "5",
            "bottom_shell_layers": "3",
            "wall_generator": "classic",
            "sparse_infill_density": "15%",
            "sparse_infill_pattern": "crosshatch",
            "enable_support": "0",
            "support_type": "tree(auto)",
            "support_threshold_angle": "30",
            "support_object_xy_distance": "0.35",
            "support_base_pattern_spacing": "2.1",
            "skirt_loops": "0",
            "reduce_crossing_wall": "0",
            "outer_wall_speed": "160",
        },
    )
    _write(
        root / "Elegoo" / "process" / "ECC2" / "standard.json",
        {
            "type": "process",
            "name": "0.20mm Standard @CC2",
            "inherits": "fdm_process_common",
            "instantiation": "true",
            "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
        },
    )
    _write(
        root / "Elegoo" / "filament" / "ECC2" / "pla.json",
        {
            "type": "filament",
            "name": "Elegoo PLA @ECC2",
            "instantiation": "true",
            "filament_type": ["PLA"],
            "nozzle_temperature": ["210"],
            "nozzle_temperature_initial_layer": ["210"],
            "hot_plate_temp": ["55"],
            "textured_plate_temp": ["60"],
            "textured_plate_temp_initial_layer": ["60"],
            "eng_plate_temp": ["0"],
            "slow_down_layer_time": ["4"],
            "filament_retraction_length": ["nil"],
            "filament_z_hop": ["nil"],
            "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
        },
    )
    executable = tmp_path / "ElegooSlicer" / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    return executable


def _setup(executable: Path, **choices: str) -> handover.SlicerSetup:
    return handover.SlicerSetup(
        executable=executable,
        flavour="orca",
        machine_profile="Elegoo Centauri Carbon 2 0.4 nozzle",
        base_process="0.20mm Standard @CC2",
        base_filament="Elegoo PLA @ECC2",
        **choices,
    )


def _cc2() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "pla")


@pytest.mark.parametrize(
    ("executable_name", "native", "switch"),
    [
        ("orca-slicer.exe", "chamber_temperature", True),
        ("elegoo-slicer.exe", "chamber_temperature", True),
        ("bambu-studio.exe", "chamber_temperatures", False),
        ("CrealityPrint.exe", "chamber_temperature", True),
    ],
)
@pytest.mark.parametrize("supported", [True, False, None])
def test_chamber_control_uses_the_program_key_and_proven_machine(
    bestand: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    executable_name: str,
    native: str,
    switch: bool,
    supported: bool | None,
) -> None:
    """35 °C dürfen weder unter einem fremden Schlüssel verschwinden noch
    eine Kammerheizung erfinden. Eine alte Pluralangabe darf nicht gewinnen."""
    executable = bestand.with_name(executable_name)
    executable.touch()
    setup = _setup(executable)
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    machine_path = root / "machine" / "fdm_machine_common.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    if supported is not None:
        machine["support_chamber_temp_control"] = "1" if supported else "0"
    _write(machine_path, machine)
    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(chamber_temperature=["0"], chamber_temperatures=["0"])
    _write(filament_path, filament)
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    settings = print_settings.with_choice(print_settings.resolve(_cc2()), "temperature.chamber", 35)

    config = handover.write_config(settings, _cc2(), setup, tmp_path)
    document = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    assert document[native] == ["35"]
    other = "chamber_temperature" if native.endswith("temperatures") else "chamber_temperatures"
    assert other not in document, "nur ein Name darf die Temperatur bestimmen"
    assert config.written[native] == "35", "die Gegenprobe liest denselben Schlüssel"
    if switch:
        assert document["activate_chamber_temp_control"] == ["1" if supported else "0"]
        assert config.written["activate_chamber_temp_control"] == ("1" if supported else "0")
    else:
        assert "activate_chamber_temp_control" not in document
    project = handover.project_settings(settings, _cc2(), setup)
    assert project[native] == ["35"]
    assert other not in project
    foundation = manufacturer.base_settings(_cc2(), settings.quality, setup)
    assert foundation.chamber_control is supported
    assert bool(manufacturer.chamber_limitation(foundation)) is (supported is not True)
    findings = handover.foundation_findings(settings, _cc2(), setup)
    assert any(f.code == "slicer.chamber_unavailable" for f in findings) is (supported is not True)


@pytest.mark.parametrize("program", ["orcaslicer", "elegooslicer", "bambustudio", "crealityprint"])
def test_chamber_readback_follows_the_same_name_as_the_slicer(tmp_path: Path, program: str) -> None:
    """Bambus Plural und der alte Orca-Alias kommen auch beim Übernehmen an."""
    from app.core.export import slicer_profiles

    source = _write(tmp_path / "material.json", {"chamber_temperatures": ["42"]})
    assert slicer_profiles.filament_values(source, program=program)["temperature.chamber"] == 42
    _write(source, {"chamber_temperature": ["42"], "chamber_temperatures": ["37"]})
    assert slicer_profiles.filament_values(source, program=program)["temperature.chamber"] == 37


@pytest.mark.parametrize("executable_name", ["orca-slicer.exe", "bambu-studio.exe"])
def test_chamber_values_stay_separate_for_each_spool(
    bestand: Path, monkeypatch: pytest.MonkeyPatch, executable_name: str
) -> None:
    """Die Maschinenfreigabe ist gemeinsam, die Temperatur gehört jeder Spule."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    machine_path = (
        bestand.parent / "resources" / "profiles" / "Elegoo" / "machine" / "fdm_machine_common.json"
    )
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    _write(machine_path, {**machine, "support_chamber_temp_control": "1"})
    executable = bestand.with_name(executable_name)
    executable.touch()
    setup = _setup(executable)
    settings = print_settings.resolve(_cc2())
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(
                name="A", material_type="PLA", temperature=replace(settings.temperature, chamber=35)
            ),
            SlotOverride(
                name="B", material_type="PLA", temperature=replace(settings.temperature, chamber=50)
            ),
        ),
    )
    slots = (
        MaterialSlot(index=0, name="A", material_type="PLA"),
        MaterialSlot(index=1, name="B", material_type="PLA"),
    )
    project = handover.project_settings(settings, _cc2(), setup, slots=slots)
    key = "chamber_temperatures" if executable_name == "bambu-studio.exe" else "chamber_temperature"
    assert project[key] == ["35", "50"]
    if executable_name != "bambu-studio.exe":
        assert project["activate_chamber_temp_control"] == ["1", "1"]


@pytest.mark.parametrize(("project_temperature", "slot_temperature"), [(35, 0), (0, 35)])
def test_chamber_warning_uses_only_the_spools_that_are_printed(
    bestand: Path,
    monkeypatch: pytest.MonkeyPatch,
    project_temperature: int,
    slot_temperature: int,
) -> None:
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    settings = print_settings.with_choice(
        print_settings.resolve(_cc2()), "temperature.chamber", project_temperature
    )
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(
                name="A",
                material_type="PLA",
                temperature=replace(settings.temperature, chamber=slot_temperature),
            ),
        ),
    )
    slot = MaterialSlot(index=0, name="A", material_type="PLA")
    findings = handover.foundation_findings(settings, _cc2(), _setup(bestand), (slot,))
    assert any(f.code == "slicer.chamber_unavailable" for f in findings) is (slot_temperature > 0)


@pytest.mark.parametrize("own_temperature", [0, None])
def test_only_a_chamber_choice_changes_the_manufacturers_heater_switch(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, own_temperature: int | None
) -> None:
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    machine_path = root / "machine" / "fdm_machine_common.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    _write(machine_path, {**machine, "support_chamber_temp_control": "1"})
    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    original_switch = "1" if own_temperature is not None else "0"
    _write(
        filament_path,
        {
            **filament,
            "chamber_temperature": ["45"],
            "activate_chamber_temp_control": [original_switch],
        },
    )
    setup = _setup(bestand)
    settings = print_settings.resolve(_cc2())
    if own_temperature is not None:
        settings = print_settings.with_choice(settings, "temperature.chamber", own_temperature)
    config = handover.write_config(settings, _cc2(), setup, tmp_path)
    document = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    assert document["chamber_temperature"] == (["0"] if own_temperature is not None else ["45"])
    assert document["activate_chamber_temp_control"] == ["0"]


def test_the_base_is_read_back_from_the_manufacturers_profile(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gemessen am echten Bestand (27.09.2026): Elegoos Standard hat zwei Wände,
    drei Bodenschichten, ``classic``, eine erste Schicht von 0,2 mm und 0,5 mm,
    Z-Hop 0,4 an der Maschine — Solidons Tabelle sagt 3, 4, ``arachne``, 0,25,
    0,449 und 0,2."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))
    base = foundation.settings

    assert foundation.has_profile
    assert (base.shell.wall_count, base.shell.bottom_layers) == (2, 3)
    assert base.shell.wall_generator == "classic"
    assert (base.layers.first_layer_height, base.layers.first_layer_line_width) == (0.2, 0.5)
    assert base.support.style == "none"
    assert base.support.threshold_angle == pytest.approx(60.0), "30 gegen die Waagerechte"
    assert base.support.xy_gap == pytest.approx(0.35)
    assert base.support.density == pytest.approx(0.42 / 2.1)
    assert base.retraction.avoid_crossing_walls is False
    assert base.retraction.z_hop == pytest.approx(0.4), "nil im Filament: der Wert der Maschine"
    assert base.retraction.length == pytest.approx(0.8)
    assert base.cooling.minimum_layer_time == pytest.approx(4.0)
    assert not base.explicit


def test_orcaslicer_legacy_percentages_match_the_values_it_prints(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OrcaSlicer 2.4.2 verwirft die Prozentwerte für Wandtempo und
    Stützenabstand, liest beim Füllungstempo aber den Zahlenteil als mm/s."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "orcaslicer")
    profile_root = bestand.parent / "resources" / "profiles" / "Elegoo"
    process = profile_root / "process" / "ECC2" / "standard.json"
    document = json.loads(process.read_text(encoding="utf-8"))
    document.update(
        {
            "initial_layer_speed": "50%",
            "support_object_xy_distance": "60%",
        }
    )
    _write(process, document)

    fallback = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))
    assert fallback.settings.speed.first_layer == pytest.approx(30.0)
    assert fallback.settings.support.xy_gap == pytest.approx(0.35)
    assert "speed.first_layer" not in fallback.foreign

    document["initial_layer_infill_speed"] = "50%"
    _write(process, document)
    printed = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert printed.settings.speed.first_layer == pytest.approx(50.0)
    assert printed.settings.support.xy_gap == pytest.approx(0.35)
    assert "speed.first_layer" not in printed.foreign


def test_bambu_reads_the_explicit_high_flow_variant(
    bestand: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Bambu-Werte folgen der ausgewählten Düsenvariante, auch beim Filament."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = ["Direct Drive Standard", "Direct Drive High Flow"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ["1", "1"],
        }
    )
    _write(machine_path, machine)

    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "print_extruder_variant": variants,
            "print_extruder_id": ["1", "1"],
            "inner_wall_speed": ["300", "400"],
            "outer_wall_speed": ["200", "350"],
        }
    )
    _write(process_path, process)
    standard = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))
    assert standard.settings.speed.inner_wall == pytest.approx(300.0)
    assert standard.settings.speed.outer_wall == pytest.approx(200.0)

    process["nozzle_volume_type"] = "High Flow"
    _write(process_path, process)

    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants,
            "filament_flow_ratio": ["0.98", "0.985"],
            "filament_max_volumetric_speed": ["21", "29"],
            "filament_retraction_length": ["nil", "0.4"],
            "filament_retraction_speed": ["nil", "50"],
            "filament_z_hop": ["nil", "0.6"],
        }
    )
    _write(filament_path, filament)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert foundation.settings.speed.inner_wall == pytest.approx(400.0)
    assert foundation.settings.speed.outer_wall == pytest.approx(350.0)
    assert foundation.settings.filament.flow_ratio == pytest.approx(0.985)
    assert foundation.settings.filament.max_flow == pytest.approx(29.0)
    assert foundation.settings.retraction.length == pytest.approx(0.4)
    assert foundation.settings.retraction.speed == pytest.approx(50.0)
    assert foundation.settings.retraction.z_hop == pytest.approx(0.6)

    chosen = print_settings.with_choice(foundation.settings, "speed.outer_wall", 210.0)
    config = handover.write_config(chosen, _cc2(), _setup(bestand), tmp_path)

    assert config.written["outer_wall_speed"] == "210"
    assert config.written["filament_flow_ratio"] == "0.985"
    assert config.written["filament_max_volumetric_speed"] == "29"
    assert config.written["filament_retraction_length"] == "0.4"
    assert config.written["filament_retraction_speed"] == "50"
    assert config.written["filament_z_hop"] == "0.6"


def test_bambu_high_flow_uses_the_exact_variant_instead_of_e3d(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P2S High Flow bleibt von der ähnlich benannten E3D-Düse getrennt."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = [
        "Direct Drive Standard",
        "Direct Drive High Flow",
        "Direct Drive E3D High Flow",
    ]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ["1", "1", "1"],
        }
    )
    _write(machine_path, machine)

    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": "High Flow",
            "print_extruder_variant": variants,
            "print_extruder_id": ["1", "1", "1"],
            "inner_wall_speed": ["300", "600", "600"],
        }
    )
    _write(process_path, process)

    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants,
            "filament_max_volumetric_speed": ["21", "40", "21"],
        }
    )
    _write(filament_path, filament)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert foundation.variant_name == "Direct Drive High Flow"
    assert foundation.settings.speed.inner_wall == pytest.approx(600.0)
    assert foundation.settings.filament.max_flow == pytest.approx(40.0)
    assert "speed.inner_wall" in foundation.from_profile


def test_bambu_maps_the_selected_variant_in_each_profile_independently(
    bestand: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """H2C-Prozess, Maschine und Filament haben verschieden lange Variantenlisten."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = [
        "Direct Drive Standard",
        "Direct Drive High Flow",
        "Direct Drive E3D High Flow",
        "Direct Drive Standard",
        "Direct Drive High Flow",
    ]
    extruder_ids = ["1", "1", "1", "2", "2"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive", "Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": extruder_ids,
        }
    )
    _write(machine_path, machine)

    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": "E3D High Flow",
            "print_extruder_variant": variants,
            "print_extruder_id": extruder_ids,
            "outer_wall_speed": ["200", "300", "400", "200", "300"],
        }
    )
    _write(process_path, process)

    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants[:3],
            "filament_flow_ratio": ["0.96", "0.97", "0.97"],
            "filament_max_volumetric_speed": ["15", "21", "21"],
            "filament_retraction_length": ["0.6", "0.4", "0.4"],
            "nozzle_temperature": ["245", "250", "250"],
        }
    )
    _write(filament_path, filament)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert foundation.variant_name == "Direct Drive E3D High Flow"
    assert foundation.variant_id == "1"
    assert foundation.settings.speed.outer_wall == pytest.approx(400.0)
    assert foundation.settings.filament.flow_ratio == pytest.approx(0.97)
    assert foundation.settings.filament.max_flow == pytest.approx(21.0)
    assert foundation.settings.retraction.length == pytest.approx(0.4)
    assert foundation.settings.temperature.nozzle == pytest.approx(250.0)

    chosen = print_settings.with_choice(foundation.settings, "speed.outer_wall", 450.0)
    config = handover.write_config(chosen, _cc2(), _setup(bestand), tmp_path)

    assert config.written["outer_wall_speed"] == "450"
    assert config.written["filament_flow_ratio"] == "0.97"
    assert config.written["filament_max_volumetric_speed"] == "21"
    assert config.written["filament_retraction_length"] == "0.4"
    assert config.written["nozzle_temperature"] == "250"


def test_bambu_without_an_explicit_variant_keeps_the_first_extruder(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Standard bleibt Eintrag 0, auch wenn sein Name an Extruder 2 vorkommt."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = [
        "Direct Drive Standard",
        "Direct Drive High Flow",
        "Direct Drive E3D High Flow",
        "Direct Drive Standard",
        "Direct Drive High Flow",
    ]
    ids = ["1", "1", "1", "2", "2"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive", "Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ids,
        }
    )
    _write(machine_path, machine)
    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "print_extruder_variant": variants,
            "print_extruder_id": ids,
            "inner_wall_speed": ["300", "400", "500", "350", "450"],
        }
    )
    assert "nozzle_volume_type" not in process
    _write(process_path, process)
    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants[:3],
            "filament_flow_ratio": ["0.96", "0.97", "0.97"],
            "filament_max_volumetric_speed": ["15", "21", "21"],
        }
    )
    _write(filament_path, filament)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert foundation.has_profile
    assert foundation.variant_name == "Direct Drive Standard"
    assert foundation.variant_id == "1"
    assert foundation.variant_index == 0
    assert foundation.settings.speed.inner_wall == pytest.approx(300.0)
    assert foundation.settings.filament.max_flow == pytest.approx(15.0)


def test_bambu_bound_slot_uses_the_active_filament_variant(
    bestand: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein gebundenes Filament behält Fluss und Rückzug der High-Flow-Düse."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = ["Direct Drive Standard", "Direct Drive High Flow"]
    ids = ["1", "1"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ids,
        }
    )
    _write(machine_path, machine)
    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": "High Flow",
            "print_extruder_variant": variants,
            "print_extruder_id": ids,
            "inner_wall_speed": ["300", "400"],
        }
    )
    _write(process_path, process)
    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants,
            "filament_flow_ratio": ["0.98", "0.985"],
            "filament_max_volumetric_speed": ["21", "29"],
            "filament_retraction_length": ["0.6", "0.4"],
        }
    )
    _write(filament_path, filament)
    setup = _setup(bestand)
    foundation = manufacturer.base_settings(_cc2(), "standard", setup)
    slot = MaterialSlot(index=0, name="PLA", material=str(filament_path), material_type="PLA")

    slot_settings = handover.settings_for_slot(foundation.settings, _cc2(), slot, setup)

    assert slot_settings.filament.flow_ratio == pytest.approx(0.985)
    assert slot_settings.filament.max_flow == pytest.approx(29.0)
    assert slot_settings.retraction.length == pytest.approx(0.4)

    chosen = print_settings.with_choice(foundation.settings, "speed.outer_wall", 210.0)
    chosen = handover.with_slot_override(chosen, slot, SlotOverride(temperature=chosen.temperature))
    output = tmp_path / "bound-slot"
    output.mkdir()
    original_base_settings = manufacturer.base_settings
    base_settings_calls: list[None] = []

    def count_base_settings(*args: Any, **kwargs: Any) -> manufacturer.Foundation:
        base_settings_calls.append(None)
        return original_base_settings(*args, **kwargs)

    monkeypatch.setattr(manufacturer, "base_settings", count_base_settings)
    config = handover.write_config(chosen, _cc2(), setup, output, slots=(slot,))
    assert len(base_settings_calls) == 1

    assert config.written["filament_flow_ratio"] == "0.985"
    assert config.written["filament_max_volumetric_speed"] == "29"
    assert config.written["filament_retraction_length"] == "0.4"

    base_settings_calls.clear()
    handover.project_settings(chosen, _cc2(), setup, slots=(slot,))
    assert len(base_settings_calls) == 1

    four_slots = tuple(
        MaterialSlot(
            index=index,
            name=f"PLA {index}",
            material=str(filament_path),
            material_type="PLA",
        )
        for index in range(4)
    )
    four_slot_settings = print_settings.with_choice(foundation.settings, "speed.outer_wall", 210.0)
    for four_slot in four_slots:
        four_slot_settings = handover.with_slot_override(
            four_slot_settings,
            four_slot,
            SlotOverride(temperature=four_slot_settings.temperature),
        )
    four_slot_output = tmp_path / "four-bound-slots"
    four_slot_output.mkdir()
    base_settings_calls.clear()
    handover.write_config(four_slot_settings, _cc2(), setup, four_slot_output, slots=four_slots)
    assert len(base_settings_calls) == 1

    base_settings_calls.clear()
    handover.project_settings(four_slot_settings, _cc2(), setup, slots=four_slots)
    assert len(base_settings_calls) == 1


@pytest.mark.parametrize(
    "bound_variants",
    [
        ["Direct Drive Standard", "Direct Drive E3D High Flow"],
        ["Direct Drive High Flow", "Direct Drive High Flow"],
    ],
    ids=["high-flow-fehlt", "high-flow-mehrdeutig"],
)
def test_unresolved_bound_bambu_variant_uses_one_checked_fallback(
    bestand: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bound_variants: list[str],
) -> None:
    """Ein unauflösbares Spulenprofil darf keine andere Temperatur einschleusen."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = ["Direct Drive Standard", "Direct Drive High Flow"]
    ids = ["1", "1"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ids,
        }
    )
    _write(machine_path, machine)
    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": "High Flow",
            "print_extruder_variant": variants,
            "print_extruder_id": ids,
        }
    )
    _write(process_path, process)
    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants,
            "nozzle_temperature": ["210", "220"],
            "nozzle_temperature_initial_layer": ["210", "220"],
        }
    )
    _write(filament_path, filament)
    setup = _setup(bestand)
    foundation = manufacturer.base_settings(_cc2(), "standard", setup)
    assert foundation.has_profile
    assert foundation.variant_name == "Direct Drive High Flow"
    slot_path = root / "filament" / "ECC2" / "bound.json"
    bound = dict(filament)
    bound.update(
        {
            "name": "Gebundene Spule",
            "filament_extruder_variant": bound_variants,
            "nozzle_temperature": ["235", "245"],
            "nozzle_temperature_initial_layer": ["235", "245"],
        }
    )
    _write(slot_path, bound)
    slot = MaterialSlot(index=0, name="PLA-Schrift", material=str(slot_path), material_type="PLA")

    slot_settings = handover.settings_for_slot(
        foundation.settings, _cc2(), slot, setup, foundation=foundation
    )
    output = tmp_path / "unresolved-bound-slot"
    output.mkdir()
    config = handover.write_config(foundation.settings, _cc2(), setup, output, slots=(slot,))
    filament_document = json.loads(config.filament.read_text(encoding="utf-8"))
    project = handover.project_settings(foundation.settings, _cc2(), setup, slots=(slot,))
    findings = handover.foundation_findings(foundation.settings, _cc2(), setup, slots=(slot,))

    assert slot_settings.temperature.nozzle == pytest.approx(220.0)
    assert filament_document["nozzle_temperature"] == ["220"]
    assert config.written["nozzle_temperature"] == "220"
    assert project["nozzle_temperature"] == ["220"]
    assert [finding.code for finding in findings] == ["slicer.filament_variant_unresolved"]
    assert findings[0].suggestions
    assert str(findings[0].message) == (
        "Die gebundene Spule „PLA-Schrift“ hat keine eindeutige Variante für "
        "Direct Drive High Flow. Wählen Sie das passende Spulenprofil im Druckdialog; "
        "bis dahin gelten die Projektwerte."
    )
    assert [
        finding.code
        for finding in handover.verify_settings({"nozzle_temperature": "999"}, config.written)
    ] == ["slicer.setting_ignored"]


@pytest.mark.parametrize(
    ("bound_variants", "unresolved_first"),
    [
        (["Direct Drive Standard", "Direct Drive E3D High Flow"], False),
        (["Direct Drive Standard", "Direct Drive E3D High Flow"], True),
        (["Direct Drive High Flow", "Direct Drive High Flow"], False),
        (["Direct Drive High Flow", "Direct Drive High Flow"], True),
        (["Direct Drive TPU High Flow"], False),
        (["Direct Drive TPU High Flow"], True),
    ],
    ids=[
        "fehlend-zweiter-slot",
        "fehlend-erster-slot",
        "doppelt-zweiter-slot",
        "doppelt-erster-slot",
        "h2d-tpu85-neben-tpu95",
        "h2d-tpu85-erster-slot",
    ],
)
def test_mixed_bound_bambu_variants_keep_temperatures_in_3mf(
    bestand: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bound_variants: list[str],
    unresolved_first: bool,
) -> None:
    """TPU-85A neben TPU-95A bewahrt H2D-AMS-Vektoren in der wirklichen 3MF."""
    import trimesh

    from app.core.export import writer
    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = [
        "Direct Drive Standard",
        "Direct Drive High Flow",
        "Direct Drive TPU High Flow",
        "Direct Drive E3D High Flow",
    ]
    ids = ["1"] * len(variants)
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ids,
        }
    )
    _write(machine_path, machine)
    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": "High Flow",
            "print_extruder_variant": variants,
            "print_extruder_id": ids,
        }
    )
    _write(process_path, process)
    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants,
            "nozzle_temperature": ["210", "220", "230", "240"],
            "nozzle_temperature_initial_layer": ["210", "220", "230", "240"],
            "filament_dev_ams_drying_temperature": ["65", "75", "45", "45"],
            "filament_dev_ams_drying_time": ["12", "18", "12", "18"],
            "filament_custom_curve": ["a", "b", "c"],
        }
    )
    _write(filament_path, filament)
    setup = _setup(bestand)
    foundation = manufacturer.base_settings(_cc2(), "standard", setup)
    assert foundation.has_profile
    valid_path = root / "filament" / "ECC2" / "bound-valid.json"
    valid = dict(filament)
    valid.update(
        {
            "name": "Gültige gebundene Spule",
            "nozzle_temperature": ["235", "245", "250", "255"],
            "nozzle_temperature_initial_layer": ["235", "245", "250", "255"],
        }
    )
    _write(valid_path, valid)
    unresolved_path = root / "filament" / "ECC2" / "bound-unresolved.json"
    unresolved = dict(filament)
    unresolved.update(
        {
            "name": "Unklare gebundene Spule",
            "filament_extruder_variant": bound_variants,
            "nozzle_temperature": ["235", "245"],
            "nozzle_temperature_initial_layer": ["235", "245"],
        }
    )
    _write(unresolved_path, unresolved)
    profiles = (unresolved_path, valid_path) if unresolved_first else (valid_path, unresolved_path)
    slots = tuple(
        MaterialSlot(
            index=index,
            name=f"Spule {index + 1}",
            material=str(path),
            material_type="PLA",
        )
        for index, path in enumerate(profiles)
    )
    expected = ["220", "245"] if unresolved_first else ["245", "220"]

    config_dir = tmp_path / "mixed-bound-slots"
    config_dir.mkdir()
    config = handover.write_config(foundation.settings, _cc2(), setup, config_dir, slots=slots)
    project = handover.project_settings(foundation.settings, _cc2(), setup, slots=slots)

    assert config.written["nozzle_temperature"] == ",".join(expected)
    assert project["nozzle_temperature"] == expected
    assert project["filament_dev_ams_drying_temperature"] == ["65", "75", "45", "45"]
    assert project["filament_dev_ams_drying_time"] == ["12", "18", "12", "18"]
    assert project["filament_custom_curve"] == ["a", "b", "c"]

    unbound_slots = tuple(replace(slot, material=None) for slot in slots)
    raw = trimesh.creation.box(extents=(10, 10, 10))
    raw.apply_translation((0, 0, 5))
    body = SceneObject(
        id="bambu-mixed-variants",
        name="Gemischte Bambu-Spulen",
        mesh=MeshData(raw, tuple(index % len(slots) for index in range(len(raw.faces)))),
        material_slots=list(unbound_slots),
    )
    bound_settings = handover.bind_slot_profiles(
        replace(foundation.settings, slot_profiles=tuple(slot.material for slot in slots)),
        unbound_slots,
    )
    assembly_dir = tmp_path / "mixed-bound-assembly"
    assembly_dir.mkdir()
    monkeypatch.setattr(writer.activation, "require", lambda _feature: None)
    assembly, findings = writer.write_assembly(
        [body],
        assembly_dir,
        project_name="Gemischte Spulen",
        profile=_cc2(),
        settings=bound_settings,
        setup=setup,
        checked=[],
        for_slicer=False,
    )
    with zipfile.ZipFile(assembly) as archive:
        metadata = json.loads(archive.read("Metadata/project_settings.config"))

    assert metadata["nozzle_temperature"] == expected
    assert metadata["filament_dev_ams_drying_temperature"] == ["65", "75", "45", "45"]
    assert metadata["filament_dev_ams_drying_time"] == ["12", "18", "12", "18"]
    assert metadata["filament_custom_curve"] == ["a", "b", "c"]
    assert any(finding.code == "slicer.filament_variant_unresolved" for finding in findings)


def test_manual_temperature_for_second_valid_bambu_slot_is_written_to_3mf(
    bestand: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Eine einzelne Bambu-Düsentemperatur je Slot bleibt im geschriebenen 3MF."""
    import trimesh

    from app.core.export import writer
    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = ["Direct Drive Standard", "Direct Drive High Flow"]
    ids = ["1", "1"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ids,
        }
    )
    _write(machine_path, machine)
    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": "High Flow",
            "print_extruder_variant": variants,
            "print_extruder_id": ids,
        }
    )
    _write(process_path, process)
    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants,
            "nozzle_temperature": ["215", "230"],
            "nozzle_temperature_initial_layer": ["215", "230"],
            "filament_dev_ams_drying_temperature": ["65", "75", "45", "45"],
            "filament_dev_ams_drying_time": ["12", "18", "12", "18"],
            "filament_custom_curve": ["a", "b", "c"],
        }
    )
    _write(filament_path, filament)
    setup = _setup(bestand)
    profile = _cc2()
    foundation = manufacturer.base_settings(profile, "standard", setup)
    assert foundation.has_profile
    assert foundation.variant_name == "Direct Drive High Flow"

    slots = []
    for index in range(2):
        bound_path = root / "filament" / "ECC2" / f"bound-valid-{index}.json"
        bound = dict(filament)
        bound["name"] = f"Gültiges H2D-Profil {index + 1}"
        _write(bound_path, bound)
        slots.append(
            MaterialSlot(
                index=index,
                name=f"Spule {index + 1}",
                material=str(bound_path),
                material_type="PLA",
            )
        )
    bound_slots = tuple(slots)
    settings = foundation.settings
    second_base = handover.settings_for_slot(
        settings, profile, bound_slots[1], setup, foundation=foundation
    )
    settings = handover.with_slot_override(
        settings,
        bound_slots[1],
        SlotOverride(
            temperature=replace(
                second_base.temperature,
                nozzle=231,
                nozzle_first_layer=232,
            )
        ),
    )

    config_dir = tmp_path / "manual-second-slot-config"
    config_dir.mkdir()
    config = handover.write_config(settings, profile, setup, config_dir, slots=bound_slots)
    project = handover.project_settings(settings, profile, setup, slots=bound_slots)

    expected_nozzle = ["230", "231"]
    expected_first_layer = ["230", "232"]
    assert config.written["nozzle_temperature"] == ",".join(expected_nozzle)
    assert config.written["nozzle_temperature_initial_layer"] == ",".join(expected_first_layer)
    assert project["nozzle_temperature"] == expected_nozzle
    assert project["nozzle_temperature_initial_layer"] == expected_first_layer
    assert project["filament_dev_ams_drying_temperature"] == ["65", "75", "45", "45"]
    assert project["filament_dev_ams_drying_time"] == ["12", "18", "12", "18"]
    assert project["filament_custom_curve"] == ["a", "b", "c"]

    unbound_slots = tuple(replace(slot, material=None) for slot in bound_slots)
    raw = trimesh.creation.box(extents=(10, 10, 10))
    raw.apply_translation((0, 0, 5))
    body = SceneObject(
        id="bambu-manual-temperature",
        name="Manuelle Bambu-Düsentemperatur",
        mesh=MeshData(raw, tuple(index % len(bound_slots) for index in range(len(raw.faces)))),
        material_slots=list(unbound_slots),
    )
    bound_settings = handover.bind_slot_profiles(
        replace(settings, slot_profiles=tuple(slot.material for slot in bound_slots)),
        unbound_slots,
    )
    assembly_dir = tmp_path / "manual-second-slot-assembly"
    assembly_dir.mkdir()
    monkeypatch.setattr(writer.activation, "require", lambda _feature: None)
    assembly, findings = writer.write_assembly(
        [body],
        assembly_dir,
        project_name="Manuelle Bambu-Düsentemperatur",
        profile=profile,
        settings=bound_settings,
        setup=setup,
        checked=[],
        for_slicer=False,
    )
    with zipfile.ZipFile(assembly) as archive:
        metadata = json.loads(archive.read("Metadata/project_settings.config"))

    assert metadata["nozzle_temperature"] == expected_nozzle
    assert metadata["nozzle_temperature_initial_layer"] == expected_first_layer
    assert metadata["filament_dev_ams_drying_temperature"] == ["65", "75", "45", "45"]
    assert metadata["filament_dev_ams_drying_time"] == ["12", "18", "12", "18"]
    assert metadata["filament_custom_curve"] == ["a", "b", "c"]
    assert not any(finding.code == "slicer.filament_variant_unresolved" for finding in findings)


def test_bambu_high_flow_keeps_a_slower_accepted_speed_suggestion(
    bestand: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """350 mm/s darf die aktive High-Flow-Innenwand mit 400 mm/s bremsen."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = ["Direct Drive Standard", "Direct Drive High Flow"]
    ids = ["1", "1"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ids,
        }
    )
    _write(machine_path, machine)
    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": "High Flow",
            "print_extruder_variant": variants,
            "print_extruder_id": ids,
            "inner_wall_speed": ["300", "400"],
        }
    )
    _write(process_path, process)
    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants,
            "filament_max_volumetric_speed": ["21", "29"],
        }
    )
    _write(filament_path, filament)
    setup = _setup(bestand)
    foundation = manufacturer.base_settings(_cc2(), "standard", setup)
    suggestion = print_settings.with_accepted(foundation.settings, "speed.inner_wall", 350.0)
    output = tmp_path / "accepted-speed"
    output.mkdir()

    config = handover.write_config(suggestion, _cc2(), setup, output)
    process_document = json.loads(config.process.read_text(encoding="utf-8"))

    assert process_document["inner_wall_speed"] == "350"
    assert process_document["print_extruder_variant"] == variants
    assert handover.project_settings(suggestion, _cc2(), setup)["inner_wall_speed"] == "350"


def test_bambu_does_not_guess_between_duplicate_extruder_variants(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein zweiter gleichartiger H2C-Extruder macht High Flow mehrdeutig."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = [
        "Direct Drive Standard",
        "Direct Drive High Flow",
        "Direct Drive E3D High Flow",
        "Direct Drive Standard",
        "Direct Drive High Flow",
    ]
    ids = ["1", "1", "1", "2", "2"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive", "Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ids,
        }
    )
    _write(machine_path, machine)
    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": "High Flow",
            "print_extruder_variant": variants,
            "print_extruder_id": ids,
            "inner_wall_speed": ["300", "400", "500", "300", "450"],
        }
    )
    _write(process_path, process)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert not foundation.has_profile
    # RM-333: Die Datei ist lesbar, nur die Variante nicht eindeutig. „Ließ
    # sich nicht lesen“ schickte den Kunden auf die Suche nach einer kaputten
    # Datei.
    assert not foundation.unreadable
    assert foundation.unresolved_variant == "High Flow"
    found = manufacturer.findings(foundation)
    assert [entry.code for entry in found] == ["slicer.process_variant_unresolved"]
    assert found[0].values == {"variant": "High Flow", "profile": "0.20mm Standard @CC2"}
    assert found[0].suggestions == (manufacturer.OPEN_PRINT_SETTINGS,)


def test_a_base_filament_without_the_chosen_variant_is_not_called_unreadable(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-333: Das Grundfilament kennt die gewählte Düsenvariante nicht. Solidons
    Tabelle gilt (gewollt), der Befund nennt die Variante und das Profil statt
    eines unlesbaren Prozesses."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = ["Direct Drive Standard", "Direct Drive High Flow", "Direct Drive E3D High Flow"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ["1", "1", "1"],
        }
    )
    _write(machine_path, machine)
    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": "E3D High Flow",
            "print_extruder_variant": variants,
            "print_extruder_id": ["1", "1", "1"],
        }
    )
    _write(process_path, process)
    filament_path = root / "filament" / "ECC2" / "pla.json"
    filament = json.loads(filament_path.read_text(encoding="utf-8"))
    filament.update(
        {
            "filament_extruder_variant": variants[:2],
            "nozzle_temperature": ["215", "225"],
        }
    )
    _write(filament_path, filament)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert not foundation.has_profile
    assert not foundation.unreadable
    assert foundation.unresolved_variant == "Direct Drive E3D High Flow"
    found = manufacturer.findings(foundation)
    assert [entry.code for entry in found] == ["slicer.process_variant_unresolved"]
    assert found[0].values == {
        "variant": "Direct Drive E3D High Flow",
        "profile": "Elegoo PLA @ECC2",
    }


@pytest.mark.parametrize(
    "value",
    ["nil", "", ["", ""], 5],
    ids=["nil", "leer", "liste-leerer-werte", "zahl"],
)
def test_bambu_without_a_readable_variant_says_solidons_values_apply(
    bestand: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    """RM-429: Ohne lesbare Düsenvariante fiel die Grundlage still auf
    Solidons Tabelle zurück — kein Befund, und der Kunde hielt die Werte für
    die des Herstellers (Regel 14, 21)."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    monkeypatch.setattr(manufacturer, "program", lambda _setup: "bambustudio")
    root = bestand.parent / "resources" / "profiles" / "Elegoo"
    variants = ["Direct Drive Standard", "Direct Drive High Flow"]
    machine_path = root / "machine" / "ECC2" / "cc2.json"
    machine = json.loads(machine_path.read_text(encoding="utf-8"))
    machine.update(
        {
            "extruder_type": ["Direct Drive"],
            "printer_extruder_variant": variants,
            "printer_extruder_id": ["1", "1"],
        }
    )
    _write(machine_path, machine)
    process_path = root / "process" / "ECC2" / "standard.json"
    process = json.loads(process_path.read_text(encoding="utf-8"))
    process.update(
        {
            "nozzle_volume_type": value,
            "print_extruder_variant": variants,
            "print_extruder_id": ["1", "1"],
        }
    )
    _write(process_path, process)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert not foundation.has_profile
    assert not foundation.unreadable, "die Datei ist lesbar"
    found = manufacturer.findings(foundation)
    assert [entry.code for entry in found] == ["slicer.process_variant_unreadable"]
    assert found[0].severity == "warning"
    assert found[0].values == {"profile": "0.20mm Standard @CC2"}
    assert "Solidons Werte" in str(found[0].message)
    assert found[0].suggestions == (manufacturer.OPEN_PRINT_SETTINGS,)


def test_what_the_chain_does_not_name_is_the_programs_default(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kein Hersteller setzt ``brim_type`` — die Programme setzen ``auto_brim``
    ein (gemessen an allen vier der Orca-Familie)."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)

    base = manufacturer.base_settings(_cc2(), "standard", _setup(bestand)).settings

    assert base.adhesion.kind == "auto"
    assert base.shell.outer_wall_first is False
    assert base.shell.precise_outer_wall is True, "ElegooSlicer setzt 1 ein"


def test_a_value_without_a_name_in_solidon_is_shown_not_translated(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``crosshatch`` hat in Solidon keinen Namen. Die Grundlage behält den
    Rückfall für die eigene Rechnung, nennt den Herstellerwert und rechnet ihn
    nicht zum Profil — sonst ginge ein falscher Name beim Speichern zurück."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert foundation.foreign == {"infill.pattern": "crosshatch"}
    assert "infill.pattern" not in foundation.from_profile


def test_the_bed_temperature_is_the_one_of_the_plate(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Elegoos „4" ist die texturierte PEI-Platte — belegt an 34 mit dem
    ElegooSlicer gespeicherten Projekten. Ihre 60 °C gelten, nicht die 55 der
    glatten, und eine gewählte Platte schlägt die Standardplatte."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)

    textured = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))
    smooth = manufacturer.base_settings(
        _cc2(), "standard", _setup(bestand, plate="High Temp Plate")
    )
    engineering = manufacturer.base_settings(
        _cc2(), "standard", _setup(bestand, plate="Engineering Plate")
    )

    assert textured.plate == "Textured PEI Plate"
    assert textured.settings.temperature.bed == 60
    assert smooth.settings.temperature.bed == 55
    assert engineering.plate_refuses_filament, "0 °C heißt: für dieses Filament gesperrt"


def test_a_printer_without_a_plate_choice_uses_the_one_bed_temperature() -> None:
    """Sovols Filamente setzen im Orca-Bestand nur ``hot_plate_temp``: Ein
    Drucker ohne Plattenwahl hat die eine Betttemperatur. Mit der
    Konsolenvorgabe „Cool Plate" druckte ein SV06 PLA auf 35 °C."""
    assert manufacturer.default_plate({}) == ""
    assert manufacturer.SINGLE_PLATE == "High Temp Plate"
    assert manufacturer.default_plate({"default_bed_type": "4"}) == "Textured PEI Plate"
    assert manufacturer.default_plate({}, {"default_bed_type": "Cool Plate"}) == "Cool Plate"
    assert manufacturer.plate_name("7") == "", "eine unbelegte Nummer wird nicht geraten"


def test_without_a_process_profile_the_base_is_solidons_table() -> None:
    profile = _cc2()
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    foundation = manufacturer.base_settings(profile, "standard", setup)

    assert not foundation.has_profile
    assert foundation.settings == print_settings.resolve(profile)


def test_a_measured_overhang_goes_to_the_slicer_like_a_choice() -> None:
    """§28.3: Die Probe am eigenen Drucker ist die Wahl des Kunden."""
    profile = _cc2()
    measured = Profile(
        profile.printer,
        replace(
            profile.material,
            overhang_angle=52.0,
            calibration_printer=profile.printer.id,
            calibration_nozzle_diameter=profile.printer.nozzle_diameter,
            calibration_layer_height=profile.printer.layer_height,
            calibration_extrusion_width=profile.printer.extrusion_width,
        ),
    )

    foundation = manufacturer.base_settings(measured, "standard", None)

    assert foundation.measured == {"support.threshold_angle": 52.0}


def _probed(profile: Profile, settings: PrintSettings, angle: float = 52.0) -> Profile:
    """Eine Überhangprobe, gedruckt auf dem Raster dieser Einstellungen."""
    return replace(
        profile,
        material=replace(
            profile.material,
            overhang_angle=angle,
            calibration_printer=profile.printer.id,
            calibration_nozzle_diameter=profile.printer.nozzle_diameter,
            calibration_layer_height=settings.layers.layer_height,
            calibration_extrusion_width=settings.layers.line_width,
        ),
    )


def test_a_measured_overhang_holds_only_on_the_raster_of_its_probe() -> None:
    """§28.3: Die Probe gilt für Schichthöhe und Bahnbreite, auf denen sie
    entstand. Mit einer breiteren Bahn oder der Stufe „Fein" stützen Analyse
    und Übergabe wieder ab der Grenze ohne Messung — bis zum 27.09.2026 blieb
    der gemessene Winkel stehen, weil die Grundlage ihn trug."""
    plain = _cc2()
    measured = _probed(plain, print_settings.resolve(plain))
    without = plain.overhang_limit_degrees
    assert not math.isclose(without, 52.0)
    foundation = manufacturer.base_settings(measured, "standard", None)
    assert foundation.settings.support.threshold_angle == pytest.approx(52.0)

    width = foundation.settings.layers.line_width
    wider = print_settings.with_choice(foundation.settings, "layers.line_width", width + 0.05)
    printed = manufacturer.effective(wider, foundation)
    assert printed.support.threshold_angle == pytest.approx(without)
    assert profiles.for_process(measured, printed, effective=True).overhang_limit_degrees == (
        pytest.approx(without)
    )

    back = print_settings.with_choice(printed, "layers.line_width", width)
    assert manufacturer.measured_on(back, foundation).support.threshold_angle == pytest.approx(52.0)

    fine = manufacturer.base_settings(measured, "fine", None)
    assert fine.measured == {}
    assert fine.settings.support.threshold_angle == pytest.approx(without)
    assert print_settings.resolve(measured, "fine").support.threshold_angle == pytest.approx(
        without
    )

    chosen = print_settings.with_choice(wider, "support.threshold_angle", 40.0)
    assert manufacturer.effective(chosen, foundation).support.threshold_angle == pytest.approx(40.0)


def test_a_measured_overhang_leaves_the_handover_with_its_raster(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auf dem Herstellerprofil geht die Messung als Abweichung hinaus, solange
    sie gilt — auf einem anderen Raster gilt wieder Elegoos Winkel, und den
    kennt der Slicer selbst."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    raster = manufacturer.base_settings(_cc2(), "standard", _setup(bestand)).settings
    measured = _probed(_cc2(), raster)
    foundation = manufacturer.base_settings(measured, "standard", _setup(bestand))
    assert foundation.has_profile
    assert foundation.measured == {"support.threshold_angle": 52.0}

    kept = manufacturer.effective(foundation.settings, foundation)
    assert "support.threshold_angle" in (manufacturer.written_paths(kept, foundation) or ())

    wider = print_settings.with_choice(
        foundation.settings, "layers.line_width", raster.layers.line_width + 0.05
    )
    printed = manufacturer.effective(wider, foundation)
    assert printed.support.threshold_angle == pytest.approx(raster.support.threshold_angle)
    assert "support.threshold_angle" not in (manufacturer.written_paths(printed, foundation) or ())


# --- Übergabe: nur die Abweichung --------------------------------------------------


def _written(
    tmp_path: Path, settings: PrintSettings, setup: handover.SlicerSetup
) -> tuple[dict, dict]:
    out = tmp_path / "out"
    out.mkdir()
    config = handover.write_config(settings, _cc2(), setup, out)
    assert config.filament is not None
    process = json.loads(config.process.read_text(encoding="utf-8"))
    filament = json.loads(config.filament.read_text(encoding="utf-8"))
    return process, filament


def test_the_handover_writes_nothing_over_the_manufacturer_without_a_choice(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Abnahme von Stufe B, am Bestand nachgestellt: Ohne eigene Wahl und
    ohne Vorschlag stehen in Prozess und Filament die Werte des Herstellers —
    bis zum 27.09.2026 standen dort Solidons drei Wände, Gitter und kein
    Auto-Brim."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    settings = print_settings.resolve(_cc2())

    process, filament = _written(tmp_path, settings, _setup(bestand))

    assert process["wall_loops"] == "2"
    assert process["support_type"] == "tree(auto)"
    assert process["support_threshold_angle"] == "30"
    assert "brim_type" not in process, "die Vorgabe des Programms gilt: auto_brim"
    assert process["curr_bed_type"] == "Textured PEI Plate", "die Platte, ausdrücklich"
    assert filament["nozzle_temperature_initial_layer"] == ["210"]
    assert filament["filament_z_hop"] == ["nil"], "der Rückzug bleibt an der Maschine"
    assert filament["eng_plate_temp"] == ["0"], "die Sperre des Herstellers bleibt"


def test_the_handover_writes_the_choice_and_the_accepted_suggestion(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    settings = print_settings.resolve(_cc2())
    settings = print_settings.with_choice(settings, "shell.wall_count", 4)
    settings = print_settings.with_accepted(settings, "support.style", "auto")
    settings = print_settings.with_choice(settings, "temperature.bed", 65)

    process, filament = _written(tmp_path, settings, _setup(bestand))

    assert process["wall_loops"] == "4"
    assert process["enable_support"] == "1"
    assert process["support_type"] == "tree(auto)", '„Stützen an" nimmt die Art des Profils'
    assert filament["textured_plate_temp"] == ["65"], "die eigene Betttemperatur für die Platte"
    assert filament["hot_plate_temp"] == ["55"], "die übrigen Platten bleiben beim Hersteller"


def test_a_field_that_serves_two_keys_never_speeds_up_the_second(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gemessen am 27.09.2026 an Anycubics Kobra 2 in OrcaSlicer: Der Vorschlag
    „Innenwand 142 mm/s“ hob die Lückenfüllung des Herstellers von 100 auf
    142 mm/s, weil Solidons Feld beide Schlüssel schreibt. Langsamer darf der
    mitbediente Schlüssel werden, schneller als beim Hersteller nicht."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    vendor = bestand.parent / "resources" / "profiles" / "Elegoo" / "process" / "ECC2"
    document = json.loads((vendor / "standard.json").read_text(encoding="utf-8"))
    document.update(
        {
            "inner_wall_speed": "150",
            "gap_infill_speed": "100",
            "sparse_infill_speed": "270",
            "internal_solid_infill_speed": ["250", "300"],
        }
    )
    _write(vendor / "standard.json", document)
    settings = print_settings.resolve(_cc2())
    settings = print_settings.with_accepted(settings, "speed.inner_wall", 142.0)
    settings = print_settings.with_choice(settings, "speed.infill", 200.0)

    process, _filament = _written(tmp_path, settings, _setup(bestand))

    assert process["inner_wall_speed"] == "142"
    assert process["gap_infill_speed"] == "100", "nicht schneller als beim Hersteller"
    assert process["sparse_infill_speed"] == "200"
    assert process["internal_solid_infill_speed"] == "200", "langsamer darf er werden"


def test_a_suggestion_slows_the_first_layer_and_never_speeds_its_walls(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Erste Schicht 50 mm/s" an schmalen Stegen (Roberts Minigolf-Platte,
    27.09.2026) schreibt Wände und Füllung der ersten Schicht. Liegen die Wände
    beim Hersteller bei 40, bleiben sie dort: Ein Vorschlag bremst, er
    beschleunigt nicht. Eine eigene Wahl im Dialog darf beides."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    vendor = bestand.parent / "resources" / "profiles" / "Elegoo" / "process" / "ECC2"
    document = json.loads((vendor / "standard.json").read_text(encoding="utf-8"))
    document.update({"initial_layer_speed": "40", "initial_layer_infill_speed": "105"})
    _write(vendor / "standard.json", document)
    base = print_settings.resolve(_cc2())
    suggested = print_settings.with_accepted(base, "speed.first_layer", 50.0)
    chosen = print_settings.with_choice(base, "speed.first_layer", 60.0)
    (tmp_path / "vorschlag").mkdir()
    (tmp_path / "wahl").mkdir()

    process, _filament = _written(tmp_path / "vorschlag", suggested, _setup(bestand))
    own, _filament = _written(tmp_path / "wahl", chosen, _setup(bestand))

    assert process["initial_layer_speed"] == "40", "der Vorschlag bremst, er beschleunigt nicht"
    assert process["initial_layer_infill_speed"] == "50"
    assert (own["initial_layer_speed"], own["initial_layer_infill_speed"]) == ("60", "60")


def test_the_check_holds_what_the_slicer_prints(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe meldete an jedem Auftrag für die P1S fünfzehn Werte als
    „anders übernommen" und an der Kobra 2 in OrcaSlicer zwei (gemessen
    27.09.2026). Bambu führt Werte je Düsenvariante als Liste und druckt die
    erste; Anycubic schreibt Prozente in Felder, die das Programm nicht liest.
    Beides stammt vom Hersteller. Geprüft wird, was Solidon schreibt, und eine
    Stichprobe der Grundlage (Entscheidung K)."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    vendor = bestand.parent / "resources" / "profiles" / "Elegoo"
    process = vendor / "process" / "ECC2" / "standard.json"
    document = json.loads(process.read_text(encoding="utf-8"))
    document.update({"inner_wall_speed": ["300", "400"], "initial_layer_speed": "50%"})
    _write(process, document)
    filament = vendor / "filament" / "ECC2" / "pla.json"
    document = json.loads(filament.read_text(encoding="utf-8"))
    document["filament_max_volumetric_speed"] = ["21", "29"]
    _write(filament, document)
    settings = print_settings.with_choice(print_settings.resolve(_cc2()), "shell.top_layers", 6)
    out = tmp_path / "out"
    out.mkdir()

    config = handover.write_config(settings, _cc2(), _setup(bestand), out)

    printed = {
        "inner_wall_speed": "300",
        "initial_layer_speed": "30",
        "filament_max_volumetric_speed": "21",
        "top_shell_layers": "6",
        "layer_height": "0.2",
        "wall_loops": "2",
        "support_threshold_angle": "30",
    }
    assert config.written["filament_max_volumetric_speed"] == "21"
    assert handover.verify_settings(printed, config.written) == []
    ignored = handover.verify_settings({**printed, "top_shell_layers": "5"}, config.written)
    assert ignored, "die eigene Wahl wird weiter geprüft"
    ignored = handover.verify_settings({**printed, "wall_loops": "3"}, config.written)
    assert ignored, "die Stichprobe der Grundlage auch"


def test_a_stage_lies_over_the_standard_process(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review Stufe A+B, F2: „Fein" blieb auf dem Herstellerprozess wirkungslos
    — die Grundlage las Elegoos 0,20 mm und schrieb die Schichthöhe nicht.
    Bis die Stufe ihren eigenen Prozess wählt (Stufe F), legt sie ihre Werte
    über den Standardprozess, und die Übergabe schreibt sie (Entscheidung I,
    Rückfall). Tempo und Wände, die die Stufe nicht ändert, bleiben Elegoos."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    fine = print_settings.resolve(_cc2(), "fine")

    base = manufacturer.base_settings(_cc2(), "fine", _setup(bestand))

    assert base.settings.layers.layer_height == pytest.approx(fine.layers.layer_height)
    assert base.settings.shell.wall_count == 2, "Fein ändert die Wände nicht — Elegoos zwei"
    assert "layers.layer_height" in base.staged
    assert not base.staged & base.from_profile
    process, _filament = _written(tmp_path, replace(fine, chosen=frozenset()), _setup(bestand))
    assert process["layer_height"] == f"{fine.layers.layer_height:g}"
    assert process["wall_loops"] == "2"
    assert process["outer_wall_speed"] == "160", "das Tempo bleibt beim Hersteller"


def test_a_chosen_process_is_the_stage(bestand: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Wer selbst einen anderen Prozess wählt, hat die Stufe damit gewählt:
    Über ihm liegt keine Stufe."""
    vendor = bestand.parent / "resources" / "profiles" / "Elegoo" / "process" / "ECC2"
    _write(
        vendor / "fine.json",
        {
            "type": "process",
            "name": "0.12mm Fine @CC2",
            "inherits": "fdm_process_common",
            "instantiation": "true",
            "layer_height": "0.12",
            "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
        },
    )
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    setup = replace(_setup(bestand), base_process="0.12mm Fine @CC2")

    base = manufacturer.base_settings(_cc2(), "strong", setup)

    assert not base.staged
    assert base.settings.layers.layer_height == pytest.approx(0.12)
    assert base.settings.shell.wall_count == 2, "keine fünf Wände von „Belastbar“ darüber"


def test_a_chosen_adhesion_kind_brings_its_measure(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review Stufe A+B, F4: Elegoos Standardprozess führt null Raft-Schichten
    und null Skirt-Runden. „Raft" schrieb die Art und behielt das Maß des
    Herstellers — gedruckt wurde kein Raft. Und „Keine" ließ einen Skirt des
    Herstellers stehen, weil sein Maß nie geschrieben wurde."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    vendor = bestand.parent / "resources" / "profiles" / "Elegoo" / "process" / "ECC2"
    document = json.loads((vendor / "standard.json").read_text(encoding="utf-8"))
    document.update({"raft_layers": "0", "skirt_loops": "3"})
    _write(vendor / "standard.json", document)
    base = manufacturer.base_settings(_cc2(), "standard", _setup(bestand)).settings
    assert base.adhesion.raft_layers == 0 and base.adhesion.skirt_loops == 3

    raft = print_settings.with_choice(base, "adhesion.kind", "raft")
    assert raft.adhesion.raft_layers == 3, "Solidons Vorgabe, weil das Maß auf null stand"
    assert raft.chosen == {"adhesion.kind", "adhesion.raft_layers"}
    process, _filament = _written(tmp_path, raft, _setup(bestand))
    assert process["raft_layers"] == "3"
    assert process["skirt_loops"] == "0", "der Skirt des Herstellers gehört nicht zum Raft"

    none = print_settings.with_choice(base, "adhesion.kind", "none")
    (tmp_path / "keine").mkdir()
    process, _filament = _written(tmp_path / "keine", none, _setup(bestand))
    assert process["skirt_loops"] == "0", "„Keine“ heißt auch kein Skirt"
    assert process["brim_type"] == "no_brim"


def test_automatic_adhesion_is_the_table_where_the_slicer_has_no_auto_brim() -> None:
    """Review Stufe A+B, F5: „Automatisch" gab CuraEngine einen Skirt mit null
    Linien und PrusaSlicer an jedem Teil einen Brim. Wo der Slicer keinen
    Auto-Brim kennt, gilt die Art aus Solidons Tabelle (Entscheidung J)."""
    profile = _cc2()
    table = print_settings.resolve(profile)
    automatic = print_settings.with_path(table, "adhesion.kind", "auto")
    automatic = print_settings.with_path(automatic, "adhesion.skirt_loops", 0)
    assert table.adhesion.kind == "skirt"

    cura = handover.values_for(automatic, profile, "cura")
    prusa = handover.values_for(automatic, profile, "prusa")
    orca = handover.values_for(automatic, profile, "orca")

    assert cura["adhesion_type"] == "skirt"
    assert cura["skirt_line_count"] == str(table.adhesion.skirt_loops)
    assert prusa["skirts"] == str(table.adhesion.skirt_loops)
    assert prusa["brim_width"] == "0"
    assert orca["brim_type"] == "auto_brim", "die Orca-Familie kennt ihn selbst"


def test_an_own_fan_ceiling_takes_the_lower_end_along(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review Stufe A+B, F7: Elegoo PLA fährt den Lüfter unten mit 50 %. Wer
    oben 20 % wählte, schrieb nur das obere Ende — und lange Schichten liefen
    mit 50, stärker gekühlt als verlangt."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    vendor = bestand.parent / "resources" / "profiles" / "Elegoo" / "filament" / "ECC2"
    document = json.loads((vendor / "pla.json").read_text(encoding="utf-8"))
    document.update({"fan_max_speed": ["100"], "fan_min_speed": ["50"]})
    _write(vendor / "pla.json", document)
    base = manufacturer.base_settings(_cc2(), "standard", _setup(bestand)).settings
    settings = print_settings.with_choice(base, "cooling.fan_speed", 0.2)

    _process, filament = _written(tmp_path, settings, _setup(bestand))

    assert filament["fan_max_speed"] == ["20"]
    assert filament["fan_min_speed"] == ["20"]


def test_the_title_follows_the_base_after_a_change() -> None:
    """Review Stufe A+B, H7: Nach einem Wechsel von PLA auf PETG stand „Standard ·
    PLA" über PETG-Werten — ``on_base`` trug Kennung und Titel aus dem alten
    Satz mit."""
    pla = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))
    petg = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    stored = print_settings.with_choice(pla, "shell.wall_count", 4)

    effective = print_settings.on_base(stored, petg)

    assert (effective.id, effective.title) == (petg.id, petg.title)
    assert effective.shell.wall_count == 4


def test_the_plates_come_from_the_filament_and_a_chosen_one_wins(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zur Wahl stehen die Platten, für die das Filament des Herstellers eine
    Betttemperatur nennt; 0 heißt gesperrt (Entscheidung F, Review R4)."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)

    base = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))
    chosen = manufacturer.base_settings(
        _cc2(), "standard", _setup(bestand, plate="High Temp Plate")
    )

    assert base.plates == {
        "High Temp Plate": 55,
        "Textured PEI Plate": 60,
        "Engineering Plate": 0,
    }
    assert base.plate == "Textured PEI Plate", "Elegoos Nummer 4"
    assert (chosen.plate, chosen.settings.temperature.bed) == ("High Temp Plate", 55)


def test_the_bed_temperature_belongs_to_the_fitted_plate(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review Stufe A+B, H14: Die Betttemperatur wurde zuerst aus
    ``hot_plate_temp`` gelesen und nur überschrieben, wenn der Schlüssel der
    aufliegenden Platte dastand. Fehlte er, zeigte die Grundlage die Temperatur
    der glatten Platte. Steht er auf 0, sperrt der Hersteller die Platte — dann
    sagt es ein Befund mit dem Weg in die Druckeinstellungen (R4)."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    vendor = bestand.parent / "resources" / "profiles" / "Elegoo" / "filament" / "ECC2"
    document = json.loads((vendor / "pla.json").read_text(encoding="utf-8"))
    for key in ("textured_plate_temp", "textured_plate_temp_initial_layer"):
        document.pop(key)
    _write(vendor / "pla.json", document)
    table = print_settings.resolve(_cc2())
    assert table.temperature.bed != 55, (
        "Vorbedingung: Solidons Wert ist nicht der der glatten Platte"
    )

    missing = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))
    refused = manufacturer.base_settings(
        _cc2(), "standard", _setup(bestand, plate="Engineering Plate")
    )

    assert missing.plate == "Textured PEI Plate"
    assert missing.settings.temperature.bed == table.temperature.bed, "nicht die 55 der glatten"
    assert refused.plate_refuses_filament
    assert [entry.code for entry in manufacturer.findings(refused)] == [
        "slicer.plate_refuses_filament"
    ]
    assert manufacturer.findings(refused)[0].suggestions


def test_a_printer_with_a_plate_choice_gets_no_guessed_plate(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review Stufe A+B, R4: Nennt eine Maschine mit Plattenwahl keine
    Standardplatte, riet Solidon die glatte. Jetzt nennt es keine und sagt es."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    common = bestand.parent / "resources" / "profiles" / "Elegoo" / "machine"
    document = json.loads((common / "fdm_machine_common.json").read_text(encoding="utf-8"))
    document.pop("default_bed_type")
    document["support_multi_bed_types"] = "1"
    _write(common / "fdm_machine_common.json", document)

    foundation = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))

    assert foundation.plate == ""
    assert [entry.code for entry in manufacturer.findings(foundation)] == ["slicer.plate_unknown"]


def test_a_user_template_finds_the_model_of_its_printer(tmp_path: Path) -> None:
    """Review Stufe A+B, R4: Eine eigene Vorlage liegt unter ``user/``, das
    Modell ihres Druckers beim Hersteller. Gesucht nur neben der Vorlage, fand
    Solidon keine Standardplatte und riet die glatte."""
    vendor = tmp_path / "resources" / "profiles"
    _write(
        vendor / "BBL" / "machine" / "Bambu Lab P1S.json",
        {
            "type": "machine_model",
            "name": "Bambu Lab P1S",
            "default_bed_type": "Textured PEI Plate",
        },
    )
    template = _write(
        tmp_path / "user" / "1" / "machine" / "Mein P1S.json",
        {"type": "machine", "name": "Mein P1S", "inherits": "Bambu Lab P1S 0.4 nozzle"},
    )

    model = manufacturer._machine_model(template, "Bambu Lab P1S", (vendor,))

    assert manufacturer.default_plate({}, model) == "Textured PEI Plate"


def test_an_unreadable_chosen_process_is_said(bestand: Path) -> None:
    """Review Stufe A+B, H13: Ließ sich ein gewählter Prozess nicht lesen, fiel
    die Übergabe still auf Solidons Tabelle zurück."""
    foundation = manufacturer.base_settings(
        _cc2(), "standard", replace(_setup(bestand), base_process="Gibt es nicht")
    )

    assert not foundation.has_profile
    assert foundation.unreadable == "Gibt es nicht"
    found = manufacturer.findings(foundation)
    assert [entry.code for entry in found] == ["slicer.process_unreadable"]
    assert found[0].suggestions


def test_the_first_layer_is_the_whole_first_layer(
    bestand: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Orca fährt die Füllung der ersten Schicht mit eigenem Tempo — am
    Centauri Carbon 2 105 mm/s, Wände und Brim 50. Solidons Feld erreichte sie
    nicht, und am Minigolf-Satz rissen genau die kurzen Bodenbahnen der
    schmalen Stege (27.09.2026). Der Dialog zeigt jetzt das schnellere Tempo,
    und eine eigene Wahl gilt beiden."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    vendor = bestand.parent / "resources" / "profiles" / "Elegoo"
    process = vendor / "process" / "ECC2" / "standard.json"
    document = json.loads(process.read_text(encoding="utf-8"))
    document.update({"initial_layer_speed": "50", "initial_layer_infill_speed": "105"})
    _write(process, document)

    base = manufacturer.base_settings(_cc2(), "standard", _setup(bestand))
    assert base.settings.speed.first_layer == pytest.approx(105.0)

    settings = print_settings.with_choice(print_settings.resolve(_cc2()), "speed.first_layer", 50)
    written, _filament = _written(tmp_path, settings, _setup(bestand))
    assert written["initial_layer_speed"] == "50"
    assert written["initial_layer_infill_speed"] == "50"
    prusa = handover.as_mapping(settings, "prusa")
    assert prusa["first_layer_speed"] == prusa["first_layer_infill_speed"] == "50"


def test_without_a_manufacturer_profile_solidon_writes_everything(tmp_path: Path) -> None:
    """Die Rückfallseite von Entscheidung D: Ohne Herstellerprofil ist Solidons
    Tabelle die Grundlage, und sie geht ganz hinaus — wie bisher."""
    settings = print_settings.resolve(_cc2())
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    process, filament = _written(tmp_path, settings, setup)

    assert process["wall_loops"] == str(settings.shell.wall_count)
    assert "curr_bed_type" not in process
    assert filament["cool_plate_temp"] == [str(settings.temperature.bed)], "wie bisher: jede Platte"


def test_switched_off_supports_do_not_name_a_type() -> None:
    """Hier stand ``none`` → ``normal(auto)``: Wer die Stützen im Slicerfenster
    einschaltete, bekam Gitter statt Elegoos Baum (Entscheidung J)."""
    settings = print_settings.resolve(_cc2())
    written = handover.as_mapping(settings, "orca")
    on = handover.as_mapping(print_settings.with_path(settings, "support.style", "auto"), "orca")
    grid = handover.as_mapping(print_settings.with_path(settings, "support.style", "grid"), "orca")

    assert written["enable_support"] == "0" and "support_type" not in written
    assert on["enable_support"] == "1" and "support_type" not in on
    assert grid["support_type"] == "normal(auto)"
    automatic = print_settings.with_path(settings, "adhesion.kind", "auto")
    assert handover.as_mapping(automatic, "orca")["brim_type"] == "auto_brim"
    assert slicer_keys.TABLES["orca"], "die Tabelle ist nicht leer"


# --- PrusaSlicer auf dem Bündel (Stufe C) ------------------------------------------

#: Ein Prusa-Bündel in der Staffelung, die PrusaResearch.ini 2.4.14 nutzt: eine
#: gemeinsame Basis je Art, der MK4S mit HF-Düse, zwei Prozesse und das PLA, das
#: den Rückzug des Druckers überstimmt. Werte wie gemessen am 27.09.2026, bis auf
#: die Prozentangaben, die es am MK4S in dieser Form nicht gibt.
_PRUSA_BUNDLE = r"""[vendor]
name = Prusa Research

[printer_model:MK4S]
name = Original Prusa MK4S
variants = HF0.4
default_materials = Prusament PLA @MK4S HF0.4

[printer:*common*]
printer_technology = FFF
gcode_flavor = marlin2
nozzle_diameter = 0.4
bed_shape = 0x0,250x0,250x210,0x210
max_print_height = 220
retract_length = 0.7
retract_speed = 35
retract_lift = 0.2
wipe = 0
binary_gcode = 1
machine_limits_usage = emit_to_gcode
printer_settings_id =
start_gcode = M862.3 P "[printer_model]" ; printer model check\nG29 P1 ; probe\nG29 A ; activate mbl

[printer:Original Prusa MK4S HF0.4 nozzle]
inherits = *common*
printer_model = MK4S
printer_variant = HF0.4
nozzle_high_flow = 1
default_print_profile = 0.20mm SPEED @MK4S HF0.4
default_filament_profile = "Prusament PLA @MK4S HF0.4"

[print:*common*]
layer_height = 0.2
first_layer_height = 0.2
extrusion_width = 0.45
first_layer_extrusion_width = 0.5
external_perimeter_extrusion_width = 0.45
perimeters = 2
top_solid_layers = 5
bottom_solid_layers = 3
fill_density = 15%
fill_pattern = grid
perimeter_speed = 250
external_perimeter_speed = 80%
infill_speed = 250
solid_infill_speed = 250
top_solid_infill_speed = 40%
gap_fill_speed = 120
first_layer_speed = 40
first_layer_infill_speed = 100
travel_speed = 300
bridge_speed = 50
default_acceleration = 4000
perimeter_acceleration = 3000
external_perimeter_acceleration = 0
support_material = 1
support_material_auto = 0
support_material_style = snug
support_material_threshold = 35
support_material_xy_spacing = 80%
support_material_spacing = 2
support_material_contact_distance = 0.2
support_material_interface_layers = 3
skirts = 0
compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]

[print:0.20mm SPEED @MK4S HF0.4]
inherits = *common*

[print:0.20mm STRUCTURAL @MK4S HF0.4]
inherits = *common*
support_material_threshold = 0

[filament:Prusament PLA @MK4S HF0.4]
filament_type = PLA
temperature = 230
first_layer_temperature = 230
bed_temperature = 60
first_layer_bed_temperature = 60
max_fan_speed = 100
min_fan_speed = 85
fan_always_on = 0
fan_below_layer_time = 100
slowdown_below_layer_time = 8
disable_fan_first_layers = 1
extrusion_multiplier = 1
filament_max_volumetric_speed = 24
filament_retract_length = 0.8
filament_retract_lift = nil
compatible_printers_condition = printer_model=="MK4S" and nozzle_high_flow[0]
"""


@pytest.fixture
def prusa_bundle(tmp_path: Path) -> Path:
    """PrusaSlicer mit dem nachgebauten Bündel, als Programmdatei daneben."""
    root = tmp_path / "PrusaSlicer" / "resources" / "profiles"
    root.mkdir(parents=True)
    (root / "PrusaResearch.ini").write_text(_PRUSA_BUNDLE, encoding="utf-8")
    executable = tmp_path / "PrusaSlicer" / "prusa-slicer-console.exe"
    executable.write_bytes(b"")
    return executable


def _prusa_setup(
    executable: Path, process: str = "0.20mm SPEED @MK4S HF0.4"
) -> handover.SlicerSetup:
    return handover.SlicerSetup(
        executable=executable,
        flavour="prusa",
        machine_profile="Original Prusa MK4S HF0.4 nozzle",
        base_process=process,
        base_filament="Prusament PLA @MK4S HF0.4",
    )


def _mk4s() -> Profile:
    return profiles.make_profile("prusa-mk4s", "pla")


def test_prusas_bundle_is_read_back_like_the_orca_family(prusa_bundle: Path) -> None:
    """Stufe C, Rücklesung: Drucker, Prozess und Filament des Bündels in
    Solidons Feldern. Prozentangaben gelten dem Wert, auf den PrusaSlicer sie
    bezieht; der Rückzug kommt vom Drucker, außer das Filament überstimmt ihn."""
    foundation = manufacturer.base_settings(_mk4s(), "standard", _prusa_setup(prusa_bundle))
    base = foundation.settings

    assert foundation.has_profile and not foundation.has_plates
    assert manufacturer.findings(foundation) == [], "keine Platte zu nennen"
    assert (base.shell.wall_count, base.shell.bottom_layers) == (2, 3)
    assert base.speed.first_layer == pytest.approx(100.0), "der Boden der ersten Schicht"
    assert base.speed.outer_wall == pytest.approx(200.0), "80 % der Wände"
    assert base.speed.top_surface == pytest.approx(100.0), "40 % der vollen Füllung"
    assert base.speed.outer_wall_acceleration == pytest.approx(3000.0), "null: die der Wände"
    assert base.support.style == "none", "nur an Verstärkern stützt nichts"
    assert base.support.threshold_angle == pytest.approx(55.0), "35 gegen die Waagerechte"
    assert base.support.xy_gap == pytest.approx(0.36), "80 % der Außenwand"
    assert base.support.density == pytest.approx(0.45 / 2.0)
    assert base.adhesion.kind == "none", "die Spüllinie steht im Startcode"
    assert base.retraction.length == pytest.approx(0.8), "das Filament überstimmt"
    assert base.retraction.z_hop == pytest.approx(0.2), "nil: der Wert des Druckers"
    assert base.cooling.minimum_fan_speed == pytest.approx(0.0), "ohne fan_always_on kein Minimum"
    assert base.temperature.nozzle == 230
    assert base.filament.max_flow == pytest.approx(24.0)
    assert not base.explicit


def test_a_slim_part_on_prusas_own_printer_gets_a_brim(prusa_bundle: Path) -> None:
    """Prusas eigene Drucker legen weder Skirt noch Brim, die Grundlage liest
    „keine" — und die hält einen Turm auf 16 mm² so wenig wie ein Skirt. Am
    MK4S bekam er ohne diese Lesart keinen Brim, weder für die Platte noch je
    Teil (Durchsicht 0.5.1, B3)."""
    base = manufacturer.base_settings(_mk4s(), "standard", _prusa_setup(prusa_bundle)).settings
    tower = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(4.0, 4.0, 80.0))

    assert base.adhesion.kind == "none"
    assert "adhesion.kind" in [
        entry.path for entry in advise.for_part(base, tower, 16.0, flavour="prusa")
    ]


def test_automatic_adhesion_uses_the_prusa_bundle_foundation(prusa_bundle: Path) -> None:
    """RM-341: Auto übernimmt bei einer Prusa-Grundlage deren Haftungsart."""
    profile = _mk4s()
    setup = _prusa_setup(prusa_bundle)
    foundation = manufacturer.base_settings(profile, "standard", setup)
    automatic = print_settings.with_choice(foundation.settings, "adhesion.kind", "auto")
    automatic = print_settings.with_choice(automatic, "adhesion.brim_width", 5.0)

    effective = handover.effective_adhesion(automatic, profile, "prusa", foundation)
    written, _expected = handover.prusa_values(automatic, profile, setup, console=False)

    assert foundation.has_profile
    assert foundation.settings.adhesion.kind == "none"
    assert effective.adhesion.kind == "none"
    assert written["skirts"] == "0"
    assert written["brim_width"] == "0"


def test_prusa_auto_preserves_multiple_native_adhesion_measures(prusa_bundle: Path) -> None:
    """RM-341: Auto lässt die gültige Mehrfach-Haftung des Prozesses bestehen."""
    profile = _mk4s()
    setup = _prusa_setup(prusa_bundle)
    bundle = prusa_bundle.parent / "resources" / "profiles" / "PrusaResearch.ini"
    source = bundle.read_text(encoding="utf-8")
    source = source.replace(
        "skirts = 0\n",
        "skirts = 2\nbrim_width = 5\nbrim_type = outer_only\nraft_layers = 0\n",
        1,
    )
    bundle.write_text(source, encoding="utf-8")

    foundation = manufacturer.base_settings(profile, "standard", setup)
    automatic = print_settings.with_choice(foundation.settings, "adhesion.kind", "auto")
    written, _expected = handover.prusa_values(automatic, profile, setup, console=False)

    assert foundation.has_profile
    assert foundation.settings.adhesion.kind == "brim"
    assert written["skirts"] == "2"
    assert written["brim_width"] == "5"
    # RM-432: Der Dialog zeigt genau, was hinausgeht — beide Arten, kein Raft.
    kind, kinds = handover.handed_over_adhesion_kinds(automatic, profile, "prusa", foundation)
    shown = set(print_settings.ADHESION_DETAILS) - print_settings.inactive_paths(
        "auto", kind, also=kinds
    )
    assert shown == {"adhesion.skirt_loops", "adhesion.skirt_distance", "adhesion.brim_width"}

    chosen_skirt = print_settings.with_choice(automatic, "adhesion.skirt_loops", 4)
    changed, _expected = handover.prusa_values(chosen_skirt, profile, setup, console=False)

    assert changed["skirts"] == "4"
    assert changed["brim_width"] == "5"
    assert written["brim_type"] == "outer_only"
    assert written["raft_layers"] == "0"

    chosen_width = print_settings.with_choice(automatic, "adhesion.brim_width", 7.0)
    changed, _expected = handover.prusa_values(chosen_width, profile, setup, console=False)
    assert changed["skirts"] == "2"
    assert changed["brim_width"] == "7"
    assert changed["brim_type"] == "outer_only"
    assert changed["raft_layers"] == "0"


def test_prusas_automatic_support_angle_is_half_an_outer_wall(prusa_bundle: Path) -> None:
    """Null heißt bei PrusaSlicer „automatisch": überhängend ist, was mehr als
    die halbe Außenwand über die Schicht darunter ragt — bei 0,45 mm und
    0,2 mm Schicht 48,4° gegen die Senkrechte. Ein gewählter Prozess ist die
    Stufe; nichts wird über ihn gelegt."""
    setup = _prusa_setup(prusa_bundle, "0.20mm STRUCTURAL @MK4S HF0.4")

    foundation = manufacturer.base_settings(_mk4s(), "fine", setup)

    assert foundation.settings.support.threshold_angle == pytest.approx(48.37, abs=0.01)
    assert not foundation.staged, "der Prozess ist nicht der Standard der Maschine"


def test_without_prusas_printer_the_base_is_solidons_table(prusa_bundle: Path) -> None:
    """Das Bündel kennt den Centauri Carbon 2 nicht. Dann bleibt Solidons
    Tabelle die Grundlage, und der Befund sagt es — PrusaSlicer druckte sonst
    mit seinem eingebauten Startcode, ohne Bettvermessung und Spüllinie."""
    profile = _cc2()
    setup = replace(_prusa_setup(prusa_bundle), machine_profile="")

    foundation = manufacturer.base_settings(profile, "standard", setup)
    values, _expected = handover.prusa_values(
        print_settings.resolve(profile), profile, setup, console=True
    )

    assert not foundation.has_profile
    assert foundation.settings == print_settings.resolve(profile)
    assert values["filament_type"] == "PLA", "PETG ging sonst als PLA hinaus (B11)"
    assert "bed_shape" in values and "start_gcode" not in values
    assert [f.code for f in handover.machine_missing(setup, profile)] == ["slicer.printer_unknown"]


@pytest.mark.parametrize("with_bundle", [False, True])
def test_prusa_writes_flex_and_reports_its_missing_filament(
    prusa_bundle: Path, with_bundle: bool
) -> None:
    """Ohne Herstellerfilament bleibt TPU lauffähig und die Herkunft sichtbar."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    setup = replace(_prusa_setup(prusa_bundle), base_filament="")
    if not with_bundle:
        setup = replace(setup, base_process="")
    foundation = manufacturer.base_settings(profile, "standard", setup)

    written, _expected = handover.prusa_values(foundation.settings, profile, setup, console=True)
    findings = handover.foundation_findings(foundation.settings, profile, setup)

    assert written["filament_type"] == "FLEX"
    assert "filament_settings_id" not in written
    assert [entry.code for entry in findings] == ["slicer.filament_from_table"]
    assert findings[0].values["source"] == "solidon_table"
    assert findings[0].suggestions
    assert (
        foundation.settings.temperature.nozzle == print_settings.resolve(profile).temperature.nozzle
    )


def test_prusa_keeps_a_flexible_filaments_start_code(prusa_bundle: Path) -> None:
    """Die richtige Vorwahl übernimmt die eigene Startsequenz des Filaments."""
    from app.core.export import slicer_profiles

    bundle = prusa_bundle.parent / "resources" / "profiles" / "PrusaResearch.ini"
    with bundle.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n[filament:Generic FLEX @MK4S]\nfilament_type = FLEX\n"
            "filament_vendor = Generic\ntemperature = 230\nfirst_layer_temperature = 230\n"
            "start_filament_gcode = M900 K0 ; Filament gcode\n"
        )
    found = slicer_profiles.find_profiles(prusa_bundle, "prusa", ("machine", "filament"))
    machine = next(entry for entry in found if entry.kind == "machine")
    filament = slicer_profiles.match_filament(found, machine, "TPU")
    assert filament is not None
    setup = replace(_prusa_setup(prusa_bundle), base_filament=slicer_profiles.identity(filament))
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    foundation = manufacturer.base_settings(profile, "standard", setup)

    written, _expected = handover.prusa_values(foundation.settings, profile, setup, console=True)

    assert written["filament_type"] == "FLEX"
    assert written["filament_settings_id"] == "Generic FLEX @MK4S"
    assert written["start_filament_gcode"] == "M900 K0 ; Filament gcode"
    assert handover.foundation_findings(foundation.settings, profile, setup) == []


def test_a_missing_filament_does_not_hide_an_unknown_plate() -> None:
    """Materialherkunft und unbekannte Platte brauchen beide ihren Hinweis."""
    foundation = manufacturer.Foundation(
        print_settings.resolve(_cc2()),
        from_profile=frozenset({"shell.wall_count"}),
        material_from_table=True,
    )

    assert [entry.code for entry in manufacturer.findings(foundation)] == [
        "slicer.filament_from_table",
        "slicer.plate_unknown",
    ]


def test_orca_receives_a_prusa_flex_slot_as_tpu_without_losing_its_profile(tmp_path: Path) -> None:
    """Eine importierte FLEX-Spule ist für Orca TPU und behält passende Herstellerwerte."""
    filament = _write(
        tmp_path / "filament.json",
        {
            "type": "filament",
            "name": "Generic TPU",
            "filament_type": ["TPU"],
            "filament_start_gcode": ["M900 K0"],
        },
    )
    profile = profiles.make_profile("centauri-carbon-2", "tpu-95a")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(Path("orca-slicer.exe"), "orca", base_filament=str(filament))
    slot = MaterialSlot(index=0, name="Flexible Spule", material_type="FLEX")

    config = handover.write_config(settings, profile, setup, tmp_path, (slot,))
    document = json.loads(config.filaments[0].read_text(encoding="utf-8"))

    assert document["filament_type"] == ["TPU"]
    assert document["filament_start_gcode"] == ["M900 K0"]


def test_prusa_gets_the_whole_chain_and_only_the_deviation(prusa_bundle: Path) -> None:
    """Die Abnahme von Stufe C, nachgestellt: Ohne eigene Wahl steht in der
    Datei, was PrusaSlicer mit den drei Profilen im Fenster druckt — Startcode
    mit Bettvermessung, ``marlin2``, zwei Wände —, dazu nur die Namen und im
    Konsolenlauf das Textformat. Bis dahin waren es 63 Schlüssel über
    PrusaSlicers eingebauten Vorgaben."""
    profile = _mk4s()
    setup = _prusa_setup(prusa_bundle)
    settings = manufacturer.effective(None, manufacturer.base_settings(profile, "standard", setup))

    console, expected = handover.prusa_values(settings, profile, setup, console=True)
    window, _expected = handover.prusa_values(settings, profile, setup, console=False)

    assert "G29 A" in console["start_gcode"] and console["gcode_flavor"] == "marlin2"
    assert console["perimeters"] == "2"
    assert console["machine_limits_usage"] == "emit_to_gcode", "die Grenzen des Druckers"
    assert console["printer_settings_id"] == "Original Prusa MK4S HF0.4 nozzle"
    assert console["print_settings_id"] == "0.20mm SPEED @MK4S HF0.4"
    assert console["filament_settings_id"] == "Prusament PLA @MK4S HF0.4"
    assert console["binary_gcode"] == "0" and window["binary_gcode"] == "1"
    assert not {"inherits", "compatible_printers_condition"} & console.keys()
    assert set(expected) == {
        "layer_height",
        "perimeters",
        "support_material_threshold",
        *handover.PRUSA_IDENTITY,
    }, "geprüft wird die Grundlage, abweichen tut nichts"


@pytest.mark.parametrize("vendor", ["170", "80%"])
def test_a_slower_outer_wall_reaches_prusas_small_perimeters(
    prusa_bundle: Path, vendor: str
) -> None:
    """RM-463, Rückschritt gegen 0.5.0: Kleine Umfänge fuhren schneller als die Außenwand.

    PrusaSlicer 2.9.6 an der MK4S: Solidon schrieb die Außenwand mit 160 mm/s,
    der Stiel lief mit 170, denn das Bündel führt ``small_perimeter_speed``
    absolut (oder als Anteil der Innenwand, hier 80 % von 250). Wer die
    Außenwand bremst, bremst die kleinen Umfänge mit; schneller wird keiner.
    """
    profile = _mk4s()
    setup = _prusa_setup(prusa_bundle)
    bundle = prusa_bundle.parent / "resources" / "profiles" / "PrusaResearch.ini"
    source = bundle.read_text(encoding="utf-8")
    bundle.write_text(
        source.replace(
            "gap_fill_speed = 120\n", f"gap_fill_speed = 120\nsmall_perimeter_speed = {vendor}\n", 1
        ),
        encoding="utf-8",
    )
    base = manufacturer.effective(None, manufacturer.base_settings(profile, "standard", setup))

    untouched, _expected = handover.prusa_values(base, profile, setup, console=True)
    slower = print_settings.with_choice(base, "speed.outer_wall", 160.0)
    braked, expected = handover.prusa_values(slower, profile, setup, console=True)
    faster = print_settings.with_choice(base, "speed.outer_wall", 230.0)
    unbraked, _expected = handover.prusa_values(faster, profile, setup, console=True)

    assert untouched["small_perimeter_speed"] == vendor, "ohne Wahl gilt der Hersteller"
    assert braked["external_perimeter_speed"] == "160"
    assert braked["small_perimeter_speed"] == "160"
    assert expected["small_perimeter_speed"] == "160", "die Gegenprobe kennt den Wert"
    assert unbraked["small_perimeter_speed"] == vendor, "schneller wird keine Rolle"


def test_the_orca_family_brakes_absolute_small_perimeters_with_the_outer_wall() -> None:
    """Dieselbe Rolle in der Orca-Familie: 23 bis 55 Prozesse führen sie absolut (RM-463).

    Ein Anteil bezieht sich dort auf die Außenwand und bleibt, wie er ist.
    """
    own = {"outer_wall_speed": "120"}

    assert handover._roles_not_faster(
        {"small_perimeter_speed": "150"}, own, handover._ORCA_ROLES
    ) == {"small_perimeter_speed": "120"}
    assert (
        handover._roles_not_faster({"small_perimeter_speed": "50%"}, own, handover._ORCA_ROLES)
        == {}
    )
    assert (
        handover._roles_not_faster({"small_perimeter_speed": "100"}, own, handover._ORCA_ROLES)
        == {}
    )
    assert (
        handover._roles_not_faster({"small_perimeter_speed": "150"}, {}, handover._ORCA_ROLES) == {}
    )


def test_prusa_supports_switched_on_are_automatic_supports(prusa_bundle: Path) -> None:
    """Prusas Vorgabe stützt nur an gemalten Verstärkern. Wer Stützen
    einschaltet, bekommt beide Schalter; der Stil bleibt der des Bündels
    (Entscheidung J)."""
    profile = _mk4s()
    setup = _prusa_setup(prusa_bundle)
    base = manufacturer.effective(None, manufacturer.base_settings(profile, "standard", setup))
    settings = print_settings.with_choice(base, "support.style", "auto")

    values, expected = handover.prusa_values(settings, profile, setup, console=True)

    assert values["support_material"] == values["support_material_auto"] == "1"
    assert values["support_material_style"] == "snug"
    assert expected["support_material"] == "1"


def test_a_prusa_suggestion_slows_the_first_layer_and_a_choice_reaches_the_filament(
    prusa_bundle: Path,
) -> None:
    """Dieselben Regeln wie bei der Orca-Familie: Ein Vorschlag bremst nur —
    „erste Schicht 50" legt den Boden langsamer und lässt die Wände bei 40.
    Ein gewählter Rückzug steht auch am Filament, das ihn sonst überstimmte."""
    profile = _mk4s()
    setup = _prusa_setup(prusa_bundle)
    base = manufacturer.effective(None, manufacturer.base_settings(profile, "standard", setup))
    suggested = print_settings.with_accepted(base, "speed.first_layer", 50.0)
    retraction = print_settings.with_choice(base, "retraction.length", 1.2)

    slowed, _expected = handover.prusa_values(suggested, profile, setup, console=True)
    retracted, _expected = handover.prusa_values(retraction, profile, setup, console=True)

    assert slowed["first_layer_infill_speed"] == "50"
    assert slowed["first_layer_speed"] == "40", "die Wände nicht schneller"
    assert retracted["retract_length"] == retracted["filament_retract_length"] == "1.2"


def test_a_spool_writes_only_what_it_changes_over_its_manufacturer(
    bestand: Path, prusa_bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review Stufe A+B, H15: Eine Spulenübersteuerung ist gruppenweise,
    vorbelegt mit den Werten, die ohne sie gälten. Wer nur die Düse ändert,
    schreibt nicht Bett und erste Schicht mit über das Herstellerfilament.
    Und über Prusas Bündel geht sie überhaupt hinaus — die erste Spule fährt
    den Satz."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    slot = MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))

    def spool(profile: Profile, setup: handover.SlicerSetup) -> PrintSettings:
        base = manufacturer.effective(None, manufacturer.base_settings(profile, "standard", setup))
        hotter = replace(base.temperature, nozzle=base.temperature.nozzle + 15)
        return replace(
            base,
            slot_overrides=(SlotOverride(name="Rot", colour=slot.colour, temperature=hotter),),
        )

    orca = spool(_cc2(), _setup(bestand))
    out = tmp_path / "orca"
    out.mkdir()
    config = handover.write_config(orca, _cc2(), _setup(bestand), out, slots=(slot,))
    assert config.filament is not None
    filament = json.loads(config.filament.read_text(encoding="utf-8"))
    prusa = spool(_mk4s(), _prusa_setup(prusa_bundle))
    values, expected = handover.prusa_values(
        prusa, _mk4s(), _prusa_setup(prusa_bundle), (slot,), console=True
    )

    assert filament["nozzle_temperature"] == ["225"], "Elegoos 210 und 15 mehr"
    assert filament["textured_plate_temp"] == ["60"], "das Bett bleibt beim Hersteller"
    assert "nozzle_temperature" in config.written
    assert values["temperature"] == expected["temperature"] == "245"
    assert "first_layer_temperature" not in expected, "nicht geändert, nicht geschrieben"


def test_the_analysis_supports_where_the_chosen_process_supports(prusa_bundle: Path) -> None:
    """Entscheidung L: Die Schichtanalyse stützt ab der Schwelle, mit der der
    Slicer stützt. Prusas „STRUCTURAL" stützt automatisch ab 48,4° gegen die
    Senkrechte, der MK4S in Solidons Tabelle ab 55°. Die Analyse folgt dem
    Prozess, und der Ratgeber schlägt keine zweite Schwelle vor — bis dahin
    riet er am SV06, den Wert des Herstellers mit Solidons zu überschreiben."""
    profile = _mk4s()
    setup = _prusa_setup(prusa_bundle, "0.20mm STRUCTURAL @MK4S HF0.4")
    printed = manufacturer.effective(None, manufacturer.base_settings(profile, "fine", setup))

    process = profiles.for_process(profile, printed, effective=True)

    assert profile.overhang_limit_degrees == pytest.approx(55.0)
    assert process.overhang_limit_degrees == pytest.approx(48.37, abs=0.01)
    paths = {entry.path for entry in advise.advise(printed, process)}
    assert "support.threshold_angle" not in paths
    assert "support.threshold_angle" in {
        entry.path for entry in advise.advise(printed, profiles.for_process(profile, printed))
    }, "gegen die Tabelle gerechnet stand der Vorschlag"


def test_a_stored_threshold_is_the_analysis_limit_only_as_a_choice() -> None:
    """Ein Projekt aus 0.5.0 trägt die Startregel von 45 Grad, ohne dass sie
    jemand gewählt hat. Aus dem gespeicherten Satz gilt die Schwelle darum nur
    als eigene Wahl; aus den wirksamen Einstellungen immer, denn dort steht die
    des Herstellers darunter. Eine gedruckte Probe geht beidem vor
    (``Profile.overhang_limit_degrees``, test_calibration)."""
    profile = _cc2()
    resolved = print_settings.resolve(profile)
    legacy = print_settings.with_path(resolved, "support.threshold_angle", 45.0)
    chosen = print_settings.with_choice(resolved, "support.threshold_angle", 50.0)

    assert profiles.for_process(profile, legacy).overhang_limit_degrees == pytest.approx(60.0)
    assert profiles.for_process(profile, chosen).overhang_limit_degrees == pytest.approx(50.0)
    assert profiles.for_process(
        profile, legacy, effective=True
    ).overhang_limit_degrees == pytest.approx(45.0)


def test_the_session_evaluates_with_what_the_window_prints() -> None:
    """Der Anschluss von Entscheidung L: Die Sitzung holt die wirksamen
    Einstellungen des Fensters vor dem Lauf, und Prüfbericht und Szene
    rechnen mit deren Schwelle. Kommt die Grundlage des Herstellers erst
    danach, sagt ``evaluation_follows``, ob ein zweiter Lauf nötig ist."""
    from app.ui.session import Session

    session = Session()
    meshes = Path(__file__).parent / "data" / "meshes"
    assert session.import_model(meshes / "near_sphere_ellipsoid.stl", unit="mm")
    stored = session.profile.overhang_limit_degrees
    printed = print_settings.with_path(
        print_settings.resolve(session.profile), "support.threshold_angle", 40.0
    )

    class Window:
        def effective_print_settings(self) -> PrintSettings:
            return printed

    window = Window()
    session.follow_print_settings(window.effective_print_settings)
    assert session.evaluation_profile.overhang_limit_degrees == pytest.approx(stored)
    result = session.evaluate_now()

    assert stored != pytest.approx(40.0)
    assert session.evaluation_profile.overhang_limit_degrees == pytest.approx(40.0)
    assert result.scene.profile is not None
    assert result.scene.profile.overhang_limit_degrees == pytest.approx(40.0)
    assert session.evaluation_follows(printed)
    later = print_settings.with_path(printed, "support.threshold_angle", 52.0)
    assert not session.evaluation_follows(later), "die Grundlage kam mit einer anderen"


def test_the_stage_takes_the_manufacturers_process(
    bestand: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stufe F (Entscheidung I): „Fein" nimmt Elegoos „0.12mm Fine", statt
    Solidons Stufe über den Standardprozess zu legen. Gesucht wird unter den
    Geschwistern mit demselben Zusatz — der Prozess für die 0,6-mm-Düse daneben
    zählt nicht. Findet sich keiner, bleibt der Standard und die Stufe liegt
    darüber; ein selbst gewählter Prozess bleibt, wie er ist."""
    monkeypatch.setattr(handover, "_fits_the_printer", lambda _machine, _profile: True)
    folder = bestand.parent / "resources" / "profiles" / "Elegoo" / "process" / "ECC2"
    for file, name, layer in (
        ("fine.json", "0.12mm Fine @CC2", "0.12"),
        ("fine06.json", "0.18mm Fine @CC2 0.6 nozzle", "0.18"),
    ):
        _write(
            folder / file,
            {
                "type": "process",
                "name": name,
                "inherits": "fdm_process_common",
                "instantiation": "true",
                "layer_height": layer,
                "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
            },
        )
    setup = _setup(bestand)

    fine = manufacturer.for_stage(setup, _cc2(), "fine")
    foundation = manufacturer.base_settings(_cc2(), "fine", fine)

    assert fine is not None and Path(fine.base_process).name == "fine.json"
    assert foundation.settings.layers.layer_height == pytest.approx(0.12)
    assert not foundation.staged, "nichts liegt mehr über dem Prozess"
    assert manufacturer.for_stage(setup, _cc2(), "strong") == setup
    assert manufacturer.base_settings(_cc2(), "strong", setup).staged, "die Stufe liegt darüber"
    assert manufacturer.for_stage(fine, _cc2(), "draft") == fine, "eine eigene Wahl bleibt"
    assert manufacturer.for_stage(setup, _cc2(), "standard") == setup


def test_prusas_stage_takes_its_structural_process(prusa_bundle: Path) -> None:
    """Dieselbe Zuordnung im Prusa-Bündel: „Belastbar" nimmt „0.20mm
    STRUCTURAL", und dessen automatische Stützschwelle gilt; eine feine Stufe
    führt das nachgebaute Bündel nicht."""
    setup = _prusa_setup(prusa_bundle)

    strong = manufacturer.for_stage(setup, _mk4s(), "strong")

    assert strong is not None and strong.base_process == "0.20mm STRUCTURAL @MK4S HF0.4"
    foundation = manufacturer.base_settings(_mk4s(), "strong", strong)
    assert foundation.process == "0.20mm STRUCTURAL @MK4S HF0.4" and not foundation.staged
    assert foundation.settings.support.threshold_angle == pytest.approx(48.37, abs=0.01)
    assert manufacturer.for_stage(setup, _mk4s(), "fine") == setup
