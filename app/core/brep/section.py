"""Der exakte Ebenenschnitt eines Körpers (P3.5, Bauplan §30.1).

Die Skizze holt die Schnittkurve eines Körpers als Hilfsgeometrie herein
(``sketch.edit.project``, Weg 1: ein fremdes Teil anpassen). Am Netz ist das
ein Sehnenzug aus Dreieckskanten; am exakten Körper schneidet
``BRepAlgoAPI_Section`` die Ebene mit den echten Flächen, und **ein Kreis
bleibt ein Kreis**: Die Bohrung liegt als Kreis mit ihrem Mittelpunkt in der
Zeichnung, eine Verrundung als Bogen, eine Gerade als eine Strecke statt als
Folge kurzer Stücke. Was weder Strecke noch Kreis ist — die Ellipse eines
schräg geschnittenen Zylinders, der Schnitt durch eine Freiformfläche —,
kommt als Spline durch Punkte, die nach derselben Abweichung verteilt sind wie
die Vernetzung (``DEFLECTION``); die Skizze kennt keine Ellipse (P6.6a).

Schnitt und Kontur sind hier dieselbe Frage: Liegt die Ebene bündig auf einer
Fläche des Körpers — der Normalfall einer Skizze auf einer Fläche —, liefert
der Schnitt deren Ränder, Außen- wie Innenrand. Liegt sie im Körper, liefert
er den Querschnitt. Beide Fälle kommen aus demselben nativen Aufruf.

Gerechnet wird an einer privaten Kopie; die Form des Körpers bleibt, wie sie
ist (``kernel``, Eigentum an der nativen Form).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

from app.core.brep.kernel import DEFLECTION, Solid, copy_shape, require
from app.core.errors import CANCEL, CORRECT_INPUT, GeometryError
from app.core.types import CancelToken, Point2, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

#: Was eine Schnittkurve in der Skizze wird — dieselben Arten und dieselbe
#: Punktfolge wie ``SketchElement``: Strecke (Anfang, Ende), Kreis (Mitte,
#: Randpunkt), Bogen (Mitte, Anfang, Ende — gegen den Uhrzeigersinn), Spline
#: (seine Stützpunkte).
SectionKind = Literal["line", "circle", "arc", "spline"]


@dataclass(frozen=True, slots=True)
class SectionCurve:
    """Eine Kurve des Schnitts in den Koordinaten der Zeichenebene."""

    kind: SectionKind
    points: tuple[Point2, ...]


def plane_section(
    solid: Solid,
    origin: Vec3,
    x_axis: Vec3,
    y_axis: Vec3,
    *,
    deflection: float = DEFLECTION,
    cancelled: CancelToken | None = None,
) -> tuple[SectionCurve, ...]:
    """Die Kurven, in denen die Ebene durch ``origin`` den Körper trifft.

    ``x_axis`` und ``y_axis`` sind die Zeichenrichtungen der Skizze; die
    Ebene ist die, die sie aufspannen. Ein Bogen läuft in der Zeichnung
    gegen den Uhrzeigersinn von ``x_axis`` nach ``y_axis`` gezählt — so liest
    ihn der Löser —, gleich wie herum die Schnittkante im Raum läuft. Ein
    Vollkreis, den die Schnittkanten in mehrere Bögen teilen (an der Naht
    der Zylinderfläche, an einer Nachbarfläche), kommt als ein Kreis heraus.
    Leer, wenn die Ebene den Körper nicht trifft.
    """
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    normal = _cross(x_axis, y_axis)
    length = math.sqrt(sum(value * value for value in normal))
    if length <= EPS_GEOM:
        raise ValueError("the drawing axes of a section plane must not be parallel")
    unit = (normal[0] / length, normal[1] / length, normal[2] / length)
    plane = gp_Pln(gp_Ax3(gp_Pnt(*origin), gp_Dir(*unit), gp_Dir(*x_axis)))
    working, _faces, _edges = copy_shape(solid.shape)
    section = BRepAlgoAPI_Section(working, plane, False)
    section.Approximation(True)
    section.Build()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not section.IsDone():
        raise GeometryError(
            detail=_(
                "Der Schnitt durch diesen Körper ließ sich nicht bilden. "
                "Wählen Sie eine andere Ebene."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )

    def flat(point: Any) -> Point2:
        offset = (point.X() - origin[0], point.Y() - origin[1], point.Z() - origin[2])
        return (_dot(offset, x_axis), _dot(offset, y_axis))

    curves: list[SectionCurve] = []
    circles: dict[int, list[tuple[float, float, Point2, float]]] = {}
    circle_keys: list[tuple[Point2, float]] = []
    walk = TopExp_Explorer(section.Shape(), TopAbs_EDGE)
    while walk.More():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        edge = TopoDS.Edge(walk.Current())
        walk.Next()
        curve = BRepAdaptor_Curve(edge)
        first, last = float(curve.FirstParameter()), float(curve.LastParameter())
        start, end = flat(curve.Value(first)), flat(curve.Value(last))
        kind = curve.GetType()
        if kind == GeomAbs_Line:
            if math.dist(start, end) > EPS_GEOM:
                curves.append(SectionCurve("line", (start, end)))
            continue
        if kind == GeomAbs_Circle:
            circle = curve.Circle()
            centre = flat(circle.Location())
            radius = float(circle.Radius())
            direction = circle.Axis().Direction()
            forward = _dot((direction.X(), direction.Y(), direction.Z()), unit) > 0.0
            # Der Löser läuft einen Bogen gegen den Uhrzeigersinn; läuft die
            # Kante andersherum, tauschen Anfang und Ende.
            begin, finish = (start, end) if forward else (end, start)
            key = _circle_key(circle_keys, centre, radius)
            circles.setdefault(key, []).append((first, last, begin, radius))
            curves.append(SectionCurve("arc", (centre, begin, finish)))
            continue
        points = _sampled(curve, first, last, deflection, flat)
        if len(points) == 2:
            curves.append(SectionCurve("line", points))
        elif len(points) > 2:
            curves.append(SectionCurve("spline", points))
    return tuple(_whole_circles(curves, circles, circle_keys))


@dataclass(frozen=True, slots=True)
class SectionRegion:
    """Ein zusammenhängendes Stück eines waagerechten Querschnitts: Umriss und Löcher.

    ``face`` ist das Materialstück selbst, ``outline`` die gefüllte Fläche
    seines Außenrands, ``holes`` sind die Flächen seiner Innenränder, jede für
    sich gefüllt — alle nach oben gerichtet, in der Höhe des Schnitts. So
    braucht sie ein Deckel: den Umriss zum Abdecken, die Löcher als Hohlräume
    und das Material tiefer unten als das, woran der Kragen vorbei muss
    (``geom.lid``, am Netz der Schnitt aus ``slice.analysis.cross_section``).
    """

    face: Any
    outline: Any
    holes: tuple[Any, ...]


def horizontal_regions(
    solid: Solid, z: float, *, cancelled: CancelToken | None = None
) -> tuple[SectionRegion, ...]:
    """Der Querschnitt des Körpers in der waagerechten Ebene auf Höhe ``z``, als Flächen.

    Der gemeinsame Teil aus Körper und einer Ebenenfläche, die ihn überragt
    (``BRepAlgoAPI_Common``): Heraus kommen die Materialstücke der Ebene mit
    ihren echten Rändern — ein gerundeter Hohlraum bleibt ein gerundeter,
    eine Bohrung ein Kreis. Leer, wenn die Ebene den Körper nicht trifft.
    Gerechnet wird an einer privaten Kopie.
    """
    require()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt
    from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from app.core.brep.profiles import upward

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    bounds = solid.bounds
    margin = max(float(value) for value in bounds.size) + 1.0
    plane = gp_Pln(gp_Ax3(gp_Pnt(0.0, 0.0, z), gp_Dir(0.0, 0.0, 1.0), gp_Dir(1.0, 0.0, 0.0)))
    sheet = BRepBuilderAPI_MakeFace(
        plane,
        float(bounds.minimum[0]) - margin,
        float(bounds.maximum[0]) + margin,
        float(bounds.minimum[1]) - margin,
        float(bounds.maximum[1]) + margin,
    ).Face()
    working, _faces, _edges = copy_shape(solid.shape)
    common = BRepAlgoAPI_Common(working, sheet)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if not common.IsDone():
        raise GeometryError(
            detail=_(
                "Der Schnitt durch diesen Körper ließ sich nicht bilden. "
                "Wählen Sie eine andere Ebene."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    regions: list[SectionRegion] = []
    walk = TopExp_Explorer(common.Shape(), TopAbs_FACE)
    while walk.More():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        face = TopoDS.Face(walk.Current())
        walk.Next()
        outer = BRepTools.OuterWire_s(face)
        holes: list[Any] = []
        wires = TopExp_Explorer(face, TopAbs_WIRE)
        while wires.More():
            wire = TopoDS.Wire(wires.Current())
            wires.Next()
            if not wire.IsSame(outer):
                holes.append(upward(BRepBuilderAPI_MakeFace(wire, True).Face()))
        regions.append(
            SectionRegion(
                upward(face), upward(BRepBuilderAPI_MakeFace(outer, True).Face()), tuple(holes)
            )
        )
    return tuple(regions)


def _whole_circles(
    curves: list[SectionCurve],
    circles: dict[int, list[tuple[float, float, Point2, float]]],
    keys: list[tuple[Point2, float]],
) -> list[SectionCurve]:
    """Bögen desselben Kreises, die zusammen eine volle Umdrehung bedecken, werden ein Kreis."""
    whole: set[int] = set()
    for key, pieces in circles.items():
        turn = sum(abs(last - first) for first, last, _begin, _radius in pieces)
        if turn >= math.tau - EPS_GEOM:
            whole.add(key)
    result: list[SectionCurve] = []
    placed: set[int] = set()
    for curve in curves:
        if curve.kind != "arc":
            result.append(curve)
            continue
        centre = curve.points[0]
        radius = math.dist(centre, curve.points[1])
        key = _circle_key(keys, centre, radius)
        if key not in whole:
            result.append(curve)
            continue
        if key in placed:
            continue
        placed.add(key)
        result.append(SectionCurve("circle", (centre, (centre[0] + radius, centre[1]))))
    return result


def _circle_key(keys: list[tuple[Point2, float]], centre: Point2, radius: float) -> int:
    """Die Nummer des Kreises mit dieser Mitte und diesem Radius — über Abstand, nicht Rundung."""
    for number, (known, known_radius) in enumerate(keys):
        if math.dist(known, centre) <= EPS_GEOM and abs(known_radius - radius) <= EPS_GEOM:
            return number
    keys.append((centre, radius))
    return len(keys) - 1


def _sampled(
    curve: Any, first: float, last: float, deflection: float, flat: Any
) -> tuple[Point2, ...]:
    """Eine freie Schnittkurve als Punktfolge nach Abweichung, ohne doppelte Punkte."""
    from OCP.GCPnts import GCPnts_QuasiUniformDeflection

    sampler = GCPnts_QuasiUniformDeflection(curve, max(deflection, EPS_GEOM), first, last)
    if sampler.IsDone() and sampler.NbPoints() >= 2:
        raw = [flat(sampler.Value(index)) for index in range(1, sampler.NbPoints() + 1)]
    else:
        raw = [flat(curve.Value(first)), flat(curve.Value(last))]
    points: list[Point2] = [raw[0]]
    for point in raw[1:]:
        if math.dist(point, points[-1]) > EPS_GEOM:
            points.append(point)
    return tuple(points) if len(points) >= 2 else ()


def _dot(one: Vec3 | tuple[float, float, float], other: Vec3) -> float:
    return float(one[0] * other[0] + one[1] * other[1] + one[2] * other[2])


def _cross(one: Vec3, other: Vec3) -> Vec3:
    return (
        one[1] * other[2] - one[2] * other[1],
        one[2] * other[0] - one[0] * other[2],
        one[0] * other[1] - one[1] * other[0],
    )
