"""Gegenproben für die Aussagen der Slicer-Matrix."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load_module(
    path: Path,
    name: str,
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
) -> ModuleType:
    import tools

    monkeypatch.setattr(sys, "argv", [str(path), *arguments])
    monkeypatch.setattr(sys, "path", list(sys.path))
    # ``matrix_unit`` bindet ``tools`` an seinen Ordner; danach kommt der
    # Suchpfad des Testprozesses zurück.
    monkeypatch.setattr(tools, "__path__", tools.__path__)
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
    script = TOOLS / "matrix_report.py"
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
    report = _load_module(TOOLS / "matrix_report.py", "delivery_matrix_fit_review", monkeypatch, [])
    entry = {
        "slicer": "superslicer",
        "printer": "prusa-mini",
        "complete": True,
        "variants": {"standard": [{"ok": False, "title": "Slicerfehler", **run}]},
    }

    assert report.state_of(entry) == ("passt nicht", [])


def test_the_slicers_own_reading_of_a_handed_chain_value_is_no_deviation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kobra 2: Solidon übergibt „50%“ wie die Kette, OrcaSlicer fährt 30.

    Mit der Kette wörtlich und mit 30 entsteht derselbe G-Code (04.10.2026);
    die Matrix meldete das als Abweichung von der Herstellerkette.
    """
    unit = _load_module(
        TOOLS / "matrix_unit.py",
        "delivery_matrix_handed_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
    )
    wanted = {"initial_layer_speed": ("process", "50%"), "outer_wall_speed": ("process", "150")}
    block = {"initial_layer_speed": "30", "outer_wall_speed": "120"}

    handed = unit.against_chain(
        block, wanted, {"initial_layer_speed": "50%", "outer_wall_speed": "120"}
    )
    assert handed["differences"] == {"outer_wall_speed": ["process", "150", "120"]}
    assert handed["console"] == {"initial_layer_speed": ["process", "50%", "30"]}
    assert set(unit.against_chain(block, wanted)["differences"]) == {
        "initial_layer_speed",
        "outer_wall_speed",
    }


@pytest.mark.parametrize("key", ["machine_start_gcode", "start_gcode"])
def test_missing_startcode_is_not_attributed_to_the_manufacturer(
    key: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein fehlender G-Code-Wert zählt nicht als Vergleich mit der Herstellerkette."""
    script = TOOLS / "matrix_unit.py"
    unit = _load_module(
        script,
        "delivery_matrix_unit_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
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
    script = TOOLS / "matrix_unit.py"
    unit = _load_module(
        script,
        "delivery_matrix_console_startcode_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
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
    script = TOOLS / "matrix_unit.py"
    unit = _load_module(
        script,
        "delivery_matrix_startcode_tail_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
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
    script = TOOLS / "matrix_unit.py"
    unit = _load_module(
        script,
        "delivery_matrix_run_without_chain_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
    )

    flags = unit.flags_for("standard", {"ok": True}, None, {})

    assert flags == ["keine Bettvermessung im Startcode", "keine Spüllinie"]


def test_full_circle_arcs_count_as_paths_and_detect_bed_overflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Vollkreis ohne Endpunktänderung bleibt als Bahn, Länge und Übertritt sichtbar."""
    script = TOOLS / "matrix_gcode.py"
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
    script = TOOLS / "matrix_unit.py"
    unit = _load_module(
        script,
        "delivery_matrix_full_circle_speed_review",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
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
    script = TOOLS / "matrix_gcode.py"
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


@pytest.mark.parametrize("bound", [True, False], ids=["gebunden", "frei"])
def test_the_matrix_keeps_its_own_siblings_when_another_root_comes_first(
    tmp_path: Path, bound: bool
) -> None:
    """Review 06.10.2026, M2: ``tools`` ist ein Namensraumpaket.

    Sein Suchpfad wird nach jeder Änderung von ``sys.path`` neu berechnet; legt
    die Matrix eine andere Code-Wurzel davor, fand ``from tools import
    matrix_gcode`` deren Fassung. ``matrix_config.own_package`` bindet ``tools``
    an den Ordner der Matrix. Gegenprobe ``frei``: ohne Bindung lädt die
    fremde Wurzel.
    """
    import subprocess

    foreign = tmp_path / "fremd" / "tools"
    foreign.mkdir(parents=True)
    (foreign / "matrix_gcode.py").write_text("FREMD = True\n", encoding="utf-8")
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from tools import matrix_config\n"
        f"if {bound!r}:\n"
        "    matrix_config.own_package()\n"
        f"sys.path.insert(0, {str(foreign.parent)!r})\n"
        "from tools import matrix_gcode\n"
        "print(matrix_gcode.__file__)\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    loaded = Path(done.stdout.strip()).resolve().parent
    assert loaded == (TOOLS.resolve() if bound else foreign.resolve())


def test_the_unit_binds_its_package_before_it_loads_a_sibling() -> None:
    """Nachprüfung 06.10.2026, F2: ``matrix_unit`` ruft ``own_package`` auf
    Modulebene, bevor es ``matrix_gcode`` lädt — ohne den Aufruf fände der
    Import nach der Code-Wurzel wieder deren Fassung."""
    import ast

    tree = ast.parse((TOOLS / "matrix_unit.py").read_text(encoding="utf-8"))
    bound = [
        statement.lineno
        for statement in tree.body
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and ast.unparse(statement.value.func) == "matrix_config.own_package"
    ]
    sibling = [
        statement.lineno
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom)
        and statement.module == "tools"
        and any(alias.name == "matrix_gcode" for alias in statement.names)
    ]
    assert bound and sibling and bound[0] < sibling[0], (bound, sibling)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("; CONFIG_BLOCK_START", "; CONFIG_BLOCK_END"),
        ("; CONFIG_BLOCK_START = begin", "; CONFIG_BLOCK_END = end"),
        ("; prusaslicer_config = begin", "; prusaslicer_config = end"),
    ],
)
def test_the_config_block_is_read_in_every_slicer_spelling(
    start: str, end: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anycubic Slicer Next schreibt „; CONFIG_BLOCK_START = begin“ (RM-525, B7).

    Der Leser kannte nur die Schreibweise der übrigen Orca-Familie und las aus
    jeder Anycubic-Druckdatei einen leeren Block — jede Kettenprüfung war blind.
    """
    gcode = TOOLS / "matrix_gcode.py"
    reader = _load_module(gcode, "delivery_matrix_gcode_block", monkeypatch, [])
    path = tmp_path / "plate.gcode"
    path.write_text(
        f"G1 X1\n{start}\n; nozzle_temperature = 210\n; layer_height = 0.2\n{end}\n; after = 1\n",
        encoding="utf-8",
    )

    assert reader.config_block(path) == {"nozzle_temperature": "210", "layer_height": "0.2"}


def _matrix_unit_for_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    return _load_module(
        TOOLS / "matrix_unit.py",
        "delivery_matrix_unit_floor",
        monkeypatch,
        [str(ROOT), str(tmp_path / "plate.stl"), str(tmp_path / "out"), "heim"],
    )


def _support_floor_at(nozzle: float) -> float:
    from app.core.knowledge import profiles
    from app.core.slice.estimate import support_floor

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    printer = dataclasses.replace(profile.printer, nozzle_diameter=nozzle)
    return support_floor(dataclasses.replace(profile, printer=printer))


@pytest.mark.parametrize(
    ("variant", "mark"),
    [("vorschlaege", "Stützvorschlag ohne Stütze"), ("stuetzen_auto", "Slicer stützt nicht")],
)
@pytest.mark.parametrize(
    ("nozzle", "metres", "volume", "flagged"),
    [
        (0.4, 0.3, 0.5, True),
        (0.4, 0.3, 4.0, False),
        (0.8, 0.3, 4.0, True),
        (0.25, 0.3, 1.0, False),
        # Die B7-Zeilen vom 05.10.2026 (``anycubic-matrix/auswertung.md``, Frage 4):
        # Kobra 3 Max 0.6 und V2 0.6 mit 0,43 m und 68,2 mm³, eine 0,8er Düse mit
        # 0,45 m und 128,3 mm³ — die alte Grenze von 0,5 m markierte sie.
        (0.6, 0.43, 68.2, False),
        (0.8, 0.45, 128.3, False),
        # Ohne Volumen schweigt das Hauptfenster, und die Matrix auch.
        (0.8, 0.0, None, False),
    ],
)
def test_supports_without_support_count_volume_not_metres(
    variant: str,
    mark: str,
    nozzle: float,
    metres: float,
    volume: float | None,
    flagged: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Beide Stützmarken messen wie das Hauptfenster (RM-525, B7).

    Dieselbe Grenze wie ``gcode.support_missing``: ein Strang im Düsenquerschnitt
    so lang wie die kürzeste gestützte Brücke (``estimate.support_floor``) —
    1,9 mm³ an einer 0,4er Düse, 7,5 mm³ an einer 0,8er, 0,7 mm³ an einer
    0,25er. Die alte Grenze von 0,5 m war düsenblind und markierte an 0,6er und
    0,8er Düsen Läufe mit 68 bis 128 mm³ Stütze.
    """
    unit = _matrix_unit_for_flags(tmp_path, monkeypatch)
    row = {
        "ok": True,
        "support_m": metres,
        "support_gcode_mm3": volume,
        "support_floor_mm3": _support_floor_at(nozzle),
    }

    flags = unit.flags_for(variant, row, None, {}, support_accepted=True)

    assert any(flag.startswith(mark) for flag in flags) is flagged


@pytest.mark.parametrize(
    ("auto_ok", "volume", "flagged"),
    [(True, 0.5, True), (True, 128.3, False), (True, None, False), (False, 0.5, False)],
)
def test_first_layer_support_against_the_slicer_uses_the_same_limit(
    auto_ok: bool,
    volume: float | None,
    flagged: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """„Gegen das Urteil des Slicers“ fragt dieselbe Grenze wie „Slicer stützt nicht“.

    Vorher genügte jede Stützbahn über null Metern als „der Slicer stützt“, und
    beide Marken einer Zeile konnten sich widersprechen. Ohne Volumen oder nach
    einem gescheiterten Lauf ``stuetzen_auto`` ist das Urteil des Slicers
    unbekannt, und dagegen wird nichts markiert.
    """
    unit = _matrix_unit_for_flags(tmp_path, monkeypatch)
    floor = _support_floor_at(0.8)
    row = {"ok": True, "first_layer_support_share": 0.4, "support_m": 1.0}
    base = {"ok": True, "first_layer_support_share": 0.0}
    auto = {
        "ok": auto_ok,
        "support_m": 0.43,
        "support_gcode_mm3": volume,
        "support_floor_mm3": floor,
    }

    flags = unit.flags_for("vorschlaege", row, base, {}, auto=auto)

    assert any("gegen das Urteil des Slicers" in flag for flag in flags) is flagged


@pytest.mark.parametrize("nozzle", [0.4, 0.8])
def test_every_plate_row_carries_the_support_limit_of_its_nozzle(
    nozzle: float, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``plate_run`` schreibt die Stützgrenze der Düse in jede Zeile (RM-525, B7).

    Ohne sie schweigen alle drei Stützmarken (``_without_support`` gibt ``None``),
    und eine feste Grenze der 0,4er Düse fiele in den Markentests nicht auf.
    Vorbereitung und Slicer sind Attrappen; gefragt wird nur die Grenze.
    """
    from types import SimpleNamespace

    from app.core.knowledge import profiles
    from app.core.slice.estimate import support_floor

    unit = _matrix_unit_for_flags(tmp_path, monkeypatch)

    def prepared(job: Any, plate: int) -> Any:
        return SimpleNamespace(
            keep_arrangement=False,
            model=tmp_path / "p.3mf",
            findings=[],
            slots=(),
            model_height=10.0,
            meshes=(),
            used_tools=(0,),
            comparison=None,
        )

    def sliced(*args: Any, **kwargs: Any) -> Any:
        metrics = SimpleNamespace(
            print_seconds=600.0, printing_seconds=540.0, support_mm3=3.0, filament_grams=2.0
        )
        return SimpleNamespace(findings=[], gcode_path=tmp_path / "p.gcode", metrics=metrics)

    monkeypatch.setattr(unit, "_prepare_plate", prepared)
    monkeypatch.setattr(unit.handover, "slice_model", sliced)
    base = profiles.make_profile("centauri-carbon-2", "pla")
    profile = dataclasses.replace(
        base, printer=dataclasses.replace(base.printer, nozzle_diameter=nozzle)
    )

    row = unit.plate_run([], 0, (0,), None, profile, SimpleNamespace(flavour="orca"), tmp_path, "p")

    assert row["support_floor_mm3"] == pytest.approx(round(support_floor(profile), 3))


def test_the_report_counts_an_unknown_support_amount_on_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ohne Volumen ist das Urteil des Slicers unbekannt, nicht „stützt“ (RM-525, B7).

    Der Bericht zählte eine Zeile ohne Volumen als „Der Slicer stützt“ und zeigte
    fehlende Werte älterer Ergebnisdateien als Grenze 0,0 mm³.
    """
    script = TOOLS / "matrix_report.py"
    report = _load_module(script, "delivery_matrix_report_unknown", monkeypatch, [])
    floor = 1.885

    def combo(printer: str, run: dict[str, Any]) -> dict[str, Any]:
        return {
            "slicer": "anycubic",
            "printer": printer,
            "complete": True,
            "variants": {
                "standard": [{"ok": True, "flags": []}],
                "stuetzen_auto": [{"ok": True, **run}],
            },
        }

    combos = [
        combo("stuetzt", {"support_m": 2.0, "support_gcode_mm3": 50.0, "support_floor_mm3": floor}),
        combo(
            "stuetzt-nicht",
            {
                "support_m": 0.01,
                "support_gcode_mm3": 0.5,
                "support_floor_mm3": floor,
                "flags": ["Slicer stützt nicht (0.50 mm³ unter 1.89 mm³; 0.01 m)"],
            },
        ),
        combo("unbekannt", {"support_m": 0.0, "support_gcode_mm3": None}),
        # Eine ältere Datei: Volumen und Marke gespeichert, die Grenze fehlt.
        combo(
            "alt",
            {
                "support_m": 0.4,
                "support_gcode_mm3": 68.2,
                "flags": ["Slicer stützt nicht (0.40 m)"],
            },
        ),
    ]
    folder = tmp_path / "results"
    folder.mkdir()
    (folder / "result.json").write_text(
        json.dumps({"model": "plate.stl", "done": True, "combos": combos}), encoding="utf-8"
    )
    monkeypatch.setattr(sys, "argv", [str(script), str(folder)])

    assert report.main() == 0

    output = capsys.readouterr().out
    assert "verlangt: 1; er stützt nicht: 2; Stützmenge unbekannt: 1." in output
    assert "| plate.stl | anycubic/alt | 68.20 | — | 0.40 |" in output
    assert "| plate.stl | anycubic/stuetzt-nicht | 0.50 | 1.89 | 0.01 |" in output
    assert report._mm3(None) == "—"


def test_support_ways_counts_the_bridges_the_need_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Tabelle „Stützbedarf gegen das Urteil des Slicers“ liest ``support_ways``.
    Nach RM-627 las es ``need.quiet_layers``, das es nicht mehr gab: Jede
    Kombination verlor „vorschlaege“ und „stuetzen_auto“ an einen ``AttributeError``.
    Gezählt wird wie im Stützbedarf, je Schicht ohne Ränder (``span_beside``)."""
    from app.core.slice.analysis import slice_body
    from tests.helpers import brick, on_bed

    unit = _matrix_unit_for_flags(tmp_path, monkeypatch)
    wall = brick(40.0, 10.0, 40.0, (0.0, 0.0, 20.0))
    shelf = brick(40.0, 2.5, 1.0, (0.0, 6.25, 20.5))
    spur = [brick(4.0, 4.0, 21.0, (30.0, -15.0, 10.5)), brick(6.0, 1.5, 1.0, (35.0, -15.0, 20.5))]
    bridge = [
        brick(3.0, 3.0, 20.0, (-35.0, -11.5, 10.0)),
        brick(3.0, 3.0, 20.0, (-35.0, 11.5, 10.0)),
        brick(3.0, 26.0, 1.0, (-35.0, 0.0, 20.5)),
    ]
    results = {
        "sporn": (45.0, 1.0, slice_body(on_bed(wall, shelf, *spur), 0.2)),
        "steg": (45.0, 1.0, slice_body(on_bed(wall, shelf, *bridge), 0.2)),
    }

    ways = unit.support_ways(results)

    assert not ways["sporn"]["needed"]
    assert ways["sporn"]["bridges_over"] == 0, "die Konsole spannt nicht"
    assert ways["steg"]["needed"]
    assert ways["steg"]["bridges_over"] == 1
    assert ways["steg"]["bridge_max"] == pytest.approx(20.0, abs=1.0), "der Steg, nicht die Konsole"
