# Wann wechselt die Knopfzeile des Auswahlfensters beim ersten Merkmalklick ihre Höhe — und wer ruft?
# Läuft über slot_probe.py (echtes Fenster).
import time as _time
import traceback as _traceback

from app.ui import panels as _panels

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)

_start = [0.0]
_footer = window.feature_panel.footer()
_original = _panels._set_shown


def _traced(widget, shown):
    before = widget.isHidden()
    result = _original(widget, shown)
    if widget.parentWidget() is _footer and before == shown:
        stack = " <- ".join(
            f"{frame.name}:{frame.lineno}" for frame in reversed(_traceback.extract_stack(limit=9)[:-1])
        )
        name = getattr(widget, "text", lambda: type(widget).__name__)()
        log(f"  {(_time.perf_counter() - _start[0]) * 1000:6.0f} ms Fuß '{name}' -> {shown}: {stack}")
    return result


_panels._set_shown = _traced
for _hole in _holes:
    _start[0] = _time.perf_counter()
    log(f"KLICK {_hole}")
    window.object_tree.select_feature(_object_id, _hole)
    _end = _time.perf_counter() + 1.5
    while _time.perf_counter() < _end:
        application.processEvents()
        _time.sleep(0.002)
    idle(0.6)
_panels._set_shown = _original
