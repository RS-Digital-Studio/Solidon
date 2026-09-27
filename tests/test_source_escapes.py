"""Ein Backslash in einem Pfad kommt als Backslash an, nicht als Steuerzeichen.

Wer ``F:\\3D Dateien`` über eine Shell in eine Datei schreibt, bekommt je nach
Weg ``F:\\3D`` als Oktal-Escape — Python liest daraus das Steuerzeichen 0x03 —
oder das Steuerzeichen gleich roh in die Datei. Beides fiel nur zufällig auf:
am 25.09.2026 sechs Docstrings in ``tests/``, alle mit demselben Pfad, einer
davon mit dem Steuerzeichen roh als Byte, und der Heredoc der Shell hatte an
diesem Tag zweimal Backslashs verschluckt
(``.claude/memory/heredoc-frisst-den-backslash.md``).

Gewollte Steuerzeichen stehen in diesem Code als Hex-Escape oder als ``\\0``
da (``\\x00``, ``\\x04``); jedes andere Oktal-Escape und jedes rohe
Steuerzeichen in einer nicht rohen Zeichenkette ist deshalb ein verschluckter
Backslash. Gelesen werden die
Tokens und nicht das AST: Erst die Schreibweise unterscheidet ``\\x03`` von
``\\3``.
"""

from __future__ import annotations

import io
import os
import re
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("app", "tests", "tools", "website", "packaging")

#: Ein Oktal-Escape hinter einer geraden Zahl Backslashs — außer dem nackten
#: ``\0``: Das NUL-Escape ist gewollt und steht zehnmal im Code.
OCTAL = re.compile(r"(?<!\\)(?:\\\\)*\\(?:[1-7]|0[0-7])")


def _prefix_is_raw(token_text: str) -> bool:
    prefix = re.match(r"[A-Za-z]*", token_text)
    return prefix is not None and "r" in prefix.group(0).lower()


def swallowed_backslashes(source: str) -> list[int]:
    """Die Zeilen, an denen eine Zeichenkette einen verschluckten Backslash trägt."""
    lines: list[int] = []
    raw_fstring: list[bool] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        kind = tokenize.tok_name[token.type]
        if kind == "FSTRING_START":
            raw_fstring.append(_prefix_is_raw(token.string))
            continue
        if kind == "FSTRING_END":
            raw_fstring.pop()
            continue
        if kind == "STRING":
            raw = _prefix_is_raw(token.string)
        elif kind == "FSTRING_MIDDLE":
            raw = raw_fstring[-1]
        else:
            continue
        control = any(ord(ch) < 32 and ch not in "\t\n\r" for ch in token.string)
        if control or (not raw and OCTAL.search(token.string)):
            lines.append(token.start[0])
    return lines


def _sources() -> list[Path]:
    found = sorted(
        path
        for folder in FOLDERS
        for path in (ROOT / folder).rglob("*.py")
        if "__pycache__" not in path.parts
    )
    # Eine leere Menge wäre ein grüner Lauf ohne Prüfung.
    assert len(found) > 300, f"nur {len(found)} Quelldateien gefunden"
    return found


def test_no_string_carries_a_swallowed_backslash() -> None:
    """Keine Zeichenkette in Solidons eigenem Code trägt einen verschluckten Backslash."""
    offenders = [
        f"{path.relative_to(ROOT)}:{line}"
        for path in _sources()
        for line in swallowed_backslashes(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        f"{len(offenders)} Zeichenketten tragen ein Oktal-Escape oder ein rohes "
        f"Steuerzeichen — gemeint war ein Backslash (\\\\): {offenders[:10]}"
    )


#: Was beim Durchsuchen nach Markdown nicht betreten wird: fremde Pakete,
#: Git-Innereien, Arbeitsbäume, Bauerzeugnisse und der Ordner mit den
#: Druckprojekten, der ein eigenes Repository ist.
_NOT_OURS: frozenset[str] = frozenset(
    {".venv", ".git", "node_modules", "worktrees", "__pycache__", "build", "dist", "3D Drucker"}
)


def control_characters(data: bytes) -> list[int]:
    """Die Zeilen, in denen ein Steuerzeichen außer Tab und Zeilenende steht."""
    return [
        number
        for number, line in enumerate(data.split(b"\n"), 1)
        if any(byte < 32 and byte not in (9, 13) for byte in line)
    ]


def _markdown() -> list[Path]:
    found: list[Path] = []
    for folder, directories, files in os.walk(ROOT):
        directories[:] = [name for name in directories if name not in _NOT_OURS]
        found.extend(Path(folder) / name for name in files if name.endswith(".md"))
    # Eine leere Menge wäre ein grüner Lauf ohne Prüfung.
    assert len(found) > 100, f"nur {len(found)} Markdown-Dateien gefunden"
    return sorted(found)


def test_no_markdown_carries_a_control_character() -> None:
    """Auch Karten, Regeln, Erinnerungen und Register tragen keinen verschluckten Backslash.

    Markdown kennt keine Escapes, und jedes Steuerzeichen außer Tab und
    Zeilenende ist dort ein Backslash, den eine Python-Zeichenkette ohne
    Rohpräfix gefressen hat. Am 27.09.2026 trug eine neue Regel in
    ``.claude/rules/wartezeit.md`` ``F:`` mit dem Steuerzeichen 0x03 statt
    ``F:\\3D Dateien``, geschrieben von einer Sonde; ``ROADMAP-ARCHIV.md`` und
    eine Erinnerung trugen dasselbe schon länger, und niemand hatte es gesehen
    — im Editor steht dort ein leeres Kästchen oder gar nichts.
    """
    offenders = [
        f"{path.relative_to(ROOT)}:{line}"
        for path in _markdown()
        for line in control_characters(path.read_bytes())
    ]
    assert not offenders, (
        f"{len(offenders)} Markdown-Zeilen tragen ein Steuerzeichen — gemeint war "
        f"vermutlich ein Backslash (\\\\): {offenders[:10]}"
    )


def test_the_markdown_check_finds_the_swallowed_backslash() -> None:
    """Die Gegenprobe: 0x03 fällt, Tab und Windows-Zeilenende nicht."""
    assert control_characters(b"aus `F:\x03D Dateien`\n") == [1]
    assert control_characters(b"eins\r\n\tzwei\r\n") == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('"""Aus ``F:\\3D Dateien``."""\n', [1]),
        ('text = "F:\x03D Dateien"\n', [1]),
        ('text = f"{name} aus F:\\3D"\n', [1]),
        ('"""Aus ``F:\\\\3D Dateien``."""\n', []),
        ('text = r"F:\\3D Dateien"\n', []),
        ('BREAK = "\\x01"\n', []),
        ('names = b"\\0.shstrtab\\0"\n', []),
        ('"""In F:\\02_Getraenkehalter."""\n', [1]),
        ('text = rf"{name} aus F:\\3D"\n', []),
    ],
)
def test_the_check_tells_a_swallowed_backslash_from_a_written_one(
    source: str, expected: list[int]
) -> None:
    """Die Gegenprobe: Oktal-Escape und rohes Steuerzeichen fallen, Hex, Doppel und roh nicht."""
    assert swallowed_backslashes(source) == expected
