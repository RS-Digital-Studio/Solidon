"""Schrift als exakte Flächen — die Kurven der Glyphen statt ihrer Vielecke (P2.8).

Die Netzfassung (``geom.label_ops.outlines``) flacht jeden Glyphenpfad zu
Vielecken ab. Hier werden dieselben Konturen, wie ``geom.glyphs`` sie über
HarfBuzz aus der Schriftdatei liest, als Strecken und Bézier-Kurven gebaut — eine
Beschriftung am exakten Körper bleibt damit exakt, und ein „o" ist in STEP
ein Kreis aus Kurven und kein 24-Eck.

**Die Füllregel ist die der Schrift: nonzero** (TrueType und CFF). Konturen,
die einander nicht schneiden, verschachteln sich über ihre Enthaltung — eine
Fläche je Außenkontur mit ihren direkten Löchern. Überlappen sich Konturen
(Comfortaa, Dancing Script: ineinanderlaufende Striche), entsteht die
Füllung über ebene Boolesche Operationen in der Reihenfolge der Größe:
Konturen im Drehsinn der größten vereinigen, die anderen ziehen ab.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import numpy as np

from app.core.brep.kernel import Solid, require
from app.core.errors import CANCEL, CORRECT_INPUT, GeometryError
from app.core.types import CancelToken, Point2
from app.core.units import EPS_GEOM
from app.i18n import _

#: Wie viele Punkte je Kurve die Näherung für Enthaltung und Überlappung
#: bekommt. Sie entscheidet nur, **welche** Kontur in welcher liegt, nie die
#: Geometrie — die kommt aus den Kurven selbst.
_SAMPLES_PER_CURVE = 16


@dataclass(frozen=True, slots=True)
class Contour:
    """Eine geschlossene Kontur eines Glyphs: Stücke als Polpunkte in der Ebene.

    Ein Stück mit zwei Punkten ist eine Strecke, mit drei eine quadratische,
    mit vier eine kubische Bézier-Kurve; das Ende eines Stücks ist der
    Anfang des nächsten, das letzte endet am Anfang des ersten.
    """

    pieces: tuple[tuple[Point2, ...], ...]

    def sampled(self) -> list[Point2]:
        """Punkte entlang der Kontur — nur für Enthaltung und Drehsinn."""
        points: list[Point2] = []
        for poles in self.pieces:
            if len(poles) == 2:
                points.append(poles[0])
                continue
            degree = len(poles) - 1
            array = np.asarray(poles, dtype=float)
            for t in np.linspace(0.0, 1.0, _SAMPLES_PER_CURVE, endpoint=False):
                weights = np.asarray(
                    [
                        math.comb(degree, k) * (1.0 - t) ** (degree - k) * t**k
                        for k in range(degree + 1)
                    ]
                )
                x, y = weights @ array
                points.append((float(x), float(y)))
        return points


def glyph_contours(found: Sequence[Sequence[Sequence[Point2]]]) -> list[Contour]:
    """Die Konturen aus ``geom.glyphs.contours`` als :class:`Contour`.

    Jede Kontur kommt als Folge von Stücken (Polpunkte), geschlossen: Das
    letzte endet am Anfang des ersten. Stücke ohne Länge und Konturen ohne
    Fläche fallen weg — sie tragen nichts und brächen den Draht.
    """
    result: list[Contour] = []
    for pieces in found:
        kept = tuple(
            tuple((float(x), float(y)) for x, y in poles)
            for poles in pieces
            if _length(poles) > EPS_GEOM
        )
        if len(kept) >= 2 or (kept and len(kept[0]) > 2):
            contour = Contour(kept)
            if abs(_signed_area(contour.sampled())) > EPS_GEOM**2:
                result.append(contour)
    return result


def _length(poles: Sequence[Point2]) -> float:
    """Die Länge des Kontrollpolygons — null heißt: das Stück ist ein Punkt."""
    return sum(math.dist(a, b) for a, b in pairwise(poles))


def _signed_area(points: Sequence[Point2]) -> float:
    """Schuhbandformel; positiv gegen den Uhrzeigersinn."""
    total = 0.0
    for (x0, y0), (x1, y1) in zip(points, [*points[1:], points[0]], strict=True):
        total += x0 * y1 - x1 * y0
    return total / 2.0


def _wire(contour: Contour) -> Any:
    """Der geschlossene Draht einer Kontur in der Ebene z = 0, Stück für Stück exakt."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.collections import Array1_gp_Pnt
    from OCP.Geom import Geom_BezierCurve
    from OCP.gp import gp_Pnt

    maker = BRepBuilderAPI_MakeWire()
    for poles in contour.pieces:
        if len(poles) == 2:
            edge = BRepBuilderAPI_MakeEdge(
                gp_Pnt(poles[0][0], poles[0][1], 0.0), gp_Pnt(poles[1][0], poles[1][1], 0.0)
            ).Edge()
        else:
            array = Array1_gp_Pnt(1, len(poles))
            for number, (x, y) in enumerate(poles, start=1):
                array.SetValue(number, gp_Pnt(x, y, 0.0))
            edge = BRepBuilderAPI_MakeEdge(Geom_BezierCurve(array)).Edge()
        maker.Add(edge)
    if not maker.IsDone():
        raise _no_letters()
    return maker.Wire()


def _no_letters() -> GeometryError:
    return GeometryError(
        detail=_("Aus diesem Text ließ sich keine Form bilden."),
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def _plain_face(wire: Any) -> Any:
    """Eine ebene Fläche um einen Draht, richtig herum (Normale +Z)."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.ShapeFix import ShapeFix_Face

    face = BRepBuilderAPI_MakeFace(wire, True).Face()
    fix = ShapeFix_Face(face)
    fix.FixOrientation()
    fix.Perform()
    return fix.Face()


def letter_faces(contours: Sequence[Contour], *, cancelled: CancelToken | None = None) -> list[Any]:
    """Die gefüllten Bereiche als ebene Flächen in z = 0 — nonzero wie die Schrift."""
    require()
    from shapely.geometry import Polygon

    def check() -> None:
        if cancelled is not None:
            cancelled.raise_if_cancelled()

    samples = [contour.sampled() for contour in contours]
    polygons = [Polygon(points).buffer(0) for points in samples]
    areas = [_signed_area(points) for points in samples]
    order = sorted(range(len(contours)), key=lambda number: -abs(areas[number]))
    overlapping = any(
        polygons[a].boundary.intersects(polygons[b].boundary)
        for position, a in enumerate(order)
        for b in order[position + 1 :]
        if polygons[a].bounds[0] <= polygons[b].bounds[2]
        and polygons[b].bounds[0] <= polygons[a].bounds[2]
        and polygons[a].bounds[1] <= polygons[b].bounds[3]
        and polygons[b].bounds[1] <= polygons[a].bounds[3]
    )
    check()
    if not overlapping:
        return _nested_faces(contours, polygons, order, check)
    return _folded_faces(contours, areas, order, check)


def _nested_faces(
    contours: Sequence[Contour], polygons: Sequence[Any], order: Sequence[int], check: Any
) -> list[Any]:
    """Ohne Überlappung: eine Fläche je Außenkontur, ihre direkten Kinder als Löcher."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.ShapeFix import ShapeFix_Face

    parent: dict[int, int | None] = {}
    for position, number in enumerate(order):
        point = polygons[number].representative_point()
        # Der kleinste Umgebende ist der Elter; ``order`` läuft von groß nach klein.
        parent[number] = next(
            (other for other in reversed(order[:position]) if polygons[other].contains(point)),
            None,
        )
    depth: dict[int, int] = {}
    for number in order:
        above = parent[number]
        depth[number] = 0 if above is None else depth[above] + 1
    faces = []
    for number in order:
        check()
        if depth[number] % 2:
            continue
        maker = BRepBuilderAPI_MakeFace(_wire(contours[number]), True)
        for child in order:
            if parent[child] == number:
                maker.Add(_wire(contours[child]))
        if not maker.IsDone():
            raise _no_letters()
        fix = ShapeFix_Face(maker.Face())
        fix.FixOrientation()
        fix.Perform()
        faces.append(fix.Face())
    return faces


def _folded_faces(
    contours: Sequence[Contour], areas: Sequence[float], order: Sequence[int], check: Any
) -> list[Any]:
    """Mit Überlappung: vereinigen im Drehsinn der größten Kontur, sonst abziehen."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    fill = math.copysign(1.0, areas[order[0]])
    result: Any = None
    for number in order:
        check()
        face = _plain_face(_wire(contours[number]))
        if math.copysign(1.0, areas[number]) == fill:
            if result is None:
                result = face
                continue
            builder = BRepAlgoAPI_Fuse(result, face)
        else:
            if result is None:
                continue
            builder = BRepAlgoAPI_Cut(result, face)
        if not builder.IsDone():
            raise _no_letters()
        result = builder.Shape()
    if result is None:
        raise _no_letters()
    # Die Boolesche hinterlässt an jeder früheren Kontur eine Naht; zusammengelegt
    # wird wieder eine Fläche je Bereich.
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    joined = ShapeUpgrade_UnifySameDomain(result, True, True, False)
    joined.Build()
    faces = []
    walk = TopExp_Explorer(joined.Shape(), TopAbs_FACE)
    while walk.More():
        faces.append(walk.Current())
        walk.Next()
    return faces


def letters(
    found: Sequence[Sequence[Sequence[Point2]]],
    height: float,
    *,
    cancelled: CancelToken | None = None,
) -> Solid:
    """Die Buchstaben (``geom.glyphs.contours``) als Prismen von z = 0 bis ``height``.

    Ein Verbund aus einem Körper je gefülltem Bereich — dieselbe Gestalt wie
    die aneinandergehängten Prismen des Netzwegs (``label_ops.label_solid``),
    nur mit den Kurven der Schrift. Die Flächen entstehen einmal und werden in
    einem Zug aufgezogen.
    """
    require()
    from OCP.BRep import BRep_Builder
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.TopoDS import TopoDS_Compound

    from app.core.brep.profiles import prism

    contours = glyph_contours(found)
    if not contours:
        raise _no_letters()
    faces = letter_faces(contours, cancelled=cancelled)
    if not faces:
        raise _no_letters()
    builder = BRep_Builder()
    flat = TopoDS_Compound()
    builder.MakeCompound(flat)
    for face in faces:
        if not BRepCheck_Analyzer(face).IsValid():
            raise _no_letters()
        builder.Add(flat, face)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    body = prism(flat, height)
    if not body.is_closed or body.solid_count != len(faces):
        raise _no_letters()
    return body
