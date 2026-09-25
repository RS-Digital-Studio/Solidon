"""Sonde 13b: b4/b5 aus s13 mit drei Ständen: HEAD, 18:04, aktuell."""
import importlib.util, sys
import numpy as np
import trimesh
from common import R, MeshData, codes, facts, HERE

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod); return mod

stands = {"HEAD": load("repair_head", "repair_head.py"), "18:04": load("repair_1804", "repair_stand_1804.py"), "aktuell": R}

def remove(body, mask):
    return MeshData.of(trimesh.Trimesh(vertices=body.vertices.copy(), faces=body.faces[~mask].copy(), process=False))

sphere = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
cs = sphere.triangles_center
cyl = trimesh.creation.cylinder(radius=10.0, height=30.0, sections=64).subdivide().subdivide()
cc = cyl.triangles_center
side = np.abs(np.hypot(cc[:, 0], cc[:, 1]) - 10.0) < 1.0
cases = {
    "b4 Kugel unter dem Äquator (Schale mit gezacktem Rand)": remove(sphere, cs[:, 2] > -2.0),
    "b4' Halbkugel exakt am Äquator": remove(sphere, cs[:, 2] > 0.0),
    "b5 Zylinderfenster ~240°": remove(cyl, side & (cc[:, 0] > -5.0) & (np.abs(cc[:, 2]) < 8.0)),
}
for label, mesh in cases.items():
    print("===", label, facts(mesh))
    for name, mod in stands.items():
        rep = mod.repair(mesh)
        f = facts(rep.mesh, intersections=True)
        print(f"  {name:8}: {codes(rep.findings)} tight={f['tight']} open={f['open']} vol={f['vol']} Schnittdreiecke={f['x_faces']}")
