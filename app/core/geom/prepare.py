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
from dataclasses import dataclass, field
from typing import Any

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


def countersink(
    mesh: MeshData,
    *,
    position: Vec3,
    axis: Axis,
    diameter: float,
    angle: float = 90.0,
    quality: Quality = "fine",
) -> BoreResult:
    """Break the mouth of a bore with a cone, so a screw head sits flush (§25).

    The angle is the full angle of the head — 90 degrees for a metric
    countersunk screw. What is cut is the cone that head describes, which is
    why the depth follows from the diameter rather than being asked for.
    """
    depth = diameter / 2.0 / math.tan(math.radians(angle / 2.0))
    cone = trimesh.creation.cone(radius=diameter / 2.0, height=depth, sections=BORE_SECTIONS)
    # The cone comes out standing on its base with the point up. A countersink
    # is the other way round: widest at the face, narrowing into the material.
    # Turned over it runs from zero downwards, which is exactly that — and it
    # is lifted by the overlap so the two faces do not coincide (§39).
    cone.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1.0, 0.0, 0.0]))
    cone.apply_translation([0.0, 0.0, BOOLEAN_OVERLAP])
    cone.apply_transform(_axis_alignment(axis))
    cone.apply_translation(np.asarray(position, dtype=float))

    outcome = boolean("difference", [mesh, MeshData.of(cone)], quality=quality)
    return BoreResult(
        mesh=outcome.mesh,
        solver=outcome.solver,
        diameter=diameter,
        findings=list(outcome.findings),
    )


def plug(
    mesh: MeshData,
    *,
    position: Vec3,
    axis: Axis,
    diameter: float,
    depth: float = 0.0,
    quality: Quality = "fine",
) -> BoreResult:
    """Fill a bore back in (§25, "verschließen").

    Slightly larger than the hole it fills, because a plug the exact size of the
    bore meets it in a coincident face — the one thing that reliably breaks a
    boolean (§39, ``boolean_overlap``).
    """
    height = depth if depth > EPS_GEOM else _through_length(mesh, axis)
    cylinder = trimesh.creation.cylinder(
        radius=diameter / 2.0 + BOOLEAN_OVERLAP, height=height, sections=BORE_SECTIONS
    )
    cylinder.apply_transform(_axis_alignment(axis))
    cylinder.apply_translation(np.asarray(position, dtype=float))

    # Intersect first: the plug must not grow out of the body it fills.
    inner = boolean("intersection", [mesh.replacing(cylinder), _shell(mesh)], quality=quality)
    outcome = boolean("union", [mesh, inner.mesh], quality=quality)
    return BoreResult(
        mesh=outcome.mesh,
        solver=outcome.solver,
        diameter=diameter,
        findings=list(outcome.findings),
    )


def _shell(mesh: MeshData) -> MeshData:
    """The body as a solid to clip against — the convex hull is close enough.

    A plug is cut back to the outside of the part, and for that the hull is the
    right shape: it never reaches inside a cavity, so a plug can never fill one.
    """
    return mesh.replacing(mesh.raw.convex_hull)


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


#: How many build plates one scene may be spread over. Not a technical limit —
#: past this many, whoever is printing wants a second project rather than a
#: list nobody can keep track of.
MAX_PLATES = 12


def compensate_elephant_foot(
    mesh: MeshData, profile: Profile, height: float = 0.6, amount: float | None = None
) -> tuple[MeshData, list[Finding]]:
    """Pull the first layers in by what the first layer spreads out (§25, §28.3).

    The value comes from the material profile, never from a guess (rule 7): a
    calibration measures it, and a part built before that calibration gets it
    when the profile changes.

    A straight step, not a taper — which is exactly what a slicer's "elephant
    foot compensation" does too. A taper would need a loft, and the mesh kernel
    has none; the B-Rep kernel could do it exactly (§30) and does not have to,
    because the printed result is the same.
    """
    from shapely.geometry import Polygon as ShapelyPolygon

    from app.core.slice.analysis import cross_section

    value = profile.material.elephant_foot if amount is None else amount
    if value <= EPS_GEOM:
        return mesh, []

    bottom = float(mesh.bounds.minimum[2])
    section = cross_section(mesh, bottom + height / 2.0)
    if section is None or section.is_empty:
        return mesh, []

    pulled = section.buffer(-value)
    if pulled.is_empty:
        return mesh, [
            Finding(
                code="prepare.foot_too_small",
                severity="warning",
                message=_("Die Aufstandsfläche ist zu klein, um sie noch einzuziehen."),
                values={"amount_mm": round(value, 3)},
            )
        ]

    # What has to go: the ring between the real outline and the pulled-in one,
    # over the height of the first layers.
    ring = section.difference(pulled)
    if ring.is_empty:
        return mesh, []
    parts = [
        trimesh.creation.extrude_polygon(entry, height=height + BOOLEAN_OVERLAP)
        for entry in getattr(ring, "geoms", [ring])
        if isinstance(entry, ShapelyPolygon) and entry.area > EPS_GEOM
    ]
    if not parts:
        return mesh, []

    collar = trimesh.util.concatenate(parts)
    collar.apply_translation([0.0, 0.0, bottom - BOOLEAN_OVERLAP / 2.0])
    outcome = boolean("difference", [mesh, mesh.replacing(collar)])
    findings = list(outcome.findings)
    findings.append(
        Finding(
            code="prepare.elephant_foot",
            severity="info",
            message=_("Die ersten Schichten wurden um den Elefantenfuß eingezogen."),
            values={"amount_mm": round(value, 3), "height_mm": round(height, 2)},
        )
    )
    return outcome.mesh, findings


@dataclass(frozen=True, slots=True)
class Arrangement:
    """Where the bodies ended up, and on which plate."""

    meshes: list[MeshData]
    plates: list[int]
    findings: list[Finding] = field(default_factory=list)

    @property
    def plate_count(self) -> int:
        return max(self.plates, default=0) + 1 if self.plates else 0


def arrange_on_bed(
    meshes: list[MeshData], profile: Profile, spacing: float = 5.0, plates: int = 1
) -> Arrangement:
    """Lay the bodies out on the plate in a row, then wrap into rows (§25).

    Deliberately simple: a shelf packing that anyone can predict beats a clever
    one that moves parts around for reasons nobody can see.

    What does not fit goes on the next plate — up to ``plates`` of them. More
    parts than plates is not an error to hide: the last plate takes the rest and
    the report says it is overfull, because a part silently left out of an
    arrangement is a part that never gets printed.
    """
    width, depth, _height = profile.printer.build_volume
    arranged: list[MeshData] = []
    assigned: list[int] = []
    findings: list[Finding] = []

    plate = 0
    cursor_x = -width / 2.0 + spacing
    cursor_y = -depth / 2.0 + spacing
    row_depth = 0.0

    for mesh in meshes:
        size = mesh.bounds.size
        if cursor_x + size[0] > width / 2.0 - spacing:
            cursor_x = -width / 2.0 + spacing
            cursor_y += row_depth + spacing
            row_depth = 0.0
        if cursor_y + size[1] > depth / 2.0 - spacing and plate + 1 < plates:
            plate += 1
            cursor_x = -width / 2.0 + spacing
            cursor_y = -depth / 2.0 + spacing
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
        assigned.append(plate)

        cursor_x += size[0] + spacing
        row_depth = max(row_depth, size[1])

    findings.extend(check_build_volume(arranged, profile, assigned))
    if plate + 1 >= plates and _overfull(arranged, assigned, profile):
        findings.append(
            Finding(
                code="arrange.needs_more_plates",
                severity="warning",
                message=_("Auf so viele Platten passt das nicht — eine mehr würde helfen."),
                values={"plates": plates},
            )
        )
    return Arrangement(meshes=arranged, plates=assigned, findings=findings)


def _overfull(meshes: list[MeshData], plates: list[int], profile: Profile) -> bool:
    """Does anything on the last plate stick out of it?"""
    last = max(plates, default=0)
    on_last = [mesh for mesh, plate in zip(meshes, plates, strict=True) if plate == last]
    return bool(check_build_volume(on_last, profile))


def check_build_volume(
    meshes: list[MeshData], profile: Profile, plates: list[int] | None = None
) -> list[Finding]:
    """What sticks out of the build volume is reported, never quietly scaled.

    Checked per plate: two objects at the same place on different plates are
    not a problem, and neither is a plate that is full while the next is empty.
    """
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
            values: dict[str, Any] = {
                "object": index,
                "axes": ", ".join("xyz"[axis] for axis in outside),
            }
            if plates is not None and index < len(plates):
                values["plate"] = plates[index] + 1
            findings.append(
                Finding(
                    code="arrange.out_of_build_volume",
                    severity="warning",
                    message=_("Ein Objekt steht über den Bauraum hinaus."),
                    values=values,
                )
            )
    return findings


def check_collisions(meshes: list[MeshData], clearance: float = 0.0) -> list[Finding]:
    """Do two bodies really overlap (§18.6)?

    Two stages, because the cheap answer is wrong often enough to matter. Boxes
    first: they rule out almost every pair for nothing. What survives that gets
    asked properly — two parts that hook into each other have overlapping boxes
    and touch nowhere, and a report that calls those a collision is a report
    people learn to ignore.

    Where the exact answer cannot be had — an open body has no inside — the box
    stands, and the finding says which of the two it is.
    """
    findings: list[Finding] = []
    for first in range(len(meshes)):
        for second in range(first + 1, len(meshes)):
            if not _boxes_overlap(meshes[first].bounds, meshes[second].bounds, clearance):
                continue

            exact = _really_overlap(meshes[first], meshes[second], clearance)
            if exact is False:
                # Boxes overlap, bodies do not touch. That is an assembly, not
                # a problem, and saying so for every pair of a product would be
                # the noise that makes a report unreadable.
                continue
            findings.append(
                Finding(
                    code="arrange.collision",
                    severity="warning",
                    message=_("Zwei Objekte überschneiden sich."),
                    values={
                        "a": first,
                        "b": second,
                        "checked": "exact" if exact is not None else "box",
                    },
                )
            )
    return findings


def _really_overlap(first: MeshData, second: MeshData, clearance: float) -> bool | None:
    """Do the bodies share volume, or come closer than ``clearance``?

    ``None`` when that cannot be decided — an open body has no inside, and
    guessing one would turn a warning into a lie.

    The kernel is asked directly rather than through the fallback chain of
    §17.2. That chain treats an empty result as a failure and tries the next
    stage, which is right for a difference somebody wanted and wrong here: an
    empty intersection is not a failure, it is the answer.
    """
    if not (first.is_watertight and second.is_watertight):
        return None

    try:
        shared = trimesh.boolean.intersection([first.raw, second.raw])
    except Exception:  # a kernel that cannot answer has not said "no"
        return None

    if shared is not None and len(shared.faces) and abs(shared.volume) > EPS_GEOM:
        return True
    if clearance <= EPS_GEOM:
        return False

    # Apart, but perhaps not far enough. Measured from the surface, which is
    # what a spacing on the plate means.
    try:
        query = trimesh.proximity.ProximityQuery(first.raw)
        _closest, distance, _face = query.on_surface(np.asarray(second.raw.vertices, dtype=float))
    except Exception:
        return False
    return bool(len(distance)) and float(np.min(distance)) < clearance


def _boxes_overlap(first: BoundingBox, second: BoundingBox, clearance: float) -> bool:
    for axis in range(3):
        if first.maximum[axis] + clearance <= second.minimum[axis]:
            return False
        if second.maximum[axis] + clearance <= first.minimum[axis]:
            return False
    return True
