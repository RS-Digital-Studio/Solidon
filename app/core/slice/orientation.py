"""Searching for a print orientation (Bauplan §22.3, §28.2).

This is what the analysis slicer is really for. Slicing externally meant three
to five candidates could be judged; slicing internally means hundreds — and the
judgement is real support volume instead of a rule of thumb over face normals.

The sampling is randomised by a stored seed (§11.3): a purely regular sampling
would systematically favour symmetric bodies, and without the seed the same file
would not search the same way twice.

The search is interruptible. Two hundred candidates take seconds, not
milliseconds, and §2.8 says nothing may block the window.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.geom.orient import candidates as face_candidates
from app.core.geom.transform import apply, place_on_bed
from app.core.log import get_logger
from app.core.slice.analysis import slice_body
from app.core.types import CancelToken, Finding, ProgressFn, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Layer height for the search. Coarser than a print: the ranking barely moves
#: below this, and it is what keeps hundreds of candidates affordable (§31).
SEARCH_LAYER_HEIGHT = 1.0

#: Default number of directions tried.
DEFAULT_CANDIDATES = 200


#: Support volumes within this share of each other count as equally good, and
#: then the first layer area decides. Without the tolerance, meshing noise would
#: pick the orientation.
SUPPORT_TIE = 0.05


@dataclass(frozen=True, slots=True)
class Candidate:
    """One direction, judged by what it would cost to print."""

    direction: Vec3
    support_volume: float
    first_layer_area: float
    height: float


def better(candidate: Candidate, current: Candidate) -> bool:
    """Less support wins; only at a tie does the first layer area decide (§22.2).

    Deliberately lexicographic rather than a weighted sum: a big footprint must
    never buy its way past real support material.
    """
    reference = max(candidate.support_volume, current.support_volume, EPS_GEOM)
    if abs(candidate.support_volume - current.support_volume) > reference * SUPPORT_TIE:
        return candidate.support_volume < current.support_volume
    return candidate.first_layer_area > current.first_layer_area


@dataclass(slots=True)
class SearchResult:
    """The winner, the field it won against, and what to tell the user."""

    mesh: MeshData
    best: Candidate
    tried: int
    baseline: Candidate
    """How the body stood before — so the gain can be stated, not claimed."""
    findings: list[Finding]

    @property
    def improvement(self) -> float:
        """Support volume saved against the starting position, in mm³."""
        return max(0.0, self.baseline.support_volume - self.best.support_volume)


def sample_directions(count: int, seed: int | None = None) -> list[Vec3]:
    """Evenly spread directions on the sphere, rotated by a seeded offset.

    A Fibonacci spiral spreads points evenly; the seeded rotation keeps a
    symmetric body from always landing on the same few axes.
    """
    generator = np.random.default_rng(seed or 0)
    offset = float(generator.random())
    golden = math.pi * (3.0 - math.sqrt(5.0))

    found: list[Vec3] = []
    for index in range(max(1, count)):
        z = 1.0 - 2.0 * (index + offset) / max(count, 1)
        z = float(np.clip(z, -1.0, 1.0))
        radius = math.sqrt(max(0.0, 1.0 - z * z))
        angle = golden * index
        found.append((radius * math.cos(angle), radius * math.sin(angle), z))
    return found


def judge(mesh: MeshData, direction: Vec3, layer_height: float) -> Candidate:
    """Turn the body so ``direction`` points down, then slice and count."""
    turned = place_on_bed(apply(mesh, _rotation_to_down(direction)))
    # §28.2: the search reads one number out of this. Measuring structure
    # widths on a body that is about to be turned again is work nobody looks at.
    result = slice_body(turned, layer_height, detail="support")
    return Candidate(
        direction=direction,
        support_volume=result.support_volume,
        first_layer_area=result.first_layer_area,
        height=turned.bounds.size[2],
    )


def _rotation_to_down(direction: Vec3) -> np.ndarray:
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


def search(
    mesh: MeshData,
    *,
    count: int = DEFAULT_CANDIDATES,
    seed: int | None = None,
    layer_height: float = SEARCH_LAYER_HEIGHT,
    progress: ProgressFn | None = None,
    cancelled: CancelToken | None = None,
) -> SearchResult:
    """Try many orientations and keep the one that needs the least support."""
    baseline = judge(mesh, (0.0, 0.0, -1.0), layer_height)
    best = baseline
    tried = 1

    # The face normals come along: the best orientation usually has a flat face
    # on the plate, and an even sampling of the sphere hits an exact axis only
    # by accident.
    directions = [*face_candidates(mesh), *sample_directions(count, seed)]
    for index, direction in enumerate(directions, start=1):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if progress is not None:
            progress(index / max(len(directions), 1), str(_("Ausrichtung suchen")))

        candidate = judge(mesh, direction, layer_height)
        tried += 1
        if better(candidate, best):
            best = candidate

    turned = place_on_bed(apply(mesh, _rotation_to_down(best.direction)))
    findings = [
        Finding(
            code="orient.searched",
            severity="info",
            message=_("Ausrichtung über die Schichtanalyse gesucht."),
            values={
                "candidates": tried,
                "support": round(best.support_volume / 1000.0, 2),
                "saved": round((baseline.support_volume - best.support_volume) / 1000.0, 2),
            },
            source="internal",
        )
    ]
    _log.info(
        "orientation search: %d candidates, support %.1f mm3 (was %.1f)",
        tried,
        best.support_volume,
        baseline.support_volume,
    )
    return SearchResult(mesh=turned, best=best, tried=tried, baseline=baseline, findings=findings)
