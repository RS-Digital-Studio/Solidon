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

from html import escape, unescape
from pathlib import Path

import pytest

from app.branding import APP_VERSION
from app.core import figures, manual, markup
from app.core.bootstrap import load_operations
from app.core.registry.registry import CATEGORIES, REGISTRY
from app.i18n import tr

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.i18n.catalog import available_languages
from app.ui.manual_window import ManualWindow
from tools.make_figures import SAMPLE_OBJECT, SAMPLE_PRINTER

#: Die erzeugten Handbuchseiten der Website. Sie sind eingecheckt, weil sie
#: hochgeladen werden — und veralten, sobald jemand am Handbuchtext dreht,
#: ohne ``tools/make_manual.py`` laufen zu lassen.
WEBSITE_PAGES = {
    "de": Path(__file__).parent.parent / "website" / "handbuch.html",
    "en": Path(__file__).parent.parent / "website" / "en" / "manual.html",
    "es": Path(__file__).parent.parent / "website" / "es" / "manual.html",
    "fr": Path(__file__).parent.parent / "website" / "fr" / "manual.html",
    "it": Path(__file__).parent.parent / "website" / "it" / "manual.html",
    "pt": Path(__file__).parent.parent / "website" / "pt" / "manual.html",
}

RELEASES = Path(__file__).parent.parent / "Releases"

PUBLIC_WARNING_MARKERS = (
    "sicherheitskrit",
    "safety-critical",
    "críticos para la seguridad",
    "critiques pour la sécurité",
    "critici per la sicurezza",
    "críticas para a segurança",
)


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


# --- und die erzeugten Seiten bleiben am Stand -----------------------------------


def test_the_manual_has_pages_at_all() -> None:
    """Die Grundmenge, über der drei Verbotstests darunter arbeiten.

    ``…carries_every_chapter``, ``…carries_its_own_heading`` und
    ``…says_in_one_sentence_what_it_is`` fragen alle dasselbe: *welche* Seite
    etwas nicht hat. Liefert ``pages()`` gar keine, ist die gesuchte Menge leer
    und alle drei sind grün — nicht weil das Handbuch stimmt, sondern weil es
    keins gibt.

    Die Zusicherung steht hier und nicht dreimal daneben: Ein roter Test genügt,
    damit das Tor es merkt, und der Grund ist nur an einer Stelle zu pflegen.
    """
    pages = manual.pages()
    assert len(pages) > 5, f"das Handbuch hat {len(pages)} Seiten"
    assert any(page.generated for page in pages), "keine erzeugte Seite"
    assert any(not page.generated for page in pages), "keine geschriebene Seite"


@pytest.mark.rendered
@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_manual_intro_reads_like_product_documentation(language: str) -> None:
    """Die Einführung verweist auf Rechtstexte, sie wiederholt keine Warnliste."""
    html = WEBSITE_PAGES[language].read_text(encoding="utf-8")
    intro = html.split('<h3 id="what">', 1)[1].split('<h3 id="start">', 1)[0]
    present = [marker for marker in PUBLIC_WARNING_MARKERS if marker in intro.casefold()]
    assert not present, f"{language}: rechtliche Warnliste im Handbuch: {present}"


@pytest.mark.rendered
@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_checked_in_manual_carries_the_current_version(language: str) -> None:
    """Die nie veröffentlichte Zwischenfassung darf nicht auf dem Umschlag bleiben."""
    html = WEBSITE_PAGES[language].read_text(encoding="utf-8")
    cover = html.split("</section>", 1)[0]

    assert APP_VERSION in cover, f"{language}: Umschlag nicht auf {APP_VERSION}"


@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_checked_in_pdf_carries_the_current_version(language: str) -> None:
    """Website und PDF tragen denselben Versionsstand auf ihrer Titelseite."""
    from pypdf import PdfReader

    path = RELEASES / f"Solidon3D-Handbuch-{language}.pdf"
    assert path.is_file(), f"{path.name} fehlt — tools/make_manual.py ausführen"
    cover = PdfReader(path).pages[0].extract_text() or ""

    assert APP_VERSION in cover, f"{path.name}: Titelseite nicht auf {APP_VERSION}"


def test_written_manual_covers_the_current_demo_and_visible_controls() -> None:
    """Die handgeschriebenen Kapitel nennen den ausgelieferten Zustand."""
    pages = {page.key: str(page.body) for page in manual.pages()}

    activation = pages["activation"]
    assert "30. Oktober 2026" in activation
    assert "vollständig freigeschaltet" in activation
    assert "startet diese Demo nicht mehr" in activation

    seeing = pages["looking"]
    for value in (
        "Schichtnummer und Gesamtzahl",
        "Z-Höhe",
        "Querschnittsfläche",
        "Zahl der Inseln",
        "Überhangfläche",
    ):
        assert value in seeing, f"Schichtvorschau ohne {value}"

    parts = pages["parts"]
    for title in ("Kugellager einsetzen", "Schraube", "Gedruckte Mutter"):
        assert title in parts, f"Bausteinübersicht ohne {title}"

    exchange = pages["exchange"]
    assert "Baustein als Datei weitergeben …" in exchange
    assert "Baustein aus Datei hinzufügen …" in exchange

    generating = pages["generating"]
    assert "TripoSG" in generating and "ComfyUI" in generating
    assert "Reparaturkette läuft ohne Nachfrage" in generating

    extras = pages["extras"]
    assert "Lokale KI-Arbeit läuft nacheinander" in extras
    assert "entlädt es das Ollama-Modell" in extras
    assert "nur den Auftrag, den Solidon selbst gestartet hat" in extras


@pytest.mark.rendered
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


@pytest.mark.rendered
@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_website_reference_carries_every_operation_and_parameter(language: str) -> None:
    """Ein neues Feld darf nicht hinter einer unveränderten Kapitelüberschrift fehlen.

    Die Kapitelprüfung darüber sah den neuen Lagersitz nicht: Er kam in die
    bestehende Kategorie *Bausteine*, deren Überschrift schon im alten HTML
    stand. Geprüft wird deshalb die Referenz selbst — jede Operation und jedes
    ihrer dort einzeln aufgeführten Felder, in allen sechs Sprachfassungen.
    """
    from app.core.registry.surfaces import PART_PLACEMENT_PARAMS

    html = WEBSITE_PAGES[language].read_text(encoding="utf-8")
    missing: list[str] = []
    for spec in REGISTRY.all():
        # Das schließende ``h4`` unterscheidet den Referenzeintrag von der
        # gleichlautenden Kennung in der kurzen Operationsliste davor.
        marker = f"(<code>{spec.name}</code>)</h4>"
        start = html.find(marker)
        if start < 0:
            missing.append(spec.name)
            continue
        end = html.find("<h4>", start + len(marker))
        section = html[start : end if end >= 0 else len(html)]
        parameters = spec.params.spec()
        if spec.category == "parts":
            parameters = tuple(
                entry for entry in parameters if entry.name not in PART_PLACEMENT_PARAMS
            )
        for entry in parameters:
            if f"<code>{entry.name}</code>" not in section:
                missing.append(f"{spec.name}.{entry.name}")

    assert not missing, (
        f"{WEBSITE_PAGES[language].name} hat eine veraltete Referenz:\n"
        + "\n".join(missing)
        + "\n\nNeu erzeugen: .venv\\Scripts\\python.exe tools/make_manual.py"
    )


@pytest.mark.rendered
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
    # Der Inhaltsstempel (`tools/stamp_assets.py`) hängt an der Adresse, nicht
    # am Dateinamen: `de/report.png?v=a8bf1166` liegt als `de/report.png` da.
    missing = [name for name in sources if not (folder / name.split("?", 1)[0]).is_file()]
    assert not missing, f"{WEBSITE_PAGES[language].name} verweist ins Leere:\n" + "\n".join(missing)


@pytest.mark.rendered
@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_website_page_carries_the_generated_reference(language: str) -> None:
    """Der **erzeugte** Teil der Seite muss zum Register passen.

    Der Test darüber prüft die Kapitel — die geschriebenen Seiten. Der
    Referenzteil kommt aus einer anderen Quelle: ``documentation()`` baut ihn
    aus dem Register, und jede Änderung dort veraltet die eingecheckte Seite
    still. Genau das ist passiert: Elf Parameter bekamen eine Bedingung, und
    ohne einen Lauf von ``tools/make_manual.py`` hätte keiner davon in der
    Website gestanden, während der Dialog sie zeigte.

    Aufgefallen wäre es niemandem — der Ändernde und der Prüfende waren
    dieselbe Person, und das ist keine Absicherung, sondern ein Zufall.

    Geprüft wird gegen das **Register** und nicht gegen die ganze Datei: Zeichen
    für Zeichen zu vergleichen hieße, die Seite im Test noch einmal zu erzeugen,
    und dann prüfte er sich selbst.
    """
    from app.core.registry import REGISTRY
    from app.core.registry.params import condition_text
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    page = WEBSITE_PAGES[language]
    assert page.is_file(), f"{page.name} fehlt — tools/make_manual.py läuft nicht?"

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        html = page.read_text(encoding="utf-8")
        missing: list[str] = []
        for spec in REGISTRY.all():
            if escape(str(spec.title)) not in html:
                missing.append(f"{spec.name}: Titel")
            # Der Vorbehalt selbst und nicht die ganze Zeile: Im Handbuch
            # steht sein Vorwort halbfett, also als ``<strong>`` und nicht
            # mit den Sternchen, die ``caveat_line`` setzt.
            if spec.caveat and escape(str(spec.caveat)) not in html:
                missing.append(f"{spec.name}: Vorbehalt")
            schema = spec.params.spec()
            for entry in schema:
                condition = condition_text(entry, schema)
                if condition and escape(condition) not in html:
                    missing.append(f"{spec.name}.{entry.name}: {condition}")
    finally:
        set_language("de")

    assert not missing, (
        f"{page.name} ist älter als das Register:\n"
        + "\n".join(missing[:20])
        + (f"\n… und {len(missing) - 20} weitere" if len(missing) > 20 else "")
        + "\n\nNeu erzeugen: .venv\\Scripts\\python.exe tools/make_manual.py"
    )


#: Die Ordner mit den erzeugten Abbildungen, je Sprache einer.
FIGURE_FOLDERS = {
    language: Path(__file__).parent.parent / "website" / "handbuch" / language
    for language in ("de", "en", "es", "fr", "it", "pt")
}


@pytest.mark.parametrize("language", sorted(FIGURE_FOLDERS))
def test_the_drawn_figures_are_the_ones_the_code_draws(language: str) -> None:
    """Jede eingecheckte Zeichnung ist die, die der Code heute zeichnet.

    **Der Fund, aus dem dieser Test entstand:** `ways.svg` zeigte drei Wege, und
    zwar in allen sechs Sprachen. Der vierte war seit P16 gebaut, das Handbuch
    beschrieb ihn, `EXAMPLES` führte sein Beispiel — und die Abbildung daneben
    zeigte weiter drei Zeilen, weil niemand `tools/make_manual.py` laufen ließ.
    Gefangen hätte es kein Test: der Nachbar prüft die Kapitelüberschriften, der
    andere die Sprungmarken, der dritte den Referenztext. Ein Bild sagt keines
    davon.

    Geprüft werden nur die **gezeichneten** (``kind == "drawn"``): Sie entstehen
    aus `core.drawing` ohne Qt und sind damit Zeichen für Zeichen dieselbe
    Datei. Gerendertes und Bildschirmfotos hängen an VTK, an Schriften und am
    Bildschirm — die zu vergleichen hieße, die Maschine zu prüfen und nicht die
    Anwendung.
    """
    from app.core import figures
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    folder = FIGURE_FOLDERS[language]
    assert folder.is_dir(), f"{folder.name} fehlt — tools/make_manual.py läuft nicht?"

    if language != "de":
        install_catalog(language, read_catalog(language))
    set_language(language)
    # Der Vorrat wird geleert, wie es der Erzeuger tut: Abbildungen werden
    # gemerkt, und ohne das kaeme sechsmal die deutsche Version zurueck.
    figures.forget()
    try:
        stale: list[str] = []
        for figure in figures.FIGURES:
            if figure.kind != "drawn":
                continue
            for scheme, suffix in (("light", ".svg"), ("dark", "-dark.svg")):
                drawn = figures.svg(figure.key, scheme)
                if drawn is None:
                    continue
                path = folder / f"{figure.key}{suffix}"
                if not path.is_file():
                    stale.append(f"{path.name} fehlt")
                    continue
                # Zeilenenden bleiben außen vor: ``write_text`` setzt auf
                # Windows CRLF, unter Linux LF, und das ist keine Aussage über
                # das Bild.
                if path.read_text(encoding="utf-8").replace("\r\n", "\n") != drawn.replace(
                    "\r\n", "\n"
                ):
                    stale.append(path.name)
    finally:
        set_language("de")
        figures.forget()

    assert not stale, (
        f"website/handbuch/{language}: diese Zeichnungen sind älter als der Code:\n"
        + "\n".join(stale)
        + "\n\nNeu erzeugen: .venv\\Scripts\\python.exe tools/make_manual.py"
    )


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


def test_no_two_chapters_share_a_title() -> None:
    """Zwei Kapitel desselben Namens sind im Verzeichnis eine Frage.

    Die geschriebene Seite über die erkannten Merkmale hieß zuerst
    „Merkmale" — und die Registerkategorie ``holes`` heißt ebenso, sie führt
    die Operationen dazu. Auf der erzeugten Seite standen damit zwei Einträge
    „Merkmale" untereinander, jeder mit eigenem Anker, und wer den falschen
    anklickte, landete in einer Operationsliste statt in der Erklärung.

    Geprüft wird über **alle** Seiten und nicht nur die geschriebenen: Der
    Zusammenstoß entsteht gerade zwischen den beiden Sorten, und ein
    Kategorietitel ändert sich, ohne dass jemand an das Handbuch denkt.
    """
    titles = [str(page.title) for page in manual.pages()]
    twice = sorted({title for title in titles if titles.count(title) > 1})

    assert not twice, "diese Kapitelnamen gibt es doppelt: " + ", ".join(twice)


def test_no_page_is_empty() -> None:
    for page in manual.pages():
        assert str(page.title).strip(), page.key
        assert len(str(page.body).strip()) > 80, page.key


def test_the_written_manual_does_not_require_cad_vocabulary() -> None:
    """Ein Einstieg für Anfänger erklärt die Wirkung statt den Rechenkern."""
    written = "\n".join(str(page.body) for page in manual.INTRODUCTION).casefold()

    for jargon in (
        "b-rep",
        "exakter körper",
        "exakte körper",
        "normaler körper",
        "zweiten rechenkern",
        "zweiten konstruktionskern",
    ):
        assert jargon not in written, jargon


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


def test_dash_bullets_become_a_list_too() -> None:
    """Die erzeugten Referenzlisten schreiben ``- ``, die Kapitel ``* `` —
    beide Schreibweisen müssen eine Liste werden. Vorher verklumpte die
    Fernsteuerungsseite zu einem Absatz, in dem zwanzig Operationen
    aneinanderhingen.
    """
    from app.core import markup

    html = markup.to_html("- `load` — Liest eine Datei.\n- `repair` — Schließt Löcher.")
    assert html.count("<li>") == 2
    assert "<p>" not in html
    assert "<p>- <code>" not in manual.as_html()


def test_a_drawn_figure_offers_its_dark_version() -> None:
    """Wo eine dunkle Version existiert, steht sie als zweite Quelle daneben.

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

    Beide Sprachen, und die zweite ist der Grund: die englische Version ist
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


def test_a_generated_chapter_shows_its_title_in_the_window_too(qt_app: QApplication) -> None:
    """Auch im Fenster steht über jeder Seite, welche es ist.

    Das Fenster entschied am Feld ``generated``, und die vier Wissensseiten
    sind erzeugt, bringen aber keine Überschrift mit: Wer „Wonach Solidon
    urteilt" anklickte, las als erste Zeile „Diese Regeln liegen dem Agenten
    bei jeder Anfrage vor" — ohne Titel, mitten im Satz. Beide Ausgaben nehmen
    die Regel jetzt aus ``manual.titled``.
    """
    window = ManualWindow()

    window.show_page("rules")
    shown = window.text.toPlainText()

    page = manual.find("rules")
    assert page is not None
    assert shown.startswith(str(page.title)), shown[:80]

    window.show_page("holes")
    reference = window.text.toPlainText()
    assert reference.startswith(str(CATEGORIES["holes"])), reference[:80]
    assert reference.count(str(CATEGORIES["holes"])) == 1, "und nicht zweimal"


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


#: Jede eingecheckte Handbuchseite, nicht nur die zwei mit Zahlenprüfung. Die
#: französische versprach drei Kapitel, die es auf ihr nicht gab, und die
#: italienische eines — monatelang, weil niemand über die deutsche und die
#: englische hinaussah.
MANUAL_PAGES = {
    "de": "handbuch.html",
    "en": "en/manual.html",
    "es": "es/manual.html",
    "fr": "fr/manual.html",
    "it": "it/manual.html",
    "pt": "pt/manual.html",
}


@pytest.mark.parametrize("language", sorted(MANUAL_PAGES))
def test_no_manual_page_promises_a_chapter_it_cannot_reach(language: str) -> None:
    """Jede Sprungmarke der eingecheckten Seite hat ihr Ziel.

    Der Test daneben prüft den Erzeuger; dieser prüft die Datei, die
    hochgeladen wird. Beides ist nötig: Eine Seite kann auch dadurch falsch
    werden, dass jemand den Erzeuger repariert und ``tools/make_manual.py``
    nicht laufen lässt.
    """
    import re

    page = Path(__file__).parent.parent / "website" / MANUAL_PAGES[language]
    assert page.is_file(), f"{MANUAL_PAGES[language]} fehlt — tools/make_manual.py läuft nicht?"
    html = page.read_text(encoding="utf-8")
    targets = set(re.findall(r'\bid="([^"]+)"', html))
    dangling = sorted({ref for ref in re.findall(r'href="#([^"]+)"', html) if ref not in targets})

    assert not dangling, (
        f"{MANUAL_PAGES[language]} verweist ins Leere: {dangling}\n\n"
        "Neu erzeugen: .venv\\Scripts\\python.exe tools/make_manual.py"
    )


def test_an_additional_language_needs_no_manual_generator_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Eine echte siebte Katalogdatei übersetzt auch den ganzen Webrahmen."""
    from app.core.bootstrap import load_operations
    from app.i18n import catalog as catalog_module
    from app.i18n import extract as extract_module
    from app.i18n import set_language
    from app.i18n.catalog import install_language, write_catalog
    from tools import make_manual

    monkeypatch.setattr(catalog_module, "LOCALES_DIR", tmp_path / "locales")
    messages = extract_module.message_ids()
    dutch = {key: "NL·" + key.split(chr(4), 1)[-1] for key in messages}
    write_catalog("nl", dutch)
    install_language("nl")
    set_language("nl")
    load_operations()
    make_manual.figures.forget()

    try:
        html = make_manual.page_html("nl", "../handbuch/nl")
    finally:
        set_language("de")

    assert '<html lang="nl">' in html
    assert '<summary aria-label="NL·Sprache wählen">NL</summary>' in html
    assert 'aria-label="NL·Menü"' in html
    assert 'href="/nl/features.html">NL·Funktionen</a>' in html
    assert 'href="/nl/ai-models.html">NL·KI-Modelle</a>' in html
    assert 'href="/nl/#pricing">NL·Preis</a>' in html
    assert '<a class="skip" href="#content">NL·Zum Inhalt springen</a>' in html
    assert '<h2 class="toc-title">NL·Inhalt</h2>' in html
    assert "NL·Referenz — jede Operation mit ihren Werten" in html
    assert "NL·Handbuch: 3D-Modelle für den Druck vorbereiten" in html
    assert "NL·Konstruieren, Erzeugen und Bearbeiten für den 3D-Druck" in html

    german_fallbacks = (
        'aria-label="Sprache wählen"',
        'aria-label="Menü"',
        ">Funktionen</a>",
        ">KI-Modelle</a>",
        ">Preis</a>",
        ">Zum Inhalt springen</a>",
        '<h2 class="toc-title">Inhalt</h2>',
    )
    assert not [text for text in german_fallbacks if text in html]

    assert make_manual.page_for("nl") == ("nl/manual.html", "../handbuch/nl")


def test_every_chapter_carries_its_own_heading() -> None:
    """Auch die erzeugten. Vier Kapitel hatten keine — und damit keinen Anker.

    Die vier Wissensseiten (Regeln, Profile, Fernsteuerwerkzeuge, Meldungen)
    fingen mitten im Satz an: Im Verzeichnis der Website standen sie als
    Kapitel 22 bis 25, im Text ging es hinter dem Wörterbuch ohne Überschrift
    weiter mit „Diese Regeln liegen dem Agenten bei jeder Anfrage vor". Wer
    einen der vier Einträge anklickte, blieb stehen, wo er war.
    """
    text = manual.as_markdown()
    ohne = [str(page.title) for page in manual.pages() if f"## {page.title}" not in text]
    assert not ohne, f"Kapitel ohne Überschrift: {ohne}"


@pytest.mark.parametrize("language", ["de", "en", "fr"])
def test_the_contents_lead_to_the_chapter_they_name(language: str) -> None:
    """Jeder Eintrag des Verzeichnisses trifft sein Kapitel — und zwar dessen
    Anfang.

    Geprüft wird die Reihenfolge und nicht nur das Vorhandensein, denn genau
    daran lag der Fehler: ``anchored`` nahm den ersten Treffer im ganzen Text,
    und das Kapitel *Die Werkzeuge der Fernsteuerung* gliedert seine Werkzeuge
    nach denselben fünfzehn Kategorien, die weiter unten die Referenzkapitel
    sind. Alle fünfzehn Referenzanker saßen damit in Kapitel 24; das
    Verzeichnis sprang ab Kapitel 26 mitten in die Fernsteuerung. Eine Prüfung
    auf „ist der Anker da" hätte das durchgelassen.

    Französisch steht dabei, weil dort der zweite Fehler saß: ``markup``
    maskiert den Apostroph zu ``&#x27;``, und die Suche nach dem rohen Titel
    fand „Ce qu'est Solidon" nie. Drei Kapitel ohne Anker, ohne eine rote
    Zeile.
    """
    import re

    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog
    from tools.make_manual import _classify, anchored, contents

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        html = anchored(_classify(manual.as_html()))
        wanted = re.findall(r'href="#(ref-[^"]+|[a-z-]+)"', contents(language))
        got = re.findall(r'<h[1-6] id="([^"]+)"', html)
    finally:
        set_language("de")

    assert wanted, "ein Verzeichnis ohne Einträge ist keines"
    assert got == wanted, (
        f"{language}: das Verzeichnis nennt {len(wanted)} Kapitel, die Anker im Text sind {got}"
    )


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
    nicht in die Anwendung kommen, ohne hier im Wortlaut aufzutauchen.

    Gezählt über **alle** Kernmodule, nicht nur das Stammmodul: Der Test lief
    über ``vars(errors)`` und die Erzeugung über eine handgepflegte
    Modulliste — zwei Mengen, beide unvollständig, und ``SendFailed`` („Die
    Rückmeldung ließ sich nicht senden", der wahrscheinlichste Fehler
    überhaupt) fehlte im ausgelieferten Handbuch, ohne dass es jemand sah.
    """
    import importlib
    import pkgutil

    import app.core
    from app.core import errors

    for info in pkgutil.walk_packages(app.core.__path__, prefix="app.core."):
        importlib.import_module(info.name)

    def walk(kind: type[errors.AppError]) -> list[type[errors.AppError]]:
        found: list[type[errors.AppError]] = []
        for child in kind.__subclasses__():
            # Nur die Anwendung selbst: Eine Testdatei, die sich im selben
            # Prozess eine Wegwerf-Ausnahme baut, gehört nicht ins Handbuch.
            if child.__module__.startswith("app.core."):
                found.append(child)
            found.extend(walk(child))
        return found

    hierarchy = walk(errors.AppError)
    assert any(kind.__name__ == "SendFailed" for kind in hierarchy), "die Probe aufs Exempel"
    body = manual.messages_text()
    for kind in hierarchy:
        assert str(kind.default_title) in body, kind.__name__
        for action in kind.default_suggestions:
            assert str(action.label) in body, action.id


def test_the_message_table_stands_on_its_own_imports() -> None:
    """Der Handbuchinhalt darf nicht an der Importreihenfolge hängen.

    Im Suite-Prozess ist längst alles importiert — der Test darüber lief
    grün, während im ausgelieferten Handbuch ``SendFailed`` fehlte: Die
    Erzeugung führte eine handgepflegte Modulliste, und ``app.core.support``
    stand nicht darauf. Ein eigener Prozess stellt die Frage so, wie
    ``tools/make_manual.py`` sie stellt.
    """
    import subprocess
    import sys
    from pathlib import Path

    probe = (
        # ``support`` wird erst NACH der Erzeugung importiert — sonst füllte
        # die Probe selbst die Hierarchie und misst sich selbst.
        "from app.core import manual\n"
        "body = manual.messages_text()\n"
        "from app.core import support\n"
        "title = str(support.SendFailed.default_title)\n"
        "assert title in body, 'SendFailed fehlt im Handbuch'\n"
    )
    done = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", probe],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[1],
        timeout=120,
    )
    assert done.returncode == 0, done.stdout + done.stderr


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

    Zwei gestellte Werte in ``tools/make_figures.py`` sind keine normalen
    Oberflächentexte: Körpername im Operationsdialog und Druckername in den
    Druckeinstellungen. (Die gestellten Befunde des Prüfberichts waren bis zum
    02.09.2026 der dritte; seither zeigt das Bild die echten Befunde des
    Passungsbeispiels, und die kommen aus dem Katalog.) Fehlt eine Sprache, fällt ein
    Bild still auf Deutsch zurück — und das sieht man dem Erzeugerlauf nicht an,
    man sieht es erst im fertigen Handbuch, wo ein deutscher Befund mitten im
    fremdsprachigen Text steht. Genau das ist im englischen Handbuch schon
    einmal passiert; der Kommentar an der Stelle erzählt davon.

    Seit eine weitere Sprache nur noch eine Datei in ``app/i18n/locales/``
    ist, kann es jederzeit wieder passieren, ohne dass jemand diese Datei
    öffnet. Deshalb steht der Riegel hier und nicht in der Erinnerung.
    """
    languages = set(available_languages())
    assert not sorted(languages - set(SAMPLE_OBJECT)), (
        f"ohne Körpernamen: {sorted(languages - set(SAMPLE_OBJECT))}"
    )
    assert not sorted(languages - set(SAMPLE_PRINTER)), (
        f"ohne Druckernamen: {sorted(languages - set(SAMPLE_PRINTER))}"
    )
    for language in languages:
        assert SAMPLE_OBJECT[language].strip(), language
        assert SAMPLE_PRINTER[language].strip(), language


def test_the_start_screen_button_opens_the_chapter_it_names(qt_app: object) -> None:
    """Der Knopf versprach „die ersten fünfzehn Minuten" und öffnete „Was Solidon ist".

    ``pages()`` liefert die Einführung zuerst, und das Handbuchfenster stellte
    auf Zeile null — den ersten von über vierzig Einträgen. Wer den einzigen
    Hilfe-Knopf des Startbildschirms drückt, musste das zugesagte Kapitel danach
    selbst suchen. ``ManualWindow.show_page`` konnte es seit je und wurde von
    keiner Stelle der Anwendung gerufen, nur vom Test.

    Geprüft wird über den **Klick**, nicht über die Methode: Die Verdrahtung ist
    die Aussage. Und der Knopftext wird gegen den Seitentitel gehalten — wer das
    eine ändert und das andere vergisst, hat wieder ein Versprechen ohne Deckung.
    """
    from app.core import manual as manual_module
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        window.start_screen.manual_button.click()
        opened = window._manual
        assert opened is not None, "der Knopf öffnete kein Handbuch"

        row = opened.contents.currentRow()
        assert row >= 0
        page = opened._visible[row]
        assert page.key == manual_module.FIRST_MINUTES, (
            f"geoeffnet wurde {page.title} statt des zugesagten Kapitels"
        )
        # Ohne Rücksicht auf die Großschreibung: Der Knopf schreibt „… die
        # ersten fünfzehn Minuten" mitten im Satz, die Seite „Die ersten …".
        #
        # **Und seit B27 im Hinweis statt auf dem Knopf**: Der ganze Satz
        # machte ihn mehr als doppelt so breit wie seine Nachbarn, er heißt
        # jetzt „Handbuch". Die Zusage hat damit ihren Ort gewechselt, nicht
        # ihren Inhalt — wohin er führt, muss er weiterhin sagen.
        knopf = window.start_screen.manual_button
        sagt = f"{knopf.text()} {knopf.toolTip()}".casefold()
        assert str(page.title).casefold() in sagt, (
            f"der Knopf sagt {knopf.text()!r} mit Hinweis {knopf.toolTip()!r}, "
            f"die Seite heisst {page.title}"
        )
    finally:
        window.close()
        window.deleteLater()


def test_a_figure_grows_back_when_the_column_does(qt_app: QApplication) -> None:
    """Eine Abbildung, die für eine schmale Spalte verkleinert wurde, darf
    nicht klein bleiben, wenn das Fenster aufgeht (§19.2).

    Qt behält, was ``loadResource`` geliefert hat, im Dokument und fragt nie
    wieder — ohne das Nachlegen in ``PageView._refit`` stand der
    Startbildschirm bei 400 Punkten Spaltenbreite auf 374 und blieb dort, auch
    bei 1600. Gemessen wird am Bild, das das **Dokument** hält, denn das ist
    das, was gezeichnet wird.
    """

    window = ManualWindow()
    try:
        window.resize(700, 900)
        window.show()
        qt_app.processEvents()

        view = window.text
        opened = next(
            (row for row in range(window.contents.count()) if _figures_on(window, row)), None
        )
        assert opened is not None, "keine Seite mit einer Abbildung gefunden"

        narrow = dict(_document_widths(view))
        assert narrow, "die Seite hat keine Abbildung im Dokument"

        window.resize(1900, 900)
        qt_app.processEvents()
        # Der Zeitgeber bündelt den Zug am Fensterrand; hier wird er direkt
        # ausgelöst, statt im Test zu warten.
        view._refit()
        qt_app.processEvents()

        wide = dict(_document_widths(view))
        grown = [key for key, width in wide.items() if width > narrow.get(key, 0)]
        assert grown, (
            "keine Abbildung ist mitgewachsen — "
            f"schmal {sorted(narrow.items())}, breit {sorted(wide.items())}"
        )
        assert all(width <= view._column() for width in wide.values()), (
            f"eine Abbildung ist breiter als die Spalte ({view._column()}): {sorted(wide.items())}"
        )
    finally:
        window.close()
        window.deleteLater()


def _figures_on(window: ManualWindow, row: int) -> bool:
    """Die Zeile aufschlagen und sagen, ob sie nach Abbildungen gefragt hat."""
    window.contents.setCurrentRow(row)
    QApplication.processEvents()
    return bool(window.text._asked)


def _document_widths(view: object) -> list[tuple[str, int]]:
    """Was das Dokument je Abbildung wirklich hält, in logischen Punkten."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage, QTextDocument

    document = view.document()  # type: ignore[attr-defined]
    found = []
    for key in sorted(view._asked):  # type: ignore[attr-defined]
        held = document.resource(QTextDocument.ResourceType.ImageResource, QUrl(f"figure:{key}"))
        if isinstance(held, QImage) and not held.isNull():
            found.append((key, round(held.width() / (held.devicePixelRatio() or 1.0))))
    return found


def test_the_model_page_names_the_models_solidon_currently_offers() -> None:
    """Sprach- und Erzeugermodelle stehen aus ihren jeweiligen Quellen da."""
    from app.core.backends.llm import OLLAMA_SUGGESTIONS

    seite = manual.models_text()

    for name, _gigabytes, _note in OLLAMA_SUGGESTIONS:
        assert name in seite, f"das Sprachmodell {name} fehlt"
    for model in ("TripoSG", "BiRefNet", "SDXL"):
        assert model in seite, f"das Erzeugungsmodell {model} fehlt"
    assert "Hugging Face" in seite
    assert "Hunyuan3D" not in seite


@pytest.mark.rendered
@pytest.mark.parametrize("language", ("de", "en", "es", "fr", "it", "pt"))
def test_every_manual_language_describes_the_released_generator_chain(language: str) -> None:
    """Quellhandbuch und veröffentlichte Seite nennen denselben lokalen Weg."""
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        relevant = [page for page in manual.pages() if page.key in {"generating", "extras"}]
        source = "\n".join(str(page.body) for page in relevant) + manual.models_text()
        published = WEBSITE_PAGES[language].read_text(encoding="utf-8")
    finally:
        set_language("de")

    for text in (source, published):
        assert "TripoSG" in text, f"{language}: TripoSG fehlt"
        assert "ComfyUI" in text, f"{language}: ComfyUI fehlt"
        assert "Hunyuan3D" not in text, f"{language}: ungeprüfte Alternative veröffentlicht"


@pytest.mark.parametrize(
    ("language", "page_title", "transfer_denial"),
    [
        (
            "de",
            "Bausteindateien austauschen",
            "Weder die Datei noch Autor, Lizenz oder Herkunft werden an RS Digital übertragen.",
        ),
        (
            "en",
            "Exchange part files",
            "Neither the file nor its author, licence or origin is sent to RS Digital.",
        ),
        (
            "es",
            "Intercambiar archivos de bloques",
            "Ni el archivo ni su autor, licencia o procedencia se envían a RS Digital.",
        ),
        (
            "fr",
            "Échanger des fichiers de blocs",
            "Ni le fichier, ni l’auteur, ni la licence, ni la provenance "
            "ne sont transmis à RS Digital.",
        ),
        (
            "it",
            "Scambiare file di blocchi",
            "Né il file né autore, licenza o provenienza vengono trasmessi a RS Digital.",
        ),
        (
            "pt",
            "Trocar ficheiros de blocos",
            "Nem o ficheiro nem o autor, a licença ou a origem são transmitidos à RS Digital.",
        ),
    ],
)
@pytest.mark.rendered
def test_the_exchange_manual_describes_only_local_files(
    language: str, page_title: str, transfer_denial: str
) -> None:
    """Das Handbuch beschreibt nur den lokalen Dateiaustausch mit Herkunft."""
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        exchange = next(page for page in manual.pages() if page.key == "exchange")
        body = str(exchange.body)
        html = WEBSITE_PAGES[language].read_text(encoding="utf-8")
    finally:
        set_language("de")

    assert page_title.casefold() in html.casefold()
    for text in (body, html):
        assert transfer_denial.casefold() in text.casefold()
        assert "CC BY" in text
        assert "CC BY-SA" in text
        assert "solidon3d.de/boerse" not in text
        assert "/exchange.html" not in text


def test_the_model_page_comes_from_the_code_and_not_from_a_second_list() -> None:
    """Eine zweite Liste veraltet — dieselbe Zusage wie bei Regeln und Profilen.

    Geprüft wird an der **Wirkung** und nicht am Quelltext: Wer eine Zeile in
    ``OLLAMA_SUGGESTIONS`` ändert, muss sie auf der Seite wiederfinden. Ein
    Test, der nur nach dem Namen der Konstante sucht, bliebe grün, wenn jemand
    die Tabelle danebenschriebe.
    """
    from app.core.backends.llm import DEFAULT_OLLAMA_MODEL, OLLAMA_SUGGESTIONS

    seite = manual.models_text()

    # Die Bewertung steht neben dem Namen, nicht nur der Name.
    for name, _gigabytes, note in OLLAMA_SUGGESTIONS:
        assert str(note) in seite, f"die Messung zu {name}"

    # Die Vorgabe ist als solche erkennbar.
    assert f"**{DEFAULT_OLLAMA_MODEL}**" in seite, "die Vorgabe steht hervorgehoben"


@pytest.mark.rendered
@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_checked_in_manual_carries_the_current_model_measurements(language: str) -> None:
    """Die ausgelieferte Seite darf nicht hinter ``OLLAMA_SUGGESTIONS`` stehen.

    Der Generator war korrekt, aber die sechs eingecheckten Seiten nannten
    weiterhin vier von fünf Aufrufen und rund fünfzehn Sekunden. Geprüft wird
    deshalb der veröffentlichte HTML-Text in jeder Sprache, nicht nur die
    Python-Quelle, aus der er beim nächsten Lauf entstehen würde.
    """
    from app.core.backends.llm import OLLAMA_SUGGESTIONS
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    if language != "de":
        install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        text = unescape(WEBSITE_PAGES[language].read_text(encoding="utf-8"))
        for name, _gigabytes, note in OLLAMA_SUGGESTIONS:
            assert name in text, f"{language}: {name} fehlt in der ausgelieferten Seite"
            assert str(note) in text, f"{language}: die aktuelle Messung zu {name} fehlt"
    finally:
        set_language("de")


def test_the_model_page_is_a_chapter_of_its_own() -> None:
    """Sie muss auffindbar sein — über das Verzeichnis, nicht über die Suche."""
    seiten = {page.key: page for page in manual.pages()}

    assert "models" in seiten, "die Seite steht im Handbuch"
    page = seiten["models"]
    assert page.generated, "erzeugt, nicht geschrieben"
    assert str(page.title) in str(page.body), "die Überschrift trägt den Anker"


def test_the_text_column_keeps_a_readable_line_length(qt_app: QApplication) -> None:
    """Achtundneunzig Zeichen je Zeile sind keine Textspalte (Befund B34).

    Der Fließtext lief über die ganze Fensterbreite: gemessen 674 Punkte für
    rund 96 Zeichen, wo Typografie 60 bis 80 nennt. Wer eine Zeile zu Ende
    liest, findet den Anfang der nächsten nicht mehr — das ist der Grund für
    die Regel, nicht Geschmack.

    Der Rand wächst mit dem Fenster: Auf einem breiten Bildschirm bleibt die
    Spalte lesbar, auf einem schmalen nimmt sie sich alles, was da ist.
    """
    from PySide6.QtWidgets import QTextBrowser

    from app.ui.manual_window import ManualWindow

    fenster = ManualWindow()
    fenster.resize(1600, 900)
    fenster.show()
    qt_app.processEvents()

    ansicht = fenster.findChild(QTextBrowser)
    assert ansicht is not None
    # Der Sichtbereich, nicht die Dokumentbreite: Was der Kunde liest, ist
    # das, was zwischen den Rändern steht.
    breite = ansicht.viewport().width()
    zeichen = ansicht.fontMetrics().horizontalAdvance("n")
    je_zeile = breite / max(zeichen, 1)

    assert je_zeile <= 85, (
        f"{je_zeile:.0f} Zeichen je Zeile bei {ansicht.viewport().width()} Punkten"
    )
    fenster.close()


def test_a_contents_entry_that_is_cut_says_so(qt_app: QApplication) -> None:
    """Ein abgeschnittener Eintrag ohne Auslassungszeichen sieht aus wie ein
    kurzer Titel (Befund B34).

    Im Verzeichnis stand „Ausprobieren statt raten: Varianten und Kalibriere"
    — mitten im Wort zu Ende, ohne Zeichen dafür. Wer das liest, hält es für
    den ganzen Namen; die drei Punkte sind der Unterschied zwischen „zu Ende"
    und „geht weiter".
    """
    from PySide6.QtCore import Qt as QtCore_Qt
    from PySide6.QtWidgets import QListWidget

    from app.ui.manual_window import ManualWindow

    fenster = ManualWindow()
    fenster.show()
    qt_app.processEvents()

    liste = fenster.findChild(QListWidget)
    assert liste is not None and liste.count() > 0

    assert liste.textElideMode() == QtCore_Qt.TextElideMode.ElideRight
    lang = max(range(liste.count()), key=lambda i: len(liste.item(i).text()))
    eintrag = liste.item(lang)
    assert eintrag.toolTip() == eintrag.text(), "der volle Name steht im Hinweis"
    fenster.close()
