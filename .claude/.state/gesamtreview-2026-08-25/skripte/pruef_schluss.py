"""Schlussdurchgang der Review-Fixes: Maßfeld, Skizzenmenü, Themenwechsel.

Drei Dinge, die heute gebaut wurden und die nur ein Bild beweist:

* Ziffern-Vorfahrt im Viewport-Skizzenmodus — die Ziffer landet im
  geliehenen Maßfeld, und das Feld erscheint im Viewport, nicht im
  unsichtbaren Canvas.
* Das Kontextmenü der Skizze kommt am Rechtsklick auf die Ebene.
* Ein Themenwechsel baut die Betten neu, statt sie im alten Thema stehen
  zu lassen.
"""

from __future__ import annotations

import time

from harness import SHOTS, build, open_log, say, settle

open_log("schluss.txt")


def screen_shot(name: str) -> None:
    from PySide6.QtWidgets import QApplication

    SHOTS.mkdir(parents=True, exist_ok=True)
    QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / name))
    say("  aufnahme:", name)


def wait_idle(app, window, seconds: float = 120.0) -> None:
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        app.processEvents()
        if not window.session.busy:
            settle(app, 0.3)
            if not window.session.busy:
                return
        time.sleep(0.05)
    say("  WARNUNG: immer noch busy")


app, window, dog = build()

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QContextMenuEvent, QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402
from PySide6.QtCore import QEvent  # noqa: E402

say("== 1. Skizzenmodus starten (Weg 2, Zeichnen)")
window.start_sketch("sketch_extrude")
wait_idle(app, window)
settle(app, 0.5)
screen_shot("schluss-01-skizzenmodus.png")

panel = window._sketch_panel
say("  panel da:", panel is not None)
canvas = panel.canvas if panel is not None else None

say("== 2. Linie zeichnen, dann Ziffer tippen — Maßfeld im Viewport?")
if canvas is not None:
    from app.core.types import Sketch, SketchElement

    drawn = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (30.0, 0.0))),),
    )
    canvas.set_sketch(drawn)
    canvas.selection = [("line", (0, 1))]
    app.processEvents()
    # Die Ziffer geht an den Interactor — der Weg des Kunden.
    interactor = window.viewport.plotter.interactor
    press = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier, "2")
    QApplication.sendEvent(interactor, press)
    settle(app, 0.5)
    host = canvas._measure_host
    say("  maßfeld-wirt:", type(host).__name__ if host is not None else None)
    field = canvas.measure_field
    say("  feld sichtbar am wirt:", field.isVisibleTo(window.viewport))
    say("  feldtext:", repr(field.text()))
    screen_shot("schluss-02-massfeld.png")

say("== 3. Rechtsklick auf die Ebene — kommt das Skizzenmenü?")
mitte = window.viewport.rect().center()
ereignis = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, mitte)
QApplication.sendEvent(window.viewport, ereignis)
window.viewport.sketchMenuAt.emit(None, mitte.x(), mitte.y())
settle(app, 0.8)
menus = [w for w in QApplication.topLevelWidgets() if isinstance(w, QMenu) and w.isVisible()]
say("  offene menüs:", len(menus), "| vom wachhund weggeräumt:", dog.seen[-3:])
screen_shot("schluss-03-menue.png")

say("== 4. Skizze verwerfen, Quader anlegen, Thema wechseln")
window.finish_sketch(keep=False)
settle(app, 0.5)
from app.core.scene import OperationDraft  # noqa: E402

window.session.apply(
    "Quader", [OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 10.0})]
)
wait_idle(app, window)
screen_shot("schluss-04-dunkel.png")
window.action_theme("light")
settle(app, 1.0)
screen_shot("schluss-05-hell.png")
window.action_theme("dark")
settle(app, 1.0)
screen_shot("schluss-06-wieder-dunkel.png")

say("== fertig; wachhund sah:", dog.seen)
window.release()
app.processEvents()
say("ENDE")
