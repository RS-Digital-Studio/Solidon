"""Im Fenster wird die linke Karte breiter, bis das krumme Maß ganz dasteht (RA-4, FD-20).

``test_object_tree_columns.py`` prüft den Baum allein — welche Mindestbreite er
nennt. Ob die Karte sie bekommt, entscheidet ``OverlayHost._card_width``; hier
steht der Anschluss: ein Quader mit krummem Maß im Fenster, und die Maßspalte
zeigt es ganz.

Im Schlusslauf L4 (2560 × 1369) hielt das nicht: neben „Redondeo cóncavo (4)“
endete „Ø8,00 mm / Ø4,00…“, neben „Parallelepipedo 1 di 4 · …“ das Maß
„24,5 × 19,5 × 20 …“. Der Baum zählte einen Namen bei seiner Wunschbreite nur
mit drei Fünfteln von fest 300 Punkten, gab ihm beim Teilen aber alles — die
Karte blieb zu schmal, und das Maß bekam den Rest.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTreeWidgetItem, QTreeWidgetItemIterator

from app.core.scene import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.overlay import LEFT_MAX, LEFT_WIDTH
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.bundled_fonts import bundled_font
from tests.ui_helpers import wait_until


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    with bundled_font(qt_app, 9):
        built = MainWindow(Session(), UiSettings())
        built.resize(1920, 1080)
        built.show()
        built._show_start_screen(False)
        yield built
        assert built.session.wait_for_idle(60_000)
        built.release()
        built.deleteLater()
        qt_app.processEvents()


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
    # Gesetzt wird über einen Nullzeitgeber (``OverlayHost._place_later``); zwanzig
    # Ereignisrunden ohne Uhr reichten auf dem Linux-Läufer nicht (Fensterauswahl
    # 39035816730).
    wait_until(qt_app, lambda: zone.width() > LEFT_WIDTH)
    assert zone.width() > LEFT_WIDTH, f"die Karte bleibt bei {zone.width()} Punkten"
    header = tree.tree.header()
    needed = tree.tree.sizeHintForColumn(1)
    assert header.sectionSize(1) >= needed, f"Maß in {header.sectionSize(1)} von {needed}"


@contextmanager
def _wide_window(qt_app: QApplication, language: str) -> Iterator[MainWindow]:
    """Das Fenster des Schlusslaufs: 2560 × 1369, in ``language``."""
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    install_language(language)
    set_language(language)
    with bundled_font(qt_app, 9):
        built = MainWindow(Session(), UiSettings())
        built.resize(2560, 1369)
        built.show()
        built._show_start_screen(False)
        try:
            yield built
        finally:
            assert built.session.wait_for_idle(60_000)
            built.release()
            built.deleteLater()
            qt_app.processEvents()


def _settle(qt_app: QApplication, window: MainWindow) -> None:
    """Auswerten lassen und die Zone ihre neue Breite nehmen lassen."""
    assert window.session.wait_for_idle(60_000)
    for _round in range(30):
        qt_app.processEvents()


def _visible_rows(window: MainWindow) -> list[QTreeWidgetItem]:
    view = window.object_tree.tree
    rows = []
    found = QTreeWidgetItemIterator(view)
    while found.value():
        item = found.value()
        if view.visualItemRect(item).height() > 0:
            rows.append(item)
        found += 1
    return rows


def _measure_cut(window: MainWindow) -> list[str]:
    """Die Zeilen, deren Maß nicht in seine Spalte passt."""
    view = window.object_tree.tree
    room = view.header().sectionSize(1)
    cut = []
    for row in _visible_rows(window):
        wanted = view.sizeHintForIndex(view.indexFromItem(row, 1)).width()
        if wanted > room:
            cut.append(f"{row.text(0)!r}: {row.text(1)!r} braucht {wanted}, hat {room}")
    return cut


def test_feature_measures_stand_whole_beside_spanish_names(qt_app: QApplication) -> None:
    """Der Kasten des Schlusslaufs auf Spanisch: jedes Merkmalsmaß ganz, und die Namen auch.

    Name und Maß zusammen passen in die Karte, wenn sie bis ``LEFT_MAX`` wächst;
    gekürzt werden darf deshalb keines von beiden.
    """
    from tests.helpers import exact_kernel

    exact_kernel()
    with _wide_window(qt_app, "es") as window:
        drafts = [
            OperationDraft(
                op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}
            ),
            OperationDraft(
                op="create_brep_box",
                params={
                    "width": 34.0,
                    "depth": 24.0,
                    "height": 20.0,
                    "x": 3.0,
                    "y": 3.0,
                    "z": 3.0,
                },
            ),
            OperationDraft(op="subtract_objects", inputs=("obj_1", "obj_2"), params={}),
            OperationDraft(
                op="fillet_edges", inputs=("obj_1",), params={"radius": 2.0, "edges": "all"}
            ),
        ]
        assert window.session.apply("Kasten", drafts)
        _settle(qt_app, window)
        view = window.object_tree.tree
        top = view.topLevelItem(0)
        assert top is not None
        top.setExpanded(True)
        _settle(qt_app, window)
        texts = [row.text(1) for row in _visible_rows(window)]
        assert any("/" in text for text in texts), f"Voraussetzung: die Wulstzeile fehlt: {texts}"

        assert not _measure_cut(window), _measure_cut(window)
        header = view.header()
        zone = window.overlay.side_zone("left")
        assert zone is not None
        assert header.sectionSize(0) >= view.sizeHintForColumn(0), (
            f"Namen in {header.sectionSize(0)} von {view.sizeHintForColumn(0)} Punkten, "
            f"Karte {zone.width()} von höchstens {LEFT_MAX}"
        )
        roofs = [row for row in _visible_rows(window) if row.childCount() and row is not top]
        assert roofs, "Voraussetzung: gebündelte Rundungen"
        for roof in roofs:
            assert roof.toolTip(0).startswith(roof.text(0)), (
                "die Kurzhilfe nennt den Namen, falls er gekürzt steht",
                roof.toolTip(0),
            )


@pytest.mark.parametrize("language", ["it", "fr"])
def test_a_long_name_yields_to_the_whole_measure(qt_app: QApplication, language: str) -> None:
    """Vier lange Teilnamen: das Maß steht ganz, der Name gekürzt und ganz in der Kurzhilfe."""
    names = {
        "it": "Parallelepipedo {index} di 4 · Accoppiamento con spine",
        "fr": "Pavé {index} sur 4 · Goupillé avec ses voisins",
    }[language]
    sizes = ((24.5, 19.5, 20.0), (24.5, 15.0, 20.0), (20.0, 19.5, 20.0), (20.0, 15.0, 20.0))
    with _wide_window(qt_app, language) as window:
        drafts = [
            OperationDraft(
                op="create_box",
                params={
                    "width": width,
                    "depth": depth,
                    "height": height,
                    "x": 40.0 * index,
                    "name": names.format(index=index + 1),
                },
            )
            for index, (width, depth, height) in enumerate(sizes)
        ]
        assert window.session.apply("Teile", drafts)
        _settle(qt_app, window)
        view = window.object_tree.tree
        assert view.topLevelItemCount() == 4

        assert not _measure_cut(window), _measure_cut(window)
        zone = window.overlay.side_zone("left")
        assert zone is not None
        assert zone.width() <= LEFT_MAX
        for row in _visible_rows(window):
            name = str(row.text(0))
            assert row.toolTip(0).startswith(name), (name, row.toolTip(0))
        header = view.header()
        assert header.sectionSize(0) >= header.sectionSizeHint(0), "die Überschrift bleibt ganz"
        assert header.sectionSize(0) < view.sizeHintForColumn(0), (
            "Voraussetzung: der Name ist länger als sein Anteil an der Karte"
        )
        assert view.textElideMode() == Qt.TextElideMode.ElideRight, "gekürzt mit Auslassung"
