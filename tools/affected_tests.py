"""Welche Testdateien eine Änderung berührt — aus dem Importgraphen, nicht aus dem Gefühl.

    .venv\\Scripts\\python.exe tools/affected_tests.py                 # geänderte Dateien aus git
    .venv\\Scripts\\python.exe tools/affected_tests.py app/core/units.py  # oder ausdrücklich
    .venv\\Scripts\\python.exe tools/affected_tests.py --run           # und gleich fahren

**Wofür das da ist.** Nach jeder Änderung die betroffenen Tests fahren, nicht
die ganze Suite — die dauert im geteilten Lauf fünf Minuten. Welche Tests
„betroffen" sind, wurde bisher geschätzt, und die Schätzung war das Gebiet der
Änderung: die Tests des Moduls, das man angefasst hat. Genau so kamen viermal an einem Tag deutsche
Bezeichner ins Tor (``tests.md``): Die Prüfung, die *jede* Datei liest, lag
außerhalb des Gebiets.

Hier wird nicht geschätzt, sondern gelesen. Betroffen ist eine Testdatei, wenn

1. sie ein geändertes Modul importiert — auch mittelbar, auch träge in einer
   Funktion, auch nur unter ``TYPE_CHECKING``; oder
2. sie selbst geändert wurde; oder
3. sie den Ordner einer geänderten Datei liest statt sie zu importieren —
   ``rglob``, ``glob``, ``iterdir``, ``walk``, ``walk_packages``,
   ``git ls-files`` über die Quellen: Sprachregel, Kerntrennung,
   Fehlertexte, Sperrklinke, Verzeichniskarten —, selbst oder über eine
   Definition, die sie aus einem anderen Modul bezieht
   (``source_tree.python_files("app/ui")``, ``code_facts.source_files``).
   Ordner und Muster löst :mod:`tools.tree_reads` statisch auf; ein Ordner,
   der sich nicht auflösen lässt, liest jede Python-Datei, wenn sein Muster
   Python nennt. So wählt eine reine Teständerung die Wächter über
   ``tests/`` (``test_toolchain``, ``test_size_ratchet``,
   ``test_source_readers``), aber keinen, der nur ``app/`` liest. Unter
   ``app/`` zählt eine Lesestelle nur mit einem Ordner im Repository
   (``extract.message_ids`` → ``test_registry_dump``); oder
4. eine geänderte Nicht-Python-Datei oder ein Skript außerhalb der Pakete
   bei ihrem Namen genannt wird — ``ROADMAP.md``, ``constraints.txt``, ein
   Katalog, eine Regeldatei, der Hook unter ``.claude/hooks/`` —, auch über
   einen Helfer, der sie nennt.

Gewählt werden nur Testdateien: Aus einem Helfer sammelt pytest nichts, er
steht für die Testdateien, die ihn importieren.

Und ``tests/conftest.py`` ist die Ausnahme von allem: Wer es ändert, ändert
jeden Test.

**Was das nicht ist: das Tor.** Die Auswahl sagt, was eine Änderung *sicher*
berührt; das Tor sagt, ob der Stand *insgesamt* trägt. Auf Paket- und
Fixzweigen genügt vor dem Commit diese Auswahl mit ruff, format und mypy; vor
jedem Stand, der nach main geht, läuft ``/pruefen`` als Entwicklungstor. Hier
läuft, was dazwischen schnell Auskunft gibt.

**Fenster, Renderer und Leistung nur beim Release.** Die reine Auswahl nennt
weiter alle betroffenen Dateien. ``--run`` und ``--split`` fahren deren
Entwicklungstests ohne Fenster, echte Renderer, Erzeugnisvergleiche oder
Leistung und stellen die Releasefälle zurück. ``--release`` nimmt Fenster
und Renderer je Datei als eigene Prozesse dazu und zusätzlich
Erzeugnisvergleiche. Getrennt wird je Test, nicht je Datei — der Fixture-Graph
entscheidet wie in ``suite-getrennt.sh``. Leistungsprüfungen laufen auch beim
Release separat und niemals über dieses Werkzeug.
"""

from __future__ import annotations

import argparse
import ast
import functools
import os
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
PYTHON = Path(sys.executable)

# Als Skript gestartet liegt ``tools/`` selbst im Suchpfad, das Paket darüber
# nicht — und ``split_windowed`` holt sich ``tools.list_windowed_tests``.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import tree_reads  # noqa: E402

#: Die Pakete, deren Importgraph gelesen wird. ``app`` und ``tools`` reisen
#: als Module, ``tests`` sind die Blätter.
PACKAGES = ("app", "tools", "tests")

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
        self._texts: dict[str, str] = {}
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
            # Auch ein direkter Untermodulimport führt die Initialisierer aller
            # Elternpakete aus. Fehlende Eltern bleiben für gelöschte
            # __init__.py als Knoten erhalten, ebenso Namensraum-Pakete.
            parts = name.split(".")
            for depth in range(1, len(parts)):
                self.importers[".".join(parts[:depth])].add(name)
            for target in imports_of(path, name):
                # Auch fehlende Ziele bleiben Knoten: Nach dem Löschen
                # müssen relative und mittelbare Importe noch auffindbar sein.
                if target != name:
                    self.importers[target].add(name)
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

    @functools.cached_property
    def resolver(self) -> tree_reads.Resolver:
        """Der statische Auflöser für Ordner, einer je Graph — er parst jede Datei einmal."""
        return tree_reads.Resolver(self.root, working_root=True)

    @functools.cached_property
    def reads(self) -> dict[str, list[tree_reads.Borrowed]]:
        """Je Testdatei, relativ zur Wurzel, was sie an Python lesen kann; einmal je Graph, denn
        ``ci_selection`` und die Tests fragen für viele Änderungen."""
        return self._reads(python_only=True)

    @functools.cached_property
    def all_reads(self) -> dict[str, list[tree_reads.Borrowed]]:
        """Wie :attr:`reads`, mit jedem Muster — für eine geänderte Datei, die kein Python ist."""
        return self._reads(python_only=False)

    def _reads(self, *, python_only: bool) -> dict[str, list[tree_reads.Borrowed]]:
        analysis = tree_reads.TreeReads(
            self.root, self.modules, self.importers, self.resolver, python_only=python_only
        )
        return analysis.readers(
            path.relative_to(self.root).as_posix()
            for name, path in self.modules.items()
            if _is_test_file(self, name)
        )

    def text(self, name: str) -> str:
        if name not in self._texts:
            self._texts[name] = self.modules[name].read_text(encoding="utf-8")
        return self._texts[name]


#: ``tests/conftest.py`` lädt pytest als Plugin unter seinem bloßen Namen;
#: ``import conftest`` erreicht genau dieses geladene Modul und lädt keine
#: zweite Kopie wie der bloße Import eines anderen Helfers. Eine Änderung
#: daran betrifft ohnehin jeden Test.
_BARE_BY_DESIGN = frozenset({"conftest"})


def bare_local_imports(graph: ImportGraph) -> list[str]:
    """Importe eines Moduls aus ``tests/`` oder ``tools/`` ohne Paketpräfix, je ``Datei:Zeile``.

    ``resolve`` kennt nur ``app.…``, ``tools.…`` und ``tests.…``. Ein
    ``from render_fakes import …`` läuft trotzdem, weil pytest und ein
    Skriptstart den eigenen Ordner in den Suchpfad legen — und lädt dieselbe
    Datei als zweites Modul, dessen Kante der Graph nicht sieht: Wer
    ``render_fakes.py`` ändert, bekäme ``test_ui.py`` nicht ausgewählt.
    """
    local = {
        path.stem
        for name, path in graph.modules.items()
        if name.count(".") == 1 and name.split(".")[0] in ("tests", "tools")
    } - _BARE_BY_DESIGN
    # Erst der Text, dann der Baum: Eine Importanweisung beginnt eine logische Zeile, und
    # ohne eine, die einen dieser Namen nennt, gibt es nichts zu finden. Alle 700 Dateien
    # zu parsen kostete 14 s je Aufruf.
    names = "|".join(re.escape(stem) for stem in sorted(local)) or "(?!)"
    statement = re.compile(
        rf"(?:^|[;:])[ \t]*(?:from[ \t]+(?:{names})\b"
        rf"|import[ \t]+(?:[\w.]+(?:[ \t]+as[ \t]+\w+)?[ \t]*,[ \t]*)*(?:{names})\b)",
        re.MULTILINE,
    )
    found: list[str] = []
    for name, path in graph.modules.items():
        if name.split(".")[0] not in ("tests", "tools"):
            continue
        text = path.read_text(encoding="utf-8")
        if not statement.search(text):
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                targets = [node.module]
            else:
                continue
            found.extend(
                f"{path.relative_to(graph.root).as_posix()}:{node.lineno}: {target}"
                for target in targets
                if target.split(".")[0] in local
            )
    return sorted(found)


def changed_files(root: Path = ROOT) -> list[Path]:
    """Was gegenüber HEAD anders ist — geändert, gestaged oder neu."""
    files: set[str] = set()
    for arguments in (
        ["git", "diff", "--name-only", "--no-renames", "-z", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    ):
        finished = subprocess.run(
            arguments, capture_output=True, text=True, check=True, cwd=root, encoding="utf-8"
        )
        # -z liefert echte Pfade ohne Git-Quoting; Leerraum gehört zum Namen.
        # Ohne Umbenennungserkennung bleiben auch die alten Modulnamen dabei.
        files.update(name for name in finished.stdout.split("\0") if name)
    return sorted(root / name for name in files)


def _is_test_file(graph: ImportGraph, name: str) -> bool:
    """Ob pytest aus dem Modul Tests sammelt — ein Helfer unter ``tests/`` sammelt keine."""
    return name.startswith("tests.") and graph.modules[name].name.startswith("test_")


def _test_files_behind(graph: ImportGraph, name: str) -> list[str]:
    """Die Testdateien, die ``name`` mittelbar importieren, sortiert."""
    return sorted(one for one in graph.dependents([name]) if _is_test_file(graph, one))


def _tree_readers(graph: ImportGraph, paths: Iterable[PurePosixPath]) -> dict[str, str]:
    """Die Testdateien, die den Ordner einer dieser Dateien lesen, je mit dem Grund.

    Was eine Testdatei liest, sagt :mod:`tools.tree_reads` — selbst oder über eine
    Definition, die sie bezieht (``source_tree.python_files``, ``code_facts.source_files``,
    ``application_sources`` aus ``test_text_length``). Gewählt wird, wessen Lesestelle den
    Pfad mit Ordner und Muster deckt (:meth:`tools.tree_reads.Read.covers`).
    """
    wanted = list(paths)
    found: dict[str, str] = {}
    python = all(path.suffix == ".py" for path in wanted)
    for relative, borrowed in sorted((graph.reads if python else graph.all_reads).items()):
        hit = next((one for path in wanted for one in borrowed if one.read.covers(path)), None)
        if hit is None:
            continue
        what = f"liest {hit.read.describe()}"
        reason = (
            f"{what} ({hit.read.site})"
            if hit.lender == relative
            else f"{what} über {hit.read.site}"
        )
        found[module_name(graph.root / relative, graph.root)] = reason
    return found


def _folder_pattern(folder: str) -> str:
    """Der Ordnername, wie er in einem Pfadausdruck steht.

    Gesucht wird er zwischen Anführungszeichen oder Schrägstrichen, damit
    ``"changelog"`` und ``"website/changelog"`` treffen, ein Bezeichner wie
    ``changelog_seiten`` aber nicht — sonst zöge jede Datei jeden Nachbarn
    mit herein.
    """
    return "[\"'/]" + re.escape(folder) + "[\"'/]"


def _named_readers(graph: ImportGraph, file: Path) -> dict[str, str]:
    """Testdateien, die von einer Datei außerhalb des Importgraphen abhängen — auf zwei Wegen.

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

    **Beide Wege nennen ihren eigenen Grund**, denn ``--why`` soll erklären und
    nicht bloß behaupten: Bis zum 03.09.2026 trug auch der zweite Weg den Text
    des ersten, und für `website/api/count.php` stand dann hinter
    ``test_agent.py`` das Wort „nennt count.php" — eine Datei, die diesen
    Namen kein einziges Mal enthält. Wer dem Grund nachgeht, sucht dort
    vergeblich und traut der Auswahl danach nicht mehr.
    """
    found: dict[str, str] = {}
    for name in graph.modules:
        if name.startswith("tests.") and file.name in graph.text(name):
            found[name] = f"nennt {file.name}"

    # Der Ordner, in dem die Datei liegt — ``changelog``, ``locales``,
    # ``data``. Module, die ihn im Quelltext nennen, lesen die Datei: eine
    # Testdatei selbst, ein Modul unter ``app/`` oder ``tools/`` und ebenso ein
    # Helfer unter ``tests/`` für die Testdateien, die ihn importieren — sonst
    # fehlte ``test_packaging_platform.py``, für den nur
    # ``tests/packaging_helpers.py`` ``.github/workflows`` nennt (RPL-1).
    #
    # **Nur die direkten Importeure dieser Leser, nicht die ganze Kette.** Die
    # erste Fassung nahm ``graph.dependents`` und machte aus zwei Testdateien
    # fünfundvierzig: ``app.ui.update_dialog`` nennt den Changelog, und über
    # die Oberfläche hängt daran fast jede Datei. Formal richtig, praktisch
    # wertlos — eine Auswahl, die zur Suite wird, sagt nichts mehr. Wer eine
    # Datendatei ändert, will die Tests der Module sehen, die sie lesen; wer
    # das ganze Fenster prüfen will, fährt das Tor. Deshalb zählt auch ein
    # Helfer, der einen Leser nur importiert, nicht: Er wäre das zweite Glied.
    folder = file.parent.name
    if folder and folder not in {"", ".", "website"}:
        pattern = _folder_pattern(folder)
        readers = [name for name in graph.modules if re.search(pattern, graph.text(name))]
        # Der Namensweg oben ist der genauere und behält den Vorrang, danach
        # die Testdatei, die den Ordner selbst nennt, vor dem Importeur.
        for name in readers:
            if _is_test_file(graph, name):
                found.setdefault(name, f"nennt den Ordner {folder}/")
        for name in readers:
            if _is_test_file(graph, name):
                continue
            for importer in graph.importers.get(name, ()):
                if _is_test_file(graph, importer):
                    found.setdefault(importer, f"hängt an einem Modul, das {folder}/ liest")
    return found


def _note_readers(graph: ImportGraph, reasons: dict[Path, str], found: dict[str, str]) -> None:
    """Trägt die Leser einer Datei ein: Testdateien selbst, für einen Helfer die Testdateien,
    die ihn mittelbar importieren.

    Ein Helfer in der Auswahl sammelt keinen Test, und sein Importeur liefe
    nicht. Die Testdateien zuerst, damit ihr genauerer Grund stehen bleibt.
    """
    for name in sorted(found):
        if _is_test_file(graph, name):
            reasons.setdefault(graph.modules[name], found[name])
    for name in sorted(found):
        if _is_test_file(graph, name):
            continue
        helper = graph.modules[name].relative_to(graph.root).as_posix()
        for test in _test_files_behind(graph, name):
            reasons.setdefault(graph.modules[test], f"über {helper}: {found[name]}")


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
    deleted_modules: set[str] = set()
    named_tools: list[str] = []
    #: Jede geänderte Datei, neu oder gelöscht — für die, die ihren Ordner lesen.
    paths: list[PurePosixPath] = []
    for path in changed:
        relative = (
            path.relative_to(graph.root).as_posix() if path.is_absolute() else path.as_posix()
        )
        if relative in _EVERYTHING:
            for name, test_path in graph.modules.items():
                if name.startswith("tests.") and test_path.name.startswith("test_"):
                    reasons.setdefault(test_path, f"{relative} betrifft jeden Test")
            continue
        paths.append(PurePosixPath(relative))
        if path.suffix == ".py":
            name = module_name(graph.root / relative, graph.root)
            if name in graph.modules:
                changed_modules.add(name)
                if name.startswith("tests.") and path.name.startswith("test_"):
                    reasons.setdefault(graph.modules[name], "selbst geändert")
                if name.startswith("tools."):
                    named_tools.append(path.name)
            elif name.split(".", 1)[0] in PACKAGES:
                # Gelöschte Module und Paketinitialisierer bleiben über ihre
                # Importkanten erreichbar, auch Helfer unter tests/.
                changed_modules.add(name)
                deleted_modules.add(name)
                _note_readers(
                    graph,
                    reasons,
                    {
                        reader: f"nennt {name}, und die Datei ist gelöscht"
                        for reader in graph.modules
                        if reader.startswith("tests.") and name in graph.text(reader)
                    },
                )
            else:
                # Ein Skript außerhalb der Pakete — der gemeinsame Hook, ein
                # Läufer unter ``.claude/.state/`` — importiert niemand; seine
                # Tests laden es über den Pfad und nennen dabei den Namen.
                _note_readers(graph, reasons, _named_readers(graph, graph.root / relative))
        else:
            _note_readers(graph, reasons, _named_readers(graph, graph.root / relative))
    for name in graph.dependents(changed_modules):
        path = graph.modules[name]
        if name.startswith("tests.") and path.name.startswith("test_"):
            reasons.setdefault(
                path,
                "importiert eine gelöschte Datei"
                if deleted_modules
                else "importiert eine geänderte Datei",
            )
    # Ein Werkzeug, das beim Import ``sys.argv`` liest, laden seine Tests über
    # den Pfad — ohne Importkante. Seit die Matrix in ``tools/`` liegt, fehlte
    # ihr Prüftest in jeder Auswahl zu ihr (Review 06.10.2026, M3). Nach den
    # Importkanten, damit deren genauerer Grund stehen bleibt.
    for file_name in named_tools:
        _note_readers(
            graph,
            reasons,
            {
                name: f"nennt {file_name}"
                for name in graph.modules
                if name.startswith("tests.") and file_name in graph.text(name)
            },
        )
    if paths:
        for name, reason in _tree_readers(graph, paths).items():
            reasons.setdefault(graph.modules[name], reason)
    return set(reasons), reasons


def split_windowed(
    files: Iterable[Path], *, release: bool = False
) -> tuple[list[Path], list[Path]]:
    """Releasefälle und reguläre Dateiläufe passend zum Modus trennen.

    Eine Datei kann in beiden Listen stehen: Der reguläre Dateilauf enthält
    keine Fenster oder Renderer. Im Release kommen Erzeugnisvergleiche dazu;
    Fenster- und Rendererfälle laufen zusätzlich in der Releasegruppe.
    """
    from tools.list_windowed_tests import collect_test_groups

    ordered = sorted(files)
    if not ordered:
        return [], []
    windowed, plain = collect_test_groups(ordered, confcutdir=ROOT, include_rendered=release)
    return list(windowed), list(plain)


def commands(
    files: Iterable[Path],
    *,
    release: bool = False,
    keyword: str | None = None,
    markexpr: str | None = None,
) -> list[list[str]]:
    """Die regulären Aufrufe; nur beim Release kommt je Release-Datei einer dazu."""
    windowed, plain = split_windowed(files, release=release)
    return _commands(windowed, plain, release=release, keyword=keyword, markexpr=markexpr)


def _commands(
    windowed: list[Path],
    plain: list[Path],
    *,
    release: bool,
    keyword: str | None = None,
    markexpr: str | None = None,
) -> list[list[str]]:
    base = [
        str(PYTHON),
        "-m",
        "pytest",
        "-q",
        "-p",
        "tools.list_windowed_tests",
        "-p",
        "no:cacheprovider",
    ]
    if keyword is not None:
        base.extend(("-k", keyword))
    if markexpr is not None:
        base.extend(("-m", markexpr))
    if release:
        # Das Release-Tor fährt die Erzeugnisvergleiche mit, das Entwicklungstor nicht.
        base.append("--with-rendered")
    # Die Fenstertrennung ergänzt der Laufplugin (``--window-group``) — so
    # bleibt ein ``-m`` aus Umgebung oder Konfiguration wirksam.
    lines: list[list[str]] = []
    if plain:
        lines.append(
            [
                *base,
                "--window-group",
                "plain",
                *(str(path.relative_to(ROOT).as_posix()) for path in plain),
            ]
        )
    if release:
        lines.extend(
            [*base, "--window-group", "windowed", str(path.relative_to(ROOT).as_posix())]
            for path in windowed
        )
    return lines


def run(lines: list[list[str]]) -> int:
    """Fährt jeden Aufruf, schreibt sein Protokoll und liest den Exit-Code sofort.

    Nicht durch eine Pipeline und nicht hinter einem ``echo`` — ``CLAUDE.md``
    führt beide Fallen; hier kommt der Code aus ``returncode``, bevor
    irgendetwas anderes läuft. Auch ein Riss beim Abbau nach vollständiger
    Zusammenfassung bleibt ein Fehler (derselbe Maßstab wie im Tor).

    Jeder Lauf bekommt einen BLAS-Faden, wenn der Aufrufer keinen Wert setzt —
    derselbe Grund wie im Tor (``suite-getrennt.sh``): OpenBLAS sagt sonst je
    Prozess einen Puffer je Rechenkern zu, an 32 Kernen 1,5 GB.
    """
    environment = {
        **os.environ,
        "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS", "1"),
    }
    failed = 0
    for arguments in lines:
        print("$", " ".join(arguments[3:]), flush=True)
        finished = subprocess.run(
            arguments,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
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
        status = "grün" if finished.returncode == 0 else "ROT"
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
    parser.add_argument("-k", dest="keyword", help="nur passende Testnamen im eigentlichen Lauf")
    parser.add_argument(
        "-m", dest="markexpr", help="zusätzlicher Markerfilter im eigentlichen Lauf"
    )
    parser.add_argument(
        "--release", action="store_true", help="beim Release auch Fenster- und Rendererfälle fahren"
    )
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
    if not arguments.run and not arguments.split:
        return 0
    print()
    windowed, plain = split_windowed(files, release=arguments.release)
    deferred = sorted(set(windowed) if not arguments.release else set())
    files_without_group = sorted(files - set(plain) - set(windowed))
    if deferred:
        print("Zurückgestellt: Fenster- und Rendererfälle dieser Dateien nur mit --release.")
        for path in deferred:
            print(f"  {path.relative_to(ROOT).as_posix()}")
    if files_without_group:
        label = (
            "Nur Leistungsprüfungen — separat beim Release:"
            if arguments.release
            else "Nur Erzeugnisvergleiche oder Leistungsprüfungen — beim Release:"
        )
        print(label)
        for path in files_without_group:
            print(f"  {path.relative_to(ROOT).as_posix()}")
    lines = _commands(
        windowed,
        plain,
        release=arguments.release,
        keyword=arguments.keyword,
        markexpr=arguments.markexpr,
    )
    if not lines:
        print("Keine regulären Tests ausgewählt; kein Testlauf gestartet.")
        return 0
    if arguments.split:
        for arguments_line in lines:
            print(" ".join(arguments_line[3:]))
        return 0
    return run(lines)


if __name__ == "__main__":
    raise SystemExit(main())
