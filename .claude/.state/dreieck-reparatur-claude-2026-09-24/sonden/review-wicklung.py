"""Review-Sonde: `wind_consistently` an großen und an offenen Netzen (nur lesend).

W1  Icosphäre Unterteilung 8 (1,31 Mio. Dreiecke), 30 % der Dreiecke gedreht: Zeit, Ergebnis
W2  offene Halbkugel, 70 % gedreht: Mehrheit gewinnt — zeigt das Ergebnis nach innen?
W3  zwei getrennte offene Kappen, je verschieden gedreht
W4  Würfel mit einer Möbius-artigen Naht (geschlossen, nicht orientierbar) — Absturz? Befund?
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import R, facts  # noqa: E402

import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402

rng = np.random.default_rng(3)

big = trimesh.creation.icosphere(subdivisions=8, radius=50.0)
faces = np.array(big.faces)
flip = rng.random(len(faces)) < 0.3
faces[flip] = faces[flip][:, ::-1]
body = trimesh.Trimesh(big.vertices, faces, process=False)
start = time.perf_counter()
R.wind_consistently(body)
spent = time.perf_counter() - start
print(f"W1 {len(faces)} Dreiecke: wind_consistently {spent:.2f} s, einheitlich {body.is_winding_consistent}")
start = time.perf_counter()
R.turn_shells_outward(body)
print(f"W1 turn_shells_outward {time.perf_counter() - start:.2f} s, facts {facts(MeshData.of(body))}")

half = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
keep = half.triangles_center[:, 2] > 0.0
half.update_faces(keep)
half.remove_unreferenced_vertices()
faces = np.array(half.faces)
flip = rng.random(len(faces)) < 0.7
faces[flip] = faces[flip][:, ::-1]
open_half = trimesh.Trimesh(half.vertices, faces, process=False)
R.wind_consistently(open_half)
normals = open_half.face_normals
outward = np.sum(normals * open_half.triangles_center, axis=1) > 0
print("W2 offene Halbkugel, 70 % gedreht: einheitlich", open_half.is_winding_consistent,
      "Anteil nach außen", round(float(outward.mean()), 3))
result = R.repair(MeshData.of(open_half))
print("W2 repair():", [f.code for f in result.findings], facts(result.mesh))
