# Welche sichtbaren Widgets liegen über der Grafikfläche, malen aber in eine Fläche
# darunter (kein eigenes natives Fenster zwischen ihnen und einem Vorfahren der Fläche)?
from PySide6.QtCore import QRect as _QRect
from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import QApplication as _QApplication
from PySide6.QtWidgets import QWidget as _QWidget

_NATIVE = _Qt.WidgetAttribute.WA_NativeWindow
_canvas = window.viewport.renderer.widget
_above = []
_current = _canvas.parentWidget()
while _current is not None:
    _above.append(_current)
    _current = _current.parentWidget()
_above_ids = {id(w) for w in _above}


def _rect(widget):
    top_left = widget.mapToGlobal(widget.rect().topLeft())
    return _QRect(top_left, widget.size())


def _check(label):
    canvas_rect = _rect(_canvas)
    covered = []
    for widget in window.findChildren(_QWidget):
        if not widget.isVisible() or widget.isWindow() or widget is _canvas or id(widget) in _above_ids:
            continue
        if _canvas.isAncestorOf(widget):
            continue
        host = widget
        while host is not None and not host.testAttribute(_NATIVE):
            host = host.parentWidget()
        if host is None or id(host) not in _above_ids:
            continue
        overlap = _rect(widget).intersected(canvas_rect)
        if overlap.isEmpty():
            continue
        chain = []
        current = widget
        while current is not None and id(current) not in _above_ids:
            chain.append(f"{type(current).__name__}:{current.objectName()}")
            current = current.parentWidget()
        covered.append(" < ".join(chain) + f"  [{overlap.width()}x{overlap.height()}]")
    natives = sum(1 for w in _QApplication.allWidgets() if w.testAttribute(_NATIVE))
    log(f"=== {label}: nativ {natives} von {len(_QApplication.allWidgets())}, verdeckt {len(covered)}")
    for line in covered[:40]:
        log("   VERDECKT:", line)


_check("nach dem Öffnen")
shot("verdeckt-1-geoeffnet")
_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)
_check("Objekt gewählt")
window.object_tree.select_feature(_object_id, _holes[0])
idle(1.2)
_check("Bohrung gewählt")
shot("verdeckt-2-bohrung")
window.object_tree.select_feature(_object_id, _holes[1])
idle(1.2)
_check("zweite Bohrung")
_faces = [name for name, f in _entry.features.items() if f.kind in ("plane", "face")][:1]
if _faces:
    window.object_tree.select_feature(_object_id, _faces[0])
    idle(1.2)
    _check("Fläche gewählt")
    shot("verdeckt-3-flaeche")
for _key in ("section", "measure", "transform", "analysis"):
    try:
        window.tools.activate(_key)
        idle(0.8)
        _check(f"Werkzeug {_key}")
        shot(f"verdeckt-4-{_key}")
        window.tools.activate(_key)
        idle(0.4)
    except Exception as _problem:  # noqa: BLE001
        log("Werkzeug", _key, "nicht bedienbar:", _problem)
# Skizzenmodus: frei (Ebenenwahl), dann auf einer Fläche.
window.action_sketch_free()
idle(1.0)
_check("Skizze frei")
shot("verdeckt-5-skizze-frei")
window.finish_sketch(keep=False)
idle(0.8)
if _faces:
    window.object_tree.select_feature(_object_id, _faces[0])
    idle(0.8)
    window._on_sketch_on_face(_faces[0])
    idle(1.2)
    _check("Skizze auf Fläche")
    shot("verdeckt-6-skizze-flaeche")
    window.finish_sketch(keep=False)
    idle(0.8)
_check("nach der Skizze")
