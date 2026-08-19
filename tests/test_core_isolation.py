"""Kein Qt unterhalb von ``app.ui`` (AGENTS.md Regel 1, Bauplan §8) — und der
Kern für sich importierbar.

Drei Prüfungen für die Qt-Frage, denn jede allein ist zu schwach: jedes
Kernmodul zu importieren und nachzusehen, was in ``sys.modules`` gelandet ist,
fängt Laufzeit-Importe; die Quellen zu lesen fängt die trägen in Funktionen.

Die vierte gilt einer anderen Frage, die lange niemand gestellt hat: ob jedes
Kernmodul auch **als erstes** geladen werden kann. „Alle zusammen laden" ist
schwächer, als es aussieht — ein Import-Kreis zwischen zwei Modulen fällt nicht
auf, solange das eine schon fertig ist, wenn das andere beginnt.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import subprocess
import sys
import textwrap
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


def test_every_core_module_imports_first() -> None:
    """Jedes Modul auch **als erstes** — sonst bleibt ein Kreis unsichtbar.

    Der Test darüber lädt die Kernmodule der Reihe nach in einem Prozess. Was
    er damit prüft, ist „alle zusammen laden", und das ist schwächer, als es
    aussieht: Ein Kreis zwischen zwei Modulen fällt nicht auf, solange das
    eine schon fertig geladen ist, wenn das andere beginnt.

    Genau so entkam einer. ``geom.pose`` braucht den Ausdrucksauswerter und
    importiert ``scene.expressions``; Python lädt dabei das ganze Paket
    ``scene``, dessen ``__init__`` ``scene.evaluate`` zieht — und das
    importierte ``geom.pose``. In der Suite lief das durch, weil ``scene``
    immer vorher dran war. Wer ``app.core.geom.pose`` als Erstes lud — ein
    Skript, ein Werkzeug, eine Kommandozeile — bekam einen ``ImportError``.

    **Im Subprozess, und das ist keine Bequemlichkeit.** Der erste Anlauf lief
    hier und räumte zwischen den Modulen alles unter ``app.`` aus
    ``sys.modules``. Das trifft ``app.ui`` mit — und in einem Lauf, der
    danach noch Oberflächentests fährt, lädt Qt seine Widgetklassen ein
    zweites Mal. Zwei Klassenobjekte für dasselbe Widget sind genau die Sorte
    Zugriffsverletzung ohne Zeile, die in dieser Suite ohnehin schon gesucht
    wird; ein Test, der eine Absturzquelle einbaut, um eine Fehlerklasse zu
    finden, hat sich nicht gelohnt.

    Der Nachbar unten fährt aus demselben Grund einen eigenen Prozess. Innen
    genügt dann das Ausräumen von ``sys.modules``, weil dort nie Qt lag: 151
    Module in rund neun Sekunden statt in einer Minute mit einem Prozess je
    Modul.
    """
    script = textwrap.dedent(
        """
        import importlib, pkgutil, sys
        import app.core

        names = ['app.core'] + [
            info.name
            for info in pkgutil.walk_packages(app.core.__path__, prefix='app.core.')
        ]
        broken = []
        for name in names:
            for loaded in [entry for entry in sys.modules if entry.startswith('app.')]:
                del sys.modules[loaded]
            try:
                importlib.import_module(name)
            except Exception as problem:
                broken.append(f'{name}: {type(problem).__name__}: {problem}')
        print(len(names))
        print('; '.join(broken))
        """
    )
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=Path(app.core.__file__).parents[2],
        check=False,
    )
    assert finished.returncode == 0, finished.stderr

    counted, _, broken = finished.stdout.partition("\n")
    assert int(counted) > 100, f"nur {counted} Module gesehen — der Lauf hat nichts geprüft"
    assert not broken.strip(), f"als erstes geladen bricht: {broken.strip()}"


def test_importing_core_pulls_in_no_surface_dependency() -> None:
    """In einem frischen Prozess ausgeführt: in diesem hier haben die
    Oberflächentests Qt längst importiert.
    """
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
