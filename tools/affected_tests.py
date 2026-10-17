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
4. sie eine Operation oder einen Baustein beim Namen nennt, den ein
   geändertes oder mittelbar betroffenes Modul registriert
   (``@register_op(name="resize_chamber")``) — Module wie ``chamber_ops``
   lädt nur eine Namensliste, und ihre Tests importieren sie nie —, auch als
   Op eines Bausteins (``insert_pipe_clamp``); oder sie die Op über einen
   Schritt erreicht, den ein direkt importiertes Modul anlegt
   (``ingest/plan.py`` legt ``load_step`` an), über eine Projektdatei, die
   sie rechnet, oder über das ganze Register oder die Beispielprojekte
   (``REGISTRY.all()``, ``app.core.examples``); oder
5. eine geänderte Nicht-Python-Datei oder ein Skript außerhalb der Pakete
   in einer Zeichenkette genannt wird — ``ROADMAP.md``, ``constraints.txt``,
   ein Katalog, eine Regeldatei, der Hook unter ``.claude/hooks/`` —, auch
   über einen Helfer, den die Testdatei direkt importiert, oder ihr Ordner
   über seinen Pfad (``Path(__file__).parent / "data"``). Ein Kommentar oder
   Docstring nennt nichts. Eine Datendatei unter ``app/``, ``tests/data/`` oder
   ``website/`` zählt dazu wie eine Änderung an dem Modul, das sie liest:
   ``materials.toml`` wählt, was ``knowledge.profiles`` mittelbar importiert.

Gewählt werden nur Testdateien: Aus einem Helfer sammelt pytest nichts, er
steht für die Testdateien, die ihn importieren.

Und ``conftest.py`` ist die Ausnahme von allem, die unter ``tests/`` wie die an der Wurzel,
die für jede Sitzung ``load_operations()`` fährt: Wer eine ändert, ändert jeden Test.

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
import gc
import os
import re
import subprocess
import sys
import zipfile
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
PYTHON = Path(sys.executable)

# Als Skript gestartet liegt ``tools/`` selbst im Suchpfad, das Paket darüber
# nicht — und ``split_windowed`` holt sich ``tools.list_windowed_tests``.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import data_reads, tree_reads  # noqa: E402

#: Die Pakete, deren Importgraph gelesen wird — eine Quelle mit dem Auflöser (F-7).
PACKAGES = tree_reads.PACKAGES

#: Die Dekoratoren, über die ein Modul Operationen und Bausteine registriert.
_REGISTRATIONS = {"register_op": "die Operation", "register_part": "den Baustein"}

#: Ein Wort in Anführungszeichen — die Vorauswahl des Namenswegs.
_QUOTED_WORD = re.compile(r"([\"'])(\w+)\1")

#: Die Vorsätze der Ops, die ``parts/ops.py`` je Baustein registriert.
_PART_OPS = ("insert_", "create_")

#: Wo ein Modul einen Schritt einer Op anlegt: ``OperationDraft(op="load")`` oder eine
#: Funktion, die den Namen der Op liefert (``return "load_step"`` in ``ingest/plan.py``).
_CREATES = re.compile(r"\bop\s*=\s*[\"']\w+[\"']|\breturn\s+[\"']\w+[\"']")

#: Ein Projekt im Text eines Moduls, und die Ops in einer Projektdatei.
_PROJECT_NAME = re.compile(r"[\w.-]+\.p3d\b")
_PROJECT_OP = re.compile(r"\"op\"\s*:\s*\"(\w+)\"")
#: Wo Projektdateien liegen: Beispiele, Korpus, Website.
_PROJECT_FOLDERS = ("app", "tests", "website")

#: Wo Datendateien liegen, deren Leser eine Änderung an ihnen erbt.
_DATA_FOLDERS = ("app/", "tests/data/", "website/")

#: Die Register der Operationen und der Bausteine, und ihre Methoden, die jeden Eintrag
#: liefern; ``get`` und ``has`` fragen nach einem Namen.
_REGISTRIES = frozenset({"REGISTRY", "PARTS"})
_WHOLE_REGISTRY = frozenset(
    {"all", "in_registration_order", "by_category", "for_feature", "by_group", "search", "versions"}
)

#: Aufrufe, die ein Register nur als Gegenstand nehmen, nicht seine Einträge.
_NOT_OVER = frozenset({"setattr", "getattr", "type", "isinstance", "id"})

#: Das Modul, das die Beispielprojekte lädt, ihr Ordner und das Modul, das ein Projekt lädt.
_EXAMPLES = "app.core.examples"
_EXAMPLES_FOLDER = PurePosixPath("app/examples")
_PROJECT = "app.core.scene.project"

#: Änderungen hieran betreffen jeden Test — auch die ``conftest.py`` an der Wurzel, die jede
#: Sitzung vor der Sammlung lädt (CS-37).
_EVERYTHING = frozenset({"conftest.py", "tests/conftest.py", "pyproject.toml", "constraints.txt"})

#: Arbeiter für die Gruppe ``plain`` von ``--run`` — fest, nie ``-n auto`` (``tests.md``):
#: Agenten laufen nebeneinander, und eine Zahl an der Kernzahl ist eine stille Variable.
WORKERS = 4
#: Ab so vielen Dateien lohnen die Arbeiter; darunter kostet ihr Start mehr, als sie sparen.
#: Gemessen im Wechsel an Teilen der Auswahl für ``chamber_ops``: Bei acht Dateien sinkt die
#: Wanduhr auf ein Drittel für 15 % mehr CPU-Zeit, bei vier und zwei Dateien kostet der Start
#: der Arbeiter 40 bis 100 % mehr CPU-Zeit.
PARALLEL_FROM = 8


def module_name(path: Path, root: Path = ROOT) -> str:
    """``app/core/units.py`` → ``app.core.units``; ``app/core/__init__.py`` → ``app.core``."""
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_of(tree: ast.Module, name: str, *, initializer: bool) -> set[str]:
    """Jedes Importziel eines Syntaxbaums als Modulname — eifrig, träge und für Typen.

    Eine Datei mit Syntaxfehler, ein fremder Zwischenstand im geteilten Baum, kommt als
    leerer Baum (:meth:`tools.tree_reads.Resolver.tree`) und zählt als Blatt ohne Kanten; ihr
    eigener Lauf sagt dann, was los ist.
    """
    package = name if initializer else name.rpartition(".")[0]
    found: set[str] = set()
    # Ein Import ist eine Anweisung: Die Ausdrücke, die den größten Teil des Baums ausmachen,
    # brauchen keinen Gang (F-6).
    for node in tree_reads.statements(tree):
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


#: Woran ein Modul einen verzögerten Import tragen kann.
_LAZY_WORDS = re.compile(r"\bimport_module\s*\(|\binstall\(\s*__name__")


def lazy_imports(
    resolver: tree_reads.Resolver, relative: str, name: str, *, initializer: bool
) -> set[str]:
    """Verzögerte Importe als Kanten (F-3): ``import_module("app.core.scene.evaluate")``, auch
    über ``f"{__package__}.registry"`` oder eine Konstante, und die Ziele von
    ``app.core.lazy.install(__name__, _EXPORTS)`` — ``from app.core.knowledge.parts import PARTS``
    lädt ``parts/builtin.py``, und keine Importanweisung sagt es."""
    if _LAZY_WORDS.search(resolver.text(relative)) is None:
        return set()
    package = name if initializer else name.rpartition(".")[0]
    tree = resolver.tree(relative)
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        called = _called(node)
        if called == "import_module":
            target = _module_text(resolver, relative, node.args[0], name, package)
            if target and not target.startswith("."):
                found.add(target)
        elif called == "install" and len(node.args) >= 2:
            owner = _module_text(resolver, relative, node.args[0], name, package)
            table = _module_level_value(tree, node.args[1])
            if owner and isinstance(table, ast.Dict):
                found.update(
                    f"{owner}.{entry.elts[0].value}"
                    for entry in table.values
                    if isinstance(entry, ast.Tuple)
                    and entry.elts
                    and isinstance(entry.elts[0], ast.Constant)
                    and isinstance(entry.elts[0].value, str)
                )
    return found


def _module_text(
    resolver: tree_reads.Resolver, relative: str, node: ast.expr, name: str, package: str
) -> str | None:
    """Ein Modulname als Text: Konstante, ``__name__``, ``__package__`` oder ein f-String aus
    ihnen; sonst ``None``."""
    if isinstance(node, ast.Name) and node.id in ("__name__", "__package__"):
        return name if node.id == "__name__" else package
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        for part in node.values:
            inner = part.value if isinstance(part, ast.FormattedValue) else part
            text = _module_text(resolver, relative, inner, name, package)
            if text is None:
                return None
            pieces.append(text)
        return "".join(pieces)
    value = resolver.value_at(relative, node)
    return value if isinstance(value, str) else None


def _module_level_value(tree: ast.Module, node: ast.expr) -> ast.expr | None:
    """Der Wert, an den ein Name auf Modulebene einmal gebunden ist."""
    if not isinstance(node, ast.Name):
        return node
    found = [
        statement.value
        for statement in tree.body
        if (
            isinstance(statement, ast.Assign)
            and any(isinstance(one, ast.Name) and one.id == node.id for one in statement.targets)
        )
        or (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == node.id
        )
    ]
    return found[0] if len(found) == 1 else None


class ImportGraph:
    """Wer importiert wen — über ``app``, ``tools`` und ``tests``."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self._strings: dict[str, tuple[str, ...]] = {}
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
            # Über den Auflöser: Jede Datei wird je Lauf einmal gelesen und geparst, und was
            # die Auswahl danach fragt, liest denselben Baum (F-6).
            relative = path.relative_to(root).as_posix()
            initializer = path.name == "__init__.py"
            tree = self.resolver.tree(relative)
            targets = imports_of(tree, name, initializer=initializer)
            targets |= lazy_imports(self.resolver, relative, name, initializer=initializer)
            for target in targets:
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
        """Der statische Auflöser für Ordner, einer je Graph — er liest und parst jede Datei
        einmal, für den Graphen wie für jede Frage danach."""
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

    @functools.cached_property
    def _facts(self) -> tree_reads.Facts:
        """Was je Datei gilt — einmal je Graph, für die Leser über Python und über alles."""
        return tree_reads.Facts()

    def _reads(self, *, python_only: bool) -> dict[str, list[tree_reads.Borrowed]]:
        analysis = tree_reads.TreeReads(
            self.root,
            self.modules,
            self.importers,
            self.resolver,
            python_only=python_only,
            facts=self._facts,
        )
        return analysis.readers(
            path.relative_to(self.root).as_posix()
            for name, path in self.modules.items()
            if _is_test_file(self, name)
        )

    def strings(self, name: str) -> tuple[str, ...]:
        """Die Zeichenketten eines Moduls — was es nennt. Docstrings und bloße Texte als
        Anweisung zählen nicht, Kommentare stehen gar nicht im Baum."""
        if name not in self._strings:
            relative = self.modules[name].relative_to(self.root).as_posix()
            tree = self.resolver.tree(relative)
            self._strings[name] = _strings_of(tree)
        return self._strings[name]

    def text(self, name: str) -> str:
        """Der Text eines Moduls, über den Auflöser einmal je Lauf gelesen."""
        return self.resolver.text(self.modules[name].relative_to(self.root).as_posix())

    def names_in_strings(self, name: str, word: str) -> bool:
        """Ob das Modul ``word`` in einer seiner Zeichenketten nennt; erst der Text, dann der
        Baum."""
        return word in self.text(name) and any(word in text for text in self.strings(name))

    @functools.cached_property
    def quoted(self) -> dict[str, set[str]]:
        """Je Wort in Anführungszeichen die Testdateien, die es so im Text tragen — die
        Vorauswahl des Namenswegs; ob es eine Zeichenkette ist, sagt erst :meth:`strings`."""
        found: dict[str, set[str]] = defaultdict(set)
        for name in self.modules:
            if _is_test_file(self, name):
                for match in _QUOTED_WORD.finditer(self.text(name)):
                    found[match.group(2)].add(name)
        return found

    @functools.cached_property
    def creators(self) -> dict[str, set[str]]:
        """Je Op-Name die Module außerhalb der Testdateien, die einen Schritt von ihr anlegen
        (:data:`_CREATES`) — ``ingest/plan.py`` für ``load`` und ``load_step``."""
        found: dict[str, set[str]] = defaultdict(set)
        for name in self.modules:
            if _is_test_file(self, name) or _CREATES.search(self.text(name)) is None:
                continue
            relative = self.modules[name].relative_to(self.root).as_posix()
            for node in ast.walk(self.resolver.tree(relative)):
                value = (
                    node.value
                    if isinstance(node, ast.Return)
                    or (isinstance(node, ast.keyword) and node.arg == "op")
                    else None
                )
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    found[value.value].add(name)
        return found

    @functools.cached_property
    def projects(self) -> dict[PurePosixPath, frozenset[str]]:
        """Je Projektdatei (``*.p3d``) die Ops, die ihr Laden rechnet."""
        found: dict[PurePosixPath, frozenset[str]] = {}
        for folder in _PROJECT_FOLDERS:
            if not (self.root / folder).is_dir():
                continue
            for path in sorted((self.root / folder).rglob("*.p3d")):
                try:
                    with zipfile.ZipFile(path) as archive:
                        text = "".join(
                            archive.read(member).decode("utf-8", "replace")
                            for member in archive.namelist()
                            if member.endswith(".json")
                        )
                except OSError, zipfile.BadZipFile:
                    continue
                relative = PurePosixPath(path.relative_to(self.root).as_posix())
                found[relative] = frozenset(_PROJECT_OP.findall(text))
        return found

    @functools.cached_property
    def project_mentions(self) -> dict[str, set[str]]:
        """Je Name einer Projektdatei die Module, die ihn im Text tragen — die Vorauswahl."""
        found: dict[str, set[str]] = defaultdict(set)
        for name in self.modules:
            if ".p3d" in self.text(name):
                for match in _PROJECT_NAME.finditer(self.text(name)):
                    found[match.group(0)].add(name)
        return found

    @functools.cached_property
    def over_everything(self) -> dict[str, str]:
        """Die Module unter ``tests/`` und ``tools/``, die über das ganze Register oder die
        Beispielprojekte gehen, je mit dem Grund (:func:`_goes_over_everything`)."""
        found: dict[str, str] = {}
        for name in self.modules:
            if name.startswith(("tests.", "tools.")):
                reason = _goes_over_everything(self, name)
                if reason is not None:
                    found[name] = reason
        return found

    def loading_conftests(self, name: str) -> list[str]:
        """Die ``conftest.py``, die ``name`` beim Laden mittelbar importieren."""
        return sorted(
            conftest for conftest, loaded in self._conftest_loads.items() if name in loaded
        )

    @functools.cached_property
    def _conftest_loads(self) -> dict[str, set[str]]:
        """Je ``conftest.py`` die Module, die ihr Laden mittelbar importiert."""
        forward: dict[str, set[str]] = defaultdict(set)
        for target, importers in self.importers.items():
            resolved = self.resolve(target)
            for importer in importers:
                forward[importer].update(one for one in (target, resolved) if one in self.modules)
        found: dict[str, set[str]] = {}
        for conftest in self._conftests:
            relative = conftest.relative_to(self.root).as_posix()
            name = module_name(conftest, self.root)
            start = (
                forward.get(name, set())
                if name in self.modules
                else {
                    one
                    for one in map(
                        self.resolve,
                        imports_of(self.resolver.tree(relative), name, initializer=False),
                    )
                    if one is not None
                }
            )
            seen = set(start)
            queue = list(start)
            while queue:
                for one in forward.get(queue.pop(), ()):
                    if one not in seen:
                        seen.add(one)
                        queue.append(one)
            found[relative] = seen
        return found

    @functools.cached_property
    def _conftests(self) -> list[Path]:
        """Jede ``conftest.py`` unter den Paketen und die an der Wurzel."""
        found = [path for path in self.modules.values() if path.name == "conftest.py"]
        if (self.root / "conftest.py").is_file():
            found.append(self.root / "conftest.py")
        return sorted(found)

    @functools.cached_property
    def per_test(self) -> dict[str, str]:
        """Je Modul, das eine ``conftest.py`` für jeden Test ausführt, deren Ort
        (:func:`_run_for_every_test`) — einmal je Graph."""
        found: dict[str, str] = {}
        for conftest in self._conftests:
            relative = conftest.relative_to(self.root).as_posix()
            for name in sorted(_run_for_every_test(self, relative)):
                found.setdefault(name, relative)
        return found


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
        if not statement.search(graph.text(name)):
            continue
        tree = graph.resolver.tree(path.relative_to(graph.root).as_posix())
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


def _direct_tests(graph: ImportGraph, name: str) -> list[str]:
    """Die Testdateien, die ``name`` direkt importieren, sortiert — ein Glied, nicht die Kette:
    ``tests/helpers.py`` importieren fast 200 Testdateien, und über einen Zwischenhelfer hinge
    jede an jeder Zeichenkette, die er nennt (RQ-2)."""
    return sorted(one for one in graph.importers.get(name, ()) if _is_test_file(graph, one))


def _strings_of(tree: ast.Module) -> tuple[str, ...]:
    """Jede Zeichenkette im Baum außer Docstrings, Texten, die als Anweisung allein stehen, und
    den Argumentnamen von ``parametrize`` — die nennen einen Parameter, keine Datei und keine
    Operation (``parametrize("pattern", …)``); die festen Teile eines f-Strings zählen mit."""
    skipped = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called(node) == "parametrize":
            names = [*node.args[:1], *(one.value for one in node.keywords if one.arg == "argnames")]
            for argument in names:
                parts = argument.elts if isinstance(argument, (ast.Tuple, ast.List)) else [argument]
                skipped.update(id(part) for part in parts if isinstance(part, ast.Constant))
    return tuple(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in skipped
    )


def _called(node: ast.Call) -> str:
    """Der Name der gerufenen Funktion: ``f`` für ``f(…)`` und ``a.b.f(…)``."""
    function = node.func
    return function.attr if isinstance(function, ast.Attribute) else getattr(function, "id", "")


def _tree_readers(
    graph: ImportGraph, paths: Iterable[PurePosixPath]
) -> dict[str, tuple[str, frozenset[str]]]:
    """Die Testdateien, die den Ordner einer dieser Dateien lesen, je mit dem Grund und den
    Einheiten, die ihn lesen (:attr:`tools.tree_reads.Borrowed.unit`).

    Was eine Testdatei liest, sagt :mod:`tools.tree_reads` — selbst oder über eine
    Definition, die sie bezieht (``source_tree.python_files``, ``code_facts.source_files``,
    ``application_sources`` aus ``test_text_length``). Gewählt wird, wessen Lesestelle den
    Pfad mit Ordner und Muster deckt (:meth:`tools.tree_reads.Read.covers`).
    """
    wanted = list(paths)
    found: dict[str, tuple[str, frozenset[str]]] = {}
    python = all(path.suffix == ".py" for path in wanted)
    for relative, borrowed in sorted((graph.reads if python else graph.all_reads).items()):
        hits = [one for path in wanted for one in borrowed if one.read.covers(path)]
        if not hits:
            continue
        hit = hits[0]
        what = f"liest {hit.read.describe()}"
        reason = (
            f"{what} ({hit.read.site})"
            if hit.lender == relative
            else f"{what} über {hit.read.site}"
        )
        found[module_name(graph.root / relative, graph.root)] = (
            reason,
            frozenset(one.unit for one in hits),
        )
    return found


def _registered(graph: ImportGraph, name: str) -> list[tuple[str, str]]:
    """Die Operationen und Bausteine, die ein Modul registriert: ``(was, name)``, statisch aus
    ``register_op(name=…)`` und ``register_part(name=…)``."""
    if not any(word in graph.text(name) for word in _REGISTRATIONS):
        return []
    relative = graph.modules[name].relative_to(graph.root).as_posix()
    tree = graph.resolver.tree(relative)
    found: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        called = _called(node)
        if called not in _REGISTRATIONS:
            continue
        for keyword in node.keywords:
            if keyword.arg == "name":
                value = graph.resolver.value_at(relative, keyword.value)
                if isinstance(value, str):
                    found.append((_REGISTRATIONS[called], value))
                    if called == "register_part":
                        # Je Baustein entstehen die Ops ``insert_<name>`` und, steht er
                        # allein, ``create_<name>`` (``parts/ops.py``) — Tests rufen diese.
                        found.extend(("die Operation", f"{one}{value}") for one in _PART_OPS)
    return found


def _name_readers(graph: ImportGraph, name: str) -> dict[str, str]:
    """Die Testdateien, die eine Operation oder einen Baustein des Moduls ``name`` nennen.

    ``chamber_ops``, ``closure_ops``, ``scene.ops`` und ``parts.panels`` lädt nur eine
    Namensliste; ihre Tests rufen die Ops über das Register und importieren das Modul nie
    (CS-31). Eine Kante über die Modulliste hinge jede Op an ``bootstrap`` — daran hängen neun
    von zehn Testdateien —, die Namen der Ops treffen je eine Handvoll.
    """
    found: dict[str, str] = {}
    for label, registered in _registered(graph, name):
        for test in sorted(graph.quoted.get(registered, ())):
            if test not in found and registered in graph.strings(test):
                found[test] = f"nennt {label} {registered}"
    return found


def _goes_over_everything(graph: ImportGraph, name: str) -> str | None:
    """Ob das Modul jede Operation erreicht, ohne eine beim Namen zu nennen — und wie.

    ``test_registry_consistency`` geht über ``REGISTRY.all()``, ``test_examples`` rechnet die
    Beispielprojekte; beide führen die Ops von ``chamber_ops`` aus, und keine nennt
    ``resize_chamber``. Über das ganze Register geht, wer ``REGISTRY`` oder ``PARTS`` mit einer
    Methode liest, die jeden Eintrag liefert, darüber eine Schleife legt oder es einer Funktion
    übergibt (``operation_rows(REGISTRY, …)``); ``REGISTRY.get("create_box")`` fragt nach
    einem Namen, ``monkeypatch.setattr(REGISTRY, …)`` nimmt das Register als Gegenstand. Die
    Beispielprojekte rechnet, wer ``app.core.examples`` importiert oder einen Pfad in
    ``app/examples`` nennt und Projekte lädt — wer die Dateien nur listet
    (``test_asset_rights``), rechnet nichts.
    """
    if name in graph.importers.get(_EXAMPLES, ()):
        return "rechnet die Beispielprojekte"
    text = graph.text(name)
    if (
        "examples" in text
        and name in graph.importers.get(_PROJECT, ())
        and _reads_folder(graph, name, _EXAMPLES_FOLDER, _EXAMPLES_FOLDER)
    ):
        return "rechnet die Beispielprojekte"
    if not any(word in text for word in _REGISTRIES):
        return None
    relative = graph.modules[name].relative_to(graph.root).as_posix()
    # Vom Träger aus gefragt, nicht vom Register: So braucht der Gang keine Eltern (F-6).
    for node in ast.walk(graph.resolver.tree(relative)):
        if isinstance(node, ast.Attribute):
            whole = node.attr in _WHOLE_REGISTRY and _is_registry(node.value)
        elif isinstance(node, ast.Call):
            # Als Argument übergeben, auch als Schlüsselwort: ``rows(registry=REGISTRY)``.
            whole = _called(node) not in _NOT_OVER and any(
                _is_registry(one) for one in (*node.args, *(one.value for one in node.keywords))
            )
        elif isinstance(node, ast.For | ast.AsyncFor | ast.comprehension):
            whole = _is_registry(node.iter)
        elif isinstance(node, ast.Starred):
            whole = _is_registry(node.value)
        else:
            continue
        if whole:
            return "geht über das ganze Register"
    return None


def _run_for_every_test(graph: ImportGraph, relative: str) -> set[str]:
    """Die Module, deren Code eine ``conftest.py`` für jeden Test ausführt (CS-38).

    Das ist, was ihre Haken (``pytest_*``) und ihre ``autouse``-Fixtures importieren oder über
    einen Namen der Modulebene benutzen, was die Modulebene selbst tut (``load_operations()``
    der Wurzel, ``PROFILE_VARIABLES``), auch über Funktionen der Datei, die eines davon ruft,
    und ein Import, der nur seiner Wirkung wegen steht (``import app.ui``). Ein Modul, das die
    Datei nur lädt, gehört nicht dazu: Ein Ladefehler darin macht jeden Test rot, auch jeden
    gewählten, und sein Verhalten wirkt nur, wo es gerufen wird — das tragen Importeure und
    Kanten (Entscheidung Koordinator). Ermittelt aus der Datei, ohne Liste: Ein neuer Haken
    oder eine neue autouse-Fixture zieht ihre Module mit.
    """
    tree = graph.resolver.tree(relative)
    package = ".".join(PurePosixPath(relative).parent.parts)
    bound: dict[str, str] = {}
    imported: list[tuple[str, str]] = []
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                head = alias.asname or alias.name.split(".")[0]
                bound[head] = alias.name if alias.asname else head
                imported.append((head, alias.name))
        elif isinstance(statement, ast.ImportFrom):
            source = _imported_module(statement, package)
            for alias in statement.names:
                bound[alias.asname or alias.name] = f"{source}.{alias.name}"
        elif isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            functions[statement.name] = statement
    targets: set[str] = set()
    queue: list[ast.AST] = [
        statement
        for statement in tree.body
        if not isinstance(statement, ast.Import | ast.ImportFrom | ast.ClassDef)
        and (
            not isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef)
            or statement.name.startswith("pytest_")
            or data_reads.is_autouse(statement)
        )
    ]
    done = {one.name for one in queue if isinstance(one, ast.FunctionDef | ast.AsyncFunctionDef)}
    while queue:
        unit = queue.pop()
        if isinstance(unit, ast.FunctionDef | ast.AsyncFunctionDef):
            # Was eine autouse-Fixture anfordert, läuft mit ihr: ``def _x(tmp_path, other):``.
            for argument in (*unit.args.posonlyargs, *unit.args.args, *unit.args.kwonlyargs):
                if argument.arg in functions and argument.arg not in done:
                    done.add(argument.arg)
                    queue.append(functions[argument.arg])
        for node in ast.walk(unit):
            if isinstance(node, ast.Import):
                targets.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                source = _imported_module(node, package)
                targets.add(source)
                targets.update(f"{source}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Name | ast.Attribute) and isinstance(node.ctx, ast.Load):
                chain = _dotted(node)
                if chain is None:
                    continue
                head, _dot, rest = chain.partition(".")
                if head in bound:
                    targets.add(f"{bound[head]}.{rest}" if rest else bound[head])
                if head in functions and head not in done:
                    done.add(head)
                    queue.append(functions[head])
    every_name = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    # Ein Import, dessen Name nie gelesen wird, steht seiner Wirkung wegen.
    targets.update(module for head, module in imported if head not in every_name)
    return {
        resolved
        for resolved in (graph.resolve(one) for one in targets)
        if resolved is not None and not _is_test_file(graph, resolved)
    }


def _imported_module(statement: ast.ImportFrom, package: str) -> str:
    """Das Modul hinter ``from … import``, auch relativ zu ``package``."""
    if not statement.level:
        return statement.module or ""
    base = package.split(".") if package else []
    base = base[: len(base) - (statement.level - 1)] if statement.level > 1 else base
    return ".".join([*base, statement.module] if statement.module else base)


def _dotted(node: ast.expr) -> str | None:
    """``a.b.c`` als Text; ``None`` für alles, was nicht mit einem Namen beginnt."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return ".".join([node.id, *reversed(parts)])


def _is_registry(node: ast.expr) -> bool:
    """Ob ``node`` ``REGISTRY`` oder ``PARTS`` liest — als Name oder als letztes Glied."""
    if isinstance(node, ast.Name):
        word = node.id
    elif isinstance(node, ast.Attribute):
        word = node.attr
    else:
        return False
    return word in _REGISTRIES and isinstance(node.ctx, ast.Load)


def _loaders(
    graph: ImportGraph, registering: Iterable[str]
) -> tuple[dict[str, str], list[PurePosixPath]]:
    """Wer eine Op dieser Module über einen Schritt oder eine Datei erreicht, ohne sie zu nennen:
    Module, die einen Schritt von ihr anlegen (``ingest/plan.py`` legt ``load`` und
    ``load_step`` an, ``test_import_placement`` ruft nur ``import_plan``), und Module, die eine
    Projektdatei mit ihr beim Namen laden (``test_orphans`` lädt ``weg4-stein-formen.p3d``, die
    ``sculpt_strokes`` rechnet). Dazu die Projektdateien selbst, für die, die sie über einen
    Ordner lesen.
    """
    owners = set(registering)
    ops = {op for name in owners for _label, op in _registered(graph, name)}
    found: dict[str, str] = {}
    for op in sorted(ops):
        for creator in sorted(graph.creators.get(op, set()) - owners):
            found.setdefault(creator, f"legt einen Schritt {op} an")
    projects = sorted(path for path, inside in graph.projects.items() if inside & ops)
    for path in projects:
        op = min(graph.projects[path] & ops)
        for module in sorted(graph.project_mentions.get(path.name, set())):
            if graph.names_in_strings(module, path.name):
                found.setdefault(module, f"lädt {path.name} mit {op}")
    return found, projects


def _data_readers(
    graph: ImportGraph, file: PurePosixPath, *, source: bool = False, units: bool = False
) -> list[str]:
    """Die Module, die eine Datendatei unter ``app/``, ``tests/data/`` oder ``website/`` lesen;
    eine Änderung an der Datei ist eine Änderung an ihnen (Entscheidung Koordinator).

    Gelesen wird über einen Pfad, der sich auf die Datei auflöst
    (``_DATA_DIR / "printers.toml"``), über einen offenen Namen im Ordner, wenn das Modul die
    Datei als Text nennt (``_DATA_DIR / table`` mit ``_shipped("materials.toml")``), oder über
    eine Lesestelle, deren Ordner und Muster die Datei decken (``LOCALES.glob("*.json")``).
    Nur aufgelöste Orte zählen — ein offener Ordner läse jede Datei —, und nur ein Muster, das
    eine Art Datei meint: ``make_installer`` kopiert ``app/**/*`` und hinge sonst mit
    163 Testdateien an jeder ``CLAUDE.md``.

    Mit ``source`` ist die Datei Python, gleich wo sie liegt, und gelesen wird sie nur über einen
    Pfad, der ihren vollen Namen trägt: ``app/i18n/extract.py`` liest die Erzeuger unter
    ``tools/`` als Quelltext (``EXTRA_SOURCES``) für ``test_translations`` (F-2). Eine
    Lesestelle über einen Ordner mit Python wählt dort schon :func:`_tree_readers`, und als
    Leser hinge sonst jede Änderung unter ``app/`` an allem, was ``extract`` importiert.

    Mit ``units`` bleiben die Module unter ``tests/`` draußen: Sie lesen je Einheit
    (:mod:`tools.data_reads`).
    """
    folder = re.compile(_folder_pattern(file.parent.name))
    stem = re.compile(f"[\"']{re.escape(file.stem)}[\"']")
    found: list[str] = []
    for name, path in graph.modules.items():
        if units and name.startswith("tests."):
            continue
        # Erst der Text: die Datei beim Namen, oder ihr Ordner neben einer Lesestelle.
        text = graph.text(name)
        if file.name not in text and (
            source
            or (
                stem.search(text) is None
                and (folder.search(text) is None or tree_reads.READ_WORDS.search(text) is None)
            )
        ):
            continue
        if _reads_data(graph, name, path.relative_to(graph.root).as_posix(), file, source=source):
            found.append(name)
    return found


def _reads_data(
    graph: ImportGraph, name: str, relative: str, file: PurePosixPath, *, source: bool = False
) -> bool:
    """Ob das Modul ``name`` die Datei ``file`` liest (:func:`_data_readers`)."""
    resolver = graph.resolver
    tree = resolver.tree(relative)
    names = {file.name} if source else {file.name, file.stem}
    named = bool(names & set(graph.strings(name)))
    for node in ast.walk(tree):
        if not data_reads.is_path_expression(node):
            continue
        assert isinstance(node, ast.expr)
        values = tree_reads.options(resolver.value_at(relative, node))
        if any(isinstance(one, tree_reads.Place) and one.parts == file.parts for one in values):
            return True
        if not named or all(isinstance(one, tree_reads.Place) for one in values):
            continue
        base: ast.expr | None = None
        if isinstance(node, ast.BinOp):
            base = node.left
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            base = node.func.value
        if base is not None:
            left = resolver.value_at(relative, base)
            if isinstance(left, tree_reads.Place) and left.parts == file.parent.parts:
                return True
    if source:
        return False
    for site in tree_reads.sites(resolver, relative):
        for read in tree_reads.evaluate_site(resolver, site, None):
            if (
                isinstance(read.folder, tree_reads.Place)
                and read.pattern[-1] != "*"
                and read.covers(file)
            ):
                return True
    return False


def _folder_pattern(folder: str) -> str:
    """Der Ordnername, wie er in einem Pfadausdruck steht.

    Gesucht wird er zwischen Anführungszeichen oder Schrägstrichen, damit
    ``"changelog"`` und ``"website/changelog"`` treffen, ein Bezeichner wie
    ``changelog_seiten`` aber nicht — sonst zöge jede Datei jeden Nachbarn
    mit herein.
    """
    return "[\"'/]" + re.escape(folder) + "[\"'/]"


def _named_readers(graph: ImportGraph, file: Path, *, units: bool = False) -> dict[str, str]:
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
        if not units and name.startswith("tests.") and graph.names_in_strings(name, file.name):
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
    relative = PurePosixPath(file.relative_to(graph.root).as_posix())
    folder = relative.parent
    if folder.as_posix() in {".", "website"}:
        return found
    words = [folder.name]
    if folder.parent.name not in ("", "app", "tests", "tools"):
        words.append(folder.parent.name)
    patterns = [re.compile(_folder_pattern(word)) for word in words]
    # Mit ``units`` lesen Module unter ``tests/`` je Einheit (:mod:`tools.data_reads`): Nicht
    # jede Funktion eines Helfers, der den Ordner nennt, liest die Datei.
    readers = [
        name
        for name in graph.modules
        if not (units and name.startswith("tests."))
        and any(one.search(graph.text(name)) for one in patterns)
        and _reads_folder(graph, name, folder, relative)
    ]
    # Der Namensweg oben ist der genauere und behält den Vorrang, danach
    # die Testdatei, die den Ordner selbst nennt, vor dem Importeur.
    for name in readers:
        if _is_test_file(graph, name):
            found.setdefault(name, f"nennt den Ordner {folder}/")
    for name in readers:
        if not _is_test_file(graph, name):
            for importer in _direct_tests(graph, name):
                found.setdefault(importer, f"hängt an einem Modul, das {folder}/ liest")
    return found


def _reads_folder(
    graph: ImportGraph, name: str, folder: PurePosixPath, file: PurePosixPath
) -> bool:
    """Ob das Modul ``name`` den Ordner ``folder`` nennt — über seinen Pfad, nicht über seinen
    letzten Namen (RQ-5).

    Zuerst die Pfadausdrücke: Löst sich einer auf den Ordner oder die Datei auf
    (``Path(__file__).parent / EXAMPLES_DIRNAME``), liest das Modul sie; ``tests/data`` ist
    nicht ``app/core/knowledge/data``. Bleibt ein Ausdruck offen, nachdem er bis höchstens eine
    Ebene über dem Ordner aufgelöst war (``ROOT / "website" / sprache``), zählt er auch — er
    kann in den Ordner zeigen. Dann die Texte: ``"knowledge/data"`` zählt, wenn die Teile vor
    dem Namen zum Pfad passen, ein bloßer Name nur für einen Ordner direkt unter der Wurzel
    (``"changelog"``); ein bloßes ``"data"`` als Schlüssel eines Wörterbuchs liest nichts.
    """
    relative = graph.modules[name].relative_to(graph.root).as_posix()
    tree = graph.resolver.tree(relative)
    for node in ast.walk(tree):
        if not data_reads.is_path_expression(node):
            continue
        assert isinstance(node, ast.expr)
        value = graph.resolver.value_at(relative, node)
        places = [one for one in tree_reads.options(value) if isinstance(one, tree_reads.Place)]
        if any(
            one.parts[: len(folder.parts)] == folder.parts or one.parts == file.parts
            for one in places
        ):
            return True
        if value is None and isinstance(node, ast.BinOp):
            left = graph.resolver.value_at(relative, node.left)
            if (
                isinstance(left, tree_reads.Place)
                and len(folder.parts) - 1 <= len(left.parts) < len(folder.parts)
                and folder.parts[: len(left.parts)] == left.parts
            ):
                return True
    alone = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Constant)
            or not isinstance(node.value, str)
            or id(node) in alone
        ):
            continue
        parts = [part for part in re.split(r"[\\/]", node.value) if part not in ("", ".")]
        if folder.name not in parts:
            continue
        before = tuple(parts[: parts.index(folder.name)])
        if before and folder.parts[:-1][-len(before) :] == before:
            return True
        if not before and len(folder.parts) == 1:
            return True
    return False


def _note_readers(graph: ImportGraph, reasons: dict[Path, str], found: dict[str, str]) -> None:
    """Trägt die Leser einer Datei ein: Testdateien selbst, für einen Helfer die Testdateien,
    die ihn direkt importieren.

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
        for test in _direct_tests(graph, name):
            reasons.setdefault(graph.modules[test], f"über {helper}: {found[name]}")


def affected(
    changed: Iterable[Path], graph: ImportGraph | None = None
) -> tuple[set[Path], dict[Path, str]]:
    """Die betroffenen Testdateien und je Datei der Grund.

    Ein leeres Ergebnis heißt: Nichts unter ``tests/`` hängt an der Änderung —
    was bei einer reinen Doku-Änderung stimmt und bei einer Codeänderung ein
    Zeichen ist, dass ein Test fehlt.
    """
    found = selection(changed, graph)
    return set(found.reasons), found.reasons


@dataclass(frozen=True)
class Selection:
    """Die betroffenen Testdateien, je mit dem Grund — und für die, die allein eine Lesestelle
    gewählt hat, die Einheiten, die lesen: Test, Fixture oder Klasse beim Namen, ``""`` für
    die Modulebene. ``ci_selection`` fährt die Fenster und Slicer einer solchen Datei nur,
    wenn einer ihrer Fälle eine davon erreicht (F-11)."""

    reasons: dict[Path, str]
    units: dict[Path, frozenset[str]]


def selection(changed: Iterable[Path], graph: ImportGraph | None = None) -> Selection:
    """Wie :func:`affected`, mit den lesenden Einheiten (:class:`Selection`)."""
    graph = graph or ImportGraph()
    changed = list(changed)
    for path in changed:
        relative = (
            path.relative_to(graph.root).as_posix() if path.is_absolute() else path.as_posix()
        )
        if relative in _EVERYTHING:
            # Jede Testdatei steht ganz in der Auswahl, keine nur mit ihren lesenden Einheiten —
            # was die übrigen Dateien des Diffs noch fänden, fügt weder Datei noch Einheit hinzu.
            # Durchgerechnet kostete es je Datendatei rund 40 s: Der main-Lauf über einen Diff
            # von 1 922 Dateien brach nach einer Stunde ohne Fensterauswahl ab.
            return Selection(
                {
                    test_path: f"{relative} betrifft jeden Test"
                    for name, test_path in graph.modules.items()
                    if name.startswith("tests.") and test_path.name.startswith("test_")
                },
                {},
            )
    reasons: dict[Path, str] = {}
    units: dict[Path, frozenset[str]] = {}
    changed_modules: set[str] = set()
    deleted_modules: set[str] = set()
    named_tools: list[str] = []
    #: Die Module, die eine geänderte Datendatei lesen (:data:`_DATA_FOLDERS`), je mit der Datei.
    data_readers: dict[str, str] = {}
    #: Jede geänderte Datei, neu oder gelöscht — für die, die ihren Ordner lesen.
    paths: list[PurePosixPath] = []
    #: Testdateien, die eine geänderte Python-Datei selbst über ihren Pfad lesen (F-2).
    source_tests: dict[str, str] = {}
    #: Jede geänderte Datei, die kein Python ist — für die Leser je Einheit unter ``tests/``.
    data_files: list[PurePosixPath] = []
    for path in changed:
        relative = (
            path.relative_to(graph.root).as_posix() if path.is_absolute() else path.as_posix()
        )
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
                        if reader.startswith("tests.") and graph.names_in_strings(reader, name)
                    },
                )
            else:
                # Ein Skript außerhalb der Pakete — der gemeinsame Hook, ein
                # Läufer unter ``.claude/.state/`` — importiert niemand; seine
                # Tests laden es über den Pfad und nennen dabei den Namen.
                _note_readers(graph, reasons, _named_readers(graph, graph.root / relative))
            # Wer die Datei über ihren Pfad als Quelltext liest, ändert mit ihr, was er tut —
            # ``extract.EXTRA_SOURCES`` liest die Erzeuger für ``test_translations`` (F-2).
            # Die Datei selbst (``Path(__file__)``) ist schon geändert.
            own = module_name(graph.root / relative, graph.root)
            for reader in _data_readers(graph, PurePosixPath(relative), source=True):
                if reader != own and _is_test_file(graph, reader):
                    source_tests.setdefault(reader, PurePosixPath(relative).name)
                elif reader != own:
                    data_readers.setdefault(reader, PurePosixPath(relative).name)
        else:
            # Ein Helfer unter ``tests/`` liest je Einheit (:mod:`tools.data_reads`), nicht als
            # ganzes Modul für alle, die ihn importieren.
            _note_readers(graph, reasons, _named_readers(graph, graph.root / relative, units=True))
            if relative.startswith(_DATA_FOLDERS):
                for reader in _data_readers(graph, PurePosixPath(relative), units=True):
                    data_readers.setdefault(reader, PurePosixPath(relative).name)
            data_files.append(PurePosixPath(relative))
    # Eine Datendatei ändert, was ihr Leser tut: Sie zählt wie eine Änderung an
    # ihm, mit seinen mittelbaren Importeuren (``materials.toml`` → ``knowledge.profiles``).
    for reader, file_name in sorted(data_readers.items()):
        where = graph.modules[reader].relative_to(graph.root).as_posix()
        for name in sorted({reader} | graph.dependents({reader})):
            if _is_test_file(graph, name):
                reasons.setdefault(graph.modules[name], f"hängt an {where}, das {file_name} liest")
    changed_modules.update(data_readers)
    for file in data_files:
        _note_data_units(graph, reasons, units, file)
    # Was eine ``conftest.py`` je Test ausführt, wirkt auf jede Testdatei unter ihr (CS-38).
    for name in sorted(changed_modules & graph.per_test.keys()):
        _note_group(graph, reasons, graph.per_test[name], f"führt {name} für jeden Test aus")
    dependents = graph.dependents(changed_modules)
    for name in sorted(dependents):
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
                if name.startswith("tests.") and graph.names_in_strings(name, file_name)
            },
        )
    # Eine Testdatei, die die Quelle über ihren Pfad liest, liest sie — nach den genaueren
    # Gründen oben (``nennt matrix_unit.py``).
    for test, file_name in sorted(source_tests.items()):
        for name in sorted({test} | graph.dependents({test})):
            if _is_test_file(graph, name):
                reasons.setdefault(graph.modules[name], f"liest {file_name}")
    # Ein Modul, das Ops registriert, erreichen seine Tests über die Namen — auch wenn es nur
    # mittelbar betroffen ist: ``closure_ops`` importiert ``chamber_ops``, und
    # ``test_closure_ops`` nennt nur ``resize_closure``. Wer über das ganze Register oder die
    # Beispielprojekte geht, rechnet jede Op.
    registering = [
        name
        for name in sorted(changed_modules | dependents)
        if name.startswith("app.") and name in graph.modules and _registered(graph, name)
    ]
    for name in registering:
        for test, reason in _name_readers(graph, name).items():
            reasons.setdefault(graph.modules[test], reason)
    if registering:
        _note_readers(graph, reasons, graph.over_everything)
        loaders, projects = _loaders(graph, registering)
        _note_readers(graph, reasons, loaders)
        _note_reads(graph, reasons, units, _tree_readers(graph, projects))
    if paths:
        _note_reads(graph, reasons, units, _tree_readers(graph, paths))
    # Ein Modul, das eine ``conftest.py`` nur lädt, zeigt einen Ladefehler in jedem Test — aber
    # nur, wenn einer läuft (CS-38).
    if not reasons:
        for name in sorted(changed_modules):
            for conftest in graph.loading_conftests(name):
                _note_group(graph, reasons, conftest, f"lädt {name}, und sonst wählte nichts")
    return Selection(reasons, units)


def _helper(graph: ImportGraph, name: str) -> bool:
    """Ob ``name`` ein Helfer unter ``tests/`` ist — ein Modul dort, aus dem pytest nichts
    sammelt, auch ``conftest.py``."""
    return name.startswith("tests.") and not _is_test_file(graph, name)


def _note_data_units(
    graph: ImportGraph,
    reasons: dict[Path, str],
    units: dict[Path, frozenset[str]],
    file: PurePosixPath,
) -> None:
    """Die Testdateien, die ``file`` über eine Einheit unter ``tests/`` erreichen — selbst, über
    einen Helfer, eine Fixture, die Modulebene eines Helfers beim Import oder eine
    autouse-Fixture (:class:`tools.data_reads.DataReads`)."""
    analysis = data_reads.DataReads(
        graph.root, graph.modules, graph.importers, graph.resolver, file, graph._facts
    )
    tests = {
        path.relative_to(graph.root).as_posix(): name
        for name, path in graph.modules.items()
        if _is_test_file(graph, name)
    }
    found: dict[str, tuple[str, frozenset[str]]] = {}
    for relative, borrowed in sorted(analysis.readers(tests).items()):
        hits = [one for one in borrowed if one.read.covers(file)]
        if hits:
            what, hit = analysis.reason(hits)
            site = hit.read.site
            how = f"({site})" if hit.lender == relative else f"über {site}"
            found[tests[relative]] = (f"{what} {how}", frozenset(one.unit for one in hits))
    _note_reads(graph, reasons, units, found)
    for name, path in sorted(graph.modules.items()):
        relative = path.relative_to(graph.root).as_posix()
        if not _helper(graph, name):
            continue
        hits = [one for one in analysis.import_time(relative) if one.read.covers(file)]
        if hits:
            for test in sorted(graph.dependents({name})):
                if _is_test_file(graph, test):
                    reasons.setdefault(
                        graph.modules[test], f"über {relative}: liest {file} beim Import"
                    )
        if path.name == "conftest.py" and any(
            one.read.covers(file) for one in analysis.autouse_reads(relative)
        ):
            _note_group(graph, reasons, relative, f"liest {file} in einer autouse-Fixture")


def _note_reads(
    graph: ImportGraph,
    reasons: dict[Path, str],
    units: dict[Path, frozenset[str]],
    found: dict[str, tuple[str, frozenset[str]]],
) -> None:
    """Trägt Leser ein, die noch keinen Grund haben, mit ihren lesenden Einheiten."""
    for name, (reason, reading) in found.items():
        path = graph.modules[name]
        if path not in reasons:
            reasons[path] = reason
            units[path] = reading
        elif path in units:
            units[path] = units[path] | reading


def _note_group(graph: ImportGraph, reasons: dict[Path, str], conftest: str, what: str) -> None:
    """Wählt jede Testdatei unter dem Ordner einer ``conftest.py``."""
    folder = PurePosixPath(conftest).parent
    for name, path in graph.modules.items():
        relative = PurePosixPath(path.relative_to(graph.root).as_posix())
        if _is_test_file(graph, name) and relative.is_relative_to(folder):
            reasons.setdefault(path, f"{conftest} {what}")


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
    workers: int = WORKERS,
) -> list[list[str]]:
    """Die regulären Aufrufe; nur beim Release kommt je Release-Datei einer dazu."""
    windowed, plain = split_windowed(files, release=release)
    return _commands(
        windowed, plain, release=release, keyword=keyword, markexpr=markexpr, workers=workers
    )


def _commands(
    windowed: list[Path],
    plain: list[Path],
    *,
    release: bool,
    keyword: str | None = None,
    markexpr: str | None = None,
    workers: int = WORKERS,
) -> list[list[str]]:
    """Die Aufrufe: die Gruppe ``plain`` in einem Prozess, ab :data:`PARALLEL_FROM` Dateien mit
    ``workers`` Arbeitern (``0`` seriell), Release-Dateien je einzeln."""
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
        parallel = (
            ["-n", str(workers), "--dist", "worksteal"]
            if workers > 0 and len(plain) >= PARALLEL_FROM
            else []
        )
        lines.append(
            [
                *base,
                *parallel,
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


def _workers(text: str) -> int:
    """``--workers``: eine Zahl ab 0 — ``auto`` gibt es nicht."""
    try:
        value = int(text)
    except ValueError:
        value = -1
    if value < 0:
        raise argparse.ArgumentTypeError(
            f"{text!r} ist keine Arbeiterzahl — eine ganze Zahl ab 0 angeben, 0 fährt seriell"
        )
    return value


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
    parser.add_argument(
        "--workers",
        type=_workers,
        default=WORKERS,
        help=f"Arbeiter für die Tests ohne Fenster ab {PARALLEL_FROM} Dateien; 0 fährt seriell",
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
        workers=arguments.workers,
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
    # Nur als Skript: Ein kurzer Lauf, dessen Syntaxbäume bis zum Ende leben — die Bereinigung
    # von Zyklen ging immer wieder über jeden Baum und kostete ein Drittel der CPU-Zeit,
    # freigeben konnte sie nichts (gemessen im Wechsel, F-6). Ein Testprozess, der ``main``
    # ruft, behält sie.
    gc.disable()
    raise SystemExit(main())
