"""Wer eine Datei außerhalb des Codes über eine Einheit unter ``tests/`` liest — je Funktion.

Entscheidung des Koordinators zum Hinweis aus Review 2 („je lesender Funktion“): Für
``tests/data/meshes/plate_holes.stl`` wählte die Auswahl 289 Testdateien. Die Masse trugen
``tests/helpers.py`` — es nennt die Datei und ihren Ordner, also liefen seine 188 direkten
Importeure mit, und es liest sie, also alle mittelbaren dazu —, obwohl nur wenige seiner
Funktionen die Datei erreichen. Hier zählt die **Einheit** (Funktion, Methode, Klasse,
Zuweisung auf Modulebene, wie in :mod:`tools.tree_reads`), die die Datei erreicht, und die
Testdatei, die diese Einheit bezieht — mit den Werten ihrer Argumente an der Aufrufstelle.

Eine Einheit unter ``tests/`` erreicht die Datei ``F``

- über eine Zeichenkette, die ihren Namen trägt (``"plate_holes.stl"``, kein Docstring), oder
- über einen Pfadausdruck (``/``, ``Path(…)``, ``joinpath``, ``os.path.join``), der sich auf
  ``F`` oder ihren Ordner auflöst, oder der offen bleibt über ihrem Ordner oder eine Ebene
  darüber (``MESHES / name``) — dieselben Orte wie der Ordnerweg von ``affected_tests``; ein
  Pfad auf eine andere Datei im Ordner (``MESHES / "cube_clean.stl"``) erreicht ``F`` nicht —,
  oder
- über eine Lesestelle, deren Ordner und Muster ``F`` decken (:class:`tools.tree_reads.Read`).

Weitergegeben wird wie bei den Lesestellen über den Namen einer Einheit, nicht über einen
Namen, der selbst Grundlage eines Pfadausdrucks oder einer Lesestelle ist — der Ausdruck
entscheidet dort mit seinem Wert. Eine Testdatei bezieht außerdem, was eine Fixture liest, die
eine ihrer Funktionen beim Namen anfordert (Parameter, ``usefixtures``): aus derselben Datei,
importiert oder aus einer ``conftest.py``. Was die Modulebene eines Helfers beim Import liest,
liest jeder, der ihn mittelbar importiert; was eine autouse-Fixture einer ``conftest.py`` liest,
jede Testdatei unter ihr.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import replace
from pathlib import Path, PurePosixPath

from tools import tree_reads
from tools.tree_reads import Borrowed, Definition, Env, Facts, Place, Read, Site

#: Aufrufe, deren Ergebnis ein Pfad aus ihren Argumenten ist.
_PATH_CALLS = frozenset({"Path", "PurePath", "PurePosixPath", "join"})

#: Ordner, deren Dateien kein Ordnerweg erreicht: An der Wurzel und unter ``website/``
#: liegt alles nebeneinander, und wer den Ordner nennt, liest damit nicht jede Datei darin
#: (wie ``affected_tests._named_readers``); Lesestellen und Nennungen gelten weiter.
_WIDE_FOLDERS = frozenset({(), ("website",)})

#: Wo die Einheiten liegen, die diese Leser je Funktion verfolgen.
_SCOPE = "tests/"


def is_path_expression(node: ast.AST) -> bool:
    """``a / b``, ``Path(…)``, ``os.path.join(…)``, ``x.joinpath(…)``."""
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, ast.Div)
    if not isinstance(node, ast.Call):
        return False
    function = node.func
    if isinstance(function, ast.Attribute):
        return function.attr in ("joinpath", "join") or function.attr in _PATH_CALLS
    return isinstance(function, ast.Name) and function.id in _PATH_CALLS


def _base(node: ast.expr) -> ast.expr | None:
    """Wovon ein Pfadausdruck ausgeht: links von ``/``, der Empfänger von ``joinpath``, das
    erste Argument von ``Path(…)``."""
    if isinstance(node, ast.BinOp):
        return node.left
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "joinpath":
            return node.func.value
        return node.args[0] if node.args else None
    return None


class DataReads(tree_reads.TreeReads):
    """Welche Testdatei die Datei ``file`` über welche Einheit unter ``tests/`` erreicht."""

    def __init__(
        self,
        root: Path,
        modules: Mapping[str, Path],
        importers: Mapping[str, Iterable[str]],
        resolver: tree_reads.Resolver,
        file: PurePosixPath,
        facts: Facts | None = None,
    ) -> None:
        self.file = file
        words = [part for part in (file.parent.name, file.parent.parent.name) if part]
        #: Woran eine Datei unter ``tests/`` ``file`` selbst erreichen kann: ihr Name, ihr
        #: Ordner oder der darüber zwischen Anführungszeichen oder Schrägstrichen.
        self._mention = re.compile(
            "|".join([re.escape(file.name)] + [f"[\"'/]{re.escape(word)}[\"'/]" for word in words])
        )
        shared = facts or Facts()
        # Die Stellen je Einheit sind hier andere als bei den Lesestellen allein; der Rest gilt
        # je Datei gleich und wird geteilt.
        own = Facts(
            sites={},
            refs=shared.refs,
            by_name=shared.by_name,
            words=shared.words,
            defined=shared.defined,
            importers=shared.importers,
        )
        self._covered: dict[str, set[int]] = {}
        #: Ob ein Pfad auf den Ordner oder ein Text, der ihn nennt, die Datei erreicht.
        self._by_folder = file.parent.parts not in _WIDE_FOLDERS
        #: Wie eine Nennung im Grund heißt, je Stelle und je Lesung, die sie ergab.
        self._labels: dict[int, str] = {}
        self._naming: dict[int, tuple[Read, str]] = {}
        #: Testdateien, die eine lesende Fixture beim Namen anfordern (:meth:`readers`).
        self._requesting: set[str] = set()
        super().__init__(root, modules, importers, resolver, python_only=False, facts=own)

    # Haken -------------------------------------------------------------------------

    def _may_read(self, relative: str, text: str) -> bool:
        if tree_reads.READ_WORDS.search(text) is not None or relative in self._requesting:
            return True
        return relative.startswith(_SCOPE) and self._mention.search(text) is not None

    def _sites_by_unit(self, relative: str) -> dict[ast.AST | None, list[Site]]:
        if relative not in self._sites:
            grouped: dict[ast.AST | None, list[Site]] = defaultdict(list)
            text = self.texts.get(relative, "")
            if tree_reads.READ_WORDS.search(text) or relative.startswith(_SCOPE):
                _tree, parents = self.resolver.parsed(relative)
                covered: set[int] = set()
                if tree_reads.READ_WORDS.search(text):
                    for site in tree_reads.sites(self.resolver, relative):
                        grouped[tree_reads.owner(site.call, parents)].append(site)
                        covered.update(id(one) for one in ast.walk(site.call))
                if relative.startswith(_SCOPE):
                    for site in self._touches(relative):
                        grouped[tree_reads.owner(site.call, parents)].append(site)
                        covered.update(id(one) for one in ast.walk(site.call))
                self._covered[relative] = covered
            self._sites[relative] = grouped
        return self._sites[relative]

    def _touches(self, relative: str) -> Iterator[Site]:
        """Die Stellen einer Datei, an denen sie ``file`` erreichen kann: Nennungen und die
        äußersten Pfadausdrücke."""
        tree, parents = self.resolver.parsed(relative)
        name = self.file.name
        folder = self.file.parent
        mentioned = self._mention.search(self.texts.get(relative, "")) is not None
        # Docstrings nennen nichts; der Gang in Breite sieht die Anweisung vor ihrem Text.
        skipped: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                skipped.add(id(node.value))
            elif (
                mentioned
                and isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in skipped
            ):
                if name in node.value:
                    self._labels[id(node)] = f"nennt {name}"
                    yield Site(relative, node, "nennt", None, None)
                elif self._by_folder and names_folder(node.value, folder):
                    self._labels[id(node)] = f"nennt den Ordner {folder}/"
                    yield Site(relative, node, "nennt", None, None)
            elif is_path_expression(node):
                assert isinstance(node, ast.expr)
                parent = parents.get(node)
                if (
                    isinstance(parent, ast.expr)
                    and is_path_expression(parent)
                    and _base(parent) is node
                ):
                    continue  # ein Glied des äußeren Ausdrucks
                yield Site(relative, node, "Pfad", None, None)

    def _evaluate_site(self, site: Site, env: Env | None) -> list[Read]:
        if site.how == "nennt":
            read = self._at_file(site)
            self._naming[id(read)] = (read, self._labels[id(site.call)])
            return [read]
        if site.how != "Pfad":
            # Eine Lesestelle zählt hier nur, wenn sie die Datei decken kann: Die übrigen —
            # ``*.py`` über die Quellen — wählt :attr:`affected_tests.ImportGraph.all_reads`, und
            # hier markierten sie nur Einheiten, deren Lesungen die Datei nie erreichen.
            return [
                read
                for read in super()._evaluate_site(site, env)
                if read.covers(self.file)
                or (read.folder is None and tree_reads.matches(self.file.name, read.pattern[-1]))
            ]
        resolver = self.resolver
        _tree, parents = resolver.parsed(site.relative)
        scopes = resolver.scopes(site.call, parents)
        folder = self.file.parent.parts
        found: list[Read] = []
        for value in tree_reads.options(resolver.evaluate(site.call, scopes, site.relative, env)):
            if isinstance(value, Place):
                if value.parts == self.file.parts:
                    found.append(self._at_file(site))
                elif value.parts == folder and self._by_folder:
                    found.append(self._in_folder(site))
                continue
            if value is not None:
                continue  # draußen
            base = _base(site.call)
            left = None if base is None else resolver.evaluate(base, scopes, site.relative, env)
            if (
                self._by_folder
                and isinstance(left, Place)
                and len(folder) - 1 <= len(left.parts) <= len(folder)
            ):
                if folder[: len(left.parts)] == left.parts:
                    found.append(self._in_folder(site))
            elif left is None and env is None:
                # Offen ohne Aufrufstelle: Ein Parameter kann dort zum Ordner werden. Die
                # Lesung markiert die Einheit und deckt nichts (``Read.covers``).
                found.append(Read(None, (self.file.name,), site.where))
        return found

    def reason(self, hits: list[Borrowed]) -> tuple[str, Borrowed]:
        """Wie die Lesungen einer Testdatei im Grund heißen, und welche ihn trägt: die erste,
        die liest, sonst die erste Nennung (``nennt plate_holes.stl``)."""
        for one in hits:
            if self._naming.get(id(one.read), (None, ""))[0] is not one.read:
                return f"liest {one.read.describe()}", one
        return self._naming[id(hits[0].read)][1], hits[0]

    def readers(self, tests: Iterable[str]) -> dict[str, list[Borrowed]]:
        """Wie bei den Lesestellen, dazu jede Testdatei, die eine lesende Fixture beim Namen
        trägt — sie hat sonst keine Einheit, die liest."""
        wanted = list(tests)
        fixtures = {
            unit.name
            for unit in self.reading
            if isinstance(unit, ast.FunctionDef | ast.AsyncFunctionDef)
            and any(tree_reads.is_fixture(one) for one in unit.decorator_list)
        }
        self._requesting = {one for one in wanted if self._words(one) & fixtures}
        holders = set(self.reading.values()) | self.touched | self._requesting
        found: dict[str, list[Borrowed]] = {}
        for relative in wanted:
            # Eine Lesestelle der Datei selbst ohne Einheit wählt ``all_reads``.
            if relative not in holders and not (
                relative.startswith(_SCOPE) and self._mention.search(self.texts.get(relative, ""))
            ):
                continue
            reads = list(
                dict.fromkeys(
                    one
                    for one in self.test_reads(relative)
                    if not isinstance(one.read.folder, tree_reads.Outside)
                )
            )
            if reads:
                found[relative] = reads
        return found

    def _in_folder(self, site: Site) -> Read:
        """Ein Pfad auf den Ordner oder offen darin: jede Datei des Ordners."""
        return Read(Place(self.file.parent.parts), ("*",), site.where)

    def _at_file(self, site: Site) -> Read:
        return Read(Place(self.file.parent.parts), (self.file.name,), site.where)

    def _lends(self, relative: str, node: ast.expr) -> bool:
        self._sites_by_unit(relative)
        return id(node) not in self._covered.get(relative, set())

    # Testdateien -------------------------------------------------------------------

    def test_reads(self, relative: str) -> list[Borrowed]:
        """Wie bei den Lesestellen, dazu was die Fixtures lesen, die eine Funktion der Datei
        beim Namen anfordert."""
        found = super().test_reads(relative)
        tree = self.resolver.tree(relative)
        for statement in tree.body:
            units: list[tuple[str, ast.AST]] = []
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
                units.append((statement.name, statement))
            elif isinstance(statement, ast.ClassDef):
                units.append((statement.name, statement))
                units.extend(
                    (statement.name, inner)
                    for inner in statement.body
                    if isinstance(inner, ast.FunctionDef | ast.AsyncFunctionDef)
                )
            elif isinstance(statement, ast.Assign) and any(
                isinstance(one, ast.Name) and one.id == "pytestmark" for one in statement.targets
            ):
                units.append(("", statement))  # ``pytestmark`` gilt für jeden Fall
            for unit, function in units:
                for name in _requested(function):
                    found.extend(
                        replace(one, unit=unit) for one in self.fixture_reads(relative, name, set())
                    )
        return found

    def fixture_reads(self, relative: str, name: str, seen: set[tuple[str, int]]) -> list[Borrowed]:
        """Was die Fixture ``name`` liest, die eine Funktion in ``relative`` anfordert — samt der
        Fixtures, die sie selbst anfordert."""
        found: list[Borrowed] = []
        for definition in self._fixtures(relative, name):
            key = (definition.relative, id(definition.node))
            if key in seen:
                continue
            seen.add(key)
            node = definition.node
            if node in self.reading:
                found.extend(self.unit_reads(definition.relative, node, None))
            for inner in _requested(node):
                found.extend(self.fixture_reads(definition.relative, inner, seen))
        return found

    def _fixtures(self, relative: str, name: str) -> list[Definition]:
        """Die Fixtures ``name``, die eine Funktion in ``relative`` bekommen kann: aus der Datei
        selbst, beim Namen importiert, und aus jeder ``conftest.py`` darüber."""
        found: list[Definition] = []
        places = [relative, *_conftests(relative)]
        for place in places:
            if place not in self.texts and not (self.root / place).is_file():
                continue
            tree = self.resolver.tree(place)
            for statement in tree.body:
                if (
                    isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef)
                    and statement.name == name
                    and any(tree_reads.is_fixture(one) for one in statement.decorator_list)
                ):
                    found.append(Definition(place, statement))
        definition = self.resolver.module_definition(self.resolver.module_name(relative), name, 0)
        if definition is not None and definition.relative != relative:
            found.append(definition)
        return found

    def autouse_reads(self, conftest: str) -> list[Borrowed]:
        """Was die autouse-Fixtures einer ``conftest.py`` lesen — jede Testdatei darunter."""
        tree = self.resolver.tree(conftest)
        found: list[Borrowed] = []
        for statement in tree.body:
            if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef) and is_autouse(
                statement
            ):
                found.extend(self.fixture_reads(conftest, statement.name, set()))
        return found

    def import_time(self, relative: str) -> list[Borrowed]:
        """Was die Modulebene eines Helfers beim Import liest: Stellen außerhalb jeder Einheit
        und Zuweisungen, deren Wert mehr ist als ein Pfad (``TABLE = load(DATA / "x.json")``)."""
        found = list(self.unit_reads(relative, None, None))
        for statement in self.resolver.tree(relative).body:
            if (
                isinstance(statement, ast.Assign | ast.AnnAssign)
                and statement.value is not None
                and not _only_a_path(statement.value)
            ):
                found.extend(self.unit_reads(relative, statement, None))
        return found


def names_folder(text: str, folder: PurePosixPath) -> bool:
    """Ob ein Text den Ordner nennt: ``"knowledge/data/"`` für ``app/core/knowledge/data``, die
    Teile vor dem Namen passend; ein bloßer Name nur für einen Ordner unter der Wurzel — ein
    ``"data"`` als Schlüssel liest nichts (RQ-5)."""
    parts = [part for part in re.split(r"[\\/]", text) if part not in ("", ".")]
    if not folder.parts or folder.name not in parts:
        return False
    before = tuple(parts[: parts.index(folder.name)])
    if before:
        return folder.parts[:-1][-len(before) :] == before
    return len(folder.parts) == 1


def _only_a_path(node: ast.expr) -> bool:
    """Ob ein Wert nur einen Pfad baut, ohne etwas zu lesen: ``ROOT / "data"``, ein Tupel
    davon, eine Konstante, ein Name."""
    if isinstance(node, ast.Constant | ast.Name | ast.Attribute):
        return True
    if isinstance(node, ast.Tuple | ast.List):
        return all(_only_a_path(one) for one in node.elts)
    if is_path_expression(node):
        base = _base(node)
        rest = (
            [node.right]
            if isinstance(node, ast.BinOp)
            else [one for one in getattr(node, "args", []) if one is not base]
        )
        return all(_only_a_path(one) for one in [*(() if base is None else (base,)), *rest])
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        # ``Path(__file__).resolve().parent``
        return node.func.attr in ("resolve", "absolute") and _only_a_path(node.func.value)
    return False


def _requested(node: ast.AST) -> list[str]:
    """Die Fixtures, die eine Funktion, eine Klasse oder ``pytestmark`` anfordert: Parameter,
    ``usefixtures("…")`` und ``request.getfixturevalue("…")``."""
    names: list[str] = []
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        arguments = node.args
        names.extend(
            one.arg for one in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)
        )
    if isinstance(node, ast.ClassDef):
        calls: list[ast.AST] = list(node.decorator_list)  # die Methoden zählen einzeln
    else:
        calls = list(ast.walk(node))
    for call in calls:
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr in ("usefixtures", "getfixturevalue")
        ):
            names.extend(
                one.value
                for one in call.args
                if isinstance(one, ast.Constant) and isinstance(one.value, str)
            )
    return names


def is_autouse(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """``@pytest.fixture(autouse=True)`` — eine Fixture, die jeder Test unter ihr bekommt."""
    return any(
        isinstance(decorator, ast.Call)
        and tree_reads.is_fixture(decorator)
        and any(
            one.arg == "autouse" and isinstance(one.value, ast.Constant) and one.value.value is True
            for one in decorator.keywords
        )
        for decorator in function.decorator_list
    )


def _conftests(relative: str) -> list[str]:
    """Jede ``conftest.py`` über einer Datei, innen zuerst, bis zur Wurzel."""
    found: list[str] = []
    folder = PurePosixPath(relative).parent
    while True:
        found.append((folder / "conftest.py").as_posix() if folder.parts else "conftest.py")
        if not folder.parts:
            return found
        folder = folder.parent
