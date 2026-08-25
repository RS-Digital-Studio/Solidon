"""Rundgang aus Kundensicht: Start, leeres Projekt, Quader, Bohrung, Undo, Speichern.

Jeder Schritt schreibt ins Protokoll und fotografiert; ein Fehler in einem
Schritt bricht den Rundgang nicht ab.
"""

from __future__ import annotations

import tempfile
import time
import traceback
from pathlib import Path

from harness import Watchdog, build, open_log, say, settle, shot

open_log("rundgang.txt")


def shot_screen(name: str) -> None:
    """Ganzer Bildschirm — ein Operationsdialog ist ein eigenes Top-Level."""
    from PySide6.QtWidgets import QApplication

    from harness import SHOTS

    SHOTS.mkdir(parents=True, exist_ok=True)
    QApplication.primaryScreen().grabWindow(0).save(str(SHOTS / name))
    say("  aufnahme:", name)


def wait_idle(app, window, seconds: float = 120.0) -> float:
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        app.processEvents()
        busy = window.session.busy
        split = getattr(window.session, "split_running", False)
        if not busy and not split:
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
say("Fenster steht. Wachhund bisher:", dog.seen)
shot(window, "01-start.png")

from app.core.registry import REGISTRY  # noqa: E402

by_name = {s.name: s for s in REGISTRY.all()}
say("Ops im Register:", len(by_name))


@step("Leeres Projekt")
def leeres_projekt():
    window.start_empty()
    settle(app, 1.0)
    shot(window, "02-leer.png")


@step("Quader anlegen")
def quader():
    window.run_operation(by_name["create_box"])
    settle(app, 1.0)
    dlg = window._op_dialog
    say("  Dialogtitel:", dlg.windowTitle())
    say("  Werte:", dict(dlg.values()))
    shot_screen("03-quader-dialog.png")
    dlg.accept()
    dauer = wait_idle(app, window)
    say(f"  Auswertung nach {dauer:.1f}s")
    shot(window, "04-quader.png")
    say("  Objekte:", [o for o in window.session.last_result.scene.objects] if window.session.last_result else "kein Ergebnis")


@step("Bohrung")
def bohrung():
    window.run_operation(by_name["drill_hole"])
    settle(app, 1.0)
    dlg = window._op_dialog
    say("  Werte (Vorbelegung aus Auswahl):", dict(dlg.values()))
    shot_screen("05-bohrung-dialog.png")
    dlg.accept()
    dauer = wait_idle(app, window)
    say(f"  Auswertung nach {dauer:.1f}s")
    shot(window, "06-bohrung.png")


@step("Prüfbefunde")
def befunde():
    from harness import show_findings

    counts = show_findings(window)
    say("  Zusammenfassung:", counts or "keine Befunde")


@step("Undo und Redo")
def undo_redo():
    window.action_undo()
    wait_idle(app, window)
    shot(window, "07-undo.png")
    window.action_redo()
    wait_idle(app, window)
    shot(window, "08-redo.png")


@step("Speichern und Wiederöffnen")
def speichern():
    ziel = Path(tempfile.mkdtemp(prefix="solidon-rundgang-")) / "rundgang.solidon"
    pfad = window.session.save_project(ziel)
    say("  gespeichert:", pfad, pfad.exists(), pfad.stat().st_size, "Bytes")
    window.open_path(pfad)
    dauer = wait_idle(app, window)
    say(f"  wiedergeöffnet nach {dauer:.1f}s, Titel: {window.windowTitle()!r}")
    shot(window, "09-wiedergeoeffnet.png")


leeres_projekt()
quader()
bohrung()
befunde()
undo_redo()
speichern()

say("Wachhund gesamt:", dog.seen)
say("FERTIG")
window.close()
settle(app, 0.5)
raise SystemExit(0)
