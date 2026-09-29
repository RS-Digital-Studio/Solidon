"""(ii) Fehlersuche am exakten Kern: Was wird ausgelassen, was schickt der Weg an OpenCASCADE?"""

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
from app.core.brep import edit, step  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.geom import edge_ops  # noqa: E402
from app.core.geom.edges import contact_band_limits, edges_of, wanted  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.types import SceneObject  # noqa: E402
from app.core.units import weld_tolerance  # noqa: E402

outer = edit.box(40.0, 30.0, 20.0)
inner = edit.moved(edit.box(34.0, 24.0, 20.0), (3.0, 3.0, 3.0))
cases = [("Hohlkasten", edit.boolean("difference", [outer, inner]), "all", 2.0)]
for name in ("pegboard-goot-ceramic-screwdrivers-v3", "pegboard-gs-100-v2"):
    cases.append((name, step.read((Path(r"F:\3D Dateien") / f"{name}.step").read_bytes()), "vertical", 1.0 if "goot" in name else 5.0))
for name, solid, group, size in cases:
    source = SceneObject(id="obj_1", name=name, mesh=solid, kind="brep")
    mesh = as_mesh_data(solid)
    entries = edges_of(mesh)
    chosen = wanted(entries, group, ())
    limits = contact_band_limits(entries, chosen, size, rounded=True, tolerance=weld_tolerance(mesh.bounds.diagonal))
    brep_group = edit.choose(solid, group)
    print(f"== {name}: Netz-Gruppe {len(chosen)}, zu eng {len(limits)}, exakte Gruppe {len(brep_group)}")
    fitted = edge_ops._group_that_fits(
        source, size, group, rounded=True, narrowest=edge_ops.narrowest_face(None), shape=None, law=None, rings_by_plane=True
    )
    if fitted is None:
        print("  _group_that_fits: None")
        continue
    indices, finding = fitted
    print(f"  behalten {len(indices)} exakte Kanten, Befund {finding.values}")
    try:
        edit.fillet(solid, size, group, (), selected_edges=indices)
        print("  OpenCASCADE: gelungen")
    except AppError as error:
        print("  OpenCASCADE:", type(error).__name__, str(getattr(error, "detail", error))[:160], getattr(error, "values", {}))
    good, bad = [], []
    for index in indices:
        try:
            edit.fillet(solid, size, group, (), selected_edges=(index,))
            good.append(index)
        except AppError as error:
            bad.append((index, str(getattr(error, "detail", error))[:50], getattr(error, "values", {}).get("wall_mm")))
    print(f"  einzeln: {len(good)} gelingen, {len(bad)} nicht: {bad[:6]}")
    if good:
        try:
            edit.fillet(solid, size, group, (), selected_edges=tuple(good))
            print("  die einzeln gelingenden zusammen: gelungen")
        except AppError as error:
            print("  zusammen:", str(getattr(error, "detail", error))[:80], getattr(error, "values", {}))
