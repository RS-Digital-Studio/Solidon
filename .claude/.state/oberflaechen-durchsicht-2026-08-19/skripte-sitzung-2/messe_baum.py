"""Der Objektbaum, mit der echten Plattform gemessen.

Offscreen hat Qt auf dieser Maschine keine Schriftfamilie — jede Breite, die
dort gemessen wird, gehört einer anderen Schrift als der gezeigten.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\rober\Documents\Solidon")

from PySide6.QtGui import QFontMetrics  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.ui.app import build_application  # noqa: E402
from app.ui.overlay import LEFT_WIDTH  # noqa: E402
from app.ui.panels import MEASURE_SHARE  # noqa: E402

app, window = build_application([])
window.resize(1900, 1030)
window.show()
for _ in range(80):
    app.processEvents()
window.open_path(Path(r"C:\Users\rober\Documents\Solidon\app\examples\gehaeuse-mit-bausteinen.p3d"))
window.session.wait_for_idle()
for _ in range(120):
    app.processEvents()

tree = window.object_tree.tree
print("LEFT_WIDTH", LEFT_WIDTH, "MEASURE_SHARE", MEASURE_SHARE)
print("Karte", window.object_tree.width(), "viewport", tree.viewport().width())
print("Spalten", tree.columnWidth(0), tree.columnWidth(1))
print("sizeHintForColumn", tree.sizeHintForColumn(0), tree.sizeHintForColumn(1))
print("waagerechte Leiste:", tree.horizontalScrollBar().isVisible())
root = tree.invisibleRootItem()
for i in range(root.childCount()):
    item = root.child(i)
    for col in (0, 1):
        metrics = QFontMetrics(item.font(col))
        need = metrics.horizontalAdvance(item.text(col))
        space = tree.columnWidth(col) - (24 if col == 0 else 8)
        print(
            f"  Spalte {col}: {item.text(col)[:32]!r:36s} braucht {need:4d}, hat {space:4d}"
            f" -> {'GEKÜRZT' if need > space else 'ganz da'}"
        )
for text in ("70 × 50 × 8 mm", "70 × 50 × 8", "70×50×8", "400 × 300 × 250 mm", "400 × 300 × 250"):
    print(f"  {text!r:22s} {QFontMetrics(tree.font()).horizontalAdvance(text):4d} px")
window.close()
