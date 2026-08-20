"""Trägt der Kontaktschatten etwas zum Bild bei? Zwei Bilder, ein Unterschied."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent / "viewport"
sys.path.insert(0, str(ROOT))


def settle(app, seconds: float = 1.2) -> None:
    for _ in range(120):
        app.processEvents()
    time.sleep(seconds)
    for _ in range(120):
        app.processEvents()


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.core.bootstrap import load_operations
    from app.ui.app import build_application

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
    viewport = window.viewport
    box = viewport.geometry()
    corner = viewport.mapTo(window, box.topLeft())

    def shot(name: str) -> None:
        image = screen.grabWindow(window.winId())
        image.copy(corner.x(), corner.y(), box.width(), box.height()).save(str(OUT / name))

    print("Schattenaktoren:", len(viewport._shadow_actors))
    shot("10-mit-schatten.png")
    for actor in viewport._shadow_actors:
        actor.SetVisibility(False)
    viewport.plotter.render()
    settle(app, 1.0)
    shot("11-ohne-schatten.png")
    for actor in viewport._shadow_actors:
        actor.SetVisibility(True)
    viewport.plotter.render()
    print("fertig")
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
