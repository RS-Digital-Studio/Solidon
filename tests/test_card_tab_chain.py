"""Tab von der Reiterleiste der rechten Karte geht in die Seite, die vorn steht (FD-177).

Qt reiht Widgets nach ihrer Entstehung in die Fokuskette, nicht nach dem
Bild. Bericht und Auswahl entstehen vor der Reiterleiste, ihre Felder später
oder an anderer Stelle: Vom Reiter *Prüfbericht* sprang Tab zur Kopfzeile und
in die linke Karte, vom Reiter *Auswahl* zuerst zu den Handlungen unten und
dann in die Kopfzeile, bevor das Merkmalfenster oben kam.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from app.ui.main_window import MainWindow
from tests.test_feature_footer_window import a_hole as a_hole


def _tab_from_the_bar(qt_app: QApplication, window: MainWindow, times: int = 1) -> QWidget:
    bar = window.right_tabs
    bar.setFocus(Qt.FocusReason.TabFocusReason)
    qt_app.processEvents()
    for _press in range(times):
        focused = QApplication.focusWidget()
        assert focused is not None
        QTest.keyClick(focused, Qt.Key.Key_Tab)
        qt_app.processEvents()
    focused = QApplication.focusWidget()
    assert focused is not None
    return focused


def _name(widget: QWidget) -> str:
    return f"{type(widget).__name__} {widget.objectName()} {widget.accessibleName()!r}"


def test_tab_from_the_report_tab_goes_into_the_report(qt_app: QApplication, a_hole) -> None:
    window = a_hole
    window.right.setCurrentWidget(window.report)
    qt_app.processEvents()

    reached = _tab_from_the_bar(qt_app, window)

    assert window.report.isAncestorOf(reached), _name(reached)


def test_tab_from_the_selection_tab_starts_at_the_top_of_the_page(
    qt_app: QApplication, a_hole
) -> None:
    window = a_hole
    assert window.right.currentIndex() == 0, "Voraussetzung: die Auswahl steht vorn"

    reached = _tab_from_the_bar(qt_app, window)

    assert window.feature_panel.isAncestorOf(reached), _name(reached)


def test_the_selection_page_is_walked_top_down_before_the_card_is_left(
    qt_app: QApplication, a_hole
) -> None:
    """Erst das Merkmalfenster, dann die Handlungen darunter — nie die Kopfzeile dazwischen."""
    window = a_hole
    bar = window.right_tabs
    bar.setFocus(Qt.FocusReason.TabFocusReason)
    qt_app.processEvents()
    places: list[str] = []
    for _press in range(200):
        focused = QApplication.focusWidget()
        assert focused is not None
        QTest.keyClick(focused, Qt.Key.Key_Tab)
        qt_app.processEvents()
        focused = QApplication.focusWidget()
        assert focused is not None
        if window.feature_panel.isAncestorOf(focused):
            place = "merkmal"
        elif window.selection_operations.isAncestorOf(focused):
            place = "handlungen"
        else:
            break
        if not places or places[-1] != place:
            places.append(place)
    assert places == ["merkmal", "handlungen"], places
