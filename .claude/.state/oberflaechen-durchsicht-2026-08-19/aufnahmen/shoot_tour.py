"""Der Weg eines Demonutzers: Beispiel öffnen, Tour ansehen, Schritte gehen.

Aufgenommen wird vom Bildschirm, weil der Viewport über OpenGL zeichnet und in
kein ``grab()`` kommt.
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

    load_operations()
    app, window = build_application([])
    window.resize(1440, 900)
    window.show()
    window.raise_()
    window.activateWindow()
    wait(app, 1.0)
    screen = QApplication.primaryScreen()

    directory = examples.directory()
    files = sorted(directory.glob("*.p3d"))
    print(f"{len(files)} Beispielprojekte in {directory}")
    for entry in files:
        print("  ", entry.name)

    # Weg 1 — das Beispiel, das ein Erstnutzer zuerst anklickt.
    wanted = [f for f in files if f.name.startswith("weg1")]
    first = wanted[0] if wanted else (files[0] if files else None)
    if first is None:
        print("keine Beispiele — nichts aufzunehmen")
        return 1

    window.open_path(first)
    window.session.wait_for_idle()
    wait(app, 2.0, rounds=200)
    screen.grabWindow(window.winId()).save(str(OUT / "tour-1-offen.png"))
    print(f"geöffnet: {first.name}")

    # Welcher Reiter liegt rechts oben? Die Tour soll es sein.
    tabs = window.right
    if tabs is not None:
        names = [tabs.tabText(index) for index in range(tabs.count())]
        print("Reiter rechts:", names, "aktiv:", tabs.tabText(tabs.currentIndex()))
    else:
        print("kein Reiterfeld gefunden")

    # Die Tour sichtbar machen, falls sie nicht vorn liegt.
    if tabs is not None:
        for index in range(tabs.count()):
            if "our" in tabs.tabText(index):
                tabs.setCurrentIndex(index)
                break
        wait(app, 0.8)
        screen.grabWindow(window.winId()).save(str(OUT / "tour-2-reiter.png"))

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
