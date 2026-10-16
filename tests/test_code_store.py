"""Der Ergebnisspeicher des Auflösers (``tools/code_store.py``) antwortet wie ein frisch gebauter
Index und wird je Baumstand genau einmal gebaut.

**Warum es diese Datei gibt** (CS-23). W2, W5 und W6 fragen den Index in jedem Testprozess; im
Tor baute jeder Arbeiter, der eine dieser Dateien bekam, ihn selbst — rund 2 GB und eine halbe
Minute je Arbeiter, bis zu vier zugleich. Der Speicher hält nur die Antworten; ein Auszug wird
erst geladen, wenn eine Frage ihn braucht. Geprüft wird an der Attrappe aus
``test_code_index.py``:

- kalt (gebaut und geschrieben) = warm (gelesen) = frisch gebaut, für jede Abfrage;
- warm lädt keinen Auszug, bis ``resolve`` oder ``modules[…]`` einen braucht;
- ein anderer Baumstand, ein anderer Stand des Auflösers und ein beschädigter Speicher bauen neu;
- wer auf einen Bau wartet, baut nicht selbst, sondern liest; ohne Sperre baut er nach der Frist.
"""

from __future__ import annotations

import gc
import importlib
import marshal
import shutil
import subprocess
import sys
import textwrap
import threading
from collections.abc import Callable
from pathlib import Path
from typing import IO

import pytest

from tests.test_code_index import FAKE
from tools import code_cache, code_index, code_store
from tools.code_index import Index

#: Namen, die es in der Attrappe nicht gibt — ``exists`` muss auch dort gleich antworten.
ABSENT = ("FEHLT", "__path__", "__name__", "sub")

#: Die Stände beider Speicher in einer Kopie von ``tools/code_*.py`` (``argv[1]``): Ergebnisse
#: (``code_store``) und Auszüge (``code_facts``).
STAMPING = """
import sys

sys.path.insert(0, sys.argv[1])
from tools import code_facts, code_store

print(code_store.stamp(), code_facts.stamp())
"""

#: Ein Prozess, der den Auflöser lädt wie die Sammlung (``code_index``; ``code_store`` erst mit
#: dem ersten ``shared()``). Die Quelle ``argv[3]`` wechselt auf der Platte zweimal: vor dem
#: Laden von ``code_store`` (RR2-1, RR2-13; nicht für ``code_store.py`` selbst, das dann erst
#: geladen wird) und nachdem er beide Speicher für den Baum ``argv[2]`` geschrieben hat — mit
#: anderen Annotationen, die ein Leser der Platte als anderes Format verstünde (RR2-13). Danach
#: sagt er, ob der Stand der Auszüge zu den geladenen Quellen passt und ob er seine eigenen
#: Speicher noch liest.
RACING = """
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from tools import code_index

changed = Path(sys.argv[1], "tools", sys.argv[3])
if changed.name != "code_store.py":
    changed.write_text(changed.read_text(encoding="utf-8") + "\\n# Fassung B\\n", encoding="utf-8")
from tools import code_cache, code_facts, code_store

root = Path(sys.argv[2])
code_store.load(root)
text = changed.read_text(encoding="utf-8")
changed.write_text(text.replace(": str\\n", ": bytes\\n") + "\\n# Fassung C\\n", encoding="utf-8")
loaded = hashlib.sha256(code_facts._SOURCE + code_cache._SOURCE).hexdigest()
tree = code_store.tree_key(code_store.tree_digests(root))
print(
    code_facts.stamp() == loaded,
    code_store.read(root / code_store.RESULT, tree) is not None,
    len(code_cache.decode(root / code_index.CACHE, code_facts.stamp())),
)
"""


#: Zur Attrappe ein Alias von ``hasattr``, den ein anderes Modul bezieht: Den meldet der Wächter
#: CS-34, und ein gelesener Index muss ihn kennen wie ein gebauter (RR2-2).
ALIASED = {
    "app/ask.py": "has = hasattr\n",
    "tests/test_ask.py": """
        from app import mod
        from app.ask import has


        def test_ask():
            assert has(mod, "CONST")
    """,
}


def _tree(root: Path) -> Path:
    for path, source in (FAKE | ALIASED).items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(source).lstrip("\n"), encoding="utf-8")
    return root


def _answers(index: Index) -> dict[str, object]:
    """Jede Abfrage, die W2, W5, W6 und das Werkzeug stellen, über jeden Namen der Attrappe —
    auch die nur unter ``TYPE_CHECKING`` gebundenen (``Hidden`` in ``app.mod``)."""
    keys = sorted(
        {
            (module, name)
            for module, (runtime, typing, _package) in index.module_names.items()
            for name in runtime | typing
        }
        | {(module, name) for module in index.module_names for name in ABSENT}
        | index.patched_names()
    )
    assert ("app.mod", "Hidden") in keys
    return {
        "sites": index.patch_sites(),
        "heads": index.head_copies(),
        "unresolved": index.unresolved(),
        "findings": index.patch_findings(),
        "reach": index.reach_dump(),
        "patched": index.patched_names(),
        "imports": index.import_count(),
        "references": {key: index.references(*key) for key in keys},
        "readers": {key: index.readers(*key) for key in keys},
        "exists": {
            (module, name, checking): index.exists(module, name, checking=checking)
            for module, name in keys
            for checking in (False, True)
        },
        "modules": sorted(index.modules),
        "packages": sorted(index.packages),
        "module_exists": {module: index.module_exists(module) for module, _name in keys},
        "aliases": index.query_aliases(),
        "exports": {module: index.exports(module) for module in index.module_names},
    }


def _count_builds(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Jeder Bau über :meth:`Index.build` hinterlässt seine Wurzel."""
    built: list[Path] = []
    original = Index.build

    def counted(cls: type[Index], root: Path | None = None, *, cache: bool = True) -> Index:
        built.append(Path(str(root)))
        return original(root, cache=cache)

    monkeypatch.setattr(Index, "build", classmethod(counted))
    return built


def _count_loads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Jeder Auszug, den ein gespeicherter Index aus dem Zwischenspeicher lädt."""
    loaded: list[str] = []
    original = code_cache.decode_one

    def counted(path: Path, current: str, name: str, digest: str) -> object:
        loaded.append(name)
        return original(path, current, name, digest)

    monkeypatch.setattr(code_cache, "decode_one", counted)
    return loaded


def test_stored_answers_equal_a_freshly_built_index_cold_and_warm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kalt baut und schreibt der Speicher, warm liest er — beide antworten wie ein frisch
    gebauter Index, und warm braucht dafür keinen einzigen Auszug."""
    root = _tree(tmp_path / "baum")
    fresh = Index.build(root, cache=False)
    expected = _answers(fresh)
    # Die Grundmenge von W5 ohne Auszüge: dieselbe Zahl wie über jede Datei gezählt.
    assert expected["imports"] == sum(len(facts.imports) for facts in fresh.files.values())
    assert expected["aliases"] == (("app.ask", "has", "app/ask.py", 1),)
    builds = _count_builds(monkeypatch)
    loads = _count_loads(monkeypatch)
    cold = code_store.load(root)
    assert builds == [root.resolve()]
    assert (root / code_store.RESULT).is_file()
    assert _answers(cold) == expected
    warm = code_store.load(root)
    assert builds == [root.resolve()], "warm darf nicht neu bauen"
    assert _answers(warm) == expected
    assert loads == [], "eine Antwort aus dem Speicher hat einen Auszug geladen"


def test_a_stored_index_loads_an_extract_only_where_a_question_needs_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``modules[…]`` lädt genau diesen Auszug, ``resolve`` faltet wie der frische Index, und
    das Inventar über alle Dateien stimmt mit dem frischen überein."""
    root = _tree(tmp_path / "baum")
    fresh = Index.build(root, cache=False)
    code_store.load(root)
    loads = _count_loads(monkeypatch)
    stored = code_store.load(root)
    assert stored.modules["app.pkg"].exports == fresh.modules["app.pkg"].exports
    assert loads == ["app/pkg/__init__.py"]
    source = (root / "tests/test_green.py").read_text(encoding="utf-8")
    import ast

    names = [node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Name)]
    assert names
    for node in names:
        assert stored.resolve("tests/test_green.py", node) == fresh.resolve(
            "tests/test_green.py", node
        )

    def strip(index: Index) -> str:
        return code_index.inventory(index).rsplit("Laufzeit", 1)[0]

    assert strip(stored) == strip(fresh)


def test_without_the_extract_cache_a_stored_index_reads_the_source_if_unchanged(
    tmp_path: Path,
) -> None:
    root = _tree(tmp_path / "baum")
    code_store.load(root)
    (root / code_index.CACHE).unlink()
    stored = code_store.load(root)
    assert "lazy_fn" in stored.modules["app.pkg"].exports
    (root / "app/mod.py").write_text("CONST = 2\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="neu starten"):
        stored.modules["app.mod"]


def test_a_stored_index_answers_lazy_exports_without_an_extract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RR2-9: W6 e) fragt die Lazy-Exporte eines Pakets. Hat ein anderer Prozess inzwischen für
    einen neuen Stand gebaut, fehlt der alte Auszug, und die Quelle ist eine andere — der
    gelesene Index antwortet trotzdem aus dem Speicher, wie der gebaute."""
    root = _tree(tmp_path / "baum")
    fresh = Index.build(root, cache=False)
    assert fresh.exports("app.pkg")
    code_store.load(root)
    loads = _count_loads(monkeypatch)
    stored = code_store.load(root)
    (root / code_index.CACHE).unlink()
    init = root / "app/pkg/__init__.py"
    init.write_text(init.read_text(encoding="utf-8") + "\nX = 1\n", encoding="utf-8")
    assert stored.exports("app.pkg") == fresh.exports("app.pkg")
    assert stored.exports("app.mod") == fresh.exports("app.mod") == {}
    assert loads == [], "die Exporte haben einen Auszug geladen"


def test_a_waiting_process_reads_what_the_builder_built_for_the_new_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RR2-9: Ändert sich eine Datei, während ein anderer Prozess baut, rechnet der Wartende den
    Baumstand nach dem Erwerb der Sperre neu und liest, was der Bauer für ihn schrieb — sonst
    baute jeder Wartende nacheinander selbst."""
    root = _tree(tmp_path / "baum")
    refused = _watch_the_lock(monkeypatch)
    builds = _count_builds(monkeypatch)
    found: dict[str, Index] = {}
    with code_store.exclusive(root / code_store.LOCK, 5.0) as locked:
        assert locked
        waiting = threading.Thread(target=lambda: found.update(index=code_store.load(root)))
        waiting.start()
        assert refused.wait(60), "der zweite Bewerber kam nie an die Sperre"
        unread = root / "app/unread.py"
        unread.write_text(unread.read_text(encoding="utf-8") + "\nX = 1\n", encoding="utf-8")
        code_store.write(root / code_store.RESULT, code_store.snapshot(Index.build(root)))
    waiting.join(60)
    assert not waiting.is_alive()
    assert len(builds) == 1, "der Wartende hat selbst gebaut"
    assert found["index"].exists("app.unread", "X")


def test_a_changed_tree_or_resolver_builds_anew(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path / "baum")
    code_store.load(root)
    builds = _count_builds(monkeypatch)
    code_store.load(root)
    assert builds == []
    unread = root / "app/unread.py"
    unread.write_text(unread.read_text(encoding="utf-8") + "\nX = 1\n", encoding="utf-8")
    changed = code_store.load(root)
    assert len(builds) == 1
    assert changed.exists("app.unread", "X")
    monkeypatch.setattr(code_store, "_STAMP", "anderer-Stand")
    code_store.load(root)
    assert len(builds) == 2


def _resolver_copy(target: Path) -> Path:
    """Eine Kopie von ``tools/code_*.py``; der Auflöser braucht außer ihnen nur die Bibliothek."""
    (target / "tools").mkdir(parents=True)
    for source in sorted((code_index.ROOT / "tools").glob("code_*.py")):
        shutil.copyfile(source, target / "tools" / source.name)
    return target


def _run(copy: Path, script: str, *args: str) -> str:
    done = subprocess.run(
        [sys.executable, "-I", "-c", script, str(copy), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=300,
        cwd=copy,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _stamp_of(copy: Path) -> tuple[str, str]:
    """Die Stände von Ergebnis- und Zwischenspeicher, die ein frischer Prozess mit dieser Kopie
    rechnet."""
    store, facts = _run(copy, STAMPING).split()
    return store, facts


@pytest.mark.parametrize("source", sorted(code_store.SOURCES))
def test_a_process_writes_under_the_stamp_of_the_code_it_loaded(
    tmp_path: Path, source: str
) -> None:
    """RR2-1, RR2-13: Wechselt eine Quelle des Auflösers auf der Platte, nachdem ein Prozess
    ihn geladen hat, rechnet er mit dem alten Code und muss unter dessen Stand schreiben —
    beide Speicher. Unter dem neuen gälten seine Antworten für jeden späteren Prozess mit dem
    neuen Code, bis sich der Baum ändert. Und er liest weiter, was er selbst schrieb: Ein Leser
    der Platte verwürfe es oder deutete es nach einem anderen Format."""
    copy = _resolver_copy(tmp_path / "werkzeug")
    root = _tree(tmp_path / "baum")
    loaded = _stamp_of(copy)
    answer = _run(copy, RACING, str(root), source)
    assert _stamp_of(copy)[0] != loaded[0], "die geänderte Quelle muss den Stand ändern"
    for path, magic, stamp in (
        (code_store.RESULT, code_store.MAGIC, loaded[0]),
        (code_index.CACHE, code_cache.MAGIC, loaded[1]),
    ):
        header = (root / path).read_bytes().split(b"\n", 2)
        assert header[0] + b"\n" == magic
        assert header[1].decode("ascii") == stamp, f"{path.name} unter dem Stand der Platte"
    files = len(code_store.tree_digests(root))
    assert answer == f"True True {files}", (
        "Stand der Auszüge passt zu den geladenen Quellen, Ergebnisse und Auszüge lesbar",
        answer,
    )


def test_the_stamp_covers_every_source_of_the_resolver() -> None:
    """Jede Datei, die rechnet, geht mit der beim Import gelesenen Quelle in den Stand ein —
    jeder Eintrag ist ``_SOURCE`` seines Moduls, nicht eine eigene Lesung der Platte, die beim
    Import von ``code_store`` schon eine andere sein kann (RR2-12)."""
    on_disk = sorted(path.name for path in (code_index.ROOT / "tools").glob("code_*.py"))
    assert sorted(code_store.SOURCES) == on_disk
    for name, source in code_store.SOURCES.items():
        module = importlib.import_module(f"tools.{name.removesuffix('.py')}")
        assert source is module._SOURCE, f"{name}: nicht die Quelle, die das Modul geladen hat"


def _damaged(root: Path, how: str) -> bytes:
    """Der gültige Speicher der Attrappe, an einer Stelle beschädigt."""
    data = (root / code_store.RESULT).read_bytes()
    tree = code_store.tree_key(code_store.tree_digests(root))
    header = code_store.MAGIC + code_store.stamp().encode() + b"\n" + tree.encode() + b"\n"
    assert data.startswith(header)
    if how == "abgeschnitten":
        return data[: len(header) + 40]
    if how == "Codeobjekt":
        return header + marshal.dumps((lambda: None).__code__)
    if how == "Feldtyp":
        # Ein PatchSite mit einer Zahl als Pfad: Die Feldprüfung muss ihn abweisen.
        stored = code_store.read(root / code_store.RESULT, tree)
        assert stored is not None and stored.results.sites
        site = stored.results.sites[0]._replace(path=1)
        results = stored.results._replace(sites=(site, *stored.results.sites[1:]))
        return header + code_cache.dumps(stored._replace(results=results))
    if how == "anderer Baum":
        stored = code_store.read(root / code_store.RESULT, tree)
        assert stored is not None
        return header + code_cache.dumps(stored._replace(tree="0" * 64))
    raise AssertionError(how)


@pytest.mark.parametrize("how", ["abgeschnitten", "Codeobjekt", "Feldtyp", "anderer Baum"])
def test_a_damaged_store_is_built_anew_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str
) -> None:
    root = _tree(tmp_path / "baum")
    expected = _answers(code_store.load(root))
    (root / code_store.RESULT).write_bytes(_damaged(root, how))
    tree = code_store.tree_key(code_store.tree_digests(root))
    assert code_store.read(root / code_store.RESULT, tree) is None
    builds = _count_builds(monkeypatch)
    assert _answers(code_store.load(root)) == expected
    assert len(builds) == 1


def test_an_undamaged_store_reads_back(tmp_path: Path) -> None:
    """Gegenprobe zu den Schäden: Ohne Schaden liest derselbe Weg den Speicher."""
    root = _tree(tmp_path / "baum")
    code_store.load(root)
    tree = code_store.tree_key(code_store.tree_digests(root))
    assert code_store.read(root / code_store.RESULT, tree) is not None


def _watch_the_lock(monkeypatch: pytest.MonkeyPatch) -> threading.Event:
    """Gesetzt, sobald ein Bewerber an der gehaltenen Sperre abgewiesen wird."""
    refused = threading.Event()
    original: Callable[[IO[bytes]], None] = code_store._try_lock

    def watched(handle: IO[bytes]) -> None:
        try:
            original(handle)
        except OSError:
            refused.set()
            raise

    monkeypatch.setattr(code_store, "_try_lock", watched)
    return refused


def test_a_second_process_waits_for_the_builder_and_reads_its_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Index je Baumstand: Wer an der Sperre wartet, liest danach, was der Halter schrieb,
    statt selbst zu bauen."""
    root = _tree(tmp_path / "baum")
    built = Index.build(root, cache=False)
    expected = _answers(built)
    refused = _watch_the_lock(monkeypatch)
    builds = _count_builds(monkeypatch)
    found: dict[str, Index] = {}
    with code_store.exclusive(root / code_store.LOCK, 5.0) as locked:
        assert locked
        waiting = threading.Thread(target=lambda: found.update(index=code_store.load(root)))
        waiting.start()
        assert refused.wait(60), "der zweite Bewerber kam nie an die Sperre"
        code_store.write(root / code_store.RESULT, code_store.snapshot(built))
    waiting.join(60)
    assert not waiting.is_alive()
    assert builds == [], "der Wartende hat selbst gebaut"
    assert _answers(found["index"]) == expected


def test_after_its_deadline_a_waiting_process_builds_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path / "baum")
    expected = _answers(Index.build(root, cache=False))
    monkeypatch.setattr(code_store, "WAIT_SECONDS", 0.5)
    refused = _watch_the_lock(monkeypatch)
    builds = _count_builds(monkeypatch)
    with code_store.exclusive(root / code_store.LOCK, 5.0) as locked:
        assert locked
        index = code_store.load(root)
    assert refused.is_set()
    assert len(builds) == 1
    assert _answers(index) == expected


def test_shared_leaves_the_collector_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """RR2-11: ``shared()`` lädt den Index und lässt den Sammler, wie er ist — kein
    ``gc.freeze()``, das ein 3MF-Import ohnehin wieder auftaute und das bis dahin
    ``gc.get_objects()`` blind machte für alles, was vorher lebte."""
    calls: list[str] = []
    marker = object()
    monkeypatch.setattr(code_store, "load", lambda root: calls.append("load") or marker)
    monkeypatch.setattr(gc, "collect", lambda *args: calls.append("collect") or 0)
    monkeypatch.setattr(gc, "freeze", lambda: calls.append("freeze"))
    assert code_index.shared.__wrapped__() is marker
    assert calls == ["load"]
