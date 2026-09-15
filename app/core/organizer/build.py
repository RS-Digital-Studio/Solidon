"""Den aufgelösten Organizer in einem Booleschen Schritt bauen (§24, §25)."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from shapely.geometry import MultiPoint, Polygon, box
from shapely.ops import unary_union

from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean
from app.core.geom.mesh import MeshData
from app.core.knowledge.parts.build import face
from app.core.knowledge.parts.containers import rounded_prism
from app.core.organizer.layout import OrganizerLayout, Rect
from app.core.organizer.serialize import invalid
from app.core.types import CancelToken, Feature, Finding, ProgressFn, Quality, SolverInfo, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _


@dataclass(frozen=True, slots=True)
class OrganizerBuild:
    """Geometrie, echte Merkmale und erreichte Rückfallstufe derselben Rechnung."""

    mesh: MeshData
    features: dict[str, Feature]
    solver: SolverInfo
    findings: tuple[Finding, ...] = ()


def _tool(rect: Rect, radius: float, bottom: float, top: float) -> MeshData:
    """Einen frischen Schneidkörper im gemeinsamen lokalen Rahmen platzieren."""
    mesh = rounded_prism(rect.width, rect.depth, top - bottom, radius)
    raw = mesh.raw.copy()
    raw.apply_translation((*rect.centre, bottom))
    return MeshData.of(raw)


def _patch(
    mesh: MeshData, identifier: str, normal: Vec3, position: float, region: Rect
) -> Feature | None:
    """Nur vorhandene ebene Dreiecke innerhalb der benannten Wandfläche ausweisen."""
    axis = next(index for index, component in enumerate(normal) if component)
    across = [index for index in range(3) if index != axis]
    raw = mesh.raw
    candidates = (np.linalg.norm(raw.face_normals - np.asarray(normal), axis=1) <= EPS_GEOM) & (
        np.abs(raw.triangles_center[:, axis] - position) <= EPS_GEOM
    )
    clip = box(region.x, region.y, region.x + region.width, region.y + region.depth)
    patches = [
        Polygon(triangle[:, across]).intersection(clip) for triangle in raw.triangles[candidates]
    ]
    patch = unary_union(patches)
    if patch.area <= EPS_GEOM**2:
        return None
    point = patch.representative_point()
    centre = [0.0, 0.0, 0.0]
    centre[axis] = position
    centre[across[0]], centre[across[1]] = point.x, point.y
    triangle_points = raw.triangles[:, :, across]
    contained = (
        (triangle_points[:, :, 0] >= region.x - EPS_GEOM)
        & (triangle_points[:, :, 0] <= region.x + region.width + EPS_GEOM)
        & (triangle_points[:, :, 1] >= region.y - EPS_GEOM)
        & (triangle_points[:, :, 1] <= region.y + region.depth + EPS_GEOM)
    ).all(axis=1)
    marker = face(identifier, float(patch.area), (centre[0], centre[1], centre[2]), normal)[1]
    return replace(marker, face_indices=tuple(map(int, np.flatnonzero(candidates & contained))))


def build_organizer(
    layout: OrganizerLayout,
    *,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    progress: ProgressFn | None = None,
) -> OrganizerBuild:
    """Alle Fachräume gemeinsam abziehen; Zwischenräume nicht einzeln erkennen."""
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    base = rounded_prism(layout.width, layout.depth, layout.height, layout.radius)
    outside = MultiPoint(np.asarray(base.raw.vertices)[:, :2]).convex_hull
    cutters: list[MeshData] = []
    features: dict[str, Feature] = dict(
        [face("organizer_base", float(outside.area), (0, 0, 0), (0, 0, -1))]
    )
    for index, cell in enumerate(layout.cells):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        tool = _tool(cell.rect, cell.radius, layout.floor, layout.height + BOOLEAN_OVERLAP)
        inside = MultiPoint(np.asarray(tool.raw.vertices)[:, :2]).convex_hull
        if not outside.covers(inside) or outside.boundary.distance(inside) <= EPS_GEOM:
            raise invalid(
                _(
                    "Ein Fach durchbricht die gerundete Außenwand. "
                    "Vergrößern Sie seinen Innenradius oder verkleinern Sie den Außenradius."
                )
            )
        cutters.append(tool)
        key, marker = face(
            f"{cell.id}/floor", float(inside.area), (*cell.rect.centre, layout.floor)
        )
        marker = replace(
            marker,
            params={
                **marker.params,
                "organizer_role": "floor",
                "organizer_id": cell.id,
                "width": cell.rect.width,
                "depth": cell.rect.depth,
                "radius": cell.radius,
                "opening_depth": layout.height - layout.floor,
            },
        )
        features[key] = marker
        if progress is not None:
            progress((index + 1) / (len(layout.cells) + 1) * 0.35, str(_("Fächer vorbereiten …")))
    for wall in layout.walls:
        if wall.height < layout.height - EPS_GEOM:
            cutters.append(
                _tool(wall.rect, wall.radius, wall.height, layout.height + BOOLEAN_OVERLAP)
            )
    outcome = boolean("difference", [base, *cutters], quality=quality, cancelled=cancelled)
    for cell in layout.cells:
        key = f"{cell.id}/floor"
        patch = _patch(outcome.mesh, key, (0, 0, 1), layout.floor, cell.rect)
        if patch is not None:
            features[key] = replace(features[key], face_indices=patch.face_indices)
    for wall in layout.walls:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        rect = wall.rect
        descriptors: list[tuple[str, Vec3, float, Rect]] = [("top", (0, 0, 1), wall.height, rect)]
        if wall.height > layout.floor + EPS_GEOM:
            vertical = Rect(
                rect.y if wall.axis == "x" else rect.x,
                layout.floor,
                rect.depth if wall.axis == "x" else rect.width,
                wall.height - layout.floor,
            )
            if wall.axis == "x":
                descriptors.extend(
                    [
                        ("side_a", (-1, 0, 0), rect.x, vertical),
                        ("side_b", (1, 0, 0), rect.x + rect.width, vertical),
                    ]
                )
            else:
                descriptors.extend(
                    [
                        ("side_a", (0, -1, 0), rect.y, vertical),
                        ("side_b", (0, 1, 0), rect.y + rect.depth, vertical),
                    ]
                )
        for suffix, normal, position, region in descriptors:
            key = f"{wall.id}/{suffix}"
            patch = _patch(outcome.mesh, key, normal, position, region)
            if patch is not None:
                features[key] = replace(
                    patch,
                    params={
                        **patch.params,
                        "organizer_role": "divider",
                        "organizer_id": wall.id,
                        "height_above_floor": wall.height - layout.floor,
                    },
                )
    if progress is not None:
        progress(1.0, str(_("Organizer berechnet.")))
    return OrganizerBuild(outcome.mesh, features, outcome.solver, tuple(outcome.findings))
