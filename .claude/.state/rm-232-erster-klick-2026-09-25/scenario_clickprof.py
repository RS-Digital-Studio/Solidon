# Bohrungen abwechselnd wählen und die Wiederholungsklicks im Hauptfaden profilieren.
# Läuft über slot_probe.py (echtes Fenster); schreibt probe-out/clickprof/klick.prof.
import cProfile as _cProfile
import statistics as _statistics
import time as _time

from PySide6.QtCore import QElapsedTimer as _QElapsedTimer
from PySide6.QtCore import QTimer as _QTimer

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
log("Bohrungen:", _holes)
_profile = _cProfile.Profile()
_ticks = []
_clock = _QElapsedTimer()
_timer = _QTimer()
_timer.setInterval(5)
_timer.timeout.connect(lambda: _ticks.append(_clock.elapsed()))
_clock.start()
_timer.start()
_times = []
for _round in range(5):
    for _hole in _holes:
        idle(0.3)
        _ticks.clear()
        _begin = _clock.elapsed()
        if _round >= 1:
            _profile.enable()
        _start = _time.perf_counter()
        window.object_tree.select_feature(_object_id, _hole)
        _sync = (_time.perf_counter() - _start) * 1000.0
        while _time.perf_counter() - _start < 30.0:
            application.processEvents()
            _flow = window._quiet_placement
            if _flow is not None and _flow._surface is not None and not _flow._surface_busy:
                break
            _time.sleep(0.002)
        _took = (_time.perf_counter() - _start) * 1000.0
        # Die Bilder nach der Fläche gehören zum Klick: bis 300 ms nachlaufen lassen.
        _tail = _time.perf_counter()
        while _time.perf_counter() - _tail < 0.3:
            application.processEvents()
            _time.sleep(0.002)
        _profile.disable()
        _gaps = [b - a for a, b in zip([_begin, *_ticks], _ticks)]
        _times.append(_took)
        log(
            f"KLICK {_hole}: synchron {_sync:6.1f} ms, Fläche nach {_took:7.1f} ms,"
            f" längste Lücke {max(_gaps, default=0)} ms"
        )
        idle(0.6)
_profile.dump_stats(str(OUT / "klick.prof"))
log("ERGEBNIS erster", round(_times[0], 1), "ms, danach Median", round(_statistics.median(_times[2:]), 1), "ms")
