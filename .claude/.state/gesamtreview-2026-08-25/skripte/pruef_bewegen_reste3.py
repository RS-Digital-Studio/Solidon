"""A3, dritter Anlauf: welche Aktor-Geometrie wächst durch den Bewegen-Wechsel?"""

from __future__ import annotations

import time

from harness import build, open_log, say, settle

open_log("bewegen-reste3.txt")

app, window, dog = build()
from app.core.registry import REGISTRY  # noqa: E402

by_name = {s.name: s for s in REGISTRY.all()}
window.start_empty()
settle(app, 0.5)
window.run_operation(by_name["create_box"])
settle(app, 0.5)
window._op_dialog.accept()
start = time.monotonic()
while window.session.busy and time.monotonic() - start < 60:
    app.processEvents()
    time.sleep(0.05)
settle(app, 0.5)
window.object_tree.select_object("obj_1")
settle(app, 0.5)


def vtk_props() -> list[str]:
    renderer = window.viewport.plotter.renderer
    collection = renderer.GetViewProps()
    collection.InitTraversal()
    found = []
    for _ in range(collection.GetNumberOfItems()):
        prop = collection.GetNextProp()
        found.append(type(prop).__name__)
    return found


def shapes() -> dict[str, tuple]:
    found = {}
    for name, actor in window.viewport.plotter.renderer.actors.items():
        prop = getattr(actor, "GetProperty", lambda: None)()
        merkmale = ()
        if prop is not None and hasattr(prop, "GetEdgeVisibility"):
            merkmale = (
                int(prop.GetEdgeVisibility()),
                round(float(prop.GetLineWidth()), 2),
                int(prop.GetRepresentation()),
                int(actor.GetVisibility()),
                tuple(round(v, 3) for v in prop.GetColor()),
            )
        matrix = actor.GetUserMatrix() if hasattr(actor, "GetUserMatrix") else None
        ident = None
        if matrix is not None:
            ident = tuple(round(matrix.GetElement(i, j), 4) for i in range(4) for j in range(4))
        found[name] = (merkmale, ident)
    return found


vorher = shapes()
props_vorher = vtk_props()
say("VTK-Props vorher:", len(props_vorher))

from PySide6.QtWidgets import QToolButton  # noqa: E402

knoepfe = {k.text(): k for k in window.tools.findChildren(QToolButton)}
knoepfe["Bewegen"].click()
settle(app, 0.8)
knoepfe["Bewegen"].click()
settle(app, 0.8)

from harness import SHOTS
from PySide6.QtWidgets import QApplication
SHOTS.mkdir(parents=True, exist_ok=True)
QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / "53-nur-bewegen.png"))
say("aufnahme: 53-nur-bewegen.png")
knoepfe["Schichten"].click()
start2 = time.monotonic()
while window.session.busy and time.monotonic() - start2 < 120:
    app.processEvents()
    time.sleep(0.05)
settle(app, 0.8)
knoepfe["Schichten"].click()
settle(app, 0.5)
knoepfe["Bewegen"].click()
settle(app, 0.8)
knoepfe["Bewegen"].click()
settle(app, 0.8)
QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / "54-schichten-dann-bewegen.png"))
say("aufnahme: 54-schichten-dann-bewegen.png")
nachher = shapes()
props_nachher = vtk_props()
say("VTK-Props nachher:", len(props_nachher))
from collections import Counter
diff = Counter(props_nachher) - Counter(props_vorher)
say("mehr geworden:", dict(diff))
for name in sorted(set(vorher) | set(nachher)):
    a = vorher.get(name)
    b = nachher.get(name)
    marke = "  <-- geändert" if a != b else ""
    say(f"{name}: {a} -> {b}{marke}")
say("FERTIG")
window.close()
for _ in range(50):
    app.processEvents()
raise SystemExit(0)
