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
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
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
    menubar_lines,
    read_cases,
    resumes,
    summary,
    write_json,
)
from tools.function_checks import (
    CHECKPOINTS,
    LICENCE_RUNS,
    LICENCE_STATES,
    MAIN_PHASES,
    PROTOCOL_FIELDS,
    PROTOCOL_SCHEMA,
    SELECTION_STAGES,
    WHY,
    validate_protocol,
)

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
    assert bench.place_of(steps, "feature:resize_hole")["error"] is not None


def test_a_target_without_a_way_is_the_finding_not_found() -> None:
    timer = FakeTimer()
    ports = FakePorts(timer, {})
    steps: list[dict[str, Any]] = []
    walker = bench.Walk(ports, steps, 0.0)
    walker.phase = "weg"
    machine = run_machine(timer, [walker.step("operation:drill_hole")])
    assert machine.finding is not None and machine.finding.kind == bench.NOT_FOUND
    assert steps == [
        {
            "target": "operation:drill_hole",
            "finding": bench.NOT_FOUND,
            "detail": "operation:drill_hole: kein Weg",
            "phase": "weg",
            "t": 0.0,
        }
    ]
    assert bench.place_of(steps, "operation:drill_hole") == {
        "where": None,
        "path": [],
        "error": "operation:drill_hole: kein Weg",
    }


def test_a_way_that_never_reaches_the_target_ends_as_not_found() -> None:
    """Ein Weg aus lauter Wegklicks ist ein Kreis — nach :data:`MOST_WAY_CLICKS` ist Schluss."""
    timer = FakeTimer()
    tab, _flap, _head, _label = _card()
    ports = FakePorts(timer, {"feature:x": [FakeClick((0, 0, 10, 10), "left", "reiter", tab)]})
    steps: list[dict[str, Any]] = []
    machine = run_machine(timer, [bench.Walk(ports, steps, 0.0).step("feature:x")])
    assert machine.finding is not None and machine.finding.kind == bench.NOT_FOUND
    assert len(ports.pressed) == bench.MOST_WAY_CLICKS + 1


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
    assert bench.step_number("Die Kette hält bei Schritt 3: kein Körper.") == 3
    assert bench.step_number("ohne Nummer") is None


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


def test_the_tab_chain_breaks_where_focus_goes_back_up() -> None:
    """Zeilenweise von oben, in der Zeile von links; der Sprung zum Anfang schließt die Kette."""

    def link(name: str, x: int, y: int) -> dict[str, Any]:
        return {"name": name, "rect": [x, y, 100, 24]}

    chain = [link("a", 10, 10), link("b", 10, 40), link("c", 120, 42), link("d", 10, 20)]
    chain.append(link("a", 10, 10))
    assert capture.chain_breaks(chain) == [3]
    assert capture.chain_breaks([*chain[:3], chain[0]]) == []
    assert capture.chain_breaks([link("a", 100, 10), link("b", 10, 12)]) == [1]
    assert capture.duplicate_names(["Durchmesser", "Tiefe", "Durchmesser", ""]) == ["Durchmesser"]


def test_a_text_wider_than_its_place_is_cut() -> None:
    entries = [
        {"text": "Bohrung ändern", "need_px": 90, "width_px": 120},
        {"text": "Modifier la profondeur", "need_px": 140, "width_px": 120},
    ]
    assert [entry["text"] for entry in capture.overflowing(entries)] == ["Modifier la profondeur"]


def test_equal_pictures_of_two_states_are_named() -> None:
    images = {"rest": "a", "hover": "b", "focus": "a", "pressed": "c"}
    assert capture.alike_states(images) == [("rest", "focus")]


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


@pytest.mark.parametrize("state", LICENCE_STATES)
def test_the_licence_state_is_set_through_the_suites_seam(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """Jeder Lizenzzustand ohne private Schlüssel — über ``activation._cached`` wie die Suite.

    Die Namen sind Eigenschaften von ``Activation`` (``function_checks``): An dem
    gebauten Zustand gilt genau die genannte. Gesperrt heißt, die Grenze im
    Datenpfad wirft (``activation.require``) — in den abgelaufenen Zuständen.
    """
    from app.core import activation
    from app.core.activation import store
    from app.core.errors import LicenceRequired

    monkeypatch.setattr(activation, "_cached", activation._cached)
    monkeypatch.setattr(store, "DEMO_UNTIL", store.DEMO_UNTIL)
    monkeypatch.setattr(store, "TRIAL_FROM", store.TRIAL_FROM)
    cached = bench.apply_licence(state, date(2026, 10, 12))
    assert activation.state() is cached
    assert getattr(cached, state) is True
    # in_demo heißt „diese Fassung ist eine Demo“ und gilt auch nach ihrem
    # Stichtag; jede andere Eigenschaft gilt nur in ihrem eigenen Zustand.
    others = {name for name in LICENCE_STATES if bool(getattr(cached, name))} - {state}
    assert others == ({"in_demo"} if state == "over" else set()), others
    assert cached.unlocked is (state not in ("over", "expired"))
    if state in ("over", "expired"):
        with pytest.raises(LicenceRequired):
            activation.require(activation.CHANGE)
    else:
        activation.require(activation.CHANGE)
    assert set(LICENCE_RUNS) <= set(LICENCE_STATES)


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


def test_the_spec_sets_licence_and_preconditions_and_both_states_run() -> None:
    """Die Spezifikation legt Lizenz und Vorbedingungen fest; „fehlt“ und „vorhanden“ laufen beide.

    Die Lizenzwörter der Spezifikation (L) werden die Zustände des Protokolls (U).
    """
    base, others = bench.spec_variants(
        {"preconditions": {"licence": "abgelaufen", "slicer": "vorhanden", "printer": "resin"}}
    )
    assert base == {
        "licence": "expired",
        "preconditions": {"slicer": "vorhanden", "printer": "resin"},
    }
    assert others == [
        {"preconditions": {"slicer": "fehlt", "printer": "resin"}, "phases": ["main"]}
    ]
    assert bench.spec_variants(None) == ({}, [])
    assert set(bench.SPEC_LICENCES.values()) <= set(LICENCE_STATES)


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
    ):
        with pytest.raises(ValueError):
            bench.Variant.of(broken)
    variant = bench.Variant.of({"window_size": "1366x728", "scale": 1.5, "phases": ["main"]})
    assert bench.parse_size(variant.window_size) == (1366, 728)
    assert variant.phases == ("main",)
    assert bench.Variant.of(variant.as_dict()) == variant
    assert set(bench.PHASES) == set(bench.VARIANT_SETS)
    assert {entry.get("licence") for entry in bench.VARIANT_SETS["lizenz"]} == set(LICENCE_RUNS)
    assert {entry.get("window_size") for entry in bench.VARIANT_SETS["skalierung"]} >= set(
        bench.WINDOW_SIZES
    )
    assert bench.VARIANT_SETS["bewegung"] == ({"set": "bewegung", "motion": False},)


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
    # basis: resize_hole einmal, drill_hole zweimal (Slicer vorhanden und fehlt); lizenz: je drei.
    assert len(function) == 1 + 2 + 2 * len(LICENCE_RUNS)
    slicer = [case.variant["preconditions"] for case in function if case.row == "drill_hole"]
    assert {"slicer": "vorhanden"} in slicer and {"slicer": "fehlt"} in slicer
    assert [(case.row, case.variant["language"]) for case in language] == [
        ("D4", "de"),
        ("D4", "en"),
    ]
    first = function[0]
    assert first.path == "scenes/merkmal.hole.exakt.p3d" and first.variant["set"] == "basis"
    assert {case.variant["licence"] for case in function if case.variant["set"] == "lizenz"} == set(
        LICENCE_RUNS
    )
    assert function_cases(ROWS, row_ids=["finding.action:place_on_bed"])[0].row == (
        "finding.action:place_on_bed"
    )
    again = function_cases(ROWS, row_ids=["resize_hole"], phases=["escape", "main"])
    assert [case.variant["phases"] for case in again] == [["escape", "main"]]
    with pytest.raises(ValueError, match="Phasen"):
        function_cases(ROWS, row_ids=["resize_hole"], variant_sets=["lizenz"], phases=["main"])
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


def test_the_menubar_reaches_the_list_with_the_line_in_its_path(tmp_path: Path) -> None:
    """W nennt die Titel **über** der Zeile, L liest den Weg **bis zur** Zeile (``MenuEntry``).

    Die Zeile selbst kommt dazu, das Kürzel steht, wie die Aktion es trägt, und
    ``read_menubar`` aus ``function_list`` liest die Datei so, wie der Prüfstand sie
    schreibt.
    """
    from tools import function_list

    class Shortcut:
        def toString(self) -> str:  # noqa: N802 - Qts Name
            return "Ctrl+Shift+S"

    class Action:
        def text(self) -> str:
            return "Speichern unter …"

        def shortcut(self) -> Shortcut:
            return Shortcut()

    lines = menubar_lines([("menubar.datei.speichern_unter", ("Datei",), Action())])
    assert lines == [
        {
            "object_name": "menubar.datei.speichern_unter",
            "path": ["Datei", "Speichern unter …"],
            "shortcut": "Ctrl+Shift+S",
        }
    ]
    assert (
        function_list.MenuEntry(
            "menubar.datei.speichern_unter", ("Datei", "Speichern unter …"), "Ctrl+Shift+S"
        )
        == function_list.read_menubar(_written(tmp_path, lines))[0]
    )


def _written(folder: Path, lines: list[dict[str, Any]]) -> Path:
    write_json(folder / "menubar.json", lines)
    return folder / "menubar.json"


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
    assert "route" not in protocol["row"], "der Auswahlweg steht in steps, nicht in row"
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
    assert bench.safe_name("Datei/Speichern unter …") == "Datei_Speichern_unter"
    assert bench.bodies_digest({"b": "2", "a": "1"}) == bench.bodies_digest({"a": "1", "b": "2"})


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
    assert protocol["variant"]["licence"] == "licensed" and protocol["variant"]["language"] == "de"
    _assert_the_main_way(protocol)
    menu = json.loads((out / "menubar.json").read_text(encoding="utf-8"))
    assert len(menu) > 30 and all(entry["object_name"].startswith("menubar.") for entry in menu)
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
        spin.setFocus(Qt.FocusReason.TabFocusReason)
        QApplication.processEvents()

        def press_tab() -> None:
            focus = QApplication.focusWidget()
            assert focus is not None
            QTest.keyClick(focus, Qt.Key.Key_Tab)

        chain = capture.tab_chain(dialog, press_tab, limit=12)
        assert chain[0]["name"] == "Bohrung ändern — Durchmesser" and len(chain) >= 3
        protocol["tab_chain"] = chain
        protocol["state_images"] = [
            {"surface": "QDialog", "widget": "Übernehmen", "states": capture.state_images(accept)}
        ]
        assert set(protocol["state_images"][0]["states"]) == set(capture.STATES)
        assert clicked == [], "der Druck für das Bild löste den Knopf aus"
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
