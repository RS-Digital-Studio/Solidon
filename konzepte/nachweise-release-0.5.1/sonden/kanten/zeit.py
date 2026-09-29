"""Wie lange braucht ein Aufruf von edit.fillet mit ausdrücklicher Auswahl — und wofür?"""
import cProfile, os, pstats, sys, time
from pathlib import Path
sys.path.insert(0, os.getcwd())
from app.core.brep import edit, step  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.geom import edge_ops  # noqa: E402
from app.core.types import SceneObject  # noqa: E402

outer = edit.box(40.0, 30.0, 20.0)
inner = edit.moved(edit.box(34.0, 24.0, 20.0), (3.0, 3.0, 3.0))
cases = [("Hohlkasten", edit.boolean("difference", [outer, inner]), "all", 2.0)]
for name in ("pegboard-goot-ceramic-screwdrivers-v3",):
    cases.append((name, step.read((Path(r"F:\3D Dateien") / f"{name}.step").read_bytes()), "vertical", 2.0))
for name, solid, group, size in cases:
    fitted = edge_ops._group_that_fits(SceneObject(id="o", name=name, mesh=solid, kind="brep"), size, group,
        rounded=True, narrowest=edge_ops.narrowest_face(None), shape=None, law=None, rings_by_plane=True)
    indices = fitted[0]
    profile = cProfile.Profile()
    start = time.perf_counter()
    profile.enable()
    try:
        edit.fillet(solid, size, group, (), selected_edges=indices)
        ok = True
    except AppError:
        ok = False
    profile.disable()
    print(name, len(indices), "Kanten", ok, f"{time.perf_counter() - start:.2f} s")
    pstats.Stats(profile).sort_stats("cumulative").print_stats(8)
