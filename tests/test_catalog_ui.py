"""Der Bausteinkatalog als Fenster (§2.6, §24.3).

Offscreen geprüft wird die Verdrahtung, keine Pixel: das Raster, die
Gruppenüberschriften, die Suche und dass jeder Baustein der Bibliothek eine
Kachel bekommt.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListView, QListWidgetItem

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


def headings_of(catalog: PartCatalog) -> list[QListWidgetItem]:
    """Die Gruppenüberschriften — sie tragen als einzige keinen Bausteinnamen."""
    return [
        item
        for row in range(catalog.list.count())
        if (item := catalog.list.item(row)) is not None
        and item.data(Qt.ItemDataRole.UserRole) is None
    ]


def wait_until(ready: Callable[[], bool], what: str, timeout_ms: int = 5000) -> None:
    """Wartet auf eine Wirkung statt auf eine Anzahl Ereignisdurchläufe.

    **Zwei ``processEvents`` waren eine Annahme, keine Bedingung.** Der Katalog
    zieht die Überschriftenbreiten in einem ``QTimer.singleShot(0, …)`` nach,
    der erst nach dem Resize der Liste läuft. Unter Windows kommt beides in den
    ersten beiden Durchläufen an, unter Xvfb kommt das Resize später — dort maß
    der Test ein Layout, das es noch nicht gab, und meldete ``assert 8 > 8``:
    Überschrift und erste Kachel in derselben Zeile, weil die Zeile noch gar
    nicht umgebrochen war.
    """
    application = QApplication.instance()
    assert application is not None
    deadline = time.monotonic() + timeout_ms / 1000
    while not ready():
        if time.monotonic() > deadline:
            raise AssertionError(f"{what} kam in {timeout_ms} ms nicht zustande")
        application.processEvents()


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
    # Gewartet wird auf die Vorbedingung, nicht auf das Ergebnis: dass der
    # Viewport seine Breite hat. Was er daraus macht, ist die Behauptung
    # darunter — und die wäre keine mehr, wenn hier schon auf sie gewartet
    # würde.
    wait_until(
        lambda: catalog.list.viewport().width() > TILE_WIDTH,
        "der Viewport bekam nie seine Breite",
    )
    headings = headings_of(catalog)
    catalog.close()

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
    # Gewartet wird darauf, dass die Überschriften ihre Zeilenbreite *bekommen*
    # haben — geprüft wird darunter, ob das Raster sie auch *angewandt* hat.
    # Das ist genau der Unterschied, um den es in diesem Test geht: Der Hinweis
    # stimmte schon immer, die Lage nicht.
    wait_until(
        lambda: all(item.sizeHint().width() > TILE_WIDTH for item in headings_of(catalog)),
        "die Überschriften bekamen nie ihre Zeilenbreite",
    )

    rows = [
        (row, item)
        for row in range(catalog.list.count())
        if (item := catalog.list.item(row)) is not None
        and item.data(Qt.ItemDataRole.UserRole) is None
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


def test_a_saved_part_joins_the_grid_and_gets_its_picture(qt_app: QApplication) -> None:
    """Nach dem Speichern steht der neue Baustein **neben** den alten (§24.5).

    Drei Funde aus demselben Bild, 25.08.2026 im echten Fenster: Der Katalog
    zeigte nach dem Speichern nur noch das Rezept (der Name war als Suchtext
    in ``show_parts`` gelandet), das Rezept hatte kein Vorschaubild (die
    Bilderkette endet, sobald alles gerendert ist, und lief nie wieder an),
    und es trug keine Kennzeichnung als eigener Baustein (``own`` kannte nur
    die ``.py``-Gestalt).
    """
    import dataclasses

    from PySide6.QtGui import QPixmap

    from app.i18n import tr
    from app.ui.catalog import describe

    donor = next(spec for spec in PARTS.all() if "magnet" not in spec.name)
    nachzuegler = dataclasses.replace(donor, name="nachzuegler_probe", source="recipe")
    assert nachzuegler.own, "ein Rezept gehört dem Kunden — §24.5 will die Kennzeichnung"
    assert tr("eigener Baustein") in describe(nachzuegler)

    catalog = PartCatalog()
    try:
        # Die Bilder der Bibliothek gelten als fertig — geprüft wird, dass die
        # Kette für den Nachzügler wieder anläuft, nicht, dass sie achtzehn
        # Bausteine rendern kann; das tut ``test_parts_catalog`` bereits.
        for existing in PARTS.all():
            catalog._previews.setdefault(existing.name, QPixmap(1, 1))

        PARTS.register(nachzuegler)
        assert "nachzuegler_probe" not in catalog_names(catalog), (
            "vor dem Auffrischen weiß der Katalog nichts von ihm"
        )

        catalog.refresh()
        names = catalog_names(catalog)
        assert "nachzuegler_probe" in names
        assert donor.name in names, "die mitgelieferten bleiben stehen — der Name ist keine Suche"
        assert catalog.search.text() == "", "das Suchfeld bleibt leer"
        wait_until(
            lambda: "nachzuegler_probe" in catalog._previews,
            "das Vorschaubild des Nachzüglers",
        )

        # Eine stehende Suche bleibt stehen — auffrischen heißt nicht leeren.
        catalog.search.setText("Magnet")
        catalog.refresh()
        assert catalog.search.text() == "Magnet"
        assert "nachzuegler_probe" not in catalog_names(catalog), "die Suche gilt weiter"
    finally:
        catalog.release()
        # Über den öffentlichen Weg zurück: ``remove`` ist für genau diesen
        # Fall da und ein unbekannter Name ist dort kein Fehler. Wer am
        # Wörterbuch vorbei aufräumt, prüft eine Kette, die es beim Kunden
        # nicht gibt — und merkt es nicht, wenn das Register eines Tages mehr
        # zurückzunehmen hat als einen Eintrag.
        PARTS.remove("nachzuegler_probe")


def test_a_failed_or_missing_range_check_is_written_on_the_entry(qt_app: QApplication) -> None:
    """§24.5 verlangt den Warnhinweis am Katalogeintrag, kein Verbot.

    ``range_passed`` wurde geschrieben, deklariert und geprüft — und von
    keiner Oberfläche gelesen: Ein Rezept mit gebrochenem Bereichstest stand
    im Katalog wie jedes andere, und der Satz im Rezeptdialog („Der Katalog
    zeigt das an") war unwahr. Gefunden im Review vom 26.08.2026, von zwei
    Prüfläufen unabhängig.
    """
    import dataclasses

    from app.i18n import tr
    from app.ui.catalog import RANGE_MARKER, describe, detail

    donor = next(iter(PARTS.all()))
    broken = dataclasses.replace(donor, source="recipe", range_passed=False)
    unchecked = dataclasses.replace(donor, source="recipe", range_passed=None)
    passed = dataclasses.replace(donor, source="recipe", range_passed=True)

    assert tr("an den Grenzen kam kein brauchbarer Körper heraus") in describe(broken)
    assert RANGE_MARKER in describe(broken), "Regel 18: Zeichen und Satz, nicht nur eines"
    assert tr("der Bereichstest ist für diesen Baustein nie gelaufen") in describe(unchecked)
    assert "Bereichstest" not in describe(passed) and "Grenzen" not in describe(passed)

    assert tr("an den Grenzen kam kein brauchbarer Körper heraus") in detail(broken)
    assert tr("der Bereichstest ist für diesen Baustein nie gelaufen") in detail(unchecked)

    # Ein mitgelieferter Baustein trägt ``None``, weil sein Bereich in der
    # Suite gefahren wird — der Katalog darf ihn nicht als ungeprüft anschreiben.
    assert "Bereichstest" not in describe(donor) and "Grenzen" not in describe(donor)


def test_the_locked_save_button_shows_its_reason_beside_it(qt_app: QApplication) -> None:
    """„Sagt daneben, was ihm fehlt" — das Handbuch versprach es, der Grund
    stand aber nur im Tooltip, und die Detailspalte desselben Dialogs sagt
    selbst, dass einen Tooltip nur findet, wer weiß, dass er da ist.

    ``isVisibleTo``, nicht ``isVisible``: In einem nie gezeigten Fenster lügt
    das zweite (siehe Regeln der Oberfläche).
    """
    catalog = PartCatalog()
    try:
        catalog.set_can_save(False, "Dafür muss zuerst etwas gerechnet sein.")
        assert catalog.save_hint.isVisibleTo(catalog), "der Grund steht sichtbar da"
        assert "gerechnet" in catalog.save_hint.text()
        assert not catalog.save_part.isEnabled()

        catalog.set_can_save(True, "")
        assert not catalog.save_hint.isVisibleTo(catalog), "frei heißt: keine Zeile"
        assert catalog.save_part.isEnabled()
    finally:
        catalog.release()


def test_without_a_body_the_catalogue_shows_but_does_not_insert(qt_app: QApplication) -> None:
    """Auf der Startseite gehört der Katalog offen, das Einsetzen nicht.

    Vorher wählte jemand einen Baustein, bestätigte — und bekam erst dann
    „Wählen Sie zuerst ein Objekt": zwei Dialoge für eine Absage, die beim
    Öffnen feststand (Robert, 25.08.2026). Gesperrt wird das Einsetzen mit
    Grund an Knopf und Hinweiszeile; die Bibliothek ansehen bleibt möglich,
    und der Doppelklick hält sich an dieselbe Sperre wie der Knopf.
    """
    catalog = PartCatalog()
    try:
        grund = "Die Szene ist leer — ein Baustein wird auf einen Körper gesetzt."
        catalog.set_can_insert(False, grund)

        chosen_item = None
        for row in range(catalog.list.count()):
            item = catalog.list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) is not None:
                catalog.list.setCurrentItem(item)
                chosen_item = item
                break
        assert chosen_item is not None and catalog.chosen() is not None

        assert catalog._insert is not None
        assert not catalog._insert.isEnabled(), "mit Auswahl, aber ohne Körper: gesperrt"
        assert catalog.insert_hint.isVisibleTo(catalog), "der Grund steht sichtbar da"
        assert "Körper" in catalog.insert_hint.text()
        assert catalog._insert.toolTip() == grund, "zweite Kodierung am Knopf (Regel 18)"

        picked: list[str] = []
        catalog.partChosen.connect(picked.append)
        catalog._chosen(chosen_item)
        assert picked == [], "der Doppelklick setzt nichts, was der Knopf nicht darf"
        catalog._accept()
        assert picked == [], "und die Eingabetaste auch nicht"

        catalog.set_can_insert(True, "")
        assert catalog._insert.isEnabled(), "mit Körper geht alles wieder"
        assert not catalog.insert_hint.isVisibleTo(catalog)
        catalog._chosen(chosen_item)
        assert picked, "frei heißt: der Doppelklick wählt wieder"
    finally:
        catalog.release()


def test_a_part_that_needs_a_spot_says_so_before_the_click(qt_app: QApplication) -> None:
    """Vierundzwanzig der siebenundzwanzig Bausteine brauchen eine Stelle.

    Der Katalog fragte nur, ob ein **Körper** gewählt ist, und ließ dann
    einsetzen; die Absage kam als Fehler danach — „Für diesen Baustein fehlt
    die Stelle, an die er soll" (Robert, 29.08.2026, am Bildschirmfoto eines
    Quaders mit aufliegender Schraube). Derselbe Fall wie am 25.08., nur eine
    Ebene tiefer: dort fehlte der Körper, hier die Stelle an ihm.

    Und die Auskunft ist **kein Riegel**: Ein Baustein lässt sich auch über
    eine eingetragene Position setzen, so machen es die ausgelieferten
    Beispielprojekte. Gesperrt würde ihnen der Weg genommen.
    """
    catalog = PartCatalog()
    try:
        catalog.set_can_insert(True, "")
        catalog.set_feature_chosen(False)

        def waehle(name: str) -> bool:
            for row in range(catalog.list.count()):
                item = catalog.list.item(row)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == name:
                    catalog.list.setCurrentItem(item)
                    return True
            return False

        assert waehle("printed_screw"), "die Schraube steht im Katalog"
        assert catalog._insert is not None
        assert catalog._insert.isEnabled(), "kein Riegel — die Position bleibt ein Weg"
        assert catalog.insert_hint.isVisibleTo(catalog), "aber der Hinweis steht da"
        text = catalog.insert_hint.text()
        assert "Fläche" in text and "Bohrung" in text, "er nennt beide Stellen"
        assert "Position" in text, "und den zweiten Weg, den es gibt"

        assert waehle("wall_ladder"), "die Wandstärkenleiter steht im Katalog"
        assert not catalog.insert_hint.isVisibleTo(catalog), (
            "ein frei stehender Prüfkörper braucht keine Stelle — die Sperre gilt je Baustein"
        )

        catalog.set_feature_chosen(True)
        assert waehle("printed_screw")
        assert not catalog.insert_hint.isVisibleTo(catalog), (
            "mit gewählter Stelle ist nichts zu sagen"
        )
    finally:
        catalog.release()
