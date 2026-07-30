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

from app.core.errors import PROGRAMMING_ERRORS
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


#: How far a point may sit off an edge and still count as lying on it. A T-junction
#: comes from an exact split in the source CAD, so the deviation is arithmetic
#: noise rather than a gap.
ON_EDGE_TOLERANCE = 1e-4

#: Above this many open edges a body is not a model with a defect but a model in
#: pieces, and pairing every boundary vertex with every boundary edge stops being
#: the right way to spend a minute.
MAX_STITCH_EDGES = 4096


def stitch_t_junctions(mesh: MeshData) -> tuple[MeshData, int]:
    """Close gaps where a vertex sits on an edge that does not know about it.

    The defect the hole filler cannot touch, and the one a real download brings.
    An Eiffel tower of 312 000 triangles had exactly one: three open edges over
    three points at ``y=117,63, z=42,5`` and x of 100,910, 104,763 and 106,690 —
    3,853 + 1,927 = 5,780, collinear to the last digit. Not a hole, a **T-junction**:
    the long edge was split by a vertex when the neighbouring face was built, and
    the face on the other side was never told. ``trimesh.repair.fill_holes``
    declines it, and rightly so — a triangle over three collinear points has no
    area, and closing a body with a face that is not there is not closing it.

    What actually fits is to give the other face the vertex it is missing: the
    face on the long edge is split in two at the point sitting on it. No new
    geometry, no moved surface, and the two new triangles have the area the old
    one had.

    Returns the body and how many faces were split.
    """
    body = mesh.raw.copy()
    boundary = trimesh.grouping.group_rows(body.edges_sorted, require_count=1)
    if not len(boundary) or len(boundary) > MAX_STITCH_EDGES:
        return mesh, 0

    edges = body.edges_sorted[boundary]
    points = np.asarray(body.vertices, dtype=float)
    candidates = np.unique(edges)

    # Which face carries which boundary edge: edges_sorted runs three per face,
    # in face order, so the row index divided by three is the face.
    owner = {tuple(edges[index]): int(boundary[index] // 3) for index in range(len(edges))}

    splits: dict[int, list[tuple[int, int, int]]] = {}
    for edge, face_index in owner.items():
        start, end = points[edge[0]], points[edge[1]]
        for vertex in candidates:
            if vertex in edge:
                continue
            if _lies_on(points[vertex], start, end):
                splits.setdefault(face_index, []).append((edge[0], edge[1], int(vertex)))
                break

    if not splits:
        return mesh, 0

    faces = [list(map(int, face)) for face in body.faces]
    kept = np.ones(len(faces), dtype=bool)
    added: list[list[int]] = []
    for face_index, cuts in splits.items():
        first, second, vertex = cuts[0]
        face = faces[face_index]
        third = next((entry for entry in face if entry not in (first, second)), None)
        if third is None:
            continue
        # Keep the direction the face was wound in, so the two halves face the
        # same way the whole did.
        position = face.index(first)
        forward = face[(position + 1) % 3] == second
        head, tail = (first, second) if forward else (second, first)
        kept[face_index] = False
        added.extend([[head, vertex, third], [vertex, tail, third]])

    if not added:
        return mesh, 0

    rebuilt = np.vstack([np.asarray(body.faces)[kept], np.asarray(added, dtype=np.int64)])
    stitched = trimesh.Trimesh(vertices=body.vertices, faces=rebuilt, process=False)
    _log.info("stitched %d T-junction(s)", len(added) // 2)
    return mesh.replacing(stitched), len(added) // 2


def _lies_on(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> bool:
    """Is this point on the segment, between its ends rather than beyond them?"""
    along = end - start
    length = float(np.linalg.norm(along))
    if length <= EPS_GEOM:
        return False
    offset = point - start
    travelled = float(np.dot(offset, along)) / (length * length)
    if not (ON_EDGE_TOLERANCE < travelled < 1.0 - ON_EDGE_TOLERANCE):
        return False
    distance = float(np.linalg.norm(offset - travelled * along))
    return distance <= ON_EDGE_TOLERANCE * max(length, 1.0)


def fill_holes(mesh: MeshData) -> tuple[MeshData, bool]:
    """Close open edges. Small holes only — trimesh cannot bridge a missing wall.

    The stitch runs first: a T-junction looks like a hole and is not one, and the
    filler leaves it exactly as it found it (see :func:`stitch_t_junctions`).
    """
    body = mesh.raw.copy()
    if body.is_watertight:
        return mesh, False
    stitched, _seams = stitch_t_junctions(mesh.replacing(body))
    body = stitched.raw.copy()
    if body.is_watertight:
        return mesh.replacing(body), True
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
    except PROGRAMMING_ERRORS:
        raise
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
        # Said separately, because it is a different defect with a different
        # answer: a seam is a face that was missing a vertex, a hole is a face
        # that was missing. Somebody reading the report can tell whether their
        # model had a gap in it or only a bookkeeping error.
        result.mesh, seams = stitch_t_junctions(result.mesh)
        if seams:
            result.changed = True
            result.findings.append(
                Finding(
                    code="repair.t_junctions",
                    severity="info",
                    message=_("Kanten mit einem Punkt darauf wurden vernäht."),
                    values={"seams": seams},
                )
            )

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
