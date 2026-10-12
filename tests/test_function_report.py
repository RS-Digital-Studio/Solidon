"""Urteile, Gegenproben, Abhakliste und Funddatei des Funktionsdurchgangs (RM-737, D0-U).

Der Prüfstand misst am echten Fenster; hier wird ohne Fenster geprüft, ob
seine Messungen richtig beurteilt werden. Jede Gegenprobe aus Bauplan D0 §3
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

from app.ui.main_window import MainWindow
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window
from tools import function_checks, function_report
from tools.function_checks import (
    CHECKPOINTS,
    COARSE_NOTE,
    CRITERIA,
    START_SIZE,
    Checkpoint,
    check_protocol,
    skill_mismatches,
    skill_rows,
    start_size_in_window,
    threshold_numbers,
    words,
)
from tools.function_judges import CRITERION_JUDGES, POINT_JUDGES, judge_case
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

#: Alle 35 Kennungen aus Konzept §4 — gegen die Tabelle in ``function_checks``.
ALL_CRITERIA = (
    *(f"E{n}" for n in range(1, 8)),
    *(f"V{n}" for n in range(1, 7)),
    *(f"G{n}" for n in range(1, 10)),
    *(f"Z{n}" for n in range(1, 8)),
    *(f"I{n}" for n in range(1, 7)),
)


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
    assert sorted(CHECKPOINTS) == list(range(1, 20))
    assert set(CRITERIA) == set(ALL_CRITERIA)
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
    assert check_protocol(protocol) == []
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
    """Jede Gegenprobe aus Bauplan D0 §3 wird rot — ohne Fenster."""
    red, detail = is_red(sample)
    assert red, f"{sample.subject} {sample.title}: blieb grün ({detail})"


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
    """Prüfpunkt 5: Nur die Auswahl verschieden ist ein Vermerk, nie rot (§3.1)."""

    def other_selection(protocol: dict[str, Any]) -> None:
        protocol["states"]["undo"] = {**protocol["states"]["before"], "selection": []}

    outcome = _judged(other_selection).points[5]
    assert outcome.verdict == "erfuellt"
    assert any("Auswahl" in note for note in outcome.notes)


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
    problems = check_protocol(protocol)
    assert "unbekanntes Feld: surprise" in problems
    assert "steps ist keine Liste" in problems
    assert "Pflichtfeld fehlt: version" in problems


def test_a_row_without_specification_is_valid_but_not_measured() -> None:
    """Eine Zeile ohne Spezifikation ist „ungeprüft“, kein ungültiges Protokoll (§2.3)."""
    protocol = sample_protocol()
    protocol["spec"] = None
    assert check_protocol(protocol) == []
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


def test_the_contrast_sample_is_the_one_the_plan_names() -> None:
    """Die Gegenprobe von G6 trägt 3,9 bei normaler Schrift (§3.3), nicht irgendeinen Wert."""
    from app.ui.theme import contrast_ratio

    assert round(contrast_ratio("#818181", "#ffffff"), 1) == 3.9


def test_every_result_names_its_evidence_as_in_the_plan() -> None:
    """§2.8: je Ergebnis Stufe, Messung, Urteil, Grund, Beleg (Bilder und Protokollstellen)."""
    case = _judged()
    record = case.points[4].record()
    assert record["point"] == 4 and record["stage"] == "A" and record["verdict"] == "erfuellt"
    assert "cases/1/01-vorher.png" in record["evidence"]
    assert "function.json#result" in record["evidence"]
    assert case.criteria["E5"].record()["criterion"] == "E5"


# --- Urteile ----------------------------------------------------------------


def test_good_verdicts_are_accepted() -> None:
    """Die Gegenseite: Was §2.9 erfüllt, wird angenommen."""
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
    """§4.4: Urteile ohne Bild oder Stelle, offen ohne RM, fremder Grund … abgewiesen."""
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
        assert checked.rejected, entry


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
            stand="gut nach Fix `lauf-12`",
        )
    )
    findings, problems = parse_findings(text)
    assert [f.number for f in findings] == [1, 2, 3]
    assert problems + check_findings(findings) == []
    assert findings[1].subjects == (4,)


BAD_FINDINGS = {
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
    "kein Prüfpunkt": (_finding(subject="Q9"), "weder Prüfpunkt noch Kriterium"),
    "Feld fehlt": (
        _finding().replace("**Ursache:** Der Dialog setzt make_primary zweimal.\n", ""),
        "Ursache fehlt",
    ),
}


@pytest.mark.parametrize("name", sorted(BAD_FINDINGS))
def test_a_finding_file_against_the_rules_is_rejected(name: str) -> None:
    """§2.11: Funddatei mit doppelter Nummer, fremder Art oder Schwere, ohne Stand → rot."""
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
    """Gleiche Eingaben, gleiche Bytes — auch in anderer Reihenfolge (§4.4)."""
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
    """E3: mehr als eine Entscheidung ohne B-Urteil ist „B offen“, nie „gut“ (§3.2)."""

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
    for number, protocol in enumerate(protocols, 1):
        case = out / "cases" / str(number)
        case.mkdir(parents=True)
        (case / "function.json").write_text(
            json.dumps(protocol, ensure_ascii=False), encoding="utf-8"
        )
    (out / "function_rows.json").write_text(json.dumps(ROWS, ensure_ascii=False), encoding="utf-8")
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
    out = _run_folder(tmp_path, [sample_protocol()])
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
    """Ausgang 1 nur bei ungültigen Eingaben (§2.13); die Abhakliste nennt die Abweisung."""
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


# --- Wächter: Skill, Startgröße, Satz der groben Vorschau ------------------------


SKILLS = {
    "ux-review": ROOT / ".claude" / "skills" / "ux-review" / "SKILL.md",
    "ui-design": ROOT / ".claude" / "skills" / "ui-design" / "SKILL.md",
}


@pytest.mark.parametrize("skill", sorted(SKILLS))
def test_the_criteria_tables_in_the_skills_match_the_constants(skill: str) -> None:
    """Skill-Text und Konstante sind ein gehaltener Zwilling (§2.12, ``zwillinge.md``).

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
    assert threshold_numbers("1280 × 820 und 1366 × 728") == {1280.0, 820.0, 1366.0, 728.0}


def test_the_start_size_is_the_one_the_window_opens_with() -> None:
    """Z6 misst bei der Startgröße; sie steht in ``MainWindow.__init__`` (gehaltener Zwilling)."""
    source = (ROOT / "app" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert start_size_in_window(source) == START_SIZE
    assert start_size_in_window(
        "class MainWindow:\n    def __init__(self):\n        self.resize(1, 2)\n"
    ) == (1, 2)


def test_the_coarse_preview_sentence_is_the_one_the_window_shows() -> None:
    """Prüfpunkt 3 sucht den Satz der groben Vorschau; jeder Katalog muss ihn kennen.

    Ändert die Anwendung den Satz, verschwindet er aus den Katalogen
    (``test_translations`` duldet keine verwaisten Einträge) — und hier wird
    es rot, bevor der Prüfstand jede grobe Vorschau als Fund meldet.
    """
    from app.i18n.catalog import available_languages, read_catalog

    source = (ROOT / "app" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert COARSE_NOTE in source
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
    assert function_report._manual_place(row)
    where, path = function_report._agent_place(row) or ("", "")
    assert where in {"menue", "karte", "katalog"} and path
    assert function_report._manual_place({"id": "erfunden", "kind": "operation"}) is None
    assert function_report._agent_place({"id": "Datei/Speichern", "kind": "fensterbefehl"}) is None


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
    """Die Fensterbefehle entstehen erst am gebauten Fenster (Konzept §3).

    Ihre Vollständigkeit hält dieser Test: Jede Zeile der Menüleiste steht in
    der Abhakliste ihres Pakets, und keine Abhakliste nennt einen Befehl, den
    es nicht mehr gibt. Rot heißt: ``tools/file_acceptance.py inventory
    --functions`` und ``report`` für das Paket neu fahren, kein Codefix.
    """
    from tools.function_list import MenuEntry, command_rows, load_scenes, registry  # D0-L

    from app.ui.guide_targets import menubar_entries  # Teilpaket D0-W

    checklists = read_checklists(STATE)
    assert checklists, f"keine Abhakliste unter {STATE} — der Prüfstand lief noch nie"
    entries = [
        MenuEntry(name, tuple(path), action.shortcut().toString())
        for name, path, action in menubar_entries(window)
    ]
    rows = command_rows(entries, registry(), load_scenes())
    assert rows, "keine Fensterbefehle an der Menüleiste"
    comparison = compare_window_commands(
        {row.id: row.package for row in rows},
        {package: listed.window_commands for package, listed in checklists.items()},
    )
    assert not comparison.missing, f"in keiner Abhakliste: {comparison.missing}"
    assert not comparison.stale, f"nicht mehr in der Menüleiste: {comparison.stale}"


def test_function_checks_reads_no_window() -> None:
    """Das Urteil braucht kein Fenster: kein Widget, keine QApplication in den Werkzeugen."""
    for module in (function_checks, function_report):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "QApplication(" not in source and "QWidget(" not in source, module.__name__
