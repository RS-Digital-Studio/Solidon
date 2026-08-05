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

import pytest

from app.core import figures, manual, markup
from app.core.bootstrap import load_operations
from app.core.registry.registry import CATEGORIES, REGISTRY
from app.i18n import tr

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.ui.manual_window import ManualWindow


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


# --- was drinsteht ---------------------------------------------------------------


def test_every_category_has_a_chapter() -> None:
    """Eine neue Kategorie kann nicht ohne Kapitel bleiben — sie wird erzeugt."""
    chapters = {page.key for page in manual.pages() if page.generated}

    assert chapters == set(REGISTRY.by_category())


def test_every_operation_appears_by_name() -> None:
    """62 Operationen, 62 Einträge. Ohne das wäre das Handbuch eine Auswahl."""
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
