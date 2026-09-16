"""Geschlossene Dichtwege, Nuten und getrennte Dichtkörper in Millimetern."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any, cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import ValidationError
from app.core.geom.contours import offset_section, polygons_of, section_of
from app.core.geom.mesh import MeshData
from app.core.geom.sketch_solid import MAX_OUTLINE_POINTS
from app.core.sketch.profile import Profile as SketchProfile
from app.core.sketch.profile import ProfileSegment
from app.core.types import FeatureRef, PlaneFrame, Point2, SceneObject, Vec3
from app.core.units import EPS_GEOM, MAX_FACET_ANGLE, MAX_FACET_SAG
from app.i18n import _

# Bahn, Normalversatz und Querschnitt teilen sich die gemeinsame Sehnengrenze.
# Das engere Teilbudget lässt auch an gekrümmten Verläufen die Summe darunter.
_SEAL_SAG = MAX_FACET_SAG / 8
MAX_OPENING_SIGNATURE = 1_048_576


@dataclass(frozen=True, slots=True)
class OpeningChoice:
    """Eine sichtbare Wahl mit Datenquittung und aktuellem geometrischem Trägerrahmen."""

    profile: SketchProfile
    frame: PlaneFrame
    area: float
    centre: Point2
    topology: str
    carrier: Any
    ring: Any

    @property
    def signature(self) -> str:
        """Die gemeinsame Trägerkontur erst für eine gespeicherte Wahl serialisieren."""
        parts = list(getattr(self.carrier, "geoms", [self.carrier]))
        return json.dumps(
            {
                "version": 1,
                "topology": self.topology,
                "carrier": [
                    {
                        "outer": list(part.exterior.coords),
                        "holes": [list(hole.coords) for hole in part.interiors],
                    }
                    for part in parts
                ],
                "ring": list(self.ring.exterior.coords),
            },
            separators=(",", ":"),
            allow_nan=False,
        )


def polygon_profile(polygon: Any) -> SketchProfile:
    """Ein aufgelöster polygonaler Umriss samt Löchern im vorhandenen Profilvertrag."""
    points = list(polygon.exterior.coords)
    return SketchProfile(
        segments=tuple(
            ProfileSegment("line", tuple(first), tuple(second))
            for first, second in pairwise(points)
        ),
        holes=tuple(polygon_profile(_polygon(ring)) for ring in polygon.interiors),
    )


def _polygon(points: Any) -> Any:
    """Shapely erst dort laden, wo der gemeinsame Konturvertrag ausgewertet wird."""
    from shapely.geometry import Polygon

    return Polygon(points)


def _signature_error() -> ValidationError:
    return ValidationError(
        field="opening_signature",
        constraint="seal_opening_signature",
        detail=_(
            "Die gespeicherte Öffnungswahl ist nicht lesbar. "
            "Wählen Sie die gewünschte Kontur erneut auf der Trägerfläche."
        ),
    )


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Doppelte Datenschlüssel nicht still mit dem letzten Wert überschreiben."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _signature_error()
        result[key] = value
    return result


def _read_signature(text: str) -> tuple[str, Any, Any]:
    """Versionierte Daten mit vollständiger Mengen-, Typ- und Geometrieprüfung."""
    from shapely.ops import unary_union

    if len(text) > MAX_OPENING_SIGNATURE:
        raise _signature_error()
    try:
        payload = json.loads(text, object_pairs_hook=_unique_keys)
    except (ValueError, RecursionError) as problem:
        raise _signature_error() from problem
    if (
        not isinstance(payload, dict)
        or set(payload) != {"version", "topology", "carrier", "ring"}
        or type(payload["version"]) is not int
        or payload["version"] != 1
        or not isinstance(payload["topology"], str)
        or len(payload["topology"]) != 64
        or any(character not in "0123456789abcdef" for character in payload["topology"])
        or not isinstance(payload["carrier"], list)
        or not payload["carrier"]
    ):
        raise _signature_error()
    count = 0

    def ring(value: Any) -> Any:
        nonlocal count
        if not isinstance(value, list) or len(value) < 4:
            raise _signature_error()
        count += len(value)
        if count > MAX_OUTLINE_POINTS:
            raise _signature_error()
        for point in value:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(not _finite_number(v) for v in point)
            ):
                raise _signature_error()
        polygon = _polygon(value)
        if not polygon.is_valid or not math.isfinite(polygon.area) or polygon.area <= EPS_GEOM**2:
            raise _signature_error()
        if math.dist(value[0], value[-1]) > EPS_GEOM:
            raise _signature_error()
        return polygon

    polygons = []
    for part in payload["carrier"]:
        if (
            not isinstance(part, dict)
            or set(part) != {"outer", "holes"}
            or not isinstance(part["holes"], list)
        ):
            raise _signature_error()
        outer = ring(part["outer"])
        holes = [ring(hole) for hole in part["holes"]]
        polygon = type(outer)(outer.exterior, [hole.exterior for hole in holes])
        if not polygon.is_valid:
            raise _signature_error()
        polygons.append(polygon)
    selected = ring(payload["ring"])
    return payload["topology"], unary_union(polygons), selected


def _finite_number(value: Any) -> bool:
    """Auch große JSON-Ganzzahlen ohne Überlauf in einen Bedienfehler überführen."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def support_geometry(
    source: SceneObject,
    support: FeatureRef,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[PlaneFrame, Any, str]:
    """Die echte gewählte Planfläche samt lokalem Rahmen und Topologie.

    Die erste belegte Dreieckskante spannt den lokalen Rahmen auf. Starre
    Bewegungen führen sie genauso mit wie ihre Fläche; eine Weltachse würde
    beim Drehen des Trägers die gespeicherte Öffnungswahl zurücklassen.
    Topologie und vollständige Konturen bestätigen später diesen Rahmen.
    """
    from shapely.ops import unary_union

    from app.core.geom.faces import _must_be_flat, _triangles_of, face_normal
    from app.core.geom.mesh import as_mesh_data

    if check_cancelled is not None:
        check_cancelled()
    feature = source.features.get(support.feature_id)
    if support.object_id != source.id or feature is None or feature.kind != "face":
        raise ValidationError(
            field="support_feature",
            constraint="seal_support_face",
            detail=_("Wählen Sie eine vorhandene ebene Trägerfläche für den Dichtweg."),
        )
    mesh = as_mesh_data(source.mesh)
    indices = _triangles_of(mesh, feature)
    normal = np.asarray(face_normal(feature), dtype=float)
    normal /= np.linalg.norm(normal)
    _must_be_flat(mesh, indices, normal)
    triangles = np.asarray(mesh.raw.triangles)[indices]
    origin = triangles[0, 0]
    tangent = triangles[0, 1] - origin
    tangent -= normal * float(np.dot(tangent, normal))
    length = float(np.linalg.norm(tangent))
    if length <= EPS_GEOM:
        raise _signature_error()
    tangent /= length
    second = np.cross(normal, tangent)
    basis = np.column_stack((tangent, second, normal))
    local = (triangles - origin) @ basis
    if np.max(np.abs(local[:, :, 2])) > EPS_GEOM:
        raise _signature_error()
    projected = unary_union([_polygon(triangle[:, :2]) for triangle in local]).simplify(
        EPS_GEOM,
        preserve_topology=True,
    )
    parts = list(getattr(projected, "geoms", [projected]))
    if not projected.is_valid or any(part.geom_type != "Polygon" for part in parts):
        raise _signature_error()
    frame = PlaneFrame(
        origin=cast(Vec3, tuple(float(value) for value in origin)),
        x_axis=cast(Vec3, tuple(float(value) for value in tangent)),
        y_axis=cast(Vec3, tuple(float(value) for value in second)),
        normal=cast(Vec3, tuple(float(value) for value in normal)),
    )
    topology = hashlib.sha256(
        np.asarray(mesh.raw.faces[indices], dtype="<i8").tobytes()
    ).hexdigest()
    return frame, projected, topology


def opening_choices(
    source: SceneObject,
    support: FeatureRef,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[OpeningChoice, ...]:
    """Alle echten Innenringe genau der gewählten Planfläche; keine Größenauswahl."""
    frame, projected, topology = support_geometry(source, support, check_cancelled=check_cancelled)
    parts = list(getattr(projected, "geoms", [projected]))
    choices = []
    for part in parts:
        for hole in part.interiors:
            if check_cancelled is not None:
                check_cancelled()
            polygon = _polygon(hole)
            choices.append(
                OpeningChoice(
                    profile=polygon_profile(polygon),
                    frame=frame,
                    area=float(polygon.area),
                    centre=(float(polygon.centroid.x), float(polygon.centroid.y)),
                    topology=topology,
                    carrier=projected,
                    ring=polygon,
                )
            )
    # Alle Wahlen teilen dieselbe Fläche. Die größte gespeicherte Datenmenge
    # wird einmal geprüft; daraus wird ausdrücklich keine Kontur ausgewählt.
    if choices:
        largest = max(
            choices, key=lambda choice: len(json.dumps(list(choice.ring.exterior.coords)))
        )
        _read_signature(largest.signature)
    return tuple(sorted(choices, key=lambda choice: (*choice.centre, choice.area)))


def match_opening(choices: Sequence[OpeningChoice], signature: str) -> OpeningChoice | None:
    """Nur eine belegte eindeutige Wiederfindung; sonst muss die Operation neu fragen."""
    topology, carrier, ring = _read_signature(signature)
    found = []
    carriers: dict[int, bool] = {}
    for choice in choices:
        carrier_key = id(choice.carrier)
        if carrier_key not in carriers:
            carriers[carrier_key] = (
                carrier.boundary.hausdorff_distance(choice.carrier.boundary) <= EPS_GEOM
            )
        if (
            choice.topology == topology
            and carriers[carrier_key]
            and ring.boundary.hausdorff_distance(choice.ring.boundary) <= EPS_GEOM
        ):
            found.append(choice)
    return found[0] if len(found) == 1 else None


@dataclass(frozen=True, slots=True)
class SealGeometry:
    """Neue lokale Körper: Nutmündung Z=0, beide Böden bei -Nuttiefe.

    ``clearance`` bezeichnet das eingegebene seitliche Nennspiel. Die
    spätere Partnerprüfung misst zusätzlich die wirklichen Körper und
    verwechselt diese geometrische Aussage nicht mit einer Dichtheitszusage.
    """

    groove: MeshData
    gasket: MeshData
    clearance: float


def _closed_path() -> ValidationError:
    return ValidationError(
        field="path_sketch",
        constraint="seal_closed_path",
        detail=_(
            "Der Dichtweg braucht genau eine geschlossene Kontur ohne Innenringe. "
            "Wählen oder zeichnen Sie einen durchgängigen Verlauf."
        ),
    )


def _single(section: Any) -> Any:
    """Einzelne gefüllte Kontur verlangen, bevor aus ihrem Rand ein Ring wird."""
    polygons = polygons_of(section)
    if len(polygons) != 1 or polygons[0].interiors:
        raise _closed_path()
    return polygons[0]


def _band(path: Any, width: float, check: Callable[[], None] | None) -> Any:
    """Ein echter Normalversatz beider Ränder; verengte Wege nicht verschlucken."""
    outside = offset_section(path, width / 2, max_sag=_SEAL_SAG, check_cancelled=check)
    inside = offset_section(path, -width / 2, max_sag=_SEAL_SAG, check_cancelled=check)
    _single(outside)
    _single(inside)
    ring = outside - inside
    polygons = polygons_of(ring)
    if len(polygons) != 1 or len(polygons[0].interiors) != 1:
        raise _closed_path()
    return ring


def _mesh(body: Any) -> MeshData:
    """Manifolds Float64-Ergebnis ohne eine zweite Reparatur übernehmen."""
    built = body.to_mesh64()
    result = MeshData.of(
        trimesh.Trimesh(
            vertices=np.array(built.vert_properties[:, :3], copy=True),
            faces=np.array(built.tri_verts, copy=True),
            process=False,
        )
    )
    if not result.is_watertight or result.component_count != 1 or result.volume <= EPS_GEOM**3:
        raise _closed_path()
    return result


def _round_tube(path: Any, radius: float, centre_z: float, check: Callable[[], None] | None) -> Any:
    """Geschlossener Kugelsweep: echte runde Übergänge auch an scharfen Ecken.

    Jede Kapsel ist die konvexe Hülle zweier identisch facettierter Kugeln.
    Die gemeinsame Vereinigung begrenzt konkave Ecken tatsächlich; ein
    gemittelter Ecknormalenvektor würde dort einen anderen Querschnitt
    behaupten oder sich selbst durchdringen. Alle Werkzeuge bleiben Manifold.
    """
    import manifold3d

    points = list(_single(path).exterior.coords)[:-1]
    if len(points) > MAX_OUTLINE_POINTS:
        raise _closed_path()
    angle = min(MAX_FACET_ANGLE, 2 * math.acos(max(0.0, 1 - _SEAL_SAG / radius)))
    steps = max(8, 4 * math.ceil(math.tau / angle / 4))
    sphere = manifold3d.Manifold.sphere(radius, circular_segments=steps)
    tools: list[Any] = []
    for index, (x, y) in enumerate(points):
        if check is not None:
            check()
        next_x, next_y = points[(index + 1) % len(points)]
        length = math.hypot(next_x - x, next_y - y)
        if length <= EPS_GEOM:
            raise _closed_path()
        # Ein separat facettierter Zylinder und eine Kugel teilen ihren
        # Äquator nicht exakt: winzige Sichelkappen blieben innerhalb des
        # Sweeps stehen. Die Hüllen teilen dieselben Kugelfacetten und
        # schließen am gemeinsamen Bahnpunkt ohne solche inneren Enden.
        tools.append(
            manifold3d.Manifold.batch_hull(
                [
                    sphere.translate((x, y, centre_z)),
                    sphere.translate((next_x, next_y, centre_z)),
                ]
            )
        )
    result = manifold3d.Manifold.batch_boolean(tools, manifold3d.OpType.Add)
    if check is not None:
        check()
    # Rein numerische Splitter bleiben unter der gemeinsamen
    # Verschweißtoleranz; die Topologie der Hülle bleibt erhalten.
    return result.simplify(EPS_GEOM)


def seal_geometry(
    profile: SketchProfile,
    *,
    groove_width: float,
    groove_depth: float,
    protrusion: float,
    gasket_width: float,
    section: str = "rectangle",
    offset: float = 0.0,
    check_cancelled: Callable[[], None] | None = None,
) -> SealGeometry:
    """Nut und unverformte Dichtung aus demselben geschlossenen Mittellinienweg.

    Runde Querschnitte haben den Durchmesser Nuttiefe plus Überstand;
    rechteckige Querschnitte tragen dieselbe Höhe und ihre eigene Breite.
    Kein Materialprofil und keine ungesagte Fertigungszugabe verändern Maße.
    """
    if check_cancelled is not None:
        check_cancelled()
    values = (groove_width, groove_depth, protrusion, gasket_width, offset)
    height = groove_depth + protrusion
    width = height if section == "round" else gasket_width
    if (
        not all(math.isfinite(value) for value in values)
        or min(groove_width, groove_depth, gasket_width) <= EPS_GEOM
        or protrusion < 0
        or width > groove_width + EPS_GEOM
        or section not in ("rectangle", "round")
    ):
        raise ValidationError(
            field="groove_width",
            constraint="seal_dimensions",
            detail=_(
                "Breite und Tiefe müssen positiv sein; die Dichtung muss in die Nut passen. "
                "Prüfen Sie Nutbreite, Nuttiefe und Überstand."
            ),
        )
    path = section_of(profile, max_sag=_SEAL_SAG, check_cancelled=check_cancelled)
    _single(path)
    path = offset_section(path, offset, max_sag=_SEAL_SAG, check_cancelled=check_cancelled)
    _single(path)
    groove_section = _band(path, groove_width, check_cancelled)
    gasket_section = _band(path, width, check_cancelled)
    groove = groove_section.extrude(groove_depth).translate((0, 0, -groove_depth))
    if section == "round":
        gasket = _round_tube(path, height / 2, -groove_depth + height / 2, check_cancelled)
    else:
        gasket = gasket_section.extrude(height).translate((0, 0, -groove_depth))
    if check_cancelled is not None:
        check_cancelled()
    return SealGeometry(_mesh(groove), _mesh(gasket), (groove_width - width) / 2)
