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
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from app.core import discover
from app.core.errors import ExternalToolError, OperationCancelled, ValidationError
from app.core.export import appimage as image_copies
from app.core.export import cura_linux, handover, slicer_profiles, squashfs
from app.core.knowledge import print_settings, profiles
from tests.cura_fakes import (
    APPRUN_ENV,
    FAILING_MOUNT,
    FLATPAK_LIBRARIES,
    K1_MAX_START,
    MOUNT_SCRIPT,
    appimage_cura,
    cura_installation,
    ended_mounts,
    failing_mount,
    flatpak_cura,
)
from tests.squashfs_fakes import IMAGE_AT, Link, appimage_file, tree_of


def _written(engine: Path, printer: str, tmp_path: Path) -> handover.SlicerConfig:
    profile = profiles.make_profile(printer, "pla")
    setup = handover.SlicerSetup(engine, "cura")
    return handover.write_config(print_settings.resolve(profile), profile, setup, tmp_path)


def _argument(command: list[str], key: str) -> str:
    """Der Wert hinter ``-s key=…`` — genau einer, sonst stimmt die Übergabe nicht."""
    found = [entry for entry in command if entry.startswith(f"{key}=")]
    assert len(found) == 1, f"{key}: {len(found)}-mal in der Kommandozeile"
    return found[0].split("=", 1)[1]


@pytest.mark.parametrize("name", ("Bayrak Direği uzun", "埃菲尔铁塔18cm", "Würfel Größe"))
@pytest.mark.parametrize("explicit_output", (False, True))
def test_cura_reads_ascii_copies_and_keeps_the_original_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, explicit_output: bool
) -> None:
    """Alle CLI-Dateien sind lesbar; Teile, Blocker und eigene Namen bleiben erhalten."""
    engine = cura_installation(tmp_path / "安装目录")
    model = tmp_path / f"{name}.stl"
    model_bytes = (Path(__file__).parent / "data" / "meshes" / "cube_clean.stl").read_bytes()
    model.write_bytes(model_bytes)
    blocker = tmp_path / f"{name}-blocker.stl"
    blocker.write_bytes(model_bytes)
    handover.write_cura_meshes(
        model,
        (
            handover.CuraMesh(model, {"wall_line_count": "4"}),
            handover.CuraMesh(blocker, {"anti_overhang_mesh": "true"}),
        ),
    )
    sources = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    output_dir = tmp_path / "输出 Größe" if explicit_output else None
    captured: list[Path] = []

    def run(command: list[str], workspace: Path, *_args: object, **_kwargs: object):
        captured.append(workspace)
        assert str(workspace).isascii()
        paths = [
            Path(command[index + 1])
            for index, flag in enumerate(command[:-1])
            if flag in {"-l", "-j", "-o"}
        ]
        assert all(str(path).isascii() for path in paths)
        roots = command[command.index("-d") + 1].split(os.pathsep)
        assert all(str(root).isascii() for root in roots)
        meshes = [Path(command[index + 1]) for index, flag in enumerate(command) if flag == "-l"]
        assert [path.read_bytes() for path in meshes] == [model_bytes, model_bytes]
        assert command[command.index(str(meshes[0])) + 2] == "wall_line_count=4"
        assert command[command.index(str(meshes[1])) + 2] == "anti_overhang_mesh=true"
        seen: set[Path] = set()

        def check_definition(path: Path) -> None:
            if path in seen:
                return
            seen.add(path)
            data = json.loads(path.read_text(encoding="utf-8"))
            references = list(data.get("metadata", {}).get("machine_extruder_trains", {}).values())
            if "inherits" in data:
                references.append(data["inherits"])
            for reference in references:
                assert reference.isascii()
                matches = [Path(root) / f"{reference}.def.json" for root in roots]
                check_definition(next(entry for entry in matches if entry.is_file()))

        for index, flag in enumerate(command):
            if flag == "-j":
                check_definition(Path(command[index + 1]))
        assert len(seen) == 4
        assert any("gantry_height" in path.read_text(encoding="utf-8") for path in seen)
        Path(command[command.index("-o") + 1]).write_text(_printed("G28"), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(handover, "_run_slicer", run)
    profile = profiles.make_profile("creality-k1-max", "pla")
    outcome = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(engine, "cura"),
        output_dir=output_dir,
    )
    expected = output_dir / handover.OUTPUT_NAME if output_dir else model.with_suffix(".gcode")
    assert outcome.gcode_path == expected
    assert expected.is_file()
    assert all(path.read_bytes() == content for path, content in sources.items())
    assert captured and not captured[0].exists()


def test_cura_model_read_error_has_a_matching_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine nicht geladene Modelldatei verweist auf erneute Übergabe und Slicerwechsel."""
    from app.core.errors import CHECK_SLICER_PROFILE, RETRY, SHOW_SLICER_OUTPUT

    engine = cura_installation(tmp_path)
    model = tmp_path / "model.stl"
    model_bytes = (Path(__file__).parent / "data" / "meshes" / "cube_clean.stl").read_bytes()
    model.write_bytes(model_bytes)
    monkeypatch.setattr(
        handover,
        "_run_slicer",
        lambda command, *_args, **_kwargs: subprocess.CompletedProcess(
            command, 1, b"", b"Failed to load model model-0.stl (error number 2)"
        ),
    )
    profile = profiles.make_profile("creality-k1-max", "pla")
    with pytest.raises(ExternalToolError) as caught:
        handover.slice_model(
            model, print_settings.resolve(profile), profile, handover.SlicerSetup(engine, "cura")
        )
    assert RETRY in caught.value.suggestions
    assert SHOW_SLICER_OUTPUT in caught.value.suggestions
    assert CHECK_SLICER_PROFILE not in caught.value.suggestions


@pytest.mark.parametrize("flavour", ("prusa", "orca"))
def test_other_families_also_read_private_ascii_model_copies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flavour: str
) -> None:
    """Der allgemeine Dateivertrag umfasst beide Slicerfamilien neben Cura."""
    model = tmp_path / "Bayrak Direği 打印.stl"
    model_bytes = (Path(__file__).parent / "data" / "meshes" / "cube_clean.stl").read_bytes()
    model.write_bytes(model_bytes)
    executable = tmp_path / "slicer.exe"
    executable.touch()
    output_dir = tmp_path / "打印"

    def run(command: list[str], workspace: Path, *_args: object, **_kwargs: object):
        assert str(workspace).isascii()
        inputs = [Path(argument) for argument in command if argument.endswith(".stl")]
        assert len(inputs) == 1 and inputs[0] != model
        assert str(inputs[0]).isascii()
        assert inputs[0].read_bytes() == model.read_bytes()
        if flavour == "prusa":
            target = Path(command[command.index("--output") + 1])
        else:
            target = Path(command[command.index("--outputdir") + 1]) / "plate_1.gcode"
        assert str(target).isascii()
        target.write_text(_printed("G28"), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(handover, "_run_slicer", run)
    profile = profiles.make_profile()
    result = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(executable, flavour),
        output_dir=output_dir,
    )
    assert result.gcode_path.parent == output_dir
    assert result.gcode_path.is_file()
    assert model.read_bytes() == model_bytes


def test_cura_copies_unicode_definition_ids_in_native_search_order(tmp_path: Path) -> None:
    """Vorlagen samt Formeln bleiben erhalten; die erste gleichnamige Vorlage gewinnt."""
    first = tmp_path / "第一"
    second = tmp_path / "第二"
    workspace = tmp_path / "workspace"
    for directory in (first, second, workspace):
        directory.mkdir()
    for directory, marker in ((first, "first"), (second, "second")):
        (directory / "基础.def.json").write_text(
            json.dumps({"name": marker, "settings": {"formula": {"value": "x + 1"}}}),
            encoding="utf-8",
        )
    child = second / "Düse.def.json"
    child.write_text(json.dumps({"inherits": "基础", "name": "Düse"}), encoding="utf-8")
    engine = first / "printer.def.json"
    engine.write_text(
        json.dumps({"inherits": "基础", "metadata": {"machine_extruder_trains": {"0": "Düse"}}}),
        encoding="utf-8",
    )
    command = [
        "CuraEngine",
        "slice",
        "-d",
        os.pathsep.join((str(first), str(second))),
        "-j",
        str(engine),
        "-e0",
        "-j",
        str(child),
        "-o",
        str(second / "打印.gcode"),
    ]
    original = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    staged = handover._prepare_cura_cli(command, workspace, None)
    copied = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (workspace / "definitions").glob("*.json")
    ]
    assert len(copied) == 3
    assert {data.get("name", "") for data in copied} == {"", "first", "Düse"}
    assert (
        next(data for data in copied if data.get("name") == "first")["settings"]["formula"]["value"]
        == "x + 1"
    )
    assert all(
        str(value).isascii()
        for index, value in enumerate(staged)
        if index and staged[index - 1] in {"-j", "-d", "-o"}
    )
    assert all(path.read_bytes() == content for path, content in original.items())


@pytest.mark.parametrize(
    "bad_data",
    (
        {"inherits": "missing"},
        {"inherits": "printer"},
        {"metadata": {"machine_extruder_trains": {"0": "missing"}}},
        {"inherits": "../elsewhere"},
        [],
    ),
)
def test_incomplete_cura_definition_copies_stop_before_starting(
    tmp_path: Path, bad_data: object
) -> None:
    """Eine abgerissene Vorlagenkette erreicht den Fremdprozess nicht."""
    source = tmp_path / "printer.def.json"
    source.write_text(json.dumps(bad_data), encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ExternalToolError) as caught:
        handover._prepare_cura_cli(["CuraEngine", "slice", "-j", str(source)], workspace, None)
    assert caught.value.suggestions
    assert source.read_text(encoding="utf-8") == json.dumps(bad_data)


def test_cura_copies_the_fallback_extruder_definition(tmp_path: Path) -> None:
    """Auch der zweite -j-Pfad der allgemeinen Maschine bleibt im Arbeitsordner."""
    engine = cura_installation(tmp_path / "安装")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = _written(engine, "anycubic-kobra-2", workspace)
    model = tmp_path / "打印.stl"
    model_bytes = (Path(__file__).parent / "data" / "meshes" / "cube_clean.stl").read_bytes()
    model.write_bytes(model_bytes)
    command = handover._command(handover.SlicerSetup(engine, "cura"), [model], config, tmp_path)
    assert command.count("-j") == 2
    staged = handover._prepare_cura_cli(command, workspace, None)
    assert staged.count("-j") == 2
    assert all(
        Path(staged[index + 1]).parent == workspace / "definitions"
        for index, flag in enumerate(staged)
        if flag == "-j"
    )


def test_cura_output_copy_cancellation_keeps_the_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Beim Abbruch bleiben die frühere Druckdatei und das Modell unverändert."""
    from app.core.errors import OperationCancelled

    class CancelDuringCopy:
        calls = 0

        @property
        def is_cancelled(self) -> bool:
            return self.calls >= 3

        def raise_if_cancelled(self) -> None:
            self.calls += 1
            if self.is_cancelled:
                raise OperationCancelled

    source = tmp_path / "print.gcode"
    source.write_bytes(b"new")
    target = tmp_path / "打印.gcode"
    target.write_bytes(b"old")
    token = CancelDuringCopy()
    monkeypatch.setattr(handover, "COPY_BLOCK_BYTES", 1)
    with pytest.raises(OperationCancelled):
        handover._copy_print_file(source, target, cancelled=token)
    assert target.read_bytes() == b"old"
    assert source.read_bytes() == b"new"
    assert set(tmp_path.iterdir()) == {source, target}


def test_cura_gets_the_start_code_of_its_printer(tmp_path: Path) -> None:
    """Der K1 Max bekommt ``START_PRINT`` mit seinen Temperaturen, nicht ``G28``.

    Gemessen am 27.09.2026 mit CuraEngine 5.13: Die Konsole löst die Erbkette
    der Druckerdefinition selbst auf, braucht für den Extruderzug aber den
    Ordner ``extruders`` hinter ``-d``. Ein ``-e0 -j fdmextruder.def.json``
    darüber setzte die Vorgaben des Zugs zurück und fällt deshalb weg.
    """
    engine = cura_installation(tmp_path)
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


def _printed(start: str, name: str = "Creality K1 Max") -> str:
    """Der Kopf einer Druckdatei, wie CuraEngine 5.13 ihn schreibt: Name, eigene
    Temperaturbefehle, der Startcode wörtlich, dann die erste Schicht."""
    return (
        f";FLAVOR:Marlin\n;TARGET_MACHINE.NAME:{name}\n\n;Generated with Cura_SteamEngine 5.13.0\n"
        f"M140 S60\nM105\n{start}\nM82 ;absolute extrusion mode\nG92 E0\n"
        ";LAYER_COUNT:2\n;LAYER:0\nG1 X10 Y10 E1\nM420 S1\n"
    )


def test_the_countercheck_sees_whether_cura_took_the_machine(tmp_path: Path) -> None:
    """Entscheidung K: CuraEngine schreibt keine Einstellungen in die Datei,
    also prüft die Gegenprobe den Namen im Kopf und den Startcode vor der
    ersten Schicht, Befehl für Befehl und in seiner Reihenfolge."""
    from app.core.slice import gcode

    engine = cura_installation(tmp_path, start="G28 ;Home\nM420 S1 ;Bettnetz\nSTART_PRINT\n")
    machine = _written(engine, "creality-k1-max", tmp_path).cura_machine
    assert machine is not None and machine.name == "Creality K1 Max"

    def differences(text: str) -> list[str]:
        return handover.cura_machine_differences(gcode.analyze(text), machine)

    assert differences(_printed("G28 ;Home\nM420 S1 ;Bettnetz\nSTART_PRINT")) == []
    assert differences(_printed("G28\nM420 S1\nSTART_PRINT", name="Unknown")) == [
        "machine_name: Creality K1 Max → Unknown"
    ]
    # Fehlt ein Befehl vor der ersten Schicht, zählt ein späterer nicht.
    assert differences(_printed("G28 ;Home\nSTART_PRINT")) == ["machine_start_gcode: M420 S1 → —"]
    # Und in seiner Reihenfolge: Ein Bettnetz vor dem Referenzfahren lädt ein
    # Netz, das danach nicht mehr stimmt.
    assert differences(_printed("M420 S1\nG28\nSTART_PRINT")) == [
        "machine_start_gcode: M420 S1 → —"
    ]
    assert handover.cura_machine_differences(gcode.analyze(_printed("")), None) == []


def test_the_countercheck_reports_the_machine_with_the_values() -> None:
    """Ein Befund für alles, was der Slicer anders nahm — Werte wie Maschine."""
    found = handover.verify_settings(
        {"layer_height": "0.2"},
        {"layer_height": "0.2"},
        ["machine_start_gcode: M420 S1 → —"],
    )

    assert [entry.code for entry in found] == ["slicer.setting_ignored"]
    assert found[0].values["count"] == 1
    assert "M420 S1" in str(found[0].values["settings"])


def test_a_calculation_in_a_placeholder_goes_through_solidons_own_evaluator(
    tmp_path: Path,
) -> None:
    """``{machine_depth - 5}`` im Endcode des Neptune 4 — Rechnung ohne ``eval``.

    Die Tiefe ist die, die Solidon schreibt, nicht die der Definition: Beide
    beschreiben dieselbe Maschine, und gedruckt wird mit Solidons Bauraum.
    Dazu ``{name, 0}`` (Wert des ersten Zugs) und ein Name, den das Fenster
    unter einem zweiten führt (``print_temperature``).
    """
    engine = cura_installation(
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
    engine = cura_installation(tmp_path, start=start)

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
    engine = cura_installation(tmp_path, start=start)

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
    engine = cura_installation(tmp_path)
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


def test_cura_instance_identity_is_kept_and_cli_unknown_finding_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    setup = handover.SlicerSetup(engine, "cura")
    known = profiles.make_profile("creality-k1-max", "pla")
    # Ein in Cura vergrößertes Bett: Dieselbe Definition mit demselben Bett
    # wäre derselbe Drucker und bliebe still (RM-417).
    active = slicer_profiles.CuraActiveMachine(
        name="K1 Max in der Werkstatt",
        definition=Path("creality_k1max.def.json"),
        bed=(350.0, 300.0),
    )
    monkeypatch.setattr(slicer_profiles, "cura_active_machine", lambda _executable: active)
    monkeypatch.setattr(slicer_profiles, "chosen_printer", lambda *_args, **_kwargs: "")

    mismatch = handover.cura_active_printer_mismatch(setup, known)
    assert mismatch is not None
    assert mismatch.code == "slicer.machine_mismatch"
    assert "K1 Max in der Werkstatt" in str(mismatch.message)

    [unknown] = handover.machine_missing(setup, profiles.make_profile("centauri-carbon-2", "pla"))
    assert unknown.code == "slicer.cura_printer_unknown"


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
    engine = cura_installation(tmp_path)
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
    engine = cura_installation(tmp_path)
    printer = replace(profiles.printer("creality-k1-max"), cura_definition="../creality_k1max")

    assert handover._cura_printer_definition(engine, printer) == ""


@pytest.mark.slicer("cura")
def test_every_cura_definition_in_the_printer_table_is_installed(
    installed_slicer: Path,
) -> None:
    """Ein Tippfehler in ``printers.toml`` fiele sonst nur als Befund beim Kunden auf.

    Gegen die Installation dieses Rechners (Cura 5.13 am 27.09.2026); ohne
    Cura prüft der Test nichts und sagt das (``installed_slicer``).
    """
    engine = installed_slicer
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
        settings = print_settings.with_choice(settings, path.replace("__", "."), value)
    return handover.values_for(settings, profile, "cura")


@pytest.mark.parametrize(
    ("printer", "expected"),
    [
        # Aus demselben Standardprozess wie die Tempi: Creality im Bestand von
        # Orca 500 am Ender-3 V3 (Prüfbericht §2.2), 1000 am K1 Max, Anycubic 2000.
        ("creality-ender3-v3", 500.0),
        ("creality-k1-max", 1000.0),
        ("anycubic-kobra-2", 2000.0),
        # Der SV06 nennt die Druckbeschleunigung, für die erste Schicht gilt die Vorgabe.
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


def test_supports_follow_the_factory_profiles() -> None:
    """Stützen wie im Werksprofil: verbunden, lockere Schnittstelle, gebremst.

    Die Schnittstelle stand auf ``concentric`` mit voller Dichte und fuhr am
    Ender-3 V3 mit 143 mm/s, die Stütze mit 214 — Creality und Elegoo legen
    sie in Cura in Linien zu einem Drittel, Orca fährt Stütze 150 und
    Schnittstelle 80 mm/s. CuraEngine liest nur die Blätter.
    """
    values = _cura_values("creality-ender3-v3", support__style="grid")
    width = float(values["line_width"])

    assert "support_pattern" not in values, "Curas zigzag bleibt"
    assert values["support_roof_pattern"] == values["support_bottom_pattern"] == "lines"
    assert float(values["support_roof_line_distance"]) == pytest.approx(3.0 * width)
    assert float(values["support_bottom_line_distance"]) == pytest.approx(3.0 * width)
    assert float(values["speed_support"]) == pytest.approx(150.0)
    assert values["speed_support_infill"] == values["speed_support"]
    interface = min(float(values["speed_wall_0"]), 80.0)
    for key in ("speed_support_interface", "speed_support_roof", "speed_support_bottom"):
        assert float(values[key]) == pytest.approx(interface), key
    assert float(values["minimum_support_area"]) == pytest.approx(2.0)


def test_a_slow_printer_keeps_its_slower_support() -> None:
    """Die Deckel gelten nach oben: Der SV06 fährt Stütze und Schnittstelle langsamer."""
    values = _cura_values("sovol-sv06", support__style="grid")

    assert float(values["speed_support"]) == pytest.approx(float(values["speed_print"]))
    assert float(values["speed_support_interface"]) == pytest.approx(float(values["speed_wall_0"]))


@pytest.mark.parametrize(
    ("printer", "factors"),
    [
        # Elegoo bremst auf 50, 30 und 10 mm/s bei 160 mm/s Außenwand.
        ("centauri-carbon-2", "[31,19,6,6]"),
        ("creality-k1-max", "[25,15,5,5]"),
        # Ohne Stufen des Herstellers die Vorgabe des Prüfberichts.
        ("generic-220", "[50,25]"),
    ],
)
def test_overhanging_walls_slow_down_like_at_the_manufacturer(printer: str, factors: str) -> None:
    """Überhänge fuhren mit voller Wandgeschwindigkeit, seit Paket 1 bis 60 Grad ohne Stütze.

    Orca bremst ab einem Viertel Bahnbreite Überhang in Stufen; Cura teilt den
    Bereich ab ``wall_overhang_angle`` in gleiche Winkelschritte. Der Winkel
    ist deshalb der eines Viertels der Bahnbreite bei dieser Schichthöhe, und
    die letzte Stufe gilt zweimal.
    """
    import math

    values = _cura_values(printer)
    width, height = float(values["line_width"]), float(values["layer_height"])

    assert values["wall_overhang_speed_factors"] == factors
    assert float(values["wall_overhang_angle"]) == round(
        math.degrees(math.atan(0.25 * width / height))
    )


def test_the_overhang_steps_are_read_from_the_printer_table(tmp_path: Path) -> None:
    """Eine Null wäre eine Wand, die nicht fährt — die Tabelle sagt es, statt zu raten."""
    table = {"title": "Eigener", "build_volume": [200.0, 200.0, 200.0]}

    read = profiles._printer_from_table(
        "eigener", {**table, "overhang_speed_factors": [40, 20, 10]}, Path("printers.toml")
    )
    assert read.overhang_speed_factors == (40.0, 20.0, 10.0)
    assert profiles._printer_from_table("eigener", table, Path("x")).overhang_speed_factors == ()
    with pytest.raises(ValidationError):
        profiles._printer_from_table(
            "eigener", {**table, "overhang_speed_factors": [40, 0]}, Path("printers.toml")
        )


def test_infill_comes_after_the_walls() -> None:
    """``fdmprinter`` druckt die Füllung zuerst, und ihr Muster zeichnet sich durch.

    Gemessen im Prüfbericht (§1.4): ``FILL``, ``WALL-INNER``, ``WALL-OUTER``.
    Creality, Anycubic und Sovol stellen in Cura ``false``.
    """
    assert _cura_values("creality-k1-max")["infill_before_walls"] == "false"


@pytest.mark.parametrize(("material", "distance"), [("pla", 30.0), ("petg", 10.0)])
def test_travel_moves_retract_after_a_while_and_avoid_supports(
    material: str, distance: float
) -> None:
    """Kämmen ohne Rückzug war unbegrenzt, der Z-Sprung kam bei jedem Rückzug."""
    values = _cura_values("creality-k1-max", material)

    assert float(values["retraction_combing_max_distance"]) == pytest.approx(distance)
    assert values["retraction_hop_only_when_collides"] == "true"
    assert values["travel_avoid_supports"] == "true"


def test_the_seam_prefers_hidden_corners() -> None:
    """``z_seam_corner_weighted`` wie Creality, Sovol und Elegoo in Cura."""
    assert _cura_values("creality-k1-max")["z_seam_corner"] == "z_seam_corner_weighted"


def test_cura_is_not_offered_a_flow_limit_it_does_not_read() -> None:
    """``material_max_flowrate`` kommt in ``CuraEngine.exe`` nicht vor (Prüfbericht §3.6).

    Eine Zeile, die nichts bewirkt, ist im Druckdialog eine Attrappe.
    """
    from app.core.export import slicer_keys

    assert "material_max_flowrate" not in _cura_values("creality-k1-max")
    assert not slicer_keys.takes("cura", "filament.max_flow")


@pytest.mark.parametrize(
    ("printer", "width"),
    [
        # Aus demselben Standardprozess wie die Tempi: 0,5 mm an der 0,4er Düse
        # bei Elegoo, Bambu, Creality und Prusa, 0,8 am Kobra 2, 0,42 am SV06.
        ("centauri-carbon-2", 0.5),
        ("anycubic-kobra-2", 0.8),
        ("sovol-sv06", 0.42),
        # Ohne Angabe bleibt Solidons 1,07-fache Bahnbreite.
        ("generic-220", round(0.42 * 1.07, 3)),
    ],
)
def test_the_first_line_is_as_wide_as_at_the_manufacturer(printer: str, width: float) -> None:
    """Die erste Bahn war 1,07 Bahnbreiten breit, schmaler als in jedem Werksprofil.

    Bei Cura ist Solidons Satz die Grundlage: Die 106,9 % gingen unverändert
    hinaus, wo Creality, Elegoo und Bambu 119 %, Sovol in Cura 150 % fahren
    (Prüfbericht Cura, B7).
    """
    profile = profiles.make_profile(printer, "pla")
    settings = print_settings.resolve(profile)

    assert settings.layers.first_layer_line_width == pytest.approx(width)
    factor = float(
        handover.values_for(settings, profile, "cura")["initial_layer_line_width_factor"]
    )
    assert factor == pytest.approx(width / settings.layers.line_width * 100.0, abs=1e-3)


def test_a_changed_nozzle_takes_the_first_line_along() -> None:
    """Der Druckdialog kopiert das Profil mit anderer Düse — die erste Bahn wächst mit."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    wider = replace(profile.printer, nozzle_diameter=0.6, extrusion_width=0.63)

    settings = print_settings.resolve(replace(profile, printer=wider))

    assert settings.layers.first_layer_line_width == pytest.approx(0.75)


def test_the_first_layer_does_not_travel_at_walking_pace() -> None:
    """Kobra 2: 16,9 mm/s Leerfahrt in Schicht 1 (20 × 120 / 142, Curas Formel).

    Dieselbe Formel, aber nie unter dem Tempo, das die Werksprofile in der
    ersten Schicht fahren — 100 mm/s, oder die Leerfahrt selbst, wenn sie
    langsamer ist.
    """
    assert float(_cura_values("anycubic-kobra-2")["speed_travel_layer_0"]) == pytest.approx(100.0)
    slow = _cura_values("generic-220", speed__travel=80.0)
    assert float(slow["speed_travel_layer_0"]) == pytest.approx(80.0)
    fast = _cura_values("creality-k1-max")
    formula = (
        float(fast["speed_layer_0"]) * float(fast["speed_travel"]) / float(fast["speed_print"])
    )
    # Sechs geltende Ziffern, wie jede geschriebene Zahl (``:g``).
    assert float(fast["speed_travel_layer_0"]) == pytest.approx(max(formula, 100.0), rel=1e-5)


# --- B10: je Teil ein Netz, die Stützsperre als eigenes --------------------------


def test_every_mesh_goes_in_with_its_own_values(tmp_path: Path) -> None:
    """Ein ``-s`` nach ``-l`` gilt nur diesem Netz (``CommandLine.cpp``).

    Die Sperre reist mit ``anti_overhang_mesh=true`` direkt hinter ihrem
    ``-l``; die Teile vor ihr bekommen keinen Wert, und die globalen Werte
    stehen vor dem ersten Netz.
    """
    engine = cura_installation(tmp_path)
    config = _written(engine, "creality-k1-max", tmp_path)
    model = tmp_path / "teil.stl"
    part = tmp_path / "teil-part-1.stl"
    blocker = tmp_path / "teil-blocker-1.stl"
    for path in (model, part, blocker):
        path.write_bytes(b"solid x\nendsolid x\n")
    handover.write_cura_meshes(
        model,
        [handover.CuraMesh(part), handover.CuraMesh(blocker, {"anti_overhang_mesh": "true"})],
    )

    command = handover._command(handover.SlicerSetup(engine, "cura"), [model], config, tmp_path)

    loads = [command[index + 1] for index, entry in enumerate(command) if entry == "-l"]
    assert loads == [str(part), str(blocker)], "das Sammel-STL bleibt für das Fenster"
    after = command[command.index(str(blocker)) + 1 : command.index("-o")]
    assert after == ["-s", "anti_overhang_mesh=true"]
    assert command.index("-e0") < command.index("-l"), "Maschine und Zug vor dem ersten Netz"


def test_a_model_without_a_mesh_list_goes_in_as_it_is(tmp_path: Path) -> None:
    """Ein Modell, das nicht aus ``write_assembly`` kommt, geht unverändert hinein."""
    engine = cura_installation(tmp_path)
    config = _written(engine, "creality-k1-max", tmp_path)
    model = tmp_path / "fremd.stl"
    model.write_bytes(b"solid x\nendsolid x\n")

    command = handover._command(handover.SlicerSetup(engine, "cura"), [model], config, tmp_path)

    assert [command[index + 1] for index, entry in enumerate(command) if entry == "-l"] == [
        str(model)
    ]


@pytest.mark.parametrize(
    "entry",
    [
        {"file": "../anderswo.stl"},
        {"file": "fehlt.stl"},
        {"file": "teil-part-1.stl", "settings": {"support_enable": "a\nb"}},
        {"file": "teil-part-1.stl", "settings": {"Mesh Type": "x"}},
    ],
)
def test_a_mesh_list_that_does_not_hold_stops_the_handover(tmp_path: Path, entry: dict) -> None:
    """Die Liste liegt in einem Ordner; was nicht passt, wird kein Argument.

    Lieber anhalten als still das Modell ohne Sperre rechnen (Regel 21).
    """
    model = tmp_path / "teil.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    (tmp_path / "teil-part-1.stl").write_bytes(b"solid x\nendsolid x\n")
    model.with_suffix(handover.CURA_MESHES_SUFFIX).write_text(
        json.dumps({"meshes": [entry]}), encoding="utf-8"
    )

    with pytest.raises(ExternalToolError) as caught:
        handover.cura_meshes(model)

    assert [action.id for action in caught.value.suggestions] == ["retry", "export_only"]


# --- B8: Ender-3 V3 SE und KE sind eigene Drucker -------------------------------


@pytest.mark.parametrize(
    ("printer", "expected"),
    [
        # Orca, „0.20mm Standard @Creality Ender3V3SE 0.4": ein Bettschubser mit
        # 2500 mm/s² und 180 mm/s Füllung, erste Schicht 500 mm/s².
        (
            "creality-ender3-v3-se",
            {
                "build_volume": (220.0, 220.0, 250.0),
                "acceleration": 2500.0,
                "outer_wall_acceleration": 1000.0,
                "first_layer_acceleration": 500.0,
                "speed_outer_wall": 60.0,
                "speed_infill": 180.0,
                "travel_speed": 150.0,
                "overhang_limit": 60.0,
                "first_layer_line_factor": 1.15,
                "overhang_speed_factors": (33.0, 25.0, 17.0),
                "cura_definition": "creality_ender3v3se",
            },
        ),
        # Orca, „0.20mm Standard @Creality Ender3V3KE": 5000 mm/s², Außenwand 200.
        # Die Bauhöhe 240 wie in Creality Print und Cura; Orca nennt 245.
        (
            "creality-ender3-v3-ke",
            {
                "build_volume": (220.0, 220.0, 240.0),
                "acceleration": 5000.0,
                "outer_wall_acceleration": 4000.0,
                "first_layer_acceleration": 1000.0,
                "speed_outer_wall": 200.0,
                "speed_infill": 300.0,
                "travel_speed": 400.0,
                "overhang_limit": 60.0,
                "first_layer_line_factor": 1.25,
                "overhang_speed_factors": (25.0, 18.0, 5.0),
                "cura_definition": "creality_ender3v3ke",
            },
        ),
    ],
)
def test_the_ender3_v3_se_and_ke_are_printers_of_their_own(
    printer: str, expected: dict[str, object]
) -> None:
    """Wer einen Ender-3 V3 SE besaß, wählte „Ender-3 V3" und bekam einen CoreXZ-Drucker.

    Der V3 beschleunigt mit 12 000 mm/s² und füllt mit 500 mm/s, der SE schafft
    2500 und 180 (Prüfbericht Cura, B8). Beide tragen jetzt den
    Standardprozess ihres Herstellerprofils und ihre Definition in Cura.
    """
    entry = profiles.printer(printer)

    for name, value in expected.items():
        assert getattr(entry, name) == value, name
    assert entry.vendor == "Creality"


@pytest.mark.parametrize(
    ("printer", "lines", "bed_prepend"),
    [
        # Der SE setzt Bett und Düse selbst und lädt sein Bettnetz.
        ("creality-ender3-v3-se", ("M420 S1", "M190 S60", "M109 S215"), "false"),
        # Der KE wartet im Startcode nur auf die Düse; das Bett setzt Cura davor.
        ("creality-ender3-v3-ke", ("M109 S215", "Draw the first line"), "true"),
    ],
)
@pytest.mark.slicer("cura")
def test_the_se_and_ke_start_with_the_code_of_their_definition(
    printer: str, lines: tuple[str, ...], bed_prepend: str, installed_slicer: Path
) -> None:
    """Gegen die echte Installation: Startcode gefüllt, Endcode ohne offene Klammer."""
    engine = installed_slicer
    machine = handover._cura_machine(
        handover.SlicerSetup(engine, "cura"),
        profiles.make_profile(printer, "pla"),
        {
            "material_print_temperature_layer_0": "215",
            "material_bed_temperature_layer_0": "60",
            "machine_depth": "220",
        },
    )

    assert machine.from_printer
    for line in lines:
        assert line in machine.codes["machine_start_gcode"], line
    assert "{" not in "".join(machine.codes.values())
    assert machine.switches == {
        "material_bed_temp_prepend": bed_prepend,
        "material_print_temp_prepend": "false",
    }


def test_cura_does_not_receive_stage_acceleration_without_a_machine_value() -> None:
    """Ein unbekannter Drucker bekommt keine 8000 mm/s² aus der Qualitätsstufe."""
    profile = profiles.make_profile("generic-220", "pla")
    values = handover.values_for(print_settings.resolve(profile), profile, "cura")

    assert values.get("acceleration_enabled", "false") == "false"
    assert "acceleration_print" not in values
    assert "acceleration_wall_0" not in values
    assert "acceleration_travel" not in values


@pytest.mark.parametrize("choose", [print_settings.with_choice, print_settings.with_accepted])
def test_cura_keeps_an_explicit_acceleration_without_a_table_value(choose) -> None:
    """Eine bewusste Wahl oder ein übernommener Rat ist keine ungeprüfte Stufenvorgabe."""
    profile = profiles.make_profile("generic-220", "pla")
    settings = choose(print_settings.resolve(profile), "speed.acceleration", 300.0)
    values = handover.values_for(settings, profile, "cura")

    assert values["acceleration_enabled"] == "true"
    assert float(values["acceleration_print"]) == pytest.approx(300.0)
    assert float(values["acceleration_print_layer_0"]) <= 300.0


def _with_motion_limits(engine: Path) -> None:
    """Curas belegte Bauart: allgemeiner Vorgabewert, numerisches Hersteller-``value``."""
    folder = engine.parent / "share" / "cura" / "resources" / "definitions"
    base = folder / "fdmprinter.def.json"
    document = json.loads(base.read_text(encoding="utf-8"))
    document["settings"]["machine_settings"]["children"].update(
        {
            "machine_acceleration": {"default_value": 4000},
            "machine_max_acceleration_x": {"default_value": 9000},
            "machine_max_acceleration_y": {"default_value": 9000},
            "machine_max_feedrate_x": {"default_value": 299792458000},
        }
    )
    base.write_text(json.dumps(document), encoding="utf-8")
    factory = folder / "creality_k1max.def.json"
    document = json.loads(factory.read_text(encoding="utf-8"))
    document["overrides"].update(
        {
            "machine_acceleration": {"value": 1000},
            "machine_max_acceleration_x": {"value": 500},
            "machine_max_acceleration_y": {"value": 600},
            "machine_max_feedrate_x": {"value": 200},
            "acceleration_travel": {"value": 400},
        }
    )
    factory.write_text(json.dumps(document), encoding="utf-8")


def test_cura_factory_motion_limits_reach_both_engine_levels(tmp_path: Path) -> None:
    """Numerisches ``value`` ersetzt den allgemeinen Default auch ohne Nutzerinstanz."""
    engine = cura_installation(tmp_path)
    _with_motion_limits(engine)
    config = _written(engine, "creality-k1-max", tmp_path)
    command = handover._command(
        handover.SlicerSetup(engine, "cura"), [tmp_path / "part.stl"], config, tmp_path
    )
    extruder = command.index("-e0")

    for key, expected in {
        # Cura setzt diesen Wert vor dem Endcode erneut mit M204.
        "machine_acceleration": "500",
        "machine_max_acceleration_x": "500",
        "machine_max_acceleration_y": "600",
        "machine_max_feedrate_x": "200",
    }.items():
        assert config.written.get(key) == expected, key
        assert f"{key}={expected}" in command[:extruder], key
        assert f"{key}={expected}" in command[extruder:], key


def test_cura_process_accelerations_stay_inside_the_factory_limits(tmp_path: Path) -> None:
    """Auch die Blätter, die ``M204`` steuern, bleiben innerhalb der X-/Y-Grenzen."""
    engine = cura_installation(tmp_path)
    _with_motion_limits(engine)
    config = _written(engine, "creality-k1-max", tmp_path)

    for key in (
        "acceleration_print",
        "acceleration_wall_0",
        "acceleration_infill",
        "acceleration_support",
        "acceleration_print_layer_0",
        "acceleration_travel_layer_0",
        "raft_base_acceleration",
    ):
        assert 0 < float(config.written[key]) <= 500.0, key
    assert float(config.written["acceleration_travel"]) == pytest.approx(400.0)


def test_cura_part_acceleration_cannot_bypass_the_machine_limits(tmp_path: Path) -> None:
    """Ein Außenwandwert je Netz überschreibt den Plattenwert erst hinter ``-l``."""
    engine = cura_installation(tmp_path)
    _with_motion_limits(engine)
    config = _written(engine, "creality-k1-max", tmp_path)
    model = tmp_path / "part.stl"
    model.write_bytes(b"solid part\nendsolid part\n")
    handover.write_cura_meshes(model, [handover.CuraMesh(model, {"acceleration_wall_0": "1500"})])

    command = handover._command(handover.SlicerSetup(engine, "cura"), [model], config, tmp_path)
    object_arguments = command[command.index("-l") + 2 :]

    assert "acceleration_wall_0=500" in object_arguments
    assert "acceleration_wall_0=1500" not in object_arguments


@pytest.mark.parametrize("choose", [print_settings.with_choice, print_settings.with_accepted])
@pytest.mark.parametrize(
    ("path", "key"),
    [
        ("speed.acceleration", "acceleration_print"),
        ("speed.outer_wall_acceleration", "acceleration_wall_0"),
    ],
)
def test_cura_reports_a_limited_explicit_acceleration(
    tmp_path: Path, choose, path: str, key: str
) -> None:
    """Die bewusste Wahl bleibt sichtbar, auch wenn die Maschine weniger zulässt."""
    engine = cura_installation(tmp_path)
    _with_motion_limits(engine)
    profile = profiles.make_profile("creality-k1-max", "pla")
    settings = choose(print_settings.resolve(profile), path, 2000.0)

    config = handover.write_config(
        settings, profile, handover.SlicerSetup(engine, "cura"), tmp_path
    )

    assert print_settings.read_path(settings, path) == pytest.approx(2000.0)
    assert float(config.written[key]) == pytest.approx(500.0)
    [finding] = [item for item in config.findings if item.values.get("setting") == path]
    assert finding.code == "slicer.acceleration_limited"
    assert finding.values["requested"] == pytest.approx(2000.0)
    assert finding.values["actual"] == pytest.approx(500.0)
    assert [action.id for action in finding.suggestions] == ["open_print_settings"]


def test_cura_slice_report_retains_plate_and_part_acceleration_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die fertige Druckdatei meldet beide Kürzungen, obwohl Cura keine Sollwerte rückliest."""
    from subprocess import CompletedProcess

    engine = cura_installation(tmp_path)
    _with_motion_limits(engine)
    profile = profiles.make_profile("creality-k1-max", "pla")
    settings = print_settings.with_choice(
        print_settings.resolve(profile), "speed.acceleration", 2000.0
    )
    model = tmp_path / "part.stl"
    model.write_bytes(b"solid part\nendsolid part\n")
    handover.write_cura_meshes(model, [handover.CuraMesh(model, {"acceleration_wall_0": "1500"})])

    def sliced(command: list[str], *_args: object, **_kwargs: object):
        assert "acceleration_print=500" in command
        assert "acceleration_wall_0=500" in command[command.index("-l") + 2 :]
        Path(command[command.index("-o") + 1]).write_text(
            ";Generated with Cura_SteamEngine 5.13.0\nG90\nM82\nG1 Z0.2 F300\n"
            "G1 X110 Y110 E0.1\nG1 X115 Y110 E0.2\n;TIME_ELAPSED:5\n",
            encoding="utf-8",
        )
        return CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(handover, "_run_slicer", sliced)
    outcome = handover.slice_model(
        model, settings, profile, handover.SlicerSetup(engine, "cura"), output_dir=tmp_path
    )

    limited = [item for item in outcome.findings if item.code == "slicer.acceleration_limited"]
    assert {(item.values["setting"], item.values["requested"]) for item in limited} == {
        ("speed.acceleration", 2000.0),
        ("speed.outer_wall_acceleration", 1500.0),
    }
    [part] = [item for item in limited if item.values["setting"] == "speed.outer_wall_acceleration"]
    assert part.values["file"] == "part.stl"
    assert all(item.values["actual"] == pytest.approx(500.0) for item in limited)
    assert all(item.suggestions[0].id == "open_print_settings" for item in limited)


@pytest.mark.parametrize("for_window", [False, True])
def test_cura_export_reports_limits_on_the_part_that_needs_the_accepted_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, for_window: bool
) -> None:
    """Auch der Exportbericht nennt den gekürzten Rat mit seiner Objektkennung."""
    import trimesh

    from app.core.export import slicer_profiles, writer
    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject, SettingAdvice

    engine = cura_installation(tmp_path)
    _with_motion_limits(engine)
    definition = engine.parent / "share/cura/resources/definitions/creality_k1max.def.json"
    active = slicer_profiles.CuraActiveMachine("Werkstatt", definition)
    monkeypatch.setattr(slicer_profiles, "cura_active_machine", lambda _exe: active)
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: "")
    profile = profiles.make_profile("creality-k1-max", "pla")
    profile = replace(profile, printer=replace(profile.printer, outer_wall_acceleration=400.0))
    settings = print_settings.with_accepted(
        print_settings.resolve(profile), "speed.outer_wall_acceleration", 2000.0
    )
    mesh = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    objects = [SceneObject(id=identifier, name=identifier, mesh=mesh) for identifier in ("a", "b")]

    def advice(entry, *_args, **_kwargs):
        return (
            [SettingAdvice("speed.outer_wall_acceleration", 2000.0, 400.0, "Teil braucht den Rat")]
            if entry.id == "a"
            else []
        )

    monkeypatch.setattr(writer, "part_advice", advice)
    target, findings = writer.write_assembly(
        objects,
        tmp_path,
        project_name="Teile",
        profile=profile,
        settings=settings,
        flavour="cura",
        setup=handover.SlicerSetup(engine, "cura"),
        checked=[],
        for_window=for_window,
    )

    limited = [item for item in findings if item.code == "slicer.acceleration_limited"]
    [part] = [item for item in limited if item.object_id == "a"]
    assert not any(item.object_id == "b" for item in limited)
    assert part.values["requested"] == pytest.approx(2000.0)
    assert part.values["actual"] == pytest.approx(500.0)
    assert part.suggestions[0].id == "open_print_settings"
    if for_window:
        import zipfile
        from xml.etree import ElementTree as ET

        with zipfile.ZipFile(target) as archive:
            root = ET.fromstring(archive.read("3D/3dmodel.model"))
        written = [
            node.text for node in root.iter() if node.get("name") == "cura:acceleration_wall_0"
        ]
        assert "500" in written and "2000" not in written


@pytest.mark.parametrize("native", ["1000", "1e3", " 1000.0 "])
def test_cura_numeric_text_is_a_limit_but_an_expression_is_not(tmp_path: Path, native: str) -> None:
    """Strateo3D IDEX420 speichert seine 1000 mm/s² als Text im Feld ``value``."""
    engine = cura_installation(tmp_path)
    _with_motion_limits(engine)
    definition = engine.parent / "share/cura/resources/definitions/creality_k1max.def.json"
    document = json.loads(definition.read_text(encoding="utf-8"))
    for key in ("machine_acceleration", "machine_max_acceleration_x", "machine_max_acceleration_y"):
        document["overrides"][key] = {"value": native}
    document["overrides"]["machine_max_feedrate_x"] = {"value": "100 + 100"}
    definition.write_text(json.dumps(document), encoding="utf-8")

    config = _written(engine, "creality-k1-max", tmp_path)

    for key in ("machine_acceleration", "machine_max_acceleration_x", "machine_max_acceleration_y"):
        assert float(config.written[key]) == pytest.approx(1000.0)
    assert "machine_max_feedrate_x" not in config.written


def test_cura_window_profile_and_parts_keep_limits_and_report_the_original_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die importierbaren Container und Objektwerte halten dieselbe Grenze wie die Konsole."""
    import configparser
    import zipfile

    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_motion_limits(engine)
    definition = engine.parent / "share/cura/resources/definitions/creality_k1max.def.json"
    active = slicer_profiles.CuraActiveMachine("Werkstatt", definition)
    monkeypatch.setattr(slicer_profiles, "cura_active_machine", lambda _exe: active)
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: "")
    monkeypatch.setattr(
        slicer_profiles, "cura_quality_types", lambda *_args, **_kwargs: {"draft": 0.2}
    )
    profile = profiles.make_profile("creality-k1-max", "pla")
    settings = print_settings.with_choice(
        print_settings.resolve(profile), "speed.acceleration", 2000.0
    )
    model = tmp_path / "part.3mf"
    findings = []

    said = handover.cura_profile_beside(
        model, settings, profile, handover.SlicerSetup(engine, "cura"), findings=findings
    )

    assert said is not None
    with zipfile.ZipFile(model.with_suffix(".curaprofile")) as archive:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(archive.read("solidon").decode("utf-8"))
    assert float(parser["values"]["acceleration_print"]) == pytest.approx(500.0)
    assert parser["values"]["acceleration_enabled"] == "True"
    [limited] = [item for item in findings if item.values.get("setting") == "speed.acceleration"]
    assert limited.values["requested"] == pytest.approx(2000.0)
    assert limited.values["actual"] == pytest.approx(500.0)
    part = handover.for_the_cura_window(
        {"acceleration_wall_0": "1500"},
        machine=handover.cura_window_motion(handover.SlicerSetup(engine, "cura"), profile),
    )
    assert part["acceleration_wall_0"] == "500"


def _with_jerk(engine: Path, overrides: dict[str, object] | None = None) -> Path:
    """Der Jerk-Ausschnitt aus Cura 5.13 mit den Beziehungen der Sovol-Basis."""
    base = engine.parent / "share/cura/resources/definitions/fdmprinter.def.json"
    data = json.loads(base.read_text(encoding="utf-8"))
    entries = {
        "machine_extruder_count": {"default_value": 1},
        "jerk_enabled": {
            "default_value": False,
            "value": True,
            "settable_per_extruder": False,
        },
        "jerk_travel_enabled": {"default_value": True, "settable_per_extruder": False},
        "jerk_print": {"default_value": 20, "value": 5},
        "jerk_travel": {"default_value": 30, "value": "jerk_print * 2"},
        "jerk_wall": {"default_value": 20, "value": "jerk_print"},
        "jerk_wall_0": {"default_value": 20, "value": "jerk_wall"},
        "jerk_infill": {"default_value": 20, "value": "jerk_print"},
        "jerk_layer_0": {"default_value": 20, "value": "jerk_print"},
        "jerk_print_layer_0": {"default_value": 20, "value": "jerk_layer_0"},
        "jerk_travel_layer_0": {"default_value": 20, "value": "jerk_travel"},
        "jerk_support": {"default_value": 20, "value": "jerk_print"},
        "jerk_support_interface": {"default_value": 20, "value": "jerk_support"},
        "jerk_support_roof": {
            "default_value": 20,
            "value": "extruderValue(support_roof_extruder_nr, 'jerk_support_interface')",
        },
    }
    for key, value in (overrides or {}).items():
        entries.setdefault(key, {})["value"] = value
    data["settings"]["jerk"] = {"children": entries}
    base.write_text(json.dumps(data), encoding="utf-8")
    return base


def test_native_jerk_reaches_both_engine_levels_and_preserves_role_choices(tmp_path: Path) -> None:
    """M205 und Zeitschätzung bekommen dieselben Rollen, auch ohne Beschleunigungswahl."""
    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_wall_0": 3, "jerk_layer_0": 2})
    config = _written(engine, "creality-k1-max", tmp_path)
    command = handover._command(
        handover.SlicerSetup(engine, "cura"), [tmp_path / "teil.stl"], config, tmp_path
    )
    for key, value in {
        "jerk_enabled": "true",
        "jerk_travel_enabled": "true",
        "jerk_print": "5",
        "jerk_wall": "5",
        "jerk_wall_0": "3",
        "jerk_infill": "5",
        "jerk_travel": "10",
        "jerk_print_layer_0": "2",
        "jerk_travel_layer_0": "10",
        "jerk_support_roof": "5",
    }.items():
        assert command.count(f"{key}={value}") == 2, key


def test_disabled_native_jerk_stays_disabled(tmp_path: Path) -> None:
    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_enabled": False, "jerk_print": "unknown()"})
    config = _written(engine, "creality-k1-max", tmp_path)
    assert config.written["jerk_enabled"] == "false"
    assert "jerk_print" not in config.written


@pytest.mark.parametrize("formula", ["unknown()", "jerk_print + 0", "__import__('os').getcwd()"])
def test_unknown_native_jerk_never_falls_back_to_engine_defaults(
    tmp_path: Path, formula: str
) -> None:
    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_wall_0": formula})
    with pytest.raises(ExternalToolError) as caught:
        _written(engine, "creality-k1-max", tmp_path)
    assert caught.value.suggestions


def test_jerk_instance_choice_recalculates_dependants_before_export(tmp_path: Path) -> None:
    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    base = _with_jerk(engine)
    chain = slicer_profiles._cura_definition_values(
        base,
        (),
        overrides={"jerk_print": "6", "jerk_wall_0": "3", "jerk_travel_layer_0": "4"},
        resolve_jerk=True,
    )
    profile = profiles.make_profile("creality-k1-max", "pla")
    motion = handover._cura_motion_values(chain, {}, profile.printer)
    assert float(motion["jerk_infill"]) == pytest.approx(6)
    assert float(motion["jerk_travel"]) == pytest.approx(12)
    assert float(motion["jerk_wall_0"]) == pytest.approx(3)
    assert float(motion["jerk_travel_layer_0"]) == pytest.approx(4)


def test_cura_window_and_cli_use_the_same_native_jerk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import configparser
    import zipfile

    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_infill": 7, "jerk_travel_layer_0": 4})
    definition = engine.parent / "share/cura/resources/definitions/creality_k1max.def.json"
    monkeypatch.setattr(
        slicer_profiles,
        "cura_active_machine",
        lambda _exe: slicer_profiles.CuraActiveMachine("Werkstatt", definition),
    )
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: "")
    monkeypatch.setattr(
        slicer_profiles, "cura_quality_types", lambda *_args, **_kwargs: {"draft": 0.2}
    )
    profile = profiles.make_profile("creality-k1-max", "pla")
    setup = handover.SlicerSetup(engine, "cura")
    config = _written(engine, "creality-k1-max", tmp_path)
    model = tmp_path / "part.3mf"
    handover.cura_profile_beside(model, print_settings.resolve(profile), profile, setup)
    with zipfile.ZipFile(model.with_suffix(".curaprofile")) as archive:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(archive.read("solidon").decode("utf-8"))
    assert parser["values"]["jerk_enabled"] == "True"
    for key, value in config.written.items():
        if key.startswith("jerk_") and not key.endswith("enabled"):
            assert float(parser["values"][key]) == pytest.approx(float(value))
    assert (
        handover.for_the_cura_window({"jerk_wall_0": "2"}, machine={"jerk_wall_0": "5"})[
            "jerk_wall_0"
        ]
        == "2"
    )


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, None, "broken"])
def test_invalid_native_jerk_is_not_sent_to_cura(tmp_path: Path, value: object) -> None:
    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_wall_0": value})
    with pytest.raises(ExternalToolError):
        _written(engine, "creality-k1-max", tmp_path)


@pytest.mark.parametrize("native, chosen", [(False, "True"), (True, "False")])
def test_explicit_instance_jerk_switch_wins(tmp_path: Path, native: bool, chosen: str) -> None:
    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    base = _with_jerk(engine, {"jerk_enabled": native})
    chain = slicer_profiles._cura_definition_values(
        base, (), overrides={"jerk_enabled": chosen}, resolve_jerk=True
    )
    motion = handover._cura_motion_values(chain, {}, profiles.make_profile().printer)
    assert motion["jerk_enabled"] == chosen.lower()
    assert ("jerk_print" in motion) is (chosen == "True")


def _jerk_instance(engine: Path, tmp_path: Path) -> Path:
    """Der native Containerstapel mit Qualität, Änderungsprofil und Extruderwerten."""
    user = tmp_path / "user_root"
    for folder in ("machine_instances", "quality", "quality_changes", "user", "extruders"):
        (user / folder).mkdir(parents=True, exist_ok=True)
    (user / "machine_instances" / "local.global.cfg").write_text(
        "[general]\nversion = 5\nname = Local\nid = local\n[containers]\n"
        "0 = local_user\n1 = changes\n2 = empty_intent\n3 = native_quality\n"
        "4 = empty_material\n5 = empty_variant\n6 = empty_definition_changes\n7 = creality_k1max\n",
        encoding="utf-8",
    )
    for folder, name, content in (
        ("quality", "native_quality", "jerk_print = 6\njerk_infill = 7\n"),
        ("quality_changes", "changes", "jerk_print = 8\njerk_wall_0 = 3\n"),
        (
            "user",
            "local_user",
            "machine_nozzle_size = 0.4\nmachine_extruder_count = 1\njerk_print = 9\n",
        ),
        ("user", "extruder_user", "jerk_layer_0 = 2\n"),
    ):
        (user / folder / f"{name}.inst.cfg").write_text(
            f"[general]\nname = {name}\n[values]\n{content}", encoding="utf-8"
        )
    (user / "extruders" / "local.extruder.cfg").write_text(
        "[general]\nversion = 4\n[metadata]\nmachine = local\nposition = 0\n"
        "[containers]\n0 = extruder_user\n1 = empty_quality_changes\n2 = empty_intent\n"
        "3 = empty_quality\n4 = empty_material\n5 = empty_variant\n"
        "6 = empty_definition_changes\n7 = fdmextruder\n",
        encoding="utf-8",
    )
    return user


def test_native_jerk_uses_all_selected_containers_in_priority_order(tmp_path: Path) -> None:
    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_jerk(engine)
    user = _jerk_instance(engine, tmp_path)
    roots = (engine.parent / "share/cura", user)
    [(entry, native)] = list(
        slicer_profiles._cura_machine_instances(roots, {}, {}, resolve_jerk=True)
    )
    assert entry.cura_instance is not None
    assert float(native["jerk_print"]) == pytest.approx(9)
    assert float(native["jerk_wall_0"]) == pytest.approx(3)
    assert float(native["jerk_infill"]) == pytest.approx(7)
    assert float(native["jerk_print_layer_0"]) == pytest.approx(2)


def test_missing_selected_jerk_container_does_not_restore_factory_values(tmp_path: Path) -> None:
    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_jerk(engine)
    user = _jerk_instance(engine, tmp_path)
    path = user / "quality_changes" / "changes.inst.cfg"
    path.unlink()
    roots = (engine.parent / "share/cura", user)
    assert not list(slicer_profiles._cura_machine_instances(roots, {}, {}, resolve_jerk=True))


@pytest.mark.parametrize("enabled", [False, True])
def test_only_active_jerk_rejects_different_extruder_roles(tmp_path: Path, enabled: bool) -> None:
    """Ausgeschaltete Rollen unterscheiden keine wirksame Maschinensteuerung."""
    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_enabled": enabled, "jerk_support_roof": 5})
    user = _jerk_instance(engine, tmp_path)
    global_user = user / "user/local_user.inst.cfg"
    global_user.write_text(
        global_user.read_text(encoding="utf-8").replace(
            "machine_extruder_count = 1", "machine_extruder_count = 2"
        ),
        encoding="utf-8",
    )
    (user / "extruders/second.extruder.cfg").write_text(
        (user / "extruders/local.extruder.cfg")
        .read_text(encoding="utf-8")
        .replace("position = 0", "position = 1")
        .replace("extruder_user", "second_user"),
        encoding="utf-8",
    )
    (user / "user/second_user.inst.cfg").write_text(
        "[general]\nname = Second\n[values]\njerk_layer_0 = 3\n", encoding="utf-8"
    )
    roots = (engine.parent / "share/cura", user)
    found = list(slicer_profiles._cura_machine_instances(roots, {}, {}, resolve_jerk=True))
    if enabled:
        assert not found
        return
    [(_entry, native)] = found
    written = handover._cura_motion_values(native, {}, profiles.make_profile().printer)
    assert written["jerk_enabled"] == "false"
    assert "jerk_layer_0" not in written
    assert native["machine_extruder_count"] == 2


@pytest.mark.parametrize("key", ["jerk_enabled", "jerk_travel_enabled"])
@pytest.mark.parametrize("global_value", [False, True])
def test_global_jerk_switch_ignores_stale_extruder_values(
    tmp_path: Path, key: str, global_value: bool
) -> None:
    """Curas globale Schalter umgehen Extrudercontainer auch bei alten Restwerten."""
    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_jerk(engine)
    user = _jerk_instance(engine, tmp_path)
    for name, value in (("local_user", global_value), ("extruder_user", not global_value)):
        container = user / f"user/{name}.inst.cfg"
        container.write_text(
            container.read_text(encoding="utf-8") + f"{key} = {value}\n", encoding="utf-8"
        )
    roots = (engine.parent / "share/cura", user)
    [(_entry, native)] = list(
        slicer_profiles._cura_machine_instances(roots, {}, {}, resolve_jerk=True)
    )
    assert native[key] is global_value


@pytest.mark.parametrize("printing", [False, True])
@pytest.mark.parametrize("travel", [False, True])
@pytest.mark.parametrize("count", [1, 2])
@pytest.mark.parametrize("role", ["jerk_layer_0", "jerk_travel", "jerk_travel_layer_0"])
@pytest.mark.parametrize("variant", ["same", "different", "invalid"])
@pytest.mark.parametrize("stale", [False, True])
def test_jerk_switches_limit_effective_extruder_roles(
    tmp_path: Path,
    printing: bool,
    travel: bool,
    count: int,
    role: str,
    variant: str,
    stale: bool,
) -> None:
    """Nur wirksame Rollen und globale Schalter bestimmen die gemeinsame Steuerung."""
    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_support_roof": 5})
    user = _jerk_instance(engine, tmp_path)
    container = user / "user/local_user.inst.cfg"
    container.write_text(
        container.read_text(encoding="utf-8").replace(
            "machine_extruder_count = 1", f"machine_extruder_count = {count}"
        )
        + f"jerk_enabled = {printing}\njerk_travel_enabled = {travel}\n",
        encoding="utf-8",
    )
    template = (user / "extruders/local.extruder.cfg").read_text(encoding="utf-8")
    for index in range(count):
        name = "extruder_user" if index == 0 else "second_user"
        value = (
            "unknown()"
            if variant == "invalid"
            else str(3 if index and variant == "different" else 2)
        )
        (user / f"user/{name}.inst.cfg").write_text(
            f"[general]\nname = {name}\n[values]\n{role} = {value}\n"
            + (
                f"jerk_enabled = {not printing}\njerk_travel_enabled = {not travel}\n"
                if stale
                else ""
            ),
            encoding="utf-8",
        )
        if index:
            (user / "extruders/second.extruder.cfg").write_text(
                template.replace("position = 0", "position = 1").replace("extruder_user", name),
                encoding="utf-8",
            )
    found = list(
        slicer_profiles._cura_machine_instances(
            (engine.parent / "share/cura", user), {}, {}, resolve_jerk=True
        )
    )
    active = printing and (travel or role == "jerk_layer_0")
    rejected = active and (variant == "invalid" or (variant == "different" and count == 2))
    if rejected:
        assert not found
        return
    [(_entry, native)] = found
    written = handover._cura_motion_values(native, {}, profiles.make_profile().printer)
    assert written["jerk_enabled"] == str(printing).lower()
    if printing:
        assert written["jerk_travel_enabled"] == str(travel).lower()
    if active:
        assert float(written[role]) == pytest.approx(2)
    else:
        assert role not in written


@pytest.mark.parametrize("role", ["jerk_travel", "jerk_travel_layer_0"])
def test_disabled_unknown_travel_jerk_reaches_cli_and_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, role: str
) -> None:
    """Inaktive Formeln gelangen weder in Engine-Argumente noch in das Importprofil."""
    import configparser
    import zipfile

    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_travel_enabled": False, role: "unknown()"})
    definition = engine.parent / "share/cura/resources/definitions/creality_k1max.def.json"
    monkeypatch.setattr(
        slicer_profiles,
        "cura_active_machine",
        lambda _exe: slicer_profiles.CuraActiveMachine("Werkstatt", definition),
    )
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: "")
    monkeypatch.setattr(
        slicer_profiles, "cura_quality_types", lambda *_args, **_kwargs: {"draft": 0.2}
    )
    config = _written(engine, "creality-k1-max", tmp_path)
    setup = handover.SlicerSetup(engine, "cura")
    command = handover._command(setup, [tmp_path / "part.stl"], config, tmp_path)
    profile = profiles.make_profile("creality-k1-max", "pla")
    model = tmp_path / "part.stl"
    handover.cura_profile_beside(model, print_settings.resolve(profile), profile, setup)
    with zipfile.ZipFile(model.with_suffix(".curaprofile")) as archive:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(archive.read("solidon").decode("utf-8"))
    assert command.count("jerk_travel_enabled=false") == 2
    assert not any(value.startswith(("jerk_travel=", "jerk_travel_layer_0=")) for value in command)
    assert parser["values"]["jerk_travel_enabled"] == "False"
    assert "jerk_travel" not in parser["values"]
    assert "jerk_travel_layer_0" not in parser["values"]


@pytest.mark.parametrize("source", ["definition", "instance"])
@pytest.mark.parametrize("way", ["cli", "window"])
@pytest.mark.parametrize("printing", [False, True])
@pytest.mark.parametrize("travel", [False, True])
@pytest.mark.parametrize("role", ["jerk_layer_0", "jerk_travel", "jerk_travel_layer_0"])
@pytest.mark.parametrize("value", ["4", "unknown()"])
def test_jerk_handover_uses_only_active_definition_or_instance_roles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    way: str,
    printing: bool,
    travel: bool,
    role: str,
    value: str,
) -> None:
    """Beide echten Schreiber erhalten dieselbe wirksame Definition oder Nutzerinstanz."""
    import configparser
    import zipfile

    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    choices = {"jerk_enabled": printing, "jerk_travel_enabled": travel, role: value}
    _with_jerk(engine, choices if source == "definition" else {})
    definition = engine.parent / "share/cura/resources/definitions/creality_k1max.def.json"
    chosen = ""
    if source == "instance":
        user = _jerk_instance(engine, tmp_path)
        container = user / "user/local_user.inst.cfg"
        container.write_text(
            container.read_text(encoding="utf-8")
            + "".join(f"{key} = {setting}\n" for key, setting in choices.items()),
            encoding="utf-8",
        )
        (user / "user/extruder_user.inst.cfg").write_text(
            "[general]\nname = Extruder\n[values]\n", encoding="utf-8"
        )
        (user / "cura.cfg").write_text(
            "[general]\nversion = 7\n[cura]\nactive_machine = local\n", encoding="utf-8"
        )
        monkeypatch.setattr(slicer_profiles, "user_roots", lambda *_args: [user])
        monkeypatch.setattr(slicer_profiles, "_cura_user_roots", lambda *_args: [user])
        chosen = "cura-instance:local"
    else:
        monkeypatch.setattr(
            slicer_profiles,
            "cura_active_machine",
            lambda _exe: slicer_profiles.CuraActiveMachine("Werkstatt", definition),
        )
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: chosen)
    monkeypatch.setattr(
        slicer_profiles, "cura_quality_types", lambda *_args, **_kwargs: {"draft": 0.2}
    )
    setup = handover.SlicerSetup(engine, "cura", machine_profile=chosen)
    profile = profiles.make_profile("creality-k1-max", "pla")
    settings = print_settings.resolve(profile)

    def write() -> dict[str, str]:
        if way == "cli":
            config = handover.write_config(settings, profile, setup, tmp_path)
            command = handover._command(setup, [tmp_path / "part.stl"], config, tmp_path)
            assert command.count(f"jerk_enabled={str(printing).lower()}") == 2
            return dict(config.written)
        model = tmp_path / "part.stl"
        handover.cura_profile_beside(model, settings, profile, setup)
        with zipfile.ZipFile(model.with_suffix(".curaprofile")) as archive:
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(archive.read("solidon").decode("utf-8"))
        return dict(parser["values"])

    active = printing and (travel or role == "jerk_layer_0")
    if active and value == "unknown()":
        with pytest.raises(ExternalToolError) as caught:
            write()
        assert caught.value.suggestions
        return
    written = write()
    assert written["jerk_enabled"].casefold() == str(printing).lower()
    if active:
        assert float(written[role]) == pytest.approx(4)
    else:
        assert role not in written


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("container_name", ["quality/native_quality", "quality_changes/changes"])
@pytest.mark.parametrize("way", ["cli", "window"])
def test_concrete_process_switch_overrides_unknown_definition_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    container_name: str,
    way: str,
) -> None:
    """Eine gültige Prozesswahl wird vor der Prüfung des Definitionsschalters gelesen."""
    import configparser
    import zipfile

    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_enabled": "unknown()"})
    user = _jerk_instance(engine, tmp_path)
    container = user / f"{container_name}.inst.cfg"
    container.write_text(
        container.read_text(encoding="utf-8") + f"jerk_enabled = {enabled}\n",
        encoding="utf-8",
    )
    [(_entry, native)] = list(
        slicer_profiles._cura_machine_instances(
            (engine.parent / "share/cura", user), {}, {}, resolve_jerk=True
        )
    )
    assert native["jerk_enabled"] is enabled
    (user / "cura.cfg").write_text(
        "[general]\nversion = 7\n[cura]\nactive_machine = local\n", encoding="utf-8"
    )
    monkeypatch.setattr(slicer_profiles, "user_roots", lambda *_args: [user])
    monkeypatch.setattr(slicer_profiles, "_cura_user_roots", lambda *_args: [user])
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_args: "cura-instance:local")
    monkeypatch.setattr(
        slicer_profiles, "cura_quality_types", lambda *_args, **_kwargs: {"draft": 0.2}
    )
    setup = handover.SlicerSetup(engine, "cura", machine_profile="cura-instance:local")
    profile = profiles.make_profile("creality-k1-max", "pla")
    settings = print_settings.resolve(profile)
    if way == "cli":
        config = handover.write_config(settings, profile, setup, tmp_path)
        written = config.written
    else:
        handover.cura_profile_beside(tmp_path / "part.stl", settings, profile, setup)
        with zipfile.ZipFile(tmp_path / "part.curaprofile") as archive:
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(archive.read("solidon").decode("utf-8"))
        written = dict(parser["values"])
    assert written["jerk_enabled"].casefold() == str(enabled).lower()


@pytest.mark.parametrize("spiral, travel, first", [(False, 30, 12), (True, 5, 2)])
def test_native_travel_and_first_layer_relationships_are_resolved(
    tmp_path: Path, spiral: bool, travel: float, first: float
) -> None:
    engine = cura_installation(tmp_path)
    _with_jerk(
        engine,
        {
            "magic_spiralize": spiral,
            "jerk_travel": "jerk_print if magic_spiralize else 30",
            "jerk_layer_0": 2,
            "jerk_travel_layer_0": "jerk_layer_0 * jerk_travel / jerk_print",
        },
    )
    config = _written(engine, "creality-k1-max", tmp_path)
    assert float(config.written["jerk_travel"]) == pytest.approx(travel)
    assert float(config.written["jerk_travel_layer_0"]) == pytest.approx(first)


@pytest.mark.parametrize(
    "key, value",
    [
        ("jerk_enabled", "broken"),
        ("jerk_travel_enabled", "broken"),
        ("machine_extruder_count", 2),
        ("jerk_wall", "jerk_wall_0"),
    ],
)
def test_ambiguous_jerk_never_enables_engine_defaults(
    tmp_path: Path, key: str, value: object
) -> None:
    engine = cura_installation(tmp_path)
    _with_jerk(engine, {key: value})
    with pytest.raises(ExternalToolError):
        _written(engine, "creality-k1-max", tmp_path)


def test_missing_jerk_dependency_remains_unknown(tmp_path: Path) -> None:
    engine = cura_installation(tmp_path)
    base = _with_jerk(engine)
    data = json.loads(base.read_text(encoding="utf-8"))
    del data["settings"]["jerk"]["children"]["jerk_wall"]
    base.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ExternalToolError):
        _written(engine, "creality-k1-max", tmp_path)


def test_enabled_creality_jerk_keeps_its_native_travel_alias(tmp_path: Path) -> None:
    """Creality setzt Leerfahrt gleich Druck; die Sovol-Basis verdoppelt sie."""
    engine = cura_installation(tmp_path)
    _with_jerk(engine, {"jerk_travel": "jerk_print"})
    config = _written(engine, "creality-k1-max", tmp_path)
    assert float(config.written["jerk_travel"]) == pytest.approx(5)
    assert float(config.written["jerk_travel_layer_0"]) == pytest.approx(5)


@pytest.mark.parametrize("read", ["selection", "bed"])
def test_unknown_jerk_keeps_printer_selection_and_active_bed_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, read: str
) -> None:
    """Unbekannte Bewegung sperrt die Übergabe, nicht die bekannten Maschinenmaße."""
    from app.core.export import slicer_profiles

    engine = cura_installation(tmp_path)
    _with_jerk(
        engine,
        {
            "machine_width": 300,
            "machine_depth": 300,
            "machine_height": 300,
            "machine_nozzle_size": 0.4,
            "jerk_support": "unknown()",
        },
    )
    user = _jerk_instance(engine, tmp_path)
    (user / "cura.cfg").write_text(
        "[general]\nversion = 7\n[cura]\nactive_machine = local\n", encoding="utf-8"
    )
    monkeypatch.setattr(slicer_profiles, "user_roots", lambda *_args: [user])
    monkeypatch.setattr(slicer_profiles, "_cura_user_roots", lambda *_args: [user])

    if read == "selection":
        found = slicer_profiles.discover_printers(engine, "cura")
        assert {"Local", "Creality K1 Max"} <= {printer.title for printer in found}
    else:
        active = slicer_profiles.cura_active_machine(engine)
        assert active is not None
        assert active.bed == pytest.approx((300, 300))

    setup = handover.SlicerSetup(engine, "cura", machine_profile="cura-instance:local")
    profile = profiles.make_profile("creality-k1-max", "pla")
    settings = print_settings.resolve(profile)
    with pytest.raises(ExternalToolError) as cli_error:
        handover.write_config(settings, profile, setup, tmp_path)
    assert cli_error.value.suggestions
    monkeypatch.setattr(
        slicer_profiles, "cura_quality_types", lambda *_args, **_kwargs: {"draft": 0.2}
    )
    with pytest.raises(ExternalToolError) as window_error:
        handover.cura_profile_beside(tmp_path / "part.stl", settings, profile, setup)
    assert window_error.value.suggestions
    assert not (tmp_path / "part.curaprofile").exists()


# Cura unter Linux: Flatpak und AppImage rechnen über Curas eigenen Lader (RM-521).


def _sliced(
    executable: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    during: Callable[[], None] | None = None,
) -> tuple[list[str], Path]:
    """Ein Würfel für den K1 Max über die echte Übergabe; zurück kommen Befehl und
    Arbeitsordner. ``during`` läuft, während CuraEngine rechnen würde."""
    model = tmp_path / "wuerfel.stl"
    model.write_bytes((Path(__file__).parent / "data" / "meshes" / "cube_clean.stl").read_bytes())
    captured: list[tuple[list[str], Path]] = []

    def run(command: list[str], workspace: Path, *_args: object, **_kwargs: object):
        _staged_from_the_workspace(command, workspace)
        if during is not None:
            during()
        captured.append((list(command), workspace))
        Path(command[command.index("-o") + 1]).write_text(_printed("G28"), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(handover, "_run_slicer", run)
    profile = profiles.make_profile("creality-k1-max", "pla")
    handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(executable, "cura"),
        output_dir=tmp_path / "aus",
    )
    assert len(captured) == 1
    return captured[0]


def _staged_from_the_workspace(command: list[str], workspace: Path) -> None:
    """Hinter ``slice`` zeigt jeder Pfad in den Arbeitsordner, und die Maschine ist der
    K1 Max — gefragt während des Laufs, danach ist der Ordner geräumt."""
    after = command[command.index("slice") + 1 :]
    paths = [
        Path(after[index + 1])
        for index, flag in enumerate(after[:-1])
        if flag in {"-d", "-j", "-l", "-o"}
    ]
    assert paths and all(path.is_relative_to(workspace) for path in paths)
    machine = Path(after[after.index("-j") + 1])
    assert json.loads(machine.read_text(encoding="utf-8"))["name"] == "Creality K1 Max"


def test_the_library_path_comes_from_apprun_env_in_its_order() -> None:
    """Gekürzt fand CuraEngine am Runner die ``libstdc++`` des Rechners und
    scheiterte an ``GLIBC_2.38``: Curas glibc zuerst, dann seine übrigen
    Bibliotheken, jede einmal; eine fremde Variable bleibt draußen — ein ``$``
    im Einhängepunkt selbst ist keine."""
    variables = cura_linux.read_environment(APPRUN_ENV + "APPDIR_LIBRARY_PATH_X=$HOME/lib\n")

    assert cura_linux.library_path(variables, "/app/cura") == FLATPAK_LIBRARIES
    assert cura_linux.library_path({"APPDIR_LIBRARY_PATH": "$APPDIR:$OTHER/lib"}, "/m") == "/m"
    assert cura_linux.library_path({"APPDIR_LIBRARY_PATH": "${APPDIR}/lib:$APPDIR"}, "/a$b") == (
        "/a$b/lib:/a$b"
    )
    assert cura_linux.linker(variables) == "lib64/ld-linux-x86-64.so.2"


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("{'lib/ld-linux-aarch64.so.1'}", "lib/ld-linux-aarch64.so.1"),
        ("{'/lib64/ld-linux-x86-64.so.2'}", cura_linux.DEFAULT_LINKER),
        ("{'../../ld.so'}", cura_linux.DEFAULT_LINKER),
        ("", cura_linux.DEFAULT_LINKER),
    ],
)
def test_the_loader_stays_inside_the_appdir(written: str, expected: str) -> None:
    assert cura_linux.linker({"APPDIR_LIBC_LINKER_PATH": written}) == expected


@pytest.mark.parametrize("folder", ["cura", "Cura-5.14"])
def test_cura_as_a_flatpak_computes_through_its_own_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, folder: str
) -> None:
    """Der Starter öffnet nur das Fenster, ``--command`` auf CuraEngine fand den
    Lader nicht (RM-521). Gerechnet wird über den Lader aus ``runtime/compat``
    mit dem Pfad aus ``AppRun.env``, der Arbeitsordner ist freigegeben, und die
    Druckerdefinition kommt aus dem ``/app`` des Pakets — vorher fehlte ``-j``.
    Lader und Bestand stehen am selben AppDir, wie auch der Ordner heißt."""
    launcher = flatpak_cura(tmp_path, monkeypatch, folder=folder)

    command, workspace = _sliced(launcher, monkeypatch, tmp_path)

    inside = f"/app/{folder}"
    assert command[: command.index("slice")] == [
        "flatpak",
        "run",
        f"--filesystem={workspace}",
        f"--command={inside}/runtime/compat/lib64/ld-linux-x86-64.so.2",
        "com.ultimaker.cura",
        "--library-path",
        FLATPAK_LIBRARIES.replace("/app/cura", inside),
        f"{inside}/CuraEngine",
    ]
    assert handover.console_refusal(launcher) is None
    root = slicer_profiles.install_root(launcher)
    assert root is not None and root.parent.parent.name == folder


@pytest.mark.parametrize(
    ("missing", "logged"),
    [
        ("environment", "AppRun.env"),
        ("loader", "no loader"),
        ("installation", "not visible"),
    ],
)
def test_a_flatpak_cura_without_its_loader_only_opens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    missing: str,
    logged: str,
) -> None:
    """Findet Solidon Lader, ``AppRun.env`` oder die Installation nicht, rechnet es
    nicht, sondern sagt im Druckdialog, dass nur Curas Fenster bleibt — und die
    Übergabe hält vor jedem Prozessstart mit demselben Satz an. Der Satz behauptet
    keine Ursache (Regel 21); welche es war, steht im Protokoll."""
    launcher = flatpak_cura(tmp_path, monkeypatch, **{missing: False})

    with caplog.at_level("INFO", logger="app.core.export.cura_linux"):
        refusal = handover.console_refusal(launcher)
    assert refusal is not None
    assert str(refusal) == str(cura_linux.WINDOW_ONLY)
    assert "Lader" not in str(refusal) and "fehlt" not in str(refusal)
    assert logged in caplog.text
    with pytest.raises(ExternalToolError) as caught:
        _sliced(launcher, monkeypatch, tmp_path)
    assert str(caught.value.detail) == str(cura_linux.WINDOW_ONLY)
    assert caught.value.suggestions
    assert handover.window_program(launcher) == launcher, "das Fenster bleibt"


def test_another_flatpak_slicer_is_not_refused_as_cura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Sperrsatz gilt Cura. Orca als Flatpak hat kein ``cura/`` und keinen
    Lader und rechnet trotzdem über seinen Starter."""
    system = tmp_path / "flatpak"
    launcher = system / "exports" / "bin" / "com.orcaslicer.OrcaSlicer"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("")
    program = system / "app" / "com.orcaslicer.OrcaSlicer" / "current" / "active" / "files"
    (program / "bin").mkdir(parents=True)
    (program / "bin" / "orca-slicer").write_bytes(b"")
    monkeypatch.setattr(discover, "_FLATPAK_EXPORTS", (str(launcher.parent),))
    monkeypatch.setattr(discover, "_FLATPAK_INSTALLATIONS", (str(system),))
    monkeypatch.setattr(discover, "in_flatpak", lambda: False)

    assert cura_linux.needs_loader(launcher), "ein Flatpak ist es"
    assert handover.console_refusal(launcher) is None


def test_cura_as_an_appimage_computes_while_it_is_mounted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Abbild bleibt eingehängt, solange CuraEngine rechnet, und ist danach
    beendet; CuraEngine startet über Lader und Pfad des Einhängepunkts. Die
    Drucker kommen aus einer Kopie, die nur einmal je Fassung entsteht — gelesen
    aus dem Abbild, eingehängt wird nur für den Lauf (RM-599)."""
    mounts: list[Path] = []
    copies: list[Path] = []
    appimage, point = appimage_cura(tmp_path, monkeypatch, mounts, copies=copies)
    ended = ended_mounts(monkeypatch)
    while_running: list[int] = []

    command, _workspace = _sliced(
        appimage, monkeypatch, tmp_path, during=lambda: while_running.append(len(ended))
    )

    assert while_running == [0], "das Einhängen des Laufs lebt, solange er rechnet"
    assert command[: command.index("slice")] == [
        str(point / "runtime" / "compat" / "lib64" / "ld-linux-x86-64.so.2"),
        "--library-path",
        cura_linux.library_path(cura_linux.read_environment(APPRUN_ENV), str(point)),
        str(point / "CuraEngine"),
    ]
    assert len(ended) == 1 and all(process.poll() is not None for process in ended)
    copy = slicer_profiles.install_root(appimage)
    assert copy is not None and not copy.is_relative_to(point)
    assert (
        slicer_profiles.cura_resources(copy) / "definitions" / "creality_k1max.def.json"
    ).is_file()
    found = slicer_profiles.find_profiles(appimage, "cura", ("machine",))
    assert "Creality K1 Max" in {entry.name for entry in found}
    assert mounts == [appimage], "eingehängt nur für den Lauf"
    assert copies == [appimage], "die Drucker einmal aus dem Abbild gelesen"
    assert handover.console_refusal(appimage) is None


def test_an_appimage_that_does_not_mount_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne FUSE scheitert das Einhängen. Die Absage sagt es mit Vorschlag, und
    was die Laufzeit dazu schrieb, reist als Grund mit — nie startet Solidon
    stattdessen das AppImage selbst als Rechenmaschine."""
    mounts: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts)
    failing_mount(tmp_path, monkeypatch, mounts)

    with (
        pytest.raises(ExternalToolError) as caught,
        cura_linux.engine(appimage, tmp_path, "Cura") as _program,
    ):
        pytest.fail("ohne Einhängepunkt kein Programm")

    assert str(caught.value.detail) == str(cura_linux.NOT_MOUNTED)
    assert caught.value.suggestions
    reason = str(caught.value.values["reason"])
    assert "fuse: device not found" in reason and "127" in reason


def test_cancelling_while_mounting_cancels_and_is_no_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Abbruch während des Einhängens ist ein Abbruch (§15.6), keine Absage
    „ließ sich nicht einhängen“; der Einhängeprozess endet."""
    from app.core.scene.cancel import CancelSignal

    mounts: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts, delay=60.0)
    ended = ended_mounts(monkeypatch)
    token = CancelSignal()
    timer = threading.Timer(0.3, token.cancel)
    timer.start()
    try:
        with (
            pytest.raises(OperationCancelled),
            cura_linux.engine(appimage, tmp_path, "Cura", token) as _program,
        ):
            pytest.fail("abgebrochen gibt es kein Programm")
    finally:
        timer.cancel()
    assert len(ended) == 1 and ended[0].poll() is not None


def test_the_window_thread_never_waits_for_the_printer_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Druckdialog fragt Curas Bestand im Fensterfaden (``_rebase``). Dort
    antwortet die Kopie nur, wenn sie schon da ist: Weder hängt der Fensterfaden
    selbst ein noch liest er das Abbild, noch wartet er auf einen Arbeiter, der
    gerade kopiert."""
    mounts: list[Path] = []
    copies: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts, delay=2.0, copies=copies)
    monkeypatch.setattr(image_copies, "_never_waits", None)
    image_copies.never_wait_in(threading.current_thread())

    assert slicer_profiles.install_root(appimage) is None
    assert not mounts and not copies, "der Fensterfaden liest nichts"

    worker = threading.Thread(target=cura_linux.appimage_resources, args=(appimage,))
    worker.start()
    deadline = time.monotonic() + 10.0
    while not copies and time.monotonic() < deadline:
        time.sleep(0.01)
    started = time.monotonic()
    assert slicer_profiles.install_root(appimage) is None
    assert time.monotonic() - started < 1.0, "nicht auf den kopierenden Arbeiter gewartet"
    worker.join(30.0)

    copy = slicer_profiles.install_root(appimage)
    assert copy is not None and (copy / "resources" / "definitions").is_dir()
    assert copies == [appimage] and not mounts


def test_the_window_waits_for_no_copy_and_rebases_after_the_worker() -> None:
    """Der Anschluss: ``build_application`` nennt den Fensterfaden, der
    Cura-Arbeiter des Druckdialogs legt die Kopie an, und sein Ergebnis gründet
    für eine AppImage-Cura neu. Gelesen am Quelltext, ohne Fenster."""
    import ast

    root = Path(__file__).resolve().parent.parent

    def body(path: str, *names: str) -> str:
        tree = ast.parse((root / path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == names[0] and len(names) > 1:
                return next(
                    ast.unparse(item)
                    for item in node.body
                    if isinstance(item, ast.FunctionDef) and item.name == names[1]
                )
            if isinstance(node, ast.FunctionDef) and node.name == names[0] and len(names) == 1:
                return ast.unparse(node)
        raise AssertionError(names)

    build = body("app/ui/app.py", "build_application")
    assert "appimage.never_wait_in(threading.current_thread())" in build
    work = body("app/ui/print_settings_dialog.py", "_CuraPrinterWorker", "work")
    assert work.index("install_root(self._executable)") < work.index("chosen_printer(")
    found = body("app/ui/print_settings_dialog.py", "PrintSettingsDialog", "_cura_printer_found")
    assert "self._foundation_key = None" in found and "self._rebase()" in found


@pytest.mark.parametrize(
    ("loader", "engine"),
    [
        (Link("../lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"), True),
        (Link("/lib64/ld-linux-x86-64.so.2"), False),
    ],
    ids=["inside", "host"],
)
def test_curas_printers_and_engine_come_from_the_image_without_starting_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loader: Link, engine: bool
) -> None:
    """RM-599: Drucker und die Frage nach der Rechenmaschine beantwortet das Abbild,
    ohne dass ein Prozess startet (Regel 11). Curas Lader ist darin eine
    Verknüpfung nach ``lib/x86_64-linux-gnu`` (Cura 5.13); eine, die auf den
    Rechner zeigt, zählt nicht."""
    mounts: list[Path] = []
    appimage, point = appimage_cura(tmp_path, monkeypatch, mounts)
    tree = tree_of(point)
    compat = tree["runtime"]["compat"]
    compat["lib"] = {"x86_64-linux-gnu": {"ld-linux-x86-64.so.2": b"ELF"}}
    compat["lib64"] = {"ld-linux-x86-64.so.2": loader}
    appimage_file(appimage, tree, compression="gzip")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("zum Lesen der Drucker startet kein Prozess")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)

    copy = cura_linux.appimage_resources(appimage)

    assert copy is not None
    assert (copy / "resources" / "definitions" / "creality_k1max.def.json").is_file()
    assert cura_linux.engine_missing(appimage) is not engine
    assert not mounts


def test_the_printers_of_an_appimage_are_copied_once_per_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mounts: list[Path] = []
    copies: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts, copies=copies)

    first = cura_linux.appimage_resources(appimage)
    again = cura_linux.appimage_resources(appimage)
    assert first is not None and first == again
    assert len(copies) == 1 and not mounts
    stamp = json.loads((first.parent.parent / image_copies.STAMP).read_text(encoding="utf-8"))
    assert stamp["engine"] is True

    newer = appimage.stat().st_mtime_ns + 10**9
    os.utime(appimage, ns=(newer, newer))
    assert cura_linux.appimage_resources(appimage) == first
    assert len(copies) == 2, "eine neue Fassung wird neu gelesen"


def test_the_copy_of_a_removed_appimage_is_cleared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cura trägt die Version im Dateinamen: Nach einem Update bliebe die Kopie
    der alten Fassung (rund 26 MB) für immer liegen. Geräumt wird nur, was zu
    keiner Datei mehr gehört."""
    mounts: list[Path] = []
    kept, _point = appimage_cura(
        tmp_path / "andere", monkeypatch, mounts, name="Cura-Beta-5.14.0.AppImage"
    )
    kept_copy = cura_linux.appimage_resources(kept)
    old, _point = appimage_cura(
        tmp_path, monkeypatch, mounts, name="UltiMaker-Cura-5.12.0-linux-X64.AppImage"
    )
    old_copy = cura_linux.appimage_resources(old)
    assert kept_copy is not None and old_copy is not None
    old.unlink()

    new, _point = appimage_cura(tmp_path / "neu", monkeypatch, mounts)
    assert cura_linux.appimage_resources(new) is not None

    assert not old_copy.exists(), "die Kopie der entfernten Fassung ist geräumt"
    assert kept_copy.is_dir(), "die einer vorhandenen bleibt"


def test_a_failed_copy_is_tried_again_after_searching_anew(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ließ sich das Abbild nicht lesen (etwa noch im Herunterladen), bekommt der
    Kunde nach *Neu suchen* Curas Drucker ohne Neustart; ohne neue Suche wird
    nicht bei jeder Frage erneut gelesen."""
    mounts: list[Path] = []
    copies: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts, copies=copies)
    working = cura_linux._read_resources

    def damaged(image: Path, target: Path) -> bool | None:
        copies.append(image)
        raise squashfs.UnreadableImageError("the file ends before 4096")

    monkeypatch.setattr(cura_linux, "_read_resources", damaged)
    assert cura_linux.appimage_resources(appimage) is None
    monkeypatch.setattr(cura_linux, "_read_resources", working)
    assert cura_linux.appimage_resources(appimage) is None
    assert len(copies) == 1, "das Nein gilt bis zur neuen Suche"

    discover.forget_cache()
    assert cura_linux.appimage_resources(appimage) is not None
    assert len(copies) == 2 and not mounts


def test_a_damaged_gzip_block_in_curas_image_is_refused_once_without_a_half_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cura 5.13 packt mit gzip. Ein gekipptes Bit in einem Block ist ein
    unlesbares Abbild: kein Absturz, kein Zwischenordner im Cache, gelesen einmal
    je Fassung bis *Neu suchen* — am echt beschädigten Abbild, nicht an einer
    Attrappe des Lesers. Vorher entkam ``zlib.error`` aus dem Druckdialog, und
    jede Frage las das Abbild erneut."""
    monkeypatch.setattr(cura_linux.PRINTER_COPIES, "root", lambda: tmp_path / "cache")
    monkeypatch.setattr(cura_linux.PRINTER_COPIES, "_kept", {})
    monkeypatch.setattr(cura_linux.PRINTER_COPIES, "_failed", {})
    mounts: list[Path] = []
    copies: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts, copies=copies)
    data = bytearray(appimage.read_bytes())
    for at in range(IMAGE_AT + 96, IMAGE_AT + 100):
        data[at] ^= 0xFF
    appimage.write_bytes(bytes(data))

    for _question in range(3):
        assert slicer_profiles.install_root(appimage) is None
    assert slicer_profiles.find_profiles(appimage, "cura", ("machine",)) == []
    assert handover.console_refusal(appimage) is None, "unbekannt sperrt nicht"
    assert copies == [appimage]
    assert list((tmp_path / "cache").iterdir()) == [], "kein halber Zwischenordner"

    discover.forget_cache()
    assert cura_linux.appimage_resources(appimage) is None
    assert copies == [appimage, appimage] and not mounts


@pytest.mark.parametrize("limit", ["files", "bytes", "environment"])
def test_curas_copy_counts_its_limits_over_all_folders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    """Dateizahl und Bytezahl gelten für Curas ganze Kopie, nicht je Ordner
    (``definitions``, ``extruders`` …), und ``AppRun.env`` hat eine eigene
    kleine Grenze. Vorher durfte jeder der sechs Ordner die volle Grenze
    nehmen und ``AppRun.env`` bis 1 GiB. Gezeigt mit herabgesetzten Grenzen,
    die jeder Ordner für sich einhält, die Kopie als Ganzes aber nicht."""
    monkeypatch.setattr(cura_linux.PRINTER_COPIES, "root", lambda: tmp_path / "cache")
    monkeypatch.setattr(cura_linux.PRINTER_COPIES, "_kept", {})
    monkeypatch.setattr(cura_linux.PRINTER_COPIES, "_failed", {})
    mounts: list[Path] = []
    appimage, point = appimage_cura(tmp_path, monkeypatch, mounts)
    resources = point / "share" / "cura" / "resources"
    folders = [
        [path for path in (resources / name).rglob("*") if path.is_file()]
        for name in cura_linux.RESOURCE_FOLDERS
        if (resources / name).is_dir()
    ]
    assert len(folders) >= 2, "mehr als ein Ordner, sonst prüft der Fall nichts"
    if limit == "files":
        monkeypatch.setattr(squashfs, "MAX_COPIED_FILES", max(len(files) for files in folders))
    elif limit == "bytes":
        sizes = [sum(path.stat().st_size for path in files) for files in folders]
        assert max(sizes) < sum(sizes)
        monkeypatch.setattr(squashfs, "MAX_COPIED_BYTES", max(sizes))
    else:
        monkeypatch.setattr(cura_linux, "ENVIRONMENT_BYTES", 16)

    assert cura_linux.appimage_resources(appimage) is None
    assert list((tmp_path / "cache").iterdir()) == []
    assert not mounts


def test_a_copy_that_cannot_replace_the_old_one_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Bleibt die alte Kopie liegen (Rechte, offene Dateien), fehlen Curas Drucker —
    das Protokoll nennt Ort und Grund statt eines angenommenen zweiten Solidon."""
    mounts: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts)

    def refuse(self: Path, target: Path) -> Path:
        raise PermissionError(13, "Zugriff verweigert", str(self))

    monkeypatch.setattr(Path, "rename", refuse)
    with caplog.at_level("WARNING", logger="app.core.export.appimage"):
        assert cura_linux.appimage_resources(appimage) is None
    assert "cannot replace the printers" in caplog.text and "Zugriff verweigert" in caplog.text


def test_an_appimage_without_its_loader_only_opens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was das Einlesen der Drucker über die Rechenmaschine erfahren hat, sagt der
    Druckdialog, ohne selbst einzuhängen; vorher ist es unbekannt und sperrt nicht."""
    mounts: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts, loader=False)

    assert handover.console_refusal(appimage) is None
    assert not mounts, "der Dialog hängt nichts ein"
    assert cura_linux.appimage_resources(appimage) is not None
    refusal = handover.console_refusal(appimage)
    assert refusal is not None and str(refusal) == str(cura_linux.WINDOW_ONLY)
    with pytest.raises(ExternalToolError) as caught:
        _sliced(appimage, monkeypatch, tmp_path)
    assert str(caught.value.detail) == str(cura_linux.WINDOW_ONLY)


def test_the_mount_ends_with_the_block_also_after_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "einhaengen.py"
    script.write_text(MOUNT_SCRIPT, encoding="utf-8")
    ended = ended_mounts(monkeypatch)

    with (
        pytest.raises(RuntimeError),
        cura_linux._mounted([sys.executable, str(script), str(tmp_path)], None) as mount,
    ):
        assert mount.point == tmp_path
        raise RuntimeError("Lauf gescheitert")

    assert len(ended) == 1 and ended[0].poll() is not None


@pytest.mark.parametrize("cancelled", [False, True])
def test_a_mount_that_never_answers_gives_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancelled: bool
) -> None:
    """Ohne Einhängepunkt kein Warten bis zum Zeitlimit des Slicers: Abbruch und
    eigene Zeitgrenze beenden den Prozess, und es gibt keinen Punkt."""
    from app.core.scene.cancel import CancelSignal

    script = tmp_path / "stumm.py"
    script.write_text(MOUNT_SCRIPT, encoding="utf-8")
    token = CancelSignal()
    if cancelled:
        token.cancel()
    ended = ended_mounts(monkeypatch)

    with cura_linux._mounted([sys.executable, str(script)], token, seconds=1.0) as mount:
        assert mount.point is None
        assert mount.reason

    assert len(ended) == 1 and ended[0].poll() is not None


def test_from_solidons_flatpak_the_appimage_mounts_where_both_see_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Aus dem Sandkasten ist das ``/tmp`` des Rechners unsichtbar; die Laufzeit
    beachtet ``TMPDIR``, und ``--watch-bus`` hängt auch dann aus, wenn
    ``flatpak-spawn`` ohne Signal stirbt (gemessen am Runner)."""
    appimage = tmp_path / "UltiMaker-Cura-5.13.0-linux-X64.AppImage"
    monkeypatch.setattr(discover, "in_flatpak", lambda: True)
    monkeypatch.setattr(discover, "exchange_dir", lambda: tmp_path / "austausch")

    assert cura_linux.mount_command(appimage) == [
        "flatpak-spawn",
        "--host",
        "--watch-bus",
        f"--env=TMPDIR={tmp_path / 'austausch'}",
        str(appimage),
        "--appimage-mount",
    ]
    assert (tmp_path / "austausch").is_dir()


@pytest.mark.parametrize("setpriv", ["/usr/bin/setpriv", None])
def test_outside_a_flatpak_the_mount_command_carries_setpriv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setpriv: str | None
) -> None:
    """Draußen startet das Einhängen in eigener Prozessgruppe; stirbt Solidon hart,
    erreicht es kein Signal. ``setpriv --pdeathsig`` schickt eines, wo es da ist."""
    appimage = tmp_path / "UltiMaker-Cura-5.13.0-linux-X64.AppImage"
    monkeypatch.setattr(discover, "in_flatpak", lambda: False)
    monkeypatch.setattr(cura_linux.shutil, "which", lambda name: setpriv)

    expected = [str(appimage), "--appimage-mount"]
    if setpriv:
        expected = [setpriv, "--pdeathsig", "TERM", "--", *expected]
    assert cura_linux.mount_command(appimage) == expected


#: Ein Kindprozess wie Solidon: hängt über ``mount_command`` ein, meldet den
#: Punkt und wartet; ``plain`` nimmt ihm ``setpriv``.
_HOLDER = (
    "import sys, time\n"
    "from pathlib import Path\n"
    "from app.core import discover\n"
    "from app.core.export import cura_linux\n"
    "discover.in_flatpak = lambda: False\n"
    "if sys.argv[2] == 'plain':\n"
    "    cura_linux.shutil.which = lambda name: None\n"
    "with cura_linux._mounted(cura_linux.mount_command(Path(sys.argv[1])), None) as mount:\n"
    "    print(mount.point, flush=True)\n"
    "    time.sleep(60)\n"
)


def _alive(pid: int) -> bool:
    """Lebt der Prozess — ein Zombie zählt nicht?"""
    try:
        state = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()[0]
    except OSError:
        return False
    return state != "Z"


@pytest.mark.skipif(
    not sys.platform.startswith("linux") or shutil.which("setpriv") is None,
    reason="setpriv --pdeathsig gibt es nur unter Linux mit util-linux",
)
@pytest.mark.parametrize("guard", ["setpriv", "plain"])
def test_a_mount_ends_when_solidon_dies_hard(tmp_path: Path, guard: str) -> None:
    """Das Verhalten, nicht nur der Befehl: Stirbt der Prozess, der eingehängt
    hat, mit SIGKILL, endet das Einhängen binnen einer Sekunde — mit
    ``setpriv``. Ohne bleibt es stehen (die Gegenprobe im selben Test), denn es
    läuft in eigener Prozessgruppe. Braucht kein FUSE: das AppImage ist ein
    Skript, das einen Punkt nennt und schläft."""
    import signal

    pidfile = tmp_path / "pid"
    fake = tmp_path / "Fake.AppImage"
    fake.write_text(f'#!/bin/sh\necho $$ > "{pidfile}"\necho "{tmp_path}"\nexec sleep 60\n')
    fake.chmod(0o755)
    root = Path(__file__).resolve().parent.parent
    pid = 0
    # Der Block schließt das Rohr des Kindes und wartet auf es; ohne ihn blieb
    # sein Lese-Ende offen (ResourceWarning, CI-Lauf 37565457904).
    with subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(fake), guard],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        stdout=subprocess.PIPE,
    ) as holder:
        assert holder.stdout is not None
        try:
            assert holder.stdout.readline().decode().strip() == str(tmp_path)
            pid = int(pidfile.read_text(encoding="utf-8"))
            assert _alive(pid)
            holder.kill()
            holder.wait(10)
            deadline = time.monotonic() + 1.0
            while _alive(pid) and time.monotonic() < deadline:
                time.sleep(0.02)
            if guard == "setpriv":
                assert not _alive(pid), "mit setpriv endet das Einhängen mit Solidon"
            else:
                assert _alive(pid), "ohne setpriv bleibt es stehen — sonst prüfte der Test nichts"
        finally:
            holder.kill()
            if pid and _alive(pid):
                os.kill(pid, signal.SIGKILL)


def test_a_hanging_mount_keeps_its_reason(tmp_path: Path) -> None:
    """Schreibt das Einhängen einen Satz und hängt, reist der Satz mit — ``read``
    kehrte erst nach vollem Puffer zurück und verlor ihn (wie ``process._drain``)."""
    script = tmp_path / "haengt.py"
    script.write_text(
        "import sys, time\n"
        "sys.stderr.write('fusermount3: mount failed: Operation not permitted\\n')\n"
        "sys.stderr.flush()\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )

    with cura_linux._mounted([sys.executable, str(script)], None, seconds=1.0) as mount:
        assert mount.point is None
        assert "fusermount3: mount failed: Operation not permitted" in mount.reason
        assert "no answer" in mount.reason


def test_a_cleared_copy_leaves_the_memory_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein AppImage auf einem Stick: abgezogen, eine andere Cura kopiert (das räumt
    die Kopie des Sticks), Stick wieder da — dann wird neu kopiert, statt einen
    gelöschten Ordner zu nennen."""
    mounts: list[Path] = []
    copies: list[Path] = []
    stick, _point = appimage_cura(
        tmp_path / "stick", monkeypatch, mounts, name="Cura-auf-dem-Stick.AppImage", copies=copies
    )
    first = cura_linux.appimage_resources(stick)
    assert first is not None and first.is_dir()
    away = stick.with_name("weg.bin")
    stick.rename(away)
    other, _point = appimage_cura(tmp_path / "andere", monkeypatch, mounts, copies=copies)
    assert cura_linux.appimage_resources(other) is not None
    assert not first.exists(), "die Kopie des abgezogenen Sticks ist geräumt"
    away.rename(stick)

    again = cura_linux.appimage_resources(stick)

    assert again is not None and again.is_dir()
    assert copies.count(stick) == 2


def test_the_rest_of_an_aborted_copy_is_cleared_once_it_is_old(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bricht eine Kopie ab (Solidon stirbt), bleibt ein Zwischenordner ohne Marke.
    Geräumt wird er erst, wenn er älter ist als :data:`STALE_SECONDS` — ein
    junger kann gerade ein zweiter Solidon füllen. Geräumt wird nur die Form, die
    ``ImageCopies._copy`` anlegt (``mkdtemp``: 16 Hex-Zeichen, Bindestrich, acht
    Zeichen aus a–z, 0–9, _); ein fremder Ordner mit Bindestrich bleibt."""
    root = cura_linux.PRINTER_COPIES.root()
    old = root / "0123456789abcdef-a1b2_c3d"
    young = root / "fedcba9876543210-x9y8z7w6"
    others = [root / "fremd", root / "meine-sicherung", root / "0123456789abcdef-Abgebrochen"]
    for folder in (old, young, *others):
        (folder / "share").mkdir(parents=True)
    past = time.time() - image_copies.STALE_SECONDS - 60
    for folder in (old, *others):
        os.utime(folder, (past, past))
    mounts: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts)

    assert cura_linux.appimage_resources(appimage) is not None

    assert not old.exists()
    assert young.is_dir()
    assert all(folder.is_dir() for folder in others), "fremde Ordner bleiben"


def test_a_cause_is_logged_once_per_search(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Der Druckdialog fragt bei jeder Feldänderung (``_show_slicer_state``); die
    Ursache steht einmal im Protokoll, nach *Neu suchen* wieder."""
    launcher = flatpak_cura(tmp_path, monkeypatch, installation=False)

    with caplog.at_level("INFO", logger="app.core.export.cura_linux"):
        for _change in range(3):
            assert handover.console_refusal(launcher) is not None
        assert caplog.text.count("not visible") == 1
        discover.forget_cache()
        assert handover.console_refusal(launcher) is not None
    assert caplog.text.count("not visible") == 2


def test_before_its_first_copy_an_appimage_is_still_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ob eine AppImage-Cura rechnen kann, weiß erst ihre Druckerkopie; bis dahin
    ist es offen, nicht „ja“ (der Druckdialog sagt dann „Curas Drucker werden
    gelesen …“)."""
    mounts: list[Path] = []
    appimage, _point = appimage_cura(tmp_path, monkeypatch, mounts, loader=False)
    launcher = flatpak_cura(tmp_path / "flatpak", monkeypatch)

    assert cura_linux.still_unknown(appimage)
    assert not cura_linux.still_unknown(launcher)
    assert cura_linux.appimage_resources(appimage) is not None
    assert not cura_linux.still_unknown(appimage)
    assert handover.console_refusal(appimage) is not None


@pytest.mark.parametrize("way", ["point", "silent", "cancelled", "failing", "missing"])
def test_every_way_out_of_a_mount_closes_its_pipes(tmp_path: Path, way: str) -> None:
    """Jeder Ausgang des Einhängens schließt beide Rohre: mit Punkt, ohne Antwort,
    abgebrochen, gescheitert und ohne startbares Programm. Ein offenes Rohr wäre
    je Lauf ein Deskriptor beim Kunden; Python meldet es als ``ResourceWarning``,
    sobald der Prozess fortgeräumt wird — auf jeder Plattform."""
    import gc
    import warnings

    from app.core.scene.cancel import CancelSignal

    mount = tmp_path / "einhaengen.py"
    mount.write_text(MOUNT_SCRIPT, encoding="utf-8")
    failing = tmp_path / "scheitern.py"
    failing.write_text(FAILING_MOUNT, encoding="utf-8")
    command = {
        "point": [sys.executable, str(mount), str(tmp_path)],
        "silent": [sys.executable, str(mount)],
        "cancelled": [sys.executable, str(mount)],
        "failing": [sys.executable, str(failing)],
        "missing": [str(tmp_path / "gibt-es-nicht.AppImage"), "--appimage-mount"],
    }[way]
    token = CancelSignal()
    if way == "cancelled":
        token.cancel()

    # Die kurze Frist nur für das stumme Einhängen: Mit Punkt brauchte ein unter
    # Last startendes Python im Tor (-n 8) länger als eine Sekunde für seine
    # erste Zeile, und der Fall endete als „no answer“.
    seconds = 1.0 if way == "silent" else None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        with cura_linux._mounted(command, token, seconds=seconds) as found:
            assert (found.point == tmp_path) == (way == "point")
        gc.collect()

    leaks = [str(entry.message) for entry in caught if issubclass(entry.category, ResourceWarning)]
    assert not leaks
