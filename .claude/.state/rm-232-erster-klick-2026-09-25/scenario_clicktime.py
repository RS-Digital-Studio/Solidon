# Bohrungen abwechselnd wählen: Zeit bis die Maßgruppe ihre Fläche hat.
import statistics as _statistics
import time as _time

_ids = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _ids.id
_holes = [name for name, f in _ids.features.items() if f.kind == "hole"][:2]
log("Bohrungen:", _holes)
_times = []
for _round in range(4):
    for _hole in _holes:
        pass
        idle(0.3)
        _start = _time.perf_counter()
        window.object_tree.select_feature(_object_id, _hole)
        while _time.perf_counter() - _start < 30.0:
            application.processEvents()
            _flow = window._quiet_placement
            if _flow is not None and _flow._surface is not None and not _flow._surface_busy:
                break
            _time.sleep(0.002)
        _took = (_time.perf_counter() - _start) * 1000.0
        _times.append(_took)
        log(f"KLICK {_hole}: Fläche nach {_took:7.1f} ms")
        idle(0.6)
log("ERGEBNIS erster", round(_times[0], 1), "ms, danach Median", round(_statistics.median(_times[1:]), 1), "ms")
