"""Das Register am Kopf der ROADMAP gegen die Punkte darunter — und das Archiv.

`ROADMAP.md` war bis zum 22.08.2026 zweierlei zugleich: die Arbeitsliste und die
Geschichte dieses Projekts, und das Zweite überwog weit — von 112 Abschnitten
enthielten 78 keinen einzigen offenen Punkt. Seither ist die Geschichte nach
`ROADMAP-ARCHIV.md` getrennt, und die Arbeitsliste behält den Kopf, das
Register, die Phasen und jeden Abschnitt mit einem offenen Punkt.

Damit prüft diese Datei zwei Dinge statt einem:

* **Das Register gegen die Punkte darunter** — nicht über die Gesamtzahl,
  sondern je Abschnitt, denn eine Summe stimmt auch dann noch, wenn ein Punkt
  zugeht und anderswo einer aufgeht. Ein von Hand gepflegtes Verzeichnis driftet
  vom Bestand ab, und ab dem ersten Fehler liest es niemand mehr.
* **Das Archiv gegen seine eigene Zusage** — dort steht kein offener Punkt.
  Sonst wäre der Schnitt eine zweite Liste, in der niemand sucht, und das
  Register könnte sie nicht führen, weil es diese Datei nicht liest.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

ROADMAP = Path(__file__).resolve().parents[1] / "ROADMAP.md"
ARCHIVE = Path(__file__).resolve().parents[1] / "ROADMAP-ARCHIV.md"

#: Die Überschrift, unter der das Register steht.
REGISTER = "## Was offen ist"

#: Ein offener Punkt — `[ ]` offen oder `[~]` in Arbeit. `[x]` ist fertig und
#: gehört nicht hierher.
_OPEN = re.compile(r"^\s*-\s*\[[ ~]\]")

#: Die Trennzeile einer Markdown-Tabelle, `|---|---|---|`.
_DIVIDER = re.compile(r"^\|[\s:|-]+\|$")


def _lines() -> list[str]:
    return ROADMAP.read_text(encoding="utf-8").splitlines()


def _archive_lines() -> list[str]:
    return ARCHIVE.read_text(encoding="utf-8").splitlines()


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


def test_the_archive_holds_nothing_that_is_still_open() -> None:
    """Im Archiv steht kein offener Punkt — sonst ist es ein zweites Register.

    Der Schnitt zwischen Arbeitsliste und Archiv trägt nur, solange er an einer
    prüfbaren Eigenschaft hängt. Wandert ein Punkt ins Archiv, weil sein
    Abschnitt sonst abgeschlossen war, sucht ihn dort niemand — und das Register
    in ``ROADMAP.md`` kann ihn nicht führen, denn es liest diese Datei nicht.

    Der Test greift auf ``_OPEN`` und damit auf ``[ ]`` **und** ``[~]``, auch
    eingerückt: Ein halbfertiger Punkt im Archiv ist derselbe Fehler wie ein
    offener.
    """
    lines = _archive_lines()
    assert len(lines) > 100, (
        f"{ARCHIVE.name} liefert nur {len(lines)} Zeilen — dann sagt dieser Test "
        "nichts darüber aus, ob das Archiv offene Punkte führt."
    )
    open_points = [line.strip() for line in lines if _OPEN.match(line)]

    assert not open_points, (
        f"{ARCHIVE.name} führt {len(open_points)} offene Punkte. Sie gehören "
        f"nach {ROADMAP.name}, mit einer Zeile im Register:\n"
        + "\n".join(f"  {point[:100]}" for point in open_points[:5])
    )


def _anchor(heading: str) -> str:
    """Die Sprungmarke, die ein Markdown-Betrachter aus einer Überschrift baut.

    Kleinschreibung, Satzzeichen fallen weg, Leerzeichen werden Bindestriche —
    und zwar **je Leerzeichen einer**. Der erste Entwurf des Verzeichnisses hat
    Trennerfolgen zu einem Bindestrich eingedampft und Punkte zu Bindestrichen
    gemacht; 59 von 78 Marken zeigten damit ins Leere. Ein Verzeichnis, dessen
    Einträge nicht springen, ist schlechter als keines: Es sieht benutzbar aus.
    """
    stripped = re.sub(r"[^\w\s-]", "", heading.lower(), flags=re.UNICODE)
    return stripped.strip().replace(" ", "-")


def test_the_archive_keeps_a_directory_of_what_it_holds() -> None:
    """Ohne Verzeichnis ist das Archiv ein Textblock von siebentausend Zeilen.

    Gesucht wird darin über den Text — aber wer wissen will, *ob* zu einem Thema
    schon einmal jemand dagewesen ist, liest Überschriften und keine Volltexte.
    Jeder ``##``-Abschnitt muss deshalb im Verzeichnis am Kopf auftauchen, und
    seine Marke muss auch treffen.
    """
    lines = _archive_lines()
    headings = [line[3:].strip() for line in lines if line.startswith("## ")]
    directory = "\n".join(line for line in lines if line.startswith("| "))

    missing = [name for name in headings if f"[{name}]" not in directory]
    assert not missing, (
        f"{ARCHIVE.name} führt {len(missing)} Abschnitte, die im Verzeichnis am "
        f"Kopf fehlen: {missing[:5]}"
    )

    astray = [name for name in headings if f"[{name}](#{_anchor(name)})" not in directory]
    assert not astray, (
        f"{len(astray)} Einträge im Verzeichnis springen ins Leere — ihre Marke "
        f"passt nicht zur Überschrift: {astray[:5]}"
    )


def test_the_existing_support_mailbox_is_not_listed_as_open_work() -> None:
    """Ein bestätigtes Postfach bleibt nicht als vermeintliche Aufgabe stehen."""
    text = ROADMAP.read_text(encoding="utf-8")

    assert "Postfach `support@solidon3d.de` samt SPF/DMARC" not in text
    assert "das Postfach support@solidon3d.de anlegen" not in text
    assert "Das Postfach `support@solidon3d.de` existiert" in text
