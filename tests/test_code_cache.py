"""Beschädigte Auszüge bleiben Ableitungen und werden vollständig aus der Quelle erneuert."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import marshal
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from tests.code_index_helpers import stored_index
from tools import code_cache, code_facts, code_store
from tools.code_index import CACHE, Index

SOURCE = b"""from app import mod
VALUE = [mod.target]
def read(item=mod.target):
    return mod.target
def test_patch(monkeypatch):
    monkeypatch.setattr(mod, 'target', None)
    read(mod.target)
"""


def _stored() -> dict[str, tuple[str, code_facts.Facts]]:
    facts = code_facts.extract("tests/test_case.py", SOURCE)
    return {facts.path: (hashlib.sha256(SOURCE).hexdigest(), facts)}


def _damage(value: object, record: str, field: str, replacement: object) -> tuple[object, int]:
    """Ändert ein Feld in allen passenden Drahtrecords, ohne das Marshal-Format zu brechen."""
    if not isinstance(value, tuple):
        return value, 0
    if len(value) == 2 and value[0] == record:
        cls = getattr(code_facts, record)
        fields = (
            tuple(item.name for item in dataclasses.fields(cls))
            if dataclasses.is_dataclass(cls)
            else cls._fields
        )
        items = list(value[1])
        items[fields.index(field)] = code_cache._pack(replacement)
        return (record, tuple(items)), 1
    children = [_damage(item, record, field, replacement) for item in value]
    return tuple(item for item, _count in children), sum(count for _item, count in children)


def _records(packed: object) -> list[tuple[str, str, bytes]]:
    """Eine gepackte Tafel ``pfad → (hash, auszug)`` wird je Datei ein Datensatz; jede andere
    Form steht als einziger Datensatz von ``tests/test_case.py`` im Rahmen."""
    if (
        isinstance(packed, tuple)
        and len(packed) == 2
        and packed[0] == 2
        and isinstance(packed[1], tuple)
        and all(
            isinstance(pair, tuple)
            and len(pair) == 2
            and isinstance(pair[0], str)
            and isinstance(pair[1], tuple)
            and len(pair[1]) == 2
            and pair[1][0] == 0
            and len(pair[1][1]) == 2
            for pair in packed[1]
        )
    ):
        return [
            (name, digest, marshal.dumps(facts, allow_code=False))
            for name, (_tag, (digest, facts)) in packed[1]
        ]
    record = marshal.dumps(cast(code_cache.Packed, packed), allow_code=False)
    return [("tests/test_case.py", "hash", record)]


def _write(path: Path, packed: object) -> None:
    """Schreibt ``packed`` im Rahmen des Speichers, damit jeder Datensatz die Prüfung je Feld
    erreicht (ungeschädigt dekodiert er: ``test_an_undamaged_frame_decodes``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(code_cache.frame(code_facts.stamp(), _records(packed)))


@pytest.mark.parametrize(
    "record, field, replacement",
    [
        ("Facts", "scopes", None),
        ("Facts", "scopes", [None]),
        ("Facts", "scopes", []),
        ("Facts", "package", 1),
        ("Facts", "lines", True),
        ("Facts", "functions", {"read": None}),
        ("Facts", "refs", [()]),
        ("Facts", "global_reads", {"read": [("mod", "wrong")]}),
        ("Facts", "import_reads", {1: 2}),
        ("Facts", "exports", {"name": ("app.mod",)}),
        ("Facts", "comprehensions", {(1, "wrong"): 0}),
        ("Facts", "contexts", {(1, 0): (0, None)}),
        ("Facts", "comprehensions", {(1, 0): -1}),
        ("Facts", "comprehensions", {(1, 0): 99}),
        ("Facts", "contexts", {(1, 0): (-1, False)}),
        ("Facts", "contexts", {(1, 0): (99, False)}),
        ("Facts", "reloads", [(0, 1, 2, None, None)]),
        ("Facts", "reloads", [(-1, 1, 2, code_facts.const(None), code_facts.const(None))]),
        ("Facts", "reloads", [(99, 1, 2, code_facts.const(None), code_facts.const(None))]),
        ("Facts", "resets", [(-1, 1, 2)]),
        ("Facts", "resets", [(99, 1, 2)]),
        ("Scope", "parent", -2),
        ("Scope", "parent", 0),
        ("Scope", "parent", 99),
        ("Scope", "kind", "function"),
        ("Scope", "span", (1, 0, 3)),
        ("Scope", "hole", (1, 0, 3, "wrong")),
        ("Scope", "binds", {"name": [None]}),
        ("Scope", "globals", {1}),
        ("Scope", "loads", {"name": "wrong"}),
        ("Scope", "regions", [("branch", 0, (1, 0, 3, 0), [None])]),
        ("Scope", "loops", [(1, 0, 3, None)]),
        ("Scope", "uncertain", [(1, 0, 3)]),
        ("Scope", "exits", [(1, 0, (1, "wrong", 3, 0))]),
        ("Fn", "defaults", {"item": None}),
        ("Fn", "parametrize", [("item", code_facts.const(1))]),
        ("Fn", "returns", [None]),
        ("Ref", "attrs", (None,)),
        ("Ref", "scope", -1),
        ("Ref", "scope", 99),
        ("Imp", "checking", 0),
        ("Imp", "scope", -1),
        ("Imp", "scope", 99),
        ("Patch", "keywords", (("name", None),)),
        ("Patch", "until", (1,)),
        ("Patch", "scope", -1),
        ("Patch", "scope", 99),
        ("Site", "args", (None,)),
        ("Bind", "flags", "wrong"),
        ("Bind", "branch", (("branch", "wrong"),)),
        ("Seq", "items", [code_facts.const(1)]),
        ("Seq", "unordered", 0),
        ("Attr", "base", None),
        ("Use", "scope", "wrong"),
        ("Use", "scope", -1),
        ("Use", "scope", 99),
        ("Const", "tag", None),
    ],
)
def test_invalid_record_field_is_rebuilt_from_source(
    tmp_path: Path, record: str, field: str, replacement: object
) -> None:
    source = tmp_path / "tests/test_case.py"
    source.parent.mkdir()
    source.write_bytes(SOURCE)
    packed, changed = _damage(code_cache._pack(_stored()), record, field, replacement)
    assert changed, f"Kein {record}.{field} im Ausgangsdatensatz"
    cache = tmp_path / CACHE
    _write(cache, packed)
    assert code_cache.decode(cache, code_facts.stamp()) == {}

    rebuilt = Index.build(tmp_path)
    assert rebuilt.counts["extracted"] == 1
    assert rebuilt.counts["cached"] == 0
    assert rebuilt.exists("tests.test_case", "VALUE")
    warm = Index.build(tmp_path)
    assert warm.counts["extracted"] == 0
    assert warm.counts["cached"] == 1
    assert warm.files == rebuilt.files


@pytest.mark.parametrize("where", ["record", "nested", "directory"])
def test_current_cache_rejects_code_objects(tmp_path: Path, where: str) -> None:
    source = tmp_path / "tests/test_case.py"
    source.parent.mkdir()
    source.write_bytes(SOURCE)
    cache = tmp_path / CACHE
    cache.parent.mkdir(parents=True)
    code = (lambda: None).__code__
    # Der Inhaltshash der Quelle: Sonst übersprünge der Bau den Datensatz, ohne ihn zu lesen.
    digest = hashlib.sha256(SOURCE).hexdigest()
    if where == "directory":
        header = code_cache.MAGIC + code_facts.stamp().encode("ascii") + b"\n"
        directory = marshal.dumps((("tests/test_case.py", digest, 0, 0), code))
        data = header + len(directory).to_bytes(8, "little") + directory
    else:
        record = marshal.dumps((0, (code,)) if where == "nested" else code)
        data = code_cache.frame(code_facts.stamp(), [("tests/test_case.py", digest, record)])
    cache.write_bytes(data)
    assert code_cache.decode(cache, code_facts.stamp()) == {}
    assert code_cache.decode_one(cache, code_facts.stamp(), "tests/test_case.py", digest) is None
    rebuilt = Index.build(tmp_path)
    assert rebuilt.counts["extracted"] == 1
    assert rebuilt.counts["cached"] == 0
    assert rebuilt.exists("tests.test_case", "VALUE")


def test_an_undamaged_frame_decodes(tmp_path: Path) -> None:
    """Gegenprobe zu den Schäden: Derselbe Weg ohne Schaden liefert den Auszug — sonst wiese
    der Rahmen alles ab, und jede Schadensprobe wäre grün, ohne ein Feld zu prüfen."""
    cache = tmp_path / "cache.data"
    files = _stored()
    _write(cache, code_cache._pack(files))
    assert code_cache.decode(cache, code_facts.stamp()) == files
    name, (digest, facts) = next(iter(files.items()))
    assert code_cache.decode_one(cache, code_facts.stamp(), name, digest) == facts


def test_one_record_is_read_without_the_others(tmp_path: Path) -> None:
    """Ein Datensatz je Datei: ``decode_one`` liest nur den einen, ``wanted`` nur die
    passenden; ein anderer Inhaltshash oder Pfad ist kein Treffer."""
    files = _stored()
    other = code_facts.extract("app/mod.py", b"VALUE = 1\n")
    files[other.path] = "anderer", other
    cache = tmp_path / "cache.data"
    current = code_facts.stamp()
    cache.write_bytes(code_cache.encode(current, files))
    assert code_cache.decode_one(cache, current, "app/mod.py", "anderer") == other
    assert code_cache.decode_one(cache, current, "app/mod.py", "geändert") is None
    assert code_cache.decode_one(cache, current, "app/fehlt.py", "anderer") is None
    wanted = {"app/mod.py": "anderer"}
    assert code_cache.decode(cache, current, wanted) == {"app/mod.py": ("anderer", other)}
    assert code_cache.decode(cache, current, {"app/mod.py": "geändert"}) == {}
    # Ein Datensatz, der eine andere Datei beschreibt, als sein Verzeichniseintrag sagt.
    swapped = code_cache.frame(current, [("tests/test_case.py", "hash", code_cache.dumps(other))])
    cache.write_bytes(swapped)
    assert code_cache.decode(cache, current) == {}
    assert code_cache.decode_one(cache, current, "tests/test_case.py", "hash") is None


@pytest.mark.parametrize(
    "entry",
    [
        ("tests/test_case.py", "hash", 0, 10**9),
        ("tests/test_case.py", "hash", -1, 1),
        ("tests/test_case.py", 1, 0, 1),
        ("tests/test_case.py", "hash", 0),
    ],
)
def test_a_damaged_directory_is_a_cache_miss(tmp_path: Path, entry: tuple[object, ...]) -> None:
    header = code_cache.MAGIC + code_facts.stamp().encode("ascii") + b"\n"
    directory = marshal.dumps((entry,))
    cache = tmp_path / "cache.data"
    cache.write_bytes(header + len(directory).to_bytes(8, "little") + directory + b"\0")
    assert code_cache.decode(cache, code_facts.stamp()) == {}
    assert code_cache.decode_one(cache, code_facts.stamp(), "tests/test_case.py", "hash") is None


@pytest.mark.parametrize("size", [2**40, 2**62, 2**64 - 1, "eins zu viel"])
def test_a_directory_length_past_the_end_is_a_cache_miss(tmp_path: Path, size: int | str) -> None:
    """RR2-5: Eine beschädigte Längenangabe des Verzeichnisses ist ein Fehlschlag in beiden
    Wegen, kein ``MemoryError`` oder ``OverflowError`` beim Lesen. Gegenprobe: dieselbe Datei
    mit ihrer richtigen Länge liest."""
    files = _stored()
    name, (digest, facts) = next(iter(files.items()))
    current = code_facts.stamp()
    data = code_cache.encode(current, files)
    start = len(code_cache.MAGIC + current.encode("ascii") + b"\n")
    right = int.from_bytes(data[start : start + 8], "little")
    cache = tmp_path / "cache.data"
    cache.write_bytes(data)
    assert code_cache.decode_one(cache, current, name, digest) == facts
    wrong = len(data) - start - 8 + 1 if size == "eins zu viel" else size
    assert isinstance(wrong, int) and wrong != right
    cache.write_bytes(data[:start] + wrong.to_bytes(8, "little") + data[start + 8 :])
    assert code_cache.decode(cache, current) == {}
    assert code_cache.decode_one(cache, current, name, digest) is None


#: Ein Prozess unter einer Speichergrenze von 512 MB liest einen Zwischenspeicher (zwei
#: Auszüge) und einen Ergebnisspeicher, deren erster Datensatz mit einer Liste von 2^30
#: Elementen beginnt — fünf Bytes geändert, alle Längen stimmen. ``marshal`` fordert dafür 8 GB
#: an, bevor es an das Ende der Daten stößt; die Grenze lässt die Anforderung scheitern, ohne
#: den Rechner zu belasten. ``argv[1]``: der Baum mit ``tools``, ``argv[2]``: Arbeitsordner.
DAMAGED_COUNT = """
import ctypes
import marshal
import sys
from pathlib import Path

LIMIT = 512 * 1024 * 1024
if sys.platform == "win32":
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_int64),
            ("job_time", ctypes.c_int64),
            ("flags", wintypes.DWORD),
            ("minimum_set", ctypes.c_size_t),
            ("maximum_set", ctypes.c_size_t),
            ("processes", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("basic", Basic),
            ("io", ctypes.c_uint64 * 6),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD
    ]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    limit = Extended()
    limit.basic.flags = 0x100  # JOB_OBJECT_LIMIT_PROCESS_MEMORY
    limit.process_memory = LIMIT
    assert kernel32.SetInformationJobObject(job, 9, ctypes.byref(limit), ctypes.sizeof(limit))
    assert kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess())
else:
    import resource

    hard = resource.getrlimit(resource.RLIMIT_AS)[1]
    soft = LIMIT if hard == resource.RLIM_INFINITY else min(LIMIT, hard)
    resource.setrlimit(resource.RLIMIT_AS, (soft, hard))

sys.path.insert(0, sys.argv[1])
from tools import code_cache, code_facts, code_store

count = b"[" + (2**30).to_bytes(4, "little")
try:
    marshal.loads(count + bytes(16))
except MemoryError:
    print("Grenze greift")
work = Path(sys.argv[2])
current = code_facts.stamp()
files = {
    path: (path, code_facts.extract(path, source))
    for path, source in (("app/a.py", b"X = 1\\n"), ("app/b.py", b"Y = 2\\n"))
}
data = code_cache.encode(current, files)
start = len(code_cache.MAGIC + current.encode("ascii") + b"\\n") + 8
base = start + int.from_bytes(data[start - 8 : start], "little")
cache = work / "code_index.data"
cache.write_bytes(data[:base] + count + data[base + len(count) :])
tree = "0" * 64
store = work / "code_index.result"
head = code_store.MAGIC + code_store.stamp().encode("ascii") + b"\\n" + tree.encode() + b"\\n"
store.write_bytes(head + count + bytes(16))
print(
    code_cache.decode(cache, current),
    code_cache.decode_one(cache, current, "app/a.py", "app/a.py"),
    code_store.read(store, tree),
)
"""


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="macOS setzt keine Speichergrenze je Prozess durch; ohne sie belegte der Fall 8 GB",
)
def test_a_damaged_count_in_a_record_is_a_miss_not_a_memory_error(tmp_path: Path) -> None:
    """RR2-14: Ein beschädigter Zähler in einem Datensatz ist ein Fehlschlag wie jeder andere
    Schaden — für beide Wege des Zwischenspeichers und den Ergebnisspeicher —, kein
    ``MemoryError``, der den Lauf abbricht. RR2-5 prüfte nur die Länge des Verzeichnisses."""
    tree = Path(code_cache.__file__).parents[1]
    done = subprocess.run(
        [sys.executable, "-I", "-c", DAMAGED_COUNT, str(tree), str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=120,
        cwd=tmp_path,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == ["Grenze greift", "{} None None"]


@pytest.mark.parametrize("error", [MemoryError, OverflowError])
def test_a_record_beyond_memory_or_range_is_a_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    """RR2-14 auf jeder Plattform: Wirft das Lesen eines Datensatzes ``MemoryError`` (ein Zähler)
    oder ``OverflowError`` (eine Länge), ist das ein Fehlschlag — in ``decode``, ``decode_one``
    und im Ergebnisspeicher. Gegenprobe: vorher liest derselbe Speicher."""
    files = _stored()
    ((name, (digest, _facts)),) = files.items()
    current = code_facts.stamp()
    cache = tmp_path / "cache.data"
    cache.write_bytes(code_cache.encode(current, files))
    assert code_cache.decode_one(cache, current, name, digest) is not None
    tree = "0" * 64
    store = tmp_path / "code_index.result"
    head = code_store.MAGIC + code_store.stamp().encode("ascii") + b"\n" + tree.encode() + b"\n"
    store.write_bytes(head + code_cache.dumps(None))

    def beyond(*_args: object) -> object:
        raise error

    monkeypatch.setattr(code_cache, "_record", beyond)
    monkeypatch.setattr(code_cache, "loads", beyond)
    assert code_cache.decode(cache, current) == {}
    assert code_cache.decode_one(cache, current, name, digest) is None
    assert code_store.read(store, tree) is None


def test_roundtrip_preserves_typed_constants_and_reads_fresh_bytes(tmp_path: Path) -> None:
    cache = tmp_path / "cache.data"
    files = _stored()
    facts = next(iter(files.values()))[1]
    facts.scopes[0].binds["constants"] = [
        code_facts.Bind(1, 0, code_facts.const(value), 0)
        for value in (None, True, False, 0, 1, 1.5, "text", b"bytes")
    ]
    cache.write_bytes(code_cache.encode(code_facts.stamp(), files))
    loaded = code_cache.decode(cache, code_facts.stamp())
    assert loaded == files
    bindings = loaded[facts.path][1].scopes[0].binds["constants"]
    assert [type(bind.value[0]) for bind in bindings] == [
        type(None),
        bool,
        bool,
        int,
        int,
        float,
        str,
        bytes,
    ]
    loaded[facts.path][1].scopes = cast(list[code_facts.Scope], None)
    assert code_cache.decode(cache, code_facts.stamp()) == files
    damaged, changed = _damage(code_cache._pack(files), "Facts", "scopes", None)
    assert changed == 1
    _write(cache, damaged)
    assert code_cache.decode(cache, code_facts.stamp()) == {}


def test_shared_records_do_not_merge_equal_but_differently_typed_values(tmp_path: Path) -> None:
    files = _stored()
    facts = next(iter(files.values()))[1]
    shared = code_facts.const(False)
    facts.scopes[0].binds["shared"] = [
        code_facts.Bind(1, 0, code_facts.Seq((shared, shared, code_facts.const(0))), 0)
    ]
    cache = tmp_path / "cache.data"
    cache.write_bytes(code_cache.encode(code_facts.stamp(), files))
    loaded = code_cache.decode(cache, code_facts.stamp())
    seq = cast(code_facts.Seq, loaded[facts.path][1].scopes[0].binds["shared"][0].value)
    assert seq.items[0] is seq.items[1]
    assert seq.items[0] is not seq.items[2]
    assert type(seq.items[0][0]) is bool
    assert type(seq.items[2][0]) is int


def test_changed_schema_source_invalidates_imported_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache.data"
    files = _stored()
    cache.write_bytes(code_cache.encode(code_facts.stamp(), files))
    assert code_cache.decode(cache, code_facts.stamp()) == files
    # Die Datensätze kommen aus der geladenen Quelle (RR2-13): Passt sie nicht zum Stand des
    # Speichers, wird nichts gedeutet.
    monkeypatch.setattr(code_facts, "_SOURCE", code_facts._SOURCE + b"\n# anderer Stand\n")
    assert code_cache.decode(cache, code_facts.stamp()) == {}


def test_annotation_syntax_does_not_call_functions() -> None:
    calls: list[str] = []

    def callback() -> type:
        calls.append("ausgeführt")
        return str

    node = ast.parse("callback()", mode="eval").body
    with pytest.raises(ValueError, match="Typbeschreibung"):
        code_cache._syntax_check(node, {"callback": callback})
    assert calls == []


@pytest.mark.parametrize(
    "packed",
    [
        (True, ()),
        (False, ()),
        (4, ()),
        ("UnknownRecord", ()),
        ("Facts", ()),
        (2, (("broken-pair",),)),
        (2, (((1, ()), None),)),
        (3, ((1, ()),)),
    ],
)
def test_invalid_container_forms_are_cache_misses(tmp_path: Path, packed: object) -> None:
    cache = tmp_path / "cache.data"
    _write(cache, packed)
    assert code_cache.decode(cache, code_facts.stamp()) == {}


@pytest.mark.parametrize("parent", [-1, 1, 2, 99])
def test_nested_scope_requires_an_existing_ancestor(tmp_path: Path, parent: int) -> None:
    files = _stored()
    facts = next(iter(files.values()))[1]
    assert len(facts.scopes) > 1
    facts.scopes[1].parent = parent
    cache = tmp_path / "cache.data"
    cache.write_bytes(code_cache.encode(code_facts.stamp(), files))
    assert code_cache.decode(cache, code_facts.stamp()) == {}


def test_shared_scope_reference_is_checked_for_each_file(tmp_path: Path) -> None:
    files = _stored()
    facts = next(iter(files.values()))[1]
    assert len(facts.scopes) > 1
    shared = code_facts.Use("mod", 1, 1, 0)
    facts.scopes[0].binds["shared"] = [code_facts.Bind(1, 0, shared, 0)]
    other = code_facts.extract("app/mod.py", b"VALUE = 1\n")
    assert len(other.scopes) == 1
    other.scopes[0].binds["shared"] = [code_facts.Bind(1, 0, shared, 0)]
    files[other.path] = "hash", other
    cache = tmp_path / "cache.data"
    cache.write_bytes(code_cache.encode(code_facts.stamp(), files))
    assert code_cache.decode(cache, code_facts.stamp()) == {}


def test_scope_bounds_do_not_restrict_other_integer_fields(tmp_path: Path) -> None:
    files = _stored()
    facts = next(iter(files.values()))[1]
    facts.lines = -99
    facts.scopes[0].span = -1000, -1000, 1000, 1000
    facts.scopes[0].binds["value"] = [
        code_facts.Bind(-100, 100, code_facts.Use("mod", 0, -1000, 1000), -99)
    ]
    cache = tmp_path / "cache.data"
    cache.write_bytes(code_cache.encode(code_facts.stamp(), files))
    assert code_cache.decode(cache, code_facts.stamp()) == files


def test_a_refused_replace_keeps_the_file_and_leaves_no_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hält ein anderer Prozess die Datei offen, gibt ``replace_atomically`` auf: Die Datei
    bleibt, wie sie ist, und keine Zwischendatei bleibt liegen. Gegenprobe: ohne Sperre ersetzt
    derselbe Weg."""
    target = tmp_path / "speicher.data"
    target.write_bytes(b"alt")
    code_cache.replace_atomically(target, b"neu")
    assert target.read_bytes() == b"neu"

    def refuse(self: Path, other: Path) -> Path:
        raise PermissionError(other)

    monkeypatch.setattr(Path, "replace", refuse)
    monkeypatch.setattr(code_cache.time, "sleep", lambda seconds: None)
    code_cache.replace_atomically(target, b"dritte")
    assert target.read_bytes() == b"neu"
    assert [path.name for path in tmp_path.iterdir()] == ["speicher.data"]


def test_both_stores_replace_their_file_through_one_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RR2-10: Zwischenspeicher der Auszüge und Ergebnisspeicher ersetzen ihre Datei über
    denselben Helfer; eine Korrektur an der Sperrlogik erreicht so beide."""
    written: list[str] = []
    original = code_cache.replace_atomically

    def recorded(path: Path, data: bytes) -> None:
        written.append(path.name)
        original(path, data)

    monkeypatch.setattr(code_cache, "replace_atomically", recorded)
    stored_index(tmp_path, {})
    assert sorted(written) == ["code_index.data", "code_index.result"]
