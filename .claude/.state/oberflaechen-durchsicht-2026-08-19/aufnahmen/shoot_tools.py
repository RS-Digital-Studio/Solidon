"""Die acht Werkzeuge der Zeile, jedes einmal geöffnet und aufgenommen.

Ein Demonutzer klickt sie als Erstes an; im Handbuch kommt keines vor.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

KEYS = ("section", "measure", "transform", "analysis", "layers", "explode", "split", "paint")


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

    load_operations()
    app, window = build_application([])
    window.resize(1440, 900)
    window.show()
    window.raise_()
    window.activateWindow()
    wait(app, 0.8)
    screen = QApplication.primaryScreen()

    window.open_path(examples.directory() / "weg1-halterung-anpassen.p3d")
    window.session.wait_for_idle()
    wait(app, 1.5, rounds=200)

    # Den Körper auswählen — mehrere Werkzeuge verlangen das.
    item = window.object_tree.tree.topLevelItem(0)
    if item is not None:
        window.object_tree.tree.setCurrentItem(item)
        wait(app, 0.4)

    for key in KEYS:
        window.tools.activate(key)
        wait(app, 1.4, rounds=160)
        screen.grabWindow(window.winId()).save(str(OUT / f"tool-{key}.png"))
        print(f"{key}: aktiv={window.tools.active()}")
        window.tools.close_tool()
        wait(app, 0.5)

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
