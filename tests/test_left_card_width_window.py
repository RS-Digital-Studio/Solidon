"""Im Fenster wird die linke Karte breiter, bis das krumme Maß ganz dasteht (RA-4, FD-20).

``test_object_tree_columns.py`` prüft den Baum allein — welche Mindestbreite er
nennt. Ob die Karte sie bekommt, entscheidet ``OverlayHost._card_width``; hier
steht der Anschluss: ein Quader mit krummem Maß im Fenster, und die Maßspalte
zeigt es ganz.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app.core.scene import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.overlay import LEFT_WIDTH
from app.ui.session import Session
from app.ui.settings import UiSettings


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    fonts = Path(__file__).parents[1] / "app/core/geom/data/fonts"
    font_ids = [
        QFontDatabase.addApplicationFont(str(fonts / name))
        for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
    ]
    assert min(font_ids) >= 0, "Die gebündelte Prüfschrift wurde nicht geladen"
    before = qt_app.font()
    qt_app.setFont(QFont("DejaVu Sans", 9))
    built = MainWindow(Session(), UiSettings())
    built.resize(1920, 1080)
    built.show()
    built._show_start_screen(False)
    yield built
    assert built.session.wait_for_idle(60_000)
    built.release()
    built.deleteLater()
    qt_app.processEvents()
    qt_app.setFont(before)
    for font_id in font_ids:
        QFontDatabase.removeApplicationFont(font_id)


def test_a_crooked_measure_widens_the_left_card(qt_app: QApplication, window: MainWindow) -> None:
    measures = {"width": 253.44, "depth": 190.08, "height": 12.67, "name": "Quader"}
    assert window.session.apply("Quader", [OperationDraft(op="create_box", params=measures)])
    assert window.session.wait_for_idle(60_000)
    for _round in range(20):
        qt_app.processEvents()
    tree = window.object_tree
    tree._size_columns()
    for _round in range(20):
        qt_app.processEvents()
    assert tree.tree.minimumWidth() > LEFT_WIDTH, (
        "Voraussetzung: der Baum verlangt mehr als die Grundbreite",
        tree.tree.minimumWidth(),
    )

    zone = window.overlay.side_zone("left")
    assert zone is not None
    assert zone.width() > LEFT_WIDTH, f"die Karte bleibt bei {zone.width()} Punkten"
    header = tree.tree.header()
    needed = tree.tree.sizeHintForColumn(1)
    assert header.sectionSize(1) >= needed, f"Maß in {header.sectionSize(1)} von {needed}"
