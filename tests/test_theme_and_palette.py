"""Themenkontrast und die Befehlspalette (Bauplan §19.2, §19.3)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from app.core.registry import REGISTRY
from app.ui.command_palette import CommandPalette, matches
from app.ui.theme import THEMES, contrast_ratio, viewport_colours

#: WCAG AA for body text.
MINIMUM_CONTRAST = 4.5


@pytest.mark.parametrize("theme", list(THEMES))
def test_text_has_enough_contrast_in_both_themes(theme: str) -> None:
    """§19.3: ausreichender Kontrast im hellen und im dunklen Thema."""
    colours = THEMES[theme]  # type: ignore[index]
    assert contrast_ratio(colours["text"], colours["window"]) >= MINIMUM_CONTRAST
    assert contrast_ratio(colours["text"], colours["base"]) >= MINIMUM_CONTRAST
    assert contrast_ratio(colours["highlight_text"], colours["highlight"]) >= 3.0


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_severity_reads_on_the_surface_it_is_written_on(theme: str) -> None:
    """Der Prüfbericht schreibt jede Zeile in der Farbe ihres Schweregrads.

    Die Rollenfarben sind für den dunklen Untergrund gewählt, auf dem die
    Anwendung startet. Auf der weißen Liste des hellen Themas brachten sie
    2,22 (Warnung), 2,67 (Hinweis) und 3,97 (Fehler) — die zentrale Ansicht der
    Anwendung stand vollständig unter der Lesbarkeitsgrenze. Geprüft hat das
    niemand: die Kontrasttests hier kannten nur die Themenfarben, und die
    Rollenfarben lagen daneben in einer eigenen Datei.
    """
    from app.ui.palette import text_colour

    surface = THEMES[theme]["base"]  # type: ignore[index]
    for role in ("info", "warning", "error"):
        ratio = contrast_ratio(text_colour(role, surface), surface)  # type: ignore[arg-type]
        assert ratio >= MINIMUM_CONTRAST, (
            f"{role} bringt auf {surface} nur {ratio:.2f} — ein Befund, den man nicht liest."
        )


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_focus_ring_is_visible_on_its_own_background(theme: str) -> None:
    """Wer ohne Maus arbeitet, sieht nur den Fokusring.

    Er nahm ``highlight``, und der Bernstein bringt gegen das helle Fenster
    1,70 und gegen ein weißes Feld 2,06. WCAG 1.4.11 verlangt 3,0 für die
    Umrandung eines Bedienelements — im hellen Thema war der Ring praktisch
    nicht da. Er nimmt jetzt ``accent_line``, die für genau diese Rechnung
    schon je Thema abgestuft war.
    """
    colours = THEMES[theme]  # type: ignore[index]
    for surface in ("base", "window"):
        ratio = contrast_ratio(colours["accent_line"], colours[surface])
        assert ratio >= 3.0, f"Fokusring auf {surface}: {ratio:.2f}"


@pytest.mark.parametrize("theme", list(THEMES))
def test_quiet_text_stays_readable_and_locked_text_looks_locked(theme: str) -> None:
    """Zwei Aufgaben, zwei Farben.

    ``disabled`` versorgte beide: den Sperrzustand *und* jeden Nebentext —
    Maße, Einheiten, Spaltenköpfe, Gruppentitel, den stillen Reiter. Damit war
    beides falsch. Ein Fünftel aller Beschriftungen kam im hellen Thema auf
    2,59 Kontrast, und ein gesperrter Knopf unterschied sich farblich nicht von
    einem Spaltenkopf, der nie bedienbar war.
    """
    colours = THEMES[theme]  # type: ignore[index]
    for surface in ("window", "base"):
        quiet = contrast_ratio(colours["muted"], colours[surface])
        assert quiet >= MINIMUM_CONTRAST, (
            f"Nebentext auf {surface}: {quiet:.2f} — leise heißt nicht unlesbar."
        )

    assert colours["muted"] != colours["disabled"], (
        "Eine Farbe für zwei Aussagen ist für beide die falsche."
    )
    assert (
        contrast_ratio(colours["text"], colours["window"])
        > contrast_ratio(colours["muted"], colours["window"])
        > contrast_ratio(colours["disabled"], colours["window"])
    ), (
        "Die Reihenfolge muss stimmen: Haupttext lauter als Nebentext, Nebentext lauter "
        "als Gesperrtes."
    )


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_locked_control_looks_locked_in_every_role(theme: str) -> None:
    """Gesperrt ist ein Zustand, den man sehen muss.

    Die Palette setzte ihn für ``Text`` und ``ButtonText`` — nicht für
    ``WindowText``. Daran hängen genau die Elemente, die das Stylesheet nicht
    anfasst: QLabel, QCheckBox, QRadioButton, QGroupBox. Ein gesperrtes
    Ankreuzfeld war pixelgleich mit einem bedienbaren; „Scheibe" in der
    Schnittleiste und „Projektdatei anhängen" im Fehlerbericht sahen
    anklickbar aus und waren es nicht.
    """
    from PySide6.QtGui import QPalette

    from app.ui.theme import build_palette

    palette = build_palette(theme)  # type: ignore[arg-type]
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        locked = palette.color(QPalette.ColorGroup.Disabled, role).name()
        usable = palette.color(QPalette.ColorGroup.Active, role).name()
        assert locked != usable, f"{role.name}: gesperrt sieht aus wie bedienbar"


def test_the_palette_leaves_no_role_to_the_system() -> None:
    """Was hier nicht gesetzt wird, kommt vom Betriebssystem.

    ``PlaceholderText`` stand als einzige Rolle nicht in der Palette. Auf einem
    Rechner mit dunkel eingestelltem Windows war er hell — und im hellen Thema
    damit weiß auf Weiß. Dreizehn Felder tragen ihre Auskunft dort: das
    Suchfeld des Prüfberichts stand leer da, der Chat fragte nichts mehr, und
    im Schlüsseldialog fehlte das Muster, das als Einziges sagt, wie ein
    Lizenzschlüssel aussieht.
    """
    from PySide6.QtGui import QPalette

    from app.ui.theme import build_palette

    for theme in THEMES:
        palette = build_palette(theme)  # type: ignore[arg-type]
        placeholder = palette.color(QPalette.ColorRole.PlaceholderText).name()
        base = THEMES[theme]["base"]  # type: ignore[index]
        assert contrast_ratio(placeholder, base) >= 3.0, (
            f"{theme}: Platzhalter {placeholder} auf {base} — man sieht ihn nicht."
        )


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_border_is_actually_visible(theme: str) -> None:
    """Ein Knopf ohne sichtbaren Rahmen ist kein Knopf, sondern Text.

    ``line`` trägt keine Schrift und muss deshalb nicht AA erfüllen — sie muss
    zu sehen sein. Der erste Anlauf nahm dafür ``alternate``, die Farbe der
    Zebrazeile: im dunklen Thema 1,05 gegen das Fenster, also nichts. Im Bild
    fiel genau das auf, und es fällt nur im Bild auf.
    """
    colours = THEMES[theme]  # type: ignore[index]
    assert contrast_ratio(colours["line"], colours["window"]) >= 1.9
    assert contrast_ratio(colours["line"], colours["base"]) >= 1.9


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_drawing_grid_is_visible_without_shouting(theme: str) -> None:
    """Das Raster der Zeichenfläche wurde gezeichnet und war unsichtbar.

    ``sketch_editor._paint_grid`` nahm ``palette.mid()`` mit Alpha 60 und 140 —
    eine Rolle, die diese Tabelle nie gesetzt hat. Angekommen ist Qts Vorgabe
    ``#282828``, in beiden Themen dieselbe, und gemischt waren das **1,02** und
    **1,05** Kontrast gegen die dunkle Zeichenfläche. Gefangen wird darauf
    trotzdem: „Am Raster fangen" steht auf an, mit einem Millimeter Weite.

    Im hellen Thema war es der umgekehrte Fehler: 3,55 für die Hauptlinie, mehr
    als die Trennlinienfarbe des Themas selbst mitbringt.

    Geprüft wird deshalb nach oben **und** nach unten. Die Spanne ist weit genug
    für die Asymmetrie zwischen den Themen — dunkel steht auf 1,60 und 2,59,
    hell auf 1,35 und 2,0, weil derselbe Kontrastwert auf dunklem Grund
    schwächer liest — und eng genug, dass ein Griff in die Tabelle hier
    auffällt und nicht erst im Bild.
    """
    colours = THEMES[theme]  # type: ignore[index]
    minor = contrast_ratio(colours["grid_minor"], colours["base"])
    major = contrast_ratio(colours["grid_major"], colours["base"])
    assert 1.3 <= minor <= 1.8, f"{theme}: Nebenlinie {minor:.2f} — unsichtbar oder zu laut"
    assert 1.9 <= major <= 2.8, f"{theme}: Hauptlinie {major:.2f} — unsichtbar oder zu laut"
    assert major > minor, "jede fünfte Linie soll kräftiger sein, nicht schwächer"


def test_the_grid_reaches_the_canvas_through_the_palette() -> None:
    """Und die Zeichenfläche muss die Farben auch bekommen.

    Sie liest sie über ``Midlight`` und ``Mid``, nicht über eine eigene
    Konstante — sonst zieht ein Themenwechsel sie nicht mit. Genau dieser Weg
    war unterbrochen: die Rollen standen nicht in der Palette, und was nicht
    gesetzt ist, kommt vom Betriebssystem.
    """
    from PySide6.QtGui import QPalette

    from app.ui.theme import build_palette

    for theme in THEMES:
        palette = build_palette(theme)  # type: ignore[arg-type]
        colours = THEMES[theme]  # type: ignore[index]
        assert palette.color(QPalette.ColorRole.Midlight).name() == colours["grid_minor"]
        assert palette.color(QPalette.ColorRole.Mid).name() == colours["grid_major"]


@pytest.mark.parametrize("theme", list(THEMES))
def test_a_locked_surface_loses_the_accent_too(theme: str) -> None:
    """Gesperrt ist ein Zustand, den man sehen muss — auch an einer Fläche.

    Für die Schriftrollen stand das schon; ``Highlight`` fehlte. Fusion
    zeichnet damit die Rille des Reglers und den Fortschrittsbalken, und beide
    trugen gesperrt denselben vollen Bernstein: an einem Regler und einem
    Balken je zweimal gerendert und die Punkte gezählt — **2638 bedienbar,
    2638 gesperrt**, pixelgleich, in beiden Themen. Der Schnittregler ohne
    gewählte Achse sah dadurch bedienbar aus, obwohl ``SectionBar`` ihn
    abschaltet.
    """
    from PySide6.QtGui import QPalette

    from app.ui.theme import build_palette

    palette = build_palette(theme)  # type: ignore[arg-type]
    locked = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight).name()
    usable = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight).name()
    assert locked != usable, "eine gesperrte Fläche trägt den Akzent weiter"
    colours = THEMES[theme]  # type: ignore[index]
    assert contrast_ratio(locked, colours["window"]) >= 1.5, (
        "gesperrt heißt leiser, nicht unsichtbar"
    )


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_surfaces_stand_apart(theme: str) -> None:
    """Sieben Flächenrollen lagen in einem Helligkeitsband von 3,7 Punkten.

    Panel gegen Fenster 1,10, Zebrazeile gegen Panel 1,16, der Viewport-Verlauf
    1,21 — nichts trat vor oder zurück, und wer keine Auswahl getroffen hatte,
    sah ein einfarbiges Fenster. Die Schwellen unten halten den Abstand fest,
    damit er nicht Farbe für Farbe zurückrutscht.

    Sie sind je Thema verschieden, und das ist keine Nachlässigkeit: Was dunkel
    für Tiefe sorgt, macht hell aus dem Weiß ein schmutziges Grau.
    """
    colours = THEMES[theme]  # type: ignore[index]
    panel = 1.4 if theme == "dark" else 1.18
    zebra = 1.25 if theme == "dark" else 1.15
    assert contrast_ratio(colours["base"], colours["window"]) >= panel, (
        "das Panel muss sich vom Fenster lösen"
    )
    assert contrast_ratio(colours["alternate"], colours["base"]) >= zebra, (
        "die Zebrazeile muss eine sein"
    )


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_accent_line_carries_on_its_own_window(theme: str) -> None:
    """Die Kante des aktiven Reiters ist der einzige Ort, an dem der Akzent
    einen *bleibenden* Zustand zeigt. Sie muss auf beiden Untergründen tragen —
    der Bernstein selbst bringt gegen das helle Fenster nur 1,37.
    """
    colours = THEMES[theme]  # type: ignore[index]
    assert contrast_ratio(colours["accent_line"], colours["window"]) >= 3.0


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_viewport_follows_the_theme(theme: str) -> None:
    colours = viewport_colours(theme)  # type: ignore[arg-type]
    assert set(colours) == {"bottom", "top", "object", "bed", "bed_surface", "edge"}
    assert contrast_ratio(colours["object"], colours["bottom"]) >= 1.8, "a body stands out"
    # Der gefüllte Grund der Platte liegt zwischen Hintergrund und Raster: hebt
    # er sich von keinem der beiden ab, ist entweder die Platte unsichtbar oder
    # ihr Raster darauf.
    assert contrast_ratio(colours["bed"], colours["bed_surface"]) >= 1.4, (
        "das Raster muss auf seinem Grund zu sehen sein"
    )
    assert contrast_ratio(colours["bed_surface"], colours["bottom"]) >= 1.1, (
        "und der Grund gegen den Hintergrund"
    )
    # Eine Körperkante, die man suchen muss, hilft niemandem — dieselbe
    # Schwelle, die WCAG für lesbaren Text nennt, und aus demselben Grund.
    assert contrast_ratio(colours["edge"], colours["object"]) >= 4.0, (
        "die Kante muss sich vom Körper abheben"
    )


def test_the_two_themes_are_actually_different() -> None:
    assert THEMES["dark"]["window"] != THEMES["light"]["window"]
    assert contrast_ratio(THEMES["dark"]["window"], THEMES["light"]["window"]) > 5.0


def test_contrast_ratio_matches_the_known_extremes() -> None:
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#123456", "#123456") == pytest.approx(1.0)


# --- command palette ------------------------------------------------------------


def test_the_search_finds_by_title_name_and_documentation() -> None:
    entry = next(entry for entry in _palette_entries() if entry.name == "rename_object")
    assert matches(entry, "")
    assert matches(entry, "umbenennen")
    assert matches(entry, "rename")
    assert matches(entry, "objekt umbenennen")
    assert not matches(entry, "bohrung")


def test_the_palette_lists_every_operation(qt_app: object) -> None:
    palette = CommandPalette()
    listed = {
        palette.list.item(index).data(0x0100)  # Qt.ItemDataRole.UserRole
        for index in range(palette.list.count())
    }
    assert listed == {spec.name for spec in REGISTRY.all()}


def test_the_palette_opens_big_enough_to_be_a_list(qt_app: object) -> None:
    """Sieben Zeilen von hundertfünfundvierzig sind keine Liste.

    Gesetzt war nur die Breite; ohne Höhe nimmt das Layout seine kleinste, und
    das waren 248 Bildpunkte. Die Palette ist der Weg, auf dem **alles**
    erreichbar sein soll (§19.2) — so war sie eine Suchmaske, in der man tippen
    muss, statt einer Liste, in der man blättern kann.

    Geprüft an der Mindesthöhe und nicht an der Zeilenzahl: wie viele Zeilen
    hineinpassen, hängt an der Systemschriftgröße, und die gehört dem Nutzer.
    """
    palette = CommandPalette()

    assert palette.minimumHeight() >= 400, (
        f"die Palette öffnet {palette.minimumHeight()} Punkte hoch — zu wenig zum Blättern"
    )
    assert palette.list.count() >= len(REGISTRY.all()), "und sie hat wirklich etwas zu zeigen"


def test_the_palette_shows_the_shortcut_so_it_gets_learned(qt_app: object) -> None:
    """§2.6: das Kürzel steht neben dem Eintrag — so lernt es sich."""
    palette = CommandPalette()
    labels = [palette.list.item(index).text() for index in range(palette.list.count())]
    assert any("F2" in label for label in labels), "rename_object carries F2"


def test_typing_narrows_the_list_and_picks_the_first(qt_app: object) -> None:
    palette = CommandPalette()
    palette.search.setText("duplizieren")

    assert palette.list.count() == 1
    assert palette.chosen() == "duplicate_object"


def test_a_search_without_hits_says_so_and_chooses_nothing(qt_app: object) -> None:
    """Eine leere Liste sagt nicht, ob nichts passt oder ob die Suche hängt.

    Die Zeile, die es jetzt sagt, ist ausdrücklich nicht wählbar und trägt
    keine Daten — sonst löste die Eingabetaste einen Befehl aus, den es nicht
    gibt. Geprüft wird deshalb beides: dass etwas dasteht, und dass ``chosen``
    weiter ``None`` liefert.
    """
    from PySide6.QtCore import Qt

    palette = CommandPalette()
    palette.search.setText("gibtsnicht")

    assert palette.list.count() == 1, "kein Wort darüber, dass nichts passt"
    zeile = palette.list.item(0)
    assert "gibtsnicht" in zeile.text(), "der Satz nennt den Suchbegriff nicht"
    assert not zeile.flags() & Qt.ItemFlag.ItemIsSelectable
    assert palette.chosen() is None


def _palette_entries():
    from app.core.registry import palette_entries

    return list(palette_entries())


def test_the_search_finds_words_typed_without_umlauts(qt_app: object) -> None:
    """Nicht jede Tastatur hat Umlaute, und nicht jeder tippt sie.

    „aushoehlen" fand **null** Einträge, obwohl die Operation „Aushöhlen"
    heißt; dasselbe galt für „groesse". Gefaltet wird auf beiden Seiten — wer
    „Aushöhlen" mit Umlaut tippt, soll ihn genauso finden.
    """
    from app.ui.command_palette import CommandPalette

    palette = CommandPalette()
    for typed in ("aushoehlen", "aushöhlen", "AUSHOEHLEN"):
        palette.search.setText(typed)
        titles = [palette.list.item(row).text() for row in range(palette.list.count())]
        assert titles, f"{typed!r} findet nichts"
        assert "Aushöhlen" in titles[0], f"{typed!r} zeigt zuerst {titles[0]!r}"


def test_the_search_falls_back_to_the_word_stem(qt_app: object) -> None:
    """„bohren" fand nichts, weil die Operation „Bohrung setzen" heißt.

    Ein Fall, den keine Synonymtabelle je vollständig abdeckt — und den die
    ersten vier Buchstaben lösen. Gelockert wird **erst**, wenn die genaue
    Suche leer ausgeht: Sonst stünde zwischen guten Treffern immer auch
    Ungefähres.
    """
    from app.ui.command_palette import CommandPalette, matches

    palette = CommandPalette()
    palette.search.setText("bohren")
    titles = [palette.list.item(row).text() for row in range(palette.list.count())]

    assert titles, "die Suche nach bohren findet nichts"
    assert "Bohrung" in titles[0], f"zuerst steht {titles[0]!r} statt der Bohrung"

    # Und die Lockerung greift wirklich nur als zweite Runde.
    treffer = [entry for entry in palette._entries if matches(entry, "bohren")]
    assert not treffer, "bohren passt neuerdings genau — dann prueft dieser Test nichts"


def test_a_hit_in_the_title_beats_a_hit_in_the_description(qt_app: object) -> None:
    """Wer tippt, meint fast immer den Namen.

    Ohne Ordnung stand bei „bohren" das „An Merkmal ausrichten" vorn, weil
    dessen Beschreibung das Wort Bohrung enthält, und „Bohrung setzen" auf
    Platz drei. Sortiert wird stabil, damit die Reihenfolge aus ``applies_to``
    innerhalb derselben Güte stehen bleibt.
    """
    from app.ui.command_palette import CommandPalette, rank

    palette = CommandPalette()
    palette.search.setText("bohrung")
    titles = [palette.list.item(row).text() for row in range(palette.list.count())]

    assert len(titles) > 1, "zu wenige Treffer, um eine Reihenfolge zu pruefen"
    assert "Bohrung" in titles[0], f"zuerst steht {titles[0]!r}"

    # Und die Ordnung dahinter, damit ein Umbau der Anzeige sie nicht still
    # verliert: Titel schlaegt Beschreibung.
    im_titel = next(e for e in palette._entries if "Bohrung" in str(e.title))
    nur_im_text = next(
        e
        for e in palette._entries
        if "bohrung" in f"{e.doc}".casefold() and "Bohrung" not in str(e.title)
    )
    assert rank(im_titel, "bohrung") < rank(nur_im_text, "bohrung")


def test_the_palette_is_sorted_by_what_the_reader_reads() -> None:
    """Die Liste kam nach dem internen englischen Namen.

    ``Registry.all()`` sortiert danach, und die Palette gab das ungefiltert
    weiter: „An Merkmal ausrichten", „Textur aufbringen", „Auf dem Bett
    anordnen", „Slot zuweisen" — für einen deutschen Leser eine Zufallsfolge.
    Die Menüleiste daneben sortiert nach Titel, und ihr Docstring sagt auch,
    warum: „Sortiert wird nach dem, was auf dem Eintrag steht."

    Mit gewähltem Merkmal bleibt die passende Gruppe vorn (§2.6) — sortiert
    wird innerhalb der Gruppen, nicht über sie hinweg.

    Verglichen wird mit ``i18n.sort_key``, demselben Schlüssel, mit dem die
    Menüleiste ihre Einträge ordnet. ``str.casefold`` allein genügt nicht: 23
    der 85 Titel tragen einen Umlaut, und „Überhangfächer" landete damit hinter
    dem letzten Z.
    """
    from app.core.registry import palette_entries
    from app.i18n import sort_key

    titles = [str(entry.title) for entry in palette_entries()]
    assert titles == sorted(titles, key=sort_key), "die Palette folgt nicht dem Titel"
    assert any(title.startswith("Ü") for title in titles), (
        "ohne Umlaut am Wortanfang prüft der Vergleich die Faltung nicht"
    )

    # ``PaletteEntry`` trägt kein ``applies_to`` — welche Operation zu einer
    # Bohrung passt, weiß das Register, und genau daran wird die Reihenfolge
    # gemessen.
    from app.core.registry import REGISTRY

    fits = {spec.name for spec in REGISTRY.all() if "hole" in spec.applies_to}
    assert fits, "ohne passende Operationen prüft dieser Test nichts"
    with_feature = palette_entries(for_feature="hole")
    front = list(with_feature[: len(fits)])
    assert {entry.name for entry in front} == fits, "was zur Auswahl passt, steht vorn"
    inside = [str(entry.title) for entry in front]
    assert inside == sorted(inside, key=sort_key), "und innerhalb der Gruppe nach Titel"
    behind = [str(entry.title) for entry in with_feature[len(fits) :]]
    assert behind == sorted(behind, key=sort_key), "und dahinter genauso"


def test_the_palette_writes_the_keys_the_way_the_keyboard_does(qt_app: object) -> None:
    """Die Palette lehrte „Del", während das Menü daneben „Entf" sagte.

    Bei den Operationen stand die Deklaration aus dem Register, bei den
    Fensterbefehlen ``action.shortcut().toString()`` ohne ``NativeText``.
    Gemessen mit installiertem Qt-Katalog: fünf Operationen und 37
    Fensterbefehle sprachen englisch — dieselbe Handlung mit zwei verschiedenen
    Tasten, je nachdem wo man hinsah.

    Das ist keine Kosmetik: §19.2 macht die Palette zu dem Ort, an dem die
    Kürzel nebenbei gelernt werden. Eine Schreibweise, die auf keiner deutschen
    Tastatur steht, lehrt das Falsche.
    """
    from PySide6.QtGui import QKeySequence
    from PySide6.QtWidgets import QApplication

    from app.core.registry import PaletteEntry, palette_entries
    from app.ui.app import install_qt_translations
    from app.ui.command_palette import native_key

    application = QApplication.instance()
    assert application is not None
    install_qt_translations(application, "de")
    expected = QKeySequence("Del").toString(QKeySequence.SequenceFormat.NativeText)
    if expected == "Del":
        pytest.skip("ohne Qt-Katalog für Deutsch gibt es nichts zu übersetzen")

    assert native_key("Ctrl+B") != "Ctrl+B", "die Umschreibung tut nichts"
    assert native_key("") == "", "ohne Taste keine Taste"
    assert native_key("Kein Kürzel") == "Kein Kürzel", (
        "was Qt nicht versteht, bleibt stehen — wegwerfen wäre schlimmer"
    )

    # Beide Quellen der Palette: die Operationen aus dem Register und die
    # Fensterbefehle, die als PaletteEntry danebengelegt werden.
    entries = list(palette_entries())
    entries.append(
        PaletteEntry(
            name="menu.0", title="Objekt entfernen", doc="", shortcut="Del", category="edit"
        )
    )
    palette = CommandPalette(entries)
    try:
        keys = []
        for row in range(palette.list.count()):
            text = palette.list.item(row).text()
            if "\t" in text:
                keys.append(text.split("\t", 1)[1].split("\n")[0])
        assert keys, "ohne Kürzel prüft dieser Test nichts"
        english = sorted({key for key in keys if "Ctrl" in key or key in ("Del", "Esc")})
        assert not english, f"die Palette spricht englisch: {english}"
        assert expected in keys, "und die deutsche Taste steht nicht da"
    finally:
        palette.deleteLater()
