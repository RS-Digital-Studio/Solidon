"""Statischer Auflöser für Namen, Importe und Patch-Ziele über ``app/``, ``tools/``, ``tests/``.

    .venv\\Scripts\\python.exe tools/code_index.py --inventory   # Grundmengen, W2, W5, Laufzeit
    .venv\\Scripts\\python.exe tools/code_index.py --reach       # Lesermengen gepatchter Namen

Gebaut für Schritt 0 der Codestruktur (``konzepte/konzept-codestruktur-2026-10.md``, 4.1): Die
Wächter W2 (``tests/test_patch_targets.py``) und W5 (``tests/test_import_resolution.py``) und das
Verschiebewerkzeug ``tools/move_names.py`` fragen ihn, statt je eine eigene Teilauflösung zu
bauen. Er liest nur Quelltext (``ast``), importiert nichts aus dem Baum und braucht nichts außer
der Standardbibliothek. Was je Datei erhoben wird, steht in ``tools/code_facts.py``.

**Wie er auflöst.** Ein Name gilt, wo Python ihn findet: lokal, in umschließenden Funktionen
(Klassen übersprungen), im Modul, eingebaut (:func:`tools.code_facts.lookup`). Ein Alias gilt so
je Funktion, nie je Datei; eine Bindung später in derselben Schleife gilt im nächsten Durchlauf.
Gefaltet werden Konstanten, Tupel und Tabellen (auch mit ``*``), f-Strings, ``+``, ``/`` an
Pfaden, ``if``-Ausdrücke, Vergleiche, ``hasattr``, ``importlib.import_module``,
``sys.modules[…]``, ``getattr``, ``Path(__file__)``-Ketten und ``spec_from_file_location``;
Namen aus Schleifen, Abstraktionen und gefüllten Behältern (``append``, ``x[k] = v``), aus
``parametrize``, aus Fixtures (auch ``request.param``) und aus den Aufrufstellen eines
Testhelfers samt ``*args``/``**kwargs``. Was aus derselben Schleife, demselben Zweig eines ``if``
oder derselben Aufrufstelle stammt, bleibt gepaart — eine Zeile der Faltung ist je Quelle ein
Wert, kein Kreuzprodukt —, und die Bedingung des ``if`` um eine Stelle schließt Zeilen aus, die
dort nicht gelten können. Was sich nicht falten lässt, wird nicht geraten, sondern ``unknown``
mit Grund; die Wächter machen daraus einen Fund (Konzept 4.1: keine Ausnahmeliste).

**Die Grenze.** Was aus einem Objekt kommt — Attribut einer Instanz, Element eines Behälters,
den ein Objekt hält, Ergebnis einer Methode —, ist ein Objekt. Ein Modul, das zur Laufzeit in ein
Objekt gelegt wird, sieht der Auflöser nicht; im Baum gibt es diese Form bei Patch-Zielen nicht
(``PatchTarget.status == "object"`` nennt jedes solche Ziel). Ein über den Pfad geladenes Modul
ist eine eigene Kopie (``loaded``): Seine Namen und Leser sind die der Quelle, ein Patch darauf
zählt nicht als Patch am Original.

**Module.** Ein Modulattribut ist eine Bindung auf Modulebene (auch unter ``if``/``try``, nie nur
unter ``TYPE_CHECKING``), ein Lazy-Export — er gewinnt wie in ``app.core.lazy`` vor einem
gleichnamigen Untermodul und wird beim Ursprung gelesen —, ein Literal aus ``__getattr__``, ein
Untermodul oder ein Name, den jedes Modul hat. Ein Stub (``.pyi``) zählt, wo es kein Python
gibt.

**Zur Aufrufzeit** heißt: in einem Funktions- oder Lambdarumpf. Was auf Modul- oder
Klassenebene, in Vorgabewerten oder Dekoratoren gelesen wird, läuft beim Import und ist eine
Kopie, kein Leser — ein Patch danach erreicht es nicht, außer der Test lädt das Modul danach in
derselben Funktion mit ``importlib.reload`` neu (``test_advise.py``, B12).

**Zwischenspeicher.** Die Auszüge liegen je Datei nach SHA-256 des Inhalts und dem Stand von
``code_facts.py`` und dem Datenformat in ``tools/__pycache__/code_index.data``. Jeder Bau prüft
sie gegen die Dateien; kalt und warm liefern dasselbe (``tests/test_code_index.py``). Die
Antworten eines analysierten Index hält ``tools/code_store.py`` je Baumstand; :func:`shared`
liest sie von dort (``tests/test_code_store.py``).
"""

from __future__ import annotations

import argparse
import ast
import builtins
import functools
import gc
import hashlib
import sys
import textwrap
import time
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.code_facts import (  # noqa: E402
    AREAS,
    CHECKING,
    INDEXED,
    IR,
    RUNTIME,
    Add,
    Attr,
    Call,
    Cmp,
    Comp,
    Const,
    DefRef,
    Div,
    Facts,
    Fn,
    FromRef,
    Fstr,
    Grown,
    IfExp,
    Imp,
    ModRef,
    Not,
    Obj,
    Param,
    Patch,
    Ref,
    Row,
    Seq,
    Site,
    Star,
    Sub,
    Table,
    Unknown,
    Unpack,
    Use,
    effective,
    extract,
    inside,
    live,
    load_cache,
    lookup,
    query_alias,
    save_cache,
    source_files,
    stamp,
    to_ir,
)

__all__ = [
    "AREAS",
    "INDEXED",
    "ROOT",
    "Finding",
    "HeadCopy",
    "Index",
    "PatchSite",
    "PatchTarget",
    "Reader",
    "Reference",
    "Unresolved",
    "Val",
    "inventory",
    "reach_text",
    "shared",
]

#: Höchstzahl der Zeilen einer Faltung. Darüber wird ein Wert ``unknown`` — gekürzt fehlte eine
#: Zeile still, und ein fehlendes Ziel sieht aus wie ein geprüftes.
MAX_ROWS = 4096

CACHE = Path("tools") / "__pycache__" / "code_index.data"

#: Tiefenmarke ohne Schnitt (siehe :meth:`Index._cached`).
_NO_CYCLE = 1 << 30

#: Namen, die jedes Modul hat, ohne sie zu binden.
_MODULE_DUNDERS = frozenset(
    {"__name__", "__file__", "__doc__", "__spec__", "__loader__", "__package__", "__dict__"}
    | {"__builtins__", "__cached__", "__annotations__"}
)

#: Fixtures, die pytest selbst liefert; ihr Wert ist ein Objekt, nie ein Modul.
_PYTEST_FIXTURES = frozenset(
    {"monkeypatch", "tmp_path", "tmp_path_factory", "tmpdir", "tmpdir_factory", "request"}
    | {"capsys", "capsysbinary", "capfd", "capfdbinary", "caplog", "recwarn", "pytestconfig"}
    | {"record_property", "record_testsuite_property", "doctest_namespace", "cache"}
    | {"pytester", "testdir", "subtests", "worker_id"}
)

_SEQUENCE_CALLS = frozenset(
    {"builtins.sorted", "builtins.tuple", "builtins.list", "builtins.reversed"}
    | {"builtins.set", "builtins.frozenset"}
)

#: Aufrufe, deren Ergebnis an den Argumenten hängt; bei allen anderen faltet der Index sie nicht.
_NEEDS_ARGUMENTS = _SEQUENCE_CALLS | {
    "importlib.import_module",
    "pytest.importorskip",
    "builtins.getattr",
    "builtins.hasattr",
    "builtins.enumerate",
    "builtins.zip",
    "builtins.str",
    "pytest.param",
    "pathlib.Path",
    "pathlib.PurePath",
    "pathlib.PurePosixPath",
    "importlib.util.spec_from_file_location",
    "importlib.util.module_from_spec",
    "textwrap.dedent",
}

#: Methoden eines Pfads, die wieder einen Pfad liefern.
_PATH_METHODS = frozenset({"resolve", "absolute", "expanduser", "joinpath", "with_suffix"})

_REF_KINDS = {"attr": "attribute", "store": "store", "del": "delete"}

#: Die Abfragen, deren Alias aus einem anderen Modul CS-34 meldet.
_QUERIES = frozenset({"builtins.getattr", "builtins.hasattr"})


# --------------------------------------------------------------------------- öffentliche Werte


from tools import code_scripts  # noqa: E402
from tools.code_report import inventory, reach_text  # noqa: E402
from tools.code_values import (  # noqa: E402
    Finding,
    HeadCopy,
    PatchSite,
    PatchTarget,
    Reader,
    Reference,
    Results,
    Unresolved,
    Val,
    keyword_arguments,
    sequence,
    unordered_items,
)
from tools.code_values import add as _add  # noqa: E402
from tools.code_values import compare as _compare  # noqa: E402
from tools.code_values import constant as _const  # noqa: E402
from tools.code_values import divide as _divide  # noqa: E402
from tools.code_values import elements as _elements  # noqa: E402
from tools.code_values import join as _join  # noqa: E402
from tools.code_values import joined as _joined  # noqa: E402
from tools.code_values import path_method as _path_method  # noqa: E402
from tools.code_values import text as _text  # noqa: E402

#: Die Quelle, wie dieser Prozess sie geladen hat; ``tools.code_store`` bildet daraus den
#: Stand des Auflösers, nicht aus der Platte (RR2-1).
_SOURCE = Path(__file__).read_bytes()

#: Eine Zeile der Faltung: je Quelle (Schleife, ``parametrize``, Aufrufstelle) der Zeilenindex.
Env = tuple[tuple[str, int], ...]
Res = list[tuple[Env, Val]]
#: Je Modul: Namen zur Laufzeit, Namen für die Typprüfung, Paket.
Names = tuple[frozenset[str], frozenset[str], bool]


def _merge(first: Env, second: Env) -> Env | None:
    """Zwei Zeilen vereinen; widersprechen sie sich in einer Quelle, gibt es die Zeile nicht."""
    if not first or first == second:
        return second
    if not second:
        return first
    merged = dict(first)
    for key, row in second:
        known = merged.get(key)
        if known is None:
            merged[key] = row
        elif known != row:
            return None
    return tuple(sorted(merged.items()))


def _chain_text(base: IR, attrs: tuple[str, ...]) -> str:
    head = base.name if isinstance(base, Use) else "…"
    return ".".join((head, *attrs))


def _name_table(modules: Mapping[str, Facts]) -> dict[str, Names]:
    """Je Modul die Namen, die es zur Laufzeit und für die Typprüfung hat, und ob es ein Paket
    ist — :meth:`Index.exists` fragt nur noch diese Tafel, auch ohne geladene Auszüge."""
    table: dict[str, Names] = {}
    for module, facts in modules.items():
        given = {*facts.exports, *facts.dynamic_names}
        binds = facts.scopes[0].binds
        runtime = given | {name for name in binds if effective(binds[name], facts.stub)}
        checking = given | {name for name in binds if effective(binds[name], facts.stub, True)}
        table[module] = frozenset(runtime), frozenset(checking), facts.package
    return table


class Index:
    """Der Index über einen Baum; gebaut mit :meth:`build`, aus dem Ergebnisspeicher mit
    :func:`tools.code_store.load` (dann lädt er Auszüge erst, wenn eine Frage sie braucht)."""

    def __init__(
        self,
        root: Path,
        files: Mapping[str, Facts],
        *,
        modules: Mapping[str, Facts] | None = None,
        packages: set[str] | None = None,
        names: dict[str, Names] | None = None,
    ) -> None:
        self.root = root
        self.files = files
        if modules is None:
            found: dict[str, Facts] = {}
            for facts in files.values():
                # ``x.py`` steht vor ``x.pyi``: Der Stub zählt nur, wo es kein Python gibt.
                found.setdefault(facts.module, facts)
            modules = found
        self.modules = modules
        if packages is None:
            packages = set()
            for facts in files.values():
                parts = facts.module.split(".")
                packages.update(".".join(parts[:size]) for size in range(1, len(parts)))
                if facts.package:
                    packages.add(facts.module)
        self.packages = packages
        #: Je Modul die Namen zur Laufzeit und für die Typprüfung und ob es ein Paket ist.
        self.module_names = _name_table(modules) if names is None else names
        #: Inhaltshash je Pfad, wie :meth:`build` ihn las (leer bei einem Index aus Auszügen).
        self.digests: dict[str, str] = {}
        self._findings: dict[str, tuple[Finding, ...]] | None = None
        self.timings: dict[str, float] = {}
        self.counts: dict[str, int] = {}
        self._memo: dict[tuple[object, ...], Res] = {}
        self._active: dict[tuple[object, ...], int] = {}
        self._low = _NO_CYCLE
        self._sites: dict[str, list[tuple[Facts, Site]]] | None = None
        self._numbers: dict[tuple[object, ...], int] = {}
        self._analysed = False
        self._readers: dict[tuple[str, str], dict[tuple[str, str, str], tuple[str, int]]] = {}
        self._references: dict[tuple[str, str], list[Reference]] = {}
        self._unresolved: list[Unresolved] = []
        self._heads: list[HeadCopy] = []
        self._patch_sites: list[PatchSite] = []
        #: Wer ``(M, N)`` beim Import liest — Module; zählt nur nach ``importlib.reload``.
        self._import_readers: dict[tuple[str, str], set[str]] = {}
        #: Je Patch-Stelle die Module, die ihr Test danach neu lädt.
        self._reloaded: dict[tuple[str, int, int], frozenset[str]] = {}
        self._aliases: list[tuple[str, str, str, int]] = []

    # ---- Bau

    @classmethod
    def build(cls, root: Path | None = None, *, cache: bool = True) -> Index:
        """Liest ``app/``, ``tools/`` und ``tests/`` unter ``root`` (Vorgabe: dieses
        Repository); ``cache`` hält die Auszüge je Datei nach Inhaltshash vor."""
        base = (root or ROOT).resolve()
        started = time.perf_counter()
        current = stamp()
        cache_file = base / CACHE
        sources = source_files(base)
        digests = {path: hashlib.sha256(full.read_bytes()).hexdigest() for path, full in sources}
        stored = load_cache(cache_file, current, digests) if cache else {}
        entries: dict[str, tuple[str, Facts]] = {}
        fresh = 0
        for relative, full in sources:
            digest = digests[relative]
            hit = stored.get(relative)
            if hit is not None and hit[0] == digest:
                entries[relative] = hit
                continue
            data = full.read_bytes()
            # Der Hash gehört zum Inhalt, der ausgezogen wird: Die Datei kann sich seit dem
            # ersten Lesen geändert haben.
            digests[relative] = hashlib.sha256(data).hexdigest()
            entries[relative] = (digests[relative], extract(relative, data))
            fresh += 1
        if cache and fresh:
            save_cache(cache_file, current, entries)
        index = cls(base, {relative: facts for relative, (_d, facts) in entries.items()})
        index.digests = digests
        index.timings["read"] = time.perf_counter() - started
        index.counts["extracted"] = fresh
        index.counts["cached"] = len(entries) - fresh
        return index

    # ---- Module und Namen

    def module_exists(self, module: str) -> bool:
        """Ob es das Modul oder Paket ``module`` in den Bereichen gibt."""
        return module in self.modules or module in self.packages

    def exists(self, module: str, name: str, *, checking: bool = False) -> bool:
        """Ob ``module.name`` zur Laufzeit existiert (mit ``checking`` auch nur für die
        Typprüfung)."""
        if self.module_exists(f"{module}.{name}"):
            return True
        entry = self.module_names.get(module)
        if entry is None:
            # Ein Namensraumpaket wie ``tools`` hat nur, was jedes Paket hat.
            return module in self.packages and (name in _MODULE_DUNDERS or name == "__path__")
        runtime, typing, package = entry
        if name in (typing if checking else runtime):
            return True
        return name in _MODULE_DUNDERS or (name == "__path__" and package)

    def _module_value(self, module: str) -> Val:
        if self.module_exists(module):
            return Val("module", module)
        if module.partition(".")[0] in AREAS:
            parent, _, name = module.rpartition(".")
            return Val("missing", module, (parent, name))
        return Val("ext", module)

    def _owner(self, module: str, name: str) -> tuple[str, str]:
        """Wo ``module.name`` wirklich gelesen wird: Ein Lazy-Export liest beim Ursprung."""
        seen: set[tuple[str, str]] = set()
        while (module, name) not in seen:
            seen.add((module, name))
            facts = self.modules.get(module)
            if facts is None or name not in facts.exports:
                break
            submodule, name = facts.exports[name]
            module = f"{module}.{submodule}"
        return module, name

    def _origin(self, module: str, name: str) -> tuple[tuple[str, str], ...]:
        """``(M, N)`` über Rückexporte und Lazy-Exporte bis zur Definition."""
        chain: list[tuple[str, str]] = []
        while (module, name) not in chain:
            chain.append((module, name))
            facts = self.modules.get(module)
            if facts is None:
                break
            if name in facts.exports:
                submodule, name = facts.exports[name]
                module = f"{module}.{submodule}"
                continue
            found = effective(facts.scopes[0].binds.get(name), facts.stub)
            if len(found) == 1 and isinstance(found[0].value, FromRef):
                source = found[0].value
                if any(
                    v.kind == "module" for _e, v in self._module_attr(source.module, source.name)
                ):
                    break
                module, name = source.module, source.name
                continue
            break
        return tuple(chain)

    def _module_attr(self, module: str, name: str, checking: bool = False) -> Res:
        return self._cached(
            ("@", module, name, checking), lambda: self._module_attr_new(module, name, checking)
        )

    def _module_attr_new(self, module: str, name: str, checking: bool = False) -> Res:
        facts = self.modules.get(module)
        qualified = f"{module}.{name}"
        result: Res = []
        found = effective(facts.scopes[0].binds.get(name), facts.stub, checking) if facts else []
        if facts is not None and name in facts.exports:
            submodule, attribute = facts.exports[name]
            result = self._attr(self._module_value(f"{module}.{submodule}"), attribute, checking)
        elif facts is not None and found:
            # Unbekannte Modulwerte bleiben unbekannt; ihr Ursprung kann ein Import sein.
            for bind in found:
                for env, value in self._fold(facts, bind.value):
                    result.append((env, value))
        elif facts is not None and name in facts.dynamic_names:
            result = [((), Val("obj", qualified))]
        elif self.module_exists(qualified):
            result = [((), Val("module", qualified))]
        elif name == "__name__":
            result = [((), _const(module))]
        elif name == "__file__" and facts is not None:
            result = [((), Val("path", facts.path))]
        elif name in _MODULE_DUNDERS or name == "__path__":
            result = [((), Val("obj", qualified))]
        else:
            result = [((), Val("missing", qualified, (module, name)))]
        return result

    def _attr(self, base: Val, name: str, checking: bool = False) -> Res:
        kind = base.kind
        if kind == "module":
            return self._module_attr(base.ref, name, checking)
        if kind == "ext":
            return [((), Val("ext", f"{base.ref}.{name}"))]
        if kind in ("unknown", "missing"):
            return [((), base)]
        if kind == "request" and name == "param":
            return self._fixture_params(base.ref)
        if kind == "path":
            path = PurePosixPath(base.ref)
            if name == "parent":
                return [((), Val("path", path.parent.as_posix()))]
            if name == "parents":
                return [((), Val("parents", base.ref))]
            if name in ("name", "stem", "suffix"):
                return [((), _const(getattr(path, name)))]
            if name in _PATH_METHODS:
                return [((), Val("method", name, base))]
        if kind == "const" and isinstance(base.data, str) and name == "join":
            # ``"; ".join((…))`` setzt ein Skript für ``python -c`` zusammen (CS-18).
            return [((), Val("method", name, base))]
        return [((), Val("obj", f"{base.ref}.{name}" if base.ref else name))]

    # ---- Faltung

    def _fold(self, facts: Facts, ir: IR) -> Res:
        """Was ``ir`` aus der Datei ``facts`` bedeuten kann, je Zeile der Faltung."""
        return self._cached((facts.path, ir), lambda: self._fold_new(facts, ir))

    def _cached(self, key: tuple[object, ...], compute: Callable[[], Res]) -> Res:
        """Rechnet ``compute`` einmal je ``key``; ein Zyklus wird an seinem Kopf geschnitten.

        Wer in einen Schlüssel zurückkehrt, der gerade gerechnet wird, bekommt ``unknown``.
        Gemerkt wird ein Ergebnis, wenn jeder Schnitt darunter nur den eigenen Schlüssel oder
        tiefere traf (Tarjans Tiefenmarke): Der Kopf eines Zyklus wird einmal gerechnet, nur
        seine Glieder bei jedem Eintritt neu — sonst wüchse die Arbeit mit jedem Zyklus
        exponentiell, und gemerkte Glieder hingen an der Frage, über die man eintrat."""
        hit = self._memo.get(key)
        if hit is not None:
            return hit
        depth = self._active.get(key)
        if depth is not None:
            self._low = min(self._low, depth)
            return [((), Val("unknown", "Zyklus"))]
        depth = len(self._active)
        self._active[key] = depth
        outer_low, self._low = self._low, _NO_CYCLE
        try:
            result = compute()
        finally:
            del self._active[key]
            inner_low, self._low = self._low, outer_low
        if inner_low < depth:
            self._low = min(self._low, inner_low)
        result = (
            [((), Val("unknown", "zu viele Zeilen"))]
            if len(result) > MAX_ROWS
            else list(dict.fromkeys(result))
        )
        if inner_low >= depth:
            self._memo[key] = result
        return result

    def _fold_new(self, facts: Facts, ir: IR) -> Res:
        if isinstance(ir, Use):
            return self._fold_use(facts, ir)
        if isinstance(ir, Attr):
            out: Res = []
            for env, base in self._fold(facts, ir.base):
                for env2, value in self._attr(base, ir.attr, ir.checking):
                    merged = _merge(env, env2)
                    if merged is not None:
                        out.append((merged, value))
            return out
        if isinstance(ir, Const):
            return [((), _const(ir.value))]
        if isinstance(ir, ModRef):
            return [((), self._module_value(ir.module))]
        if isinstance(ir, FromRef):
            return self._attr(self._module_value(ir.module), ir.name, ir.checking)
        if isinstance(ir, Seq):
            if any(isinstance(item, Star) for item in ir.items):
                return self._fold_starred(facts, ir)
            return self._combine(
                facts,
                ir.items,
                lambda values: Val(
                    "seq",
                    "unordered" if ir.unordered else "",
                    unordered_items(values) if ir.unordered else values,
                ),
            )
        if isinstance(ir, (Comp, Grown)):
            return self._fold_open(facts, ir)
        if isinstance(ir, Table):
            flat = tuple(part for pair in ir.pairs for part in pair)
            return self._combine(
                facts, flat, lambda v: Val("map", "", tuple(zip(v[::2], v[1::2], strict=True)))
            )
        if isinstance(ir, Sub):
            rows = self._rows(facts, (ir.base, ir.key))
            if rows is None:
                return [((), Val("unknown", "zu viele Zeilen"))]
            out = []
            for env, pair in rows:
                found = self._subscript(*pair)
                if len(found) == 1:
                    out.append((env, found[0]))
                    continue
                # Ein offener Index wählt eines der Elemente — für alle Namen, die aus
                # demselben Ausdruck entpackt werden, dasselbe.
                key = f"{facts.path}:index@{id(ir)}"
                for number, value in enumerate(found):
                    merged = _merge(env, ((key, number),))
                    if merged is not None:
                        out.append((merged, value))
            return out
        if isinstance(ir, Call):
            return self._fold_call(facts, ir)
        if isinstance(ir, Fstr):
            return self._combine(facts, ir.parts, _join)
        if isinstance(ir, Add):
            return self._combine(facts, (ir.left, ir.right), _add)
        if isinstance(ir, Div):
            return self._combine(facts, (ir.left, ir.right), _divide)
        if isinstance(ir, IfExp):
            return self._fold_if(facts, ir)
        if isinstance(ir, Cmp):
            return self._combine(facts, (ir.left, ir.right), lambda v: _compare(ir.op, v))
        if isinstance(ir, Not):
            return [
                (env, _const(not value.data) if value.kind == "const" else Val("obj", "not"))
                for env, value in self._fold(facts, ir.operand)
            ]
        if isinstance(ir, Unpack):
            return self._fold_unpack(facts, ir)
        if isinstance(ir, Row):
            return self._fold_row(facts, ir)
        if isinstance(ir, Param):
            return self._fold_param(facts, ir)
        if isinstance(ir, DefRef):
            return [((), Val(ir.kind, ir.ref))]
        if isinstance(ir, Obj):
            return [((), Val("obj", ir.reason))]
        if isinstance(ir, Unknown):
            return [((), Val("unknown", ir.reason))]
        raise TypeError(f"Unbekannte Form im Auszug: {type(ir).__name__}")

    def _fold_use(self, facts: Facts, ir: Use) -> Res:
        """Ein Name: je Bindung, die ihn erreichen kann, ihre Werte. Der Zweig der Stelle und
        der der Bindung gehen in die Zeile ein — so gilt eine Bindung aus dem ``else`` nicht
        im ``if``, und zwei Namen aus demselben Zweig bleiben gepaart."""
        at = (ir.line, ir.col)
        binds = lookup(facts.scopes, ir.scope, ir.name, at, checking=ir.checking)
        if binds is None:
            if ir.name == "__name__":
                # Als Skript gestartet heißt jedes Modul ``__main__``.
                return [((), _const(facts.module)), ((), _const("__main__"))]
            return [((), self._unbound(facts, ir.name))]
        regions = facts.scopes[ir.scope].regions
        around = [region for region in regions if inside(region[2], at)] if regions else []
        if not around and len(binds) == 1 and not binds[0].branch:
            return self._fold(facts, binds[0].value)
        here: Env = tuple(sorted((key, n) for key, n, _span, _test in around))
        out: Res = []
        for bind in binds:
            start = _merge(here, bind.branch)
            if start is None:
                continue
            for env, value in self._fold(facts, bind.value):
                merged = _merge(start, env)
                if merged is not None:
                    out.append((merged, value))
        tests = [(n, test) for _key, n, _span, test in around if test is not None]
        if tests:
            # Bleibt keine Zeile, ist der Zweig für die Faltung tot — geprüft wird er trotzdem:
            # Ein Helfer kann mit Werten gerufen werden, die der Auszug nicht sieht.
            out = [row for row in out if self._possible(facts, row[0], tests)] or out
        return out

    def _possible(self, facts: Facts, env: Env, tests: list[tuple[int, IR]]) -> bool:
        """Ob eine Zeile die Bedingungen der ``if`` um die Stelle erfüllen kann: Im ``else``
        von ``if phase == "entry"`` ist ``phase`` nie ``"entry"``."""
        for branch, test in tests:
            truths: set[bool] = set()
            for env2, value in self._fold(facts, test):
                if _merge(env, env2) is None:
                    continue
                if value.kind != "const":
                    truths = {True, False}
                    break
                truths.add(bool(value.data))
            if truths and (branch == 0) not in truths:
                return False
        return True

    def _fold_if(self, facts: Facts, ir: IfExp) -> Res:
        out: Res = []
        for env, test in self._fold(facts, ir.test):
            branches = [ir.body, ir.orelse]
            if test.kind == "const":
                branches = [ir.body if test.data else ir.orelse]
            for branch in branches:
                for env2, value in self._fold(facts, branch):
                    merged = _merge(env, env2)
                    if merged is not None:
                        out.append((merged, value))
        return out

    def _fold_unpack(self, facts: Facts, ir: Unpack) -> Res:
        out: Res = []
        for env, value in self._fold(facts, ir.value):
            items = _elements(value)
            if value.kind == "seq" and value.ref in ("open", "unordered") and items is not None:
                out.extend((env, item) for item in items or (Val("obj", "Element"),))
            elif items is not None and -len(items) <= ir.position < len(items):
                out.append((env, items[ir.position]))
            elif value.kind in ("unknown", "missing"):
                out.append((env, value))
            elif items is None:
                out.append((env, Val("obj", f"Element von {value.ref}")))
            else:
                out.append((env, Val("unknown", f"Entpacken von {value.kind}")))
        return out

    def _fold_starred(self, facts: Facts, ir: Seq) -> Res:
        """``(*a, b)``: die Elemente von ``a`` eingereiht; ist ``a`` kein Literal, bleibt die
        Folge offen, und ihre Elemente sind Objekte."""
        rows = self._rows(
            facts, (item.value if isinstance(item, Star) else item for item in ir.items)
        )
        if rows is None:
            return [((), Val("unknown", "zu viele Zeilen"))]
        out: Res = []
        for env, values in rows:
            items: list[Val] = []
            open_ = False
            for item, value in zip(ir.items, values, strict=True):
                if not isinstance(item, Star):
                    items.append(value)
                    continue
                inner = _elements(value)
                if value.kind in ("unknown", "missing"):
                    items.append(value)
                elif inner is None:
                    items.append(Val("obj", f"Element von {value.ref}"))
                else:
                    items.extend(inner)
                open_ = open_ or inner is None or value.ref == "open"
            order = "unordered" if ir.unordered else "open" if open_ else ""
            folded_items = unordered_items(tuple(items)) if ir.unordered else tuple(items)
            out.append((env, Val("seq", order, folded_items)))
        return out

    def _fold_open(self, facts: Facts, ir: Comp | Grown) -> Res:
        """Eine Folge, deren Länge erst zur Laufzeit feststeht: Jedes Element kann jedes der
        gefalteten sein; die Zeilen darin gelten nur innen und fallen weg. Eine Tabelle, die
        per Index, ``setdefault`` oder ``update`` wächst, bleibt eine (offene) Tabelle."""
        items: list[Val] = []
        if isinstance(ir, Comp) and ir.table:
            folded = self._fold(facts, ir.element)
            unknown = [
                (env, value) for env, value in folded if value.kind in ("unknown", "missing")
            ]
            if unknown:
                return unknown
            pairs = [
                value.data
                for _env, value in folded
                if value.kind == "seq" and isinstance(value.data, tuple)
            ]
            return [((), Val("map", "open", tuple(dict.fromkeys(pairs))))]
        if isinstance(ir, Comp):
            items.extend(value for _env, value in self._fold(facts, ir.element))
        else:
            bases = [base for _env, base in self._fold(facts, ir.base)]
            if any(base.kind in ("unknown", "missing") for base in bases):
                return [((), base) for base in bases if base.kind in ("unknown", "missing")]
            if any(base.kind == "map" for base in bases) or any(
                how in ("setitem", "update") for how, _ in ir.added
            ):
                return [((), self._open_map(facts, bases, ir.added))]
            for base in bases:
                items.extend(_elements(base) or ())
            for how, added in ir.added:
                for _env, value in self._fold(facts, added):
                    inner = _elements(value) if how == "extend" else None
                    if how != "extend" or value.kind in ("unknown", "missing"):
                        items.append(value)
                    elif inner is not None:
                        items.extend(inner)
                    else:
                        items.append(Val("obj", f"Element von {value.ref}"))
        return [((), Val("seq", "open", tuple(dict.fromkeys(items))))]

    def _fold_row(self, facts: Facts, ir: Row) -> Res:
        out: Res = []
        for env, iterable in self._fold(facts, ir.iterable):
            items = _elements(iterable)
            if iterable.kind in ("unknown", "missing"):
                out.append((env, iterable))
                continue
            if items is None or (not items and iterable.ref != "args"):
                # Was aus einem Objekt kommt, ist ein Objekt: Ein Modul, das zur Laufzeit in
                # ein Objekt gelegt wird, sieht der Auflöser nicht (Grenze im Docstring). Über
                # ein leeres Literal läuft keine Schleife — es wird auf einem Weg gefüllt, den
                # der Auszug nicht kennt (``workers.append`` als Rückruf). Genau leer sind nur
                # ``*args`` und ``**kwargs`` einer Aufrufstelle.
                out.append((env, Val("obj", f"Element von {iterable.ref}")))
                continue
            for number, item in enumerate(items):
                merged = _merge(env, ((ir.key, number),))
                if merged is not None:
                    out.append((merged, item))
        return out

    def _open_map(self, facts: Facts, bases: list[Val], added: tuple[tuple[str, IR], ...]) -> Val:
        pairs: list[tuple[Val, Val]] = []
        for base in bases:
            if base.kind in ("unknown", "missing"):
                return base
            if base.kind == "map" and isinstance(base.data, tuple):
                pairs.extend(base.data)
        for how, value in added:
            for _env, item in self._fold(facts, value):
                if item.kind in ("unknown", "missing"):
                    return item
                if how == "setitem" and item.kind == "seq" and isinstance(item.data, tuple):
                    key, entry = item.data
                    pairs.append((key, entry))
                elif how == "update" and item.kind == "map" and isinstance(item.data, tuple):
                    pairs.extend(item.data)
        return Val("map", "open", tuple(dict.fromkeys(pairs)))

    def _combine(
        self, facts: Facts, parts: Iterable[IR], make: Callable[[tuple[Val, ...]], Val]
    ) -> Res:
        rows = self._rows(facts, parts)
        if rows is None:
            return [((), Val("unknown", "zu viele Zeilen"))]
        return [(env, make(values)) for env, values in rows]

    def _rows(self, facts: Facts, parts: Iterable[IR]) -> list[tuple[Env, tuple[Val, ...]]] | None:
        """Das Kreuzprodukt der Zeilen aller Teile, soweit sie zusammenpassen.

        Hat jeder Teil genau eine Zeile — ein Literal aus Konstanten —, ist es eine Zeile;
        die Tabelle mit 256 Einträgen kostet dann 256 Schritte, nicht 256²."""
        # Ein Teil ohne eigene Zeile leert nicht das Ganze: Er wird ``unknown``. Ohne Zeile
        # bleibt, was erst im Zusammenspiel der Teile widerspricht.
        folded_parts = [
            self._fold(facts, part) or [((), Val("unknown", "keine Zeile"))] for part in parts
        ]
        if all(len(folded) == 1 for folded in folded_parts):
            env: Env | None = ()
            for folded in folded_parts:
                env = _merge(env, folded[0][0]) if env is not None else None
            if env is None:
                return []
            return [(env, tuple(folded[0][1] for folded in folded_parts))]
        rows: list[tuple[Env, tuple[Val, ...]]] = [((), ())]
        for folded in folded_parts:
            grown: list[tuple[Env, tuple[Val, ...]]] = []
            for env, values in rows:
                for env2, value in folded:
                    merged = _merge(env, env2)
                    if merged is not None:
                        grown.append((merged, (*values, value)))
            if len(grown) > MAX_ROWS:
                return None
            rows = grown
        return rows

    def _unbound(self, facts: Facts, name: str) -> Val:
        if name == "__name__":
            return _const(facts.module)
        if name == "__file__":
            return Val("path", facts.path)
        if name in _MODULE_DUNDERS or name == "__path__":
            return Val("obj", name)
        if hasattr(builtins, name):
            return Val("ext", f"builtins.{name}")
        return Val("unknown", f"ungebunden: {name}")

    def _subscript(self, base: Val, index: Val) -> list[Val]:
        """``base[index]``: Ein bekannter Index trifft ein Element, ein offener jedes."""
        if base.kind == "seq" and isinstance(base.data, tuple):
            items: tuple[Val, ...] = base.data
            position = index.data if index.kind == "const" else None
            if base.ref in ("open", "unordered") or not isinstance(position, int):
                return list(items) or [Val("obj", "Element")]
            if -len(items) <= position < len(items):
                return [items[position]]
            return [Val("unknown", "Index außerhalb")]
        if base.kind == "map" and isinstance(base.data, tuple):
            pairs: tuple[tuple[Val, Val], ...] = base.data
            if index.kind != "const":
                return [value for _key, value in pairs] or [Val("obj", "Element")]
            found = [
                value for key, value in pairs if key.kind == "const" and key.data == index.data
            ]
            if found:
                return found
            if base.ref == "open":
                return [value for key, value in pairs if key.kind != "const"] or [
                    Val("obj", "Element")
                ]
            return [Val("unknown", "Schlüssel fehlt")]
        if base.kind == "ext" and base.ref == "sys.modules":
            name = _text(index)
            return [self._module_value(name) if name else Val("unknown", "sys.modules[?]")]
        if base.kind == "parents" and index.kind == "const" and isinstance(index.data, int):
            path = PurePosixPath(base.ref)
            for _step in range(index.data + 1):
                path = path.parent
            return [Val("path", path.as_posix())]
        if base.kind in ("unknown", "missing"):
            return [base]
        return [Val("obj", f"{base.ref}[]")]

    def _fold_call(self, facts: Facts, ir: Call) -> Res:
        func = ir.func
        if isinstance(func, Attr) and func.attr in ("items", "keys", "values") and not ir.args:
            return self._fold_view(facts, func)
        functions = self._fold(facts, func)
        out: Res = []
        if not any(
            (f.kind == "ext" and f.ref in _NEEDS_ARGUMENTS) or f.kind == "method"
            for _env, f in functions
        ):
            # Was eine Klasse, eine eigene Funktion oder ein fremdes Programm zurückgibt, hängt
            # hier nicht an den Argumenten — sie zu falten kostete nur Zeilen. Ein Testhelfer
            # antwortet mit den Zeilen dieser Aufrufstelle: Seine Parameter tragen ihre Nummer,
            # und die Nummer gilt nur im Aufruf — zwei Aufrufe desselben Helfers in einem
            # Ausdruck widersprechen sich nicht.
            for env, function in functions:
                here = self._site_number(facts, ir, function)
                for env3, value in self._apply(function, ()):
                    inner = _merge(env3, here)
                    if inner is None:
                        continue
                    final = _merge(env, tuple(item for item in inner if item not in here))
                    if final is not None:
                        out.append((final, value))
            return out
        arguments = self._rows(facts, (*ir.args, *(value for _name, value in ir.keywords)))
        if arguments is None:
            return [((), Val("unknown", "zu viele Zeilen"))]
        for env, function in functions:
            for env2, values in arguments:
                merged = _merge(env, env2)
                if merged is None:
                    continue
                keywords = dict(
                    zip((name for name, _value in ir.keywords), values[len(ir.args) :], strict=True)
                )
                for env3, value in self._apply(function, values[: len(ir.args)], keywords):
                    final = _merge(merged, env3)
                    if final is not None:
                        out.append((final, value))
        return out

    def _fold_view(self, facts: Facts, func: Attr) -> Res:
        """``.items()``, ``.keys()`` und ``.values()`` einer gefalteten Tabelle."""
        out: Res = []
        for env, base in self._fold(facts, func.base):
            if base.kind in ("unknown", "missing"):
                out.append((env, base))
                continue
            if base.kind != "map" or not isinstance(base.data, tuple):
                out.append((env, Val("obj", f"{func.attr}()")))
                continue
            pairs: tuple[tuple[Val, Val], ...] = base.data
            if func.attr == "keys":
                items = tuple(key for key, _value in pairs)
            elif func.attr == "values":
                items = tuple(value for _key, value in pairs)
            else:
                items = tuple(Val("seq", "", pair) for pair in pairs)
            # Offen bleibt offen, genau bleibt genau (``**kwargs`` ohne Schlüsselwort).
            out.append((env, Val("seq", base.ref, items)))
        return out

    def _apply(
        self, function: Val, values: tuple[Val, ...], keywords: dict[str, Val] | None = None
    ) -> Res:
        kind, ref = function.kind, function.ref
        if kind == "ext":
            if ref in ("importlib.import_module", "pytest.importorskip") and values:
                name = _text(values[0])
                if name is None:
                    return [((), Val("unknown", "import_module mit offenem Namen"))]
                return [((), self._module_value(name))]
            if ref == "builtins.getattr" and len(values) >= 2:
                name = _text(values[1])
                if name is None:
                    return [((), Val("unknown", "getattr mit offenem Namen"))]
                found = self._attr(values[0], name)
                if len(values) >= 3:
                    found = [(e, values[2] if v.kind == "missing" else v) for e, v in found]
                return found
            if ref == "builtins.hasattr" and len(values) == 2:
                name = _text(values[1])
                target = values[0]
                if name is None or target.kind not in ("module", "missing"):
                    return [((), Val("obj", "hasattr()"))]
                own = target.kind == "module" and self.exists(target.ref, name)
                return [((), _const(own))]
            if ref in _SEQUENCE_CALLS | {"builtins.enumerate", "builtins.zip"} and values:
                return [((), self._sequence(ref, values, keywords))]
            if keywords:
                return [((), Val("unknown", f"Schlüsselwörter von {ref}"))]
            if ref == "pytest.param":
                return [((), Val("seq", "pytest.param", values))]
            if ref == "builtins.str" and len(values) == 1 and values[0].kind == "const":
                return [((), _const(str(values[0].data)))]
            if ref == "textwrap.dedent" and len(values) == 1:
                text = _text(values[0])
                dedented = _const(textwrap.dedent(text)) if text is not None else None
                return [((), dedented or Val("unknown", "dedent mit offenem Text"))]
            if ref.startswith("pathlib.") and len(values) == 1 and values[0].kind == "path":
                return [((), values[0])]
            if ref == "importlib.util.spec_from_file_location" and len(values) >= 2:
                return [((), self._spec(values[1]))]
            if ref == "importlib.util.module_from_spec" and values and values[0].kind == "spec":
                # Eine eigene Kopie des Moduls unter anderem Namen: Ihre Namen und Leser sind
                # die der Quelle, ein Patch darauf erreicht aber die Quelle nicht.
                return [((), Val("module", values[0].ref, "loaded"))]
            return [((), Val("obj", f"{ref}()"))]
        if kind == "method" and isinstance(function.data, Val):
            if function.data.kind == "const":
                return [((), _joined(function.data, values))]
            return [((), _path_method(ref, function.data, values))]
        if kind == "def" and ref.startswith("tests"):
            return self._returns(ref)
        if kind in ("def", "class"):
            return [((), Val("obj", f"{ref}()"))]
        if kind in ("unknown", "missing"):
            return [((), function)]
        return [((), Val("obj", "Aufrufergebnis"))]

    def _sequence(
        self, ref: str, values: tuple[Val, ...], keywords: dict[str, Val] | None = None
    ) -> Val:
        return sequence(ref, values, keywords or {}, MAX_ROWS)

    def _spec(self, path: Val) -> Val:
        """``spec_from_file_location(…, pfad)`` für eine Datei des Baums."""
        if path.kind == "path":
            facts = self.files.get(PurePosixPath(path.ref).as_posix())
            if facts is not None:
                return Val("spec", facts.module)
        return Val("obj", "spec")

    def _function(self, ref: str) -> tuple[Facts, Fn] | None:
        module, _, qualname = ref.partition(":")
        facts = self.modules.get(module)
        if facts is None:
            return None
        fn = facts.functions.get(qualname)
        return (facts, fn) if fn is not None else None

    def _returns(self, ref: str) -> Res:
        found = self._function(ref)
        if found is None:
            return [((), Val("obj", f"{ref}()"))]
        facts, fn = found
        if not fn.returns:
            return [((), _const(None))]
        return [row for value in fn.returns for row in self._fold(facts, value)]

    def _fold_param(self, facts: Facts, ir: Param) -> Res:
        fn = facts.functions.get(ir.function)
        if fn is None:
            return [((), Val("unknown", f"Parameter {ir.name}"))]
        for number, (names, table) in enumerate(fn.parametrize):
            if ir.name in names:
                return self._parametrized(facts, fn, number, names, table, ir.name)
        if fn.method and fn.params and fn.params[0] == ir.name:
            return [((), Val("obj", f"{fn.qualname}:{ir.name}"))]
        if ir.name in (fn.vararg, fn.kwarg) and not (fn.test or fn.fixture is not None):
            return self._call_rest(facts, fn, ir.name == fn.kwarg) or [
                ((), Val("unknown", f"Parameter {ir.name} ohne Aufrufstelle"))
            ]
        if facts.area == "tests" and (fn.test or fn.fixture is not None):
            if ir.name in fn.defaults:
                return self._fold(facts, fn.defaults[ir.name])
            if ir.name == "request" and fn.fixture is not None:
                return [((), Val("request", f"{facts.module}:{fn.qualname}"))]
            return self._fixture(facts, ir.name)
        out: Res = []
        if facts.area != "tests":
            # Wer eine Funktion in app/ oder tools/ ruft, sieht der Auszug nicht: Der Wert ist
            # offen, die Vorgabe nur einer davon. Ohne das schnitte eine Bedingung wie
            # ``if jacobian is None`` den anderen Zweig weg.
            if ir.name in fn.defaults:
                out.extend(self._fold(facts, fn.defaults[ir.name]))
            out.append(((), Val("unknown", f"Parameter {ir.name}")))
            return out
        out.extend(self._call_values(facts, fn, ir.name))
        return out or [((), Val("unknown", f"Parameter {ir.name} ohne Aufrufstelle"))]

    def _parametrized(
        self, facts: Facts, fn: Fn, number: int, names: tuple[str, ...], table: IR, name: str
    ) -> Res:
        key = f"{facts.path}:{fn.qualname}:parametrize{number}"
        position = names.index(name)
        out: Res = []
        for env, values in self._fold(facts, table):
            rows = _elements(values)
            if rows is None:
                out.append((env, Val("unknown", "parametrize ohne Literal")))
                continue
            for row_number, row in enumerate(rows):
                if row.ref == "pytest.param" and isinstance(row.data, tuple):
                    row = row.data[0] if len(names) == 1 and row.data else Val("seq", "", row.data)
                value = row
                if len(names) > 1:
                    items = _elements(row)
                    in_range = items is not None and position < len(items)
                    value = items[position] if items and in_range else Val("unknown", "Zeile")
                merged = _merge(env, ((key, row_number),))
                if merged is not None:
                    out.append((merged, value))
        return out

    def _fixture(self, facts: Facts, name: str) -> Res:
        if name in _PYTEST_FIXTURES:
            return [((), Val("obj", f"Fixture {name}"))]
        sources = self._fixture_sources(facts, name)
        if sources:
            return self._returns(sources[0])
        return [((), Val("unknown", f"Fixture {name} nicht gefunden"))]

    def _fixture_sources(self, facts: Facts, name: str) -> list[str]:
        """Woher pytest die Fixture ``name`` für diese Datei nimmt: die Datei selbst, ein
        eingebundener Name, dann ``conftest.py`` vom Ordner der Datei aufwärts."""
        found = [
            f"{facts.module}:{fn.qualname}"
            for fn in facts.functions.values()
            if fn.fixture == name and "." not in fn.qualname
        ]
        for bind in live(facts.scopes[0].binds.get(name)):
            for _env, value in self._fold(facts, bind.value):
                function = self._function(value.ref) if value.kind == "def" else None
                if function is not None and function[1].fixture is not None:
                    found.append(value.ref)
        folder = facts.path.rpartition("/")[0]
        while folder:
            conftest = self.files.get(f"{folder}/conftest.py")
            if conftest is not None:
                found.extend(
                    f"{conftest.module}:{fn.qualname}"
                    for fn in conftest.functions.values()
                    if fn.fixture == name and "." not in fn.qualname
                )
            folder = folder.rpartition("/")[0]
        return found

    def _fixture_params(self, ref: str) -> Res:
        found = self._function(ref)
        if found is None or found[1].fixture_params is None:
            return [((), Val("unknown", "request.param ohne params"))]
        facts, fn = found
        table = fn.fixture_params
        assert table is not None
        out: Res = []
        for env, values in self._fold(facts, table):
            for number, item in enumerate(_elements(values) or ()):
                if item.ref == "pytest.param" and isinstance(item.data, tuple) and item.data:
                    item = item.data[0]
                merged = _merge(env, ((f"{ref}:params", number),))
                if merged is not None:
                    out.append((merged, item))
        return out or [((), Val("unknown", "params ohne Literal"))]

    def _call_values(self, facts: Facts, fn: Fn, name: str) -> Res:
        """Was die Aufrufstellen eines Testhelfers an ``name`` übergeben, je Stelle eine Zeile."""
        ref = f"{facts.module}:{fn.qualname}"
        position = fn.params.index(name) if name in fn.params else -1
        out: Res = []
        for number, (site_facts, site) in enumerate(self._call_sites().get(ref, [])):
            rows = self._arguments(site_facts, site.args, site.keywords, {position}, {name})
            for env, args, keywords, open_, optional in rows:
                values: Res
                if 0 <= position < len(args):
                    value = (
                        args[position]
                        if name not in keywords
                        else Val("unknown", "doppeltes Argument")
                    )
                    values = [((), value)]
                elif name in keywords:
                    values = [((), keywords[name])]
                elif open_:
                    values = [((), Val("unknown", "offene Schlüsselworterweiterung"))]
                elif name in fn.defaults:
                    values = self._fold(facts, fn.defaults[name])
                else:
                    values = [((), Val("unknown", f"fehlendes Argument {name}"))]
                if name in optional and not 0 <= position < len(args):
                    values += (
                        self._fold(facts, fn.defaults[name])
                        if name in fn.defaults
                        else [((), Val("unknown", f"möglicherweise fehlendes Argument {name}"))]
                    )
                for inner, value in values:
                    merged = _merge(env, inner)
                    merged = (
                        _merge(merged, ((f"{ref}:call", number),)) if merged is not None else None
                    )
                    if merged is not None:
                        out.append((merged, value))
        return out

    def _arguments(
        self,
        facts: Facts,
        args: tuple[IR, ...],
        keywords: tuple[tuple[str, IR], ...],
        positions: set[int] | None = None,
        names: set[str] | None = None,
    ) -> list[tuple[Env, tuple[Val, ...], dict[str, Val], bool, frozenset[str]]]:
        """Aufrufform und ** vollständig; Werte nur für die abgefragten Parameter falten.

        Unbenutzte Argumente tragen keine zusätzlichen Helferzeilen ein. Ihre Positionen
        und Namen bleiben für die Bindung erhalten; jede **-Tabelle wird erhoben.
        """
        parts = (
            *(
                value if positions is None or i in positions else Obj("anderes Argument")
                for i, value in enumerate(args)
            ),
            *(
                value if name == "**" or names is None or name in names else Obj("anderes Argument")
                for name, value in keywords
            ),
        )
        rows = self._rows(facts, parts)
        if rows is None:
            return [((), (), {}, True, frozenset())]
        out = []
        keyword_names = tuple(name for name, _value in keywords)
        for env, values in rows:
            named, open_, optional = keyword_arguments(keyword_names, values[len(args) :])
            out.append((env, values[: len(args)], named, open_, optional))
        return out

    def _call_rest(self, facts: Facts, fn: Fn, keywords: bool) -> Res:
        """``*args`` als Folge der übrigen Argumente, ``**kwargs`` als Tabelle der übrigen
        Schlüsselwörter, je Aufrufstelle eine Zeile."""
        ref = f"{facts.module}:{fn.qualname}"
        named = {*fn.params, *fn.kwonly}
        out: Res = []
        for number, (site_facts, site) in enumerate(self._call_sites().get(ref, [])):
            positions = set() if keywords else set(range(len(fn.params), len(site.args)))
            names = (
                {name for name, _value in site.keywords if name not in named} if keywords else set()
            )
            rows = self._arguments(site_facts, site.args, site.keywords, positions, names)
            for env, args, supplied, open_, optional in rows:
                merged = _merge(env, ((f"{ref}:call", number),))
                if merged is None:
                    continue
                if keywords:
                    pairs = [
                        (_const(name), value)
                        for name, value in supplied.items()
                        if name not in named
                    ]
                    if open_:
                        pairs.append((Val("unknown", "Schlüssel"), Val("unknown", "Wert")))
                    partial = open_ or bool(optional - named)
                    out.append((merged, Val("map", "open" if partial else "args", tuple(pairs))))
                else:
                    out.append((merged, Val("seq", "args", args[len(fn.params) :])))
        return out

    def _call_sites(self) -> dict[str, list[tuple[Facts, Site]]]:
        if self._sites is None:
            sites: dict[str, list[tuple[Facts, Site]]] = {}
            self._sites = sites
            for facts in self.files.values():
                for site in facts.calls:
                    targets = {v.ref for _e, v in self._fold(facts, site.func) if v.kind == "def"}
                    for target in sorted(targets):
                        found = sites.setdefault(target, [])
                        where = (facts.path, site.func, site.args, site.keywords, target)
                        self._numbers[where] = len(found)
                        found.append((facts, site))
        return self._sites

    def _site_number(self, facts: Facts, ir: Call, function: Val) -> Env:
        """Die Zeile ``(helfer:call, n)``, wenn ``ir`` die ``n``-te Aufrufstelle des Helfers ist."""
        if function.kind != "def" or not function.ref.startswith("tests"):
            return ()
        self._call_sites()
        where = (facts.path, ir.func, ir.args, ir.keywords, function.ref)
        number = self._numbers.get(where)
        return () if number is None else ((f"{function.ref}:call", number),)

    # ---- Auswertung über den ganzen Baum

    def _analyse(self) -> None:
        if self._analysed:
            return
        self._analysed = True
        started = time.perf_counter()
        for facts in self.files.values():
            self._scan_imports(facts)
            self._scan_refs(facts)
            if facts.area in INDEXED:
                self._scan_globals(facts)
                self._scan_heads(facts)
        for facts in self.files.values():
            for patch in facts.patches:
                site = self._patch_site(facts, patch)
                if site is not None:
                    self._patch_sites.append(site)
        found, missing, counted = code_scripts.scan(self)
        for key, references in found.items():
            self._references.setdefault(key, []).extend(references)
        self._unresolved.extend(missing)
        self.counts.update(counted)
        self._patch_sites.sort()
        self._unresolved = sorted(set(self._unresolved))
        self._heads.sort()
        self._aliases = self._query_aliases()
        self.timings["resolve"] = time.perf_counter() - started

    def _query_aliases(self) -> list[tuple[str, str, str, int]]:
        """CS-34: ``has = hasattr`` auf Modulebene, das ein anderes Modul bezieht. Dort sieht der
        Auszug den Aufruf nicht als Abfrage (nur ein Alias derselben Datei, CS-27)."""
        found = []
        for facts in self.files.values():
            for name, binds in facts.scopes[0].binds.items():
                for bind in effective(binds, facts.stub):
                    if not query_alias(bind.value):
                        continue
                    values = {v.ref for _e, v in self._fold(facts, bind.value) if v.kind == "ext"}
                    if not values & _QUERIES:
                        continue
                    refs = self._references.get((facts.module, name), ())
                    if any(ref.path != facts.path for ref in refs):
                        found.append((facts.module, name, facts.path, bind.line))
        return sorted(set(found))

    def _count(self, key: str) -> None:
        self.counts[key] = self.counts.get(key, 0) + 1

    def _refer(self, reference: Reference) -> None:
        key = (reference.module, reference.name)
        self._references.setdefault(key, []).append(reference)
        owner = self._owner(*key)
        if owner != key:
            self._references.setdefault(owner, []).append(reference)

    def _read(self, owner: tuple[str, str], facts: Facts, scope: int, line: int, kind: str) -> None:
        if not facts.scopes[scope].runtime:
            self._import_readers.setdefault(owner, set()).add(facts.module)
            return
        readers = self._readers.setdefault(owner, {})
        readers.setdefault((facts.module, facts.scopes[scope].qualname, kind), (facts.path, line))

    def _unresolvable(
        self, facts: Facts, at: tuple[int, int], kind: str, module: str, name: str, text: str
    ) -> None:
        if module.partition(".")[0] in INDEXED:
            self._unresolved.append(Unresolved(facts.path, *at, kind, module, name, text))

    def _scan_imports(self, facts: Facts) -> None:
        for imp in facts.imports:
            self._count(f"imports.{imp.kind}")
            at = (imp.line, imp.col)
            if imp.kind == "dynamic":
                assert imp.arg is not None
                for _env, value in self._fold(facts, imp.arg):
                    name = _text(value)
                    if name is not None and not self.module_exists(name):
                        self._unresolvable(facts, at, "import_module", name, "", name)
                    elif name is not None:
                        self._refer(self._reference(facts, imp, "import_module", name, ""))
            elif imp.kind == "import":
                parts = imp.module.split(".")
                missing = next(
                    (
                        ".".join(parts[:size])
                        for size in range(1, len(parts) + 1)
                        if not self.module_exists(".".join(parts[:size]))
                    ),
                    None,
                )
                if missing is not None:
                    self._unresolvable(facts, at, "import", missing, "", f"import {imp.module}")
                else:
                    self._refer(self._reference(facts, imp, "import", imp.module, ""))
            else:
                self._scan_from(facts, imp)

    def _scan_from(self, facts: Facts, imp: Imp) -> None:
        text = f"from {imp.module} import {imp.name}"
        at = (imp.line, imp.col)
        if not self.module_exists(imp.module) or not self.exists(
            imp.module, imp.name, checking=imp.checking
        ):
            self._unresolvable(facts, at, "from", imp.module, imp.name, text)
            return
        self._refer(self._reference(facts, imp, "from", imp.module, imp.name))
        if not imp.checking and facts.area in INDEXED:
            self._read(self._owner(imp.module, imp.name), facts, imp.scope, imp.line, "import")

    def _reference(self, facts: Facts, imp: Imp, kind: str, module: str, name: str) -> Reference:
        return Reference(
            facts.path, imp.line, imp.col, kind, module, name, imp.runtime, imp.checking
        )

    def _scan_refs(self, facts: Facts) -> None:
        indexed_file = facts.area in INDEXED
        for ref in facts.refs:
            self._count(f"refs.{ref.kind}")
            if ref.name is not None:
                self._scan_getattr(facts, ref, indexed_file)
                continue
            # Ohne Merker: Die Basis eines Bezugs steht an genau einer Stelle und wird nur hier
            # gefaltet; Zyklen fängt der Merker der Bindungswerte darunter.
            values = {value for _env, value in self._fold_new(facts, ref.base)}
            if not values:
                # Keine Zeile: Die Faltung hat jede verworfen. Gezählt, damit Schweigen auffällt.
                self._count("refs.empty")
            last = len(ref.attrs) - 1
            for number, attr in enumerate(ref.attrs):
                label = _REF_KINDS[ref.kind if number == last else "attr"]
                following: set[Val] = set()
                for value in values:
                    if value.kind != "module":
                        continue
                    module = value.ref
                    if not self.exists(module, attr, checking=ref.checking):
                        text = _chain_text(ref.base, ref.attrs[: number + 1])
                        self._unresolvable(facts, (ref.line, ref.col), label, module, attr, text)
                        continue
                    where = (facts.path, ref.line, ref.col)
                    self._refer(Reference(*where, label, module, attr, ref.runtime, ref.checking))
                    if label == "attribute" and indexed_file and not ref.checking:
                        owner = self._owner(module, attr)
                        self._read(owner, facts, ref.scope, ref.line, "attribute")
                    if number < last:
                        following.update(
                            v
                            for _e, v in self._module_attr(module, attr, ref.checking)
                            if v.kind == "module"
                        )
                values = following
                if not values:
                    break

    def _query_kinds(self, facts: Facts, ref: Ref) -> set[str]:
        """``getattr``, ``getattr-default`` oder ``hasattr`` — das, woran der gerufene Name
        gebunden ist, für den Namen selbst wie für einen Alias (``query``). Ein Parameter oder
        eine eigene Bindung namens ``hasattr`` ist keine Abfrage (RR2-6)."""
        if ref.func is None:
            return {ref.kind}
        found = {value.ref for _env, value in self._fold(facts, ref.func) if value.kind == "ext"}
        default = ref.kind in ("query-default", "getattr-default")
        kinds = set()
        if "builtins.getattr" in found:
            kinds.add("getattr-default" if default else "getattr")
        if "builtins.hasattr" in found and not default:
            kinds.add("hasattr")
        return kinds

    def _scan_getattr(self, facts: Facts, ref: Ref, indexed_file: bool) -> None:
        """``getattr(M, "N")`` muss auflösen (W5). Mit Vorgabe und ``hasattr`` fragt der Code nach
        einer Abwesenheit, das ist kein Fund; gibt es ``N``, sind beide ein Bezug und lesen es zur
        Aufrufzeit (CS-27)."""
        assert ref.name is not None
        kinds = self._query_kinds(facts, ref)
        if not kinds:
            return
        for _env, pair in self._fold(facts, Seq((ref.base, ref.name))):
            if pair.kind != "seq" or not isinstance(pair.data, tuple):
                continue
            target, name_value = pair.data
            name = _text(name_value)
            if target.kind != "module" or name is None:
                continue
            for kind in sorted(kinds):
                if not self.exists(target.ref, name, checking=ref.checking):
                    if kind == "getattr":
                        text = f"getattr({target.ref}, {name!r})"
                        at = (ref.line, ref.col)
                        self._unresolvable(facts, at, "getattr", target.ref, name, text)
                    else:
                        self._count(f"absent.{kind}")
                    continue
                label = "hasattr" if kind == "hasattr" else "getattr"
                where = (facts.path, ref.line, ref.col)
                self._refer(Reference(*where, label, target.ref, name, ref.runtime, ref.checking))
                if indexed_file and not ref.checking:
                    owner = self._owner(target.ref, name)
                    self._read(owner, facts, ref.scope, ref.line, label)

    def _scan_globals(self, facts: Facts) -> None:
        module_binds = facts.scopes[0].binds
        for name in facts.import_reads:
            if effective(module_binds.get(name), facts.stub):
                self._import_readers.setdefault((facts.module, name), set()).add(facts.module)
        for name, users in facts.global_reads.items():
            if not effective(module_binds.get(name), facts.stub):
                continue
            readers = self._readers.setdefault((facts.module, name), {})
            for qualname, line in users:
                readers.setdefault((facts.module, qualname, "global"), (facts.path, line))

    def _scan_heads(self, facts: Facts) -> None:
        for imp in facts.imports:
            if imp.kind != "from" or imp.scope or imp.checking:
                continue
            if not any(
                bind.line == imp.end_line
                for bind in effective(facts.scopes[0].binds.get(imp.bound), facts.stub)
            ):
                continue
            if not self.exists(imp.module, imp.name):
                continue
            if any(v.kind == "module" for _e, v in self._module_attr(imp.module, imp.name)):
                continue
            chain = self._origin(imp.module, imp.name)
            copy = (facts.module, facts.path, imp.line, imp.bound, imp.module, imp.name, chain)
            self._heads.append(HeadCopy(*copy, "from"))
        for bound, binds in facts.scopes[0].binds.items():
            for bind in effective(binds, facts.stub):
                if bind.flags & (CHECKING | RUNTIME) or not isinstance(bind.value, Attr):
                    continue
                attr = bind.value.attr
                for _env, base in self._fold(facts, bind.value.base):
                    if base.kind != "module" or not self.exists(base.ref, attr):
                        continue
                    if any(v.kind == "module" for _e, v in self._module_attr(base.ref, attr)):
                        continue
                    chain = self._origin(base.ref, attr)
                    copy = (facts.module, facts.path, bind.line, bound, base.ref, attr, chain)
                    self._heads.append(HeadCopy(*copy, "assign"))

    def _patch_site(self, facts: Facts, patch: Patch) -> PatchSite | None:
        forms = {"unittest.mock.patch": "patch", "unittest.mock.patch.object": "patch.object"}
        if patch.func is not None and not any(
            value.ref in forms for _env, value in self._fold(facts, patch.func)
        ):
            return None
        parts = patch.args if patch.func is None else (patch.func, *patch.args)
        targets: list[PatchTarget] = []
        false_targets: list[PatchTarget] = []
        raising_values: set[Val] = set()
        used_forms: set[str] = set()
        positions = (
            {0, 1, 2} if patch.func is not None else {0, 1, 2 if patch.form == "delattr" else 3}
        )
        names = {"target", "name", "attribute", "raising"}
        argument_rows = self._arguments(facts, parts, patch.keywords, positions, names)
        for _env, args, keywords, open_, optional in argument_rows:
            form = patch.form
            if patch.func is not None:
                function = args[0] if args else Val("unknown", "zu viele Zeilen")
                form = forms.get(function.ref, "")
                args = args[1:]
                if not form:
                    if function.kind in ("unknown", "missing"):
                        targets.append(PatchTarget("unknown", "Patch-Aufrufer nicht faltbar", None))
                    continue
            used_forms.add(form)
            row_targets = self._target_values(form, args, keywords)
            targets.extend(row_targets)
            if open_ or optional & names:
                targets.append(PatchTarget("unknown", "offene Schlüsselworterweiterung", None))
            raising = keywords.get("raising")
            position = 2 if form == "delattr" else 3
            if form in ("setattr", "delattr") and len(args) > position:
                raising = args[position]
            if raising is not None:
                raising_values.add(raising)
                if raising == _const(False):
                    false_targets.extend(row_targets)
        if not targets:
            targets.append(PatchTarget("unknown", "keine Zeile", None))
        raising_summary = (
            False
            if _const(False) in raising_values
            else True
            if raising_values == {_const(True)}
            else None
        )
        patch = patch._replace(form="|".join(sorted(used_forms)) or patch.form)
        scope = facts.scopes[patch.scope]
        reloaded: set[str] = set()
        for number, line, col, argument, function_ir in facts.reloads:
            if number != patch.scope or not self._reload_reaches(facts, patch, (line, col)):
                continue
            rows = self._rows(facts, (function_ir, argument))
            if not rows or any(
                fn.ref != "importlib.reload" or module.kind != "module"
                for _env, (fn, module) in rows
            ):
                continue
            modules = {module.ref for _env, (_fn, module) in rows}
            if len(modules) == 1:
                reloaded.update(modules)
        self._reloaded[(facts.path, patch.line, patch.col)] = frozenset(reloaded)
        site = PatchSite(
            facts.path,
            patch.line,
            patch.col,
            scope.qualname,
            patch.form,
            patch.text,
            raising_summary,
            tuple(dict.fromkeys(targets)),
            tuple(dict.fromkeys(false_targets)),
        )
        for target in site.targets:
            if target.status in ("module", "loaded", "tests") and target.name is not None:
                at = (facts.path, patch.line, patch.col)
                self._refer(
                    Reference(*at, "patch", target.module, target.name, scope.runtime, False)
                )
        return site

    def _reload_reaches(self, facts: Facts, patch: Patch, at: tuple[int, int]) -> bool:
        """Ein Reload zählt nur im nachgewiesenen Pfad vor dem Abbau des Patches."""
        if patch.form not in ("setattr", "delattr") and patch.until is None:
            # Der Aufruf erzeugt nur einen Patcher. Erst ein aktiver Kontext belegt,
            # dass der Reload den Ersatz tatsächlich sieht.
            return False
        start = (patch.line, patch.col)
        if at <= start or (patch.until is not None and at > patch.until):
            return False
        if any(
            number == patch.scope and start < (line, col) < at for number, line, col in facts.resets
        ):
            return False
        scope = facts.scopes[patch.scope]
        if any(inside(span, at) for span in scope.uncertain):
            return False
        for line, col, limit in scope.exits:
            if (line, col) >= at or (limit is not None and not inside(limit, at)):
                continue
            unreachable = False
            for _key, branch, span, test in scope.regions:
                if test is None or not inside(span, (line, col)):
                    continue
                values = self._fold(facts, test)
                if values and all(
                    value.kind == "const" and bool(value.data) != (branch == 0)
                    for _env, value in values
                ):
                    unreachable = True
            if not unreachable:
                return False
        for _key, branch, span, test in scope.regions:
            if not inside(span, at) or inside(span, start):
                continue
            if test is None:
                return False
            values = self._fold(facts, test)
            if not values or any(
                value.kind != "const" or bool(value.data) != (branch == 0) for _env, value in values
            ):
                return False
        return True

    def _target_values(
        self, form: str, args: tuple[Val, ...], keywords: dict[str, Val]
    ) -> list[PatchTarget]:
        """Ein Ziel aus genau einer normalisierten Zeile, nach ihrer eigenen Aufrufform."""
        target = args[0] if args else keywords.get("target")
        if target is None:
            return [PatchTarget("unknown", "Aufruf ohne Ziel", None)]
        path_form = (
            form == "patch"
            or (form == "delattr" and len(args) < 2 and "name" not in keywords)
            or (
                form == "setattr"
                and len(args) < 3
                and "value" not in keywords
                and _text(target) is not None
            )
        )
        if path_form:
            text = _text(target)
            if text is None or "." not in text:
                return [PatchTarget("unknown", "Pfad nicht faltbar", None)]
            owner, _, name = text.rpartition(".")
            return [self._classify(value, name) for value in self._path(owner)]
        key = "attribute" if form == "patch.object" else "name"
        name_value = args[1] if len(args) > 1 else keywords.get(key)
        if name_value is None:
            return [PatchTarget("unknown", "Aufruf ohne Namen", None)]
        return [self._classify(target, _text(name_value))]

    def _path(self, dotted: str) -> list[Val]:
        """Ein Pfad als Text, aufgelöst wie ``monkeypatch``: Teil für Teil, Untermodule
        werden importiert, Attribute gelesen."""
        parts = dotted.split(".")
        values = [self._module_value(parts[0])]
        for part in parts[1:]:
            values = list(
                dict.fromkeys(found for value in values for _env, found in self._attr(value, part))
            )
        return values

    def _classify(self, value: Val, name: str | None) -> PatchTarget:
        kind = value.kind
        own = value.ref.partition(".")[0] in INDEXED
        if kind == "module" and value.data == "loaded":
            return PatchTarget("loaded" if own else "tests", value.ref, name)
        if kind == "module":
            return PatchTarget("module" if own else "tests", value.ref, name)
        if kind == "missing":
            return PatchTarget("missing" if own else "tests", value.ref, name)
        if kind == "ext":
            return PatchTarget("foreign", value.ref, name)
        if kind == "unknown":
            return PatchTarget("unknown", value.ref, name)
        return PatchTarget("object", f"{kind} {value.ref}".strip(), name)

    # ---- öffentliche Abfragen

    def resolve(self, path: str | Path, node: ast.AST) -> frozenset[Val]:
        """Was der Ausdruck ``node`` aus der Datei ``path`` statisch bedeutet. ``node`` stammt
        aus einem ``ast.parse`` derselben Datei; er wird über Lage und Typ gefunden."""
        if not isinstance(node, ast.expr):
            raise TypeError(f"resolve erwartet einen Ausdruck, nicht {type(node).__name__}")
        relative = Path(path)
        if relative.is_absolute():
            relative = relative.resolve().relative_to(self.root)
        facts = self.files[relative.as_posix()]
        at = (node.lineno, node.col_offset)
        scope = 0
        for number, candidate in enumerate(facts.scopes):
            if number and inside(candidate.span, at) and not inside(candidate.hole, at):
                scope = number
        scope, checking = facts.contexts.get(at, (scope, False))
        return frozenset(
            value
            for _env, value in self._fold(
                facts, to_ir(node, scope, comps=facts.comprehensions, checking=checking)
            )
        )

    def fold(self, facts: Facts, ir: IR) -> frozenset[Val]:
        """Was die Form ``ir`` aus dem Auszug ``facts`` bedeuten kann."""
        return frozenset(value for _env, value in self._fold(facts, ir))

    def scan_apart(
        self, facts: Facts
    ) -> tuple[dict[tuple[str, str], list[Reference]], list[Unresolved]]:
        """Bezüge und W5-Funde eines Auszugs, der nicht zum Baum gehört (ein Skript aus einer
        Zeichenkette, :mod:`tools.code_scripts`), getrennt von den eigenen Ergebnissen; Leser
        liefert er nur, wenn sein Bereich ``app`` oder ``tools`` ist."""
        saved = self._references, self._unresolved, self.counts
        self._references, self._unresolved, self.counts = {}, [], {}
        try:
            self._scan_imports(facts)
            self._scan_refs(facts)
            return self._references, self._unresolved
        finally:
            self._references, self._unresolved, self.counts = saved

    def patch_sites(self) -> tuple[PatchSite, ...]:
        """Alle Patch-Stellen in ``tests/``, nach Pfad und Zeile sortiert."""
        self._analyse()
        return tuple(self._patch_sites)

    def readers(self, module: str, name: str) -> tuple[Reader, ...]:
        """Die Lesermenge von ``module.name`` in ``app/`` und ``tools/``, sortiert."""
        self._analyse()
        found = self._readers.get((module, name), {})
        return tuple(
            sorted(
                Reader(holder, qualname, path, line, kind)
                for (holder, qualname, kind), (path, line) in found.items()
            )
        )

    def head_copies(self) -> tuple[HeadCopy, ...]:
        """Alle Kopfkopien in ``app/`` und ``tools/``, die kein Modul binden."""
        self._analyse()
        return tuple(self._heads)

    def unresolved(self) -> tuple[Unresolved, ...]:
        """Alle Bezüge auf ``app``/``tools``, die sich nicht auflösen (W5)."""
        self._analyse()
        return tuple(self._unresolved)

    def references(self, module: str, name: str) -> tuple[Reference, ...]:
        """Jeder aufgelöste Bezug auf ``module.name`` in ``app/``, ``tools/`` und ``tests/``."""
        self._analyse()
        return tuple(sorted(set(self._references.get((module, name), ()))))

    def patched_names(self) -> frozenset[tuple[str, str]]:
        """Die ``(M, N)`` aus ``app``/``tools``, die eine Patch-Stelle trifft."""
        return frozenset(
            (target.module, target.name)
            for site in self.patch_sites()
            for target in site.targets
            if target.status == "module" and target.name is not None
        )

    def reach_dump(self) -> dict[tuple[str, str], tuple[str, ...]]:
        """Je gepatchtem ``(M, N)`` die sortierte Lesermenge als ``modul:qualname``."""
        return {
            key: tuple(sorted({f"{r.module}:{r.qualname}" for r in self.readers(*key)}))
            for key in sorted(self.patched_names())
        }

    def query_aliases(self) -> tuple[tuple[str, str, str, int], ...]:
        """Jeder Alias von ``getattr``/``hasattr`` auf Modulebene, den ein anderes Modul bezieht:
        Modul, Name, Datei, Zeile (CS-34). Seine Aufrufe dort sind für den Index keine Abfrage."""
        self._analyse()
        return tuple(self._aliases)

    def import_count(self) -> int:
        """Wie viele Importe die Dateien des Baums haben (Grundmenge von W5, Plan 2.5)."""
        self._analyse()
        return sum(count for key, count in self.counts.items() if key.startswith("imports."))

    def results(self) -> Results:
        """Was die Abfragen beantwortet, für den Ergebnisspeicher (:mod:`tools.code_store`)."""
        self._analyse()
        return Results(
            tuple(self._patch_sites),
            tuple(self._heads),
            tuple(self._unresolved),
            self.patch_findings(),
            self._readers,
            {key: tuple(sorted(set(found))) for key, found in self._references.items()},
            dict(self.counts),
            dict(self.timings),
            tuple(self._aliases),
        )

    @classmethod
    def restored(
        cls,
        root: Path,
        files: Mapping[str, Facts],
        modules: Mapping[str, Facts],
        packages: set[str],
        names: dict[str, Names],
        results: Results,
    ) -> Index:
        """Ein Index aus gespeicherten Ergebnissen: Die Abfragen antworten aus ``results``,
        ``files`` und ``modules`` laden einen Auszug erst, wenn eine Frage ihn braucht."""
        index = cls(root, files, modules=modules, packages=packages, names=names)
        index._patch_sites = list(results.sites)
        index._heads = list(results.heads)
        index._unresolved = list(results.unresolved)
        index._findings = results.findings
        index._readers = results.readers
        index._references = {key: list(found) for key, found in results.references.items()}
        index.counts = dict(results.counts)
        index.timings = dict(results.timings)
        index._aliases = list(results.aliases)
        index._analysed = True
        return index

    def patch_findings(self) -> dict[str, tuple[Finding, ...]]:
        """Die Verstöße gegen W2, je Regel ``a`` bis ``e`` (Plan 2.2)."""
        if self._findings is None:
            self._findings = self._find()
        return dict(self._findings)

    def _find(self) -> dict[str, tuple[Finding, ...]]:
        found: dict[str, list[Finding]] = {rule: [] for rule in "abcde"}
        for site in self.patch_sites():
            reloaded = self._reloaded.get((site.path, site.line, site.col), frozenset())
            for target in site.targets:
                rule, detail = self._judge(target, reloaded)
                if rule:
                    module = "" if rule == "e" and target.status == "unknown" else target.module
                    name = target.name or ""
                    found[rule].append(Finding(rule, site.path, site.line, module, name, detail))
            module_targets = [t for t in site.false_targets if t.status in ("module", "loaded")]
            if site.raising is False and module_targets:
                first = module_targets[0]
                detail = "raising=False"
                finding = Finding("b", site.path, site.line, first.module, first.name or "", detail)
                found["b"].append(finding)
        patched = self.patched_names()
        refreshed = self._refreshed()
        for copy in self.head_copies():
            hits = [
                link
                for link in copy.chain
                if link in patched and copy.holder not in refreshed[link]
            ]
            if hits:
                detail = f"Kopfkopie ({copy.kind}) von {hits[0][0]}.{hits[0][1]}"
                finding = Finding("c", copy.path, copy.line, copy.holder, copy.bound, detail)
                found["c"].append(finding)
        return {rule: tuple(dict.fromkeys(items)) for rule, items in found.items()}

    def _refreshed(self) -> dict[tuple[str, str], frozenset[str]]:
        """Je gepatchtem ``(M, N)`` die Module, die **jeder** Test nach dem Patch neu lädt —
        deren Kopfkopie holt den gepatchten Wert, sie ist kein c)-Fund."""
        found: dict[tuple[str, str], frozenset[str]] = {}
        for site in self.patch_sites():
            reloaded = self._reloaded.get((site.path, site.line, site.col), frozenset())
            for target in site.targets:
                if target.status == "module" and target.name is not None:
                    key = (target.module, target.name)
                    found[key] = found[key] & reloaded if key in found else reloaded
        return found

    def _judge(self, target: PatchTarget, reloaded: frozenset[str]) -> tuple[str, str]:
        """Die Regel (a, d oder e), gegen die ein einzelnes Ziel verstößt, samt Grund.
        ``reloaded`` sind die Module, die der Test nach dem Patch neu lädt: Was sie beim Import
        lesen, erreicht der Patch."""
        if target.status == "missing":
            return "a", "Modul fehlt"
        if target.status == "unknown":
            return "e", f"Ziel nicht auflösbar: {target.module}"
        if target.status not in ("module", "loaded"):
            return "", ""
        if target.name is None:
            return "e", "Name nicht faltbar"
        if not self.exists(target.module, target.name):
            return "a", "Name fehlt"
        dunder = target.name.startswith("__") and target.name.endswith("__")
        owner = self._owner(target.module, target.name)
        refreshed = reloaded & self._import_readers.get(owner, set())
        if not dunder and not refreshed and not self.readers(target.module, target.name):
            # Einen Namen wie ``__path__`` liest der Interpreter selbst.
            return "d", "Lesermenge leer"
        return "", ""


# ------------------------------------------------------------------------------ Inventar


@functools.cache
def shared() -> Index:
    """Der Index dieses Repositorys, einmal je Prozess: W2, W5, W6 und ``test_code_index.py``
    teilen ihn. Er kommt aus dem Ergebnisspeicher (:func:`tools.code_store.load`) — gebaut wird
    einmal je Baumstand, nicht je Prozess.

    Danach friert der Sammler alles ein, was lebt: Der Index lebt bis zum Prozessende, und
    ``tests/conftest.py`` ruft je Fenstertest zweimal ``gc.collect()`` (CS-23)."""
    from tools import code_store

    index = code_store.load(ROOT)
    gc.collect()
    gc.freeze()
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Statischer Auflöser für app/, tools/, tests/")
    parser.add_argument("--root", type=Path, default=ROOT, help="Wurzel des Baums")
    parser.add_argument("--no-cache", action="store_true", help="ohne Zwischenspeicher")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--inventory", action="store_true", help="Inventar ausgeben")
    action.add_argument("--reach", action="store_true", help="Lesermengen ausgeben")
    args = parser.parse_args(argv)
    index = Index.build(args.root, cache=not args.no_cache)
    text = inventory(index) if args.inventory else reach_text(index)
    sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
