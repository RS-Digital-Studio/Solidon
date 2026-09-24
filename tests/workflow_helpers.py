"""Genaue Job- und Schrittblöcke für die Verträge unserer CI-Dateien.

Kein allgemeiner YAML-Parser: Die eingecheckten Workflows verwenden zwei
Leerzeichen je Ebene. Mehrdeutige oder fehlende Blöcke sind ein Fehler.
"""

from __future__ import annotations

import re
import textwrap


def job_block(workflow: str, name: str) -> str:
    """Liest genau den benannten Job, ohne spätere Nachbarjobs mitzunehmen."""
    jobs = workflow.split("\njobs:\n", 1)[1]
    matches = re.findall(rf"(?ms)^  {re.escape(name)}:\n.*?(?=^  [a-zA-Z0-9_-]+:\n|\Z)", jobs)
    assert len(matches) == 1, f"Workflow-Job fehlt oder ist doppelt: {name}"
    return matches[0]


def step_block(job: str, name: str) -> str:
    """Liest einen benannten Schritt bis zum nächsten Schritt, gleich womit er beginnt."""
    matches = re.findall(rf"(?ms)^      - name: {re.escape(name)}\n.*?(?=^      - |\Z)", job)
    assert len(matches) == 1, f"Workflow-Schritt fehlt oder ist doppelt: {name}"
    return matches[0]


def step_script(step: str) -> str:
    """Liefert den eingerückten Shellblock ohne nachfolgende Schrittattribute."""
    match = re.search(r"(?m)^        run: \|\n((?: {10}.*\n|\n)+)", step + "\n")
    assert match is not None, "Workflow-Schritt enthält keinen Shellblock"
    return textwrap.dedent(match.group(1))
