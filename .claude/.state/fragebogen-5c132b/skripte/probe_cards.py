"""Sonde: verschiebbare Karten am Fenster (offscreen)."""

from __future__ import annotations

import faulthandler
import os
import sys
import tempfile

TREE, OUT = sys.argv[1], sys.argv[2]
tmp = tempfile.mkdtemp(prefix="probe-cards-")
os.environ["APPDATA"] = os.path.join(tmp, "roaming")
os.environ["LOCALAPPDATA"] = os.path.join(tmp, "local")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, TREE)
faulthandler.dump_traceback_later(300, exit=True)
out = open(OUT, "w", encoding="utf-8", buffering=1)


def say(*p):
    out.write(" ".join(str(x) for x in p) + "\n")


from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
import app.ui.overlay as O  # noqa: E402

say("gemessen wird", O.__file__)
O.MOVE_MS = 0
from app.core.scene import OperationDraft  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.overlay import (  # noqa: E402
    EDGE,
    LEFT_MAX,
    LEFT_WIDTH,
    MARGIN,
    CardPlace,
    card_width,
)
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

sys.path.insert(0, os.path.join(TREE, "tools"))
from run_ui_audit import settle, silence_questions  # noqa: E402

window = MainWindow(Session(), UiSettings())
window.resize(1600, 1000)
window.show()
silence_questions(window.session, window)
settle(app, 10)
window.session.apply("Körper", [OperationDraft(op="create_box")])
for _ in range(40):
    settle(app, 5)
    if window.session.wait_for_idle():
        break
settle(app, 20)
host = window.overlay
left, right = host.left, host.right


def state(label):
    settle(app, 10)
    vp = window.viewport
    say(
        f"{label}: links-Zone {left.geometry().getRect()} dock={left.property('dock')!r} | "
        f"rechts-Zone {right.geometry().getRect()} dock={right.property('dock')!r} | "
        f"Ränder {vp._zone_margins} | Plätze { {k: v.text() for k, v in host.places.items()} }"
    )


W = host.width()
state("Stamm")
lw = card_width(LEFT_WIDTH, LEFT_MAX, W)
rw = host._right_width(W)
say("  erwartet alt: links x=0 w=", lw, " rechts x=", W - rw - EDGE, " Ränder", (lw + EDGE + MARGIN, rw + EDGE + MARGIN))
vb = window.viewport.view_bar.geometry()
say("  Ansichtsleiste", vb.getRect(), "schneidet rechte Karte:", vb.intersects(right.geometry()))

saved = []
host.placesChanged.connect(lambda places: saved.append(places))
notices = []
host.cardNotice.connect(notices.append)

host.put_card("right", CardPlace("left"))
state("rechte Karte an den linken Rand (Tausch)")
say("  Einstellung:", window.settings.card_places, "Quittung:", notices[-1])

host.put_card("left", CardPlace("", 0.5, 0.2))
state("linke Karte schwebt in der Mitte")
say("  Quittung:", notices[-1])

host.put_card("right", CardPlace("", 0.5, 0.2))
state("rechte Karte will auf dieselbe Stelle")
say("  Quittung:", notices[-1])

window.action_reset_cards()
state("zurückgesetzt")
say("  Quittung:", notices[-1], "Einstellung:", window.settings.card_places)

# Ziehen mit der Maus über den Griff
grip_left, grip_right = window.card_grips
say("Griffe:", grip_left.geometry().getRect(), grip_left.isVisibleTo(window), grip_right.isVisibleTo(window), grip_right.accessibleName(), "|", grip_right.accessibleDescription())
hints = []
host.dragHint.connect(hints.append)
start = grip_right.mapToGlobal(grip_right.rect().center())
QTest.mousePress(grip_right, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip_right.rect().center())
target = start - QPoint(600, -100)
QTest.mouseMove(grip_right, grip_right.mapFromGlobal(start - QPoint(30, 0)))
QTest.mouseMove(grip_right, grip_right.mapFromGlobal(target))
settle(app, 5)
outline = [w for w in host.findChildren(type(left)) if w.objectName() == O.OUTLINE]
say("  beim Ziehen: Hinweis", hints[-1] if hints else None, "Umriss sichtbar:", [w.isVisibleTo(host) for w in outline], "zieht:", host.dragging())
QTest.mouseRelease(grip_right, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip_right.mapFromGlobal(target))
state("nach dem Zug mit der Maus")
say("  Hinweis danach leer:", hints[-1] == "", "Umriss weg:", not any(w.isVisibleTo(host) for w in outline))

# Escape bricht ab
before = dict(host.places)
QTest.mousePress(grip_right, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip_right.rect().center())
QTest.mouseMove(grip_right, grip_right.rect().center() - QPoint(200, 0))
grip_right.setFocus()
QTest.keyClick(grip_right, Qt.Key.Key_Escape)
QTest.mouseRelease(grip_right, Qt.MouseButton.LeftButton)
say("Escape: Plätze unverändert", host.places == before, "zieht:", host.dragging())

# Doppelklick legt zurück
QTest.mouseDClick(grip_right, Qt.MouseButton.LeftButton)
state("nach Doppelklick")

# Tastatur
grip_left.setFocus()
QTest.keyClick(grip_left, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
state("Umschalt+Pfeil rechts an der linken Karte")
QTest.keyClick(grip_left, Qt.Key.Key_Down)
state("Pfeil runter")
menu = grip_left.place_menu()
say("Menü:", [a.text() for a in menu.actions()])
menu.actions()[2].trigger()
menu.deleteLater()
state("Menü: an ihren Platz")

# schmales Fenster: eigene Anordnung überdeckt sich -> vorübergehend Stamm
host.put_card("left", CardPlace("", 1.0, 0.0))
state("linke Karte schwebt ganz rechts (neben der rechten)")
window.resize(800, 700)
settle(app, 20)
state("Fenster 800 breit")
window.resize(1600, 1000)
settle(app, 20)
state("wieder 1600")
window.action_reset_cards()

# Ansichtsleiste bei hoher rechter Karte
window.right_column.setVisible(True)
settle(app, 10)
vb = window.viewport.view_bar.geometry()
say("Ansichtsleiste", vb.getRect(), "rechte Karte", right.geometry().getRect(), "schneidet:", vb.intersects(right.geometry()))
say("fertig")
out.close()
os._exit(0)
