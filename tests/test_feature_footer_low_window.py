"""In einer niedrigen Karte rollt *Übernehmen* zur untersten Handlung ins Bild (RA-4, FD-136).

Die Knopfzeile wandert unter die scharfe Handlung. Liegt die tief in einer Karte,
die nicht alles zeigt, stünde sie unter dem Rand; ``feature_footer.keep_in_sight``
holt sie beim Scharfschalten (``FeaturePanel._arm``). ``test_feature_footer_window.py``
prüft die oberste Handlung, die ohne Rollen sichtbar ist — hier die unterste in
einem Fenster, in dem sie es nicht ist.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from app.core.scene.project import save
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import wait_for_print_findings
from tools import function_scenes


def _settle(qt_app: QApplication, page: QWidget) -> None:
    """Bis die Seite eine Weile dieselbe Größe hat (die Karte öffnet mit Bewegung)."""
    last, still = None, 0
    deadline = time.monotonic() + 10
    while still < 30 and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
        size = page.size()
        still = still + 1 if size == last else 0
        last = size


@pytest.fixture
def low_hole(qt_app: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    path = tmp_path / "bohrung.p3d"
    save(function_scenes.build_scene("erkannte_bohrung.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(1600, 560)
    window.show()
    window._show_start_screen(False)
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    wait_for_print_findings(window)
    result = window.session.last_result
    object_id = next(iter(result.scene.objects))
    hole = next(
        name
        for name, feature in result.scene.objects[object_id].features.items()
        if feature.kind == "hole"
    )
    window.object_tree.select_feature(object_id, hole)
    assert window.session.wait_for_idle(60_000)
    _settle(qt_app, window.feature_dock)
    yield window
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def test_arming_the_lowest_handling_brings_apply_into_sight(
    qt_app: QApplication, low_hole: MainWindow
) -> None:
    panel = low_hole.feature_panel
    footer = panel._footer
    holder = footer.parentWidget()
    while holder is not None and not isinstance(holder, QScrollArea):
        holder = holder.parentWidget()
    assert holder is not None
    view = holder.viewport()
    lowest = max(
        (row for row in panel._shown_rows.values() if row.key in panel._runs),
        key=lambda row: row.box.geometry().top(),
    )
    content = holder.widget()
    assert content is not None
    below = lowest.box.mapTo(content, lowest.box.rect().bottomLeft()).y()
    assert below > view.height(), (
        "Voraussetzung: die unterste Handlung liegt unter dem Sichtfeld",
        below,
        view.height(),
    )

    panel._arm(lowest.key)
    _settle(qt_app, low_hole.feature_dock)

    assert panel._rows.indexOf(footer) == panel._rows.indexOf(lowest.box) + 1
    top = footer.mapTo(view, footer.rect().topLeft()).y()
    bottom = footer.mapTo(view, footer.rect().bottomLeft()).y()
    assert top >= 0 and bottom <= view.height(), (top, bottom, view.height())
