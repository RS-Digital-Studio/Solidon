"""Der Bausteinkatalog als Fenster (§2.6, §24.3).

Offscreen geprüft wird die Verdrahtung, keine Pixel: das Raster, die
Gruppenüberschriften, die Suche und dass jeder Baustein der Bibliothek eine
Kachel bekommt.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListView

from app.core.knowledge.parts import PARTS
from app.ui.catalog import TILE_WIDTH, PartCatalog


def catalog_names(catalog: PartCatalog) -> set[str]:
    """Die Bausteinnamen aller Kacheln — Überschriften tragen keinen."""
    names = set()
    for row in range(catalog.list.count()):
        item = catalog.list.item(row)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) is not None:
            names.add(item.data(Qt.ItemDataRole.UserRole))
    return names


def test_the_catalogue_is_a_grid_not_a_list(qt_app: QApplication) -> None:
    """§2.6: eine Bibliothek, die man sieht.

    Als Liste mit bildhohen Zeilen zeigte das Fenster zweieinhalb von
    dreizehn Bausteinen — der Rest existierte nur hinter der Bildlaufleiste.
    """
    catalog = PartCatalog()

    assert catalog.list.viewMode() == QListView.ViewMode.IconMode
    assert catalog.list.isWrapping()


def test_every_part_has_a_tile(qt_app: QApplication) -> None:
    catalog = PartCatalog()

    assert {spec.name for spec in PARTS.all()} <= catalog_names(catalog)


def test_a_heading_spans_the_row(qt_app: QApplication) -> None:
    """Im Raster wäre eine Überschrift sonst eine Kachel unter vielen, und
    die Gruppe begänne irgendwo in der Zeilenmitte.
    """
    catalog = PartCatalog()
    catalog.resize(740, 640)
    # Die Breite einer Zeile kennt erst das gezeigte Fenster — vorher hat der
    # Viewport der Liste keine; genau darum zieht resizeEvent die Hinweise nach.
    catalog.show()
    # Zweimal: der erste Durchlauf trägt das Resize aus, der zweite den
    # nachgelagerten Abgleich der Überschriftenbreiten.
    qt_app.processEvents()
    qt_app.processEvents()
    catalog.close()

    headings = [
        catalog.list.item(row)
        for row in range(catalog.list.count())
        if catalog.list.item(row).data(Qt.ItemDataRole.UserRole) is None
    ]
    assert headings, "ohne Gruppen prüft dieser Test nichts"
    for heading in headings:
        assert heading.sizeHint().width() > TILE_WIDTH
        assert not heading.flags() & Qt.ItemFlag.ItemIsSelectable


def test_every_group_starts_its_own_row(qt_app: QApplication) -> None:
    """Jede Gruppe fängt links an, keine Überschrift steht neben Kacheln.

    Die Breite allein reichte nicht: Der Kachelmodus rechnet seine Zeilen beim
    Einfügen und nimmt ein ``setSizeHint``, das danach kommt, zur Kenntnis, ohne
    es anzuwenden. Sichtbar wurde das erst auf einem breiten Dialog —
    „Verbindungen", „Einlegeteile" und „Mechanik" standen nebeneinander in der
    obersten Zeile, jede über den Kacheln einer fremden Gruppe. Deshalb wird
    hier die *Lage* geprüft und nicht der Hinweis darauf: Der Hinweis stimmte.
    """
    catalog = PartCatalog()
    catalog.resize(1560, 1000)
    catalog.show()
    qt_app.processEvents()
    qt_app.processEvents()

    rows = [
        (row, catalog.list.item(row))
        for row in range(catalog.list.count())
        if catalog.list.item(row).data(Qt.ItemDataRole.UserRole) is None
    ]
    catalog.close()

    assert len(rows) > 1, "mit einer Gruppe prüft dieser Test nichts"
    left = min(catalog.list.visualItemRect(item).x() for _row, item in rows)
    for row, heading in rows:
        rect = catalog.list.visualItemRect(heading)
        assert rect.x() == left, (
            f"„{heading.text()}“ steht bei x={rect.x()} statt bei {left} — "
            "die Überschrift hat keine eigene Zeile"
        )
        following = catalog.list.item(row + 1)
        if following is not None:
            assert catalog.list.visualItemRect(following).y() > rect.y(), (
                f"die erste Kachel unter „{heading.text()}“ steht in derselben Zeile"
            )


def test_insert_stays_shut_until_something_is_chosen(qt_app: QApplication) -> None:
    """Ein Knopf, der nichts tun kann, verspricht auch nichts.

    „Einfügen" stand beim Öffnen in voller Akzentfarbe da, obwohl nichts
    gewählt war und rechts daneben „Wählen Sie einen Baustein" stand. Er nahm
    den Klick an, schloss den Dialog — und setzte nichts in die Szene:
    ``_accept`` rief ``accept()`` auch ohne Baustein. Das ist die stillste Art,
    jemanden ratlos zu machen; ein Fehler, der nicht einmal sagt, dass etwas
    nicht ging.
    """
    catalog = PartCatalog()
    assert catalog._insert is not None
    assert not catalog._insert.isEnabled(), "ohne Auswahl kann er nichts einfügen"

    for row in range(catalog.list.count()):
        item = catalog.list.item(row)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) is not None:
            catalog.list.setCurrentItem(item)
            break

    assert catalog.chosen() is not None, "ohne Kachel prüft dieser Test nichts"
    assert catalog._insert.isEnabled(), "mit Auswahl muss er wieder gehen"


def test_the_search_narrows_and_empties_the_grid(qt_app: QApplication) -> None:
    """Die Suche filtert die Kacheln; ohne Treffer bleibt auch keine
    Überschrift stehen, die eine leere Gruppe verspräche.

    **Die Anfrage muss wirklich unsinnig sein, nicht nur unsinnig aussehen.**
    Hier stand „zzz-gibt-es-nicht", und `PARTS.search` zerlegt an allem, was
    kein Wortzeichen ist — aus dem Bindestrich wurden vier Wörter, darunter
    „gibt". Als ein Baustein einen Beschreibungssatz mit „gibt es" bekam, fand
    die angeblich leere Suche ihn. Ein Buchstabensalat ohne Trennzeichen kann
    das nicht passieren.
    """
    catalog = PartCatalog()
    everything = catalog.list.count()

    catalog.search.setText("qwertzuiopasdfgh")
    # Eine Zeile bleibt, und sie ist der Satz, dass nichts passt — ein leeres
    # Raster sagte das nicht, und die Detailspalte forderte weiter auf, einen
    # Baustein zu wählen, den es dort nicht gibt.
    assert catalog_names(catalog) == set(), "kein Baustein darf übrig bleiben"
    assert catalog.list.count() == 1
    assert "qwertzuiopasdfgh" in catalog.list.item(0).text()
    assert not catalog.list.item(0).flags() & Qt.ItemFlag.ItemIsSelectable
    assert catalog.chosen() is None

    catalog.search.setText("")
    assert catalog.list.count() == everything


def test_the_catalogue_grows_with_the_screen(qt_app: QApplication) -> None:
    """Der Katalog zeigte vier Kacheln von neunzehn.

    ``resize(980, 640)`` galt auf jedem Bildschirm: die Rasterfläche war 718 mal
    562, also vier Kacheln je Zeile und zweieinhalb Zeilen, und der Rollbalken
    hatte 1240 Pixel Weg. §2.6 will eine Bibliothek, die man *sieht* — vier von
    neunzehn ist eine Liste, durch die man sich arbeitet.

    Nicht die Kachel ist der Grund: Ihre Breite kommt vom Text, und wer sie
    schrumpft, schneidet „Schraubenloch mit Senkung" ab. Also wächst der Dialog.
    Gerechnet wird hier und nicht am Fenster gemessen — offscreen gibt es keinen
    Bildschirm, und dort gilt die Mindestgröße.
    """
    from app.ui.catalog import (
        CATALOG_MAX,
        CATALOG_MIN,
        CATALOG_SHARE,
        DETAIL_WIDTH,
        TILE_WIDTH,
        catalog_size,
    )
    from app.ui.style import NORMAL

    def for_screen(width: int, height: int) -> tuple[int, int]:
        return (
            max(CATALOG_MIN[0], min(int(width * CATALOG_SHARE), CATALOG_MAX[0])),
            max(CATALOG_MIN[1], min(int(height * CATALOG_SHARE), CATALOG_MAX[1])),
        )

    # Gefragt wird nach dem Bildschirm, den dieser Lauf hat, statt einen
    # anzunehmen. Offscreen gibt es keinen und die Mindestgröße gilt; unter
    # Xvfb — so läuft die CI, seit VTK dort einen GL-Kontext braucht — gibt es
    # einen von 1920 mal 1080, und dann ist genau die Rechnung oben das
    # erwartete Ergebnis. Die Annahme „hier ist nie ein Bildschirm" hat diesen
    # Test in der CI rot gemacht, ohne dass am Katalog etwas falsch war.
    screen = QApplication.primaryScreen() if QApplication.screens() else None
    if screen is None:
        assert catalog_size() == CATALOG_MIN, "ohne Bildschirm bleibt es bei der Mindestgröße"
    else:
        area = screen.availableGeometry()
        assert catalog_size() == for_screen(area.width(), area.height()), (
            "der Katalog folgt dem Bildschirm nicht"
        )

    def per_row(width: int) -> int:
        return max(1, (width - DETAIL_WIDTH - 6 * NORMAL) // (TILE_WIDTH + NORMAL))

    small = for_screen(1024, 768)
    assert small == CATALOG_MIN, "auf einem kleinen Bildschirm bleibt es, wie es war"

    wide = for_screen(1920, 1040)
    assert wide[0] <= CATALOG_MAX[0] and wide[1] <= CATALOG_MAX[1], "gewachsen wird mit Deckel"
    assert per_row(wide[0]) >= per_row(CATALOG_MIN[0]) + 2, (
        f"{per_row(wide[0])} statt {per_row(CATALOG_MIN[0])} Kacheln je Zeile ist keine Änderung"
    )

    huge = for_screen(5120, 2880)
    assert huge == CATALOG_MAX, "auf einer Wand hört das Wachsen auf"
