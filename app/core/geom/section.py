"""Cutting a body with a plane (Bauplan §18.2).

**The cut face is closed.** Without a cap every solid looks hollow and wall
thickness cannot be judged — that is where naive implementations fail, and it is
why this lives in the core rather than in the viewport: a capped cut is geometry,
so it can be checked by measuring the result instead of comparing pixels.

A second plane turns the cut into a slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import Vec3
from app.core.units import EPS_GEOM

_log = get_logger(__name__)

Axis = Literal["x", "y", "z"]

AXIS_NORMALS: dict[Axis, Vec3] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


@dataclass(frozen=True, slots=True)
class SectionPlane:
    """A cutting plane. Everything on the positive side of the normal is removed."""

    normal: Vec3 = (0.0, 0.0, 1.0)
    position: float = 0.0
    """Distance of the plane from the origin along its normal, in millimetres."""

    @classmethod
    def along(cls, axis: Axis, position: float = 0.0) -> SectionPlane:
        return cls(normal=AXIS_NORMALS[axis], position=position)

    @property
    def origin(self) -> Vec3:
        length = float(np.linalg.norm(self.normal)) or 1.0
        return (
            self.normal[0] / length * self.position,
            self.normal[1] / length * self.position,
            self.normal[2] / length * self.position,
        )

    def flipped(self) -> SectionPlane:
        return SectionPlane(
            normal=(-self.normal[0], -self.normal[1], -self.normal[2]),
            position=-self.position,
        )


@dataclass(frozen=True, slots=True)
class SectionResult:
    """What is left of the body, and whether the cut face could be closed."""

    mesh: MeshData
    capped: bool
    """False when the body was not closed to begin with — then a cap is impossible."""


def cut(mesh: MeshData, plane: SectionPlane, second: SectionPlane | None = None) -> SectionResult:
    """Cut a body, closing the cut face. A second plane leaves a slice.

    An open model cannot be capped honestly, so the cut is still shown but
    reported as uncapped rather than faked.
    """
    body: trimesh.Trimesh = mesh.raw
    capped = True

    for entry in (plane, second) if second is not None else (plane,):
        body, closed = _apply(body, entry)
        capped = capped and closed
        if not len(body.faces):
            return SectionResult(mesh=mesh.replacing(trimesh.Trimesh()), capped=capped)

    return SectionResult(mesh=mesh.replacing(body), capped=capped)


def _apply(body: trimesh.Trimesh, plane: SectionPlane) -> tuple[trimesh.Trimesh, bool]:
    """One plane. ``slice_plane`` caps when the input is watertight."""
    normal = np.asarray(plane.normal, dtype=float)
    length = float(np.linalg.norm(normal))
    if length <= EPS_GEOM:
        return body, True
    normal = normal / length
    # trimesh keeps what lies on the positive side, so the normal points the
    # other way: the visible half is the one the plane looks away from.
    watertight = bool(body.is_watertight)

    # A plane that misses the body needs no cut — and a cut with nothing to cap
    # is the one case the polygon code cannot make sense of.
    distances = _corner_distances(body, normal, np.asarray(plane.origin, dtype=float))
    if distances.max() <= EPS_GEOM:
        return body, watertight
    if distances.min() >= -EPS_GEOM:
        return trimesh.Trimesh(), watertight
    result = body.slice_plane(
        plane_origin=np.asarray(plane.origin, dtype=float),
        plane_normal=-normal,
        cap=watertight,
    )
    return result, watertight


def _corner_distances(body: trimesh.Trimesh, normal: np.ndarray, origin: np.ndarray) -> np.ndarray:
    """Signed distance of the bounding box corners; positive means "gets removed"."""
    low, high = body.bounds
    corners = np.array(
        [(x, y, z) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
    )
    return np.asarray((corners - origin) @ normal, dtype=float)


def section_volume(mesh: MeshData, plane: SectionPlane) -> float:
    """Volume left after the cut — the honest test for a closed cut face."""
    return float(cut(mesh, plane).mesh.volume)
