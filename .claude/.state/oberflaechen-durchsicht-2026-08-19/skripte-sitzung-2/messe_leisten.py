"""Alle acht Werkzeugleisten am laufenden Fenster ausmessen (echte Plattform)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\rober\Documents\Solidon")

from PySide6.QtWidgets import QLabel  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.ui.app import build_application  # noqa: E402


def settle(app, seconds: float = 0.6) -> None:
    for _ in range(60):
        app.processEvents()
    time.sleep(seconds)
    for _ in range(60):
        app.processEvents()


app, window = build_application([])
window.resize(1440, 900)
window.move(0, 0)
window.show()
settle(app)
window.open_path(Path(r"C:\Users\rober\Documents\Solidon\app\examples\weg1-halterung-anpassen.p3d"))
window.session.wait_for_idle()
settle(app, 1.5)

for key in ("section", "measure", "transform", "analysis", "layers", "explode", "split", "paint"):
    try:
        window.tools.toggle(key)
    except KeyError:
        print(f"{key}: kein solches Werkzeug")
        continue
    settle(app, 0.4)
    tool = window.tools._tools.get(key)
    if tool is None:
        print(f"{key}: keine Leiste")
        continue
    bar = tool.bar
    card = window.tools
    tight = 0
    for label in bar.findChildren(QLabel):
        if label.isVisibleTo(bar) and label.width() <= 2 and label.text().strip():
            tight += 1
    print(
        f"{key:10s} Karte {card.height():4d}  Leiste {bar.width():4d}x{bar.height():4d}"
        f"  hint {bar.sizeHint().height():4d}  min {bar.minimumSizeHint().height():4d}"
        f"  unsichtbare Beschriftungen: {tight}"
    )
    window.tools.toggle(key)
    settle(app, 0.2)
window.close()
