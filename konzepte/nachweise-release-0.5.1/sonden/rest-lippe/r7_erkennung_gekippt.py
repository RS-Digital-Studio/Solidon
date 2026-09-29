"""Sonde r7_erkennung_gekippt: Was liest die Erkennung am gekippten Hohlraum — und woran scheitert sie?

Aufruf: python r7_erkennung_gekippt.py <baum>

Am Netz, je Fall frisch erkannt (``perceive.features.detect``): die gekippte
Magnettasche (mit Lippe), dieselbe Tasche ohne Lippe (Lippe zuerst entfernt,
dann gekippt), eine gebohrte Sackbohrung Ø 8,25 × 3 gekippt, und eine
gebohrte Sackbohrung mit Senkung gekippt. Je Fall die Merkmale mit
Dreieckszahl, dazu die Knickwinkel zwischen Nachbardreiecken im Hohlraum
(Histogramm), damit sichtbar wird, ob Tasche und Lippe getrennt liegen.
"""

from __future__ import annotations

import sys

import _baum

TREE = _baum.setup(sys.argv[1])
_baum.activation_free()

import numpy as np  # noqa: E402

import common  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402
from app.core.scene import History, OperationDraft  # noqa: E402
from app.core.scene.project import new_project  # noqa: E402

POCKET = "magnet_pocket_pocket_1"
TILT = ("rotate_feature", {"at_feature": POCKET, "axis": "x", "angle": 10.0})


def drilled(countersink: bool):
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 10.0})],
    )
    history.apply(
        "Bohren",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 8.25, "x": 0.0, "y": 0.0, "z": 10.0, "axis": "z", "depth": 3.0},
            )
        ],
    )
    if countersink:
        history.apply(
            "Senken",
            [
                OperationDraft(
                    op="countersink_hole",
                    inputs=("obj_1",),
                    params={"diameter": 11.0, "x": 0.0, "y": 0.0, "z": 10.0, "axis": "z"},
                )
            ],
        )
    return project, history


def report(label: str, project) -> None:
    result = common.run(project)
    entry = result.scene.objects.get("obj_1")
    if entry is None or not result.complete:
        print(f"   {label}: vollständig {result.complete}; Halt {common.stops(result)}", flush=True)
        return
    data = as_mesh_data(entry.mesh)
    print(f"   {label}: {len(data.raw.faces)} Dreiecke, V {data.volume:.3f}", flush=True)
    print("      im Baum:", flush=True)
    for name, f in sorted(entry.features.items()):
        if f.kind in ("face", "fillet", "chamfer"):
            continue
        print(
            f"         {name}: {f.kind} Ø{float(f.params.get('diameter', 0) or 0):.3f} "
            f"eng={f.params.get('narrowing')} dreiecke={len(f.face_indices)} {f.provenance}",
            flush=True,
        )
    fresh = detect(data)
    print("      frisch erkannt:", flush=True)
    for name, f in sorted(fresh.items()):
        if f.kind in ("face", "fillet", "chamfer"):
            continue
        print(
            f"         {name}: {f.kind} Ø{float(f.params.get('diameter', 0) or 0):.3f} "
            f"eng={f.params.get('narrowing')} dreiecke={len(f.face_indices)}",
            flush=True,
        )
    # Knickwinkel im Hohlraum: Kanten, deren beide Dreiecke innerhalb r < 5 um die Achse liegen.
    raw = data.raw
    centres = raw.triangles_center
    near = np.hypot(centres[:, 0], centres[:, 1] + 0.3) < 5.0
    pairs = raw.face_adjacency
    angles = np.degrees(raw.face_adjacency_angles)
    keep = near[pairs[:, 0]] & near[pairs[:, 1]]
    counts, edges = np.histogram(angles[keep], bins=[0, 1, 5, 10, 15, 20, 25, 30, 45, 60, 90, 180])
    print(
        "      Knicke im Hohlraum (Grad: Zahl): "
        + ", ".join(f"{edges[i]:.0f}-{edges[i + 1]:.0f}: {counts[i]}" for i in range(len(counts))),
        flush=True,
    )


def main() -> None:
    project, history = common.pocket_project(False)
    common.run(project)
    report("Magnettasche gerade", project)
    common.apply(history, *TILT)
    report("Magnettasche gekippt 10°", project)

    project, history = common.pocket_project(False)
    common.run(project)
    common.apply(history, "remove_feature", {"at_feature": "cone_1", "sections": "single"})
    common.run(project)
    common.apply(history, *TILT)
    report("Tasche ohne Lippe gekippt 10°", project)

    for countersink in (False, True):
        project, history = drilled(countersink)
        result = common.run(project)
        entry = result.scene.objects["obj_1"]
        hole = next(n for n, f in entry.features.items() if f.kind == "hole")
        common.apply(history, "rotate_feature", {"at_feature": hole, "axis": "x", "angle": 10.0})
        report(f"Sackbohrung{' mit Senkung' if countersink else ''} gekippt 10°", project)


if __name__ == "__main__":
    main()
