"""Repairing meshes (Bauplan §25, §17.2).

Downloaded models are broken in a handful of recurring ways: open edges, needles,
duplicate faces, stray fragments, inverted normals, self-intersections. Each is
handled on its own here, and each reports what it did — the report has to be able
to say what was changed, and the agent has to know what it is standing on (§17.3).

Nothing repairs silently: an operation that changes geometry says so in its
findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData, face_components
from app.core.log import get_logger
from app.core.types import Finding
from app.core.units import EPS_GEOM, weld_tolerance
from app.i18n import _

_log = get_logger(__name__)

#: A component below this share of the largest one counts as a stray fragment.
SMALL_COMPONENT_SHARE = 0.001


@dataclass(slots=True)
class RepairResult:
    """The repaired body plus what each step actually did."""

    mesh: MeshData
    findings: list[Finding] = field(default_factory=list)
    changed: bool = False


def merge_vertices(mesh: MeshData, tolerance: float | None = None) -> tuple[MeshData, int]:
    """Weld coincident points. Returns the body and how many vertices went away."""
    body = mesh.raw.copy()
    before = len(body.vertices)
    limit = tolerance if tolerance is not None else weld_tolerance(mesh.bounds.diagonal)
    digits = max(0, min(12, round(float(-np.log10(max(limit, EPS_GEOM))))))
    body.merge_vertices(digits_vertex=digits)
    return mesh.replacing(body), before - len(body.vertices)


def remove_degenerate_faces(mesh: MeshData) -> tuple[MeshData, int]:
    """Zero-area triangles, needles and duplicates."""
    body = mesh.raw.copy()
    before = len(body.faces)
    body.update_faces(body.nondegenerate_faces(height=EPS_GEOM))
    body.update_faces(body.unique_faces())
    body.remove_unreferenced_vertices()
    return mesh.replacing(body), before - len(body.faces)


def unify_normals(mesh: MeshData) -> tuple[MeshData, bool]:
    """Make the winding consistent and turn the body outside out if needed."""
    body = mesh.raw.copy()
    before = float(body.volume)
    trimesh.repair.fix_winding(body)
    if body.is_watertight:
        trimesh.repair.fix_inversion(body)
    return mesh.replacing(body), abs(float(body.volume) - before) > EPS_GEOM


def fill_holes(mesh: MeshData) -> tuple[MeshData, bool]:
    """Close open edges. Small holes only — trimesh cannot bridge a missing wall."""
    body = mesh.raw.copy()
    if body.is_watertight:
        return mesh, False
    trimesh.repair.fill_holes(body)
    return mesh.replacing(body), bool(body.is_watertight)


def remove_small_components(
    mesh: MeshData, share: float = SMALL_COMPONENT_SHARE
) -> tuple[MeshData, int]:
    """Drop stray fragments — but only when asked, never on the way in (§17.1)."""
    pieces = face_components(mesh.raw)
    if len(pieces) <= 1:
        return mesh, 0
    areas = [float(mesh.raw.area_faces[piece].sum()) for piece in pieces]
    largest = max(areas)
    keep = [piece for piece, area in zip(pieces, areas, strict=True) if area >= largest * share]
    if len(keep) == len(pieces):
        return mesh, 0

    body = mesh.raw.copy()
    mask = np.zeros(len(body.faces), dtype=bool)
    for piece in keep:
        mask[piece] = True
    body.update_faces(mask)
    body.remove_unreferenced_vertices()
    return mesh.replacing(body), len(pieces) - len(keep)


def resolve_self_intersections(mesh: MeshData) -> tuple[MeshData, bool]:
    """Let the kernel rebuild the body; manifold3d normalises self-intersections.

    A union of a body with itself is a no-op on paper and a clean-up in practice.
    """
    try:
        rebuilt = trimesh.boolean.union([mesh.raw, mesh.raw])
    except Exception as problem:  # pragma: no cover - kernel specific
        _log.warning("could not resolve self-intersections: %s", problem)
        return mesh, False
    if rebuilt is None or not len(rebuilt.faces):
        return mesh, False
    return mesh.replacing(rebuilt), True


def repair(
    mesh: MeshData,
    *,
    weld: bool = True,
    degenerate: bool = True,
    normals: bool = True,
    holes: bool = True,
    small_components: bool = False,
    self_intersections: bool = False,
) -> RepairResult:
    """Run the requested steps in the order that makes each one cheaper."""
    result = RepairResult(mesh=mesh)

    if weld:
        result.mesh, removed = merge_vertices(result.mesh)
        if removed:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.welded",
                    severity="info",
                    message=_("Doppelte Punkte wurden verschweißt."),
                    values={"removed": removed},
                )
            )

    if degenerate:
        result.mesh, removed = remove_degenerate_faces(result.mesh)
        if removed:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.degenerate_removed",
                    severity="info",
                    message=_("Entartete Dreiecke wurden entfernt."),
                    values={"removed": removed},
                )
            )

    if small_components:
        result.mesh, dropped = remove_small_components(result.mesh)
        if dropped:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.components_removed",
                    severity="warning",
                    message=_("Kleinstteile wurden gelöscht."),
                    values={"removed": dropped},
                )
            )

    if self_intersections:
        result.mesh, rebuilt = resolve_self_intersections(result.mesh)
        if rebuilt:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.self_intersections",
                    severity="info",
                    message=_("Selbstdurchdringungen wurden aufgelöst."),
                )
            )

    if holes:
        result.mesh, closed = fill_holes(result.mesh)
        if closed:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.holes_filled",
                    severity="info",
                    message=_("Offene Stellen wurden geschlossen."),
                )
            )

    if normals:
        result.mesh, flipped = unify_normals(result.mesh)
        if flipped:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.normals_flipped",
                    severity="info",
                    message=_("Die Ausrichtung der Flächen wurde korrigiert."),
                )
            )

    if not result.mesh.is_watertight:
        result.findings.append(
            Finding(
                code="repair.still_open",
                severity="warning",
                message=_("Das Modell ist weiterhin nicht geschlossen."),
                values={"open_edges": open_edge_count(result.mesh)},
            )
        )
    return result


def open_edge_count(mesh: MeshData) -> int:
    """Edges belonging to a single triangle — the measure of "open"."""
    single = trimesh.grouping.group_rows(mesh.raw.edges_sorted, require_count=1)
    return len(single)
