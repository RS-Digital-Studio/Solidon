"""A3, zweiter Anlauf: die exakte Werkzeugfolge der Durchsicht nachstellen."""

from __future__ import annotations

import time

from harness import SHOTS, build, open_log, say, settle

open_log("bewegen-reste2.txt")

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


def screen_shot(name: str) -> None:
    from PySide6.QtWidgets import QApplication

    SHOTS.mkdir(parents=True, exist_ok=True)
    QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / name))
    say("  aufnahme:", name)


vorher = actor_names()
say("Aktoren vorher:", len(vorher))
screen_shot("50-vorher.png")

from PySide6.QtWidgets import QToolButton  # noqa: E402

knoepfe = {k.text(): k for k in window.tools.findChildren(QToolButton)}
for name in ("Messen", "Analyse", "Schichten", "Bewegen"):
    knoepfe[name].click()
    while window.session.busy and time.monotonic() - start < 120:
        app.processEvents()
        time.sleep(0.05)
    settle(app, 0.8)
    knoepfe[name].click()
    settle(app, 0.5)
    jetzt = actor_names()
    say(f"nach {name} an/aus:", len(jetzt), "— Reste:", sorted(jetzt - vorher))
    screen_shot(f"52-nach-{name.lower()}.png")

screen_shot("51-nachher.png")
say("FERTIG")
window.close()
for _ in range(50):
    app.processEvents()
raise SystemExit(0)
