"""Sculpting: viele Gesten, eine Operation (Bauplan §25, Konzept P16 §7.1).

Eine Figur sind mehrere tausend Striche. Jeder davon als eigener Schritt im
Verlauf wäre kein Verlauf mehr, und die naive Wiedergabe — je Strich ein
Durchgang über alle Eckpunkte — kostet das Produkt aus Strichzahl und
Eckpunktzahl: bei 200 000 Eckpunkten und 1 000 Strichen rund anderthalb
Minuten je Auswertung.

Deshalb rechnet dieses Modul **akkumuliert**: ein KD-Baum über die Eckpunkte,
je Strich eine Kugelabfrage, Gewichte summieren, einmal verschieben. Gemessen
in P16.2 ist das Faktor sechzig, und es ist der Unterschied zwischen „geht
nicht" und „geht".

Der Preis steht als Entscheidung C im Konzept und wird hier nicht versteckt:
Striche derselben Etappe sind **kommutativ**. Zweimal über dieselbe Stelle zu
fahren addiert zwei Gewichte auf die Ausgangsfläche, statt den zweiten Zug auf
das Ergebnis des ersten zu setzen. Drei Werkzeuge lassen sich so nicht rechnen
und beginnen von selbst eine neue Etappe (:data:`ORDERED_TOOLS`), und jeder
Strich kann eine erzwingen (``cut``) — wer die exakte Reihenfolge braucht,
kauft sie sich stückweise statt für die ganze Sitzung.

**Pinselfassung 2 (RM-560)** legt die Etappengrenze an jede Geste: Ein neuer
Mauszug wirkt auf das Ergebnis der vorigen, zehnmal dieselbe Linie wird ein
runder Hügel statt einer Säule mit Falte (H4). Die Stärke ist eine Stufe 1
bis 10 ohne Einheit; Auftragen sättigt je Geste, Glätten, Flachziehen und
Kneifen laufen höchstens bis an ihr Ziel (H3). Alte Züge tragen Fassung 1
und rechnen wie zuvor (:attr:`Stroke.brush`).
"""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any, Final, cast, get_args

import numpy as np

from app.core.deferred import cKDTree, trimesh
from app.core.errors import CANCEL, SHOW_LOCATION, TAKE_BACK_STROKE, ValidationError
from app.core.geom.intersections import (
    box_groups,
    boxes_around,
    crossings_at,
    face_bounds,
    faces_touching,
)
from app.core.geom.mesh import (
    MeshData,
    as_mesh_data,
    ray_hits_batch,
    read_mesh,
    stable_vertex_normals_at,
)
from app.core.registry import op_params, param, register_op
from app.core.types import (
    CONVERGENT_TOOLS,
    ORDERED_TOOLS,
    Action,
    BaseParams,
    CancelToken,
    Finding,
    OpContext,
    OpResult,
    Profile,
    SculptTool,
    Stroke,
    Vec3,
)
from app.core.units import EPS_GEOM
from app.i18n import _

#: Die drei Symmetrieebenen als Bit im Feld ``Stroke.symmetry``.
AXIS_BITS: Final[tuple[tuple[int, int], ...]] = ((1, 0), (2, 1), (4, 2))

#: Wie weit ein Strich über seinen Radius hinaus noch etwas bewirkt. Die
#: Gewichtsfunktion fällt glockenförmig ab und wird am Rand nicht exakt null;
#: hart abzuschneiden ist richtig, weil ein Pinsel eine Grenze hat, die man
#: sieht — und weil nur so die Vorschau auf die getroffenen Eckpunkte
#: beschränkt bleiben kann (P16.2).
FALLOFF: Final = 1.0

#: Die Pinselfassung neuer Züge (:attr:`Stroke.brush`, RM-560).
BRUSH: Final = 2

#: Die Stufen der Stärke in Fassung 2: eine Zahl ohne Einheit.
LEVEL_RANGE: Final = (1, 10)

#: Die Vorgabestufe einer neuen Sitzung — die Mitte, von der aus man in beide
#: Richtungen nachstellen kann.
LEVEL_DEFAULT: Final = 5

#: Wie weit eine auftragende Probe der Fassung 2 bei voller Stufe trägt, als
#: Anteil ihres Radius. Eine Linie aus Proben im Abstand eines halben Radius
#: hebt die Fläche bei Stufe 5 um rund ein Fünftel des Radius (Messung H4).
ADD_SHARE: Final = 0.25

#: Wie viele Proben voller Stufe eine Geste höchstens aufhäuft, bevor sie
#: sättigt. Ohne Grenze wuchs aus einem Kritzeln an einer Stelle eine Säule
#: mit gefalteten Flanken (H4: 148,6° Diederwinkel); gesättigt wird sie ein
#: Hügel, und die nächste Geste setzt auf dessen Ergebnis auf.
ADD_LIMIT: Final = 2.0


def starts_stage(previous: Stroke | None, stroke: Stroke) -> bool:
    """Ob ``stroke`` hinter ``previous`` eine neue Etappe beginnt.

    Fassung 1 (bis Format 48, RM-560): vor einem Strich, der den Zustand vor
    sich liest (``smooth``, ``inflate``, ``flatten``), nach einem solchen und
    vor einem erzwungenen Schnitt. Fassung 2: an jeder neuen Geste — und vor
    einem Zug ohne Gestenkennung, denn der ist seine eigene. Wechselt die
    Fassung, beginnt ebenfalls eine Etappe.

    Der erste Strich beginnt nie eine zweite Etappe: Vor ihm liegt nichts, was
    er lesen könnte, und ein leerer Durchgang kostet nur Zeit.
    """
    if previous is None:
        return False
    if stroke.cut or stroke.brush != previous.brush:
        return True
    if stroke.brush >= BRUSH:
        return not stroke.gesture or stroke.gesture != previous.gesture
    return stroke.tool in ORDERED_TOOLS or previous.tool in ORDERED_TOOLS


def stages(strokes: Sequence[Stroke]) -> list[list[Stroke]]:
    """Die Strichliste in Abschnitte zerlegen, die je in einem Durchgang gehen
    (:func:`starts_stage`)."""
    parts: list[list[Stroke]] = []
    current: list[Stroke] = []
    previous: Stroke | None = None
    for stroke in strokes:
        if current and starts_stage(previous, stroke):
            parts.append(current)
            current = []
        current.append(stroke)
        previous = stroke
    if current:
        parts.append(current)
    return parts


def mirror_centre(mesh: MeshData) -> np.ndarray:
    """Wo die Symmetrieebenen eines Körpers liegen: in der Mitte seines
    Hüllquaders vor den Zügen.

    **Nicht am Schwerpunkt** — der wandert beim Formen, und eine
    Symmetrieebene, die sich unter der Hand bewegt, ist die Sorte
    Überraschung, die Vertrauen kostet. **Und nicht am Nullpunkt der Szene**:
    Dort lag sie bis RM-363, und an jedem Körper abseits der Mitte ging die
    Spiegelung ins Leere — Symmetrie Z an keinem Körper auf dem Bett.
    Die Mitte des Körpers vor den Zügen steht fest, solange der Schritt
    davor sich nicht ändert, und wandert mit, wenn er sich bewegt.
    """
    bounds = np.asarray(mesh.raw.bounds, dtype=float)
    if bounds.shape != (2, 3) or not np.isfinite(bounds).all():
        return np.zeros(3)
    middle: np.ndarray = (bounds[0] + bounds[1]) / 2.0
    return middle


#: Wie viele Eckpunkte die Suche nach der Spiegelebene höchstens befragt —
#: gleichmäßig über das Netz genommen, jeder so und so vielte.
SYMMETRY_SAMPLE: Final = 500

#: Wie weit die Spiegelebene von der Hüllquadermitte abrücken darf, als Anteil
#: der Ausdehnung — und wie fein die Suche sie stellt (Anzahl Schritte je
#: Seite, grob und dann fein um den besten).
SYMMETRY_REACH: Final = 0.25
SYMMETRY_STEPS: Final = 10

#: Um wie viel die gefundene Ebene das Spiegelbild besser treffen muss als die
#: Mitte, damit sie gilt. Ein Körper ohne Symmetrie fände sonst irgendeine
#: Ebene, die ein wenig besser passt, und spiegelte dort: Eine erzeugte Figur
#: trifft sich links/rechts an der gefundenen Ebene auf 0,38 bis 0,41 des
#: Fehlers an der Mitte, oben/unten nur auf 0,6 bis 0,7 — dort ist keine.
SYMMETRY_GAIN: Final = 0.5


def fitted_mirror_centre(mesh: MeshData, axes: Sequence[int] = (0, 1, 2)) -> np.ndarray:
    """Wo die Spiegelebenen eines Körpers liegen, wenn er sich dort selbst trifft (H11).

    Die Mitte des Hüllquaders lag an einer erzeugten Figur 4,2 mm neben ihrer
    Symmetrie: ein ausgestreckter Arm schiebt den Hüllquader, nicht den
    Körper. Je Achse wird die Ebene gesucht, an der das Spiegelbild der
    Eckpunkte das Netz am nächsten trifft, auf einem festen Raster um die
    Mitte — dieselbe Ebene auf jeder Maschine. Trifft sie nicht deutlich
    besser als die Mitte (:data:`SYMMETRY_GAIN`), bleibt die Mitte: Ein
    unsymmetrischer Körper hat keine Symmetrie zu finden. Gesucht wird nur an
    ``axes``; jede Achse für sich, also dieselbe Ebene, ob eine oder drei
    gefragt sind.
    """
    middle = mirror_centre(mesh)
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    if len(vertices) < 4:
        return middle
    extent = np.ptp(vertices, axis=0)
    tree = cKDTree(vertices)
    sample = vertices[:: max(1, len(vertices) // SYMMETRY_SAMPLE)]
    centre = middle.copy()
    for axis in axes:
        if extent[axis] <= EPS_GEOM:
            continue

        def miss(at: float, axis: int = axis) -> float:
            mirrored = sample.copy()
            mirrored[:, axis] = 2.0 * at - sample[:, axis]
            away, _index = tree.query(mirrored)
            return float(np.mean(away))

        at_middle = miss(float(middle[axis]))
        step = float(extent[axis]) * SYMMETRY_REACH / SYMMETRY_STEPS
        best = (at_middle, 0, float(middle[axis]))
        for rounds in range(2):
            around = best[2]
            for index in range(-SYMMETRY_STEPS, SYMMETRY_STEPS + 1):
                at = around + index * step
                candidate = (miss(at), abs(index) + rounds * SYMMETRY_STEPS, at)
                best = min(best, candidate)
            step /= SYMMETRY_STEPS
        if best[0] < at_middle * SYMMETRY_GAIN:
            centre[axis] = best[2]
    return centre


def mirror_plane(
    mesh: MeshData, *, at_body: bool = True, fitted: bool = True, axes: int = 7
) -> Vec3:
    """Der Punkt, durch den die Spiegelebenen eines Formschritts gehen.

    Eine Stelle für Operation, Vorschau und Fenster: Liefen sie auseinander,
    zeigte die Vorschau den Spiegelzug an einer anderen Stelle als die
    Auswertung danach. ``at_body`` aus heißt Nullpunkt der Szene (vor Format
    40), ``fitted`` aus die Hüllquadermitte (vor Format 49). ``axes`` ist die
    Bitmaske der Ebenen, die gebraucht werden (wie ``Stroke.symmetry``); die
    übrigen bleiben in der Mitte und kosten keine Suche.
    """
    if not at_body:
        return (0.0, 0.0, 0.0)
    if fitted:
        found = fitted_mirror_centre(mesh, [axis for bit, axis in AXIS_BITS if axes & bit])
    else:
        found = mirror_centre(mesh)
    return (float(found[0]), float(found[1]), float(found[2]))


def _mirrored(stroke: Stroke, centre: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Punkt und Richtung des Strichs, dazu jede verlangte Spiegelung an den
    Ebenen durch ``centre`` (:func:`mirror_centre`)."""
    point = np.asarray(stroke.point, dtype=float)
    direction = np.asarray(stroke.normal, dtype=float)
    places = [(point, direction)]
    for bit, axis in AXIS_BITS:
        if not stroke.symmetry & bit:
            continue
        flip = np.ones(3)
        flip[axis] = -1.0
        places = [
            *places,
            *[((place - centre) * flip + centre, way * flip) for place, way in places],
        ]
    return places


def _falloff(away: np.ndarray) -> np.ndarray:
    """Das Gewicht eines Pinsels im Abstand ``away`` (in Radien) von seiner Mitte."""
    return np.asarray(np.exp(-4.0 * away * away))


def _weights(tree: cKDTree, points: np.ndarray, centre: np.ndarray, radius: float) -> Any:
    """Wen dieser Strich trifft und wie stark — Indizes und Gewichte.

    Die Kugelabfrage ist der ganze Trick: Sie kostet die Zahl der
    *tatsächlich* getroffenen Punkte, nicht die Zahl aller. In P16.2 gemessen:
    ein Strich trifft 10 595 von 3 932 160 Eckpunkten, und der Unterschied
    zwischen beiden Zahlen ist das Leistungsbudget.
    """
    near = np.asarray(tree.query_ball_point(centre, radius * FALLOFF), dtype=np.int64)
    if not len(near):
        return near, np.zeros(0)
    offset = points[near] - centre
    # Dieselbe Rechnung wie ``np.linalg.norm(…, axis=1)``, bitgleich, ohne
    # dessen Aufrufkosten: Tausend Züge mit Spiegelbild sind zweitausend
    # Aufrufe, und je Aufruf kostete die Prüfung der Argumente mehr als die
    # Rechnung an den tausend getroffenen Punkten (RM-428).
    away = np.sqrt(np.add.reduce(offset * offset, axis=1)) / max(radius, 1e-9)
    return near, _falloff(away) * (away <= FALLOFF)


def _mirror_share(places: list[tuple[np.ndarray, np.ndarray]], radius: float) -> float:
    """Welchen Anteil jede Kopie eines gespiegelten Zugs trägt (RM-378, RM-428).

    Ein Zug auf der Symmetrieebene fiel mit seinem Spiegelbild zusammen und
    wirkte doppelt. Die stärkere Kopie je Ecke (RM-378) wirkte dort einmal,
    hinterließ aber knapp daneben eine Kerbe mit Knick, wo beide gleich stark
    sind, und schob bei Gleichstand die Ecken auf der Ebene zur Seite der
    ersten Kopie: 1 mm neben der Ebene 0,148 mm tief, Kneifen 0,426 mm aus der
    Ebene.

    Jetzt tragen alle Kopien denselben Anteil ``1 / Σ κ``: ``κ`` ist das
    Gewicht, das eine Kopie an der Mitte der ersten hat, ohne die harte Grenze
    des Pinsels. An der Mitte des Zugs wirkt so genau seine Stärke, ob sein
    Spiegelbild darüber liegt (Anteil ½, er wirkt einmal) oder weit weg
    (Anteil 1, beide wirken wie bisher); dazwischen gleitet der Anteil glatt.
    Die Summe zweier Glockenkurven hat keinen Knick, und weil die Kopien
    einander spiegeln, sehen alle dieselben Abstände — derselbe Anteil für
    jede, und das Ergebnis bleibt spiegelgleich.

    Überdecken sich die Pinsel nicht, ist der Anteil genau eins: dort rechnet
    der Zug bitgleich wie vor RM-378. Bis dahin fehlen höchstens e⁻¹⁶ der
    Stärke.
    """
    if len(places) < 2:
        return 1.0
    # Höchstens acht Kopien: in Gleitkommazahlen von Python, nicht als Feld —
    # je Zug kostete das Feld mehr als die Kopien selbst.
    first = places[0][0]
    x, y, z = float(first[0]), float(first[1]), float(first[2])
    size = max(radius, 1e-9)
    reaching = []
    for centre, _direction in places:
        dx, dy, dz = float(centre[0]) - x, float(centre[1]) - y, float(centre[2]) - z
        away = math.sqrt(dx * dx + dy * dy + dz * dz) / size
        if away < 2.0 * FALLOFF:
            reaching.append(away)
    if len(reaching) < 2:
        return 1.0
    return float(1.0 / _falloff(np.asarray(reaching)).sum())


def _neighbours(mesh: trimesh.Trimesh, count: int) -> tuple[np.ndarray, np.ndarray]:
    """Für jeden Eckpunkt die Summe seiner Nachbarn und deren Zahl.

    Einmal je Etappe gerechnet, nicht je Strich: Glätten und Flachziehen
    brauchen dieselbe Nachbarschaft, und sie ändert sich innerhalb einer
    Etappe nicht — die Topologie bleibt, wie sie war.
    """
    edges = np.asarray(mesh.edges, dtype=np.int64)
    total = np.zeros((count, 3), dtype=float)
    seen = np.zeros(count, dtype=float)
    vertices = np.asarray(mesh.vertices, dtype=float)
    np.add.at(total, edges[:, 0], vertices[edges[:, 1]])
    np.add.at(seen, edges[:, 0], 1.0)
    return total, np.maximum(seen, 1.0)


class _Stage:
    """Eine Etappe im Aufbau: die Fläche an ihrem Anfang, ihr Suchbaum, ihre
    Normalen — und das Offsetfeld der Züge, die bisher zu ihr gehören.

    Die Striche einer Etappe summieren sich auf diese Fläche (Entscheidung C),
    einer nach dem anderen und in ihrer Reihenfolge: :meth:`add` kostet nur
    die Kugelabfrage des Zugs. Die Operation gibt alle Züge einer Etappe
    hinein, die Vorschau der Formsitzung (:class:`SculptPreview`) nur den
    neuen — beide rechnen dieselbe Folge und sind bitgleich.

    Nachbarschaft und Krümmung brauchen nur die Werkzeuge aus
    :data:`ORDERED_TOOLS`, und jedes davon steht allein in seiner Etappe; sie
    entstehen erst mit ihm.
    """

    def __init__(
        self,
        body: trimesh.Trimesh,
        plane: np.ndarray,
        *,
        front_only: bool,
        mirror_once: bool,
        tree: Any = None,
    ) -> None:
        self.body = body
        self.points = np.asarray(body.vertices, dtype=float)
        self.normals = np.asarray(body.vertex_normals, dtype=float)
        self.tree = cKDTree(self.points) if tree is None else tree
        self.plane = plane
        self.front_only = front_only
        self.mirror_once = mirror_once
        self.shift = np.zeros_like(self.points)
        self.strokes: list[Stroke] = []
        self._neighbours: tuple[np.ndarray, np.ndarray] | None = None
        self._curvature: np.ndarray | None = None
        # Pinselfassung 2: Weg und Gewicht je Eckpunkt, getrennt nach
        # auftragend und zulaufend — angewandt erst in :meth:`positions`, weil
        # Sättigung und Obergrenze an der Summe hängen, nicht am einzelnen Zug.
        self._push: np.ndarray | None = None
        self._push_weight: np.ndarray | None = None
        self._pull: np.ndarray | None = None
        self._pull_weight: np.ndarray | None = None

    def neighbours(self) -> tuple[np.ndarray, np.ndarray]:
        """Summe und Zahl der Nachbarn je Eckpunkt (:func:`_neighbours`)."""
        if self._neighbours is None:
            self._neighbours = _neighbours(self.body, len(self.points))
        return self._neighbours

    def curvature(self) -> np.ndarray:
        """Krümmung als Abstand zum Nachbarschaftsmittel entlang der Normale:
        positiv, wo die Fläche nach innen gewölbt ist. Eine Näherung, und die
        richtige — sie kostet nichts über die Nachbarn hinaus, die für das
        Glätten ohnehin gebraucht werden."""
        if self._curvature is None:
            total, seen = self.neighbours()
            middle = total / seen[:, None]
            self._curvature = np.einsum("ij,ij->i", middle - self.points, self.normals)
        return self._curvature

    def add(
        self,
        stroke: Stroke,
        missed: list[Stroke] | None = None,
        cancelled: CancelToken | None = None,
    ) -> None:
        """Einen Zug aufsummieren.

        ``missed`` sammelt die Striche, die keinen einzigen Eckpunkt greifen —
        hier und nicht anderswo, weil die Kugelabfrage es ohnehin feststellt.
        Was daraus wird, steht in ``_sculpting_findings``.

        ``cancelled`` wird vor jedem Zug gefragt (§15.6): Eine Sitzung mit
        tausenden Zügen ist ein Suchlauf je Zug, und bis zum 22.09.2026 wirkte
        der Abbrechen-Knopf erst, wenn alle gerechnet waren.
        """
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        self.strokes.append(stroke)
        points, normals, shift = self.points, self.normals, self.shift
        touched = False
        places = []
        copies = _mirrored(stroke, self.plane)
        share = _mirror_share(copies, stroke.radius) if self.mirror_once else 1.0
        for centre, direction in copies:
            near, weight = _weights(self.tree, points, centre, stroke.radius)
            if not len(near):
                continue
            touched = True
            if self.front_only:
                weight = weight * _facing(normals[near], direction)
            if share != 1.0:
                weight = weight * share
            places.append((centre, direction, near, weight))
        if stroke.brush >= BRUSH:
            self._add_level(stroke, places)
            if missed is not None and not touched:
                missed.append(stroke)
            return
        for centre, direction, near, weight in places:
            if not np.any(weight > 0.0):
                continue
            scale = (weight * stroke.strength)[:, None]
            if stroke.tool == "draw":
                shift[near] += direction * scale
            elif stroke.tool == "carve":
                shift[near] -= direction * scale
            elif stroke.tool == "pinch":
                towards = centre - points[near]
                shift[near] += towards * scale * 0.5
            elif stroke.tool == "smooth":
                total, seen = self.neighbours()
                middle = total[near] / seen[near, None]
                shift[near] += (middle - points[near]) * scale
            elif stroke.tool == "inflate":
                curvature = self.curvature()
                shift[near] += normals[near] * (curvature[near][:, None] + 1.0) * scale
            elif stroke.tool == "flatten":
                # Die Ebene bildet sich aus dem, was der Pinsel greift: ihr
                # Aufpunkt ist der gewichtete Mittelwert der getroffenen
                # Punkte, ihre Normale die Strichrichtung. Eine feste Ebene
                # durch den Klickpunkt wäre die naheliegende Wahl und die
                # falsche — sie schnitte in den Körper, sobald der Pinsel
                # größer ist als die Wölbung darunter.
                anchor = np.average(points[near], axis=0, weights=weight)
                height = np.einsum("ij,j->i", points[near] - anchor, direction)
                shift[near] -= direction * (height[:, None] * scale)
        if missed is not None and not touched:
            missed.append(stroke)

    def _add_level(
        self, stroke: Stroke, places: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]
    ) -> None:
        """Einen Zug der Pinselfassung 2 sammeln (RM-560, H3).

        Die Stärke ist eine Stufe: ``stroke.strength / 10`` ist der Anteil, den
        die Probe an ihrer Mitte beiträgt. Auftragende Werkzeuge sammeln eine
        Richtung mal :data:`ADD_SHARE` des Radius, zulaufende den Weg zu ihrem
        Ziel — beide mit ihrem Gewicht, damit :meth:`positions` die Summe
        sättigen oder deckeln kann.
        """
        points, normals = self.points, self.normals
        level = min(max(float(stroke.strength), 0.0), float(LEVEL_RANGE[1])) / LEVEL_RANGE[1]
        converging = stroke.tool in CONVERGENT_TOOLS
        if converging and self._pull is None:
            self._pull = np.zeros_like(points)
            self._pull_weight = np.zeros(len(points))
        if not converging and self._push is None:
            self._push = np.zeros_like(points)
            self._push_weight = np.zeros(len(points))
        reach = stroke.radius * ADD_SHARE
        for centre, direction, near, weight in places:
            share = weight * level
            if not np.any(share > 0.0):
                continue
            if stroke.tool == "draw":
                way = np.broadcast_to(direction * reach, (len(near), 3))
            elif stroke.tool == "carve":
                way = np.broadcast_to(-direction * reach, (len(near), 3))
            elif stroke.tool == "inflate":
                way = normals[near] * reach
            elif stroke.tool == "smooth":
                total, seen = self.neighbours()
                way = total[near] / seen[near, None] - points[near]
            elif stroke.tool == "flatten":
                anchor = np.average(points[near], axis=0, weights=weight)
                height = np.einsum("ij,j->i", points[near] - anchor, direction)
                way = -direction * height[:, None]
            else:
                # Kneifen: höchstens auf halbem Weg zur Strichmitte — so kreuzen
                # zwei Seiten einer Falte einander nie (H3: Stärke 3 ergab 216
                # sich schneidende Dreieckspaare).
                way = (centre - points[near]) * 0.5
            if converging:
                assert self._pull is not None and self._pull_weight is not None
                self._pull[near] += way * share[:, None]
                self._pull_weight[near] += share
            else:
                assert self._push is not None and self._push_weight is not None
                self._push[near] += way * share[:, None]
                self._push_weight[near] += share

    def positions(self) -> np.ndarray:
        """Die Eckpunkte nach den bisherigen Zügen dieser Etappe.

        Fassung 1 ist die Summe der Wege. Fassung 2 teilt die gesammelte
        Richtung durch ihr Gewicht und nimmt davon, was die Sättigung zulässt:
        auftragend ``ADD_LIMIT·(1 - e^(-W/ADD_LIMIT))`` — für wenige Proben
        fast die Summe, für ein Kritzeln an einer Stelle höchstens
        :data:`ADD_LIMIT` volle Proben —, zulaufend ``min(W, 1)``: nie über das
        Ziel hinaus.
        """
        placed = self.points + self.shift
        if self._push is not None and self._push_weight is not None:
            weight = self._push_weight
            safe = np.where(weight > 0.0, weight, 1.0)
            gain = np.where(weight > 0.0, -ADD_LIMIT * np.expm1(-weight / ADD_LIMIT) / safe, 0.0)
            placed = placed + self._push * gain[:, None]
        if self._pull is not None and self._pull_weight is not None:
            weight = self._pull_weight
            safe = np.where(weight > 0.0, weight, 1.0)
            gain = np.where(weight > 0.0, np.minimum(weight, 1.0) / safe, 0.0)
            placed = placed + self._pull * gain[:, None]
        return np.asarray(placed, dtype=float)

    def moved(self) -> trimesh.Trimesh:
        """Die Fläche nach den bisherigen Zügen dieser Etappe."""
        return trimesh.Trimesh(vertices=self.positions(), faces=self.body.faces, process=False)


#: Nach wie vielen Zügen die Auswertung ihren Fortschritt meldet — je Zug
#: kostete die Meldung mehr als der Zug.
PROGRESS_STROKES: Final = 64


#: Ab welchem Skalarprodukt zwischen Eckpunktnormale und Strichrichtung ein
#: Punkt dem Pinsel zugewandt ist. Null heißt: die ganze zugewandte
#: Halbkugel — eine Rundung unter dem Pinsel bleibt erreichbar, die Rückseite
#: einer dünnen Wand nicht (RM-376). Eine Richtung, keine Toleranz.
FACING_LIMIT: Final = 0.0


def _facing(normals: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """1 für Punkte, die dem Pinsel zugewandt sind, sonst 0 (RM-376).

    Der Pinsel griff jeden Eckpunkt in seiner Kugel, auch die Unterseite einer
    dünnen Wand und die Innenwand eines Hohlkörpers: *Abtragen* auf einer
    4-mm-Platte zog die Unterseite 0,6 mm mit (die 3,7 mm unter dem Bett waren
    die durchgestoßene Oberseite, RM-430). Elementweise wie jeder Strahl im
    Kern (RM-187).
    """
    along = (
        normals[:, 0] * direction[0] + normals[:, 1] * direction[1] + normals[:, 2] * direction[2]
    )
    return np.asarray(along > FACING_LIMIT, dtype=float)


def median_edge(mesh: MeshData) -> float:
    """Die mittlere Kantenlänge — das Maß, an dem ein Pinsel sich messen lässt.

    Der Median und nicht der Mittelwert: Ein einziges entartetes Dreieck zieht
    den Mittelwert nach unten und ließe ein grobes Netz fein aussehen.
    """
    lengths = np.asarray(mesh.raw.edges_unique_length, dtype=float)
    return float(np.median(lengths)) if len(lengths) else 0.0


#: Welcher Anteil der Hüllquaderdiagonale ein Pinsel zu Beginn greift (H8).
#: Ein fester Radius von 6 mm war an der Figur aus dem Korpus ein Zwanzigstel
#: der Diagonale, am Würfel ein Sechstel — derselbe Zug tat am einen fast
#: nichts und überdeckte am anderen eine ganze Seite.
RADIUS_SHARE: Final = 1.0 / 20.0

#: Wie viele Dreiecke das selbsttätige Angleichen höchstens erzeugt. Darüber
#: nimmt es die Kante, die dorthin passt, und die Leiste sagt, dass ein
#: größerer Pinsel glatter wird — besser als eine Sitzung, die minutenlang
#: rechnet und dann keinen Speicher mehr hat.
REFINE_MAX_TRIANGLES: Final = 600_000


def brush_radius_for(mesh: MeshData) -> float:
    """Der Pinselradius, mit dem eine Sitzung an diesem Körper beginnt (H8).

    Ein Zwanzigstel der Hüllquaderdiagonale, gerundet auf 1, 2 oder 5 mal
    eine Zehnerpotenz — eine Zahl, die man liest und nachstellt, keine mit
    drei Nachkommastellen.
    """
    bounds = np.asarray(mesh.raw.bounds, dtype=float)
    if bounds.shape != (2, 3) or not np.isfinite(bounds).all():
        return 5.0
    diagonal = float(np.sqrt(((bounds[1] - bounds[0]) ** 2).sum())) * RADIUS_SHARE
    if diagonal <= EPS_GEOM:
        return 5.0
    power = 10.0 ** math.floor(math.log10(diagonal))
    mantissa = min((1.0, 2.0, 5.0, 10.0), key=lambda step: abs(math.log(diagonal / power / step)))
    return float(min(max(mantissa * power, 0.1), 100.0))


def refine_edge_for(
    mesh: MeshData, radius: float, finest: float, edge: float | None = None
) -> float:
    """Auf welche Kantenlänge die Sitzung das Netz für diesen Pinsel angleicht —
    oder null, wenn es fein genug ist (H2, H9).

    Zu grob heißt: weniger als :data:`BRUSH_TO_EDGE` Kanten je Radius. Dann
    :data:`REFINE_TO_EDGE` Kanten je Radius, nicht feiner als ``finest`` (die
    Untergrenze von *Dreiecke angleichen*) und nicht feiner, als
    :data:`REFINE_MAX_TRIANGLES` zulassen. ``edge`` ist die mittlere
    Kantenlänge, wenn sie schon bekannt ist.
    """
    current = median_edge(mesh) if edge is None else edge
    if current * BRUSH_TO_EDGE <= radius:
        return 0.0
    area = float(mesh.raw.area)
    # Ein gleichseitiges Dreieck mit Kante e hat die Fläche √3/4·e².
    largest = math.sqrt(max(area, 0.0) / (math.sqrt(3.0) / 4.0 * REFINE_MAX_TRIANGLES))
    wanted = max(finest, radius / REFINE_TO_EDGE, largest)
    return wanted if wanted < current else 0.0


def stroke_at(
    mesh: MeshData,
    point: Vec3,
    *,
    radius: float,
    strength: float,
    tool: str = "draw",
    symmetry: int = 0,
    cut: bool = False,
    before: Sequence[Stroke] = (),
    mirrored: int = 0,
    preview: SculptPreview | None = None,
    gesture: int = 0,
    brush: int = 1,
    centre: Vec3 | None = None,
) -> Stroke:
    """Aus einem angeklickten Punkt einen Strich machen.

    Die Oberfläche liefert einen Ort, keine Richtung — und die Richtung ist
    das, woran der Strich trägt. In Pinselfassung 1 kommt sie aus der Normale
    des nächsten Eckpunkts; an einer Kante zeigte die 45° schräg (H10). In
    Fassung 2 ist sie das Mittel der Normalen im Pinselgebiet, gewichtet wie
    der Pinsel selbst (:func:`_brush_direction`).

    ``gesture`` und ``brush`` gehören zur Frage, ob der Zug eine Etappe
    beginnt (:func:`starts_stage`), und reisen im Zug mit. ``centre`` ist die
    Spiegelmitte der Sitzung (:func:`mirror_plane`); ohne Angabe die Mitte des
    Hüllquaders.

    ``before`` sind die Züge, die schon in der Sitzung stehen, so wie die
    Vorschau sie rechnet. Geklickt wird auf die Fläche, die sie zeigt; ein
    Zug wirkt aber auf die Fläche, an der seine Etappe beginnt. Greift er die
    nicht — ein Zug in die Mulde, die ein Zug derselben Etappe gegraben hat,
    bei einer Stärke über dem Radius —, beginnt er eine eigene Etappe
    (``cut``). Sonst wirkte er nicht und hieße verfehlt (RM-438). Die
    Entscheidung reist im Zug mit; die Operation rechnet sie nicht nach.

    ``mirrored`` sind die Spiegelebenen, die die ganze Sitzung über jeden Zug
    legt (der Parameter *Symmetrie* der Operation). Sie gehören nicht in den
    Zug — sie bleiben nachträglich änderbar —, aber in die Frage, wo er wirkt:
    Auch ein Spiegelbild kann als einziges die Fläche greifen (RM-454).

    ``preview`` ist die Vorschau der Sitzung (:class:`SculptPreview`), wenn
    sie zu ``mesh`` und ``before`` passt: Ihre Etappe kennt Fläche, Suchbaum
    und Normalen schon, und der Zug kostet keinen Suchbaum über das ganze Netz
    (RM-366). Ohne sie entsteht derselbe Zug.

    Im Kern und nicht in der Oberfläche, weil es Geometrie ist. Was das Fenster
    beisteuert, sind zwei Zahlen und ein Klick.
    """
    candidate = Stroke(
        point=point,
        normal=(0.0, 0.0, 1.0),
        radius=radius,
        strength=strength,
        tool=_tool(tool),
        symmetry=symmetry,
        cut=cut,
        gesture=gesture,
        brush=brush,
    )
    if preview is not None and preview.mesh is mesh and preview.strokes == tuple(before):
        surface, cut, tree, normals = preview.surface_for(candidate, symmetry=symmetry | mirrored)
    else:
        surface, cut = _surface_for(
            mesh, before, candidate, symmetry=symmetry | mirrored, centre=centre
        )
        points = np.asarray(surface.raw.vertices, dtype=float)
        tree = cKDTree(points) if len(points) else None
        normals = np.asarray(surface.raw.vertex_normals, dtype=float)
    if tree is None:
        return replace(candidate, cut=cut)
    here = np.asarray(point, dtype=float)
    _away, index = tree.query(here)
    normal = normals[int(index)]
    if brush >= BRUSH:
        normal = _brush_direction(tree, normals, here, radius, normal)
    return replace(
        candidate, normal=(float(normal[0]), float(normal[1]), float(normal[2])), cut=cut
    )


def _brush_direction(
    tree: Any, normals: np.ndarray, point: np.ndarray, radius: float, nearest: np.ndarray
) -> np.ndarray:
    """Die Richtung eines Zugs der Fassung 2: das Mittel der Normalen unter dem Pinsel.

    Gewichtet mit derselben Glocke, mit der der Pinsel wirkt, und nur über
    Punkte, die zur Seite des Klicks schauen — sonst höben sich an einer
    dünnen Wand Vorder- und Rückseite auf. Auf einer Kante eines Quaders zog
    die Normale der nächsten Ecke den Zug 45° schräg (H10); das Mittel zeigt,
    wohin die Fläche unter dem Pinsel im Ganzen schaut.
    """
    near = np.asarray(tree.query_ball_point(point, radius * FALLOFF), dtype=np.int64)
    if not len(near):
        return nearest
    offset = tree.data[near] - point
    away = np.sqrt(np.add.reduce(offset * offset, axis=1)) / max(radius, 1e-9)
    weight = _falloff(away) * _facing(normals[near], nearest)
    total = np.einsum("ij,i->j", normals[near], weight)
    length = float(np.sqrt((total * total).sum()))
    if length <= EPS_GEOM:
        return nearest
    found: np.ndarray = total / length
    return found


def _surface_for(
    mesh: MeshData,
    before: Sequence[Stroke],
    stroke: Stroke,
    *,
    symmetry: int = 0,
    centre: Vec3 | None = None,
) -> tuple[MeshData, bool]:
    """Die Fläche, auf die ein neuer Zug wirkt, und ob er dafür eine Etappe
    beginnen muss.

    Die Etappe, der er sich anschließt, beginnt nach den abgeschlossenen
    Etappen davor. Beginnt er ohnehin eine neue (:func:`starts_stage`),
    wirkt er auf die Fläche nach allen Zügen. Sonst entscheidet, ob seine Kugel einen
    Eckpunkt der Etappenfläche greift: dieselbe Frage, an der
    :meth:`_Stage.add` einen Zug verfehlt nennt — **an jedem seiner
    Spiegelorte**, um dieselbe Mitte, um die die Auswertung spiegelt.
    Gefragt war nur der Klickpunkt; griff allein ein Spiegelbild die Fläche
    nach der Etappe, blieb der Zug in ihr und wirkte nirgends (RM-454).

    Eine eigene Etappe bekommt er nur, wenn er die Fläche nach der Etappe
    greift. Greift er auch die nicht, ist er verfehlt, und eine Etappe
    kostete einen Durchgang, ohne etwas zu ändern (RM-442).
    """
    cut, radius = stroke.cut, stroke.radius
    if not before:
        return mesh, cut
    middle = mirror_centre(mesh) if centre is None else np.asarray(centre, dtype=float)
    plane: Vec3 = (float(middle[0]), float(middle[1]), float(middle[2]))
    current = stages(before)[-1]
    fresh = starts_stage(before[-1], stroke)
    start = len(before) if fresh else len(before) - len(current)
    surface = _completed(mesh, tuple(before[:start]), plane)
    probe = replace(stroke, strength=0.0, symmetry=symmetry)
    places = [place for place, _way in _mirrored(probe, middle)]
    if fresh or _reaches(surface, places, radius):
        return surface, cut
    after = apply_strokes(surface, before[start:], centre=plane)
    if _reaches(after, places, radius):
        return after, True
    return surface, False


def _reaches(mesh: MeshData, places: Sequence[np.ndarray], radius: float) -> bool:
    """Ob die Kugel eines Zugs um einen seiner Orte einen Eckpunkt von ``mesh`` greift."""
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    if not len(vertices):
        return False
    away, _index = cKDTree(vertices).query(np.asarray(places, dtype=float))
    return bool(np.min(away) <= radius * FALLOFF)


#: Die zuletzt gerechnete Etappenfläche: Netz, Züge bis zu ihr, Ergebnis.
#: Abgeschlossene Etappen ändern sich zwischen zwei Klicks fast nie, und ohne
#: das Gedächtnis kostete jeder Klick einer großen Sitzung eine zweite volle
#: Auswertung neben der Vorschau — gemessen 615 ms bei 20 Etappen auf
#: 40 962 Eckpunkten.
_last_stage: list[tuple[MeshData, tuple[Stroke, ...], MeshData]] = []


def _completed(mesh: MeshData, done: tuple[Stroke, ...], plane: Vec3) -> MeshData:
    """Die Fläche nach den abgeschlossenen Etappen ``done``.

    Eine gemerkte Fläche desselben Netzes, deren Züge am Anfang von ``done``
    stehen und dort an einer Etappengrenze enden, wird weitergerechnet: Von
    einer Grenze aus rechnen die übrigen Züge dasselbe wie die ganze Liste.
    """
    surface: MeshData | None = None
    if _last_stage:
        source, known, remembered = _last_stage[0]
        borders = set(np.cumsum([0, *(len(part) for part in stages(done))]).tolist())
        if source is mesh and len(known) in borders and done[: len(known)] == known:
            surface = apply_strokes(remembered, done[len(known) :], centre=plane)
    if surface is None:
        surface = apply_strokes(mesh, done, centre=plane)
    _last_stage[:] = [(mesh, done, surface)]
    return surface


def apply_strokes(
    mesh: MeshData,
    strokes: Sequence[Stroke],
    missed: list[Stroke] | None = None,
    *,
    cancelled: CancelToken | None = None,
    centre: Vec3 | None = None,
    front_only: bool = True,
    mirror_once: bool = True,
    progress: Callable[[float], None] | None = None,
) -> MeshData:
    """Die ganze Strichliste auswerten — Etappe für Etappe, jede in einem Zug.

    ``warp`` ändert die Topologie nicht: Es kommen keine Dreiecke dazu, und
    keines verschwindet. Wer eine feine Falte in ein grobes Netz sculpten will,
    braucht vorher Eckpunkte — dafür gibt es ``remesh_uniform`` (Entscheidung
    E), und der Editor misst und sagt es, bevor jemand vergeblich malt.

    ``centre`` ist der Punkt, durch den die Symmetrieebenen gehen. Ohne
    Angabe die Mitte von ``mesh`` vor dem ersten Zug (:func:`mirror_centre`)
    — einmal genommen, nicht je Etappe, damit die Ebene beim Formen steht.

    ``front_only`` lässt nur dem Pinsel zugewandte Punkte wirken (RM-376),
    ``mirror_once`` einen Zug auf der Symmetrieebene nur einmal (RM-378,
    :func:`_mirror_share`). Beide sind die Vorgabe; alte Formschritte tragen
    ``False`` (Format 41). ``progress`` bekommt den Anteil der übertragenen
    Züge.
    """
    if not strokes:
        return mesh
    plane = mirror_centre(mesh) if centre is None else np.asarray(centre, dtype=float)
    body = mesh.raw
    done = 0
    for part in stages(strokes):
        stage = _Stage(body, plane, front_only=front_only, mirror_once=mirror_once)
        for stroke in part:
            stage.add(stroke, missed, cancelled)
            done += 1
            if progress is not None and done % PROGRESS_STROKES == 0:
                progress(done / len(strokes))
        body = stage.moved()
    if progress is not None:
        progress(1.0)
    return mesh.replacing(body)


#: Wie viele Etappenanfänge die Vorschau einer Formsitzung behält
#: (:class:`SculptPreview`). Jeder ist ein Feld der Ecken; zurückgenommen wird
#: meist der letzte Zug, und weiter zurück rechnet sie vom nächsten behaltenen
#: Anfang aus.
KEPT_STAGES: Final = 12


class SculptPreview:
    """Die Vorschau einer Formsitzung, Zug für Zug (RM-366).

    Das Fenster rechnete nach jedem Klick und jedem Ziehschritt die ganze
    Sitzung neu, im Oberflächen-Thread: an einer Figur mit 145 742 Ecken
    0,03 s nach dem ersten Zug, 5,8 s nach dem vierzigsten im Wechsel mit
    Glätten. Hier steht die laufende Etappe (:class:`_Stage`) mit ihrer
    Fläche, ihrem Suchbaum und ihren Normalen: Ein Zug in ihr kostet seine
    Kugelabfrage, eine neue Etappe einen Durchgang — nach dem vierzigsten
    Zug so viel wie nach dem ersten. Zurückgenommen oder umgestellt wird ab
    dem letzten Etappenanfang, den die Änderung nicht berührt.

    Gerechnet wird dieselbe Folge wie in :func:`apply_strokes`, Etappe für
    Etappe und Zug für Zug; die Vorschau ist bitgleich mit der Operation, die
    beim Verlassen entsteht. Ein Dokumentzustand ist sie nicht (Regel 2).
    """

    def __init__(
        self,
        mesh: MeshData,
        *,
        centre: Vec3 | None = None,
        front_only: bool = True,
        mirror_once: bool = True,
    ) -> None:
        self.mesh = mesh
        self.plane = mirror_centre(mesh) if centre is None else np.asarray(centre, dtype=float)
        self.front_only = front_only
        self.mirror_once = mirror_once
        self.strokes: tuple[Stroke, ...] = ()
        self._starts: dict[int, np.ndarray] = {}
        """Die Ecken am Anfang der Etappen, nach der Nummer ihres ersten Zugs."""
        self._stage: _Stage | None = None
        self._begin = 0
        self._shown: MeshData | None = mesh
        """Die gezeigte Fläche — ``None``, solange sie nach einem Zug noch nicht
        gebaut ist (:meth:`extend`)."""
        self._shown_tree: Any = None
        self._input_tree: Any = None

    @property
    def shown(self) -> MeshData:
        """Die Fläche nach allen Zügen — was die Vorschau zeigt."""
        return self._shown_mesh()

    def _shown_mesh(self) -> MeshData:
        """Die gezeigte Fläche, gebaut, wenn jemand sie braucht."""
        if self._shown is None:
            stage = self._stage
            self._shown = self.mesh if stage is None else self.mesh.replacing(stage.moved())
        return self._shown

    def show(self, strokes: Sequence[Stroke]) -> MeshData:
        """Die Fläche nach ``strokes``, gerechnet ab der letzten Etappe, die
        sich nicht geändert hat."""
        self.extend(strokes)
        return self._shown_mesh()

    def extend(self, strokes: Sequence[Stroke]) -> None:
        """Wie :meth:`show`, ohne die Fläche zu bauen (H6).

        Ein Arbeiter, der mehrere wartende Proben auf einmal rechnet, braucht
        das Netz nur nach der letzten; je Probe ein neues kostete an 241 480
        Dreiecken mehr als die Probe selbst. Der nächste Zug fragt
        :meth:`surface_for`, und das baut die Fläche, wo es sie braucht.
        """
        strokes = tuple(strokes)
        if strokes == self.strokes:
            return
        common = 0
        limit = min(len(strokes), len(self.strokes))
        while common < limit and strokes[common] == self.strokes[common]:
            common += 1
        begins = list(np.cumsum([0, *(len(part) for part in stages(strokes))])[:-1].tolist())
        for index in [index for index in self._starts if index > common]:
            del self._starts[index]
        stage = self._stage
        if not (
            stage is not None
            and self._begin in begins
            and self._begin + len(stage.strokes) <= common
        ):
            stage = None
        start = (
            self._begin
            if stage is not None
            else max(
                [index for index in self._starts if index in begins and index <= common],
                default=0,
            )
        )
        for number, begin in enumerate(begins):
            end = begins[number + 1] if number + 1 < len(begins) else len(strokes)
            if end <= start and begin < start:
                continue
            if stage is None or begin != self._begin:
                body, tree = self._start_of(begin, common)
                stage = _Stage(
                    body,
                    self.plane,
                    front_only=self.front_only,
                    mirror_once=self.mirror_once,
                    tree=tree,
                )
                self._begin = begin
            for stroke in strokes[begin + len(stage.strokes) : end]:
                stage.add(stroke)
            if end < len(strokes):
                self._starts[end] = stage.positions()
                stage = None
        self._keep_few()
        self._stage = stage
        self.strokes = strokes
        self._shown = None
        self._shown_tree = None

    def _start_of(self, begin: int, common: int) -> tuple[trimesh.Trimesh, Any]:
        """Fläche und Suchbaum am Anfang der Etappe, deren erster Zug die
        Nummer ``begin`` hat.

        Beginnt sie, wo die gezeigte Fläche steht, sind es deren Körper und
        Suchbaum: Der Zug, der die Etappe beginnt, hat Normalen und Baum dort
        schon gebraucht (:meth:`surface_for`), und jede neue Etappe rechnete
        beide ein zweites Mal — die Hälfte eines Klicks an einem großen Netz.
        """
        if begin == 0:
            return self.mesh.raw, self._input_tree
        if begin == len(self.strokes) == common:
            return self._shown_mesh().raw, self._shown_tree
        body = trimesh.Trimesh(
            vertices=self._starts[begin], faces=self.mesh.raw.faces, process=False
        )
        return body, None

    def _keep_few(self) -> None:
        """Nur die jüngsten :data:`KEPT_STAGES` Anfänge — ältere rechnet sie nach."""
        for index in sorted(self._starts)[:-KEPT_STAGES]:
            del self._starts[index]

    def surface_for(
        self, stroke: Stroke, *, symmetry: int
    ) -> tuple[MeshData, bool, Any, np.ndarray]:
        """:func:`_surface_for` für den nächsten Zug — mit Suchbaum und Normalen
        der Fläche, auf die er wirkt, aus der laufenden Etappe."""
        cut, radius = stroke.cut, stroke.radius
        stage = self._stage
        if not self.strokes or stage is None:
            if self._input_tree is None:
                self._input_tree = cKDTree(np.asarray(self.mesh.raw.vertices, dtype=float))
            normals = np.asarray(self.mesh.raw.vertex_normals, dtype=float)
            return self.mesh, cut, self._input_tree, normals
        fresh = starts_stage(self.strokes[-1], stroke)
        if not fresh:
            probe = replace(stroke, strength=0.0, symmetry=symmetry)
            places = np.asarray([place for place, _way in _mirrored(probe, self.plane)])
            away, _index = stage.tree.query(places)
            if float(np.min(away)) <= radius * FALLOFF:
                return self.mesh.replacing(stage.body), cut, stage.tree, stage.normals
            away, _index = self._shown_query().query(places)
            if float(np.min(away)) > radius * FALLOFF:
                return self.mesh.replacing(stage.body), False, stage.tree, stage.normals
            cut = True
        shown = self._shown_mesh()
        normals = np.asarray(shown.raw.vertex_normals, dtype=float)
        return shown, cut, self._shown_query(), normals

    def _shown_query(self) -> Any:
        """Der Suchbaum über die gezeigte Fläche — gebaut, wenn ihn ein Zug braucht."""
        if self._shown_tree is None:
            self._shown_tree = cKDTree(np.asarray(self._shown_mesh().raw.vertices, dtype=float))
        return self._shown_tree


# --- Serialisierung -------------------------------------------------------------
#
# Als JSON-Text im Parameter, nach dem Vorbild von ``kind="sketch"`` (§30.1).
# Kurze Schlüssel, weil bis zweitausend Striche im ``project.json`` liegen und
# der Unterschied zwischen ``p`` und ``point`` dort das Doppelte an Bytes ist.


def stroke_count(strokes: Sequence[Stroke]) -> int:
    """Zusammenhängende Mauszüge zählen; alte Einzelproben bleiben Einzelzüge."""
    return sum(
        index == 0 or not stroke.gesture or stroke.gesture != strokes[index - 1].gesture
        for index, stroke in enumerate(strokes)
    )


def _gesture(value: object) -> int:
    """Eine optionale Gestenkennung ist eine nichtnegative ganze Zahl."""
    if type(value) is not int or value < 0:
        raise ValueError(f"not a gesture: {value!r}")
    return value


def _brush(value: object) -> int:
    """Eine Pinselfassung, die dieses Programm rechnen kann (:attr:`Stroke.brush`)."""
    if type(value) is not int or not 1 <= value <= BRUSH:
        raise ValueError(f"not a brush: {value!r}")
    return value


def strokes_to_text(strokes: Sequence[Stroke]) -> str:
    """Die Strichliste als kompakter JSON-Text."""
    return json.dumps(
        [
            {
                "p": [round(value, 6) for value in stroke.point],
                "n": [round(value, 6) for value in stroke.normal],
                "r": round(stroke.radius, 6),
                "s": round(stroke.strength, 6),
                "t": stroke.tool,
                "y": stroke.symmetry,
                "c": stroke.cut,
                **({"g": stroke.gesture} if stroke.gesture else {}),
                **({"v": stroke.brush} if stroke.brush != 1 else {}),
            }
            for stroke in strokes
        ],
        separators=(",", ":"),
    )


def strokes_from_text(text: str) -> list[Stroke]:
    """Zurück aus dem Parameterwert. Leerer Text ist eine leere Sitzung.

    Der Text kommt aus einer Projektdatei oder dem Feld *Striche* — beides
    fremde Eingabe. Ein verdorbener Text endete als „unerwarteter Fehler“ mit
    *Fehler melden*; jetzt ist er ein Eingabefehler mit Ausweg, wie beim
    Skelett (RM-367, W4-3).
    """
    if not text.strip():
        return []
    try:
        entries = json.loads(text)
        strokes = [
            Stroke(
                point=_finite_point(entry["p"]),
                normal=_finite_point(entry["n"]),
                radius=_finite(entry["r"], positive=True),
                strength=_finite(entry["s"]),
                tool=_tool(entry.get("t", "draw")),
                symmetry=int(entry.get("y", 0)),
                cut=bool(entry.get("c", False)),
                gesture=_gesture(entry.get("g", 0)),
                brush=_brush(entry.get("v", 1)),
            )
            for entry in entries
        ]
    except (ValueError, KeyError, TypeError, IndexError, AttributeError) as problem:
        raise ValidationError(
            title=_("Diese Pinselzüge lassen sich nicht lesen."),
            field="strokes",
            detail=_(
                "Erwartet wird die Liste der Züge, wie *Formen* sie schreibt — gemalt, nicht "
                "getippt. Den Schritt neu malen oder das Feld leeren."
            ),
            value=text,
            constraint="unreadable",
        ) from problem
    return strokes


def _finite(value: object, *, positive: bool = False) -> float:
    """Eine endliche Zahl aus dem Text — ``NaN`` und Unendlich sind Lesefehler.

    Sonst endete ``"s": NaN`` als unerwarteter Fehler, ein Radius von null
    oder kleiner nahm Ecken mit, und ``"r": Infinity`` blieb still
    wirkungslos (RM-367, W4-3).
    """
    number = float(value)  # type: ignore[arg-type]
    if not math.isfinite(number) or (positive and number <= 0.0):
        raise ValueError(f"not a usable number: {value!r}")
    return number


def _finite_point(value: object) -> Vec3:
    """Genau drei endliche Koordinaten — eine vierte wurde still abgeschnitten."""
    if not isinstance(value, list | tuple) or len(value) != 3:
        raise ValueError(f"not a point: {value!r}")
    x, y, z = (_finite(entry) for entry in value)
    return (x, y, z)


def _tool(value: object) -> SculptTool:
    """Ein Pinselwerkzeug aus dem Text — ein unbekanntes ist ein Lesefehler,
    kein Zug, der still nichts tut."""
    if value not in get_args(SculptTool):
        raise ValueError(f"unknown sculpt tool {value!r}")
    return cast(SculptTool, value)


# --- operation --------------------------------------------------------------------

#: Wie die Symmetrie der Operation auf die Bitmaske eines Strichs fällt.
SYMMETRY_BITS: Final[dict[str, int]] = {
    "none": 0,
    "x": 1,
    "y": 2,
    "z": 4,
    "xy": 3,
    "xz": 5,
    "yz": 6,
    "xyz": 7,
}

#: Ab wie vielen Etappen das Einbacken angeboten wird (Entscheidung D).
#: Jede Etappe ist ein eigener Durchgang über alle Eckpunkte; bei zwanzig
#: kostet jede Auswertung das Zwanzigfache eines einzelnen.
BAKE_STAGES: Final = 20

#: Und ab wie vielen Zügen, unabhängig von den Etappen. Zwanzigtausend sind
#: rund zwei Megabyte Zahlen — spätestens dort ist die Sitzung ein Datenblock
#: und keine Liste von Entscheidungen mehr.
BAKE_STROKES: Final = 20_000

#: Ab wie vielen mittleren Kantenlängen je Radius ein Pinsel eine glatte Form
#: trägt. Darunter liegen im Pinselgebiet zu wenige Eckpunkte — es entsteht
#: keine Falte, sondern eine Facette. Gemessen an einer Kugel (H2): bei
#: r/2,5 Kantenlänge 22,9° Diederwinkel und 13,6 % Abweichung von der Glocke,
#: bei r/4 noch 5,5 %, bei r/6 2,9 %. Bis RM-560 stand hier 2, und gewarnt
#: wurde erst, wo es schon facettiert.
BRUSH_TO_EDGE: Final = 4.0

#: Auf wie viele Kantenlängen je Radius die Formsitzung ein zu grobes Netz
#: angleicht — feiner als die Warnschwelle, damit die Warnung nach dem
#: Angleichen nicht stehen bleibt (H2: unter 3 % Abweichung).
REFINE_TO_EDGE: Final = 6.0


@op_params
class SculptParams(BaseParams):
    strokes: str = param(
        title=_("Striche"),
        kind="strokes",
        default="",
        placement="advanced",
        doc=_(
            "Die gesammelten Pinselzüge dieser Sitzung. Sie werden gemalt, nicht "
            "getippt — dieses Feld zeigt nur, was dabei entstanden ist."
        ),
    )
    baked: str = param(
        title=_("Eingebacken"),
        kind="source",
        default="",
        placement="advanced",
        doc=_(
            "Ein festgeschriebener Stand dieser Sitzung. Ist er gesetzt, kommt das "
            "Ergebnis von dort und nicht mehr aus den Zügen — die bleiben als Beleg "
            "stehen, wirken aber nicht mehr."
        ),
    )
    symmetry: str = param(
        title=_("Symmetrie"),
        default="none",
        choices=("none", "x", "y", "z", "xy", "xz", "yz", "xyz"),
        doc=_(
            "An welchen Ebenen jeder Strich zusätzlich gespiegelt wird. Nachträglich "
            "änderbar — eine fertige Sitzung lässt sich damit symmetrisch machen."
        ),
    )
    front_only: bool = param(
        title=_("Nur die zugewandte Seite formen"),
        default=True,
        placement="advanced",
        internal=True,
        doc=_("Ein Zug bewegt nur Punkte, die dem Pinsel zugewandt sind."),
    )
    mirror_once: bool = param(
        title=_("Spiegelzug auf der Ebene einmal"),
        default=True,
        placement="advanced",
        internal=True,
        doc=_("Ein Zug auf der Symmetrieebene wirkt einmal, nicht doppelt."),
    )
    mirror_at_body: bool = param(
        title=_("An der Körpermitte spiegeln"),
        default=True,
        placement="advanced",
        doc=_(
            "Die Symmetrieebenen gehen durch die Mitte des Körpers. Ohne Haken gehen "
            "sie durch den Nullpunkt der Szene, wie in älteren Projekten."
        ),
    )
    mirror_fitted: bool = param(
        title=_("Spiegelebene an der Form ausrichten"),
        default=True,
        placement="advanced",
        internal=True,
        doc=_("Die Spiegelebene liegt dort, wo der Körper sich selbst am besten trifft."),
    )


@register_op(
    name="sculpt_strokes",
    result_kind="mesh",
    title=_("Formen"),
    category="mesh",
    params=SculptParams,
    consumes=1,
    produces=1,
    # 1: Spiegelkopien teilen sich glatt (RM-428), der Durchstich nennt
    # seinen Zug (RM-419). 2: Der Befund ``sculpt.subtle`` ist neu gefasst
    # (RM-084); der Plattencache gäbe sonst den alten Satz zurück. 3:
    # Pinselfassung 2, Spiegelebene an der Form, ``too_coarse`` ab r/4 (RM-560).
    cache_version="3",
    doc=_(
        "Trägt Material mit dem Pinsel auf und ab. Der ganze Vorgang ist ein Schritt "
        "im Verlauf und bleibt änderbar, so viele Züge er auch enthält."
    ),
    caveat=_(
        "An einem Teil, das noch bemaßt wird. Ein Strich bleibt im Raum stehen, also erst "
        "konstruieren, dann formen."
    ),
)
def sculpt_strokes(ctx: OpContext) -> OpResult:
    """Eine ganze Sitzung als ein Schritt (Regel 2, seit P16.1)."""
    params = cast(SculptParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    strokes = strokes_from_text(params.strokes)

    if params.baked:
        # Entscheidung D: Der Stand ist festgeschrieben. Gerechnet wird nichts
        # mehr — das ist der Sinn der Sache, denn bei zwanzig Etappen kostet
        # jede Auswertung zwanzig Durchgänge. Reproduzierbar bleibt es
        # trotzdem: Die Quelle reist im Container mit wie jede andere, und was
        # aus ihr kommt, hängt an keinem Rechner und an keiner Sitzung.
        return _from_baked(ctx, source, before, strokes)

    extra = SYMMETRY_BITS.get(params.symmetry, 0)
    if extra:
        strokes = [replace(stroke, symmetry=stroke.symmetry | extra) for stroke in strokes]

    missed: list[Stroke] = []
    # Die Suche nach der Spiegelebene kostet nur, wer spiegelt, und nur an
    # den Ebenen, an denen gespiegelt wird.
    axes = 0
    for stroke in strokes:
        axes |= stroke.symmetry
    centre = mirror_plane(
        before, at_body=params.mirror_at_body, fitted=params.mirror_fitted, axes=axes
    )
    ctx.progress(0.0, str(_("Züge übertragen")))
    after = apply_strokes(
        before,
        strokes,
        missed,
        cancelled=ctx.cancelled,
        centre=centre,
        front_only=params.front_only,
        mirror_once=params.mirror_once,
        progress=lambda share: ctx.progress(0.6 * share, str(_("Züge übertragen"))),
    )
    findings = _sculpting_findings(
        before,
        after,
        strokes,
        source.id,
        missed,
        ctx.profile,
        ctx.cancelled,
        centre,
        lambda share: ctx.progress(0.6 + 0.4 * share, str(_("Wand prüfen"))),
    )
    return OpResult(outputs=[dataclasses.replace(source, mesh=after)], findings=findings)


def _from_baked(
    ctx: OpContext, source: Any, before: MeshData, strokes: Sequence[Stroke]
) -> OpResult:
    """Das eingebackene Netz statt der Rechnung.

    Der Verlust an Änderbarkeit steht als Befund da und nicht nur im Dialog,
    der ihn seinerzeit angekündigt hat: Wer eine Datei ein halbes Jahr später
    öffnet, war bei der Nachfrage nicht dabei.
    """
    params = cast(SculptParams, ctx.params)
    if ctx.sources is None:
        raise ValidationError(
            field="baked",
            detail=_(
                "Der eingebackene Stand lässt sich ohne die Quellen des Projekts nicht lesen."
            ),
            constraint="no_sources",
            suggestions=(CANCEL,),
        )
    payload = ctx.sources.read(params.baked)
    from app.core.ingest.loader import MAX_FILE_BYTES

    # Neue Etappen verwenden dieselbe verlustfreie Form wie der Mesh-Cache.
    # Alte Projekte mit eingebettetem STL bleiben weiterhin lesbar.
    mesh = (
        MeshData.from_bytes(payload, maximum_bytes=MAX_FILE_BYTES)
        if payload.startswith(b"PK\x03\x04")
        else read_mesh(payload, ".stl")
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh)],
        findings=[
            Finding(
                code="sculpt.baked",
                severity="info",
                message=_(
                    "Dieser Stand ist festgeschrieben — die Züge stehen als Beleg da, "
                    "geändert werden kann an ihnen nichts mehr."
                ),
                object_id=source.id,
                values={"strokes": len(strokes), "before": before.triangle_count},
            )
        ],
    )


#: Unter dieser Verschiebung gilt ein Eckpunkt als nicht bewegt: Rauschen der
#: doppelten Genauigkeit, keine Geometrie. Weit unter jeder Toleranz eines
#: Druckers und weit über dem, was ``warp`` an Rundung hinterlässt.
MOVED_EPSILON_MM: Final = 1e-9


def _sculpting_findings(
    before: MeshData,
    after: MeshData,
    strokes: Sequence[Stroke],
    object_id: str,
    missed: Sequence[Stroke],
    profile: Profile,
    cancelled: CancelToken | None = None,
    centre: Vec3 | None = None,
    progress: Callable[[float], None] | None = None,
) -> list[Finding]:
    """Was die Sitzung gekostet hat — und was ihr im Weg stand.

    Vier Dinge, die der Nutzer nicht sehen kann und wissen muss: ob überhaupt
    etwas geschehen ist, ob das Netz für seinen Pinsel fein genug war
    (Entscheidung E), wie viele Durchgänge seine Etappen kosten
    (Entscheidung C), und ob die Fläche sich dabei selbst durchdrungen hat —
    ``warp`` prüft das nicht (Entscheidung L).

    **Das erste ist am 31.08.2026 dazugekommen und war das teuerste.** Der
    Vorbehalt im Register warnt seit jeher: Ein Zug sitzt an einer Stelle im
    Raum, und wer die Form darunter verschiebt, zieht ihm die Fläche weg.
    Geprüft wurde es nicht — die Sitzung meldete auch dann „übertragen", wenn
    kein einziger Eckpunkt sich bewegt hatte. Gemessen am Schaustück des
    vierten Wegs, dessen drei Fingerrillen 18 mm über dem Körper lagen: null
    Abtrag, ein Schritt im Verlauf, und im Bericht die Erfolgsmeldung.
    """
    if not strokes:
        return [
            Finding(
                code="sculpt.empty",
                severity="info",
                message=_("Diese Formsitzung enthält noch keine Züge."),
                object_id=object_id,
            )
        ]

    parts = stages(strokes)

    # Getroffen ist nicht gewirkt: Der Muldenzug des Schaustücks griff 321 von
    # 5770 Eckpunkten und trug dabei 0,41 mm ab, bei eingestellter Stärke 5,0.
    # Gemessen wird deshalb die Verschiebung, und die Grenze kommt aus dem
    # Profil (Regel 7): Was unter einer Schichthöhe bleibt, zeigt der Druck
    # kaum. **Verändert ist der Körper trotzdem** — bis zum 05.09.2026 hieß
    # so eine Sitzung „hat den Körper nicht verändert", und eine
    # Z-Schichthöhe ist kein Maß für eine seitliche Kontur (Gesamtreview,
    # R39). ``warp`` lässt die Topologie stehen, die Punkte sind vergleichbar.
    shifted = np.linalg.norm(
        np.asarray(after.raw.vertices, dtype=float) - np.asarray(before.raw.vertices, dtype=float),
        axis=1,
    )
    moved = float(shifted.max()) if len(shifted) else 0.0
    layer = profile.printer.layer_height

    changed = moved > MOVED_EPSILON_MM
    findings = [
        Finding(
            code="sculpt.applied",
            severity="info",
            message=_("Die Züge dieser Sitzung wurden auf den Körper übertragen."),
            object_id=object_id,
            values={"strokes": len(strokes), "stages": len(parts), "moved_mm": round(moved, 3)},
        )
        if changed
        else Finding(
            code="sculpt.no_effect",
            severity="warning",
            message=_(
                "Diese Formsitzung hat den Körper nicht verändert. Die Züge liegen neben der "
                "Fläche oder sind für dieses Teil zu schwach."
            ),
            object_id=object_id,
            values={"strokes": len(strokes), "stages": len(parts)},
        )
    ]
    if changed and moved < layer:
        findings.append(
            Finding(
                code="sculpt.subtle",
                severity="warning",
                message=_(
                    "Die Züge bewegen die Fläche unter einer Schichthöhe, das druckt sich kaum. "
                    "Vielleicht liegen sie daneben oder sind zu schwach."
                ),
                object_id=object_id,
                values={
                    "strokes": len(strokes),
                    "stages": len(parts),
                    "moved_mm": round(moved, 3),
                    "layer_mm": round(layer, 3),
                },
            )
        )
    if missed:
        findings.append(
            Finding(
                code="sculpt.strokes_missed",
                severity="warning",
                message=_(
                    "Ein Teil der Züge hat die Fläche nicht erreicht, meist weil die Form "
                    "darunter verschoben wurde. Diese Stellen neu formen."
                ),
                object_id=object_id,
                values={"missed": len(missed), "strokes": len(strokes)},
            )
        )

    edge = float(np.median(np.asarray(before.raw.edges_unique_length, dtype=float)))
    finest = min(stroke.radius for stroke in strokes)
    if finest < edge * BRUSH_TO_EDGE:
        findings.append(
            Finding(
                code="sculpt.too_coarse",
                severity="warning",
                message=_(
                    "Der feinste Pinsel ist für die Dreiecke darunter zu klein, dort entsteht "
                    "eine kantige Fläche. Erst „Dreiecke angleichen“."
                ),
                object_id=object_id,
                values={"brush_mm": round(finest, 3), "edge_mm": round(edge, 3)},
            )
        )
    if len(parts) >= BAKE_STAGES or len(strokes) >= BAKE_STROKES:
        # Entscheidung D: angeboten, nie automatisch. Das Einbacken ist ein
        # bewusster Verlust an Änderbarkeit und damit die einzige Stelle in
        # diesem Konzept, an der eine Nachfrage richtig ist (Regel 19 greift
        # nicht, weil die Handlung nicht folgenlos rücknehmbar ist).
        findings.append(
            Finding(
                code="sculpt.consider_baking",
                severity="info",
                message=_(
                    "Diese Sitzung macht jede Auswertung spürbar langsamer. Der Stand lässt sich "
                    "festschreiben, danach sind die Züge nicht mehr änderbar."
                ),
                object_id=object_id,
                values={"strokes": len(strokes), "stages": len(parts)},
            )
        )
    # ``warp`` lässt die Dreiecke, wie sie sind, und Dichtheit hängt nur an
    # ihnen: Mit derselben Dreiecksliste ist das Ergebnis genau so dicht wie
    # der Eingang. Die Prüfung am neuen Netz kostete an 327 680 Dreiecken eine
    # Zehntelsekunde je Auswertung (RM-419).
    same_faces = np.array_equal(np.asarray(after.raw.faces), np.asarray(before.raw.faces))
    if not same_faces and not after.is_watertight and before.is_watertight:
        findings.append(
            Finding(
                code="sculpt.torn",
                severity="warning",
                message=_(
                    "Das Netz ist beim Formen aufgegangen. Reparieren, bevor es "
                    "mit Vereinigen oder Abziehen weitergeht."
                ),
                object_id=object_id,
            )
        )
    elif after.volume <= 0.0 < before.volume:
        findings.append(
            Finding(
                code="sculpt.inverted",
                severity="warning",
                message=_(
                    "Der Körper hat sich beim Formen umgestülpt — für diese Stärke ist "
                    "seine Wand zu dünn."
                ),
                object_id=object_id,
            )
        )
    if changed:
        findings.extend(
            _damage_findings(
                before, after, shifted, object_id, profile, cancelled, strokes, centre, progress
            )
        )
    return findings


#: Wie viele der am tiefsten abgetragenen Eckpunkte die Wandprobe misst. Die
#: dünnste Stelle liegt dort, wo am meisten abgetragen wurde; jeden bewegten
#: Punkt zu messen kostete an einer feinen Figur Sekunden je Auswertung.
WALL_PROBES: Final = 256


def _damage_findings(
    before: MeshData,
    after: MeshData,
    shifted: np.ndarray,
    object_id: str,
    profile: Profile,
    cancelled: CancelToken | None,
    strokes: Sequence[Stroke] = (),
    centre: Vec3 | None = None,
    progress: Callable[[float], None] | None = None,
) -> list[Finding]:
    """Hat ein Zug die Wand durchstoßen oder unter die Mindestwand gedünnt?

    Gefunden in der Gebietsprüfung von Weg 4 (RM-364): Ein *Abtragen* an
    einer 4-mm-Platte drückte die Oberseite durch die Unterseite, ein
    flacherer ließ 0,44 mm Restwand — beide Male stand im Bericht nur
    „übertragen“, und der Export lief ohne Warnung. „Aufgerissen“ kann es
    nicht sehen, denn ``warp`` ändert die Topologie nicht.

    Geprüft wird nur um die bewegten Punkte: Paare mit einem bewegten
    Dreieck, die Wand unter den am tiefsten abgetragenen Punkten. Gemeldet
    wird nur, was der Zug verursacht hat: mehr schneidende Paare mit einem
    bewegten Dreieck als vorher, eine Wand, die dünner wurde.

    Die Schnittsuche lief bis RM-419 über den gemeinsamen Hüllquader aller
    bewegten Punkte; sechs kleine Züge rund um eine Kugel nahmen so jedes
    Dreieck des Körpers mit, und der Formschritt kostete bis zum
    Hundertdreißigfachen. Jetzt sucht :func:`crossings_at` je Zugbereich und
    meldet seinen Fortschritt.
    """
    moved_points = shifted > MOVED_EPSILON_MM
    if not moved_points.any():
        return []
    minimum = profile.minimum_wall_thickness
    vertices = np.asarray(after.raw.vertices, dtype=float)
    earlier = np.asarray(before.raw.vertices, dtype=float)
    faces = np.asarray(after.raw.faces, dtype=np.int64)
    touched = moved_points[faces].any(axis=1)
    # Die längste Kante vorher steht im Netzcache (``too_coarse`` fragt sie
    # auch); jetzt ist keine länger als sie plus zweimal der weiteste Weg.
    lengths = np.asarray(before.raw.edges_unique_length, dtype=float)
    longest_then = float(lengths.max()) if len(lengths) else 0.0
    reach = float(shifted.max())
    longest = (longest_then + 2.0 * reach, longest_then)
    # Eine Suche für alles, was hier fragt: Partner der Schnittsuche um die
    # Zugbereiche, Gegenwände der Wandprobe bis zur Mindestwand, jetzt und —
    # um den weitesten Weg weiter — vorher.
    chosen = np.flatnonzero(touched)
    low, high = face_bounds(vertices, faces[chosen])
    pad = minimum + reach
    padded = [(box_low - pad, box_high + pad) for box_low, box_high in boxes_around(low, high)]
    nearby = np.union1d(faces_touching(vertices, faces, padded, longest[0]), chosen)

    pierced = _new_crossings(
        earlier, vertices, faces, touched, longest, nearby, cancelled, progress
    )
    if pierced is not None:
        count, where, crossing = pierced
        values: dict[str, float | str] = {"triangles": count}
        suggestions: tuple[Action, ...] = (SHOW_LOCATION,)
        culprit = _culprit(strokes, earlier, vertices, faces[crossing], centre)
        if culprit is not None:
            # Gezählt wie im Verlauf, ab eins: Die Handlung nimmt genau diesen
            # Zug aus der Sitzung, als eine rücknehmbare Änderung (RM-419).
            values["stroke"] = culprit + 1
            suggestions = (TAKE_BACK_STROKE, SHOW_LOCATION)
        return [
            Finding(
                code="sculpt.pierced",
                severity="warning",
                message=_(
                    "Ein Zug hat die Fläche durch die Wand dahinter gedrückt, gedruckt bleibt "
                    "die Stelle offen oder doppelt."
                ),
                object_id=object_id,
                values=values,
                location=where,
                suggestions=suggestions,
            )
        ]

    thinnest = _thinned_wall(before, after, faces, nearby, minimum, cancelled)
    if thinnest is None:
        return []
    thickness, where = thinnest
    return [
        Finding(
            code="sculpt.thin_wall",
            severity="warning",
            message=_(
                "Ein Zug hat die Wand dünner gemacht, als dieses Material sicher druckt. Dort "
                "hilft Material auftragen."
            ),
            object_id=object_id,
            values={"thickness_mm": round(thickness, 2), "minimum_mm": round(minimum, 2)},
            location=where,
            suggestions=(SHOW_LOCATION,),
        )
    ]


def _new_crossings(
    earlier: np.ndarray,
    vertices: np.ndarray,
    faces: np.ndarray,
    touched: np.ndarray,
    longest: tuple[float, float],
    nearby: np.ndarray,
    cancelled: CancelToken | None,
    progress: Callable[[float], None] | None = None,
) -> tuple[int, Vec3, np.ndarray] | None:
    """Wie viele Dreiecke sich jetzt an einem bewegten schneiden, wenn es mehr
    schneidende Paare sind als vorher — wo das erste liegt, und welche es sind.

    ``longest`` sind Schranken der längsten Kante jetzt und vorher
    (:func:`faces_touching`), ``nearby`` die Dreiecke, unter denen jetzt die
    Partner liegen. Vorher wird nur gesucht,
    wenn jetzt etwas schneidet: Das ist der seltene Fall, und die Suche dort
    kostet noch einmal dasselbe."""
    now = crossings_at(
        vertices, faces, touched, cancelled, progress=progress, longest=longest[0], nearby=nearby
    )
    if not len(now.first):
        return None
    then = crossings_at(earlier, faces, touched, cancelled, longest=longest[1])
    if len(now.first) <= len(then.first):
        return None
    crossing = np.unique(np.concatenate([now.first, now.second]))
    centre = vertices[faces[int(now.first[0])]].mean(axis=0)
    return len(crossing), (float(centre[0]), float(centre[1]), float(centre[2])), crossing


def _culprit(
    strokes: Sequence[Stroke],
    earlier: np.ndarray,
    vertices: np.ndarray,
    crossing: np.ndarray,
    centre: Vec3 | None,
) -> int | None:
    """Der letzte Zug, dessen Pinsel die durchstoßenen Dreiecke greift.

    Gesucht an den Ecken vor und nach der Sitzung: Ein Zug greift die Fläche
    seiner Etappe, und die liegt zwischen beiden. ``None``, wenn keiner sie
    erreicht — dann bleibt nur *Stelle zeigen*.
    """
    if not strokes:
        return None
    corners = np.unique(np.asarray(crossing, dtype=np.int64).ravel())
    tree = cKDTree(np.concatenate([earlier[corners], vertices[corners]]))
    plane = np.zeros(3) if centre is None else np.asarray(centre, dtype=float)
    for index in range(len(strokes) - 1, -1, -1):
        stroke = strokes[index]
        for place, _way in _mirrored(stroke, plane):
            if tree.query_ball_point(place, stroke.radius * FALLOFF, return_length=True):
                return index
    return None


def _rays_near(
    points: np.ndarray,
    faces: np.ndarray,
    nearby: np.ndarray,
    origins: np.ndarray,
    directions: np.ndarray,
    reach: float,
    cancelled: CancelToken | None,
) -> np.ndarray:
    """Je Strahl der nächste Treffer bis ``reach`` — gegen die Dreiecke, die er
    bis dorthin erreichen kann, je Kasten um nahe Strahlen (:func:`box_groups`).

    Weiter weg kann ``inf`` oder ein Treffer stehen; beides ist mehr als
    ``reach``. Die Proben eines Formschritts sitzen an wenigen Stellen, und
    jede Stelle fragt nur ihre Umgebung statt aller Dreiecke um alle Stellen.
    """
    found = np.full(len(origins), np.inf)
    groups = box_groups(origins - reach, origins + reach)
    corners = points[faces[nearby]]
    low, high = corners.min(axis=1), corners.max(axis=1)
    for group_low, group_high, group in groups:
        mine = np.flatnonzero(np.all(low <= group_high, axis=1) & np.all(high >= group_low, axis=1))
        for members in _clumps(origins, group):
            box_low = origins[members].min(axis=0) - reach
            box_high = origins[members].max(axis=0) + reach
            near = mine[
                np.all(low[mine] <= box_high, axis=1) & np.all(high[mine] >= box_low, axis=1)
            ]
            travel, _hit = ray_hits_batch(
                corners[near],
                origins[members],
                directions[members],
                edge_margin=EPS_GEOM,
                minimum_travel=EPS_GEOM * 100.0,
                cancelled=cancelled,
            )
            found[members] = travel
    return found


#: Wie viele Wandproben sich einen Kasten teilen (:func:`_rays_near`). Die
#: tiefsten Punkte eines Zugs liegen dicht beieinander; in einem Kasten um
#: alle prüfte jeder Strahl jedes Dreieck um alle.
RAY_CLUMP: Final = 16


def _clumps(points: np.ndarray, members: np.ndarray) -> list[np.ndarray]:
    """``members`` in Gruppen zu höchstens :data:`RAY_CLUMP` nahen Punkten,
    geteilt am Median der längsten Ausdehnung."""
    if len(members) <= RAY_CLUMP:
        return [members]
    spread = np.ptp(points[members], axis=0)
    axis = int(np.argmax(spread))
    order = members[np.argsort(points[members, axis], kind="stable")]
    half = len(order) // 2
    return [*_clumps(points, order[:half]), *_clumps(points, order[half:])]


def _thinned_wall(
    before: MeshData,
    after: MeshData,
    faces: np.ndarray,
    nearby: np.ndarray,
    minimum: float,
    cancelled: CancelToken | None,
) -> tuple[float, Vec3] | None:
    """Die dünnste Wand unter den am tiefsten abgetragenen Punkten, wenn sie
    unter ``minimum`` liegt und der Zug sie dünner gemacht hat.

    Gefragt werden nur Dreiecke, die ein Strahl bis ``minimum`` erreichen
    kann: Was weiter weg liegt, macht keine Wand dünn, und vorher galt es als
    dicker als jetzt — dieselbe Antwort, ohne den Rest des Körpers."""
    earlier = np.asarray(before.raw.vertices, dtype=float)
    vertices = np.asarray(after.raw.vertices, dtype=float)
    normals_then = np.asarray(before.raw.vertex_normals, dtype=float)
    # Abgetragen heißt: gegen die Normale von vorher bewegt.
    inward = -np.sum((vertices - earlier) * normals_then, axis=1)
    candidates = np.flatnonzero(inward > MOVED_EPSILON_MM)
    if not len(candidates):
        return None
    probes = candidates[np.argsort(-inward[candidates], kind="stable")[:WALL_PROBES]]
    # Plattformgleich und nur an den Proben: Die Normalen des ganzen neuen
    # Netzes kosteten mehr als die ganze Probe.
    normals_now = stable_vertex_normals_at(after.raw, probes)
    # Dieselben Schwellen wie die Wandstärke (``measure.ray_distances``): Das
    # Dreieck unter dem Startpunkt ist kein Gegenüber.
    now = _rays_near(vertices, faces, nearby, vertices[probes], -normals_now, minimum, cancelled)
    thin = np.isfinite(now) & (now < minimum)
    if not thin.any():
        # Keine Wand unter dem Minimum — wie dick sie vorher war, ändert daran nichts.
        return None
    then = np.full(len(probes), np.inf)
    then[thin] = _rays_near(
        earlier,
        faces,
        nearby,
        earlier[probes[thin]],
        -normals_then[probes[thin]],
        minimum,
        cancelled,
    )
    thinner = thin & (now < then)
    if not thinner.any():
        return None
    index = int(np.flatnonzero(thinner)[np.argmin(now[thinner])])
    point = vertices[probes[index]]
    return float(now[index]), (float(point[0]), float(point[1]), float(point[2]))
