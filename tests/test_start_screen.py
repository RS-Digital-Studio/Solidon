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
    TILE_MIN_WIDTH,
    WIDE_COLUMN_WIDTH,
    DropArea,
    ExampleTile,
    StartScreen,
    current_theme,
)


@pytest.fixture
def screen(qt_app: QApplication) -> StartScreen:
    return StartScreen()


def test_the_start_screen_fits_a_laptop_without_scrolling(qt_app: QApplication) -> None:
    """Der erste Eindruck darf nicht rollen.

    1600x900 ist die häufigste Laptop-Auflösung, und dort brauchte der
    Startbildschirm **1040** Bildpunkte: Er rollte um 140, und die
    Kachelbereiche reichten bis 917 bei 900 Fensterhöhe. Das ist das Erste,
    was jemand von Solidon sieht.

    Kleiner geworden ist ``more_area`` — die fünf Beispiele ohne Weg klappen
    zu, die vier Wege aus §2.2 nicht. Die Naht liegt dort, wo die Sache selbst
    eine hat: Die vier sind die Struktur des Programms, die fünf sind
    Vertiefung.

    **Geprüft wird die Grenze und nicht der Posten** — „passt auf 900" statt
    „``more_area`` ist kleiner als X". Die Zahlen dieses Punktes waren dreimal
    veraltet; ein Test auf einen Einzelposten altert mit, sobald jemand eine
    Kachel hinzufügt, und sagt dann nichts mehr über das, was zählt.

    Gemessen **mit Thema**: Ohne fehlt die Polsterung, die ein Kunde sieht.
    """
    from PySide6.QtWidgets import QScrollArea

    from app.ui.style import stylesheet

    davor = qt_app.styleSheet()
    qt_app.setStyleSheet(stylesheet("light", 10))
    screen = StartScreen()
    try:
        screen.show_recent([])
        screen.resize(1600, 900)
        screen.show()
        qt_app.processEvents()

        roll = screen.findChildren(QScrollArea)
        assert roll, "der Startbildschirm rollt gar nicht mehr — dann prüft das hier nichts"
        innen = roll[0].widget()
        assert innen is not None
        noetig = innen.sizeHint().height()

        assert noetig <= 900, (
            f"der Startbildschirm verlangt {noetig} Bildpunkte und rollt damit auf einem "
            "1600x900-Schirm — dem häufigsten Laptop"
        )
        assert len(screen.tiles) == len(examples.EXAMPLES), (
            "zugeklappt heißt nicht weg: alle Beispiele sind weiterhin da"
        )
    finally:
        screen.deleteLater()
        qt_app.setStyleSheet(davor)


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


def test_the_drop_area_names_every_format_it_accepts(screen: StartScreen) -> None:
    """Eine beworbene Teilmenge lässt gültige Dateien wie Ausnahmen wirken."""
    from PySide6.QtWidgets import QLabel

    from app.branding import PROJECT_SUFFIX
    from app.core.ingest.plan import MODEL_SUFFIXES

    area = screen.findChild(DropArea)
    assert area is not None
    shown = "\n".join(label.text().lower() for label in area.findChildren(QLabel))
    for suffix in (*MODEL_SUFFIXES, PROJECT_SUFFIX):
        assert suffix.lstrip(".").lower() in shown, suffix


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
        assert "Geführte Tour · Schritt für Schritt" in texts, (
            "eine Beispielkachel muss sagen, dass hinter ihr eine Führung beginnt"
        )


def test_the_four_starts_use_actions_instead_of_internal_way_numbers(
    screen: StartScreen,
) -> None:
    """Ein neuer Kunde wählt eine Absicht und keinen Bauplanabschnitt."""
    starts = [tile for tile in screen.tiles if tile.entry.way]

    assert len(starts) == 4
    assert all(not str(tile.entry.title).startswith("Weg ") for tile in starts)
    shown = {str(tile.entry.title) for tile in starts}
    assert {
        "Vorhandenes Modell anpassen",
        "Eigenes Teil bauen",
        "Modell aus Text oder Bild vorbereiten",
        "Figur frei formen",
    } == shown


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


# --- Vorschaubilder (Konzept Teil 2.1, Punkt 3) ---------------------------------


def test_every_example_brings_a_preview() -> None:
    """Die Kacheln zeigten Titel und Satz und sonst nichts.

    Das Bild entsteht aus demselben Lauf, der das Beispiel baut
    (`tools/make_examples.py`) — eines, das jemand später von Hand nachzieht,
    zeigt irgendwann ein anderes Teil als die Datei daneben. Dieselbe
    Begründung, aus der auch die Bausteinvorschauen gerendert und nicht
    gepflegt werden (§24.3).
    """
    for path in examples.paths():
        entry = examples.by_path(path)
        assert entry is not None
        picture = examples.preview_of(entry)
        assert picture.startswith("<svg"), f"{entry.id} hat kein Vorschaubild"
        assert len(picture) < 400_000, f"{entry.id}: {len(picture) / 1024:.0f} kB sind zu viel"


def test_a_preview_draws_all_bodies_of_the_example() -> None:
    """Eine Kachel zeigt, was das Beispiel enthält — bei „Aushöhlen und
    teilen" sind das zwei Hälften, die nebeneinanderliegen."""
    import trimesh

    from app.core.geom.mesh import MeshData

    one = MeshData.of(trimesh.creation.box(extents=(20.0, 10.0, 6.0)))
    other = MeshData.of(trimesh.creation.box(extents=(8.0, 8.0, 8.0)))
    other.raw.apply_translation((30.0, 0.0, 0.0))

    single = examples.render_preview([one])
    both = examples.render_preview([one, other])

    assert single.startswith("<svg") and both.startswith("<svg")
    assert len(both) > len(single), "der zweite Körper steht mit im Bild"


def test_a_preview_of_nothing_is_nothing() -> None:
    """Ein Beispiel ohne Körper ist keiner — und kein leeres SVG."""
    assert examples.render_preview([]) == ""


def test_the_tile_shows_the_picture(screen: StartScreen) -> None:
    tiles = screen.findChildren(ExampleTile)
    assert tiles

    for tile in tiles:
        assert not tile.preview.isHidden(), f"{tile.entry.id} zeigt sein Bild nicht"
        assert not tile.preview.pixmap().isNull()


def test_a_missing_picture_leaves_the_tile_standing(qt_app: QApplication) -> None:
    """Ein frisch ausgecheckter Baum hat die Bilder erst, wenn das Werkzeug
    gelaufen ist — eine leere Fläche wäre schlimmer als keine."""
    from pathlib import Path

    from app.core.examples import Example

    unknown = Example(id="gibt-es-nicht", title="Kein Beispiel", way="", doc="Ohne Bild.")
    tile = ExampleTile(unknown, Path("gibt-es-nicht.p3d"))

    assert tile.preview.isHidden()
    assert unknown.title in [label.text() for label in tile.findChildren(type(tile.preview))]


def test_the_examples_stand_in_two_groups(screen: StartScreen) -> None:
    """Neun gleich aussehende Kacheln unter einer Überschrift.

    Der Code kennt die Zweiteilung seit je — ``examples.py`` sagt im Kommentar:
    „Die vier oben beantworten ‚wie fange ich an', diese ‚was kann das
    eigentlich'." Die Oberfläche zeigte sie nicht, und der Erstnutzer musste aus
    den Titeln „Weg 1 … Weg 4" schließen, dass genau diese vier der Anfang sind.
    Das Wort „Weg" erklärt der Startbildschirm nirgends; es stammt aus Bauplan
    §2.2.

    Geteilt wird nach ``way`` und nicht nach der Reihenfolge: Ein fünfter Weg
    fände von selbst in die obere Gruppe.
    """
    from app.core import examples

    ways = [entry for entry in examples.EXAMPLES if entry.way]
    others = [entry for entry in examples.EXAMPLES if not entry.way]
    assert ways and others, "ohne beide Sorten prüft dieser Test nichts"

    assert screen.examples_grid.count() == len(ways), (
        f"{screen.examples_grid.count()} Einstiege statt {len(ways)}"
    )
    assert screen.more_grid.count() == len(others), (
        f"{screen.more_grid.count()} Funktionsschauen statt {len(others)}"
    )
    assert len(screen.tiles) == len(ways) + len(others), "eine Kachel ist unterwegs verloren"

    # Und jede Kachel steht in dem Raster, in das sie gehört.
    for index in range(screen.examples_grid.count()):
        item = screen.examples_grid.itemAt(index)
        tile = item.widget() if item is not None else None
        assert tile is not None and tile.entry.way, f"{tile.entry.id} ist kein Einstieg"


def test_the_tiles_use_the_width_they_have(screen: StartScreen) -> None:
    """Die neunte Kachel lag unter der Kante, daneben blieben 900 Pixel leer.

    Gemessen im maximierten Fenster auf 1920 mal 1080: Sichtfeld 956, Inhalt
    1154, Rollbalken sichtbar — und die Spalte 900 Pixel breit in einem 1906
    Pixel breiten Fenster. Drei Kachelspalten machen aus fünf Kachelzeilen vier.

    Bei einem schmalen Fenster bleibt es bei zwei: drei Kacheln unter
    ``TILE_MIN_WIDTH`` wären drei Wortkolonnen.
    """
    from app.ui.start_screen import TILE_COLUMNS, TILE_MIN_WIDTH

    screen.show()
    screen.resize(3 * TILE_MIN_WIDTH + 200, 900)
    QApplication.processEvents()
    assert screen._columns == 3, "die Breite ist da und wird nicht benutzt"
    way_positions = [screen.examples_grid.getItemPosition(index)[:2] for index in range(4)]
    assert way_positions == [(0, 0), (0, 1), (1, 0), (1, 1)], (
        "vier Einstiege stehen als ruhiges 2×2-Raster, nicht als 3+1 mit einem Waisenkärtchen"
    )
    more_positions = [
        screen.more_grid.getItemPosition(index)[:2] for index in range(screen.more_grid.count())
    ]
    assert (0, 2) in more_positions, "die Vertiefungen nutzen die dritte Spalte weiter"

    screen.resize(2 * TILE_MIN_WIDTH + 40, 900)
    QApplication.processEvents()
    assert screen._columns == TILE_COLUMNS, "drei Spalten in einem schmalen Fenster"

    # Und die Kacheln sind alle noch da, in der richtigen Gruppe.
    assert len(screen.tiles) == screen.examples_grid.count() + screen.more_grid.count()
    screen.hide()


def test_the_column_uses_the_width_it_is_allowed(screen: StartScreen) -> None:
    """Erlaubt ist nicht benutzt — und der Test daneben merkte den Unterschied nicht.

    ``_fit_the_columns`` stellt die erlaubte Breite auf
    :data:`WIDE_COLUMN_WIDTH` und die Kachelspalten auf drei, sobald der Platz
    da ist. Beides stimmte, und trotzdem stand der Startbildschirm bei **714
    Pixeln** — bei jeder Fenstergröße von 1280 bis 3413. ``setMaximumWidth``
    erlaubt nur; zwischen zwei Stretch-Feldern ohne eigenen Faktor bekam die
    Spalte ihre ``sizeHint`` und blieb dort stehen.

    Für einen Kunden ohne CAD-Erfahrung ist das der erste Eindruck der
    Anwendung: eine schmale Spalte in der Mitte, zwei Drittel des Bildschirms
    schwarz. Der Test darüber prüft die **Rechnung** und blieb dabei grün —
    geprüft wird hier deshalb die **Wirkung**, und zwar an der Zusage selbst:
    Wo Platz ist, ist die Spalte so breit, wie sie sein darf.

    **Die Zahl daneben stimmt hier nicht, die Zusage schon.** Offscreen hat die
    Suite keine Schriftmetrik, und die Phantomschrift ist breiter als eine
    echte: Dieselbe Spalte maß hier 1216 Pixel und im sichtbaren Fenster 714.
    Wer das Ausmaß wissen will, misst mit echter Plattform; was dieser Test
    prüft — genommen gleich erlaubt —, hängt an keiner Schriftbreite und fällt
    in beiden Umgebungen.
    """
    screen.show()

    screen.resize(1920, 1000)
    QApplication.processEvents()
    assert screen.column.maximumWidth() == WIDE_COLUMN_WIDTH, (
        "the wide layout should be allowed at 1920"
    )
    assert screen.column.width() == screen.column.maximumWidth(), (
        f"the column may be {screen.column.maximumWidth()} wide but takes only "
        f"{screen.column.width()} — allowed is not used"
    )

    # **Im schmalen Fenster gilt die Zusage gegen den Platz, nicht gegen die
    # Erlaubnis.** Dort ist erlaubt mehr, als vorhanden ist — die Spalte nimmt
    # dann, was da ist. Gemessen wird deshalb am Fenster und nicht an einer
    # nachgerechneten Randbreite: Wer die Ränder hier nachrechnet, prüft seinen
    # eigenen Nachbau des Layouts.
    screen.resize(2 * TILE_MIN_WIDTH + 40, 900)
    QApplication.processEvents()
    assert screen.column.maximumWidth() == COLUMN_WIDTH
    assert screen.column.width() < screen.column.maximumWidth(), (
        "a narrow window cannot grant the full column width"
    )
    assert screen.column.width() > 0.8 * screen.width(), (
        f"narrow window: the column takes {screen.column.width()} of {screen.width()} — "
        f"it should fill everything but the margins"
    )

    screen.hide()
