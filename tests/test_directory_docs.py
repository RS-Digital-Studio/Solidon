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
MEMORY = ROOT / ".claude" / "memory"

#: Eine numerierte Überschrift des Bauplans — dieselbe Vorschrift wie in
#: `test_plan_references.py`, denn es ist dieselbe Frage.
HEADING = re.compile(r"^#{2,5}\s+(\d+(?:\.\d+)*)\.?\s")

#: Ein Verweis: ``§31``, ``§ 17.2``, ``(§2.4)``.
REFERENCE = re.compile(r"§+\s?(\d+(?:\.\d+)*)")

#: Ein Eintrag im Erinnerungsverzeichnis: ``[Titel](datei.md)``.
MEMORY_ENTRY = re.compile(r"\]\(([a-z0-9_-]+\.md)\)")

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


def memory_notes() -> list[Path]:
    """Jede Erinnerung — das Verzeichnis selbst, nicht der Index darüber."""
    return sorted(path for path in MEMORY.glob("*.md") if path.name != "MEMORY.md")


def memory_index() -> set[str]:
    """Die Dateinamen, auf die ``MEMORY.md`` zeigt."""
    text = (MEMORY / "MEMORY.md").read_text(encoding="utf-8")
    return {hit.group(1) for hit in MEMORY_ENTRY.finditer(text)}


def test_the_plan_and_the_maps_are_both_there() -> None:
    """Ohne diese Zusicherung prüfte alles darunter gegen eine leere Menge."""
    assert PLAN.exists(), "der Bauplan fehlt"
    assert len(plan_sections()) > 100, "das Überschriften-Muster greift nicht"
    assert len(maps()) > 20, f"nur {len(maps())} Karten gefunden — der Suchlauf greift nicht"
    assert len(memory_notes()) > 50, (
        f"nur {len(memory_notes())} Erinnerungen gefunden — der Suchlauf greift nicht"
    )
    assert len(memory_index()) > 50, "das Muster für die Einträge in MEMORY.md greift nicht"


def test_every_memory_note_is_named_in_the_index() -> None:
    """Eine Erinnerung, die niemand findet, verhält sich wie eine, die es nicht gibt.

    ``MEMORY.md`` ist die einzige Datei des Verzeichnisses, die in jede Sitzung
    geladen wird; alles übrige wird über sie gefunden. Wer eine Notiz anlegt und
    den Zeiger vergisst, legt sie ab, wo niemand sucht — und das fällt nie auf,
    weil das Fehlen einer Erinnerung sich nicht meldet.

    Am 30.08.2026 standen drei so da: ``baustein-begriff-je-sprache`` und
    ``fremde-zwischenstaende-verfaelschen-messungen`` waren seit ``f934a422``
    committet und in keinem Index, ``sicherung-ist-eine-zeitmaschine`` umgekehrt
    im Index und in keinem Commit. Die erste von ihnen legt die Begriffe fest,
    nach denen gerade in fünf Sprachen übersetzt wird.
    """
    named = memory_index()
    without = [note.name for note in memory_notes() if note.name not in named]
    assert not without, (
        "Erinnerungen ohne Zeiger in MEMORY.md:\n"
        + "\n".join(f"  {name}" for name in without)
        + "\nEine Zeile im Index, sonst findet sie niemand."
    )


def test_every_entry_of_the_index_has_its_note() -> None:
    """Die Gegenrichtung: ein Zeiger auf eine Datei, die es nicht gibt.

    Sie entsteht auf der Maschine, auf der die Notiz liegt, gar nicht — dort
    stimmt beides. Sichtbar wird sie erst auf den beiden anderen, und dort als
    Verweis ins Leere.
    """
    present = {note.name for note in memory_notes()}
    missing = sorted(name for name in memory_index() if name not in present)
    assert not missing, (
        "Zeiger in MEMORY.md ohne Datei:\n"
        + "\n".join(f"  {name}" for name in missing)
        + "\nEntweder fehlt der Commit der Notiz, oder der Zeiger ist zu löschen."
    )


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
