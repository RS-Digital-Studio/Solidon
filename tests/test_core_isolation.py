"""No Qt below ``app.ui`` (AGENTS.md rule 1, Bauplan §8).

Two checks, because either one alone is too weak: importing every core module and
looking at what ended up in ``sys.modules`` catches runtime imports, reading the
sources catches lazy ones inside functions.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import sys
from pathlib import Path

import app.core

FORBIDDEN_ROOTS = ("PySide6", "PyQt5", "PyQt6", "PySide2", "app.ui")
CORE_DIR = Path(app.core.__file__).parent


def core_modules() -> list[str]:
    names = ["app.core"]
    for info in pkgutil.walk_packages(app.core.__path__, prefix="app.core."):
        names.append(info.name)
    return names


def core_sources() -> list[Path]:
    return sorted(CORE_DIR.rglob("*.py"))


def test_every_core_module_imports() -> None:
    for name in core_modules():
        importlib.import_module(name)


def test_no_qt_in_sys_modules_after_importing_core() -> None:
    for name in core_modules():
        importlib.import_module(name)
    loaded = {module for module in sys.modules if module.split(".")[0] in FORBIDDEN_ROOTS}
    assert not loaded, f"core pulled in a surface dependency: {sorted(loaded)}"


def test_core_sources_never_reference_the_surface() -> None:
    offenders: list[str] = []
    for path in core_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                if any(module == root or module.startswith(f"{root}.") for root in FORBIDDEN_ROOTS):
                    offenders.append(f"{path.name}:{node.lineno} imports {module}")
    assert not offenders, "\n".join(offenders)
