# Wo stehen die Maßfelder nach jedem Bohrungsklick? Zum Vergleich vor und nach einer Änderung.
import os as _os
from pathlib import Path as _Path

_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = sorted(name for name, f in _entry.features.items() if f.kind == "hole")[:4]
window.object_tree.select_object(_object_id)
idle(0.8)
_lines = []
for _hole in _holes:
    window.object_tree.select_feature(_object_id, _hole)
    idle(1.2)
    _flow = window._quiet_placement
    if _flow is None:
        _lines.append(f"{_hole}: kein Fluss")
        continue
    for _name, _widget in [("karte", _flow._measure_box), *[(f"kante{i}", b) for i, b in enumerate(_flow._reference_boxes)], *[(f"mitte{i}", m) for i, m in enumerate(_flow._centre_measures)]]:
        _lines.append(f"{_hole} {_name}: {'sichtbar' if not _widget.isHidden() else 'verborgen'} {_widget.geometry().getRect()}")
_target = _Path(OUT) / f"plaetze-{_os.environ.get('PROBE_TAG', 'x')}.txt"
_target.write_text("\n".join(_lines) + "\n", encoding="utf-8")
log("geschrieben", _target.name, len(_lines))
