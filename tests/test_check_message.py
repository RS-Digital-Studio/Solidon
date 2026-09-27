"""Der Wächter über die Commit-Meldungen: Umlaute im Deutsch, Namen bleiben Namen.

`.githooks/commit-msg` ruft `tools/check_message.py`. Er soll „prueft“ und
„gross“ fangen — aber nicht `uebersetzung.md` oder den Zweig
`uebergabe-gesamtpruefung`, die so heißen müssen: Beide hielten an einem Tag
zwei Commits an, die kein Wort falsch geschrieben hatten.
"""

from __future__ import annotations

from tools import check_message


def test_a_substitute_in_german_text_is_found() -> None:
    assert check_message.findings("Das prueft die Datei") == {"prueft": "prüft"}
    assert check_message.findings("Die Platte ist zu gross.") == {"gross": "groß"}, (
        "ein Wort am Satzende ist kein Dateiname"
    )


def test_correct_umlauts_pass() -> None:
    assert check_message.findings("Die Regel prüft die Größe und löscht nichts.") == {}


def test_names_are_not_german_text() -> None:
    for text in (
        "Die Regel steht in `uebersetzung.md`.",
        "Der Zweig `uebergabe-gesamtpruefung` wartet.",
        "siehe .claude/rules/uebersetzung.md",
        "uebersetzung.md lädt für app/i18n/",
        "konzepte\\begruendungen\\regel-uebersetzung.md",
    ):
        assert check_message.findings(text) == {}, text


def test_a_name_does_not_hide_the_german_around_it() -> None:
    assert check_message.findings("`uebersetzung.md` prueft nichts") == {"prueft": "prüft"}
