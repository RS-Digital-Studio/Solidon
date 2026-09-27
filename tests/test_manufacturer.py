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
from app.core.types import PrintSettings, Profile


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
