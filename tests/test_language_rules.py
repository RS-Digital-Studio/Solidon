"""Bezeichner bleiben englisch (Bauplan §4.1, AGENTS.md).

Ohne diese Prüfung wächst eine Mischung wie ``bausteinRegistry`` oder
``wall_staerke`` von selbst herein. Angesehen werden nur Bezeichner —
Zeichenketten tragen die deutschen Oberflächentexte und sollen deutsch sein.
"""

from __future__ import annotations

import ast
import itertools
from pathlib import Path

import pytest

import app

PACKAGE_DIR = Path(app.__file__).parent
TOOLS_DIR = PACKAGE_DIR.parent / "tools"

#: Deutsche Wörter, die nie ein Abschnitt eines Bezeichners sein dürfen.
#:
#: Die Liste ist kuratiert und nicht vollständig — sie kann es nicht sein, denn
#: ein deutsches Wörterbuch träfe zu viel: `object`, `radius`, `position` und
#: `parameter` stehen wörtlich in den deutschen Oberflächentexten und sind
#: trotzdem englische Bezeichner. Was hier steht, ist eindeutig.
GERMAN_WORDS = frozenset(
    {
        "abstand",
        "anlass",
        "anzahl",
        "arten",
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
        "vorlage",
        "wand",
        "wert",
        "wurzel",
        "zahl",
        "zeile",
    }
)

#: Deutsche Stämme, die eindeutig genug sind, um innerhalb von Bezeichnern
#: gesucht zu werden.
#:
#: **Das ist eine Stichprobe und kein vollständiger Test — und das ist keine
#: Nachlässigkeit, sondern gemessen.** Am 23.08.2026 sind vier deutsche
#: Bezeichner in einer einzigen Sitzung durchgerutscht (``schuldige``,
#: ``letzter``, ``grund``, ``frei``), weil keiner davon auf dieser Liste stand.
#:
#: Der naheliegende Ausweg wurde probiert und ist gescheitert: die Liste aus
#: den **deutschen Kommentaren des Projekts** zu gewinnen. Sie lieferte 1319
#: Kandidaten und meldete 2758 angebliche Verstöße — darunter ``index``,
#: ``material``, ``parameter``, ``value``, ``export``, ``message``, ``scene``
#: und ``profile``. **Deutsch und Englisch überlappen bei technischen Wörtern
#: zu stark**, um sie ohne echtes Wörterbuch zu trennen, und ein Wörterbuch
#: wäre eine neue Abhängigkeit für einen Test.
#:
#: Also bleibt es bei der kuratierten Liste, und daraus folgt die Pflegeregel:
#: **Wer ein deutsches Wort in einem Bezeichner findet, trägt seinen Stamm
#: hier ein.** Der Test fängt, was schon einmal jemand falsch gemacht hat —
#: mehr verspricht er nicht, und weniger auch nicht.
GERMAN_STEMS = (
    "aenderung",
    "auswahl",
    "bohrung",
    "dezimier",
    "druck",
    "einstellung",
    "flaeche",
    "frei",
    "gemerkt",
    "geschlossen",
    "geschrieben",
    "gespeichert",
    "grund",
    "groesse",
    "hoehe",
    "laenge",
    "letzt",
    "loesch",
    "pruef",
    "schuld",
    "staerke",
    "stelle",
    "stueck",
    "versetz",
    "waehl",
    "werkzeug",
    "zeile",
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
    """Die Dateien, gegen die die Sprachprüfung läuft.

    **Die Zusicherung steht hier und nicht in den Tests.** Vier Tests werden
    über diese Liste parametrisiert, und eine leere Parameterliste macht sie
    nicht rot — pytest sammelt dann schlicht **null Tests**, meldet
    ``no tests ran`` und gibt Exit 5. Ein Lauf, der nichts geprüft hat, sieht
    damit aus wie einer, der nichts gefunden hat.

    Eine Zusicherung *in* den Tests fängt das nicht: Sie liefe nie. Und eine je
    Datei wäre falsch — eine leere ``__init__.py`` hat legitim keine Bezeichner,
    was elf Fehlschläge gab, als es einmal so versucht wurde.
    """
    gefunden = sorted({*PACKAGE_DIR.rglob("*.py"), *TOOLS_DIR.glob("*.py")})
    assert len(gefunden) > 50, (
        f"nur {len(gefunden)} Quelldateien gefunden — stimmen {PACKAGE_DIR} "
        f"und {TOOLS_DIR} noch? Die Sprachprüfung hätte sonst nichts zu prüfen."
    )
    return gefunden


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


#: Wörter, an denen eine Sprache zu erkennen ist, ohne den Satz zu verstehen.
#:
#: Funktionswörter und keine Fachbegriffe: „solid", „dots" oder „Encoding"
#: stehen in beiden Sprachen gleich da, „the" und „der" nicht.
GERMAN_MARKERS = frozenset(
    (
        "der",
        "die",
        "das",
        "und",
        "nicht",
        "ein",
        "eine",
        "ist",
        "dem",
        "den",
        "mit",
        "von",
        "auf",
        "für",
        "wird",
        "was",
        "wer",
        "sich",
        "nur",
        "nach",
        "aus",
        "als",
        "auch",
        "dann",
        "über",
        "kein",
        "keine",
        "sie",
        "es",
        "im",
        "zu",
        "bei",
        "noch",
        "wie",
        "damit",
        "ohne",
        "steht",
        "bleibt",
    )
)
ENGLISH_MARKERS = frozenset(
    (
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "from",
        "which",
        "when",
        "what",
        "are",
        "not",
        "but",
        "only",
        "any",
        "can",
        "cannot",
        "its",
        "their",
        "them",
        "would",
        "also",
        "shown",
        "print",
        "stays",
        "either",
    )
)


def field_docstrings(tree: ast.AST) -> list[tuple[int, str]]:
    """Die Docstrings, die hinter einem Feld stehen — mit Zeile.

    ``ast.get_docstring`` sieht sie nicht: Es kennt Modul, Klasse und Funktion,
    und ein Feld-Docstring ist syntaktisch nur ein Ausdruck, der auf eine
    Zuweisung folgt. Genau deshalb braucht es diese Funktion.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for before, after in itertools.pairwise(body):
            if not isinstance(before, ast.AnnAssign | ast.Assign):
                continue
            if not isinstance(after, ast.Expr):
                continue
            value = after.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                found.append((after.lineno, value.value))
    return found


def reads_as_english(text: str) -> bool:
    """Ob dieser Text eher englisch als deutsch ist.

    Gezählt, nicht geparst: zwei Sätze Funktionswörter, und die Mehrheit
    entscheidet. Zwei Treffer sind die Untergrenze, damit ein deutscher Satz
    mit einem zitierten ``for`` nicht umkippt. Gemessen am Bestand hat diese
    Schwelle 454 von 457 Feld-Docstrings richtig durchgelassen und die drei
    englischen gefunden.
    """
    words = {word.strip(".,;:()`*\"'").lower() for word in text.split()}
    english = len(words & ENGLISH_MARKERS)
    return english >= 2 and english > len(words & GERMAN_MARKERS)


@pytest.mark.parametrize("path", source_files(), ids=lambda path: path.name)
def test_field_docstrings_are_german(path: Path) -> None:
    """Auch der Satz hinter einem Feld ist Doku, und Doku ist deutsch.

    **Warum das eine eigene Prüfung braucht.** Die Sprachregelung trennt
    Bezeichner (englisch) von Docstrings (deutsch), und geprüft wurden bisher
    nur die Bezeichner. Für die Docstrings stand in `CLAUDE.md`, der Bestand
    sei „vollständig nachgezogen" — und für Modul, Klasse und Funktion stimmt
    das auch, nachgezählt am 21.08.2026: null englische unter allen.

    Drei sind trotzdem übrig geblieben, alle in derselben Nische: der Satz
    hinter einem Dataclass-Feld. ``ast.get_docstring`` sieht ihn nicht, also
    sah ihn keine Prüfung — zwei in ``palette.py`` (``pattern``, ``symbol``)
    und einer in ``settings.py`` (``display_unit``). Gefunden beim Durchgang
    durch den Viewport, beim Nachlesen, ob die Differenzansicht eine zweite
    Kodierung neben der Farbe führt (§19.1 — sie führt drei).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        f"{path.name}:{line} {text.splitlines()[0][:60]}"
        for line, text in field_docstrings(tree)
        if len(text) >= 25 and reads_as_english(text)
    ]
    assert not offenders, "englische Feld-Docstrings:" + chr(10) + chr(10).join(offenders)
