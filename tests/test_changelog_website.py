"""Der Versionsverlauf auf der Website kommt aus derselben Quelle wie die App."""

from __future__ import annotations

import html
import re
import sys

import pytest

from app.branding import APP_VERSION
from app.core import changes
from app.i18n.catalog import available_languages
from tools import make_changelog
from tools.make_changelog import page_path, path_for, render_page, version_id


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_every_language_has_a_generated_page(language: str) -> None:
    page = path_for(language)

    assert page.is_file(), f"{page_path(language)} fehlt — make_changelog.py ausführen"
    assert page.read_text(encoding="utf-8") == render_page(language)


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_the_picker_offers_every_bundled_version(language: str) -> None:
    text = path_for(language).read_text(encoding="utf-8")
    offered = tuple(re.findall(r'<option value="([^"]+)"', text))
    expected = tuple(entry.version for entry in changes.history(language))

    assert offered == expected
    assert re.search(rf'<option value="{re.escape(APP_VERSION)}" selected>', text)


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_every_customer_point_reaches_the_page(language: str) -> None:
    text = html.unescape(path_for(language).read_text(encoding="utf-8"))

    for entry in changes.history(language):
        assert f'id="{version_id(entry.version)}"' in text
        for group in entry.groups:
            if group.title:
                assert f"<h3>{group.title}</h3>" in text
            for point in group.points:
                assert f"<li>{point}</li>" in text


def test_the_page_works_as_a_full_history_without_script() -> None:
    text = path_for("de").read_text(encoding="utf-8")

    assert "<noscript>" in text
    assert ".release-card[hidden]{display:block!important}" in text
    assert text.count("data-changelog-entry") == len(changes.history("de"))


def test_an_additional_language_needs_no_generator_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein weiterer Katalog reicht; feste Tabellen dürfen den Release nicht stoppen."""
    languages = (*available_languages(), "nl")
    monkeypatch.setattr(make_changelog, "available_languages", lambda: languages)

    text = render_page("nl")

    assert '<html lang="nl">' in text
    assert 'href="https://solidon3d.de/nl/changelog.html"' in text
    assert 'href="/nl/changelog.html"' in text
    assert ">nl</a>" in text


def test_each_release_starts_with_a_plain_language_summary() -> None:
    text = path_for("de").read_text(encoding="utf-8")

    for entry in changes.history("de"):
        changes_word = "Neuerung" if len(entry.points) == 1 else "Neuerungen"
        topics_word = "Thema" if len(entry.groups) == 1 else "Themen"
        summary = f"{len(entry.points)} {changes_word} · {len(entry.groups)} {topics_word}"
        assert f'<p class="release-summary">{summary}</p>' in text
        assert f'data-announcement="{entry.version}: {summary}"' in text

    assert 'data-changelog-status aria-live="polite"' in text


def test_an_empty_history_becomes_a_customer_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(make_changelog.changes, "history", lambda _language: ())

    text = render_page("de")

    assert "Für diese Version liegt kein Verlauf bei." in text
    assert "data-changelog-select" not in text


def test_the_release_run_always_rebuilds_the_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Veröffentlichung kennt keinen vergessbaren Changelog-Schritt."""
    from tools import make_download

    calls = []
    monkeypatch.setattr(sys, "argv", ["make_download.py"])
    monkeypatch.setattr(make_download, "write_changelog_pages", lambda: calls.append(True) or ())
    monkeypatch.setattr(make_download, "write_pages", lambda _packages: None)
    monkeypatch.setattr(make_download, "write_version", lambda _packages: None)

    assert make_download.main() == 0
    assert calls == [True]
