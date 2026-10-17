"""Im Fenster steht *Übernehmen* unter der offenen Handlung und bleibt im Bild (FD-136).

``MainWindow._build_feature_dock`` hob die Knopfzeile unter den Rollbereich
der Auswahlkarte; dort stand sie am Kartenende, das Feld ganz oben. Sie
bleibt im Merkmalfenster unter der scharfen Handlung, und
``feature_footer.keep_in_sight`` hält sie im Sichtfeld des Rollbereichs.

Die Fläche ist die kleinste, für die Solidon gebaut ist: 1920 × 1080 logisch.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QScrollArea

from app.ui.main_window import MainWindow
from tests.hole_window import hole_window


@pytest.fixture
def a_hole(qt_app: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    with hole_window(qt_app, tmp_path, 1920, 1080) as window:
        yield window


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
