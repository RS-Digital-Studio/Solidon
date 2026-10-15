"""``hasattr(M, "N")`` und ``getattr(M, "N", vorgabe)`` sind Bezüge auf ``M.N`` (CS-27).

**Warum es diese Datei gibt.** Der Auflöser (``tools/code_index.py``) zählte ``hasattr`` nicht
als Bezug: Ein Schnitt, der ``N`` aus ``M`` verschiebt, ließe ``hasattr(M, "N")`` danach still
``False`` antworten, das Verschiebewerkzeug schriebe es nicht um, und W2 d) hielte einen Namen,
den nur ein ``hasattr`` liest, für ungelesen. Auch unter anderem Namen (``has = hasattr``,
``from builtins import hasattr as has``, ``builtins.hasattr``) ist es dieselbe Frage. Fragt der
Code nach einem Namen, den es nicht gibt, ist das weiter kein Fund (W5).

Einen Alias aus einem **anderen** Modul (``from tests.helfer import has``) erkennt der Auszug
nicht als Abfrage; im Baum gibt es keinen, und ein Wächter hält das fest (CS-34).
"""

from __future__ import annotations

from pathlib import Path

from tests.code_index_helpers import build_index, stored_index
from tools import code_store
from tools.code_index import Index, shared

PATCH = """
from app import mod


def test_patch(monkeypatch):
    monkeypatch.setattr(mod, "FLAG", False)
"""


def _queries(body: str) -> Index:
    """Eine Attrappe: ``app.mod.FLAG``, das nur ``app/user.py`` mit ``body`` erfragt und ein
    Test patcht."""
    return build_index(
        {
            "app/mod.py": "FLAG = True\ndef target():\n    return 1\n",
            "app/user.py": "import builtins\nfrom app import mod\n\n" + body,
            "tests/test_flag.py": PATCH,
        }
    )


def _kinds(index: Index, name: str = "FLAG") -> set[tuple[str, str, int]]:
    """Die Bezüge aus app/user.py; der Patch im Test ist selbst einer (patch)."""
    return {
        (r.kind, r.path, r.line)
        for r in index.references("app.mod", name)
        if r.path == "app/user.py"
    }


def test_hasattr_is_a_reference_and_reads_the_name() -> None:
    index = _queries("def probe():\n    return hasattr(mod, 'FLAG')\n")
    assert ("hasattr", "app/user.py", 5) in _kinds(index)
    readers = {(r.module, r.qualname, r.kind) for r in index.readers("app.mod", "FLAG")}
    assert readers == {("app.user", "probe", "hasattr")}
    # W2 d): Ein Name, den nur ein ``hasattr`` liest, hat Leser; der Patch erreicht sie.
    assert not [f for f in index.patch_findings()["d"] if f.name == "FLAG"]


def test_without_a_query_the_patched_name_has_no_reader() -> None:
    """Gegenprobe zu oben: Dieselbe Attrappe ohne ``hasattr`` ist ein d)-Fund."""
    index = _queries("def probe():\n    return mod.target()\n")
    assert [f.name for f in index.patch_findings()["d"]] == ["FLAG"]


def test_a_name_that_only_shadows_the_builtin_is_no_query() -> None:
    """RR2-6: ``def probe(hasattr)`` ruft, was der Aufrufer übergibt, ``getattr = lambda …`` den
    eigenen Wert — keine Abfrage: kein Bezug, kein Leser, kein W5-Fund, und der gepatchte Name,
    den sonst niemand liest, bleibt ein d)-Fund. Gegenprobe ist der erste Fall dieser Datei mit
    dem eingebauten ``hasattr``."""
    index = _queries(
        "def probe(hasattr):\n    return hasattr(mod, 'FLAG')\n\n"
        "def local():\n"
        "    getattr = lambda module, name: None\n"
        "    return getattr(mod, 'MISSING')\n"
    )
    assert not _kinds(index)
    assert not index.readers("app.mod", "FLAG")
    assert not index.unresolved()
    assert [f.name for f in index.patch_findings()["d"]] == ["FLAG"]


def test_getattr_with_a_default_is_a_reference_and_reads_the_name() -> None:
    index = _queries("def fallback():\n    return getattr(mod, 'FLAG', None)\n")
    assert ("getattr", "app/user.py", 5) in _kinds(index)
    readers = {(r.qualname, r.kind) for r in index.readers("app.mod", "FLAG")}
    assert readers == {("fallback", "getattr")}


def test_a_query_for_a_missing_name_is_no_reference_and_no_finding() -> None:
    index = _queries(
        "def absent():\n    return hasattr(mod, 'MISSING') or getattr(mod, 'MISSING', None)\n"
    )
    assert not index.references("app.mod", "MISSING")
    assert not [u for u in index.unresolved() if u.name == "MISSING"]
    assert index.counts["absent.hasattr"] == 1
    assert index.counts["absent.getattr-default"] == 1


def test_an_alias_of_hasattr_or_getattr_asks_the_same_question() -> None:
    index = _queries(
        "has = hasattr\n"
        "from builtins import getattr as look\n\n"
        "def by_name():\n    return has(mod, 'FLAG')\n\n"
        "def by_builtins():\n    return builtins.hasattr(mod, 'FLAG')\n\n"
        "def with_default():\n    return look(mod, 'FLAG', None)\n\n"
        "def without_default():\n    return look(mod, 'MISSING')\n"
    )
    readers = {(r.qualname, r.kind) for r in index.readers("app.mod", "FLAG")}
    assert readers == {
        ("by_name", "hasattr"),
        ("by_builtins", "hasattr"),
        ("with_default", "getattr"),
    }
    assert {kind for kind, _path, _line in _kinds(index)} == {"hasattr", "getattr"}
    # ``getattr`` ohne Vorgabe auch unter anderem Namen: W5 meldet den fehlenden Namen.
    assert [(u.kind, u.name) for u in index.unresolved()] == [("getattr", "MISSING")]


def test_a_function_that_only_shares_the_name_is_no_query() -> None:
    """``has`` ist hier eine eigene Funktion, ``builtins`` ein eigenes Objekt — kein Bezug."""
    index = _queries(
        "def has(module, name):\n    return False\n\n"
        "class builtins:\n    hasattr = staticmethod(has)\n\n"
        "def probe():\n    return has(mod, 'FLAG') or builtins.hasattr(mod, 'FLAG')\n"
    )
    assert not _kinds(index)
    assert not index.readers("app.mod", "FLAG")


def test_no_module_draws_an_alias_of_getattr_or_hasattr_from_another_one() -> None:
    """CS-34, Wächter am echten Baum: Bezieht ein Modul ``has = hasattr`` aus einem anderen,
    sind seine Aufrufe für den Auflöser keine Abfrage — kein Bezug, kein Leser, nach einem
    Schnitt still ``False``. Statt die Auflösung dafür zu bauen, gibt es die Form im Baum nicht;
    taucht sie auf, ist hier die Stelle. Ausweg: ``hasattr``/``getattr`` selbst schreiben oder
    den Alias in der Datei binden, die ihn ruft."""
    found = shared().query_aliases()
    assert not found, "\n".join(
        f"{path}:{line}: {module}.{name} ist ein Alias von getattr/hasattr, den ein anderes "
        "Modul bezieht"
        for module, name, path, line in found
    )


def test_an_alias_drawn_from_another_module_is_found(tmp_path: Path) -> None:
    """Gegenprobe zum Wächter: über ``from … import`` und über das Modul als Attribut; ein
    Alias, den nur seine eigene Datei ruft, und einer, den niemand bezieht, sind kein Fund.
    Über denselben Weg wie der Wächter: gebaut, gespeichert und gelesen (RR2-2)."""
    index = stored_index(
        tmp_path,
        {
            "tests/query_alias.py": "has = hasattr\nlook = getattr\nunused = hasattr\n"
            "mine = hasattr\n\n\n"
            "def own(module):\n"
            "    import tests.query_alias as me\n\n"
            "    return me.mine(module, 'target')\n",
            "tests/test_user.py": "import tests.query_alias as aliases\n"
            "from app import mod\n"
            "from tests.query_alias import has\n\n\n"
            "def test_queries():\n"
            "    assert has(mod, 'target')\n"
            "    assert aliases.look(mod, 'target', None)\n",
            "app/own.py": "from builtins import hasattr as ask\n\n\n"
            "def probe(module):\n    return ask(module, 'target')\n",
        },
    )
    expected = (
        ("tests.query_alias", "has", "tests/query_alias.py", 1),
        ("tests.query_alias", "look", "tests/query_alias.py", 2),
    )
    assert index.query_aliases() == expected
    assert code_store.load(tmp_path).query_aliases() == expected, "warm gelesen"
