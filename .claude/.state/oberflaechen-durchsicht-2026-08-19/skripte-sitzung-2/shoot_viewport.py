"""Die 3D-Ansicht aufnehmen — mit Körper, mit Auswahl, in beiden Themen.

Aufgenommen wird über ``QScreen.grabWindow(window.winId())``: OpenGL kommt in
kein ``QWidget.grab``, und der Viewport wäre im Bild schwarz. ``load_operations``
läuft vor ``build_application``, sonst baut die Menüleiste aus einem leeren
Register.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent / "viewport"
sys.path.insert(0, str(ROOT))


def settle(app, window, seconds: float = 1.5) -> None:
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
    settle(app, window)

    screen = QApplication.primaryScreen()
    project = ROOT / "app" / "examples" / "gehaeuse-mit-bausteinen.p3d"
    window.open_path(project)
    window.session.wait_for_idle()
    settle(app, window, 2.5)
    screen.grabWindow(window.winId()).save(str(OUT / "01-projekt.png"))
    print("01 aufgenommen")

    # Nur die Ansicht, ohne die Spalten — dafür den mittleren Bereich greifen.
    viewport = window.viewport
    geometry = viewport.geometry()
    top_left = viewport.mapTo(window, geometry.topLeft())
    print("Viewport im Fenster:", top_left.toTuple(), geometry.size().toTuple())
    shot = screen.grabWindow(window.winId())
    shot.copy(top_left.x(), top_left.y(), geometry.width(), geometry.height()).save(
        str(OUT / "02-ansicht.png")
    )

    # Mit gewähltem Körper
    ids = list(window.object_tree.ids()) if hasattr(window.object_tree, "ids") else []
    if ids:
        window.object_tree.select(ids[0])
        settle(app, window, 1.0)
        shot = screen.grabWindow(window.winId())
        shot.copy(top_left.x(), top_left.y(), geometry.width(), geometry.height()).save(
            str(OUT / "03-auswahl.png")
        )
        print("03 aufgenommen, gewählt:", ids[0])

    # Helles Thema
    from app.ui.theme import apply_theme

    apply_theme(app, "light")
    settle(app, window, 1.5)
    shot = screen.grabWindow(window.winId())
    shot.copy(top_left.x(), top_left.y(), geometry.width(), geometry.height()).save(
        str(OUT / "04-ansicht-hell.png")
    )
    print("04 aufgenommen")

    apply_theme(app, "dark")
    settle(app, window, 1.0)
    print("Umgebungsverdeckung:", viewport.ambient_occlusion, "Kontaktschatten:", viewport.contact_shadows)
    print("Verdeckung angewandt:", getattr(viewport, "_occlusion_applied", "?"))
    print("Schattenaktoren:", [name for name in getattr(viewport, "_shadow_actors", {}) ] if hasattr(viewport, "_shadow_actors") else "kein Feld")
    for feld in ("_shadows", "_shadow", "_shadow_items"):
        if hasattr(viewport, feld):
            print("  ", feld, "=", getattr(viewport, feld))

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
