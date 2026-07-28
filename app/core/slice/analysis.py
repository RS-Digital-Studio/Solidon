"""The analysis slicer (Bauplan §22).

Deliberately **not** a G-code slicer. Perimeters, seams, cooling, retraction and
machine limits are fifteen years of other people's work, and a worse answer would
cost the trust in the whole application. The file that goes to the printer keeps
coming from the external slicer (§28).

Cutting for *analysis* is a different matter, and the bigger lever: with numbers
per layer in milliseconds, the orientation search can judge hundreds of rotations
by real support volume instead of a rule of thumb (§22.3).

Every number here is ``internal``. It is never mixed with a figure measured from
G-code (§22.5) — an estimated support volume and a measured one are different
things, and the report says which is which.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import shapely
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.ops import unary_union

from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import LayerInfo, Polygon, SliceResult
from app.core.units import EPS_GEOM

_log = get_logger(__name__)

#: Smallest overhang that is not just meshing noise.
OVERHANG_MARGIN = 0.05

#: A layer may grow sideways by one layer height and still be printable — that
#: is exactly 45 degrees, the angle the rule set draws the line at (§39, §18.4).
#: Only what reaches further than this counts as an overhang.
OVERHANG_ANGLE_FACTOR = 1.0

#: Steps of the binary search for the smallest structure width. Six halvings of
#: a bracket that is already close leave under two percent.
WIDTH_STEPS = 6

#: How far the contour may be simplified before that search — a hundredth of a
#: millimetre is a tenth of what the finest nozzle can put down.
WIDTH_SIMPLIFY = 0.01


@dataclass(frozen=True, slots=True)
class LayerMetrics:
    """What one layer contributes to the judgement (§22.2)."""

    z: float
    area: float
    overhang_area: float
    island_area: float
    min_width: float
    bridge_width: float
    contour_count: int
    overhang: ShapelyPolygon | None = None
    """The unsupported region itself — the support map needs the place, not the number."""


def slice_body(mesh: MeshData, layer_height: float = 0.2) -> SliceResult:
    """Cut the body into layers and measure each one (§22.1, §22.2)."""
    if layer_height <= EPS_GEOM:
        raise ValueError("layer height has to be positive")

    bounds = mesh.bounds
    low, high = bounds.minimum[2], bounds.maximum[2]
    if high - low <= EPS_GEOM:
        return SliceResult(layers=(), support_volume=0.0, first_layer_area=0.0, source="internal")

    layers: list[LayerInfo] = []
    support = 0.0
    previous: ShapelyPolygon | None = None
    on_plate = True
    """The first layer with material rests on the build plate — it needs no
    support. A layer after a gap does not have that excuse."""

    # Half a layer above the bottom: the first cut has to hit material.
    heights = np.arange(low + layer_height / 2.0, high, layer_height)
    for z, shape in zip(heights, cross_sections(mesh, heights), strict=True):
        if shape is None or shape.is_empty:
            previous = None
            continue

        metrics = _measure(shape, previous, on_plate, layer_height)
        on_plate = False
        support += metrics.overhang_area * layer_height
        layers.append(
            LayerInfo(
                z=float(z),
                contours=_to_polygons(shape),
                area=metrics.area,
                overhang_area=metrics.overhang_area,
                islands=()
                if metrics.island_area <= EPS_GEOM
                else _to_polygons(_islands(shape, previous)),
                min_width=metrics.min_width,
                overhangs=()
                if metrics.overhang is None or metrics.overhang.is_empty
                else _to_polygons(metrics.overhang),
            )
        )
        previous = shape

    return SliceResult(
        layers=tuple(layers),
        support_volume=float(support),
        first_layer_area=layers[0].area if layers else 0.0,
        source="internal",
    )


def cross_section(mesh: MeshData, z: float) -> ShapelyPolygon | None:
    """One plane through the mesh, as a polygon with holes (§22.1).

    Public because the analysis maps raster the body out of these sections
    (§18.4) — the same cut, used twice.
    """
    return cross_sections(mesh, np.array([z], dtype=float))[0]


def cross_sections(mesh: MeshData, heights: Any) -> list[ShapelyPolygon | None]:
    """Many planes at once — the reason the layer analysis is usable at all.

    Cutting plane by plane means walking every triangle for every layer, and a
    body of two hundred thousand triangles sliced into four hundred layers walks
    eighty million of them. Here each triangle is sorted into the layers its own
    height reaches, so every layer only sees what actually crosses it.

    The coordinates stay the world's X and Y at every height. That is not a
    detail: comparing a layer with the one below it only means anything if both
    are drawn on the same map.
    """
    heights = np.asarray(heights, dtype=float)
    empty: list[ShapelyPolygon | None] = [None] * len(heights)
    if not len(heights) or not len(mesh.raw.faces):
        return empty

    points, layers = _plane_segments(mesh, heights)
    if not len(points):
        return empty

    order = np.argsort(layers, kind="stable")
    points, layers = points[order], layers[order]
    starts = np.searchsorted(layers, np.arange(len(heights)), side="left")
    ends = np.searchsorted(layers, np.arange(len(heights)), side="right")

    result: list[ShapelyPolygon | None] = []
    for start, end in zip(starts, ends, strict=True):
        result.append(_polygon_from(points[start:end]) if end > start else None)
    return result


def _plane_segments(mesh: MeshData, heights: Any) -> tuple[Any, Any]:
    """Where every triangle crosses every plane it reaches.

    Returns the segments as ``(n, 2, 2)`` points in XY and the layer each one
    belongs to.
    """
    triangles = np.asarray(mesh.raw.triangles, dtype=float)
    step = float(heights[1] - heights[0]) if len(heights) > 1 else 1.0
    base = float(heights[0])

    vertical = triangles[:, :, 2]
    first = np.ceil((vertical.min(axis=1) - base) / step - EPS_GEOM).astype(np.int64)
    last = np.floor((vertical.max(axis=1) - base) / step + EPS_GEOM).astype(np.int64)
    np.clip(first, 0, len(heights) - 1, out=first)
    np.clip(last, 0, len(heights) - 1, out=last)
    counts = np.maximum(last - first + 1, 0)
    counts[vertical.min(axis=1) > heights[-1]] = 0
    counts[vertical.max(axis=1) < heights[0]] = 0
    if not counts.sum():
        return np.empty((0, 2, 2)), np.empty(0, dtype=np.int64)

    faces = np.repeat(np.arange(len(triangles)), counts)
    within = np.arange(counts.sum()) - np.repeat(np.cumsum(counts) - counts, counts)
    layers = np.repeat(first, counts) + within
    z = heights[layers]

    corners = triangles[faces]
    height_above = corners[:, :, 2] - z[:, None]
    # The three edges of a triangle, as "from corner i to corner i+1".
    above = height_above > 0.0
    crossing = above != above[:, [1, 2, 0]]

    keep = crossing.sum(axis=1) == 2
    if not keep.any():
        return np.empty((0, 2, 2)), np.empty(0, dtype=np.int64)

    corners, height_above, crossing = corners[keep], height_above[keep], crossing[keep]
    rows = np.arange(len(corners))[:, None]
    # The two crossing edges, in the order the triangle names them.
    edges = np.argsort(~crossing, axis=1, kind="stable")[:, :2]

    start = corners[rows, edges]
    end = corners[rows, (edges + 1) % 3]
    start_height = height_above[rows, edges]
    end_height = height_above[rows, (edges + 1) % 3]

    span = start_height - end_height
    fraction = np.where(
        np.abs(span) > EPS_GEOM, start_height / np.where(span == 0.0, 1.0, span), 0.0
    )
    points = start[:, :, :2] + (end[:, :, :2] - start[:, :, :2]) * fraction[:, :, None]
    return points, layers[keep]


def _polygon_from(points: Any) -> ShapelyPolygon | None:
    """Build the filled area of one layer out of its loose segments.

    The segments come from triangles that share their corners exactly, so after
    rounding away the last floating point digits the ends match and GEOS can
    close the rings itself. What comes back are rings, not areas: an outer ring
    and the ring of a bore look the same. Which is which follows from how deep a
    ring sits inside the others — even is material, odd is a hole.
    """
    rounded = np.round(points.reshape(-1, 2), 6)
    lengths = np.linalg.norm(rounded[1::2] - rounded[0::2], axis=1)
    usable = np.repeat(lengths > 0.0, 2)
    if not usable.any():
        return None

    kept = rounded[usable]
    edges = shapely.linestrings(kept, indices=np.repeat(np.arange(len(kept) // 2), 2))
    built = shapely.polygonize(edges)
    parts = [part for part in getattr(built, "geoms", []) if not part.is_empty]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]

    # Only the outlines count for the nesting. GEOS hands back the bore of a
    # plate twice — once as the hole of the plate and once as a disc of its own —
    # and comparing the full shapes would let the disc look like an area outside
    # the plate rather than inside it.
    shells = [ShapelyPolygon(part.exterior) for part in parts]
    inside = [
        [
            other
            for other in range(len(shells))
            if other != index and shells[other].contains(shells[index].representative_point())
        ]
        for index in range(len(shells))
    ]
    solids = []
    for index, containers in enumerate(inside):
        if len(containers) % 2:
            continue
        holes = [
            shells[other].exterior
            for other, others in enumerate(inside)
            if len(others) == len(containers) + 1 and index in others
        ]
        solids.append(ShapelyPolygon(shells[index].exterior, holes))
    if not solids:
        return None
    return unary_union(solids)


def _measure(
    shape: ShapelyPolygon,
    previous: ShapelyPolygon | None,
    on_plate: bool = False,
    layer_height: float = 0.2,
) -> LayerMetrics:
    area = float(shape.area)
    region: ShapelyPolygon | None = None
    if on_plate:
        # Resting on the build plate is the one kind of support that is free.
        overhang = 0.0
        islands = 0.0
    elif previous is None or previous.is_empty:
        overhang = area
        islands = area
        region = shape
    else:
        reach = max(layer_height * OVERHANG_ANGLE_FACTOR, OVERHANG_MARGIN)
        supported = previous.buffer(reach)
        region = shape.difference(supported)
        overhang = float(region.area)
        islands = float(_islands(shape, previous).area)

    return LayerMetrics(
        z=0.0,
        area=area,
        overhang_area=overhang,
        island_area=islands,
        min_width=minimum_width(shape),
        bridge_width=_bridge_width(shape, previous),
        contour_count=_contour_count(shape),
        overhang=region,
    )


def _islands(shape: ShapelyPolygon, previous: ShapelyPolygon | None) -> ShapelyPolygon:
    """Contours with no connection downwards — these need support, always (§22.2)."""
    if previous is None or previous.is_empty:
        return shape
    parts = getattr(shape, "geoms", [shape])
    floating = [part for part in parts if not part.intersects(previous)]
    return unary_union(floating) if floating else ShapelyPolygon()


def minimum_width(shape: ShapelyPolygon) -> float:
    """Smallest structure width, found by eroding until nothing is left.

    Checkable against the nozzle diameter, which is what it is for (§22.2).

    Two liberties are taken for speed, and both stay far below what a printer
    can resolve: the contour is simplified by a hundredth of a millimetre first,
    and the erosion uses mitred corners instead of rounded ones. A layer of a
    detailed model brings thousands of points, and eroding those eight times
    over cost more than the whole rest of the analysis together.
    """
    if shape.is_empty or shape.length <= EPS_GEOM:
        return 0.0
    coarse = shape.simplify(WIDTH_SIMPLIFY)
    if coarse.is_empty:
        coarse = shape
    # Twice the area over the perimeter is the largest circle that can possibly
    # fit — for a disc and for a square it is exactly the inscribed one. Starting
    # there instead of at the diagonal keeps every probe small, and a small
    # erosion on a simplified contour is what makes this affordable at all.
    low, high = 0.0, 2.0 * float(shape.area) / float(shape.length)
    for _step in range(WIDTH_STEPS):
        middle = (low + high) / 2.0
        if coarse.buffer(-middle, quad_segs=1, join_style="mitre").is_empty:
            high = middle
        else:
            low = middle
    return float(low * 2.0)


def _bridge_width(shape: ShapelyPolygon, previous: ShapelyPolygon | None) -> float:
    """Longest free span in this layer — what has to be bridged (§22.2)."""
    if previous is None or previous.is_empty:
        return 0.0
    free = shape.difference(previous.buffer(OVERHANG_MARGIN))
    # Bridges are measured against the layer itself, not against the 45 degree
    # allowance: what spans free air is a bridge whatever its angle.
    if free.is_empty:
        return 0.0
    low, left, high, right = free.bounds
    return float(max(high - low, right - left))


def _contour_count(shape: ShapelyPolygon) -> int:
    return len(getattr(shape, "geoms", [shape]))


def _to_polygons(shape: ShapelyPolygon) -> tuple[Polygon, ...]:
    """Shapely to the core's own contour type — the core keeps its own vocabulary."""
    if shape.is_empty:
        return ()
    parts = getattr(shape, "geoms", [shape])
    return tuple(
        Polygon(
            outline=_ring(part.exterior),
            holes=tuple(_ring(ring) for ring in part.interiors),
        )
        # A difference can hand back lines where two areas only touch. They carry
        # no area, so they are not contours — dropping them keeps the type honest.
        for part in parts
        if not part.is_empty and part.geom_type == "Polygon"
    )


def _ring(ring: Any) -> tuple[tuple[float, float], ...]:
    """One contour as plain numbers. A detailed layer brings thousands of points,
    so the coordinates are pulled out in one call rather than one at a time."""
    return tuple(map(tuple, shapely.get_coordinates(ring).tolist()))


# --- judgements over the whole body ---------------------------------------------


def total_overhang(result: SliceResult) -> float:
    return float(sum(layer.overhang_area for layer in result.layers))


def island_layers(result: SliceResult) -> tuple[float, ...]:
    """Heights at which a contour starts in mid-air (§22.2)."""
    return tuple(layer.z for layer in result.layers if layer.islands)


def narrowest(result: SliceResult) -> float:
    """The thinnest structure anywhere in the body."""
    widths = [layer.min_width for layer in result.layers if layer.min_width > EPS_GEOM]
    return min(widths) if widths else 0.0
