"""Jeder Job jeder CI-Datei hat dieselbe Zeitgrenze: zwei Stunden (``auslieferung.md``).

Eine eigene, kürzere Grenze brach den Auswahljob zum Push nach main nach einer Stunde ab,
als er über einem Diff, der jeden Test wählt, jede Datendatei einzeln untersuchte
(main-Lauf zu welle5); ohne Grenze gälte GitHubs Vorgabe von sechs Stunden, und der nächste
Push wartete so lange. Zwei Stunden reichen dem längsten Job, dem Paketbau auf dem Intel-Mac.

Ausgenommen sind Jobs, die einen anderen Workflow aufrufen (``uses:`` auf Jobebene):
Dort nimmt GitHub keine Zeitgrenze an, die aufgerufenen Jobs tragen ihre eigene und
werden hier mit ihrer Datei geprüft. Zeitgrenzen einzelner Schritte bleiben frei.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.packaging_helpers import ROOT
from tests.workflow_helpers import job_block, job_names

#: Die Grenze je Job, in Minuten.
LIMIT = 120


def _workflows() -> list[Path]:
    found = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert len(found) >= 5, found
    return found


@pytest.mark.parametrize("workflow", _workflows(), ids=lambda path: path.name)
def test_every_job_has_the_same_two_hours(workflow: Path) -> None:
    """Jede Jobebene trägt ``timeout-minutes: 120`` — nicht fehlend, nicht kürzer."""
    text = workflow.read_text(encoding="utf-8")
    names = job_names(text)
    assert names, f"{workflow.name}: keine Jobs gefunden"
    differing: dict[str, str] = {}
    for name in names:
        block = job_block(text, name)
        if re.search(r"(?m)^    uses: ", block):
            continue
        minutes = re.search(r"(?m)^    timeout-minutes: (\d+)$", block)
        if minutes is None or int(minutes.group(1)) != LIMIT:
            differing[name] = minutes.group(1) if minutes else "fehlt"
    assert not differing, f"{workflow.name}: {differing}"
