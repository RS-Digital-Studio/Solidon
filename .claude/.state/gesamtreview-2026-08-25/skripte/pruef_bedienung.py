"""Bedienung mit Auswahl: Objekt wählen, Bohrung, Werkzeugleiste, Katalog, Chat.

Fortsetzung des Rundgangs — jetzt mit ausgewähltem Objekt, so wie der Kunde
arbeitet.
"""

from __future__ import annotations

import time
import traceback

from harness import SHOTS, build, open_log, say, settle, show_findings

open_log("bedienung.txt")


def screen_shot(name: str) -> None:
    from PySide6.QtWidgets import QApplication

    SHOTS.mkdir(parents=True, exist_ok=True)
    QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / name))
    say("  aufnahme:", name)


def wait_idle(app, window, seconds: float = 120.0) -> float:
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        app.processEvents()
        if not window.session.busy and not getattr(window.session, "split_running", False):
            settle(app, 0.3)
            if not window.session.busy:
                return time.monotonic() - started
        time.sleep(0.05)
    say("  WARNUNG: nach", seconds, "s immer noch busy")
    return time.monotonic() - started


def step(title: str):
    def wrap(fn):
        def run(*args, **kwargs):
            say("==", title)
            try:
                fn(*args, **kwargs)
            except Exception:
                say("  FEHLER im Schritt:", title)
                for line in traceback.format_exc().splitlines():
                    say("   ", line)
        return run
    return wrap


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


@step("Objekt auswählen")
def auswahl():
    objekte = list(window.session.last_result.scene.objects)
    say("  Objekte:", objekte)
    window.object_tree.select_object(objekte[0])
    settle(app, 0.6)
    say("  ausgewählt:", window.object_tree.selected())
    screen_shot("10-auswahl.png")
    aus = []
    bar = window.menuBar()
    for top in bar.actions():
        menu = top.menu()
        if menu is None:
            continue
        gesamt = 0
        inaktiv = 0

        def zaehle(m):
            nonlocal gesamt, inaktiv
            for a in m.actions():
                if a.isSeparator():
                    continue
                if a.menu() is not None:
                    zaehle(a.menu())
                    continue
                gesamt += 1
                if not a.isEnabled():
                    inaktiv += 1

        zaehle(menu)
        aus.append(f"{top.text()}: {gesamt - inaktiv}/{gesamt} aktiv")
    say("  Menüs nach Auswahl:", "; ".join(aus))


@step("Bohrung mit Auswahl")
def bohrung():
    window.run_operation(by_name["drill_hole"])
    settle(app, 0.8)
    dlg = window._op_dialog
    if dlg is None:
        say("  KEIN Dialog — Wachhund sah:", dog.seen[-1] if dog.seen else "nichts")
        return
    say("  Werte (Vorbelegung):", dict(dlg.values()))
    screen_shot("11-bohrung-dialog.png")
    dlg.accept()
    dauer = wait_idle(app, window)
    say(f"  Auswertung nach {dauer:.1f}s")
    screen_shot("11-bohrung.png")
    show_findings(window)


@step("Werkzeugleiste unten")
def werkzeuge():
    from PySide6.QtWidgets import QToolButton

    knoepfe = {k.text(): k for k in window.tools.findChildren(QToolButton)}
    say("  Knöpfe:", list(knoepfe))
    for name, datei in [("Messen", "12-messen.png"), ("Analyse", "13-analyse.png"), ("Schichten", "14-schichten.png"), ("Bewegen", "15-bewegen.png")]:
        knopf = knoepfe.get(name)
        if knopf is None:
            say("  fehlt:", name)
            continue
        say(f"  klicke {name!r} (enabled={knopf.isEnabled()})")
        knopf.click()
        wait_idle(app, window, 60)
        settle(app, 0.8)
        screen_shot(datei)
        knopf.click()
        settle(app, 0.4)


@step("Bausteinkatalog")
def katalog():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    def _shot() -> None:
        screen_shot("16-katalog.png")
        modal = QApplication.activeModalWidget()
        if modal is not None:
            say("  modal:", type(modal).__name__)
            modal.reject()

    dog._timer.stop()
    QTimer.singleShot(1200, _shot)
    window.action_catalog()
    for _ in range(200):
        app.processEvents()
    time.sleep(1.8)
    for _ in range(200):
        app.processEvents()
    dog.start(app)


@step("Chat ohne KI")
def chat():
    window.right.setCurrentWidget(window.chat)
    settle(app, 0.6)
    screen_shot("17-chat.png")


@step("Druckeinstellungen")
def druckeinstellungen():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    def _shot() -> None:
        screen_shot("18-druckeinstellungen.png")
        modal = QApplication.activeModalWidget()
        if modal is not None:
            say("  modal:", type(modal).__name__)
            modal.reject()

    dog._timer.stop()
    QTimer.singleShot(2500, _shot)
    window.action_print_settings()
    for _ in range(200):
        app.processEvents()
    time.sleep(3.2)
    for _ in range(200):
        app.processEvents()
    dog.start(app)


auswahl()
bohrung()
werkzeuge()
katalog()
chat()
druckeinstellungen()

say("Wachhund gesamt:", dog.seen)
say("FERTIG")
window.close()
for _ in range(50):
    app.processEvents()
raise SystemExit(0)
