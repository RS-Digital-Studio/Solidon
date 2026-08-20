"""Der leere Viewport, ein sehr kleines und ein sehr großes Teil."""

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

    OUT.mkdir(parents=True, exist_ok=True)
    load_operations()
    app, window = build_application([])
    window.resize(1900, 1030)
    window.move(0, 0)
    window.show()
    window.raise_()
    window.activateWindow()
    settle(app)

    screen = QApplication.primaryScreen()
    view = window.viewport
    box = view.geometry()
    corner = view.mapTo(window, box.topLeft())

    def shot(name: str) -> None:
        # Die Geometrie **je Aufnahme**: vor dem ersten Projekt liegt der
        # Startbildschirm vorn, und der Viewport ist dort winzig.
        here = view.geometry()
        at = view.mapTo(window, here.topLeft())
        image = screen.grabWindow(window.winId())
        image.copy(at.x(), at.y(), here.width(), here.height()).save(str(OUT / name))
        print(f"aufgenommen: {name} ({here.width()}x{here.height()})")

    window.start_empty()
    window.session.wait_for_idle()
    settle(app, 1.5)
    shot("20-leer.png")

    from app.core.scene.history import OperationDraft

    window.session.apply(
        "Winziges Teil",
        [OperationDraft(op="create_box", params={"width": 2.0, "depth": 2.0, "height": 1.0})],
    )
    window.session.wait_for_idle()
    settle(app, 2.0)
    shot("21-winzig.png")

    window.session.apply(
        "Großes Teil",
        [OperationDraft(op="create_box", params={"width": 400.0, "depth": 300.0, "height": 250.0})],
    )
    window.session.wait_for_idle()
    settle(app, 2.5)
    shot("22-riesig.png")

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
