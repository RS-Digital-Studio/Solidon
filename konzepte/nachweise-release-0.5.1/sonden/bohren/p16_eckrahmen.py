"""Sonde p16: Versetzt *Verrunden*/*Fase* an einer gemischten Ecke Ecken weit weg davon?

Aufruf: python p16_eckrahmen.py <baum>

``edges._placed_edge_work`` legt den ganzen Körper in den Rahmen der Ecke und
zurück. Körper: das L-Profil aus ``tests/test_mesh_edges.py`` (20 × 20 × 20,
Kerbe 10 × 10), dazu eine Kugel Ø 6 an der fernen Ecke (Ecken außerhalb jeder
Ebene), einmal achsparallel, einmal um 31° um (2, 1, -3) gedreht und
verschoben. Bearbeitet werden die drei Kanten am gemischten Knoten
(10, 10, 20). Gezählt: Ecken des Eingangs weiter als 8 mm vom Knoten, die im
Ergebnis nicht bitgleich stehen, und Ecken des Ergebnisses dort, die im
Eingang fehlen; bitgleich übernommene Dreiecke.
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
from shapely.geometry import Polygon  # noqa: E402

from app.core.geom import attributes  # noqa: E402
from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom.edges import bevel_edges, edge_key, edges_of, round_edges  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402


def rows(points: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(points, dtype=np.float64).view([("", float)] * 3).ravel()


def body(turned: bool) -> tuple[MeshData, np.ndarray]:
    profile = Polygon([(0, 0), (20, 0), (20, 10), (10, 10), (10, 20), (0, 20)])
    raw = trimesh.creation.extrude_polygon(profile, 20.0)
    knob = trimesh.creation.icosphere(subdivisions=3, radius=3.0)
    knob.vertices = np.asarray(knob.vertices) + np.array([2.0, 2.0, 0.0])
    mesh = boolean("union", [MeshData.of(raw), MeshData.of(knob)]).mesh
    frame = np.eye(4)
    if turned:
        frame = trimesh.transformations.rotation_matrix(math.radians(31.0), (2.0, 1.0, -3.0))
        frame[:3, 3] = (-15.0, 10.0, 7.0)
        turned_raw = mesh.raw.copy()
        turned_raw.apply_transform(frame)
        mesh = MeshData.of(turned_raw)
    return mesh, trimesh.transform_points([[10.0, 10.0, 20.0]], frame)[0]


def main() -> None:
    for turned in (False, True):
        for rounded in (False, True):
            mesh, point = body(turned)
            touching = [
                entry
                for entry in edges_of(mesh)
                if min(math.dist(point, entry.points[0]), math.dist(point, entry.points[-1])) < 1e-6
            ]
            edit = round_edges if rounded else bevel_edges
            result = edit(mesh, 3.0, "named", [edge_key(entry) for entry in touching[:3]])
            after = result.mesh
            before = np.asarray(mesh.raw.vertices)
            now = np.asarray(after.raw.vertices)
            lines = [np.asarray(entry.points, dtype=float) for entry in touching[:3]]

            def to_edges(points: np.ndarray) -> np.ndarray:
                best = np.full(len(points), np.inf)
                for line in lines:
                    for start, end in zip(line[:-1], line[1:], strict=True):
                        step = end - start
                        share = np.clip(((points - start) @ step) / float(step @ step), 0.0, 1.0)
                        best = np.minimum(best, np.linalg.norm(points - (start + share[:, None] * step), axis=1))
                return best

            # Außerhalb des Schnitts: weiter als Maß plus 1 mm von jeder bearbeiteten Kante.
            far_before = before[to_edges(before) > 4.0]
            far_now = now[to_edges(now) > 4.0]
            missing = int((~np.isin(rows(far_before), rows(now))).sum())
            foreign = int((~np.isin(rows(far_now), rows(before))).sum())
            kept = int((attributes._same_triangles(mesh.raw, after.raw) >= 0).sum())
            print(
                f"{'gedreht' if turned else 'achsparallel'} {'Verrunden' if rounded else 'Fase'}: "
                f"{len(touching)} Kanten am Knoten, Stufe {result.solver.strategy}, "
                f"ferne Ecken {len(far_before)}, davon fehlen {missing}, neue ferne Ecken {foreign}, "
                f"bitgleiche Dreiecke {kept} von {after.triangle_count}, Volumen {after.volume:.6f}",
                flush=True,
            )


if __name__ == "__main__":
    main()
