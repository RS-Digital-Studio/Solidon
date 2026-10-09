"""Zieht Drache und Stützsperre aus der Übergabe-3MF als STL heraus."""

import re
import sys
import zipfile

import numpy as np
import trimesh

src = sys.argv[1]
data = zipfile.ZipFile(src).read("3D/3dmodel.model")
objects = {}
for m in re.finditer(rb'<object id="(\d+)" type="model"[^>]*name="([^"]*)">', data):
    objects[int(m.group(1))] = (m.start(), m.group(2).decode())
order = sorted(objects.items(), key=lambda kv: kv[1][0])
for i, (oid, (start, name)) in enumerate(order):
    end = order[i + 1][1][0] if i + 1 < len(order) else len(data)
    chunk = data[start:end]
    if b"<mesh>" not in chunk:
        continue
    verts = np.array(
        re.findall(rb'<vertex x="([^"]+)" y="([^"]+)" z="([^"]+)"', chunk), dtype=np.float64
    )
    tris = np.array(
        re.findall(rb'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', chunk), dtype=np.int64
    )
    mesh = trimesh.Trimesh(verts, tris, process=False)
    out = f"obj{oid}.stl"
    mesh.export(out)
    print(
        oid,
        name,
        len(verts),
        len(tris),
        mesh.bounds.tolist(),
        "watertight",
        mesh.is_watertight,
        "vol",
        mesh.volume,
    )
