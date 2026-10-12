"""Der Prüfstand der Funktionsfälle — ohne Fenster (D0-P, RM-737).

``tools/function_bench.py`` fährt eine Funktion am echten Fenster so, wie der
Kunde sie bedient: jeder Klick an der Stelle, die ``guide_targets.next_click``
nennt, mit der Probe, ob dort das Ziel liegt; Zahlen getippt; ein Schrittautomat,
der auch durch modale ``exec()``-Schleifen weiterläuft. Was davon reine Rechnung
ist, prüft diese Datei an nachgestellten Ereignissen und Zeitgebern: der
Automat, Wegklicks, „verdeckt“, „nicht auffindbar“, der Szenenabdruck, das
Zahlenformat je Sprache, die Herzschlaglücke, Profil, Lizenz und Vorbedingungen,
dazu dass ein geschriebenes Protokoll gegen das Schema von D0-U gültig ist und
jeder Prüfpunkt ein Feld bekommt. Und der Wächter, dass Prüfstand, Aufnahmen
und ``WindowFlow`` keine Bedienung umgehen und ``function_bench`` keinen eigenen
Einstieg hat (kein drittes Fensterwerkzeug, Konzept Funktionsdurchgang §12).

Die Wege am Fenster selbst prüfen die Fenstertests unten (``windowed``), die
beim Push nach main in der CI laufen.
"""

from __future__ import annotations

import ast
import heapq
import itertools
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from tests.ui_helpers import session as session
from tests.ui_helpers import window as window
from tools import function_bench as bench
from tools import function_capture as capture
from tools.file_acceptance import (
    ROOT,
    Case,
    function_cases,
    read_cases,
    resumes,
    summary,
    write_json,
)
from tools.function_checks import (
    CHECKPOINTS,
    LICENCE_UNLOCKED,
    MAIN_PHASES,
    PROTOCOL_FIELDS,
    PROTOCOL_SCHEMA,
    SELECTION_STAGES,
    WHY,
    validate_protocol,
)
from tools.function_list import LICENCE_STATES, STARTUP_LICENCE, licence_states

BENCH = ROOT / "tools" / "function_bench.py"
CAPTURE = ROOT / "tools" / "function_capture.py"
ACCEPTANCE = ROOT / "tools" / "file_acceptance.py"


# --- Nachgestellter Zeitgeber und nachgestellte Oberfläche ----------------------------


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
        self.keys_sent: list[str] = []
        self.typed: list[str] = []
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

    def press(self, widget: FakeWidget, point: tuple[int, int], button: str) -> None:
        self.pressed.append((widget.name, point, button))
        clicks = self.script.get(self._last_name, [])
        if len(clicks) > 1:
            clicks.pop(0)
        if self.on_press is not None:
            self.on_press(widget, button)

    def keys(self, sequence: Any) -> None:
        self.keys_sent.append(str(sequence))

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


def run_machine(
    timer: FakeTimer,
    steps: list[bench.Step],
    *,
    unstick: Callable[[], None] | None = None,
    timeout_s: float = 600.0,
) -> bench.StepMachine:
    machine = bench.StepMachine(timer.schedule, timer.clock, unstick=unstick)
    bench.drive(machine, steps, timer.pump, timer.clock, timeout_s)
    return machine


# --- Der Schrittautomat (B6) -------------------------------------------------------------


def test_the_machine_runs_on_inside_a_modal_loop_and_finishes_after_it() -> None:
    """Ein Klick öffnet einen Dialog über ``exec()`` und kehrt erst nach dessen Ende zurück.

    Schritt 1 blockiert in einer verschachtelten Schleife, bis der Dialog zu
    ist; Schritt 2 wartet, bis er offen ist, und schließt ihn; Schritt 3 kommt
    danach. Ein linear geschriebener Ablauf bliebe in Schritt 1 stehen.
    """
    timer = FakeTimer()
    state = {"open": False}
    order: list[str] = []

    def opens(machine: bench.StepMachine) -> None:
        order.append("klick öffnet")
        state["open"] = True
        timer.loop_until(lambda: not state["open"])
        order.append("klick kehrt zurück")

    def closes(machine: bench.StepMachine) -> None:
        order.append("im dialog geklickt")
        state["open"] = False

    machine = run_machine(
        timer,
        [
            bench.Step("öffnen", opens),
            bench.Step("schließen", closes, ready=lambda: state["open"]),
            bench.Step("danach", lambda machine: order.append("danach")),
        ],
    )
    assert machine.done and machine.error is None and machine.finding is None
    assert order == ["klick öffnet", "im dialog geklickt", "klick kehrt zurück", "danach"]


def test_a_step_that_never_becomes_ready_stops_with_its_name() -> None:
    timer = FakeTimer()
    machine = run_machine(
        timer, [bench.Step("wartet ewig", lambda machine: None, ready=lambda: False, timeout_s=2.0)]
    )
    assert machine.done
    assert machine.error is not None and "wartet ewig" in machine.error
    assert "Zeitgrenze" in machine.error


def test_a_modal_left_open_is_closed_until_the_action_returns() -> None:
    """Endet der Automat, während eine Handlung noch in einer modalen Schleife steht, räumt er ab.

    Am Fenster ist das Escape an das modale Fenster; hier schließt der Rückruf
    den nachgestellten Dialog. Ohne ihn hinge der Lauf in der Schleife.
    """
    timer = FakeTimer()
    state = {"open": False}

    def opens(machine: bench.StepMachine) -> None:
        state["open"] = True
        timer.loop_until(lambda: not state["open"])

    machine = run_machine(
        timer,
        [bench.Step("öffnen", opens)],
        unstick=lambda: state.update(open=False),
    )
    assert machine.done and machine.unsticks >= 1 and machine.error is None


def test_a_window_escape_cannot_close_is_named_once_not_escaped_forever() -> None:
    """Review L12: Höchstens ``MOST_UNSTICKS`` Escape, dann einmal ``on_stuck`` — und weiter.

    Das Fenster schließt erst ``on_stuck`` (am Fenster der Knopf zum Ablehnen);
    vorher sendete der Automat alle 120 ms Escape, bis die Frist ablief.
    """
    timer = FakeTimer()
    state = {"open": False, "stuck": 0, "escapes": 0}

    def open_window(machine: bench.StepMachine) -> None:
        state["open"] = True
        timer.loop_until(lambda: not state["open"])

    def escape() -> None:
        state["escapes"] += 1

    def stuck() -> None:
        state["stuck"] += 1
        state["open"] = False

    machine = bench.StepMachine(timer.schedule, timer.clock, unstick=escape, on_stuck=stuck)
    bench.drive(machine, [bench.Step("öffnen", open_window)], timer.pump, timer.clock, 600.0)
    assert machine.done and machine.stuck
    assert state == {"open": False, "stuck": 1, "escapes": bench.MOST_UNSTICKS}


def test_an_error_in_an_action_stops_the_machine_with_the_trace() -> None:
    timer = FakeTimer()

    def broken(machine: bench.StepMachine) -> None:
        raise ValueError("kaputt")

    reached: list[str] = []
    machine = run_machine(
        timer,
        [bench.Step("kaputt", broken), bench.Step("danach", lambda machine: reached.append("x"))],
    )
    assert machine.done and machine.error is not None and "ValueError: kaputt" in machine.error
    assert reached == []


# --- Wege: Wegklicks, verdeckt, nicht auffindbar ---------------------------------------


def _card() -> tuple[FakeWidget, FakeWidget, FakeWidget, FakeWidget]:
    head_label = FakeWidget("kopf-text")
    head = FakeWidget("feature:resize_hole", children=[head_label])
    flap = FakeWidget("klappe")
    tab = FakeWidget("reiter", zone="karte_rechts")
    return tab, flap, head, head_label


def test_way_clicks_are_counted_and_each_click_lands_where_the_probe_says() -> None:
    """Reiter, Klappe, dann der Kopf der Handlung: zwei Wegklicks, ein Ziel.

    Der Treffer am Ziel ist ein Kind des Ziels (die Beschriftung im Kopf) — das
    zählt als Treffer, und der Klick geht an das Widget, das dort liegt.
    """
    timer = FakeTimer()
    tab, flap, head, head_label = _card()
    script = {
        "feature:resize_hole": [
            FakeClick((0, 0, 40, 20), "left", "reiter", tab),
            FakeClick((0, 30, 200, 20), "left", "klappe", flap),
            FakeClick((0, 60, 200, 30), "left", "ziel", head),
        ]
    }
    ports = FakePorts(
        timer, script, under=lambda click: head_label if click.target is head else click.target
    )
    steps: list[dict[str, Any]] = []
    walker = bench.Walk(ports, steps, 0.0)
    walker.phase = bench.PATH_PHASE
    machine = run_machine(timer, [walker.step("feature:resize_hole")])
    assert machine.done and machine.error is None and machine.finding is None
    assert [step["why"] for step in steps] == ["reiter", "klappe", "ziel"]
    assert all(step["hit"] and step["phase"] == "weg" for step in steps)
    assert [name for name, _point, _button in ports.pressed] == ["reiter", "klappe", "kopf-text"]
    assert bench.way_clicks(steps) == 2
    assert bench.place_of(steps, "feature:resize_hole") == {
        "where": "karte",
        "path": ["reiter", "klappe", "kopf-text"],
        "error": None,
    }


def test_a_click_that_would_land_on_something_else_is_the_finding_covered() -> None:
    """Liegt an der Stelle weder das Ziel noch ein Kind, wird nicht geklickt: Fund „verdeckt“."""
    timer = FakeTimer()
    _tab, _flap, head, _label = _card()
    toast = FakeWidget("einladung", zone="ansicht")
    script = {"feature:resize_hole": [FakeClick((0, 60, 200, 30), "left", "ziel", head)]}
    ports = FakePorts(timer, script, under=lambda click: toast)
    steps: list[dict[str, Any]] = []
    walker = bench.Walk(ports, steps, 0.0)
    walker.phase = bench.PATH_PHASE
    machine = run_machine(timer, [walker.step("feature:resize_hole")])
    assert machine.finding is not None and machine.finding.kind == bench.COVERED
    assert ports.pressed == []
    assert steps[-1]["hit"] is False and steps[-1]["finding"] == bench.COVERED
    assert steps[-1]["widget_at"]["object_name"] == "einladung"
    assert steps[-1]["t"] >= bench.STABLE_S + bench.COVERED_S
    assert bench.place_of(steps, "feature:resize_hole")["error"] is not None


def test_a_cover_that_clears_while_the_card_settles_is_no_finding() -> None:
    """Der Zwischenstand nach einem Aufklappen deckt kurz — gewartet wird, geklickt aufs Ziel.

    Der Baum wächst sofort, die Karte Runden später: Eine halbe Sekunde liegt
    über der Zeile die Karte, danach die Zeile selbst. Kein Fund, ein Klick.
    """
    timer = FakeTimer()
    row = FakeWidget("zeile")
    card = FakeWidget("overlayCard")
    script = {"tree.row:obj_1.hole_1": [FakeClick((0, 300, 200, 20), "left", "ziel", row)]}
    ports = FakePorts(timer, script, under=lambda click: card if timer.now < 0.5 else row)
    steps: list[dict[str, Any]] = []
    walker = bench.Walk(ports, steps, 0.0)
    walker.phase = bench.PATH_PHASE
    machine = run_machine(timer, [walker.step("tree.row:obj_1.hole_1")])
    assert machine.done and machine.finding is None and machine.error is None
    assert ports.pressed == [("zeile", (100, 310), "left")]
    assert steps[-1]["hit"] is True and steps[-1]["t"] >= 0.5


def test_a_target_without_a_way_is_the_finding_not_found() -> None:
    timer = FakeTimer()
    ports = FakePorts(timer, {})
    steps: list[dict[str, Any]] = []
    walker = bench.Walk(ports, steps, 0.0)
    walker.phase = "weg"
    machine = run_machine(timer, [walker.step("operation:drill_hole")])
    assert machine.finding is not None and machine.finding.kind == bench.NOT_FOUND
    assert len(steps) == 1 and steps[0]["t"] >= bench.MISSING_S, "erst nach der Frist"
    assert {key: value for key, value in steps[0].items() if key != "t"} == {
        "target": "operation:drill_hole",
        "finding": bench.NOT_FOUND,
        "detail": "operation:drill_hole: kein Weg",
        "phase": "weg",
    }
    assert bench.place_of(steps, "operation:drill_hole") == {
        "where": None,
        "path": [],
        "error": "operation:drill_hole: kein Weg",
    }


def test_a_target_that_appears_late_is_no_finding() -> None:
    """Review M14: Ein Ziel, das 0,5 s nach dem Klick davor erscheint, wird geklickt, kein Fund.

    Vorher war ein Schritt ohne Weg sofort „nicht auffindbar“ — ein Dialog nach
    einer Rechnung wurde so zum schweren Fund.
    """
    timer = FakeTimer()
    dialog = FakeWidget("dialog")

    class Late(FakePorts):
        def next_click(self, name: str) -> FakeClick:
            if timer.now < 0.5:
                raise LookupError(f"{name}: der Dialog ist noch nicht da")
            self._last, self._last_name = FakeClick((0, 0, 80, 20), "left", "ziel", dialog), name
            return self._last

    ports = Late(timer, {})
    steps: list[dict[str, Any]] = []
    machine = run_machine(timer, [bench.Walk(ports, steps, 0.0).step("dialog.accept")])
    assert machine.done and machine.finding is None and machine.error is None
    assert ports.pressed == [("dialog", (40, 10), "left")]


def test_a_way_that_never_reaches_the_target_ends_as_not_found() -> None:
    """Ein Weg aus lauter Wegklicks ist ein Kreis — nach :data:`MOST_WAY_CLICKS` ist Schluss."""
    timer = FakeTimer()
    tab, _flap, _head, _label = _card()
    ports = FakePorts(timer, {"feature:x": [FakeClick((0, 0, 10, 10), "left", "reiter", tab)]})
    steps: list[dict[str, Any]] = []
    machine = run_machine(timer, [bench.Walk(ports, steps, 0.0).step("feature:x")])
    assert machine.finding is not None and machine.finding.kind == bench.NOT_FOUND
    assert len(ports.pressed) == bench.MOST_WAY_CLICKS + 1
    assert "Rollen" not in machine.finding.detail


def test_a_list_that_scrolls_in_vain_is_named_in_the_finding() -> None:
    """Rollt jeder Wegklick an derselben Stelle, ohne dass das Ziel kommt, sagt der Fund das.

    So stand die angeschnittene letzte Zeile des Objektbaums da: Die Liste hat
    keinen Rollbalken, der Weg nennt trotzdem jedes Mal „rollen“.
    """
    timer = FakeTimer()
    area = FakeWidget("rollfläche")
    arrow = FakeWidget("pfeil")
    ports = FakePorts(
        timer,
        {
            "tree.row:obj_1.hole_1": [
                FakeClick((4, 130, 20, 50), "left", "aufklappen", arrow),
                FakeClick((4, 130, 262, 206), "none", "rollen", area, 1),
            ]
        },
    )
    steps: list[dict[str, Any]] = []
    machine = run_machine(timer, [bench.Walk(ports, steps, 0.0).step("tree.row:obj_1.hole_1")])
    assert machine.finding is not None and machine.finding.kind == bench.NOT_FOUND
    rolled = bench.MOST_WAY_CLICKS
    assert f"die letzten {rolled} Klicks rollten an derselben Stelle" in machine.finding.detail
    assert [button for _name, _point, button in ports.pressed] == ["left"] + ["wheel_down"] * rolled


def test_a_click_waits_until_its_place_stands_still() -> None:
    """Die Karte setzt ihre Höhen erst Runden nach dem Aufklappen: geklickt wird, wo es stillsteht.

    Der nachgestellte Weg nennt dreimal ein anderes Rechteck, dann bleibt es.
    Der Klick fällt auf das letzte — und erst :data:`STABLE_S` danach.
    """
    timer = FakeTimer()
    row = FakeWidget("zeile")

    class Drifting(FakePorts):
        def __init__(self) -> None:
            super().__init__(
                timer, {"tree.row:obj_1": [FakeClick((0, 0, 10, 10), "left", "ziel", row)]}
            )
            self.asked = 0

        def next_click(self, name: str) -> FakeClick:
            self.asked += 1
            y = min(self.asked, 4) * 40
            self._last = FakeClick((0, y, 100, 20), "left", "ziel", row)
            return self._last

    ports = Drifting()
    steps: list[dict[str, Any]] = []
    machine = run_machine(timer, [bench.Walk(ports, steps, 0.0).step("tree.row:obj_1")])
    assert machine.done and machine.error is None
    assert [point for _name, point, _button in ports.pressed] == [(50, 170)]
    assert steps[-1]["t"] >= bench.STABLE_S


def test_a_reading_waits_for_its_state_before_it_reads() -> None:
    """Review M1: Die Ruhe eines Schritts liegt nach ihm — gelesen wird nach einem Warteschritt.

    Gegenprobe: Ein Leseschritt mit ``settle_ms`` liest sofort (bei 0 s), auch
    wenn die Wirkung erst nach 0,5 s kommt. Mit ``until_step`` davor liest er
    danach; kommt sie nie, nach der Frist und ohne Fehler.
    """
    timer = FakeTimer()
    read_at: list[float] = []

    def read(machine: bench.StepMachine) -> None:
        read_at.append(timer.now)

    run_machine(timer, [bench.Step("lesen", read, settle_ms=2000)])
    assert read_at == [0.0], "so las der Prüfstand vor der Fixrunde"
    timer = FakeTimer()
    read_at.clear()
    machine = run_machine(
        timer,
        [
            bench.until_step("wirkung", lambda: timer.now >= 0.5, 2.0, timer.clock),
            bench.Step("lesen", read),
        ],
    )
    assert machine.error is None and 0.5 <= read_at[0] < 0.6
    timer = FakeTimer()
    read_at.clear()
    machine = run_machine(
        timer,
        [bench.until_step("nie", lambda: False, 2.0, timer.clock), bench.Step("lesen", read)],
    )
    assert machine.error is None and 2.0 <= read_at[0] < 2.1


def test_the_hover_label_is_read_once_the_view_shows_it() -> None:
    """Review S3: Name und Maß stehen erst nach der Suchfrist der Ansicht in ihrem Tooltip.

    Die Ansicht sucht 90 ms nach dem Hinfahren (``viewport.HOVER_DELAY_MS``).
    Gelesen wird danach, nicht 15 ms nach dem Hinfahren — so las der Prüfstand
    vorher, und jede Art stand ohne Namen da.
    """
    from app.ui.viewport import HOVER_DELAY_MS

    timer = FakeTimer()
    moved: dict[str, float] = {}

    def tooltip() -> str:
        shown = "t" in moved and timer.now >= moved["t"] + HOVER_DELAY_MS / 1000
        return "Bohrung 1\nØ5,20 mm" if shown else ""

    early: list[str] = []
    run_machine(
        timer,
        [
            bench.Step("hin", lambda machine: moved.setdefault("t", timer.now)),
            bench.Step("lesen", lambda machine: early.append(tooltip()), settle_ms=480),
        ],
    )
    assert early == [""], "so las der Prüfstand vor der Fixrunde"
    timer = FakeTimer()
    moved.clear()
    sink: list[str] = []
    machine = run_machine(
        timer,
        bench.hover_steps(
            lambda: moved.setdefault("t", timer.now) and None,
            tooltip,
            sink,
            timer.clock,
            HOVER_DELAY_MS / 1000,
        ),
    )
    assert machine.error is None
    assert sink == ["Bohrung 1\nØ5,20 mm"]


def test_a_scroll_click_turns_the_wheel_in_its_direction() -> None:
    """``rollen`` dreht das Rad, wohin ``Click.direction`` zeigt (1 nach unten, -1 nach oben)."""
    timer = FakeTimer()
    area = FakeWidget("rollfläche")
    target = FakeWidget("feld")
    script = {
        "feature.field:x.y": [
            FakeClick((0, 0, 100, 300), "none", "rollen", area, direction=1),
            FakeClick((0, 0, 100, 300), "none", "rollen", area, direction=-1),
            FakeClick((0, 0, 50, 20), "left", "ziel", target),
        ]
    }
    ports = FakePorts(timer, script)
    steps: list[dict[str, Any]] = []
    run_machine(timer, [bench.Walk(ports, steps, 0.0).step("feature.field:x.y")])
    assert [button for _name, _point, button in ports.pressed] == [
        "wheel_down",
        "wheel_up",
        "left",
    ]


def test_a_context_menu_opened_by_exec_is_walked_inside_its_own_loop() -> None:
    """Ein Rechtsklick öffnet das Kontextmenü über ``exec()``; der Eintrag kommt darin.

    Der Weg zum Eintrag geht im nächsten Schritt weiter, während der
    Rechtsklick noch nicht zurückgekehrt ist — genau das, woran ein linearer
    Ablauf hängen bliebe (Plan D0 B6).
    """
    timer = FakeTimer()
    row = FakeWidget("tree.row:obj_1", zone="karte_links")
    menu = FakeWidget("kontextmenü", zone="menue")
    state = {"menu": False}

    def on_press(widget: FakeWidget, button: str) -> None:
        if widget is row and button == "right":
            state["menu"] = True
            timer.loop_until(lambda: not state["menu"])
        elif widget is menu:
            state["menu"] = False

    script = {
        "tree.row:obj_1": [FakeClick((0, 0, 100, 20), "left", "ziel", row)],
        "menu:tree.rename": [FakeClick((0, 20, 100, 20), "left", "ziel", menu)],
    }
    ports = FakePorts(timer, script, on_press=on_press)
    steps: list[dict[str, Any]] = []
    walker = bench.Walk(ports, steps, 0.0)
    walker.phase = bench.PATH_PHASE
    machine = run_machine(
        timer,
        [
            walker.step("tree.row:obj_1", "right"),
            walker.step("menu:tree.rename"),
        ],
    )
    assert machine.done and machine.error is None and machine.finding is None
    assert [(name, button) for name, _point, button in ports.pressed] == [
        ("tree.row:obj_1", "right"),
        ("kontextmenü", "left"),
    ]
    assert bench.place_of(steps, "menu:tree.rename")["where"] == "kontext"


def test_the_place_names_menu_toolbar_and_card_and_reads_only_the_main_path() -> None:
    def step(why: str, zone: str, button: str = "left", phase: str = "weg") -> dict[str, Any]:
        return {
            "target": "t",
            "why": why,
            "button": button,
            "hit": True,
            "zone": zone,
            "phase": phase,
            "widget_at": {"text": why},
        }

    assert bench.place_of([step("ziel", "kopf")], "t")["where"] == "werkzeugleiste"
    menu = bench.place_of([step("menue", "kopf"), step("ziel", "menue")], "t")
    assert menu == {"where": "menue", "path": ["menue", "ziel"], "error": None}
    assert bench.place_of([step("ziel", "karte_links")], "t")["where"] == "karte"
    elsewhere = bench.place_of([step("ziel", "kopf", phase="suche x")], "t")
    assert elsewhere["where"] is None and elsewhere["error"]


def test_the_search_rank_counts_from_one() -> None:
    hits = ["operation:fillet_edges", "operation:drill_hole", "command:file.open"]
    assert bench.search_rank(hits, "operation:drill_hole") == 2
    assert bench.search_rank(hits, "operation:hollow_object") is None


def test_buttons_are_named_as_words() -> None:
    assert bench.button_name("right") == "right"
    assert bench.button_name("") == "left"
    assert bench.with_modifier("left", "ctrl") == "ctrl+left"
    assert bench.with_modifier("left", "") == "left"

    class Mouse:
        name = "RightButton"

    assert bench.button_name(Mouse()) == "right"


def test_the_target_reason_and_the_main_phases_come_from_the_schema() -> None:
    assert bench.TARGET_REASON in WHY
    assert frozenset(WHY) == bench.WAY_REASONS | {bench.TARGET_REASON}
    assert tuple(MAIN_PHASES) == (bench.PATH_PHASE, bench.APPLY_PHASE)


# --- Szenenabdruck, Kennzahlen ---------------------------------------------------------------


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
        return bench.scene_print(
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
    changed = bench.compare_prints(before, applied)
    assert changed["same"] is False and {"ops", "params", "bodies"} <= set(changed["differs"])
    returned = bench.compare_prints(before, undone)
    assert returned == {"same": True, "differs": [], "selection_same": False, "camera_same": True}
    assert bench.compare_prints(before, None)["same"] is None
    assert set(bench.DOCUMENT_PARTS) <= set(before)


def test_the_result_metrics_carry_the_names_the_row_specs_expect(profile: Any) -> None:
    """``volume``, ``extent``, ``bounds.*`` und ``<art>.<wert>`` — so heißen die Erwartungen (L).

    Der Quader 20 × 10 × 5 aus ``create_box``: Volumen und Maß aus der
    Konstruktion, das Bett liegt bei z = 0 (``create_box`` setzt auf).
    """
    project, _history, evaluated = _box_project(profile)
    metrics = bench.result_metrics(evaluated().scene, project.document, None)
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
    metrics = bench.result_metrics(shape, project.document, None)
    assert metrics["bodies_without_mesh"] == ["obj_x"]
    assert metrics["volume"] == pytest.approx(20.0 * 10.0 * 5.0, abs=1e-3)


# --- Zahlen getippt ------------------------------------------------------------------------


def test_numbers_are_typed_with_the_separator_the_field_reads_in_every_language() -> None:
    """Getippt wird mit dem Dezimalzeichen der Sprache — und das ist das, was das Feld liest.

    Das Feld liest über ``QLocale`` (``labels.localised``), der Prüfstand
    schreibt über den Katalog (``i18n.decimal_separator``). Beide müssen in
    jeder Sprache übereinstimmen, sonst tippt der Prüfstand, was das Feld
    ablehnt.
    """
    from PySide6.QtCore import QLocale

    from app.i18n import decimal_separator, set_language
    from app.i18n.catalog import available_languages, install_language

    languages = available_languages()
    assert len(languages) >= 6
    try:
        for language in languages:
            install_language(language)
            set_language(language)
            separator = decimal_separator()
            assert separator == QLocale(language).decimalPoint(), language
            assert bench.typed_number(5.2) == f"5{separator}2"
            assert bench.typed_number(36.0) == "36"
            assert bench.typed_number(12.7, "in") == f"0{separator}5"
            assert bench.typed_number(0.0) == "0"
    finally:
        install_language("de")
        set_language("de")
    assert bench.typed_number(39.6) == "39,6"


# --- Herzschlag, Bildzähler, Tab-Kette, Texte, Fenster ------------------------------------------


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
    assert capture.modal_allowed(["AskDialog", "QDialog"], [])
    assert capture.modal_allowed(["QMessageBox", "QDialog"], ["poll", "confirm_unsaved", "x"])
    assert not capture.modal_allowed(["QMessageBox", "QDialog"], ["poll", "show_error"])
    assert capture.is_question("QMessageBox", ["Speichern", "Verwerfen", "Abbrechen"])
    assert not capture.is_question("QMessageBox", ["OK"])
    assert capture.is_question("AskDialog", ["OK"])
    defined = {
        node.name
        for path in (ROOT / "app" / "ui").rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    assert len(defined) > 1000
    assert defined >= capture.ALLOWED_CALLERS
    assert defined >= capture.ALLOWED_CLASSES - {"QFileDialog"}


# --- Profil, Lizenz, Vorbedingungen ----------------------------------------------------------


def test_the_prepared_profile_is_what_the_application_reads_at_its_start() -> None:
    """Sprache, Thema, Einheit und Drucker kommen aus der Variante, Zuletzt-Liste dazu.

    Die Suite hat die Nutzerordner schon umgebogen (§38); geschrieben wird also
    in das Profil des Tests, gelesen mit ``load_settings`` wie beim Start.
    """
    from app.ui.settings import load_settings

    variant = bench.Variant.of(
        {"language": "en", "theme": "dark", "unit": "in", "preconditions": {"printer": "resin"}}
    )
    second = Path("scenes") / "zweites_projekt.p3d"
    bench.write_profile(variant, recent=[second])
    settings = load_settings()
    assert (settings.language, settings.theme, settings.display_unit) == ("en", "dark", "in")
    assert (settings.printer, settings.material) == bench.PRINTERS["resin"]
    assert settings.first_run_done is True and settings.check_for_updates is False
    assert settings.recent == [str(second)]
    assert settings.ai_disclosure_version == "", "der KI-Hinweis bleibt Teil des Kundenwegs"
    plain = bench.write_profile(bench.Variant())
    assert plain.is_file()
    settings = load_settings()
    assert (settings.language, settings.printer) == ("de", "centauri-carbon-2")


@pytest.mark.parametrize("trial_from", [None, date(2026, 12, 1)])
def test_each_licence_run_of_the_shipped_version_is_set_through_the_suites_seam(
    monkeypatch: pytest.MonkeyPatch, trial_from: date | None
) -> None:
    """Die Läufe sind die Zustände, die die Fassung erreicht (Entscheidung 12.10., Review S1).

    Ohne ``store.TRIAL_FROM`` (Verkaufsversion) ``sale_without_trial``, mit ihm
    ``expired``; dazu ``needs_activation`` und ``licensed``. Jeder ohne private
    Schlüssel über ``activation._cached``, und an dem gebauten Zustand gilt genau
    seine Eigenschaft — auch keine von ``over``. Gesperrt heißt: Die Grenze im
    Datenpfad wirft (``activation.require``), so wie U es erwartet
    (``LICENCE_UNLOCKED``). Der Satz ``lizenz`` liest die Läufe erst jetzt.
    """
    from app.core import activation
    from app.core.activation import store
    from app.core.errors import DeviceActivationRequired, LicenceRequired

    monkeypatch.setattr(activation, "_cached", activation._cached)
    monkeypatch.setattr(store, "DEMO_UNTIL", store.DEMO_UNTIL)
    monkeypatch.setattr(store, "TRIAL_FROM", trial_from)
    runs = licence_states()
    assert ("expired" in runs) is (trial_from is not None)
    assert {entry["licence"] for entry in bench.variant_sets()["lizenz"]} == set(runs)
    for state in runs:
        monkeypatch.setattr(store, "TRIAL_FROM", trial_from)
        cached = bench.apply_licence(state, date(2026, 10, 12))
        assert activation.state() is cached
        holding = {name for name in (*LICENCE_STATES, STARTUP_LICENCE) if getattr(cached, name)}
        assert holding == {state}, (state, holding)
        assert store.DEMO_UNTIL is None
        assert cached.unlocked is LICENCE_UNLOCKED[state]
        if LICENCE_UNLOCKED[state]:
            activation.require(activation.CHANGE)
        else:
            # Ein Kaufcode ohne Gerätefreigabe sperrt mit eigenem Weg hinaus.
            with pytest.raises((LicenceRequired, DeviceActivationRequired)):
                activation.require(activation.CHANGE)
    if trial_from is None:
        with pytest.raises(ValueError, match="TRIAL_FROM"):
            bench.apply_licence("expired", date(2026, 10, 12))


def test_the_expired_demo_is_the_start_case_and_no_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """``over`` ist kein Lauf je Funktion, sondern der Startfall der D12-Zeile (Review S1).

    Der Zustand trägt seinen Stichtag (gestern), und eine Variante mit ihm gibt
    es nur im Satz ``start``.
    """
    from app.core import activation
    from app.core.activation import store

    monkeypatch.setattr(activation, "_cached", activation._cached)
    monkeypatch.setattr(store, "DEMO_UNTIL", store.DEMO_UNTIL)
    cached = bench.apply_licence(STARTUP_LICENCE, date(2026, 10, 12))
    assert cached.over is True and cached.unlocked is False
    assert store.DEMO_UNTIL == cached.deadline == date(2026, 10, 11)
    assert STARTUP_LICENCE not in licence_states()
    with pytest.raises(ValueError, match="Startfall"):
        bench.Variant.of({"licence": STARTUP_LICENCE})
    with pytest.raises(ValueError, match="Startfall"):
        bench.Variant.of({"set": "start", "licence": "licensed"})
    start = bench.Variant.of({"set": "start", "licence": STARTUP_LICENCE})
    assert start.protocol(None, (0, 0))["licence"] == STARTUP_LICENCE
    assert bench.PHASES["start"] == ()


def test_missing_preconditions_go_through_the_seams_and_present_ones_are_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """„fehlt“ setzt die Nahtstellen der Suite; „vorhanden“ wird an der Maschine nachgesehen.

    In der Suite gibt es keinen gefundenen Slicer und kein Modell
    (``tests/conftest.py``) — „vorhanden“ verlangt, steht also ehrlich als
    „fehlt (Maschine)“ im Lauf, statt einen Fall zu behaupten, den es nicht gab.
    """
    from app.core import discover, tools
    from app.core.backends import llm, mesh

    monkeypatch.setattr(discover, "find_program", discover.find_program)
    monkeypatch.setattr(discover, "find_programs", discover.find_programs)
    monkeypatch.setattr(discover, "reachable", discover.reachable)
    monkeypatch.setattr(llm, "backends", llm.backends)
    monkeypatch.setattr(mesh, "reachable", mesh.reachable)
    applied = bench.apply_preconditions(
        {"slicer": "fehlt", "ki": "fehlt", "comfyui": "fehlt", "printer": "resin"}
    )
    assert applied == {"slicer": "fehlt", "ki": "fehlt", "comfyui": "fehlt", "printer": "resin"}
    assert tools.slicer_programs() == ()
    assert tuple(llm.backends()) == ()
    assert mesh.reachable(mesh.DEFAULT_COMFY_URL) is False
    assert bench.apply_preconditions({"slicer": "vorhanden"}) == {"slicer": "fehlt (Maschine)"}


def test_present_ai_and_a_missing_comfyui_are_read_the_way_the_application_reads_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """„KI vorhanden“ liest ``available`` als Eigenschaft (M2), ComfyUI fehlt an beiden Wegen (L1).

    Gegenprobe M2: Ein Backend-Doppel mit ``available`` als Eigenschaft —
    vorher stürzte ``available()`` an einem ``bool`` ab. Gegenprobe L1: Der
    Werkzeugdialog fragt ``discover.reachable``; nach „ComfyUI fehlt“ antwortet
    dort keine ComfyUI-Adresse mehr, jede andere wie vorher.
    """
    from app.core import discover
    from app.core.backends import llm, mesh

    class Backend:
        def __init__(self, ready: bool) -> None:
            self.ready = ready

        @property
        def available(self) -> bool:
            return self.ready

    monkeypatch.setattr(llm, "backends", lambda: (Backend(False), Backend(True)))
    assert bench.apply_preconditions({"ki": "vorhanden"}) == {"ki": "vorhanden"}
    monkeypatch.setattr(llm, "backends", lambda: (Backend(False),))
    assert bench.apply_preconditions({"ki": "vorhanden"}) == {"ki": "fehlt (Maschine)"}

    asked: list[str] = []

    def answers(url: str, seconds: float = 0.0) -> bool:
        asked.append(url)
        return True

    monkeypatch.setattr(discover, "reachable", answers)
    monkeypatch.setattr(mesh, "reachable", mesh.reachable)
    assert bench.apply_preconditions({"comfyui": "fehlt"}) == {"comfyui": "fehlt"}
    assert discover.reachable(mesh.DEFAULT_COMFY_URL) is False
    assert discover.reachable("127.0.0.1:8188") is False
    assert mesh.reachable(mesh.DEFAULT_COMFY_URL) is False
    assert discover.reachable("http://127.0.0.1:11434") is True
    assert asked == ["http://127.0.0.1:11434"]


def test_the_spec_sets_licence_and_preconditions_and_both_states_run() -> None:
    """Die Spezifikation legt Lizenz und Vorbedingungen fest; „fehlt“ und „vorhanden“ laufen beide.

    Die Spezifikation nennt Lizenzzustände mit den Namen von D0-L; der Prüfstand
    übersetzt nichts. Was die Fassung nicht erreicht, ist ein Fehler: das alte
    Wort „demo“, ein deutsches Wort, ``over`` (der Startfall) und der gesperrte
    Zustand, den diese Fassung nicht hat.
    """
    locked = licence_states()[0]
    base, others = bench.spec_variants(
        {"preconditions": {"licence": locked, "slicer": "vorhanden", "printer": "resin"}}
    )
    assert base == {
        "licence": locked,
        "preconditions": {"slicer": "vorhanden", "printer": "resin"},
    }
    assert others == [
        {"preconditions": {"slicer": "fehlt", "printer": "resin"}, "phases": ["main"]}
    ]
    assert bench.spec_variants(None) == ({}, [])
    assert bench.spec_licence("licensed") == "licensed"
    unreachable = next(state for state in LICENCE_STATES if state not in licence_states())
    for word in ("demo", "gekauft", STARTUP_LICENCE, unreachable):
        with pytest.raises(ValueError, match="keinen Lauf"):
            bench.spec_licence(word)


def test_a_variant_takes_only_states_the_bench_can_make() -> None:
    assert bench.Variant.of(None) == bench.Variant()
    for broken in (
        {"licence": "gekauft"},
        {"preconditions": {"slicer": "kaputt"}},
        {"preconditions": {"drucker": "filament"}},
        {"unit": "cm"},
        {"theme": "bunt"},
        {"window_size": "groß"},
        {"scale": 0},
        {"farbe": "rot"},
        {"set": "bunt"},
        {"phases": ["fliegen"]},
        {"set": "lizenz", "phases": ["main"]},
        {"licence": STARTUP_LICENCE},
    ):
        with pytest.raises(ValueError):
            bench.Variant.of(broken)
    variant = bench.Variant.of({"window_size": "1366x728", "scale": 1.5, "phases": ["main"]})
    assert bench.parse_size(variant.window_size) == (1366, 728)
    assert variant.phases == ("main",)
    assert bench.Variant.of(variant.as_dict()) == variant
    sets = bench.variant_sets()
    assert set(bench.PHASES) == {*sets, "start"}
    assert {entry.get("licence") for entry in sets["lizenz"]} == set(licence_states())
    assert {entry.get("window_size") for entry in sets["skalierung"]} >= set(bench.WINDOW_SIZES)
    assert sets["bewegung"] == ({"set": "bewegung", "motion": False},)


# --- Fälle, Wiederaufnahme, Bericht ------------------------------------------------------------

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


def test_function_cases_unfold_rows_variants_and_languages() -> None:
    """Je Zeile und Variante ein Fall, je Sprache und Paket einer; fremde Kennung ist ein Fehler."""
    cases = function_cases(
        ROWS,
        packages=["D4"],
        variant_sets=["basis", "lizenz", "sprachen"],
        languages=("de", "en"),
        first_number=5,
    )
    function = [case for case in cases if case.kind == "function"]
    language = [case for case in cases if case.kind == "language"]
    assert [case.number for case in cases] == list(range(5, 5 + len(cases)))
    # basis: resize_hole einmal, drill_hole zweimal (Slicer vorhanden und fehlt); lizenz: je
    # einer je Lauf der Fassung.
    assert len(function) == 1 + 2 + 2 * len(licence_states())
    slicer = [case.variant["preconditions"] for case in function if case.row == "drill_hole"]
    assert {"slicer": "vorhanden"} in slicer and {"slicer": "fehlt"} in slicer
    assert [(case.row, case.variant["language"]) for case in language] == [
        ("D4", "de"),
        ("D4", "en"),
    ]
    first = function[0]
    assert first.path == "scenes/merkmal.hole.exakt.p3d" and first.variant["set"] == "basis"
    assert {case.variant["licence"] for case in function if case.variant["set"] == "lizenz"} == set(
        licence_states()
    )
    assert function_cases(ROWS, row_ids=["finding.action:place_on_bed"])[0].row == (
        "finding.action:place_on_bed"
    )
    again = function_cases(ROWS, row_ids=["resize_hole"], phases=["escape", "main"])
    assert [case.variant["phases"] for case in again] == [["escape", "main"]]
    with pytest.raises(ValueError, match="Phasen"):
        function_cases(ROWS, row_ids=["resize_hole"], variant_sets=["lizenz"], phases=["main"])
    # Review L5: Phasen gelten nur für Sätze, die sie haben; der Lizenzsatz fällt weg.
    mixed = function_cases(
        ROWS, row_ids=["resize_hole"], variant_sets=["basis", "lizenz"], phases=["main"]
    )
    assert [(case.variant["set"], case.variant["phases"]) for case in mixed] == [
        ("basis", ["main"])
    ]
    # Die Zeile des Startablaufs ist ein Startfall, einmal, im Zustand „Demo abgelaufen“.
    started = function_cases(ROWS, packages=["D12"], variant_sets=["basis", "lizenz", "dunkel"])
    assert [
        (case.kind, case.row, case.variant["set"], case.variant["licence"]) for case in started
    ] == [("start", "startup.expired_demo", "start", STARTUP_LICENCE)]
    with pytest.raises(ValueError, match="keine Zeile"):
        function_cases(ROWS, row_ids=["gibt_es_nicht"])
    with pytest.raises(ValueError, match="Variantensätze"):
        function_cases(ROWS, variant_sets=["basis", "bunt"])


def test_old_cases_stay_file_cases_and_new_ones_keep_their_fields(tmp_path: Path) -> None:
    """Ein ``cases.json`` von RM-184 ohne die neuen Felder liest sich als Dateifälle."""
    write_json(
        tmp_path / "cases.json",
        [
            {
                "number": 1,
                "relative": "a.stl",
                "path": "F:/x/a.stl",
                "suffix": ".stl",
                "bores": False,
            }
        ],
    )
    (old,) = read_cases(tmp_path)
    assert (old.kind, old.row, old.variant) == ("file", "", {})
    new = function_cases(ROWS, row_ids=["resize_hole"])[0]
    write_json(tmp_path / "cases.json", [asdict(new)])
    assert read_cases(tmp_path) == [new]


def test_only_a_broken_language_case_resumes_without_again() -> None:
    """Ein Sprachfall nimmt seine Flächen einzeln wieder auf, andere Fälle nur mit ``--again``."""
    language = Case(1, "D4 [de]", "", "", kind="language", row="D4")
    function = Case(2, "resize_hole [basis]", "", "", kind="function", row="resize_hole")
    assert resumes(language, {"exit_code": 1, "timeout": False})
    assert resumes(language, {"exit_code": 0, "timeout": True})
    assert not resumes(language, {"exit_code": 0, "timeout": False})
    assert not resumes(function, {"exit_code": 1, "timeout": False})


def test_a_run_starts_only_what_is_not_done_and_hands_on_the_screen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wiederaufnahme wie bei RM-184: Fertige Fälle bleiben liegen, ``--again`` fährt alle neu.

    Der Kindprozess ist nachgestellt; geprüft wird, welche Fälle ``run`` startet,
    mit welcher Frist und ob ``--screen`` beim Kind ankommt.
    """
    from tools import file_acceptance

    cases = [
        Case(1, "a.stl", "F:/x/a.stl", ".stl"),
        Case(2, "resize_hole [basis]", "", "", kind="function", row="resize_hole"),
        Case(3, "D4 [de]", "", "", kind="language", row="D4"),
        Case(4, "D4 [en]", "", "", kind="language", row="D4"),
    ]
    write_json(tmp_path / "cases.json", [asdict(case) for case in cases])
    for number, code in ((1, 0), (2, 0), (3, 1), (4, 0)):
        write_json(
            tmp_path / "cases" / f"{number:03d}" / "process.json",
            {"exit_code": code, "timeout": False, "wall_s": 1.0},
        )
    started: list[tuple[str, float, list[str]]] = []

    class Child:
        def __init__(self, command: list[str], **_options: object) -> None:
            self.command = command
            self.pid = 4711

        def wait(self, timeout: float | None = None) -> int:
            number = self.command[self.command.index("--case") + 1]
            started.append((number, float(timeout or 0.0), self.command))
            return 0

    monkeypatch.setattr(file_acceptance.subprocess, "Popen", Child)
    assert file_acceptance.run(tmp_path, 1, 99, False, 600.0, screen="MSI") == 0
    assert [(number, timeout) for number, timeout, _command in started] == [
        ("3", file_acceptance.LANGUAGE_CASE_TIMEOUT)
    ]
    assert started[0][2][-2:] == ["--screen", "MSI"]
    started.clear()
    assert file_acceptance.run(tmp_path, 1, 99, True, 600.0) == 0
    assert [(number, timeout) for number, timeout, _command in started] == [
        ("1", 600.0),
        ("2", file_acceptance.FUNCTION_CASE_TIMEOUT),
        ("3", file_acceptance.LANGUAGE_CASE_TIMEOUT),
        ("4", file_acceptance.LANGUAGE_CASE_TIMEOUT),
    ]
    assert all("--screen" not in command for _number, _timeout, command in started)


def test_the_report_lists_function_cases_beside_the_file_cases(tmp_path: Path) -> None:
    """Der Lauf steht in ``bench.json``, die Messung im Protokoll — die Übersicht liest beide."""
    cases = [
        Case(1, "plate.stl", "F:/x/plate.stl", ".stl"),
        Case(
            2,
            "resize_hole [basis]",
            "scenes/merkmal.hole.exakt.p3d",
            "",
            kind="function",
            row="resize_hole",
            variant={"set": "basis"},
        ),
        Case(3, "D4 [en]", "", "", kind="language", row="D4", variant={"set": "sprachen"}),
    ]
    folder = tmp_path / "cases"
    write_json(folder / "002" / "bench.json", {"stage": "done"})
    write_json(
        folder / "002" / "function.json",
        {"findings": [{"kind": bench.COVERED}], "unmeasured": {"abort": "x"}, "errors": []},
    )
    write_json(folder / "002" / "process.json", {"exit_code": 0, "timeout": False, "wall_s": 41.0})
    write_json(folder / "003" / "bench.json", {"stage": "start", "harness_exception": "Abriss"})
    write_json(folder / "003" / "surfaces" / "resize_hole.json", {"errors": [], "findings": []})
    write_json(folder / "003" / "process.json", {"exit_code": 139, "timeout": False, "wall_s": 9.0})
    data = summary(tmp_path, cases)
    assert (
        data["cases"],
        data["function_cases"],
        data["function_ran"],
        data["function_complete"],
    ) == (1, 2, 2, 1)
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "| 2 | resize_hole [basis] | function | basis | done | 0 | 41.0 | 1 | 1 |" in text
    assert "- 3 D4 [en]: Abriss" in text
    written = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert written["functions"][1]["exit_code"] == 139


# --- Protokoll ---------------------------------------------------------------------------------


def _written_keys() -> set[str]:
    """Die Felder, die ``FunctionFlow`` ins Protokoll schreibt — gelesen am Quelltext."""
    tree = ast.parse(BENCH.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
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
    Dazu die Pflichtfelder aus :func:`function_bench.empty_protocol`.
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
    variant = bench.Variant().protocol({"screen": "MSI"}, (1280, 820))
    protocol = bench.empty_protocol(ROWS[0], variant, {"commit": "abc", "app": "0.6.1"})
    assert set(protocol) == set(PROTOCOL_SCHEMA)
    assert set(protocol["row"]) <= set(PROTOCOL_SCHEMA["row"].keys or ())
    # Z6 je Zeile über alle Fälle (D0-U): jeder Fall trägt seine Fenstergröße
    # und eine Liste der Rollleisten, auch leer — gültig schon im Gerüst.
    assert protocol["variant"]["window_size"] == [1280, 820]
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
            "place": bench.place_of([], "x") | {"error": "kein Weg"},
            "matrix": {
                stage: {"state": "nicht herstellbar", "reason": "x", "effective": None}
                for stage in SELECTION_STAGES
            },
            "licence_runs": {"licensed": {"writes": True, "enabled": True, "reason": ""}},
            "findings": [{"phase": "weg", "kind": bench.COVERED, "target": "x", "detail": "y"}],
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


def test_route_apply_target_and_command_line_come_from_the_row() -> None:
    row = {
        "target": "menu:tree.rename",
        "route": [{"target": "tree.row:obj_1", "button": "left", "modifier": ""}],
        "spec": {"route": [{"target": "tree.row:obj_2", "button": "left", "modifier": "ctrl"}]},
    }
    assert bench.route_of(row) == [
        ("tree.row:obj_1", "left"),
        ("tree.row:obj_2", "ctrl+left"),
        ("menu:tree.rename", "left"),
    ]
    assert bench.route_of({"target": "feature:resize_hole"}) == [("feature:resize_hole", "left")]
    feature_row = {
        "target": "operation:resize_hole",
        "route": [{"target": "tree.row:obj_1.hole_1", "button": "left", "modifier": ""}],
        "spec": {"inputs": {"feature.field:resize_hole.diameter": 8.0}},
    }
    # Eine Merkmalsoperation findet der Kunde an der Auswahl als Handlung, nicht im
    # Kontextmenü: Der Hauptweg führt zu ihrem Kopf, übernommen wird dort.
    assert bench.walk_target(feature_row) == "feature:resize_hole"
    assert bench.route_of(feature_row)[-1] == ("feature:resize_hole", "left")
    assert bench.default_apply_target(feature_row) == "feature.apply"
    dialog_row = {"target": "operation:drill_hole", "spec": {"inputs": {"field:diameter": 5}}}
    assert bench.walk_target(dialog_row) == "operation:drill_hole"
    assert bench.protocol_spec({"inputs": {}, "file": "d04.toml", "package": "D4"}) == {
        "inputs": {}
    }
    assert bench.protocol_spec(None) is None
    assert bench.selected_feature(ROWS[0]) == ("obj_1", "hole_1")
    assert bench.selected_feature(ROWS[1]) is None
    assert bench.default_apply_target({"target": "feature:resize_hole"}) == "feature.apply"
    assert bench.default_apply_target({"target": "edge:fillet_edges"}) == "feature.apply"
    assert bench.default_apply_target({"target": "operation:drill_hole"}) == "dialog.accept"
    assert bench.default_apply_target({"target": "menu:menubar.datei.speichern"}) is None
    assert bench.cli_arguments(
        {
            "op": "drill_hole",
            "in": ["obj_1"],
            "params": {"diameter": 5.2, "axis": "z", "slotted": False},
        }
    ) == ["drill_hole", "--on", "obj_1", "--diameter", "5.2", "--axis", "z", "--no-slotted"]
    assert bench.cli_arguments({"op": "pattern", "params": {"points": [[0, 0]]}}) is None
    named = bench.safe_name("Datei/Speichern unter …")
    assert named.startswith("Datei_Speichern_unter-")
    # Review L4: zwei Kennungen, die sich nur im Zeichen danach unterscheiden.
    assert named != bench.safe_name("Datei/Speichern unter")
    assert bench.bodies_digest({"b": "2", "a": "1"}) == bench.bodies_digest({"a": "1", "b": "2"})


def test_drag_times_stay_raw_and_d0_u_converts_them_once() -> None:
    """Review M3: P schreibt roh, U rechnet einmal um — P's Ausgabe durch U's Urteil.

    Vorher schrieb der Prüfstand ``Messwert × Faktor`` **und** den Faktor; U
    rechnete noch einmal, der Faktor wirkte quadratisch (40 ms hier wären 80 ms).
    """
    from tools.function_judges import _z1
    from tools.function_samples import sample_context, sample_protocol

    protocol = sample_protocol()
    protocol["frames"] = bench.drag_frames([10.0, None, 20.0, None], 2.0)
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


def test_a_drag_counts_only_if_the_view_noticed_the_grip(qt_app: Any) -> None:
    """Review L11: Ein Zug, bei dem die Ansicht keinen Zugwert meldet, fasste keinen Griff.

    Griff und Ansicht sind ein echtes Widget. Meldet es bei den Bewegungen
    nichts, ist Z1 ungemessen — vorher standen auch dann Bildzeiten im
    Protokoll. Meldet es ``transformDragged`` wie die Ansicht, stehen die
    rohen Zeiten da, und die Bewegungen kamen im Takt einer Hand
    (``DRAG_TICK_S``), nicht so schnell die Schleife kann.
    """
    from types import SimpleNamespace

    from PySide6.QtCore import QPoint, QRect, QSize, Signal
    from PySide6.QtWidgets import QApplication, QWidget

    class View(QWidget):
        transformDragged = Signal(object)  # noqa: N815 - Name des Signals der Ansicht

        def __init__(self, answers: bool) -> None:
            super().__init__()
            self.answers = answers
            self.setMouseTracking(True)

        def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802 - Qt
            if self.answers:
                self.transformDragged.emit(event.position())

    def drag(answers: bool) -> tuple[dict[str, Any], list[float]]:
        view = View(answers)
        view.resize(300, 200)
        view.show()
        QApplication.processEvents()
        rect = QRect(view.mapToGlobal(QPoint(40, 90)), QSize(20, 20))
        moves: list[float] = []

        def latencies(events: list[float]) -> list[float | None]:
            moves.extend(events)
            return [5.0 for _ in events]

        flow = object.__new__(bench.FunctionFlow)
        flow.row = {"id": "zug", "target": "handle:move.x"}
        flow.spec = {"criteria": ["Z1"]}
        flow.data = {"unmeasured": {}}
        flow.frames_wrapped = True
        flow.frames = SimpleNamespace(latencies=latencies)
        flow.reference_factor = 1.5
        flow.application = QApplication.instance()
        flow.window = SimpleNamespace(viewport=view)
        flow.ports = SimpleNamespace(
            next_click=lambda target: SimpleNamespace(rect=rect, why="ziel", target=target),
            centre=lambda area: area.center(),
            widget_under=lambda point: view,
            covers=lambda click, hit: True,
        )
        flow.path_steps = lambda: [bench.Step("hin", lambda machine: None)]  # type: ignore[method-assign]
        flow.run_steps = lambda label, steps: all(  # type: ignore[method-assign]
            step.act(None) or True for step in steps
        )
        try:
            flow.phase_drag()
        finally:
            view.close()
            view.deleteLater()
            QApplication.processEvents()
        return flow.data, moves

    data, _moves = drag(answers=False)
    assert "frames" not in data
    assert data["unmeasured"]["frames.raw_drag_ms"] == "der Zug fasste keinen Griff"

    data, moves = drag(answers=True)
    assert data["frames"] == {"raw_drag_ms": [5.0] * bench.DRAG_MOVES, "reference_factor": 1.5}
    assert "frames.raw_drag_ms" not in data["unmeasured"]
    gaps = [later - earlier for earlier, later in itertools.pairwise(moves)]
    assert len(moves) == bench.DRAG_MOVES and min(gaps) >= bench.DRAG_TICK_S * 0.9


def test_the_surface_of_a_surface_set_counts_as_the_rows_own_window() -> None:
    """Review L13: In Zoll, Skalierung, Dunkel und Bewegung ist die Fläche der Zeile erlaubt.

    Ihr modaler Dialog ist die Funktion selbst. Vorher trug ``phase_surface``
    seine Klasse nicht in ``watch.own`` ein, und der Dialog stand als nicht
    erlaubtes Fenster im Protokoll. Ein fremder Dialog bleibt nicht erlaubt.
    """

    class ParameterDialog:
        """Attrappe der Bedienfläche, die die Zeile öffnet."""

    flow = object.__new__(bench.FunctionFlow)
    flow.variant = bench.Variant.of({"set": "zoll", "unit": "in"})
    flow.watch = capture.ModalWatch(0.0)
    for name in ("ParameterDialog", "FremderDialog"):
        flow.watch.modals.append(
            {"class": name, "title": name, "allowed": False, "question": False}
        )
    pictures: list[str] = []
    flow.surface = ParameterDialog  # type: ignore[method-assign]
    flow.capture_surface = lambda root: None  # type: ignore[method-assign]
    flow.picture = pictures.append  # type: ignore[method-assign]
    flow.path_steps = list  # type: ignore[method-assign]
    flow.still_step = lambda name, root: bench.Step(name, lambda machine: None)  # type: ignore[method-assign]
    flow.run_steps = lambda label, steps: all(  # type: ignore[method-assign]
        step.act(None) or True for step in steps
    )
    flow.phase_surface()
    allowed = {entry["class"]: entry["allowed"] for entry in flow.watch.modal_entries()}
    assert allowed == {"ParameterDialog": True, "FremderDialog": False}
    assert pictures == ["flaeche-zoll"]


def test_the_aborted_computation_lasts_as_long_as_the_main_way() -> None:
    """Review M4: ``abort.eval_s`` ist die Rechendauer aus dem Hauptweg, nicht die Ladezeit."""
    data = bench.empty_protocol(ROWS[0], bench.Variant().protocol(None, (0, 0)), {})
    data["scene"] = {"key": "langsam_2s", "triangles": 1, "build_s": None, "eval_s": 0.4}
    data["timing"] = {"total_s": 3.2}
    assert bench.abort_entry(data, 0.9, True) == {
        "eval_s": 3.2,
        "cancel_shown_s": 0.9,
        "clicked": True,
    }
    data["timing"] = None
    assert bench.abort_entry(data, None, False)["eval_s"] is None
    assert "abort.eval_s" in data["unmeasured"]


def test_every_phase_starts_at_its_scene_and_runs_only_if_it_got_there() -> None:
    """Review M5: Vor jeder Phase ein Rücksetzen, auch nach einer Ausnahme; misslingt es, ruht sie.

    Der Fall ist ohne Fenster nachgestellt: ``reset`` und die Phasen sind
    Attrappen, ``run`` ist der echte Ablauf.
    """
    calls: list[str] = []
    answers = iter([True, False, True])
    flow = object.__new__(bench.FunctionFlow)
    flow.variant = bench.Variant.of({"phases": ["escape", "main", "revise"]})
    flow.bench = {}
    flow.data = {"errors": []}
    flow.persist = lambda: None
    flow.finish = lambda: calls.append("finish")  # type: ignore[method-assign]

    def reset() -> bool:
        calls.append("reset")
        return next(answers)

    def broken() -> None:
        calls.append("escape")
        raise RuntimeError("Phase stürzt")

    flow.reset = reset  # type: ignore[method-assign]
    flow.phase_escape = broken  # type: ignore[method-assign]
    flow.phase_main = lambda: calls.append("main")  # type: ignore[method-assign]
    flow.phase_revise = lambda: calls.append("revise")  # type: ignore[method-assign]
    flow.run()
    assert calls == ["reset", "escape", "reset", "reset", "revise", "finish"]
    assert any("Phase stürzt" in error for error in flow.data["errors"])
    assert any(error.startswith("main: Startszene") for error in flow.data["errors"])


def test_each_case_opens_its_own_copy_of_a_shared_scene(tmp_path: Path) -> None:
    """Review M6: Die gemeinsame Szene unter ``<out>/scenes`` wird nie selbst geöffnet."""
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    (scenes / "quader.exakt.p3d").write_bytes(b"szene")
    folder = tmp_path / "cases" / "007"
    copy = bench.case_scene(folder, scenes, "quader.exakt")
    assert copy == folder / "scenes" / "quader.exakt.p3d" and copy.read_bytes() == b"szene"
    copy.write_bytes(b"geaendert")
    assert bench.case_scene(folder, scenes, "quader.exakt") == copy
    assert copy.read_bytes() == b"geaendert", "einmal angelegt, dann die eigene"
    assert (scenes / "quader.exakt.p3d").read_bytes() == b"szene"
    assert bench.case_scene(folder, scenes, "gibt_es_nicht") is None


def test_a_language_case_skips_the_surface_its_last_run_died_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review M14: Eine Fläche, an der der Prozess starb, kommt im nächsten Lauf nicht wieder dran.

    Vor jeder Fläche steht ein Anfangsvermerk in ``bench.json``; ein Vermerk ohne
    Ergebnis heißt Absturz. Die Fläche bekommt ein Protokoll mit dem Fehler,
    der Rest des Pakets läuft weiter.
    """
    from types import SimpleNamespace

    monkeypatch.setattr(bench, "place_window", lambda application, window, variant: {})
    state: dict[str, Any] = {"surface_started": "D4.abgestuerzt"}
    window = SimpleNamespace(width=lambda: 800, height=lambda: 600)
    rows = [{"id": "D4.abgestuerzt", "kind": "operation", "package": "D4"}]
    flow = bench.LanguageFlow(
        None,
        window,
        tmp_path,
        state,
        lambda: None,
        rows,
        bench.Variant.of({"set": "sprachen"}),
        tmp_path / "scenes",
        {"commit": "", "app": ""},
    )
    flow.run()
    (written,) = (tmp_path / "surfaces").glob("*.json")
    protocol = json.loads(written.read_text(encoding="utf-8"))
    assert protocol["errors"] == ["Die Fläche brach im vorigen Lauf den Prozess ab"]
    assert validate_protocol(protocol) == []
    assert state["surfaces_done"] == ["D4.abgestuerzt"] and state["surface_started"] is None


def test_a_failed_preparation_lands_in_the_case_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review L8: Scheitert Lizenz oder Vorbedingung, steht der Grund in ``bench.json``.

    Vorher standen Profil, Lizenz, Vorbedingungen und Fensterbau vor dem
    ``try`` — ``bench.json`` blieb auf ``start``, die Übersicht nannte keinen Grund.
    """
    from tools import file_acceptance

    monkeypatch.setattr(file_acceptance, "version_info", lambda: {"commit": "", "app": ""})

    def refuses(state: str, today: Any = None) -> Any:
        raise RuntimeError("Lizenz ließ sich nicht setzen")

    monkeypatch.setattr(bench, "apply_licence", refuses)
    out = tmp_path / "lauf"
    write_json(out / "rows.json", [ROWS[0]])
    case = function_cases(ROWS, row_ids=["resize_hole"])[0]
    folder = out / "cases" / "001"
    folder.mkdir(parents=True)
    code = file_acceptance.function_child(out, case, folder, "")
    state = json.loads((folder / "bench.json").read_text(encoding="utf-8"))
    assert code == 1 and state["stage"] == "start" and state["shutdown_complete"] is True
    assert "Lizenz ließ sich nicht setzen" in state["harness_exception"]


# --- Wächter: keine Abkürzung, kein eigener Einstieg ---------------------------------------------


def test_bench_captures_and_window_flow_go_through_input_events_only() -> None:
    """Kein ``click``, ``set_value*``, ``emit``, ``session.apply``, ``trigger``, ``select_*``.

    Dazu ``action_undo``/``action_redo``. Geprüft an den drei Orten, die
    Kundenhandlungen ausführen: Prüfstand, Aufnahmen und der Dateiweg
    ``WindowFlow`` (Plan D0 B5, Konzept §12). Dazu die Gegenprobe an einem
    Quelltext mit jeder verbotenen Form — der Wächter muss jede finden.
    """
    assert bench.forbidden_calls(BENCH.read_text(encoding="utf-8")) == []
    assert bench.forbidden_calls(CAPTURE.read_text(encoding="utf-8")) == []
    flow = bench.forbidden_calls(ACCEPTANCE.read_text(encoding="utf-8"), within_class="WindowFlow")
    assert flow == []
    broken = "\n".join(
        [
            "class WindowFlow:",
            "    def run(self):",
            "        self.button.click()",
            "        self.spin.set_value_mm(3.0)",
            "        self.spin.setValue(3.0)",
            "        self.window.valueChanged.emit(1)",
            "        self.session.apply('x', [])",
            "        self.window.session.apply('y', [])",
            "        self.action.trigger()",
            "        self.tree.select_feature('obj_1', 'hole_1')",
            "        self.window.action_undo()",
            "        self.window.action_redo()",
            "        self.tabs.setCurrentIndex(1)",
            "        self.box.setChecked(True)",
            "        self.button.animateClick()",
            "        self.history.apply('erlaubt', [])",
            "        QTest.mouseClick(widget, button)",
        ]
    )
    found = bench.forbidden_calls(broken, within_class="WindowFlow")
    assert [line for line, _call in found] == list(range(3, 16))
    assert "self.history.apply" not in {call for _line, call in found}
    # Review M8: die vierzehn Umwege der Durchsicht — jeder muss gefunden werden.
    detours = "\n".join(
        [
            "class WindowFlow:",
            "    def run(self):",
            "        getattr(self.button, 'click')()",
            "        press = self.button.click",
            "        QMetaObject.invokeMethod(self.button, 'click')",
            "        self.window._show_start_screen(False)",
            "        approval = getattr(self.window, '_preview_approval')",
            "        self.window.feature_panel._apply.released.connect(print)",
            "        guide_targets.area_for(self.window, 'feature.apply')",
            "        self.dialog.accept()",
            "        self.edit.setText('5')",
            "        self.session.start_new('p', 'm')",
            "        self.window.run_operation(spec)",
            "        self.list.setCurrentRow(2)",
            "        self.box.toggle()",
            "        self.dialog.done(0)",
            "        self.dialog.reject()",
            "        self.row.setSelected(True)",
            "        self.field.setFocus()",
            "        if machine.done or self._answering:",
            "            activation._cached = cached",
            "            sys._getframe(1)",
            "        getattr(view, 'renderer', None)",
        ]
    )
    found = bench.forbidden_calls(detours, within_class="WindowFlow")
    lines = sorted({line for line, _call in found})
    assert lines == list(range(3, 20)), found
    with pytest.raises(LookupError):
        bench.forbidden_calls("x = 1\n", within_class="WindowFlow")


def test_the_bench_has_no_entry_of_its_own() -> None:
    """``function_bench`` und ``function_capture`` laufen nur unter ``file_acceptance``.

    Kein ``if __name__ == "__main__"``, kein ``argparse`` — sonst wäre es das
    dritte Fensterwerkzeug (Konzept Funktionsdurchgang §12). Gegenprobe:
    ``file_acceptance`` hat beides.
    """

    def entries(path: Path) -> tuple[bool, bool]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        main = any(
            isinstance(node, ast.If) and "__main__" in ast.unparse(node.test) for node in tree.body
        )
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in (
                node.names if isinstance(node, ast.Import) else [ast.alias(node.module or "")]
            )
        }
        return main, "argparse" in imports

    assert entries(BENCH) == (False, False)
    assert entries(CAPTURE) == (False, False)
    assert entries(ACCEPTANCE) == (True, True)


# --- Am Fenster (Fenster-CI) ----------------------------------------------------------------

#: Die Probezeile der Merkmalshandlungen (Plan D0, Abschnitt 1.2, D4).
PROBE_ROW = "resize_hole"


def _probe_row(scenes: Path) -> dict[str, Any]:
    """Die Zeile ``resize_hole`` aus der erzeugten Liste, Startszenen wie im Inventar."""
    from tools import function_list

    rows = {row.id: asdict(row) for row in function_list.rows()}
    function_list.save_scenes(scenes)
    return rows[PROBE_ROW]


def _assert_the_main_way(data: dict[str, Any]) -> None:
    """Escape verwirft, Rückgängig kehrt zurück, Wiederholen bringt das Übernommene zurück."""
    assert not data["errors"], data["errors"]
    assert not data["findings"], data["findings"]
    states = data["states"]
    assert bench.compare_prints(states["before"], states["escape"])["same"] is True
    assert bench.compare_prints(states["before"], states["applied"])["same"] is False
    assert bench.compare_prints(states["before"], states["undo"])["same"] is True
    assert bench.compare_prints(states["applied"], states["redo"])["same"] is True
    main = [step for step in data["steps"] if step.get("phase") in MAIN_PHASES]
    assert any(step.get("why") == bench.TARGET_REASON and step.get("hit") for step in main)
    assert any(step.get("typed") for step in main), "keine Zahl getippt"
    assert data["place"]["error"] is None and data["place"]["where"] == "karte"
    assert data["preview"] is not None and data["preview"]["bodies"]
    assert data["timing"]["main_gap_ms"] is not None and data["timing"]["total_s"] is not None
    assert data["result"]["metrics"]["hole.diameter"] == pytest.approx(8.0, abs=0.01)
    assert validate_protocol(data) == []


def test_the_probe_row_runs_through_input_events_in_the_window(window: Any, tmp_path: Path) -> None:
    """Die Zeile ``resize_hole`` im Prozess der Suite: Auswahl, Tippen, Vorschau, Tasten.

    Offscreen, Phasen ``escape`` und ``main`` — dieselben, mit denen eine Zeile
    nach einem Fix nachgeprüft wird. Jeder Klick ging über ``next_click`` mit
    Probe; kein Fund, kein Fehler, und das Protokoll ist gegen U's Schema gültig.
    """
    from PySide6.QtWidgets import QApplication

    scenes = tmp_path / "scenes"
    row = _probe_row(scenes)
    variant = bench.Variant.of({"phases": ["escape", "main"]})
    data = bench.empty_protocol(row, variant.protocol(None, (0, 0)), {"commit": "", "app": ""})
    folder = tmp_path / "cases" / "001"
    folder.mkdir(parents=True)
    flow = bench.FunctionFlow(
        QApplication.instance(),
        window,
        folder,
        data,
        lambda: None,
        row,
        variant,
        scenes,
        out=tmp_path,
    )
    flow.prepare()
    flow.run()
    _assert_the_main_way(data)


@pytest.mark.windowed
def test_the_probe_row_runs_in_its_own_process_from_inventory_to_report(tmp_path: Path) -> None:
    """Der ganze Weg eines Funktionsfalls: Inventar, eigener Prozess mit Profil, Protokoll, Bericht.

    Wie ``test_file_acceptance`` für den Dateiweg: Der Prozess baut die
    Anwendung wie ``main``, mit vorbereitetem Profil, Lizenz über die
    Nahtstelle und ohne Systemdialoge; die Menüleiste zählt ein Kindprozess.
    """
    import os
    import subprocess
    import sys

    out = tmp_path / "abnahme"
    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"}
    for arguments in (
        [
            "inventory",
            "--functions",
            "--rows",
            PROBE_ROW,
            "--phases",
            "escape,main",
            "--out",
            str(out),
        ],
        ["run", "--out", str(out), "--timeout", "900"],
    ):
        finished = subprocess.run(
            [sys.executable, str(ACCEPTANCE), *arguments],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1200,
            check=False,
        )
        assert finished.returncode == 0, (finished.stdout, finished.stderr)
    state = json.loads((out / "cases" / "001" / "bench.json").read_text(encoding="utf-8"))
    assert state["stage"] == "done" and state["shutdown_complete"] is True
    protocol = json.loads((out / "cases" / "001" / "function.json").read_text(encoding="utf-8"))
    assert validate_protocol(protocol) == []
    variant = protocol["variant"]
    assert (variant["licence"], variant["language"], variant["phases"]) == (
        "licensed",
        "de",
        ["escape", "main"],
    )
    assert protocol["row"]["id"] == PROBE_ROW and protocol["scene"]["key"]
    # Ein Referenzfaktor je Lauf (Bauplan §31): ``run`` misst ihn, der Fall
    # schreibt genau diesen an die Stelle, an der D0-U ihn liest.
    factor = json.loads((out / capture.REFERENCE_FILE).read_text(encoding="utf-8"))
    from tools.function_checks import REFERENCE_FACTOR_AT

    section, key = REFERENCE_FACTOR_AT
    assert protocol[section][key] == factor["reference_factor"] > 0
    # Der Hauptweg ist geprobt: Jeder Klick steht mit Treffer oder Fund da. Ob
    # die Anwendung ihn freigibt, ist ein Befund über sie, nicht über den
    # Prüfstand — ein Fund steht dann vollständig in ``findings``.
    main = [step for step in protocol["steps"] if step["phase"] in MAIN_PHASES]
    assert main and all("hit" in step or "finding" in step for step in main if step.get("why"))
    assert protocol["errors"] == [], protocol["errors"]
    # Review L9: streng wie im Prozess — ein falsches „verdeckt“ hielte den Fall
    # sonst grün. Die Probe kennt seit der Fixrunde den Empfänger jedes Klicks.
    assert protocol["findings"] == [], protocol["findings"]
    _assert_the_main_way(protocol)
    from tools import function_list

    menu = function_list.read_menubar(out / "menubar.json")
    assert len(menu) > 30 and all(entry.object_name.startswith("menubar.") for entry in menu)
    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert (report["function_cases"], report["function_complete"]) == (1, 1)


def test_the_probe_finds_a_list_or_the_view_over_a_real_target(window: Any) -> None:
    """Review S2 an echten Widgets: Liste oder 3D-Ansicht über dem Ziel ergeben „verdeckt“.

    Ein Behälter zählt nur, wenn er der Behälter **dieses** Ziels ist. Ziel ist
    das Suchfeld des Fensters (``search``). Kontrollfall: frei, getroffen. Eine
    ``QListWidget`` darüber — vorher hielt die Probe ihre Fläche für „eine
    Liste, also ein Behälter“. Die Ansicht an der Stelle des Ziels — vorher
    galt ``window.viewport`` für jedes Ziel als Behälter. Die Ansicht als
    eigenes Ziel (``viewport``) bleibt getroffen.
    """
    from types import SimpleNamespace

    from PySide6.QtCore import QPoint, QRect, QSize, Qt
    from PySide6.QtWidgets import QApplication, QListWidget

    from app.ui import guide_targets

    def settle() -> None:
        for _ in range(20):
            QApplication.processEvents()

    def global_rect(widget: Any) -> QRect:
        return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())

    def click(rect: QRect, target: str) -> Any:
        return SimpleNamespace(
            rect=rect, why="ziel", target=target, button=Qt.MouseButton.LeftButton, direction=0
        )

    window.resize(1280, 820)
    window.show()
    settle()
    ports = bench.QtPorts(window, 0.0)
    # Was gerade dasteht: der Startbildschirm mit *Neues Projekt* oder das Suchfeld.
    name, field = next(
        (name, widget)
        for name in ("start.new", "search")
        if (widget := guide_targets.widget_for(window, name)).isVisible()
    )
    rect = global_rect(field)
    free = ports.widget_under(rect.center())
    assert ports.covers(click(rect, name), free), "Kontrollfall: das freie Ziel"

    cover = QListWidget(window)
    cover.addItem("darüber")
    cover.setGeometry(
        QRect(window.mapFromGlobal(rect.topLeft()) - QPoint(10, 10), rect.size() + QSize(20, 20))
    )
    cover.raise_()
    cover.show()
    settle()
    try:
        hit = ports.widget_under(rect.center())
        assert hit is cover or cover.isAncestorOf(hit), hit
        assert not ports.covers(click(rect, name), hit), "Liste über dem Ziel"
    finally:
        cover.hide()
        cover.deleteLater()
        settle()

    if window.stack.currentWidget() is window.start_screen:
        # Die Ansicht steht erst mit einem Projekt da — *Neues Projekt*, geklickt.
        from PySide6.QtTest import QTest

        start = guide_targets.widget_for(window, "start.new")
        QTest.mouseClick(start, Qt.MouseButton.LeftButton)
        for _ in range(200):
            settle()
            if window.stack.currentWidget() is not window.start_screen:
                break
    view = window.viewport
    centre = view.mapToGlobal(view.rect().center())
    spot = QRect(centre - QPoint(50, 10), QSize(100, 20))
    hit = ports.widget_under(spot.center())
    assert hit is view or view.isAncestorOf(hit), hit
    assert not ports.covers(click(spot, name), hit), "die Ansicht an der Stelle des Ziels"
    assert ports.covers(click(spot, "viewport"), hit), "die Ansicht als eigenes Ziel"


@pytest.fixture
def box_window(qt_app: Any) -> Any:
    """Ein gezeigtes Fenster mit einem Quader samt Bohrung, ohne Startbildschirm.

    Gebaut wie ``prepared_window`` von D0-W: Die Attrappe des Renderers gibt der
    Ansicht eine Projektion. Das ist Vorbereitung, nicht der geprüfte Weg.
    """
    from PySide6.QtWidgets import QMenu

    from app.core.scene.history import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tests.render_fakes import RecordingRenderer

    window = MainWindow(Session(), UiSettings())
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.resize(1400, 900)
    window.show()
    window._show_start_screen(False)
    assert window.session.apply(
        "Quader mit Bohrung",
        [
            OperationDraft(op="create_box"),
            OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 12.0}),
        ],
    )
    assert window.session.wait_for_idle(60_000)
    _settle(qt_app)
    try:
        yield window
    finally:
        for menu in [*window.findChildren(QMenu), *qt_app.topLevelWidgets()]:
            if isinstance(menu, QMenu) and menu.isVisible():
                menu.hide()
        window.hide()
        window.release()
        window.viewport.renderer = None


def _settle(qt_app: Any, rounds: int = 20) -> None:
    for _ in range(rounds):
        qt_app.processEvents()


def _walk_to(qt_app: Any, ports: Any, name: str) -> Any:
    """Die Wegklicks zu ``name`` über ``QtPorts.press``, jeder mit Probe; der Zielklick nicht.

    Gibt den Zielklick und den Treffer der Probe an seiner Mitte zurück.
    """
    for _step in range(6):
        click = ports.next_click(name)
        point = ports.centre(click.rect)
        hit = ports.widget_under(point)
        if click.why == bench.TARGET_REASON:
            return click, hit
        assert hit is not None and ports.covers(click, hit), (name, click.why, hit)
        ports.press(hit, point, "left")
        _settle(qt_app)
    raise AssertionError(f"{name}: kein Ziel nach sechs Wegklicks")


def test_an_operation_that_stands_only_in_the_menu_is_its_menu_line(
    box_window: Any, qt_app: Any
) -> None:
    """Review N1: Eine Operation ohne Kartenknopf steht als Zeile im offenen Menü.

    Der Weg geht über Menütitel und Untermenü der Leiste; am Ziel liegt unter der
    Mitte das Menü mit genau dieser Zeile — gedeckt. Vorher galt dort „verdeckt“,
    denn die Operation hat kein eigenes Widget. Die Ansicht an derselben Stelle
    bleibt verdeckt.
    """
    from PySide6.QtWidgets import QMenu

    ports = bench.QtPorts(box_window, 0.0)
    name = next(
        f"operation:{op}"
        for op in ("field_cut", "inlay_text", "label_text")
        if (button := box_window.selection_operations.button_for(op)) is None
        or not button.isVisible()
    )
    click, hit = _walk_to(qt_app, ports, name)
    assert isinstance(hit, QMenu), hit
    assert ports.covers(click, hit), name
    assert not ports.covers(click, box_window.viewport), "die Ansicht ist nicht die Menüzeile"


def test_an_operation_found_by_the_search_is_its_row_in_the_hits(
    box_window: Any, qt_app: Any
) -> None:
    """Review N1: Ein Suchtreffer einer Operation ist ihre Zeile in der Trefferliste.

    Vorher nahm die Probe den Kartenknopf oder ein Rechteck und meldete
    „verdeckt“. Gedeckt ist nur die Zeile **dieser** Operation: Derselbe Ort für
    einen anderen Treffer ist es nicht.
    """
    from app.ui import guide_targets

    box_window.right.setCurrentIndex(0)
    box_window.selection_operations.search.setText("e")
    _settle(qt_app)
    ports = bench.QtPorts(box_window, 0.0)
    found = [hit for hit in guide_targets.search_hits(box_window) if hit.startswith("operation:")]
    assert len(found) >= 2, found
    name, other = found[0], found[1]
    click, hit = _walk_to(qt_app, ports, name)
    hits = box_window.selection_operations.hits
    assert hit is hits or hits.isAncestorOf(hit), hit
    assert ports.covers(click, hit), name
    elsewhere = replace(click, target=other)
    assert not ports.covers(elsewhere, hit), "die Zeile einer anderen Operation"
    box_window.selection_operations.search.setText("")


def test_a_part_is_its_tile_in_the_open_catalog(box_window: Any, qt_app: Any) -> None:
    """Review N1: Ein Baustein (``part:``) ist seine Kachel in der Liste des Katalogs.

    Vorher warf ``widget_for`` für ``part:``, die Probe nahm ein Rechteck und
    meldete an jeder Kachel „verdeckt“. Die Ansicht des Fensters unter dem
    Katalog ist es nicht.
    """
    from PySide6.QtCore import Qt

    from app.ui.catalog import PartCatalog

    catalog = PartCatalog(box_window)
    catalog.setModal(True)
    catalog.show()
    _settle(qt_app)
    try:
        # Überschriften der Gruppen tragen keinen Namen, nur die Kacheln.
        names = [
            str(named)
            for row in range(catalog.list.count())
            if (named := catalog.list.item(row).data(Qt.ItemDataRole.UserRole))
        ]
        assert names, "der Katalog zeigt keine Kachel"
        ports = bench.QtPorts(box_window, 0.0)
        click, hit = _walk_to(qt_app, ports, f"part:{names[0]}")
        assert hit is catalog.list or catalog.list.isAncestorOf(hit), hit
        assert ports.covers(click, hit)
        assert not ports.covers(click, box_window.viewport), "die Ansicht unter dem Katalog"
    finally:
        catalog.hide()
        catalog.deleteLater()
        _settle(qt_app)


def test_a_bar_over_the_view_is_its_own_widget_not_the_view(box_window: Any, qt_app: Any) -> None:
    """Review N1: ``handle:bar.*`` ist die Leiste in der Werkzeugzeile, nicht die Ansicht.

    Das Werkzeug *Schnitt* wird per Klick geöffnet; dann steht die Schnittleiste.
    Vorher nahm die Probe für jeden ``handle:`` die Ansicht und meldete an jeder
    der sieben Leisten „verdeckt“. Ein Griff im Bild bleibt bei der Ansicht.
    """
    ports = bench.QtPorts(box_window, 0.0)
    click, hit = _walk_to(qt_app, ports, "tool:section")
    ports.press(hit, ports.centre(click.rect), "left")
    _settle(qt_app, 60)
    bar = box_window.section_bar
    assert bar.isVisible()
    click, hit = _walk_to(qt_app, ports, "handle:bar.section")
    assert hit is bar or bar.isAncestorOf(hit), hit
    assert not box_window.viewport.isAncestorOf(hit)
    assert ports.covers(click, hit)
    assert not ports.covers(click, box_window.viewport), "die Ansicht ist nicht die Leiste"


def test_a_scroll_click_covers_its_scroll_area_and_not_a_list_over_it(qt_app: Any) -> None:
    """Rollen nennt bei D0-W die Sichtfläche, ganz oder ihren sichtbaren Teil.

    Ziel ist die Rollfläche selbst: Die Probe an der Mitte trifft ihre
    Sichtfläche — gedeckt, ob der Klick die ganze Sichtfläche oder nur ihren
    sichtbaren Teil nennt. Eine Liste darüber ist auch eine Rollfläche, aber
    nicht die mit diesem Rechteck: verdeckt.
    """
    from types import SimpleNamespace

    from PySide6.QtCore import QPoint, QRect, QSize, Qt
    from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QScrollArea, QWidget

    def settle() -> None:
        for _ in range(20):
            QApplication.processEvents()

    root = QWidget()
    root.resize(400, 300)
    area = QScrollArea(root)
    # Unten ragt die Rollfläche aus dem Fenster: Ihr sichtbarer Teil ist kleiner.
    area.setGeometry(20, 20, 300, 400)
    inner = QLabel("lang")
    inner.setMinimumSize(280, 900)
    area.setWidget(inner)
    root.show()
    settle()
    try:
        ports = bench.QtPorts(None, 0.0)
        viewport = area.viewport()
        whole = QRect(viewport.mapToGlobal(QPoint(0, 0)), viewport.size())
        shown = bench._shown(viewport)
        assert shown != whole and whole.contains(shown), (shown, whole)

        def roll(rect: QRect) -> Any:
            return SimpleNamespace(
                rect=rect,
                why="rollen",
                target="param.x",
                button=Qt.MouseButton.NoButton,
                direction=1,
            )

        hit = ports.widget_under(whole.center())
        assert hit is viewport or viewport.isAncestorOf(hit), hit
        assert ports.covers(roll(whole), hit), "die ganze Sichtfläche"
        assert ports.covers(roll(shown), hit), "ihr sichtbarer Teil"

        cover = QListWidget(root)
        cover.addItem("darüber")
        cover.setGeometry(QRect(root.mapFromGlobal(whole.center()) - QPoint(40, 20), QSize(80, 40)))
        cover.raise_()
        cover.show()
        settle()
        hit = ports.widget_under(whole.center())
        assert hit is cover or cover.isAncestorOf(hit), hit
        assert not ports.covers(roll(whole), hit), "eine Liste über der Rollfläche"
    finally:
        root.close()
        root.deleteLater()
        settle()


def test_text_needs_count_box_symbol_padding_rich_text_and_list_cells(qt_app: Any) -> None:
    """Review M12 und L3 an echten Widgets.

    Je Widget genau so breit wie sein Text: Ein Haken braucht sein Kästchen, ein
    Knopf mit Symbol Symbol und Polsterung — beide abgeschnitten; der Kontrollfall
    ``QLabel`` passt genau. Rich Text zählt mit seinem sichtbaren Text, eine
    schmale Listenzelle ist abgeschnitten. Ein Symbolknopf trägt die Farbe seines
    Symbols, und „groß“ beginnt bei 18 pt (fett 14 pt).
    """
    from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QLabel,
        QListWidget,
        QPushButton,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )

    root = QWidget()
    root.resize(600, 500)
    layout = QVBoxLayout(root)
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#ff0000"))
    label = QLabel("Durchmesser ändern", root)
    box = QCheckBox("Durchgehend bohren", root)
    button = QPushButton(QIcon(pixmap), "Mit Symbol übernehmen", root)
    rich = QLabel("<b>Fett</b> und <i>schräg</i>", root)
    listing = QListWidget(root)
    listing.addItem("Ein sehr langer Eintrag, der in keine schmale Liste passt")
    symbol = QToolButton(root)
    symbol.setIcon(QIcon(pixmap))
    for widget in (label, box, button, rich, listing, symbol):
        layout.addWidget(widget)
    root.show()
    QApplication.processEvents()
    for widget in (label, box, button):
        text_px = widget.fontMetrics().horizontalAdvance(widget.text().replace("&", ""))
        widget.setFixedWidth(text_px + (widget.width() - widget.contentsRect().width()))
    listing.setFixedWidth(120)
    QApplication.processEvents()
    texts = {entry["text"]: entry for entry in capture.text_entries(root)}
    assert texts["Durchmesser ändern"]["cut"] is False, "Kontrollfall: das Etikett passt"
    assert texts["Durchgehend bohren"]["cut"] is True, "das Kästchen braucht Platz"
    assert texts["Mit Symbol übernehmen"]["cut"] is True, "Symbol und Polsterung brauchen Platz"
    assert "Fett und schräg" in texts, "Rich Text zählt mit seinem sichtbaren Text"
    cell = texts["Ein sehr langer Eintrag, der in keine schmale Liste passt"]
    assert cell["carrier"] == "QListWidget.Zeile" and cell["cut"] is True
    contrast = {entry["widget"]: entry for entry in capture.contrast_entries(root, "light")}
    (painted,) = [entry for entry in contrast.values() if entry["symbol"]]
    assert painted["foreground"] == "#ff0000"
    big = QLabel("Groß", root)
    big.setFont(QFont(big.font().family(), 16))
    bold = QLabel("Fett", root)
    font = QFont(bold.font().family(), 14)
    font.setBold(True)
    bold.setFont(font)
    layout.addWidget(big)
    layout.addWidget(bold)
    QApplication.processEvents()
    contrast = {entry["widget"]: entry for entry in capture.contrast_entries(root, "light")}
    assert contrast["Groß"]["large"] is False, "16 pt ist nach WCAG nicht groß"
    assert contrast["Fett"]["large"] is True
    root.close()
    root.deleteLater()


def test_a_screen_that_matches_none_is_an_error_not_another_screen() -> None:
    """Review L14: ``--screen`` ohne Treffer fällt nicht still auf einen anderen Schirm zurück."""

    class Screen:
        def __init__(self, name: str) -> None:
            self.label = name

        def name(self) -> str:
            return self.label

        def model(self) -> str:
            return ""

        def manufacturer(self) -> str:
            return ""

    class Application:
        def screens(self) -> list[Screen]:
            return [Screen("Haupt"), Screen("MSI")]

        def primaryScreen(self) -> Screen:  # noqa: N802 - Qts Name
            return self.screens()[0]

    with pytest.raises(ValueError, match="trifft keinen Schirm"):
        bench.place_window(Application(), None, bench.Variant.of({"screen": "Mond"}))
    with pytest.raises(ValueError, match="trifft keinen Schirm"):
        bench.place_window(Application(), None, bench.Variant.of({"screen": "7"}))


def test_typing_needs_the_focus_in_the_field_and_actions_need_a_vocabulary_name(
    qt_app: Any,
) -> None:
    """Review M13 und M11 an echten Widgets.

    Getippt wird nur, wenn der Fokus im Feld des Ziels liegt — auch in der
    Textzeile eines Zahlenfelds; sonst ein Fehler, der das Fokuswidget nennt.
    Eine Handlung einer Meldung hat nur mit Wortschatzkennzeichen ein Ziel; ein
    ``objectName`` ist keines.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QPushButton, QWidget

    from app.core.guides import TARGET_PROPERTY

    root = QWidget()
    spin = QDoubleSpinBox(root)
    other = QLineEdit(root)
    other.move(0, 40)
    root.show()
    root.activateWindow()
    spin.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    bench.focus_check(spin, "feature.field:resize_hole.diameter")
    other.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.processEvents()
    with pytest.raises(RuntimeError, match="QLineEdit"):
        bench.focus_check(spin, "feature.field:resize_hole.diameter")
    with pytest.raises(RuntimeError, match="kein Feld"):
        bench.focus_check(None, "search")
    named = QPushButton("Auf das Bett legen", root)
    named.setProperty(TARGET_PROPERTY, "finding.action:place_on_bed")
    plain = QPushButton("Ohne Namen", root)
    plain.setObjectName("handlung_ohne_namen")
    assert capture.vocabulary_name(named) == "finding.action:place_on_bed"
    assert capture.vocabulary_name(plain) == ""
    root.close()
    root.deleteLater()


def test_a_menubar_child_that_never_answers_is_a_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review L6: Hängt der Kindprozess der Menüleiste, kommt eine Meldung, kein Stapel."""
    import subprocess

    from tools import file_acceptance

    def hangs(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="menubar", timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(file_acceptance.subprocess, "run", hangs)
    with pytest.raises(RuntimeError, match="antwortete"):
        file_acceptance.menubar(tmp_path)


def test_the_halt_reason_is_read_where_the_report_shows_it(window: Any, tmp_path: Path) -> None:
    """Review M10: Der Haltgrund ist die Zeile des Prüfberichts am angehaltenen Schritt.

    Die Szene ``halt`` hält ihre Kette an. Gelesen wird der Text der
    Berichtszeile, deren Befund am angehaltenen Schritt steht, und als Nummer
    die, die der Verlauf dem Schritt gibt — nicht „der erste Text mit einer Zahl“.
    Ob der Text die Nummer nennt, urteilt U (Prüfpunkt 15).
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.ui.labels import step_number

    scenes = tmp_path / "scenes"
    row = {**_probe_row(scenes), "start_scene": "halt", "spec": {"start_scene": "halt"}}
    variant = bench.Variant.of({"phases": ["halt"]})
    data = bench.empty_protocol(row, variant.protocol(None, (0, 0)), {"commit": "", "app": ""})
    folder = tmp_path / "cases" / "001"
    folder.mkdir(parents=True)
    flow = bench.FunctionFlow(
        QApplication.instance(), window, folder, data, lambda: None, row, variant, scenes,
        out=tmp_path,
    )  # fmt: skip
    flow.prepare()
    assert flow.reset(), data["errors"]
    result = window.session.last_result
    assert result is not None and result.stopped_at is not None, "die Szene hält an"
    flow.read_halt()
    halt = data["halt"]
    assert halt is not None, data["unmeasured"]
    assert halt["step"] == step_number(window.session.project.document, result.stopped_at)
    shown = [
        window.report.list.item(row).text()
        for row in range(window.report.list.count())
        if getattr(window.report.list.item(row).data(Qt.ItemDataRole.UserRole), "op_id", None)
        == result.stopped_at
    ]
    assert halt["text"] in shown
    flow.finish()


@pytest.mark.windowed
def test_the_project_switch_runs_in_preview_draft_and_computation(tmp_path: Path) -> None:
    """Prüfpunkt 16 (Koordinator, Konzept §4): Wechsel während Vorschau, Entwurf und Rechnung.

    Die Probezeile im eigenen Prozess, nur die Phase ``switch``. Vorschau und
    Entwurf werden gemessen; die Rechnung, wenn sie beim ersten Wechselklick
    noch läuft — sonst steht der Grund in ``unmeasured``. Keine Phase endet in
    einem Fehler, und das Protokoll ist gültig.
    """
    out = tmp_path / "wechsel"
    _run_acceptance(
        out,
        ["inventory", "--functions", "--rows", PROBE_ROW, "--phases", "switch"],
        ["run", "--timeout", "900"],
    )
    protocol = json.loads((out / "cases" / "001" / "function.json").read_text(encoding="utf-8"))
    assert validate_protocol(protocol) == []
    assert protocol["errors"] == [], protocol["errors"]
    switch = protocol["switch"]
    assert switch is not None, protocol["unmeasured"]
    assert {"vorschau", "entwurf"} <= set(switch["phases"]), switch
    if "rechnung" not in switch["phases"]:
        assert "rechnung" in protocol["unmeasured"].get("switch", ""), protocol["unmeasured"]
    assert all(event["phase"] in switch["phases"] for event in switch["late_events"])


def _run_acceptance(out: Path, *arguments: list[str]) -> None:
    """``tools/file_acceptance.py`` in eigenen Prozessen, offscreen, je Aufruf ein Prozess."""
    import os
    import subprocess
    import sys

    environment = {**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONUTF8": "1"}
    for argument in arguments:
        finished = subprocess.run(
            [sys.executable, str(ACCEPTANCE), *argument, "--out", str(out)],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1200,
            check=False,
        )
        assert finished.returncode == 0, (finished.stdout, finished.stderr)


@pytest.mark.windowed
def test_the_expired_demo_row_starts_through_main_and_stops(tmp_path: Path) -> None:
    """D12 „Demo abgelaufen“: der Startfall über ``app.ui.app.main`` im eigenen Prozess (S1).

    Das Starttor wird nicht umgangen: Der Fall setzt nur den Zustand über die
    Nahtstelle der Suite und ruft ``main``. Die Anwendung startet nicht, zeigt den
    Grund, der Prüfstand schließt die Meldung mit *Schließen* samt Probe, und
    ``main`` endet mit seinem eigenen Ausgang.
    """
    out = tmp_path / "start"
    _run_acceptance(
        out,
        ["inventory", "--functions", "--rows", "startup.expired_demo"],
        ["run", "--timeout", "600"],
    )
    (case,) = read_cases(out)
    assert (case.kind, case.variant["licence"]) == ("start", STARTUP_LICENCE)
    folder = out / "cases" / "001"
    state = json.loads((folder / "bench.json").read_text(encoding="utf-8"))
    assert state["stage"] == "done" and state["main_exit_code"] == 1, state
    protocol = json.loads((folder / "function.json").read_text(encoding="utf-8"))
    assert validate_protocol(protocol) == []
    assert protocol["variant"]["licence"] == STARTUP_LICENCE
    assert protocol["errors"] == [] and protocol["findings"] == []
    assert protocol["result"]["metrics"] == {
        "exit_code": 1,
        "main_window": False,
        "message_shown": True,
    }
    (message,) = protocol["messages"]
    assert message["text"].strip()
    assert [action["clicked"] for action in message["actions"]].count(True) == 1
    (click,) = protocol["steps"]
    assert click["hit"] is True and click["phase"] == "start"
    assert [entry["class"] for entry in protocol["raw_windows"]] == ["QMessageBox"]
    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert (report["function_cases"], report["function_complete"]) == (1, 1)


def test_the_captures_read_a_small_dialog_without_acting_on_it(qt_app: Any) -> None:
    """Die Aufnahmen an einem kleinen, gezeigten Dialog: Texte, Felder, Layout, Tab-Kette, Zustände.

    Offscreen gibt es keine Schrift (``tests.md``) — geprüft werden Gestalt
    und Herkunft der Daten, nicht Pixelbreiten; jede Liste ist gegen U's Schema
    gültig. Die Zustandsbilder drücken den Knopf, lassen ihn aber außerhalb los:
    Er löst nicht aus.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QDialog,
        QDoubleSpinBox,
        QFormLayout,
        QLabel,
        QListWidget,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    from app.core.guides import TARGET_PROPERTY

    dialog = QDialog()
    outer = QVBoxLayout(dialog)
    outer.addWidget(QLabel("Bohrt ein rundes Loch.", dialog))
    form = QFormLayout()
    outer.addLayout(form)
    spin = QDoubleSpinBox(dialog)
    spin.setAccessibleName("Bohrung ändern — Durchmesser")
    spin.setToolTip("Wie weit die Bohrung wird.")
    spin.setProperty(TARGET_PROPERTY, "feature.field:resize_hole.diameter")
    form.addRow(QLabel("Durchmesser", dialog), spin)
    through = QCheckBox("Durchgehend", dialog)
    form.addRow(through)
    empty = QListWidget(dialog)
    outer.addWidget(empty)
    outer.addWidget(QLabel("Noch kein Eintrag", dialog))
    area = QScrollArea(dialog)
    tall = QWidget()
    tall.setMinimumHeight(2000)
    area.setWidget(tall)
    area.setFixedHeight(80)
    outer.addWidget(area)
    accept = QPushButton("Übernehmen", dialog)
    accept.setDefault(True)
    clicked: list[bool] = []
    accept.clicked.connect(lambda: clicked.append(True))
    outer.addWidget(accept)
    notice = QMessageBox(QMessageBox.Icon.Information, "Hinweis", "Roh", parent=dialog)
    watch = capture.ModalWatch(0.0)
    try:
        dialog.show()
        dialog.activateWindow()
        QApplication.processEvents()
        protocol: dict[str, Any] = {
            "texts": capture.text_entries(dialog),
            "fields": capture.field_entries(dialog),
            "empty_states": capture.empty_states(dialog),
            **capture.sheet_snapshot(dialog, "light", (1280, 820)),
        }
        texts = {entry["text"]: entry for entry in protocol["texts"]}
        assert {"Durchmesser", "Durchgehend", "Übernehmen", "Noch kein Eintrag"} <= set(texts)
        assert texts["Bohrt ein rundes Loch."]["lead"] is True
        assert texts["Übernehmen"]["lead"] is False
        fields = {entry["accessible_name"]: entry for entry in protocol["fields"]}
        diameter = fields["Bohrung ändern — Durchmesser"]
        assert diameter["label"] == "Durchmesser" and diameter["front"] is True
        assert diameter["tooltip"] == "Wie weit die Bohrung wird."
        assert capture.field_values(dialog)["resize_hole.diameter"] == pytest.approx(0.0)
        kinds = [entry["kind"] for entry in protocol["layout"]]
        assert kinds[0] == "primary" and "form" in kinds and "spacing" in kinds
        assert protocol["layout"][0]["primary"] == 1
        assert any(entry["vertical"] for entry in protocol["scrollbars"])
        assert any("Noch kein Eintrag" in entry["sentence"] for entry in protocol["empty_states"])
        # Review S4: Der Fokus steht am Hauptknopf, wie früher nach den
        # Zustandsbildern. Die Kette beginnt trotzdem am ersten Feld, läuft in
        # Lesefolge und endet mit dem Glied, das wiederkommt — U zählt es nicht.
        QTest.mouseClick(accept, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.processEvents()
        clicked.clear()
        assert QApplication.focusWidget() is accept

        def press_tab() -> None:
            focus = QApplication.focusWidget()
            assert focus is not None
            QTest.keyClick(focus, Qt.Key.Key_Tab)

        focused: dict[str, str] = {}

        def on_focus(widget: Any) -> None:
            if widget is accept:
                focused["digest"] = capture.picture_digest(accept)

        chain = capture.tab_chain(dialog, press_tab, limit=12, on_focus=on_focus)
        assert chain[0]["name"] == "Bohrung ändern — Durchmesser" and len(chain) >= 3
        assert all(entry["inside"] for entry in chain)
        assert chain[-1]["name"] == chain[0]["name"], "das Schlussglied kommt wieder"
        from tools.function_points import _reading_order_jumps, _within_chain

        within = _within_chain(chain)
        assert len(within) == len(chain) - 1
        assert (
            _reading_order_jumps([(entry["name"], tuple(entry["rect"])) for entry in within]) == []
        )
        protocol["tab_chain"] = chain
        # Review L2: „Fokus“ ist das Bild, das die Kette am Knopf aufnahm.
        assert focused["digest"]
        protocol["state_images"] = [
            {
                "surface": "QDialog",
                "widget": "Übernehmen",
                "states": capture.state_images(accept, focused["digest"]),
            }
        ]
        assert set(protocol["state_images"][0]["states"]) == set(capture.STATES)
        assert protocol["state_images"][0]["states"]["focus"] == focused["digest"]
        assert clicked == [], "der Druck für das Bild löste den Knopf aus"
        reacting = QPushButton("Halten", dialog)
        reacting.pressed.connect(lambda: clicked.append(False))
        reacting.show()
        QApplication.processEvents()
        assert "pressed" not in capture.state_images(reacting), "Drücken hätte ausgelöst"
        assert clicked == []
        notice.show()
        QApplication.processEvents()
        watch.poll()
        protocol["raw_windows"] = watch.raw_entries()
        protocol["windows"] = watch.windows
        assert [entry["class"] for entry in protocol["raw_windows"]] == ["QMessageBox"]
        assert protocol["raw_windows"][0]["allowed"] is False
        complete = {**dict.fromkeys(PROTOCOL_SCHEMA), **protocol, **_required()}
        assert validate_protocol(complete) == []
    finally:
        notice.close()
        dialog.close()
        notice.deleteLater()
        dialog.deleteLater()
        QApplication.processEvents()


def _required() -> dict[str, Any]:
    protocol = bench.empty_protocol(ROWS[0], bench.Variant().protocol(None, (0, 0)), {})
    return {key: protocol[key] for key in ("row", "kind", "package", "variant", "version")}
