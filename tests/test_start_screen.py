"""Der Startbildschirm (Bauplan §2.3, §37.2, Konzept Teil 10 Punkt 11).

Der leere Zustand ist der erste Eindruck, und er war einer von einem Formular,
dem die Felder fehlen. Was hier steht, sind die sechs Punkte, mit denen er
einer von Absicht wurde — jeder als Aussage, nicht als Pixelmaß: eine
Gestaltung lässt sich nicht festnageln, ihre Entscheidungen schon.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget

from app.core import examples
from app.ui.start_screen import (
    COLUMN_WIDTH,
    DROP_AREA_MIN_HEIGHT,
    MEDIUM_LAYOUT_MIN_WIDTH,
    PREVIEW_HEIGHT,
    TILE_GRID_SPACING,
    TILE_MIN_WIDTH,
    WIDE_COLUMN_WIDTH,
    WIDE_LAYOUT_MIN_WIDTH,
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
        assert roll[0].verticalScrollBar().maximum() == 0, (
            "der Startbildschirm rollt auf einem 1600x900-Schirm — dem häufigsten Laptop"
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
        # **Dass eine Führung dahinter beginnt, steht seit B27 über der
        # Gruppe** — viermal derselbe Satz untereinander war einmal Information
        # und dreimal Rauschen. Die Kachel sagt es weiterhin, aber dort, wo es
        # ohne Blick auf die Überschrift ankommt: in ihrer Beschreibung, die
        # der Bildschirmleser vorliest.
        assert "ührte Tour" in tile.accessibleDescription(), (
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


def test_a_tile_is_one_real_action_for_mouse_and_keyboard(screen: StartScreen) -> None:
    """Maus, Eingabe und Leertaste lösen denselben echten Knopf je einmal aus."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAccessible
    from PySide6.QtTest import QTest

    screen.show()
    QApplication.processEvents()
    tiles = screen.findChildren(ExampleTile)
    assert tiles
    tile = tiles[0]
    interface = QAccessible.queryAccessibleInterface(tile)
    assert interface is not None and interface.role() == QAccessible.Role.Button

    opened: list[str] = []
    screen.openRequested.connect(lambda path: opened.append(str(path)))
    for trigger in (
        lambda: QTest.mouseClick(tile, Qt.MouseButton.LeftButton),
        lambda: QTest.keyClick(tile, Qt.Key.Key_Return),
        lambda: QTest.keyClick(tile, Qt.Key.Key_Space),
    ):
        before = len(opened)
        trigger()
        assert opened[before:] == [str(tile.path)]


@pytest.mark.parametrize(("width", "height"), ((1040, 760), (800, 600)))
def test_the_tab_chain_follows_the_visible_page_and_scrolls_each_target_into_view(
    screen: StartScreen, width: int, height: int
) -> None:
    """Tab folgt von oben nach unten und lässt kein Ziel außerhalb des Rollfensters."""
    from PySide6.QtCore import QPoint, QRect, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QScrollArea, QToolButton

    screen.show_recent([Path("mein-projekt.p3d")])
    screen.resize(width, height)
    screen.show()
    QApplication.processEvents()
    scroll = screen.findChild(QScrollArea)
    heading = screen.more_section.findChild(QToolButton, "sectionHeading")
    assert scroll is not None and heading is not None
    guided = [tile for tile in screen.tiles if tile.entry.way]
    screen.new_button.setFocus(Qt.FocusReason.OtherFocusReason)
    for expected in (
        screen.open_button,
        screen.manual_button,
        screen.recent_list,
        *guided,
        screen.feedback_button,
        screen.support_button,
        heading,
    ):
        QTest.keyClick(screen, Qt.Key.Key_Tab)
        QApplication.processEvents()
        assert QApplication.focusWidget() is expected
        top_left = expected.mapTo(scroll.viewport(), QPoint(0, 0))
        assert scroll.viewport().rect().contains(QRect(top_left, expected.size())), (
            f"{expected!r} hat Fokus, liegt aber außerhalb des sichtbaren Rollfensters"
        )
    if width == 800:
        assert scroll.verticalScrollBar().value() > 0


@pytest.mark.parametrize("theme", ("dark", "light"))
def test_a_held_tile_changes_its_surface_without_jumping(qt_app: QApplication, theme: str) -> None:
    """Maus und Leertaste drücken die echte Fläche und lösen erst danach einmal aus."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.theme import apply_theme

    def pixels(tile: ExampleTile) -> bytes:
        return tile.grab().toImage().constBits().tobytes()

    def changed(before: bytes, after: bytes) -> int:
        return sum(
            before[offset : offset + 4] != after[offset : offset + 4]
            for offset in range(0, min(len(before), len(after)), 4)
        )

    previous = current_theme()
    apply_theme(qt_app, theme)  # type: ignore[arg-type]
    screen = StartScreen()
    try:
        screen.resize(1200, 900)
        screen.show()
        qt_app.processEvents()
        tile = screen.tiles[0]
        tile.setFocus(Qt.FocusReason.OtherFocusReason)
        QTest.mouseMove(tile, tile.rect().center())
        qt_app.processEvents()

        opened: list[Path] = []
        screen.openRequested.connect(opened.append)
        geometry = tile.geometry()
        label_geometry = [label.geometry() for label in tile.findChildren(QLabel)]

        resting = pixels(tile)
        QTest.mousePress(tile, Qt.MouseButton.LeftButton, pos=tile.rect().center())
        qt_app.processEvents()
        held_by_mouse = pixels(tile)
        assert tile.isDown()
        assert changed(resting, held_by_mouse) > tile.width() * tile.height() // 4
        assert tile.geometry() == geometry
        assert [label.geometry() for label in tile.findChildren(QLabel)] == label_geometry
        assert opened == []
        QTest.mouseRelease(tile, Qt.MouseButton.LeftButton, pos=tile.rect().center())
        assert opened == [tile.path]

        QTest.mouseMove(screen.new_button, screen.new_button.rect().center())
        tile.setFocus(Qt.FocusReason.OtherFocusReason)
        qt_app.processEvents()
        resting = pixels(tile)
        QTest.keyPress(tile, Qt.Key.Key_Space)
        qt_app.processEvents()
        held_by_keyboard = pixels(tile)
        assert tile.isDown()
        assert changed(resting, held_by_keyboard) > tile.width() * tile.height() // 4
        assert tile.geometry() == geometry
        assert [label.geometry() for label in tile.findChildren(QLabel)] == label_geometry
        assert opened == [tile.path]
        QTest.keyRelease(tile, Qt.Key.Key_Space)
        assert opened == [tile.path, tile.path]
    finally:
        screen.close()
        screen.deleteLater()
        apply_theme(qt_app, previous)


def test_a_tile_answers_pointer_and_keyboard_focus_without_motion(screen: StartScreen) -> None:
    """Tiefe bestätigt die ganze Zielfläche unmittelbar, ohne Animation."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtWidgets import QGraphicsDropShadowEffect

    screen.resize(1200, 900)
    screen.show()
    QApplication.processEvents()
    tile = screen.tiles[0]
    effect = tile.graphicsEffect()
    assert isinstance(effect, QGraphicsDropShadowEffect)

    QApplication.sendEvent(tile, QEvent(QEvent.Type.Leave))
    rest = effect.blurRadius()
    QApplication.sendEvent(tile, QEvent(QEvent.Type.Enter))
    assert effect.blurRadius() > rest

    tile.setFocus(Qt.FocusReason.OtherFocusReason)
    QApplication.sendEvent(tile, QEvent(QEvent.Type.Leave))
    assert effect.blurRadius() > rest, "Tastaturfokus braucht dieselbe zweite Rückmeldung"
    tile.clearFocus()
    assert effect.blurRadius() == rest


def test_an_empty_recent_list_is_a_line_not_a_box(screen: StartScreen) -> None:
    """Ein leerer Zustand darf klein sein; er muss nur seinen Platz wieder
    hergeben, wenn er gefüllt wird."""
    screen.show_recent([])
    assert not screen.recent_empty.isHidden()
    assert screen.recent_list.isHidden()

    screen.show_recent([Path("a.p3d"), Path("b.p3d")])
    assert screen.recent_empty.isHidden()
    assert not screen.recent_list.isHidden()
    assert screen.recent_list.count() == 2


def test_recent_projects_come_before_the_guided_tours(screen: StartScreen) -> None:
    """Weiterarbeiten steht vor Entdecken, sobald es etwas fortzusetzen gibt."""
    screen.show_recent([Path("mein-projekt.p3d")])
    screen.resize(1920, 1080)
    screen.show()
    QApplication.processEvents()

    assert screen.recent_list.geometry().bottom() < screen.examples_area.geometry().top()


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
    from app.ui.start_screen import TILE_COLUMNS
    from app.ui.style import WIDE

    screen.show()
    screen.resize(WIDE_LAYOUT_MIN_WIDTH + 4 * WIDE, 900)
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

    screen.resize(1200, 900)
    QApplication.processEvents()
    assert screen._columns == TILE_COLUMNS, "zwei Spalten bei mittlerer Breite"

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


@pytest.mark.parametrize(
    ("width", "columns"),
    (
        (640, 1),
        (800, 1),
        (904, 1),
        (1080, 2),
        (1200, 2),
        (1536, 2),
        (1920, 3),
        (2560, 3),
        (3072, 3),
    ),
)
def test_the_start_layout_degrades_without_horizontal_overflow(
    screen: StartScreen, width: int, columns: int
) -> None:
    """Von 640 bis 3072 Punkten bleibt jede Kachel lesbar und erreichbar.

    Zwei Kacheln auf 640 Punkten ließen nach Bild, Innenrand und Abstand nur
    eine Wortkolonne. Der Rückweg ist eine Spalte und senkrechtes Rollen — nie
    eine zweite Achse, die den wichtigsten Inhalt außerhalb des Fensters legt.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea

    screen.resize(width, 900)
    screen.show()
    QApplication.processEvents()

    scroll = screen.findChild(QScrollArea)
    assert scroll is not None
    assert screen._columns == columns
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert scroll.horizontalScrollBar().maximum() == 0, (
        f"{width}: der erste Eindruck verlangt waagerechtes Rollen"
    )
    assert screen.column.width() <= scroll.viewport().width(), (
        f"{width}: die Inhaltsspalte ist breiter als ihr Sichtfeld"
    )

    starts = [tile for tile in screen.tiles if tile.entry.way]
    wanted_start_columns = 1 if columns == 1 else 2
    positions = [screen.examples_grid.getItemPosition(index)[:2] for index in range(len(starts))]
    assert max(column for _row, column in positions) + 1 == wanted_start_columns
    if columns > 1:
        assert min(tile.width() for tile in starts) >= TILE_MIN_WIDTH
    screen.hide()


@pytest.mark.parametrize("themes", (("dark", "light"), ("light", "dark")))
def test_primary_start_actions_are_large_and_examples_are_readable(
    qt_app: QApplication, themes: tuple[str, str]
) -> None:
    """Die echte Themenkette darf den drei sicheren Trefferflächen nichts nehmen."""
    from app.ui.style import TARGET_SIZE
    from app.ui.theme import apply_theme

    assert PREVIEW_HEIGHT == 88, "die Vorschau soll erkennbar und zugleich kompakt bleiben"
    before = current_theme()
    try:
        for theme in themes:
            apply_theme(qt_app, theme)  # type: ignore[arg-type]
            screen = StartScreen()
            screen.resize(1536, 740)
            screen.show()
            qt_app.processEvents()
            area = screen.findChild(DropArea)
            assert area is not None and area.minimumHeight() == DROP_AREA_MIN_HEIGHT
            for button in (screen.new_button, screen.open_button, screen.manual_button):
                measures = button.minimumHeight(), button.sizeHint().height(), button.height()
                assert min(measures) >= TARGET_SIZE, (
                    f"{theme}: {button.text()!r} misst min/sizeHint/aktuell {measures} "
                    f"statt mindestens {TARGET_SIZE}"
                )
            screen.close()
            screen.deleteLater()
    finally:
        apply_theme(qt_app, before)


def test_the_start_screen_offers_feedback_and_voluntary_support_as_two_action_cards(
    qt_app: QApplication,
) -> None:
    """Die zwei Nebenwege bleiben zugänglich, ohne einen fünften Hauptweg vorzutäuschen."""
    from app.ui.style import TARGET_SIZE, stylesheet

    before = qt_app.styleSheet()
    qt_app.setStyleSheet(stylesheet("light", 10))
    screen = StartScreen()
    feedback: list[bool] = []
    support: list[bool] = []
    screen.feedbackRequested.connect(lambda: feedback.append(True))
    screen.supportRequested.connect(lambda: support.append(True))
    screen.resize(800, 600)
    screen.show()
    qt_app.processEvents()

    assert screen.secondary_actions == [screen.feedback_button, screen.support_button]
    assert screen.feedback_button.accessibleName() == "Feedback geben"
    assert screen.support_button.accessibleName() == "Solidon freiwillig unterstützen"
    assert "PayPal" not in screen.support_button.accessibleName()
    assert "Eine Person" in screen.feedback_button.detail_label.text()
    assert screen.feedback_button.hint_label.text() == "Vorschau vor dem Senden"
    assert screen.support_button.detail_label.text() == (
        "Hilft bei Veröffentlichung, Signierung, Tests und Website"
    )
    assert screen.support_button.hint_label.text() == "PayPal erst im nächsten Schritt"
    for button in screen.secondary_actions:
        assert isinstance(button, QPushButton)
        assert button.objectName() == "startActionCard"
        assert min(button.sizeHint().height(), button.height()) >= TARGET_SIZE
        assert button.minimumWidth() >= TARGET_SIZE
        assert button.focusPolicy() == Qt.FocusPolicy.StrongFocus
        assert button.accessibleDescription()
        assert button.detail_label.text() in button.accessibleDescription()
        assert button.hint_label.text() in button.accessibleDescription()
        assert button.icon_label.pixmap() is not None
        assert not button.icon_label.pixmap().isNull()
        assert not button.findChildren(QPushButton), "die ganze Karte ist genau ein Schaltziel"

    screen.feedback_button.click()
    screen.support_button.click()

    assert feedback == [True]
    assert support == [True]

    from PySide6.QtGui import QAccessible

    for button in screen.secondary_actions:
        interface = QAccessible.queryAccessibleInterface(button)
        assert interface is not None and interface.role() == QAccessible.Role.Button
    screen.deleteLater()
    qt_app.setStyleSheet(before)


@pytest.mark.parametrize(
    ("width", "height", "columns"),
    ((1920, 1080, 2), (1040, 760, 2), (800, 600, 1), (640, 720, 1)),
)
def test_the_two_quiet_start_actions_never_add_a_horizontal_scroll_axis(
    qt_app: QApplication, width: int, height: int, columns: int
) -> None:
    """Breit stehen die Karten als Paar, schmal gestapelt und niemals seitlich."""
    from PySide6.QtWidgets import QScrollArea

    from app.ui.style import stylesheet

    before = qt_app.styleSheet()
    qt_app.setStyleSheet(stylesheet("dark", 10))
    screen = StartScreen()
    screen.resize(width, height)
    screen.show()
    qt_app.processEvents()

    scroll = screen.findChild(QScrollArea)
    assert scroll is not None
    assert scroll.horizontalScrollBar().maximum() == 0
    assert screen._secondary_columns == columns
    positions = [
        screen.secondary_grid.getItemPosition(index)[:2]
        for index in range(screen.secondary_grid.count())
    ]
    assert max(column for _row, column in positions) + 1 == columns
    for button in screen.secondary_actions:
        assert button.width() <= screen.column.width()
        assert button.height() >= 44
        assert button.detail_label.heightForWidth(button.detail_label.width()) <= (
            button.detail_label.height()
        )
        assert button.hint_label.heightForWidth(button.hint_label.width()) <= (
            button.hint_label.height()
        )
    if columns == 2:
        assert abs(screen.feedback_button.width() - screen.support_button.width()) <= 1
    else:
        assert all(
            abs(button.width() - screen.secondary_area.width()) <= 1
            for button in screen.secondary_actions
        )
    screen.deleteLater()
    qt_app.setStyleSheet(before)


def test_the_feedback_card_opens_the_existing_survey_kind(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Startaktion öffnet den halbstündigen Bogen, nicht den Ideenmodus."""
    from app.core.support import KIND_SURVEY
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    kinds: list[str] = []
    shown: list[str] = []

    class SurveyDialog:
        def show(self) -> None:
            shown.append("show")

        def raise_(self) -> None:
            shown.append("raise")

    def make_dialog(kind: str) -> SurveyDialog:
        kinds.append(kind)
        return SurveyDialog()

    monkeypatch.setattr(window, "_support_dialog", make_dialog)
    window.start_screen.feedback_button.click()

    assert kinds == [KIND_SURVEY]
    assert shown == ["show", "raise"]


def test_the_support_card_opens_only_the_local_notice_dialog(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Karte selbst öffnet weder Website noch PayPal, sondern nur den Hinweis."""
    from app.ui.dialogs import DonationDialog
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    shown: list[str] = []
    before = (
        tuple(window.session.project.document.ops),
        tuple(window.session.project.document.transactions),
    )
    monkeypatch.setattr(
        DonationDialog, "exec", lambda dialog: shown.append(dialog.windowTitle()) or 0
    )

    window.start_screen.support_button.click()

    assert shown == ["Solidon3D unterstützen"]
    after = (
        tuple(window.session.project.document.ops),
        tuple(window.session.project.document.transactions),
    )
    assert after == before, "eine Nebenaktion verändert weder Szene noch Verlauf"


@pytest.mark.parametrize("key", (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space))
def test_a_start_action_card_activates_once_on_key_release(
    qt_app: QApplication, key: Qt.Key
) -> None:
    """Tastatur und Maus lösen denselben einen Dialogzug aus — beim Loslassen."""
    from PySide6.QtTest import QTest

    screen = StartScreen()
    screen.show()
    qt_app.processEvents()
    requests: list[bool] = []
    screen.feedbackRequested.connect(lambda: requests.append(True))
    card = screen.feedback_button
    card.setFocus(Qt.FocusReason.TabFocusReason)

    QTest.keyPress(card, key)
    assert not requests
    QTest.keyRelease(card, key)

    assert requests == [True]


def test_a_double_click_requests_at_most_one_start_action(qt_app: QApplication) -> None:
    """Ein hastiger Doppelklick öffnet keine zwei modalen Fenster übereinander."""
    from PySide6.QtTest import QTest

    screen = StartScreen()
    screen.show()
    qt_app.processEvents()
    requests: list[bool] = []
    screen.supportRequested.connect(lambda: requests.append(True))

    QTest.mouseDClick(screen.support_button, Qt.MouseButton.LeftButton)

    assert requests == [True]


def test_the_start_action_cards_animate_without_making_motion_the_only_feedback(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bewegung veredelt die Zustände; Fläche und Rahmen antworten sofort."""
    from PySide6.QtCore import QAbstractAnimation, QEvent, QPropertyAnimation

    import app.ui.start_screen as start_screen

    monkeypatch.setattr(start_screen, "animations_enabled", lambda: True)
    screen = StartScreen()
    screen.resize(1040, 760)
    screen.show()
    qt_app.processEvents()
    card = screen.feedback_button
    quiet_blur = card._shadow.blurRadius()

    QApplication.sendEvent(card, QEvent(QEvent.Type.Enter))

    animations = card.findChildren(QPropertyAnimation)
    assert len(animations) == 3
    assert card._depth_animation is not None
    assert card._depth_animation.state() == QAbstractAnimation.State.Running
    blur = next(animation for animation in animations if animation.propertyName() == b"blurRadius")
    assert float(blur.endValue()) > quiet_blur
    assert card._hovered, "die statische Fläche antwortet unabhängig von der Bewegung"


def test_the_start_action_cards_keep_the_same_states_with_reduced_motion(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reduzierte Bewegung behält Fokus, Druck, Tiefe und Handlung sofort."""
    from PySide6.QtCore import QEvent, QPropertyAnimation

    from app.ui.motion import animations_enabled

    monkeypatch.setenv("SOLIDON3D_MOTION", "aus")
    assert not animations_enabled()
    screen = StartScreen()
    screen.resize(1040, 760)
    screen.show()
    qt_app.processEvents()
    card = screen.feedback_button
    quiet_blur = card._shadow.blurRadius()

    QApplication.sendEvent(card, QEvent(QEvent.Type.Enter))
    qt_app.processEvents()

    assert card._shadow.blurRadius() > quiet_blur
    assert not card.findChildren(QPropertyAnimation)
    card.setFocus(Qt.FocusReason.TabFocusReason)
    assert card.hasFocus()
    focused_blur = card._shadow.blurRadius()
    card.setDown(True)
    card._paint_depth()
    assert card._shadow.blurRadius() < focused_blur
    assert not card.findChildren(QPropertyAnimation)


def test_the_wide_layout_starts_only_when_a_third_column_has_room(screen: StartScreen) -> None:
    """Ein 1536er Fenster zeigt vier Wege als ruhiges 2×2 statt als breite Bühne."""
    from app.ui.style import WIDE

    outer = 4 * WIDE
    screen.resize(WIDE_LAYOUT_MIN_WIDTH + outer - 1, 900)
    screen.show()
    QApplication.processEvents()
    assert screen._columns == 2
    assert screen.column.maximumWidth() == COLUMN_WIDTH

    screen.resize(WIDE_LAYOUT_MIN_WIDTH + outer, 900)
    QApplication.processEvents()
    assert screen._columns == 3
    assert screen.column.maximumWidth() == WIDE_COLUMN_WIDTH
    screen.hide()


def test_two_columns_start_only_when_both_tiles_and_the_gap_fit(screen: StartScreen) -> None:
    """Die Rasterrechnung enthält die echte Fuge und gewährt der Spalte den Raum."""
    from app.ui.style import WIDE

    outer = 4 * WIDE
    screen.show()
    screen.resize(MEDIUM_LAYOUT_MIN_WIDTH + outer - 1, 900)
    QApplication.processEvents()
    assert screen._columns == 1

    screen.resize(MEDIUM_LAYOUT_MIN_WIDTH + outer, 900)
    QApplication.processEvents()
    starts = [tile for tile in screen.tiles if tile.entry.way]
    assert screen._columns == 2
    assert screen.examples_grid.horizontalSpacing() == TILE_GRID_SPACING
    assert min(tile.width() for tile in starts) >= TILE_MIN_WIDTH


@pytest.mark.parametrize(("width", "height"), ((1536, 740), (1920, 970)))
def test_the_empty_desktop_start_fits_without_scrolling(
    qt_app: QApplication, width: int, height: int
) -> None:
    """Im echten Hauptfenster bleiben alle vier Einstiege im ersten Blick."""
    from PySide6.QtWidgets import QScrollArea

    from app.ui.style import stylesheet

    before = qt_app.styleSheet()
    qt_app.setStyleSheet(stylesheet("dark", 10))
    screen = StartScreen()
    try:
        screen.resize(width, height)
        screen.show()
        qt_app.processEvents()
        scroll = screen.findChild(QScrollArea)
        assert scroll is not None
        assert scroll.horizontalScrollBar().maximum() == 0
        assert scroll.verticalScrollBar().maximum() == 0, (
            f"{width}×{height}: die vier Einstiege liegen wieder unter der Kante"
        )
    finally:
        screen.deleteLater()
        qt_app.setStyleSheet(before)


@pytest.mark.parametrize("font_size", (10, 13, 15, 20))
def test_the_start_screen_has_no_second_scroll_axis_at_100_to_200_percent(
    qt_app: QApplication, font_size: int
) -> None:
    """Größere Systemschrift macht die Seite länger, aber nie breiter."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea

    from app.ui.style import stylesheet

    before = qt_app.styleSheet()
    qt_app.setStyleSheet(stylesheet("light", font_size))
    screen = StartScreen()
    try:
        screen.resize(1920, 1080)
        screen.show()
        qt_app.processEvents()

        scroll = screen.findChild(QScrollArea)
        assert scroll is not None
        assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        assert scroll.horizontalScrollBar().maximum() == 0
        assert all(tile.accessibleName() for tile in screen.tiles)
        assert all(tile.accessibleDescription() for tile in screen.tiles)
    finally:
        screen.deleteLater()
        qt_app.setStyleSheet(before)


@pytest.mark.parametrize("width", (800, 1536))
@pytest.mark.parametrize("font_size", (10, 13, 15, 20))
def test_the_drop_area_wraps_every_line_at_large_system_text(
    qt_app: QApplication, width: int, font_size: int
) -> None:
    """Kein Ablagetext ragt unsichtbar über seine echte Beschriftungsfläche."""
    from app.ui.style import stylesheet

    before = qt_app.styleSheet()
    qt_app.setStyleSheet(stylesheet("light", font_size))
    screen = StartScreen()
    try:
        screen.resize(width, 1080)
        screen.show()
        qt_app.processEvents()
        area = screen.findChild(DropArea)
        assert area is not None and area.accessibleName()
        labels = [label for label in area.findChildren(QLabel) if label.text()]
        assert labels
        for label in labels:
            assert label.wordWrap(), f"{width}/{font_size}: {label.text()!r} bricht nicht um"
            needed = label.heightForWidth(label.contentsRect().width())
            assert needed <= label.contentsRect().height(), (
                f"{width}/{font_size}: {label.text()!r} braucht {needed} Punkte Höhe, "
                f"hat aber nur {label.contentsRect().height()}"
            )
    finally:
        screen.deleteLater()
        qt_app.setStyleSheet(before)


def test_the_tour_note_stands_once_above_the_tiles(qt_app: QApplication) -> None:
    """Viermal derselbe Satz ist einmal Information und dreimal Rauschen (B27).

    Unter jedem der vier Kacheltitel stand „Geführte Tour · Schritt für
    Schritt" — dieselbe Aussage über dieselbe Sache, viermal untereinander im
    selben Blickfeld. Was für alle vier gilt, gehört über die Gruppe: Die
    Überschrift „Wo fange ich an?" ist der Ort, an dem der Satz einmal steht
    und trotzdem für jede Kachel gilt.

    Am Bildschirmleser ändert das nichts — dort trägt jede Kachel den Hinweis
    weiter in ihrer Beschreibung, weil ein Vorleser nicht sieht, was darüber
    steht.
    """
    from app.ui.start_screen import StartScreen

    screen = StartScreen()
    screen.show()
    qt_app.processEvents()

    # Gesucht wird der Wortstamm, nicht der ganze Satz: Über der Gruppe heißt
    # es „Vier geführte Touren", in der Kachelbeschreibung „Geführte Tour" —
    # dieselbe Auskunft, zwei Beugungen.
    sichtbar = [
        label.text()
        for label in screen.findChildren(QLabel)
        if label.isVisibleTo(screen) and "ührte Tour" in label.text()
    ]
    beschreibungen = [
        widget.accessibleDescription()
        for widget in screen.findChildren(QWidget)
        if "Geführte Tour" in widget.accessibleDescription()
    ]

    assert len(sichtbar) <= 1, f"{len(sichtbar)}-mal derselbe Satz: {sichtbar[:3]}"
    assert sichtbar, "einmal muss er dastehen — sonst weiß niemand, dass es Touren sind"
    assert len(beschreibungen) >= 4, "jede Kachel sagt es dem Bildschirmleser weiter"


def test_the_manual_button_names_its_action(qt_app: QApplication) -> None:
    """Ein Knopf, der einen Satz trägt, sprengt seine Nachbarn (B27).

    Gemessen: 249 Punkte gegen 99 und 113 der beiden Nachbarn — mehr als
    doppelt so breit, weil er „Handbuch — die ersten fünfzehn Minuten" trug.
    Der Knopf nennt seine Handlung, der Zusatz gehört in den Hinweis daneben;
    so hält es die Anwendung an jeder anderen Stelle.
    """
    from app.ui.start_screen import StartScreen

    screen = StartScreen()
    screen.show()
    qt_app.processEvents()

    knopf = screen.manual_button
    nachbarn = [screen.new_button.sizeHint().width(), screen.open_button.sizeHint().width()]

    assert knopf.sizeHint().width() <= 2 * max(nachbarn), (
        f"{knopf.text()!r} misst {knopf.sizeHint().width()}, die Nachbarn {nachbarn}"
    )
    assert "fünfzehn" in knopf.toolTip(), "was wegfällt, steht im Hinweis"
