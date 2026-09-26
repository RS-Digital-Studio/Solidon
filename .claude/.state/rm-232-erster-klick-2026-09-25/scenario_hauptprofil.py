# Profil über den ganzen Klick bis zur Fläche (Klicks 2 bis 10), Aufrufer von setToolTip und setVisible.
import cProfile as _cProfile
import time as _time

_profile = _cProfile.Profile()
_entry = [f for f in window.session.last_result.scene.objects.values()][0]
_object_id = _entry.id
_holes = [name for name, f in _entry.features.items() if f.kind == "hole"][:2]
for _round in range(6):
    for _hole in _holes:
        idle(0.4)
        if _round >= 1:
            _profile.enable()
        _start = _time.perf_counter()
        window.object_tree.select_feature(_object_id, _hole)
        while _time.perf_counter() - _start < 5.0:
            application.processEvents()
            _flow = window._quiet_placement
            if _flow is not None and _flow._surface is not None and not _flow._surface_busy:
                break
            _time.sleep(0.001)
        _profile.disable()
_profile.dump_stats(str(OUT / "haupt.prof"))
log("fertig")
