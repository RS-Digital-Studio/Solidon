"""Qt im Komponentenmodus des Verschiebewerkzeugs: was nach einem Schnitt anders wirkte, obwohl
die Rümpfe gleich bleiben (Review 1 über Paket M, RM-M2 und RM-M8).

Ein ``QObject`` ist für Qt mehr als seine Rümpfe:

* ``self.sender()`` gilt dem **Empfänger** eines Signals. Nach dem Schnitt ist das die
  Komponente (wenn das Signal mit ihrer Methode verbunden ist) oder niemand (wenn eine Methode des
  Wirts sie aufruft) — weder ``self.sender()`` noch ``self._parent.sender()`` meint sicher, was
  es vorher meinte.
* Eine **Überschreibung** einer Methode der Qt-Basis (``timerEvent``, ``resizeEvent``,
  ``closeEvent``, ``show`` …) ruft Qt am Wirt; in der Komponente riefe Qt sie für die Komponente
  oder nie. Sie bleibt im Wirt (Konzept 3.3, „Was im Fenster bleibt“).
* ``eventFilter`` wirkt nur dort, wo es installiert ist: Es wandert nur, wenn weder eine bleibende
  Methode des Wirts noch eine andere Stelle den Wirt selbst als Filter installiert.
* Eine **Unterklasse** des Wirts, die ein verschobenes Member definiert, würde danach umgangen:
  Der Wirt ruft die Fassung der Komponente.

Welche Namen eine Qt-Basis trägt, sagt die Klasse selbst (``dir`` der Klasse aus PySide6); den
Weg dorthin über eigene Zwischenklassen löst der Auflöser (Paket R) auf.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from tools.code_index import Index
from tools.move_source import Source, SourceError, path_of

#: Was nur der Empfänger eines Signals weiß.
RECEIVER_MEMBERS = frozenset({"sender", "senderSignalIndex"})
#: Aufrufe, deren Argument ein Ereignisfilter ist.
FILTER_CALLS = frozenset({"installEventFilter", "removeEventFilter"})
#: Module, deren Klassen Qt-Basen sind.
QT_PACKAGES = ("PySide6.", "shiboken6.")


def qt_bases(index: Index, path: str, cls: ast.ClassDef) -> tuple[list[str], list[str]]:
    """Die Qt-Klassen (Punktnamen) unter den Basen von ``cls`` in der Datei ``path``, über
    eigene Zwischenklassen hinweg, und die Basen, die sich nicht auflösen ließen (Text)."""
    found: list[str] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    pending: list[tuple[str, ast.ClassDef]] = [(path, cls)]
    while pending:
        where, current = pending.pop()
        for base in current.bases:
            values = index.resolve(where, base)
            known = [v for v in values if v.kind in ("ext", "class")]
            if not values or len(known) != len(values):
                unresolved.append(f"{where}:{base.lineno} {ast.unparse(base)}")
                continue
            for value in known:
                if value.ref in seen:
                    continue
                seen.add(value.ref)
                if value.kind == "ext":
                    if value.ref.startswith(QT_PACKAGES):
                        found.append(value.ref)
                    continue
                located = _class_source(index.root, value.ref)
                if located is None:
                    unresolved.append(f"{where}:{base.lineno} {value.ref}")
                    continue
                pending.append(located)
    return sorted(set(found)), unresolved


def qt_members(refs: list[str]) -> tuple[frozenset[str], list[str]]:
    """Alle Namen der Qt-Klassen ``refs`` (``dir``) und die, die sich nicht laden ließen."""
    names: set[str] = set()
    problems: list[str] = []
    for ref in refs:
        module, _, name = ref.rpartition(".")
        try:
            loaded = getattr(importlib.import_module(module), name)
        except (ImportError, AttributeError) as error:
            problems.append(f"{ref} ({error})")
            continue
        names.update(dir(loaded))
    return frozenset(names), problems


def _class_source(root: Path, ref: str) -> tuple[str, ast.ClassDef] | None:
    """Die Klasse ``modul:qualname`` im Baum unter ``root`` samt ihrer Datei."""
    module, _, qualname = ref.partition(":")
    for path in (path_of(module), path_of(module, package=True)):
        full = root / path
        if not full.is_file():
            continue
        try:
            tree = Source(path, full.read_bytes()).tree
        except SourceError:
            return None
        body: list[ast.stmt] = tree.body
        found: ast.ClassDef | None = None
        for part in qualname.split("."):
            match = next(
                (
                    s
                    for s in body
                    if isinstance(s, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                    and s.name == part
                ),
                None,
            )
            if match is None:
                return None
            body = match.body
            found = match if isinstance(match, ast.ClassDef) else None
        return (path, found) if found is not None else None
    return None


def filter_argument(call: ast.Call) -> ast.expr | None:
    """Das Argument eines ``….installEventFilter(x)``/``removeEventFilter(x)``, sonst ``None``."""
    if (
        isinstance(call.func, ast.Attribute)
        and call.func.attr in FILTER_CALLS
        and len(call.args) == 1
        and not call.keywords
    ):
        return call.args[0]
    return None


def class_reference(module: str, source: Source, node: ast.ClassDef) -> str:
    """``modul:qualname`` einer Klasse, wie der Auflöser sie nennt."""
    names = [
        outer.name
        for outer in source.ancestors(node)
        if isinstance(outer, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    return f"{module}:{'.'.join([*reversed(names), node.name])}"
