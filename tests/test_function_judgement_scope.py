"""Was Stufe A an einer Zeile misst, gilt nur, wo die Zeile es hat (Paket F8, RM-737).

Ein Prüfpunkt, der einen Zustand verlangt, den die Zeile nicht hat, bleibt für
immer „nicht gelaufen“; einer, der an einem Weg zählt, der vor dem Ziel endet,
heißt „erfüllt“, ohne gemessen zu haben. Beides prüft diese Datei ohne Fenster
am Probeprotokoll (``tools/function_samples.sample_protocol``): Schrittzahlen
nur bis zum Beispielziel (FD-146), Rückweg und Projektwechsel nur in den Lagen
der Zeile (FD-128), die Tab-Kette bis zur Zielhandlung und mit Namen statt
Klassen (FD-141).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tools.function_checks import (
    NO_DRAFT,
    SWITCH_RUN_OVER,
    SWITCH_WITHOUT_INPUTS,
    SWITCH_WITHOUT_PREVIEW,
    WITHOUT_DIALOG,
    CaseOutcome,
)
from tools.function_points import judge_case
from tools.function_samples import sample_context, sample_protocol


def _judged(change: Callable[[dict[str, Any]], None] | None = None) -> CaseOutcome:
    protocol = copy.deepcopy(sample_protocol())
    if change is not None:
        change(protocol)
    return judge_case(protocol, sample_context())


# --- FD-146: E1 bis E3 nur an einem Weg, der das Beispielziel erreicht hat ------------


def _language_surface(protocol: dict[str, Any]) -> None:
    """Ein Sprachdurchgang: ohne Spezifikation, der Weg endet an der offenen Fläche."""
    protocol["spec"] = None
    protocol["steps"] = [step for step in protocol["steps"] if step["phase"] != "übernehmen"]


def _without_goal(protocol: dict[str, Any]) -> None:
    protocol["spec"].pop("example_goal")


def _ends_at_the_surface(protocol: dict[str, Any]) -> None:
    protocol["steps"] = [step for step in protocol["steps"] if step["phase"] != "übernehmen"]


def _apply_not_found(protocol: dict[str, Any]) -> None:
    last = protocol["steps"][-1]
    assert last["phase"] == "übernehmen"
    last["finding"] = "nicht auffindbar"
    last["hit"] = False


@pytest.mark.parametrize(
    "change",
    [_language_surface, _without_goal, _ends_at_the_surface, _apply_not_found],
    ids=["sprachflaeche", "ohne_beispielziel", "endet_an_der_flaeche", "uebernehmen_scheitert"],
)
@pytest.mark.parametrize("criterion", ["E1", "E2", "E3"])
def test_steps_count_only_on_a_way_that_reached_the_example_goal(
    change: Callable[[dict[str, Any]], None], criterion: str
) -> None:
    """Ein Weg, der vor dem Beispielziel endet, misst keine Schritte bis zum Ziel.

    Abweichungen 01, 07–09, 11–15 der Zweitprüfung: An den Sprachflächenzeilen
    meldete Stufe A „0 Eingaben, erfüllt“, obwohl der Weg an Karte oder Dialog
    endete. Ein Prüfer schätzte dann die Restschritte aus dem Bild, der andere
    nannte sie unzählbar — gemessen war nichts.
    """
    outcome = _judged(change).criteria[criterion]
    assert outcome.verdict == "nicht_gelaufen", outcome
    assert "fehlt" in outcome.reason


def test_the_main_way_to_the_example_goal_still_counts() -> None:
    """Gegenfall: Der Hauptweg bis Übernehmen bleibt gezählt (E1 Stufe B, E2 und E3 erfüllt)."""
    case = _judged()
    assert case.criteria["E1"].verdict == "stufe_b"
    assert case.criteria["E1"].measurement["clicks"] == 2
    assert case.criteria["E2"].verdict == "erfuellt"
    assert case.criteria["E3"].verdict == "erfuellt"


def test_a_way_without_its_goal_does_not_enter_the_input_share() -> None:
    """Der E2-Paketanteil liest nur Zeilen, deren Eingaben gezählt sind (N4)."""
    case = _judged(_language_surface)
    assert "inputs" not in case.criteria["E2"].measurement


# --- FD-128: Rückweg und Projektwechsel nur in den Lagen der Zeile -------------------


def _without_draft_or_dialog(protocol: dict[str, Any]) -> None:
    """Eine Befundhandlung wie *Auf das Bett setzen*: kein Entwurf, kein Dialog (Lauf 002)."""
    protocol["states"].pop("escape")
    protocol["states"].pop("cancelled")
    protocol["unmeasured"] = {
        "states.escape": NO_DRAFT,
        "focus_return": WITHOUT_DIALOG,
    }


def test_the_way_back_without_a_draft_needs_no_escape() -> None:
    """Lauf 002: Rückgängig und Wiederholen stimmen, P5 meldete trotzdem alles fehlend."""
    outcome = _judged(_without_draft_or_dialog).points[5]
    assert outcome.verdict == "erfuellt", outcome
    assert outcome.measurement["compared"] == ["undo", "redo"]


def test_a_dialog_without_a_measured_escape_stays_unmeasured() -> None:
    """Gegenfall: Wer einen Dialog öffnet, hat einen Entwurf — ohne Escape kein Rückweg."""

    def change(protocol: dict[str, Any]) -> None:
        _without_draft_or_dialog(protocol)
        protocol["unmeasured"].pop("focus_return")

    assert _judged(change).points[5].verdict == "nicht_gelaufen"


ALL_ABSENT = (
    f"vorschau: {SWITCH_WITHOUT_INPUTS}, kein vorschau; "
    f"entwurf: {SWITCH_WITHOUT_INPUTS}, kein entwurf; rechnung: {SWITCH_RUN_OVER}"
)


def _switch(phases: list[str] | None, notes: str) -> Callable[[dict[str, Any]], None]:
    def change(protocol: dict[str, Any]) -> None:
        protocol["switch"] = None if phases is None else {"phases": phases, "late_events": []}
        protocol["unmeasured"] = {"switch": notes} if notes else {}

    return change


def test_a_row_without_any_switch_situation_is_not_applicable() -> None:
    """Lauf 002: ohne Eingaben, ohne Vorschau und mit sofort fertiger Rechnung (FD-128)."""
    outcome = _judged(_switch(None, ALL_ABSENT)).points[16]
    assert outcome.verdict == "entfaellt" and outcome.reason == "ohne_rechnung", outcome


def test_only_the_situations_of_the_row_are_demanded() -> None:
    """Lauf 003 *Parameter anlegen*: nur der Entwurf — Vorschau und Rechnung gibt es nicht."""
    notes = f"vorschau: {SWITCH_WITHOUT_PREVIEW}; rechnung: {SWITCH_RUN_OVER}"
    outcome = _judged(_switch(["entwurf"], notes)).points[16]
    assert outcome.verdict == "erfuellt", outcome
    assert any("vorschau" in note for note in outcome.notes)


@pytest.mark.parametrize(
    ("phases", "notes"),
    [
        (None, "Szene zweites_projekt fehlt"),
        (["vorschau", "entwurf"], "rechnung: der Wechsel kam nicht an"),
        (["entwurf"], f"vorschau: Startszene nicht herstellbar; rechnung: {SWITCH_RUN_OVER}"),
    ],
    ids=["ohne_szene", "wechsel_kam_nicht_an", "startszene_fehlt"],
)
def test_a_situation_the_bench_could_not_reach_stays_unmeasured(
    phases: list[str] | None, notes: str
) -> None:
    """Gegenfälle: Was die Zeile hat, aber nicht gemessen ist, bleibt „nicht gelaufen“."""
    assert _judged(_switch(phases, notes)).points[16].verdict == "nicht_gelaufen"


def test_a_late_event_after_a_switch_stays_a_finding() -> None:
    def change(protocol: dict[str, Any]) -> None:
        _switch(["entwurf"], f"vorschau: {SWITCH_WITHOUT_PREVIEW}; rechnung: {SWITCH_RUN_OVER}")(
            protocol
        )
        protocol["switch"]["late_events"] = [{"kind": "meldung", "text": "spät"}]

    assert _judged(change).points[16].verdict == "fund"


def test_the_bench_writes_the_reasons_the_judges_read() -> None:
    """Gehaltener Zwilling: Prüfstand und Urteil lesen dieselben Sätze (FD-128).

    ``function_bench.phase_escape`` schreibt den Satz ohne Entwurf als Text;
    der Wächter hält ihn gleich :data:`NO_DRAFT`, bis die Zeile die Konstante nimmt.
    """
    root = Path(__file__).resolve().parents[1] / "tools"
    bench = (root / "function_bench.py").read_text(encoding="utf-8")
    switch = (root / "function_switch.py").read_text(encoding="utf-8")
    assert f'"states.escape", "{NO_DRAFT}"' in bench or "NO_DRAFT" in bench
    for name in ("SWITCH_WITHOUT_INPUTS", "SWITCH_WITHOUT_PREVIEW", "SWITCH_RUN_OVER"):
        assert name in switch, name


# --- FD-141: die Tab-Kette erreicht die Zielhandlung, und eine Klasse ist kein Name ---


def _old_chain(protocol: dict[str, Any]) -> None:
    """Die Kette eines älteren Laufs: nur Name, Rechteck und drinnen (Lauf 001, 002)."""
    protocol["tab_chain"] = [
        {"name": "FittedScroller", "rect": [0, 0, 300, 400], "inside": True},
        {"name": "Durchmesser", "rect": [12, 40, 120, 24], "inside": True},
        {"name": "Hilfe", "rect": [0, 600, 40, 40], "inside": False},
    ]
    protocol["names"] = ["FittedScroller", "Durchmesser"]


def test_a_class_name_in_an_older_chain_is_a_missing_name() -> None:
    """Lauf 001/002: „FittedScroller“ zählte als Name, P10 hieß „2 Tab-Schritte, erfüllt“."""
    outcome = _judged(_old_chain).points[10]
    assert outcome.verdict == "fund", outcome
    assert any("FittedScroller" in issue.text for issue in outcome.issues)


def test_a_chain_without_the_target_action_is_a_finding() -> None:
    def change(protocol: dict[str, Any]) -> None:
        for link in protocol["tab_chain"]:
            link["primary"], link["mark"] = False, ""

    outcome = _judged(change).points[10]
    assert outcome.verdict == "fund"
    assert any("Zielhandlung" in issue.text for issue in outcome.issues)


def test_the_target_action_counts_by_its_mark_where_no_main_button_is() -> None:
    """Eine Befundhandlung: Ihr Knopf ist das Ziel der Zeile, kein Hauptknopf."""

    def change(protocol: dict[str, Any]) -> None:
        protocol["tab_chain"][2].update(primary=False, mark="operation:drill_hole")

    assert _judged(change).points[10].verdict == "erfuellt"


def test_an_empty_chain_is_not_measured() -> None:
    """Brachte der Prüfstand den Fokus nicht in die Fläche, ist nichts gemessen — nie erfüllt."""

    def change(protocol: dict[str, Any]) -> None:
        protocol["tab_chain"], protocol["names"] = [], []

    assert _judged(change).points[10].verdict == "nicht_gelaufen"
