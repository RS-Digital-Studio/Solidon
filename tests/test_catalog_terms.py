"""Begriffe in den Katalogen: Schreibweise und Trennschärfe einzelner Wörter.

`test_translations.py` prüft Vollständigkeit und Form jedes Eintrags; hier
stehen die Zusagen über **bestimmte** Wörter, die in einer Sprache anders
gelesen werden als im Deutschen — die Merkmalsarten als Kartenkopf, und zwei
deutsche Fachwörter, die in einer Sprache nicht zusammenfallen dürfen.
"""

from __future__ import annotations

import pytest

from app.core.registry.registry import FEATURE_TITLES
from app.i18n.catalog import available_languages, read_catalog

#: Die Übersetzungssprachen — ohne Deutsch, das ist die Quelle.
LANGUAGES = tuple(language for language in available_languages() if language != "de")


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_feature_kind_starts_with_a_capital_letter(language: str) -> None:
    """FD-98: Eine Merkmalsart steht als Kopf von Karte und Baumzeile da.

    „peg · Ø6,00 mm“ sah neben „Hole“ und „Face“ wie ein Fehler aus: Der
    Eintrag „Zapfen“ war in fünf Sprachen klein übersetzt. Der Kopf beginnt
    groß wie im Deutschen; braucht ein Satz das Wort klein, bekommt er einen
    eigenen Schlüssel mit Kontext.
    """
    catalog = read_catalog(language)
    small = {
        str(title.msgid): catalog.get(str(title.msgid), "")
        for title in FEATURE_TITLES.values()
        if not catalog.get(str(title.msgid), "")[:1].isupper()
    }
    assert not small, f"{language}: Merkmalsarten beginnen klein: {small}"
