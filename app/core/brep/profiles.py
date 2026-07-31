"""Vom Skizzenumriss zum exakten Körper (Bauplan §30.1).

Hier wird aus einem :class:`~app.core.sketch.profile.Profile` ein B-Rep-Körper:
extrudiert, rotiert, entlang eines Bogens geführt oder zwischen zwei Umrissen
aufgespannt. Bögen und Kreise reisen als Kurven, nicht als Segmentfolgen — das
ist der Grund, warum die Skizzen-Operationen gegen diesen Kern rechnen (§30).

Dazu die zwei Formwerkzeuge auf fertigen Körpern, die ohne echte Flächen nicht
gehen: die exakte Schale und die Formschräge.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from app.core.brep.kernel import Solid, require
from app.core.errors import PROGRAMMING_ERRORS, GeometryError, ValidationError
from app.core.log import get_logger
from app.core.sketch.profile import Profile
from app.core.types import Point2
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Wie ein 2D-Profilpunkt in den Raum kommt. Die Ebene entscheidet die Operation.
_Lift = Callable[[Point2], Any]


def _lift_xy(point: Point2) -> Any:
    """Skizzenebene XY auf Höhe null — der Normalfall beim Extrudieren."""
    from OCP.gp import gp_Pnt

    return gp_Pnt(point[0], point[1], 0.0)


def _lift_xz(point: Point2) -> Any:
    """Skizze als Querschnitt in der XZ-Ebene — x wird Radius, y wird Höhe."""
    from OCP.gp import gp_Pnt

    return gp_Pnt(point[0], 0.0, point[1])


def _wire(profile: Profile, lift: _Lift) -> Any:
    """Der Umriss als Draht: Strecken als Segmente, Bögen als echte Bögen."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.GC import GC_MakeArcOfCircle

    maker = BRepBuilderAPI_MakeWire()
    if profile.circle is not None:
        centre, radius = profile.circle
        maker.Add(_circle_edge(centre, radius, lift))
        return maker.Wire()
    for segment in profile.segments:
        if segment.kind == "line":
            edge = BRepBuilderAPI_MakeEdge(lift(segment.start), lift(segment.end)).Edge()
        else:
            assert segment.via is not None  # profile_of setzt via bei jedem Bogen
            curve = GC_MakeArcOfCircle(
                lift(segment.start), lift(segment.via), lift(segment.end)
            ).Value()
            edge = BRepBuilderAPI_MakeEdge(curve).Edge()
        maker.Add(edge)
    return maker.Wire()


def _circle_edge(centre: Point2, radius: float, lift: _Lift) -> Any:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Vec

    origin = lift(centre)
    above = lift((centre[0], centre[1] + 1.0))
    aside = lift((centre[0] + 1.0, centre[1]))
    normal = gp_Vec(origin, aside).Crossed(gp_Vec(origin, above))
    circle = gp_Circ(gp_Ax2(origin, gp_Dir(normal)), radius)
    return BRepBuilderAPI_MakeEdge(circle).Edge()


def _face(profile: Profile, lift: _Lift) -> Any:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    return BRepBuilderAPI_MakeFace(_wire(profile, lift), True).Face()


def extrude(profile: Profile, height: float) -> Solid:
    """Zieht den Umriss senkrecht nach oben auf — der Boden liegt auf Z = 0."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    if height <= 0.0:
        raise ValidationError("height", _("Dieses Maß muss größer als null sein."), value=height)
    return Solid(BRepPrimAPI_MakePrism(_face(profile, _lift_xy), gp_Vec(0.0, 0.0, height)).Shape())


def revolve(profile: Profile, angle_deg: float) -> Solid:
    """Rotiert den Querschnitt um die Z-Achse.

    Der Umriss wird in der XZ-Ebene gelesen: seine x-Richtung ist der Abstand
    von der Achse, seine y-Richtung die Höhe. Ein Querschnitt, der über die
    Achse hinüberreicht, würde sich selbst durchdringen und wird abgewiesen."""
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

    if not 0.0 < angle_deg <= 360.0:
        raise ValidationError(
            "angle", _("Der Winkel muss zwischen null und 360 Grad liegen."), value=angle_deg
        )
    if _leftmost(profile) < -EPS_GEOM:
        raise ValidationError(
            "offset",
            _("Der Querschnitt muss rechts der Achse liegen — Abstand vergrößern."),
            value=_leftmost(profile),
            constraint="crosses_axis",
        )
    axis = gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0))
    builder = BRepPrimAPI_MakeRevol(_face(profile, _lift_xz), axis, math.radians(angle_deg))
    return Solid(builder.Shape())


def sweep_arc(profile: Profile, bend_radius: float, bend_deg: float) -> Solid:
    """Führt den Umriss entlang eines Bogens: senkrecht startend, zur Seite kippend.

    Der Pfad beginnt im Ursprung nach oben und krümmt sich mit ``bend_radius``
    in Richtung +X, bis ``bend_deg`` erreicht ist — ein Rohrbogen."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
    from OCP.GC import GC_MakeArcOfCircle

    if not 1.0 <= bend_deg <= 180.0:
        raise ValidationError(
            "bend_angle", _("Der Winkel muss zwischen eins und 180 Grad liegen."), value=bend_deg
        )
    if bend_radius <= _rightmost(profile) + EPS_GEOM:
        raise ValidationError(
            "bend_radius",
            _("Der Bogenradius muss größer sein als der halbe Querschnitt."),
            value=bend_radius,
            constraint="kinks_inside",
        )

    def along(theta_deg: float) -> Any:
        from OCP.gp import gp_Pnt

        theta = math.radians(theta_deg)
        return gp_Pnt(bend_radius * (1.0 - math.cos(theta)), 0.0, bend_radius * math.sin(theta))

    curve = GC_MakeArcOfCircle(along(0.0), along(bend_deg / 2.0), along(bend_deg)).Value()
    spine = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(curve).Edge()).Wire()
    builder = BRepOffsetAPI_MakePipe(spine, _face(profile, _lift_xy))
    return _finished(builder, _("Der Bogen ist für diesen Querschnitt zu eng."))


def loft(bottom: Profile, top: Profile, height: float) -> Solid:
    """Spannt einen Körper zwischen zwei Umrissen auf — unten auf Z = 0."""
    require()
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.gp import gp_Pnt

    if height <= 0.0:
        raise ValidationError("height", _("Dieses Maß muss größer als null sein."), value=height)

    def lifted(point: Point2) -> Any:
        return gp_Pnt(point[0], point[1], height)

    builder = BRepOffsetAPI_ThruSections(True, False)
    builder.AddWire(_wire(bottom, _lift_xy))
    builder.AddWire(_wire(top, lifted))
    return _finished(builder, _("Zwischen diesen beiden Umrissen entsteht kein Körper."))


def shell_open_top(solid: Solid, thickness: float) -> Solid:
    """Höhlt den Körper exakt aus und lässt die Oberseite offen.

    Entfernt werden alle ebenen Flächen, die nach oben zeigen und auf der
    höchsten Ebene des Körpers liegen — bei einem Kasten der Deckel."""
    require()
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.TopTools import TopTools_ListOfShape

    if thickness <= 0.0:
        raise ValidationError("wall", _("Dieses Maß muss größer als null sein."), value=thickness)
    tops = _top_faces(solid)
    if not tops:
        raise GeometryError(
            detail=_("Dieser Körper hat keine ebene Oberseite, die sich öffnen ließe."),
        )
    removed = TopTools_ListOfShape()
    for face in tops:
        removed.Append(face)
    builder = BRepOffsetAPI_MakeThickSolid()
    builder.MakeThickSolidByJoin(solid.shape, removed, -thickness, EPS_GEOM)
    return _finished(builder, _("Für diese Wandstärke ist im Körper kein Platz."), solid)


def draft_vertical(solid: Solid, angle_deg: float) -> Solid:
    """Stellt alle senkrechten Flächen um den Winkel an — die Formschräge.

    Neutral bleibt die Standfläche auf Z = 0: dort behält der Körper sein Maß,
    nach oben wird er schmaler."""
    require()
    from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt

    if not 0.0 < angle_deg <= 30.0:
        raise ValidationError(
            "angle", _("Der Winkel muss zwischen null und 30 Grad liegen."), value=angle_deg
        )
    uprights = _upright_faces(solid)
    if not uprights:
        raise GeometryError(detail=_("Dieser Körper hat keine senkrechten Flächen."))
    neutral = gp_Pln(gp_Ax3(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0)))
    builder = BRepOffsetAPI_DraftAngle(solid.shape)
    for face in uprights:
        builder.Add(face, gp_Dir(0.0, 0.0, 1.0), math.radians(angle_deg), neutral)
    return _finished(
        builder, _("Die Formschräge lässt sich an diesen Flächen nicht anlegen."), solid
    )


def bounds(solid: Solid) -> tuple[float, float, float, float, float, float]:
    """Der Hüllquader eines Körpers: xmin, ymin, zmin, xmax, ymax, zmax."""
    require()
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(solid.shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return (xmin, ymin, zmin, xmax, ymax, zmax)


# --- Innereien -------------------------------------------------------------------


def _leftmost(profile: Profile) -> float:
    if profile.circle is not None:
        centre, radius = profile.circle
        return centre[0] - radius
    values = [point[0] for segment in profile.segments for point in _points(segment)]
    return min(values)


def _rightmost(profile: Profile) -> float:
    if profile.circle is not None:
        centre, radius = profile.circle
        return centre[0] + radius
    values = [point[0] for segment in profile.segments for point in _points(segment)]
    return max(values)


def _points(segment: Any) -> list[Point2]:
    found = [segment.start, segment.end]
    if segment.via is not None:
        found.append(segment.via)
    return found


def _top_faces(solid: Solid) -> list[Any]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.Add_s(solid.shape, box)
    _, _, _, _, _, top = box.Get()
    found = []
    for face, normal, centre in _planar_faces(solid):
        if normal[2] > 0.9 and abs(centre[2] - top) <= 1e-4:
            found.append(face)
    return found


def _upright_faces(solid: Solid) -> list[Any]:
    return [face for face, normal, _ in _planar_faces(solid) if abs(normal[2]) < 0.1]


def _planar_faces(solid: Solid) -> list[tuple[Any, tuple[float, float, float], Any]]:
    """Jede ebene Fläche mit ihrer nach außen zeigenden Normale und Mitte."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_REVERSED

    found = []
    for face in solid.faces():
        surface = BRepAdaptor_Surface(face)
        if surface.GetType() != GeomAbs_Plane:
            continue
        direction = surface.Plane().Axis().Direction()
        normal = [direction.X(), direction.Y(), direction.Z()]
        if face.Orientation() == TopAbs_REVERSED:
            normal = [-normal[0], -normal[1], -normal[2]]
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        centre = props.CentreOfMass()
        found.append(
            (face, (normal[0], normal[1], normal[2]), (centre.X(), centre.Y(), centre.Z()))
        )
    return found


def _finished(builder: Any, sentence: Any, base: Solid | None = None) -> Solid:
    """Baut fertig und macht aus dem Scheitern einen Satz mit Vorschlag (§33.1)."""
    try:
        builder.Build()
        if not builder.IsDone():
            raise GeometryError(detail=sentence)
        shape = builder.Shape()
    except GeometryError:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # OpenCASCADE wirft eigene Ausnahmearten
        raise GeometryError(detail=sentence) from problem
    _log.info("profile build via %s", type(builder).__name__)
    return base.replacing(shape) if base is not None else Solid(shape)
