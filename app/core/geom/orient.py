"""Geometrische Druckorientierungen und ihre günstige Vorauswahl (§28.2)."""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, cast

import numpy as np

from app.core import units
from app.core.build_area import placement_offset
from app.core.deferred import trimesh
from app.core.errors import (
    CANCEL,
    CHOOSE_PRINTER,
    OPEN_PRINT_SETTINGS,
    SHOW_SUPPORT_NEED,
    SPLIT_MODEL,
    GeometryError,
)
from app.core.geom.mesh import IntegerGrid, MeshData, stable_normals
from app.core.geom.transform import (
    apply,
    composed,
    moved_points,
    rotation,
    rotation_between,
    translation,
)
from app.core.knowledge.rules import OVERHANG_LIMIT_DEGREES
from app.core.types import BoundingBox, CancelToken, Finding, PrinterProfile, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

#: Wie viele Kandidatenrichtungen über die sechs Achsrichtungen hinaus
#: angesehen werden.
MAX_FACE_CANDIDATES = 12

#: Die sechs Achsrichtungen — die Lagen, die jemand beim Konstruieren gewählt
#: hat. Sie stehen immer vorn in der Kandidatenliste, und die Suche schneidet
#: sie immer (``slice.orientation.search``).
AXES: Final[tuple[Vec3, ...]] = (
    (0.0, 0.0, 1.0),
    (0.0, 0.0, -1.0),
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
)

#: Zielgrenze je Projektionsmatrix; daneben liegen Normalen, Höhen und Masken.
#: Kleine Stapel halten diese Zwischenfelder im Cache. Eine größere Lage bleibt einzeln.
MAX_PROJECTION_VALUES = 100_000

#: Höchstens so viele Arbeiter bewerten Stapel von Lagen gleichzeitig
#: (:func:`evaluate_directions`).
PROJECTION_WORKERS = 6

#: So viele Werte je Feld dürfen alle Arbeiter zusammen in Arbeit haben. Eine
#: Lage hält rund zehn Felder von der Länge des Netzes; bei 1,2 Millionen
#: Werten sind das knapp 100 MB, so viel wie ein Netz mit 1,2 Millionen
#: Dreiecken schon einfädig braucht. Größere Netze rechnen deshalb einfädig
#: weiter, kleinere teilen sich die Lagen.
PARALLEL_PROJECTION_VALUES = 1_200_000

#: Mehr Eckpunkte sieht Qhull für die Kandidatenrichtungen nicht. Die
#: Hüllnormalen sind Vorschläge, die die Schichtanalyse danach beurteilt; ob
#: sie aus allen 655 362 Ecken einer Kugel kommen oder aus jeder dreißigsten,
#: ändert an den großen Hüllflächen nichts — an der Zeit schon: 5,3 s gegen
#: 0,4 s für ``candidates`` an 1,3 Millionen Dreiecken (21.09.2026).
HULL_SAMPLE = 20_000

#: Ab so vielen Eckpunkten fragt :func:`extreme_points` erst eine Stichprobe,
#: ob die konvexe Hülle überhaupt lohnt. Liegt mehr als ``HULL_ROUND_SHARE``
#: der Stichprobe auf ihrer eigenen Hülle, ist der Körper rund wie eine
#: Kugel: Dort ist jede Ecke eine äußerste, die vollständige Hülle kostete
#: 2,9 s an 655 362 Ecken und spart nichts.
HULL_PROBE_FROM = 50_000
HULL_ROUND_SHARE = 0.25

#: Um wie viel die Überhangschwelle eines Einheitsvektors zur druckbaren Seite
#: rückt — eine **Rechengrenze**, keine Geometrietoleranz: Eine Fläche unter
#: genau dem Grenzwinkel liegt mit ihrer Projektion auf der Schwelle, und das
#: Rauschen einer Normalen liegt bei 10⁻¹⁶. In Grad sind es 10⁻⁷ an 45 Grad.
OVERHANG_EDGE: Final = 1e-9

#: So weit darf die schnelle Projektion (BLAS) von der elementweisen Rechnung
#: abweichen, mit der die äußersten Punkte danach exakt bewegt werden. Der
#: gemessene Unterschied liegt bei 10⁻¹⁴ mm (RM-187); das Band ist bewusst
#: fünf Größenordnungen weiter, und trotzdem fallen nur eine Handvoll Ecken
#: hinein.
EXTENT_BAND = 1e-9


class NoFittingOrientationError(GeometryError):
    """Keine der geprüften Lagen passt; Teilung kann diesen Kandidaten verwerfen."""

    default_title = _(
        "Keine geprüfte Lage passt in den Druckbereich. "
        "Wählen Sie einen anderen Drucker oder teilen Sie das Modell."
    )
    default_suggestions = (SPLIT_MODEL, CHOOSE_PRINTER, CANCEL)


class NoStandingOrientationError(GeometryError):
    """Die passenden Lagen tragen das Modell nicht sicher."""

    default_title = _(
        "Das Modell steht in keiner geprüften Lage sicher. "
        "Prüfen Sie Stützen oder eine größere Plattenhaftung."
    )
    default_suggestions = (OPEN_PRINT_SETTINGS, SHOW_SUPPORT_NEED, CANCEL)


@dataclass(frozen=True, slots=True)
class Orientation:
    """Ein Kandidat und was für ihn spricht."""

    direction: Vec3
    """Die Flächennormale, die am Ende nach unten zeigte."""
    footprint: float
    """Fläche, die auf der Platte aufläge, in mm²."""
    overhang: float
    """Fläche, die Stützen bräuchte, in mm²."""
    height: float
    support: float = 0.0
    """Geschätzter Stützraum in mm³: jede Überhangfläche in Projektion, mal
    ihrer Höhe über dem Bett.

    Eine obere Schranke — die Stütze endet in Wahrheit am nächsten Material
    darunter —, aber anders als :attr:`overhang` weiß sie, **wie hoch** ein
    Überhang hängt. Genau das fehlte der Vorauswahl der Suche (RM-190): Das
    Schirmdach des Getränkehalters hängt gekippt über mehr Fläche als
    liegend, aber nahe am Bett; die Schichtanalyse maß dort ein Drittel des
    Stützraums, und die Überhangfläche setzte die Lage auf Rang 123 von 204.
    Die Suche schneidet deshalb auch die Lagen mit der kleinsten Schätzung
    (``slice.orientation.search``); die Heuristik selbst rechnet weiter mit
    Fläche und Überhang, wie :attr:`score` sagt."""

    @property
    def score(self) -> float:
        """Große Aufstandsfläche, wenig Überhang, flache Bauhöhe — in dieser
        Reihenfolge."""
        return self.footprint * 2.0 - self.overhang - self.height * 10.0


@dataclass(slots=True)
class OrientResult:
    mesh: MeshData
    chosen: Orientation
    findings: list[Finding]
    transform: np.ndarray = field(default_factory=lambda: np.eye(4))
    """Die starre Bewegung, die den Körper in diese Lage gebracht hat.

    Ohne sie war *Druckoptimal ausrichten* die einzige bewegende Operation, die
    schwieg: Die Zuordnung (§21.2) muss danach raten, welches Merkmal welches
    ist, und bei einer Drehung um neunzig Grad rät sie falsch. Merkmalskennungen
    wechseln, und jede Passung, die auf eine davon zeigt, zeigt danach ins
    Leere.
    """


def _largest_normals(normals: np.ndarray, areas: np.ndarray, limit: int) -> list[Vec3]:
    """Gruppiert ebene Flächen, bewahrt aber ihre ungerundete Richtung.

    **Die Gruppensummen sind exakt** (``IntegerGrid``): Zwei spiegelgleiche
    Flächen eines symmetrischen Teils haben dieselbe Summe, gleich in welcher
    Reihenfolge ihre Dreiecke stehen, und die lexikographische Ordnung ihrer
    Normalen entscheidet — nicht die letzte Stelle einer Gleitkommasumme
    (RM-187). Die Richtung wird über ``math.hypot`` normiert, nicht über BLAS.
    """
    unique, inverse = np.unique(np.round(normals, 6), axis=0, return_inverse=True)
    inverse = np.asarray(inverse).reshape(-1)
    # In ganzen Zahlen gesammelt — ``bincount`` rechnete die Gewichte in
    # ``float`` und damit wieder in der Reihenfolge der Dreiecke.
    grouped = np.zeros(len(unique), dtype=np.int64)
    np.add.at(grouped, inverse, IntegerGrid.of(areas).steps)
    weighted = np.column_stack(
        [
            np.bincount(inverse, weights=normals[:, axis] * areas, minlength=len(unique))
            for axis in range(3)
        ]
    )
    # unique ist bereits lexikographisch geordnet. Die stabile Flächensortierung
    # erhält diese Reihenfolge bei gleichen Flächensummen.
    order = np.argsort(-grouped, kind="stable")
    found: list[Vec3] = []
    for index in order[:limit]:
        normal = weighted[index]
        length = math.hypot(float(normal[0]), float(normal[1]), float(normal[2]))
        if length > EPS_GEOM:
            found.append(
                (float(normal[0]) / length, float(normal[1]) / length, float(normal[2]) / length)
            )
    return found


def candidates(mesh: MeshData, *, hull_limit: int = 200) -> list[Vec3]:
    """Achsen, tragende Körperflächen und flächengeordnete konvexe Hüllnormalen.

    Die Hülle verwendet sortierte eindeutige Punkte ohne Zufallsstörung.
    Ihre Normalen sind auch bei konkaven oder organischen Körpern geometrisch
    begründet; die tatsächliche Auflage beurteilt erst die Schichtanalyse.

    **Über :data:`HULL_SAMPLE` Ecken nimmt die Hülle jede n-te**, dazu die
    äußersten in den sechs Achsenrichtungen, damit ein Klotz seine Ecken
    behält — dieselbe Stichprobe wie ``mesh.hull_planes``. Die Richtungen
    bleiben deterministisch, weil die Stichprobe aus den sortierten Punkten
    gezogen wird und nicht aus der Reihenfolge der Datei.
    """
    found: list[Vec3] = list(AXES)
    body = mesh.raw
    if not len(body.faces):
        return found

    normals, areas = stable_normals(body)
    found.extend(_largest_normals(normals, areas, MAX_FACE_CANDIDATES))
    vertices = np.unique(np.asarray(body.vertices, dtype=float), axis=0)
    if len(vertices) < 4:
        return found
    if len(vertices) > HULL_SAMPLE:
        step = len(vertices) // HULL_SAMPLE + 1
        extremes = np.concatenate(
            [vertices[vertices[:, axis].argmin()][None] for axis in range(3)]
            + [vertices[vertices[:, axis].argmax()][None] for axis in range(3)]
        )
        vertices = np.unique(np.concatenate([vertices[::step], extremes]), axis=0)
    from scipy.spatial import ConvexHull, QhullError

    try:
        hull = ConvexHull(vertices)
    except QhullError:
        # Ein flaches oder entartetes Netz hat keine dreidimensionale Hülle.
        # Seine eigenen Flächen und Achsen bleiben trotzdem prüfbar.
        return found
    # **Die Richtungen aus den Ecken der Hüllflächen, nicht aus Qhulls
    # Ebenengleichungen** (RM-187): Deren letzte Stelle rechnet Qhulls eigener,
    # je Plattform übersetzter Code, und aus einer Kandidatenrichtung wird
    # die Drehmatrix des ganzen Körpers. Die Ecken sind Eingangspunkte; die
    # Normale daraus rechnet :func:`stable_normals` in Grundrechenarten, die
    # Seite (nach außen) sagt Qhull, denn dafür reicht das Vorzeichen.
    faces = np.asarray(hull.simplices, dtype=np.int64)
    triangles = vertices[faces]
    normals, hull_areas = stable_normals(
        trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    )
    outward = (
        normals[:, 0] * hull.equations[:, 0]
        + normals[:, 1] * hull.equations[:, 1]
        + normals[:, 2] * hull.equations[:, 2]
    ) >= 0.0
    normals = np.where(outward[:, None], normals, -normals)
    usable = hull_areas > 0.0
    found.extend(
        _largest_normals(normals[usable], hull_areas[usable], max(1, hull_limit))
        if len(triangles)
        else []
    )
    return found


def evaluate_direction(
    mesh: MeshData, direction: Vec3, *, overhang_limit: float = OVERHANG_LIMIT_DEGREES
) -> Orientation:
    """Wie der Körper aussähe, stünde er auf dieser Fläche."""
    return evaluate_directions(mesh, [direction], overhang_limit=overhang_limit)[0]


def evaluate_directions(
    mesh: MeshData,
    directions: list[Vec3],
    cancelled: CancelToken | None = None,
    *,
    overhang_limit: float = OVERHANG_LIMIT_DEGREES,
) -> list[Orientation]:
    """Bewertet dieselben Lagen in speicherbegrenzten gemeinsamen Projektionen.

    Öffentlich, weil die Suche (``slice.orientation.search``) ihre Lagen
    ebenfalls stapelt: je Netz ein Aufruf statt einer je Richtung.

    ``overhang_limit`` ist die Überhanggrenze gegen die Senkrechte, mit der
    auch die Schichtanalyse danach urteilt (``Profile.overhang_limit_degrees``
    über ``profiles.analysis_limits``). Ohne Angabe gilt die Startregel. Bis zum
    27.09.2026 stand sie hier fest: Die Vorauswahl zählte am Centauri Carbon 2
    Schrägen zwischen 45 und 60 Grad als Überhang, die der Slicer dort nicht
    stützt, und ordnete Lagen danach, die das Endurteil anders sah.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not directions:
        return []
    body = mesh.raw
    # Normalen, Flächen und Summen so, dass dieselbe Lage auf jeder Maschine
    # dieselben Zahlen bekommt (RM-187): ``stable_normals`` statt der Normalen
    # von ``trimesh`` (BLAS), elementweise Projektionen statt ``@``, und
    # Flächensummen in ganzen Zahlen (``IntegerGrid``) — zwei spiegelgleiche
    # Lagen eines symmetrischen Teils sind damit exakt gleich gut, und die
    # Richtung entscheidet, nicht das Rauschen.
    normals, areas = stable_normals(body)
    grid = IntegerGrid.of(areas)
    vertices = np.asarray(body.vertices)
    referenced = body.referenced_vertices
    if not referenced.all():
        vertices = vertices[referenced]
    centres = np.asarray(body.triangles_center)
    # Mehrere Lagen nur bis zur Grenze gemeinsam projizieren. Ist schon eine
    # Lage größer, bleibt sie einzeln. Einzelabfragen nutzen denselben Weg.
    batch_size = max(
        1, min(len(directions), MAX_PROJECTION_VALUES // max(len(vertices), len(normals), 1))
    )
    # **Genau auf der Grenze ist druckbar, nicht überhängend.** Eine Fase unter
    # dem Grenzwinkel liegt mit ihrer Normalen auf der Schwelle, und ob sie als
    # Überhang zählte, entschied die letzte Stelle einer Projektion — an
    # einem CAD-Teil mit 45-Grad-Fasen der häufigste Fall, nicht der seltene.
    # Die Rechengrenze ``OVERHANG_EDGE`` schiebt die Schwelle um das Rauschen
    # eines Einheitsvektors auf die Seite, die die Regel meint.
    #
    # **Der Sinus, nicht der Kosinus.** Eine Fläche, die um den Winkel a gegen
    # die Senkrechte überhängt, trägt eine Normale mit z = -sin(a); über der
    # Grenze heißt also z < -sin(Grenze). Hier stand der Kosinus, und bei
    # 45 Grad sind beide dieselbe Zahl, bitgenau — mit 60 Grad aber hätte die
    # Vorauswahl schon ab 30 Grad Überhang gezählt statt ab 60 (27.09.2026).
    threshold = -units.exact_sin_degrees(overhang_limit) - OVERHANG_EDGE

    def score(batch: list[Vec3]) -> list[Orientation]:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        verticals = np.asarray([rotation_to_down(direction)[2, :3] for direction in batch])
        vertex_heights = _heights(verticals, vertices)
        normal_heights = _heights(verticals, normals)
        centre_heights = _heights(verticals, centres)
        bottom = vertex_heights.min(axis=1)
        height = vertex_heights.max(axis=1) - bottom
        flat_bottom = (normal_heights < -0.999) & (centre_heights < bottom[:, None] + 0.05)
        downward = normal_heights < threshold
        hanging = downward & ~flat_bottom
        footprints = grid.sums(flat_bottom)
        overhangs = grid.sums(hanging)
        # Der Stützraum unter jeder Überhangfläche bis zum Bett: projizierte
        # Fläche mal Höhe ihrer Mitte. Je Lage exakt summiert (``IntegerGrid``),
        # damit zwei spiegelgleiche Lagen dieselbe Zahl tragen.
        lifted = np.where(
            hanging, areas[None, :] * -normal_heights * (centre_heights - bottom[:, None]), 0.0
        )
        supports = [IntegerGrid.of(row).total() for row in lifted]
        return [
            Orientation(
                direction=direction,
                footprint=float(footprints[index]),
                overhang=float(overhangs[index]),
                height=float(height[index]),
                support=supports[index],
            )
            for index, direction in enumerate(batch)
        ]

    batches = [
        directions[start : start + batch_size] for start in range(0, len(directions), batch_size)
    ]
    # **Die Stapel auf Arbeitern** (RM-266). Jede Lage rechnet für sich — die
    # Rechnung ist Element für Element dieselbe, auf welchem Faden sie läuft,
    # und ``map`` gibt die Stapel in ihrer Folge zurück. NumPy gibt den
    # Interpreter-Lock in diesen Feldern frei. Am Laptop-Ständer beurteilt
    # *Modell teilen* die Vorauswahl je fertiger Hälfte (173 000 Dreiecke,
    # 206 Lagen einzeln): 1,5 s auf einem Faden, 0,6 s auf sechs (unter
    # Fremdlast, 27.09.2026), dieselbe Rangfolge. So viele Arbeiter, wie
    # :data:`PARALLEL_PROJECTION_VALUES` Werte je Feld zulässt — mehr
    # gleichzeitige Stapel hießen mehr Speicher, nicht mehr Tempo.
    workers = min(
        len(batches),
        PROJECTION_WORKERS,
        os.cpu_count() or 1,
        max(1, PARALLEL_PROJECTION_VALUES // max(len(vertices), len(normals), 1)),
    )
    if workers < 2:
        return [entry for batch in batches for entry in score(batch)]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return [entry for scored in pool.map(score, batches) for entry in scored]


def _heights(verticals: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Je Lage und Punkt die Höhe — ``verticals @ points.T`` ohne BLAS (RM-187)."""
    result = np.empty((len(verticals), len(points)))
    scratch = np.empty(len(points))
    # Drei Produkte und zwei Summen in derselben Reihenfolge wie beim Bewegen
    # des Netzes. Nur ein Zwischenfeld je Lage statt mehrerer ganzer Stapel:
    # Bei dichten Teilkörpern kostet deren Speicherverkehr mehr als die Rechnung.
    for index, vertical in enumerate(verticals):
        row = result[index]
        np.multiply(vertical[0], points[:, 0], out=row)
        np.multiply(vertical[1], points[:, 1], out=scratch)
        np.add(row, scratch, out=row)
        np.multiply(vertical[2], points[:, 2], out=scratch)
        np.add(row, scratch, out=row)
    return result


def ranked_orientations(
    mesh: MeshData,
    *,
    limit: int | None = None,
    cancelled: CancelToken | None = None,
    printer: PrinterProfile | None = None,
    margin: float = 0.0,
    overhang_limit: float = OVERHANG_LIMIT_DEGREES,
    standing: Callable[[Orientation], bool] | None = None,
) -> list[Orientation]:
    """Grundflächen nach der billigen Heuristik, beste zuerst.

    Die Schichtanalyse benutzt diese Liste als Vorauswahl: Nur wenige Lagen
    werden danach wirklich geschnitten. Darum ist die Reihenfolge vollständig
    bestimmt — auch bei gleichem Score entscheidet die Richtung und nicht die
    zufällige Reihenfolge eines Sortierverfahrens.

    Doppelte Richtungen fallen vorher heraus. Achsen stehen sowohl fest in der
    Liste als auch unter den größten Flächennormalen; sie ein zweites Mal zu
    prüfen ändert kein Urteil und kostet auf einem dichten Netz spürbar Zeit.

    ``standing`` sagt, ob eine Lage steht. Mit ihm geht der letzte Platz
    einer begrenzten Vorauswahl, wenn keine der vorderen steht, an die Lage
    mit dem kleinsten geschätzten Stützraum (:attr:`Orientation.support`), die
    steht. Die Heuristik wiegt Auflage gegen Überhang, das Endurteil fragt
    zuerst, ob eine Lage steht (``slice.orientation.best_of``). Mit 60 Grad
    reihte sie an einer Auto-Split-Hälfte mit Stift 62 Lagen vor die Lage auf
    dem Stift — Kippungen auf eine Kante und liegende Lagen, die rollen —, und
    keine der drei geschnittenen stand.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    directions: list[Vec3] = []
    for direction in candidates(mesh):
        if any(math.dist(direction, previous) <= EPS_GEOM for previous in directions):
            continue
        directions.append(direction)

    scored = evaluate_directions(mesh, directions, cancelled, overhang_limit=overhang_limit)

    ranked = sorted(
        scored,
        key=lambda entry: (
            -entry.score,
            -entry.footprint,
            entry.overhang,
            entry.height,
            entry.direction,
        ),
    )
    selected: list[Orientation] = []
    wanted = None if limit is None else max(1, limit)
    rest: list[Orientation] = []
    for index, entry in enumerate(ranked):
        # Erst die günstige Reihenfolge bestimmen: Für eine begrenzte
        # Vorauswahl müssen schlechtere Lagen nicht mehr platziert werden.
        if wanted is not None and len(selected) >= wanted:
            rest = ranked[index:]
            break
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if (
            printer is not None
            and fitting_transform(mesh, entry.direction, printer, margin=margin) is None
        ):
            continue
        selected.append(entry)
    if standing is None or not rest or any(standing(entry) for entry in selected):
        return selected
    # Der freie Platz: die Lage mit dem kleinsten geschätzten Stützraum, die
    # steht. Nach der Heuristik stünde oft eine davor, deren Überhänge sie
    # nicht sieht, weil sie nicht weiß, wie hoch sie hängen (RM-190).
    for entry in sorted(rest, key=lambda entry: (entry.support, entry.direction)):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if (
            printer is not None
            and fitting_transform(mesh, entry.direction, printer, margin=margin) is None
        ):
            continue
        if standing(entry):
            selected[-1] = entry
            break
    return selected


def rotation_to_down(direction: Vec3) -> np.ndarray:
    """Die Drehung, die ``direction`` auf -Z bringt.

    Öffentlich, weil die Schichtanalyse sie mitbenutzt: ``slice.orientation``
    trug sie bis zum 24.08.2026 als wortgleiche Kopie, Zeile für Zeile dieselbe
    — und damit dieselbe Rechnung an zwei Stellen, von denen nur eine gepflegt
    worden wäre. Sie gehört hierher, denn hier stehen die Kandidatenrichtungen,
    die sie dreht.
    """
    x, y, z = (float(value) for value in direction)
    length = math.hypot(x, y, z)
    if length <= EPS_GEOM:
        return np.eye(4)
    # **Rodrigues aus den Vektoren, nicht Achse und Winkel** (RM-187). Hier
    # stand ``trimesh.transformations.rotation_matrix(math.acos(…), achse)``:
    # ``acos`` und ``sin``/``cos`` aus der Mathematikbibliothek der Plattform,
    # dazu Normen über BLAS — und mit dieser Matrix wird der ganze Körper
    # gedreht. ``transform.rotation_between`` braucht nur Grundrechenarten
    # und liefert dieselbe kürzeste Drehung.
    #
    # Die Kopfüber-Lage bleibt eine halbe Drehung um **X**, wie bisher —
    # jetzt exakt: ``diag(1, -1, -1)`` statt einer Matrix mit ``sin(π)``
    # ``= 1,2·10⁻¹⁶`` neben den Nullen.
    cross = math.hypot(y, x)
    if cross / length <= EPS_GEOM and z > 0.0:
        return np.diag((1.0, -1.0, -1.0, 1.0))
    return rotation_between((x, y, z), (0.0, 0.0, -1.0))


def extreme_points(mesh: MeshData) -> np.ndarray:
    """Die Ecken, an denen der Körper in irgendeiner Richtung am weitesten
    reicht — einmal je Netz gerechnet, dann im Cache des Netzes.

    Die Hüllbox eines gedrehten Körpers steht an seinen äußersten Ecken, und
    das sind die Ecken seiner konvexen Hülle: Eine lineare Größe nimmt ihr
    Extrem über eine Punktmenge auf deren Hülle an. Wer die Hüllbox von
    zweihundert Drehungen braucht — die Orientierungssuche für jede
    Kandidatenlage —, dreht danach nur noch diese Ecken statt des ganzen
    Netzes: :func:`print_transform` kopierte 1,3 Millionen Dreiecke je
    Kandidat, 18,9 der 37 Sekunden einer Suche (21.09.2026).

    **Rund wie eine Kugel heißt: alle Ecken.** Dort ist jede Ecke eine
    äußerste; Qhull über 655 362 Punkte kostete 2,9 s und gab dieselben
    655 362 zurück. Ab :data:`HULL_PROBE_FROM` Ecken entscheidet deshalb eine
    Stichprobe (:data:`HULL_ROUND_SHARE`), ob die Hülle überhaupt gerechnet
    wird. Ein Klotz aus 1,3 Millionen Dreiecken kommt so auf acht Ecken, die
    Kugel bleibt bei allen — und beide sind für die Hüllbox exakt.

    Exakt heißt hier: bis auf Qhulls eigene Rundungstoleranz. Eine Ecke, die
    Qhull beim Verschmelzen fast koplanarer Flächen als „koplanar" einstuft,
    liegt höchstens um Rundungsfehler (10⁻¹³ mm) außerhalb der gemeldeten
    Hülle; so weit kann die Hüllbox daneben liegen, und ``fits_on_bed`` misst
    mit ``EPS_GEOM``.

    Gezählt werden nur referenzierte Ecken, wie in ``MeshData.bounds``.
    """
    from scipy.spatial import ConvexHull, QhullError

    body = mesh.raw
    cache = getattr(body, "_cache", None)
    if cache is not None:
        cache.verify()
        if "solidon_extreme_points" in cache:
            return cast(np.ndarray, cache["solidon_extreme_points"])
    points = np.asarray(body.vertices, dtype=float)
    referenced = body.referenced_vertices
    if not referenced.all():
        points = points[referenced]
    found = points
    if len(points) >= 4:
        worthwhile = True
        if len(points) > HULL_PROBE_FROM:
            sample = points[:: len(points) // HULL_PROBE_FROM + 1]
            try:
                probe = ConvexHull(sample)
            except QhullError:
                worthwhile = False
            else:
                worthwhile = len(probe.vertices) <= HULL_ROUND_SHARE * len(sample)
        if worthwhile:
            try:
                hull = ConvexHull(points)
            except QhullError:
                # Flach oder entartet — dann bleiben alle Ecken die äußersten.
                pass
            else:
                found = points[np.sort(hull.vertices)]
    if cache is not None:
        cache["solidon_extreme_points"] = found
    return found


def turned_extents(points: np.ndarray, turn: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Kleinste und größte Koordinate der bewegten Punkte — bitgleich mit
    ``apply(mesh, turn).bounds``, wenn ``points`` die äußersten Ecken sind.

    Zwei Rechnungen, eine Antwort: Die schnelle Projektion ``points @ R.T``
    geht durch BLAS und ist auf verschiedenen Maschinen um 10⁻¹⁴ mm
    verschieden (RM-187, :func:`app.core.geom.transform.moved_points`). Sie
    darf deshalb nur **auswählen**: welche Ecken einem Extrem auf
    :data:`EXTENT_BAND` nahekommen. Diese wenigen werden dann elementweise
    bewegt, mit denselben Rechenschritten wie das ganze Netz — und das
    Minimum darüber ist das Minimum über alle, Bit für Bit.

    Die Verschiebung von ``turn`` kommt zuletzt dazu, einmal je Achse: Genau
    so rechnet ``moved_points`` sie je Ecke, und eine einzelne Addition ist
    monoton — das Minimum der verschobenen Ecken ist die verschobene kleinste
    Ecke.
    """
    cells = np.asarray(turn, dtype=float)
    linear = np.eye(4)
    linear[:3, :3] = cells[:3, :3]
    rough = points @ cells[:3, :3].T
    low = np.empty(3)
    high = np.empty(3)
    for axis in range(3):
        column = rough[:, axis]
        near = (column <= column.min() + EXTENT_BAND) | (column >= column.max() - EXTENT_BAND)
        exact = moved_points(points[near], linear)[:, axis]
        low[axis] = exact.min()
        high[axis] = exact.max()
    return low + cells[:3, 3], high + cells[:3, 3]


def _lifted(mesh: MeshData, direction: Vec3) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Die Drehung nach unten und die Hüllbox des gedrehten Körpers."""
    turn = rotation_to_down(direction)
    low, high = turned_extents(extreme_points(mesh), turn)
    return turn, low, high


def _onto_bed(mesh: MeshData, turn: np.ndarray, low: np.ndarray, high: np.ndarray) -> np.ndarray:
    """Die Drehung, ergänzt um den Schritt aufs Bett und zurück über die alte Mitte."""
    offset = (
        mesh.bounds.centre[0] - (high[0] + low[0]) / 2.0,
        mesh.bounds.centre[1] - (high[1] + low[1]) / 2.0,
        -low[2],
    )
    return composed(translation(offset), turn)


def print_transform(mesh: MeshData, direction: Vec3) -> np.ndarray:
    """Die eine Matrix, die den Körper auf diese Fläche stellt: erst drehen,
    dann aufs Bett setzen.

    Als **eine** Bewegung und nicht als zwei, weil genau das der Wert ist, den
    eine Operation melden muss (``OpResult.transform``, §21.2). Zwei
    nacheinander angewandte Matrizen ergeben dasselbe Netz und keine Auskunft.
    Benutzt auch die Schichtanalyse-Suche über die Operation — sie dreht mit
    denselben zwei Schritten, hat aber nur die Richtung zurückgegeben.

    Das Netz selbst wird dafür nicht bewegt: Die Hüllbox der gedrehten Lage
    kommt aus den äußersten Ecken (:func:`extreme_points`,
    :func:`turned_extents`), und die Matrix ist dieselbe wie aus einer Kopie.
    """
    turn, low, high = _lifted(mesh, direction)
    return _onto_bed(mesh, turn, low, high)


@dataclass(frozen=True, slots=True)
class _Placed:
    """Ein bewegter Körper, dessen Hüllbox feststeht, bevor das Netz bewegt ist.

    ``placement_offset`` liest die Hüllbox und — nur wenn das Rechteck an
    einer Sperrfläche oder am Rand scheitert — die tatsächliche Projektion;
    dafür holt es sich das Netz über ``to_mesh`` (``as_mesh_data``). So wird
    von zweihundert Kandidatenlagen nur die kopiert, die den Umweg braucht.
    Eine starre Bewegung ändert an Volumen, Fläche, Dichtheit und Teilen
    nichts; sie kommen vom Ursprung.
    """

    source: MeshData
    matrix: np.ndarray
    bounds: BoundingBox

    def to_mesh(self) -> MeshData:
        return apply(self.source, self.matrix)

    @property
    def vertex_count(self) -> int:
        return self.source.vertex_count

    @property
    def triangle_count(self) -> int:
        return self.source.triangle_count

    @property
    def volume(self) -> float:
        return self.source.volume

    @property
    def area(self) -> float:
        return self.source.area

    @property
    def is_watertight(self) -> bool:
        return self.source.is_watertight

    @property
    def component_count(self) -> int:
        return self.source.component_count

    @property
    def slot_indices(self) -> tuple[int, ...]:
        return self.source.slot_indices


def _shifted(low: np.ndarray, high: np.ndarray, shift: np.ndarray) -> BoundingBox:
    """Die Hüllbox nach einer Verschiebung — je Achse eine Addition, wie
    ``moved_points`` sie zuletzt je Ecke ausführt."""
    return BoundingBox(
        (float(low[0] + shift[0]), float(low[1] + shift[1]), float(low[2] + shift[2])),
        (float(high[0] + shift[0]), float(high[1] + shift[1]), float(high[2] + shift[2])),
    )


def fitting_transform(
    mesh: MeshData, direction: Vec3, printer: PrinterProfile, *, margin: float = 0.0
) -> np.ndarray | None:
    """Eine passende Lage dieser Grundfläche, auch um 90° auf dem Bett gedreht.

    Die äußersten Ecken werden einmal je Richtung gedreht; die Lage um 90° ist
    davon ein Tausch der Achsen — ``x' = -y, y' = x`` Bit für Bit, weil die
    Drehmatrix dort nur Nullen und Einsen enthält — und die Verschiebungen
    kommen als je eine Addition dazu (:func:`turned_extents`). Das Netz
    kopiert erst ``placement_offset``, und nur, wenn es die Projektion braucht.
    """
    turn, low, high = _lifted(mesh, direction)
    initial = _onto_bed(mesh, turn, low, high)
    for yaw in (0.0, 90.0):
        # Zusammengesetzt über ``composed`` und nicht über ``@`` (BLAS): Mit
        # dieser Matrix wird der Körper gedreht, und dieselbe Datei soll auf
        # jeder Maschine dasselbe Teil ergeben (RM-187). Die Vierteldrehung
        # ist exakt (``units.exact_cos_degrees``), ``x' = -y, y' = x``.
        turned = composed(rotation("z", yaw), initial)
        if yaw:
            low, high = (
                np.array([-high[1], low[0], low[2]]),
                np.array([-low[1], high[0], high[2]]),
            )
        box = _shifted(low, high, turned[:3, 3])
        # Eine Drehung in der Platte bewahrt denselben sinnvollen Mittelpunkt.
        centre = translation(
            (
                mesh.bounds.centre[0] - box.centre[0],
                mesh.bounds.centre[1] - box.centre[1],
                0.0,
            )
        )
        turned = composed(centre, turned)
        placed = _Placed(mesh, turned, _shifted(low, high, turned[:3, 3]))

        # Die äußersten Ecken tragen die Hülle der Projektion; mit ihnen
        # fragt die Platzierung nicht jede Ecke des Netzes (RM-190) — und erst,
        # wenn das Rechteck nicht reicht.
        def outline(matrix: np.ndarray = turned) -> np.ndarray:
            return moved_points(extreme_points(mesh), matrix)[:, :2]

        offset = placement_offset(placed, printer, margin=margin, outline=outline)
        if offset is not None:
            return composed(translation(offset), turned)
    return None


def orient_for_print(
    mesh: MeshData,
    *,
    cancelled: CancelToken | None = None,
    printer: PrinterProfile | None = None,
    margin: float = 0.0,
    overhang_limit: float = OVERHANG_LIMIT_DEGREES,
    standing: Callable[[Orientation], bool] | None = None,
) -> OrientResult:
    """Dreht den Körper in die Lage, die der Heuristik am besten gefällt.

    ``overhang_limit`` wie bei :func:`evaluate_directions`: die Grenze, mit der
    die Schichtanalyse danach urteilt.
    ``standing`` prüft den Stand mit dem Druckprofil. Ohne diese Auskunft
    bleibt die reine geometrische Heuristik; die FDM-Operation gibt sie immer mit.
    """
    scored = ranked_orientations(
        mesh, cancelled=cancelled, printer=printer, margin=margin, overhang_limit=overhang_limit
    )
    if not scored:
        raise NoFittingOrientationError()
    best = None
    for entry in scored:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        can_stand = standing is None or standing(entry)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if can_stand:
            best = entry
            break
    if best is None:
        raise NoStandingOrientationError()
    matrix = (
        fitting_transform(mesh, best.direction, printer, margin=margin)
        if printer is not None
        else print_transform(mesh, best.direction)
    )
    assert matrix is not None
    turned = apply(mesh, matrix)

    findings = [
        Finding(
            code="orient.heuristic",
            severity="info",
            message=_(
                "Ausrichtung aus den Flächenrichtungen geschätzt — die Schichtanalyse "
                "urteilt später genauer."
            ),
            values={
                "footprint": round(best.footprint, 1),
                "overhang": round(best.overhang, 1),
                "candidates": len(scored),
            },
        )
    ]
    # Die Überhanggrenze gilt der Düse: Was sie nicht mehr trägt, braucht
    # Stützen. Ein Resinteil hängt ohnehin an Stützen, und ob es welche
    # braucht, entscheidet dort die Saugglocke, nicht der Überhang
    # (Resin-Konzept §5.3, Stufe 2) — bis dahin sagt die Heuristik zu
    # Resin nichts, was nicht gilt.
    if best.overhang > best.footprint and not (printer is not None and printer.is_resin):
        findings.append(
            Finding(
                code="orient.support_likely",
                severity="warning",
                message=_("Auch in der besten Lage bleibt viel Überhang — Stützen sind nötig."),
                # Regel 17: Die Stützkarte zeigt, wo der Überhang bleibt.
                suggestions=(SHOW_SUPPORT_NEED,),
            )
        )
    return OrientResult(mesh=turned, chosen=best, findings=findings, transform=matrix)
