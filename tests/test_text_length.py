"""Jeder Kundentext hat an seinem Ort eine Längengrenze (RM-509).

Für über achttausend sichtbare Texte gab es eine Grenze nur bei den
Bildanleitungen (``guides.MAX_STEP_WORDS``). Befunde standen als Absatz in
der Liste, geänderte Bausteine mit bis zu 99 Wörtern im Prüfbericht, die Tour
mit 56 von 83 Schritten über 20 Wörtern.

Eingeordnet wird jeder Text nach seinem **Aufrufort** im Quelltext — als
Meldung eines ``Finding``, als ``detail`` einer Ausnahme, als ``caveat`` eines
Registereintrags und so fort (:data:`LIMITS`). Was heute über der Grenze
liegt, steht je Art in ``tests/data/text_lengths/<art>.json`` und darf nur
schrumpfen: Ein neuer Text über der Grenze ist rot, ein gekürzter, der noch in
der Liste steht, ebenso, und die Zahl der Einträge steht in
:data:`FROZEN_COUNTS` fest — wer die Liste wachsen lässt, ändert sie sichtbar.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.core.registry.surfaces import sentences

ROOT = Path(__file__).resolve().parent.parent
FROZEN_DIR = ROOT / "tests" / "data" / "text_lengths"

#: Die Namen, unter denen ein Kundentext im Quelltext steht.
MARKERS = frozenset({"_", "tr"})


@dataclass(frozen=True, slots=True)
class Limit:
    """Wie lang ein Text einer Art höchstens ist, gezählt an der deutschen Quelle."""

    words: int = 0
    sentences: int = 0
    characters: int = 0
    first_sentence: bool = False
    """Nur der erste Satz zählt — Menü, Statuszeile und Dialogkopf zeigen nur ihn."""


#: Die Grenzen je Art (Register RM-509). Null heißt: an dieser Achse keine.
LIMITS: dict[str, Limit] = {
    "finding": Limit(words=20, sentences=2),
    "error_detail": Limit(words=25, sentences=2),
    "part_change": Limit(words=20, sentences=1),
    "caveat": Limit(words=20, sentences=2),
    "op_doc": Limit(words=15, first_sentence=True),
    "param_doc": Limit(words=25, sentences=2),
    "hint": Limit(words=25, sentences=2),
    "tooltip": Limit(words=25, sentences=2),
    "announcement": Limit(words=20),
    "empty": Limit(words=20),
    "tour": Limit(words=20),
    "print_reason": Limit(characters=60),
}

#: Wie viele Texte je Art heute über der Grenze stehen dürfen. Die Zahl sinkt
#: mit jeder Kürzung; sie zu erhöhen ist eine Entscheidung, kein Nachtrag.
FROZEN_COUNTS: dict[str, int] = {
    "announcement": 1,
    "error_detail": 36,
    "op_doc": 42,
    "param_doc": 56,
    "tooltip": 3,
}


@dataclass(frozen=True, slots=True)
class CustomerText:
    """Ein Kundentext mit Art und Fundstelle."""

    kind: str
    text: str
    where: str


def too_long(text: str, limit: Limit) -> bool:
    """Ob ein Text die Grenze seiner Art überschreitet."""
    parts = sentences(text)
    measured = parts[0] if limit.first_sentence and parts else text
    if limit.words and len(measured.split()) > limit.words:
        return True
    if limit.sentences and len(parts) > limit.sentences:
        return True
    return bool(limit.characters and len(text) > limit.characters)


def _callee(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _literal(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in MARKERS
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _kind_at(node: ast.AST, parents: dict[ast.AST, ast.AST], path: str) -> str:
    """Die Art eines Textes aus seinem Aufrufort — oder ``""``, wenn keine passt."""
    parent = parents.get(node)
    # Ein bedingter Text („a if x else b“) gehört an denselben Ort wie beide Zweige.
    while isinstance(parent, ast.IfExp | ast.BoolOp):
        node, parent = parent, parents.get(parent)
    if isinstance(parent, ast.Return):
        function = parent
        while function is not None and not isinstance(
            function, ast.FunctionDef | ast.AsyncFunctionDef
        ):
            function = parents.get(function)
        if function is not None and "empty" in function.name:
            return "empty"
        return ""
    keyword = None
    if isinstance(parent, ast.keyword):
        keyword = parent.arg
        parent = parents.get(parent)
    if not isinstance(parent, ast.Call):
        return ""
    callee = _callee(parent)
    position = next((index for index, arg in enumerate(parent.args) if arg is node), None)
    if callee == "Finding" and (keyword == "message" or position == 2):
        return "finding"
    if callee.endswith("Error") and (keyword == "detail" or position == 1):
        return "error_detail"
    if callee == "PartChange" and keyword == "effect":
        return "part_change"
    if keyword == "caveat":
        return "caveat"
    if keyword == "doc":
        return "op_doc" if callee in ("register_op", "register_part") else "param_doc"
    if keyword == "hint":
        return "hint"
    if keyword == "reason" and callee == "_advice" and path.endswith("slice/advise.py"):
        return "print_reason"
    if callee == "setToolTip":
        return "tooltip"
    if callee in ("announce", "showMessage", "show_note"):
        return "announcement"
    if callee in ("say_why_empty", "_only_this_sentence", "setPlaceholderText"):
        return "empty"
    if (callee == "TourStep" and (keyword == "text" or position == 0)) or (
        callee == "Tour" and keyword in ("intro", "closing")
    ):
        return "tour"
    return ""


def customer_texts(sources: Iterable[tuple[str, str]]) -> Iterator[CustomerText]:
    """Jeder eingeordnete Kundentext aus ``(Pfad, Quelltext)``-Paaren."""
    for path, source in sources:
        tree = ast.parse(source)
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            text = _literal(node)
            if text is None:
                continue
            kind = _kind_at(node, parents, path)
            if kind:
                yield CustomerText(kind, text, f"{path}:{getattr(node, 'lineno', 0)}")


def _application_sources() -> Iterator[tuple[str, str]]:
    for path in sorted((ROOT / "app").rglob("*.py")):
        yield path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")


def frozen(kind: str) -> list[str]:
    """Der eingefrorene Bestand einer Art."""
    path = FROZEN_DIR / f"{kind}.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")))


def problems(
    found: Iterable[CustomerText],
    frozen_lists: dict[str, list[str]],
    counts: dict[str, int],
) -> list[str]:
    """Was den Wächter rot macht — leer, wenn alles stimmt."""
    over: dict[str, dict[str, str]] = {kind: {} for kind in LIMITS}
    seen: dict[str, set[str]] = {kind: set() for kind in LIMITS}
    for entry in found:
        seen[entry.kind].add(entry.text)
        if too_long(entry.text, LIMITS[entry.kind]):
            over[entry.kind].setdefault(entry.text, entry.where)
    lines: list[str] = []
    for kind in LIMITS:
        listed = frozen_lists.get(kind, [])
        allowed = set(listed)
        for text, where in sorted(over[kind].items(), key=lambda item: item[1]):
            if text not in allowed:
                lines.append(f"{kind} zu lang ({where}): {text}")
        for text in listed:
            if text not in over[kind]:
                state = "steht nicht mehr im Code" if text not in seen[kind] else "ist kurz genug"
                lines.append(f"{kind}: aus der Liste streichen, {state}: {text}")
        if len(listed) != len(allowed):
            lines.append(f"{kind}: doppelte Einträge in der Liste")
        expected = counts.get(kind, 0)
        if len(listed) != expected:
            lines.append(
                f"{kind}: {len(listed)} eingefrorene Texte, FROZEN_COUNTS sagt {expected} — "
                "die Liste darf nur schrumpfen, und die Zahl schrumpft mit ihr"
            )
    return lines


def test_every_customer_text_stays_within_the_limit_of_its_place() -> None:
    """Kein neuer Text über der Grenze, und der Bestand schrumpft nur."""
    lists = {kind: frozen(kind) for kind in LIMITS}
    found = problems(customer_texts(_application_sources()), lists, FROZEN_COUNTS)
    assert not found, "\n".join(found[:40]) + (
        f"\n… und {len(found) - 40} weitere" if len(found) > 40 else ""
    )


def test_the_frozen_lists_are_sorted_and_name_only_known_kinds() -> None:
    """Eine Liste, die sortiert ist, zeigt im Diff genau, was wegfiel."""
    for path in sorted(FROZEN_DIR.glob("*.json")):
        assert path.stem in LIMITS, f"{path.name}: keine bekannte Art"
        entries = json.loads(path.read_text(encoding="utf-8"))
        assert entries == sorted(entries), f"{path.name} ist nicht sortiert"


SAMPLE = """
from app.core.types import Finding
from app.i18n import _

def check():
    return Finding(
        "sample.long",
        "warning",
        _("Ein Befund mit viel zu vielen Wörtern, die niemand in einer Zeile der Liste "
          "lesen will, weil die Handlung irgendwo in der Mitte des Satzes versteckt steht."),
    )

def other():
    return Finding("sample.short", "info", message=_("Kurz und klar."))
"""


def test_a_new_text_over_the_limit_turns_the_guard_red() -> None:
    """Gegenprobe: ein langer Befund an einem neuen Ort fällt auf, ein kurzer nicht."""
    found = list(customer_texts([("app/sample.py", SAMPLE)]))
    assert {entry.kind for entry in found} == {"finding"}
    lines = problems(found, {}, {})
    assert len(lines) == 1 and lines[0].startswith("finding zu lang (app/sample.py:"), lines


def test_a_growing_list_turns_the_guard_red() -> None:
    """Gegenprobe: Wer den Bestand wachsen lässt, muss die Zahl sichtbar erhöhen."""
    found = list(customer_texts([("app/sample.py", SAMPLE)]))
    long_text = next(entry.text for entry in found if entry.text.startswith("Ein Befund"))
    assert not problems(found, {"finding": [long_text]}, {"finding": 1})
    grown = problems(found, {"finding": [long_text]}, {})
    assert any("FROZEN_COUNTS" in line for line in grown), grown
    stale = problems(found, {"finding": [long_text, "Kurz und klar."]}, {"finding": 2})
    assert any("ist kurz genug" in line for line in stale), stale


@pytest.mark.parametrize(
    ("text", "count"),
    [
        ("Ein Satz.", 1),
        ("Zwei Sätze. Hier der zweite.", 2),
        ("Mit Abkürzung, z. B. Holz. Und noch einer.", 2),
        ("Eine Zahl 1.5 mm bleibt ein Satz.", 1),
    ],
)
def test_sentences_are_counted_as_a_reader_counts_them(text: str, count: int) -> None:
    assert len(sentences(text)) == count
