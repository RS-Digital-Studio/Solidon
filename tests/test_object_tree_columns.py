"""Die Maßspalte im Objektbaum zeigt ein krummes Maß ganz, wenn der Name Platz lässt (FD-20).

Nach *Auf den Bauraum verkleinern* stand „253,44 × 190,08 × 12,67 mm“ in
117 von 152 nötigen Punkten: Die Spalte war fest auf zwei Fünftel der Breite
gedeckelt (``MEASURE_SHARE``), auch neben einem Namen wie „Quader“, der den
Rest nicht brauchte. Der Deckel gilt jetzt nur, wo beide Spalten nicht
zugleich passen — dann behält der Name die Mehrheit wie bisher.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QTreeWidgetItem

from app.ui.overlay import LEFT_WIDTH
from app.ui.panels import MEASURE_SHARE, ObjectTree


@pytest.fixture(autouse=True)
def _readable_font(qt_app: QApplication) -> Iterator[None]:
    """Eine echte Schrift: Offscreen misst Qt unter Windows sonst Ersatzkästchen.

    Dieselbe gebündelte Datei wie ``test_card_content_width.py``; danach steht die
    Schrift der Suite wieder da.
    """
    fonts = Path(__file__).parents[1] / "app/core/geom/data/fonts"
    font_ids = [
        QFontDatabase.addApplicationFont(str(fonts / name))
        for name in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")
    ]
    assert min(font_ids) >= 0, "Die gebündelte Prüfschrift wurde nicht geladen"
    before = qt_app.font()
    qt_app.setFont(QFont("DejaVu Sans", 9))
    yield
    qt_app.setFont(before)
    for font_id in font_ids:
        QFontDatabase.removeApplicationFont(font_id)


def _tree(rows: list[tuple[str, str]]) -> ObjectTree:
    tree = ObjectTree()
    tree.resize(LEFT_WIDTH, 300)
    for name, size in rows:
        QTreeWidgetItem(tree.tree, [name, size])
    tree.show()
    QApplication.processEvents()
    tree._size_columns()
    QApplication.processEvents()
    return tree


def test_a_crooked_measure_beside_a_short_name_stands_whole(qt_app: QApplication) -> None:
    tree = _tree([("Quader", "253,44 × 190,08 × 12,67 mm")])
    try:
        header = tree.tree.header()
        needed = tree.tree.sizeHintForColumn(1)
        assert header.sectionSize(1) >= needed, (
            f"Maß in {header.sectionSize(1)} von {needed} nötigen Punkten"
        )
        assert header.sectionSize(0) >= tree.tree.sizeHintForColumn(0), "der Name passt weiter"
    finally:
        tree.close()
        tree.deleteLater()


def test_long_names_keep_the_larger_half(qt_app: QApplication) -> None:
    """Gegenprobe: Passen beide nicht, gilt der Anteil — der Name ist die Auskunft."""
    tree = _tree(
        [
            ("Gehäuseboden (Kopie) Prüfstück mit Halter", "253,44 × 190,08 × 12,67 mm"),
            ("Gehäuseboden", "60 × 40 × 12 mm"),
        ]
    )
    try:
        header = tree.tree.header()
        free = tree.tree.viewport().width()
        assert header.sectionSize(1) <= max(
            header.sectionSizeHint(1), int(free * MEASURE_SHARE) + 1
        )
        assert header.sectionSize(0) > header.sectionSize(1)
    finally:
        tree.close()
        tree.deleteLater()


def test_the_tree_asks_the_card_for_room_for_the_whole_measure(qt_app: QApplication) -> None:
    """Reicht die Grundbreite nicht für Name und Maß, nennt der Baum die Breite, die reicht.

    Die linke Karte nimmt sie bis ``LEFT_MAX`` (``OverlayHost._card_width``); ein
    langer Name zählt nur mit seinem gewohnten Anteil, sonst machte jeder lange
    Dateiname die Karte breit.
    """
    from app.ui.overlay import LEFT_MAX
    from app.ui.panels import FILAMENT_WIDTH

    tree = _tree([("Quader", "253,44 × 190,08 × 12,67 mm")])
    try:
        view = tree.tree
        wanted = view.sizeHintForColumn(0) + view.sizeHintForColumn(1) + FILAMENT_WIDTH
        assert view.minimumWidth() >= min(wanted, LEFT_MAX), (view.minimumWidth(), wanted)
    finally:
        tree.close()
        tree.deleteLater()
    widths = []
    for name in ("Ein langer Dateiname aus dem Netz", "Ein langer Dateiname aus dem Netz " * 4):
        tree = _tree([(name, "20 × 20 × 20 mm")])
        try:
            widths.append(tree.tree.minimumWidth())
        finally:
            tree.close()
            tree.deleteLater()
    assert widths[0] == widths[1], f"ein längerer Name allein macht nichts breiter: {widths}"
