"""W4: Quelltextprüfungen lesen rekursiv (Konzept Codestruktur 4.1, Plan Schritt 0, 2.4).

**Warum es diese Datei gibt.** Die Verbotsprüfungen über ``app/ui``,
``perceive``, ``agent`` und ``activation`` lasen über ein flaches
``glob("*.py")`` und sahen damit kein Unterpaket — ``app/ui/render/`` lag
außerhalb jeder Prüfung über die Oberfläche, und nach dem ersten Schnitt, der
eine Datei zum Paket macht, wären es die größten Dateien gewesen (CS-2). Ihre
Gegenproben zählten nur Dateien und wären dabei grün geblieben (CS-12).

Drei Teile halten das:

- **Der Helfer** ``tests/source_tree.py`` liest rekursiv, sortiert und nie
  leer und findet Definitionsdateien statisch, auch in einer Kopie des Baums.
- **Der Wächter** liest ``tests/`` und ``tools/`` und verbietet jedes flache
  ``glob`` auf ``*.py``, dessen Ordner nicht statisch ``tests/`` oder
  ``tools/`` ist — beide bleiben nach Konzept 3.4 flach. Ein Ordner, der sich
  nicht auflösen lässt (Parameter, ``tmp_path``, Arbeitsordner), ist rot; der
  Fix ist der Helfer oder ``rglob``, eine Ausnahmeliste gibt es nicht.
- **Die Gegenproben im Unterpaket:** Jede umgestellte Prüfung wird an einer
  Kopie des Baums gefahren, in deren Unterpaket ein Verstoß liegt, und muss
  ihn mit seinem Dateinamen melden.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import re
import shutil
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import pytest

from tests import source_tree

# --- Der Helfer -----------------------------------------------------------------


def _write(root: Path, relative: str, text: str = "") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_the_helper_reads_subpackages_sorted_and_never_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rekursiv, sortiert, ohne Bytecode-Ordner — und ein leerer Ordner ist ein Fehler."""
    top = _write(tmp_path, "pkg/top.py")
    inner = _write(tmp_path, "pkg/inner/deep.py")
    _write(tmp_path, "pkg/__pycache__/stale.py")
    _write(tmp_path, "pkg/notes.txt")
    (tmp_path / "empty").mkdir()
    monkeypatch.setattr(source_tree, "ROOT", tmp_path)

    assert source_tree.python_files("pkg") == [inner, top]
    assert source_tree.relative(inner) == "pkg/inner/deep.py"
    with pytest.raises(AssertionError, match="keine Python-Datei"):
        source_tree.python_files("empty")


def test_the_helper_finds_the_definition_modules_where_the_import_finds_them() -> None:
    """``MainWindow``, ``Viewport`` und die Merkmalserkennung, gegen den Import gehalten.

    Der Sollwert kommt von außen: ``inspect`` nennt die Datei, aus der Python
    die Definition lädt. Zieht ein Schnitt sie in ein Unterpaket, ändert sich
    nur der Import, nicht diese Zusicherung (RM-729).
    """
    from app.core.perceive.features import detect
    from app.ui.main_window import MainWindow
    from app.ui.viewport import Viewport

    for definition, folder in (
        (MainWindow, "app/ui"),
        (Viewport, "app/ui"),
        (detect, "app/core/perceive"),
    ):
        loaded = Path(inspect.getsourcefile(definition) or "").resolve()
        assert source_tree.definition_file(definition.__name__, folder) == loaded


def test_an_ambiguous_or_missing_definition_is_an_error() -> None:
    """``detect`` gibt es dreimal unter ``app/`` — der Helfer rät nicht, er nennt sie."""
    with pytest.raises(AssertionError, match=r"app/core/perceive/features\.py"):
        source_tree.definition_file("detect")
    with pytest.raises(AssertionError, match="0-mal"):
        source_tree.definition_file("NothingIsCalledLikeThis", "app/ui")


def test_a_definition_inside_a_string_or_a_class_does_not_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gezählt wird die Modulebene des Syntaxbaums, nicht eine Zeile, die so aussieht."""
    _write(tmp_path, "pkg/text.py", 'DOC = """\nclass Probe:\n    pass\n"""\n')
    _write(tmp_path, "pkg/nested.py", "class Outer:\n    class Probe:\n        pass\n")
    real = _write(tmp_path, "pkg/real.py", "async def Probe():\n    pass\n")
    monkeypatch.setattr(source_tree, "ROOT", tmp_path)

    assert source_tree.definition_file("Probe", "pkg") == real


# --- Der Wächter: kein flaches glob über ein Paket --------------------------------

#: Konstruktoren, deren erstes Argument ein Pfad ist.
_PATH_TYPES = frozenset(
    {"Path", "PurePath", "PosixPath", "WindowsPath", "PurePosixPath", "PureWindowsPath"}
)

#: Die Ordner, die flach bleiben (Konzept 3.4) und deshalb flach gelesen werden dürfen.
_FLAT_FOLDERS = frozenset({"tests", "tools"})

_SCOPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


@dataclass(frozen=True)
class _Module:
    """Ein Modul oder Paket unter der Wurzel, als Punktname."""

    name: str


@dataclass(frozen=True)
class _Place:
    """Ein Ort relativ zur Wurzel."""

    parts: tuple[str, ...]


_Value = _Module | _Place | str | None


@dataclass(frozen=True)
class _Glob:
    """Ein flaches ``glob`` auf ``*.py``: wo es steht und welchen Ordner es liest."""

    where: str
    line: int
    folder: str | None
    pattern: str


class _Resolver:
    """Löst Ordnerausdrücke statisch auf: ``Path(__file__)``-Ketten, ``ROOT / "…"``,
    ``Path(M.__file__)``, Konstanten der Modul- und Funktionsebene, Importe aus
    eigenen Modulen. Was sich nicht eindeutig auflösen lässt, ist ``None``.

    Ein Name gilt in dem Bereich, in dem er gebunden ist, so wie Python ihn
    sucht: Funktion, umgebende Funktionen, Modul; ein Klassenrumpf nur für
    Code direkt darin. Mehr als eine Bindung oder eine Bindung ohne Wert
    (Parameter, Schleife, ``with``) heißt „nicht auflösbar“.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._trees: dict[str, tuple[ast.Module, dict[ast.AST, ast.AST]]] = {}
        self._bindings: dict[ast.AST, dict[str, list[tuple[str, object]]]] = {}
        self._busy: set[tuple[int, str]] = set()

    # Module ---------------------------------------------------------------------

    def module_path(self, name: str) -> Path | None:
        base = self.root.joinpath(*name.split("."))
        if (base / "__init__.py").is_file():
            return base / "__init__.py"
        if base.with_suffix(".py").is_file():
            return base.with_suffix(".py")
        return None

    def module_exists(self, name: str) -> bool:
        return self.module_path(name) is not None or self.root.joinpath(*name.split(".")).is_dir()

    def parsed(self, relative: str) -> tuple[ast.Module, dict[ast.AST, ast.AST]]:
        if relative not in self._trees:
            tree = ast.parse((self.root / relative).read_text(encoding="utf-8"), filename=relative)
            parents = {
                child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
            }
            self._trees[relative] = (tree, parents)
        return self._trees[relative]

    @staticmethod
    def module_name(relative: str) -> str:
        parts = list(PurePosixPath(relative).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    # Bereiche -------------------------------------------------------------------

    def scopes(self, node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.AST]:
        """Die Bereiche, in denen ein Name an ``node`` gesucht wird, innen zuerst."""
        found: list[ast.AST] = []
        current = parents.get(node)
        in_function = False
        while current is not None:
            if isinstance(current, _SCOPES):
                found.append(current)
                in_function = in_function or not isinstance(
                    current, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
                )
            elif isinstance(current, ast.Module) or (
                isinstance(current, ast.ClassDef) and not in_function
            ):
                found.append(current)
            current = parents.get(current)
        return found

    def bindings(self, scope: ast.AST) -> dict[str, list[tuple[str, object]]]:
        if scope in self._bindings:
            return self._bindings[scope]
        found: dict[str, list[tuple[str, object]]] = defaultdict(list)
        if isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            arguments = scope.args
            for argument in (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
                *(one for one in (arguments.vararg, arguments.kwarg) if one is not None),
            ):
                found[argument.arg].append(("unknown", None))
        if isinstance(scope, ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp):
            for generator in scope.generators:
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
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found[node.name].append(("unknown", None))
            return
        if isinstance(node, _SCOPES):
            return
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id].append(("value", node.value))
                else:
                    for name in _target_names(target):
                        found[name].append(("unknown", None))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found[node.target.id].append(("value", node.value) if node.value else ("unknown", None))
        elif isinstance(node, ast.AugAssign | ast.For | ast.AsyncFor):
            for name in _target_names(node.target):
                found[name].append(("unknown", None))
        elif isinstance(node, ast.NamedExpr):
            found[node.target.id].append(("unknown", None))
        elif isinstance(node, ast.With | ast.AsyncWith):
            for item in node.items:
                if item.optional_vars is not None:
                    for name in _target_names(item.optional_vars):
                        found[name].append(("unknown", None))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            found[node.name].append(("unknown", None))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    found[alias.asname].append(("module", alias.name))
                else:
                    head = alias.name.split(".")[0]
                    found[head].append(("module", head))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                found[alias.asname or alias.name].append(("from", (node, alias.name)))
        for child in ast.iter_child_nodes(node):
            self._bind(child, found)

    # Werte ----------------------------------------------------------------------

    def lookup(self, name: str, scopes: list[ast.AST], relative: str) -> _Value:
        for index, scope in enumerate(scopes):
            entries = self.bindings(scope).get(name)
            if not entries:
                continue
            if len(entries) != 1:
                return None
            kind, data = entries[0]
            if kind == "value":
                key = (id(data), relative)
                if key in self._busy:
                    return None
                self._busy.add(key)
                try:
                    return self.evaluate(data, scopes[index:], relative)  # type: ignore[arg-type]
                finally:
                    self._busy.discard(key)
            if kind == "module":
                return _Module(str(data)) if self.module_exists(str(data)) else None
            if kind == "from":
                statement, imported = data  # type: ignore[misc]
                return self.imported(statement, imported, relative)
            return None
        if name == "__file__":
            return _Place(PurePosixPath(relative).parts)
        return None

    def imported(self, statement: ast.ImportFrom, name: str, relative: str) -> _Value:
        if statement.level:
            package = self.module_name(relative).split(".")
            if not relative.endswith("__init__.py"):
                package = package[:-1]
            package = package[: len(package) - (statement.level - 1)]
            source = ".".join([*package, statement.module] if statement.module else package)
        else:
            source = statement.module or ""
        return self.attribute(_Module(source), name) if self.module_exists(source) else None

    def attribute(self, module: _Module, name: str) -> _Value:
        path = self.module_path(module.name)
        if path is not None:
            relative = path.relative_to(self.root).as_posix()
            tree, _parents = self.parsed(relative)
            if name in self.bindings(tree):
                return self.lookup(name, [tree], relative)
        inner = f"{module.name}.{name}"
        return _Module(inner) if self.module_exists(inner) else None

    def evaluate(self, node: ast.expr, scopes: list[ast.AST], relative: str) -> _Value:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return self.lookup(node.id, scopes, relative)
        if isinstance(node, ast.Call):
            function = node.func
            called = function.id if isinstance(function, ast.Name) else None
            if isinstance(function, ast.Attribute):
                if function.attr in ("resolve", "absolute") and not node.args:
                    value = self.evaluate(function.value, scopes, relative)
                    return value if isinstance(value, _Place) else None
                called = function.attr
            if called in _PATH_TYPES and len(node.args) == 1 and not node.keywords:
                value = self.evaluate(node.args[0], scopes, relative)
                # Ein Text als Pfad hängt am Arbeitsordner — nicht auflösbar.
                return value if isinstance(value, _Place) else None
            return None
        if isinstance(node, ast.Attribute):
            value = self.evaluate(node.value, scopes, relative)
            if isinstance(value, _Place) and node.attr == "parent":
                return _Place(value.parts[:-1]) if value.parts else None
            if isinstance(value, _Module):
                if node.attr == "__file__":
                    path = self.module_path(value.name)
                    return _Place(path.relative_to(self.root).parts) if path else None
                return self.attribute(value, node.attr)
            return None
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "parents"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, int)
        ):
            value = self.evaluate(node.value.value, scopes, relative)
            depth = node.slice.value + 1
            if isinstance(value, _Place) and 0 < depth <= len(value.parts):
                return _Place(value.parts[:-depth])
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left = self.evaluate(node.left, scopes, relative)
            right = self.evaluate(node.right, scopes, relative)
            if isinstance(left, _Place) and isinstance(right, str):
                return _joined(left, right)
        return None


def _target_names(target: ast.AST) -> Iterator[str]:
    for node in ast.walk(target):
        if isinstance(node, ast.Name):
            yield node.id


def _joined(place: _Place, text: str) -> _Place | None:
    parts = list(place.parts)
    for part in PurePosixPath(text.replace("\\", "/")).parts:
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part not in ("", "."):
            parts.append(part)
    return _Place(tuple(parts))


def _pattern(node: ast.expr) -> str | None:
    """Das Muster eines Globs als Text; Platzhalter eines f-Strings werden ``{}``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value if isinstance(part, ast.Constant) else "{}" for part in node.values
        )
    return None


#: Ein Muster, das Python-Quellen meint: ``*.py``, ``test_*.py``, ``*.pyi``, ``*.py*``.
_SOURCE_PATTERN = re.compile(r"\.pyi?\*?$")


def flat_globs(root: Path, relative: str, resolver: _Resolver | None = None) -> list[_Glob]:
    """Jedes ``glob`` auf Python-Quellen ohne ``**`` in einer Datei, mit dem Ordner, den es
    liest.

    Gesucht werden ``<pfad>.glob(…)`` und das Modul ``glob`` (``glob.glob``,
    ``glob.iglob``, ``from glob import glob``); dieses liest relativ zum
    Arbeitsordner und ist damit nie auflösbar. Ein Verzeichnisteil im Muster
    gehört zum Ordner.
    """
    resolver = resolver or _Resolver(root)
    tree, parents = resolver.parsed(relative)
    found: list[_Glob] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        pattern = _pattern(node.args[0])
        if pattern is None or not _SOURCE_PATTERN.search(pattern) or "**" in pattern:
            continue
        function = node.func
        through_module = (
            isinstance(function, ast.Attribute)
            and function.attr in ("glob", "iglob")
            and isinstance(function.value, ast.Name)
            and function.value.id == "glob"
        ) or (isinstance(function, ast.Name) and function.id in ("glob", "iglob"))
        if through_module:
            receiver: _Value = None
        elif isinstance(function, ast.Attribute) and function.attr == "glob":
            receiver = resolver.evaluate(function.value, resolver.scopes(node, parents), relative)
        else:
            continue
        folder = None
        directory = PurePosixPath(pattern).parent.as_posix()
        if isinstance(receiver, _Place) and not any(mark in directory for mark in "*?[{"):
            place = _joined(receiver, directory)
            folder = "/".join(place.parts) if place is not None else None
        found.append(_Glob(f"{relative}:{node.lineno}", node.lineno, folder, pattern))
    return found


def _sources_with_globs(root: Path, folders: tuple[str, ...]) -> list[str]:
    """Die Dateien unter ``folders``, in denen überhaupt ein ``glob(`` steht — der Rest
    braucht keinen Syntaxbaum (Plan 4, Laufzeit)."""
    mention = re.compile(r"\bi?glob\s*\(")
    return [
        path.relative_to(root).as_posix()
        for folder in folders
        for path in sorted((root / folder).rglob("*.py"))
        if "__pycache__" not in path.parts and mention.search(path.read_text(encoding="utf-8"))
    ]


def test_no_source_check_reads_a_package_flat() -> None:
    """W4 am Bestand: In ``tests/`` und ``tools/`` liest kein flaches ``glob`` über einen
    anderen Ordner als diese beiden.

    Die Grundmenge ist nicht leer und enthält bekannte erlaubte Stellen: Wer
    sie nicht mehr sieht, hat den Auflöser zerbrochen, nicht den Bestand
    bereinigt.
    """
    root = source_tree.ROOT
    resolver = _Resolver(root)
    globs = [
        one
        for relative in _sources_with_globs(root, ("tests", "tools"))
        for one in flat_globs(root, relative, resolver)
    ]
    flat = [f"{one.where}  {one.pattern!r} liest {one.folder or 'Unauflösbares'}" for one in globs]
    red = [line for one, line in zip(globs, flat, strict=True) if one.folder not in _FLAT_FOLDERS]
    assert not red, (
        "flaches glob über einen Ordner außer tests/ und tools/ — "
        "source_tree.python_files oder rglob nehmen:\n" + "\n".join(red)
    )
    allowed = {one.where.rsplit(":", 1)[0] for one in globs}
    assert {
        "tools/affected_tests.py",
        "tools/run_suite_isolated.py",
        "tests/test_toolchain.py",
        "tests/test_language_rules.py",
        "tests/test_function_guard.py",
    } <= allowed, f"bekannte erlaubte Stellen fehlen in der Grundmenge: {sorted(allowed)}"


#: Die synthetische Testquelle: jede Zeile mit einem Glob trägt ihr Urteil.
_PROBE_TEST = """\
from pathlib import Path

import app.ui
from tools.probe_root import ROOT

HERE = Path(__file__).resolve().parent
UI = ROOT / "app" / "ui"
TOOLS = HERE.parent / "tools"
TWICE = HERE
TWICE = UI


def surface():
    return sorted(UI.glob("*.py"))  # rot


def own_folder():
    return sorted(HERE.glob("test_*.py"))  # grün


def tool_folder():
    return sorted(TOOLS.glob("*.py"))  # grün


def package_file():
    return sorted(Path(app.ui.__file__).parent.glob("*.py"))  # rot


def folder_in_the_pattern():
    return sorted(Path(__file__).resolve().parents[1].glob("app/ui/*.py"))  # rot


def tests_in_the_pattern():
    return sorted(Path(__file__).resolve().parents[1].glob("tests/test_*.py"))  # grün


def parameter(folder):
    return sorted(folder.glob("*.py"))  # rot


def temporary(tmp_path):
    return sorted(tmp_path.glob("*.py"))  # rot


def working_directory():
    return sorted(Path("app/ui").glob("*.py"))  # rot


def glob_module():
    import glob

    return glob.glob("tests/*.py")  # rot


def bound_twice():
    return sorted(TWICE.glob("*.py"))  # rot


def f_string_here(name):
    return sorted(HERE.glob(f"{name}*.py"))  # grün


def f_string_surface(name):
    return sorted(UI.glob(f"{name}*.py"))  # rot


def local_shadow():
    UI = HERE
    return sorted(UI.glob("*.py"))  # grün


def comprehension():
    return [path for UI in (HERE,) for path in UI.glob("*.py")]  # rot


def recursive():
    return sorted(UI.rglob("*.py")), sorted(UI.glob("**/*.py")), sorted(UI.glob("*.txt"))
"""

#: Ein Werkzeug mit eigener Wurzel und relativem Import.
_PROBE_TOOL = """\
from pathlib import Path

from .probe_root import ROOT as BASE

APP = Path(__file__).resolve().parent.parent / "app"


def own():
    return sorted(BASE.joinpath("tools").glob("*.py"))  # rot


def tools_flat():
    return sorted((BASE / "tools").glob("*.py"))  # grün


def app_flat():
    return sorted(APP.glob("*.py"))  # rot


def stubs_flat():
    return sorted(APP.glob("*.pyi"))  # rot


def tool_sources_flat():
    return sorted((BASE / "tools").glob("*.py*"))  # grün
"""


@pytest.fixture
def probe_tree(tmp_path: Path) -> Path:
    _write(tmp_path, "app/__init__.py")
    _write(tmp_path, "app/ui/__init__.py")
    _write(tmp_path, "app/ui/render/__init__.py")
    _write(
        tmp_path,
        "tools/probe_root.py",
        "from pathlib import Path\n\nROOT = Path(__file__).resolve().parent.parent\n",
    )
    _write(tmp_path, "tests/test_probe.py", _PROBE_TEST)
    _write(tmp_path, "tools/probe_tool.py", _PROBE_TOOL)
    return tmp_path


def _verdicts(root: Path, relative: str) -> tuple[set[int], set[int]]:
    marks = (root / relative).read_text(encoding="utf-8").splitlines()
    red = {number for number, line in enumerate(marks, 1) if line.endswith("# rot")}
    green = {number for number, line in enumerate(marks, 1) if line.endswith("# grün")}
    return red, green


@pytest.mark.parametrize("relative", ["tests/test_probe.py", "tools/probe_tool.py"])
def test_the_flat_glob_guard_sees_every_form(probe_tree: Path, relative: str) -> None:
    """Gegenprobe des Wächters: Jede rote Zeile der Attrappe ist rot, jede grüne grün,
    und rekursive oder fremde Muster zählen gar nicht erst."""
    expected_red, expected_green = _verdicts(probe_tree, relative)
    globs = flat_globs(probe_tree, relative)

    red = {one.line for one in globs if one.folder not in _FLAT_FOLDERS}
    green = {one.line for one in globs if one.folder in _FLAT_FOLDERS}
    assert expected_red and expected_green, "die Attrappe trägt beide Urteile"
    assert red == expected_red, sorted(red ^ expected_red)
    assert green == expected_green, sorted(green ^ expected_green)


def test_the_guard_reads_only_files_that_mention_glob(probe_tree: Path) -> None:
    """Die Vorauswahl übergeht keine Datei mit einem Glob — sonst sähe der Wächter
    den Bestand nur halb."""
    _write(probe_tree, "tests/test_quiet.py", "VALUE = 1\n")
    _write(probe_tree, "tests/sub/test_deep.py", "import glob\nFILES = glob.glob('x/*.py')\n")

    assert _sources_with_globs(probe_tree, ("tests", "tools")) == [
        "tests/sub/test_deep.py",
        "tests/test_probe.py",
        "tools/probe_tool.py",
    ]


# --- Gegenproben im Unterpaket ------------------------------------------------------


@pytest.fixture(scope="module")
def tree_copy(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Eine Kopie der Python-Quellen unter ``app/``, einmal je Modul; jede Gegenprobe legt
    ihren Verstoß hinein und räumt ihn wieder ab."""
    root = tmp_path_factory.mktemp("tree")
    for source in source_tree.python_files("app"):
        target = root / source_tree.relative(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return root


#: Je umgestellter Prüfung: Testmodul, Testfunktion, Ort im Unterpaket, Verstoß.
_PROBES: tuple[tuple[str, str, str, str], ...] = (
    (
        "test_leash",
        "test_no_worker_is_started_past_the_leash",
        "app/ui/render/zz_probe_start.py",
        "def run(worker):\n    worker.start()\n",
    ),
    (
        "test_leash",
        "test_every_worker_in_the_surface_uses_the_base_class",
        "app/ui/render/zz_probe_thread.py",
        "from PySide6.QtCore import QThread\n\n\nclass ZzProbe(QThread):\n    pass\n",
    ),
    (
        "test_leash",
        "test_every_worker_has_somebody_listening_for_its_crash",
        "app/ui/render/zz_probe_deaf.py",
        "from app.ui.leash import Worker\n\n\nclass ZzProbeWorker(Worker):\n    pass\n\n\n"
        "def build():\n    worker = ZzProbeWorker()\n    worker.start()\n",
    ),
    (
        "test_style",
        "test_no_layout_invents_its_own_distance",
        "app/ui/render/zz_probe_spacing.py",
        "def build(layout):\n    layout.setSpacing(5)\n",
    ),
    (
        "test_style",
        "test_every_default_button_of_the_surface_goes_through_make_primary",
        "app/ui/render/zz_probe_default.py",
        "def build(button):\n    button.setDefault(True)\n",
    ),
    (
        "test_style",
        "test_no_multiline_field_swallows_the_tab_key",
        "app/ui/render/zz_probe_tab.py",
        "def build(self):\n    feld = QPlainTextEdit(self)\n    return feld\n",
    ),
    (
        "test_style",
        "test_no_progress_bar_prints_its_number_over_the_moving_edge",
        "app/ui/render/zz_probe_bar.py",
        "def build(self):\n    bar = QProgressBar(self)\n    return bar\n",
    ),
    (
        "test_style",
        "test_every_layout_of_a_dialog_keeps_the_grid",
        "app/ui/render/zz_probe_grid.py",
        "class ZzProbe(QDialog):\n    def build(self):\n        bare = QVBoxLayout(self)\n"
        "        return bare\n",
    ),
    (
        "test_ui",
        "test_no_worker_hands_its_field_to_a_blind_lambda",
        "app/ui/render/zz_probe_lambda.py",
        "def wire(self, worker):\n"
        "    worker.finished.connect(lambda: setattr(self, '_worker', None))\n",
    ),
    (
        "test_ui",
        "test_no_window_overrides_the_application_icon",
        "app/ui/render/zz_probe_icon.py",
        "def build(window, icon):\n    window.setWindowIcon(icon)\n",
    ),
    (
        "test_value_labels",
        "test_no_bar_nails_a_length_field_to_millimetres",
        "app/ui/render/zz_probe_unit.py",
        "from app.core.units import DISPLAY_UNITS\n\nUNIT = DISPLAY_UNITS[0]\n",
    ),
    (
        "test_widget_lifetime",
        "test_everything_that_holds_a_leash_can_be_told_to_let_go",
        "app/ui/render/zz_probe_holder.py",
        "from app.ui.leash import WorkerLeash\n\n\nclass ZzProbeHolder:\n"
        "    def __init__(self):\n        self.leash = WorkerLeash(self)\n",
    ),
    (
        "test_widget_lifetime",
        "test_every_filter_on_a_mortal_widget_unwatches_it",
        "app/ui/render/zz_probe_filter.py",
        "class ZzProbeFilter:\n    def watch(self, widget):\n"
        "        widget.installEventFilter(self)\n",
    ),
    (
        "test_native_keys",
        "test_a_list_that_opens_on_activation_carries_the_return_filter",
        "app/ui/render/zz_probe_return.py",
        "class ZzProbeList:\n    def build(self):\n"
        "        self.view.itemActivated.connect(self.open)\n",
    ),
    (
        "test_features",
        "test_recognition_selects_triangles_and_corners_through_plain_arrays",
        "app/core/perceive/zz_probe_pkg/zz_probe_faces.py",
        "def pick(body, mask):\n    return body.faces[mask]\n",
    ),
    (
        "test_translations",
        "test_model_texts_do_not_append_a_fixed_colon",
        "app/core/agent/zz_probe_pkg/zz_probe_colon.py",
        "from app.i18n import tr\n\nLABEL = tr('Wert') + ': x'\n",
    ),
    (
        "test_translations",
        "test_non_model_surface_labels_do_not_append_a_fixed_colon",
        "app/core/zz_probe_pkg/zz_probe_surface_colon.py",
        "from app.i18n import tr\n\nLABEL = tr('Wert') + ': x'\n",
    ),
    (
        "test_activation",
        "test_the_activation_never_asks_the_network",
        "app/core/activation/zz_probe_pkg/zz_probe_net.py",
        "import socket\n",
    ),
    (
        "test_activation",
        "test_there_is_no_switch_to_flip",
        "app/core/activation/zz_probe_pkg/zz_probe_switch.py",
        "from os import environ\n\nFLAG = environ.get('SOLIDON_PROBE')\n",
    ),
    (
        "test_print_disclosure",
        "test_both_notices_ask_the_same_source_what_a_utc_timestamp_is",
        "app/ui/render/zz_probe_utc.py",
        'def stamp(value):\n    return value.endswith("Z")\n',
    ),
)


def _check(module: str, name: str) -> Callable[[], None]:
    found: Callable[[], None] = getattr(importlib.import_module(f"tests.{module}"), name)
    return found


@pytest.mark.parametrize(
    ("module", "check", "probe", "text"), _PROBES, ids=[f"{one[0]}-{one[1]}" for one in _PROBES]
)
def test_every_converted_check_finds_a_violation_in_a_subpackage(
    tree_copy: Path, monkeypatch: pytest.MonkeyPatch, module: str, check: str, probe: str, text: str
) -> None:
    """Je umgestellter Prüfung ein Verstoß in einem Unterpaket der Kopie — gemeldet mit
    seinem Dateinamen, also aus dem richtigen Grund rot (CS-2, CS-12, RM-723).

    Ein flacher Glob ginge daran vorbei, ebenso eine Prüfung, die am Helfer
    vorbei in den echten Baum liest: Beide blieben grün, und ``pytest.raises``
    schlüge an.
    """
    function = _check(module, check)
    target = _write(tree_copy, probe, text)
    monkeypatch.setattr(source_tree, "ROOT", tree_copy)
    try:
        with pytest.raises(AssertionError, match=re.escape(target.name)):
            function()
    finally:
        target.unlink()


@pytest.fixture
def moved(tree_copy: Path) -> Iterator[Callable[[str, str], None]]:
    """Verschiebt Dateien der Kopie wie ein Schnitt in ein Unterpaket und stellt sie zurück."""
    done: list[tuple[Path, Path]] = []

    def move(source: str, target: str) -> None:
        before, after = tree_copy / source, tree_copy / target
        after.parent.mkdir(parents=True, exist_ok=True)
        before.rename(after)
        done.append((after, before))

    yield move
    for after, before in reversed(done):
        after.rename(before)


def test_the_sweeps_follow_a_definition_into_a_package(
    tree_copy: Path, monkeypatch: pytest.MonkeyPatch, moved: Callable[[str, str], None]
) -> None:
    """Wird ``main_window.py`` ein Paket und zieht ``detect`` um, lesen die Gegenproben
    der Oberflächen- und der Erkennungssuche weiter, was sie meinen (CS-12)."""
    moved("app/ui/main_window.py", "app/ui/main_window_cut/window.py")
    moved("app/core/perceive/features.py", "app/core/perceive/features_cut/recognition.py")
    monkeypatch.setattr(source_tree, "ROOT", tree_copy)

    _check("test_leash", "test_the_sweep_over_the_surface_finds_files_to_read")()
    _check("test_features", "test_recognition_selects_triangles_and_corners_through_plain_arrays")()


def test_a_flat_sweep_is_red(
    tree_copy: Path, monkeypatch: pytest.MonkeyPatch, moved: Callable[[str, str], None]
) -> None:
    """Gegenprobe zu CS-12: Läse der Helfer wieder flach, schlügen beide Gegenproben an —
    eine Mindestzahl Dateien allein hätte das nicht gesehen."""
    moved("app/ui/main_window.py", "app/ui/main_window_cut/window.py")
    moved("app/core/perceive/features.py", "app/core/perceive/features_cut/recognition.py")
    monkeypatch.setattr(source_tree, "ROOT", tree_copy)
    recursive = source_tree.python_files

    def flat(folder: str) -> list[Path]:
        return [path for path in recursive(folder) if path.parent == tree_copy / folder]

    monkeypatch.setattr(source_tree, "python_files", flat)
    for module, check in (
        ("test_leash", "test_the_sweep_over_the_surface_finds_files_to_read"),
        ("test_features", "test_recognition_selects_triangles_and_corners_through_plain_arrays"),
    ):
        with pytest.raises(AssertionError, match="0-mal"):
            _check(module, check)()
