"""Sonde 10: Ein geschlossenes, nicht orientierbares Netz (Röhre, deren Enden
gespiegelt verbunden sind) — was meldet unify_normals / repair?"""
import math
import numpy as np
import trimesh
from common import R, MeshData, codes, facts

n, m = 48, 12
rings = []
for i in range(n):
    t = 2 * math.pi * i / n
    centre = np.array([30 * math.cos(t), 30 * math.sin(t), 0.0])
    radial = np.array([math.cos(t), math.sin(t), 0.0])
    up = np.array([0.0, 0.0, 1.0])
    rings.append([centre + 5 * (math.cos(2 * math.pi * k / m) * radial + math.sin(2 * math.pi * k / m) * up) for k in range(m)])
vertices = np.asarray(rings).reshape(-1, 3)
faces = []
for i in range(n):
    j = (i + 1) % n
    for k in range(m):
        l = (k + 1) % m
        if i == n - 1:  # Naht: Ring 0 gespiegelt (k -> -k) anschließen
            jk, jl = (-k) % m, (-l) % m
        else:
            jk, jl = k, l
        a, b, c, d = i * m + k, i * m + l, j * m + jl, j * m + jk
        faces += [[a, b, c], [a, c, d]]
body = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)
mesh = MeshData.of(body)
print("vorher:", facts(mesh))
fixed, flipped = R.unify_normals(mesh)
print("unify_normals flipped=", flipped, facts(fixed))
rep = R.repair(mesh, inspect_intersections=True)
print("repair:", codes(rep.findings), facts(rep.mesh))
for f in rep.findings:
    print("   ", f.code, "|", str(f.message))
