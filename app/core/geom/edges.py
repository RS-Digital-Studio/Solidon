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
from typing import Any, Literal, Protocol, cast

import numpy as np

from app.core.errors import GeometryError, ValidationError
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
    ``direction`` und ``length`` sind die drei Zahlen, aus denen
    :func:`edge_key` den Schlüssel baut, und sie bedeuten dasselbe wie bei
    ``brep.edit.EdgeInfo``: die Mitte des Zugs, seine Richtung von Anfang zu
    Ende, seine Länge entlang der Punkte.

    ``normals`` trägt je **Stück** des Zugs die zwei Flächennormalen, zwischen
    denen es liegt — so viele Paare, wie es Stücke gibt. Ein Werkzeug zum
    Verrunden entsteht daraus: Wo die beiden Flächen zusammenstoßen, sagt
    ihre Winkelhalbierende, wohin die Rundung geht, und der Winkel zwischen
    ihnen, wie weit. Am Zug variieren sie, deshalb je Stück und nicht je
    Kante — bei einem Bogen dreht sich die Halbierende mit.
    """

    points: tuple[Vec3, ...]
    length: float
    direction: Vec3
    middle: Vec3
    convex: bool
    normals: tuple[tuple[Vec3, Vec3], ...] = ()

    @property
    def upright(self) -> bool:
        return abs(self.direction[2]) > 0.9

    @property
    def flat(self) -> bool:
        return abs(self.direction[2]) < 0.1


class HasPlacement(Protocol):
    """Was :func:`edge_key` von einer Kante braucht — und mehr nicht.

    ``MeshEdge`` und ``brep.edit.EdgeInfo`` haben nichts gemeinsam als diese
    zwei Zahlen, und für den Schlüssel genügen sie beiden. Dieselbe Bauart
    wie ``boolean.HasVolume``, und aus demselben Grund: Die Funktion soll für
    beide Kerne gelten, ohne einen von ihnen zu kennen.
    """

    @property
    def middle(self) -> Vec3: ...

    @property
    def direction(self) -> Vec3: ...


def edge_key(entry: HasPlacement) -> str:
    """Der stabile Verweis auf **eine** Kante — Mittelpunkt und Richtung.

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
    """
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
        described = _describe(points, is_convex, normals)
        if described is not None:
            found.append(described)
    return found


def _describe(
    points: np.ndarray, convex: bool, normals: tuple[tuple[np.ndarray, np.ndarray], ...] = ()
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
    """
    described = {edge_key(entry): entry for entry in edges}
    return [described[key] for key in keys if key in described]


def wanted[AnyEdge: SelectableEdge](
    edges: Sequence[AnyEdge], choice: EdgeChoice, keys: Sequence[str]
) -> list[AnyEdge]:
    """Die Kanten, die dieser Aufruf behandelt — genannte vor Gruppe (E4).

    Eine leere Auswahl ist an beiden Wegen ein Satz und kein leerer Körper,
    aber sie hat **verschiedene Gründe**: Bei einer Gruppe gibt es die Sorte
    Kante nicht, bei genannten sind sie verschwunden — ein Schritt davor hat
    sie weggenommen. Wer denselben Satz für beides schriebe, schickte den
    Kunden in die falsche Richtung (Regel 17).
    """
    if choice == "named" and not keys:
        raise GeometryError(
            detail=_("Für diese Auswahl ist noch keine Kante benannt — wählen Sie eine aus."),
            values={"choice": choice},
        )
    if keys:
        chosen = named_edges(edges, keys)
        if not chosen:
            raise GeometryError(
                detail=_(
                    "Die gewählten Kanten gibt es an diesem Körper nicht mehr — "
                    "ein Schritt davor hat sie verändert. Wählen Sie sie neu."
                ),
                values={"edges": len(keys)},
            )
        return chosen
    chosen = choose(edges, choice)
    if not chosen:
        raise GeometryError(
            detail=_("Zu dieser Auswahl gehört keine Kante."),
            values={"choice": choice},
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


def rounding_tool(entry: MeshEdge, radius: float, rounded: bool = True) -> MeshData:
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
            subtracted=entry.convex,
        )
        if wedge is not None:
            pieces.append(wedge)
    if not pieces:
        raise GeometryError(
            detail=_(
                "Das Maß ist für diese Kante zu groß — sie hat keine Flächen, auf "
                "denen die Bearbeitung Platz findet. Wählen Sie ein kleineres."
            ),
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
        bow = _arc(centre, first_touch, second_touch, radius)
    profile = [start, first_touch, *bow, second_touch]

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
    centre: np.ndarray, first: np.ndarray, second: np.ndarray, radius: float
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
    steps = _arc_steps(radius, span)
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


def _worked_edges(
    mesh: MeshData,
    size: float,
    choice: EdgeChoice,
    keys: Sequence[str],
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
    chosen = wanted(edges_of(mesh), choice, keys)
    outer = [rounding_tool(entry, size, rounded) for entry in chosen if entry.convex]
    inner = [rounding_tool(entry, size, rounded) for entry in chosen if not entry.convex]

    body = mesh
    runs: list[BooleanOutcome] = []
    for kind, tools in (("difference", outer), ("union", inner)):
        if not tools:
            continue
        outcome = boolean(cast(BooleanKind, kind), [body, *tools], quality="fine")
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


def _placed(corner: SharpCorner) -> _Placed:
    """Die wiederhergestellte Kante, so beschrieben, wie ``edge_key`` sie liest."""
    middle = (corner.start + corner.end) / 2.0
    along = corner.end - corner.start
    along = along / float(np.linalg.norm(along))
    return _Placed(
        middle=(float(middle[0]), float(middle[1]), float(middle[2])),
        direction=(float(along[0]), float(along[1]), float(along[2])),
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
