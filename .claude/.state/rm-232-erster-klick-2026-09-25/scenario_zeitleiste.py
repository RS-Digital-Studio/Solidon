# Zeitleiste je Bohrungsklick: synchroner Teil, Arbeiter (seat_of, prepare_tool), _settle, Bilder.
import statistics as _statistics
import threading as _threading
import time as _time
from collections import defaultdict as _defaultdict

import app.core.scene.placement as _placement
import app.ui.placement_flow as _pf

_events = []
_t0 = [0.0]


def _mark(label):
    _events.append(((_time.perf_counter() - _t0[0]) * 1000.0, label, _threading.current_thread().name))


def _wrap(owner, name, label):
    original = getattr(owner, name)

    def wrapped(*args, **kwargs):
        _mark(label + " an")
        try:
            return original(*args, **kwargs)
        finally:
            _mark(label + " aus")

    setattr(owner, name, wrapped)


_wrap(_placement, "seat_of", "seat_of")
_wrap(_placement, "prepare_tool", "prepare_tool")
_wrap(_placement, "at_point", "at_point")
_wrap(_pf.PlacementFlow, "_settle", "_settle")
_wrap(type(window.viewport.renderer), "_draw", "Bild")
_wrap(_pf.PlacementFlow, "start", "start")

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
_lines = _defaultdict(list)
for _round in range(5):
    for _hole in _holes:
        idle(0.4)
        _events.clear()
        _t0[0] = _time.perf_counter()
        window.object_tree.select_feature(_object_id, _hole)
        _mark("synchron fertig")
        _deadline = _time.perf_counter() + 5.0
        while _time.perf_counter() < _deadline:
            application.processEvents()
            _flow = window._quiet_placement
            if _flow is not None and _flow._surface is not None and not _flow._surface_busy:
                break
            _time.sleep(0.001)
        _mark("Fläche da")
        _tail = _time.perf_counter()
        while _time.perf_counter() - _tail < 0.25:
            application.processEvents()
            _time.sleep(0.001)
        if _round >= 1:
            _rest = max((at for at, label, _thread in _events if label == "Bild aus"), default=0.0)
            _lines["RUHE (letztes Bild fertig)"].append(_rest)
            for _at, _label, _thread in _events:
                _lines[_label + (" (Arbeiter)" if _thread != "MainThread" else "")].append(_at)
        if _round == 4:
            log(f"--- Klick {_hole}")
            for _at, _label, _thread in _events:
                log(f"  {_at:7.1f} ms  {_label}  [{_thread}]")
log("Mediane über die Klicks 3 bis 10 (erstes Auftreten je Marke):")
for _label, _values in sorted(_lines.items(), key=lambda item: _statistics.median(item[1])):
    log(f"  {_statistics.median(_values):7.1f} ms  {_label}  ({len(_values)}x)")
