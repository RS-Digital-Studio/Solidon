"""Wendelflächen finden — Gewinde an einem eingelesenen Netz (§21.1).

**Warum es dieses Modul gibt.** Ein Gewinde, das in Solidon entsteht, meldet
sich selbst: Der Baustein schreibt ein ``thread``-Merkmal in die Szene, und die
Erkennung muss es nicht finden. Ein **eingelesenes** Netz bringt diese Auskunft
nicht mit — dort sieht die Einpassung nur eine Wendel und passt darauf ein, was
sie kennt. Gemessen an einer Platte mit aufgesetztem Bolzen, alle Größen über
einen STL-Umlauf eingelesen:

===== ==============================================
Größe erfundene Merkmale
===== ==============================================
M4    ein Kegel, zwei Zapfen
M5    **neunzehn Kegel**, ein Zapfen
M6    drei Kegel, zwei Kugeln
M8    zwei Kegel, zwei Zapfen
===== ==============================================

Die Flanke eines Gewindegangs ist örtlich eine Kegelfläche und passt sich
sauber ein; der Rückstand ist klein, das vorhandene Tor lässt sie durch. Und
weil jede Art betroffen ist, hilft der Zylinderfilter in
:func:`~app.core.perceive.features._without_thread_turns` hier nicht — er sieht
Kegel und Kugeln gar nicht.

**Was stattdessen gemessen wird.** Nicht die Einpassungen, sondern die
Geometrie: Der Kamm eines Gewindes ist eine einzige scharfe Kante, die sich um
eine Achse windet. Auf einer Wendel gilt

    z = a + Steigung · θ / 2π

Trägt man ``z - p·θ/2π`` modulo ``p`` auf, fallen die Kantenpunkte für die
richtige Steigung auf wenige Werte zusammen und streuen für jede andere. Der
Gipfel dieser Konzentration nennt die Steigung — an fünfzehn erzeugten
Gewinden auf 0,01 mm genau.

**Fünf Bedingungen, und die tragende ist die Gangtiefe.** Die Konzentration
allein trennt nicht: Ein Kantenzug aus 59 Kanten erreicht 0,73, weil bei so
wenigen Punkten jede Steigung zufällig passt, und der Mantel einer Kundendatei
erreicht 4,2 — er trägt eine echte Naht-Wendel über 22 Windungen bei konstantem
Radius. Erst die **Gangtiefe** macht daraus eine Aussage: Ein Regelgewinde hat
0,54 · Steigung unter dem Kamm, eine Naht hat keine Rille.

Nachgezählt, welche Bedingung welchen Fall aufhält, über den Referenzkorpus,
eine Kundendatei und drei kurze Bolzen: **In genau zwei Fällen lehnt eine
einzige Bedingung ab, und beide Male ist es die Rille.** Alles andere scheitert
an mehreren zugleich — Kammstreuung, Schärfe, Windungszahl und Konzentration
überlappen sich stark (44, 46, 42 und 33 Beteiligungen). Sie bleiben trotzdem:
Sie decken Fälle, die dieser Korpus nicht enthält, und sie sind billig. Aber
wer eine davon lockert, verändert wenig; wer die Rille lockert, meldet dem
Kunden ein Gewinde, wo keines ist.

Gemessen über fünf Größen, drei Längen und beide Richtungen, dazu der
Referenzkorpus, eine Kundendatei und neunzehn weitere Kundenmodelle
(3d-druck-11, 04.09.2026, bis 1,2 Millionen Dreiecke): **sechzehn von neunzehn
Gewinden gefunden, null Fehlalarme.** Was nicht gefunden wird, sind Gewinde
unter etwa sieben Windungen — bei fünf Millimetern Länge überwiegt der Auslauf,
und die Steigung ist nicht mehr abzulesen. Lieber nichts sagen als das Falsche
(§21).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.units import EPS_GEOM

_log = get_logger(__name__)

#: Ab welchem Knickwinkel eine Kante als scharf gilt, in Grad.
#:
#: Der Kamm eines gedruckten Gewindes knickt um sechzig Grad, die Facetten
#: eines glatten Zylinders um wenige. Fünfundzwanzig liegt weit von beidem.
SHARP_EDGE_LIMIT: Final = 25.0

#: Wie viele scharfe Kanten ein Zug mindestens hat, um überhaupt geprüft zu
#: werden.
#:
#: Ein Gewinde bringt tausende mit — das kürzeste gemessene (M8 mit 5 mm) noch 1471.
#: Der Rand einer Platte bringt vier. Die Grenze hält die teure Steigungssuche
#: von allem fern, was ohnehin keine Wendel sein kann.
MIN_CHAIN_EDGES: Final = 200

#: Der abgesuchte Steigungsbereich in Millimetern, und die Schrittweite.
#:
#: Nach oben weit genug, dass der Gipfel **nicht am Rand** liegt: Bei einer
#: Obergrenze von 3,0 mm meldete der Mantel einer Kundendatei 2,97 mm mit
#: Schärfe 5,7 — weitet man auf 6,0, wandert der Gipfel auf 5,37 und die
#: Schärfe fällt auf 4,2. Ein Gipfel am Rand ist kein Gipfel, sondern ein
#: abgeschnittener Hang. 6,0 mm deckt jedes metrische Regelgewinde bis M36.
PITCH_RANGE: Final = (0.3, 6.0)
PITCH_STEP: Final = 0.01

#: Wie stark der Gipfel seinen eigenen Untergrund überragen muss.
#:
#: Der Untergrund ist der Median über alle abgesuchten Steigungen — das Maß
#: prüft sich damit an sich selbst und altert nicht mit der Netzdichte.
#: Gemessen: echte Gewinde 3,4 bis 69,7; alles andere höchstens 4,2, und jener
#: eine Fall scheitert an der Gangtiefe.
MIN_SHARPNESS: Final = 3.0

#: Wie stark die Kantenpunkte für die beste Steigung zusammenfallen müssen.
#:
#: Nur um den Fall auszuschließen, in dem gar keine Periodizität da ist: Eine
#: gesenkte Platte kommt auf 0,000 und hat damit einen unendlichen Quotienten
#: aus Gipfel und Untergrund, ohne dass irgendetwas gefunden wäre. Das ist die
#: ganze Aufgabe dieser Zahl — geurteilt wird über :data:`MIN_SHARPNESS` und
#: :data:`GROOVE_RANGE`, und beide bleiben, wo sie sind.
#:
#: Sie stand zuerst bei 0,10 und wies damit ein M6-Innengewinde ab, dessen
#: Grundton bei 0,051 lag: In einer Bohrung sind die Kämme kürzer und die
#: Facettierung gröber, die Konzentration also schwächer als am Bolzen (0,394).
#: Gegengemessen über den Referenzkorpus und eine Kundendatei ändert 0,03
#: nichts — dort scheitert alles an der Schärfe oder an der Rille.
MIN_CONCENTRATION: Final = 0.03

#: Welchen Anteil des höchsten Gipfels ein Gipfel erreichen muss, um als
#: Grundton in Frage zu kommen.
#:
#: **Eine Wendel konzentriert nicht nur bei ihrer Steigung, sondern auch bei
#: p/2, p/3, p/4.** Nach einer vollen Windung wächst ``z`` um p, und damit ist
#: der Rest modulo p/n wieder derselbe. Vielfache dagegen konzentrieren nicht:
#: Bei 2p verteilen sich die Windungen auf zwei gegenüberliegende Phasen und
#: heben sich auf. Der Grundton ist deshalb der **größte** Gipfel der Familie,
#: nicht der höchste — an einem M8-Innengewinde lag p/2 bei 0,166 und die
#: richtige Steigung bei 0,132, und mit dem höchsten kam eine halbe Steigung
#: heraus, an der dann auch die Rille scheiterte.
#:
#: Gemessen über fünf Fälle liegt der Grundton bei 0,80 bis 1,00 des höchsten;
#: 0,70 lässt ihm Luft, ohne einem fremden Gipfel welche zu geben.
HARMONIC_SHARE: Final = 0.70

#: Wie viele Windungen ein Gewinde mindestens hat.
#:
#: Darunter sind es ein paar Ringe und keine Wendel. Gemessen liegt das
#: kürzeste erkannte Gewinde bei 7,5 Windungen, die falschen Treffer der
#: 5-mm-Bolzen bei 1,5.
MIN_TURNS: Final = 5.0

#: In welchem Vielfachen der Steigung die Rille unter dem Kamm liegen darf.
#:
#: Ein metrisches Regelgewinde hat 0,54 · Steigung Gangtiefe — das ist die
#: Norm und keine abgelesene Zahl. Gemessen an fünfzehn erzeugten Gewinden
#: kommen 0,553 bis 0,873 heraus; das Fenster, in dem gemessen wird, nimmt am
#: oberen Ende etwas Auslauf mit. Alles, was keine Rille hat oder eine viel
#: tiefere, ist kein Gewinde: Der Mantel der Kundendatei liegt bei 2,3 bis 2,9,
#: eine gesenkte Bohrung bei 1,7.
GROOVE_RANGE: Final = (0.40, 1.20)

#: Wie weit der Kamm streuen darf, als Anteil seines eigenen Radius.
#:
#: Eine Vorprüfung, kein Urteil: Sie hält die Steigungssuche von Kantenzügen
#: fern, die gar nicht auf einem Zylinder liegen. Echte Gewindekämme streuen
#: 0,090 bis 0,138, die verworfenen Züge einer Kundendatei 0,49 bis 0,71.
CREST_SPREAD_LIMIT: Final = 0.25


@dataclass(frozen=True)
class Helix:
    """Eine gefundene Wendel — Achse, Steigung und die Rille darunter."""

    axis: tuple[float, float, float]
    centre: tuple[float, float, float]
    pitch: float
    crest_radius: float
    depth: float
    """Die Gangtiefe in Millimetern, vom Kamm bis zum Grund."""
    length: float
    turns: float
    sharpness: float
    internal: bool
    """Ob das Material **außerhalb** des Kamms liegt — dann ein Innengewinde."""
    face_indices: tuple[int, ...]

    @property
    def diameter(self) -> float:
        """Der Nenndurchmesser: außen der Kamm, innen der Grund."""
        radius = self.crest_radius + self.depth if self.internal else self.crest_radius
        return 2.0 * radius


def find_helices(mesh: MeshData) -> list[Helix]:
    """Jede Wendel des Körpers, gemessen an seinen scharfen Kanten.

    Gibt eine leere Liste zurück, wenn keine da ist — der übliche Fall, und er
    kostet nur die Kantensuche.
    """
    body = mesh.raw
    if len(body.faces) < MIN_CHAIN_EDGES:
        return []
    found: list[Helix] = []
    for chain in _sharp_chains(body):
        helix = _helix_of(body, chain)
        if helix is not None:
            found.append(helix)
    if found:
        _log.info("found %d helices", len(found))
    return found


def _sharp_chains(body: trimesh.Trimesh) -> list[NDArray[np.float64]]:
    """Die scharfen Kanten, über gemeinsame Ecken zu Zügen verbunden.

    **Zusammenhängend und nicht am Stück**: Der Kamm eines Gewindes ist *ein*
    Zug, der Rand einer Platte ein anderer. Über den ganzen Körper gemittelt
    überstimmt die Platte das Gewinde — gemessen an einem M5 auf einer Platte
    200 auf 200 fand die Achse aus allen scharfen Kanten die falsche Steigung,
    aus dem Zug allein die richtige (0,80 mm, Schärfe 15,8).
    """
    angles = np.degrees(body.face_adjacency_angles)
    edges = body.face_adjacency_edges[angles > SHARP_EDGE_LIMIT]
    if len(edges) < MIN_CHAIN_EDGES:
        return []
    labels = trimesh.graph.connected_component_labels(  # type: ignore[no-untyped-call]
        edges, node_count=len(body.vertices)
    )
    belongs = labels[edges[:, 0]]
    chains: list[NDArray[np.float64]] = []
    for label in np.unique(belongs):
        mine = belongs == label
        if int(mine.sum()) >= MIN_CHAIN_EDGES:
            chains.append(np.asarray(body.vertices[edges[mine]].mean(axis=1), dtype=float))
    return chains


def _helix_of(body: trimesh.Trimesh, chain: NDArray[np.float64]) -> Helix | None:
    """Prüft einen Kantenzug auf alle vier Bedingungen."""
    centre = chain.mean(axis=0)
    offset = chain - centre
    _, _, directions = np.linalg.svd(offset, full_matrices=False)
    axis = np.asarray(directions[0], dtype=float)

    along = offset @ axis
    across = offset - np.outer(along, axis)
    radius = np.linalg.norm(across, axis=1)
    mean_radius = float(radius.mean())
    if mean_radius <= 0.0 or float(radius.std()) / mean_radius > CREST_SPREAD_LIMIT:
        return None

    pitch, concentration, sharpness = _best_pitch(offset, axis, along)
    if concentration < MIN_CONCENTRATION or sharpness < MIN_SHARPNESS:
        return None
    low = float(along.min())
    high = float(along.max())
    span = high - low
    turns = span / pitch
    if turns < MIN_TURNS:
        return None

    groove = _groove(body, centre, axis, low, high, radius, pitch)
    if groove is None:
        return None
    crest, depth, internal = groove

    return Helix(
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        pitch=pitch,
        crest_radius=crest,
        depth=depth,
        length=span,
        turns=turns,
        sharpness=sharpness,
        internal=internal,
        face_indices=_faces_in(
            body, centre, axis, low - pitch, high + pitch, crest, depth, internal
        ),
    )


def _best_pitch(
    offset: NDArray[np.float64], axis: NDArray[np.float64], along: NDArray[np.float64]
) -> tuple[float, float, float]:
    """Der Grundton der Konzentration, und wie sehr er heraussticht.

    Gibt Steigung, Konzentration und Schärfe zurück — letztere als Gipfel
    geteilt durch den Median über den ganzen Bereich. Gewählt wird der
    **größte** Gipfel, der :data:`HARMONIC_SHARE` des höchsten erreicht; die
    Begründung steht dort.
    """
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = np.cross(axis, helper)
    first /= np.linalg.norm(first)
    second = np.cross(axis, first)
    angle = np.arctan2(offset @ second, offset @ first)

    pitches = np.arange(PITCH_RANGE[0], PITCH_RANGE[1] + PITCH_STEP, PITCH_STEP)
    rest = (along[None, :] - pitches[:, None] * angle[None, :] / (2 * math.pi)) % pitches[:, None]
    phase = 2 * math.pi * rest / pitches[:, None]
    strength = np.hypot(np.cos(phase).mean(axis=1), np.sin(phase).mean(axis=1))

    highest = float(strength.max())
    rises = np.r_[True, strength[1:] >= strength[:-1]]
    falls = np.r_[strength[:-1] >= strength[1:], True]
    candidates = np.flatnonzero(rises & falls & (strength >= HARMONIC_SHARE * highest))
    best = int(candidates[-1]) if len(candidates) else int(strength.argmax())

    background = float(np.median(strength))
    peak = float(strength[best])
    sharpness = peak / background if background > 1e-9 else float("inf")
    return float(pitches[best]), peak, sharpness


def _groove(
    body: trimesh.Trimesh,
    centre: NDArray[np.float64],
    axis: NDArray[np.float64],
    low: float,
    high: float,
    crest_radii: NDArray[np.float64],
    pitch: float,
) -> tuple[float, float, bool] | None:
    """Der Kamm und die Rille darunter, in beide Richtungen gesucht.

    Bei einem Außengewinde liegt der Grund **innerhalb** des Kamms, bei einem
    Innengewinde außerhalb — dieselbe Rille, gespiegelt. Gemessen wird deshalb
    beides, und es gilt, was in das Fenster aus :data:`GROOVE_RANGE` fällt.
    Passt keines, ist der Zug kein Gewindekamm.

    **Der Kamm ist nicht dieselbe Zahl für beide Richtungen**, und daran ist
    dieser Schritt zuerst gescheitert: Ein Kantenzug enthält Kamm *und* Grund,
    und welches Ende davon der Kamm ist, hängt daran, wo das Material liegt.
    Für einen Bolzen ist es das äußere, für eine Gewindebohrung das innere.
    Mit dem äußeren Ende für beide gemessen kam am Innengewinde eine Rille von
    0,01 · Steigung heraus statt 0,54 — die Steigung selbst stand da längst auf
    0,01 mm genau.

    **Und die Richtung wird bestimmt, nicht durchprobiert.** Der erste Anlauf
    maß beides und nahm, was passte; damit hatte jeder Kantenzug zwei Chancen
    statt einer, und der Mantel einer Kundendatei ging als Innengewinde durch.
    Wo das Material liegt, sagen die Normalen (:func:`_material_outside`) —
    gemessen +0,69 an zwei Bolzen, -0,29 an zwei Gewindebohrungen.
    """
    offset = body.triangles_center - centre
    along = offset @ axis
    radius = np.linalg.norm(offset - np.outer(along, axis), axis=1)
    inside_span = (along >= low) & (along <= high)

    internal = not _material_outside(body, centre, axis, low, high, crest_radii, pitch)
    crest = float(np.percentile(crest_radii, 10 if internal else 90))
    if internal:
        near = inside_span & (radius >= crest - 0.3 * pitch) & (radius <= crest + 3.0 * pitch)
        if int(near.sum()) < 20:
            return None
        depth = float(np.percentile(radius[near], 95)) - crest
    else:
        near = inside_span & (radius <= crest + 0.3 * pitch) & (radius >= crest - 3.0 * pitch)
        if int(near.sum()) < 20:
            return None
        depth = crest - float(np.percentile(radius[near], 5))
    if GROOVE_RANGE[0] <= depth / pitch <= GROOVE_RANGE[1]:
        return crest, depth, internal
    return None


def _material_outside(
    body: trimesh.Trimesh,
    centre: NDArray[np.float64],
    axis: NDArray[np.float64],
    low: float,
    high: float,
    crest_radii: NDArray[np.float64],
    pitch: float,
) -> bool:
    """Zeigt die Oberfläche um den Kantenzug von der Achse weg?

    Bei einem Bolzen tut sie das — das Material liegt innen, die Normalen
    zeigen nach außen. Bei einer Gewindebohrung ist es umgekehrt. Gemittelt
    über die Dreiecke rund um den Zug ist das kein knapper Unterschied:
    **+0,69 gegen -0,29** an je zwei gemessenen Fällen.

    Der Weg über ``trimesh.contains`` wäre direkter und steht hier trotzdem
    nicht: Er verlangt ``rtree``, und das ist weder installiert noch in langen
    Läufen zuverlässig.
    """
    offset = body.triangles_center - centre
    along = offset @ axis
    across = offset - np.outer(along, axis)
    radius = np.linalg.norm(across, axis=1)
    near = (
        (along >= low)
        & (along <= high)
        & (radius >= float(crest_radii.min()) - 0.3 * pitch)
        & (radius <= float(crest_radii.max()) + 0.3 * pitch)
        & (radius > EPS_GEOM)
    )
    if int(near.sum()) < 20:
        return True
    outward = across[near] / radius[near][:, None]
    return float((body.face_normals[near] * outward).sum(axis=1).mean()) > 0.0


def _faces_in(
    body: trimesh.Trimesh,
    centre: NDArray[np.float64],
    axis: NDArray[np.float64],
    low: float,
    high: float,
    crest: float,
    depth: float,
    internal: bool,
) -> tuple[int, ...]:
    """Die Dreiecke, die auf der Wendel liegen — Kamm, Flanken und Grund.

    Sie sind der Grund, aus dem die Unterdrückung überhaupt zielen kann: Was
    hier drinsteht, gehört zum Gewinde, und was eine Einpassung darauf findet,
    steht daneben statt darin.

    **Eine Steigung Zugabe an beiden Enden**, denn der Auslauf steht über dem
    letzten Kamm: Ohne sie blieb an M6 eine Kugel und an M8 ein Kegel übrig,
    beide an der Spitze des Bolzens.

    **Eine Hülle und kein Zylinder.** Der Unterschied ist gemessen: Eine volle
    Zylinderhülle verschluckte eine Querbohrung durch denselben Bolzen, die
    1,67 mm unter dem Gewindegrund liegt (3d-druck-4d, 04.09.2026). Was
    innerhalb des Grundes liegt, gehört dem Kunden.
    """
    offset = body.triangles_center - centre
    along = offset @ axis
    radius = np.linalg.norm(offset - np.outer(along, axis), axis=1)
    if internal:
        shell = (radius >= crest - 0.1 * depth) & (radius <= crest + depth * 1.1)
    else:
        shell = (radius <= crest + 0.1 * depth) & (radius >= crest - depth * 1.1)
    inside = (along >= low) & (along <= high) & shell
    return tuple(int(index) for index in np.flatnonzero(inside))
