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

import re
import sys
from collections.abc import Callable
from html import escape, unescape
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from app.branding import APP_VERSION
from app.core import figures, manual, markup
from app.core.bootstrap import load_operations
from app.core.registry.registry import CATEGORIES, REGISTRY
from app.i18n import tr
from app.i18n.catalog import available_languages
from app.ui.manual_window import ManualWindow
from tools.make_figures import SAMPLE_OBJECT, SAMPLE_PRINTER, figure_sketch

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
    # Die Seite „Was Solidon ist", bis zur nächsten Kapitelüberschrift — seit
    # „Wo fange ich an?" vorn steht, folgt ihr nicht mehr ``start``.
    intro = html.split('<h3 id="what">', 1)[1].split("<h3 ", 1)[0]
    present = [marker for marker in PUBLIC_WARNING_MARKERS if marker in intro.casefold()]
    assert not present, f"{language}: rechtliche Warnliste im Handbuch: {present}"


@pytest.mark.rendered
@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_checked_in_manual_carries_the_current_version(language: str) -> None:
    """Die nie veröffentlichte Zwischenfassung darf nicht auf dem Umschlag bleiben."""
    html = WEBSITE_PAGES[language].read_text(encoding="utf-8")
    cover = html.split("</section>", 1)[0]

    assert APP_VERSION in cover, f"{language}: Umschlag nicht auf {APP_VERSION}"


@pytest.mark.rendered
@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_checked_in_pdf_carries_the_current_version(language: str) -> None:
    """Website und PDF tragen denselben Versionsstand auf ihrer Titelseite.

    **Der dreizehnte, und er hat die kuratierte Liste widerlegt.** Er las als
    einziger aus ``Releases/`` statt aus ``website/`` und fiel deshalb durch
    jedes Muster, mit dem ich die zwölf anderen gesucht hatte. Aufgefallen ist
    er am 04.09.2026 vor dem Tag zu 0.3.2: Achtzehn Läufe von ``test_manual``
    waren rot, zwölf davon diese sechs Sprachen — und mit ``-m "not rendered"``
    blieben sie rot, wären in der CI also angeschlagen. Genau das sollte
    Roberts Entscheidung verhindern.
    """
    from pypdf import PdfReader

    path = RELEASES / f"Solidon3D-Handbuch-{language}.pdf"
    assert path.is_file(), f"{path.name} fehlt — tools/make_manual.py ausführen"
    cover = PdfReader(path).pages[0].extract_text() or ""

    assert APP_VERSION in cover, f"{path.name}: Titelseite nicht auf {APP_VERSION}"


@pytest.mark.rendered
@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_the_pdf_links_nowhere_outside_itself_but_the_website(language: str) -> None:
    """Jedes Bildschirmfoto im PDF von 0.5.0 verwies auf ``file:///F:/3D%20Druck/…``.

    Auf der Website öffnet ein Tippen das Bild in voller Größe; im Druck wurde
    aus demselben Verweis der Pfad des Bau-Rechners — neun je Sprache, beim
    Kunden ein Klick ins Leere, der einen fremden Pfad zeigt
    (``konzepte/nachweise-handbuch-2026-09/findbarkeit.md``, Teil 3). Erlaubt
    sind Sprünge im Dokument und Verweise ins Netz.
    """
    from pypdf import PdfReader

    path = RELEASES / f"Solidon3D-Handbuch-{language}.pdf"
    assert path.is_file(), f"{path.name} fehlt — tools/make_manual.py ausführen"
    local: list[str] = []
    for page in PdfReader(path).pages:
        for reference in page.get("/Annots") or []:
            action = reference.get_object().get("/A") or {}
            target = str(action.get("/URI", ""))
            if target and not target.startswith(("https://", "http://", "mailto:")):
                local.append(target)
    assert not local, (
        f"{path.name}: {len(local)} Verweise aus dem Dokument hinaus, z. B. {local[0]}"
    )


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
    assert "TRELLIS.2" in generating and "ComfyUI" in generating
    assert "TripoSG" not in generating
    for licence in ("MIT", "DINOv3-Lizenz", "Apache-2.0"):
        assert licence in generating, f"die Lizenz {licence} fehlt"
    assert "Reparaturkette läuft ohne Nachfrage" in generating

    extras = pages["extras"]
    assert "Modelle einrichten" in extras
    assert "Version" in extras and "0.35" in extras
    assert "ComfyUI einmal neu starten" in extras
    assert "drei Minuten auf der Grafikkarte" not in extras


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
    from app.core.registry.surfaces import part_placement_params
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    html = WEBSITE_PAGES[language].read_text(encoding="utf-8")
    # Übersetzt wie in der Anwendung, mit Kontext: „Bereich“ heißt als
    # Musterfeld anders als ohne, „Verschluss“ steht nur mit Kontext im Katalog.
    install_catalog(language, read_catalog(language))
    set_language(language)
    missing: list[str] = []
    try:
        _collect_missing_reference(html, part_placement_params, missing)
    finally:
        set_language("de")

    assert not missing, (
        f"{WEBSITE_PAGES[language].name} hat eine veraltete Referenz:\n"
        + "\n".join(missing)
        + "\n\nNeu erzeugen: .venv\\Scripts\\python.exe tools/make_manual.py"
    )


def _collect_missing_reference(
    html: str, part_placement_params: Callable[[Any], frozenset[str]], missing: list[str]
) -> None:
    """Sammelt Operationen und Felder, die in der erzeugten Referenz der Seite fehlen."""
    for spec in REGISTRY.all():
        # Die unsichtbare Kennung ordnet auch gleichlautende Werkzeugtitel zu.
        marker = f'<h4 data-operation="{spec.name}"'
        start = html.find(marker)
        if start < 0:
            missing.append(spec.name)
            continue
        end = html.find("<h4", start + len(marker))
        section = html[start : end if end >= 0 else len(html)]
        # Dieselbe Auswahl wie ``documentation`` und ``parameter_table``:
        # Interne Felder (Migrationswerte, Flächenbezug der Platzierung) sind
        # keine Eingaben und stehen nirgends; die Ortsfelder der Bausteine
        # stehen einmal am Kategoriekopf.
        parameters = tuple(entry for entry in spec.params.spec() if not entry.internal)
        if spec.category == "parts":
            placement = part_placement_params(spec)
            parameters = tuple(entry for entry in parameters if entry.name not in placement)
        for entry in parameters:
            if f"<td>{escape(str(entry.title))}</td>" not in section:
                missing.append(f"{spec.name}.{entry.name}")


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
    from dataclasses import replace

    from app.core.registry import REGISTRY
    from app.core.registry.params import condition_text
    from app.core.registry.surfaces import choice_label
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    page = WEBSITE_PAGES[language]
    assert page.is_file(), f"{page.name} fehlt — tools/make_manual.py läuft nicht?"

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        html = page.read_text(encoding="utf-8")
        visible = re.sub(r"<[^>]+>", "", html)
        missing: list[str] = []
        for spec in REGISTRY.all():
            if escape(str(spec.title)) not in html:
                missing.append(f"{spec.name}: Titel")
            # Der Vorbehalt selbst und nicht die ganze Zeile: Im Handbuch
            # steht sein Vorwort halbfett, also als ``<strong>`` und nicht
            # mit den Sternchen, die ``caveat_line`` setzt. Verglichen wird der
            # sichtbare Text — eine Hervorhebung darin steht als ``<em>``.
            if spec.caveat and escape(markup.plain(str(spec.caveat))) not in visible:
                missing.append(f"{spec.name}: Vorbehalt")
            schema = tuple(
                replace(
                    entry,
                    depends_on=(
                        entry.depends_on[0],
                        tuple(
                            choice_label(value) if isinstance(value, str) else value
                            for value in entry.depends_on[1]
                        ),
                    ),
                )
                if entry.depends_on
                else entry
                for entry in spec.params.spec()
            )
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


@pytest.mark.rendered
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
    Datei. Gerendertes und Bildschirmfotos hängen am Renderer, an Schriften
    und am Bildschirm — die zu vergleichen hieße, die Maschine zu prüfen und
    nicht die Anwendung.
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

    assert chapters - knowledge == {manual.reference_key(name) for name in REGISTRY.by_category()}


def test_every_operation_appears_by_name() -> None:
    """Jede Operation erscheint mit dem Kundentitel, ohne interne Befehlsnamen."""
    text = manual.as_markdown()

    for spec in REGISTRY.all():
        assert f"(`{spec.name}`)" not in text, spec.name
        assert str(spec.title) in text, spec.name


def test_every_operation_names_where_it_is_found() -> None:
    """Von 142 Referenzeinträgen nannten zwei ihren Ort in der Oberfläche.

    Wer in der Referenz liest, sucht als Nächstes den Knopf
    (``konzepte/nachweise-handbuch-2026-09/findbarkeit.md``, Teil 4). Der Ort
    kommt aus ``menu_path``, derselben Auskunft, die der Chat bekommt.
    """
    from app.core.registry.surfaces import documentation, menu_path

    text = documentation()
    for spec in REGISTRY.all():
        entry = text.split(f"(`{spec.name}`)", 1)[1].split("\n### ", 1)[0]
        assert tr("**Ort:** {path}", path=menu_path(spec)) in entry, spec.name


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


def test_no_two_pages_share_a_key() -> None:
    """Ein Schlüssel, eine Seite: Wer beim Schlüssel sucht, bekommt die erste.

    „Die Bausteine“ und das Kapitel „Bausteine“ hießen beide ``parts``,
    „Zeichnen“ und „Skizze“ beide ``sketch``. F1 in *Mutternfalle* und in
    *Tasche schneiden* schlug deshalb die Erklärseite auf, oben, statt den
    Eintrag in der Referenz — bei 53 von 142 Operationen, in jeder Sprache.
    """
    keys = [page.key for page in manual.pages()]
    assert keys, "keine Seiten gelesen — dann prüft das nichts"
    twice = sorted({key for key in keys if keys.count(key) > 1})
    assert not twice, f"doppelt vergeben: {twice}"


def test_a_chapter_can_be_asked_for_on_its_own() -> None:
    holes = manual.find(manual.reference_key("holes"))

    assert holes is not None
    assert str(CATEGORIES["holes"]) in str(holes.body)
    assert str(REGISTRY.get("drill_hole").title) in str(holes.body)


def test_f1_on_a_taught_operation_opens_its_guide() -> None:
    """F1 im Dialog *Bohrung setzen* öffnet die Anleitung, nicht die Referenz
    (Konzept Handbuch §7) — in beiden Rechenkernen, der Dialog ist derselbe."""
    assert manual.help_for("drill_hole") == ("drill-a-hole", "")
    assert manual.help_for("drill_brep_hole") == ("drill-a-hole", "")


def test_f1_on_every_other_operation_finds_its_entry_in_the_reference() -> None:
    """Ohne Anleitung schlägt F1 den Eintrag der Operation in der Referenz auf,
    an seiner Überschrift — für jede Operation im Register, in jeder Kategorie.

    Das Ziel trägt die Operationskennung unsichtbar: Gleich benannte
    Operationen bleiben verschiedene Einträge.
    """
    from app.core import guides, markup

    taught = {name for guide in guides.GUIDES for name in guide.teaches}
    # Die erste Seite je Schlüssel, wie das Handbuchfenster sie wählt.
    pages: dict[str, str] = {}
    for page in manual.pages():
        pages.setdefault(page.key, markup.plain(page.text()))
    lost = []
    for spec in REGISTRY.all():
        if spec.name in taught:
            continue
        key, spot = manual.help_for(spec.name)
        anchors = dict(manual.reference_anchors(key))
        if (
            key not in pages
            or spot != f"#{manual.operation_anchor(spec.name)}"
            or anchors.get(spot[1:]) != str(spec.title)
            or f"### {spec.title}" not in pages[key]
        ):
            lost.append(f"{spec.name} → {key}: {spot!r}")
    assert not lost, "\n".join(lost)


@pytest.mark.parametrize("language", available_languages())
def test_reference_anchors_follow_the_headings_and_keep_duplicate_titles_distinct(
    language: str,
) -> None:
    """Anker und sichtbare Überschriften haben in jeder Sprache dieselbe Ordnung."""
    from app.i18n import get_language, set_language

    previous = get_language()
    try:
        set_language(language)
        seen: set[str] = set()
        for page in manual.pages():
            anchors = manual.reference_anchors(page.key)
            if not anchors:
                continue
            headings = re.findall(r"^### (.+)$", str(page.body), re.MULTILINE)
            assert [title for _anchor, title in anchors] == headings, page.key
            for anchor, _title in anchors:
                assert anchor not in seen, anchor
                seen.add(anchor)
        assert len(seen) == len(REGISTRY.all())
        for first, second in (
            ("create_brep_cone", "create_cone"),
            ("create_organizer_rim", "insert_organizer_rim"),
        ):
            assert str(REGISTRY.get(first).title) == str(REGISTRY.get(second).title)
            assert manual.help_for(first) != manual.help_for(second)
    finally:
        set_language(previous)


def test_only_reference_pages_expose_operation_anchors() -> None:
    """Eine Erklärseite gleichen Namens oder ein fremder Schlüssel hat kein F1-Ziel."""
    assert manual.reference_anchors("parts") == ()
    assert manual.reference_anchors("ref-unknown") == ()
    assert manual.operation_anchor("create_cone") == "operation-create_cone"


def test_the_reference_writes_numbers_the_way_the_language_does() -> None:
    """Vorgabe und Bereich stehen im Trennzeichen der jeweiligen Sprache.

    Die erzeugte Hälfte lieferte ``0.2 … 200`` und ``8.4`` in ein deutsches
    Handbuch — neben eine Anwendung, die im selben Bild ``2,40 mm`` anzeigt.
    Der Leser tippt danach ein, was er gelesen hat, und trifft ein Feld, das
    das Komma erwartet.
    """
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    german = manual.find(manual.reference_key("holes"))
    assert german is not None
    assert "0,2 … 200" in str(german.body)
    assert "0.2 … 200" not in str(german.body)

    install_catalog("en", read_catalog("en"))
    set_language("en")
    try:
        english = manual.find(manual.reference_key("holes"))
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


def test_numbered_lines_become_a_numbered_list() -> None:
    """Die drei Schritte der Seite über zusätzliche Programme klebten auf der
    Website zu einem Absatz zusammen; das Handbuchfenster, das Qts Markdown
    liest, zeigte sie als Liste. Die Legenden der Bildanleitungen brauchen sie
    auch: Ihre Nummern sind die Nummern im Bild.
    """
    from app.core import markup

    html = markup.to_html("1. **Läuft es?** Ja.\n2. Ein Modell holen.\n\nDanach.")
    assert html.startswith("<ol><li><strong>Läuft es?</strong> Ja.</li><li>")
    assert html.count("<li>") == 2
    assert "<p>Danach.</p>" in html
    assert '<ol start="3">' in markup.to_html("3. Weiter.")
    mixed = markup.to_html("- Punkt\n1. Schritt")
    assert mixed == "<ul><li>Punkt</li></ul>\n<ol><li>Schritt</li></ol>"
    assert "<p>1. " not in manual.as_html()


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


def test_a_link_to_another_page_leads_where_the_output_says_and_else_stays_text() -> None:
    """``[Text](manual:schlüssel)``: Die Ausgabe sagt, wohin; ohne Ziel bleibt der Text.

    Ein Verweis im Code bleibt Code, und Code im Verweis bleibt Code — die
    Platzhalter beider stehen ineinander.
    """
    text = "Siehe [Ein **Loch** bohren](manual:drill-a-hole) und `[x](manual:y)`."
    assert markup.to_html(text, link=lambda key: f"#{key}") == (
        '<p>Siehe <a href="#drill-a-hole">Ein <strong>Loch</strong> bohren</a> '
        "und <code>[x](manual:y)</code>.</p>"
    )
    assert markup.to_html(text) == (
        "<p>Siehe Ein <strong>Loch</strong> bohren und <code>[x](manual:y)</code>.</p>"
    )
    assert markup.to_html("[Knopf `OK`](manual:x)", link=lambda key: "#x") == (
        '<p><a href="#x">Knopf <code>OK</code></a></p>'
    )
    assert markup.to_html("[a <b>](manual:z)", link=lambda key: None) == "<p>a &lt;b&gt;</p>"
    assert markup.unlinked("Erst [das](manual:what), dann das.") == "Erst das, dann das."


def test_the_alt_text_of_a_picture_carries_no_markup() -> None:
    """Ein Schrittsatz steht als Alt-Text am Bild; Sternchen und Verweisklammern
    darin läse ein Bildschirmleser vor."""
    text = "Klicken Sie auf *Bohrung setzen*, **dann** `Esc`, wie in [Ein Loch bohren](manual:x)."
    assert markup.plain(text) == "Klicken Sie auf Bohrung setzen, dann Esc, wie in Ein Loch bohren."
    html = markup.to_html(
        "![](figure:probe)", lambda key: markup.FigureSource("probe.webp", text, "")
    )
    assert 'alt="Klicken Sie auf Bohrung setzen, dann Esc, wie in Ein Loch bohren."' in html


@pytest.mark.parametrize("language", sorted(WEBSITE_PAGES))
def test_every_link_between_pages_leads_to_a_page(language: str) -> None:
    """Ein Verweis auf eine Seite, die es nicht gibt, führte ins Leere.

    Im Fenster wäre der Klick ohne Wirkung, auf der Website ein toter Anker,
    und bemerkt hätte es nur, wer genau diesen Verweis anklickt. Geprüft wird
    in jeder Sprache, denn der Verweis steht im übersetzten Text.
    """
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        written = manual.pages()
        keys = {page.key for page in written}
        dangling = [
            f"{page.key} → {target}"
            for page in written
            for label, target in markup.MANUAL_LINK.findall(page.text())
            if target not in keys or not label.strip()
        ]
    finally:
        set_language("de")

    assert not dangling, f"{language}: Verweise ins Leere:\n" + "\n".join(dangling)


@pytest.mark.parametrize("language", sorted(set(WEBSITE_PAGES) - {"de"}))
def test_a_translation_keeps_every_link_of_its_page(language: str) -> None:
    """Die Übersetzung übersetzt den Text eines Verweises, nie sein Ziel, und lässt keinen aus."""
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    def targets() -> dict[str, list[str]]:
        return {
            page.key: sorted(target for _label, target in markup.MANUAL_LINK.findall(page.text()))
            for page in manual.pages()
            if not page.generated
        }

    source = targets()
    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        translated = targets()
    finally:
        set_language("de")

    differing = [key for key in source if translated.get(key) != source[key]]
    assert not differing, f"{language}: andere Verweise als im Deutschen auf {differing}"


#: Ein Weg im Text einer Seite: *Datei → Exportieren*, **Hilfe → Über Solidon**.
#: Ein Weg ist ausgezeichnet wie jedes Bedienelement; ein Pfeil außerhalb einer
#: Auszeichnung ist einer, den der Abgleich nicht sähe, und zählt selbst als Fund.
MENU_WAY = re.compile(r"\*{1,2}([^*\n]*→[^*\n]*)\*{1,2}")


def _plain(text: str) -> str:
    """Ein Menütext, wie ihn ein Satz schreibt: ohne Auslassung und Satzpunkt."""
    return text.replace("…", "").strip(" .:")


def _ways_of_the_written_pages() -> dict[str, tuple[list[list[str]], int]]:
    """Je geschriebene Seite ihre Wege, Glied für Glied, und die Zahl ihrer Pfeile.

    In der eingestellten Sprache. Die Bildanleitungen stehen nicht dabei:
    Ihre Wege prüft ``test_guides`` an den Markierungen der Schritte.
    """
    from app.core import guides

    taught = {guide.key for guide in guides.GUIDES}
    found: dict[str, tuple[list[list[str]], int]] = {}
    for page in manual.pages():
        if page.generated or page.key in taught:
            continue
        text = page.text()
        ways = [[_plain(part) for part in way.split("→")] for way in MENU_WAY.findall(text)]
        found[page.key] = (ways, text.count("→"))
    return found


def _menus_of_the_bar() -> set[str]:
    """Die Menüs der Leiste, in der eingestellten Sprache.

    Die festen vier baut das Hauptfenster mit ``self._menu(tr(…))``; gelesen
    wird der Quelltext, denn ein Fenster zu bauen ist ein Fenstertest und läuft
    nur beim Release. Dazu die Gruppen des Registers, die es in die Leiste
    schaffen. Was darunter steht, weiß erst das gebaute Fenster:
    ``test_wording.test_every_menu_path_in_the_texts_exists_in_the_menu_bar``.
    """
    import ast

    from app.core.registry.registry import group_title
    from app.core.registry.surfaces import in_the_menu_bar

    source = Path(__file__).parent.parent / "app" / "ui" / "main_window.py"
    fixed = [
        node.args[0].args[0].value
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_menu"
        and node.args
        and isinstance(node.args[0], ast.Call)
        and isinstance(node.args[0].func, ast.Name)
        and node.args[0].func.id == "tr"
        and isinstance(node.args[0].args[0], ast.Constant)
    ]
    assert len(fixed) >= 4, f"nur {fixed} als Menü gefunden — das Muster greift nicht mehr"
    grouped = {
        _plain(group_title(category)) for category in CATEGORIES if in_the_menu_bar(category)
    }
    return {_plain(tr(title)) for title in fixed} | grouped


@pytest.mark.parametrize("language", available_languages())
def test_a_way_in_a_written_page_is_the_one_the_interface_shows(language: str) -> None:
    """Jeder Weg *A → B* einer geschriebenen Seite besteht aus Texten der Oberfläche.

    Konzept Handbuch §6, HB-11. Ein umbenannter Menüeintrag machte das Handbuch
    bisher still falsch, und in fünf Sprachen merkte es niemand: Die Prüfung
    am gebauten Fenster läuft nur beim Release und nur auf Deutsch.

    Geprüft wird je Sprache, dass der Weg an einem Menü der Leiste beginnt,
    dass jedes Glied ein Text der Oberfläche ist und dass die Übersetzung
    Glied für Glied so heißt, wie der Katalog Menü und Eintrag übersetzt — und
    endet der Weg auf einer Operation, dass er ihr Menüweg ist
    (``registry.surfaces.menu_path``). Ob ein Eintrag, der keine Operation
    ist, unter genau diesem Menü steht, weiß nur das Fenster; das prüft
    ``test_wording`` beim Release am Deutschen, dem jede Übersetzung hier
    Glied für Glied folgen muss.
    """
    from app.core.registry.surfaces import menu_path
    from app.i18n import SOURCE_LANGUAGE, install_catalog, set_language
    from app.i18n.catalog import read_catalog

    reference = next(other for other in available_languages() if other != SOURCE_LANGUAGE)
    known = set(read_catalog(reference))
    catalog = {key: key for key in known} if language == SOURCE_LANGUAGE else read_catalog(language)
    said: dict[str, set[str]] = {}
    for key, value in catalog.items():
        said.setdefault(_plain(key), set()).add(_plain(value))

    source = _ways_of_the_written_pages()
    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        translated = _ways_of_the_written_pages()
        bar = _menus_of_the_bar()
        operations = {_plain(str(spec.title)): spec for spec in REGISTRY.all()}
        findings: list[str] = []
        for key, (ways, arrows) in translated.items():
            if arrows != sum(len(way) - 1 for way in ways):
                findings.append(f"{key}: ein Pfeil steht außerhalb eines ausgezeichneten Wegs")
            german = source[key][0]
            if len(ways) != len(german):
                findings.append(f"{key}: {len(ways)} Wege statt {len(german)} wie im Deutschen")
                continue
            for meant, way in zip(german, ways, strict=True):
                shown = " → ".join(way)
                unknown = [part for part in meant if part not in said]
                if unknown:
                    findings.append(f"{key}: {unknown} ist kein Text der Oberfläche")
                    continue
                if way[0] not in bar:
                    findings.append(f"{key}: *{shown}* beginnt an keinem Menü der Leiste")
                if len(way) != len(meant) or any(
                    part not in said[original] for original, part in zip(meant, way, strict=False)
                ):
                    findings.append(f"{key}: *{shown}* heißt nicht wie *{' → '.join(meant)}*")
                    continue
                operation = operations.get(way[-1])
                where = menu_path(operation) if operation is not None else ""
                if where and shown != " → ".join(_plain(part) for part in where.split("→")):
                    findings.append(f"{key}: *{shown}* ist nicht der Menüweg {where!r}")
    finally:
        set_language("de")

    ways_seen = sum(len(ways) for ways, _arrows in translated.values())
    assert ways_seen >= 10, f"nur {ways_seen} Wege gefunden — das Muster greift nicht mehr"
    assert not findings, f"{language}:\n" + "\n".join(findings)


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


def _page_rows(window: ManualWindow) -> list[int]:
    """Die Zeilen der Seitenliste, in denen eine Seite steht — ohne Teilüberschriften."""
    from app.ui.manual_window import PAGE_ROLE

    return [
        row
        for row in range(window.contents.count())
        if window.contents.item(row).data(PAGE_ROLE) is not None
    ]


def test_the_window_lists_every_page(qt_app: QApplication) -> None:
    window = ManualWindow()

    assert len(_page_rows(window)) == len(manual.pages())


def test_the_window_groups_the_pages_under_their_parts(qt_app: QApplication) -> None:
    """Über jedem Teil eine Überschrift, die sich nicht wählen lässt; die Pfeiltasten
    gehen über sie hinweg, und eine Suche zeigt ihre Rangliste ohne sie
    (Konzept Handbuch §4, §7)."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window = ManualWindow()
    try:
        pages = manual.pages()
        rows = _page_rows(window)
        headings = [row for row in range(window.contents.count()) if row not in rows]
        parts = list(dict.fromkeys(page.part for page in pages))
        assert [window.contents.item(row).text() for row in headings] == [
            str(manual.PART_TITLES[part]) for part in parts
        ]
        for row in headings:
            flags = window.contents.item(row).flags()
            assert not flags & Qt.ItemFlag.ItemIsSelectable, window.contents.item(row).text()
        # Geöffnet wird die erste Seite, nicht die Überschrift über ihr.
        page = window.current_page()
        assert page is not None and page.key == manual.WHERE_TO_START

        # Von der letzten Seite eines Teils führt ↓ auf die erste des nächsten.
        boundary = headings[1]
        window.contents.setCurrentRow(boundary - 1)
        QTest.keyClick(window.contents, Qt.Key.Key_Down)
        assert window.contents.currentRow() == boundary + 1
        QTest.keyClick(window.contents, Qt.Key.Key_Up)
        assert window.contents.currentRow() == boundary - 1

        window.search.setText("Loch")
        assert len(_page_rows(window)) == window.contents.count(), "Überschriften in der Suche"
    finally:
        window.close()
        window.deleteLater()


def test_a_page_opens_at_the_entry_it_was_asked_for(qt_app: QApplication) -> None:
    """F1 im Dialog *Mutternfalle*: das Referenzkapitel, aufgeschlagen und
    markiert an seinem Eintrag — auch wenn das Kapitel schon offen war.

    Eine Operation ohne Anleitung aus ``parts``: Dort heißt auch die
    Erklärseite „Die Bausteine“, und F1 landete oben auf ihr statt am Eintrag.
    """
    window = ManualWindow()
    try:
        page, spot = manual.help_for("insert_nut_trap")
        assert spot, "die Operation hat inzwischen eine Anleitung — eine andere wählen"
        for _attempt in range(2):
            window.show_page(page, spot)
            shown = window.current_page()
            assert shown is not None and shown.key == page
            assert window.text.textCursor().selectedText() == str(
                REGISTRY.get("insert_nut_trap").title
            )
            assert spot[1:] in window.text.textCursor().charFormat().anchorNames()
    finally:
        window.close()
        window.deleteLater()


@pytest.mark.parametrize(
    "names",
    [
        ("create_brep_cone", "create_cone"),
        ("create_organizer_rim", "insert_organizer_rim"),
    ],
)
def test_f1_selects_each_duplicate_title_at_its_own_anchor(
    qt_app: QApplication, names: tuple[str, str]
) -> None:
    """Vorwärts und zurück auf derselben Seite: jeder gleiche Titel bleibt sein Ziel."""
    window = ManualWindow()
    try:
        positions: dict[str, int] = {}
        for name in (*names, *reversed(names)):
            page, spot = manual.help_for(name)
            window.show_page(page, spot)
            cursor = window.text.textCursor()
            assert cursor.selectedText() == str(REGISTRY.get(name).title)
            assert cursor.blockFormat().headingLevel() == 3
            assert spot[1:] in cursor.charFormat().anchorNames()
            previous = positions.setdefault(name, cursor.selectionStart())
            assert cursor.selectionStart() == previous
        assert positions[names[0]] != positions[names[1]]
    finally:
        window.close()
        window.deleteLater()


def test_f1_anchors_ignore_body_mentions_and_raw_html(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nur echte Überschriften bekommen Ziele; Roh-HTML bleibt sichtbarer Text."""
    first = manual.operation_anchor("first")
    second = manual.operation_anchor("second")
    page = manual.Page(
        "ref-probe",
        "Probe",
        "## Probe\n\nGleicher Titel steht schon im Fließtext.\n\n"
        f'<a name="{second}" href="file://///fremd.example/x">Gleicher Titel</a>\n\n'
        "### Gleicher Titel\n\nErster Eintrag.\n\n"
        "### Gleicher Titel\n\nZweiter Eintrag.",
        generated=True,
    )
    monkeypatch.setattr(manual, "pages", lambda: (page,))
    monkeypatch.setattr(
        manual,
        "reference_anchors",
        lambda key: ((first, "Gleicher Titel"), (second, "Gleicher Titel")),
    )
    window = ManualWindow()
    try:
        positions = []
        for anchor in (first, second):
            window.show_page(page.key, f"#{anchor}")
            cursor = window.text.textCursor()
            assert cursor.selectedText() == "Gleicher Titel"
            assert cursor.blockFormat().headingLevel() == 3
            assert cursor.charFormat().anchorNames() == [anchor]
            positions.append(cursor.selectionStart())
        assert positions[0] < positions[1]
        assert 'href="file:' not in window.text.document().toHtml()
        assert "<a name=" in window.text.document().toPlainText()
    finally:
        window.close()
        window.deleteLater()


def test_recipe_subheadings_preserve_all_native_reference_anchors(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rezept-Hinweise dürfen trotz ATX und Setext keinen Operationsanker übernehmen."""
    from dataclasses import replace

    from app.core.registry.registry import Registry
    from app.core.registry.surfaces import documentation

    own = Registry()
    first = REGISTRY.get("create_brep_cone")
    second = REGISTRY.get("create_cone")
    own.register(
        replace(
            first,
            doc=(
                f"### {second.title}\n\nEin Hinweis.\n\nWeitere Hinweise\n===\n\nText.\n\n"
                f"> ### {second.title}\n\n- ### {second.title}"
            ),
        )
    )
    own.register(second)
    page = manual.Page(
        manual.reference_key(first.category),
        CATEGORIES[first.category],
        documentation(own, category=first.category, technical=False),
        generated=True,
    )
    anchors_for = manual.reference_anchors
    monkeypatch.setattr(manual, "pages", lambda: (page,))
    monkeypatch.setattr(manual, "reference_anchors", lambda key: anchors_for(key, own))
    window = ManualWindow()
    try:
        positions = []
        for spec in (first, second):
            key, anchor = manual.help_for(spec.name, own)
            window.show_page(key, anchor)
            cursor = window.text.textCursor()
            assert cursor.selectedText() == str(spec.title)
            assert anchor[1:] in cursor.charFormat().anchorNames()
            assert cursor.blockFormat().headingLevel() == 3
            positions.append(cursor.selectionStart())
        assert positions[0] != positions[1]
        assert "Weitere Hinweise" in window.text.document().toPlainText()
    finally:
        window.close()
        window.deleteLater()


def test_searching_looks_inside_the_pages(qt_app: QApplication) -> None:
    """Wer „Elefantenfuß" sucht, weiß nicht, in welchem Kapitel es steht."""
    window = ManualWindow()

    window.search.setText("Elefantenfuß")

    assert window.contents.count() >= 1
    assert window.contents.count() < len(manual.pages())


def test_the_search_lists_the_best_page_first_and_opens_it_where_the_word_stands(
    qt_app: QApplication,
) -> None:
    """Die Liste folgt der Rangfolge des Kerns, und die Seite schlägt an der
    Fundstelle auf, markiert (Konzept Handbuch §7). „Elefantenfuß" steht weit
    unten in der Referenz mitten im Text. „abrunden" trifft seit HB-8 den Titel
    der Anleitung *Kanten abrunden oder anfasen*, und ein Titeltreffer
    beginnt oben, ohne Markierung."""
    from app.core import manual_search

    window = ManualWindow()
    try:
        window.search.setText("Elefantenfuß")
        found = manual_search.search("Elefantenfuß")
        assert found and found[0].spot
        assert window.contents.item(0).text() == str(found[0].page.title)
        assert window.text.textCursor().selectedText() == found[0].spot
        window.search.setText("abrunden")
        found = manual_search.search("abrunden")
        assert found and not found[0].spot, "ein Titeltreffer hat keine Fundstelle im Text"
        assert window.contents.item(0).text() == str(found[0].page.title)
        assert not window.text.textCursor().hasSelection()
    finally:
        window.close()
        window.deleteLater()


def test_a_search_without_a_hit_says_so_instead_of_showing_nothing(
    qt_app: QApplication,
) -> None:
    window = ManualWindow()

    window.search.setText("gibtesnicht-xyz")

    assert window.contents.count() == 0
    assert window.text.toPlainText().strip()


def test_a_search_without_a_hit_names_the_way_back(qt_app: QApplication) -> None:
    """„Dazu steht nichts im Handbuch." endete dort — ohne den nächsten Schritt
    (Regel 17)."""
    window = ManualWindow()
    try:
        window.search.setText("gibtesnicht-xyz")
        assert "Suchfeld" in window.text.toPlainText(), window.text.toPlainText()
    finally:
        window.close()
        window.deleteLater()


@pytest.mark.parametrize("chosen", ["first", "last"])
def test_a_search_that_runs_out_of_hits_reads_no_page_of_the_old_list(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, chosen: str
) -> None:
    """Eine Suche ohne Treffer nach einer mit Treffern wirft nichts.

    Kundenmeldung zu 0.5.2: Viermal ``IndexError`` in ``_show_current``,
    während im Handbuch gesucht wurde. ``_fill`` setzte die neue Seitenliste,
    bevor die alten Zeilen weg waren, und ``clear()`` meldete dazwischen noch
    eine alte Zeile — mit einer Nummer in die neue, leere Liste. Eine
    Ausnahme in einem Slot sieht nur ``sys.excepthook``; ohne ihn bliebe der
    Test grün.
    """
    errors: list[BaseException] = []
    monkeypatch.setattr(sys, "excepthook", lambda _kind, value, _trace: errors.append(value))
    window = ManualWindow()
    try:
        window.search.setText("Gewinde")
        assert window.contents.count() > 1, "die Suche muss vorher etwas finden"
        if chosen == "last":
            window.contents.setCurrentRow(window.contents.count() - 1)

        window.search.setText("gibtesnicht-xyz")

        assert not errors, errors
        assert window.contents.count() == 0
        assert "Suchfeld" in window.text.toPlainText(), window.text.toPlainText()
    finally:
        window.close()
        window.deleteLater()


def test_the_search_and_the_page_list_carry_names(qt_app: QApplication) -> None:
    """Suchfeld und Seitenliste standen ohne zugänglichen Namen da — ein
    Bildschirmleser las „Eingabefeld" und „Liste"."""
    window = ManualWindow()
    try:
        assert window.search.accessibleName().strip()
        assert window.contents.accessibleName().strip()
        assert window.text.accessibleName().strip()
    finally:
        window.close()
        window.deleteLater()


def test_clearing_the_search_brings_everything_back(qt_app: QApplication) -> None:
    window = ManualWindow()
    window.search.setText("Elefantenfuß")

    window.search.setText("")

    assert len(_page_rows(window)) == len(manual.pages())


def test_a_page_can_be_opened_by_name(qt_app: QApplication) -> None:
    window = ManualWindow()

    window.show_page("tolerances")

    assert "Material" in window.contents.currentItem().text()


def test_an_unknown_page_keeps_the_shown_one_and_says_so_in_the_log(
    qt_app: QApplication, caplog: pytest.LogCaptureFixture
) -> None:
    """Ein Schlüssel ohne Seite verpufft nicht still: Das Protokoll nennt ihn."""
    import logging

    window = ManualWindow()
    try:
        window.show_page("tolerances")
        shown = window.text.toPlainText()
        with caplog.at_level(logging.WARNING):
            window.show_page("holes")

        assert window.text.toPlainText() == shown, "die gezeigte Seite bleibt"
        assert "'holes'" in caplog.text, caplog.text
    finally:
        window.close()
        window.deleteLater()


def test_a_link_to_another_page_opens_it_in_the_window(qt_app: QApplication) -> None:
    """Ein Klick auf ``manual:<schlüssel>`` schlägt die Seite auf, im selben Fenster."""
    from PySide6.QtCore import QUrl

    window = ManualWindow()
    try:
        window.show_page("what")
        window.text.anchorClicked.emit(QUrl("manual:tolerances"))

        assert "Material" in window.contents.currentItem().text()
    finally:
        window.close()
        window.deleteLater()


def test_a_generated_chapter_shows_its_title_in_the_window_too(qt_app: QApplication) -> None:
    """Auch im Fenster steht über jeder Seite, welche es ist.

    Das Fenster entschied am Feld ``generated``, und die vier Wissensseiten
    sind erzeugt, bringen aber keine Überschrift mit: Wer „Wonach Solidon
    urteilt" anklickte, las als erste Zeile „Diese Regeln liegen dem Agenten
    bei jeder Anfrage vor" — ohne Titel, mitten im Satz. Beide Ausgaben nehmen
    die Regel jetzt aus ``manual.titled``.
    """
    window = ManualWindow()

    window.show_page("profiles")
    shown = window.text.toPlainText()

    page = manual.find("profiles")
    assert page is not None
    assert shown.startswith(str(page.title)), shown[:80]

    # Das Referenzkapitel trägt den Vorsatz ``ref-``; „holes“ allein ist
    # keine Seite, und das Fenster stünde weiter auf „Wonach Solidon urteilt“.
    window.show_page(manual.reference_key("holes"))
    reference = window.text.toPlainText()
    assert reference.startswith(str(CATEGORIES["holes"])), reference[:80]
    # Der Kategoriename kann auch ein Feldtitel sein; nur wirkliche
    # Kapitelüberschriften zählen, keine gleichlautenden Klartextzeilen. Die
    # Ebene ist Sache der Darstellung (Seitentitel ``h2``, Operationen ``h3``).
    headings = []
    block = window.text.document().begin()
    while block.isValid():
        if block.blockFormat().headingLevel() > 0:
            headings.append(block.text())
        block = block.next()
    assert headings.count(str(CATEGORIES["holes"])) == 1, "und nicht zweimal"


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

    assert tr("Gilt für: {kinds}", kinds=tr("Fläche")) in text
    assert "face" not in text.split("|")[0], "der Schlüssel steht nicht in der Faktenzeile"


def test_french_sets_a_space_before_colon_semicolon_and_question_mark() -> None:
    """Das französische Handbuch setzt vor „:“, „;“, „?“ und „!“ ein Leerzeichen.

    Die Übersetzungen tun das von selbst. Wo aber der Code zwei übersetzte
    Teile mit einem festen „: “ verband, stand „Objets: 0 → 1“ und „**Où:**“
    an jeder Operation der Referenz. Der Doppelpunkt gehört deshalb in den
    übersetzten Satz. Code, Verweisziele und Adressen zählen nicht.
    """
    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog

    install_catalog("fr", read_catalog("fr"))
    set_language("fr")
    try:
        text = manual.as_markdown()
    finally:
        set_language("de")
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"https?://\S+", "", text)
    tight = [
        text[max(0, found.start() - 40) : found.end() + 10].replace("\n", " ")
        for found in re.finditer(r"(?<=[\w)*»”…])[:;!?](?=\s|$|\*)", text, re.MULTILINE)
    ]
    assert not tight, "ohne Leerzeichen davor:\n" + "\n".join(tight[:10])


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
    stünde im deutschen Handbuch neben einer Anwendung, die 2,40 mm anzeigt.

    **Der Katalog wird hier geladen und nicht vorausgesetzt.** ``set_language``
    setzt nur eine Variable; das Dezimalzeichen kommt aus dem Katalog
    (``decimal_separator`` liest ``tr("0,1")``), und ohne ihn fällt ``tr`` auf
    die deutsche Message-ID zurück — also auf das Komma. Der Test war trotzdem
    jahrelang grün, weil in derselben Portion vorher ein anderer Test den
    englischen Katalog geladen hatte. Am 10.09.2026 fiel dieser Vorgänger weg:
    Ein nativer Abbruch ließ das Tor die Portion halbieren, der Test landete in
    der anderen Hälfte und wurde rot — an einer Anwendung, in der nichts kaputt
    war. ``app.py`` lädt den Katalog beim Start; das ist die Betriebslage, und
    ein Test stellt sie selbst her.
    """
    from app.i18n import set_language
    from app.i18n.catalog import install_language

    try:
        install_language("de")
        set_language("de")
        assert "0,25" in manual.profiles_text()
        install_language("en")
        set_language("en")
        assert "0.25" in manual.profiles_text()
    finally:
        install_language("de")
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
    assert '<h3 class="toc-part">NL·Erste Schritte</h3>' in html
    assert '<h2 class="part">NL·Nachschlagen</h2>' in html
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
        '<h3 class="toc-part">Erste Schritte</h3>',
        '<h2 class="part">Nachschlagen</h2>',
    )
    assert not [text for text in german_fallbacks if text in html]

    assert make_manual.page_for("nl") == ("nl/manual.html", "../handbuch/nl")


def test_layout_refresh_preserves_released_chapters_and_is_repeatable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Eine Website-Korrektur darf keine unveröffentlichten Handbuchtexte einführen."""
    from tools import make_manual

    monkeypatch.setattr(make_manual, "WEBSITE", tmp_path)
    page = tmp_path / "handbuch.html"
    chapter = '<h3 id="released">Veröffentlichter Stand</h3><p>Unverändert &amp; lesbar.</p>'
    navigation = '<nav class="toc" id="toc"><a href="#released">Kapitel</a></nav>'
    page.write_text(
        f"<html><head><style>alt</style></head><body><main>{navigation}{chapter}</main></body></html>",
        encoding="utf-8",
    )
    make_manual.refresh_layout("de")
    first = page.read_text(encoding="utf-8")
    make_manual.refresh_layout("de")
    assert page.read_text(encoding="utf-8") == first
    assert chapter in first
    assert navigation in first
    assert first.count('<details class="manual-index"') == 1
    assert '<body class="manual-page">' in first


def test_layout_refresh_leaves_unknown_templates_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein unbekannter Rahmen wird nicht teilweise überschrieben."""
    from tools import make_manual

    monkeypatch.setattr(make_manual, "WEBSITE", tmp_path)
    page = tmp_path / "handbuch.html"
    original = "<html><head><style>alt</style></head><body>Anderer Aufbau</body></html>"
    page.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="Vorlage"):
        make_manual.refresh_layout("de")
    assert page.read_text(encoding="utf-8") == original


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


@pytest.mark.parametrize("language", ["de", "en", "fr"])
def test_the_parts_stand_in_the_contents_and_in_the_text_alike(language: str) -> None:
    """Verzeichnis und Text gliedern sich nach denselben Teilen (Konzept Handbuch §4).

    Je Teil mit Seiten steht im Verzeichnis sein Titel über seinen Kapiteln
    und im Text eine Teilüberschrift vor seinem ersten Kapitel — in der
    Reihenfolge von ``manual.pages()`` und aus ``Page.part``, derselben
    Auskunft, nach der das Handbuchfenster gruppiert. Verglichen wird die
    ganze Folge aus Teilen und Kapiteln: Stünde ein Teil an der falschen
    Stelle, fehlte er im Text oder stünde ein Kapitel unter dem falschen, wiche
    sie ab.
    """
    import re
    from html import escape as html_escape
    from itertools import groupby

    from app.i18n import install_catalog, set_language
    from app.i18n.catalog import read_catalog
    from tools.make_manual import _anchor, _classify, anchored, contents

    install_catalog(language, read_catalog(language))
    set_language(language)
    try:
        expected: list[str] = []
        for part, members in groupby(manual.pages(), key=lambda page: page.part):
            expected.append(f"teil:{html_escape(str(manual.PART_TITLES[part]), quote=False)}")
            expected.extend(f"kapitel:{_anchor(page)}" for page in members)
        toc = [
            f"teil:{title}" if title else f"kapitel:{target}"
            for title, target in re.findall(
                r'<h3 class="toc-part">([^<]+)</h3>|<a href="#([^"]+)">', contents(language)
            )
        ]
        text = [
            f"teil:{title}" if title else f"kapitel:{target}"
            for title, target in re.findall(
                r'<h\d class="part">([^<]+)</h\d>|<h\d id="([^"]+)"',
                anchored(_classify(manual.as_html())),
            )
        ]
    finally:
        set_language("de")

    parts = [entry for entry in expected if entry.startswith("teil:")]
    assert len(parts) >= 3, f"{language}: nur diese Teile haben Seiten: {parts}"
    assert toc == expected, f"{language}: das Verzeichnis folgt den Teilen nicht"
    assert text == expected, f"{language}: der Text folgt den Teilen nicht"


def test_a_part_without_pages_has_no_heading_and_the_numbers_run_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Teil ohne Seiten verspräche Kapitel, die es nicht gibt.

    Sein Titel steht weder im Verzeichnis noch im Text. Die Nummern laufen über
    die Teile hinweg durch, wie über den Kapiteln im Text. Die Teilüberschrift
    steht unmittelbar vor dem ersten Kapitel, auch vor einem erzeugten: Daran
    hängt im Druck, dass ein Referenzkapitel am Anfang eines Teils kein
    zweites Blatt beginnt und die Überschrift allein zurücklässt.
    """
    from tools.make_manual import _classify, anchored, contents

    pages = (
        manual.Page("one", "Eins", "Der erste Text über etwas.", part="start"),
        manual.Page("two", "Zwei", "Der zweite Text über etwas.", part="start"),
        manual.Page("three", "Drei", "Der dritte Text über etwas.", part="topics"),
        manual.Page("scene", "Szene", "## Szene\n\nErzeugt aus dem Register.", generated=True),
    )
    monkeypatch.setattr(manual, "pages", lambda registry=None: pages)
    toc = contents("de")
    text = anchored(_classify(manual.as_html()))

    for absent in ("tasks", "help"):
        assert str(manual.PART_TITLES[absent]) not in toc + text, absent
    assert '<h3 class="toc-part">Erste Schritte</h3><ol>' in toc
    assert '<h3 class="toc-part">Funktionen</h3><ol start="3">' in toc
    assert '<h3 class="toc-part">Nachschlagen</h3><ol start="4">' in toc
    assert '<h2 class="part">Erste Schritte</h2><h3 id="one">' in text
    assert '<h2 class="part">Funktionen</h2><h3 id="three">' in text
    assert '<h2 class="part">Nachschlagen</h2><h3 id="ref-scene" class="chapter">' in text
    assert text.count('class="part"') == 3


def test_the_knowledge_pages_stand_before_the_reference() -> None:
    """Wonach gerechnet wird, gehört vor die Liste dessen, was gerechnet werden
    kann."""
    keys = [page.key for page in manual.pages()]
    scene = keys.index(manual.reference_key("scene"))
    assert keys.index("profiles") < scene


def test_the_customer_manual_has_no_agent_internal_chapters() -> None:
    """Die Bedienanleitung zeigt Handlungen und Hilfe, keine Anweisungen an die KI."""
    pages = manual.pages()
    keys = {page.key for page in pages}
    assert not {"rules", "remote-tools"} & keys
    assert {"chat", "generating", "remote", "models", "profiles", "messages"} <= keys
    assert not any("manual:remote-tools" in str(page.body) for page in pages)


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


def test_the_manual_names_a_face_the_way_the_labels_do() -> None:
    """Was der Kunde im Objektbaum liest, steht auch im Handbuch.

    Das Handbuch sagte „Oben“, „Vorn“, „Rechts“; die Beschriftung
    (``labels._SIDES``) sagt „Oberseite“, „Vorderseite“, „Rechte Seite“. Wer
    nach der Seite sucht, die im Handbuch steht, findet sie im Fenster nicht —
    und die Richtung ist die einzige Auskunft, die ein Flächenname überhaupt
    gibt. Das Fenster hat recht: Der Kunde liest die Beschriftung öfter als
    das Handbuch.

    Gefragt werden die Beschriftungen selbst und keine Kopie: Wer sie umbenennt,
    macht diesen Test rot und findet dabei den Absatz, der nachziehen muss.
    """
    from app.ui import labels

    text = manual.as_markdown()
    for positiv, negativ in labels._SIDES:
        assert str(positiv) in text or str(negativ) in text, (
            f"weder „{positiv}“ noch „{negativ}“ steht im Handbuch"
        )
    innen = str(labels._INNER_SIDES[2][0])
    assert innen in text, f"„{innen}“ — der Name der Innenwand steht nicht im Handbuch"


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

        page = opened.current_page()
        assert page is not None
        assert page.key == manual_module.WHERE_TO_START, (
            f"geoeffnet wurde {page.title} statt des zugesagten Kapitels"
        )
        # Ohne Rücksicht auf die Großschreibung: Der Hinweis darf den Titel
        # mitten im Satz tragen.
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


def _help_action(window: object) -> object:
    """Der Menüeintrag *Hilfe → Handbuch …*, der F1 trägt."""
    from PySide6.QtGui import QAction, QKeySequence

    help_key = QKeySequence(QKeySequence.StandardKey.HelpContents)
    return next(
        action
        for action in window.findChildren(QAction)  # type: ignore[attr-defined]
        if action.shortcut() == help_key
    )


def test_f1_opens_where_to_start_and_keeps_the_page_being_read(qt_app: QApplication) -> None:
    """F1 im Hauptfenster: Ein neu geöffnetes Handbuch beginnt bei „Wo fange ich
    an?"; ein offenes bleibt auf der Seite, die gerade gelesen wird. Der Weg
    durch eine Bildanleitung ist Schritt lesen, im Hauptfenster tun, mit F1
    zurück (Konzept Handbuch §7)."""
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        action = _help_action(window)
        action.trigger()  # type: ignore[attr-defined]
        opened = window._manual
        assert opened is not None
        assert opened.current_page().key == manual.WHERE_TO_START  # type: ignore[union-attr]

        opened.show_page("drill-a-hole")
        action.trigger()  # type: ignore[attr-defined]
        assert opened.current_page().key == "drill-a-hole", "F1 riss die Leseseite weg"  # type: ignore[union-attr]

        opened.close()
        action.trigger()  # type: ignore[attr-defined]
        assert opened.isVisible()
        assert opened.current_page().key == manual.WHERE_TO_START  # type: ignore[union-attr]
    finally:
        window.close()
        window.deleteLater()


def test_f1_in_an_operation_dialog_opens_the_guide_that_teaches_it(qt_app: QApplication) -> None:
    """Das F1 des Hauptfensters kommt im Dialog nicht an, er ist ein eigenes
    Fenster (gemessen: null Auslösungen, Konzept Handbuch §1.2). Geprüft wird
    der Weg, den das Fenster für jeden Operationsdialog legt."""
    from PySide6.QtGui import QKeySequence, QShortcut

    from app.ui.main_window import MainWindow
    from app.ui.op_dialog import OperationDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        dialog = OperationDialog(REGISTRY.get("drill_hole"), {}, window)
        window._open_operation_dialog(dialog, lambda: None)
        assert window._op_dialog is dialog
        help_key = QKeySequence(QKeySequence.StandardKey.HelpContents)
        shortcut = next(item for item in dialog.findChildren(QShortcut) if item.key() == help_key)
        shortcut.activated.emit()

        opened = window._manual
        assert opened is not None and opened.isVisible()
        page = opened.current_page()
        assert page is not None and page.key == "drill-a-hole"
    finally:
        window.close()
        window.deleteLater()


def test_f1_in_the_dialog_of_an_operation_without_a_guide_marks_its_entry(
    qt_app: QApplication,
) -> None:
    """F1 in *Mutternfalle* und *Tasche schneiden*: das Referenzkapitel, an
    ihrem Eintrag markiert — über den ganzen Weg der Anwendung.

    Beide Kategorien teilten ihren Schlüssel mit einer Erklärseite („Die
    Bausteine“, „Zeichnen“), und das Fenster nahm die erste Seite dieses
    Namens: oben, ohne Markierung.
    """
    from PySide6.QtGui import QKeySequence, QShortcut

    from app.ui.main_window import MainWindow
    from app.ui.op_dialog import OperationDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        help_key = QKeySequence(QKeySequence.StandardKey.HelpContents)
        for name in ("insert_nut_trap", "sketch_pocket"):
            key, spot = manual.help_for(name)
            assert spot, f"{name} hat inzwischen eine Anleitung — eine andere wählen"
            dialog = OperationDialog(REGISTRY.get(name), {}, window)
            window._open_operation_dialog(dialog, lambda: None)
            shortcut = next(
                item for item in dialog.findChildren(QShortcut) if item.key() == help_key
            )
            shortcut.activated.emit()
            opened = window._manual
            assert opened is not None and opened.isVisible()
            page = opened.current_page()
            assert page is not None and page.key == key, name
            assert opened.text.textCursor().selectedText() == str(REGISTRY.get(name).title), name
            assert spot[1:] in opened.text.textCursor().charFormat().anchorNames(), name
            dialog.reject()
    finally:
        window.close()
        window.deleteLater()


def test_f1_from_a_dialog_leaves_an_open_guide_where_it_is(qt_app: QApplication) -> None:
    """Schritt 3 von *Ein Loch bohren* öffnet *Bohrung setzen*, F1 im Dialog
    soll zum nächsten Schritt führen: Die offene Anleitung bleibt stehen, wo
    der Leser ist, statt an den Anfang zu springen.
    """
    window = ManualWindow()
    try:
        window.resize(700, 400)
        window.show()
        page, spot = manual.help_for("drill_hole")
        assert not spot, "die Operation hat keine Anleitung mehr — eine andere wählen"
        window.show_page(page)
        qt_app.processEvents()
        bar = window.text.verticalScrollBar()
        assert bar.maximum() > 0, "die Seite passt ins Fenster — dann prüft das nichts"
        bar.setValue(bar.maximum() // 2)
        before = bar.value()
        window.show_page(page, spot)
        qt_app.processEvents()
        assert bar.value() == before
    finally:
        window.close()
        window.deleteLater()


def test_the_manual_opens_only_its_own_website(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Klick im Handbuch führt nur auf solidon3d.de.

    Das Handbuch entsteht aus dem Register, und ein mitgereistes Rezept bringt
    Titel und Beschreibung aus einer fremden Projektdatei mit. Ein
    ``[Text](search-ms:…)`` darin wurde zu einem echten Anker mit
    angreifergewählter Beschriftung — die Adresse stand nirgends, denn das
    Fenster hat keine Statuszeile (Sicherheitsdurchsicht 04.09.2026).
    """
    from PySide6.QtCore import QUrl

    window = ManualWindow()
    try:
        geoeffnet: list[str] = []
        monkeypatch.setattr(
            "PySide6.QtGui.QDesktopServices.openUrl",
            lambda url: geoeffnet.append(url.toString()) or True,
        )

        for adresse in (
            # Startet unter Windows den eingetragenen Protokoll-Handler.
            "search-ms:query=update&crumb=location:\\\\fremd.example\\share",
            "ms-msdt:/id x",
            # Erzwingt eine SMB-Anmeldung, also einen NetNTLM-Abfluss.
            "file://///fremd.example/share/x.exe",
            "https://fremd.example/",
            # Ein Präfixvergleich fiele hierauf herein, ein Hostvergleich nicht.
            "https://solidon3d.de.fremd.example/",
            # Auch die eigene Domain nur verschlüsselt.
            "http://solidon3d.de/handbuch.html",
        ):
            window._open_link(QUrl(adresse))
        assert geoeffnet == [], f"nichts davon darf öffnen: {geoeffnet}"

        window._open_link(QUrl("https://solidon3d.de/handbuch.html"))
        assert geoeffnet == ["https://solidon3d.de/handbuch.html"], (
            "die eigene Website muss weiter erreichbar sein"
        )
    finally:
        window.close()
        window.deleteLater()


def test_no_click_in_the_manual_opens_anything_by_itself(qt_app: QApplication) -> None:
    """``setOpenLinks`` schließt auch den Weg über ``setSource``.

    ``setOpenExternalLinks(False)`` allein genügt nicht: Ein ``file://`` gilt
    Qt nicht als extern, sondern wird als Dokument geladen — bei einem
    UNC-Pfad heißt das, dass Windows die Freigabe öffnet.
    """
    window = ManualWindow()
    try:
        assert not window.text.openLinks(), "kein Anker öffnet sich selbst"
        assert not window.text.openExternalLinks(), "und schon gar nicht nach außen"
    finally:
        window.close()
        window.deleteLater()


def test_raw_html_in_a_manual_page_stays_text(qt_app: QApplication) -> None:
    """Rohes HTML im Markdown wird kein Anker.

    Qts Vorgabe ist der GitHub-Dialekt, und der wertet eingebettetes HTML aus.
    Mit ``MarkdownNoHTML`` steht dasselbe HTML als Text da — sichtbar, aber
    ohne ``href``. Die zweite Schicht neben der Positivliste des Klicks.
    """
    window = ManualWindow()
    try:
        window.text.setMarkdown(
            'Ein <a href="file://///fremd.example/s/x.exe">harmlos aussehender</a> Satz.'
        )
        html = window.text.document().toHtml()

        assert 'href="file:' not in html, "kein Anker auf eine Netzfreigabe"
        assert "fremd.example" in window.text.document().toPlainText(), (
            "der Text bleibt sichtbar — verschwiegen wird nichts, es wirkt nur nicht"
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
    for model in ("TRELLIS.2", "DINOv3", "BiRefNet", "FLUX.2 [klein] 4B", "Qwen3-4B"):
        assert model in seite, f"das Erzeugungsmodell {model} fehlt"
    assert "TripoSG" not in seite and "SDXL" not in seite
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
        assert "TRELLIS.2" in text, f"{language}: TRELLIS.2 fehlt"
        assert "TripoSG" not in text, f"{language}: TripoSG steht noch da"
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
            "Ni le fichier, ni l'auteur, ni la licence, ni la provenance "
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
        # Entschlüsselt: Die Seite schreibt einen geraden Apostroph als
        # ``&#x27;``, und der Satz, den der Kunde liest, ist der entschlüsselte.
        html = unescape(WEBSITE_PAGES[language].read_text(encoding="utf-8"))
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
    # Seit RM-509 steht hinter dem Namen die Art der Seite („— Funktionen“),
    # die vorher der Statustipp trug; der volle Name bleibt vorn.
    assert eintrag.toolTip().startswith(f"{eintrag.text()} — "), "der volle Name steht im Hinweis"
    fenster.close()


def test_a_click_on_a_manual_link_really_reaches_the_allowlist(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die **Verbindung**, nicht die Methode dahinter.

    ``test_the_manual_opens_only_its_own_website`` ruft ``_open_link``
    unmittelbar auf und prüft damit die Positivliste — bei der Gegenprobe
    blieb es deshalb grün, während vier andere Tests fielen. Was dort fehlte,
    ist die Frage, ob Qts ``anchorClicked`` überhaupt bei diesem Slot ankommt.
    Genau davor warnt ``.claude/rules/tests.md`` unter „Am Weg vorbei", und
    solidon-b4 hat am 04.09.2026 dieselbe Familie in ihrer schärferen Gestalt
    gemessen: eine in Python überschriebene VTK-Methode, die VTKs eigener
    C++-Code nie ruft — Rechnung richtig, drei Einheitstests grün, am
    laufenden Fenster 35,8 Grad Schräglage statt der gerechneten 0.

    **Was dieser Test nicht prüft:** den Mausklick selbst. Dass Qt beim Klick
    auf einen Anker ``anchorClicked`` feuert, ist Qt-Verhalten und keine
    Zusage dieses Projekts; die Position eines Ankers offscreen zu treffen
    wäre eine Messung an der Schriftmetrik, und die gibt es dort nicht.
    Geprüft wird die Kette dahinter: Anker im Dokument, Signal am Slot,
    Positivliste am Ziel.
    """
    from PySide6.QtCore import QUrl

    window = ManualWindow()
    try:
        opened: list[str] = []
        monkeypatch.setattr(
            "PySide6.QtGui.QDesktopServices.openUrl",
            lambda url: opened.append(url.toString()) or True,
        )
        window.text.setMarkdown(
            "Ein [Handbuch](https://solidon3d.de/handbuch.html) und ein "
            "[fremder](search-ms:query=x) Link."
        )

        # Erst der Beleg, dass Qt überhaupt Anker gerendert hat — ohne ihn
        # prüfte alles Weitere eine leere Menge (`tests.md`: „Ein Verbotstest
        # über eine leere Menge ist immer grün").
        html = window.text.document().toHtml()
        assert 'href="https://solidon3d.de/handbuch.html"' in html, "der eigene Anker steht da"
        assert 'href="search-ms:query=x"' in html, "der fremde auch — gesperrt wird beim Klick"

        # Und jetzt der Weg, den ein Klick nimmt: Qt schickt das Signal, und
        # es muss bei ``_open_link`` ankommen.
        window.text.anchorClicked.emit(QUrl("search-ms:query=x"))
        assert opened == [], "ein fremdes Ziel öffnet nicht"

        window.text.anchorClicked.emit(QUrl("https://solidon3d.de/handbuch.html"))
        assert opened == ["https://solidon3d.de/handbuch.html"], (
            "die eigene Website muss über die Verbindung erreichbar sein"
        )
    finally:
        window.close()
        window.deleteLater()


def test_the_manual_loads_no_image_but_its_own_figures(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Gesamtreview 05.09.2026, UI-22: ``loadResource`` reichte alles außer
    ``figure:`` an Qt weiter, und Qt lädt — eine Rezeptbeschreibung mit
    ``![Bild](file:///…)`` ließ schon das Öffnen der Seite die Datei lesen,
    ohne Klick und an der Hostprüfung der Links vorbei. Das Handbuch kennt
    genau eine Bildquelle: seinen Abbildungskatalog."""
    from PySide6.QtCore import QSize, QUrl
    from PySide6.QtGui import QImage, QPixmap, QTextDocument

    from app.ui.manual_window import PageView

    image = tmp_path / "fremd.png"
    picture = QImage(4, 4, QImage.Format.Format_RGB32)
    picture.fill(0xFF00FF00)
    assert picture.save(str(image))

    view = PageView()
    try:
        view.setMarkdown(f"# Seite\n\n![Bild]({image.as_uri()})\n")
        qt_app.processEvents()

        # Gemessen wird das **gezeichnete** Dokument: Ein leerer Rückgabewert
        # allein hielt Qt nicht davon ab, die Datei selbst zu laden (die
        # Nachprüfung vom 05.09.2026 fand genau diesen Weg übersehen).
        assert _painted_pixels(view.document(), 0xFF00FF00) == 0, (
            "das fremde Bild darf nirgends im gezeichneten Handbuch stehen"
        )
        assert "Bild" in view.document().toPlainText(), "der Alt-Text bleibt lesbar"

        served = view.loadResource(QTextDocument.ResourceType.ImageResource, QUrl(image.as_uri()))
        assert isinstance(served, QImage) and served.size() == QSize(1, 1), (
            "eine fremde Anfrage bekommt ein gültiges leeres Pixel, kein None und keine Daten"
        )
        held = view.document().resource(
            QTextDocument.ResourceType.ImageResource, QUrl(image.as_uri())
        )
        assert not (
            isinstance(held, (QImage, QPixmap)) and not held.isNull() and held.size() != QSize(1, 1)
        ), "Qt darf die Datei auch nicht als QPixmap nachladen — höchstens unser leeres Pixel"
    finally:
        view.deleteLater()


def _painted_pixels(document: object, colour: int) -> int:
    """Zeichnet das Dokument und zählt die Pixel einer Farbe."""
    from PySide6.QtCore import QSizeF
    from PySide6.QtGui import QImage, QPainter

    document.setTextWidth(320)  # type: ignore[attr-defined]
    size: QSizeF = document.size()  # type: ignore[attr-defined]
    canvas = QImage(
        max(1, int(size.width())), max(1, int(size.height())), QImage.Format.Format_RGB32
    )
    canvas.fill(0xFFFFFFFF)
    painter = QPainter(canvas)
    try:
        document.drawContents(painter)  # type: ignore[attr-defined]
    finally:
        painter.end()
    return sum(
        1
        for y in range(canvas.height())
        for x in range(canvas.width())
        if canvas.pixel(x, y) == colour
    )


def test_the_sketch_figure_draws_on_the_face_it_names() -> None:
    """Die Zeichnung des Skizzenbildes liegt auf der Fläche, nicht nur ihr Blick.

    ``frame_sketch`` übergab ein Rechteck auf der Draufsicht und die Fläche
    nur als ``plane``. Mit Strichen dreht die Ebenenwahl aber nur noch den
    Blick (``SketchCanvas.set_plane``): Das Handbuchbild zeigte „Zeichenebene:
    Draufsicht (XY)" unter dem Körper. Seit der Zeichenmodus beim Betreten
    das Ebenenfeld aus der Zeichnung neu aufbaut, sprang das Feld auf XY
    zurück, und das Werkzeug brach mit „die Skizze liegt nicht auf der
    angeforderten Fläche" ab — kein Handbuch- und kein Websitebild vom
    Skizzenmodus mehr.
    """
    from app.core.sketch.serialize import sketch_from_text

    plane = "feature:obj_1:face_9"
    sketch = sketch_from_text(figure_sketch(plane))
    assert sketch.plane == plane
    assert [element.kind for element in sketch.elements] == ["line"] * 4


def _pdf_with_chapter_targets(path: Path, targets: dict[str, int], *, dictionary: bool) -> None:
    """Eine kleine PDF mit echten Kapitelzielen und einem Inhaltslink."""
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject

    writer = PdfWriter()
    for _ in range(6):
        writer.add_blank_page(width=595, height=842)
    if dictionary:
        writer.root_object[NameObject("/Dests")] = DictionaryObject(
            {
                NameObject("/" + name): ArrayObject(
                    [writer.pages[number].indirect_reference, NameObject("/Fit")]
                )
                for name, number in targets.items()
            }
        )
    else:
        for name, number in targets.items():
            writer.add_named_destination(name, number)
    writer.pages[0][NameObject("/Annots")] = ArrayObject(
        [
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Annot"),
                    NameObject("/Subtype"): NameObject("/Link"),
                    NameObject("/Rect"): ArrayObject(
                        [NumberObject(value) for value in (0, 0, 20, 20)]
                    ),
                    NameObject("/Dest"): NameObject("/what"),
                }
            )
        ]
    )
    with path.open("wb") as stream:
        writer.write(stream)


@pytest.mark.parametrize("dictionary", (False, True))
def test_pdf_chapters_follow_printed_anchor_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dictionary: bool
) -> None:
    """Zeilenumbrüche und doppelte Titel ändern keine Kapitelposition."""
    from tools.make_manual import _chapter_of_each_page

    pages = (
        manual.Page("what", "Die vier Wege", ""),
        manual.Page("parts", "Ein langer Titel mit Zeilenumbruch", ""),
        manual.Page("parts", "Die vier Wege", "", generated=True),
        manual.Page("mesh", "Netz", "", generated=True),
    )
    monkeypatch.setattr(manual, "pages", lambda: pages)
    pdf = tmp_path / "manual.pdf"
    _pdf_with_chapter_targets(
        pdf, {"what": 2, "parts": 3, "ref-parts": 3, "ref-mesh": 4}, dictionary=dictionary
    )
    assert _chapter_of_each_page(pdf) == ["", "", "Die vier Wege", "Die vier Wege", "Netz", "Netz"]


def test_a_missing_pdf_chapter_target_stops_stamping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein fehlendes Ziel liefert keinen scheinbar gültigen Kapitelkopf."""
    from tools.make_manual import _chapter_of_each_page

    monkeypatch.setattr(manual, "pages", lambda: (manual.Page("missing", "Fehlendes Kapitel", ""),))
    pdf = tmp_path / "manual.pdf"
    _pdf_with_chapter_targets(pdf, {"what": 2}, dictionary=True)
    with pytest.raises(RuntimeError, match=r"Fehlendes Kapitel.*Erzeugen Sie"):
        _chapter_of_each_page(pdf)


def test_stamping_preserves_pdf_link_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Inhaltsverzeichnis erreicht nach Kopf- und Fußzeile noch sein Ziel."""
    from pypdf import PdfReader

    from tools import make_manual

    monkeypatch.setattr(manual, "pages", lambda: (manual.Page("what", "Die vier Wege", ""),))
    pdf = tmp_path / "manual.pdf"
    _pdf_with_chapter_targets(pdf, {"what": 2}, dictionary=True)

    def overlay(path: Path, chapters: list[str], total: int, language: str) -> Path:
        """Die Seitendarstellung bleibt hier unabhängig vom Qt-Zeichner."""
        _pdf_with_chapter_targets(path, {}, dictionary=True)
        return path

    monkeypatch.setattr(make_manual, "_overlay", overlay)
    make_manual._stamp(pdf, "de")
    reader = PdfReader(pdf)
    link = reader.pages[0]["/Annots"][0].get_object()
    target = reader.named_destinations[link["/Dest"]]
    assert reader.get_destination_page_number(target) == 2
    assert make_manual._chapter_of_each_page(pdf) == ["", "", *("Die vier Wege",) * 4]


def test_every_page_before_the_first_chapter_stays_without_header_and_footer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deckblatt und Verzeichnis bleiben frei, auch wenn das Verzeichnis wächst.

    Die Grenze sagt das erste Kapitelziel, keine feste Seitenzahl: Mit mehr
    Kapiteln oder in einer längeren Sprache reicht das Verzeichnis auf ein
    weiteres Blatt, und das bekäme sonst Kopf- und Fußzeile ohne Kapitel.
    """
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ContentStream

    from tools import make_manual

    monkeypatch.setattr(manual, "pages", lambda: (manual.Page("what", "Die vier Wege", ""),))
    pdf = tmp_path / "manual.pdf"
    _pdf_with_chapter_targets(pdf, {"what": 3}, dictionary=True)
    given: list[list[str]] = []

    def overlay(path: Path, chapters: list[str], total: int, language: str) -> Path:
        """Jede Seite der Lage trägt einen Strich, damit man sieht, wo sie liegt."""
        given.append(chapters)
        writer = PdfWriter()
        for _ in range(total):
            page = writer.add_blank_page(width=595, height=842)
            stroke = ContentStream(None, writer)
            stroke.set_data(b"0 0 m 10 10 l S")
            page.replace_contents(stroke)
        with path.open("wb") as stream:
            writer.write(stream)
        return path

    monkeypatch.setattr(make_manual, "_overlay", overlay)
    make_manual._stamp(pdf, "de")
    stamped = [page.get_contents() is not None for page in PdfReader(pdf).pages]
    assert stamped == [False, False, False, True, True, True]
    assert given == [["", "", "", *("Die vier Wege",) * 3]], "die Lage lässt dieselben frei"


def test_the_pdf_bookmarks_hold_the_parts_and_under_them_their_chapters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Lesezeichen des PDF: oben die Teile, darunter ihre Kapitel.

    Jedes springt auf seine erste Seite, gebaut aus denselben benannten Zielen
    wie Kopfzeile und Inhaltsverzeichnis: Ein Kapitel springt an die Stelle,
    die auch sein Eintrag im Verzeichnis anspringt, ein Teil an den Kopf der
    Seite, auf der sein erstes Kapitel beginnt. Das PDF öffnet mit sichtbaren
    Lesezeichen — vorher war die Seitenleiste des Betrachters leer.
    """
    from pypdf import PdfReader

    from tools import make_manual

    pages = (
        manual.Page("what", "Was Solidon ist", "", part="start"),
        manual.Page("ways", "Die vier Wege", "", part="start"),
        manual.Page("window", "Das Fenster", "", part="topics"),
        manual.Page("glossary", "Wörterbuch", "", part="reference"),
        manual.Page("mesh", "Netz", "", generated=True),
    )
    monkeypatch.setattr(manual, "pages", lambda: pages)
    pdf = tmp_path / "manual.pdf"
    _pdf_with_chapter_targets(
        pdf, {"what": 2, "ways": 2, "window": 3, "glossary": 4, "ref-mesh": 5}, dictionary=True
    )

    def overlay(path: Path, chapters: list[str], total: int, language: str) -> Path:
        """Die Seitendarstellung bleibt hier unabhängig vom Qt-Zeichner."""
        _pdf_with_chapter_targets(path, {}, dictionary=True)
        return path

    monkeypatch.setattr(make_manual, "_overlay", overlay)
    make_manual._stamp(pdf, "de")
    reader = PdfReader(pdf)

    parts: list[tuple[str, int]] = []
    chapters: list[list[tuple[str, int]]] = []
    for item in reader.outline:
        if isinstance(item, list):
            chapters.append(
                [(str(one.title), reader.get_destination_page_number(one)) for one in item]
            )
        else:
            parts.append((str(item.title), reader.get_destination_page_number(item)))
    assert parts == [("Erste Schritte", 2), ("Funktionen", 3), ("Nachschlagen", 4)]
    assert chapters == [
        [("Was Solidon ist", 2), ("Die vier Wege", 2)],
        [("Das Fenster", 3)],
        [("Wörterbuch", 4), ("Netz", 5)],
    ]
    first_part, first_chapters = reader.outline[0], reader.outline[1]
    assert (first_part.typ, float(first_part.top)) == ("/XYZ", 842.0), "Teil: Kopf der Seite"
    assert [one.typ for one in first_chapters] == ["/Fit", "/Fit"], "Kapitel: sein Ziel"
    assert reader.page_mode == "/UseOutlines"


def test_the_raster_count_sees_every_picture_once_also_inside_a_form(tmp_path: Path) -> None:
    """Die Zählung hinter der Bedingung, dass das PDF jedes Bildschirmfoto trägt.

    Ein Bild, das zwei Seiten zeigen, zählt einmal; eines in einem
    Formularobjekt zählt mit; ein Formular ohne Bild zählt nicht.
    """
    from pypdf import PdfWriter
    from pypdf.generic import (
        ArrayObject,
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
        NumberObject,
    )

    from tools.make_manual import _raster_images

    writer = PdfWriter()

    def xobject(subtype: str, data: bytes, **entries: object) -> object:
        item = DecodedStreamObject()
        item.set_data(data)
        item[NameObject("/Type")] = NameObject("/XObject")
        item[NameObject("/Subtype")] = NameObject(subtype)
        for key, value in entries.items():
            item[NameObject(f"/{key}")] = value
        return writer._add_object(item)

    def image() -> object:
        return xobject(
            "/Image",
            b"\x00\x00\x00",
            Width=NumberObject(1),
            Height=NumberObject(1),
            ColorSpace=NameObject("/DeviceRGB"),
            BitsPerComponent=NumberObject(8),
        )

    def form(inner: dict[str, object]) -> object:
        return xobject(
            "/Form",
            b"",
            BBox=ArrayObject([NumberObject(0), NumberObject(0), NumberObject(9), NumberObject(9)]),
            Resources=DictionaryObject(
                {
                    NameObject("/XObject"): DictionaryObject(
                        {NameObject(name): value for name, value in inner.items()}
                    )
                }
            ),
        )

    shared = image()
    for used in (
        {"/Im0": shared},
        {"/Im0": shared, "/Fm0": form({"/Im1": image()})},
        {"/Fm1": form({})},
    ):
        page = writer.add_blank_page(width=100, height=100)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/XObject"): DictionaryObject(
                    {NameObject(name): value for name, value in used.items()}
                )
            }
        )
    pdf = tmp_path / "bilder.pdf"
    with pdf.open("wb") as stream:
        writer.write(stream)

    assert _raster_images(pdf) == 2


def test_the_print_takes_a_screenshot_as_jpeg_only_where_that_is_lighter(tmp_path: Path) -> None:
    """Der Druck liest eine Kopie der Seite; die Website behält ihre Dateien.

    Chromium reicht ein JPEG unverändert ins PDF durch und legt jedes andere
    Rasterbild verlustfrei gepackt ab. Ein Bild mit Verlauf und Rauschen — wie
    ein Schrittbild über dem abgedunkelten Modell — packt sich verlustfrei
    schlecht und geht als JPEG in den Druck. Eine ruhige Fläche packt sich
    verlustfrei kleiner und bleibt, ebenso ein Bild mit Durchsicht, denn JPEG
    kennt keine. Die Verweise um die Bildschirmfotos fallen weg, relative
    Adressen werden absolut; Sprünge im Dokument und Adressen im Netz bleiben.
    """
    import random
    import re

    from PySide6.QtGui import QColor, QImage

    from tools.make_manual import _print_copy

    site = tmp_path / "website"
    images = site / "handbuch" / "de"
    images.mkdir(parents=True)
    flat = QImage(320, 200, QImage.Format.Format_RGB32)
    flat.fill(QColor(30, 32, 36))
    busy = QImage(320, 200, QImage.Format.Format_RGB32)
    clear = QImage(320, 200, QImage.Format.Format_ARGB32)
    noise = random.Random(5)
    for y in range(200):
        for x in range(320):
            shade = 40 + x // 4 + y // 4 + noise.randrange(-6, 7)
            busy.setPixelColor(x, y, QColor(shade, shade + 10, shade + 25))
            clear.setPixelColor(x, y, QColor(shade, shade + 10, shade + 25, 120 if x < 40 else 255))
    for name, picture in (("flat", flat), ("busy", busy), ("clear", clear)):
        assert picture.save(str(images / f"{name}.png"))
    page = site / "handbuch.html"
    page.write_text(
        '<link rel="stylesheet" href="style.css">'
        '<p><a href="#what">Sprung</a> <a href="https://solidon3d.de/">Netz</a></p>'
        + "".join(
            f'<figure class="screenshot"><div class="stage"><a href="handbuch/de/{name}.png">'
            f'<img src="handbuch/de/{name}.png" alt="{name}" loading="lazy"></a></div></figure>'
            for name in ("flat", "busy", "clear")
        )
        + '<figure><picture><source srcset="handbuch/de/drawing-dark.svg" '
        'media="(prefers-color-scheme: dark)"><img src="handbuch/de/drawing.svg" '
        'alt="drawing"></picture></figure>',
        encoding="utf-8",
    )
    before = page.read_bytes()
    folder = tmp_path / "druck"
    folder.mkdir()

    copy, shown = _print_copy(page, folder)
    html = copy.read_text(encoding="utf-8")
    sources = {alt: source for source, alt in re.findall(r'<img src="([^"]+)" alt="(\w+)"', html)}

    assert copy.parent == folder
    assert page.read_bytes() == before, "die Seite der Website bleibt, wie sie ist"
    assert sorted(path.name for path in images.iterdir()) == ["busy.png", "clear.png", "flat.png"]
    assert shown == 3
    assert sources["busy"] == (folder / "busy.jpg").as_uri()
    assert (folder / "busy.jpg").read_bytes()[:2] == b"\xff\xd8"
    assert QImage(str(folder / "busy.jpg")).size() == busy.size()
    assert sources["flat"] == (images / "flat.png").resolve().as_uri()
    assert sources["clear"] == (images / "clear.png").resolve().as_uri()
    assert sources["drawing"] == (images / "drawing.svg").resolve().as_uri()
    assert f'srcset="{(images / "drawing-dark.svg").resolve().as_uri()}"' in html
    assert f'href="{(site / "style.css").resolve().as_uri()}"' in html
    assert 'href="#what"' in html and 'href="https://solidon3d.de/"' in html
    assert html.count('<div class="stage"><img src=') == 3, "kein Verweis um ein Bildschirmfoto"
