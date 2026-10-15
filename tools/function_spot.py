"""Die bearbeitete Stelle einer Handlung am ganzen Körper im Ergebnisbild (E4, FD-169).

E4 verlangt: Die bearbeitete Stelle — bei einer Handlung am ganzen Körper der
Körper — bleibt vom Auswahlzustand bis zum Ergebnisbild ohne Kamerabewegung des
Kunden ganz im Bild, und kein Dialog verdeckt sie. An Merkmal und Kante misst
``FunctionFlow.spot`` vor dem Übernehmen den Punkt der Stelle. Eine Handlung
ohne gewählte Stelle — *Auf das Bett setzen*, *Druckoptimal ausrichten* — hatte
keine Messung: ``spot`` blieb leer, und die Oberseite nach dem Hub stand
unbemerkt außerhalb des Kamerarands (Abweichung 19, M-E4).

:func:`body_spot` misst sie im Ergebnisbild: die Körper, deren Netz sich mit
dem Übernehmen änderte (:func:`changed_bodies`), ihr Rahmen aus der Projektion
ihrer Hüllpunkte (:func:`body_frame`) und ob er ganz in der Ansicht liegt. Die
Hülle genügt: Die Projektion bildet die Hülle eines Körpers auf die Hülle
seines Bildes ab, der Rahmen ist derselbe. Ohne Bild der Ansicht (offscreen)
ist die Stelle nicht messbar — das steht in ``unmeasured``, nie als „im Bild“.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

#: Warum die Stelle offscreen nicht messbar ist.
WITHOUT_VIEW: Final = "ohne Bild der Ansicht: der Rahmen des Körpers ist nicht messbar"


def changed_bodies(
    before: Mapping[str, Any] | None, applied: Mapping[str, Any] | None
) -> list[str]:
    """Die Körper, deren Netz das Übernehmen änderte oder anlegte — aus den Abdrücken."""
    old = dict((before or {}).get("bodies") or {})
    new = dict((applied or {}).get("bodies") or {})
    return sorted(key for key, digest in new.items() if old.get(key) != digest)


def body_frame(window: Any, object_ids: Sequence[str]) -> dict[str, Any] | None:
    """Rahmen der Körper im Bild und ob er ganz in der Ansicht liegt — ``None`` ohne Bild.

    ``frame`` und ``view`` sind globale Rechtecke ``[x, y, Breite, Höhe]``;
    gerechnet wird in den Bildpunkten des Renderers. Ein Hüllpunkt hinter der
    Kamera oder außerhalb des Tiefenbereichs liegt nicht im Bild.
    """
    import numpy as np
    from PySide6.QtWidgets import QWidget

    from app.core.geom.mesh import as_mesh_data
    from app.ui import guide_targets

    viewport = window.viewport
    renderer = viewport.renderer
    result = window.session.last_result
    if renderer is None or result is None:
        return None
    width, height = renderer.view_size()
    corners: list[tuple[float, float, float, tuple[float, ...]]] = []
    for object_id in object_ids:
        entry = result.scene.objects.get(object_id)
        if entry is None:
            continue
        raw = as_mesh_data(entry.mesh).raw
        shift = np.asarray(viewport.view_offset_of(object_id), dtype=float)
        for vertex in np.asarray(raw.convex_hull.vertices, dtype=float) + shift:
            world = tuple(float(value) for value in vertex)
            x, y, depth = renderer.world_to_display(world)
            corners.append((float(x), float(y), float(depth), world))
    if not corners:
        return None
    xs = [corner[0] for corner in corners]
    ys = [corner[1] for corner in corners]
    inside = (
        min(xs) >= 0.0
        and min(ys) >= 0.0
        and max(xs) <= width
        and max(ys) <= height
        and all(0.0 <= corner[2] <= 1.0 for corner in corners)
    )
    # Global über dieselbe Rechnung wie der Wortschatz (``point_of_world``):
    # die Hüllpunkte, die links, oben, rechts und unten den Rahmen bilden.
    extremes = [min(corners, key=lambda c: c[0]), min(corners, key=lambda c: c[1])]
    extremes += [max(corners, key=lambda c: c[0]), max(corners, key=lambda c: c[1])]
    found = [guide_targets.point_of_world(window, corner[3]) for corner in extremes]
    points = [point for point in found if point is not None]
    if len(points) != len(extremes):
        return None
    left, top = points[0].x(), points[1].y()
    right, bottom = points[2].x(), points[3].y()
    surface = renderer.widget if isinstance(renderer.widget, QWidget) else viewport
    origin = surface.mapToGlobal(surface.rect().topLeft())
    return {
        "frame": [left, top, right - left, bottom - top],
        "view": [origin.x(), origin.y(), surface.width(), surface.height()],
        "inside": bool(inside),
        "bodies": list(object_ids),
    }


def covering_window(window: Any, frame: Sequence[int]) -> str | None:
    """Die Klasse eines offenen Fensters, das über dem Rahmen liegt — ``None``, wenn keins."""
    from PySide6.QtCore import QRect

    from tools.function_surface import windows_to_picture

    area = QRect(*frame)
    for widget in windows_to_picture(window):
        if widget.frameGeometry().intersects(area):
            return type(widget).__name__
    return None


def body_spot(window: Any, data: dict[str, Any]) -> None:
    """Misst nach dem Übernehmen die Stelle einer Handlung am ganzen Körper (E4).

    Nur wo die Zeile keine gewählte Stelle hat (``spot`` leer und ohne Grund in
    ``unmeasured``) und das Übernehmen einen Körper änderte. Schreibt ``spot``
    mit Rahmen, Ansicht, ``inside`` und ``covered_by`` — oder den Grund in
    ``unmeasured``.
    """
    from tools.function_protocol import unmeasured

    if data.get("spot") is not None or "spot" in (data.get("unmeasured") or {}):
        return
    states = data.get("states") or {}
    bodies = changed_bodies(states.get("before"), states.get("applied"))
    if not bodies:
        return
    measured = body_frame(window, bodies)
    if measured is None:
        unmeasured(data, "spot", WITHOUT_VIEW)
        return
    measured["covered_by"] = covering_window(window, measured["frame"])
    data["spot"] = measured
