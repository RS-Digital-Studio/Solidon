"""Der Wächter gegen offen gelassene Fenster erkennt sie und räumt sie ab (FD-191).

Der Wächter selbst ist eine Fixture in ``tests/conftest.py``; hier steht, was
er fragt (``tests/window_leftovers.py``), an einem gepflanzten Dialog.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog, QMenu

from tests import window_leftovers


def test_a_dialog_left_open_is_named_and_closed(qt_app: QApplication) -> None:
    before = window_leftovers.visible_windows()
    planted = QDialog()
    planted.setWindowTitle("Gepflanzt")
    planted.show()
    qt_app.processEvents()
    left = window_leftovers.leftovers({id(widget) for widget in before})
    assert left == [planted]
    assert "QDialog „Gepflanzt“" in window_leftovers.describe(left)
    window_leftovers.close_all(left)
    assert not planted.isVisible()
    assert window_leftovers.leftovers({id(widget) for widget in before}) == []


def test_a_menu_is_no_window_of_the_test(qt_app: QApplication) -> None:
    """Menüs und Kurzhilfen zählt der Prüfstand nicht als Fenster, der Wächter auch nicht."""
    before = window_leftovers.visible_windows()
    menu = QMenu()
    menu.addAction("Eintrag")
    menu.popup(menu.pos())
    qt_app.processEvents()
    try:
        assert window_leftovers.leftovers({id(widget) for widget in before}) == []
    finally:
        menu.close()
        menu.deleteLater()


#: Ein Fall, der einen Dialog zeigt und festhält — gepflanzt in einen eigenen Lauf.
PLANTED = """
from PySide6.QtWidgets import QDialog

KEEP = []


def test_leaves_a_dialog_open(qt_app):
    dialog = QDialog()
    dialog.setWindowTitle("Gepflanzt")
    dialog.show()
    qt_app.processEvents()
    KEEP.append(dialog)
"""


def test_the_guard_reds_the_case_that_leaves_a_window_open(tmp_path: Path) -> None:
    """Die Verdrahtung des Wächters in ``conftest.py``: ein eigener Lauf mit
    gepflanztem Fall endet mit „ERROR at teardown“ und der Meldung FD-191
    (Review 2 Restpaket A, L3c)."""
    planted = tmp_path / "test_planted_leftover.py"
    planted.write_text(PLANTED, encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    finished = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "tests.conftest",
            "--rootdir",
            str(tmp_path),
            str(planted),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    output = finished.stdout + finished.stderr
    assert finished.returncode == 1, output
    assert "ERROR at teardown of test_leaves_a_dialog_open" in output, output
    assert "Gepflanzt" in output and "FD-191" in output, output
