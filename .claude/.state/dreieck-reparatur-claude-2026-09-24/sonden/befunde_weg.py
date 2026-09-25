"""Sonde: Welche Befunde und Knöpfe sieht der Kunde beim Import und nach „Reparieren“?

Geht den Weg der Sitzung ohne Fenster: import_plan → History.apply → evaluate,
danach ein Reparaturschritt mit Vorgabe und einer mit aufgelösten Durchdringungen.
Nur lesend gegenüber dem Repository.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402
from app.i18n import _  # noqa: E402
from app.ui.panels import actions_for_document  # noqa: E402

PROFILE = profiles.make_profile("centauri-carbon-2", "petg")


def show(title: str, document, result) -> None:
    print(f"  -- {title}: vollständig={result.complete} angehalten={result.stopped_at}")
    live = result.scene.objects
    for finding in result.scene.report.findings:
        actions = actions_for_document(
            finding, document, stopped_at=result.stopped_at, live_objects=live
        )
        labels = ", ".join(str(action.label) for action in actions) or "—"
        values = {k: v for k, v in finding.values.items() if k != "detail"}
        print(
            f"     [{finding.severity}] {finding.code} op={finding.op_id} obj={finding.object_id}"
        )
        print(f"        Text: {finding.message}")
        print(f"        Knöpfe: {labels}   Werte: {values}")


def run(path: Path) -> None:
    print(f"== {path.name} ({path.stat().st_size} Bytes)")
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    payload = path.read_bytes()
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{path.name}", sha256=""
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", path.name, payload, "mm", first_model=True)
    history = History(document)
    history.apply(plan.title, [plan.draft])
    started = time.perf_counter()
    result = evaluate(document, PROFILE, sources=ProjectSources(project))
    print(f"  Import {time.perf_counter() - started:.2f} s")
    show("nach Import", document, result)
    target = next(iter(result.scene.objects), None)
    if target is None:
        return
    history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=(target,))])
    started = time.perf_counter()
    result = evaluate(document, PROFILE, sources=ProjectSources(project))
    print(f"  Reparieren (Vorgabe) {time.perf_counter() - started:.2f} s")
    show("nach Reparieren (Vorgabe)", document, result)
    history.apply(
        _("Reparieren"),
        [
            OperationDraft(
                op="repair", inputs=(target,), params={"self_intersections": True}
            )
        ],
    )
    started = time.perf_counter()
    result = evaluate(document, PROFILE, sources=ProjectSources(project))
    print(f"  Reparieren (Durchdringungen) {time.perf_counter() - started:.2f} s")
    show("nach zweitem Reparieren mit Durchdringungen", document, result)


if __name__ == "__main__":
    for name in sys.argv[1:]:
        try:
            run(Path(name))
        except Exception as problem:  # Sonde: weiter mit der nächsten Datei
            print(f"  FEHLER {type(problem).__name__}: {problem}")
        print()
