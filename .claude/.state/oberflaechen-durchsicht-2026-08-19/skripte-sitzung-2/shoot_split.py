"""Der Trennen-Bereich als Bild, bei derselben Fenstergröße wie die alte Aufnahme."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent / "viewport"

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.ui.app import build_application  # noqa: E402


def settle(app, seconds: float = 1.0) -> None:
    for _ in range(80):
        app.processEvents()
    time.sleep(seconds)
    for _ in range(80):
        app.processEvents()


app, window = build_application([])
window.resize(1440, 900)
window.move(0, 0)
window.show()
settle(app)
window.open_path(Path(r"C:\Users\rober\Documents\Solidon\app\examples\weg1-halterung-anpassen.p3d"))
window.session.wait_for_idle()
settle(app, 2.0)
window.tools.toggle("split")
settle(app, 1.0)

screen = QApplication.primaryScreen()
shot = screen.grabWindow(window.winId())
shot.save(str(OUT / "30-trennen.png"))
strip = window.tools
top = strip.mapTo(window, strip.rect().topLeft())
print("Werkzeugkarte:", strip.size().toTuple(), "bei", top.toTuple())
print("Leiste:", window.split_bar.size().toTuple(), "sizeHint", window.split_bar.sizeHint().toTuple())
shot.copy(top.x() - 10, top.y() - 10, strip.width() + 20, strip.height() + 20).save(
    str(OUT / "31-trennen-karte.png")
)
window.close()
