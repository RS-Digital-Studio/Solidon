"""Erzeugt die Codex-Agentenprofile aus den Claude-Agentendateien.

Dieselben vierzehn Fachagenten stehen zweimal im Repository: als Markdown mit
Frontmatter unter ``.claude/agents/`` für Claude Code, als TOML unter
``.codex/agents/`` für Codex. Beide Werkzeuge lesen nur ihr eigenes Format,
und bis zum 08.09.2026 wurden beide von Hand gepflegt.

**Das hat nicht getragen, und zwar messbar.** Neun Commits fassten nur die
Claude-Seite an, drei nur die Codex-Seite, und *kein einziger* beide. Am
08.09.2026 wich jede der vierzehn Beschreibungen ab, die Anweisungstexte zu
4 bis 29 Prozent — und die Abweichung transportierte Fehler: Drei
Claude-Agenten schrieben ``pytest -q`` am Stück vor, den Lauf, der seit dem
16.08.2026 nach rund zweiundzwanzig Minuten mit einem Speicherabriss endet,
und kein einziger kannte ``tools/affected_tests.py`` aus Roberts Entscheidung
vom 02.09.2026. Die Codex-Seite kannte beides — sie war die gepflegtere.

Seither ist ``.claude/agents/`` die Quelle und ``.codex/agents/`` erzeugt.
Markdown ist das Format, das ein Mensch bearbeitet; TOML entsteht daraus.
``tests/test_agent_mirror.py`` fährt ``--check`` und wird rot, sobald die
beiden auseinanderlaufen — dasselbe Muster wie ``ruff format --check``.

Was aus dem Frontmatter wird:

===================  ==============================================
``model``            ``model`` über :data:`MODELS`
``effort``           ``model_reasoning_effort``, unverändert
``tools``            ``sandbox_mode = "read-only"``, wenn weder
                     ``Write`` noch ``Edit`` darin vorkommt
``description``      ``description``, gefaltet wie YAML es für
                     ``>`` vorschreibt
===================  ==============================================

``color`` bleibt in Claude Code, Codex kennt nichts dergleichen.

Aufruf::

    .venv\\Scripts\\python.exe tools/sync_agents.py           # schreiben
    .venv\\Scripts\\python.exe tools/sync_agents.py --check    # nur prüfen
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / ".claude" / "agents"
TARGET_DIR = ROOT / ".codex" / "agents"
SKILL_DIR = ROOT / ".agents" / "skills"

#: Welches Modell ein Agent bei Codex bekommt, abgeleitet aus dem, das er bei
#: Claude Code bekommt. ``gpt-6-astra`` ist seit Codex CLI 0.153.4 (04.09.2026)
#: die gebündelte Vorgabe; wer keinen Zugang hat, setzt hier ``gpt-5.6-sol``
#: zurück — der stabile Rückfall — und lässt das Werkzeug einmal laufen.
MODELS = {
    "opus": "gpt-6-astra",
    "sonnet": "gpt-5.6-terra",
}

#: Werkzeuge, die eine Datei ändern. Fehlen sie, arbeitet der Agent nur
#: lesend, und Codex bekommt die Sandbox dazu.
WRITING_TOOLS = ("Write", "Edit")

#: Ein Skill heißt bei Claude Code ``/name`` und bei Codex so, wie seine Datei
#: heißt. Beide meinen dieselbe Anleitung.
SKILL_PATTERN = re.compile(r"`/([a-z][a-z0-9-]*)`")


class SyncError(Exception):
    """Die Quelle lässt sich nicht in ein Codex-Profil übersetzen."""


def _split_front_matter(text: str, name: str) -> tuple[dict[str, str], str]:
    """Zerlegt eine Agentendatei in ihre Kopffelder und den Anweisungstext."""
    match = re.match(r"^---\n(.*?\n)---\n(.*)$", text, re.DOTALL)
    if match is None:
        raise SyncError(f"{name}: kein Frontmatter zwischen zwei '---'-Zeilen")

    fields: dict[str, str] = {}
    key: str | None = None
    for line in match.group(1).split("\n"):
        start = re.match(r"^([a-z][a-z-]*):\s*(.*)$", line)
        if start is not None:
            key = start.group(1)
            fields[key] = start.group(2)
        elif key is not None:
            fields[key] += "\n" + line
    return fields, match.group(2).strip()


def _fold(text: str) -> str:
    """Faltet einen YAML-Block der Art ``>`` so, wie YAML es vorschreibt.

    Zeilen eines Absatzes werden mit Leerzeichen verbunden, eine Leerzeile
    trennt Absätze. Genau das sieht ein Modell, das die Beschreibung liest —
    die Codex-Fassung muss deshalb dasselbe enthalten und nicht die
    Zeilenumbrüche, die nur der Lesbarkeit der Quelldatei dienen.
    """
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return "\n\n".join(" ".join(line.strip() for line in p.split("\n")).strip() for p in paragraphs)


def _to_codex_skills(text: str) -> str:
    """Ersetzt ``/name`` durch den Pfad, unter dem Codex denselben Skill liest."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if not (SKILL_DIR / name / "SKILL.md").exists():
            return match.group(0)
        return f"`.agents/skills/{name}/SKILL.md`"

    return SKILL_PATTERN.sub(replace, text)


def _quote(text: str, *, name: str, field: str) -> str:
    """Verpackt einen Text als mehrzeilige TOML-Zeichenkette."""
    if '"""' in text:
        raise SyncError(f"{name}: {field} enthält dreifache Anführungszeichen")
    if text.endswith('"'):
        raise SyncError(f"{name}: {field} endet auf ein Anführungszeichen")
    # In einer TOML-Zeichenkette leitet der Backslash eine Maskierung ein; die
    # Windows-Pfade in den Anweisungen sollen aber wörtlich ankommen.
    return '"""\n' + text.replace("\\", "\\\\") + '\n"""'


def render(path: Path) -> str:
    """Baut den Inhalt der Codex-Datei zu einer Claude-Agentendatei."""
    name = path.stem
    fields, body = _split_front_matter(path.read_text(encoding="utf-8"), name)

    for required in ("name", "description", "model", "effort", "tools"):
        if required not in fields:
            raise SyncError(f"{name}: Feld '{required}' fehlt im Frontmatter")
    if fields["name"].strip() != name:
        raise SyncError(f"{name}: Feld 'name' sagt {fields['name'].strip()!r}")

    model = fields["model"].strip()
    if model not in MODELS:
        raise SyncError(f"{name}: für Modell {model!r} ist kein Codex-Modell hinterlegt")

    description = _fold(re.sub(r"^\s*>\s*\n", "", fields["description"]))
    tools = [t.strip() for t in fields["tools"].strip().split(",")]

    lines = [
        f'name = "{name}"',
        "description = " + _quote(description, name=name, field="description"),
        f'model = "{MODELS[model]}"',
        f'model_reasoning_effort = "{fields["effort"].strip()}"',
    ]
    if not any(tool in tools for tool in WRITING_TOOLS):
        lines.append('sandbox_mode = "read-only"')
    lines.append(
        "developer_instructions = "
        + _quote(_to_codex_skills(body), name=name, field="developer_instructions")
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="nichts schreiben, nur melden, was nicht auf dem Stand der Quelle ist",
    )
    args = parser.parse_args(argv)

    sources = sorted(SOURCE_DIR.glob("*.md"))
    if not sources:
        print(f"Keine Agentendateien unter {SOURCE_DIR}", file=sys.stderr)
        return 1

    stale: list[str] = []
    for source in sources:
        target = TARGET_DIR / (source.stem + ".toml")
        try:
            wanted = render(source)
        except SyncError as problem:
            print(f"{problem}", file=sys.stderr)
            return 1
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current == wanted:
            continue
        stale.append(source.stem)
        if not args.check:
            target.write_text(wanted, encoding="utf-8", newline="\n")

    # Ein Profil ohne Quelle wäre eine Datei, die niemand mehr pflegt.
    orphans = sorted(
        p.stem for p in TARGET_DIR.glob("*.toml") if not (SOURCE_DIR / (p.stem + ".md")).exists()
    )
    for orphan in orphans:
        print(f"Ohne Quelle in .claude/agents/: {orphan}.toml", file=sys.stderr)

    if args.check:
        for name in stale:
            print(f"Nicht auf dem Stand der Quelle: {name}.toml", file=sys.stderr)
        if stale or orphans:
            print(
                "\n.venv\\Scripts\\python.exe tools/sync_agents.py schreibt sie neu.",
                file=sys.stderr,
            )
            return 1
        print(f"{len(sources)} Codex-Profile stehen auf dem Stand ihrer Quelle.")
        return 0

    if orphans:
        return 1
    print(f"{len(stale)} von {len(sources)} Profilen neu geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
