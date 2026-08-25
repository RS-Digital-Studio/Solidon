"""Fremdsprachen-Durchgang (Portugiesisch) und die kleinen Dialoge.

Eine fremde Sprache deckt feste deutsche Zeichenketten auf — zwei der sechs
Fehler vom 25.08. standen genau so im Bild.
"""

from __future__ import annotations

import time
import traceback

from harness import SHOTS, build, open_log, say, settle

open_log("sprache.txt")

# Vor dem Fensterbau: Sprache in die (isolierten) Einstellungen schreiben.
from app.ui.settings import load_settings, save_settings  # noqa: E402

settings = load_settings()
settings.language = "pt"
save_settings(settings)
say("Sprache gesetzt:", settings.language)

app, window, dog = build()


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


def modal_dialog(opener, name: str, delay_ms: int = 1500, wait_s: float = 2.2) -> None:
    """Öffnet einen modalen Dialog, fotografiert ihn und schließt ihn."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    def _shot() -> None:
        screen_shot(name)
        modal = QApplication.activeModalWidget()
        if modal is not None:
            say("  modal:", type(modal).__name__, repr(modal.windowTitle()))
            modal.reject()
        else:
            say("  KEIN modaler Dialog offen")

    dog._timer.stop()
    QTimer.singleShot(delay_ms, _shot)
    try:
        opener()
    except Exception:
        for line in traceback.format_exc().splitlines():
            say("   ", line)
    for _ in range(200):
        app.processEvents()
    time.sleep(wait_s)
    for _ in range(200):
        app.processEvents()
    dog.start(app)


say("== Startbildschirm (pt)")
screen_shot("30-start-pt.png")

from app.core.registry import REGISTRY  # noqa: E402

by_name = {s.name: s for s in REGISTRY.all()}
window.start_empty()
settle(app, 0.5)

say("== Quader-Dialog (pt)")
window.run_operation(by_name["create_box"])
settle(app, 0.8)
dlg = window._op_dialog
if dlg is not None:
    say("  Titel:", repr(dlg.windowTitle()))
    try:
        dlg.advanced.click()
        settle(app, 0.4)
        say("  Weitere Einstellungen aufgeklappt")
    except Exception as fehler:
        say("  advanced?", fehler)
    screen_shot("31-quader-dialog-pt.png")
    dlg.accept()
    wait_idle(app, window)

say("== Bohrung + Prüfbericht (pt)")
window.object_tree.select_object("obj_1")
settle(app, 0.3)
window.run_operation(by_name["drill_hole"])
settle(app, 0.6)
if window._op_dialog is not None:
    window._op_dialog.accept()
    wait_idle(app, window)
screen_shot("32-hauptfenster-pt.png")

say("== Einstellungen-Dialog (pt)")
modal_dialog(window.action_settings, "33-einstellungen-pt.png")

say("== Tastenkürzel (pt)")
try:
    modal_dialog(window.action_shortcuts, "34-tastenkuerzel-pt.png")
except AttributeError:
    say("  action_shortcuts fehlt — Kandidaten:", [n for n in dir(window) if "short" in n.lower()])

say("== Über-Dialog (pt)")
try:
    modal_dialog(window.action_about, "35-ueber-pt.png")
except AttributeError:
    say("  action_about fehlt — Kandidaten:", [n for n in dir(window) if "about" in n.lower()])

say("== Freischalten (pt)")
try:
    modal_dialog(window.action_activate, "36-freischalten-pt.png")
except AttributeError:
    say("  action_activate fehlt — Kandidaten:", [n for n in dir(window) if "activ" in n.lower()])

say("Wachhund gesamt:", dog.seen)
say("FERTIG")
window.close()
for _ in range(50):
    app.processEvents()
raise SystemExit(0)
