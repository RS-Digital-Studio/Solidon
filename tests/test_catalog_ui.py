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


# --- Was die Kachel zeigt, bevor ihr Bild da ist ------------------------------


def test_every_tile_has_a_face_from_the_first_moment(qt_app: QApplication) -> None:
    """Keine Kachel steht ohne Fläche da, auch nicht in der ersten Sekunde.

    **§2.6 begründet den Katalog gerade mit dem Bild** — ein räumliches Teil
    als Textzeile ist die schlechtere Darstellung. Gemessen am 30.08.2026 im
    echten Fenster: Nach einer halben Sekunde trug **eine** von 27 Kacheln ihr
    Rendering, nach zwei Sekunden alle. In dieser halben Sekunde sah der
    Katalog aus wie eine Liste.

    Der Platzhalter schließt die Lücke, ohne einen Balken zu setzen:
    ``wartezeit.md`` verlangt Fortschritt ab zwei Sekunden, die Kette bleibt
    darunter, und ein Balken für eine halbe Sekunde wäre Lärm.

    Geprüft wird **vor** jeder Ereignisrunde — also bevor die Renderkette
    überhaupt laufen konnte.
    """
    from app.ui.catalog import PartCatalog

    katalog = PartCatalog()
    try:
        liste = katalog.list
        kacheln = [
            liste.item(zeile)
            for zeile in range(liste.count())
            if liste.item(zeile) is not None and liste.item(zeile).data(Qt.ItemDataRole.UserRole)
        ]
        assert len(kacheln) >= 20, (
            f"nur {len(kacheln)} Bausteinkacheln gefunden — sucht das noch richtig?"
        )

        ohne = [
            kachel.text()
            for kachel in kacheln
            if kachel.icon().isNull() or not kachel.icon().availableSizes()
        ]
        assert not ohne, f"{len(ohne)} Kacheln ohne Fläche: {ohne[:3]}"

        # Und die Gegenrichtung: Der Platzhalter ist noch kein Rendering.
        assert not katalog._previews, (
            "vor der ersten Ereignisrunde darf kein Bild gerechnet sein — sonst "
            "misst dieser Test die fertige Kette statt den Anfangszustand"
        )
    finally:
        katalog.release()


def test_the_placeholder_is_drawn_once_and_reused(qt_app: QApplication) -> None:
    """Ein Platzhalter für alle Kacheln, nicht 27 gleiche Zeichnungen.

    Er ist für jede Kachel derselbe; ihn je Kachel zu zeichnen wäre 27-mal
    dasselbe Rechteck.
    """
    from app.ui.catalog import PartCatalog

    katalog = PartCatalog()
    try:
        erst = katalog._placeholder()
        zweit = katalog._placeholder()
        assert erst is zweit, "der Platzhalter wird einmal gebaut und wiederverwendet"
        assert not erst.isNull(), "und er ist kein leeres Bild"
    finally:
        katalog.release()


def test_a_rendered_preview_replaces_the_placeholder(qt_app: QApplication) -> None:
    """Sobald ein Bild da ist, zeigt die Kachel es — der Platzhalter tritt ab.

    Die Gegenprobe zum Platzhalter: Er darf die Renderkette nicht ersetzen,
    sondern nur überbrücken. Ohne diesen Test wäre eine Kachel, die dauerhaft
    den Platzhalter zeigt, von einer richtig gefüllten nicht zu unterscheiden.
    """
    from app.core.knowledge.parts import PARTS
    from app.ui.catalog import PartCatalog

    katalog = PartCatalog()
    try:
        erster = PARTS.all()[0]
        vorher = katalog._preview(erster)
        katalog._render_pending()
        nachher = katalog._preview(erster)

        assert erster.name in katalog._previews, "die Kette muss das erste Bild gerechnet haben"
        assert vorher.cacheKey() != nachher.cacheKey(), (
            "nach dem Rendern muss die Kachel ein anderes Bild tragen als den Platzhalter"
        )
    finally:
        katalog.release()


def test_part_file_export_stays_shut_and_says_why(qt_app: QApplication) -> None:
    """Der Datei-Export ist gesperrt, und er sagt jedes Mal, warum.

    **Gesperrt mit Grund, nicht versteckt.** Ein eingebauter Baustein kommt
    aus Python — es gibt keine Datei, die man weitergeben könnte. Der Knopf
    verschwindet trotzdem nicht: Wer ihn sucht, soll ihn finden und lesen,
    weshalb er gerade nicht kann. Ein grauer Knopf ohne Grund ist derselbe
    Fehler wie eine gesperrte Operation ohne Grund.

    **Der Grund steht an drei Stellen**, weil je nach Bedienung eine davon
    ausfällt: Tooltip für die Maus, ``statusTip`` für die Statuszeile ohne
    Wartezeit, ``accessibleDescription`` für den Bildschirmleser. Regel 18
    verlangt mehr als eine Kodierung, und ein grau gewordener Knopf ist genau
    eine.

    Zwei Lagen, zwei Sätze: ohne Auswahl fehlt der Baustein, mit einem
    eingebauten fehlt die Datei. Ein Satz für beides wäre in einem der Fälle
    unwahr.
    """
    catalog = PartCatalog()
    try:
        catalog.show()
        QApplication.processEvents()
        assert not catalog.share_part.isEnabled(), "ohne Auswahl gibt es keine Datei zu exportieren"
        leer = catalog.share_part.toolTip()
        assert leer, "der gesperrte Knopf sagt nicht, was fehlt"
        assert catalog.share_hint.isVisibleTo(catalog)
        assert catalog.share_hint.text() == leer
        assert catalog.share_part.statusTip() == leer, "die Statuszeile schweigt"
        assert catalog.share_part.accessibleDescription() == leer, (
            "der Bildschirmleser bekommt den Grund nicht"
        )

        # Ein eingebauter Baustein: gewählt, und trotzdem gesperrt — aber mit
        # einem **anderen** Grund als der leeren Auswahl.
        eingebaut = next(entry for entry in PARTS.all() if not getattr(entry, "own", False))
        for row in range(catalog.list.count()):
            item = catalog.list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == eingebaut.name:
                catalog.list.setCurrentItem(item)
                break
        else:  # pragma: no cover - der Katalog wäre dann leer
            raise AssertionError("kein eingebauter Baustein im Katalog")

        assert not catalog.share_part.isEnabled(), (
            f"{eingebaut.name} kommt aus Python und hat keine Datei zum Weitergeben"
        )
        gewaehlt = catalog.share_part.toolTip()
        assert gewaehlt and gewaehlt != leer, (
            "gewählt und nichts gewählt sind zwei Lagen und brauchen zwei Sätze"
        )
        assert catalog.share_hint.isVisibleTo(catalog)
        assert catalog.share_hint.text() == gewaehlt
    finally:
        catalog.release()
        catalog.deleteLater()


def test_a_file_result_is_visible_and_reveals_the_affected_part(
    qt_app: QApplication,
) -> None:
    """Das Ergebnis bleibt im Katalog und hebt einen zuvor weggefilterten Eintrag hervor."""
    catalog = PartCatalog()
    try:
        wanted = PARTS.all()[0].name
        catalog.search.setText("dieser Filter findet keinen Baustein")
        assert wanted not in catalog_names(catalog)

        catalog.show()
        undone: list[bool] = []
        shown: list[bool] = []
        catalog.undoFileRequested.connect(lambda: undone.append(True))
        catalog.showAffectedStepRequested.connect(lambda: shown.append(True))
        catalog.show_file_result(
            "Dateiweg abgeschlossen.",
            part_name=wanted,
            can_undo=True,
            can_show_affected_step=True,
        )
        QApplication.processEvents()

        assert catalog.search.text() == ""
        assert catalog.chosen() == wanted
        assert catalog.file_result.isVisibleTo(catalog)
        assert catalog.file_result.text() == "Dateiweg abgeschlossen."
        assert catalog.file_result.accessibleName() == "Dateiweg abgeschlossen."
        assert catalog.file_undo.isVisibleTo(catalog)
        assert catalog.file_undo.focusPolicy() != Qt.FocusPolicy.NoFocus
        assert catalog.file_undo.accessibleName() == "Rückgängig"
        assert catalog.show_affected_step.isVisibleTo(catalog)
        assert catalog.show_affected_step.focusPolicy() != Qt.FocusPolicy.NoFocus
        assert catalog.show_affected_step.accessibleName() == "Im Verlauf zeigen"
        catalog.file_undo.click()
        catalog.show_affected_step.click()
        assert undone == [True] and shown == [True]
    finally:
        catalog.release()
        catalog.close()


def test_local_part_file_way_runs_through_the_buttons(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Export, Import, Neustart und Re-Export laufen durch die Oberfläche.

    Der Dateidialog wird abgefangen, nicht umgangen. Alles davor und dahinter
    läuft echt: Katalogsignale, Fensterhandler, ``PartFileIO`` und die
    Herkunftszeile im Steckbrief. Der zweite Katalog entsteht nach dem erneuten
    Laden des Rezeptordners; damit prüft der Weg nicht bloß den Zustand, den
    ``install_file`` gerade im Speicher hinterlassen hat.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts import recipe as recipe_module
    from app.core.knowledge.parts.part_file import PART_FILE_SUFFIX, PartFileIO
    from app.core.knowledge.parts.recipe import register, save
    from app.core.registry import REGISTRY
    from app.ui.catalog import PartCatalog, detail
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    name = "probeklotz"
    operation_name = f"insert_{name}"
    storage = tmp_path / "user-parts"
    monkeypatch.setattr(recipe_module, "user_parts_dir", lambda: storage)

    part = _box_recipe(name)
    source = save(part)
    register(part)

    target = tmp_path / f"{name}{PART_FILE_SUFFIX}"
    forwarded = tmp_path / f"{name}-weitergegeben{PART_FILE_SUFFIX}"
    save_target = [target]
    catalogs: list[PartCatalog] = []
    calls = {"export": 0, "install": 0}
    worker_threads: list[bool] = []

    original_export = PartFileIO.export_to_file
    original_install = PartFileIO.install_file

    def counted_export(codec, chosen, destination):
        from PySide6.QtCore import QThread

        calls["export"] += 1
        worker_threads.append(QThread.currentThread() is not QApplication.instance().thread())
        return original_export(codec, chosen, destination)

    def counted_install(codec, payload, **kwargs):
        calls["install"] += 1
        from PySide6.QtCore import QThread

        worker_threads.append(QThread.currentThread() is not QApplication.instance().thread())
        return original_install(codec, payload, **kwargs)

    monkeypatch.setattr(PartFileIO, "export_to_file", counted_export)
    monkeypatch.setattr(PartFileIO, "install_file", counted_install)

    def instead_of_exec(dialog: PartCatalog) -> int:
        catalogs.append(dialog)
        return int(PartCatalog.DialogCode.Rejected)

    from app.ui import main_window as _mw

    troubles: list[object] = []
    monkeypatch.setattr(
        _mw,
        "show_error",
        lambda problem, parent=None, handlers=None: troubles.append(problem),
    )
    monkeypatch.setattr(PartCatalog, "exec", instead_of_exec)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(save_target[0]), "")),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "")),
    )
    window = MainWindow(Session(), UiSettings())
    restarted = None
    try:
        window.action_catalog()
        assert catalogs, "action_catalog hat keinen Katalog gebaut"
        catalog = catalogs[0]

        # Eingebaute Python-Bausteine haben keine exportierbare Bausteindatei.
        builtin = next(entry for entry in PARTS.all() if not entry.own)
        _choose(catalog, builtin.name)
        assert not catalog.share_part.isEnabled(), (
            f"{builtin.name} kommt aus Python und hat keine Datei zum Weitergeben"
        )
        assert catalog.share_part.toolTip(), "der gesperrte Knopf sagt nicht, warum"

        _choose(catalog, name)
        assert catalog.share_part.isEnabled(), "ein eigenes Rezept muss exportierbar sein"
        catalog.share_part.click()
        wait_until(target.is_file, "der Exportarbeiter schrieb die Bausteindatei nicht")
        assert not troubles, f"der Export meldete einen Fehler: {troubles}"
        assert target.is_file(), "der Klick hat keine Datei geschrieben"
        assert target.stat().st_size > 0, "die geschriebene Datei ist leer"

        # Der Import beginnt wie auf einem zweiten Rechner: kein Eintrag, keine
        # Operation und keine gleichnamige Datei im dortigen Rezeptordner.
        PARTS.remove(name)
        REGISTRY.remove(operation_name)
        source.unlink()
        catalog.adopt_part.click()
        wait_until(lambda: PARTS.has(name), "der Importarbeiter ergänzte den Katalog nicht")

        spec = next((entry for entry in PARTS.all() if entry.name == name), None)
        assert spec is not None, "nach dem Einlesen steht der Baustein nicht im Katalog"
        assert spec.source == recipe_module.IMPORTED_SOURCE
        assert "aus Datei hinzugefügt" in detail(spec)
        assert recipe_module.recipes_dir().joinpath(f"{name}.json").is_file()
        _choose(catalog, name)
        wait_until(
            catalog.share_part.isEnabled,
            "die Erfolgsrückmeldung gab den Weitergabe-Knopf nicht wieder frei",
        )
        assert catalog.share_part.isEnabled(), (
            "die geprüfte Dateiherkunft muss beim lokalen Weiterexport erhalten bleiben"
        )

        # Neustart: Nur die dauerhafte Datei bleibt. Katalog und Operation
        # werden daraus neu aufgebaut, anschließend geht derselbe Exportknopf.
        catalog.release()
        window.close()
        PARTS.remove(name)
        REGISTRY.remove(operation_name)
        loaded = recipe_module.load_all()
        assert loaded.loaded == (name,)
        assert not loaded.findings

        restarted = MainWindow(Session(), UiSettings())
        save_target[0] = forwarded
        restarted.action_catalog()
        after_restart = catalogs[-1]
        _choose(after_restart, name)
        spec_after_restart = PARTS.get(name)
        assert spec_after_restart.source == recipe_module.IMPORTED_SOURCE
        assert "aus Datei hinzugefügt" in detail(spec_after_restart)
        assert after_restart.share_part.isEnabled()
        after_restart.share_part.click()
        wait_until(forwarded.is_file, "der Re-Exportarbeiter schrieb die Datei nicht")

        assert not troubles, f"der Re-Export meldete einen Fehler: {troubles}"
        assert forwarded.is_file()
        forwarded_recipe = PartFileIO().validate(forwarded.read_bytes())
        assert forwarded_recipe.imported_origin is not None
        assert forwarded_recipe.author == "Probe"
        assert forwarded_recipe.license == "CC0-1.0"
        assert calls == {"export": 2, "install": 1}, (
            "der produktive Weg muss genau über export_to_file/install_file laufen"
        )
        assert worker_threads and all(worker_threads), (
            "Prüfung und Schreiben müssen vollständig außerhalb des Qt-Hauptthreads laufen"
        )
        after_restart.release()
    finally:
        PARTS.remove(name)
        REGISTRY.remove(operation_name)
        if restarted is not None:
            restarted.close()
        window.close()


def test_open_path_routes_a_part_file_through_the_catalog_worker(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Startargument, Finder und Ablage nutzen denselben geprüften Importweg."""
    from app.core.knowledge.parts import recipe as recipe_module
    from app.core.knowledge.parts.part_file import PART_FILE_SUFFIX, PartFileIO
    from app.core.registry import REGISTRY
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    name = "direkt_geoeffnet"
    incoming = tmp_path / f"{name}{PART_FILE_SUFFIX}"
    incoming.write_bytes(PartFileIO().export_file(_box_recipe(name)))
    monkeypatch.setattr(recipe_module, "user_parts_dir", lambda: tmp_path / "user-parts")
    catalogs: list[PartCatalog] = []

    def instead_of_exec(dialog: PartCatalog) -> int:
        catalogs.append(dialog)
        return int(PartCatalog.DialogCode.Rejected)

    monkeypatch.setattr(PartCatalog, "exec", instead_of_exec)
    window = MainWindow(Session(), UiSettings())
    try:
        window.open_path(incoming)
        wait_until(lambda: PARTS.has(name), "open_path erreichte den Importarbeiter nicht")

        assert len(catalogs) == 1
        catalog = catalogs[0]
        wait_until(catalog.file_result.isVisible, "das Importergebnis blieb unsichtbar")
        assert catalog.chosen() == name
        assert "Baustein hinzugefügt" in catalog.file_result.text()
        assert catalog.file_undo.isVisibleTo(catalog)
        stored = recipe_module.recipes_dir().joinpath(f"{name}.json")
        exact = stored.read_bytes()

        catalog.file_undo.click()
        wait_until(lambda: not PARTS.has(name), "Rückgängig entfernte den Import nicht")
        wait_until(
            lambda: window._part_file_worker is None,
            "der Entfernungsarbeiter wurde nicht abgebaut",
        )
        assert "Baustein entfernt" in catalog.file_result.text()
        assert catalog.file_undo.isVisibleTo(catalog)

        catalog.file_undo.click()
        wait_until(lambda: PARTS.has(name), "Rückgängig stellte den Import nicht wieder her")
        wait_until(
            lambda: window._part_file_worker is None,
            "der Wiederherstellungsarbeiter wurde nicht abgebaut",
        )
        assert stored.read_bytes() == exact, "der echte Kerntoken muss dieselben Bytes liefern"
        assert PARTS.get(name).source == recipe_module.IMPORTED_SOURCE
        assert catalog.remove_part.isVisibleTo(catalog), (
            "ein aus Datei hinzugefügter Baustein muss wieder entfernbar sein"
        )
        catalog.release()
    finally:
        PARTS.remove(name)
        REGISTRY.remove(f"insert_{name}")
        window.close()


def test_removing_a_used_local_part_is_immediate_exact_and_points_to_history(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Entfernen fragt nicht, nennt Verwendungen und stellt Datei sowie Vorschau wieder her."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QMessageBox

    from app.core.knowledge.parts import recipe as recipe_module
    from app.core.knowledge.parts.recipe import register, save
    from app.core.registry import REGISTRY
    from app.core.types import Operation, Transaction
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    name = "entfernungsprobe"
    storage = tmp_path / "user-parts"
    monkeypatch.setattr(recipe_module, "user_parts_dir", lambda: storage)
    part = _box_recipe(name)
    path = save(part)
    register(part)
    exact = path.read_bytes()
    catalogs: list[PartCatalog] = []

    def instead_of_exec(dialog: PartCatalog) -> int:
        catalogs.append(dialog)
        return int(PartCatalog.DialogCode.Rejected)

    monkeypatch.setattr(PartCatalog, "exec", instead_of_exec)
    window = MainWindow(Session(), UiSettings())
    document = window.session.project.document
    used_op = 91
    document.ops.append(
        Operation(
            id=used_op,
            op=f"insert_{name}",
            outputs=("obj_91",),
            params={},
        )
    )
    document.transactions.append(Transaction(id=9, title="Baustein einsetzen", ops=(used_op,)))
    window.history_panel.show_document(document)
    original_ops = tuple(document.ops)
    original_transactions = tuple(document.transactions)
    try:
        window.action_catalog()
        catalog = catalogs[-1]
        for spec in PARTS.all():
            catalog._previews[spec.name] = QPixmap(1, 1)
        _choose(catalog, name)
        catalog.show()
        QApplication.processEvents()

        assert catalog.remove_part.isVisibleTo(catalog)
        builtin = next(spec for spec in PARTS.all() if spec.source not in ("recipe", "imported"))
        _choose(catalog, builtin.name)
        assert catalog.remove_part.isHidden(), "eingebaute und mitgereiste Bausteine bleiben"
        _choose(catalog, name)

        monkeypatch.setattr(
            QMessageBox,
            "exec",
            lambda *_args, **_values: pytest.fail("Entfernen darf nicht nachfragen"),
        )
        catalog.remove_part.click()
        wait_until(lambda: not PARTS.has(name), "der lokale Baustein blieb im Register")
        wait_until(lambda: window._part_file_worker is None, "der Entfernungsworker blieb hängen")

        assert not path.exists()
        assert name not in catalog._previews, "eine entfernte Vorschau darf nicht im Cache bleiben"
        assert "Baustein entfernt" in catalog.file_result.text()
        assert "einem Schritt" in catalog.file_result.text()
        assert catalog.file_undo.isVisibleTo(catalog)
        assert catalog.show_affected_step.isVisibleTo(catalog)
        assert tuple(document.ops) == original_ops
        assert tuple(document.transactions) == original_transactions

        catalog.show_affected_step.click()
        current = window.history_panel.list.currentItem()
        assert current is not None
        assert current.data(Qt.ItemDataRole.UserRole) == used_op

        catalog.show()
        catalog.file_undo.click()
        wait_until(lambda: PARTS.has(name), "der echte Rücknahmetoken stellte nichts wieder her")
        wait_until(
            lambda: window._part_file_worker is None,
            "der Wiederherstellungsworker blieb hängen",
        )
        wait_until(lambda: name in catalog._previews, "die Vorschau wurde nicht neu aufgebaut")

        assert path.read_bytes() == exact
        assert tuple(document.ops) == original_ops
        assert tuple(document.transactions) == original_transactions
        assert "Baustein wiederhergestellt" in catalog.file_result.text()
        assert catalog.file_undo.isVisibleTo(catalog)
        assert catalog.chosen() == name
        assert catalog.remove_part.isVisibleTo(catalog)
        catalog.release()
    finally:
        PARTS.remove(name)
        REGISTRY.remove(f"insert_{name}")
        window.close()


def test_the_picker_keeps_historical_json_and_reads_it_in_the_worker(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Nur der Picker kennt Alt-JSON; selbst dessen Lesen blockiert den Qt-Thread nicht."""
    from pathlib import Path

    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QFileDialog

    from app.core.knowledge.parts import recipe as recipe_module
    from app.core.knowledge.parts.part_file import PartFileIO
    from app.core.registry import REGISTRY
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    name = "historische_json_probe"
    source = tmp_path / f"{name}.json"
    source.write_bytes(PartFileIO().export_file(_box_recipe(name)))
    monkeypatch.setattr(recipe_module, "user_parts_dir", lambda: tmp_path / "user-parts")
    offered: list[tuple[str, str]] = []
    read_off_main: list[bool] = []
    original_read = Path.read_bytes

    def choose(*args, **kwargs):
        offered.append((str(args[1]), str(args[3])))
        return str(source), ""

    def watched_read(path: Path) -> bytes:
        if path == source:
            application = QApplication.instance()
            assert application is not None
            read_off_main.append(QThread.currentThread() is not application.thread())
        return original_read(path)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(choose))
    monkeypatch.setattr(Path, "read_bytes", watched_read)
    monkeypatch.setattr(
        PartCatalog,
        "exec",
        lambda dialog: int(PartCatalog.DialogCode.Rejected),
    )
    window = MainWindow(Session(), UiSettings())
    try:
        window.action_adopt_part_file()
        wait_until(lambda: PARTS.has(name), "das historische JSON wurde nicht hinzugefügt")
        wait_until(lambda: window._part_file_worker is None, "der Importworker blieb hängen")

        assert offered
        title, file_filter = offered[0]
        assert title == "Baustein hinzufügen"
        assert "*.solidon-part" in file_filter and "*.json" in file_filter
        assert read_off_main == [True]
    finally:
        PARTS.remove(name)
        REGISTRY.remove(f"insert_{name}")
        window.close()


def test_the_application_path_rejects_an_unreferenced_executable_payload(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Auch der echte Importknopf lässt ein verstecktes ``plugin.py`` nicht durch."""
    import base64
    import hashlib
    import json

    from PySide6.QtWidgets import QFileDialog

    from app.core.errors import AppError
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts import recipe as recipe_module
    from app.core.knowledge.parts.part_file import PART_FILE_SUFFIX, PartFileIO
    from app.core.registry import REGISTRY
    from app.ui.catalog import PartCatalog
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    name = "payload_probe"
    operation_name = f"insert_{name}"
    storage = tmp_path / "user-parts"
    monkeypatch.setattr(recipe_module, "user_parts_dir", lambda: storage)

    data = json.loads(PartFileIO().export_file(_box_recipe(name)))
    source_id = "plugin_source"
    executable = b"import os\n"
    data["document"]["sources"] = {
        source_id: {
            "type": "import",
            "path": "sources/plugin.py",
            "sha256": hashlib.sha256(executable).hexdigest(),
            "embedded": True,
            "ingest": {},
        }
    }
    data["payloads"] = {source_id: base64.b64encode(executable).decode("ascii")}
    # Ein gewöhnliches Textfeld darf eine Quellenkennung erwähnen. Erreichbar
    # wird der Payload erst über ein als Quelle registriertes Parameterschema.
    data["document"]["ops"][0]["params"]["name"] = source_id
    malicious = tmp_path / f"fremder-baustein{PART_FILE_SUFFIX}"
    malicious.write_text(json.dumps(data), encoding="utf-8")

    catalogs: list[PartCatalog] = []
    troubles: list[AppError] = []
    calls = 0
    original_install = PartFileIO.install_file

    def counted_install(codec, payload, **kwargs):
        nonlocal calls
        calls += 1
        return original_install(codec, payload, **kwargs)

    def instead_of_exec(dialog: PartCatalog) -> int:
        catalogs.append(dialog)
        return int(PartCatalog.DialogCode.Rejected)

    from app.ui import main_window as _mw

    monkeypatch.setattr(PartFileIO, "install_file", counted_install)
    monkeypatch.setattr(
        _mw,
        "show_error",
        lambda problem, parent=None, handlers=None: troubles.append(problem),
    )
    monkeypatch.setattr(PartCatalog, "exec", instead_of_exec)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(malicious), "")),
    )

    window = MainWindow(Session(), UiSettings())
    try:
        window.action_catalog()
        catalog = catalogs[-1]
        catalog.adopt_part.click()
        wait_until(lambda: bool(troubles), "die abgelehnte Bausteindatei meldete sich nicht")

        assert calls == 1, "der Importknopf hat install_file umgangen"
        assert len(troubles) == 1
        problem = troubles[0]
        assert problem.suggestions, "die Ablehnung braucht einen nächsten Schritt"
        assert source_id not in str(problem.values), "fremde Kennungen bleiben intern"
        assert str(malicious) not in str(problem), "lokale Pfade gehören nicht in die Meldung"
        assert not PARTS.has(name)
        assert not REGISTRY.has(operation_name)
        assert not recipe_module.recipes_dir().joinpath(f"{name}.json").exists()
        catalog.release()
    finally:
        PARTS.remove(name)
        REGISTRY.remove(operation_name)
        window.close()


def test_a_name_collision_uses_the_free_name_from_the_error_action(
    qt_app: QApplication, tmp_path, monkeypatch
) -> None:
    """Der Hauptknopf der Kollision wiederholt exakt dieselben Bytes mit Namen."""
    from PySide6.QtWidgets import QFileDialog

    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts import recipe as recipe_module
    from app.core.knowledge.parts.part_file import PART_FILE_SUFFIX, PartFileIO
    from app.core.knowledge.parts.recipe import register, save
    from app.core.registry import REGISTRY
    from app.ui.catalog import PartCatalog
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    name = "kollisionsprobe"
    operation_name = f"insert_{name}"
    storage = tmp_path / "user-parts"
    monkeypatch.setattr(recipe_module, "user_parts_dir", lambda: storage)
    existing = _box_recipe(name)
    source = save(existing)
    register(existing)
    incoming = tmp_path / f"eingang{PART_FILE_SUFFIX}"
    incoming.write_bytes(PartFileIO().export_file(existing))

    catalogs: list[PartCatalog] = []
    attempted_names: list[str | None] = []
    original_install = PartFileIO.install_file

    def counted_install(codec, payload, **kwargs):
        attempted_names.append(kwargs.get("name"))
        return original_install(codec, payload, **kwargs)

    def instead_of_exec(dialog: PartCatalog) -> int:
        catalogs.append(dialog)
        return int(PartCatalog.DialogCode.Rejected)

    from app.ui import main_window as _mw

    chosen_actions: list[str] = []

    def choose_suggestion(problem, parent=None, handlers=None):
        ids = {action.id for action in problem.suggestions}
        if "use_suggested_name" in ids:
            assert handlers is not None
            chosen_actions.append("use_suggested_name")
            handlers["use_suggested_name"](problem)

    monkeypatch.setattr(PartFileIO, "install_file", counted_install)
    monkeypatch.setattr(_mw, "show_error", choose_suggestion)
    monkeypatch.setattr(PartCatalog, "exec", instead_of_exec)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(incoming), "")),
    )

    window = MainWindow(Session(), UiSettings())
    suggested = ""
    try:
        window.action_catalog()
        catalog = catalogs[-1]
        catalog.adopt_part.click()
        wait_until(lambda: len(attempted_names) == 2, "der freie Name wurde nicht erneut versucht")
        suggested = next((entry for entry in attempted_names if entry), "") or ""
        wait_until(lambda: bool(suggested) and PARTS.has(suggested), "der freie Name kam nicht an")

        assert attempted_names == [None, suggested]
        assert chosen_actions == ["use_suggested_name"]
        assert suggested != name
        assert source.read_bytes(), "der vorhandene Baustein darf nicht ersetzt werden"
        catalog.release()
    finally:
        for part_name in filter(None, (name, suggested)):
            PARTS.remove(part_name)
            REGISTRY.remove(f"insert_{part_name}")
        REGISTRY.remove(operation_name)
        window.close()


@pytest.mark.parametrize("first_kind", ["invalid", "unreadable"])
def test_an_unusable_part_file_action_opens_the_picker_again(
    qt_app: QApplication, tmp_path, monkeypatch, first_kind: str
) -> None:
    """Formatfehler und Lesefehler führen mit „Auswählen“ zurück zur Datei."""
    from PySide6.QtWidgets import QFileDialog

    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts import recipe as recipe_module
    from app.core.knowledge.parts.part_file import PART_FILE_SUFFIX, PartFileIO
    from app.core.registry import REGISTRY
    from app.ui.catalog import PartCatalog
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    name = f"auswahlprobe_{first_kind}"
    storage = tmp_path / "user-parts"
    monkeypatch.setattr(recipe_module, "user_parts_dir", lambda: storage)
    invalid = tmp_path / f"ungueltig{PART_FILE_SUFFIX}"
    if first_kind == "invalid":
        invalid.write_bytes(b"kein json")
    valid = tmp_path / f"gueltig{PART_FILE_SUFFIX}"
    valid.write_bytes(PartFileIO().export_file(_box_recipe(name)))
    choices = iter((str(invalid), str(valid)))
    picker_calls = 0
    catalogs: list[PartCatalog] = []

    def choose_file(*args, **kwargs):
        nonlocal picker_calls
        picker_calls += 1
        return next(choices), ""

    def instead_of_exec(dialog: PartCatalog) -> int:
        catalogs.append(dialog)
        return int(PartCatalog.DialogCode.Rejected)

    from app.ui import main_window as _mw

    def choose_again(problem, parent=None, handlers=None):
        assert "choose" in {action.id for action in problem.suggestions}
        assert handlers is not None
        handlers["choose"](problem)

    monkeypatch.setattr(_mw, "show_error", choose_again)
    monkeypatch.setattr(PartCatalog, "exec", instead_of_exec)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(choose_file))

    window = MainWindow(Session(), UiSettings())
    try:
        window.action_catalog()
        catalog = catalogs[-1]
        catalog.adopt_part.click()
        wait_until(lambda: PARTS.has(name), "die zweite, gültige Datei wurde nicht hinzugefügt")

        assert picker_calls == 2
        catalog.release()
    finally:
        PARTS.remove(name)
        REGISTRY.remove(f"insert_{name}")
        window.close()


@pytest.mark.parametrize("action_id", ["retry", "save_elsewhere"])
def test_a_part_export_write_error_performs_the_chosen_action(
    qt_app: QApplication, tmp_path, monkeypatch, action_id: str
) -> None:
    """Erneut nutzt denselben Pfad; anderer Ort öffnet den Speicherdialog neu."""
    from PySide6.QtWidgets import QFileDialog

    from app.core.errors import FileWriteError
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts import recipe as recipe_module
    from app.core.knowledge.parts.part_file import PART_FILE_SUFFIX, PartFileIO
    from app.core.knowledge.parts.recipe import register, save
    from app.core.registry import REGISTRY
    from app.i18n import tr
    from app.ui.catalog import PartCatalog
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    name = f"schreibprobe_{action_id}"
    storage = tmp_path / "user-parts"
    monkeypatch.setattr(recipe_module, "user_parts_dir", lambda: storage)
    part = _box_recipe(name)
    source = save(part)
    register(part)
    first = tmp_path / f"erster-ort{PART_FILE_SUFFIX}"
    second = tmp_path / f"anderer-ort{PART_FILE_SUFFIX}"
    offered_targets = iter((str(first), str(second)))
    picker_calls = 0
    written_targets: list[object] = []
    catalogs: list[PartCatalog] = []
    original_export = PartFileIO.export_to_file

    def choose_target(*args, **kwargs):
        nonlocal picker_calls
        picker_calls += 1
        return next(offered_targets), ""

    def fail_once(codec, recipe, target):
        written_targets.append(target)
        if len(written_targets) == 1:
            raise FileWriteError(
                target=getattr(target, "name", "part.json"),
                detail=tr("Die Datei ließ sich nicht schreiben."),
            )
        return original_export(codec, recipe, target)

    def instead_of_exec(dialog: PartCatalog) -> int:
        catalogs.append(dialog)
        return int(PartCatalog.DialogCode.Rejected)

    window: MainWindow

    def choose_recovery(problem, parent=None, handlers=None):
        available = window.error_handlers()
        assert action_id in available
        available[action_id](problem)

    from app.ui import main_window as _mw

    monkeypatch.setattr(PartFileIO, "export_to_file", fail_once)
    monkeypatch.setattr(_mw, "show_error", choose_recovery)
    monkeypatch.setattr(PartCatalog, "exec", instead_of_exec)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(choose_target))

    window = MainWindow(Session(), UiSettings())
    try:
        window.action_catalog()
        catalog = catalogs[-1]
        _choose(catalog, name)
        catalog.share_part.click()
        expected = first if action_id == "retry" else second
        wait_until(expected.is_file, "die gewählte Schreibhandlung führte nicht zum Ziel")

        assert written_targets == ([first, first] if action_id == "retry" else [first, second])
        assert picker_calls == (1 if action_id == "retry" else 2)
        catalog.release()
    finally:
        PARTS.remove(name)
        REGISTRY.remove(f"insert_{name}")
        if source.exists():
            source.unlink()
        window.close()


def _choose(catalog, name: str) -> None:
    """Eine Kachel auswählen, wie ein Klick es täte."""
    for row in range(catalog.list.count()):
        item = catalog.list.item(row)
        if item is not None and item.data(Qt.ItemDataRole.UserRole) == name:
            catalog.list.setCurrentItem(item)
            return
    raise AssertionError(f"{name} steht nicht im Katalog")


def _box_recipe(name: str):
    """Ein kleines, vollständig registrierbares Rezept für den UI-Dateiweg."""
    from app.core.knowledge.parts.recipe import Recipe
    from app.core.scene.migrations import FORMAT_VERSION
    from app.core.types import Document, Operation

    return Recipe(
        name=name,
        title="Probeklotz",
        group="structure",
        document=Document(
            format_version=FORMAT_VERSION,
            app_version="test",
            ops=[
                Operation(
                    id=1,
                    op="create_box",
                    outputs=("obj_1",),
                    params={
                        "width": 40.0,
                        "depth": 30.0,
                        "height": 12.0,
                        "anchor": "corner",
                        "name": "",
                    },
                )
            ],
        ),
        license="CC0-1.0",
        author="Probe",
        features={"top": "face_top"},
    )


def test_an_own_python_part_is_told_apart_from_a_shipped_one(qt_app: QApplication) -> None:
    """§24.5 heißt „Eigene Bausteine" und meint die ``.py`` aus dem Nutzerordner.

    Genau die fielen durch. ``_range_warning`` zählte ``recipe``, ``travelled``
    und ``imported`` auf — die drei Quellen, die später dazukamen — und ließ
    ``user`` aus. Gemessen: Ein Baustein mit ``source="user"`` bekam unter
    keinem Wert von ``range_passed`` einen Hinweis, auch nicht bei ``False``.

    Für den Kunden hieß das: Er legt eine eigene ``.py`` in seinen Ordner, sie
    steht im Katalog wie ein mitgelieferter Baustein, und dass ihr Bereich nie
    gefahren wurde, erfährt er nicht. Der Bauplan verspricht ihm das Gegenteil.
    """
    import dataclasses

    from app.i18n import tr
    from app.ui.catalog import RANGE_MARKER, describe, detail

    donor = next(iter(PARTS.all()))
    ungeprueft = dataclasses.replace(donor, source="user", range_passed=None)
    gebrochen = dataclasses.replace(donor, source="user", range_passed=False)
    bestanden = dataclasses.replace(donor, source="user", range_passed=True)

    assert tr("der Bereichstest ist für diesen Baustein nie gelaufen") in describe(ungeprueft)
    assert tr("an den Grenzen kam kein brauchbarer Körper heraus") in describe(gebrochen)
    assert RANGE_MARKER in detail(gebrochen), "Regel 18: Zeichen und Satz"
    assert "Bereichstest" not in describe(bestanden) and "Grenzen" not in describe(bestanden)

    # Und die Gegenprobe bleibt: Der mitgelieferte trägt dasselbe ``None`` und
    # wird nicht angeschrieben, denn seinen Bereich fährt die Suite.
    ausgeliefert = dataclasses.replace(donor, source="shipped", range_passed=None)
    assert "Bereichstest" not in describe(ausgeliefert)


def test_a_new_source_inherits_the_warning_instead_of_losing_it(qt_app: QApplication) -> None:
    """Die Bedingung nennt die Ausnahme, nicht die Fälle.

    Das ist der Grund, aus dem ``user`` überhaupt durchfallen konnte: Eine
    Aufzählung der betroffenen Quellen altert mit jeder neuen. Wer morgen eine
    fünfte einführt, soll den Hinweis erben und ihn nicht stillschweigend
    verlieren — der Fehler wäre wieder unsichtbar, weil nichts rot wird.
    """
    import dataclasses

    from app.ui.catalog import _range_warning

    donor = next(iter(PARTS.all()))
    erfunden = dataclasses.replace(donor, source="von_wo_auch_immer", range_passed=None)

    assert _range_warning(erfunden), "eine unbekannte Herkunft gilt als ungeprüft"
