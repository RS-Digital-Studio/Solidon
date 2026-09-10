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

import math
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from app.core.geom.measure import SHARP_EDGE_ANGLE
from app.core.geom.mesh import MeshData
from app.core.types import Vec3
from app.core.units import EPS_GEOM

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
    """

    points: tuple[Vec3, ...]
    length: float
    direction: Vec3
    middle: Vec3
    convex: bool

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
    vertices = np.asarray(raw.vertices, dtype=float)

    found: list[MeshEdge] = []
    for nodes, is_convex in _chains(segments, convex):
        points = vertices[nodes]
        described = _describe(points, is_convex)
        if described is not None:
            found.append(described)
    return found


def _describe(points: np.ndarray, convex: bool) -> MeshEdge | None:
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
