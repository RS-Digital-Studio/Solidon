"""Nur der Themenwechsel, ohne die Skizzen-Abschnitte davor."""

from __future__ import annotations

from harness import SHOTS, build, open_log, say, settle

open_log("thema.txt")


def screen_shot(name: str) -> None:
    from PySide6.QtWidgets import QApplication

    SHOTS.mkdir(parents=True, exist_ok=True)
    QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / name))
    say("  aufnahme:", name)


app, window, dog = build()

say("== Thema hell")
window.action_theme("light")
settle(app, 1.0)
say("  palette:", app.palette().window().color().name())
screen_shot("thema-01-hell.png")

say("== Thema dunkel")
window.action_theme("dark")
settle(app, 1.0)
say("  palette:", app.palette().window().color().name())
screen_shot("thema-02-dunkel.png")

say("ENDE; wachhund sah:", dog.seen)
window.release()
app.processEvents()
