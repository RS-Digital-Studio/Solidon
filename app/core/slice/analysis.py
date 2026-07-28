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

import numpy as np
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

#: Steps of the binary search for the smallest structure width.
WIDTH_STEPS = 8


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
    for z in heights:
        shape = cross_section(mesh, float(z))
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
    section = mesh.raw.section(plane_origin=[0.0, 0.0, z], plane_normal=[0.0, 0.0, 1.0])
    if section is None:
        return None
    # Move the cut down onto Z = 0 rather than letting trimesh pick a frame:
    # every layer has to land in the same XY coordinates, otherwise comparing
    # one layer with the one below it compares two different maps.
    to_flat = np.eye(4)
    to_flat[2, 3] = -z
    try:
        planar, _transform = section.to_2D(to_2D=to_flat)
    except ValueError:  # pragma: no cover - degenerate sections
        return None
    polygons = list(planar.polygons_full)  # type: ignore[attr-defined]
    if not polygons:
        return None
    return unary_union(polygons)


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
    """
    if shape.is_empty:
        return 0.0
    low, high = 0.0, float(np.sqrt(shape.area))
    for _step in range(WIDTH_STEPS):
        middle = (low + high) / 2.0
        if shape.buffer(-middle).is_empty:
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
            outline=tuple((float(x), float(y)) for x, y in part.exterior.coords),
            holes=tuple(
                tuple((float(x), float(y)) for x, y in ring.coords) for ring in part.interiors
            ),
        )
        # A difference can hand back lines where two areas only touch. They carry
        # no area, so they are not contours — dropping them keeps the type honest.
        for part in parts
        if not part.is_empty and part.geom_type == "Polygon"
    )


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
