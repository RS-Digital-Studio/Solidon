"""Qt im Komponentenmodus des Verschiebewerkzeugs: was nach einem Schnitt anders wirkte, obwohl
die Rümpfe gleich bleiben (Review 1 über Paket M, RM-M2 und RM-M8).

Ein ``QObject`` ist für Qt mehr als seine Rümpfe:

* ``self.sender()`` gilt dem **Empfänger** eines Signals. Nach dem Schnitt ist das die
  Komponente (wenn das Signal mit ihrer Methode verbunden ist) oder niemand (wenn eine Methode des
  Wirts sie aufruft) — weder ``self.sender()`` noch ``self._parent.sender()`` meint sicher, was
  es vorher meinte.
* Eine **Überschreibung** einer Methode der Qt-Basis (``timerEvent``, ``resizeEvent``,
  ``closeEvent``, ``show`` …) ruft Qt am Wirt; in der Komponente riefe Qt sie für die Komponente
  oder nie. Sie bleibt im Wirt (Konzept 3.3, „Was im Fenster bleibt“). Dasselbe gilt für jede
  andere Basis (Review 2, RM-M19): ``logging`` ruft ``filter`` eines ``logging.Filter``, ein
  eigenes Mixin ruft über ``self.step()`` die Fassung des Wirts — nach dem Schnitt die eigene.
* ``eventFilter`` wirkt nur dort, wo es installiert ist: Es wandert nur, wenn weder eine bleibende
  Methode des Wirts noch eine andere Stelle den Wirt selbst als Filter installiert.
* Eine **Unterklasse** des Wirts, die ein verschobenes Member definiert, würde danach umgangen:
  Der Wirt ruft die Fassung der Komponente.

Welche Namen eine fremde Basis trägt, sagt die Klasse selbst (``dir``), welche eine eigene trägt,
ihr Rumpf; den Weg dorthin über eigene Zwischenklassen löst der Auflöser (Paket R) auf.
"""

from __future__ import annotations

import ast
import importlib
from dataclasses import dataclass, field
from pathlib import Path

from tools.code_index import Index
from tools.move_source import Source, SourceError, path_of

#: Was nur der Empfänger eines Signals weiß.
RECEIVER_MEMBERS = frozenset({"sender", "senderSignalIndex"})
#: Aufrufe, deren Argument ein Ereignisfilter ist.
FILTER_CALLS = frozenset({"installEventFilter", "removeEventFilter"})
#: Module, deren Klassen Qt-Basen sind.
QT_PACKAGES = ("PySide6.", "shiboken6.")


@dataclass
class Inherited:
    """Die Basen einer Klasse über eigene Zwischenklassen hinweg: fremde Qt-Klassen (``qt``,
    Punktnamen), andere fremde Klassen (``external``, etwa ``logging.Filter``), eigene Klassen
    des Baums (``own``, Datei und Definition) und Basen, die sich nicht auflösen ließen."""

    qt: list[str] = field(default_factory=list)
    external: list[str] = field(default_factory=list)
    own: list[tuple[str, ast.ClassDef]] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    def merged(self, other: Inherited) -> Inherited:
        return Inherited(
            sorted({*self.qt, *other.qt}),
            sorted({*self.external, *other.external}),
            [*self.own, *other.own],
            [*self.unresolved, *other.unresolved],
        )


def inherited(index: Index, path: str, cls: ast.ClassDef) -> Inherited:
    """Die Basen von ``cls`` in der Datei ``path``, über eigene Zwischenklassen hinweg
    (:class:`Inherited`). Der Weg über eigene Klassen kommt aus dem Auflöser (Paket R)."""
    found = Inherited()
    seen: set[str] = set()
    pending: list[tuple[str, ast.ClassDef]] = [(path, cls)]
    while pending:
        where, current = pending.pop()
        for base in current.bases:
            values = index.resolve(where, base)
            known = [v for v in values if v.kind in ("ext", "class")]
            if not values or len(known) != len(values):
                found.unresolved.append(f"{where}:{base.lineno} {ast.unparse(base)}")
                continue
            for value in known:
                if value.ref in seen:
                    continue
                seen.add(value.ref)
                if value.kind == "ext":
                    target = found.qt if value.ref.startswith(QT_PACKAGES) else found.external
                    target.append(value.ref)
                    continue
                located = _class_source(index.root, value.ref)
                if located is None:
                    found.unresolved.append(f"{where}:{base.lineno} {value.ref}")
                    continue
                found.own.append(located)
                pending.append(located)
    found.qt.sort()
    found.external.sort()
    return found


def loaded_members(refs: list[str]) -> tuple[dict[str, frozenset[str]], list[str]]:
    """Je fremder Klasse ``refs`` (Punktname) ihre Namen (``dir``) und die, die sich nicht laden
    ließen."""
    names: dict[str, frozenset[str]] = {}
    problems: list[str] = []
    for ref in refs:
        module, _, name = ref.rpartition(".")
        try:
            loaded = getattr(importlib.import_module(module), name)
        except (ImportError, AttributeError) as error:
            problems.append(f"{ref} ({error})")
            continue
        names[ref] = frozenset(dir(loaded))
    return names, problems


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
