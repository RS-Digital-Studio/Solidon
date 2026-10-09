"""Sonde: Was der Klick aus „Ein Gehäuse mit Deckel“ nach dem Anlegen trifft."""
from __future__ import annotations
import faulthandler, os, sys, tempfile
TREE, OUT = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp(prefix="probe-click-")
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
window.run_operation(REGISTRY.get("create_brep_box"))
settle(app, 10)
d = [c for c in window.findChildren(OperationDialog) if c.isVisible()][0]
d.accept(); idle()
entry = next(iter(window.session.last_result.scene.objects.values()))
b = entry.mesh.bounds
point = ((b.minimum[0] + b.maximum[0]) / 2, (b.minimum[1] + b.maximum[1]) / 2, b.maximum[2])
say("nach dem Anlegen gewählt:", window.object_tree.selected_objects(), "Tiefe", window.viewport.selection_depth())
say("Klickziel auf der Oberseite:", window.viewport._click_target(point))
window.viewport._select_at(point); idle()
say("nach dem Klick: Tiefe", window.viewport.selection_depth(), "Merkmal", window.viewport.selected_feature)
say("  Kopf:", panel.summary.text(), "| vorn:", [x.text() for x in panel._quick_buttons.values() if not x.isHidden()])
say("  Liste an der Fläche:", [b.text().replace(chr(10)," ") for _s,_t,bs in panel._groups.values() for b in bs if not b.isHidden()])
button = panel._list_twins["hollow_object"]
say("  Knopf Aushöhlen: sichtbar", not button.isHidden(), "frei", button.isEnabled())
button.click(); settle(app, 10)
dialogs = [c for c in window.findChildren(OperationDialog) if c.isVisible()]
say("  Dialog:", bool(dialogs), "Öffnungen:", dialogs[0].values().get("openings") if dialogs else None, "oben offen:", dialogs[0].values().get("open_top") if dialogs else None)
if dialogs:
    dialogs[0].accept(); idle()
    body = next(iter(window.session.last_result.scene.objects.values()))
    say("  nach Übernehmen: Schritte", [o.op for o in window.session.project.document.ops], "Volumen", round(float(body.mesh.volume), 1))
say("fertig")
out.close(); os._exit(0)
