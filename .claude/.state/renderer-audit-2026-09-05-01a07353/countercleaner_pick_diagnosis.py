"""Prüft gespeicherte Countercleaner-Treffer ohne Qt, Renderer oder neue Erkennung."""

from __future__ import annotations

import argparse
import ast
import json
import math
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from app.core.geom.mesh import distance_to_triangles
from app.core.units import EPS_GEOM


BASE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--current", action="store_true")
args = parser.parse_args()
SOURCE = (
    Path.cwd() / "app/ui/viewport.py"
    if args.current
    else BASE / "final-source-v6/app/ui/viewport.py"
)
CASE = BASE / "preflight-v6/gfx/file-18"
result = json.loads((CASE / "result.json").read_text(encoding="utf-8"))
surface = next(check for check in result["checks"] if check["label"] == "Oberflächenklicks")
held = next(
    check for check in result["checks"] if check["label"] == "Freier Körperzug: gehaltene Vorschau"
)
camera = held["before"]["camera"]
eye = np.asarray(camera["position"])
focus = np.asarray(camera["focal_point"])
cache = next(CASE.rglob("0310a09dd646502d4f4a510d1e05c6f6/objects.json"))
data = json.loads(cache.read_text(encoding="utf-8"))
assert np.array_equal(data["transform"], np.eye(4))
entry_data = data["objects"][0]
packed = np.load(cache.parent / entry_data["mesh"])
vertices, faces = packed["vertices"], packed["faces"]
entry = SimpleNamespace(
    mesh=SimpleNamespace(raw=SimpleNamespace(vertices=vertices, faces=faces)),
    features={key: SimpleNamespace(**value) for key, value in entry_data["features"].items()},
)
tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
viewport = next(
    node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Viewport"
)
methods = {
    "_prepared_bores",
    "_bore_aim",
    "_feature_at",
    "_feature_hit",
    "_feature_inside",
    "_prepared_features",
}
nodes = [
    node
    for node in tree.body
    if isinstance(node, ast.FunctionDef) and node.name in {"bore_span", "_is_opening_feature"}
]
nodes += [
    node for node in viewport.body if isinstance(node, ast.FunctionDef) and node.name in methods
]
module = ast.Module(
    body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *nodes,
    ],
    type_ignores=[],
)
ast.fix_missing_locations(module)
namespace = {
    "math": math,
    "EPS_GEOM": EPS_GEOM,
    "distance_to_triangles": distance_to_triangles,
    "_BoreTarget": namedtuple("BoreTarget", "feature_id centre line radius bounds"),
    "_SelectionHit": lambda *args, **kwargs: SimpleNamespace(args=args, **kwargs),
}
exec(compile(module, str(SOURCE), "exec"), namespace)
probe = SimpleNamespace(
    _result=SimpleNamespace(scene=SimpleNamespace(objects={entry_data["id"]: entry})),
    _feature_bores={},
    _feature_geometry={},
    _selected=entry_data["id"],
    _feature_reach=lambda _: max(0.5, float(np.linalg.norm(np.ptp(vertices, axis=0))) * 0.01),
    _in_view=lambda *_: True,
    _in_pick_view=lambda *_: True,
    _shown_offset=lambda *_: np.zeros(3),
    _object_at=lambda *_: entry_data["id"],
    _feature_on_cell=lambda *_: None,
)
for method in methods:
    setattr(
        probe,
        method,
        lambda *values, _method=method, **kwargs: namespace[_method](probe, *values, **kwargs),
    )
probe._hit_at = lambda point: (
    probe._selection_hit
    if (
        probe._selection_hit is not None
        and math.dist(probe._selection_hit.args[1], point) <= EPS_GEOM
    )
    else None
)
targets = probe._prepared_bores(entry_data["id"])
rows = []
for hit in surface["hits"]:
    if hit.get("feature_matches") is not False:
        continue
    expected = hit["expected_cpu"]
    point = np.asarray(expected["point"])
    distances = sorted(
        (
            float(distance_to_triangles(vertices[faces[feature.face_indices]], point)),
            identifier,
        )
        for identifier, feature in entry.features.items()
        if feature.face_indices
    )
    ray_rows = []
    for projection in ("perspective", "parallel"):
        probe._selection_hit = None
        direction = point - eye if projection == "perspective" else focus - eye
        direction = direction / np.linalg.norm(direction)
        origin = (
            eye if projection == "perspective" else point - direction * np.linalg.norm(point - eye)
        )
        until = float((point - origin) @ direction)
        aim = namespace["_bore_aim"](probe, tuple(origin), tuple(direction), until, view_space=True)
        candidates = []
        for identifier, centre, line, radius, bounds in targets:
            span = namespace["bore_span"](origin, direction, centre, line, radius, bounds)
            if span is not None and span[1] > 0 and span[0] <= until + EPS_GEOM:
                candidates.append(
                    {
                        "feature": identifier,
                        "kind": entry.features[identifier].kind,
                        "recess": entry.features[identifier].params.get("recess"),
                        "span": span,
                        "before_surface_mm": until - span[0],
                    }
                )
        ray_rows.append(
            {
                "projection": projection,
                "aim": aim,
                "selected": getattr(getattr(probe, "_selection_hit", None), "feature_id", None),
                "feature_at": probe._feature_at(aim if aim is not None else tuple(point)),
                "candidates": sorted(candidates, key=lambda item: item["span"][0]),
            }
        )
    rows.append(
        {
            "pixel": hit["pixel"],
            "original_cell": expected["cell"],
            "original_point": expected["point"],
            "recorded_lod_cell": hit["cell"],
            "recorded_ui_feature": hit["feature"],
            "nearest_original_features": distances[:4],
            "ray_checks": ray_rows,
        }
    )
output = {
    "source": str(SOURCE),
    "cache": str(cache),
    "camera": camera,
    "camera_origin": "Gespeicherte Kamera nach späterem Projektionswechsel; beide Projektionsarten geprüft",
    "lod_point_limit": "Native Ergebnisdatei enthält den LOD-Zellindex, aber keinen LOD-Trefferpunkt",
    "rows": rows,
}
print(json.dumps(output, ensure_ascii=False, indent=2))
(
    BASE
    / (
        "countercleaner_pick_diagnosis_fixed.json"
        if args.current
        else "countercleaner_pick_diagnosis.json"
    )
).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
