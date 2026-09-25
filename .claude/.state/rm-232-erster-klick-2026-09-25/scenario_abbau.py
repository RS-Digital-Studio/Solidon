# Nach dem Schließen des Fensters: Vorrat leer, Ansicht und Maßtinte eingesammelt?
import gc as _gc
import weakref as _weakref

from PySide6.QtCore import QEvent as _QEvent
from PySide6.QtWidgets import QApplication as _QApplication

import app.ui.placement_flow as _pf

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)
for _hole in (*_holes, *_holes):
    window.object_tree.select_feature(_object_id, _hole)
    idle(0.8)
_canvas_ref = _weakref.ref(window._quiet_placement._canvas)
_view_ref = _weakref.ref(window.viewport)
log("vor dem Schließen: Vorrat", len(_pf._PARKED), "beobachtet", len(_pf._PARKED_WATCHED))
window.object_tree.select_object(_object_id)
idle(0.8)
log("nach Abwahl: Vorrat", len(_pf._PARKED), "beobachtet", len(_pf._PARKED_WATCHED))
window.release()
window.close()
window.deleteLater()
for _ in range(5):
    _QApplication.sendPostedEvents(None, _QEvent.Type.DeferredDelete)
    application.processEvents()
del window
_gc.collect()
log("nach dem Schließen: Vorrat", len(_pf._PARKED), "beobachtet", len(_pf._PARKED_WATCHED), "Ansicht lebt:", _view_ref() is not None, "Tinte lebt:", _canvas_ref() is not None)
import os as _os
LOG.flush()
_os._exit(0)
