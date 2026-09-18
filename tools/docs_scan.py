"""Was die Unterlagen kosten und wo sie sich wiederholen — gemessen.

    .venv\\Scripts\\python.exe tools/docs_scan.py
    .venv\\Scripts\\python.exe tools/docs_scan.py --frage 1
    .venv\\Scripts\\python.exe tools/docs_scan.py --frage 2 --frage 3 > funde.txt

**Wofür das da ist.** Die Pyramide aus `CLAUDE.md` verspricht zweierlei: dass
jedes Gebiet eine Karte hat und eine Regel, und dass **keine die andere
wiederholt**. Das erste prüft `tests/test_directory_docs.py` bei jedem Lauf.
Das zweite prüfte bis zum 18.09.2026 niemand — und es ist das teurere
Versprechen: Wer `app/ui/viewport.py` anfasst, bekam an diesem Tag 340 KB
Unterlagen zu sehen, bevor er eine Zeile Code gelesen hatte.

Vier Fragen, alle ohne Ausführung von Projektcode:

1. **Ladelast** — welche Quelldatei zieht wie viel Prosa nach sich.
2. **Doppelte Absätze** — derselbe Absatz in zwei Unterlagen.
3. **Tote Verweise** — eine Unterlage nennt eine Quelldatei, die es nicht
   gibt. Lesen mit Kopf: Eine Karte, die erzählt, wie etwas *früher* hieß
   („hatte bis zum 11.09.2026 eine eigene Leiste, `slot_bar.py`"), steht hier
   zu Recht und ist trotzdem ein Fund.
4. **Leere Geltungsbereiche** — ein `paths:`-Muster, auf das nichts passt.

**Was es nicht ist: ein Test.** Es steht nicht im Tor. Eine große Regeldatei
ist kein Fehler, sondern eine Abwägung, und ein doppelter Absatz kann ein
bewusstes Zitat sein. Was hier herauskommt, ist die Grundlage einer
Durchsicht — die Entscheidung trifft, wer die Gebiete kennt.

Der Selbsttest liegt in `tests/test_docs_scan.py`: Ein Suchwerkzeug, das zu
wenig findet, schweigt, und Schweigen sieht aus wie ein sauberes Ergebnis.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Die Bäume, deren Quelldateien eine Ladelast tragen.
TREES: tuple[str, ...] = ("app", "tools", "tests")

#: Was immer mitlädt, unabhängig von der angefassten Datei.
ALWAYS: tuple[str, ...] = ("CLAUDE.md", "AGENTS.md")

#: Ein Absatz zählt erst ab dieser Länge als Wiederholung — darunter sind es
#: Überschriften, Tabellenzeilen und Redewendungen, die nichts belegen.
PARAGRAPH_FLOOR = 120

#: Unter dieser Zahl gelesener Unterlagen ist der Lauf keine Messung.
FLOOR = 20

#: Ein Verweis in Rückwärtsanführungszeichen auf eine Datei **dieses**
#: Repositories.
#:
#: **Nur Quelltext und Unterlagen** — beim ersten Lauf am 18.09.2026 nahm die
#: Vorschrift auch `.json`, `.toml` und `.sh`, und alle zehn Funde waren
#: Falschalarme: `feedback.json`, `filaments.json`, `trial.json` und
#: `salt.json` entstehen zur Laufzeit im Nutzerordner, `fdmprinter.def.json`
#: liegt beim Kunden in seinem Cura. Eine Karte, die sie nennt, hat recht.
REFERENCE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py))`")

#: Verweise, die absichtlich ins Nichts zeigen: Beispiele und Platzhalter.
NOT_A_PATH = re.compile(r"^(?:<|beispiel|example|name|datei|pfad)", re.IGNORECASE)


def rule_files() -> list[Path]:
    """Die Regeldateien unter ``.claude/rules/``."""
    return sorted((ROOT / ".claude" / "rules").glob("*.md"))


def maps() -> list[Path]:
    """Alle Karten des Repositories — die Arbeitsbäume fremder Sitzungen nicht."""
    found = []
    for path in ROOT.rglob("CLAUDE.md"):
        parts = path.relative_to(ROOT).parts
        if "worktrees" in parts or ".venv" in parts or "node_modules" in parts:
            continue
        found.append(path)
    return sorted(found)


def documents() -> list[Path]:
    """Jede Unterlage, die eine Sitzung ungefragt zu sehen bekommt."""
    return sorted({*maps(), *rule_files(), *(ROOT / name for name in ALWAYS)})


def scopes(rule: Path) -> list[str]:
    """Die ``paths:``-Muster einer Regel — ohne YAML-Bibliothek gelesen.

    Das Frontmatter dieser Dateien ist einfach genug, dass ein Zeilenleser
    genügt: ``paths:`` gefolgt von eingerückten ``- "muster"``-Zeilen.
    Kommentarzeilen tragen hier die Begründung, warum ein Pfad dazukam.
    """
    patterns: list[str] = []
    inside = False
    for line in rule.read_text(encoding="utf-8").splitlines():
        if line.startswith("---") and patterns:
            break
        if line.startswith("paths:"):
            inside = True
            continue
        if not inside:
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            patterns.append(stripped[2:].strip().strip('"').strip("'"))
        elif stripped and not stripped.startswith("-"):
            break
    return patterns


def matched(pattern: str) -> set[Path]:
    """Die Dateien, auf die ein Muster passt."""
    try:
        return {path for path in ROOT.glob(pattern) if path.is_file()}
    except ValueError, IndexError:
        return set()


def sources() -> list[Path]:
    """Die Quelldateien, für die eine Ladelast gemessen wird."""
    found: list[Path] = []
    for tree in TREES:
        found.extend(
            path for path in (ROOT / tree).rglob("*.py") if "__pycache__" not in path.parts
        )
    return sorted(found)


def kilobytes(paths: Iterable[Path]) -> int:
    return sum(path.stat().st_size for path in paths) // 1024


def load_for(source: Path, rules: dict[Path, set[Path]]) -> tuple[list[Path], int]:
    """Was beim Anfassen einer Quelldatei mitlädt, und wie schwer es wiegt.

    Gezählt wird die Karte des eigenen Verzeichnisses, die beiden Dateien der
    Wurzel und jede Regel, deren Geltungsbereich die Datei trifft. Die Karten
    **darüber** sind bewusst nicht mitgezählt: Sie laden nur, wenn jemand auch
    dort eine Datei anfasst. Die Zahl ist damit die Untergrenze.
    """
    loaded = [ROOT / name for name in ALWAYS]
    local_map = source.parent / "CLAUDE.md"
    if local_map.exists():
        loaded.append(local_map)
    loaded.extend(rule for rule, files in rules.items() if source in files)
    return loaded, kilobytes(loaded)


def paragraphs(document: Path) -> list[str]:
    """Die Absätze einer Unterlage, auf Vergleichbarkeit gebracht."""
    blocks = re.split(r"\n\s*\n", document.read_text(encoding="utf-8"))
    found = []
    for block in blocks:
        text = " ".join(block.split())
        if text.startswith(("#", "|", "-", "*", ">", "```")):
            continue
        if len(text) >= PARAGRAPH_FLOOR:
            found.append(text)
    return found


def report_load(rules: dict[Path, set[Path]], limit: int) -> None:
    print("\n## 1 — Ladelast je Quelldatei\n")
    measured = [(load_for(path, rules), path) for path in sources()]
    measured.sort(key=lambda item: item[0][1], reverse=True)
    print("| KB | Datei | Was lädt |")
    print("|---|---|---|")
    for (loaded, weight), path in measured[:limit]:
        names = ", ".join(sorted(relative(item) for item in loaded if item.name != "AGENTS.md"))
        print(f"| {weight} | `{relative(path)}` | {names} |")
    total = [weight for (_, weight), _ in measured]
    average = sum(total) // len(total)
    print(f"\n{len(total)} Quelldateien gemessen, schwerste {max(total)} KB, Mittel {average} KB.")


def report_duplicates(limit: int) -> None:
    print("\n## 2 — Derselbe Absatz in zwei Unterlagen\n")
    seen: dict[str, list[Path]] = defaultdict(list)
    for document in documents():
        for text in paragraphs(document):
            seen[text].append(document)
    repeated = {text: places for text, places in seen.items() if len(set(places)) > 1}
    if not repeated:
        print("Keiner.")
        return
    for text, places in sorted(repeated.items(), key=lambda item: -len(item[0]))[:limit]:
        names = " ↔ ".join(sorted(relative(place) for place in set(places)))
        print(f"- **{names}**\n  > {text[:220]}…\n")
    print(f"{len(repeated)} Absätze stehen mehr als einmal.")


def report_dead(limit: int) -> None:
    print("\n## 3 — Verweise auf Dateien, die es nicht gibt\n")
    dead: list[tuple[Path, str]] = []
    for document in documents():
        for line in document.read_text(encoding="utf-8").splitlines():
            for reference in REFERENCE.findall(line):
                if NOT_A_PATH.match(reference) or reference.startswith("."):
                    continue
                if (ROOT / reference).exists() or (document.parent / reference).exists():
                    continue
                if next(ROOT.rglob(Path(reference).name), None) is not None:
                    continue
                dead.append((document, reference))
    if not dead:
        print("Keine.")
        return
    for document, reference in dead[:limit]:
        print(f"- `{relative(document)}` nennt `{reference}`")
    print(f"\n{len(dead)} Verweise gehen ins Leere.")


def report_scopes(rules: dict[Path, set[Path]]) -> None:
    print("\n## 4 — Geltungsbereiche\n")
    print("| Regel | KB | Muster | Dateien |")
    print("|---|---|---|---|")
    for rule, files in sorted(rules.items(), key=lambda item: -item[0].stat().st_size):
        patterns = scopes(rule)
        empty = [pattern for pattern in patterns if not matched(pattern)]
        note = f" — **{len(empty)} ohne Treffer**" if empty else ""
        weight = rule.stat().st_size // 1024
        print(f"| `{rule.name}` | {weight} | {len(patterns)}{note} | {len(files)} |")
        for pattern in empty:
            print(f"| | | `{pattern}` trifft nichts | |")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--frage", type=int, action="append", choices=range(1, 5), help="nur diese Frage"
    )
    parser.add_argument(
        "--limit", type=int, default=15, help="wie viele Zeilen je Frage (Vorgabe 15)"
    )
    arguments = parser.parse_args(argv)

    found = documents()
    if len(found) < FLOOR:
        print(
            f"Nur {len(found)} Unterlagen gelesen — das ist keine Messung. Stimmt das Verzeichnis?",
            file=sys.stderr,
        )
        return 1

    rules = {
        rule: set().union(*(matched(pattern) for pattern in scopes(rule))) for rule in rule_files()
    }

    print(f"# Durchsicht der Unterlagen über {relative(ROOT)}\n")
    print(f"{len(found)} Unterlagen, {kilobytes(found)} KB, davon {len(rules)} Regeln.")

    wanted = set(arguments.frage or range(1, 5))
    if 1 in wanted:
        report_load(rules, arguments.limit)
    if 2 in wanted:
        report_duplicates(arguments.limit)
    if 3 in wanted:
        report_dead(arguments.limit)
    if 4 in wanted:
        report_scopes(rules)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
