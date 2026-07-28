"""Bringing features into line (Bauplan §18.11).

Snapping that means something: not "close to a grid point" but "this bore is
now coaxial with that one", "this face lies flat on that face". Both are the
motion a person describes in words, and both are one operation afterwards —
a matrix nobody can read is exactly what §2.1 forbids.

The maths is the same in both cases: turn one direction onto another, then move
one point onto another. What differs is what counts as the direction and the
point — for a bore its axis and its centre, for a face its normal and its
middle. Faces are turned to face *into* each other, bores to run *with* each
other, which is the difference between lying on something and sliding into it.
"""

from __future__ import annotations

import math

import numpy as np

from app.core.errors import Action, AppError
from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply
from app.core.log import get_logger
from app.core.types import Feature, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)


def frame_of(feature: Feature) -> tuple[Vec3, Vec3]:
    """Direction and anchor point of a feature — its axis and its centre.

    A bore points along its axis, a face along its normal. An edge loop has
    neither, and saying so beats inventing one.
    """
    params = feature.params
    if feature.kind == "hole":
        direction = params.get("axis")
        point = params.get("centre")
    elif feature.kind == "face":
        direction = params.get("normal")
        point = params.get("centre")
    else:
        raise AppError(
            _("An diesem Merkmal lässt sich nichts ausrichten."),
            detail=f"feature kind {feature.kind!r} has no axis",
            values={"feature": feature.id, "kind": feature.kind},
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie eine Bohrung oder eine Fläche.")),
            ),
        )
    if direction is None or point is None:
        raise AppError(
            _("An diesem Merkmal lässt sich nichts ausrichten."),
            detail=f"feature {feature.id!r} carries no frame",
            values={"feature": feature.id},
        )
    return _unit(direction), (float(point[0]), float(point[1]), float(point[2]))


def align_matrix(source: Feature, target: Feature, flip: bool = False) -> np.ndarray:
    """The transform that puts ``source`` onto ``target``.

    Two faces meet front to front, so the source normal is turned onto the
    *inverted* target normal — otherwise the parts would end up back to back,
    which is the one thing nobody means by "lay this on that". Two bores share
    an axis, so they are turned onto the same direction. ``flip`` turns the
    result around for the case where the other way was meant.
    """
    source_direction, source_point = frame_of(source)
    target_direction, target_point = frame_of(target)

    wanted = np.asarray(target_direction, dtype=float)
    if source.kind == "face" and target.kind == "face":
        wanted = -wanted
    if flip:
        wanted = -wanted

    turn = rotation_between(
        source_direction, (float(wanted[0]), float(wanted[1]), float(wanted[2]))
    )
    moved_point = turn @ np.array([*source_point, 1.0])
    offset = np.asarray(target_point, dtype=float) - moved_point[:3]

    matrix = np.eye(4)
    matrix[:3, 3] = offset
    return np.asarray(matrix @ turn, dtype=float)


def rotation_between(source: Vec3, target: Vec3) -> np.ndarray:
    """Shortest rotation carrying one direction onto another (Rodrigues)."""
    first = np.asarray(_unit(source), dtype=float)
    second = np.asarray(_unit(target), dtype=float)
    axis = np.cross(first, second)
    length = float(np.linalg.norm(axis))
    dot = float(np.clip(first @ second, -1.0, 1.0))

    if length <= EPS_GEOM:
        if dot > 0.0:
            return np.eye(4)
        # Opposite directions: any perpendicular axis turns it, so take one.
        helper = np.array([1.0, 0.0, 0.0]) if abs(first[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        axis = np.cross(first, helper)
        length = float(np.linalg.norm(axis))
        angle = math.pi
    else:
        angle = math.acos(dot)

    axis = axis / length
    cross = np.array(
        [
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0],
        ]
    )
    turn = np.eye(3) + math.sin(angle) * cross + (1.0 - math.cos(angle)) * (cross @ cross)
    matrix = np.eye(4)
    matrix[:3, :3] = turn
    return matrix


def align(mesh: MeshData, source: Feature, target: Feature, flip: bool = False) -> MeshData:
    """Move a body so its feature lines up with another one."""
    matrix = align_matrix(source, target, flip)
    _log.info("aligning %s onto %s", source.id, target.id)
    return apply(mesh, matrix)


def _unit(vector: object) -> Vec3:
    values = np.asarray(vector, dtype=float)
    length = float(np.linalg.norm(values))
    if length <= EPS_GEOM:
        raise AppError(
            _("An diesem Merkmal lässt sich nichts ausrichten."),
            detail="direction of length zero",
        )
    values = values / length
    return (float(values[0]), float(values[1]), float(values[2]))
