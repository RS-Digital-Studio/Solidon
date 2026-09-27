"""CuraEngine bekommt seine Maschine (Konzept „Herstellerprofil als Grundlage", Stufe D).

CuraEngine liest aus einer Definition nur Vorgabewerte und füllt keine
Platzhalter; das Cura-Fenster tut beides, bevor es die Rechenmaschine ruft.
Bis zum 27.09.2026 bekam die Konsole deshalb immer ``fdmprinter`` — mit
dessen Startcode ``G28``, ``G1 Z15`` und drei Millimetern Filament in der
Luft, ohne Spüllinie und ohne Bettnetz, gleich welcher Drucker. Jetzt wählt
die Übergabe die Druckerdefinition (``PrinterProfile.cura_definition``),
reicht Start- und Endcode mit gefüllten Platzhaltern als eigene Werte weiter
und schaltet Curas eigene Temperaturbefehle ab, wo der Startcode sie setzt.

Die Installation wird hier nachgebaut, nach Cura 5.13
(``share/cura/resources/definitions`` und ``extruders``); ein Test am Ende
prüft die echte, wenn sie da ist.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.errors import ExternalToolError, ValidationError
from app.core.export import handover
from app.core.knowledge import print_settings, profiles

#: Der Startcode des K1 Max in Cura 5.13 (``creality_k1max.def.json``), wörtlich.
K1_MAX_START = (
    "M140 S0\nM104 S0 \nSTART_PRINT EXTRUDER_TEMP={material_print_temperature_layer_0} "
    "BED_TEMP={material_bed_temperature_layer_0}\n"
)


def _cura(tmp_path: Path, start: str = K1_MAX_START, end: str = "END_PRINT") -> Path:
    """Eine Cura-Installation mit ``fdmprinter``, einem K1 Max und seinem Extruderzug."""
    install = tmp_path / "UltiMaker Cura 5.13.0"
    resources = install / "share" / "cura" / "resources"
    definitions = resources / "definitions"
    extruders = resources / "extruders"
    definitions.mkdir(parents=True)
    extruders.mkdir(parents=True)
    machine = {
        "machine_start_gcode": {
            "default_value": "G28 ;Home\nG1 Z15.0 F6000 ;Move the platform down 15mm"
        },
        "machine_end_gcode": {"default_value": "M104 S0\nM84"},
        "machine_depth": {"default_value": 100},
        "machine_name": {"default_value": "Unknown"},
        "gantry_height": {"default_value": 99999, "value": "machine_height"},
    }
    (definitions / "fdmprinter.def.json").write_text(
        json.dumps(
            {
                "version": 2,
                "name": "FFF",
                "metadata": {
                    "setting_version": 27,
                    "machine_extruder_trains": {"0": "fdmextruder"},
                },
                "settings": {"machine_settings": {"children": machine}},
            }
        ),
        encoding="utf-8",
    )
    (definitions / "fdmextruder.def.json").write_text(
        json.dumps({"version": 2, "name": "Extruder", "settings": {}}), encoding="utf-8"
    )
    (definitions / "creality_k1max.def.json").write_text(
        json.dumps(
            {
                "version": 2,
                "name": "Creality K1 Max",
                "inherits": "fdmprinter",
                "metadata": {"machine_extruder_trains": {"0": "creality_k1max_extruder_0"}},
                "overrides": {
                    "machine_start_gcode": {"default_value": start},
                    "machine_end_gcode": {"default_value": end},
                    "machine_name": {"default_value": "Creality K1 Max"},
                    "gantry_height": {"value": 45},
                },
            }
        ),
        encoding="utf-8",
    )
    (extruders / "creality_k1max_extruder_0.def.json").write_text(
        json.dumps({"version": 2, "name": "Extruder 1", "inherits": "fdmextruder"}),
        encoding="utf-8",
    )
    engine = install / "CuraEngine.exe"
    engine.write_bytes(b"")
    return engine


def _written(engine: Path, printer: str, tmp_path: Path) -> handover.SlicerConfig:
    profile = profiles.make_profile(printer, "pla")
    setup = handover.SlicerSetup(engine, "cura")
    return handover.write_config(print_settings.resolve(profile), profile, setup, tmp_path)


def _argument(command: list[str], key: str) -> str:
    """Der Wert hinter ``-s key=…`` — genau einer, sonst stimmt die Übergabe nicht."""
    found = [entry for entry in command if entry.startswith(f"{key}=")]
    assert len(found) == 1, f"{key}: {len(found)}-mal in der Kommandozeile"
    return found[0].split("=", 1)[1]


def test_cura_gets_the_start_code_of_its_printer(tmp_path: Path) -> None:
    """Der K1 Max bekommt ``START_PRINT`` mit seinen Temperaturen, nicht ``G28``.

    Gemessen am 27.09.2026 mit CuraEngine 5.13: Die Konsole löst die Erbkette
    der Druckerdefinition selbst auf, braucht für den Extruderzug aber den
    Ordner ``extruders`` hinter ``-d``. Ein ``-e0 -j fdmextruder.def.json``
    darüber setzte die Vorgaben des Zugs zurück und fällt deshalb weg.
    """
    engine = _cura(tmp_path)
    config = _written(engine, "creality-k1-max", tmp_path)
    settings = print_settings.resolve(profiles.make_profile("creality-k1-max", "pla"))

    command = handover._command(
        handover.SlicerSetup(engine, "cura"), [tmp_path / "teil.stl"], config, tmp_path
    )

    definitions = engine.parent / "share" / "cura" / "resources" / "definitions"
    assert command[command.index("-j") + 1] == str(definitions / "creality_k1max.def.json")
    assert command.index("-d") < command.index("-j"), "die Suchpfade vor der Definition"
    assert command[command.index("-d") + 1].split(os.pathsep) == [
        str(definitions),
        str(definitions.parent / "extruders"),
    ]
    start = _argument(command, "machine_start_gcode")
    assert start == (
        f"M140 S0\nM104 S0 \nSTART_PRINT EXTRUDER_TEMP={settings.temperature.nozzle_first_layer} "
        f"BED_TEMP={settings.temperature.bed_first_layer}\n"
    )
    assert _argument(command, "machine_end_gcode") == "END_PRINT"
    assert "fdmextruder.def.json" not in " ".join(command), "der Zug kommt aus der Definition"
    assert command.index("machine_start_gcode=" + start) < command.index("-e0"), "global"


def test_a_calculation_in_a_placeholder_goes_through_solidons_own_evaluator(
    tmp_path: Path,
) -> None:
    """``{machine_depth - 5}`` im Endcode des Neptune 4 — Rechnung ohne ``eval``.

    Die Tiefe ist die, die Solidon schreibt, nicht die der Definition: Beide
    beschreiben dieselbe Maschine, und gedruckt wird mit Solidons Bauraum.
    Dazu ``{name, 0}`` (Wert des ersten Zugs) und ein Name, den das Fenster
    unter einem zweiten führt (``print_temperature``).
    """
    engine = _cura(
        tmp_path,
        start="M109 S{print_temperature, 0}\nM190 S{material_bed_temperature,0}",
        end="G1 X0 Y{machine_depth - 5} ;Present print\nM84",
    )
    config = _written(engine, "creality-k1-max", tmp_path)
    profile = profiles.make_profile("creality-k1-max", "pla")
    settings = print_settings.resolve(profile)

    assert config.cura_machine is not None
    codes = config.cura_machine.codes
    assert codes["machine_start_gcode"] == (
        f"M109 S{settings.temperature.nozzle}\nM190 S{settings.temperature.bed}"
    )
    depth = profile.printer.build_volume[1]
    assert codes["machine_end_gcode"] == f"G1 X0 Y{depth - 5:g} ;Present print\nM84"


@pytest.mark.parametrize(
    "start",
    [
        "{if material_type == 'PLA'}M104 S200{endif}",
        "M117 {print_time}",
        "M104 S{material_print_temperature, initial_extruder_nr}",
        "SET_PARAM VALUE={unbekannter_wert}",
        "G1 Y{machine_depth - machine_name}",
    ],
)
def test_a_placeholder_solidon_cannot_fill_stops_the_handover(tmp_path: Path, start: str) -> None:
    """Wörtlich im G-Code bräche ``START_PRINT EXTRUDER_TEMP={…}`` am Drucker ab.

    Gemessen im Prüfbericht: CuraEngine ersetzt keinen Platzhalter, die Zeile
    stand unverändert in der Druckdatei. Was Solidon nicht füllen kann, hält
    die Übergabe an und sagt, wohin es weitergeht (Regel 17, 21).
    """
    engine = _cura(tmp_path, start=start)

    with pytest.raises(ExternalToolError) as caught:
        _written(engine, "creality-k1-max", tmp_path)

    assert caught.value.values["setting"] == "machine_start_gcode"
    assert "{" in str(caught.value.values["text"])
    assert [action.id for action in caught.value.suggestions] == ["choose_slicer", "export_only"]


@pytest.mark.parametrize(
    ("start", "bed", "nozzle"),
    [
        (K1_MAX_START, "false", "false"),
        ("M190 S{material_bed_temperature_layer_0}\nG28", "false", "true"),
        ("M109 S{material_print_temperature_layer_0}\nG28", "true", "false"),
        ("G28 ;Home\nM420 S1", "true", "true"),
        # Ein Platzhalter im Kommentar setzt nichts — das Fenster streicht
        # Kommentare, bevor es sucht.
        ("G28 ; heizt auf {material_bed_temperature}\nM420 S1", "true", "true"),
    ],
)
def test_curas_own_temperature_commands_stay_out_where_the_start_code_sets_them(
    tmp_path: Path, start: str, bed: str, nozzle: str
) -> None:
    """Genau ein ``M190``/``M109``: Curas eigenes vor dem Startcode nur, wo er keines setzt.

    Dieselbe Regel wie ``StartSliceJob.py`` im Fenster. Ohne sie stand am K1
    Max ``M190 S60`` vor ``START_PRINT … BED_TEMP=60`` (Prüfbericht §1.3).
    """
    engine = _cura(tmp_path, start=start)

    config = _written(engine, "creality-k1-max", tmp_path)

    assert config.written["material_bed_temp_prepend"] == bed
    assert config.written["material_print_temp_prepend"] == nozzle
    lines = config.process.read_text(encoding="utf-8").splitlines()
    assert f"material_bed_temp_prepend={bed}" in lines, "die Schalter reisen mit den Werten"


def test_a_printer_cura_does_not_know_prints_with_fdmprinter_and_says_so(
    tmp_path: Path,
) -> None:
    """Der Centauri Carbon 2 steht nicht in Cura — dann ``fdmprinter`` und ein Befund.

    ``machine_missing`` schwieg für Cura bis zum 27.09.2026 („Bauart, kein
    Mangel“). Für die erste Schicht ist es einer: kein Startcode des
    Herstellers, keine Spüllinie, kein Bettnetz.
    """
    engine = _cura(tmp_path)
    setup = handover.SlicerSetup(engine, "cura")
    unknown = profiles.make_profile("centauri-carbon-2", "pla")
    known = profiles.make_profile("creality-k1-max", "pla")
    config = _written(engine, "centauri-carbon-2", tmp_path)

    command = handover._command(setup, [tmp_path / "teil.stl"], config, tmp_path)

    assert command[command.index("-j") + 1].endswith("fdmprinter.def.json")
    assert "-d" not in command
    assert command[command.index("-e0") + 1] == "-j", "fdmprinter braucht seinen Zug"
    assert _argument(command, "machine_start_gcode").startswith("G28 ;Home")
    [said] = handover.machine_missing(setup, unknown)
    assert said.code == "slicer.cura_printer_unknown"
    assert said.severity == "warning"
    assert said.values["printer"] == unknown.printer.title
    assert [action.id for action in said.suggestions] == ["choose_slicer", "export_only"]
    assert handover.machine_missing(setup, known) == []


def test_without_readable_definitions_nothing_is_claimed(tmp_path: Path) -> None:
    """Ohne Definitionen startet CuraEngine gar nicht; der Befund behauptet nichts."""
    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    setup = handover.SlicerSetup(engine, "cura")

    assert handover.machine_missing(setup, profiles.make_profile("centauri-carbon-2", "pla")) == []
    config = _written(engine, "creality-k1-max", tmp_path)
    assert config.cura_machine is not None and not config.cura_machine.codes


def test_an_installation_without_the_printer_falls_back_like_an_unknown_one(
    tmp_path: Path,
) -> None:
    """Eine ältere Cura ohne die Datei: ``fdmprinter`` und derselbe Befund."""
    engine = _cura(tmp_path)
    (
        engine.parent / "share" / "cura" / "resources" / "definitions" / "creality_k1max.def.json"
    ).unlink()
    setup = handover.SlicerSetup(engine, "cura")

    config = _written(engine, "creality-k1-max", tmp_path)

    assert config.cura_machine is not None and not config.cura_machine.from_printer
    assert [
        f.code
        for f in handover.machine_missing(setup, profiles.make_profile("creality-k1-max", "pla"))
    ] == ["slicer.cura_printer_unknown"]


@pytest.mark.parametrize("name", ["../evil", "creality k1max", "a/b", "x.def.json"])
def test_a_cura_definition_is_a_bare_name(name: str) -> None:
    """Die Kennung wird zu einem Pfad im Definitionsordner — mehr als ein Name ist sie nicht.

    Ein mitgebrachter Drucker kommt aus einer fremden Projektdatei; ``..``
    oder ein Trenner zeigte aus dem Ordner der Installation heraus.
    """
    table = {"title": "Eigener", "build_volume": [200.0, 200.0, 200.0], "cura_definition": name}

    with pytest.raises(ValidationError):
        profiles._printer_from_table("eigener", table, Path("printers.toml"))


def test_a_printer_with_a_foreign_definition_name_hands_over_fdmprinter(tmp_path: Path) -> None:
    """Ein Profil ohne Tabelle (``replace``) geht an derselben Prüfung vorbei nicht durch."""
    engine = _cura(tmp_path)
    printer = replace(profiles.printer("creality-k1-max"), cura_definition="../creality_k1max")

    assert handover._cura_printer_definition(engine, printer) == ""


def _installed_cura() -> Path | None:
    """Die echte Cura-Installation dieses Rechners, wenn es eine gibt."""
    for base in (Path("C:/Program Files"), Path("/usr/share"), Path("/opt")):
        if not base.is_dir():
            continue
        for folder in sorted(base.iterdir()):
            engine = folder / "CuraEngine.exe"
            if engine.is_file() and handover._cura_base(engine):
                return engine
    return None


def test_every_cura_definition_in_the_printer_table_is_installed() -> None:
    """Ein Tippfehler in ``printers.toml`` fiele sonst nur als Befund beim Kunden auf.

    Gegen die Installation dieses Rechners (Cura 5.13 am 27.09.2026); ohne
    Cura prüft der Test nichts und sagt das.
    """
    engine = _installed_cura()
    if engine is None:
        pytest.skip("keine Cura-Installation auf diesem Rechner")
    named = {
        identifier: printer.cura_definition
        for identifier, printer in profiles.printer_profiles().items()
        if printer.cura_definition
    }
    assert len(named) >= 5, f"zu wenige Einträge gefunden: {named}"
    missing = {
        identifier: name
        for identifier, name in named.items()
        if not handover._cura_printer_definition(engine, profiles.printer(identifier))
    }
    assert not missing, f"in Cura nicht gefunden: {missing}"
    start = handover._cura_machine(
        handover.SlicerSetup(engine, "cura"),
        profiles.make_profile("creality-k1-max", "pla"),
        {"material_print_temperature_layer_0": "215", "material_bed_temperature_layer_0": "60"},
    ).codes["machine_start_gcode"]
    assert "START_PRINT EXTRUDER_TEMP=215 BED_TEMP=60" in start


# --- Die Befunde B2 bis B12 des Prüfberichts ------------------------------------


def _cura_values(printer: str, material: str = "pla", **paths: object) -> dict[str, str]:
    """Was CuraEngine für diesen Drucker bekommt: Einstellungen, Maschine, Abgeleitetes.

    ``paths`` setzt Einstellungen vorher, ``speed__travel=80`` für ``speed.travel``.
    """
    profile = profiles.make_profile(printer, material)
    settings = print_settings.resolve(profile)
    for path, value in paths.items():
        settings = print_settings.with_path(settings, path.replace("__", "."), value)
    return handover.values_for(settings, profile, "cura")


@pytest.mark.parametrize(
    ("printer", "expected"),
    [
        # Aus demselben Standardprozess wie die Tempi: Creality im Bestand von
        # Orca 500 am Ender-3 V3 (Prüfbericht §2.2), 1000 am K1 Max, Anycubic 2000.
        ("creality-ender3-v3", 500.0),
        ("creality-k1-max", 1000.0),
        ("anycubic-kobra-2", 2000.0),
        # Ohne Angabe des Herstellers die Vorgabe der Werksprofile.
        ("generic-220", 500.0),
        ("sovol-sv06", 500.0),
    ],
)
def test_the_first_layer_has_its_own_acceleration(printer: str, expected: float) -> None:
    """Die erste Schicht fuhr mit der Druckbeschleunigung: ``M204 S12000`` am Ender-3 V3.

    ``acceleration_layer_0`` spiegelte ``acceleration_print``; jetzt trägt sie
    den Wert des Herstellers, und ihre Blätter (erste Schicht, Skirt und Brim,
    Raft-Basis) folgen ihr. Die Leerfahrt der ersten Schicht rechnet Cura aus
    ihr, und weil die Fahrt mit der Druckbeschleunigung fährt, ist es derselbe
    Wert.
    """
    values = _cura_values(printer)

    for key in (
        "acceleration_layer_0",
        "acceleration_print_layer_0",
        "acceleration_skirt_brim",
        "raft_base_acceleration",
        "acceleration_travel_layer_0",
    ):
        assert float(values[key]) == pytest.approx(expected), key
    assert float(values["acceleration_print"]) > expected, "die übrigen Schichten bleiben schnell"
    assert values["acceleration_travel"] == values["acceleration_print"], (
        "die Fahrt beschleunigt wie der Druck, nicht mit festen 5000"
    )


def test_the_first_layer_is_never_faster_than_the_rest() -> None:
    """Eine Maschine, die sanfter beschleunigt als 500, bekommt keine schnellere erste Schicht."""
    values = _cura_values("generic-220", speed__acceleration=300.0)

    assert float(values["acceleration_layer_0"]) == pytest.approx(300.0)
    assert float(values["acceleration_print_layer_0"]) == pytest.approx(300.0)
