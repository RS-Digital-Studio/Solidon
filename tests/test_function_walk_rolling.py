"""Ein Radschritt, der näher bringt, ist kein Kreis im Weg (FD-131, RM-737).

Der Weg zu einem Ziel hielt nach :data:`function_walk.MOST_WAY_CLICKS` Wegklicks
an. Rollen zählte mit, auch wenn jeder Schritt das Ziel näher brachte: Auf der
kleinsten Arbeitsfläche liegt die Klappe *Filament und Druck* an einem
gewählten Körper weiter unter dem Rand, als acht Radschritte reichen, und die
Filamentzeilen hießen „nicht auffindbar … das Ziel kam nicht ins Bild“. Jetzt
zählt ein Radschritt mit Annäherung nicht; angehalten wird, wenn zwei
Radschritte in Folge nichts näher bringen.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.bench_fakes import FakeClick, FakePorts, FakeTimer, FakeWidget, run_machine
from tools import function_walk
from tools.function_checks import NOT_FOUND


class RollingPorts(FakePorts):
    """Nachgestellte Oberfläche, deren Radschritte sagen, ob sie etwas bewegten."""

    def __init__(self, timer: FakeTimer, script: dict[str, list[FakeClick]], moves: bool) -> None:
        super().__init__(timer, script)
        self.moves = moves

    def press(
        self, widget: FakeWidget, point: tuple[int, int], button: str, *, wheel_angle: int = 120
    ) -> bool | None:
        super().press(widget, point, button, wheel_angle=wheel_angle)
        return self.moves if button.startswith("wheel_") else None


def _rolls_then_target(rolls: int) -> dict[str, list[FakeClick]]:
    card, target = FakeWidget("Karte"), FakeWidget("Ziel")
    clicks = [FakeClick((0, 0, 100, 400), "none", "rollen", card, direction=1)] * rolls
    return {"ziel": [*clicks, FakeClick((0, 0, 20, 20), "left", "ziel", target)]}


@pytest.mark.parametrize("rolls", [function_walk.MOST_WAY_CLICKS + 1, 25])
def test_rolling_that_brings_the_target_closer_reaches_it(rolls: int) -> None:
    """Mehr Radschritte als Wegklicks erlaubt, jeder mit Annäherung: das Ziel wird erreicht."""
    timer = FakeTimer()
    ports = RollingPorts(timer, _rolls_then_target(rolls), moves=True)
    walker = function_walk.Walk(ports, [], 0.0)
    machine = run_machine(timer, [walker.step("ziel")])
    assert machine.finding is None, machine.finding
    assert [name for name, _, _ in ports.pressed] == ["Karte"] * rolls + ["Ziel"]
    assert all(step.get("moved") is True for step in walker.steps if step.get("why") == "rollen")


def test_rolling_without_progress_still_stops() -> None:
    """Gegenprobe: Ein Rollbereich, der nicht weiterrollt, hält nach zwei Schritten an."""
    timer = FakeTimer()
    ports = RollingPorts(timer, _rolls_then_target(25), moves=False)
    walker = function_walk.Walk(ports, [], 0.0)
    machine = run_machine(timer, [walker.step("ziel")])
    assert machine.finding is not None and machine.finding.kind == NOT_FOUND
    assert "kam nicht ins Bild" in machine.finding.detail, machine.finding.detail
    assert len(ports.pressed) == function_walk.STILL_ROLLS, ports.pressed


def test_a_port_that_cannot_tell_keeps_the_old_limit() -> None:
    """Sagt die Oberfläche nicht, ob ein Schritt rollte, gilt die alte Grenze der Wegklicks."""
    timer = FakeTimer()
    ports = FakePorts(timer, _rolls_then_target(25))
    walker = function_walk.Walk(ports, [], 0.0)
    machine = run_machine(timer, [walker.step("ziel")])
    assert machine.finding is not None and machine.finding.kind == NOT_FOUND
    assert len(ports.pressed) == function_walk.MOST_WAY_CLICKS + 1


def test_the_real_wheel_reports_whether_its_area_rolled(qt_app: Any) -> None:
    """Am echten Rollbereich: Rad nach unten rückt vor, am Anschlag nicht mehr."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QScrollArea, QWidget

    area = QScrollArea()
    inner = QWidget()
    inner.setFixedSize(200, 2000)
    area.setWidget(inner)
    area.resize(240, 200)
    area.show()
    try:
        for _ in range(20):
            qt_app.processEvents()
        ports = function_walk.QtPorts(area, 0.0)
        point = area.viewport().mapToGlobal(QPoint(100, 100))
        assert ports.press(area.viewport(), point, "wheel_down") is True
        bar = area.verticalScrollBar()
        bar.setValue(bar.maximum())
        assert ports.press(area.viewport(), point, "wheel_down") is False
        assert ports.press(area.viewport(), point, "wheel_up") is True
    finally:
        area.hide()
        area.deleteLater()
