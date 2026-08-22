"""Das echte Fenster vom Bildschirm aufnehmen — OpenGL kommt in kein grab().

Dazu die Menüleiste im leeren Zustand auszählen: der Hinweis im Objektbaum
nennt ein Menü, und es muss dasselbe geben.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def report_menus(window, label: str) -> None:
    bar = window.menuBar()
    names = [action.text() for action in bar.actions()]
    print(f"{label}: {len(names)} Menues: {names}")
    for action in bar.actions():
        menu = action.menu()
        if menu is None:
            continue
        rows = [entry.text() for entry in menu.actions() if not entry.isSeparator()]
        enabled = sum(1 for entry in menu.actions() if entry.isEnabled() and not entry.isSeparator())
        print(f"    {action.text():14} {len(rows):2} Zeilen, {enabled} bedienbar, sichtbar={action.isVisible()}")


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.core.bootstrap import load_operations
    from app.ui.app import build_application

    # Wie main(): erst das Register, dann das Fenster. Ohne das baut die
    # Menueleiste aus einem leeren Register und sieht aus wie ein Fehler.
    load_operations()
    app, window = build_application([])
    window.show()
    window.raise_()
    window.activateWindow()
    for _ in range(80):
        app.processEvents()
    time.sleep(1.0)
    for _ in range(80):
        app.processEvents()

    report_menus(window, "Startbildschirm")

    screen = QApplication.primaryScreen()
    screen.grabWindow(window.winId()).save(str(OUT / "real-start.png"))

    window.start_empty()
    for _ in range(80):
        app.processEvents()
    time.sleep(1.5)
    for _ in range(120):
        app.processEvents()

    report_menus(window, "leeres Projekt")
    screen.grabWindow(window.winId()).save(str(OUT / "real-leer.png"))

    # Und mit einem Körper darin: der Quader über die Operation.
    from app.core.registry import REGISTRY

    if REGISTRY.has("create_box"):
        window.session.run_op("create_box", {})
        for _ in range(200):
            app.processEvents()
        time.sleep(2.0)
        for _ in range(200):
            app.processEvents()
        screen.grabWindow(window.winId()).save(str(OUT / "real-quader.png"))
        print("Quader aufgenommen")

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
