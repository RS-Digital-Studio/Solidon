"""Die gemeinsame Druckfläche für Anordnung, Orientierung und Ausgabe (§29).

Alle Konturen liegen in Solidons Weltkoordinaten: XY relativ zur nominellen
Bettmitte, Z ab Bett. Nomineller Bauraum, fester Druckbereich und der separat
übergebene Auftragsrand sind drei verschiedene Größen.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import numpy as np
from shapely import (
    covers,
    get_coordinates,
    intersects_xy,
    make_valid,
    polygons,
    prepare,
    union_all,
)
from shapely.affinity import translate
from shapely.geometry import MultiPoint, Polygon, box
from shapely.geometry.base import BaseGeometry

from app.core.errors import CHOOSE_PRINTER, ValidationError
from app.core.types import BoundingBox, Mesh, PrinterProfile, PrintSettings, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

#: Rasterweite der Größenmessung um Z; die Absage berücksichtigt deren Schranke.
SIZE_ANGLE_STEP_DEGREES: Final = 1


def printable_height(printer: PrinterProfile) -> float:
    """Die freigegebene Höhe des Profils, unabhängig von der nominellen Höhe."""
    height = (
        printer.build_volume[2] if printer.printable_height is None else printer.printable_height
    )
    if not math.isfinite(height) or height <= 0.0:
        raise ValidationError(
            field="printable_height",
            detail=_("Die Druckhöhe ist ungültig. Prüfen Sie das Druckerprofil."),
            suggestions=(CHOOSE_PRINTER,),
        )
    return height


def _contour(points: tuple[tuple[float, float], ...]) -> Polygon:
    """Weist fehlerhafte Profilkonturen zurück, statt eine Fläche zu erfinden."""
    finite = all(math.isfinite(value) for point in points for value in point)
    polygon = Polygon(points) if len(points) >= 3 and finite else Polygon()
    if polygon.is_empty or not polygon.is_valid or not finite:
        raise ValidationError(
            field="printable_area",
            detail=_("Die Druckkontur ist ungültig. Prüfen Sie das Druckerprofil."),
            suggestions=(CHOOSE_PRINTER,),
        )
    return polygon


def printable_area(printer: PrinterProfile, *, margin: float = 0.0) -> BaseGeometry:
    """Freigegebene XY-Fläche ohne Sperrzonen und mit dem gewählten Auftragsrand.

    Eine ausdrückliche Kontur kann vom nominellen Rechteck abweichen: Manche
    Herstellerprofile erlauben mehr als die nominell beworbene Druckfläche.
    Nur ohne Kontur gilt das definierte Rechteck aus ``build_volume``.
    """
    width, depth, _height = printer.build_volume
    area: BaseGeometry = (
        _contour(printer.printable_area)
        if printer.printable_area
        else box(-width / 2.0, -depth / 2.0, width / 2.0, depth / 2.0)
    )
    for contour in printer.bed_exclusions:
        area = area.difference(_contour(contour))
    return area.buffer(-max(0.0, margin), join_style="mitre") if margin > 0.0 else area


def machine_shift(printer: PrinterProfile) -> tuple[float, float]:
    """Wohin Solidons Bettmitte in den Koordinaten der Maschine fällt (§29).

    Die eine Umrechnung für alles, was Maschinenkoordinaten schreibt oder
    liest — Platzierung in der 3MF, Bettform und Ursprung der Übergabe,
    Gegenprobe an der Druckdatei: ``Maschine = Solidon + machine_shift``.
    Ohne ``bed_origin`` misst die Maschine von der vorderen linken Ecke, und
    die Verschiebung ist das halbe Bett; an einem Bett um den Ursprung ist sie
    null. Bis RM-424 stand an jeder dieser Stellen das halbe Bett, und am
    Dremel 3D45 lag ein Würfel aus der Bettmitte am hinteren Rand.
    """
    if printer.bed_origin is None:
        width, depth, _height = printer.build_volume
        return width / 2.0, depth / 2.0
    across, along = printer.bed_origin
    if not (math.isfinite(across) and math.isfinite(along)):
        raise ValidationError(
            field="bed_origin",
            detail=_("Der Nullpunkt des Betts ist ungültig. Prüfen Sie das Druckerprofil."),
            suggestions=(CHOOSE_PRINTER,),
        )
    return 0.0 - across, 0.0 - along


def footprint(mesh: Mesh) -> BaseGeometry:
    """Die tatsächliche XY-Projektion, einschließlich ausgesparter Bereiche.

    Eine Hüllbox oder konvexe Hülle würde einen Ring um eine Sperrzone ablehnen,
    obwohl kein Material darin liegt. Deshalb werden projizierte Dreiecke
    vereinigt — für die Anordnung, die die Form braucht. Die Frage, ob ein
    Körper passt, stellt :class:`_Projection` ohne Vereinigung.
    """
    from app.core.geom.mesh import as_mesh_data

    body = as_mesh_data(mesh).raw
    if len(body.faces) and body.is_watertight and body.is_winding_consistent:
        outline = _outline_of_closed(body)
        if outline is not None:
            return outline
    triangles = np.asarray(body.triangles, dtype=float)[:, :, :2]
    # Nahezu senkrechte Flächen werden bei einer Drehung zu Dreiecken mit
    # wenigen Rundungsbits Breite. Ihr ungerasterter Overlay kann eine
    # Seitenzuordnung verlieren. Entartete Projektionen bleiben als Linien
    # erhalten; echte dünne Flächen werden nicht nach einem Flächenschwellwert
    # verworfen. Das vorhandene geometrische Präzisionsmaß gilt nur für den
    # Overlay, das Eingangsnetz und seine Koordinaten bleiben unangetastet.
    projected = make_valid(polygons(triangles))
    return union_all(projected, grid_size=EPS_GEOM)


def _outline_of_closed(body: Any) -> BaseGeometry | None:
    """Die Projektion eines geschlossenen Netzes über seine Umrisskanten.

    **Vereinigt wurde jedes Dreieck, und das kostete Sekunden.** Ein
    Besteckeinsatz mit 59 744 Dreiecken brauchte 4,2 s für eine Projektion,
    und die Orientierungssuche fragt sie für jede Lage, deren Hüllbox eine
    Sperrzone des Betts schneidet: neunmal, 47 der 57 Sekunden einer Suche
    (23.09.2026).

    Bei einem geschlossenen, einheitlich umlaufenden Netz ist die Projektion
    die Vereinigung der **nach oben** zeigenden Dreiecke — über jedem Punkt
    des Schattens liegt als oberstes ein solches. Zwei nach oben zeigende
    Nachbarn liegen in der Projektion auf verschiedenen Seiten ihrer
    gemeinsamen Kante (beide laufen gegen den Uhrzeigersinn um, die Kante
    einmal hin und einmal zurück); der Rand des Schattens liegt also auf den
    **Umrisskanten**, deren einer Nachbar nach oben zeigt und der andere
    nicht. Diese wenigen Kanten werden verknotet und zu Flächen geschlossen,
    und eine Fläche gehört zum Schatten, wenn ein Punkt in ihr unter einem
    nach oben zeigenden Dreieck liegt. Dieselbe Fläche wie die Vereinigung,
    gerechnet über den Rand statt über das Innere.

    ``None``, wenn es keine Umrisskante gibt (ein entartetes Netz) — dann
    bleibt die Vereinigung aller Dreiecke.
    """
    import shapely

    triangles = np.asarray(body.triangles, dtype=float)
    # Senkrechte Wände liegen nach einer Drehung um Rundungsbits neben der
    # Senkrechten, und dann zeigte jede zweite „nach oben": Eine Kumiko-Schale
    # von der Seite trug so 44 088 Umrisskanten, die fast alle nur Wände
    # nachzeichneten, und das Verknoten kostete 6 s. Eine Wand, die um weniger
    # als ``EPS_GEOM`` im Bogenmaß kippt, wirft keinen Schatten, den die
    # Vereinigung je gesehen hätte.
    up = np.asarray(body.face_normals, dtype=float)[:, 2] > EPS_GEOM
    if not up.any():
        return None
    edges = np.asarray(body.faces_unique_edges, dtype=np.int64)[up].ravel()
    counts = np.bincount(edges, minlength=len(body.edges_unique))
    rim = np.flatnonzero(counts == 1)
    if not len(rim):
        return None
    ends = np.asarray(body.vertices, dtype=float)[
        np.asarray(body.edges_unique, dtype=np.int64)[rim]
    ][:, :, :2]
    lines = shapely.linestrings(ends)
    # Verknotet auf dem Raster, das auch die Vereinigung benutzte: Kanten, die
    # sich in der Projektion kreuzen oder berühren, bekommen dort einen Knoten.
    noded = union_all(lines, grid_size=EPS_GEOM)
    faces = shapely.get_parts(shapely.polygonize(shapely.get_parts(noded)))
    if not len(faces):
        return None
    covering = polygons(triangles[up][:, :, :2])
    probes = shapely.point_on_surface(faces)
    inside, _covered = shapely.STRtree(covering).query(probes, predicate="intersects")
    kept = faces[np.unique(inside)]
    if not len(kept):
        return None
    # Die Flächen einer Polygonisierung überlappen nicht — sie sind eine
    # Überdeckung, und die vereinigt GEOS ohne Überlagerung: an 18 131 Flächen
    # 0,12 s statt 1,43.
    merged = shapely.coverage_union_all(kept)
    return merged if merged.is_valid else make_valid(union_all(kept, grid_size=EPS_GEOM))


def _bounds_inside(bounds: BoundingBox, area: BaseGeometry) -> bool:
    """Außerhalb der Flächenbounds kann auch die tatsächliche Projektion nicht passen."""
    if area.is_empty:
        return False
    left, front, right, back = area.bounds
    return bool(
        bounds.minimum[0] >= left - EPS_GEOM
        and bounds.minimum[1] >= front - EPS_GEOM
        and bounds.maximum[0] <= right + EPS_GEOM
        and bounds.maximum[1] <= back + EPS_GEOM
    )


class _Projection:
    """Die XY-Projektion eines Körpers, befragt von billig nach teuer.

    **Die Vereinigung aller projizierten Dreiecke ist für die Frage „passt
    er?" nicht nötig** (Review 23.09.2026, RM-190). Die Kegel des
    Bowlingspiels aus den Downloads stehen in der 3MF neben der Platte; ihre
    nächste Randlage ist beim Centauri Carbon 2 die Sperrecke, und
    ``placement_offset`` vereinigte dort die 83 878 Dreiecke eines Kegels —
    7,8 s, und *Druckoptimal ausrichten* fragte das für jede seiner 215 Lagen:
    zwanzig Minuten für einen Kegel.

    Die Projektion liegt in der freigegebenen Fläche, wenn **jedes** ihrer
    Dreiecke darin liegt — das ist dieselbe Menge, nur ohne Überlagerung. Und
    die meisten Lagen sind schon vorher entschieden, exakt: Deckt die Fläche
    die konvexe Hülle der Ecken, deckt sie auch jedes Dreieck darin; liegt
    eine Ecke außerhalb, liegt ihr Dreieck außerhalb. Erst dazwischen — ein
    Ring um eine Sperrfläche, eine Ecke der Sperrzone in der Hülle — wird je
    Dreieck gefragt, an 83 878 Dreiecken in einer Viertelsekunde für den
    ersten Aufbau und Millisekunden je weitere Lage.
    """

    def __init__(
        self,
        mesh: Mesh,
        allowed: BaseGeometry,
        outline: Callable[[], np.ndarray] | None = None,
    ) -> None:
        self._mesh = mesh
        self._allowed = allowed
        self._outline = outline
        self._body: Any = None
        self._points: np.ndarray | None = None
        self._reach: tuple[np.ndarray, np.ndarray] | None = None
        self._hull: BaseGeometry | None = None
        self._triangles: np.ndarray | None = None

    def _raw(self) -> Any:
        """Das Netz, einmal geholt — ein bewegter Körper wird erst hier bewegt."""
        if self._body is None:
            from app.core.geom.mesh import as_mesh_data

            self._body = as_mesh_data(self._mesh).raw
        return self._body

    @property
    def points(self) -> np.ndarray:
        """Die projizierten Ecken, die ein Dreieck benutzt."""
        if self._points is None:
            body = self._raw()
            vertices = np.asarray(body.vertices, dtype=float)
            used = np.zeros(len(vertices), dtype=bool)
            used[np.asarray(body.faces, dtype=np.int64).ravel()] = True
            self._points = vertices[used, :2]
        return self._points

    @property
    def reach(self) -> tuple[np.ndarray, np.ndarray]:
        """Die Grenzen der Projektion — aus der Hüllbox, die nur benutzte Ecken
        zählt (``MeshData.bounds``), ohne das Netz anzufassen."""
        if self._reach is None:
            bounds = self._mesh.bounds
            self._reach = (
                np.asarray(bounds.minimum[:2], dtype=float),
                np.asarray(bounds.maximum[:2], dtype=float),
            )
        return self._reach

    @property
    def hull(self) -> BaseGeometry:
        """Die konvexe Hülle der Projektion — sie enthält jedes Dreieck.

        Über Qhull in der Ebene statt über ``MultiPoint.convex_hull``: an den
        42 000 Ecken eines Kegels 5 statt 43 ms, und das je Lage. Eine
        Projektion ohne Fläche — eine senkrechte Wand von der Seite — ist keine
        Hülle für Qhull; dann rechnet GEOS sie als Linie.
        """
        if self._hull is None:
            from scipy.spatial import ConvexHull, QhullError

            points = self.points if self._outline is None else self._outline()
            try:
                self._hull = Polygon(points[ConvexHull(points).vertices])
            except QhullError, ValueError:
                self._hull = MultiPoint(points).convex_hull
        return self._hull

    @property
    def triangles(self) -> np.ndarray:
        """Jedes projizierte Dreieck als Geometrie; eine senkrechte Fläche als Linie."""
        if self._triangles is None:
            corners = np.asarray(self._raw().triangles, dtype=float)[:, :, :2]
            self._triangles = np.asarray(make_valid(polygons(corners)))
        return self._triangles

    def covered(self, x: float = 0.0, y: float = 0.0) -> bool:
        """Liegt die um ``(x, y)`` verschobene Projektion in der freigegebenen Fläche?"""
        if not self._mesh.triangle_count:
            # Wie zuvor: Eine leere Projektion deckt nichts ab (``covers`` mit
            # einer leeren Geometrie ist falsch).
            return False
        left, front, right, back = self._allowed.bounds
        low, high = self.reach
        if low[0] + x < left or low[1] + y < front or high[0] + x > right or high[1] + y > back:
            return False
        if self._allowed.covers(translate(self.hull, xoff=x, yoff=y)):
            return True
        points = self.points
        if not intersects_xy(self._allowed, points[:, 0] + x, points[:, 1] + y).all():
            return False
        # Die Fläche wird zurückgeschoben, nicht jedes Dreieck vorwärts.
        region = translate(self._allowed, xoff=-x, yoff=-y)
        prepare(region)
        return bool(covers(region, self.triangles).all())


def fits_xy(mesh: Mesh, area: BaseGeometry) -> bool:
    """Liegt die gesamte Projektion innerhalb dieser freigegebenen Fläche?"""
    bounds = mesh.bounds
    if not _bounds_inside(bounds, area):
        return False
    allowed = area.buffer(EPS_GEOM, join_style="mitre")
    rectangle = box(*bounds.minimum[:2], *bounds.maximum[:2])
    return bool(allowed.covers(rectangle) or _Projection(mesh, allowed).covered())


def fits_on_bed(mesh: Mesh, printer: PrinterProfile, *, margin: float = 0.0) -> bool:
    """Prüft die aktuelle Lage gegen tatsächliche Fläche und Höhe des Profils."""
    bounds = mesh.bounds
    return (
        bounds.minimum[2] >= -EPS_GEOM
        and bounds.maximum[2] <= printable_height(printer) + EPS_GEOM
        and fits_xy(mesh, printable_area(printer, margin=margin))
    )


def placement_offset(
    mesh: Mesh,
    printer: PrinterProfile,
    *,
    margin: float = 0.0,
    outline: Callable[[], np.ndarray] | None = None,
) -> Vec3 | None:
    """Setzt aufs Bett und sucht bei Bedarf die nächste passende XY-Lage.

    Die bisherige XY-Lage gewinnt, solange sie passt. Sonst werden Bettmitte,
    Rand- und Sperrkonturkanten deterministisch geprüft. Keine mögliche
    Verschiebung aus dieser Kandidatenmenge ergibt ``None``; das wird niemals
    als Nachweis ausgegeben, dass eine andere Drehung unmöglich wäre.

    ``outline`` liefert, wenn der Aufrufer sie kennt, Punkte in XY, deren
    konvexe Hülle die der Projektion ist — die äußersten Ecken eines bewegten
    Körpers (``orient.extreme_points``). Dann braucht die Hülle nicht jede
    Ecke. Gefragt wird erst, wenn das Rechteck nicht reicht; passt es gleich,
    kostet der Umriss nichts.
    """
    bounds = mesh.bounds
    if bounds.size[2] > printable_height(printer) + EPS_GEOM:
        return None
    area = printable_area(printer, margin=margin)
    if area.is_empty:
        return None
    left, front, right, back = area.bounds
    if bounds.size[0] > right - left + EPS_GEOM or bounds.size[1] > back - front + EPS_GEOM:
        return None
    z = -bounds.minimum[2]
    allowed = area.buffer(EPS_GEOM, join_style="mitre")
    rectangle = box(*bounds.minimum[:2], *bounds.maximum[:2])
    projection = _Projection(mesh, allowed, outline)
    if _bounds_inside(bounds, area):
        if allowed.covers(rectangle):
            return (0.0, 0.0, z)
        # Ein Ring kann schon richtig um eine Sperrfläche liegen, obwohl
        # sein Rechteck sie überdeckt. Diese Lage gewinnt vor jeder Bewegung.
        if projection.covered():
            return (0.0, 0.0, z)
    # Die nächste Lage des Rechtecks innerhalb der Bettbounds ist ein
    # günstiger Kandidat. Passt bereits das ganze Rechteck, ist eine Union
    # sämtlicher Dreiecke unnötig, auch bei sehr großen Netzen.
    x = min(max(0.0, left - bounds.minimum[0]), right - bounds.maximum[0])
    y = min(max(0.0, front - bounds.minimum[1]), back - bounds.maximum[1])
    if allowed.covers(translate(rectangle, xoff=x, yoff=y)):
        return (x, y, z)
    coordinates = get_coordinates(area)
    # Die Mitte der konvexen Hülle, nicht die der Vereinigung: Sie ist ohne
    # Vereinigung zu haben, und für einen konvexen oder symmetrischen Körper
    # ist es dieselbe. Ein Kandidat für die Bettmitte, keine Zusage.
    middle = projection.hull.centroid
    xs = {0.0, -bounds.centre[0], float(area.centroid.x - middle.x)}
    ys = {0.0, -bounds.centre[1], float(area.centroid.y - middle.y)}
    for x, y in coordinates:
        xs.update((float(x - bounds.minimum[0]), float(x - bounds.maximum[0])))
        ys.update((float(y - bounds.minimum[1]), float(y - bounds.maximum[1])))
    offsets = sorted(((x, y) for x in xs for y in ys), key=lambda p: (p[0] ** 2 + p[1] ** 2, p))
    for x, y in offsets:
        # Das Rechteck zuerst: Passt es, passt die Projektion darin auch.
        if allowed.covers(translate(rectangle, xoff=x, yoff=y)) or projection.covered(x, y):
            return (x, y, z)
    return None


def size_excess(mesh: Mesh, printer: PrinterProfile) -> float:
    """Gemessener Überstand über den Bauraum im Winkelraster, in mm.

    Die Frage vor dem Slicen (KUNDE-09): Ein Körper **neben** dem Bett ist mit
    *Auf dem Bett anordnen* erledigt, und ein langer Stab, der nur schräg auf
    das Bett passt, legt der Slicer selbst so (gemessen am ElegooSlicer: 270
    auf 40 mm auf 256 mm, ohne ``--arrange 0`` geschnitten). Ein Körper, der
    in **keiner** Drehung passt, scheitert dagegen in jedem Slicer — der
    Laptop-Ständer mit 205 auf 272 mm am Centauri Carbon 2 mit -50 und
    „found error". Gezählt wird der kleinste Überstand über alle Drehungen
    in Schritten von einem Grad, am Hüllrechteck der konvexen Hülle gegen das
    Rechteck der Druckfläche; die Höhe zählt ohne Drehung.

    Eine Messung für den Bericht, keine Geometrie: Die Drehung darf mit den
    Winkelfunktionen der Plattform rechnen (``.claude/rules/kern.md``, RM-187).
    Passt das Hüllrechteck, der Körper aber wegen einer Sperrzone nirgends,
    kommt der kleinste positive Wert zurück (:data:`EPS_GEOM`) — dort gibt es
    kein Maß, sondern eine erfolglose Platzierungsprobe. Für eine harte
    Größenabsage muss :func:`size_excess_uncertainty` abgezogen werden;
    das Winkelraster kann eine tatsächlich passende Drehung verfehlen.
    """
    from app.core.geom.mesh import as_mesh_data

    if placement_offset(mesh, printer) is not None:
        return 0.0
    bounds = mesh.bounds
    height = float(bounds.size[2]) - printable_height(printer)
    left, front, right, back = printable_area(printer).bounds
    width, depth = right - left, back - front
    points = np.asarray(as_mesh_data(mesh).raw.vertices, dtype=float)[:, :2]
    flat = _turned_overhang(MultiPoint(points).convex_hull, width, depth)
    if max(flat, height) > EPS_GEOM:
        return max(flat, height)
    # Er passt in einer Drehung. Liegt er achsparallel schon im Rechteck und
    # findet trotzdem keinen Platz, steht eine Sperrzone im Weg; sonst dreht
    # ihn der Slicer beim Anordnen selbst.
    square = bounds.size[0] <= width + EPS_GEOM and bounds.size[1] <= depth + EPS_GEOM
    return EPS_GEOM if square else 0.0


def _turned_overhang(hull: BaseGeometry, width: float, depth: float) -> float:
    """Der kleinste Überstand einer Hülle über ein Rechteck ``width`` mal ``depth``
    über alle Drehungen im Winkelraster, in mm; negativ heißt so viel Luft auf
    der knapperen Achse. Eine Messung wie :func:`size_excess`."""
    from shapely.affinity import rotate

    least = float("inf")
    for degrees in range(0, 90, SIZE_ANGLE_STEP_DEGREES):
        low_x, low_y, high_x, high_y = rotate(hull, degrees, origin="centroid").bounds
        least = min(
            least,
            max(high_x - low_x - width, high_y - low_y - depth),
            max(high_x - low_x - depth, high_y - low_y - width),
        )
    return least


def free_margin(points: np.ndarray, printer: PrinterProfile) -> float:
    """Wie breit ein Rand rundum um diesen Umriss höchstens sein darf, damit
    Umriss und Rand in einer Drehung noch auf die Druckfläche passen, in mm.

    ``points`` sind Punkte in XY, deren konvexe Hülle die der Projektion ist.
    Negativ heißt: Schon der Umriss passt nicht. Die Waschschüssel aus dem
    Korpus (240 auf 200 mm) hat auf 220 auf 220 mm schräg gelegt 0,15 mm —
    kein Brim, kein Skirt, und Creality Print wie OrcaSlicer legten sie gerade
    und lehnten ab (04.10.2026). Gleiches Winkelraster wie :func:`size_excess`.
    """
    left, front, right, back = printable_area(printer).bounds
    hull = MultiPoint(np.asarray(points, dtype=float)[:, :2]).convex_hull
    return -_turned_overhang(hull, right - left, back - front) / 2.0


def rim_room(
    first: np.ndarray, whole: np.ndarray, printer: PrinterProfile, *, around_whole: float = 0.0
) -> float:
    """Wie breit ein Rand um die erste Schicht höchstens sein darf, damit das
    ganze Teil samt ``around_whole`` in einer Drehung noch auf die Druckfläche
    passt, in mm (RM-312).

    Brim und Skirt legt der Slicer um die erste Schicht, nicht um die
    Aufsicht: Ein Tisch auf einem Fuß in der Mitte hat für den Brim viel Platz,
    auch wenn die Platte das Bett fast ausfüllt; eine Schüssel auf Füßen am
    Rand nicht. ``first`` und ``whole`` sind Punkte in XY wie bei
    :func:`free_margin`; beide werden um denselben Punkt gedreht, dann wird je
    Achse verschoben, soweit beide Bedingungen es zulassen. Negativ heißt:
    Schon das Teil passt in keiner Drehung. Gleiches Winkelraster wie
    :func:`size_excess`, eine Messung, keine Geometrie.
    """
    from shapely.affinity import rotate

    left, front, right, back = printable_area(printer).bounds
    first_hull = MultiPoint(np.asarray(first, dtype=float)[:, :2]).convex_hull
    whole_hull = MultiPoint(np.asarray(whole, dtype=float)[:, :2]).convex_hull
    origin = whole_hull.centroid
    best = float("-inf")
    for degrees in range(0, 90, SIZE_ANGLE_STEP_DEGREES):
        whole_bounds = rotate(whole_hull, degrees, origin=origin).bounds
        first_bounds = rotate(first_hull, degrees, origin=origin).bounds
        for width, depth in ((right - left, back - front), (back - front, right - left)):
            rooms = [
                _room_along(
                    (whole_bounds[axis], whole_bounds[axis + 2]),
                    (first_bounds[axis], first_bounds[axis + 2]),
                    length,
                    around_whole,
                )
                for axis, length in ((0, width), (1, depth))
            ]
            best = max(best, min(rooms))
    if best == float("-inf"):
        return free_margin(whole, printer) - around_whole
    return best


def _room_along(
    whole: tuple[float, float], first: tuple[float, float], length: float, around_whole: float
) -> float:
    """Der breiteste Rand um ``first`` auf einer Strecke ``length``, während
    ``whole`` mit ``around_whole`` auf ihr bleibt; ``-inf``, wenn ``whole``
    nicht passt. Aus den vier Grenzen der Verschiebung (Teil und Rand je
    Seite)."""
    if whole[1] - whole[0] + 2.0 * around_whole > length + EPS_GEOM:
        return float("-inf")
    return min(
        (length - (first[1] - first[0])) / 2.0,
        length - around_whole - (whole[1] - first[0]),
        length - around_whole - (first[1] - whole[0]),
    )


def size_excess_uncertainty(mesh: Mesh) -> float:
    """Obere Schranke des XY-Messfehlers aus dem Winkelraster.

    Die Projektionsbreite ändert sich bei Winkelabstand delta höchstens um
    2 D sin(delta/2), D ist der Durchmesser der Projektion. Die XY-Diagonale
    begrenzt D nach oben; die nächste Rasterprobe liegt höchstens einen
    halben Schritt entfernt. Kleine Restüberstände belegen kein Nichtpassen.
    """
    diameter = math.hypot(*mesh.bounds.size[:2])
    return 2.0 * diameter * math.sin(math.radians(SIZE_ANGLE_STEP_DEGREES / 4.0))


#: Die größte Breite, die der Auto-Brim der Orca-Familie wählt, in mm.
#: OrcaSlicer ``Brim.cpp``, ``configBrimWidthByVolumeGroups`` (aus Bambu Studio
#: übernommen, ``BBS``): Die Breite folgt aus Höhe, Flächenträgheit und
#: Wärmelänge der ersten Schicht und wird bei 18 mm gekappt („large brims are
#: omitted"), unabhängig von ``brim_width``. Gemessen in der Slicer-Matrix
#: (RM-312): ElegooSlicer legte am Rack 14,7 mm statt der 5 mm des Profils.
ORCA_AUTO_BRIM_MAX: Final = 18.0


@dataclass(frozen=True, slots=True)
class RimReach:
    """Wie weit die erste Schicht über ein Teil hinausreicht, und woraus."""

    reach: float
    """In mm über die Aufsicht des Teils hinaus — die weiteste der beiden
    unten, für Abstände und Anordnen, wo nur ein Umriss gefragt wird."""
    layer: float = 0.0
    """Über den Umriss der ersten Schicht: Brim und Skirt um ihn (RM-312)."""
    top: float = 0.0
    """Über die Aufsicht: der Stützfuß unter Überhängen und der Skirt um ihn."""
    auto_brim: bool = False
    """Der Auto-Brim der Orca-Familie zählt mit seiner Höchstbreite."""
    support_foot: bool = False
    """Die verbreiterte erste Stützschicht reicht weiter als der Brim."""
    support_foot_unknown: bool = False
    """Stützen sind an, ihre Verbreiterung nennt das Profil nicht."""


def rim_of(
    settings: PrintSettings,
    flavour: str = "other",
    support_foot: float | None = None,
) -> RimReach:
    """Die belegte Außenkante der ersten Schicht um ein Teil (RM-312).

    Von innen nach außen: Brim (bei der Orca-Familie mit ``auto`` bis
    :data:`ORCA_AUTO_BRIM_MAX`) oder, mit Stützen, die verbreiterte erste
    Stützschicht (``support_foot``, ``manufacturer.Foundation.support_foot``),
    je nachdem, was weiter reicht; darum der Skirt mit Abstand und Bahnen.
    Der Skirt zählt bei Haftungsart Skirt und bei Prusa und Orca neben einem
    Brim, solange Solidon die Haftungsart nicht schreibt — dann drucken sie
    beides, wie das Profil es sagt; schreibt Solidon eine Art, nullt die
    Übergabe die übrigen (``handover._only_chosen_adhesion``). Cura druckt
    nur eine Art. Die eine Rechnung für Übergabe (``writer.rim_reach``,
    ``check_adhesion_on_bed``) und Druckvorschläge (``advise``: Brim und Skirt
    nur, wo das Bett Platz lässt).

    **Zwei Umrisse, zwei Reichweiten** (RM-312): Brim und Skirt liegen um die
    erste Schicht (``layer``), der Stützfuß unter den Überhängen und damit um
    die Aufsicht (``top``). Gemessen von der Aufsicht allein bekam ein Teil,
    das oben breiter ist als am Fuß, eine Warnung, obwohl der Rand auf dem Bett
    blieb (garden-hose-holder am MINI, Waschschüssel am Kobra 2).
    """
    adhesion = settings.adhesion
    auto = adhesion.kind == "auto" and flavour == "orca"
    if auto:
        band = ORCA_AUTO_BRIM_MAX + max(0.0, adhesion.brim_gap)
    elif adhesion.kind in ("brim", "auto", "raft"):
        band = adhesion.brim_width
    else:
        band = 0.0
    supported = settings.support.style != "none"
    footing = support_foot if supported and support_foot is not None else 0.0
    written = "adhesion.kind" in settings.chosen or "adhesion.kind" in settings.accepted
    skirt = adhesion.skirt_loops > 0 and (
        adhesion.kind == "skirt"
        or (flavour in ("prusa", "orca") and not written and adhesion.kind != "raft")
    )
    around = 0.0
    if skirt:
        line = settings.layers.first_layer_line_width or settings.layers.line_width
        around = adhesion.skirt_distance + adhesion.skirt_loops * line
    layer = band + around if band > 0.0 or skirt else 0.0
    top = footing + around if footing > 0.0 else 0.0
    return RimReach(
        max(band, footing) + around if layer or top else 0.0,
        layer=layer,
        top=top,
        auto_brim=auto,
        support_foot=footing > band,
        support_foot_unknown=supported and support_foot is None,
    )
