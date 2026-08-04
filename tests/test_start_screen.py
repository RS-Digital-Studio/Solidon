"""Der Startbildschirm (Bauplan §2.3, §37.2, Konzept Teil 10 Punkt 11).

Der leere Zustand ist der erste Eindruck, und er war einer von einem Formular,
dem die Felder fehlen. Was hier steht, sind die sechs Punkte, mit denen er
einer von Absicht wurde — jeder als Aussage, nicht als Pixelmaß: eine
Gestaltung lässt sich nicht festnageln, ihre Entscheidungen schon.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core import examples
from app.ui.start_screen import (
    COLUMN_WIDTH,
    DropArea,
    ExampleTile,
    StartScreen,
    current_theme,
)


@pytest.fixture
def screen(qt_app: QApplication) -> StartScreen:
    return StartScreen()


def test_the_content_stays_in_one_readable_column(screen: StartScreen) -> None:
    """Vorher über 1900 Pixel verteilt: ein Knopf am linken Rand, sein Verweis
    am rechten, und dazwischen nichts, das die beiden verbindet."""
    screen.resize(1920, 1080)
    screen.show()
    QApplication.processEvents()

    assert screen.new_button.width() < COLUMN_WIDTH
    distance = abs(screen.manual_button.x() - screen.open_button.x())
    assert distance < COLUMN_WIDTH, "der Handbuch-Verweis gehört neben die Knöpfe"
    screen.hide()


def test_the_main_button_looks_like_one(screen: StartScreen) -> None:
    """„Neues Projekt" und „Projekt öffnen" standen gleich groß nebeneinander
    und sagten nicht, welcher gemeint ist, wenn man nichts Bestimmtes vorhat."""
    assert screen.new_button.isDefault()
    assert not screen.open_button.isDefault()


def test_the_drop_area_is_a_field_and_says_when_it_is_hit(screen: StartScreen) -> None:
    """Vorher ein Satz in der Bildmitte, ohne Rahmen, ohne Feld, ohne Symbol.

    Der Rahmen kommt aus dem Thema und nicht aus ``palette(mid)`` — das war im
    dunklen unsichtbar, also genau dort, wo die Anwendung startet.
    """
    from app.ui.theme import THEMES

    area = screen.findChild(DropArea)
    assert area is not None
    assert "dashed" in area.styleSheet()
    assert not area.symbol.pixmap().isNull(), "und ein Symbol"

    quiet = area.styleSheet()
    area._set_hover(True)
    assert area.styleSheet() != quiet, "getroffen sieht anders aus als ruhig"
    assert THEMES[current_theme()]["highlight"] in area.styleSheet()  # type: ignore[index]

    area._set_hover(False)
    assert area.styleSheet() == quiet


def test_every_example_is_a_tile_with_its_sentence(screen: StartScreen) -> None:
    """§37.2 nennt die Beispiele Dokumentation, Abnahmetest und Inhalt des
    Startbildschirms zugleich. Eine Textzeile unter sechs anderen sagt davon
    nichts."""
    tiles = screen.findChildren(ExampleTile)
    assert len(tiles) == len(examples.paths())

    from PySide6.QtWidgets import QLabel

    for tile in tiles:
        texts = [label.text() for label in tile.findChildren(QLabel)]
        assert str(tile.entry.title) in texts
        assert str(tile.entry.doc) in texts, "der Satz gehört auf die Kachel"


def test_a_tile_opens_its_project(screen: StartScreen) -> None:
    """Mit der Maus und mit der Tastatur — §19.2 kennt keine Ausnahme."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    tiles = screen.findChildren(ExampleTile)
    assert tiles
    opened: list[str] = []
    screen.openRequested.connect(lambda path: opened.append(str(path)))

    tiles[0].keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    )
    assert opened == [str(tiles[0].path)]

    assert tiles[0].focusPolicy() != Qt.FocusPolicy.NoFocus, "und erreichbar mit Tab"


def test_an_empty_recent_list_is_a_line_not_a_box(screen: StartScreen) -> None:
    """Ein leerer Zustand darf klein sein; er muss nur seinen Platz wieder
    hergeben, wenn er gefüllt wird."""
    from pathlib import Path

    screen.show_recent([])
    assert not screen.recent_empty.isHidden()
    assert screen.recent_list.isHidden()

    screen.show_recent([Path("a.p3d"), Path("b.p3d")])
    assert screen.recent_empty.isHidden()
    assert not screen.recent_list.isHidden()
    assert screen.recent_list.count() == 2
