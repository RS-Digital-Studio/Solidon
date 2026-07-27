"""Moving, rotating and scaling (Bauplan §25, §18.11).

Every manipulation is an operation — also the one that started as a drag in the
viewport (§18.11). So the arithmetic sits here and the gizmo only decides which
numbers to hand over; undo then takes back a drag exactly like a menu entry.

Snapping belongs to the interaction, not to the geometry: the surface rounds the
value, the operation stores what was actually applied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.types import Vec3
from app.core.units import EPS_DISPLAY, EPS_GEOM

Axis = Literal["x", "y", "z"]
Anchor = Literal["centre", "origin", "bed"]
"""What a rotation or scaling turns around: the body's centre, the world origin,
or the point where the body sits on the plate."""

AXIS_VECTORS: dict[Axis, Vec3] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


def anchor_point(mesh: MeshData, anchor: Anchor) -> Vec3:
    """The fixed point of a transformation."""
    bounds = mesh.bounds
    if anchor == "origin":
        return (0.0, 0.0, 0.0)
    if anchor == "bed":
        centre = bounds.centre
        return (centre[0], centre[1], bounds.minimum[2])
    return bounds.centre


def translation(offset: Vec3) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(offset, dtype=float)
    return matrix


def rotation(axis: Axis, degrees: float, about: Vec3 = (0.0, 0.0, 0.0)) -> np.ndarray:
    return np.asarray(
        trimesh.transformations.rotation_matrix(
            math.radians(degrees), np.asarray(AXIS_VECTORS[axis], dtype=float), np.asarray(about)
        ),
        dtype=float,
    )


def scaling(factors: Vec3, about: Vec3 = (0.0, 0.0, 0.0)) -> np.ndarray:
    """Uniform or per-axis scaling around a fixed point."""
    values = np.asarray(factors, dtype=float)
    if np.any(np.abs(values) <= EPS_GEOM):
        raise ValueError("a scale factor of zero would collapse the body")
    matrix = np.eye(4)
    matrix[0, 0], matrix[1, 1], matrix[2, 2] = values
    pivot = np.asarray(about, dtype=float)
    matrix[:3, 3] = pivot - values * pivot
    return matrix


def apply(mesh: MeshData, matrix: np.ndarray) -> MeshData:
    """Return a transformed copy. The input is never touched (AGENTS.md rule 3)."""
    body = mesh.raw.copy()
    body.apply_transform(matrix)
    return mesh.replacing(body)


def place_on_bed(mesh: MeshData) -> MeshData:
    """Drop the body onto Z = 0 without moving it sideways (§17.1 step 6)."""
    return apply(mesh, translation((0.0, 0.0, -mesh.bounds.minimum[2])))


@dataclass(frozen=True, slots=True)
class TransformSteps:
    """A gizmo drag, taken apart into things an operation can express (§18.11).

    A dragged matrix is not editable afterwards; ``translate 12 mm`` is. So the
    matrix is decomposed once, here, and what reaches the stack are operations
    whose numbers can still be changed (§2.1).
    """

    offset: Vec3 = (0.0, 0.0, 0.0)
    axis: Axis | None = None
    angle: float = 0.0
    scale: float = 1.0

    @property
    def moves(self) -> bool:
        return any(abs(value) > EPS_DISPLAY for value in self.offset)

    @property
    def turns(self) -> bool:
        return self.axis is not None and abs(self.angle) > EPS_DISPLAY

    @property
    def resizes(self) -> bool:
        return abs(self.scale - 1.0) > 1e-4


def decompose_transform(matrix: np.ndarray) -> TransformSteps:
    """Split a transformation into offset, rotation about a main axis, and scale.

    The gizmo turns around its own axes, so a rotation lands on x, y or z; a
    combined drag simply yields several steps, which then travel as one
    transaction (§15.5).
    """
    scales, _shear, angles, offset, _perspective = trimesh.transformations.decompose_matrix(
        np.asarray(matrix, dtype=float)
    )
    degrees = [math.degrees(value) for value in angles]
    largest = max(range(3), key=lambda index: abs(degrees[index]))
    axis: Axis | None = ("x", "y", "z")[largest]
    angle = degrees[largest]
    if abs(angle) <= EPS_DISPLAY:
        axis, angle = None, 0.0

    scale = float(np.mean(scales))
    return TransformSteps(
        offset=(float(offset[0]), float(offset[1]), float(offset[2])),
        axis=axis,
        angle=angle,
        scale=scale,
    )


def snap_to_step(value: float, step: float) -> float:
    """Grid and angle snapping. A step of zero means no snapping (§18.11)."""
    if step <= EPS_GEOM:
        return value
    return round(value / step) * step
