# RM-269 (4): Wo steht die Kamera nach *Modell teilen*? (KUNDE-11)
import os as _os

import numpy as _np

from app.core.scene import OperationDraft as _Draft

_view = window.viewport
_renderer = _view.renderer
_factor = float(_os.environ.get("SONDE_SKALIERUNG", "1"))


def _frame(title):
    result = window.session.last_result
    width, height = _renderer.view_size()
    union = []
    log(f"--- {title}: Bild {width}x{height}, gewählt {window.object_tree.selected_objects()}, "
        f"Explosion {_view._explosion:.2f}, eingepasst auf {_view._fitted_to}")
    pose = _renderer.camera_pose()
    log("   Kamera", [round(float(v), 1) for v in pose.position], "Blick", [round(float(v), 1) for v in pose.focal_point])
    for identifier, entry in result.scene.objects.items():
        box = entry.mesh.bounds
        offset = _np.asarray(_view._shown_offset(entry, result), float)
        corners = [
            _np.asarray((x, y, z), float) + offset
            for x in (box.minimum[0], box.maximum[0])
            for y in (box.minimum[1], box.maximum[1])
            for z in (box.minimum[2], box.maximum[2])
        ]
        shown = [_renderer.world_to_display(tuple(float(v) for v in c))[:2] for c in corners]
        xs = [p[0] for p in shown]
        ys = [p[1] for p in shown]
        area = max(1e-9, (max(xs) - min(xs)) * (max(ys) - min(ys)))
        inside = max(0.0, min(max(xs), width) - max(min(xs), 0)) * max(0.0, min(max(ys), height) - max(min(ys), 0))
        union += shown
        log(f"   {identifier}: Bildanteil im Rahmen {inside / area:5.0%}, "
            f"Rahmen x {min(xs):.0f}..{max(xs):.0f}, y {min(ys):.0f}..{max(ys):.0f}")
    xs = [p[0] for p in union]
    ys = [p[1] for p in union]
    area = max(1e-9, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    inside = max(0.0, min(max(xs), width) - max(min(xs), 0)) * max(0.0, min(max(ys), height) - max(min(ys), 0))
    log(f"   ALLE: im Bild {inside / area:5.0%}, Rahmen x {min(xs):.0f}..{max(xs):.0f} (von {width}), "
        f"y {min(ys):.0f}..{max(ys):.0f} (von {height})")


_object_id = next(iter(window.session.last_result.scene.objects))
if _factor != 1.0:
    window.session.apply("Skalieren", [_Draft(op="scale_object", inputs=(_object_id,), params={"factor": _factor})])
    idle(1.0)
    _object_id = next(iter(window.session.last_result.scene.objects))
window.object_tree.select_object(_object_id)
idle(0.6)
_frame("vor dem Teilen")
window.action_auto_split(_object_id)
_deadline = time.monotonic() + 200
while time.monotonic() < _deadline and (window.session.split_running or window.session.busy):
    pump(0.1)
idle(1.5)
_frame("nach dem Teilen")
