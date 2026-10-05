"""Eine Solidon-Platte liefert genau eine vollständige Druckdatei (RM-312)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from app.core.errors import ExternalToolError
from app.core.export import handover
from app.core.knowledge import print_settings, profiles

# Zwei kurze echte Bahnen genügen hier; Geometrie und Messwerte werden nicht
# vorgetäuscht. Geprüft wird die Auswahl vor dem Rücklesen. Die vollständige
# native Gegenprobe liegt unter B-slicer-rest/rm312/replay-output-before.json:
# Bambu 2.6.0, sieben chufang-Objekte, zwei Platten mit vier und drei Objekten.
PRINT = "G90\nM83\nG0 X10 Y10 Z0.2\nG1 X20 Y10 E1 F1200\nG1 X20 Y20 E1\n"


def _run_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attempts: list[dict[str, str]],
    *,
    program: str = "BambuStudio.exe",
    keep_arrangement: bool = False,
) -> tuple[handover.SliceOutcome, list[list[str]]]:
    """Ersetzt allein den Fremdprozess; der vollständige Rückgabeweg bleibt echt."""
    executable = tmp_path / program
    executable.touch()
    model = Path(__file__).parent / "data/meshes/cube_clean.stl"
    calls: list[list[str]] = []

    def run(command: list[str], *_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        target = Path(command[command.index("--outputdir") + 1])
        files = attempts[len(calls)]
        calls.append(command)
        for name, contents in files.items():
            (target / name).write_text(contents, encoding="utf-8")
        refused = len(calls) < len(attempts)
        return subprocess.CompletedProcess(command, -101 if refused else 0, b"", b"")

    monkeypatch.setattr(handover, "_run_slicer", run)
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable, "orca")
    outcome = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        setup,
        output_dir=tmp_path / "output",
        keep_arrangement=keep_arrangement,
    )
    return outcome, calls


@pytest.mark.parametrize(
    "program", ("BambuStudio.exe", "OrcaSlicer.exe", "ElegooSlicer.exe", "AnycubicSlicerNext.exe")
)
@pytest.mark.parametrize("with_result", (False, True))
def test_multiple_native_print_files_never_become_one_complete_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, program: str, with_result: bool
) -> None:
    """Auch gleiche Inhalte beweisen keine vollständige einzelne Platte."""
    output = tmp_path / "output"
    output.mkdir()
    existing = output / "plate_2.gcode"
    existing.write_bytes(b"previous print")
    files = {"plate_1.gcode": PRINT, "plate_2.gcode": PRINT}
    if with_result:
        files["result.json"] = json.dumps(
            {
                "return_code": 0,
                "sliced_plates": [{"objects": [5, 9, 13, 17]}, {"objects": [21, 25, 29]}],
            }
        )
    with pytest.raises(ExternalToolError) as caught:
        _run_output(tmp_path, monkeypatch, [files], program=program)
    assert "mehrere Druckdateien" in str(caught.value.detail)
    assert {action.id for action in caught.value.suggestions} >= {"arrange_on_bed", "export_only"}
    assert existing.read_bytes() == b"previous print"
    assert list(output.iterdir()) == [existing]


def test_native_plate_report_prevents_returning_only_the_surviving_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei gemeldete Platten sind auch bei nur einer auffindbaren Datei unvollständig."""
    files = {
        "plate_2.gcode": PRINT,
        "result.json": json.dumps({"return_code": 0, "sliced_plates": [{}, {}]}),
    }
    with pytest.raises(ExternalToolError, match="mehrere Druckdateien"):
        _run_output(tmp_path, monkeypatch, [files])
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("suffix", (".gcode", ".GCODE", ".gco", ".g", ".nc"))
def test_single_native_print_file_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    files = {
        f"plate_1{suffix}": PRINT,
        "empty.gcode": "",
        "plate_2.gcode.tmp": PRINT,
        "result.json": json.dumps({"return_code": 0, "sliced_plates": [{}]}),
    }
    outcome, calls = _run_output(tmp_path, monkeypatch, [files])
    assert len(calls) == 1
    assert outcome.gcode_path.read_text(encoding="utf-8") == PRINT


@pytest.mark.parametrize("files", ({}, {"empty.gcode": ""}))
def test_no_nonempty_output_is_no_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: dict[str, str]
) -> None:
    with pytest.raises(ExternalToolError, match="keine Druckdatei"):
        _run_output(tmp_path, monkeypatch, [files])


def test_expected_name_does_not_hide_a_second_new_print_file(tmp_path: Path) -> None:
    (tmp_path / handover.OUTPUT_NAME).write_text(PRINT, encoding="utf-8")
    (tmp_path / "plate_2.gcode").write_text(PRINT, encoding="utf-8")
    with pytest.raises(ExternalToolError, match="mehrere Druckdateien"):
        handover._find_gcode(tmp_path, handover.OUTPUT_NAME)


@pytest.mark.parametrize("second", ({"plate_2.gcode": PRINT}, {}))
def test_retry_does_not_reuse_files_or_plate_report_from_the_failed_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, second: dict[str, str]
) -> None:
    """Eine gescheiterte native Platte darf keinen späteren Erfolg vortäuschen."""
    first = {
        "plate_1.gcode": PRINT,
        "result.json": json.dumps({"return_code": -101, "sliced_plates": [{}, {}]}),
    }
    if not second:
        with pytest.raises(ExternalToolError, match="keine Druckdatei"):
            _run_output(tmp_path, monkeypatch, [first, second], keep_arrangement=True)
        return
    outcome, calls = _run_output(tmp_path, monkeypatch, [first, second], keep_arrangement=True)
    assert len(calls) == 2
    assert outcome.gcode_path.name == "plate_2.gcode"
    assert outcome.gcode_path.read_text(encoding="utf-8") == PRINT


def test_retry_with_two_new_files_is_also_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ExternalToolError, match="mehrere Druckdateien"):
        _run_output(
            tmp_path,
            monkeypatch,
            [{}, {"plate_1.gcode": PRINT, "plate_2.gcode": PRINT}],
            keep_arrangement=True,
        )
