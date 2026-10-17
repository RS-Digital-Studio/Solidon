"""Nachgestellter Zeitgeber, nachgestellte Oberfläche und Probezeilen für die Prüfstandstests.

``FakeTimer`` ersetzt den Zeitgeber des Schrittautomaten, ``FakePorts`` die
Oberfläche als Drehbuch der Klicks, die ``next_click`` nacheinander nennt;
``ROWS`` sind Zeilen in der Form von ``function_list.rows``, ``PROBE_ROW`` die
Zeile des Probelaufs. Gemeinsam für ``test_function_*.py``.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from tools import (
    function_machine,
)


class FakeTimer:
    """Ein Zeitgeber mit eigener Uhr; ``loop_until`` ist eine Schleife wie ``exec()``."""

    def __init__(self) -> None:
        self.now = 0.0
        self.pending: list[tuple[float, int, Callable[[], None]]] = []
        self.counter = 0

    def schedule(self, milliseconds: int, callback: Callable[[], None]) -> None:
        self.counter += 1
        heapq.heappush(self.pending, (self.now + milliseconds / 1000.0, self.counter, callback))

    def clock(self) -> float:
        return self.now

    def step(self) -> None:
        when, _number, callback = heapq.heappop(self.pending)
        self.now = max(self.now, when)
        callback()

    def pump(self) -> None:
        if self.pending:
            self.step()
        else:
            self.now += 0.01

    def loop_until(self, done: Callable[[], bool], limit: int = 100_000) -> None:
        for _ in range(limit):
            if done():
                return
            self.step()
        raise AssertionError("die verschachtelte Schleife endete nie")


@dataclass(eq=False)
class FakeWidget:
    name: str
    zone: str = "karte_rechts"
    children: list[FakeWidget] = field(default_factory=list)
    #: Bis wann der Knopf grau steht, nach der Uhr des Zeitgebers (``Ports.enabled``).
    grey_until: float = 0.0

    def isAncestorOf(self, other: FakeWidget) -> bool:  # noqa: N802 - Qts Name
        return any(child is other or child.isAncestorOf(other) for child in self.children)


@dataclass
class FakeClick:
    """Wie ``guide_targets.Click``; ``target`` ist hier das gemeinte Widget, für die Probe."""

    rect: tuple[int, int, int, int]
    button: str
    why: str
    target: FakeWidget
    direction: int = 0
    wheel_angle: int = 120


class FakePorts:
    """Die Oberfläche als Drehbuch: je Ziel die Klicks, die ``next_click`` nacheinander nennt."""

    def __init__(
        self,
        timer: FakeTimer,
        script: dict[str, list[FakeClick]],
        under: Callable[[FakeClick], FakeWidget | None] | None = None,
        on_press: Callable[[FakeWidget, str], None] | None = None,
    ) -> None:
        self.timer = timer
        self.script = {name: list(clicks) for name, clicks in script.items()}
        self.under = under or (lambda click: click.target)
        self.on_press = on_press
        self.pressed: list[tuple[str, tuple[int, int], str]] = []
        self.wheel_angles: list[int] = []
        self.keys_sent: list[str] = []
        self.typed: list[str] = []
        self.moved: list[tuple[int, int]] = []
        #: Bis wann das Fenster sagt, dass etwas kommt (``Ports.pending``).
        self.pending_until = 0.0
        self._last: FakeClick | None = None
        self._last_name = ""

    def next_click(self, name: str) -> FakeClick:
        """Der nächste Klick, so oft gefragt wird; erst ein Klick schiebt das Drehbuch weiter."""
        clicks = self.script.get(name)
        if not clicks:
            raise LookupError(f"{name}: kein Weg")
        self._last, self._last_name = clicks[0], name
        return self._last

    def widget_under(self, point: tuple[int, int]) -> FakeWidget | None:
        assert self._last is not None
        return self.under(self._last)

    def covers(self, click: FakeClick, hit: FakeWidget) -> bool:
        return click.target is hit or click.target.isAncestorOf(hit)

    def centre(self, rect: tuple[int, int, int, int]) -> tuple[int, int]:
        return (rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)

    def press(
        self, widget: FakeWidget, point: tuple[int, int], button: str, *, wheel_angle: int = 120
    ) -> None:
        if wheel_angle <= 0:
            raise ValueError("Der Radwinkel muss positiv sein (Achtelgrad).")
        if button in ("wheel_up", "wheel_down"):
            self.wheel_angles.append(wheel_angle)
        self.pressed.append((widget.name, point, button))
        clicks = self.script.get(self._last_name, [])
        if len(clicks) > 1:
            clicks.pop(0)
        if self.on_press is not None:
            self.on_press(widget, button)

    def keys(self, sequence: Any) -> None:
        self.keys_sent.append(str(sequence))

    def move(self, point: tuple[int, int]) -> None:
        self.moved.append(point)

    def type_text(self, text: str) -> None:
        self.typed.append(text)

    def describe(self, widget: FakeWidget, point: Any = None) -> dict[str, Any]:
        return {"class": "FakeWidget", "object_name": widget.name, "mark": "", "text": widget.name}

    def zone_of(self, widget: FakeWidget) -> str | None:
        return widget.zone

    def rect_data(self, rect: tuple[int, int, int, int]) -> list[int]:
        return list(rect)

    def point_data(self, point: tuple[int, int]) -> list[int]:
        return list(point)

    def now(self) -> float:
        return self.timer.now

    def pending(self) -> bool:
        return self.timer.now < self.pending_until

    def aim(self, click: FakeClick, point: tuple[int, int]) -> tuple[int, int]:
        return point

    def enabled(self, widget: FakeWidget) -> bool:
        return self.timer.now >= widget.grey_until


def run_machine(
    timer: FakeTimer,
    steps: list[function_machine.Step],
    *,
    unstick: Callable[[], None] | None = None,
    timeout_s: float = 600.0,
) -> function_machine.StepMachine:
    machine = function_machine.StepMachine(timer.schedule, timer.clock, unstick=unstick)
    function_machine.drive(machine, steps, timer.pump, timer.clock, timeout_s)
    return machine


ROWS: list[dict[str, Any]] = [
    {
        "id": "resize_hole",
        "kind": "operation",
        "source": "merkmalfenster",
        "package": "D4",
        "requirement": "merkmal:hole",
        "start_scene": "merkmal.hole.exakt",
        "target": "feature:resize_hole",
        "route": [{"target": "tree.row:obj_1.hole_1", "button": "left", "modifier": ""}],
        "spec": {"inputs": {"feature.field:resize_hole.diameter": 5.0}},
    },
    {
        "id": "drill_hole",
        "kind": "operation",
        "source": "register",
        "package": "D4",
        "requirement": "koerper:1",
        "start_scene": "quader.exakt",
        "target": "operation:drill_hole",
        "route": [{"target": "tree.row:obj_1", "button": "left", "modifier": ""}],
        "spec": {"preconditions": {"slicer": "vorhanden"}},
    },
    {
        "id": "finding.action:place_on_bed",
        "kind": "bedienflaeche",
        "source": "befundhandlung",
        "package": "D8",
        "requirement": "befund",
        "start_scene": "unter_dem_bett.netz",
        "target": "finding.action:place_on_bed",
        "route": [],
        "spec": None,
    },
    {
        "id": "startup.expired_demo",
        "kind": "bedienflaeche",
        "source": "startablauf",
        "package": "D12",
        "requirement": "start",
        "start_scene": "startbildschirm",
        "target": "",
        "route": [],
        "spec": None,
    },
]

#: Die Probezeile der Merkmalshandlungen (Plan D0, Abschnitt 1.2, D4).
PROBE_ROW = "resize_hole"
