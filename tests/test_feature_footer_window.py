"""Im Fenster steht *Übernehmen* unter der offenen Handlung und bleibt im Bild (FD-136).

``MainWindow._build_feature_dock`` hob die Knopfzeile unter den Rollbereich
der Auswahlkarte; dort stand sie am Kartenende, das Feld ganz oben. Sie
bleibt im Merkmalfenster unter der scharfen Handlung, und
``feature_footer.keep_in_sight`` hält sie im Sichtfeld des Rollbereichs.

Die Fläche ist die kleinste, für die Solidon gebaut ist: 1920 × 1080 logisch.
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
    """Bis die Seite eine Weile dieselbe Größe hat.

    Die Karte wächst nach der Wahl über Zeitgeber auf ihre Höhe; davor ist
    das Sichtfeld rund 90 Punkte hoch, und jede Lagefrage wäre erfunden.
    """
    last, still = None, 0
    deadline = time.monotonic() + 10
    while still < 30 and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
        size = page.size()
        still = still + 1 if size == last else 0
        last = size


@pytest.fixture
def a_hole(qt_app: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    path = tmp_path / "bohrung.p3d"
    save(function_scenes.build_scene("erkannte_bohrung.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(1920, 1080)
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
    for _round in range(10):
        qt_app.processEvents()
    assert window.session.wait_for_idle(60_000)
    _settle(qt_app, window.feature_dock)
    yield window
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def test_apply_stands_below_the_open_handling_and_in_sight(
    qt_app: QApplication, a_hole: MainWindow
) -> None:
    panel = a_hole.feature_panel
    footer = panel._footer
    assert footer.parentWidget() is panel, "die Knopfzeile steht im Merkmalfenster"
    box = next(row.box for row in panel._shown_rows.values() if row.key == panel._armed)
    assert panel._rows.indexOf(footer) == panel._rows.indexOf(box) + 1
    holder = footer.parentWidget()
    while holder is not None and not isinstance(holder, QScrollArea):
        holder = holder.parentWidget()
    assert holder is not None
    view = holder.viewport()
    top = footer.mapTo(view, footer.rect().topLeft()).y()
    bottom = footer.mapTo(view, footer.rect().bottomLeft()).y()
    assert top >= 0 and bottom <= view.height(), (top, bottom, view.height())
    # Platz für beides: Name und Maß der Wahl rollen dafür nicht hinaus.
    head = panel.mapTo(view, panel.rect().topLeft()).y()
    assert head >= 0, f"der Kopf der Wahl steht {-head} Punkte über dem Rand"
