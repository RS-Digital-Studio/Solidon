"""Karten an den unteren Rand und Reiter in eigene Fenster verschieben (§2.5)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QMainWindow

from app.ui.overlay import CardPlace, CurrentPageTabs, card_rect, dropped_place, settled_places
from app.ui.tab_signal import SignalTabBar
from app.ui.tab_windows import reachable_geometry


@pytest.mark.parametrize(
    "edge,across", [("bottom-left", 0.0), ("bottom-right", 0.0), ("bottom", 0.4)]
)
def test_lower_cards_roundtrip_and_keep_their_bottom(edge, across):
    place = CardPlace(edge, across)
    assert CardPlace.read(place.text(), "left") == place
    for width, room in [(1200, 800), (640, 480)]:
        for size in [QSize(260, 300), QSize(260, 900)]:
            rect = card_rect(place, width, room, size)
            assert rect.bottom() == room - 1
            assert QRect(0, 0, width, room).contains(rect)
            assert dropped_place(rect, width, room).edge == edge


def test_two_lower_corners_can_coexist_and_swap():
    places = {"left": CardPlace("bottom-left"), "right": CardPlace("bottom-right")}
    sizes = {"left": QSize(250, 300), "right": QSize(350, 300)}
    result = settled_places("left", CardPlace("bottom-right"), places, sizes, 1200, 800)
    assert result == {"left": CardPlace("bottom-right"), "right": CardPlace("bottom-left")}


@pytest.mark.parametrize(
    "saved",
    [None, [], [0, 0, 0, 20], [True, 1, 20, 20], [0, 0, float("nan"), 5], [0, 0, 1_000_000, 2]],
)
def test_invalid_saved_windows_are_not_restored(saved):
    assert reachable_geometry(saved, [QRect(0, 0, 1920, 1080)]) is None


def test_a_missing_monitor_returns_the_whole_window_to_a_present_screen():
    screen = QRect(0, 0, 1366, 768)
    rect = reachable_geometry([2100, 900, 1800, 1000], [screen])
    assert rect is not None and screen.contains(rect)
    second = QRect(-1920, 0, 1920, 1080)
    original = [-1800, 100, 500, 600]
    assert reachable_geometry(original, [screen, second]) == QRect(*original)


@pytest.fixture
def tabs(qt_app):
    window = QMainWindow()
    tabs = CurrentPageTabs(window)
    tabs.setTabBar(SignalTabBar(tabs))
    window.setCentralWidget(tabs)
    first, second = QLineEdit("unveränderter Entwurf"), QLineEdit("zweiter Inhalt")
    tabs.addTab(first, "Erster")
    tabs.addTab(second, "Zweiter")
    tabs.configure_pages({"first": first, "second": second}, {})
    window.resize(800, 600)
    window.show()
    QApplication.processEvents()
    yield tabs, first, second
    tabs.shutdown_windows()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_detaching_and_closing_preserve_page_identity_and_unsaved_text(tabs):
    tabs, first, second = tabs
    first.setText("noch nicht übernommen")
    tabs.detach_page(first, QPoint(100, 100))
    floating = first.window()
    assert floating.isWindow() and floating is not tabs.window()
    assert tabs.widget(tabs.indexOf(first)) is first
    assert tabs.currentWidget() is first
    first.setText("im eigenen Fenster geändert")
    floating.close()
    QApplication.processEvents()
    assert first.window() is tabs.window()
    assert first.text() == "im eigenen Fenster geändert"
    assert tabs.indexOf(second) == 1
    assert tabs.layout_state()["windows"] == {}


def test_tab_order_and_signal_badges_follow_the_page(tabs):
    tabs, _first, second = tabs
    bar = tabs.tabBar()
    bar.show_counts(1, 2, 3)
    badge = bar.badge(1)
    bar.signal(1, error=True, warning=True, fresh=False)
    bar.point_at(1)
    bar.moveTab(1, 0)
    assert tabs.widget(0) is second
    assert bar.badge(0) is badge
    assert bar.unseen(0), "eine Umordnung liest keine Meldung"
    assert bar.pointed() == 0
    assert "2" in bar.tabToolTip(0)
    assert tabs.layout_state()["order"] == ["second", "first"]


def test_hidden_detached_pages_follow_their_original_tab(tabs):
    tabs, first, _second = tabs
    tabs.detach_page(first)
    floating = first.window()
    tabs.setTabVisible(tabs.indexOf(first), False)
    assert not floating.isVisible()
    tabs.setTabVisible(tabs.indexOf(first), True)
    assert floating.isVisible()
    tabs.setCurrentWidget(first)
    assert tabs.currentWidget() is first


def test_saved_detachment_and_order_restore_without_changing_text(tabs):
    tabs, first, second = tabs
    tabs.configure_pages(
        {"first": first, "second": second},
        {"order": ["second", "first"], "windows": {"first": [100, 100, 500, 400]}},
    )
    assert tabs.widget(0) is second
    assert first.window() is not tabs.window()
    assert first.text() == "unveränderter Entwurf"
    assert tabs.layout_state()["order"] == ["second", "first"]


def test_dragging_a_tab_outside_opens_a_real_window(native_window_platform):
    """Der echte Plattformweg läuft isoliert und endet wieder vollständig angedockt."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = r"""
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit, QMainWindow
from app.ui.overlay import CurrentPageTabs
from app.ui.tab_signal import SignalTabBar
app = QApplication([])
assert app.platformName() not in ('offscreen', 'minimal')
window = QMainWindow()
escaped = []
escape = QAction(window)
escape.setShortcut(QKeySequence(Qt.Key.Key_Escape))
escape.triggered.connect(lambda: escaped.append(1))
window.addAction(escape)
tabs = CurrentPageTabs(window)
tabs.setTabBar(SignalTabBar(tabs))
window.setCentralWidget(tabs)
page = QLineEdit('Entwurf bleibt')
tabs.addTab(page, 'Reiter')
tabs.configure_pages({'page': page}, {})
window.resize(800, 600)
window.show()
assert QTest.qWaitForWindowExposed(window)
bar = tabs.tabBar()
start = bar.tabRect(0).center()
target = QPoint(start.x(), bar.height() + 90)
QTest.mousePress(bar, Qt.MouseButton.LeftButton, pos=start)
QTest.mouseMove(bar, target)
QTest.mouseRelease(bar, Qt.MouseButton.LeftButton, pos=target)
app.processEvents()
floating = page.window()
assert floating is not window
assert QTest.qWaitForWindowExposed(floating)
floating.activateWindow()
assert QTest.qWaitForWindowActive(floating)
QTest.keyClick(page, Qt.Key.Key_Escape)
assert escaped == [1]
escape.setEnabled(False)
QTest.keyClick(page, Qt.Key.Key_Escape)
assert escaped == [1]
page.setText('im eigenen Fenster geändert')
before = tabs.layout_state()
floating.close()
app.processEvents()
assert page.window() is window
assert page.text() == 'im eigenen Fenster geändert'
tabs.configure_pages({'page': page}, before)
assert QTest.qWaitForWindowExposed(page.window())
app.processEvents()
assert tabs.layout_state() == before, (before, tabs.layout_state())
page.window().close()
app.processEvents()
assert page.window() is window
tabs.shutdown_windows()
window.close()
window.deleteLater()
app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
print('native drag and return passed')
"""
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": native_window_platform},
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "native drag and return passed" in done.stdout


def test_main_window_shortcuts_follow_the_detached_page(qt_app, monkeypatch):
    """Escape und Werkzeugkürzel arbeiten im echten Hauptfenster auf derselben Sitzung."""
    from PySide6.QtGui import QAction, QKeySequence

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    escaped = []
    monkeypatch.setattr(MainWindow, "_escape", lambda self: escaped.append(1))
    window = MainWindow(Session(), UiSettings())
    window.show()
    window._show_start_screen(False)
    QApplication.processEvents()
    window.right.detach_page(window.chat)
    floating = window.chat.window()
    try:
        # Die echte Auswahlkarte bleibt neben dem Chat sichtbar; ein Wechsel
        # beendet ihre laufende Vorschau nicht und erneuert sie ohne Fokusraub.
        window.right.detach_page(window.feature_dock)
        selection_window = window.feature_dock.window()
        closed = []
        window.feature_dock.closed.connect(lambda: closed.append(1))
        window.right.setCurrentWidget(window.report)
        assert window.feature_dock.is_current()
        assert closed == []
        activated = []
        monkeypatch.setattr(selection_window, "activateWindow", lambda: activated.append(1))
        window.feature_dock.reveal()
        assert activated == []
        escape = next(
            action
            for action in floating.actions()
            if action.shortcut() == QKeySequence(Qt.Key.Key_Escape)
        )
        assert escape in window.actions(), "ein gemeinsamer Befehl"
        escape.trigger()
        assert escaped == [1]
        escape.setEnabled(False)
        escape.trigger()
        assert escaped == [1], "der Sperrzustand ist derselbe"
        keys = {
            sequence.toString() for action in floating.actions() for sequence in action.shortcuts()
        }
        assert "Ctrl+Tab" in keys and "Alt+1" in keys
        assert any(
            action.shortcut() == QKeySequence.StandardKey.Undo
            for action in floating.findChildren(QAction) + floating.actions()
        )
    finally:
        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_swapping_lower_edge_cards_keeps_both_horizontal_anchors():
    from app.ui.overlay import _drag_sentence

    places = {"left": CardPlace("bottom", 0.8), "right": CardPlace("bottom", 0.4)}
    sizes = {"left": QSize(200, 200), "right": QSize(200, 200)}
    result = settled_places("left", places["right"], places, sizes, 1400, 900)
    assert result == {"left": places["right"], "right": places["left"]}
    assert (
        _drag_sentence("left", places, result, places["right"])
        == "Loslassen tauscht die beiden Karten."
    )


def test_a_hidden_saved_window_is_kept_until_its_page_is_shown(tabs):
    tabs, first, second = tabs
    tabs.setTabVisible(tabs.indexOf(second), False)
    saved = {"order": ["first", "second"], "windows": {"second": [100, 100, 500, 400]}}
    tabs.configure_pages({"first": first, "second": second}, saved)
    assert tabs.layout_state() == saved
    assert second.window() is tabs.window()
    tabs.setTabVisible(tabs.indexOf(second), True)
    assert second.window() is not tabs.window()
    assert second.window().isVisible()
