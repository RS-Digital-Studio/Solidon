"""Funde zwischen Funddatei und Abhakliste (RM-737, Funktionsdurchgang).

Welche Zeilen ein Fund mit „Funktion“ trifft, welchen Fund eine offene Zelle
als Grund nennt, und die Wächter über die eingecheckten Funde und Urteile.
Getrennt von ``tests/test_function_report.py``, das an der Grenze von 2 000
Zeilen steht; geprüft wird dasselbe Werkzeug, ``tools/function_report.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tools import function_report, function_verdict_rules
from tools.function_list import rows as function_rows
from tools.function_points import judge_case
from tools.function_report import (
    STATE,
    check_finding_rows,
    check_verdicts,
    package_values,
    parse_findings,
    read_checklists,
    render_checklist,
)
from tools.function_samples import sample_context, sample_protocol


def test_every_checked_in_verdict_file_holds_its_form_on_any_machine() -> None:
    """Wächter zu RD-5: Format, Funde und ``[[run]]`` jeder Urteilsdatei, ohne den Lauf.

    Die Dateien sind aus dem Dateisystem erhoben: Ohne sie wäre der Wächter grün,
    weil er nichts prüft (``tests.md``, Verbotstest über eine leere Menge).

    **Ohne die Regeln der Runde** (``round_rules=False``): Bindung der Vorhersage
    und Kennzeichnung nach dem Stand der Funddatei gelten zur Zeit der Runde und
    prüft ``report`` (``check_verdicts``); die Funddatei wächst und wird behoben,
    die Urteile einer Runde bleiben, was sie waren (RC-2). Die Form prüft der
    Wächter weiter — die Gegenprobe unten weist ein verdorbenes Urteil ab.
    """
    findings, _problems = function_report.read_findings(STATE / "funde.md")
    paths = sorted(STATE.glob("urteile-*.toml"))
    assert {path.name for path in paths} >= {f"urteile-d{n:02}.toml" for n in (4, 8, 10)}
    for path in paths:
        entries, runs = function_report.read_verdict_file(path)
        checked = check_verdicts(entries, findings=findings, round_rules=False)
        assert checked.rejected == (), path.name
        assert function_report.check_runs(runs, entries) == [], path.name
        # Gegenprobe: Ohne die Regeln der Runde bleibt die Form scharf.
        spoiled = [{**entries[0], "verdict": "vielleicht"}, *entries[1:]]
        refused = check_verdicts(spoiled, findings=findings, round_rules=False).rejected
        assert [entry["verdict"] for entry, _problems in refused] == ["vielleicht"], path.name


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


KNOWN = ("resize_hole", "finding.action:install", "command:edit.auto_split", "drill_hole")


def test_a_row_with_an_addition_or_only_its_tail_names_no_row() -> None:
    """„resize_hole im Bild“ und „install“ trafen keine Zelle, und der Fund fehlte still
    in der Abhakliste (Schlussreview D0, RF-3: FD-67, FD-70, FD-101).

    Ein bloßes Ende prüft nur die ganze Liste: Der Bericht über einen Lauf kennt nur
    dessen Pakete, und dort ist ``place_on_bed`` eine Operation aus D3, kein
    abgeschnittenes ``finding.action:place_on_bed`` (FD-60, FD-61).
    """
    findings = _findings(
        (1, "resize_hole im Bild, Weitere Werte", "19", "offen RM-741"),
        (2, "`drill_hole`, install und auto_split", "1", "offen RM-737"),
        (3, "`resize_hole`", "19", "offen RM-741"),
        (4, "`drill_hole` und die Sprachflächen", "9", "offen RM-737"),
    )
    assert check_finding_rows(findings.values(), KNOWN, complete=False) == [
        "FD-1: „resize_hole im Bild“ ist keine Zeile, gemeint: resize_hole"
    ]
    assert check_finding_rows(findings.values(), KNOWN) == [
        "FD-1: „resize_hole im Bild“ ist keine Zeile, gemeint: resize_hole",
        "FD-1: offen, trifft aber keine Zeile — Kennung ausschreiben oder „keine Zeile: …“",
        "FD-2: „auto_split“ ist keine Zeile, gemeint: command:edit.auto_split",
        "FD-2: „install“ ist keine Zeile, gemeint: finding.action:install",
    ]
    fixed = _findings((60, "`place_on_bed`, `resize_hole`", "9", "behoben `f50704312`"))
    run_rows = ("resize_hole", "finding.action:place_on_bed")
    assert check_finding_rows(fixed.values(), run_rows, complete=False) == []


NAVIGATION = "Ansicht/Navigation/Wie in Bambu Studio, Orca und PrusaSlicer — links dreht"


def test_a_row_with_a_comma_stays_one_row_in_backticks() -> None:
    """Fensterbefehle heißen nach Menütiteln mit Komma und „und“ — die Kennung oben steht
    so in der Menüleiste. In Backticks bleibt sie eine Zeile; ohne zerfällt sie an den
    Trennzeichen, und die Prüfung sagt es (Schlussreview D0, RF-3)."""
    quoted, bare = _findings(
        (1, f"`{NAVIGATION}`, `drill_hole`", "19", "offen RM-737"),
        (2, f"{NAVIGATION}, drill_hole", "19", "offen RM-737"),
    ).values()
    assert quoted.rows == {NAVIGATION, "drill_hole"}
    assert NAVIGATION not in bare.rows and "drill_hole" in bare.rows
    assert check_finding_rows([quoted, bare], (*KNOWN, NAVIGATION)) == [
        f"FD-2: „{NAVIGATION}“ zerfällt ohne Backticks"
    ]


def test_an_open_finding_names_a_row_or_says_it_has_none() -> None:
    """Mit der ganzen Funktionsliste hält jeder offene Fund eine Zeile oder sagt
    ausdrücklich, dass er keine betrifft; ein behobener darf eine Zeile tragen, die sein
    Fix entfernt hat (FD-24). Der Bericht über einen Lauf kennt nicht alle Zeilen und
    prüft das nicht."""
    findings = _findings(
        (1, "Prüfanschlüsse des Prüfstands", "19", "offen RM-737"),
        (2, "keine Zeile: Prüfanschlüsse des Prüfstands", "19", "offen RM-737"),
        (3, "`meldung:_online_completed`", "19", "behoben `544640f2a`"),
        (4, "`drill_hole`, Statusleiste", "9", "offen RM-737"),
    )
    assert findings["FD-2"].rows == frozenset()
    assert check_finding_rows(findings.values(), KNOWN) == [
        "FD-1: offen, trifft aber keine Zeile — Kennung ausschreiben oder „keine Zeile: …“"
    ]
    assert check_finding_rows(findings.values(), KNOWN, complete=False) == []


def test_every_quoted_row_of_an_open_finding_is_known() -> None:
    """Ein Tippfehler neben einer bekannten Kennung blieb still: Der Fund traf über die
    bekannte eine Zeile, und die Zelle der gemeinten blieb ohne ihn (Review 2, RF-17,
    die drei Sondenfunde). Freier Text ohne Backticks darf daneben stehen; ein
    behobener Fund darf eine Zeile nennen, die es nicht mehr gibt."""
    findings = _findings(
        (1, "`drill_hole`, `resize_hol`", "19", "offen RM-737"),
        (2, "`drill_hole`, `finding.action:instal`", "1", "offen RM-737"),
        (3, "`dialog:body_choice_dialg`, `dialog:seal_path_dialog`", "1", "offen RM-737"),
        (4, "`drill_hole`, Statusleiste", "9", "offen RM-737"),
        (5, "`drill_hole`, `meldung:_online_completed`", "9", "behoben `544640f2a`"),
    )
    known = (*KNOWN, "dialog:seal_path_dialog")
    assert check_finding_rows(findings.values(), known) == [
        "FD-1: „resize_hol“ ist keine bekannte Zeile",
        "FD-2: „finding.action:instal“ ist keine bekannte Zeile",
        "FD-3: „dialog:body_choice_dialg“ ist keine bekannte Zeile",
    ]


def test_every_finding_names_the_rows_it_means() -> None:
    """Der Wächter über die eingecheckte Funddatei, gegen die ganze Funktionsliste samt
    den Fensterbefehlen der Abhaklisten (die Menüleiste entsteht erst am Fenster)."""
    found, problems = function_report.read_findings(STATE / "funde.md")
    assert problems == [] and len(found) > 150
    listed = {row for checklist in read_checklists().values() for row in checklist.rows}
    known = {row.id for row in function_rows(with_specs=False)} | listed
    assert len(known) > 300 and any("/" in row for row in listed)
    assert check_finding_rows(found.values(), known) == []


# --- Der Stand der Funde vor einer Urteilsrunde (FD-153) ---------------------------

PLANTED = """### FD-1 Ein Fund, dessen Fix im Laufkopf liegt

- Art: Fehler
- Schwere: mittel
- Funktion: `drill_hole`
- Prüfpunkt: 9
- Beleg: gepflanzt.
- Ursache: Ein Satz.
- Vorschlag: Ein Satz.
- Wirkung beim Kunden: Ein Satz.
- Stand: offen RM-737; Fix `{commit}`, integriert{rest}
"""


def _head() -> str:
    """Der Kopf dieses Baums — als Laufkopf und als Fix, der in ihm liegt."""
    finished = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=function_report.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    head = finished.stdout.strip()
    if finished.returncode != 0 or not head:
        pytest.skip("kein Git-Baum: der Laufkopf lässt sich nicht lesen")
    return head


def test_the_report_refuses_an_open_finding_whose_fix_lies_in_the_run_head(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """FD-153: Beim gemeinsamen Lauf standen sechs Funde offen, obwohl ihre Fixe Vorfahren
    des Laufkopfs waren, und die Prüfer lasen *gut nach Fix* aus dem Text statt aus der
    Datei. ``report`` verlangt deshalb vor jeder Abhakliste, dass ein offener Fund keinen
    Commit nennt, der im Laufkopf liegt — es sei denn, sein Stand sagt mit „Rest:“, was
    trotzdem offen bleibt. Der Kopf dieses Baums ist sein eigener Vorfahr; so trägt der
    Fall auch in einem flachen Klon."""
    head = _head()
    protocol = sample_protocol()
    protocol["version"]["commit"] = head
    case = tmp_path / "lauf" / "cases" / "1"
    case.mkdir(parents=True)
    (case / "function.json").write_text(json.dumps(protocol, ensure_ascii=False), "utf-8")
    findings = tmp_path / "funde.md"

    def report(rest: str) -> int:
        findings.write_text(PLANTED.format(commit=head[:9], rest=rest), encoding="utf-8")
        return function_report.write(
            tmp_path / "lauf",
            state=tmp_path / "state",
            findings=findings,
            date="2026-10-16",
            context=sample_context(),
            solutions={},
            common_goals={},
        )

    assert report("") == 1
    said = capsys.readouterr().out
    assert f"funde.md: FD-1: steht offen, obwohl `{head[:9]}` im Laufkopf" in said, said
    assert report("; Rest: die Lage am echten Fenster") == 0, capsys.readouterr().out


def test_an_open_stand_is_stale_only_with_a_fix_inside_the_head_and_no_rest() -> None:
    """Die Regel ohne Git: Ein Commit außerhalb des Kopfs, ein behobener Fund und ein
    benannter Rest sind kein Befund; ein unbekannter Commit oder ein Lauf ohne Kopf
    machen den Stand nicht prüfbar, statt still durchzugehen."""
    inside, outside, head = "1111111aa", "2222222bb", "3333333cc"

    def ancestry(commit: str, of: str) -> bool | None:
        assert of == head
        return {inside: True, outside: False}.get(commit)

    found = _findings(
        (1, "`drill_hole`", "9", f"offen RM-737; Fix `{inside}`"),
        (2, "`drill_hole`", "9", f"offen RM-737; Fix `{outside}` auf einem Zweig"),
        (3, "`drill_hole`", "9", f"behoben `{inside}`"),
        (4, "`drill_hole`", "9", f"offen RM-737; Teil `{inside}`; Rest: am Fenster"),
        (5, "`drill_hole`", "9", "offen RM-737; in Arbeit"),
        (6, "`drill_hole`", "9", "offen RM-737; Fix `4444444dd`"),
    ).values()
    stale = function_verdict_rules.stale_findings
    problems = stale(found, [head, "unbekannt"], ancestry)
    assert [problem.split(":")[0] for problem in problems] == ["FD-1", "FD-6"], problems
    assert "im Laufkopf" in problems[0] and "nicht prüfbar" in problems[1]
    alone = [f for f in found if f.key == "FD-1"]
    assert stale(alone, ["None"], ancestry) == [
        "FD-1: nennt `1111111aa` in einem offenen Stand, doch der Lauf trägt keinen Kopf"
        " — der Stand ist nicht prüfbar (FD-153)"
    ]
