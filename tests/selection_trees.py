"""Kleine Bäume für die Fälle von ``tools/affected_tests.py`` — eine Quelle für beide Testdateien.

``test_affected_tests.py`` und ``test_affected_edges.py`` bauen ihre Attrappen über dieselben
drei Helfer: eine Datei schreiben, Pfade relativ nennen und den Grundbaum aus fünf Testdateien,
in dem jeder Ausgang bekannt ist.
"""

from __future__ import annotations

from pathlib import Path


def write(root: Path, relative: str, text: str) -> Path:
    """Schreibt ``text`` nach ``root / relative`` und legt die Ordner an."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def names(files: set[Path], root: Path) -> set[str]:
    """Die Dateien relativ zu ``root``, mit ``/``."""
    return {path.relative_to(root).as_posix() for path in files}


def small_tree(root: Path) -> Path:
    """Der Grundbaum: drei Module unter ``app/``, ihre direkten, mittelbaren und typisierten
    Importeure, ein Baumleser, ein Unbeteiligter und einer, der ``ROADMAP.md`` nennt."""
    write(root, "app/__init__.py", "")
    write(root, "app/x.py", "VALUE = 1\n")
    write(root, "app/y.py", "from app.x import VALUE\n")
    write(root, "app/z.py", "OTHER = 2\n")
    write(root, "tests/__init__.py", "")
    write(root, "tests/conftest.py", "")
    write(root, "tests/test_direct.py", "from app import x\n")
    write(root, "tests/test_indirect.py", "def f():\n    from app.y import VALUE\n")
    write(
        root,
        "tests/test_typed.py",
        "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from app.x import VALUE\n",
    )
    write(
        root,
        "tests/test_reader.py",
        "from pathlib import Path\nSOURCES = Path('app').rglob('*.py')\n",
    )
    write(root, "tests/test_unrelated.py", "from app.z import OTHER\n")
    write(root, "tests/test_roadmap.py", "TEXT = 'ROADMAP.md'\n")
    write(root, "ROADMAP.md", "# Liste\n")
    return root
