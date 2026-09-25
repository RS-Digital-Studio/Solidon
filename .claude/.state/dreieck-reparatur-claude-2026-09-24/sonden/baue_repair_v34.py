"""Einmalig: tests/data/projects/repair_v34.p3d — ein Reparaturschritt ohne Schlüssel.

So speicherte Format 34 jeden Reparaturschritt, der die Vorgabe nicht
änderte (``History._plan`` hält nur genannte Werte) — auch den aus
„Reparieren und erneut versuchen" (``params={}``). Die Vorgabe war damals
„Überschneidungen auflösen: aus".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from app.core.bootstrap import load_operations  # noqa: E402
from app.core.scene import History, OperationDraft  # noqa: E402
from app.core.scene.migrations import FORMAT_VERSION  # noqa: E402
from app.core.scene.project import new_project, save  # noqa: E402
from app.core.types import Source  # noqa: E402
from app.i18n import _  # noqa: E402

assert FORMAT_VERSION == 34, "vor dem Sprung auf 35 bauen"
load_operations()
project = new_project("centauri-carbon-2", "petg")
document = project.document
document.sources["src_1"] = Source(id="src_1", kind="import", path="sources/broken_selfint.stl", sha256="")
project.sources["src_1"] = Path("tests/data/meshes/broken_selfint.stl").read_bytes()
history = History(document)
history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
history.apply(_("Reparieren"), [OperationDraft(op="repair", inputs=("obj_1",))])
assert "self_intersections" not in document.ops[-1].params
target = Path("tests/data/projects/repair_v34.p3d")
save(project, target)
print(target, target.stat().st_size, document.ops[-1].params)
