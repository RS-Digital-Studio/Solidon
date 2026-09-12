"""Das Zwillingswerkzeug an Fällen, deren Ausgang bekannt ist.

**Warum es diese Datei gibt.** `ROADMAP-ARCHIV.md` hält den Satz vom
24.08.2026: *„Ein Prüfer für Doppelungen, der den bekannten Fall nicht findet,
ist kaputt; einer, der ihn findet, hat seine erste Zusicherung."* Der
Duplikat-Sucher jenes Tages war brauchbar, weil er zuerst den Fall fand, den
eine andere Sitzung eine Stunde vorher gemeldet hatte.

`tools/twin_scan.py` sucht nicht nach Fehlern, sondern nach Kandidaten — und
ein Suchwerkzeug hat die gefährlichste Fehlerart der drei aus
`.claude/memory/messwerkzeug-misst-sich-selbst.md`: **es schweigt**. Zu wenig
zu finden sieht aus wie nichts zu finden. Geprüft wird deshalb, dass es
gepflanzte Fälle findet, und dass es einen leeren Baum als Fehler meldet statt
als Ergebnis.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import twin_scan


def _tree(root: Path, files: dict[str, str]) -> Path:
    """Ein kleiner Baum mit vorgegebenem Inhalt."""
    tree = root / "baum"
    tree.mkdir()
    for name, text in files.items():
        (tree / name).write_text(text, encoding="utf-8")
    return tree


def test_a_planted_pair_of_constants_is_found(tmp_path: Path) -> None:
    """Dieselbe Zahl unter demselben Namen in zwei Dateien — Frage 1a.

    Der Fall, der `tests/test_shared_constants.py` veranlasst hat, in seiner
    kleinsten Form.
    """
    tree = _tree(
        tmp_path,
        {
            "eins.py": "OVERLAP_MM = 0.05\n",
            "zwei.py": "OVERLAP_MM = 0.05\n",
            "drei.py": "ANDERES = 7.25\n",
        },
    )
    found = twin_scan.constants(twin_scan.parsed(twin_scan.sources(tree)))

    assert len(found["OVERLAP_MM"]) == 2, found["OVERLAP_MM"]
    assert len(found["ANDERES"]) == 1, "eine einzelne Konstante ist kein Zwilling"


def test_a_planted_twin_body_is_found_and_a_shared_docstring_is_not(tmp_path: Path) -> None:
    """Zwei gleiche Körper werden gefunden — zwei gleiche *Docstrings* nicht.

    **Der zweite Teil ist der wichtigere und kostete am 07.09.2026 eine falsche
    Zahl.** Gezählt wurde zuerst in Zeilen, und das Zeilenmaß nimmt den
    Docstring mit: `wants_bed_coordinates` und `PrintDisclosureResult.may_continue`
    sind beide `return True` unter zehn Zeilen Erklärung und wurden als
    Zwillinge gemeldet. Gezählt werden **Anweisungen des Körpers**.
    """
    tree = _tree(
        tmp_path,
        {
            "eins.py": (
                "def rechne(a, b):\n"
                '    """Ein Satz."""\n'
                "    zwischen = a * 2\n"
                "    dazu = zwischen + b\n"
                "    geteilt = dazu / 3\n"
                "    return geteilt\n"
            ),
            "zwei.py": (
                "def rechne_auch(a, b):\n"
                '    """Ein ganz anderer Satz, viel länger, damit die Zeilen abweichen.\n'
                "\n"
                "    Und noch eine Zeile Erklärung dazu.\n"
                '    """\n'
                "    zwischen = a * 2\n"
                "    dazu = zwischen + b\n"
                "    geteilt = dazu / 3\n"
                "    return geteilt\n"
            ),
            "drei.py": (
                "def kurz(a):\n"
                '    """Derselbe lange Docstring wie nebenan, nur ein anderer Körper.\n'
                "\n"
                "    Und noch eine Zeile Erklärung dazu.\n"
                '    """\n'
                "    return True\n"
            ),
            "vier.py": (
                "def kurz_auch(a):\n"
                '    """Derselbe lange Docstring wie nebenan, nur ein anderer Körper.\n'
                "\n"
                "    Und noch eine Zeile Erklärung dazu.\n"
                '    """\n'
                "    return True\n"
            ),
        },
    )
    entries = twin_scan.functions(twin_scan.parsed(twin_scan.sources(tree)))
    assert len(entries) == 4, entries

    twins = twin_scan.grouped([e for e in entries if e["statements"] >= 4], "exact")
    assert len(twins) == 1, f"genau ein Paar erwartet: {twins}"
    assert {e["name"] for e in twins[0]} == {"rechne", "rechne_auch"}

    einzeiler = [e for e in entries if e["name"].startswith("kurz")]
    assert all(e["statements"] == 1 for e in einzeiler), einzeiler
    assert not twin_scan.grouped(
        [e for e in entries if e["statements"] >= 4 and e["name"].startswith("kurz")], "exact"
    ), "zwei gleiche Docstrings über zwei `return True` sind kein Zwillingspaar"


def test_a_renamed_twin_is_found_only_by_the_structural_question(tmp_path: Path) -> None:
    """Gleiche Struktur, andere Namen und Zahlen — Frage 3 statt Frage 2."""
    tree = _tree(
        tmp_path,
        {
            "eins.py": (
                "def erste(wert):\n"
                "    grenze = 12\n"
                "    if wert > grenze:\n"
                "        return grenze\n"
                "    return wert\n"
            ),
            "zwei.py": (
                "def zweite(zahl):\n"
                "    schranke = 40\n"
                "    if zahl > schranke:\n"
                "        return schranke\n"
                "    return zahl\n"
            ),
        },
    )
    entries = twin_scan.functions(twin_scan.parsed(twin_scan.sources(tree)))

    assert not twin_scan.grouped(entries, "exact"), "wortgleich sind sie nicht"
    strukturell = twin_scan.grouped(entries, "normalised")
    assert len(strukturell) == 1, f"strukturgleich schon: {strukturell}"


def test_a_number_written_as_a_product_is_read(tmp_path: Path) -> None:
    """``64 * 1024`` ist ein Wert und keine Rechnung, die niemand liest.

    Am 27.08.2026 fiel ``MAX_ANSWER_BYTES`` aus der Erhebung, weil
    ``literal_eval`` an dem Produkt scheitert — der Wächter schwieg über einen
    Zwilling, den er hätte melden müssen.
    """
    tree = _tree(
        tmp_path,
        {"eins.py": "GRENZE_BYTES = 64 * 1024\n", "zwei.py": "GRENZE_BYTES = 65536\n"},
    )
    found = twin_scan.constants(twin_scan.parsed(twin_scan.sources(tree)))

    werte = {value for _file, _line, value in found["GRENZE_BYTES"]}
    assert werte == {65536}, f"beide Schreibweisen sind derselbe Wert: {werte}"


def test_an_empty_tree_is_an_error_and_not_a_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Null Funde über null Dateien ist kein „alles in Ordnung".

    Der Anlass, 07.09.2026: Ein Lauf mit einem Git-Bash-Pfad (``/c/Users/…``)
    fand unter Windows keine Datei und meldete keine Zwillinge. Die Ausgabe
    sah aus wie ein sauberes Ergebnis.
    """
    leer = tmp_path / "leer"
    leer.mkdir()

    assert twin_scan.main([str(leer)]) == 1
    assert "keine Messung" in capsys.readouterr().err


def test_a_path_that_is_no_directory_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Und ein Pfad, den diese Plattform nicht kennt, wird benannt."""
    assert twin_scan.main([str(tmp_path / "gibt-es-nicht")]) == 2
    fehler = capsys.readouterr().err
    assert "Kein Verzeichnis" in fehler
    assert "/c/Users" in fehler, "der Hinweis auf den Bash-Pfad ist der eigentliche Dienst"


def test_the_tool_finds_the_case_it_was_built_for(tmp_path: Path) -> None:
    """Der bekannte Fall aus dem Bestand, in seiner kleinsten Form nachgebaut.

    Zwei Module leiten dieselbe Frage her — ``hole`` ist ein Hohlraum, ``pin``
    ist Materie —, und genau so stand es bis zum 07.09.2026 in
    ``geom/prepare_ops`` und ``perceive/relations``. Findet das Werkzeug das
    nicht, taugt es für keine Durchsicht.
    """
    körper = (
        "    if merkmal.kind == 'hole':\n"
        "        return True\n"
        "    if merkmal.kind == 'pin':\n"
        "        return False\n"
        "    return bool(merkmal.params.get('recess', False))\n"
    )
    tree = _tree(
        tmp_path,
        {
            "geometrie.py": f"def _ist_hohlraum(merkmal):\n{körper}",
            "wahrnehmung.py": f"def ist_hohlraum(merkmal):\n{körper}",
        },
    )
    entries = twin_scan.functions(twin_scan.parsed(twin_scan.sources(tree)))
    assert {e["statements"] for e in entries} == {3}, (
        "drei Anweisungen — und genau deshalb liegt die Mindestgröße des Werkzeugs "
        f"bei drei und nicht bei vier: {entries}"
    )
    twins = twin_scan.grouped([e for e in entries if e["statements"] >= 3], "exact")

    assert len(twins) == 1, f"der bekannte Fall wird gefunden: {twins}"
    assert {e["file"].rsplit("/", 1)[-1] for e in twins[0]} == {"geometrie.py", "wahrnehmung.py"}


@pytest.mark.parametrize(
    ("wert", "sagt_etwas"),
    [
        (2, False),
        (100, False),
        (0.5, False),
        (0.866, True),
        (65536, True),
        ("de.rsdigital.solidon3d.activation", True),
        ("mm", False),
        (True, False),
    ],
)
def test_only_a_telling_value_counts_as_a_hint(wert: object, sagt_etwas: bool) -> None:
    """Frage 1c wäre ohne diese Grenze Rauschen: Jede 2 stünde als Zwilling da."""
    assert twin_scan.telling(wert) is sagt_etwas, wert
