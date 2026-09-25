"""Hauptsitzung: die künstlichen Fehlerbilder der Prüfer gegen repair() und normalise()."""

import sys
from pathlib import Path

import numpy as np

import app.core.bootstrap  # noqa: F401
from app.core.geom.mesh import MeshData, face_components, read_mesh
from app.core.geom.repair import open_edge_count, branching_edge_count, repair, self_intersection_check
from app.core.ingest.loader import normalise

HERE = Path(__file__).parent / "netze"
names = sys.argv[1:] or sorted(p.name for p in HERE.glob("*.stl"))
for name in names:
    raw = read_mesh((HERE / name).read_bytes(), ".stl")
    imported = normalise(raw, "mm", weld_is_reading=True)
    body = imported.mesh
    found, _ = self_intersection_check(body)
    parts = [float(np.sum(body.raw.area_faces[c])) for c in face_components(body.raw)]
    print(f"== {name}: Import dicht={body.is_watertight} Vol={body.volume:.1f} Teile={len(parts)} offen={open_edge_count(body)} verzweigt={branching_edge_count(body)} wound={body.raw.is_winding_consistent} Schnitte={len(found)}")
    for f in imported.findings:
        print("   I", f.code, f.severity, str(f.message)[:110], dict(f.values) if f.values else "", f.location)
    fixed = repair(body, self_intersections=True, inspect_intersections=True)
    found, _ = self_intersection_check(fixed.mesh)
    print(f"   Reparieren: dicht={fixed.mesh.is_watertight} Vol={fixed.mesh.volume:.1f} Teile={len(face_components(fixed.mesh.raw))} wound={fixed.mesh.raw.is_winding_consistent} Schnitte={len(found)}")
    for f in fixed.findings:
        print("   R", f.code, f.severity, str(f.message)[:110])
