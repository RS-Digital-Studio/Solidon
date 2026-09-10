"""Der Versionsverlauf auf der Website kommt aus derselben Quelle wie die App."""

from __future__ import annotations

import html
import re
import sys

import pytest

from app.core import changes
from app.i18n.catalog import available_languages
from tools import make_changelog
from tools.make_changelog import (
    page_path,
    path_for,
    published_version,
    released_only,
    render_page,
    version_id,
)


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_every_language_has_a_generated_page(language: str) -> None:
    page = path_for(language)

    assert page.is_file(), f"{page_path(language)} fehlt — make_changelog.py ausführen"
    assert page.read_text(encoding="utf-8") == render_page(language)


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_the_picker_offers_every_published_version(language: str) -> None:
    """Jede veröffentlichte Fassung — und keine, die es noch nicht gibt."""
    text = path_for(language).read_text(encoding="utf-8")
    offered = tuple(re.findall(r'<option value="([^"]+)"', text))
    public = published_version()
    expected = tuple(entry.version for entry in released_only(changes.history(language), public))

    assert offered == expected
    assert expected, "an empty picker would make the assertion above meaningless"
    assert re.search(rf'<option value="{re.escape(public)}" selected>', text)


def test_a_version_that_cannot_be_downloaded_stays_off_the_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Was es nicht zu laden gibt, kündigt die Verkaufsseite nicht an.

    **Hier stand das Gegenteil**, und es war so lange harmlos, wie ein
    Abschnitt mit seiner Versionsnummer entstand. Seit dem 09.09.2026 entsteht
    er vorher: Am 10.09. führte die öffentliche Seite 0.4.0 mit
    zweiundsechzig Punkten, während der Download-Kasten 0.3.5 anbot — im
    Auswahlfeld ganz oben und ohne Skript als sichtbare Karte darüber, weil das
    ``<noscript>`` jede versteckte Karte wieder aufklappt.

    Der Kunde bekam damit eine Fassung samt Funktionen angekündigt, die er
    nicht laden konnte und von der jeder Punkt noch fallen durfte
    (Entscheidung Robert, 10.09.2026).
    """
    monkeypatch.setattr(make_changelog, "published_version", lambda: "0.2.2")

    text = render_page("de")

    assert '<option value="0.2.2" selected>0.2.2 — diese Version</option>' in text
    assert '<option value="0.3.0">' not in text
    assert 'data-version="0.2.2"' in text and 'data-version="0.3.0"' not in text
    assert '<option value="0.2.1">' in text, "older versions stay — only newer ones go"


def test_a_missing_public_version_stops_with_the_next_action(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Veröffentlichungsstand darf der Generator kein Badge raten."""
    monkeypatch.setattr(make_changelog, "WEBSITE", tmp_path)

    with pytest.raises(RuntimeError, match=r"version\.json.*make_download\.py"):
        make_changelog.published_version()


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_every_customer_point_reaches_the_page(language: str) -> None:
    text = html.unescape(path_for(language).read_text(encoding="utf-8"))

    for entry in released_only(changes.history(language), published_version()):
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
    assert text.count("data-changelog-entry") == len(
        released_only(changes.history("de"), published_version())
    )


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

    for entry in released_only(changes.history("de"), published_version()):
        changes_word = "Neuerung" if len(entry.points) == 1 else "Neuerungen"
        topics_word = "Thema" if len(entry.groups) == 1 else "Themen"
        summary = f"{len(entry.points)} {changes_word} · {len(entry.groups)} {topics_word}"
        assert f'<p class="release-summary">{summary}</p>' in text
        assert f'data-announcement="{entry.version}: {summary}"' in text

    assert 'data-changelog-status aria-live="polite"' in text


def test_a_public_version_missing_from_history_stops_with_the_next_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(make_changelog, "published_version", lambda: "9.9.9")

    with pytest.raises(
        RuntimeError,
        match=r"veröffentlichte Version 9\.9\.9.*app/core/changes\.py.*erneut",
    ):
        render_page("de")


def test_the_release_run_always_rebuilds_the_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Veröffentlichung kennt keinen vergessbaren Changelog-Schritt."""
    from tools import make_download

    calls = []
    monkeypatch.setattr(sys, "argv", ["make_download.py"])
    monkeypatch.setattr(
        make_download, "write_changelog_pages", lambda: calls.append("changelog") or ()
    )
    monkeypatch.setattr(make_download, "write_pages", lambda _packages: calls.append("pages"))
    monkeypatch.setattr(make_download, "write_version", lambda _packages: calls.append("version"))

    assert make_download.main() == 0
    assert calls == ["pages", "version", "changelog"], (
        "erst die veröffentlichte Version schreiben, dann ihr öffentliches Badge erzeugen"
    )


def test_a_release_with_packages_builds_the_badge_after_version_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auch der echte Paketzweig erzeugt den Verlauf aus dem neuen Stand."""
    from tools import make_download

    calls = []
    package = object()
    monkeypatch.setattr(sys, "argv", ["make_download.py", "solidon-setup.exe"])
    monkeypatch.setattr(make_download, "read_packages", lambda _paths: [package])
    monkeypatch.setattr(
        make_download, "write_pages", lambda packages: calls.append(("pages", packages))
    )
    monkeypatch.setattr(
        make_download, "write_version", lambda packages: calls.append(("version", packages))
    )
    monkeypatch.setattr(
        make_download,
        "write_changelog_pages",
        lambda: calls.append(("changelog", None)) or (),
    )

    assert make_download.main() == 0
    assert [name for name, _value in calls] == ["pages", "version", "changelog"]
