"""Urteile, Gegenproben, Abhakliste und Funddatei des Funktionsdurchgangs (RM-737, D0-U).

Der Prüfstand misst am echten Fenster; hier wird ohne Fenster geprüft, ob
seine Messungen richtig beurteilt werden. Jede Gegenprobe (Konzept §10)
ist ein absichtlich kaputtes Protokoll, Urteil oder Fund und muss rot werden
(``tools/function_samples.py``). Ein Prüfpunkt ohne Gegenprobe macht diese
Datei rot, ebenso ein Urteil, das abgewiesen gehört, eine Funddatei mit
doppelter Nummer und eine Kriterientabelle im Skill, die von den Konstanten
abweicht.

Der eine Fenstertest der Datei ist ein ``rendered``-Test: die Menüleiste am
gebauten Fenster gegen die Fensterbefehlszeilen der Abhaklisten. Grün ist er
erst nach einem Lauf des Prüfstands (``tools/file_acceptance.py report``).
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.ui.main_window import START_SIZE, MainWindow
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window
from tools import function_checks, function_report
from tools.function_checks import (
    CHECKPOINTS,
    COARSE_NOTE,
    CRITERIA,
    GOOD_OVER_FINDING,
    SMALLEST_SCREEN,
    SMALLEST_WINDOW,
    TASKBAR_HEIGHT,
    Checkpoint,
    skill_mismatches,
    skill_rows,
    threshold_numbers,
    validate_protocol,
    words,
)
from tools.function_judges import CRITERION_JUDGES
from tools.function_points import POINT_JUDGES, judge_case
from tools.function_report import (
    STATE,
    check_findings,
    check_verdicts,
    compare_window_commands,
    is_red,
    merge_cases,
    package_values,
    parse_findings,
    read_checklist,
    read_checklists,
    render_checklist,
    write,
)
from tools.function_samples import BROKEN_SAMPLES, sample_context, sample_protocol, uncovered

ROOT = Path(__file__).resolve().parents[1]


def _judged(change: Any = None) -> Any:
    protocol = copy.deepcopy(sample_protocol())
    if change is not None:
        change(protocol)
    return judge_case(protocol, sample_context())


def _verdict(**values: Any) -> dict[str, Any]:
    verdict: dict[str, Any] = {
        "row": "drill_hole",
        "verdict": "gut",
        "reviewer": "stufe_b",
        "reason": "Bild und Text gelesen",
        "image": "cases/1/01-vorher.png",
        "place": "Merkmalfenster, Kopf der Bohrung",
    }
    for key, value in values.items():
        if value is None:
            verdict.pop(key, None)
        else:
            verdict[key] = value
    return verdict


FINDING = """### FD-{number} {title}

**Art:** {kind}
**Schwere:** {severity}
**Funktion:** drill_hole
**Prüfpunkt:** {subject}
**Beleg:** cases/1/03-dialog.png
**Ursache:** Der Dialog setzt make_primary zweimal.
**Vorschlag:** Nur Übernehmen ist die Hauptaktion.
**Wirkung beim Kunden:** Der Kunde sieht zwei gleich laute Knöpfe.
**Stand:** {stand}
"""


def _finding(**values: Any) -> str:
    given = {
        "number": 1,
        "title": "Zwei Hauptknöpfe",
        "kind": "Gestaltung",
        "severity": "leicht",
        "subject": "G1",
        "stand": "offen RM-800",
    }
    given.update(values)
    return FINDING.format(**given)


# --- Schema und Abdeckung -------------------------------------------------


def test_the_schema_has_nineteen_checkpoints_and_the_thirty_five_criteria() -> None:
    """Konzept §4: neunzehn Prüfpunkte, dazu E1–E7, V1–V6, G1–G9, Z1–Z7, I1–I6."""
    from tools.function_list import CHECKPOINT_NUMBERS, CRITERION_IDS

    # Die Kennungen führt L (Spezifikationsformat); hier stehen ihre Definitionen.
    assert tuple(CHECKPOINTS) == CHECKPOINT_NUMBERS
    assert tuple(CRITERIA) == CRITERION_IDS
    assert len(CRITERIA) == 35


def test_every_checkpoint_and_criterion_has_a_judge() -> None:
    """Ein Prüfpunkt ohne Urteilsfunktion würde nie gemessen."""
    assert set(POINT_JUDGES) == set(CHECKPOINTS)
    assert set(CRITERION_JUDGES) == set(CRITERIA)
    for number, point in CHECKPOINTS.items():
        assert set(point.parts) <= set(CRITERIA), number


def test_the_sample_protocol_has_nothing_to_find() -> None:
    """Die Grundlage aller Gegenproben: vollständig, gültig, ohne Fund.

    Erst wenn das Muster nichts findet, belegt eine Gegenprobe, dass genau
    ihre eine verdorbene Stelle rot wird.
    """
    protocol = sample_protocol()
    assert validate_protocol(protocol) == []
    case = judge_case(protocol, sample_context())
    assert set(case.points) == set(CHECKPOINTS)
    assert len(case.criteria) >= 30, sorted(case.criteria)
    found = {
        subject: outcome.issues
        for subject, outcome in [*case.points.items(), *case.criteria.items()]
        if outcome.verdict == "fund"
    }
    assert not found
    measured = [o for o in case.points.values() if o.verdict in {"erfuellt", "stufe_b"}]
    assert len(measured) == len(CHECKPOINTS), {
        n: o.verdict for n, o in case.points.items() if o not in measured
    }


@pytest.mark.parametrize(
    "sample", BROKEN_SAMPLES, ids=[f"{s.subject}-{s.title}" for s in BROKEN_SAMPLES]
)
def test_every_broken_sample_turns_red(sample: Any) -> None:
    """Jede Gegenprobe (Konzept §10) wird rot — ohne Fenster."""
    red, detail = is_red(sample)
    assert red, f"{sample.subject} {sample.title}: blieb grün ({detail})"


JUDGED_SAMPLES = [s for s in BROKEN_SAMPLES if s.kind in {"verdict", "finding"}]


def test_every_verdict_and_finding_sample_names_its_reason() -> None:
    """Rot aus irgendeinem Grund belegt nichts: Jede solche Gegenprobe nennt ihren."""
    assert JUDGED_SAMPLES
    assert all(sample.reason for sample in JUDGED_SAMPLES), [
        f"{s.subject} {s.title}" for s in JUDGED_SAMPLES if not s.reason
    ]


@pytest.mark.parametrize(
    "sample",
    [s for s in JUDGED_SAMPLES if s.kind == "verdict" and s.change is not None],
    ids=lambda s: f"{s.subject}-{s.title}",
)
def test_a_verdict_sample_is_accepted_without_its_break(sample: Any) -> None:
    """Die Gegenseite: Dasselbe Urteil am heilen Muster wird angenommen.

    Erst dann liegt das Rot der Gegenprobe an ihrer verdorbenen Stelle und nicht
    an einem Urteil, das ohnehin abgewiesen würde.
    """
    case = _judged()
    checked = check_verdicts([sample.verdict], outcomes={case.row_id: case})
    assert checked.rejected == (), checked.rejected


def test_every_checkpoint_and_criterion_has_a_broken_sample() -> None:
    """Je Prüfpunkt und Kriterium mindestens ein Rotfall (Konzept §10)."""
    assert len(BROKEN_SAMPLES) >= len(CHECKPOINTS) + len(CRITERIA)
    assert uncovered() == set()


def test_a_new_checkpoint_without_a_broken_sample_turns_the_suite_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Metatest: Wer einen zwanzigsten Prüfpunkt anlegt, muss seine Gegenprobe mitbringen."""
    monkeypatch.setitem(CHECKPOINTS, 20, Checkpoint(20, "Neu", ("A",), ("steps",)))
    assert uncovered() == {20}


def test_only_a_different_selection_after_undo_is_a_note_not_a_finding() -> None:
    """Prüfpunkt 5: Nur die Auswahl verschieden ist ein Vermerk, nie rot.

    Konzept §4, Prüfpunkt 5.
    """

    def other_selection(protocol: dict[str, Any]) -> None:
        protocol["states"]["undo"] = {**protocol["states"]["before"], "selection": []}

    outcome = _judged(other_selection).points[5]
    assert outcome.verdict == "erfuellt"
    assert any("Auswahl" in note for note in outcome.notes)


def test_a_click_outside_the_main_path_does_not_count_for_e1_to_e4() -> None:
    """Nur ``weg`` und ``übernehmen`` sind der Hauptweg (Festlegung Koordinator).

    Die Gegenprobe in beide Richtungen: Fünf Klicks in der Phase der Matrix
    lassen E1 bis E4 unverändert; dieselben fünf auf dem Weg machen E1 rot.
    """
    from tools.function_samples import click_step

    def clicks_in(phase: str) -> Any:
        def change(protocol: dict[str, Any]) -> None:
            protocol["steps"] += [
                click_step(f"menu:tree.x{n}", "ansicht", "menue", phase=phase) for n in range(5)
            ]

        return change

    base = _judged()
    other = _judged(clicks_in("matrix klick operation:drill_hole"))
    for key in ("E1", "E2", "E3", "E4"):
        assert other.criteria[key] == base.criteria[key], key
    assert other.points[2].verdict == base.points[2].verdict
    assert _judged(clicks_in("weg")).criteria["E1"].verdict == "fund"


def _activation_in(state: str) -> Any:
    """Ein Freischaltzustand, wie die Suite ihn über ``activation._cached`` setzt."""
    from app.core import activation
    from app.core.activation import key

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=activation.DEVICE_ACTIVATION_FROM,
        order="A-1234",
        holder="kaeufer@beispiel.de",
    )
    certificate = activation.ActivationCertificate(
        licence_digest="test-licence",
        device_public=b"\x01" * 32,
        device_name="Prüfrechner",
        activation_id="test-activation",
        issued_on=activation.DEVICE_ACTIVATION_FROM,
    )
    built = {
        "sale_without_trial": lambda: activation.Activation(days_left=0),
        "expired": lambda: activation.Activation(days_left=0),
        "needs_activation": lambda: activation.Activation(licence=licence),
        "licensed": lambda: activation.Activation(licence=licence, certificate=certificate),
    }
    return built[state]()


@pytest.mark.parametrize("trial_from", [None, "2026-12-01"])
def test_the_licence_states_are_the_ones_the_application_reads(
    monkeypatch: pytest.MonkeyPatch, trial_from: str | None
) -> None:
    """Jeder verlangte Lizenzlauf ist in der Fassung erreichbar und bedeutet das Erwartete.

    Die Anwendung führt keine Aufzählung; sie liest den Zustand an Eigenschaften
    von ``Activation`` ab. Geprüft wird je Lauf, dass ein Zustand, wie die Suite
    ihn setzt, genau diese Eigenschaft wahr macht, keine der anderen, und dass
    ``unlocked`` sagt, was ``LICENCE_UNLOCKED`` erwartet. Ohne ``TRIAL_FROM``
    (Verkaufsversion) ist der Testlauf unerreichbar, mit ihm die lesende
    Verkaufsversion; ``over`` startet die Anwendung gar nicht und ist kein Lauf.
    """
    from datetime import date

    from app.core.activation import store
    from tools.function_checks import LICENCE_UNLOCKED
    from tools.function_list import LICENCE_STATES, licence_states

    monkeypatch.setattr(
        store, "TRIAL_FROM", None if trial_from is None else date.fromisoformat(trial_from)
    )
    runs = licence_states()
    assert {"needs_activation", "licensed"} <= set(runs)
    assert ("expired" in runs) is (trial_from is not None)
    assert ("sale_without_trial" in runs) is (trial_from is None)
    assert "over" not in LICENCE_STATES
    for state in runs:
        reached = _activation_in(state)
        assert getattr(reached, state) is True, state
        others = [name for name in LICENCE_STATES if name != state and getattr(reached, name)]
        assert others == [], (state, others)
        assert reached.unlocked is LICENCE_UNLOCKED[state], state


def test_the_expired_demo_row_carries_its_licence_state() -> None:
    """``over`` ist kein Lauf je Funktion, aber der Zustand der D12-Zeile von L.

    Die Zeile ``startup.expired_demo`` startet die Anwendung im Zustand „Demo
    abgelaufen“; ihr Protokoll muss ihn tragen dürfen, und die Anwendung muss
    ihn so lesen: ``over`` wahr, nichts frei.
    """
    from datetime import date

    from app.core import activation
    from tools.function_list import RAW_WINDOW_IDS, STARTUP_LICENCE

    assert "startup.expired_demo" in RAW_WINDOW_IDS.values()
    reached = activation.Activation(days_left=0, deadline=date(2026, 1, 1))
    assert getattr(reached, STARTUP_LICENCE) is True and not reached.unlocked
    protocol = sample_protocol()
    protocol["variant"]["licence"] = STARTUP_LICENCE
    assert validate_protocol(protocol) == []


def test_the_display_unit_is_the_one_the_application_writes() -> None:
    """Die Einheit kommt aus ``app.core.units.DISPLAY_UNITS`` — „in“, nicht „inch“."""
    protocol = sample_protocol()
    protocol["variant"]["unit"] = "in"
    assert validate_protocol(protocol) == []
    protocol["variant"]["unit"] = "inch"
    assert any(problem.startswith("variant: unit") for problem in validate_protocol(protocol))


def test_a_purchased_licence_that_still_greys_out_is_a_finding() -> None:
    """Prüfpunkt 18 in der Gegenrichtung: Gekauft und trotzdem grau ist eine Sperre zu viel."""

    def locked(protocol: dict[str, Any]) -> None:
        protocol["licence_runs"]["licensed"] = {"writes": True, "enabled": False, "reason": "x"}

    assert _judged(locked).points[18].verdict == "fund"


def test_the_licence_point_is_judged_once_per_row_over_all_runs() -> None:
    """Der Prüfstand fährt je Lizenzzustand einen Fall mit einem Lauf (Review S3).

    Geurteilt wird einmal je Zeile über alle Läufe ihrer Fälle: Jeder Fall für
    sich ist kein Fund, weil ihm die übrigen Läufe fehlen; zusammengeführt ist
    die Zeile erfüllt, und erst ein fehlender Lauf über alle Fälle ist einer.
    """
    from tools.function_checks import LICENCE_UNLOCKED
    from tools.function_list import licence_states

    base = sample_protocol()
    base.pop("licence_runs")
    # Die Läufe, die diese Fassung verlangt — die Suite setzt ``TRIAL_FROM``.
    runs = {
        state: {
            "writes": True,
            "enabled": LICENCE_UNLOCKED[state],
            "reason": "" if LICENCE_UNLOCKED[state] else "Ändern braucht eine Lizenz.",
        }
        for state in licence_states()
    }
    single = []
    for state, entry in runs.items():
        protocol = sample_protocol()
        protocol["licence_runs"] = {state: entry}
        protocol["variant"]["licence"] = state
        single.append(protocol)
    cases = [judge_case(p, sample_context()) for p in [base, *single]]
    assert all(case.points[18].verdict != "fund" for case in cases), [
        case.points[18].issues for case in cases
    ]
    assert merge_cases(cases, [base, *single]).points[18].verdict == "erfuellt"
    partial = merge_cases(cases[:-1], [base, *single[:-1]]).points[18]
    # Ein Lauf, den es über alle Fälle nicht gab, ist nicht gemessen — nie gut.
    assert partial.verdict == "nicht_gelaufen"
    assert "Lizenzlauf" in partial.reason


def test_a_selection_the_bench_could_not_build_is_a_note_not_a_finding() -> None:
    """Prüfpunkt 13: „nicht herstellbar“ ist ein Vermerk über die Messung, kein Fund."""

    def unreachable(protocol: dict[str, Any]) -> None:
        protocol["matrix"]["eine_kante"] = {
            "state": "nicht herstellbar",
            "reason": "",
            "effective": None,
        }

    outcome = _judged(unreachable).points[13]
    assert outcome.verdict == "stufe_b"
    assert any("nicht herstellbar" in note for note in outcome.notes)


def test_a_suspected_budget_overrun_is_a_note_for_the_bench() -> None:
    """Prüfpunkt 6: Über dem §31-Budget ist ein Verdacht, den ``window_bench`` bestätigt."""

    def slow(protocol: dict[str, Any]) -> None:
        protocol["timing"]["total_s"] = 1.5

    outcome = _judged(slow).points[6]
    assert outcome.verdict == "erfuellt"
    assert any(note.startswith("Verdacht") for note in outcome.notes)


def test_a_foreign_not_applicable_reason_in_the_spec_is_not_applicable_never_fine() -> None:
    """Ein Grund außerhalb der Liste macht den Prüfpunkt nicht prüfbar, nie *entfällt*."""

    def foreign(protocol: dict[str, Any]) -> None:
        protocol["spec"]["not_applicable"] = {"3": "keine Lust", "12": "ohne_dialog"}

    case = _judged(foreign)
    assert case.points[3].verdict == "nicht_pruefbar"
    assert case.points[12].verdict == "entfaellt"


def test_a_protocol_with_unknown_or_malformed_fields_is_invalid() -> None:
    """Das Schema hat eine Quelle; ein neues Feld kommt über die Schnittstelle, nicht still."""
    protocol = sample_protocol()
    protocol["surprise"] = 1
    protocol["steps"] = {"not": "a list"}
    del protocol["version"]
    problems = validate_protocol(protocol)
    assert "unbekanntes Feld: surprise" in problems
    assert "steps ist keine Liste" in problems
    assert "Pflichtfeld fehlt: version" in problems


NESTED = {
    "unbekannter Schlüssel im Eintrag": (
        ("spot", "covered"),
        True,
        "spot: unbekannter Schlüssel covered",
    ),
    "Zone außerhalb der Liste": (("steps", 0, "zone"), "links", "steps[1]: zone = 'links'"),
    "why außerhalb der Liste": (("steps", 1, "why"), "suche", "steps[2]: why = 'suche'"),
    "Ort außerhalb der Liste": (
        ("place", "where"),
        "seitenleiste",
        "place: where = 'seitenleiste'",
    ),
    "Art der Zeile": (("kind",), "dialog", "kind = 'dialog'"),
    "Zustand der Auswahlstufe": (("matrix", "ohne", "state"), "aus", "matrix.ohne: Zustand 'aus'"),
    "Pflichtfeld leer": (("variant",), None, "Pflichtfeld leer: variant"),
    "Zeile als bloße Kennung": (("row",), "drill_hole", "row ist keine Tabelle"),
    "Namen keine Texte": (("names",), [1, 2], "names ist keine Liste von Texten"),
    "Fokus kein Wahrheitswert": (
        ("focus_return",),
        "ja",
        "focus_return ist nicht wahr oder falsch",
    ),
    "Lizenzlauf unbekannt": (
        ("licence_runs", "abgelaufen"),
        {},
        "licence_runs: unbekannter Schlüssel",
    ),
}


@pytest.mark.parametrize("name", sorted(NESTED))
def test_the_protocol_schema_reaches_into_every_object(name: str) -> None:
    """Schlüssel und Werte aus geschlossenen Listen werden bis in die Einträge geprüft.

    Der Prüfstand schreibt nach diesem Schema und prüft sich mit
    ``validate_protocol`` — ein Tippfehler in einem Schlüssel fiele sonst erst
    als „nicht gelaufen“ auf.
    """
    path, value, expected = NESTED[name]
    protocol = sample_protocol()
    target: Any = protocol
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    problems = validate_protocol(protocol)
    assert any(problem.startswith(expected) for problem in problems), problems


def test_the_sample_protocol_carries_every_field_of_the_schema() -> None:
    """Das Muster nutzt das ganze Schema — sonst prüfte keine Gegenprobe ein neues Feld."""
    from tools.function_checks import PROTOCOL_FIELDS, REQUIRED_FIELDS

    assert set(sample_protocol()) == PROTOCOL_FIELDS
    assert set(REQUIRED_FIELDS) == {"row", "kind", "package", "variant", "version"}


def test_a_row_without_specification_is_valid_but_not_measured() -> None:
    """Eine Zeile ohne Spezifikation ist „ungeprüft“, kein ungültiges Protokoll.

    Konzept §3: Eine leere Spezifikation heißt ungeprüft.
    """
    protocol = sample_protocol()
    protocol["spec"] = None
    assert validate_protocol(protocol) == []
    case = judge_case(protocol, sample_context())
    assert case.points[4].verdict == "nicht_gelaufen"
    assert case.points[7].verdict == "nicht_gelaufen"


def test_criteria_that_do_not_apply_to_a_row_are_left_out() -> None:
    """Z3 ohne Auswahlbezug, I5 außerhalb der Zeile Vorher/Nachher: kein Ergebnis."""

    def empty_scene(protocol: dict[str, Any]) -> None:
        protocol["row"]["requirement"] = "leer"

    case = _judged(empty_scene)
    assert "Z3" not in case.criteria
    assert "I5" not in case.criteria


def test_a_function_nobody_can_find_is_a_heavy_finding() -> None:
    """Prüfpunkt 1: „nicht auffindbar“ ist schwer (Konzept §4, „Urteil und Schwere“)."""

    def lost(protocol: dict[str, Any]) -> None:
        protocol["place"]["error"] = "MissingTargetError"

    outcome = _judged(lost).points[1]
    assert [issue.severity for issue in outcome.issues] == ["schwer"]


def test_the_contrast_sample_lies_just_below_the_threshold() -> None:
    """Die Gegenprobe von G6 trägt 3,9 bei normaler Schrift, nicht irgendeinen Wert.

    Konzept §4, G6: Die Probe liegt knapp unter der Schwelle von 4,5.
    """
    from app.ui.theme import contrast_ratio

    assert round(contrast_ratio("#818181", "#ffffff"), 1) == 3.9


def test_every_result_names_its_evidence() -> None:
    """Je Ergebnis Stufe, Messung, Urteil, Grund und Beleg (Konzept §4).

    Der Beleg sind die Bilder des Falls und die gelesenen Stellen im Protokoll.
    """
    case = _judged()
    record = case.points[4].record()
    assert record["point"] == 4 and record["stage"] == "A" and record["verdict"] == "erfuellt"
    assert "cases/1/01-vorher.png" in record["evidence"]
    assert "function.json#result" in record["evidence"]
    assert case.criteria["E5"].record()["criterion"] == "E5"


# --- Urteile ----------------------------------------------------------------


def test_good_verdicts_are_accepted() -> None:
    """Die Gegenseite: Was Konzept §5, Stufe B erfüllt, wird angenommen."""
    case = _judged()
    findings, problems = parse_findings(_finding(subject="1", kind="Einfachheit"))
    assert not problems
    found = {finding.key: finding for finding in findings}
    entries = [
        _verdict(point=1),
        _verdict(point=17, verdict="entfaellt", not_applicable="ohne_agentenwerkzeug", image=None),
        _verdict(point=2, verdict="offen", rm="RM-801", finding="FD-1"),
        _verdict(point=8, verdict="gut_nach_fix", finding="FD-1"),
        _verdict(criterion="G9", design_judgement=True),
        _verdict(criterion="V4", prediction="Ein Loch von 5 mm"),
        _verdict(criterion="Z7", reviewer="stufe_c", steps=14, misclicks=1),
        _verdict(point=1, reviewer="zweitpruefer"),
        _verdict(
            row="vergleich:merkmalfenster",
            criterion="Z3",
            design_judgement=True,
            comparison="besser",
        ),
    ]
    checked = check_verdicts(
        entries, outcomes={case.row_id: case}, rows=["drill_hole"], findings=found
    )
    assert checked.rejected == ()
    assert len(checked.accepted) == len(entries)


REJECTED = {
    "ohne Bild": (_verdict(point=2, image=None), "ohne Bild oder Stelle"),
    "ohne Stelle": (_verdict(point=2, place=""), "ohne Bild oder Stelle"),
    "offen ohne RM": (_verdict(point=2, verdict="offen"), "offen ohne RM-Nummer"),
    "fremder Grund": (
        _verdict(point=3, verdict="entfaellt", not_applicable="zu schwer", image=None),
        "fremder entfällt-Grund",
    ),
    "G9 ohne Kennzeichen": (_verdict(criterion="G9"), "Gestaltungsurteil nicht als solches"),
    "Kennzeichen an E1": (_verdict(criterion="E1", design_judgement=True), "kein Urteil ist"),
    "V4 ohne Vorhersage": (_verdict(criterion="V4"), "V4 ohne vorher geschriebene Vorhersage"),
    "Z7 ohne Fehlklicks": (_verdict(criterion="Z7", reviewer="stufe_c", steps=3), "misclicks"),
    "Z7 aus Stufe B": (_verdict(criterion="Z7", steps=3, misclicks=0), "Z7 urteilt nur Stufe C"),
    "unbekannter Schlüssel": (_verdict(point=2, severity="leicht"), "unbekannter Schlüssel"),
    "unbekannte Zeile": (_verdict(point=2, row="erfunden"), "unbekannte Zeile"),
    "kein Prüfpunkt": (_verdict(point=20), "kein Prüfpunkt"),
    "beides": (_verdict(point=2, criterion="E1"), "genau eines"),
    "gut nach Fix ohne Fund": (_verdict(point=2, verdict="gut_nach_fix"), "ohne Fund"),
    "Fund nicht in der Datei": (_verdict(point=2, finding="FD-9"), "nicht in der Funddatei"),
}


@pytest.mark.parametrize("name", sorted(REJECTED))
def test_a_verdict_against_the_rules_is_rejected(name: str) -> None:
    """Urteile ohne Bild oder Stelle, offen ohne RM, fremder Grund … werden abgewiesen.

    Konzept §5 (Stufe B: mit Bild und Stelle) und §7 („Offen“ nur mit RM-Nummer).
    """
    entry, reason = REJECTED[name]
    case = _judged()
    findings, _problems = parse_findings(_finding())
    checked = check_verdicts(
        [entry],
        outcomes={case.row_id: case},
        rows=["drill_hole"],
        findings={f.key: f for f in findings},
    )
    reasons = [why for _entry, whys in checked.rejected for why in whys]
    assert any(reason in why for why in reasons), reasons


def test_a_g9_verdict_pointing_at_a_heavier_finding_is_rejected() -> None:
    """G9 ist höchstens leicht — auch über den Fund, auf den das Urteil zeigt."""
    findings, _problems = parse_findings(_finding(subject="G9", severity="mittel"))
    checked = check_verdicts(
        [
            _verdict(
                criterion="G9", design_judgement=True, verdict="offen", rm="RM-1", finding="FD-1"
            )
        ],
        findings={f.key: f for f in findings},
    )
    assert any("G9 schwerer als leicht" in why for _e, whys in checked.rejected for why in whys)


def test_fine_against_a_stage_a_finding_is_rejected() -> None:
    """„gut“ gegen einen Fund der Stufe A wird abgewiesen, auch über den Prüfpunkt darüber."""

    def two_primaries(protocol: dict[str, Any]) -> None:
        protocol["layout"][0]["primary"] = 2

    case = _judged(two_primaries)
    for entry in (_verdict(criterion="G1"), _verdict(point=19)):
        checked = check_verdicts([entry], outcomes={case.row_id: case})
        reasons = [why for _entry, whys in checked.rejected for why in whys]
        assert GOOD_OVER_FINDING in reasons, (entry, reasons)


def test_a_second_verdict_of_the_same_stage_is_rejected() -> None:
    """Ein Urteil je Zeile, Prüfpunkt und Stufe — sonst entschiede die Reihenfolge."""
    checked = check_verdicts([_verdict(point=1), _verdict(point=1, verdict="offen", rm="RM-2")])
    assert len(checked.accepted) == 1
    assert "doppeltes Urteil derselben Stufe" in checked.rejected[0][1]


# --- Funddatei ----------------------------------------------------------------


def test_a_good_finding_file_has_no_problems() -> None:
    """Die Gegenseite: Nummern eindeutig, Art und Schwere aus der Liste, Stand gesetzt."""
    text = (
        "# Funde\n\n## D0\n\n"
        + _finding()
        + "\n"
        + _finding(
            number=2, subject="4", kind="Fehler", severity="schwer", stand="behoben `a280ee8f5`"
        )
        + "\n"
        + _finding(
            number=3,
            subject="I3",
            kind="Gestaltung",
            severity="Vorschlag",
            stand="gut nach Fix `a280ee8f5`, Lauf `lauf-12`",
        )
        + "\n"
        # I6 ohne Chat ist die Suche mit Frageformen — die darf Vorschlag sein.
        + _finding(number=4, subject="I6", kind="Gestaltung", severity="Vorschlag")
    )
    findings, problems = parse_findings(text)
    assert [f.number for f in findings] == [1, 2, 3, 4]
    assert problems + check_findings(findings) == []
    assert findings[1].subjects == (4,)


BAD_FINDINGS = {
    "gut nach Fix ohne Commit": (_finding(stand="gut nach Fix `lauf-12`"), "Stand"),
    "doppelte Nummer": (_finding() + _finding(), "mehrfach"),
    "Art nicht aus der Liste": (_finding(kind="Schönheit"), "Art Schönheit"),
    "Schwere nicht aus der Liste": (_finding(severity="kritisch"), "Schwere kritisch"),
    "Stand nicht gesetzt": (_finding(stand="offen"), "Stand"),
    "G9 als mittel": (_finding(subject="G9", severity="mittel"), "G9 ist höchstens leicht"),
    "Vorschlag bei einer Bauplanzusage": (
        _finding(subject="I1", severity="Vorschlag"),
        "Vorschlag nur",
    ),
    "Vorschlag bei einem Fehler": (_finding(subject="4", severity="Vorschlag"), "Vorschlag nur"),
    # Der Chatweg zu I6 ist eine Bauplanzusage (Konzept §4: „für den Chat gilt
    # Prüfpunkt 17“) — als Vorschlag ginge er an der Abnahme vorbei (L13).
    "Vorschlag am Chatweg": (
        _finding(subject="I6", severity="Vorschlag").replace(
            "Der Dialog setzt make_primary zweimal.",
            "Der Chat versteht „Loch größer machen“ nicht.",
        ),
        "Prüfpunkt 17",
    ),
    "kein Prüfpunkt": (_finding(subject="Q9"), "weder Prüfpunkt noch Kriterium"),
    "Feld fehlt": (
        _finding().replace("**Ursache:** Der Dialog setzt make_primary zweimal.\n", ""),
        "Ursache fehlt",
    ),
}


@pytest.mark.parametrize("name", sorted(BAD_FINDINGS))
def test_a_finding_file_against_the_rules_is_rejected(name: str) -> None:
    """Funddatei mit doppelter Nummer, fremder Art oder Schwere, ohne Stand → rot.

    Konzept §7.
    """
    text, expected = BAD_FINDINGS[name]
    findings, problems = parse_findings(text)
    problems += check_findings(findings)
    assert any(expected in problem for problem in problems), problems


def test_a_malformed_finding_heading_is_reported() -> None:
    """Eine Überschrift, die wie ein Fund aussieht, aber keiner ist, fällt auf."""
    _findings, problems = parse_findings("### FD-x Ohne Nummer\n\n**Art:** Fehler\n")
    assert problems


def test_the_checked_in_finding_file_reads_without_problems() -> None:
    """Die Funddatei des Durchgangs (Teilpaket S) liest sich ohne Befund."""
    path = STATE / "funde.md"
    if not path.is_file():
        pytest.skip("funde.md liegt erst mit Teilpaket S im Baum")
    _found, problems = function_report.read_findings(path)
    assert problems == [], problems


# --- Abhakliste ----------------------------------------------------------------


ROWS = [
    {"id": "drill_hole", "kind": "operation", "package": "D4", "start_scene": "quader.exakt"},
    {
        "id": "resize_hole",
        "kind": "operation",
        "package": "D4",
        "start_scene": "merkmal.hole.exakt",
    },
    {
        "id": "Bearbeiten/Parameter anlegen …",
        "kind": "fensterbefehl",
        "package": "D10",
        "start_scene": "leer",
    },
]

SOLUTIONS = {"arrange.out_of_build_volume": True, "mesh.unknown": False}


def _checklist(
    entries: list[dict[str, Any]], *, rows: list[dict[str, Any]] | None = None, change: Any = None
) -> str:
    case = _judged(change)
    cases = {case.row_id: case}
    checked = check_verdicts(entries, outcomes=cases)
    values = package_values(
        cases,
        checked.accepted,
        common_goals={"flaeche_bohren": "operation:drill_hole"},
        solutions=SOLUTIONS,
    )
    return render_checklist(
        "D4",
        rows=rows if rows is not None else ROWS[:2],
        cases=cases,
        verdicts=checked,
        findings={},
        values=values,
        commit="a280ee8f5",
        date="2026-10-12",
        out="F:/tmp-suche/lauf",
    )


def _b_verdicts() -> list[dict[str, Any]]:
    """Ein Urteil für jeden Prüfpunkt, den Stufe B am Muster offen lässt."""
    case = _judged()
    return [_verdict(point=n) for n, o in sorted(case.points.items()) if o.verdict == "stufe_b"]


def test_the_checklist_is_deterministic() -> None:
    """Gleiche Eingaben, gleiche Bytes — auch in anderer Reihenfolge (Konzept §7)."""
    first = _checklist(_b_verdicts())
    assert first == _checklist(_b_verdicts())
    assert first == _checklist(list(reversed(_b_verdicts())), rows=list(reversed(ROWS[:2])))
    assert "| Paket | D4 |" in first
    assert "| Zeilen | 2 |" in first


def test_a_row_is_fine_only_when_every_checkpoint_is_settled() -> None:
    """Ohne Stufe-B-Urteile bleibt die Zeile „nicht geprüft“; mit ihnen „gut“."""
    without = read_checklist(_checklist([]))
    assert without.rows == {"drill_hole": "operation", "resize_hole": "operation"}
    line = next(line for line in _checklist([]).splitlines() if line.startswith("| drill_hole"))
    assert "| B |" in line and line.endswith("| nicht geprüft |  |")
    settled = next(
        line for line in _checklist(_b_verdicts()).splitlines() if line.startswith("| drill_hole")
    )
    assert "| B |" not in settled and "| gut |" in settled
    unrun = next(line for line in _checklist([]).splitlines() if line.startswith("| resize_hole"))
    cells = [cell.strip() for cell in unrun.strip("|").split("|")]
    assert cells[3 : 3 + len(CHECKPOINTS)] == ["?"] * len(CHECKPOINTS)


def test_more_than_one_decision_stays_open_in_the_checklist() -> None:
    """E3: mehr als eine Entscheidung ohne B-Urteil ist „B offen“, nie „gut“.

    Konzept §4, E3.
    """

    def decide(protocol: dict[str, Any]) -> None:
        protocol["steps"][1]["decision"] = True
        protocol["steps"][2]["decision"] = True

    case = _judged(decide)
    assert case.criteria["E3"].verdict == "stufe_b"
    verdicts = [v for v in _b_verdicts() if v["point"] != 2]
    line = next(
        line
        for line in _checklist(verdicts, change=decide).splitlines()
        if line.startswith("| drill_hole")
    )
    assert "nicht geprüft" in line


def test_an_open_verdict_names_its_rm_number() -> None:
    """*offen* nur mit RM-Nummer, und die Zeile sagt welche."""
    verdicts = [v for v in _b_verdicts() if v["point"] != 2] + [
        _verdict(point=2, verdict="offen", rm="RM-801", finding="FD-4")
    ]
    text = _checklist(verdicts)
    line = next(line for line in text.splitlines() if line.startswith("| drill_hole"))
    assert "| offen RM-801 |" in line and "FD-4" in line
    assert "| offen mit RM | 1 |" in text


def test_unmet_criteria_are_listed_with_value_and_threshold() -> None:
    """Tabelle 2: Kennung, Messwert, Schwelle je nicht erfülltem Kriterium."""

    def five_fields(protocol: dict[str, Any]) -> None:
        protocol["fields"] = [
            {"label": f"Feld {n}", "description": f"Satz {n} erklärt etwas.", "front": True}
            for n in range(5)
        ]

    text = _checklist([], change=five_fields)
    assert "| drill_hole | E5 | 5 Felder vorn, erlaubt 4 |" in text
    assert CRITERIA["E5"].threshold in text


def test_agreement_below_ninety_percent_is_marked() -> None:
    """Zwei Prüfer: 9 von 10 gleich ist erfüllt, 8 von 10 markiert (Konzept §4)."""
    rows = [f"row{n}" for n in range(10)]
    first = [_verdict(row=row, point=2) for row in rows]
    same = [_verdict(row=row, point=2, reviewer="zweitpruefer") for row in rows]
    differ = [
        _verdict(row=row, point=2, reviewer="zweitpruefer", verdict="offen", rm="RM-9")
        for row in rows[:2]
    ]
    nine = function_report.agreement(first + same[1:] + differ[:1])
    eight = function_report.agreement(first + same[2:] + differ)
    assert nine["2"].text() == "90% (9 von 10)" and not nine["2"].flagged
    assert eight["2"].flagged
    assert function_report.agreement(first) == {}


def test_without_a_second_reviewer_the_agreement_is_marked() -> None:
    """Keine Doppelprüfung ist kein Erfolg: die Abhakliste markiert sie."""
    assert "| Übereinstimmung | keine Doppelprüfung | ≥ 90% | markiert |" in _checklist([])


def test_hell_and_dunkel_with_different_accents_is_a_z6_finding() -> None:
    """Z6: hell und dunkel zeigen dieselben Flächen mit derselben Zahl Akzente."""
    light = sample_protocol()
    dark = copy.deepcopy(light)
    dark["variant"]["theme"] = "dark"
    dark["layout"][0]["accents"] = 0
    cases = [judge_case(p, sample_context()) for p in (light, dark)]
    merged = merge_cases(cases, [light, dark])
    assert merged.criteria["Z6"].verdict == "fund"
    assert merged.points[19].verdict == "fund"
    assert merge_cases(cases[:1], [light]).criteria["Z6"].verdict == "erfuellt"


def test_a_finding_in_one_language_is_a_finding_of_the_row() -> None:
    """Zusammengeführt über Varianten: Der Fund einer Sprache gilt der Zeile."""
    german = sample_protocol()
    french = copy.deepcopy(german)
    french["variant"]["language"] = "fr"
    french["texts"][1]["need_px"] = 140
    cases = [judge_case(p, sample_context()) for p in (german, french)]
    assert merge_cases(cases, [german, french]).points[9].verdict == "fund"


# --- Bericht über einen Lauf ----------------------------------------------------


def _run_folder(tmp_path: Path, protocols: list[dict[str, Any]]) -> Path:
    out = tmp_path / "lauf"
    out.mkdir(parents=True, exist_ok=True)
    for number, protocol in enumerate(protocols, 1):
        case = out / "cases" / str(number)
        case.mkdir(parents=True)
        (case / "function.json").write_text(
            json.dumps(protocol, ensure_ascii=False), encoding="utf-8"
        )
    (out / "rows.json").write_text(json.dumps(ROWS, ensure_ascii=False), encoding="utf-8")
    return out


def _write(out: Path, state: Path, **values: Any) -> int:
    return write(
        out,
        state=state,
        date="2026-10-12",
        context=sample_context(),
        solutions=SOLUTIONS,
        common_goals={"flaeche_bohren": "operation:drill_hole"},
        **values,
    )


def test_the_report_writes_one_deterministic_checklist_per_package(tmp_path: Path) -> None:
    """``report``: je Paket eine Abhakliste, beim zweiten Lauf dieselben Bytes."""
    state = tmp_path / "state"
    command = sample_protocol()
    command["row"] = {**ROWS[2], "requirement": "leer", "target": "menu:x"}
    command["kind"], command["package"] = "fensterbefehl", "D10"
    out = _run_folder(tmp_path, [sample_protocol(), command])
    assert _write(out, state) == 0
    written = sorted(path.name for path in state.glob("abhakliste-*.md"))
    assert written == ["abhakliste-d04.md", "abhakliste-d10.md"]
    first = (state / "abhakliste-d04.md").read_bytes()
    assert _write(out, state) == 0
    assert (state / "abhakliste-d04.md").read_bytes() == first
    lists = read_checklists(state)
    assert lists["D10"].window_commands == {"Bearbeiten/Parameter anlegen …"}
    results = json.loads((out / "function_results.json").read_text(encoding="utf-8"))
    assert results[0]["row"] == "drill_hole"
    assert {r.get("point") for r in results[0]["results"]} >= set(CHECKPOINTS)


def test_the_report_rejects_invalid_input_with_exit_one(tmp_path: Path) -> None:
    """Ausgang 1 nur bei ungültigen Eingaben; die Abhakliste nennt die Abweisung.

    Die Kommandozeile des Prüfstands (``file_acceptance.py report``) liest den Ausgang.
    """
    state = tmp_path / "state"
    state.mkdir()
    (state / "urteile-d04.toml").write_text(
        '[[verdict]]\nrow = "drill_hole"\npoint = 2\nverdict = "offen"\nreviewer = "stufe_b"\n'
        'reason = "zu viele Klicks"\nimage = "cases/1/a.png"\nplace = "Karte"\n',
        encoding="utf-8",
    )
    out = _run_folder(tmp_path, [sample_protocol()])
    assert _write(out, state, package="D4") == 1
    text = (state / "abhakliste-d04.md").read_text(encoding="utf-8")
    assert "## Abgewiesene Urteile" in text and "offen ohne RM-Nummer" in text


def test_an_invalid_protocol_is_invalid_input(tmp_path: Path) -> None:
    """Ein Protokoll mit unbekanntem Feld ist eine ungültige Eingabe, kein stiller Fall."""
    protocol = sample_protocol()
    protocol["surprise"] = True
    out = _run_folder(tmp_path, [protocol])
    assert _write(out, tmp_path / "state", package="D4") == 1


def test_a_language_case_surface_reaches_the_row_of_its_function(tmp_path: Path) -> None:
    """Ein Sprachfall legt je Fläche ein Protokoll ab; Prüfpunkt 9 sieht es an der Zeile."""
    out = _run_folder(tmp_path, [sample_protocol()])
    french = sample_protocol()
    french["variant"]["language"] = "fr"
    french["texts"][1]["need_px"] = 140
    surfaces = out / "cases" / "2" / "surfaces"
    surfaces.mkdir(parents=True)
    (surfaces / "drill_hole.json").write_text(json.dumps(french), encoding="utf-8")
    state = tmp_path / "state"
    assert _write(out, state, package="D4") == 0
    line = next(
        line
        for line in (state / "abhakliste-d04.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| drill_hole")
    )
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    assert cells[3 + 8] == "Fund", cells


# --- Wächter: Skill, Startgröße, Satz der groben Vorschau ------------------------


SKILLS = {
    "ux-review": ROOT / ".claude" / "skills" / "ux-review" / "SKILL.md",
    "ui-design": ROOT / ".claude" / "skills" / "ui-design" / "SKILL.md",
}


@pytest.mark.parametrize("skill", sorted(SKILLS))
def test_the_criteria_tables_in_the_skills_match_the_constants(skill: str) -> None:
    """Skill-Text und Konstante sind ein gehaltener Zwilling (``zwillinge.md``).

    Konzept §4.

    Das Skill ist die Quelle für Menschen, ``function_checks`` die für den
    Prüfstand. Verglichen werden die Kennungen, die Zahlen jeder Schwelle,
    die Stufen und die Protokollfelder der Messung.
    """
    text = SKILLS[skill].read_text(encoding="utf-8")
    assert skill_mismatches(skill, text) == []


def test_the_skill_guard_sees_a_changed_threshold() -> None:
    """Die Gegenprobe des Wächters: eine Schwelle mit anderer Zahl wird gefunden."""
    rows = [
        f"| {key} | x | {c.threshold} | {', '.join(c.stages)} | `{(c.fields or ('steps',))[0]}` |"
        for key, c in CRITERIA.items()
        if c.skill == "ux-review"
    ]
    table = (
        "| Kennung | Zählgröße | Schwelle | Stufe | Messung |\n|---|---|---|---|---|\n"
        + "\n".join(rows)
    )
    assert len(skill_rows(table)) == 13
    good = [
        problem
        for problem in skill_mismatches("ux-review", table)
        if "Protokollfelder" not in problem
    ]
    assert good == []
    changed = table.replace("| ≤ 3; am Merkmal ≤ 2", "| ≤ 4; am Merkmal ≤ 2")
    assert any("E1 Schwelle" in p for p in skill_mismatches("ux-review", changed))
    missing = "\n".join(line for line in table.splitlines() if not line.startswith("| V6"))
    assert any("V6 fehlt" in p for p in skill_mismatches("ux-review", missing))
    assert skill_mismatches("ux-review", "kein Text") != []


def test_threshold_numbers_read_like_a_reader() -> None:
    """Zahlwörter zählen, Verweise und Kontrastnenner nicht."""
    assert threshold_numbers("≥ 4,5 : 1, große Schrift ≥ 3 : 1") == {4.5, 3.0}
    assert threshold_numbers("nur die vier Stufen aus `LEVELS`") == {4.0}
    assert threshold_numbers("0, außer den Ausnahmen aus Z2 und Konzept §4") == {0.0}
    assert threshold_numbers("100 %; höchstens die Hälfte") == {100.0, 50.0}
    assert threshold_numbers("1920 × 1080 und 3840 × 2160") == {1920.0, 1080.0, 3840.0, 2160.0}


def test_z6_names_the_smallest_screen_and_not_the_start_size() -> None:
    """Z6 misst an der kleinsten Fläche, 1920 × 1080 logisch (Festlegung Robert).

    ``main_window.START_SIZE`` ist nur die Größe beim Verkleinern; Z6 nennt sie
    nicht mehr. Die kleinste Fensterfläche ist der kleinste Schirm ohne
    Taskleiste, und die Schwelle von Z6 nennt genau diesen Schirm.
    """
    assert set(SMALLEST_SCREEN) <= set(CRITERIA["Z6"].numbers)
    assert not set(START_SIZE) & set(CRITERIA["Z6"].numbers)
    assert (SMALLEST_SCREEN[0], SMALLEST_SCREEN[1] - TASKBAR_HEIGHT) == SMALLEST_WINDOW
    assert "LAPTOP_SIZE" not in vars(function_checks)


def test_the_coarse_preview_sentence_is_the_one_the_window_shows() -> None:
    """Prüfpunkt 3 sucht den Satz der groben Vorschau; jeder Katalog muss ihn kennen.

    Ändert die Anwendung den Satz, verschwindet er aus den Katalogen
    (``test_translations`` duldet keine verwaisten Einträge) — und hier wird
    es rot, bevor der Prüfstand jede grobe Vorschau als Fund meldet.
    """
    from app.i18n.catalog import available_languages, read_catalog

    # Gesucht über den ganzen Baum: Zieht der Satz mit dem Code um
    # (Codestruktur), bleibt der Wächter grün, solange es ihn gibt.
    sources = sorted((ROOT / "app").rglob("*.py"))
    assert len(sources) > 100
    assert any(COARSE_NOTE in source.read_text(encoding="utf-8") for source in sources)
    for language in available_languages()[1:]:
        assert read_catalog(language).get(COARSE_NOTE), language


def test_words_count_like_a_reader() -> None:
    """Die eine Wortzählung für E5 und die Lead-Grenze."""
    # Der Gedankenstrich ist kein Wort, die Ziffer schon.
    assert words("Bohrt ein rundes Loch — 5 mm tief.") == 7


# --- Kontext aus dem Baum --------------------------------------------------------


def test_the_frozen_long_texts_are_read() -> None:
    """V2 liest den eingefrorenen Bestand; leer hieße: V2 prüft nichts."""
    assert len(function_report.read_frozen_texts()) > 10


def test_the_finding_kinds_split_into_solved_and_proposals() -> None:
    """I4 zählt Befundarten mit und ohne behebende Handlung — beide Seiten belegt."""
    kinds = function_report.finding_solutions()
    assert len(kinds) > 50
    assert any(kinds.values()) and not all(kinds.values())
    assert kinds["arrange.out_of_build_volume"] is True


def test_the_agent_and_the_manual_know_a_real_operation() -> None:
    """Prüfpunkte 11 und 17 am Register: Handbuchstelle und Ort des Agenten."""
    from app.core.bootstrap import load_operations

    load_operations()
    row = {"id": "drill_hole", "kind": "operation"}
    assert function_report.manual_place(row)
    where, path = function_report.agent_place(row) or ("", "")
    assert where in {"menue", "karte", "katalog"} and path
    assert function_report.manual_place({"id": "erfunden", "kind": "operation"}) is None
    assert function_report.agent_place({"id": "Datei/Speichern", "kind": "fensterbefehl"}) is None


def test_the_vocabulary_reader_takes_patterns_and_languages(tmp_path: Path) -> None:
    """V1 liest Wort, Sprache und Muster; ohne Datei ist V1 nicht prüfbar, nie gut."""
    path = tmp_path / "vocabulary.json"
    path.write_text(
        json.dumps(
            {
                "negative": [
                    {"word": "Voxel", "language": "de", "pattern": "[Vv]oxel\\w*"},
                    {"word": "watertight", "language": "en"},
                ]
            }
        ),
        encoding="utf-8",
    )
    read = function_report.read_negative_words(path)
    assert read[0] == ("Voxel", "de", "[Vv]oxel\\w*")
    assert read[1][:2] == ("watertight", "en")
    assert function_report.read_negative_words(tmp_path / "fehlt.json") == ()
    context = replace(sample_context(), negative_words=())
    case = judge_case(sample_protocol(), context)
    assert case.criteria["V1"].verdict == "nicht_pruefbar"
    # Und der Prüfpunkt darüber wird nicht „B“, das ein Urteil „gut“ schließen könnte.
    assert case.points[8].verdict == "nicht_pruefbar"


def test_the_checked_in_vocabulary_drives_v1() -> None:
    """Die Wortliste von Teilpaket L trägt Muster je Sprache, und V1 greift mit ihnen."""
    if not function_report.VOCABULARY.is_file():
        pytest.skip("customer_vocabulary.json liegt erst mit Teilpaket L im Baum")
    words_and_patterns = function_report.read_negative_words()
    assert len(words_and_patterns) > 10
    context = replace(sample_context(), negative_words=words_and_patterns)

    def manifold(protocol: dict[str, Any]) -> None:
        protocol["texts"][0]["text"] = "Das Netz ist kein Manifold."

    assert judge_case(sample_protocol(), context).criteria["V1"].verdict == "erfuellt"
    changed = sample_protocol()
    manifold(changed)
    assert judge_case(changed, context).criteria["V1"].verdict == "fund"


def test_a_language_without_negative_words_leaves_v1_to_the_source() -> None:
    """Führt die Liste für eine Sprache nichts, gilt V1 dort nicht — statt still „gut“."""
    protocol = sample_protocol()
    protocol["variant"]["language"] = "fr"
    assert "V1" not in judge_case(protocol, sample_context()).criteria
    protocol["variant"]["language"] = "en"
    protocol["texts"][0]["text"] = "Makes the body watertight."
    assert judge_case(protocol, sample_context()).criteria["V1"].verdict == "fund"


def test_the_common_goals_reader_maps_goals_to_targets(tmp_path: Path) -> None:
    """I3 liest ``[[goal]]`` mit ``id`` und ``target`` und zählt an der Zeile mit diesem Ziel."""
    path = tmp_path / "goals.toml"
    path.write_text(
        '[[goal]]\nid = "loch"\ntarget = "operation:drill_hole"\n'
        '[[goal]]\nid = "rund"\ntarget = "edge:fillet_edges"\n',
        encoding="utf-8",
    )
    goals = function_report.read_common_goals(path)
    assert goals == {"loch": "operation:drill_hole", "rund": "edge:fillet_edges"}
    case = _judged()
    values = package_values({case.row_id: case}, [], common_goals=goals, solutions=SOLUTIONS)
    assert values.goals.text() == "100% (1 von 1)"
    if function_report.COMMON_GOALS.is_file():
        assert len(function_report.read_common_goals()) >= 10


# --- Fensterbefehle -----------------------------------------------------------------


def test_the_window_command_comparison_finds_missing_and_stale_rows() -> None:
    """Die Gegenprobe des ``rendered``-Tests: neu, verschwunden, umgezogen."""
    menubar = {"Datei/Neu": "D1", "Datei/Öffnen …": "D1", "Hilfe/Handbuch": "D12"}
    same = compare_window_commands(menubar, {"D1": ["Datei/Neu", "Datei/Öffnen …"]})
    assert same.missing == () and same.stale == () and same.unchecked == ("D12",)
    changed = compare_window_commands(
        menubar, {"D1": ["Datei/Neu", "Datei/Schließen"], "D12": ["Datei/Öffnen …"]}
    )
    assert ("D1", "Datei/Öffnen …") in changed.missing
    assert ("D12", "Hilfe/Handbuch") in changed.missing
    assert ("D1", "Datei/Schließen") in changed.stale
    assert ("D12", "Datei/Öffnen …") in changed.stale


@pytest.mark.rendered
def test_the_menu_bar_matches_the_window_commands_of_every_checklist(window: MainWindow) -> None:
    """Die Fensterbefehle entstehen erst am gebauten Fenster (Konzept Funktionsdurchgang §3).

    Ihre Vollständigkeit hält dieser Test: Jeder Fensterbefehl — Menüzeile oder
    Aktion der Auswahlkarte wie ``command:edit.auto_split`` — steht in der
    Abhakliste seines Pakets, und keine Abhakliste nennt einen, den es nicht
    mehr gibt. Rot heißt: ``tools/file_acceptance.py inventory --functions`` und
    ``report`` für das Paket neu fahren, kein Codefix.
    """
    checklists = read_checklists(STATE)
    assert checklists, f"keine Abhakliste unter {STATE} — der Prüfstand lief noch nie"
    comparison = compare_window_commands(
        function_report.window_commands_of(window),
        {package: listed.window_commands for package, listed in checklists.items()},
    )
    assert not comparison.missing, f"in keiner Abhakliste: {comparison.missing}"
    assert not comparison.stale, f"nicht mehr in der Menüleiste: {comparison.stale}"


def test_the_menu_bar_and_the_function_list_meet_at_the_window(window: MainWindow) -> None:
    """Die Erwartung des ``rendered``-Tests entsteht wie im Prüfstand (Review M3).

    Menüleiste über ``function_list.menubar_of``, Fensterbefehle über
    ``function_list.rows`` — die Fensteraktionen der Auswahlkarte gehören dazu
    und stehen in ihrem Paket. Eine Abhakliste aus genau diesen Zeilen ist
    vollständig und ohne Veraltetes.
    """
    expected = function_report.window_commands_of(window)
    assert len(expected) > 20, sorted(expected)
    assert expected.get("command:edit.auto_split") == "D8"
    lists: dict[str, set[str]] = {}
    for command, package in expected.items():
        lists.setdefault(package, set()).add(command)
    comparison = compare_window_commands(expected, lists)
    assert comparison.missing == () and comparison.stale == ()


def test_function_checks_reads_no_window() -> None:
    """Das Urteil braucht kein Fenster: kein Widget, keine QApplication in den Werkzeugen."""
    from tools import function_judges, function_points, function_samples

    modules = (function_checks, function_judges, function_points, function_samples)
    for module in (*modules, function_report):
        source = Path(str(module.__file__)).read_text(encoding="utf-8")
        assert "QApplication(" not in source and "QWidget(" not in source, module.__name__


# --- Fixrunde nach dem Review D0-U ------------------------------------------


def test_the_report_survives_a_case_it_cannot_judge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scheitert das Urteil an einem Fall, ist das eine ungültige Eingabe, kein Absturz (S4)."""

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise TypeError("float() argument must be a string or a real number, not 'NoneType'")

    monkeypatch.setattr(function_report, "judge_case", broken)
    out = _run_folder(tmp_path, [sample_protocol()])
    assert _write(out, tmp_path / "state", package="D4") == 1
    assert "ungültig: 1/function.json: TypeError" in capsys.readouterr().out


def test_the_report_reads_null_as_not_measured(tmp_path: Path) -> None:
    """Die Werte, die der Prüfstand nach einem Fehlschlag schreibt, ergeben eine Liste (S4)."""
    protocol = sample_protocol()
    protocol["timing"]["total_s"] = None
    protocol["frames"]["raw_drag_ms"] = [None, 12.0]
    protocol["abort"]["eval_s"] = None
    assert validate_protocol(protocol) == []
    out = _run_folder(tmp_path, [protocol])
    assert _write(out, tmp_path / "state", package="D4") == 0


def test_an_empty_run_writes_nothing(tmp_path: Path) -> None:
    """Ohne Protokoll bleibt die Abhakliste, wie sie ist, und der Ausgang ist 1 (M4)."""
    state = tmp_path / "state"
    state.mkdir()
    kept = state / "abhakliste-d04.md"
    kept.write_text("alt\n", encoding="utf-8")
    out = _run_folder(tmp_path, [])
    assert _write(out, state, package="D4") == 1
    assert kept.read_text(encoding="utf-8") == "alt\n"
    assert not (out / "function_results.json").exists()


def test_only_packages_with_a_case_get_a_checklist(tmp_path: Path) -> None:
    """Ein Paket ohne einen Fall bekommt keine neue Abhakliste (L16)."""
    state = tmp_path / "state"
    out = _run_folder(tmp_path, [sample_protocol()])
    assert _write(out, state) == 0
    assert sorted(path.name for path in state.glob("abhakliste-*.md")) == ["abhakliste-d04.md"]


def test_i3_judges_only_the_rows_of_common_goals() -> None:
    """Der Menüklick eines Fensterbefehls ist kein Fund an Prüfpunkt 19 (M2)."""
    from tools.function_samples import click_step

    def menu_row(protocol: dict[str, Any]) -> None:
        protocol["row"].update(
            {"id": "Datei/Speichern unter …", "kind": "fensterbefehl", "requirement": "leer"}
        )
        protocol["row"]["target"] = "menu:menubar.datei.speichern_unter"
        protocol["kind"] = "fensterbefehl"
        protocol["steps"] = [
            click_step("menu:menubar.datei", "menue", "menue"),
            click_step("menu:menubar.datei.speichern_unter", "menue", phase="übernehmen"),
        ]

    case = _judged(menu_row)
    assert "I3" not in case.criteria
    assert case.points[19].verdict != "fund", case.points[19].issues
    goal = _judged()
    assert goal.criteria["I3"].measurement["way_clicks"] == 0


def test_the_e5_share_stands_in_the_package_values() -> None:
    """Drei vorn bei neun von zehn: der Anteil steht in den Paketwerten (M6)."""
    text = _checklist([])
    assert "| E5-Anteil | 100% (1 von 1) | ≥ 90% | erfüllt |" in text


def test_a_verdict_sample_rejected_for_another_reason_stays_green() -> None:
    """Rot zählt nur aus dem eigenen Grund (L1): ein fremder Mangel macht keine Gegenprobe rot."""
    v4 = next(s for s in BROKEN_SAMPLES if s.subject == "V4" and s.kind == "verdict")
    other = replace(
        v4, verdict={**(v4.verdict or {}), "prediction": "Ein Loch von 5 mm", "image": ""}
    )
    red, detail = is_red(other)
    assert not red and "ohne Bild oder Stelle" in detail
    g9 = next(s for s in BROKEN_SAMPLES if s.subject == "G9" and s.kind == "finding")
    assert g9.finding is not None
    healed = replace(g9, finding=g9.finding.replace("mittel", "leicht").replace("RM-800", "RM"))
    red, detail = is_red(healed)
    assert not red and "Stand" in detail


def test_the_skill_guard_wants_every_field_the_judge_reads() -> None:
    """Felder in beide Richtungen (L2): Nennt das Skill weniger, als das Urteil liest, rot."""
    row = "| E4 | x | ≤ 2; kein Dialog verdeckt die bearbeitete Stelle | A | `steps[].zone` |"
    table = "| Kennung | Zählgröße | Schwelle | Stufe | Messung |\n|---|---|---|---|---|\n" + row
    assert any(
        "E4" in problem and "spot" in problem for problem in skill_mismatches("ux-review", table)
    )


def test_the_thresholds_without_a_code_source_match_the_concept() -> None:
    """Hauptfadenlücke, Übereinstimmung und Anteil des Zweitprüfers wie im Konzept (L3)."""
    import re

    from tools.function_checks import AGREEMENT, MAIN_GAP_MS, SECOND_REVIEW_SHARE

    concept = (ROOT / "konzepte" / "konzept-funktionsdurchgang-2026-10.md").read_text(
        encoding="utf-8"
    )
    flat = " ".join(concept.split())
    gap = re.search(r"Lücke im Hauptfaden ≤ (\d+) ms", flat)
    second = re.search(r"prüft ein zweiter Agent (\d+) % der Zeilen", flat)
    agree = re.search(r"Stimmen weniger als (\d+) % der Urteile", flat)
    assert gap and second and agree, "die Sätze im Konzept haben sich geändert"
    assert int(gap.group(1)) == MAIN_GAP_MS
    assert int(second.group(1)) == round(SECOND_REVIEW_SHARE * 100)
    assert int(agree.group(1)) == round(AGREEMENT * 100)


def test_the_references_point_into_the_concept_that_stays() -> None:
    """Verweise zeigen aufs Konzept, nicht in den Plan im Zustandsordner (L10).

    Der Zustandsordner geht am Ende (Konzept §7); ein Verweis dorthin führt
    dann ins Leere. Jeder Verweis „Konzept §n“ trifft einen Abschnitt.
    """
    import re

    concept = (ROOT / "konzepte" / "konzept-funktionsdurchgang-2026-10.md").read_text(
        encoding="utf-8"
    )
    sections = set(re.findall(r"^## (\d+) ", concept, flags=re.MULTILINE))
    plan = "Plan " + "D0"
    files = [
        "tools/function_checks.py",
        "tools/function_judges.py",
        "tools/function_points.py",
        "tools/function_samples.py",
        "tools/function_report.py",
        "tests/test_function_report.py",
    ]
    stale: list[str] = []
    for name in files:
        text = (ROOT / name).read_text(encoding="utf-8")
        stale += [f"{name}: {plan}" for _ in range(text.count(plan))]
        stale += [
            f"{name}: Konzept §{number}"
            for number in re.findall(r"Konzept(?: Funktionsdurchgang)? §(\d+)", text)
            if number not in sections
        ]
    assert not stale, stale


def test_the_value_lists_are_the_ones_the_application_and_the_finding_file_use() -> None:
    """Zwillinge mit Bindung (L4): Wortschatz von W, Handbuchfenster, Arten und Schwere."""
    import re
    from typing import get_args

    from app.ui.guide_targets import ClickReason, Zone
    from app.ui.manual_window import ManualWindow
    from tools.function_checks import (
        FINDING_KINDS,
        MANUAL_WINDOW,
        PROTOCOL_SCHEMA,
        SEVERITIES,
        WHY,
        ZONES,
    )
    from tools.function_list import ROW_KINDS as LISTED_KINDS

    assert get_args(ClickReason) == WHY
    assert get_args(Zone) == ZONES
    assert ManualWindow.__name__ == MANUAL_WINDOW
    assert PROTOCOL_SCHEMA["kind"].choices is LISTED_KINDS
    table = (STATE / "funde.md").read_text(encoding="utf-8")
    kinds = re.search(r"^\| Art \| (.+) \|$", table, flags=re.MULTILINE)
    severities = re.search(r"^\| Schwere \| (.+?) \(", table, flags=re.MULTILINE)
    assert kinds and severities
    assert tuple(part.strip() for part in kinds.group(1).split(",")) == FINDING_KINDS
    assert tuple(part.strip() for part in severities.group(1).split(",")) == SEVERITIES


def test_motion_that_was_not_measured_is_not_motion_off() -> None:
    """``variant.motion = null`` heißt nicht gemessen, nicht „Bewegung aus“ (L6)."""

    def unknown(protocol: dict[str, Any]) -> None:
        protocol["variant"]["motion"] = None

    assert _judged(unknown).criteria["G8"].verdict == "erfuellt"


@pytest.mark.parametrize("order", ["b_zuerst", "c_zuerst"])
def test_two_stages_on_one_point_settle_on_the_open_one(order: str) -> None:
    """Urteile der Stufen B und C an einem Punkt: „offen“ vor „gut“, in jeder Folge (L7)."""
    entries = [v for v in _b_verdicts() if v["point"] != 1] + [
        _verdict(point=1),
        _verdict(point=1, reviewer="stufe_c", verdict="offen", rm="RM-805"),
    ]
    if order == "c_zuerst":
        entries.reverse()
    line = next(
        line for line in _checklist(entries).splitlines() if line.startswith("| drill_hole")
    )
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    assert cells[3] == "offen" and "RM-805" in cells[-2]


def test_the_coarse_preview_follows_the_bench_not_the_scene_sum() -> None:
    """Grob ist, was der Prüfstand am Fall sah (``preview.coarse``), nicht die Summe (L11)."""

    def many_triangles(protocol: dict[str, Any]) -> None:
        protocol["scene"]["triangles"] = 2 * 100_000

    assert _judged(many_triangles).points[3].verdict == "erfuellt"


def test_an_open_finding_keeps_a_fulfilled_point_open() -> None:
    """Ein offener Fund aus der Funddatei lässt die Zeile nicht „gut“ werden (L18)."""
    findings, _problems = parse_findings(_finding(subject="1", kind="Einfachheit"))
    case = _judged()
    cases = {case.row_id: case}
    checked = check_verdicts(_b_verdicts(), outcomes=cases)
    values = package_values(cases, checked.accepted, common_goals={}, solutions=SOLUTIONS)
    text = render_checklist(
        "D4",
        rows=ROWS[:1],
        cases=cases,
        verdicts=checked,
        findings={f.key: f for f in findings},
        values=values,
        commit="a280ee8f5",
        date="2026-10-12",
        out="F:/tmp-suche/lauf",
    )
    line = next(line for line in text.splitlines() if line.startswith("| drill_hole"))
    assert "| offen RM-800 |" in line


def test_evidence_names_the_file_of_the_case() -> None:
    """Belege zeigen auf die Datei des Falls, auch bei Sprachfällen (L19)."""
    case = judge_case(sample_protocol(), sample_context(), source="2/surfaces/drill_hole.json")
    assert "2/surfaces/drill_hole.json#texts" in case.points[9].evidence


def test_a_hand_edited_checklist_is_noticed() -> None:
    """Die Abhakliste trägt eine Prüfsumme; eine Änderung von Hand fällt auf (L20)."""
    text = _checklist(_b_verdicts())
    assert function_report.checklist_intact(text)
    assert not function_report.checklist_intact(text.replace("| gut |", "| gut nach Fix |", 1))


def test_every_checked_in_checklist_is_untouched() -> None:
    """Der Wächter im Tor: Jede Abhakliste im Zustandsordner ist erzeugt, nicht bearbeitet."""
    found = sorted(STATE.glob("abhakliste-*.md"))
    if not found:
        pytest.skip("noch keine Abhakliste — der Probelauf schreibt die ersten")
    tampered = [
        p.name for p in found if not function_report.checklist_intact(p.read_text(encoding="utf-8"))
    ]
    assert tampered == []


def test_light_and_dark_compare_the_cases_that_measured_the_layout() -> None:
    """Hell gegen dunkel nimmt die Fälle mit Hauptknöpfen, nicht den ersten hellen (L21)."""
    licence = sample_protocol()
    licence.pop("layout")
    licence["variant"]["set"] = "lizenz"
    basis = sample_protocol()
    basis["variant"]["set"] = "basis"
    dark = sample_protocol()
    dark["variant"]["theme"] = "dark"
    protocols = [licence, basis, dark]
    cases = [judge_case(p, sample_context()) for p in protocols]
    assert merge_cases(cases, protocols).criteria["Z6"].verdict == "erfuellt"


def test_the_agent_place_is_the_branch_menu_path_takes() -> None:
    """Der Ort des Agenten kommt aus derselben Verzweigung wie sein Menüpfad (L14)."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY, catalogue_operations, menu_path, menu_place

    load_operations()
    places = {spec.name: menu_place(spec) for spec in REGISTRY.all()}
    assert {"menue", "karte", "katalog"} == set(places.values())
    for name in catalogue_operations():
        assert places[name] == "katalog"
    row = {"id": "drill_hole", "kind": "operation"}
    assert function_report.agent_place(row) == (
        places["drill_hole"],
        menu_path(REGISTRY.get("drill_hole")),
    )


# --- Ergänzung aus dem Review von P: Urteile nur hier ---------------------------


def test_the_raw_bases_are_the_counted_classes_and_the_file_dialog() -> None:
    """P nimmt rohe Fenster über ``RAW_BASES`` auf; gezählt wird nur ``RAW_CLASSES``.

    Der Systemdateidialog ist roh, aber erlaubt (Z5) — der Prüfstand nimmt ihn
    auf, das Urteil zählt ihn nicht (Review P, M9: eine Liste statt einer Abschrift).
    """
    from tools.function_checks import RAW_ALLOWED, RAW_BASES, RAW_CLASSES

    assert (*RAW_CLASSES, RAW_ALLOWED) == RAW_BASES
    assert f"`{RAW_ALLOWED}`" in CRITERIA["Z5"].threshold

    def file_dialog(protocol: dict[str, Any]) -> None:
        protocol["raw_windows"] = [{"class": RAW_ALLOWED, "title": "Öffnen", "allowed": False}]

    assert _judged(file_dialog).criteria["Z5"].verdict == "erfuellt"


def test_the_tab_chain_ends_before_it_wraps_or_leaves() -> None:
    """Der Umlauf zum Anfang und das Glied aus dem Dialog hinaus sind kein Rücksprung.

    So schreibt P die Kette (``function_capture.tab_chain``): Sie endet mit dem
    Widget, das wiederkommt, oder mit dem, das ``root`` verlässt
    (``inside: false``). Ein Rücksprung mitten in der Kette bleibt ein Fund.
    """

    def wraps(protocol: dict[str, Any]) -> None:
        chain = protocol["tab_chain"]
        chain.append(dict(chain[0]))

    def leaves(protocol: dict[str, Any]) -> None:
        protocol["tab_chain"].append(
            {"name": "Objektbaum", "rect": [-400, 0, 200, 600], "inside": False}
        )

    def jumps_then_wraps(protocol: dict[str, Any]) -> None:
        chain = protocol["tab_chain"]
        chain[1], chain[2] = chain[2], chain[1]
        chain.append(dict(chain[0]))

    assert validate_protocol(_protocol_with(leaves)) == []
    assert _judged(wraps).points[10].verdict == "erfuellt"
    assert _judged(leaves).points[10].verdict == "erfuellt"
    jumped = _judged(jumps_then_wraps).points[10]
    assert jumped.verdict == "fund"
    assert [issue.text for issue in jumped.issues] == [
        "Rücksprung in der Tab-Kette: Übernehmen → Tiefe"
    ]


def test_a_state_image_not_taken_is_not_measured() -> None:
    """Fehlt ein Zustand im Protokoll, ist er nicht gemessen — kein Fund an G5."""

    def no_focus(protocol: dict[str, Any]) -> None:
        for entry in protocol["state_images"]:
            entry["states"].pop("focus", None)

    outcome = _judged(no_focus).criteria["G5"]
    assert outcome.verdict == "nicht_gelaufen", outcome
    assert not outcome.issues


def test_the_drag_delay_is_raw_and_converted_once() -> None:
    """``frames.raw_drag_ms`` ist roh, ``frames.reference_factor`` rechnet einmal um.

    P schreibt die rohe Messung und den Faktor (Review P, M3); das alte Feld
    ``drag_ms``, in dem P schon umgerechnet hatte, ist ungültig.
    """

    def raw(protocol: dict[str, Any]) -> None:
        protocol["frames"] = {"raw_drag_ms": [20.0], "reference_factor": 1.5}

    outcome = _judged(raw).criteria["Z1"]
    assert outcome.verdict == "erfuellt"
    assert outcome.measurement["worst_ms"] == 30.0
    old = _protocol_with(
        lambda protocol: protocol.update(frames={"drag_ms": [30.0], "reference_factor": 1.5})
    )
    assert any("drag_ms" in problem for problem in validate_protocol(old))


def _protocol_with(change: Any) -> dict[str, Any]:
    protocol = copy.deepcopy(sample_protocol())
    change(protocol)
    return protocol


def test_the_budget_is_compared_on_the_reference_machine() -> None:
    """Prüfpunkt 6 rechnet die Dauer einmal auf die Referenz um, wie Z1 (Koordinator).

    Die Überschreitung bleibt ein Verdacht, kein Fund. Ohne Referenzfaktor wird
    roh verglichen, und der Vermerk sagt es.
    """

    def slow_here(protocol: dict[str, Any]) -> None:
        protocol["timing"].update(total_s=1.5, budget_s=1.0)
        protocol["frames"]["reference_factor"] = 0.5

    def slow_there(protocol: dict[str, Any]) -> None:
        protocol["timing"].update(total_s=1.5, budget_s=1.0)
        protocol["frames"]["reference_factor"] = 1.0

    def without_factor(protocol: dict[str, Any]) -> None:
        protocol["timing"].update(total_s=1.5, budget_s=1.0)
        protocol.pop("frames")

    fast = _judged(slow_here).points[6]
    assert fast.verdict == "erfuellt" and not any("Verdacht" in n for n in fast.notes)
    assert fast.measurement["reference_s"] == 0.75
    slow = _judged(slow_there).points[6]
    assert slow.verdict == "erfuellt" and not slow.issues
    assert any(note.startswith("Verdacht: 1.50 s auf der Referenz") for note in slow.notes)
    raw = _judged(without_factor).points[6]
    assert any("roh verglichen" in note for note in raw.notes), raw.notes


def test_times_and_images_read_one_reference_factor() -> None:
    """Z1 und Prüfpunkt 6 lesen den Faktor an derselben Stelle des Protokolls."""

    def factor(protocol: dict[str, Any]) -> None:
        protocol["frames"]["reference_factor"] = 2.0

    case = _judged(factor)
    assert case.criteria["Z1"].measurement["factor"] == 2.0
    assert case.points[6].measurement["reference_factor"] == 2.0


# --- Nachprüfung der Fixrunde (N1 bis N5) ---------------------------------------


def _at_size(size: tuple[int, int], bars: list[dict[str, Any]]) -> dict[str, Any]:
    def change(protocol: dict[str, Any]) -> None:
        protocol["variant"]["window_size"] = list(size)
        protocol["scrollbars"] = bars

    return _protocol_with(change)


def test_z6_is_judged_once_per_row_at_the_smallest_area() -> None:
    """P fährt je Fenstergröße einen Fall; Z6 urteilt einmal je Zeile (N1, Befund C).

    Verlangt ist die kleinste Fläche (``SMALLEST_WINDOW``, 1920 × 1080 logisch
    maximiert); eine größere zählt mit, allein genügt sie nicht. Eine Größe gilt
    als gemessen, wenn ein Fall in ihr lief — auch mit leerer Liste der
    Rollleisten. Eine Rollleiste vorn an der kleinsten Fläche ist ein Fund,
    unterhalb von ihr keiner.
    """
    larger = (2560, 1392)
    smallest, wide = _at_size(SMALLEST_WINDOW, []), _at_size(larger, [])
    cases = [judge_case(protocol, sample_context()) for protocol in (smallest, wide)]
    assert cases[0].criteria["Z6"].verdict == "erfuellt"
    merged = merge_cases(cases, [smallest, wide])
    assert merged.criteria["Z6"].verdict == "erfuellt"
    assert merged.points[19].verdict == "stufe_b"
    alone = merge_cases(cases[1:], [wide])
    assert alone.criteria["Z6"].verdict == "nicht_gelaufen"
    assert f"{SMALLEST_WINDOW[0]} x {SMALLEST_WINDOW[1]}" in alone.criteria["Z6"].reason
    assert alone.points[19].verdict == "nicht_gelaufen"

    def bar_at(size: tuple[int, int]) -> dict[str, Any]:
        return _at_size(
            SMALLEST_WINDOW,
            [
                {
                    "surface": "OperationDialog",
                    "window_size": list(size),
                    "front": True,
                    "vertical": True,
                }
            ],
        )

    shown = bar_at(SMALLEST_WINDOW)
    found = merge_cases([judge_case(shown, sample_context()), cases[1]], [shown, wide])
    assert found.criteria["Z6"].verdict == "fund"
    assert found.points[19].verdict == "fund"
    below = bar_at((1366, 728))
    quiet = merge_cases([judge_case(below, sample_context()), cases[1]], [below, wide])
    assert quiet.criteria["Z6"].verdict == "erfuellt", "unter der Untergrenze kein Fund"


def test_empty_fonts_are_not_measured_like_empty_contrast() -> None:
    """``fonts: []`` heißt: nichts aufgenommen — wie ``contrast: []`` (N3).

    ``icons: []`` dagegen kann stimmen: eine Fläche ohne Symbolknopf.
    """

    def empty(protocol: dict[str, Any]) -> None:
        protocol["fonts"] = []
        protocol["contrast"] = []
        protocol["icons"] = []

    case = _judged(empty)
    assert case.criteria["G4"].verdict == "nicht_gelaufen"
    assert case.criteria["G6"].verdict == "nicht_gelaufen"
    assert case.criteria["G7"].verdict == "erfuellt"


def test_a_drag_event_without_a_picture_is_the_longest_delay() -> None:
    """Bleibt nach einem Ziehereignis das Bild aus, ist das ein Fund; am Ende ein Vermerk (N4)."""

    def middle(protocol: dict[str, Any]) -> None:
        protocol["frames"]["raw_drag_ms"] = [12.0, None, 14.0]

    def end(protocol: dict[str, Any]) -> None:
        protocol["frames"]["raw_drag_ms"] = [12.0, 14.0, None]

    stalled = _judged(middle).criteria["Z1"]
    assert stalled.verdict == "fund"
    assert any("ohne Bild" in issue.text for issue in stalled.issues)
    last = _judged(end).criteria["Z1"]
    assert last.verdict == "erfuellt"
    assert any("ohne Bild" in note for note in last.notes)


def test_the_z1_message_names_the_factor_where_the_schema_puts_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Meldung nennt die Stelle aus ``REFERENCE_FACTOR_AT``, keine feste (N5)."""
    from tools import function_judges

    monkeypatch.setattr(function_judges, "REFERENCE_FACTOR_AT", ("timing", "reference_factor"))
    outcome = _judged().criteria["Z1"]
    assert outcome.verdict == "nicht_gelaufen"
    assert "timing.reference_factor" in outcome.reason


def test_the_spec_format_and_the_licence_names_come_from_the_function_list() -> None:
    """Eine Quelle: L führt Schlüssel, Gründe und Lizenznamen, U importiert sie.

    ``function_list`` und die Module, die es lädt (``function_scan``,
    ``function_scenes``), importieren keines der Urteilsmodule — sonst wäre es
    ein Kreis.
    """
    import ast

    from tools import function_checks, function_list

    assert function_checks.PROTOCOL_SCHEMA["spec"].keys is function_list.SPEC_KEYS
    assert not hasattr(function_checks, "NOT_APPLICABLE")
    # Die Übergangsnamen für den Prüfstand sind weg; er nimmt sie von L.
    for name in ("STARTUP_LICENCE", "licence_runs"):
        assert not hasattr(function_checks, name), name
    assert "LICENCE_STATES" not in getattr(function_checks, "__all__", ())
    assert function_checks.VARIANT_LICENCES is function_list.PRECONDITIONS["licence"]
    assert set(function_checks.LICENCE_UNLOCKED) == set(function_list.LICENCE_STATES)
    own = {"function_list", "function_scan", "function_scenes"}
    folder = Path(function_list.__file__ or "").parent
    seen: set[str] = set()
    todo = ["function_list"]
    while todo:
        module = todo.pop()
        if module in seen:
            continue
        seen.add(module)
        tree = ast.parse((folder / f"{module}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == "tools":
                names = [alias.name for alias in node.names]
            elif (node.module or "").startswith("tools."):
                names = [(node.module or "").removeprefix("tools.")]
            else:
                continue
            for name in names:
                if name.startswith("function_"):
                    assert name in own, f"{module} importiert {name}"
                    todo.append(name)
    assert seen == own, seen


def test_a_row_without_a_drag_does_not_miss_z1() -> None:
    """Steht in ``frames`` nur der Referenzfaktor, gibt es an der Zeile keinen Zug.

    Z1 gilt dann nicht — kein „frames.raw_drag_ms fehlt“. Nennt die Zeile Z1
    in ihrer Spezifikation, fehlt die Messung wirklich.
    """

    def factor_only(protocol: dict[str, Any]) -> None:
        protocol["frames"] = {"reference_factor": 1.0}

    def named(protocol: dict[str, Any]) -> None:
        factor_only(protocol)
        protocol["spec"]["criteria"] = ["Z1"]

    assert "Z1" not in _judged(factor_only).criteria
    missing = _judged(named).criteria["Z1"]
    assert missing.verdict == "nicht_gelaufen"
    assert "frames.raw_drag_ms" in missing.reason
