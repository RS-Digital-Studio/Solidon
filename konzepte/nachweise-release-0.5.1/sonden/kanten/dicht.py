"""Ist das Pegboard-goot als exakter Körper vor und nach Verrunden R 1 (8 Kanten) dicht?"""
import os, sys
from pathlib import Path
sys.path.insert(0, os.getcwd())
from app.core.brep import edit, step  # noqa: E402
from app.core.geom import edge_ops  # noqa: E402
from app.core.types import SceneObject  # noqa: E402

solid = step.read((Path(r"F:\3D Dateien") / "pegboard-goot-ceramic-screwdrivers-v3.step").read_bytes())
print("vorher dicht", solid.is_watertight, "Teile", solid.component_count)
fitted = edge_ops._group_that_fits(SceneObject(id="o", name="g", mesh=solid, kind="brep"), 1.0, "vertical",
    rounded=True, narrowest=edge_ops.narrowest_face(None), shape=None, law=None, rings_by_plane=True)
indices, findings = fitted
out = edit.fillet(solid, 1.0, "vertical", (), selected_edges=indices)
print("nachher dicht", out.is_watertight, "Teile", out.component_count, "gültig", out.is_valid() if hasattr(out, "is_valid") else "?")
from OCP.BRepCheck import BRepCheck_Analyzer
print("BRepCheck vorher", BRepCheck_Analyzer(solid.shape).IsValid(), "nachher", BRepCheck_Analyzer(out.shape).IsValid())
for fine in (0.05, 0.01):
    print("Tessellierung", fine, out.to_mesh(deflection=fine).is_watertight)
try:
    whole = edit.fillet(solid, 0.3, "vertical")
    print("ganze Gruppe R 0,3 (alter Weg, 52 Kanten): dicht", whole.is_watertight)
except Exception as error:  # noqa: BLE001
    print("ganze Gruppe R 0,3:", type(error).__name__)
for radius in (0.3, 0.5, 1.0):
    part = edit.fillet(solid, radius, "vertical", (), selected_edges=indices)
    print(f"dieselben 8 Kanten R {radius}: dicht", part.is_watertight)
for index in indices:
    one = edit.fillet(solid, 1.0, "vertical", (), selected_edges=(index,))
    print("  einzeln", index, "dicht", one.is_watertight)
