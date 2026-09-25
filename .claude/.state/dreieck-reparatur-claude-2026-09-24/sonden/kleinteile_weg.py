"""Sonde: „Kleine Teile entfernen“ am Import-Befund — was bleibt im Bericht stehen?"""

from __future__ import annotations

import os
import sys
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
for name in sys.argv[1:]:
    path = Path(name)
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    payload = path.read_bytes()
    document.sources["src_1"] = Source(id="src_1", kind="import", path="sources/x.stl", sha256="")
    project.sources["src_1"] = payload
    plan = import_plan("src_1", path.name, payload, "mm", first_model=True)
    history = History(document)
    history.apply(plan.title, [plan.draft])
    history.apply(
        _("Reparieren"),
        [OperationDraft(op="repair", inputs=("obj_1",), params={"small_components": True})],
    )
    result = evaluate(document, PROFILE, sources=ProjectSources(project))
    print(f"== {path.name}: Teile nach Entfernen = {result.scene.objects['obj_1'].mesh.component_count}")
    for finding in result.scene.report.findings:
        labels = ", ".join(
            str(a.label)
            for a in actions_for_document(
                finding, document, stopped_at=result.stopped_at, live_objects=result.scene.objects
            )
        )
        print(f"   [{finding.severity}] {finding.code}: {finding.message}  Knöpfe: {labels or '—'}")
