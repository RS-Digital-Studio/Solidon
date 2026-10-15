"""W6: Namenslisten lösen auf und tragen bei.

**Warum es diese Datei gibt** (Konzept Codestruktur 4.1, Plan Schritt 0, 2.6).
Wo Code Modul- oder Funktionsnamen als Text hält, prüft weder ein Import noch
mypy, ob der Name noch stimmt. Teilt ein Schnitt ein Modul oder verschiebt er
einen Namen, bleibt die Liste stehen — und wer sie liest, übersprang bisher
still, was fehlt (CS-10), oder hielt einen Namen, den niemand mehr las
(CS-9b). Jeder Eintrag muss deshalb auflösen und etwas beitragen:

a) ``bootstrap._OPERATION_MODULES``: importierbar, und mindestens eine
   registrierte Operation hat dort ihre Funktion.
b) ``builtin.SHIPPED_MODULES``: liefert mindestens einen Baustein.
c) ``evaluate._STEP_WAY_MODULES``: ``_step_ways`` importiert jedes Modul und
   bricht ab, wenn eines fehlt oder keine eigene Funktion beiträgt — auch
   mitten in ``evaluate``.
d) ``matching._MATCH_WAYS``: im Modul gebunden und zur Aufrufzeit gelesen; die
   Lesermenge des Auflösers wie in W2 d) (Entscheidung E8).
e) Lazy-Exporte: Das Untermodul jedes Eintrags bindet den Namen auf
   Modulebene, und jemand bezieht den Namen über das Paket — in ``app/``,
   ``tools/`` oder ``tests/``, auch in einem Subprozess-Skript (wie in d): Ein
   Export, den niemand bezieht, ist ein Name, den nur die Liste hält). Dass es
   Untermodul und Attribut zur Laufzeit gibt, prüft ``test_lazy_exports.py``.
g) Jede Zeichenkette ``"app.…"`` in ``app/`` und ``tools/`` nennt ein Modul,
   einen Namen darin oder — mit Punkt am Ende — ein Paket.
h) ``function_list.RAW_WINDOW_PACKAGES``: Jeder Schlüssel ist der Name genau
   einer Funktion, die ein Meldungsfenster baut, und jede solche Funktion hat
   einen. Die Kennung nennt nur den Funktionsnamen, nie ein Modul (D0, E10).

f), den Lebensdauer-Pin in ``conftest.py``, prüft ``test_suite_pin.py``.

Jede Prüfung ist eine Funktion über die Liste; die Gegenproben geben ihr je
einen fehlenden und einen leeren Eintrag und verlangen den Fund.
"""

from __future__ import annotations

import ast
import functools
import importlib
import os.path
import re
import sys
import textwrap
import types
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

import pytest

from app.core import bootstrap
from app.core.errors import InternalError
from app.core.knowledge.parts import builtin
from app.core.perceive import matching
from app.core.registry import REGISTRY
from tools import function_list, function_scan
from tools.code_index import Index, shared

ROOT = Path(__file__).resolve().parents[1]
MATCHING = "app.core.perceive.matching"

#: Das fehlende Modul der Gegenproben liegt außerhalb von ``app``: Ein erfundener Name
#: unter ``app``, den ein Helfer hier importiert, wäre für W5
#: (``test_import_resolution.py``) ein echter, unauflösbarer Bezug.
ABSENT = "cs0_name_lists_absent"

#: Untergrenzen der Grundmengen, je mit ihrer Herkunft. Wo der Plan keine Zahl
#: nennt, heißt die Untergrenze nur „nicht leer“: Der heutige Ist-Wert als
#: Untergrenze machte jede berechtigte Streichung eines Eintrags rot
#: (``.claude/rules/tests.md``, „Prüft dieser Test eine Zusage — oder den Ist-Zustand?“).
GROUND_SETS = {
    # Plan 2.6 a)
    "_OPERATION_MODULES": 31,
    # Plan 2.6 b) nennt keine Zahl
    "SHIPPED_MODULES": 1,
    # Plan 1.3
    "_STEP_WAY_MODULES": 8,
    # Plan 2.6 d) nennt keine Zahl
    "_MATCH_WAYS": 1,
    # Plan 2.0 zählte ``_EXPORTS`` in 7 Paketen; ``app.core.agent`` exportiert nichts
    # mehr, seit e) einen Bezug über das Paket verlangt (CS-19): Keinen seiner zwölf
    # Namen bezog jemand so
    "Lazy-Pakete": 6,
    # Plan 2.6 g), Anhang A S15
    "app-Zeichenketten": 52,
    # Plan 2.6 h) zählte 26 Schlüssel mit Modulstamm; seit D0 (E10) nennt eine
    # Kennung nur die Funktion — Zählung an ``fc597cac9``
    "Meldungsfenster": 21,
}

#: Eine Zeichenkette, die wie ein Modulpfad unter ``app`` aussieht; mit Punkt am
#: Ende ein Präfix. Ob der erste Teil ein Modul von ``app`` ist, sagt der Baum —
#: ``"app.log"`` ist ein Dateiname.
DOTTED = re.compile(r"app(?:\.[A-Za-z_]\w*)+\.?")

#: Eine Importzeile von ``app``, auch eingerückt: In einer Zeichenkette ist sie das
#: Zeichen eines Skripts, das der Auflöser nicht liest.
SCRIPT_IMPORT = re.compile(r"^[ \t]*(?:from|import) app\.", re.MULTILINE)

#: Vorfilter je Datei: eine Dreifachzeichenkette oder eine Zeichenkette, die mit einem
#: Import von ``app`` beginnt (``-c``). Geparst wird nur, wo eine davon ein Skript sein
#: kann — über den Baum 10,5 s gegen 1,3 s, dieselben Paare.
LITERAL = re.compile(r"(\"\"\"|''')(.*?)\1|[\"'](?:import|from) app\.", re.DOTALL)


def _step_way_module() -> types.ModuleType:
    return importlib.import_module("app.core.scene.evaluate")


@pytest.fixture(scope="module")
def index() -> Index:
    return shared()


@pytest.fixture(scope="module")
def scan() -> function_scan.UiScan:
    return function_scan.scan_ui(function_list.ui_sources())


# ------------------------------------------------------------------------- Prüfungen


def _operation_problems(names: Iterable[str]) -> list[str]:
    """a) Jedes Modul lässt sich importieren und trägt eine Operation."""
    bootstrap.load_operations()
    owners = Counter(spec.fn.__module__ for spec in REGISTRY.all())
    problems = []
    for name in names:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as missing:
            problems.append(f"{name}: nicht importierbar ({missing})")
            continue
        if not owners[name]:
            problems.append(f"{name}: registriert keine Operation")
    return problems


def _shipped_modules() -> list[str]:
    """``SHIPPED_MODULES`` nennt Module relativ zu ``builtin``; hier stehen sie ganz."""
    return [f"{builtin.__package__}.{short}" for short in builtin.SHIPPED_MODULES]


def _part_problems(names: Iterable[str]) -> list[str]:
    """b) Jedes Bausteinmodul lässt sich importieren und liefert einen Baustein."""
    owners = Counter(spec.fn.__module__ for spec in builtin.load().all())
    problems = []
    for name in names:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError as missing:
            problems.append(f"{name}: nicht importierbar ({missing})")
            continue
        if not owners[name]:
            problems.append(f"{name}: liefert keinen Baustein")
    return problems


def _way_problems(index: Index, module: str, names: Iterable[str]) -> list[str]:
    """d) Jeder Name ist im Modul gebunden, und jemand liest ihn zur Aufrufzeit."""
    problems = []
    for name in names:
        if not index.exists(module, name):
            problems.append(f"{module}.{name}: im Modul nicht gebunden")
        elif not index.readers(module, name):
            problems.append(f"{module}.{name}: liest niemand zur Aufrufzeit")
    return problems


def _lazy_packages() -> list[str]:
    """Jedes Paket unter ``app/``, das ``install(__name__, _EXPORTS)`` ruft."""
    return [
        ".".join(init.relative_to(ROOT).parent.parts)
        for init in sorted((ROOT / "app").rglob("__init__.py"))
        if "install(__name__, _EXPORTS)" in init.read_text(encoding="utf-8")
    ]


def _script_names(script: ast.Module) -> set[tuple[str, str]]:
    """``(modul, name)`` aus ``from M import N`` und ``import M [as x]`` mit ``x.N``."""
    modules: dict[str, str] = {}
    found: set[tuple[str, str]] = set()
    for node in ast.walk(script):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            found.update((node.module, alias.name) for alias in node.names)
        elif isinstance(node, ast.Import):
            modules.update({alias.asname or alias.name: alias.name for alias in node.names})
    for node in ast.walk(script):
        if isinstance(node, ast.Attribute):
            head = ast.unparse(node.value)
            if head in modules:
                found.add((modules[head], node.attr))
    return found


@functools.cache
def _script_references(root: Path) -> frozenset[tuple[str, str]]:
    """Was Quelltext in Zeichenketten unter ``app/``, ``tools/`` und ``tests/`` bezieht.

    Ein Subprozess-Skript (``textwrap.dedent('''…''')``) liest der Auflöser aus R nicht;
    ``test_core_isolation.py`` bezieht dort ``parts.PartRegistry`` und
    ``activation.Licence`` über das Paket, um genau diese Schnittstelle zu prüfen.
    """
    found: set[tuple[str, str]] = set()
    for area in ("app", "tools", "tests"):
        for path in sorted((root / area).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if not any(
                literal.group(2) is None or SCRIPT_IMPORT.search(literal.group(2))
                for literal in LITERAL.finditer(source)
            ):
                continue
            for node in ast.walk(ast.parse(source, filename=str(path))):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and SCRIPT_IMPORT.search(node.value)
                ):
                    try:
                        script = ast.parse(textwrap.dedent(node.value))
                    except SyntaxError:
                        continue
                    found |= _script_names(script)
    return frozenset(found)


def _export_problems(index: Index, package: str) -> list[str]:
    """e) Das Untermodul bindet den Namen auf Modulebene, und jemand bezieht ihn.

    Gefragt wird der Auflöser, nichts wird importiert: So steht ein erfundener Eintrag
    einer Gegenprobe nie als echter Bezug im Baum (W5). Dass das Paket genau dieses
    Objekt liefert, sichert ``app.core.lazy.install`` selbst zu. Bezogen heißt:
    ``index.references`` nennt ``paket.name`` irgendwo in ``app/``, ``tools/`` oder
    ``tests/`` — ``_EXPORTS``, ``__all__`` und der ``TYPE_CHECKING``-Block nennen das
    Untermodul oder bloßen Text und zählen nicht —, oder ein Skript in einer
    Zeichenkette bezieht ihn (:func:`_script_references`).
    """
    scripts = _script_references(index.root)
    problems = []
    for name, (submodule, attribute) in index.modules[package].exports.items():
        origin = f"{package}.{submodule}"
        if not index.exists(origin, attribute):
            problems.append(f"{package}.{name}: {origin} bindet {attribute} nicht")
        elif not index.references(package, name) and (package, name) not in scripts:
            problems.append(f"{package}.{name}: bezieht niemand über das Paket")
    return problems


@functools.cache
def _app_strings() -> dict[str, set[str]]:
    """Jede Zeichenkette in ``app/`` und ``tools/``, die einen Pfad unter ``app`` nennt."""
    heads = {
        path.stem
        for path in (ROOT / "app").iterdir()
        if (path.suffix == ".py" and path.stem != "__init__") or (path / "__init__.py").is_file()
    }
    found: dict[str, set[str]] = {}
    for area in ("app", "tools"):
        for path in sorted((ROOT / area).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            for node in ast.walk(ast.parse(path.read_bytes(), filename=str(path))):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and DOTTED.fullmatch(node.value)
                    and node.value.split(".")[1] in heads
                ):
                    found.setdefault(node.value, set()).add(path.relative_to(ROOT).as_posix())
    return found


def _string_problems(index: Index, strings: Mapping[str, Iterable[str]]) -> list[str]:
    """g) Ein Modul, ein Name in einem Modul oder, mit Punkt am Ende, ein Paket."""
    problems = []
    for text, places in sorted(strings.items()):
        if text.endswith("."):
            resolved = text[:-1] in index.packages
        else:
            parent, _, name = text.rpartition(".")
            resolved = index.module_exists(text) or (
                index.module_exists(parent) and index.exists(parent, name)
            )
        if not resolved:
            problems.append(f"{text!r} in {', '.join(sorted(places))}: löst nicht auf")
    return problems


def _window_problems(
    keys: Iterable[str], ids: Iterable[str], scan: function_scan.UiScan
) -> list[str]:
    """h) Schlüssel und Meldungsfunktionen decken sich eins zu eins."""
    keys = tuple(keys)
    problems = [
        f"{key!r}: an {len(scan.raw_places.get(key, ()))} Stellen ein Meldungsfenster"
        for key in keys
        if len(scan.raw_places.get(key, ())) != 1
    ]
    problems += [
        f"{key}: Meldungsfenster ohne Schlüssel" for key in scan.raw_windows if key not in keys
    ]
    problems += [f"{key}: eigene Kennung ohne Schlüssel" for key in ids if key not in keys]
    return problems


# ------------------------------------------------------------------------- Grundmengen


def test_every_list_has_its_ground_set(scan: function_scan.UiScan) -> None:
    """Über einer leeren Liste wäre jede Prüfung grün, weil nichts geprüft wurde."""
    sizes = {
        "_OPERATION_MODULES": len(bootstrap._OPERATION_MODULES),
        "SHIPPED_MODULES": len(builtin.SHIPPED_MODULES),
        "_STEP_WAY_MODULES": len(_step_way_module()._STEP_WAY_MODULES),
        "_MATCH_WAYS": len(matching._MATCH_WAYS),
        "Lazy-Pakete": len(_lazy_packages()),
        "app-Zeichenketten": len(_app_strings()),
        "Meldungsfenster": len(scan.raw_windows),
    }
    short = {name: size for name, size in sizes.items() if size < GROUND_SETS[name]}
    assert not short, f"unter der Untergrenze: {short} (Untergrenzen {GROUND_SETS})"


# ------------------------------------------------------------------------- a) und b)


def test_a_every_operation_module_registers_an_operation() -> None:
    problems = _operation_problems(bootstrap._OPERATION_MODULES)
    assert not problems, "\n".join(problems)


def test_a_a_missing_or_empty_operation_module_is_found() -> None:
    """Gegenprobe: ein fehlendes Modul und eines, das keine Operation trägt."""
    problems = _operation_problems((*bootstrap._OPERATION_MODULES, ABSENT, "app.core.units"))
    assert [problem.split(":")[0] for problem in problems] == [ABSENT, "app.core.units"]


def test_b_every_shipped_module_brings_a_part() -> None:
    problems = _part_problems(_shipped_modules())
    assert not problems, "\n".join(problems)


def test_b_a_missing_or_empty_part_module_is_found() -> None:
    """Gegenprobe: ein fehlendes Modul und das Register selbst, das keinen Baustein baut."""
    registry = f"{builtin.__package__}.registry"
    problems = _part_problems((*_shipped_modules(), ABSENT, registry))
    assert [problem.split(":")[0] for problem in problems] == [ABSENT, registry]


# ------------------------------------------------------------------------- c)


def test_c_every_step_way_module_contributes_its_own_functions() -> None:
    """``_step_ways`` nimmt jedes Modul, und jedes bringt eigene Funktionen mit."""
    evaluate = _step_way_module()
    ways = evaluate._step_ways()
    own = Counter(getattr(way, "__module__", None) for way in ways)
    empty = [name for name in evaluate._STEP_WAY_MODULES if not own[name]]
    assert not empty, f"ohne eigene Funktion: {empty}"


def test_c_a_missing_step_way_module_stops_instead_of_being_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gegenprobe zu CS-10: Bis Schritt 0 übersprang ``_step_ways`` den Namen still."""
    evaluate = _step_way_module()
    monkeypatch.setattr(evaluate, "_STEP_WAY_MODULES", (*evaluate._STEP_WAY_MODULES, ABSENT))
    with pytest.raises(ModuleNotFoundError, match=ABSENT):
        evaluate._step_ways()


def test_c_a_step_way_module_without_own_function_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gegenprobe: ein Modul, das nur Geliehenes hält — aufrufbar, aber nicht seins."""
    evaluate = _step_way_module()
    borrowed = types.ModuleType("cs0_borrowed_ways")
    vars(borrowed).update(LIMIT=3, join=os.path.join)
    monkeypatch.setitem(sys.modules, borrowed.__name__, borrowed)
    monkeypatch.setattr(
        evaluate, "_STEP_WAY_MODULES", (*evaluate._STEP_WAY_MODULES, borrowed.__name__)
    )
    with pytest.raises(InternalError) as caught:
        evaluate._step_ways()
    assert caught.value.values["name"] == borrowed.__name__
    assert caught.value.suggestions, "jede Ausnahme trägt einen Handlungsvorschlag"


def test_c_the_evaluation_itself_stops_on_a_missing_step_way_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anschluss: Nicht nur die Hilfsfunktion, die Auswertung bricht ab."""
    from app.core.knowledge.profiles import make_profile
    from app.core.scene.project import new_project

    evaluate = _step_way_module()
    monkeypatch.setattr(evaluate, "_STEP_WAY_MODULES", (*evaluate._STEP_WAY_MODULES, ABSENT))
    with pytest.raises(ModuleNotFoundError, match=ABSENT):
        evaluate.evaluate(new_project().document, make_profile())


# ------------------------------------------------------------------------- d)


def test_d_every_match_way_is_bound_and_read(index: Index) -> None:
    problems = _way_problems(index, MATCHING, matching._MATCH_WAYS)
    assert not problems, "\n".join(problems)


def test_d_an_unused_or_missing_match_way_is_found(tmp_path: Path) -> None:
    """Gegenprobe an einer Attrappe: ein Name, den nur die Liste hält (wie
    ``_cost_matrix`` bis Schritt 0), und einer, den es nicht gibt."""
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "__init__.py").write_text('"""Attrappe."""\n', encoding="utf-8")
    (tmp_path / "app" / "ways.py").write_text(
        "def used():\n"
        "    return 1\n\n\n"
        "def unused():\n"
        "    return 2\n\n\n"
        "def caller():\n"
        "    return used()\n\n\n"
        'WAYS = ("used", "unused")\n',
        encoding="utf-8",
    )
    fake = Index.build(tmp_path, cache=False)
    assert _way_problems(fake, "app.ways", ("used", "unused", "absent")) == [
        "app.ways.unused: liest niemand zur Aufrufzeit",
        "app.ways.absent: im Modul nicht gebunden",
    ]


# ------------------------------------------------------------------------- e)


@pytest.mark.parametrize("package", _lazy_packages())
def test_e_every_lazy_export_is_bound_and_referenced(index: Index, package: str) -> None:
    assert index.modules[package].exports, f"{package}: der Auflöser sieht kein _EXPORTS"
    problems = _export_problems(index, package)
    assert not problems, "\n".join(problems)


def test_e_a_missing_unbound_or_unreferenced_export_is_found(tmp_path: Path) -> None:
    """Gegenprobe an einer Attrappe: ein Eintrag, dessen Untermodul fehlt, einer, dessen
    Untermodul den Namen nicht bindet, und einer, den nur die Exportliste hält — neben
    einem, den ein Modul bezieht, und einem, den nur ein Subprozess-Skript in einer
    Zeichenkette bezieht."""
    package = tmp_path / "app" / "pkg"
    package.mkdir(parents=True)
    (tmp_path / "app" / "__init__.py").write_text('"""Attrappe."""\n', encoding="utf-8")
    (tmp_path / "app" / "lazy.py").write_text(
        "def install(package, exports):\n    return None\n", encoding="utf-8"
    )
    (package / "__init__.py").write_text(
        "from app.lazy import install\n\n"
        "_EXPORTS = {\n"
        '    "used": ("sub", "used"),\n'
        '    "scripted": ("sub", "scripted"),\n'
        '    "unused": ("sub", "unused"),\n'
        '    "unbound": ("sub", "absent"),\n'
        '    "lost": ("gone", "lost"),\n'
        "}\n"
        "install(__name__, _EXPORTS)\n"
        '__all__ = ["lost", "scripted", "unbound", "unused", "used"]\n',
        encoding="utf-8",
    )
    (package / "sub.py").write_text(
        "def used():\n    return 1\n\n\n"
        "def scripted():\n    return 2\n\n\n"
        "def unused():\n    return 3\n",
        encoding="utf-8",
    )
    (tmp_path / "app" / "user.py").write_text(
        "from app.pkg import used\n\n\ndef call():\n    return used()\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_probe.py").write_text(
        'SCRIPT = """\nimport app.pkg as pkg\n\npkg.scripted()\n"""\n', encoding="utf-8"
    )
    fake = Index.build(tmp_path, cache=False)
    assert _export_problems(fake, "app.pkg") == [
        "app.pkg.unused: bezieht niemand über das Paket",
        "app.pkg.unbound: app.pkg.sub bindet absent nicht",
        "app.pkg.lost: app.pkg.gone bindet lost nicht",
    ]


# ------------------------------------------------------------------------- g)


def test_g_every_module_path_in_the_code_resolves(index: Index) -> None:
    problems = _string_problems(index, _app_strings())
    assert not problems, "\n".join(problems)


def test_g_an_unresolved_module_path_is_found(index: Index) -> None:
    """Gegenprobe: fehlendes Modul, fehlender Name, fehlendes Paket als Präfix — und je
    eine Form, die auflöst."""
    problems = _string_problems(
        index,
        {
            "app.core.perceive.not_there": ["a.py"],
            f"{MATCHING}.not_there": ["b.py"],
            "app.core.not_a_package.": ["c.py"],
            MATCHING: ["d.py"],
            f"{MATCHING}._MATCH_WAYS": ["e.py"],
            "app.core.perceive.": ["f.py"],
        },
    )
    assert problems == [
        "'app.core.not_a_package.' in c.py: löst nicht auf",
        "'app.core.perceive.matching.not_there' in b.py: löst nicht auf",
        "'app.core.perceive.not_there' in a.py: löst nicht auf",
    ]


# ------------------------------------------------------------------------- h)


def test_h_every_message_window_key_names_exactly_one_window(scan: function_scan.UiScan) -> None:
    problems = _window_problems(
        function_list.RAW_WINDOW_PACKAGES, function_list.RAW_WINDOW_IDS, scan
    )
    assert not problems, "\n".join(problems)


def test_h_a_missing_empty_or_unlisted_key_is_found(scan: function_scan.UiScan) -> None:
    """Gegenprobe: ein Schlüssel ohne Fenster, ein leerer, ein Fenster ohne Schlüssel
    und eine Kennung ohne Paket."""
    keys = [key for key in function_list.RAW_WINDOW_PACKAGES if key != "confirm_unsaved"]
    problems = _window_problems(
        (*keys, "not_a_window", ""),
        (*function_list.RAW_WINDOW_IDS, "ghost"),
        scan,
    )
    assert problems == [
        "'not_a_window': an 0 Stellen ein Meldungsfenster",
        "'': an 0 Stellen ein Meldungsfenster",
        "confirm_unsaved: Meldungsfenster ohne Schlüssel",
        "ghost: eigene Kennung ohne Schlüssel",
    ]
