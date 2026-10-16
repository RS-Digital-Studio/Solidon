"""Der Wächter gegen offen gelassene Fenster erkennt sie und räumt sie ab (FD-191).

Der Wächter selbst ist eine Fixture in ``tests/conftest.py``; hier steht, was
er fragt (``tests/window_leftovers.py``), an einem gepflanzten Dialog.
"""

from __future__ import annotations

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
