"""Ob der Empfänger eines Zugriffs im Komponentenmodus nachweislich der Wirt ist.

Review 2 über Paket M, RM-M18: Ein Zugriff ``x.m`` auf ein verschobenes Member wird nur dann
``x.<attr>.m``, wenn ``x`` **nachweislich** der Wirt ist, und bleibt nur dann stehen, wenn ``x``
nachweislich etwas anderes ist. Dass kein anderer Ort des Baums ein Member ``m`` definiert, ist
kein Nachweis: Fremde Typen tragen dieselben Namen (``QTimer.stop``, ``list.count``), ohne dass der
Baum sie definiert — ``timer.stop()`` wurde sonst ``timer.area.stop()``.

Nachweise, in dieser Reihenfolge:

* **der Auflöser** (Paket R): ``self`` einer Methode des Wirts oder einer Unterklasse und ein
  Exemplar ``Wirt(…)`` (auch über eine Zuweisung oder die Rückgabe eines Testhelfers) sind der
  Wirt; ein Exemplar einer anderen Klasse, ein Modul, eine Klasse, eine Funktion, ein Wert sind
  es nicht;
* **eine Annotation**, die der Auflöser auflöst — des Parameters oder der Variablen (ein Name,
  dessen Wert der Auflöser offen lässt) und die Rückgabe einer gerufenen Funktion des Baums: der
  Wirt oder eine Unterklasse ist der Wirt; eine Klasse, die der Wirt weder ist noch erbt
  (``QTimer``, ``Toast``), ist es nicht. ``Any``, ``object``, eine Basis des Wirts (``QObject``),
  ein Protokoll, ``type[…]`` und eine Annotation als Zeichenkette lassen es offen.

Ob eine fremde Klasse eine Basis des Wirts ist, sagt die Klasse selbst (``issubclass`` gegen die
geladenen fremden Basen des Wirts), keine Liste. Alles Übrige ist **offen** — ein Parameter ohne
Annotation, ``timers["main"]``, ein Attribut eines Objekts — und verlangt eine Entscheidung in
``[[accesses]]`` (oder eine Annotation, die es nachweist).
"""

from __future__ import annotations

import ast
import importlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from tools.code_index import Index, Val
from tools.move_compare import FileScopes
from tools.move_source import IMPORTS, Source, bound_name, module_of, own_statements, path_of

#: Die Urteile über einen Empfänger.
HOST = "host"
OTHER = "other"
OPEN = "open"
#: ``None``: weder Wirt noch etwas anderes — in einer Vereinigung ohne Gewicht.
NEUTRAL = "neutral"

#: Formen, deren erstes Argument der eigentliche Typ ist.
_WRAPPERS = frozenset(
    {
        "typing.Optional",
        "typing.Annotated",
        "typing.ClassVar",
        "typing.Final",
        "typing_extensions.Annotated",
    }
)
_UNIONS = frozenset({"typing.Union"})
_CLASS_OF = frozenset({"builtins.type", "typing.Type"})
_PROTOCOLS = frozenset({"typing.Protocol", "typing_extensions.Protocol"})
#: Eine Definition, in deren Rumpf eine weitere stehen kann.
Definition = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
DEFINITIONS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
#: Ein Parameter einer Methode, wie der Auflöser ihn nennt (``Klasse.methode:self``).
_SELF = re.compile(r"(?P<qual>[\w.]+):(?P<name>\w+)")


@dataclass(frozen=True)
class Judgement:
    """Das Urteil über einen Empfänger und sein Grund (für Meldung und Protokoll)."""

    verdict: str
    why: str


def combine(parts: Iterable[Judgement]) -> Judgement:
    """Mehrere mögliche Werte: Wirt nur, wenn jeder der Wirt ist; nicht der Wirt nur, wenn
    keiner es ist; sonst offen. ``None`` zählt nicht."""
    found = [p for p in parts if p.verdict != NEUTRAL]
    if not found:
        return Judgement(OTHER, "nur None")
    verdicts = {p.verdict for p in found}
    if verdicts == {HOST}:
        return Judgement(HOST, found[0].why)
    if verdicts == {OTHER}:
        return Judgement(OTHER, found[0].why)
    reasons = sorted({p.why for p in found if p.verdict != OTHER or len(verdicts) > 1})
    return Judgement(OPEN, "; ".join(reasons[:3]))


class Receivers:
    """Urteile über Empfänger für einen Wirt ``module:host`` an einem Baum (Auflöser
    ``index``, Quellen über ``source_of``, das ``None`` für eine fehlende Datei liefert)."""

    def __init__(
        self, index: Index, module: str, host: str, source_of: Callable[[str], Source | None]
    ) -> None:
        self.index = index
        self.module = module
        self.host = host
        self.host_ref = f"{module}:{host}"
        self.source_of = source_of
        self._scopes: dict[str, FileScopes] = {}
        self._classes: dict[str, str] = {}
        self._bases: dict[str, list[Val] | None] = {}
        self._loaded: dict[str, object] = {}
        #: Die Klassen des Baums, die der Wirt erbt, und seine fremden Basen (geladen).
        self.ancestors: set[str] = set()
        self.external: list[type] = []
        self.unloadable: list[str] = []
        self._ancestry()

    # ---- Klassen

    def _definition(self, ref: str) -> tuple[str, Definition] | None:
        """Die Definition ``modul:qualname`` (Klasse oder Funktion) im Baum samt Datei."""
        module, _, qualname = ref.partition(":")
        for path in (path_of(module), path_of(module, package=True)):
            source = self.source_of(path)
            if source is None:
                continue
            body: list[ast.stmt] = source.tree.body
            found: Definition | None = None
            for part in qualname.split("."):
                found = next(
                    (s for s in body if isinstance(s, DEFINITIONS) and s.name == part), None
                )
                if found is None:
                    return None
                body = found.body
            return (path, found) if found is not None else None
        return None

    def _base_values(self, ref: str) -> list[Val] | None:
        """Die aufgelösten Basen der Klasse ``ref`` des Baums; ``None``, wenn es sie nicht gibt."""
        if ref not in self._bases:
            found = self._definition(ref)
            node = found[1] if found is not None else None
            if found is None or not isinstance(node, ast.ClassDef):
                self._bases[ref] = None
            else:
                self._bases[ref] = [
                    value for base in node.bases for value in self.index.resolve(found[0], base)
                ]
        return self._bases[ref]

    def _ancestry(self) -> None:
        pending = [self.host_ref]
        seen: set[str] = set()
        while pending:
            ref = pending.pop()
            if ref in seen:
                continue
            seen.add(ref)
            for value in self._base_values(ref) or []:
                if value.kind == "class":
                    self.ancestors.add(value.ref)
                    pending.append(value.ref)
                elif value.kind == "ext":
                    loaded = self._load(value.ref)
                    if isinstance(loaded, type):
                        self.external.append(loaded)
                    else:
                        self.unloadable.append(value.ref)
                else:
                    self.unloadable.append(f"{value.kind} {value.ref}")

    def class_kind(self, ref: str) -> str:
        """Die Klasse ``ref`` des Baums: der Wirt oder eine Unterklasse (``host``), eine Basis
        des Wirts oder ein Protokoll (``open``), sonst ``other``; eine Klasse, die es nicht
        gibt, ist ``open``."""
        if ref not in self._classes:
            self._classes[ref] = OPEN  # gegen Kreise
            self._classes[ref] = self._class_kind(ref)
        return self._classes[ref]

    def _class_kind(self, ref: str) -> str:
        if ref == self.host_ref:
            return HOST
        if ref in self.ancestors:
            return OPEN
        bases = self._base_values(ref)
        if bases is None:
            return OPEN
        kinds: set[str] = set()
        for value in bases:
            if value.kind == "class":
                kinds.add(self.class_kind(value.ref))
            elif value.kind != "ext" or value.ref in _PROTOCOLS:
                kinds.add(OPEN)
        if HOST in kinds:
            return HOST
        return OPEN if OPEN in kinds else OTHER

    def _load(self, ref: str) -> object:
        """Das fremde Objekt hinter dem Punktnamen ``ref`` (Modul, dann Attribute), sonst
        ``None``."""
        if ref in self._loaded:
            return self._loaded[ref]
        parts = ref.split(".")
        found: object = None
        for cut in range(len(parts), 0, -1):
            try:
                found = importlib.import_module(".".join(parts[:cut]))
            except Exception:
                continue
            try:
                for name in parts[cut:]:
                    found = getattr(found, name)
            except AttributeError:
                found = None
            break
        self._loaded[ref] = found
        return found

    def external_kind(self, ref: str) -> Judgement:
        """Ein Exemplar der fremden Klasse ``ref``: der Wirt nur, wenn er von ihr erbt (dann
        offen), sonst nicht; eine Form, die keine Klasse ist (``Any``), oder ein Protokoll
        lassen es offen."""
        loaded = self._load(ref)
        if loaded is Any or loaded is object or getattr(loaded, "_is_protocol", False):
            # ``Any`` ist seit Python 3.11 eine Klasse, meint aber jeden Typ.
            return Judgement(OPEN, f"{ref} lässt jeden Typ zu")
        if not isinstance(loaded, type):
            return Judgement(OPEN, f"{ref} ist keine Klasse")
        if self.unloadable:
            return Judgement(OPEN, f"Basen des Wirts nicht ladbar ({', '.join(self.unloadable)})")
        if any(issubclass(base, loaded) for base in self.external):
            return Judgement(OPEN, f"{ref} ist eine Basis des Wirts")
        return Judgement(OTHER, f"ein {ref}, nicht der Wirt")

    # ---- Werte des Auflösers

    def value(self, path: str, value: Val) -> Judgement:
        kind, ref = value.kind, value.ref
        if kind == "const" and value.data is None:
            return Judgement(NEUTRAL, "None")
        if kind in ("module", "def", "const", "seq", "map", "path", "missing", "request", "spec"):
            return Judgement(OTHER, f"laut Auflöser ein Wert der Art {kind}, nicht der Wirt")
        if kind == "ext":
            return Judgement(OTHER, f"laut Auflöser {ref}, nicht der Wirt")
        if kind == "class":
            if self.class_kind(ref) == HOST:
                return Judgement(OPEN, f"die Klasse {ref} selbst, kein Exemplar")
            return Judgement(OTHER, f"laut Auflöser die Klasse {ref}, nicht der Wirt")
        if kind == "obj":
            return self._object(path, ref)
        return Judgement(OPEN, f"laut Auflöser offen ({ref})")

    def _object(self, path: str, ref: str) -> Judgement:
        if ref.endswith("()") and " " not in ref:
            callee = ref[:-2]
            if ":" in callee:
                return self._call_of(callee)
            if "." in callee:
                instance = self.external_kind(callee)
                if instance.verdict == OTHER:
                    return Judgement(OTHER, f"laut Auflöser {instance.why}")
                return Judgement(OPEN, f"Ergebnis von {callee}() ({instance.why})")
            return Judgement(OPEN, f"Ergebnis von {callee}()")
        match = _SELF.fullmatch(ref)
        if match is not None:
            owner = match.group("qual").rpartition(".")[0]
            if not owner:
                return Judgement(OPEN, f"laut Auflöser offen ({ref})")
            kind = self.class_kind(f"{module_of(path)}:{owner}")
            if kind == HOST:
                return Judgement(
                    HOST, f"laut Auflöser {match.group('name')} einer Methode von {owner}"
                )
            if kind == OTHER:
                return Judgement(OTHER, f"laut Auflöser self von {owner}, nicht der Wirt")
            return Judgement(OPEN, f"self von {owner}, einer Basis des Wirts")
        if ref.startswith("Fixture "):
            return Judgement(OTHER, f"laut Auflöser die {ref} von pytest")
        return Judgement(OPEN, f"laut Auflöser offen ({ref})")

    def _call_of(self, callee: str) -> Judgement:
        """Das Ergebnis von ``modul:qualname()``: ein Exemplar der Klasse oder die Rückgabe der
        Funktion laut ihrer Annotation."""
        found = self._definition(callee)
        if found is None:
            return Judgement(OPEN, f"Ergebnis von {callee}()")
        path, node = found
        if isinstance(node, ast.ClassDef):
            kind = self.class_kind(callee)
            if kind == HOST:
                return Judgement(HOST, f"laut Auflöser ein Exemplar von {callee}")
            if kind == OTHER:
                return Judgement(OTHER, f"laut Auflöser ein Exemplar von {callee}, nicht der Wirt")
            return Judgement(OPEN, f"ein Exemplar von {callee}, einer Basis des Wirts")
        returns = getattr(node, "returns", None)
        if returns is None:
            return Judgement(OPEN, f"Rückgabe von {callee}() ohne Annotation")
        judged = self.annotation(path, returns)
        return Judgement(judged.verdict, f"{judged.why} (Rückgabe von {callee})")

    # ---- Annotationen

    def annotation(self, path: str, node: ast.expr) -> Judgement:
        """Was eine Annotation über den Wert sagt, den sie beschreibt."""
        text = ast.unparse(node)
        if isinstance(node, ast.Constant):
            if node.value is None:
                return Judgement(NEUTRAL, "None")
            return Judgement(OPEN, f"Annotation als Zeichenkette {text}")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return combine((self.annotation(path, node.left), self.annotation(path, node.right)))
        if isinstance(node, ast.Subscript):
            heads = {v.ref for v in self.index.resolve(path, node.value) if v.kind == "ext"}
            inner = node.slice
            items = list(inner.elts) if isinstance(inner, ast.Tuple) else [inner]
            if heads and heads <= _WRAPPERS:
                return self.annotation(path, items[0])
            if heads and heads <= _UNIONS:
                return combine(self.annotation(path, item) for item in items)
            if heads and heads <= _CLASS_OF:
                return Judgement(OPEN, f"Annotation {text}: eine Klasse, kein Exemplar")
            return self.annotation(path, node.value)
        parts: list[Judgement] = []
        for value in self.index.resolve(path, node):
            if value.kind == "class":
                kind = self.class_kind(value.ref)
                verdict = {HOST: HOST, OTHER: OTHER}.get(kind, OPEN)
                parts.append(Judgement(verdict, f"laut Annotation {text}"))
            elif value.kind == "ext":
                judged = self.external_kind(value.ref)
                why = f"laut Annotation {text}" if judged.verdict == OTHER else judged.why
                parts.append(Judgement(judged.verdict, why))
            elif value.kind == "const" and value.data is None:
                parts.append(Judgement(NEUTRAL, "None"))
            else:
                parts.append(Judgement(OPEN, f"Annotation {text} nicht auflösbar"))
        if not parts:
            return Judgement(OPEN, f"Annotation {text} nicht auflösbar")
        return combine(parts)

    def _scopes_of(self, source: Source) -> FileScopes:
        if source.path not in self._scopes:
            self._scopes[source.path] = FileScopes(source)
        return self._scopes[source.path]

    def annotation_of(self, source: Source, node: ast.Name) -> ast.expr | None:
        """Die Annotation der Bindung, die der Name ``node`` an seiner Stelle meint: Parameter
        der Funktion, die ihn bindet, eine annotierte Variable in ihr oder auf Modulebene."""
        name = node.id
        scopes = self._scopes_of(source).of(node)
        current: ast.AST = node
        for outer in source.ancestors(node):
            if isinstance(outer, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                targets = {
                    t.id
                    for generator in outer.generators
                    for t in ast.walk(generator.target)
                    if isinstance(t, ast.Name)
                }
                if name in targets and current is not outer.generators[0].iter:
                    return None  # die Laufvariable einer Abstraktion: keine Annotation
            elif isinstance(outer, ast.ClassDef) and any(current is s for s in outer.body):
                declared = _declared(outer, name)
                if declared is not None or _assigned(outer, name):
                    return declared
            elif isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                inside = (
                    current is outer.body
                    if isinstance(outer, ast.Lambda)
                    else any(current is s for s in outer.body)
                )
                table = scopes.table_of.get(id(outer)) if inside else None
                if table is not None and name in table.get_identifiers():
                    symbol = table.lookup(name)
                    if symbol.is_parameter():
                        return _parameter_annotation(outer, name)
                    if symbol.is_global() or symbol.is_declared_global():
                        break
                    if symbol.is_local():
                        return _declared(outer, name)
            current = outer
        return _declared(source.tree, name)

    # ---- Urteil

    def judge(self, path: str, source: Source, node: ast.expr) -> Judgement:
        """Ob ``node`` (ein Empfänger in ``path``) der Wirt ist: erst der Auflöser, dann — für
        einen Namen, den er offen lässt — die Annotation seiner Bindung."""
        values = self.index.resolve(path, node)
        found = (
            combine(self.value(path, v) for v in values)
            if values
            else Judgement(OPEN, "laut Auflöser ohne Wert")
        )
        if found.verdict != OPEN or not isinstance(node, ast.Name):
            return found
        annotation = self.annotation_of(source, node)
        if annotation is None:
            return Judgement(OPEN, f"{found.why}, ohne Annotation")
        judged = self.annotation(path, annotation)
        if judged.verdict in (HOST, OTHER):
            return judged
        return Judgement(OPEN, judged.why)


def _parameter_annotation(function: ast.AST, name: str) -> ast.expr | None:
    if isinstance(function, ast.Lambda):
        return None
    assert isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
    arguments = function.args
    every = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    every.extend(a for a in (arguments.vararg, arguments.kwarg) if a is not None)
    for argument in every:
        if argument.arg == name:
            if argument in (arguments.vararg, arguments.kwarg):
                return None  # ``*args: T`` beschreibt die Elemente, nicht den Namen
            return argument.annotation
    return None


def _assigned(scope: ast.AST, name: str) -> bool:
    """Ob der eigene Rumpf von ``scope`` ``name`` bindet (Zuweisung, Definition, Import)."""
    for stmt in own_statements(scope):
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store):
                return True
        if isinstance(stmt, DEFINITIONS) and stmt.name == name:
            return True
        if isinstance(stmt, IMPORTS) and any(bound_name(a) == name for a in stmt.names):
            return True
    return False


def _declared(scope: ast.AST, name: str) -> ast.expr | None:
    """Die Annotation ``name: T`` im eigenen Rumpf des Bereichs ``scope``."""
    for stmt in own_statements(scope):
        if (
            isinstance(stmt, ast.AnnAssign)
            and isinstance(stmt.target, ast.Name)
            and stmt.target.id == name
        ):
            return stmt.annotation
    return None
