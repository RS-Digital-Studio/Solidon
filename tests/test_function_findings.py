"""Funde zwischen Funddatei und Abhakliste (RM-737, Funktionsdurchgang).

Welche Zeilen ein Fund mit „Funktion“ trifft, welchen Fund eine offene Zelle
als Grund nennt, und die Wächter über die eingecheckten Funde und Urteile.
Getrennt von ``tests/test_function_report.py``, das an der Grenze von 2 000
Zeilen steht; geprüft wird dasselbe Werkzeug, ``tools/function_report.py``.
"""

from __future__ import annotations

from typing import Any

from tools import function_report
from tools.function_points import judge_case
from tools.function_report import (
    STATE,
    check_verdicts,
    package_values,
    parse_findings,
    render_checklist,
)
from tools.function_samples import sample_context, sample_protocol


def test_every_checked_in_verdict_file_holds_its_form_on_any_machine() -> None:
    """Wächter zu RD-5: Format, Funde und ``[[run]]`` jeder Urteilsdatei, ohne den Lauf.

    Die Dateien sind aus dem Dateisystem erhoben: Ohne sie wäre der Wächter grün,
    weil er nichts prüft (``tests.md``, Verbotstest über eine leere Menge).
    """
    findings, _problems = function_report.read_findings(STATE / "funde.md")
    paths = sorted(STATE.glob("urteile-*.toml"))
    assert {path.name for path in paths} >= {f"urteile-d{n:02}.toml" for n in (4, 8, 10)}
    for path in paths:
        entries, runs = function_report.read_verdict_file(path)
        assert check_verdicts(entries, findings=findings).rejected == (), path.name
        assert function_report.check_runs(runs, entries) == [], path.name


FINDING = """### FD-{number} Ein Fund

**Art:** Fehler
**Schwere:** mittel
**Funktion:** {rows}
**Prüfpunkt:** {subject}
**Beleg:** cases/1/03-dialog.png
**Ursache:** Ein Satz.
**Vorschlag:** Ein Satz.
**Wirkung beim Kunden:** Ein Satz.
**Stand:** {stand}
"""


def _findings(*given: tuple[int, str, str, str]) -> dict[str, function_report.Finding]:
    """Funde aus (Nummer, Funktion, Prüfpunkt, Stand), gelesen wie die Funddatei."""
    text = "\n".join(
        FINDING.format(number=number, rows=rows, subject=subject, stand=stand)
        for number, rows, subject, stand in given
    )
    findings, problems = parse_findings(text)
    assert problems == [] and len(findings) == len(given)
    return {finding.key: finding for finding in findings}


def _render(entries: list[dict[str, Any]], findings: dict[str, Any]) -> list[str]:
    """Die Zeilen der Abhakliste des Musterfalls ``drill_hole`` (Tabelle 1 und 2)."""
    case = judge_case(sample_protocol(), sample_context())
    cases = {case.row_id: case}
    checked = check_verdicts(entries, outcomes=cases)
    assert checked.rejected == ()
    values = package_values(cases, checked.accepted, common_goals={}, solutions={})
    text = render_checklist(
        "D4",
        rows=[{"id": "drill_hole", "kind": "operation", "package": "D4", "start_scene": "leer"}],
        cases=cases,
        verdicts=checked,
        findings=findings,
        values=values,
        commit="a280ee8f5",
        date="2026-10-15",
        out="F:/tmp-suche/lauf",
    )
    return [line for line in text.splitlines() if line.startswith("| drill_hole |")]


def _open(**where: Any) -> dict[str, Any]:
    return {
        "row": "drill_hole",
        "verdict": "offen",
        "rm": "RM-737",
        "reviewer": "stufe_b",
        "reason": "nicht gemessen",
        "image": "cases/1/01-vorher.png",
        "place": "Merkmalfenster",
        **where,
    }


def test_an_open_cell_names_no_fixed_finding_as_its_reason() -> None:
    """Offen bleibt eine Zelle am Urteil; ein behobener Fund an Zeile und Punkt ist dafür
    kein Grund (Schlussreview D0, RF-5: 20 offene Zellen nannten einen). Dasselbe gilt
    für die Kriterien in Tabelle 2."""
    fixed = _findings((5, "`drill_hole`", "9, V1", "behoben `0123456789`"))
    table, criterion = _render([_open(point=9), _open(criterion="V1")], fixed)
    assert table.split(" | ")[11] == "offen", table
    assert criterion.startswith("| drill_hole | V1 |") and criterion.endswith("| — |"), criterion
    both = fixed | _findings((6, "`drill_hole`", "9, V1", "offen RM-801"))
    table, criterion = _render([_open(point=9), _open(criterion="V1")], both)
    assert table.split(" | ")[11] == "FD-6" and criterion.endswith("| FD-6 |"), (table, criterion)
    own = _render([_open(point=9, finding="FD-5"), _open(criterion="V1", finding="FD-5")], fixed)
    assert own[0].split(" | ")[11] == "FD-5" and own[1].endswith("| FD-5 |"), own
