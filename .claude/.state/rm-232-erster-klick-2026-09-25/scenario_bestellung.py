# Wie lange wartet eine Bestellung render() bis zum Zeichnen? Zufällige Zeitpunkte, Ruhe dazwischen.
import random as _random
import statistics as _statistics
import time as _time

_renderer = window.viewport.renderer
_renderer_type = type(_renderer)
_started = []
_original_draw = _renderer_type._draw


def _marked(self, *args, **kwargs):
    _started.append(_time.perf_counter())
    return _original_draw(self, *args, **kwargs)


_renderer_type._draw = _marked
_waits = []
_rng = _random.Random(7)
for _index in range(40):
    idle(0.15)
    pump(_rng.random() * 0.05)
    _started.clear()
    _t = _time.perf_counter()
    _renderer.render()
    while not _started and _time.perf_counter() - _t < 1.0:
        application.processEvents()
        _time.sleep(0.0005)
    if _started:
        _waits.append((_started[0] - _t) * 1000)
log(f"Wartezeit bis zum Zeichnen: Median {_statistics.median(_waits):.1f} ms, Mittel {_statistics.fmean(_waits):.1f}, höchstens {max(_waits):.1f}, n={len(_waits)}")
