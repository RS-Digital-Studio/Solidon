"""Die leere Ansicht: passt die Kamera auf den Bauraum, oder passt sie nicht?

Aufgenommen wird dreimal — direkt nach *Neues Projekt*, nach einem zweiten
``reset_camera`` und mit einem Quader darin. Wenn das zweite Bild richtig
aussieht und das erste nicht, ist der Zeitpunkt des Einpassens das Problem.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def wait(app, seconds: float = 1.0, rounds: int = 80) -> None:
    for _ in range(rounds):
        app.processEvents()
    time.sleep(seconds)
    for _ in range(rounds):
        app.processEvents()


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.core.bootstrap import load_operations
    from app.core.scene import OperationDraft
    from app.ui.app import build_application

    load_operations()
    app, window = build_application([])
    window.resize(1280, 820)
    window.show()
    window.raise_()
    window.activateWindow()
    wait(app, 1.0)

    screen = QApplication.primaryScreen()
    view = window.viewport

    window.start_empty()
    wait(app, 1.5)
    screen.grabWindow(window.winId()).save(str(OUT / "cam-1-neu.png"))
    print("Kamera nach Neues Projekt:", view.plotter.camera_position if view.plotter else "kein Plotter")

    view.reset_camera()
    view._draw()
    wait(app, 0.6)
    screen.grabWindow(window.winId()).save(str(OUT / "cam-2-nochmal.png"))
    print("Kamera nach erneutem Einpassen:", view.plotter.camera_position if view.plotter else "-")

    # Ein Quader hinein.
    window.session.apply("Quader", [OperationDraft(op="create_box", params={})])
    wait(app, 3.0, rounds=200)
    screen.grabWindow(window.winId()).save(str(OUT / "cam-3-quader.png"))
    print("mit Quader aufgenommen")

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
