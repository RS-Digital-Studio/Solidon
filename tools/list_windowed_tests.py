"""Testdateien nennen, die über ihren Fixture-Graphen ein Qt-Fenster bauen.

    .venv\\Scripts\\python.exe tools/list_windowed_tests.py

Die geteilte Suite muss Fensterdateien in eigene Prozesse legen. Eine Suche
nach Klassennamen im Quelltext war dafür kein Kriterium: Ein Docstring zog
eine reine Kerndatei in die Fenstergruppe, während eine indirekt geerbte
Fixture ohne den Namen unsichtbar blieb. Pytest kennt den vollständigen
Fixture-Graphen bereits; dieses Werkzeug liest ihn nach der Sammlung aus.
"""

from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


class WindowedCollector:
    """Sammelt Dateipfade mit mindestens einem nicht langsamen ``qt_app``-Test."""

    def __init__(self) -> None:
        self.files: set[Path] = set()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        for item in session.items:
            if item.get_closest_marker("performance") is not None:
                continue
            if "qt_app" in item.fixturenames:
                self.files.add(Path(str(item.path)).resolve())


def collect_windowed(paths: Sequence[Path], *, confcutdir: Path | None = None) -> tuple[Path, ...]:
    """Sammelt ohne Testlauf und gibt die betroffenen Dateien sortiert zurück."""
    collector = WindowedCollector()
    arguments = ["--collect-only", "-q", "-m", "not performance"]
    if confcutdir is not None:
        arguments.extend(("--confcutdir", str(confcutdir)))
    arguments.extend(str(path) for path in paths)
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(captured_err):
        outcome = pytest.main(arguments, plugins=[collector])
    if outcome != pytest.ExitCode.OK:
        details = (captured_out.getvalue() + captured_err.getvalue()).strip()
        raise RuntimeError(f"Die Tests ließen sich nicht sammeln (Exit {int(outcome)}).\n{details}")
    return tuple(sorted(collector.files))


def main() -> int:
    files = collect_windowed((ROOT / "tests",))
    for path in files:
        print(path.relative_to(ROOT).as_posix())
    if not files:
        print("Keine Fensterdatei über den Fixture-Graphen gefunden.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
