"""Native Integrale über Knotenspannen und ursprüngliche NURBS-Trimmkurven.

Die Topologie bleibt unverändert. Volumen wie Fläche rechnet der Kern nativ auf
einem **knotenzerlegten Verbund** privater Arbeitsflächen: Jede Spline-Fläche
wird an ihren Knotenspannen geteilt, damit die native Gauß-Quadratur keine
schmale Spanne übersieht (der Zackenkörper in ``tests/test_brep.py`` verliert
ungeteilt 7·10⁻⁶, geteilt nichts), und zwei unabhängige Teilungen müssen sich
auf ``INTEGRAL_RELATIVE_ERROR`` einigen. Erst wenn das nicht gelingt, integriert
der Python-Rückfall entlang der ursprünglichen Randkurven — derselbe Weg, nur
tausendmal langsamer (genähtes M6-Gewinde: 20 ms gegen 3 s, gemessen
21.09.2026). Lage, Innenlöcher und Orientierung bleiben Teil des
Integrationsgebiets.
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
# Die Leiter der Knotenzerlegung: erst jede Spanne ganz, dann halbiert, dann
# geviertelt. Zwei aufeinanderfolgende Stufen müssen sich einigen; die erste
# genügt allein, wenn keine Fläche eine Spanne hat (nichts zu teilen).
_SUBDIVISIONS = (1, 2, 4)
# Die Trimmkurven werden beim Teilen an den Knotenlinien geschnitten. Diese
# Genauigkeit im Parameterraum verändert keine Kante der veröffentlichten Form.
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


def _span_source(
    face: Any, *, cancelled: CancelToken | None = None
) -> tuple[tuple[Any | None, str], tuple[Any | None, str]] | None:
    """Woher die Knotenspannen je Parameterrichtung kommen — oder ``None`` für analytische Träger.

    Ebene, Zylinder, Kegel, Kugel und Ring bleiben im nativen Standardweg.
    Alles andere wird zerlegt: Spline-Flächen an ihren eigenen Knoten, eine
    Extrusion an den Knoten ihrer Basiskurve (in U), ein Drehkörper ebenso (in
    V); Offset- und Trimmhüllen lesen unter sich. Eine Fläche ohne Knoten wird
    trotzdem zerlegt — die Leiter halbiert dann das Parametergebiet, und das
    ist der Nachweis, den der native Gauß-Weg ohne Knotenwissen nicht führt:
    Die Extrusion eines rationalen Kreises maß ungeteilt 1,2 Prozent daneben
    bei gemeldetem Fehler 2·10⁻¹⁶ (``test_planar_consumers_use_the_original_nurbs_faces``).
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.Geom import (
        Geom_BezierCurve,
        Geom_BezierSurface,
        Geom_BSplineCurve,
        Geom_BSplineSurface,
        Geom_OffsetSurface,
        Geom_SurfaceOfLinearExtrusion,
        Geom_SurfaceOfRevolution,
        Geom_TrimmedCurve,
    )
    from OCP.GeomAbs import (
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_Plane,
        GeomAbs_Sphere,
        GeomAbs_Torus,
    )

    from app.core.brep.kernel import _MAX_SURFACE_WRAPPERS, untrimmed_surface

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if BRepAdaptor_Surface(face).GetType() in (
        GeomAbs_Plane,
        GeomAbs_Cylinder,
        GeomAbs_Cone,
        GeomAbs_Sphere,
        GeomAbs_Torus,
    ):
        return None
    surface = BRep_Tool.Surface_s(face)
    for _depth in range(_MAX_SURFACE_WRAPPERS + 1):
        surface = untrimmed_surface(surface, cancelled=cancelled)
        if surface is None:
            raise _unresolved_integral()
        if isinstance(surface, (Geom_BSplineSurface, Geom_BezierSurface)):
            return (surface, "U"), (surface, "V")
        if isinstance(surface, (Geom_SurfaceOfLinearExtrusion, Geom_SurfaceOfRevolution)):
            curve = surface.BasisCurve()
            for _inner in range(_MAX_SURFACE_WRAPPERS + 1):
                if cancelled is not None:
                    cancelled.raise_if_cancelled()
                if not isinstance(curve, Geom_TrimmedCurve):
                    break
                curve = curve.BasisCurve()
            knotted = curve if isinstance(curve, (Geom_BSplineCurve, Geom_BezierCurve)) else None
            if isinstance(surface, Geom_SurfaceOfLinearExtrusion):
                return (knotted, ""), (None, "")
            return (None, ""), (knotted, "")
        if not isinstance(surface, Geom_OffsetSurface):
            return (None, ""), (None, "")
        surface = surface.BasisSurface()
    raise _unresolved_integral()


def _needs_spans(face: Any, *, cancelled: CancelToken | None = None) -> bool:
    """Analytische Flächen behalten ihren einfachen nativen Integrationsweg."""
    return _span_source(face, cancelled=cancelled) is not None


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
    """Innere Basisknoten im wirklichen Trimmintervall, auch über einer periodischen Naht.

    ``axis`` ist ``"U"`` oder ``"V"`` an einer Fläche und leer an einer Kurve
    (``NbKnots``, ``Knot``, ``IsPeriodic``, ``Period``); ohne Quelle gibt es keine Knoten.
    """
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
    """Zerlegt eine private Flächenkopie und erhält ihre äußeren und inneren Drähte.

    Die Teilflächen tragen die **ursprünglichen Trimmkurven**, an den
    Knotenlinien geschnitten — und sonst nichts: Weder werden 3D-Kurven neu
    gebaut noch die Parameterkurven mit ``SameParameter`` nachgezogen. Beides
    stand hier bis zum 21.09.2026 und verschob die Ränder um bis zu 8·10⁻⁶ mm
    (gemessen am Flankenrand eines M10-Bolzens mit Kantentoleranz 6·10⁻⁵),
    womit jede feinere Teilung ein **anderes** Gebiet integrierte und die
    Leiter an echten Gewinden nie zusammenkam (2·10⁻⁸ zwischen den Stufen).
    Die Integration liest allein die Parameterkurven; mit den ungeänderten
    stimmt die Zerlegung mit dem Randintegral der ganzen Fläche auf 10⁻¹²
    überein, und ob sie vollständig ist, belegt die Leiter der Aufrufer.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.BRepGProp import BRepGProp_Face
    from OCP.ShapeBuild import ShapeBuild_ReShape
    from OCP.ShapeFix import ShapeFix_ComposeShell
    from OCP.ShapeUpgrade import ShapeUpgrade_SplitSurface
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    from app.core.brep.kernel import untrimmed_surface

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    face = TopoDS.Face(BRepBuilderAPI_Copy(original, True, False).Shape())
    location = TopLoc_Location()
    surface = BRep_Tool.Surface_s(face, location)
    low_u, high_u, low_v, high_v = BRepGProp_Face(face).Bounds()
    if not all(math.isfinite(value) for value in (low_u, high_u, low_v, high_v)):
        raise _unresolved_integral()
    source = _span_source(face, cancelled=cancelled)
    if source is None:
        raise _unresolved_integral()
    (u_source, u_axis), (v_source, v_axis) = source
    u_values = _split_values(u_source, u_axis, low_u, high_u, subdivisions, cancelled=cancelled)
    v_values = _split_values(v_source, v_axis, low_v, high_v, subdivisions, cancelled=cancelled)
    if (u_values.Length() - 1) * (v_values.Length() - 1) > _MAX_PATCHES:
        raise _unresolved_integral()
    if isinstance(untrimmed_surface(surface, cancelled=cancelled), _segmentable()):
        splitter = ShapeUpgrade_SplitSurface()
        splitter.Init(surface, low_u, high_u, low_v, high_v)
        splitter.SetUSplitValues(u_values)
        splitter.SetVSplitValues(v_values)
        splitter.Perform(True)
        grid = splitter.ResSurfaces()
    else:
        grid = _trimmed_grid(surface, u_values, v_values, cancelled=cancelled)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    composer = ShapeFix_ComposeShell()
    composer.Init(grid, location, face, _REPARAMETRIZATION_PRECISION)
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
    patches = _faces(result, cancelled=cancelled)
    if not patches:
        raise _unresolved_integral()
    return patches


def _segmentable() -> tuple[type, ...]:
    """Die Trägerarten, die ``ShapeUpgrade_SplitSurface`` selbst in Stücke schneidet."""
    from OCP.Geom import Geom_BezierSurface, Geom_BSplineSurface

    return (Geom_BSplineSurface, Geom_BezierSurface)


def _trimmed_grid(
    surface: Any, u_values: Any, v_values: Any, *, cancelled: CancelToken | None = None
) -> Any:
    """Das Teilungsgitter aus rechteckig getrimmten Sichten desselben Trägers.

    ``ShapeUpgrade_SplitSurface`` schneidet eine Extrusion **nicht** in der
    Richtung ihrer Basiskurve und eine Drehfläche nicht in der ihres Profils:
    Jedes Stück behielt dort die volle Spanne, ``ShapeFix_ComposeShell`` ließ
    die doppelten fallen, und die Teilung deckte die Hälfte, dann ein
    Viertel der Fläche. Die Leiter kam so nie zusammen und fiel in den
    Python-Rückfall — an erhabener Schrift auf einem exakten Quader 75 s für
    ein Volumen (gemessen 22.09.2026). Getrimmte Sichten behalten die
    Parametrisierung des Trägers, also passen die Parameterkurven der Fläche
    unverändert; eine Extrusion und eine Drehfläche aus Bézier-Kurven decken
    mit 4 und 16 Stücken ihre Fläche auf 10⁻¹².
    """
    from OCP.collections import Array1_double, HArray2_Geom_Surface
    from OCP.Geom import Geom_RectangularTrimmedSurface
    from OCP.ShapeExtend import ShapeExtend_CompositeSurface

    us = [float(u_values.Value(index)) for index in range(1, u_values.Length() + 1)]
    vs = [float(v_values.Value(index)) for index in range(1, v_values.Length() + 1)]
    patches = HArray2_Geom_Surface(1, len(us) - 1, 1, len(vs) - 1)
    for row, (first_u, last_u) in enumerate(pairwise(us), start=1):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        for column, (first_v, last_v) in enumerate(pairwise(vs), start=1):
            view = Geom_RectangularTrimmedSurface(surface, first_u, last_u, first_v, last_v)
            patches.SetValue(row, column, view)
    u_joints, v_joints = Array1_double(1, len(us)), Array1_double(1, len(vs))
    for index, value in enumerate(us, start=1):
        u_joints.SetValue(index, value)
    for index, value in enumerate(vs, start=1):
        v_joints.SetValue(index, value)
    return ShapeExtend_CompositeSurface(patches, u_joints, v_joints)


def _local_copy(shape: Any, origin: Vec3, *, cancelled: CancelToken | None = None) -> Any:
    """Eine private Kopie, in den lokalen Bezugsrahmen verschoben — Geometrie, nicht Lage.

    Bereits die rationalen Ableitungen müssen lokal entstehen: Erst nach der
    Auswertung große Weltkoordinaten abzuziehen verliert die Stellen, die die
    Quadratur für ihre Fehlerschranke braucht (Halbkugel bei 5·10⁶ mm in
    ``tests/test_brep_surfaces.py``). Über ``BRepTools_Modifier`` statt des
    Transformationsbuilders: Der ist der Vertrag von ``edit.transformed``, und
    was ihn dort stellvertretend beschädigt, darf ein Maß des Eingangs nicht
    mitbeschädigen.
    """
    import numpy as np
    from OCP.BRepTools import BRepTools_Modifier, BRepTools_TrsfModification
    from OCP.gp import gp_Trsf, gp_Vec

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(*(-np.asarray(origin))))
    modifier = BRepTools_Modifier(shape, BRepTools_TrsfModification(transform))
    if not modifier.IsDone():
        raise _unresolved_integral()
    local = modifier.ModifiedShape(shape)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if local.IsNull():
        raise _unresolved_integral()
    return local


def _shifted(centre: tuple[float, float, float], origin: Vec3) -> Vec3:
    """Der im lokalen Rahmen gerechnete Schwerpunkt, zurück in Weltkoordinaten."""
    return cast(
        Vec3, tuple(float(value + shift) for value, shift in zip(centre, origin, strict=True))
    )


def _oriented_faces(shape: Any, *, cancelled: CancelToken | None = None) -> list[Any]:
    """Die gerichteten Flächen, so oft sie vorkommen — nicht entdoppelt.

    Gemeinsame Wände zweier Körper zählen mit beiden Orientierungen; eine
    Indexkarte fasste die beiden gerichteten Vorkommen zusammen.
    """
    from OCP.TopAbs import TopAbs_FACE, TopAbs_FORWARD, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    faces = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        face = TopoDS.Face(explorer.Current())
        explorer.Next()
        if face.Orientation() in (TopAbs_FORWARD, TopAbs_REVERSED):
            faces.append(face)
    return faces


def _has_edges(face: Any) -> bool:
    """Ob eine Fläche überhaupt Kanten trägt — eine natürlich begrenzte muss es nicht."""
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer

    return bool(TopExp_Explorer(face, TopAbs_EDGE).More())


def _cone_volume(face: Any, *, cancelled: CancelToken | None = None) -> tuple[Any, float]:
    """Das native Kegelvolumen einer Fläche zum lokalen Ursprung samt seinem Fehler.

    OCCTs ``VolumeProperties`` wählt den Bezugspunkt selbst — den groben
    Schwerpunkt der übergebenen Form. An einem Verbund aus Teilflächen wandert
    er mit jeder Teilung, und an einem Körper, dessen Nähte innerhalb seiner
    Toleranz offen stehen, hängt das Volumen am Bezugspunkt: Der M10-Bolzen
    des Korpus (Kantentoleranz 3,5 µm) schwankte damit um 10⁻⁷ zwischen den
    Stufen. Der Bezugspunkt ist deshalb fest — derselbe wie im Python-Rückfall.
    """
    from OCP.BRepGProp import BRepGProp_Domain, BRepGProp_Face, BRepGProp_Vinert
    from OCP.gp import gp_Pnt

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    surface = BRepGProp_Face(face)
    # **Die natürliche Begrenzung geht über ihre Kanten, nicht über den
    # Trägerbereich.** ``BRepGProp_Vinert(Fläche, Punkt, Genauigkeit)`` gab an
    # einer natürlich begrenzten Fläche 0 zurück, mit Fehler 0 — gemessen an
    # einer vollen Kugel und einem vollen Ring (P4.0: ein aus einem Netz
    # gebauter Ring hatte das Volumen 0). Über ``BRepGProp_Domain`` stimmt
    # derselbe Aufruf auf die letzte Stelle. Nur eine Fläche ganz ohne Kanten
    # hat kein Gebiet, und für sie trägt der Aufruf ohne Genauigkeitsvorgabe.
    if surface.NaturalRestriction() and not _has_edges(face):
        inert = BRepGProp_Vinert(surface, gp_Pnt(0.0, 0.0, 0.0))
    else:
        inert = BRepGProp_Vinert(
            surface, BRepGProp_Domain(face), gp_Pnt(0.0, 0.0, 0.0), _PATCH_RELATIVE_ERROR
        )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    mass = float(inert.Mass())
    error = float(inert.GetEpsilon())
    if not math.isfinite(mass) or not math.isfinite(error) or error < 0.0:
        raise _unresolved_integral()
    # Der gemeldete Fehler ist relativ zum Kegelvolumen dieser Fläche; die
    # Summe zählt absolut gegen das ganze Volumen, wie im Python-Rückfall.
    return inert, error * abs(mass)


def _spanned_volume(shape: Any, *, cancelled: CancelToken | None = None) -> MassProperties:
    """Volumen und Schwerpunkt nativ auf dem knotenzerlegten Verbund, mit Leiter.

    Jede Spline-Fläche geht an ihren Knotenspannen geteilt hinein, jede
    analytische ganz; zwei aufeinanderfolgende Teilungen müssen sich in
    Volumen und Schwerpunkt auf ``INTEGRAL_RELATIVE_ERROR`` einigen. Trägt
    keine Fläche Spannen, gibt es nichts zu teilen, und die erste Stufe ist
    das Ergebnis. Gemessen (21.09.2026): genähtes M6-Gewinde 20 ms statt 3 s,
    STEP-Gewinde ``m6_rechts`` 130 ms statt 13,8 s, verrundete
    NurbsConvert-Lochplatte Millisekunden statt 9,8 s — der Zackenkörper mit
    seiner 10⁻⁵ breiten Spanne bleibt exakt.
    """
    from OCP.GProp import GProp_GProps

    if not _oriented_faces(shape, cancelled=cancelled):
        # Eine leere Form hat kein Volumen und keinen Ort — der Aufrufer
        # entscheidet, ob das ein Befund ist (``boolean.NOTHING_LEFT``).
        return MassProperties(0.0, (0.0, 0.0, 0.0), None)
    origin, size = _local_frame(shape, cancelled=cancelled)
    local = _local_copy(shape, origin, cancelled=cancelled)
    faces = _oriented_faces(local, cancelled=cancelled)
    spanned = [_needs_spans(face, cancelled=cancelled) for face in faces]
    levels = _SUBDIVISIONS if any(spanned) else _SUBDIVISIONS[:1]
    before = None
    for subdivisions in levels:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        total = GProp_GProps()
        error = 0.0
        for face, split in zip(faces, spanned, strict=True):
            for part in _patches(face, subdivisions, cancelled=cancelled) if split else (face,):
                inert, absolute = _cone_volume(part, cancelled=cancelled)
                total.Add(inert)
                error += absolute
        mass = float(total.Mass())
        if not math.isfinite(mass) or mass < 0.0 or error > INTEGRAL_RELATIVE_ERROR * mass:
            raise _unresolved_integral()
        centre = total.CentreOfMass()
        measured = MassProperties(
            mass, _shifted((centre.X(), centre.Y(), centre.Z()), origin), None
        )
        if before is None and len(levels) == 1:
            return measured
        if before is not None and _converged(before, measured, size):
            return measured
        before = measured
    raise _unresolved_integral()


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


def _converged(before: MassProperties, after: MassProperties, span: float) -> bool:
    """Fläche/Volumen und Schwerpunkt müssen gemeinsam konvergieren; die Trägheit endlich sein.

    ``span`` ist die Länge, an der der Schwerpunkt gemessen wird — die
    Diagonale der Hülle. Bis zum 21.09.2026 verlangte die Leiter auch von der
    Trägheit Konvergenz auf 10⁻⁹, obwohl niemand sie liest: Die erste Fläche
    des M10-Gewindes fiel daran in den Python-Rückfall (5,1 s statt
    Millisekunden bei 3·10⁻¹⁰ Unterschied in der Fläche).
    """
    import numpy as np

    mass = abs(after.mass)
    if not math.isfinite(mass) or mass <= 0.0 or not math.isfinite(span) or span <= 0.0:
        return False
    if not math.isclose(before.mass, after.mass, rel_tol=INTEGRAL_RELATIVE_ERROR, abs_tol=0.0):
        return False
    if after.inertia is not None and not np.isfinite(np.asarray(after.inertia)).all():
        return False
    return math.dist(before.centre, after.centre) <= INTEGRAL_RELATIVE_ERROR * span


def _spanned_surface(face: Any, *, cancelled: CancelToken | None = None) -> MassProperties:
    """Der schnelle native Weg mit belegter Konvergenz zwischen Unterteilungen."""
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    origin, size = _local_frame(face, cancelled=cancelled)
    local = _local_copy(face, origin, cancelled=cancelled)
    before = None
    for subdivisions in _SUBDIVISIONS:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        for patch in _patches(local, subdivisions, cancelled=cancelled):
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            builder.Add(compound, patch)
        measured = _integrate(compound, "surface", cancelled=cancelled)
        total = MassProperties(measured.mass, _shifted(measured.centre, origin), measured.inertia)
        if before is not None and _converged(before, total, size):
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
    inneren U-Integration. Eine private, nur verschobene Arbeitsfläche
    erhält die ursprünglichen Trimmkurven und ihre Parameter.
    """
    import numpy as np
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepGProp import BRepGProp_Domain, BRepGProp_Face
    from OCP.gp import gp_Pnt, gp_Pnt2d, gp_Trsf, gp_Vec, gp_Vec2d
    from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from scipy.integrate import quad_vec

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # Bereits die rationalen Ableitungen müssen lokal entstehen. Erst nach
    # der Auswertung große Weltkoordinaten abzuziehen verliert die Stellen,
    # die die Quadratur für ihre unveränderte Fehlerschranke benötigt.
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(*(-np.asarray(origin))))
    local = BRepBuilderAPI_Transform(face, transform, True).Shape()
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    forward = TopoDS.Face(local.Oriented(TopAbs_FORWARD))
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
        x, y, z = np.array((point.X(), point.Y(), point.Z())) / size
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


def estimated_volume(shape: Any) -> float:
    """Ein grobes Volumen für eine Plausibilitätsfrage — **nie** eine Kennzahl des Körpers.

    OCCTs Gauß-Weg mit fester Stützstellenzahl, ohne Knotenzerlegung und ohne
    Fehlerschranke, nur über geschlossene Schalen. Für „ist hier mehr als der
    Kern?" genügt das: An genähten Gewindebolzen lag er 10⁻⁷ neben dem
    Integral auf ``INTEGRAL_RELATIVE_ERROR`` und war 30- bis 45-mal schneller
    (M3 x 0,5 x 60: 79 ms gegen 3,5 s, gemessen 22.09.2026). Er wird weder
    gecacht noch veröffentlicht; wer ein Volumen zeigt oder vergleicht, nimmt
    :func:`properties`.
    """
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props, True)
    return float(props.Mass())


def properties(
    shape: Any, kind: Literal["volume", "surface"], *, cancelled: CancelToken | None = None
) -> MassProperties:
    """Geprüfte Maße; schwierige Trimmungen rechnen auf den ursprünglichen Randkurven.

    Volumen: der knotenzerlegte Verbund mit Leiter (:func:`_spanned_volume`),
    danach der Python-Rückfall. Fläche: analytische Flächen im nativen
    Standardweg, Spline-Flächen je Fläche über die Leiter, der Rückfall je
    Fläche — und ein Körper ohne Spline-Fläche in einem einzigen nativen Aufruf.
    """
    try:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if kind == "volume":
            try:
                return _spanned_volume(shape, cancelled=cancelled)
            except OperationCancelled:
                raise
            except PROGRAMMING_ERRORS:
                raise
            except Exception:
                return _uv_volume(shape, cancelled=cancelled)
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
                pass
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
