"""Dowel pins across a parting plane (Bauplan §25, §14).

A split part that is only glued has one job left for the person holding it:
lining the halves up while the glue grabs. Two pins take that job away, and
they are the reason auto split is worth having at all.

Where the pins go is decided on the cut face, not on the bounding box: the
section polygon is pulled in by the pin radius plus a wall, and what is left is
where material exists on both sides. Two pins along the long direction of that
region — one would let the halves twist.

The play is not a number here. It comes from the material profile
(AGENTS.md rule 7), so a calibration later reaches parts that were split
before it, and the fit pair records the reference rather than the value (§14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np

from app.core.geom.autosplit import Candidate, sections_along, upright
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, rotation, translation
from app.core.knowledge.parts.registry import PARTS
from app.core.log import get_logger
from app.core.types import Feature, FeatureId, Finding, Profile, Vec3
from app.i18n import _

_log = get_logger(__name__)

#: How many pins a seam gets. One pin is a hinge, three is a tolerance problem.
PIN_COUNT = 2

#: Pin diameter relative to the shorter side of the cut face, and the range it
#: is held to. Thin pins shear, fat ones weaken the part they sit in.
PIN_RELATIVE = 0.12
PIN_MIN = 3.0
PIN_MAX = 8.0

#: How deep a pin sits in each half, relative to its diameter.
PIN_DEPTH_FACTOR = 1.5

#: Material that has to stay around a pin. Below this the bore breaks out.
PIN_WALL = 1.6

#: Extra depth of the bore over the pin, so the halves close on the face and
#: not on the pin's end.
BORE_RELIEF = 0.4


@dataclass(frozen=True, slots=True)
class PinPlan:
    """Where the pins go, and how big they are."""

    positions: tuple[Vec3, ...]
    diameter: float
    length: float
    axis: str
    findings: tuple[Finding, ...] = ()

    @property
    def count(self) -> int:
        return len(self.positions)


@dataclass(slots=True)
class PinnedPair:
    """Both halves after pinning, with the features a fit pair needs."""

    first: MeshData
    second: MeshData
    pin_features: dict[FeatureId, Feature] = field(default_factory=dict)
    bore_features: dict[FeatureId, Feature] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


def plan_pins(
    mesh: MeshData, candidate: Candidate, *, count: int = PIN_COUNT, wall: float = PIN_WALL
) -> PinPlan:
    """Find room for pins on the cut face of ``candidate``.

    Returns a plan with no positions when the face is too small — a seam
    without pins still glues, and a pin that breaks out of the wall does not.
    """
    section = sections_along(mesh, cast(Any, candidate.axis), np.array([candidate.position]))[0]
    if section is None or section.is_empty:
        return PinPlan((), 0.0, 0.0, candidate.axis, (_no_face(),))

    largest = max(getattr(section, "geoms", (section,)), key=lambda entry: entry.area)
    diameter = _diameter(largest)
    inset = largest.buffer(-(diameter / 2.0 + wall))
    if inset.is_empty:
        return PinPlan((), 0.0, 0.0, candidate.axis, (_too_small(diameter, wall),))

    room = max(getattr(inset, "geoms", (inset,)), key=lambda entry: entry.area)
    points = _spread(room, count)
    length = diameter * PIN_DEPTH_FACTOR * 2.0
    return PinPlan(
        positions=tuple(_in_world(point, candidate) for point in points),
        diameter=diameter,
        length=length,
        axis=candidate.axis,
    )


def _diameter(section: Any) -> float:
    """From the narrowest direction of the face, held inside the usable range."""
    low_x, low_y, high_x, high_y = section.bounds
    narrow = min(high_x - low_x, high_y - low_y)
    return float(min(PIN_MAX, max(PIN_MIN, narrow * PIN_RELATIVE)))


def _spread(room: Any, count: int) -> list[tuple[float, float]]:
    """Points spread along the long direction of the usable region.

    Along the *long* direction on purpose: two pins close together hold about
    as well against twisting as one.
    """
    from shapely.geometry import Point
    from shapely.ops import nearest_points

    low_x, low_y, high_x, high_y = room.bounds
    horizontal = (high_x - low_x) >= (high_y - low_y)
    span = (low_x, high_x) if horizontal else (low_y, high_y)
    fixed = (low_y + high_y) / 2.0 if horizontal else (low_x + high_x) / 2.0

    points: list[tuple[float, float]] = []
    for index in range(count):
        along = span[0] + (span[1] - span[0]) * (2 * index + 1) / (2 * count)
        candidate = Point(along, fixed) if horizontal else Point(fixed, along)
        if not room.contains(candidate):
            candidate = nearest_points(room, candidate)[0]
        points.append((float(candidate.x), float(candidate.y)))
    return points


def _in_world(point: tuple[float, float], candidate: Candidate) -> Vec3:
    """A point of the section back in world coordinates.

    The section was taken with the cut axis turned upright, so the way back is
    that same turn inverted — not a table of sign flips that has to be right
    for three axes at once.
    """
    turned = np.array([point[0], point[1], candidate.position, 1.0])
    back = np.linalg.inv(upright(cast(Any, candidate.axis))) @ turned
    return (float(back[0]), float(back[1]), float(back[2]))


def add_pins(
    first: MeshData,
    second: MeshData,
    plan: PinPlan,
    profile: Profile,
    *,
    play: float | None = None,
) -> PinnedPair:
    """Put the pins into one half and the bores into the other.

    ``first`` carries the pins. Which half that is does not matter mechanically
    — what matters is that the two are told apart, because the fit pair names
    one of each (§14).
    """
    pair = PinnedPair(first=first, second=second, findings=list(plan.findings))
    if not plan.count:
        return pair

    clearance = profile.material.clearance if play is None else play
    pin_body = _part("dowel", diameter=plan.diameter, length=plan.length, kind="pin", play=0.0)
    bore_body = _part(
        "dowel",
        diameter=plan.diameter,
        length=plan.length / 2.0 + BORE_RELIEF,
        kind="bore",
        play=clearance,
    )

    for index, position in enumerate(plan.positions, start=1):
        placed_pin = _upright(pin_body, plan.axis, position, -plan.length / 2.0)
        placed_bore = _upright(bore_body, plan.axis, position, 0.0)

        pair.first = boolean("union", [pair.first, placed_pin]).mesh
        pair.second = boolean("difference", [pair.second, placed_bore]).mesh

        axis_vector = _axis_vector(plan.axis)
        pair.pin_features[f"pin_{index}"] = Feature(
            id=f"pin_{index}",
            kind="pin",
            provenance="generated",
            params={
                "diameter": round(plan.diameter, 4),
                "centre": position,
                "axis": axis_vector,
                "depth": round(plan.length / 2.0, 4),
            },
        )
        pair.bore_features[f"bore_{index}"] = Feature(
            id=f"bore_{index}",
            kind="hole",
            provenance="generated",
            params={
                "diameter": round(plan.diameter + clearance, 4),
                "centre": position,
                "axis": axis_vector,
                "depth": round(plan.length / 2.0 + BORE_RELIEF, 4),
            },
        )

    _log.info("pinned a seam with %d pin(s) of %.1f mm", plan.count, plan.diameter)
    return pair


def _part(name: str, **values: Any) -> MeshData:
    """One body from the library. Parts before primitives (§39), here as well."""
    from app.core.geom.mesh import as_mesh_data

    spec = PARTS.get(name)
    return as_mesh_data(spec.fn(spec.params(**values)).mesh)


def _upright(body: MeshData, axis: str, position: Vec3, offset: float) -> MeshData:
    """Lay a part that stands on +Z along the cut axis and move it into place."""
    placed = body
    if axis == "x":
        placed = apply(placed, rotation("y", 90.0))
    elif axis == "y":
        placed = apply(placed, rotation("x", -90.0))

    shift = [0.0, 0.0, 0.0]
    shift["xyz".index(axis)] = offset
    target = (position[0] + shift[0], position[1] + shift[1], position[2] + shift[2])
    return apply(placed, translation(target))


def _axis_vector(axis: str) -> Vec3:
    vector = [0.0, 0.0, 0.0]
    vector["xyz".index(axis)] = 1.0
    return (vector[0], vector[1], vector[2])


def _no_face() -> Finding:
    return Finding(
        code="split.no_cut_face",
        severity="warning",
        message=_("An der Trennebene war keine Schnittfläche zu finden."),
    )


def _too_small(diameter: float, wall: float) -> Finding:
    return Finding(
        code="split.face_too_small",
        severity="warning",
        message=_("Die Schnittfläche ist für Passstifte zu klein — geklebt hält sie trotzdem."),
        values={"diameter_mm": round(diameter, 2), "wall_mm": round(wall, 2)},
    )
