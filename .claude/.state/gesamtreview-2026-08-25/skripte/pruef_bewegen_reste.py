"""A3: Welche Aktoren lässt der Bewegen-Modus beim Verlassen zurück?"""

from __future__ import annotations

import time

from harness import build, open_log, say, settle

open_log("bewegen-reste.txt")

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


def actor_names() -> set[str]:
    return set(window.viewport.plotter.renderer.actors)


vorher = actor_names()
say("Aktoren vorher:", len(vorher))

from PySide6.QtWidgets import QToolButton  # noqa: E402

knoepfe = {k.text(): k for k in window.tools.findChildren(QToolButton)}
knoepfe["Bewegen"].click()
settle(app, 0.8)
mit_gizmo = actor_names()
say("Aktoren im Bewegen-Modus:", len(mit_gizmo), "— neu:", sorted(mit_gizmo - vorher))

knoepfe["Bewegen"].click()
settle(app, 0.8)
nachher = actor_names()
say("Aktoren nach Verlassen:", len(nachher), "— Reste:", sorted(nachher - vorher))
say("FERTIG")
window.close()
for _ in range(50):
    app.processEvents()
raise SystemExit(0)
