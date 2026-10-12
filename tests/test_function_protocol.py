"""Messprotokoll und Aufnahmen eines Funktionsfalls, ohne Fenster (D0-P, RM-737).

Szenenabdruck und Kennzahlen (``function_protocol``), die Rechnung hinter den
Aufnahmen (``function_capture``: Herzschlag, Bildzähler, erlaubte Fenster),
dass ein geschriebenes Protokoll gegen das Schema von D0-U gültig ist, jeder
Prüfpunkt ein Feld bekommt, Ziehzeiten roh bleiben und der Referenzfaktor
einmal je Lauf aus der Kalibrierung von Bauplan §31 kommt.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.bench_fakes import (
    ROWS,
)
from tools import function_capture as capture
from tools import (
    function_guard,
    function_protocol,
    function_setup,
    function_walk,
)
from tools.file_acceptance import (
    ROOT,
)
from tools.function_checks import (
    CHECKPOINTS,
    COVERED,
    PROTOCOL_FIELDS,
    PROTOCOL_SCHEMA,
    SELECTION_STAGES,
    SMALLEST_WINDOW,
    validate_protocol,
)


def _box_project(profile: Any) -> tuple[Any, Any, Callable[[], Any]]:
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 10.0, "height": 5.0})],
    )

    def evaluated() -> Any:
        return evaluate(project.document, profile, sources=ProjectSources(project))

    return project, history, evaluated


def test_the_scene_print_tells_a_change_from_a_return(profile: Any) -> None:
    """Rückgängig kehrt zum Abdruck von vorher zurück; Auswahl und Kamera stehen daneben.

    Ein Quader, dann ein zweiter Schritt, dann zurück: Dokumentteil und Körper
    sind wieder die von vorher. Eine andere Auswahl allein ist ein Vermerk,
    kein Unterschied (Prüfpunkt 5). ``ops`` nennt die Operationen — daran liest
    U, ob der Verlauf gewachsen ist.
    """
    from app.core.scene import OperationDraft

    project, history, evaluated = _box_project(profile)
    camera = [(0, 0, 9), (0, 0, 0), (0, 1, 0), None]

    def printed(selection: tuple[str, ...] = ()) -> dict[str, Any]:
        return function_protocol.scene_print(
            project.document, evaluated().scene, selection=selection, camera=camera
        )

    before = printed()
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 5.0})],
    )
    applied = printed()
    history.undo()
    undone = printed(selection=("obj_1",))
    assert before["ops"] == ["create_box"] and applied["ops"] == ["create_box", "translate_object"]
    changed = function_protocol.compare_prints(before, applied)
    assert changed["same"] is False and {"ops", "params", "bodies"} <= set(changed["differs"])
    returned = function_protocol.compare_prints(before, undone)
    assert returned == {"same": True, "differs": [], "selection_same": False, "camera_same": True}
    assert function_protocol.compare_prints(before, None)["same"] is None
    assert set(function_protocol.DOCUMENT_PARTS) <= set(before)


def test_the_result_metrics_carry_the_names_the_row_specs_expect(profile: Any) -> None:
    """``volume``, ``extent``, ``bounds.*`` und ``<art>.<wert>`` — so heißen die Erwartungen (L).

    Der Quader 20 × 10 × 5 aus ``create_box``: Volumen und Maß aus der
    Konstruktion, das Bett liegt bei z = 0 (``create_box`` setzt auf).
    """
    project, _history, evaluated = _box_project(profile)
    metrics = function_protocol.result_metrics(evaluated().scene, project.document, None)
    assert metrics["volume"] == pytest.approx(20.0 * 10.0 * 5.0, abs=1e-3)
    assert metrics["extent"] == pytest.approx([20.0, 10.0, 5.0], abs=1e-3)
    assert metrics["bounds.z_max"] - metrics["bounds.z_min"] == pytest.approx(5.0, abs=1e-3)
    assert any("." in key and not key.startswith(("bounds.", "parameter.")) for key in metrics)
    assert "bodies_without_mesh" not in metrics
    # Review L15: Ein Körper ohne Netz fällt nicht still heraus.
    from types import SimpleNamespace

    scene = evaluated().scene
    body = SimpleNamespace(mesh=object(), features={})
    shape = SimpleNamespace(objects={**scene.objects, "obj_x": body})
    metrics = function_protocol.result_metrics(shape, project.document, None)
    assert metrics["bodies_without_mesh"] == ["obj_x"]
    assert metrics["volume"] == pytest.approx(20.0 * 10.0 * 5.0, abs=1e-3)


def test_the_heartbeat_names_the_largest_gap_inside_its_window() -> None:
    """Schläge alle 10 ms, dann 150 ms Stille: Die Lücke ist 150 ms (Prüfpunkt 6, Gegenprobe)."""
    heartbeat = capture.Heartbeat()
    heartbeat.beat(0.0)
    assert heartbeat.largest_ms == 0.0, "vor dem Messfenster zählt nichts"
    heartbeat.open(1.0)
    for moment in (1.01, 1.02, 1.03, 1.18, 1.19):
        heartbeat.beat(moment)
    assert heartbeat.close(1.20) == pytest.approx(150.0, abs=0.5)
    heartbeat.beat(9.0)
    assert heartbeat.largest_ms == pytest.approx(150.0, abs=0.5), "nach dem Schließen zählt nichts"


def test_the_frame_counter_measures_from_each_event_to_the_next_picture() -> None:
    clock = {"now": 0.0}

    class Renderer:
        def render(self) -> str:
            return "bild"

    renderer = Renderer()
    counter = capture.FrameCounter(clock=lambda: clock["now"])
    assert counter.wrap(renderer) is True
    assert counter.wrap(None) is False
    for moment in (0.010, 0.050, 0.090):
        clock["now"] = moment
        assert renderer.render() == "bild"
    assert counter.latencies([0.0, 0.040, 0.100]) == [10.0, 10.0, None]


def test_the_captures_judge_nothing_that_d0_u_judges() -> None:
    """Keine Zwillinge der Urteile (Review M9): Rücksprünge, Überlauf, Doppelnamen, gleiche Bilder.

    Die Aufnahme liefert Rohdaten; U rechnet daraus (``function_judges``). Die
    rohen Fensterklassen kommen aus U's ``RAW_BASES``, nicht abgeschrieben.
    """
    from tools.function_checks import RAW_BASES

    for twin in ("chain_breaks", "overflowing", "duplicate_names", "alike_states", "RAW_BASES"):
        assert not hasattr(capture, twin), twin
    assert capture._raw_bases() == tuple(RAW_BASES)


def test_a_window_is_allowed_by_its_class_or_the_function_that_opened_it() -> None:
    """Z2 und E6: erlaubt sind die Ausnahmen von Regel 19 — erkannt an Klasse oder Aufrufer.

    Ein ``QMessageBox`` aus ``confirm_unsaved`` ist die Speicherfrage, derselbe
    aus einer Meldung nach dem Übernehmen ist es nicht. Ein Wächter hält, dass
    jede genannte Funktion in ``app/ui`` steht — sonst erkennte die Wache nach
    einer Umbenennung nichts mehr.
    """
    # Konzept Z2 wie ``fenster.md`` (welle4 ``89e7f5819``): Eine Rückfrage über
    # ``ctx.ask`` ist nur vor der Vollerkennung ausgenommen, erkannt an der Antwort.
    assert not capture.modal_allowed(["AskDialog", "QDialog"], [])
    assert not capture.modal_allowed(["AskDialog", "QDialog"], [], ["Oben", "Unten"])
    assert capture.modal_allowed(
        ["AskDialog", "QDialog"], [], ["Sofort laden", capture.FULL_RECOGNITION_ANSWER]
    )
    assert capture.modal_allowed(["QMessageBox", "QDialog"], ["poll", "confirm_unsaved", "x"])
    assert capture.modal_allowed(["QMessageBox", "QDialog"], ["poll", "_ask_recovery"])
    assert capture.modal_allowed(["QMessageBox", "QDialog"], ["poll", "confirm_generation_loss"])
    assert not capture.modal_allowed(["QMessageBox", "QDialog"], ["poll", "show_error"])
    assert capture.is_question("QMessageBox", ["Speichern", "Verwerfen", "Abbrechen"])
    assert not capture.is_question("QMessageBox", ["OK"])
    assert capture.is_question("AskDialog", ["OK"])
    # Die Meldung im Hausstil ist nie eine Frage, auch mit Handlung und Ausgang (FD-21).
    assert not capture.is_question("MessageDialog", ["Rückgängig", "Schließen"])
    sources = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "app").rglob("*.py"))
    assert f'"{capture.FULL_RECOGNITION_ANSWER}"' in sources
    defined = {
        node.name
        for path in (ROOT / "app" / "ui").rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    assert len(defined) > 1000
    assert defined >= capture.ALLOWED_CALLERS
    assert defined >= capture.ALLOWED_CLASSES - {"QFileDialog"}


def _written_keys() -> set[str]:
    """Die Felder, die die Fälle ins Protokoll schreiben — gelesen am Quelltext jedes Moduls."""
    keys: set[str] = set()
    nodes = [
        node
        for module in function_guard.BENCH_MODULES
        for node in ast.walk(
            ast.parse((ROOT / "tools" / f"{module}.py").read_text(encoding="utf-8"))
        )
    ]
    for node in nodes:
        if (
            isinstance(node, ast.Subscript)
            and ast.unparse(node.value) == "self.data"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            keys.add(node.slice.value)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "unmeasured"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
        ):
            keys.add(str(node.args[1].value).split(".")[0])
    return keys


def test_every_checkpoint_gets_a_field_the_bench_writes_and_only_schema_fields() -> None:
    """Je Prüfpunkt 1 bis 19 schreibt der Prüfstand mindestens ein Feld (Abnahme D0-P).

    Die Felder je Prüfpunkt gehören U (``function_checks.CHECKPOINTS``); der
    Prüfstand schreibt nur Felder des Schemas, sonst wiese U das Protokoll ab.
    Dazu die Pflichtfelder aus :func:`function_protocol.empty_protocol`.
    """
    written = _written_keys() | {"row", "kind", "package", "spec", "variant", "version"}
    assert len(written) > 30, written
    assert written <= PROTOCOL_FIELDS, sorted(written - PROTOCOL_FIELDS)
    assert sorted(CHECKPOINTS) == list(range(1, 20))
    for number, point in CHECKPOINTS.items():
        assert set(point.fields) & written, (number, point.fields)


def test_an_assembled_protocol_is_valid_against_the_schema_of_u() -> None:
    """Ein Protokoll aus dem Gerüst und den Formen, die der Prüfstand schreibt, ist gültig.

    Gegenprobe: ein Feld außerhalb des Schemas und ein Schritt ohne Phase werden
    abgewiesen — die Prüfung von U greift also an dem, was hier entsteht.
    """
    variant = function_setup.Variant().protocol({"screen": "MSI"}, SMALLEST_WINDOW)
    protocol = function_protocol.empty_protocol(ROWS[0], variant, {"commit": "abc", "app": "0.6.1"})
    assert set(protocol) == set(PROTOCOL_SCHEMA)
    assert set(protocol["row"]) <= set(PROTOCOL_SCHEMA["row"].keys or ())
    # Z6 je Zeile über alle Fälle (D0-U): jeder Fall trägt seine Fenstergröße
    # und eine Liste der Rollleisten, auch leer — gültig schon im Gerüst.
    assert protocol["variant"]["window_size"] == list(SMALLEST_WINDOW)
    assert protocol["scrollbars"] == []
    assert validate_protocol(protocol) == []
    print_ = {
        "ops": ["create_box"],
        "params": ["x"],
        "project_params": "p",
        "fits": "f",
        "bodies": {"obj_1": "aaaa"},
        "selection": [],
        "camera": {},
    }
    protocol.update(
        {
            "scene": {
                "key": "merkmal.hole.exakt",
                "triangles": 120,
                "build_s": None,
                "eval_s": 0.4,
            },
            "steps": [
                {
                    "target": "tree.row:obj_1.hole_1",
                    "why": "ziel",
                    "button": "left",
                    "rect": [0, 0, 10, 10],
                    "point": [5, 5],
                    "widget_at": {"class": "QWidget", "text": "Bohrung 1"},
                    "hit": True,
                    "zone": "karte_links",
                    "decision": False,
                    "phase": "weg",
                    "t": 0.1,
                },
                {
                    "target": "feature.field:resize_hole.diameter",
                    "typed": "8",
                    "button": None,
                    "decision": False,
                    "phase": "weg",
                    "t": 0.2,
                },
                {"target": "undo", "key": "Ctrl+Z", "button": None, "phase": "undo", "t": 0.3},
            ],
            "states": dict.fromkeys(("before", "preview", "applied", "undo", "redo"), print_),
            "place": function_walk.place_of([], "x") | {"error": "kein Weg"},
            "matrix": {
                stage: {"state": "nicht herstellbar", "reason": "x", "effective": None}
                for stage in SELECTION_STAGES
            },
            "licence_runs": {"licensed": {"writes": True, "enabled": True, "reason": ""}},
            "findings": [{"phase": "weg", "kind": COVERED, "target": "x", "detail": "y"}],
            "closed_by_escape": [{"phase": "weg", "times": 1}],
            "revise": [
                {
                    "way": "doppelklick",
                    "opened": True,
                    "fields": {},
                    "params": {},
                    "history_before": 2,
                    "history_after": 2,
                }
            ],
            "abort": {"eval_s": 2.4, "cancel_shown_s": 2.0, "clicked": True},
            "switch": {"phases": ["vorschau"], "late_events": []},
        }
    )
    assert validate_protocol(protocol) == []
    broken = {**protocol, "stage_b": {}}
    assert any("stage_b" in problem for problem in validate_protocol(broken))
    no_phase = {**protocol, "steps": [{"target": "x", "why": "ziel"}]}
    assert any("phase" in problem for problem in validate_protocol(no_phase))


def test_drag_times_stay_raw_and_d0_u_converts_them_once() -> None:
    """Review M3: P schreibt roh, U rechnet einmal um — P's Ausgabe durch U's Urteil.

    Vorher schrieb der Prüfstand ``Messwert × Faktor`` **und** den Faktor; U
    rechnete noch einmal, der Faktor wirkte quadratisch (40 ms hier wären 80 ms).
    """
    from tools.function_judges import _z1
    from tools.function_samples import sample_context, sample_protocol

    protocol = sample_protocol()
    protocol["frames"] = function_protocol.drag_frames([10.0, None, 20.0, None], 2.0)
    assert protocol["frames"] == {"raw_drag_ms": [10.0, None, 20.0, None], "reference_factor": 2.0}
    assert validate_protocol(protocol) == []
    outcome = _z1(protocol, sample_context())
    assert outcome is not None and outcome.measurement["worst_ms"] == pytest.approx(40.0)


def test_the_reference_factor_is_measured_once_per_run_with_the_calibration_of_section_31(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Faktor ist „18 ms durch die Probe des Laufs“ (``recognition_time``), einmal je Lauf.

    Jeder Fall liest den Faktor seines Laufs, statt neu zu messen; ohne Datei
    (ein Fall ohne ``run``) misst er selbst und legt sie ab.
    """
    from app.core.perceive import recognition_time

    probes = iter([0.036])
    monkeypatch.setattr(recognition_time, "calibrate", lambda: next(probes))
    factor = capture.measure_reference(tmp_path)
    assert factor == pytest.approx(recognition_time.PROBE_REFERENCE_SECONDS / 0.036)
    assert capture.run_reference_factor(tmp_path) == factor, "gelesen, nicht neu gemessen"
    elsewhere = tmp_path / "anderer"
    monkeypatch.setattr(recognition_time, "calibrate", lambda: 0.009)
    assert capture.run_reference_factor(elsewhere) == pytest.approx(2.0)
    assert (elsewhere / capture.REFERENCE_FILE).is_file()


def test_the_command_line_names_the_file_before_the_bodies() -> None:
    """Probelauf, Befund B: ``run place_on_bed --on obj_1 <datei>`` lehnte die Kommandozeile ab.

    ``--on`` nimmt beliebig viele Namen; die Datei am Ende wurde ein weiterer
    Körper, und ``path`` fehlte. Gelesen mit dem Parser der Anwendung selbst.
    """
    from app.cli.main import build_parser
    from app.core.bootstrap import load_operations

    load_operations()
    arguments = function_protocol.cli_arguments(
        {"op": "place_on_bed", "in": ["obj_1"], "params": {}}
    )
    assert arguments is not None
    parsed = build_parser().parse_args(function_protocol.cli_command(arguments, "x.p3d"))
    assert (parsed.op, parsed.path, parsed.on) == ("place_on_bed", "x.p3d", ["obj_1"])
    with pytest.raises(SystemExit):
        build_parser().parse_args(["run", *arguments, "x.p3d"])  # die alte Reihenfolge


def test_the_aborted_computation_lasts_as_long_as_the_main_way() -> None:
    """Review M4: ``abort.eval_s`` ist die Rechendauer aus dem Hauptweg, nicht die Ladezeit."""
    data = function_protocol.empty_protocol(
        ROWS[0], function_setup.Variant().protocol(None, (0, 0)), {}
    )
    data["scene"] = {"key": "langsam_2s", "triangles": 1, "build_s": None, "eval_s": 0.4}
    data["timing"] = {"total_s": 3.2}
    assert function_protocol.abort_entry(data, 0.9, True) == {
        "eval_s": 3.2,
        "cancel_shown_s": 0.9,
        "clicked": True,
    }
    data["timing"] = None
    assert function_protocol.abort_entry(data, None, False)["eval_s"] is None
    assert "abort.eval_s" in data["unmeasured"]
