"""Gemeinsame Dateisperre für das private Lizenzarchiv.

Generator und Support-Oberfläche schreiben dieselbe JSONL-Datei. Ein
atomisches Ersetzen schützt nur vor halben Dateien; ohne gemeinsame Sperre
könnten zwei vollständige Schreibvorgänge einander trotzdem verlieren.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO


class ArchiveBusyError(OSError):
    """Das Archiv wird gerade an einer anderen Stelle geschrieben."""


def _prepare_lock(stream: BinaryIO) -> None:
    """Stellt das eine sperrbare Byte auch auf Windows bereit."""
    stream.seek(0, os.SEEK_END)
    if stream.tell() == 0:
        stream.write(b"\0")
        stream.flush()
        os.fsync(stream.fileno())


def _try_lock(stream: BinaryIO) -> None:
    """Belegt genau ein Byte ohne Warten; die Zeitschleife liegt außen."""
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        return
    fcntl = importlib.import_module("fcntl")

    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(stream: BinaryIO) -> None:
    """Gibt die plattformspezifische Sperre wieder frei."""
    stream.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        return
    fcntl = importlib.import_module("fcntl")

    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def archive_lock(path: Path, *, timeout: float = 5.0) -> Iterator[None]:
    """Serialisiert jeden vollständigen Lese-Ändern-Schreiben-Durchgang."""
    target = path.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_name(f".{target.name}.lock")
    try:
        stream = lock_path.open("a+b")
    except OSError as problem:
        raise ArchiveBusyError(
            "Die Sperrdatei des privaten Schlüsselarchivs ließ sich nicht öffnen. "
            "Ablageort prüfen und erneut versuchen."
        ) from problem
    locked = False
    try:
        _prepare_lock(stream)
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            try:
                _try_lock(stream)
                locked = True
                break
            except OSError as problem:
                if time.monotonic() >= deadline:
                    raise ArchiveBusyError(
                        "Das private Schlüsselarchiv wird bereits in einem anderen "
                        "Fenster geändert. Dort abschließen oder schließen und erneut "
                        "versuchen."
                    ) from problem
                time.sleep(0.05)
        with contextlib.suppress(OSError):
            lock_path.chmod(0o600)
        yield
    finally:
        if locked:
            with contextlib.suppress(OSError):
                _unlock(stream)
        stream.close()
