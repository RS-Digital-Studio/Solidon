# Welche Widgets sind nativ (eigenes Windows-Fenster)? Und was kostet setVisible dort?
# Läuft über slot_probe.py (echtes Fenster).
import time as _time

from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import QApplication as _QApplication
from PySide6.QtWidgets import QWidget as _QWidget

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)
window.object_tree.select_feature(_object_id, _holes[0])
idle(1.0)
log(
    "AA_DontCreateNativeWidgetSiblings",
    _QApplication.testAttribute(_Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings),
    "AA_NativeWindows",
    _QApplication.testAttribute(_Qt.ApplicationAttribute.AA_NativeWindows),
)
_all = window.findChildren(_QWidget)
_native = [w for w in _all if w.testAttribute(_Qt.WidgetAttribute.WA_NativeWindow)]
log(f"Widgets {len(_all)}, nativ {len(_native)}")
for _w in _native[:60]:
    log("  nativ:", type(_w).__name__, _w.objectName(), "sichtbar" if _w.isVisible() else "verborgen")
_panel_children = window.feature_panel.findChildren(_QWidget)
log(
    "im Merkmalfenster nativ:",
    sum(w.testAttribute(_Qt.WidgetAttribute.WA_NativeWindow) for w in _panel_children),
    "von",
    len(_panel_children),
)
# Was kostet ein Sichtbarkeitswechsel einer Zeile im Merkmalfenster?
_rows = [w for w in window.feature_panel._built if w.isVisible()]
if _rows:
    _row = _rows[len(_rows) // 2]
    _t = _time.perf_counter()
    for _ in range(10):
        _row.setVisible(False)
        _row.setVisible(True)
    log(f"20 × setVisible an '{type(_row).__name__}': {(_time.perf_counter() - _t) * 1000 / 20:.2f} ms je Aufruf")
