"""Sonde r6_lippe_messen: Steht die Lippe nach der zweiten Handlung an einer gekippten Tasche noch?

Aufruf: python r6_lippe_messen.py <baum>

Gemessen wird an der bekannten Lage, nicht an den Kennzahlen der Merkmale (die
erkannte Mitte am exakten Körper liegt anders als die gesetzte): Tasche Ø 8,25
um (0, 0, 8,5), Mündung z = 10, Lippe 0,4 mm hoch mit Öffnung 7,95, um X
gekippt. Je Richtung um die Achse der freie Halbmesser 0,2 mm unter der
Mündung (Strahl von 3,8 bis 4,4 mm, Schritt 0,005) — nur Richtungen, deren
Strahl ganz unter der Deckfläche liegt. Lippe ganz: 4,05; ohne Lippe: 4,125.
Dazu der freie Halbmesser 1,5 mm unter der Mündung (Tasche: 4,125).
"""

from __future__ import annotations

import math
import sys

import _baum

TREE = _baum.setup(sys.argv[1])
_baum.activation_free()

import numpy as np  # noqa: E402

import common  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402

POCKET = "magnet_pocket_pocket_1"
PIVOT = np.array([0.0, 0.0, 8.5])


def rotation_x(angle: float) -> np.ndarray:
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def inside(mesh, points):
    from app.core.geom.mesh import on_surface
    from app.core.geom.prepare import surface_index_of

    data = as_mesh_data(mesh)
    closest, _, at = on_surface(data.raw, points, index=surface_index_of(data))
    normals = np.asarray(data.raw.face_normals, dtype=np.float64)[at]
    return np.einsum("ij,ij->i", points - closest, normals) < 0.0


def free_radius(mesh, mouth, axis, t: float) -> str:
    axis = np.asarray(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = np.cross(axis, helper)
    first /= np.linalg.norm(first)
    second = np.cross(axis, first)
    radii = np.arange(3.8, 4.4001, 0.005)
    found = []
    for angle in np.linspace(0.0, 2.0 * math.pi, 72, endpoint=False):
        direction = math.cos(angle) * first + math.sin(angle) * second
        points = mouth + t * axis + np.outer(radii, direction)
        if points[:, 2].max() > 9.9:
            continue
        solid = inside(mesh, points)
        hit = np.flatnonzero(solid)
        found.append(float(radii[hit[0]]) if len(hit) else float("inf"))
    if not found:
        return "keine Richtung"
    values = np.asarray(found)
    return (
        f"{len(values)} Richtungen: min {values.min():.3f} Median {np.median(values):.3f} "
        f"max {values.max():.3f}"
    )


def measure(entry, mouths) -> str:
    rows = []
    for label, mouth, axis in mouths:
        rows.append(
            f"{label}: Lippe {free_radius(entry.mesh, mouth, axis, -0.2)} | "
            f"Tasche {free_radius(entry.mesh, mouth, axis, -1.5)}"
        )
    return "\n         ".join(rows)


def placed(angle: float, shift=(0.0, 0.0, 0.0)):
    matrix = rotation_x(angle)
    mouth = matrix @ (np.array([0.0, 0.0, 10.0]) - PIVOT) + PIVOT + np.asarray(shift)
    axis = matrix @ np.array([0.0, 0.0, 1.0])
    return mouth, axis


def run_case(exact: bool, steps):
    project, history = common.pocket_project(exact)
    common.run(project)
    for op, params in steps:
        common.apply(history, op, params)
    return common.run(project)


def main() -> None:
    for exact in (False, True):
        label = "exakt" if exact else "Netz"
        print(f"##### {label}", flush=True)
        tilt = ("rotate_feature", {"at_feature": POCKET, "axis": "x", "angle": 10.0})
        cases = [
            ("gerade", [], [("Tasche", *placed(0.0))]),
            ("gekippt 10°", [tilt], [("Tasche", *placed(10.0))]),
            (
                "gekippt 20° direkt",
                [("rotate_feature", {"at_feature": POCKET, "axis": "x", "angle": 20.0})],
                [("Tasche", *placed(20.0))],
            ),
            ("10° + 10°", [tilt, tilt], [("Tasche", *placed(20.0))]),
            (
                "gekippt, versetzt 3 mm X",
                [tilt, ("move_feature", {"at_feature": POCKET, "x": 3.0, "y": 0.0, "z": 8.5})],
                [("Tasche", *placed(10.0, (3.0, 0.0, 0.0)))],
            ),
            (
                "gekippt, verdoppelt 10 mm X",
                [tilt, ("duplicate_feature", {"at_feature": POCKET, "x": 10.0, "y": 0.0, "z": 8.5})],
                [("Tasche", *placed(10.0)), ("Kopie", *placed(10.0, (10.0, 0.0, 0.0)))],
            ),
            (
                "gekippt, Bohrung ändern Einlauf 8,5",
                [tilt, ("resize_hole", {"at_feature": POCKET, "diameter": 8.5, "entrance_mode": "follow"})],
                [("Tasche", *placed(10.0))],
            ),
            (
                "gekippt, Bohrung ändern nur 8,5",
                [tilt, ("resize_hole", {"at_feature": POCKET, "diameter": 8.5, "entrance_mode": "keep"})],
                [("Tasche", *placed(10.0))],
            ),
            (
                "gekippt, Bohrung ändern nur 7,8",
                [tilt, ("resize_hole", {"at_feature": POCKET, "diameter": 7.8, "entrance_mode": "keep"})],
                [("Tasche", *placed(10.0))],
            ),
        ]
        for text, steps, mouths in cases:
            try:
                result = run_case(exact, steps)
            except Exception as error:  # noqa: BLE001 — die Sonde zählt
                print(f"   {text}: Anlegen scheiterte: {type(error).__name__}: {error}", flush=True)
                continue
            entry = result.scene.objects.get("obj_1")
            if entry is None or not result.complete:
                print(f"   {text}: vollständig {result.complete}; Halt {common.stops(result)}", flush=True)
                continue
            twin = as_mesh_data(entry.mesh)
            print(f"   {text}: V {twin.volume:.3f} dicht {twin.is_watertight}", flush=True)
            print(f"         {measure(entry, mouths)}", flush=True)
            for row in common.warnings(result):
                print(f"         {row}", flush=True)


if __name__ == "__main__":
    main()
