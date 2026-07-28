"""Boolean operations with the fallback chain (Bauplan §17.2).

| Stage | What it does                                   | Recorded as |
|-------|------------------------------------------------|-------------|
| 1     | straight through the kernel                    | ``direct``  |
| 2     | weld, clean up, try again                      | ``welded``  |
| 3     | disturb the input geometry minimally           | ``jittered``|
| 4     | compute on voxels and mesh the result again    | ``voxel``   |
| 5     | give up, with a finding and a way forward      | —           |

The stage that succeeded is written into the operation, so the same file
recomputes the same way (§11.3) and the report can say what the numbers are
worth. Stage 4 costs accuracy and is never used silently.

In draft quality the chain stops after stage 2, to keep iterating fast (§31).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import trimesh

from app.core.errors import BooleanFailedError
from app.core.geom.attributes import DEFAULT_CUT_SLOT, transfer
from app.core.geom.mesh import MeshData
from app.core.geom.repair import merge_vertices, remove_degenerate_faces
from app.core.log import get_logger
from app.core.types import Finding, Quality, SolverInfo, SolverStage
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

BooleanKind = Literal["union", "difference", "intersection"]

#: The full chain, and the shortened one for draft quality (§31).
FULL_CHAIN: tuple[SolverStage, ...] = ("direct", "welded", "jittered", "voxel")
DRAFT_CHAIN: tuple[SolverStage, ...] = ("direct", "welded")

#: How far stage 3 moves the vertices: enough to break a coincidence, far below
#: anything a printer could resolve.
JITTER_AMPLITUDE = 1e-4

#: Edge length of the voxel grid in stage 4, relative to the model diagonal.
VOXEL_PITCH_RELATIVE = 0.004


@dataclass(slots=True)
class BooleanOutcome:
    """The result plus how it was reached."""

    mesh: MeshData
    solver: SolverInfo
    findings: list[Finding] = field(default_factory=list)


def boolean(
    kind: BooleanKind,
    meshes: list[MeshData],
    *,
    quality: Quality = "fine",
    seed: int | None = None,
    stages: tuple[SolverStage, ...] | None = None,
    cut_slot: int = DEFAULT_CUT_SLOT,
) -> BooleanOutcome:
    """Run a boolean operation, falling back stage by stage until one holds.

    ``cut_slot`` is what a newly cut face gets (§20): by default the slot of the
    body being cut, so a hole through a two-coloured part does not paint its
    wall in whatever the cutter happened to be.
    """
    if len(meshes) < 2:
        raise ValueError("a boolean operation needs at least two bodies")

    chain = stages if stages is not None else (FULL_CHAIN if quality == "fine" else DRAFT_CHAIN)
    attempted: list[SolverStage] = []

    for stage in chain:
        attempted.append(stage)
        try:
            result = _run_stage(kind, meshes, stage, seed)
        except Exception as problem:  # kernels fail in kernel-specific ways
            _log.info("boolean stage %s failed: %s", stage, problem)
            continue
        if result is None or not _plausible(result):
            _log.info("boolean stage %s produced nothing usable", stage)
            continue
        return BooleanOutcome(
            mesh=_keep_slots(result, meshes, kind, stage, cut_slot),
            solver=SolverInfo(
                strategy=stage,
                attempted=tuple(attempted),
                seed=seed if stage == "jittered" else None,
            ),
            findings=list(_findings_for(stage)),
        )

    raise BooleanFailedError(
        detail=_("Auch die letzte Rückfallstufe hat kein brauchbares Ergebnis geliefert."),
        attempted=tuple(attempted),
        seed=seed,
    )


def _keep_slots(
    result: MeshData,
    sources: list[MeshData],
    kind: BooleanKind,
    stage: SolverStage,
    cut_slot: int,
) -> MeshData:
    """§20: the slot assignment survives the operation.

    Kept as it is only where the kernel really handed the triangles through
    unchanged. After the voxel stage that is never the case — the meshing was
    replaced — so there the transfer always runs.

    Only the bodies that are still *in* the result hand their colour over. In a
    difference the tool is gone, and the bore wall it left behind is a new
    surface, not a piece of the drill — otherwise a hole through a red part
    would come out in whatever colour the cutter happened to have.
    """
    if stage != "voxel" and len(result.slots) == len(result.raw.faces) and result.slots:
        return result
    tolerance = None
    if stage == "voxel":
        # The staircase of the grid is half a voxel deep everywhere; measured
        # more tightly than that, the body would lose its colour to its own
        # tessellation rather than to the operation.
        diagonal = max(mesh.bounds.diagonal for mesh in sources)
        tolerance = max(diagonal * VOXEL_PITCH_RELATIVE, 0.05) * 1.5
    carriers = sources[:1] if kind == "difference" else sources
    return transfer(result, carriers, cut_slot=cut_slot, tolerance=tolerance)


def _run_stage(
    kind: BooleanKind, meshes: list[MeshData], stage: SolverStage, seed: int | None
) -> MeshData | None:
    if stage == "direct":
        return _kernel(kind, [mesh.raw for mesh in meshes], meshes[0])
    if stage == "welded":
        cleaned = [remove_degenerate_faces(merge_vertices(mesh)[0])[0] for mesh in meshes]
        return _kernel(kind, [mesh.raw for mesh in cleaned], meshes[0])
    if stage == "jittered":
        disturbed = [_jitter(mesh, seed, index) for index, mesh in enumerate(meshes)]
        return _kernel(kind, [mesh.raw for mesh in disturbed], meshes[0])
    return _voxel(kind, meshes)


def _kernel(kind: BooleanKind, bodies: list[trimesh.Trimesh], like: MeshData) -> MeshData | None:
    operation = {
        "union": trimesh.boolean.union,
        "difference": trimesh.boolean.difference,
        "intersection": trimesh.boolean.intersection,
    }[kind]
    result = operation(bodies)
    if result is None or not len(result.faces):
        return None
    return like.replacing(result)


def _jitter(mesh: MeshData, seed: int | None, index: int) -> MeshData:
    """Stage 3: nudge the vertices so coincident faces stop being coincident.

    The seed is stored with the operation, so the same nudge happens again
    (§11.3) — without it the result would be unreproducible.
    """
    generator = np.random.default_rng((seed or 0) + index)
    body = mesh.raw.copy()
    scale = max(mesh.bounds.diagonal, 1.0) * JITTER_AMPLITUDE
    body.vertices = body.vertices + generator.normal(scale=scale, size=body.vertices.shape)
    return mesh.replacing(body)


def _voxel(kind: BooleanKind, meshes: list[MeshData]) -> MeshData | None:
    """Stage 4: decide the question on a grid, then mesh the answer again.

    Robust where topology is not, and it costs accuracy — which is why the
    report says so whenever this stage was used (§17.3).
    """
    diagonal = max(mesh.bounds.diagonal for mesh in meshes)
    pitch = max(diagonal * VOXEL_PITCH_RELATIVE, 0.05)

    # One raster for all bodies. A difference only ever shrinks the first body,
    # everything else may grow beyond it, so the grid spans them all.
    low = np.min([np.asarray(mesh.bounds.minimum) for mesh in meshes], axis=0) - pitch * 2
    high = np.max([np.asarray(mesh.bounds.maximum) for mesh in meshes], axis=0) + pitch * 2
    shape = tuple(int(np.ceil(value)) for value in (high - low) / pitch + 1)

    combined = _rasterise(meshes[0], low, pitch, shape)
    for mesh in meshes[1:]:
        other = _rasterise(mesh, low, pitch, shape)
        if kind == "union":
            combined = combined | other
        elif kind == "difference":
            combined = combined & ~other
        else:
            combined = combined & other

    if not combined.any():
        return None
    body = trimesh.voxel.ops.matrix_to_marching_cubes(matrix=combined, pitch=pitch)
    # matrix_to_marching_cubes puts cell (0,0,0) at the origin; shift onto the raster.
    body.apply_translation(low)
    return meshes[0].replacing(body)


def _rasterise(
    mesh: MeshData, origin: np.ndarray, pitch: float, shape: tuple[int, ...]
) -> np.ndarray:
    """Put one body onto the shared raster."""
    grid = mesh.raw.voxelized(pitch=pitch).fill()
    offset = np.round((np.asarray(grid.transform)[:3, 3] - origin) / pitch).astype(int)
    target = np.zeros(shape, dtype=bool)
    source = np.asarray(grid.matrix, dtype=bool)

    starts = np.maximum(offset, 0)
    ends = np.minimum(offset + np.array(source.shape), np.array(shape))
    if np.any(ends <= starts):
        return target

    target_slice = tuple(slice(int(a), int(b)) for a, b in zip(starts, ends, strict=True))
    source_slice = tuple(
        slice(int(a - o), int(b - o)) for a, b, o in zip(starts, ends, offset, strict=True)
    )
    target[target_slice] = source[source_slice]
    return target


def _plausible(mesh: MeshData) -> bool:
    """A result has to have volume; an empty or inside-out body is not an answer."""
    return mesh.triangle_count > 0 and abs(mesh.volume) > EPS_GEOM


def _findings_for(stage: SolverStage) -> list[Finding]:
    if stage == "direct":
        return []
    if stage == "welded":
        return [
            Finding(
                code="boolean.welded",
                severity="info",
                message=_("Die Operation gelang erst nach dem Verschweißen."),
            )
        ]
    if stage == "jittered":
        return [
            Finding(
                code="boolean.jittered",
                severity="warning",
                message=_(
                    "Die Eingangsgeometrie wurde minimal gestört, um die Operation zu lösen."
                ),
            )
        ]
    return [
        Finding(
            code="boolean.voxel",
            severity="warning",
            message=_("Über die Voxelstufe gelöst — die Maße sind gerundet."),
        )
    ]
