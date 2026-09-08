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

Auch die Skills haben eine Quelle: ``.claude/skills/``. Ihr Codex-Spiegel
unter ``.agents/skills/`` enthält dieselben Anleitungen und Referenzen; nur
Skillverweise und der Argumentplatzhalter werden übersetzt. Die Codex-Datei
``agents/openai.yaml`` entsteht aus ``disable-model-invocation`` und wird
nicht getrennt gepflegt. Verwaiste Zieldateien werden gemeldet, nie gelöscht.

Aufruf::

    .venv\\Scripts\\python.exe tools/sync_agents.py           # schreiben
    .venv\\Scripts\\python.exe tools/sync_agents.py --check    # nur prüfen
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / ".claude" / "agents"
TARGET_DIR = ROOT / ".codex" / "agents"
SKILL_DIR = ROOT / ".agents" / "skills"
SOURCE_SKILL_DIR = ROOT / ".claude" / "skills"

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
EFFORTS = {"low", "medium", "high", "max"}

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
        if line.startswith("#"):
            continue
        start = re.match(r"^([a-zA-Z][a-zA-Z0-9_-]*):[ \t]*(.*)$", line)
        if start is not None:
            key = start.group(1)
            if key in fields:
                raise SyncError(f"{name}: Feld '{key}' steht doppelt im Frontmatter")
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
    paragraphs = re.split(r"(\n[ \t]*\n(?:[ \t]*\n)*)", text.strip())
    return "".join(
        "\n" * (part.count("\n") - 1)
        if part.startswith("\n")
        else " ".join(line.strip() for line in part.split("\n"))
        for part in paragraphs
    )


def _to_codex_skills(text: str) -> str:
    """Ersetzt ``/name`` durch den Pfad, unter dem Codex denselben Skill liest."""

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if not (SOURCE_SKILL_DIR / name / "SKILL.md").is_file():
            return match.group(0)
        return f"`.agents/skills/{name}/SKILL.md`"

    return SKILL_PATTERN.sub(replace, text)


def _quote(text: str, *, name: str, field: str) -> str:
    """Verpackt einen Text als mehrzeilige TOML-Zeichenkette."""
    # Normale Texte behalten die gut lesbare Darstellung. JSON maskiert die
    # Sonderfälle zugleich gültig für eine einfache TOML-Zeichenkette.
    if '"""' in text or any(
        (ord(char) < 32 and char not in "\n\t") or char == "\x7f" for char in text
    ):
        return json.dumps(text + "\n")
    return '"""\n' + text.replace("\\", "\\\\") + '\n"""'


def render(path: Path) -> str:
    """Baut den Inhalt der Codex-Datei zu einer Claude-Agentendatei."""
    name = path.stem
    fields, body = _split_front_matter(path.read_text(encoding="utf-8"), name)
    unknown = fields.keys() - {"name", "description", "model", "effort", "tools", "color"}
    if unknown:
        raise SyncError(
            f"{name}: für {', '.join(sorted(unknown))} zuerst eine Codex-Übersetzung ergänzen."
        )

    for required in ("name", "description", "model", "effort", "tools"):
        if required not in fields:
            raise SyncError(f"{name}: Feld '{required}' fehlt im Frontmatter")
    if fields["name"].strip() != name:
        raise SyncError(f"{name}: Feld 'name' sagt {fields['name'].strip()!r}")

    model = fields["model"].strip()
    if model not in MODELS:
        raise SyncError(f"{name}: für Modell {model!r} ist kein Codex-Modell hinterlegt")
    if fields["effort"].strip() not in EFFORTS:
        raise SyncError(f"{name}: unbekannter Aufwand {fields['effort'].strip()!r}")

    description = _fold(re.sub(r"^\s*>\s*\n", "", fields["description"]))
    tool_text = fields["tools"].strip()
    if tool_text.startswith("[") and tool_text.endswith("]"):
        tool_text = tool_text[1:-1]
    if tool_text.startswith("- "):
        tools = [line.strip().removeprefix("- ").strip("\"'") for line in tool_text.splitlines()]
    else:
        tools = [tool.strip().strip("\"'") for tool in tool_text.split(",")]

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


def _skill_outputs() -> dict[Path, bytes]:
    """Spiegelt die gemeinsamen Skills samt Dateien und übersetzt die Aufrufregel."""
    outputs: dict[Path, bytes] = {}
    sources = sorted(SOURCE_SKILL_DIR.glob("*/SKILL.md"))
    if not sources:
        raise SyncError(f"Keine Skills unter {SOURCE_SKILL_DIR}; Quelle wiederherstellen.")
    if SOURCE_SKILL_DIR.resolve() == SKILL_DIR.resolve():
        raise SyncError(
            "Die Skillordner sind verknüpft; den Codex-Spiegel als eigenen Ordner anlegen."
        )
    for source in sources:
        fields, _ = _split_front_matter(source.read_text(encoding="utf-8"), source.parent.name)
        if fields.get("name", "").strip() != source.parent.name:
            raise SyncError(f"{source}: Skillname und Ordnername müssen übereinstimmen.")
        invocation = fields.get("disable-model-invocation", "false").strip()
        if invocation not in {"true", "false"}:
            raise SyncError(f"{source}: disable-model-invocation muss true oder false sein.")
        for path in sorted(source.parent.rglob("*")):
            if path.is_file():
                relative = path.relative_to(SOURCE_SKILL_DIR)
                if relative.parts[1:] == ("agents", "openai.yaml"):
                    raise SyncError(
                        f"{path}: Aufrufregel im SKILL.md pflegen; openai.yaml wird daraus erzeugt."
                    )
                content = path.read_bytes()
                if path.name == "SKILL.md":
                    content = (
                        _to_codex_skills(path.read_text(encoding="utf-8"))
                        .replace("$ARGUMENTS", "Angaben aus der aktuellen Anfrage")
                        .encode("utf-8")
                    )
                outputs[SKILL_DIR / relative] = content
        if invocation == "true":
            outputs[SKILL_DIR / source.parent.name / "agents" / "openai.yaml"] = (
                b"policy:\n  allow_implicit_invocation: false\n"
            )
    return outputs


def _is_current(path: Path, content: bytes) -> bool:
    """Vergleicht Textdateien unabhängig von Gits Zeilenenden auf Windows."""
    if not path.is_file():
        return False
    current = path.read_bytes()
    if path.suffix in {".md", ".toml", ".yaml"}:
        current = current.replace(b"\r\n", b"\n")
        content = content.replace(b"\r\n", b"\n")
    return current == content


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

    # Erst alle Quellen prüfen. Ein Fehler in der letzten darf nicht vorher
    # bereits die ersten Profile überschrieben haben.
    try:
        wanted = _skill_outputs()
        wanted.update(
            (TARGET_DIR / (source.stem + ".toml"), render(source).encode("utf-8"))
            for source in sources
        )
    except (SyncError, OSError) as problem:
        print(str(problem), file=sys.stderr)
        return 1

    existing = set(TARGET_DIR.glob("*.toml")) | {
        path for path in SKILL_DIR.rglob("*") if path.is_file()
    }
    orphans = sorted(existing - wanted.keys())
    for path in orphans:
        print(f"Ohne Quelle: {path}; entfernen oder eine Quelle ergänzen.", file=sys.stderr)
    stale = [path for path, content in wanted.items() if not _is_current(path, content)]

    if args.check:
        for path in stale:
            print(f"Nicht auf dem Stand der Quelle: {path}", file=sys.stderr)
        if stale or orphans:
            print(
                "\n.venv\\Scripts\\python.exe tools/sync_agents.py schreibt sie neu.",
                file=sys.stderr,
            )
            return 1
        print(
            f"{len(sources)} Codex-Profile und alle Skilldateien stehen auf dem Stand ihrer Quelle."
        )
        return 0

    if orphans:
        return 1
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(wanted[path])
    print(f"{len(stale)} von {len(wanted)} Agenten- und Skilldateien neu geschrieben.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
