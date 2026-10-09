"""Sonde: Auswahl nach dem Anlegen, Karte an einer Fläche, Kartensuche."""
from __future__ import annotations
import faulthandler, os, sys, tempfile
TREE, OUT = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp(prefix="probe-face-")
os.environ["APPDATA"] = os.path.join(tmp, "roaming")
os.environ["LOCALAPPDATA"] = os.path.join(tmp, "local")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, TREE)
faulthandler.dump_traceback_later(300, exit=True)
out = open(OUT, "w", encoding="utf-8", buffering=1)
def say(*p): out.write(" ".join(str(x) for x in p) + "\n")
from PySide6.QtWidgets import QApplication
app = QApplication([])
from app.core.bootstrap import load_operations
load_operations()
import app.ui.main_window as M
say("gemessen wird", M.__file__)
from app.core.registry import REGISTRY
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.session import Session
from app.ui.settings import UiSettings
sys.path.insert(0, os.path.join(TREE, "tools"))
from run_ui_audit import settle, silence_questions
def idle():
    for _ in range(60):
        settle(app, 5)
        if window.session.wait_for_idle():
            break
    settle(app, 10)
window = MainWindow(Session(), UiSettings())
window.resize(1500, 950); window.show()
silence_questions(window.session, window); settle(app, 10)
panel = window.selection_operations
def card(label):
    front = [b.text() for n, b in panel._quick_buttons.items() if not b.isHidden()]
    listed = [b.text() for n, b in panel._buttons.items() if b.isVisible()]
    say(label, "| Kopf:", panel.summary.text(), "| vorn:", front)
    say("   Liste:", listed)
    return listed
for i in range(2):
    window.run_operation(REGISTRY.get("create_brep_box"))
    settle(app, 10)
    d = [c for c in window.findChildren(OperationDialog) if c.isVisible()][0]
    d.accept(); idle()
    say(f"nach Quader {i+1}: gewählt", window.object_tree.selected_objects(), "Tiefe", window.viewport.selection_depth() if callable(getattr(window.viewport, "selection_depth", None)) else getattr(window.viewport, "selection_depth", "?"))
card("nach dem Anlegen")
result = window.session.last_result
ids = list(result.scene.objects)
entry = result.scene.objects[ids[0]]
top = next(fid for fid, f in entry.features.items() if f.kind == "face" and f.params.get("normal", (0, 0, 0))[2] > 0.9)
window.object_tree.select_object(ids[0]); settle(app, 10)
card("ein Körper")
for q in ("verschmelzen", "vereinigen", "zusammenfügen", "löschen", "entfernen", "aushoehlen", "hohl"):
    panel.search.setText(q); settle(app, 5)
    vis = [b.text() for b in panel._buttons.values() if b.isVisible()]
    say(f"   Kartensuche {q!r} (1 Körper):", vis)
panel.search.setText(""); settle(app, 5)
window.object_tree.select_feature(ids[0], top); settle(app, 10)
listed = card("Oberseite gewählt")
say("   Aushöhlen sichtbar an der Fläche:", "Aushöhlen" in listed)
say("fertig")
out.close(); os._exit(0)
