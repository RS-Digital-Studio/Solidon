"""Gewinde an importierter Geometrie messen — ohne Erzeugerwissen (P2.5).

Ein eingelesener Gewindekörper trägt keine Auskunft: keine Steigung, keine
Händigkeit, keine Gangzahl. Was er trägt, sind Kanten, die sich um eine
Achse winden — die Kämme und Füße der Gänge. Hier wird genau das gelesen:

1. **Kandidatenkanten**: jede Kante, deren Kurve weder Strecke noch Kreis
   ist, wird nach **Bogenlänge** abgetastet (``GCPnts_UniformAbscissa``);
   ebene Kurven fallen heraus (die Stirnprofile sind auch B-Splines). Kanten,
   die einen Vertex teilen und dort tangential anschließen, werden ein Zug —
   STEP zerlegt einen Gang in mehrere Kanten.
2. **Achse**: kleinste Quadrate über die Punkte des Zugs — der Zylinder, auf
   dem alle liegen; gestartet aus der SVD und aus den Achsen der analytischen
   Zylinderflächen des Körpers (ein Gewindekern ist meist einer).
3. **Vorschub und Händigkeit**: in einer **rechtshändigen** Achsbasis wird
   der Umlaufwinkel entlang des Zugs entwickelt und ``z`` gegen ``θ/2π``
   regressiert. Die Steigung dieser Geraden ist der Vorschub je Umdrehung,
   ihr Vorzeichen die Händigkeit, das Residuum die Wendelabweichung.
4. **Gangzahl**: die Menge (Radius, Phase) aller Wendeln — Kamm- wie
   Fußkanten — ist unter einer Verschiebung um 1/n des Vorschubs periodisch;
   Teilung = Vorschub / Gangzahl.
5. **Materialseite**: die orientierte Normale der Flächen am Zug zeigt von
   der Achse weg (Bolzen) oder zu ihr hin (Gewindebohrung) — dieselbe Frage
   wie ``helix._material_outside`` am Netz.
6. **Gangtiefe**: Kamm- gegen Fußradius, geprüft gegen ``helix.GROOVE_RANGE``
   — die Bedingung, die auch am Netz allein ablehnt (eine Naht ohne Rille ist
   kein Gewinde). Die Schranken werden aus ``helix`` gelesen, nicht
   abgeschrieben.

**Der Kurvenparameter ist kein Winkel.** Nichts hier liest ``u`` einer
B-Spline: Abgetastet wird nach Bogenlänge, der Winkel kommt aus der
Projektion auf die eingepasste Achse. Deshalb liefert derselbe Körper nach
einer Neuparametrisierung (``NurbsConvert``) oder mit geteilten Trägern
dieselbe Auskunft.

Unzureichende Belege — weniger als eine volle Umdrehung, eine schlechte
Wendel, keine Rille — liefern einen **Grund** und nie eine geratene
Steigung. Jede Schleife nimmt den Abbruch entgegen. Die Eingabe bleibt
unverändert: Gelesen werden Kanten und Flächen, abgelegt wird nichts.

Der Netzweg (``perceive.helix.find_helices``) ist der gewollte Zwilling
dieses Lesers: zwei Rechenkerne, und der Zweig endet ohne ihn — das Netz
hat keine Kanten, der exakte Körper keine Dreiecke, an denen sich die
Konzentration misst (``zwillinge.md``). Geteilt sind die fachlichen Anteile:
``GROOVE_RANGE``, die Festlegung des Nenndurchmessers und die Regel, welche
Einpassungen eine Wendel verschluckt.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from app.core.brep.kernel import Solid, listed, require
from app.core.deferred import least_squares
from app.core.log import get_logger
from app.core.types import CancelToken, Feature, FeatureId, MeasureSource, Vec3
from app.core.units import EPS_GEOM, positive_axis

_log = get_logger(__name__)

Cancel = Callable[[], None] | None

#: Grobe Abtastung je Kante — genug, um Ebenheit und Verkettung zu entscheiden.
SAMPLES_COARSE: Final = 24
#: Feine Abtastung der Züge: so viele Punkte je Umlauf, je Zug mindestens
#: ``SAMPLES_MIN``. Der Abstand hängt am Umfang, nicht am Millimeter: Ein
#: fester Abstand von 0,05 mm tastete 231 Kanten einer verrundeten Lochplatte
#: mit 83 000 Punkten ab, bevor die Ebenheit sie alle aussortierte (Review
#: 21.09.2026); die fünf Korpuswerte sind bei 64 Punkten je Umlauf bis auf
#: 10⁻⁴ an der Steigung dieselben wie bei 0,05 mm.
SAMPLES_PER_TURN: Final = 64
SAMPLES_MIN: Final = 120

#: Was „gleiche Achse“, „gleicher Radius“ und „gleicher Vorschub“ heißt, wenn
#: Züge zu einem Gewinde zusammengefasst werden.
SAME_AXIS_TOLERANCE: Final = 1e-3
RADIUS_TOLERANCE: Final = 2e-3
LEAD_TOLERANCE: Final = 2e-3

#: Wann zwei Zylinderachsen des Körpers dieselbe sind — im Skalarprodukt, für
#: die Startkandidaten der Achseinpassung.
SAME_START_AXIS: Final = 1e-6

#: Wie viele Auswertungen eine Achseinpassung höchstens bekommt — ein
#: Arbeitsbudget, keine Genauigkeit. Eine Wendel von einem guten Start (die
#: SVD-Hauptrichtung, ein Kernzylinder) kommt in vier bis neun zusammen,
#: ein schlechter Start einer echten Wendel in höchstens 104 (gezählt am
#: Korpus, 22.09.2026). Ohne Grenze liefen die Kantenzüge einer Verrundung,
#: die sich um keine Achse winden, bis zur Vorgabe von scipy (500 je Start):
#: acht solche Läufe waren an ``Cat_3.stp`` die halbe Merkmalserkennung.
FIT_EVALUATIONS: Final = 200

#: Unter einer vollen Umdrehung ist eine Steigung eine Vermutung, keine Messung.
MIN_TURNS_FOR_PITCH: Final = 1.0

#: Wie weit ein Punkt von der Wendel abweichen darf, als Anteil des Vorschubs.
HELIX_DEVIATION_SHARE: Final = 0.02

#: Wie weit zwei Phasen (als Anteil eines Vorschubs) auseinanderliegen dürfen,
#: um als dieselbe zu gelten — für die Gangzahl aus der Periodizität.
PHASE_TOLERANCE: Final = 0.03

#: Wie flach eine Kurve relativ zu ihrer Ausdehnung sein darf, um als eben zu gelten.
PLANAR_LIMIT: Final = 1e-4

#: Wie schräg zwei Kanten am gemeinsamen Vertex noch als eine Kurve gelten.
TANGENT_LIMIT_DEG: Final = 10.0

#: Wann zwei Kantenenden derselbe Punkt sind.
SHARED_VERTEX_GAP: Final = 1e-4


@dataclass(frozen=True)
class Chain:
    """Ein Kantenzug mit seinen Bogenlängen-Abtastpunkten."""

    edges: tuple[int, ...]
    points: NDArray[np.float64]
    length: float


@dataclass(frozen=True)
class Winding:
    """Eine gemessene Wendel — ein Zug, eine Achse, ein Vorschub."""

    chain: Chain
    axis: Vec3
    centre: Vec3
    radius: float
    radius_spread: float
    lead: float
    """Vorschub je Umdrehung, positiv. Die Händigkeit steht getrennt."""
    handedness: str
    turns: float
    deviation: float
    """Größte Abweichung eines Punkts von der Wendel, in mm."""
    low: float
    high: float
    phase: float
    taper: float = 0.0
    """Anstieg des Radius je Millimeter entlang der Achse — null am Zylinder.

    Liegt der Zug auf einem Kegel, ist ``radius`` der Radius am Fußpunkt
    ``centre``, sonst das Mittel über den Zug."""


#: Wann zwei Züge denselben Kegel meinen — im Anstieg des Radius je Millimeter.
TAPER_TOLERANCE: Final = 1e-3


@dataclass(frozen=True)
class ThreadReading:
    """Die fachliche Auskunft — oder der Grund, warum es keine gibt."""

    found: bool
    reason: str = ""
    axis: Vec3 | None = None
    centre: Vec3 | None = None
    lead: float | None = None
    pitch: float | None = None
    starts: int = 0
    handedness: str = ""
    internal: bool | None = None
    crest_radius: float | None = None
    root_radius: float | None = None
    depth: float | None = None
    length: float | None = None
    turns: float | None = None
    uncertainty: float | None = None
    """Größte Wendelabweichung über alle beteiligten Züge, in mm."""
    axis_source: MeasureSource = "fit"
    """``native``, wenn ein Kernzylinder die Achse bestätigt hat, sonst ``fit``."""
    members: tuple[Winding, ...] = field(default_factory=tuple)
    """Die Züge, die das Gewinde tragen — ihre Kanten nennen seine Flächen."""
    taper: float = 0.0
    """Halber Kegelwinkel im Bogenmaß, positiv, wenn der Durchmesser entlang
    ``axis`` wächst — null an einem zylindrischen Gewinde. Kamm- und Fußradius
    gelten dann in der Mitte ``centre``."""

    @property
    def diameter(self) -> float | None:
        """Der Nenndurchmesser: außen der Kamm, innen der Grund.

        Dieselbe Festlegung wie ``perceive.helix.Helix.diameter`` — damit ein
        M8-Innengewinde Ø 8 (plus Spiel) meldet und nicht seinen Kern-Ø.
        """
        if self.crest_radius is None or self.root_radius is None:
            return None
        return 2.0 * max(self.crest_radius, self.root_radius)


# --- Kanten lesen ----------------------------------------------------------------------


def _check(check_cancelled: Cancel) -> None:
    if check_cancelled is not None:
        check_cancelled()


def _curve_kind(edge: Any) -> int:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopoDS import TopoDS

    return int(BRepAdaptor_Curve(TopoDS.Edge(edge)).GetType())


def _sample_edge(
    edge: Any, count: int, check_cancelled: Cancel
) -> tuple[NDArray[np.float64], float]:
    """``count`` Punkte nach **Bogenlänge**, nicht nach Parameter — und die Länge."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_AbscissaPoint, GCPnts_UniformAbscissa
    from OCP.TopoDS import TopoDS

    _check(check_cancelled)
    adaptor = BRepAdaptor_Curve(TopoDS.Edge(edge))
    length = float(GCPnts_AbscissaPoint.Length_s(adaptor))
    spread = GCPnts_UniformAbscissa(adaptor, max(2, count))
    if not spread.IsDone():
        return np.zeros((0, 3)), length
    points = []
    for index in range(1, spread.NbPoints() + 1):
        point = adaptor.Value(spread.Parameter(index))
        points.append((point.X(), point.Y(), point.Z()))
    return np.asarray(points, dtype=float), length


def _end_tangents(edge: Any) -> tuple[NDArray[np.float64], ...]:
    """Anfangs- und Endpunkt einer Kante mit ihren Tangenten (Richtung ohne Vorzeichen)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.gp import gp_Pnt, gp_Vec
    from OCP.TopoDS import TopoDS

    adaptor = BRepAdaptor_Curve(TopoDS.Edge(edge))
    result: list[NDArray[np.float64]] = []
    for parameter in (adaptor.FirstParameter(), adaptor.LastParameter()):
        point, tangent = gp_Pnt(), gp_Vec()
        adaptor.D1(parameter, point, tangent)
        direction = np.array([tangent.X(), tangent.Y(), tangent.Z()], dtype=float)
        norm = float(np.linalg.norm(direction))
        result.append(np.array([point.X(), point.Y(), point.Z()], dtype=float))
        result.append(direction / norm if norm > EPS_GEOM else direction)
    return tuple(result)


def _ordered_points(pieces: list[NDArray[np.float64]]) -> NDArray[np.float64]:
    """Die Abtastpunkte eines Zugs in **Kurvenreihenfolge**.

    Die Kantenreihenfolge im Register ist Zufall, und jede Kante kann in beide
    Richtungen laufen. Die Winkelentwicklung braucht die Reihenfolge entlang
    der Kurve: Stück an Stück nach dem nächstliegenden Ende gehängt, gedreht,
    wenn sein Anfang nicht am aktuellen Ende liegt.
    """
    remaining = [points for points in pieces if len(points)]
    if not remaining:
        return np.zeros((0, 3))
    # **Die Enden als Felder, nicht je Paar gefragt.** Dieselbe Rechnung wie
    # vorher Stück gegen Stück in Python — an den 180 Stücken eines Zugs des
    # genähten M3 x 0,5 x 60 waren das 97 000 Normen und 0,6 s (Review
    # 22.09.2026). Reihenfolge und Gleichstände bleiben dieselben: Die
    # Sortierung ist stabil, und ``argmin`` nimmt wie die Schleife den
    # ersten kleinsten Abstand in der Folge Anfang, Ende, nächstes Stück.
    count = len(remaining)
    heads = np.asarray([points[0] for points in remaining])
    tails = np.asarray([points[-1] for points in remaining])
    ends = np.concatenate((heads, tails))
    gaps = np.linalg.norm(ends[:, None, :] - ends[None, :, :], axis=2) <= SHARED_VERTEX_GAP
    own = np.arange(2 * count) % count
    gaps[own[:, None] == own[None, :]] = False
    matched = gaps.any(axis=1)
    loose = (~matched[:count]).astype(int) + (~matched[count:]).astype(int)
    order = sorted(range(count), key=lambda index: -loose[index])
    remaining = [remaining[index] for index in order]
    current = remaining.pop(0)
    first = order[0]
    if loose[first] == 1 and matched[first]:
        current = current[::-1]
    ordered = [current]
    while remaining:
        tail = ordered[-1][-1]
        candidates = np.empty((len(remaining) * 2, 3))
        candidates[0::2] = [points[0] for points in remaining]
        candidates[1::2] = [points[-1] for points in remaining]
        nearest = int(np.argmin(np.linalg.norm(candidates - tail, axis=1)))
        points = remaining.pop(nearest // 2)
        ordered.append(points[::-1] if nearest % 2 else points)
    return np.vstack(ordered)


def _is_planar(points: NDArray[np.float64]) -> bool:
    """Liegen alle Punkte in einer Ebene? Dann ist die Kurve keine Wendel."""
    offset = points - points.mean(axis=0)
    singular = np.linalg.svd(offset, full_matrices=False, compute_uv=False)
    return bool(singular[-1] <= PLANAR_LIMIT * max(float(singular[0]), EPS_GEOM))


def _tangent_at_shared_vertex(
    one: tuple[NDArray[np.float64], ...], other: tuple[NDArray[np.float64], ...]
) -> bool:
    limit = math.cos(math.radians(TANGENT_LIMIT_DEG))
    for point_a, tangent_a in ((one[0], one[1]), (one[2], one[3])):
        for point_b, tangent_b in ((other[0], other[1]), (other[2], other[3])):
            close = np.linalg.norm(point_a - point_b) <= SHARED_VERTEX_GAP
            if close and abs(float(tangent_a @ tangent_b)) >= limit:
                return True
    return False


def candidate_chains(
    solid: Solid,
    check_cancelled: Cancel = None,
    starts: Sequence[NDArray[np.float64]] | None = None,
) -> list[Chain]:
    """Kantenzüge aus allen nicht geradlinigen, nicht kreisförmigen, nicht ebenen Kanten.

    Verkettet werden Kanten, die einen Vertex teilen, dort **tangential**
    anschließen und beide Kandidaten sind — so werden die STEP-Stücke eines
    Gangs wieder ein Zug. Kreise bleiben draußen: Sie sind Ringrillen oder
    Stirnkanten, keine Wendel. Ebene Kandidaten fallen heraus, bevor verkettet
    wird: Die Profilkanten in den Stirnflächen sind ebenfalls B-Splines und
    laufen am Kamm fast tangential ein; über sie wurden Kamm und beide
    Fußwendeln zu einem Zug (gemessen: 36 „Umläufe“, 6 mm Abweichung). Und
    über bloße Nachbarschaft ohne Tangente wurden aus drei Wendeln eine.

    **Grob entscheiden, fein messen.** Ebenheit und Verkettung brauchen
    ``SAMPLES_COARSE`` Punkte je Kante; erst die Züge, die übrig bleiben,
    werden mit ``SAMPLES_PER_TURN`` Punkten je Umlauf abgetastet — der Umlauf
    kommt aus dem Radius einer Einpassung an die groben Punkte, ``starts``
    sind dieselben Startachsen wie in der Messung.
    """
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as AncestorMap,
    )
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopExp import TopExp

    edge_map = ShapeMap()
    TopExp.MapShapes_s(solid.shape, TopAbs_EDGE, edge_map)
    edges = [edge_map.FindKey(index) for index in range(1, edge_map.Extent() + 1)]
    candidate = [
        _curve_kind(edge) not in (int(GeomAbs_Line), int(GeomAbs_Circle)) for edge in edges
    ]
    sampled: dict[int, tuple[NDArray[np.float64], float]] = {}
    for index, edge in enumerate(edges):
        if not candidate[index]:
            continue
        _check(check_cancelled)
        points, length = _sample_edge(edge, SAMPLES_COARSE, check_cancelled)
        sampled[index] = (points, length)
        if len(points) < 4 or _is_planar(points):
            candidate[index] = False
    by_vertex = AncestorMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_VERTEX, TopAbs_EDGE, by_vertex)
    neighbours: dict[int, set[int]] = {index: set() for index in range(len(edges))}
    ends = {index: _end_tangents(edge) for index, edge in enumerate(edges) if candidate[index]}
    for slot in range(1, by_vertex.Extent() + 1):
        _check(check_cancelled)
        siblings = [edge_map.FindIndex(item) - 1 for item in listed(by_vertex.FindFromIndex(slot))]
        siblings = [index for index in siblings if index >= 0 and candidate[index]]
        for one in siblings:
            for other in siblings:
                if one < other and _tangent_at_shared_vertex(ends[one], ends[other]):
                    neighbours[one].add(other)
                    neighbours[other].add(one)
    seen: set[int] = set()
    chains: list[Chain] = []
    for start in range(len(edges)):
        if not candidate[start] or start in seen:
            continue
        stack, members = [start], []
        while stack:
            _check(check_cancelled)
            index = stack.pop()
            if index in seen:
                continue
            seen.add(index)
            members.append(index)
            stack.extend(sorted(neighbours[index] - seen))
        coarse = _ordered_points([sampled[index][0] for index in members])
        total = sum(sampled[index][1] for index in members)
        if not len(coarse):
            continue
        # Der Umfang des Zugs bestimmt die Abtastung: so viele Punkte je Umlauf
        # wie ``SAMPLES_PER_TURN``, verteilt auf die Kanten nach ihrer Länge.
        _axis, _foot, radius, _spread, _native = fit_axis(coarse, starts, check_cancelled)
        wanted = SAMPLES_MIN
        if math.isfinite(radius) and radius > EPS_GEOM:
            wanted = max(SAMPLES_MIN, math.ceil(SAMPLES_PER_TURN * total / (math.tau * radius)))
        fine = []
        for index in members:
            _check(check_cancelled)
            share = sampled[index][1] / total if total > 0.0 else 1.0 / len(members)
            count = max(SAMPLES_COARSE, math.ceil(wanted * share))
            fine.append(_sample_edge(edges[index], count, check_cancelled)[0])
        ordered = _ordered_points(fine)
        if len(ordered):
            chains.append(Chain(tuple(sorted(members)), ordered, total))
    return chains


# --- Achse ------------------------------------------------------------------------------


def _basis(axis: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Eine rechtshändige Basis (erste, zweite, Achse) — wie ``helix._best_pitch``."""
    helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = np.cross(axis, helper)
    first /= np.linalg.norm(first)
    second = np.cross(axis, first)
    return first, second


def cylinder_axes(solid: Solid, check_cancelled: Cancel = None) -> list[NDArray[np.float64]]:
    """Achsen der analytischen Zylinderflächen des Körpers — Kandidaten für den Start.

    Ein Gewindekern ist meist ein Zylinder; seine Achse ist dann die beste
    Startschätzung, vor allem für kurze Stücke unter einem Umlauf.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopoDS import TopoDS

    found: list[NDArray[np.float64]] = []
    for face in solid.faces():
        _check(check_cancelled)
        adaptor = BRepAdaptor_Surface(TopoDS.Face(face))
        if adaptor.GetType() != GeomAbs_Cylinder:
            continue
        direction = adaptor.Cylinder().Axis().Direction()
        axis = np.array([direction.X(), direction.Y(), direction.Z()], dtype=float)
        if not any(abs(abs(float(axis @ other)) - 1.0) <= SAME_START_AXIS for other in found):
            found.append(axis)
    return found


def fit_axis(
    points: NDArray[np.float64],
    starts: Sequence[NDArray[np.float64]] | None = None,
    check_cancelled: Cancel = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64], float, float, bool]:
    """Der Zylinder, auf dem die Punkte liegen: Achse, Fußpunkt, Radius, Streuung —
    und ob ein übergebener Kandidat (ein Zylindernachbar) der beste Start war.

    Kleinste Quadrate über den radialen Abstand. Gestartet wird von der
    SVD-Hauptrichtung (lange Züge), der SVD-Nebenrichtung (kurze Bögen unter
    einem Umlauf: dort ist die Kreisnormale die Achse) und jedem übergebenen
    Kandidaten; es gilt der Start mit der kleinsten Reststreuung.
    """
    _check(check_cancelled)
    centre = points.mean(axis=0)
    offset = points - centre
    _, _, directions = np.linalg.svd(offset, full_matrices=False)
    candidates: list[tuple[NDArray[np.float64], bool]] = [
        (directions[0], False),
        (directions[-1], False),
        *((start, True) for start in (starts or [])),
    ]
    best: tuple[float, NDArray[np.float64], NDArray[np.float64], float, bool] | None = None
    for start, from_cylinder in candidates:
        _check(check_cancelled)
        start_axis = np.asarray(start, dtype=float)
        start_axis = start_axis / np.linalg.norm(start_axis)
        first, second = _basis(start_axis)

        def unpack(
            values: NDArray[np.float64],
            start_axis: NDArray[np.float64] = start_axis,
            first: NDArray[np.float64] = first,
            second: NDArray[np.float64] = second,
        ) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
            axis = start_axis + values[0] * first + values[1] * second
            axis /= np.linalg.norm(axis)
            foot = centre + values[2] * first + values[3] * second
            return axis, foot, float(values[4])

        def residual(values: NDArray[np.float64], unpack: Any = unpack) -> NDArray[np.float64]:
            _check(check_cancelled)
            axis, foot, radius = unpack(values)
            relative = points - foot
            along = relative @ axis
            across = relative - np.outer(along, axis)
            return np.asarray(np.linalg.norm(across, axis=1) - radius, dtype=float)

        def jacobian(
            values: NDArray[np.float64],
            start_axis: NDArray[np.float64] = start_axis,
            first: NDArray[np.float64] = first,
            second: NDArray[np.float64] = second,
        ) -> NDArray[np.float64]:
            """Die Ableitungen des radialen Abstands nach den fünf Unbekannten.

            **Ausgerechnet, nicht abgetastet.** Mit Differenzenquotienten rief
            die Ausgleichsrechnung den Rest je Schritt sechsmal auf und
            verbrachte an ``Cat_3.stp`` — einem Teil ohne Gewinde — 3,1 von
            4,8 Sekunden der Merkmalserkennung darin (Review 22.09.2026).
            Mit ``w = s + a e1 + b e2``, der Achse ``u = w / |w|``, dem Rest
            ``q = p - f`` und seinem Anteil ``s = q u`` entlang, ``d`` quer zur
            Achse, gilt ``d|d|/da = -s (d e1) / (|w| |d|)`` und
            ``d|d|/dc = -(d e1) / |d|`` (``c`` verschiebt den Fußpunkt entlang
            ``e1``), entsprechend für ``b`` und ``d`` mit ``e2``, und
            ``d|d|/dr = -1``.
            """
            _check(check_cancelled)
            direction = start_axis + values[0] * first + values[1] * second
            length = float(np.linalg.norm(direction))
            axis = direction / length
            foot = centre + values[2] * first + values[3] * second
            relative = points - foot
            along = relative @ axis
            across = relative - np.outer(along, axis)
            distance = np.maximum(np.linalg.norm(across, axis=1), np.finfo(float).tiny)
            on_first = (across @ first) / distance
            on_second = (across @ second) / distance
            return np.column_stack(
                (
                    -along * on_first / length,
                    -along * on_second / length,
                    -on_first,
                    -on_second,
                    -np.ones(len(points)),
                )
            )

        along0 = offset @ start_axis
        radius0 = float(np.linalg.norm(offset - np.outer(along0, start_axis), axis=1).mean())
        fit = least_squares(
            residual,
            np.array([0.0, 0.0, 0.0, 0.0, radius0]),
            jac=jacobian,
            method="lm",
            max_nfev=FIT_EVALUATIONS,
        )
        axis, foot, radius = unpack(fit.x)
        if radius <= EPS_GEOM:
            continue
        relative = points - foot
        along = relative @ axis
        spread = float(
            np.abs(np.linalg.norm(relative - np.outer(along, axis), axis=1) - radius).max()
        )
        if best is None or spread < best[0]:
            best = (spread, axis, foot, radius, from_cylinder)
    if best is None:
        return directions[0], centre, 0.0, math.inf, False
    spread, axis, foot, radius, _won = best
    axis = np.asarray(positive_axis((float(axis[0]), float(axis[1]), float(axis[2]))), dtype=float)
    # **Bestätigt heißt: ein Kernzylinder zeigt in dieselbe Richtung** — nicht,
    # dass sein Start gewonnen hat. Zwei Starts enden auf derselben Achse, und
    # welcher die kleinere Streuung hat, ist eine Frage der letzten Stellen.
    confirmed = any(
        abs(abs(float(axis @ np.asarray(start, dtype=float))) - 1.0) <= SAME_AXIS_TOLERANCE
        for start in (starts or [])
    )
    return axis, foot, radius, spread, confirmed


def _tapered(along: NDArray[np.float64], radii: NDArray[np.float64]) -> tuple[float, float, float]:
    """Radius am Fußpunkt, Anstieg je Millimeter entlang der Achse und Reststreuung.

    Die Gerade ``r = r0 + k·z`` durch die Radien eines Zugs. Ein zylindrisches
    Gewinde hat ``k ≈ 0``; ein kegeliges Rohrgewinde (1:16 auf den
    Durchmesser) ``k = 1/32``.
    """
    design = np.column_stack((np.ones(len(along)), along))
    coefficients, *_ = np.linalg.lstsq(design, radii, rcond=None)
    spread = float(np.abs(design @ coefficients - radii).max())
    return float(coefficients[0]), float(coefficients[1]), spread


def _is_tapered(along: NDArray[np.float64], slope: float, radius: float) -> bool:
    """Ob der Radius eines Zugs über seine Länge merklich wächst — ein Kegel, kein Zylinder.

    Gemessen wird die Änderung über die ganze Spanne gegen dieselbe
    Radiustoleranz, mit der Züge zu einer Wendel gruppiert werden: Was darunter
    bleibt, ist ein Zylinder mit Rauschen.
    """
    span = float(along.max() - along.min())
    return abs(slope) * span > RADIUS_TOLERANCE * max(1.0, radius)


def fit_cone_axis(
    points: NDArray[np.float64],
    axis: NDArray[np.float64],
    foot: NDArray[np.float64],
    radius: float,
    slope: float,
    check_cancelled: Cancel = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64], float, float, float]:
    """Der Kegel, auf dem die Punkte liegen: Achse, Fußpunkt, Radius am Fuß, Anstieg, Streuung.

    Dieselbe Ausgleichsrechnung wie :func:`fit_axis`, mit einer sechsten
    Unbekannten: Der Sollradius ist ``r0 + k·s`` statt ``r``, ``s`` der Anteil
    entlang der Achse. Gestartet wird an der Zylinderachse, die schon passt —
    an einem kegeligen Gewinde liegt sie wenige Hundertstel neben der wahren,
    und die Wendel wich dort um 6 µm ab (``konisch.step``, 22.09.2026).
    Ableitungen ausgerechnet: zu denen des Zylinders kommt je Unbekannte der
    Anteil ``-k·ds``, mit ``ds/da = (q e1 - s (u e1)) / |w|`` und
    ``ds/dc = -(u e1)``, dazu ``d/dk = -s``.
    """
    _check(check_cancelled)
    start_axis = np.asarray(axis, dtype=float)
    start_axis = start_axis / np.linalg.norm(start_axis)
    first, second = _basis(start_axis)
    base = np.asarray(foot, dtype=float)

    def unpack(values: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        direction = start_axis + values[0] * first + values[1] * second
        return direction / np.linalg.norm(direction), base + values[2] * first + values[3] * second

    def residual(values: NDArray[np.float64]) -> NDArray[np.float64]:
        _check(check_cancelled)
        unit, origin = unpack(values)
        relative = points - origin
        along = relative @ unit
        across = relative - np.outer(along, unit)
        return np.asarray(
            np.linalg.norm(across, axis=1) - values[4] - values[5] * along, dtype=float
        )

    def jacobian(values: NDArray[np.float64]) -> NDArray[np.float64]:
        _check(check_cancelled)
        direction = start_axis + values[0] * first + values[1] * second
        length = float(np.linalg.norm(direction))
        unit = direction / length
        origin = base + values[2] * first + values[3] * second
        relative = points - origin
        along = relative @ unit
        across = relative - np.outer(along, unit)
        distance = np.maximum(np.linalg.norm(across, axis=1), np.finfo(float).tiny)
        on_first = (across @ first) / distance
        on_second = (across @ second) / distance
        slope_now = values[5]
        tilt_first = (relative @ first - along * float(unit @ first)) / length
        tilt_second = (relative @ second - along * float(unit @ second)) / length
        return np.column_stack(
            (
                -along * on_first / length - slope_now * tilt_first,
                -along * on_second / length - slope_now * tilt_second,
                -on_first + slope_now * float(unit @ first),
                -on_second + slope_now * float(unit @ second),
                -np.ones(len(points)),
                -along,
            )
        )

    fit = least_squares(
        residual,
        np.array([0.0, 0.0, 0.0, 0.0, radius, slope]),
        jac=jacobian,
        method="lm",
        max_nfev=FIT_EVALUATIONS,
    )
    unit, origin = unpack(fit.x)
    spread = float(np.abs(residual(fit.x)).max())
    return unit, origin, float(fit.x[4]), float(fit.x[5]), spread


# --- Wendel je Zug ------------------------------------------------------------------------


def measure_winding(
    chain: Chain,
    starts: Sequence[NDArray[np.float64]] | None = None,
    frame: tuple[NDArray[np.float64], NDArray[np.float64]] | None = None,
    check_cancelled: Cancel = None,
    *,
    tapered: bool = False,
) -> tuple[Winding, bool] | None:
    """Vorschub, Händigkeit und Wendelabweichung eines Zugs — oder nichts.

    Mit ``frame`` (Achse, Fußpunkt) wird nicht neu eingepasst: So bekommen
    alle Züge eines Körpers dieselbe Basis, und ihre Phasen sind vergleichbar.
    Das zweite Ergebnis sagt, ob ein Zylindernachbar die Achse bestätigt hat.

    **Ein Zug darf auf einem Kegel liegen** (P2.5, kegelige Rohrgewinde):
    Wächst sein Radius entlang der Achse über die Radiustoleranz hinaus, wird
    ein Kegel eingepasst (:func:`fit_cone_axis`), und der Zug trägt den
    Anstieg ``taper`` und seinen Radius am Fußpunkt. Im Rahmen eines
    kegeligen Bezugszugs (``tapered``) bekommt jeder Zug dieselbe Gerade
    ``r = r0 + k·z``. Ein zylindrisches Gewinde bleibt, wie es war: Radius
    als Mittel, kein Anstieg.
    """
    points = chain.points
    if len(points) < 8:
        return None
    native = False
    slope = 0.0
    if frame is None:
        axis, foot, radius, spread, native = fit_axis(points, starts, check_cancelled)
        if radius > EPS_GEOM:
            relative = points - foot
            along = relative @ axis
            radii = np.linalg.norm(relative - np.outer(along, axis), axis=1)
            base, rising, linear = _tapered(along, radii)
            if _is_tapered(along, rising, radius) and linear < spread:
                axis, foot, radius, slope, spread = fit_cone_axis(
                    points, axis, foot, base, rising, check_cancelled
                )
    else:
        axis, foot = frame
        relative = points - foot
        along = relative @ axis
        radii = np.linalg.norm(relative - np.outer(along, axis), axis=1)
        if tapered:
            radius, slope, spread = _tapered(along, radii)
        else:
            radius = float(radii.mean())
            spread = float(np.abs(radii - radius).max())
    if radius <= EPS_GEOM:
        return None
    first, second = _basis(axis)
    relative = points - foot
    along = relative @ axis
    angle = np.unwrap(np.arctan2(relative @ second, relative @ first))
    turns = float((angle.max() - angle.min()) / math.tau)
    if turns <= 1e-6:
        return None
    # z = z0 + lead · θ/2π — die Gerade durch die Abtastpunkte.
    design = np.column_stack((np.ones(len(along)), angle / math.tau))
    coefficients, *_ = np.linalg.lstsq(design, along, rcond=None)
    lead = float(coefficients[1])
    deviation = float(np.abs(design @ coefficients - along).max())
    if abs(lead) <= EPS_GEOM:
        return None
    handedness = "right" if lead > 0.0 else "left"
    phase = float((along - lead * angle / math.tau).mean() % abs(lead))
    winding = Winding(
        chain=chain,
        axis=(float(axis[0]), float(axis[1]), float(axis[2])),
        centre=(float(foot[0]), float(foot[1]), float(foot[2])),
        radius=float(radius),
        radius_spread=spread,
        lead=abs(lead),
        handedness=handedness,
        turns=turns,
        deviation=deviation,
        low=float(along.min()),
        high=float(along.max()),
        phase=phase,
        taper=slope,
    )
    return winding, native


# --- Materialseite ---------------------------------------------------------------------------


def _faces_at(solid: Solid, chains: Sequence[Chain], check_cancelled: Cancel) -> list[int]:
    """Die nativen Flächen, die die Kanten dieser Züge tragen — aufsteigend."""
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as AncestorMap,
    )
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp

    edge_map = ShapeMap()
    TopExp.MapShapes_s(solid.shape, TopAbs_EDGE, edge_map)
    by_edge = AncestorMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, by_edge)
    face_map = ShapeMap()
    for face in solid.faces():
        face_map.Add(face)
    found: set[int] = set()
    for chain in chains:
        for index in chain.edges:
            _check(check_cancelled)
            slot = by_edge.FindIndex(edge_map.FindKey(index + 1))
            if slot == 0:
                continue
            for face in listed(by_edge.FindFromIndex(slot)):
                if face_map.Contains(face):
                    found.add(face_map.FindIndex(face) - 1)
    return sorted(found)


def material_outside(solid: Solid, winding: Winding, check_cancelled: Cancel = None) -> bool | None:
    """Zeigt die Fläche neben dem Zug von der Achse weg?

    Gelesen an den Flächen, die die Kanten des Zugs tragen: orientierte
    Normale (``BRepLProp_SLProps`` mit der Flächenorientierung) an der
    Flächenmitte, gemittelt gegen die radiale Richtung. Bolzen: positiv.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.TopoDS import TopoDS

    faces = solid.faces()
    axis = np.asarray(winding.axis)
    centre = np.asarray(winding.centre)
    votes: list[float] = []
    for index in _faces_at(solid, [winding.chain], check_cancelled):
        _check(check_cancelled)
        face = faces[index]
        surface = BRepAdaptor_Surface(TopoDS.Face(face))
        u = (surface.FirstUParameter() + surface.LastUParameter()) / 2.0
        v = (surface.FirstVParameter() + surface.LastVParameter()) / 2.0
        props = BRepLProp_SLProps(surface, u, v, 1, 1e-6)
        if not props.IsNormalDefined():
            continue
        normal = props.Normal()
        sign = -1.0 if face.Orientation() == TopAbs_REVERSED else 1.0
        point = props.Value()
        relative = np.array([point.X(), point.Y(), point.Z()]) - centre
        across = relative - axis * (relative @ axis)
        if np.linalg.norm(across) <= EPS_GEOM:
            continue
        outward = across / np.linalg.norm(across)
        votes.append(sign * float(np.array([normal.X(), normal.Y(), normal.Z()]) @ outward))
    if not votes:
        return None
    return float(np.mean(votes)) > 0.0


# --- Zusammenfassen ---------------------------------------------------------------------------


def _phase_gap(one: float, other: float) -> float:
    """Abstand zweier Phasen auf dem Kreis der Länge 1."""
    gap = abs(one - other) % 1.0
    return min(gap, 1.0 - gap)


def _coaxial(one: Winding, other: Winding) -> bool:
    """Ob zwei Züge dieselbe Achslinie messen — Richtung und Fußpunkt."""
    axis, other_axis = np.asarray(one.axis), np.asarray(other.axis)
    if abs(abs(float(axis @ other_axis)) - 1.0) > SAME_AXIS_TOLERANCE:
        return False
    gap = np.asarray(one.centre) - np.asarray(other.centre)
    across = gap - other_axis * float(gap @ other_axis)
    return float(np.linalg.norm(across)) <= RADIUS_TOLERANCE * max(1.0, other.radius)


def _same_helices(windings: Sequence[Winding], lead: float) -> list[list[Winding]]:
    """Stücke derselben Wendel zusammen: gleicher Radius, gleiche Phase — mit Toleranz.

    Eine Wendel = ein Radius und eine Phase je Vorschub. Bis zum 21.09.2026
    entschied ``round``: Zwei Stücke mit den Phasen 0,00499 und 0,00501 fielen
    in zwei Gruppen, die Gangzahl halbierte sich, und der Körper galt als
    „nur 0,60 Umläufe belegt“ (Regel 6 — kein Vergleich über Rundung).
    Gruppiert wird wie in :func:`starts_from_periodicity`, mit
    ``RADIUS_TOLERANCE`` und ``PHASE_TOLERANCE`` auf dem Kreis.
    """
    groups: list[list[Winding]] = []
    for winding in windings:
        phase = (winding.phase / lead) % 1.0
        for group in groups:
            radius = float(np.mean([w.radius for w in group]))
            reference = float(np.mean([(w.phase / lead) % 1.0 for w in group]))
            if (
                abs(winding.radius - radius) <= RADIUS_TOLERANCE
                and _phase_gap(phase, reference) <= PHASE_TOLERANCE
            ):
                group.append(winding)
                break
        else:
            groups.append([winding])
    return groups


def starts_from_periodicity(helices: Sequence[tuple[float, float]]) -> int:
    """Die Gangzahl n, unter der die Menge (Radius, Phase) periodisch ist.

    Ein n-gängiges Gewinde wiederholt **alle** seine Wendeln — Kamm- wie
    Fußkanten, auch die beiden Kanten eines flachen Kamms — nach einer
    Verschiebung um 1/n des Vorschubs. Nur die Kammphasen zu zählen trägt
    nicht: Ein flacher Kamm hat zwei Kanten je Gang, und deren Abstände sind
    nicht gleichmäßig (gemessen am zweigängigen Referenzkörper: vier
    Kammkanten mit Abständen 0,35/0,15/0,35/0,15 — Gangzahl fälschlich 1).
    Geprüft wird von der größten möglichen Gangzahl abwärts; 1 ist der
    Rückfall, wenn keine Verschiebung die Menge auf sich selbst abbildet.
    """
    entries = list(helices)
    for count in range(len(entries), 1, -1):
        shift = 1.0 / count
        if all(
            any(
                abs(radius - other_radius) <= RADIUS_TOLERANCE
                and _phase_gap(phase + shift, other_phase) <= PHASE_TOLERANCE
                for other_radius, other_phase in entries
            )
            for radius, phase in entries
        ):
            return count
    return 1


def read_thread(solid: Solid, *, cancelled: CancelToken | None = None) -> ThreadReading:
    """Die Gewindeauskunft eines Körpers — oder der Grund dagegen.

    Ein Körper trägt hier höchstens **ein** Gewinde: Der Zug mit den meisten
    Umläufen gibt Achse und Fußpunkt vor, und alle anderen Züge werden in
    diesem Rahmen gemessen — Züge um eine andere Achse fallen an ihrer
    Wendelabweichung heraus. Der Grund einer Absage ist eine Auskunft fürs
    Protokoll, keine Oberflächenzeile.
    """
    require()
    check_cancelled = cancelled.raise_if_cancelled if cancelled is not None else None
    starts = cylinder_axes(solid, check_cancelled)
    chains = candidate_chains(solid, check_cancelled, starts)
    if not chains:
        return ThreadReading(False, "keine Kantenzüge außer Strecken, Kreisen und ebenen Kurven")
    first_pass: list[Winding] = []
    confirmed = False
    for chain in chains:
        _check(check_cancelled)
        measured = measure_winding(chain, starts, None, check_cancelled)
        if measured is not None:
            first_pass.append(measured[0])
            confirmed = confirmed or measured[1]
    if not first_pass:
        return ThreadReading(False, "kein Zug windet sich um eine Achse")
    # **Unter einer vollen Umdrehung ist die Achse selbst eine Vermutung.** Die
    # Einpassung an einen Viertelbogen liefert irgendeine Achse und dazu einen
    # Vorschub (gemessen: 0,15 statt 1,0 an einem 90°-Ausschnitt) — die
    # Abweichung davon zu melden, wäre die falsche Begründung. Zusammen zählen
    # nur Züge um **dieselbe Achslinie** wie der längste: Zwölf Stücke einer
    # halbierten Wendel zu je 0,64 Umläufen belegen sie (der Kernzylinder
    # bestätigt jedem seine Achse), zwei Bögen um verschiedene Achsen nicht.
    # Bis zum 21.09.2026 zählte die Summe aller Züge.
    reference = max(first_pass, key=lambda w: w.turns)
    covered = sum(w.turns for w in first_pass if _coaxial(w, reference))
    if covered < MIN_TURNS_FOR_PITCH:
        return ThreadReading(
            False,
            f"Ausschnitt unter einer Umdrehung: nur {covered:.2f} Umläufe belegt — "
            "Achse und Steigung wären geraten",
            turns=covered,
        )
    # Der Zug mit den meisten Umläufen gibt Achse und Fußpunkt vor; alle
    # anderen werden in **diesem** Rahmen gemessen, damit Phasen vergleichbar sind.
    first_pass.sort(key=lambda w: -w.turns)
    reference = first_pass[0]
    frame = (np.asarray(reference.axis), np.asarray(reference.centre))
    # Ein kegeliger Bezugszug gibt allen Zügen die Gerade ``r = r0 + k·z``;
    # ihre Radien gelten dann am selben Fußpunkt und sind vergleichbar.
    tapered = reference.taper != 0.0
    windings: list[Winding] = []
    for winding in first_pass:
        _check(check_cancelled)
        again = measure_winding(winding.chain, None, frame, check_cancelled, tapered=tapered)
        if again is not None:
            windings.append(again[0])
    lead_group = [
        w
        for w in windings
        if abs(w.lead - reference.lead) <= LEAD_TOLERANCE * max(1.0, reference.lead)
        and w.handedness == reference.handedness
        and w.deviation <= HELIX_DEVIATION_SHARE * reference.lead
        and w.radius_spread <= RADIUS_TOLERANCE * max(1.0, w.radius)
        and abs(w.taper - reference.taper) <= TAPER_TOLERANCE
    ]
    if not lead_group:
        return ThreadReading(
            False,
            f"Wendelabweichung {reference.deviation:.4f} mm über "
            f"{HELIX_DEVIATION_SHARE:.0%} des Vorschubs",
            axis=reference.axis,
            centre=reference.centre,
        )
    lead = float(np.mean([w.lead for w in lead_group]))
    helices = _same_helices(lead_group, lead)
    total_turns = max(sum(w.turns for w in group) for group in helices)
    if total_turns < MIN_TURNS_FOR_PITCH:
        return ThreadReading(
            False,
            f"nur {total_turns:.2f} Umläufe belegt — unter einer vollen Umdrehung ist die "
            "Steigung eine Vermutung",
            axis=reference.axis,
            centre=reference.centre,
            turns=total_turns,
        )
    low = min(w.low for w in lead_group)
    high = max(w.high for w in lead_group)
    # Kamm und Fuß in der Mitte der belegten Länge — am Zylinder überall
    # dieselben Radien, am Kegel dort, wo auch ``centre`` liegt.
    slope = float(np.mean([w.taper for w in lead_group])) if tapered else 0.0
    grown = slope * (low + high) / 2.0
    radii = sorted(float(np.mean([w.radius for w in group])) + grown for group in helices)
    outer, inner = max(radii), min(radii)
    outside = material_outside(solid, reference, check_cancelled)
    if outside is None:
        return ThreadReading(False, "keine Flächennormale am Zug lesbar")
    internal = not outside
    crest = inner if internal else outer
    root = outer if internal else inner
    depth = root - crest if internal else crest - root
    if depth <= EPS_GEOM:
        return ThreadReading(
            False,
            "Kamm ohne Rille: Züge auf einem Radius — eine Naht, kein Gewinde",
            axis=reference.axis,
            centre=reference.centre,
            lead=lead,
            handedness=reference.handedness,
            turns=total_turns,
        )
    # Gangzahl: die Periodizität aller Wendeln (Radius, Phase je Vorschub);
    # Teilung = Vorschub / Gangzahl.
    phase_sets = [
        (
            float(np.mean([w.radius for w in group])),
            float(np.mean([(w.phase / lead) % 1.0 for w in group])),
        )
        for group in helices
    ]
    starts_count = starts_from_periodicity(phase_sets)
    pitch = lead / starts_count
    # Die Schranken der Rille kommen aus dem Netzweg — träge, damit der exakte
    # Kern keine eifrige Kante zur Wahrnehmung bekommt.
    from app.core.perceive.helix import GROOVE_RANGE

    if not (GROOVE_RANGE[0] <= depth / pitch <= GROOVE_RANGE[1]):
        return ThreadReading(
            False,
            f"Gangtiefe {depth:.3f} mm ist {depth / pitch:.2f} Teilungen — außerhalb "
            f"{GROOVE_RANGE}",
            axis=reference.axis,
            centre=reference.centre,
            lead=lead,
            pitch=pitch,
            starts=starts_count,
            handedness=reference.handedness,
            turns=total_turns,
        )
    axis = np.asarray(reference.axis)
    middle = np.asarray(reference.centre) + axis * (low + high) / 2.0
    return ThreadReading(
        True,
        "",
        axis=reference.axis,
        centre=(float(middle[0]), float(middle[1]), float(middle[2])),
        lead=lead,
        pitch=pitch,
        starts=starts_count,
        handedness=reference.handedness,
        internal=internal,
        crest_radius=crest,
        root_radius=root,
        depth=depth,
        length=high - low,
        turns=total_turns,
        uncertainty=max(w.deviation for w in lead_group),
        axis_source="native" if confirmed else "fit",
        members=tuple(lead_group),
        taper=math.atan(slope),
    )


def thread_features(solid: Solid, *, cancelled: CancelToken | None = None) -> list[Feature]:
    """Das gemessene Gewinde als Merkmal — im Vertrag des Netzwegs, mit mehr Maßen.

    ``diameter`` bleibt der Nenndurchmesser (außen Kamm, innen Grund); dazu
    kommen ``lead``, ``starts``, ``handedness``, ``crest_radius``,
    ``root_radius``, ``depth``, ``turns`` und ``uncertainty`` — die größte
    Wendelabweichung, das Maß, mit dem eine Passung zwei gemessene Steigungen
    vergleicht. Alles ist an Kanten und Flächen des exakten Körpers gemessen
    (``native``); die Achse ist eingepasst (``fit``), außer ein Kernzylinder
    hat sie bestätigt. Die Dreiecke des Merkmals sind die aller Flächen, die
    die Züge tragen — Flanken, Kamm und Grund —, damit ein Klick auf eine
    Flanke das Gewinde wählt. Die Auswahl der Züge verändert den Körper nicht.
    """
    reading = read_thread(solid, cancelled=cancelled)
    if not reading.found:
        if reading.reason:
            _log.debug("no thread on this body: %s", reading.reason)
        return []
    assert reading.pitch is not None and reading.lead is not None
    assert reading.axis is not None and reading.centre is not None
    assert reading.crest_radius is not None and reading.root_radius is not None
    assert reading.depth is not None and reading.length is not None
    assert reading.turns is not None and reading.uncertainty is not None
    check_cancelled = cancelled.raise_if_cancelled if cancelled is not None else None
    faces = _faces_at(solid, [w.chain for w in reading.members], check_cancelled)
    triangles = tuple(sorted({index for face in faces for index in solid.triangles_of_face(face)}))
    params: dict[str, Any] = {
        "diameter": reading.diameter,
        "pitch": reading.pitch,
        "lead": reading.lead,
        "starts": reading.starts,
        "handedness": reading.handedness,
        "centre": reading.centre,
        "axis": reading.axis,
        "internal": bool(reading.internal),
        "length": reading.length,
        "crest_radius": reading.crest_radius,
        "root_radius": reading.root_radius,
        "depth": reading.depth,
        "turns": reading.turns,
        "uncertainty": reading.uncertainty,
    }
    if reading.taper != 0.0:
        # Nur am kegeligen Gewinde: der halbe Kegelwinkel in Grad, positiv,
        # wenn der Durchmesser entlang ``axis`` wächst. Kamm, Fuß und
        # Nenndurchmesser gelten in der Mitte (``centre``).
        params["taper"] = math.degrees(reading.taper)
    sources: dict[str, MeasureSource] = {
        name: "native"
        for name, value in params.items()
        if not isinstance(value, bool | str) and name != "axis"
    }
    sources["axis"] = reading.axis_source
    sources["handedness"] = "native"
    identifier = FeatureId("thread_1")
    return [
        Feature(
            id=identifier,
            kind="thread",
            provenance="detected",
            params=params,
            measure_sources=sources,
            face_indices=triangles,
        )
    ]
