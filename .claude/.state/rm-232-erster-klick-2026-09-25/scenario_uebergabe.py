# Übergabe der schwebenden Widgets von Bohrung zu Bohrung, am echten Fenster (wie der Test).
from PySide6.QtCore import SIGNAL as _SIGNAL
from PySide6.QtCore import Qt as _Qt
from PySide6.QtWidgets import QApplication as _QApplication

from app.ui.labels import _WheelNeedsFocus

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
window.object_tree.select_object(_object_id)
idle(0.8)
window.object_tree.select_feature(_object_id, _holes[0])
idle(1.2)
_first = window._quiet_placement
log("erster Fluss aktiv:", _first is not None and _first.active, "Fläche:", _first._surface is not None)
_kept = (_first._measure_box, _first._canvas, *_first._measures, *_first._reference_boxes)
_listeners = (
    _first._measure_cancel.receivers(_SIGNAL("clicked(bool)")),
    _first._measures[0].receivers(_SIGNAL("valueChangedMm(double)")),
)
log("Empfänger vorher:", _listeners)
window.object_tree.select_feature(_object_id, _holes[1])
idle(1.2)
_second = window._quiet_placement
_now = (_second._measure_box, _second._canvas, *_second._measures, *_second._reference_boxes)
log("zweiter Fluss neu:", _second is not _first, "aktiv:", _second.active, "alter aktiv:", _first.active, "alte Links:", len(_first._links), "neue Links:", len(_second._links))
log("dieselben Widgets:", all(a is b for a, b in zip(_kept, _now, strict=True)))
log("Empfänger nachher:", (
    _second._measure_cancel.receivers(_SIGNAL("clicked(bool)")),
    _second._measures[0].receivers(_SIGNAL("valueChangedMm(double)")),
))
log("Radfilter je Feld:", [len(f.findChildren(_WheelNeedsFocus)) for f in (*_second._measures, _second._depth_measure, *_second._centre_measures)])
log("Maßkarte sichtbar:", not _second._measure_box.isHidden(), "Tinte:", _second._canvas.shown)
_heard = []
_first.dialog.valuesChanged.connect(lambda *_a: _heard.append("alt"))
_second.dialog.valuesChanged.connect(lambda *_a: _heard.append("neu"))
_field = next((f for f in _second._measures if not f.isHidden()), None)
log("sichtbares Kantenmaß:", _field is not None)
if _field is not None:
    _before = _field.value_mm()
    _field.set_value_mm(_before + 1.0)
    idle(0.8)
    log("gehört:", _heard, "Werte neu:", {k: v for k, v in _second.dialog.values().items() if k in ("x", "y", "z")})
state("nach dem Tippen")
shot("uebergabe-zweite-bohrung")
# Dritte Runde zurück zur ersten Bohrung: Übergabe klappt auch ein zweites Mal.
window.object_tree.select_feature(_object_id, _holes[0])
idle(1.2)
_third = window._quiet_placement
log("dritter Fluss:", _third is not _second, "dieselbe Karte:", _third._measure_box is _kept[0], "Links alt:", len(_second._links))
