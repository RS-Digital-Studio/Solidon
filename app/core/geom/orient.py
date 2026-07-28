"""Choosing a print orientation (Bauplan §25, P2).

A heuristic over face normals, and openly labelled as one: it looks for a flat
face to stand on and counts how much would overhang. In P3 the layer analysis
(§22) replaces it — then hundreds of rotations get judged by real support volume
instead of by a rule of thumb.

Until then the rule of thumb is honest about what it is: the finding says which
candidate won and by what margin.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, place_on_bed
from app.core.types import Finding, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

#: Faces steeper than this against the plate need support (§39, §18.4).
OVERHANG_LIMIT_DEGREES = 45.0

#: How many candidate directions are looked at beyond the six axis directions.
MAX_FACE_CANDIDATES = 12


@dataclass(frozen=True, slots=True)
class Orientation:
    """One candidate and what speaks for it."""

    direction: Vec3
    """The face normal that would end up pointing down."""
    footprint: float
    """Area that would rest on the plate, in mm²."""
    overhang: float
    """Area that would need support, in mm²."""
    height: float

    @property
    def score(self) -> float:
        """Large footprint, little overhang, low build — in that order."""
        return self.footprint * 2.0 - self.overhang - self.height * 10.0


@dataclass(slots=True)
class OrientResult:
    mesh: MeshData
    chosen: Orientation
    findings: list[Finding]


def candidates(mesh: MeshData) -> list[Vec3]:
    """Six axis directions plus the normals of the largest flat faces."""
    found: list[Vec3] = [
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
    ]
    body = mesh.raw
    if not len(body.faces):
        return found

    normals = np.asarray(body.face_normals, dtype=float)
    areas = np.asarray(body.area_faces, dtype=float)
    rounded = np.round(normals, 3)
    unique, inverse = np.unique(rounded, axis=0, return_inverse=True)
    grouped = np.zeros(len(unique))
    np.add.at(grouped, inverse, areas)

    for index in np.argsort(grouped)[::-1][:MAX_FACE_CANDIDATES]:
        normal = unique[index]
        length = float(np.linalg.norm(normal))
        if length > EPS_GEOM:
            unit = normal / length
            found.append((float(unit[0]), float(unit[1]), float(unit[2])))
    return found


def evaluate_direction(mesh: MeshData, direction: Vec3) -> Orientation:
    """What the body would look like standing on that face."""
    turned = apply(mesh, _rotation_to_down(direction))
    body = turned.raw
    normals = np.asarray(body.face_normals, dtype=float)
    areas = np.asarray(body.area_faces, dtype=float)

    downward = normals[:, 2] < -math.cos(math.radians(OVERHANG_LIMIT_DEGREES))
    flat_bottom = (normals[:, 2] < -0.999) & (
        np.asarray(body.triangles_center)[:, 2] < body.bounds[0][2] + 0.05
    )
    return Orientation(
        direction=direction,
        footprint=float(areas[flat_bottom].sum()),
        overhang=float(areas[downward & ~flat_bottom].sum()),
        height=float(turned.bounds.size[2]),
    )


def _rotation_to_down(direction: Vec3) -> np.ndarray:
    """The rotation that turns ``direction`` into -Z."""
    source = np.asarray(direction, dtype=float)
    length = float(np.linalg.norm(source))
    if length <= EPS_GEOM:
        return np.eye(4)
    source = source / length
    target = np.array([0.0, 0.0, -1.0])

    axis = np.cross(source, target)
    if float(np.linalg.norm(axis)) <= EPS_GEOM:
        if float(np.dot(source, target)) > 0:
            return np.eye(4)
        return np.asarray(
            trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]), dtype=float
        )
    angle = math.acos(float(np.clip(np.dot(source, target), -1.0, 1.0)))
    return np.asarray(trimesh.transformations.rotation_matrix(angle, axis), dtype=float)


def orient_for_print(mesh: MeshData) -> OrientResult:
    """Turn the body onto the orientation the heuristic likes best."""
    scored = [evaluate_direction(mesh, direction) for direction in candidates(mesh)]
    best = max(scored, key=lambda entry: entry.score)
    turned = place_on_bed(apply(mesh, _rotation_to_down(best.direction)))

    findings = [
        Finding(
            code="orient.heuristic",
            severity="info",
            message=_(
                "Ausrichtung über eine Normalen-Heuristik gewählt — die Schichtanalyse "
                "urteilt später genauer."
            ),
            values={
                "footprint": round(best.footprint, 1),
                "overhang": round(best.overhang, 1),
                "candidates": len(scored),
            },
        )
    ]
    if best.overhang > best.footprint:
        findings.append(
            Finding(
                code="orient.support_likely",
                severity="warning",
                message=_("Auch in der besten Lage bleibt viel Überhang — Stützen sind nötig."),
            )
        )
    return OrientResult(mesh=turned, chosen=best, findings=findings)
