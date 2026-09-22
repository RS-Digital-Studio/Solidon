"""Prüft Facettierung, Ausreißer und polygonales Loch über den echten Kartenanschluss."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.perceive.maps import build
from app.core.types import SceneObject

results = []
for sections in (24, 96):
    raw = trimesh.creation.cylinder(radius=5.0, height=12.0, sections=sections)
    before_vertices, before_faces = raw.vertices.copy(), raw.faces.copy()
    mesh = MeshData(raw)
    features = detect(mesh)
    patches = [patch for feature in features.values() for patch in feature.surface_patches]
    rounded = [patch for patch in patches if patch.kind == "cylinder"]
    assert rounded and all(abs(patch.params["radius"] - 5.0) < 1e-9 for patch in rounded)
    analysis = build("deviation", SceneObject("obj_1", "Zylinder", mesh, features=features))
    assert analysis.unknown_count == 0 and analysis.maximum_interval is not None
    expected = 5.0 * (1.0 - math.cos(math.pi / sections))
    lower, upper = analysis.maximum_interval
    assert lower - 1e-9 <= expected <= upper + 1e-9
    assert upper - lower < 1e-6
    assert np.array_equal(raw.vertices, before_vertices) and np.array_equal(raw.faces, before_faces)
    results.append({"case": f"cylinder-{sections}", "expected_sag_mm": expected,
                    "maximum_interval": analysis.maximum_interval, "unknown": analysis.unknown_count})

raw = trimesh.creation.annulus(r_min=5.0, r_max=10.0, height=12.0, sections=6)
mesh = MeshData(raw)
features = detect(mesh)
assert not any(feature.kind == "hole" for feature in features.values())
assert all(patch.kind == "plane" for feature in features.values() for patch in feature.surface_patches)
analysis = build("deviation", SceneObject("obj_1", "Sechskantloch", mesh, features=features))
assert analysis.maximum_interval is not None and analysis.maximum_interval[1] < 1e-9
assert analysis.unknown_count == 0
results.append({"case": "hexagonal-hole", "features": [feature.kind for feature in features.values()],
                "maximum_interval": analysis.maximum_interval, "unknown": analysis.unknown_count})

raw = trimesh.creation.cylinder(radius=5.0, height=12.0, sections=96)
vertex = int(np.argmax(raw.vertices[:, 0] + raw.vertices[:, 2] * 0.001))
raw.vertices[vertex, :2] *= 1.004
before_vertices, before_faces = raw.vertices.copy(), raw.faces.copy()
mesh = MeshData(raw)
features = detect(mesh)
analysis = build("deviation", SceneObject("obj_1", "Ausreißer", mesh, features=features))
# Der echte Erkenner lehnt diesen Rundfit ab. Die Karte darf keinen neuen
# Ersatzfit erfinden oder den gesamten unbekannten Mantel als null rechnen.
assert not any(patch.kind == "cylinder" for feature in features.values() for patch in feature.surface_patches)
side = np.flatnonzero(np.ptp(raw.vertices[raw.faces][:, :, 2], axis=1) > 1.0)
assert len(side) == analysis.unknown_count == 192
assert all(math.isnan(analysis.values[int(index)]) for index in side)
assert len(analysis.known) == 192
assert analysis.maximum_interval is not None and analysis.maximum_interval[1] < 1e-9
actual_outlier = float(np.linalg.norm(raw.vertices[vertex, :2]) - 5.0)
assert abs(actual_outlier - 0.02) < 1e-12
assert np.array_equal(raw.vertices, before_vertices) and np.array_equal(raw.faces, before_faces)
results.append({"case": "radial-outlier-0.02mm", "actual_outlier_mm": actual_outlier,
                "accepted_round_fit": False, "known_planes_maximum": analysis.maximum_interval,
                "unknown_mantle_triangles": analysis.unknown_count})
Path(__file__).with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False))
