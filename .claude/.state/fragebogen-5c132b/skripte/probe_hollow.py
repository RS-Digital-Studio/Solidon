"""Sonde: Aushöhlen an einem eingelesenen Modell — was vorn steht, was der Dialog zeigt, was herauskommt."""

from __future__ import annotations

import faulthandler
import os
import sys
import tempfile

TREE = sys.argv[1]
OUT = sys.argv[2]
MODEL = sys.argv[3]
tmp = tempfile.mkdtemp(prefix="probe-hollow-")
os.environ["APPDATA"] = os.path.join(tmp, "roaming")
os.environ["LOCALAPPDATA"] = os.path.join(tmp, "local")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, TREE)
faulthandler.dump_traceback_later(600, exit=True)

out = open(OUT, "w", encoding="utf-8", buffering=1)


def say(*parts: object) -> None:
    out.write(" ".join(str(p) for p in parts) + "\n")


from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

app = QApplication([])

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

import app.ui.main_window as M  # noqa: E402

say("gemessen wird", M.__file__, "Modell", MODEL)

from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene import OperationDraft  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.op_dialog import OperationDialog  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

sys.path.insert(0, os.path.join(TREE, "tools"))
from run_ui_audit import settle, silence_questions  # noqa: E402


def idle() -> None:
    for _ in range(80):
        settle(app, 5)
        if window.session.wait_for_idle():
            break
    settle(app, 10)


window = MainWindow(Session(), UiSettings())
window.resize(1500, 950)
window.show()
silence_questions(window.session, window)
settle(app, 10)
from pathlib import Path
window.open_path(Path(MODEL))
idle()
result = window.session.last_result
ids = list(result.scene.objects)
entry = result.scene.objects[ids[0]]
say("Objekte:", ids, "Art:", entry.kind, "Volumen:", round(entry.mesh.volume, 1) if hasattr(entry.mesh, "volume") else "?")

window.object_tree.select_object(ids[0])
settle(app, 10)
panel = window.selection_operations
say(
    "vorn:",
    [(n, b.text(), b.isEnabled(), b.toolTip()[:120]) for n, b in panel._quick_buttons.items() if not b.isHidden()],
)

spec = REGISTRY.get("hollow_object")
window.run_operation(spec)
settle(app, 10)
dialogs = [c for c in window.findChildren(OperationDialog) if c.isVisible()]
say("Dialog offen:", bool(dialogs))
if dialogs:
    d = dialogs[0]
    say("  Werte:", d.values())
    labels = [w.text() for w in d.findChildren(QLabel) if w.isVisible() and w.text().strip()]
    say("  sichtbare Beschriftungen:", labels)
    d.reject()
    settle(app, 5)

for params in ({"wall": 2.0}, {"wall": 2.0, "open_top": True}):
    window.session.apply(
        "Aushöhlen", [OperationDraft(op="hollow_object", inputs=(ids[0],), params=params)]
    )
    idle()
    r = window.session.last_result
    body = next(iter(r.scene.objects.values()))
    mesh = body.mesh
    try:
        vol = round(float(mesh.volume), 1)
    except Exception as error:  # noqa: BLE001
        vol = f"? {error}"
    say("Aushöhlen", params, "-> Art", body.kind, "Volumen", vol, "angehalten:", r.stopped_at)
    for f in getattr(r.scene.report, "findings", []):
        say("   Befund:", getattr(f, "code", f), str(getattr(f, "message", ""))[:160], dict(getattr(f, "values", {}) or {}))
    say("   Statuszeile:", window.statusBar().currentMessage())
    window.session.undo()
    idle()

say("fertig")
out.close()
os._exit(0)
