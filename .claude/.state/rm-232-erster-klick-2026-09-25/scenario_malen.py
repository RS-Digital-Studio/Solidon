# Malt Qt das Auswahlfenster mit einer Geometrie, die noch nicht zum Inhalt passt?
# Läuft über slot_probe.py (echtes Fenster). Zählt je Klick die Malereignisse des
# Rollinhalts und schreibt bei jedem die Höhen auf — ohne Bildschirmaufnahme,
# die selbst 50 ms kostet und die Ereignisfolge verschiebt.
import time as _time

from PySide6.QtCore import QEvent as _QEvent
from PySide6.QtCore import QObject as _QObject
from PySide6.QtWidgets import QScrollArea as _QScrollArea

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)
_scroller = window.feature_dock.widget().findChild(_QScrollArea)
_inside = _scroller.widget()
_footer = window.feature_panel.footer()
_start = [0.0]
_rows = []


class _Watcher(_QObject):
    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() == _QEvent.Type.Paint:
            heading = window.feature_panel._built[0].text()[:24] if window.feature_panel._built else ""
            _rows.append(
                (
                    (_time.perf_counter() - _start[0]) * 1000.0,
                    type(watched).__name__,
                    _inside.height(),
                    _inside.minimumSizeHint().height(),
                    _scroller.viewport().height(),
                    _footer.height(),
                    _footer.sizeHint().height(),
                    heading,
                    " <- ".join(
                        f"{frame.name}:{frame.lineno}"
                        for frame in reversed(__import__("traceback").extract_stack(limit=14)[:-1])
                    ),
                )
            )
        return False


_watcher = _Watcher()
for _widget in (_inside, window.feature_panel, _footer):
    _widget.installEventFilter(_watcher)
for _round, _hole in enumerate([*_holes, *_holes]):
    _rows.clear()
    _start[0] = _time.perf_counter()
    window.object_tree.select_feature(_object_id, _hole)
    _end = _time.perf_counter() + 1.2
    while _time.perf_counter() < _end:
        application.processEvents()
        _time.sleep(0.001)
    log(f"KLICK {_round} {_hole}: {len(_rows)} Malereignisse")
    for _at, _name, _height, _least, _sight, _foot, _foot_hint, _heading, _stack in _rows:
        broken = "  KAPUTT" if _height < _least or _foot != _foot_hint else ""
        log(
            f"  {_at:6.0f} ms {_name:14s} Inhalt={_height} min={_least} Sicht={_sight}"
            f" Fuß={_foot}/{_foot_hint} Kopf='{_heading}'{broken}"
        )
        if broken:
            log(f"      {_stack}")
    idle(0.6)
for _widget in (_inside, window.feature_panel, _footer):
    _widget.removeEventFilter(_watcher)
