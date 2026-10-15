"""Der Auszug je Datei für ``tools/code_index.py``: was eine Quelldatei bindet, liest und patcht.

Ein Auszug hängt nur am Inhalt seiner Datei — so lässt er sich nach Inhaltshash zwischenspeichern
(:func:`load_cache`, :func:`save_cache`), und die Auflösung über Dateien hinweg bleibt Sache von
:class:`tools.code_index.Index`. Gelesen wird in einem Durchgang über den Syntaxbaum:

- die Bereiche (Modul, Funktion, Lambda, Klasse, Abstraktion) mit ihren Bindungen, je mit Lage
  und Wert — ``def``, ``class``, Zuweisung (auch annotiert und entpackt), ``type X = …``,
  Import, Parameter, Schleifen-, ``with``-, ``except``- und ``match``-Ziele, ``:=`` und Ziele von
  ``global``; unter ``if``, ``try``, Schleifen und ``match`` als bedingt (:data:`COND`), unter
  ``TYPE_CHECKING`` getrennt (:data:`CHECKING`), weil sie zur Laufzeit nicht binden; je Bindung
  der Zweig jedes umschließenden ``if``/``match``, je Bereich die Zweige mit ihrer Bedingung
  und die Lage jeder Schleife;
- was der Code nach der Bindung in einen Behälter legt (``append``, ``add``, ``insert``,
  ``extend``, ``x[k] = v``, ``setdefault``, ``update``);
- je Funktion Parameter, Vorgaben, ``parametrize``, ``pytest.fixture`` und (in ``tests/``) die
  zurückgegebenen Werte;
- Attributketten auf Namen, ``getattr``/``hasattr``, Importe (auch späte und
  ``importlib.import_module``), Patch-Stellen in ``tests/``, Aufrufe von Testhelfern und die
  freien Globals jeder Funktion in ``app/`` und ``tools/``;
- die Lazy-Exporte (``_EXPORTS`` mit ``app.core.lazy.install``) und die Literale, mit denen ein
  ``__getattr__`` auf Modulebene seinen Namen vergleicht.

Ausdrücke werden als kleine, speicherbare Formen abgelegt (:data:`IR`); ein Name trägt seinen
Bereich und seine Lage, damit die Faltung ihn später so auflöst wie Python.
"""

from __future__ import annotations

import ast
import hashlib
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

#: Bereiche, deren Module der Index als Ziele prüft (W2 und W5).
INDEXED = ("app", "tools")
#: Bereiche, deren Dateien gelesen werden; ``tests`` liefert Patch-Stellen und Importe.
AREAS = ("app", "tools", "tests")

#: Längster Text, den der Auszug als Konstante hält: Ein Skript für ``python -c`` ist oft
#: ein ganzer Absatz (CS-18); im Baum stehen 262 Texte über 512 Zeichen, zusammen 0,3 MB.
LONGEST_TEXT = 1 << 16

COND = 1  # unter if/try/Schleife/match: kann fehlen
CHECKING = 2  # unter TYPE_CHECKING: bindet zur Laufzeit nicht
ANNOTATED = 4  # nur annotiert, ohne Wert
RUNTIME = 8  # globaler Schreibzugriff erst bei einem späteren Aufruf
DELETED = 16  # del name entfernt die bisherige Bindung


# ------------------------------------------------------------ Ausdrücke ohne Syntaxbaum (IR)
#
# Jede Form trägt hinten eine eigene Marke: Zwei NamedTuples mit gleichen Feldern wären als
# Tupel sonst gleich, und der Merker der Faltung verwechselte eine Konstante mit einem Grund.


class Const(NamedTuple):
    """Eine Konstante. Die Marke trägt den Typ: Als Tupel wären ``Const(False)`` und
    ``Const(0)`` gleich, und der Merker gäbe für ``raising=False`` eine ``0`` zurück."""

    value: object
    tag: str = "c"


def const(value: object) -> Const:
    return Const(value, f"c:{type(value).__name__}")


class Use(NamedTuple):
    """Ein gelesener Name mit dem Bereich und der Stelle, an der er steht."""

    name: str
    scope: int
    line: int
    col: int
    tag: str = "n"
    checking: bool = False


class Attr(NamedTuple):
    base: IR
    attr: str
    checking: bool = False
    tag: str = "a"


class Seq(NamedTuple):
    items: tuple[IR, ...]
    tag: str = "t"
    unordered: bool = False


class Table(NamedTuple):
    pairs: tuple[tuple[IR, IR], ...]
    tag: str = "d"


class Sub(NamedTuple):
    base: IR
    key: IR
    tag: str = "s"


class Call(NamedTuple):
    func: IR
    args: tuple[IR, ...]
    keywords: tuple[tuple[str, IR], ...]
    tag: str = "call"


class Fstr(NamedTuple):
    parts: tuple[IR, ...]
    tag: str = "f"


class Add(NamedTuple):
    left: IR
    right: IR
    tag: str = "+"


class Div(NamedTuple):
    """``left / right`` — für Pfade (``ROOT / "tools"``)."""

    left: IR
    right: IR
    tag: str = "/"


class IfExp(NamedTuple):
    test: IR
    body: IR
    orelse: IR
    tag: str = "if"


class Cmp(NamedTuple):
    op: str
    left: IR
    right: IR
    tag: str = "cmp"


class Not(NamedTuple):
    operand: IR
    tag: str = "not"


class ModRef(NamedTuple):
    """Die Bindung eines ``import M`` (das Modul)."""

    module: str
    tag: str = "mod"


class FromRef(NamedTuple):
    """Die Bindung eines ``from M import N``."""

    module: str
    name: str
    tag: str = "from"
    checking: bool = False


class Unpack(NamedTuple):
    """Das ``index``-te Element beim Entpacken von ``value``."""

    value: IR
    position: int
    tag: str = "item"


class Row(NamedTuple):
    """Ein Schleifenziel: je Element von ``iterable`` eine Zeile der Quelle ``key``."""

    key: str
    iterable: IR
    tag: str = "row"


class Param(NamedTuple):
    function: str
    name: str
    tag: str = "param"


class DefRef(NamedTuple):
    """Eine Funktion oder Klasse (``kind``), ``ref`` ist ``modul:qualname``."""

    ref: str
    kind: str
    tag: str = "def"


class Obj(NamedTuple):
    reason: str
    tag: str = "obj"


class Unknown(NamedTuple):
    reason: str
    tag: str = "u"


class Star(NamedTuple):
    """Ein ``*wert`` in einem Literal."""

    value: IR
    tag: str = "star"


class Comp(NamedTuple):
    """Eine Liste, Menge oder ein Generator aus einer Abstraktion: Elemente wie ``element``;
    bei einer Tabelle (``table``) ist ``element`` das Paar aus Schlüssel und Wert."""

    element: IR
    table: bool = False
    tag: str = "comp"


class Grown(NamedTuple):
    """Ein Behälter, den der Code danach füllt (``append``, ``add``, ``insert``, ``extend``)."""

    base: IR
    added: tuple[tuple[str, IR], ...]
    tag: str = "grown"


#: Eine der Formen oben. Bewusst keine Union der zwanzig Klassen: An der rekursiven Union
#: rechnete mypy über zwei Minuten an einer Datei, ohne fertig zu werden; die Formen
#: unterscheidet der Index ohnehin über ``isinstance``.
IR = tuple[object, ...]


# ----------------------------------------------------------------------------- Auszug


class Bind(NamedTuple):
    """Eine Bindung. ``branch`` nennt je umschließendem ``if``/``match`` desselben Bereichs
    den Zweig, sortiert — zwei Bindungen aus Geschwisterzweigen gelten nie zugleich."""

    line: int
    col: int
    value: IR
    flags: int
    branch: tuple[tuple[str, int], ...] = ()


@dataclass(slots=True)
class Scope:
    kind: str  # module, function, lambda, class, comprehension
    qualname: str
    parent: int
    runtime: bool  # läuft zur Aufrufzeit, in einem Funktionsrumpf
    span: tuple[int, int, int, int]
    hole: tuple[int, int, int, int] | None = None
    binds: dict[str, list[Bind]] = field(default_factory=dict)
    globals: set[str] = field(default_factory=set)
    loads: dict[str, int] = field(default_factory=dict)
    #: Zweige von ``if``/``match``: Schlüssel, Zweig, Lage und die Bedingung (``if``).
    regions: list[tuple[str, int, tuple[int, int, int, int], IR | None]] = field(
        default_factory=list
    )
    #: Lage jeder Schleife: Was in ihr später gebunden wird, gilt im nächsten Durchlauf vorn.
    loops: list[tuple[int, int, int, int]] = field(default_factory=list)
    #: Nicht bewiesene Ausführung: Schleifen und Ausnahme-/Erfolgsarme eines try.
    uncertain: list[tuple[int, int, int, int]] = field(default_factory=list)
    #: Abbrüche; break/continue wirken nur bis zum Ende der betreffenden Schleife.
    exits: list[tuple[int, int, tuple[int, int, int, int] | None]] = field(default_factory=list)


@dataclass(slots=True)
class Fn:
    qualname: str
    params: tuple[str, ...]
    defaults: dict[str, IR]
    parametrize: list[tuple[tuple[str, ...], IR]]
    fixture: str | None
    fixture_params: IR | None
    method: bool
    test: bool
    returns: list[IR] = field(default_factory=list)
    kwonly: tuple[str, ...] = ()
    vararg: str | None = None
    kwarg: str | None = None


class Ref(NamedTuple):
    """Ein Bezug. ``kind``: ``attr``, ``store``, ``del``, ``getattr``, ``getattr-default``,
    ``hasattr`` — oder ``query``/``query-default``: ein Aufruf über einen Namen, der in der Datei
    an ``getattr``/``hasattr`` gebunden wird (``has = hasattr``, ``builtins.hasattr``). Ob und
    welcher der beiden Eingebauten gerufen wird, faltet der Index für alle fünf aus ``func``."""

    kind: str
    scope: int
    line: int
    col: int
    base: IR
    attrs: tuple[str, ...]
    name: IR | None
    runtime: bool
    checking: bool
    func: IR | None = None


class Imp(NamedTuple):
    kind: str  # import, from, dynamic
    scope: int
    line: int
    col: int
    module: str
    name: str
    bound: str
    arg: IR | None
    runtime: bool
    checking: bool
    end_line: int = 0


class Patch(NamedTuple):
    form: str  # setattr, delattr, patch, patch.object
    scope: int
    line: int
    col: int
    args: tuple[IR, ...]
    keywords: tuple[tuple[str, IR], ...]
    func: IR | None
    text: str
    until: tuple[int, int] | None = None


class Site(NamedTuple):
    """Ein Aufruf eines Testhelfers, für die Faltung seiner Parameter."""

    func: IR
    args: tuple[IR, ...]
    keywords: tuple[tuple[str, IR], ...]


class Script(NamedTuple):
    """Ein Skript in einer Zeichenkette, das ein Befehl ``[kopf, …, "-c", skript, …]`` an einen
    Prozess gibt (CS-18). ``head`` ist ``None``, wenn ``-c`` vorn steht (Argumente, die vor
    einen Interpreter kommen), ``head_text`` der Kopf als Quelltext; Lage ist die des
    Skriptausdrucks."""

    scope: int
    line: int
    col: int
    head: IR | None
    head_text: str
    script: IR
    runtime: bool


@dataclass(slots=True)
class Facts:
    path: str
    module: str
    area: str
    package: bool
    stub: bool
    lines: int
    scopes: list[Scope] = field(default_factory=list)
    functions: dict[str, Fn] = field(default_factory=dict)
    refs: list[Ref] = field(default_factory=list)
    imports: list[Imp] = field(default_factory=list)
    patches: list[Patch] = field(default_factory=list)
    calls: list[Site] = field(default_factory=list)
    global_reads: dict[str, list[tuple[str, int]]] = field(default_factory=dict)
    #: Globals, die das Modul beim Import liest (Modulebene, Klassenrumpf): Erst ein
    #: ``importlib.reload`` liest sie neu.
    import_reads: dict[str, int] = field(default_factory=dict)
    #: ``importlib.reload(…)`` in Tests: Bereich, Zeile, Spalte, Argument.
    reloads: list[tuple[int, int, int, IR, IR]] = field(default_factory=list)
    resets: list[tuple[int, int, int]] = field(default_factory=list)
    exports: dict[str, tuple[str, str]] = field(default_factory=dict)
    dynamic_names: tuple[str, ...] = ()
    comprehensions: dict[tuple[int, int], int] = field(default_factory=dict)
    #: Abweichender Typ-/Headerkontext für öffentliche Abfragen an eigenen AST-Knoten.
    contexts: dict[tuple[int, int], tuple[int, bool]] = field(default_factory=dict)
    #: Skripte in Zeichenketten, die an ``python -c`` gehen; der Index liest sie wie Module.
    scripts: list[Script] = field(default_factory=list)


def to_ir(
    node: ast.expr | None,
    scope: int,
    depth: int = 0,
    comps: dict[tuple[int, int], int] | None = None,
    checking: bool = False,
) -> IR:
    """Ein Ausdruck als speicherbare Form; Namen tragen ihren Bereich und ihre Lage.

    ``comps`` nennt je Abstraktion (Zeile, Spalte) ihren Bereich; ohne ihn bleibt eine
    Abstraktion ``unknown``."""
    if node is None:
        return const(None)
    if depth > 24:
        return Unknown("zu tief verschachtelt")
    if isinstance(node, ast.Name):
        return Use(node.id, scope, node.lineno, node.col_offset, checking=checking)
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, str) and len(value) > LONGEST_TEXT:
            return Unknown("lange Zeichenkette")
        if value is None or isinstance(value, (str, int, float, bytes)):
            return const(value)
        return Unknown("Konstante")
    d = depth + 1
    if isinstance(node, ast.Attribute):
        return Attr(to_ir(node.value, scope, d, comps, checking), node.attr, checking)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        if len(node.elts) > 256:
            return Unknown("großes Literal")
        return Seq(
            tuple(
                Star(to_ir(e.value, scope, d, comps, checking))
                if isinstance(e, ast.Starred)
                else to_ir(e, scope, d, comps, checking)
                for e in node.elts
            ),
            unordered=isinstance(node, ast.Set),
        )
    if isinstance(node, ast.Dict):
        if len(node.keys) > 256 or any(k is None for k in node.keys):
            return Unknown("Tabelle")
        pairs = zip(node.keys, node.values, strict=True)
        return Table(
            tuple(
                (to_ir(k, scope, d, comps, checking), to_ir(v, scope, d, comps, checking))
                for k, v in pairs
            )
        )
    if isinstance(node, ast.Call):
        if any(isinstance(a, ast.Starred) for a in node.args) or any(
            k.arg is None for k in node.keywords
        ):
            return Unknown("entpackter Aufruf")
        return Call(
            to_ir(node.func, scope, d, comps, checking),
            tuple(to_ir(a, scope, d, comps, checking) for a in node.args),
            tuple(
                (k.arg, to_ir(k.value, scope, d, comps, checking)) for k in node.keywords if k.arg
            ),
        )
    if isinstance(node, ast.Subscript):
        return Sub(
            to_ir(node.value, scope, d, comps, checking),
            to_ir(node.slice, scope, d, comps, checking),
        )
    if isinstance(node, ast.JoinedStr):
        parts: list[IR] = []
        for part in node.values:
            if isinstance(part, ast.Constant):
                parts.append(const(part.value))
            elif (
                isinstance(part, ast.FormattedValue)
                and part.format_spec is None
                and part.conversion in (-1, 115)
            ):
                parts.append(to_ir(part.value, scope, d, comps, checking))
            else:
                # Ein Teil mit Umwandlung (``!r``) oder Format bleibt offen, der Rest des Texts
                # bleibt lesbar (ein Skript mit eingesetztem Pfad, CS-18).
                parts.append(Unknown("formatierter Teil"))
        return Fstr(tuple(parts))
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Div)):
        left, right = (
            to_ir(node.left, scope, d, comps, checking),
            to_ir(node.right, scope, d, comps, checking),
        )
        return Add(left, right) if isinstance(node.op, ast.Add) else Div(left, right)
    if isinstance(node, ast.IfExp):
        test, body = (
            to_ir(node.test, scope, d, comps, checking),
            to_ir(node.body, scope, d, comps, checking),
        )
        return IfExp(test, body, to_ir(node.orelse, scope, d, comps, checking))
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left, right = (
            to_ir(node.left, scope, d, comps, checking),
            to_ir(node.comparators[0], scope, d, comps, checking),
        )
        return Cmp(type(node.ops[0]).__name__, left, right)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return Not(to_ir(node.operand, scope, d, comps, checking))
        operand = node.operand
        if (
            isinstance(node.op, ast.USub)
            and isinstance(operand, ast.Constant)
            and isinstance(operand.value, (int, float))
        ):
            return const(-operand.value)
    if isinstance(node, ast.Lambda):
        return Obj("lambda")
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)) and comps:
        inner = comps.get((node.lineno, node.col_offset))
        if inner is not None and isinstance(node, ast.DictComp):
            pair = Seq(
                (
                    to_ir(node.key, inner, d, comps, checking),
                    to_ir(node.value, inner, d, comps, checking),
                )
            )
            return Comp(pair, True)
        if inner is not None and not isinstance(node, ast.DictComp):
            return Comp(to_ir(node.elt, inner, d, comps, checking))
    return Unknown(type(node).__name__)


def _dotted(node: ast.expr) -> str | None:
    """``a.b.c`` als Text, sonst ``None``."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _span(first: ast.expr | ast.stmt, last: ast.expr | ast.stmt) -> tuple[int, int, int, int]:
    end = (last.end_lineno or 0, last.end_col_offset or 0)
    return (first.lineno, first.col_offset, *end)


def _end(node: ast.expr | ast.stmt) -> tuple[int, int]:
    return (node.end_lineno or 0, node.end_col_offset or 0)


def _argnames(node: ast.expr) -> tuple[str, ...]:
    """Die Namen eines ``parametrize`` aus ``"a, b"`` oder einem Literal von Texten."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return tuple(name.strip() for name in node.value.split(",") if name.strip())
    if isinstance(node, (ast.Tuple, ast.List)):
        names = [e.value for e in node.elts if isinstance(e, ast.Constant)]
        if len(names) == len(node.elts) and all(isinstance(n, str) for n in names):
            return tuple(str(n) for n in names)
    return ()


def _compared_names(node: ast.FunctionDef | ast.AsyncFunctionDef, param: str) -> set[str]:
    """Die Texte, mit denen ein ``__getattr__`` seinen Parameter vergleicht."""
    found: set[str] = set()
    for sub in ast.walk(node):
        if not (
            isinstance(sub, ast.Compare)
            and isinstance(sub.left, ast.Name)
            and sub.left.id == param
            and len(sub.ops) == 1
        ):
            continue
        right = sub.comparators[0]
        if isinstance(sub.ops[0], ast.Eq) and isinstance(right, ast.Constant):
            found.add(str(right.value))
        elif isinstance(sub.ops[0], ast.In) and isinstance(right, (ast.Tuple, ast.Set, ast.List)):
            found.update(str(e.value) for e in right.elts if isinstance(e, ast.Constant))
    return found


def _export_table(table: Table) -> dict[str, tuple[str, str]]:
    exports: dict[str, tuple[str, str]] = {}
    for key, value in table.pairs:
        if not (isinstance(key, Const) and isinstance(key.value, str) and isinstance(value, Seq)):
            continue
        parts = [item.value for item in value.items if isinstance(item, Const)]
        if len(parts) == 2 and all(isinstance(p, str) for p in parts):
            exports[key.value] = (str(parts[0]), str(parts[1]))
    return exports


class _Extractor:
    """Liest eine Datei in einem Durchgang: Bereiche, Bindungen, Bezüge, Importe, Patches."""

    def __init__(self, facts: Facts) -> None:
        self.f = facts
        self.scope = 0
        self.runtime = False
        self.cond = 0
        self.checking = False
        self.fns: list[Fn | None] = [None]
        self.keep_loads = facts.area in INDEXED
        self.in_tests = facts.area == "tests"
        self.pending: list[tuple[ast.Call, int]] = []
        self.installs = False
        self.branch: tuple[tuple[str, int], ...] = ()
        self.comps: dict[tuple[int, int], int] = {}
        self.grows: list[tuple[int, str, tuple[int, int], str, IR]] = []
        self.patch_until: tuple[int, int] | None = None
        self.contexts: dict[str, tuple[int, int]] = {}
        #: Aufrufe mit zwei Argumenten über einen Namen oder ``….getattr``/``….hasattr``.
        self.maybe: list[tuple[ast.Call, int, bool, bool]] = []

    # ---- Bereiche und Bindungen

    def run(self, tree: ast.Module) -> None:
        self.f.scopes.append(Scope("module", "", -1, False, (0, 0, 1 << 30, 0)))
        self.body(tree.body)
        self.finish()

    def enter(
        self,
        kind: str,
        name: str,
        span: tuple[int, int, int, int],
        runtime: bool,
        hole: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, bool, int, tuple[tuple[str, int], ...]]:
        outer = self.f.scopes[self.scope]
        qualname = f"{outer.qualname}.{name}" if outer.qualname else name
        self.f.scopes.append(Scope(kind, qualname, self.scope, runtime, span, hole))
        saved = (self.scope, self.runtime, self.cond, self.branch)
        self.scope = len(self.f.scopes) - 1
        self.runtime = runtime
        self.cond = 0
        self.branch = ()
        return saved

    def leave(self, saved: tuple[int, bool, int, tuple[tuple[str, int], ...]]) -> None:
        self.scope, self.runtime, self.cond, self.branch = saved

    def branched(
        self, key: str, number: int, statements: list[ast.stmt], test: IR | None = None
    ) -> None:
        """Liest ``statements`` als Zweig ``number`` der Verzweigung ``key``; ``test`` ist die
        Bedingung eines ``if`` (Zweig 0 wahr, Zweig 1 falsch)."""
        if not statements:
            return
        span = _span(statements[0], statements[-1])
        self.f.scopes[self.scope].regions.append((key, number, span, test))
        saved = self.branch
        self.branch = tuple(sorted((*saved, (key, number))))
        self.body(statements)
        self.branch = saved

    def bind(self, name: str, value: IR, at: tuple[int, int], extra: int = 0) -> None:
        scopes = self.f.scopes
        scope = scopes[self.scope]
        flags = extra | (COND if self.cond else 0) | (CHECKING if self.checking else 0)
        if self.scope and name in scope.globals:
            scope = scopes[0]
            flags |= COND | RUNTIME
        branch = self.branch if scope is scopes[self.scope] else ()
        scope.binds.setdefault(name, []).append(Bind(at[0], at[1], value, flags, branch))

    def ir(self, node: ast.expr | None) -> IR:
        return to_ir(node, self.scope, comps=self.comps, checking=self.checking)

    def annotation(self, node: ast.expr | None) -> None:
        """Typbezüge werden geprüft, erzeugen aber keine Laufzeitleser."""
        if node is not None:
            saved = self.checking
            self.checking = True
            self.expr(node)
            self.checking = saved

    def type_scope(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.TypeAlias
    ) -> tuple[int, bool, int, tuple[tuple[str, int], ...]] | None:
        """Typparameter binden im eigenen Bereich, auch in Bounds und Vorgaben."""
        if not node.type_params:
            return None
        outer = self.f.scopes[self.scope]
        saved = self.enter("typeparams", "", _span(node, node), False)
        self.f.scopes[self.scope].qualname = outer.qualname
        for param in node.type_params:
            assert isinstance(param, (ast.TypeVar, ast.TypeVarTuple, ast.ParamSpec))
            self.bind(param.name, Obj("Typparameter"), (0, 0))
        for param in node.type_params:
            assert isinstance(param, (ast.TypeVar, ast.TypeVarTuple, ast.ParamSpec))
            if isinstance(param, ast.TypeVar):
                self.annotation(param.bound)
            self.annotation(param.default_value)
        return saved

    # ---- Anweisungen

    def body(self, statements: list[ast.stmt]) -> None:
        for statement in statements:
            self.stmt(statement)

    def stmt(self, node: ast.stmt) -> None:
        if isinstance(node, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            scope = self.f.scopes[self.scope]
            at = (node.lineno, node.col_offset)
            limit = None
            if isinstance(node, (ast.Break, ast.Continue)):
                limit = next((span for span in reversed(scope.loops) if inside(span, at)), None)
            scope.exits.append((*at, limit))
        if isinstance(node, ast.Expr):
            self.expr(node.value)
        elif isinstance(node, ast.Assign):
            self.expr(node.value)
            value = self.ir(node.value)
            for target in node.targets:
                self.target(target, value, _end(node))
        elif isinstance(node, ast.Return):
            if node.value is not None:
                self.expr(node.value)
                self.returned(node.value)
        elif isinstance(node, ast.If):
            self.if_(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.function(node)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            self.expr(node.iter)
            row = Row(f"{self.f.path}:for@{node.lineno}:{node.col_offset}", self.ir(node.iter))
            self.f.scopes[self.scope].loops.append(_span(node, node))
            self.f.scopes[self.scope].uncertain.append(_span(node, node))
            self.cond += 1
            self.target(node.target, row, _end(node.target))
            self.body(node.body)
            self.body(node.orelse)
            self.cond -= 1
        elif isinstance(node, ast.ImportFrom):
            self.import_from(node)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.partition(".")[0]
                self.imported("import", node, alias.name, "", bound, None)
                self.bind(bound, ModRef(alias.name if alias.asname else bound), _end(node))
        elif isinstance(node, ast.AnnAssign):
            self.annotation(node.annotation)
            if node.value is not None:
                self.expr(node.value)
                self.target(node.target, self.ir(node.value), _end(node))
            elif isinstance(node.target, ast.Name):
                self.bind(node.target.id, Unknown("annotiert"), _end(node), ANNOTATED)
            else:
                self.expr(node.target)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            saved_contexts = self.contexts.copy()
            for item in node.items:
                saved_until = self.patch_until
                self.patch_until = _end(node)
                self.expr(item.context_expr)
                self.patch_until = saved_until
                if item.optional_vars is not None:
                    self.target(item.optional_vars, Unknown("with"), _end(item.optional_vars))
                    if isinstance(item.optional_vars, ast.Name):
                        self.contexts[item.optional_vars.id] = _end(node)
            self.body(node.body)
            self.contexts = saved_contexts
        elif isinstance(node, (ast.Try, ast.TryStar)):
            self.cond += 1
            self.body(node.body)
            for handler in node.handlers:
                self.f.scopes[self.scope].uncertain.append(_span(handler.body[0], handler.body[-1]))
                if handler.type is not None:
                    self.expr(handler.type)
                if handler.name:
                    at = (handler.lineno, handler.col_offset)
                    self.bind(handler.name, Unknown("except"), at)
                self.body(handler.body)
            if node.orelse:
                self.f.scopes[self.scope].uncertain.append(_span(node.orelse[0], node.orelse[-1]))
            self.body(node.orelse)
            self.body(node.finalbody)
            self.cond -= 1
        elif isinstance(node, ast.ClassDef):
            self.class_(node)
        elif isinstance(node, ast.AugAssign):
            self.expr(node.value)
            if isinstance(node.target, ast.Name):
                self.load(node.target.id, node.lineno)
                grown: IR = Unknown("erweiterte Zuweisung")
                if isinstance(node.op, ast.Add):
                    # ``text += …`` ist der Wert davor plus der Zusatz; gelesen an der Stelle davor.
                    before = node.target.lineno, node.target.col_offset
                    grown = Add(
                        Use(node.target.id, self.scope, *before, checking=self.checking),
                        self.ir(node.value),
                    )
                self.bind(node.target.id, grown, _end(node))
            else:
                self.target(node.target, Unknown("erweiterte Zuweisung"), _end(node))
        elif isinstance(node, ast.While):
            self.expr(node.test)
            self.f.scopes[self.scope].loops.append(_span(node, node))
            self.f.scopes[self.scope].uncertain.append(_span(node, node))
            self.cond += 1
            self.body(node.body)
            self.body(node.orelse)
            self.cond -= 1
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.bind(target.id, Unknown("gelöscht"), _end(node), DELETED)
                elif isinstance(target, (ast.Attribute, ast.Subscript)):
                    self.target(target, Unknown("del"), _end(node))
        elif isinstance(node, ast.Global):
            self.f.scopes[self.scope].globals.update(node.names)
        elif isinstance(node, ast.Match):
            self.match(node)
        elif isinstance(node, ast.TypeAlias):
            saved_types = self.type_scope(node)
            self.annotation(node.value)
            if saved_types is not None:
                self.leave(saved_types)
            self.bind(node.name.id, Obj("type"), _end(node))
        elif not isinstance(node, ast.Nonlocal):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.expr):
                    self.expr(child)

    def if_(self, node: ast.If) -> None:
        test = node.test
        key = f"{self.f.path}:if@{node.lineno}:{node.col_offset}"
        if (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        ):
            saved = self.checking
            self.checking = True
            self.branched(key, 0, node.body)
            self.checking = saved
            self.cond += 1
            self.branched(key, 1, node.orelse)
            self.cond -= 1
            return
        self.expr(test)
        condition = self.ir(test)
        self.cond += 1
        self.branched(key, 0, node.body, condition)
        self.branched(key, 1, node.orelse, condition)
        self.cond -= 1

    def match(self, node: ast.Match) -> None:
        self.expr(node.subject)
        self.cond += 1
        key = f"{self.f.path}:match@{node.lineno}:{node.col_offset}"
        for number, case in enumerate(node.cases):
            saved = self.branch
            self.branch = tuple(sorted((*saved, (key, number))))
            for sub in ast.walk(case.pattern):
                if isinstance(sub, (ast.MatchAs, ast.MatchStar)) and sub.name:
                    self.bind(sub.name, Unknown("match"), (sub.lineno, sub.col_offset))
                elif isinstance(sub, ast.MatchMapping) and sub.rest:
                    self.bind(sub.rest, Unknown("match"), (sub.lineno, sub.col_offset))
                elif isinstance(sub, ast.MatchValue):
                    self.expr(sub.value)
                elif isinstance(sub, ast.MatchClass):
                    self.expr(sub.cls)
            if case.guard is not None:
                self.expr(case.guard)
            self.branched(key, number, case.body)
            self.branch = saved
        self.cond -= 1

    def import_from(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if node.level:
            base = self.f.module.split(".")
            if not self.f.package:
                base = base[:-1]
            base = base[: len(base) - (node.level - 1)]
            module = ".".join([*base, module] if module else base)
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname or alias.name
            self.imported("from", node, module, alias.name, bound, None)
            self.bind(bound, FromRef(module, alias.name, checking=self.checking), _end(node))

    def imported(
        self,
        kind: str,
        node: ast.stmt | ast.expr,
        module: str,
        name: str,
        bound: str,
        arg: IR | None,
    ) -> None:
        at = (node.lineno, node.col_offset)
        self.f.imports.append(
            Imp(
                kind,
                self.scope,
                *at,
                module,
                name,
                bound,
                arg,
                self.runtime,
                self.checking,
                node.end_lineno or node.lineno,
            )
        )

    def function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            self.expr(decorator)
        saved_types = self.type_scope(node)
        type_scope = self.scope if saved_types is not None else None
        args = node.args
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg):
            if arg is not None:
                self.annotation(arg.annotation)
        self.annotation(node.returns)
        if saved_types is not None:
            self.leave(saved_types)
        for default in (*args.defaults, *args.kw_defaults):
            if default is not None:
                self.expr(default)
                if type_scope is not None:
                    for part in ast.walk(default):
                        if isinstance(part, ast.expr):
                            self.f.contexts[(part.lineno, part.col_offset)] = (
                                self.scope,
                                self.checking,
                            )
        outer = self.f.scopes[self.scope]
        qualname = f"{outer.qualname}.{node.name}" if outer.qualname else node.name
        self.bind(node.name, DefRef(f"{self.f.module}:{qualname}", "def"), _end(node))
        positional = [*args.posonlyargs, *args.args]
        defaults: dict[str, IR] = {}
        for arg, default in zip(
            positional[len(positional) - len(args.defaults) :], args.defaults, strict=True
        ):
            defaults[arg.arg] = self.ir(default)
        for arg, kw_default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
            if kw_default is not None:
                defaults[arg.arg] = self.ir(kw_default)
        params = tuple(a.arg for a in positional)
        is_test = self.in_tests and node.name.startswith("test")
        fn = Fn(qualname, params, defaults, [], None, None, outer.kind == "class", is_test)
        fn.kwonly = tuple(a.arg for a in args.kwonlyargs)
        fn.vararg = args.vararg.arg if args.vararg else None
        fn.kwarg = args.kwarg.arg if args.kwarg else None
        self.decorators(node, fn)
        self.f.functions[qualname] = fn
        if self.scope == 0 and node.name == "__getattr__" and params:
            self.f.dynamic_names = tuple(sorted(_compared_names(node, params[0])))
        saved = self.enter("function", node.name, _span(node.body[0], node), True)
        if type_scope is not None:
            self.f.scopes[self.scope].parent = type_scope
        every = [*params, *(a.arg for a in args.kwonlyargs)]
        every += [a.arg for a in (args.vararg, args.kwarg) if a is not None]
        for name in every:
            self.bind(name, Param(qualname, name), (node.lineno, node.col_offset))
        self.fns.append(fn)
        self.body(node.body)
        self.fns.pop()
        self.leave(saved)

    def decorators(self, node: ast.FunctionDef | ast.AsyncFunctionDef, fn: Fn) -> None:
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            name = _dotted(call.func if call is not None else decorator)
            if name is None:
                continue
            if name.endswith("parametrize") and call is not None and len(call.args) >= 2:
                if any(k.arg == "indirect" for k in call.keywords):
                    continue
                names = _argnames(call.args[0])
                if names:
                    fn.parametrize.append((names, self.ir(call.args[1])))
            elif name in ("pytest.fixture", "fixture"):
                fn.fixture = node.name
                for keyword in call.keywords if call is not None else ():
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                        fn.fixture = str(keyword.value.value)
                    elif keyword.arg == "params":
                        fn.fixture_params = self.ir(keyword.value)

    def class_(self, node: ast.ClassDef) -> None:
        for decorator in node.decorator_list:
            self.expr(decorator)
        saved_types = self.type_scope(node)
        type_scope = self.scope if saved_types is not None else None
        for base in node.bases:
            self.expr(base)
        for keyword in node.keywords:
            self.expr(keyword.value)
        if saved_types is not None:
            self.leave(saved_types)
        outer = self.f.scopes[self.scope]
        qualname = f"{outer.qualname}.{node.name}" if outer.qualname else node.name
        self.bind(node.name, DefRef(f"{self.f.module}:{qualname}", "class"), _end(node))
        saved = self.enter("class", node.name, _span(node.body[0], node), self.runtime)
        if type_scope is not None:
            self.f.scopes[self.scope].parent = type_scope
        self.fns.append(None)
        self.body(node.body)
        self.fns.pop()
        self.leave(saved)

    def returned(self, value: ast.expr) -> None:
        fn = self.fns[-1]
        if fn is not None and self.in_tests:
            fn.returns.append(self.ir(value))

    def target(self, node: ast.expr, value: IR, at: tuple[int, int]) -> None:
        if isinstance(node, ast.Name):
            self.bind(node.id, value, at)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for number, element in enumerate(node.elts):
                if isinstance(element, ast.Starred):
                    self.target(element.value, Unknown("entpackt"), at)
                else:
                    self.target(element, Unpack(value, number), at)
        elif isinstance(node, ast.Attribute):
            self.chain(node)
        elif isinstance(node, ast.Subscript):
            self.expr(node.value)
            self.expr(node.slice)
            if isinstance(node.value, ast.Name):
                pair = Seq((self.ir(node.slice), value))
                self.grows.append((self.scope, node.value.id, at, "setitem", pair))
        elif isinstance(node, ast.Starred):
            self.target(node.value, Unknown("entpackt"), at)

    # ---- Ausdrücke

    def load(self, name: str, line: int) -> None:
        if self.keep_loads and not self.checking:
            loads = self.f.scopes[self.scope].loads
            if name not in loads:
                loads[name] = line

    def expr(self, node: ast.expr) -> None:
        if self.checking or self.f.scopes[self.scope].kind == "typeparams":
            self.f.contexts[(node.lineno, node.col_offset)] = self.scope, self.checking
        if isinstance(node, (ast.List, ast.Tuple)):
            self.command(node)
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                self.load(node.id, node.lineno)
        elif isinstance(node, ast.Attribute):
            self.chain(node)
        elif isinstance(node, ast.Call):
            self.call(node)
        elif isinstance(node, ast.Constant):
            return
        elif isinstance(node, ast.Lambda):
            self.lambda_(node)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            self.comprehension(node)
        elif isinstance(node, ast.NamedExpr):
            self.expr(node.value)
            saved = self.scope
            while self.f.scopes[self.scope].kind == "comprehension":
                self.scope = self.f.scopes[self.scope].parent
            self.bind(
                node.target.id,
                to_ir(node.value, saved, comps=self.comps, checking=self.checking),
                _end(node),
            )
            self.scope = saved
        elif isinstance(node, (ast.Yield, ast.YieldFrom)):
            if node.value is not None:
                self.expr(node.value)
                if isinstance(node, ast.Yield):
                    self.returned(node.value)
        else:
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.expr):
                    self.expr(child)
                elif isinstance(child, ast.keyword):
                    self.expr(child.value)

    def command(self, node: ast.List | ast.Tuple) -> None:
        """``[kopf, …, "-c", skript, …]``: Das Element hinter ``-c`` ist ein Skript, wenn
        davor nur Schalter eines Interpreters stehen (``-I``, ``-u``, ``-X faulthandler``) — nach
        ``-m modul`` oder einem Dateinamen gehört ``-c`` dem Programm (``pytest -c``). Ob der Kopf
        ein Python ist, entscheidet der Index (:class:`Script`); ``-c`` vorn heißt: kein Kopf."""
        elements = node.elts
        position = 0 if _text_is(elements[0] if elements else None, "-c") else 1
        while position < len(elements) - 1:
            element = elements[position]
            if not (isinstance(element, ast.Constant) and isinstance(element.value, str)):
                return
            if element.value == "-c":
                break
            if element.value in ("-X", "-W"):
                position += 2
            elif element.value.startswith("-") and element.value not in ("-", "-m"):
                position += 1
            else:
                return
        else:
            return
        script, head = elements[position + 1], elements[0] if position else None
        if isinstance(script, ast.Starred) or isinstance(head, ast.Starred):
            return
        head_ir = None if head is None else self.ir(head)
        head_text = "" if head is None else ast.unparse(head)
        at = (script.lineno, script.col_offset)
        self.f.scripts.append(
            Script(self.scope, *at, head_ir, head_text, self.ir(script), self.runtime)
        )

    def chain(self, node: ast.Attribute) -> None:
        attrs: list[str] = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            attrs.append(current.attr)
            current = current.value
        attrs.reverse()
        kind = "attr"
        if isinstance(node.ctx, ast.Store):
            kind = "store"
        elif isinstance(node.ctx, ast.Del):
            kind = "del"
        if isinstance(current, ast.Name):
            self.load(current.id, current.lineno)
            base: IR = Use(
                current.id, self.scope, current.lineno, current.col_offset, checking=self.checking
            )
        else:
            self.expr(current)
            if not isinstance(current, (ast.Call, ast.Subscript)):
                return
            base = self.ir(current)
        at = (node.lineno, node.col_offset)
        self.f.refs.append(
            Ref(kind, self.scope, *at, base, tuple(attrs), None, self.runtime, self.checking)
        )

    def call(self, node: ast.Call) -> None:
        func = node.func
        # Erst die Teile: Eine Abstraktion darin kennt danach ihren Bereich.
        self.expr(func)
        for arg in node.args:
            self.expr(arg)
        for keyword in node.keywords:
            self.expr(keyword.value)
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.attr in _FILLS
            and node.args
        ):
            at = (node.lineno, node.col_offset)
            added = self.ir(node.args[-1])
            if func.attr == "setdefault":
                added = Seq((self.ir(node.args[0]), added)) if len(node.args) > 1 else Unknown("")
                self.grows.append((self.scope, func.value.id, at, "setitem", added))
            else:
                self.grows.append((self.scope, func.value.id, at, func.attr, added))
        if self.in_tests:
            self.patch_call(node)
            if isinstance(func, ast.Name) or (
                isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
            ):
                self.pending.append((node, self.scope))
        if isinstance(func, ast.Name) and func.id in ("getattr", "hasattr") and len(node.args) >= 2:
            kind = func.id
            if kind == "getattr" and len(node.args) >= 3:
                kind = "getattr-default"
            at = (node.lineno, node.col_offset)
            base, name, called = (self.ir(part) for part in (node.args[0], node.args[1], func))
            # Mit ``func``: Ob der Name der eingebaute ist und kein Parameter oder eine eigene
            # Bindung gleichen Namens, faltet der Index wie beim Alias (RR2-6).
            self.f.refs.append(
                Ref(kind, self.scope, *at, base, (), name, self.runtime, self.checking, called)
            )
        elif len(node.args) >= 2 and (
            isinstance(func, ast.Name)
            or (isinstance(func, ast.Attribute) and func.attr in ("getattr", "hasattr"))
        ):
            # Vielleicht ``has(M, "N")`` mit ``has = hasattr``: ob ``has`` in der Datei so
            # gebunden wird, steht erst am Ende fest (:meth:`queries`).
            self.maybe.append((node, self.scope, self.runtime, self.checking))
        last = func.id if isinstance(func, ast.Name) else _dotted(func) or ""
        last = last.rpartition(".")[2]
        if last in ("import_module", "importorskip") and node.args:
            self.imported("dynamic", node, "", "", "", self.ir(node.args[0]))
        elif last == "install" and self.scope == 0:
            self.installs = True
        elif last == "reload" and self.in_tests and len(node.args) == 1:
            at = (node.lineno, node.col_offset)
            self.f.reloads.append((self.scope, *at, self.ir(node.args[0]), self.ir(func)))
        elif last in ("undo", "stop", "stopall") and self.in_tests:
            self.f.resets.append((self.scope, node.lineno, node.col_offset))

    def patch_call(self, node: ast.Call) -> None:
        func = node.func
        form = ""
        patch_func: IR | None = None
        if isinstance(func, ast.Attribute) and func.attr in ("setattr", "delattr"):
            form = func.attr
        elif isinstance(func, (ast.Name, ast.Attribute)):
            # Die Schreibweise des Alias sagt nichts über den wirklichen Aufrufer.
            form, patch_func = "candidate", self.ir(func)
        if not form:
            return
        text = ast.unparse(node)
        args = tuple(self.ir(a) for a in node.args)
        keywords = tuple((k.arg or "**", self.ir(k.value)) for k in node.keywords)
        at = (node.lineno, node.col_offset)
        short = text if len(text) <= 160 else text[:157] + "..."
        until = self.patch_until
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            until = until or self.contexts.get(func.value.id)
        self.f.patches.append(
            Patch(form, self.scope, *at, args, keywords, patch_func, short, until)
        )

    def lambda_(self, node: ast.Lambda) -> None:
        args = node.args
        for default in (*args.defaults, *args.kw_defaults):
            if default is not None:
                self.expr(default)
        positional = [*args.posonlyargs, *args.args]
        firsts = positional[len(positional) - len(args.defaults) :]
        defaults = {
            arg.arg: self.ir(value) for arg, value in zip(firsts, args.defaults, strict=True)
        }
        saved = self.enter("lambda", "<lambda>", _span(node.body, node.body), True)
        for arg in (*positional, *args.kwonlyargs, args.vararg, args.kwarg):
            if arg is not None:
                self.bind(arg.arg, defaults.get(arg.arg, Unknown("Lambdaparameter")), (0, 0))
        self.expr(node.body)
        self.leave(saved)

    def comprehension(
        self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp
    ) -> None:
        generators = node.generators
        self.expr(generators[0].iter)
        outer = self.scope
        hole = _span(generators[0].iter, generators[0].iter)
        saved = self.enter(
            "comprehension", "<comprehension>", _span(node, node), self.runtime, hole
        )
        self.comps[(node.lineno, node.col_offset)] = self.scope
        for number, generator in enumerate(generators):
            if number:
                self.expr(generator.iter)
            iterable = to_ir(
                generator.iter,
                outer if number == 0 else self.scope,
                comps=self.comps,
                checking=self.checking,
            )
            key = f"{self.f.path}:comp@{generator.iter.lineno}:{generator.iter.col_offset}"
            self.target(generator.target, Row(key, iterable), (0, 0))
            for condition in generator.ifs:
                self.expr(condition)
        if isinstance(node, ast.DictComp):
            self.expr(node.key)
            self.expr(node.value)
        else:
            self.expr(node.elt)
        self.leave(saved)

    # ---- Abschluss

    def finish(self) -> None:
        facts = self.f
        facts.comprehensions = self.comps
        if self.installs:
            for bind in facts.scopes[0].binds.get("_EXPORTS", ()):
                if isinstance(bind.value, Table):
                    facts.exports = _export_table(bind.value)
        reads: dict[str, list[tuple[str, int]]] = {}
        for number, scope in enumerate(facts.scopes):
            for name, line in scope.loads.items():
                if not scope.runtime:
                    if number == 0 or _free_global(facts.scopes, number, name):
                        facts.import_reads.setdefault(name, line)
                elif _free_global(facts.scopes, number, name):
                    reads.setdefault(name, []).append((scope.qualname, line))
        facts.global_reads = reads
        for scope in facts.scopes:
            scope.loads = {}
        self.grown()
        self.queries()
        if self.in_tests:
            self.helper_calls()

    def queries(self) -> None:
        """Behält die Aufrufe, die ``getattr``/``hasattr`` unter anderem Namen sein können: über
        einen Namen, den die Datei an einen von beiden bindet (``has = hasattr``, ``from
        builtins import hasattr as has``), oder als Attribut (``builtins.hasattr``). Welcher es
        ist, faltet der Index; ein Alias aus einem anderen Modul sieht der Auszug nicht."""
        aliases = {
            name
            for scope in self.f.scopes
            for name, binds in scope.binds.items()
            if any(query_alias(bind.value) for bind in binds)
        }
        for node, number, runtime, checking in self.maybe:
            func = node.func
            if isinstance(func, ast.Name) and func.id not in aliases:
                continue
            kind = "query-default" if len(node.args) >= 3 else "query"
            at = (node.lineno, node.col_offset)
            base, name, called = (
                to_ir(part, number, comps=self.comps, checking=checking)
                for part in (node.args[0], node.args[1], func)
            )
            self.f.refs.append(Ref(kind, number, *at, base, (), name, runtime, checking, called))

    def grown(self) -> None:
        """Hängt an jede Bindung eines Behälters, was der Code später hineinlegt.

        ``made = []`` und in einer Methode ``made.append(self)``: Ein Element von ``made`` ist
        dann ``self``, kein unbekannter Wert."""
        if not self.grows:
            return
        scopes = self.f.scopes
        where = {
            id(bind): (number, name, position)
            for number, scope in enumerate(scopes)
            for name, binds in scope.binds.items()
            for position, bind in enumerate(binds)
        }
        added: dict[tuple[int, str, int], list[tuple[str, IR]]] = {}
        for number, name, at, how, value in self.grows:
            for bind in lookup(scopes, number, name, at) or ():
                place = where.get(id(bind))
                if place is not None and _container(bind.value):
                    added.setdefault(place, []).append((how, value))
        for (number, name, position), items in added.items():
            bind = scopes[number].binds[name][position]
            grown = Grown(bind.value, tuple(items))
            scopes[number].binds[name][position] = bind._replace(value=grown)

    def helper_calls(self) -> None:
        """Behält die Aufrufe, deren Ziel ein Helfer dieser Datei oder aus ``tests`` ist —
        aus ihnen faltet der Index die Parameter des Helfers."""
        facts = self.f
        names = {qualname.rpartition(".")[2] for qualname in facts.functions}
        module_binds = facts.scopes[0].binds
        for node, number in self.pending:
            func = node.func
            head = func.id if isinstance(func, ast.Name) else _dotted(func) or ""
            root = head.partition(".")[0]
            local = isinstance(func, ast.Name) and head in names
            imported = any(
                isinstance(b.value, (FromRef, ModRef)) and b.value.module.startswith("tests")
                for b in module_binds.get(root, ())
            )
            if not (local or imported) or any(isinstance(a, ast.Starred) for a in node.args):
                continue
            comps = self.comps
            args = tuple(to_ir(a, number, comps=comps) for a in node.args)
            # ``**tabelle`` steht als Schlüsselwort ``**``; der Index faltet es in ``**kwargs``.
            keywords = tuple(
                (k.arg or "**", to_ir(k.value, number, comps=comps)) for k in node.keywords
            )
            facts.calls.append(Site(to_ir(func, number, comps=comps), args, keywords))


#: Methoden, die einen Behälter füllen; ``setdefault`` legt ein Paar ab, ``update`` öffnet.
_FILLS = frozenset({"append", "add", "insert", "extend", "appendleft", "setdefault", "update"})


def _text_is(node: ast.expr | None, text: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == text


def query_alias(value: IR) -> bool:
    """Ob eine Bindung ``getattr``/``hasattr`` unter anderem Namen sein kann."""
    queries = ("getattr", "hasattr")
    if isinstance(value, Use):
        return value.name in queries
    if isinstance(value, FromRef):
        return value.module == "builtins" and value.name in queries
    return isinstance(value, Attr) and value.attr in queries and isinstance(value.base, Use)


def _container(value: IR) -> bool:
    """Ob eine Bindung einen frischen Behälter hält: ein Literal oder ``list()`` und Co."""
    if isinstance(value, (Seq, Table, Comp, Grown)):
        return True
    return (
        isinstance(value, Call)
        and isinstance(value.func, Use)
        and value.func.name in ("list", "set", "dict", "deque")
        and not value.args
    )


def _free_global(scopes: list[Scope], number: int, name: str) -> bool:
    """Ob ``name`` im Bereich ``number`` als Global des Moduls gelesen wird."""
    scope = scopes[number]
    if name in scope.globals:
        return True
    if number == 0 or name in scope.binds:
        return False
    outer = scope.parent
    while outer > 0:
        enclosing = scopes[outer]
        if enclosing.kind != "class" and name in enclosing.binds:
            return name in enclosing.globals
        outer = enclosing.parent
    return True


def inside(span: tuple[int, int, int, int] | None, at: tuple[int, int]) -> bool:
    """Ob die Stelle ``at`` in der Lage ``span`` liegt."""
    if span is None:
        return False
    return (span[0], span[1]) <= at <= (span[2], span[3])


def live(binds: list[Bind] | None, stub: bool = False, checking: bool = False) -> list[Bind]:
    """Die Bindungen, die zur Laufzeit gelten; in einem Stub zählt auch die Annotation."""
    if not binds:
        return []
    mask = 0 if checking else CHECKING if stub else CHECKING | ANNOTATED
    return [b for b in binds if not b.flags & mask]


def effective(binds: list[Bind] | None, stub: bool = False, checking: bool = False) -> list[Bind]:
    """Modulzustand nach dem Import plus mögliche spätere globale Schreiber."""
    candidates = live(binds, stub, checking)
    found = [bind for bind in candidates if bind.flags & RUNTIME]
    for bind in reversed(candidates):
        if bind.flags & RUNTIME:
            continue
        if not bind.flags & DELETED:
            found.append(bind)
        if not bind.flags & COND:
            break
    return found


def _values(binds: list[Bind] | None, checking: bool = False) -> list[Bind] | None:
    found = effective(binds, checking=checking)
    return found or None


_WITHOUT_VALUE = Bind(0, 0, Unknown("ohne Wert gebunden"), 0)


def lookup(
    scopes: list[Scope], number: int, name: str, at: tuple[int, int], checking: bool = False
) -> list[Bind] | None:
    """Die Werte, die ``name`` an der Stelle ``at`` im Bereich ``number`` haben kann.

    Im eigenen Bereich die letzte Bindung vor ``at`` samt den bedingten davor bis zur ersten
    unbedingten, dazu die späteren derselben Schleife (nächster Durchlauf); liegt keine davor,
    alle. Aus einem umschließenden Bereich alle —
    zur Aufrufzeit hat jede gelaufen sein können. Klassenbereiche sieht ein inneres ``def``
    nicht. Welche davon aus einem Geschwisterzweig stammen, entscheidet der Index über
    ``Bind.branch``. ``None`` heißt: nirgends gebunden, also eingebaut oder unbekannt.
    """
    scope = scopes[number]
    if number and name in scope.globals:
        return _values(scopes[0].binds.get(name), checking)
    binds = scope.binds.get(name)
    if binds is not None:
        found = live(binds, checking=checking)
        if not found:
            return [_WITHOUT_VALUE]
        if len(found) == 1 and not scope.loops:
            # Der häufigste Fall: eine Bindung, keine Schleife — sie gilt, davor oder nicht.
            return found
        before = sorted((b for b in found if (b.line, b.col) <= at), key=lambda b: (b.line, b.col))
        if not before:
            return found
        picked: list[Bind] = []
        for bind in reversed(before):
            picked.append(bind)
            if not bind.flags & COND:
                break
        picked.extend(
            bind
            for bind in found
            if (bind.line, bind.col) > at
            and any(
                inside(loop, at) and inside(loop, (bind.line, bind.col)) for loop in scope.loops
            )
        )
        return picked
    outer = scope.parent
    while outer > 0:
        enclosing = scopes[outer]
        if enclosing.kind != "class" and name in enclosing.binds:
            if name in enclosing.globals:
                break
            # Eine äußere Funktion ist beim Aufruf des inneren Helfers noch nicht
            # zwingend an ihrer letzten Zuweisung angekommen. Ohne konkreten
            # Aufrufbeweis bleiben alle erreichbaren Closure-Bindungen erhalten.
            return live(enclosing.binds[name], checking=checking) or [_WITHOUT_VALUE]
        outer = enclosing.parent
    if number:
        return _values(scopes[0].binds.get(name), checking)
    return None


def module_name(path: str) -> tuple[str, bool]:
    """Punktname und Paketeigenschaft einer Datei aus ihrem relativen Pfad."""
    parts = path.rsplit(".", 1)[0].split("/")
    if parts[-1] == "__init__":
        return ".".join(parts[:-1]), True
    return ".".join(parts), False


def extract(path: str, source: bytes) -> Facts:
    """Der Auszug einer Datei; ``path`` ist relativ zur Wurzel, mit ``/``."""
    tree = ast.parse(source, filename=path)
    module, package = module_name(path)
    area = path.partition("/")[0]
    facts = Facts(path, module, area, package, path.endswith(".pyi"), source.count(b"\n"))
    _Extractor(facts).run(tree)
    return facts


def extract_script(path: str, text: str) -> Facts | None:
    """Der Auszug eines Skripts aus einer Zeichenkette (CS-18), oder ``None``, wenn der Text
    kein Python ist. ``path`` ist ein eigener Schlüssel; als ``-c`` gestartet heißt das Modul
    ``__main__``, und es liegt in keinem Bereich: Es liest keinen Namen zur Aufrufzeit eines
    Moduls aus ``app/`` oder ``tools/`` und hat keine Patch-Stellen."""
    try:
        tree = ast.parse(text, filename=path)
    except SyntaxError, ValueError:
        return None
    facts = Facts(path, "__main__", "script", False, False, text.count("\n"))
    _Extractor(facts).run(tree)
    return facts


def source_files(root: Path) -> list[tuple[str, Path]]:
    """Alle ``*.py`` und ``*.pyi`` unter den Bereichen, sortiert, ohne ``__pycache__`` und
    Punktordner. Gelesen wird das Dateisystem, nicht Git: So geht dasselbe an einer Attrappe,
    und eine neue, noch nicht vorgemerkte Datei zählt mit."""
    found: list[tuple[str, Path]] = []
    for area in AREAS:
        base = root / area
        if not base.is_dir():
            continue
        for full in base.rglob("*.py*"):
            relative = full.relative_to(root)
            folders = relative.parts[:-1]
            if full.suffix not in (".py", ".pyi") or any(
                part == "__pycache__" or part.startswith(".") for part in folders
            ):
                continue
            found.append((relative.as_posix(), full))
    # ``x.py`` vor ``x.pyi``: Der Index nimmt den Stub nur, wo es kein Python gibt.
    return sorted(found)


# ---------------------------------------------------------------------- Zwischenspeicher


#: Die Quelle, wie dieser Prozess sie geladen hat; ``tools.code_store`` bildet daraus den Stand
#: des Auflösers, nicht aus der Platte (RR2-1).
_SOURCE = Path(__file__).read_bytes()

#: Der Stand beim Import, nicht beim Bau: Ein Prozess, der den alten Code geladen hat, während
#: die Datei schon neu ist, schrieb sonst alte Auszüge unter dem neuen Stand (gemessen: ein
#: Lauf ohne ``import_reads`` unter dem Stand mit).
_STAMP = hashlib.sha256(
    _SOURCE + Path(__file__).with_name("code_cache.py").read_bytes()
).hexdigest()


def stamp() -> str:
    """Der Stand dieses Moduls: Ändert sich der Auszug, ist jeder alte ungültig."""
    return _STAMP


def load_cache(
    path: Path, current: str, wanted: dict[str, str] | None = None
) -> dict[str, tuple[str, Facts]]:
    """Die gespeicherten Auszüge je Pfad mit ihrem Inhaltshash; leer bei anderem Stand. Mit
    ``wanted`` (Pfad → Hash) nur die Auszüge, deren Inhalt noch so aussieht."""
    from tools.code_cache import decode

    return decode(path, current, wanted)


def save_cache(path: Path, current: str, files: dict[str, tuple[str, Facts]]) -> None:
    """Schreibt über eine eigene Zwischendatei und ersetzt dann; ein zweiter Prozess liest so nie
    eine halbe Datei. Hält ein anderer die Datei gerade offen, bleibt dessen Stand — seine
    Einträge sind nach Inhaltshash ebenso gültig, fehlende zieht der nächste Bau nach."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    from tools.code_cache import encode

    data = encode(current, files)
    temporary.write_bytes(data)
    for _attempt in range(20):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            time.sleep(0.05)
    temporary.unlink()
