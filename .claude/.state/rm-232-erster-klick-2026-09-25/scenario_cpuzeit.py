# CPU-Zeit des Hauptfadens je Bohrungsklick bis zur Ruhe, in Millionen Takten des Fadens
# (QueryThreadCycleTime: zählt nur, was der Hauptfaden rechnet, fein aufgelöst — unter
# Fremdlast weit stabiler als die Wandzeit; thread_time löst unter Windows nur 15,6 ms auf).
import ctypes as _ctypes
import statistics as _statistics
import time as _time

_kernel = _ctypes.windll.kernel32
_kernel.GetCurrentThread.restype = _ctypes.c_void_p


def _cycles():
    value = _ctypes.c_ulonglong(0)
    _kernel.QueryThreadCycleTime(_ctypes.c_void_p(_kernel.GetCurrentThread()), _ctypes.byref(value))
    return value.value

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
_cpu = []
_wall = []
for _round in range(6):
    for _hole in _holes:
        idle(0.4)
        _c0 = _cycles()
        _w0 = _time.perf_counter()
        window.object_tree.select_feature(_object_id, _hole)
        while _time.perf_counter() - _w0 < 5.0:
            application.processEvents()
            _flow = window._quiet_placement
            if _flow is not None and _flow._surface is not None and not _flow._surface_busy:
                break
            _time.sleep(0.001)
        _tail = _time.perf_counter()
        while _time.perf_counter() - _tail < 0.25:
            application.processEvents()
            _time.sleep(0.002)
        _c = (_cycles() - _c0) / 1e6
        if _round >= 1:
            _cpu.append(_c)
            _wall.append((_tail - _w0) * 1000.0)
log("ERGEBNIS Takte Hauptfaden Median", round(_statistics.median(_cpu), 1), "Mio, Wand bis Fläche", round(_statistics.median(_wall), 1), "ms, Klicks", len(_cpu))
