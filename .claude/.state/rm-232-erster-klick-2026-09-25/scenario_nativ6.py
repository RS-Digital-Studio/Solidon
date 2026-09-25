# Welche Widgets sind nach einem Bohrungsklick nativ, wo hängen sie, sind sie sichtbar?
from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import QApplication as _QApplication

_NATIVE = _Qt.WidgetAttribute.WA_NativeWindow
_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)
_before = {id(w) for w in _QApplication.allWidgets() if w.testAttribute(_NATIVE)}
window.object_tree.select_feature(_object_id, _holes[0])
idle(1.2)
for _w in _QApplication.allWidgets():
    if _w.testAttribute(_NATIVE) and id(_w) not in _before:
        _chain = []
        _c = _w
        while _c is not None and type(_c).__name__ != "Viewport":
            _chain.append(f"{type(_c).__name__}:{_c.objectName()}")
            _c = _c.parentWidget()
        log("neu nativ:", " < ".join(_chain), "sichtbar" if _w.isVisible() else "verborgen", _w.geometry().getRect())
