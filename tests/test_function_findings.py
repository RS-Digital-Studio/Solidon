"""Funde zwischen Funddatei und Abhakliste (RM-737, Funktionsdurchgang).

Welche Zeilen ein Fund mit „Funktion“ trifft, welchen Fund eine offene Zelle
als Grund nennt, und die Wächter über die eingecheckten Funde und Urteile.
Getrennt von ``tests/test_function_report.py``, das an der Grenze von 2 000
Zeilen steht; geprüft wird dasselbe Werkzeug, ``tools/function_report.py``.
"""

from __future__ import annotations

from tools import function_report
from tools.function_report import STATE, check_verdicts


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
