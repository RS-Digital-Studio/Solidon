# Profil nur über _settle und über den synchronen Klick vor start (Arbeiter ruhen dort).
import cProfile as _cProfile
import time as _time

import app.ui.placement_flow as _pf

_settle_profile = _cProfile.Profile()
_sync_profile = _cProfile.Profile()
_active = [False]
_original_settle = _pf.PlacementFlow._settle
_original_start = _pf.PlacementFlow.start


def _settle(self, *args, **kwargs):
    if _active[0]:
        _settle_profile.enable()
    try:
        return _original_settle(self, *args, **kwargs)
    finally:
        _settle_profile.disable()


def _start(self, *args, **kwargs):
    _sync_profile.disable()
    return _original_start(self, *args, **kwargs)


_pf.PlacementFlow._settle = _settle
_pf.PlacementFlow.start = _start
_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
for _round in range(6):
    for _hole in _holes:
        idle(0.4)
        _active[0] = _round >= 1
        if _active[0]:
            _sync_profile.enable()
        window.object_tree.select_feature(_object_id, _hole)
        _sync_profile.disable()
        idle(0.6)
_settle_profile.dump_stats(str(OUT / "settle.prof"))
_sync_profile.dump_stats(str(OUT / "sync.prof"))
log("fertig")
