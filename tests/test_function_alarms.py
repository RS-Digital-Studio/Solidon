"""Die Fehlalarme des Probelaufs D0 ohne Fenster (D0-P2, RM-737).

Der Probelauf vom 12.10.2026 (``output/konsolidierung-2026-10-12/
auswertung-probelauf-d0.md``) fand 39 Befunde, die der Prüfstand falsch maß
oder falsch beurteilte (F-1 bis F-39). Was davon ohne Fenster zu greifen ist,
hält diese Datei fest — je Fehlalarm ein Fall, der am Stand des Laufs rot war:
die Urteile über ein Protokoll in der Form, in der der Prüfstand es schrieb,
und die Rechnung des Prüfstands an nachgestellten Ereignissen. Was nur am
Fenster geht, steht in ``test_function_captures_window.py``.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from tests.bench_fakes import FakeClick, FakePorts, FakeTimer, FakeWidget, run_machine
from tools import (
    function_bench,
    function_list,
    function_machine,
    function_scenes,
    function_setup,
    function_walk,
)
from tools.function_checks import (
    FAULT_PHASE,
    MAIN_PHASES,
    NO_RESPONSE,
    NOT_FOUND,
    STEP_WITHOUT_VALUES,
    WITHOUT_DIALOG,
    validate_protocol,
)
from tools.function_judges import CRITERION_JUDGES
from tools.function_points import POINT_JUDGES, judge_case, judge_licence
from tools.function_samples import click_step, sample_context, sample_protocol

PATH, APPLY = MAIN_PHASES


def _protocol(change: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    protocol = copy.deepcopy(sample_protocol())
    if change is not None:
        change(protocol)
    return protocol


def _criterion(key: str, protocol: dict[str, Any]) -> Any:
    return CRITERION_JUDGES[key](protocol, sample_context())


def _point(number: int, protocol: dict[str, Any]) -> Any:
    case = judge_case(protocol, sample_context())
    return case.points[number]


def _texts(outcome: Any) -> list[str]:
    return [issue.text for issue in outcome.issues]


# --- Einfachheit: E1 (F-17, F-18) -------------------------------------------------


#: Die Zeile *Auf das Bett setzen* und ihr Hauptweg, wie der Probelauf sie
#: schrieb (Fall 002): Reiter und Klappe auf dem Weg zum Befund tragen dessen
#: Namen als Ziel.
_FINDING_ROW = {
    "id": "finding.action:place_on_bed",
    "kind": "bedienflaeche",
    "source": "befundhandlung",
    "package": "D8",
    "requirement": "befund",
    "start_scene": "unter_dem_bett.netz",
    "target": "finding.action:place_on_bed",
    "route": [{"target": "finding:arrange.below_bed", "button": "left", "modifier": ""}],
}
_FINDING_STEPS = [
    click_step("finding:arrange.below_bed", why="reiter"),
    click_step("finding:arrange.below_bed", why="klappe"),
    click_step("finding:arrange.below_bed"),
    click_step("finding.action:place_on_bed", phase=APPLY),
]


def test_e1_ends_the_selection_at_the_click_that_hits_its_target() -> None:
    """F-17: Die Startauswahl endet am Treffer auf das Routenziel, nicht am ersten Wegklick.

    Vorher endete sie am Reiterklick, der dasselbe Ziel trägt; Klappe, Befund
    und Handlung zählten als drei Klicks nach der Auswahl, und der Punkt im
    Befundcode ``arrange.below_bed`` machte daraus ein Merkmal mit Grenze 2.
    Ein Klick bleibt: die Handlung selbst.
    """
    protocol = _protocol(
        lambda data: data.update(row=dict(_FINDING_ROW), steps=copy.deepcopy(_FINDING_STEPS))
    )
    outcome = _criterion("E1", protocol)
    assert outcome.measurement == {"clicks": 1, "limit": 3}, outcome
    assert outcome.verdict != "fund", _texts(outcome)


def test_e1_leaves_the_clicks_into_typed_fields_to_e2() -> None:
    """F-18: Ein Klick ins Feld, in das danach getippt wird, ist eine Eingabe (E2), kein E1-Klick.

    *Parameter anlegen* im Probelauf (Fall 003): Menü, Eintrag, Klick in Name
    und Wert, Tippen, dann *Anlegen*. Mit den Vorgaben sind es drei Klicks.
    """

    def typed(target: str, text: str) -> dict[str, Any]:
        return {"target": target, "typed": text, "button": None, "phase": PATH}

    steps = [
        click_step("menu:menubar.parameter_anlegen", "menue", why="menue"),
        click_step("menu:menubar.parameter_anlegen", "menue"),
        click_step("field:name", "dialog"),
        typed("field:name", "breite"),
        click_step("field:value", "dialog"),
        typed("field:value", "40"),
        click_step("dialog.accept", "dialog", phase=APPLY),
    ]
    protocol = _protocol(
        lambda data: data.update(
            row={**data["row"], "requirement": "leer", "route": []}, steps=steps
        )
    )
    outcome = _criterion("E1", protocol)
    assert outcome.measurement["clicks"] == 3, outcome
    assert outcome.verdict != "fund", _texts(outcome)
    assert _criterion("E2", protocol).measurement["inputs"] == 2


# --- Verständlichkeit: V1 (F-10) -------------------------------------------------------


def test_v1_leaves_out_the_names_the_scene_brings() -> None:
    """F-10: Objekt- und Projektnamen der Szene sind Text des Kunden, kein Bezeichner der Anwendung.

    ``cube_clean`` kommt aus ``meshes/cube_clean.stl`` und traf das Muster für
    Bezeichner. Steht der Name in ``scene.names``, zählt er nicht; ein
    Bezeichner in einem Text der Anwendung zählt weiter.
    """
    context = sample_context()
    context = replace(
        context,
        negative_words=(
            *context.negative_words,
            ("Bezeichner", "de", r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"),
        ),
    )

    def judged(names: list[str], text: str) -> Any:
        protocol = _protocol()
        protocol["scene"]["names"] = names
        protocol["texts"][0]["text"] = text
        outcome = CRITERION_JUDGES["V1"](protocol, context)
        assert validate_protocol(protocol) == []
        return outcome

    assert judged(["cube_clean", "unter_dem_bett.netz"], "cube_clean").verdict == "erfuellt"
    assert judged(["cube_clean"], "Öffnet unter_dem_bett.netz").verdict == "fund"
    assert judged([], "cube_clean").verdict == "fund"


# --- Gestaltung: G2, G4, G7, Z6 (F-4 bis F-7, F-11, F-12) ---------------------------------


def _spacing(group: str, spacing: int, items: int, horizontal: int | None = None) -> dict[str, Any]:
    return {
        "kind": "spacing",
        "surface": "OperationDialog",
        "group": group,
        "spacing": spacing,
        "margins": [0, 0, 0, 0],
        "items": items,
        "horizontal": horizontal,
    }


def test_g2_counts_a_gap_only_between_two_items_and_in_both_directions() -> None:
    """F-6, F-7: Ein Abstand liegt zwischen zwei Elementen, und ein Formular hat zwei.

    Das Zahlenfeld trägt eine Spalte mit einem Element (Abstand 0, Qt-Vorgabe 6
    bedeutungslos) und eine Zeile mit ``TIGHT``; jedes Layout ist seine eigene
    Gruppe. Ein Formular mit waagerecht 12 und senkrecht 8 ist in Ordnung —
    vorher stand dort -1. Senkrecht 6 bleibt ein Fund (E-9 ist echt).
    """
    entries = [
        {"kind": "primary", "surface": "OperationDialog", "primary": 1, "accents": 1},
        _spacing("field:diameter#1", 6, 1),
        _spacing("field:diameter#2", 4, 3),
        _spacing("QFormLayout#3", 8, 4, horizontal=12),
    ]
    good = _protocol(lambda data: data.update(layout=entries))
    outcome = _criterion("G2", good)
    assert outcome.verdict == "erfuellt", _texts(outcome)

    off = copy.deepcopy(entries)
    off[3]["spacing"] = 6
    outcome = _criterion("G2", _protocol(lambda data: data.update(layout=off)))
    assert outcome.verdict == "fund" and "[6.0]" in _texts(outcome)[0], _texts(outcome)


def _font(**values: Any) -> dict[str, Any]:
    entry = {"surface": "OperationDialog", "widget": "Weitere Einstellungen", "stylesheet": ""}
    entry.update(values)
    return entry


def test_g4_reads_the_effective_font_and_lets_design_colours_pass() -> None:
    """F-4, F-5: Ohne ``level`` gilt die Grundschrift; Gestaltungsfarben sind keine fremden.

    Vorher war jede Schrift ohne gesetzte Stufe ein Fund (60 Zeilen) und jede
    Hexfarbe im Stylesheet ebenso — auch die Rollenfarbe der Warnmarke und die
    Feldschrift der Analyselegende. Eine Größe im Stylesheet, eine fremde
    Schriftfarbe und eine Schrift außerhalb der vier Stufen bleiben Funde.
    """
    from app.ui.palette import ON_DARK_FIELD, ROLES, readable_on
    from app.ui.style import type_scale

    base = 9
    body, normal = type_scale(base)["body"]
    caption, _weight = type_scale(base)["caption"]
    mark = (
        f"QLabel {{ background: {ROLES['error']}; color: {readable_on(ROLES['error'])};"
        " border-radius: 6px; padding: 0px 5px; }"
    )
    good = [
        _font(level="", points=float(body), weight=normal, base_points=base),
        _font(level="caption", points=float(caption), weight=normal, base_points=base),
        _font(level="", points=float(body), weight=normal, base_points=base, stylesheet=mark),
        _font(
            level="",
            points=float(body),
            weight=normal,
            base_points=base,
            stylesheet=f"background: #21918c; color: {ON_DARK_FIELD}; padding: 1px 5px;",
        ),
    ]
    outcome = _criterion("G4", _protocol(lambda data: data.update(fonts=good)))
    assert outcome.verdict == "erfuellt", _texts(outcome)

    for wrong in (
        _font(
            level="",
            points=float(body),
            weight=normal,
            base_points=base,
            stylesheet="color: #123456;",
        ),
        _font(
            level="",
            points=float(body),
            weight=normal,
            base_points=base,
            stylesheet="font-size: 13px;",
        ),
        _font(level="", points=float(body + 3), weight=normal, base_points=base),
    ):
        outcome = _criterion("G4", _protocol(lambda data, wrong=wrong: data.update(fonts=[wrong])))
        assert outcome.verdict == "fund", wrong


def test_g7_finds_only_a_missing_or_foreign_symbol() -> None:
    """F-12: Eine ungeklärte Herkunft (``own`` ``None``) ist ein Vermerk, kein Fund."""
    unknown = _protocol(lambda data: data["icons"][0].update(own=None))
    outcome = _criterion("G7", unknown)
    assert outcome.verdict == "erfuellt", _texts(outcome)
    assert any("nicht belegt" in note for note in outcome.notes)
    foreign = _protocol(lambda data: data["icons"][0].update(own=False))
    assert _criterion("G7", foreign).verdict == "fund"


def test_z6_finds_only_a_pixmap_coarser_than_the_screen() -> None:
    """F-11: Doppelt gerastert (``icons.OVERSAMPLING``) ist schärfer, nicht unscharf."""
    sharper = _protocol(lambda data: data["icons"][0].update(scale=1.0, pixmap_ratio=2.0))
    outcome = _criterion("Z6", sharper)
    assert outcome.verdict == "erfuellt", _texts(outcome)
    coarser = _protocol(lambda data: data["icons"][0].update(scale=2.0, pixmap_ratio=1.0))
    assert _criterion("Z6", coarser).verdict == "fund"


# --- Prüfpunkte 1, 5, 6, 7, 10, 12, 18 (F-23, F-24, F-29, F-35 bis F-37) ------------------


def test_p1_keeps_not_found_of_a_case_that_measures_no_place() -> None:
    """F-37: Ein Variantenfall misst keinen Ort; sein „nicht auffindbar“ geht nicht verloren."""

    def surface_only(data: dict[str, Any]) -> None:
        data["place"] = None
        data["findings"] = [
            {
                "phase": PATH,
                "kind": NOT_FOUND,
                "target": "feature:resize_hole",
                "detail": "QToolButton steht nicht da",
            }
        ]

    outcome = _point(1, _protocol(surface_only))
    assert outcome.verdict == "fund", outcome
    assert any("feature:resize_hole" in text for text in _texts(outcome))
    assert _point(1, _protocol(lambda data: data.update(place=None))).verdict == "nicht_gelaufen"


def test_p5_needs_a_change_to_measure_the_way_back() -> None:
    """F-36: Ändert das Übernehmen nichts, ist der Rückweg nicht gemessen — nicht „ja“.

    *Parameter anlegen* klickte nie *Anlegen*; vorher, übernommen, rückgängig
    und wiederholt waren derselbe Abdruck, und Prüfpunkt 5 stand auf erfüllt.
    """

    def unchanged(data: dict[str, Any]) -> None:
        before = data["states"]["before"]
        for key in ("applied", "undo", "redo", "escape", "cancelled"):
            data["states"][key] = copy.deepcopy(before)

    outcome = _point(5, _protocol(unchanged))
    assert outcome.verdict == "nicht_gelaufen", outcome
    assert _point(5, _protocol()).verdict == "erfuellt"


def test_p6_a_wait_without_result_is_the_finding_no_response() -> None:
    """Neue Fundart „keine Rückmeldung“: Eine abgelaufene Wartefrist ist ein Fund an Prüfpunkt 6.

    Vorher stand sie nur in ``unmeasured.timing``, und Prüfpunkt 6 hieß
    „nicht gelaufen“ — als hätte niemand hingesehen.
    """

    def silent(data: dict[str, Any]) -> None:
        data["timing"]["total_s"] = None
        data["unmeasured"]["timing"] = "keine Rückmeldung: nach 180 s kein fertiges Ergebnis"
        data["findings"] = [
            {
                "phase": APPLY,
                "kind": NO_RESPONSE,
                "target": "feature.apply",
                "detail": "nach 180 s kein fertiges Ergebnis",
            }
        ]

    protocol = _protocol(silent)
    outcome = _point(6, protocol)
    assert outcome.verdict == "fund", outcome
    assert outcome.issues[0].severity == "schwer"
    assert "keine Rückmeldung" in outcome.issues[0].text
    assert validate_protocol(protocol) == []


def test_p7_is_not_run_when_the_fault_case_was_not_made() -> None:
    """F-24: Kam der Fehlfall nicht zustande, ist „keine Meldung“ kein Fund der Anwendung."""

    def unreached(data: dict[str, Any]) -> None:
        data["messages"] = []
        data["findings"] = [
            {
                "phase": FAULT_PHASE,
                "kind": NOT_FOUND,
                "target": "field:edge",
                "detail": "kein Bedienelement trägt dieses Kennzeichen",
            }
        ]

    outcome = _point(7, _protocol(unreached))
    assert outcome.verdict == "nicht_gelaufen", outcome
    assert "field:edge" in outcome.reason
    errored = _protocol(
        lambda data: data.update(
            messages=[], errors=[f"{FAULT_PHASE}: meldung: Zeitgrenze von 180 s überschritten"]
        )
    )
    assert _point(7, errored).verdict == "nicht_gelaufen"
    silent = _protocol(lambda data: data.update(messages=[]))
    assert _point(7, silent).verdict == "fund"


def test_p10_needs_no_focus_return_where_no_dialog_opens() -> None:
    """F-29: An einer Befundhandlung öffnet sich kein Dialog — die Fokusrückkehr entfällt."""

    def without(data: dict[str, Any]) -> None:
        data["focus_return"] = None
        data["unmeasured"]["focus_return"] = WITHOUT_DIALOG

    outcome = _point(10, _protocol(without))
    assert outcome.verdict == "erfuellt", outcome
    assert _point(10, _protocol(lambda data: data.update(focus_return=None))).verdict == (
        "nicht_gelaufen"
    )


def test_p12_a_step_without_values_has_no_dialog_to_open() -> None:
    """F-23: *Auf das Bett setzen* hat keinen Wert — Prüfpunkt 12 entfällt, statt „öffnet nicht“."""

    def without(data: dict[str, Any]) -> None:
        data["revise"] = []
        data["unmeasured"]["revise"] = STEP_WITHOUT_VALUES

    outcome = _point(12, _protocol(without))
    assert (outcome.verdict, outcome.reason) == ("entfaellt", "ohne_dialog"), outcome
    assert _point(12, _protocol(lambda data: data.update(revise=[]))).verdict == "nicht_gelaufen"


def test_p18_a_function_that_writes_unlocked_writes_in_every_run() -> None:
    """F-35: Schreiben ist eine Eigenschaft der Funktion, nicht des Laufs.

    Im gesperrten Lauf konnte die Befundhandlung nichts ändern — der Kern
    lehnte ab, und ``writes`` stand falsch; offen ohne Grau hieß dann
    „Lesendes frei“. Der freigeschaltete Lauf derselben Zeile zeigt, dass sie
    schreibt.
    """
    runs = {
        "needs_activation": {"writes": False, "state": "angeboten", "reason": ""},
        "licensed": {"writes": True, "state": "angeboten", "reason": ""},
    }
    outcome = judge_licence(runs, complete=True)
    assert outcome.verdict == "fund", outcome
    assert any("needs_activation" in text for text in _texts(outcome))


def _licence_run(monkeypatch: Any, licence: str, *, missing: bool, grey: str | None) -> Any:
    """Ein Lizenzlauf des Prüfstands an einer nachgestellten Oberfläche.

    ``missing``: ``next_click`` findet das Ziel nicht (``LookupError``);
    ``grey``: der Grund, mit dem es grau steht, ``None`` heißt offen.
    """
    from tools import function_surface

    monkeypatch.setattr(function_surface, "in_view", lambda window, inputs: False)
    monkeypatch.setattr(function_surface, "grey_reason", lambda window, name: grey)

    class Signal:
        def connect(self, slot: Any) -> None:
            pass

        def disconnect(self, slot: Any) -> None:
            pass

    button = FakeWidget("operation:drill_hole")
    script = (
        {}
        if missing
        else {"operation:drill_hole": [FakeClick((0, 0, 9, 9), "left", "ziel", button)]}
    )
    flow = _flow({})
    flow.row = {**flow.row, "kind": "operation", "target": "operation:drill_hole", "route": []}
    flow.walker = function_walk.Walk(FakePorts(FakeTimer(), script), [], 0.0)
    flow.ports = flow.walker.ports
    flow.window = None
    flow.session = type("Session", (), {"failed": Signal()})()
    flow.variant = function_setup.Variant.of({"set": "lizenz", "licence": licence})
    flow.widget = lambda name: None  # type: ignore[method-assign]
    flow.scene_now = lambda: {"ops": ["create_brep_box"]}  # type: ignore[method-assign]
    flow.effect_steps = lambda label: (  # type: ignore[method-assign]
        [function_machine.Step(f"{label} merken", lambda machine: None)],
        lambda: True,
    )
    flow.run_steps = lambda phase, steps: True  # type: ignore[method-assign]
    flow.phase_licence()
    return flow.data["licence_runs"][licence]


def test_p18_a_target_missing_in_a_locked_run_is_no_grey_with_a_reason(monkeypatch: Any) -> None:
    """Durchsicht welle4 C-S1: „fehlt“ im gesperrten Lauf ist kein „grau mit Grund“.

    Fand ``next_click`` das Ziel im gesperrten Lauf nicht, schrieb der Lauf den
    Text der eigenen ``LookupError`` als Grund, und Prüfpunkt 18 las „nicht
    offen, Grund nicht leer“ als erfüllt — auch dann, wenn die Oberfläche eine
    schreibende Funktion in der Demo versteckt, statt sie auszugrauen
    (``kern.md``, „Die Lizenzgrenze“). Der Grund kommt nur noch aus dem grauen
    Ziel; fehlt es gesperrt und steht es freigeschaltet da, ist das ein Fund.
    """
    locked = _licence_run(monkeypatch, "needs_activation", missing=True, grey=None)
    offered = _licence_run(monkeypatch, "licensed", missing=False, grey=None)
    assert locked["reason"] == "", locked
    outcome = judge_licence({"needs_activation": locked, "licensed": offered}, complete=False)
    assert outcome.verdict == "fund", outcome
    assert any("needs_activation" in text and "fehlt" in text for text in _texts(outcome))
    assert {issue.severity for issue in outcome.issues} == {"mittel"}, outcome.issues
    # Fehlt es auch freigeschaltet, oder fehlt der freigeschaltete Lauf, ist nichts
    # gemessen: Dann erreichte der Prüfstand das Ziel gar nicht.
    lost = _licence_run(monkeypatch, "licensed", missing=True, grey=None)
    for runs in ({"needs_activation": locked}, {"needs_activation": locked, "licensed": lost}):
        assert judge_licence(runs, complete=False).verdict == "nicht_gelaufen", runs
    # Grau mit dem Grund aus der Kurzhilfe bleibt erfüllt.
    greyed = _licence_run(monkeypatch, "needs_activation", missing=False, grey="Ändern braucht")
    assert greyed["reason"] == "Ändern braucht", greyed
    outcome = judge_licence({"needs_activation": greyed, "licensed": offered}, complete=False)
    assert outcome.verdict == "erfuellt", outcome


def test_p18_a_writing_target_open_while_locked_is_a_rule_violation() -> None:
    """Durchsicht welle4 D-L3: „Schreibendes Ziel frei“ ist *mittel*, nicht *schwer*.

    Konzept §4: Schwer ist falsches Ergebnis, Datenverlust, Sackgasse, nicht
    auffindbar; ein offenes schreibendes Ziel trotz Sperre ist ein Regelverstoß
    (Lizenzgrenze, ``kern.md``) — und der Kern lehnt am Ende ohnehin ab, also
    ein Umweg. Die Funddatei führt FD-5, FD-26 und FD-28 ebenso; die
    Abhakliste entsteht aus dem Prüfstand. „Sperrgrund ohne Ausweg“ (V5) bleibt
    *mittel*: ein Fehlerweg ohne Handlung.
    """
    offered = {"writes": True, "state": "angeboten", "reason": ""}
    outcome = judge_licence({"needs_activation": offered, "licensed": offered}, complete=False)
    assert [(issue.text, issue.severity) for issue in outcome.issues] == [
        ("schreibendes Ziel frei trotz needs_activation", "mittel")
    ]
    locked = {"text": "Gesperrt.", "actions": [], "kind": "sperrgrund", "way_out": False}
    protocol = _protocol(lambda data: data.update(messages=[locked]))
    assert [issue.severity for issue in _criterion("V5", protocol).issues] == ["mittel"]


# --- Zeilen: Z3 am Prüfbericht (F-33) --------------------------------------------------------


def test_the_report_is_a_view_without_a_selection() -> None:
    """F-33: Der Prüfbericht braucht Körper mit Befunden, aber keinen gewählten — Z3 gilt nicht.

    Vorher trug er ``koerper:1``: Der Weg wählte den Körper, und der Reiter
    zum Bericht hieß ein Wegklick nach der Auswahl.
    """
    scenes = function_scenes.load_scenes()
    row = function_list.surface_rows(["report"], [], [], scenes)[0]
    assert function_list.selection_route(row, scenes) == ()
    protocol = _protocol(
        lambda data: data.update(
            row={**data["row"], "id": "report", "target": "report", "requirement": row.requirement},
            steps=[click_step("report", why="reiter"), click_step("report")],
        )
    )
    assert CRITERION_JUDGES["Z3"](protocol, sample_context()) is None


# --- Der Prüfstand: Weg, Übernehmen, Fehlfall, Lizenz, Zeilen (F-20 bis F-35) ------------------


def test_a_target_the_window_still_works_out_is_awaited_not_lost() -> None:
    """F-20: Solange das Fenster sagt, dass es ermittelt, ist ein fehlendes Ziel nicht verloren.

    Das Merkmalfenster rechnet seine Zeilen im Arbeiter; nach zwei Sekunden hieß
    *Bohrung ändern* „nicht auffindbar“, obwohl es danach dastand. Hier steht
    der Kopf erst nach fünf Sekunden da, und bis dahin sagt das Fenster, dass
    es ermittelt.
    """
    timer = FakeTimer()
    head = FakeWidget("kopf")

    class Late(FakePorts):
        def next_click(self, name: str) -> FakeClick:
            if timer.now < 5.0:
                raise LookupError(f"{name}: noch nicht da")
            self._last, self._last_name = FakeClick((0, 0, 80, 20), "left", "ziel", head), name
            return self._last

    ports = Late(timer, {})
    ports.pending_until = 5.0
    steps: list[dict[str, Any]] = []
    machine = run_machine(
        timer, [function_walk.Walk(ports, steps, 0.0).step("feature:resize_hole")]
    )
    assert machine.done and machine.finding is None and machine.error is None
    assert ports.pressed == [("kopf", (40, 10), "left")]


def test_a_window_that_works_out_forever_is_the_finding_no_response() -> None:
    """Neue Fundart: Ermittelt das Fenster länger als ``PENDING_S``, ist das ein Fund."""
    timer = FakeTimer()
    ports = FakePorts(timer, {})
    ports.pending_until = 10 * function_walk.PENDING_S
    steps: list[dict[str, Any]] = []
    machine = run_machine(
        timer, [function_walk.Walk(ports, steps, 0.0).step("feature:resize_hole")]
    )
    assert machine.finding is not None and machine.finding.kind == NO_RESPONSE, machine.finding
    assert steps[-1]["finding"] == NO_RESPONSE
    assert function_walk.PENDING_S <= steps[-1]["t"] < function_walk.PENDING_S + 1


def test_a_wait_for_an_effect_that_never_lands_is_the_finding_no_response() -> None:
    """Neue Fundart am Automaten: Eine Frist mit ``on_timeout`` endet als Fund, nicht als Fehler."""
    timer = FakeTimer()
    waiting = function_machine.Step("ergebnis steht", lambda machine: None, ready=lambda: False)
    waiting.timeout_s = 5.0
    waiting.on_timeout = lambda: function_machine.BenchFinding(NO_RESPONSE, "ergebnis", "nach 5 s")
    machine = run_machine(timer, [waiting])
    assert machine.error is None
    assert machine.finding is not None and machine.finding.kind == NO_RESPONSE


def test_a_window_command_with_inputs_is_taken_over_with_its_dialog() -> None:
    """F-25: *Parameter anlegen* tippt in den Dialog des Befehls und klickt *Anlegen*."""
    row = {
        "kind": "fensterbefehl",
        "target": "menu:menubar.parameter_anlegen",
        "spec": {"inputs": {"field:name": "breite", "field:value": 40.0}},
    }
    assert function_setup.default_apply_target(row) == "dialog.accept"
    assert function_setup.default_apply_target({**row, "spec": {}}) is None


def test_an_operation_row_aims_where_the_customer_works_it() -> None:
    """F-21: Merkmalshandlungen heißen ``feature:<op>``, Färben der Filamentwähler.

    *Bohrung setzen* am exakten Körper ist kein eigener Eingang, sondern
    derselbe Dialog — eine Zeile für beide.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()
    rows = {
        row.id: row for row in function_list.operation_rows(REGISTRY, function_scenes.load_scenes())
    }
    for name in ("move_feature", "rotate_feature", "resize_hole", "slot_hole", "push_face"):
        assert rows[name].target == f"feature:{name}", rows[name]
    for name in ("assign_slot", "clear_filament", "paint_slot"):
        assert rows[name].target == "filament.picker", rows[name]
    assert "drill_brep_hole" not in rows
    assert rows["drill_hole"].covers == ("drill_brep_hole", "drill_hole")
    assert rows["drill_hole"].target == "operation:drill_hole"


def test_the_search_counts_every_name_of_the_same_function() -> None:
    """F-27: *Auf Grundebene setzen* findet die Operation — das ist die Befundhandlung.

    Verglichen wurde die genaue Kennung: ``operation:place_on_bed`` auf Rang 1
    hieß an der Zeile ``finding.action:place_on_bed`` „nicht gefunden“.
    """
    from tools import function_surface

    hits = ["operation:create_sphere", "operation:place_on_bed"]
    finding_row = {"id": "finding.action:place_on_bed", "target": "finding.action:place_on_bed"}
    names = function_surface.search_names(None, finding_row)
    assert function_surface.search_rank(hits, names) == 2
    feature_row = {"id": "resize_hole", "kind": "operation", "target": "feature:resize_hole"}
    names = function_surface.search_names(None, feature_row)
    assert function_surface.search_rank(["operation:resize_hole"], names) == 1


def test_a_licence_refusal_is_writing_that_was_stopped() -> None:
    """F-35: Eine Absage an der Lizenzgrenze heißt, die Handlung wollte schreiben."""
    from app.core import activation
    from app.core.errors import ValidationError
    from tools import function_surface

    assert function_surface.licence_refusal(activation.LicenceRequired(action="change"))
    assert function_surface.licence_refusal(activation.DeviceActivationRequired(action="change"))
    assert not function_surface.licence_refusal(ValidationError(field="name", detail="x"))


def test_a_language_case_names_each_surface_picture_after_its_row() -> None:
    """F-31: Im Sprachfall trägt jedes Flächenbild Sprache und Zeile."""
    from tools import function_surface

    variant = function_setup.Variant.of({"set": "sprachen", "language": "fr"})
    first = function_surface.picture_label(variant, "drill_hole", "flaeche")
    second = function_surface.picture_label(variant, "plug_hole", "flaeche")
    assert first != second and first.startswith("flaeche-fr-drill_hole")
    zoll = function_setup.Variant.of({"set": "zoll", "unit": "in"})
    assert function_surface.picture_label(zoll, "drill_hole", "flaeche") == "flaeche-zoll"


def test_rows_without_a_way_to_their_surface_are_not_run() -> None:
    """F-32: Ohne Szene mit ihrem Befund oder ohne Klick, der ihr Fenster öffnet, kein Lauf."""
    from tools import function_surface

    assert function_surface.without_way({"target": "finding.action:x", "start_scene": ""})
    assert function_surface.without_way({"target": "dialog:about_dialog", "start_scene": "leer"})
    assert function_surface.without_way({"target": "meldung:show_error", "start_scene": "leer"})
    opened = {
        "target": "dialog:about_dialog",
        "start_scene": "leer",
        "spec": {"route": [{"target": "menu:menubar.ueber_solidon"}]},
    }
    assert function_surface.without_way(opened) == ""
    assert (
        function_surface.without_way({"target": "operation:drill_hole", "start_scene": "q"}) == ""
    )


def _flow(spec: dict[str, Any], states: dict[str, Any] | None = None) -> Any:
    """Ein Funktionsfall ohne Fenster: nur, was die Phase bis zu ihren Schritten braucht."""
    from tools.function_protocol import empty_protocol

    flow = object.__new__(function_bench.FunctionFlow)
    row = {"id": "finding.action:place_on_bed", "target": "finding.action:place_on_bed"}
    flow.row = {**row, "spec": spec}
    flow.spec = spec
    flow.scene_key = "unter_dem_bett.netz"
    flow.apply_target = None
    flow.data = empty_protocol(flow.row, {}, {})
    flow.data["states"] = states or {}
    flow.walker = function_walk.Walk(FakePorts(FakeTimer(), {}), [], 0.0)
    return flow


def test_the_revision_needs_a_new_step_with_values() -> None:
    """F-23: Nur eine Zeile, die einen Schritt mit Werten anlegt, wird nachträglich geändert.

    *Parameter anlegen* legt keinen Schritt an; vorher änderte der Prüfstand den
    letzten Schritt der Szene und hielt die Karte der Auswahl für den Dialog.
    """
    same = {"before": {"ops": ["create_brep_box"]}, "applied": {"ops": ["create_brep_box"]}}
    flow = _flow({}, same)
    flow.reset = lambda: (_ for _ in ()).throw(AssertionError("kein Lauf ohne neuen Schritt"))
    flow.phase_revise()
    assert flow.data["unmeasured"]["revise"] == "die Zeile legt keinen Schritt im Verlauf an"
    assert flow.data["revise"] is None


def test_the_fault_case_walks_its_own_scene_and_way() -> None:
    """F-34, F-24: Der Fehlfall fährt seine Startszene, seinen Weg und klickt während der Rechnung.

    Vorher nahm der Prüfstand den Weg der Zeile und suchte ``field:edge`` im
    Prüfbericht — „nicht auffindbar“, und Prüfpunkt 7 hieß „keine Meldung“.
    """
    fault = {
        "start_scene": "unter_dem_bett_langsam",
        "route": [{"target": "history.row:4", "button": "double"}],
        "inputs": {"field:edge": 0.14},
        "during": "rechnung",
        "expected": "sperrgrund",
    }
    flow = _flow({"fault_case": fault})
    scenes: list[str] = []
    walked: list[str] = []
    flow.fault_scene = lambda key: scenes.append(key) or True
    flow.path_steps = lambda: [function_machine.Step("weg zu finding.action:place_on_bed", None)]
    flow.input_steps = lambda inputs: [
        function_machine.Step(f"tippen {name}", None) for name in inputs
    ]
    flow.run_steps = lambda label, steps: walked.extend(step.name for step in steps) or True
    flow.picture = lambda label: None
    flow.session = type("Session", (), {"last_result": None})()
    flow.phase_fault()
    assert scenes == ["unter_dem_bett_langsam"]
    # Die Rechnung muss zu sehen sein, bevor die Handlung geklickt wird; stößt
    # die Eingabe keine an, tut es der Hauptknopf des offenen Dialogs.
    assert walked[:7] == [
        "weg zu history.row:4",
        "tippen field:edge",
        "dialog merken",
        "rechnet",
        "anstoßen",
        "rechnung gesehen",
        "weg zu finding.action:place_on_bed",
    ], walked


def test_the_surface_follows_the_kind_of_target(monkeypatch: Any) -> None:
    """F-30: Die Fläche einer Befundhandlung ist der Prüfbericht, eines Werkzeugs seine Leiste.

    Vorher war sie für jede Zeile ohne Dialog die Karte der Auswahl oder das
    ganze Hauptfenster — Wörter über dem ersten Feld, Hauptknöpfe und Abstände
    des ganzen Fensters standen an jeder Befundhandlung. Ein offener Dialog geht
    vor.
    """
    from app.ui import guide_targets
    from tools import function_surface

    class Shown:
        def isVisible(self) -> bool:  # noqa: N802 - Qts Name
            return True

    shown: dict[str, Any] = {
        "report": Shown(),
        "handle:bar.split": Shown(),
        "selection": Shown(),
    }

    def widget_for(window: Any, name: str) -> Any:
        if name in shown:
            return shown[name]
        raise guide_targets.MissingTargetError(name)

    monkeypatch.setattr(guide_targets, "widget_for", widget_for)
    window = object()
    surface = function_surface.surface_for
    assert surface(window, "finding.action:place_on_bed") is shown["report"]
    assert surface(window, "report") is shown["report"]
    assert surface(window, "tool:split") is shown["handle:bar.split"]
    assert surface(window, "feature:resize_hole") is shown["selection"]
    shown["dialog"] = Shown()
    assert surface(window, "finding.action:place_on_bed") is shown["dialog"]


def test_a_grey_button_gives_the_reason_its_tooltip_shows(monkeypatch: Any) -> None:
    """F-34: Der Sperrgrund ist die Kurzhilfe des grauen Knopfs, nicht seine alte Beschreibung.

    Im Fehlfall von *Auf das Bett setzen* sperrt der Bericht die Handlung während
    der Rechnung und nennt den Grund in der Kurzhilfe; die Beschreibung trägt
    weiter die Nebenfolge des offenen Knopfs. Der Prüfstand las die Nebenfolge
    als Meldung.
    """
    from app.ui import guide_targets
    from tools import function_surface

    class Grey:
        def isEnabled(self) -> bool:  # noqa: N802 - Qts Name
            return False

        def toolTip(self) -> str:  # noqa: N802 - Qts Name
            return "Erst nach der Berechnung — der Befund gehört zum vorigen Stand."

        def accessibleDescription(self) -> str:  # noqa: N802 - Qts Name
            return "Nebenfolge: Senkt den Körper bis auf das Bett."

    monkeypatch.setattr(guide_targets, "widget_for", lambda window, name: Grey())
    reason = function_surface.grey_reason(object(), "finding.action:place_on_bed")
    assert reason == "Erst nach der Berechnung — der Befund gehört zum vorigen Stand."


def test_hovering_takes_a_facing_feature_per_kind_and_names_what_it_missed() -> None:
    """F-28: Je Art ein Merkmal mit zugewandter Stelle; ohne eines ist die Art nicht gemessen.

    Vorher fuhr der Prüfstand das erste Merkmal jeder Art an; lag es abgewandt,
    scheiterte das Überfahren, und der leere Hinweis hieß „Art face ohne Name
    und Maß“.
    """
    from types import SimpleNamespace

    def feature(kind: str) -> Any:
        return SimpleNamespace(kind=kind)

    objects = {
        "obj_1": SimpleNamespace(
            features={
                "face_1": feature("face"),
                "face_2": feature("face"),
                "hole_1": feature("hole"),
            }
        )
    }

    def next_click(name: str) -> Any:
        if name != "view:obj_1.face_2":
            raise LookupError(f"{name}: keine zugewandte Stelle")
        return SimpleNamespace(rect=None, why="ziel", target=name)

    hovered: list[str] = []
    flow = object.__new__(function_bench.FunctionFlow)
    flow.session = SimpleNamespace(
        last_result=SimpleNamespace(scene=SimpleNamespace(objects=objects))
    )
    flow.window = SimpleNamespace(viewport=SimpleNamespace(renderer=object(), toolTip=lambda: ""))
    flow.ports = SimpleNamespace(next_click=next_click)
    flow.data = {"unmeasured": {}}
    flow.run_steps = lambda label, steps: hovered.append(label) or True  # type: ignore[method-assign]
    flow.phase_hover()
    assert hovered == ["überfahren view:obj_1.face_2"]
    assert flow.data["hover_labels"] == [{"kind": "face", "label": ""}]
    assert "hole" in flow.data["unmeasured"]["hover_labels"]


def test_an_action_shown_in_the_view_is_typed_there_and_taken_there(
    monkeypatch: Any,
) -> None:
    """F-20, N2: Steht die Handlung im Bild, klickt der Fall keinen Kopf im Merkmalfenster.

    Er schreibt den Schritt als Ziel in der Zone ``ansicht``, tippt ins Maßfeld
    (``measure.field:<feld>``) und übernimmt mit dem Knopf der Maßgruppe
    (``measure.apply``, vorher ohne Namen: die Eingabetaste). Steht sie im
    Merkmalfenster, geht der Weg wie bisher über den Kopf und *Übernehmen*.
    """
    from tools import function_surface

    shown = {"in_view": True}
    monkeypatch.setattr(function_surface, "in_view", lambda window, inputs: shown["in_view"])
    monkeypatch.setattr(
        function_surface,
        "field_name",
        lambda window, name: "measure.field:diameter" if shown["in_view"] else name,
    )
    flow = _flow({"inputs": {"feature.field:resize_hole.diameter": 8.0}})
    flow.row = {**flow.row, "target": "feature:resize_hole", "route": []}
    flow.apply_target = "feature.apply"
    flow.window = None
    flow.widget = lambda name: None  # type: ignore[method-assign]
    flow.variant = function_setup.Variant.of({})
    # Ohne Anwendung keine Tastenfolge (QKeySequence): Der Weg allein zählt hier.
    flow.mark_all_step = lambda target: function_machine.Step(  # type: ignore[method-assign]
        f"alles markieren {target}", lambda machine: None
    )
    machine = function_machine.StepMachine(FakeTimer().schedule, FakeTimer().clock)
    for case in (True, False):
        shown["in_view"] = case
        flow.walker.steps.clear()
        names: list[str] = []
        (head,) = flow.path_steps()
        typed = flow.input_steps(flow.spec["inputs"])
        for step in (head, typed[0], flow.apply_step()):
            machine.queue, machine.index = [], 0
            step.act(machine)
            names += [inserted.name for inserted in machine.queue]
        if case:
            assert flow.walker.steps[-1]["zone"] == "ansicht"
            assert flow.walker.steps[-1]["target"] == "feature:resize_hole"
            assert names == [
                "weg zu measure.field:diameter",
                "alles markieren measure.field:diameter",
                "tippen measure.field:diameter",
                "weg zu measure.apply",
            ], names
        else:
            assert names == [
                "weg zu feature:resize_hole",
                "weg zu feature.field:resize_hole.diameter",
                "alles markieren feature.field:resize_hole.diameter",
                "tippen feature.field:resize_hole.diameter",
                "weg zu feature.apply",
            ], names


def test_the_licence_run_finds_an_action_shown_in_the_view(monkeypatch: Any) -> None:
    """F-20: Im Lizenzlauf steht *Bohrung ändern* mit Bild offen in der Maßgruppe.

    Der Lauf fragte den Kopf im Merkmalfenster gleich nach der Auswahl; mit Bild
    ist er verborgen, und jeder Lizenzzustand, auch „licensed“, hieß „fehlt“ —
    Prüfpunkt 18 meldete eine Sperre, die es nicht gab. Gefragt wird jetzt das
    Feld im Bild, und der Weg geht wie im Hauptlauf.
    """
    from tools import function_surface

    monkeypatch.setattr(function_surface, "in_view", lambda window, inputs: True)
    monkeypatch.setattr(
        function_surface, "field_name", lambda window, name: "measure.field:diameter"
    )
    monkeypatch.setattr(function_surface, "grey_reason", lambda window, name: None)

    class Signal:
        def connect(self, slot: Any) -> None:
            pass

        def disconnect(self, slot: Any) -> None:
            pass

    field = FakeWidget("measure.field:diameter")
    flow = _flow({"inputs": {"feature.field:resize_hole.diameter": 8.0}})
    flow.row = {**flow.row, "kind": "operation", "target": "feature:resize_hole", "route": []}
    flow.walker = function_walk.Walk(
        FakePorts(
            FakeTimer(),
            {"measure.field:diameter": [FakeClick((0, 0, 9, 9), "left", "ziel", field)]},
        ),
        [],
        0.0,
    )
    flow.ports = flow.walker.ports
    flow.window = None
    flow.session = type("Session", (), {"failed": Signal()})()
    flow.variant = function_setup.Variant.of({})
    flow.widget = lambda name: None  # type: ignore[method-assign]
    flow.scene_now = lambda: {"ops": ["create_brep_box", "drill_hole"]}  # type: ignore[method-assign]
    flow.mark_all_step = lambda target: function_machine.Step(  # type: ignore[method-assign]
        f"alles markieren {target}", lambda machine: None
    )
    flow.effect_steps = lambda label: (  # type: ignore[method-assign]
        [function_machine.Step(f"{label} merken", lambda machine: None)],
        lambda: True,
    )
    ran: list[list[str]] = []
    flow.run_steps = lambda phase, steps: ran.append([step.name for step in steps]) or True  # type: ignore[method-assign]
    flow.phase_licence()
    run = flow.data["licence_runs"][flow.variant.licence]
    assert run["state"] == "angeboten", run
    assert "handlung feature:resize_hole" in ran[-1], ran


def test_a_whole_scene_operation_starts_at_a_chosen_body() -> None:
    """F-32: *Druckoptimal ausrichten* steht in der Karte am gewählten Körper, nicht ohne Auswahl.

    Vorher war der Weg einer Operation über die ganze Szene leer, und der
    Sprachfall fand „keinen Knopf und keine Menüzeile“. Der Prüfbericht als
    Ansicht bleibt ohne Auswahl (F-33).
    """
    scenes = function_scenes.load_scenes()
    route = function_list.route_for("szene", "zwei_koerper.exakt", scenes)
    assert [step["target"] for step in route] == ["tree.row:obj_1"]
    assert function_list.route_for("ansicht", "quader.exakt", scenes) == ()


def test_the_scene_names_are_its_bodies_and_its_project() -> None:
    """F-10: Was die Szene benennt — Körper aus Dateien, das Projekt nach seiner Datei."""
    from pathlib import Path
    from types import SimpleNamespace

    from tools import function_surface

    objects = {"obj_1": SimpleNamespace(name="cube_clean"), "obj_2": SimpleNamespace(name="")}
    session = SimpleNamespace(
        last_result=SimpleNamespace(scene=SimpleNamespace(objects=objects)),
        path=Path("F:/fall/scenes/unter_dem_bett.netz.p3d"),
    )
    assert function_surface.scene_names(session) == ["cube_clean", "unter_dem_bett.netz"]


def test_a_message_after_the_click_is_not_the_surface_of_the_row() -> None:
    """Z2, Z5, E6: Eine Meldung oder Frage ist nie die Fläche einer Zeile, außer sie ist die Zeile.

    Der Prüfstand merkt den Dialog nach dem Klick als eigene Fläche; vorher nahm
    er davon nur rohe Qt-Fenster aus. Seit FD-21 kommen Fehler als
    ``MessageDialog`` — als „eigene Fläche“ wären sie erlaubt, und Z2 sähe sie
    nicht. Ebenso eine Rückfrage (``AskDialog``).
    """
    from tools import function_surface

    message = type("MessageDialog", (), {})()
    question = type("AskDialog", (), {})()
    raw = type("QMessageBox", (), {})()
    own = type("ParameterDialog", (), {})()
    operation = {"target": "operation:drill_hole", "source": "register"}
    for window in (message, question, raw):
        assert not function_surface.own_surface(operation, window), type(window).__name__
    assert function_surface.own_surface(operation, own)
    assert function_surface.own_surface({"target": "message:recovery"}, raw)
    assert function_surface.own_surface({"target": "dialog:AskDialog"}, question)
    assert function_surface.own_surface({"target": "", "source": "startablauf"}, raw)


def test_v5_a_lock_reason_needs_no_button_but_a_way_out() -> None:
    """V5 (Entscheidung Koordinator): Ein Sperrgrund ist keine Meldung, er nennt aber den Ausweg.

    Vorher galt jeder graue Knopf mit Grund als „Meldung ohne Handlung“; jetzt
    ist nur der Sperrgrund ohne Ausweg ein Fund. Die Grenzablehnung nennt die
    Grenze und braucht keinen Knopf.
    """
    protocol = sample_protocol()
    protocol["messages"] = [
        {
            "text": "Dafür braucht Solidon einen Lizenzschlüssel (Hilfe → Solidon freischalten …).",
            "actions": [],
            "kind": "sperrgrund",
            "way_out": True,
        },
        {"text": "0,1 mm liegt unter 0,5 mm.", "actions": [], "kind": "grenzablehnung"},
    ]
    assert CRITERION_JUDGES["V5"](protocol, sample_context()).issues == ()
    protocol["messages"].append(
        {
            "text": "Der Testzeitraum ist abgelaufen.",
            "actions": [],
            "kind": "sperrgrund",
            "way_out": False,
        }
    )
    outcome = CRITERION_JUDGES["V5"](protocol, sample_context())
    assert [issue.text for issue in outcome.issues] == [
        "Sperrgrund ohne Ausweg: „Der Testzeitraum ist abgelaufen.“"
    ]


def test_p7_compares_the_refusal_with_the_expected_kind() -> None:
    """Prüfpunkt 7 (Entscheidung Koordinator): Die Absage hat die Art, die die Spezifikation nennt.

    Gezählt werden nur die Meldungen des Fehlfalls; ein Sperrgrund der Fläche
    davor täuscht keinen erwarteten Sperrgrund vor.
    """
    protocol = sample_protocol()
    protocol["spec"]["fault_case"]["expected"] = "sperrgrund"
    surface_lock = {"text": "Gesperrt (Hilfe → Solidon freischalten …).", "actions": []}
    protocol["messages"] = [
        {**surface_lock, "kind": "sperrgrund", "way_out": True},
        {"text": "Das ging nicht.", "actions": [], "kind": "meldung", "phase": FAULT_PHASE},
    ]
    outcome = POINT_JUDGES[7](protocol, sample_context(), {})
    assert any(issue.text == "erwartet sperrgrund, gemessen meldung" for issue in outcome.issues), (
        outcome
    )
    protocol["messages"][1]["kind"] = "sperrgrund"
    protocol["messages"][1]["way_out"] = True
    outcome = POINT_JUDGES[7](protocol, sample_context(), {})
    assert not [issue for issue in outcome.issues if "erwartet" in issue.text], outcome


def test_the_measure_group_counts_only_for_the_action_it_carries(monkeypatch: Any) -> None:
    """N5: Die Maßgruppe im Bild ist die Fläche der Zeile nur, wenn sie deren Handlung trägt.

    An einer gesetzten Bohrung trägt sie mit Bild *Bohrung im ursprünglichen
    Schritt ändern* (``drill_hole``); deren Durchmesser heißt wie der von *Bohrung
    ändern*. Der Prüfstand tippte dort für ``resize_hole``, änderte den
    Ursprungsschritt samt Materialtoleranz und maß 8,2 mm statt 8 mm.

    Gefragt wird die Gruppe selbst (``measure_op``), nicht die scharfe Handlung:
    Die beiden fielen an einer erkannten Bohrung auseinander (FD-34), und der
    Prüfstand fand die Zeile dort nicht (FD-29).
    """
    from tools import function_surface

    shown = {"measure.field:diameter"}
    monkeypatch.setattr(
        function_surface, "_shown", lambda window, name: object() if name in shown else None
    )

    class Panel:
        measure_op: str | None = "drill_hole"
        armed: tuple[str, dict[str, Any]] = ("drill_hole", {})

        def preview_values(self) -> tuple[str, dict[str, Any]]:
            return self.armed

    window = type("Window", (), {"feature_panel": Panel()})()
    name = "feature.field:resize_hole.diameter"
    assert function_surface.field_name(window, name) == name
    assert not function_surface.in_view(window, [name])
    window.feature_panel.measure_op = "resize_hole"
    window.feature_panel.armed = ("move_feature", {})
    assert function_surface.field_name(window, name) == "measure.field:diameter"
    assert function_surface.in_view(window, [name])
    assert function_surface.op_in_view(window) == "resize_hole"


# --- Prüfpunkt 13: eine Kante (Durchsicht welle4 C-M4) ---------------------------------------


def _matrix_flow(script: dict[str, list[FakeClick]]) -> Any:
    """Ein Fall für die Matrix: ein Quader mit einer Fläche, die Oberfläche als Drehbuch."""
    from types import SimpleNamespace

    body = SimpleNamespace(features={"face_top": SimpleNamespace(kind="face")})
    flow = _flow({})
    flow.row = {**flow.row, "target": "edge:fillet_edges"}
    flow.session = SimpleNamespace(
        last_result=SimpleNamespace(scene=SimpleNamespace(objects={"obj_1": body}))
    )
    flow.walker = function_walk.Walk(FakePorts(FakeTimer(), script), [], 0.0)
    flow.ports = flow.walker.ports
    flow.reset = lambda: True
    flow.offer_state = lambda target, label: {"state": "angeboten", "reason": "", "effective": True}
    return flow


def test_the_matrix_chooses_an_edge_in_the_view_after_its_body() -> None:
    """Durchsicht welle4 C-M4: Die Stufe „eine Kante“ lief nie.

    Die Matrix suchte Merkmale der Art ``edge``, die die Erkennung nicht
    liefert; eine Kante ist kein Merkmal, sondern eine Stelle im Bild
    (``view.edge:<körper>``). Gewählt wird sie wie vom Kunden: erst der
    Körper, dann der Klick auf seine Kante (gestufte Tiefe, §18.5). Hat der
    Körper keine sichtbare Kante, ist die Stufe nicht herstellbar — ohne Klick
    ins Leere, der „nicht auffindbar“ gegen die Anwendung schriebe.
    """
    edge = FakeWidget("viewport", zone="ansicht")
    flow = _matrix_flow({"view.edge:obj_1": [FakeClick((0, 0, 5, 5), "left", "ziel", edge)]})
    walked: dict[str, list[str]] = {}

    def run_steps(label: str, steps: list[Any]) -> bool:
        walked[label] = [step.name for step in steps]
        return True

    flow.run_steps = run_steps
    flow.phase_matrix()
    assert flow.data["matrix"]["eine_kante"]["state"] == "angeboten", flow.data["matrix"]
    # Gelesen wird erst, wenn die Zeile an der Kante steht oder so lange ohne Weg
    # blieb wie auf dem Hauptweg — sofort gefragt hieß sie „fehlt“.
    assert walked["matrix eine_kante auswahl"] == [
        "weg zu tree.row:obj_1",
        "weg zu view.edge:obj_1",
        "edge:fillet_edges steht",
    ], walked
    plain = _matrix_flow({})
    plain.run_steps = run_steps
    plain.phase_matrix()
    assert plain.data["matrix"]["eine_kante"]["state"] == "nicht herstellbar", plain.data["matrix"]


def test_e1_counts_an_edge_in_the_view_as_part_of_the_selection() -> None:
    """Durchsicht welle4 C-M4: Der Klick auf die Kante im Bild gehört zur Startauswahl.

    Ohne Auswahlweg in der Zeile liest E1 die Startauswahl aus den führenden
    Auswahlklicks; ``view.edge:`` war keiner, und die Kante zählte als Klick
    danach, an der Grenze für einen Körper (drei) statt für eine Stelle (zwei).
    """
    steps = [
        click_step("tree.row:obj_1", "baum"),
        click_step("view.edge:obj_1", "ansicht"),
        click_step("edge:fillet_edges"),
        click_step("feature.apply", phase=APPLY),
    ]
    row = {"id": "edge:fillet_edges", "kind": "bedienflaeche", "target": "edge:fillet_edges"}
    protocol = _protocol(lambda data: data.update(row=row, steps=steps))
    assert _criterion("E1", protocol).measurement == {"clicks": 2, "limit": 2}


def test_an_edge_operation_row_aims_at_its_row_at_the_edge() -> None:
    """Durchsicht welle4 C-M4 am Prüfstand: An der gewählten Kante steht *Verrunden* als
    Kantenzeile im Merkmalfenster (``edge:fillet_edges``), nicht als Knopf der Karte.

    Wie F-21 für die Merkmalshandlungen: Mit dem Kantenklick im Auswahlweg suchte
    der Hauptweg ``operation:fillet_edges`` und fand „kein Knopf zu sehen und keine
    Menüzeile“ — „nicht auffindbar“ gegen die Anwendung (Prüfstandlauf am
    13.10.2026, Fall 001). Die Suche zählt den Treffer ``operation:<op>`` weiter
    (``function_surface.search_names``).
    """
    from app.core.bootstrap import load_operations
    from app.core.guides import action_key
    from app.core.perceive.actions import edge_actions
    from app.core.registry import REGISTRY

    load_operations()
    rows = {
        row.id: row for row in function_list.operation_rows(REGISTRY, function_scenes.load_scenes())
    }
    own = {action.op for action in edge_actions("probe") if action_key(action) == action.op}
    assert own >= {"fillet_edges", "chamfer_edges"}, own
    for name in own:
        assert rows[name].target == f"edge:{name}", rows[name]
        assert rows[name].requirement == "kante", rows[name]


# --- Rücksetzen vor jeder Messung (Durchsicht welle4 C-L15) ---------------------------------


def test_the_matrix_measures_nothing_where_the_start_scene_was_not_made() -> None:
    """C-L15: ``phase_matrix`` las den Ausgang von ``reset()`` nicht.

    Misslang das Zurücksetzen, maß die Stufe an dem, was die vorige liegen ließ —
    eine andere Lage. Jetzt ist sie nicht herstellbar, mit Grund.
    """
    edge = FakeWidget("viewport", zone="ansicht")
    flow = _matrix_flow({"view.edge:obj_1": [FakeClick((0, 0, 5, 5), "left", "ziel", edge)]})
    flow.reset = lambda: False
    flow.run_steps = lambda label, steps: True
    flow.phase_matrix()
    states = {stage: entry["state"] for stage, entry in flow.data["matrix"].items()}
    assert set(states.values()) == {"nicht herstellbar"}, states
    assert (
        flow.data["matrix"]["ein_koerper"]["reason"] == "die Startszene ließ sich nicht herstellen"
    )


def test_the_revision_measures_no_way_whose_start_scene_was_not_made() -> None:
    """C-L15: ``phase_revise`` las den Ausgang von ``reset()`` nicht — kein Weg ohne Startszene."""
    applied = {"ops": ["create_brep_box", "drill_hole"]}
    flow = _flow({}, {"before": {"ops": ["create_brep_box"]}, "applied": applied})
    flow.reset = lambda: False
    flow.run_steps = lambda label, steps: (_ for _ in ()).throw(
        AssertionError(f"{label} lief ohne Startszene")
    )
    flow.phase_revise()
    assert flow.data["revise"] in (None, []), flow.data["revise"]
    assert any("Startszene" in error for error in flow.data["errors"]), flow.data["errors"]


# --- Sperrgrund im Fehlfall (Durchsicht welle4 C-L1, C-L2) ----------------------------------


def test_v5_a_way_out_is_a_menu_way_or_the_whole_words_of_a_button() -> None:
    """C-L2: Ein Ausweg ist ein Menüweg „Menü → Zeile“ oder ein offener Knopf mit ganzen Wörtern.

    Vorher genügte ein Teilstring irgendeines offenen Knopf- oder Menütexts:
    „Dateien“ nannte den Knopf *Datei*, und ein Satz mit „Öffnen“ den Menüeintrag
    *Öffnen* ohne sein Menü — beides kein Weg, den der Kunde findet.
    """
    from tools.function_capture import names_a_way_out

    menus = [("&Hilfe", "Solidon freischalten …"), ("&Datei", "Öffnen …")]
    buttons = ["Datei", "Abbrechen", "OK"]
    named = "Dafür braucht Solidon einen Lizenzschlüssel (Hilfe → Solidon freischalten …)."
    assert names_a_way_out(named, menus, buttons)
    assert names_a_way_out("Wählen Sie Abbrechen und dann neu.", menus, buttons)
    for reason in ("Dateien fehlen noch.", "Öffnen geht hier nicht.", "OK geht nicht."):
        assert not names_a_way_out(reason, menus, buttons), reason


def test_p7_reads_the_lock_reason_of_the_target_of_the_row(monkeypatch: Any) -> None:
    """C-L1: Im Fehlfall zählt der Sperrgrund des Ziels der Zeile, nicht jeder graue Knopf.

    „Erwartet Sperrgrund“ war erfüllt, sobald irgendein fremder Knopf grau mit
    Kurzhilfe stand. Jetzt liest der Fehlfall ``grey_reason`` an den Zielen der
    Zeile; die übrigen Meldungen der Oberfläche bleiben.
    """
    from app.ui import guide_targets
    from tools import function_capture, function_surface

    foreign = {"text": "Fremder Knopf gesperrt.", "actions": [], "kind": "sperrgrund"}
    status = {"text": "Berechnet …", "actions": [], "kind": "meldung"}
    monkeypatch.setattr(function_capture, "message_entries", lambda window: [foreign, status])
    # Der Ausweg wird am grauen Element selbst gefragt — die Felder seiner Fläche
    # zählen (FD-31).
    element = object()
    monkeypatch.setattr(guide_targets, "widget_for", lambda window, name: element)
    monkeypatch.setattr(
        function_capture, "way_out", lambda window, reason, widget=None: widget is element
    )
    reasons = {"finding.action:place_on_bed": None}
    monkeypatch.setattr(function_surface, "grey_reason", lambda window, name: reasons.get(name))
    targets = ["finding.action:place_on_bed"]
    assert function_surface.fault_messages(None, targets) == [status]
    reasons["finding.action:place_on_bed"] = "Während der Neuberechnung gesperrt."
    assert function_surface.fault_messages(None, targets) == [
        status,
        {
            "text": "Während der Neuberechnung gesperrt.",
            "actions": [],
            "kind": "sperrgrund",
            "way_out": True,
        },
    ]


def test_the_fault_case_asks_for_the_lock_reason_at_its_own_targets(monkeypatch: Any) -> None:
    """C-L1 am Prüfstand: ``phase_fault`` liest die Meldungen über ``fault_messages`` an den
    Zielen der Zeile — ihrem Ziel und dem, womit sie übernommen wird."""
    from types import SimpleNamespace

    from tools import function_surface

    asked: list[list[str]] = []
    lock = {"text": "Gesperrt.", "actions": [], "kind": "sperrgrund", "way_out": True}

    def told(window: Any, targets: Any) -> list[dict[str, Any]]:
        asked.append(list(targets))
        return [lock]

    monkeypatch.setattr(function_surface, "fault_messages", told)
    monkeypatch.setattr(function_surface, "open_dialog", lambda window: None)
    monkeypatch.setattr(function_surface, "report_findings", lambda session: {})
    fault = {"route": [{"target": "history.row:4"}], "expected": "sperrgrund"}
    flow = _flow({"fault_case": fault})
    flow.fault_scene = lambda key: True
    flow.apply_target = "dialog.accept"
    flow.input_steps = lambda inputs: []
    flow.picture = lambda label: None
    flow.session = SimpleNamespace(last_result=None)
    flow.window = None

    def run_steps(label: str, steps: list[Any]) -> bool:
        for step in steps:
            if step.name == "meldung lesen":
                step.act(None)
        return True

    flow.run_steps = run_steps
    flow.phase_fault()
    assert asked and asked[-1] == ["finding.action:place_on_bed", "dialog.accept"], asked
    assert flow.data["messages"] == [{**lock, "phase": FAULT_PHASE}], flow.data["messages"]


# --- Vorbereitung mit Nachweis (Durchsicht welle4 C-L3) --------------------------------------


def test_a_preparation_waits_for_the_findings_its_scene_promises(
    monkeypatch: Any, tmp_path: Any
) -> None:
    """C-L3: Nach Einfügemarke, Export oder *Automatisch teilen* prüfte niemand, ob die
    zugesagten Befunde im Prüfbericht stehen; ein Fehlschlag landete als „nicht
    auffindbar“ bei der Anwendung. Jetzt wartet die Vorbereitung auf
    ``promises.findings`` und hält sonst mit „Vorbereitung nicht hergestellt“ an.
    """
    from tools import function_surface

    flow = _flow({})
    flow.setup = function_setup.scene_setup("export_gemischt")
    flow.folder = tmp_path
    steps = flow.preparation_steps()
    names = [step.name for step in steps]
    assert names[-2:] == ["befunde der vorbereitung", "vorbereitung geprüft"], names
    shown: set[str] = set()
    monkeypatch.setattr(function_surface, "shown_findings", lambda window: shown)
    flow.window = None
    try:
        steps[-1].act(None)
    except RuntimeError as error:
        assert "Vorbereitung nicht hergestellt" in str(error) and "export.needs_solid" in str(error)
    else:
        raise AssertionError("ohne den zugesagten Befund ging die Vorbereitung durch")
    shown.add("export.needs_solid")
    steps[-1].act(None)
    plain = _flow({})
    plain.setup = function_setup.scene_setup("quader.exakt")
    plain.folder = tmp_path
    assert plain.preparation_steps() == []


# --- Aufnahme nur im Stillstand (Durchsicht welle4 C-L10) ------------------------------------


def test_a_surface_that_never_stood_still_is_not_measured(monkeypatch: Any) -> None:
    """C-L10: Stand die Fläche nach der Frist nicht still, wurde trotzdem aufgenommen und
    geurteilt; den Vermerk ``still:`` las kein Urteil. Jetzt bleiben die Aufnahmefelder
    ungemessen — auch die Rollleisten, die sonst die Fenstergröße als gemessen zählten.
    """
    import itertools
    import time

    from tools import function_capture

    ticks = itertools.count()
    monkeypatch.setattr(function_bench, "surface_signature", lambda root: (next(ticks),))
    entries = {"layout": [{"group": "g"}], "scrollbars": [{"surface": "s"}]}
    monkeypatch.setattr(function_capture, "sheet_snapshot", lambda root, theme, size: dict(entries))
    monkeypatch.setattr(function_capture, "text_entries", lambda root: [{"text": "t"}])
    monkeypatch.setattr(function_capture, "field_entries", lambda root: [{"field": "f"}])
    monkeypatch.setattr(function_capture, "empty_states", lambda window: [])
    flow = _flow({})
    flow.window = None
    flow.variant = function_setup.Variant.of({})
    flow.window_size = lambda: (1920, 1009)  # type: ignore[method-assign]
    flow.restless = None
    step = flow.still_step("fläche steht still", lambda: None, at_most_s=0.05)
    assert step.ready is not None
    for _ in range(200):
        if step.ready():
            break
        time.sleep(0.005)
    flow.capture_surface(None)
    assert flow.data["layout"] is None and flow.data["texts"] is None, flow.data
    assert flow.data["scrollbars"] is None, flow.data["scrollbars"]
    assert "ohne Stillstand" in flow.data["unmeasured"]["layout"], flow.data["unmeasured"]
    # Steht sie still, wird aufgenommen.
    monkeypatch.setattr(function_bench, "surface_signature", lambda root: ("still",))
    calm = flow.still_step("fläche steht still", lambda: None, at_most_s=5.0)
    assert calm.ready is not None
    for _ in range(400):
        if calm.ready():
            break
        time.sleep(0.005)
    flow.capture_surface(None)
    assert flow.data["layout"] == entries["layout"] and flow.data["texts"] == [{"text": "t"}]


def test_v5_the_title_of_an_open_field_of_the_surface_is_a_way_out() -> None:
    """FD-31, Entscheidung Koordinator: *Übernehmen* der Maßgruppe ist vor der ersten
    Eingabe grau und sagt „Erst „<Feldtitel>“ ändern, dann übernehmen.“ — das Feld ist
    der Ausweg, als ganzes Wort genannt. Welche Felder offen auf derselben Fläche
    stehen, liest ``surface_field_titles`` (Fenstertest); hier die Urteilsregel.
    """
    from tools.function_capture import names_a_way_out

    reason = "Erst „Durchmesser“ ändern, dann übernehmen."
    assert names_a_way_out(reason, [], [], fields=["Durchmesser:"])
    assert not names_a_way_out(reason, [], [])
    assert not names_a_way_out("Erst die Durchmessers ändern.", [], [], fields=["Durchmesser"])
