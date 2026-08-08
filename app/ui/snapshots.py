"""Ansichten für den Agenten (Bauplan §23, Konzept Agent-Vertiefung 3.5).

§23 verlangt die gerenderten Ansichten neben dem Steckbrief: „das Loch vorne
links" ist im Text mehrdeutig, im Bild nicht. Der Kern rendert keine
Rasterbilder — seine Projektion ist SVG (``app/core/drawing``), und die
Modelle nehmen PNG. Also rendert die Oberfläche: ein eigener
Offscreen-Plotter, klein und kurzlebig, der den sichtbaren Viewport nicht
anfasst.

Kurzlebig ist Absicht: VTK-Objekte, die jemand über ihr Fenster hinaus
festhält, reißen den Abriss am Prozessende mit — der Plotter wird im
``finally`` geschlossen, gleich welchen Weg der Lauf nimmt.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

from app.core.geom.mesh import as_mesh_data
from app.core.log import get_logger
from app.core.types import Scene
from app.i18n import tr

_log = get_logger(__name__)

#: Kantenmaß der Ansichten. Ein Steckbrief-Begleitbild, kein Poster — jede
#: Ansicht kostet Eingabe-Token, und zwei kleine sagen mehr als ein großes.
VIEW_SIZE = (480, 360)


def scene_views(scene: Scene) -> tuple[tuple[str, bytes], ...]:
    """Zwei beschriftete PNG-Ansichten der Szene: schräg oben und von oben.

    Wirft, was das Rendern wirft — der Aufrufer entscheidet, dass Bilder
    Zugabe sind und ein Fehlschlag den Zug nicht kostet (Leitprinzip 8).
    """
    import pyvista as pv

    if not scene.objects:
        return ()

    plotter = pv.Plotter(off_screen=True, window_size=list(VIEW_SIZE))
    try:
        for entry in scene.objects.values():
            plotter.add_mesh(pv.wrap(as_mesh_data(entry.mesh).raw))
        # pyvistas Methoden sind zur Laufzeit gewrappt; die Stubs kennen den
        # Descriptor nicht und verlangen ein self, das längst gebunden ist.
        plotter.view_isometric()  # type: ignore[call-arg]
        three_quarter = _png(plotter.screenshot(return_img=True))
        plotter.view_xy()  # type: ignore[call-arg]
        top = _png(plotter.screenshot(return_img=True))
        return (
            (tr("Ansicht von schräg oben"), three_quarter),
            (tr("Ansicht von oben"), top),
        )
    finally:
        plotter.close()


def _png(image: Any) -> bytes:
    """Ein RGB-Array als PNG-Bytes — über Qt, das die Oberfläche ohnehin hat."""
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
