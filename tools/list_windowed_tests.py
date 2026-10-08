"""Testdateien für Qt-Fenster und echte Rendererläufe trennen.

    .venv\\Scripts\\python.exe tools/list_windowed_tests.py

Die geteilte Suite muss Fenster- und Rendererfälle in eigene Prozesse legen. Eine Suche
nach Klassennamen im Quelltext war dafür kein Kriterium: Ein Docstring zog
eine reine Kerndatei in die Fenstergruppe, während eine indirekt geerbte
Fixture ohne den Namen unsichtbar blieb. Pytest kennt den vollständigen
Fixture-Graphen bereits; dieses Werkzeug liest ihn nach der Sammlung aus.
Fenster in eigenen Prozessen tragen ausdrücklich ``pytest.mark.windowed``,
weil deren Aufbau nicht im Fixture-Graphen des aufrufenden Tests steht; wer
eines auf der echten Plattform zeigt, fordert ``native_window_platform`` an
und ist damit markiert. Echte Grafik trägt ``pytest.mark.rendering`` oder
fordert die zentrale Fixture ``require_graphics_adapter`` an.
Erzeugnisvergleiche bleiben davon getrennt: ``rendered`` bezeichnet nur
vorbereitete Handbuch- und Website-Bilder.

**Getrennt wird je Test, nicht je Datei** (22.09.2026). Bis dahin zog ein
einziger Fenstertest seine ganze Datei in die Fenstergruppe, und die lief nur
beim Release — und in der CI nur unter Windows. Gemessen an jenem Tag: 1709
Tests ohne Fenster lagen so außerhalb jedes Entwicklungstors, darunter 216
von 217 in ``test_translations.py``, 307 von 313 in ``test_print_settings.py``
und 101 von 103 in ``test_toolchain.py``. Sie liefen dabei zu drei Befunden
auf, die niemand gesehen hatte. :func:`mark_windowed_items` gibt deshalb
jedem Fenstertest den Marker ``windowed``. Echte Rendererfälle tragen
``rendering``. Das reguläre Tor wählt beide mit
``-m "not windowed and not rendering"`` ab, das Release-Tor fährt beide
Gruppen je Datei.
"""

from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_GRAPHICS_FIXTURES = frozenset({"graphics_adapter_problem", "require_graphics_adapter"})
#: ``qt_app`` baut Fenster im Testprozess, ``native_window_platform`` zeigt
#: eines auf der echten Plattform im Kindprozess (``tests/conftest.py``).
_WINDOW_FIXTURES = frozenset({"qt_app", "native_window_platform"})


def needs_a_window(item: pytest.Item) -> bool:
    """Ob ein Test ein Fenster baut: über eine Fensterfixture oder ausdrücklich markiert."""
    return (
        bool(_WINDOW_FIXTURES.intersection(getattr(item, "fixturenames", ())))
        or item.get_closest_marker("windowed") is not None
    )


def needs_rendering(item: pytest.Item) -> bool:
    """Ob ein Test echte Grafik nutzt: zentrale Adapterfixture oder Direktmarke."""
    return (
        bool(_GRAPHICS_FIXTURES.intersection(getattr(item, "fixturenames", ())))
        or item.get_closest_marker("rendering") is not None
    )


def needs_release_isolation(item: pytest.Item) -> bool:
    """Ob ein Test nur im Release-Tor laufen darf."""
    return needs_a_window(item) or needs_rendering(item)


def mark_windowed_items(items: list[pytest.Item]) -> None:
    """Gibt jedem Test mit ``qt_app`` oder ``native_window_platform`` den Marker ``windowed``.

    Dann trennt ``-m`` genau wie der Fixture-Graph: ``not windowed`` für das
    reguläre Tor, ``windowed`` für die Fensterprozesse beim Release. Gerufen
    aus ``tests/conftest.py`` und als Laufplugin von ``affected_tests``.
    """
    for item in items:
        if needs_a_window(item) and item.get_closest_marker("windowed") is None:
            item.add_marker(pytest.mark.windowed)


def mark_rendering_items(items: list[pytest.Item]) -> None:
    """Markiert Nutzer der zentralen Grafikfixture vor der Markerabwahl."""
    for item in items:
        if needs_rendering(item) and item.get_closest_marker("rendering") is None:
            item.add_marker(pytest.mark.rendering)


class WindowedCollector:
    """Sammelt je Datei Releasefälle und die reguläre Dateigruppe des angefragten Laufs."""

    def __init__(self, *, include_rendered: bool = False) -> None:
        self.files: set[Path] = set()
        self.plain_files: set[Path] = set()
        self.window_counts: dict[Path, int] = {}
        #: Je Datei die Programme ihrer Slicertests (``pytest.mark.slicer``).
        self.slicer_programs: dict[Path, set[str]] = {}
        self.include_rendered = include_rendered
        self.collected_count = 0

    def pytest_itemcollected(self, item: pytest.Item) -> None:
        """Erfasst den aufgelösten Fall vor jeder Abwahl durch Fallfilter."""
        self.collected_count += 1
        if item.get_closest_marker("performance") is not None:
            return
        if not self.include_rendered and item.get_closest_marker("rendered") is not None:
            return
        path = Path(str(item.path)).resolve()
        for marker in item.iter_markers("slicer"):
            self.slicer_programs.setdefault(path, set()).update(str(arg) for arg in marker.args)
        if needs_release_isolation(item):
            self.files.add(path)
            self.window_counts[path] = self.window_counts.get(path, 0) + 1
        else:
            self.plain_files.add(path)


#: Welche Tests ein Lauf mit ``--window-group`` nimmt.
WINDOW_GROUPS = {
    "plain": "not windowed and not rendering",
    "windowed": "(windowed or rendering)",
}


def pytest_addoption(parser: pytest.Parser) -> None:
    """``--window-group`` als Laufplugin: ergänzt den Markerfilter, statt ihn zu ersetzen.

    Ein zweites ``-m`` auf der Kommandozeile gewönne gegen das aus
    ``PYTEST_ADDOPTS`` oder der Konfiguration — und der Filter des Aufrufers
    wäre still verloren.
    """
    parser.addoption("--window-group", choices=sorted(WINDOW_GROUPS), default=None)
    parser.addoption(
        "--with-rendered",
        action="store_true",
        default=False,
        help="Erzeugnisvergleiche (rendered) mitnehmen wie das Release-Tor",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Als ausdrücklich geladenes Laufplugin Leistung und die andere Gruppe abwählen.

    Erzeugnisvergleiche (``rendered``) wählt es ab wie das Entwicklungstor; erst
    ``--with-rendered`` nimmt sie mit wie das Release-Tor.
    """
    terms = ["not performance"]
    if not config.getoption("--with-rendered", default=False):
        terms.append("not rendered")
    group = config.getoption("--window-group", default=None)
    if group:
        terms.append(WINDOW_GROUPS[group])
    marker = config.option.markexpr
    joined = " and ".join(terms)
    config.option.markexpr = f"({marker}) and {joined}" if marker else joined


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Fenster und Renderer markieren, bevor ``-m`` abwählt."""
    mark_windowed_items(items)
    mark_rendering_items(items)


def collect_windowed(paths: Sequence[Path], *, confcutdir: Path | None = None) -> tuple[Path, ...]:
    """Sammelt ohne Testlauf und gibt die betroffenen Dateien sortiert zurück."""
    windowed, _plain = collect_test_groups(paths, confcutdir=confcutdir, include_rendered=True)
    return windowed


def collect_test_groups(
    paths: Sequence[Path], *, confcutdir: Path | None = None, include_rendered: bool = False
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Dateien mit Fenster-/Rendererfällen und regulären Tests sammeln.

    Fenster- und Rendererfälle zählen zur Releasegruppe. Erzeugnisvergleiche
    kommen nur mit ``include_rendered`` in die reguläre Dateigruppe. Leistung
    zählt zu keiner Gruppe; Dateien ohne wählbare Fälle bleiben draußen.
    """
    collector = _collect(paths, confcutdir=confcutdir, include_rendered=include_rendered)
    return tuple(sorted(collector.files)), tuple(sorted(collector.plain_files))


def collect_ci_window_counts(
    paths: Sequence[Path], *, confcutdir: Path | None = None
) -> dict[Path, int]:
    """Zählt Fenster- und Rendererfälle ohne Leistung und Erzeugnisvergleiche."""
    collector = _collect(paths, confcutdir=confcutdir)
    return dict(sorted(collector.window_counts.items()))


def collect_ci_selection(
    paths: Sequence[Path], *, confcutdir: Path | None = None
) -> tuple[tuple[Path, ...], dict[Path, tuple[str, ...]]]:
    """Fensterdateien und je Datei die Slicer ihrer ``slicer``-Fälle, in einer Sammlung.

    Für ``tools/ci_selection.py``: Eine Sammlung über die betroffenen Dateien
    kostet mit der Oberfläche über eine Minute, zwei kosteten das Doppelte.
    """
    collector = _collect(paths, confcutdir=confcutdir)
    programs = {
        path: tuple(sorted(found)) for path, found in sorted(collector.slicer_programs.items())
    }
    return tuple(sorted(collector.files)), programs


def _collect(
    paths: Sequence[Path], *, confcutdir: Path | None, include_rendered: bool = False
) -> WindowedCollector:
    """Liest den ungefilterten Fixture-Graphen für lokale und CI-Gruppen einmal."""
    collector = WindowedCollector(include_rendered=include_rendered)
    # Nur die Sammlung ist ungefiltert. Die Umgebung bleibt für den echten
    # Lauf erhalten; dort verknüpft das Plugin den wirksamen Marker mit dem
    # Leistungsausschluss, statt den Nutzerfilter zu überschreiben.
    #
    # ``-qq``: eine Zeile je Datei statt je Fall. Die Ausgabe dient nur der
    # Fehlermeldung unten, und mit ``-q`` stand dort vor dem eigentlichen
    # Fehler jede Fallkennung der Suite — gemessen am 25.09.2026 1,9 MB in
    # 20 699 Zeilen gegen 11 KB in 363, und mehr, als GitHub in den
    # Schrittbericht eines Schritts aufnimmt (1 MiB).
    arguments = ["--collect-only", "-qq", "-k", "", "-m", ""]
    if confcutdir is not None:
        arguments.extend(("--confcutdir", str(confcutdir)))
    arguments.extend(str(path) for path in paths)
    captured_out = io.StringIO()
    captured_err = io.StringIO()
    # **Die Sammlung hinterlässt dem Aufrufer sein Modulverzeichnis.** Eine
    # ``conftest.py`` ohne Paket lädt pytest als Modul ``conftest`` und wirft
    # dafür das vorhandene gleichen Namens aus ``sys.modules`` — im eigenen
    # Prozess einer laufenden Suite ist das deren ``tests/conftest.py``.
    # Danach fand ``from conftest import make_object`` die ``conftest.py``
    # eines Testordners im Temp-Verzeichnis (CI 0.5.1, macOS). Ersetztes kommt
    # zurück, und der Suchpfad steht wieder, wie er stand.
    modules = dict(sys.modules)
    search_path = list(sys.path)
    try:
        with contextlib.redirect_stdout(captured_out), contextlib.redirect_stderr(captured_err):
            outcome = pytest.main(arguments, plugins=[collector])
    finally:
        sys.path[:] = search_path
        for name, module in modules.items():
            if sys.modules.get(name) is not module:
                sys.modules[name] = module
    only_filtered = outcome == pytest.ExitCode.NO_TESTS_COLLECTED and collector.collected_count > 0
    if outcome != pytest.ExitCode.OK and not only_filtered:
        details = (captured_out.getvalue() + captured_err.getvalue()).strip()
        raise RuntimeError(f"Die Tests ließen sich nicht sammeln (Exit {int(outcome)}).\n{details}")
    return collector


def main() -> int:
    files = collect_windowed((ROOT / "tests",))
    for path in files:
        print(path.relative_to(ROOT).as_posix())
    if not files:
        print(
            "Keine Fenster- oder Rendererdatei über Fixtures oder Marker gefunden.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
