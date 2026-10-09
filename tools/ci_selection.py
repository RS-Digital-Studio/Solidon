"""Welche Fenster- und Slicertests eine Änderung auf Linux und macOS braucht.

    .venv\\Scripts\\python.exe tools/ci_selection.py                    # origin/main...HEAD
    .venv\\Scripts\\python.exe tools/ci_selection.py --diff abc12..origin/main  # ein Merge
    .venv\\Scripts\\python.exe tools/ci_selection.py app/ui/panels.py   # oder Dateien
    .venv\\Scripts\\python.exe tools/ci_selection.py --programs "<auswahl>"

Linux und macOS gibt es an keinem Arbeitsplatz. Beim Push nach main laufen
deshalb die Fenstertests und die Slicertests mit echtem Programm, die der
gepushte Diff berührt, auf den Läufern (Entscheidung Robert, 07.10.2026; auf
Zweigen läuft keine CI, 09.10.2026): ``build.yml`` ruft dieses Werkzeug im Job
``auswahl`` und gibt beide Listen an ``fenster-auswahl.yml`` und
``slicer-auswahl.yml``. Nicht die ganze Suite — macOS-Minuten kosten das
Zehnfache. Lokal zeigt es vor dem Merge, was der Push fahren wird.

Die betroffenen Testdateien kommen aus demselben Importgraphen wie
``affected_tests.py``. Zwei Dinge sind anders:

1. **Unterlagen zählen nicht — der Kosten wegen.** Markdown außerhalb von
   ``changelog/``, ``konzepte/`` und die Sprachkataloge lösen keine Auswahl
   aus. Über den Ordnerweg zöge ein Katalog sonst jeden Test eines Moduls
   nach sich, das ``locales/`` liest, und damit fast die ganze
   Fenstergruppe auf macOS. Folgenlos ist das nicht: Die Sprachfälle der
   Fenstertests messen Textlängen und Umbruch, und die prüft für einen
   geänderten Katalog erst das Releasetor auf allen Plattformen; ohne
   Fenster laufen ``test_translations.py`` und ``test_text_length.py`` im
   Tor. **Ausgenommen sind die Markdown-Dateien, die die Anwendung selbst
   liest** (:data:`READ_BY_THE_APPLICATION`) — sie zeigt ein Fenster.
2. **Ausgegeben wird je Datei eine Auswahl**, im Eingabeformat der Workflows:
   Semikolon zwischen den Auswahlen, je Auswahl ein Prozess. Fenster laufen
   über die Fenstergruppe des Laufplugins, Slicertests über ``-m slicer``.

``--programs`` liest eine Slicerauswahl zurück und nennt die Programme, die
ihre Fälle über ``pytest.mark.slicer`` verlangen — der Workflow installiert
genau diese.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import affected_tests, list_windowed_tests  # noqa: E402

#: Der Vergleich, wenn nichts genannt ist: was der Zweig gegenüber main trägt.
DEFAULT_DIFF = "origin/main...HEAD"

#: Was eine Fensterauswahl dem Lauf mitgibt: nur die Fenster- und
#: Rendererfälle der Datei, wie die Releasegruppe.
WINDOW_ARGUMENTS = ("-p", "tools.list_windowed_tests", "--window-group", "windowed")

#: Was eine Slicerauswahl dem Lauf mitgibt: nur die Fälle mit echtem Programm.
SLICER_ARGUMENTS = ("-m", "slicer")


#: Markdown, das die Anwendung zur Laufzeit liest und in einem Fenster zeigt:
#: die Datenschutzauskunft (``ui/ai_disclosure.py``) und die Lizenzbeilage
#: (``core/knowledge/licences.py``). ``tests/test_slicer_selection.py`` hält
#: die Liste an den Dateinamen im Code.
READ_BY_THE_APPLICATION: frozenset[str] = frozenset({"DATENSCHUTZ.md", "THIRD-PARTY-NOTICES.md"})


def is_documentation(relative: str) -> bool:
    """Gilt diese Datei für die Auswahl als Unterlage, die keinen Lauf auslöst?

    Ausgeschlossen wird der Kosten wegen, nicht weil kein Fenster sie zeigte
    (Modulkopf, Punkt 1). Der Changelog ist keine Unterlage: Das
    Update-Fenster zeigt ihn — ebenso die Dateien aus
    :data:`READ_BY_THE_APPLICATION`.
    """
    path = PurePosixPath(relative)
    if path.parts[:1] == ("konzepte",):
        return True
    if path.parent == PurePosixPath("app/i18n/locales") and path.suffix == ".json":
        return True
    if relative in READ_BY_THE_APPLICATION:
        return False
    return path.suffix == ".md" and path.parts[:1] != ("changelog",)


def changed_in(diff: str, root: Path = ROOT) -> list[Path]:
    """Die Dateien eines Diffs ``<basis>..<kopf>`` oder ``<basis>...<kopf>``.

    Ohne Umbenennungserkennung, wie ``affected_tests.changed_files``: Der alte
    Modulname bleibt in der Auswahl.
    """
    finished = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "-z", diff],
        capture_output=True,
        text=True,
        check=True,
        cwd=root,
        encoding="utf-8",
    )
    return sorted(root / name for name in finished.stdout.split("\0") if name)


def _relative(path: Path, root: Path) -> str:
    return (path.relative_to(root) if path.is_absolute() else path).as_posix()


def select(changed: Iterable[Path], root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Fensterauswahlen und Slicerauswahlen zu diesen geänderten Dateien."""
    root = root.resolve()
    relevant = [path for path in changed if not is_documentation(_relative(path, root))]
    if not relevant:
        return [], []
    files, _reasons = affected_tests.affected(relevant, affected_tests.ImportGraph(root))
    if not files:
        return [], []
    ordered = sorted(files)
    windowed, slicers = list_windowed_tests.collect_ci_selection(ordered, confcutdir=root)
    return (
        [_selection(path, root, WINDOW_ARGUMENTS) for path in windowed],
        [_selection(path, root, SLICER_ARGUMENTS) for path in slicers],
    )


def _selection(path: Path, root: Path, arguments: Sequence[str]) -> str:
    return shlex.join([_relative(path, root), *arguments])


def programs(selection: str, root: Path = ROOT) -> list[str]:
    """Die Programme, die die Slicertests einer Auswahl verlangen."""
    paths: list[Path] = []
    for part in selection.split(";"):
        words = shlex.split(part)
        if words:
            paths.append(root / words[0].split("::", 1)[0])
    _windowed, found = list_windowed_tests.collect_ci_selection(paths, confcutdir=root)
    return sorted({program for wanted in found.values() for program in wanted})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="*", help="geänderte Dateien; leer: aus --diff")
    parser.add_argument("--diff", default=DEFAULT_DIFF, help=f"Git-Diff, Vorgabe {DEFAULT_DIFF}")
    parser.add_argument("--programs", metavar="AUSWAHL", help="Programme einer Slicerauswahl")
    arguments = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if arguments.programs is not None:
        print(" ".join(programs(arguments.programs)))
        return 0
    changed = [Path(name).resolve() for name in arguments.files] or changed_in(arguments.diff)
    windows, slicers = select(changed)
    print("fenster: " + "; ".join(windows))
    print("slicer: " + "; ".join(slicers))
    if windows:
        print(f'gh workflow run fenster-auswahl.yml --ref main -f tests="{"; ".join(windows)}"')
    if slicers:
        print(f'gh workflow run slicer-auswahl.yml --ref main -f tests="{"; ".join(slicers)}"')
    if not windows and not slicers:
        print("Kein Fenster- und kein Slicertest hängt an dieser Änderung.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
