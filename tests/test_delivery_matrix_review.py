"""Gegenproben für die Aussagen der Slicer-Matrix."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / ".claude" / ".state" / "uebergabe-matrix-2026-09-27"
DELIVERY = ROOT / ".claude" / ".state" / "uebergabe-gesamt-2026-09-27"


def _load_module(
    path: Path,
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    search_paths: tuple[Path, ...] = (),
) -> ModuleType:
    monkeypatch.setattr(sys, "argv", [str(path), *arguments])
    monkeypatch.setattr(sys, "path", list(sys.path))
    for search_path in reversed(search_paths):
        sys.path.insert(0, str(search_path))
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    monkeypatch.setitem(sys.modules, name, module)
    specification.loader.exec_module(module)
    return module


def test_an_advice_failure_is_reported_even_when_the_standard_run_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ein erfolgreicher Standardlauf darf die fehlende Vorschlagsprüfung nicht verdecken."""
    script = DELIVERY / "bericht.py"
    report = _load_module(script, "delivery_matrix_report_review", monkeypatch, [])
    entry = {
        "slicer": "orca",
        "printer": "Drucker",
        "complete": True,
        "advice_error": "RuntimeError: Profilrat nicht berechenbar",
        "variants": {"standard": [{"ok": True, "flags": []}]},
    }
    folder = tmp_path / "results"
    folder.mkdir()
    (folder / "result.json").write_text(
        json.dumps({"model": "plate.stl", "done": True, "combos": [entry]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", [str(script), str(folder)])

    assert report.state_of(entry) == (
        "Befund",
        ["Vorschläge nicht geprüft: RuntimeError: Profilrat nicht berechenbar"],
    )
    failed = {
        **entry,
        "variants": {"standard": [{"ok": False, "title": "Slicerfehler"}]},
    }
    failed_state, failed_flags = report.state_of(failed)
    assert failed_state == "kein Druck"
    assert "Vorschläge nicht geprüft: RuntimeError: Profilrat nicht berechenbar" in failed_flags
    assert report.main() == 0
    output = capsys.readouterr().out
    assert "| orca | Drucker | 0 | 1 |" in output
    assert "Vorschläge nicht geprüft: RuntimeError: Profilrat nicht berechenbar" in output


@pytest.mark.parametrize(
    "run",
    [
        {"detail": "Ein Teil ist höher, als dieser Drucker drucken kann."},
        {"detail": "Bauraumfehler", "constraint": "slicer_build_volume"},
    ],
)
def test_a_part_too_tall_for_the_printer_does_not_fit_instead_of_failing(
    run: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Höhenabsage der Übergabe ist „passt nicht“, kein Fehler der Übergabe.

    Im Probelauf scheiterte der Minigolf-Satz am MINI (180 mm Bauhöhe) an
    ``_check_plate``; der Bericht zählte das als „kein Druck“.
    """
    report = _load_module(DELIVERY / "bericht.py", "delivery_matrix_fit_review", monkeypatch, [])
    entry = {
        "slicer": "superslicer",
        "printer": "prusa-mini",
        "complete": True,
        "variants": {"standard": [{"ok": False, "title": "Slicerfehler", **run}]},
    }

    assert report.state_of(entry) == ("passt nicht", [])


@pytest.mark.parametrize("key", ["machine_start_gcode", "start_gcode"])
def test_missing_startcode_is_not_attributed_to_the_manufacturer(
    key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein fehlender G-Code-Wert zählt nicht als Vergleich mit der Herstellerkette."""
    script = DELIVERY / "einheit.py"
    unit = _load_module(
        script,
        "delivery_matrix_unit_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
        (DELIVERY, MATRIX),
    )
    wanted = {key: ("machine", "G28\nG29\nG1 X10 E1")}
    missing = unit.against_chain({}, wanted)
    row = {"ok": True, "chain": missing, "start_levelling": [], "start_purge_mm": 0.0}
    flags = unit.flags_for("standard", row, None, {})

    assert missing["missing_keys"] == [key]
    assert missing["compared_keys"] == []
    assert flags == ["keine Bettvermessung im Startcode", "keine Spüllinie"]

    matched = unit.against_chain({key: wanted[key][1]}, wanted)
    matched_flags = unit.flags_for("standard", {**row, "chain": matched}, None, {})
    assert matched["compared_keys"] == [key]
    assert matched_flags == [
        "wie Hersteller: keine Bettvermessung im Startcode",
        "wie Hersteller: keine Spüllinie",
    ]


@pytest.mark.parametrize("key", ["machine_start_gcode", "start_gcode"])
def test_console_startcode_difference_is_not_attributed_to_the_manufacturer(
    key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein von der Konsole geänderter Startcode gilt nicht als Herstellervergleich."""
    script = DELIVERY / "einheit.py"
    unit = _load_module(
        script,
        "delivery_matrix_console_startcode_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
        (DELIVERY, MATRIX),
    )
    chain = unit.against_chain(
        {key: "G28\nG29"},
        {key: ("machine", "")},
    )
    row = {"ok": True, "chain": chain, "start_levelling": [], "start_purge_mm": 0.0}

    assert key in chain["console"]
    flags = unit.flags_for("standard", row, None, {})
    assert flags == ["keine Bettvermessung im Startcode", "keine Spüllinie"]


@pytest.mark.parametrize("key", ["machine_start_gcode", "start_gcode"])
@pytest.mark.parametrize(
    "found",
    ["G28; Kommentar\nM117 Geändert", r"G28; Kommentar\nM117 Geändert"],
)
def test_startcode_commands_after_inline_comment_are_compared(
    key: str, found: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein weiterer Befehl nach einem Inline-Kommentar darf nicht verschwinden."""
    script = DELIVERY / "einheit.py"
    unit = _load_module(
        script,
        "delivery_matrix_startcode_tail_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
        (DELIVERY, MATRIX),
    )
    chain = unit.against_chain({key: found}, {key: ("machine", "G28")})
    row = {"ok": True, "chain": chain, "start_levelling": [], "start_purge_mm": 0.0}

    assert chain["differences"] == {key: ["machine", "G28", found[:120]]}
    assert unit.flags_for("standard", row, None, {}) == [
        "keine Bettvermessung im Startcode",
        "keine Spüllinie",
        f"weicht von der Herstellerkette ab: {key}",
    ]


def test_successful_run_without_a_chain_still_reports_startcode_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cura/Prusa dürfen ohne Ketteneintrag trotzdem einen Bericht erzeugen."""
    script = DELIVERY / "einheit.py"
    unit = _load_module(
        script,
        "delivery_matrix_run_without_chain_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
        (DELIVERY, MATRIX),
    )

    flags = unit.flags_for("standard", {"ok": True}, None, {})

    assert flags == ["keine Bettvermessung im Startcode", "keine Spüllinie"]


def test_full_circle_arcs_count_as_paths_and_detect_bed_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Vollkreis ohne Endpunktänderung bleibt als Bahn, Länge und Übertritt sichtbar."""
    script = MATRIX / "gcode_lesen.py"
    parser = _load_module(script, "delivery_matrix_gcode_review", monkeypatch, [])
    path = tmp_path / "circle.gcode"
    path.write_text(
        "G90\nM83\n;TYPE:Outer wall\n;LAYER:0\nG0 X10 Y0 Z0.2\nG2 X10 Y0 I-10 J0 E1\n",
        encoding="utf-8",
    )

    reading = parser.read(path, bed=(20.0, 20.0))
    drawn = parser.first_layer_segments(path)["model"]
    drawn_length = sum(math.hypot(x1 - x0, y1 - y0) for x0, y0, x1, y1 in drawn)

    assert reading.layer_count == 1
    assert reading.total["Outer wall"] == pytest.approx(20.0 * math.pi)
    assert reading.layers_first[0].runs["Outer wall"] == 1
    assert reading.off_bed["Outer wall"] == 1
    assert len(drawn) >= 70
    assert drawn_length == pytest.approx(20.0 * math.pi, rel=0.001)


def test_first_layer_speed_uses_full_arc_length_for_weighting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Vollkreis ohne XY-Endpunktänderung zählt mit seiner wirklichen Bahnlänge."""
    script = DELIVERY / "einheit.py"
    unit = _load_module(
        script,
        "delivery_matrix_full_circle_speed_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
        (DELIVERY, MATRIX),
    )
    path = tmp_path / "full-circle-speed.gcode"
    path.write_text(
        "G90\nM83\n;TYPE:Outer wall\n;LAYER:0\nG0 X30 Y20 Z0.2\nG2 X30 Y20 I-10 J0 E1 F6000\n",
        encoding="utf-8",
    )

    speeds = unit.first_layer_speeds(path)

    assert speeds == {"Outer wall": {"mm": 63, "median": 100.0, "max": 100.0}}


def test_counterclockwise_quarter_arc_uses_its_absolute_centre(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G90.1 steuert die Bogenmitte, ohne die XY-Bewegung auf eine Sehne zu reduzieren."""
    script = MATRIX / "gcode_lesen.py"
    parser = _load_module(script, "delivery_matrix_gcode_absolute_arc_review", monkeypatch, [])
    path = tmp_path / "quarter-circle.gcode"
    path.write_text(
        "G90\nG90.1\nM83\n;TYPE:Outer wall\n;LAYER:0\nG0 X10 Y0 Z0.2\nG3 X0 Y10 I0 J0 E1\n",
        encoding="utf-8",
    )

    reading = parser.read(path, bed=(20.0, 20.0))
    segments = parser.first_layer_segments(path)["model"]

    assert reading.total["Outer wall"] == pytest.approx(5.0 * math.pi)
    assert reading.off_bed == {}
    assert len(segments) == 18
