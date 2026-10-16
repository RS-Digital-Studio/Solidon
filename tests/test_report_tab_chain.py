"""Die Tabulatortaste erreicht im Prüfbericht die angebotene Handlung (FD-139, FD-140).

Der Funktionsdurchgang maß an *Auf das Bett setzen* eine Kette, die am
Rollbereich des Berichts (``overlay.FittedScroller``) begann und von dort
gleich zum Reiter der Karte sprang: Der Rollbereich war ein eigener Tab-Halt
ohne Namen, und die Knöpfe darunter erreichte die Tastatur nicht. Gedrückt
wird hier wie ein Kunde — Tab am Fokuswidget, gelesen über ``focusWidget()``,
nicht aus ``nextInFocusChain``.

Die Fläche ist die kleinste, für die Solidon gebaut ist: 1920 × 1080 logisch.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QPushButton, QScrollArea, QWidget

from app.core import guides
from app.core.scene.project import save
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import wait_for_print_findings
from tools import function_scenes

#: Die kleinste Arbeitsfläche (Festlegung Robert, Bauplan §19.3).
SMALLEST = (1920, 1080)

#: So viele Tabs geht die Probe höchstens, bevor sie aufgibt.
MOST_TABS = 40


@pytest.fixture
def below_the_bed(qt_app: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    """Der Würfel halb unter dem Bett, gezeigt, mit dem Befund im Bericht."""
    path = tmp_path / "unter_dem_bett.p3d"
    save(function_scenes.build_scene("unter_dem_bett.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(*SMALLEST)
    window.show()
    window._show_start_screen(False)
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


def _choose_the_finding(window: MainWindow) -> QPushButton:
    """Reiter *Prüfbericht*, Liste auf, Befundzeile gewählt — der Knopf darunter."""
    tabs = window.right
    tabs.setCurrentIndex(next(i for i in range(tabs.count()) if tabs.widget(i) is window.report))
    report = window.report
    if not report.list_toggle.isChecked():
        report.list_toggle.click()
    row = next(
        report.list.item(i)
        for i in range(report.list.count())
        if report.list.item(i).data(Qt.ItemDataRole.UserRole).code == "arrange.below_bed"
    )
    report.list.setCurrentItem(row)
    QApplication.processEvents()
    return next(
        entry
        for entry in report.findChildren(QPushButton)
        if entry.property(guides.TARGET_PROPERTY) == "finding.action:place_on_bed"
        and entry.isVisibleTo(report)
    )


def _tabs_from(start: QWidget) -> list[QWidget]:
    """Tab am Fokuswidget, bis der Fokus wiederkommt oder die Probe aufgibt."""
    start.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    seen: list[QWidget] = []
    for _press in range(MOST_TABS):
        focused = QApplication.focusWidget()
        assert focused is not None, "der Fokus ging verloren"
        if focused in seen:
            break
        seen.append(focused)
        QTest.keyClick(focused, Qt.Key.Key_Tab)
        QApplication.processEvents()
    return seen


def _stops(report: QWidget) -> list[QWidget]:
    """Was im Bericht gerade einen Tab annimmt — gesucht über die Kinder, nicht die Kette."""
    return [
        widget
        for widget in report.findChildren(QWidget)
        if widget.isVisible()
        and widget.isEnabled()
        and widget.focusPolicy() & Qt.FocusPolicy.TabFocus
    ]


def test_tab_reaches_the_offered_action_from_every_stop_before_it(
    qt_app: QApplication, below_the_bed: MainWindow
) -> None:
    """Wo im Bericht der Fokus vor der Handlung auch steht, Tab erreicht *Auf das Bett setzen*.

    Gemessen wurde die Kette ab dem ersten Halt des Berichts, dem Rollbereich,
    und von dort sprang sie zum Reiter der Karte (FD-140).
    """
    window = below_the_bed
    window.activateWindow()
    button = _choose_the_finding(window)
    report = window.report
    later = {report.to_slicer, report.export_button}
    later.update(
        entry for entry in report.findChildren(QPushButton) if entry.parent() is button.parent()
    )
    missed: list[str] = []
    for start in _stops(report):
        if start in later:
            continue
        chain = _tabs_from(start)
        inside = []
        for widget in chain:
            if not report.isAncestorOf(widget):
                break
            inside.append(widget)
        if button not in inside:
            missed.append(" → ".join(type(widget).__name__ for widget in chain[: len(inside) + 1]))
    assert not missed, f"Tab verlässt den Bericht vor der Handlung: {missed}"


def test_no_scroll_area_of_the_report_is_a_tab_stop_without_a_name(
    qt_app: QApplication, below_the_bed: MainWindow
) -> None:
    """Ein Rollbereich ist kein Halt, oder er trägt Namen und Beschreibung (FD-139)."""
    window = below_the_bed
    window.activateWindow()
    _choose_the_finding(window)
    report = window.report
    report.review_toggle.click()
    QApplication.processEvents()
    nameless = [
        type(widget).__name__
        for widget in _stops(report)
        if isinstance(widget, QAbstractScrollArea)
        and isinstance(widget, QScrollArea)
        and not (widget.accessibleName() and widget.accessibleDescription())
    ]
    assert report.review_scroll.isVisible(), "der Prüfumfang ging nicht auf"
    assert not nameless, f"Rollbereiche ohne Namen als Tab-Halt: {nameless}"
