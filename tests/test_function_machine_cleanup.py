"""Eine fehlgeschlagene Bereitschaft darf eine modale Handlung nicht eingeschlossen lassen."""

import pytest

from tests.bench_fakes import FakeTimer, run_machine
from tools.function_machine import BenchFinding, Step


@pytest.mark.parametrize("failure", ["timeout", "finding", "exception"])
def test_readiness_failure_still_unwinds_the_own_modal_action(failure):
    """Echter Automat in verschachtelter Schleife: nach Rot folgt weiterhin Escape."""
    timer = FakeTimer()
    state = {"open": False}

    def open_(machine):
        state["open"] = True
        timer.loop_until(lambda: not state["open"])

    def ready():
        if failure == "exception":
            raise RuntimeError("Bereitschaft nicht lesbar")
        return False

    machine = run_machine(
        timer,
        [
            Step("öffnen", open_),
            Step(
                "wartet",
                lambda machine: None,
                ready=ready,
                timeout_s=0.1,
                on_timeout=(lambda: BenchFinding("nicht auffindbar", "Ziel", "fehlt"))
                if failure == "finding"
                else None,
            ),
        ],
        unstick=lambda: state.update(open=False),
    )
    assert not state["open"]
    assert machine.done and machine.unsticks == 1
    assert (machine.finding is not None) is (failure == "finding")
    assert (machine.error is not None) is (failure != "finding")
