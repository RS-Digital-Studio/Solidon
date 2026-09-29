"""RM-269 (1): Öffnet ein Klick auf „Zuletzt geöffnet" das Projekt?

Echte Plattform, Fenster mit WA_DontShowOnScreen. Aufruf: python s269_zuletzt.py <baum>
"""
import os
import sys
import tempfile
import threading
from pathlib import Path

TREE = sys.argv[1]
sys.path.insert(0, TREE)
_guard = threading.Timer(240, lambda: os._exit(9))
_guard.daemon = True
_guard.start()
tmp = tempfile.mkdtemp(prefix="s269-")
os.environ["APPDATA"] = tmp
os.environ["LOCALAPPDATA"] = tmp
import app  # noqa: E402

print("app:", app.__file__, flush=True)
assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve())

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QStyle  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.ui.app import build_application  # noqa: E402
from app.ui.start_screen import StartScreen  # noqa: E402

built = build_application([])
qt = QApplication.instance()
print("build_application:", type(built).__name__, flush=True)
screen = StartScreen()
screen.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
screen.show_recent([Path(tmp) / "a.p3d", Path(tmp) / "b.p3d"])
screen.resize(1200, 900)
screen.show()
QApplication.processEvents()
print("Stil:", qt.style().name(), "Einzelklick aktiviert:",
      qt.style().styleHint(QStyle.StyleHint.SH_ItemView_ActivateItemOnSingleClick))
opened: list[str] = []
screen.openRequested.connect(lambda path: opened.append(Path(path).name))
view = screen.recent_list
spot = view.visualItemRect(view.item(0)).center()


def step(name, action):
    opened.clear()
    action()
    for _ in range(5):
        QApplication.processEvents()
    QTest.qWait(QApplication.doubleClickInterval() + 50)
    print(f"{name}: {opened}", flush=True)


step("Einfachklick", lambda: QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=spot))
step("Doppelklick", lambda: (QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=spot),
                             QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, pos=spot)))
view.setCurrentRow(1)
view.setFocus()
step("Eingabetaste", lambda: QTest.keyClick(view, Qt.Key.Key_Return))
print("Mauszeiger:", view.viewport().cursor().shape(), flush=True)
screen.hide()
screen.deleteLater()
QApplication.processEvents()
os._exit(0)
