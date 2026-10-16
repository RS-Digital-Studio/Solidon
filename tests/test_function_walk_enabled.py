"""Ein Wegziel, das gerade grau steht, klickt der Kunde erst, wenn es frei ist (FD-175).

Der Druckdialog sucht beim Öffnen seine Slicer; *Slicen* ist bis dahin grau. Der
Prüfstand klickte es sofort, der Klick tat nichts, und das nächste Wegziel — die
Meldung nach dem Absturz des Slicers — hieß „nicht auffindbar“. Jetzt wartet
ein Wegziel (``when_enabled``), bis es frei ist, höchstens ``PENDING_S``, dann
meldet es „keine Rückmeldung“ samt Grund. Das Ziel der Zeile selbst wartet nicht:
Sein Grau misst der Fehlfall.
"""

from __future__ import annotations

from tests.bench_fakes import FakeClick, FakePorts, FakeTimer, FakeWidget, run_machine
from tools.function_checks import NO_RESPONSE
from tools.function_walk import PENDING_S, Walk


def _walk(grey_until: float, *, when_enabled: bool) -> tuple[FakeTimer, FakePorts, object]:
    timer = FakeTimer()
    button = FakeWidget("Slicen", grey_until=grey_until)
    ports = FakePorts(timer, {"print.slice": [FakeClick((0, 0, 90, 26), "left", "ziel", button)]})
    walker = Walk(ports, [], 0.0)
    machine = run_machine(timer, [walker.step("print.slice", when_enabled=when_enabled)])
    return timer, ports, machine


def test_a_grey_way_target_is_clicked_once_it_is_free() -> None:
    timer, ports, machine = _walk(8.0, when_enabled=True)
    assert machine.finding is None
    assert [name for name, _point, _button in ports.pressed] == ["Slicen"]
    assert timer.now >= 8.0


def test_without_the_wait_the_grey_target_is_clicked_at_once() -> None:
    """Das Ziel der Zeile: geklickt, wie es steht — grau eingeschlossen."""
    timer, ports, machine = _walk(8.0, when_enabled=False)
    assert machine.finding is None
    assert [name for name, _point, _button in ports.pressed] == ["Slicen"]
    assert timer.now < 8.0


def test_a_way_target_that_stays_grey_is_no_response() -> None:
    _timer, ports, machine = _walk(PENDING_S + 30.0, when_enabled=True)
    assert machine.finding is not None and machine.finding.kind == NO_RESPONSE
    assert "noch grau" in machine.finding.detail
    assert ports.pressed == []
