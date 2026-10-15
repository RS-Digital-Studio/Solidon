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


# --- FD-152: I1 „jede Art“ gegen die Arten, die die Erkennung liefert ----------------


def test_the_bench_records_the_kinds_recognition_delivers() -> None:
    """Lauf 002: ``hover_labels`` hatte einen Eintrag, welche Arten es gab, stand nirgends.

    Der Prüfstand schreibt die Arten der Szene, bevor er überfährt — auch ohne
    Renderer, wo er nichts überfahren kann.
    """
    from types import SimpleNamespace

    from tools import function_bench

    objects = {
        "obj_1": SimpleNamespace(
            features={
                "face_1": SimpleNamespace(kind="face"),
                "hole_1": SimpleNamespace(kind="hole"),
            }
        )
    }
    flow = object.__new__(function_bench.FunctionFlow)
    flow.session = SimpleNamespace(
        last_result=SimpleNamespace(scene=SimpleNamespace(objects=objects))
    )
    flow.window = SimpleNamespace(viewport=SimpleNamespace(renderer=None))
    flow.data = {"unmeasured": {}}
    flow.phase_hover()
    assert flow.data["recognized_kinds"] == ["face", "hole"]
    assert "Renderer" in flow.data["unmeasured"]["hover_labels"]


@pytest.mark.parametrize(
    ("recognized", "verdict"),
    [(None, "nicht_gelaufen"), (["hole", "slot"], "nicht_gelaufen"), (["hole"], "stufe_b")],
    ids=["ohne_liste", "art_nicht_ueberfahren", "jede_art"],
)
def test_every_recognized_kind_must_be_hovered(recognized: list[str] | None, verdict: str) -> None:
    """Gemessen ist I1 erst, wenn jede erkannte Art überfahren wurde; das Urteil bleibt B."""

    def change(protocol: dict[str, Any]) -> None:
        if recognized is None:
            protocol.pop("recognized_kinds")
        else:
            protocol["recognized_kinds"] = recognized

    assert _judged(change).criteria["I1"].verdict == verdict


# --- FD-150: Fundstellen für Prüfpunkt 11 aus der Spezifikation und aus Bildtexten -----


def _repository_promises() -> Any:
    """Der Kontext der Gegenproben mit den echten Fundstellen von Handbuch und Website."""
    from dataclasses import replace

    from app.core.bootstrap import load_operations
    from tools import function_promises, function_report

    load_operations()
    return replace(
        sample_context(),
        manual_place=function_report.manual_place,
        website_hits=function_report._website_hits,
        promise_problems=function_promises.reference_problems,
    )


def _window_command(spec_values: dict[str, Any]) -> Callable[[dict[str, Any]], None]:
    def change(protocol: dict[str, Any]) -> None:
        protocol["row"] = {
            **protocol["row"],
            "id": "Bearbeiten/Parameter anlegen …",
            "kind": "fensterbefehl",
            "target": "menu:menubar.edit.add_parameter",
        }
        protocol["kind"] = "fensterbefehl"
        protocol["spec"] = {**protocol["spec"], **spec_values}

    return change


def test_a_row_outside_the_register_finds_its_places_through_the_spec() -> None:
    """Abweichung 02: an *Parameter anlegen* lieferte Stufe A keine Fundstelle (FD-150)."""
    protocol = copy.deepcopy(sample_protocol())
    _window_command({"manual": "parameters", "website": ["funktionen.html#parametrisch"]})(protocol)
    outcome = judge_case(protocol, _repository_promises()).points[11]
    assert outcome.verdict == "stufe_b", outcome
    assert outcome.measurement["manual"] == "parameters"
    hits = outcome.measurement["website"]
    assert "website/funktionen.html#parametrisch" in hits
    assert len(hits) == 6, hits


@pytest.mark.parametrize(
    "spec_values",
    [
        {"manual": "erfunden"},
        {"manual": "ref-holes#operation-erfunden"},
        {"website": ["funktionen.html#erfunden"]},
        {"website": ["index.html#anfang"]},
    ],
    ids=["seite", "sprungmarke", "abschnitt", "fremde_seite"],
)
def test_a_place_the_spec_names_must_exist(spec_values: dict[str, Any]) -> None:
    """Eine Fundstelle, die es nicht gibt, macht P11 nicht prüfbar — nie erfüllt."""
    protocol = copy.deepcopy(sample_protocol())
    _window_command(spec_values)(protocol)
    assert judge_case(protocol, _repository_promises()).points[11].verdict == "nicht_pruefbar"


def test_without_places_a_window_command_stays_with_stage_b() -> None:
    protocol = copy.deepcopy(sample_protocol())
    _window_command({})(protocol)
    outcome = judge_case(protocol, _repository_promises()).points[11]
    assert outcome.verdict == "stufe_b" and "nennt keine" in outcome.summary


def test_a_promise_in_a_picture_text_is_a_place(tmp_path: Any) -> None:
    """``alt`` und ``title`` zählen: *Bohrung ändern* steht auf der Website im Bildtext (N8)."""
    from tools import function_promises, function_report

    page = tmp_path / "seite.html"
    page.write_text(
        '<p>Text</p><img alt="Die Gruppe &bdquo;Bohrung ändern&ldquo;"><a title="Senken">x</a>',
        encoding="utf-8",
    )
    text = function_promises.page_text(page)
    assert "bohrung ändern" in text and "senken" in text
    _repository_promises()
    hits = function_report._website_hits({"id": "resize_hole", "kind": "operation"})
    assert "website/funktionen.html" in hits


# --- FD-129: Prüfpunkt 17 an Zeilen, deren Agentenwerkzeug nicht im Register steht ----


@pytest.mark.parametrize(
    ("row", "said"),
    [
        ("Bearbeiten/Parameter anlegen …", "menue"),
        ("dialog:parameter_dialog", "menue"),
        ("menu:parameters.edit", "leiste"),
    ],
)
def test_a_tool_outside_the_register_names_its_rows(row: str, said: str) -> None:
    """Abweichung 04: Stufe A meldete „ohne Agentenwerkzeug“, obwohl ``add_parameter`` es tut."""
    from tools import function_report

    place = function_report.agent_place({"id": row, "kind": "fensterbefehl"})
    assert place is not None and place[0] == said, place
    assert function_report.agent_place({"id": "Datei/Speichern", "kind": "fensterbefehl"}) is None


def _agent_row(said: str, where: str) -> Callable[[dict[str, Any]], None]:
    def change(protocol: dict[str, Any]) -> None:
        protocol["row"] = {**protocol["row"], "id": "Bearbeiten/Parameter anlegen …"}
        protocol["row"]["kind"] = protocol["kind"] = "fensterbefehl"
        protocol["place"] = {"where": where, "path": [], "error": None}

    return change


@pytest.mark.parametrize(
    ("said", "where", "verdict"),
    [
        ("menue", "menue", "erfuellt"),
        ("leiste", "kontext", "erfuellt"),
        ("leiste", "karte", "erfuellt"),
        ("leiste", "menue", "fund"),
        ("menue", "kontext", "nicht_pruefbar"),
    ],
)
def test_the_agent_place_of_a_window_command_is_compared(
    said: str, where: str, verdict: str
) -> None:
    """Der Ort ``leiste`` (Parameterleiste) hat sein Gegenstück in Karte und Kontextmenü."""
    from dataclasses import replace

    protocol = copy.deepcopy(sample_protocol())
    _agent_row(said, where)(protocol)
    context = replace(sample_context(), agent_place=lambda row: (said, "Weg"))
    assert judge_case(protocol, context).points[17].verdict == verdict
