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
