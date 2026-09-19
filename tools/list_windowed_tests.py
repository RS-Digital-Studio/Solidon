"""Testdateien nennen, die über Fixtures oder eigene Prozesse Qt-Fenster bauen.

    .venv\\Scripts\\python.exe tools/list_windowed_tests.py

Die geteilte Suite muss Fensterdateien in eigene Prozesse legen. Eine Suche
nach Klassennamen im Quelltext war dafür kein Kriterium: Ein Docstring zog
eine reine Kerndatei in die Fenstergruppe, während eine indirekt geerbte
Fixture ohne den Namen unsichtbar blieb. Pytest kennt den vollständigen
Fixture-Graphen bereits; dieses Werkzeug liest ihn nach der Sammlung aus.
Fenster in eigenen Prozessen tragen ausdrücklich ``pytest.mark.windowed``,
weil deren Aufbau nicht im Fixture-Graphen des aufrufenden Tests steht.
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
    """Sammelt Dateien mit Fensterbedarf über ``qt_app`` oder ``windowed``."""

    def __init__(self) -> None:
        self.files: set[Path] = set()
        self.plain_files: set[Path] = set()
        self.performance_count = 0
        self.deselected_count = 0

    def pytest_deselected(self, items: list[pytest.Item]) -> None:
        self.deselected_count += len(items)
        self.performance_count += sum(
            item.get_closest_marker("performance") is not None for item in items
        )

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        for item in session.items:
            if item.get_closest_marker("performance") is not None:
                continue
            if (
                "qt_app" in getattr(item, "fixturenames", ())
                or item.get_closest_marker("windowed") is not None
            ):
                self.files.add(Path(str(item.path)).resolve())
            else:
                self.plain_files.add(Path(str(item.path)).resolve())


def collect_windowed(paths: Sequence[Path], *, confcutdir: Path | None = None) -> tuple[Path, ...]:
    """Sammelt ohne Testlauf und gibt die betroffenen Dateien sortiert zurück."""
    windowed, _plain = collect_test_groups(paths, confcutdir=confcutdir)
    return windowed


def collect_test_groups(
    paths: Sequence[Path], *, confcutdir: Path | None = None
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Fenster und übrige Dateien mit ausführbaren Tests; Leistung bleibt draußen."""
    collector = WindowedCollector()
    arguments = ["--collect-only", "-q", "-m", "not performance"]
    if confcutdir is not None:
        arguments.extend(("--confcutdir", str(confcutdir)))
    arguments.extend(str(path) for path in paths)
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(captured_err):
        outcome = pytest.main(arguments, plugins=[collector])
    only_performance = (
        outcome == pytest.ExitCode.NO_TESTS_COLLECTED
        and collector.performance_count > 0
        and collector.performance_count == collector.deselected_count
    )
    if outcome != pytest.ExitCode.OK and not only_performance:
        details = (captured_out.getvalue() + captured_err.getvalue()).strip()
        raise RuntimeError(f"Die Tests ließen sich nicht sammeln (Exit {int(outcome)}).\n{details}")
    return tuple(sorted(collector.files)), tuple(sorted(collector.plain_files - collector.files))


def main() -> int:
    files = collect_windowed((ROOT / "tests",))
    for path in files:
        print(path.relative_to(ROOT).as_posix())
    if not files:
        print("Keine Fensterdatei über Fixtures oder Marker gefunden.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
