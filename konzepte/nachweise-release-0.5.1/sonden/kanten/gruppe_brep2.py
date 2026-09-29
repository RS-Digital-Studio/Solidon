"""(ii) Fehlersuche: exakte Kanten nur übernehmen, wenn sie auf einem behaltenen Netzzug liegen."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402

from app.core.brep import edit, step  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.geom.edges import contact_band_limits, edges_of, wanted  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.units import MAX_FACET_SAG, weld_tolerance  # noqa: E402

outer = edit.box(40.0, 30.0, 20.0)
inner = edit.moved(edit.box(34.0, 24.0, 20.0), (3.0, 3.0, 3.0))
cases = [("Hohlkasten", edit.boolean("difference", [outer, inner]), "all", s) for s in (2.0, 5.0)]
for name in ("pegboard-goot-ceramic-screwdrivers-v3", "pegboard-gs-100-v2", "pegboard-pb3041-v4"):
    solid = step.read((Path(r"F:\3D Dateien") / f"{name}.step").read_bytes())
    cases += [(name, solid, "vertical", s) for s in (0.3, 1.0, 2.0)]


def near(chains, tolerance):
    if not chains:
        return lambda point: False
    starts = np.concatenate([np.asarray(e.points[:-1], dtype=float) for e in chains])
    stops = np.concatenate([np.asarray(e.points[1:], dtype=float) for e in chains])
    span = stops - starts
    square = np.maximum(np.einsum("ij,ij->i", span, span), 1e-24)

    def test(point):
        offset = np.asarray(point, dtype=float) - starts
        share = np.clip(np.einsum("ij,ij->i", offset, span) / square, 0.0, 1.0)
        return bool(np.linalg.norm(offset - share[:, None] * span, axis=1).min() <= tolerance)

    return test


for name, solid, group, size in cases:
    mesh = as_mesh_data(solid)
    entries = edges_of(mesh)
    tol = weld_tolerance(mesh.bounds.diagonal)
    chosen = wanted(entries, group, ())
    limits = contact_band_limits(entries, chosen, size, rounded=True, tolerance=tol)
    keep_chains = [e for e in chosen if id(e) not in limits]
    on_kept = near(keep_chains, 10 * tol + MAX_FACET_SAG)
    on_narrow = near([e for e in chosen if id(e) in limits], 10 * tol + MAX_FACET_SAG)
    brep_group = edit.choose(solid, group)
    kept = []
    for e in brep_group:
        pts = np.asarray(edit.edge_points(e), dtype=float)
        steps = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        run = np.concatenate(([0.0], np.cumsum(steps)))
        probes = [
            np.array([np.interp(f * run[-1], run, pts[:, k]) for k in range(3)])
            for f in (1 / 3, 2 / 3)
        ]
        if all(on_kept(p) for p in probes) and not any(on_narrow(p) for p in probes):
            kept.append(e)
    text = f"{name} R {size}: Netz {len(chosen)} (zu eng {len(limits)}), exakt {len(brep_group)} → behalten {len(kept)}"
    if kept:
        try:
            out = edit.fillet(solid, size, group, (), selected_edges=edit.native_edge_indices(solid, kept))
            text += f"  OCC gelungen, weg {solid.volume - out.volume:.3f}"
        except AppError as error:
            text += f"  OCC abgelehnt {getattr(error, 'values', {})}"
    print(text)
