"""Wer welchen Ordner des Baums liest — statisch, ohne Import (Codestruktur Schritt 0, W4 und E5).

Zwei Prüfungen fragen dasselbe:

- **W4** (``tests/test_source_readers.py``): Liest ein ``glob`` auf Python-Quellen flach über
  ein Paket? Dafür der Ordner jedes solchen Globs (:func:`flat_globs`).
- **Die Auswahl** (``tools/affected_tests.py``) braucht denselben Auflöser für die Frage,
  welche Testdateien den Ordner einer Änderung lesen.

**Lesestellen** sind ``glob``, ``rglob``, ``iterdir`` und ``walk`` eines Pfads, die Funktionen
``glob.glob``/``iglob``, ``os.walk``/``listdir``/``scandir``, ``pkgutil.walk_packages``/
``iter_modules`` und ``shutil.copytree`` — auch umbenannt (``from glob import glob as find``).
``ast.walk`` ist keine: Ein Empfänger, der ein fremdes Modul ist, liest keinen Ordner.

**Aufgelöst wird statisch**, wie Python einen Namen sucht: Funktion, umgebende Funktionen,
Modul, eingebaut; ein Klassenrumpf nur für Code direkt darin. Gefaltet werden
``Path(__file__)``-Ketten, ``.parent``, ``.parents[n]``, ``resolve()``, ``joinpath``, ``/``,
``Path(M.__file__)``, ``M.__path__``, Konstanten und Importe eigener Module, auch relativ,
Muster aus Konstanten, Schleifen über Tupel und über das, was eine Lesestelle liefert
(:class:`Choice`), ``or`` und der Rückgabewert einer eigenen Funktion mit den Werten ihrer
Argumente. Mehr als eine Bindung, ein Parameter ohne Wert oder ein Arbeitsordner heißt „nicht
auflösbar“ (``None``).

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
CI läuft. Dieser Auflöser parst nur die Dateien, die eine Frage berührt, und faltet nur
Ordnerausdrücke. Was er nicht auflöst, ist ``None`` und liest in der Auswahl jeden Ordner —
ein Test zu viel, nie einer zu wenig.
"""

from __future__ import annotations

import ast
import builtins
import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

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

#: Die Ordner, deren Module ein Punktname erreicht.
_PACKAGES = ("app", "tools", "tests")

#: So tief folgt die Auflösung Rückgabewerten in andere Funktionen.
_DEPTH = 12

_WILDCARD = re.compile(r"[*?\[]")


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
    """Löst Ausdrücke einer Datei unter ``root`` statisch auf; parst jede Datei höchstens einmal."""

    def __init__(self, root: Path, *, working_root: bool = False) -> None:
        self.root = root
        #: Ob ein relativer Pfad relativ zur Wurzel gilt. Für die Auswahl ja: Die Suite läuft
        #: dort (``suite-getrennt.sh``, CI, ``affected_tests --run``). W4 nicht: Dort ist ein
        #: Glob über den Arbeitsordner selbst der Fund.
        self.working_root = working_root
        self._trees: dict[str, tuple[ast.Module, dict[ast.AST, ast.AST]]] = {}
        self._bindings: dict[ast.AST, dict[str, list[tuple[str, object]]]] = {}
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
        if not name or name.split(".", 1)[0] not in _PACKAGES:
            return False
        if name not in self._exists:
            self._exists[name] = (
                self.module_path(name) is not None or self.root.joinpath(*name.split(".")).is_dir()
            )
        return self._exists[name]

    def parsed(self, relative: str) -> tuple[ast.Module, dict[ast.AST, ast.AST]]:
        """Syntaxbaum und Eltern; eine Datei mit Syntaxfehler (fremder Zwischenstand im
        geteilten Baum) zählt als leer."""
        if relative not in self._trees:
            try:
                text = (self.root / relative).read_text(encoding="utf-8")
                tree = ast.parse(text, filename=relative)
            except SyntaxError, ValueError, OSError:
                tree = ast.Module(body=[], type_ignores=[])
            parents: dict[ast.AST, ast.AST] = {}
            stack: list[ast.AST] = [tree]
            while stack:
                node = stack.pop()
                for child in ast.iter_child_nodes(node):
                    parents[child] = node
                    stack.append(child)
            self._trees[relative] = (tree, parents)
        return self._trees[relative]

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

    def bindings(self, scope: ast.AST) -> dict[str, list[tuple[str, object]]]:
        """Jeder Name, den ``scope`` bindet, mit der Art jeder Bindung."""
        if scope in self._bindings:
            return self._bindings[scope]
        found: dict[str, list[tuple[str, object]]] = defaultdict(list)
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

    def _bind(self, node: ast.AST, found: dict[str, list[tuple[str, object]]]) -> None:
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

    def binding(self, name: str, scopes: list[ast.AST]) -> tuple[int, tuple[str, object]] | None:
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
            statement, imported = data  # type: ignore[misc]
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
            iterable, position = data  # type: ignore[misc]
            return self.column(iterable, position, scopes[index:], relative, env)
        if kind in ("value", "for", "with"):
            expression = data[0] if kind == "value" else data  # type: ignore[index]
            if expression is None:
                return None
            key = (id(expression), relative)
            if key in self._busy:
                return None
            self._busy.add(key)
            try:
                inner = scopes[index:]
                if kind == "for":
                    return self.elements(expression, inner, relative, env)  # type: ignore[arg-type]
                value = self.evaluate(expression, inner, relative, env)  # type: ignore[arg-type]
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
            statement, imported = data  # type: ignore[misc]
            return self.imported(statement, imported, relative)
        if kind == "def":
            return Definition(relative, data)  # type: ignore[arg-type]
        if kind == "param":
            function, parameter = data  # type: ignore[misc]
            if env is not None and (id(function), parameter) in env:
                return env[(id(function), parameter)]
            if parameter in _TEMP_FIXTURES:
                return Outside("pytest")
            takes_fixtures = isinstance(function, _FUNCTIONS) and (
                function.name.startswith("test")
                or any(_is_fixture(one) for one in function.decorator_list)
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
            tree, _parents = self.parsed(place)
            for statement in tree.body:
                if (
                    isinstance(statement, _FUNCTIONS)
                    and statement.name == name
                    and any(_is_fixture(one) for one in statement.decorator_list)
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
            tree, _parents = self.parsed(relative)
            if name in self.bindings(tree):
                return self.lookup(name, [tree], relative, None)
        inner = f"{module.name}.{name}"
        if self.module_exists(inner):
            return Module(inner)
        if name == "__file__" and path is not None:
            return Place(path.relative_to(self.root).parts)
        if name == "__path__" and path is not None and path.name == "__init__.py":
            return Place(path.parent.relative_to(self.root).parts)
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
        tree, _parents = self.parsed(relative)
        entries = self.bindings(tree).get(name)
        if not entries or len(entries) != 1:
            return None
        return self._defined((0, entries[0]), relative, depth + 1)

    def _defined(
        self, found: tuple[int, tuple[str, object]] | None, relative: str, depth: int
    ) -> Definition | None:
        if found is None:
            return None
        kind, data = found[1]
        if kind == "def":
            return Definition(relative, data)  # type: ignore[arg-type]
        if kind == "value":
            _value, statement = data  # type: ignore[misc]
            return Definition(relative, statement)
        if kind == "from":
            statement, imported = data  # type: ignore[misc]
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
            texts = [part.value for part in node.values if isinstance(part, ast.Constant)]
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
            return choice(
                self.evaluate(item, scopes, relative, env)
                for item in node.elts
                if not isinstance(item, ast.Starred)
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
            if node.args and node.func.attr != "iterdir":
                found = self.pattern(node.args[0], scopes, relative, env)
                text = found if isinstance(found, str) else "*"
            parts = _pattern_parts(text, node.func.attr == "rglob")

            def found_paths(one: Value) -> Value:
                if isinstance(one, Outside):
                    return one
                return Place((*one.parts, *parts)) if isinstance(one, Place) else None

            return each(base, found_paths)
        value = self.evaluate(node, scopes, relative, env)
        if isinstance(node, ast.Tuple | ast.List | ast.Set) or isinstance(value, Choice):
            return value
        if isinstance(node, ast.Name) and isinstance(value, str | Place | Outside):
            # Ein Name, der an ein Tupel mit einem Element gebunden ist.
            return value if self._sequence_binding(node, scopes) else None
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
            value, _statement = found[1][1]  # type: ignore[misc]
            return value, scopes[found[0] :], relative  # type: ignore[return-value]
        definition = self.definition(relative, node)
        if definition is not None and isinstance(definition.node, ast.Assign | ast.AnnAssign):
            tree, _parents = self.parsed(definition.relative)
            return definition.node.value, [tree], definition.relative
        return None, scopes, relative

    def _sequence_binding(self, node: ast.Name, scopes: list[ast.AST]) -> bool:
        found = self.binding(node.id, scopes)
        if found is None or found[1][0] != "value":
            return False
        value, _statement = found[1][1]  # type: ignore[misc]
        return isinstance(value, ast.Tuple | ast.List | ast.Set)

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
        return None

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
        self, node: ast.expr, scopes: list[ast.AST], relative: str, env: Env | None = None
    ) -> Value:
        """Ein Muster als Text oder Wahl von Texten; offene Teile eines f-Strings werden ``*``,
        ohne mit einem Nachbarn ein ``**`` zu bilden, das jede Tiefe hieße."""
        if isinstance(node, ast.JoinedStr):
            text = "".join(
                str(part.value) if isinstance(part, ast.Constant) else "*" for part in node.values
            )
            return "/".join(
                part if part == "**" else re.sub(r"\*{2,}", "*", part) for part in text.split("/")
            )
        return self.evaluate(node, scopes, relative, env)

    def pattern_at(self, relative: str, node: ast.expr, env: Env | None = None) -> Value:
        _tree, parents = self.parsed(relative)
        return self.pattern(node, self.scopes(node, parents), relative, env)


def _is_fixture(decorator: ast.expr) -> bool:
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

#: Die letzten Namen aller Lesestellen; andere Aufrufe braucht :func:`sites` nicht aufzulösen.
_READ_NAMES = frozenset({*_PATH_READS, *(name.rsplit(".", 1)[1] for name in _FUNCTION_READS)})


@dataclass(frozen=True)
class Site:
    """Eine Lesestelle: der Aufruf, wie er liest, und was den Ordner bestimmt."""

    relative: str
    call: ast.Call
    how: str
    receiver: ast.expr | None
    pattern: ast.expr | None

    @property
    def where(self) -> str:
        return f"{self.relative}:{self.call.lineno}"


def _pattern_parts(text: str, recursive: bool) -> tuple[str, ...]:
    parts = tuple(part for part in text.replace("\\", "/").split("/") if part not in ("", "."))
    parts = parts or ("*",)
    return ("**", *parts) if recursive and parts[0] != "**" else parts


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
            pattern = node.args[0] if node.args and function.attr in ("glob", "rglob") else None
            found.append(Site(relative, node, function.attr, function.value, pattern))
            continue
        called = resolver.foreign(function, scopes, relative)
        if called is not None and called.name in _FUNCTION_READS:
            found.append(_function_site(relative, node, called.name))
    return found


def _is_module_or_definition(resolver: Resolver, node: ast.expr, scopes: list[ast.AST]) -> bool:
    """Ob der Empfänger ein eigenes Modul oder eine Definition ist — dann ist ``x.walk()`` ein
    Aufruf ins Modul, kein Pfad. Geprüft an der Bindung, ohne das Modul zu lesen."""
    if not isinstance(node, ast.Name):
        return False
    found = resolver.binding(node.id, scopes)
    return found is not None and found[1][0] in ("module", "def")


def _function_site(relative: str, node: ast.Call, name: str) -> Site:
    how, _recursive = _FUNCTION_READS[name]
    argument = node.args[0] if node.args else None
    if how == "packages" and argument is None:
        argument = next((one.value for one in node.keywords if one.arg == "path"), None)
    if how == "pattern":
        root_dir = next((one.value for one in node.keywords if one.arg == "root_dir"), None)
        return Site(relative, node, name, root_dir, argument)
    return Site(relative, node, name, argument, None)


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
