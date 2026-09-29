"""Sonde p5: ``prepare.drill`` mit Normale an achsparallelen, gedrehten und float32-Platten.

Aufruf: python p5_drill_platten.py <baum>

Dieselben Körper wie p4, diesmal über die Operation selbst (``prepare.drill``
mit ``normal``), damit alter und neuer Stand dieselbe Frage bekommen:
Sackloch 4 mm, Tiefe gleich Plattendicke (10 mm, der Boden fällt in die
Unterseite), durchgehend (Tiefe 0), Mittenanker mit 4 mm, Langloch und
Aufweitung. Je Fall: Stufe, dicht, Teile, abgetragenes Volumen, erster
Treffer eines Strahls von 1 mm vor der Mündung entlang -n (5 heißt offen bis
zum Boden, nan heißt durch), Nadeln, erkannte Bohrungen, Ecken des Eingangs,
die nicht bitgleich im Ergebnis stehen (weit weg vom Loch, > 4 mm).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _baum  # noqa: E402

_baum.setup(sys.argv[1])

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom import transform  # noqa: E402
from app.core.geom.mesh import MeshData, ray_hit_distances  # noqa: E402
from app.core.geom.prepare import drill  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402

PROFILE = profiles.make_profile("centauri-carbon-2", "petg")


def plate(angle: float, float32: bool) -> MeshData:
    body = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    if angle:
        body = transform.apply(body, transform.rotation("y", angle))
    if float32:
        raw = body.raw.copy()
        raw.vertices = np.asarray(raw.vertices, dtype=np.float32).astype(np.float64)
        body = MeshData.of(raw)
    return body


def top_frame(angle: float):
    turn = transform.rotation("y", angle) if angle else np.eye(4)
    normal = transform.turned(np.array([[0.0, 0.0, 1.0]]), turn)[0]
    point = transform.moved_points(np.array([[5.0, 3.0, 5.0]]), turn)[0]
    return normal, point


def needles(mesh: MeshData) -> int:
    triangles = np.asarray(mesh.raw.triangles)
    edges = np.linalg.norm(triangles[:, [1, 2, 0]] - triangles, axis=2)
    doubled = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
    return int((doubled / np.maximum(edges.max(axis=1), 1e-300) < 1e-9).sum())


def first_hit(mesh: MeshData, origin: np.ndarray, direction: np.ndarray) -> float:
    found = ray_hit_distances(np.asarray(mesh.raw.triangles), origin, direction)
    found = found[found > 0.0]
    return float(found.min()) if len(found) else float("nan")


def rows(points: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(points, dtype=np.float64).view([("", float)] * 3).ravel()


def far_moved(body: MeshData, mesh: MeshData, point: np.ndarray) -> int:
    before = np.asarray(body.raw.vertices, dtype=np.float64)
    far = np.sqrt(((before - point) ** 2).sum(axis=1)) > 12.0
    return int((~np.isin(rows(before[far]), rows(np.asarray(mesh.raw.vertices)))).sum())


CASES = {
    "Sackloch 4": dict(depth=4.0),
    "Tiefe = Dicke": dict(depth=10.0),
    "durch": dict(depth=0.0),
    "Mitte 4": dict(depth=4.0, anchor="centre"),
    "Langloch 4": dict(depth=4.0, slot_length=14.0),
    "Aufweitung 4": dict(depth=6.0, widening_diameter=10.0, widening_depth=2.0),
}


def main() -> None:
    for angle in (0.0, 17.5, 33.0):
        for float32 in (False, True):
            body = plate(angle, float32)
            normal, point = top_frame(angle)
            print(f"Platte gedreht {angle}°{' float32' if float32 else ''}", flush=True)
            for label, extra in CASES.items():
                try:
                    result = drill(
                        body,
                        position=tuple(float(v) for v in point),
                        axis="z",
                        normal=tuple(float(v) for v in normal),
                        diameter=6.0,
                        profile=PROFILE,
                        compensate=False,
                        seed=1,
                        **extra,
                    )
                except Exception as error:  # noqa: BLE001 — die Sonde will jeden Ausgang sehen
                    print(f"  {label:<14} Fehler {type(error).__name__}: {error}", flush=True)
                    continue
                mesh = result.mesh
                holes = [f for f in detect(mesh).values() if f.kind in ("hole", "slot")]
                described = [
                    (f.kind, round(float(f.params["diameter"]), 3), round(float(f.params.get("depth", 0.0)), 3), bool(f.params.get("through")))
                    for f in holes
                ]
                print(
                    f"  {label:<14} Stufe {result.solver.strategy:<8} dicht {mesh.raw.is_watertight!s:<5} "
                    f"Teile {mesh.component_count} △ {mesh.triangle_count:>5} Volumen ab {body.volume - mesh.volume:.9f} "
                    f"Strahl {first_hit(mesh, point + normal, -normal):.9f} Nadeln {needles(mesh)} "
                    f"fern versetzt {far_moved(body, mesh, point)} Merkmale {described}",
                    flush=True,
                )


if __name__ == "__main__":
    main()
