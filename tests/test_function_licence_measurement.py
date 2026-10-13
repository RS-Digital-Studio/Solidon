"""P18 urteilt nur über wirklich abgeschlossene Lizenzwege (NC-S1)."""

from types import SimpleNamespace
from typing import Any

import pytest

from tests.bench_fakes import FakeClick, FakePorts, FakeTimer, FakeWidget
from tools import function_bench, function_setup, function_surface
from tools.function_checks import LICENCE_UNLOCKED
from tools.function_list import licence_states
from tools.function_machine import Step
from tools.function_points import judge_licence
from tools.function_walk import Walk


def valid_runs() -> dict[str, Any]:
    """Die angebotene Operation und ihre begründeten Sperren als Gegenkontrolle."""
    return {
        state: {
            "writes": True,
            "state": "angeboten" if LICENCE_UNLOCKED[state] else "grau",
            "reason": "" if LICENCE_UNLOCKED[state] else "Solidon freischalten",
        }
        for state in licence_states()
    }


@pytest.mark.parametrize("mode", ["ok", "selection", "acting"])
def test_a_broken_licence_walk_never_becomes_a_measurement(monkeypatch: Any, mode: str) -> None:
    """Echter Walk und StepMachine: fehlendes Auswahlziel und Eingabeausnahme bleiben offen."""
    timer = FakeTimer()
    monkeypatch.setattr(function_bench, "qt_schedule", timer.schedule)
    monkeypatch.setattr(function_bench, "time", SimpleNamespace(perf_counter=timer.clock))
    monkeypatch.setattr(function_surface, "grey_reason", lambda window, name: None)
    monkeypatch.setattr(function_surface, "in_view", lambda window, names: False)
    target = "operation:drill_hole"
    ports = FakePorts(
        timer, {target: [FakeClick((0, 0, 9, 9), "left", "ziel", FakeWidget(target))]}
    )
    connections: list[Any] = []
    flow = function_bench.FunctionFlow.__new__(function_bench.FunctionFlow)
    flow.data = {"findings": [], "errors": [], "closed_by_escape": [], "unmeasured": {}}
    flow.row = {
        "kind": "operation",
        "target": target,
        "route": [{"target": "tree.row:absent", "button": "left"}] if mode == "selection" else [],
    }
    flow.spec = {}
    flow.window = None
    flow.variant = function_setup.Variant.of({"set": "lizenz", "licence": "licensed"})
    flow.session = SimpleNamespace(
        failed=SimpleNamespace(connect=connections.append, disconnect=connections.remove)
    )
    flow.apply_target = None
    flow.walker = Walk(ports, [], 0.0)
    flow.ports = ports
    flow.widget = lambda name: None
    flow.scene_now = lambda: {"ops": ["create_box"]}
    flow.pump = timer.pump
    flow.persist = lambda: None
    flow.escape_modal = lambda: None
    flow.stuck_modal = lambda label: None
    flow.mark_own = lambda machine: None

    def broken_step(machine: Any) -> None:
        raise RuntimeError("Eingabe bricht ab")

    flow.input_steps = lambda inputs: [Step("Eingabe", broken_step)] if mode == "acting" else []
    flow.effect_steps = lambda label: ([Step("Wirkung", lambda machine: None)], lambda: True)
    flow.phase_licence()
    assert connections == []
    runs = valid_runs()
    runs.pop("licensed")
    runs.update(flow.data.get("licence_runs", {}))
    outcome = judge_licence(runs, complete=True)
    if mode == "ok":
        assert outcome.verdict == "erfuellt", outcome
        assert flow.data["findings"] == flow.data["errors"] == []
    else:
        assert outcome.verdict == "nicht_gelaufen", outcome
        assert flow.data["unmeasured"]["licence_runs.licensed"]
        assert flow.data["findings"] if mode == "selection" else flow.data["errors"]
        if mode == "selection":
            assert ports.pressed == []


@pytest.mark.parametrize(
    "entry",
    [
        None,
        [],
        "angeboten",
        {},
        {"writes": True},
        {"writes": True, "state": "angeboten", "reason": None},
        {"writes": True, "state": "grau", "reason": 12},
    ],
)
def test_every_required_run_needs_typed_inner_values(entry: Any) -> None:
    """Ein vorhandener Name ist noch keine Messung; beschädigte Werte stürzen nicht ab."""
    runs = valid_runs()
    runs["licensed"] = entry
    assert judge_licence(runs, complete=True).verdict == "nicht_gelaufen"


def test_empty_null_and_unknown_runs_are_not_green() -> None:
    """Auch das Einzelurteil braucht mindestens einen bekannten, gemessenen Zustand."""
    for runs in (
        {},
        dict.fromkeys(licence_states()),
        {"unknown": {"writes": False, "state": "angeboten", "reason": ""}},
    ):
        assert judge_licence(runs, complete=False).verdict == "nicht_gelaufen"
    assert judge_licence(valid_runs(), complete=True).verdict == "erfuellt"


def test_a_damaged_run_is_not_comparison_evidence() -> None:
    """Ungültiges Angebot beweist kein Verstecken; ungültiges Schreiben keine Lizenzverletzung."""
    runs = {
        "needs_activation": {"writes": False, "state": "fehlt", "reason": ""},
        "licensed": {"writes": True, "state": "angeboten", "reason": None},
    }
    assert judge_licence(runs, complete=False).verdict == "nicht_gelaufen"
    runs["needs_activation"]["state"] = "angeboten"
    assert judge_licence(runs, complete=False).verdict == "nicht_gelaufen"
