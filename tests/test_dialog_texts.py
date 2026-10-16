"""Was ein Dialog vorn sagt, passt zu dem, was davor stand (FD-112, FD-119).

Ohne Fenster: Gefragt werden Register und Kataloge, aus denen der Dialog seine
Beschriftungen und seinen ersten Satz baut.
"""

from __future__ import annotations

import pytest

from app.core import bootstrap
from app.core.errors import GIVE_THICKNESS
from app.core.registry import REGISTRY
from app.core.registry.surfaces import sentences
from app.i18n import get_language, set_language, tr
from app.i18n.catalog import available_languages, install_language


def test_no_field_is_named_like_the_place_line_in_front() -> None:
    """FD-119: Am Prüfstück hießen die Lesezeile vorn und die Auswahl darunter
    beide „Stelle“ — welches Feld legt die Stelle fest? Eine Beschriftung steht
    nur einmal im Dialog (``fenster.md``, „Formulare“)."""
    from app.ui.op_dialog import place_fields

    bootstrap.load_operations()
    place = str(tr("Stelle"))
    with_place = [spec for spec in REGISTRY.all() if place_fields(spec) is not None]
    assert with_place, "keine Operation mit Lesezeile — die Prüfung prüft nichts"
    clashing = sorted(
        spec.name
        for spec in with_place
        if any(str(entry.title) == place for entry in spec.params.spec())
    )
    assert clashing == [], f"Feld „Stelle“ neben der Lesezeile „Stelle“: {clashing}"


@pytest.mark.parametrize("language", sorted(available_languages()))
def test_give_thickness_opens_a_dialog_that_says_thickness_first(language: str) -> None:
    """FD-112: *Dicke geben* öffnet *Offene Fläche schließen*; die erste Zeile des
    Dialogs sagt jetzt, dass er der Fläche eine Dicke gibt — in jeder Sprache
    mit dem Wort des Knopfs."""
    bootstrap.load_operations()
    before = get_language()
    try:
        install_language(language)
        set_language(language)
        # Die Wörter des Knopfs ab fünf Buchstaben: das Nomen („Dicke“,
        # „thickness“, „grosor“), nicht das kurze Verb davor.
        words = [word for word in str(GIVE_THICKNESS.label).casefold().split() if len(word) >= 5]
        lead = sentences(str(REGISTRY.get("thicken").doc))[0].casefold()
        assert words, f"{language}: der Knopf hat kein tragendes Wort"
        assert any(word in lead for word in words), f"{language}: {words} fehlt in „{lead}“"
    finally:
        install_language(before)
        set_language(before)
