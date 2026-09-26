# Ereignisse des Hauptfadens je Bohrungsklick: welche Art, an wen, wie lange (über notify-Ersatz nicht
# möglich, darum über einen Filter, der die Zeit bis zum nächsten Ereignis misst).
import statistics as _statistics
import time as _time
from collections import defaultdict as _defaultdict

from PySide6.QtCore import QObject as _QObject

_log = []
_t0 = [0.0]
_last = [None]


class _Watch(_QObject):
    def eventFilter(self, receiver, event):  # noqa: N802
        now = (_time.perf_counter() - _t0[0]) * 1000.0
        if _last[0] is not None:
            at, kind, name = _last[0]
            _log.append((at, now - at, kind, name))
        try:
            name = type(receiver).__name__ + ":" + (receiver.objectName() or "")
        except Exception:  # noqa: BLE001
            name = "?"
        _last[0] = (now, int(event.type()), name)
        return False


_watch = _Watch()
_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
_sums = _defaultdict(list)
for _round in range(5):
    for _hole in _holes:
        idle(0.4)
        _log.clear()
        _last[0] = None
        _t0[0] = _time.perf_counter()
        application.installEventFilter(_watch)
        window.object_tree.select_feature(_object_id, _hole)
        _sync = (_time.perf_counter() - _t0[0]) * 1000.0
        while _time.perf_counter() - _t0[0] < 5.0:
            application.processEvents()
            _flow = window._quiet_placement
            if _flow is not None and _flow._surface is not None and not _flow._surface_busy:
                break
            _time.sleep(0.001)
        _done = (_time.perf_counter() - _t0[0]) * 1000.0
        application.removeEventFilter(_watch)
        if _round == 4:
            log(f"--- Klick {_hole}: synchron {_sync:.1f}, Fläche {_done:.1f}")
            for _at, _took, _kind, _name in _log:
                if _took >= 0.7:
                    log(f"  {_at:7.1f} +{_took:6.1f} ms  Art {_kind:4d}  {_name}")
