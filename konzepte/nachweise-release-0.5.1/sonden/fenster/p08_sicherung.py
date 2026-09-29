"""Sonde p08: die automatische Sicherung im Hauptfaden — wie lange steht das Fenster?

Modell über den Kundenweg öffnen (große Frage mit *Sofort laden*), dann den
Zeitgeber-Slot der Sicherung von Hand auslösen, dreimal, mit 5-ms-Takt."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SONDE_FRIST", "600")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

MODEL = Path(sys.argv[1])
log = common.Log(f"p08_{MODEL.stem[:20]}_{os.environ.get('SONDE_TAG', 'x')}.txt")
application, window = common.build()
from app.ui.dialogs import AskDialog  # noqa: E402


def handler(dialog) -> bool:
    if isinstance(dialog, AskDialog):
        dialog.list.setCurrentRow(0)
        dialog._accept.click()
        return True
    return False


dog = common.Watchdog(application, window, log, handler)
window.start()
window.open_path(MODEL)
started = time.monotonic()
common.wait_until(application, lambda: time.monotonic() - started > 2 and not window.session.busy, 500)
common.pump(application, 1.0)
log("geladen nach", round(time.monotonic() - started, 1), "s; geändert:", window.session.modified)
slot = window._autosave.timeout
meter = common.GapMeter(application)
for run in range(3):
    window.session._dirty = True
    meter.start()
    begun = time.monotonic()
    slot.emit()
    took = time.monotonic() - begun
    common.pump(application, 0.2)
    common.wait_until(application, lambda: getattr(window.session, "_autosaving", None) is None, 30)
    common.pump(application, 0.1)
    log(f"Sicherung {run}: Slot {took * 1000:.0f} ms, längste Lücke {meter.stop() * 1000:.0f} ms")
from app.core.scene.project import autosave_path  # noqa: E402

target = autosave_path(window.session.path, window.session.recovery_token)
log("Datei:", target.name, round(target.stat().st_size / 1e6, 1), "MB" if target.exists() else "fehlt")
import app.ui.session as session_module  # noqa: E402
from app.core.errors import FileWriteError  # noqa: E402

if hasattr(window.session, "autosave_async"):
    def refusing(*_a, **_k):
        raise FileWriteError(target="x", detail="Kein Platz")
    session_module.write_autosave = refusing
    window.session._dirty = True
    slot.emit()
    common.wait_until(application, lambda: window.session._autosaving is None, 30)
    common.pump(application, 0.2)
    log("nach Schreibfehler, Statuszeile:", repr(window.status_message.text()))
log("Ende")
common.os._exit(0)
