"""Geschlossene Querschnitte und echte Normalversätze für gezeichnete Gegenstücke."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from shapely.geometry import Polygon

from app.core.errors import ValidationError
from app.core.geom.sketch_solid import MAX_OUTLINE_POINTS, outline_points
from app.core.units import EPS_GEOM, MAX_FACET_SAG
from app.i18n import _

if TYPE_CHECKING:
    from app.core.sketch.profile import Profile


def _invalid() -> ValidationError:
    return ValidationError(
        field="sketch",
        constraint="closed_contour",
        detail=_(
            "Die Kontur ist nicht eindeutig geschlossen oder enthält überlappende Ränder. "
            "Korrigieren Sie die Zeichnung."
        ),
    )


def section_of(
    profile: Profile,
    *,
    max_sag: float = MAX_FACET_SAG,
    check_cancelled: Callable[[], None] | None = None,
) -> Any:
    """Gefüllter Umriss einschließlich aller Löcher; keine Reparatur oder Richtungsannahme.

    Ein Loch im Loch ist wieder Material. Jede Verschachtelung wird zuerst
    als gültige Kontur geprüft; ein fremder Innenring darf nicht durch eine
    Füllregel zu einer neuen Außenkomponente umgedeutet werden.
    """
    import manifold3d

    count = 0

    def build(current: Profile, points: list[tuple[float, float]] | None = None) -> Any:
        nonlocal count
        if points is None:
            points = outline_points(current, max_sag=max_sag, check_cancelled=check_cancelled)
        holes = [
            outline_points(hole, max_sag=max_sag, check_cancelled=check_cancelled)
            for hole in current.holes
        ]
        count += len(points)
        if count > MAX_OUTLINE_POINTS or len(points) < 3 or any(len(hole) < 3 for hole in holes):
            raise _invalid()
        polygon = Polygon(points, holes)
        if not polygon.is_valid or polygon.area <= EPS_GEOM**2:
            raise _invalid()
        result = manifold3d.CrossSection([points], manifold3d.FillRule.EvenOdd)
        for hole, sampled in zip(current.holes, holes, strict=True):
            result -= build(hole, sampled)
        return result

    return build(profile)


def polygons_of(section: Any) -> tuple[Polygon, ...]:
    """Alle gefüllten Komponenten mit ihren Löchern; ein leerer Querschnitt liefert ().

    Manifold zerlegt in je einen Außenring samt seinen Innenringen. Der
    flächenmäßig größte Ring ist der Außenring; die Reihenfolge oder
    Laufrichtung der ausgegebenen Pfade trägt hier keine Bedeutung.
    """
    result = []
    for component in section.decompose():
        paths = component.to_polygons()
        if not paths:
            continue
        outer = max(range(len(paths)), key=lambda index: abs(Polygon(paths[index]).area))
        polygon = Polygon(
            paths[outer], [ring for index, ring in enumerate(paths) if index != outer]
        )
        if not polygon.is_valid or polygon.area <= EPS_GEOM**2:
            raise _invalid()
        result.append(polygon)
    return tuple(sorted(result, key=lambda polygon: (*polygon.bounds, polygon.area)))


def offset_section(
    section: Any,
    distance: float,
    *,
    max_sag: float = MAX_FACET_SAG,
    check_cancelled: Callable[[], None] | None = None,
) -> Any:
    """Runder Normalversatz, positiv wächst Material und verkleinert Innenlöcher.

    Aufspaltung und Kollaps bleiben als mehrere oder keine Komponente
    erhalten; ob eine Familie das erlaubt, entscheidet ihr Aufrufer. Nur
    numerische Clipper-Restkanten unter EPS_GEOM werden entfernt. Fertigungs-
    spiel ist die Eingabe ``distance`` und wird hier weder ergänzt noch geraten.
    """
    if check_cancelled is not None:
        check_cancelled()
    if not math.isfinite(distance) or not math.isfinite(max_sag) or max_sag <= 0.0:
        raise _invalid()
    radius = abs(distance)
    if radius <= EPS_GEOM:
        return section
    sag = min(max_sag, MAX_FACET_SAG)
    angle = 4.0 * math.asin(math.sqrt(min(1.0, sag / (2.0 * radius))))
    if angle <= 0.0:
        raise _invalid()
    steps = max(4, 4 * math.ceil(math.tau / angle / 4.0))
    if steps > MAX_OUTLINE_POINTS:
        raise _invalid()
    moved = section.offset(distance, circular_segments=steps).simplify(EPS_GEOM)
    if check_cancelled is not None:
        check_cancelled()
    if sum(len(path) for path in moved.to_polygons()) > MAX_OUTLINE_POINTS:
        raise _invalid()
    return moved
