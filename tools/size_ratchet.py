"""Sperrklinke für Dateigrößen (W1, Konzept Codestruktur 4.1 und 3.1, Regel 6).

Keine ``*.py`` unter ``app/``, ``tools/`` und ``tests/`` hat mehr als 2 000 Zeilen,
außer den Dateien in ``tests/data/size_ratchet.toml``. Für jede von ihnen steht
dort die Zahl ihrer Definitionen — Funktionen, Methoden und Klassen, auch
geschachtelte, ohne Lambdas —, und **die Zahl gilt genau** (Entscheidung E3,
keine Streuzahl): Mehr heißt, eine gelistete Datei hat eine neue Definition
bekommen; weniger heißt, ein Schritt hat Code herausgelöst und die Liste nicht
gesenkt. Zeilen in bestehenden Rümpfen bleiben frei, das ist der Fix-Fall.

    python tools/size_ratchet.py               # prüfen, wie --check
    python tools/size_ratchet.py --check       # Exit 1 bei jedem Verstoß
    python tools/size_ratchet.py --lower       # senkt und trägt aus, hebt nie
    python tools/size_ratchet.py --raise app/ui/main_window.py 2 \\
        --sections MainWindow._build_file_menu MainWindow._build_edit_menu
    python tools/size_ratchet.py --move app/ui/main_window.py app/ui/main_window/window.py
    python tools/size_ratchet.py --init        # legt die Liste einmal an

``--raise`` gehört nur Ordnungsschritten (Konzept 4.3, Schritt 4c): Er hebt die
Zahl einer gelisteten Datei um genau die Abschnitte, die der Commit nennt, und
verlangt, dass gegenüber HEAD genau sie neu sind. ``--move`` trägt einen Umzug
ein (Schritt 4b): Die alte Datei fällt aus der Liste, die neuen über der Grenze
kommen hinein, wenn alles an ihnen an HEAD in der alten stand und ihre Summe
die gelistete Zahl nicht erhöht. Beide laufen vor
dem Commit des Schritts. ``--init`` legt die Liste ein einziges Mal an (Codestruktur
Schritt 0), nur aus versionierten Dateien, und verweigert sich, sobald Git die
Liste je gesehen hat: Eine gelöschte Liste neu anzulegen segnete jeden Verstoß
seit ihrem letzten Stand; fehlt sie, wird sie aus Git zurückgeholt und mit
``--lower`` gesenkt. Die Liste wächst nie um eine Datei; eine Bestandsliste,
die nur Schritte des Programms ändern, ist keine Ausnahmeliste (Regel 9).

Gezählt wird, was Git kennt (versioniert und neu, ohne ignorierte Kopien); ohne
Git jede Datei unter den drei Ordnern. Zeilen sind Zeilenumbrüche wie bei
``wc -l``, nicht ``str.splitlines()``: Das trennt auch an ``\\x0c`` und
``\\u2028`` in Zeichenketten und zählte ``tests/test_recipes.py`` eine Zeile zu
lang. Exit 0 ohne Verstoß, 1 mit Verstoß, 2, wenn das Werkzeug nicht prüfen
kann (Liste fehlt oder ist kaputt, falscher Ordner, abgelehnter Schreibweg).
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tomllib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal

ROOT: Final = Path(__file__).resolve().parent.parent

#: Die Zielgrenze aus Konzept 3.1, Regel 1: so viel liest eine Sitzung am Stück.
LIMIT: Final = 2000

#: Die Ordner, deren Dateien die Sperrklinke zählt.
AREAS: Final = ("app", "tools", "tests")

#: Die Liste, relativ zur Wurzel.
LIST: Final = "tests/data/size_ratchet.toml"

#: Der volle Wortlaut, den jede Meldung über eine neue Definition oder eine neue
#: große Datei trägt — in ``AGENTS.md`` steht Regel 6 nur als Satz.
RULES: Final = (
    "Konzept Codestruktur 3.1 (konzepte/konzept-codestruktur-2026-10.md): "
    "Regel 6 — neuer Code an einer großen Datei geht in ein neues Modul unter "
    "2 000 Zeilen, eine neue Handlung am Fenster ist eine neue Komponente (3.3), "
    "neue Tests zu einer gelisteten Datei kommen in test_<thema>_<bereich>.py (3.4). "
    "Regel 9 — eine bestehende Methode um einen fremden Fall zu verlängern, damit "
    "diese Prüfung grün bleibt, ist ein Workaround."
)

HEADER: Final = (
    "# Sperrklinke für Dateigrößen (W1, Konzept Codestruktur 4.1, Regel 6): jede *.py",
    "# unter app/, tools/ und tests/ mit mehr als 2 000 Zeilen und die Zahl ihrer",
    "# Definitionen (Funktionen, Methoden, Klassen, auch geschachtelte). Die Zahl gilt",
    "# genau. Geschrieben von tools/size_ratchet.py — --lower senkt und trägt aus,",
    "# --raise für Ordnungsschritte, --move für Umzüge —, nie von Hand. Fehlt sie oder",
    "# steht sie im Konflikt: eine Seite aus Git nehmen, dann --lower, nie --init.",
)

Kind = Literal["too_long", "new_definition", "not_lowered", "release"]

_DEFINITIONS: Final = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

#: Was Anweisungen enthalten kann: Definitionen sind Anweisungen und stehen nie
#: in einem Ausdruck, also reicht der Gang über diese Knoten. Er findet dieselbe
#: Zahl wie ``ast.walk`` und spart am Baum gut ein Fünftel der Laufzeit.
_BODIES: Final = (ast.stmt, ast.excepthandler, ast.match_case)


class RatchetError(Exception):
    """Das Werkzeug kann nicht prüfen oder lehnt einen Schritt ab; die Meldung sagt, was hilft."""


@dataclass(frozen=True, slots=True)
class Size:
    """Zeilen einer Datei und, über der Grenze, die Zahl ihrer Definitionen."""

    lines: int
    definitions: int | None


@dataclass(frozen=True, slots=True)
class Violation:
    """Ein Verstoß gegen die Sperrklinke, mit der Meldung, die sagt, was zu tun ist."""

    path: str
    kind: Kind
    message: str


def line_count(source: str) -> int:
    """Zeilen wie ``wc -l`` und wie eine Sitzung sie liest: Umbrüche plus ein offenes Ende."""
    return source.count("\n") + (1 if source and not source.endswith("\n") else 0)


def definition_names(source: str, filename: str = "<source>") -> list[str]:
    """Jede Definition der Quelle als Qualname (``Klasse.methode``, ``f.<locals>.g``)."""
    names: list[str] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _DEFINITIONS):
                name = prefix + child.name
                names.append(name)
                visit(child, name + ("." if isinstance(child, ast.ClassDef) else ".<locals>."))
            elif isinstance(child, _BODIES):
                visit(child, prefix)

    visit(ast.parse(source, filename=filename), "")
    return names


def size_of(source: str, filename: str = "<source>") -> Size:
    """Die Größe einer Quelle; Definitionen zählt nur, wer über der Grenze liegt."""
    lines = line_count(source)
    definitions = len(definition_names(source, filename)) if lines > LIMIT else None
    return Size(lines, definitions)


def measure_sources(sources: Mapping[str, str]) -> dict[str, Size]:
    """Die Größen eines Baums, der als ``{pfad: quelltext}`` vorliegt."""
    return {name: size_of(text, name) for name, text in sorted(sources.items())}


def tree_files(root: Path) -> list[str]:
    """Die ``*.py`` unter den drei Ordnern, als Pfade relativ zu ``root``.

    Mit Git versioniert und neu, ohne ignorierte Kopien — eine neue große Datei
    ist rot, bevor sie committet wird. Ohne Git (ausgepackter Baum, Attrappe)
    jede Datei darunter.
    """
    if is_git_tree(root):
        listed = _git(
            root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *AREAS
        ).split("\0")
        names = {name for name in listed if name.endswith(".py") and (root / name).is_file()}
    else:
        names = {
            path.relative_to(root).as_posix()
            for area in AREAS
            for path in (root / area).rglob("*.py")
            if path.is_file()
        }
    return sorted(names)


def _git(root: Path, *arguments: str) -> str:
    """Ein Git-Aufruf im Baum ``root``; scheitert er, wirft er."""
    return subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, encoding="utf-8", check=True
    ).stdout


def is_git_tree(root: Path) -> bool:
    """Ist ``root`` selbst die Wurzel eines Git-Baums (auch eines Worktrees)?"""
    try:
        top = _git(root, "rev-parse", "--show-toplevel").rstrip("\r\n")
    except OSError, subprocess.CalledProcessError:
        return False
    return Path(top).resolve() == root.resolve()


def versioned_files(root: Path) -> set[str]:
    """Die ``*.py`` unter den drei Ordnern, die Git versioniert (Index), ohne neue."""
    listed = _git(root, "ls-files", "-z", "--cached", "--", *AREAS).split("\0")
    return {name for name in listed if name.endswith(".py")}


def list_known(root: Path) -> str | None:
    """Der jüngste Commit auf irgendeinem Zweig, der die Liste berührt hat — ``"Index"``,
    wenn sie nur vorgemerkt ist, ``None`` nur nach erfolgreichem Lesen beider Quellen."""
    try:
        found = _git(root, "log", "--all", "-1", "--format=%H", "--", LIST).strip()
        staged = _git(root, "ls-files", "--cached", "--", LIST).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise RatchetError(
            f"Git-Geschichte oder Index von {LIST} nicht lesbar ({error}) — "
            "Git-Zustand und Zugriff berichtigen, dann erneut prüfen; "
            "ohne gelesene Herkunft wird keine Liste angelegt"
        ) from error
    return found or ("Index" if staged else None)


def _list_source(root: Path) -> str | None:
    """Der jüngste Commit mit einer Fassung der Liste, zuerst in der Geschichte von HEAD."""
    for scope in ("HEAD", "--all"):
        try:
            found = _git(root, "log", "-1", "--format=%H", "--diff-filter=d", scope, "--", LIST)
        except OSError, subprocess.CalledProcessError:
            continue
        if found.strip():
            return found.strip()
    return None


def missing_list(root: Path | None) -> str:
    """Was zu tun ist, wenn die Liste fehlt: zurückholen und senken, nie neu anlegen."""
    source = _list_source(root) if root is not None and is_git_tree(root) else None
    if source is not None:
        return (
            f"{LIST} fehlt — aus Git zurückholen (`git show {source[:12]}:{LIST} > {LIST}`), "
            "dann `python tools/size_ratchet.py --lower`; eine neu angelegte Liste segnete "
            "jeden Verstoß seit ihrem letzten Stand"
        )
    return (
        f"{LIST} fehlt, und Git kennt keine Fassung — die Liste entsteht ein einziges Mal mit "
        "Codestruktur Schritt 0; ein Auszug ohne Git-Geschichte wird im Repository geprüft"
    )


def measure(root: Path) -> dict[str, Size]:
    """Die Größen aller Dateien unter ``root``; ohne eine einzige ist es der falsche Ordner."""
    names = tree_files(root)
    if not names:
        raise RatchetError(
            f"unter {root} liegt keine *.py in {', '.join(AREAS)} — "
            "das Werkzeug zählt den Baum, in dem es liegt; einen anderen Ordner gibt --root"
        )
    # Datei für Datei: Den ganzen Baum auf einmal im Speicher zu halten kostete
    # gut das Doppelte an Spitze, bei gleichem Ergebnis (Durchsicht W13, Fund 9).
    return {name: size_of(_source(root / name), name) for name in names}


def _source(path: Path) -> str:
    """Ohne Zeilenumbruch-Übersetzung gelesen: ``\\r\\n`` zählt einmal, ein loses ``\\r``
    gar nicht, wie bei ``wc -l``; eine Bytereihenfolgemarke fällt weg wie beim Import."""
    return path.read_bytes().decode("utf-8-sig")


def check(sizes: Mapping[str, Size], listed: Mapping[str, int]) -> list[Violation]:
    """Jeder Verstoß des Baums gegen die Liste, nach Pfad geordnet."""
    found: list[Violation] = []
    for name, size in sizes.items():
        if name not in listed and size.lines > LIMIT:
            found.append(
                Violation(
                    name,
                    "too_long",
                    f"{name}: {size.lines} Zeilen, mehr als {LIMIT}, und nicht in der "
                    f"Sperrklinke. Die Liste wächst nie um eine Datei: teilen, sodass "
                    f"jedes Modul unter {LIMIT} Zeilen bleibt. Zieht eine gelistete Datei "
                    "um (Konzept 4.3, Schritt 4b), trägt `python tools/size_ratchet.py "
                    f"--move ALT NEU …` den neuen Pfad ein. {RULES}",
                )
            )
    for name, count in listed.items():
        current = sizes.get(name)
        if current is None or current.lines <= LIMIT:
            state = "gibt es nicht mehr" if current is None else f"hat {current.lines} Zeilen"
            found.append(
                Violation(
                    name,
                    "release",
                    f"{name} {state} und gehört nicht mehr in die Sperrklinke — "
                    f"austragen mit `python tools/size_ratchet.py --lower`.",
                )
            )
        elif current.definitions is not None and current.definitions > count:
            found.append(
                Violation(
                    name,
                    "new_definition",
                    f"{name}: {current.definitions} Definitionen, gelistet {count} — eine "
                    f"Datei der Sperrklinke bekommt keine neue Definition. {RULES}",
                )
            )
        elif current.definitions is not None and current.definitions < count:
            found.append(
                Violation(
                    name,
                    "not_lowered",
                    f"{name}: {current.definitions} Definitionen, gelistet {count} — "
                    f"die Sperrklinke senken mit `python tools/size_ratchet.py --lower`.",
                )
            )
    return sorted(found, key=lambda violation: violation.path)


def initial(root: Path, sizes: Mapping[str, Size]) -> dict[str, int]:
    """Die erste Liste: jede versionierte Datei über der Grenze mit ihrer heutigen Zahl.

    Nur ein einziges Mal (Codestruktur Schritt 0). Abgelehnt wird, sobald Git die
    Liste je gesehen hat — eine gelöschte Liste neu anzulegen segnete jeden
    Verstoß seit ihrem letzten Stand —, außerhalb von Git und bei jeder
    unversionierten Datei über der Grenze, die sonst still in die Liste käme.
    """
    if not is_git_tree(root):
        raise RatchetError(
            f"--init nimmt nur auf, was Git versioniert, und {root} ist kein Git-Baum"
        )
    known = list_known(root)
    if known is not None or (root / LIST).exists():
        raise RatchetError(
            f"Git kennt {LIST} schon ({(known or 'Arbeitsbaum')[:12]}) — angelegt wird die "
            "Liste nur einmal. Senken mit --lower, ein Ordnungsschritt hebt mit --raise, ein "
            f"Umzug trägt mit --move ein; fehlt sie: {missing_list(root)}"
        )
    versioned = versioned_files(root)
    loose = sorted(
        name for name, size in sizes.items() if size.lines > LIMIT and name not in versioned
    )
    if loose:
        raise RatchetError(
            f"nicht versioniert und über {LIMIT} Zeilen: {', '.join(loose)} — --init nimmt "
            f"nur auf, was Git kennt; eine neue große Datei wird geteilt, nie gelistet. {RULES}"
        )
    return {
        name: size.definitions
        for name, size in sizes.items()
        if size.lines > LIMIT and size.definitions is not None
    }


def lowered(sizes: Mapping[str, Size], listed: Mapping[str, int]) -> dict[str, int]:
    """Die Liste nach ``--lower``: gesenkt, wo weniger gezählt wird, ausgetragen, wo
    die Datei fehlt oder unter die Grenze fiel. Gehoben und ergänzt wird nichts."""
    result: dict[str, int] = {}
    for name, count in listed.items():
        current = sizes.get(name)
        if current is None or current.lines <= LIMIT or current.definitions is None:
            continue
        result[name] = min(count, current.definitions)
    return result


def head_definitions(root: Path, name: str) -> list[str] | None:
    """Die Definitionen von ``name`` am Stand HEAD; ``None``, wenn HEAD die Datei nicht hat."""
    try:
        data = subprocess.run(
            ["git", "show", f"HEAD:{name}"], cwd=root, capture_output=True, check=True
        ).stdout
    except OSError, subprocess.CalledProcessError:
        return None
    return definition_names(data.decode("utf-8-sig"), f"HEAD:{name}")


def raised(
    root: Path, listed: Mapping[str, int], name: str, amount: int, sections: Sequence[str]
) -> dict[str, int]:
    """Die Liste nach einem Ordnungsschritt, der ``sections`` neu anlegt (Konzept 4.3, 4c).

    „Neu“ heißt gegenüber HEAD, als Menge mit Vielfachheit: Was gegenüber HEAD
    dazukam, muss genau ``sections`` sein — eine alte Methode statt einer neuen
    lässt eine ungenannte durch und wird abgelehnt. Eine geteilte Methode ist
    zwei neue und eine weniger. Die neue Zahl ist die gezählte, höchstens Liste
    plus ``amount``. Läuft vor dem Commit des Schritts."""
    if name not in listed:
        raise RatchetError(
            f"{name} steht nicht in der Sperrklinke — --raise hebt nur gelistete Dateien; "
            f"eine Datei über {LIMIT} Zeilen wird geteilt, nicht gelistet. {RULES}"
        )
    if amount < 1 or amount != len(sections) or len(set(sections)) != len(sections):
        raise RatchetError(
            f"--raise {name} {amount} nennt {len(sections)} verschiedene Abschnitte — "
            "die Zahl hebt sich um genau die Abschnitte, die der Commit benennt, je einer "
            "mit --sections"
        )
    before = head_definitions(root, name)
    if before is None:
        raise RatchetError(
            f"{name} gibt es an HEAD nicht — --raise misst „neu“ gegen den Stand HEAD und "
            "läuft vor dem Commit des Ordnungsschritts"
        )
    now = definition_names(_source(root / name), name)
    added = Counter(now) - Counter(before)
    if added != Counter(sections):
        raise RatchetError(
            f"{name}: neu gegenüber HEAD sind {sorted(added.elements()) or 'keine'}, genannt "
            f"{list(sections)} — --sections nennt genau die neuen Abschnitte, als Qualnamen "
            "wie MainWindow._build_file_menu"
        )
    if len(now) > listed[name] + amount:
        raise RatchetError(
            f"{name}: {len(now)} Definitionen, gelistet {listed[name]}, gehoben um {amount} — "
            f"die Liste lag schon unter dem Stand HEAD ({len(before)}); der Rest ist ein "
            f"Verstoß, kein Abschnitt. {RULES}"
        )
    return {**listed, name: len(now)}


def at_head(root: Path, name: str) -> bool:
    """Hat der Stand HEAD die Datei ``name``?"""
    try:
        _git(root, "cat-file", "-e", f"HEAD:{name}")
    except OSError, subprocess.CalledProcessError:
        return False
    return True


def moved(
    root: Path, listed: Mapping[str, int], old: str, targets: Sequence[str]
) -> dict[str, int]:
    """Die Liste nach einem Umzug: ``old`` zieht nach ``targets`` (Konzept 4.3, Schritt 4b).

    Ein Umzug trägt nichts Neues mit. Verlangt wird: ``old`` ist gelistet und
    liegt jetzt nicht mehr über der Grenze oder fehlt; jedes Ziel ist ungelistet,
    neu gegenüber HEAD und über der Grenze; alle Definitionen der Ziele standen
    an HEAD in ``old`` (Menge mit Vielfachheit), ihre Summe übersteigt die gelistete
    Zahl nicht. Dann fällt ``old`` aus der Liste, und jedes Ziel steht mit seiner
    gezählten Zahl darin. Auch der Weg für das
    Verschiebewerkzeug (``move_names``), das nach dem Schnitt hierher ruft.
    """
    if old not in listed:
        raise RatchetError(
            f"{old} steht nicht in der Sperrklinke — --move trägt nur eine gelistete Datei um"
        )
    if not targets or len(set(targets)) != len(targets) or old in targets:
        raise RatchetError(f"--move {old} braucht neue Pfade, jeden einmal und keiner gleich {old}")
    if (root / old).exists():
        lines = line_count(_source(root / old))
        if lines > LIMIT:
            raise RatchetError(
                f"{old} hat noch {lines} Zeilen, über der Grenze — ein Umzug lässt die alte "
                "Datei höchstens mit 2 000 Zeilen zurück oder entfernt sie"
            )
    before = head_definitions(root, old)
    if before is None:
        raise RatchetError(
            f"{old} gibt es an HEAD nicht — --move misst gegen den Stand HEAD und läuft vor "
            "dem Commit des Umzugs"
        )
    result = {name: count for name, count in listed.items() if name != old}
    carried: Counter[str] = Counter()
    for target in targets:
        if target in listed:
            raise RatchetError(f"{target} ist schon gelistet — ein Umzug zieht in neue Dateien")
        if not is_tree_path(target) or not (root / target).is_file():
            raise RatchetError(
                f"{target} fehlt oder ist keine *.py unter {', '.join(AREAS)} — erst "
                "verschieben, dann --move"
            )
        if at_head(root, target):
            raise RatchetError(
                f"{target} gibt es schon an HEAD — ein Umzug zieht in neue Dateien, nicht in "
                f"vorhandene. {RULES}"
            )
        source = _source(root / target)
        if line_count(source) <= LIMIT:
            raise RatchetError(
                f"{target} liegt nicht über der Grenze und braucht keinen Eintrag — nur "
                "Ziele über 2 000 Zeilen nennen"
            )
        names = definition_names(source, target)
        carried += Counter(names)
        result[target] = len(names)
    foreign = carried - Counter(before)
    if foreign:
        raise RatchetError(
            f"am neuen Ort stehen Definitionen, die an HEAD nicht in {old} standen: "
            f"{', '.join(sorted(foreign.elements()))} — ein Umzug trägt nichts Neues mit. {RULES}"
        )
    if carried.total() > listed[old]:
        raise RatchetError(
            f"{old}: am neuen Ort zusammen {carried.total()} Definitionen, gelistet "
            f"{listed[old]} — ein Umzug hebt die Sperrklinke nicht; den schon an HEAD "
            f"vorhandenen Verstoß durch Herauslösen in kleine Module beheben. {RULES}"
        )
    return result


def is_tree_path(name: str) -> bool:
    """Ein relativer POSIX-Pfad zu einer ``*.py`` unter einem der drei Ordner."""
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and path.suffix == ".py"
        and len(path.parts) > 1
        and path.parts[0] in AREAS
        and ".." not in path.parts
        and "\\" not in name
    )


def read_list(path: Path, root: Path | None = None) -> dict[str, int]:
    """Die Liste; fehlt sie oder trägt sie etwas anderes als Pfad und Zahl, hält es an.
    Mit ``root`` nennt die Meldung über eine fehlende Liste den Commit zum Zurückholen."""
    if not path.is_file():
        raise RatchetError(missing_list(root))
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise RatchetError(
            f"{LIST} ist kein gültiges TOML ({error}) — die Liste schreibt nur dieses Werkzeug"
        ) from error
    entries: dict[str, int] = {}
    for name, count in data.items():
        if not is_tree_path(name) or type(count) is not int or count < 0:
            raise RatchetError(
                f"{LIST}: {name!r} = {count!r} ist kein Pfad unter {', '.join(AREAS)} mit "
                "einer Zahl — die Liste schreibt nur dieses Werkzeug"
            )
        entries[name] = count
    return entries


def list_text(entries: Mapping[str, int]) -> str:
    """Die Liste als TOML, nach Pfad sortiert — ohne Bibliothek, nur Schlüssel und Zahl."""
    rows = [
        f"{json.dumps(name, ensure_ascii=False)} = {count}"
        for name, count in sorted(entries.items())
    ]
    return "\n".join([*HEADER, "", *rows]) + "\n"


def write_list(path: Path, entries: Mapping[str, int]) -> None:
    """Schreibt die Liste mit LF, wie ``.gitattributes`` sie hält."""
    path.write_text(list_text(entries), encoding="utf-8", newline="\n")


def changes(before: Mapping[str, int], after: Mapping[str, int]) -> list[str]:
    """Was ``--lower`` oder ``--raise`` an der Liste ändert; beide tragen nie ein."""
    lines = []
    for name in sorted(before):
        if name not in after:
            lines.append(f"ausgetragen: {name} ({before[name]})")
        elif before[name] != after[name]:
            lines.append(f"{name}: {before[name]} → {after[name]}")
    return lines


def _report(sizes: Mapping[str, Size], listed: Mapping[str, int], out: Iterable[str]) -> int:
    """Gibt die Änderungen und jeden Verstoß aus; der Rückgabewert ist der Exit-Code."""
    for line in out:
        print(line)
    found = check(sizes, listed)
    for violation in found:
        print(violation.message)
    print(f"W1: {len(sizes)} Dateien gezählt, {len(listed)} gelistet, {len(found)} Verstöße")
    return 1 if found else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Prüft, senkt, hebt oder legt an; jeder schreibende Weg prüft danach den ganzen Baum."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="prüfen (Vorgabe)")
    mode.add_argument("--lower", action="store_true", help="senken und austragen, nie heben")
    mode.add_argument(
        "--raise",
        dest="raise_entry",
        nargs=2,
        metavar=("PFAD", "N"),
        help="Ordnungsschritt: Zahl einer gelisteten Datei um N Abschnitte heben",
    )
    mode.add_argument(
        "--move",
        nargs="+",
        metavar="PFAD",
        help="Umzug: ALT NEU …, die gelistete Datei ALT zieht nach NEU",
    )
    mode.add_argument("--init", action="store_true", help="die Liste einmal anlegen")
    parser.add_argument(
        "--sections", nargs="+", default=[], metavar="ABSCHNITT", help="die Abschnitte zu --raise"
    )
    parser.add_argument(
        "--root", type=Path, default=ROOT, metavar="ORDNER", help="Wurzel des Baums"
    )
    args = parser.parse_args(argv)
    if args.sections and not args.raise_entry:
        parser.error("--sections gehört zu --raise")
    if args.raise_entry and not args.sections:
        parser.error("--raise verlangt --sections mit den Abschnitten, die der Commit benennt")
    root: Path = args.root
    target = root / LIST
    try:
        sizes = measure(root)
        if args.init:
            created = initial(root, sizes)
            write_list(target, created)
            shown = [f"gelistet: {name} = {count}" for name, count in sorted(created.items())]
            return _report(sizes, created, [*shown, f"angelegt: {LIST} mit {len(created)} Dateien"])
        listed = read_list(target, root)
        if args.lower:
            after = lowered(sizes, listed)
        elif args.raise_entry:
            name, amount = args.raise_entry
            if not amount.isdigit():
                raise RatchetError(f"--raise {name} {amount}: N ist die Zahl der Abschnitte")
            after = raised(root, listed, name, int(amount), args.sections)
        elif args.move:
            if len(args.move) < 2:
                raise RatchetError("--move braucht ALT und mindestens einen neuen Pfad")
            after = moved(root, listed, args.move[0], args.move[1:])
        else:
            return _report(sizes, listed, [])
        if after != listed:
            write_list(target, after)
        return _report(sizes, after, changes(listed, after))
    except RatchetError as error:
        print(f"size_ratchet: {error}", file=sys.stderr)
        return 2
    except (OSError, UnicodeDecodeError, SyntaxError) as error:
        # Eine Datei, die sich nicht lesen oder nicht parsen lässt, ist nicht
        # geprüft — Exit 1 hieße „Verstoß“, und das wäre eine Behauptung.
        print(
            f"size_ratchet: {type(error).__name__}: {error} — nicht geprüft (Exit 2); die "
            "Datei lesbar, als UTF-8 und als gültiges Python ablegen, dann erneut prüfen",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
