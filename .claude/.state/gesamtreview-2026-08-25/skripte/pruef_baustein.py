"""Eilprüfung für -ce: Kommt aus dem Katalogweg ein Baustein-Schritt heraus?

Nachgestellt wird genau der Pfad hinter dem Katalog: Auswahl steht, dann
``run_operation(REGISTRY.get(part_op_name(name)))`` — wie ``action_catalog``
nach dem Accept. Bestätigt wird über den echten Dialog.
"""

from __future__ import annotations

import time

from harness import SHOTS, build, open_log, say, settle

open_log("baustein.txt")

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
settle(app, 0.3)
say("Vorher im Stapel:", [op.op for op in window.session.project.document.ops])

from app.core.knowledge.parts.ops import op_name as part_op_name  # noqa: E402

op_name = part_op_name("pegboard_hook")
say("Operation:", op_name, "— im Register:", op_name in by_name)
window.run_operation(by_name[op_name])
settle(app, 0.8)
dlg = window._op_dialog
if dlg is None:
    say("KEIN Dialog — Wachhund:", dog.seen[-2:])
else:
    say("Dialog:", dlg.windowTitle())
    say("Werte:", dict(dlg.values()))
    from PySide6.QtWidgets import QApplication

    SHOTS.mkdir(parents=True, exist_ok=True)
    QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / "60-baustein-dialog.png"))
    dlg.accept()
    start = time.monotonic()
    while window.session.busy and time.monotonic() - start < 120:
        app.processEvents()
        time.sleep(0.05)
    settle(app, 0.8)
    say("Nachher im Stapel:", [op.op for op in window.session.project.document.ops])
    result = window.session.last_result
    say("Objekte:", list(result.scene.objects) if result else None)
    from harness import show_findings

    show_findings(window)
    QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / "61-baustein.png"))
    say("aufnahme: 61-baustein.png")
say("Wachhund gesamt:", dog.seen)
say("FERTIG")
window.close()
for _ in range(50):
    app.processEvents()
raise SystemExit(0)
