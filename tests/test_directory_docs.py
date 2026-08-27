"""Die Karte je Verzeichnis bleibt vollständig und belegt.

`CLAUDE.md` beschreibt eine Pyramide: Jedes Verzeichnis trägt eine eigene
Karte seines Gebiets, und sie lädt mit, sobald jemand eine Datei darin
anfasst. Eine Pyramide mit Löchern ist keine — wer ein neues Paket anlegt und
die Karte vergisst, hinterlässt genau die Stelle, an der die nächste Sitzung
raten muss.

Zwei Prüfungen also, und beide messen dasselbe Versprechen aus zwei
Richtungen:

* **Vollständigkeit** — jedes Verzeichnis mit Code hat eine Karte.
* **Belegbarkeit** — jeder §-Verweis darin trifft einen Abschnitt des
  Bauplans. `tests/test_plan_references.py` prüft das für den Quelltext und
  liest dafür ausschließlich `*.py`; die Karten sind Markdown und fielen
  durch. Gemessen am 27.08.2026: 161 Nennungen in 33 Dateien, keine davon
  ins Leere — der Wächter hält diesen Stand, er stellt ihn nicht erst her.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "3d-agent-bauplan.md"

#: Eine numerierte Überschrift des Bauplans — dieselbe Vorschrift wie in
#: `test_plan_references.py`, denn es ist dieselbe Frage.
HEADING = re.compile(r"^#{2,5}\s+(\d+(?:\.\d+)*)\.?\s")

#: Ein Verweis: ``§31``, ``§ 17.2``, ``(§2.4)``.
REFERENCE = re.compile(r"§+\s?(\d+(?:\.\d+)*)")

#: Zeilen, die ein **anderes** Dokument nennen, meinen nicht den Bauplan.
OTHER_DOCUMENT = re.compile(r"\bRFC\b|\bKonzept\b|\bISO\b|\bDIN\b", re.IGNORECASE)

#: Verzeichnisse, die keine eigene Karte brauchen.
#:
#: ``comfyui`` ist fremder Code und trägt trotzdem eine — die sagt gerade,
#: dass er fremd ist. Ausgenommen ist er hier, weil seine *Unterordner* keine
#: brauchen: Was dort liegt, gehört TripoSG, nicht uns.
EXEMPT: frozenset[str] = frozenset({"__pycache__", "comfyui"})


def plan_sections() -> set[str]:
    found = set()
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        heading = HEADING.match(line)
        if heading:
            found.add(heading.group(1))
    return found


def documented_folders() -> list[Path]:
    """Jedes Verzeichnis unter ``app/``, in dem eigener Code liegt."""
    folders: list[Path] = []
    for path in sorted((ROOT / "app").rglob("*")):
        if not path.is_dir() or EXEMPT & set(path.parts):
            continue
        if any(child.suffix == ".py" for child in path.iterdir() if child.is_file()):
            folders.append(path)
    return folders


def maps() -> list[Path]:
    """Alle Karten des Repositories — die Arbeitsbäume fremder Sitzungen nicht."""
    skip = {".venv", "build", "dist", "worktrees", "node_modules"}
    return sorted(
        path
        for path in ROOT.rglob("CLAUDE.md")
        if not skip & set(path.parts) and "3D Drucker" not in path.parts
    )


def test_the_plan_and_the_maps_are_both_there() -> None:
    """Ohne diese Zusicherung prüfte alles darunter gegen eine leere Menge."""
    assert PLAN.exists(), "der Bauplan fehlt"
    assert len(plan_sections()) > 100, "das Überschriften-Muster greift nicht"
    assert len(maps()) > 20, f"nur {len(maps())} Karten gefunden — der Suchlauf greift nicht"


def test_every_code_folder_carries_its_own_map() -> None:
    without = [
        folder.relative_to(ROOT).as_posix()
        for folder in documented_folders()
        if not (folder / "CLAUDE.md").exists()
    ]
    assert not without, (
        "Verzeichnisse mit Code, aber ohne CLAUDE.md:\n"
        + "\n".join(f"  {name}" for name in without)
        + "\nDie Pyramide aus CLAUDE.md verlangt je Gebiet eine Karte."
    )


def test_every_reference_in_a_map_points_at_a_section_that_exists() -> None:
    sections = plan_sections()
    used: dict[str, list[str]] = defaultdict(list)
    for path in maps():
        relative = path.relative_to(ROOT).as_posix()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if OTHER_DOCUMENT.search(line):
                continue
            for hit in REFERENCE.finditer(line):
                used[hit.group(1)].append(f"{relative}:{number}")

    assert len(used) > 40, f"nur {len(used)} Verweise gefunden — das Muster greift nicht"

    missing = {section: places for section, places in used.items() if section not in sections}
    assert not missing, "§-Verweise ohne Abschnitt im Bauplan:\n" + "\n".join(
        f"  §{section} ({len(places)}x) — {places[0]}"
        for section, places in sorted(missing.items())
    )
