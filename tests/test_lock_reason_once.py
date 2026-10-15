"""Ohne Freischaltung steht der Sperrgrund im Reiter *Auswahl* einmal (FD-32).

An einer erkannten Bohrung stand derselbe Satz unter dem Suchfeld und im
Merkmalfenster. Die Zeile unter dem Suchfeld gilt für den Reiter; das
Merkmalfenster trägt den Grund nur an seinen grauen Elementen (Kurzhilfe und
Beschreibung). Geprüft in beiden gesperrten Zuständen, an der gewählten
Bohrung, ruhend und mit Suchtext.

Die Fläche ist die kleinste, für die Solidon gebaut ist: 1920 × 1080 logisch.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QListWidget

from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.test_licence_lock_offers import LOCKED
from tests.ui_helpers import set_licence, wait_for_print_findings


@pytest.fixture
def a_hole(qt_app: QApplication) -> Iterator[MainWindow]:
    path = Path(__file__).parent / "data" / "meshes" / "plate_holes.stl"
    window = MainWindow(Session(), UiSettings())
    window.resize(1920, 1080)
    window.show()
    window._show_start_screen(False)
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    wait_for_print_findings(window)
    yield window
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def _visible_lines_with(window: MainWindow, reason: str) -> list[str]:
    page = window.feature_dock
    labels = [
        label.objectName() or type(label.parentWidget()).__name__
        for label in page.findChildren(QLabel)
        if label.isVisibleTo(page) and reason and reason in label.text()
    ]
    rows = [
        "Trefferzeile"
        for listing in page.findChildren(QListWidget)
        if listing.isVisibleTo(page)
        for index in range(listing.count())
        if not listing.item(index).isHidden() and reason in listing.item(index).text()
    ]
    return labels + rows


@pytest.mark.parametrize("state", LOCKED)
def test_the_reason_stands_once_at_a_chosen_hole(
    qt_app: QApplication, a_hole: MainWindow, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    window = a_hole
    reason = set_licence(monkeypatch, state)
    assert reason, f"{state}: ohne Sperrgrund prüft dieser Test nichts"
    result = window.session.last_result
    object_id = next(iter(result.scene.objects))
    hole = next(
        name
        for name, feature in result.scene.objects[object_id].features.items()
        if feature.kind == "hole"
    )
    window.object_tree.select_feature(object_id, hole)
    window._update_actions()
    for _round in range(10):
        qt_app.processEvents()
    assert window.session.wait_for_idle(60_000)
    shown = _visible_lines_with(window, reason)
    assert len(shown) == 1, f"{state}, ruhend: {shown}"

    window.selection_operations.search.setText("Bohrung")
    for _round in range(5):
        qt_app.processEvents()
    shown = _visible_lines_with(window, reason)
    assert len(shown) == 1, f"{state}, mit Suchtext: {shown}"
