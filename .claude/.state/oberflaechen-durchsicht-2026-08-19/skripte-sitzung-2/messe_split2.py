from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\rober\Documents\Solidon")

from PySide6.QtWidgets import QLabel  # noqa: E402

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

bar = window.split_bar
layout = bar.layout()
print("Leiste:", bar.size().toTuple(), "sizeHint", bar.sizeHint().toTuple())
print("Layout:", type(layout).__name__, "margins", layout.contentsMargins().top(),
      layout.contentsMargins().bottom(), "spacing", layout.spacing())
for index in range(layout.count()):
    item = layout.itemAt(index)
    widget = item.widget()
    if widget is None:
        print(f"  {index}: {type(item).__name__} min {item.minimumSize().toTuple()}")
        continue
    print(
        f"  {index}: {type(widget).__name__:14s} y={widget.mapTo(bar, widget.rect().topLeft()).y():4d}"
        f" x={widget.mapTo(bar, widget.rect().topLeft()).x():4d} w={widget.width():4d}"
        f" h={widget.height():4d} hint={widget.sizeHint().height():4d}"
        f" min={widget.minimumSizeHint().height():4d} sichtbar={widget.isVisible()}"
        f" text={(widget.text() if hasattr(widget, 'text') else '')[:44]!r}"
    )
    if isinstance(widget, QLabel):
        print(
            f"       wordWrap={widget.wordWrap()} Farbe={widget.palette().windowText().color().name()}"
            f" Ausrichtung={int(widget.alignment())}"
        )
window.close()
