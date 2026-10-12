"""Die Suche *Funktion suchen* im Reiter Auswahl: Runden, Güte, Rangfolge, Kundenwörter.

Die Rechnung steht ohne Qt in ``app/core/registry/search.py`` und lebte bis
RM-735 in der Befehlspalette; die meisten Fälle hier prüfen sie ohne Fenster.
Was die Trefferliste der Karte zeichnet und wie Feld und Tasten sich
verhalten, prüft ``tests/test_selection_operations.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

import app
from app.core.bootstrap import load_operations
from app.core.registry import MENU_TWINS, REGISTRY, SearchEntry, search_entries, variant_members
from app.core.registry.search import (
    first_choice,
    found_in_rounds,
    hidden_from_the_menu,
    matches,
    rank,
    ranked,
)

load_operations()


def _names(query: str, entries: list[SearchEntry] | None = None) -> list[str]:
    """Die Treffer einer Suche in ihrer Rangfolge."""
    hits, _loosened = ranked(entries if entries is not None else list(search_entries()), query)
    return [str(entry.name) for entry in hits]


def test_the_search_finds_by_title_name_and_documentation() -> None:
    entry = next(entry for entry in search_entries() if entry.name == "rename_object")
    assert matches(entry, "")
    assert matches(entry, "umbenennen")
    assert matches(entry, "rename")
    assert matches(entry, "objekt umbenennen")
    assert not matches(entry, "bohrung")


def test_the_search_answers_in_rounds() -> None:
    """Genau, dann am Wortstamm, zuletzt für mehrere Wörter irgendeines — und
    die letzte Runde sagt, dass sie gelockert hat.

    Fragebogen zu 0.5.3: Ein Anfänger suchte *Vereinigen* als „verschmelzen“
    und das Löschen als „löschen“; die Karte fand keines davon. Seit RM-735
    ist die Suche der Karte die einzige.
    """
    entries = list(search_entries())

    def found(query: str) -> set[str]:
        return {str(entry.name) for entry in found_in_rounds(entries, query)[0]}

    assert "union_objects" in found("verschmelzen"), "Kundenwort"
    assert "union_objects" in found("zusammenfügen"), "Kundenwort mit Umlaut"
    assert "delete_object" in found("löschen"), "Kundenwort ohne Titeltreffer"
    assert "hollow_object" in found("aushoehlen"), "Faltung"
    assert "drill_hole" in found("bohren"), "zweite Runde: der Wortstamm"
    assert found_in_rounds(entries, "verschmelzen")[1] is False, "eine genaue Runde lockert nicht"
    loose, loosened = found_in_rounds(entries, "loch bitte xyzzy")
    assert loosened and loose, "dritte Runde: ein Wort von mehreren genügt, und sie sagt es"
    assert found_in_rounds(entries, "xyzzy") == ([], False)
    assert ranked(entries, "gibtsnicht") == ([], False), "keine Treffer, nichts vorgewählt"
    assert first_choice([], "gibtsnicht") == -1


def test_without_a_word_every_operation_stands_once() -> None:
    """Ohne Suchtext steht jede Handlung **einmal** — zusammengelegte Zwillinge
    und Variantenmitglieder nicht, wie im Menü.

    Wer „quader“ suchte, bekam sonst „Exakten Quader anlegen“ vor „Quader
    anlegen“ — die Sonderform vor der Normalform. Die Zusage aus §2.6 („alles
    aus dem Register per Suche“) bleibt: Der Test darunter prüft sie.
    """
    listed = {str(entry.name) for entry in found_in_rounds(list(search_entries()), "")[0]}
    versteckt = hidden_from_the_menu()
    assert MENU_TWINS and variant_members(), "beide Mechanismen müssen belegt sein"
    assert versteckt >= set(MENU_TWINS) | variant_members(), "die Regel deckt beide"
    assert listed == {spec.name for spec in REGISTRY.all()} - versteckt


def test_every_merged_twin_is_still_reachable_by_typing() -> None:
    """Und die andere Hälfte: **jeder** Zwilling ist per Suche da (§2.6)."""
    entries = {entry.name: entry for entry in search_entries()}
    assert hidden_from_the_menu(), "ohne versteckte Einträge prüft dieser Test nichts"
    for hidden in hidden_from_the_menu():
        eintrag = entries[hidden]
        assert matches(eintrag, str(eintrag.title)), f"{hidden} über seinen Titel"
        assert not matches(eintrag, ""), f"{hidden} steht nicht in der Grundliste"
    assert matches(entries["shell_exact"], "exakt aushoehlen"), "Kundenwort ohne Umlaut"


def test_the_twin_never_stands_before_its_partner() -> None:
    """Beim Tippen kommt die Normalform zuerst — welche das ist, sagt die
    Maschine (``MENU_TWINS``): mit exaktem Kern der exakte Quader."""
    for suche, mesh, brep in (
        ("quader", "create_box", "create_brep_box"),
        ("zylinder", "create_cylinder", "create_brep_cylinder"),
        ("aushöhlen", "hollow_object", "shell_exact"),
    ):
        zwilling = mesh if mesh in MENU_TWINS else brep
        partner = MENU_TWINS[zwilling]
        namen = _names(suche)
        assert partner in namen and zwilling in namen, f"„{suche}“ findet beide"
        assert namen.index(partner) < namen.index(zwilling), f"„{suche}“: {zwilling} vorn"


def test_typing_exact_finds_both_twins() -> None:
    """Wer „exakt“ tippt, soll **beide** Wege sehen."""
    entries = {entry.name: entry for entry in search_entries()}
    for hidden, shown in MENU_TWINS.items():
        assert matches(entries[hidden], "exakt"), f"{hidden} — der versteckte Zwilling"
        assert matches(entries[shown], "exakt"), f"{shown} — der Eintrag im Menü"


def test_typing_narrows_the_list_and_picks_the_first() -> None:
    hits, _loosened = ranked(list(search_entries()), "duplizieren")
    assert [str(entry.name) for entry in hits] == ["duplicate_object"]
    assert first_choice(hits, "duplizieren") == 0


def test_the_search_finds_words_typed_without_umlauts() -> None:
    """„aushoehlen“ fand **null** Einträge; gefaltet wird auf beiden Seiten."""
    for typed in ("aushoehlen", "aushöhlen", "AUSHOEHLEN"):
        titles = [str(REGISTRY.get(name).title) for name in _names(typed)]
        assert titles, f"{typed!r} findet nichts"
        assert "Aushöhlen" in titles[0], f"{typed!r} zeigt zuerst {titles[0]!r}"


def test_the_search_falls_back_to_the_word_stem() -> None:
    """„bohren“ fand nichts, weil die Operation „Bohrung setzen“ heißt — und
    gelockert wird erst, wenn die genaue Suche leer ausgeht."""
    namen = _names("bohren")
    assert namen, "die Suche nach bohren findet nichts"
    assert "Bohrung" in str(REGISTRY.get(namen[0]).title)
    assert not [entry for entry in search_entries() if matches(entry, "bohren")], (
        "bohren passt neuerdings genau — dann prüft dieser Test nichts"
    )


@pytest.mark.parametrize("query", ["qqq", "qj", "xq"])
def test_a_short_word_that_matches_nothing_finds_nothing(query: str) -> None:
    """Ein Wort unter der Stammlänge hat keinen Stamm — die zweite Runde trifft
    mit ihm nichts.

    Sie prüfte nur die Wörter ab :data:`~app.core.registry.search.STEM_LENGTH`,
    und ohne ein solches war die Bedingung leer und damit wahr: „qqq“ fand alle
    273 Zeilen der Suche, ohne Lockerungszeile, und Return startete die erste.
    """
    entries = list(search_entries())
    assert not [entry for entry in entries if matches(entry, query)], (
        f"{query} passt genau — dann prüft dieser Test nichts"
    )
    assert found_in_rounds(entries, query) == ([], False)
    assert all(rank(entry, query) == 7 for entry in entries)


def test_a_hit_in_the_title_beats_a_hit_in_the_description() -> None:
    """Ohne Ordnung stand bei „bohren“ das *An Merkmal ausrichten* vorn."""
    entries = list(search_entries())
    namen = _names("bohrung", entries)
    assert len(namen) > 1, "zu wenige Treffer, um eine Reihenfolge zu prüfen"
    assert "Bohrung" in str(REGISTRY.get(namen[0]).title)
    im_titel = next(e for e in entries if "Bohrung" in str(e.title))
    nur_im_text = next(
        e for e in entries if "bohrung" in f"{e.doc}".casefold() and "Bohrung" not in str(e.title)
    )
    assert rank(im_titel, "bohrung") < rank(nur_im_text, "bohrung")


def test_the_rows_stand_by_what_the_reader_reads() -> None:
    """Die Zeilen stehen nach dem Titel mit ``i18n.sort_key`` — wie die
    Menüleiste —, nicht nach dem englischen Namen und nicht mit ``casefold``:
    „Überhangfächer" landete sonst hinter dem letzten Z."""
    from app.i18n import sort_key

    titles = [str(entry.title) for entry in search_entries()]
    assert titles == sorted(titles, key=sort_key), "die Suche folgt nicht dem Titel"
    assert any(title.startswith("Ü") for title in titles), (
        "ohne Umlaut am Wortanfang prüft der Vergleich die Faltung nicht"
    )


def test_enter_never_starts_a_command_that_only_the_description_matched() -> None:
    """Wer „Verrund" tippt, bekommt keinen Quader.

    Gesucht wird auch in der Beschreibung, und die Vorauswahl übersprang jede
    gesperrte Zeile: Ohne gewählten Körper war *Quader anlegen* vorgewählt —
    in der Liste allein deshalb, weil sein Satz „Verrundungen" enthält. Enter
    legte einen Quader an (gemessen am 13.09.2026). Die Vorauswahl bleibt
    deshalb in der **besten Güte**: Findet sich dort nichts Ausführbares, steht
    sie auf der ersten Zeile, die sagt, was ihr fehlt.
    """
    gesperrt = SearchEntry(
        name="fillet_edges",
        title="Verrunden",
        category="modify",
        doc="Rundet die gewählten Kanten ab.",
        available=False,
        reason="Wählen Sie dafür ein Objekt aus — im Bild oder im Objektbaum.",
    )
    frei = SearchEntry(
        name="create_box",
        title="Quader anlegen",
        category="create",
        doc="Legt einen Quader an — an seine Kanten lassen sich später Verrundungen setzen.",
    )
    hits, _loosened = ranked([gesperrt, frei], "Verrund")
    assert [str(entry.name) for entry in hits] == ["fillet_edges", "create_box"]
    assert rank(gesperrt, "verrund") < rank(frei, "verrund"), "der Titel wiegt schwerer"
    assert first_choice(hits, "Verrund") == 0, "der beste Treffer, nicht der erste freie"

    zweiter = SearchEntry(
        name="fillet_edges_free",
        title="Verrunden am Netz",
        category="modify",
        doc="Rundet die gewählten Kanten ab.",
    )
    hits, _loosened = ranked([gesperrt, zweiter, frei], "Verrund")
    assert first_choice(hits, "Verrund") == 1, "der erste ausführbare Treffer gleicher Güte"


def test_what_works_here_stands_first_among_equal_hits() -> None:
    """Bei gleicher Güte bleibt die Reihenfolge der Zeilen stehen — dort stellt
    die Karte vorn hin, was an der Auswahl geht (``_search_rows``)."""
    vorn = SearchEntry(name="b_here", title="Bohrung hier", category="holes", doc="")
    hinten = SearchEntry(name="a_there", title="Bohrung dort", category="holes", doc="")
    assert _names("bohrung", [vorn, hinten]) == ["b_here", "a_there"]
    assert _names("bohrung", [hinten, vorn]) == ["a_there", "b_here"]


@pytest.mark.windowed
def test_the_hit_rows_keep_their_second_line_below_the_title() -> None:
    """Echte Schriftmetriken prüfen die Textspalten einer gesperrten Trefferzeile:
    Titel links, Kürzel rechtsbündig, darunter der Grund."""
    import os
    import subprocess
    import sys

    from tests.native_window_probe import require_native_platform

    platform = require_native_platform()
    script = """
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import (
    QApplication, QProxyStyle, QStyle, QStyleFactory, QStyleOptionViewItem,
)
from app.ui.selection_operations import _HitList, _HitRows

application = QApplication([])
drawn, texts = [], []
class Style(QProxyStyle):
    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_ItemViewItem:
            drawn.append(option.text)
        super().drawControl(element, option, painter, widget)
class Painter(QPainter):
    def drawText(self, area, flags, text):
        texts.append((QRect(area), text))
        return super().drawText(area, flags, text)

view = _HitList()
view.resize(520, 200)
style = Style(QStyleFactory.create("Fusion"))
style.setParent(view)
view.setStyle(style)
view.addItem("Bohrung setzen\\tCtrl+B\\nWählen Sie zuerst einen Körper.")
view.item(0).setFlags(view.item(0).flags() & ~Qt.ItemFlag.ItemIsEnabled)
option = QStyleOptionViewItem()
option.rect = QRect(0, 0, 520, 48)
option.widget = view
image = QImage(520, 48, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.white)
painter = Painter(image)
try:
    _HitRows(view).paint(painter, option, view.model().index(0, 0))
finally:
    painter.end()
assert drawn == [""], drawn
assert [text for _area, text in texts] == [
    "Bohrung setzen", "Ctrl+B", "Wählen Sie zuerst einen Körper."
], texts
title, shortcut, detail = (area for area, _text in texts)
assert title.right() < shortcut.left(), texts
assert title.bottom() < detail.top(), texts
assert shortcut.bottom() < detail.top(), texts
view.close()
"""
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": platform},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_chosen_hit_sets_only_its_title_in_bold(qt_app: QApplication) -> None:
    """Die vorgewählte Zeile steht halbfett — nur ihr Titel.

    ``QStyleOptionViewItem.font`` gibt in PySide6 eine Referenz auf das Feld,
    keine Kopie: Wer sie halbfett stellte, stellte Kürzel und zweite Zeile mit
    um. Die zweite Zeile wurde normal umbrochen und halbfett geschrieben, und
    ihre letzte Zeile fiel aus dem Rechteck — in der Zeile, die Return
    ausführt (Review RM-735, F1).
    """
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QFont, QImage, QPainter
    from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

    from app.ui.selection_operations import _HitList, _HitRows

    gezeichnet: list[tuple[str, bool]] = []

    class Painter(QPainter):
        def drawText(self, *args: object) -> None:  # noqa: N802 — Qt-Name
            gezeichnet.append((str(args[-1]), self.font().bold()))
            super().drawText(*args)  # type: ignore[call-overload]

    view = _HitList()
    view.resize(320, 200)
    view.addItem("Bohrung setzen\tCtrl+B\nSetzt eine Bohrung an der gewählten Stelle.")
    delegate = _HitRows(view)
    try:
        for gewaehlt in (False, True):
            gezeichnet.clear()
            option = QStyleOptionViewItem()
            option.rect = QRect(0, 0, 320, 60)
            option.widget = view
            option.font = QFont(view.font())
            option.state = QStyle.StateFlag.State_Enabled | (
                QStyle.StateFlag.State_Selected if gewaehlt else QStyle.StateFlag.State_None
            )
            image = QImage(320, 60, QImage.Format.Format_ARGB32)
            painter = Painter(image)
            try:
                delegate.paint(painter, option, view.model().index(0, 0))
            finally:
                painter.end()
            assert [text for text, _bold in gezeichnet] == [
                "Bohrung setzen",
                "Ctrl+B",
                "Setzt eine Bohrung an der gewählten Stelle.",
            ], gezeichnet
            assert [bold for _text, bold in gezeichnet] == [gewaehlt, False, False], (
                "gewählt" if gewaehlt else "frei",
                gezeichnet,
            )
    finally:
        view.close()


def test_the_search_writes_the_keys_the_way_the_keyboard_does(qt_app: QApplication) -> None:
    """Die Palette lehrte „Del", während das Menü daneben „Entf" sagte.

    Bei den Operationen stand die Deklaration aus dem Register, bei den
    Fensterbefehlen ``action.shortcut().toString()`` ohne ``NativeText`` —
    dieselbe Handlung mit zwei verschiedenen Tasten, je nachdem wo man hinsah.
    Die Trefferliste der Karte schreibt jede Taste mit :func:`native_key`.
    """
    from PySide6.QtGui import QKeySequence

    from app.ui.app import install_qt_translations
    from app.ui.selection_operations import SelectionOperationsPanel
    from app.ui.shortcut_schemes import native_key

    install_qt_translations(qt_app, "de")
    expected = QKeySequence("Del").toString(QKeySequence.SequenceFormat.NativeText)
    if expected == "Del":
        pytest.skip("ohne Qt-Katalog für Deutsch gibt es nichts zu übersetzen")
    assert native_key("Ctrl+B") != "Ctrl+B", "die Umschreibung tut nichts"
    assert native_key("") == "", "ohne Taste keine Taste"
    assert native_key("Kein Kürzel") == "Kein Kürzel", "was Qt nicht versteht, bleibt stehen"

    panel = SelectionOperationsPanel(REGISTRY.all())
    entfernen = SearchEntry(
        name="menu.0", title="Objekt entfernen", doc="", shortcut="Del", category="edit"
    )
    panel.set_search_sources(lambda: [entfernen], lambda _name, declared: declared, frozenset())
    panel.set_context(1, lambda _name: (True, ""))
    try:
        panel.search.setText("entfernen")
        keys = [
            panel.hits.item(row).text().split("\t", 1)[1].split("\n")[0]
            for row in range(panel.hits.count())
            if "\t" in panel.hits.item(row).text()
        ]
        assert keys, "ohne Kürzel prüft dieser Test nichts"
        english = sorted({key for key in keys if "Ctrl" in key or key in ("Del", "Esc")})
        assert not english, f"die Suche spricht englisch: {english}"
        assert expected in keys, "und die deutsche Taste steht nicht da"
    finally:
        panel.deleteLater()


def test_every_hit_names_its_place(qt_app: QApplication) -> None:
    """RM-506: Jeder Treffer nennt seinen Ort — so lernt man ihn nebenbei wie
    das Kürzel. Er steht in Kurzhilfe und Beschreibung der Zeile."""
    from PySide6.QtCore import Qt

    from app.ui.selection_operations import SelectionOperationsPanel

    panel = SelectionOperationsPanel(REGISTRY.all())
    panel.set_context(1, lambda _name: (True, ""))
    try:
        panel.search.setText("verrunden")
        assert panel.hits.count() > 0
        item = panel.hits.item(0)
        assert "Ort:" in item.toolTip() or "Ort:" in str(
            item.data(Qt.ItemDataRole.AccessibleDescriptionRole)
        ), item.toolTip()
    finally:
        panel.deleteLater()


#: Wörter, die ein Kunde tippt, und die Operation, die er meint.
#:
#: Ausgewählt nach dem, was jemand sagt, der noch nie in unserem Register
#: gelesen hat: Alltagswörter, Slicer-Wörter und die aus anderen
#: CAD-Programmen. Gemessen am 23.08.2026 fanden **zehn von 42** davon nichts —
#: „abrunden", „halbieren", „gravieren", „zusammenfügen", „ausschneiden" und
#: fünf weitere.
CUSTOMER_WORDS: tuple[tuple[str, str], ...] = (
    ("abrunden", "fillet_edges"),
    ("kante brechen", "chamfer_edges"),
    ("array", "pattern"),
    ("zerschneiden", "split_pinned"),
    ("halbieren", "split_pinned"),
    ("zusammenfügen", "union_objects"),
    ("ausschneiden", "subtract_objects"),
    ("gravieren", "label_text"),
    ("beschriften", "label_text"),
    ("vereinfachen", "decimate_mesh"),
    # Die zweite Messung, am selben Abend: vierzig Wörter gegen die
    # Kategorien, die noch niemand durchgesehen hatte. Sechs fanden nichts,
    # und **kein einziges davon war ein Fachbegriff** — es waren die
    # gewöhnlichsten Wörter, die es gibt.
    ("kopieren", "duplicate_object"),
    ("löschen", "delete_object"),
    ("öffnen", "load"),
    ("importieren", "load"),
    ("färben", "assign_slot"),
    ("anmalen", "paint_slot"),
    ("logo", "displace_image"),
    ("foto", "displace_image"),
)


def test_the_search_finds_what_a_customer_types() -> None:
    """Wer sein Wort tippt, findet die Operation — auch wenn sie anders heißt.

    **Robert am 23.08.2026:** „schau dir alle funktionen nochmal an und ob sie
    wirklich einfach sind, leicht zu verstehen für kunden."

    Die Palette faltet Umlaute und sucht nach Wortstämmen, und beides trägt
    weit: „aushoehlen" findet das Aushöhlen, „bohren" die Bohrung. Es trägt
    aber nicht über die Wortgrenze. Gemessen an 42 Kundenwörtern fanden zehn
    **nichts** — nicht das Falsche, sondern gar nichts, und die Palette sagte
    „Kein Befehl passt".

    Der Docstring von ``matches`` sagt, eine Synonymtabelle decke so etwas „nie
    vollständig" ab. Das stimmt und ist kein Grund, sie wegzulassen: Zehn von
    42 sind kein Rand, und jedes Wort hier ist eines, das jemand wirklich
    tippt. Vollständig muss sie nicht sein — sie muss die häufigen treffen.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.registry.search import matches

    load_operations()
    from app.core.registry.surfaces import search_entries

    eintraege = search_entries(REGISTRY)

    ohne: list[str] = []
    falsch: list[str] = []
    for wort, gemeint in CUSTOMER_WORDS:
        treffer = [e for e in eintraege if matches(e, wort)]
        if not treffer:
            treffer = [e for e in eintraege if matches(e, wort, stem=True)]
        if not treffer:
            ohne.append(wort)
        elif not any(e.name == gemeint for e in treffer):
            falsch.append(f"{wort} -> {[e.name for e in treffer][:3]}, gemeint war {gemeint}")

    assert not ohne, "diese Wörter finden nichts: " + ", ".join(ohne)
    assert not falsch, "diese Wörter finden das Falsche: " + "; ".join(falsch)


def test_every_customer_word_points_at_an_operation_that_exists() -> None:
    """Die Tabelle altert mit dem Register — dieser Test merkt es.

    Ein Synonym, dessen Ziel umbenannt wurde, zeigt ins Leere und niemand
    merkt es: Die Suche findet dann wieder nichts, und der Kunde hält es für
    seinen Fehler.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY

    load_operations()
    fehlend = [ziel for _wort, ziel in CUSTOMER_WORDS if not REGISTRY.has(ziel)]
    assert not fehlend, "diese Operationen gibt es nicht (mehr): " + ", ".join(fehlend)


def test_the_word_a_customer_types_lands_on_top() -> None:
    """Gefunden genügt nicht — es muss an erster Stelle stehen.

    **Der Fund, der diesen Test veranlasst hat.** Die Synonymtabelle wirkte,
    und trotzdem sah der Kunde das Falsche: „oeffnen" fand *Modell laden*, aber
    ``rank`` stellte *Deckel erzeugen* davor — dessen Beschreibung enthält
    „offen", und ein Wortstamm im Titel wog schwerer als ein Synonym. Dasselbe
    bei „importieren", das auf *Fläche versetzen* zeigte.

    **Ein Synonym ist eine bewusste Zuordnung, ein Stammtreffer eine
    Rechnung.** Jemand hat aufgeschrieben, dass dieses Kundenwort diese
    Operation meint; die Rechnung trifft auch daneben. Deshalb rangiert das
    Synonym seit dieser Messung vor dem Stamm.

    Der Test daneben (``test_the_search_finds_what_a_customer_types``) prüft,
    dass das Gemeinte **dabei** ist. Beide zusammen sind die Zusage: Wer sein
    Wort tippt, sieht es zuerst.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.registry.search import matches, rank
    from app.core.registry.surfaces import search_entries

    load_operations()
    eintraege = search_entries(REGISTRY)
    assert eintraege, "keine Zeilen der Suche — dann prüft das nichts"

    daneben: list[str] = []
    for wort, gemeint in CUSTOMER_WORDS:
        treffer = [e for e in eintraege if matches(e, wort)]
        if not treffer:
            treffer = [e for e in eintraege if matches(e, wort, stem=True)]
        if not treffer:
            continue  # der Test daneben meldet das, hier zählt die Reihenfolge
        # ``min`` nimmt bei Gleichstand das erste — dieselbe Zusage wie die
        # stabile Sortierung der Palette, auf der „Was zur Auswahl passt, steht
        # vorn" beruht.
        erste = min(treffer, key=lambda e: rank(e, wort))
        if erste.name != gemeint:
            daneben.append(f"{wort} -> {erste.name} statt {gemeint}")

    assert not daneben, "diese Wörter zeigen zuerst auf das Falsche: " + "; ".join(daneben)


#: Kundenwörter in jeder Sprache, und was sie meinen (Durchsicht 0.5.1). Vorher
#: fanden „copy", „calamita", „apagar", „Füße" nichts oder das Falsche, und
#: „Loch größer" fand *Bohrung setzen* statt *Bohrung ändern*: Die Kundenwörter
#: gab es nur auf Deutsch, und die Titel tragen dieselbe Lücke über die
#: Wortgrenze wie im Deutschen.
WORDS_BY_LANGUAGE: tuple[tuple[str, str, str], ...] = (
    ("de", "Loch größer", "resize_hole"),
    ("de", "Füße", "insert_foot"),
    ("de", "Würfel", "create_brep_box"),
    ("de", "Loch machen", "drill_hole"),
    ("de", "flicken", "repair"),
    ("de", "subtrahieren", "subtract_objects"),
    ("de", "Differenz", "subtract_objects"),
    ("de", "difference", "subtract_objects"),
    ("de", "union", "union_objects"),
    ("es", "diferencia", "subtract_objects"),
    ("fr", "différence", "subtract_objects"),
    ("it", "differenza", "subtract_objects"),
    ("pt", "diferença", "subtract_objects"),
    ("pt", "union", "union_objects"),
    ("en", "copy", "duplicate_object"),
    ("en", "make hole bigger", "resize_hole"),
    ("en", "move hole", "move_feature"),
    ("en", "feet", "insert_foot"),
    ("es", "agujero más grande", "resize_hole"),
    ("es", "borrar", "delete_object"),
    ("fr", "trou plus grand", "resize_hole"),
    ("fr", "copier", "duplicate_object"),
    ("it", "calamita", "insert_magnet_pocket"),
    ("it", "girare", "rotate_object"),
    ("pt", "apagar", "delete_object"),
    ("pt", "ímã", "insert_magnet_pocket"),
)


@pytest.mark.parametrize(("language", "word", "meant"), WORDS_BY_LANGUAGE)
def test_a_customer_finds_his_operation_in_his_language(
    language: str, word: str, meant: str
) -> None:
    """Dieselbe Frage wie ``test_the_word_a_customer_types_lands_on_top`` — in
    der Sprache, in der der Kunde tippt, mit den Kundenwörtern seiner Sprache
    (``registry.search.CUSTOMER_WORDS``)."""
    from app.core.bootstrap import load_operations
    from app.core.registry.search import rank
    from app.core.registry.surfaces import search_entries
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    load_operations()
    install_language(language)
    set_language(language)
    eintraege = search_entries(REGISTRY)
    treffer = [e for e in eintraege if matches(e, word)] or [
        e for e in eintraege if matches(e, word, stem=True)
    ]
    assert treffer, f"„{word}“ findet auf {language} nichts"
    erste = min(treffer, key=lambda e: rank(e, word))
    assert erste.name == meant, f"„{word}“ ({language}) zeigt zuerst {erste.name}"


def test_a_word_inside_a_title_does_not_beat_the_word_that_means_it() -> None:
    """„Stützen" stellte *Hilfe: Solidon3D unterstützen …* vor alles, weil das
    Wort mitten in „unterstützen" steckt. Ein Titel zählt am Wortanfang; mitten
    im Wort erst nach den Kundenwörtern."""
    from app.core.bootstrap import load_operations
    from app.core.registry.search import rank
    from app.core.registry.surfaces import SearchEntry, search_entries

    load_operations()
    spende = SearchEntry(
        name="menu.41", title="Hilfe: Solidon3D unterstützen …", doc="", category="menu"
    )
    ausrichten = next(e for e in search_entries(REGISTRY) if e.name == "orient_for_print")
    assert rank(ausrichten, "Stützen") < rank(spende, "Stützen")


#: Der Fachbegriff, den ein Umsteiger aus einem CAD-Programm tippt, je Sprache
#: (RM-734). Fragebogen zu 0.5.3: „Boolesche Operationen wären toll“ — es gab
#: sie, aber „boolesch“, „Boolean“ und „kombinieren“ fanden nichts, und
#: „Boolesche Operation“ zeigte *Fläche versetzen*.
BOOLEAN_WORDS: tuple[tuple[str, str], ...] = (
    ("de", "boolesch"),
    ("de", "Boolesche Operation"),
    ("de", "Boolean"),
    ("de", "kombinieren"),
    ("en", "boolean"),
    ("en", "Boolean operation"),
    ("es", "booleano"),
    ("fr", "booléen"),
    ("it", "operazione booleana"),
    ("pt", "booleano"),
)

_BOOLEANS: frozenset[str] = frozenset({"union_objects", "subtract_objects", "intersect_objects"})


@pytest.mark.parametrize(("language", "word"), BOOLEAN_WORDS)
def test_the_technical_word_finds_the_three_boolean_operations(language: str, word: str) -> None:
    """Vorn stehen die drei Booleschen, keine andere Operation davor."""
    from app.core.bootstrap import load_operations
    from app.core.registry.search import found_in_rounds, rank
    from app.core.registry.surfaces import search_entries
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    load_operations()
    install_language(language)
    set_language(language)
    found, loosened = found_in_rounds(search_entries(REGISTRY), word)
    assert not loosened, f"„{word}“ ({language}) passt nur auf einzelne Wörter"
    vorn = {str(entry.name) for entry in sorted(found, key=lambda e: rank(e, word))[:3]}
    assert vorn == _BOOLEANS, f"„{word}“ ({language}) zeigt vorn {sorted(vorn)}"


@pytest.mark.parametrize(
    ("language", "word", "meant", "row", "title"),
    [
        ("de", "Differenz", "subtract_objects", "settings.diff_palette", "Differenzansicht"),
        ("en", "difference", "subtract_objects", "settings.diff_palette", "Differenzansicht"),
    ],
)
def test_a_customer_word_said_exactly_beats_a_longer_word_in_a_title(
    language: str, word: str, meant: str, row: str, title: str
) -> None:
    """Wer „Differenz“ tippt, meint das Abziehen, nicht die Einstellung
    *Differenzansicht*, und wer „difference“ tippt, nicht *Difference view*.
    Das Kundenwort ist eine Zuordnung, das Wort im Titel der anderen Zeile ein
    Zufall (RM-734)."""
    from app.core.bootstrap import load_operations
    from app.core.registry.search import rank
    from app.core.registry.surfaces import SearchEntry, search_entries
    from app.i18n import set_language, tr
    from app.i18n.catalog import install_language

    load_operations()
    install_language(language)
    set_language(language)
    gemeint = next(e for e in search_entries(REGISTRY) if e.name == meant)
    shown = tr("{name}: {value}", name=tr("Einstellungen"), value=tr(title))
    zeile = SearchEntry(name=row, title=shown, doc="", category="settings")
    assert rank(gemeint, word) < rank(zeile, word), f"„{word}“ ({language}) zeigt {shown} zuerst"


def test_among_the_best_hits_what_works_stands_before_what_is_locked() -> None:
    """Unter den besten Treffern steht das Freie vor dem Gesperrten, auch wenn
    das Gesperrte ein Kundenwort trägt.

    „Wandhalter“ ohne Auswahl: Beide Zeilen heißen so, nur der Baustein *an*
    die Auswahl hat das Kundenwort „Wandhalterung“ — und geht ohne Körper
    nicht. Er stand ohne diesen Schlüssel über dem freien, eigenen Körper
    (Nachprüfung RM-735, N6).
    """
    gesperrt = SearchEntry(
        name="insert_wall_mount",
        title="Wandhalter",
        category="parts",
        doc="",
        available=False,
        reason="Wählen Sie dafür ein Objekt aus.",
    )
    frei = SearchEntry(name="create_wall_mount", title="Wandhalter", category="parts", doc="")
    hits, _loosened = ranked([gesperrt, frei], "Wandhalter")
    assert [entry.name for entry in hits] == ["create_wall_mount", "insert_wall_mount"]


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
def test_whoever_types_a_whole_title_gets_that_row_first(language: str) -> None:
    """Den ganzen Titel einer Zeile schlägt keine andere Zeile.

    RM-734 stellte ein genau gesagtes Kundenwort vor jeden Titelanfang, damit
    „Differenz“ das Abziehen vor der Einstellung *Differenzansicht* zeigt. Die
    Regel griff auch, wo die Anfrage der **ganze Titel** einer anderen Zeile
    war: „Wiederholen“ wählte *Kopien in Reihe oder Kreis* vor, weil
    „wiederholen“ dessen Kundenwort ist — Return startete eine andere Handlung
    als die, deren Namen man getippt hatte (Review RM-735, F6). Gleich gut
    darf eine andere sein („Verschieben“ und *Merkmal verschieben*): Dann
    entscheidet, was an der Auswahl steht.

    **Gezählt wird die Vorauswahl, nicht nur die Güte.** Bei gleicher Güte
    entschied das Alphabet: „Tornillo“ wählte das *Agujero para tornillo* vor,
    „Schraube“ den Baustein — je Sprache eine andere Handlung (Nachprüfung
    RM-735, N1). Ohne Auswahl steht keine Zeile an der Lage; dann gewinnt der
    ganze Titel.
    """
    from app.core.registry.search import rank
    from app.i18n import set_language, tr
    from app.i18n.catalog import install_language

    load_operations()
    install_language(language)
    set_language(language)
    try:
        wiederholen = SearchEntry(
            name="edit.redo", title=tr("Wiederholen"), doc="", category="edit"
        )
        zeilen = [*search_entries(REGISTRY), wiederholen]
        daneben: list[str] = []
        for zeile in zeilen:
            titel = str(zeile.title)
            eigene = rank(zeile, titel)
            for andere in zeilen:
                if str(andere.title) != titel and rank(andere, titel) < eigene:
                    daneben.append(f"„{titel}“ -> {andere.name} vor {zeile.name}")
            hits, _loosened = ranked(zeilen, titel)
            gewaehlt = hits[first_choice(hits, titel)]
            if str(gewaehlt.title) != titel:
                daneben.append(f"„{titel}“ wählt {gewaehlt.name} vor statt {zeile.name}")
        assert not daneben, f"{language}: " + "; ".join(daneben[:10])
    finally:
        install_language("de")
        set_language("de")


def test_every_customer_word_belongs_to_a_row_of_the_search() -> None:
    """Ein Kundenwort, dessen Ziel es nicht gibt, zeigt stumm ins Leere.

    So stand es bis zur Durchsicht 0.5.1 um „flicken" und „löcher schließen":
    eingetragen unter ``repair_mesh``, die Operation heißt ``repair``. Ein
    Schlüssel ist eine Operation oder ein Fensterbefehl, den das Hauptfenster
    unter genau dieser Kennung in die Palette legt.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry.search import CUSTOMER_WORDS, SYNONYMS

    load_operations()
    fenster = (Path(app.__file__).parent / "ui" / "main_window.py").read_text(encoding="utf-8")
    fehlend = [
        name
        for name in (*SYNONYMS, *CUSTOMER_WORDS)
        if not REGISTRY.has(name) and f'"{name}": (' not in fenster
    ]
    assert not fehlend, "diese Kundenwörter zeigen auf nichts: " + ", ".join(fehlend)


def test_an_operation_shown_as_a_window_command_hands_over_its_words() -> None:
    """Seit RM-507 zeigt die Palette *Modell einfügen* nur als Fensterbefehl
    ``file.import``; die Operation ``load`` hat dort keine Zeile mehr. Ihre
    Kundenwörter hingen nur an ihr, und „STL“ oder „Zoll“ fanden das Einlesen
    nicht mehr (Nachprüfung N1)."""
    from app.core.registry.search import SYNONYMS, customer_phrases
    from app.core.registry.surfaces import SearchEntry
    from app.ui.main_window import WINDOW_COMMAND_OPERATIONS

    assert WINDOW_COMMAND_OPERATIONS, "keine Operation als Fensterbefehl — der Test prüfte nichts"
    for name, command in WINDOW_COMMAND_OPERATIONS.items():
        assert SYNONYMS.get(name) == SYNONYMS.get(command), command
        assert set(customer_phrases(name)) <= set(customer_phrases(command)), command
    einlesen = SearchEntry(name="file.import", title="Modell einfügen …", doc="", category="file")
    for wort in ("stl", "zoll", "importieren"):
        assert matches(einlesen, wort), wort
