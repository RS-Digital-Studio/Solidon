"""Der Verlauf in der Anwendung — *Hilfe → Neuerungen* (Bauplan §37.2).

Bis 0.1.3 kannte die Anwendung ihre eigenen Neuerungen nicht: Die Punkte kamen
über die Versionsdatei vom Server und erschienen nur im Update-Fenster, also
nur dann, wenn es etwas Neueres gab. Wer den Hinweis weggeklickt hatte oder die
neueste Fassung benutzte, kam an sie nicht mehr heran.

Geprüft wird deshalb beides: dass der Kern den Verlauf **aus dem Paket** liest
(ohne Netz, ohne Server) und dass das Fenster ihn zeigt.
"""

from __future__ import annotations

import html
from pathlib import Path

import pytest

from app.branding import APP_VERSION
from app.core import changes
from app.i18n.catalog import available_languages

# --- der Kern -------------------------------------------------------------------------


def test_the_bundled_history_is_not_empty() -> None:
    """Die Grundmenge, gegen die alles Weitere prüft.

    Ohne diese Zusicherung wären die Tests darunter grün, sobald der Ordner
    fehlt — sie filterten dann über nichts (siehe `.claude/rules/tests.md`).
    """
    assert changes.history("de"), "no bundled changelog — the tests below would check nothing"


def test_the_current_version_has_points() -> None:
    """Ein Bau ohne Abschnitt zeigte dem Kunden einen leeren Kasten.

    Derselbe Anspruch wie in ``test_changelog.py``, hier aber über den Weg,
    den die **Anwendung** nimmt — nicht über den des Bauwerkzeugs.
    """
    assert changes.points_for(APP_VERSION, "de"), f"no section for {APP_VERSION} in changelog/de.md"


def test_every_language_is_read_through_the_same_door() -> None:
    for language in ("de", "en", "es", "fr", "it", "pt"):
        assert changes.points_for(APP_VERSION, language), language


def test_an_unknown_language_falls_back_to_the_source() -> None:
    """Ein deutscher Satz ist besser als eine Überschrift ohne Inhalt."""
    assert changes.history("kl") == changes.history("de")


def test_a_missing_folder_is_no_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Paket ohne Verlauf zeigt einen Satz, keinen Stapelabzug."""
    changes.forget_cache()
    monkeypatch.setattr(changes, "folder", lambda: Path("gibtsnicht"))
    try:
        assert changes.history("de") == ()
    finally:
        changes.forget_cache()


def test_the_newest_version_comes_first() -> None:
    """Gelesen wird von oben; wer den Dialog öffnet, sieht das Neueste zuerst."""
    entries = changes.history("de")

    assert entries[0].version == APP_VERSION


# --- das Fenster ----------------------------------------------------------------------

pytest.importorskip("PySide6")

from app.ui.changes_dialog import ChangesDialog, history_html  # noqa: E402


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_the_dialog_shows_every_version(language: str) -> None:
    """Jede Sprache, nicht nur die Quelle — und gegen den entmaskierten Text.

    Zwei Dinge, die der Test bis zum 27.08.2026 nicht konnte. Er las allein
    ``de``, und er verglich den rohen Punkt gegen fertiges HTML. Dort steht
    ein Apostroph aber als ``&#x27;`` und ein gerades Anführungszeichen als
    ``&quot;`` — richtig so, denn beides sind Sonderzeichen, und der
    Nachbartest unten besteht für ``<`` ausdrücklich darauf.

    Der rohe Vergleich hätte damit jeden französischen Punkt mit ``l'…``
    verworfen, und davon gibt es 189. Gefragt ist, ob der Punkt im Fenster
    ankommt, nicht wie er unterwegs geschrieben wird — also entmaskieren.
    """
    entries = changes.history(language)

    text = html.unescape(history_html(entries))

    for entry in entries:
        assert entry.version in text, entry.version
        for point in entry.points:
            assert point[:30] in text, f"{language}: {point[:30]}"


def test_the_running_version_is_marked() -> None:
    """Ohne Marke sucht der Kunde in einer Liste von Nummern die eigene."""
    text = history_html(changes.history("de"))

    assert "diese Version" in text


def test_a_point_with_a_pointed_bracket_survives() -> None:
    """„Wände unter 2 Extrusionsbreiten“ ließe sich mit ``<`` schreiben.

    Als Auszeichnung gelesen verschwände der Satz ab dort bis zum nächsten
    ``>``. Das ist kein Angriff, nur ein Punkt, der dann fehlt.
    """
    entry = changes.Entry(
        version="9.9.9",
        groups=(changes.Group(title="", points=("Wände unter <2 Breiten werden gemeldet.",)),),
    )

    text = history_html((entry,))

    assert "&lt;2 Breiten" in text


def test_the_dialog_opens_without_a_network(qt_app: object) -> None:
    """Der Verlauf liegt im Paket — dieser Weg fragt nichts nach draußen.

    Gefragt wird mit ``isHidden`` und nicht mit ``isVisible``: Ein Widget in
    einem Dialog, der nie gezeigt wurde, ist **nie** sichtbar, und der Test
    prüfte damit die Testumgebung statt den Dialog. Was hier zu prüfen ist, ist
    der gewählte Zweig — der Verlauf steht da, also nicht der leere Satz.
    """
    dialog = ChangesDialog()

    assert dialog.windowTitle()
    assert APP_VERSION in dialog.headline.text()
    assert not dialog.scroller.isHidden(), "history is bundled, so the list belongs on screen"
    assert dialog.empty.isHidden(), "the empty notice belongs to a package without a history"


def test_the_dialog_offers_every_version_in_a_picker(qt_app: object) -> None:
    """Der lange Verlauf bleibt erreichbar, ohne als eine Wand aufzugehen."""
    entries = changes.history("de")
    dialog = ChangesDialog()

    offered = tuple(
        dialog.version_choice.itemData(index) for index in range(dialog.version_choice.count())
    )

    assert offered == tuple(entry.version for entry in entries)
    assert dialog.version_choice.currentData() == APP_VERSION


def test_choosing_a_version_replaces_the_visible_entry(qt_app: object) -> None:
    """Die Auswahl ist ein Filter und kein Sprung in einer langen Textwand."""
    entries = changes.history("de")
    dialog = ChangesDialog()
    last = len(entries) - 1

    dialog.version_choice.setCurrentIndex(last)

    assert f">{entries[last].version}</h3>" in dialog.body.text()
    assert f">{entries[0].version}" not in dialog.body.text()
    assert dialog.summary.text() == (
        f"{len(entries[last].points)} Neuerungen · {len(entries[last].groups)} Thema"
    )
