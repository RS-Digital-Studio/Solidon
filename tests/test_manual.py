"""Das Handbuch (§2.7, §37.2).

Was hier geprüft wird, ist nicht der Wortlaut, sondern die Eigenschaft, die
ein Handbuch überhaupt brauchbar macht: dass es dasselbe sagt wie das
Programm. Die Referenzseiten kommen aus dem Register, also kann eine neue
Operation nicht dazukommen, ohne im Handbuch aufzutauchen — und genau das
steht hier als Zusicherung, damit es so bleibt.

Für die Abbildungen gilt dasselbe: geprüft wird nicht, wie ein Bild aussieht,
sondern dass jeder Verweis auflösbar ist, dass keine Abbildung ohne Alt-Text
existiert und dass keine im Katalog liegt, die niemand zeigt. Wie ein Bild
aussieht, entscheidet ein Augenpaar — daran hätte ein Test nur die
Schriftglättung des Bauservers gemessen.

Achtung beim Erweitern: ein Test, der ein lebendes ``MainWindow`` etwas
fehlschlagen lässt, hängt — das Fenster antwortet auf ``session.failed`` mit
einem modalen Meldungsfenster.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import figures, manual, markup
from app.core.bootstrap import load_operations
from app.core.registry.registry import CATEGORIES, REGISTRY
from app.i18n import tr

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.i18n.catalog import available_languages
from app.ui.manual_window import ManualWindow
from tools.make_figures import SAMPLE_FINDINGS, SAMPLE_OBJECT

#: Die erzeugten Handbuchseiten der Website. Sie sind eingecheckt, weil sie
#: hochgeladen werden — und veralten, sobald jemand am Handbuchtext dreht,
#: ohne ``tools/make_manual.py`` laufen zu lassen.
WEBSITE_PAGES = {
    "de": Path(__file__).parent.parent / "website" / "handbuch.html",
    "en": Path(__file__).parent.parent / "website" / "en" / "manual.html",
}


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


# --- und die erzeugten Seiten bleiben am Stand -----------------------------------


@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_website_page_carries_every_chapter(language: str) -> None:
    """Die eingecheckte Seite muss zum Handbuch passen, nicht zu einem alten.

    ``website/handbuch.html`` und ``website/en/manual.html`` werden
    hochgeladen; das PDF entsteht aus genau derselben Datei. Wer ein Kapitel
    ergänzt und ``tools/make_manual.py`` nicht laufen lässt, hat danach ein
    Programm, eine Website und ein PDF, die drei verschiedene Handbücher
    zeigen — und niemand merkt es, denn keines davon ist kaputt.

    Geprüft werden die Kapitelüberschriften und nicht der ganze Wortlaut: eine
    Datei Zeichen für Zeichen zu vergleichen hieße, sie im Test noch einmal zu
    erzeugen, und dann prüfte er sich selbst.
    """
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    page = WEBSITE_PAGES[language]
    assert page.is_file(), f"{page.name} fehlt — tools/make_manual.py läuft nicht?"

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        html = page.read_text(encoding="utf-8")
        missing = [str(entry.title) for entry in manual.pages() if str(entry.title) not in html]
    finally:
        set_language("de")

    assert not missing, (
        f"{page.name} kennt diese Kapitel nicht:\n"
        + "\n".join(missing)
        + "\n\nNeu erzeugen: .venv\\Scripts\\python.exe tools/make_manual.py"
    )


@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_every_figure_of_the_website_page_is_there(language: str) -> None:
    """Jede Abbildung, die die Seite nennt, liegt auch daneben.

    Ein fehlendes Bild ist im Browser ein Rahmen mit Kreuz und im PDF eine
    Lücke — beides sieht man erst, wenn es jemand liest.
    """
    import re

    folder = WEBSITE_PAGES[language].parent
    html = WEBSITE_PAGES[language].read_text(encoding="utf-8")
    sources = re.findall(r'<img src="([^"]+)"', html)

    assert sources, "eine Handbuchseite ohne eine einzige Abbildung ist keine"
    missing = [name for name in sources if not (folder / name).is_file()]
    assert not missing, f"{WEBSITE_PAGES[language].name} verweist ins Leere:\n" + "\n".join(missing)


# --- was drinsteht ---------------------------------------------------------------


def test_every_category_has_a_chapter() -> None:
    """Eine neue Kategorie kann nicht ohne Kapitel bleiben — sie wird erzeugt.

    Seit den Wissensseiten gibt es zwei Sorten erzeugter Seiten: die Referenz
    aus dem Register und die Tabellen aus ``knowledge/data``. Beide sind
    ``generated``, weil beide keine Handarbeit sind; „erzeugt" heißt deshalb
    nicht mehr „eine Kategorie". Geprüft wird, dass keine Kategorie fehlt —
    das war der Punkt.
    """
    chapters = {page.key for page in manual.pages() if page.generated}
    knowledge = {page.key for page in manual.knowledge_pages()}

    assert chapters - knowledge == set(REGISTRY.by_category())


def test_every_operation_appears_by_name() -> None:
    """So viele Einträge wie Operationen. Sonst wäre das Handbuch eine Auswahl."""
    text = manual.as_markdown()

    for spec in REGISTRY.all():
        assert f"`{spec.name}`" in text, spec.name
        assert str(spec.title) in text, spec.name


def test_the_written_pages_come_first() -> None:
    """Erst erklären, dann nachschlagen — wer das Handbuch öffnet, sucht nicht immer."""
    pages = manual.pages()
    written = [index for index, page in enumerate(pages) if not page.generated]
    generated = [index for index, page in enumerate(pages) if page.generated]

    assert max(written) < min(generated)


def test_no_page_is_empty() -> None:
    for page in manual.pages():
        assert str(page.title).strip(), page.key
        assert len(str(page.body).strip()) > 80, page.key


def test_the_explanations_cover_what_a_schema_cannot_say() -> None:
    """Die geschriebenen Seiten tragen das, was in keinem Parameterschema steht."""
    written = "\n".join(str(page.body) for page in manual.pages() if not page.generated)

    for topic in ("Materialprofil", "Transaktion", "Millimetern", "Slicer"):
        assert topic in written, topic


def test_a_chapter_can_be_asked_for_on_its_own() -> None:
    holes = manual.find("holes")

    assert holes is not None
    assert str(CATEGORIES["holes"]) in str(holes.body)
    assert "drill_hole" in str(holes.body)


def test_the_reference_writes_numbers_the_way_the_language_does() -> None:
    """Vorgabe und Bereich stehen im Trennzeichen der jeweiligen Sprache.

    Die erzeugte Hälfte lieferte ``0.2 … 200`` und ``8.4`` in ein deutsches
    Handbuch — neben eine Anwendung, die im selben Bild ``2,40 mm`` anzeigt.
    Der Leser tippt danach ein, was er gelesen hat, und trifft ein Feld, das
    das Komma erwartet.
    """
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    german = manual.find("holes")
    assert german is not None
    assert "0,2 … 200" in str(german.body)
    assert "0.2 … 200" not in str(german.body)

    install_catalog("en", read_catalog("en"))
    set_language("en")
    try:
        english = manual.find("holes")
        assert english is not None
        assert "0.2 … 200" in str(english.body)
        assert "0,2 … 200" not in str(english.body)
    finally:
        set_language("de")


# --- die Abbildungen --------------------------------------------------------------


def test_every_figure_carries_an_alt_text() -> None:
    """Ohne Alt-Text verschwindet die Aussage, wo kein Bild entstehen kann."""
    for figure in figures.FIGURES:
        assert len(str(figure.alt).strip()) > 30, figure.key


def test_every_reference_resolves() -> None:
    """Ein Verweis auf eine Abbildung, die es nicht gibt, ist eine Lücke im Text."""
    for page in manual.pages():
        for key in page.figures():
            assert figures.find(key) is not None, f"{page.key} → {key}"


def test_no_figure_is_unused() -> None:
    """Eine Abbildung, die niemand zeigt, wird auch von niemandem gepflegt."""
    shown = {key for page in manual.pages() for key in page.figures()}

    assert {figure.key for figure in figures.FIGURES} == shown


def test_the_drawn_figures_come_out_in_both_themes() -> None:
    """Sie brauchen keine Zusatzpakete, also müssen sie immer entstehen."""
    for figure in figures.FIGURES:
        if figure.kind != "drawn":
            continue
        for theme in ("light", "dark"):
            drawn = figures.svg(figure.key, theme)
            assert drawn is not None and drawn.startswith("<svg"), f"{figure.key}/{theme}"


def test_a_figure_that_cannot_be_built_says_so_instead_of_raising() -> None:
    """Ein fehlendes Bild darf ein Kapitel nicht unlesbar machen."""
    assert figures.svg("gibtesnicht") is None


def test_the_text_output_keeps_what_the_pictures_say() -> None:
    """Ohne Bilder tritt der Alt-Text an ihre Stelle, nicht eine Lücke."""
    text = manual.as_markdown()

    assert "![](figure:" not in text
    assert str(figures.find("window").alt) in text


# --- die Ausgabe als HTML ---------------------------------------------------------


def test_the_html_carries_headings_lists_and_tables() -> None:
    html = manual.as_html()

    # ``##`` wird zu ``<h3>``: die Seite selbst trägt das ``<h1>``, und ein
    # Kapitel darunter darf nicht auf derselben Ebene stehen.
    for tag in ("<h3>", "<ul>", "<table>", "<strong>", "<code>"):
        assert tag in html, tag


def test_a_drawn_figure_offers_its_dark_version() -> None:
    """Wo eine dunkle Fassung existiert, steht sie als zweite Quelle daneben.

    Die Zeichnungen konnten beide Themen von Anfang an — ``figures.svg`` nimmt
    das Thema entgegen. Benutzt wurde nur ``light``, und weil die Seite dem
    System folgt, standen im Dunkelmodus zwanzig weiße Kästen mit schwarzer
    Schrift in einer dunklen Seite.
    """
    html = manual.as_html(
        figure_source=lambda key: f"bilder/{key}.svg",
        dark_source=lambda key: f"bilder/{key}-dark.svg",
    )

    assert "<picture>" in html
    assert 'media="(prefers-color-scheme: dark)"' in html
    assert "-dark.svg" in html
    # Ohne dunkle Quelle bleibt es ein gewöhnliches Bild.
    plain = manual.as_html(figure_source=lambda key: f"bilder/{key}.svg")
    assert "<picture>" not in plain


def test_a_figure_without_a_source_falls_back_to_its_text() -> None:
    """Wer keine Bildadresse liefert, bekommt den Alt-Text — kein leeres Kästchen."""
    html = manual.as_html()

    assert "<img" not in html
    assert str(figures.find("window").alt) in html


def test_a_figure_with_a_source_becomes_an_image_with_its_alt_text() -> None:
    html = manual.as_html(figure_source=lambda key: f"bilder/{key}.svg")

    assert '<img src="bilder/window.svg"' in html
    assert f'alt="{figures.find("window").alt}"' in html


def test_markup_escapes_what_would_otherwise_be_markup() -> None:
    """Ein spitzes Klammerpaar im Text darf kein Element werden."""
    assert markup.to_html("Ein <script> im Text") == "<p>Ein &lt;script&gt; im Text</p>"


def test_markup_leaves_asterisks_inside_code_alone() -> None:
    assert markup.to_html("`a * b`") == "<p><code>a * b</code></p>"


@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_no_page_prints_its_own_markup(language: str) -> None:
    """Keine Auszeichnung darf als Sternchenpaar im Handbuch landen.

    Die Auszeichnung ist absichtlich flach (``markup._STRONG`` lässt kein
    Sternchen im Inneren zu): ``**fett mit *kursiv* darin**`` wird nicht
    umgesetzt, sondern gedruckt — mit den Sternchen. Der Umsetzer sagt dazu
    nichts, weil aus seiner Sicht nichts fehlt, und im Fenster fällt es nur
    dem auf, der die Stelle liest.

    Drei Absätze des Zeichnen-Kapitels standen so in der erzeugten Seite,
    bevor sie jemand ansah.

    Gesucht wird das Paar und nicht das einzelne Sternchen: in der Referenz
    steht „Darf ein Ausdruck sein, etwa =breite*2" aus einem
    Parameterschema, und dort ist es ein Malzeichen. In Code darf es ohnehin
    stehen, deshalb fällt ``<code>`` vorher heraus.

    Beide Sprachen, und die zweite ist der Grund: die englische Fassung ist
    ein Eintrag im Katalog. Wer dort einen Absatz von Hand nachzieht, hat
    keinen Umsetzer, der ihn korrigiert, und keine Seite, die er danach
    ansieht.
    """
    import re

    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        offenders: list[str] = []
        for page in manual.pages():
            html = markup.to_html(str(page.body))
            without_code = re.sub(r"<code>.*?</code>", "", html, flags=re.DOTALL)
            for line in without_code.splitlines():
                if "**" in line:
                    offenders.append(f"{page.key}: {line.strip()[:110]}")
    finally:
        set_language("de")

    assert not offenders, f"{language}: unumgesetzte Auszeichnung:\n" + "\n".join(offenders)


# --- das Fenster ------------------------------------------------------------------


def test_the_window_lists_every_page(qt_app: QApplication) -> None:
    window = ManualWindow()

    assert window.contents.count() == len(manual.pages())


def test_searching_looks_inside_the_pages(qt_app: QApplication) -> None:
    """Wer „Elefantenfuß" sucht, weiß nicht, in welchem Kapitel es steht."""
    window = ManualWindow()

    window.search.setText("Elefantenfuß")

    assert window.contents.count() >= 1
    assert window.contents.count() < len(manual.pages())


def test_a_search_without_a_hit_says_so_instead_of_showing_nothing(
    qt_app: QApplication,
) -> None:
    window = ManualWindow()

    window.search.setText("gibtesnicht-xyz")

    assert window.contents.count() == 0
    assert window.text.toPlainText().strip()


def test_clearing_the_search_brings_everything_back(qt_app: QApplication) -> None:
    window = ManualWindow()
    window.search.setText("Elefantenfuß")

    window.search.setText("")

    assert window.contents.count() == len(manual.pages())


def test_a_page_can_be_opened_by_name(qt_app: QApplication) -> None:
    window = ManualWindow()

    window.show_page("tolerances")

    assert "Material" in window.contents.currentItem().text()


# --- Der erzeugte Referenzteil (Konzept Teil 7) ---------------------------------


def test_a_parameter_is_named_before_it_is_keyed() -> None:
    """Die Spalte „Parameter" trug `fill_holes`, `small_components`,
    `self_intersections` — die internen englischen Namen, in Monospace, in
    einem deutschen Handbuch. Was sie bedeuten, stand ganz rechts.
    """
    from app.core.registry import REGISTRY
    from app.core.registry.surfaces import parameter_table

    parameters = REGISTRY.get("repair").params.spec()
    rows = parameter_table(parameters)

    first = next(line for line in rows if "fill_holes" in line)
    cell = first.split("|")[1].strip()
    assert cell.startswith(str(parameters[0].title)), "der Titel steht vorn"
    assert "`fill_holes`" in cell, "und der Schlüssel bleibt daneben"


def test_a_switch_is_on_or_off_not_true_or_false() -> None:
    """Pythons Schreibweise in einem deutschen Handbuch — für jeden, der nicht
    programmiert, zwei Wörter ohne Bedeutung."""
    from app.core.registry import REGISTRY
    from app.core.registry.surfaces import parameter_table

    rows = parameter_table(REGISTRY.get("repair").params.spec())
    joined = "\n".join(rows)

    assert "True" not in joined and "False" not in joined
    assert tr("an") in joined and tr("aus") in joined


def test_an_empty_column_is_left_out() -> None:
    """Bei der Reparatur waren „Einheit" und „Bereich" über die ganze Tabelle
    leer. Eine Spalte, die nichts trägt, ist kein Platzhalter für später,
    sondern eine Frage, die der Leser sich selbst stellt.
    """
    from app.core.registry import REGISTRY
    from app.core.registry.surfaces import parameter_table

    plain = parameter_table(REGISTRY.get("repair").params.spec())
    assert tr("Einheit") not in plain[0]
    assert tr("Bereich") not in plain[0]

    measured = parameter_table(REGISTRY.get("drill_hole").params.spec())
    assert tr("Einheit") in measured[0], "wo Einheiten stehen, steht die Spalte"
    assert tr("Bereich") in measured[0]


def test_the_reference_names_the_feature_kinds() -> None:
    """„Features: face, hole" ist eine Zeile aus dem Register, keine aus einem
    Handbuch."""
    from app.core.registry.surfaces import documentation

    text = documentation(category="holes")

    assert f"{tr('Gilt für')}: {tr('Fläche')}" in text
    assert "face" not in text.split("|")[0], "der Schlüssel steht nicht in der Faktenzeile"


def test_every_category_page_that_has_a_figure_opens_with_it() -> None:
    """Keine Abbildung im ganzen Referenzteil, obwohl der Katalog voll ist.

    Nicht je Operation: dreiundsiebzig Vorher-Nachher-Bilder wären
    dreiundsiebzig Aufbauten, jeder für sich veraltend. Eine je Kategorie
    zeigt, worum es im Kapitel geht.
    """
    from app.core.registry.surfaces import CATEGORY_FIGURES, documentation

    pages = set(REGISTRY.by_category())
    for category, key in CATEGORY_FIGURES.items():
        # Eine Kategorie ohne Operationen bekommt keine Seite (`by_category`
        # lässt leere weg) — ein Eintrag darauf wäre ein toter Verweis.
        assert category in pages, f"{category} hat keine Seite"
        assert f"![](figure:{key})" in documentation(category=category), category
        assert figures.find(key) is not None, f"{category} zeigt auf {key}"


def test_the_knowledge_pages_show_the_numbers_the_program_rechnet_mit() -> None:
    """Die Werte bestimmten jede Passung und jede Warnung — und standen nirgends.

    Geprüft wird gegen die Tabellen selbst, nicht gegen abgeschriebene Zahlen:
    Ein Test, der eine 0,25 erwartet, wäre beim nächsten Kalibrieren rot, ohne
    dass etwas kaputt ist.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.profiles import material_profiles, printer_profiles

    body = manual.profiles_text()
    for profile in material_profiles().values():
        assert profile.title in body, profile.title
    for printer in printer_profiles().values():
        assert printer.title in body, printer.title
    for size in standards.load().screws:
        assert size in body, size


def test_the_rules_page_carries_every_rule() -> None:
    """§39 nennt die Regelsammlung das eigentliche Produkt. Eine Regel, die der
    Agent befolgt und niemand nachlesen kann, ist keines."""
    from app.core.knowledge.rules import load as load_rules

    collection = load_rules()
    body = manual.rules_text()
    for rule in collection.rules:
        assert rule.title in body, rule.id
    assert collection.version in body


def test_the_numbers_are_written_the_way_the_language_writes_them() -> None:
    """Der Kern liefert diese Seite fertig aus — ein Punkt statt eines Kommas
    stünde im deutschen Handbuch neben einer Anwendung, die 2,40 mm anzeigt."""
    from app.i18n import set_language

    try:
        set_language("de")
        assert "0,25" in manual.profiles_text()
        set_language("en")
        assert "0.25" in manual.profiles_text()
    finally:
        set_language("de")


def test_the_knowledge_pages_stand_before_the_reference() -> None:
    """Wonach gerechnet wird, gehört vor die Liste dessen, was gerechnet werden
    kann."""
    keys = [page.key for page in manual.pages()]
    assert keys.index("rules") < keys.index("scene")
    assert keys.index("profiles") < keys.index("scene")


def test_the_remote_page_lists_exactly_what_gets_through() -> None:
    """Eine Seite, die ein gesperrtes Werkzeug mitzählt, verspricht etwas, das
    beim ersten Aufruf abgelehnt wird — und eine, die eines auslässt, versteckt
    Arbeit, die möglich wäre."""
    from app.core.agent.remote import DENIED, remote_tools

    body = manual.remote_text()
    reachable = {entry["name"] for entry in remote_tools()}
    for name in reachable:
        assert f"`{name}`" in body, name
    for name in DENIED:
        assert f"`{name}`" in body, f"{name} muss als gesperrt dastehen"
        assert name not in reachable


def test_the_remote_page_names_the_reason_not_just_the_ban() -> None:
    """Regel 17 gilt auch fürs Handbuch: Eine Sperre ohne Grund ist eine
    Behauptung."""
    body = manual.remote_text()
    assert "Dateipfad" in body
    assert "ausgeführt" in body


def test_every_written_page_says_in_one_sentence_what_it_is_about() -> None:
    """Eine Kurzfassung, die man vergessen darf, schreibt beim zwanzigsten
    Kapitel niemand mehr — deshalb steht sie im Feld und nicht im Fließtext."""
    ohne = [page.key for page in manual.pages() if not page.generated and not page.summary]
    assert not ohne, f"ohne Kurzfassung: {ohne}"


def test_the_summary_reaches_the_reader() -> None:
    """Sie nützt nur, wenn sie ausgegeben wird — im Fenster wie im Handbuch."""
    seite = manual.pages()[0]
    assert str(seite.summary) in seite.text()
    assert str(seite.summary) in manual.as_markdown()


def test_the_message_table_carries_every_exception() -> None:
    """Regel 17: Jede Ausnahme trägt einen Handlungsvorschlag. Eine neue kann
    nicht in die Anwendung kommen, ohne hier im Wortlaut aufzutauchen."""
    import inspect

    from app.core import errors

    body = manual.messages_text()
    for _name, kind in vars(errors).items():
        if not inspect.isclass(kind) or not issubclass(kind, errors.AppError):
            continue
        if kind is errors.AppError:
            continue
        assert str(kind.default_title) in body, kind.__name__
        for action in kind.default_suggestions:
            assert str(action.label) in body, action.id


def test_an_operation_with_a_limit_says_when_not_to_use_it() -> None:
    """Ein Vorbehalt an jeder Operation wäre keiner mehr. An den fünf mit einer
    echten Grenze steht er — und er steht getrennt vom doc-Satz, sonst liest er
    sich wie ein Nachtrag."""
    with_caveat = [spec for spec in REGISTRY.all() if spec.caveat]
    assert len(with_caveat) >= 5
    text = manual.as_markdown()
    for spec in with_caveat:
        assert str(spec.caveat) in text, spec.name
    assert tr("Wann nicht") in text


def test_the_staged_texts_of_the_figures_cover_every_language() -> None:
    """Die gestellten Texte der Aufnahmen gibt es in jeder Sprache.

    Zwei Texte in ``tools/make_figures.py`` laufen bewusst nicht über den
    Katalog, weil der Sammler nur ``app/`` liest: die Befunde im Prüfbericht
    und der Körpername im Operationsdialog. Fehlt eine Sprache, fällt beides
    still auf Deutsch zurück — und das sieht man dem erzeugten Bild nicht an,
    man sieht es erst im fertigen Handbuch, wo ein deutscher Befund mitten im
    fremdsprachigen Text steht. Genau das ist im englischen Handbuch schon
    einmal passiert; der Kommentar an der Stelle erzählt davon.

    Seit eine weitere Sprache nur noch eine Datei in ``app/i18n/locales/``
    ist, kann es jederzeit wieder passieren, ohne dass jemand diese Datei
    öffnet. Deshalb steht der Riegel hier und nicht in der Erinnerung.
    """
    languages = set(available_languages())
    assert not sorted(languages - set(SAMPLE_FINDINGS)), (
        f"ohne gestellte Befunde: {sorted(languages - set(SAMPLE_FINDINGS))}"
    )
    assert not sorted(languages - set(SAMPLE_OBJECT)), (
        f"ohne Körpernamen: {sorted(languages - set(SAMPLE_OBJECT))}"
    )
    for language, findings in SAMPLE_FINDINGS.items():
        assert len(findings) == 4, language
        assert all(text.strip() for text in findings), language
        assert SAMPLE_OBJECT[language].strip(), language
