"""Formen, die mehrere Teile des Verschiebewerkzeugs erkennen müssen — je eine Quelle.

Review 2 über Paket M, RM-M23: Dieselbe Auskunft stand mehrfach im Werkzeug und lief auseinander.
Eine Annotation als Zeichenkette wurde an fünf Stellen geparst; ob ein Aufruf einen Attributnamen
nimmt, entschieden sechs Stellen, zwei über den Auflöser, vier über den Namen im Quelltext — dort
blieb ``has = hasattr; has(M, "N")`` grün (RM-M20). Hier steht jede Antwort einmal:

* :func:`annotation_expression`, :func:`annotation_names` und :func:`is_annotation` — eine
  Annotation als Zeichenkette und ob ein Knoten eine Annotation ist;
* :class:`Calls` — ein Aufruf von ``getattr``/``hasattr``/``setattr``/``delattr`` (auch über einen
  Alias, ``from builtins import hasattr as has`` oder ``builtins.hasattr``) und ein Aufruf, der
  den Namensraum eines Objekts als Ganzes liest (``vars``, ``dir``, ``inspect.getmembers``) —
  erkannt über den Auflöser (Paket R), nicht über den Namen im Quelltext. Welche Dateien solche
  Aufrufe enthalten können, folgt aus den Namen, unter denen der Baum diese Funktionen bindet;
* :func:`patch_call` — ``monkeypatch.setattr``/``delattr`` und ``mock.patch.object`` mit einem
  Attributnamen an zweiter Stelle (Schreibweise, denn das Ziel ist ein Exemplar).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass

from tools.code_index import Index

#: Die eingebauten Funktionen, deren zweites Argument ein Attributname des ersten ist.
ATTRIBUTE_FUNCTIONS = {
    "builtins.getattr": "getattr",
    "builtins.hasattr": "hasattr",
    "builtins.setattr": "setattr",
    "builtins.delattr": "delattr",
}
#: Funktionen, die den Namensraum ihres Arguments als Ganzes lesen.
NAMESPACE_FUNCTIONS = {
    "builtins.vars": "vars",
    "builtins.dir": "dir",
    "inspect.getmembers": "getmembers",
}
#: Attribute, über die ein Objekt seinen Namensraum als Wert herausgibt.
NAMESPACE_ATTRIBUTES = frozenset({"__dict__"})
#: ``monkeypatch.setattr``/``delattr`` und ``patch.object``: der letzte Teil des Aufrufs.
PATCH_ATTRIBUTES = frozenset({"setattr", "delattr", "object"})


# ------------------------------------------------------------------ Annotationen


def annotation_expression(text: str) -> ast.expr | None:
    """Eine Annotation als Zeichenkette (``"Shape | None"``) als Ausdruck, sonst ``None``."""
    try:
        return ast.parse(text.strip(), mode="eval").body
    except SyntaxError, ValueError:
        return None


def annotation_names(text: str) -> set[str]:
    """Die Namen, die eine Annotation als Zeichenkette liest."""
    expression = annotation_expression(text)
    if expression is None:
        return set()
    return {node.id for node in ast.walk(expression) if isinstance(node, ast.Name)}


def is_annotation(parent: ast.AST | None, node: ast.AST) -> bool:
    """Ob ``node`` die Annotation von ``parent`` ist (Parameter, Rückgabe, Variable)."""
    if isinstance(parent, ast.arg):
        return parent.annotation is node
    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return parent.returns is node
    if isinstance(parent, ast.AnnAssign):
        return parent.annotation is node
    return False


# ------------------------------------------------------------------ Aufrufe


def folded_names(index: Index, path: str, node: ast.expr) -> frozenset[str] | None:
    """Die Zeichenketten, zu denen der Auflöser einen Attributnamen faltet (``name`` aus einer
    Schleife über ein Literal, eine Konstante, ein ``if``-Ausdruck); ``None``, wenn er ihn nicht
    ganz falten kann — dann ist der Name offen."""
    values = index.resolve(path, node)
    if not values or not all(v.kind == "const" and isinstance(v.data, str) for v in values):
        return None
    return frozenset(str(v.data) for v in values)


@dataclass(frozen=True)
class NamedCall:
    """Ein Aufruf mit einem Attributnamen an zweiter Stelle.

    ``kind``: ``getattr``, ``hasattr``, ``setattr``, ``delattr`` (eingebaut) oder ``patch``
    (``monkeypatch.setattr``/``delattr``, ``patch.object``). ``plain``: über den eingebauten
    Namen selbst gerufen — so, wie der Auflöser ``getattr`` als Bezug zählt."""

    call: ast.Call
    kind: str
    plain: bool

    @property
    def target(self) -> ast.expr:
        return self.call.args[0]

    @property
    def name(self) -> ast.expr:
        return self.call.args[1]

    @property
    def fixed(self) -> str | None:
        """Der Attributname, wenn er als Zeichenkette dasteht, sonst ``None``."""
        second = self.call.args[1]
        if isinstance(second, ast.Constant) and isinstance(second.value, str):
            return second.value
        return None


def is_query(kind: str | None, call: ast.Call) -> bool:
    """Ob ein Aufruf der Art ``kind`` eine Abfrage ist, die bei fehlendem Namen still antwortet:
    ``hasattr`` mit ``False``, ``getattr`` mit seiner Vorgabe."""
    return kind == "hasattr" or (kind == "getattr" and len(call.args) > 2)


def patch_call(call: ast.Call) -> bool:
    """``….setattr(x, "m", …)``, ``….delattr(x, "m")``, ``….object(x, "m")`` mit festem Namen."""
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr in PATCH_ATTRIBUTES
        and len(call.args) >= 2
        and isinstance(call.args[1], ast.Constant)
        and isinstance(call.args[1].value, str)
    )


class Calls:
    """Erkennt Aufrufe der Funktionen aus :data:`ATTRIBUTE_FUNCTIONS` und
    :data:`NAMESPACE_FUNCTIONS` an einem Baum (Auflöser ``index``, Dateien ``files``)."""

    def __init__(self, index: Index, files: Mapping[str, bytes]) -> None:
        self.index = index
        self.functions = {**ATTRIBUTE_FUNCTIONS, **NAMESPACE_FUNCTIONS}
        self.names = _aliases(index, files, self.functions)
        self._pattern = _words(self.names)

    def may_call(self, data: bytes) -> bool:
        """Ob eine Datei eine der Funktionen rufen kann (ihr Text nennt einen ihrer Namen)."""
        return bool(self._pattern.search(data))

    def _function(self, path: str, func: ast.expr) -> str | None:
        """Welche der Funktionen ``func`` laut Auflöser ist, sonst ``None``. Ein Name oder ein
        Attribut, das keinen ihrer Namen trägt, kann keine sein."""
        if isinstance(func, ast.Name) and func.id not in self.names:
            return None
        if isinstance(func, ast.Attribute) and func.attr not in self.names:
            return None
        return _function(self.index, path, func, self.functions)

    def named(self, path: str, call: ast.Call) -> NamedCall | None:
        """Ein Aufruf von ``getattr``/``hasattr``/``setattr``/``delattr`` mit mindestens zwei
        Argumenten, sonst ``None``."""
        if len(call.args) < 2 or any(isinstance(a, ast.Starred) for a in call.args[:2]):
            return None
        kind = self._function(path, call.func)
        if kind is None or kind not in ATTRIBUTE_FUNCTIONS.values():
            return None
        plain = isinstance(call.func, ast.Name) and call.func.id == kind
        return NamedCall(call, kind, plain)

    def namespace(self, path: str, node: ast.AST) -> ast.expr | None:
        """Das Objekt, dessen Namensraum ``node`` als Ganzes liest (``vars(X)``, ``dir(X)``,
        ``inspect.getmembers(X)``, ``X.__dict__``), sonst ``None``."""
        if isinstance(node, ast.Attribute) and node.attr in NAMESPACE_ATTRIBUTES:
            return node.value
        if not isinstance(node, ast.Call) or len(node.args) != 1:
            return None
        if self._function(path, node.func) in NAMESPACE_FUNCTIONS.values():
            return node.args[0]
        return None

    def every(self, path: str, tree: ast.AST) -> Iterator[NamedCall]:
        """Jeder Aufruf mit Attributnamen in ``tree`` (der Datei ``path``)."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                found = self.named(path, node)
                if found is not None:
                    yield found


def attribute_kind(index: Index, path: str, func: ast.expr) -> str | None:
    """Welche der Funktionen aus :data:`ATTRIBUTE_FUNCTIONS` der aufgerufene Ausdruck ``func``
    laut Auflöser ist (``getattr`` …), sonst ``None`` — für eine einzelne Stelle, an der
    :class:`Calls` nicht gebaut ist."""
    return _function(index, path, func, ATTRIBUTE_FUNCTIONS)


def _function(index: Index, path: str, func: ast.expr, functions: Mapping[str, str]) -> str | None:
    values = index.resolve(path, func)
    kinds = {functions.get(v.ref) if v.kind == "ext" else None for v in values}
    if len(kinds) != 1:
        return None
    return kinds.pop()


def _words(names: Iterable[str]) -> re.Pattern[bytes]:
    return re.compile(rb"\b(" + b"|".join(re.escape(n.encode()) for n in sorted(names)) + rb")\b")


def _aliases(
    index: Index, files: Mapping[str, bytes], functions: Mapping[str, str]
) -> frozenset[str]:
    """Die Namen, unter denen der Baum eine der ``functions`` rufen kann: ihre eigenen und jede
    Bindung auf Modulebene, die eine von ihnen ist — ``has = hasattr`` (laut Auflöser),
    ``from builtins import hasattr as has`` und der Import eines solchen Alias aus einem anderen
    Modul —, bis nichts mehr dazukommt."""
    # Erst hier: ``tools/move_source.py`` liest die Annotationshilfen dieses Moduls.
    from tools.move_source import absolute_module, module_of

    names = {ref.rpartition(".")[2] for ref in functions}
    pairs: set[tuple[str, str]] = set()
    grown = True
    while grown:
        grown = False
        pattern = _words(names)
        for path, data in files.items():
            if not path.endswith(".py") or not pattern.search(data):
                continue
            try:
                tree = ast.parse(data)
            except SyntaxError, ValueError:
                continue
            module = module_of(path)
            for stmt in tree.body:
                bound: list[str] = []
                if isinstance(stmt, ast.Assign) and _function(index, path, stmt.value, functions):
                    bound = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                elif isinstance(stmt, ast.ImportFrom):
                    origin = absolute_module(path, stmt)
                    bound = [
                        alias.asname or alias.name
                        for alias in stmt.names
                        if f"{origin}.{alias.name}" in functions or (origin, alias.name) in pairs
                    ]
                for name in bound:
                    if (module, name) not in pairs:
                        pairs.add((module, name))
                        names.add(name)
                        grown = True
    return frozenset(names)
