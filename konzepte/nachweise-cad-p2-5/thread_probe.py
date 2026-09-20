"""Prototyp: Gewinde an importierter B-Spline-Geometrie messen (P2.5).

**Was gemessen wird, und was nicht.** Ein eingelesener Gewindekörper trägt
keine Erzeugerauskunft: keine Steigung, keine Händigkeit, keine Gangzahl.
Was er trägt, sind Kanten, die sich um eine Achse winden — die Kämme und
Füße der Gänge. Dieser Prototyp liest genau die:

1. **Kandidatenkanten**: jede Kante, deren Kurve weder Strecke noch Kreis
   ist, wird nach **Bogenlänge** abgetastet (``GCPnts_UniformAbscissa``).
   Der Kurvenparameter ist kein Winkel und kein Steigungsbeleg; er kommt
   in keiner Rechnung vor. Kanten werden über gemeinsame Vertices zu Zügen
   verkettet (STEP zerlegt einen Gang in mehrere Kanten).
2. **Achse**: kleinste Quadrate über die Punkte des Zugs — der Zylinder, auf
   dem alle liegen (SciPy ``least_squares``, Start aus der SVD oder aus
   einem analytischen Zylindernachbarn, wenn einer da ist).
3. **Vorschub und Händigkeit**: in der Achsbasis wird der Umlaufwinkel
   entlang des Zugs entwickelt und ``z`` gegen ``θ/2π`` regressiert. Die
   Steigung dieser Geraden ist der Vorschub je Umdrehung, ihr Vorzeichen
   die Händigkeit — in einer **rechtshändigen** Basis (erste, zweite,
   Achse). Das Residuum ist die Wendelabweichung und der Beleg.
4. **Gangzahl**: Züge mit gleicher Achse, gleichem Vorschub und gleichem
   Radius, deren Phasen sich gleichmäßig über den Umlauf verteilen, sind
   die Kämme eines mehrgängigen Gewindes; Teilung = Vorschub / Gangzahl.
5. **Materialseite**: die orientierte Normale einer angrenzenden Fläche
   nahe der Kammkante zeigt von der Achse weg (Bolzen) oder zu ihr hin
   (Gewindebohrung) — dieselbe Frage wie ``helix._material_outside`` am Netz.
6. **Gangtiefe**: Kamm- gegen Fußradius, geprüft gegen ``helix.GROOVE_RANGE``
   — die Bedingung, die am Netz allein ablehnt (Naht ohne Rille ist kein
   Gewinde). Die Schranken werden aus ``helix`` gelesen, nicht abgeschrieben.

Unzureichende Belege (weniger als eine volle Umdrehung, schlechte Wendel,
keine Rille) liefern einen **Grund**, keine Steigung. Jede Schleife nimmt
``check_cancelled`` entgegen. Der Prototyp verändert die Eingabe nicht: Er
liest Kanten und Flächen und legt keine Kopie ab.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.core.brep.kernel import Solid
from app.core.perceive import helix as mesh_helix
from app.core.units import EPS_GEOM, positive_axis

Vec3 = tuple[float, float, float]
Cancel = Callable[[], None] | None

#: Abtastung je Zug: mindestens so viele Punkte, höchstens alle 0,05 mm.
SAMPLES_MIN = 120
SAMPLE_SPACING = 0.05

#: Was „gleiche Achse“ und „gleicher Radius“ heißt, wenn Züge zusammengefasst werden.
AXIS_TOLERANCE = 1e-3
RADIUS_TOLERANCE = 2e-3
LEAD_TOLERANCE = 2e-3

#: Unter einer vollen Umdrehung ist eine Steigung eine Vermutung, keine Messung.
MIN_TURNS_FOR_PITCH = 1.0

#: Wie weit ein Punkt von der Wendel abweichen darf, als Anteil des Vorschubs.
HELIX_DEVIATION_SHARE = 0.02

#: Wie weit zwei Phasen (als Anteil eines Vorschubs) auseinanderliegen dürfen,
#: um als dieselbe zu gelten — für die Gangzahl aus der Periodizität.
PHASE_TOLERANCE = 0.03


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
    axis_source: str = ""
    windings: tuple[Winding, ...] = field(default_factory=tuple)

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


def _curve_kind(edge: Any) -> int:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopoDS import TopoDS

    return int(BRepAdaptor_Curve(TopoDS.Edge(edge)).GetType())


def _sample_edge(edge: Any, check_cancelled: Cancel = None) -> tuple[NDArray[np.float64], float]:
    """Punkte nach **Bogenlänge**, nicht nach Parameter."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_AbscissaPoint, GCPnts_UniformAbscissa
    from OCP.TopoDS import TopoDS

    if check_cancelled is not None:
        check_cancelled()
    adaptor = BRepAdaptor_Curve(TopoDS.Edge(edge))
    length = float(GCPnts_AbscissaPoint.Length_s(adaptor))
    count = max(SAMPLES_MIN, math.ceil(length / SAMPLE_SPACING))
    spread = GCPnts_UniformAbscissa(adaptor, count)
    if not spread.IsDone():
        return np.zeros((0, 3)), length
    points = []
    for index in range(1, spread.NbPoints() + 1):
        point = adaptor.Value(spread.Parameter(index))
        points.append((point.X(), point.Y(), point.Z()))
    return np.asarray(points, dtype=float), length


def _end_tangents(
    edge: Any,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Anfangs- und Endpunkt einer Kante mit ihren Tangenten (Richtung ohne Vorzeichen)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.gp import gp_Pnt, gp_Vec
    from OCP.TopoDS import TopoDS

    adaptor = BRepAdaptor_Curve(TopoDS.Edge(edge))
    result = []
    for parameter in (adaptor.FirstParameter(), adaptor.LastParameter()):
        point, tangent = gp_Pnt(), gp_Vec()
        adaptor.D1(parameter, point, tangent)
        direction = np.array([tangent.X(), tangent.Y(), tangent.Z()], dtype=float)
        norm = np.linalg.norm(direction)
        result.append(np.array([point.X(), point.Y(), point.Z()], dtype=float))
        result.append(direction / norm if norm > EPS_GEOM else direction)
    return result[0], result[1], result[2], result[3]


def _ordered_points(pieces: list[tuple[int, NDArray[np.float64]]]) -> NDArray[np.float64]:
    """Die Abtastpunkte eines Zugs in **Kurvenreihenfolge**.

    Die Kantenreihenfolge im Register ist Zufall, und jede Kante kann in beide
    Richtungen laufen. Die Winkelentwicklung braucht die Reihenfolge entlang
    der Kurve: Stück an Stück nach dem nächstliegenden Ende gehängt, gedreht,
    wenn sein Anfang nicht am aktuellen Ende liegt.
    """
    remaining = [points for _index, points in pieces if len(points)]
    if not remaining:
        return np.zeros((0, 3))

    # Am Kettenende beginnen: dem Stück, dessen ein Ende zu keinem anderen passt.
    def loose(points: NDArray[np.float64]) -> int:
        count = 0
        for end in (points[0], points[-1]):
            near = any(
                np.linalg.norm(end - other[0]) <= 1e-4 or np.linalg.norm(end - other[-1]) <= 1e-4
                for other in remaining
                if other is not points
            )
            count += 0 if near else 1
        return count

    remaining.sort(key=lambda points: -loose(points))
    current = remaining.pop(0)
    if loose(current) == 1 and any(
        np.linalg.norm(current[0] - other[0]) <= 1e-4
        or np.linalg.norm(current[0] - other[-1]) <= 1e-4
        for other in remaining
    ):
        current = current[::-1]
    ordered = [current]
    while remaining:
        tail = ordered[-1][-1]
        best, best_gap, flip = 0, math.inf, False
        for slot, points in enumerate(remaining):
            for reverse, end in ((False, points[0]), (True, points[-1])):
                gap = float(np.linalg.norm(tail - end))
                if gap < best_gap:
                    best, best_gap, flip = slot, gap, reverse
        points = remaining.pop(best)
        ordered.append(points[::-1] if flip else points)
    return np.vstack(ordered)


def _is_planar(points: NDArray[np.float64]) -> bool:
    """Liegen alle Punkte in einer Ebene? Dann ist die Kurve keine Wendel."""
    offset = points - points.mean(axis=0)
    singular = np.linalg.svd(offset, full_matrices=False, compute_uv=False)
    return bool(singular[-1] <= PLANAR_LIMIT * max(float(singular[0]), EPS_GEOM))


#: Wie flach eine Kurve relativ zu ihrer Ausdehnung sein darf, um als eben zu gelten.
PLANAR_LIMIT = 1e-4

#: Wie schräg zwei Kanten am gemeinsamen Vertex noch als eine Kurve gelten.
TANGENT_LIMIT_DEG = 10.0


def _tangent_at_shared_vertex(one: Any, other: Any) -> bool:
    limit = math.cos(math.radians(TANGENT_LIMIT_DEG))
    for point_a, tangent_a in ((one[0], one[1]), (one[2], one[3])):
        for point_b, tangent_b in ((other[0], other[1]), (other[2], other[3])):
            close = np.linalg.norm(point_a - point_b) <= 1e-4
            if close and abs(float(tangent_a @ tangent_b)) >= limit:
                return True
    return False


def candidate_chains(solid: Solid, check_cancelled: Cancel = None) -> list[Chain]:
    """Kantenzüge aus allen nicht geradlinigen, nicht kreisförmigen Kanten.

    Verkettet werden Kanten, die einen Vertex teilen und beide Kandidaten
    sind — so werden die STEP-Stücke eines Gangs wieder ein Zug. Kreise
    bleiben draußen: Sie sind Ringrillen oder Stirnkanten, keine Wendel.
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
    kinds = [_curve_kind(edge) for edge in edges]
    candidate = [kind not in (int(GeomAbs_Line), int(GeomAbs_Circle)) for kind in kinds]
    # **Eine Wendel ist nicht eben.** Die Profilkanten in den Stirnflächen sind
    # ebenfalls B-Splines und laufen am Kamm fast tangential ein; über sie wurden
    # Kamm und beide Fußwendeln zu einem Zug (gemessen: 36 „Umläufe“). Ebene
    # Kandidaten fallen deshalb heraus, bevor verkettet wird.
    sampled: dict[int, tuple[NDArray[np.float64], float]] = {}
    for index, edge in enumerate(edges):
        if not candidate[index]:
            continue
        if check_cancelled is not None:
            check_cancelled()
        points, length = _sample_edge(edge, check_cancelled)
        sampled[index] = (points, length)
        if len(points) < 4 or _is_planar(points):
            candidate[index] = False
    by_vertex = AncestorMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_VERTEX, TopAbs_EDGE, by_vertex)
    neighbours: dict[int, set[int]] = {index: set() for index in range(len(edges))}
    # **Nur tangentiale Anschlüsse verketten.** Kamm, Fuß und Flankenknicke eines
    # Gangs teilen an den Stirnkappen Vertices; über bloße Nachbarschaft wurden
    # aus drei Wendeln eine mit 36 „Umläufen“ und 6 mm Abweichung (gemessen).
    ends: dict[
        int,
        tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]],
    ] = {}
    for index, edge in enumerate(edges):
        if candidate[index]:
            ends[index] = _end_tangents(edge)
    for slot in range(1, by_vertex.Extent() + 1):
        if check_cancelled is not None:
            check_cancelled()
        siblings = [edge_map.FindIndex(item) - 1 for item in by_vertex.FindFromIndex(slot)]
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
            if check_cancelled is not None:
                check_cancelled()
            index = stack.pop()
            if index in seen:
                continue
            seen.add(index)
            members.append(index)
            stack.extend(sorted(neighbours[index] - seen))
        ordered = _ordered_points([(index, sampled[index][0]) for index in members])
        total = sum(sampled[index][1] for index in members)
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
        if check_cancelled is not None:
            check_cancelled()
        adaptor = BRepAdaptor_Surface(TopoDS.Face(face))
        if adaptor.GetType() != GeomAbs_Cylinder:
            continue
        direction = adaptor.Cylinder().Axis().Direction()
        axis = np.array([direction.X(), direction.Y(), direction.Z()], dtype=float)
        if not any(abs(abs(float(axis @ other)) - 1.0) <= 1e-6 for other in found):
            found.append(axis)
    return found


def fit_axis(
    points: NDArray[np.float64],
    starts: list[NDArray[np.float64]] | None = None,
    check_cancelled: Cancel = None,
) -> tuple[NDArray[np.float64], NDArray[np.float64], float, float]:
    """Der Zylinder, auf dem die Punkte liegen: Achse, Fußpunkt, Radius, Streuung.

    Kleinste Quadrate über den radialen Abstand (SciPy). Gestartet wird von
    der SVD-Hauptrichtung (lange Züge), der SVD-Nebenrichtung (kurze Bögen
    unter einem Umlauf: dort ist die Kreisnormale die Achse) und jedem
    übergebenen Kandidaten (analytische Zylindernachbarn); es gilt der Start
    mit der kleinsten Reststreuung.
    """
    from scipy.optimize import least_squares

    if check_cancelled is not None:
        check_cancelled()
    centre = points.mean(axis=0)
    offset = points - centre
    _, _, directions = np.linalg.svd(offset, full_matrices=False)
    candidates = [directions[0], directions[-1], *(starts or [])]
    best: tuple[float, NDArray[np.float64], NDArray[np.float64], float] | None = None
    for start in candidates:
        if check_cancelled is not None:
            check_cancelled()
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
            if check_cancelled is not None:
                check_cancelled()
            axis, foot, radius = unpack(values)
            relative = points - foot
            along = relative @ axis
            across = relative - np.outer(along, axis)
            return np.linalg.norm(across, axis=1) - radius

        along0 = offset @ start_axis
        radius0 = float(np.linalg.norm(offset - np.outer(along0, start_axis), axis=1).mean())
        fit = least_squares(residual, np.array([0.0, 0.0, 0.0, 0.0, radius0]), method="lm")
        axis, foot, radius = unpack(fit.x)
        if radius <= EPS_GEOM:
            continue
        relative = points - foot
        along = relative @ axis
        spread = float(
            np.abs(np.linalg.norm(relative - np.outer(along, axis), axis=1) - radius).max()
        )
        if best is None or spread < best[0]:
            best = (spread, axis, foot, radius)
    if best is None:
        return directions[0], centre, 0.0, math.inf
    spread, axis, foot, radius = best
    axis = np.asarray(positive_axis((float(axis[0]), float(axis[1]), float(axis[2]))), dtype=float)
    return axis, foot, radius, spread


# --- Wendel je Zug ------------------------------------------------------------------------


def measure_winding(
    chain: Chain,
    starts: list[NDArray[np.float64]] | None = None,
    frame: tuple[NDArray[np.float64], NDArray[np.float64]] | None = None,
    check_cancelled: Cancel = None,
) -> Winding | None:
    """Vorschub, Händigkeit und Wendelabweichung eines Zugs — oder nichts.

    Mit ``frame`` (Achse, Fußpunkt) wird nicht neu eingepasst: So bekommen
    alle Züge eines Körpers dieselbe Basis, und ihre Phasen sind vergleichbar.
    """
    points = chain.points
    if len(points) < 8:
        return None
    if frame is None:
        axis, foot, radius, spread = fit_axis(points, starts, check_cancelled)
    else:
        axis, foot = frame
        relative = points - foot
        along = relative @ axis
        radii = np.linalg.norm(relative - np.outer(along, axis), axis=1)
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
    return Winding(
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
    )


# --- Materialseite ---------------------------------------------------------------------------


def material_outside(solid: Solid, winding: Winding, check_cancelled: Cancel = None) -> bool | None:
    """Zeigt die Fläche neben dem Zug von der Achse weg?

    Gelesen an den Flächen, die die Kanten des Zugs tragen: orientierte
    Normale (``BRepLProp_SLProps`` mit der Flächenorientierung) an der
    Flächenmitte, gemittelt gegen die radiale Richtung. Bolzen: positiv.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as AncestorMap,
    )
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    edge_map = ShapeMap()
    TopExp.MapShapes_s(solid.shape, TopAbs_EDGE, edge_map)
    edges = [edge_map.FindKey(index) for index in range(1, edge_map.Extent() + 1)]
    by_edge = AncestorMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, by_edge)
    face_map = ShapeMap()
    TopExp.MapShapes_s(solid.shape, TopAbs_FACE, face_map)
    axis = np.asarray(winding.axis)
    centre = np.asarray(winding.centre)
    votes: list[float] = []
    seen: set[int] = set()
    for index in winding.chain.edges:
        if check_cancelled is not None:
            check_cancelled()
        edge = edges[index]
        slot = by_edge.FindIndex(edge)
        if slot == 0:
            continue
        for face in by_edge.FindFromIndex(slot):
            key = int(face_map.FindIndex(face)) if face_map.Contains(face) else -1
            if key in seen:
                continue
            seen.add(key)
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


def _same_axis(one: Winding, other: Winding) -> bool:
    a, b = np.asarray(one.axis), np.asarray(other.axis)
    if abs(abs(float(a @ b)) - 1.0) > AXIS_TOLERANCE:
        return False
    gap = np.asarray(other.centre) - np.asarray(one.centre)
    return float(np.linalg.norm(gap - a * (gap @ a))) <= RADIUS_TOLERANCE * 10.0


def read_thread(
    solid: Solid,
    *,
    check_cancelled: Cancel = None,
) -> ThreadReading:
    """Die Gewindeauskunft eines importierten Körpers — oder der Grund dagegen."""
    chains = candidate_chains(solid, check_cancelled)
    if not chains:
        return ThreadReading(False, "keine Kantenzüge außer Strecken, Kreisen und ebenen Kurven")
    starts = cylinder_axes(solid, check_cancelled)
    axis_source = "cylinder" if starts else "fit"
    first_pass = []
    for chain in chains:
        if check_cancelled is not None:
            check_cancelled()
        winding = measure_winding(chain, starts, None, check_cancelled)
        if winding is not None:
            first_pass.append(winding)
    if not first_pass:
        return ThreadReading(False, "kein Zug windet sich um eine Achse")
    # **Unter einer vollen Umdrehung ist die Achse selbst eine Vermutung.** Die
    # Einpassung an einen Viertelbogen liefert irgendeine Achse und dazu einen
    # Vorschub (gemessen: 0,15 statt 1,0 an einem 90°-Ausschnitt) — die
    # Abweichung davon zu melden, wäre die falsche Begründung.
    covered = sum(w.turns for w in first_pass)
    if covered < MIN_TURNS_FOR_PITCH:
        return ThreadReading(
            False,
            f"Ausschnitt unter einer Umdrehung: nur {covered:.2f} Umläufe belegt — "
            "Achse und Steigung wären geraten",
            turns=covered,
            windings=tuple(first_pass),
        )
    # Der Zug mit den meisten Umläufen gibt Achse und Fußpunkt vor; alle
    # anderen werden in **diesem** Rahmen gemessen, damit Phasen vergleichbar sind.
    first_pass.sort(key=lambda w: -w.turns)
    reference = first_pass[0]
    frame = (np.asarray(reference.axis), np.asarray(reference.centre))
    windings = []
    for winding in first_pass:
        if check_cancelled is not None:
            check_cancelled()
        again = measure_winding(winding.chain, None, frame, check_cancelled)
        if again is not None:
            windings.append(again)
    lead_group = [
        w
        for w in windings
        if abs(w.lead - reference.lead) <= LEAD_TOLERANCE * max(1.0, reference.lead)
        and w.handedness == reference.handedness
        and w.deviation <= HELIX_DEVIATION_SHARE * reference.lead
        and w.radius_spread <= RADIUS_TOLERANCE * max(1.0, w.radius)
    ]
    if not lead_group:
        return ThreadReading(
            False,
            f"Wendelabweichung {reference.deviation:.4f} mm über "
            f"{HELIX_DEVIATION_SHARE:.0%} des Vorschubs",
            axis=reference.axis,
            centre=reference.centre,
            windings=tuple(windings),
        )
    lead = float(np.mean([w.lead for w in lead_group]))
    # Eine Wendel = gleicher Radius und gleiche Phase; ihre Stücke zählen zusammen.
    helices: dict[tuple[float, float], list[Winding]] = {}
    for w in lead_group:
        key = (round(w.radius, 3), round((w.phase / lead) % 1.0, 2) % 1.0)
        helices.setdefault(key, []).append(w)
    turns_by_helix = {key: sum(w.turns for w in group) for key, group in helices.items()}
    total_turns = max(turns_by_helix.values())
    if total_turns < MIN_TURNS_FOR_PITCH:
        return ThreadReading(
            False,
            f"nur {total_turns:.2f} Umläufe belegt — unter einer vollen Umdrehung ist die "
            "Steigung eine Vermutung",
            axis=reference.axis,
            centre=reference.centre,
            turns=total_turns,
            windings=tuple(windings),
        )
    radii = sorted({key[0] for key in helices})
    outer, inner = max(radii), min(radii)
    outside = material_outside(solid, reference, check_cancelled)
    if outside is None:
        return ThreadReading(False, "keine Flächennormale am Zug lesbar", windings=tuple(windings))
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
            windings=tuple(windings),
        )
    # Gangzahl: die Periodizität aller Wendeln (Radius, Phase je Vorschub);
    # Teilung = Vorschub / Gangzahl.
    phase_sets = [
        (key[0], float(np.mean([(w.phase / lead) % 1.0 for w in group])))
        for key, group in helices.items()
    ]
    starts_count = starts_from_periodicity(phase_sets)
    pitch = lead / starts_count
    if not (mesh_helix.GROOVE_RANGE[0] <= depth / pitch <= mesh_helix.GROOVE_RANGE[1]):
        return ThreadReading(
            False,
            f"Gangtiefe {depth:.3f} mm ist {depth / pitch:.2f} Teilungen — außerhalb "
            f"{mesh_helix.GROOVE_RANGE}",
            axis=reference.axis,
            centre=reference.centre,
            lead=lead,
            pitch=pitch,
            starts=starts_count,
            handedness=reference.handedness,
            turns=total_turns,
            windings=tuple(windings),
        )
    low = min(w.low for w in lead_group)
    high = max(w.high for w in lead_group)
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
        axis_source=axis_source,
        windings=tuple(windings),
    )


def describe(reading: ThreadReading) -> str:
    if not reading.found:
        return f"kein Gewinde: {reading.reason}"
    assert reading.pitch is not None and reading.lead is not None
    return (
        f"{'Innen' if reading.internal else 'Außen'}gewinde {reading.handedness}, "
        f"Ø {reading.diameter:.4f}, Teilung {reading.pitch:.4f}, Vorschub {reading.lead:.4f}, "
        f"{reading.starts}-gängig, Tiefe {reading.depth:.4f}, Länge {reading.length:.3f}, "
        f"{reading.turns:.2f} Umläufe, Wendelabweichung {reading.uncertainty:.5f}, "
        f"Achse {tuple(round(v, 6) for v in reading.axis)}"
    )
