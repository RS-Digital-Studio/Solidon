"""Der Update-Hinweis (Bauplan §37.2).

Die Prüfung fragt eine Adresse und zeigt eine Zeile an. Das klingt nach wenig
und ist genau deshalb zu prüfen: was von dort kommt, kommt von einem Server
und nicht aus diesem Programm. Jedes Problem hat „keine Antwort" zu heißen —
nie ein Fehlerdialog, nie ein Start, der daran hängt.
"""

from __future__ import annotations

from typing import Any

from app.core import updates


def answering(payload: dict[str, Any]) -> updates.Transport:
    """Ein Transport, der genau diese Antwort gibt."""

    def fetch(_url: str, _headers: dict[str, str], _payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    return fetch


def test_a_newer_version_is_reported() -> None:
    release = updates.check(fetch=answering({"version": "99.0.0", "url": "https://example.org/"}))

    assert release is not None
    assert release.newer_than()
    assert release.url == "https://example.org/"


def test_a_failing_request_is_simply_no_answer() -> None:
    """Ein Update-Hinweis, der den Start unterbricht, wäre schlimmer als
    keiner."""

    def broken(_url: str, _headers: dict[str, str], _payload: dict[str, Any]) -> dict[str, Any]:
        raise OSError("kein Netz")

    assert updates.check(fetch=broken) is None


def test_a_version_without_content_is_no_answer() -> None:
    assert updates.check(fetch=answering({})) is None
    assert updates.check(fetch=answering({"version": "  "})) is None


def test_a_url_that_is_not_https_is_dropped() -> None:
    """Angezeigt wird nur, was auch eine Adresse ist.

    Das Feld landet in der Statusleiste; ein „url", das keine ist, soll dort
    nicht als eine auftreten.
    """
    release = updates.check(fetch=answering({"version": "99.0", "url": "Rufen Sie 0900 an!"}))

    assert release is not None
    assert release.url == ""


def test_the_fields_cannot_flood_the_status_bar() -> None:
    release = updates.check(fetch=answering({"version": "9" * 5000, "notes": "x" * 5000}))

    assert release is not None
    assert len(release.version) <= updates.MAX_FIELD_LENGTH
    assert len(release.notes) <= updates.MAX_FIELD_LENGTH


def test_an_older_version_is_not_announced() -> None:
    """Kein Downgrade-Hinweis, wenn die eigene Fassung weiter ist."""
    release = updates.check(fetch=answering({"version": "0.0.0"}))

    assert release is not None
    assert not release.newer_than()
