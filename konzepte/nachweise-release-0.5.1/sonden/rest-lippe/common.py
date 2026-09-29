"""Gemeinsame Bausteine der Sonden des Prüfers rest-lippe.

Erst nach ``_baum.setup`` importieren: Hier wird ``app`` gelesen.

``pocket_project(exact)`` baut den Aufbau aus den Sonden von rest-erkennung:
Quader 40 x 40 x 10 (Netz oder exakter Körper), Magnettasche 8x3 mittig
oben — Tasche ``magnet_pocket_pocket_1`` (Ø 8,25), Lippe ``cone_1``
(Ø 8,25 → Öffnung 7,95 über 0,4 mm an der Mündung z = 10).

``opening(mesh, centre, axis, t)`` schneidet quer zur Achse ``axis`` im Abstand
``t`` von ``centre`` und gibt den Durchmesser des flächengleichen Kreises der
Schleife um die Achse — ``None``, wenn dort Material ist.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.core.bootstrap import load_operations
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project

load_operations()
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")
BOX = 40.0 * 40.0 * 10.0


def pocket_project(exact: bool, *, size: str = "8x3") -> tuple[Any, History]:
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box" if exact else "create_box",
                params={"width": 40.0, "depth": 40.0, "height": 10.0},
            )
        ],
    )
    history.apply(
        "Magnettasche",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": size, "x": 0.0, "y": 0.0, "z": 10.0},
            )
        ],
    )
    return project, history


def run(project: Any) -> Any:
    return evaluate(project.document, PROFILE, sources=ProjectSources(project))


def apply(history: History, op: str, params: dict[str, Any]) -> None:
    history.apply(op, [OperationDraft(op=op, inputs=("obj_1",), params=params)])


def opening(mesh: Any, centre: Any, axis: Any, t: float) -> float | None:
    from shapely.geometry import Polygon

    body = as_mesh_data(mesh).raw
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    origin = np.asarray(centre, dtype=float) + t * axis
    section = body.section(plane_origin=origin, plane_normal=axis)
    if section is None:
        return None
    planar, to_3d = section.to_2D()
    # Die Achse im ebenen Bild: der Ursprung der Schnittebene.
    inverse = np.linalg.inv(to_3d)
    local = (inverse @ np.append(origin, 1.0))[:2]
    best = None
    for loop in planar.discrete:
        points = np.asarray(loop, dtype=float)
        if len(points) < 3:
            continue
        shape = Polygon(points)
        if not shape.is_valid or shape.area > 400.0:
            continue
        middle = np.asarray(shape.centroid.coords[0])
        if float(np.hypot(*(middle - local))) < 1.5:
            diameter = 2.0 * math.sqrt(shape.area / math.pi)
            best = diameter if best is None else min(best, diameter)
    return best


def fmt(value: float | None) -> str:
    return "zu" if value is None else f"{value:.3f}"


def body_facts(entry: Any) -> str:
    twin = as_mesh_data(entry.mesh)
    return f"V {twin.volume:.3f} dicht {twin.is_watertight}"


def stops(result: Any) -> list[str]:
    return [
        f"{f.code}: {str(f.message)[:110]}"
        for f in result.scene.report.findings
        if f.severity == "error" or "Error" in f.code
    ]


def warnings(result: Any) -> list[str]:
    return [
        f"{f.code} ({f.severity}): {str(f.message)[:140]} -> {[str(w.label) for w in f.suggestions]}"
        for f in result.scene.report.findings
        if f.severity in ("warning", "info")
        and (f.code.startswith(("resize.", "rotate_feature.", "move_feature.", "op.")))
    ]
