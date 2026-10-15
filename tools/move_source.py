"""Quelltext für das Verschiebewerkzeug ``tools/move_names.py``: Lage, Spannen, Bindungen.

Was ein Ausdruck **bedeutet**, sagt allein der gemeinsame Auflöser ``tools/code_index.py``
(Paket R, Plan Schritt 0, 2.0). Dieses Modul beantwortet nur, was zum Schreiben und zum Beweis
gebraucht wird und was der Auflöser nicht liefert:

* wo eine Anweisung samt Dekoratoren und Kopfkommentar beginnt und endet (``tokenize``) und wie
  Byte- und Zeichenspalten zueinander stehen — ``ast`` zählt Spalten in UTF-8-Bytes, Text und
  ``tokenize`` in Zeichen;
* welche Namen eine Anweisung auf Modulebene bindet, liest und über ``global`` schreibt — aus
  ``symtable``, der Bereichsanalyse des Compilers selbst, nicht aus einem eigenen Auflöser;
* welche Importanweisung einen Namen an einer Stelle bindet (die Stelle, neben die ein neuer
  Import gehört). Ob der Name dort wirklich das Modul meint, fragt der Aufrufer bei R.
"""

from __future__ import annotations

import ast
import builtins
import io
import re
import symtable
import tokenize
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import PurePosixPath

#: Die Bereiche, die das Werkzeug liest und umschreibt (wie der Auflöser).
AREAS = ("app", "tools", "tests")

#: Größte Zeilenzahl eines neuen Moduls und einer Komponente (Konzept 3.1, Regel 1; 4.5).
LINE_LIMIT = 2000

FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
IMPORTS = (ast.Import, ast.ImportFrom)

BUILTINS = frozenset(dir(builtins))


class SourceError(Exception):
    """Eine Quelle lässt sich nicht so lesen, wie das Werkzeug sie braucht; die Meldung nennt
    den Ausweg."""


def module_of(path: str) -> str:
    """Der Punktname zu einem relativen Pfad (``app/x/__init__.py`` → ``app.x``)."""
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def path_of(module: str, *, package: bool = False) -> str:
    """Der relative Pfad zu einem Punktnamen; ein Paket liegt in seinem ``__init__.py``."""
    base = module.replace(".", "/")
    return f"{base}/__init__.py" if package else f"{base}.py"


def split_lines(text: str) -> list[str]:
    """Zeilen samt Zeilenende, getrennt nur an ``\\n`` — ``str.splitlines`` trennt auch an
    ``\\x0c`` und ``\\u2028`` in Zeichenketten, ``ast`` zählt dort keine neue Zeile."""
    lines = text.split("\n")
    out = [line + "\n" for line in lines[:-1]]
    if lines[-1]:
        out.append(lines[-1])
    return out


@dataclass(frozen=True)
class Comment:
    """Ein Kommentar: Zeile (ab 1), Zeichenspalte, Text samt ``#``."""

    line: int
    col: int
    text: str


class Source:
    """Eine Python-Datei, gelesen wie der Auflöser sie liest: UTF-8, Positionen wie ``ast``."""

    def __init__(self, path: str, data: bytes) -> None:
        self.path = path
        self.data = data
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SourceError(f"{path}: kein UTF-8 ({error}) — Datei als UTF-8 speichern") from None
        self.bom = text.startswith("﻿")
        self.text = text.removeprefix("﻿")
        if "\r" in self.text.replace("\r\n", ""):
            raise SourceError(
                f"{path}: einzelnes \\r als Zeilenende — Zeilenenden auf \\n oder \\r\\n stellen"
            )
        self.lines = split_lines(self.text)
        first = self.lines[0] if self.lines else "\n"
        self.newline = "\r\n" if first.endswith("\r\n") else "\n"
        try:
            self.tree = ast.parse(self.text, filename=path)
        except SyntaxError as error:
            raise SourceError(
                f"{path}:{error.lineno}: {error.msg} — Quelle zuerst reparieren"
            ) from None
        self._starts: list[int] = []
        offset = 0
        for line in self.lines:
            self._starts.append(offset)
            offset += len(line)
        self._starts.append(offset)
        self._comments: list[Comment] | None = None
        self._parents: dict[int, ast.AST] | None = None

    # ---- Positionen

    def char_col(self, line: int, byte_col: int) -> int:
        """Die Zeichenspalte zu einer Bytespalte von ``ast`` in Zeile ``line`` (ab 1)."""
        if line > len(self.lines):
            return 0
        raw = self.lines[line - 1].encode("utf-8")
        return len(raw[:byte_col].decode("utf-8"))

    def offset(self, line: int, byte_col: int) -> int:
        """Die Zeichenstelle im ganzen Text zu einer Position von ``ast``."""
        if line > len(self.lines):
            return len(self.text)
        return self._starts[line - 1] + self.char_col(line, byte_col)

    def line_start(self, line: int) -> int:
        return self._starts[min(line, len(self.lines) + 1) - 1]

    def line_end(self, line: int) -> int:
        """Die Stelle hinter dem Zeilenende von Zeile ``line``."""
        return self._starts[min(line, len(self.lines))]

    def node_text(self, node: ast.AST) -> str:
        line = getattr(node, "lineno", None)
        end_line = getattr(node, "end_lineno", None)
        col = getattr(node, "col_offset", None)
        end_col = getattr(node, "end_col_offset", None)
        if line is None or end_line is None or col is None or end_col is None:
            raise SourceError(f"{self.path}: Knoten {type(node).__name__} ohne Lage")
        return self.text[self.offset(line, col) : self.offset(end_line, end_col)]

    def indent_of(self, line: int) -> str:
        text = self.lines[line - 1]
        return text[: len(text) - len(text.lstrip(" \t"))]

    def lines_text(self, first: int, last: int) -> str:
        return "".join(self.lines[first - 1 : last])

    # ---- Kommentare

    def comments(self) -> list[Comment]:
        """Alle Kommentare der Datei, in Reihenfolge (``tokenize``)."""
        if self._comments is None:
            found: list[Comment] = []
            reader = io.StringIO(self.text).readline
            try:
                for token in tokenize.generate_tokens(reader):
                    if token.type == tokenize.COMMENT:
                        found.append(Comment(token.start[0], token.start[1], token.string))
            except (tokenize.TokenError, SyntaxError) as error:
                raise SourceError(f"{self.path}: nicht zerlegbar ({error})") from None
            self._comments = found
        return self._comments

    def comments_between(self, first: int, last: int) -> list[Comment]:
        """Kommentare in den Zeilen ``first`` bis ``last`` einschließlich."""
        return [c for c in self.comments() if first <= c.line <= last]

    def is_comment_line(self, line: int) -> bool:
        return self.lines[line - 1].lstrip().startswith("#")

    # ---- Eltern

    def parent(self, node: ast.AST) -> ast.AST | None:
        if self._parents is None:
            self._parents = {}
            for outer in ast.walk(self.tree):
                for child in ast.iter_child_nodes(outer):
                    self._parents[id(child)] = outer
        return self._parents.get(id(node))

    def ancestors(self, node: ast.AST) -> Iterator[ast.AST]:
        current = self.parent(node)
        while current is not None:
            yield current
            current = self.parent(current)


def docstring_node(body: list[ast.stmt]) -> ast.Expr | None:
    """Der Docstring eines Rumpfs als Knoten, wenn es einen gibt."""
    if body and isinstance(body[0], ast.Expr):
        value = body[0].value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return body[0]
    return None


def docstring_ids(tree: ast.AST) -> set[int]:
    """Die ``id`` jeder Docstring-Konstante: Prosa, kein Bezug — Zeichenketten darin werden nie
    umgeschrieben."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, *DEFINITIONS)):
            doc = docstring_node(node.body)
            if doc is not None:
                found.add(id(doc.value))
    return found


def dotted(node: ast.AST) -> str | None:
    """Ein Name oder eine Attributkette als Text (``app.legacy.rules``), sonst ``None``."""
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def is_type_checking(test: ast.expr) -> bool:
    """``if TYPE_CHECKING:`` oder ``if typing.TYPE_CHECKING:``."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    return isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"


def absolute_module(path: str, stmt: ast.ImportFrom) -> str:
    """Das Modul eines ``from``-Imports, relative Formen aufgelöst."""
    if not stmt.level:
        return stmt.module or ""
    package = module_of(path)
    if not path.endswith("__init__.py"):
        package = package.rpartition(".")[0]
    for _ in range(stmt.level - 1):
        package = package.rpartition(".")[0]
    return f"{package}.{stmt.module}" if stmt.module else package


def bound_name(alias: ast.alias) -> str:
    """Der Name, den ein Eintrag einer Importanweisung bindet."""
    return alias.asname or alias.name.partition(".")[0]


def names_source(value: str, path: str, module: str, moved: Iterable[str]) -> bool:
    """Ob die Zeichenkette ``value`` die Quelldatei ``path`` nennt (auch mit Backslash, ohne
    Endung oder nur ihr Dateiname), das Modul ``module`` (auch in ``"modul:name"`` oder mitten im
    Text) oder einen verschobenen Namen darunter (``moved``, Punktnamen ``modul.name``) — Text,
    der nach dem Schnitt ins Leere zeigte. Ein Pfad in das neue Paket (``app/x/ziel.py``) und ein
    Zielmodul (``app.x.ziel``) nennen die Quelle nicht."""
    slashed = value.replace("\\", "/")
    file_name = path.rpartition("/")[2]
    if path in slashed or slashed == file_name or slashed.endswith("/" + file_name):
        return True
    stem = re.escape(path.removesuffix(".py"))
    if re.search(rf"(?<![\w.]){stem}(?![\w/.])", slashed):
        return True
    if re.search(rf"(?<![\w.]){re.escape(module)}(?![\w.])", value):
        return True
    return any(re.search(rf"(?<![\w.]){re.escape(m)}(?!\w)", value) for m in moved)


# ------------------------------------------------------------------ Spannen von Anweisungen


@dataclass(frozen=True)
class Span:
    """Die Zeilen einer Anweisung samt allem, was vor ihr bis zur vorigen steht (Leerzeilen,
    Kopfkommentar): ``first`` bis ``last`` einschließlich, ``head`` ist die erste Zeile des
    Kopfkommentars, ``start`` die erste Zeile der Anweisung (mit Dekoratoren)."""

    first: int
    head: int
    start: int
    last: int


def statement_start(stmt: ast.stmt) -> int:
    decorators: list[ast.expr] = getattr(stmt, "decorator_list", [])
    return min([stmt.lineno, *(d.lineno for d in decorators)])


def spans(
    source: Source, body: list[ast.stmt], *, after: int = 0, until: int | None = None
) -> list[Span]:
    """Die Spannen der Anweisungen eines Rumpfs (Vorgabe: Modulebene). Was zwischen zwei
    Anweisungen steht, gehört zur folgenden — ein Kopfkommentar wandert mit seiner Definition —,
    was hinter der letzten steht, zur letzten. Teilen sich zwei Anweisungen eine Zeile (``a = 1;
    b = 2``), bricht das ab: Eine solche Zeile lässt sich nicht zerschneiden. Für einen
    Klassenrumpf nennt ``after`` die letzte Zeile des Kopfs und ``until`` die letzte der Klasse."""
    found: list[Span] = []
    previous_end = after
    for stmt in body:
        start = statement_start(stmt)
        assert stmt.end_lineno is not None
        if start <= previous_end:
            raise SourceError(
                f"{source.path}:{start}: zwei Anweisungen in einer Zeile — vor dem Schnitt auf "
                "eigene Zeilen stellen"
            )
        last_line = source.lines[stmt.end_lineno - 1]
        end_col = source.char_col(stmt.end_lineno, stmt.end_col_offset or 0)
        rest = last_line[end_col:].strip()
        if rest and not rest.startswith("#"):
            raise SourceError(
                f"{source.path}:{stmt.end_lineno}: hinter der Anweisung steht weiterer Code — "
                "vor dem Schnitt auf eigene Zeilen stellen"
            )
        head = start
        while head - 1 > previous_end and source.is_comment_line(head - 1):
            head -= 1
        found.append(Span(previous_end + 1, head, start, stmt.end_lineno))
        previous_end = stmt.end_lineno
    if found:
        last = found[-1]
        end = len(source.lines) if until is None else until
        found[-1] = Span(last.first, last.head, last.start, max(last.last, end))
    return found


def class_spans(source: Source, cls: ast.ClassDef) -> list[Span]:
    """Die Spannen der Anweisungen im Rumpf der Klasse ``cls``; der Docstring zählt mit."""
    parts: list[ast.expr] = [*cls.bases, *(k.value for k in cls.keywords)]
    head = max([cls.lineno, *(n.end_lineno or n.lineno for n in parts)])
    first = cls.body[0]
    head = min(head, statement_start(first) - 1)
    return spans(source, cls.body, after=head, until=cls.end_lineno)


# ------------------------------------------------------------- Namen einer Anweisung


@dataclass
class StatementNames:
    """Was eine Anweisung auf Modulebene mit Namen tut, nach ``symtable``.

    ``binds``: Namen, die sie auf Modulebene bindet (Definition, Zuweisung, Import in einem
    Block). ``reads``: Namen, die sie aus dem Modulnamensraum liest — auf Modulebene, in Klassen
    und in Funktionen als Global, auch in Annotationen (dort zur Typprüfung). ``writes``: Namen,
    die eine Funktion darin über ``global`` schreibt. ``string_reads``: Namen in Annotationen als
    Zeichenkette (``"Shape"``), die ``symtable`` nicht sieht."""

    binds: set[str] = field(default_factory=set)
    reads: set[str] = field(default_factory=set)
    writes: set[str] = field(default_factory=set)
    string_reads: set[str] = field(default_factory=set)
    identity: set[str] = field(default_factory=set)

    @property
    def all_reads(self) -> set[str]:
        return self.reads | self.string_reads


#: Namen, deren Wert die Identität des Moduls ist: Ein Schnitt ändert ihn.
IDENTITY_NAMES = frozenset({"__name__", "__file__", "__spec__", "__loader__", "__package__"})
IDENTITY_CALLS = frozenset({"globals", "vars", "locals"})


def statement_names(source: Source, stmt: ast.stmt, span: Span) -> StatementNames:
    """Die Namen der Anweisung ``stmt`` auf Modulebene. Gelesen wird der Text der Anweisung
    allein, ohne ``from __future__``: So zählt ``symtable`` auch Annotationen als Leser —
    gebraucht werden ihre Namen zur Typprüfung, also im Ziel unter ``TYPE_CHECKING``."""
    text = source.lines_text(span.start, stmt.end_lineno or span.start)
    result = StatementNames()
    try:
        table = symtable.symtable(text, source.path, "exec")
    except SyntaxError as error:
        raise SourceError(f"{source.path}:{span.start}: nicht einzeln lesbar ({error})") from None
    _collect(table, result, top=True)
    for node in ast.walk(stmt):
        for annotation in _annotations(node):
            for inner in ast.walk(annotation):
                if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                    result.string_reads.update(_string_annotation_names(inner.value))
        if isinstance(node, ast.Name) and node.id in IDENTITY_NAMES:
            result.identity.add(node.id)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in IDENTITY_CALLS
            and not node.args
        ):
            result.identity.add(f"{node.func.id}()")
    return result


def _collect(table: symtable.SymbolTable, result: StatementNames, *, top: bool) -> None:
    for symbol in table.get_symbols():
        name = symbol.get_name()
        if top:
            if symbol.is_referenced():
                result.reads.add(name)
            if symbol.is_assigned() or symbol.is_imported():
                result.binds.add(name)
            continue
        if (symbol.is_global() or symbol.is_declared_global()) and symbol.is_referenced():
            result.reads.add(name)
        if symbol.is_declared_global() and symbol.is_assigned():
            result.writes.add(name)
    for child in table.get_children():
        _collect(child, result, top=False)


def _annotations(node: ast.AST) -> list[ast.expr]:
    found: list[ast.expr] = []
    if isinstance(node, ast.arg) and node.annotation is not None:
        found.append(node.annotation)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
        found.append(node.returns)
    elif isinstance(node, ast.AnnAssign):
        found.append(node.annotation)
    return found


def _string_annotation_names(text: str) -> set[str]:
    try:
        expression = ast.parse(text.strip(), mode="eval")
    except SyntaxError:
        return set()
    return {node.id for node in ast.walk(expression) if isinstance(node, ast.Name)}


# ----------------------------------------------------------- Importbindungen an einer Stelle


def scope_of(source: Source, node: ast.AST) -> ast.AST:
    """Der Bereich, dessen Namensraum ``node`` liest: die innerste umschließende Funktion, die
    Klasse, wenn ``node`` direkt in ihrem Rumpf steht, sonst das Modul. Eine Funktion in einer
    Klasse sieht die Klasse nicht (Python)."""
    for outer in source.ancestors(node):
        if isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if _in_signature(outer, node):
                continue
            return outer
        if isinstance(outer, ast.ClassDef):
            if any(_contains(stmt, node) for stmt in outer.body):
                return outer
            continue
    return source.tree


def _contains(root: ast.AST, target: ast.AST) -> bool:
    return any(child is target for child in ast.walk(root))


def _in_signature(function: ast.AST, node: ast.AST) -> bool:
    """Ob ``node`` in Dekoratoren, Vorgaben oder Annotationen von ``function`` steht — die laufen
    im umschließenden Bereich."""
    if isinstance(function, ast.Lambda):
        return any(_contains(d, node) for d in function.args.defaults)
    assert isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
    outer = [*function.decorator_list, *function.args.defaults]
    outer.extend(d for d in function.args.kw_defaults if d is not None)
    if function.returns is not None:
        outer.append(function.returns)
    for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]:
        if arg.annotation is not None:
            outer.append(arg.annotation)
    return any(_contains(part, node) for part in outer)


def own_statements(scope: ast.AST) -> Iterator[ast.stmt]:
    """Die Anweisungen, die im Namensraum ``scope`` laufen — ohne die Rümpfe darin
    geschachtelter Funktionen und Klassen."""
    body: list[ast.stmt] = getattr(scope, "body", [])
    if isinstance(scope, ast.Lambda):
        return
    stack: list[ast.stmt] = list(reversed(body))
    while stack:
        stmt = stack.pop()
        yield stmt
        if isinstance(stmt, DEFINITIONS):
            continue
        inner: list[ast.stmt] = []
        for name in ("body", "orelse", "finalbody"):
            inner.extend(getattr(stmt, name, []))
        for handler in getattr(stmt, "handlers", []):
            inner.extend(handler.body)
        for case in getattr(stmt, "cases", []):
            inner.extend(case.body)
        stack.extend(reversed(inner))


def import_binders(source: Source, name: str, use: ast.AST) -> list[ast.Import | ast.ImportFrom]:
    """Die Importanweisungen, die ``name`` für die Stelle ``use`` binden: im innersten Bereich
    auf dem Weg nach außen, der ``name`` über einen Import bindet. Mehrere im selben Bereich
    (Zweige eines ``if``) kommen alle zurück. Bindet ein Bereich ``name`` anders (Parameter,
    Zuweisung), meint ``use`` nicht den Import — das sagt dem Aufrufer der Auflöser."""
    scope: ast.AST = scope_of(source, use)
    while True:
        found = [
            stmt
            for stmt in own_statements(scope)
            if isinstance(stmt, IMPORTS) and any(bound_name(a) == name for a in stmt.names)
        ]
        if found:
            return found
        if isinstance(scope, ast.Module):
            return []
        scope = _outer_function_scope(source, scope)


def _outer_function_scope(source: Source, scope: ast.AST) -> ast.AST:
    """Der nächste Bereich nach außen, der für Namen aus ``scope`` zählt: Funktionen und das
    Modul, Klassen nicht."""
    for outer in source.ancestors(scope):
        if isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return outer
    return source.tree


def identifiers(tree: ast.AST) -> set[str]:
    """Jeder Name, den eine Datei bindet oder liest — für die Wahl eines freien Alias."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.arg):
            found.add(node.arg)
        elif isinstance(node, DEFINITIONS):
            found.add(node.name)
        elif isinstance(node, ast.alias):
            found.add(bound_name(node))
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            found.update(node.names)
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            found.add(node.name)
    return found
