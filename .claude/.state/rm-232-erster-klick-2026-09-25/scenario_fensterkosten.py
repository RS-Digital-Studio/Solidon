# Was kostet ein natives Überlagerungsfenster: anlegen+zeigen, verbergen, wieder zeigen, bewegen?
import statistics as _statistics
import time as _time

from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import QLabel as _QLabel

_view = window.viewport
_rounds = {"anlegen+zeigen": [], "verbergen": [], "wieder zeigen": [], "bewegen": [], "raise_": [], "löschen": []}
for _round in range(6):
    _labels = []
    _t = _time.perf_counter()
    for _index in range(9):
        _label = _QLabel(f"Probe {_index}", _view)
        _label.setAutoFillBackground(True)
        _label.move(400 + 30 * _index, 300 + 20 * _index)
        _label.show()
        _labels.append(_label)
    application.processEvents()
    _rounds["anlegen+zeigen"].append((_time.perf_counter() - _t) * 1000)
    _t = _time.perf_counter()
    for _label in _labels:
        _label.hide()
    application.processEvents()
    _rounds["verbergen"].append((_time.perf_counter() - _t) * 1000)
    _t = _time.perf_counter()
    for _label in _labels:
        _label.show()
    application.processEvents()
    _rounds["wieder zeigen"].append((_time.perf_counter() - _t) * 1000)
    _t = _time.perf_counter()
    for _label in _labels:
        _label.move(_label.x() + 5, _label.y() + 3)
    application.processEvents()
    _rounds["bewegen"].append((_time.perf_counter() - _t) * 1000)
    _t = _time.perf_counter()
    for _label in reversed(_labels):
        _label.raise_()
    application.processEvents()
    _rounds["raise_"].append((_time.perf_counter() - _t) * 1000)
    _t = _time.perf_counter()
    for _label in _labels:
        _label.hide()
        _label.deleteLater()
    application.processEvents()
    from PySide6.QtCore import QEvent as _QEvent
    from PySide6.QtWidgets import QApplication as _QA
    _QA.sendPostedEvents(None, _QEvent.Type.DeferredDelete)
    _rounds["löschen"].append((_time.perf_counter() - _t) * 1000)
    log("nativ:", all(l.testAttribute(_Qt.WidgetAttribute.WA_NativeWindow) for l in _labels[:0]) if False else "", end="") if False else None
for _key, _values in _rounds.items():
    log(f"{_key:16s} je 9 Fenster: Median {_statistics.median(_values[1:]):6.1f} ms  ({', '.join(f'{v:.1f}' for v in _values)})")
