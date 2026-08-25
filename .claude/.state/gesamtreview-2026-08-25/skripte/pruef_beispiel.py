"""Ein Beispiel über den Menüweg öffnen — Hilfe → Beispiele → erster Eintrag."""

from __future__ import annotations

import time
import traceback

from harness import SHOTS, build, open_log, say, settle

open_log("beispiel.txt")


def screen_shot(name: str) -> None:
    from PySide6.QtWidgets import QApplication

    SHOTS.mkdir(parents=True, exist_ok=True)
    QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / name))
    say("  aufnahme:", name)


def wait_idle(app, window, seconds: float = 180.0) -> None:
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

try:
    bar = window.menuBar()
    hilfe = next(a.menu() for a in bar.actions() if a.text() == "Hilfe")
    beispiele = next(a.menu() for a in hilfe.actions() if a.text() == "Beispiele")
    eintraege = [a for a in beispiele.actions() if not a.isSeparator()]
    say("Beispiele:", [(a.text(), a.isEnabled()) for a in eintraege])
    if eintraege:
        eintraege[0].trigger()
        wait_idle(app, window)
        settle(app, 1.5)
        say("Titel:", repr(window.windowTitle()))
        say("Objekte:", list(window.session.last_result.scene.objects) if window.session.last_result else None)
        say("Reiter rechts:", [window.right.tabText(i) for i in range(window.right.count()) if window.right.isTabVisible(i)])
        screen_shot("42-beispiel.png")
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
