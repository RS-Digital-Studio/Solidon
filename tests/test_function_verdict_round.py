"""Urteile gegen Funddatei und Vorhersage, Übereinstimmung je Runde (Paket F8, RM-737).

Die Zweitprüfung am finalen Lauf fand 37 Abweichungen; 32 erklärten Prüfstand
und Kriterien, nicht die Prüfer. Diese Datei hält die Regeln, die daraus
folgen, ohne Fenster fest:

* *gut nach Fix* folgt aus der Funddatei, nicht aus einer Lesart (M-Fix);
* V4 zählt nur mit einer vor dem Klick gebundenen Vorhersage (FD-148);
* Zellen ohne Gegenurteil werden ausgewiesen (FD-144);
* bindend ist die Übereinstimmung über alle Pakete einer Runde, die Werte je
  Paket sind Auskunft (FD-145).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.bench_fakes import ROWS
from tools import function_agreement, function_verdict_rules
from tools.function_report import Finding, check_verdicts, parse_findings, write
from tools.function_samples import sample_context, sample_protocol

SHA = "e0deb7e246f28a83b7b72fc175129860947dc4fbb24288865f57587c553574d1"


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


def _findings(*entries: tuple[int, str, str, str]) -> dict[str, Finding]:
    """Funde aus (Nummer, Zeilen, Prüfpunkt, Stand) — so, wie die Funddatei sie schreibt."""
    text = "\n".join(
        f"### FD-{number} Ein Fund\n\n**Art:** Fehler\n**Schwere:** leicht\n"
        f"**Funktion:** {rows}\n**Prüfpunkt:** {subject}\n**Beleg:** cases/1/a.png\n"
        "**Ursache:** belegt\n**Vorschlag:** beheben\n**Wirkung beim Kunden:** keine\n"
        f"**Stand:** {stand}\n"
        for number, rows, subject, stand in entries
    )
    found, problems = parse_findings(text)
    assert problems == []
    return {finding.key: finding for finding in found}


def _reasons(entry: dict[str, Any], findings: dict[str, Finding] | None = None) -> list[str]:
    checked = check_verdicts([entry], findings=findings)
    return [reason for _entry, why in checked.rejected for reason in why]


# --- FD-148: V4 nur mit gebundener Vorhersage --------------------------------------


@pytest.mark.parametrize("verdict", ["gut", "gut_nach_fix"])
def test_a_good_v4_without_a_bound_prediction_is_rejected(verdict: str) -> None:
    """Eine Vorhersage nach dem Lauf, aber vor dem Ansehen, ist kein „gut“ (Fälle 29, 36, 37)."""
    entry = _verdict(criterion="V4", verdict=verdict, prediction="Hebt den Körper um 10 mm.")
    if verdict == "gut_nach_fix":
        entry["finding"] = "FD-35"
    assert function_verdict_rules.UNBOUND_PREDICTION in _reasons(entry)


def test_a_bound_prediction_carries_v4() -> None:
    """Mit Datei und SHA256 der vor dem Klick freigegebenen Vorhersage zählt „gut“."""
    entry = _verdict(
        criterion="V4",
        prediction="Hebt den Körper um 10 mm.",
        prediction_bound=f"v4/prediction-before-click.json SHA256 {SHA}",
    )
    assert _reasons(entry) == []


def test_an_open_v4_needs_no_binding() -> None:
    """*offen* mit RM bleibt ohne Bindung möglich — es behauptet nichts."""
    entry = _verdict(criterion="V4", verdict="offen", rm="RM-737", prediction="Hebt den Körper.")
    assert _reasons(entry) == []


@pytest.mark.parametrize(
    "bound",
    [f"F:\\tmp-suche\\v4\\prediction.json SHA256 {SHA}", "v4/prediction.json ohne Siegel"],
    ids=["laufwerk", "ohne_sha256"],
)
def test_a_binding_needs_a_seal_and_no_drive(bound: str) -> None:
    entry = _verdict(criterion="V4", prediction="Hebt.", prediction_bound=bound)
    assert function_verdict_rules.UNBOUND_PREDICTION in _reasons(entry)


def test_a_binding_belongs_to_a_v4_prediction() -> None:
    entry = _verdict(point=2, prediction_bound=f"v4/a.json SHA256 {SHA}")
    assert "prediction_bound an einem Urteil, das nicht V4 ist" in _reasons(entry)


# --- M-Fix: „gut nach Fix“ folgt aus der Funddatei -----------------------------------


def test_good_over_an_open_finding_of_the_cell_is_rejected() -> None:
    findings = _findings((7, "`drill_hole`", "V1", "offen RM-737"))
    reasons = _reasons(_verdict(point=8), findings)
    assert function_verdict_rules.GOOD_OVER_OPEN in reasons


def test_good_where_a_finding_was_fixed_must_say_so() -> None:
    """Abweichungen 05, 17, 24: „gut“ gegen „gut nach Fix“ an derselben Tatsache."""
    findings = _findings((30, "`drill_hole`", "V5", "behoben `660501d8f`"))
    reasons = _reasons(_verdict(point=7), findings)
    assert any(reason.startswith(function_verdict_rules.GOOD_OVER_FIXED) for reason in reasons)
    assert _reasons(_verdict(point=7, verdict="gut_nach_fix", finding="FD-30"), findings) == []


def test_fixed_after_a_fix_needs_the_fixed_finding_of_this_cell() -> None:
    findings = _findings(
        (30, "`drill_hole`", "V5", "behoben `660501d8f`"),
        (31, "`resize_hole`", "7", "behoben `660501d8f`"),
        (32, "`drill_hole`", "7", "offen RM-737"),
    )
    elsewhere = _verdict(point=7, verdict="gut_nach_fix", finding="FD-31")
    assert function_verdict_rules.FIX_WITHOUT_CELL in _reasons(elsewhere, findings)
    still_open = _verdict(point=7, verdict="gut_nach_fix", finding="FD-30")
    assert function_verdict_rules.GOOD_OVER_OPEN in _reasons(still_open, findings)


def test_a_finding_of_several_rows_marks_each_of_its_cells() -> None:
    findings = _findings((18, "`resize_hole`, `drill_hole`", "I6", "gut nach Fix `ac28ecbb2`"))
    entry = _verdict(criterion="I6", verdict="gut_nach_fix", finding="FD-18", design_judgement=True)
    assert _reasons(entry, findings) == []


def test_a_point_covers_its_criteria_and_nothing_else() -> None:
    assert function_verdict_rules.covered(7) == {7, "V5"}
    assert {"E1", "E2", "E7"} <= function_verdict_rules.covered(2)
    assert function_verdict_rules.covered(8) == {8, "V1", "V2", "V3", "V4", "V5", "V6"}
    assert {"G1", "Z6", "I4"} <= function_verdict_rules.covered(19)
    assert function_verdict_rules.covered("V5") == {"V5"}


def test_without_a_finding_file_the_marking_is_not_checked() -> None:
    """Die Gegenproben ohne Funddatei bleiben, was sie sind."""
    assert _reasons(_verdict(point=7)) == []


# --- FD-144: Zellen ohne Gegenurteil ---------------------------------------------------


def test_cells_without_a_counter_verdict_are_counted_not_dropped() -> None:
    """An den Zeilen des Zweitprüfers fehlt keine Zelle still (77 + 5 im finalen Lauf)."""
    entries = [
        _verdict(row="a", point=2),
        _verdict(row="a", point=2, reviewer="zweitpruefer"),
        _verdict(row="a", criterion="G1"),
        _verdict(row="a", criterion="I1", reviewer="zweitpruefer"),
        # Keine Zeile des Zweitprüfers: kein Paar erwartet.
        _verdict(row="b", criterion="G1"),
    ]
    shares = function_agreement.agreement(entries)
    assert shares["2"].text() == "100% (1 von 1)"
    assert shares["G1"].text() == "nicht gemessen" and shares["G1"].flagged
    assert shares["I1"].flagged
    assert function_agreement.unpaired(entries) == {
        "G1": ("a (nur stufe_b)",),
        "I1": ("a (nur zweitpruefer)",),
    }


# --- FD-145: die Runde ist die Grundmenge -----------------------------------------------


def _pairs(rows: list[str], differ: int) -> list[dict[str, Any]]:
    entries = []
    for number, row in enumerate(rows):
        entries.append(_verdict(row=row, point=9))
        second = "offen" if number < differ else "gut"
        extra = {"rm": "RM-737"} if second == "offen" else {}
        entries.append(_verdict(row=row, point=9, reviewer="zweitpruefer", verdict=second, **extra))
    return entries


def test_the_round_pools_the_packages_and_binds() -> None:
    """Zwei Zeilen mit einer Abweichung sind 50 % — eine Messung ist erst die Runde."""
    small = _pairs(["a", "b"], differ=1)
    large = _pairs([f"r{n}" for n in range(10)], differ=0)
    assert function_agreement.agreement(small)["9"].flagged
    pooled = function_agreement.round_agreement("lauf", {"D4": small, "D8": large})
    assert pooled.packages == ("D4", "D8")
    assert pooled.shares["9"].text() == "92% (11 von 12)"
    assert not pooled.shares["9"].flagged


def _case(tmp_path: Path, number: int, protocol: dict[str, Any]) -> None:
    case = tmp_path / "lauf" / "cases" / str(number)
    case.mkdir(parents=True)
    (case / "function.json").write_text(json.dumps(protocol, ensure_ascii=False), "utf-8")


def _verdict_file(path: Path, run: str, entries: list[dict[str, Any]]) -> None:
    lines = [f'[[run]]\nname = "{run}"\nhead = "a280ee8f5"\nseal = "seal.json {SHA}"\n']
    for entry in entries:
        lines.append("[[verdict]]")
        lines += [
            f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in entry.items()
        ]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def test_the_checklist_binds_the_round_and_informs_per_package(tmp_path: Path) -> None:
    """``report`` rechnet je Paket und über die Runde; nur die Runde markiert (FD-145)."""
    drill = sample_protocol()
    hole = sample_protocol()
    hole["row"] = {**hole["row"], "id": "resize_hole", "package": "D8"}
    hole["package"] = "D8"
    _case(tmp_path, 1, drill)
    _case(tmp_path, 2, hole)
    rows = [{**ROWS[1]}, {**ROWS[0], "package": "D8"}]
    (tmp_path / "lauf" / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    agree = [
        _verdict(row="drill_hole", point=9),
        _verdict(row="drill_hole", point=9, reviewer="zweitpruefer"),
    ]
    differ = [
        _verdict(row="resize_hole", point=9),
        _verdict(row="resize_hole", point=9, reviewer="zweitpruefer", verdict="offen", rm="RM-737"),
        _verdict(row="resize_hole", criterion="G1"),
    ]
    _verdict_file(state / "urteile-d04.toml", "probelauf-x", agree)
    _verdict_file(state / "urteile-d08.toml", "probelauf-x", differ)
    write(
        tmp_path / "lauf",
        state=state,
        date="2026-10-15",
        context=sample_context(),
        solutions={},
        common_goals={},
    )
    d08 = (state / "abhakliste-d08.md").read_text(encoding="utf-8")
    assert "| Runde | probelauf-x: D4, D8 |" in d08
    assert "| Übereinstimmung 9 in der Runde | 50% (1 von 2) | ≥ 90% | markiert |" in d08
    assert "| Übereinstimmung 9 im Paket | 0% (0 von 1) | Auskunft | — |" in d08
    assert "| Ohne Gegenurteil G1 | 1 Zelle: resize_hole (nur stufe_b) |" in d08
    d04 = (state / "abhakliste-d04.md").read_text(encoding="utf-8")
    assert "| Übereinstimmung 9 in der Runde | 50% (1 von 2) | ≥ 90% | markiert |" in d04
