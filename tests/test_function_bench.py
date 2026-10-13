"""Der Prüfstand der Funktionsfälle ohne Fenster: Automat, Weg und Phasen (D0-P, RM-737).

Was am Prüfstand reine Rechnung ist, prüft diese Datei an nachgestellten
Ereignissen und Zeitgebern (``tests/bench_fakes.py``): der Schrittautomat
(``function_machine``) auch durch modale ``exec()``-Schleifen, der Weg mit
Probe (``function_walk``) samt Wegklicks, „verdeckt“, „nicht auffindbar“,
Stillstand und Rollen, das Zahlenformat je Sprache, und Phasen des
Funktionsfalls, die ohne Fenster gehen (``function_bench``,
``function_language``). Vorbereitung und Fälle prüft
``test_function_setup.py``, Protokoll und Aufnahmen
``test_function_protocol.py``, den Wächter ``test_function_guard.py``, die
Wege am echten Fenster ``test_function_bench_window.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.bench_fakes import (
    FakeClick,
    FakePorts,
    FakeTimer,
    FakeWidget,
    run_machine,
)
from tools import (
    function_bench,
    function_gestures,
    function_language,
    function_machine,
    function_setup,
    function_walk,
)
from tools import function_capture as capture
from tools.function_checks import (
    COVERED,
    MAIN_PHASES,
    NOT_FOUND,
    WHY,
    validate_protocol,
)


def test_the_machine_runs_on_inside_a_modal_loop_and_finishes_after_it() -> None:
    """Ein Klick öffnet einen Dialog über ``exec()`` und kehrt erst nach dessen Ende zurück.

    Schritt 1 blockiert in einer verschachtelten Schleife, bis der Dialog zu
    ist; Schritt 2 wartet, bis er offen ist, und schließt ihn; Schritt 3 kommt
    danach. Ein linear geschriebener Ablauf bliebe in Schritt 1 stehen.
    """
    timer = FakeTimer()
    state = {"open": False}
    order: list[str] = []

    def opens(machine: function_machine.StepMachine) -> None:
        order.append("klick öffnet")
        state["open"] = True
        timer.loop_until(lambda: not state["open"])
        order.append("klick kehrt zurück")

    def closes(machine: function_machine.StepMachine) -> None:
        order.append("im dialog geklickt")
        state["open"] = False

    machine = run_machine(
        timer,
        [
            function_machine.Step("öffnen", opens),
            function_machine.Step("schließen", closes, ready=lambda: state["open"]),
            function_machine.Step("danach", lambda machine: order.append("danach")),
        ],
    )
    assert machine.done and machine.error is None and machine.finding is None
    assert order == ["klick öffnet", "im dialog geklickt", "klick kehrt zurück", "danach"]


def test_a_step_that_never_becomes_ready_stops_with_its_name() -> None:
    timer = FakeTimer()
    machine = run_machine(
        timer,
        [
            function_machine.Step(
                "wartet ewig", lambda machine: None, ready=lambda: False, timeout_s=2.0
            )
        ],
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

    def opens(machine: function_machine.StepMachine) -> None:
        state["open"] = True
        timer.loop_until(lambda: not state["open"])

    machine = run_machine(
        timer,
        [function_machine.Step("öffnen", opens)],
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

    def open_window(machine: function_machine.StepMachine) -> None:
        state["open"] = True
        timer.loop_until(lambda: not state["open"])

    def escape() -> None:
        state["escapes"] += 1

    def stuck() -> None:
        state["stuck"] += 1
        state["open"] = False

    machine = function_machine.StepMachine(
        timer.schedule, timer.clock, unstick=escape, on_stuck=stuck
    )
    function_machine.drive(
        machine, [function_machine.Step("öffnen", open_window)], timer.pump, timer.clock, 600.0
    )
    assert machine.done and machine.stuck
    assert state == {"open": False, "stuck": 1, "escapes": function_machine.MOST_UNSTICKS}


def test_an_error_in_an_action_stops_the_machine_with_the_trace() -> None:
    timer = FakeTimer()

    def broken(machine: function_machine.StepMachine) -> None:
        raise ValueError("kaputt")

    reached: list[str] = []
    machine = run_machine(
        timer,
        [
            function_machine.Step("kaputt", broken),
            function_machine.Step("danach", lambda machine: reached.append("x")),
        ],
    )
    assert machine.done and machine.error is not None and "ValueError: kaputt" in machine.error
    assert reached == []


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
    walker = function_walk.Walk(ports, steps, 0.0)
    walker.phase = function_walk.PATH_PHASE
    machine = run_machine(timer, [walker.step("feature:resize_hole")])
    assert machine.done and machine.error is None and machine.finding is None
    assert [step["why"] for step in steps] == ["reiter", "klappe", "ziel"]
    assert all(step["hit"] and step["phase"] == "weg" for step in steps)
    assert [name for name, _point, _button in ports.pressed] == ["reiter", "klappe", "kopf-text"]
    assert function_walk.way_clicks(steps) == 2
    assert function_walk.place_of(steps, "feature:resize_hole") == {
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
    walker = function_walk.Walk(ports, steps, 0.0)
    walker.phase = function_walk.PATH_PHASE
    machine = run_machine(timer, [walker.step("feature:resize_hole")])
    assert machine.finding is not None and machine.finding.kind == COVERED
    assert ports.pressed == []
    assert steps[-1]["hit"] is False and steps[-1]["finding"] == COVERED
    assert steps[-1]["widget_at"]["object_name"] == "einladung"
    assert steps[-1]["t"] >= function_walk.STABLE_S + function_walk.COVERED_S
    assert function_walk.place_of(steps, "feature:resize_hole")["error"] is not None


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
    walker = function_walk.Walk(ports, steps, 0.0)
    walker.phase = function_walk.PATH_PHASE
    machine = run_machine(timer, [walker.step("tree.row:obj_1.hole_1")])
    assert machine.done and machine.finding is None and machine.error is None
    assert ports.pressed == [("zeile", (100, 310), "left")]
    assert steps[-1]["hit"] is True and steps[-1]["t"] >= 0.5


def test_a_target_without_a_way_is_the_finding_not_found() -> None:
    timer = FakeTimer()
    ports = FakePorts(timer, {})
    steps: list[dict[str, Any]] = []
    walker = function_walk.Walk(ports, steps, 0.0)
    walker.phase = "weg"
    machine = run_machine(timer, [walker.step("operation:drill_hole")])
    assert machine.finding is not None and machine.finding.kind == NOT_FOUND
    assert len(steps) == 1 and steps[0]["t"] >= function_walk.MISSING_S, "erst nach der Frist"
    assert {key: value for key, value in steps[0].items() if key != "t"} == {
        "target": "operation:drill_hole",
        "finding": NOT_FOUND,
        "detail": "operation:drill_hole: kein Weg",
        "phase": "weg",
    }
    assert function_walk.place_of(steps, "operation:drill_hole") == {
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
    machine = run_machine(timer, [function_walk.Walk(ports, steps, 0.0).step("dialog.accept")])
    assert machine.done and machine.finding is None and machine.error is None
    assert ports.pressed == [("dialog", (40, 10), "left")]


def test_a_way_that_never_reaches_the_target_ends_as_not_found() -> None:
    """Ein Weg aus lauter Wegklicks ist ein Kreis — nach :data:`MOST_WAY_CLICKS` ist Schluss."""
    timer = FakeTimer()
    tab, _flap, _head, _label = _card()
    ports = FakePorts(timer, {"feature:x": [FakeClick((0, 0, 10, 10), "left", "reiter", tab)]})
    steps: list[dict[str, Any]] = []
    machine = run_machine(timer, [function_walk.Walk(ports, steps, 0.0).step("feature:x")])
    assert machine.finding is not None and machine.finding.kind == NOT_FOUND
    assert len(ports.pressed) == function_walk.MOST_WAY_CLICKS + 1
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
    machine = run_machine(
        timer, [function_walk.Walk(ports, steps, 0.0).step("tree.row:obj_1.hole_1")]
    )
    assert machine.finding is not None and machine.finding.kind == NOT_FOUND
    rolled = function_walk.MOST_WAY_CLICKS
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
    machine = run_machine(timer, [function_walk.Walk(ports, steps, 0.0).step("tree.row:obj_1")])
    assert machine.done and machine.error is None
    assert [point for _name, point, _button in ports.pressed] == [(50, 170)]
    assert steps[-1]["t"] >= function_walk.STABLE_S


def test_a_reading_waits_for_its_state_before_it_reads() -> None:
    """Review M1: Die Ruhe eines Schritts liegt nach ihm — gelesen wird nach einem Warteschritt.

    Gegenprobe: Ein Leseschritt mit ``settle_ms`` liest sofort (bei 0 s), auch
    wenn die Wirkung erst nach 0,5 s kommt. Mit ``until_step`` davor liest er
    danach; kommt sie nie, nach der Frist und ohne Fehler.
    """
    timer = FakeTimer()
    read_at: list[float] = []

    def read(machine: function_machine.StepMachine) -> None:
        read_at.append(timer.now)

    run_machine(timer, [function_machine.Step("lesen", read, settle_ms=2000)])
    assert read_at == [0.0], "so las der Prüfstand vor der Fixrunde"
    timer = FakeTimer()
    read_at.clear()
    machine = run_machine(
        timer,
        [
            function_machine.until_step("wirkung", lambda: timer.now >= 0.5, 2.0, timer.clock),
            function_machine.Step("lesen", read),
        ],
    )
    assert machine.error is None and 0.5 <= read_at[0] < 0.6
    timer = FakeTimer()
    read_at.clear()
    machine = run_machine(
        timer,
        [
            function_machine.until_step("nie", lambda: False, 2.0, timer.clock),
            function_machine.Step("lesen", read),
        ],
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
            function_machine.Step("hin", lambda machine: moved.setdefault("t", timer.now)),
            function_machine.Step("lesen", lambda machine: early.append(tooltip()), settle_ms=480),
        ],
    )
    assert early == [""], "so las der Prüfstand vor der Fixrunde"
    timer = FakeTimer()
    moved.clear()
    sink: list[str] = []
    machine = run_machine(
        timer,
        function_gestures.hover_steps(
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
    run_machine(timer, [function_walk.Walk(ports, steps, 0.0).step("feature.field:x.y")])
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
    walker = function_walk.Walk(ports, steps, 0.0)
    walker.phase = function_walk.PATH_PHASE
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
    assert function_walk.place_of(steps, "menu:tree.rename")["where"] == "kontext"


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

    assert function_walk.place_of([step("ziel", "kopf")], "t")["where"] == "werkzeugleiste"
    menu = function_walk.place_of([step("menue", "kopf"), step("ziel", "menue")], "t")
    assert menu == {"where": "menue", "path": ["menue", "ziel"], "error": None}
    assert function_walk.place_of([step("ziel", "karte_links")], "t")["where"] == "karte"
    elsewhere = function_walk.place_of([step("ziel", "kopf", phase="suche x")], "t")
    assert elsewhere["where"] is None and elsewhere["error"]


def test_buttons_are_named_as_words() -> None:
    assert function_walk.button_name("right") == "right"
    assert function_walk.button_name("") == "left"
    assert function_walk.with_modifier("left", "ctrl") == "ctrl+left"
    assert function_walk.with_modifier("left", "") == "left"

    class Mouse:
        name = "RightButton"

    assert function_walk.button_name(Mouse()) == "right"


def test_the_target_reason_and_the_main_phases_come_from_the_schema() -> None:
    assert function_walk.TARGET_REASON in WHY
    assert frozenset(WHY) == function_walk.WAY_REASONS | {function_walk.TARGET_REASON}
    assert tuple(MAIN_PHASES) == (function_walk.PATH_PHASE, function_walk.APPLY_PHASE)


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
            assert function_walk.typed_number(5.2) == f"5{separator}2"
            assert function_walk.typed_number(36.0) == "36"
            assert function_walk.typed_number(12.7, "in") == f"0{separator}5"
            assert function_walk.typed_number(0.0) == "0"
    finally:
        install_language("de")
        set_language("de")
    assert function_walk.typed_number(39.6) == "39,6"


def test_the_surface_of_a_surface_set_counts_as_the_rows_own_window() -> None:
    """Review L13: In Zoll, Skalierung, Dunkel und Bewegung ist die Fläche der Zeile erlaubt.

    Ihr modaler Dialog ist die Funktion selbst. Vorher trug ``phase_surface``
    seine Klasse nicht in ``watch.own`` ein, und der Dialog stand als nicht
    erlaubtes Fenster im Protokoll. Ein fremder Dialog bleibt nicht erlaubt.
    """

    class ParameterDialog:
        """Attrappe der Bedienfläche, die die Zeile öffnet."""

    flow = object.__new__(function_bench.FunctionFlow)
    flow.variant = function_setup.Variant.of({"set": "zoll", "unit": "in"})
    flow.row = {"id": "Bearbeiten/Parameter anlegen …"}
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
    flow.still_step = lambda name, root: function_machine.Step(name, lambda machine: None)  # type: ignore[method-assign]
    flow.run_steps = lambda label, steps: all(  # type: ignore[method-assign]
        step.act(None) or True for step in steps
    )
    flow.phase_surface()
    allowed = {entry["class"]: entry["allowed"] for entry in flow.watch.modal_entries()}
    assert allowed == {"ParameterDialog": True, "FremderDialog": False}
    assert pictures == ["flaeche-zoll"]


def test_the_preparation_of_a_scene_walks_its_route_and_waits_for_its_cause(
    tmp_path: Path,
) -> None:
    """Nach dem Öffnen stellt der Fall den Zustand der Szene her: Klicks über den Weg,
    Tippen in den Dateidialog, Tasten, und vor dem Export wartet er auf die Rückfrage
    und bricht sie ab; danach wartet er auf die zugesagten Befunde (Durchsicht welle4
    C-L3). Eine Szene ohne Angaben hat keine Vorbereitung."""
    walked: list[tuple[str, str]] = []

    class Walker:
        def step(self, name: str, button: str = "left") -> function_machine.Step:
            walked.append((name, button))
            return function_machine.Step(f"weg {name}", lambda machine: None)

    flow = object.__new__(function_bench.FunctionFlow)
    flow.folder = tmp_path
    flow.walker = Walker()  # type: ignore[assignment]
    names: dict[str, list[str]] = {}
    for key in ("export_gemischt", "geschuetzte_leiste.netz", "einfuegen.netz", "quader.netz"):
        walked.clear()
        flow.setup = function_setup.scene_setup(key)
        names[key] = [step.name for step in flow.preparation_steps()]
        names[f"{key} weg"] = [f"{target} {button}" for target, button in walked]
    assert names["export_gemischt"] == [
        "weg command:file.export",
        "taste Ctrl+A",
        "tippen dateiname",
        "taste Return",
        "rückfrage vor dem export",
        "rückfrage abbrechen",
        "vorbereitung steht",
        "befunde der vorbereitung",
        "vorbereitung geprüft",
    ]
    assert names["geschuetzte_leiste.netz weg"] == [
        "tree.row:obj_1 left",
        "command:edit.auto_split left",
    ]
    assert names["einfuegen.netz weg"] == ["history.row:2 right", "history:insert left"]
    assert names["einfuegen.netz"][-3:] == [
        "vorbereitung steht",
        "befunde der vorbereitung",
        "vorbereitung geprüft",
    ]
    assert names["quader.netz"] == []


def test_every_phase_starts_at_its_scene_and_runs_only_if_it_got_there() -> None:
    """Review M5: Vor jeder Phase ein Rücksetzen, auch nach einer Ausnahme; misslingt es, ruht sie.

    Der Fall ist ohne Fenster nachgestellt: ``reset`` und die Phasen sind
    Attrappen, ``run`` ist der echte Ablauf.
    """
    calls: list[str] = []
    answers = iter([True, False, True])
    flow = object.__new__(function_bench.FunctionFlow)
    flow.variant = function_setup.Variant.of({"phases": ["escape", "main", "revise"]})
    flow.not_a_case = ""
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


def test_a_language_case_skips_the_surface_its_last_run_died_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review M14: Eine Fläche, an der der Prozess starb, kommt im nächsten Lauf nicht wieder dran.

    Vor jeder Fläche steht ein Anfangsvermerk in ``bench.json``; ein Vermerk ohne
    Ergebnis heißt Absturz. Die Fläche bekommt ein Protokoll mit dem Fehler,
    der Rest des Pakets läuft weiter.
    """
    from types import SimpleNamespace

    monkeypatch.setattr(function_language, "place_window", lambda application, window, variant: {})
    state: dict[str, Any] = {"surface_started": "D4.abgestuerzt"}
    window = SimpleNamespace(width=lambda: 800, height=lambda: 600)
    rows = [{"id": "D4.abgestuerzt", "kind": "operation", "package": "D4"}]
    flow = function_language.LanguageFlow(
        None,
        window,
        tmp_path,
        state,
        lambda: None,
        rows,
        function_setup.Variant.of({"set": "sprachen"}),
        tmp_path / "scenes",
        {"commit": "", "app": ""},
    )
    flow.run()
    (written,) = (tmp_path / "surfaces").glob("*.json")
    protocol = json.loads(written.read_text(encoding="utf-8"))
    assert protocol["errors"] == ["Die Fläche brach im vorigen Lauf den Prozess ab"]
    assert validate_protocol(protocol) == []
    assert state["surfaces_done"] == ["D4.abgestuerzt"] and state["surface_started"] is None
