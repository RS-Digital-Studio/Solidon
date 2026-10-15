"""Skripte in Zeichenketten für ``tools/code_index.py``: was ``python -c`` ausführt (CS-18).

Ein Test startet oft einen eigenen Python-Prozess mit einem Skript als Text
(``[sys.executable, "-c", skript]``); ``tests/test_core_isolation.py`` prüft so, was ``import
app.core.knowledge.parts`` lädt. Ein Name, den ein Schnitt verschiebt, bricht dort erst, wenn
der Prozess läuft — für W5 und das Verschiebewerkzeug war der Text bisher kein Code. Hier wird
jedes solche Skript, dessen Text sich falten lässt, wie ein Modul gelesen (``__main__``, ohne
Bereich): Seine Importe und Bezüge zählen, als ``script:<art>`` an der Stelle des Skripts im
Aufruf. Leser zur Aufrufzeit liefert es nicht — einen anderen Prozess erreicht kein Patch.

**Was ein Skript ist.** Das Element hinter ``-c`` einer Liste oder eines Tupels, vor dem nur
Schalter eines Interpreters stehen, wenn der Kopf ein Python ist: ``sys.executable``, ein Text
oder Ausdruck, der ``python`` nennt (``str(python)``), oder kein Kopf (``["-c", text]`` kommt
hinter einen Interpreter). ``git -c``, ``sh -c``, ``bash -c`` und ``-m pytest -c`` sind keiner.

**Sein Text.** Faltet der Ausdruck genau zu Texten, gelten sie. Sonst wird er als Vorlage
gelesen: ein offener Teil eines f-Strings (``{pfad!r}``) oder einer Summe wird
:data:`PLACEHOLDER`, ein Name nimmt jede seiner Bindungen, ``textwrap.dedent`` und
``"…".join`` wirken auf die Vorlage. Was so keinen Text ergibt (ein Parameter, ``str(pfad)``)
oder ein Modul oder einen Namen nur über den Platzhalter nennt, zählt ``scripts.open`` — nicht
faltbar ist kein Fund —, was kein Python ist, ``scripts.unparsed`` (Inventar).
"""

from __future__ import annotations

import ast
import itertools
import textwrap
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from tools.code_facts import (
    IR,
    Add,
    Attr,
    Call,
    Const,
    Facts,
    Fstr,
    Script,
    Seq,
    Use,
    extract_script,
    lookup,
)
from tools.code_values import Reference, Unresolved

if TYPE_CHECKING:
    from tools.code_index import Index

#: Die Quelle, wie dieser Prozess sie geladen hat; ``tools.code_store`` bildet daraus den
#: Stand des Auflösers, nicht aus der Platte (RR2-1).
_SOURCE = Path(__file__).read_bytes()

#: Was ein Skript an Bezügen und W5-Funden liefert, je ``(M, N)`` und als Liste.
Found = tuple[dict[tuple[str, str], list[Reference]], list[Unresolved], dict[str, int]]

#: Steht für einen Teil des Skripts, der erst zur Laufzeit feststeht. Ein Name: Er passt dort,
#: wo ein Wert steht (``sys.path.insert(0, {pfad!r})``), und nennt kein Modul.
PLACEHOLDER = "_offener_wert_"

#: Höchstzahl der Vorlagen je Skript; darüber bleibt es offen.
MOST_TEXTS = 64

#: Wie tief eine Vorlage Namen und Teile verfolgt.
DEEPEST = 16


def _limited(texts: set[str]) -> set[str] | None:
    return texts if len(texts) <= MOST_TEXTS else None


def _texts(index: Index, facts: Facts, ir: IR, depth: int = 0) -> set[str] | None:
    """Die Texte, die ``ir`` sein kann, mit :data:`PLACEHOLDER` für einen offenen Teil;
    ``None``, wenn der Ausdruck selbst offen ist."""
    values = index.fold(facts, ir)
    exact = {value.data for value in values if value.kind == "const"}
    if values and len(exact) == len(values) and all(isinstance(v, str) for v in exact):
        return _limited({str(value) for value in exact})
    if depth > DEEPEST:
        return None
    deeper = depth + 1
    if isinstance(ir, Use):
        binds = lookup(facts.scopes, ir.scope, ir.name, (ir.line, ir.col), checking=ir.checking)
        found: set[str] = set()
        for bind in binds or ():
            part = _texts(index, facts, bind.value, deeper)
            if part is None:
                return None
            found |= part
        return _limited(found) if found else None
    if isinstance(ir, Fstr):
        return _joined("", (_texts(index, facts, part, deeper) for part in ir.parts))
    if isinstance(ir, Add):
        parts = (_texts(index, facts, part, deeper) for part in (ir.left, ir.right))
        return _joined("", parts)
    if isinstance(ir, Call) and len(ir.args) == 1 and not ir.keywords:
        called = {value.ref for value in index.fold(facts, ir.func) if value.kind == "ext"}
        if called == {"textwrap.dedent"}:
            inner = _texts(index, facts, ir.args[0], deeper)
            return None if inner is None else {textwrap.dedent(text) for text in inner}
        separator = ir.func
        if (
            isinstance(separator, Attr)
            and separator.attr == "join"
            and isinstance(separator.base, Const)
            and isinstance(separator.base.value, str)
            and isinstance(ir.args[0], Seq)
        ):
            items = (_texts(index, facts, item, deeper) for item in ir.args[0].items)
            return _joined(separator.base.value, items)
    return None


def _parseable(text: str) -> str | None:
    """Der Text, wie Python ihn liest; ein offener Teil am Zeilenanfang kann ein ganzer Block
    sein (``_kopf() + "import os\\n…"``) und steht dann als eigene Zeile davor."""
    variants = [text]
    if PLACEHOLDER in text:
        lines = []
        for line in text.split("\n"):
            rest = line.lstrip()
            indent = line[: len(line) - len(rest)]
            if rest.startswith(PLACEHOLDER) and rest != PLACEHOLDER:
                line = f"{indent}{PLACEHOLDER}\n{indent}{rest[len(PLACEHOLDER) :]}"
            lines.append(line)
        variants.append("\n".join(lines))
    for variant in variants:
        try:
            ast.parse(variant)
        except SyntaxError, ValueError:
            continue
        return variant
    return None


def _joined(separator: str, parts: Iterable[set[str] | None]) -> set[str] | None:
    """Jede Kombination der Teile; ein offener Teil wird :data:`PLACEHOLDER`."""
    options = [part if part is not None else {PLACEHOLDER} for part in parts]
    size = 1
    for option in options:
        size *= len(option)
        if size > MOST_TEXTS:
            return None
    return {separator.join(combination) for combination in itertools.product(*options)}


def runs_python(index: Index, host: Facts, site: Script) -> bool:
    """Ob der Befehl um ``site`` ein Python startet: ja, wenn einer der Werte des Kopfes eines
    ist, unabhängig von ihrer Reihenfolge (RR2-4). Bleibt ein Wert offen, entscheidet der
    Kopf im Quelltext (``str(python)``)."""
    if site.head is None:
        return True
    undecided = False
    values = index.fold(host, site.head)
    for value in values:
        if value.kind == "ext" and value.ref == "sys.executable":
            return True
        if value.kind == "const" and isinstance(value.data, str):
            if "python" in value.data.lower():
                return True
        else:
            undecided = True
    return (undecided or not values) and "python" in site.head_text.lower()


def scan(index: Index) -> Found:
    """Jedes Skript des Baums, mit seinen Bezügen an der Stelle des Skripts im Aufruf."""
    found: dict[tuple[str, str], list[Reference]] = {}
    missing: list[Unresolved] = []
    counts: Counter[str] = Counter()
    for host in list(index.files.values()):
        for site in host.scripts:
            if not runs_python(index, host, site):
                continue
            counts["scripts.sites"] += 1
            found_texts = _texts(index, host, site.script)
            if found_texts is None:
                counts["scripts.open"] += 1
                continue
            if any(PLACEHOLDER in text for text in found_texts):
                counts["scripts.template"] += 1
            opened = False
            for number, text in enumerate(sorted(found_texts)):
                readable = _parseable(text)
                path = f"{host.path}#-c@{site.line}:{site.col}:{number}"
                facts = None if readable is None else extract_script(path, readable)
                if facts is None:
                    counts["scripts.unparsed"] += 1
                    continue
                counts["scripts.read"] += 1
                references, unresolved = index.scan_apart(facts)
                # Ein Modul oder Name aus dem Platzhalter steht erst zur Laufzeit fest: offen wie
                # ein ganzes Skript, weder Bezug noch Fund (RR2-3).
                kept = [item for item in unresolved if not _open(item.module, item.name)]
                opened |= len(kept) < len(unresolved)
                unresolved = kept
                for key, every in references.items():
                    items = [item for item in every if not _open(item.module, item.name)]
                    opened |= len(items) < len(every) or _open(*key)
                    if not items or _open(*key):
                        continue
                    found.setdefault(key, []).extend(
                        Reference(
                            host.path,
                            site.line,
                            site.col,
                            f"script:{item.kind}",
                            item.module,
                            item.name,
                            site.runtime,
                            item.checking,
                        )
                        for item in items
                    )
                missing.extend(
                    Unresolved(
                        host.path,
                        site.line,
                        site.col,
                        f"script:{item.kind}",
                        item.module,
                        item.name,
                        f"{item.text} (Skript, Zeile {item.line})",
                    )
                    for item in unresolved
                )
            if opened:
                counts["scripts.open"] += 1
    return found, missing, dict(counts)


def _open(module: str, name: str) -> bool:
    """Ob ein Bezug aus dem offenen Teil einer Vorlage stammt."""
    return PLACEHOLDER in module or PLACEHOLDER in name
