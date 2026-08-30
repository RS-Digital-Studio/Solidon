"""Der Changelog, den das Update-Fenster zeigt (Bauplan §37.2).

Er ist die einzige Stelle, an der die Anwendung erzählt, was sich geändert
hat — und die einzige, die dabei nicht aus dem Code kommt, sondern von Hand
geschrieben wird. Also prüft diese Datei, was ein Mensch beim Schreiben
vergisst: eine Sprache, einen Punkt, die Version von gestern.

Und den Ton. „Nur Wichtiges, verständlich" lässt sich nicht messen; was sich
messen lässt, ist das Gegenteil davon — ein Modulname, eine Paragraphennummer,
ein Commit-Titel. Wer eines davon hineinschreibt, hat den Adressaten verwechselt.
"""

from __future__ import annotations

import re

import pytest

from app.branding import APP_VERSION
from app.core.updates import MAX_CHANGES, MAX_FIELD_LENGTH
from app.i18n import SOURCE_LANGUAGE
from app.i18n.catalog import available_languages
from tools.make_download import CHANGELOG, changelog_for, changes_for


def test_the_current_version_has_a_section() -> None:
    """Ohne Abschnitt zeigt das Update-Fenster nur den Hinweistext.

    Kein Fehler, aber eine vertane Gelegenheit: Wer vor der Frage steht, ob er
    aktualisieren soll, bekommt dann nichts, woran er sie beantworten könnte.
    """
    points = changelog_for(APP_VERSION, SOURCE_LANGUAGE)

    assert points, (
        f"changelog/{SOURCE_LANGUAGE}.md hat keinen Abschnitt '## {APP_VERSION}' — "
        "nach jeder Versionserhöhung gehört einer dazu"
    )


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_every_language_carries_the_same_points(language: str) -> None:
    """Eine Sprache, die fehlt, fällt auf Deutsch zurück — sichtbar mitten im
    Fenster."""
    source = changelog_for(APP_VERSION, SOURCE_LANGUAGE)
    points = changelog_for(APP_VERSION, language)

    assert points, f"changelog/{language}.md kennt {APP_VERSION} nicht"
    assert len(points) == len(source), (
        f"{language}: {len(points)} Punkte gegen {len(source)} in {SOURCE_LANGUAGE}"
    )


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_every_language_carries_the_same_groups(language: str) -> None:
    """Dieselbe Gliederung in jeder Sprache — Gruppen samt Reihenfolge.

    Seit 0.2.0 gliedern ``###``-Überschriften die Punkte (Entscheidung
    Robert, 26.08.2026). Die Titel sind übersetzt und dürfen sich
    unterscheiden; was gleich sein muss, ist die **Struktur**: gleich viele
    Gruppen, in jeder dieselbe Punktzahl an derselben Stelle. Sonst zeigt
    ein italienisches Fenster andere Bündel als das deutsche daneben — und
    ein verrutschter Punkt fiele in keiner Zählung der flachen Liste auf.
    """
    from app.core import changes

    def shape(lang: str) -> list[int]:
        for entry in changes.history(lang):
            if entry.version == APP_VERSION:
                return [len(group.points) for group in entry.groups]
        return []

    source = shape(SOURCE_LANGUAGE)
    assert source, f"{SOURCE_LANGUAGE} kennt {APP_VERSION} nicht"
    assert shape(language) == source, (
        f"{language}: Gruppenform {shape(language)} gegen {source} in {SOURCE_LANGUAGE}"
    )
    for entry in changes.history(language):
        if entry.version == APP_VERSION:
            untitled = [i for i, group in enumerate(entry.groups) if not group.title]
            assert not untitled, f"{language}: Gruppe(n) ohne Überschrift an {untitled}"


#: Ab dieser Fassung tragen die Abschnitte ``###``-Gruppen.
FIRST_GROUPED = (0, 2, 0)


def _as_numbers(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def test_an_old_section_still_reads_as_one_list() -> None:
    """Die Fassungen vor 0.2.0 tragen keine Gruppen und bleiben gültig.

    Ihre Punkte stehen in genau einer Gruppe ohne Titel — so rendert der
    Dialog sie wie eh und je als eine Liste unter der Versionszeile.

    **Geprüft wird „vor 0.2.0", nicht „nicht die aktuelle".** Hier stand der
    zweite Filter, und solange 0.2.0 die aktuelle Fassung war, kam dasselbe
    heraus. Mit 0.2.1 wurde der gegliederte 0.2.0-Abschnitt zur „älteren
    Fassung", und der Test schlug an, obwohl sich an ihm nichts geändert
    hatte — ein Test, der den nächsten Versionssprung verhindert, prüft die
    falsche Sache.
    """
    from app.core import changes

    older = [
        entry
        for entry in changes.history(SOURCE_LANGUAGE)
        if _as_numbers(entry.version) < FIRST_GROUPED
    ]
    assert older, "es gibt keine ältere Fassung zum Prüfen"
    for entry in older:
        assert len(entry.groups) == 1 and entry.groups[0].title == "", (
            f"{entry.version}: unerwartete Gliederung"
        )
        assert entry.points == entry.groups[0].points


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_a_point_fits_into_the_window(language: str) -> None:
    """Die Anwendung stutzt jedes Feld auf :data:`MAX_FIELD_LENGTH`.

    Ein Punkt, der darüber liegt, endet im Fenster mitten im Wort — und zwar
    ohne dass es beim Schreiben jemand sieht.
    """
    for point in changelog_for(APP_VERSION, language):
        assert len(point) <= MAX_FIELD_LENGTH, f"{language}: zu lang ({len(point)}): {point[:60]} …"


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_no_point_speaks_like_a_commit(language: str) -> None:
    """Der Adressat sitzt vor dem Programm, nicht im Repository."""
    verboten = re.compile(r"\.py\b|§|\bcommit\b|\bregistry\b|\bOpContext\b|\bmanifold3d\b")

    for point in changelog_for(APP_VERSION, language):
        assert not verboten.search(point), f"{language}: spricht wie ein Commit: {point}"


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_no_point_talks_about_internal_tests(language: str) -> None:
    """Der Kunde bekommt das Ergebnis, nicht den Nachweis aus der Entwicklung.

    Der Wächter liest den gesamten Verlauf. Der Fund vom 29.08.2026 stand in
    0.2.1 und wäre einer Prüfung nur der aktuellen Fassung entgangen.
    """
    from app.core import changes

    forbidden = re.compile(
        r"\b(?:(?:bereichs|regressions|geometrie|einheiten|integrations|abnahme|"
        r"leistungs|oberflächen)?test(?:s|e|en)?|tested|testing|"
        r"pruebas?|prova sull'intervallo|testes?)\b",
        re.IGNORECASE,
    )

    for entry in changes.history(language):
        for point in entry.points:
            assert not forbidden.search(point), (
                f"{language} {entry.version}: spricht über interne Tests: {point}"
            )


def test_windows_update_distinguishes_the_in_app_path_from_manual_setup() -> None:
    """Die Start-Auswahl des manuellen Setups widerspricht dem Update nicht.

    Am 29.08.2026 klang der Punkt so, als gäbe es diese Auswahl gar nicht.
    Gemeint ist aber nur der aus Solidon gestartete stille Lauf: Er öffnet die
    Anwendung selbst wieder, während ein doppelt angeklicktes Setup seine
    gewohnte Schlussseite behält.
    """
    from app.core import changes

    release = next(entry for entry in changes.history("de") if entry.version == "0.2.2")
    point = next(point for point in release.points if "Windows-Update" in point)

    assert "aus Solidon gestartet" in point
    assert "manuell gestarteten Setup" in point


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_a_point_is_a_sentence(language: str) -> None:
    """Kein Stichwort und keine halbe Zeile: Was hier steht, wird gelesen."""
    for point in changelog_for(APP_VERSION, language):
        assert point[0].isupper(), f"{language}: fängt klein an: {point}"
        assert point.endswith((".", "!", "?")), f"{language}: hört ohne Punkt auf: {point}"


def test_the_window_never_sees_more_than_it_shows() -> None:
    """Die Grenze der Anwendung und die Zahl der Punkte gehören zusammen."""
    assert len(changelog_for(APP_VERSION, SOURCE_LANGUAGE)) <= MAX_CHANGES


def test_all_languages_are_gathered_at_once() -> None:
    """Was ``make_download`` in die Versionsdatei schreibt, ist vollständig."""
    gathered = changes_for(APP_VERSION)

    assert set(gathered) == set(available_languages())


def test_the_folder_holds_no_stray_language() -> None:
    """Eine Datei ohne Katalog wäre eine Sprache, die es in der Anwendung nicht
    gibt — und ihre Punkte sähe nie jemand."""
    files = {path.stem for path in CHANGELOG.glob("*.md")}

    assert files <= set(available_languages()), (
        f"ohne Katalog: {files - set(available_languages())}"
    )


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_no_language_uses_a_straight_quotation_mark(language: str) -> None:
    """Ein gerades ``"`` ist in keiner der sechs Sprachen die richtige Wahl.

    Deutsch setzt „…“, Englisch “…”, die drei romanischen «…» oder “…” — und
    am 27.08.2026 standen trotzdem zwölf gerade in ``de.md`` und achtzehn in
    ``en.md``, mitten zwischen den typografischen. Aufgefallen sind sie an
    einem Test, der etwas ganz anderes prüfte: Ein gerades ``"`` wird in HTML
    zu ``&quot;`` maskiert, ein typografisches nicht, und daran zerbrach der
    Textvergleich im Neuerungen-Fenster.

    Dieser Weg ist mit dem Entmaskieren dort verschwunden — er war ohnehin
    ein Zufallsfund und kein Wächter. Der hier ist einer.

    **Apostrophe fallen ausdrücklich nicht darunter.** Der gerade ist der
    Bestand: 189 in ``fr.md`` gegen 55 typografische, 9 zu 0 in ``en.md``.
    Eine Massenänderung daran gewönne nichts und bräche jede offene Arbeit
    an denselben Zeilen.
    """
    text = (CHANGELOG / f"{language}.md").read_text(encoding="utf-8")

    getroffen = [nummer for nummer, zeile in enumerate(text.splitlines(), 1) if '"' in zeile]

    assert not getroffen, (
        f"changelog/{language}.md: gerades Anführungszeichen in Zeile(n) "
        f"{', '.join(str(n) for n in getroffen)}"
    )


#: Wörter, hinter denen in den Presseanschreiben eine Punktzahl steht —
#: deutsch und englisch. Kuratiert: Eine Zahl steht in solchen Texten auch
#: für eine Version, ein Datum oder einen Preis, und nur die Zahl **dieser**
#: Wendungen ist der Changelog.
ZAEHLWORTE = (
    "ausgewählte",
    "für Nutzer sichtbare",
    "Nutzeränderungen",
    "curated",
    "user-facing",
)

#: „insgesamt 241." — die Zahl steht auch ohne Zählwort dahinter, wenn der
#: Satz davor schon eines genannt hat.
NACKTE_ZAHL = re.compile(r"(?:insgesamt|contains|now contains|accounts for)\s+(\d{2,4})")


def test_the_press_drafts_count_the_same_changes() -> None:
    """Die Zahl in den Anschreiben ist die des Changelogs — heute noch.

    Am 29.08.2026 standen morgens 220 in vier Entwürfen und abends waren es
    241: Ein Nachtrag von einundzwanzig Punkten hatte die Zahl überholt, und
    keine Prüfung sah es. Eine falsche Zahl in einer Mail an eine Redaktion ist
    teurer als eine im Programm — sie lässt sich nicht mehr zurücknehmen.

    Erlaubt sind genau zwei Werte: die Punkte der aktuellen Version und die
    Summe über alle. Was ein Entwurf sonst als Änderungszahl nennt, ist ein
    Fund.
    """
    ordner = CHANGELOG.parent / "marketing" / f"presse-{APP_VERSION}"
    if not ordner.is_dir():
        pytest.skip(f"keine Presseentwürfe für {APP_VERSION}")

    quelle = (CHANGELOG / f"{SOURCE_LANGUAGE}.md").read_text(encoding="utf-8")
    versionen = re.findall(r"^## (\S+)", quelle, re.MULTILINE)
    # **Nur bis zur beworbenen Fassung.** Ein Anschreiben für 0.2.2 nennt die
    # Zahl zum Stand 0.2.2; sobald der Abschnitt der nächsten Fassung
    # entsteht, wäre jede Zahl darin falsch, obwohl niemand sie angefasst hat.
    # Gemessen am 31.08.2026: Die vierzehn Punkte von 0.2.3 machten 263 zu
    # 277, und die Entwürfe hatten recht behalten, nicht der Test.
    if APP_VERSION in versionen:
        versionen = versionen[versionen.index(APP_VERSION) :]
    dieser_stand = len(changelog_for(APP_VERSION, SOURCE_LANGUAGE))
    alle = sum(len(changelog_for(version, SOURCE_LANGUAGE)) for version in versionen)
    assert alle >= dieser_stand > 0, f"gezählt wurden {alle} und {dieser_stand}"
    erlaubt = {dieser_stand, alle}

    # Auch die Versandseite: Sie trägt heute keine Zahl, und morgen
    # vielleicht doch — eine Datei, die niemand prüft, ist der Ort, an dem
    # die nächste falsche steht.
    entwürfe = sorted(
        pfad for muster in ("*.eml", "*.md", "*.html") for pfad in ordner.glob(muster)
    )
    assert entwürfe, f"{ordner} ist leer — dann prüft der Test nichts"

    funde = []
    gefundene_zahlen = 0
    for pfad in entwürfe:
        text = " ".join(pfad.read_text(encoding="utf-8").split())
        zahlen = [
            int(treffer)
            for wort in ZAEHLWORTE
            for treffer in re.findall(rf"(\d{{2,4}})\s+{re.escape(wort)}", text)
        ]
        zahlen += [int(treffer) for treffer in NACKTE_ZAHL.findall(text)]
        gefundene_zahlen += len(zahlen)
        funde += [
            f"{pfad.name}: nennt {zahl}, richtig wären {sorted(erlaubt)}"
            for zahl in zahlen
            if zahl not in erlaubt
        ]

    assert gefundene_zahlen >= 4, (
        f"nur {gefundene_zahlen} Zahlen gefunden — das Muster greift nicht mehr, "
        f"oder die Entwürfe nennen keine Zahl mehr"
    )
    assert not funde, "\n".join(funde)
