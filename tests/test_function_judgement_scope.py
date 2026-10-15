"""Was Stufe A an einer Zeile misst, gilt nur, wo die Zeile es hat (Paket F8, RM-737).

Ein Prüfpunkt, der einen Zustand verlangt, den die Zeile nicht hat, bleibt für
immer „nicht gelaufen“; einer, der an einem Weg zählt, der vor dem Ziel endet,
heißt „erfüllt“, ohne gemessen zu haben. Beides prüft diese Datei ohne Fenster
am Probeprotokoll (``tools/function_samples.sample_protocol``): Schrittzahlen
nur bis zum Beispielziel (FD-146), Rückweg und Projektwechsel nur in den Lagen
der Zeile (FD-128).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest

from tools.function_checks import CaseOutcome
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
