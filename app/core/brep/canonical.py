"""Analytische Träger und ihre tatsächlichen Grenzen, ohne die Eingabeform zu ändern."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from app.core.brep.kernel import box_limits, untrimmed_surface
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


Surface = PlaneSurface | CylinderSurface | TorusSurface | SphereSurface


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


def _cylinder_limits(
    face: Any, cylinder: Any, cancelled: CancelToken | None
) -> tuple[float, float, float] | None:
    """Misst axial an der Originalform und Winkel an ihren tatsächlichen Randkurven."""
    from OCP.Bnd import Bnd_Box, Bnd_Box2d
    from OCP.BndLib import BndLib_Add2dCurve
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Transform
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.Geom import Geom_CylindricalSurface
    from OCP.GeomProjLib import GeomProjLib
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt, gp_Trsf
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    _check(cancelled)
    transform = gp_Trsf()
    transform.SetTransformation(cylinder.Position())
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
        distance = BRepExtrema_DistShapeShape(local, target_face)
        _check(cancelled)
        if not distance.IsDone():
            return None
        measured.append(height + distance.Value() if index == 0 else height - distance.Value())
    first, last = measured
    intervals = []
    target = Geom_CylindricalSurface(cylinder)
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
        if not matched or recognizer.GetStatus() != 0:
            continue
        gap = float(recognizer.GetGap())
        if (
            math.isfinite(gap)
            and 0.0 <= gap <= EPS_GEOM
            and _matches(adaptor, probe, plane, cancelled, offset=offset)
        ):
            _check(cancelled)
            return probe, plane
    return None


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
        if kind == GeomAbs_Cylinder:
            first, last = float(adaptor.FirstVParameter()), float(adaptor.LastVParameter())
            turn = abs(float(adaptor.LastUParameter() - adaptor.FirstUParameter()))
        else:
            limits = _cylinder_limits(face, candidate, cancelled)
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
