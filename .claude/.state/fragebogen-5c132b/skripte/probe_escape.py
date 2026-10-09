"""Sonde: Escape während des Ziehens — was ändert die Plätze?"""

from __future__ import annotations

import os
import sys
import tempfile

TREE, OUT = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp(prefix="probe-esc-")
os.environ["APPDATA"] = os.path.join(tmp, "roaming")
os.environ["LOCALAPPDATA"] = os.path.join(tmp, "local")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, TREE)
out = open(OUT, "w", encoding="utf-8", buffering=1)


def say(*p):
    out.write(" ".join(str(x) for x in p) + "\n")


from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
import app.ui.overlay as O  # noqa: E402

O.MOVE_MS = 0
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

sys.path.insert(0, os.path.join(TREE, "tools"))
from run_ui_audit import settle  # noqa: E402

window = MainWindow(Session(), UiSettings())
window.resize(1600, 1000)
window.show()
settle(app, 10)
host = window.overlay
grip = window.card_grips[1]
calls = []
real_put = host.put_card


def spy(key, place):
    import traceback

    calls.append((key, place, "".join(traceback.format_stack(limit=6))))
    return real_put(key, place)


host.put_card = spy
say("vorher", host.places)
QTest.mousePress(grip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip.rect().center())
QTest.mouseMove(grip, grip.rect().center() - QPoint(200, 0))
say("nach Bewegung: zieht", host.dragging(), "Griff zieht", grip._dragging)
grip.setFocus()
say("nach setFocus: zieht", host.dragging())
QTest.keyClick(grip, Qt.Key.Key_Escape)
say("nach Escape: zieht", host.dragging(), host.places)
QTest.mouseRelease(grip, Qt.MouseButton.LeftButton)
say("nach Loslassen", host.places)
for key, place, stack in calls:
    say("put_card", key, place)
    say(stack)
out.close()
os._exit(0)
