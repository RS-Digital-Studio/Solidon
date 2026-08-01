"""Merkmalserkennung (Bauplan §21.1).

Was ein STL nicht sagt, arbeitet dieses Modul heraus: wo die Bohrungen sind,
welche Flächen eben sind, wo das Netz offen ist. Dieses Vokabular macht den
Rest erst möglich — das Kontextmenü an einer Bohrung, den Agenten, der „das
Loch auf der Oberseite" sagt statt Koordinaten, die Passung zwischen einem
Stift und seinem Loch.

Bohrungen werden gefunden, indem ein Zylinder eingepasst wird, nicht indem
nach runden Kanten gesucht wird: eine Einpassung hat eine Achse, einen Radius
und einen Restfehler — die Antwort lässt sich also beurteilen statt glauben.
Flächen kommen aus koplanaren Flecken, offene Kanten aus dem Netz selbst.

Nichts hier rät im Stillen. Was zu keiner Form passt, ist schlicht kein
Merkmal, und der Steckbrief sagt, wie viele gefunden wurden.
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

#: Wie gut ein Fleck zu einem Zylinder passen muss, um als Bohrung zu zählen:
#: der Radius darf um diesen Anteil streuen, bevor die Einpassung abgelehnt wird.
CYLINDER_TOLERANCE = 0.08

#: Ein Fleck braucht mindestens so viele Dreiecke, um überhaupt beurteilt zu
#: werden.
MIN_PATCH_FACES = 6

#: Flächen unter diesem Anteil der größten werden nicht eigens gemeldet.
MIN_FACE_SHARE = 0.02

#: …und unter dieser absoluten Größe erst recht nicht, egal wie groß der Rest ist.
#:
#: Der relative Anteil allein hilft nur bei einem konstruierten Teil, wo eine
#: Fläche gegen eine viel größere antritt. Auf einem erzeugten Netz sind alle
#: Facetten gleich groß, also ist jede „mindestens zwei Prozent der größten" —
#: eine Kugel aus 3 400 Dreiecken meldete daraufhin 180 Flächen. Danach war
#: jede Zuordnung mehrdeutig, und die Auswertung hielt bei jeder Operation an
#: (§21.3), womit Weg 3 nach der Reparatur nicht weiterkam.
#:
#: Zwei mal zwei Millimeter ist die kleinste Fläche, an der jemand etwas
#: ansetzt: darunter passt weder ein Schraubenkopf noch ein lesbarer Buchstabe.
MIN_FACE_AREA = 4.0

#: Zylinder unter diesem Durchmesser sind keine Bohrungen, sondern Artefakte.
#:
#: Eine Düse legt 0,4 mm breite Bahnen; ein Loch von 0,05 mm hat kein Werkzeug
#: gemacht und keines wird je hineinpassen. Auf einem erzeugten Netz entstehen
#: solche Zylinderfits an jeder Stelle, an der ein paar Dreiecke zufällig um
#: eine Achse herumstehen.
MIN_HOLE_DIAMETER = 0.5

#: … außer sie bestehen aus mindestens so vielen koplanaren Dreiecken. Ein
#: Zylinderdeckel kommt aus dem Kern als ein Dreieck je Segment — sie zu zählen
#: ist also das, was eine kleine ebene Fläche von einer Scheibe einer gekrümmten
#: unterscheidet.
MIN_FLAT_FACES = 8


@dataclass(frozen=True, slots=True)
class CylinderFit:
    """Ein Zylinder, eingepasst durch einen Fleck von Dreiecken."""

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
    """Alles, was dieses Modul erkennen kann, mit stabilen Namen.

    Bohrungen und Stifte teilen ihre Suche (siehe :func:`_cylinders`) — beide
    zu erfragen kostet also, was früher eines kostete.
    """
    found: dict[FeatureId, Feature] = {}
    for feature in [
        *detect_holes(mesh),
        *detect_pins(mesh),
        *detect_faces(mesh),
        *detect_edge_loops(mesh),
    ]:
        found[feature.id] = feature
    _log.info("detected %d features", len(found))
    return found


# --- bores ----------------------------------------------------------------------


def _cylinders(mesh: MeshData) -> list[tuple[CylinderFit, list[int]]]:
    """Jeder zylindrische Fleck des Körpers, einmal eingepasst.

    Bohrungen und Stifte sind dieselbe Suche, zweimal gelesen, und die Suche
    ist die teure Hälfte: an einem Körper mit einer Million Dreiecken kosten
    die Facetten und die zusammenhängenden Flecken Sekunden. Sie zweimal zu
    machen verdoppelte die Erkennungszeit für nichts — also passiert sie hier,
    und beide Aufrufer filtern das Ergebnis.
    """
    body = mesh.raw
    if not len(body.faces):
        return []

    # Eine Bohrungswand besteht aus vielen schmalen ebenen Segmenten — „gehört zu
    # einer Facette" ist also nicht die Trennlinie, „gehört zu einer *großen*
    # Facette" schon.
    planar = _large_facet_faces(body)
    curved = [index for index in range(len(body.faces)) if index not in planar]
    if not curved:
        return []

    found: list[tuple[CylinderFit, list[int]]] = []
    for patch in _connected_patches(body, curved):
        if len(patch) < MIN_PATCH_FACES:
            continue
        fit = fit_cylinder(body, patch)
        if fit is not None and fit.good:
            found.append((fit, patch))

    # Nach Position sortiert, damit die Nummerierung für denselben Körper
    # reproduzierbar ist.
    found.sort(key=lambda entry: (round(entry[0].centre[0], 3), round(entry[0].centre[1], 3)))
    return found


def detect_holes(mesh: MeshData) -> list[Feature]:
    """Cylindrical patches whose normals point inwards (§21.1)."""
    body = mesh.raw
    found = [
        entry
        for entry in _cylinders(mesh)
        if entry[0].inward and entry[0].radius * 2.0 >= MIN_HOLE_DIAMETER
    ]
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


def detect_pins(mesh: MeshData) -> list[Feature]:
    """Zylindrische Flecken, deren Normalen nach außen zeigen (§21.1).

    Dieselbe Einpassung wie bei einer Bohrung, andersherum gelesen. Sie lohnt
    aus einem Grund: ein Stift ist das, womit eine Bohrung gepaart wird (§14),
    und eine Passung braucht beide Enden. Auto Split benennt die Stifte, die es
    selbst macht — dieser hier ist für das Teil, das von woanders kam.
    """
    body = mesh.raw
    found = [entry for entry in _cylinders(mesh) if not entry[0].inward]
    return [
        Feature(
            id=f"pin_{number}",
            kind="pin",
            provenance="detected",
            params={
                "diameter": round(fit.radius * 2.0, 4),
                "axis": fit.axis,
                "centre": fit.centre,
                "depth": round(_patch_extent(body, patch, fit.axis), 4),
                "residual": round(fit.residual, 4),
            },
            face_indices=tuple(patch),
        )
        for number, (fit, patch) in enumerate(found, start=1)
    ]


def _large_facet_faces(body: trimesh.Trimesh) -> set[int]:
    """Dreiecke, die zu einem ebenen Fleck gehören, der groß genug für eine
    eigene Fläche ist.

    Zwei Wege sich zu qualifizieren, und der zweite ist keine Zierde. Die
    Fläche allein wird gegen die größte Fläche des Körpers gemessen, und auf
    einer Platte mit einem Stift darauf ist die Stiftoberseite unter zwei
    Prozent der Platte — sie zählte also als gekrümmt, schloss sich der
    Stiftwand an, und die Zylinder-Einpassung über Wand-plus-Deckel kam als gar
    nichts heraus. Ein Fleck aus vielen koplanaren Dreiecken ist eine Fläche,
    egal welche Größe er neben dem Rest des Teils hat.
    """
    facets = list(body.facets)
    if not facets:
        return set()
    areas = [float(body.area_faces[facet].sum()) for facet in facets]
    limit = max(areas) * MIN_FACE_SHARE
    return {
        int(index)
        for facet, area in zip(facets, areas, strict=True)
        if area >= limit or len(facet) >= MIN_FLAT_FACES
        for index in facet
    }


def fit_cylinder(body: trimesh.Trimesh, patch: list[int]) -> CylinderFit | None:
    """Kleinste-Quadrate-Zylinder durch einen Fleck von Dreiecken.

    Die Achse ist die Richtung, auf der jede Normale senkrecht steht — der
    Eigenvektor der Normalen-Kovarianz mit dem kleinsten Eigenwert.
    """
    normals = np.asarray(body.face_normals[patch], dtype=float)
    centres = np.asarray(body.triangles_center[patch], dtype=float)

    _values, vectors = np.linalg.eigh(normals.T @ normals)
    axis = vectors[:, 0]
    axis = axis / float(np.linalg.norm(axis))

    # In die Ebene senkrecht zur Achse projizieren und dort einen Kreis einpassen.
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
    """Algebraische Kreiseinpassung (Kåsa): linear, stabil genug für ein
    gebohrtes Loch.
    """
    matrix = np.column_stack([points[:, 0], points[:, 1], np.ones(len(points))])
    target = points[:, 0] ** 2 + points[:, 1] ** 2
    solution, *_ = np.linalg.lstsq(matrix, target, rcond=None)
    centre = np.array([solution[0] / 2.0, solution[1] / 2.0])
    radius = math.sqrt(max(solution[2] + centre @ centre, 0.0))
    return centre, radius


def _patch_extent(body: trimesh.Trimesh, patch: list[int], axis: Vec3) -> float:
    """Wie weit der Fleck entlang seiner eigenen Achse reicht — die Tiefe der
    Bohrung.
    """
    points = np.asarray(body.vertices[np.unique(body.faces[patch])], dtype=float)
    along = points @ np.asarray(axis, dtype=float)
    return float(along.max() - along.min())


def _is_through(mesh: MeshData, fit: CylinderFit) -> bool:
    """Eine Bohrung ist durchgehend, wenn sie so tief ist, wie der Körper
    entlang ihrer Achse dick ist.
    """
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
    """Gruppiert die gegebenen Dreiecke in zusammenhängende Flecken."""
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
    # Dieselbe Schwelle, die die Bohrungserkennung benutzt — ein Fleck ist also
    # entweder eine Fläche oder Teil einer gekrümmten Oberfläche, nie beides,
    # nie keines.
    entries = [
        (facet, area)
        for facet, area in zip(facets, areas, strict=True)
        if area >= largest * MIN_FACE_SHARE and area >= MIN_FACE_AREA
    ]
    entries.sort(key=lambda entry: -entry[1])

    features: list[Feature] = []
    for number, (facet, area) in enumerate(entries, start=1):
        normal = np.asarray(body.face_normals[facet[0]], dtype=float)
        # Flächengewichtet, nicht als Mittel über die Dreiecke: sonst hängt der
        # Mittelpunkt an der Vernetzung statt an der Form. Eine Bohrung in eine
        # Platte lässt rund um sich viele kleine Dreiecke entstehen, und der
        # ungewichtete Mittelwert wandert daraufhin zum Loch — bei einem
        # 60-auf-40-Deckel um 16,8 mm. Die Zuordnung (§21.2) hielt die Fläche
        # danach für eine andere und meldete die alte als verwaist.
        weights = np.asarray(body.area_faces[facet], dtype=float)
        points = np.asarray(body.triangles_center[facet], dtype=float)
        total = float(weights.sum())
        centre = (
            (points * weights[:, None]).sum(axis=0) / total
            if total > EPS_GEOM
            else points.mean(axis=0)
        )
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
    """Offene Kanten sind Defekte, und zu wissen wo sie sind, ist die halbe
    Reparatur.
    """
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
