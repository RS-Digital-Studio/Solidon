"""Die Kanten eines **Netzes** — als Züge, mit stabilen Schlüsseln.

Der exakte Kern hat sie von der Topologie (`brep.edit.edges_of`): Dort ist
eine Kante ein Ding, und OpenCASCADE nennt sie beim Namen. Ein Netz hat
davon nichts — es hat Dreiecke, und was der Kunde als Kante sieht, ist die
Linie, an der zwei davon einen Knick machen.

**Trotzdem ist sie dieselbe Sache**, und deshalb sieht sie hier genauso aus:
:class:`MeshEdge` trägt Mitte, Richtung und Länge wie ``EdgeInfo``, und
:func:`edge_key` gibt beiden denselben Schlüssel. Was darauf aufbaut — das
Anklicken in der Ansicht, die Beschriftung, die Auswahl in der Operation —
muss die zwei Kerne damit nicht auseinanderhalten (Entscheidung Robert,
10.09.2026: „alles soll immer bearbeitbar sein, egal ob importiert Format
egal und beim selbst zeichnen").

Zwei Dinge kann ein Netz dabei, die der exakte Kern nicht braucht:

* **Ein Zug statt eines Segments.** Eine Bauteilkante von dreißig Millimetern
  besteht in einem feinen Netz aus vierzig Dreieckskanten. Wer sie einzeln
  ausgibt, gibt dem Kunden vierzig Kanten, wo er eine sieht.
* **Konvex oder konkav.** Am exakten Körper sagt das die Topologie beim
  Verrunden selbst; hier muss es dabeistehen, denn eine Außenkante wird
  gerundet, indem Material weggeht, eine Innenkante, indem welches dazukommt.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import numpy as np

from app.core.errors import CANCEL, CHANGE_SELECTION, CORRECT_INPUT, GeometryError, ValidationError
from app.core.geom.boolean import BooleanKind, BooleanOutcome, boolean, deepest
from app.core.geom.measure import SHARP_EDGE_ANGLE
from app.core.geom.mesh import MeshData
from app.core.geom.repair import remove_hollow_shells
from app.core.log import get_logger
from app.core.types import Feature, Vec3, is_a_cavity
from app.core.units import EPS_GEOM, MAX_FACET_ANGLE, MAX_FACET_SAG
from app.i18n import _

_log = get_logger(__name__)

#: Wie viele Kanten an einem Knoten zusammenlaufen dürfen, damit ein Zug
#: durchläuft. An einer Ecke sind es drei, und dort endet er — sonst liefe er
#: um den ganzen Körper und wäre keine Kante mehr, sondern ein Rundgang.
THROUGH = 2


@dataclass(frozen=True, slots=True)
class MeshEdge:
    """Eine Kante des Netzes — beschrieben wie eine des exakten Kerns.

    ``points`` ist der Zug selbst, von einem Ende zum anderen. ``middle``,
    ``direction`` und ``length`` bedeuten dasselbe wie bei ``brep.edit.EdgeInfo``:
    die Mitte des Zugs, seine Richtung von Anfang zu Ende und seine Länge.
    :func:`edge_key` liest Mitte und Richtung, bei geschlossenen Zügen auch
    ``extent``, ihren größten Abstand von der Mitte.

    ``normals`` trägt je **Stück** des Zugs die zwei Flächennormalen, zwischen
    denen es liegt — so viele Paare, wie es Stücke gibt. Ein Werkzeug zum
    Verrunden entsteht daraus: Wo die beiden Flächen zusammenstoßen, sagt
    ihre Winkelhalbierende, wohin die Rundung geht, und der Winkel zwischen
    ihnen, wie weit. Am Zug variieren sie, deshalb je Stück und nicht je
    Kante — bei einem Bogen dreht sich die Halbierende mit.

    ``node_indices`` hält die ursprünglichen Netzknoten für den Eckanschluss
    fest. Nur innerhalb dieser einen Topologie gilt die Nummer; sie wird
    weder im Kantenschlüssel noch in einer Projektdatei gespeichert.
    """

    points: tuple[Vec3, ...]
    length: float
    direction: Vec3
    middle: Vec3
    convex: bool
    normals: tuple[tuple[Vec3, Vec3], ...] = ()
    node_indices: tuple[int, ...] = ()

    @property
    def upright(self) -> bool:
        return abs(self.direction[2]) > 0.9

    @property
    def flat(self) -> bool:
        return abs(self.direction[2]) < 0.1

    @property
    def extent(self) -> float:
        """Der größte Abstand vom Linienschwerpunkt, am Kreis sein Radius."""
        return max(math.dist(self.middle, point) for point in self.points)


class HasPlacement(Protocol):
    """Was :func:`edge_key` von einer Kante braucht — und mehr nicht.

    ``MeshEdge`` und ``brep.edit.EdgeInfo`` haben nichts gemeinsam als diese
    geometrischen Auskünfte. Dieselbe Bauart wie ``boolean.HasVolume``,
    und aus demselben Grund: Die Funktion soll für
    beide Kerne gelten, ohne einen von ihnen zu kennen.
    """

    @property
    def middle(self) -> Vec3: ...

    @property
    def direction(self) -> Vec3: ...

    @property
    def extent(self) -> float: ...


def edge_key(entry: HasPlacement) -> str:
    """Der stabile Verweis auf **eine** Kante — Lage und bei Ringen ihre Größe.

    Wörtlich dasselbe Format wie ``brep.edit.edge_key``, und das ist der
    Punkt: Eine Kante trägt denselben Schlüssel, gleich aus welchem Kern sie
    kommt. Was darauf aufbaut — die Auswahl im Bild, die Beschriftung, der
    Parameter ``edge_keys`` der Operation — kennt den Unterschied nicht.

    Der Grund für das Format steht dort ausführlich und gilt hier genauso:
    Ein Index in eine Dreiecksliste verschiebt sich, sobald davor etwas
    anderes passiert, und in einer Projektdatei hieße das, beim nächsten
    Öffnen eine andere Kante zu verrunden — still.

    **Die Richtung ohne Vorzeichen**, denn ein Zug läuft je nach Startpunkt
    in beide Richtungen: Die erste Komponente ungleich null wird positiv
    gemacht.

    **Und die Null hat auch keines.** ``-0.0`` schreibt sich als ``-0.000``
    und ist damit ein anderer Schlüssel als ``0.000`` — dieselbe Kante, zwei
    Zeichenketten. Gemessen an einem Zylinder: Der exakte Kern gab
    ``0.000,-0.000,0.000``, das Netz ``0.000,0.000,0.000``, und beide meinten
    die entartete Richtung eines geschlossenen Kreises.

    Geschlossene Kanten tragen zusätzlich ihren größten Abstand von der
    Mitte. Sonst heißen die beiden Ränder eines Rohrs gleich: Ihre Mitten
    fallen zusammen, und ihre Richtungen sind beide null. Der Abstand bleibt
    bei einer Unterteilung derselben Segmente erhalten; die Polygonlänge
    dagegen weicht von der exakten Kreislänge ab.
    """
    placement = _placement_key(entry)
    if math.dist(entry.direction, (0.0, 0.0, 0.0)) <= EPS_GEOM:
        return f"{placement}:r:{_unsigned_zero(entry.extent, 2):.2f}"
    return placement


def _placement_key(entry: HasPlacement) -> str:
    """Der bisherige Schlüssel bleibt für eindeutige gespeicherte Auswahlen lesbar."""
    direction = entry.direction
    lead = next((value for value in direction if abs(value) > 1e-6), 1.0)
    sign = -1.0 if lead < 0.0 else 1.0
    return "e:{:.2f},{:.2f},{:.2f}:{:.3f},{:.3f},{:.3f}".format(
        *(_unsigned_zero(value, 2) for value in entry.middle),
        *(_unsigned_zero(value * sign, 3) for value in direction),
    )


def _unsigned_zero(value: float, digits: int) -> float:
    """Auf ``digits`` Stellen gerundet, und eine Null ohne Vorzeichen.

    **Gerundet wird hier und nicht erst beim Formatieren**, denn genau
    dazwischen entsteht der Fall: ``-1e-16`` ist keine negative Null und
    schreibt sich trotzdem als ``-0.000``. Wer nur ``-0.0`` abfängt, fängt
    ihn nicht — gemessen an der entarteten Richtung eines Kreises, wo der
    exakte Kern genau solche Werte liefert.
    """
    rounded = round(float(value), digits)
    return rounded or 0.0


def edges_of(mesh: MeshData, angle: float = SHARP_EDGE_ANGLE) -> list[MeshEdge]:
    """Die sichtbaren Kanten eines Netzes, zu Zügen verkettet.

    ``angle`` ist der Knick im Bogenmaß, ab dem zwei Dreiecke eine Kante
    bilden — dieselbe Schwelle, die das Messen benutzt
    (:data:`~app.core.geom.measure.SHARP_EDGE_ANGLE`), damit ein Klick nicht
    etwas anderes trifft, als der Fang zeigt.

    **Gelesen wird ``face_adjacency`` und nicht ``visible_edges``**, obwohl
    die Frage dieselbe beginnt: Dort fällt die Zuordnung zur **Konvexität**
    weg, und die entscheidet beim Verrunden, ob Material geht oder kommt.
    Offene Ränder bleiben deshalb hier außen vor — an einem Loch im Netz gibt
    es keine zwei Flächen, zwischen denen eine Rundung säße; was dort hilft,
    ist die Reparatur.
    """
    raw = mesh.raw
    angles = np.asarray(raw.face_adjacency_angles, dtype=float)
    if not len(angles):
        return []
    sharp = angles > float(angle)
    if not sharp.any():
        return []
    segments = np.asarray(raw.face_adjacency_edges, dtype=np.int64)[sharp]
    convex = np.asarray(raw.face_adjacency_convex, dtype=bool)[sharp]
    pairs = np.asarray(raw.face_adjacency, dtype=np.int64)[sharp]
    face_normals = np.asarray(raw.face_normals, dtype=float)
    vertices = np.asarray(raw.vertices, dtype=float)
    # Je Segment die zwei Flächennormalen, unter dem Schlüssel des
    # Knotenpaars — beim Verketten steht die Reihenfolge der Knoten noch
    # nicht fest, und danach ist die Zuordnung zu den Flächen fort.
    sides = {
        (min(a, b), max(a, b)): (face_normals[first], face_normals[second])
        for (a, b), (first, second) in zip(segments.tolist(), pairs.tolist(), strict=True)
    }

    found: list[MeshEdge] = []
    for nodes, is_convex in _chains(segments, convex):
        points = vertices[nodes]
        normals = tuple(sides[(min(a, b), max(a, b))] for a, b in itertools.pairwise(nodes))
        described = _describe(points, is_convex, normals, tuple(nodes))
        if described is not None:
            found.append(described)
    return found


def _describe(
    points: np.ndarray,
    convex: bool,
    normals: tuple[tuple[np.ndarray, np.ndarray], ...] = (),
    node_indices: tuple[int, ...] = (),
) -> MeshEdge | None:
    """Aus einem Punktzug die Zahlen, an denen eine Auswahl hängt."""
    steps = np.linalg.norm(np.diff(points, axis=0), axis=1)
    length = float(steps.sum())
    if length <= EPS_GEOM:
        return None
    # **Beide Zahlen genau wie im exakten Kern**, und das ist keine
    # Geschmacksfrage, sondern die Zusage: Dieselbe Kante muss aus beiden
    # Kernen denselben Schlüssel bekommen. Gemessen am Zylinder liefen sie
    # auseinander, solange hier etwas anderes stand — dort ist die Kante ein
    # geschlossener Kreis, ihr Schwerpunkt liegt auf der Achse, und die
    # Richtung von Anfang zu Ende ist entartet.
    span = points[-1] - points[0]
    reach = max(float(np.linalg.norm(span)), EPS_GEOM)
    direction = tuple(float(value) for value in span / reach)
    # **Längengewichtet und nicht als Mittel der Punkte.** Das ist die
    # diskrete Fassung von OpenCASCADEs ``CentreOfMass``: Ein fein
    # unterteilter Abschnitt zöge den Punktmittelwert zu sich, und derselbe
    # Zug bekäme nach einer Neuvernetzung einen anderen Schlüssel.
    middle = tuple(float(value) for value in _centre_of_mass(points, steps, length))
    return MeshEdge(
        points=tuple(tuple(float(v) for v in point) for point in points),  # type: ignore[misc]
        length=length,
        direction=direction,  # type: ignore[arg-type]
        middle=middle,  # type: ignore[arg-type]
        convex=convex,
        normals=tuple(
            (tuple(float(v) for v in first), tuple(float(v) for v in second))  # type: ignore[misc]
            for first, second in normals
        ),
        node_indices=node_indices,
    )


def _centre_of_mass(points: np.ndarray, steps: np.ndarray, length: float) -> np.ndarray:
    """Der Schwerpunkt des Linienzugs — jedes Stück mit seiner Länge gewichtet.

    Die diskrete Fassung dessen, was OpenCASCADE über
    ``BRepGProp.LinearProperties`` für eine Kurve rechnet. Der Unterschied zum
    Mittel der Punkte ist die Gewichtung, und sie ist der Grund: Ein Zug, den
    jemand an einer Stelle feiner unterteilt, hat dort mehr Punkte und
    denselben Schwerpunkt.
    """
    middles = (points[:-1] + points[1:]) / 2.0
    return np.asarray((middles * steps[:, None]).sum(axis=0) / max(length, EPS_GEOM))


def _chains(segments: np.ndarray, convex: np.ndarray) -> list[tuple[list[int], bool]]:
    """Die Segmente zu Zügen verketten — Knotennummern und Konvexität.

    Ein Zug läuft, solange an einem Knoten genau zwei Kanten hängen. Wo drei
    zusammenkommen, ist eine **Ecke** des Körpers, und dort endet er: Der
    Kunde sieht dort drei Kanten und nicht einen Rundgang.

    Ein Zug gilt als konvex, wenn seine Segmente es sind. Gemischte gibt es
    — eine Kante kann über ihre Länge umschlagen —, und dort entscheidet die
    Mehrheit: Was überwiegt, bestimmt, in welche Richtung eine Verrundung
    Material bewegt.
    """
    neighbours: dict[int, list[int]] = {}
    kinds: dict[tuple[int, int], bool] = {}
    for (first, second), is_convex in zip(segments.tolist(), convex.tolist(), strict=True):
        if first == second:
            continue
        neighbours.setdefault(first, []).append(second)
        neighbours.setdefault(second, []).append(first)
        kinds[(min(first, second), max(first, second))] = bool(is_convex)

    walked: set[tuple[int, int]] = set()
    chains: list[tuple[list[int], bool]] = []

    def walk(start: int, first: int) -> None:
        nodes = [start, first]
        votes = [kinds[(min(start, first), max(start, first))]]
        walked.add((min(start, first), max(start, first)))
        while len(neighbours.get(nodes[-1], ())) == THROUGH:
            here, came_from = nodes[-1], nodes[-2]
            onward = next((n for n in neighbours[here] if n != came_from), None)
            if onward is None:
                break
            step = (min(here, onward), max(here, onward))
            if step in walked:
                break
            walked.add(step)
            votes.append(kinds[step])
            nodes.append(onward)
        chains.append((nodes, sum(votes) * 2 >= len(votes)))

    # Erst von den Ecken aus — dort beginnt und endet, was der Kunde als
    # Kante sieht.
    for node, around in neighbours.items():
        if len(around) == THROUGH:
            continue
        for other in around:
            if (min(node, other), max(node, other)) not in walked:
                walk(node, other)
    # Was danach übrig ist, ist ein geschlossener Ring ohne Ecke — der Rand
    # einer Bohrung, die Naht eines Zylinders.
    for first, second in list(kinds):
        if (first, second) not in walked:
            walk(first, second)
    return chains


def sharp_angle_degrees() -> float:
    """Die Knickschwelle in Grad — für Texte und Parameterschemata."""
    return math.degrees(SHARP_EDGE_ANGLE)


EdgeChoice = Literal["all", "vertical", "horizontal", "top", "bottom", "named"]

#: Welche Kanten eine Auswahl meint. „Senkrecht" ist, was jemand mit „runde
#: die Ecken dieser Box" meint: die vier Stehenden, nicht die Plattenkanten.
#: ``named`` ist die sechste und die einzige, die nicht nach der Lage geht:
#: einzelne Kanten, jede über ihren eigenen Schlüssel (:func:`edge_key`, E4).
EDGE_CHOICES: tuple[EdgeChoice, ...] = (
    "all",
    "vertical",
    "horizontal",
    "top",
    "bottom",
    "named",
)

#: Wie weit zwei Kanten in der Höhe auseinanderliegen dürfen und trotzdem
#: beide „oben" sind. Ein Tausendstel Millimeter — enger als jede Fertigung
#: und weiter als jede Rundung im Fließkomma.
SAME_HEIGHT = EPS_GEOM * 1000


class SelectableEdge(HasPlacement, Protocol):
    """Was eine Auswahl **nach der Lage** von einer Kante braucht.

    Wieder für beide Kerne: ``upright`` und ``flat`` beantworten
    ``MeshEdge`` und ``brep.edit.EdgeInfo`` gleich, und deshalb gibt es die
    Auswahl nur einmal. Eine zweite Fassung im exakten Kern hieße, dass „alle
    senkrechten Kanten" dort bald etwas anderes bedeutet als hier.
    """

    @property
    def upright(self) -> bool: ...

    @property
    def flat(self) -> bool: ...


def choose[AnyEdge: SelectableEdge](edges: Sequence[AnyEdge], choice: EdgeChoice) -> list[AnyEdge]:
    """Die Kanten, die eine benannte Auswahl meint."""
    # ``named`` geht nicht nach der Lage, sondern nach Schlüsseln — die kennt
    # nur :func:`wanted`. Hier wäre jede Antwort eine falsche.
    if choice == "named":
        return []
    if choice == "all":
        return list(edges)
    if choice == "vertical":
        return [entry for entry in edges if entry.upright]
    if choice == "horizontal":
        return [entry for entry in edges if entry.flat]

    heights = [entry.middle[2] for entry in edges]
    if not heights:
        return []
    wanted_height = max(heights) if choice == "top" else min(heights)
    return [
        entry
        for entry in edges
        if entry.flat and abs(entry.middle[2] - wanted_height) <= SAME_HEIGHT
    ]


def named_edges[AnyEdge: SelectableEdge](
    edges: Sequence[AnyEdge], keys: Sequence[str]
) -> list[AnyEdge]:
    """Die Kanten zu diesen Schlüsseln — in der Reihenfolge der Schlüssel.

    Was nicht mehr da ist, fehlt in der Antwort; **wer daraus einen Fehler
    macht, entscheidet der Aufrufer.** Eine Kante kann verschwunden sein, weil
    ein Schritt davor sie weggenommen hat, und dann ist das eine Auskunft an
    den Kunden und kein Programmfehler (Regel 17).

    Mehrdeutige Schlüssel halten dagegen hier an: Ein alter Rohrschlüssel
    oder eine Quantisierungskollision darf keine Kante zufällig auswählen.
    """
    described: dict[str, list[AnyEdge]] = {}
    for entry in edges:
        key = edge_key(entry)
        described.setdefault(key, []).append(entry)
        legacy = _placement_key(entry)
        if legacy != key:
            described.setdefault(legacy, []).append(entry)
    selected: list[AnyEdge] = []
    for key in keys:
        matches = described.get(key, [])
        if len(matches) > 1:
            raise GeometryError(
                detail=_("Die gewählte Kante ist nicht eindeutig — wählen Sie sie am Körper neu."),
                values={"key": key, "matches": len(matches)},
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        if matches:
            selected.append(matches[0])
    return selected


def wanted[AnyEdge: SelectableEdge](
    edges: Sequence[AnyEdge], choice: EdgeChoice, keys: Sequence[str]
) -> list[AnyEdge]:
    """Die Kanten, die dieser Aufruf behandelt — genannte vor Gruppe (E4).

    Eine leere Auswahl ist an beiden Wegen ein Satz und kein leerer Körper,
    aber sie hat **verschiedene Gründe**: Bei einer Gruppe gibt es die Sorte
    Kante nicht, bei genannten sind sie verschwunden — ein Schritt davor hat
    sie weggenommen. Wer denselben Satz für beides schriebe, schickte den
    Kunden in die falsche Richtung (Regel 17).

    Eine ausdrücklich benannte Auswahl gilt nur vollständig: Fehlt auch nur
    ein Schlüssel, wird keine der übrigen Kanten bearbeitet (§21.3).
    """
    if choice == "named" and not keys:
        raise GeometryError(
            detail=_("Für diese Auswahl ist noch keine Kante benannt — wählen Sie eine aus."),
            values={"choice": choice},
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    if keys:
        chosen = named_edges(edges, keys)
        if len(chosen) != len(keys):
            raise GeometryError(
                detail=_(
                    "Mindestens eine gewählte Kante gibt es an diesem Körper nicht mehr — "
                    "ein Schritt davor hat sie verändert. Wählen Sie die Kanten neu."
                ),
                values={"edges": len(keys), "missing": len(keys) - len(chosen)},
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        return chosen
    chosen = choose(edges, choice)
    if not chosen:
        raise GeometryError(
            detail=_("Zu dieser Auswahl gehört keine Kante."),
            values={"choice": choice},
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    return chosen


#: Wie wenige Sehnen einen Bogen mindestens ausmachen.
#:
#: Zwei wären eine Ecke statt einer Rundung. Die Zahl greift nur bei sehr
#: kleinen Radien, wo beide Grenzen darunter schon mit einem Stück erfüllt
#: wären.
MIN_ARC_STEPS = 4

#: Wie weit der Werkzeugkörper an den Enden über die Kante hinausragt.
#:
#: Ein Boolescher Schnitt, dessen Flächen genau aufeinanderliegen, ist der
#: Fall, den die Rückfallkette teuer auflösen muss (§17.2). Dieselbe
#: Begründung wie bei ``prepare.FEATURE_OVERLAP`` — hier eine eigene Zahl,
#: weil es um die Längsrichtung eines Zugs geht und nicht um ein Maß, das
#: der Kunde wiederfinden soll.
EDGE_OVERSHOOT = 0.01

#: Wie weit die Normale einer Nachbarfläche aus der Senkrechten zur
#: Rundungsachse kippen darf und noch als deren Nachbar gilt.
UPRIGHT_TO_AXIS = 0.1


def rounding_tool(
    entry: MeshEdge,
    radius: float,
    rounded: bool = True,
    *,
    min_steps: int = 0,
    extend_ends: bool = True,
) -> MeshData:
    """Der Körper, der aus einer Kante eine Rundung oder eine Fase macht.

    Im Querschnitt ist es der Zwickel zwischen den beiden Flächen und dem
    Kreis, der beide berührt: Bei einer **Außenkante** wird er abgezogen und
    lässt die Rundung stehen, bei einer **Innenkante** dazugelegt und füllt
    sie aus. Beide Male ist es derselbe Körper — was ihn unterscheidet, ist
    die Richtung, in die er von der Kante wegzeigt, und die sagen die
    Flächennormalen.

    Die drei Zahlen dahinter stehen in jedem Tabellenwerk und sind hier
    nachgerechnet: Der Mittelpunkt liegt auf der Winkelhalbierenden im
    Abstand ``R / sin(θ/2)``, die Berührpunkte ``R / tan(θ/2)`` von der
    Kante entfernt, und der weggenommene Querschnitt misst
    ``t·R minus ½R²(π minus θ)``. Für rechte Winkel ergibt das ``R² minus ¼πR²``.

    **Die Fase ist derselbe Zwickel ohne den Bogen** (``rounded=False``), und
    ``radius`` heißt dann Rücknahme: Die Berührpunkte liegen so weit von der
    Kante entfernt, wie die Fase auf jeder Fläche wegnimmt, und zwischen
    ihnen läuft eine Gerade. Nur diese zwei Zeilen unterscheiden die beiden
    Handlungen — zwei Funktionen dafür hießen, dass eine von ihnen den
    nächsten Fehler allein bekommt.

    **Gebaut wird stückweise.** Jedes Stück des Zugs bekommt sein eigenes
    Prisma mit seinem eigenen Querschnitt; vereinigt ergeben sie den ganzen
    Körper. An einem Bogen dreht sich die Winkelhalbierende dabei mit.

    Ein gemischter Eckanschluss setzt ``min_steps`` gemeinsam für Torus und
    Zylinder. Dort verhindert ``extend_ends=False`` einen Schnitt auf der
    anderen Seite des Knotens, wo wieder Material stehen kann.
    """
    if radius <= EPS_GEOM:
        raise ValidationError(
            "radius" if rounded else "distance",
            _("Ohne Maß entsteht keine Kantenbearbeitung. Dieser Wert muss größer als null sein."),
            value=radius,
        )
    if not entry.normals:
        raise GeometryError(
            detail=_(
                "Zu dieser Kante sind die angrenzenden Flächen nicht bekannt. "
                "Lesen Sie das Modell neu ein und wählen Sie die Kante erneut."
            ),
        )

    points = np.asarray(entry.points, dtype=float)
    pieces: list[MeshData] = []
    for index, (first, second) in enumerate(entry.normals):
        wedge = _wedge(
            points[index],
            points[index + 1],
            first,
            second,
            radius,
            entry.convex,
            rounded,
            subtracted=entry.convex and extend_ends,
            min_steps=min_steps,
            flank_overlap=0.0 if extend_ends else EPS_GEOM,
        )
        if wedge is not None:
            pieces.append(wedge)
    if not pieces:
        raise GeometryError(
            detail=_(
                "Das Maß ist für diese Kante zu groß — sie hat keine Flächen, auf "
                "denen die Bearbeitung Platz findet. Wählen Sie ein kleineres."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"radius": radius},
        )
    if len(pieces) == 1:
        return pieces[0]
    # **In einem Zug und nicht paarweise.** Der erste Anlauf faltete die Stücke
    # nacheinander zusammen; bei einem geschlossenen Rundgang — der Oberkante
    # einer schon verrundeten Platte, achtundzwanzig Stücke — blieben dabei zwei
    # Häute ohne Dicke stehen. Der Körper war danach wasserdicht und trug sein
    # richtiges Volumen, aber ``body_count`` zählte drei Teile, und der
    # Prüfbericht meldet so etwas dem Kunden als Zerfall.
    return boolean("union", pieces, quality="fine").mesh


def _wedge(
    start: np.ndarray,
    end: np.ndarray,
    first: Vec3,
    second: Vec3,
    radius: float,
    convex: bool,
    rounded: bool,
    subtracted: bool,
    min_steps: int = 0,
    flank_overlap: float = 0.0,
) -> MeshData | None:
    """Ein Stück des Werkzeugs — das Prisma über einem Querschnitt.

    ``convex`` sagt, auf welcher Seite der Kante der Zwickel liegt;
    ``subtracted``, ob er vom Körper abgezogen wird. Beim Verrunden ist das
    dasselbe, beim Wegnehmen einer Rundung nicht.
    """
    along = end - start
    reach = float(np.linalg.norm(along))
    if reach <= EPS_GEOM:
        return None
    along = along / reach

    one = np.asarray(first, dtype=float)
    two = np.asarray(second, dtype=float)
    # **Die Winkelhalbierende zeigt in den Zwickel — und der liegt je nach
    # Kante auf der anderen Seite.** An einer Außenkante ist er das Material,
    # das weggeht, also die Gegenrichtung der Normalensumme; an einer
    # Innenkante ist er der Hohlraum, den die Kehle auffüllt, also die
    # Normalensumme selbst. Gemessen an einer Nut: Ohne die Unterscheidung lag
    # das Werkzeug unter dem Nutboden im vollen Material, und die Vereinigung
    # legte 0,02 mm³ dazu statt 30.
    into = (one + two) if not convex else -(one + two)
    weight = float(np.linalg.norm(into))
    if weight <= EPS_GEOM:
        # Zwei entgegengesetzte Normalen: keine Kante, sondern eine Wand von
        # null Dicke. Dort ist nichts zu runden.
        return None
    into = into / weight
    theta = math.pi - math.acos(float(np.clip(np.dot(one, two), -1.0, 1.0)))
    half = theta / 2.0
    if half <= EPS_GEOM or half >= math.pi / 2.0 - EPS_GEOM:
        return None

    # **Bei der Fase ist das Maß die Rücknahme selbst**, bei der Rundung folgt
    # sie aus dem Radius: Eine Fase von 1 mm nimmt jeder Fläche 1 mm weg,
    # gleich unter welchem Winkel sie stehen — so ist es auch im exakten Kern
    # beschrieben („auf jeder der beiden Flächen").
    tangent = radius / math.tan(half) if rounded else radius
    # Die Richtungen entlang der beiden Flächen, weg von der Kante.
    towards_one = _along_face(one, along, into)
    towards_two = _along_face(two, along, into)
    if towards_one is None or towards_two is None:
        return None

    first_touch = start + tangent * towards_one
    second_touch = start + tangent * towards_two
    bow: list[np.ndarray] = []
    if rounded:
        centre = start + radius / math.sin(half) * into
        bow = _arc(centre, first_touch, second_touch, radius, min_steps=min_steps)
    profile = [start, first_touch, *bow, second_touch]
    if flank_overlap > 0.0:
        # Die Schnittkurve bleibt unverändert. Nur die beiden ursprünglichen
        # Kontaktseiten reichen aus dem Schnittmaterial beziehungsweise in
        # das vorhandene Material hinein; so bleibt keine innere Naht stehen.
        sign = 1.0 if convex else -1.0
        shifted = sign * flank_overlap
        profile = [
            start + shifted * (one + two) / (1.0 + float(np.dot(one, two))),
            first_touch + shifted * one,
            first_touch,
            *bow,
            second_touch,
            second_touch + shifted * two,
        ]

    # **Zwei senkrechte Achsen in der Querschnittsebene.** Die beiden
    # Flächenrichtungen sind es nicht — bei jedem Winkel außer neunzig Grad
    # stünde das Polygon schief, und der erste Anlauf tat genau das.
    across = np.cross(along, towards_one)
    flat = [
        (float(np.dot(point - start, towards_one)), float(np.dot(point - start, across)))
        for point in profile
    ]
    # **Den Überstand bekommt nur, was abgezogen wird.** Bei einer Differenz
    # hält er die Schnittflächen von den Körperflächen fern; bei einer
    # Vereinigung klebt er, was über das Kantenende hinausragt, außen an den
    # Körper. Gemessen an einer durchgehenden Nut: 0,02 mm³ zu viel, als
    # 0,01 mm dünner Grat auf beiden Stirnflächen der Platte.
    #
    # **Und die Frage ist die Boolesche Richtung, nicht die Kante.** Beim
    # Verrunden fällt beides zusammen — außen wird abgezogen, innen vereinigt —,
    # und deshalb stand hier zuerst ``convex``. Beim *Wegnehmen* einer Rundung
    # kehrt sich das um: außen wird vereinigt. Mit der alten Bedingung stand
    # der Quader danach 20,02 mm hoch und trug 24000,36 mm³ statt 24000,0.
    overshoot = EDGE_OVERSHOOT if subtracted else 0.0
    return _prism(flat, start, towards_one, across, along, reach, overshoot)


def _prism(
    flat: list[tuple[float, float]],
    origin: np.ndarray,
    axis_u: np.ndarray,
    axis_v: np.ndarray,
    along: np.ndarray,
    reach: float,
    overshoot: float,
) -> MeshData | None:
    """Aus dem Querschnitt ein Prisma entlang der Kante — im Weltsystem.

    Der Überstand an beiden Enden (:data:`EDGE_OVERSHOOT`) ist kein Maß,
    sondern eine Vorsichtsmaßnahme: Zwei Flächen, die genau aufeinander
    liegen, sind der Fall, den die Boolesche Rückfallkette teuer auflöst.
    Wo er schadet statt zu helfen, entscheidet der Aufrufer.
    """
    import trimesh
    from shapely.geometry import Polygon as ShapelyPolygon

    outline = ShapelyPolygon(flat)
    if not outline.is_valid or outline.area <= EPS_GEOM:
        return None
    body = trimesh.creation.extrude_polygon(outline, height=reach + 2.0 * overshoot)
    frame = np.eye(4)
    frame[:3, 0] = axis_u
    frame[:3, 1] = axis_v
    frame[:3, 2] = along
    frame[:3, 3] = origin - overshoot * along
    body.apply_transform(frame)
    return MeshData(body)


def _along_face(normal: np.ndarray, along: np.ndarray, inward: np.ndarray) -> np.ndarray | None:
    """Die Richtung in dieser Fläche, quer zur Kante und in den Zwickel."""
    direction = np.cross(normal, along)
    reach = float(np.linalg.norm(direction))
    if reach <= EPS_GEOM:
        return None
    direction = direction / reach
    return direction if float(np.dot(direction, inward)) > 0.0 else -direction


def _arc_steps(radius: float, span: float) -> int:
    """Aus wie vielen Sehnen ein Bogen dieses Radius besteht.

    Zwei Grenzen, dieselben, mit denen der exakte Kern tesselliert: Keine
    Sehne weicht weiter von der Rundung ab als :data:`MAX_FACET_SAG`, und
    keine dreht weiter als :data:`MAX_FACET_ANGLE`. Die erste ergibt sich aus
    ``sag = R·(1 - cos(φ/2))``, nach ``φ`` aufgelöst.

    **Eine feste Zahl je Bogen wäre beides zugleich falsch:** Bei R = 30 mm
    ließen sechzehn Stücke 0,036 mm stehen, bei R = 0,5 mm rechnete sie
    sechzehnmal für sechs Tausendstel. Die Feinheit gehört an den Radius, und
    an welche Zahl sie gehört, entscheidet nicht dieses Modul — sonst liefen
    die beiden Kerne bei derselben Rundung auseinander.
    """
    if radius <= MAX_FACET_SAG:
        # Kleiner als die erlaubte Abweichung: Dann sagt sie nichts mehr, und
        # es bleibt bei der Winkelgrenze.
        turn = MAX_FACET_ANGLE
    else:
        turn = min(2.0 * math.acos(1.0 - MAX_FACET_SAG / radius), MAX_FACET_ANGLE)
    return max(MIN_ARC_STEPS, math.ceil(span / turn))


def _arc(
    centre: np.ndarray,
    first: np.ndarray,
    second: np.ndarray,
    radius: float,
    *,
    min_steps: int = 0,
) -> list[np.ndarray]:
    """Die Zwischenpunkte des Rundungsbogens von einem Berührpunkt zum anderen."""
    one = (first - centre) / radius
    two = (second - centre) / radius
    span = math.acos(float(np.clip(np.dot(one, two), -1.0, 1.0)))
    axis = np.cross(one, two)
    length = float(np.linalg.norm(axis))
    if length <= EPS_GEOM:
        return []
    axis = axis / length
    steps = max(_arc_steps(radius, span), min_steps)
    points = []
    for step in range(1, steps):
        angle = span * step / steps
        turned = (
            one * math.cos(angle)
            + np.cross(axis, one) * math.sin(angle)
            + axis * float(np.dot(axis, one)) * (1.0 - math.cos(angle))
        )
        points.append(centre + radius * turned)
    return points


def round_edges(
    mesh: MeshData,
    radius: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
) -> BooleanOutcome:
    """Verrundet die gewählten Kanten eines Netzes — dieselbe Handlung wie
    ``brep.edit.fillet``, an einem Körper, der keine Topologie hat.

    Der Bogen ist ein Sehnenzug und keine Kurve; das ist der Unterschied zum
    exakten Kern und der Grund, aus dem es ihn weiter gibt. Wie fein, sagt
    :func:`_arc_steps` — die Zusage lautet, dass keine Sehne weiter als
    :data:`~app.core.units.MAX_FACET_SAG` von der Rundung abweicht, also
    genauso weit wie die Flächen, die der exakte Kern ausgibt.
    """
    return _worked_edges(mesh, radius, choice, keys, rounded=True)


def bevel_edges(
    mesh: MeshData,
    distance: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
) -> BooleanOutcome:
    """Fast die gewählten Kanten — dieselbe Handlung wie ``brep.edit.chamfer``.

    ``distance`` ist die Rücknahme auf **jeder** der beiden Flächen, wie im
    exakten Kern. Am Netz ist die Fase der genauere der beiden Fälle: Sie ist
    eine Ebene, und eine Ebene hat ein Netz exakt — hier weicht nichts ab.
    """
    return _worked_edges(mesh, distance, choice, keys, rounded=False)


def _mixed_corner_region(size: float, *, rounded: bool) -> tuple[MeshData, MeshData]:
    """Ersatzquader und Zielmaterial für zwei konvexe und eine konkave Kante.

    Kanonischer Knoten ist der Ursprung, die Deckflächennormale zeigt nach
    +Z, die konkave Kante nach -Z und die seitlichen Außennormalen nach +X/+Y.
    Der Quader reicht von ``(-size,-size,-size)`` bis ``(size,size,0)``.
    Die Größe ist bereits positiv validiert. Transformation, lokale Ersetzung und Prüfung auf
    andere betroffene Merkmale gehören zum Aufrufer.

    Für die Rundung liegt die Torusachse bei ``(size,size,-size)``. Beide
    Winkelrichtungen teilen sich ein Raster, das am vierfachen Radius bemessen
    ist. Damit bleiben die Sehnenabweichungen für den Außenring mit ``2*size``
    und das Röhrenprofil mit ``size`` zusammen unter dem gemeinsamen Budget.
    Die angrenzenden Zylinder müssen dieselbe Mindestschrittzahl erhalten.
    """
    import trimesh

    region = trimesh.creation.box((2.0 * size, 2.0 * size, size))
    region.apply_translation((0.0, 0.0, -size / 2.0))
    if not rounded:
        points = np.asarray(
            [
                (-1.0, -1.0, -1.0),
                (1.0, -1.0, -1.0),
                (-1.0, 1.0, -1.0),
                (1.0, 0.0, -1.0),
                (0.0, 1.0, -1.0),
                (-1.0, -1.0, 0.0),
                (1.0, -1.0, 0.0),
                (-1.0, 1.0, 0.0),
            ],
            dtype=float,
        )
        return MeshData(region), _hull(points * size)

    steps = _arc_steps(4.0 * size, math.pi / 2.0)
    angles = np.linspace(0.0, math.pi / 2.0, steps + 1)
    sine, cosine = np.sin(angles), np.cos(angles)
    # Analytische Endpunkte teilen wirklich dieselben Knoten mit den Seiten.
    sine[0], sine[-1] = 0.0, 1.0
    cosine[0], cosine[-1] = 1.0, 0.0
    vertices: list[tuple[float, float, float]] = []
    indices: dict[tuple[float, float, float], int] = {}
    rings: list[list[int]] = []
    faces: list[tuple[int, int, int]] = []
    for height, radius in zip(size * (sine - 1.0), size * (2.0 - cosine), strict=True):
        outline = [(-size, size), (-size, -size), (size, -size)]
        outline.extend(zip(size - radius * cosine[::-1], size - radius * sine[::-1], strict=True))
        ring = []
        for x, y in outline:
            point = (float(x), float(y), float(height))
            if point not in indices:
                indices[point] = len(vertices)
                vertices.append(point)
            ring.append(indices[point])
        rings.append(ring)

    for lower, upper in itertools.pairwise(rings):
        for first in range(len(lower)):
            second = (first + 1) % len(lower)
            faces.extend(
                (
                    (lower[first], lower[second], upper[second]),
                    (lower[first], upper[second], upper[first]),
                )
            )
    # Die Ecke (-size,-size) sieht den gesamten Querschnitt. Ihr Fächer
    # schließt die nicht konvexe Kontur, ohne den ausgesparten Viertelkreis.
    for ring, reverse in ((rings[0], True), (rings[-1], False)):
        for first in range(len(ring)):
            second = (first + 1) % len(ring)
            face = (ring[1], ring[first], ring[second])
            faces.append((face[0], face[2], face[1]) if reverse else face)
    # Am obersten Ring fallen die zwei Bogenenden mit den Quaderecken zusammen.
    faces = [face for face in faces if len(set(face)) == 3]
    target = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=False)
    return MeshData(region), MeshData(target)


def _extend_corner_contacts(body: MeshData, size: float) -> MeshData:
    """Extrudiert nur die fünf künstlichen Randflächen um EPS_GEOM nach außen."""
    import trimesh

    raw = body.raw
    for axis, level, sign in (
        (0, -size, -1.0),
        (0, size, 1.0),
        (1, -size, -1.0),
        (1, size, 1.0),
        (2, -size, -1.0),
    ):
        vertices = np.asarray(raw.vertices)
        faces = np.asarray(raw.faces)
        picked = np.max(np.abs(vertices[faces, axis] - level), axis=1) <= EPS_GEOM
        chosen = faces[picked]
        if not len(chosen):
            continue
        indices = np.unique(chosen)
        mapping = np.full(len(vertices), -1, dtype=np.int64)
        mapping[indices] = np.arange(len(indices)) + len(vertices)
        extra = vertices[indices].copy()
        extra[:, axis] += sign * EPS_GEOM
        oriented = np.concatenate([chosen[:, [0, 1]], chosen[:, [1, 2]], chosen[:, [2, 0]]])
        _, inverse, counts = np.unique(
            np.sort(oriented, axis=1), axis=0, return_inverse=True, return_counts=True
        )
        rim = oriented[counts[inverse] == 1]
        sides: list[tuple[int, int, int]] = []
        for first, second in rim:
            sides.extend(
                (
                    (first, second, mapping[second]),
                    (first, mapping[second], mapping[first]),
                )
            )
        raw = trimesh.Trimesh(
            vertices=np.vstack([vertices, extra]),
            faces=np.vstack([faces[~picked], mapping[chosen], sides]),
            process=False,
        )
    return MeshData(raw)


def _corner_stars(
    entries: Sequence[MeshEdge], selected: Sequence[MeshEdge]
) -> list[list[tuple[MeshEdge, int]]]:
    """Die vollständig gewählten Knoten der ursprünglichen Netztopologie.

    Ein offener Kantenzug endet an einem wirklichen Netzknoten. Seine Nummer
    bleibt hier erhalten; ein räumlich naher, aber getrennter Körper darf
    nicht versehentlich dieselbe Eckfläche bekommen.
    """
    stars: dict[int, list[tuple[MeshEdge, int]]] = {}
    for entry in entries:
        if not entry.node_indices or entry.node_indices[0] == entry.node_indices[-1]:
            continue
        for end in (0, -1):
            stars.setdefault(entry.node_indices[end], []).append((entry, end))
    selected_ids = {id(entry) for entry in selected}
    return [
        star
        for star in stars.values()
        if len(star) > THROUGH and all(id(entry) in selected_ids for entry, _ in star)
    ]


def _distinct_vectors(vectors: Sequence[np.ndarray]) -> np.ndarray:
    """Gleichgerichtete Flächennormalen nur einmal, unabhängig von Dreiecken."""
    unique: list[np.ndarray] = []
    for vector in vectors:
        if not any(float(np.linalg.norm(vector - other)) <= EPS_GEOM for other in unique):
            unique.append(vector)
    return np.asarray(unique)


def _cone_planes(normals: np.ndarray) -> np.ndarray:
    """Stützebenen des positiven Normalenkegels, mit der Außenseite positiv."""
    planes: list[np.ndarray] = []
    for first, second in itertools.combinations(normals, 2):
        direction = np.cross(first, second)
        length = float(np.linalg.norm(direction))
        if length <= EPS_GEOM:
            continue
        direction /= length
        products = normals @ direction
        if float(products.max()) <= EPS_GEOM:
            planes.append(direction)
        elif float(products.min()) >= -EPS_GEOM:
            planes.append(-direction)
    return _distinct_vectors(planes)


def _halfspace_vertices(normals: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    """Die Ecken eines beschränkten Schnitts von Halbräumen n·x <= d."""
    points: list[np.ndarray] = []
    for indices in itertools.combinations(range(len(normals)), 3):
        rows = normals[list(indices)]
        if abs(float(np.linalg.det(rows))) <= EPS_GEOM:
            continue
        point = np.linalg.solve(rows, offsets[list(indices)])
        if bool(np.all(normals @ point <= offsets + EPS_GEOM)):
            points.append(point)
    return _distinct_vectors(points)


def _hull(points: np.ndarray) -> MeshData:
    """Ein kleiner konvexer Werkzeugkörper aus seinen geometrischen Eckpunkten."""
    import trimesh

    return MeshData(trimesh.convex.convex_hull(points))


def _corner_ball(radius: float) -> np.ndarray:
    """Kugelknoten mit begrenzter Facettenabweichung auch im Dreiecksinneren."""
    import trimesh

    divisions = 0
    while True:
        ball = trimesh.creation.icosphere(subdivisions=divisions, radius=radius)
        supports = np.einsum("ij,ij->i", ball.triangles[:, 0], ball.face_normals)
        arcs = np.linalg.norm(np.diff(ball.vertices[ball.edges_unique], axis=1)[:, 0], axis=1)
        if float(supports.min()) >= radius - MAX_FACET_SAG and float(arcs.max()) <= (
            2.0 * radius * math.sin(MAX_FACET_ANGLE / 2.0)
        ):
            return np.asarray(ball.vertices)
        divisions += 1


def _chamfer_contacts(
    star: list[tuple[MeshEdge, int]], normals: np.ndarray, size: float, sign: float
) -> np.ndarray:
    """Schnittpunkte der beiden Fasenflanken auf jeder ursprünglichen Fläche."""
    boundaries: list[tuple[np.ndarray, float, np.ndarray]] = []
    for entry, end in star:
        pair = sign * np.asarray(entry.normals[end], dtype=float)
        along = np.asarray(entry.points[1 if end == 0 else -2]) - entry.points[end]
        along /= float(np.linalg.norm(along))
        bisector = pair.sum(axis=0)
        bisector /= float(np.linalg.norm(bisector))
        inward = _along_face(pair[0], along, -bisector)
        assert inward is not None
        boundaries.append((bisector, float(size * np.dot(bisector, inward)), pair))
    contacts: list[np.ndarray] = []
    for normal in normals:
        touching = [
            (bisector, offset)
            for bisector, offset, pair in boundaries
            if bool(np.any(np.linalg.norm(pair - normal, axis=1) <= EPS_GEOM))
        ]
        if len(touching) != THROUGH:
            continue
        rows = np.vstack([normal, touching[0][0], touching[1][0]])
        contacts.append(np.linalg.solve(rows, [0.0, touching[0][1], touching[1][1]]))
    return np.asarray(contacts)


def _corner_tools(
    star: list[tuple[MeshEdge, int]], size: float, *, rounded: bool, ball_vertices: np.ndarray
) -> tuple[BooleanKind, MeshData, list[BooleanOutcome]] | None:
    """Die Eckfläche verbindet die Flanken am ursprünglichen gemeinsamen Knoten.

    Eine Kugel ersetzt bei gleichem Radius die Zylinderschnitte innerhalb
    ihres Normalenkegels. Der Bereich reicht bis zu den Nachbarflächen;
    das Tetraeder aus Ecke und Berührpunkten wäre zu klein. Eine Fase
    verbindet stattdessen die Schnittpunkte auf diesen Flächen.
    """
    entry, end = star[0]
    if any(other.convex != entry.convex for other, _ in star):
        return None
    sign = 1.0 if entry.convex else -1.0
    normals = _distinct_vectors(
        [sign * np.asarray(normal) for other, tip in star for normal in other.normals[tip]]
    )
    if len(normals) < 3:
        return None
    vertex = np.asarray(entry.points[end])
    kind: BooleanKind = "difference" if entry.convex else "union"
    if not rounded:
        contacts = _chamfer_contacts(star, normals, size, sign)
        cap = _hull(np.vstack([np.zeros(3), contacts])).raw
        offsets = np.einsum("ij,ij->i", cap.face_normals, cap.triangles[:, 0])
        beyond = offsets > EPS_GEOM
        # Nur die äußeren Hilfsflächen bekommen Überstand. Die eigentliche
        # Eckfläche bleibt exakt auf den berechneten Kontaktpunkten.
        overshoot = EDGE_OVERSHOOT if entry.convex else 0.0
        corners = _halfspace_vertices(
            np.vstack([normals, cap.face_normals[beyond]]),
            np.concatenate([np.full(len(normals), overshoot), offsets[beyond]]),
        )
        return kind, _hull(corners + vertex), []
    centre = np.linalg.lstsq(normals, np.full(len(normals), -size), rcond=None)[0]
    if float(np.max(np.abs(normals @ centre + size))) > EPS_GEOM:
        # Mehr als drei Flächen haben nicht notwendig ein gemeinsames
        # Offsetzentrum. Der wirkliche versetzte Polyeder besitzt dann
        # mehrere Ecken und verbindende Grate. Seine Minkowski-Summe mit
        # der Kugel verbindet sie, ohne ein beliebiges Ebenentripel zu wählen.
        eroded = _halfspace_vertices(normals, np.full(len(normals), -size))
        axis = normals.sum(axis=0)
        axis /= float(np.linalg.norm(axis))
        depth = float(np.min(eroded @ axis)) - size
        rows = np.vstack([normals, -axis])
        corners = _halfspace_vertices(
            rows, np.append(np.full(len(normals), EDGE_OVERSHOOT), -depth)
        )
        # Die künstliche Abschlussebene liegt eine weitere Kugelbreite
        # hinter dem Werkzeugrand und kann dessen Fläche nicht beeinflussen.
        core = _halfspace_vertices(rows, np.append(np.full(len(normals), -size), size - depth))
        ball_points = (core[:, None, :] + ball_vertices).reshape(-1, 3)
    else:
        cone = _cone_planes(normals)
        corners = _halfspace_vertices(
            np.vstack([normals, cone]),
            np.concatenate([np.full(len(normals), EDGE_OVERSHOOT), cone @ centre]),
        )
        ball_points = ball_vertices + centre
    local = _hull(corners + vertex)
    ball = _hull(ball_points + vertex)
    removed = boolean("difference", [local, ball], quality="fine", allow_empty=True)
    return kind, removed.mesh, [removed]


def _mixed_corner_frame(star: list[tuple[MeshEdge, int]]) -> tuple[np.ndarray, bool] | None:
    """Der lokale Rahmen eines gemischten orthogonalen Dreiflächenknotens."""
    convex_count = sum(entry.convex for entry, _ in star)
    if len(star) != 3 or convex_count not in (1, 2):
        return None
    complement = convex_count == 1
    lone, end = next((entry, end) for entry, end in star if entry.convex == complement)
    sign = -1.0 if complement else 1.0
    sides = sign * np.asarray(lone.normals[end])
    normals = _distinct_vectors(
        [sign * np.asarray(normal) for entry, tip in star for normal in entry.normals[tip]]
    )
    if len(normals) != 3:
        return None
    top = next(
        normal
        for normal in normals
        if bool(np.all(np.linalg.norm(sides - normal, axis=1) > EPS_GEOM))
    )
    axes = np.column_stack([sides[0], sides[1], top])
    if not bool(np.all(np.abs(axes.T @ axes - np.eye(3)) <= EPS_GEOM)):
        return None
    frame = np.eye(4)
    frame[:3, :3] = axes
    frame[:3, 3] = lone.points[end]
    return frame, complement


def _check_corner_region(
    mesh: MeshData, region: MeshData, frame: np.ndarray, size: float, complement: bool
) -> BooleanOutcome:
    """Der örtliche Ersatz muss ausschließlich die drei gewählten Flächen treffen."""
    clipped = boolean("intersection", [mesh, region], quality="fine", allow_empty=True)
    local = (clipped.mesh.raw.triangles - frame[:3, 3]) @ frame[:3, :3]
    allowed = np.zeros(len(local), dtype=bool)
    for axis, levels in ((0, (-size, 0.0, size)), (1, (-size, 0.0, size)), (2, (-size, 0.0))):
        for level in levels:
            allowed |= np.max(np.abs(local[:, :, axis] - level), axis=1) <= EPS_GEOM
    expected = (1.0 if complement else 3.0) * size**3
    if not bool(allowed.all()) or abs(clipped.mesh.volume - expected) > EPS_GEOM * region.raw.area:
        raise GeometryError(
            detail=_(
                "Die Eckbearbeitung würde ein weiteres Detail verändern. Wählen Sie "
                "ein kleineres Maß oder bearbeiten Sie die Kanten einzeln."
            ),
            values={"size": size},
        )
    return clipped


def _selected_edge_groups(selected: Sequence[MeshEdge]) -> list[list[MeshEdge]]:
    """Verbindet gewählte Züge über ihre ursprünglichen gemeinsamen Knoten."""
    around: dict[int, list[int]] = {}
    for index, entry in enumerate(selected):
        for node in (entry.node_indices[0], entry.node_indices[-1]):
            around.setdefault(node, []).append(index)
    remaining = set(range(len(selected)))
    groups: list[list[MeshEdge]] = []
    while remaining:
        pending = [min(remaining)]
        connected: set[int] = set()
        while pending:
            index = pending.pop()
            if index not in remaining:
                continue
            remaining.remove(index)
            connected.add(index)
            entry = selected[index]
            for node in (entry.node_indices[0], entry.node_indices[-1]):
                pending.extend(around[node])
        groups.append([selected[index] for index in sorted(connected)])
    return groups


def _worked_edges(
    mesh: MeshData,
    size: float,
    choice: EdgeChoice,
    keys: Sequence[str],
    *,
    rounded: bool,
) -> BooleanOutcome:
    """Löst die Auswahl im Weltsystem und rechnet gemischte Ecken in ihrem Rahmen."""
    entries = edges_of(mesh)
    chosen = wanted(entries, choice, keys)
    groups = _selected_edge_groups(chosen)
    mixed = any(_mixed_corner_frame(star) is not None for star in _corner_stars(entries, chosen))
    if len(groups) == 1 or not mixed:
        return _placed_edge_work(mesh, entries, chosen, size, rounded=rounded)
    runs: list[BooleanOutcome] = []
    body = mesh
    for group in groups:
        result = _placed_edge_work(body, entries, group, size, rounded=rounded)
        runs.append(result)
        body = result.mesh
    solver = deepest(run.solver for run in runs)
    assert solver is not None
    return BooleanOutcome(body, solver, [finding for run in runs for finding in run.findings])


def _placed_edge_work(
    mesh: MeshData,
    entries: Sequence[MeshEdge],
    chosen: Sequence[MeshEdge],
    size: float,
    *,
    rounded: bool,
) -> BooleanOutcome:
    """Rechnet eine unabhängige Auswahlgruppe mit ihrer unveränderten Ausgangstopologie."""
    frame = next(
        (
            located[0]
            for star in _corner_stars(entries, chosen)
            if (located := _mixed_corner_frame(star)) is not None
        ),
        None,
    )
    if frame is None:
        return _edge_work(mesh, entries, chosen, size, rounded=rounded)
    raw = mesh.raw.copy()
    delta = np.asarray(raw.vertices) - frame[:3, 3]
    local = delta @ frame[:3, :3]
    # Subtraktion, Skalarprodukte und die vorher berechneten Einheitsnormalen
    # tragen Float64-Rauschen. Nur dessen Band an den drei belegten Ebenen
    # durch den Knoten wird bereinigt, kein geometrischer Abstand gerundet.
    roundoff = 32.0 * np.finfo(float).eps
    error = roundoff * (np.abs(delta) @ np.abs(frame[:3, :3]) + np.abs(frame[:3, 3]).sum() + 1.0)
    local[np.abs(local) <= error] = 0.0
    raw.vertices = local
    if float(np.linalg.det(frame[:3, :3])) < 0.0:
        raw.faces = raw.faces[:, ::-1]
    local_entries: list[MeshEdge] = []
    local_chosen: list[MeshEdge] = []
    selected_ids = {id(entry) for entry in chosen}
    for entry in entries:
        # Nach einer anderen Auswahlgruppe ist der Körper neu vernetzt.
        # Die gespeicherten Knotennummern verbinden weiterhin die gewählten
        # Züge, sind aber keine Indizes dieses Zwischenkörpers mehr.
        offset = np.asarray(entry.points) - frame[:3, 3]
        points = offset @ frame[:3, :3]
        noise = roundoff * (
            np.abs(offset) @ np.abs(frame[:3, :3]) + np.abs(frame[:3, 3]).sum() + 1.0
        )
        points[np.abs(points) <= noise] = 0.0
        normals = np.asarray(entry.normals) @ frame[:3, :3]
        normals[np.abs(normals) <= roundoff] = 0.0
        normals /= np.linalg.norm(normals, axis=2, keepdims=True)
        placed = _describe(
            points,
            entry.convex,
            tuple((pair[0], pair[1]) for pair in normals),
            entry.node_indices,
        )
        assert placed is not None
        local_entries.append(placed)
        if id(entry) in selected_ids:
            local_chosen.append(placed)
    result = _edge_work(mesh.replacing(raw), local_entries, local_chosen, size, rounded=rounded)
    world = result.mesh.raw.copy()
    world.apply_transform(frame)
    result.mesh = result.mesh.replacing(world)
    return result


def _edge_work(
    mesh: MeshData,
    entries: Sequence[MeshEdge],
    chosen: Sequence[MeshEdge],
    size: float,
    *,
    rounded: bool,
) -> BooleanOutcome:
    """Der gemeinsame Weg von Verrundung und Fase.

    **Zwei Richtungen, zwei Rechnungen.** An einer Außenkante wird der Zwickel
    abgezogen, an einer Innenkante dazugelegt; wer beides in einem Zug
    versuchte, müsste die Werkzeuge vorher trennen und käme auf denselben Weg
    zurück. Gemeldet wird die **tiefste** Stufe beider Läufe
    (:func:`~app.core.geom.boolean.deepest`): Wer wissen will, was seine Maße
    wert sind, interessiert sich für die, die am stärksten geglättet hat.
    """
    stars = _corner_stars(entries, chosen)
    mixed = [
        (star, located) for star in stars if (located := _mixed_corner_frame(star)) is not None
    ]
    refined_ids = {id(entry) for star, _ in mixed for entry, _ in star}
    steps = _arc_steps(4.0 * size, math.pi / 2.0) if mixed and rounded else 0
    outer: list[MeshData] = []
    inner: list[MeshData] = []
    for entry in chosen:
        tool = rounding_tool(
            entry,
            size,
            rounded,
            min_steps=steps if id(entry) in refined_ids else 0,
            extend_ends=id(entry) not in refined_ids,
        )
        (outer if entry.convex else inner).append(tool)
    runs: list[BooleanOutcome] = []
    ball_vertices = _corner_ball(size) if stars and rounded else np.empty((0, 3))
    for star in stars:
        prepared = _corner_tools(star, size, rounded=rounded, ball_vertices=ball_vertices)
        if prepared is not None:
            kind, tool, preparation = prepared
            runs.extend(preparation)
            (outer if kind == "difference" else inner).append(tool)
    regions: list[MeshData] = []
    targets: list[MeshData] = []
    for _star, (frame, complement) in mixed:
        region, target = _mixed_corner_region(size, rounded=rounded)
        if complement:
            reversed_target = boolean("difference", [region, target], quality="fine")
            runs.append(reversed_target)
            target = reversed_target.mesh
        target = _extend_corner_contacts(target, size)
        region.raw.apply_transform(frame)
        target.raw.apply_transform(frame)
        runs.append(_check_corner_region(mesh, region, frame, size, complement))
        regions.append(region)
        targets.append(target)
    if regions:
        clipped_inner = []
        for tool in inner:
            clipped = boolean("difference", [tool, *regions], quality="fine", allow_empty=True)
            runs.append(clipped)
            if clipped.mesh.triangle_count:
                clipped_inner.append(clipped.mesh)
        inner = [*clipped_inner, *targets]
        outer.extend(regions)

    body = mesh
    for kind, tools in (("difference", outer), ("union", inner)):
        if not tools:
            continue
        outcome = boolean(kind, [body, *tools], quality="fine")
        body = outcome.mesh
        runs.append(outcome)
    # Ohne Kante hätte ``wanted`` angehalten, und ``rounding_tool`` wirft,
    # statt nichts zu liefern — einer der beiden Läufe hat also stattgefunden.
    # **Was kein Volumen hat, ist kein Körper.** Wo das Werkzeug über eine schon
    # facettierte Rundung läuft, bleiben einzelne Flächenpaare ohne Dicke
    # stehen; der Prüfbericht meldete sie als zerfallenen Körper.
    cleaned, shells = remove_hollow_shells(body)
    if shells:
        _log.debug("removed %d hollow shells after edge work", shells)
        body = cleaned

    solver = deepest(run.solver for run in runs)
    return BooleanOutcome(
        mesh=body,
        solver=solver if solver is not None else runs[0].solver,
        findings=[finding for run in runs for finding in run.findings],
    )


@dataclass(frozen=True, slots=True)
class SharpCorner:
    """Die Kante, die unter einer erkannten Rundung liegt.

    ``reach`` ist, wie weit die Rundung auf jeder der beiden Flächen greift —
    gemessen an ihren eigenen Knoten und nicht aus dem Radius gerechnet.
    """

    start: np.ndarray
    end: np.ndarray
    first: Vec3
    second: Vec3
    reach: float
    convex: bool


def sharp_corner(mesh: MeshData, feature: Feature) -> SharpCorner:
    """Rechnet aus einer erkannten Rundung die Kante zurück, die sie ersetzt hat.

    **Über den Schnitt der beiden Nachbarebenen und nicht über den Radius.**
    Der erkannte Radius stammt aus einem Sehnenzug und ist deshalb ein wenig
    zu klein — gemessen 2,9772 an einer Rundung, die mit 3,0 gebaut wurde. Die
    daraus gerechnete Kante läge 0,023 mm neben der wirklichen, und der
    Füllkörper ließe an der Ecke eine Fehlstelle. Die zwei Ebenen daneben sind
    exakt: Ihre Schnittgerade **ist** die Kante.
    """
    triangles = [int(index) for index in feature.face_indices]
    if not triangles:
        raise GeometryError(
            detail=_(
                "Zu dieser Rundung sind die Flächen nicht bekannt. Lesen Sie das "
                "Modell neu ein und wählen Sie sie erneut."
            ),
        )
    axis = np.asarray(feature.params["axis"], dtype=float)
    axis = axis / float(np.linalg.norm(axis))
    normals, neighbours = _around(mesh, triangles, axis)
    if len(normals) < THROUGH:
        raise GeometryError(
            detail=_(
                "Diese Rundung grenzt nicht an zwei ebene Flächen — sie lässt sich "
                "nicht auf eine Kante zurückführen. Verrunden Sie stattdessen neu."
            ),
        )
    first, second = normals[0], normals[1]
    line, point = _plane_cut(first, neighbours[0], second, neighbours[1])

    if float(np.dot(axis, line)) < 0.0:
        line = -line
    centre = np.asarray(feature.params["centre"], dtype=float)
    # **Ohne Überstand.** Der Füllkörper wird vereinigt, und was über das Ende
    # der Kante hinausragt, klebt außen am Körper an statt zu helfen — gemessen
    # 24000,72 mm³ statt 24000,0 und ein Quader, der 20,04 mm hoch war. Derselbe
    # Fall wie bei der Kehle in :func:`_wedge`, nur eine Handlung weiter.
    half = float(feature.params.get("length", 0.0)) / 2.0
    middle = point + line * float(np.dot(centre - point, line))

    corners = np.asarray(mesh.raw.faces, dtype=np.int64)[triangles]
    points = np.asarray(mesh.raw.vertices, dtype=float)[np.unique(corners)]
    # Wie weit die Rundung auf den Flächen greift: der weiteste ihrer eigenen
    # Knoten, quer zur Kante gemessen. Ein Füllkörper, der genauso weit reicht,
    # deckt den Bogen sicher ab und liegt mit seinen Flanken trotzdem in den
    # Nachbarebenen — dort ist ohnehin Material (§39, „überall breiter").
    across = points - middle
    reach = float(np.max(np.linalg.norm(across - np.outer(across @ line, line), axis=1)))
    return SharpCorner(
        start=middle - line * half,
        end=middle + line * half,
        first=tuple(float(value) for value in first),  # type: ignore[arg-type]
        second=tuple(float(value) for value in second),  # type: ignore[arg-type]
        reach=reach,
        # **Die Hohlraumfrage steht in ``types.is_a_cavity``**, nicht hier: Eine
        # Kehle ist ein Hohlraum, ein Wulst Materie, und wer das zweimal
        # beantwortet, bekommt zwei Antworten.
        convex=not is_a_cavity(feature),
    )


def _around(
    mesh: MeshData, triangles: list[int], axis: np.ndarray
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Die Normalen der angrenzenden Flächen und je ein Punkt darauf.

    **Nur die quer zur Achse.** Eine Rundung an einer senkrechten Kante grenzt
    auch an Deckel und Boden, und die beiden sind einander entgegengesetzt:
    Der erste Anlauf nahm sie als das gesuchte Paar und bekam „diese Flächen
    sind parallel" zurück. Gesucht sind die Flächen, zwischen denen die
    Rundung *liegt*, und die stehen senkrecht auf ihrer Achse.
    """
    own = set(triangles)
    raw = mesh.raw
    face_normals = np.asarray(raw.face_normals, dtype=float)
    centres = np.asarray(raw.triangles_center, dtype=float)
    normals: list[np.ndarray] = []
    places: list[np.ndarray] = []
    for a, b in np.asarray(raw.face_adjacency, dtype=np.int64).tolist():
        outside = b if a in own and b not in own else a if b in own and a not in own else None
        if outside is None:
            continue
        normal = face_normals[outside]
        if abs(float(np.dot(normal, axis))) > UPRIGHT_TO_AXIS:
            continue
        if any(float(np.dot(normal, seen)) > 1.0 - EPS_GEOM for seen in normals):
            continue
        normals.append(normal)
        places.append(centres[outside])
    return normals, places


def _plane_cut(
    first: np.ndarray, on_first: np.ndarray, second: np.ndarray, on_second: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Schnittgerade zweier Ebenen: Richtung und ein Punkt darauf."""
    line = np.cross(first, second)
    length = float(np.linalg.norm(line))
    if length <= EPS_GEOM:
        raise GeometryError(
            detail=_(
                "Die beiden Flächen neben dieser Rundung sind parallel — dazwischen "
                "liegt keine Kante."
            ),
        )
    line = line / length
    # Der Punkt auf beiden Ebenen, der der Bauart nach am stabilsten ist:
    # gelöst wird das 3x3-System aus den zwei Ebenen und der Schnittgeraden.
    matrix = np.vstack([first, second, line])
    right = np.array(
        [float(np.dot(first, on_first)), float(np.dot(second, on_second)), 0.0], dtype=float
    )
    return line, np.linalg.solve(matrix, right)


def unround(mesh: MeshData, feature: Feature) -> BooleanOutcome:
    """Nimmt eine erkannte Rundung weg und stellt die scharfe Kante her.

    Der Füllkörper ist der **Zwickel ohne Bogen** — das Dreieck zwischen der
    Kante und den beiden Berührlinien. Er deckt den Bogen vollständig ab, und
    seine Flanken liegen in den Nachbarebenen, wo ohnehin Material ist. Einen
    Körper zu bauen, der die Rundungsfläche nachzeichnet, wäre der Fehler, den
    `.claude/rules/operationen.md` unter „Ein Füllkörper hat die Form des
    Werkzeugs" beschreibt: Er endete **auf** der Fläche, und übrig blieben zwei
    Flächen nebeneinander statt einer.

    An einer Hohlkehle (``recess``) geht es umgekehrt: Dort hat die Rundung
    Material hinzugefügt, und der Zwickel wird abgezogen.
    """
    corner = sharp_corner(mesh, feature)
    filler = _wedge(
        corner.start,
        corner.end,
        corner.first,
        corner.second,
        corner.reach,
        corner.convex,
        rounded=False,
        # Umgekehrt zum Verrunden: An einer Außenkante wird hier **vereinigt**.
        subtracted=not corner.convex,
    )
    if filler is None:
        raise GeometryError(
            detail=_(
                "Diese Rundung lässt sich nicht auf eine Kante zurückführen — "
                "verrunden Sie stattdessen neu."
            ),
        )
    kind: BooleanKind = "union" if corner.convex else "difference"
    outcome = boolean(kind, [mesh, filler], quality="fine")
    return BooleanOutcome(mesh=outcome.mesh, solver=outcome.solver, findings=list(outcome.findings))


def reround(mesh: MeshData, feature: Feature, radius: float) -> BooleanOutcome:
    """Ändert den Radius einer erkannten Rundung — wegnehmen, neu verrunden.

    **Zwei Schritte und nicht einer**, weil es zwischen ihnen etwas gibt, das
    beide brauchen: die scharfe Kante. Eine Rundung direkt zu vergrößern hieße,
    den Bogen zu verschieben und die Berührlinien mitzuziehen — dieselbe
    Rechnung, nur ohne den Zwischenstand, an dem man sie prüfen kann.

    Die Kante wird über ihren **Schlüssel** wiedergefunden und nicht über einen
    Index: Zwischen Auffüllen und Neuverrunden ist das Netz ein anderes, und
    jede Nummer darin zeigt danach woandershin (§21.2).
    """
    if radius <= EPS_GEOM:
        raise ValidationError(
            "diameter",
            _("Ohne Radius entsteht keine Rundung. Dieser Wert muss größer als null sein."),
            value=radius,
        )
    corner = sharp_corner(mesh, feature)
    taken = unround(mesh, feature)
    key = edge_key(_placed(corner))
    again = round_edges(taken.mesh, radius, "named", [key])
    return BooleanOutcome(
        mesh=again.mesh,
        solver=deepest([taken.solver, again.solver]) or again.solver,
        findings=[*taken.findings, *again.findings],
    )


@dataclass(frozen=True, slots=True)
class _Placed:
    middle: Vec3
    direction: Vec3
    extent: float


def _placed(corner: SharpCorner) -> _Placed:
    """Die wiederhergestellte Kante, so beschrieben, wie ``edge_key`` sie liest."""
    middle = (corner.start + corner.end) / 2.0
    along = corner.end - corner.start
    along = along / float(np.linalg.norm(along))
    return _Placed(
        middle=(float(middle[0]), float(middle[1]), float(middle[2])),
        direction=(float(along[0]), float(along[1]), float(along[2])),
        extent=float(np.linalg.norm(corner.end - corner.start)) / 2.0,
    )


def bead_edges(
    mesh: MeshData,
    radius: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
) -> BooleanOutcome:
    """Legt einen Wulst auf die gewählten Kanten — eine runde Leiste.

    Die Gegenrichtung zum Verrunden: Dort geht an einer Außenkante Material
    weg, hier kommt welches dazu. Gebaut wird ein **Rundstab** auf der Kante —
    ein Zylinder, dessen Achse auf ihr liegt; was davon im Material steckt,
    verschwindet in der Vereinigung.

    **An einer Innenkante liegt derselbe Stab im Eck** — eine Kehlnaht, wie
    sie beim Schweißen entsteht. Gemessen an einer Nut mit R = 1,5: 104,45 mm³
    kommen dazu, also der Viertelkreis (analytisch 106,03; der Rest ist die
    Facettierung).

    **Das ist nicht die glatte Hohlkehle**, und der Unterschied ist keine
    Feinheit: Die Hohlkehle nimmt dem Innenwinkel seine Kante, indem sie den
    Zwickel füllt — 28,97 mm³ an derselben Nut —, und dafür gibt es
    :func:`round_edges` an einer konkaven Kante. Der erste Entwurf dieser
    Funktion versprach im Docstring die Hohlkehle und lieferte die Naht; die
    Zahl daneben hat es gesagt (Robert, 10.09.2026: „Hohlkehlen, Wulst und
    Verrundung müssen noch bearbeitbar sein bzw auch anlegbar sein").
    """
    if radius <= EPS_GEOM:
        raise ValidationError(
            "radius",
            _("Ohne Radius entsteht kein Wulst. Dieser Wert muss größer als null sein."),
            value=radius,
        )
    chosen = wanted(edges_of(mesh), choice, keys)
    # **Jedes Stück einzeln in die Kette.** Zusammengelegt (``concatenate``)
    # überlappen sich die Zylinder eines Zugs an ihren Knicken, und ein Körper
    # mit doppelt belegtem Raum hat kein wohldefiniertes Volumen: Am
    # unterteilten Quader kamen 24250 mm³ heraus statt 24186. Die Vereinigung
    # löst die Überlappung, dafür ist sie da.
    tools: list[MeshData] = []
    for entry in chosen:
        tools.extend(_rod_along(entry, radius))
    return boolean("union", [mesh, *tools], quality="fine")


def _rod_along(entry: MeshEdge, radius: float) -> list[MeshData]:
    """Der Rundstab entlang eines Kantenzugs — Zylinder je Stück, Kugel je Knick.

    Die Kugeln sind kein Zierat: An einem Knick des Zugs stoßen zwei Zylinder
    unter einem Winkel aneinander und lassen außen einen Keil frei. Eine Kugel
    im Knoten füllt ihn, und zwar für jeden Winkel dieselbe.
    """
    import trimesh

    points = np.asarray(entry.points, dtype=float)
    parts: list[Any] = []
    for first, second in itertools.pairwise(points):
        along = second - first
        reach = float(np.linalg.norm(along))
        if reach <= EPS_GEOM:
            continue
        rod = trimesh.creation.cylinder(radius=radius, height=reach, sections=_ring_steps(radius))
        rod.apply_transform(_towards(along / reach, (first + second) / 2.0))
        parts.append(rod)
    for point in points[1:-1] if len(points) > THROUGH else []:
        ball = trimesh.creation.icosphere(subdivisions=1, radius=radius)
        ball.apply_translation(point)
        parts.append(ball)
    if not parts:
        raise GeometryError(
            detail=_(
                "Diese Kante ist zu kurz für einen Wulst. Wählen Sie eine andere "
                "oder einen kleineren Radius."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return [MeshData(part) for part in parts]


def _ring_steps(radius: float) -> int:
    """Wie viele Segmente ein voller Kreis dieses Radius bekommt.

    Dieselbe Rechnung wie beim Rundungsbogen, nur über den ganzen Umlauf:
    ``_arc_steps`` hält ``MAX_FACET_SAG`` und ``MAX_FACET_ANGLE`` ein, und ein
    Wulst darf nicht kantiger sein als die Verrundung daneben.
    """
    return _arc_steps(radius, 2.0 * math.pi)


def _towards(along: np.ndarray, middle: np.ndarray) -> np.ndarray:
    """Der Rahmen, der einen Zylinder von +Z auf die Kantenrichtung dreht."""
    frame = np.eye(4)
    helper = np.array([0.0, 0.0, 1.0]) if abs(float(along[2])) < 0.9 else np.array([1.0, 0.0, 0.0])
    across = np.cross(helper, along)
    across = across / float(np.linalg.norm(across))
    frame[:3, 0] = across
    frame[:3, 1] = np.cross(along, across)
    frame[:3, 2] = along
    frame[:3, 3] = middle
    return frame
