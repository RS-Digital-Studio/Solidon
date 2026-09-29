"""Sonde r5_nach_dem_kippen: Was geschieht mit der Lippe bei der zweiten Handlung nach dem Kippen?

Aufruf: python r5_nach_dem_kippen.py <baum>

Nach *Merkmal drehen* (Tasche, X, 10°) liest die Erkennung die gekippte Lippe
am exakten Körper als Kegel ohne ``narrowing`` (r3_drehen_wt1.txt). Die
Kettenhandlungen fragen genau dieses Flag (``_narrows_outward``). Gefragt:
Macht eine zweite Handlung an der gekippten Tasche aus der Lippe eine Senkung?

Je Kern: die Merkmale nach dem Kippen und ihre Zeilen im Merkmalfenster,
danach je zweiter Handlung Volumen, Dichtheit, Lippenanteil (Ring r = 4,05 mm
um die Achse der Tasche, 0,2 mm unter der Mündung — nur Punkte unter der
Deckfläche gezählt, 1,0 heißt: die Lippe steht ringsum) und die Merkmale.
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
from app.core.perceive.actions import actions_for  # noqa: E402

POCKET = "magnet_pocket_pocket_1"


def inside(mesh, points):
    from app.core.geom.mesh import on_surface
    from app.core.geom.prepare import surface_index_of

    data = as_mesh_data(mesh)
    closest, _, at = on_surface(data.raw, points, index=surface_index_of(data))
    normals = np.asarray(data.raw.face_normals, dtype=np.float64)[at]
    return np.einsum("ij,ij->i", points - closest, normals) < 0.0


def lip_share(mesh, pocket) -> str:
    """Anteil des Rings in der Lippenzone, der im Material liegt."""
    axis = np.asarray(pocket.params["axis"], dtype=float)
    axis /= np.linalg.norm(axis)
    mouth = np.asarray(pocket.params["centre"], dtype=float) + 1.5 * axis
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = np.cross(axis, helper)
    first /= np.linalg.norm(first)
    second = np.cross(axis, first)
    angles = np.linspace(0.0, 2.0 * math.pi, 144, endpoint=False)
    points = (
        mouth
        - 0.2 * axis
        + 4.05 * (np.outer(np.cos(angles), first) + np.outer(np.sin(angles), second))
    )
    below = points[points[:, 2] < 9.95]
    if not len(below):
        return "keine Punkte"
    share = float(np.count_nonzero(inside(mesh, below))) / len(below)
    # Gegenprobe: Ring im Schaft (Tasche frei, 1,5 mm unter der Mündung).
    shaft = mouth - 1.5 * axis + 4.05 * (
        np.outer(np.cos(angles), first) + np.outer(np.sin(angles), second)
    )
    free = 1.0 - float(np.count_nonzero(inside(mesh, shaft))) / len(shaft)
    return f"Lippe {share:.2f} ({len(below)} Punkte), Tasche frei {free:.2f}"


def features_of(entry) -> list[str]:
    rows = []
    for name, f in sorted(entry.features.items()):
        if f.kind in ("hole", "cone", "curved_face", "chamfer"):
            p = f.params
            rows.append(
                f"{name}:{f.kind} Ø{float(p.get('diameter', 0) or 0):.3f} "
                f"eng={p.get('narrowing')} öff={p.get('opening')} "
                f"achse={tuple(round(float(v), 3) for v in p.get('axis', (0, 0, 0)))} "
                f"dreiecke={len(f.face_indices)} herkunft={f.provenance}"
            )
    return rows


def tilted(exact: bool):
    project, history = common.pocket_project(exact)
    common.run(project)
    common.apply(history, "rotate_feature", {"at_feature": POCKET, "axis": "x", "angle": 10.0})
    return project, history


def main() -> None:
    for exact in (False, True):
        label = "exakt" if exact else "Netz"
        print(f"##### {label}", flush=True)
        project, history = tilted(exact)
        result = common.run(project)
        entry = result.scene.objects["obj_1"]
        twin = as_mesh_data(entry.mesh)
        print(
            f"   gekippt 10°: V {twin.volume:.3f} dicht {twin.is_watertight}; "
            f"{lip_share(entry.mesh, entry.features[POCKET])}",
            flush=True,
        )
        for row in features_of(entry):
            print(f"      {row}", flush=True)
        for name, f in sorted(entry.features.items()):
            if f.kind not in ("hole", "cone", "curved_face"):
                continue
            print(f"   Zeilen {name} ({f.kind}):", flush=True)
            for action in actions_for(f, entry.features, mesh=twin):
                state = action.op if action.op else f"GRAU: {str(action.reason)[:150]}"
                print(f"      {action.title} -> {state}", flush=True)
        centre = tuple(float(v) for v in entry.features[POCKET].params["centre"])
        cone_names = sorted(n for n, f in entry.features.items() if f.kind == "cone")
        seconds = [
            ("noch einmal drehen 10°", "rotate_feature", {"at_feature": POCKET, "axis": "x", "angle": 10.0}),
            ("versetzen 3 mm X", "move_feature", {"at_feature": POCKET, "x": centre[0] + 3.0, "y": centre[1], "z": centre[2]}),
            ("verdoppeln 10 mm X", "duplicate_feature", {"at_feature": POCKET, "x": centre[0] + 10.0, "y": centre[1], "z": centre[2]}),
            ("Bohrung ändern Einlauf 8,5", "resize_hole", {"at_feature": POCKET, "diameter": 8.5, "entrance_mode": "follow"}),
            ("Bohrung ändern nur 8,5", "resize_hole", {"at_feature": POCKET, "diameter": 8.5, "entrance_mode": "keep"}),
            ("Bohrung ändern nur 7,8", "resize_hole", {"at_feature": POCKET, "diameter": 7.8, "entrance_mode": "keep"}),
        ]
        for cone in cone_names:
            seconds.append((f"{cone} entfernen (nur)", "remove_feature", {"at_feature": cone, "sections": "single"}))
            seconds.append((f"{cone} ändern +1", "resize_feature", {"at_feature": cone, "diameter": 9.25}))
            seconds.append((f"{cone} drehen 10°", "rotate_feature", {"at_feature": cone, "axis": "x", "angle": 10.0}))
        for text, op, params in seconds:
            project, history = tilted(exact)
            common.run(project)
            try:
                common.apply(history, op, params)
            except Exception as error:  # noqa: BLE001 — die Sonde zählt
                print(f"   {text}: Anlegen scheiterte: {type(error).__name__}: {error}", flush=True)
                continue
            result = common.run(project)
            entry = result.scene.objects.get("obj_1")
            if entry is None or not result.complete:
                print(f"   {text}: vollständig {result.complete}; Halt {common.stops(result)}", flush=True)
                continue
            twin = as_mesh_data(entry.mesh)
            pockets = [n for n, f in entry.features.items() if f.kind == "hole"]
            shares = "; ".join(
                f"{n}: {lip_share(entry.mesh, entry.features[n])}" for n in sorted(pockets)
            )
            print(f"   {text}: V {twin.volume:.3f} dicht {twin.is_watertight}; {shares}", flush=True)
            for row in common.warnings(result):
                print(f"      {row}", flush=True)
            for row in features_of(entry):
                print(f"      {row}", flush=True)


if __name__ == "__main__":
    main()
