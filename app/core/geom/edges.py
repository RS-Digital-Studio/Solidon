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

import bisect
import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Integral
from typing import Any, Final, Literal, Protocol, cast

import numpy as np

from app.core import units
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    CORRECT_INPUT,
    REPAIR_AND_RETRY,
    GeometryError,
    ValidationError,
)
from app.core.geom import lathe, transform
from app.core.geom.boolean import BOOLEAN_OVERLAP, BooleanKind, BooleanOutcome, boolean, deepest
from app.core.geom.measure import SHARP_EDGE_ANGLE
from app.core.geom.mesh import MeshData
from app.core.geom.repair import remove_hollow_shells
from app.core.log import get_logger
from app.core.types import CancelToken, Feature, Finding, Mesh, Quality, Vec3, is_a_cavity
from app.core.units import (
    EPS_GEOM,
    MAX_FACET_ANGLE,
    MAX_FACET_SAG,
    is_close,
    is_zero,
    weld_tolerance,
)
from app.i18n import TranslatableText, _

#: Der eine Satz für eine ausdrückliche Kantenauswahl, die es so nicht gibt —
#: am Netz wie im exakten Kern (``brep.kernel.Solid.checked_edge_indices``).
EDGE_SELECTION_REJECTED = _("Wählen Sie die Kante am Körper neu und wiederholen Sie die Änderung.")

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


class DescribedEdge(HasPlacement, Protocol):
    """Was ein Fingerabdruck von einer Kante braucht: die Lage und ihre Länge."""

    @property
    def length(self) -> float: ...


def edge_fingerprint(entry: DescribedEdge) -> dict[str, Any]:
    """Die ungerundete Beschreibung **einer** Kante — der Beleg hinter dem Schlüssel.

    Der Schlüssel (:func:`edge_key`) rundet auf ein Hundertstel, und genau
    deshalb können zwei verschiedene Kanten denselben tragen: die zwei Ränder
    eines Spalts von vier Tausendstel Millimetern. Der Fingerabdruck trägt
    Mitte, Richtung (wie im Schlüssel ohne Vorzeichen), Ausdehnung und Länge
    in voller Genauigkeit. Er unterscheidet, was der Schlüssel zusammenwirft,
    und er geht in den Cache-Schlüssel des Verbrauchers ein, damit zwei
    verschieden bestätigte Kanten zwei verschiedene Ergebnisse sind
    (``scene.edge_binding``, P1.4c). Gespeichert wird er nur in einer
    Kantenantwort, nie als Ersatz für den Schlüssel im Parameter.
    """
    return {
        "middle": [float(value) for value in entry.middle],
        "direction": [float(value) for value in _unsigned_direction(entry.direction)],
        "extent": float(entry.extent),
        "length": float(entry.length),
    }


def same_edge(fingerprint: Mapping[str, Any], entry: DescribedEdge) -> bool:
    """Ob ein gespeicherter Fingerabdruck diese Kante beschreibt — innerhalb ``EPS_GEOM``.

    Zwei Kanten, die sich in keinem der vier Werte um mehr als das
    Rechenepsilon unterscheiden, sind nicht auseinanderzuhalten; eine
    gespeicherte Wahl zwischen ihnen gilt dann nicht, und die Frage wird neu
    gestellt (Regel 21).
    """
    current = edge_fingerprint(entry)
    for name in ("middle", "direction"):
        stored = fingerprint.get(name)
        if not isinstance(stored, list | tuple) or len(stored) != 3:
            return False
        if any(
            not is_close(float(a), float(b)) for a, b in zip(stored, current[name], strict=True)
        ):
            return False
    return all(is_close(float(fingerprint[name]), current[name]) for name in ("extent", "length"))


def checked_indices(
    indices: Sequence[int],
    count: int,
    rejection: TranslatableText = EDGE_SELECTION_REJECTED,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[int, ...]:
    """Eine nichtleere Menge gültiger Indizes in einen Raum von ``count`` Einträgen.

    Sortiert und entdoppelt, ohne Wahrheitswerte und ohne Bruchzahlen: Was
    hier nicht durchkommt, ist keine Auswahl, sondern ein Bedienfehler mit
    Rückweg — derselbe Satz für Netz und exakten Kern.
    """
    selected: set[int] = set()
    for value in cast(Sequence[object], indices):
        if check_cancelled is not None:
            check_cancelled()
        if (
            isinstance(value, bool)
            or not isinstance(value, Integral)
            or not 0 <= int(value) < count
        ):
            raise ValidationError(detail=rejection)
        selected.add(int(value))
    if not selected:
        raise ValidationError(detail=rejection)
    return tuple(sorted(selected))


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
    return _key_from_placement(entry, _placement_key(entry))


def _key_from_placement(entry: HasPlacement, placement: str) -> str:
    """Der Schlüssel aus dem schon gerechneten Lageschlüssel — Ringe tragen ihre Größe."""
    if math.dist(entry.direction, (0.0, 0.0, 0.0)) <= EPS_GEOM:
        return f"{placement}:r:{_unsigned_zero(entry.extent, 2):.2f}"
    return placement


def _placement_key(entry: HasPlacement) -> str:
    """Der bisherige Schlüssel bleibt für eindeutige gespeicherte Auswahlen lesbar."""
    return "e:{:.2f},{:.2f},{:.2f}:{:.3f},{:.3f},{:.3f}".format(
        *(_unsigned_zero(value, 2) for value in entry.middle),
        *(_unsigned_zero(value, 3) for value in _unsigned_direction(entry.direction)),
    )


def _unsigned_direction(direction: Vec3) -> tuple[float, float, float]:
    """Die Richtung ohne Vorzeichen: die erste Komponente ungleich null wird positiv."""
    lead = next((value for value in direction if abs(value) > 1e-6), 1.0)
    sign = -1.0 if lead < 0.0 else 1.0
    return (direction[0] * sign, direction[1] * sign, direction[2] * sign)


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

    **Gemerkt am Netz selbst**, wie ``MeshData.component_count``: Die
    Auswertung löst ein Kantenfeld vor dem Cache am Eingang auf
    (``scene.edge_binding``), und die Operation verkettet dieselben Züge
    gleich darauf ein zweites Mal (``_worked_edges``) — am Lochblech 20 mal 20
    zweimal 201 ms für 812 Züge, an der Kumiko-Platte 729 und 181 ms für
    27 912 (Review, 21.09.2026). Der Cache des Netzes verfällt mit dessen
    Geometrie; ``MeshEdge`` ist eingefroren, die Liste bekommt jeder Aufrufer
    als eigene Kopie.
    """
    raw = mesh.raw
    cache = getattr(raw, "_cache", None)
    key = f"solidon_edges_{float(angle)!r}"
    if cache is not None:
        cache.verify()
        if key in cache:
            return list(cache[key])
    found = _edges_of(raw, angle)
    if cache is not None:
        cache[key] = tuple(found)
    return found


def _edges_of(raw: Any, angle: float) -> list[MeshEdge]:
    """Die Züge eines ``trimesh.Trimesh`` — die Rechnung hinter :func:`edges_of`."""
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

    # **Die Höhe der waagerechten Kanten, nicht aller** (22.09.2026). Eine
    # schräge Kante hat ihre Mitte zwischen ihren Enden: Am Walmdach lagen die
    # Mitten der Grate bei 12,5, die Traufen bei 10, und „oben" suchte
    # waagerechte Kanten auf 12,5 — es gab keine.
    heights = [entry.middle[2] for entry in edges if entry.flat]
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
    described = described_by_key(edges)
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


def described_by_key[AnyEdge: SelectableEdge](
    edges: Sequence[AnyEdge],
) -> dict[str, list[AnyEdge]]:
    """Jede Kante unter ihrem Schlüssel — und unter dem alten Lageschlüssel als Alias.

    Mehr als ein Eintrag je Schlüssel ist eine **Kollision**: zwei Kanten, die
    der gerundete Schlüssel nicht unterscheidet, oder ein alter Rohrschlüssel,
    der beide Ränder trifft. :func:`named_edges` hält dort an; die Auswertung
    fragt den Kunden davor (``scene.edge_binding``), und was er wählt, erreicht
    die Operation als ausdrückliche Auswahl statt als Schlüssel.
    """
    described: dict[str, list[AnyEdge]] = {}
    for entry in edges:
        # Der Lageschlüssel einmal je Kante — ``edge_key`` rechnete ihn ein
        # zweites Mal, und an 812 Zügen war das die Hälfte der Bindung.
        legacy = _placement_key(entry)
        key = _key_from_placement(entry, legacy)
        described.setdefault(key, []).append(entry)
        if legacy != key:
            described.setdefault(legacy, []).append(entry)
    return described


def selected_or_wanted[AnyEdge: SelectableEdge](
    edges: Sequence[AnyEdge],
    choice: EdgeChoice,
    keys: Sequence[str],
    selected_edges: Sequence[int] | None,
) -> list[AnyEdge]:
    """Die Kanten dieses Aufrufs: ausdrücklich gewählte vor Schlüsseln vor Gruppe.

    ``selected_edges`` sind Indizes in ``edges`` — am Netz die Reihenfolge von
    :func:`edges_of`, die für dasselbe Netz dieselbe ist. Eine ausdrückliche
    Auswahl fällt nie auf Schlüssel oder Gruppe zurück (§21.3): Sie ist die
    vom Kunden bestätigte Antwort, und ein Schlüssel danach könnte wieder
    zwei Kanten treffen.
    """
    if selected_edges is None:
        return wanted(edges, choice, keys)
    return [edges[index] for index in checked_indices(selected_edges, len(edges))]


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


@dataclass(frozen=True, slots=True)
class ChamferShape:
    """Wie eine Fase ihre zwei Flächen zurücknimmt, wenn es nicht beide gleich sind (P6.2).

    Die Breite der Operation gilt auf der **Bezugsfläche**; die Gegenfläche
    bekommt ``second`` — oder, mit ``angle``, so viel, dass die Fasenfläche
    unter diesem Winkel zur Bezugsfläche steht. Welche der beiden Flächen einer
    Kante die Bezugsfläche ist, sagt :func:`reference_first`; ``flipped``
    tauscht das. Beide Kerne rechnen mit denselben drei Zeilen
    (:func:`chamfer_reaches`), damit dieselbe Eingabe an einem Netz und an
    einem exakten Körper dieselbe Fase gibt.
    """

    second: float | None = None
    angle: float | None = None
    flipped: bool = False


#: Wie viele gleichmäßig verteilte Stellen der exakte Kern vom Verlauf bekommt.
#:
#: OpenCASCADE nimmt kein eigenes Radiusgesetz an: ``Add(Law_Function, E)``
#: und ``SetRadius(Law_Function, …)`` werfen in ``Build`` (OCCT 8.0.1,
#: ``NCollection_Sequence::First``), ``SetLaw`` setzt den Builder still auf
#: den unveränderten Körper zurück. Was geht, ist eine Liste aus Stelle und
#: Radius, die der Kern mit seiner eigenen Spline verbindet — dicht genug
#: abgetastet, trifft sie diesen Verlauf: gemessen unter 4·10⁻⁶ mm mit 33
#: Stellen und den Nachbarstellen aus :data:`LAW_NEAR` (Sonde ``p6a``,
#: 23.09.2026). Ohne die Nachbarstellen lag der Fehler an den Enden bei
#: 5·10⁻³ mm: Der Kern verlängert den Verlauf für seine Spline über beide
#: Enden hinaus.
LAW_SAMPLES: Final = 33

#: Wie nah an jeder Stelle (auch Anfang und Ende) zusätzlich abgetastet wird,
#: als Anteil der Kantenlänge — dort knickt die zweite Ableitung des Verlaufs.
LAW_NEAR: Final = (1e-4, 1e-3, 1e-2)


@dataclass(frozen=True, slots=True)
class RadiusLaw:
    """Wie sich der Radius einer Verrundung entlang ihrer Kante ändert (P6.1).

    ``positions`` sind Stellen als Anteil der Kantenlänge vom **Anfang** aus,
    aufsteigend von 0 bis 1; ``radii`` die Radien dort. Dazwischen verläuft
    der Radius als monotone kubische Hermite-Kurve (Fritsch-Carlson, wie
    ``scipy``s ``PchipInterpolator``): zwischen zwei Stellen nie über oder
    unter deren Werte, ohne Knick an einer Stelle, und bei nur zwei Stellen
    eine Gerade. Gerechnet wird nur mit Grundrechenarten — dieselbe Zahl auf
    jeder Maschine.

    **Wo der Anfang ist, sagt die Kante und nicht ihre Nummer**
    (:func:`starts_at_first`): das linke Ende, bei gleicher Lage das vordere,
    dann das untere. ``reversed`` tauscht Anfang und Ende. Auf einem Ring
    (:func:`loop_start`) sind Anfang und Ende dieselbe Stelle; ``periodic``
    rechnet die Steigung dort aus beiden Nachbarabschnitten, damit der Verlauf
    auch über diese Stelle ohne Knick läuft.
    """

    positions: tuple[float, ...]
    radii: tuple[float, ...]
    reversed: bool = False
    periodic: bool = False

    def __post_init__(self) -> None:
        if len(self.positions) != len(self.radii) or len(self.positions) < 2:
            raise ValueError("a radius law needs matching positions and radii, at least two")
        if not is_zero(self.positions[0]) or not is_close(self.positions[-1], 1.0):
            raise ValueError("a radius law runs from 0 to 1")
        if any(b - a <= EPS_GEOM for a, b in itertools.pairwise(self.positions)):
            raise ValueError("radius law positions must rise")

    @property
    def constant(self) -> bool:
        """Ob überall derselbe Radius gilt — dann ist es die alte Verrundung."""
        return all(is_close(radius, self.radii[0]) for radius in self.radii)

    @property
    def largest(self) -> float:
        """Der größte Radius; er steht an einer Stelle und nie dazwischen."""
        return max(self.radii)

    @property
    def smallest(self) -> float:
        return min(self.radii)

    def as_loop(self) -> RadiusLaw:
        """Derselbe Verlauf auf einem Ring — mit glatter Steigung an Anfang und Ende."""
        return RadiusLaw(self.positions, self.radii, self.reversed, periodic=True)

    def at(self, t: float) -> float:
        """Der Radius an der Stelle ``t`` (Anteil der Länge vom Anfang)."""
        if self.reversed:
            t = 1.0 - t
        return self._value(min(max(float(t), 0.0), 1.0))

    def along(self, values: np.ndarray) -> np.ndarray:
        """:meth:`at` für ein Feld von Stellen."""
        return np.asarray([self.at(float(value)) for value in np.asarray(values).ravel()])

    def curvature_bound(self) -> float:
        """Die größte zweite Ableitung ``|r''(t)|`` über den ganzen Verlauf.

        Innerhalb eines Abschnitts ist ``r''`` linear; das Größte steht also an
        einem Abschnittsende.
        """
        slopes = self._slopes()
        worst = 0.0
        for index in range(len(self.positions) - 1):
            width = self.positions[index + 1] - self.positions[index]
            rise = (self.radii[index + 1] - self.radii[index]) / width
            first, second = slopes[index], slopes[index + 1]
            worst = max(
                worst,
                abs(6.0 * rise - 4.0 * first - 2.0 * second) / width,
                abs(-6.0 * rise + 2.0 * first + 4.0 * second) / width,
            )
        return worst

    def stations(self) -> tuple[float, ...]:
        """Die Stellen in der Richtung, in der :meth:`at` sie liest."""
        if self.reversed:
            return tuple(sorted(1.0 - value for value in self.positions))
        return self.positions

    def _slopes(self) -> list[float]:
        """Die Steigungen an den Stellen — Fritsch-Carlson mit scipys Randformel."""
        x, y = self.positions, self.radii
        count = len(x)
        widths = [x[index + 1] - x[index] for index in range(count - 1)]
        rises = [(y[index + 1] - y[index]) / widths[index] for index in range(count - 1)]
        if count == 2:
            return [rises[0], rises[0]]
        slopes = [0.0] * count
        for index in range(1, count - 1):
            before, after = rises[index - 1], rises[index]
            if before * after <= 0.0:
                continue
            left = 2.0 * widths[index] + widths[index - 1]
            right = widths[index] + 2.0 * widths[index - 1]
            slopes[index] = (left + right) / (left / before + right / after)
        if self.periodic:
            # Anfang und Ende sind dieselbe Stelle: dieselbe Regel wie innen,
            # mit dem letzten Abschnitt davor und dem ersten danach.
            before, after = rises[-1], rises[0]
            seam = 0.0
            if before * after > 0.0:
                left = 2.0 * widths[0] + widths[-1]
                right = widths[0] + 2.0 * widths[-1]
                seam = (left + right) / (left / before + right / after)
            slopes[0] = slopes[-1] = seam
            return slopes
        slopes[0] = _edge_slope(widths[0], widths[1], rises[0], rises[1])
        slopes[-1] = _edge_slope(widths[-1], widths[-2], rises[-1], rises[-2])
        return slopes

    def _value(self, t: float) -> float:
        x, y = self.positions, self.radii
        index = max(0, min(len(x) - 2, bisect.bisect_right(x, t) - 1))
        width = x[index + 1] - x[index]
        slopes = self._slopes()
        u = (t - x[index]) / width
        u2, u3 = u * u, u * u * u
        return (
            (2.0 * u3 - 3.0 * u2 + 1.0) * y[index]
            + (u3 - 2.0 * u2 + u) * width * slopes[index]
            + (-2.0 * u3 + 3.0 * u2) * y[index + 1]
            + (u3 - u2) * width * slopes[index + 1]
        )


def _edge_slope(width: float, beside: float, rise: float, next_rise: float) -> float:
    """Die Steigung am Rand: Dreipunktformel, auf Monotonie zurückgenommen (wie scipy)."""
    slope = ((2.0 * width + beside) * rise - width * next_rise) / (width + beside)
    if math.copysign(1.0, slope) != math.copysign(1.0, rise) or rise == 0.0:
        return 0.0
    if math.copysign(1.0, rise) != math.copysign(1.0, next_rise) and abs(slope) > abs(3.0 * rise):
        return 3.0 * rise
    return slope


def starts_at_first(first: Sequence[float], last: Sequence[float]) -> bool:
    """Ob ``first`` der **Anfang** einer offenen Kante ist, die bei ``last`` endet.

    Dieselbe Regel wie die Richtung im Kantenschlüssel (:func:`edge_key`): Die
    Richtung vom Anfang zum Ende zeigt in ihrer ersten Komponente, die auf drei
    Stellen nicht null ist, ins Positive. Am Teil heißt das: der Anfang liegt
    links, bei gleicher Lage vorn, dann unten. Beide Kerne fragen hier, damit
    „Radius am Anfang" am Netz und am exakten Körper dieselbe Stelle meint.
    """
    span = np.asarray(last, dtype=float) - np.asarray(first, dtype=float)
    reach = float(np.linalg.norm(span))
    if reach <= EPS_GEOM:
        return True
    for value in span / reach:
        rounded = _unsigned_zero(float(value), 3)
        if rounded:
            return rounded > 0.0
    return True


#: In welcher Richtung ein **Ring** anfängt: an seinem Punkt, der in dieser
#: Richtung am weitesten zurückliegt — links, bei gleicher Lage vorn, dann
#: unten; die kleinen Anteile entscheiden nur einen Gleichstand, etwa an der
#: geraden linken Seite eines gerundeten Rechtecks (dort das vordere Ende).
LOOP_START: Final = (1.0, 1e-3, 1e-6)

#: Und wohin er von dort läuft: in die Richtung, die in dieser Achse ins
#: Positive zeigt — nach hinten, bei einem stehenden Ring nach oben. Am
#: Anfangspunkt steht die Tangente quer zu :data:`LOOP_START`; ihr Anteil
#: dort ist kein verlässliches Vorzeichen, dieser schon.
LOOP_WAY: Final = (0.0, 1.0, 1e-3)


def points_forward(direction: Sequence[float]) -> bool:
    """Ob ein Ring in dieser Tangentenrichtung von seinem Anfang weg läuft (:data:`LOOP_WAY`)."""
    return float(np.dot(np.asarray(direction, dtype=float), LOOP_WAY)) > 0.0


def loop_start(points: np.ndarray) -> tuple[float, bool]:
    """Wo ein geschlossener Punktzug anfängt (Bogenlänge ab ``points[0]``) und ob er vorwärts läuft.

    Der Punkt kleinster Lage in :data:`LOOP_START`: am Zug die Ecke mit dem
    kleinsten Wert, dann mit einer Parabel durch sie und ihre Nachbarn
    verfeinert — zwischen zwei Ecken eines Sehnenzugs liegt der Punkt, den
    der exakte Kern an seiner Kurve findet (``brep.edit``). Vorwärts heißt
    :func:`points_forward` für die Richtung wachsender Bogenlänge.
    """
    ring = np.asarray(points, dtype=float)
    if float(np.linalg.norm(ring[0] - ring[-1])) <= EPS_GEOM:
        ring = ring[:-1]
    count = len(ring)
    steps = np.linalg.norm(np.roll(ring, -1, axis=0) - ring, axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(steps)))
    total = float(cumulative[-1])
    weight = np.asarray(LOOP_START, dtype=float)
    values = ring @ (weight / float(np.linalg.norm(weight)))
    corner = int(np.argmin(values))
    before, after = float(steps[corner - 1]), float(steps[corner])
    low, here, high = values[corner - 1], values[corner], values[(corner + 1) % count]
    offset = 0.0
    # **Verfeinert wird nur zwischen ähnlich langen Sehnen** — dem Sehnenzug
    # eines Bogens. Am Übergang von einer Geraden in einen Bogen (die linke
    # Seite eines gerundeten Rechtecks) liegt der Anfang auf der Ecke; eine
    # Parabel über die lange Seite hinweg schob ihn gemessen 10 mm hinein.
    even = max(before, after) <= 2.0 * min(before, after)
    if even and before > EPS_GEOM and after > EPS_GEOM:
        bend = ((low - here) / before + (high - here) / after) / (before + after)
        if bend > 0.0:
            slope = (high - here) / after - bend * after
            offset = min(max(-slope / (2.0 * bend), -before), after)
    start = (float(cumulative[corner]) + offset) % total
    segment = int(np.searchsorted(cumulative, start, side="right") - 1) % count
    onward = ring[(segment + 1) % count] - ring[segment]
    return start, points_forward(onward)


@dataclass(frozen=True, slots=True)
class LawOnChain:
    """Ein Radiusverlauf auf einem bestimmten Zug: Bogenlänge ``s`` zu Stelle und Radius.

    Offene Züge beginnen an ihrem Anfang (:func:`starts_at_first`), Ringe an
    :func:`loop_start`; ``start`` ist die Bogenlänge dieses Anfangs ab dem
    ersten Punkt des Zugs, ``forward``, ob die Stelle mit wachsender
    Bogenlänge wächst. Netz und exakter Kern stellen dieselbe Frage — der eine
    am Punktzug, der andere an der Kontur aus Kurven.
    """

    law: RadiusLaw
    total: float
    start: float
    forward: bool
    closed: bool

    def share(self, distance: float) -> float:
        """Die Stelle im Verlauf (0 … 1) zur Bogenlänge ``distance``."""
        if self.total <= EPS_GEOM:
            return 0.0
        if self.closed:
            offset = distance - self.start if self.forward else self.start - distance
            return (offset / self.total) % 1.0
        share = min(max(distance / self.total, 0.0), 1.0)
        return share if self.forward else 1.0 - share

    def radius(self, distance: float) -> float:
        return self.law.at(self.share(distance))

    def places(self) -> list[float]:
        """Die Bogenlängen der Stellen des Verlaufs — auf einem Ring auch sein Anfang."""
        found: list[float] = []
        for station in self.law.stations():
            along = station * self.total
            if self.closed:
                spot = self.start + along if self.forward else self.start - along
                found.append(spot % self.total)
            else:
                found.append(along if self.forward else self.total - along)
        return sorted(set(found))


def samples_along(on_chain: LawOnChain, low: float, high: float) -> list[tuple[float, float]]:
    """Stelle und Radius für das Stück ``low`` … ``high`` (Bogenlänge) eines Zugs, von 0 bis 1.

    Für den exakten Kern: OpenCASCADE nimmt kein eigenes Radiusgesetz an, und
    ``SetRadius(UandR, IC, IinC)`` gilt einer Kante der Kontur. Abgetastet wird
    gleichmäßig (:data:`LAW_SAMPLES`) und verdichtet an den Enden des Stücks und
    um jede Stelle des Verlaufs, die hineinfällt (:data:`LAW_NEAR`, als Anteil
    der ganzen Länge): Der Kern verlängert jede Tabelle für seine Spline über
    ihre Enden hinaus und traf ohne die Verdichtung dort um 5·10⁻³ mm daneben.
    Gemessen an einer Kette Gerade-Bogen-Gerade weicht sein Gesetz mit ihr
    höchstens 5·10⁻⁸ mm von diesem ab.
    """
    width = high - low
    if width <= EPS_GEOM:
        return [(0.0, on_chain.radius(low)), (1.0, on_chain.radius(high))]
    wanted = {index / (LAW_SAMPLES - 1) for index in range(LAW_SAMPLES)}
    wanted.update(value for near in LAW_NEAR for value in (near, 1.0 - near))
    for place in on_chain.places():
        if low - EPS_GEOM <= place <= high + EPS_GEOM:
            local = (place - low) / width
            wanted.add(local)
            for near in LAW_NEAR:
                step = near * on_chain.total / width
                wanted.update((local - step, local + step))
    ordered = sorted(value for value in wanted if 0.0 <= value <= 1.0)
    kept = [0.0]
    for value in ordered:
        if value - kept[-1] > EPS_GEOM:
            kept.append(value)
    kept[-1] = 1.0
    return [(value, on_chain.radius(low + value * width)) for value in kept]


def law_on_points(points: Sequence[Sequence[float]] | np.ndarray, law: RadiusLaw) -> LawOnChain:
    """Der Verlauf auf einem Punktzug — offen oder geschlossen, wie am Netz."""
    ring = np.asarray(points, dtype=float)
    steps = np.linalg.norm(np.diff(ring, axis=0), axis=1)
    total = float(steps.sum())
    closed = len(ring) > 2 and float(np.linalg.norm(ring[0] - ring[-1])) <= EPS_GEOM
    if closed:
        start, forward = loop_start(ring)
        return LawOnChain(law.as_loop(), total, start, forward, True)
    return LawOnChain(law, total, 0.0, starts_at_first(ring[0], ring[-1]), False)


def law_at_ends(points: Sequence[Sequence[float]], law: RadiusLaw) -> tuple[float, float]:
    """Der Radius am ersten und am letzten Punkt eines Zugs — nach der Regel für den Anfang.

    Auf einem Ring sind beide derselbe Punkt; geliefert werden dann Anfangs-
    und Endradius des Verlaufs, und :func:`check_varying_radius` verlangt,
    dass sie gleich sind.
    """
    if len(points) > 2 and math.dist(points[0], points[-1]) <= EPS_GEOM:
        return law.at(0.0), law.at(1.0)
    forward = starts_at_first(points[0], points[-1])
    return (law.at(0.0), law.at(1.0)) if forward else (law.at(1.0), law.at(0.0))


def check_varying_radius(
    ends: Sequence[tuple[Any, Any, tuple[float, float]]], *, mixed_corner: bool
) -> None:
    """Hält an, wo ein veränderlicher Radius keine eindeutige Form hat — an beiden Kernen gleich.

    ``ends`` nennt je gewählter Kante ihre zwei Endknoten (eine Kennung, die
    an einer gemeinsamen Ecke gleich ist) und die Radien dort. Drei Fälle
    haben keine Antwort, und jeder bekommt seinen Satz mit Weg (Regel 17):

    * **Auf einem Ring sind Anfang und Ende dieselbe Stelle** — beide Enden
      sind derselbe Knoten. Der Anfang selbst ist über die Lage bestimmt
      (:func:`loop_start`); verschiedene Radien an Anfang und Ende hätten dort
      einen Sprung.
    * **Zwei gewählte Kanten mit verschiedenen Radien an einer Ecke**: Die
      Eckkugel hätte zwei Radien zugleich.
    * **Eine Ecke aus Außen- und Innenkante**: Ihr örtlicher Ersatz ist für
      ein Maß gebaut (:func:`_mixed_corner_region`).
    """
    radii_at: dict[Any, list[float]] = {}
    for first, last, (radius_first, radius_last) in ends:
        if first == last:
            if abs(radius_first - radius_last) > EPS_GEOM:
                raise GeometryError(
                    detail=_(
                        "Diese Kante läuft ringsum: Anfang und Ende sind dieselbe Stelle, links "
                        "vorn am Ring. Geben Sie beiden denselben Radius, und legen Sie den "
                        "Verlauf über Zwischenstellen."
                    ),
                    suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
                    values={
                        "radius_mm": round(radius_first, 3),
                        "largest_mm": round(radius_last, 3),
                    },
                )
            continue
        radii_at.setdefault(first, []).append(radius_first)
        radii_at.setdefault(last, []).append(radius_last)
    if mixed_corner:
        raise GeometryError(
            detail=_(
                "Ein veränderlicher Radius geht nicht an einer Ecke, an der eine Außen- und "
                "eine Innenkante zusammentreffen. Wählen Sie einen gleichbleibenden Radius, "
                "oder lassen Sie eine dieser Kanten aus."
            ),
            suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
        )
    for radii in radii_at.values():
        if len(radii) > 1 and max(radii) - min(radii) > EPS_GEOM:
            raise GeometryError(
                detail=_(
                    "An einer Ecke treffen gewählte Kanten mit verschiedenen Radien zusammen. "
                    "Geben Sie ihnen dort denselben Radius, oder verrunden Sie sie einzeln."
                ),
                suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
                values={"radius_mm": round(min(radii), 3), "largest_mm": round(max(radii), 3)},
            )


def reference_first(one: Sequence[float], two: Sequence[float]) -> bool:
    """Ob die Fläche mit der Normale ``one`` die Bezugsfläche ist — gegen ``two``.

    Die Regel ist eine, die man am Teil sieht: die Fläche, die am weitesten
    nach **oben** zeigt; bei gleicher Höhe die, die weiter nach **hinten**
    zeigt, dann die weiter **rechts**. An einer oberen Kante ist das die
    Oberseite, an einer senkrechten Kante vorn rechts die rechte Seite.
    """
    for axis in (2, 1, 0):
        gap = float(one[axis]) - float(two[axis])
        if abs(gap) > 1e-6:
            return gap > 0.0
    return True


def chamfer_reaches(
    distance: float,
    shape: ChamferShape | None,
    one: Sequence[float],
    two: Sequence[float],
) -> tuple[float, float]:
    """Wie weit die Fase auf der Fläche ``one`` und auf der Fläche ``two`` zurücknimmt.

    Ohne ``shape`` beide gleich — die Bedeutung aller bisherigen Fasen. Mit
    Winkel folgt die zweite Rücknahme aus dem Sinussatz im Dreieck aus Kante
    und den beiden Berührlinien: ``b = a · sin(w) / sin(t + w)``, mit dem
    Fasenwinkel ``w`` und dem Winkel ``t`` zwischen den beiden Flächen quer zur
    Kante (bei einem Quader 90°, dann ``b = a · tan(w)``). Trifft die
    Fasenfläche die Gegenfläche nicht mehr (``t + w`` ab 180°), ist das eine
    Absage mit dem größten Winkel.
    """
    if shape is None or (shape.second is None and shape.angle is None):
        return distance, distance
    reference_is_one = reference_first(one, two) != shape.flipped
    if shape.angle is not None:
        cosine = -float(np.clip(np.dot(np.asarray(one, float), np.asarray(two, float)), -1.0, 1.0))
        between = math.degrees(math.acos(float(np.clip(cosine, -1.0, 1.0))))
        if between + shape.angle >= 180.0 - 1e-6:
            raise ValidationError(
                "angle",
                _(
                    "Unter diesem Winkel trifft die Fase die zweite Fläche nicht. "
                    "Wählen Sie einen Winkel unter {largest:.1f} Grad.",
                    largest=180.0 - between,
                ),
                value=shape.angle,
                constraint="chamfer_angle",
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        other = (
            distance
            * units.exact_sin_degrees(shape.angle)
            / units.exact_sin_degrees(between + shape.angle)
        )
    else:
        other = float(cast(float, shape.second))
    return (distance, other) if reference_is_one else (other, distance)


@dataclass(frozen=True, slots=True)
class EdgeSide:
    """Eine der zwei Flächen an einer Kante, gefragt an einer Stelle der Kante.

    ``normal`` zeigt aus dem Körper heraus; ``towards`` liegt in der Fläche,
    quer zur Kante, und zeigt von ihr weg in die Fläche hinein — dorthin, wo
    eine Fase die Fläche zurücknimmt.
    """

    normal: Vec3
    towards: Vec3


@dataclass(frozen=True, slots=True)
class EdgeSides:
    """Die beiden Flächen einer Kante an einem Punkt **auf** ihr (P6.2).

    Die Reihenfolge ``one``/``two`` ist die, in der der Kern der Kante die
    Flächen fragt; :func:`chamfer_reaches` bekommt die Normalen in derselben
    Folge. Deshalb sagt diese Auskunft, welche Fläche welche Rücknahme
    bekommt, ohne die Wahl der Bezugsfläche ein zweites Mal zu treffen.
    """

    at: Vec3
    one: EdgeSide
    two: EdgeSide


def mesh_edge_sides(entry: MeshEdge) -> EdgeSides | None:
    """Die zwei Flächen eines Netzzugs an seiner halben Länge — oder ``None``.

    Gefragt wird das Stück, auf dem die halbe Länge liegt, mit seinen eigenen
    Normalen: Das Netz fast jedes Stück mit dessen Normalen
    (:func:`_wedge`), und an einem Bogen drehen sie sich mit. Die Richtungen
    in die Flächen sind dieselben wie beim Werkzeug (:func:`_along_face`).
    """
    if len(entry.points) < 2 or len(entry.normals) != len(entry.points) - 1:
        return None
    points = np.asarray(entry.points, dtype=float)
    steps = np.linalg.norm(np.diff(points, axis=0), axis=1)
    total = float(steps.sum())
    if total <= EPS_GEOM:
        return None
    walked = 0.0
    index = len(steps) - 1
    for position, step in enumerate(steps):
        if walked + float(step) >= total / 2.0:
            index = position
            break
        walked += float(step)
    step = float(steps[index])
    if step <= EPS_GEOM:
        return None
    along = (points[index + 1] - points[index]) / step
    at = points[index] + along * min(max(total / 2.0 - walked, 0.0), step)
    one = np.asarray(entry.normals[index][0], dtype=float)
    two = np.asarray(entry.normals[index][1], dtype=float)
    into = -(one + two) if entry.convex else one + two
    if float(np.linalg.norm(into)) <= EPS_GEOM:
        return None
    towards_one = _along_face(one, along, into)
    towards_two = _along_face(two, along, into)
    if towards_one is None or towards_two is None:
        return None
    return EdgeSides(
        at=_vec(at),
        one=EdgeSide(normal=_vec(one), towards=_vec(towards_one)),
        two=EdgeSide(normal=_vec(two), towards=_vec(towards_two)),
    )


def _vec(values: np.ndarray) -> Vec3:
    """Ein NumPy-Vektor als Raumpunkt des Kerns."""
    return (float(values[0]), float(values[1]), float(values[2]))


def rounding_tool(
    entry: MeshEdge,
    radius: float,
    rounded: bool = True,
    *,
    min_steps: int = 0,
    extend_ends: bool = True,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    shape: ChamferShape | None = None,
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
    subtracted = entry.convex and extend_ends
    # **Ein abziehender Keil steht mit seinen Kontaktflanken in der Luft, nicht
    # in der Körperfläche.** Mit ``flank_overlap=0.0`` lag die Flanke exakt
    # auf der Fläche, die sie abträgt — koplanar, und ``manifold3d`` rechnet
    # das in float64 sauber. Kommt der Körper aber aus einer STL (float32),
    # sind Fläche und Flanke nur fast koplanar, und die Differenz ließ an den
    # Bohrungsrändern einer gefasten Platte ~36 mm² Haut ohne Dicke stehen:
    # per Index dicht, nach der nächsten STL-Runde nicht mehr (RM-166,
    # 13.09.2026). Um ``BOOLEAN_OVERLAP`` nach außen gerückt bleibt die
    # Schnittkurve dieselbe, nur die Flanken schneiden Luft. ``EPS_GEOM`` war
    # dafür zu wenig — 499 Eckpunktpaare unter der Schweißtoleranz.
    flank_overlap = BOOLEAN_OVERLAP if subtracted else (0.0 if extend_ends else EPS_GEOM)
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
            subtracted=subtracted,
            min_steps=min_steps,
            flank_overlap=flank_overlap,
            shape=shape,
        )
        if wedge is not None:
            pieces.append(wedge)
    if not pieces:
        raise _without_an_angle(radius)
    if len(pieces) == 1:
        return pieces[0]
    # **In einem Zug und nicht paarweise.** Der erste Anlauf faltete die Stücke
    # nacheinander zusammen; bei einem geschlossenen Rundgang — der Oberkante
    # einer schon verrundeten Platte, achtundzwanzig Stücke — blieben dabei zwei
    # Häute ohne Dicke stehen. Der Körper war danach wasserdicht und trug sein
    # richtiges Volumen, aber ``body_count`` zählte drei Teile, und der
    # Prüfbericht meldet so etwas dem Kunden als Zerfall.
    return boolean("union", pieces, quality=quality, cancelled=cancelled).mesh


def _without_an_angle(radius: float) -> GeometryError:
    """Der Satz für einen Zug, an dem keine zwei Flächen unter einem Winkel stoßen.

    **Und der Satz spricht nicht vom Maß.** Bis zum 13.09.2026 stand hier
    „Das Maß ist für diese Kante zu groß — wählen Sie ein kleineres", und das
    war in jedem Fall falsch, in dem er erschien: :func:`_wedge` scheitert am
    **Winkel** zwischen den zwei Flächen und nie an ``radius``. Gemessen am
    ``generated_figure`` des Korpus bekam derselbe Körper denselben Satz bei
    R = 0,001 wie bei R = 2,0. Ein kleinerer Radius versucht dasselbe noch
    einmal, und Regel 17 verlangt eine Handlung, die weiterführt.
    """
    return GeometryError(
        detail=_(
            "An dieser Kante stoßen keine zwei Flächen unter einem Winkel "
            "zusammen — das Netz ist dort gefaltet oder eben. Reparieren Sie "
            "das Modell, oder wählen Sie eine andere Kante."
        ),
        suggestions=(REPAIR_AND_RETRY, CHANGE_SELECTION, CANCEL),
        values={"radius": radius},
    )


def workable(entry: MeshEdge) -> bool:
    """Ob an diesem Zug überhaupt ein Werkzeug entsteht — unabhängig vom Maß.

    Dieselben Bedingungen, an denen :func:`_wedge` ein Stück verwirft: ein
    Stück ohne Länge, zwei entgegengesetzte Normalen (eine Wand ohne Dicke,
    zwei Hälften Wand an Wand) oder ein Winkel, der keine Kante ist. Trägt kein
    Stück, gibt es an diesem Zug nichts zu runden oder zu fasen — gleich mit
    welchem Maß.
    """
    if not entry.normals:
        return False
    points = np.asarray(entry.points, dtype=float)
    for index, (first, second) in enumerate(entry.normals):
        along = points[index + 1] - points[index]
        reach = float(np.linalg.norm(along))
        if reach <= EPS_GEOM:
            continue
        along = along / reach
        one = np.asarray(first, dtype=float)
        two = np.asarray(second, dtype=float)
        into = (one + two) if not entry.convex else -(one + two)
        weight = float(np.linalg.norm(into))
        if weight <= EPS_GEOM:
            continue
        half = (math.pi - math.acos(float(np.clip(np.dot(one, two), -1.0, 1.0)))) / 2.0
        if half <= EPS_GEOM or half >= math.pi / 2.0 - EPS_GEOM:
            continue
        into = into / weight
        if _along_face(one, along, into) is None or _along_face(two, along, into) is None:
            continue
        return True
    return False


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
    shape: ChamferShape | None = None,
) -> MeshData | None:
    """Ein Stück des Werkzeugs — das Prisma über einem Querschnitt.

    ``convex`` sagt, auf welcher Seite der Kante der Zwickel liegt;
    ``subtracted``, ob er vom Körper abgezogen wird. Beim Verrunden ist das
    dasselbe, beim Wegnehmen einer Rundung nicht. ``shape`` gibt einer Fase
    zwei verschiedene Rücknahmen (:func:`chamfer_reaches`).
    """
    along = end - start
    reach = float(np.linalg.norm(along))
    if reach <= EPS_GEOM:
        return None
    along = along / reach
    section = _wedge_section(
        start,
        along,
        first,
        second,
        radius,
        convex,
        rounded,
        min_steps=min_steps,
        flank_overlap=flank_overlap,
        shape=shape,
    )
    if section is None:
        return None
    profile, towards_one = section

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


def _wedge_section(
    start: np.ndarray,
    along: np.ndarray,
    first: Vec3,
    second: Vec3,
    radius: float,
    convex: bool,
    rounded: bool,
    *,
    min_steps: int = 0,
    flank_overlap: float = 0.0,
    shape: ChamferShape | None = None,
    steps: int | None = None,
) -> tuple[list[np.ndarray], np.ndarray] | None:
    """Der Querschnitt des Werkzeugs an ``start``: seine Punkte und die erste Flächenrichtung.

    Dieselben Zeilen für das Prisma eines festen Radius (:func:`_wedge`) und
    für jeden Querschnitt eines veränderlichen (:func:`_varying_tool`);
    ``steps`` setzt die Zahl der Sehnen fest, damit alle Querschnitte eines
    Stücks gleich viele Punkte tragen.
    """
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
    tangents = (tangent, tangent) if rounded else chamfer_reaches(radius, shape, first, second)
    # Die Richtungen entlang der beiden Flächen, weg von der Kante.
    towards_one = _along_face(one, along, into)
    towards_two = _along_face(two, along, into)
    if towards_one is None or towards_two is None:
        return None

    first_touch = start + tangents[0] * towards_one
    second_touch = start + tangents[1] * towards_two
    bow: list[np.ndarray] = []
    if rounded:
        centre = start + radius / units.exact_sin(half) * into
        bow = _arc(centre, first_touch, second_touch, radius, min_steps=min_steps, steps=steps)
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
    return profile, towards_one


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
    transform.moved(body, frame)
    return MeshData(body)


def _along_face(normal: np.ndarray, along: np.ndarray, inward: np.ndarray) -> np.ndarray | None:
    """Die Richtung in dieser Fläche, quer zur Kante und in den Zwickel."""
    direction = np.cross(normal, along)
    reach = float(np.linalg.norm(direction))
    if reach <= EPS_GEOM:
        return None
    direction = direction / reach
    return direction if float(np.dot(direction, inward)) > 0.0 else -direction


def _arc_steps(radius: float, span: float, sag: float = MAX_FACET_SAG) -> int:
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
    if radius <= sag:
        # Kleiner als die erlaubte Abweichung: Dann sagt sie nichts mehr, und
        # es bleibt bei der Winkelgrenze.
        turn = MAX_FACET_ANGLE
    else:
        turn = min(2.0 * math.acos(1.0 - sag / radius), MAX_FACET_ANGLE)
    return max(MIN_ARC_STEPS, math.ceil(span / turn))


#: Welcher Anteil der Sehnengrenze bei einem gekrümmten Radiusverlauf der
#: Länge nach verbraucht werden darf. Zwischen zwei Querschnitten verbindet
#: das Werkzeug gerade; wo der Radius sich gekrümmt ändert, weicht diese
#: Gerade von der Rundung ab. Der Rest der Grenze bleibt dem Sehnenzug im
#: Querschnitt — zusammen hält es :data:`MAX_FACET_SAG` (P6.1).
LENGTHWISE_SAG_SHARE: Final = 0.1


def _chain_positions(entry: MeshEdge) -> tuple[np.ndarray, float]:
    """Bogenlänge an jedem Punkt des Zugs und seine Länge."""
    points = np.asarray(entry.points, dtype=float)
    steps = np.linalg.norm(np.diff(points, axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(steps)))
    return cumulative, float(cumulative[-1])


def _varying_tool(
    entry: MeshEdge,
    law: RadiusLaw,
    *,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
) -> MeshData:
    """Das Werkzeug einer Rundung mit veränderlichem Radius — Querschnitte, gerade verbunden.

    Je Stück des Zugs entsteht ein Loft: Querschnitte wie bei :func:`_wedge`,
    jeder mit dem Radius seiner Stelle, an beiden Enden, an jeder Stelle des
    Verlaufs, die in das Stück fällt, und so dicht dazwischen, dass die gerade
    Verbindung höchstens :data:`LENGTHWISE_SAG_SHARE` der Sehnengrenze von der
    Rundung abweicht. Alle Querschnitte eines Stücks tragen gleich viele
    Sehnen — so viele, wie der größte Radius des Stücks braucht. Bei einem
    geraden Verlauf an einer geraden Kante liegt die Verbindung genau auf der
    Rundungsfläche (einem Kegel), und der Sehnenzug hat die ganze Grenze.
    """
    points = np.asarray(entry.points, dtype=float)
    cumulative, total = _chain_positions(entry)
    on_chain = law_on_points(points, law)
    radius_at = on_chain.radius
    stations = on_chain.places()
    bend = on_chain.law.curvature_bound() / max(total * total, EPS_GEOM)
    curved = bend > EPS_GEOM
    chord_sag = MAX_FACET_SAG * (1.0 - LENGTHWISE_SAG_SHARE) if curved else MAX_FACET_SAG
    subtracted = entry.convex
    flank_overlap = BOOLEAN_OVERLAP if subtracted else 0.0
    pieces: list[MeshData] = []
    for index, (first, second) in enumerate(entry.normals):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        start, end = points[index], points[index + 1]
        reach = float(np.linalg.norm(end - start))
        if reach <= EPS_GEOM:
            continue
        along = (end - start) / reach
        low, high = float(cumulative[index]), float(cumulative[index + 1])
        places = {low, high}
        places.update(value for value in stations if low < value < high)
        one, two = np.asarray(first, dtype=float), np.asarray(second, dtype=float)
        half = (math.pi - math.acos(float(np.clip(np.dot(one, two), -1.0, 1.0)))) / 2.0
        if curved and EPS_GEOM < half < math.pi / 2.0 - EPS_GEOM:
            # Wie weit ein Querschnittspunkt je Millimeter Radius wandert:
            # höchstens um den Mittelpunktsabstand und einen Radius dazu.
            leverage = 1.0 / units.exact_sin(half) + 1.0
            spacing = math.sqrt(8.0 * MAX_FACET_SAG * LENGTHWISE_SAG_SHARE / (leverage * bend))
            count = max(1, math.ceil((high - low) / spacing))
            places.update(low + (high - low) * step / count for step in range(1, count))
        ordered = sorted(places)
        radii = [radius_at(value) for value in ordered]
        steps = _arc_steps(max(radii), math.pi - 2.0 * half, chord_sag) if half > 0 else 1
        sections: list[list[np.ndarray]] = []
        for place, radius in zip(ordered, radii, strict=True):
            section = _wedge_section(
                start + (place - low) * along,
                along,
                first,
                second,
                radius,
                entry.convex,
                True,
                flank_overlap=flank_overlap,
                steps=steps,
            )
            if section is None:
                sections = []
                break
            sections.append(section[0])
        if len(sections) < 2:
            continue
        piece = _loft(sections, along, EDGE_OVERSHOOT if subtracted else 0.0)
        if piece is not None:
            pieces.append(piece)
    if not pieces:
        raise _without_an_angle(law.largest)
    if len(pieces) == 1:
        return pieces[0]
    return boolean("union", pieces, quality=quality, cancelled=cancelled).mesh


def _loft(sections: list[list[np.ndarray]], along: np.ndarray, overshoot: float) -> MeshData | None:
    """Ein geschlossener Körper durch gleich lange Querschnitte, der Reihe nach gerade verbunden.

    Die Enden sind Fächer vom ersten Punkt jedes Querschnitts aus — das ist
    die Kante (oder ihr Versatz nach außen), und von dort sieht man jeden
    Punkt des Zwickels. ``overshoot`` setzt vor und hinter die Endquerschnitte
    je eine Kopie entlang der Kante, wie beim Prisma (:data:`EDGE_OVERSHOOT`).

    **Eine Kopie und kein verschobener Endquerschnitt.** Wer den ersten
    Querschnitt um den Überstand nach außen schob, streckte den Verlauf um
    zwei Hundertstel über die ganze Kante: 116,2356 statt 116,2423 mm³ an
    einer Rundung von 2 auf 5 mm über 40 mm — der Radius stand an keiner Stelle
    mehr dort, wo er hingehört.
    """
    import trimesh

    rings = [np.asarray(section, dtype=float) for section in sections]
    if overshoot > 0.0:
        rings = [rings[0] - overshoot * along, *rings, rings[-1] + overshoot * along]
    count = len(rings[0])
    vertices = np.vstack(rings)
    faces: list[tuple[int, int, int]] = []
    for ring in range(len(rings) - 1):
        here, there = ring * count, (ring + 1) * count
        for corner in range(count):
            following = (corner + 1) % count
            faces.append((here + corner, here + following, there + following))
            faces.append((here + corner, there + following, there + corner))
    last = (len(rings) - 1) * count
    for corner in range(1, count - 1):
        faces.append((0, corner + 1, corner))
        faces.append((last, last + corner, last + corner + 1))
    body = trimesh.Trimesh(
        vertices=vertices, faces=np.asarray(faces, dtype=np.int64), process=False
    )
    if body.volume < 0.0:
        body.invert()
    if body.volume <= EPS_GEOM:
        return None
    return MeshData(body)


def _arc(
    centre: np.ndarray,
    first: np.ndarray,
    second: np.ndarray,
    radius: float,
    *,
    min_steps: int = 0,
    steps: int | None = None,
) -> list[np.ndarray]:
    """Die Zwischenpunkte des Rundungsbogens von einem Berührpunkt zum anderen.

    ``steps`` setzt die Zahl der Sehnen fest, statt sie aus dem Radius zu
    rechnen — die Querschnitte eines veränderlichen Radius tragen so alle
    gleich viele Punkte.
    """
    one = (first - centre) / radius
    two = (second - centre) / radius
    span = math.acos(float(np.clip(np.dot(one, two), -1.0, 1.0)))
    axis = np.cross(one, two)
    length = float(np.linalg.norm(axis))
    if length <= EPS_GEOM:
        return []
    axis = axis / length
    if steps is None:
        steps = max(_arc_steps(radius, span), min_steps)
    points = []
    for step in range(1, steps):
        angle = span * step / steps
        turned = (
            one * units.exact_cos(angle)
            + np.cross(axis, one) * units.exact_sin(angle)
            + axis * float(np.dot(axis, one)) * (1.0 - units.exact_cos(angle))
        )
        points.append(centre + radius * turned)
    return points


def round_edges(
    mesh: MeshData,
    radius: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
    *,
    selected_edges: Sequence[int] | None = None,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    narrowest: float = MAX_FACET_SAG,
    law: RadiusLaw | None = None,
) -> BooleanOutcome:
    """Verrundet die gewählten Kanten eines Netzes — dieselbe Handlung wie
    ``brep.edit.fillet``, an einem Körper, der keine Topologie hat.

    Der Bogen ist ein Sehnenzug und keine Kurve; das ist der Unterschied zum
    exakten Kern und der Grund, aus dem es ihn weiter gibt. Wie fein, sagt
    :func:`_arc_steps` — die Zusage lautet, dass keine Sehne weiter als
    :data:`~app.core.units.MAX_FACET_SAG` von der Rundung abweicht, also
    genauso weit wie die Flächen, die der exakte Kern ausgibt.

    ``law`` gibt jedem gewählten Zug einen veränderlichen Radius (P6.1,
    :class:`RadiusLaw`); ``radius`` ist dann sein größter Wert. Ein Verlauf,
    der überall gleich ist, ist die gewöhnliche Verrundung.
    """
    varying = law if law is not None and not law.constant else None
    return _worked_edges(
        mesh,
        law.largest if law is not None else radius,
        choice,
        keys,
        selected_edges=selected_edges,
        rounded=True,
        quality=quality,
        cancelled=cancelled,
        narrowest=narrowest,
        law=varying,
    )


def bevel_edges(
    mesh: MeshData,
    distance: float,
    choice: EdgeChoice = "all",
    keys: Sequence[str] = (),
    *,
    selected_edges: Sequence[int] | None = None,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    narrowest: float = MAX_FACET_SAG,
    shape: ChamferShape | None = None,
) -> BooleanOutcome:
    """Fast die gewählten Kanten — dieselbe Handlung wie ``brep.edit.chamfer``.

    ``distance`` ist die Rücknahme auf **jeder** der beiden Flächen, wie im
    exakten Kern — oder, mit ``shape``, auf der Bezugsfläche (P6.2). Am Netz
    ist die Fase der genauere der beiden Fälle: Sie ist eine Ebene, und eine
    Ebene hat ein Netz exakt — hier weicht nichts ab.
    """
    return _worked_edges(
        mesh,
        distance,
        choice,
        keys,
        selected_edges=selected_edges,
        rounded=False,
        quality=quality,
        cancelled=cancelled,
        narrowest=narrowest,
        shape=shape,
    )


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
    # Ein Viertelkreis mit ``steps`` Stuecken ist das erste Viertel eines
    # ``4*steps``-Ecks — aus Ganzzahlen und damit ueberall gleich (RM-187).
    quarter = np.asarray(
        [units.circle_point(4 * steps, index) for index in range(steps + 1)], dtype=float
    )
    sine, cosine = quarter[:, 1].copy(), quarter[:, 0].copy()
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


def _corner_hull(points: np.ndarray, vertex: np.ndarray) -> MeshData | None:
    """Die Eckhülle an ihrem Knoten — ``None``, wo die Punkte keinen Körper ergeben.

    **Vier Punkte braucht ein Körper mindestens**, und die Rechnung darüber gibt
    das nicht immer her: :func:`_chamfer_contacts` nimmt nur Flächen an, die
    **genau zwei** der gewählten Kanten berühren, und :func:`_halfspace_vertices`
    nur beschränkte Ecken.

    Gemessen am 13.09.2026 an ``plate_countersunk.stl``, nur verschweißt und
    nicht über ``ingest.normalise`` eingelesen: An acht Knoten der Senkungen
    enden drei Züge, an denen **vier** verschiedene Flächen liegen — zwei
    davon berühren nur eine Kante, also blieben zwei Kontaktpunkte übrig. Mit
    dem Knoten sind das drei Punkte, und Qhull warf ``QH6214 … not enough
    points(3) to construct initial simplex`` aus :func:`_hull` heraus. Die
    Auswertung macht aus einer fremden Ausnahme einen ``InternalError``, und
    der Kunde liest „Fehlerbericht" für eine gewöhnliche Handlung (Regel 17).

    Ein Eckanschluss, den die Geometrie nicht hergibt, ist kein Programmfehler:
    Die Flanken der Kantenwerkzeuge schneiden dort auch ohne ihn, genau wie an
    jeder Ecke, an der nicht alle Kanten gewählt sind.
    """
    if len(points) < 4:
        return None
    return _hull(np.asarray(points, dtype=float) + vertex)


def _ball(radius: float, *, turn_limit: bool = True) -> Any:
    """Eine Kugel, deren Facetten :data:`MAX_FACET_SAG` auch innen einhalten.

    **Die Unterteilung hängt am Radius**, wie bei :func:`_arc_steps` und aus
    demselben Grund: Eine feste Zahl ist bei R = 0,5 Verschwendung und bei
    R = 5 zu grob. Geprüft wird die Stützweite jeder Facette — der Abstand
    ihrer Ebene von der Mitte —, denn sie ist die Abweichung, die im Druck
    ankommt.

    ``turn_limit`` nimmt zusätzlich :data:`MAX_FACET_ANGLE` dazu, und das ist
    keine Feinheit, sondern eine Kostenfrage: Die Winkelgrenze erzwingt eine
    Unterteilung mehr, also viermal so viele Facetten (an R = 0,5: 80 mit der
    Sehnengrenze allein, 1280 mit beiden). Der **Eckanschluss** braucht sie —
    dort ersetzt die Kugel die Flächen der angrenzenden Zylinder, und zwei
    Auflösungen nebeneinander hinterlassen eine sichtbare Kante. Der **Wulst**
    braucht sie nicht: Dort füllt die Kugel den Zwickel zwischen zwei
    Zylindern, und der ist so breit wie der Knick des Zugs. Gemessen am Wulst
    R = 0,5 über alle Kanten von ``plate_holes.stl``: 1,53 s und 228 278
    Dreiecke mit der Winkelgrenze, 0,56 s und 53 970 ohne — bei derselben
    Sehnenabweichung.
    """
    import trimesh

    divisions = 0
    while True:
        ball = trimesh.creation.icosphere(subdivisions=divisions, radius=radius)
        supports = np.einsum("ij,ij->i", ball.triangles[:, 0], ball.face_normals)
        arcs = np.linalg.norm(np.diff(ball.vertices[ball.edges_unique], axis=1)[:, 0], axis=1)
        turns_enough = not turn_limit or float(arcs.max()) <= (
            2.0 * radius * units.exact_sin(MAX_FACET_ANGLE / 2.0)
        )
        if float(supports.min()) >= radius - MAX_FACET_SAG and turns_enough:
            return ball
        divisions += 1


def _corner_ball(radius: float) -> np.ndarray:
    """Die Ecken des Kugelknotens — der Körper dazu steht in :func:`_ball`."""
    return np.asarray(_ball(radius).vertices)


def _chamfer_contacts(
    star: list[tuple[MeshEdge, int]],
    normals: np.ndarray,
    size: float,
    sign: float,
    shape: ChamferShape | None = None,
) -> np.ndarray:
    """Schnittpunkte der beiden Fasenflanken auf jeder ursprünglichen Fläche.

    Jede Fase ist hier ihre Ebene durch die beiden Berührlinien. Bei gleicher
    Breite steht sie senkrecht auf der Winkelhalbierenden; mit zwei Breiten
    (:func:`chamfer_reaches`) ist sie gekippt, und ihre Normale kommt aus der
    Kante und der Linie zwischen den Berührpunkten.
    """
    boundaries: list[tuple[np.ndarray, float, np.ndarray]] = []
    for entry, end in star:
        original = np.asarray(entry.normals[end], dtype=float)
        pair = sign * original
        along = np.asarray(entry.points[1 if end == 0 else -2]) - entry.points[end]
        along /= float(np.linalg.norm(along))
        bisector = pair.sum(axis=0)
        bisector /= float(np.linalg.norm(bisector))
        first_in = _along_face(pair[0], along, -bisector)
        second_in = _along_face(pair[1], along, -bisector)
        assert first_in is not None and second_in is not None
        reach_one, reach_two = chamfer_reaches(size, shape, original[0], original[1])
        first_touch = first_in * reach_one
        second_touch = second_in * reach_two
        plane = np.cross(along, second_touch - first_touch)
        plane /= float(np.linalg.norm(plane))
        if float(plane @ bisector) < 0.0:
            plane = -plane
        boundaries.append((plane, float(plane @ first_touch), pair))
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
    star: list[tuple[MeshEdge, int]],
    size: float,
    *,
    rounded: bool,
    ball_vertices: np.ndarray,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    shape: ChamferShape | None = None,
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
        contacts = _chamfer_contacts(star, normals, size, sign, shape)
        # Drei Kontaktpunkte und der Knoten sind das Wenigste, woraus eine
        # Haube entsteht; darunter gibt es keine (siehe :func:`_corner_hull`).
        if len(contacts) < 3:
            return None
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
        capped = _corner_hull(corners, vertex)
        return (kind, capped, []) if capped is not None else None
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
    local = _corner_hull(corners, vertex)
    ball = _corner_hull(ball_points, vertex)
    if local is None or ball is None:
        return None
    removed = boolean(
        "difference", [local, ball], quality=quality, allow_empty=True, cancelled=cancelled
    )
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
    mesh: MeshData,
    region: MeshData,
    frame: np.ndarray,
    size: float,
    complement: bool,
    *,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
) -> BooleanOutcome:
    """Der örtliche Ersatz muss ausschließlich die drei gewählten Flächen treffen."""
    clipped = boolean(
        "intersection", [mesh, region], quality=quality, allow_empty=True, cancelled=cancelled
    )
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
            # Der Satz nennt zwei Wege, und beide sind Handlungen am Schritt —
            # nicht „Reparieren", die Vorgabe des Geometriefehlers: Am Netz ist
            # hier nichts kaputt, die Ecke ist nur zu eng für das Maß.
            suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
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
    selected_edges: Sequence[int] | None = None,
    rounded: bool,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    narrowest: float = MAX_FACET_SAG,
    shape: ChamferShape | None = None,
    law: RadiusLaw | None = None,
) -> BooleanOutcome:
    """Löst die Auswahl im Weltsystem und rechnet gemischte Ecken in ihrem Rahmen.

    **Eine Gruppe nimmt, was sich bearbeiten lässt** (22.09.2026). „Alle
    Kanten" hielt am ersten Zug an, an dem keine zwei Flächen unter einem
    Winkel stoßen — an zusammengesetzten Kundenteilen, deren Hälften Wand an
    Wand stehen, blockierten 39 solche Züge die übrigen 927 (Übertrag der
    Durchsicht v0.4.1). Wer eine Gruppe wählt, meint die Kanten, die es gibt;
    der Rest wird übersprungen und im Befund ``edges.skipped`` gezählt. Eine
    ausdrücklich benannte Kante hält weiter an (§21.3) — dort ist genau sie
    gemeint.
    """
    entries = edges_of(mesh)
    chosen = selected_or_wanted(entries, choice, keys, selected_edges)
    skipped = 0
    if selected_edges is None and not keys and choice != "named":
        kept = [entry for entry in chosen if workable(entry)]
        skipped = len(chosen) - len(kept)
        if not kept:
            raise _without_an_angle(size)
        chosen = kept
    if law is not None:
        check_varying_radius(
            [
                (entry.node_indices[0], entry.node_indices[-1], law_at_ends(entry.points, law))
                for entry in chosen
                if entry.node_indices
            ],
            mixed_corner=any(
                _mixed_corner_frame(star) is not None for star in _corner_stars(entries, chosen)
            ),
        )
    largest = contact_band_limit(
        entries,
        chosen,
        size,
        rounded=rounded,
        tolerance=weld_tolerance(mesh.bounds.diagonal),
        narrowest=narrowest,
        shape=shape,
        law=law,
    )
    if largest is not None:
        raise too_large_for_the_faces(size, largest, rounded=rounded, varying=law is not None)
    if law is not None:
        outcome = _edge_work(
            mesh, entries, chosen, size, rounded=True, quality=quality, cancelled=cancelled, law=law
        )
    else:
        outcome = _grouped_edge_work(
            mesh,
            entries,
            chosen,
            size,
            rounded=rounded,
            quality=quality,
            cancelled=cancelled,
            shape=shape,
        )
    if skipped:
        outcome.findings.append(_skipped_finding(skipped, len(chosen)))
    return outcome


#: Wie viele Stellen je Kantenstück die Berührlinien höchstens prüfen — genug,
#: dass eine Bohrung neben einer langen Kante nicht zwischen zwei Proben liegt,
#: und begrenzt, damit ein langer Zug nicht tausend Strahlen kostet.
_BAND_SAMPLES: Final = 8


def contact_band_limit(
    entries: Sequence[MeshEdge],
    chosen: Sequence[MeshEdge],
    size: float,
    *,
    rounded: bool,
    tolerance: float,
    narrowest: float = MAX_FACET_SAG,
    shape: ChamferShape | None = None,
    law: RadiusLaw | None = None,
) -> float | None:
    """Das Maß, unter dem die Berührlinien aller gewählten Kanten auf ihren Flächen
    bleiben — ``None``, wenn das eingetragene passt.

    Mit einem Radiusverlauf (``law``, P6.1) ist ``size`` sein größter Radius,
    und jeder Strahl greift so weit, wie der Radius **an seiner Stelle** es
    verlangt; zusätzliche Strahlen stehen an jeder Stelle des Verlaufs, denn
    dort liegen seine größten Werte. Die Antwort ist dann der größte Radius,
    bei dem der ganze Verlauf im selben Verhältnis verkleinert passt.

    Mit zwei Fasenbreiten (``shape``) reicht jede Seite so weit, wie
    :func:`chamfer_reaches` sagt, und die Antwort ist die größte Breite der
    Bezugsfläche, bei der beide — im selben Verhältnis — passen.

    **Die Frage, die der exakte Kern mit seinem Scheitern beantwortet, und das
    Netz gar nicht stellte** (22.09.2026). Eine Rundung berührt jede ihrer zwei
    Flächen im Abstand ``R / tan(θ/2)`` von der Kante, eine Fase im Abstand
    ihrer Breite. Reicht die Fläche nicht so weit — oder liegt dort schon die
    Berührlinie einer anderen gewählten Kante —, gibt es die Rundung nicht:
    OpenCASCADE lehnt ab, und das Netz schnitt weiter und machte eine 3-mm-Wand
    still niedriger (Fase 2,9 mm: 18,6 statt 20 mm hoch). Gefragt wird mit
    Strahlen in der Ebene jeder Fläche, quer zur Kante: Die nächste scharfe
    Kante, die in derselben Ebene liegt, ist dort der Rand der Fläche.
    Gleichstand zählt als zu groß: Eine Fläche, die auf eine Linie schrumpft,
    baut der exakte Kern nicht, und beide Kerne sollen dasselbe sagen.

    ``narrowest`` ist die schmalste Fläche, die zählt: Was schmaler ist, gibt
    es im Druck nicht, und eine Rundung, die darüber hinweggeht, verliert
    nichts, was jemand sieht. Die Operation nennt dafür das kleinste Detail
    des Druckers (``PrinterProfile.smallest_detail``); ohne Drucker bleibt es
    bei der Sehnengrenze.

    **Wo zwei Kanten einen Knoten teilen, laufen sie dort ineinander.** Ist die
    andere gewählt, ist das der Eckanschluss (``_corner_tools``, am exakten
    Kern die Eckverrundung), und ihre Streifen dürfen sich überlappen. Ist sie
    es nicht, läuft die Rundung am Ende der eigenen Kante in sie aus, solange
    der Treffer näher am gemeinsamen Knoten liegt, als die Berührlinie
    reicht — gemessen am Tetraeder mit drei Rundungen an einer Ecke: Am
    fernen Ende jeder Kante schnitt der Strahl die dritte Kante 3,5 mm vor dem
    Knoten, bei 5,8 mm Reichweite.

    **Gerechnet als Feld über alle Strahlen.** Die erste Fassung ging die
    Treffer in Python durch und fragte die Nachbarn über die Mitten der
    Kantenstücke mit dem Radius des längsten Stücks — an ``BowlingGame.3mf``
    (349 128 Dreiecke, „alle Kanten") 19 s. Jetzt sucht der Baum über Punkte,
    die entlang jedes Stücks im Abstand der größten Reichweite liegen.
    """
    from scipy.spatial import cKDTree

    if not chosen or size <= EPS_GEOM:
        return None
    chosen_ids = {id(entry) for entry in chosen}
    chains = [entry for entry in entries if entry.normals]
    if not chains:
        return None
    counts = np.asarray([len(entry.normals) for entry in chains], dtype=np.int64)
    first = np.concatenate(
        [np.asarray(entry.points, dtype=float)[: len(entry.normals)] for entry in chains]
    )
    last = np.concatenate(
        [np.asarray(entry.points, dtype=float)[1 : len(entry.normals) + 1] for entry in chains]
    )
    normals = np.concatenate([np.asarray(entry.normals, dtype=float) for entry in chains])
    owners = np.repeat(np.arange(len(chains)), counts)
    convex = np.repeat(np.asarray([entry.convex for entry in chains], dtype=bool), counts)
    # Wo jedes Stück in seinem Zug beginnt, wie lang der Zug ist und ob er an
    # seinem ersten Punkt anfängt — für den Radius an einer Stelle (P6.1).
    # Nur mit einem Verlauf gerechnet: „alle Kanten" an einem großen Netz
    # sind zehntausende Züge, und ohne Verlauf braucht niemand diese Zahlen.
    piece_length = np.linalg.norm(last - first, axis=1)
    piece_start: np.ndarray | None = None
    laws: list[LawOnChain | None] = []
    if law is not None:
        before = np.cumsum(piece_length) - piece_length
        first_piece = np.concatenate(([0], np.cumsum(counts)[:-1]))
        piece_start = before - before[first_piece][owners]
        laws = [
            law_on_points(entry.points, law) if id(entry) in chosen_ids else None
            for entry in chains
        ]

    def ratio(piece: np.ndarray, share: np.ndarray) -> np.ndarray:
        """Radius an der Stelle ``share`` des Stücks ``piece``, als Anteil von ``size``.

        Nur gewählte Züge tragen einen Verlauf; an allen anderen ist der Anteil
        eins und zählt ohnehin nicht (``counted``).
        """
        if law is None or piece_start is None:
            return np.ones(len(piece))
        found = np.ones(len(piece))
        for number, (chunk, where) in enumerate(zip(piece.tolist(), share.tolist(), strict=True)):
            on_chain = laws[int(owners[chunk])]
            if on_chain is not None:
                distance = float(piece_start[chunk]) + where * float(piece_length[chunk])
                found[number] = on_chain.radius(distance) / size
        return found

    chosen_chain = np.asarray([id(entry) in chosen_ids for entry in chains], dtype=bool)
    if not chosen_chain.any():
        return None
    reach = _reaches(normals, size, rounded=rounded)
    # Jede Seite greift ``grows · size + fixed`` weit: mit dem Maß wachsend, oder
    # fest — die zweite Breite einer Fase mit zwei Abständen wächst nicht mit.
    grows = np.stack((reach, reach), axis=1) / size
    fixed = np.zeros_like(grows)
    if not rounded and shape is not None:
        sided = np.asarray(
            [chamfer_reaches(size, shape, pair[0], pair[1]) for pair in normals], dtype=float
        )
        if shape.angle is None and shape.second is not None:
            fixed_side = np.isclose(sided, float(shape.second)) & ~np.isclose(sided, size)
            if abs(float(shape.second) - size) <= EPS_GEOM:
                fixed_side[:] = False
            grows = np.where(fixed_side, 0.0, sided / size)
            fixed = np.where(fixed_side, sided, 0.0)
        else:
            grows = sided / size
        reach = sided.max(axis=1)
    sided = grows * size + fixed

    # Die Strahlen: je gewähltem Stück bis zu acht Stellen, je Seite einer.
    picked = np.flatnonzero(chosen_chain[owners] & np.isfinite(reach))
    span = last[picked] - first[picked]
    lengths = np.linalg.norm(span, axis=1)
    good = lengths > EPS_GEOM
    picked, span, lengths = picked[good], span[good], lengths[good]
    along = span / lengths[:, None]
    one, two = normals[picked, 0], normals[picked, 1]
    into = np.where(convex[picked][:, None], -(one + two), one + two)
    weight = np.linalg.norm(into, axis=1)
    good = weight > EPS_GEOM
    picked, span, lengths, along, one, two, into = (
        picked[good],
        span[good],
        lengths[good],
        along[good],
        one[good],
        two[good],
        into[good] / weight[good][:, None],
    )
    if not len(picked):
        return None
    samples = np.clip(
        np.ceil(lengths / np.maximum(reach[picked], EPS_GEOM)), 1, _BAND_SAMPLES
    ).astype(np.int64)
    owner_rows: list[np.ndarray] = []
    origin_rows: list[np.ndarray] = []
    head_rows: list[np.ndarray] = []
    face_rows: list[np.ndarray] = []
    walk_rows: list[np.ndarray] = []
    wanted_rows: list[np.ndarray] = []
    growing_rows: list[np.ndarray] = []
    for number, side in enumerate((one, two)):
        direction = np.cross(side, along)
        size_of = np.linalg.norm(direction, axis=1)
        valid = size_of > EPS_GEOM
        direction = direction / np.where(valid, size_of, 1.0)[:, None]
        flip = np.einsum("ij,ij->i", direction, into) <= 0.0
        direction[flip] *= -1.0
        index = np.repeat(np.arange(len(picked)), samples)
        position = np.concatenate([(np.arange(count) + 0.5) / count for count in samples])
        if law is not None and piece_start is not None:
            index, position = _with_station_rays(
                index, position, picked, owners, piece_start, piece_length, laws
            )
        index, position = index[valid[index]], position[valid[index]]
        scale = ratio(picked[index], position)
        owner_rows.append(picked[index])
        origin_rows.append(first[picked[index]] + span[index] * position[:, None])
        head_rows.append(direction[index])
        face_rows.append(side[index])
        walk_rows.append(along[index])
        wanted_rows.append(sided[picked[index], number] * scale)
        growing_rows.append(grows[picked[index], number] * scale)
    mine = np.concatenate(owner_rows)
    if not len(mine):
        return None
    origin = np.concatenate(origin_rows)
    head = np.concatenate(head_rows)
    face = np.concatenate(face_rows)
    walk = np.concatenate(walk_rows)
    wanted = np.concatenate(wanted_rows)
    growing = np.concatenate(growing_rows)

    # Kandidaten: Stücke, die einem Strahl näher kommen, als jede Überlappung reicht.
    chosen_reach = reach[chosen_chain[owners] & np.isfinite(reach)]
    limit = float(wanted.max() + (chosen_reach.max() if len(chosen_reach) else 0.0)) + tolerance
    spacing = max(limit, EPS_GEOM)
    lengths_all = np.linalg.norm(last - first, axis=1)
    steps = np.maximum(np.ceil(lengths_all / spacing).astype(np.int64), 1)
    segment_of = np.repeat(np.arange(len(first)), steps + 1)
    fraction = np.concatenate([np.linspace(0.0, 1.0, count + 1) for count in steps])
    points = first[segment_of] + (last[segment_of] - first[segment_of]) * fraction[:, None]
    tree = cKDTree(points)
    near = tree.query_ball_point(origin, limit + spacing / 2.0 + tolerance)
    sizes = np.fromiter((len(found) for found in near), dtype=np.int64, count=len(near))
    if not sizes.sum():
        return None
    rows = np.repeat(np.arange(len(origin)), sizes)
    columns = segment_of[np.fromiter((i for found in near for i in found), dtype=np.int64)]
    pair = np.unique(rows * len(first) + columns)
    rows, columns = pair // len(first), pair % len(first)
    keep = columns != mine[rows]
    rows, columns = rows[keep], columns[keep]

    start_point = first[columns] - origin[rows]
    stop_point = last[columns] - origin[rows]
    planar = (np.abs(np.einsum("ij,ij->i", start_point, face[rows])) <= tolerance) & (
        np.abs(np.einsum("ij,ij->i", stop_point, face[rows])) <= tolerance
    )
    start_u = np.einsum("ij,ij->i", start_point, head[rows])
    start_v = np.einsum("ij,ij->i", start_point, walk[rows])
    stop_u = np.einsum("ij,ij->i", stop_point, head[rows])
    stop_v = np.einsum("ij,ij->i", stop_point, walk[rows])
    across = start_v - stop_v
    crossing = planar & (np.abs(across) > EPS_GEOM)
    share = np.where(crossing, start_v / np.where(crossing, across, 1.0), -1.0)
    crossing &= (share >= -1e-9) & (share <= 1.0 + 1e-9)
    distance = start_u + share * (stop_u - start_u)
    crossing &= distance > tolerance
    rows, columns, distance = rows[crossing], columns[crossing], distance[crossing]
    share = share[crossing]
    if not len(rows):
        return None
    # Je Strahl der nächste Treffer: der Rand der Fläche an dieser Stelle.
    order = np.lexsort((distance, rows))
    rows, columns, distance, share = rows[order], columns[order], distance[order], share[order]
    nearest = np.concatenate(([True], rows[1:] != rows[:-1]))
    rows, columns, width = rows[nearest], columns[nearest], distance[nearest]
    share = np.clip(share[nearest], 0.0, 1.0)

    mine_chain = owners[mine[rows]]
    other_chain = owners[columns]
    other_chosen = chosen_chain[other_chain]
    facing_one = np.einsum("ij,ij->i", normals[columns, 0], face[rows]) > 1.0 - 1e-6
    facing_two = np.einsum("ij,ij->i", normals[columns, 1], face[rows]) > 1.0 - 1e-6
    facing = facing_one | facing_two
    # Die Nachbarkante greift auf **dieser** Fläche so weit, wie ihre Seite auf ihr reicht.
    # Mit einem Verlauf greift die Nachbarkante so weit, wie ihr Radius dort
    # ist, wo der Strahl sie trifft.
    other_scale = ratio(columns, share)
    beside = np.where(facing_one, sided[columns, 0], sided[columns, 1]) * other_scale
    beside_grows = np.where(facing_one, grows[columns, 0], grows[columns, 1]) * other_scale
    counted = other_chosen & facing
    other_reach = np.where(counted, np.nan_to_num(beside, posinf=0.0), 0.0)
    needed = wanted[rows] + other_reach
    # Der Anteil, der mit dem Maß wächst; der Rest steht fest (zweite Breite).
    scaling = growing[rows] + np.where(counted, np.nan_to_num(beside_grows, posinf=0.0), 0.0)
    violating = (width >= narrowest) & (needed >= width - tolerance)
    if not violating.any():
        return None
    rows, width, needed = rows[violating], width[violating], needed[violating]
    scaling = scaling[violating]
    mine_chain, other_chain = mine_chain[violating], other_chain[violating]
    other_chosen = other_chosen[violating]
    ends = np.asarray(
        [
            (entry.node_indices[0], entry.node_indices[-1]) if entry.node_indices else (-1, -2)
            for entry in chains
        ],
        dtype=np.int64,
    )
    tips = np.asarray([(entry.points[0], entry.points[-1]) for entry in chains], dtype=float)
    hit = origin[rows] + head[rows] * width[:, None]
    foreign = other_chain != mine_chain
    connected = np.zeros(len(rows), dtype=bool)
    close = np.zeros(len(rows), dtype=bool)
    for mine_end in (0, 1):
        for other_end in (0, 1):
            shared = foreign & (ends[mine_chain, mine_end] == ends[other_chain, other_end])
            connected |= shared
            corner = tips[mine_chain, mine_end]
            close |= shared & (np.linalg.norm(hit - corner, axis=1) <= needed + tolerance)
    skipped = (connected & other_chosen) | close
    if skipped.all():
        return None
    width, needed, scaling = width[~skipped], needed[~skipped], scaling[~skipped]
    steady = needed - scaling * size
    alone = (scaling <= EPS_GEOM) | (steady >= width - tolerance)
    if bool(np.any(alone)) and shape is not None and shape.second is not None:
        # Schon die feste zweite Breite passt nicht — mit der ersten ist das
        # nicht zu lösen, und der Satz nennt, welche Zahl zu groß ist.
        count = np.maximum(np.rint(steady[alone] / float(shape.second)), 1.0)
        room = (width[alone] - scaling[alone] * size) / count
        raise too_large_for_the_faces(
            float(shape.second),
            float(max(np.min(room), 0.0)),
            rounded=False,
            second=True,
        )
    usable = scaling > EPS_GEOM
    return float(((width[usable] - steady[usable]) / scaling[usable]).min())


def _with_station_rays(
    index: np.ndarray,
    position: np.ndarray,
    picked: np.ndarray,
    owners: np.ndarray,
    piece_start: np.ndarray,
    piece_length: np.ndarray,
    laws: Sequence[LawOnChain | None],
) -> tuple[np.ndarray, np.ndarray]:
    """Zusätzliche Strahlen an jeder Stelle eines Verlaufs, die in ein gewähltes Stück fällt.

    Die gleichmäßigen Strahlen stehen zwischen den Stellen; der größte Radius
    eines monotonen Verlaufs steht aber an einer Stelle. Ohne diese Strahlen
    könnte die Prüfung genau dort vorbeisehen.
    """
    extra_index: list[int] = []
    extra_position: list[float] = []
    for number, piece in enumerate(picked.tolist()):
        on_chain = laws[int(owners[piece])]
        width = float(piece_length[piece])
        if on_chain is None or width <= EPS_GEOM:
            continue
        low = float(piece_start[piece])
        for place in on_chain.places():
            if low <= place <= low + width:
                extra_index.append(number)
                extra_position.append(min(max((place - low) / width, 0.0), 1.0))
    if not extra_index:
        return index, position
    return (
        np.concatenate([index, np.asarray(extra_index, dtype=index.dtype)]),
        np.concatenate([position, np.asarray(extra_position, dtype=float)]),
    )


def _reaches(normals: np.ndarray, size: float, *, rounded: bool) -> np.ndarray:
    """:func:`_reach` für ein ganzes Feld von Normalenpaaren."""
    if not rounded:
        return np.full(len(normals), float(size))
    dots = np.clip(np.einsum("ij,ij->i", normals[:, 0], normals[:, 1]), -1.0, 1.0)
    half = (math.pi - np.arccos(dots)) / 2.0
    valid = (half > EPS_GEOM) & (half < math.pi / 2.0 - EPS_GEOM)
    return np.where(valid, size / np.tan(np.where(valid, half, 1.0)), np.inf)


def _reach(pair: np.ndarray, size: float, *, rounded: bool) -> float:
    """Wie weit eine Rundung oder Fase auf ihren Flächen von der Kante greift."""
    if not rounded:
        return size
    one, two = pair
    half = (math.pi - math.acos(float(np.clip(np.dot(one, two), -1.0, 1.0)))) / 2.0
    if half <= EPS_GEOM or half >= math.pi / 2.0 - EPS_GEOM:
        return math.inf
    return size / math.tan(half)


def too_large_for_the_faces(
    size: float, largest: float, *, rounded: bool, second: bool = False, varying: bool = False
) -> GeometryError:
    """Der eine Satz beider Kerne, wenn die Berührlinien nicht auf die Flächen passen.

    ``second`` sagt, dass die feste zweite Breite einer Fase zu groß ist (P6.2);
    ``varying``, dass die Radien eines Verlaufs zu groß sind (P6.1) — dann ist
    ``largest`` der größte Radius des Verlaufs, bei dem alle Stellen im selben
    Verhältnis verkleinert passen.
    """
    from app.core.units import format_length

    shown = format_length(max(largest, 0.0))
    if varying:
        return GeometryError(
            detail=_(
                "Die Radien sind für diese Kanten zu groß: Auf einer angrenzenden Fläche "
                "bleibt kein Platz für die Rundung. Verkleinern Sie die Radien so, dass "
                "der größte unter {largest} bleibt, oder bearbeiten Sie weniger Kanten.",
                largest=shown,
            ),
            suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
            values={"size_mm": round(size, 3), "largest_mm": largest},
        )
    if second:
        return GeometryError(
            detail=_(
                "Die zweite Breite ist für diese Kanten zu groß: Auf einer angrenzenden "
                "Fläche bleibt kein Platz für die Fase. Wählen Sie eine zweite Breite "
                "unter {largest}, oder bearbeiten Sie weniger Kanten.",
                largest=shown,
            ),
            suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
            values={"size_mm": round(size, 3), "largest_mm": largest, "field": "second_distance"},
        )
    return GeometryError(
        detail=(
            _(
                "Der Radius ist für diese Kanten zu groß: Auf einer angrenzenden Fläche "
                "bleibt kein Platz für die Rundung. Wählen Sie einen Radius unter {largest}, "
                "oder bearbeiten Sie weniger Kanten.",
                largest=shown,
            )
            if rounded
            else _(
                "Die Breite ist für diese Kanten zu groß: Auf einer angrenzenden Fläche "
                "bleibt kein Platz für die Fase. Wählen Sie eine Breite unter {largest}, "
                "oder bearbeiten Sie weniger Kanten.",
                largest=shown,
            )
        ),
        suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
        values={"size_mm": round(size, 3), "largest_mm": largest},
    )


def _skipped_finding(skipped: int, worked: int) -> Finding:
    """Wie viele Kanten einer Gruppe ausgelassen wurden — und warum."""
    return Finding(
        code="edges.skipped",
        severity="warning",
        message=_(
            "Einige Kanten dieser Auswahl wurden ausgelassen: Dort stoßen keine zwei "
            "Flächen unter einem Winkel zusammen, etwa wo zwei Teile Wand an Wand "
            "stehen. Die übrigen Kanten sind bearbeitet."
        ),
        values={"skipped": skipped, "worked": worked},
    )


def _grouped_edge_work(
    mesh: MeshData,
    entries: Sequence[MeshEdge],
    chosen: Sequence[MeshEdge],
    size: float,
    *,
    rounded: bool,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    shape: ChamferShape | None = None,
) -> BooleanOutcome:
    """Die gewählten Züge in unabhängigen Gruppen, gemischte Ecken in ihrem Rahmen."""
    groups = _selected_edge_groups(chosen)
    mixed = any(_mixed_corner_frame(star) is not None for star in _corner_stars(entries, chosen))
    if mixed and shape is not None and (shape.second is not None or shape.angle is not None):
        # Der gemischte Eckanschluss (außen und innen an einem Knoten) ist für
        # gleiche Breiten gebaut; für zwei verschiedene gibt es ihn nicht.
        raise GeometryError(
            detail=_(
                "Zwei verschiedene Fasenbreiten gehen nicht an einer Ecke, an der "
                "eine Außen- und eine Innenkante zusammentreffen. Wählen Sie gleiche "
                "Breiten, oder lassen Sie eine der Kanten an dieser Ecke aus."
            ),
            suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
        )
    if len(groups) == 1 or not mixed:
        return _placed_edge_work(
            mesh,
            entries,
            chosen,
            size,
            rounded=rounded,
            quality=quality,
            cancelled=cancelled,
            shape=shape,
        )
    runs: list[BooleanOutcome] = []
    body = mesh
    for group in groups:
        result = _placed_edge_work(
            body, entries, group, size, rounded=rounded, quality=quality, cancelled=cancelled
        )
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
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    shape: ChamferShape | None = None,
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
        return _edge_work(
            mesh,
            entries,
            chosen,
            size,
            rounded=rounded,
            quality=quality,
            cancelled=cancelled,
            shape=shape,
        )
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
    result = _edge_work(
        mesh.replacing(raw),
        local_entries,
        local_chosen,
        size,
        rounded=rounded,
        quality=quality,
        cancelled=cancelled,
    )
    world = result.mesh.raw.copy()
    transform.moved(world, frame)
    result.mesh = result.mesh.replacing(world)
    return result


def _edge_work(
    mesh: MeshData,
    entries: Sequence[MeshEdge],
    chosen: Sequence[MeshEdge],
    size: float,
    *,
    rounded: bool,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
    shape: ChamferShape | None = None,
    law: RadiusLaw | None = None,
) -> BooleanOutcome:
    """Der gemeinsame Weg von Verrundung und Fase.

    Mit ``law`` bekommt jeder Zug sein Werkzeug aus Querschnitten
    (:func:`_varying_tool`) und jede Ecke die Kugel mit dem Radius, den ihre
    Züge dort gemeinsam haben — dass es einer ist, hat
    :func:`check_varying_radius` vorher verlangt.

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
        # **Zwischen den Kanten gefragt und nicht in der inneren Schleife.**
        # Ein Werkzeugkörper ist ein Aufruf in numpy und shapely und dort
        # kooperativ nicht zu unterbrechen; die Kante davor ist die Stelle,
        # an der ein Klick auf *Abbrechen* ankommt. Dieselbe Grenze wie in
        # ``boolean.boolean`` zwischen den Rückfallstufen (§15.6). Gemessen
        # an einer Lochplatte mit 60 Bohrungen: 2,7 s für die Fase über alle
        # Kanten, 6,9 s für die Verrundung — beides über der Grenze, ab der
        # eine Rechnung abbrechbar sein muss.
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if law is not None:
            tool = _varying_tool(entry, law, quality=quality, cancelled=cancelled)
        else:
            tool = rounding_tool(
                entry,
                size,
                rounded,
                min_steps=steps if id(entry) in refined_ids else 0,
                extend_ends=id(entry) not in refined_ids,
                quality=quality,
                cancelled=cancelled,
                shape=shape,
            )
        (outer if entry.convex else inner).append(tool)
    runs: list[BooleanOutcome] = []
    ball_vertices = _corner_ball(size) if stars and rounded and law is None else np.empty((0, 3))
    balls: dict[float, np.ndarray] = {}
    for star in stars:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        corner_size, corner_ball = size, ball_vertices
        if law is not None:
            member, end = star[0]
            corner_size = law_at_ends(member.points, law)[0 if end == 0 else 1]
            corner_ball = balls.setdefault(corner_size, _corner_ball(corner_size))
        prepared = _corner_tools(
            star,
            corner_size,
            rounded=rounded,
            ball_vertices=corner_ball,
            quality=quality,
            cancelled=cancelled,
            shape=shape,
        )
        if prepared is not None:
            kind, tool, preparation = prepared
            runs.extend(preparation)
            (outer if kind == "difference" else inner).append(tool)
    regions: list[MeshData] = []
    targets: list[MeshData] = []
    for _star, (frame, complement) in mixed:
        region, target = _mixed_corner_region(size, rounded=rounded)
        if complement:
            reversed_target = boolean(
                "difference", [region, target], quality=quality, cancelled=cancelled
            )
            runs.append(reversed_target)
            target = reversed_target.mesh
        target = _extend_corner_contacts(target, size)
        transform.moved(region.raw, frame)
        transform.moved(target.raw, frame)
        runs.append(
            _check_corner_region(
                mesh, region, frame, size, complement, quality=quality, cancelled=cancelled
            )
        )
        regions.append(region)
        targets.append(target)
    if regions:
        clipped_inner = []
        for tool in inner:
            clipped = boolean(
                "difference",
                [tool, *regions],
                quality=quality,
                allow_empty=True,
                cancelled=cancelled,
            )
            runs.append(clipped)
            if clipped.mesh.triangle_count:
                clipped_inner.append(clipped.mesh)
        inner = [*clipped_inner, *targets]
        outer.extend(regions)

    body = mesh
    for kind, tools in (("difference", outer), ("union", inner)):
        if not tools:
            continue
        outcome = boolean(kind, [body, *tools], quality=quality, cancelled=cancelled)
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


#: Warum eine Rundung ohne zwei ebene Nachbarflächen keine Kante zurückgibt —
#: der Satz der Operation, den auch das Merkmalspanel in die graue Zeile
#: schreibt (``perceive.actions``).
NOT_BETWEEN_TWO_PLANES: Final = _(
    "Diese Rundung grenzt nicht an zwei ebene Flächen — sie lässt sich "
    "nicht auf eine Kante zurückführen. Verrunden Sie stattdessen neu."
)


def sharp_corner(
    mesh: MeshData, feature: Feature, *, features: Mapping[str, Feature] | None = None
) -> SharpCorner:
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
    normals, neighbours = _around(mesh, triangles, axis, feature.params.get("centre"), features)
    if len(normals) != THROUGH:
        raise GeometryError(detail=NOT_BETWEEN_TWO_PLANES, suggestions=(CHANGE_SELECTION, CANCEL))
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
    mesh: MeshData,
    triangles: list[int],
    axis: np.ndarray,
    centre: Any = None,
    features: Mapping[str, Feature] | None = None,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Die Normalen der angrenzenden Flächen und je ein Punkt darauf.

    **Nur die quer zur Achse.** Eine Rundung an einer senkrechten Kante grenzt
    auch an Deckel und Boden, und die beiden sind einander entgegengesetzt:
    Der erste Anlauf nahm sie als das gesuchte Paar und bekam „diese Flächen
    sind parallel" zurück. Gesucht sind die Flächen, zwischen denen die
    Rundung *liegt*, und die stehen senkrecht auf ihrer Achse.
    """
    from app.core.perceive.features import (
        nearly_flat_mask,
        planar_mask,
        planes_beside,
    )

    # Eine Mantelfacette besitzt ebenfalls eine Normale, aber keine ebene
    # Nachbarfläche. Dieselbe Flächenerkennung wie beim Anklicken belegt die
    # Ebene; sonst würde deren lokale Tangente eine falsche Kante erzeugen.
    # **Die Frage selbst steht bei der Erkennung** (``planes_beside``): Sie
    # entscheidet dort, ob ein Bogen als Kante oder als Wand in den Baum kommt,
    # und hier, ob sich die Kante zurückrechnen lässt — eine Frage, eine
    # Antwort, sonst verspricht der Baum, was die Bearbeitung nicht hält.
    # Die Ebenen liest ``planar_mask`` einmal je Körper — dieselbe Menge
    # wie ``detect_faces``, und dieselbe, die das Merkmalfenster fragt.
    beside = planes_beside(
        mesh.raw,
        triangles,
        axis,
        planar_mask(mesh) | nearly_flat_mask(mesh.raw, features or {}),
        centre=None
        if not isinstance(centre, list | tuple) or len(centre) != 3
        else np.asarray(centre, dtype=float),
    )
    if beside is None:
        return [], []
    return [normal for normal, _place in beside], [place for _normal, place in beside]


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


def unround(
    mesh: MeshData,
    feature: Feature,
    *,
    quality: Quality = "fine",
    features: Mapping[str, Feature] | None = None,
    cancelled: CancelToken | None = None,
) -> BooleanOutcome:
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
    corner = sharp_corner(mesh, feature, features=features)
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
    outcome = boolean(kind, [mesh, filler], quality=quality, cancelled=cancelled)
    return BooleanOutcome(mesh=outcome.mesh, solver=outcome.solver, findings=list(outcome.findings))


def reround(
    mesh: MeshData,
    feature: Feature,
    radius: float,
    *,
    quality: Quality = "fine",
    features: Mapping[str, Feature] | None = None,
    cancelled: CancelToken | None = None,
) -> BooleanOutcome:
    """Ändert den Radius einer erkannten Rundung oder belegten Zylinderwand.

    **Zwei Schritte und nicht einer**, weil es zwischen ihnen etwas gibt, das
    beide brauchen: die scharfe Kante. Eine Rundung direkt zu vergrößern hieße,
    den Bogen zu verschieben und die Berührlinien mitzuziehen — dieselbe
    Rechnung, nur ohne den Zwischenstand, an dem man sie prüfen kann.

    Die Kante wird über ihren **Schlüssel** wiedergefunden und nicht über einen
    Index: Zwischen Auffüllen und Neuverrunden ist das Netz ein anderes, und
    jede Nummer darin zeigt danach woandershin (§21.2).

    Eine mindestens halb umlaufende Zylinderwand besitzt dagegen keine
    scharfe Ersatzkante; ihr eigener Rand begrenzt die radiale Bearbeitung.
    """
    if radius <= EPS_GEOM:
        raise ValidationError(
            "diameter",
            _("Ohne Radius entsteht keine Rundung. Dieser Wert muss größer als null sein."),
            value=radius,
        )
    radial = radial_rounding(mesh, feature, radius, quality=quality, cancelled=cancelled)
    if radial is not None:
        return radial
    corner = sharp_corner(mesh, feature, features=features)
    taken = unround(mesh, feature, quality=quality, features=features, cancelled=cancelled)
    key = edge_key(_placed(corner))
    again = round_edges(taken.mesh, radius, "named", [key], quality=quality, cancelled=cancelled)
    return BooleanOutcome(
        mesh=again.mesh,
        solver=deepest([taken.solver, again.solver]) or again.solver,
        findings=[*taken.findings, *again.findings],
    )


def radial_rounding(
    mesh: MeshData,
    feature: Feature,
    radius: float,
    *,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
) -> BooleanOutcome | None:
    """Ändert einen belegten Zylindermantel nur innerhalb seiner ausgewählten Haut.

    Der Werkzeugkörper liegt zwischen alter und radial versetzter Haut.
    Geschlossen wird ausschließlich an deren eigenen Randkanten. Weder
    ein voller Zylinder noch eine angenommene scharfe Kante greifen daneben.
    Die Ausgabe behält ihre Topologie und Randebenen; das Boolesche belegt
    unabhängig davon, dass der gesamte Zwischenraum frei veränderbar ist.
    """
    from app.core.deferred import trimesh
    from app.core.perceive.features import fit_cylinder, radial_cylinder

    patch = list(feature.face_indices)
    if not patch:
        return None
    fit = fit_cylinder(mesh.raw, patch)
    if fit is None:
        return None
    fitted = radial_cylinder(mesh.raw, fit, patch)
    if fitted is None:
        return None
    indices, reverse = np.unique(np.asarray(mesh.raw.faces)[patch], return_inverse=True)
    old = np.asarray(mesh.raw.vertices)[indices]
    faces = reverse.reshape(-1, 3)
    axis = np.asarray(fitted.axis)
    centre = np.asarray(fitted.centre)
    relative = old - centre
    axial = np.outer(relative @ axis, axis)
    radial = relative - axial
    # Auch nachträglich eingefügte Punkte auf einer Sehne skalieren mit.
    # Sie auf den Kreis zu ziehen würde die vorhandene Facette ausbeulen.
    fresh = centre + axial + radial * (radius / fitted.radius)
    changed = mesh.raw.copy()
    vertices = np.array(changed.vertices, copy=True)
    vertices[indices] = fresh
    changed.vertices = vertices
    touched = np.any(np.isin(np.asarray(mesh.raw.faces), indices), axis=1)
    neighbours = np.array(touched, copy=True)
    neighbours[patch] = False
    # Am Rand dürfen nur die Trimmkurven der vorhandenen Ebenen wandern.
    # Eine schräge oder gekrümmte Nachbarhaut würde mitverformt; dafür reicht
    # der belegte Zylinderradius allein nicht als geometrische Absicht aus.
    displacements = vertices - np.asarray(mesh.raw.vertices)
    plane_error = np.einsum(
        "ijk,ik->ij",
        displacements[np.asarray(mesh.raw.faces)[neighbours]],
        np.asarray(mesh.raw.face_normals)[neighbours],
    )
    same_side = np.einsum(
        "ij,ij->i",
        np.asarray(mesh.raw.face_normals)[touched],
        np.asarray(changed.face_normals)[touched],
    )
    if np.any(np.abs(plane_error) > weld_tolerance(mesh.bounds.diagonal)):
        raise GeometryError(
            detail=_(
                "Diese Zylinderfläche lässt sich innerhalb ihrer Ränder nicht versetzen. "
                "Wählen Sie einen kleineren Unterschied zum bisherigen Radius."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    edges = np.vstack((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    _unique_edges, locations, counts = np.unique(
        np.sort(edges, axis=1), axis=0, return_index=True, return_counts=True
    )
    boundary = edges[locations[counts == 1]]
    size = len(old)
    walls = np.vstack(
        (
            np.column_stack((boundary[:, 0], boundary[:, 0] + size, boundary[:, 1] + size)),
            np.column_stack((boundary[:, 0], boundary[:, 1] + size, boundary[:, 1])),
        )
    )
    skin = trimesh.Trimesh(
        vertices=np.vstack((old, fresh)),
        faces=np.vstack((faces, faces[:, ::-1] + size, walls)),
        process=False,
    )
    if skin.volume < 0.0:
        skin.invert()
    if not skin.is_watertight or not skin.is_winding_consistent:
        raise GeometryError(detail=_("Diese Zylinderfläche hat keinen geschlossenen Rand."))
    subtracted = (radius > fitted.radius) == fitted.inward
    outcome = boolean(
        "difference" if subtracted else "union",
        [mesh, MeshData.of(skin)],
        quality=quality,
        allow_empty=True,
        cancelled=cancelled,
    )
    outcome.mesh, _shells = remove_hollow_shells(outcome.mesh)
    validate_radial_change(mesh, outcome.mesh, float(skin.volume), float(skin.area))
    if np.any(same_side <= 0.0):
        # Die Randebene bleibt gleich, ihre bisherigen Dreiecksdiagonalen
        # können bei verschobenen Trimmkurven aber außerhalb der Fläche
        # liegen. Dann liefert der bereits geprüfte Schnitt die neue Teilung.
        return outcome
    # Das Boolesche belegt den freien Zwischenraum. Zurück geht die eigene
    # Topologie: An deckungsgleichen Endrändern erzeugt die Neuvernetzung
    # sonst gelegentlich angehängte Nullhäute mit alten Außenmaßen.
    candidate = mesh.replacing(changed)
    validate_radial_change(mesh, candidate, float(skin.volume), float(skin.area))
    outcome.mesh = candidate
    return outcome


def validate_radial_change(before: Mesh, after: Mesh, volume: float, area: float) -> None:
    """Der gesamte radiale Zwischenkörper muss frei von anderem Material bleiben."""
    tolerance = weld_tolerance(before.bounds.diagonal) * area
    if (
        not after.is_watertight
        or after.component_count != before.component_count
        or after.volume <= EPS_GEOM
        or abs(abs(after.volume - before.volume) - volume) > tolerance
    ):
        raise GeometryError(
            detail=_(
                "Dieser Radius reicht über die angrenzende Wand oder trifft anderes Material. "
                "Wählen Sie einen kleineren Unterschied zum bisherigen Radius."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
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
    *,
    selected_edges: Sequence[int] | None = None,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
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
    chosen = selected_or_wanted(edges_of(mesh), choice, keys, selected_edges)
    # **Jedes Stück einzeln in die Kette.** Zusammengelegt (``concatenate``)
    # überlappen sich die Zylinder eines Zugs an ihren Knicken, und ein Körper
    # mit doppelt belegtem Raum hat kein wohldefiniertes Volumen: Am
    # unterteilten Quader kamen 24250 mm³ heraus statt 24186. Die Vereinigung
    # löst die Überlappung, dafür ist sie da.
    tools: list[MeshData] = []
    for entry in chosen:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        tools.extend(_rod_along(entry, radius))
    return boolean("union", [mesh, *tools], quality=quality, cancelled=cancelled)


def _rod_along(entry: MeshEdge, radius: float) -> list[MeshData]:
    """Der Rundstab entlang eines Kantenzugs — Zylinder je Stück, Kugel je Knick.

    Die Kugeln sind kein Zierat: An einem Knick des Zugs stoßen zwei Zylinder
    unter einem Winkel aneinander und lassen außen einen Keil frei. Eine Kugel
    im Knoten füllt ihn, und zwar für jeden Winkel dieselbe.

    **Und sie ist so fein wie der Stab daneben.** Hier stand eine feste
    Unterteilung (``icosphere(subdivisions=1)``), deren Abweichung mit dem
    Radius wächst — und an einem Knick **ist** die Kugel die Oberfläche.
    Gemessen am Wulst auf der Oberkante eines verrundeten Quaders (27 Knicke),
    als Einsenkung der Facetten gegenüber dem Sollstab: 0,097 mm bei R = 1,5
    (der Vorgabe des Dialogs) und 0,328 mm bei R = 5 — erlaubt sind
    :data:`~app.core.units.MAX_FACET_SAG` = 0,05, und 0,328 mm ist mehr als
    eine Schichthöhe (Fund des Reviews, 13.09.2026). Mit :func:`_ball` sind es
    0,026 und 0,046 mm. Die Unterteilung hängt am Radius, wie :func:`_ring_steps`
    es für die Zylinder rechnet.
    """

    points = np.asarray(entry.points, dtype=float)
    parts: list[Any] = []
    for first, second in itertools.pairwise(points):
        along = second - first
        reach = float(np.linalg.norm(along))
        if reach <= EPS_GEOM:
            continue
        rod = lathe.cylinder(radius=radius, height=reach, sections=_ring_steps(radius))
        transform.moved(rod, _towards(along / reach, (first + second) / 2.0))
        parts.append(rod)
    knots = points[1:-1] if len(points) > THROUGH else np.empty((0, 3))
    if len(knots):
        # Einmal gebaut, je Knick kopiert: Die Unterteilung hängt am Radius
        # und nicht am Knoten (siehe :func:`_ball`).
        shape = _ball(radius, turn_limit=False)
        for point in knots:
            ball = shape.copy()
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


EdgeKernel = Literal["brep", "mesh"]


def edges_in_kernel(
    body: Mesh, kind: str, *, on_mesh: bool = False
) -> tuple[EdgeKernel, list[Any]]:
    """Die Kanten, die eine Kantenoperation an diesem Körper sieht — in ihrem Kern.

    Am exakten Körper (``kind == "brep"``) ist das die Topologie
    (``brep.edit.edges_of``), am Netz sind es die Züge (:func:`edges_of`);
    ``on_mesh`` erzwingt das Netz auch am exakten Körper — für *Wulst
    anlegen*, das am tessellierten Körper vereinigt. Die Auswertung bindet
    ausdrücklich gewählte Kanten hier (``scene.edge_binding``) und muss
    dieselbe Liste sehen wie die Operation: dieselbe Funktion, derselbe Kern.
    """
    if kind == "brep" and not on_mesh:
        from app.core.brep import edit

        return "brep", list(edit.edges_of(body))  # type: ignore[arg-type]
    from app.core.geom.mesh import as_mesh_data

    return "mesh", list(edges_of(as_mesh_data(body)))


def indices_in_kernel(
    kernel: EdgeKernel, body: Mesh, chosen: Sequence[Any], entries: Sequence[Any]
) -> tuple[int, ...]:
    """Die Indizes gewählter Kanten im Auswahlraum des Kerns.

    Am exakten Körper ist das ``solid.edges()`` — über echte Mitgliedschaft in
    der Kantenkarte, nicht über die Position in ``edges_of``, die Nähte und
    Nullkanten auslässt (``brep.edit.native_edge_indices``). Am Netz ist es
    die Position in ``entries``, dem Ergebnis von :func:`edges_of` für genau
    dieses Netz.
    """
    if kernel == "brep":
        from app.core.brep import edit

        return edit.native_edge_indices(body, chosen)  # type: ignore[arg-type]
    positions = {id(entry): index for index, entry in enumerate(entries)}
    return tuple(positions[id(entry)] for entry in chosen)


def points_in_kernel(kernel: EdgeKernel, body: Mesh, entry: Any) -> tuple[Vec3, ...]:
    """Der Zug einer Kante als Punktfolge — dieselbe, die die Ansicht abtastet."""
    if kernel == "brep":
        from app.core.brep import edit

        return edit.edge_points(entry, body.deflection)  # type: ignore[attr-defined]
    return tuple(entry.points)
