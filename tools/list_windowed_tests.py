"""Testdateien nennen, die über Fixtures oder eigene Prozesse Qt-Fenster bauen.

    .venv\\Scripts\\python.exe tools/list_windowed_tests.py

Die geteilte Suite muss Fenstertests in eigene Prozesse legen. Eine Suche
nach Klassennamen im Quelltext war dafür kein Kriterium: Ein Docstring zog
eine reine Kerndatei in die Fenstergruppe, während eine indirekt geerbte
Fixture ohne den Namen unsichtbar blieb. Pytest kennt den vollständigen
Fixture-Graphen bereits; dieses Werkzeug liest ihn nach der Sammlung aus.
Fenster in eigenen Prozessen tragen ausdrücklich ``pytest.mark.windowed``,
weil deren Aufbau nicht im Fixture-Graphen des aufrufenden Tests steht.

**Getrennt wird je Test, nicht je Datei** (22.09.2026). Bis dahin zog ein
einziger Fenstertest seine ganze Datei in die Fenstergruppe, und die lief nur
beim Release — und in der CI nur unter Windows. Gemessen an jenem Tag: 1709
Tests ohne Fenster lagen so außerhalb jedes Entwicklungstors, darunter 216
von 217 in ``test_translations.py``, 307 von 313 in ``test_print_settings.py``
und 101 von 103 in ``test_toolchain.py``. Sie liefen dabei zu drei Befunden
auf, die niemand gesehen hatte. :func:`mark_windowed_items` gibt deshalb
jedem Fenstertest den Marker ``windowed``; das reguläre Tor wählt ihn mit
``-m "not windowed"`` ab, das Release-Tor fährt je Datei ``-m windowed``.
"""

from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def needs_a_window(item: pytest.Item) -> bool:
    """Ob ein Test ein Fenster baut: über ``qt_app`` oder ausdrücklich markiert."""
    return (
        "qt_app" in getattr(item, "fixturenames", ())
        or item.get_closest_marker("windowed") is not None
    )


def mark_windowed_items(items: list[pytest.Item]) -> None:
    """Gibt jedem Test mit ``qt_app`` den Marker ``windowed``.

    Dann trennt ``-m`` genau wie der Fixture-Graph: ``not windowed`` für das
    reguläre Tor, ``windowed`` für die Fensterprozesse beim Release. Gerufen
    aus ``tests/conftest.py`` und als Laufplugin von ``affected_tests``.
    """
    for item in items:
        if needs_a_window(item) and item.get_closest_marker("windowed") is None:
            item.add_marker(pytest.mark.windowed)


class WindowedCollector:
    """Sammelt je Datei, ob sie Fenstertests und ob sie Tests ohne Fenster trägt."""

    def __init__(self) -> None:
        self.files: set[Path] = set()
        self.plain_files: set[Path] = set()
        self.collected_count = 0

    def pytest_itemcollected(self, item: pytest.Item) -> None:
        """Erfasst den aufgelösten Fall vor jeder Abwahl durch Fallfilter."""
        self.collected_count += 1
        if item.get_closest_marker("performance") is not None:
            return
        path = Path(str(item.path)).resolve()
        if needs_a_window(item):
            self.files.add(path)
        else:
            self.plain_files.add(path)


#: Welche Tests ein Lauf mit ``--window-group`` nimmt.
WINDOW_GROUPS = {"plain": "not windowed", "windowed": "windowed"}


def pytest_addoption(parser: pytest.Parser) -> None:
    """``--window-group`` als Laufplugin: ergänzt den Markerfilter, statt ihn zu ersetzen.

    Ein zweites ``-m`` auf der Kommandozeile gewönne gegen das aus
    ``PYTEST_ADDOPTS`` oder der Konfiguration — und der Filter des Aufrufers
    wäre still verloren.
    """
    parser.addoption("--window-group", choices=sorted(WINDOW_GROUPS), default=None)


def pytest_configure(config: pytest.Config) -> None:
    """Als ausdrücklich geladenes Laufplugin Leistung und die andere Gruppe abwählen."""
    terms = ["not performance"]
    group = config.getoption("--window-group", default=None)
    if group:
        terms.append(WINDOW_GROUPS[group])
    marker = config.option.markexpr
    joined = " and ".join(terms)
    config.option.markexpr = f"({marker}) and {joined}" if marker else joined


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Als Laufplugin markieren, bevor ``-m`` abwählt — auch ohne Projekt-conftest."""
    mark_windowed_items(items)


def collect_windowed(paths: Sequence[Path], *, confcutdir: Path | None = None) -> tuple[Path, ...]:
    """Sammelt ohne Testlauf und gibt die betroffenen Dateien sortiert zurück."""
    windowed, _plain = collect_test_groups(paths, confcutdir=confcutdir)
    return windowed


def collect_test_groups(
    paths: Sequence[Path], *, confcutdir: Path | None = None
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Dateien mit Fenstertests und Dateien mit Tests ohne Fenster — eine kann beides sein.

    Leistungstests zählen zu keiner der beiden Gruppen; eine Datei, die nur
    sie trägt, bleibt draußen.
    """
    collector = WindowedCollector()
    # Nur die Sammlung ist ungefiltert. Die Umgebung bleibt für den echten
    # Lauf erhalten; dort verknüpft das Plugin den wirksamen Marker mit dem
    # Leistungsausschluss, statt den Nutzerfilter zu überschreiben.
    arguments = ["--collect-only", "-q", "-k", "", "-m", ""]
    if confcutdir is not None:
        arguments.extend(("--confcutdir", str(confcutdir)))
    arguments.extend(str(path) for path in paths)
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(captured_err):
        outcome = pytest.main(arguments, plugins=[collector])
    only_filtered = outcome == pytest.ExitCode.NO_TESTS_COLLECTED and collector.collected_count > 0
    if outcome != pytest.ExitCode.OK and not only_filtered:
        details = (captured_out.getvalue() + captured_err.getvalue()).strip()
        raise RuntimeError(f"Die Tests ließen sich nicht sammeln (Exit {int(outcome)}).\n{details}")
    return tuple(sorted(collector.files)), tuple(sorted(collector.plain_files))


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
