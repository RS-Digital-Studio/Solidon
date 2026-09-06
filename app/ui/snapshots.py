"""Ansichten der Szene für den Agenten (§26.3) — zwei kleine Bilder.

Ein bildfähiges Modell bekommt neben dem Steckbrief zwei gerenderte Ansichten:
schräg von oben und von oben. Sie entstehen ohne Fenster im eigenen Renderer
(über :func:`app.ui.render.factory.make_renderer`, also im selben, den die
Ansicht zeichnet), damit sie auch dann kommen, wenn das Fenster gerade etwas
anderes zeigt.

Kurzlebig ist Absicht: Ein Renderer, den jemand über seinen Zweck hinaus
festhält, hält Grafikpuffer und Fenster mit — er wird im ``finally``
geschlossen, gleich welchen Weg der Lauf nimmt.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

from app.core.geom.mesh import as_mesh_data
from app.core.types import Scene
from app.i18n import tr
from app.ui.render.api import CameraPose, SurfaceStyle

#: Kantenmaß der Ansichten. Ein Steckbrief-Begleitbild, kein Poster — jede
#: Ansicht kostet Eingabe-Token, und zwei kleine sagen mehr als ein großes.
VIEW_SIZE = (480, 360)


def scene_views(scene: Scene) -> tuple[tuple[str, bytes], ...]:
    """Zwei PNG-Ansichten der Szene mit Beschriftung — oder nichts bei leerer Szene."""
    import numpy as np

    from app.ui.render.factory import make_renderer

    if not scene.objects:
        return ()

    view = make_renderer(offscreen=True, size=VIEW_SIZE)
    try:
        bounds: list[tuple[float, float, float, float, float, float]] = []
        for object_id, entry in scene.objects.items():
            raw = as_mesh_data(entry.mesh).raw
            item = view.add_surface(
                np.asarray(raw.vertices, dtype=float),
                np.asarray(raw.faces, dtype=np.int64),
                name=f"object:{object_id}",
                style=SurfaceStyle(),
            )
            bounds.append(item.bounds())
        low = [min(box[axis * 2] for box in bounds) for axis in range(3)]
        high = [max(box[axis * 2 + 1] for box in bounds) for axis in range(3)]
        centre = tuple((low[axis] + high[axis]) / 2.0 for axis in range(3))
        span = max(high[axis] - low[axis] for axis in range(3)) or 1.0
        whole = (low[0], high[0], low[1], high[1], low[2], high[2])
        # Schräg von oben, wie die Isometrie der Anwendung.
        view.set_camera_pose(
            CameraPose(
                (centre[0] + span, centre[1] - span, centre[2] + span * 0.8),
                (centre[0], centre[1], centre[2]),
                (0.0, 0.0, 1.0),
            )
        )
        view.reset_camera(whole)
        three_quarter = _png(view.screenshot())
        view.set_camera_pose(
            CameraPose(
                (centre[0], centre[1], centre[2] + span * 2.0),
                (centre[0], centre[1], centre[2]),
                (0.0, 1.0, 0.0),
            )
        )
        view.reset_camera(whole)
        top = _png(view.screenshot())
        return (
            (tr("Ansicht von schräg oben"), three_quarter),
            (tr("Ansicht von oben"), top),
        )
    finally:
        view.close()


def _png(image: Any) -> bytes:
    """Ein Bild ``(h, w, 3)`` als PNG-Bytes."""
    height, width = image.shape[0], image.shape[1]
    # QImage borgt den Puffer, es kopiert ihn nicht — die Variable hält ihn
    # am Leben, bis das PNG geschrieben ist.
    raw = image.tobytes()
    picture = QImage(raw, width, height, width * 3, QImage.Format.Format_RGB888)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    # Zur Laufzeit nimmt PySide hier eine Zeichenkette; die Stubs behaupten
    # bytes — der Laufzeit wird geglaubt, den Stubs widersprochen.
    picture.save(buffer, "PNG")  # type: ignore[call-overload]
    return bytes(buffer.data().data())
