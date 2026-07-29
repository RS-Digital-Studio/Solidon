"""Auto split: cutting a part until it fits on the plate (Bauplan §22.3, §25).

The parting plane is found with the same machinery as the orientation search —
the layer analysis (§22.3). For a set of cut positions the cross-section is
computed and judged, and the best one wins. What makes a section good is not
its size:

* **One contour, not five.** A plane through five thin arms leaves five thin
  bridges, and every one of them is a place the part breaks at.
* **Prismatic.** Where the section barely changes over a millimetre the cut
  runs through a straight stretch — the two faces meet flat, and a dowel finds
  material on both sides. Where it changes fast the plane is cutting across a
  curve.
* **Balanced.** Of two cuts that are equally good, the one nearer the middle
  wins: it takes fewer cuts to get everything onto the plate.

Where no plane helps at all, the convex decomposition is asked where the body
naturally comes apart, and the cut is placed there — as a plane, not as the
hulls themselves. Hull pieces are an approximation, and glueing an
approximation back together gives an approximate part (§11.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.geom.section import AXIS_NORMALS, Axis, SectionPlane
from app.core.log import get_logger
from app.core.slice.analysis import cross_sections
from app.core.types import Finding, Profile
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: How many cut positions are tried per axis. Enough to find the flat spot on a
#: real part, few enough that the search stays under a second.
SAMPLES = 33

#: How far the part has to stay below the build volume. Not decoration: a part
#: that exactly fills the plate cannot be arranged next to anything.
MARGIN = 2.0

#: Upper bound on the pieces. A part that needs more than this is not a split
#: problem, it is the wrong printer — and the report says so instead of running.
MAX_PARTS = 12

#: How far above and below a candidate the section is measured to see whether
#: the body is prismatic there.
PRISM_STEP = 0.5

#: Weights of the three criteria. Contours dominate on purpose: a seam that
#: falls apart into several bridges is worse than any amount of imbalance.
CONTOUR_WEIGHT = 1.0
PRISM_WEIGHT = 0.6
BALANCE_WEIGHT = 0.25

#: Above this score the sampled planes are all mediocre, and the convex
#: decomposition is asked for a second opinion.
HINT_THRESHOLD = 0.3

#: How much of the usable length the first cut takes off a body that is more
#: than twice too long. Not the full length: the search needs room to find a
#: seam, and a piece cut to the exact limit cannot be arranged next to anything.
FIRST_SLICE_SHARE = 0.7


@dataclass(frozen=True, slots=True)
class Candidate:
    """One possible parting plane, and what speaks for it."""

    axis: Axis
    position: float
    area: float
    contours: int
    score: float

    @property
    def plane(self) -> SectionPlane:
        return SectionPlane(normal=AXIS_NORMALS[self.axis], position=self.position)


@dataclass(frozen=True, slots=True)
class Step:
    """One cut of the plan: which piece was divided, and along which plane.

    The index is what turns a search result into a stack: the caller walks the
    steps in order and knows at every point which object the next cut applies
    to, without having to re-derive it from the geometry.
    """

    part_index: int
    plane: Candidate


@dataclass(slots=True)
class SplitOutcome:
    """The pieces, the cuts that made them, and what is worth saying about it."""

    parts: list[MeshData]
    cuts: list[Step] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def divided(self) -> bool:
        return len(self.parts) > 1


def oversize(
    mesh: MeshData, profile: Profile, margin: float = MARGIN
) -> tuple[float, float, float]:
    """How much the body sticks out of the build volume, per axis, in mm."""
    limits = [value - 2.0 * margin for value in profile.printer.build_volume]
    size = mesh.bounds.size
    return tuple(max(0.0, float(size[index]) - limits[index]) for index in range(3))  # type: ignore[return-value]


def fits(mesh: MeshData, profile: Profile, margin: float = MARGIN) -> bool:
    """Does the body fit on the plate at all, in the orientation it has?"""
    return max(oversize(mesh, profile, margin)) <= EPS_GEOM


def split_to_fit(
    mesh: MeshData,
    profile: Profile,
    *,
    max_parts: int = MAX_PARTS,
    samples: int = SAMPLES,
) -> SplitOutcome:
    """Cut until every piece fits, or until it is clear that cutting will not do it.

    Breadth first: the piece that sticks out furthest is cut next. That keeps
    the number of pieces down — cutting the worst offender first is what a
    person does with a saw, and for the same reason.
    """
    outcome = SplitOutcome(parts=[mesh])
    if fits(mesh, profile):
        return outcome

    while len(outcome.parts) < max_parts:
        index = _worst(outcome.parts, profile)
        if index is None:
            return outcome

        part = outcome.parts[index]
        candidate = find_plane(part, profile, samples=samples)
        if candidate is None:
            outcome.findings.append(
                Finding(
                    code="split.no_plane",
                    severity="warning",
                    message=_("Für dieses Teil war keine brauchbare Trennebene zu finden."),
                    values={"oversize_mm": round(max(oversize(part, profile)), 1)},
                )
            )
            return outcome

        first, second = _cut_in_two(part, candidate)
        if first is None or second is None:
            outcome.findings.append(
                Finding(
                    code="split.cut_failed",
                    severity="warning",
                    message=_("Der Schnitt hat kein zweites Teil ergeben."),
                    values={"axis": candidate.axis, "position": round(candidate.position, 2)},
                )
            )
            return outcome

        outcome.parts[index : index + 1] = [first, second]
        outcome.cuts.append(Step(part_index=index, plane=candidate))
        _log.info("split along %s at %.2f mm", candidate.axis, candidate.position)

    if _worst(outcome.parts, profile) is not None:
        outcome.findings.append(
            Finding(
                code="split.too_many_parts",
                severity="warning",
                message=_("Auch nach dem letzten Schnitt passt nicht jedes Teil auf das Bett."),
                values={"parts": len(outcome.parts), "limit": max_parts},
            )
        )
    return outcome


def _worst(parts: list[MeshData], profile: Profile) -> int | None:
    """Which piece sticks out furthest — or ``None`` when they all fit."""
    overshoot = [max(oversize(part, profile)) for part in parts]
    largest = max(overshoot, default=0.0)
    if largest <= EPS_GEOM:
        return None
    return overshoot.index(largest)


def find_plane(
    mesh: MeshData,
    profile: Profile,
    *,
    samples: int = SAMPLES,
) -> Candidate | None:
    """The best parting plane for this body, or ``None`` when none helps.

    Only planes that actually make the piece fit better count. A beautiful seam
    that leaves both halves too large is not an answer.
    """
    axis = _axis_to_cut(mesh, profile)
    if axis is None:
        return None

    window = _window(mesh, profile, axis)
    positions = np.linspace(window[0], window[1], samples)
    candidates = [entry for entry in _judge(mesh, axis, positions) if entry.area > EPS_GEOM]
    best = min(candidates, key=lambda entry: entry.score) if candidates else None
    if best is not None and best.score <= HINT_THRESHOLD:
        return best

    # Nothing convincing among the sampled planes: ask the decomposition where
    # the body comes apart by itself, and judge that position by the same rules.
    hinted = _from_decomposition(mesh, axis, window)
    if hinted is not None and (best is None or hinted.score < best.score):
        return hinted
    return best


def _axis_to_cut(mesh: MeshData, profile: Profile) -> Axis | None:
    """Cut across the direction that does not fit — the longest one that sticks out."""
    over = oversize(mesh, profile)
    if max(over) <= EPS_GEOM:
        return None
    return ("x", "y", "z")[int(np.argmax(over))]


def _window(mesh: MeshData, profile: Profile, axis: Axis) -> tuple[float, float]:
    """The range of cut positions worth trying.

    Normally that is where *both* halves come out short enough. A body more
    than twice as long as the plate has no such position — there the first cut
    takes off one piece that fits and leaves the rest for the next round, which
    is what somebody with a saw does too.
    """
    index = "xyz".index(axis)
    limit = profile.printer.build_volume[index] - 2.0 * MARGIN
    low = float(mesh.bounds.minimum[index])
    high = float(mesh.bounds.maximum[index])

    earliest = high - limit
    latest = low + limit
    if earliest <= latest:
        # Never cut so close to the end that a sliver comes off.
        inset = (high - low) * 0.05
        return (max(earliest, low + inset), min(latest, high - inset))
    return (low + limit * FIRST_SLICE_SHARE, low + limit)


def _judge(mesh: MeshData, axis: Axis, positions: np.ndarray) -> list[Candidate]:
    """Section the body at every candidate position and score what comes out."""
    heights = np.concatenate([positions - PRISM_STEP, positions, positions + PRISM_STEP])
    sections = sections_along(mesh, axis, heights)
    count = len(positions)
    below, middle, above = sections[:count], sections[count : 2 * count], sections[2 * count :]

    index = "xyz".index(axis)
    centre = float(mesh.bounds.centre[index])
    span = float(mesh.bounds.size[index]) or 1.0

    judged: list[Candidate] = []
    for position, under, here, over in zip(positions, below, middle, above, strict=True):
        if here is None or here.is_empty:
            continue
        area = float(here.area)
        contours = len(getattr(here, "geoms", (here,)))
        neighbours = [float(entry.area) for entry in (under, over) if entry is not None]
        change = max((abs(area - other) for other in neighbours), default=0.0) / max(area, EPS_GEOM)
        balance = abs(float(position) - centre) / (span / 2.0)
        judged.append(
            Candidate(
                axis=axis,
                position=float(position),
                area=area,
                contours=contours,
                score=(
                    CONTOUR_WEIGHT * (contours - 1)
                    + PRISM_WEIGHT * change
                    + BALANCE_WEIGHT * balance
                ),
            )
        )
    return judged


def upright(axis: Axis) -> np.ndarray:
    """The turn that puts ``axis`` on +Z. Identity for Z itself."""
    if axis == "z":
        return np.eye(4)
    return np.asarray(
        trimesh.geometry.align_vectors(np.asarray(AXIS_NORMALS[axis]), [0.0, 0.0, 1.0]),
        dtype=float,
    )


def sections_along(mesh: MeshData, axis: Axis, heights: np.ndarray) -> list[Any]:
    """Cross-sections along any axis, by turning that axis upright first.

    The layer analysis cuts along Z and does it well; rotating the body is
    cheaper than a second implementation, and it keeps the two answers
    comparable. The polygons are in the turned frame — :func:`upright` gives the
    matrix back, so a point on them can be put where it belongs in the world.
    """
    body = mesh
    if axis != "z":
        turned = mesh.raw.copy()
        turned.apply_transform(upright(axis))
        body = MeshData.of(turned)

    # The layer analysis sorts every triangle into the layers it reaches and
    # therefore expects the heights in order. The search asks for them in the
    # order it thought of them, so they are sorted here and put back after.
    order = np.argsort(np.asarray(heights, dtype=float))
    sections = cross_sections(body, np.asarray(heights, dtype=float)[order])
    result: list[Any] = [None] * len(order)
    for target, section in zip(order, sections, strict=True):
        result[int(target)] = section
    return result


def _cut_in_two(mesh: MeshData, candidate: Candidate) -> tuple[MeshData | None, MeshData | None]:
    """Both halves of one cut, each with its face closed (§25)."""
    from app.core.geom.prepare import split_at_plane

    first, second, _findings = split_at_plane(mesh, candidate.plane)
    return (
        first if first.triangle_count else None,
        second if second.triangle_count else None,
    )


def _from_decomposition(
    mesh: MeshData, axis: Axis, window: tuple[float, float]
) -> Candidate | None:
    """Ask where the body naturally comes apart, and judge cutting there.

    The convex decomposition is a hint, not the result: its hulls approximate
    the body, and a part glued together from approximations is an approximate
    part. What is taken from it is one number — the position where two of its
    pieces meet along the axis being cut.
    """
    pieces = convex_parts(mesh)
    if len(pieces) < 2:
        return None

    index = "xyz".index(axis)
    edges = {float(piece.bounds.maximum[index]) for piece in pieces}
    edges |= {float(piece.bounds.minimum[index]) for piece in pieces}
    inside = sorted(value for value in edges if window[0] <= value <= window[1])
    if not inside:
        return None

    judged = _judge(mesh, axis, np.array(inside))
    usable = [entry for entry in judged if entry.area > EPS_GEOM]
    return min(usable, key=lambda entry: entry.score) if usable else None


def convex_parts(mesh: MeshData, *, limit: int = 8) -> list[MeshData]:
    """Convex pieces of the body, largest first — empty when V-HACD is missing.

    No seed: this V-HACD offers no randomisation knob and returns the same
    hulls for the same body, which is what §11.3 wants of it. Without the
    module the answer is an empty list and the caller says so; it is an
    optional dependency and never a crash.
    """
    try:
        raw = mesh.raw.convex_decomposition(maxConvexHulls=limit)
    except Exception as problem:  # the module is optional, and V-HACD is C++
        _log.info("convex decomposition unavailable: %s", problem)
        return []
    pieces = raw if isinstance(raw, list) else [raw]
    bodies = [MeshData.of(entry) for entry in pieces if len(getattr(entry, "faces", ()))]
    return sorted(bodies, key=lambda entry: -abs(entry.volume))
