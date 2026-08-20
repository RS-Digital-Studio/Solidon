"""Welche Schattenrichtung ist überhaupt zu sehen? Gemessen, nicht geraten.

Für jede Kandidatenrichtung ein Bild mit und ohne die Schattenaktoren, und
gezählt wird, wie viele Bildpunkte der Schatten wirklich abdunkelt.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent / "viewport"
sys.path.insert(0, str(ROOT))

CANDIDATES = [
    (0.54, 0.18),  # der Stand vor der Änderung
    (0.30, 0.55),  # mehr zur Seite
    (0.10, 0.62),  # fast nur zur Seite
    (-0.30, 0.55),  # zur Seite und auf den Betrachter zu
    (-0.45, 0.35),  # überwiegend nach vorn
]


def settle(app, seconds: float = 0.8) -> None:
    for _ in range(80):
        app.processEvents()
    time.sleep(seconds)
    for _ in range(80):
        app.processEvents()


def darker(first: str, second: str, region: tuple[int, int, int, int]) -> int:
    from PySide6.QtGui import QImage

    a = QImage(first)
    b = QImage(second)
    x0, y0, x1, y1 = region
    count = 0
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            pa = a.pixelColor(x, y)
            pb = b.pixelColor(x, y)
            step = (pb.red() - pa.red()) + (pb.green() - pa.green()) + (pb.blue() - pa.blue())
            if step > 12:
                count += 1
    return count


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.core.bootstrap import load_operations
    from app.ui import viewport as viewport_module
    from app.ui.app import build_application

    OUT.mkdir(parents=True, exist_ok=True)
    load_operations()
    app, window = build_application([])
    window.resize(1900, 1030)
    window.move(0, 0)
    window.show()
    window.raise_()
    window.activateWindow()
    settle(app)
    window.open_path(ROOT / "app" / "examples" / "gehaeuse-mit-bausteinen.p3d")
    window.session.wait_for_idle()
    settle(app, 2.5)

    screen = QApplication.primaryScreen()
    view = window.viewport
    box = view.geometry()
    corner = view.mapTo(window, box.topLeft())
    region = (290, 50, 1570, 860)

    def shot(name: str) -> str:
        image = screen.grabWindow(window.winId())
        target = OUT / name
        image.copy(corner.x(), corner.y(), box.width(), box.height()).save(str(target))
        return str(target)

    for reach, side in CANDIDATES:
        viewport_module.SHADOW_REACH = reach
        viewport_module.SHADOW_SIDE = side
        view._redraw_shadows()
        settle(app, 0.6)
        with_shadow = shot(f"sweep-{reach}-{side}-mit.png")
        for actor in view._shadow_actors:
            actor.SetVisibility(False)
        view.plotter.render()
        settle(app, 0.6)
        without = shot(f"sweep-{reach}-{side}-ohne.png")
        for actor in view._shadow_actors:
            actor.SetVisibility(True)
        view.plotter.render()
        print(f"reach={reach:5.2f} side={side:5.2f} -> {darker(with_shadow, without, region)} Punkte")

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
