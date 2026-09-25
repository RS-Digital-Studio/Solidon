# Wandzeit je Hauptfaden-Methode je Bohrungsklick (Hüllen, einschließlich verschachtelter).
import statistics as _statistics
import threading as _threading
import time as _time
from collections import defaultdict as _defaultdict

import app.ui.main_window as _mw
import app.ui.panels as _panels
import app.ui.placement_flow as _pf
import app.ui.viewport as _vp

_totals = _defaultdict(float)
_counts = _defaultdict(int)
_main = _threading.main_thread()


def _wrap(owner, name, label):
    original = getattr(owner, name)

    def wrapped(*args, **kwargs):
        if _threading.current_thread() is not _main:
            return original(*args, **kwargs)
        start = _time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            _totals[label] += (_time.perf_counter() - start) * 1000.0
            _counts[label] += 1

    wrapped.__wrapped__ = original
    setattr(owner, name, wrapped)


for _owner, _name in [
    (_mw.MainWindow, "_on_features_selected"),
    (_mw.MainWindow, "_show_feature_fields"),
    (_mw.MainWindow, "_place_from_feature_panel"),
    (_mw.MainWindow, "end_quiet_placement"),
    (_mw.MainWindow, "_lay_out_now"),
    (_pf.PlacementFlow, "__init__"),
    (_pf.PlacementFlow, "start"),
    (_pf.PlacementFlow, "dispose"),
    (_pf.PlacementFlow, "redraw"),
    (_pf.PlacementFlow, "_settle"),
    (_pf.PlacementFlow, "_draw_now"),
    (_pf.PlacementFlow, "set_measure_fields"),
    (_panels.FeaturePanel, "show_feature"),
    (_panels.FeaturePanel, "set_measuring"),
    (_panels.FeaturePanel, "measure_fields"),
    (_vp.Viewport, "_draw"),
    (_vp.Viewport, "_redraw_features"),
    (_vp.Viewport, "select_feature_refs"),
    (_vp.Viewport, "set_gizmo"),
    (_vp.Viewport, "set_placement_pointer"),
    (_vp.Viewport, "_layout_feature_labels"),
]:
    _wrap(_owner, _name, f"{_owner.__name__}.{_name}")
_renderer = window.viewport.renderer
for _name in ("_draw", "render_now", "render"):
    if hasattr(type(_renderer), _name):
        _wrap(type(_renderer), _name, f"Renderer.{_name}")

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
        _sync = (_time.perf_counter() - _start) * 1000.0
        while _time.perf_counter() - _start < 30.0:
            application.processEvents()
            _flow = window._quiet_placement
            if _flow is not None and _flow._surface is not None and not _flow._surface_busy:
                break
            _time.sleep(0.001)
        _took = (_time.perf_counter() - _start) * 1000.0
        if _round >= 1:
            _times.append(_took)
        log(f"KLICK {_hole}: synchron {_sync:6.1f} ms, Fläche nach {_took:6.1f} ms")
_clicks = len(_times)
log("ERGEBNIS Median", round(_statistics.median(_times), 1), "ms über", _clicks, "Klicks")
for _label, _total in sorted(_totals.items(), key=lambda item: -item[1]):
    log(f"  {_total / _clicks:7.1f} ms  {_counts[_label] / _clicks:5.1f}x  {_label}")
