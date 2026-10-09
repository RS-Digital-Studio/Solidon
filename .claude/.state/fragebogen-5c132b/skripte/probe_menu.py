"""Sonde: Rechtsklickmenü mit Entfernen/Vereinigen, Mehrfachauswahl bleibt, Mehrfachlöschen."""
from __future__ import annotations
import faulthandler, os, sys, tempfile
TREE, OUT = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp(prefix="probe-menu-")
os.environ["APPDATA"] = os.path.join(tmp, "roaming")
os.environ["LOCALAPPDATA"] = os.path.join(tmp, "local")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, TREE)
faulthandler.dump_traceback_later(300, exit=True)
out = open(OUT, "w", encoding="utf-8", buffering=1)
def say(*p): out.write(" ".join(str(x) for x in p) + "\n")
from PySide6.QtWidgets import QApplication, QMenu
app = QApplication([])
from app.core.bootstrap import load_operations
load_operations()
import app.ui.main_window as M
say("gemessen wird", M.__file__)
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
shown = []
def fake_exec(self, *args, **kwargs):
    shown.append([(a.text(), a.isEnabled(), a.toolTip()) for a in self.actions() if not a.isSeparator()])
    return None
window = MainWindow(Session(), UiSettings())
window.resize(1500, 950); window.show()
silence_questions(window.session, window); settle(app, 10)
def boxes(n):
    window.session.apply("Körper", [OperationDraft(op="create_brep_box") for _ in range(n)])
    idle()
    return list(window.session.last_result.scene.objects)
ids = boxes(2)
tree = window.object_tree
view = tree.tree
_real_menu = type(tree).context_menu
class _Shown:
    def __init__(self, menu):
        self.menu = menu
    def exec(self, *a, **k):
        shown.append([(x.text(), x.isEnabled(), x.toolTip()) for x in self.menu.actions() if not x.isSeparator()])
    def deleteLater(self):
        self.menu.deleteLater()
def _wrapped():
    m = _real_menu(tree)
    return _Shown(m) if m is not None else None
tree.context_menu = _wrapped
tree.select_objects(ids); settle(app, 10)
say("Auswahl:", tree.selected_objects())
item = view.topLevelItem(1)
view.setCurrentItem(item, 0, view.selectionModel().SelectionFlag.NoUpdate) if False else None
tree._on_context_menu(view.visualItemRect(item).center())
settle(app, 5)
say("Rechtsklick auf markierte Zeile, Auswahl danach:", tree.selected_objects())
say("Menü:", shown[-1] if shown else None)
menu = _real_menu(tree)
union = next(a for a in menu.actions() if a.text().startswith("Vereinigen"))
union.trigger(); idle()
say("nach Vereinigen: Objekte", list(window.session.last_result.scene.objects), "Schritte", [o.op for o in window.session.project.document.ops])
menu.deleteLater(); settle(app, 3)
window.session.undo(); idle()
ids = list(window.session.last_result.scene.objects)
tree.select_objects(ids); settle(app, 5)
menu = _real_menu(tree)
removal = [a for a in menu.actions() if a.text().startswith("Objekt entfernen")]
say("Entfernen-Eintrag:", [(a.text(), a.isEnabled()) for a in removal])
removal[0].trigger(); idle()
say("nach Entfernen mit zwei markierten: Objekte", list(window.session.last_result.scene.objects), "Schritte", [o.op for o in window.session.project.document.ops])
window.session.undo(); idle()
say("nach einem Strg+Z: Objekte", list(window.session.last_result.scene.objects))
menu.deleteLater(); settle(app, 3)
# Rechtsklick auf eine nicht markierte Zeile wählt nur sie
ids = list(window.session.last_result.scene.objects)
tree.select_object(ids[0]); settle(app, 5)
tree._on_context_menu(view.visualItemRect(view.topLevelItem(1)).center()); settle(app, 5)
say("Rechtsklick auf andere Zeile, Auswahl danach:", tree.selected_objects(), "Menü:", shown[-1])
# an einer Fläche
entry = window.session.last_result.scene.objects[ids[0]]
face = next(fid for fid, f in entry.features.items() if f.kind == "face")
tree.select_feature(ids[0], face); settle(app, 5)
menu = _real_menu(tree)
say("Menü an Fläche:", [(a.text(), a.isEnabled()) for a in menu.actions() if not a.isSeparator()])
say("fertig")
out.close(); os._exit(0)
