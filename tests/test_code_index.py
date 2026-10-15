"""Der gemeinsame Auflöser ``tools/code_index.py`` an Fällen, deren Ausgang bekannt ist.

**Warum es diese Datei gibt.** Auf dem Auflöser stehen die Wächter W2
(``test_patch_targets.py``) und W5 (``test_import_resolution.py``) und das
Verschiebewerkzeug ``tools/move_names.py`` (Konzept Codestruktur 4.1, Plan
Schritt 0, 2.0). Ein Auflöser, der zu wenig findet, schweigt — und Schweigen
sieht aus wie ein grüner Wächter. Geprüft wird deshalb an einer Attrappe in
``tmp_path`` jede Form, an der ein Textverfahren gescheitert ist (Plan 2.5 und
4: verschattetes Alias, Alias je Funktion, Lazy-Export, ``__getattr__``,
``.pyi``, ``type``, ``TYPE_CHECKING``, Konstantenfaltung), und je Regel von W2
ein roter Fall. Am echten Baum stehen die Bekanntfälle aus Plan 2.2 und die
Grundmengen mit den Zahlen aus dem Plan.

Die Bekanntfälle am echten Baum gelten, **solange ihre Fixes fehlen** (Plan
2.2): Wer einen behebt, streicht seinen Fall hier im selben Commit; die
Meldung des Tests nennt dann das Paket und die Regel von W2, die ihn ab da
hält. Trägt diese Regel noch ``xfail``, wird der Fall umgekehrt statt
gestrichen und hält den behobenen Stand, bis sie scharf ist (CS-9a).
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from tools import code_index
from tools.code_index import HeadCopy, Index, Reader, Val

#: Die Attrappe: ein Baum mit ``app/``, ``tools/`` und ``tests/``. Kommentare
#: der Form ``# <marke>`` benennen Zeilen, an denen die Tests etwas erwarten.
FAKE: dict[str, str] = {
    "app/__init__.py": "",
    "app/lazy.py": """
        def install(package, exports):
            return None
    """,
    "app/mod.py": """
        from __future__ import annotations

        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from app.other import Hidden  # mod-checking

        CONST = 1
        LIMIT = 3
        SPAN = 4
        type Alias = int


        def target() -> int:
            return 1


        def reader() -> int:
            return target() + CONST


        def __getattr__(name: str) -> object:
            if name == "DYN":
                return 2
            raise AttributeError(name)
    """,
    "app/other.py": """
        from app.mod import target  # kopfkopie


        class Hidden:
            pass


        def uses() -> int:
            return target()
    """,
    "app/pkg/__init__.py": """
        from app.lazy import install

        _EXPORTS = {"lazy_fn": ("sub", "lazy_fn")}
        install(__name__, _EXPORTS)
    """,
    "app/pkg/sub.py": """
        def lazy_fn() -> int:
            return 3
    """,
    "app/via_pkg.py": """
        from app import pkg


        def call() -> int:
            return pkg.lazy_fn()  # ueber-paket
    """,
    "app/stubbed.pyi": """
        SIZE: int

        def compiled() -> int: ...
    """,
    "app/unread.py": """
        def only_listed() -> int:
            return 4


        WAYS = (only_listed,)
    """,
    "app/table_user.py": """
        from app.mod import LIMIT, SPAN

        LIMITS = (LIMIT, SPAN)
    """,
    "app/loops.py": """
        from app import mod


        def walk(items):
            current = None
            for _item in items:
                if current is not None:
                    current.reader()  # schleife-weiter
                current = mod
    """,
    "tools/tool.py": """
        def late() -> int:
            from app.mod import CONST  # spaet

            return CONST


        def renamed() -> int:
            from app.mod import OLD_NAME  # spaet-umbenannt

            return OLD_NAME
    """,
    "tests/conftest.py": """
        import pytest

        from app import mod


        @pytest.fixture
        def the_module():
            return mod
    """,
    "tests/test_green.py": """
        import importlib
        from typing import Final

        import pytest

        from app import mod, other
        from app.mod import DYN, Alias  # gruen-import
        from app.pkg import lazy_fn  # gruen-lazy
        from app.stubbed import SIZE, compiled  # gruen-stub

        NAMES: Final = ("target",)
        TABLE = {"x": ("app.mod", "CONST")}


        def test_shadow(monkeypatch):
            mod = object()
            mod.missing  # schatten
            monkeypatch.setattr(mod, "missing", 1)  # schatten-patch


        def test_alias_a():
            from app import mod as module

            module.reader  # alias-a


        def test_alias_b():
            from app import other as module

            module.reader  # alias-b


        def test_loop(monkeypatch):
            for name in ("target", "CONST"):
                monkeypatch.setattr(mod, name, None)  # schleife


        @pytest.mark.parametrize("name", ["target", "nope"])
        def test_param(monkeypatch, name):
            monkeypatch.setattr(mod, name, None)  # parametrize


        def test_final(monkeypatch):
            for name in NAMES:
                monkeypatch.setattr(mod, name, None)  # final


        @pytest.mark.parametrize("way", sorted(TABLE))
        def test_table(monkeypatch, way):
            module_name, attr = TABLE[way]
            module = importlib.import_module(module_name)
            monkeypatch.setattr(module, attr, 5)  # tabelle


        def test_pairs(monkeypatch):
            for module, name in ((mod, "target"), (other, "target")):
                monkeypatch.setattr(module, name, None)  # paare


        def _patch(patcher, module, name):
            patcher.setattr(module, name, None)  # helfer


        def test_helper(monkeypatch):
            _patch(monkeypatch, mod, "CONST")


        def test_fixture(monkeypatch, the_module):
            monkeypatch.setattr(the_module, "target", None)  # fixture


        @pytest.mark.parametrize("phase", ["first", "second"])
        def test_branches(monkeypatch, phase):
            if phase == "first":
                module, name = mod, "CONST"
            else:
                module, name = other, "target"
            monkeypatch.setattr(module, name, None)  # zweige


        @pytest.mark.parametrize("phase", ["entry", "x"])
        def test_pruned(monkeypatch, phase):
            if phase == "entry":
                return
            else:
                name = {"x": "target"}[phase]
                monkeypatch.setattr(mod, name, None)  # schnitt


        def test_grown(monkeypatch):
            found = []
            found.append(mod)
            for module in found:
                monkeypatch.setattr(module, "CONST", 1)  # gefuellt


        def test_comprehension(monkeypatch):
            modules = [module for module in (mod, other)]
            for module in modules:
                monkeypatch.setattr(module, "target", None)  # abstraktion


        def test_starred(monkeypatch):
            for module in (*(mod,), other):
                monkeypatch.setattr(module, "target", None)  # stern


        def _many(patcher, **names):
            for name, value in names.items():
                patcher.setattr(mod, name, value)  # kwargs


        def test_kwargs(monkeypatch):
            _many(monkeypatch, CONST=2, target=None)


        def test_hasattr(monkeypatch):
            chosen = mod if hasattr(mod, "reader") else other
            monkeypatch.setattr(chosen, "reader", None)  # hasattr


        def test_loaded(monkeypatch):
            import importlib.util
            from pathlib import Path

            path = Path(__file__).parents[1] / "tools" / "tool.py"
            spec = importlib.util.spec_from_file_location("kopie", path)
            loaded = importlib.util.module_from_spec(spec)
            monkeypatch.setattr(loaded, "late", None)  # geladen


        def test_reload(monkeypatch):
            import importlib

            from app import table_user

            monkeypatch.setattr(mod, "LIMIT", 5)  # neu-geladen
            importlib.reload(table_user)
    """,
    "tests/test_red.py": """
        from typing import TYPE_CHECKING
        from unittest import mock

        import app.missing  # w5-import
        from app import mod, pkg, unread
        from app.mod import NOPE  # w5-getattr-literal
        from app.mod import Hidden  # w5-checking
        from app.pkg import nope  # w5-lazy
        from app.stubbed import absent  # w5-stub

        if TYPE_CHECKING:
            from app.mod import Hidden as Seen  # checking-ok


        def test_a(monkeypatch):
            monkeypatch.setattr(mod, "nope", 1)  # a-name
            monkeypatch.setattr("app.nomodule.x", 1)  # a-modul


        def test_b(monkeypatch):
            monkeypatch.setattr(mod, "CONST", 1, raising=False)  # b


        def test_c(monkeypatch):
            monkeypatch.setattr(mod, "target", None)  # c-original


        def test_d(monkeypatch):
            monkeypatch.setattr(unread, "only_listed", None)  # d
            monkeypatch.setattr(pkg, "lazy_fn", None)  # d-lazy


        def _blind(patcher, thing):
            patcher.setattr(thing, "x", 1)  # e-ziel


        def test_e(monkeypatch):
            monkeypatch.setattr(mod, str(len("ab")), 1)  # e-name
            mod.ABSENT = 1  # w5-store


        @mock.patch("app.mod.target")  # mock-pfad
        def test_mock(patched):
            with mock.patch.object(mod, "CONST", 2):  # mock-objekt
                pass


        def patch(first, second):
            return first


        def test_not_mock():
            patch(mod, "nothing")  # kein-patch


        def test_without_reload(monkeypatch):
            monkeypatch.setattr(mod, "SPAN", 9)  # ohne-neuladen
    """,
}


def _source(path: str) -> str:
    return textwrap.dedent(FAKE[path]).lstrip("\n")


def _line(path: str, marker: str) -> int:
    """Die Zeile der Attrappe, die ``# <marker>`` trägt — genau eine."""
    found = [
        number
        for number, text in enumerate(_source(path).splitlines(), start=1)
        if text.rstrip().endswith(f"# {marker}")
    ]
    assert len(found) == 1, f"Marke {marker!r} steht {len(found)}-mal in {path}"
    return found[0]


def _write(root: Path) -> Path:
    for path in FAKE:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_source(path), encoding="utf-8")
    return root


@pytest.fixture
def fake(tmp_path: Path) -> Index:
    return Index.build(_write(tmp_path / "baum"), cache=False)


def _targets(index: Index, path: str, marker: str) -> set[tuple[str, str, str | None]]:
    line = _line(path, marker)
    sites = [site for site in index.patch_sites() if site.path == path and site.line == line]
    assert len(sites) == 1, f"{path}:{line} ({marker}) ist {len(sites)}-mal eine Patch-Stelle"
    return {(t.status, t.module, t.name) for t in sites[0].targets}


def _unresolved_at(index: Index, path: str, marker: str) -> set[tuple[str, str, str]]:
    line = _line(path, marker)
    return {
        (u.kind, u.module, u.name) for u in index.unresolved() if (u.path, u.line) == (path, line)
    }


def _findings_at(index: Index, rule: str, path: str, marker: str) -> list[str]:
    line = _line(path, marker)
    return [
        f"{f.module}.{f.name}: {f.detail}"
        for f in index.patch_findings()[rule]
        if (f.path, f.line) == (path, line)
    ]


# --------------------------------------------------------------------------- Attrappe


def test_a_shadowing_local_is_not_the_module_alias(fake: Index) -> None:
    """``mod = object()`` in einer Funktion verschattet den Modulalias: ``mod.missing``
    ist dann kein W5-Fund und der Patch darauf kein Modulpatch. Ein Textverfahren meldete
    in ``test_viewport_decisions.py`` 1 540 solche Scheintreffer (Plan 2.5)."""
    assert _unresolved_at(fake, "tests/test_green.py", "schatten") == set()
    assert {status for status, *_ in _targets(fake, "tests/test_green.py", "schatten-patch")} == {
        "object"
    }


def test_an_alias_holds_per_function_not_per_file(fake: Index) -> None:
    """``module`` meint in ``test_alias_a`` ``app.mod`` und in ``test_alias_b``
    ``app.other`` — wie ``module`` in ``tests/test_variants_ui.py`` (Plan 1.4). Nur der
    zweite Zugriff ist rot, weil ``app.other`` kein ``reader`` hat."""
    assert _unresolved_at(fake, "tests/test_green.py", "alias-a") == set()
    assert _unresolved_at(fake, "tests/test_green.py", "alias-b") == {
        ("attribute", "app.other", "reader")
    }


def test_a_lazy_export_resolves_and_is_read_at_its_origin(fake: Index) -> None:
    """``_EXPORTS`` mit ``install`` macht ``lazy_fn`` zum Namen des Pakets; gelesen wird
    beim Ursprung ``app.pkg.sub``. Ein Patch auf das Paket greift nicht (``LazyPackage``
    liest am ``__dict__`` vorbei) — seine Lesermenge ist leer, W2 d) ist rot."""
    assert fake.exists("app.pkg", "lazy_fn")
    assert _unresolved_at(fake, "tests/test_green.py", "gruen-lazy") == set()
    assert _unresolved_at(fake, "tests/test_red.py", "w5-lazy") == {("from", "app.pkg", "nope")}
    line = _line("app/via_pkg.py", "ueber-paket")
    assert Reader("app.via_pkg", "call", "app/via_pkg.py", line, "attribute") in fake.readers(
        "app.pkg.sub", "lazy_fn"
    )
    assert fake.readers("app.pkg", "lazy_fn") == ()
    assert _findings_at(fake, "d", "tests/test_red.py", "d-lazy") == [
        "app.pkg.lazy_fn: Lesermenge leer"
    ]


def test_the_literals_of_a_module_getattr_are_names(fake: Index) -> None:
    """Wie ``PARTS`` (``knowledge/parts/builtin.py``) und ``MENU_TWINS``
    (``registry/registry.py``): Was ``__getattr__`` vergleicht, existiert; anderes nicht."""
    assert fake.exists("app.mod", "DYN")
    assert _unresolved_at(fake, "tests/test_green.py", "gruen-import") == set()
    assert _unresolved_at(fake, "tests/test_red.py", "w5-getattr-literal") == {
        ("from", "app.mod", "NOPE")
    }


def test_a_stub_stands_for_a_compiled_module(fake: Index) -> None:
    """Wie ``app/core/slice/_chain.pyi``: Ohne Python-Datei zählt der Stub, auch eine reine
    Annotation darin."""
    assert fake.exists("app.stubbed", "compiled")
    assert fake.exists("app.stubbed", "SIZE")
    assert _unresolved_at(fake, "tests/test_green.py", "gruen-stub") == set()
    assert _unresolved_at(fake, "tests/test_red.py", "w5-stub") == {
        ("from", "app.stubbed", "absent")
    }


def test_a_type_statement_binds_a_name(fake: Index) -> None:
    """``type Alias = int`` bindet wie ``type Form`` in ``knowledge/parts/shapes.py``."""
    assert fake.exists("app.mod", "Alias")


def test_type_checking_imports_bind_only_for_the_type_checker(fake: Index) -> None:
    """``Hidden`` steht in ``app.mod`` nur unter ``TYPE_CHECKING``: Zur Laufzeit importiert
    ist es rot, unter ``TYPE_CHECKING`` grün, und es ist keine Kopfkopie."""
    assert not fake.exists("app.mod", "Hidden")
    assert fake.exists("app.mod", "Hidden", checking=True)
    assert _unresolved_at(fake, "tests/test_red.py", "w5-checking") == {
        ("from", "app.mod", "Hidden")
    }
    assert _unresolved_at(fake, "tests/test_red.py", "checking-ok") == set()
    assert not [copy for copy in fake.head_copies() if copy.holder == "app.mod"]


@pytest.mark.parametrize(
    ("marker", "expected"),
    [
        ("schleife", {("app.mod", "target"), ("app.mod", "CONST")}),
        ("parametrize", {("app.mod", "target"), ("app.mod", "nope")}),
        ("final", {("app.mod", "target")}),
        ("tabelle", {("app.mod", "CONST")}),
        ("paare", {("app.mod", "target"), ("app.other", "target")}),
        ("helfer", {("app.mod", "CONST")}),
        ("fixture", {("app.mod", "target")}),
        ("zweige", {("app.mod", "CONST"), ("app.other", "target")}),
        ("schnitt", {("app.mod", "target")}),
        ("gefuellt", {("app.mod", "CONST")}),
        ("abstraktion", {("app.mod", "target"), ("app.other", "target")}),
        ("stern", {("app.mod", "target"), ("app.other", "target")}),
        ("kwargs", {("app.mod", "CONST"), ("app.mod", "target")}),
        ("hasattr", {("app.mod", "reader")}),
    ],
)
def test_constant_folding_finds_every_target(
    fake: Index, marker: str, expected: set[tuple[str, str]]
) -> None:
    """Namen aus Schleifen über Literale, ``parametrize``, ``Final``-Tupeln, Tabellen wie
    ``_THREADED`` (``test_platform_identity.py``), den Aufrufstellen eines Helfers und
    Fixtures werden gefaltet. ``paare`` hält die Zeilen zusammen: zwei Ziele, kein
    Kreuzprodukt aus vier; ``zweige`` ebenso über ``if``/``else`` (``test_repair.py``).
    ``schnitt`` liest die Bedingung: Im ``else`` von ``phase == "entry"`` fehlt der
    Schlüssel ``"entry"`` nie (``test_parts.py``). ``gefuellt``, ``abstraktion``,
    ``stern`` und ``kwargs`` falten Behälter, die erst der Code füllt
    (``test_kernel_process.py``, ``test_overlay.py``, ``test_refine.py``); ``hasattr``
    wählt den Zweig eines ``if``-Ausdrucks (``test_geometry_review.py``)."""
    found = _targets(fake, "tests/test_green.py", marker)
    assert found == {("module", module, name) for module, name in expected}


def test_a_module_loaded_by_path_is_its_own_copy(fake: Index) -> None:
    """``spec_from_file_location`` mit einem Pfad aus ``Path(__file__)`` lädt eine Kopie von
    ``tools/tool.py`` (``test_delivery_matrix_review.py``): Ihre Namen und Leser sind die der
    Quelle, ein Patch darauf zählt nicht als Patch am Original."""
    assert _targets(fake, "tests/test_green.py", "geladen") == {("loaded", "tools.tool", "late")}
    assert ("tools.tool", "late") not in fake.patched_names()


def test_reloading_a_module_lets_its_import_time_reads_see_the_patch(fake: Index) -> None:
    """``importlib.reload`` nach dem Patch führt die Modulebene neu aus: Die Tabelle in
    ``app.table_user`` liest dann den gepatchten Wert (``test_advise.py``, B12). Ohne Neuladen
    bleibt ``SPAN`` ein Name ohne Leser, und die Kopfkopie ist ein c)-Fund."""
    assert _findings_at(fake, "d", "tests/test_green.py", "neu-geladen") == []
    assert _findings_at(fake, "d", "tests/test_red.py", "ohne-neuladen") == [
        "app.mod.SPAN: Lesermenge leer"
    ]
    copies = {f.name for f in fake.patch_findings()["c"] if f.path == "app/table_user.py"}
    assert copies == {"SPAN"}


def test_a_binding_later_in_a_loop_reaches_the_next_round(fake: Index) -> None:
    """``current = mod`` steht in der Schleife hinter dem Zugriff und gilt im nächsten
    Durchlauf: ``walk`` liest ``mod.reader``."""
    line = _line("app/loops.py", "schleife-weiter")
    assert Reader("app.loops", "walk", "app/loops.py", line, "attribute") in fake.readers(
        "app.mod", "reader"
    )


def test_rule_a_finds_a_missing_name_and_a_missing_module(fake: Index) -> None:
    assert _findings_at(fake, "a", "tests/test_red.py", "a-name") == ["app.mod.nope: Name fehlt"]
    assert _findings_at(fake, "a", "tests/test_red.py", "a-modul") == [
        "app.nomodule.x: Modul fehlt"
    ]
    assert _findings_at(fake, "a", "tests/test_green.py", "parametrize") == [
        "app.mod.nope: Name fehlt"
    ]


def test_rule_b_finds_raising_false_on_an_own_module(fake: Index) -> None:
    assert _findings_at(fake, "b", "tests/test_red.py", "b") == ["app.mod.CONST: raising=False"]


def test_rule_c_finds_the_head_copy_of_a_patched_original(fake: Index) -> None:
    """``app.other`` hält ``from app.mod import target``; ``mod.target`` wird gepatcht,
    der Patch erreicht die Kopie nie (CS-11)."""
    line = _line("app/other.py", "kopfkopie")
    copy = HeadCopy(
        "app.other",
        "app/other.py",
        line,
        "target",
        "app.mod",
        "target",
        (("app.mod", "target"),),
        "from",
    )
    assert copy in fake.head_copies()
    assert _findings_at(fake, "c", "app/other.py", "kopfkopie") == [
        "app.other.target: Kopfkopie (from) von app.mod.target"
    ]


def test_rule_d_finds_a_name_that_only_a_table_holds(fake: Index) -> None:
    """``only_listed`` steht nur im Tupel ``WAYS`` auf Modulebene — gelesen beim Import,
    nie zur Aufrufzeit, wie ``_cost_matrix`` in ``_MATCH_WAYS`` (CS-9b)."""
    assert fake.readers("app.unread", "only_listed") == ()
    assert _findings_at(fake, "d", "tests/test_red.py", "d") == [
        "app.unread.only_listed: Lesermenge leer"
    ]


def test_rule_e_finds_a_target_and_a_name_that_do_not_fold(fake: Index) -> None:
    assert _findings_at(fake, "e", "tests/test_red.py", "e-ziel") == [
        ".x: Ziel nicht auflösbar: Parameter thing ohne Aufrufstelle"
    ]
    assert _findings_at(fake, "e", "tests/test_red.py", "e-name") == [
        "app.mod.: Name nicht faltbar"
    ]


def test_w5_finds_a_missing_module_and_a_silent_store(fake: Index) -> None:
    assert _unresolved_at(fake, "tests/test_red.py", "w5-import") == {("import", "app.missing", "")}
    assert _unresolved_at(fake, "tests/test_red.py", "w5-store") == {("store", "app.mod", "ABSENT")}


def test_w5_finds_a_renamed_name_that_only_a_late_import_in_a_tool_reads(fake: Index) -> None:
    """RM-724: mypy prüft ``tools/`` nicht, und ein später Import bricht erst, wenn die
    Zeile läuft — der Auflöser sieht ihn sofort."""
    assert _unresolved_at(fake, "tools/tool.py", "spaet") == set()
    assert _unresolved_at(fake, "tools/tool.py", "spaet-umbenannt") == {
        ("from", "app.mod", "OLD_NAME")
    }


def test_mock_patch_counts_and_a_local_patch_function_does_not(fake: Index) -> None:
    assert _targets(fake, "tests/test_red.py", "mock-pfad") == {("module", "app.mod", "target")}
    assert _targets(fake, "tests/test_red.py", "mock-objekt") == {("module", "app.mod", "CONST")}
    line = _line("tests/test_red.py", "kein-patch")
    assert not [s for s in fake.patch_sites() if (s.path, s.line) == ("tests/test_red.py", line)]


def test_readers_name_every_way_a_name_is_reached(fake: Index) -> None:
    """Global in der eigenen Funktion, später Import in einem Werkzeug; das Lesen beim
    Import (``WAYS``) zählt nicht."""
    readers = {(r.module, r.qualname, r.kind) for r in fake.readers("app.mod", "CONST")}
    assert readers == {("app.mod", "reader", "global"), ("tools.tool", "late", "import")}
    assert fake.reach_dump()[("app.mod", "CONST")] == ("app.mod:reader", "tools.tool:late")


def test_resolve_answers_for_a_node_from_an_own_parse(fake: Index) -> None:
    """``resolve`` nimmt einen Knoten aus einem eigenen ``ast.parse`` und findet seinen
    Bereich über die Lage: ``module`` in ``test_alias_b`` ist ``app.other``."""
    tree = ast.parse(_source("tests/test_green.py"))
    line = _line("tests/test_green.py", "alias-b")
    node = next(
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Name) and n.id == "module" and n.lineno == line
    )
    assert fake.resolve("tests/test_green.py", node) == frozenset({Val("module", "app.other")})


def test_the_cache_gives_the_same_index_cold_and_warm(tmp_path: Path) -> None:
    """Kalt (ohne Zwischenspeicher), dann zweimal mit: Das Inventar ist dasselbe, der dritte
    Bau zieht keine Datei neu aus, und eine geänderte Datei wird neu ausgezogen."""
    root = _write(tmp_path / "baum")

    def stripped(index: Index) -> str:
        return code_index.inventory(index).rsplit("Laufzeit", 1)[0]

    cold = Index.build(root, cache=False)
    first = Index.build(root)
    warm = Index.build(root)
    assert stripped(cold) == stripped(first) == stripped(warm)
    assert (root / code_index.CACHE).is_file()
    assert warm.counts["extracted"] == 0
    assert warm.counts["cached"] == len(FAKE)
    (root / "app/unread.py").write_text(_source("app/unread.py") + "\nX = 1\n", encoding="utf-8")
    changed = Index.build(root)
    assert changed.counts["extracted"] == 1
    assert changed.exists("app.unread", "X")
    # Ein Speicher aus einem anderen Stand von ``code_facts.py`` gilt nicht: Sonst hielte ein
    # geänderter Auszug alte Ergebnisse für neue.
    cache = root / code_index.CACHE
    cache.write_bytes(
        cache.read_bytes().replace(code_index.stamp().encode("ascii"), b"alter-Stand", 1)
    )
    assert Index.build(root).counts["extracted"] == len(FAKE)


# ------------------------------------------------------------------------ echter Baum


def _real() -> Index:
    return code_index.shared()


#: Die Grundmengen aus dem Plan (``plan-cs0.md``, 2.2 und 2.5).
LEAST_PATCH_SITES = 3000
LEAST_IMPORTS = 13000


def test_the_ground_sets_of_the_real_tree_are_not_empty() -> None:
    """Mehr als 3 000 Patch-Stellen (Plan 2.2) und mehr als 13 000 Importe (Plan 2.5)."""
    index = _real()
    imports = index.import_count()
    assert len(index.patch_sites()) > LEAST_PATCH_SITES, len(index.patch_sites())
    assert imports > LEAST_IMPORTS, imports


def test_known_case_head_copy_of_detect_in_evaluate() -> None:
    """``scene/evaluate.py`` hält ``detect`` aus ``perceive.features`` als Kopfkopie, und
    ``test_bore_mouth_resize.py`` patcht das Original (Konzept, CS-11). Paket K behebt es;
    dann wird dieser Fall gestrichen, W2 c) hält es."""
    index = _real()
    copies = [
        copy
        for copy in index.head_copies()
        if copy.holder == "app.core.scene.evaluate" and copy.bound == "detect"
    ]
    assert copies, "Kopie von detect in evaluate.py fehlt: K hat CS-11 behoben, Fall streichen"
    assert ("app.core.perceive.features", "detect") in copies[0].chain
    assert ("app.core.perceive.features", "detect") in index.patched_names()
    rules = [f for f in index.patch_findings()["c"] if f.path == "app/core/scene/evaluate.py"]
    assert any(f.name == "detect" for f in rules)


def test_known_case_the_spool_ban_sits_on_the_binding_the_inventory_reads() -> None:
    """CS-9a, behoben und umgekehrt gehalten: ``test_first_run.py`` verbietet
    ``configured_spools`` an der Bindung in ``filament_inventory.py``, die das Lager zur
    Aufrufzeit liest — nicht am Original in ``filament_picker``, das dessen Kopfkopie nie
    erreicht. Solange W2 c) und d) ``xfail`` tragen, hält dieser Fall das ohne Fenster;
    sind beide scharf, wird er gestrichen."""
    index = _real()
    binding = ("app.ui.filament_inventory", "configured_spools")
    bans = [
        site
        for site in index.patch_sites()
        if site.path == "tests/test_first_run.py"
        and any(target.name == "configured_spools" for target in site.targets)
    ]
    assert bans, "kein Patch auf configured_spools in test_first_run.py"
    for site in bans:
        targets = {(target.module, target.name) for target in site.targets}
        assert targets == {binding}, f"Zeile {site.line} verbietet an {targets}"
    assert index.readers(*binding), "niemand liest filament_inventory.configured_spools"
    assert ("app.ui.filament_picker", "configured_spools") not in index.patched_names()
    found = index.patch_findings()
    named = [f for rule in "cd" for f in found[rule] if f.name == "configured_spools"]
    assert not named, named
