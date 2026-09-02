"""Aus einem Skizzenumriss ein Netz ziehen — der Weg ohne B-Rep-Kern.

`app.core.brep.profiles.extrude` tut dasselbe mit OpenCASCADE und liefert einen
exakten Körper mit Flächen und Kanten. Das ist der bessere Körper, und er ist
nicht immer zu haben: Der B-Rep-Kern ist optional (§30), und ein eingelesenes
STL hat ohnehin keine Flächen im CAD-Sinn.

**Der Anlass ist ein Kundenweg, kein Aufräumen.** Robert am 30.08.2026: Wer ein
heruntergeladenes Modell öffnet und eine Tasche hineinschneiden will, bekam
„Der gewählte Körper besteht bereits aus festen Dreiecken" — und damit war der
häufigste aller Fälle ausgeschlossen. In Fusion geht das; dort zieht man den
Umriss in den Körper, und was darunter liegt, wird geschnitten.

Gerechnet wird deshalb hier über denselben Weg, den jede andere Mesh-Operation
geht: Umriss zu einem Polygon abtasten, senkrecht aufziehen, auf die Ebene
drehen, und die Boolesche Rückfallkette (:mod:`app.core.geom.boolean`) zieht
ab. Was dabei entsteht, ist ein Netz — mit allem, was das heißt: keine exakten
Kanten, keine nachträglich einzeln bearbeitbaren Flächen. Wer die braucht,
nimmt weiterhin den B-Rep-Weg.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from app.core.types import PlaneFrame
from app.core.units import EPS_GEOM

if TYPE_CHECKING:  # pragma: no cover - nur für die Typprüfung
    from app.core.sketch.profile import Profile

#: Wie fein ein Bogen abgetastet wird — Punkte über den vollen Kreis.
#:
#: Zweiundsiebzig heißt fünf Grad je Schritt, und die Zahl kommt aus der
#: Sehnenhöhe: Bei einer Bohrung von 3 mm Durchmesser weicht die Sehne um
#: 1,4 Mikrometer vom Kreis ab, bei 100 mm um 48 Mikrometer. Beides liegt unter
#: dem, was ein FDM-Drucker auflöst — die Düse ist 400 Mikrometer breit.
#:
#: Feiner wäre teurer ohne Gewinn: Die Zahl der Dreiecke im Werkzeug wächst
#: linear mit ihr, und die Boolesche Differenz rechnet über alle.
ARC_STEPS = 72

#: Wie viele Punkte je Spline-Abschnitt eingeschoben werden.
#:
#: Ein Spline ist hier ein Polygonzug durch seine Stützpunkte, kein
#: interpolierter B-Spline wie im B-Rep-Kern (``_spline_curve`` dort). Der
#: Unterschied ist sichtbar und gewollt benannt: Was dieses Modul liefert, ist
#: ein Netz, und ein Netz nähert ohnehin.
SPLINE_STEPS = 8


def _arc_points(
    start: tuple[float, float],
    via: tuple[float, float],
    end: tuple[float, float],
) -> list[tuple[float, float]]:
    """Ein Kreisbogen durch drei Punkte, abgetastet.

    Liegen die drei fast auf einer Geraden, gibt es keinen Kreis — dann ist die
    Strecke die richtige Antwort und nicht ein Kreis mit riesigem Radius, der
    numerisch auseinanderfliegt.

    **Fallen Anfang und Ende zusammen, ist es ein voller Umlauf** — dieselbe
    Lesart wie in ``sketch.profile.arc_through``: Der Stützpunkt liegt dem
    Anfang gegenüber, die Mitte also zwischen beiden. Ohne diesen Fall gab die
    Determinante unten null, der Umriss kam mit einem einzigen Punkt zurück,
    und eine Tasche aus einem gezeichneten Vollkreis-Bogen endete auf dem
    Netzweg mit „Aus diesem Umriss entsteht kein Körper."
    """
    (ax, ay), (bx, by), (cx, cy) = start, via, end
    if math.dist(start, end) < EPS_GEOM:
        centre = ((ax + bx) / 2.0, (ay + by) / 2.0)
        radius = math.dist(start, via) / 2.0
        if radius < EPS_GEOM:
            return [end]
        first = math.atan2(ay - centre[1], ax - centre[0])
        return [
            (
                centre[0] + radius * math.cos(first + 2.0 * math.pi * index / ARC_STEPS),
                centre[1] + radius * math.sin(first + 2.0 * math.pi * index / ARC_STEPS),
            )
            for index in range(1, ARC_STEPS + 1)
        ]
    # Umkreismittelpunkt über die Determinante; sie ist zugleich das Maß dafür,
    # wie weit die drei Punkte von einer Geraden entfernt sind.
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < EPS_GEOM:
        return [end]
    ux = (
        (ax * ax + ay * ay) * (by - cy)
        + (bx * bx + by * by) * (cy - ay)
        + (cx * cx + cy * cy) * (ay - by)
    ) / d
    uy = (
        (ax * ax + ay * ay) * (cx - bx)
        + (bx * bx + by * by) * (ax - cx)
        + (cx * cx + cy * cy) * (bx - ax)
    ) / d
    radius = math.hypot(ax - ux, ay - uy)
    if radius < EPS_GEOM:
        return [end]

    first = math.atan2(ay - uy, ax - ux)
    middle = math.atan2(by - uy, bx - ux)
    last = math.atan2(cy - uy, cx - ux)

    # **Die Richtung entscheidet der Zwischenpunkt.** Von Anfang zu Ende führen
    # zwei Wege um den Kreis; gemeint ist der, auf dem ``via`` liegt. Ohne diese
    # Prüfung schnitt ein Bogen gelegentlich das Gegenstück heraus.
    def _normalised(angle: float) -> float:
        while angle < 0.0:
            angle += 2.0 * math.pi
        while angle >= 2.0 * math.pi:
            angle -= 2.0 * math.pi
        return angle

    span = _normalised(last - first)
    if _normalised(middle - first) > span:
        span -= 2.0 * math.pi

    steps = max(2, int(abs(span) / (2.0 * math.pi) * ARC_STEPS) + 1)
    points = []
    for index in range(1, steps + 1):
        angle = first + span * index / steps
        points.append((ux + radius * math.cos(angle), uy + radius * math.sin(angle)))
    return points


def outline_points(profile: Profile) -> list[tuple[float, float]]:
    """Den Umriss als geschlossenen Polygonzug — Bögen und Splines abgetastet.

    Ein Kreisprofil hat keine Segmente; es trägt Mittelpunkt und Radius und
    wird hier zu seinem eigenen Polygon.
    """
    if profile.circle is not None:
        (cx, cy), radius = profile.circle
        return [
            (
                cx + radius * math.cos(2.0 * math.pi * index / ARC_STEPS),
                cy + radius * math.sin(2.0 * math.pi * index / ARC_STEPS),
            )
            for index in range(ARC_STEPS)
        ]

    points: list[tuple[float, float]] = []
    for segment in profile.segments:
        if not points:
            points.append(tuple(segment.start))  # type: ignore[arg-type]
        if segment.kind == "line":
            points.append(tuple(segment.end))  # type: ignore[arg-type]
        elif segment.kind == "spline" and segment.through:
            # Der Polygonzug durch die Stützpunkte, jeder Abschnitt unterteilt —
            # das hält die Kanten dicht genug beieinander, dass die Boolesche
            # Operation keine Splitter erzeugt.
            through = [tuple(one) for one in segment.through]
            for at in range(len(through) - 1):
                (x0, y0), (x1, y1) = through[at], through[at + 1]
                for step in range(1, SPLINE_STEPS + 1):
                    share = step / SPLINE_STEPS
                    points.append((x0 + (x1 - x0) * share, y0 + (y1 - y0) * share))
        elif segment.via is not None:
            points.extend(
                _arc_points(
                    tuple(segment.start),  # type: ignore[arg-type]
                    tuple(segment.via),  # type: ignore[arg-type]
                    tuple(segment.end),  # type: ignore[arg-type]
                )
            )
        else:
            points.append(tuple(segment.end))  # type: ignore[arg-type]

    # Der Ring schließt sich; ein doppelter letzter Punkt macht Shapely
    # unglücklich und trimesh eine entartete Kante.
    while len(points) > 1 and math.dist(points[0], points[-1]) < EPS_GEOM:
        points.pop()
    return points


def extrude_profile(profile: Profile, height: float, frame: PlaneFrame) -> Any:
    """Den Umriss auf ``frame`` aufziehen — als Netz.

    Das Gegenstück zu :func:`app.core.brep.profiles.extrude`, nur ohne exakten
    Kern. ``height`` zählt entlang der Ebenen-Normalen; negativ zieht nach
    unten, wie es die Tasche braucht.

    Zurück kommt ein ``trimesh.Trimesh`` — die Rohform, die
    :mod:`app.core.geom.boolean` erwartet. Wer ein ``MeshData`` will, wickelt
    es dort ein, wo die Szene ohnehin bekannt ist.
    """
    import numpy as np
    import trimesh
    from shapely.geometry import Polygon as ShapelyPolygon

    outer = outline_points(profile)
    if len(outer) < 3:
        raise ValueError("ein Umriss aus weniger als drei Punkten trägt keine Fläche")

    holes = []
    for hole in profile.holes or ():
        inner = outline_points(hole)
        if len(inner) >= 3:
            holes.append(inner)

    shape = ShapelyPolygon(outer, holes)
    if not shape.is_valid:
        # ``buffer(0)`` räumt Selbstberührungen aus, die aus der Abtastung
        # entstehen können — dieselbe Behandlung wie in ``prepare.py``.
        shape = shape.buffer(0)
    if shape.is_empty or shape.area < EPS_GEOM:
        raise ValueError("der Umriss schließt keine Fläche ein")

    solid = trimesh.creation.extrude_polygon(shape, height=abs(height))
    if height < 0.0:
        solid.apply_translation((0.0, 0.0, -abs(height)))

    # **Auf die Ebene drehen und schieben.** Die Extrusion liegt in XY bei
    # Z = 0; ``frame`` sagt, wo diese Ebene im Raum liegt. Die Spalten der
    # Drehmatrix sind genau die drei Achsen des Rahmens — dieselbe Rechnung,
    # die ``planes.to_world`` für einen einzelnen Punkt macht.
    turn = np.eye(4)
    turn[:3, 0] = frame.x_axis
    turn[:3, 1] = frame.y_axis
    turn[:3, 2] = frame.normal
    turn[:3, 3] = frame.origin
    solid.apply_transform(turn)
    return solid
