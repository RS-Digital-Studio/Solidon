"""Welche Testdateien eine Änderung berührt — aus dem Importgraphen, nicht aus dem Gefühl.

    .venv\\Scripts\\python.exe tools/affected_tests.py                 # geänderte Dateien aus git
    .venv\\Scripts\\python.exe tools/affected_tests.py app/core/units.py  # oder ausdrücklich
    .venv\\Scripts\\python.exe tools/affected_tests.py --run           # und gleich fahren

**Wofür das da ist.** Nach jeder Änderung die betroffenen Tests fahren, nicht
die ganze Suite — die dauert im geteilten Lauf fünf Minuten und braucht das
Schloss. Welche Tests „betroffen" sind, hat bisher jede Sitzung selbst
geschätzt, und die Schätzung war das Gebiet der Änderung: die Tests des
Moduls, das man angefasst hat. Genau so kamen viermal an einem Tag deutsche
Bezeichner ins Tor (``tests.md``): Die Prüfung, die *jede* Datei liest, lag
außerhalb des Gebiets.

Hier wird nicht geschätzt, sondern gelesen. Betroffen ist eine Testdatei, wenn

1. sie ein geändertes Modul importiert — auch mittelbar, auch träge in einer
   Funktion, auch nur unter ``TYPE_CHECKING``; oder
2. sie selbst geändert wurde; oder
3. sie den Baum liest statt ihn zu importieren — ``rglob``, ``walk_packages``,
   ``iterdir`` über die Quellen: Sprachregel, Kerntrennung, Fehlertexte,
   Verzeichniskarten. Diese Wächter sehen jede Änderung an ``app/`` oder
   ``tools/`` und gehören deshalb zu jeder dazu; oder
4. eine geänderte Nicht-Python-Datei bei ihrem Namen genannt wird —
   ``ROADMAP.md``, ``constraints.txt``, ein Katalog, eine Regeldatei.

Und ``tests/conftest.py`` ist die Ausnahme von allem: Wer es ändert, ändert
jeden Test.

**Was das nicht ist: das Tor.** Die Auswahl sagt, was eine Änderung *sicher*
berührt; das Tor sagt, ob der Stand *insgesamt* trägt. Vor dem Commit läuft
``/pruefen``, hier läuft, was dazwischen schnell Auskunft gibt.

**Fensterdateien fahren einzeln.** Die Auswahl teilt sich wie
``suite-getrennt.sh``: Dateien, die über ihren Fixture-Graphen ein Qt-Fenster
bauen (``list_windowed_tests.collect_windowed``), bekommen je einen eigenen
Prozess, der Rest läuft in einem Zug.
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = Path(sys.executable)

# Als Skript gestartet liegt ``tools/`` selbst im Suchpfad, das Paket darüber
# nicht — und ``split_windowed`` holt sich ``tools.list_windowed_tests``.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: Die Pakete, deren Importgraph gelesen wird. ``app`` und ``tools`` reisen
#: als Module, ``tests`` sind die Blätter.
PACKAGES = ("app", "tools", "tests")

#: Aufrufe, an denen eine Testdatei den Baum liest statt ihn zu importieren.
#: Wer so einen Wächter schreibt, benutzt eines dieser Wörter — und wer eines
#: benutzt, ohne den Baum zu lesen, bekommt einen Test zu viel, nie einen zu
#: wenig.
_TREE_READERS = re.compile(r"\b(rglob|walk_packages|iterdir|iter_modules)\s*\(")

#: Änderungen hieran betreffen jeden Test.
_EVERYTHING = frozenset({"tests/conftest.py", "pyproject.toml", "constraints.txt"})


def module_name(path: Path, root: Path = ROOT) -> str:
    """``app/core/units.py`` → ``app.core.units``; ``app/core/__init__.py`` → ``app.core``."""
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_of(path: Path, name: str) -> set[str]:
    """Jedes Importziel der Datei als Modulname — eifrig, träge und für Typen."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        # Ein fremder Zwischenstand im geteilten Baum. Die Datei zählt als
        # Blatt ohne Kanten; ihr eigener Lauf sagt dann, was los ist.
        return set()
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                target = ".".join([*base, node.module] if node.module else base)
            else:
                target = node.module or ""
            found.add(target)
            found.update(f"{target}.{alias.name}" for alias in node.names)
    return found


class ImportGraph:
    """Wer importiert wen — über ``app``, ``tools`` und ``tests``."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self.modules: dict[str, Path] = {}
        for package in PACKAGES:
            folder = root / package
            if not folder.is_dir():
                continue
            for path in sorted(folder.rglob("*.py")):
                if "__pycache__" in path.parts:
                    continue
                self.modules[module_name(path, root)] = path
        self.importers: dict[str, set[str]] = defaultdict(set)
        for name, path in self.modules.items():
            for target in imports_of(path, name):
                resolved = self.resolve(target)
                if resolved is not None and resolved != name:
                    self.importers[resolved].add(name)

    def resolve(self, target: str) -> str | None:
        """Das längste existierende Modul, auf das ein Importziel zeigt."""
        parts = target.split(".")
        while parts:
            candidate = ".".join(parts)
            if candidate in self.modules:
                return candidate
            parts.pop()
        return None

    def dependents(self, names: Iterable[str]) -> set[str]:
        """Alle Module, die eines der genannten mittelbar importieren."""
        seen: set[str] = set()
        queue = list(names)
        while queue:
            current = queue.pop()
            for importer in self.importers.get(current, ()):
                if importer not in seen:
                    seen.add(importer)
                    queue.append(importer)
        return seen


def changed_files(root: Path = ROOT) -> list[Path]:
    """Was gegenüber HEAD anders ist — geändert, gestaged oder neu."""
    files: set[str] = set()
    for arguments in (
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        finished = subprocess.run(
            arguments, capture_output=True, text=True, check=True, cwd=root, encoding="utf-8"
        )
        files.update(line.strip() for line in finished.stdout.splitlines() if line.strip())
    return sorted(root / name for name in files)


def _tree_readers(graph: ImportGraph) -> set[str]:
    found: set[str] = set()
    for name, path in graph.modules.items():
        if name.startswith("tests.") and _TREE_READERS.search(path.read_text(encoding="utf-8")):
            found.add(name)
    return found


def _folder_pattern(folder: str) -> str:
    """Der Ordnername, wie er in einem Pfadausdruck steht.

    Gesucht wird er zwischen Anführungszeichen oder Schrägstrichen, damit
    ``"changelog"`` und ``"website/changelog"`` treffen, ein Bezeichner wie
    ``changelog_seiten`` aber nicht — sonst zöge jede Datei jeden Nachbarn
    mit herein.
    """
    return "[\"'/]" + re.escape(folder) + "[\"'/]"


def _named_readers(graph: ImportGraph, file: Path) -> set[str]:
    """Testdateien, die von einer Nicht-Python-Datei abhängen — auf zwei Wegen.

    **Der Name allein genügt nicht, und das hat am 03.09.2026 eine CI-Runde
    gekostet.** Für eine geänderte ``changelog/de.md`` nannte diese Funktion
    ``test_changelog`` und ``test_changes_view``, aber nicht
    ``test_changelog_website`` — und genau der wurde rot, weil die erzeugten
    Seiten fehlten. Der Grund: Diese Datei liest den Changelog nie beim Namen.
    Sie ruft ``tools.make_changelog.path_for(language)``, und der Pfad entsteht
    dort aus ``available_languages()``.

    Gefragt wird deshalb zweierlei: Wer nennt die **Datei**, und wer hängt an
    einem Modul, das ihr **Verzeichnis** nennt? Der zweite Weg findet, was über
    ein Werkzeug gelesen wird — und das ist bei jeder Datendatei die Regel und
    nicht die Ausnahme.
    """
    found: set[str] = set()
    for name, path in graph.modules.items():
        if name.startswith("tests.") and file.name in path.read_text(encoding="utf-8"):
            found.add(name)

    # Der Ordner, in dem die Datei liegt — ``changelog``, ``locales``,
    # ``data``. Module, die ihn im Quelltext nennen, lesen die Datei.
    #
    # **Nur die direkten Importeure dieser Leser, nicht die ganze Kette.** Die
    # erste Fassung nahm ``graph.dependents`` und machte aus zwei Testdateien
    # fünfundvierzig: ``app.ui.update_dialog`` nennt den Changelog, und über
    # die Oberfläche hängt daran fast jede Datei. Formal richtig, praktisch
    # wertlos — eine Auswahl, die zur Suite wird, sagt nichts mehr. Wer eine
    # Datendatei ändert, will die Tests der Module sehen, die sie lesen; wer
    # das ganze Fenster prüfen will, fährt das Tor.
    folder = file.parent.name
    if folder and folder not in {"", ".", "website"}:
        for name, path in graph.modules.items():
            if name.startswith("tests.") or not re.search(
                _folder_pattern(folder), path.read_text(encoding="utf-8")
            ):
                continue
            found.update(
                importer
                for importer in graph.importers.get(name, ())
                if importer.startswith("tests.")
            )
    return found


def affected(
    changed: Iterable[Path], graph: ImportGraph | None = None
) -> tuple[set[Path], dict[Path, str]]:
    """Die betroffenen Testdateien und je Datei der Grund.

    Ein leeres Ergebnis heißt: Nichts unter ``tests/`` hängt an der Änderung —
    was bei einer reinen Doku-Änderung stimmt und bei einer Codeänderung ein
    Zeichen ist, dass ein Test fehlt.
    """
    graph = graph or ImportGraph()
    reasons: dict[Path, str] = {}
    changed_modules: set[str] = set()
    touches_code = False
    for path in changed:
        relative = (
            path.relative_to(graph.root).as_posix() if path.is_absolute() else path.as_posix()
        )
        if relative in _EVERYTHING:
            for name, test_path in graph.modules.items():
                if name.startswith("tests.") and test_path.name.startswith("test_"):
                    reasons.setdefault(test_path, f"{relative} betrifft jeden Test")
            continue
        if path.suffix == ".py":
            name = module_name(graph.root / relative, graph.root)
            if name in graph.modules:
                changed_modules.add(name)
                if name.startswith("tests.") and path.name.startswith("test_"):
                    reasons.setdefault(graph.modules[name], "selbst geändert")
                if name.startswith(("app.", "tools.")) or name in ("app", "tools"):
                    touches_code = True
        else:
            for name in _named_readers(graph, graph.root / relative):
                reasons.setdefault(graph.modules[name], f"nennt {path.name}")
    for name in graph.dependents(changed_modules):
        path = graph.modules[name]
        if name.startswith("tests.") and path.name.startswith("test_"):
            reasons.setdefault(path, "importiert eine geänderte Datei")
    if touches_code:
        for name in _tree_readers(graph):
            reasons.setdefault(graph.modules[name], "liest den ganzen Baum")
    return set(reasons), reasons


def split_windowed(files: Iterable[Path]) -> tuple[list[Path], list[Path]]:
    """Fensterdateien getrennt vom Rest — über denselben Weg wie das Tor."""
    from tools.list_windowed_tests import collect_windowed

    ordered = sorted(files)
    if not ordered:
        return [], []
    windowed = set(collect_windowed(ordered, confcutdir=ROOT))
    return [path for path in ordered if path in windowed], [
        path for path in ordered if path not in windowed
    ]


def commands(files: Iterable[Path]) -> list[list[str]]:
    """Die Aufrufe, die die Auswahl fahren — je Fensterdatei einer."""
    windowed, plain = split_windowed(files)
    base = [str(PYTHON), "-m", "pytest", "-q", "-m", "not performance", "-p", "no:cacheprovider"]
    lines: list[list[str]] = []
    if plain:
        lines.append([*base, *(str(path.relative_to(ROOT).as_posix()) for path in plain)])
    lines.extend([*base, str(path.relative_to(ROOT).as_posix())] for path in windowed)
    return lines


def run(lines: list[list[str]]) -> int:
    """Fährt jeden Aufruf, schreibt sein Protokoll und liest den Exit-Code sofort.

    Nicht durch eine Pipeline und nicht hinter einem ``echo`` — ``CLAUDE.md``
    führt beide Fallen; hier kommt der Code aus ``returncode``, bevor
    irgendetwas anderes läuft. Ein Riss beim Abbau nach vollständiger
    Zusammenfassung zählt nicht als rot (derselbe Maßstab wie im Tor).
    """
    failed = 0
    for arguments in lines:
        print("$", " ".join(arguments[3:]), flush=True)
        finished = subprocess.run(
            arguments, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        output = finished.stdout + finished.stderr
        summary = next(
            (
                line
                for line in reversed(output.splitlines())
                if re.match(r"^\d+ (passed|failed|error)", line.strip())
            ),
            "",
        )
        clean = summary and not re.search(r"\d+ (failed|error)", summary)
        status = "grün" if finished.returncode == 0 or clean else "ROT"
        if status == "ROT":
            failed += 1
            print(output)
        print(f"--> {status}  Exit {finished.returncode}  {summary}", flush=True)
    return failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="*", help="geänderte Dateien; leer: aus git")
    parser.add_argument("--run", action="store_true", help="die Auswahl gleich fahren")
    parser.add_argument("--split", action="store_true", help="die Aufrufe zeigen, nicht fahren")
    parser.add_argument("--why", action="store_true", help="je Datei den Grund nennen")
    arguments = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    changed = [Path(name).resolve() for name in arguments.files] or changed_files()
    if not changed:
        print("Nichts geändert.")
        return 0
    files, reasons = affected(changed)
    if not files:
        print("Keine Testdatei hängt an dieser Änderung.")
        return 0
    for path in sorted(files):
        line = path.relative_to(ROOT).as_posix()
        print(f"{line}  — {reasons[path]}" if arguments.why else line)
    total = sum(1 for path in (ROOT / "tests").glob("test_*.py"))
    if len(files) >= total * 0.8:
        # Eine Änderung an ``types.py`` oder ``errors.py`` berührt über den
        # Graphen fast jede Datei — das ist keine Schwäche der Auswahl,
        # sondern ihre Aussage. Dann ist der geteilte Lauf der ehrlichere Weg.
        print()
        print(
            f"{len(files)} von {total} Testdateien — das ist die Suite. "
            "Fahr sie als Tor (/pruefen), nicht als Auswahl."
        )
    if arguments.split:
        print()
        for arguments_line in commands(files):
            print(" ".join(arguments_line[3:]))
        return 0
    if not arguments.run:
        return 0
    print()
    return run(commands(files))


if __name__ == "__main__":
    raise SystemExit(main())
