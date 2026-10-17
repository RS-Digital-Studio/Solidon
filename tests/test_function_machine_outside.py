"""Eine modale Schleife, die keine Handlung des Automaten öffnete, wird trotzdem abgeräumt.

Ein Arbeiter fragt (*Alle Merkmale erkennen*: die lange Vollerkennung, §21.1),
eine Absage kommt als Meldung (*Davor einfügen* mit einem Folgeschritt, der
sein Merkmal verlöre): Das Fenster geht während ``pump`` auf, nicht in einem
Schritt. Der Automat war danach fertig und tickte nicht mehr, ``drive`` stand
in der Schleife des Fensters, und der Fall hing bis zur Frist des
Elternprozesses (Proben FD-101: fünf und mehr Minuten in ``show_error`` und
``_on_ask``). Jetzt räumt der Automat eine solche Schleife ab wie eine eigene.
"""

from __future__ import annotations

from typing import Any

from tests.bench_fakes import FakeTimer
from tools import function_machine
from tools.function_machine import Step


def _run(timer: FakeTimer, state: dict[str, Any], *, nested: bool) -> Any:
    machine = function_machine.StepMachine(
        timer.schedule,
        timer.clock,
        unstick=lambda: state.update(open=False),
        nested=(lambda: bool(state["open"])) if nested else None,
    )

    def pump() -> None:
        # Die Antwort des Arbeiters kommt im Ereignisdurchlauf, nach dem Klick.
        if state["asked"] and not state["shown"]:
            state.update(shown=True, open=True)
            timer.loop_until(lambda: not state["open"], limit=2_000)
        timer.pump()

    steps = [
        Step("klick", lambda machine: state.update(asked=True)),
        Step("antwort", lambda machine: None, ready=lambda: bool(state["shown"])),
    ]
    function_machine.drive(machine, steps, pump, timer.clock, 60.0)
    return machine


def test_a_modal_loop_from_outside_the_steps_is_closed() -> None:
    timer = FakeTimer()
    state: dict[str, Any] = {"asked": False, "shown": False, "open": False}
    machine = _run(timer, state, nested=True)
    assert state["shown"] and not state["open"]
    assert machine.done and machine.unsticks == 1


def test_without_the_question_the_loop_never_ends() -> None:
    """Gegenprobe: Ohne die Frage nach der Schleife endet sie nie — der alte Hänger."""
    import pytest

    timer = FakeTimer()
    state: dict[str, Any] = {"asked": False, "shown": False, "open": False}
    with pytest.raises((AssertionError, IndexError)):
        _run(timer, state, nested=False)
