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

from tools import function_list, function_scenes
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
from tools.function_points import judge_case, judge_licence
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
        "needs_activation": {"writes": False, "enabled": True, "reason": ""},
        "licensed": {"writes": True, "enabled": True, "reason": ""},
    }
    outcome = judge_licence(runs, complete=True)
    assert outcome.verdict == "fund", outcome
    assert any("needs_activation" in text for text in _texts(outcome))


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
