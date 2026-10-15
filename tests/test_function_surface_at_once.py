"""Eine Handlung, die mit dem Klick wirkt, wird vor ihrer Wirkung gemessen (FD-115, Rest zu FD-37).

Der Fix von FD-37 hielt den Weg nur bei Zielen ``finding.action:`` und
``feature:`` vor dem letzten Klick an. Die erste Handlung des Prüfberichts
(``report.action``) und *Objekt entfernen* (``operation:delete_object``) wirken
ebenso mit ihrem Klick; ihre Flächen entstanden nach der Wirkung — der Körper
schon auf dem Bett, der Quader schon weg (Lauf 043). Entschieden wird jetzt an
der Art der Handlung (``function_surface.acts_at_once``), nicht am Präfix.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.bench_fakes import FakeClick, FakePorts, FakeTimer, FakeWidget, run_machine
from tools import function_bench, function_surface
from tools.function_machine import Step
from tools.function_setup import Variant
from tools.function_walk import Walk


@pytest.fixture(autouse=True)
def operations() -> None:
    """Ob eine Operation Werte fragt, sagt das geladene Register."""
    from app.core.bootstrap import load_operations

    load_operations()


def _surface_run(monkeypatch: Any, target: str) -> tuple[list[list[str]], list[str]]:
    """Die Phase ``surface`` einer Zeile mit diesem Ziel: was beim Aufnehmen schon geklickt war."""
    timer = FakeTimer()
    widgets = [FakeWidget(name) for name in ("Weg", "Ziel")]
    ports = FakePorts(
        timer,
        {
            target: [
                FakeClick((0, 0, 20, 20), "left", why, widget)
                for why, widget in zip(("reiter", "ziel"), widgets, strict=True)
            ]
        },
    )
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = {"id": target, "target": target, "source": "wortschatz"}
    flow.variant = Variant.of({"set": "dunkel"})
    flow.data = {}
    flow.window = object()
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: None)
    flow.walker = Walk(ports, [], 0)
    flow.surface = lambda: widgets[-1]
    flow.claim_surface = lambda root: None
    captured: list[list[str]] = []
    flow.capture_surface = lambda root: captured.append([name for name, _, _ in ports.pressed])
    flow.picture = lambda name: None
    flow.still_step = lambda name, root: Step(name, lambda machine: None)
    flow.run_steps = lambda label, steps: run_machine(timer, steps).error is None
    flow.phase_surface()
    return captured, [name for name, _, _ in ports.pressed]


@pytest.mark.parametrize("target", ["report.action", "operation:delete_object"])
def test_an_action_that_acts_with_its_click_is_measured_before_it(
    monkeypatch: Any, target: str
) -> None:
    """Aufgenommen wird vor dem Zielklick; danach fällt er doch, wie beim Kunden."""
    captured, pressed = _surface_run(monkeypatch, target)
    assert captured == [["Weg"]], captured
    assert pressed == ["Weg", "Ziel"], pressed


def test_an_operation_that_asks_for_values_is_measured_in_what_it_opens(monkeypatch: Any) -> None:
    """Gegenprobe: *Bohrung setzen* fragt Werte — die Fläche ist ihr Dialog, nach dem Klick."""
    captured, pressed = _surface_run(monkeypatch, "operation:drill_hole")
    assert captured == [["Weg", "Ziel"]], captured
    assert pressed == ["Weg", "Ziel"], pressed


@pytest.mark.parametrize(
    ("target", "at_once"),
    [
        ("finding.action:place_on_bed", True),
        ("report.action", True),
        ("operation:delete_object", True),
        ("operation:place_on_bed", True),
        ("operation:drill_hole", False),
        ("operation:create_label", False),
        ("menu:menubar.parameter_anlegen", False),
        ("tool:analysis", False),
    ],
)
def test_the_kind_of_action_decides_not_the_prefix(target: str, at_once: bool) -> None:
    """Befundhandlungen, die erste Berichtshandlung und Operationen ohne Werte wirken sofort."""
    assert function_surface.acts_at_once(object(), target) is at_once
