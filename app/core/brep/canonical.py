"""Analytische Träger und ihre tatsächlichen Grenzen, ohne die Eingabeform zu ändern."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from app.core.brep.kernel import box_limits, nearest_distance, untrimmed_surface
from app.core.errors import PROGRAMMING_ERRORS, OperationCancelled
from app.core.log import get_logger
from app.core.types import CancelToken, Vec3
from app.core.units import EPS_GEOM

if TYPE_CHECKING:
    from app.core.brep.kernel import Solid

_log = get_logger(__name__)

# Grenzen der zusätzlichen Kandidatenprüfung, keine geometrischen Toleranzen.
# Bei ausgeschöpfter Arbeit bleibt der Träger unklassifiziert.
_MAX_CANONICAL_PATCHES = 4096
_MAX_COEFFICIENT_PRODUCTS = 1_000_000


def outward_normal(face: Any, point: Vec3) -> Vec3 | None:
    """Die nach außen zeigende Normale einer Fläche am Fußpunkt von ``point``.

    Die Normale kommt aus der Fläche selbst (``BRepLProp_SLProps``), mit der
    Orientierung der Fläche im Körper — an einer ebenen Fläche die
    Ebenennormale, an einer gekrümmten die an dieser Stelle. ``None``, wo sich
    der Punkt nicht auf die Fläche legen lässt oder die Normale dort nicht
    bestimmt ist. Fase mit zwei Abständen (``edit._faces_at_edge``) und
    Tangentenkette der Formschräge (``profiles._tangent_chain``) fragen hier.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.TopoDS import TopoDS

    typed = TopoDS.Face(face)
    projector = GeomAPI_ProjectPointOnSurf(gp_Pnt(*point), BRep_Tool.Surface_s(typed))
    if projector.NbPoints() < 1:
        return None
    u, v = projector.LowerDistanceParameters()
    props = BRepLProp_SLProps(BRepAdaptor_Surface(typed), u, v, 1, 1e-6)
    if not props.IsNormalDefined():
        return None
    normal = props.Normal()
    sign = -1.0 if typed.Orientation() == TopAbs_REVERSED else 1.0
    return (sign * normal.X(), sign * normal.Y(), sign * normal.Z())


def projected_surface_point(face: Any, point: Vec3) -> tuple[Vec3, Vec3] | None:
    """Punkt und Normale auf dem echten beschnittenen Träger statt auf seiner Sehne."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON
    from OCP.TopoDS import TopoDS

    typed = TopoDS.Face(face)
    projection = GeomAPI_ProjectPointOnSurf(gp_Pnt(*point), BRep_Tool.Surface_s(typed))
    if projection.NbPoints() < 1:
        return None
    nearest = projection.NearestPoint()
    if BRepClass_FaceClassifier(typed, nearest, EPS_GEOM).State() not in (TopAbs_IN, TopAbs_ON):
        return None
    located: Vec3 = (nearest.X(), nearest.Y(), nearest.Z())
    normal = outward_normal(typed, located)
    return (located, normal) if normal is not None else None


@dataclass(frozen=True, slots=True)
class PlaneSurface:
    """Ebene mit der wirklichen, nach außen gerichteten Flächennormale."""

    plane: Any
    normal: Vec3


@dataclass(frozen=True, slots=True)
class CylinderSurface:
    """Kreiszylinder mit axialen Längen, Winkelabdeckung und tatsächlicher Materialseite."""

    cylinder: Any
    first: float
    last: float
    turn: float
    inward: bool


@dataclass(frozen=True, slots=True)
class TorusSurface:
    """Ringträger mit geprüften Radien und tatsächlicher Materialseite."""

    torus: Any
    inward: bool


@dataclass(frozen=True, slots=True)
class SphereSurface:
    """Kugelträger mit geprüftem Zentrum, Radius und tatsächlicher Materialseite."""

    sphere: Any
    inward: bool


@dataclass(frozen=True, slots=True)
class ConeSurface:
    """Kreiskegel aus einer Spline-Fläche: Spitze, gerichtete Nappe, axiale Spanne, Materialseite.

    ``axis`` zeigt von der Spitze in die belegte Nappe, zum weiten Ende;
    ``near`` und ``far`` sind die axialen Abstände der Flächengrenzen von der
    Spitze, ``turn`` die Winkelabdeckung im Bogenmaß — dieselben Auskünfte,
    die ein nativer Kegel über seine V-Grenzen gibt (``features._cone_nappe``).
    """

    cone: Any
    apex: Vec3
    axis: Vec3
    half_angle: float
    near: float
    far: float
    turn: float
    inward: bool


Surface = PlaneSurface | CylinderSurface | TorusSurface | SphereSurface | ConeSurface


def _check(cancelled: CancelToken | None) -> None:
    """Native Teilrechnungen und Python-Schleifen teilen denselben Abbruchauftrag."""
    if cancelled is not None:
        cancelled.raise_if_cancelled()


def surface_sample(face: Any) -> tuple[Any, Any] | None:
    """Eine echte Innenprobe statt einer möglicherweise ausgeschnittenen UV-Mitte."""
    from OCP.BRepClass3d import BRepClass3d_SolidExplorer
    from OCP.gp import gp_Pnt, gp_Vec
    from OCP.TopAbs import TopAbs_REVERSED

    point, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
    if not BRepClass3d_SolidExplorer.FindAPointInTheFace_s(face, point, 0.0, 0.0, 0.5, du, dv):
        return None
    normal = du.Crossed(dv)
    if not math.isfinite(normal.Magnitude()) or not normal.Magnitude() > 0.0:
        return None
    normal.Normalize()
    if face.Orientation() == TopAbs_REVERSED:
        normal.Reverse()
    return point, normal


def _product(first: Any, second: Any, cancelled: CancelToken | None) -> Any:
    """Multipliziert auch unterschiedlich hohe Bernstein-Grade ohne Punktabtastung."""
    first_degree = np.asarray(first.shape) - 1
    second_degree = np.asarray(second.shape) - 1
    combined = first_degree + second_degree

    def factors(degrees: Any) -> Any:
        """Binomialfaktoren beider Parameter bilden die Tensorproduktbasis."""
        return np.outer(
            [math.comb(int(degrees[0]), index) for index in range(degrees[0] + 1)],
            [math.comb(int(degrees[1]), index) for index in range(degrees[1] + 1)],
        ).astype(float)

    left, right = first * factors(first_degree), second * factors(second_degree)
    result = np.zeros(tuple(combined + 1), dtype=np.float64)
    for row in range(first.shape[0]):
        _check(cancelled)
        for column in range(first.shape[1]):
            result[row : row + second.shape[0], column : column + second.shape[1]] += (
                left[row, column] * right
            )
    return result / factors(combined)


def _normal_bound(
    relative: Any, weights: Any, axis: Any, plane: bool, cancelled: CancelToken | None
) -> float:
    """Begrenzt die Abweichung der Einheitsnormale von Ebene beziehungsweise Radiale.

    Rationale Ableitungszähler ergeben ein polynomiales Kreuzprodukt N.
    Für den Sollvektor Q begrenzen dessen Bernstein-Koeffizienten
    Kreuzproduktnorm / Skalarproduktbetrag. Bei gesichertem Vorzeichen ist
    dies tan(Winkel) und damit auch eine obere Grenze des Abstands der
    gerichteten Einheitsvektoren.
    Eine kleine Lageabweichung allein könnte beim Offset stark anwachsen.
    """
    count_u, count_v = weights.shape
    if min(count_u, count_v) < 2:
        return math.inf
    weighted = relative * weights[:, :, None]
    tangents = []
    for dimension, degree in ((0, count_u - 1), (1, count_v - 1)):
        _check(cancelled)
        derivative = degree * np.diff(weighted, axis=dimension)
        weight_derivative = degree * np.diff(weights, axis=dimension)
        tangents.append(
            [
                _product(derivative[:, :, coordinate], weights, cancelled)
                - _product(weighted[:, :, coordinate], weight_derivative, cancelled)
                for coordinate in range(3)
            ]
        )
    normal = [
        _product(tangents[0][first], tangents[1][second], cancelled)
        - _product(tangents[0][second], tangents[1][first], cancelled)
        for first, second in ((1, 2), (2, 0), (0, 1))
    ]
    if plane:
        dot = sum(normal[index] * axis[index] for index in range(3))
        cross = [
            normal[first] * axis[second] - normal[second] * axis[first]
            for first, second in ((1, 2), (2, 0), (0, 1))
        ]
    else:
        radial = weighted - (weighted @ axis)[:, :, None] * axis
        dot = sum(_product(normal[index], radial[:, :, index], cancelled) for index in range(3))
        cross = [
            _product(normal[first], radial[:, :, second], cancelled)
            - _product(normal[second], radial[:, :, first], cancelled)
            for first, second in ((1, 2), (2, 0), (0, 1))
        ]
    lower = max(float(np.min(dot)), -float(np.max(dot)))
    if not math.isfinite(lower) or lower <= 0.0:
        return math.inf
    return math.hypot(*(float(np.max(np.abs(value))) for value in cross)) / lower


def _parameter_spans(
    first: float, last: float, low: float, high: float, periodic: bool
) -> tuple[tuple[float, float], ...] | None:
    """Teilt eine periodische Trimmung an der Naht in ihre wirklichen Trägerintervalle."""
    from OCP.Precision import Precision

    if not all(math.isfinite(value) for value in (first, last, low, high)):
        return None
    if not last > first or not high > low:
        return None
    if periodic:
        period = high - low
        length = last - first
        if length >= period:
            return ((low, high),)
        start = low + (first - low) % period
        stop = start + length
        if stop <= high:
            return ((start, stop),)
        return ((start, high), (low, low + stop - high))
    clipped = []
    for value, boundary, outside in ((first, low, first < low), (last, high, last > high)):
        tolerance = max(Precision.PConfusion_s(), math.ulp(value) + math.ulp(boundary))
        if outside and abs(value - boundary) > tolerance:
            return None
        clipped.append(boundary if outside else value)
    return ((clipped[0], clipped[1]),) if clipped[1] > clipped[0] else None


def _bezier_patches(adaptor: Any, cancelled: CancelToken | None) -> list[Any] | None:
    """Private rationale Teilflächen mit periodischen Trimmungen und gemeinsamer Arbeitsgrenze."""
    from OCP.GeomAbs import GeomAbs_BezierSurface
    from OCP.GeomConvert import GeomConvert_BSplineSurfaceToBezierSurface
    from OCP.Precision import Precision

    _check(cancelled)
    if adaptor.GetType() == GeomAbs_BezierSurface:
        patch = adaptor.Bezier().Copy()
        patch.Segment(
            adaptor.FirstUParameter(),
            adaptor.LastUParameter(),
            adaptor.FirstVParameter(),
            adaptor.LastVParameter(),
        )
        patches = [patch]
    else:
        spline = adaptor.BSpline()
        if (spline.NbUKnots() - 1) * (spline.NbVKnots() - 1) > _MAX_CANONICAL_PATCHES:
            return None
        domain = spline.Bounds()
        u_spans = _parameter_spans(
            adaptor.FirstUParameter(),
            adaptor.LastUParameter(),
            domain[0],
            domain[1],
            spline.IsUPeriodic(),
        )
        v_spans = _parameter_spans(
            adaptor.FirstVParameter(),
            adaptor.LastVParameter(),
            domain[2],
            domain[3],
            spline.IsVPeriodic(),
        )
        if u_spans is None or v_spans is None:
            return None
        patches = []
        for u_span in u_spans:
            for v_span in v_spans:
                _check(cancelled)
                converter = GeomConvert_BSplineSurfaceToBezierSurface(
                    spline.Copy(), *u_span, *v_span, Precision.PConfusion_s()
                )
                if (
                    len(patches) + converter.NbUPatches() * converter.NbVPatches()
                    > _MAX_CANONICAL_PATCHES
                ):
                    return None
                for row in range(1, converter.NbUPatches() + 1):
                    _check(cancelled)
                    for column in range(1, converter.NbVPatches() + 1):
                        patches.append(converter.Patch(row, column))
    return patches


def _patch_data(patch: Any, cancelled: CancelToken | None) -> tuple[Any, Any] | None:
    """Endliche Pole und positive, normierte Gewichte einer privaten Bézier-Fläche."""
    rows, columns = patch.NbUPoles(), patch.NbVPoles()
    poles = np.empty((rows, columns, 3), dtype=np.float64)
    weights = np.empty((rows, columns), dtype=np.float64)
    for row in range(rows):
        _check(cancelled)
        for column in range(columns):
            poles[row, column] = patch.Pole(row + 1, column + 1).Coord()
            weights[row, column] = patch.Weight(row + 1, column + 1)
    if not np.isfinite(poles).all() or not np.isfinite(weights).all() or not (weights > 0.0).all():
        return None
    weights /= float(weights.max())
    return poles, weights


def _matches(
    adaptor: Any,
    candidate: Any,
    plane: bool,
    cancelled: CancelToken | None,
    *,
    offset: float = 0.0,
    spherical: bool = False,
) -> bool:
    """Prüft jeden rationalen Bézier-Abschnitt einschließlich seiner inneren Pole.

    Positive Gewichte begrenzen Ebenenabstände durch die Polhülle. Beim
    Zylinder wird X²+Y²-R²W² in homogenen Bernstein-Koeffizienten geprüft,
    bei der Kugel zusätzlich Z².
    Deren Betragsmaximum, geteilt durch R·min(W)², begrenzt den radialen
    Abstand. So kann ein Ausschlag zwischen Punktproben nicht verschwinden.
    Die Aussage gilt der Trägerfläche, nicht einer beidseitigen Hausdorff-
    Distanz des getrimmten Körpers und nicht einer Fertigungsunsicherheit.
    """
    patches = _bezier_patches(adaptor, cancelled)
    if patches is None:
        return False
    origin = np.asarray(candidate.Location().Coord(), dtype=np.float64)
    axis = np.asarray(candidate.Position().Direction().Coord(), dtype=np.float64)
    remaining = _MAX_COEFFICIENT_PRODUCTS
    for patch in patches:
        _check(cancelled)
        count_u, count_v = patch.NbUPoles(), patch.NbVPoles()
        count = count_u * count_v
        remaining -= (4 if spherical else 3) * count**2
        if abs(offset) > 0.0:
            # 12 Ableitungs-, 6 Kreuzprodukt- und beim Zylinder weitere
            # 9 Projektionsprodukte: gezählte Koeffizientenpaare, keine Laufzeitgrenze.
            remaining -= 6 * count * ((count_u - 1) * count_v + count_u * (count_v - 1))
            remaining -= (
                6 * (2 * count_u - 2) * (2 * count_v - 1) * (2 * count_u - 1) * (2 * count_v - 2)
            )
            if not plane:
                remaining -= 9 * count * (4 * count_u - 4) * (4 * count_v - 4)
        if remaining < 0:
            return False
        data = _patch_data(patch, cancelled)
        if data is None:
            return False
        poles, weights = data
        relative = poles - origin
        if plane:
            bound = float(np.max(np.abs(relative @ axis)))
            if abs(offset) > 0.0:
                bound += abs(offset) * _normal_bound(relative, weights, axis, True, cancelled)
            if not math.isfinite(bound) or bound > EPS_GEOM:
                return False
            continue
        radius = float(candidate.Radius())
        if not math.isfinite(radius) or radius <= 0.0:
            return False
        x_axis = np.asarray(candidate.Position().XDirection().Coord(), dtype=np.float64)
        y_axis = np.asarray(candidate.Position().YDirection().Coord(), dtype=np.float64)
        x = weights * (relative @ x_axis) / radius
        y = weights * (relative @ y_axis) / radius
        residual = (
            _product(x, x, cancelled)
            + _product(y, y, cancelled)
            - _product(weights, weights, cancelled)
        )
        if spherical:
            z = weights * (relative @ axis) / radius
            residual += _product(z, z, cancelled)
        bound = radius * float(np.max(np.abs(residual))) / float(weights.min()) ** 2
        if abs(offset) > 0.0:
            bound += abs(offset) * _normal_bound(relative, weights, axis, False, cancelled)
        if not math.isfinite(bound) or bound > EPS_GEOM:
            return False
    return True


def _ruled(adaptor: Any) -> bool:
    """Ob die Spline-Fläche in einer Richtung linear ist — dann trägt sie Strecken.

    Eine Kugel und ein Ring enthalten keine einzige Strecke; eine Fläche vom
    Grad eins in U oder V besteht aus ihnen (auch rational: eine rationale
    Strecke bleibt eine Strecke). Sie braucht die Einpassung von Kugel und Ring
    gar nicht erst: An einem genähten Gewindebolzen M3 x 0,5 x 60 sind das
    362 Regelflächen und 1,2 s für zwei Antworten, die „nein" heißen müssen
    (Review 22.09.2026).
    """
    from OCP.GeomAbs import GeomAbs_BezierSurface, GeomAbs_BSplineSurface

    kind = adaptor.GetType()
    if kind == GeomAbs_BSplineSurface:
        surface = adaptor.BSpline()
    elif kind == GeomAbs_BezierSurface:
        surface = adaptor.Bezier()
    else:
        return False
    return bool(surface.UDegree() == 1 or surface.VDegree() == 1)


def _sphere_surface(face: Any, adaptor: Any, cancelled: CancelToken | None) -> SphereSurface | None:
    """Native Kugel oder vollständig geprüfter rationaler Träger auf einer privaten Kopie."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.GeomAbs import GeomAbs_BezierSurface, GeomAbs_BSplineSurface, GeomAbs_Sphere
    from OCP.gp import gp_Sphere, gp_Vec
    from OCP.ShapeAnalysis import ShapeAnalysis_CanonicalRecognition

    kind = adaptor.GetType()
    if kind == GeomAbs_Sphere:
        candidate = adaptor.Sphere()
    elif kind in (GeomAbs_BezierSurface, GeomAbs_BSplineSurface):
        working = (adaptor.Bezier() if kind == GeomAbs_BezierSurface else adaptor.BSpline()).Copy()
        local_origin = np.asarray(working.Pole(1, 1).Coord(), dtype=float)
        working.Translate(gp_Vec(*(-local_origin)))
        _check(cancelled)
        local_face = BRepBuilderAPI_MakeFace(
            working,
            adaptor.FirstUParameter(),
            adaptor.LastUParameter(),
            adaptor.FirstVParameter(),
            adaptor.LastVParameter(),
            EPS_GEOM,
        ).Face()
        recognizer = ShapeAnalysis_CanonicalRecognition(local_face)
        candidate = gp_Sphere()
        matched = recognizer.IsSphere(EPS_GEOM, candidate)
        _check(cancelled)
        if not matched or recognizer.GetStatus() != 0:
            return None
        gap = float(recognizer.GetGap())
        if not math.isfinite(gap) or not 0.0 <= gap <= EPS_GEOM:
            return None
        candidate.Translate(gp_Vec(*local_origin))
        if not _matches(adaptor, candidate, False, cancelled, spherical=True):
            return None
    else:
        return None
    if not math.isfinite(candidate.Radius()) or candidate.Radius() <= EPS_GEOM:
        return None
    measured = surface_sample(face)
    _check(cancelled)
    if measured is None:
        return None
    point, normal = measured
    return SphereSurface(candidate, normal.Dot(gp_Vec(candidate.Location(), point)) < 0.0)


def _torus_matches(adaptor: Any, candidate: Any, cancelled: CancelToken | None) -> bool:
    """Begrenzt den Torusabstand über homogene Bernstein-Koeffizienten.

    F=(|p|²+R²-r²)²-4R²·rho² faktorisiert in (s²-r²) und
    ((rho+R)²+z²-r²), wobei s der Abstand zum Mittellinienkreis ist
    und rho der Abstand zur Ringachse.
    Für R>r ist der zweite Faktor mindestens R²-r²; s+r ist
    mindestens r. Deshalb begrenzt |F|/[r(R²-r²)] den Flächenabstand.
    Positive rationale Gewichte liefern diese Schranke ohne Punktstichprobe.
    Ein durch die Polhülle belegter Mindestabstand zur Achse verschärft den
    zweiten Faktor auf (rho_min+R)²-r²; er lockert keine Formtoleranz.
    """
    patches = _bezier_patches(adaptor, cancelled)
    if patches is None:
        return False
    major, minor = float(candidate.MajorRadius()), float(candidate.MinorRadius())
    if not math.isfinite(major + minor) or not major > minor > EPS_GEOM:
        return False
    origin = np.asarray(candidate.Location().Coord(), dtype=float)
    frame = candidate.Position()
    basis = np.asarray(
        [frame.XDirection().Coord(), frame.YDirection().Coord(), frame.Direction().Coord()]
    )
    remaining = _MAX_COEFFICIENT_PRODUCTS
    for patch in patches:
        _check(cancelled)
        rows, columns = patch.NbUPoles(), patch.NbVPoles()
        count = rows * columns
        doubled = (2 * rows - 1) * (2 * columns - 1)
        remaining -= 4 * count**2 + 2 * doubled**2
        if remaining < 0:
            return False
        data = _patch_data(patch, cancelled)
        if data is None:
            return False
        poles, weights = data
        relative = (poles - origin) @ basis.T / major * weights[:, :, None]
        squared = [
            _product(relative[:, :, axis], relative[:, :, axis], cancelled) for axis in range(3)
        ]
        weight_squared = _product(weights, weights, cancelled)
        radial_squared = squared[0] + squared[1]
        quadratic = radial_squared + squared[2] + (1.0 - (minor / major) ** 2) * weight_squared
        residual = _product(quadratic, quadratic, cancelled) - 4.0 * _product(
            radial_squared, weight_squared, cancelled
        )
        radial_poles = (poles - origin) @ basis[:2].T
        direction = radial_poles.mean(axis=(0, 1))
        direction_length = float(np.linalg.norm(direction))
        radial_lower = (
            max(0.0, float(np.min(radial_poles @ (direction / direction_length))))
            if direction_length > EPS_GEOM
            else 0.0
        )
        denominator = minor * ((radial_lower + major) ** 2 - minor**2) * float(weights.min()) ** 4
        if not math.isfinite(denominator) or denominator <= 0.0:
            return False
        bound = major**4 * float(np.max(np.abs(residual))) / denominator
        if not math.isfinite(bound) or bound > EPS_GEOM:
            return False
    return True


def _torus_surface(face: Any, adaptor: Any, cancelled: CancelToken | None) -> TorusSurface | None:
    """Ein nativer Ring oder ein an der gesamten rationalen Trägerfläche geprüfter Kandidat."""
    from OCP.GeomAbs import GeomAbs_BezierSurface, GeomAbs_BSplineSurface, GeomAbs_Torus
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Torus, gp_Vec

    kind = adaptor.GetType()
    if kind == GeomAbs_Torus:
        candidate = adaptor.Torus()
    elif kind in (GeomAbs_BezierSurface, GeomAbs_BSplineSurface):
        from app.core.perceive.features import fit_torus_samples

        limits = (
            adaptor.FirstUParameter(),
            adaptor.LastUParameter(),
            adaptor.FirstVParameter(),
            adaptor.LastVParameter(),
        )
        if not all(math.isfinite(value) for value in limits):
            return None
        # Native rationale Ableitungen dürfen keine großen Weltkoordinaten
        # gegeneinander auslöschen. Nur diese private Trägerkopie wird versetzt.
        working = (adaptor.Bezier() if kind == GeomAbs_BezierSurface else adaptor.BSpline()).Copy()
        local_origin = np.asarray(working.Pole(1, 1).Coord(), dtype=float)
        working.Translate(gp_Vec(*(-local_origin)))
        points, normals = [], []
        for u in np.linspace(limits[0], limits[1], 9):
            _check(cancelled)
            for v in np.linspace(limits[2], limits[3], 9):
                point, du, dv = gp_Pnt(), gp_Vec(), gp_Vec()
                working.D1(float(u), float(v), point, du, dv)
                normal = du.Crossed(dv)
                if normal.Magnitude() <= EPS_GEOM:
                    continue
                normal.Normalize()
                points.append(point.Coord())
                normals.append(normal.Coord())
        fitted = fit_torus_samples(np.asarray(points), np.asarray(normals))
        _check(cancelled)
        if fitted is None or not fitted.good:
            return None
        candidate = gp_Torus(
            gp_Ax3(gp_Pnt(*(np.asarray(fitted.centre) + local_origin)), gp_Dir(*fitted.axis)),
            fitted.ring_radius,
            fitted.tube_radius,
        )
        if not _torus_matches(adaptor, candidate, cancelled):
            return None
    else:
        return None
    if not float(candidate.MajorRadius()) > float(candidate.MinorRadius()) > EPS_GEOM:
        return None
    measured = surface_sample(face)
    _check(cancelled)
    if measured is None:
        return None
    point, normal = measured
    axis = gp_Vec(candidate.Axis().Direction())
    radial = gp_Vec(candidate.Location(), point)
    radial.Subtract(axis.Multiplied(radial.Dot(axis)))
    if radial.Magnitude() <= EPS_GEOM:
        return None
    radial.Normalize()
    middle = candidate.Location().Translated(radial.Multiplied(candidate.MajorRadius()))
    return TorusSurface(candidate, normal.Dot(gp_Vec(middle, point)) < 0.0)


def _rims_on_grid(face: Any) -> bool:
    """Ob jede Randkante eines Zylinders Mantellinie oder Querkreis ist (RM-226).

    Nur dann sind die Parametergrenzen der Fläche genau: Eine Strecke auf dem
    Zylinder liegt längs der Achse, ein Kreis quer zu ihr. Schneidet eine
    schräge Ebene den Mantel, ist der Rand eine Ellipse oder ein Spline, und
    die Parametergrenzen kommen aus seiner Näherung im Parameterraum: Am
    tieferen Bogen eines Langlochs durch eine um 4 Grad geneigte Platte lag
    das untere Ende 0,042 mm zu tief (-4,2584 statt -4,3007). Dann misst
    :func:`_axial_limits` an der Originalform.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    walk = TopExp_Explorer(face, TopAbs_EDGE)
    while walk.More():
        edge = TopoDS.Edge(walk.Current())
        walk.Next()
        if BRep_Tool.Degenerated_s(edge):
            continue
        if BRepAdaptor_Curve(edge).GetType() not in (GeomAbs_Line, GeomAbs_Circle):
            return False
    return True


def _axial_limits(
    face: Any, position: Any, target: Any, cancelled: CancelToken | None
) -> tuple[float, float, float] | None:
    """Misst axial an der Originalform und Winkel an ihren tatsächlichen Randkurven.

    ``position`` ist der Rahmen, in dessen Z die Spanne gemessen wird (die
    Lage des Zylinders; beim Kegel die Spitze mit der Achse in die Nappe),
    ``target`` die Drehfläche, auf die die Randkurven für den Winkel
    projiziert werden — ihr U ist der Umlaufwinkel.
    """
    from OCP.Bnd import Bnd_Box, Bnd_Box2d
    from OCP.BndLib import BndLib_Add2dCurve
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
    from OCP.GeomProjLib import GeomProjLib
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt, gp_Trsf
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    _check(cancelled)
    transform = gp_Trsf()
    transform.SetTransformation(position)
    local = BRepBuilderAPI_Transform(face, transform, True).Shape()
    bounds = Bnd_Box()
    BRepBndLib.AddOptimal_s(local, bounds, False, False)
    limits = box_limits(bounds)
    # AddOptimal erweitert NURBS-Hüllwerte intern, auch ohne Formtoleranz
    # und bei Gap=0. Die Hülle legt deshalb nur zwei äußere Messebenen fest;
    # ihre tatsächlichen Abstände liefern die Endlagen ohne diesen Zuschlag.
    reach = math.dist(limits[:3], limits[3:])
    heights = (limits[2] - reach, limits[5] + reach)
    measured = []
    for index, height in enumerate(heights):
        _check(cancelled)
        plane = gp_Pln(gp_Ax3(gp_Pnt(0.0, 0.0, height), gp_Dir(0.0, 0.0, 1.0)))
        target_face = BRepBuilderAPI_MakeFace(
            plane,
            limits[0] - reach,
            limits[3] + reach,
            limits[1] - reach,
            limits[4] + reach,
        ).Face()
        away = nearest_distance(local, target_face)
        _check(cancelled)
        if away is None:
            return None
        measured.append(height + away if index == 0 else height - away)
    first, last = measured
    intervals = []
    walk = TopExp_Explorer(face, TopAbs_EDGE)
    while walk.More():
        _check(cancelled)
        edge = TopoDS.Edge(walk.Current())
        walk.Next()
        if BRep_Tool.Degenerated_s(edge):
            continue
        curve = BRep_Tool.Curve_s(edge, 0.0, 0.0)
        if curve is None:
            return None
        adaptor = BRepAdaptor_Curve(edge)
        projected = GeomProjLib.Curve2d_s(
            curve, adaptor.FirstParameter(), adaptor.LastParameter(), target, EPS_GEOM
        )
        _check(cancelled)
        if projected is None:
            return None
        box = Bnd_Box2d()
        BndLib_Add2dCurve.AddOptimal_s(
            projected, adaptor.FirstParameter(), adaptor.LastParameter(), 0.0, box
        )
        box.SetGap(0.0)
        low, high = float(box.GetXMin()), float(box.GetXMax())
        if not all(math.isfinite(value) for value in (low, high)):
            return None
        span = min(math.tau, high - low)
        start = low % math.tau
        stop = start + span
        intervals.append((start, min(math.tau, stop)))
        if stop > math.tau:
            intervals.append((0.0, stop - math.tau))
    end = turn = 0.0
    for low, high in sorted(intervals):
        turn += max(0.0, high - max(low, end))
        end = max(end, high)
    if not all(math.isfinite(value) for value in (first, last, turn)) or not last > first:
        return None
    return first, last, min(turn, math.tau)


#: Wie oft ein Bézier-Abschnitt zur Kegelspitze hin halbiert wird, bis der
#: Rest in ``EPS_GEOM`` um die Spitze liegt. Von 100 mm auf 10⁻⁶ mm sind es 27
#: Halbierungen; die Zahl ist eine Arbeitsgrenze, keine Toleranz.
_APEX_SPLITS = 64


def _halved(homogeneous: Any, dimension: int, toward_end: bool) -> tuple[Any, Any]:
    """Teilt einen rationalen Bézier-Abschnitt in der Mitte seines Parameters (de Casteljau).

    ``homogeneous`` trägt je Pol ``(w·x, w·y, w·z, w)``; in diesen Koordinaten
    ist die Teilung exakt. Zurück kommen die Hälfte am gewählten Rand von
    ``dimension`` — am letzten Index, wenn ``toward_end`` — und die andere.
    """
    points = np.moveaxis(homogeneous, dimension, 0)
    first, last = [points[0]], [points[-1]]
    work = points
    for _ in range(1, points.shape[0]):
        work = 0.5 * (work[:-1] + work[1:])
        first.append(work[0])
        last.append(work[-1])
    low = np.moveaxis(np.stack(first), 0, dimension)
    high = np.moveaxis(np.stack(last[::-1]), 0, dimension)
    return (high, low) if toward_end else (low, high)


def _apart_from_the_apex(
    poles: Any, weights: Any, origin: Any, cancelled: CancelToken | None
) -> list[tuple[Any, Any]] | None:
    """Die Teile eines Bézier-Abschnitts, deren Polhülle die Kegelspitze nicht berührt.

    Ein Kegel, der bis in seine Spitze reicht — die Bohrspitze eines
    Sacklochs, ein spitzer Stift —, hat dort einen Abschnitt, dessen Polreihe
    an einem Rand ganz auf der Spitze liegt, und dort teilt die Schranke von
    :func:`_cone_matches` durch null. Der Abschnitt wird deshalb zur Spitze
    hin halbiert, bis der Rest ganz in ``EPS_GEOM`` um sie liegt: Seine Punkte
    sind Konvexkombinationen der Pole, und die Spitze liegt auf dem Kegel.
    Jede abgetrennte Hälfte prüft der Aufrufer wie jeden anderen Abschnitt.
    Berührt die Hülle die Spitze anders als mit genau einer Randreihe, bleibt
    die Fläche ohne Befund.
    """
    distance = np.linalg.norm(poles - origin, axis=-1)
    if float(distance.min()) > EPS_GEOM:
        return [(poles, weights)]
    if float(distance.max()) <= EPS_GEOM:
        return []
    ends = [
        (dimension, toward_end)
        for dimension in (0, 1)
        for toward_end in (False, True)
        if float(np.take(distance, -1 if toward_end else 0, axis=dimension).max()) <= EPS_GEOM
    ]
    if len(ends) != 1:
        return None
    dimension, toward_end = ends[0]
    current = np.concatenate((poles * weights[..., None], weights[..., None]), axis=-1)
    pieces = []
    for _ in range(_APEX_SPLITS):
        _check(cancelled)
        near, far = _halved(current, dimension, toward_end)
        far_weights = far[..., 3]
        pieces.append(
            (far[..., :3] / far_weights[..., None], far_weights / float(far_weights.max()))
        )
        current = near
        points = current[..., :3] / current[..., 3:]
        if float(np.linalg.norm(points - origin, axis=-1).max()) <= EPS_GEOM:
            return pieces
    return None


def _cone_matches(
    adaptor: Any, apex: Any, axis: Any, half_angle: float, cancelled: CancelToken | None
) -> float | None:
    """Prüft jeden rationalen Bézier-Abschnitt gegen den Kreiskegel — und nennt die Nappe.

    In der Kegelbasis mit Spitze ``A``, Achse ``a`` und ``t = tan(Halbwinkel)``
    gilt auf der Fläche ``x² + y² - t²z² = 0``. Homogen mit den Gewichten sind
    das Bernstein-Koeffizienten von ``X² + Y² - t²Z²`` (dieselbe Rechnung wie am
    Zylinder, :func:`_matches`). Mit dem Achsabstand ``r`` zerfällt der
    Ausdruck in ``(r - tz)(r + tz)``, und der Abstand eines Punkts zur
    Kegelfläche ist höchstens ``|r - tz|·cos(Halbwinkel)``. Weil ``z`` über der
    Polhülle nicht unter ``z_min`` fällt, ist ``r + tz ≥ t·z_min``; so begrenzt
    ``max|F|·cos / (t·z_min·w_min²)`` den Abstand ohne Punktstichprobe.
    Reicht die Fläche bis in die Spitze, übernimmt :func:`_apart_from_the_apex`
    die Teilung davor. Schließt die Polhülle die Spitze anders ein (beide
    Nappen), bleibt die Fläche ohne Befund — dieselbe Regel wie am nativen
    Kegel. Zurück kommt das Vorzeichen der belegten Nappe entlang ``axis``
    oder ``None``.
    """
    patches = _bezier_patches(adaptor, cancelled)
    if patches is None:
        return None
    tangent = math.tan(half_angle)
    cosine = math.cos(half_angle)
    if not (math.isfinite(tangent) and tangent > 0.0):
        return None
    origin = np.asarray(apex.Coord(), dtype=np.float64)
    direction = np.asarray(axis.Coord(), dtype=np.float64)
    helper = np.array((1.0, 0.0, 0.0)) if abs(direction[0]) < 0.9 else np.array((0.0, 1.0, 0.0))
    across = np.cross(direction, helper)
    across /= np.linalg.norm(across)
    upward = np.cross(direction, across)
    remaining = _MAX_COEFFICIENT_PRODUCTS
    side = 0.0
    for patch in patches:
        _check(cancelled)
        data = _patch_data(patch, cancelled)
        if data is None:
            return None
        pieces = _apart_from_the_apex(*data, origin, cancelled)
        if pieces is None:
            return None
        for poles, weights in pieces:
            _check(cancelled)
            remaining -= 3 * weights.size**2
            if remaining < 0:
                return None
            relative = poles - origin
            along = relative @ direction
            nappe = 1.0 if float(along.min()) > 0.0 else (-1.0 if float(along.max()) < 0.0 else 0.0)
            if nappe == 0.0 or (side and nappe != side):
                return None
            side = nappe
            nearest = float(np.min(np.abs(along)))
            scale = float(np.max(np.abs(along)))
            if not (math.isfinite(scale) and scale > 0.0 and nearest > 0.0):
                return None
            x = weights * (relative @ across) / scale
            y = weights * (relative @ upward) / scale
            z = weights * along / scale
            residual = (
                _product(x, x, cancelled)
                + _product(y, y, cancelled)
                - tangent**2 * _product(z, z, cancelled)
            )
            bound = (
                float(np.max(np.abs(residual)))
                * scale**2
                * cosine
                / (tangent * nearest * float(weights.min()) ** 2)
            )
            if not math.isfinite(bound) or bound > EPS_GEOM:
                return None
    return side or None


def _cone_surface(face: Any, adaptor: Any, cancelled: CancelToken | None) -> ConeSurface | None:
    """Ein rationaler Kegelträger, erkannt an einer privaten Kopie und vollständig geprüft.

    Der native Kegel (``GeomAbs_Cone``) bleibt beim bisherigen Weg in
    ``features``; hier geht es um dieselbe Fläche als B-Spline, wie manche
    Programme jede Fläche nach STEP schreiben. Bis zum 22.09.2026 kam eine
    solche Senkung als „gerundete Seite" in den Baum und trug keine Maße
    (P2.3). Die axiale Spanne kommt wie am Zylinder aus Abständen zu äußeren
    Messebenen, der Winkel aus den projizierten Randkurven.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.Geom import Geom_ConicalSurface
    from OCP.GeomAbs import GeomAbs_BezierSurface, GeomAbs_BSplineSurface
    from OCP.gp import gp_Ax3, gp_Cone, gp_Dir, gp_Vec
    from OCP.ShapeAnalysis import ShapeAnalysis_CanonicalRecognition

    kind = adaptor.GetType()
    if kind not in (GeomAbs_BezierSurface, GeomAbs_BSplineSurface):
        return None
    working = (adaptor.Bezier() if kind == GeomAbs_BezierSurface else adaptor.BSpline()).Copy()
    local_origin = np.asarray(working.Pole(1, 1).Coord(), dtype=float)
    working.Translate(gp_Vec(*(-local_origin)))
    _check(cancelled)
    local_face = BRepBuilderAPI_MakeFace(
        working,
        adaptor.FirstUParameter(),
        adaptor.LastUParameter(),
        adaptor.FirstVParameter(),
        adaptor.LastVParameter(),
        EPS_GEOM,
    ).Face()
    recognizer = ShapeAnalysis_CanonicalRecognition(local_face)
    candidate = gp_Cone()
    matched = recognizer.IsCone(EPS_GEOM, candidate)
    _check(cancelled)
    if not matched or recognizer.GetStatus() != 0:
        return None
    gap = float(recognizer.GetGap())
    if not math.isfinite(gap) or not 0.0 <= gap <= EPS_GEOM:
        return None
    candidate.Translate(gp_Vec(*local_origin))
    half_angle = abs(float(candidate.SemiAngle()))
    if not EPS_GEOM < half_angle < math.pi / 2.0 - EPS_GEOM:
        return None
    apex = candidate.Apex()
    direction = candidate.Axis().Direction()
    side = _cone_matches(adaptor, apex, direction, half_angle, cancelled)
    if side is None:
        return None
    into = gp_Dir(side * direction.X(), side * direction.Y(), side * direction.Z())
    limits = _axial_limits(face, gp_Ax3(apex, into), Geom_ConicalSurface(candidate), cancelled)
    if limits is None:
        return None
    near, far, turn = limits
    # Ein Kegel bis in die Spitze beginnt bei null; ``_axial_limits`` misst
    # dort Rundungsrauschen, und darunter liegt nichts (``_cone_matches``
    # hat die Nappe belegt).
    if not (-EPS_GEOM <= near < far and far > EPS_GEOM):
        return None
    near = max(near, 0.0)
    measured = surface_sample(face)
    _check(cancelled)
    if measured is None:
        return None
    point, normal = measured
    axis = gp_Vec(into)
    radial = gp_Vec(apex, point)
    radial.Subtract(axis.Multiplied(radial.Dot(axis)))
    if radial.Magnitude() <= EPS_GEOM:
        return None
    return ConeSurface(
        cone=candidate,
        apex=(float(apex.X()), float(apex.Y()), float(apex.Z())),
        axis=(float(into.X()), float(into.Y()), float(into.Z())),
        half_angle=half_angle,
        near=near,
        far=far,
        turn=turn,
        inward=normal.Dot(radial) < 0.0,
    )


def _candidate(
    face: Any, adaptor: Any, cancelled: CancelToken | None, *, offset: float = 0.0
) -> tuple[Any, bool] | None:
    """Ein gemeinsamer Kandidatenweg für Originalflächen und private Offset-Basisflächen."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.Geom import Geom_RectangularTrimmedSurface
    from OCP.GeomAbs import (
        GeomAbs_BezierSurface,
        GeomAbs_BSplineSurface,
        GeomAbs_Cylinder,
        GeomAbs_Plane,
    )
    from OCP.gp import gp_Cylinder, gp_Pln
    from OCP.ShapeAnalysis import ShapeAnalysis_CanonicalRecognition

    _check(cancelled)
    kind = adaptor.GetType()
    if kind == GeomAbs_Plane:
        return adaptor.Plane(), True
    if kind == GeomAbs_Cylinder:
        return adaptor.Cylinder(), False
    if kind not in (GeomAbs_BSplineSurface, GeomAbs_BezierSurface):
        return None
    native = BRep_Tool.Surface_s(face)
    if isinstance(native, Geom_RectangularTrimmedSurface):
        surface = untrimmed_surface(native, cancelled=cancelled)
        if surface is None:
            return None
        face = BRepBuilderAPI_MakeFace(
            surface.Copy(),
            adaptor.FirstUParameter(),
            adaptor.LastUParameter(),
            adaptor.FirstVParameter(),
            adaptor.LastVParameter(),
            EPS_GEOM,
        ).Face()
    for plane in (True, False):
        _check(cancelled)
        recognizer = ShapeAnalysis_CanonicalRecognition(face)
        probe = gp_Pln() if plane else gp_Cylinder()
        method = recognizer.IsPlane if plane else recognizer.IsCylinder
        matched = method(EPS_GEOM, probe)
        _check(cancelled)
        if matched and recognizer.GetStatus() == 0:
            gap = float(recognizer.GetGap())
            if (
                math.isfinite(gap)
                and 0.0 <= gap <= EPS_GEOM
                and _matches(adaptor, probe, plane, cancelled, offset=offset)
            ):
                _check(cancelled)
                return probe, plane
        if plane:
            # Versagt der Erkenner an einer Ebene, sprechen ihre Pole
            # (:func:`_pole_plane`); belegt wird der Kandidat wie jeder andere.
            fitted = _pole_plane(adaptor, cancelled)
            if fitted is not None and _matches(adaptor, fitted, True, cancelled, offset=offset):
                _check(cancelled)
                return fitted, True
    return None


def _pole_plane(adaptor: Any, cancelled: CancelToken | None) -> Any | None:
    """Die Ebene durch die Pole einer Spline-Fläche, wenn alle in ``EPS_GEOM`` darauf liegen.

    ``ShapeAnalysis_CanonicalRecognition.IsPlane`` versagt an großen
    gespiegelten Ebenen (Lücke -1): Ein Quader 300 x 300 x 30 mit Bohrung,
    gespiegelt und um 31° gedreht, verlor als NURBS fünf seiner sechs Ebenen,
    bei 1000 mm alle sechs, und kam als gerundete Flächen ohne Maß in den Baum
    (gemessen 22.09.2026). Seine Pole lagen dabei auf 10⁻¹⁴ in einer Ebene.
    Die Ausgleichsebene durch sie ist deshalb ein Kandidat wie der des
    Erkenners, und mit positiven Gewichten liegt jeder Flächenpunkt in der
    konvexen Hülle der Pole — die Bernstein-Prüfung in :func:`_matches`
    bestätigt ihn trotzdem, damit Offset und Trimmung denselben Weg gehen.
    """
    from OCP.GeomAbs import GeomAbs_BezierSurface
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    surface = adaptor.Bezier() if adaptor.GetType() == GeomAbs_BezierSurface else adaptor.BSpline()
    rows, columns = int(surface.NbUPoles()), int(surface.NbVPoles())
    if rows * columns > _MAX_COEFFICIENT_PRODUCTS:
        return None
    # Erst die vier Eckpole: Liegen sie nicht in einer Ebene, ist die Fläche
    # keine — die Regelflächen eines Gewindes fallen hier heraus, ohne dass
    # jeder ihrer Pole gelesen wird.
    corners = np.asarray(
        [surface.Pole(row, column).Coord() for row in (1, rows) for column in (1, columns)],
        dtype=np.float64,
    )
    span = corners - corners[0]
    across = np.cross(span[1], span[2])
    size = float(np.linalg.norm(across))
    if size > EPS_GEOM**2 and abs(float(span[3] @ across)) / size > EPS_GEOM:
        return None
    poles = np.empty((rows * columns, 3), dtype=np.float64)
    for row in range(rows):
        _check(cancelled)
        for column in range(columns):
            if not surface.Weight(row + 1, column + 1) > 0.0:
                return None
            poles[row * columns + column] = surface.Pole(row + 1, column + 1).Coord()
    if not np.isfinite(poles).all():
        return None
    centre = poles.mean(axis=0)
    _, singular, directions = np.linalg.svd(poles - centre, full_matrices=False)
    if len(singular) < 3 or not singular[1] > EPS_GEOM:
        return None
    normal = directions[2]
    if float(np.max(np.abs((poles - centre) @ normal))) > EPS_GEOM:
        return None
    return gp_Pln(gp_Pnt(*(float(value) for value in centre)), gp_Dir(*(float(v) for v in normal)))


def _offset_candidate(
    face: Any, adaptor: Any, cancelled: CancelToken | None
) -> tuple[Any, bool] | None:
    """Leitet einen Offset ausschließlich aus seiner geprüften Basis und Parameternormale ab."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Vec

    _check(cancelled)
    surface = untrimmed_surface(BRep_Tool.Surface_s(face), cancelled=cancelled)
    if surface is None:
        return None
    offset = float(surface.Offset())
    if not math.isfinite(offset):
        return None
    # OCCT fasst konstruktiv verschachtelte Offsets in einer Basis zusammen.
    # Verbleibt dort ein Offset, verweigert _candidate ihn ohne Rekursion;
    # damit teilen auch solche Eingaben dieselbe endliche Arbeitsgrenze.
    basis = untrimmed_surface(surface.BasisSurface(), cancelled=cancelled)
    if basis is None:
        return None
    basis_face = BRepBuilderAPI_MakeFace(
        basis.Copy(),
        adaptor.FirstUParameter(),
        adaptor.LastUParameter(),
        adaptor.FirstVParameter(),
        adaptor.LastVParameter(),
        EPS_GEOM,
    ).Face()
    _check(cancelled)
    found = _candidate(basis_face, BRepAdaptor_Surface(basis_face), cancelled, offset=offset)
    if found is None:
        return None
    candidate, plane = found
    measured = surface_sample(basis_face)
    _check(cancelled)
    if measured is None:
        return None
    point, normal = measured
    axis = gp_Vec(candidate.Axis().Direction())
    if plane:
        sign = -1.0 if normal.Dot(axis) < 0.0 else 1.0
        candidate.Translate(axis.Multiplied(sign * offset))
    else:
        radial = gp_Vec(candidate.Location(), point)
        radial.Subtract(axis.Multiplied(radial.Dot(axis)))
        sign = -1.0 if normal.Dot(radial) < 0.0 else 1.0
        radius = float(candidate.Radius()) + sign * offset
        if not math.isfinite(radius) or radius <= 0.0:
            return None
        candidate.SetRadius(radius)
    return candidate, plane


def describe(face: Any, *, cancelled: CancelToken | None = None) -> Surface | None:
    """Liest analytische Träger samt Grenzen; die Topologie bleibt unangetastet."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_OffsetSurface
    from OCP.gp import gp_Vec

    _check(cancelled)
    try:
        adaptor = BRepAdaptor_Surface(face)
        kind = adaptor.GetType()
        found = (
            _offset_candidate(face, adaptor, cancelled)
            if kind == GeomAbs_OffsetSurface
            else _candidate(face, adaptor, cancelled)
        )
        if found is None:
            # Ein Kegel ist eine Regelfläche: erst er, dann erst die Absage an
            # Kugel und Ring, die keine Strecke enthalten.
            cone = _cone_surface(face, adaptor, cancelled)
            if cone is not None:
                return cone
            if _ruled(adaptor):
                return None
            sphere = _sphere_surface(face, adaptor, cancelled)
            return sphere if sphere is not None else _torus_surface(face, adaptor, cancelled)
        candidate, plane = found
        _check(cancelled)
        measured = surface_sample(face)
        _check(cancelled)
        if measured is None:
            return None
        point, normal = measured
        if plane:
            return PlaneSurface(
                candidate, (float(normal.X()), float(normal.Y()), float(normal.Z()))
            )
        origin = candidate.Location()
        axis = gp_Vec(candidate.Axis().Direction())
        radial = gp_Vec(origin, point)
        radial.Subtract(axis.Multiplied(radial.Dot(axis)))
        inward = normal.Dot(radial) < 0.0
        if kind == GeomAbs_Cylinder and _rims_on_grid(face):
            first, last = float(adaptor.FirstVParameter()), float(adaptor.LastVParameter())
            turn = abs(float(adaptor.LastUParameter() - adaptor.FirstUParameter()))
        else:
            from OCP.Geom import Geom_CylindricalSurface

            limits = _axial_limits(
                face, candidate.Position(), Geom_CylindricalSurface(candidate), cancelled
            )
            if limits is None:
                return None
            first, last, turn = limits
        _check(cancelled)
        return CylinderSurface(candidate, first, last, turn, inward)
    except OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception:
        _log.debug("canonical surface description could not be resolved", exc_info=True)
        return None


def horizontal_area(solid: Solid, z: float, *, up: bool = True) -> float:
    """Die Summe der ebenen Flächen auf Höhe ``z``, nach oben oder nach unten gerichtet.

    Das exakte Gegenstück zur Dreieckszählung der Organizer-Bausteine
    (``knowledge/parts/containers._horizontal_area``): Dort zählt jedes
    Dreieck mit dieser Normale in dieser Höhe, hier jede ebene Fläche — die
    gerundeten Ecken und eine ausgesparte Mitte eingeschlossen, als Integral
    statt als Summe von Sehnen. Die Richtung ist die der Fläche, nicht die des
    Trägers: Die Ebene kennt ihre Achse, die Orientierung der Fläche dreht sie
    um — ohne Innenprobe, damit keine Fläche still ausgelassen wird.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_REVERSED

    from app.core.brep.properties import properties

    sign = 1.0 if up else -1.0
    total = 0.0
    for face in solid.faces():
        adaptor = BRepAdaptor_Surface(face)
        if adaptor.GetType() != GeomAbs_Plane:
            continue
        plane = adaptor.Plane()
        outward = float(plane.Axis().Direction().Z())
        if face.Orientation() == TopAbs_REVERSED:
            outward = -outward
        if abs(outward - sign) > EPS_GEOM:
            continue
        if abs(float(plane.Location().Z()) - z) > EPS_GEOM:
            continue
        total += properties(face, "surface").mass
    return total
