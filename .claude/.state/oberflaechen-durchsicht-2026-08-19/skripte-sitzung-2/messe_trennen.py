"""Der Trennen-Bereich, mit der echten Plattform gemessen.

Offscreen rechnet Qt ohne Schriftfamilien und kommt bei Höhen auf andere Zahlen
— der Fund über den Totraum braucht dieselbe Plattform wie die Abbildungen.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\rober\Documents\Solidon")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
    QWidget,
)

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
window.resize(1900, 1030)
window.move(0, 0)
window.show()
settle(app)
window.open_path(Path(r"C:\Users\rober\Documents\Solidon\app\examples\gehaeuse-mit-bausteinen.p3d"))
window.session.wait_for_idle()
settle(app, 2.0)

# Werkzeug öffnen wie ein Nutzer: über die Werkzeugzeile
window.tools.toggle("split")
settle(app, 1.0)

bar = window.split_bar
print("Trennen-Bereich:", bar.size().toTuple(), "sichtbar:", bar.isVisible())
print("sizeHint:", bar.sizeHint().toTuple(), "minimumSizeHint:", bar.minimumSizeHint().toTuple())
layout = bar.layout()
print("Layout:", type(layout).__name__, "Einträge:", layout.count() if layout else 0)
if layout is not None:
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        if widget is not None:
            top = widget.mapTo(bar, widget.rect().topLeft())
            print(
                f"  {index}: {type(widget).__name__:14s} y={top.y():4d} h={widget.height():3d} "
                f"{(widget.text() if hasattr(widget, 'text') else '')[:40]!r}"
            )
        elif item.layout() is not None:
            print(f"  {index}: {type(item.layout()).__name__} h={item.geometry().height()}")
        else:
            print(f"  {index}: {type(item).__name__} h={item.geometry().height()}")

# Wo endet der obere Inhalt, wo beginnt der untere?
kinds = (QLabel, QPushButton, QCheckBox, QComboBox, QDoubleSpinBox)
spans: list[tuple[int, int, str]] = []
for kind in kinds:
    for child in bar.findChildren(kind):
        if not child.isVisibleTo(bar):
            continue
        top = child.mapTo(bar, child.rect().topLeft()).y()
        spans.append((top, top + child.height(), type(child).__name__))
spans.sort()
for top, bottom, name in spans:
    print(f"    {name:12s} {top:4d} .. {bottom:4d}")
if spans:
    print("größte Lücke:", max(
        (spans[i + 1][0] - spans[i][1], spans[i][2], spans[i + 1][2])
        for i in range(len(spans) - 1)
    ) if len(spans) > 1 else "eine Zeile")
window.close()
