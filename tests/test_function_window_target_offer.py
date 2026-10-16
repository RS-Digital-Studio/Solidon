"""Ein Fenster als Ziel wird gelesen, solange es steht: Matrix (P13) und Lizenzlauf (P18).

``path_steps`` sagt seit FD-101: Ein Fenster als Ziel ist erreicht, sobald es
dasteht. Matrix und Lizenzlauf öffneten das Fenster über den Weg der Zeile,
der Automat räumte es am Ende des Schritts mit Escape ab, und erst danach
fragten sie nach dem Ziel — „fehlt“ an jeder Fensterzeile, auch im Zustand
*licensed* (RC-4). Ohne Fenster: Der nachgestellte Lauf öffnet das Fenster mit
dem Weg und schließt es, wenn der Lauf endet, wie der Automat.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tests.bench_fakes import FakePorts, FakeTimer
from tools import function_bench, function_surface, function_walk
from tools.function_protocol import empty_protocol

TARGET = "dialog:about_dialog"
OPENER = "menu:menubar.ueber_solidon"
ROW = {
    "id": TARGET,
    "target": TARGET,
    "kind": "dialog",
    "route": [
        {"target": OPENER, "button": "left", "modifier": ""},
        {"target": TARGET, "button": "left", "modifier": ""},
    ],
    "spec": {},
}


class WindowPorts(FakePorts):
    """Das Ziel ist nur auffindbar, solange das Fenster steht."""

    def __init__(self) -> None:
        super().__init__(FakeTimer(), {})
        self.open = False

    def next_click(self, name: str) -> Any:
        if name == TARGET and self.open:
            return SimpleNamespace(target=None)
        raise LookupError(f"{name}: kein Fenster dieser Klasse ist offen")


def _flow(monkeypatch: pytest.MonkeyPatch, *, grey_opener: str | None = None) -> Any:
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = ROW
    flow.spec = {}
    flow.data = empty_protocol(ROW, {}, {})
    flow.window = object()
    flow.walker = function_walk.Walk(WindowPorts(), [], 0.0)
    flow.walker.stable = lambda name, *args, **named: lambda: True  # type: ignore[method-assign]
    flow.ports = flow.walker.ports
    flow.reset = lambda: True
    flow.session = SimpleNamespace(
        last_result=SimpleNamespace(scene=SimpleNamespace(objects={})),
        failed=SimpleNamespace(connect=lambda slot: None, disconnect=lambda slot: None),
    )
    flow.scene_now = dict
    flow.widget = lambda name: None
    flow.variant = SimpleNamespace(licence="licensed")
    flow.apply_target = None
    monkeypatch.setattr(
        function_surface,
        "grey_reason",
        lambda window, name: grey_opener if name == OPENER else None,
    )

    def run_steps(label: str, steps: list[Any], timeout_s: float | None = None) -> bool:
        # Der Weg öffnet das modale Fenster; was danach im Lauf steht, sieht es offen.
        flow.ports.open = not grey_opener
        for step in steps:
            if not step.name.startswith("weg zu"):
                step.act(SimpleNamespace(insert=lambda more: None))
        # Am Ende des Laufs räumt der Automat das Fenster mit Escape ab.
        flow.ports.open = False
        return True

    flow.run_steps = run_steps
    return flow


def test_the_matrix_reads_a_window_while_it_stands(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = _flow(monkeypatch)
    flow.phase_matrix()
    assert flow.data["matrix"]["ohne"]["state"] == "angeboten", flow.data["matrix"]["ohne"]
    assert flow.data["matrix"]["ohne"]["effective"] is True


def test_the_licence_run_reads_a_window_while_it_stands(monkeypatch: pytest.MonkeyPatch) -> None:
    flow = _flow(monkeypatch)
    flow.phase_licence()
    assert flow.data["licence_runs"]["licensed"]["state"] == "angeboten", flow.data
    assert flow.data["licence_runs"]["licensed"]["writes"] is False


def test_a_grey_opener_gives_the_window_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gegenfall: Der Weg öffnet nichts, weil der Öffner grau steht — grau mit seinem Grund."""
    reason = "Erst freischalten: Hilfe → Solidon freischalten …"
    flow = _flow(monkeypatch, grey_opener=reason)
    flow.phase_licence()
    assert flow.data["licence_runs"]["licensed"] == {
        "writes": False,
        "state": "grau",
        "reason": reason,
    }
