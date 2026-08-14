"""Bezeichner bleiben englisch (Bauplan §4.1, AGENTS.md).

Ohne diese Prüfung wächst eine Mischung wie ``bausteinRegistry`` oder
``wall_staerke`` von selbst herein. Angesehen werden nur Bezeichner —
Zeichenketten tragen die deutschen Oberflächentexte und sollen deutsch sein.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import app

PACKAGE_DIR = Path(app.__file__).parent

#: Deutsche Wörter, die nie ein Abschnitt eines Bezeichners sein dürfen.
#:
#: Die Liste ist kuratiert und nicht vollständig — sie kann es nicht sein, denn
#: ein deutsches Wörterbuch träfe zu viel: `object`, `radius`, `position` und
#: `parameter` stehen wörtlich in den deutschen Oberflächentexten und sind
#: trotzdem englische Bezeichner. Was hier steht, ist eindeutig.
GERMAN_WORDS = frozenset(
    {
        "abstand",
        "anzahl",
        "bauteil",
        "baustein",
        "beschreibung",
        "beschriftung",
        "breite",
        "datei",
        "dicke",
        "direkt",
        "durchmesser",
        "ebene",
        "einheit",
        "ende",
        "farbe",
        "fehler",
        "feld",
        "hinweis",
        "kante",
        "koerper",
        "loch",
        "menge",
        "meldung",
        "minuten",
        "mutter",
        "objekt",
        "ordner",
        "pfad",
        "punkt",
        "schicht",
        "schraube",
        "schritt",
        "seite",
        "spalte",
        "stelle",
        "stift",
        "stunde",
        "szene",
        "teil",
        "tiefe",
        "wand",
        "wert",
        "zahl",
        "zeile",
    }
)

#: Deutsche Stämme, die eindeutig genug sind, um innerhalb von Bezeichnern
#: gesucht zu werden.
GERMAN_STEMS = (
    "aenderung",
    "auswahl",
    "bohrung",
    "dezimier",
    "druck",
    "einstellung",
    "flaeche",
    "gemerkt",
    "geschlossen",
    "geschrieben",
    "gespeichert",
    "groesse",
    "hoehe",
    "laenge",
    "loesch",
    "pruef",
    "staerke",
    "stueck",
    "versetz",
    "waehl",
)

#: Deutsche Beugungen der Wörter oben. ``wert`` stand in der Liste und
#: ``werte`` kam trotzdem durch: geprüft wurde auf Gleichheit, und ein
#: deutscher Plural ist kein anderes Wort. Nur ``-e``, ``-en`` und ``-n`` —
#: ``-er`` und ``-s`` erzeugen aus ``wand`` und ``loch`` die englischen
#: ``wander`` und ``lochs``.
GERMAN_ENDINGS = ("e", "en", "n")
INFLECTED = frozenset(
    word + ending
    for word in GERMAN_WORDS
    for ending in GERMAN_ENDINGS
    if word + ending not in GERMAN_WORDS
)

UMLAUTS = "äöüÄÖÜß"


def source_files() -> list[Path]:
    return sorted(PACKAGE_DIR.rglob("*.py"))


def identifiers_of(tree: ast.AST) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.append((node.name, node.lineno))
        elif isinstance(node, ast.arg):
            found.append((node.arg, node.lineno))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            found.append((node.id, node.lineno))
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            found.append((node.attr, node.lineno))
        elif isinstance(node, ast.alias) and node.asname:
            found.append((node.asname, node.lineno))
    return found


def offences_in(name: str) -> list[str]:
    lowered = name.lower()
    hits = [word for word in lowered.split("_") if word in GERMAN_WORDS | INFLECTED]
    hits += [stem for stem in GERMAN_STEMS if stem in lowered]
    return hits


@pytest.mark.parametrize("path", source_files(), ids=lambda path: path.name)
def test_identifiers_are_english(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        f"{path.name}:{line} {name} -> {', '.join(hits)}"
        for name, line in identifiers_of(tree)
        if (hits := offences_in(name))
    ]
    assert not offenders, "\n".join(offenders)


@pytest.mark.parametrize("path", source_files(), ids=lambda path: path.name)
def test_identifiers_have_no_umlauts(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        f"{path.name}:{line} {name}"
        for name, line in identifiers_of(tree)
        if any(character in UMLAUTS for character in name)
    ]
    assert not offenders, "\n".join(offenders)


def test_module_names_are_english() -> None:
    offenders = [
        f"{path.name} -> {', '.join(hits)}"
        for path in source_files()
        if (hits := offences_in(path.stem))
    ]
    assert not offenders, "\n".join(offenders)


def test_the_check_would_catch_a_violation() -> None:
    """Ein Wächter, der laut scheitert, falls die Wortlisten je geleert werden."""
    assert offences_in("wall_staerke")
    assert offences_in("baustein_registry")
    assert offences_in("hoehe")
    assert not offences_in("detail_view")
    assert not offences_in("part_registry")


def test_the_check_sees_through_a_german_plural() -> None:
    """``wert`` stand in der Liste, ``werte`` kam durch — ein Jahr lang.

    Gesucht wurde auf Gleichheit, und der Plural ist damit ein anderes Wort.
    Die vier hier standen so im Bestand oder hätten es jederzeit gekonnt.
    """
    assert offences_in("werte")
    assert offences_in("schritte")
    assert offences_in("kanten")
    assert offences_in("objekte")


def test_the_check_leaves_english_words_alone() -> None:
    """Die Gegenprobe zur Beugung, und der Grund für die Wahl der Endungen.

    ``wand`` und ``loch`` stehen in der Liste; mit ``-er`` und ``-s`` daran
    entstünden ``wander`` und ``lochs``, und beide sind englisch. Deshalb
    kennt `GERMAN_ENDINGS` nur ``-e``, ``-en`` und ``-n``.
    """
    assert not offences_in("wander")
    assert not offences_in("wanders")
    assert not offences_in("lochs")
    assert not offences_in("ends")
