"""RM-279 (i) an echten Modellen: die Mündungen der Querbohrungen einzeln verrundet.

Aufruf aus der Wurzel eines Arbeitsbaums: python ringe_echt.py. Je Pegboard-STEP
alle Ringe über ihre Schlüssel, exakt aus der STEP, als Netz aus ihrer
Tessellierung; Abtrag Netz gegen exakt. Vorher/nachher im Wechsel an zwei
Arbeitsbäumen fahren.
"""

import math
import os
import sys
from pathlib import Path

TREE = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
sys.path.insert(0, TREE)
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve()), app.__file__

from app.core.brep import edit, step  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.geom.edges import (  # noqa: E402
    bevel_edges,
    edge_key,
    edge_lie_of,
    edges_of,
    round_edges,
    workable,
)

FILES = Path(r"F:\3D Dateien")


def rings(entries):
    """Die stehenden Ringe — die Mündungen der Querbohrungen."""
    return [
        e
        for e in entries
        if math.dist(e.direction, (0.0, 0.0, 0.0)) < 1e-6
        and edge_lie_of(e) == "upright"
        and (not hasattr(e, "normals") or workable(e))
    ]


for name in ("pegboard-goot-ceramic-screwdrivers-v3", "pegboard-pb3041-v4", "pegboard-gs-100-v2"):
    solid = step.read((FILES / f"{name}.step").read_bytes())
    mesh = solid.to_mesh()
    exact_keys = [edit.edge_key(e) for e in rings(edit.edges_of(solid))]
    mesh_keys = [edge_key(e) for e in rings(edges_of(mesh))]
    print(f"\n== {name}: Ringe exakt {len(exact_keys)}, Netz {len(mesh_keys)}")
    for size, rounded in ((0.1, True), (0.2, True), (0.5, True), (1.0, True), (0.3, False)):
        label = f"{'R' if rounded else 'Fase'} {size}"
        try:
            exact = solid.volume - (edit.fillet if rounded else edit.chamfer)(
                solid, size, "named", exact_keys
            ).volume
        except AppError as error:
            exact = None
            exact_note = str(getattr(error, "detail", error))[:70]
        try:
            outcome = (round_edges if rounded else bevel_edges)(mesh, size, "named", mesh_keys)
            netz = mesh.volume - outcome.mesh.volume
            closed = outcome.mesh.is_watertight
        except AppError as error:
            netz = None
            closed = False
            mesh_note = str(getattr(error, "detail", error))[:70]
        text = f"  {label:8s} exakt " + (f"{exact:8.3f}" if exact is not None else f"abgelehnt ({exact_note})")
        text += "  Netz " + (
            f"{netz:8.3f} dicht {closed}" if netz is not None else f"abgelehnt ({mesh_note})"
        )
        if exact and netz is not None:
            text += f"  Netz/exakt {netz / exact:6.3f}"
        print(text)
