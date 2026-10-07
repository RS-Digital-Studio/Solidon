"""Vom Skizzenumriss zum exakten Körper (Bauplan §30.1).

Hier wird aus einem :class:`~app.core.sketch.profile.Profile` ein B-Rep-Körper:
extrudiert, rotiert, entlang eines Bogens geführt oder zwischen zwei Umrissen
aufgespannt. Bögen und Kreise reisen als Kurven, nicht als Segmentfolgen — das
ist der Grund, warum die Skizzen-Operationen gegen diesen Kern rechnen (§30).

Dazu die zwei Solidonzeuge auf fertigen Körpern, die ohne echte Flächen nicht
gehen: die exakte Schale und die Formschräge.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import replace
from itertools import pairwise
from typing import Any, Final, Literal

from app.core.brep.canonical import PlaneSurface
from app.core.brep.kernel import DEFLECTION, Solid, boolean_builder, box_limits, require
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    CORRECT_INPUT,
    PROGRAMMING_ERRORS,
    Action,
    GeometryError,
    InternalError,
    OperationCancelled,
    ValidationError,
    require_positive,
)
from app.core.log import get_logger
from app.core.sketch.planes import to_world
from app.core.sketch.profile import (
    Profile,
    ProfileSegment,
    arc_segment_extremes,
    arc_through,
    ellipse_frame,
    ellipse_segment_extremes,
    ellipse_turn,
    shifted,
    signed_area,
    spline_controls,
)
from app.core.types import CancelToken, PlaneFrame, Point2, Vec3
from app.core.units import EPS_GEOM, THREAD_MIN_CORE_SHARE, is_close, is_zero
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


def _lift_yz(point: Point2) -> Any:
    """Skizze in der YZ-Ebene — x wird Tiefe, y wird Höhe."""
    from OCP.gp import gp_Pnt

    return gp_Pnt(0.0, point[0], point[1])


#: Die drei Hauptebenen aus §30.1 mit ihrer Hebefunktion und der Richtung, in
#: die ein Prisma darauf wächst — die Normale der Ebene.
PLANES: dict[str, tuple[_Lift, tuple[float, float, float]]] = {
    "plane:xy": (_lift_xy, (0.0, 0.0, 1.0)),
    "plane:xz": (_lift_xz, (0.0, 1.0, 0.0)),
    "plane:yz": (_lift_yz, (1.0, 0.0, 0.0)),
}

#: Auf welchen Ebenen eine **Bahn** liegen darf (:func:`sweep_path`, E3): auf
#: den beiden, die senkrecht zum Querschnitt stehen. Eine Bahn in XY liefe in
#: der Ebene des Querschnitts — der Körper hätte keine Länge, und OpenCASCADE
#: meldete das als unerwarteten Fehler statt als Zeichnung, die nicht passt.
PATH_PLANES: Final = frozenset({"plane:xz", "plane:yz"})


def _wire(profile: Profile, lift: _Lift) -> Any:
    """Der Umriss als Draht: Strecken als Segmente, Bögen als echte Bögen.

    **Ein Bogen, dessen Ende auf seinem Anfang liegt, ist ein Kreis.** Aus drei
    Punkten, von denen zwei zusammenfallen, macht ``GC_MakeArcOfCircle`` keinen
    Bogen — es antwortete ``StdFail_NotDone``, und das wurde nach der Regel in
    ``errors.py`` zu „Im Programm ist ein unerwarteter Fehler aufgetreten".
    ``_arc_midpoint`` und ``_flat_curve`` lesen denselben Fall längst als
    vollen Umlauf; hier fehlte er als einziger.
    """
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
        elif segment.kind == "ellipse":
            edge = _ellipse_edge(segment, lift)
        elif segment.kind == "spline":
            # Ein kubisches Stück je Kante: Flächenintegrale des Kernes
            # müssen an den inneren Splineknoten getrennt werden. Eine
            # einzige zusammengesetzte Kante lieferte falsche Volumina.
            from OCP.collections import Array1_gp_Pnt
            from OCP.Geom import Geom_BezierCurve

            for piece in spline_controls(segment.through):
                poles = Array1_gp_Pnt(1, 4)
                for index, point in enumerate(piece, start=1):
                    poles.SetValue(index, lift(point))
                maker.Add(BRepBuilderAPI_MakeEdge(Geom_BezierCurve(poles)).Edge())
            continue
        else:
            assert segment.via is not None  # profile_of setzt via bei jedem Bogen
            turn = arc_through(segment.start, segment.via, segment.end)
            if turn is not None and abs(turn[2]) >= 2.0 * math.pi:
                maker.Add(_circle_edge(turn[0], turn[1], lift))
                continue
            curve = GC_MakeArcOfCircle(
                lift(segment.start), lift(segment.via), lift(segment.end)
            ).Value()
            edge = BRepBuilderAPI_MakeEdge(curve).Edge()
        maker.Add(edge)
    return maker.Wire()


def _spline_curve(points: tuple[Point2, ...], lift: _Lift) -> Any:
    """Die gezeichneten kubischen Stücke als exakte, zusammenhängende Kurve."""
    from OCP.collections import Array1_gp_Pnt
    from OCP.Geom import Geom_BSplineCurve

    return _spline_from_controls(points, lift, Array1_gp_Pnt, Geom_BSplineCurve)


def spline_curve_2d(points: tuple[Point2, ...]) -> Any:
    """Dieselbe Kurve für die ebene Schnittprüfung vor dem Körperbau."""
    from OCP.collections import Array1_gp_Pnt2d
    from OCP.Geom2d import Geom2d_BSplineCurve
    from OCP.gp import gp_Pnt2d

    return _spline_from_controls(
        points, lambda point: gp_Pnt2d(*point), Array1_gp_Pnt2d, Geom2d_BSplineCurve
    )


def _spline_from_controls(
    points: tuple[Point2, ...], lift: Any, array_type: Any, curve_type: Any
) -> Any:
    """Bézier-Stücke werden über gemeinsame Endpole in einen B-Spline gefasst."""
    from OCP.collections import Array1_double, Array1_int

    pieces = spline_controls(points)
    controls = [points[0], *(point for piece in pieces for point in piece[1:])]
    poles = array_type(1, len(controls))
    for index, point in enumerate(controls, start=1):
        poles.SetValue(index, lift(point))
    knots = Array1_double(1, len(pieces) + 1)
    multiplicities = Array1_int(1, len(pieces) + 1)
    for index in range(len(pieces) + 1):
        knots.SetValue(index + 1, float(index))
        multiplicities.SetValue(index + 1, 4 if index in (0, len(pieces)) else 3)
    return curve_type(poles, knots, multiplicities, 3, False)


def _ellipse_axes(segment: ProfileSegment, lift: _Lift) -> tuple[Any, float, float, Any]:
    """Die Ellipse eines Profilstücks im Raum: Lage, Haupt- und Nebenhalbachse.

    ``gp_Elips`` verlangt die längere Achse zuerst; die Skizze legt das nicht
    fest (die erste Achse darf die kürzere sein). Dann trägt die zweite
    Richtung die Hauptachse. Die Normale bleibt ``x`` kreuz ``y`` der gehobenen
    Zeichnung — derselbe Drehsinn wie beim Kreis (:func:`_circle_edge`), also
    läuft der Parameter der Ellipse gegen den Uhrzeigersinn der Zeichnung.
    """
    from OCP.gp import gp_Ax2, gp_Dir, gp_Elips, gp_Vec

    frame = ellipse_frame(*segment.ellipse) if segment.ellipse is not None else None
    assert frame is not None, "ein Ellipsenstück trägt seine Ellipse"
    ux, uy = frame.axis
    origin = lift(frame.centre)
    along = gp_Vec(origin, lift((frame.centre[0] + ux, frame.centre[1] + uy)))
    across = gp_Vec(origin, lift((frame.centre[0] - uy, frame.centre[1] + ux)))
    normal = gp_Dir(along.Crossed(across))
    if frame.first >= frame.second:
        axes = gp_Ax2(origin, normal, gp_Dir(along))
        return gp_Elips(axes, frame.first, frame.second), frame.first, frame.second, normal
    axes = gp_Ax2(origin, normal, gp_Dir(across))
    return gp_Elips(axes, frame.second, frame.first), frame.second, frame.first, normal


def _ellipse_edge(segment: ProfileSegment, lift: _Lift) -> Any:
    """Ein Stück Ellipse als **echte** Ellipsenkante — voll oder als Bogen.

    Der Bogen läuft vom Anfang zum Ende des Stücks, in der Richtung, die sein
    Stützpunkt sagt. ``GC_MakeArcOfEllipse`` mit ``True`` läuft gegen den
    Uhrzeigersinn vom ersten zum zweiten Punkt; mit ``False`` gibt es
    denselben Bogen umgekehrt zurück (gemessen im Paket P6.6 der Durchsicht
    0.5.0, `11c429cc2`; die Sonde ist nicht versioniert). Ein Stück im
    Uhrzeigersinn ist also der Bogen vom Ende zum Anfang, umgekehrt.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.GC import GC_MakeArcOfEllipse

    ellipse, _major, _minor, _normal = _ellipse_axes(segment, lift)
    _frame, sweep = ellipse_turn(segment)
    if abs(sweep) >= 2.0 * math.pi - EPS_GEOM:
        return BRepBuilderAPI_MakeEdge(ellipse).Edge()
    if sweep > 0.0:
        curve = GC_MakeArcOfEllipse(ellipse, lift(segment.start), lift(segment.end), True)
    else:
        curve = GC_MakeArcOfEllipse(ellipse, lift(segment.end), lift(segment.start), False)
    return BRepBuilderAPI_MakeEdge(curve.Value()).Edge()


def ellipse_curve_2d(segment: ProfileSegment) -> Any:
    """Dieselbe Ellipse für die ebene Schnittprüfung vor dem Körperbau.

    Für die Frage „kreuzt sich der Umriss" zählt nur, welche Punkte die Kurve
    überstreicht, nicht ihre Laufrichtung — genommen wird deshalb immer der
    Bogen gegen den Uhrzeigersinn über den Bereich des Stücks.
    """
    from OCP.GC import GC_MakeArcOfEllipse2d
    from OCP.Geom2d import Geom2d_Ellipse
    from OCP.gp import gp_Ax2d, gp_Dir2d, gp_Elips2d, gp_Pnt2d

    frame, sweep = ellipse_turn(segment)
    ux, uy = frame.axis
    centre = gp_Pnt2d(*frame.centre)
    if frame.first >= frame.second:
        ellipse = gp_Elips2d(gp_Ax2d(centre, gp_Dir2d(ux, uy)), frame.first, frame.second, True)
    else:
        ellipse = gp_Elips2d(gp_Ax2d(centre, gp_Dir2d(-uy, ux)), frame.second, frame.first, True)
    if abs(sweep) >= 2.0 * math.pi - EPS_GEOM:
        return Geom2d_Ellipse(ellipse)
    low, high = (segment.start, segment.end) if sweep > 0.0 else (segment.end, segment.start)
    return GC_MakeArcOfEllipse2d(ellipse, gp_Pnt2d(*low), gp_Pnt2d(*high), True).Value()


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
    """Die Fläche des Umrisses, mit seinen Löchern als inneren Ringen.

    Ein innerer Ring muss **gegen** den äußeren laufen, sonst gilt er
    OpenCASCADE als zweite Außenkontur und die Fläche wächst, statt ein Loch zu
    bekommen — ``Add`` sagt dazu nichts, der Fehler zeigt sich erst am Volumen.

    Ob umgedreht werden muss, entscheidet der **gemessene** Drehsinn, nicht die
    Annahme, jedes Loch sei linksherum gezeichnet. Bedingungslos umgedreht kippte
    genau der Fall in den Fehler, in dem das Loch schon gegen die Außenkontur
    lief: Aus dem Umdrehen wurde ein Gleichsinn, aus dem Loch eine zweite
    Außenkontur (+67 % Volumen). In der Zeichenfläche ist der Drehsinn reiner
    Zufall der Klickreihenfolge — es gibt kein Rechteckwerkzeug.

    **Gemessen wird mit** :func:`app.core.sketch.profile.signed_area`, und die
    rechnet Bögen exakt statt über ihre Sehnen. Hier stand ein Sehnenvieleck,
    und bei einem Bogen über 180° kippte es das Vorzeichen: Der Umriss eines
    Pac-Man maß -50 mm² statt +235,6, sein Loch galt damit als gleichsinnig,
    wurde umgedreht und damit zur zweiten Außenkontur — der Körper wuchs beim
    Bohren."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.TopoDS import TopoDS

    maker = BRepBuilderAPI_MakeFace(_wire(profile, lift), True)
    outer_left = signed_area(profile) >= 0.0
    for hole in profile.holes:
        wire = _wire(hole, lift)
        # Läuft das Loch im selben Drehsinn wie die Außenkontur, wird es
        # umgedreht (``Reversed`` gibt eine Form, ``TopoDS.Wire`` zieht sie
        # zum Draht zurück); lief es schon dagegen, bleibt es.
        if (signed_area(hole) >= 0.0) == outer_left:
            wire = TopoDS.Wire(wire.Reversed())
        maker.Add(wire)
    return maker.Face()


def _lift_frame(frame: PlaneFrame) -> _Lift:
    """Die Hebefunktion eines freien Rahmens (§30.1).

    Dieselbe Rechnung wie bei den drei Hauptebenen, nur mit Achsen, die nicht
    im Voraus feststehen: der Zeichenpunkt wird als Vielfaches der beiden
    Rahmenachsen auf den Ursprung addiert.

    **Gerechnet wird sie in** :func:`app.core.sketch.planes.to_world`, hier
    wird sie nur in ein OpenCASCADE-Objekt gehüllt. Der Grund für den Umzug
    ist die Zeichenfläche: Sie muss dieselbe Umrechnung machen wie die
    Auswertung, sonst liegt das Bild woanders als das Ergebnis — und sie muss
    es können, wenn OpenCASCADE gar nicht installiert ist. Die Richtung
    stimmt: ``brep`` darf von ``sketch`` abhängen, umgekehrt nicht, und
    ``planes`` bleibt damit frei von OCC.
    """

    def lift(point: Point2) -> Any:
        # Der Import bleibt in der Funktion: Diese Datei muss ohne
        # installiertes OpenCASCADE importierbar sein.
        from OCP.gp import gp_Pnt

        return gp_Pnt(*to_world(frame, point))

    return lift


def extrude(
    profile: Profile,
    height: float,
    plane: str = "plane:xy",
    frame: PlaneFrame | None = None,
) -> Solid:
    """Zieht den Umriss senkrecht zu seiner Ebene auf.

    Auf XY liegt der Boden bei Z = 0 und es geht nach oben — der Normalfall.
    Die beiden anderen Hauptebenen wachsen entlang ihrer eigenen Normalen;
    eine Skizze, die auf XZ liegt, wird nach Y aufgezogen und nicht nach oben.

    Ist ``frame`` gesetzt, gilt er statt ``plane``: die Skizze liegt dann auf
    einer Fläche eines vorhandenen Körpers, und ``plane`` trägt nur noch deren
    ID. Den Rahmen rechnet ``app.core.sketch.planes`` aus dem Feature aus — hier
    unten ist von Szenen nichts bekannt und soll auch nichts bekannt sein.

    Eine unbekannte Ebene wird abgewiesen statt stillschweigend als XY
    gelesen: bis hierher trug ``Sketch.plane`` seinen Wert bis in die
    Projektdatei, und niemand las ihn — eine falsche Ebene sah aus wie eine
    erfüllte Zusage.
    """
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    require_positive("height", height)
    if frame is not None:
        lift, normal = _lift_frame(frame), frame.normal
    elif plane in PLANES:
        lift, normal = PLANES[plane]
    else:
        raise ValidationError("plane", _("Diese Ebene gibt es nicht."), value=plane)
    direction = gp_Vec(normal[0] * height, normal[1] * height, normal[2] * height)
    # Durch ``_finished`` wie die vier Geschwister: Ein Prisma, das scheitert,
    # war sonst ein roher Kernfehler statt eines Satzes mit Vorschlag.
    return _finished(
        BRepPrimAPI_MakePrism(_face(profile, lift), direction),
        _("Aus diesem Umriss entsteht kein Körper."),
    )


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
    return _finished(builder, _("Aus diesem Querschnitt entsteht kein Drehkörper."))


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


def sweep_path(profile: Profile, path: Profile, plane: str = "plane:xz") -> Solid:
    """Führt den Umriss entlang einer **gezeichneten** Bahn (E3, RM-147).

    Der Gegenstück zu :func:`sweep_arc`, das nur einen Kreisbogen kennt: Ein
    Kabelkanal um zwei Ecken, ein Griff mit einer Kehle, ein Rohr, das einem
    Gehäuse folgt — alles, was keine gleichmäßige Krümmung hat.

    **Der Querschnitt liegt in XY, die Bahn senkrecht dazu**, genau wie beim
    Bogen. Die Bahn wird dafür so verschoben, dass ihr Anfang im Ursprung
    liegt: Sie beschreibt einen Verlauf und keinen Ort, und ein Körper, der
    davonläuft, weil jemand seine Zeichnung nicht am Nullpunkt begonnen hat,
    wäre eine Überraschung ohne Gewinn. Die Verschiebung steht im ``doc``-Satz
    der Operation.

    ``plane`` ist die Ebene der **Bahn** — ``plane:xz`` oder ``plane:yz``. Die
    Ebene des Querschnitts ist nicht wählbar, weil sie es beim Bogen auch nicht
    ist; wer sie einführt, führt sie an beiden Stellen ein.
    """
    require()
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBuilderAPI import BRepBuilderAPI_RightCorner
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.gp import gp_Pnt, gp_Vec
    from OCP.TopAbs import TopAbs_REVERSED

    if plane not in PATH_PLANES:
        raise ValidationError(
            "path_sketch",
            _(
                "Die Bahn muss senkrecht zum Querschnitt liegen — zeichnen Sie sie "
                "auf der Vorder- oder der Seitenansicht."
            ),
            value=plane,
            constraint="path_plane",
        )
    if not path.segments:
        raise ValidationError(
            "path_sketch", _("Diese Bahn hat keinen Verlauf."), constraint="no_path"
        )
    lift = PLANES[plane][0]
    begin = path.segments[0].start
    at_origin = shifted(Profile(segments=path.segments), -begin[0], -begin[1])
    spine = _wire(at_origin, lift)
    first = BRepTools_WireExplorer(spine).Current()
    curve = BRepAdaptor_Curve(first)
    start = (
        curve.LastParameter() if first.Orientation() == TopAbs_REVERSED else curve.FirstParameter()
    )
    tangent = gp_Vec()
    curve.D1(start, gp_Pnt(), tangent)
    # Die Sehne eines Bogens zeigt nicht in seine Anfangsrichtung. Geprüft
    # wird dieselbe exakte Kurve, die anschließend den Querschnitt führt.
    length = tangent.Magnitude()
    if length <= EPS_GEOM or math.hypot(tangent.X(), tangent.Y()) > EPS_GEOM * length:
        raise ValidationError(
            "path_sketch",
            _(
                "Der Bahnanfang muss senkrecht zum Querschnitt verlaufen. "
                "Zeichnen Sie ihn senkrecht nach oben oder unten."
            ),
            constraint="path_start",
        )
    # **``MakePipeShell`` und nicht ``MakePipe``**, und das ist der ganze
    # Unterschied zwischen einer Bahn und einem Bogen: An einer scharfen Ecke
    # hört ``MakePipe`` auf zu bauen. Gemessen an einer Bahn aus 40 mm hoch und
    # 30 mm quer: ein Körper von 3141 mm³ statt 5497 — also genau das erste
    # Segment, ohne ein Wort dazu. Der Übergangsmodus entscheidet, was an der
    # Ecke geschieht; ``RightCorner`` schneidet sie auf Gehrung, wie ein Rohr
    # oder ein Kanal es hat, und trifft damit die Länge der Bahn exakt.
    builder = BRepOffsetAPI_MakePipeShell(spine)
    builder.SetTransitionMode(BRepBuilderAPI_RightCorner)
    builder.Add(_wire(profile, _lift_xy), False, False)
    refusal = _("Entlang dieser Bahn lässt sich der Querschnitt nicht führen.")
    solid = _finished(builder, refusal)
    # ``MakePipeShell`` liefert eine Schale; erst ``MakeSolid`` schließt sie zu
    # einem Körper. Ohne das wäre das Ergebnis hohl und ohne Volumen — und der
    # Fehler zeigte sich erst beim Schneiden oder Exportieren.
    if not builder.MakeSolid():
        raise GeometryError(
            detail=_("Diese Bahn ergibt keinen geschlossenen Körper — prüfen Sie ihren Verlauf."),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    solid = solid.replacing(builder.Shape())
    # MakePipeShell nimmt einen Draht, keine Fläche mit Innenkonturen. Jedes
    # Loch folgt derselben Bahn und wird wie beim Loft vom Außenkörper abgezogen.
    for hole in profile.holes:
        solid = _fuzzy_boolean("difference", solid, sweep_path(hole, path, plane), refusal)
    return solid


def loft(
    bottom: Profile,
    top: Profile,
    height: float,
    plane: str = "plane:xy",
    frame: PlaneFrame | None = None,
    *,
    compatible: bool = True,
) -> Solid:
    """Spannt einen Körper zwischen zwei Umrissen auf — unten auf der Ebene.

    Ebene und Rahmen wie bei :func:`extrude`, und aus demselben Grund: Seit
    die Operation eine **gezeichnete** Skizze annimmt, kann diese auf XZ, auf
    YZ oder auf einer Fläche liegen. Ohne die beiden Argumente entstünde der
    Körper immer auf XY — bei einer Zeichnung auf der Vorderansicht also um
    neunzig Grad verdreht, und zwar stillschweigend.

    Der obere Umriss wird um ``height`` entlang der Ebenennormalen gehoben;
    auf XY ist das die Z-Achse und alles bleibt, wie es war.

    ``compatible`` lässt OpenCASCADE die Ecken der beiden Außenumrisse selbst
    einander zuordnen (``CheckCompatibility``) — die Vorgabe und der Weg des
    Erzeugers. Wer die Zuordnung schon entschieden hat, weil zwei gleich nahe
    zur Wahl standen und der Kunde gefragt wurde (``sketch_loft_cut``),
    schaltet sie ab: Sonst wählte der Kern bei Gleichstand still eine Seite,
    und welche, hinge an der letzten Stelle einer Summe.
    """
    require()
    from OCP.BRepOffsetAPI import BRepOffsetAPI_ThruSections
    from OCP.gp import gp_Pnt

    require_positive("height", height)
    if frame is not None:
        lift, normal = _lift_frame(frame), frame.normal
    elif plane in PLANES:
        lift, normal = PLANES[plane]
    else:
        raise ValidationError("plane", _("Diese Ebene gibt es nicht."), value=plane)

    def lifted(point: Point2) -> Any:
        low = lift(point)
        return gp_Pnt(
            low.X() + normal[0] * height,
            low.Y() + normal[1] * height,
            low.Z() + normal[2] * height,
        )

    builder = BRepOffsetAPI_ThruSections(True, False)
    builder.CheckCompatibility(compatible)
    builder.AddWire(_wire(bottom, lift))
    builder.AddWire(_wire(top, lifted))
    solid = _finished(builder, _("Zwischen diesen beiden Umrissen entsteht kein Körper."))
    # **Die Löcher reisen mit.** ``extrude``, ``revolve`` und ``sweep_arc``
    # setzen sie über ``_face`` als innere Ringe; ``ThruSections`` nimmt nur
    # Drähte — hier ging jedes gezeichnete Loch stillschweigend verloren
    # (Regel 21): Der Kunde bekam einen Körper ohne das Loch, das er
    # gezeichnet hat, und kein Wort dazu. Je Lochpaar ein eigener Durchzug,
    # abgezogen mit derselben Fuzzy-Toleranz wie bei den Nachbarn.
    if len(bottom.holes) != len(top.holes):
        raise ValidationError(
            "sketch",
            _(
                "Die beiden Umrisse tragen verschieden viele Löcher — so lässt "
                "sich kein Übergang aufspannen."
            ),
        )
    no_passage = _("Aus einem der gezeichneten Löcher entsteht kein Durchzug.")
    for below, above in zip(bottom.holes, top.holes, strict=True):
        drill = BRepOffsetAPI_ThruSections(True, False)
        drill.AddWire(_wire(below, lift))
        drill.AddWire(_wire(above, lifted))
        solid = _fuzzy_boolean("difference", solid, _finished(drill, no_passage), no_passage)
    return solid


def intersects_itself(solid: Solid) -> bool:
    """Ob ein Werkzeugkörper sich selbst durchdringt (P6.5b/c).

    **Die Gültigkeitsprüfung des Kerns sieht das nicht.** Ein Kreis Ø4 um
    einen Bogen R1 geführt ergibt einen Körper, den ``BRepCheck_Analyzer``
    für gültig hält — seine Flächen sind je für sich in Ordnung, sie treffen
    sich nur gegenseitig. Erst ``BRepAlgoAPI_Check`` mit der Prüfung auf
    Selbstschnitt findet es; gemessen an drei Bahnen (enger Bogen, zu nahe
    Rückführung, gekreuzte Bahn) schlug sie an allen dreien an und an der
    geraden Gegenprobe nicht. Ein solches Werkzeug schnitte trotzdem — nur
    nicht das, was gezeichnet ist.
    """
    require()
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Check

    return not BRepAlgoAPI_Check(solid.shape, True, True).IsValid()


def is_sound(solid: Solid) -> bool:
    """Ob ein Ergebnis des exakten Kerns ein gültiger Körper ist (P6.5).

    **Eine Boolesche Operation kann ungültig gelingen.** Gemessen an einer
    eingelesenen STEP-Klammer aus zwei Teilen (``carpet-corner-clip.step``):
    Eine Ringnut in ihrer Bohrung meldete ``IsDone``, das Volumen sank um genau
    das Werkzeug — und der Körper war ungültig; der Klassierer fand die Luft der
    Bohrung danach innen und das weggenommene Material noch da. Wer ein exaktes
    Ergebnis ausliefert, fragt deshalb die Gültigkeit und nicht das Volumen.
    """
    require()
    from OCP.BRepCheck import BRepCheck_Analyzer

    return solid.solid_count >= 1 and bool(BRepCheck_Analyzer(solid.shape).IsValid())


def shell_open_top(
    solid: Solid, thickness: float, *, cancelled: CancelToken | None = None
) -> Solid:
    """Höhlt den Körper exakt aus und lässt die Oberseite offen.

    Entfernt werden alle ebenen Flächen, die nach oben zeigen und auf der
    höchsten Ebene des Körpers liegen — bei einem Kasten der Deckel."""
    require()
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.collections import List_TopoDS_Shape

    require_positive("wall", thickness)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    working = replace(solid)
    tops = _top_faces(working, cancelled=cancelled)
    if not tops:
        raise GeometryError(
            detail=_("Dieser Körper hat keine ebene Oberseite, die sich öffnen ließe."),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    removed = List_TopoDS_Shape()
    for face in tops:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        removed.Append(face)
    builder = BRepOffsetAPI_MakeThickSolid()
    builder.MakeThickSolidByJoin(working.shape, removed, -thickness, EPS_GEOM)
    return _finished(
        builder,
        _("Für diese Wandstärke ist im Körper kein Platz."),
        working,
        cancelled=cancelled,
    )


def top_faces_of(solid: Solid, *, cancelled: CancelToken | None = None) -> tuple[int, ...]:
    """Die Indizes der Flächen, die *Oben öffnen* meint — dieselbe Frage wie
    :func:`shell_open_top`, als Zahlen für :func:`shell_open_at`."""
    require()
    return tuple(solid.face_index(face) for face in _top_faces(solid, cancelled=cancelled))


def shell_open_at(
    solid: Solid,
    thickness: float,
    faces: Sequence[int],
    *,
    outward: bool = False,
    cancelled: CancelToken | None = None,
) -> Solid | None:
    """Höhlt exakt aus und lässt genau die gewählten Flächen offen (P6.3).

    ``faces`` zählt die nativen Flächen aus :meth:`Solid.faces`. Nach innen
    bleibt die Außenhaut, wo sie war; nach außen (``outward``) wird der Körper
    selbst zum Hohlraum, und die Wand legt sich um ihn — die offenen Flächen
    bleiben dabei bündig, der Rand der Öffnung liegt in ihrer Ebene. Die
    Stöße nach außen sind rund (``GeomAbs_Arc``, die Vorgabe von OpenCASCADE):
    Dieselbe Form entsteht am Netz, wo die Wand mit einer Kugel wächst.

    **``None`` statt einer Ausnahme, und aus gemessenem Grund.** OpenCASCADE
    scheitert hier auf drei Arten, und keine davon wirft (Sonde vom
    23.09.2026, Bericht P6.3): Bei zu großer Wand kommt der Eingang
    unverändert zurück, an einem konkaven Körper ebenso, an einer dünnen
    Platte ist das Ergebnis leer, und ein geschlossener Winkel wird eine
    Schale statt eines Körpers. Welcher Satz dem Kunden gilt — zu dicke Wand
    oder sich schneidende Innenwände —, entscheidet der Aufrufer, der dafür das
    Raster fragen kann; hier steht nur, dass kein brauchbarer Körper entstand.
    Ein Ergebnis, das kein gültiger, geschlossener und veränderter Körper ist,
    geht nie hinaus.
    """
    require()
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid
    from OCP.collections import List_TopoDS_Shape
    from OCP.TopAbs import TopAbs_SOLID

    require_positive("wall", thickness)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    working = replace(solid)
    chosen = working.checked_face_indices(faces, cancelled=cancelled)
    native = working.faces()
    removed = List_TopoDS_Shape()
    for index in chosen:
        removed.Append(native[index])
    builder = BRepOffsetAPI_MakeThickSolid()
    offset = thickness if outward else -thickness
    try:
        builder.MakeThickSolidByJoin(working.shape, removed, offset, EPS_GEOM)
        builder.Build()
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if not builder.IsDone():
            return None
        shape = builder.Shape()
    except OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # OpenCASCADE wirft eigene Ausnahmearten
        _log.info("thick solid failed: %s", problem)
        return None
    if shape.IsNull() or shape.ShapeType() != TopAbs_SOLID:
        return None
    if not BRepCheck_Analyzer(shape).IsValid():
        return None
    result = working.replacing(shape, history=builder, cancelled=cancelled)
    try:
        unchanged = is_close(result.volume, working.volume)
    except GeometryError:
        # Ein Ergebnis, dessen Volumen sich nicht bestimmen lässt, ist keines —
        # gemessen an ``Cat_1.stp`` von unten geöffnet (Sonde 23.09.2026).
        return None
    if not result.is_closed or unchanged:
        return None
    return result


def draft_faces(
    solid: Solid,
    angle_deg: float,
    *,
    direction: tuple[float, float, float] = (0.0, 0.0, 1.0),
    neutral: float | None = None,
    selected_faces: Sequence[int] | None = None,
    cancelled: CancelToken | None = None,
) -> tuple[Solid, int]:
    """Stellt Flächen um den Winkel an — gewählte oder alle in Entformungsrichtung (P6.4).

    Zurück kommen der Körper und die Zahl der Flächen, die als **notwendiger
    Übergang** dazukamen (:func:`_tangent_chain`): Eine gerundete Ecke, die
    tangential an eine angestellte Wand anschließt, muss mit, sonst gibt es
    zwischen beiden keine Kante — OpenCASCADE sagte dann ab (``build_tray_v3.step``,
    119 senkrechte Flächen, gerundete Ecken).

    ``direction`` ist die Entformungsrichtung, in die hinein der Körper
    schmaler wird; ``neutral`` die Lage der neutralen Ebene entlang dieser
    Richtung, ohne Angabe der Anfang des Körpers. ``selected_faces`` sind
    Indizes in :meth:`Solid.faces`; ohne sie gilt jede ebene Fläche, die in
    Entformungsrichtung steht. ``BRepOffsetAPI_DraftAngle`` verlängert und
    beschneidet die Nachbarflächen selbst — derselbe Vertrag wie am Netz
    (``geom.faces.draft_walls``).

    **Gebaut heißt nicht heil.** Laufen zwei angestellte Flächen durch
    dieselbe Wand, liefert der Kern einen Körper, den ``BRepCheck_Analyzer``
    ablehnt — am Gehäuse mit 3 mm Wand bei 5° über 20 mm Höhe eine Deckfläche,
    deren Innenrand in der Tessellierung fehlte (Netzvolumen 12 569 statt
    5 694 mm³). ``ShapeFix_Shape`` macht ihn formal gültig, zählt die fehlende
    Wand aber negativ; repariert wird deshalb nicht, sondern abgesagt, mit dem
    Satz, den auch das Netz sagt.
    """
    require()
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepOffsetAPI import BRepOffsetAPI_DraftAngle
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pln, gp_Pnt

    from app.core.geom.faces import (
        DRAFT_BESIDE_A_FREE_FACE,
        DRAFT_BESIDE_A_ROUND,
        DRAFT_CUTS_THROUGH,
        UPRIGHT_ENOUGH,
        _across_the_pull,
    )

    if not 0.0 < angle_deg <= 30.0:
        raise ValidationError(
            "angle", _("Der Winkel muss zwischen null und 30 Grad liegen."), value=angle_deg
        )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    pull = (float(direction[0]), float(direction[1]), float(direction[2]))
    working = replace(solid)
    # Die ebenen Flächen mit ihrer nach außen zeigenden Normale, unter ihrem
    # Index in ``faces()`` — gewölbte fehlen, eine Auswahl davon ist eine Absage.
    planes: dict[int, tuple[float, float, float]] = {}
    for index in range(len(working.faces())):
        surface = working.surface(index, cancelled=cancelled)
        if isinstance(surface, PlaneSurface):
            planes[index] = surface.normal
    if selected_faces is None:
        chosen = [
            index
            for index, normal in planes.items()
            if abs(sum(a * b for a, b in zip(normal, pull, strict=True))) < UPRIGHT_ENOUGH
        ]
        if not chosen:
            raise GeometryError(
                detail=_(
                    "Dieser Körper hat keine Flächen, die in Entformungsrichtung stehen. "
                    "Wählen Sie eine andere Richtung oder einzelne Flächen."
                ),
                suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
            )
    else:
        chosen = list(selected_faces)
        for index in chosen:
            normal = planes.get(index)
            if normal is None:
                raise GeometryError(
                    detail=_(
                        "Angestellt werden ebene Flächen. Wählen Sie eine ebene Seitenwand, "
                        "oder lassen Sie die Auswahl leer für alle Wände."
                    ),
                    suggestions=(CHANGE_SELECTION, CANCEL),
                )
            if abs(sum(a * b for a, b in zip(normal, pull, strict=True))) > UPRIGHT_ENOUGH:
                raise _across_the_pull()
    grown, beside = _tangent_chain(working, chosen, pull, cancelled)
    if beside is not None:
        # Vor der Rechnung, wie am Netz: ``Draft_FaceRecomputation`` rechnet
        # die Rundung neben der gekippten Wand nicht nach (RM-230), und eine
        # stehende freie Fläche bliebe still senkrecht.
        raise GeometryError(
            detail=DRAFT_BESIDE_A_ROUND if beside == "round" else DRAFT_BESIDE_A_FREE_FACE,
            suggestions=(CHANGE_SELECTION, CANCEL),
            values={"angle_deg": round(angle_deg, 2)},
        )
    added = len(grown) - len(set(chosen))
    chosen = grown
    axis = next(number for number, value in enumerate(pull) if abs(value) > 0.5)
    sign = 1.0 if pull[axis] > 0.0 else -1.0
    start = solid.bounds.minimum[axis] if sign > 0.0 else -solid.bounds.maximum[axis]
    level = start if neutral is None else neutral
    origin = tuple(level * value for value in pull)
    plane = gp_Pln(gp_Ax3(gp_Pnt(*origin), gp_Dir(*pull)))
    builder = BRepOffsetAPI_DraftAngle(working.shape)
    refusal = _(
        "Die Formschräge lässt sich an diesen Flächen nicht anlegen. Stellen Sie "
        "einen kleineren Winkel ein, oder wählen Sie weniger Flächen."
    )

    faces = working.faces()
    for index in chosen:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        # **``Add`` rechnet schon**, nicht erst ``Build``: An einer
        # B-Spline-Wand wirft es ``Standard_ConstructionError``, und außerhalb
        # der Übersetzung kam das als „unerwarteter Fehler" mit der Bitte um
        # einen Fehlerbericht an (22.09.2026, NURBS-Platte aus STEP).
        try:
            builder.Add(faces[index], gp_Dir(*pull), math.radians(angle_deg), plane)
            done = builder.AddDone()
        except PROGRAMMING_ERRORS:
            raise
        except Exception as problem:  # OpenCASCADE wirft eigene Ausnahmearten
            raise GeometryError(
                detail=refusal, suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL)
            ) from problem
        if not done:
            raise GeometryError(
                detail=refusal, suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL)
            )
    result = _finished(builder, refusal, working, cancelled=cancelled)
    if (
        not BRepCheck_Analyzer(result.shape).IsValid()
        or not result.is_closed
        or result.solid_count != solid.solid_count
        or result.volume <= EPS_GEOM
    ):
        raise GeometryError(
            detail=DRAFT_CUTS_THROUGH,
            suggestions=(CORRECT_INPUT, CHANGE_SELECTION, CANCEL),
            values={"angle_deg": round(angle_deg, 2)},
        )
    return result, added


def _tangent_chain(
    solid: Solid,
    chosen: Sequence[int],
    pull: tuple[float, float, float],
    cancelled: CancelToken | None,
) -> tuple[list[int], Literal["round", "upright"] | None]:
    """Die gewählten Flächen und alles, was tangential an sie anschließt und mitkann.

    Mit kann eine ebene Fläche, die in Entformungsrichtung steht, und ein
    Zylinder, dessen Achse in ihr liegt — die gerundete senkrechte Ecke.
    Tangential heißt: An der Mitte der gemeinsamen Kante zeigen beide
    Flächen um höchstens :data:`~app.core.units.SAME_PLANE_AT_A_CORNER` in
    verschiedene Richtungen (dieselbe Grenze, mit der das Netz die Ebenen an
    einer Ecke zählt). Eine Bohrung, die an keine angestellte Wand anschließt,
    bleibt stehen — wie seit je.

    ``BRepOffsetAPI_DraftAngle.Add`` nimmt tangentiale Flächen mit seiner
    Vorgabe (``Flag=True``) ohnehin mit; gezählt wird hier, damit der Befund
    dieselbe Menge nennt wie am Netz und eine Absage vorher fällt, wo eine
    tangentiale Fläche nicht mitkann.

    Zurück kommt auch, ob tangential eine Fläche anschließt, die **nicht**
    mitkann (RM-230): ``"round"``, wenn sie irgendwo schräg zur
    Entformungsrichtung liegt — eine liegende Verrundung am Fuß oder oben, die
    ``Draft_FaceRecomputation`` neben der gekippten Wand nicht nachrechnet;
    gefragt an einem Raster von neun Punkten, denn eine Vollrundung aus einer
    Fläche liegt in ihrer Mitte waagerecht. ``"upright"``, wenn sie steht —
    eine frei geformte Ecke oder ein fast stehender Zylinder: ``Add`` ließ sie
    still senkrecht, und die gekippten Wände schnitten sich in sie ein. Eine
    Fase oder eine Querbohrung schließt mit Knick an. Am Netz fragt
    ``faces._round_beside_the_walls`` nach der Rundung.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as NeighbourMap,
    )
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from app.core.brep.canonical import CylinderSurface, outward_normal
    from app.core.geom.faces import UPRIGHT_ENOUGH, leans_across
    from app.core.units import SAME_PLANE_AT_A_CORNER, is_close

    faces = solid.faces()
    known = ShapeMap()
    TopExp.MapShapes_s(solid.shape, TopAbs_FACE, known)
    neighbours = NeighbourMap()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, neighbours)

    def draftable(index: int) -> bool:
        surface = solid.surface(index, cancelled=cancelled)
        if isinstance(surface, PlaneSurface):
            return (
                abs(sum(a * b for a, b in zip(surface.normal, pull, strict=True))) < UPRIGHT_ENOUGH
            )
        if isinstance(surface, CylinderSurface):
            axis = surface.cylinder.Axis().Direction()
            along = abs(axis.X() * pull[0] + axis.Y() * pull[1] + axis.Z() * pull[2])
            return is_close(along, 1.0)
        return False

    leaning: dict[int, bool] = {}

    def leans(index: int) -> bool:
        if index not in leaning:
            face = TopoDS.Face(faces[index])
            low_u, high_u, low_v, high_v = BRepTools.UVBounds_s(face)
            adaptor = BRepAdaptor_Surface(face)
            found = False
            for share_u in (0.25, 0.5, 0.75):
                for share_v in (0.25, 0.5, 0.75):
                    spot = adaptor.Value(
                        low_u + share_u * (high_u - low_u), low_v + share_v * (high_v - low_v)
                    )
                    normal = outward_normal(face, (spot.X(), spot.Y(), spot.Z()))
                    found = found or (normal is not None and leans_across(normal, pull))
            leaning[index] = found
        return leaning[index]

    grown = list(dict.fromkeys(chosen))
    seen = set(grown)
    queue = list(grown)
    beside: Literal["round", "upright"] | None = None
    while queue:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        current = queue.pop()
        explorer = TopExp_Explorer(faces[current], TopAbs_EDGE)
        while explorer.More():
            edge = explorer.Current()
            explorer.Next()
            if not neighbours.Contains(edge):
                continue
            curve = BRepAdaptor_Curve(TopoDS.Edge(edge))
            middle = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2.0)
            point = (middle.X(), middle.Y(), middle.Z())
            for shape in neighbours.FindFromKey(edge):
                other = int(known.FindIndex(shape)) - 1
                if other < 0 or other in seen:
                    continue
                one = outward_normal(faces[current], point)
                two = outward_normal(faces[other], point)
                if one is None or two is None:
                    continue
                if 1.0 - sum(a * b for a, b in zip(one, two, strict=True)) > SAME_PLANE_AT_A_CORNER:
                    continue
                if not draftable(other):
                    if leans(other):
                        beside = "round"
                    elif beside is None:
                        beside = "upright"
                    continue
                seen.add(other)
                grown.append(other)
                queue.append(other)
    return grown, beside


#: Gewindetiefe je Steigung: 5H/8 des scharfen Dreiecksprofils (metrisches ISO).
_THREAD_DEPTH_SHARE: Final = 0.6134

#: Halbe Fußbreite des Gewindegangs je Steigung — schmaler als der halbe Gang,
#: damit zwischen zwei Umläufen Grund bleibt.
_THREAD_FOOT_SHARE: Final = 0.375

#: Wie viel vom Außendurchmesser der Kern mindestens behalten muss — dieselbe
#: Regel wie für jedes Bausteingewinde (``units.THREAD_MIN_CORE_SHARE``, dort
#: der Anlass: M2 mit 1,5 mm Steigung ergab einen Faden von 0,16 mm).
_THREAD_MIN_CORE_SHARE: Final = THREAD_MIN_CORE_SHARE


#: Wie genau die 3D-Kurve einer Helix ihre Linie auf dem Zylinder trifft — eine
#: Helix ist keine NURBS, OCCT nähert sie als BSpline. Die Vorgabe (10⁻⁵ mm)
#: verschob die Flanken um Mikrometer: Volumen gegen Pappus 2·10⁻⁷, die Hülle
#: eines M10-Bolzens 3 µm neben der Achse. Ein Hundertstel von ``EPS_GEOM``
#: hält beides unter 10⁻⁹ und kostet keine messbare Bauzeit (21.09.2026).
_HELIX_PRECISION: Final = EPS_GEOM / 100.0

#: Wie tief der Fuß des Gangs unter dem Kernradius sitzt, in Millimetern —
#: die Sockelbreite des früheren Sweeps. Sie bestimmt zusammen mit der
#: Fußbreite den Flankenwinkel: Die Flanke lief vom Fuß bei ``core - 0.1`` zur
#: Spitze, und was der Bolzen davon zeigt, beginnt am Kernradius. Der genähte
#: Körper baut genau dieses Profil, damit kein Maß sich ändert (RM-195).
_THREAD_FOOT_SEAT: Final = 0.1


def thread_ridge(major: float, pitch: float) -> tuple[Point2, ...]:
    """Das sichtbare Gangprofil eines Umlaufs, vom Kernradius aus (radial, axial).

    Das ISO-nahe Profil des Erzeugers *Gewindebolzen*: Kamm bei ``major / 2``,
    Kern um ``_THREAD_DEPTH_SHARE`` mal Steigung darunter, die Flanken so
    steil, wie der Sweep sie mit seinem Fuß ``_THREAD_FOOT_SEAT`` unter dem
    Kern und der halben Fußbreite ``_THREAD_FOOT_SHARE`` mal Steigung zog.
    Über dem Kern bleibt davon ein Dreieck: Fuß, Spitze, Fuß.
    """
    ridge = _THREAD_DEPTH_SHARE * pitch
    core_radius = major / 2.0 - ridge
    half = pitch * _THREAD_FOOT_SHARE
    at_core = half * ridge / (ridge + _THREAD_FOOT_SEAT)
    return (
        (core_radius, 0.0),
        (core_radius + ridge, at_core),
        (core_radius, 2.0 * at_core),
    )


def threaded_rod(
    major: float, pitch: float, length: float, *, cancelled: CancelToken | None = None
) -> Solid:
    """Ein Bolzen mit exaktem Außengewinde: Kern und Gang als **ein** genähter Körper.

    Kein Sweep, keine Vereinigung mehr (RM-195): :func:`helical_thread` näht
    Flanken, Kamm und Fußstreifen aus Regelflächen zwischen geteilten
    Helixkanten, mit einem Umlauf Vorlauf unter dem Bett und einem über der
    Länge, und der Schnitt auf Länge ist ein Quader, dessen Boden und Deckel
    als Ebenen die BSpline-Flächen treffen — der Schnitt, den der Kern
    zuverlässig kann. Das Profil
    ist dasselbe wie beim Sweep (:func:`thread_ridge`); die Flanken sind exakt
    die Regelflächen der Schraubbewegung, wo der Sweep sie als Spline neunten
    Grades genähert hatte. Gemessen (21.09.2026): M6 x 1, L 12 in 0,2 s statt
    15 s, M10 x 1,5, L 12 in 0,25 s statt 27 s — davon steckten 25 s in den
    Volumenintegralen der Prüfstufen und keine in der Vereinigung, die der
    Registereintrag RM-195 dafür hielt.

    Die Absage bei zu großer Steigung, zu kurzer Länge und einem Bolzen, der
    doch nicht geschlossen ist, bleibt (:func:`_checked_rod`). Ein langer
    Bolzen hat Hunderte Flächen; ``cancelled`` wird je Umlauf, vor und nach
    jedem nativen Schritt gefragt.
    """
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    from app.core.brep import edit

    ridge = _THREAD_DEPTH_SHARE * pitch
    core_radius = major / 2.0 - ridge
    if core_radius <= major / 2.0 * _THREAD_MIN_CORE_SHARE:
        raise ValidationError(
            "pitch",
            _("Die Steigung ist für diesen Durchmesser zu groß — es bliebe kaum ein Kern."),
            value=pitch,
            constraint="no_core",
            values={"core": round(core_radius * 2.0, 3), "major": major},
        )
    if length <= 2.0 * pitch:
        raise ValidationError(
            "length",
            _("Ein Gewinde braucht mindestens zwei Gänge Länge."),
            value=length,
            constraint="too_short",
        )

    turns = math.ceil(length / pitch) + 2
    profile = thread_ridge(major, pitch)
    whole = helical_thread(core_radius, pitch, turns, profile, start=-pitch, cancelled=cancelled)
    # **Auf Länge mit einem Quader, nicht mit einem Zylinder.** Der Mantel
    # eines Schnittzylinders umhüllt jede Gangfläche, und die Boolesche prüfte
    # jede davon gegen ihn: 1,4 s am M3 x 0,5 x 60. Die Seiten eines Quaders
    # liegen neben dem Gewinde, nur Boden und Deckel treffen Flächen, und
    # schneiden tun sie dasselbe (0,74 s, gleiche Flächen, gleiches Volumen;
    # gemessen 22.09.2026).
    reach = major + 2.0
    slab = Solid(
        BRepPrimAPI_MakeBox(gp_Pnt(-reach / 2.0, -reach / 2.0, 0.0), reach, reach, length).Shape()
    )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    rod = edit.boolean("intersection", [whole, slab])
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # **Ein Bolzen ohne Gang ist keiner** (B3, P2.5): Über dem Kern muss der
    # Gang liegen — mindestens die Hälfte seines Volumens nach Pappus, damit
    # das grobe Volumen der Prüfung (10⁻⁷) die Frage sicher entscheidet.
    core = math.pi * core_radius**2 * length
    rod = _checked_rod(
        rod, major, pitch, at_least=core + 0.5 * _ridge_volume(profile, pitch, length)
    )

    # **Die Vernetzung folgt der Steigung.** Die Standardfeinheit (0,05 mm)
    # ist für einen Gewindegang von einem Viertelmillimeter zu grob: Der Körper
    # kommt geschlossen heraus, sein Netz aber mit Ritzen an der Flanke — und
    # damit wäre der STL-Export löchrig, während STEP stimmt. Gemessen an M10
    # mit 0,25 mm Steigung, und auf dem macOS-Runner an M6 mit einem
    # Millimeter, wo dieselbe Standardfeinheit anders rundet.
    #
    # Ein Zwanzigstel der Steigung ist die Grenze, unterhalb derer die Flanke
    # in Dreiecken aufgeht; feiner als nötig wird nicht vernetzt, denn jede
    # Halbierung vervierfacht die Dreiecke.
    return _finely_meshed(rod, min(DEFLECTION, pitch / 20.0))


def _ridge_volume(ridge: Sequence[Point2], pitch: float, length: float) -> float:
    """Das Volumen des Gangs über dem Kern: Pappus je Umlauf, Umläufe je Länge.

    Das Profil in (radial, axial) schließt am Fuß; Fläche und radialer
    Schwerpunkt über die Schuhbandformel, derselbe Weg wie im Test, der die
    Analytik gegen den Körper hält.
    """
    corners = [*ridge, ridge[0]]
    area = 0.0
    moment = 0.0
    for (r_a, z_a), (r_b, z_b) in pairwise(corners):
        cross = r_a * z_b - r_b * z_a
        area += cross
        moment += (r_a + r_b) * cross
    return 2.0 * math.pi * abs(moment) / 6.0 * (length / pitch)


def helical_thread(
    root_radius: float,
    pitch: float,
    turns: int,
    ridge: Sequence[Point2],
    *,
    start: float,
    starts: int = 1,
    taper: float = 0.0,
    cancelled: CancelToken | None = None,
) -> Solid:
    """Kern und Gang eines Gewindes als **ein** genähter Körper — ohne Boolesche Operation.

    Die Vereinigung eines gesweepten Gangs mit dem Kernzylinder ist der
    unzuverlässigste Schritt dieses Kerns: Ohne Fuzzy-Toleranz verschluckt sie
    den Gang still (Bericht P2.7, B1), und welche Toleranz ihn rettet, wechselt
    von Größe zu Größe — gemessen am 21.09.2026 über sechs Gewinde und drei
    Längen: M3 x 0,5 brauchte bei Länge 6 die Stufe 1e-2, bei Länge 8 die Stufe
    1e-3 und bei Länge 12 die Stufe 3e-3, jede Stufe 7 bis 24 Sekunden. Hier
    wird deshalb nichts vereinigt. Jede Fläche entsteht aus den Helixkanten,
    die sie mit ihren Nachbarn teilt: Die Flanken und der Kamm sind
    Regelflächen zwischen zwei Helices (``BRepFill.Face``), der Fuß zwischen
    den Umläufen ebenso, und die Enden schließen zwei Rampen von der Achse zur
    Fußhelix mit je einer ebenen Fläche bei Winkel null. Nähen macht daraus
    einen Körper: gültig, geschlossen, in dreißig Millisekunden, mit dem
    Volumen der Analytik auf 5·10⁻¹⁰ (die Helix ist eine BSpline-Näherung mit
    ``_HELIX_PRECISION``; mit OCCTs Vorgabe von 10⁻⁵ waren es 2·10⁻⁷, und die
    Hülle eines M10-Bolzens saß 3 µm neben der Achse).

    ``ridge`` ist das Gangprofil **eines** Gangs in der Ebene (radial,
    axial), vom Fuß ``(root_radius, 0)`` bis zum letzten Gangpunkt
    ``(root_radius, dz)`` mit ``dz < pitch``; den Fußstreifen bis zum nächsten
    Gang ergänzt die Funktion. Die Helix beginnt bei Winkel null auf der Höhe
    ``start`` und läuft ``turns`` Umläufe. Beide Rampen liegen unter
    ``start + lead`` und über ``start + turns * lead`` — wer den Körper mit
    einem Umlauf Vorlauf baut und danach auf Länge schneidet, schneidet sie
    weg. Ein Innengewinde-Werkzeug ist dieselbe Form: Fuß an der Bohrung, Gang
    nach außen.

    ``starts`` Gänge teilen sich einen Umlauf: Der Vorschub ist
    ``starts * pitch``, und jeder Gang sitzt um eine Teilung über dem vorigen
    — dieselben Flächenarten, nur mehr davon je Umlauf. ``taper`` ist der
    halbe Kegelwinkel im Bogenmaß (ein kegeliges Rohrgewinde): Jeder
    Profilpunkt läuft dann auf einem Kegel statt einem Zylinder, sein Radius
    wächst je Millimeter Höhe um ``tan(taper)``, und die Radien in ``ridge``
    gelten auf der Höhe ``start``. Die Regelflächen zwischen zwei Helices
    derselben Steigung verbinden Punkte gleichen Winkels; auf einem Kegel
    liegen beide auf derselben Mantellinie, der Fußstreifen bleibt also
    Kegelmantel.
    """
    require()
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeSolid,
        BRepBuilderAPI_MakeWire,
        BRepBuilderAPI_Sewing,
    )
    from OCP.BRepFill import BRepFill
    from OCP.BRepLib import BRepLib
    from OCP.Geom import Geom_ConicalSurface, Geom_CylindricalSurface
    from OCP.Geom2d import Geom2d_Line
    from OCP.gp import gp_Ax2d, gp_Ax3, gp_Dir, gp_Dir2d, gp_Pnt, gp_Pnt2d
    from OCP.TopoDS import TopoDS

    def check() -> None:
        if cancelled is not None:
            cancelled.raise_if_cancelled()

    check()
    if turns < 1 or len(ridge) < 2 or starts < 1:
        raise InternalError(detail="a helical thread needs a ridge, a start and at least one turn")
    if not (
        is_close(ridge[0][0], root_radius)
        and is_zero(ridge[0][1])
        and is_close(ridge[-1][0], root_radius)
        and ridge[-1][1] < pitch
    ):
        raise InternalError(detail="the ridge must start and end on the root radius")
    if not (math.isfinite(taper) and 0.0 <= taper < math.pi / 4.0):
        raise InternalError(detail="the half angle of a tapered thread must lie below 45 degrees")
    lead = starts * pitch
    slope = math.tan(taper)
    # Eine Trägerfläche je Profilpunkt — nach seinem Index, nicht nach dem
    # Radius: Ein Fließkommawert taugt nicht als Schlüssel (Regel 6). Ohne
    # Kegel ist der Parameter längs der Fläche die Höhe, mit Kegel die
    # Mantellinie ab der Höhe ``start``.
    stretch = 1.0 / math.cos(taper)
    surfaces: list[Any]
    if taper > 0.0:
        frame = gp_Ax3(gp_Pnt(0.0, 0.0, start), gp_Dir(0.0, 0.0, 1.0))
        surfaces = [Geom_ConicalSurface(frame, taper, radial) for radial, _axial in ridge]
    else:
        surfaces = [Geom_CylindricalSurface(gp_Ax3(), radial) for radial, _axial in ridge]

    def along(height: float) -> float:
        """Wo die Höhe ``height`` auf der Trägerfläche liegt."""
        return (height - start) * stretch if taper > 0.0 else height

    def radius(radial: float, height: float) -> float:
        """Der Radius eines Profilpunkts auf der Höhe ``height``."""
        return radial + (height - start) * slope

    rise = lead * stretch if taper > 0.0 else lead

    def helix(point: int, origin: float) -> Any:
        """Ein Umlauf auf der Fläche des Profilpunkts, ab Winkel null auf Höhe ``origin``."""
        check()
        line = Geom2d_Line(gp_Ax2d(gp_Pnt2d(0.0, along(origin)), gp_Dir2d(2.0 * math.pi, rise)))
        edge = BRepBuilderAPI_MakeEdge(
            line, surfaces[point], 0.0, math.hypot(2.0 * math.pi, rise)
        ).Edge()
        BRepLib.BuildCurves3d_s(edge, _HELIX_PRECISION)
        return edge

    def segment(one: Vec3, other: Vec3) -> Any:
        return BRepBuilderAPI_MakeEdge(gp_Pnt(*one), gp_Pnt(*other)).Edge()

    faces: list[Any] = []
    # Die Fußhelix je Umlaufanfang — eine mehr als Umläufe, die letzte trägt die obere Rampe.
    feet = [helix(0, start + turn * lead) for turn in range(turns + 1)]
    for turn in range(turns):
        level = start + turn * lead
        # Je Gang sein Profil, eine Teilung über dem vorigen; der Fuß des
        # ersten ist die Fußhelix dieses Umlaufs, die des nächsten Umlaufs
        # schließt die Reihe.
        row = [feet[turn]]
        for course in range(starts):
            row.extend(
                helix(point, level + course * pitch + axial)
                for point, (_radial, axial) in enumerate(ridge)
                if point or course
            )
        for index in range(len(row) - 1):
            faces.append(BRepFill.Face_s(row[index], row[index + 1]))
        faces.append(BRepFill.Face_s(row[-1], feet[turn + 1]))

    def close_end(level: float, foot: Any) -> None:
        """Die Rampe von der Achse zur Fußhelix und die ebene Fläche bei Winkel null."""
        check()
        axis = segment((0.0, 0.0, level), (0.0, 0.0, level + lead))
        faces.append(BRepFill.Face_s(axis, foot))
        corners: list[Vec3] = [(0.0, 0.0, level)]
        for course in range(starts):
            corners.extend(
                (radius(radial, level + course * pitch + dz), 0.0, level + course * pitch + dz)
                for radial, dz in ridge
            )
        top = level + lead
        corners.extend([(radius(root_radius, top), 0.0, top), (0.0, 0.0, top)])
        outline = BRepBuilderAPI_MakeWire()
        for one, other in pairwise(corners):
            outline.Add(segment(one, other))
        outline.Add(axis)
        faces.append(BRepBuilderAPI_MakeFace(outline.Wire(), True).Face())

    close_end(start, feet[0])
    close_end(start + turns * lead, feet[turns])

    check()
    sewing = BRepBuilderAPI_Sewing(EPS_GEOM)
    for face in faces:
        sewing.Add(face)
    sewing.Perform()
    check()
    if sewing.NbFreeEdges() or sewing.NbMultipleEdges():
        raise GeometryError(
            detail=_("Aus dieser Steigung entsteht kein Gewindegang."),
            values={"pitch": pitch, "root": 2.0 * root_radius},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    solid = BRepBuilderAPI_MakeSolid(TopoDS.Shell(sewing.SewedShape())).Solid()
    BRepLib.OrientClosedSolid_s(solid)
    return Solid(solid)


def _finely_meshed(rod: Solid, fineness: float) -> Solid:
    """Vernetzt den Bolzen so fein, dass sein Netz dicht ist.

    **Gefragt wird das Netz, nicht eine Formel.** Ein Zwanzigstel der Steigung
    reicht meistens; bei einem Millimeter Steigung ist das genau die
    Standardfeinheit, und auf dem macOS-Runner riss die Flanke dort trotzdem
    auf — dieselbe Rechnung, andere Übersetzung. Eine festere Zahl wäre
    geraten: zu grob für die eine Plattform oder zu fein für alle anderen, und
    jede Halbierung vervierfacht die Dreiecke.

    Also wird nachgesehen und höchstens zweimal halbiert. Der Körper selbst
    ist zu diesem Zeitpunkt längst geprüft (:func:`_is_sound_rod` fragt die
    Topologie); hier geht es allein um die Dreiecke, aus denen STL und
    Schichtanalyse entstehen.

    **Es ist der zweite von zwei Griffen, nicht der einzige.** Seit dem
    27.08.2026 vernäht die Tessellierung selbst, was sich vernähen lässt
    (``kernel._stitched``): Ein Riss an der Flanke ist meist eine T-Kreuzung,
    und dagegen hilft kein feineres Netz. Was hier ankommt, ist also bereits
    vernäht — halbiert wird nur noch, wenn auch das nicht gereicht hat. Wer
    eine der beiden Stellen ändert, sollte die andere kennen: Sie verfolgen
    dasselbe Ziel mit verschiedenen Mitteln. Bleibt das Netz auch dann offen, kommt der
    Bolzen trotzdem heraus — er trägt STEP und jede weitere Operation, und ein
    Befund über ein grobes Netz ist besser als eine Absage über einen
    gelungenen Körper.
    """
    for _attempt in range(3):
        meshed = replace(rod, deflection=fineness)
        if meshed.is_watertight:
            return meshed
        fineness /= 2.0
        _log.info("thread rod: mesh had gaps, refining to %.4f mm", fineness)
    return replace(rod, deflection=fineness)


def _checked_rod(solid: Solid, major: float, pitch: float, *, at_least: float = 0.0) -> Solid:
    """Nachsehen, was der Schnitt auf Länge wirklich ergeben hat.

    Der Gewindebolzen entsteht genäht (:func:`helical_thread`) und wird danach
    mit einem Quader auf Länge geschnitten. Was dabei den Gang verliert,
    offen bleibt oder zerfällt, ist kein Ergebnis, das man jemandem in die
    Hand gibt: Ein offener exakter Körper trägt weder den STEP-Export noch
    eine weitere Operation. Bis RM-195 vereinigte der Bolzen einen Sweep mit
    dem Kern, und der verlor den Gang an neun von 23 Rasterlängen still.

    **Vor der Absage steht eine Rettungsstufe** (§17.2 dem Geist nach): Was
    rechnerisch zusammengehört, schließt ``ShapeFix``; es verschiebt keine
    Fläche, es näht (:func:`_sewn`). Erst wenn auch das nichts hilft, ist die
    Kombination wirklich keine.
    """
    if not _is_sound_rod(solid, at_least=at_least):
        solid = _sewn(solid)
    if not _is_sound_rod(solid, at_least=at_least):
        _log.warning("thread rod refused: d=%.2f pitch=%.2f (%s)", major, pitch, _rod_state(solid))
        raise GeometryError(
            detail=_(
                "Aus diesem Durchmesser und dieser Steigung entsteht kein "
                "geschlossener Bolzen — der Gang trifft den Kern nicht sauber."
            ),
            values={"diameter": major, "pitch": pitch},
            suggestions=(
                Action(id="coarser_pitch", label=_("Eine gröbere Steigung nehmen.")),
                Action(id="smaller_diameter", label=_("Einen kleineren Durchmesser nehmen.")),
                Action(id="use_parts", label=_("Stattdessen den Gewinde-Baustein verwenden.")),
            ),
        )
    return solid


def _is_sound_rod(solid: Solid, *, at_least: float = 0.0) -> bool:
    """Ob dieser Bolzen etwas ist, das man weiterreichen kann: Volumen über
    ``at_least``, geschlossen, ein Stück.

    ``at_least`` ist das Volumen, das ein Bolzen **mit** Gang mindestens hat
    (Kern und halber Gang, :func:`threaded_rod`): Was nicht darüber liegt,
    hat den Gang still verloren (B3, P2.5).

    **Gefragt wird der Körper, nicht sein Netz.** Hier standen
    ``is_watertight`` und ``component_count``, und beide beantworten die Frage
    über die Dreiecke — also über eine Näherung, die je nach Plattform anders
    ausfällt. Auf dem macOS-Runner kam M6 mit richtigem Volumen und als ein
    Stück heraus und galt trotzdem als undicht, weil die Vernetzung der
    Gewindeflanke dort ritzte; die Absage traf einen Bolzen, der gelungen war.

    **Und das Volumen ist ein grobes** (``properties.estimated_volume``): Die
    Frage lautet „liegt der Gang über dem Kern?", und die entscheidet ein
    Wert auf 10⁻⁷ so sicher wie einer auf 10⁻⁹ — in einem Vierzigstel der
    Zeit. Das Integral auf ``INTEGRAL_RELATIVE_ERROR`` kostete an einem
    M3 x 0,5 x 60 dreieinhalb Sekunden und fiel danach mit der Kopie für die
    feinere Vernetzung weg (22.09.2026).
    """
    from app.core.brep.properties import estimated_volume

    return (
        solid.solid_count == 1
        and solid.is_closed
        and estimated_volume(solid.shape) > max(EPS_GEOM, at_least + EPS_GEOM)
    )


def _rod_state(solid: Solid) -> str:
    """Woran eine Stufe gescheitert ist, in einer Zeile fürs Protokoll.

    **Eine Absage ohne Messwert ist eine Absage ohne Diagnose.** Der Bolzen
    kann auf drei Arten unbrauchbar sein — kein Volumen, offen, zerfallen —,
    und welche es war, stand nirgends. Gezählt wird am Körper, wie in
    :func:`_is_sound_rod`, nicht an seinem Netz.
    """
    from app.core.brep.properties import estimated_volume

    return (
        f"volume={estimated_volume(solid.shape):.3f} closed={solid.is_closed} "
        f"solids={solid.solid_count}"
    )


def _sewn(solid: Solid) -> Solid:
    """Offene Nähte schließen, ohne die Geometrie zu verrücken.

    ``ShapeFix_Shape`` ist OCCTs eigener Weg dafür. Er wird hier **nur** als
    zweiter Anlauf gerufen: Was beim ersten Mal geschlossen herauskam, geht
    unverändert weiter — eine Reparatur, die immer läuft, kostet Zeit und
    verdeckt, dass sie gebraucht wurde. Die Toleranz ist die, die die Form
    mitbringt: Was über die Naht hinausgeht, verrückt Flächen, und dann
    stimmt das Gewinde nicht mehr. (Bis RM-195 nahm der Sweep-Bolzen hier
    eine Grenze aus der Steigung an; der genähte Bolzen braucht keine.)
    """
    from OCP.ShapeFix import ShapeFix_Shape

    working = replace(solid)
    fix = ShapeFix_Shape(working.shape)
    fix.Perform()
    return working.replacing(fix.Shape(), history=fix.Context())


def _fuzzy_boolean(
    kind: str, first: Solid, second: Solid, sentence: Any, tolerance: float = EPS_GEOM
) -> Solid:
    """Boolesch mit kleiner Fuzzy-Toleranz — für die Löcher von Durchzug und Bahn.

    Die Löcher eines Umrisses übernehmen ``ThruSections`` und ``MakePipeShell``
    nicht; jedes wird als eigener Körper derselben Bahn abgezogen, und dessen
    Flanken stoßen genau dort an die des Außenkörpers, wo Umriss und Loch
    einander berühren. ``sentence`` ist der Satz des Aufrufers, wenn es nicht
    gelingt: **Der Satz gehört dem Weg, nicht dem Werkzeug** — hier stand bis
    zum 22.09.2026 die Absage des alten Gewindebolzens („Kern und Gang des
    Gewindes …"), und ein Loch im Durchzug scheiterte mit einem Satz über ein
    Gewinde, das es nicht gab.
    """
    operation = boolean_builder(kind, first.shape, second.shape, tolerance=tolerance)
    return _finished(
        operation,
        sentence,
        first,
        others=() if kind == "difference" else (second,),
    )


def bounds(solid: Solid) -> tuple[float, float, float, float, float, float]:
    """Der Hüllquader eines Körpers: xmin, ymin, zmin, xmax, ymax, zmax.

    Über ``AddOptimal`` ohne Vernetzung und ohne Formtoleranz: das einfache
    ``Add`` — und auch ``AddOptimal`` in der Vorgabe — liest die gespeicherte
    Vernetzung mitsamt ihrem Durchhang. Ein Körper, den die Auswertung fürs
    Hashing vernetzt hatte, wurde damit ringsum ein Hundertstel größer, die
    Oberseite lag über jeder echten Fläche, und eine Tasche entsprechend
    flacher. Exakt aus der Geometrie gerechnet kostet es hier nichts."""
    require()
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(solid.shape, box, False, False)
    xmin, ymin, zmin, xmax, ymax, zmax = box_limits(box)
    return (xmin, ymin, zmin, xmax, ymax, zmax)


# --- Innereien -------------------------------------------------------------------


# --- Querschnitte: ebene Flächen in XY als exakter Zwilling des Netzquerschnitts (P2.7) ---

OFFSET_FAILED = _(
    "Der Konturversatz ließ sich exakt nicht bilden. Ändern Sie die Kontur oder den Abstand."
)
SECTIONS_NOT_JOINED = _("Die Querschnitte ließen sich nicht verknüpfen. Ändern Sie die Kontur.")


def face_of(profile: Profile) -> Any:
    """Die ebene Fläche eines Umrisses in XY — der exakte Querschnitt eines Bausteins.

    Das Gegenstück zu ``geom.contours.section_of``: Dort wird der Umriss nach
    ``max_sag`` in Sehnen zerlegt, hier bleibt ein Bogen ein Bogen. Die
    Profilklemmen bauen aus solchen Flächen (``knowledge/parts/section.py``).
    """
    require()
    return _face(profile, _lift_xy)


def rectangle_face(x0: float, x1: float, y0: float, y1: float) -> Any:
    """Ein achsparalleles Rechteck als Fläche — die Ohren einer Klemme, eine Halbebene."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    polygon = BRepBuilderAPI_MakePolygon()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        polygon.Add(gp_Pnt(x, y, 0.0))
    polygon.Close()
    return BRepBuilderAPI_MakeFace(polygon.Wire(), True).Face()


def offset_face(face: Any, distance: float) -> Any:
    """Exakter Normalversatz einer Kontur: Bögen bleiben Bögen, Ecken bekommen Kreisbögen.

    ``BRepOffsetAPI_MakeOffset`` mit ``GeomAbs_Arc`` — der eine Baustein, den
    Klemmen und Dichtungen zusätzlich brauchen (Bericht P2.7, Abschnitt 4.3):
    Ein Kreis um vier Millimeter versetzt ist wieder ein Kreis, und das Prisma
    darüber ein Zylinder. Positiv wächst Material, negativ schrumpft es. Ein
    Versatz, der die Kontur in mehrere Teile zerlegt, ist keine Wand mehr und
    wird abgewiesen — dieselbe Regel, die der Netzquerschnitt am Polygon prüft.
    """
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
    from OCP.GeomAbs import GeomAbs_Arc
    from OCP.TopAbs import TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    if abs(distance) <= EPS_GEOM:
        return face
    offset = BRepOffsetAPI_MakeOffset(TopoDS.Face(face), GeomAbs_Arc)
    try:
        offset.Perform(distance)
        done = offset.IsDone()
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # OpenCASCADE wirft eigene Ausnahmearten
        raise GeometryError(detail=OFFSET_FAILED, suggestions=(CORRECT_INPUT, CANCEL)) from problem
    if not done:
        raise GeometryError(detail=OFFSET_FAILED, suggestions=(CORRECT_INPUT, CANCEL))
    wires = []
    explorer = TopExp_Explorer(offset.Shape(), TopAbs_WIRE)
    while explorer.More():
        wires.append(TopoDS.Wire(explorer.Current()))
        explorer.Next()
    if len(wires) != 1:
        raise ValidationError(
            field="sketch",
            constraint="profile_clamp",
            detail=_(
                "Der Konturversatz zerfällt in mehrere Teile. "
                "Ändern Sie Kontur oder Einlagenstärke."
            ),
        )
    return BRepBuilderAPI_MakeFace(wires[0], True).Face()


def shrunk_faces(face: Any, distance: float) -> tuple[Any, ...]:
    """Die Fläche um ``distance`` nach innen versetzt — jedes Stück für sich, nach oben gerichtet.

    Das exakte Gegenstück zu ``buffer(-distance)`` am Netz, dem Kragen eines
    Deckels (``geom.lid``): Jeder Punkt des Ergebnisses liegt mindestens
    ``distance`` vom Rand entfernt, ein Bogen bleibt ein Bogen mit kleinerem
    Radius, und an einer einspringenden Ecke — einer Wandecke, die in den
    Hohlraum ragt — läuft der Versatz im Bogen um sie herum
    (``GeomAbs_Arc``). Die Gehrung des Netzwegs (``join_style=2``) nimmt dort
    ein wenig mehr weg; beide halten das Spiel. **Gemessen, nicht gewählt:**
    ``GeomAbs_Intersection`` scheiterte an zwei von vier echten Modellen
    (``Cat_1.stp``, ``Cat_2.stp``: Ränder aus Kreisbögen), der Bogen an
    keinem. Anders als bei :func:`offset_face` darf die Kontur dabei in
    Stücke zerfallen — eine Taille, schmaler als der Versatz, gibt zwei
    Kragen, wie am Netz.
    """
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
    from OCP.GeomAbs import GeomAbs_Arc
    from OCP.TopAbs import TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    if distance <= EPS_GEOM:
        return (upward(face),)
    offset = BRepOffsetAPI_MakeOffset(TopoDS.Face(face), GeomAbs_Arc)
    try:
        offset.Perform(-distance)
        done = offset.IsDone()
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # OpenCASCADE wirft eigene Ausnahmearten
        raise GeometryError(detail=OFFSET_FAILED, suggestions=(CORRECT_INPUT, CANCEL)) from problem
    if not done:
        raise GeometryError(detail=OFFSET_FAILED, suggestions=(CORRECT_INPUT, CANCEL))
    faces: list[Any] = []
    explorer = TopExp_Explorer(offset.Shape(), TopAbs_WIRE)
    while explorer.More():
        made = BRepBuilderAPI_MakeFace(TopoDS.Wire(explorer.Current()), True)
        explorer.Next()
        if made.IsDone():
            faces.append(upward(made.Face()))
    return tuple(faces)


def upward(face: Any) -> Any:
    """Dieselbe ebene Fläche, nach oben gerichtet — ein Prisma darüber wächst nach außen.

    Eine Fläche aus einem Draht erbt dessen Umlaufsinn: Aus dem Innenrand
    eines Querschnitts wird eine Fläche, die nach unten zeigt. Gefragt wird
    die Ebene samt Orientierung der Fläche, nicht der Draht.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.TopoDS import TopoDS

    up = float(BRepAdaptor_Surface(face).Plane().Axis().Direction().Z())
    if face.Orientation() == TopAbs_REVERSED:
        up = -up
    return face if up > 0.0 else TopoDS.Face(face.Reversed())


def face_boolean(kind: str, first: Any, second: Any) -> Any:
    """Vereinigung, Differenz oder Schnitt zweier ebener Flächen in XY.

    Kommt genau eine Fläche heraus, ist sie das Ergebnis; mehrere bleiben als
    Verbund, und ob das erlaubt ist, entscheidet der Aufrufer am
    Netzquerschnitt daneben (``Section.pieces``).
    """
    require()
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    operation = boolean_builder(kind, first, second)
    try:
        operation.Build()
        done = operation.IsDone()
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # OpenCASCADE wirft eigene Ausnahmearten
        raise GeometryError(
            detail=SECTIONS_NOT_JOINED, suggestions=(CORRECT_INPUT, CANCEL)
        ) from problem
    if not done:
        raise GeometryError(detail=SECTIONS_NOT_JOINED, suggestions=(CORRECT_INPUT, CANCEL))
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    # Eine Vereinigung zweier ebener Flächen lässt drei Teilflächen zurück,
    # die sich Kanten teilen; als eine Fläche zusammengelegt zieht das Prisma
    # darüber einen Körper statt dreier.
    unified = ShapeUpgrade_UnifySameDomain(operation.Shape(), True, True, False)
    unified.Build()
    shape = unified.Shape()
    faces = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        faces.append(TopoDS.Face(explorer.Current()))
        explorer.Next()
    return faces[0] if len(faces) == 1 else shape


def face_bounds(face: Any) -> tuple[float, float, float, float]:
    """Der Hüllquader einer Fläche in XY: xmin, ymin, xmax, ymax — exakt aus der Geometrie.

    Wie :func:`bounds` über ``AddOptimal`` ohne Vernetzung und ohne Formtoleranz;
    die Ohren einer Klemme sitzen sonst um den Sehnen-Sag des Netzquerschnitts
    daneben.
    """
    require()
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(face, box, False, False)
    xmin, ymin, _zmin, xmax, ymax, _zmax = box_limits(box)
    return (xmin, ymin, xmax, ymax)


def face_rotated(face: Any, degrees: float) -> Any:
    """Die Fläche um die Z-Achse gedreht — der Teilungsrahmen einer Klemme."""
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf

    turn = gp_Trsf()
    turn.SetRotation(gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0)), math.radians(degrees))
    return BRepBuilderAPI_Transform(face, turn, True).Shape()


def prism(face: Any, height: float, *, bottom: float = 0.0) -> Solid:
    """Das Prisma über einer fertigen Fläche, mit dem Boden auf ``bottom``.

    Der Boden wird vor dem Einpacken verschoben: Eine Verschiebung des fertigen
    Körpers über ``edit.transformed`` kostete zwei Volumenintegrale (RM-196),
    eine Verschiebung der rohen Form nichts.
    """
    require()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Trsf, gp_Vec

    require_positive("height", height)
    body = _finished(
        BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, height)),
        _("Aus diesem Umriss entsteht kein Körper."),
    )
    if not bottom:
        return body
    lift = gp_Trsf()
    lift.SetTranslation(gp_Vec(0.0, 0.0, bottom))
    return Solid(BRepBuilderAPI_Transform(body.shape, lift, True).Shape())


def round_cord(face: Any, radius: float, centre_z: float) -> Solid:
    """Eine runde Schnur entlang des Außenrands einer Fläche, an jeder Ecke rund (P2.7).

    Die exakte Seite von ``geom.seal._round_tube``: die Minkowski-Summe des
    Wegs mit der Kugel, die das Netz als Hüllenkette facettiert — je Strecke
    ein Zylinder, je Kreisbogen ein Torusstück, je Ecke eine Kugel, alles
    vereinigt; ein geschlossener Kreis ist ein ganzer Torus. Gemessen:
    Rechteckweg 20 mal 12 gegen die Analytik (vier Zylinder, vier Kugeln) auf
    10⁻¹⁰, Kreisweg Ø 20 ein einziger Torus.

    **Kein Rohrsweep mit runden Ecken.** ``BRepOffsetAPI_MakePipeShell`` mit
    ``BRepBuilderAPI_RoundCorner`` baute dieselbe Form gültig und ebenso
    genau, kam aber aus STEP um zehn Prozent leichter zurück (21.09.2026):
    Seine Eckflächen sind keine Kugeln, und was STEP daraus liest, ist ein
    anderer Körper. Eine Kante, die weder Strecke noch Bogen ist (ein Spline),
    bekommt ihr Stück als Rohr entlang genau dieser einen Kante — dort gibt
    es keine Ecke, die rund werden müsste.
    """
    require()
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
        BRepBuilderAPI_Transform,
    )
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeCylinder,
        BRepPrimAPI_MakeSphere,
        BRepPrimAPI_MakeTorus,
    )
    from OCP.BRepTools import BRepTools
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from app.core.brep import edit

    require_positive("radius", radius)
    lift = gp_Trsf()
    lift.SetTranslation(gp_Vec(0.0, 0.0, centre_z))
    spine = TopoDS.Wire(BRepBuilderAPI_Transform(BRepTools.OuterWire_s(face), lift, True).Shape())
    edges = []
    explorer = TopExp_Explorer(spine, TopAbs_EDGE)
    while explorer.More():
        edges.append(TopoDS.Edge(explorer.Current()))
        explorer.Next()
    pieces: list[Solid] = []
    whole_circle = False
    for edge in edges:
        curve = BRepAdaptor_Curve(edge)
        first, last = curve.FirstParameter(), curve.LastParameter()
        start, end = curve.Value(first), curve.Value(last)
        kind = curve.GetType()
        if kind == GeomAbs_Line:
            length = start.Distance(end)
            if length <= EPS_GEOM:
                continue
            axis = gp_Ax2(start, gp_Dir(gp_Vec(start, end)))
            pieces.append(Solid(BRepPrimAPI_MakeCylinder(axis, radius, length).Shape()))
        elif kind == GeomAbs_Circle:
            # Der Bogen läuft im Parameter gegen den Uhrzeigersinn um seine
            # Achse; der Rahmen des Torus beginnt mit seiner X-Richtung am
            # Bogenanfang und überstreicht denselben Winkel.
            circle = curve.Circle()
            centre = circle.Location()
            sweep = float(last - first)
            axis = gp_Ax2(centre, circle.Axis().Direction(), gp_Dir(gp_Vec(centre, start)))
            if sweep >= 2.0 * math.pi - EPS_GEOM:
                whole_circle = len(edges) == 1
                torus = BRepPrimAPI_MakeTorus(axis, circle.Radius(), radius)
            else:
                torus = BRepPrimAPI_MakeTorus(axis, circle.Radius(), radius, sweep)
            pieces.append(Solid(torus.Shape()))
        else:
            tangent = gp_Vec()
            curve.D1(first, gp_Pnt(), tangent)
            ring = BRepBuilderAPI_MakeWire(
                BRepBuilderAPI_MakeEdge(gp_Circ(gp_Ax2(start, gp_Dir(tangent)), radius)).Edge()
            ).Wire()
            path = BRepBuilderAPI_MakeWire(edge).Wire()
            pipe = BRepOffsetAPI_MakePipe(path, BRepBuilderAPI_MakeFace(ring, True).Face())
            pieces.append(Solid(pipe.Shape()))
    if not whole_circle:
        corners = ShapeMap()
        TopExp.MapShapes_s(spine, TopAbs_VERTEX, corners)
        for index in range(1, corners.Extent() + 1):
            point = BRep_Tool.Pnt_s(TopoDS.Vertex(corners.FindKey(index)))
            pieces.append(Solid(BRepPrimAPI_MakeSphere(point, radius).Shape()))
    if not pieces:
        raise GeometryError(
            detail=_("Aus diesem Umriss entsteht kein Körper."),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return pieces[0] if len(pieces) == 1 else edit.boolean("union", pieces)


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
    """Alle Punkte, über die dieses Segment läuft.

    ``through`` gehört dazu: Bei einem Spline sind das **alle** Stützpunkte,
    und ohne sie sahen ``_leftmost``/``_rightmost`` nur Anfang und Ende — ein
    Querschnitt, dessen Spline 40 mm über die Drehachse greift, meldete 10,
    die Achsprüfung von ``revolve`` lief ins Leere, und der Kunde bekam einen
    rohen Kernfehler für seine eigene Zeichnung (Gesamtreview D-3).
    """
    found = [segment.start, segment.end]
    if segment.via is not None:
        found.append(segment.via)
    found.extend(segment.through)
    if segment.kind == "ellipse":
        # Die Scheitel, die das Stück überstreicht: An einer gedrehten Ellipse
        # reicht sie weiter als ihre Enden und ihr Stützpunkt, und die
        # Achsprüfung von ``revolve`` sähe sonst eine Ellipse über der Achse
        # nicht.
        found.extend(ellipse_segment_extremes(segment))
    elif segment.kind == "arc":
        # Dasselbe beim Kreisbogen: Ein Bogen über 340° hatte seinen linken
        # Scheitel jenseits der Achse, und geprüft wurden nur seine drei Punkte.
        found.extend(arc_segment_extremes(segment))
    return found


def _top_faces(solid: Solid, *, cancelled: CancelToken | None = None) -> list[Any]:
    _, _, _, _, _, top = bounds(solid)
    found = []
    for face, normal, centre in _planar_faces(solid, cancelled=cancelled):
        if normal[2] > 0.9 and abs(centre[2] - top) <= 1e-4:
            found.append(face)
    return found


def _planar_faces(
    solid: Solid, *, cancelled: CancelToken | None = None
) -> list[tuple[Any, tuple[float, float, float], Any]]:
    """Jede ebene Fläche mit ihrer nach außen zeigenden Normale und Mitte.

    Träger und Mitte kommen aus dem Memo des Körpers: ``push_faces`` fragt
    zweimal (Richtung, dann Stelle), und vorher wurde jede Fläche zweimal
    beschrieben und integriert.
    """
    found = []
    for index, face in enumerate(solid.faces()):
        surface = solid.surface(index, cancelled=cancelled)
        if not isinstance(surface, PlaneSurface):
            continue
        centre = solid.face_properties(index, cancelled=cancelled).centre
        found.append((face, surface.normal, centre))
    return found


def _finished(
    builder: Any,
    sentence: Any,
    base: Solid | None = None,
    *,
    cancelled: CancelToken | None = None,
    others: tuple[Solid, ...] = (),
) -> Solid:
    """Baut fertig und macht aus dem Scheitern einen Satz mit Vorschlag (§33.1).

    Die Vorschläge sind die des exakten Kerns: Eingabe berichtigen oder
    abbrechen. Die geerbten — Netz reparieren, offene Stellen zeigen — gibt es
    für einen B-Rep-Körper nicht (wie in ``edit.boolean``).
    """
    try:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        builder.Build()
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if not builder.IsDone():
            raise GeometryError(detail=sentence, suggestions=(CORRECT_INPUT, CANCEL))
        shape = builder.Shape()
    except GeometryError, OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # OpenCASCADE wirft eigene Ausnahmearten
        raise GeometryError(detail=sentence, suggestions=(CORRECT_INPUT, CANCEL)) from problem
    _log.info("profile build via %s", type(builder).__name__)
    return (
        base.replacing(shape, history=builder, others=others, cancelled=cancelled)
        if base is not None
        else Solid(shape)
    )


def push_faces(
    solid: Solid,
    direction: tuple[float, float, float],
    distance: float,
    centre: tuple[float, float, float] | None = None,
    *,
    selected_faces: Sequence[int] | None = None,
    cancelled: CancelToken | None = None,
) -> Solid:
    """Versetzt eine Fläche — oder alle einer Richtung — entlang ihrer Normalen.

    Das ist Press/Pull: eine Wand greifen und verschieben, ohne den Rest neu zu
    zeichnen. Über jeder gewählten Fläche entsteht ein Prisma ihres eigenen
    Umrisses; nach außen wird es vereinigt, nach innen abgezogen. Damit wachsen
    die Nachbarwände mit, statt eine Stufe zu hinterlassen — das Prisma hat
    genau die Kontur der Fläche, die es fortsetzt.

    ``selected_faces`` benennt vollständige aktuelle Topologieflächen des
    Eingabe-Solids. Ihre eigenen Normalen bestimmen die Bewegung; Richtung
    und Mitte suchen nur im älteren Modus ``None`` nach einer Fläche.
    Eine ausdrückliche leere oder ungültige Auswahl wechselt nie den Modus.

    **Nicht** über ``BRepOffsetAPI_MakeOffsetShape``: das war der erste Versuch
    und versetzt *alle* Flächen des Körpers. Eine Ausnahmeliste nimmt es zwar
    entgegen, aber ``PerformByJoin`` liest sie nicht — der Quader wurde in
    beide Richtungen kürzer, und der Test sagte es sofort.
    """
    require()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    if is_zero(distance):
        raise ValidationError(
            "distance",
            _("Ohne Weg bewegt sich nichts — dieser Wert darf nicht null sein."),
            value=distance,
        )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    indices = (
        None
        if selected_faces is None
        else solid.checked_face_indices(selected_faces, cancelled=cancelled)
    )
    working = replace(solid)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if indices is None:
        wanted = _facing(working, direction, cancelled=cancelled)
        if not wanted:
            raise ValidationError(
                "nx",
                _("In diese Richtung zeigt keine ebene Fläche dieses Körpers."),
                value=direction,
                constraint="no_face",
            )
        if centre is not None:
            wanted = _nearest_face(working, wanted, centre, cancelled=cancelled)
    else:
        faces = working.faces()
        wanted = []
        for index in indices:
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            face = faces[working._copied_faces[index]]
            surface = solid.surface(index, cancelled=cancelled)
            if not isinstance(surface, PlaneSurface):
                raise ValidationError(
                    detail=_(
                        "Nicht jede gewählte Fläche ist als eben erkannt. "
                        "Wählen Sie zum Versetzen vollständige ebene Flächen."
                    )
                )
            wanted.append((face, surface.normal))

    outcome = working
    for face, normal in wanted:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        reach = gp_Vec(*(value * abs(distance) for value in normal))
        prism = BRepPrimAPI_MakePrism(face, reach if distance > 0 else reach.Reversed()).Shape()
        joined = boolean_builder("union" if distance > 0 else "difference", outcome.shape, prism)
        # ``_finished`` statt blindem ``Shape()``: Ein Schritt ohne ``IsDone``
        # lieferte sonst wortlos irgendetwas — bis hin zu gar nichts.
        outcome = _finished(
            joined,
            _(
                "Mit diesem Weg bleibt von der Fläche nichts übrig — kleiner "
                "versetzen oder die Richtung umkehren."
            ),
            outcome,
            cancelled=cancelled,
        )
    # **Die Nachbarwände wachsen, sie zerfallen nicht** (23.09.2026): Die
    # Vereinigung mit dem Prisma ließ jede Seitenwand als zwei Teilflächen
    # stehen — die alte und den Streifen darüber. Eine Skizze auf der Seite
    # sah nur eine Hälfte, und die Erkennung zählte zehn Flächen an einem
    # Quader. ``unified`` legt sie zusammen, Filamentgrenzen bleiben.
    from app.core.brep.edit import unified

    # Vorher gefragt: ``unified`` baut und kopiert eine weitere Form, und nach
    # einem Abbruch rechnete sie noch für ein Ergebnis, das niemand abholt.
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    outcome = unified(outcome)
    # Und das Ergebnis muss ein Körper sein: distance = -25 auf einem 20 mm
    # hohen Quader gab Volumen null, null Befunde — ein Schritt im Verlauf,
    # nichts im Bild, und gesagt wurde nichts (Gesamtreview D-6).
    if (
        outcome.solid_count < 1
        or outcome._properties("volume", cancelled=cancelled).mass <= EPS_GEOM
    ):
        raise GeometryError(
            detail=_(
                "Mit diesem Weg bleibt vom Körper nichts übrig — kleiner "
                "versetzen oder die Richtung umkehren."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return outcome


def _nearest_face(
    solid: Solid,
    candidates: list[tuple[Any, tuple[float, float, float]]],
    centre: tuple[float, float, float],
    *,
    cancelled: CancelToken | None = None,
) -> list[tuple[Any, tuple[float, float, float]]]:
    """Von den passend gerichteten Flächen die **eine** an dieser Stelle.

    **Warum es das gibt** (Befund Robert, 10.09.2026): Ohne diese Auswahl
    bewegte *Fläche versetzen* jede Fläche, deren Normale in die Richtung
    zeigte. An einer Treppe wanderten damit alle Stufen zugleich — gemessen
    24000,0 mm³ statt 21000,0 —, und der Kunde hatte eine einzelne
    angeklickt. Die Richtung bleibt der Vorfilter, die Stelle entscheidet.

    Gesucht wird über den Flächenschwerpunkt und nicht über eine Kennung: Ein
    nativer Handle gehört dem Lauf, der ihn erzeugt hat, und ein Index in die
    Topologie verschiebt sich beim nächsten Schritt — derselbe Grund, aus dem
    eine Kante über ihre Lage benannt wird (:func:`edit.edge_key`).
    """
    places = {id(face): spot for face, _n, spot in _planar_faces(solid, cancelled=cancelled)}
    reachable = [(face, normal) for face, normal in candidates if id(face) in places]
    if not reachable:
        return candidates[:1]
    return [min(reachable, key=lambda entry: math.dist(places[id(entry[0])], centre))]


def _facing(
    solid: Solid,
    direction: tuple[float, float, float],
    *,
    cancelled: CancelToken | None = None,
) -> list[tuple[Any, tuple[float, float, float]]]:
    """Die ebenen Flächen, deren Normale in die gegebene Richtung zeigt, mit
    ihrer eigenen Normalen — das Prisma folgt der Fläche, nicht der Anfrage."""
    length = math.sqrt(sum(value * value for value in direction))
    if length <= EPS_GEOM:
        return []
    unit = [value / length for value in direction]
    return [
        (face, normal)
        for face, normal, _centre in _planar_faces(solid, cancelled=cancelled)
        if sum(a * b for a, b in zip(normal, unit, strict=True)) > 0.9
    ]
