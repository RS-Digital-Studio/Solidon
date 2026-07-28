"""Feature detection (Bauplan §21.1).

What an STL does not say, this module works out: where the bores are, which
faces are flat, where the mesh is open. That vocabulary is what makes the rest
possible — the context menu on a bore, the agent that says "the hole on the top
face" instead of coordinates, the fit between a pin and its hole.

Bores are found by fitting a cylinder rather than by looking for round edges:
a fit has an axis, a radius and a residual, so the answer can be judged instead
of believed. Faces come from coplanar patches, open edges from the mesh itself.

Nothing here guesses in silence. What does not fit a shape simply is not a
feature, and the digest says how many were found.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData, face_components
from app.core.log import get_logger
from app.core.types import Feature, FeatureId, Vec3
from app.core.units import EPS_GEOM

_log = get_logger(__name__)

#: How well a patch has to fit a cylinder to count as a bore: the radius may
#: scatter by this share before the fit is rejected.
CYLINDER_TOLERANCE = 0.08

#: A patch needs at least this many triangles to be judged at all.
MIN_PATCH_FACES = 6

#: Faces smaller than this share of the largest one are not reported separately.
MIN_FACE_SHARE = 0.02


@dataclass(frozen=True, slots=True)
class CylinderFit:
    """A cylinder fitted through a patch of triangles."""

    axis: Vec3
    centre: Vec3
    radius: float
    residual: float
    """Mean deviation from the fitted radius, relative to the radius."""
    inward: bool
    """True when the normals point at the axis — that is a bore, not a pin."""

    @property
    def good(self) -> bool:
        return self.residual <= CYLINDER_TOLERANCE and self.radius > EPS_GEOM


def detect(mesh: MeshData) -> dict[FeatureId, Feature]:
    """Everything this module can recognise, with stable names."""
    found: dict[FeatureId, Feature] = {}
    for feature in [*detect_holes(mesh), *detect_faces(mesh), *detect_edge_loops(mesh)]:
        found[feature.id] = feature
    _log.info("detected %d features", len(found))
    return found


# --- bores ----------------------------------------------------------------------


def detect_holes(mesh: MeshData) -> list[Feature]:
    """Cylindrical patches whose normals point inwards (§21.1)."""
    body = mesh.raw
    if not len(body.faces):
        return []

    # A bore wall is made of many narrow flat segments, so "belongs to a facet"
    # is not the dividing line — "belongs to a *large* facet" is.
    planar = _large_facet_faces(body)
    curved = [index for index in range(len(body.faces)) if index not in planar]
    if not curved:
        return []

    found: list[tuple[CylinderFit, list[int]]] = []
    for patch in _connected_patches(body, curved):
        if len(patch) < MIN_PATCH_FACES:
            continue
        fit = fit_cylinder(body, patch)
        if fit is not None and fit.good and fit.inward:
            found.append((fit, patch))

    # Sorted by position, so the numbering is reproducible for the same body.
    found.sort(key=lambda entry: (round(entry[0].centre[0], 3), round(entry[0].centre[1], 3)))
    return [
        Feature(
            id=f"hole_{number}",
            kind="hole",
            provenance="detected",
            params={
                "diameter": round(fit.radius * 2.0, 4),
                "axis": fit.axis,
                "centre": fit.centre,
                "depth": round(_patch_extent(body, patch, fit.axis), 4),
                "through": _is_through(mesh, fit),
                "residual": round(fit.residual, 4),
            },
            face_indices=tuple(patch),
        )
        for number, (fit, patch) in enumerate(found, start=1)
    ]


def _large_facet_faces(body: trimesh.Trimesh) -> set[int]:
    """Triangles that belong to a flat patch big enough to be a face of its own."""
    facets = list(body.facets)
    if not facets:
        return set()
    areas = [float(body.area_faces[facet].sum()) for facet in facets]
    limit = max(areas) * MIN_FACE_SHARE
    return {
        int(index)
        for facet, area in zip(facets, areas, strict=True)
        if area >= limit
        for index in facet
    }


def fit_cylinder(body: trimesh.Trimesh, patch: list[int]) -> CylinderFit | None:
    """Least-squares cylinder through a patch of triangles.

    The axis is the direction every normal is perpendicular to — the eigenvector
    of the normal covariance with the smallest eigenvalue.
    """
    normals = np.asarray(body.face_normals[patch], dtype=float)
    centres = np.asarray(body.triangles_center[patch], dtype=float)

    _values, vectors = np.linalg.eigh(normals.T @ normals)
    axis = vectors[:, 0]
    axis = axis / float(np.linalg.norm(axis))

    # Project into the plane perpendicular to the axis and fit a circle there.
    basis_u, basis_v = _plane_basis(axis)
    flat = np.column_stack([centres @ basis_u, centres @ basis_v])
    centre_2d, radius = _fit_circle(flat)
    if radius <= EPS_GEOM:
        return None

    distances = np.linalg.norm(flat - centre_2d, axis=1)
    residual = float(np.mean(np.abs(distances - radius)) / radius)

    origin = centres.mean(axis=0)
    along = float(origin @ axis)
    centre = basis_u * centre_2d[0] + basis_v * centre_2d[1] + axis * along

    towards = centre - centres
    towards = towards - np.outer(towards @ axis, axis)
    inward = bool(np.mean(np.einsum("ij,ij->i", normals, towards)) > 0)

    return CylinderFit(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        radius=float(radius),
        residual=residual,
        inward=inward,
    )


def _plane_basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    basis_u = np.cross(axis, helper)
    basis_u = basis_u / float(np.linalg.norm(basis_u))
    return basis_u, np.cross(axis, basis_u)


def _fit_circle(points: np.ndarray) -> tuple[np.ndarray, float]:
    """Algebraic circle fit (Kåsa): linear, stable enough for a drilled hole."""
    matrix = np.column_stack([points[:, 0], points[:, 1], np.ones(len(points))])
    target = points[:, 0] ** 2 + points[:, 1] ** 2
    solution, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    centre = np.array([solution[0] / 2.0, solution[1] / 2.0])
    radius = math.sqrt(max(solution[2] + centre @ centre, 0.0))
    return centre, radius


def _patch_extent(body: trimesh.Trimesh, patch: list[int], axis: Vec3) -> float:
    """How far the patch reaches along its own axis — the depth of the bore."""
    points = np.asarray(body.vertices[np.unique(body.faces[patch])], dtype=float)
    along = points @ np.asarray(axis, dtype=float)
    return float(along.max() - along.min())


def _is_through(mesh: MeshData, fit: CylinderFit) -> bool:
    """A bore is through when it is as deep as the body is thick along its axis."""
    axis = np.asarray(fit.axis, dtype=float)
    corners = np.asarray(mesh.raw.vertices, dtype=float) @ axis
    thickness = float(corners.max() - corners.min())
    return thickness > 0 and _bore_depth(mesh, fit) >= thickness - EPS_GEOM * 10


def _bore_depth(mesh: MeshData, fit: CylinderFit) -> float:
    axis = np.asarray(fit.axis, dtype=float)
    centre = np.asarray(fit.centre, dtype=float)
    points = np.asarray(mesh.raw.vertices, dtype=float)
    radial = points - centre
    radial = radial - np.outer(radial @ axis, axis)
    on_wall = np.abs(np.linalg.norm(radial, axis=1) - fit.radius) < fit.radius * 0.1
    if not on_wall.any():
        return 0.0
    along = points[on_wall] @ axis
    return float(along.max() - along.min())


def _connected_patches(body: trimesh.Trimesh, faces: list[int]) -> list[list[int]]:
    """Group the given triangles into connected patches."""
    wanted = set(faces)
    adjacency = [
        pair for pair in np.asarray(body.face_adjacency) if pair[0] in wanted and pair[1] in wanted
    ]
    if not adjacency:
        return [[index] for index in faces]
    groups = trimesh.graph.connected_components(
        np.asarray(adjacency), nodes=np.asarray(faces), engine="scipy"
    )
    return [[int(index) for index in group] for group in groups]


# --- flat faces -----------------------------------------------------------------


def detect_faces(mesh: MeshData) -> list[Feature]:
    """Coplanar patches: normal, area, centre (§21.1)."""
    body = mesh.raw
    facets = list(body.facets)
    if not facets:
        return []

    areas = [float(body.area_faces[facet].sum()) for facet in facets]
    largest = max(areas)
    # The same threshold the bore detection uses, so a patch is either a face or
    # part of a curved surface — never both, never neither.
    entries = [
        (facet, area)
        for facet, area in zip(facets, areas, strict=True)
        if area >= largest * MIN_FACE_SHARE
    ]
    entries.sort(key=lambda entry: -entry[1])

    features: list[Feature] = []
    for number, (facet, area) in enumerate(entries, start=1):
        normal = np.asarray(body.face_normals[facet[0]], dtype=float)
        centre = np.asarray(body.triangles_center[facet], dtype=float).mean(axis=0)
        features.append(
            Feature(
                id=f"face_{number}",
                kind="face",
                provenance="detected",
                params={
                    "area": round(area, 4),
                    "normal": (float(normal[0]), float(normal[1]), float(normal[2])),
                    "centre": (float(centre[0]), float(centre[1]), float(centre[2])),
                },
                face_indices=tuple(int(index) for index in facet),
            )
        )
    return features


# --- open edges -----------------------------------------------------------------


def detect_edge_loops(mesh: MeshData) -> list[Feature]:
    """Open edges are defects, and knowing where they are is half the repair."""
    body = mesh.raw
    single = trimesh.grouping.group_rows(body.edges_sorted, require_count=1)
    if not len(single):
        return []

    edges = np.asarray(body.edges_sorted)[single]
    points = np.asarray(body.vertices[np.unique(edges)], dtype=float)
    centre = points.mean(axis=0)
    return [
        Feature(
            id="edge_loop_1",
            kind="edge_loop",
            provenance="detected",
            params={
                "open_edges": len(single),
                "centre": (float(centre[0]), float(centre[1]), float(centre[2])),
            },
        )
    ]


# --- components -----------------------------------------------------------------


def component_count(mesh: MeshData) -> int:
    """How many separate bodies the mesh holds (§21.1)."""
    return len(face_components(mesh.raw))
