"""Die gemeinsame Druckfläche für Anordnung, Orientierung und Ausgabe (§29).

Alle Konturen liegen in Solidons Weltkoordinaten: XY relativ zur nominellen
Bettmitte, Z ab Bett. Nomineller Bauraum, fester Druckbereich und der separat
übergebene Auftragsrand sind drei verschiedene Größen.
"""

from __future__ import annotations

import math

import numpy as np
from shapely import get_coordinates, make_valid, polygons, union_all
from shapely.affinity import translate
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry

from app.core.errors import CHOOSE_PRINTER, ValidationError
from app.core.types import BoundingBox, Mesh, PrinterProfile, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _


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


def footprint(mesh: Mesh) -> BaseGeometry:
    """Die tatsächliche XY-Projektion, einschließlich ausgesparter Bereiche.

    Eine Hüllbox oder konvexe Hülle würde einen Ring um eine Sperrzone ablehnen,
    obwohl kein Material darin liegt. Deshalb werden projizierte Dreiecke
    vereinigt. Der Rechteck-Schnelltest in ``fits_on_bed`` spart diese Arbeit,
    solange schon die ganze Hüllbox freigegeben ist.
    """
    from app.core.geom.mesh import as_mesh_data

    triangles = np.asarray(as_mesh_data(mesh).raw.triangles, dtype=float)[:, :, :2]
    # Nahezu senkrechte Flächen werden bei einer Drehung zu Dreiecken mit
    # wenigen Rundungsbits Breite. Ihr ungerasterter Overlay kann eine
    # Seitenzuordnung verlieren. Entartete Projektionen bleiben als Linien
    # erhalten; echte dünne Flächen werden nicht nach einem Flächenschwellwert
    # verworfen. Das vorhandene geometrische Präzisionsmaß gilt nur für den
    # Overlay, das Eingangsnetz und seine Koordinaten bleiben unangetastet.
    projected = make_valid(polygons(triangles))
    return union_all(projected, grid_size=EPS_GEOM)


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


def fits_xy(mesh: Mesh, area: BaseGeometry) -> bool:
    """Liegt die gesamte Projektion innerhalb dieser freigegebenen Fläche?"""
    bounds = mesh.bounds
    if not _bounds_inside(bounds, area):
        return False
    allowed = area.buffer(EPS_GEOM, join_style="mitre")
    rectangle = box(*bounds.minimum[:2], *bounds.maximum[:2])
    return bool(allowed.covers(rectangle) or allowed.covers(footprint(mesh)))


def fits_on_bed(mesh: Mesh, printer: PrinterProfile, *, margin: float = 0.0) -> bool:
    """Prüft die aktuelle Lage gegen tatsächliche Fläche und Höhe des Profils."""
    bounds = mesh.bounds
    return (
        bounds.minimum[2] >= -EPS_GEOM
        and bounds.maximum[2] <= printable_height(printer) + EPS_GEOM
        and fits_xy(mesh, printable_area(printer, margin=margin))
    )


def placement_offset(mesh: Mesh, printer: PrinterProfile, *, margin: float = 0.0) -> Vec3 | None:
    """Setzt aufs Bett und sucht bei Bedarf die nächste passende XY-Lage.

    Die bisherige XY-Lage gewinnt, solange sie passt. Sonst werden Bettmitte,
    Rand- und Sperrkonturkanten deterministisch geprüft. Keine mögliche
    Verschiebung aus dieser Kandidatenmenge ergibt ``None``; das wird niemals
    als Nachweis ausgegeben, dass eine andere Drehung unmöglich wäre.
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
    shape = None
    if _bounds_inside(bounds, area):
        if allowed.covers(rectangle):
            return (0.0, 0.0, z)
        # Ein Ring kann schon richtig um eine Sperrfläche liegen, obwohl
        # sein Rechteck sie überdeckt. Diese Lage gewinnt vor jeder Bewegung.
        shape = footprint(mesh)
        if allowed.covers(shape):
            return (0.0, 0.0, z)
    # Die nächste Lage des Rechtecks innerhalb der Bettbounds ist ein
    # günstiger Kandidat. Passt bereits das ganze Rechteck, ist eine Union
    # sämtlicher Dreiecke unnötig, auch bei sehr großen Netzen.
    x = min(max(0.0, left - bounds.minimum[0]), right - bounds.maximum[0])
    y = min(max(0.0, front - bounds.minimum[1]), back - bounds.maximum[1])
    if allowed.covers(translate(rectangle, xoff=x, yoff=y)):
        return (x, y, z)
    if shape is None:
        shape = footprint(mesh)
    coordinates = get_coordinates(area)
    xs = {0.0, -bounds.centre[0], float(area.centroid.x - shape.centroid.x)}
    ys = {0.0, -bounds.centre[1], float(area.centroid.y - shape.centroid.y)}
    for x, y in coordinates:
        xs.update((float(x - bounds.minimum[0]), float(x - bounds.maximum[0])))
        ys.update((float(y - bounds.minimum[1]), float(y - bounds.maximum[1])))
    offsets = sorted(((x, y) for x in xs for y in ys), key=lambda p: (p[0] ** 2 + p[1] ** 2, p))
    for x, y in offsets:
        if allowed.covers(translate(shape, xoff=x, yoff=y)):
            return (x, y, z)
    return None
