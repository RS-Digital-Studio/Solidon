"""Native Integrale über Knotenspannen und ursprüngliche NURBS-Trimmkurven.

Die Topologie bleibt unverändert. Nur private Arbeitsflächen werden unterteilt;
bei schwierigen Konturen integriert ein begrenzter Rückfall die ursprünglichen
Randkurven. Lage, Innenlöcher und Orientierung bleiben Teil des Integrationsgebiets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import chain, pairwise
from typing import Any, Literal, cast

from app.core.errors import (
    CANCEL,
    CORRECT_INPUT,
    PROGRAMMING_ERRORS,
    GeometryError,
    OperationCancelled,
)
from app.core.types import CancelToken, Vec3
from app.i18n import _

# Numerische Rechengenauigkeit, kein Fertigungsspiel: Die äußere Konvergenz
# vergleicht unabhängige Unterteilungen; OCCT rechnet jedes Teilgebiet feiner.
INTEGRAL_RELATIVE_ERROR = 1e-9
_PATCH_RELATIVE_ERROR = 1e-12
_SUBDIVISIONS = (2, 4, 8)
# Die Parameterkurven werden auf privaten Flächen erneut synchronisiert.
# Diese Genauigkeit in mm verändert keine Kante der veröffentlichten Form.
_REPARAMETRIZATION_PRECISION = 1e-9
# Begrenzt die temporäre Topologie, bevor der native Aufteiler sie erzeugt.
_MAX_PATCHES = 4096
# Bereits die erste Quadratur benötigt je Trimmkurven-Knotenspanne viele
# Ableitungen. Die Momentenrechnung komplexer Gewindeflanken überschreitet 200 000;
# die feste Arbeitsgrenze bleibt von der geforderten Genauigkeit getrennt.
_MAX_EVALUATIONS = 1_000_000


@dataclass(frozen=True, slots=True)
class MassProperties:
    """Unveränderliche Kennzahlen; nicht berechnete Trägheit bleibt ausdrücklich leer."""

    mass: float
    centre: Vec3
    inertia: tuple[Vec3, Vec3, Vec3] | None

    def __post_init__(self) -> None:
        """Ungültige Kennzahlen gelangen aus keinem Rechenweg in einen Cache."""
        values: tuple[float, ...] = (self.mass, *self.centre)
        if self.inertia is not None:
            values += tuple(value for row in self.inertia for value in row)
        if self.mass < 0.0 or not all(math.isfinite(value) for value in values):
            raise _unresolved_integral()


def _from_native(props: Any, *, inertia: bool) -> MassProperties:
    """Nimmt ausschließlich berechnete Werte mit, ohne einen nativen Handle zu cachen."""
    centre = props.CentreOfMass()
    tensor = props.MatrixOfInertia() if inertia else None
    result = MassProperties(
        float(props.Mass()),
        (float(centre.X()), float(centre.Y()), float(centre.Z())),
        cast(
            tuple[Vec3, Vec3, Vec3],
            tuple(tuple(float(tensor.Value(i, j)) for j in range(1, 4)) for i in range(1, 4)),
        )
        if tensor is not None
        else None,
    )
    return result


def _unresolved_integral() -> GeometryError:
    """Keine geratene Kennzahl veröffentlichen, wenn die native Rechnung nicht trägt."""
    return GeometryError(
        detail=_(
            "Die Fläche oder das Volumen lässt sich an dieser exakten Form nicht zuverlässig "
            "bestimmen. Verkleinern Sie die Änderung oder wählen Sie eine andere Ausgangsform."
        ),
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def _faces(shape: Any, *, cancelled: CancelToken | None = None) -> list[Any]:
    """Die gerichteten Flächen der Form, ohne mehrfach besuchte Unterformen."""
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    found = ShapeMap()
    TopExp.MapShapes_s(shape, TopAbs_FACE, found)
    faces = []
    for index in range(1, found.Extent() + 1):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        faces.append(TopoDS.Face(found.FindKey(index)))
    return faces


def _spline_basis(face: Any, *, cancelled: CancelToken | None = None) -> Any | None:
    """Liest die NURBS-Basis auch unter Offset- und Trimmhüllen, ohne sie zu verändern."""
    from OCP.BRep import BRep_Tool
    from OCP.Geom import Geom_BezierSurface, Geom_BSplineSurface, Geom_OffsetSurface

    from app.core.brep.kernel import _MAX_SURFACE_WRAPPERS, untrimmed_surface

    surface = BRep_Tool.Surface_s(face)
    for _depth in range(_MAX_SURFACE_WRAPPERS + 1):
        surface = untrimmed_surface(surface, cancelled=cancelled)
        if surface is None:
            raise _unresolved_integral()
        if isinstance(surface, (Geom_BSplineSurface, Geom_BezierSurface)):
            return surface
        if not isinstance(surface, Geom_OffsetSurface):
            return None
        surface = surface.BasisSurface()
    raise _unresolved_integral()


def _needs_spans(face: Any, *, cancelled: CancelToken | None = None) -> bool:
    """Analytische Flächen behalten ihren einfachen nativen Integrationsweg."""
    return _spline_basis(face, cancelled=cancelled) is not None


def _split_values(
    surface: Any,
    axis: str,
    low: float,
    high: float,
    subdivisions: int,
    *,
    cancelled: CancelToken | None = None,
) -> Any:
    """Unterteilt jede vollständige Knotenspanne innerhalb des getrimmten Gebiets."""
    from OCP.collections import HSequence_double

    knots = [low, *_knots(surface, axis, low, high, cancelled=cancelled), high]
    result = HSequence_double()
    for first, last in pairwise(knots):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        for step in range(subdivisions):
            result.Append(first + (last - first) * step / subdivisions)
    result.Append(high)
    return result


def _knots(
    surface: Any, axis: str, low: float, high: float, *, cancelled: CancelToken | None = None
) -> tuple[float, ...]:
    """Innere Basisknoten im wirklichen Trimmintervall, auch über einer periodischen Naht."""
    count = getattr(surface, f"Nb{axis}Knots", None)
    if count is None:
        return ()
    total = count()
    if total > _MAX_PATCHES:
        raise _unresolved_integral()
    period = (
        float(getattr(surface, f"{axis}Period")())
        if getattr(surface, f"Is{axis}Periodic")()
        else None
    )
    values = set()
    for index in range(1, total + 1):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        value = float(getattr(surface, f"{axis}Knot")(index))
        if period is None:
            if low < value < high:
                values.add(value)
            continue
        first = math.floor((low - value) / period) + 1
        last = math.ceil((high - value) / period)
        if last - first > _MAX_PATCHES:
            raise _unresolved_integral()
        for shift in range(first, last):
            values.add(value + shift * period)
            if len(values) > _MAX_PATCHES:
                raise _unresolved_integral()
    return tuple(sorted(values))


def _patches(
    original: Any, subdivisions: int, *, cancelled: CancelToken | None = None
) -> list[Any]:
    """Zerlegt eine private Flächenkopie und erhält ihre äußeren und inneren Drähte."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp_Face
    from OCP.BRepLib import BRepLib
    from OCP.ShapeBuild import ShapeBuild_ReShape
    from OCP.ShapeFix import ShapeFix_ComposeShell
    from OCP.ShapeUpgrade import ShapeUpgrade_SplitSurface
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    face = TopoDS.Face(BRepBuilderAPI_Copy(original, True, False).Shape())
    location = TopLoc_Location()
    surface = BRep_Tool.Surface_s(face, location)
    low_u, high_u, low_v, high_v = BRepGProp_Face(face).Bounds()
    if not all(math.isfinite(value) for value in (low_u, high_u, low_v, high_v)):
        raise _unresolved_integral()
    basis = _spline_basis(face, cancelled=cancelled)
    u_values = _split_values(basis, "U", low_u, high_u, subdivisions, cancelled=cancelled)
    v_values = _split_values(basis, "V", low_v, high_v, subdivisions, cancelled=cancelled)
    if (u_values.Length() - 1) * (v_values.Length() - 1) > _MAX_PATCHES:
        raise _unresolved_integral()
    splitter = ShapeUpgrade_SplitSurface()
    splitter.Init(surface, low_u, high_u, low_v, high_v)
    splitter.SetUSplitValues(u_values)
    splitter.SetVSplitValues(v_values)
    splitter.Perform(True)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    composer = ShapeFix_ComposeShell()
    composer.Init(splitter.ResSurfaces(), location, face, _REPARAMETRIZATION_PRECISION)
    composer.SetMaxTolerance(_REPARAMETRIZATION_PRECISION)
    # Ohne expliziten Kontext dereferenziert OCCT hier einen leeren Handle.
    composer.SetContext(ShapeBuild_ReShape())
    if not composer.Perform():
        raise _unresolved_integral()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    result = composer.Result()
    if result.IsNull():
        raise _unresolved_integral()
    BRepLib.BuildCurves3d_s(result, _REPARAMETRIZATION_PRECISION)
    BRepLib.SameParameter_s(result, _REPARAMETRIZATION_PRECISION, True)
    if not BRepCheck_Analyzer(result).IsValid():
        raise _unresolved_integral()
    patches = _faces(result, cancelled=cancelled)
    if not patches:
        raise _unresolved_integral()
    return patches


def _integrate(shape: Any, kind: str, *, cancelled: CancelToken | None = None) -> MassProperties:
    """Eine native Teilintegration liefert Masse, Schwerpunkt und Trägheit gemeinsam."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    props = GProp_GProps()
    if kind == "volume":
        error = BRepGProp.VolumeProperties_s(shape, props, _PATCH_RELATIVE_ERROR)
    else:
        error = BRepGProp.SurfaceProperties_s(shape, props, _PATCH_RELATIVE_ERROR)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not math.isfinite(error) or error < 0.0 or error > INTEGRAL_RELATIVE_ERROR:
        raise _unresolved_integral()
    return _from_native(props, inertia=kind == "surface")


def _converged(before: MassProperties, after: MassProperties) -> bool:
    """Fläche/Volumen, Schwerpunkt und Trägheit müssen gemeinsam konvergieren."""
    import numpy as np

    mass = abs(after.mass)
    if not math.isfinite(mass) or mass <= 0.0:
        return False
    if not math.isclose(before.mass, after.mass, rel_tol=INTEGRAL_RELATIVE_ERROR, abs_tol=0.0):
        return False
    old, new = np.asarray(before.inertia), np.asarray(after.inertia)
    inertia_scale = float(np.linalg.norm(new))
    span = math.sqrt(inertia_scale / mass)
    return bool(
        np.isfinite(new).all()
        and math.dist(before.centre, after.centre) <= INTEGRAL_RELATIVE_ERROR * span
        and np.linalg.norm(old - new) <= INTEGRAL_RELATIVE_ERROR * inertia_scale
    )


def _spanned_surface(face: Any, *, cancelled: CancelToken | None = None) -> MassProperties:
    """Der schnelle native Weg mit belegter Konvergenz zwischen Unterteilungen."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    before = None
    for subdivisions in _SUBDIVISIONS:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        for patch in _patches(face, subdivisions, cancelled=cancelled):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            builder.Add(compound, patch)
        total = _integrate(compound, "surface", cancelled=cancelled)
        if before is not None and _converged(before, total):
            return total
        before = total
    raise _unresolved_integral()


def _v_knots(face: Any, *, cancelled: CancelToken | None = None) -> tuple[float, ...]:
    """Innere V-Knoten verlangen explizite Schnitte der Randkurven."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    adaptor = BRepAdaptor_Surface(face)
    surface = _spline_basis(face, cancelled=cancelled)
    low, high = adaptor.FirstVParameter(), adaptor.LastVParameter()
    return _knots(surface, "V", low, high, cancelled=cancelled)


def _boundary_parameters(
    face: Any,
    edge: Any,
    native: Any,
    v_knots: tuple[float, ...],
    *,
    u_knots: tuple[float, ...] = (),
    cancelled: CancelToken | None = None,
) -> list[float]:
    """Trimmkurven-Knoten und ihre tatsächlichen Schnitte mit inneren U-/V-Knoten."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve2d
    from OCP.collections import Array1_double
    from OCP.Geom2d import Geom2d_Line
    from OCP.Geom2dAdaptor import Geom2dAdaptor_Curve
    from OCP.Geom2dInt import Geom2dInt_GInter
    from OCP.gp import gp_Dir2d, gp_Pnt2d
    from OCP.TopAbs import TopAbs_REVERSED

    first, last = native.FirstParameter(), native.LastParameter()
    # GetTKnots lässt OCCT 8 bei analytischen Trägerflächen leer, selbst
    # wenn deren Trimmkurve eine BSpline ist. LKnots erhält ihre Orientierung.
    knots = Array1_double(1, native.LIntSubs() + 1)
    native.LKnots(knots)
    parameters = {
        float(value)
        for index in range(knots.Lower(), knots.Upper() + 1)
        if first < (value := knots.Value(index)) < last
    }
    if u_knots or v_knots:
        curve = BRepAdaptor_Curve2d(edge, face).Curve()
        if edge.Orientation() == TopAbs_REVERSED:
            curve = curve.Reversed()
        boundary = Geom2dAdaptor_Curve(curve, first, last)
        low_u, high_u, low_v, high_v = native.Bounds()
        # Eine relative Rechengenauigkeit im UV-Raum, keine Längentoleranz.
        precision = _PATCH_RELATIVE_ERROR * max(high_u - low_u, high_v - low_v)
        lines = chain(
            ((gp_Pnt2d(u, 0.0), gp_Dir2d(0.0, 1.0)) for u in u_knots),
            ((gp_Pnt2d(0.0, v), gp_Dir2d(1.0, 0.0)) for v in v_knots),
        )
        for point, direction in lines:
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            line = Geom2dAdaptor_Curve(Geom2d_Line(point, direction))
            crossing = Geom2dInt_GInter(boundary, line, precision, precision)
            if not crossing.IsDone():
                raise _unresolved_integral()
            for index in range(1, crossing.NbPoints() + 1):
                if cancelled is not None:
                    cancelled.raise_if_cancelled()
                parameter = float(crossing.Point(index).ParamOnFirst())
                if first < parameter < last:
                    parameters.add(parameter)
    return sorted(parameters)


def _uv_moments(
    face: Any,
    origin: Vec3,
    size: float,
    kind: Literal["volume", "surface"],
    *,
    cancelled: CancelToken | None = None,
) -> tuple[Any, float]:
    """Green-Integral entlang der ursprünglichen, gerichteten UV-Trimmkurven.

    Für jeden Moment gilt: Randintegral der U-Stammfunktion mal dV.
    Innere Drähte subtrahieren sich über ihren Umlaufsinn. OCCT liefert
    Trimmung, Knotenspannen und exakte Ableitungen; die Quadratur erhält
    Fehlergrenzen für alle normalisierten Momente einschließlich der
    inneren U-Integration. Keine Kopie der Geometrie wird verändert.
    """
    import numpy as np
    from OCP.BRepGProp import BRepGProp_Domain, BRepGProp_Face
    from OCP.gp import gp_Pnt, gp_Pnt2d, gp_Vec, gp_Vec2d
    from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from scipy.integrate import quad_vec

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    forward = TopoDS.Face(face.Oriented(TopAbs_FORWARD))
    reference = np.asarray(origin)
    orientation = -1.0 if face.Orientation() == TopAbs_REVERSED else 1.0
    count = 10 if kind == "surface" else 4
    native = BRepGProp_Face(forward, True)
    v_knots = _v_knots(forward, cancelled=cancelled)
    low_u, high_u, _, _ = native.Bounds()
    knots = native.GetUKnots(low_u, high_u)
    u_knots = sorted(
        {float(knots.Value(index)) for index in range(knots.Lower(), knots.Upper() + 1)}
        | set(
            _knots(
                _spline_basis(forward, cancelled=cancelled), "U", low_u, high_u, cancelled=cancelled
            )
        )
    )
    point, normal = gp_Pnt(), gp_Vec()
    uv, derivative = gp_Pnt2d(), gp_Vec2d()
    evaluations = 0

    def along_u(u: float, v: float) -> Any:
        """Normierte Flächenmomente oder Volumenfluss am ursprünglichen Flächenpunkt."""
        nonlocal evaluations
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        evaluations += 1
        if evaluations > _MAX_EVALUATIONS:
            raise _unresolved_integral()
        native.Normal(float(u), float(v), point, normal)
        x, y, z = (np.array((point.X(), point.Y(), point.Z())) - reference) / size
        if kind == "volume":
            # Divergenzsatz: div(r)=3 und div(r_i*r)=4. Alle Flächen benutzen
            # denselben Ursprung; die gerichtete Normale erhält innere Hohlräume.
            flux = (x * normal.X() + y * normal.Y() + z * normal.Z()) * orientation / size**2
            return np.array((1.0 / 3.0, x / 4.0, y / 4.0, z / 4.0)) * flux
        return (
            np.array((1.0, x, y, z, x * x, y * y, z * z, x * y, x * z, y * z))
            * normal.Magnitude()
            / size**2
        )

    def along_boundary(parameter: float) -> Any:
        """Innere Integration bis zur Randkurve, mit mitgeführter Fehlerschranke."""
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        native.D12d(float(parameter), uv, derivative)
        u, v, dv = uv.X(), uv.Y(), derivative.Y()
        if not all(math.isfinite(value) for value in (u, v, dv)):
            raise _unresolved_integral()
        if abs(dv) <= 0.0 or abs(u - low_u) <= 0.0:
            return np.zeros(count + 1)
        values, error, info = quad_vec(
            lambda position: along_u(position, v),
            low_u,
            u,
            epsabs=_PATCH_RELATIVE_ERROR,
            epsrel=_PATCH_RELATIVE_ERROR,
            norm="max",
            points=[knot for knot in u_knots if min(low_u, u) < knot < max(low_u, u)],
            full_output=True,
        )
        if not info.success or not math.isfinite(error) or error < 0.0:
            raise _unresolved_integral()
        return np.concatenate((values * dv, (float(error) * abs(dv),)))

    domain = BRepGProp_Domain(forward)
    moments = np.zeros(count + 1)
    outer_error = 0.0
    while domain.More():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        edge = domain.Value()
        domain.Next()
        if not native.Load(edge):
            raise _unresolved_integral()
        first, last = native.FirstParameter(), native.LastParameter()
        if not math.isfinite(first) or not math.isfinite(last):
            raise _unresolved_integral()
        parameters = _boundary_parameters(
            forward, edge, native, v_knots, u_knots=tuple(u_knots), cancelled=cancelled
        )
        values, error, info = quad_vec(
            along_boundary,
            first,
            last,
            epsabs=_PATCH_RELATIVE_ERROR,
            epsrel=_PATCH_RELATIVE_ERROR,
            norm="max",
            points=parameters,
            full_output=True,
        )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if not info.success or not math.isfinite(error) or error < 0.0:
            raise _unresolved_integral()
        moments += values
        outer_error += float(error)
    error = outer_error + float(moments[-1])
    if not np.isfinite(moments).all() or not math.isfinite(error):
        raise _unresolved_integral()
    return moments[:-1], error


def _local_frame(shape: Any, *, cancelled: CancelToken | None = None) -> tuple[Vec3, float]:
    """Die native Begrenzung konditioniert die Integrale, ohne ein Maß vorwegzunehmen."""
    import numpy as np
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    from .kernel import box_limits

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    bounds = Bnd_Box()
    bounds.SetGap(0.0)
    BRepBndLib.AddOptimal_s(shape, bounds, False, False)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if bounds.IsVoid() or bounds.IsWhole():
        raise _unresolved_integral()
    limits = box_limits(bounds)
    low, high = np.asarray(limits[:3]), np.asarray(limits[3:])
    size = float(np.linalg.norm(high - low))
    origin = cast(Vec3, tuple(float(value) for value in (low + high) / 2.0))
    if not math.isfinite(size) or size <= 0.0:
        raise _unresolved_integral()
    return origin, size


def _uv_surface(face: Any, *, cancelled: CancelToken | None = None) -> MassProperties:
    """Fläche, Schwerpunkt und Trägheit aus zehn gemeinsam begrenzten UV-Momenten."""
    import numpy as np

    origin, size = _local_frame(face, cancelled=cancelled)
    moments, error = _uv_moments(face, origin, size, "surface", cancelled=cancelled)
    if moments[0] <= 0.0 or error > INTEGRAL_RELATIVE_ERROR * moments[0]:
        raise _unresolved_integral()
    centre = moments[1:4] / moments[0]
    xx, yy, zz, xy, xz, yz = moments[4:10]
    second = np.array(((xx, xy, xz), (xy, yy, yz), (xz, yz, zz)))
    covariance = second - moments[0] * np.outer(centre, centre)
    tensor = (np.trace(covariance) * np.eye(3) - covariance) * size**4
    return MassProperties(
        float(moments[0] * size**2),
        cast(Vec3, tuple(float(value) for value in np.asarray(origin) + centre * size)),
        cast(
            tuple[Vec3, Vec3, Vec3], tuple(tuple(float(value) for value in row) for row in tensor)
        ),
    )


def _uv_volume(shape: Any, *, cancelled: CancelToken | None = None) -> MassProperties:
    """Volumen und Schwerpunkt aus dem gerichteten Fluss über die Originalflächen."""
    import numpy as np
    from OCP.TopAbs import TopAbs_FACE, TopAbs_FORWARD, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    origin, size = _local_frame(shape, cancelled=cancelled)
    values, errors = [], []
    # Gemeinsame Wände zweier Körper müssen mit beiden Orientierungen zählen;
    # eine Indexkarte würde diese gerichteten Vorkommen zusammenfassen.
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        face = TopoDS.Face(explorer.Current())
        explorer.Next()
        if face.Orientation() not in (TopAbs_FORWARD, TopAbs_REVERSED):
            continue
        moments, error = _uv_moments(face, origin, size, "volume", cancelled=cancelled)
        values.append(moments)
        errors.append(error)
    total = np.array([math.fsum(value[index] for value in values) for index in range(4)])
    if total[0] <= 0.0 or math.fsum(errors) > INTEGRAL_RELATIVE_ERROR * total[0]:
        raise _unresolved_integral()
    centre = np.asarray(origin) + total[1:4] / total[0] * size
    return MassProperties(
        float(total[0] * size**3), cast(Vec3, tuple(float(value) for value in centre)), None
    )


def _surface_sum(
    entries: list[MassProperties], *, cancelled: CancelToken | None = None
) -> MassProperties:
    """Führt Flächenmomente mit dem Satz von Steiner in einem Schwerpunkt zusammen."""
    import numpy as np

    mass = math.fsum(entry.mass for entry in entries)
    if not entries or mass <= 0.0:
        raise _unresolved_integral()
    origin = np.asarray(entries[0].centre)
    centre = (
        origin + sum(entry.mass * (np.asarray(entry.centre) - origin) for entry in entries) / mass
    )
    tensor = np.zeros((3, 3))
    for entry in entries:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        offset = np.asarray(entry.centre) - centre
        tensor += np.asarray(entry.inertia) + entry.mass * (
            np.dot(offset, offset) * np.eye(3) - np.outer(offset, offset)
        )
    return MassProperties(
        mass,
        cast(Vec3, tuple(float(value) for value in centre)),
        cast(
            tuple[Vec3, Vec3, Vec3], tuple(tuple(float(value) for value in row) for row in tensor)
        ),
    )


def properties(
    shape: Any, kind: Literal["volume", "surface"], *, cancelled: CancelToken | None = None
) -> MassProperties:
    """Geprüfte Maße; schwierige Trimmungen rechnen auf den ursprünglichen Randkurven."""
    try:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        faces = _faces(shape, cancelled=cancelled)
        requires_spans = []
        for face in faces:
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            requires_spans.append(_needs_spans(face, cancelled=cancelled))
        if not any(requires_spans):
            try:
                return _integrate(shape, kind, cancelled=cancelled)
            except OperationCancelled:
                raise
            except PROGRAMMING_ERRORS:
                raise
            except Exception:
                if kind == "volume":
                    return _uv_volume(shape, cancelled=cancelled)
        if kind == "volume":
            # Native GK-Integrale lassen V-Spannen aus und können bei der
            # Schwerpunktrechnung nicht terminieren. Der gemeinsame UV-Weg
            # begrenzt beide Momente an den tatsächlichen Knotenspannen.
            return _uv_volume(shape, cancelled=cancelled)
        measured = []
        for face, split in zip(faces, requires_spans, strict=True):
            try:
                if cancelled is not None:
                    cancelled.raise_if_cancelled()
                measured.append(
                    _spanned_surface(face, cancelled=cancelled)
                    if split
                    else _integrate(face, kind, cancelled=cancelled)
                )
            except OperationCancelled:
                raise
            except PROGRAMMING_ERRORS:
                raise
            except Exception:
                measured.append(_uv_surface(face, cancelled=cancelled))
        return _surface_sum(measured, cancelled=cancelled)
    except OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except GeometryError:
        raise
    except Exception as problem:
        raise _unresolved_integral() from problem
