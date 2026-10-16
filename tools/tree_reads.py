"""Wer welchen Ordner des Baums liest — statisch, ohne Import (Codestruktur Schritt 0, W4 und E5).

Zwei Prüfungen fragen dasselbe:

- **W4** (``tests/test_source_readers.py``): Liest ein ``glob`` auf Python-Quellen flach über
  ein Paket? Dafür der Ordner jedes solchen Globs (:func:`flat_globs`).
- **Die Auswahl** (``tools/affected_tests.py``, über sie auch ``tools/ci_selection.py``):
  Welche Testdateien lesen den Ordner, in dem eine Änderung liegt? Dafür jede Lesestelle mit
  Ordner und Muster (:class:`Read`) — in der Testdatei selbst oder in einer Definition, die sie
  aus einem anderen Modul bezieht (:class:`TreeReads`).

**Lesestellen** sind ``glob``, ``rglob``, ``iterdir`` und ``walk`` eines Pfads, die Funktionen
``glob.glob``/``iglob``, ``os.walk``/``listdir``/``scandir``, ``pkgutil.walk_packages``/
``iter_modules`` und ``shutil.copytree`` — auch umbenannt (``from glob import glob as find``) —
und ein Aufruf mit der Befehlsliste ``["git", "ls-files", …]``. ``ast.walk`` ist keine: Ein
Empfänger, der ein fremdes Modul ist, liest keinen Ordner. Ein Modul, das ein Test über
``spec_from_file_location`` lädt, ist das Modul des Baums.

**Aufgelöst wird statisch**, wie Python einen Namen sucht: Funktion, umgebende Funktionen,
Modul, eingebaut; ein Klassenrumpf nur für Code direkt darin. Gefaltet werden
``Path(__file__)``-Ketten, ``.parent``, ``.parents[n]``, ``resolve()``, ``joinpath``, ``/``,
``Path(M.__file__)``, ``M.__path__``, Konstanten und Importe eigener Module, auch relativ,
Muster aus Konstanten, Tupel samt ``*``-Elementen, Schleifen über Tupel und über das, was eine
Lesestelle liefert (:class:`Choice`), ``or`` und der Rückgabewert einer eigenen Funktion mit
den Werten ihrer Argumente. Mehr als eine Bindung, ein Parameter ohne Wert oder ein
Arbeitsordner heißt „nicht auflösbar“ (``None``); ein Teil einer Wahl, der sich nicht
auflösen lässt, bleibt als offene Möglichkeit darin und fällt nie still weg.

**Draußen** (:class:`Outside`) liegt, was die Fixtures ``tmp_path``, ``tmpdir`` und
``tmp_path_factory`` liefern, was ``tempfile``, ``Path.home()`` und ``platformdirs`` nennen und
was aus einer Umgebungsvariablen kommt — samt allem, was daraus abgeleitet ist. Eine
Umgebungsvariable nennt im Bestand nie einen Ordner des Baums, nur Programme, Systemordner,
Nutzerordner und Marken eines Kindprozesses.

**Parameter bekommen ihren Wert an der Aufrufstelle.** ``source_tree.python_files("app/ui")``
liest ``app/ui``, weil der Wert des Arguments in den Empfänger ``ROOT / folder`` des Helfers
eingesetzt wird — über beliebig viele Glieder (``definition_file`` → ``python_files``) und mit
den Vorgaben der Signatur. Bezogen wird nur, was eine Datei nennt: Wer aus einem Modul einen
Körper leiht, der nichts liest, liest durch den Import nichts.

**Abgrenzung zu ``tools/code_index.py``.** Der Index faltet weiter (Tabellen, Aufrufstellen
von Testhelfern, Bedingungen), erhebt dafür aber jede Datei unter ``app/``, ``tools/`` und
``tests/``: gemessen 46 s kalt und 38 s warm, davon 26 s das Laden seines Zwischenspeichers,
gegen 20 s für den ganzen Importgraphen der Auswahl, die je Schritt und vor jedem Push in der
CI läuft. Dieser Auflöser liest und parst jede Datei einmal, gemeinsam mit dem Importgraphen,
und faltet nur Ordnerausdrücke. Was er nicht auflöst, ist ``None`` und liest in der Auswahl
jeden Ordner; ein Muster, das er nicht auflöst, liest jede Tiefe (:data:`OPEN_PATTERN`) —
ein Test zu viel, nie einer zu wenig. Ein offener Teil eines f-Strings innerhalb eines
Namens (``f"{name}*.py"``) steht für einen Namen ohne ``/``: So stehen alle im Bestand.
"""

from __future__ import annotations

import ast
import builtins
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any

# --------------------------------------------------------------------------- Werte


@dataclass(frozen=True)
class Module:
    """Ein Modul oder Paket unter der Wurzel, als Punktname."""

    name: str


@dataclass(frozen=True)
class Foreign:
    """Ein Modul oder ein Name daraus, der nicht im Baum liegt: ``ast``, ``os.walk``."""

    name: str


@dataclass(frozen=True)
class Place:
    """Ein Ort relativ zur Wurzel; ``()`` ist die Wurzel selbst. Ein Teil darf ein Muster sein
    (``app/*``), wenn der Ort aus einer Schleife über eine Lesestelle stammt."""

    parts: tuple[str, ...]

    @property
    def text(self) -> str:
        return "/".join(self.parts)


@dataclass(frozen=True)
class Outside:
    """Ein Ordner außerhalb des Repositorys: Temp-Ordner, Nutzerordner, Umgebung."""

    reason: str


@dataclass(frozen=True)
class Definition:
    """Eine Definition im Baum: Funktion, Methode, Klasse oder Zuweisung auf Modulebene."""

    relative: str
    node: ast.AST


@dataclass(frozen=True)
class Choice:
    """Einer von mehreren Werten: die Elemente eines Tupels, die Durchläufe einer Schleife,
    die Seiten eines ``or``, die Rückgaben einer Funktion."""

    values: tuple[Value, ...]


Value = Module | Foreign | Place | Outside | Definition | Choice | str | None

#: Werte der Parameter: ``(id(funktionsknoten), name)`` → Wert.
Env = Mapping[tuple[int, str], Value]

#: Eine Bindung: Art und was sie trägt (Wert und Anweisung, Import, Parameter, Definition).
_Binding = tuple[str, Any]

#: Konstruktoren, deren Argumente ein Pfad sind.
_PATH_TYPES = frozenset(
    f"pathlib.{name}"
    for name in ("Path", "PurePath", "PosixPath", "WindowsPath", "PurePosixPath", "PureWindowsPath")
)

#: Pfadmethoden, die denselben Ort liefern.
_SAME_PLACE = frozenset({"resolve", "absolute", "expanduser"})

#: Fixtures von pytest, deren Wert ein frischer Ordner außerhalb des Baums ist.
_TEMP_FIXTURES = frozenset({"tmp_path", "tmpdir", "tmp_path_factory", "tmpdir_factory"})

#: Aufrufe, die einen Ordner außerhalb des Baums liefern.
_OUTSIDE_CALLS = frozenset(
    {
        "tempfile.mkdtemp",
        "tempfile.gettempdir",
        "tempfile.TemporaryDirectory",
        "pathlib.Path.home",
        "os.path.expanduser",
        "os.environ.get",
        "os.getenv",
    }
)
_OUTSIDE_MODULES = ("platformdirs.", "PySide6.QtCore.QStandardPaths.")

#: Aufrufe, deren Ergebnis der Pfad ihres einzigen Arguments ist.
_SAME_ARGUMENT = frozenset(
    {
        "builtins.str",
        "os.fspath",
        "os.fsdecode",
        "os.path.abspath",
        "os.path.realpath",
        "os.path.normpath",
    }
)

#: Hüllen, deren Elemente die ihres Arguments sind.
_SAME_ELEMENTS = frozenset(
    f"builtins.{name}"
    for name in ("sorted", "list", "tuple", "set", "frozenset", "reversed", "iter")
)

_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_SCOPES = (*_FUNCTIONS, ast.Lambda, *_COMPREHENSIONS)

#: Die Ordner, deren Module ein Punktname erreicht — dieselben, deren Importgraph
#: ``affected_tests`` liest. ``app`` und ``tools`` reisen als Module, ``tests`` sind die Blätter.
PACKAGES = ("app", "tools", "tests")

#: So tief folgt die Auflösung Rückgabewerten in andere Funktionen.
_DEPTH = 12

_WILDCARD = re.compile(r"[*?\[]")

#: Ein Muster, das sich nicht auflösen lässt (aus Daten, einem Parameter ohne Wert): jede Datei
#: in jeder Tiefe — es kann ``**`` tragen, und die Auswahl nimmt nie einen Test zu wenig (F-4).
OPEN_PATTERN = "**/*"


def _argument(call: ast.Call, position: int, keyword: str) -> ast.expr | None:
    """Das Argument an ``position`` oder unter dem Namen ``keyword``."""
    if len(call.args) > position and not isinstance(call.args[position], ast.Starred):
        return call.args[position]
    return next((one.value for one in call.keywords if one.arg == keyword), None)


def _target_names(target: ast.AST) -> Iterator[str]:
    """Die Namen, die ein Zuweisungsziel bindet. ``x[k] = …`` und ``x.a = …`` binden keinen:
    ``alias[ast.unparse(e)] = …`` lässt ``ast`` unberührt."""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, ast.Tuple | ast.List):
        for item in target.elts:
            yield from _target_names(item)
    elif isinstance(target, ast.Starred):
        yield from _target_names(target.value)


def _flat_names(target: ast.AST) -> list[str]:
    """Die Namen eines flachen Tupelziels ``a, b``; sonst nichts."""
    if isinstance(target, ast.Tuple | ast.List) and all(
        isinstance(one, ast.Name) for one in target.elts
    ):
        return [one.id for one in target.elts]  # type: ignore[attr-defined]
    return []


#: Die Felder, in denen Anweisungen stehen — in Anweisungen, ``except`` und ``case``.
_BODIES = ("body", "orelse", "finalbody", "handlers", "cases")


def statements(tree: ast.AST) -> Iterator[ast.stmt]:
    """Jede Anweisung im Baum, auch in Funktionen, Klassen und Blöcken — ohne einen Gang über
    die Ausdrücke, die den größten Teil eines Baums ausmachen; in keinem Ausdruck steht eine
    Anweisung."""
    stack: list[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, ast.stmt):
            yield node
        for name in _BODIES:
            stack.extend(getattr(node, name, ()))


def joined(place: Place, text: str) -> Place | None:
    """``place / text``; ``..`` über die Wurzel hinaus ist nicht auflösbar."""
    parts = list(place.parts)
    for part in PurePosixPath(text.replace("\\", "/")).parts:
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part not in ("", ".", "/"):
            parts.append(part)
    return Place(tuple(parts))


def choice(values: Iterable[Value]) -> Value:
    """Ein Wert aus mehreren: verschachtelte Wahlen flach, Doppelte einmal, einer allein er
    selbst."""
    flat: list[Value] = []
    for value in values:
        for one in value.values if isinstance(value, Choice) else (value,):
            if one not in flat:
                flat.append(one)
    if not flat:
        return None
    return flat[0] if len(flat) == 1 else Choice(tuple(flat))


def each(value: Value, function: Callable[[Value], Value]) -> Value:
    """``function`` auf jede Möglichkeit von ``value``."""
    if isinstance(value, Choice):
        return choice(function(one) for one in value.values)
    return function(value)


def options(value: Value) -> tuple[Value, ...]:
    """Die Möglichkeiten eines Werts."""
    return value.values if isinstance(value, Choice) else (value,)


# --------------------------------------------------------------------------- Auflöser


class Resolver:
    """Löst Ausdrücke einer Datei unter ``root`` statisch auf; liest und parst jede Datei
    höchstens einmal — auch für den Importgraphen der Auswahl, der über ihn liest (F-6)."""

    def __init__(self, root: Path, *, working_root: bool = False) -> None:
        self.root = root
        #: Ob ein relativer Pfad relativ zur Wurzel gilt. Für die Auswahl ja: Die Suite läuft
        #: dort (``suite-getrennt.sh``, CI, ``affected_tests --run``). W4 nicht: Dort ist ein
        #: Glob über den Arbeitsordner selbst der Fund.
        self.working_root = working_root
        self._texts: dict[str, str] = {}
        self._trees: dict[str, ast.Module] = {}
        self._parents: dict[str, dict[ast.AST, ast.AST]] = {}
        self._bindings: dict[ast.AST, dict[str, list[_Binding]]] = {}
        self._busy: set[tuple[int, str]] = set()
        self._exists: dict[str, bool] = {}
        self._paths: dict[str, Path | None] = {}
        self._returns: dict[tuple[ast.AST, bool], list[ast.expr]] = {}
        self._calls: list[int] = []

    # Module -----------------------------------------------------------------------

    def module_path(self, name: str) -> Path | None:
        if name not in self._paths:
            base = self.root.joinpath(*name.split("."))
            found = None
            if (base / "__init__.py").is_file():
                found = base / "__init__.py"
            elif base.with_suffix(".py").is_file():
                found = base.with_suffix(".py")
            self._paths[name] = found
        return self._paths[name]

    def module_exists(self, name: str) -> bool:
        """Ob es ``name`` unter ``app``, ``tools`` oder ``tests`` gibt, als Modul oder Ordner."""
        if not name or name.split(".", 1)[0] not in PACKAGES:
            return False
        if name not in self._exists:
            self._exists[name] = (
                self.module_path(name) is not None or self.root.joinpath(*name.split(".")).is_dir()
            )
        return self._exists[name]

    def text(self, relative: str) -> str:
        """Der Text einer Datei, einmal gelesen; eine, die sich nicht lesen lässt, ist leer."""
        if relative not in self._texts:
            try:
                self._texts[relative] = (self.root / relative).read_text(encoding="utf-8")
            except OSError, ValueError:
                self._texts[relative] = ""
        return self._texts[relative]

    def tree(self, relative: str) -> ast.Module:
        """Der Syntaxbaum, einmal geparst; eine Datei mit Syntaxfehler (fremder Zwischenstand im
        geteilten Baum) zählt als leer."""
        if relative not in self._trees:
            try:
                self._trees[relative] = ast.parse(self.text(relative), filename=relative)
            except SyntaxError, ValueError:
                self._trees[relative] = ast.Module(body=[], type_ignores=[])
        return self._trees[relative]

    def parsed(self, relative: str) -> tuple[ast.Module, dict[ast.AST, ast.AST]]:
        """Syntaxbaum und Eltern; die Eltern erst, wenn eine Frage sie braucht — der
        Importgraph braucht nur den Baum."""
        tree = self.tree(relative)
        if relative not in self._parents:
            parents: dict[ast.AST, ast.AST] = {}
            stack: list[ast.AST] = [tree]
            while stack:
                node = stack.pop()
                for child in ast.iter_child_nodes(node):
                    parents[child] = node
                    stack.append(child)
            self._parents[relative] = parents
        return tree, self._parents[relative]

    @staticmethod
    def module_name(relative: str) -> str:
        parts = list(PurePosixPath(relative).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    # Bereiche ---------------------------------------------------------------------

    def scopes(self, node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> list[ast.AST]:
        """Die Bereiche, in denen ein Name an ``node`` gesucht wird, innen zuerst."""
        found: list[ast.AST] = []
        current = parents.get(node)
        in_function = False
        while current is not None:
            if isinstance(current, _SCOPES):
                found.append(current)
                in_function = in_function or not isinstance(current, _COMPREHENSIONS)
            elif isinstance(current, ast.Module) or (
                isinstance(current, ast.ClassDef) and not in_function
            ):
                found.append(current)
            current = parents.get(current)
        return found

    def bindings(self, scope: ast.AST) -> dict[str, list[_Binding]]:
        """Jeder Name, den ``scope`` bindet, mit der Art jeder Bindung."""
        if scope in self._bindings:
            return self._bindings[scope]
        found: dict[str, list[_Binding]] = defaultdict(list)
        if isinstance(scope, (*_FUNCTIONS, ast.Lambda)):
            arguments = scope.args
            for argument in (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
                *(one for one in (arguments.vararg, arguments.kwarg) if one is not None),
            ):
                found[argument.arg].append(("param", (scope, argument.arg)))
        if isinstance(scope, _COMPREHENSIONS):
            for generator in scope.generators:
                if isinstance(generator.target, ast.Name):
                    found[generator.target.id].append(("for", generator.iter))
                elif _flat_names(generator.target):
                    for index, name in enumerate(_flat_names(generator.target)):
                        found[name].append(("row", (generator.iter, index)))
                else:
                    for name in _target_names(generator.target):
                        found[name].append(("unknown", None))
            self._bindings[scope] = found
            return found
        body = [scope.body] if isinstance(scope, ast.Lambda) else list(scope.body)  # type: ignore[attr-defined]
        for statement in body:
            self._bind(statement, found)
        self._bindings[scope] = found
        return found

    def _bind(self, node: ast.AST, found: dict[str, list[_Binding]]) -> None:
        if isinstance(node, (*_FUNCTIONS, ast.ClassDef)):
            found[node.name].append(("def", node))
            return
        if isinstance(node, _SCOPES):
            return
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id].append(("value", (node.value, node)))
                else:
                    for name in _target_names(target):
                        found[name].append(("unknown", None))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found[node.target.id].append(
                ("value", (node.value, node)) if node.value else ("unknown", None)
            )
        elif isinstance(node, ast.For | ast.AsyncFor) and isinstance(node.target, ast.Name):
            found[node.target.id].append(("for", node.iter))
        elif isinstance(node, ast.For | ast.AsyncFor) and _flat_names(node.target):
            for index, name in enumerate(_flat_names(node.target)):
                found[name].append(("row", (node.iter, index)))
        elif isinstance(node, ast.AugAssign | ast.For | ast.AsyncFor):
            for name in _target_names(node.target):
                found[name].append(("unknown", None))
        elif isinstance(node, ast.NamedExpr):
            found[node.target.id].append(("unknown", None))
        elif isinstance(node, ast.With | ast.AsyncWith):
            for item in node.items:
                if isinstance(item.optional_vars, ast.Name):
                    found[item.optional_vars.id].append(("with", item.context_expr))
                elif item.optional_vars is not None:
                    for name in _target_names(item.optional_vars):
                        found[name].append(("unknown", None))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            found[node.name].append(("unknown", None))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    kind = "module" if self.module_exists(alias.name) else "foreign"
                    found[alias.asname].append((kind, alias.name))
                else:
                    head = alias.name.split(".")[0]
                    kind = "module" if self.module_exists(head) else "foreign"
                    found[head].append((kind, head))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                found[alias.asname or alias.name].append(("from", (node, alias.name)))
        for child in ast.iter_child_nodes(node):
            self._bind(child, found)

    def binding(self, name: str, scopes: list[ast.AST]) -> tuple[int, _Binding] | None:
        """Die eine Bindung von ``name`` mit dem Index ihres Bereichs; mehrere verschiedene oder
        keine: ``None``. Derselbe Import zweimal ist eine Bindung."""
        for index, scope in enumerate(scopes):
            entries = self.bindings(scope).get(name)
            if not entries:
                continue
            first = entries[0]
            if len(entries) == 1 or (
                first[0] in ("module", "foreign") and all(one == first for one in entries)
            ):
                return index, first
            return None
        return None

    def foreign(self, node: ast.expr, scopes: list[ast.AST], relative: str) -> Foreign | None:
        """Ein Name oder eine Kette, die auf ein fremdes Modul zeigt — ohne ein eigenes Modul zu
        lesen: ``os``, ``glob.glob``, ``find`` nach ``from glob import glob as find``."""
        if isinstance(node, ast.Attribute):
            base = self.foreign(node.value, scopes, relative)
            return Foreign(f"{base.name}.{node.attr}") if base is not None else None
        if not isinstance(node, ast.Name):
            return None
        found = self.binding(node.id, scopes)
        if found is None:
            return None
        kind, data = found[1]
        if kind == "foreign":
            return Foreign(str(data))
        if kind == "from":
            statement, imported = data
            source = self.source_module(statement, relative)
            if not statement.level and not self.module_exists(source):
                return Foreign(f"{source}.{imported}")
        return None

    # Werte ------------------------------------------------------------------------

    def lookup(self, name: str, scopes: list[ast.AST], relative: str, env: Env | None) -> Value:
        found = self.binding(name, scopes)
        if found is None:
            if any(self.bindings(scope).get(name) for scope in scopes):
                return None  # mehrfach gebunden
            if name == "__file__":
                return Place(PurePosixPath(relative).parts)
            return Foreign(f"builtins.{name}") if hasattr(builtins, name) else None
        index, (kind, data) = found
        if kind == "row":
            iterable, position = data
            return self.column(iterable, position, scopes[index:], relative, env)
        if kind in ("value", "for", "with"):
            expression = data[0] if kind == "value" else data
            if expression is None:
                return None
            key = (id(expression), relative)
            if key in self._busy:
                return None
            self._busy.add(key)
            try:
                inner = scopes[index:]
                if kind == "for":
                    return self.elements(expression, inner, relative, env)
                value = self.evaluate(expression, inner, relative, env)
                if kind == "with":
                    return value if isinstance(value, Outside) else None
                return value
            finally:
                self._busy.discard(key)
        if kind == "module":
            return Module(str(data))
        if kind == "foreign":
            return Foreign(str(data))
        if kind == "from":
            statement, imported = data
            return self.imported(statement, imported, relative)
        if kind == "def":
            return Definition(relative, data)
        if kind == "param":
            function, parameter = data
            if env is not None and (id(function), parameter) in env:
                return env[(id(function), parameter)]
            if parameter in _TEMP_FIXTURES:
                return Outside("pytest")
            takes_fixtures = isinstance(function, _FUNCTIONS) and (
                function.name.startswith("test")
                or any(is_fixture(one) for one in function.decorator_list)
            )
            fixture = self.fixture(parameter, relative) if takes_fixtures else None
            return self.produced(fixture) if fixture is not None else None
        return None

    def fixture(self, name: str, relative: str) -> Definition | None:
        """Die Fixture ``name``, die ein Test unter ``tests/`` als Parameter bekommt: aus seiner
        Datei oder aus ``tests/conftest.py``."""
        if not relative.startswith("tests/"):
            return None
        for place in (relative, "tests/conftest.py"):
            if not (self.root / place).is_file():
                continue
            tree = self.tree(place)
            for statement in tree.body:
                if (
                    isinstance(statement, _FUNCTIONS)
                    and statement.name == name
                    and any(is_fixture(one) for one in statement.decorator_list)
                ):
                    return Definition(place, statement)
        return None

    def produced(self, fixture: Definition) -> Value:
        """Was eine Fixture liefert: ihre ``return``- und ``yield``-Werte, ihre Parameter
        wieder als Fixtures."""
        node = fixture.node
        if id(node) in self._calls or len(self._calls) > _DEPTH:
            return None
        self._calls.append(id(node))
        try:
            _tree, parents = self.parsed(fixture.relative)
            values = [
                self.evaluate(one, self.scopes(one, parents), fixture.relative, None)
                for one in self._returns_of(node, yields=True)
            ]
        finally:
            self._calls.pop()
        return choice(values) if values else None

    def source_module(self, statement: ast.ImportFrom, relative: str) -> str:
        """Das Modul, aus dem ``statement`` importiert, auch relativ."""
        if not statement.level:
            return statement.module or ""
        package = self.module_name(relative).split(".")
        if not relative.endswith("__init__.py"):
            package = package[:-1]
        package = package[: len(package) - (statement.level - 1)]
        return ".".join([*package, statement.module] if statement.module else package)

    def imported(self, statement: ast.ImportFrom, name: str, relative: str) -> Value:
        source = self.source_module(statement, relative)
        if self.module_exists(source):
            return self.attribute(Module(source), name)
        return None if statement.level else Foreign(f"{source}.{name}")

    def attribute(self, module: Module, name: str) -> Value:
        """``module.name``: Bindung auf Modulebene, Untermodul, ``__file__`` oder ``__path__``."""
        path = self.module_path(module.name)
        if path is not None:
            relative = path.relative_to(self.root).as_posix()
            tree = self.tree(relative)
            if name in self.bindings(tree):
                return self.lookup(name, [tree], relative, None)
        inner = f"{module.name}.{name}"
        if self.module_exists(inner):
            return Module(inner)
        if name == "__file__" and path is not None:
            return Place(path.relative_to(self.root).parts)
        if name == "__path__" and path is not None and path.name == "__init__.py":
            return Place(path.parent.relative_to(self.root).parts)
        if name == "__path__" and path is None and self.module_exists(module.name):
            # Ein Namensraum-Paket wie ``tools`` hat keinen Initialisierer, aber seinen Ordner.
            return Place(tuple(module.name.split(".")))
        return None

    def member(self, owner: Definition, name: str) -> Definition | None:
        """Eine Methode einer Klasse im Baum."""
        if isinstance(owner.node, ast.ClassDef):
            for statement in owner.node.body:
                if isinstance(statement, _FUNCTIONS) and statement.name == name:
                    return Definition(owner.relative, statement)
        return None

    def definition(self, relative: str, node: ast.expr) -> Definition | None:
        """Die Definition, die ein Name oder eine Kette nennt — Funktion, Klasse, Methode oder
        die Zuweisung, die ihn bindet; über Importe bis in das Modul, das sie trägt."""
        _tree, parents = self.parsed(relative)
        if isinstance(node, ast.Name):
            return self._defined(self.binding(node.id, self.scopes(node, parents)), relative, 0)
        if isinstance(node, ast.Attribute):
            base = self.value_at(relative, node.value)
            if isinstance(base, Module):
                return self.module_definition(base.name, node.attr, 0)
            if isinstance(base, Definition):
                return self.member(base, node.attr)
        return None

    def module_definition(self, module: str, name: str, depth: int) -> Definition | None:
        """Die Definition von ``module.name`` auf Modulebene."""
        path = self.module_path(module)
        if path is None or depth > 8:
            return None
        relative = path.relative_to(self.root).as_posix()
        tree = self.tree(relative)
        entries = self.bindings(tree).get(name)
        if not entries or len(entries) != 1:
            return None
        return self._defined((0, entries[0]), relative, depth + 1)

    def _defined(
        self, found: tuple[int, _Binding] | None, relative: str, depth: int
    ) -> Definition | None:
        if found is None:
            return None
        kind, data = found[1]
        if kind == "def":
            return Definition(relative, data)
        if kind == "value":
            _value, statement = data
            return Definition(relative, statement)
        if kind == "from":
            statement, imported = data
            source = self.source_module(statement, relative)
            if self.module_exists(source):
                return self.module_definition(source, imported, depth)
        return None

    def evaluate(
        self, node: ast.expr, scopes: list[ast.AST], relative: str, env: Env | None = None
    ) -> Value:
        """Was ``node`` statisch bedeutet; ``None``, wo es sich nicht eindeutig sagen lässt."""
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        if isinstance(node, ast.JoinedStr):
            texts = [str(part.value) for part in node.values if isinstance(part, ast.Constant)]
            return "".join(texts) if len(texts) == len(node.values) else None
        if isinstance(node, ast.Name):
            return self.lookup(node.id, scopes, relative, env)
        if isinstance(node, ast.Attribute):
            return each(
                self.evaluate(node.value, scopes, relative, env),
                lambda one: self._attribute_of(one, node.attr),
            )
        if isinstance(node, ast.Call):
            return self._call(node, scopes, relative, env)
        if isinstance(node, ast.Tuple | ast.List | ast.Set):
            # Ein ``*``-Element trägt die Elemente seines Werts bei
            # (``(*asset_rights.APPLICATION_ROOTS, WEBSITE_ROOT)``); lässt es sich nicht
            # auflösen, bleibt eine offene Möglichkeit — nie fällt ein Teil still weg (F-1).
            return choice(
                self.elements(item.value, scopes, relative, env)
                if isinstance(item, ast.Starred)
                else self.evaluate(item, scopes, relative, env)
                for item in node.elts
            )
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            return choice(self.evaluate(item, scopes, relative, env) for item in node.values)
        if isinstance(node, ast.BinOp):
            left = self.evaluate(node.left, scopes, relative, env)
            right = self.evaluate(node.right, scopes, relative, env)
            return each(left, lambda one: each(right, lambda two: _binary(node.op, one, two)))
        if isinstance(node, ast.Subscript):
            base = self.evaluate(node.value, scopes, relative, env)
            if base == Foreign("os.environ"):
                return Outside("Umgebung")
            if (
                isinstance(node.value, ast.Attribute)
                and node.value.attr == "parents"
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, int)
            ):
                depth = node.slice.value + 1
                return each(
                    self.evaluate(node.value.value, scopes, relative, env),
                    lambda one: _ancestor(one, depth),
                )
            return None
        if isinstance(node, ast.IfExp):
            return choice(
                (
                    self.evaluate(node.body, scopes, relative, env),
                    self.evaluate(node.orelse, scopes, relative, env),
                )
            )
        return None

    def elements(
        self, node: ast.expr, scopes: list[ast.AST], relative: str, env: Env | None
    ) -> Value:
        """Was eine Schleife über ``node`` je Durchlauf bindet: die Elemente eines Tupels oder
        die Pfade, die eine Lesestelle liefert (``app/*`` aus ``APP.iterdir()``)."""
        while isinstance(node, ast.Call) and node.args:
            called = self.foreign(node.func, scopes, relative)
            if called is None or called.name not in _SAME_ELEMENTS:
                break
            node = node.args[0]
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("glob", "rglob", "iterdir")
        ):
            base = self.evaluate(node.func.value, scopes, relative, env)
            text = "*"
            if node.func.attr != "iterdir":
                argument = _argument(node, 0, "pattern")
                found = (
                    None
                    if argument is None
                    else self.pattern(argument, scopes, relative, env, deep=True)
                )
                text = found if isinstance(found, str) else OPEN_PATTERN
            parts = _pattern_parts(text, node.func.attr == "rglob")

            def found_paths(one: Value) -> Value:
                if isinstance(one, Outside):
                    return one
                return Place((*one.parts, *parts)) if isinstance(one, Place) else None

            return each(base, found_paths)
        value = self.evaluate(node, scopes, relative, env)
        if isinstance(node, ast.Tuple | ast.List | ast.Set) or isinstance(value, Choice):
            return value
        if isinstance(node, ast.Attribute) and node.attr == "__path__":
            # ``M.__path__`` ist die Liste der Ordner eines Pakets; im Baum hat es einen.
            return value
        if isinstance(node, ast.Name | ast.Attribute) and isinstance(value, str | Place | Outside):
            # Ein Name, der an ein Tupel mit einem Element gebunden ist — auch aus einem anderen
            # Modul (``(*asset_rights.APPLICATION_ROOTS, …)``).
            return value if self._is_sequence(node, scopes, relative) else None
        return None

    def column(
        self, node: ast.expr, position: int, scopes: list[ast.AST], relative: str, env: Env | None
    ) -> Value:
        """Was ``for a, b in rows`` an der Stelle ``position`` bindet, wenn ``rows`` ein Tupel aus
        Tupeln ist, ``enumerate(…)`` oder ``tabelle.items()`` eines Wörterbuchs."""
        if isinstance(node, ast.Call) and node.args:
            called = self.foreign(node.func, scopes, relative)
            if called is not None and called.name == "builtins.enumerate":
                return None if position == 0 else self.elements(node.args[0], scopes, relative, env)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "items"
            and not node.args
        ):
            table, where, place = self._literal(node.func.value, scopes, relative)
            if isinstance(table, ast.Dict):
                found = table.keys if position == 0 else table.values
                inner = env if place == relative else None
                return choice(
                    self.evaluate(one, where, place, inner) for one in found if one is not None
                )
            return None
        rows, where, place = self._literal(node, scopes, relative)
        if not isinstance(rows, ast.Tuple | ast.List | ast.Set):
            return None
        values: list[Value] = []
        inner = env if place == relative else None
        for row in rows.elts:
            if not isinstance(row, ast.Tuple | ast.List) or position >= len(row.elts):
                return None
            values.append(self.evaluate(row.elts[position], where, place, inner))
        return choice(values)

    def _literal(
        self, node: ast.expr, scopes: list[ast.AST], relative: str
    ) -> tuple[ast.expr | None, list[ast.AST], str]:
        """Der Ausdruck selbst oder der, an den ein Name gebunden ist — auch auf Modulebene
        eines Moduls, aus dem er importiert ist; mit den Bereichen, in denen er gilt."""
        if not isinstance(node, ast.Name):
            return node, scopes, relative
        found = self.binding(node.id, scopes)
        if found is not None and found[1][0] == "value":
            value, _statement = found[1][1]
            return value, scopes[found[0] :], relative
        definition = self.definition(relative, node)
        if definition is not None and isinstance(definition.node, ast.Assign | ast.AnnAssign):
            tree = self.tree(definition.relative)
            return definition.node.value, [tree], definition.relative
        return None, scopes, relative

    def _is_sequence(
        self, node: ast.Name | ast.Attribute, scopes: list[ast.AST], relative: str
    ) -> bool:
        """Ob der Name an ein Tupel, eine Liste oder eine Menge gebunden ist — hier oder auf
        Modulebene des Moduls, das ihn trägt."""
        if isinstance(node, ast.Name):
            found = self.binding(node.id, scopes)
            if found is not None and found[1][0] == "value":
                value, _statement = found[1][1]
                return isinstance(value, ast.Tuple | ast.List | ast.Set)
        definition = self.definition(relative, node)
        return (
            definition is not None
            and isinstance(definition.node, ast.Assign | ast.AnnAssign)
            and isinstance(definition.node.value, ast.Tuple | ast.List | ast.Set)
        )

    def _attribute_of(self, value: Value, name: str) -> Value:
        if isinstance(value, Place):
            if name == "parent":
                return Place(value.parts[:-1]) if value.parts else None
            if name in ("name", "stem", "suffix") and value.parts:
                part = value.parts[-1]
                return None if _WILDCARD.search(part) else str(getattr(PurePosixPath(part), name))
            return None
        if isinstance(value, Outside):
            return value if name in ("parent", "parents") else None
        if isinstance(value, Module):
            return self.attribute(value, name)
        if isinstance(value, Foreign):
            return Foreign(f"{value.name}.{name}")
        if isinstance(value, Definition):
            return self.member(value, name)
        return None

    def _call(self, node: ast.Call, scopes: list[ast.AST], relative: str, env: Env | None) -> Value:
        function = node.func
        if isinstance(function, ast.Attribute):
            base = self.evaluate(function.value, scopes, relative, env)
            if all(isinstance(one, Place | Outside) for one in options(base)):
                return each(base, lambda one: self._path_method(one, node, scopes, relative, env))
            called = each(base, lambda one: self._attribute_of(one, function.attr))
        else:
            called = self.evaluate(function, scopes, relative, env)
        if isinstance(called, Definition):
            return self.returned(called, node, scopes, relative, env)
        if not isinstance(called, Foreign):
            return None
        name = called.name
        if name in _OUTSIDE_CALLS or name.startswith(_OUTSIDE_MODULES):
            return Outside(name)
        if name == "builtins.next" and node.args:
            # ``next(iter(tools.__path__))``: das erste Element, der Ordner des Pakets.
            inner = node.args[0]
            if isinstance(inner, ast.Call) and len(inner.args) == 1:
                wrapper = self.evaluate(inner.func, scopes, relative, env)
                if isinstance(wrapper, Foreign) and wrapper.name == "builtins.iter":
                    inner = inner.args[0]
            return self.elements(inner, scopes, relative, env)
        values = [self.evaluate(argument, scopes, relative, env) for argument in node.args]
        if name in _PATH_TYPES or name == "os.path.join":
            if not values or node.keywords:
                return None

            def path(first: Value) -> Value:
                if isinstance(first, Outside):
                    return first
                first = self.place(first)
                if not isinstance(first, Place):
                    return None
                result: Place | None = first
                for value in values[1:]:
                    if result is None or not isinstance(value, str):
                        return None
                    result = joined(result, value)
                return result

            return each(values[0], path)
        if name in _SAME_ARGUMENT and len(values) == 1:
            return each(values[0], lambda one: one if isinstance(one, Place | Outside) else None)
        if name == "os.path.dirname" and len(values) == 1:
            return each(values[0], lambda one: self._attribute_of(one, "parent"))
        # Ein Modul, über seinen Pfad oder seinen Namen geladen, ist das Modul des Baums.
        if name == "importlib.util.spec_from_file_location" and len(values) >= 2:
            return each(values[1], self._module_at)
        if name == "importlib.util.module_from_spec" and len(values) == 1:
            return values[0] if isinstance(values[0], Module) else None
        if name == "importlib.import_module" and len(values) == 1 and isinstance(values[0], str):
            return Module(values[0]) if self.module_exists(values[0]) else None
        return None

    def _module_at(self, value: Value) -> Value:
        """Das Modul des Baums, dessen Datei ``value`` ist."""
        if not isinstance(value, Place) or not value.parts or value.parts[0] not in PACKAGES:
            return None
        name = self.module_name("/".join(value.parts))
        return Module(name) if self.module_path(name) is not None else None

    def _path_method(
        self, base: Value, node: ast.Call, scopes: list[ast.AST], relative: str, env: Env | None
    ) -> Value:
        """``resolve()``, ``joinpath(…)`` und Co. eines Orts; was aus einem Temp-Ordner kommt,
        bleibt draußen (``mktemp``)."""
        if isinstance(base, Outside):
            return base
        assert isinstance(base, Place)
        method = node.func.attr  # type: ignore[attr-defined]
        if method in _SAME_PLACE and not node.args:
            return base
        if method == "joinpath":
            place: Place | None = base
            for argument in node.args:
                text = self.evaluate(argument, scopes, relative, env)
                if place is None or not isinstance(text, str):
                    return None
                place = joined(place, text)
            return place
        return None

    def returned(
        self,
        target: Definition,
        call: ast.Call,
        scopes: list[ast.AST],
        relative: str,
        env: Env | None,
    ) -> Value:
        """Was eine eigene Funktion an diesem Aufruf zurückgibt — jede ``return``-Anweisung mit
        den Werten ihrer Argumente; eine Klasse gibt ein Objekt."""
        node = target.node
        if not isinstance(node, _FUNCTIONS) or id(node) in self._calls or len(self._calls) > _DEPTH:
            return None
        inner = self.arguments(call, relative, scopes, env, target)
        self._calls.append(id(node))
        try:
            _tree, parents = self.parsed(target.relative)
            values = [
                self.evaluate(one, self.scopes(one, parents), target.relative, inner)
                for one in self._returns_of(node, yields=False)
            ]
        finally:
            self._calls.pop()
        return choice(values) if values else None

    def _returns_of(self, function: ast.AST, *, yields: bool) -> list[ast.expr]:
        """Die Ausdrücke hinter ``return`` (und ``yield``) einer Funktion, ohne innere."""
        key = (function, yields)
        if key not in self._returns:
            found: list[ast.expr] = []
            stack = list(ast.iter_child_nodes(function))
            while stack:
                node = stack.pop()
                value = node.value if isinstance(node, ast.Return | ast.Yield) else None
                if value is not None and (yields or isinstance(node, ast.Return)):
                    found.append(value)
                if not isinstance(node, (*_SCOPES, ast.ClassDef)):
                    stack.extend(ast.iter_child_nodes(node))
            self._returns[key] = found
        return self._returns[key]

    def arguments(
        self,
        call: ast.Call,
        caller: str,
        scopes: list[ast.AST],
        env: Env | None,
        target: Definition,
    ) -> dict[tuple[int, str], Value]:
        """Die Werte der Parameter von ``target`` an diesem Aufruf, Vorgaben eingeschlossen;
        ``self`` und ``cls`` bleiben frei."""
        node = target.node
        skip = 0
        _tree, target_parents = self.parsed(target.relative)
        if isinstance(node, ast.ClassDef):
            init = self.member(target, "__init__")
            if init is None:
                return {}
            node, skip = init.node, 1
        elif isinstance(node, _FUNCTIONS) and isinstance(target_parents.get(node), ast.ClassDef):
            decorators = {one.id for one in node.decorator_list if isinstance(one, ast.Name)}
            skip = 0 if "staticmethod" in decorators else 1
        if not isinstance(node, _FUNCTIONS):
            return {}
        signature = node.args
        ordered = [*signature.posonlyargs, *signature.args]
        offset = len(ordered) - len(signature.defaults)
        inside = self.scopes(node, target_parents)
        values: dict[tuple[int, str], Value] = {}
        for index, parameter in enumerate(ordered):
            if index >= offset:
                values[(id(node), parameter.arg)] = self.evaluate(
                    signature.defaults[index - offset], inside, target.relative
                )
        for parameter, default in zip(signature.kwonlyargs, signature.kw_defaults, strict=True):
            if default is not None:
                values[(id(node), parameter.arg)] = self.evaluate(default, inside, target.relative)
        for parameter, argument in zip(ordered[skip:], call.args, strict=False):
            if isinstance(argument, ast.Starred):
                break
            values[(id(node), parameter.arg)] = self.evaluate(argument, scopes, caller, env)
        for keyword in call.keywords:
            if keyword.arg is not None:
                values[(id(node), keyword.arg)] = self.evaluate(keyword.value, scopes, caller, env)
        return values

    def place(self, value: Value) -> Value:
        """Ein Text als Pfad: relativ zum Arbeitsordner, also nur mit :attr:`working_root` ein
        Ort, sonst nicht auflösbar."""
        if isinstance(value, str):
            return joined(Place(()), value) if self.working_root else None
        return value

    def value_at(self, relative: str, node: ast.expr, env: Env | None = None) -> Value:
        """:meth:`evaluate` an der Stelle von ``node`` in der Datei ``relative``."""
        _tree, parents = self.parsed(relative)
        return self.evaluate(node, self.scopes(node, parents), relative, env)

    def pattern(
        self,
        node: ast.expr,
        scopes: list[ast.AST],
        relative: str,
        env: Env | None = None,
        *,
        deep: bool = False,
    ) -> Value:
        """Ein Muster als Text oder Wahl von Texten. Ein offener Teil eines f-Strings in einem
        Namen wird ``*``, ohne mit einem Nachbarn ein ``**`` zu bilden; ein Teil, der einen
        ganzen Abschnitt ausmacht (``f"{ordner}/*.py"``), mit ``deep`` jede Tiefe — die Auswahl
        nimmt im Zweifel einen Test zu viel, W4 (ohne ``deep``) im Zweifel einen flachen Glob."""
        if not isinstance(node, ast.JoinedStr):
            return self.evaluate(node, scopes, relative, env)
        # Je Abschnitt zwischen ``/`` sein Text und ob er nur aus offenen Teilen besteht.
        segments: list[list[str]] = [[]]
        literal = [False]
        for part in node.values:
            if not isinstance(part, ast.Constant):
                segments[-1].append("*")
                continue
            for index, piece in enumerate(str(part.value).split("/")):
                if index:
                    segments.append([])
                    literal.append(False)
                segments[-1].append(piece)
                literal[-1] = literal[-1] or bool(piece)
        parts: list[str] = []
        for pieces, named in zip(segments, literal, strict=True):
            text = "".join(pieces)
            if deep and text and not named:
                if parts[-1:] != ["**"]:
                    parts.append("**")
            else:
                parts.append(text if text == "**" else re.sub(r"\*{2,}", "*", text))
        if deep and parts[-1:] == ["**"]:
            parts.append("*")
        return "/".join(parts)

    def pattern_at(self, relative: str, node: ast.expr, env: Env | None = None) -> Value:
        _tree, parents = self.parsed(relative)
        return self.pattern(node, self.scopes(node, parents), relative, env)


def is_fixture(decorator: ast.expr) -> bool:
    """``@pytest.fixture``, ``@fixture``, auch mit Argumenten."""
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    name = decorator.attr if isinstance(decorator, ast.Attribute) else getattr(decorator, "id", "")
    return name == "fixture"


def _binary(operator: ast.operator, left: Value, right: Value) -> Value:
    if isinstance(operator, ast.Div):
        if isinstance(left, Outside):
            return left
        if isinstance(left, Place) and isinstance(right, str):
            return joined(left, right)
        return None
    if isinstance(operator, ast.Add) and isinstance(left, str) and isinstance(right, str):
        return left + right
    return None


def _ancestor(value: Value, depth: int) -> Value:
    if isinstance(value, Outside):
        return value
    if isinstance(value, Place) and 0 < depth <= len(value.parts):
        return Place(value.parts[:-depth])
    return None


# --------------------------------------------------------------------------- Lesestellen

#: Methoden eines Pfads, die einen Ordner lesen.
_PATH_READS = frozenset({"glob", "rglob", "iterdir", "walk"})

#: Funktionen, die einen Ordner lesen: Name → (was den Ordner nennt, rekursiv).
_FUNCTION_READS: dict[str, tuple[str, bool]] = {
    "glob.glob": ("pattern", False),
    "glob.iglob": ("pattern", False),
    "os.walk": ("folder", True),
    "os.listdir": ("folder", False),
    "os.scandir": ("folder", False),
    "pkgutil.walk_packages": ("packages", True),
    "pkgutil.iter_modules": ("packages", False),
    "shutil.copytree": ("folder", True),
}

#: Wie das erste Argument dieser Funktionen als Schlüsselwort heißt.
_FIRST_KEYWORD: dict[str, str] = {
    "glob.glob": "pathname",
    "glob.iglob": "pathname",
    "os.walk": "top",
    "os.listdir": "path",
    "os.scandir": "path",
    "pkgutil.walk_packages": "path",
    "pkgutil.iter_modules": "path",
    "shutil.copytree": "src",
}

#: Die letzten Namen aller Lesestellen; andere Aufrufe braucht :func:`sites` nicht aufzulösen.
_READ_NAMES = frozenset({*_PATH_READS, *(name.rsplit(".", 1)[1] for name in _FUNCTION_READS)})

#: Der Text, an dem eine Datei überhaupt eine Lesestelle tragen kann: ein Aufruf als Methode
#: (``ast.walk`` ausgenommen) oder ein Import des Namens, der danach bloß gerufen wird.
READ_WORDS = re.compile(
    r"\.(?:r?glob|iglob|iterdir|listdir|scandir|walk_packages|iter_modules|copytree)\s*\("
    r"|(?<!\bast)\.walk\s*\("
    r"|\bimport\b[^\n]*\b(?:glob|iglob|walk|listdir|scandir|walk_packages|iter_modules|copytree)\b"
    r"|[\"']ls-files[\"']"
)


@dataclass(frozen=True)
class Site:
    """Eine Lesestelle: der Aufruf, wie er liest, und was den Ordner bestimmt."""

    relative: str
    call: ast.expr
    how: str
    receiver: ast.expr | None
    pattern: ast.expr | None

    @property
    def where(self) -> str:
        return f"{self.relative}:{self.call.lineno}"


def _matches(name: str, part: str) -> bool:
    return part == "**" or PurePosixPath(name).full_match(part)


def python_pattern(part: str) -> bool:
    """Ob ein Muster für einen Dateinamen eine ``.py`` treffen kann: ``*``, ``*.py``,
    ``test_*.py``, ``*_ops.py`` ja, ``*.json`` und ``*.pyi`` nein."""
    if part == "**":
        return True
    last = max(part.rfind(mark) for mark in "*?]")
    if last < 0:
        return part.endswith(".py")
    tail = part[last + 1 :]
    return not tail or ".py".endswith(tail) or tail.endswith(".py")


@dataclass(frozen=True)
class Read:
    """Was eine Lesestelle liest: Ordner, Muster relativ dazu (``**`` heißt jede Tiefe), Stelle.

    ``folder`` ist ein :class:`Place` ohne Muster, :class:`Outside` oder ``None`` (nicht
    auflösbar).
    """

    folder: Place | Outside | None
    pattern: tuple[str, ...]
    site: str
    #: Ob sich das Muster nicht auflösen ließ (:data:`OPEN_PATTERN`).
    open_pattern: bool = False

    @property
    def origin(self) -> str:
        """Der oberste Ordner der Datei, in der gelesen wird: ``app``, ``tools``, ``tests``."""
        return self.site.split("/", 1)[0]

    def meets_python(self) -> bool:
        """Ob diese Stelle überhaupt eine Python-Datei des Baums lesen kann.

        Ein Ordner im Repository zählt mit jedem Muster, das eine ``.py`` trifft (``*``,
        ``*.py``). Ein nicht auflösbarer Ordner zählt nur mit einem Muster, das Python nennt
        (``*.py``): Ein ``rglob("*")`` über einen unbekannten Ordner geht im Bestand über
        Programme, Archive, Profile und Temp-Bäume, und die Lesemessung aller Testdateien
        fand darunter keinen Leser von Quellen. Unter ``app/`` zählt ein nicht auflösbarer
        Ordner nie: Die Anwendung liest so Nutzer- und Profilordner, und zählte das, wäre
        jede Änderung die Suite (CS-32). Ein Muster, das sich selbst nicht auflösen lässt,
        zählt dagegen auch über einem offenen Ordner: Es kann ``app/**/*.py`` sein (F-4).
        """
        if isinstance(self.folder, Outside):
            return False
        if self.folder is None:
            return self.origin != "app" and (self.open_pattern or ".py" in self.pattern[-1])
        return python_pattern(self.pattern[-1])

    def covers(self, path: PurePosixPath) -> bool:
        """Ob ``path`` (relativ zur Wurzel) unter dem liegt, was diese Stelle liest; ein nicht
        auflösbarer Ordner liest jeden Ort, auf dessen Namen das Muster passt, wenn es Python
        nennt (:meth:`meets_python`)."""
        if isinstance(self.folder, Outside):
            return False
        if self.folder is None:
            return self.meets_python() and _matches(path.name, self.pattern[-1])
        fixed = list(self.folder.parts)
        rest = list(self.pattern)
        while rest and not _WILDCARD.search(rest[0]):
            fixed.append(rest.pop(0))
        if tuple(path.parts[: len(fixed)]) != tuple(fixed):
            return False
        remainder = path.parts[len(fixed) :]
        if not rest:
            return not remainder
        return bool(remainder) and PurePosixPath(*remainder).full_match("/".join(rest))

    def describe(self) -> str:
        """Was gelesen wird, als ein Pfadmuster: ``app/ui/**/*.py``."""
        head = self.folder.parts if isinstance(self.folder, Place) else ("<unauflösbar>",)
        return "/".join((*head, *self.pattern))


def _pattern_parts(text: str, recursive: bool) -> tuple[str, ...]:
    parts = tuple(part for part in text.replace("\\", "/").split("/") if part not in ("", "."))
    parts = parts or ("*",)
    return ("**", *parts) if recursive and parts[0] != "**" else parts


def _read(folder: Value, pattern: tuple[str, ...], site: str, text: str = "") -> Read:
    """Eine Lesung; Muster im Ordner (aus einer Schleife über eine Lesestelle) wandern ins
    Muster. ``text`` ist das Muster, wie es dastand — :data:`OPEN_PATTERN`, wenn offen."""
    opened = text == OPEN_PATTERN
    if isinstance(folder, Place):
        cut = next(
            (index for index, part in enumerate(folder.parts) if _WILDCARD.search(part)),
            len(folder.parts),
        )
        return Read(Place(folder.parts[:cut]), (*folder.parts[cut:], *pattern), site, opened)
    return Read(folder if isinstance(folder, Outside) else None, pattern, site, opened)


def sites(resolver: Resolver, relative: str) -> list[Site]:
    """Jede Lesestelle einer Datei, ohne ein eigenes Modul dafür zu lesen."""
    tree, parents = resolver.parsed(relative)
    calls: list[ast.Call] = []
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            calls.append(node)
        elif isinstance(node, ast.ImportFrom):
            aliases.update(
                alias.asname or alias.name for alias in node.names if alias.name in _READ_NAMES
            )
    found: list[Site] = []
    for node in calls:
        listing = _git_listing(node)
        if listing is not None:
            cwd = next((one.value for one in node.keywords if one.arg == "cwd"), None)
            found.append(Site(relative, node, "git ls-files", cwd, listing))
            continue
        function = node.func
        if isinstance(function, ast.Attribute):
            if function.attr not in _READ_NAMES:
                continue
        elif not isinstance(function, ast.Name) or function.id not in aliases:
            continue
        scopes = resolver.scopes(node, parents)
        if isinstance(function, ast.Attribute) and function.attr in _PATH_READS:
            base = resolver.foreign(function.value, scopes, relative)
            if base is not None:
                name = f"{base.name}.{function.attr}"
                if name in _FUNCTION_READS:
                    found.append(_function_site(relative, node, name))
                continue
            if _is_module_or_definition(resolver, function.value, scopes):
                continue
            pattern = _argument(node, 0, "pattern") if function.attr in ("glob", "rglob") else None
            found.append(Site(relative, node, function.attr, function.value, pattern))
            continue
        called = resolver.foreign(function, scopes, relative)
        if called is not None and called.name in _FUNCTION_READS:
            found.append(_function_site(relative, node, called.name))
    return found


def _git_listing(node: ast.Call) -> ast.List | ast.Tuple | None:
    """Die Befehlsliste eines Aufrufs, der ``git ls-files`` startet — ``subprocess.run([…])``
    und Co.; so lesen ``test_source_escapes`` und ``docs_scan`` die Dateien des Baums."""
    for argument in node.args:
        if (
            isinstance(argument, ast.List | ast.Tuple)
            and argument.elts
            and isinstance(argument.elts[0], ast.Constant)
            and argument.elts[0].value == "git"
            and any(
                isinstance(one, ast.Constant) and one.value == "ls-files" for one in argument.elts
            )
        ):
            return argument
    return None


def _is_module_or_definition(resolver: Resolver, node: ast.expr, scopes: list[ast.AST]) -> bool:
    """Ob der Empfänger ein eigenes Modul oder eine Definition ist — dann ist ``x.walk()`` ein
    Aufruf ins Modul, kein Pfad. Geprüft an der Bindung, ohne das Modul zu lesen."""
    if not isinstance(node, ast.Name):
        return False
    found = resolver.binding(node.id, scopes)
    return found is not None and found[1][0] in ("module", "def")


def _function_site(relative: str, node: ast.Call, name: str) -> Site:
    how, _recursive = _FUNCTION_READS[name]
    argument = _argument(node, 0, _FIRST_KEYWORD[name])
    if how == "pattern":
        root_dir = next((one.value for one in node.keywords if one.arg == "root_dir"), None)
        return Site(relative, node, name, root_dir, argument)
    return Site(relative, node, name, argument, None)


def _pathspecs(
    resolver: Resolver, site: Site, scopes: list[ast.AST], env: Env | None
) -> list[str | None]:
    """Die Pfadangaben eines ``git ls-files``-Aufrufs nach ``--``; keine heißt der ganze Baum,
    eine, die sich nicht auflösen lässt, ``None``."""
    assert isinstance(site.pattern, ast.List | ast.Tuple)
    items = site.pattern.elts
    marker = next(
        (
            index
            for index, one in enumerate(items)
            if isinstance(one, ast.Constant) and one.value == "--"
        ),
        None,
    )
    if marker is None:
        return [""]
    found: list[str | None] = []
    for item in items[marker + 1 :]:
        node = item.value if isinstance(item, ast.Starred) else item
        value = resolver.evaluate(node, scopes, site.relative, env)
        found.extend(one if isinstance(one, str) else None for one in options(value))
    return found or [""]


def _spec_reads(base: Value, spec: str | None, where: str) -> list[Read]:
    """Was eine Pfadangabe von ``git ls-files`` liest: ``*.md`` jede Tiefe, ``app`` alles
    darunter, ``app/x.py`` die Datei selbst; Vorsätze wie ``:(glob)`` fallen weg."""
    if spec is None:
        return [_read(base, ("**", "*"), where)]
    text = re.sub(r"^:\([^)]*\)", "", spec).strip("/")
    if not text or text == ".":
        return [_read(base, ("**", "*"), where)]
    parts = tuple(part for part in text.split("/") if part not in ("", "."))
    if _WILDCARD.search(text):
        return [_read(base, ("**", *parts) if len(parts) == 1 else parts, where)]
    if not isinstance(base, Place):
        return [_read(base, ("**", "*"), where)]
    inside = joined(base, text)
    if inside is None:
        return []
    return [_read(inside, ("**", "*"), where), _read(Place(inside.parts[:-1]), parts[-1:], where)]


def evaluate_site(resolver: Resolver, site: Site, env: Env | None) -> list[Read]:
    """Was eine Lesestelle liest, mit den Parameterwerten ``env``."""
    _tree, parents = resolver.parsed(site.relative)
    scopes = resolver.scopes(site.call, parents)

    def folders(node: ast.expr | None) -> tuple[Value, ...]:
        if node is None:
            return (None,)
        found = options(resolver.evaluate(node, scopes, site.relative, env))
        return tuple(resolver.place(one) for one in found)

    def patterns(node: ast.expr | None) -> tuple[str, ...]:
        if node is None:
            return (OPEN_PATTERN,)
        found = options(resolver.pattern(node, scopes, site.relative, env, deep=True))
        return tuple(one if isinstance(one, str) else OPEN_PATTERN for one in found)

    how = site.how
    if how == "git ls-files":
        bases = (Place(()),) if site.receiver is None else folders(site.receiver)
        return [
            read
            for base in bases
            for spec in _pathspecs(resolver, site, scopes, env)
            for read in _spec_reads(base, spec, site.where)
        ]
    if how in ("glob", "rglob"):
        return [
            _read(folder, _pattern_parts(text, how == "rglob"), site.where, text)
            for folder in folders(site.receiver)
            for text in patterns(site.pattern)
        ]
    if how in ("iterdir", "walk"):
        pattern = ("*",) if how == "iterdir" else ("**", "*")
        return [_read(folder, pattern, site.where) for folder in folders(site.receiver)]
    kind, recursive = _FUNCTION_READS[how]
    if kind == "folder":
        pattern = ("**", "*") if recursive else ("*",)
        return [_read(folder, pattern, site.where) for folder in folders(site.receiver)]
    if kind == "pattern":
        if site.receiver is not None:  # ``root_dir=``
            return [
                _read(folder, _pattern_parts(text, False), site.where, text)
                for folder in folders(site.receiver)
                for text in patterns(site.pattern)
            ]
        found: list[Read] = []
        for one in folders(site.pattern):
            if isinstance(one, Place) and one.parts:
                found.append(_read(Place(one.parts[:-1]), (one.parts[-1],), site.where))
            elif isinstance(one, Outside):
                found.append(Read(one, ("*",), site.where))
            else:
                # Ein Text gilt relativ zum Arbeitsordner und ist nicht auflösbar.
                found.extend(
                    _read(None, _pattern_parts(text, False), site.where, text)
                    for text in ((one,) if isinstance(one, str) else patterns(site.pattern))
                )
        return found
    # Pakete: eine Liste von Ordnern, ``M.__path__`` oder nichts (der Suchpfad).
    pattern = ("**", "*.py") if recursive else ("*.py",)
    return [_read(folder, pattern, site.where) for folder in folders(site.receiver)]


# --------------------------------------------------------------------------- W4


@dataclass(frozen=True)
class FlatGlob:
    """Ein flaches ``glob`` auf ``*.py``: wo es steht und welchen Ordner es liest."""

    where: str
    line: int
    folder: str | None
    pattern: str


#: Ein Muster, das Python-Quellen meint: ``*.py``, ``test_*.py``, ``*.pyi``, ``*.py*``.
SOURCE_PATTERN = re.compile(r"\.pyi?\*?$")

#: Woran eine Datei ein ``glob`` tragen kann — auch umbenannt aus dem Modul ``glob``.
GLOB_MENTION = re.compile(r"\bi?glob\b")


def flat_globs(root: Path, relative: str, resolver: Resolver | None = None) -> list[FlatGlob]:
    """Jedes ``glob`` auf Python-Quellen ohne ``**`` in einer Datei, je Ordner, den es liest.

    Gesucht werden ``<pfad>.glob(…)`` und das Modul ``glob`` unter jedem Namen
    (``glob.glob``, ``iglob``, ``from glob import glob as find``, ``import glob as g``); dieses
    liest relativ zum Arbeitsordner und ist damit nie auflösbar. Das Muster darf eine
    Konstante sein. Ein Verzeichnisteil im Muster gehört zum Ordner; ein Empfänger aus einer
    Schleife liest jeden seiner Ordner.
    """
    resolver = resolver or Resolver(root)
    found: list[FlatGlob] = []
    for site in sites(resolver, relative):
        if site.how not in ("glob", "glob.glob", "glob.iglob") or site.pattern is None:
            continue
        line = site.call.lineno
        for pattern in options(resolver.pattern_at(relative, site.pattern)):
            if not isinstance(pattern, str) or not SOURCE_PATTERN.search(pattern):
                continue
            if "**" in pattern:
                continue
            receivers: tuple[Value, ...] = (None,)
            if site.how == "glob" and site.receiver is not None:
                receivers = options(resolver.value_at(relative, site.receiver))
            directory = PurePosixPath(pattern).parent.as_posix()
            for receiver in receivers:
                folder = None
                if (
                    isinstance(receiver, Place)
                    and not _WILDCARD.search(receiver.text)
                    and not _WILDCARD.search(directory)
                ):
                    place = joined(receiver, directory)
                    folder = place.text if place is not None else None
                found.append(FlatGlob(f"{relative}:{line}", line, folder, pattern))
    return found


def sources_with_globs(root: Path, folders: tuple[str, ...]) -> list[str]:
    """Die Dateien unter ``folders``, die ``glob`` überhaupt nennen — der Rest braucht keinen
    Syntaxbaum."""
    return [
        path.relative_to(root).as_posix()
        for folder in folders
        for path in sorted((root / folder).rglob("*.py"))
        if "__pycache__" not in path.parts and GLOB_MENTION.search(path.read_text(encoding="utf-8"))
    ]


# --------------------------------------------------------------------------- Leser


@dataclass(frozen=True)
class Borrowed:
    """Eine Lesung einer Testdatei mit der Datei, in der gelesen wird, und der Einheit der
    Testdatei, die liest: Test, Fixture oder Klasse beim Namen, ``""`` für die Modulebene,
    die jeder Fall beim Import ausführt."""

    read: Read
    lender: str
    unit: str = ""


def owner(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> ast.AST | None:
    """Die Einheit, zu der ``node`` gehört: die innerste Funktion, sonst der Klassenrumpf oder
    die Zuweisung auf Modulebene. ``None`` heißt: Modulebene ohne Namen."""
    current = parents.get(node)
    statement: ast.AST = node
    while current is not None:
        if isinstance(current, (*_FUNCTIONS, ast.ClassDef)):
            return current
        if isinstance(current, ast.Module):
            return statement if isinstance(statement, ast.Assign | ast.AnnAssign) else None
        statement = current
        current = parents.get(current)
    return None


def _unit_names(unit: ast.AST) -> list[str]:
    if isinstance(unit, (*_FUNCTIONS, ast.ClassDef)):
        return [unit.name]
    if isinstance(unit, ast.Assign):
        return [target.id for target in unit.targets if isinstance(target, ast.Name)]
    if isinstance(unit, ast.AnnAssign) and isinstance(unit.target, ast.Name):
        return [unit.target.id]
    return []


def _chains(node: ast.expr) -> Iterator[ast.expr]:
    """Eine Attributkette und jedes ihrer Anfangsstücke: ``a.b.c`` → ``a.b.c``, ``a.b``, ``a``."""
    while isinstance(node, ast.Attribute):
        yield node
        node = node.value
    if isinstance(node, ast.Name):
        yield node


def _last(node: ast.expr) -> str:
    return node.attr if isinstance(node, ast.Attribute) else node.id  # type: ignore[attr-defined]


def _is_annotation(node: ast.AST, field: str) -> bool:
    """Ob das Feld ``field`` von ``node`` eine Annotation trägt: Parameter, Rückgabe,
    annotierte Zuweisung."""
    return (
        (isinstance(node, ast.arg) and field == "annotation")
        or (isinstance(node, _FUNCTIONS) and field == "returns")
        or (isinstance(node, ast.AnnAssign) and field == "annotation")
    )


#: Ein Bezeichner im Text — für die Vorauswahl, wer einen Namen überhaupt trägt.
_WORD = re.compile(r"[A-Za-z_]\w*")

_Key = tuple[tuple[str, int], frozenset[tuple[tuple[int, str], Value]]]


@dataclass
class Facts:
    """Was je Datei gilt, gleich wonach gefragt wird: Lesestellen je Einheit, Nennungen, Wörter,
    Definitionen und wer ein Modul erreicht. Die Leser über Python und über alles eines Graphen
    teilen sie, statt jede Datei zweimal zu durchsuchen (F-6)."""

    sites: dict[str, dict[ast.AST | None, list[Site]]] = field(default_factory=dict)
    refs: dict[str, dict[ast.AST | None, list[tuple[ast.expr, ast.Call | None]]]] = field(
        default_factory=dict
    )
    by_name: dict[str, dict[str, list[tuple[ast.AST | None, ast.expr]]]] = field(
        default_factory=dict
    )
    words: dict[str, set[str]] = field(default_factory=dict)
    defined: dict[int, Definition | None] = field(default_factory=dict)
    importers: dict[str, list[str]] = field(default_factory=dict)


class TreeReads:
    """Welche Testdatei welchen Ordner liest — selbst oder über eine Definition, die sie nennt.

    ``modules`` ordnet jedem Modulnamen unter ``app``, ``tools``, ``tests`` seine Datei zu,
    ``importers`` jedem Modul die Module, die es direkt importieren (der Graph der Auswahl).

    Eine **Einheit** ist eine Funktion, eine Methode, ein Klassenrumpf oder eine Zuweisung auf
    Modulebene. Sie liest, wenn sie eine Lesestelle trägt, die nicht sicher draußen liegt, oder
    eine lesende Einheit nennt. Gesucht wird von den Lesestellen aus über die Module, die den
    Namen der Einheit tragen und ihr Modul mittelbar importieren — geparst wird nur, wer den
    Namen trägt. Mit ``python_only`` zählen nur Lesestellen, deren Muster eine ``.py`` treffen
    kann: Das genügt für eine Änderung an Python und spart ein Drittel der Zeit.
    """

    def __init__(
        self,
        root: Path,
        modules: Mapping[str, Path],
        importers: Mapping[str, Iterable[str]],
        resolver: Resolver | None = None,
        *,
        python_only: bool = False,
        facts: Facts | None = None,
    ) -> None:
        self.root = root
        self.python_only = python_only
        self.resolver = resolver or Resolver(root, working_root=True)
        self.relative = {name: path.relative_to(root).as_posix() for name, path in modules.items()}
        self.names = {relative: name for name, relative in self.relative.items()}
        self.importers = importers
        self.texts = {relative: self.resolver.text(relative) for relative in self.relative.values()}
        #: Geteilt mit einem zweiten Leser über denselben Graphen und Auflöser.
        self.facts = facts if facts is not None else Facts()
        self._sites = self.facts.sites
        self._refs = self.facts.refs
        self._by_name = self.facts.by_name
        self._word_sets = self.facts.words
        #: Jede lesende Einheit mit ihrer Datei.
        self.reading: dict[ast.AST, str] = {}
        #: Dateien, die eine lesende Einheit auf Modulebene ohne Namen nennen.
        self.touched: set[str] = set()
        self._memo: dict[_Key, list[Borrowed]] = {}
        self._active: set[_Key] = set()
        self._defined = self.facts.defined
        self._importers = self.facts.importers
        self._spread()
        self.reading_names = {name for unit in self.reading for name in _unit_names(unit)}

    # Haken -------------------------------------------------------------------------

    def _may_read(self, relative: str, text: str) -> bool:
        """Ob eine Datei eine Lesestelle tragen kann — die Vorauswahl vor dem Syntaxbaum."""
        return READ_WORDS.search(text) is not None

    def _evaluate_site(self, site: Site, env: Env | None) -> list[Read]:
        """Was eine Stelle mit den Parameterwerten ``env`` liest."""
        return evaluate_site(self.resolver, site, env)

    def _lends(self, relative: str, node: ast.expr) -> bool:
        """Ob die Nennung ``node`` die Lesungen ihres Ziels weitergibt — hier jede."""
        return True

    # Einheiten ---------------------------------------------------------------------

    def _sites_by_unit(self, relative: str) -> dict[ast.AST | None, list[Site]]:
        if relative not in self._sites:
            grouped: dict[ast.AST | None, list[Site]] = defaultdict(list)
            if READ_WORDS.search(self.texts.get(relative, "")):
                _tree, parents = self.resolver.parsed(relative)
                for site in sites(self.resolver, relative):
                    grouped[owner(site.call, parents)].append(site)
            self._sites[relative] = grouped
        return self._sites[relative]

    def _words(self, relative: str) -> set[str]:
        if relative not in self._word_sets:
            self._word_sets[relative] = set(_WORD.findall(self.texts.get(relative, "")))
        return self._word_sets[relative]

    def _references(
        self, relative: str
    ) -> dict[ast.AST | None, list[tuple[ast.expr, ast.Call | None]]]:
        """Je Einheit jeder gelesene Name und jedes Anfangsstück einer Attributkette, mit dem
        Aufruf, dessen Ziel die ganze Kette ist."""
        if relative not in self._refs:
            self._scan(relative)
        return self._refs[relative]

    def _named(self, relative: str, name: str) -> list[tuple[ast.AST | None, ast.expr]]:
        """Jede Nennung von ``name`` in einer Datei, mit ihrer Einheit."""
        if relative not in self._by_name:
            self._scan(relative)
        return self._by_name[relative].get(name, [])

    def _scan(self, relative: str) -> None:
        """Ein Gang über den Baum: Nennungen je Einheit und je Name. Annotationen nennen einen
        Typ und rufen nichts (``graph: ImportGraph``), sie zählen nicht."""
        tree = self.resolver.tree(relative)
        by_owner: dict[ast.AST | None, list[tuple[ast.expr, ast.Call | None]]] = defaultdict(list)
        by_name: dict[str, list[tuple[ast.AST | None, ast.expr]]] = defaultdict(list)

        def emit(node: ast.expr, owner: ast.AST | None, call: ast.Call | None) -> ast.expr:
            """Trägt die Kette ein und gibt ihren Grund zurück (``f(x).y`` → ``f(x)``)."""
            for index, piece in enumerate(_chains(node)):
                by_owner[owner].append((piece, call if index == 0 else None))
                by_name[_last(piece)].append((owner, piece))
            while isinstance(node, ast.Attribute):
                node = node.value
            return node

        stack: list[tuple[ast.AST, ast.AST | None]] = [
            (
                statement,
                statement
                if isinstance(statement, (*_FUNCTIONS, ast.ClassDef, ast.Assign, ast.AnnAssign))
                else None,
            )
            for statement in tree.body
        ]
        while stack:
            node, owner = stack.pop()
            if isinstance(node, (*_FUNCTIONS, ast.ClassDef)):
                owner = node
            pending: list[ast.AST] = []
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name | ast.Attribute):
                base = emit(node.func, owner, node)
                if not isinstance(base, ast.Name):
                    pending.append(base)
                pending.extend(node.args)
                pending.extend(keyword.value for keyword in node.keywords)
            elif isinstance(node, ast.Name | ast.Attribute) and isinstance(node.ctx, ast.Load):
                base = emit(node, owner, None)
                if not isinstance(base, ast.Name):
                    pending.append(base)
            else:
                for field, value in ast.iter_fields(node):
                    if _is_annotation(node, field):
                        continue
                    if isinstance(value, ast.AST):
                        pending.append(value)
                    elif isinstance(value, list):
                        pending.extend(item for item in value if isinstance(item, ast.AST))
            stack.extend((child, owner) for child in pending)
        self._refs[relative] = by_owner
        self._by_name[relative] = by_name

    def _target(self, relative: str, node: ast.expr) -> Definition | None:
        """Die lesende Einheit, die ``node`` nennt — auch eine Zuweisung auf Modulebene wie
        ``FILES = sorted(…glob…)``."""
        if id(node) not in self._defined:
            self._defined[id(node)] = self.resolver.definition(relative, node)
        found = self._defined[id(node)]
        return found if found is not None and found.node in self.reading else None

    def _mark(self, unit: ast.AST, relative: str, queue: list[tuple[str, ast.AST]]) -> None:
        if unit in self.reading:
            return
        self.reading[unit] = relative
        queue.append((relative, unit))
        _tree, parents = self.resolver.parsed(relative)
        parent = parents.get(unit)
        if isinstance(unit, _FUNCTIONS) and isinstance(parent, ast.ClassDef):
            # Wer die Klasse nennt, bezieht die Methode.
            self._mark(parent, relative, queue)

    def _spread(self) -> None:
        """Markiert jede Einheit, die liest — selbst oder über eine, die sie nennt."""
        queue: list[tuple[str, ast.AST]] = []
        for relative, text in self.texts.items():
            if not self._may_read(relative, text):
                continue
            # Ein offener Ordner kann an einer Aufrufstelle einer im Baum werden — außer unter
            # ``app/``, wo nur ein Ordner zählt, der ohne Aufrufstelle feststeht (CS-32).
            counts = Place if relative.startswith("app/") else (Place, type(None))
            for unit, found in self._sites_by_unit(relative).items():
                if unit is None:
                    continue
                if any(
                    isinstance(read.folder, counts)
                    and (not self.python_only or python_pattern(read.pattern[-1]))
                    for site in found
                    for read in self._evaluate_site(site, None)
                ):
                    self._mark(unit, relative, queue)
        done: set[tuple[str, str]] = set()
        while queue:
            relative, unit = queue.pop()
            for name in _unit_names(unit):
                if (relative, name) in done:
                    continue
                done.add((relative, name))
                for candidate in self._candidates(relative):
                    if name not in self._words(candidate):
                        continue
                    for owner, node in self._named(candidate, name):
                        if owner is not None and owner in self.reading:
                            continue
                        if self._target(candidate, node) is None:
                            continue
                        if owner is None:
                            self.touched.add(candidate)
                        else:
                            self._mark(owner, candidate, queue)

    def _candidates(self, relative: str) -> Iterator[str]:
        """Die Datei selbst, jede, die ihr Modul mittelbar importiert, und jede, die ihren
        Dateinamen nennt — so laden Tests ein Werkzeug über den Pfad
        (``spec_from_file_location``).

        Eine lesende Einheit unter ``app/`` geht nur an Module unter ``tools/`` und ``tests/``
        weiter, nicht an andere Module der Anwendung: Sonst trüge der Stempel aus
        Änderungszeiten in ``paths.py`` die Lesung in jede Funktion, die den Zwischenspeicher
        öffnet, und jede Änderung unter ``app/core`` wählte fast jede Testdatei.
        """
        yield relative
        if relative not in self._importers:
            found: list[str] = []
            module = self.names.get(relative)
            inside_app = relative.startswith("app/")
            seen = {module}
            queue = [module] if module is not None else []
            while queue:
                for importer in self.importers.get(queue.pop(), ()):
                    if importer not in seen:
                        seen.add(importer)
                        queue.append(importer)
                        path = self.relative.get(importer)
                        if path is not None and not (inside_app and path.startswith("app/")):
                            found.append(path)
            if not inside_app:
                # Über den Pfad lädt ein Test ein Werkzeug oder einen Helfer, kein Modul der
                # Anwendung.
                file_name = PurePosixPath(relative).name
                known = set(found)
                found.extend(
                    other
                    for other, text in self.texts.items()
                    if other not in known
                    and other != relative
                    and not other.startswith("app/")
                    and file_name in text
                )
            self._importers[relative] = found
        yield from self._importers[relative]

    # Auswertung --------------------------------------------------------------------

    def unit_reads(self, relative: str, unit: ast.AST | None, env: Env | None) -> list[Borrowed]:
        """Was eine Einheit liest — ihre Stellen und die lesenden Einheiten, die sie nennt."""
        key: _Key = ((relative, id(unit)), frozenset((env or {}).items()))
        if key in self._memo:
            return self._memo[key]
        if key in self._active:
            return []
        self._active.add(key)
        try:
            found = [
                Borrowed(read, relative)
                for site in self._sites_by_unit(relative).get(unit, ())
                for read in self._evaluate_site(site, env)
            ]
            _tree, parents = self.resolver.parsed(relative)
            for node, call in self._references(relative).get(unit, ()):
                if _last(node) not in self.reading_names or not self._lends(relative, node):
                    continue
                target = self._target(relative, node)
                if target is None:
                    continue
                inner: dict[tuple[int, str], Value] = {}
                _target_tree, target_parents = self.resolver.parsed(target.relative)
                if target.relative == relative and not isinstance(
                    target_parents.get(target.node), ast.Module | ast.ClassDef
                ):
                    inner.update(env or {})  # eine innere Funktion sieht die äußeren Parameter
                if call is not None:
                    scopes = self.resolver.scopes(call, parents)
                    inner.update(self.resolver.arguments(call, relative, scopes, env, target))
                found.extend(self._definition_reads(target, inner, called=call is not None))
            self._memo[key] = found
            return found
        finally:
            self._active.discard(key)

    def _definition_reads(self, target: Definition, env: Env, *, called: bool) -> list[Borrowed]:
        node = target.node
        if not isinstance(node, ast.ClassDef):
            return self.unit_reads(target.relative, node, env)
        found = list(self.unit_reads(target.relative, node, {}))
        for statement in node.body:
            if isinstance(statement, _FUNCTIONS) and statement in self.reading:
                inner = env if called and statement.name == "__init__" else {}
                found.extend(self.unit_reads(target.relative, statement, inner))
        return found

    def test_reads(self, relative: str) -> list[Borrowed]:
        """Alles, was eine Testdatei liest: Modulebene, jede Funktion, die sie nicht selbst
        ruft (Test, Fixture, Rückruf), jede Klasse und was sie davon bezieht."""
        tree = self.resolver.tree(relative)
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        found = list(self.unit_reads(relative, None, None))
        for statement in tree.body:
            if isinstance(statement, ast.Assign | ast.AnnAssign):
                found.extend(self.unit_reads(relative, statement, None))
            elif isinstance(statement, ast.ClassDef):
                found.extend(
                    replace(one, unit=statement.name)
                    for one in self._definition_reads(
                        Definition(relative, statement), {}, called=False
                    )
                )
            elif isinstance(statement, _FUNCTIONS) and statement.name not in called:
                found.extend(
                    replace(one, unit=statement.name)
                    for one in self.unit_reads(relative, statement, None)
                )
        return found

    def readers(self, tests: Iterable[str]) -> dict[str, list[Borrowed]]:
        """Je Testdatei aus ``tests``, die etwas liest, das nicht sicher draußen liegt, ihre
        Lesungen."""
        holders = set(self.reading.values()) | self.touched
        found: dict[str, list[Borrowed]] = {}
        for relative in tests:
            if relative not in holders and not self._may_read(
                relative, self.texts.get(relative, "")
            ):
                continue
            reads = list(
                dict.fromkeys(
                    one
                    for one in self.test_reads(relative)
                    if not isinstance(one.read.folder, Outside)
                )
            )
            if reads:
                found[relative] = reads
        return found
