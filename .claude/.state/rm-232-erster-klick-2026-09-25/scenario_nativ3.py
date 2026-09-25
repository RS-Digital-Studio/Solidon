# Welches Kind macht das Merkmalfenster nativ? ChildAdded mitschreiben, dazu die Zahl
# nativer Kinder vorher; und ob je Klick alte Widgets wirklich gehen (DeferredDelete).
import time as _time

from PySide6.QtCore import QEvent as _QEvent
from PySide6.QtCore import QObject as _QObject
from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import QApplication as _QApplication
from PySide6.QtWidgets import QWidget as _QWidget

_NATIVE = _Qt.WidgetAttribute.WA_NativeWindow
_panel = window.feature_panel


def _native_children():
    return sum(
        1
        for child in _panel.children()
        if isinstance(child, _QWidget) and child.testAttribute(_NATIVE)
    )


class _Watch(_QObject):
    first = True

    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() == _QEvent.Type.ChildAdded:
            child = event.child()
            if isinstance(child, _QWidget) and child.testAttribute(_NATIVE) and _Watch.first:
                import traceback as _tb

                log(
                    "ERSTES natives Kind:",
                    type(child).__name__,
                    child.objectName(),
                    "native Kinder vorher:",
                    _native_children(),
                )
                log("".join(_tb.format_stack(limit=14)))
                _Watch.first = False
        return False


_watch = _Watch()
_panel.installEventFilter(_watch)
log("Merkmalfenster selbst nativ:", _panel.testAttribute(_NATIVE), "native Kinder:", _native_children())
_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)
log("nach Objektwahl native Kinder:", _native_children())


def _natives():
    return {id(w) for w in _QApplication.allWidgets() if w.testAttribute(_NATIVE)}


_times = []
for _round in range(3):
    for _hole in _holes:
        _start = _time.perf_counter()
        window.object_tree.select_feature(_object_id, _hole)
        while _time.perf_counter() - _start < 30.0:
            application.processEvents()
            _flow = window._quiet_placement
            if _flow is not None and _flow._surface is not None and not _flow._surface_busy:
                break
            _time.sleep(0.002)
        _times.append((_time.perf_counter() - _start) * 1000.0)
        idle(0.6)
        _QApplication.sendPostedEvents(None, _QEvent.Type.DeferredDelete)
        application.processEvents()
        log(
            f"Klick {_hole}: {_times[-1]:.1f} ms, nativ gesamt {len(_natives())},"
            f" Widgets {len(_QApplication.allWidgets())}, native Kinder im Fenster {_native_children()}"
        )
