"""Nach einer Befundhandlung nimmt Strg+Z den Schritt zurück (FD-4, Bauplan §19.2).

Nach *Auf das Bett setzen* im Prüfbericht holte die wiederhergestellte Auswahl
den Reiter *Auswahl* nach vorn, und der Fokus fiel dort in das Suchfeld. Ein
leeres ``QLineEdit`` beansprucht Strg+Z trotzdem für sich (``ShortcutOverride``),
und die Tastatur des Kunden nahm nichts zurück. Geprüft wird beides: dass der
Bericht vorn bleibt und der Fokus bei ihm, und dass ein Textfeld ohne
Rücknehmbares die Taste an das Fenster durchlässt.

Die Fläche ist die kleinste, für die Solidon gebaut ist: 1920 × 1080 logisch.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget

from app.core import guides
from app.core.scene.project import save
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import wait_for_print_findings, wait_until
from tools import function_scenes

#: Die kleinste Arbeitsfläche (Festlegung Robert, Bauplan §19.3).
SMALLEST = (1920, 1080)


@pytest.fixture
def below_the_bed(qt_app: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    """Der Würfel halb unter dem Bett, gezeigt und mit dem Befund im Bericht."""
    path = tmp_path / "unter_dem_bett.p3d"
    save(function_scenes.build_scene("unter_dem_bett.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(*SMALLEST)
    window.show()
    window._show_start_screen(False)
    window.activateWindow()
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    wait_for_print_findings(window)
    qt_app.processEvents()
    yield window
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def _ops(window: MainWindow) -> list[str]:
    return [entry.op for entry in window.session.project.document.ops]


def _show_the_report(window: MainWindow) -> None:
    """Wie der Kunde: den Reiter *Prüfbericht* anklicken, die Liste aufklappen."""
    tabs = window.right
    index = next(i for i in range(tabs.count()) if tabs.widget(i) is window.report)
    tabs.setCurrentIndex(index)
    if not window.report.list_toggle.isChecked():
        window.report.list_toggle.click()
    QApplication.processEvents()


def _press_place_on_bed(qt_app: QApplication, window: MainWindow) -> None:
    """Die Befundzeile anklicken, dann *Auf das Bett setzen* — und warten wie das Fenster."""
    _show_the_report(window)
    report = window.report
    row = next(
        report.list.item(i)
        for i in range(report.list.count())
        if report.list.item(i).data(Qt.ItemDataRole.UserRole).code == "arrange.below_bed"
    )
    QTest.mouseClick(
        report.list.viewport(),
        Qt.MouseButton.LeftButton,
        pos=report.list.visualItemRect(row).center(),
    )
    qt_app.processEvents()
    button = next(
        entry
        for entry in report.findChildren(QPushButton)
        if entry.property(guides.TARGET_PROPERTY) == "finding.action:place_on_bed"
        and entry.isVisible()
    )
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    wait_until(qt_app, lambda: "place_on_bed" in _ops(window))
    assert window.session.wait_for_idle(60_000)
    wait_for_print_findings(window)
    qt_app.processEvents()


def _ctrl_z_at_the_focus(window: MainWindow) -> None:
    """Strg+Z an das Fokuswidget — so kommt die Taste des Kunden an."""
    target: QWidget = QApplication.focusWidget() or window
    QTest.keyClick(target, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()


def test_after_a_finding_action_the_report_keeps_the_focus_and_ctrl_z_undoes_it(
    qt_app: QApplication, below_the_bed: MainWindow
) -> None:
    """Der Bericht bleibt vorn, der Fokus bei ihm, und Strg+Z nimmt den Schritt zurück."""
    window = below_the_bed
    _press_place_on_bed(qt_app, window)
    assert _ops(window) == ["load", "place_on_bed"]

    assert not window.feature_dock.is_current(), (
        "die wiederhergestellte Auswahl ist keine neue — der Bericht bleibt vorn"
    )
    focus = QApplication.focusWidget()
    assert focus is not None and window.report.isAncestorOf(focus), (
        f"der Fokus gehört nach der Handlung in den Bericht, nicht nach {focus!r}"
    )

    _ctrl_z_at_the_focus(window)
    assert _ops(window) == ["load"], "Strg+Z am Fokus hat den Schritt nicht zurückgenommen"


def test_an_empty_search_field_lets_ctrl_z_and_ctrl_y_through(
    qt_app: QApplication, below_the_bed: MainWindow
) -> None:
    """Das Suchfeld der Auswahl nimmt nur sein eigenes Tippen zurück, sonst den Schritt."""
    window = below_the_bed
    _press_place_on_bed(qt_app, window)
    window.object_tree.select_object(window.object_tree.selected_objects()[0])
    window.feature_dock.reveal()
    qt_app.processEvents()
    search = window.selection_operations.search
    search.setFocus(Qt.FocusReason.OtherFocusReason)
    wait_until(qt_app, search.hasFocus)

    # Leer und unberührt: Die Taste gilt dem Verlauf, Wiederholen ebenso.
    QTest.keyClick(search, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window.session.wait_for_idle(60_000)
    assert _ops(window) == ["load"], "das leere Suchfeld hat Strg+Z geschluckt"
    QTest.keyClick(search, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert window.session.wait_for_idle(60_000)
    assert _ops(window) == ["load", "place_on_bed"], "das leere Suchfeld hat Strg+Y geschluckt"

    # Getippt: Strg+Z nimmt das Tippen zurück und lässt den Verlauf stehen.
    QTest.keyClicks(search, "bohr")
    QTest.keyClick(search, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window.session.wait_for_idle(60_000)
    assert search.text() != "bohr", "Strg+Z im Feld nimmt das Getippte zurück"
    assert _ops(window) == ["load", "place_on_bed"]

    # Escape leert das Feld ohne Rest: Danach gilt Strg+Z wieder dem Verlauf.
    QTest.keyClicks(search, "bohr")
    QTest.keyClick(search, Qt.Key.Key_Escape)
    assert search.text() == "" and search.hasFocus()
    QTest.keyClick(search, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window.session.wait_for_idle(60_000)
    assert _ops(window) == ["load"], "nach Escape hielt das Suchfeld seinen alten Text fest"


def test_the_filter_asks_the_field_and_not_the_class(qt_app: QApplication) -> None:
    """Die Regel selbst: ein Feld ohne Rücknehmbares lässt durch, eines mit nicht."""
    from app.ui.shortcut_schemes import install_navigation_keys, nothing_to_take_back

    install_navigation_keys()
    field = QLineEdit()
    undo = QKeyEvent(
        QKeyEvent.Type.ShortcutOverride, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier
    )
    plain = QKeyEvent(QKeyEvent.Type.ShortcutOverride, Qt.Key.Key_Z, Qt.KeyboardModifier.NoModifier)
    assert nothing_to_take_back(undo, field)
    assert not nothing_to_take_back(plain, field), "nur Rückgängig und Wiederholen"
    field.insert("M4")
    assert not nothing_to_take_back(undo, field), "Getipptes nimmt das Feld selbst zurück"
    field.setReadOnly(True)
    assert not nothing_to_take_back(undo, field), "ein Lesefeld beansprucht nichts"
    assert not nothing_to_take_back(undo, QWidget()), "kein Textfeld, keine Frage"
    field.deleteLater()
