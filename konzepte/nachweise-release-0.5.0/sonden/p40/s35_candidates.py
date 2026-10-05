"""Sonde 35: Was ein umgewandelter Körper für den Nachbau (P4.1) mitbringt.

Je Körper: Flächen gesamt; wie viele davon ein Merkmal der exakten Erkennung
(P2.3) belegt; wie viele ebene Flächen Stützebenen der konvexen Hülle sind
(Kandidaten der Grundform, Konzept §8.2); und wie nah der einfachste
Nachbaukandidat — Hüllquader der Stützebenen minus Bohrungen plus Zapfen —
am Volumen liegt. Keine Rekonstruktion, nur die Frage, woraus sie schöpfen kann.
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

TREE = sys.argv[1]
sys.path.insert(0, TREE)

import numpy as np  # noqa: E402

import app  # noqa: E402
from app.core.brep import from_mesh  # noqa: E402
from app.core.brep.features import features_of  # noqa: E402
from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402

print("app", app.__file__)
for name in sys.argv[2:]:
    path = Path(name)
    if not path.exists():
        path = Path(TREE) / "tests" / "data" / "meshes" / name
    mesh = normalise(read_mesh(path.read_bytes(), path.suffix), "mm", weld_is_reading=True).mesh
    result = from_mesh.convert(mesh, detect(mesh), tolerance=0.01)
    body = result.solid
    features = features_of(body)
    kinds = Counter(feature.kind for feature in features.values())
    faces = body.faces()
    owned: set[int] = set()
    for feature in features.values():
        if feature.kind == "face":
            continue
        for index in body.faces_of_triangles(feature.face_indices):
            owned.add(int(index))
    hull = mesh.raw.convex_hull
    hull_points = np.asarray(hull.vertices)
    support = 0
    planes = 0
    for index, face in enumerate(faces):
        carrier = from_mesh._carrier_of_face(face)
        if carrier is None or carrier.kind != "plane":
            continue
        planes += 1
        axis = np.asarray(carrier.axis)
        offsets = (hull_points - np.asarray(carrier.origin)) @ axis
        # Stützebene: die ganze Hülle auf einer Seite (bis auf die Toleranz).
        if offsets.max() <= 0.01 or offsets.min() >= -0.01:
            support += 1
    lower, upper = body.bounds.minimum, body.bounds.maximum
    box = float(np.prod(np.asarray(upper) - np.asarray(lower)))
    removed = 0.0
    added = 0.0
    for feature in features.values():
        params = feature.params
        if feature.kind == "hole" and "diameter" in params and "depth" in params:
            removed += math.pi * (float(params["diameter"]) / 2.0) ** 2 * float(params["depth"])
        if feature.kind == "pin" and "diameter" in params and "height" in params:
            added += math.pi * (float(params["diameter"]) / 2.0) ** 2 * float(params["height"])
    candidate = box - removed + added
    print(
        f"{path.name}: faces {len(faces)} (planes {planes}, support {support}), "
        f"features {dict(kinds)}, faces owned by features {len(owned)}, "
        f"body {body.volume:.1f} box {box:.1f} candidate {candidate:.1f} "
        f"({(candidate - body.volume) / body.volume:+.2%})"
    )
