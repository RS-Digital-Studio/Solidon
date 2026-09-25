# Wer bestellt die Bilder nach _settle? Stapel je render()/render_now() mit Zeit relativ zum Klick.
import time as _time
import traceback as _traceback

import app.ui.placement_flow as _pf

_t0 = [0.0]
_log_on = [False]
_renderer_type = type(window.viewport.renderer)
for _name in ("render", "render_now", "_draw"):
    _original = getattr(_renderer_type, _name)

    def _make(original, name):
        def wrapped(self, *args, **kwargs):
            if _log_on[0]:
                stack = [
                    f"{frame.name}:{frame.lineno}"
                    for frame in _traceback.extract_stack(limit=9)[:-1]
                    if "3D Druck\app" in frame.filename or "3D Druck/app" in frame.filename
                ]
                log(f"  {(_time.perf_counter() - _t0[0]) * 1000:7.1f} ms {name}  <- {' < '.join(reversed(stack[-5:]))}")
            return original(self, *args, **kwargs)

        return wrapped

    setattr(_renderer_type, _name, _make(_original, _name))
_original_settle = _pf.PlacementFlow._settle


def _settle(self, *args, **kwargs):
    if _log_on[0]:
        log(f"  {(_time.perf_counter() - _t0[0]) * 1000:7.1f} ms _settle")
    return _original_settle(self, *args, **kwargs)


_pf.PlacementFlow._settle = _settle
_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
for _round in range(3):
    for _hole in _holes:
        idle(0.4)
        _log_on[0] = _round == 2
        if _log_on[0]:
            log(f"--- Klick {_hole}")
        _t0[0] = _time.perf_counter()
        window.object_tree.select_feature(_object_id, _hole)
        if _log_on[0]:
            log(f"  {(_time.perf_counter() - _t0[0]) * 1000:7.1f} ms synchron fertig")
        idle(0.6)
        _log_on[0] = False
