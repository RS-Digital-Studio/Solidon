"""Der Erste eines Monats in der Anzeigesprache (FD-181).

Auf Französisch heißt er „1er“: „1er décembre 2026“. ``QLocale`` kennt nur das
Muster „d MMMM yyyy“ und schrieb „1 décembre 2026“ — im Abschied der Demo, an
jedem Stichtag und jedem Datum, das ``labels.calendar_date`` setzt. Die Regel
gehört zur Sprache, nicht zu einem Text: Sie gilt an der einen Stelle, die das
Datum baut. Die übrigen Sprachen schreiben den Ersten wie jeden Tag (Deutsch
„1.“, Englisch „December 1“, Spanisch „1 de diciembre“, Italienisch
„1 dicembre“, Portugiesisch „1 de dezembro“).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

from app.i18n import get_language, set_language
from app.ui import labels


@pytest.fixture
def language() -> Iterator[None]:
    before = get_language()
    yield
    set_language(before)


@pytest.mark.parametrize(
    ("spoken", "first", "other"),
    [
        ("fr", "1er décembre 2026", "14 octobre 2026"),
        ("de", "1. Dezember 2026", "14. Oktober 2026"),
        ("en", "December 1, 2026", "October 14, 2026"),
        ("es", "1 de diciembre de 2026", "14 de octubre de 2026"),
        ("it", "1 dicembre 2026", "14 ottobre 2026"),
        ("pt", "1 de dezembro de 2026", "14 de outubro de 2026"),
    ],
)
def test_the_first_of_a_month_follows_the_rule_of_its_language(
    language: None, spoken: str, first: str, other: str
) -> None:
    set_language(spoken)
    assert labels.calendar_date(date(2026, 12, 1)) == first
    assert labels.calendar_date(date(2026, 10, 14)) == other


def test_the_ordinal_stays_on_the_day_and_never_on_the_eleventh(language: None) -> None:
    """„11 décembre“ und „21 décembre“ bleiben Zahlen: Nur der Erste ist „1er“."""
    set_language("fr")
    assert labels.calendar_date(date(2026, 12, 11)) == "11 décembre 2026"
    assert labels.calendar_date(date(2026, 12, 21)) == "21 décembre 2026"
    assert labels.calendar_date(date(2027, 1, 1)) == "1er janvier 2027"
