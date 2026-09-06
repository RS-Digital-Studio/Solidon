"""Messen (Bauplan §18.3).

Der Viewport ist kein Anzeigefenster, sondern das Prüfwerkzeug, und Messen ist
der Teil davon, der exakt sein muss. Also lebt die Rechnung hier, wo sie gegen
bekannte Körper geprüft werden kann, und die Oberfläche sammelt nur Klicks.

Einrasten ist, was eine Messung reproduzierbar macht: ein Klick landet nie
genau auf einer Ecke, also wird er auf den nächsten Eckpunkt oder die nächste
Kante gezogen, bevor irgendetwas gerechnet wird. Gerundet wird nur in der
Anzeige (§11.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.core.deferred import trimesh
from app.core.geom.mesh import RAY_PARALLEL_EPS, MeshData, on_surface
from app.core.types import BoundingBox, Vec3
from app.core.units import EPS_GEOM, round_display

#: Wie weit ein Klick von einem Eckpunkt oder einer Kante entfernt sein darf,
#: um darauf gezogen zu werden — relativ zur Modelldiagonale. Auf dem
#: Bildschirm etwa eine Fingerbreite.
#:
#: **Das ist die Rückfallweite.** Wer die Ansicht hat, rechnet sie in
#: Bildpunkten (``Viewport._snap_radius_at``): Gezielt wird mit der Maus, und
#: vier Millimeter sind je nach Zoom zweihundert Bildpunkte oder zwei.
SNAP_RADIUS_RELATIVE = 0.02

#: Ab welchem Knick zwischen zwei Dreiecken eine Kante **sichtbar** ist.
#:
#: Ohne diese Grenze fängt ein Messklick auf jede Dreieckskante, und die
#: meisten davon gibt es im Bild nicht: Die Deckfläche eines Quaders besteht
#: aus zwei Dreiecken, und ihre Diagonale läuft mitten über die Fläche. Ein
#: Klick zwei Millimeter neben der Ecke landete deshalb mit Abstand **null**
#: auf dieser Diagonalen — der Punkt sprang auf eine Linie, die niemand sieht,
#: und die Messung stimmte nur zufällig (Robert, 03.09.2026: „bei messen ist
#: das zielen relativ schwer").
#:
#: Zwanzig Grad trennen die Triangulierung (null Grad) von dem, was eine Kante
#: ist: Eine Fase mit 45 Grad bleibt eine, ein Zylindermantel mit 64 Segmenten
#: (5,6 Grad je Schritt) wird keine. Ein grob geteilter Zylinder mit weniger
#: als achtzehn Segmenten fängt auf seinen Mantellinien — dort sieht man sie
#: aber auch.
SHARP_EDGE_ANGLE = math.radians(20.0)


def surface_gap(first: MeshData, second: MeshData, search_length: float) -> float | None:
    """Kleinster Flächenabstand bis zur Suchweite, einschließlich Kante gegen Kante.

    Der vorhandene Geometriekern prüft sämtliche Dreiecke über seinen Raumindex.
    Eine fehlgeschlagene Körperübernahme ist keine Abstandsaussage.
    """
    import manifold3d

    solids = [
        manifold3d.Manifold(
            manifold3d.Mesh64(
                np.asarray(mesh.raw.vertices, dtype=np.float64),
                np.asarray(mesh.raw.faces, dtype=np.uint64),
            )
        )
        for mesh in (first, second)
    ]
    if any(solid.status() != manifold3d.Error.NoError or solid.is_empty() for solid in solids):
        return None
    return float(solids[0].min_gap(solids[1], search_length))


#: Wie viele sichtbare Kanten an einem Punkt zusammenlaufen müssen, damit er
#: eine **Ecke** ist.
#:
#: Zwei genügen nicht: Jeder Knoten entlang einer Kante hat zwei, und der
#: Fang zöge dann auf jeden Zwischenpunkt einer Kreiskante. Drei ist die Ecke
#: eines Körpers. Eine offene Fläche ohne Volumen hat damit keine Ecken —
#: ihre Ränder fängt der Kantenfang, und drucken lässt sie sich ohnehin nicht.
CORNER_EDGES = 3


@dataclass(frozen=True, slots=True)
class SnapResult:
    """Wo ein Klick gelandet ist, und worauf er gezogen wurde."""

    point: Vec3
    kind: str
    """``vertex``, ``edge`` or ``free``."""
    distance: float = 0.0
    """Wie weit der Klick gewandert ist."""


@dataclass(frozen=True, slots=True)
class Measurement:
    """Ein Maß, das bleibt, bis es gelöscht wird (§18.3)."""

    kind: str
    """``distance``, ``diameter``, ``thickness`` or ``angle``."""
    value: float
    points: tuple[Vec3, ...] = ()
    object_id: str | None = None
    object_ids: tuple[str, ...] = ()
    """Zu welchem Körper jeder Punkt gehört — **je Punkt einer**.

    Ein Maß spannt sich über zwei Flächen, und die dürfen zu verschiedenen
    Körpern gehören; ``object_id`` daneben benennt das Maß als Ganzes und
    reicht dafür nicht. Gebraucht wird das nicht zum Rechnen — die Zahl steht
    in den Punkten —, sondern zum **Zeigen**: Zwei Druckplatten stehen im Bild
    nebeneinander und in der Szene übereinander (§25), und ohne diese Zuordnung
    lässt sich ein Punkt der einen nicht von einem der anderen unterscheiden.

    Leer heißt „nicht zugeordnet"; dann bleibt der Punkt, wo er ist.
    """
    label: str = ""

    @property
    def shown(self) -> float:
        """Der Wert, wie er erscheint — auf Anzeigegenauigkeit gerundet."""
        return round_display(self.value)


@dataclass(slots=True)
class MeasurementList:
    """Die Maße einer Sitzung. Sie bleiben bis zum Löschen und verfallen
    nie von selbst.
    """

    entries: list[Measurement] = field(default_factory=list)

    def add(self, measurement: Measurement) -> Measurement:
        self.entries.append(measurement)
        return measurement

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            del self.entries[index]

    def clear(self) -> None:
        self.entries.clear()

    def __len__(self) -> int:
        return len(self.entries)


# --- Grundgrößen -----------------------------------------------------------------


def distance(a: Vec3, b: Vec3) -> float:
    """Von Punkt zu Punkt, in Millimetern."""
    return float(np.linalg.norm(np.asarray(b, dtype=float) - np.asarray(a, dtype=float)))


def angle_between(first: Vec3, second: Vec3) -> float:
    """Winkel zwischen zwei Richtungen in Grad, immer der kleinere."""
    one = np.asarray(first, dtype=float)
    two = np.asarray(second, dtype=float)
    lengths = float(np.linalg.norm(one)) * float(np.linalg.norm(two))
    if lengths <= EPS_GEOM:
        return 0.0
    # ``abs`` ist der „immer der kleinere" aus der Zusage: Eine Richtung und
    # ihre Gegenrichtung spannen denselben Winkel auf. Hier standen zwei
    # Zweige, und der für ``cosine >= 0`` rechnete dasselbe — ``abs`` einer
    # nichtnegativen Zahl ist sie selbst.
    cosine = float(np.clip(float(np.dot(one, two)) / lengths, -1.0, 1.0))
    return math.degrees(math.acos(abs(cosine)))


def bounding_box_of(meshes: list[MeshData]) -> BoundingBox:
    """Grenzen einer Auswahl — eine leere Auswahl gibt einen leeren Quader."""
    if not meshes:
        return BoundingBox((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    lows = np.array([mesh.bounds.minimum for mesh in meshes], dtype=float)
    highs = np.array([mesh.bounds.maximum for mesh in meshes], dtype=float)
    low = lows.min(axis=0)
    high = highs.max(axis=0)
    return BoundingBox(
        (float(low[0]), float(low[1]), float(low[2])),
        (float(high[0]), float(high[1]), float(high[2])),
    )


def volume_of(meshes: list[MeshData]) -> float:
    """Volumen einer Auswahl in mm³. Nur bei geschlossenen Körpern sinnvoll."""
    return float(sum(mesh.volume for mesh in meshes))


# --- Einrasten ------------------------------------------------------------------


def snap(mesh: MeshData, point: Vec3, radius: float | None = None) -> SnapResult:
    """Zieht einen Klick auf die nächste Ecke, sonst auf die nächste Kante,
    sonst lässt ihn stehen.

    **Gefangen wird nur, was man sieht** (:data:`SHARP_EDGE_ANGLE`,
    :data:`CORNER_EDGES`). Über alle Netzknoten und alle Dreieckskanten
    gerechnet, fängt jeder Klick auf irgendetwas — auf einen Knoten mitten in
    einer Fläche, auf eine Triangulierungsdiagonale, auf eine Kante, die nur
    die Vernetzung kennt. Ein Punkt, der auf eine unsichtbare Linie springt,
    ist schlimmer als einer, der stehen bleibt: Die Zahl daneben stimmt, und
    niemand weiß, wovon sie gilt.
    """
    limit = radius if radius is not None else mesh.bounds.diagonal * SNAP_RADIUS_RELATIVE
    target = np.asarray(point, dtype=float)

    edges = visible_edges(mesh)
    vertices = np.asarray(mesh.raw.vertices, dtype=float)

    corners = corner_points(mesh, edges)
    if len(corners):
        offsets = np.linalg.norm(corners - target, axis=1)
        closest = int(np.argmin(offsets))
        if float(offsets[closest]) <= limit:
            found = corners[closest]
            return SnapResult(
                point=(float(found[0]), float(found[1]), float(found[2])),
                kind="vertex",
                distance=float(offsets[closest]),
            )

    edge_point, edge_offset = _closest_point_on_edges(vertices, edges, target)
    if edge_point is not None and edge_offset <= limit:
        return SnapResult(point=edge_point, kind="edge", distance=edge_offset)

    return SnapResult(point=(float(target[0]), float(target[1]), float(target[2])), kind="free")


def visible_edges(mesh: MeshData) -> np.ndarray:
    """Die Kanten, die im Bild eine sind — als Paare von Knotennummern.

    Zwei Sorten zählen: die **scharfen**, an denen zwei Dreiecke einen Knick
    machen (:data:`SHARP_EDGE_ANGLE`), und die **offenen**, an denen überhaupt
    nur eines hängt — ein Loch im Netz hat einen sichtbaren Rand.

    Beide Auskünfte hält ``trimesh`` selbst vor und rechnet sie einmal je
    Netz; gemessen kostet der erste Zugriff bei zwanzigtausend Dreiecken
    7,6 ms und jeder weitere elf Mikrosekunden. Das ist der Grund, warum die
    Frage bei jeder Ruhepause des Zeigers gestellt werden darf.
    """
    raw = mesh.raw
    pieces: list[np.ndarray] = []

    angles = np.asarray(raw.face_adjacency_angles, dtype=float)
    if len(angles):
        adjacent = np.asarray(raw.face_adjacency_edges, dtype=np.int64)
        pieces.append(adjacent[angles > SHARP_EDGE_ANGLE])

    # **Offene Kanten nur, wo es welche geben kann.** Die Zählung läuft über
    # jede Dreieckskante — bei einem Netz aus dreihunderttausend Dreiecken ist
    # sie der ganze Aufwand dieser Funktion (gemessen 3,9 ms von 3,9 ms). Ein
    # wasserdichtes Netz hat keine offene Kante, und ob es das ist, weiß
    # ``trimesh`` bereits.
    if not raw.is_watertight:
        unique = np.asarray(raw.edges_unique, dtype=np.int64)
        if len(unique):
            counts = np.bincount(
                np.asarray(raw.edges_unique_inverse, dtype=np.int64), minlength=len(unique)
            )
            pieces.append(unique[counts == 1])

    found = [piece for piece in pieces if len(piece)]
    if not found:
        return np.empty((0, 2), dtype=np.int64)
    return np.vstack(found)


def corner_points(mesh: MeshData, edges: np.ndarray | None = None) -> np.ndarray:
    """Die Punkte, an denen mindestens drei sichtbare Kanten zusammenlaufen.

    Das ist die Ecke eines Körpers. Jeder andere Netzknoten ist einer, den die
    Vernetzung gesetzt hat, und ihn zu fangen hieße, eine Messung an eine
    Entscheidung des Vernetzers zu hängen: Eine Kugel aus zwanzigtausend
    Dreiecken hat keine einzige Ecke und lieferte trotzdem für jeden Klick
    einen „Eckpunkt".
    """
    if edges is None:
        edges = visible_edges(mesh)
    if not len(edges):
        return np.empty((0, 3), dtype=float)
    nodes, counts = np.unique(edges.ravel(), return_counts=True)
    chosen = nodes[counts >= CORNER_EDGES]
    if not len(chosen):
        return np.empty((0, 3), dtype=float)
    vertices: np.ndarray = np.asarray(mesh.raw.vertices, dtype=float)[chosen]
    return vertices


def _closest_point_on_edges(
    vertices: np.ndarray, edges: np.ndarray, target: np.ndarray
) -> tuple[Vec3 | None, float]:
    if not len(edges):
        return None, math.inf
    starts = vertices[edges[:, 0]]
    ends = vertices[edges[:, 1]]

    directions = ends - starts
    lengths = np.einsum("ij,ij->i", directions, directions)
    lengths[lengths < EPS_GEOM] = EPS_GEOM
    travel = np.clip(np.einsum("ij,ij->i", target - starts, directions) / lengths, 0.0, 1.0)
    projected = starts + directions * travel[:, None]
    offsets = np.linalg.norm(projected - target, axis=1)

    closest = int(np.argmin(offsets))
    found = projected[closest]
    return (float(found[0]), float(found[1]), float(found[2])), float(offsets[closest])


# --- Wandstärke ------------------------------------------------------------------


def wall_thickness(mesh: MeshData, point: Vec3, direction: Vec3 | None = None) -> float | None:
    """Dicke an einem Punkt: nach innen schießen und bis zum ersten Treffer
    messen (§18.3).

    Gibt None zurück, wo der Strahl den Körper verlässt, ohne etwas zu treffen —
    ein ehrliches „kann ich nicht sagen" schlägt eine erfundene Zahl.
    """
    origin = np.asarray(point, dtype=float)
    ray = _inward_direction(mesh, origin, direction)
    if ray is None:
        return None

    hits = ray_distances(mesh, origin, ray)
    return float(hits.min()) if len(hits) else None


def ray_distances(mesh: MeshData, origin: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Abstände von ``origin`` zu jedem Dreieck, das der Strahl trifft,
    nächstes zuerst.

    Möller-Trumbore über alle Dreiecke auf einmal. Vektorisiert ist das schnell
    genug für einzelne Strahlen und braucht keinen Raumindex — eine
    Abhängigkeit weniger für eine Handvoll Zeilen (AGENTS.md Regel 22).
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    if not len(faces):
        return np.array([])

    first = vertices[faces[:, 0]]
    edge_one = vertices[faces[:, 1]] - first
    edge_two = vertices[faces[:, 2]] - first

    side = np.cross(direction, edge_two)
    determinant = np.einsum("ij,ij->i", edge_one, side)
    # ``EPS_GEOM`` sind Millimeter, die Determinante ist ein Spatprodukt aus
    # drei Vektoren — mit einem Längenmaß verglichen fällt sie bei kleinen
    # Dreiecken durch, ohne dass der Strahl parallel läge. Dieselbe Rechnung
    # steht in :func:`app.core.geom.mesh.ray_hit_distances` und hat dort die
    # dimensionsrichtige Schranke; jetzt beide dieselbe.
    hits = np.abs(determinant) > RAY_PARALLEL_EPS
    if not hits.any():
        return np.array([])

    inverse = np.zeros_like(determinant)
    inverse[hits] = 1.0 / determinant[hits]

    offset = origin - first
    along = inverse * np.einsum("ij,ij->i", offset, side)
    across = np.cross(offset, edge_one)
    sideways = inverse * (across @ direction)
    travel = inverse * np.einsum("ij,ij->i", edge_two, across)

    inside = (
        hits
        & (along >= -EPS_GEOM)
        & (sideways >= -EPS_GEOM)
        & (along + sideways <= 1.0 + EPS_GEOM)
        & (travel > EPS_GEOM * 100.0)
    )
    return np.sort(travel[inside])


def _inward_direction(
    mesh: MeshData, origin: np.ndarray, direction: Vec3 | None
) -> np.ndarray | None:
    """Die Richtung zum Schießen: die gegebene, oder die invertierte
    Flächennormale.
    """
    if direction is not None:
        ray = np.asarray(direction, dtype=float)
        length = float(np.linalg.norm(ray))
        return ray / length if length > EPS_GEOM else None

    if not mesh.triangle_count:
        return None
    normals = np.asarray(mesh.raw.face_normals, dtype=float)
    lengths = np.linalg.norm(normals, axis=1)
    usable = np.isfinite(normals).all(axis=1) & (lengths > EPS_GEOM)
    if not usable.any():
        return None

    indices = np.flatnonzero(usable)
    surface = mesh.raw
    if len(indices) != mesh.triangle_count:
        # Nullflächen sind im Viewport unsichtbar und besitzen keine Richtung.
        # Sie dürfen deshalb auch dann nicht gewinnen, wenn ihre Restkante
        # genau unter dem Klick liegt. Das nächste tragende Dreieck entscheidet.
        surface = trimesh.Trimesh(
            vertices=np.asarray(mesh.raw.vertices, dtype=float),
            faces=np.asarray(mesh.raw.faces, dtype=np.int64)[indices],
            process=False,
        )
    _closest, _distance, faces = on_surface(surface, origin.reshape(1, 3))
    nearest = int(indices[int(faces[0])])
    normal = normals[nearest]
    length = float(np.linalg.norm(normal))
    return -normal / length if length > EPS_GEOM else None
