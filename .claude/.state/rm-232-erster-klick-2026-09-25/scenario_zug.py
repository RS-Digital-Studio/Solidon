# Eine Kamerageste (Linkszug über die Ansicht, eine Sekunde): Bilder je Sekunde und Hauptfaden-Zeit.
import time as _time

from PySide6.QtCore import QEvent as _QEvent
from PySide6.QtCore import QPointF as _QPointF
from PySide6.QtCore import Qt as _Qt

_renderer_type = type(window.viewport.renderer)
_frames = []
_original_draw = _renderer_type._draw


def _counted(self, *args, **kwargs):
    _start = _time.perf_counter()
    try:
        return _original_draw(self, *args, **kwargs)
    finally:
        _frames.append((_start, _time.perf_counter() - _start))


_renderer_type._draw = _counted
_widget = render_widget()
_centre = _QPointF(_widget.width() * 0.5, _widget.height() * 0.5)
_results = []
for _round in range(3):
    idle(0.5)
    _frames.clear()
    _left = _Qt.MouseButton.LeftButton
    send(_QEvent.Type.MouseMove, _centre, _Qt.MouseButton.NoButton)
    send(_QEvent.Type.MouseButtonPress, _centre, _left, _left)
    _cpu = _time.thread_time()
    _t = _time.perf_counter()
    _steps = 0
    while _time.perf_counter() - _t < 1.0:
        _share = (_time.perf_counter() - _t) / 1.0
        send(_QEvent.Type.MouseMove, _QPointF(_centre.x() + 400 * _share, _centre.y() + 120 * _share), _left)
        _steps += 1
        _time.sleep(0.004)
    _span = _time.perf_counter() - _t
    _cpu = _time.thread_time() - _cpu
    send(_QEvent.Type.MouseButtonRelease, _QPointF(_centre.x() + 400, _centre.y() + 120), _Qt.MouseButton.NoButton, _left)
    _inside = [f for f in _frames if f[0] - _t < _span]
    _draw = sum(f[1] for f in _inside) * 1000
    _results.append((len(_inside) / _span, _cpu / _span * 100, _draw / max(len(_inside), 1)))
    log(f"Zug {_round}: {len(_inside) / _span:5.1f} Bilder/s, {_steps} Bewegungen, Hauptfaden {_cpu / _span * 100:4.0f} % belegt, {_draw / max(len(_inside), 1):4.1f} ms je Bild")
log("ERGEBNIS", " | ".join(f"{fps:.0f} Bilder/s, {cpu:.0f} %" for fps, cpu, _ms in _results))
