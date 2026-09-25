# Wo entstehen je Bohrungsklick neue native Widgets, und warum ist das Merkmalfenster nativ?
# Läuft über slot_probe.py (echtes Fenster).
import time as _time

from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import QApplication as _QApplication


def _natives():
    return {
        id(w): w
        for w in _QApplication.allWidgets()
        if w.testAttribute(_Qt.WidgetAttribute.WA_NativeWindow)
    }


def _chain(widget, stop):
    names = []
    current = widget
    while current is not None and current is not stop:
        names.append(f"{type(current).__name__}:{current.objectName()}")
        current = current.parentWidget()
    return " < ".join(names)


_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)
_before = _natives()
log("vor dem ersten Klick nativ:", len(_before))
for _round in range(3):
    for _hole in _holes:
        _seen = _natives()
        _start = _time.perf_counter()
        window.object_tree.select_feature(_object_id, _hole)
        idle(0.8)
        _now = _natives()
        _new = [w for key, w in _now.items() if key not in _seen]
        log(
            f"Klick {_hole}: nativ {len(_now)}, neu {len(_new)}, weg {len([k for k in _seen if k not in _now])}"
        )
        if _round == 0:
            for _w in _new[:40]:
                log("   neu:", _chain(_w, window))
_panel = window.feature_panel
log("Merkmalfenster:", _chain(_panel, window))
for _w in _panel.findChildren(object):
    if hasattr(_w, "testAttribute") and _w.testAttribute(_Qt.WidgetAttribute.WA_NativeWindow):
        log("   nativ im Fenster:", _chain(_w, _panel))
