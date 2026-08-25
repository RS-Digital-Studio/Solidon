"""Menü-Durchsicht: jedes Menü aufklappen, fotografieren, Einträge protokollieren.

Der Wachhund würde jedes Popup sofort schließen — für die Aufnahme wird er
angehalten und danach wieder gestartet.
"""

from __future__ import annotations

import time
import traceback

from harness import SHOTS, build, open_log, say, settle

open_log("menues.txt")

app, window, dog = build()

from app.core.registry import REGISTRY  # noqa: E402

by_name = {s.name: s for s in REGISTRY.all()}
window.start_empty()
settle(app, 0.5)
window.run_operation(by_name["create_box"])
settle(app, 0.5)
if window._op_dialog is not None:
    window._op_dialog.accept()
for _ in range(100):
    app.processEvents()
time.sleep(1.0)
for _ in range(100):
    app.processEvents()
say("Projekt mit Quader steht.")


def screen_shot(name: str) -> None:
    from PySide6.QtWidgets import QApplication

    SHOTS.mkdir(parents=True, exist_ok=True)
    QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / name))


def dump_menu(menu, depth: int) -> None:
    for action in menu.actions():
        if action.isSeparator():
            say("  " * depth + "---")
            continue
        sub = action.menu()
        state = []
        if not action.isEnabled():
            state.append("AUS")
        if action.isChecked():
            state.append("angehakt")
        shortcut = action.shortcut().toString()
        line = "  " * depth + repr(action.text())
        if shortcut:
            line += f"  [{shortcut}]"
        if state:
            line += "  (" + ", ".join(state) + ")"
        say(line)
        if sub is not None:
            dump_menu(sub, depth + 1)


dog._timer.stop()
bar = window.menuBar()
index = 0
for top in bar.actions():
    menu = top.menu()
    if menu is None:
        continue
    index += 1
    say(f"== Menü {index}: {top.text()!r}")
    try:
        dump_menu(menu, 1)
        rect = bar.actionGeometry(top)
        menu.popup(bar.mapToGlobal(rect.bottomLeft()))
        for _ in range(60):
            app.processEvents()
        time.sleep(0.35)
        for _ in range(30):
            app.processEvents()
        screen_shot(f"menue-{index:02d}.png")
        say("  aufnahme:", f"menue-{index:02d}.png")
        menu.hide()
        for _ in range(30):
            app.processEvents()
    except Exception:
        for line in traceback.format_exc().splitlines():
            say("   ", line)

say("== Werkzeugleiste")
try:
    strip = window.tool_strip
except AttributeError:
    strip = None
    say("  kein Attribut tool_strip — suche Kinder")
if strip is not None:
    from PySide6.QtWidgets import QToolButton

    for knopf in strip.findChildren(QToolButton):
        say(f"  {knopf.text()!r} tooltip={knopf.toolTip()!r} enabled={knopf.isEnabled()}")

say("== Befehlspalette")
try:
    from PySide6.QtCore import QTimer

    def _palette_shot() -> None:
        screen_shot("befehlspalette.png")
        say("  aufnahme: befehlspalette.png")
        from PySide6.QtWidgets import QApplication

        modal = QApplication.activeModalWidget()
        if modal is not None:
            say("  modal:", type(modal).__name__)
            modal.reject()
        popup = QApplication.activePopupWidget()
        if popup is not None:
            say("  popup:", type(popup).__name__)
            popup.close()

    QTimer.singleShot(700, _palette_shot)
    window.action_command_palette()
    for _ in range(100):
        app.processEvents()
    time.sleep(1.2)
    for _ in range(100):
        app.processEvents()
except Exception:
    for line in traceback.format_exc().splitlines():
        say("   ", line)

dog.start(app)
say("Wachhund gesamt:", dog.seen)
say("FERTIG")
window.close()
for _ in range(50):
    app.processEvents()
raise SystemExit(0)
