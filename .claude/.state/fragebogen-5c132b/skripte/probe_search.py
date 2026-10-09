"""Sonde: Suche in der Auswahlkarte wie in der Palette."""
from __future__ import annotations
import faulthandler, os, sys, tempfile
TREE, OUT = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp(prefix="probe-search-")
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
import app.ui.selection_operations as SO
say("gemessen wird", SO.__file__)
from app.core.scene import OperationDraft
from app.ui.main_window import MainWindow
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
window.session.apply("Körper", [OperationDraft(op="create_brep_box"), OperationDraft(op="create_brep_box")])
idle()
ids = list(window.session.last_result.scene.objects)
panel = window.selection_operations
def look(label):
    vis = [b.text().replace("\n", " ") for b in panel._buttons.values() if b.isVisible() and b.property("operationName") not in panel._quick_buttons]
    quick = [b.text() for n, b in panel._quick_buttons.items() if not b.isHidden()]
    say(label, "| vorn:", quick, "| Liste:", vis[:8], "| Satz:", panel._nothing.text() if not panel._nothing.isHidden() else "-", "| Überall:", not panel._everywhere.isHidden())
window.object_tree.select_object(ids[0]); settle(app, 10)
for q in ("verschmelzen", "vereinigen", "zusammenfügen", "löschen", "entfernen", "aushoehlen", "hohl", "formgebung", "xyzzy"):
    panel.search.setText(q); settle(app, 5)
    look(f"1 Körper, {q!r}")
panel.search.setText(""); settle(app, 5)
window.object_tree.select_objects(ids); settle(app, 10)
for q in ("verschmelzen", "löschen"):
    panel.search.setText(q); settle(app, 5)
    look(f"2 Körper, {q!r}")
panel.search.setText(""); settle(app, 5)
say("fertig")
out.close(); os._exit(0)
