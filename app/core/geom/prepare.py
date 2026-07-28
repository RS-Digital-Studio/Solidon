"""Print preparation: bores, splitting, arranging, collisions (Bauplan §25, §18.6).

Three rules from the rule set (§39) live here, because this is where they would
otherwise be forgotten:

* a bore is drilled larger than nominal, because FDM prints holes tight — and
  the amount comes from the calibrated material profile, never from a literal
  (AGENTS.md rule 7);
* boolean cuts always overlap by a hundredth of a millimetre, so no two faces
  are ever coincident;
* what leaves the build volume is reported, not silently scaled.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import trimesh

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.geom.section import SectionPlane, cut
from app.core.geom.transform import Axis, translation
from app.core.knowledge.profiles import resolve_tolerance
from app.core.types import BoundingBox, Finding, Profile, Quality, SolverInfo, Vec3
from app.core.units import EPS_GEOM, format_length
from app.i18n import _

#: §39: booleans always overlap slightly, never share a face exactly.
BOOLEAN_OVERLAP = 0.01

#: Sections a drilled cylinder is built from. Fine enough that the printed hole
#: is round, coarse enough not to explode the triangle count.
BORE_SECTIONS = 48


@dataclass(slots=True)
class BoreResult:
    mesh: MeshData
    solver: SolverInfo
    diameter: float
    """The diameter actually cut, including the material compensation."""
    findings: list[Finding]


def bore_diameter(nominal: float, profile: Profile, compensate: bool) -> float:
    """Nominal plus what the material eats, from the profile (§39, §28.3)."""
    if not compensate:
        return nominal
    return nominal + resolve_tolerance("auto:", "thread", profile)


def drill(
    mesh: MeshData,
    *,
    position: Vec3,
    axis: Axis,
    diameter: float,
    depth: float = 0.0,
    profile: Profile,
    compensate: bool = True,
    quality: Quality = "fine",
    seed: int | None = None,
) -> BoreResult:
    """Cut a cylindrical bore. Depth zero drills right through."""
    cut_diameter = bore_diameter(diameter, profile, compensate)
    height = depth if depth > EPS_GEOM else _through_length(mesh, axis)
    cylinder = trimesh.creation.cylinder(
        radius=cut_diameter / 2.0, height=height + BOOLEAN_OVERLAP * 2, sections=BORE_SECTIONS
    )
    cylinder.apply_transform(_axis_alignment(axis))
    cylinder.apply_translation(np.asarray(position, dtype=float))

    outcome = boolean("difference", [mesh, MeshData.of(cylinder)], quality=quality, seed=seed)
    findings = list(outcome.findings)
    if compensate and abs(cut_diameter - diameter) > EPS_GEOM:
        findings.append(
            Finding(
                code="bore.compensated",
                severity="info",
                message=_("Die Bohrung wurde um die Materialtoleranz vergrößert."),
                values={
                    "nominal": format_length(diameter),
                    "cut": format_length(cut_diameter),
                },
            )
        )
    return BoreResult(
        mesh=outcome.mesh, solver=outcome.solver, diameter=cut_diameter, findings=findings
    )


def _through_length(mesh: MeshData, axis: Axis) -> float:
    """Long enough to pass through the whole body along that axis."""
    size = mesh.bounds.size
    index = {"x": 0, "y": 1, "z": 2}[axis]
    return float(size[index]) + BOOLEAN_OVERLAP * 4


def _axis_alignment(axis: Axis) -> np.ndarray:
    """Cylinders are built along Z; turn them onto the requested axis."""
    if axis == "z":
        return np.eye(4)
    angle = math.radians(90.0)
    direction = (0.0, 1.0, 0.0) if axis == "x" else (1.0, 0.0, 0.0)
    return np.asarray(trimesh.transformations.rotation_matrix(angle, direction), dtype=float)


def split_at_plane(mesh: MeshData, plane: SectionPlane) -> tuple[MeshData, MeshData, list[Finding]]:
    """Cut a body in two, both halves closed (§18.2, §25)."""
    first = cut(mesh, plane)
    second = cut(mesh, plane.flipped())
    findings: list[Finding] = []
    if not (first.capped and second.capped):
        findings.append(
            Finding(
                code="split.uncapped",
                severity="warning",
                message=_("Die Schnittflächen konnten nicht geschlossen werden."),
            )
        )
    return first.mesh, second.mesh, findings


def arrange_on_bed(
    meshes: list[MeshData], profile: Profile, spacing: float = 5.0
) -> tuple[list[MeshData], list[Finding]]:
    """Lay the bodies out on the plate in a row, then wrap into rows (§25).

    Deliberately simple: a shelf packing that anyone can predict beats a clever
    one that moves parts around for reasons nobody can see.
    """
    width, depth, _height = profile.printer.build_volume
    arranged: list[MeshData] = []
    findings: list[Finding] = []

    cursor_x = -width / 2.0 + spacing
    cursor_y = -depth / 2.0 + spacing
    row_depth = 0.0

    for mesh in meshes:
        size = mesh.bounds.size
        if cursor_x + size[0] > width / 2.0 - spacing:
            cursor_x = -width / 2.0 + spacing
            cursor_y += row_depth + spacing
            row_depth = 0.0

        target = (
            cursor_x + size[0] / 2.0,
            cursor_y + size[1] / 2.0,
            mesh.bounds.size[2] / 2.0,
        )
        offset = tuple(target[index] - mesh.bounds.centre[index] for index in range(3))
        body = mesh.raw.copy()
        body.apply_transform(translation((offset[0], offset[1], offset[2])))
        arranged.append(mesh.replacing(body))

        cursor_x += size[0] + spacing
        row_depth = max(row_depth, size[1])

    findings.extend(check_build_volume(arranged, profile))
    return arranged, findings


def check_build_volume(meshes: list[MeshData], profile: Profile) -> list[Finding]:
    """What sticks out of the build volume is reported, never quietly scaled."""
    width, depth, height = profile.printer.build_volume
    allowed = BoundingBox((-width / 2.0, -depth / 2.0, 0.0), (width / 2.0, depth / 2.0, height))
    findings: list[Finding] = []

    for index, mesh in enumerate(meshes):
        bounds = mesh.bounds
        outside = [
            axis
            for axis, (low, high, limit_low, limit_high) in enumerate(
                zip(bounds.minimum, bounds.maximum, allowed.minimum, allowed.maximum, strict=True)
            )
            if low < limit_low - EPS_GEOM or high > limit_high + EPS_GEOM
        ]
        if outside:
            findings.append(
                Finding(
                    code="arrange.out_of_build_volume",
                    severity="warning",
                    message=_("Ein Objekt steht über den Bauraum hinaus."),
                    values={"object": index, "axes": ", ".join("xyz"[axis] for axis in outside)},
                )
            )
    return findings


def check_collisions(meshes: list[MeshData], clearance: float = 0.0) -> list[Finding]:
    """Overlapping bounding boxes — cheap, and enough to warn about (§18.6)."""
    findings: list[Finding] = []
    for first in range(len(meshes)):
        for second in range(first + 1, len(meshes)):
            if _boxes_overlap(meshes[first].bounds, meshes[second].bounds, clearance):
                findings.append(
                    Finding(
                        code="arrange.collision",
                        severity="warning",
                        message=_("Zwei Objekte überschneiden sich."),
                        values={"a": first, "b": second},
                    )
                )
    return findings


def _boxes_overlap(first: BoundingBox, second: BoundingBox, clearance: float) -> bool:
    for axis in range(3):
        if first.maximum[axis] + clearance <= second.minimum[axis]:
            return False
        if second.maximum[axis] + clearance <= first.minimum[axis]:
            return False
    return True
