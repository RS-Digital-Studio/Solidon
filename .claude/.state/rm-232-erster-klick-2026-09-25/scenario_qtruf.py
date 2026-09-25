# Was kosten Qt-Widgetaufrufe je Bohrungsklick — innerhalb und außerhalb von PlacementFlow.redraw?
import statistics as _statistics
import threading as _threading
import time as _time
from collections import defaultdict as _defaultdict

from PySide6.QtWidgets import QWidget as _QWidget

import app.ui.placement_flow as _pf

_totals = _defaultdict(float)
_counts = _defaultdict(int)
_main = _threading.main_thread()
_inside = [0]


def _wrap(owner, name, label, marks=False):
    original = getattr(owner, name)

    def wrapped(*args, **kwargs):
        if _threading.current_thread() is not _main:
            return original(*args, **kwargs)
        where = "redraw" if _inside[0] else "sonst"
        if marks:
            _inside[0] += 1
        start = _time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            if marks:
                _inside[0] -= 1
            key = label if marks else f"{where}: {label}"
            _totals[key] += (_time.perf_counter() - start) * 1000.0
            _counts[key] += 1

    setattr(owner, name, wrapped)


_wrap(_pf.PlacementFlow, "redraw", "PlacementFlow.redraw", marks=True)
for _name in ("raise_", "show", "hide", "setVisible", "move", "adjustSize", "setMaximumWidth", "setGeometry", "resize", "update", "repaint", "setEnabled"):
    _wrap(_QWidget, _name, _name)

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
_times = []
for _round in range(5):
    for _hole in _holes:
        idle(0.4)
        if _round == 1 and _hole == _holes[0]:
            _totals.clear()
            _counts.clear()
        _start = _time.perf_counter()
        window.object_tree.select_feature(_object_id, _hole)
        while _time.perf_counter() - _start < 30.0:
            application.processEvents()
            _flow = window._quiet_placement
            if _flow is not None and _flow._surface is not None and not _flow._surface_busy:
                break
            _time.sleep(0.001)
        if _round >= 1:
            _times.append((_time.perf_counter() - _start) * 1000.0)
_clicks = len(_times)
log("ERGEBNIS Median", round(_statistics.median(_times), 1), "ms über", _clicks, "Klicks")
for _label, _total in sorted(_totals.items(), key=lambda item: -item[1])[:30]:
    log(f"  {_total / _clicks:7.1f} ms  {_counts[_label] / _clicks:6.1f}x  {_label}")
