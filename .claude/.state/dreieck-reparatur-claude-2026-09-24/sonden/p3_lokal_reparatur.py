"""Sonde 3: Lokale Erkennung großer Netze nach einer Reparatur.

Der große Weg der Auswertung (`FEATURE_LIMIT_TRIANGLES` wie in den Tests auf 1
gesetzt) misst nach jeder Operation die bekannten Merkmale lokal nach
(`local.detect_known`). Gefragt wird: Übersteht eine lokal erkannte Bohrung
einen Reparaturschritt, der das Netz an anderer Stelle oder dicht neben ihr
ändert, mit Namen und Maß — oder bricht der Schritt mit einem lokalen Fehler ab?
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import traceback
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.geom.repair import repair  # noqa: E402
from app.core.perceive.local import detect_local  # noqa: E402
from app.core.types import Operation, SceneObject  # noqa: E402

evaluation = importlib.import_module("app.core.scene.evaluate")
OUT = Path(__file__).with_suffix(".txt")
DATA = Path(r"F:\3D Druck\tests\data")


def blind_cylinder(sections: int = 64, levels: int = 2) -> MeshData:
    """Wie ``tests/test_local_detection.blind_cylinder``, mit wählbarer Feinheit."""
    spec = json.loads((DATA / "local_detection.json").read_text(encoding="utf-8"))
    count = sections
    angles = np.arange(count) * (2 * np.pi / count)
    radial = np.column_stack((np.cos(angles), np.sin(angles)))
    outer = np.empty((levels + 1, count, 3))
    outer[:, :, :2] = radial * spec["outer_radius"]
    outer[:, :, 2] = np.linspace(0, spec["height"], levels + 1)[:, None]
    top = np.column_stack((radial * spec["bore_radius"], np.full(count, spec["height"])))
    floor_z = spec["height"] - spec["bore_depth"]
    floor = np.column_stack((radial * spec["bore_radius"], np.full(count, floor_z)))
    vertices = np.vstack((outer.reshape(-1, 3), top, floor, [[0, 0, 0], [0, 0, floor_z]]))
    ti, bi, ci = (levels + 1) * count, (levels + 2) * count, (levels + 3) * count
    k, following = np.arange(count), np.roll(np.arange(count), -1)
    lower = np.arange(levels)[:, None] * count + k
    after = np.arange(levels)[:, None] * count + following
    faces = np.vstack(
        (
            np.stack((lower, after, lower + count), axis=-1).reshape(-1, 3),
            np.stack((after, after + count, lower + count), axis=-1).reshape(-1, 3),
            np.column_stack((levels * count + k, levels * count + following, ti + k)),
            np.column_stack((levels * count + following, ti + following, ti + k)),
            np.column_stack((following, k, np.full(count, ci))),
            np.column_stack((ti + k, ti + following, bi + k)),
            np.column_stack((ti + following, bi + following, bi + k)),
            np.column_stack((bi + k, bi + following, np.full(count, ci + 1))),
        )
    )
    return MeshData.of(trimesh.Trimesh(vertices, faces, process=False))


def bore_seed(mesh: MeshData):
    triangles = np.asarray(mesh.raw.triangles)
    radial = np.linalg.norm(triangles[:, :, :2], axis=2)
    face = int(
        np.flatnonzero(
            np.all(np.isclose(radial, 3), axis=1)
            & (triangles[:, :, 2].max(axis=1) > 19)
            & (triangles[:, :, 2].min(axis=1) < 16)
        )[0]
    )
    return (
        face,
        tuple(float(v) for v in mesh.raw.triangles_center[face]),
        tuple(float(v) for v in mesh.raw.face_normals[face]),
    )


def without(mesh: MeshData, gone) -> MeshData:
    keep = np.ones(mesh.triangle_count, dtype=bool)
    keep[list(gone)] = False
    return MeshData.of(
        trimesh.Trimesh(np.asarray(mesh.raw.vertices), np.asarray(mesh.raw.faces)[keep],
                        process=False)
    )


def describe(features) -> str:
    rows = []
    for name, feature in sorted(features.items()):
        params = feature.params
        dims = ",".join(
            f"{key}={float(params[key]):.3f}"
            for key in ("diameter", "depth", "area", "local_search_radius")
            if isinstance(params.get(key), int | float) and not isinstance(params.get(key), bool)
        )
        rows.append(f"{name}:{feature.kind}[{dims}] n={len(feature.face_indices)}")
    return "; ".join(rows)


def main() -> None:
    evaluation.FEATURE_LIMIT_TRIANGLES = 1
    with OUT.open("w", encoding="utf-8") as out:
        for sections, levels in ((64, 2), (256, 16)):
            mesh = blind_cylinder(sections, levels)
            face, point, normal = bore_seed(mesh)
            for radius in (8.0, 20.0):
                known = detect_local(mesh, point, normal=normal, radius=radius,
                                     seed_faces=(face,)).features
                out.write(f"\n# Zylinder {sections}x{levels} ({mesh.triangle_count} Dreiecke), "
                          f"Radius {radius}: bekannt {describe(known)}\n")
                triangles = np.asarray(mesh.raw.triangles)
                centres = triangles.mean(axis=1)
                radial = np.linalg.norm(centres[:, :2], axis=1)
                top = np.isclose(triangles[:, :, 2], 20.0).all(axis=1)
                cases = {
                    "Mantel weit weg (x=100) zwei Dreiecke fehlen": list(np.flatnonzero(
                        (radial > 99) & (centres[:, 0] > 90))[:2]),
                    "Deckel am Bohrungsrand ein Dreieck fehlt": list(np.flatnonzero(
                        top & (radial < 6))[:1]),
                    "Deckel am Bohrungsrand zwei Nachbarn fehlen": list(np.flatnonzero(
                        top & (radial < 6))[:2]),
                    "Bohrungswand ein Dreieck fehlt": [face],
                }
                for title, gone in cases.items():
                    damaged = without(mesh, gone)
                    fixed = repair(damaged)
                    try:
                        output = evaluation._with_features(
                            SceneObject("obj_1", "Körper", fixed.mesh),
                            dict(known),
                            Operation(3, "repair"),
                            lambda question, choices: (_ for _ in ()).throw(
                                AssertionError(f"Frage: {question}")),
                            findings := [],
                        )
                        out.write(
                            f"  {title}: repariert={fixed.changed} "
                            f"{[entry.code for entry in fixed.findings]} -> "
                            f"{describe(output.features)} | Befunde "
                            f"{[entry.code for entry in findings]}\n"
                        )
                    except Exception as problem:  # Sonde: jede Ausnahme mitschreiben
                        out.write(
                            f"  {title}: repariert={fixed.changed} -> AUSNAHME "
                            f"{type(problem).__name__}: {getattr(problem, 'constraint', '')} "
                            f"{str(problem)[:160]!r}\n"
                        )
                    out.flush()


if __name__ == "__main__":
    main()
