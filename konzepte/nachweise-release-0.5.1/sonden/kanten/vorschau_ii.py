"""RM-279 (ii): Zeigt die Vorschau des Dialogs den Befund „nicht verrundet“, bevor der Kunde übernimmt?

Aufruf aus der Wurzel eines Arbeitsbaums: python vorschau_ii.py. Offscreen,
umgebogene Nutzerordner, derselbe Weg wie das Band des Dialogs
(``Session._preview_outcome`` mit ``detect_features=False``).
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = tempfile.mkdtemp(prefix="kanten-vorschau-ii-")
for name in ("APPDATA", "LOCALAPPDATA"):
    os.environ[name] = home
sys.path.insert(0, os.getcwd())
import trimesh  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

application = QApplication([])
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.core.scene.history import OperationDraft  # noqa: E402
from app.ui.session import Session  # noqa: E402

wall_path = Path(home) / "wand.stl"
wall = trimesh.creation.box(extents=(40.0, 3.0, 20.0))
wall.apply_translation((0.0, 0.0, 10.0))
wall.export(wall_path)
FILES = Path(r"F:\3D Dateien")

for label, path, params in (
    ("Wand 40 x 3 x 20 (Netz), oben R 2", wall_path, {"radius": 2.0, "edges": "top"}),
    ("pegboard-goot (exakt), senkrecht R 1", FILES / "pegboard-goot-ceramic-screwdrivers-v3.step", {"radius": 1.0}),
    ("pegboard-goot (Netz, 3MF), senkrecht R 1", FILES / "pegboard-goot-ceramic-screwdrivers-v3.3mf", {"radius": 1.0}),
):
    session = Session()
    session.import_model(path, unit="mm", raise_on_error=True)
    session.evaluate_now()
    object_id, entry = next(iter(session.last_result.scene.objects.items()))
    draft = OperationDraft(op="fillet_edges", params=params, inputs=(object_id,))
    scene, difference, reason = session._preview_outcome([draft], detect_features=False)
    if difference is None:
        print(f"{label}: keine Vorschau — {reason}")
        continue
    change = difference.entries[object_id]
    print(
        f"{label}: Art {entry.kind}, entfernt {change.removed_volume:.3f} mm³, Befunde "
        f"{[(f.code, dict(f.values), f.location is not None, [a.id for a in f.suggestions]) for f in difference.findings]}"
    )
    for finding in difference.findings:
        if finding.code == "edges.too_narrow":
            print("   Satz:", str(finding.message))
