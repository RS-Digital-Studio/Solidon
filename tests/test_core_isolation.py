"""No Qt below ``app.ui`` (AGENTS.md rule 1, Bauplan §8).

Two checks, because either one alone is too weak: importing every core module and
looking at what ended up in ``sys.modules`` catches runtime imports, reading the
sources catches lazy ones inside functions.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import subprocess
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


def test_importing_core_pulls_in_no_surface_dependency() -> None:
    """Run in a fresh process: in this one the surface tests have already imported Qt."""
    script = (
        "import importlib, pkgutil, sys\n"
        "import app.core\n"
        "for info in pkgutil.walk_packages(app.core.__path__, prefix='app.core.'):\n"
        "    importlib.import_module(info.name)\n"
        f"forbidden = {FORBIDDEN_ROOTS!r}\n"
        "loaded = sorted(m for m in sys.modules if m.split('.')[0] in forbidden)\n"
        "print(','.join(loaded))\n"
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    assert not finished.stdout.strip(), f"core pulled in a surface dependency: {finished.stdout}"


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
