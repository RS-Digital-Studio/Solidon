"""Dasselbe Fenster im hellen Thema — dort wohnen die Kontrastfehler.

Und der Skizzeneditor, weil das Raster dort in beiden Themen aus derselben
ungesetzten Palettenrolle kommt.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def wait(app, seconds: float = 1.0, rounds: int = 120) -> None:
    for _ in range(rounds):
        app.processEvents()
    time.sleep(seconds)
    for _ in range(rounds):
        app.processEvents()


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.core import examples
    from app.core.bootstrap import load_operations
    from app.ui.app import build_application
    from app.ui.theme import apply_theme

    load_operations()
    app, window = build_application([])
    apply_theme(app, "light")
    window.viewport.set_theme("light") if hasattr(window.viewport, "set_theme") else None
    window.resize(1440, 900)
    window.show()
    window.raise_()
    window.activateWindow()
    wait(app, 0.8)
    screen = QApplication.primaryScreen()

    window.open_path(examples.directory() / "dose-mit-deckel.p3d")
    window.session.wait_for_idle()
    wait(app, 2.0, rounds=200)
    screen.grabWindow(window.winId()).save(str(OUT / "light-fenster.png"))
    print("helles Fenster aufgenommen")

    # Der Skizzeneditor im hellen Thema.
    from app.core.sketch import shapes
    from app.core.sketch.serialize import sketch_to_text
    from app.ui.sketch_editor import SketchPanel

    panel = SketchPanel(sketch_to_text(shapes.rectangle(120.0, 60.0)))
    panel.canvas.insert_shape(shapes.circle(40.0))
    panel.resize(980, 620)
    panel.show()
    panel.raise_()
    wait(app, 1.0)
    screen.grabWindow(panel.winId()).save(str(OUT / "light-skizze.png"))
    panel.close()

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
