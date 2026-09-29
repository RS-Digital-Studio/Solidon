"""RM-279: Zeigt die Vorschau des Dialogs die Mündungen, bevor der Kunde übernimmt?

Aufruf aus der Wurzel eines Arbeitsbaums: python vorschau.py. Offscreen, mit
umgebogenen Nutzerordnern. Derselbe Weg wie das Band des Dialogs
(``Session._preview_outcome`` mit ``detect_features=False``): Quader mit
Querbohrung als STL (Netz) und das Pegboard-STEP gs-100 (exakt), *Verrunden*
mit der Vorgabe „senkrecht“. Gezählt wird, welcher Teil des entfernten
Volumens in der Vorschau an den Mündungen liegt.
"""

import math
import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = tempfile.mkdtemp(prefix="kanten-vorschau-")
for name in ("APPDATA", "LOCALAPPDATA"):
    os.environ[name] = home
sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

application = QApplication([])
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.scene.history import OperationDraft  # noqa: E402
from app.ui.session import Session  # noqa: E402

box = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
box.apply_translation((0.0, 0.0, 10.0))
bore = trimesh.creation.cylinder(radius=3.0, height=90.0, sections=48)
bore.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1, 0, 0)))
bore.apply_translation((0.0, 0.0, 10.0))
body = boolean("difference", [MeshData(box), MeshData(bore)]).mesh
stl = Path(home) / "querbohrung.stl"
body.raw.export(stl)

for label, path, params in (
    ("Quader mit Querbohrung (Netz)", stl, {"radius": 2.0}),
    ("pegboard-gs-100-v2 (exakt)", Path(r"F:\3D Dateien\pegboard-gs-100-v2.step"), {"radius": 0.5}),
):
    for rings_by_plane in (True, False):
        session = Session()
        session.import_model(path, unit="mm", raise_on_error=True)
        session.evaluate_now()
        object_id, entry = next(iter(session.last_result.scene.objects.items()))
        draft = OperationDraft(
            op="fillet_edges",
            params={**params, "rings_by_plane": rings_by_plane},
            inputs=(object_id,),
        )
        scene, difference, reason = session._preview_outcome([draft], detect_features=False)
        if difference is None:
            print(f"{label} {'neu' if rings_by_plane else 'bisher'}: keine Vorschau — {reason}")
            continue
        change = difference.entries[object_id]
        removed = change.removed
        print(f"{label} {'neu' if rings_by_plane else 'bisher'}: Art {entry.kind}, "
              f"entfernt {change.removed_volume:.3f} mm³, Teile im Abtrag "
              f"{removed.component_count if removed is not None else 0}, "
              f"Befunde {sorted({f.code for f in difference.findings})}")
