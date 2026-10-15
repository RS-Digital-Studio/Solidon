"""Der Ergebnisspeicher des Auflösers: ein Index je Baumstand, einmal gebaut, danach von der Platte.

**Wozu (CS-23).** W2, W5 und W6 fragen den Index in jedem Testprozess. Baute jeder Prozess ihn
selbst, hielte jeder rund 2 GB Auszüge und rechnete eine halbe Minute; im Tor taten das bis zu
vier von acht Arbeitern (Spitze 6,9 GB). Hier wird er einmal je Baumstand gebaut und analysiert,
gespeichert werden nur die Antworten (:class:`tools.code_values.Results`) und die Tafel der
Modulnamen. Jeder weitere Prozess liest sie; einen Auszug lädt er erst, wenn eine Frage ihn
braucht (``resolve``, ``modules[…]``), und dann nur diesen aus dem Zwischenspeicher je Datei
(:func:`tools.code_cache.decode_one`).

**Der Schlüssel** ist der Stand: der Inhaltshash jeder Datei unter ``app/``, ``tools/`` und
``tests/`` und der Quelltext des Auflösers selbst (``tools/code_*.py``), wie der Prozess ihn
geladen hat (:data:`SOURCES`). Bauen zwei Prozesse
zugleich, wartet der zweite an einer Sperre — das Betriebssystem gibt sie frei, wenn ihr Halter
endet — und liest dann, was der erste schrieb; nach :data:`WAIT_SECONDS` baut er selbst.

**Nur Daten.** Wie der Zwischenspeicher: Marshal ohne Codeobjekte, Stand und Baum im Klartext
vor dem Inhalt, jede Form und jedes Feld gegen die Datensätze geprüft (:mod:`tools.code_cache`).
Ein unlesbarer oder veralteter Speicher wird neu gebaut, nie gedeutet.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import sys
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import IO, NamedTuple

from tools import code_cache, code_facts, code_index, code_report, code_scripts, code_values
from tools.code_facts import Facts, source_files
from tools.code_index import CACHE, Index, Names
from tools.code_values import Results

#: Die Quelle, wie dieser Prozess sie geladen hat (wie in jedem ``tools/code_*.py``).
_SOURCE = Path(__file__).read_bytes()

RESULT = Path("tools") / "__pycache__" / "code_index.result"
LOCK = Path("tools") / "__pycache__" / "code_index.lock"
MAGIC = b"SOLIDON-CODE-INDEX-RESULT-1\n"

#: So lange wartet ein Prozess auf einen anderen, der gerade baut; danach baut er selbst. Ein
#: kalter Bau unter Torlast dauert rund zwei Minuten.
WAIT_SECONDS = 600.0

#: Jede Datei, die rechnet, mit der Quelle, die ihr Modul beim Import las — nicht, was jetzt auf
#: der Platte liegt. ``code_index`` lädt die Sammlung, dieses Modul erst das erste ``shared()``;
#: ändert sich dazwischen eine Datei, schriebe der Prozess sonst die Antworten des alten Codes
#: unter dem Stand des neuen (RR2-1). ``tests/test_code_store.py`` hält die Liste gleich mit
#: ``tools/code_*.py``.
SOURCES: dict[str, bytes] = {
    "code_cache.py": code_cache._SOURCE,
    "code_facts.py": code_facts._SOURCE,
    "code_index.py": code_index._SOURCE,
    "code_report.py": code_report._SOURCE,
    "code_scripts.py": code_scripts._SOURCE,
    "code_store.py": _SOURCE,
    "code_values.py": code_values._SOURCE,
}

#: Der Stand des geladenen Auflösers (wie ``code_facts.stamp``).
_STAMP = hashlib.sha256(
    b"".join(name.encode() + b"\0" + source for name, source in sorted(SOURCES.items()))
).hexdigest()


class Stored(NamedTuple):
    """Ein gespeicherter Index: ``files`` je Pfad Inhaltshash und Modul, ``modules`` je Modul
    seine Datei (``x.py`` vor ``x.pyi``), ``names`` je Modul die Namen zur Laufzeit und für die
    Typprüfung und ob es ein Paket ist, ``exports`` je Paket mit ``_EXPORTS`` seine
    Lazy-Exporte (W6 e) fragt sie, ohne einen Auszug zu laden)."""

    tree: str
    files: dict[str, tuple[str, str]]
    modules: dict[str, str]
    packages: tuple[str, ...]
    names: dict[str, tuple[tuple[str, ...], tuple[str, ...], bool]]
    results: Results
    exports: dict[str, dict[str, tuple[str, str]]]


def stamp() -> str:
    """Der Stand des Auflösers; ein Speicher aus einem anderen gilt nicht."""
    return _STAMP


def tree_digests(root: Path) -> dict[str, str]:
    """Inhaltshash je Datei, die der Index liest."""
    return {
        path: hashlib.sha256(file.read_bytes()).hexdigest() for path, file in source_files(root)
    }


def tree_key(digests: Mapping[str, str]) -> str:
    """Ein Hash über alle Pfade mit ihrem Inhaltshash."""
    text = "".join(f"{path}\0{digest}\n" for path, digest in sorted(digests.items()))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _header(tree: str) -> bytes:
    return MAGIC + stamp().encode("ascii") + b"\n" + tree.encode("ascii") + b"\n"


@functools.cache
def _records() -> code_cache.Records:
    return code_cache.records_of(code_values, sys.modules[__name__])


def read(path: Path, tree: str) -> Stored | None:
    """Der gespeicherte Index für diesen Baumstand, oder ``None``."""
    try:
        header = _header(tree)
        with path.open("rb") as handle:
            if handle.read(len(header)) != header:
                return None
            data = handle.read()
        stored = code_cache.loads(data, _records())
    except code_cache.UNREADABLE:
        return None
    if not isinstance(stored, Stored) or stored.tree != tree:
        return None
    return stored


def write(path: Path, stored: Stored) -> None:
    """Über :func:`tools.code_cache.replace_atomically`: Ein Leser sieht nie eine halbe Datei;
    hält ein anderer Prozess sie gerade offen, bleibt sie, wie sie ist, und der nächste baut neu."""
    code_cache.replace_atomically(path, _header(stored.tree) + code_cache.dumps(stored))


def snapshot(index: Index) -> Stored:
    """Was von einem gebauten Index gespeichert wird; analysiert ihn dabei."""
    results = index.results()
    names = {
        module: (tuple(sorted(runtime)), tuple(sorted(typing)), package)
        for module, (runtime, typing, package) in index.module_names.items()
    }
    return Stored(
        tree_key(index.digests),
        {path: (index.digests[path], facts.module) for path, facts in index.files.items()},
        {module: facts.path for module, facts in index.modules.items()},
        tuple(sorted(index.packages)),
        names,
        results,
        {module: dict(facts.exports) for module, facts in index.modules.items() if facts.exports},
    )


class _Loader:
    """Lädt einen Auszug, wenn ihn eine Frage braucht: aus dem Zwischenspeicher je Datei, sonst
    aus der Quelle, wenn sie noch den gespeicherten Inhalt hat."""

    def __init__(self, root: Path, digests: dict[str, str]) -> None:
        self.root = root
        self.digests = digests
        self.loaded: dict[str, Facts] = {}

    def __call__(self, path: str) -> Facts:
        facts = self.loaded.get(path)
        if facts is None:
            facts = self._read(path)
            self.loaded[path] = facts
        return facts

    def _read(self, path: str) -> Facts:
        digest = self.digests[path]
        facts = code_cache.decode_one(self.root / CACHE, code_facts.stamp(), path, digest)
        if facts is not None:
            return facts
        data = (self.root / path).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError(
                f"{path} hat sich geändert, seit der Index gebaut wurde, und sein Auszug fehlt "
                "im Zwischenspeicher. Den Lauf neu starten: Der Index baut sich dann für den "
                "neuen Stand."
            )
        return code_facts.extract(path, data)


class LazyFacts(Mapping[str, Facts]):
    """Auszüge je Schlüssel (Pfad oder Modul), geladen beim ersten Zugriff. Schlüssel,
    ``in`` und ``len`` brauchen keinen Auszug."""

    def __init__(self, paths: Mapping[str, str], loader: _Loader) -> None:
        self._paths = paths
        self._loader = loader

    def __getitem__(self, key: str) -> Facts:
        return self._loader(self._paths[key])

    def __iter__(self) -> Iterator[str]:
        return iter(self._paths)

    def __len__(self) -> int:
        return len(self._paths)

    def __contains__(self, key: object) -> bool:
        return key in self._paths


def restore(root: Path, stored: Stored) -> Index:
    """Ein Index aus dem Speicher: Antworten sofort, Auszüge bei Bedarf."""
    loader = _Loader(root, {path: digest for path, (digest, _module) in stored.files.items()})
    names: dict[str, Names] = {
        module: (frozenset(runtime), frozenset(typing), package)
        for module, (runtime, typing, package) in stored.names.items()
    }
    return Index.restored(
        root,
        LazyFacts({path: path for path in stored.files}, loader),
        LazyFacts(stored.modules, loader),
        set(stored.packages),
        names,
        stored.results,
        stored.exports,
    )


if sys.platform == "win32":
    import msvcrt

    def _try_lock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(handle: IO[bytes]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(handle: IO[bytes]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def exclusive(path: Path, seconds: float) -> Iterator[bool]:
    """Hält die Sperre ``path`` für diesen Prozess, ``True``; nach ``seconds`` ohne sie
    ``False``. Endet der Halter, gibt das Betriebssystem sie frei."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        deadline = time.monotonic() + seconds
        locked = False
        while not locked:
            try:
                _try_lock(handle)
                locked = True
            except OSError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.2)
        try:
            yield locked
        finally:
            if locked:
                _unlock(handle)


def load(root: Path) -> Index:
    """Der Index des Baums ``root`` aus dem Speicher; fehlt er oder ist er veraltet, baut ihn
    genau ein Prozess, die übrigen warten und lesen."""
    base = root.resolve()
    started = time.perf_counter()
    tree = tree_key(tree_digests(base))
    stored = read(base / RESULT, tree)
    if stored is None:
        with exclusive(base / LOCK, WAIT_SECONDS):
            # Der Stand nach dem Warten: Änderte sich eine Datei während des Baus eines
            # anderen, gilt dessen Ergebnis für den neuen Stand (RR2-9).
            tree = tree_key(tree_digests(base))
            stored = read(base / RESULT, tree)
            if stored is None:
                stored = snapshot(Index.build(base))
                write(base / RESULT, stored)
    index = restore(base, stored)
    index.timings["load"] = time.perf_counter() - started
    return index
