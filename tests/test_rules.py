"""Die Regelsammlung als eigenes Produkt (Bauplan §39)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.knowledge import rules


def test_the_rules_of_the_plan_are_all_there() -> None:
    """§39 zählt acht Regeln auf; hier sind sie Daten, keine Prosa in einem
    Prompt.
    """
    loaded = rules.load()
    titles = " ".join(rule.title for rule in loaded.rules)

    for expected in ("Mindestwandstärke", "Fasen", "Toleranzen", "Hauptmaße", "Überlappung"):
        assert expected in titles
    assert len(loaded.rules) >= 8


def test_every_rule_carries_a_version_and_a_text() -> None:
    loaded = rules.load()

    assert loaded.version
    for rule in loaded.rules:
        assert rule.id and rule.title and rule.text
        assert rule.applies_to, f"{rule.id} says nothing about where it applies"


def test_the_version_is_what_a_transaction_records() -> None:
    """§26.4: ohne das lässt sich später nicht sagen, unter welcher Regel eine
    Op entstand.
    """
    assert rules.version() == rules.load().version


def test_the_change_log_is_kept_with_the_rules() -> None:
    loaded = rules.load()

    assert loaded.changes, "§39 wants date, reason and suite result for every change"
    for change in loaded.changes:
        assert change.date and change.reason


def test_rules_can_be_asked_for_by_topic() -> None:
    geometry = rules.load().for_topic("geometry")

    assert geometry
    assert all("geometry" in rule.applies_to for rule in geometry)


def test_the_set_reads_as_one_block_for_the_prompt() -> None:
    text = rules.load().as_text()

    assert text.count("\n") >= 7
    assert "Mindestwandstärke" in text
    assert "\n\n" not in text, "one rule per line keeps the prompt short"


def test_a_broken_file_is_not_swallowed(tmp_path: Path) -> None:
    path = tmp_path / "rules.toml"
    path.write_text('version = "2"\n[[rules]]\ntitle = "ohne id"\n', encoding="utf-8")

    with pytest.raises(KeyError):
        rules.load(path)


def test_a_own_file_can_be_loaded_without_touching_the_cache(tmp_path: Path) -> None:
    path = tmp_path / "rules.toml"
    path.write_text(
        'version = "9"\n[[rules]]\nid = "x"\ntitle = "T"\ntext = "t"\napplies_to = ["geometry"]\n',
        encoding="utf-8",
    )

    assert rules.load(path).version == "9"
    assert rules.load().version != "9", "the shipped set stays the shipped set"


def test_the_manual_can_read_the_rules_in_every_language() -> None:
    """§39 nennt die Regelsammlung das eigentliche Produkt — ein Produkt, das
    im Handbuch einer Sprache deutsch bleibt, ist dort eine Lücke.
    """
    from app.i18n.catalog import available_languages

    collection = rules.load()
    assert collection.rules, (
        "die Regelsammlung ist leer — dann prüft dieser Test keine einzige "
        "Übersetzung, sondern nur, dass eine leere Schleife durchläuft"
    )
    for language in available_languages():
        if language == "de":
            continue
        missing = [rule.id for rule in collection.rules if language not in rule.translations]
        assert not missing, f"ohne Version für {language}: {missing}"
        for rule in collection.rules:
            title, text = rule.translations[language]
            assert rule.reading(language) == (title, " ".join(text.split()))


def test_the_agent_keeps_reading_german_whatever_the_language() -> None:
    """Zwei Versionen einer Regel wären zwei Wahrheiten, und die Suite-Quote
    hinge davon ab, welche gerade gilt. Die Übersetzung ist fürs Handbuch da.
    """
    collection = rules.load()
    for rule in collection.rules:
        assert rule.title in rule.as_line()
        for title, _text in rule.translations.values():
            assert title not in rule.as_line()
    assert "Mindestwandstärke" in collection.as_text()


def test_a_rule_without_a_translation_falls_back_to_the_original() -> None:
    """Ein Handbuch mit einem fremdsprachigen Absatz ist besser als eines mit
    einer Lücke."""
    plain = rules.Rule(id="x", title="Titel", text="Ein Satz.")
    assert plain.reading("en") == ("Titel", "Ein Satz.")
