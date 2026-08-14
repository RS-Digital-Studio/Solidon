"""Das Register am Kopf der ROADMAP gegen die Punkte darunter.

`ROADMAP.md` ist zweierlei zugleich: die Arbeitsliste und die Geschichte dieses
Projekts. Das Zweite überwiegt inzwischen deutlich — der weitaus größte Teil der
Datei enthält keinen einzigen offenen Punkt, und die, die es gibt, stehen über
die ganze Länge verstreut. Wer wissen will, was offen ist, hat sie deshalb bis
heute gesucht statt nachgeschlagen.

Das Register oben ist die Abkürzung. Es ist aber nur so viel wert, wie man ihm
glaubt: Ein von Hand gepflegtes Verzeichnis driftet vom Bestand ab, und ab dem
ersten Fehler liest es niemand mehr. Diese Datei hält beides zusammen — nicht
über die Gesamtzahl, sondern je Abschnitt, denn eine Summe stimmt auch dann noch,
wenn ein Punkt zugeht und anderswo einer aufgeht.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

ROADMAP = Path(__file__).resolve().parents[1] / "ROADMAP.md"

#: Die Überschrift, unter der das Register steht.
REGISTER = "## Was offen ist"

#: Ein offener Punkt — `[ ]` offen oder `[~]` in Arbeit. `[x]` ist fertig und
#: gehört nicht hierher.
_OPEN = re.compile(r"^\s*-\s*\[[ ~]\]")

#: Die Trennzeile einer Markdown-Tabelle, `|---|---|---|`.
_DIVIDER = re.compile(r"^\|[\s:|-]+\|$")


def _lines() -> list[str]:
    return ROADMAP.read_text(encoding="utf-8").splitlines()


def _split() -> tuple[list[str], list[str]]:
    """Das Register und alles darunter, getrennt.

    Getrennt wird an der nächsten Überschrift, nicht an einer Zeilenzahl: Das
    Register wächst und schrumpft mit den Punkten, die es führt.
    """
    lines = _lines()
    start = lines.index(REGISTER)
    after = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
    return lines[start:after], lines[after:]


def _register_sections() -> Counter[str]:
    """Wie oft das Register jeden Abschnitt nennt."""
    block, _ = _split()
    counted: Counter[str] = Counter()
    behind_divider = False
    for line in block:
        if _DIVIDER.match(line):
            behind_divider = True
            continue
        if behind_divider and line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            counted[cells[1]] += 1
    return counted


def _actual_sections() -> Counter[str]:
    """Wie viele offene Punkte jeder Abschnitt wirklich trägt."""
    _, body = _split()
    counted: Counter[str] = Counter()
    chapter = ""
    for line in body:
        if line.startswith("## "):
            chapter = line[3:].strip()
        elif _OPEN.match(line):
            counted[chapter] += 1
    return counted


def test_the_register_names_every_section_that_still_has_open_points() -> None:
    """Kein offener Punkt ohne Zeile im Register — und keine Zeile zu viel.

    Gezählt wird je Abschnitt. Eine reine Summe ginge durch, wenn irgendwo ein
    Punkt zugeht und anderswo einer aufgeht — also genau in dem Fall, für den es
    das Register gibt.
    """
    register, actual = _register_sections(), _actual_sections()

    missing = {name: n for name, n in actual.items() if register[name] != n}
    stale = {name: n for name, n in register.items() if actual[name] != n}

    assert not missing and not stale, (
        "Das Register am Kopf der ROADMAP passt nicht mehr zu den Punkten darunter.\n"
        f"In der Datei, aber nicht (so oft) im Register: {missing or '—'}\n"
        f"Im Register, aber nicht (so oft) in der Datei: {stale or '—'}\n"
        "Wer einen Punkt abhakt oder aufmacht, zieht die Tabelle unter "
        f"`{REGISTER}` mit."
    )


def test_every_section_the_register_points_at_exists() -> None:
    """Ein Verweis auf einen Abschnitt, den es nicht gibt, ist eine Sackgasse.

    Abschnitte werden umbenannt — dann zeigt das Register ins Leere, und wer
    danach sucht, findet nichts und glaubt, der Punkt sei erledigt.
    """
    _, body = _split()
    headings = {line[3:].strip() for line in body if line.startswith("## ")}

    for name in _register_sections():
        assert name in headings, (
            f"Das Register nennt den Abschnitt „{name}“, den es in der ROADMAP "
            "nicht gibt. Wurde er umbenannt?"
        )


@pytest.mark.parametrize("column", ["Punkt", "steht unter", "wartet auf"])
def test_the_register_keeps_its_three_columns(column: str) -> None:
    """Die dritte Spalte ist der eigentliche Ertrag.

    „Offen" sagt nur, dass etwas aussteht; erst *worauf es wartet* trennt den
    Punkt, den jemand heute angehen kann, von dem, der auf ein Zertifikat, eine
    Entscheidung oder einen fremden Rechner wartet.
    """
    block, _ = _split()
    header = next(line for line in block if line.startswith("|"))
    assert column in header, (
        f"Die Spalte „{column}“ fehlt im Register. Der Test liest die zweite "
        "Spalte als Abschnitt — eine andere Reihenfolge macht ihn blind."
    )
