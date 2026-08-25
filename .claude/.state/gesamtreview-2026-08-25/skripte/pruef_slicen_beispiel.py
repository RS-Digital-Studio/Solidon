"""Zwei Kundenwege: Slicen ohne gewähltes Slicer-Profil, und ein Beispiel öffnen."""

from __future__ import annotations

import time
import traceback

from harness import SHOTS, build, open_log, say, settle

open_log("slicen-beispiel.txt")


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
    say("== Slicen ohne Slicer-Profil")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QPushButton

    dog._timer.stop()

    def _in_dialog() -> None:
        modal = QApplication.activeModalWidget()
        if modal is None:
            say("  KEIN Dialog offen")
            return
        say("  Dialog:", type(modal).__name__)
        knoepfe = {k.text(): k for k in modal.findChildren(QPushButton)}
        say("  Knöpfe:", {t: k.isEnabled() for t, k in knoepfe.items()})
        slicen = knoepfe.get("Slicen")
        if slicen is None or not slicen.isEnabled():
            say("  Slicen nicht klickbar")
            modal.reject()
            return

        def _after_click() -> None:
            screen_shot("40-slicen-ohne-profil.png")
            inner = QApplication.activeModalWidget()
            say("  nach Klick modal:", type(inner).__name__ if inner else None,
                repr(inner.windowTitle()) if inner else "")
            from PySide6.QtWidgets import QMessageBox

            if isinstance(inner, QMessageBox):
                say("  Meldung:", repr(inner.text()))
                inner.accept()
                QTimer.singleShot(300, lambda: _close_settings())
            elif inner is not None and inner is not modal:
                inner.reject()
                QTimer.singleShot(300, lambda: _close_settings())
            else:
                _close_settings()

        def _close_settings() -> None:
            outer = QApplication.activeModalWidget()
            if outer is not None:
                fehlt = getattr(outer, "problem", None)
                say("  Hinweis im Dialog:", fehlt.text() if hasattr(fehlt, "text") else None)
                screen_shot("41-slicen-danach.png")
                outer.reject()

        QTimer.singleShot(2500, _after_click)
        slicen.click()

    QTimer.singleShot(2500, _in_dialog)
    window.action_print_settings()
    for _ in range(300):
        app.processEvents()
    time.sleep(7.0)
    for _ in range(300):
        app.processEvents()
    dog.start(app)
except Exception:
    for line in traceback.format_exc().splitlines():
        say("   ", line)

try:
    say("== Beispiel öffnen")
    from app.core import examples

    kandidaten = None
    try:
        kandidaten = list(examples.all())
    except AttributeError:
        say("  examples-API:", [n for n in dir(examples) if not n.startswith("_")])
    say("  Kandidaten:", kandidaten)
    handler = getattr(window, "open_example", None) or getattr(window, "action_example", None)
    say("  Fenster-Handler:", handler)
    if handler is not None and kandidaten:
        first = kandidaten[0]
        handler(getattr(first, "id", first))
        wait_idle(app, window)
        settle(app, 1.0)
        screen_shot("42-beispiel.png")
        say("  Titel:", repr(window.windowTitle()))
except Exception:
    for line in traceback.format_exc().splitlines():
        say("   ", line)

say("Wachhund gesamt:", dog.seen)
say("FERTIG")
window.close()
for _ in range(50):
    app.processEvents()
raise SystemExit(0)
