# Wer ruft set_measuring je Bohrungsklick, mit welchen Werten, und wie lange dauert es.
import time as _time
import traceback as _traceback

import app.ui.panels as _panels

_calls = []
_original = _panels.FeaturePanel.set_measuring


def _wrapped(self, active, **kwargs):
    started = _time.perf_counter()
    try:
        return _original(self, active, **kwargs)
    finally:
        took = (_time.perf_counter() - started) * 1000.0
        where = " <- ".join(
            f"{frame.name}:{frame.lineno}" for frame in _traceback.extract_stack(limit=7)[:-1][::-1]
        )
        _calls.append((active, kwargs, took, where))


_panels.FeaturePanel.set_measuring = _wrapped
_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
for _round in range(3):
    for _hole in _holes:
        idle(0.4)
        _calls.clear()
        window.object_tree.select_feature(_object_id, _hole)
        idle(0.4)
        if _round == 2:
            log(f"--- {_hole}")
            for _active, _kwargs, _took, _where in _calls:
                log(f"  {_active} {_kwargs} {_took:.1f} ms  {_where}")
