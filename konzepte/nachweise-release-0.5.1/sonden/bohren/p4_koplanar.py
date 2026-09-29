"""Sonde p4: Wie rechnet der Kern ein Werkzeug in Weltlage, dessen Enden fast in einer Körperfläche liegen?

Aufruf: python p4_koplanar.py <baum>

Eine Platte 60 × 40 × 10, einmal achsparallel, einmal um 17,5° und um 33° um y
gedreht (``transform.apply``, Float64 gerundet), einmal zusätzlich auf float32
gerundet wie eine STL. Gebohrt wird Ø 6 von der Oberseite:

* ``bündig``: Werkzeug von der Mündung (0) bis -4, in Weltlage gelegt;
* ``Zugabe``: Mündung um ``BOOLEAN_OVERLAP`` über der Fläche;
* ``durch bündig``: bis -10, der Boden fällt in die Unterseite;
* ``versetzt k``: Mündung um k·ULP der Lage entlang der Normalen verschoben.

Gemessen: Stufe, dicht, Teile, abgetragenes Volumen gegen das Vieleck mal Tiefe,
ob die Mündung offen ist (Strahl von außen entlang -n trifft erst am Boden),
Dreiecke mit Höhe unter 1e-9 mm (Nadeln) und die erkannte Bohrung.
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

from app.core import units  # noqa: E402
from app.core.geom import lathe, transform  # noqa: E402
from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402
from app.core.sketch.planes import frame_of  # noqa: E402

SECTIONS = 48
RADIUS = 3.0
POLYGON = SECTIONS / 2.0 * RADIUS * RADIUS * math.sin(2.0 * math.pi / SECTIONS)


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


def tool(normal: np.ndarray, point: np.ndarray, low: float, high: float) -> MeshData:
    frame = frame_of(tuple(float(v) for v in normal), tuple(float(v) for v in point))
    cylinder = lathe.cylinder(radius=RADIUS, height=high - low, sections=SECTIONS)
    cylinder.apply_translation((0.0, 0.0, (high + low) / 2.0))
    to_world = np.eye(4)
    to_world[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    to_world[:3, 3] = point
    transform.moved(cylinder, to_world)
    return MeshData.of(cylinder)


def needles(mesh: MeshData) -> int:
    triangles = np.asarray(mesh.raw.triangles)
    edges = np.linalg.norm(triangles[:, [1, 2, 0]] - triangles, axis=2)
    doubled = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
    height = doubled / np.maximum(edges.max(axis=1), 1e-300)
    return int((height < 1e-9).sum())


def first_hit(mesh: MeshData, origin: np.ndarray, direction: np.ndarray) -> float:
    from app.core.geom.mesh import ray_hit_distances

    found = ray_hit_distances(np.asarray(mesh.raw.triangles), origin, direction)
    found = found[found > 0.0]
    return float(found.min()) if len(found) else float("nan")


def report(label: str, body: MeshData, normal: np.ndarray, point: np.ndarray, low: float, high: float, depth: float) -> None:
    outcome = boolean("difference", [body, tool(normal, point, low, high)], quality="fine", seed=1)
    mesh = outcome.mesh
    removed = body.volume - mesh.volume
    hit = first_hit(mesh, point + normal * 1.0 + np.array([0.3, 0.2, 0.0]) * 0.0, -normal)
    holes = [f for f in detect(mesh).values() if f.kind == "hole"]
    described = [
        (round(float(f.params["diameter"]), 4), round(float(f.params.get("depth", 0.0)), 4), bool(f.params.get("through")))
        for f in holes
    ]
    print(
        f"  {label:<16} Stufe {outcome.solver.strategy:<8} dicht {mesh.raw.is_watertight!s:<5} "
        f"Teile {mesh.component_count} △ {mesh.triangle_count:>5} Volumen ab {removed:.9f} "
        f"(Soll {POLYGON * depth:.9f}, Abw {removed - POLYGON * depth:+.2e}) Strahl {hit:.9f} "
        f"Nadeln {needles(mesh)} Bohrungen {described}",
        flush=True,
    )


def main() -> None:
    for angle in (0.0, 17.5, 33.0):
        for float32 in (False, True):
            body = plate(angle, float32)
            normal, point = top_frame(angle)
            print(f"Platte gedreht {angle}°{' float32' if float32 else ''}: Normale {normal.tolist()}", flush=True)
            report("bündig", body, normal, point, -4.0, 0.0, 4.0)
            report("Zugabe", body, normal, point, -4.0, BOOLEAN_OVERLAP, 4.0)
            report("durch bündig", body, normal, point, -10.0, 0.0, 10.0)
            report("durch Zugabe", body, normal, point, -10.0 - BOOLEAN_OVERLAP, BOOLEAN_OVERLAP, 10.0)
            step = float(np.spacing(np.abs(point).max()))
            for k in (-4, -1, 1, 4):
                report(f"versetzt {k:+d} ULP", body, normal, point + normal * (k * step), -4.0, 0.0, 4.0)


if __name__ == "__main__":
    main()
