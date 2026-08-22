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
