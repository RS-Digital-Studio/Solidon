"""In einer niedrigen Karte rollt *Übernehmen* zur untersten Handlung ins Bild (RA-4, FD-136).

Die Knopfzeile wandert unter die scharfe Handlung. Liegt die tief in einer Karte,
die nicht alles zeigt, stünde sie unter dem Rand; ``feature_footer.keep_in_sight``
holt sie beim Scharfschalten (``FeaturePanel._arm``). ``test_feature_footer_window.py``
prüft die oberste Handlung, die ohne Rollen sichtbar ist — hier die unterste in
einem Fenster, in dem sie es nicht ist.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QScrollArea

from app.ui.main_window import MainWindow
from tests.hole_window import hole_window, settle


@pytest.fixture
def low_hole(qt_app: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    with hole_window(qt_app, tmp_path, 1600, 560) as window:
        yield window


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
    settle(qt_app, low_hole.feature_dock)

    assert panel._rows.indexOf(footer) == panel._rows.indexOf(lowest.box) + 1
    top = footer.mapTo(view, footer.rect().topLeft()).y()
    bottom = footer.mapTo(view, footer.rect().bottomLeft()).y()
    assert top >= 0 and bottom <= view.height(), (top, bottom, view.height())
