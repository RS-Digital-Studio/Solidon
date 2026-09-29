"""Sonde p6: Die Merkmalswege an einer schrägen Sackbohrung — Tiefe, Versetzen, Ändern, Langloch.

Aufruf: python p6_merkmalwege.py <baum>

Platte 60 × 40 × 10, um 17,5° um y gedreht (Float64), einmal zusätzlich auf
float32 gerundet wie eine STL. Die Sackbohrung Ø 6 × 4 entsteht direkt über
die Boolesche mit einem Werkzeug in Weltlage und Zugabe über der Mündung
(damit der Ausgangskörper in jedem Stand derselbe ist), dann erkannt. Je Weg:
Stufe, dicht, Teile, erster Treffer eines Strahls entlang der Achse von 1 mm
vor der Mündung (Tiefe + 1 heißt offen bis zum Boden), die erkannte Bohrung,
Ecken weiter als 12 mm von der Bohrung, die nicht bitgleich im Ergebnis
stehen, und bitgleich übernommene Dreiecke.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _baum  # noqa: E402

_baum.setup(sys.argv[1])

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.geom import attributes, lathe, transform  # noqa: E402
from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean  # noqa: E402
from app.core.geom.mesh import MeshData, as_mesh_data, ray_hit_distances  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.features import detect, forget_cache  # noqa: E402
from app.core.sketch.planes import frame_of  # noqa: E402
from tests.helpers import feature_operation  # noqa: E402

load_operations()
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")


def plate(angle: float, float32: bool) -> MeshData:
    body = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    body = transform.apply(body, transform.rotation("y", angle))
    if float32:
        raw = body.raw.copy()
        raw.vertices = np.asarray(raw.vertices, dtype=np.float32).astype(np.float64)
        body = MeshData.of(raw)
    return body


def bored(angle: float, float32: bool) -> tuple[MeshData, np.ndarray, np.ndarray]:
    body = plate(angle, float32)
    turn = transform.rotation("y", angle)
    normal = transform.turned(np.array([[0.0, 0.0, 1.0]]), turn)[0]
    point = transform.moved_points(np.array([[5.0, 3.0, 5.0]]), turn)[0]
    frame = frame_of(tuple(float(v) for v in normal), tuple(float(v) for v in point))
    tool = lathe.cylinder(radius=3.0, height=4.0 + BOOLEAN_OVERLAP, sections=48)
    tool.apply_translation((0.0, 0.0, (BOOLEAN_OVERLAP - 4.0) / 2.0))
    to_world = np.eye(4)
    to_world[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    to_world[:3, 3] = point
    transform.moved(tool, to_world)
    return boolean("difference", [body, MeshData.of(tool)], quality="fine", seed=1).mesh, normal, point


def rows(points: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(points, dtype=np.float64).view([("", float)] * 3).ravel()


def first_hit(mesh: MeshData, origin: np.ndarray, direction: np.ndarray) -> float:
    found = ray_hit_distances(np.asarray(mesh.raw.triangles), origin, direction)
    found = found[found > 0.0]
    return float(found.min()) if len(found) else float("nan")


def main() -> None:
    for float32 in (False, True):
        forget_cache()
        mesh, normal, point = bored(17.5, float32)
        features = detect(mesh)
        hole = next(f for f in features.values() if f.kind == "hole")
        print(
            f"Platte 17,5°{' float32' if float32 else ''}: {mesh.triangle_count} △, Bohrung {hole.id} "
            f"Ø {float(hole.params['diameter']):.4f} Tiefe {float(hole.params['depth']):.4f}",
            flush=True,
        )
        across = np.cross(normal, [0.0, 1.0, 0.0])
        across = across / np.linalg.norm(across)
        moved_to = np.asarray(hole.params["centre"], dtype=float) + across * 5.0
        ways = {
            "Tiefe 6": dict(diameter=6.0, depth=6.0, compensate=False),
            "Tiefe 10 (durch)": dict(diameter=6.0, depth=10.0, compensate=False),
            "Ø 8": dict(diameter=8.0, compensate=False),
            "versetzt 5": dict(diameter=6.0, compensate=False, x=float(moved_to[0]), y=float(moved_to[1]), z=float(moved_to[2])),
        }
        for label, params in ways.items():
            run(label, "resize_hole", mesh, features, hole, normal, point, params)
        run("Langloch 14", "slot_hole", mesh, features, hole, normal, point, dict(slot_length=14.0, slot_angle=0.0))


def run(label, name, mesh, features, hole, normal, point, params) -> None:
    try:
        result = feature_operation(name, mesh, features, hole, PROFILE, **params)
    except Exception as error:  # noqa: BLE001 — die Sonde will jeden Ausgang sehen
        print(f"  {label:<16} Fehler {type(error).__name__}: {error}", flush=True)
        return
    after = as_mesh_data(result.outputs[0].mesh)
    centre = np.asarray(hole.params["centre"], dtype=float)
    if "x" in params:
        centre = np.array([params["x"], params["y"], params["z"]])
    # Mündung der neuen Stelle: die Achse durch die Mitte, 1 mm vor der Fläche.
    axis = normal
    offset = float((point - centre) @ axis)
    origin = centre + axis * (offset + 1.0)
    before = np.asarray(mesh.raw.vertices)
    far = np.linalg.norm(before - np.asarray(hole.params["centre"]), axis=1) > 12.0
    if "x" in params:
        far &= np.linalg.norm(before - centre, axis=1) > 12.0
    moved = int((~np.isin(rows(before[far]), rows(np.asarray(after.raw.vertices)))).sum())
    kept = int((attributes._same_triangles(mesh.raw, after.raw) >= 0).sum())
    holes = [
        (f.kind, round(float(f.params["diameter"]), 3), round(float(f.params.get("depth", 0.0)), 3), bool(f.params.get("through")))
        for f in detect(after).values()
        if f.kind in ("hole", "slot")
    ]
    codes = sorted({f.code for f in result.findings})
    print(
        f"  {label:<16} Stufe {result.solver.strategy if result.solver else None!s:<8} dicht {after.raw.is_watertight!s:<5} "
        f"Teile {after.component_count} △ {after.triangle_count:>5} (bitgleich {kept}) Strahl {first_hit(after, origin, -axis):.6f} "
        f"fern versetzt {moved} Merkmale {holes} Befunde {codes}",
        flush=True,
    )


if __name__ == "__main__":
    main()
