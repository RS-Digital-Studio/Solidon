"""Flat outlines with a height (Bauplan §25, "SVG und DXF mit Extrusion").

A logo, a gasket, a front panel, a template traced from a photo: two dimensions
plus a thickness is a large share of what gets printed, and the usual way there
is a detour through a modelling program. This is the short way.

Holes come out as holes. That sounds obvious and is the part that goes wrong in
naive implementations — a contour inside another contour is a hole, and the
nesting decides it, not the order the file lists them in. That work is trimesh's
here, and it does it right.

**Units.** SVG has no reliable unit: a file says 100 and means pixels,
millimetres or points depending on who wrote it. So the coordinates are read as
millimetres and there is a target width to say otherwise — a guess dressed up as
detection would be worse than a number somebody can see and change (§11.1).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import trimesh

from app.core.errors import PROGRAMMING_ERRORS, ValidationError
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: What this can read. Both come out of trimesh's path loaders.
OUTLINE_SUFFIXES: tuple[str, ...] = (".svg", ".dxf")


@dataclass(frozen=True, slots=True)
class OutlineResult:
    """The extruded body and what the outline looked like."""

    mesh: MeshData
    contours: int
    width: float
    """Width of the outline before scaling, in the file's own numbers."""


def is_outline(suffix: str) -> bool:
    return suffix.lower() in OUTLINE_SUFFIXES


def extrude(payload: bytes, suffix: str, height: float, width: float = 0.0) -> OutlineResult:
    """Read a flat drawing and give it a thickness.

    ``width`` scales the whole outline so it comes out that wide; zero takes
    the numbers in the file as millimetres.
    """
    if height <= EPS_GEOM:
        raise ValueError("an extrusion needs a positive height")
    if not is_outline(suffix):
        raise ValidationError(
            field="file",
            detail=_("Dieses Format ist keine flache Zeichnung."),
            value=suffix,
            constraint="not_outline",
        )

    try:
        path = trimesh.load_path(io.BytesIO(payload), file_type=suffix.lower().lstrip("."))
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # every parser fails in its own way
        raise ValidationError(
            field="file",
            detail=_("Die Zeichnung ließ sich nicht lesen."),
            constraint="unreadable",
            values={"suffix": suffix},
        ) from problem

    polygons = list(getattr(path, "polygons_full", ()) or ())
    if not polygons:
        raise ValidationError(
            field="file",
            detail=_("In dieser Zeichnung ist keine geschlossene Fläche."),
            constraint="no_area",
            values={"suffix": suffix},
        )

    bounds = path.bounds
    actual = float(bounds[1][0] - bounds[0][0])
    scale = (width / actual) if width > EPS_GEOM and actual > EPS_GEOM else 1.0

    parts = [trimesh.creation.extrude_polygon(entry, height=height) for entry in polygons]
    body = parts[0] if len(parts) == 1 else trimesh.util.concatenate(parts)
    if abs(scale - 1.0) > EPS_GEOM:
        # Only in the plane: the height was asked for in millimetres and does
        # not shrink because the drawing was scaled to a width.
        body.apply_scale([scale, scale, 1.0])
    # Onto the plate and centred: an outline drawn around some corner of a
    # drawing sheet would otherwise land wherever that corner was.
    body.apply_translation(-body.bounds[0] * [0, 0, 1] - [*body.centroid[:2], 0.0])

    _log.info("extruded %d contour(s) from %s", len(polygons), suffix)
    return OutlineResult(mesh=MeshData.of(body), contours=len(polygons), width=actual)
