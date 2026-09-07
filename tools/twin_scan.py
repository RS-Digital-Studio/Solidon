"""Doppelte Stellen und Zwillinge in einem Baum — gemessen, nicht geschätzt.

    .venv\\Scripts\\python.exe tools/twin_scan.py app
    .venv\\Scripts\\python.exe tools/twin_scan.py tests --frage 2 --frage 7
    .venv\\Scripts\\python.exe tools/twin_scan.py app --similarity 0.7
    .venv\\Scripts\\python.exe tools/twin_scan.py app > funde.txt

**Wofür das da ist.** Eine Auskunft, die an mehr als einer Stelle hergeleitet
wird, läuft eines Tages auseinander, und die Stelle, die niemand sieht, bleibt
falsch. Dieses Werkzeug findet die Kandidaten; **welche Klasse ein Fund hat,
entscheidet sich am Code** — die vier Klassen und ihre Pflichten stehen in
``konzepte/konzept-zwillinge-2026-09.md``.

**Warum es hier liegt und nicht in der Sitzung.** Es ist dreimal gebaut
worden: am 24.08.2026 als Duplikat-Sucher, am 27.08. als „zwanzig Zeilen
``ast.walk``", am 07.09. noch einmal. Die ROADMAP hat es beim zweiten Mal
selbst notiert („ist in zwanzig Zeilen wieder gebaut") — und beim dritten hat
niemand die Zeilen von vorher gehabt.

**Was es nicht ist: ein Test.** Es steht nicht im Tor. Gemessen am 07.09.2026
gibt es in ``app/`` keinen wortgleichen Funktionskörper ab vier Anweisungen
mehr; ein Wächter darüber würde zwölf Dreizeiler melden und die zwei
Zwillinge, die an dem Tag wirklich zählten, übersehen — beide waren längst
auseinandergelaufen und damit für Gleichheit unsichtbar. Was ins Tor gehört,
steht dort: ``tests/test_shared_constants.py`` hält die Konstanten.

**Und die Grenze, die es selbst nicht sieht.** Dieselbe Regel in zwei
Formulierungen — eine bedingte und eine unbedingte Fassung derselben
Filterregel — hat weder Wortgleichheit noch Strukturgleichheit. Keine der
Fragen unten zeigt darauf. Gefunden hat einen solchen Fall am 07.09.2026 die
Sitzung, die den Code geschrieben hatte. Dieses Werkzeug ist der Zubringer
einer Durchsicht, nicht ihr Ersatz.

Die sieben Fragen:

1. **Konstanten** auf Modulebene: gleicher Name und gleicher Wert (1a),
   gleicher Name und verschiedener Wert (1b), gleicher nicht-trivialer Wert
   unter verschiedenen Namen (1c).
2. **Wortgleiche Funktionskörper** — Docstring abgezogen, ab einer Mindestzahl
   von Anweisungen.
3. **Strukturgleiche Körper**: Namen und Zahlen normalisiert.
4. **Nahe Zwillinge** über die Ähnlichkeit ihrer 6-Gramme.
5. **Zeichenketten**, gegen die an mehreren Stellen verglichen wird — dort
   steckt oft ein Prädikat, das noch keinen Namen hat.
6. **Kommentare, die eine Kopie bekennen** („dieselbe Zahl wie…"). Ein solcher
   Verweis ist keine geteilte Sache; er wandert beim nächsten Anfassen nicht
   mit.
7. **Gleichnamige Funktionen** in verschiedenen Dateien.

**Drei Zusicherungen, alle drei bezahlt.** Erstens zählt der Kopf, wie viel
überhaupt gelesen wurde, und ein leerer Baum ist ein Fehler und kein Ergebnis:
Ein Lauf mit Git-Bash-Pfad (``/c/Users/…``) fand unter Windows null Dateien
und meldete null Zwillinge. Zweitens zählt Frage 2 **Anweisungen** und nicht
Zeilen — das Zeilenmaß zählt Docstrings mit und meldete Einzeiler unter langen
Erklärungen als Zwillinge.

**Und drittens liegt die Mindestgröße bei drei Anweisungen und nicht bei
vier.** Das hat der Selbsttest herausgeholt, bevor das Werkzeug einen Tag alt
war: Der Zwilling, um dessentwillen es gebaut wurde — dieselbe Hohlraumfrage
in ``geom/prepare_ops`` und ``perceive/relations`` — besteht aus genau drei
Anweisungen. Mit der Vier hätte das Werkzeug den Fall verpasst, für den es
seinen Beleg mitbringt. ``tests/test_twin_scan.py`` fährt ihn nachgebaut.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import operator
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent

#: Unter so vielen gelesenen Funktionen ist der Lauf keine Messung, sondern ein
#: Fehlgriff — meist ein Pfad, den diese Plattform nicht kennt.
FLOOR: Final = 20

#: Zahlen, die überall vorkommen und nichts bedeuten. Ohne sie besteht Frage 1c
#: aus Rauschen.
TRIVIAL: Final[frozenset[float]] = frozenset(
    {
        -1,
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        8,
        10,
        12,
        16,
        20,
        24,
        32,
        50,
        60,
        64,
        90,
        100,
        128,
        180,
        200,
        255,
        256,
        360,
        500,
        512,
        1000,
        1024,
        0.001,
        0.01,
        0.1,
        0.5,
    }
)

#: Rechenzeichen, die zwischen zwei Zahlen noch einen festen Wert ergeben.
#: Kein ``eval`` (Regel 10) — aufgelöst wird ein Syntaxbaum, und ein Name darin
#: bricht die Auswertung ab. Eine Größenangabe steht als ``64 * 1024``, und
#: ``literal_eval`` allein hätte sie übersehen.
ARITHMETIC: Final[dict[type[ast.operator], Callable[[Any, Any], Any]]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
}

#: Wendungen, mit denen ein Kommentar eine Kopie oder ein Gegenstück zugibt.
CONFESSION: Final = re.compile(
    r"wie bei |wie in `|dieselbe (Zahl|Schwelle|Logik|Regel|Reihenfolge|Liste|Formel)"
    r"|derselbe (Grund|Wert|Satz|Weg)|denselben (Grund|Wert|Weg)|genau wie "
    r"|Kopie (von|aus|der|des)|identisch (mit|zu)|analog zu|gespiegelt|spiegelt "
    r"|Gegenstück (zu|von|in)|Zwilling|zweite Stelle|an zwei Stellen|beide Stellen",
    re.IGNORECASE,
)

#: Methodennamen, die in jeder Qt-Klasse gleich heißen. Frage 7 zählt sie nicht
#: — sie sind die Schnittstelle des Rahmens und keine Doppelung.
FRAMEWORK_NAMES: Final[frozenset[str]] = frozenset(
    {
        "__init__",
        "__repr__",
        "__eq__",
        "__hash__",
        "__str__",
        "__enter__",
        "__exit__",
        "accept",
        "reject",
        "apply",
        "reset",
        "clear",
        "update",
        "refresh",
        "values",
        "value",
        "params",
        "event",
        "eventFilter",
        "paintEvent",
        "sizeHint",
        "minimumSizeHint",
        "retranslate",
        "retranslate_ui",
        "retranslateUi",
        "work",
    }
)


def value_of(node: ast.expr) -> object | None:
    """Der feste Wert hinter einem Ausdruck — Literal oder Rechnung darüber."""
    try:
        return ast.literal_eval(node)
    except ValueError, SyntaxError, TypeError:
        pass
    if isinstance(node, ast.BinOp) and type(node.op) in ARITHMETIC:
        left, right = value_of(node.left), value_of(node.right)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            try:
                return ARITHMETIC[type(node.op)](left, right)
            except ZeroDivisionError, OverflowError:
                return None
    return None


class Normalise(ast.NodeTransformer):
    """Namen und Konstanten austauschen; Aufrufziele und Struktur bleiben."""

    def visit_Name(self, node: ast.Name) -> ast.AST:
        return ast.copy_location(ast.Name(id="N", ctx=node.ctx), node)

    def visit_arg(self, node: ast.arg) -> ast.AST:
        node.arg = "a"
        node.annotation = None
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, str):
            return ast.copy_location(ast.Constant(value="S"), node)
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return ast.copy_location(ast.Constant(value=0), node)
        return node


def sources(tree: Path) -> list[Path]:
    """Die Python-Dateien eines Baums, ohne Bytecode-Ordner."""
    return sorted(p for p in tree.rglob("*.py") if "__pycache__" not in p.parts)


def parsed(files: Iterable[Path]) -> dict[Path, ast.Module]:
    """Jede Datei als Syntaxbaum; eine kaputte wird genannt und übersprungen."""
    trees: dict[Path, ast.Module] = {}
    for path in files:
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as problem:
            print(f"!! {path}: {problem}", file=sys.stderr)
    return trees


def constants(trees: dict[Path, ast.Module]) -> dict[str, list[tuple[str, int, object]]]:
    """Jede Konstante auf Modulebene mit Datei, Zeile und Wert."""
    found: dict[str, list[tuple[str, int, object]]] = defaultdict(list)
    for path, tree in trees.items():
        for node in tree.body:
            targets: list[str] = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            for name in targets:
                if not (name.isupper() and len(name) > 3) or node.value is None:
                    continue
                value = value_of(node.value)
                if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                    continue
                found[name].append((relative(path), node.lineno, value))
    return found


def telling(value: object) -> bool:
    """Ob ein Wert überhaupt etwas aussagt, wenn er zweimal vorkommt.

    Eine 2 oder eine 100 steht überall und bedeutet nichts; ein Wert wie
    0,866 oder ein Dienstname sagt, dass zwei Stellen dieselbe Sache meinen.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value not in TRIVIAL
    return isinstance(value, str) and len(value) > 3 and not value.isupper()


def relative(path: Path) -> str:
    """Der Pfad, wie ihn ein Mensch sucht — relativ zum Projektstamm."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def functions(trees: dict[Path, ast.Module]) -> list[dict[str, Any]]:
    """Jede Funktion mit Körper ohne Docstring, exakt und normalisiert."""
    out: list[dict[str, Any]] = []
    for path, tree in trees.items():
        owners: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                owners[child] = parent
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = without_docstring(node.body)
            if not body:
                continue
            owner = owners.get(node)
            qualified = node.name
            if isinstance(owner, ast.ClassDef):
                qualified = f"{owner.name}.{node.name}"
            exact = "\n".join(ast.unparse(one) for one in body)
            normalised = "\n".join(
                ast.unparse(
                    ast.fix_missing_locations(Normalise().visit(ast.parse(ast.unparse(one))))
                )
                for one in body
            )
            out.append(
                {
                    "file": relative(path),
                    "line": node.lineno,
                    "name": node.name,
                    "qualified": qualified,
                    "statements": len(body),
                    "body_lines": len(exact.splitlines()),
                    "exact": exact,
                    "normalised": normalised,
                }
            )
    return out


def without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    """Der Körper ohne seinen Docstring — sonst zählt Erklärung als Code."""
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def shingles(text: str, width: int = 6) -> set[str]:
    """Die überlappenden Wortgruppen eines Textes — Grundlage der Ähnlichkeit."""
    tokens = re.findall(r"\w+|[^\w\s]", text)
    return {" ".join(tokens[i : i + width]) for i in range(max(0, len(tokens) - width + 1))}


def grouped(entries: Iterable[dict[str, Any]], key: str) -> list[list[dict[str, Any]]]:
    """Einträge mit demselben Körper, gruppiert und nach Größe sortiert."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        groups[hashlib.sha1(entry[key].encode(), usedforsecurity=False).hexdigest()].append(entry)
    twins = [group for group in groups.values() if len(group) > 1]
    return sorted(twins, key=lambda group: -group[0]["statements"])


def place(entry: dict[str, Any]) -> str:
    """Wo eine Funktion steht — Name, Datei, Zeile, Größe."""
    return f"{entry['qualified']} {entry['file']}:{entry['line']} ({entry['statements']} Anw.)"


def report_constants(trees: dict[Path, ast.Module]) -> None:
    found = constants(trees)
    total = sum(len(places) for places in found.values())
    print(f"\n## 1. Konstanten auf Modulebene: {total} in {len(found)} Namen")

    same = {n: p for n, p in found.items() if len(p) > 1 and len({v for _, _, v in p}) == 1}
    print(f"\n### 1a. Gleicher Name, gleicher Wert: {len(same)}")
    for name, places in sorted(same.items()):
        where = ", ".join(f"{file}:{line}" for file, line, _ in places)
        print(f"  {name} = {places[0][2]!r}: {where}")

    other = {n: p for n, p in found.items() if len(p) > 1 and len({v for _, _, v in p}) > 1}
    print(f"\n### 1b. Gleicher Name, verschiedener Wert: {len(other)}")
    for name, places in sorted(other.items()):
        where = ", ".join(f"{file}:{line}={value!r}" for file, line, value in places)
        print(f"  {name}: {where}")

    by_value: dict[object, list[tuple[str, str, int]]] = defaultdict(list)
    for name, places in found.items():
        for file, line, value in places:
            if telling(value):
                by_value[value].append((name, file, line))
    multi = {v: p for v, p in by_value.items() if len({n for n, _, _ in p}) > 1}
    print(f"\n### 1c. Gleicher Wert, verschiedene Namen: {len(multi)}")
    for value, places in sorted(multi.items(), key=lambda pair: -len(pair[1])):
        where = ", ".join(f"{name}@{file}:{line}" for name, file, line in places)
        print(f"  {value!r}: {where}")


def report_exact(entries: list[dict[str, Any]], least: int) -> None:
    print(f"\n## 2. Wortgleiche Körper (ohne Docstring), ab {least} Anweisungen")
    twins = grouped([e for e in entries if e["statements"] >= least], "exact")
    print(f"Gruppen: {len(twins)}")
    for group in twins:
        print(f"  [{group[0]['statements']} Anw.] " + " | ".join(place(e) for e in group))


def report_structural(entries: list[dict[str, Any]], least: int) -> None:
    print(f"\n## 3. Strukturgleiche Körper (Namen und Zahlen normalisiert), ab {least}")
    twins = [
        group
        for group in grouped([e for e in entries if e["statements"] >= least], "normalised")
        if len({e["exact"] for e in group}) > 1
    ]
    print(f"Gruppen (nicht schon unter 2.): {len(twins)}")
    for group in twins:
        print(f"  [{group[0]['statements']} Anw.] " + " | ".join(place(e) for e in group))


def report_near(entries: list[dict[str, Any]], least: int, threshold: float) -> None:
    print(f"\n## 4. Nahe Zwillinge (Ähnlichkeit ab {threshold:.2f}, ab {least} Anweisungen)")
    candidates = [e for e in entries if e["statements"] >= least]
    sets = [shingles(e["normalised"]) for e in candidates]
    index: dict[str, list[int]] = defaultdict(list)
    for position, group in enumerate(sets):
        for one in group:
            index[one].append(position)
    shared: Counter[tuple[int, int]] = Counter()
    for members in index.values():
        if len(members) > 40:
            continue
        for first in range(len(members)):
            for second in range(first + 1, len(members)):
                shared[(members[first], members[second])] += 1
    pairs = []
    for (first, second), count in shared.items():
        left, right = candidates[first], candidates[second]
        if left["normalised"] == right["normalised"]:
            continue
        union = len(sets[first] | sets[second])
        if union and count / union >= threshold:
            pairs.append((count / union, left, right))
    print(f"Paare: {len(pairs)}")
    for score, left, right in sorted(pairs, key=lambda triple: -triple[0]):
        print(f"  {score:.2f} {place(left)}  <->  {place(right)}")


def report_literals(trees: dict[Path, ast.Module], least: int) -> None:
    print(f"\n## 5. Zeichenketten, gegen die an {least} oder mehr Stellen verglichen wird")
    hits: dict[str, list[str]] = defaultdict(list)
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for side in [node.left, *node.comparators]:
                if (
                    isinstance(side, ast.Constant)
                    and isinstance(side.value, str)
                    and len(side.value) >= 2
                ):
                    hits[side.value].append(relative(path))
    multi = {k: v for k, v in hits.items() if len(v) >= least and len(set(v)) >= 2}
    print(f"Literale: {len(multi)}")
    for literal, places in sorted(multi.items(), key=lambda pair: -len(pair[1])):
        counted = Counter(places)
        where = ", ".join(f"{file}({count})" for file, count in counted.most_common())
        print(f"  {literal!r} x{len(places)} in {len(counted)} Dateien: {where}")


def report_confessions(files: list[Path]) -> None:
    print("\n## 6. Kommentare, die eine Kopie oder ein Gegenstück nennen")
    hits: list[tuple[str, int, str]] = []
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CONFESSION.search(line):
                hits.append((relative(path), number, line.strip()[:140]))
    print(f"Zeilen: {len(hits)}")
    per_file = Counter(file for file, _, _ in hits)
    if per_file:
        print("  je Datei: " + ", ".join(f"{f}({n})" for f, n in per_file.most_common(15)))
    for file, number, text in hits:
        print(f"  {file}:{number}: {text}")


def report_same_names(entries: list[dict[str, Any]], least: int) -> None:
    print(f"\n## 7. Gleichnamige Funktionen ab {least} Anweisungen in verschiedenen Dateien")
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        if entry["statements"] >= least and entry["name"] not in FRAMEWORK_NAMES:
            by_name[entry["name"]].append(entry)
    multi = {n: e for n, e in by_name.items() if len({one["file"] for one in e}) > 1}
    print(f"Namen: {len(multi)}")
    for name, found in sorted(multi.items(), key=lambda pair: -len(pair[1])):
        if len(found) > 12:
            print(f"  {name} x{len(found)} in {len({o['file'] for o in found})} Dateien")
            continue
        print(
            f"  {name}: " + " | ".join(f"{o['file']}:{o['line']}({o['statements']})" for o in found)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tree", type=Path, help="Verzeichnis, etwa app oder tests")
    parser.add_argument(
        "--frage",
        type=int,
        action="append",
        choices=range(1, 8),
        metavar="N",
        help="nur diese Frage stellen (mehrfach möglich); ohne Angabe alle sieben",
    )
    parser.add_argument("--anweisungen", type=int, default=3, help="Mindestgröße für Frage 2")
    parser.add_argument("--similarity", type=float, default=0.55, help="Schwelle für Frage 4")
    arguments = parser.parse_args(argv)

    tree = arguments.tree if arguments.tree.is_absolute() else ROOT / arguments.tree
    if not tree.is_dir():
        print(f"Kein Verzeichnis: {tree}", file=sys.stderr)
        print("Unter Windows ist ein Pfad wie /c/Users/… keiner.", file=sys.stderr)
        return 2

    files = sources(tree)
    trees = parsed(files)
    entries = functions(trees)
    lines = sum(len(path.read_text(encoding="utf-8").splitlines()) for path in trees)
    print(f"# Zwillingsmessung über {relative(tree)}")
    # **Gelesen gegen geparst, und nicht nur geparst.** Die Zahl unten hieß
    # zuerst „50 Dateien", wo es „50 von 60" heißen musste: Eine Datei mit
    # Syntaxfehler fällt aus ``parsed`` heraus, ihre Meldung steht auf stderr
    # und geht in tausend Ausgabezeilen unter. Eine Grundmenge, die still
    # schrumpft, ist genau der Fehler, gegen den die Mindestzählung steht
    # (Befund solidon-e8, 07.09.2026).
    fehlend = len(files) - len(trees)
    gelesen = f"{len(trees)} von {len(files)} Dateien" if fehlend else f"{len(trees)} Dateien"
    print(f"{gelesen}, {lines} Zeilen, {len(entries)} Funktionen")
    if fehlend:
        print(f"!! {fehlend} Datei(en) ließen sich nicht lesen — siehe stderr")
    if len(entries) < FLOOR:
        print(
            f"\nNur {len(entries)} Funktionen gelesen — das ist keine Messung. Stimmt der Pfad?",
            file=sys.stderr,
        )
        return 1

    wanted = set(arguments.frage or range(1, 8))
    if 1 in wanted:
        report_constants(trees)
    if 2 in wanted:
        report_exact(entries, arguments.anweisungen)
    if 3 in wanted:
        report_structural(entries, arguments.anweisungen + 2)
    if 4 in wanted:
        report_near(entries, arguments.anweisungen + 2, arguments.similarity)
    if 5 in wanted:
        report_literals(trees, 3)
    if 6 in wanted:
        report_confessions(files)
    if 7 in wanted:
        report_same_names(entries, arguments.anweisungen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
