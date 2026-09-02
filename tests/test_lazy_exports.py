"""Die Lazy-Pakete halten ihre drei Listen zusammen (``app/core/CLAUDE.md``).

Sieben Kernpakete exportieren ihre Namen über ``_EXPORTS`` und
:func:`app.core.lazy.install`, weil ein eifriges ``__init__`` zwei Threads
verklemmt (:mod:`app.core.lazy`). Die Karte sagt dazu: „Wer einen Namen
hinzufügt, trägt ihn an **drei** Stellen ein — ``TYPE_CHECKING``-Block,
``_EXPORTS``, ``__all__``." Bis hierher stand hinter dem Satz kein Test, und
jede der drei Stellen kann für sich allein driften, ohne dass etwas rot wird:

* Ein Eintrag in ``_EXPORTS``, dessen Untermodul oder Attribut es nicht gibt,
  fällt erst beim ersten Zugriff — und der kommt in einem Menü, nicht in der
  Suite.
* Ein Name in ``__all__``, den weder ``_EXPORTS`` noch das ``__init__`` selbst
  liefert, bricht ``from paket import *`` und täuscht jeden, der die Liste
  liest.
* Ein Name im ``TYPE_CHECKING``-Block, der nicht in ``_EXPORTS`` steht, ist
  für mypy da und zur Laufzeit ein ``AttributeError``.

Gesucht wird, nicht gepflegt: Jedes ``__init__`` unter ``app/`` mit einem
``install(__name__, _EXPORTS)`` ist ein Lazy-Paket.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Final

import pytest

import app

APP_DIR: Final = Path(app.__file__).parent


def _is_type_checking(node: ast.If) -> bool:
    test = node.test
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def _names_of(node: ast.expr) -> set[str]:
    """Die Zeichenketten einer Liste, eines Tupels oder der Schlüssel eines Dicts."""
    if isinstance(node, (ast.List, ast.Tuple)):
        return {item.value for item in node.elts if isinstance(item, ast.Constant)}
    if isinstance(node, ast.Dict):
        return {key.value for key in node.keys if isinstance(key, ast.Constant)}
    return set()


class LazyPackage:
    """Was ein Lazy-Paket in seiner ``__init__.py`` deklariert."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.name = ".".join(("app", *path.relative_to(APP_DIR).parent.parts))
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        self.exports: set[str] = set()
        self.all_names: set[str] = set()
        self.type_checking: set[str] = set()
        self.own: set[str] = set()
        for node in tree.body:
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            for target in targets:
                if not isinstance(target, ast.Name) or value is None:
                    continue
                if target.id == "_EXPORTS":
                    self.exports = _names_of(value)
                elif target.id == "__all__":
                    self.all_names = _names_of(value)
                elif not target.id.startswith("_"):
                    self.own.add(target.id)
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ) and not node.name.startswith("_"):
                self.own.add(node.name)
            if isinstance(node, ast.If) and _is_type_checking(node):
                for statement in node.body:
                    if isinstance(statement, ast.ImportFrom):
                        self.type_checking.update(
                            alias.asname or alias.name for alias in statement.names
                        )
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # Eifrig importierte Namen gehören dem Paket genauso wie eigene
                # Definitionen — ``activation`` reexportiert so seine Fehler.
                self.own.update(alias.asname or alias.name for alias in node.names)

    def __repr__(self) -> str:
        return self.name


def lazy_packages() -> list[LazyPackage]:
    found: list[LazyPackage] = []
    for path in sorted(APP_DIR.rglob("__init__.py")):
        source = path.read_text(encoding="utf-8")
        if "install(__name__, _EXPORTS)" in source:
            found.append(LazyPackage(path))
    assert len(found) >= 5, f"nur {len(found)} Lazy-Pakete gefunden — die Suche greift nicht"
    return found


@pytest.mark.parametrize("package", lazy_packages(), ids=repr)
def test_every_lazy_export_resolves(package: LazyPackage) -> None:
    """Jeder Eintrag zeigt auf ein Untermodul und ein Attribut, das es gibt."""
    module = importlib.import_module(package.name)
    exports = module.__dict__["_EXPORTS"]
    broken: list[str] = []
    for name, (submodule, attribute) in exports.items():
        try:
            target = importlib.import_module(f"{package.name}.{submodule}")
        except ImportError as problem:
            broken.append(f"{name}: Untermodul {submodule!r} — {problem}")
            continue
        if not hasattr(target, attribute):
            broken.append(f"{name}: {package.name}.{submodule} hat kein {attribute!r}")
    assert not broken, "\n".join(broken)


@pytest.mark.parametrize("package", lazy_packages(), ids=repr)
def test_every_lazy_export_is_promised_in_all(package: LazyPackage) -> None:
    missing = sorted(package.exports - package.all_names)
    assert not missing, f"in _EXPORTS, aber nicht in __all__: {missing}"


@pytest.mark.parametrize("package", lazy_packages(), ids=repr)
def test_all_promises_only_what_the_package_delivers(package: LazyPackage) -> None:
    """``__all__`` nennt nur Namen, die ``_EXPORTS`` oder das ``__init__`` liefern."""
    unbacked = sorted(package.all_names - package.exports - package.own)
    assert not unbacked, (
        f"in __all__, aber weder in _EXPORTS noch im __init__ definiert: {unbacked}"
    )


@pytest.mark.parametrize("package", lazy_packages(), ids=repr)
def test_type_checking_names_match_the_exports(package: LazyPackage) -> None:
    """Was mypy sieht, sieht auch die Laufzeit — und umgekehrt.

    Namen mit Unterstrich sind ausgenommen: ``activation`` holt sich so ein
    Modul für seine Annotationen, das nach außen nicht gehört.
    """
    public_type_checking = {name for name in package.type_checking if not name.startswith("_")}
    only_for_mypy = sorted(public_type_checking - package.exports)
    only_at_runtime = sorted(package.exports - public_type_checking)
    assert not only_for_mypy, f"nur unter TYPE_CHECKING, nicht in _EXPORTS: {only_for_mypy}"
    assert not only_at_runtime, f"in _EXPORTS, aber nicht unter TYPE_CHECKING: {only_at_runtime}"
