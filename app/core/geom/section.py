"""Einen Körper mit einer Ebene schneiden (Bauplan §18.2).

**Die Schnittfläche ist geschlossen.** Ohne Deckel sieht jeder Vollkörper hohl
aus, und die Wandstärke lässt sich nicht beurteilen — genau daran scheitern
naive Umsetzungen, und darum lebt das hier im Kern statt im Viewport: ein
gedeckelter Schnitt ist Geometrie, lässt sich also am Ergebnis nachmessen
statt an Pixeln vergleichen.

Eine zweite Ebene macht aus dem Schnitt eine Scheibe.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import ValidationError
from app.core.geom import enclosure, transform
from app.core.geom.mesh import MeshData, edge_table
from app.core.geom.transform import moved, rotation_between
from app.core.types import Vec3
from app.core.units import EPS_GEOM, is_zero
from app.i18n import _

Axis = Literal["x", "y", "z"]

AXIS_NORMALS: dict[Axis, Vec3] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


@dataclass(frozen=True, slots=True)
class SectionPlane:
    """Eine Schnittebene. Alles auf der positiven Seite der Normalen fällt weg."""

    normal: Vec3 = (0.0, 0.0, 1.0)
    position: float = 0.0
    """Abstand der Ebene vom Ursprung entlang ihrer Normalen, in Millimetern."""

    @classmethod
    def along(cls, axis: Axis, position: float = 0.0) -> SectionPlane:
        return cls(normal=AXIS_NORMALS[axis], position=position)

    @property
    def origin(self) -> Vec3:
        # ``math.hypot`` statt ``np.linalg.norm`` (BLAS, RM-187).
        length = math.hypot(*self.normal) or 1.0
        return (
            self.normal[0] / length * self.position,
            self.normal[1] / length * self.position,
            self.normal[2] / length * self.position,
        )

    def flipped(self) -> SectionPlane:
        return SectionPlane(
            normal=(-self.normal[0], -self.normal[1], -self.normal[2]),
            position=-self.position,
        )


def plane_through(first: Vec3, second: Vec3, view: Vec3) -> SectionPlane | None:
    """Die Ebene, die eine im Bild gezeichnete Linie meint.

    Zwei angeklickte Punkte auf dem Körper geben eine Linie — und eine Linie
    allein legt keine Ebene fest, sie lässt sich um sich selbst drehen. Was
    die Drehung festhält, ist die Richtung, in die geschaut wurde: Gemeint ist
    immer der Schnitt *in den Bildschirm hinein*, denn das ist die Ebene, die
    der Nutzer als Strich sieht. Beides zusammen ist eindeutig, und deshalb
    steht die Blickrichtung hier im Argument statt in der Operation — die Op
    bekommt die fertige Ebene und hängt damit an keiner Kamerastellung (§11.2).

    ``None``, wenn die Linie zu kurz ist oder genau in die Blickrichtung
    zeigt: dann spannt sich keine Ebene auf, und eine geratene wäre schlimmer
    als keine (Regel 21).
    """
    along = np.asarray(second, dtype=float) - np.asarray(first, dtype=float)
    normal = np.cross(along, np.asarray(view, dtype=float))
    length = float(np.linalg.norm(normal))
    if length <= EPS_GEOM:
        return None
    normal = normal / length
    return SectionPlane(
        normal=(float(normal[0]), float(normal[1]), float(normal[2])),
        position=float(np.dot(normal, np.asarray(first, dtype=float))),
    )


def plane_patch(minimum: Vec3, maximum: Vec3, plane: SectionPlane) -> tuple[Vec3, ...]:
    """Der Teil einer Ebene, der im Hüllquader eines Körpers liegt.

    Das Polygon ist für die Vorschau des Trennwerkzeugs: Eine gezeichnete
    Linie zeigt nur die Kante der Ebene. Erst die Fläche bis an den Körperrand
    beantwortet sichtbar, was beim Anwenden wirklich getrennt wird. Sie ist
    reine Anzeigegeometrie und ändert weder Netz noch Dokument.

    Die Ecken kommen umlaufend sortiert zurück, damit der Viewport daraus eine
    Fläche zeichnen kann. Verfehlt die Ebene den Quader, ist das Ergebnis leer.
    """
    normal = np.asarray(plane.normal, dtype=float)
    length = float(np.linalg.norm(normal))
    if length <= EPS_GEOM:
        return ()
    normal /= length
    origin = np.asarray(plane.origin, dtype=float)
    low, high = np.asarray(minimum, dtype=float), np.asarray(maximum, dtype=float)
    corners = np.array(
        [
            (x, y, z)
            for x in (low[0], high[0])
            for y in (low[1], high[1])
            for z in (low[2], high[2])
        ],
        dtype=float,
    )
    bits = tuple((x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1))
    points: list[np.ndarray] = []

    def remember(point: np.ndarray) -> None:
        if not any(float(np.linalg.norm(point - known)) <= EPS_GEOM for known in points):
            points.append(point)

    for first in range(len(corners)):
        for second in range(first + 1, len(corners)):
            if sum(a != b for a, b in zip(bits[first], bits[second], strict=True)) != 1:
                continue
            start, end = corners[first], corners[second]
            start_distance = float(np.dot(start - origin, normal))
            end_distance = float(np.dot(end - origin, normal))
            if is_zero(start_distance):
                remember(start)
            if is_zero(end_distance):
                remember(end)
            crosses = (start_distance < -EPS_GEOM and end_distance > EPS_GEOM) or (
                end_distance < -EPS_GEOM and start_distance > EPS_GEOM
            )
            if crosses:
                share = start_distance / (start_distance - end_distance)
                remember(start + share * (end - start))

    if len(points) < 3:
        return ()

    centre = np.mean(points, axis=0)
    # Die am wenigsten parallele Weltachse gibt eine stabile erste Achse in
    # der Ebene — auch dann, wenn die Ebene fast genau waagerecht steht.
    seed = np.eye(3)[int(np.argmin(np.abs(normal)))]
    across = np.cross(normal, seed)
    across /= float(np.linalg.norm(across))
    upward = np.cross(normal, across)
    points.sort(
        key=lambda point: float(
            np.arctan2(np.dot(point - centre, upward), np.dot(point - centre, across))
        )
    )
    return tuple((float(point[0]), float(point[1]), float(point[2])) for point in points)


@dataclass(frozen=True, slots=True)
class SectionResult:
    """Was vom Körper bleibt, und ob die Schnittfläche geschlossen werden
    konnte.
    """

    mesh: MeshData
    capped: bool
    """Falsch, wenn der Körper von vornherein offen war — dann gibt es keinen Deckel."""


class CutContactError(ValidationError):
    """Eine Schnittlage erzeugt eine Berührlinie statt eines Volumenkörpers."""

    def __init__(self, position: float | None = None) -> None:
        super().__init__(
            field="position",
            title=_("Diese Schnittebene berührt eine Modellwand."),
            detail=_(
                "Die Schnittfläche und die Modellwand treffen hier nur entlang einer Linie "
                "aufeinander. Verschieben Sie die Ebene etwas, sodass sie die Wand schneidet "
                "oder Abstand zu ihr hat."
            ),
            value=position,
            constraint="cut_surface_contact",
        )


def check_cut_contact(result: SectionResult, position: float) -> None:
    """Eine neu entstandene Berührlinie vor Folgerechnungen absagen.

    ``capped`` beschreibt den Eingang, nicht die Dichtheit des Ergebnisses.
    War der Eingang geschlossen und trägt die Hälfte jetzt eine Kante mit
    mehr als zwei Dreiecken, treffen Schnittdeckel und Modellwand dort nur
    längs einer Linie aufeinander. Die Stifte könnten daraus nur über das
    maßändernde Raster wieder einen Körper machen. Ein von vornherein
    offenes Netz behält dagegen seine eigene Diagnose; seine alten Kanten
    belegen keine tangierende Schnittlage.

    Die Operationswege fragen hier, die reine Schnittansicht zeigt weiter
    die unveränderte Lage. ``position`` ist der eingetragene Wert, auch wenn
    die behaltene Seite mit umgedrehter Ebenennormaler geschnitten wurde.
    """
    if result.capped and bool((edge_table(result.mesh.raw).counts > 2).any()):
        raise CutContactError(position)


def cut(mesh: MeshData, plane: SectionPlane, second: SectionPlane | None = None) -> SectionResult:
    """Schneidet einen Körper und schließt die Schnittfläche. Eine zweite
    Ebene lässt eine Scheibe übrig.

    Ein offenes Modell lässt sich nicht ehrlich deckeln — der Schnitt wird
    trotzdem gezeigt, aber als ungedeckelt gemeldet statt vorgetäuscht.
    """
    body: trimesh.Trimesh = mesh.raw
    capped = True
    if not len(body.faces):
        # **Ein leerer Körper hat nichts zu schneiden.** Sein Hüllquader ist
        # ``None``, und die Vorschau einer Aufweitung trägt einen solchen
        # Körper als Zugabe mit: Ein Ansichtsschnitt riss dort die ganze
        # Vorschau ab (Durchsicht 0.5.1).
        return SectionResult(mesh=mesh, capped=capped)

    for entry in (plane, second) if second is not None else (plane,):
        body, closed = _apply(body, entry)
        capped = capped and closed
        if not len(body.faces):
            return SectionResult(mesh=mesh.replacing(trimesh.Trimesh()), capped=capped)

    return SectionResult(mesh=_keeping_slots(mesh, body), capped=capped)


def clip_triangles(
    corners: np.ndarray, plane: SectionPlane, second: SectionPlane | None = None
) -> np.ndarray:
    """Lose Dreiecke an der Schnittebene kappen — für die Anzeige, ohne Deckel.

    ``corners`` sind ``3·n`` Eckpunkte, je drei ein Dreieck: die Form, in der
    die Ansicht Merkmalsflecken und Kandidaten hinlegt. Zurück kommt dieselbe
    Form mit dem, was auf der behaltenen Seite liegt, an der Ebene sauber
    geschnitten. Ein loses Dreiecksfeld ist keine geschlossene Fläche;
    :func:`cut` setzt darauf keine Kappe und fasst den Körper, zu dem die
    Dreiecke gehören, nicht an.
    """
    points = np.asarray(corners, dtype=float).reshape(-1, 3)
    if len(points) == 0:
        return np.empty((0, 3), dtype=float)
    faces = np.arange(len(points), dtype=np.int64).reshape(-1, 3)
    patch = MeshData(trimesh.Trimesh(points, faces, process=False))
    clipped = cut(patch, plane, second).mesh.raw
    return np.asarray(clipped.vertices[clipped.faces], dtype=float).reshape(-1, 3)


def _keeping_slots(mesh: MeshData, body: trimesh.Trimesh) -> MeshData:
    """§20: ein Schnitt ist eine Boolesche Op gegen einen Halbraum, und er
    behält die Slots.

    Die Schnittfläche selbst gehört zu keiner alten Oberfläche und bekommt den
    Vorgabe-Slot — dieselbe Regel wie eine Bohrungswand, aus demselben Grund:
    sie ist neues, sichtbares Material, kein Stück von etwas, das vorher da
    war.
    """
    from app.core.geom.attributes import transfer

    result = mesh.replacing(body)
    if not mesh.slots or result.slots:
        return result
    return transfer(result, [mesh])


def _apply(body: trimesh.Trimesh, plane: SectionPlane) -> tuple[trimesh.Trimesh, bool]:
    """Eine Ebene — geschnitten und gedeckelt in einem Rahmen, in dem sie
    waagerecht liegt.

    **Warum ein eigener Rahmen** (RM-187, 22.09.2026): ``slice_plane`` von
    ``trimesh`` rechnet Seite und Schnittpunkt jeder Kante über ``np.dot``
    — also durch BLAS, dessen letzte Stelle an der CPU hängt —, und für den
    Deckel legt es die Ebene über ``align_vectors`` in die XY-Ebene, das über
    ``np.linalg.svd`` geht: Die Drehung *in* der Ebene war damit Sache der
    Plattform, und die Dreiecke des Deckels auch. Hier wird der Körper erst so
    gedreht, dass die Ebene waagerecht liegt (:func:`transform.rotation_between`,
    elementweise bewegt). Dort ist jedes Skalarprodukt mit der Normalen
    ``(0, 0, 1)`` exakt, jeder Schnittpunkt elementweise gerechnet, und die
    Deckelkontur liest ihre ebenen Koordinaten direkt aus X und Y. Eine
    achsparallele Ebene — der Regelfall — dreht dabei nur Vorzeichen und
    Achsen und ist Bit für Bit umkehrbar; eine schräge kostet zwei Bewegungen
    und bekommt dafür auf jeder Maschine dieselben Dreiecke.

    Das Deckeln braucht die Konturverschachtelung, und die kommt seit dem
    24.08.2026 aus :mod:`app.core.geom.enclosure` statt aus ``rtree`` — der
    Aufruf unten installiert sie, bevor hier geschnitten wird.
    """
    x, y, z = (float(value) for value in plane.normal)
    length = math.hypot(x, y, z)
    if length <= EPS_GEOM:
        return body, True
    normal = np.array([x / length, y / length, z / length])
    watertight = bool(body.is_watertight)

    # Eine Ebene, die den Körper verfehlt, braucht keinen Schnitt — und ein
    # Schnitt ohne etwas zu deckeln ist der eine Fall, aus dem der
    # Polygon-Code nicht schlau wird.
    distances = _corner_distances(body, normal, np.asarray(plane.origin, dtype=float))
    if distances.max() <= EPS_GEOM:
        return body, watertight
    if distances.min() >= -EPS_GEOM:
        return trimesh.Trimesh(), watertight
    enclosure.install()
    turn = rotation_between(normal, (0.0, 0.0, 1.0))
    local = body.copy()
    moved(local, turn)
    vertices = np.asarray(local.vertices, dtype=np.float64)
    settled = settled_on_plane(vertices, (0.0, 0.0, 1.0), plane.position)
    if settled is not vertices:
        local.vertices = settled
    # Im gedrehten Rahmen liegt die Ebene bei z = position, und was darüber
    # liegt, fällt weg: trimesh behält die positive Seite der Normalen, die
    # hier also nach unten zeigt.
    sliced = trimesh.intersections.slice_mesh_plane(  # type: ignore[no-untyped-call]
        local, plane_normal=(0.0, 0.0, -1.0), plane_origin=(0.0, 0.0, plane.position), cap=False
    )
    if watertight and len(sliced.faces):
        sliced = _capped(sliced, plane.position)
    back = np.eye(4)
    back[:3, :3] = turn[:3, :3].T
    moved(sliced, back)
    return sliced, watertight


#: Wie nah eine Ecke an der Schnittebene liegen muss, um zum Deckelrand zu
#: gehören — derselbe Wert wie in ``trimesh.intersections.slice_mesh_plane``.
_ON_PLANE: Final = 1e-8


def settled_on_plane(
    points: np.ndarray, normal: Sequence[float] | np.ndarray, offset: float
) -> np.ndarray:
    """Die Punkte, die ``trimesh`` beim Schneiden an dieser Ebene zu ihr zählt, genau auf ihr.

    ``normal`` hat die Länge eins, ``offset`` ist die Lage der Ebene entlang von
    ihr. ``trimesh`` gibt einem Punkt bis ``_ON_PLANE`` neben der Ebene das
    Vorzeichen null und lässt ihn stehen, wo er ist. Ein Dreieck, das mit ihm
    von einer Seite zur anderen reicht, wird trotzdem geschnitten, und seine
    Kopie dieser Ecke liegt genau auf der Ebene — dieselbe Ecke steht danach
    zweimal da, bis zu ``_ON_PLANE`` auseinander. Wer die Schnittkante danach
    über gerundete Koordinaten zusammenlegt (:func:`_capped`, das Verschweißen
    der Formschräge in ``faces._draft_tools``), verfehlt das Paar, sobald eine
    Rundungsgrenze dazwischenliegt: Der Rand zerfällt in offene Ketten, und
    der Körper bleibt offen. So an einer gespiegelt modellierten Figur, deren
    Mittelnaht aus einer float32-STL Milliardstel Millimeter neben der Mitte
    des Hüllquaders steht — dort, wo *Teilen* seine Ebene vorschlägt (Bob, CC0:
    26 solche Ecken, 21 und 18 offene Ketten an den zwei Hälften, danach
    scheiterten die Stifte an einem offenen Körper).

    Auf der Ebene liegt der Punkt dort, wo ``trimesh`` ihn ohnehin einordnet,
    und seine Kopien fallen mit ihm zusammen. Bewegt wird entlang der Normalen,
    um höchstens ``_ON_PLANE``, ein Hundertstel von ``EPS_GEOM``; verglichen
    wie in ``trimesh`` (``|Abstand| <= _ON_PLANE``), gerechnet in
    Grundrechenarten (:func:`transform.along`). Bei einer Achsennormalen
    bleiben die zwei anderen Koordinaten Bit für Bit, und die dritte ist danach
    die Lage der Ebene — bis auf Reste unter 1e-24 an einer Ebene, die näher
    als ``_ON_PLANE`` am Nullpunkt liegt. Liegt kein Punkt in der Spanne, kommt
    ``points`` selbst zurück, sonst eine Kopie.
    """
    raw = np.asarray(points, dtype=np.float64)
    distances = transform.along(raw, normal) - offset
    beside = np.abs(distances) <= _ON_PLANE
    if not beside.any():
        return raw
    settled = raw.copy()
    settled[beside] -= distances[beside, None] * np.asarray(normal, dtype=np.float64)
    return settled


def _capped(sliced: trimesh.Trimesh, position: float) -> trimesh.Trimesh:
    """Den Schnitt bei ``z = position`` mit einem ebenen Deckel schließen.

    Dieselbe Bauart wie ``slice_mesh_plane(cap=True)``: Ecken zusammenlegen,
    Randkanten in der Ebene zu Umrissen, Umrisse triangulieren, die
    Dreiecksecken auf die vorhandenen Ecken zurückführen. Nur liegen die
    ebenen Koordinaten hier exakt in X und Y, statt über eine SVD dorthin
    gedreht zu werden. Der Deckel zeigt nach oben, aus dem Körper hinaus, wie
    der, den ``trimesh`` setzt.

    **Zusammengelegt wird nur die Schnittkante, und nur innerhalb einer
    Schale** (KUNDE-10). ``slice_mesh_plane`` legt jeden Schnittpunkt je
    Dreieck neu an; diese Ecken in der Ebene müssen zu einem Rand werden.
    ``trimesh`` legte dafür *alle* gleichen Ecken des Körpers zusammen — auch
    die zweier Teile, die sich nur berühren, und die einer Engstelle, die das
    Einlesen eigens getrennt hat (``repair.weld``). Die Berührflächen teilten
    danach ihre Kanten: Am Laptopständer (21 Teile) trug jede Hälfte 89 bis
    500 verzweigte Kanten, war kein Körper mehr, und die Stifte von *Modell
    teilen* scheiterten daran. Welche Ecken zu einer Schale gehören, sagt die
    Nachbarschaft der Dreiecke über ihre Eckennummern, wie sie aus dem Schnitt
    kommen; jede Schale deckelt ihre eigenen Umrisse (:func:`_cap_batches`).
    """
    from scipy.spatial import cKDTree
    from trimesh import geometry, grouping
    from trimesh.creation import triangulate_polygon
    from trimesh.path import polygons

    vertices = np.asarray(sliced.vertices, dtype=np.float64)
    faces = np.asarray(sliced.faces, dtype=np.int64)
    shells = _vertex_shells(faces, len(vertices))
    on_plane = np.abs(vertices[:, 2] - position) < _ON_PLANE
    inverse = np.arange(len(vertices), dtype=np.int64)
    rim = np.flatnonzero(on_plane)
    if len(rim):
        keys = np.column_stack((shells[rim].astype(np.float64), vertices[rim]))
        first, groups = grouping.unique_rows(keys)  # type: ignore[no-untyped-call]
        inverse[rim] = rim[np.asarray(first, dtype=np.int64)[np.asarray(groups, dtype=np.int64)]]
    faces = inverse[faces]
    faces = faces[(faces[:, :1] != faces[:, 1:]).all(axis=1) & (faces[:, 1] != faces[:, 2])]
    used = np.zeros(len(vertices), dtype=bool)
    used[faces.ravel()] = True
    renumbered = np.cumsum(used, dtype=np.int64) - 1
    vertices = vertices[used]
    shells = shells[used]
    faces = renumbered[faces]
    edges = geometry.faces_to_edges(faces)  # type: ignore[no-untyped-call]
    edges.sort(axis=1)
    on_plane = np.abs(vertices[:, 2] - position) < _ON_PLANE
    edges = edges[on_plane[edges].all(axis=1)]
    edges = edges[edges[:, 0] != edges[:, 1]]
    single = grouping.group_rows(edges, require_count=1)  # type: ignore[no-untyped-call]
    collected = [faces]
    if len(vertices) >= 3 and len(single):
        for batch in _cap_batches(edges[single], vertices, shells):
            corners = np.unique(batch)
            tree = cKDTree(vertices[corners])
            for outline in polygons.edges_to_polygons(batch, vertices[:, :2]):
                points, triangles = triangulate_polygon(outline, force_vertices=True)
                if not len(triangles):
                    continue
                spatial = np.column_stack(
                    (np.asarray(points, dtype=np.float64), np.full(len(points), position))
                )
                _distance, nearest = tree.query(spatial)
                mapped = corners[np.asarray(nearest, dtype=np.int64)][
                    np.asarray(triangles, dtype=np.int64)
                ]
                usable = (mapped[:, 1:] != mapped[:, :1]).all(axis=1) & (
                    mapped[:, 1] != mapped[:, 2]
                )
                collected.append(mapped[usable])
    return trimesh.Trimesh(vertices=vertices, faces=np.vstack(collected), process=False)


def _vertex_shells(faces: np.ndarray, count: int) -> np.ndarray:
    """Zu welcher Schale jede Ecke gehört — über die Eckennummern der Dreiecke.

    Eine Ecke, die kein Dreieck benutzt, bildet ihre eigene Schale. Die
    Antwort von ``connected_components`` kommt in ``int32`` und geht sofort
    nach ``int64`` (siehe ``csgraph antwortet in int32``).
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    if not len(faces):
        return np.arange(count, dtype=np.int64)
    rows = np.concatenate((faces[:, 0], faces[:, 1]))
    cols = np.concatenate((faces[:, 1], faces[:, 2]))
    graph = coo_matrix((np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(count, count))
    _found, labels = connected_components(graph, directed=False)
    return np.asarray(labels, dtype=np.int64)


def _cap_batches(edges: np.ndarray, vertices: np.ndarray, shells: np.ndarray) -> list[np.ndarray]:
    """Die Randkanten in Gruppen, deren Umrisse sich keine Stelle teilen.

    Umrisse zweier Schalen, die sich an einer Stelle berühren, dürfen weder
    zu einem Umriss verschmelzen noch ihre Deckelecken bei der anderen Schale
    holen. Solche Schalen deckeln einzeln; alle übrigen zusammen, wie bisher —
    ein Schnitt durch ein Teil mit vielen losen Stücken wird damit nicht zu
    einer Schleife über jedes einzelne.
    """
    from trimesh import grouping

    corners = np.unique(edges)
    owner = shells[corners]
    _first, groups = grouping.unique_rows(vertices[corners])  # type: ignore[no-untyped-call]
    groups = np.asarray(groups, dtype=np.int64)
    order = np.lexsort((owner, groups))
    same_place = groups[order][1:] == groups[order][:-1]
    other_shell = owner[order][1:] != owner[order][:-1]
    shared = same_place & other_shell
    touching = np.unique(np.concatenate((owner[order][1:][shared], owner[order][:-1][shared])))
    edge_shells = shells[edges[:, 0]]
    alone = np.isin(edge_shells, touching)
    batches = [edges[~alone]] if bool((~alone).any()) else []
    batches.extend(edges[edge_shells == shell] for shell in touching)
    return batches


def _corner_distances(body: trimesh.Trimesh, normal: np.ndarray, origin: np.ndarray) -> np.ndarray:
    """Vorzeichenbehafteter Abstand der Hüllquader-Ecken; positiv heißt
    „fällt weg".
    """
    low, high = body.bounds
    corners = np.array(
        [(x, y, z) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
    )
    return transform.along(corners - origin, normal)
