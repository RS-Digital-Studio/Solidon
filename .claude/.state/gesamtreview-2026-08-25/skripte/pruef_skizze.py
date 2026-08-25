"""Skizzenmodus: Tasche schneiden nach dem Zeichnen auf einer Fläche.

Prüft die Vermutung der Nachbarsitzung: verlangt die Operation nach dem
Zeichnen noch eine Auswahl? Dazu: Fertig mit leerer Skizze — was passiert?
"""

from __future__ import annotations

import time
import traceback

from harness import SHOTS, build, open_log, say, settle

open_log("skizze.txt")


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
from app.core.registry import REGISTRY  # noqa: E402

by_name = {s.name: s for s in REGISTRY.all()}
window.start_empty()
settle(app, 0.5)
window.run_operation(by_name["create_box"])
settle(app, 0.5)
window._op_dialog.accept()
wait_idle(app, window)
say("Quader steht.")

try:
    say("== Fläche wählen, Tasche schneiden über das Menü")
    window.object_tree.select_feature("obj_1", "face_top")
    settle(app, 0.5)
    say("  gewählt:", window.object_tree.selected(), window.object_tree.selected_feature())
    say("  Zeichenebene:", window._selected_face_plane())
    action = window._op_actions.get("sketch_pocket")
    say("  Menüeintrag aktiv:", action.isEnabled() if action else "kein Eintrag")
    if action is not None and action.isEnabled():
        action.trigger()
        settle(app, 1.0)
        say("  Skizzenmodus:", window._sketch_panel is not None, "— Ziel:", window._sketch_target)
        say("  Op-Dialog offen:", window._op_dialog is not None)
        screen_shot("20-skizzenmodus.png")
except Exception:
    for line in traceback.format_exc().splitlines():
        say("   ", line)

try:
    say("== Fertig mit leerer Skizze")
    if window._sketch_panel is not None:
        window.finish_sketch(True)
        settle(app, 0.8)
        say("  Skizzenmodus danach:", window._sketch_panel is not None)
        say("  Op-Dialog danach:", window._op_dialog is not None)
        say("  Statuszeile:", window.statusBar().currentMessage() or repr(""))
        screen_shot("21-fertig-leer.png")
except Exception:
    for line in traceback.format_exc().splitlines():
        say("   ", line)

try:
    say("== Erneut: mit gezeichnetem Rechteck")
    from app.core.sketch.serialize import sketch_to_text
    from app.core.sketch.shapes import rectangle

    text = sketch_to_text(rectangle(12.0, 8.0))
    window.object_tree.select_feature("obj_1", "face_top")
    settle(app, 0.3)
    window.start_sketch("sketch_pocket", text=text)
    settle(app, 0.8)
    say("  Skizzenmodus:", window._sketch_panel is not None)
    say("  Skizzentext da:", bool(window._sketch_panel.sketch_text()))
    screen_shot("22-skizze-gefuellt.png")
    window.finish_sketch(True)
    settle(app, 1.0)
    dlg = window._op_dialog
    say("  Op-Dialog offen:", dlg is not None, "—", dlg.windowTitle() if dlg else "")
    if dlg is None:
        say("  Wachhund zuletzt:", dog.seen[-3:])
        screen_shot("23-kein-dialog.png")
    else:
        say("  Werte:", {k: v for k, v in dict(dlg.values()).items() if k != "sketch"})
        screen_shot("23-taschen-dialog.png")
        dlg.accept()
        wait_idle(app, window)
        screen_shot("24-tasche.png")
        result = window.session.last_result
        say("  Objekte:", list(result.scene.objects) if result else "kein Ergebnis")
        from harness import show_findings

        show_findings(window)
except Exception:
    for line in traceback.format_exc().splitlines():
        say("   ", line)

say("Wachhund gesamt:", dog.seen)
say("FERTIG")
window.close()
for _ in range(50):
    app.processEvents()
raise SystemExit(0)
