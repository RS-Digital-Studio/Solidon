"""Jede Sprachfläche beginnt im Ausgangszustand eines frischen Starts (FD-132, RM-737).

Der Sprachdurchgang wechselte die Startszene, stellte aber Klappzustand und
Rolllage der Karten nicht zurück: Die vorige Fläche hatte *Filament und Druck*
aufgeklappt oder die Karte ans Ende gerollt, und Z3 maß an ``paint_slot`` und
``filament.section`` 0 Wegklicks (Lauf 031). Jetzt steht vor jeder Fläche der
Prüfbericht vorn, und was sonst vom Ausgangszustand abweicht, beendet den
Prozess vor dieser Fläche; ``file_acceptance.run`` startet den Fall neu.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tools import file_acceptance, function_cases, function_language
from tools.function_setup import Variant


def _language_flow(tmp_path: Path, monkeypatch: Any, states: list[Any]) -> tuple[Any, list[str]]:
    """Ein Sprachfall mit drei Zeilen; ``states`` ist der Ausgangszustand vor jeder Fläche."""
    measured: list[str] = []
    queue = list(states)

    class Flow:
        def __init__(self, application, window, folder, data, persist, row, *args, **kwargs):
            self.row = row

        def reset(self) -> bool:
            return True

        def phase_surface(self) -> None:
            measured.append(str(self.row["id"]))

    monkeypatch.setattr(function_language, "FunctionFlow", Flow)
    monkeypatch.setattr(function_language, "place_window", lambda *args: {})
    monkeypatch.setattr(function_language, "without_way", lambda row: "")
    monkeypatch.setattr(function_language, "ground_state", lambda window: queue.pop(0))
    monkeypatch.setattr(function_language.LanguageFlow, "close_surfaces", lambda self, flow: True)
    window = SimpleNamespace(
        width=lambda: 800,
        height=lambda: 600,
        right=SimpleNamespace(isVisible=lambda: False),
        report=object(),
    )
    rows = [
        {"id": name, "target": "operation:test", "kind": "operation", "package": "D4"}
        for name in ("erste", "zweite", "dritte")
    ]
    flow = function_language.LanguageFlow(
        None,
        window,
        tmp_path,
        {},
        lambda: None,
        rows,
        Variant.of({"set": "sprachen"}),
        tmp_path,
        {},
    )
    return flow, measured


def test_a_surface_after_a_changed_ground_waits_for_a_fresh_process(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Die zweite Fläche fände einen aufgeklappten Abschnitt vor: nichts gemessen, Neustart."""
    flow, measured = _language_flow(tmp_path, monkeypatch, ["frisch", "aufgeklappt"])
    assert flow.run() is False
    assert measured == ["erste"]
    assert flow.bench["restart_before"] == "zweite"
    assert not (tmp_path / "surfaces" / "zweite.json").exists()
    # Der neue Prozess beginnt mit der zweiten Fläche — sein Ausgangszustand ist frisch.
    again, measured_again = _language_flow(tmp_path, monkeypatch, ["frisch", "frisch"])
    assert again.run() is True
    assert measured_again == ["zweite", "dritte"]


def test_an_unchanged_ground_keeps_the_process(tmp_path: Path, monkeypatch: Any) -> None:
    """Gegenprobe: Bleibt der Ausgangszustand, laufen alle Flächen in einem Prozess."""
    flow, measured = _language_flow(tmp_path, monkeypatch, ["frisch"] * 3)
    assert flow.run() is True
    assert measured == ["erste", "zweite", "dritte"]


@pytest.mark.parametrize("codes", [[75, 75, 0], [0]])
def test_run_starts_a_language_case_again_while_it_asks_for_it(
    tmp_path: Path, monkeypatch: Any, codes: list[int]
) -> None:
    """``run`` startet einen Sprachfall neu, solange er es verlangt — höchstens einmal je Zeile."""
    import subprocess

    from tools import function_capture

    out = tmp_path / "abnahme"
    out.mkdir()
    rows = [{"id": f"z{number}", "package": "D4", "target": "operation:x"} for number in range(3)]
    file_acceptance.write_json(out / "rows.json", rows)
    case = file_acceptance.Case(
        1, "D4 [de]", "", "", kind="language", row="D4", variant=Variant.of({}).as_dict()
    )
    from dataclasses import asdict

    file_acceptance.write_json(out / "cases.json", [asdict(case)])
    started: list[list[str]] = []
    pending = list(codes)

    class Process:
        pid = 1

        def __init__(self, command: list[str], **kwargs: Any) -> None:
            started.append(command)

        def wait(self, timeout: float | None = None) -> int:
            return pending.pop(0)

    monkeypatch.setattr(subprocess, "Popen", Process)
    monkeypatch.setattr(function_capture, "measure_reference", lambda out: 1.0)
    monkeypatch.setattr(file_acceptance, "summary", lambda out, cases: None)
    assert function_cases.RESTART_EXIT == 75
    assert file_acceptance.run(out, 1, 1, False, 60.0) == 0
    assert len(started) == len(codes)
    status = json.loads((out / "cases" / "001" / "process.json").read_text(encoding="utf-8"))
    assert status["exit_code"] == 0


def test_run_gives_up_when_a_case_never_gets_on(tmp_path: Path, monkeypatch: Any) -> None:
    """Gegenprobe: mehr Neustarts als Zeilen — der Fall endet rot statt endlos."""
    import subprocess
    from dataclasses import asdict

    from tools import function_capture

    out = tmp_path / "abnahme"
    out.mkdir()
    file_acceptance.write_json(out / "rows.json", [{"id": "z", "package": "D4"}])
    case = file_acceptance.Case(
        1, "D4 [de]", "", "", kind="language", row="D4", variant=Variant.of({}).as_dict()
    )
    file_acceptance.write_json(out / "cases.json", [asdict(case)])
    started: list[int] = []

    class Process:
        pid = 1

        def __init__(self, command: list[str], **kwargs: Any) -> None:
            started.append(1)

        def wait(self, timeout: float | None = None) -> int:
            return 75

    monkeypatch.setattr(subprocess, "Popen", Process)
    monkeypatch.setattr(function_capture, "measure_reference", lambda out: 1.0)
    monkeypatch.setattr(file_acceptance, "summary", lambda out, cases: None)
    monkeypatch.setattr(file_acceptance, "crash_note", lambda folder: "")
    assert file_acceptance.run(out, 1, 1, False, 60.0) == 1
    assert len(started) == 2, "ein Neustart je Zeile, dann aufgeben"


def test_the_ground_state_sees_a_remembered_section_and_a_rolled_card(qt_app: Any) -> None:
    """Am echten Fenster: Ein gemerkter Abschnitt und eine gerollte Karte sind Abweichungen."""
    from app.core.scene.history import OperationDraft
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tools.function_checks import SMALLEST_WINDOW
    from tools.function_walk import QtPorts

    window = MainWindow(Session(), UiSettings())
    window.resize(*SMALLEST_WINDOW)
    window.show()
    window._show_start_screen(False)
    try:
        assert window.session.apply("Quader", [OperationDraft(op="create_box")])
        assert window.session.wait_for_idle(60_000)
        for _ in range(30):
            qt_app.processEvents()
        pristine = function_language.ground_state(window)
        window.object_tree.select_object("obj_1")
        for _ in range(30):
            qt_app.processEvents()
        assert function_language.ground_state(window) != pristine, "Reiter Auswahl vorn"
        ports = QtPorts(window, 0.0)
        # Gemerkt wird *Filament und Druck*; sie steht seit FD-19 oben und braucht
        # keinen Radschritt. Gerollt wird zu *Vorbereiten* unter dem Rand.
        for name, click_it in (("filament.section", True), ("section:prepare", False)):
            for _step in range(60):
                click = guide_targets.next_click(window, name)
                point = click.rect.center()
                under = guide_targets.widget_under(point)
                if click.why == "rollen":
                    ports.press(under, point, "wheel_down", wheel_angle=click.wheel_angle)
                else:
                    if click_it:
                        ports.press(under, point, "left")
                    break
                for _ in range(10):
                    qt_app.processEvents()
            for _ in range(10):
                qt_app.processEvents()
        for _ in range(30):
            qt_app.processEvents()
        state = function_language.ground_state(window)
        assert state[1] != pristine[1], "der gemerkte Abschnitt fehlt im Ausgangszustand"
        assert any(state[2]), "die gerollte Karte fehlt im Ausgangszustand"
    finally:
        window.hide()
        window.release()
