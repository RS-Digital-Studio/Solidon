"""RM-279: Das Feld „Runde Ränder nach ihrer Lage“ am gebauten Dialog, offscreen.

Aufruf aus der Wurzel des Arbeitsbaums: python dialog.py. Je Operation:
Editorart, Rückseite, Vorgabe, aktiv je Gruppe, und ein alter Schritt.
"""

import os
import sys
import tempfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = tempfile.mkdtemp(prefix="kanten-dialog-")
for name in ("APPDATA", "LOCALAPPDATA"):
    os.environ[name] = home
sys.path.insert(0, os.getcwd())
from PySide6.QtWidgets import QApplication  # noqa: E402

application = QApplication([])
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.core.registry import REGISTRY  # noqa: E402
from app.ui.op_dialog import OperationDialog  # noqa: E402

for name in ("fillet_edges", "chamfer_edges", "bead_edges"):
    dialog = OperationDialog(REGISTRY.get(name), {"obj_1": "Quader"}, None)
    box = dialog._editors["rings_by_plane"]
    label = dialog._rows["rings_by_plane"].labelForField(box)
    choice = dialog._editors["edges"]
    states = {}
    for group in ("vertical", "horizontal", "top", "bottom", "all", "named"):
        choice.setCurrentIndex(choice.findData(group))
        application.processEvents()
        states[group] = box.isEnabled()
    print(
        f"{name}: {type(box).__name__}, Beschriftung „{label.text() if label else '?'}“, "
        f"Rückseite {dialog._rows['rings_by_plane'] is dialog._advanced_form}, "
        f"Vorgabe {dialog.values()['rings_by_plane']}, aktiv {states}, Tooltip „{box.toolTip()[:70]}…“"
    )
    dialog.deleteLater()
    stored = OperationDialog(
        REGISTRY.get(name), {"obj_1": "Quader"}, None,
        values={"edges": "horizontal", "rings_by_plane": False},
    )
    print(f"  alter Schritt: Haken {stored._editors['rings_by_plane'].isChecked()}, "
          f"übernommen {stored.values()['rings_by_plane']}")
    stored.deleteLater()
