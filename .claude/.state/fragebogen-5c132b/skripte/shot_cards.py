"""Bild: Griffe und schwebende Karte auf der echten Plattform (ohne Bildschirm)."""

from __future__ import annotations

import faulthandler
import os
import sys
import tempfile

TREE, OUTDIR = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp(prefix="shot-cards-")
os.environ["APPDATA"] = os.path.join(tmp, "roaming")
os.environ["LOCALAPPDATA"] = os.path.join(tmp, "local")
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, TREE)
faulthandler.dump_traceback_later(240, exit=True)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
import app.ui.overlay as O  # noqa: E402

O.MOVE_MS = 0
from app.core.scene import OperationDraft  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.overlay import CardPlace  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402
from app.ui.style import apply_style  # noqa: E402
from app.ui.theme import apply_theme  # noqa: E402

apply_theme(app, "dark")
apply_style(app, "dark")
window = MainWindow(Session(), UiSettings())
window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
window.resize(1600, 1000)
window.show()
for _ in range(30):
    app.processEvents()
window.session.apply("Körper", [OperationDraft(op="create_box")])
window.session.wait_for_idle()
for _ in range(60):
    app.processEvents()
first = next(iter(window.session.last_result.scene.objects))
window.object_tree.select_object(first)
for _ in range(30):
    app.processEvents()
window.grab().save(os.path.join(OUTDIR, "karten-stamm.png"))
window.overlay.put_card("right", CardPlace("", 0.45, 0.15))
for _ in range(30):
    app.processEvents()
window.grab().save(os.path.join(OUTDIR, "karten-schwebend.png"))
window.overlay.put_card("right", CardPlace("left"))
for _ in range(30):
    app.processEvents()
window.grab().save(os.path.join(OUTDIR, "karten-getauscht.png"))
print("fertig", flush=True)
os._exit(0)
