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
Gewinden gefunden, null Fehlalarme.** Kurze breite Gewinde bekommen zusätzlich
einen Nachweis an einzeln verfolgten Kammkanten. Zwei vollständige Umläufe,
konstanter Radius, eine punktweise belegte Wendel und die Gangtiefe müssen
zusammenpassen; ein unklarer Auslauf bleibt ohne Gewindeauskunft (§21).

**Gemessen wird an den Kanten** (P2.5, :func:`_measured_helix`). Das Spektrum
findet ein Gewinde und schätzt seine Steigung; Händigkeit, Vorschub und
Gangzahl liest danach der Kantenleser, mit denselben Fragen wie der exakte
Leser (``brep.thread``): das Vorzeichen der Steigung jeder windenden Kante,
der Vorschub, den die meisten Kanten tragen, die Wendeln nach Radius und
Phase und die Gangzahl aus ihrer Periodizität (:func:`starts_from_periodicity`,
eine Regel für beide Kerne). Die Rille prüft er gegen
:data:`MEASURED_GROOVE_RANGE` — er misst den Abstand zweier Wendeln und nicht
Perzentile der Dreiecksmitten. Nur wo er nicht messen kann, bleibt die
Schätzung des Spektrums, und deren Händigkeit heißt ``fit``.

Abgenommen an Netzen verschiedener Vernetzung und an echten gedruckten
Gewinden aus ``F:\\3D Dateien`` (23.09.2026): 35 von 35 Referenzfällen (vorher
27) — gedruckte Profile rechts und gespiegelt bis 2,5 Umläufe, gekippt, innen,
die STEP-Referenzen in zwei Sehnenhöhen, zweigängig —, dazu die Behälter und
Deckel des Gewürzregals, Düsenbox, Poolfontäne und die Schraubfüße eines
Besteckkorbs: jedes gemessen, mit Vorschub auf 10⁻⁴ und ohne Fehlalarm im
übrigen Korpus.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.units import EPS_GEOM, MAX_FACET_SAG, positive_axis

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

#: Höchstens 2 MiB je Steigungs-Zwischenmatrix, statt aller Steigungen auf einmal.
#: Ganze Punktzeilen bewahren die Reihenfolge der Mittelwertbildung. Ist schon
#: eine Zeile größer, bleibt nur deren linearer Speicherbedarf übrig.
PITCH_BLOCK_VALUES: Final = 262_144

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

#: Ein einzeln verfolgter Kamm darf kürzer sein als das gemischte Spektrum.
#: Zwei vollständige Wiederholungen und höchstens eine Facettenabweichung
#: von der Wendel sind hier gemeinsam nötig; die Spektrumsgrenze bleibt bestehen.
MIN_RESOLVED_TURNS: Final = 2.0

#: Wie viele Umläufe der Kantenleser mindestens belegt sehen muss
#: (:func:`_measured_helix`) — einen, wie der exakte Leser
#: (``brep.thread.MIN_TURNS_FOR_PITCH``): Unter einer vollen Umdrehung ist
#: eine Steigung eine Vermutung, darüber eine Messung. Der Kantenleser prüft
#: dazu Schar, Abweichung und Rille; die zwei Umläufe von
#: :data:`MIN_RESOLVED_TURNS` gelten dem Spektrum. Gemessen über 516 Körper aus
#: ``F:\3D Dateien`` und dem Referenzkorpus (23.09.2026): Zwischen einem und
#: zwei Umläufen lagen nur echte Gewinde — die Schraubfüße eines Besteckkorbs
#: mit zwei Umläufen, die überdeckt gezählt 1,99 ergeben.
MIN_MEASURED_TURNS: Final = 1.0

#: In welchem Vielfachen der Steigung die Rille unter dem Kamm liegen darf.
#:
#: Ein metrisches Regelgewinde hat 0,54 · Steigung Gangtiefe — das ist die
#: Norm und keine abgelesene Zahl. Gemessen an fünfzehn erzeugten Gewinden
#: kommen 0,553 bis 0,873 heraus; das Fenster, in dem gemessen wird, nimmt am
#: oberen Ende etwas Auslauf mit. Alles, was keine Rille hat oder eine viel
#: tiefere, ist kein Gewinde: Der Mantel der Kundendatei liegt bei 2,3 bis 2,9,
#: eine gesenkte Bohrung bei 1,7.
GROOVE_RANGE: Final = (0.40, 1.20)

#: Dasselbe Fenster für die zwei Leser, die **messen** statt zu schätzen: den
#: Kantenleser am Netz (:func:`_measured_helix`) und den exakten Kern
#: (``brep.thread.read_thread``). Oben dieselbe Grenze. Unten ein Fünftel
#: statt zwei Fünftel: Die untere Grenze von :data:`GROOVE_RANGE` gilt einer
#: Tiefe aus Perzentilen der Dreiecksmitten, und dort trennt sie einen
#: Fehltreffer. Gemessen wird hier dagegen der Abstand zweier Wendeln, und
#: eine Naht ohne Rille hat nur eine. Über alle 176 Dateien aus
#: ``F:\3D Dateien`` und den Referenzkorpus lag jeder Kandidat unter 0,40
#: auf einem echten Gewinde (23.09.2026): die Deckel des Gewürzregals bei
#: 0,399, die Schraubfüße eines Besteckkorbs bei 0,315 und 0,242 —
#: Behälter- und Lampengewinde sind flach, und kein metrisches Maß sagt etwas
#: über sie. Darunter liegt nichts, was gemessen wäre.
MEASURED_GROOVE_RANGE: Final = (0.20, 1.20)

#: Wie weit der Kamm streuen darf, als Anteil seines eigenen Radius.
#:
#: Eine Vorprüfung, kein Urteil: Sie hält die Steigungssuche von Kantenzügen
#: fern, die gar nicht auf einem Zylinder liegen. Echte Gewindekämme streuen
#: 0,090 bis 0,138, die verworfenen Züge einer Kundendatei 0,49 bis 0,71.
CREST_SPREAD_LIMIT: Final = 0.25

#: Wie nah zwei Wendeln in der Phase liegen dürfen, um dieselbe zu sein — als
#: Anteil am Vorschub. **Eine Zahl für beide Leser:** Der exakte Kern fragt
#: sie von hier (``brep.thread._same_helices``), und
#: ``tests/test_shared_constants.py`` verbietet eine zweite Definition. Zwei
#: Kanten eines flachen Kamms liegen 0,30 Vorschub auseinander, zwei Stücke
#: einer Wendel im Rechenrauschen.
PHASE_TOLERANCE: Final = 0.03

#: Wie weit die Steigung einer Kante vom gemeinsamen Vorschub abliegen darf,
#: um zu derselben Wendelschar zu gehören — als Anteil am Vorschub. Eine Kante
#: auf einer Wendel trägt deren Vorschub genau: Zwei Punkte darauf liegen um
#: ``Vorschub · Δθ / 2π`` auseinander, gleich wie fein vernetzt ist. Was um zwei
#: Prozent daneben liegt, ist keine Kante derselben Wendel.
LEAD_AGREEMENT: Final = 0.02

#: Welcher Anteil der windenden Kanten — nach ihrem Winkel gewichtet — Richtung
#: und Vorschub der Schar teilen muss. Neun Zehntel: Ein Gewinde besteht aus
#: nichts anderem, eine zufällige Kette aus scharfen Kanten nie.
LEAD_SHARE: Final = 0.9

#: Wie weit eine Kante mindestens um die Achse drehen muss, um überhaupt zu
#: winden, in Radiant. Eine Rechengrenze gegen die Division durch null an
#: achsparallelen Kanten, keine Geometrietoleranz — deren Steigung fällt
#: ohnehin an :data:`LEAD_AGREEMENT`.
TURN_FLOOR: Final = 1e-9


def phase_gap(one: float, other: float) -> float:
    """Abstand zweier Phasen auf dem Kreis der Länge 1."""
    gap = abs(one - other) % 1.0
    return min(gap, 1.0 - gap)


def starts_from_periodicity(
    helices: Sequence[tuple[float, float]], *, radius_tolerance: float
) -> int:
    """Die Gangzahl n, unter der die Menge (Radius, Phase) periodisch ist.

    Ein n-gängiges Gewinde wiederholt **alle** seine Wendeln — Kamm- wie
    Fußkanten, auch die beiden Kanten eines flachen Kamms — nach einer
    Verschiebung um 1/n des Vorschubs. Nur die Kammphasen zu zählen trägt
    nicht: Ein flacher Kamm hat zwei Kanten je Gang, und deren Abstände sind
    nicht gleichmäßig (gemessen am zweigängigen Referenzkörper: vier
    Kammkanten mit Abständen 0,35/0,15/0,35/0,15 — Gangzahl fälschlich 1).
    Geprüft wird von der größten möglichen Gangzahl abwärts; 1 ist der
    Rückfall, wenn keine Verschiebung die Menge auf sich selbst abbildet.

    **Eine Regel für beide Kerne** (P2.5): Der exakte Leser
    (``brep.thread.starts_from_periodicity``) fragt hier, der Netzleser auch
    — mit der Radiustoleranz seiner Belege: Am exakten Körper liegen die
    Kanten auf ihrem Zylinder, am Netz bis zur Sehnenhöhe daneben.
    """
    entries = list(helices)
    for count in range(len(entries), 1, -1):
        shift = 1.0 / count
        if all(
            any(
                abs(radius - other_radius) <= radius_tolerance
                and phase_gap(phase + shift, other_phase) <= PHASE_TOLERANCE
                for other_radius, other_phase in entries
            )
            for radius, phase in entries
        ):
            return count
    return 1


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
    handedness: str = "right"
    """``right`` oder ``left``.

    Mit ``measured`` am Vorzeichen der Steigung jeder windenden Kante gemessen
    (:func:`_slope_reading`), sonst am Vorzeichen der Konzentration (B1,
    P2.5). Bis zum 20.09.2026 setzte die Konzentration ``z - p·θ/2π`` den
    Rechtsgang voraus: Die Spiegelung desselben Bolzens ergab **null**
    Wendeln, und der Netz-Zwilling eines Linksgewindes sagte „kein Gewinde“,
    während der exakte es maß.
    """
    lead: float = 0.0
    """Der Vorschub je Umdrehung — mit ``measured`` gemessen, sonst null."""
    starts: int = 1
    """Die Gangzahl — mit ``measured`` aus der Periodizität aller Wendeln."""
    measured: bool = False
    """Ob Händigkeit, Vorschub und Gangzahl an den Kanten gemessen sind
    (:func:`_slope_reading`) und nicht aus dem Gipfel des Spektrums geschätzt."""
    uncertainty: float | None = None
    """Die größte Abweichung einer Kante von ihrer Wendel in mm — nur mit ``measured``."""

    @property
    def diameter(self) -> float:
        """Der Nenndurchmesser: außen der Kamm, innen der Grund."""
        radius = self.crest_radius + self.depth if self.internal else self.crest_radius
        return 2.0 * radius


def find_helices(
    mesh: MeshData, *, check_cancelled: Callable[[], None] | None = None
) -> list[Helix]:
    """Jede Wendel des Körpers, gemessen an seinen scharfen Kanten.

    Gibt eine leere Liste zurück, wenn keine da ist — der übliche Fall, und er
    kostet nur die Kantensuche.
    """
    if check_cancelled is not None:
        check_cancelled()
    body = mesh.raw
    if len(body.faces) < MIN_CHAIN_EDGES:
        return []
    found: list[Helix] = []
    for edges in _sharp_chain_edges(body, check_cancelled=check_cancelled):
        if check_cancelled is not None:
            check_cancelled()
        chain = np.asarray(body.vertices[edges].mean(axis=1), dtype=float)
        helix = _helix_of(body, chain, check_cancelled=check_cancelled)
        if helix is None:
            helix = _resolved_helix(body, edges, check_cancelled=check_cancelled)
        # **Gemessen wird an den Kanten, geschätzt am Spektrum** (P2.5). Wo
        # die Kanten eine Wendelschar belegen, gelten ihre Händigkeit, ihr
        # Vorschub und ihre Gangzahl; sonst bleibt, was das Spektrum fand.
        measured = _measured_helix(body, edges, hint=helix, check_cancelled=check_cancelled)
        if measured is not None:
            found.append(measured)
        elif helix is not None and _winds_around(body, edges, helix):
            found.append(helix)
    if check_cancelled is not None:
        check_cancelled()
    if found:
        _log.info("found %d helices", len(found))
    return found


def _winds_around(body: trimesh.Trimesh, edges: NDArray[np.int64], helix: Helix) -> bool:
    """Ob sich der Zug um die Achse des Spektrums **windet** — mit einem Vorschub.

    Das Spektrum misst, wie gut die Punkte eines Zugs auf eine Periode fallen,
    und das tun auch Punkte, die gar nicht wendeln: Die Kanten axialer Rillen
    um einen Griff sind Geraden längs der Achse, ihre Ecken liegen im Takt
    der Vernetzung, und das Spektrum fand darin ein Linksgewinde mit Teilung
    0,6 und Schärfe 15,6 — am Griff, den ``apply_texture`` selbst berippt
    (23.09.2026, am Stand davor genauso). Um die leicht gekippte Achse des
    Spektrums steigt dabei jede Kante ein wenig; das allein belegt nichts.

    Belegt ist eine Wendel, wenn der Kantenleser an ihr eine Schar findet:
    windende Kanten mit einer Richtung und einem Vorschub, die
    :data:`LEAD_SHARE` des Winkels tragen (:func:`_slope_reading`). Die
    übrigen Tore des Kantenlesers — Umläufe, Abweichung, Rille — muss die
    Schätzung des Spektrums nicht bestehen; sonst wäre sie gemessen.
    """
    return (
        _slope_reading(
            body, edges, np.asarray(helix.axis, dtype=float), np.asarray(helix.centre, dtype=float)
        )
        is not None
    )


def _sharp_chains(
    body: trimesh.Trimesh, *, check_cancelled: Callable[[], None] | None = None
) -> list[NDArray[np.float64]]:
    """Die scharfen Kanten, über gemeinsame Ecken zu Zügen verbunden.

    **Zusammenhängend und nicht am Stück**: Der Kamm eines Gewindes ist *ein*
    Zug, der Rand einer Platte ein anderer. Über den ganzen Körper gemittelt
    überstimmt die Platte das Gewinde — gemessen an einem M5 auf einer Platte
    200 auf 200 fand die Achse aus allen scharfen Kanten die falsche Steigung,
    aus dem Zug allein die richtige (0,80 mm, Schärfe 15,8).
    """
    return [
        np.asarray(body.vertices[edges].mean(axis=1), dtype=float)
        for edges in _sharp_chain_edges(body, check_cancelled=check_cancelled)
    ]


def _sharp_chain_edges(
    body: trimesh.Trimesh, *, check_cancelled: Callable[[], None] | None = None
) -> list[NDArray[np.int64]]:
    """Bewahrt die Kantenverbindungen, damit ein Kamm einzeln verfolgbar bleibt."""
    angles = np.degrees(body.face_adjacency_angles)
    edges = body.face_adjacency_edges[angles > SHARP_EDGE_LIMIT]
    if check_cancelled is not None:
        check_cancelled()
    if len(edges) < MIN_CHAIN_EDGES:
        return []
    labels = trimesh.graph.connected_component_labels(  # type: ignore[no-untyped-call]
        edges, node_count=len(body.vertices)
    )
    belongs = labels[edges[:, 0]]
    chains: list[NDArray[np.int64]] = []
    for label in np.unique(belongs):
        if check_cancelled is not None:
            check_cancelled()
        mine = belongs == label
        if int(mine.sum()) >= MIN_CHAIN_EDGES:
            chains.append(np.asarray(edges[mine], dtype=np.int64))
    return chains


def _candidate_axes(
    body: trimesh.Trimesh, edges: NDArray[np.int64]
) -> tuple[NDArray[np.float64], NDArray[np.float64], list[NDArray[np.float64]]]:
    """Mitte, lokale Punkte und die Achsen, um die sich ein Zug winden könnte.

    Die drei Hauptachsen der Punktwolke und die Normalen der drei größten
    angrenzenden Ebenen: Bei einem breiten kurzen Gewinde zeigt die längste
    Hauptachse quer zur Wendel, die Stirnfläche aber nicht.
    """
    vertex_ids = np.unique(edges)
    points = np.asarray(body.vertices[vertex_ids], dtype=float)
    origin = points.mean(axis=0)
    local = points - origin
    _, _, principal = np.linalg.svd(local, full_matrices=False)
    candidates = list(principal)
    touching = np.zeros(len(body.vertices), dtype=bool)
    touching[vertex_ids] = True
    # Welche Facetten den Zug berühren, für alle auf einmal: Die Schleife fragte
    # jede Facette einzeln, größte zuerst, und lief an einem Körper, dessen Zug
    # keine der großen berührt, durch Tausende — am Drachen aus TripoSG 0,3 s
    # für vier kleine Züge (23.09.2026). Dieselbe Folge, dieselbe Auswahl.
    facets = body.facets
    facet_touches = np.zeros(len(facets), dtype=bool)
    if len(facets):
        members = np.concatenate(facets)
        owners = np.repeat(np.arange(len(facets)), [len(facet) for facet in facets])
        facet_touches[owners[touching[np.asarray(body.faces)[members]].any(axis=1)]] = True
    added = 0
    order = np.argsort(body.facets_area)[::-1]
    for index in order[facet_touches[order]]:
        normal = np.asarray(body.facets_normal[index], dtype=float)
        # Flächenlose Nachbardreiecke können eine Facette ohne Richtung bilden.
        if float(np.linalg.norm(normal)) <= EPS_GEOM:
            continue
        if any(abs(float(normal @ other)) > 1.0 - EPS_GEOM for other in candidates):
            continue
        candidates.append(normal)
        added += 1
        if added >= 3:
            break
    return origin, local, candidates


def _resolved_helix(
    body: trimesh.Trimesh,
    edges: NDArray[np.int64],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> Helix | None:
    """Belegt kurze Wendelzüge getrennt von Grund, zweiter Flanke und Auslauf.

    Bei einem breiten kurzen Gewinde zeigt die längste Hauptachse quer zur
    Wendel. Die Normalen der drei größten angrenzenden Ebenen ergänzen deshalb
    die drei Hauptachsen. Jede Richtung muss danach einen zylindrischen Kamm,
    eine zusammenhängende Wendel und deren echte Gangtiefe nachweisen.
    """
    from app.core.perceive.features import _fit_circle, _plane_basis

    origin, local, candidates = _candidate_axes(body, edges)

    best: Helix | None = None
    for candidate in candidates:
        if check_cancelled is not None:
            check_cancelled()
        axis = np.asarray(positive_axis(tuple(float(value) for value in candidate)), dtype=float)
        first, second = _plane_basis(axis)
        flat = np.column_stack((local @ first, local @ second))
        initial, _ = _fit_circle(flat)
        distances = np.linalg.norm(flat - initial, axis=1)
        mean_radius = float(distances.mean())
        if mean_radius <= EPS_GEOM or float(distances.std()) / mean_radius > CREST_SPREAD_LIMIT:
            continue
        for quantile in (0.1, 0.9):
            centre_2d = initial.copy()
            # Vier lokale Ausgleichsschritte lösen die beiden Radiusbänder.
            # Die spätere Wendelprüfung entscheidet, ob die Näherung genügt.
            for _ in range(4):
                distances = np.linalg.norm(flat - centre_2d, axis=1)
                selected = abs(distances - np.quantile(distances, quantile)) <= MAX_FACET_SAG
                if int(selected.sum()) < 3:
                    break
                centre_2d, radius = _fit_circle(flat[selected])
            else:
                centre = origin + first * centre_2d[0] + second * centre_2d[1]
                result = _resolved_crest(
                    body, edges, centre, axis, radius, check_cancelled=check_cancelled
                )
                if result is not None and (best is None or result.length > best.length):
                    best = result
    return best


def _resolved_crest(
    body: trimesh.Trimesh,
    edges: NDArray[np.int64],
    centre: NDArray[np.float64],
    axis: NDArray[np.float64],
    radius: float,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> Helix | None:
    """Prüft zusammenhängende scharfe Kanten auf konstanten Radius und Steigung."""
    relative = np.asarray(body.vertices, dtype=float) - centre
    along = relative @ axis
    across = relative - np.outer(along, axis)
    radii = np.linalg.norm(across, axis=1)
    edge_across = across[edges]
    angle = np.arctan2(
        np.cross(edge_across[:, 0], edge_across[:, 1]) @ axis,
        np.einsum("ij,ij->i", edge_across[:, 0], edge_across[:, 1]),
    )
    rise = along[edges[:, 1]] - along[edges[:, 0]]
    # **Steigen und Drehen gehören zusammen — in beide Richtungen.** Eine
    # Rechtswendel steigt mit dem Winkel, eine Linkswendel gegen ihn; beide
    # sind Kammkanten, keine Kante mit Höhe ohne Drehung ist es (B1).
    on_crest = (
        (abs(radii[edges] - radius) <= MAX_FACET_SAG).all(axis=1)
        & (abs(angle) > EPS_GEOM)
        & (abs(rise * angle) > EPS_GEOM)
    )
    kept = edges[on_crest]
    if len(kept) < MIN_CHAIN_EDGES:
        return None
    groups = trimesh.graph.connected_components(
        kept, nodes=np.unique(kept), min_len=MIN_CHAIN_EDGES, engine="scipy"
    )
    best: Helix | None = None
    for indices in groups:
        if check_cancelled is not None:
            check_cancelled()
        points = relative[indices]
        heights = along[indices]
        pitch, concentration, sharpness, handedness = _best_pitch(
            points, axis, heights, check_cancelled=check_cancelled
        )
        low, high = float(heights.min()), float(heights.max())
        if (high - low) / pitch < MIN_RESOLVED_TURNS or sharpness < MIN_SHARPNESS:
            continue
        # Die mittlere Konzentration allein ließe örtliche Abweichungen zu.
        # Der Rest jedes Punkts muss auf derselben Wendel liegen.
        from app.core.perceive.features import _plane_basis

        first, second = _plane_basis(axis)
        theta = np.arctan2(points @ second, points @ first)
        turn = 1.0 if handedness == "right" else -1.0
        phase = heights * (2.0 * math.pi / pitch) - turn * theta
        mean_phase = math.atan2(float(np.sin(phase).mean()), float(np.cos(phase).mean()))
        error = np.abs(np.angle(np.exp(1j * (phase - mean_phase)))) * pitch / (2.0 * math.pi)
        if concentration < MIN_CONCENTRATION or float(error.max()) > MAX_FACET_SAG:
            continue
        chain_radii = radii[np.unique(edges)]
        internal = not _material_outside(body, centre, axis, low, high, chain_radii, pitch)
        inner, outer = np.quantile(chain_radii, (0.1, 0.9))
        depth = float(outer - inner)
        if depth < GROOVE_RANGE[0] * pitch - EPS_GEOM or depth > GROOVE_RANGE[1] * pitch + EPS_GEOM:
            continue
        crest = float(inner if internal else outer)
        midpoint = centre + axis * (low + high) / 2.0
        result = Helix(
            axis=(float(axis[0]), float(axis[1]), float(axis[2])),
            centre=(float(midpoint[0]), float(midpoint[1]), float(midpoint[2])),
            pitch=pitch,
            crest_radius=crest,
            depth=depth,
            length=high - low,
            turns=(high - low) / pitch,
            sharpness=sharpness,
            internal=internal,
            face_indices=_faces_in(
                body, centre, axis, low - pitch, high + pitch, crest, depth, internal
            ),
            handedness=handedness,
        )
        if best is None or result.length > best.length:
            best = result
    return best


def _helix_of(
    body: trimesh.Trimesh,
    chain: NDArray[np.float64],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> Helix | None:
    """Prüft einen Kantenzug auf alle vier Bedingungen."""
    centre = chain.mean(axis=0)
    offset = chain - centre
    _, _, directions = np.linalg.svd(offset, full_matrices=False)
    axis = np.asarray(positive_axis(tuple(float(value) for value in directions[0])), dtype=float)

    along = offset @ axis
    across = offset - np.outer(along, axis)
    radius = np.linalg.norm(across, axis=1)
    mean_radius = float(radius.mean())
    if mean_radius <= 0.0 or float(radius.std()) / mean_radius > CREST_SPREAD_LIMIT:
        return None

    pitch, concentration, sharpness, handedness = _best_pitch(
        offset, axis, along, check_cancelled=check_cancelled
    )
    if concentration < MIN_CONCENTRATION or sharpness < MIN_SHARPNESS:
        return None
    low = float(along.min())
    high = float(along.max())
    span = high - low
    turns = span / pitch
    if turns < MIN_TURNS:
        return None

    groove = _groove(body, centre, axis, low, high, radius, pitch)
    if check_cancelled is not None:
        check_cancelled()
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
        handedness=handedness,
    )


@dataclass(frozen=True, slots=True)
class _Winding:
    """Eine gemessene Wendel des Netzes: Radius, Phase als Anteil am Vorschub, Umläufe."""

    radius: float
    phase: float
    turns: float
    deviation: float
    """Die größte Abweichung einer Kante von der Phase der Wendel, in mm."""


@dataclass(frozen=True, slots=True)
class _SlopeReading:
    """Was die Kanten eines Zugs über ihre Wendelschar sagen."""

    lead: float
    handedness: str
    windings: tuple[_Winding, ...]
    low: float
    high: float
    corners: tuple[NDArray[np.int64], ...] = ()
    """Je Wendel die Ecken ihrer Kanten — für den gemeinsamen Mittelpunkt
    (:func:`_shared_centre`)."""


def _weighted_median(values: NDArray[np.float64], weights: NDArray[np.float64]) -> float:
    """Der Wert, unter dem die Hälfte des Gewichts liegt."""
    return _weighted_quantile(values, weights, 0.5)


def _weighted_quantile(
    values: NDArray[np.float64], weights: NDArray[np.float64], share: float
) -> float:
    """Der Wert, unter dem ``share`` des Gewichts liegt."""
    order = np.argsort(values, kind="stable")
    cumulative = np.cumsum(weights[order])
    position = int(np.searchsorted(cumulative, cumulative[-1] * share))
    return float(values[order][min(position, len(values) - 1)])


def _circular_groups(phases: NDArray[np.float64]) -> list[NDArray[np.int64]]:
    """Phasen auf dem Kreis der Länge 1 zu Gruppen — getrennt, wo die Lücke größer ist als
    :data:`PHASE_TOLERANCE`; über die Naht bei null hinweg zusammengehalten."""
    order = np.argsort(phases, kind="stable")
    ordered = phases[order]
    gaps = np.diff(np.r_[ordered, ordered[0] + 1.0])
    cuts = np.flatnonzero(gaps > PHASE_TOLERANCE)
    if not len(cuts):
        return [order]
    # Die Gruppen beginnen hinter jeder Lücke; die über die Naht reicht vom
    # letzten Schnitt bis zum ersten.
    starts = (cuts + 1) % len(ordered)
    groups = []
    for number, start in enumerate(starts):
        end = starts[(number + 1) % len(starts)]
        span = np.r_[order[start:], order[:end]] if end <= start else order[start:end]
        groups.append(np.asarray(span, dtype=np.int64))
    return groups


def _lead_mode(leads: NDArray[np.float64], weights: NDArray[np.float64]) -> float:
    """Der Vorschub, den die meisten Kanten tragen — gewogen mit ihrem Winkel.

    Gesucht wird das Fenster der Breite :data:`LEAD_AGREEMENT` mit dem größten
    Gewicht; sein gewogener Median ist der Vorschub. Nicht der Median über alle:
    An einem gedruckten Gewinde sind die Fußkanten Schnitte der gedrehten Flanken
    mit dem Vieleck des Kerns und laufen im Zickzack um ihre Wendel (Steigungen
    0,2 und 1,8 bei Vorschub 1), und sie tragen die Hälfte der Kanten.
    """
    order = np.argsort(leads, kind="stable")
    ordered, heavy = leads[order], weights[order]
    cumulative = np.r_[0.0, np.cumsum(heavy)]
    ends = np.searchsorted(ordered, ordered * (1.0 + 2.0 * LEAD_AGREEMENT), side="right")
    covered = cumulative[ends] - cumulative[: len(ordered)]
    start = int(np.argmax(covered))
    window = slice(start, int(ends[start]))
    return _weighted_median(ordered[window], heavy[window])


def _slope_reading(
    body: trimesh.Trimesh,
    edges: NDArray[np.int64],
    axis: NDArray[np.float64],
    origin: NDArray[np.float64],
) -> _SlopeReading | None:
    """Vorschub, Händigkeit und Wendeln eines Zugs — an jeder Kante gemessen (P2.5).

    **Dieselbe Frage wie der exakte Leser, an Kanten statt an Kurven.** Zwei
    Punkte einer Wendel liegen um ``Vorschub · Δθ / 2π`` auseinander, gleich wie
    fein vernetzt ist: Das Vorzeichen von ``Δz / Δθ`` in der rechtshändigen
    Basis um die Achse ist die Händigkeit, und der Vorschub ist der Wert, den
    die meisten Kanten tragen (:func:`_lead_mode`). Gewogen wird mit dem
    Winkel, den eine Kante überstreicht.

    Das Spektrum (:func:`_best_pitch`) tut das nicht, und daran ist es am
    gedruckten Profil gescheitert: Ein abgeflachter Kamm trägt vier Wendeln je
    Gang — zwei Kammkanten, zwei Fußkanten —, fast gleich über die Periode
    verteilt, und im Mittel über ihre Phasen heben sie sich nahezu auf. Am
    Gewinde, das diese Anwendung selbst druckt (``build.threaded(6, 1, 8)``),
    stand der Gipfel deshalb bei 0,98 mm und links statt rechts (21.09.2026).

    **Zur Wendel gehört eine Kante, deren beide Enden dieselbe Phase tragen**
    — nicht dieselbe Steigung: Ein Zickzack um die Wendel bleibt in der Phase
    beisammen, auch wenn jede seiner Kanten schräger oder flacher steht. Die
    Kanten ordnen sich danach nach Radius und Phase zu Wendeln: Kamm- und
    Fußkanten, auch die zwei Kanten eines flachen Kamms. Aus ihnen kommen
    Gangzahl (:func:`starts_from_periodicity`), Kamm, Grund und Umläufe.
    """
    from app.core.perceive.features import _plane_basis

    vertices = np.asarray(body.vertices, dtype=float)
    ends = vertices[edges] - origin
    along = ends @ axis
    across = ends - along[..., None] * axis
    first, second = _plane_basis(axis)
    x, y = across @ first, across @ second
    theta = np.arctan2(y, x)
    radius = np.hypot(x, y)
    turn = (theta[:, 1] - theta[:, 0] + math.pi) % math.tau - math.pi
    rise = along[:, 1] - along[:, 0]
    winding = (
        (np.abs(turn) > TURN_FLOOR) & (np.abs(rise) > EPS_GEOM) & (radius.min(axis=1) > EPS_GEOM)
    )
    if not winding.any():
        return None
    weight = np.abs(turn[winding])
    total = float(weight.sum())
    slope = rise[winding] / turn[winding]
    right = float(weight[slope > 0.0].sum())
    # Die Schar muss unten :data:`LEAD_SHARE` des Winkels in **einer** Richtung
    # tragen, mit Vorschub und Phase. Wer das schon mit der Richtung allein
    # nicht schafft, schafft es danach erst recht nicht — dieselbe Antwort,
    # nur vor dem teuren Teil. An der Freiform aus den Leistungstests (ein Zug
    # mit 233 330 scharfen Kanten, kein Gewinde) kosteten sechs vollständige
    # Lesungen eine Sekunde der Gewindesuche (23.09.2026).
    if max(right, total - right) < LEAD_SHARE * total:
        return None
    handedness = "right" if right >= total - right else "left"
    sign = 1.0 if handedness == "right" else -1.0
    chosen = slope * sign > 0.0
    lead = _lead_mode(math.tau * np.abs(slope[chosen]), weight[chosen])
    if lead <= EPS_GEOM:
        return None
    candidates = np.flatnonzero(winding)[chosen]
    phase = ((along[candidates] - sign * lead * theta[candidates] / math.tau) / lead) % 1.0
    gap = np.abs(phase[:, 0] - phase[:, 1]) % 1.0
    steady = (np.minimum(gap, 1.0 - gap) <= PHASE_TOLERANCE) & (
        np.abs(radius[candidates, 0] - radius[candidates, 1]) <= MAX_FACET_SAG
    )
    if float(weight[chosen][steady].sum()) < LEAD_SHARE * total:
        return None
    selected = candidates[steady]
    radii = radius[selected].mean(axis=1)
    # Die Phase einer Kante ist die Mitte ihrer zwei Enden auf dem Kreis.
    ends_phase = phase[steady]
    phases = (
        np.arctan2(
            np.sin(math.tau * ends_phase).sum(axis=1), np.cos(math.tau * ends_phase).sum(axis=1)
        )
        / math.tau
    ) % 1.0
    windings: list[_Winding] = []
    corners: list[NDArray[np.int64]] = []
    # Erst nach Radius, dann nach Phase: Am Netz liegt eine Fußkante bis zur
    # Sehnenhöhe des Kerns neben ihrem Radius (``MAX_FACET_SAG``), und die zwei
    # Kanten eines flachen Kamms teilen den Radius, nicht die Phase.
    order = np.argsort(radii, kind="stable")
    breaks = np.flatnonzero(np.diff(radii[order]) > MAX_FACET_SAG) + 1
    for band in np.split(order, breaks):
        # Die Mitte der Achse kommt aus allen Kanten eines Radius, nicht aus
        # denen einer Wendel: Für den Kreis zählt der Radius, die Phase ist
        # gleich — und jede weggelassene Kante kostet ihn Bogen.
        corners.append(np.unique(edges[selected[band]]))
        for group in _circular_groups(phases[band]):
            for members in _dense_parts(band[group], phases, np.abs(turn[selected]), lead):
                centre, spread = _winding_spread(
                    ends_phase[members], np.abs(turn[selected[members]])
                )
                windings.append(
                    _Winding(
                        radius=float(radii[members].mean()),
                        phase=centre,
                        turns=_covered(along[selected[members]]) / lead,
                        deviation=spread * lead,
                    )
                )
    heights = along[selected]
    return _SlopeReading(
        lead=lead,
        handedness=handedness,
        windings=tuple(windings),
        low=float(heights.min()),
        high=float(heights.max()),
        corners=tuple(corners),
    )


def _circular_centre(phases: NDArray[np.float64]) -> float:
    """Die Mitte von Phasen auf dem Kreis der Länge 1."""
    angle = math.atan2(
        float(np.sin(math.tau * phases).sum()), float(np.cos(math.tau * phases).sum())
    )
    return (angle / math.tau) % 1.0


def _covered(heights: NDArray[np.float64]) -> float:
    """Wie viel Höhe die Kanten einer Wendel zusammen überdecken — jede Stelle einmal.

    **Nicht die Summe ihrer Winkel.** Die zwei Kanten eines flachen Kamms
    liegen enger beisammen, als eine Wendel breit sein darf, und bilden
    deshalb eine; ihre Winkel zusammengezählt, hatte die waagrechte Düse aus
    dem Korpus zwölf Umläufe statt sechs (23.09.2026). Die Vereinigung der
    Höhenbereiche zählt jede Stelle einmal und lässt Unterbrechungen aus.
    """
    low = heights.min(axis=1)
    high = heights.max(axis=1)
    order = np.argsort(low, kind="stable")
    low, high = low[order], high[order]
    reach = np.maximum.accumulate(high)
    starts = np.flatnonzero(np.r_[True, low[1:] > reach[:-1]])
    return float((np.maximum.reduceat(high, starts) - low[starts]).sum())


def _winding_spread(
    ends_phase: NDArray[np.float64], weights: NDArray[np.float64]
) -> tuple[float, float]:
    """Mitte und Abweichung einer Wendel in Phasen — die Abweichung für :data:`LEAD_SHARE`.

    **Nicht das Größte über alle Kanten.** Ein gedrucktes Gewinde läuft aus:
    Am Ende geht der Kamm in eine Fase über und entfernt sich stetig von
    seiner Wendel — an der waagrechten Düse aus dem Korpus bis 0,051 mm, bei
    0,0002 mm am Kamm daneben (23.09.2026). Dieselbe Regel wie beim Vorschub:
    Die Wendel ist, was :data:`LEAD_SHARE` ihres Winkels tragen, und so weit
    liegt sie höchstens neben ihren Kanten. Die Mitte kommt aus eben diesen
    Kanten, damit der Auslauf sie nicht verschiebt.
    """
    centre = _circular_centre(ends_phase)
    for _step in range(2):
        gap = np.abs(ends_phase - centre) % 1.0
        offset = np.minimum(gap, 1.0 - gap).max(axis=1)
        spread = _weighted_quantile(offset, weights, LEAD_SHARE)
        centre = _circular_centre(ends_phase[offset <= spread])
    gap = np.abs(ends_phase - centre) % 1.0
    offset = np.minimum(gap, 1.0 - gap).max(axis=1)
    return centre, _weighted_quantile(offset, weights, LEAD_SHARE)


def _dense_parts(
    group: NDArray[np.int64],
    phases: NDArray[np.float64],
    weights: NDArray[np.float64],
    lead: float,
) -> list[NDArray[np.int64]]:
    """Eine Phasengruppe, die zwei Wendeln trägt, als zwei — sonst unverändert.

    :func:`_circular_groups` trennt nur an Lücken, und ein paar Kanten
    zwischen zwei Wendeln überbrücken die Lücke: Der flache Grund der
    waagrechten Düse aus dem Korpus hat zwei Randwendeln mit je 1 630 Kanten,
    und rund neunzig Kanten mit Phasen dazwischen hielten sie als eine Gruppe
    mit 0,54 mm Abweichung zusammen (23.09.2026).

    Gewogen wird mit dem Winkel in Fächern von einer halben
    :data:`PHASE_TOLERANCE`. Dicht ist ein Fach mit mindestens dem Rest von
    :data:`LEAD_SHARE` des schwersten. Getrennt wird nur, wo zwei dichte
    Fächer weiter auseinander liegen, als eine Wendel breit sein darf
    (zweimal :data:`MAX_FACET_SAG`): Eine grob vernetzte Wendel verteilt ihre
    Kanten ungleich über benachbarte Fächer, und die bleiben eine. Jede Kante
    geht zum nächsten dichten Teil — was dazwischen lag, zählt dort als
    Ausreißer (:func:`_winding_spread`). Was weiter als eine Wendelbreite von
    jedem dichten Teil liegt, fällt heraus: Das ist ein Auslauf — der Kamm,
    der am Ende in eine Fase übergeht und sich stetig von seiner Wendel
    entfernt; an der Düsenbox 0,55 mm weit und mit 13 Prozent ihres Winkels.
    """
    if len(group) < 2:
        return [group]
    width = PHASE_TOLERANCE / 2.0
    relative = (phases[group] - phases[group[0]]) % 1.0
    bins = np.floor(relative / width).astype(np.int64)
    mass = np.bincount(bins, weights=weights[group])
    dense = np.flatnonzero(mass >= (1.0 - LEAD_SHARE) * float(mass.max()))
    reach = max(1, math.ceil(2.0 * MAX_FACET_SAG / lead / width))
    runs = np.split(dense, np.flatnonzero(np.diff(dense) > reach) + 1)
    low = np.array([float(run[0]) for run in runs])
    high = np.array([float(run[-1]) for run in runs])
    distance = np.maximum(low[None, :] - bins[:, None], 0.0) + np.maximum(
        bins[:, None] - high[None, :], 0.0
    )
    nearest = np.argmin(distance, axis=1)
    near = distance[np.arange(len(group)), nearest] <= reach
    return [
        group[near & (nearest == index)]
        for index in range(len(runs))
        if bool((near & (nearest == index)).any())
    ]


def _shared_centre(
    vertices: NDArray[np.float64],
    groups: Sequence[NDArray[np.int64]],
    axis: NDArray[np.float64],
    centre: NDArray[np.float64],
) -> NDArray[np.float64] | None:
    """Der gemeinsame Mittelpunkt aller Wendeln: je Wendel ein Kreis, alle um eine Achse.

    Linear wie der Kreis nach Kåsa, nur mit einem freien Glied je Wendel:
    ``x² + y² = 2a·x + 2b·y + c_k``. Gerechnet um die bisherige Mitte, damit die
    Quadrate klein bleiben. Der erste Kreis durch alle Ecken des Zugs nimmt
    die Stirnringe mit, und die liegen auf keinem Kreis: Am gedruckten M6
    stand die Mitte so sechs Mikrometer daneben, und die Kanten maßen einen
    Vorschub von 1,0018 statt 1,0000 (22.09.2026).
    """
    from app.core.perceive.features import _plane_basis

    first, second = _plane_basis(axis)
    rows: list[NDArray[np.float64]] = []
    targets: list[NDArray[np.float64]] = []
    for number, group in enumerate(groups):
        relative = vertices[group] - centre
        x, y = relative @ first, relative @ second
        design = np.zeros((len(group), 2 + len(groups)))
        design[:, 0] = 2.0 * x
        design[:, 1] = 2.0 * y
        design[:, 2 + number] = 1.0
        rows.append(design)
        targets.append(x * x + y * y)
    matrix = np.vstack(rows)
    if len(matrix) < 2 + len(groups) + 1:
        return None
    solution, _residuals, rank, _values = np.linalg.lstsq(
        matrix, np.concatenate(targets), rcond=None
    )
    if rank < 2 + len(groups):
        return None
    return np.asarray(centre + first * solution[0] + second * solution[1], dtype=float)


#: Welchen Anteil der längsten Wendel eine Wendel an Umläufen tragen muss, um
#: für Gangzahl, Kamm und Grund mitzuzählen. Ein Viertel: Ein Auslauf am Ende
#: eines Gewindes oder ein Stück Stirnkante windet sich ein wenig mit, ohne eine
#: Wendel des Gewindes zu sein — gezählt, verdürbe er die Periodizität.
WINDING_SHARE: Final = 0.25


def _measured_helix(
    body: trimesh.Trimesh,
    edges: NDArray[np.int64],
    *,
    hint: Helix | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> Helix | None:
    """Das Gewinde eines Zugs, an seinen Kanten gemessen — oder nichts.

    Gefragt wird zuerst die Achse, die das Spektrum schon gefunden hat
    (``hint``), dann die Kandidaten aus :func:`_candidate_axes`: Ein kurzes
    breites Gewinde und ein mehrgängiges fand das Spektrum nicht — das eine
    trägt zu wenige Umläufe, beim anderen heben sich die Gänge beim Vorschub
    auf. Die Mitte der Achse kommt aus einem Kreis durch die Ecken des Zugs.

    Die Tore sind dieselben wie am exakten Kern: eine Schar mit einer Richtung
    und einem Vorschub (:data:`LEAD_SHARE`), mindestens
    :data:`MIN_MEASURED_TURNS` Umläufe, jede Kante auf ihrer Wendel (höchstens
    :data:`MAX_FACET_SAG` daneben) und eine Rille in :data:`MEASURED_GROOVE_RANGE`
    Teilungen — ein Mantel mit einer Spiralnaht hat eine Wendel und keine Rille.
    """
    from app.core.perceive.features import _fit_circle, _plane_basis

    origin, local, candidates = _candidate_axes(body, edges)
    if hint is not None:
        candidates = [np.asarray(hint.axis, dtype=float), *candidates]
    found: list[Helix] = []
    for candidate in candidates:
        if check_cancelled is not None:
            check_cancelled()
        axis = np.asarray(positive_axis(tuple(float(value) for value in candidate)), dtype=float)
        first, second = _plane_basis(axis)
        circle, _radius = _fit_circle(np.column_stack((local @ first, local @ second)))
        centre = origin + first * float(circle[0]) + second * float(circle[1])
        reading = _slope_reading(body, edges, axis, centre)
        # Die Mitte an den Wendeln selbst nachziehen und neu lesen — zweimal
        # genügt: Der erste Schritt nimmt die Stirnringe heraus, der zweite
        # bestätigt ihn.
        for _step in range(2):
            if reading is None or not reading.windings:
                break
            refined = _shared_centre(
                np.asarray(body.vertices, dtype=float), reading.corners, axis, centre
            )
            if refined is None:
                break
            again = _slope_reading(body, edges, axis, refined)
            if again is None:
                break
            centre, reading = refined, again
        if reading is None or not reading.windings:
            continue
        longest = max(winding.turns for winding in reading.windings)
        if longest < MIN_MEASURED_TURNS:
            continue
        strong = [w for w in reading.windings if w.turns >= WINDING_SHARE * longest]
        deviation = max(winding.deviation for winding in strong)
        if deviation > MAX_FACET_SAG:
            continue
        starts = starts_from_periodicity(
            [(winding.radius, winding.phase) for winding in strong],
            radius_tolerance=MAX_FACET_SAG,
        )
        pitch = reading.lead / starts
        # Derselbe Steigungsbereich wie das Spektrum: Ein verdrehter Stern mit
        # sechs Spitzen windet sich auch, aber mit einer Teilung, die kein
        # Gewinde hat.
        if not PITCH_RANGE[0] - EPS_GEOM <= pitch <= PITCH_RANGE[1] + EPS_GEOM:
            continue
        radii = np.array([winding.radius for winding in strong])
        outer, inner = float(radii.max()), float(radii.min())
        depth = outer - inner
        if (
            depth < MEASURED_GROOVE_RANGE[0] * pitch - EPS_GEOM
            or depth > MEASURED_GROOVE_RANGE[1] * pitch + EPS_GEOM
        ):
            continue
        internal = not _material_outside(
            body, centre, axis, reading.low, reading.high, radii, pitch
        )
        crest = inner if internal else outer
        midpoint = centre + axis * (reading.low + reading.high) / 2.0
        result = Helix(
            axis=(float(axis[0]), float(axis[1]), float(axis[2])),
            centre=(float(midpoint[0]), float(midpoint[1]), float(midpoint[2])),
            pitch=pitch,
            crest_radius=crest,
            depth=depth,
            length=reading.high - reading.low,
            turns=longest,
            sharpness=hint.sharpness if hint is not None else 0.0,
            internal=internal,
            face_indices=_faces_in(
                body,
                centre,
                axis,
                reading.low - pitch,
                reading.high + pitch,
                crest,
                depth,
                internal,
            ),
            handedness=reading.handedness,
            lead=reading.lead,
            starts=starts,
            measured=True,
            uncertainty=deviation,
        )
        found.append(result)
    if not found:
        return None
    # **Die Achse, auf der die Kanten am genauesten auf ihren Wendeln liegen**
    # — unter denen, die fast das ganze Gewinde sehen. Die Kandidaten liegen
    # alle dicht an der wahren Achse; hier stand „die meisten Umläufe, dann
    # die kleinste Abweichung", und seit die Umläufe überdeckt gezählt werden,
    # entschied ein Hundertstel Umlauf über eine Achse mit 0,0066 statt
    # 0,000015 mm Abweichung (zweigängiges Gewinde, Sehne 0,05, 23.09.2026).
    longest = max(helix.turns for helix in found)
    return min(
        (helix for helix in found if helix.turns >= LEAD_SHARE * longest),
        key=lambda helix: float(helix.uncertainty or 0.0),
    )


def _best_pitch(
    offset: NDArray[np.float64],
    axis: NDArray[np.float64],
    along: NDArray[np.float64],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[float, float, float, str]:
    """Der Grundton der Konzentration, wie sehr er heraussticht — und in welche Richtung.

    Gibt Steigung, Konzentration, Schärfe und Händigkeit zurück — die Schärfe
    als Gipfel geteilt durch den Median über den ganzen Bereich. Gewählt wird
    der **größte** Gipfel, der :data:`HARMONIC_SHARE` des höchsten erreicht;
    die Begründung steht dort.

    **Beide Vorzeichen** (B1, P2.5): Eine Rechtswendel konzentriert bei
    ``z - p·θ/2π``, eine Linkswendel bei ``z + p·θ/2π`` — in derselben
    rechtshändigen Basis (erste, zweite, Achse), in der auch der exakte Leser
    misst. Gerechnet wird beides, und es gilt die Richtung mit dem höheren
    Gipfel; die andere ist an einer echten Wendel Rauschen. Vorher setzte die
    Rechnung den Rechtsgang voraus, und die Spiegelung desselben Bolzens ergab
    null Wendeln.

    **Und beide aus einem Durchlauf.** Die Phase ist ``a ∓ θ`` mit
    ``a = 2π·z/p``; ``cos(a ∓ θ) = cos a·cos θ ± sin a·sin θ`` und
    ``sin(a ∓ θ) = sin a·cos θ ∓ cos a·sin θ``. Die Winkelfunktionen über die
    Phasenmatrix — das teure Stück — laufen deshalb einmal je Block, und die
    vier Mittelwerte sind zwei Matrixprodukte der Phasenmatrix mit den zwei
    Spalten ``cos θ`` und ``sin θ``; beide Händigkeiten kommen aus denselben
    vier Zahlen je Steigung. Ein Modulo braucht die Phase nicht, Sinus und
    Kosinus sind periodisch. Zwei volle Durchläufe verdoppelten die
    Steigungssuche (``test_helix.py`` von 7,3 auf 16,5 s, gemessen am
    21.09.2026); gemessen am M3-Bolzen mit 6 965 Punkten: 236 → 66 ms.
    """
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = np.cross(axis, helper)
    first /= np.linalg.norm(first)
    second = np.cross(axis, first)
    angle = np.arctan2(offset @ second, offset @ first)
    turns = np.stack((np.cos(angle), np.sin(angle)), axis=1) / len(along)

    pitches = np.arange(PITCH_RANGE[0], PITCH_RANGE[1] + PITCH_STEP, PITCH_STEP)
    rows = max(1, PITCH_BLOCK_VALUES // len(along))
    strengths = {
        "right": np.empty(len(pitches), dtype=float),
        "left": np.empty(len(pitches), dtype=float),
    }
    for start in range(0, len(pitches), rows):
        if check_cancelled is not None:
            check_cancelled()
        block = pitches[start : start + rows]
        phase = along[None, :] * (2 * math.pi / block)[:, None]
        # Je Steigung: mean(cos a·cos θ), mean(cos a·sin θ) und
        # mean(sin a·cos θ), mean(sin a·sin θ).
        with_cos = np.cos(phase) @ turns
        with_sin = np.sin(phase) @ turns
        stop = start + len(block)
        # Rechtsgang: a - θ; Linksgang: a + θ.
        strengths["right"][start:stop] = np.hypot(
            with_cos[:, 0] + with_sin[:, 1], with_sin[:, 0] - with_cos[:, 1]
        )
        strengths["left"][start:stop] = np.hypot(
            with_cos[:, 0] - with_sin[:, 1], with_sin[:, 0] + with_cos[:, 1]
        )
    if check_cancelled is not None:
        check_cancelled()

    chosen: tuple[float, float, float, str] | None = None
    for handedness in ("right", "left"):
        strength = strengths[handedness]
        highest = float(strength.max())
        rises = np.r_[True, strength[1:] >= strength[:-1]]
        falls = np.r_[strength[:-1] >= strength[1:], True]
        candidates = np.flatnonzero(rises & falls & (strength >= HARMONIC_SHARE * highest))
        best = int(candidates[-1]) if len(candidates) else int(strength.argmax())

        background = float(np.median(strength))
        peak = float(strength[best])
        sharpness = peak / background if background > 1e-9 else float("inf")
        if chosen is None or peak > chosen[1]:
            chosen = (float(pitches[best]), peak, sharpness, handedness)
    assert chosen is not None
    return chosen


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
