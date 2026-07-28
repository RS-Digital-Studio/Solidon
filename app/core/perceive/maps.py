"""Analysis maps (Bauplan §18.4).

Seven ways of looking at the same body: how thick it is, where it overhangs,
where the mesh is broken, how it curves, what the detection made of it, which
fits it takes part in, and where support will grow.

The maps are computed here, not in the viewport. The surface only needs the
numbers, the range and the unit — it paints them with the ramp from §19.1 and
draws the legend. That keeps the maps testable without a window, and it keeps
``core`` free of Qt.

Every number carries ``source="internal"`` (§22.5). A support estimate from the
layer analysis is not a measured value from G-code, and the legend says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import trimesh
from shapely.geometry import Point
from shapely.geometry import Polygon as ShapelyPolygon

from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.slice.analysis import cross_sections, slice_body
from app.core.types import (
    Feature,
    FeatureId,
    Finding,
    Fit,
    MetricSource,
    ObjectId,
    Profile,
    Scene,
    SceneObject,
    SliceResult,
    Vec3,
)
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

MapKind = Literal["wall", "overhang", "defects", "curvature", "features", "fits", "support"]

#: Above this a map is refused rather than computed for minutes (§31). The maps
#: shoot one ray per triangle, and that cost grows with the square of the mesh.
MAP_LIMIT_TRIANGLES = 120_000

#: Everything steeper than this needs support — the line the rule set draws (§39).
OVERHANG_LIMIT_DEGREES = 45.0

#: Face categories of the defect map, in the order their values run.
DEFECT_LEVELS = ("in Ordnung", "offene Kante", "Non-Manifold")

#: Face categories of the fit map.
FIT_LEVELS = ("unbeteiligt", "Teil einer Passung", "Passung verletzt")


@dataclass(frozen=True, slots=True)
class AnalysisMap:
    """One map over the triangles of a body.

    ``values`` holds one number per triangle. ``nan`` means "cannot say" — a ray
    that left the body without hitting anything is not a thickness of zero.
    """

    kind: MapKind
    title: TranslatableText | str
    values: tuple[float, ...]
    unit: str
    low: float
    high: float
    highlighted: tuple[int, ...] = ()
    """Triangles the map wants to point at: too thin, too steep, broken."""
    threshold: float | None = None
    """Where the highlight starts, in the unit of the map."""
    categories: tuple[str, ...] = ()
    """For maps whose values are levels rather than measurements."""
    source: MetricSource = "internal"
    note: TranslatableText | str | None = None
    """One line for the legend when the number needs a caveat (§22.5)."""
    resolution: float | None = None
    """Grid width in mm where the map was sampled rather than measured exactly."""

    @property
    def known(self) -> tuple[float, ...]:
        return tuple(value for value in self.values if not math.isnan(value))

    @property
    def unknown_count(self) -> int:
        return sum(1 for value in self.values if math.isnan(value))


class MapTooLarge(Exception):
    """The body has more triangles than a map is willing to walk (§31)."""

    def __init__(self, triangles: int) -> None:
        super().__init__(f"{triangles} triangles exceed the map limit {MAP_LIMIT_TRIANGLES}")
        self.triangles = triangles


TITLES: dict[MapKind, TranslatableText] = {
    "wall": _("Wandstärke"),
    "overhang": _("Überhang"),
    "defects": _("Netzfehler"),
    "curvature": _("Krümmung"),
    "features": _("Feature-Zuordnung"),
    "fits": _("Passungen"),
    "support": _("Stützbedarf"),
}


def build(
    kind: MapKind,
    entry: SceneObject,
    *,
    profile: Profile | None = None,
    scene: Scene | None = None,
) -> AnalysisMap:
    """The one entry point the surface uses; the rest is the map itself."""
    mesh = _mesh_of(entry)
    if mesh.triangle_count > MAP_LIMIT_TRIANGLES:
        raise MapTooLarge(mesh.triangle_count)

    if kind == "wall":
        return wall_thickness_map(mesh, profile.minimum_wall_thickness if profile else None)
    if kind == "overhang":
        return overhang_map(mesh)
    if kind == "defects":
        return defect_map(mesh)
    if kind == "curvature":
        return curvature_map(mesh)
    if kind == "features":
        return feature_map(mesh, entry.features)
    if kind == "fits":
        return fit_map(mesh, entry, scene)
    return support_map(mesh, profile.printer.layer_height if profile else 0.2)


def _mesh_of(entry: SceneObject) -> MeshData:
    mesh = entry.mesh
    if not isinstance(mesh, MeshData):  # pragma: no cover - only one kernel today
        raise TypeError("analysis maps need the trimesh backed mesh")
    return mesh


# --- the voxel field both distance maps live on ---------------------------------


@dataclass(frozen=True, slots=True)
class SolidField:
    """The body as a filled raster, plus the distance to the outside per voxel.

    Both distance maps need the same two questions answered — "is there material
    here" and "how far is it to the surface" — and both answers are far cheaper
    on a raster than as one ray per triangle: a ray per triangle grows with the
    square of the mesh, this grows with the volume and does not care how fine the
    mesh is.

    The raster comes out of the same cross sections the layer analysis uses
    (§22.1), not out of a mesh subdivision — a plate of twelve big triangles
    would take minutes to subdivide and takes milliseconds to cut.

    The price is resolution: everything read from this field is quantised to
    ``pitch``, and the legend says so rather than pretending otherwise.
    """

    filled: Any
    origin: Any
    """World position of voxel (0, 0, 0)."""
    pitch: float


#: The raster never gets finer than this many steps along the diagonal. A finer
#: grid buys accuracy nobody can print and costs memory nobody wants to spend.
MAX_GRID_STEPS = 300


def solid_field(mesh: MeshData, pitch: float | None = None) -> SolidField:
    """Raster the body: which cells hold material and which do not."""
    import shapely

    step = pitch if pitch is not None else default_pitch(mesh)
    low = np.asarray(mesh.bounds.minimum, dtype=float) - step
    high = np.asarray(mesh.bounds.maximum, dtype=float) + step
    # One empty cell all around, so a walk that leaves the body always lands on
    # something empty instead of falling off the raster.
    axes = [np.arange(low[axis], high[axis] + step, step) for axis in range(3)]
    filled = np.zeros(tuple(len(axis) for axis in axes), dtype=bool)

    grid_x, grid_y = np.meshgrid(axes[0], axes[1], indexing="ij")
    flat_x, flat_y = grid_x.ravel(), grid_y.ravel()
    # Every height in one pass. Cutting layer by layer walked all the triangles
    # once per layer — three hundred layers of a body with three hundred
    # thousand triangles is where the wall map spent most of its time.
    for index, shape in enumerate(cross_sections(mesh, axes[2])):
        if shape is None or shape.is_empty:
            continue
        inside = shapely.contains_xy(shape, flat_x, flat_y)
        filled[:, :, index] = inside.reshape(grid_x.shape)

    return SolidField(
        filled=filled,
        origin=np.array([axis[0] for axis in axes], dtype=float),
        pitch=step,
    )


def default_pitch(mesh: MeshData, extrusion_width: float = 0.42) -> float:
    """Half an extrusion width, but never more steps than the raster allows."""
    diagonal = float(mesh.bounds.diagonal)
    return max(extrusion_width / 2.0, diagonal / MAX_GRID_STEPS)


def _indices(field: SolidField, points: Any) -> Any:
    """World points as grid indices, clipped to the raster."""
    raw = (np.asarray(points, dtype=float) - field.origin) / field.pitch
    indices = np.rint(raw).astype(int)
    upper = np.asarray(field.filled.shape) - 1
    return np.clip(indices, 0, upper)


# --- thickness ------------------------------------------------------------------


def wall_thickness_map(
    mesh: MeshData, minimum: float | None = None, pitch: float | None = None
) -> AnalysisMap:
    """Thickness under every triangle: inwards along the normal to the far wall.

    The same question the measuring tool answers with a single ray (§18.3), so
    clicking a spot and looking at the map give the same number — up to the grid
    the map is sampled on. Where the walk finds no material at all the value is
    ``nan``: an open surface has no thickness, and zero would be a lie.
    """
    body = mesh.raw
    if not len(body.faces):
        return AnalysisMap(
            kind="wall", title=TITLES["wall"], values=(), unit="mm", low=0.0, high=0.0
        )

    field = solid_field(mesh, pitch)
    thickness = _inward_thickness(body, field)

    highlighted: tuple[int, ...] = ()
    if minimum is not None:
        highlighted = tuple(
            int(index)
            for index, value in enumerate(thickness)
            if not math.isnan(value) and value < minimum
        )
    known = [value for value in thickness if not math.isnan(value)]
    return AnalysisMap(
        kind="wall",
        title=TITLES["wall"],
        values=tuple(thickness),
        unit="mm",
        low=min(known) if known else 0.0,
        high=max(known) if known else 0.0,
        highlighted=highlighted,
        threshold=minimum,
        note=_("Untergrenze sind zwei Extrusionsbreiten.")
        if minimum is not None
        else _("Auf einem Raster abgetastet."),
        resolution=field.pitch,
    )


def _inward_thickness(body: trimesh.Trimesh, field: SolidField) -> list[float]:
    """Walk inwards from every triangle until the material runs out."""
    centres = np.asarray(body.triangles_center, dtype=float)
    normals = np.asarray(body.face_normals, dtype=float)

    # Nothing can be thicker than the body is long.
    steps = int(float(body.scale) / field.pitch) + 2
    reached = np.zeros(len(centres), dtype=float)
    inside = np.ones(len(centres), dtype=bool)

    for step in range(steps):
        points = centres - normals * (field.pitch * (step + 0.5))
        indices = _indices(field, points)
        here = field.filled[indices[:, 0], indices[:, 1], indices[:, 2]]
        # Once a walk has left the material it stops counting: what lies beyond
        # the far wall belongs to the next wall, not to this one.
        inside &= here
        if not inside.any():
            break
        reached += inside

    values = reached * field.pitch
    return [float(value) if value > 0.0 else float("nan") for value in values]


# --- overhang -------------------------------------------------------------------


def overhang_map(mesh: MeshData, limit: float = OVERHANG_LIMIT_DEGREES) -> AnalysisMap:
    """Angle against the build direction, zero for a vertical wall (§18.4).

    A wall parallel to Z is 0°, a ceiling facing straight down is 90°. Upward
    facing triangles are not overhangs at all, so they stay at zero instead of
    turning negative.
    """
    body = mesh.raw
    if not len(body.faces):
        return AnalysisMap(
            kind="overhang",
            title=TITLES["overhang"],
            values=(),
            unit="grad",
            low=0.0,
            high=0.0,
            threshold=limit,
        )

    downward = -np.asarray(body.face_normals, dtype=float)[:, 2]
    angles = np.degrees(np.arcsin(np.clip(downward, -1.0, 1.0)))
    angles = np.maximum(angles, 0.0)
    return AnalysisMap(
        kind="overhang",
        title=TITLES["overhang"],
        values=tuple(float(value) for value in angles),
        unit="grad",
        low=0.0,
        high=90.0,
        highlighted=tuple(int(index) for index in np.nonzero(angles > limit)[0]),
        threshold=limit,
        note=_("Über 45 Grad braucht die Fläche in aller Regel eine Stütze."),
    )


# --- mesh defects ---------------------------------------------------------------


def defect_map(mesh: MeshData) -> AnalysisMap:
    """Open edges and non-manifold edges, per triangle (§18.4)."""
    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    if len(body.faces):
        edges = np.asarray(body.edges_sorted)
        groups = trimesh.grouping.group_rows(edges, require_count=None)
        for group in groups:
            count = len(group)
            if count == 2:
                continue
            level = 1.0 if count == 1 else 2.0
            for edge in np.atleast_1d(np.asarray(group)):
                face = int(edge) // 3
                values[face] = max(values[face], level)

    return AnalysisMap(
        kind="defects",
        title=TITLES["defects"],
        values=tuple(float(value) for value in values),
        unit="",
        low=0.0,
        high=2.0,
        highlighted=tuple(int(index) for index in np.nonzero(values > 0.0)[0]),
        threshold=1.0,
        categories=DEFECT_LEVELS,
    )


# --- curvature ------------------------------------------------------------------


def curvature_map(mesh: MeshData) -> AnalysisMap:
    """Sharpest angle to a neighbour — edges stand out, fillets stay smooth."""
    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    pairs = np.asarray(body.face_adjacency)
    if len(pairs):
        angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
        for (first, second), angle in zip(pairs, angles, strict=True):
            values[int(first)] = max(values[int(first)], float(angle))
            values[int(second)] = max(values[int(second)], float(angle))

    return AnalysisMap(
        kind="curvature",
        title=TITLES["curvature"],
        values=tuple(float(value) for value in values),
        unit="grad",
        low=0.0,
        high=float(values.max()) if len(values) else 0.0,
        note=_("Zum Gegenprüfen, was die Merkmalserkennung als Kante sieht."),
    )


# --- what the detection saw -----------------------------------------------------


def feature_map(mesh: MeshData, features: dict[FeatureId, Feature]) -> AnalysisMap:
    """Every feature in its own level — "verstehen, was die KI sieht" (§18.4)."""
    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    names: list[str] = [str(_("ohne Merkmal"))]

    for level, (feature_id, feature) in enumerate(sorted(features.items()), start=1):
        names.append(feature_id)
        for index in feature.face_indices:
            if 0 <= index < len(values):
                values[index] = float(level)

    return AnalysisMap(
        kind="features",
        title=TITLES["features"],
        values=tuple(float(value) for value in values),
        unit="",
        low=0.0,
        high=float(len(names) - 1),
        categories=tuple(names),
    )


# --- fits (§14) -----------------------------------------------------------------


def fit_map(mesh: MeshData, entry: SceneObject, scene: Scene | None) -> AnalysisMap:
    """Which triangles take part in a fit, and which of those are violated."""
    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    if scene is not None:
        violated = _violated_features(scene, entry.id)
        for fit in scene.fits:
            for reference in (fit.a, fit.b):
                if reference.object_id != entry.id:
                    continue
                feature = entry.features.get(reference.feature_id)
                if feature is None:
                    continue
                level = 2.0 if reference.feature_id in violated else 1.0
                for index in feature.face_indices:
                    if 0 <= index < len(values):
                        values[index] = max(values[index], level)

    return AnalysisMap(
        kind="fits",
        title=TITLES["fits"],
        values=tuple(float(value) for value in values),
        unit="",
        low=0.0,
        high=2.0,
        highlighted=tuple(int(index) for index in np.nonzero(values >= 2.0)[0]),
        threshold=2.0,
        categories=FIT_LEVELS,
    )


def _violated_features(scene: Scene, object_id: ObjectId) -> set[FeatureId]:
    """Features named by a fit finding — the report is the single source (§14)."""
    names: set[FeatureId] = set()
    for finding in scene.report.findings:
        if not finding.code.startswith("fit."):
            continue
        if finding.object_id not in (None, object_id):
            continue
        names.update(finding.feature_ids)
    return names


def fits_of(scene: Scene, object_id: ObjectId) -> tuple[Fit, ...]:
    """Fits one object takes part in — used by the legend and the digest."""
    return tuple(fit for fit in scene.fits if object_id in (fit.a.object_id, fit.b.object_id))


# --- support (§22) --------------------------------------------------------------


def support_map(mesh: MeshData, layer_height: float = 0.2) -> AnalysisMap:
    """How tall the support column under each triangle would grow.

    The *judgement* — does this spot need support at all — comes from the layer
    analysis (§22): a triangle counts only if its centre falls into a layer's
    unsupported region. The *height* is the drop below it. Both are estimates
    from this application, never numbers measured from G-code (§22.5).
    """
    body = mesh.raw
    if not len(body.faces):
        return AnalysisMap(
            kind="support", title=TITLES["support"], values=(), unit="mm", low=0.0, high=0.0
        )

    result = slice_body(mesh, layer_height)
    regions = _overhang_regions(result)
    centres = np.asarray(body.triangles_center, dtype=float)
    field = solid_field(mesh)
    drops = _drop_below(mesh, field, centres)

    values = np.zeros(len(centres), dtype=float)
    marked: list[int] = []
    for index, centre in enumerate(centres):
        region = _region_at(regions, float(centre[2]), layer_height)
        if region is None or not _inside(region, float(centre[0]), float(centre[1])):
            continue
        values[index] = drops[index]
        marked.append(index)

    return AnalysisMap(
        kind="support",
        title=TITLES["support"],
        values=tuple(float(value) for value in values),
        unit="mm",
        low=0.0,
        high=float(values.max()) if len(values) else 0.0,
        highlighted=tuple(marked),
        note=_("Geschätzt aus der Schichtanalyse, nicht aus G-Code gemessen."),
        resolution=field.pitch,
    )


def _overhang_regions(result: SliceResult) -> list[tuple[float, list[Any]]]:
    """Layer height and its unsupported contours, as shapely shapes."""
    regions: list[tuple[float, list[Any]]] = []
    for layer in result.layers:
        shapes = [
            ShapelyPolygon(polygon.outline, polygon.holes)
            for polygon in layer.overhangs
            if len(polygon.outline) >= 4
        ]
        if shapes:
            regions.append((layer.z, shapes))
    return regions


def _region_at(
    regions: list[tuple[float, list[Any]]], z: float, layer_height: float
) -> list[Any] | None:
    for height, shapes in regions:
        if abs(height - z) <= layer_height:
            return shapes
    return None


def _inside(shapes: list[Any], x: float, y: float) -> bool:
    point = Point(x, y)
    return any(shape.intersects(point) for shape in shapes)


def _drop_below(mesh: MeshData, field: SolidField, centres: Any) -> Any:
    """How far it is straight down to the next material, or to the build plate.

    Read off the same raster the thickness map uses: in every column the highest
    filled voxel below the triangle is where a support column would land.
    """
    filled = field.filled
    height = filled.shape[2]
    ladder = np.arange(height).reshape(1, 1, height)
    # Highest filled voxel at or below each level, per column; -1 where none is.
    below = np.maximum.accumulate(np.where(filled, ladder, -1), axis=2)

    indices = _indices(field, centres)
    rows, columns, layers = indices[:, 0], indices[:, 1], indices[:, 2]
    # Two voxels down, so the triangle does not find the wall it sits on.
    start = np.maximum(layers - 2, 0)
    landing = below[rows, columns, start]

    plate = float(mesh.bounds.minimum[2])
    to_plate = centres[:, 2] - plate
    to_surface = (layers - landing) * field.pitch
    return np.maximum(np.where(landing >= 0, to_surface, to_plate), 0.0)


# --- where to fly ---------------------------------------------------------------


def focus_point(entry: SceneObject, analysis: AnalysisMap) -> Vec3 | None:
    """Centre of what the map highlights — where the camera should look (§18.4)."""
    if not analysis.highlighted:
        return None
    mesh = _mesh_of(entry)
    centres = np.asarray(mesh.raw.triangles_center, dtype=float)
    picked = centres[list(analysis.highlighted)]
    middle = picked.mean(axis=0)
    return (float(middle[0]), float(middle[1]), float(middle[2]))


def location_of(entry: SceneObject, finding: Finding) -> Vec3 | None:
    """Where a finding sits: its own location, or the centre of its features."""
    if finding.location is not None:
        return finding.location
    mesh = _mesh_of(entry)
    centres = np.asarray(mesh.raw.triangles_center, dtype=float)
    named = [entry.features[key] for key in finding.feature_ids if key in entry.features]
    indices = [
        index for feature in named for index in feature.face_indices if 0 <= index < len(centres)
    ]
    if not indices:
        return None
    middle = centres[indices].mean(axis=0)
    return (float(middle[0]), float(middle[1]), float(middle[2]))


def map_for(finding: Finding) -> MapKind | None:
    """Which map explains a finding — the shortest way from warning to place (§18.4)."""
    code = finding.code
    if code.startswith("fit."):
        return "fits"
    if code.startswith("perceive."):
        return "features"
    if code.startswith(("repair.", "ingest.", "mesh.")):
        return "defects"
    if "overhang" in code or code.startswith("orient."):
        return "overhang"
    if "wall" in code or "thin" in code:
        return "wall"
    if "support" in code:
        return "support"
    return None
