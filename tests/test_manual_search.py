"""Die Suche im Handbuch (Konzept Handbuch §7, ``app/core/manual_search.py``).

Die Abnahme sind die Kundensuchen aus
``konzepte/nachweise-handbuch-2026-09/findbarkeit.md``: 38 aus dem Auftrag,
zwölf weitere. Mit der alten Suche — Zeichenfolge in Titel oder Text, Liste
in Handbuchreihenfolge — standen am 27.09.2026 25 der 38 unter den ersten
drei und 7 ganz oben, 4 fanden gar nichts. Die Messung vorher und nachher
steht in ``konzepte/nachweise-handbuch-2026-09/suche.md``.
"""

from __future__ import annotations

import pytest

from app.core import manual_search
from app.core.bootstrap import load_operations
from app.core.manual import Page
from app.core.registry import REGISTRY
from app.core.registry.search import CUSTOMER_WORDS
from app.i18n import set_language
from app.i18n.catalog import available_languages, install_language

load_operations()

#: Suche, die Seiten, auf denen ein Kunde die Antwort findet, und ob sie aus
#: dem Auftrag stammt. ``@G`` meint die erzeugte Seite dieses Schlüssels —
#: „parts" ist das Kapitel *Die Bausteine*, „parts@G" die Referenz
#: *Bausteine*. Die Ziele sind die aus der Messung; dazu kommen die
#: Bildanleitungen, wo sie die Antwort sind, und bei *Bambu* und *Zoll* die
#: Referenzseite, auf der Druckerliste und Einheit stehen.
CUSTOMER_SEARCHES: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("Loch", ("drill-a-hole", "start", "holes@G"), True),
    ("Bohrung", ("drill-a-hole", "start", "holes@G"), True),
    ("Gewinde", ("parts@G", "parts"), True),
    ("Gehäuse", ("shaping@G", "prepare@G", "parts@G"), True),
    ("Deckel", ("parts@G",), True),
    ("drehen", ("moving", "transform@G"), True),
    ("verschieben", ("moving", "transform@G"), True),
    ("spiegeln", ("transform@G",), True),
    ("Maß ändern", ("features", "history", "moving", "transform@G"), True),
    ("größer machen", ("moving", "transform@G"), True),
    ("skalieren", ("moving", "transform@G"), True),
    ("rückgängig", ("history",), True),
    ("Slicer", ("print", "print-a-model"), True),
    ("exportieren", ("export",), True),
    ("zu groß", ("splitting", "export"), True),
    ("teilen", ("splitting", "prepare@G"), True),
    ("Text", ("labels", "label@G"), True),
    ("Schrift", ("labels", "label@G"), True),
    ("Rundung", ("features", "shaping@G"), True),
    ("abrunden", ("features", "shaping@G"), True),
    ("Fase", ("features", "shaping@G"), True),
    ("Mutter", ("parts", "parts@G"), True),
    ("Schraube", ("parts", "parts@G"), True),
    ("Magnet", ("parts", "parts@G"), True),
    ("reparieren", ("start", "trouble", "repair@G"), True),
    ("Loch schließen", ("trouble", "repair@G", "holes@G"), True),
    ("hohl", ("prepare@G", "shaping@G", "surfaces"), True),
    ("Wandstärke", ("looking",), True),
    ("Stütze", ("print", "looking", "export"), True),
    ("Überhang", ("looking", "export"), True),
    ("Farbe", ("moving", "colour@G"), True),
    ("zweifarbig", ("moving", "colour@G", "labels"), True),
    ("Skizze", ("sketch", "sketch@G"), True),
    ("zeichnen", ("sketch",), True),
    ("Kreis", ("sketch", "sketch@G"), True),
    ("Passung", ("tolerances",), True),
    ("Spiel", ("tolerances", "variants"), True),
    ("Toleranz", ("tolerances", "variants"), True),
    ("Löcher", ("drill-a-hole", "start", "holes@G"), False),
    ("gravieren", ("labels", "label@G"), False),
    ("Logo", ("sketch", "import@G", "surface@G"), False),
    ("Zoll", ("start", "import@G"), False),
    ("Scharnier", ("parts", "parts@G"), False),
    ("Clip", ("parts", "parts@G"), False),
    ("Strg+Z", ("history",), False),
    ("aufs Bett", ("transform@G", "export"), False),
    ("glätten", ("mesh@G", "sculpting"), False),
    ("kopieren", ("scene@G", "transform@G"), False),
    ("messen", ("looking",), False),
    ("Bambu", ("print", "extras", "profiles@G"), False),
)


def _name(page: Page) -> str:
    return f"{page.key}@G" if page.generated else page.key


def _rank(found: list[manual_search.Found], targets: tuple[str, ...]) -> int | None:
    names = [_name(hit.page) for hit in found]
    ranks = [names.index(target) + 1 for target in targets if target in names]
    return min(ranks) if ranks else None


@pytest.fixture(scope="module")
def index() -> manual_search.SearchIndex:
    return manual_search.SearchIndex()


def test_the_targets_name_pages_that_exist(index: manual_search.SearchIndex) -> None:
    names = {_name(hit.page) for hit in index.search("")}
    unknown = {target for _query, targets, _given in CUSTOMER_SEARCHES for target in targets}
    assert unknown <= names, sorted(unknown - names)


@pytest.mark.parametrize("given_only", [True, False], ids=["auftrag", "alle"])
def test_the_right_page_is_among_the_first_three_for_most_customer_searches(
    index: manual_search.SearchIndex, given_only: bool
) -> None:
    """Abnahme aus Konzept Handbuch §11: mindestens 80 Prozent."""
    chosen = [entry for entry in CUSTOMER_SEARCHES if entry[2] or not given_only]
    misses = []
    for query, targets, _given in chosen:
        rank = _rank(index.search(query), targets)
        if rank is None or rank > 3:
            misses.append(f"{query} ({rank})")
    assert len(misses) <= 0.2 * len(chosen), misses


def test_no_customer_search_comes_back_empty(index: manual_search.SearchIndex) -> None:
    """„abrunden", „zweifarbig", „größer machen", „Loch schließen" fanden
    nichts, weil das Handbuch ein anderes Wort benutzt."""
    empty = [query for query, _targets, _given in CUSTOMER_SEARCHES if not index.search(query)]
    assert not empty, empty


def test_the_page_for_remote_programs_never_stands_before_the_answer(
    index: manual_search.SearchIndex,
) -> None:
    """*Die Werkzeuge der Fernsteuerung* wiederholt jede Operation und stand
    bei vier Kundensuchen vor der richtigen Seite."""
    ahead = []
    for query, targets, _given in CUSTOMER_SEARCHES:
        found = index.search(query)
        names = [_name(hit.page) for hit in found]
        rank = _rank(found, targets)
        if "remote-tools@G" in names and (rank is None or names.index("remote-tools@G") < rank):
            ahead.append(query)
    assert not ahead, ahead


def _pages(*texts: tuple[str, str]) -> list[Page]:
    return [
        Page(key=f"p{number}", title=title, body=body) for number, (title, body) in enumerate(texts)
    ]


def _keys(found: list[manual_search.Found]) -> list[str]:
    return [hit.page.key for hit in found]


def test_a_word_in_the_title_beats_the_same_word_in_the_text() -> None:
    source = _pages(("Andere Dinge", "Hier steht Toleranz im Text."), ("Toleranz", "Anderes."))
    assert _keys(manual_search.search("Toleranz", source)) == ["p1", "p0"]


def test_the_whole_word_beats_a_longer_word_that_starts_with_it() -> None:
    """„hohl" meint *hohl* und nicht die *Hohlkehle*."""
    source = _pages(
        ("Eins", "Die Hohlkehle ist eine Rundung nach innen."),
        ("Zwei", "Ein hohl gedrucktes Teil spart Material."),
    )
    assert _keys(manual_search.search("hohl", source)) == ["p1", "p0"]


def test_several_words_find_only_the_pages_that_carry_all_of_them() -> None:
    source = _pages(
        ("Eins", "Das Maß steht hier, und dort lässt es sich ändern."),
        ("Zwei", "Nur ein Maß."),
        ("Drei", "Nur ändern."),
    )
    assert _keys(manual_search.search("Maß ändern", source)) == ["p0"]


def test_words_side_by_side_come_first_and_the_page_opens_there() -> None:
    source = _pages(
        ("Eins", "Loch hier, und viel später schließen."),
        ("Zwei", "Vorher anderes. Ein Loch schließen Sie mit einem Klick."),
    )
    found = manual_search.search("Loch schließen", source)
    assert _keys(found) == ["p1", "p0"]
    assert found[0].spot == "Loch schließen"


def test_the_page_opens_at_the_first_place_that_fits_or_at_the_top() -> None:
    """Bei *Gehäuse* stand das Wort in der Referenz bei Wort 5 368 — die Seite
    begann trotzdem oben."""
    deep = "Viel davor. " * 50 + "Der **Kasten** entsteht hier, ein Kasten aus einem Quader."
    source = _pages(("Lang", deep), ("Kasten", "Der Kasten steht schon im Titel."))
    found = {hit.page.key: hit.spot for hit in manual_search.search("Kasten", source)}
    assert found == {"p0": "Kasten", "p1": ""}


def test_a_keyboard_without_umlauts_finds_the_same() -> None:
    """Dieselbe Faltung wie in der Befehlspalette: „aushoehlen" meint *Aushöhlen*."""
    source = _pages(("Formen", "Aushöhlen lässt eine Wand stehen."))
    assert _keys(manual_search.search("aushoehlen", source)) == ["p0"]


def test_an_empty_search_lists_every_page_in_its_order() -> None:
    source = _pages(("B", "zwei"), ("A", "eins"))
    found = manual_search.search("  ", source)
    assert _keys(found) == ["p0", "p1"]
    assert all(hit.spot == "" for hit in found)


def test_a_customer_word_leads_to_the_pages_of_its_operation() -> None:
    """„abrunden" steht nirgends im Handbuch; die Palette weiß, dass es
    *Verrunden* meint, und dieselbe Tabelle führt hier zur Seite."""
    title = str(REGISTRY.get("fillet_edges").title)
    source = _pages(("Kanten", f"Mit *{title}* wird die Kante rund."), ("Sonst", "Nichts dazu."))
    found = manual_search.search("abrunden", source)
    assert _keys(found) == ["p0"]
    assert found[0].spot == title


def test_a_customer_word_counts_only_when_the_search_is_that_word() -> None:
    """Wer „vergrößern Temperatur" sucht, meint die Temperatur, nicht *Skalieren*."""
    title = str(REGISTRY.get("scale_object").title)
    source = _pages(
        (title, "Ändert die Größe eines Teils."),
        ("Drucken", "Die Temperatur vergrößern Sie im Profil."),
    )
    assert _keys(manual_search.search("vergrößern", source))[0] == "p0"
    assert _keys(manual_search.search("vergrößern Temperatur", source)) == ["p1"]


def test_the_title_of_an_operation_counts_only_as_a_whole_name() -> None:
    """„Zoll" meint *Modell einfügen*; eine Seite mit „Modell" im Titel und
    „einfügen" irgendwo im Text ist keine Antwort."""
    title = str(REGISTRY.get("load").title)
    first, second = title.split(maxsplit=1)
    source = _pages(
        (f"Ein {first}", f"Weit weg davon steht {second}."),
        ("Einlesen", f"*{title}* fragt nach der Einheit."),
    )
    assert _keys(manual_search.search("Zoll", source)) == ["p1"]


@pytest.mark.parametrize("language", available_languages())
def test_a_customer_word_finds_the_chapter_of_its_operation_in_every_language(
    language: str,
) -> None:
    """Die Kundenwörter stehen je Sprache im Katalog; die Handbuchsuche liest
    dieselben wie die Palette."""
    install_language(language)
    set_language(language)
    spec = REGISTRY.get("fillet_edges")
    phrase = str(CUSTOMER_WORDS["fillet_edges"]).split(";")[0].strip()
    found = manual_search.search(phrase)
    first_three = {(hit.page.key, hit.page.generated) for hit in found[:3]}
    assert (spec.category, True) in first_three, (phrase, _keys(found)[:5])
