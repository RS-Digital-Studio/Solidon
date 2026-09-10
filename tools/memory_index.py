"""Eine Zeile in `MEMORY.md` einfügen — unter Sperre und atomar.

`.claude/memory/MEMORY.md` ist eine geteilte Datei: An diesem Projekt arbeiten
mehrere Sitzungen zugleich, und jede legt ab und zu eine Erinnerung an. Der
naheliegende Weg — Datei lesen, Zeile anhängen, Datei schreiben — verliert
dabei still einen Eintrag, sobald zwei Sitzungen sich überlappen: Die zweite
schreibt einen Stand zurück, den sie gelesen hat, bevor die erste fertig war.
Auffallen kann das niemandem, denn eine fehlende Erinnerung meldet sich nicht.

Deshalb drei Dinge, und keines davon ist Zierat:

1. **Eine Sperrdatei daneben.** Wer schreiben will, hält sie exklusiv.
2. **Gelesen wird unter der Sperre**, nicht davor. Ein Stand, der vor dem
   Sperren gelesen wurde, kann beim Schreiben schon alt sein — genau der
   Fehler, den die Sperre verhindern soll.
3. **Vor dem Schreiben wird nachgezählt.** Alle übrigen Zeilen müssen
   unverändert sein und genau eine dazugekommen. Das fängt den Fall, den eine
   Sperre nicht fängt: einen Fehler in diesem Werkzeug selbst.

Aufruf:

    python tools/memory_index.py --section "Diese Maschine" \\
        --line "- [Titel](datei.md) — worum es geht."

Die Zeile wird ans Ende des genannten Abschnitts gesetzt. Ohne `--section`
kommt sie ans Ende der Datei.
"""

from __future__ import annotations

import argparse
import importlib
import os
import re
import stat
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from time import monotonic, sleep
from typing import cast

REPOSITORY = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPOSITORY / ".claude" / "memory" / "MEMORY.md"

#: Wie lange auf eine fremde Sperre gewartet wird, bevor der Lauf aufgibt.
LOCK_TIMEOUT_SECONDS = 10.0

#: Ein Eintrag, wie ihn ``tests/test_directory_docs.py`` sucht: ``[Titel](datei.md)``.
#: Wer eine Zeile ohne diesen Bau einfügt, legt sie ab, wo der Wächter sie
#: nicht findet — und der meldet sie dann als fehlenden Zeiger.
ENTRY = re.compile(r"\]\(([a-z0-9_-]+\.md)\)")


class IndexWriteError(RuntimeError):
    """Der Index ließ sich nicht sicher ändern."""


def _posix_lock(descriptor: int) -> None:
    """Sperrt eine Datei über das erst auf POSIX geladene Systemmodul."""
    module = importlib.import_module("fcntl")
    flock = cast(Callable[[int, int], None], vars(module)["flock"])
    flock(descriptor, int(vars(module)["LOCK_EX"]) | int(vars(module)["LOCK_NB"]))


@contextmanager
def index_lock(index: Path) -> Iterator[None]:
    """Hält die Sperre neben dem Index, solange der Block läuft.

    Dieselbe Bauart wie ``updates._cache_lock``: eine eigene Datei, exklusiv
    geöffnet, mit einer Frist statt eines unbegrenzten Wartens. Eine Sperre,
    auf die man ewig wartet, ist von einem Hänger nicht zu unterscheiden.
    """
    lock_path = index.parent / f".{index.name}.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise IndexWriteError(f"{lock_path} ist keine gewöhnliche Datei.")
        deadline = monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                if os.name == "nt":
                    msvcrt = importlib.import_module("msvcrt")
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    _posix_lock(descriptor)
                break
            except OSError as problem:
                if monotonic() >= deadline:
                    raise IndexWriteError(
                        f"Eine andere Sitzung hält {lock_path.name} seit über "
                        f"{LOCK_TIMEOUT_SECONDS:.0f} Sekunden."
                    ) from problem
                sleep(0.05)
        try:
            yield
        finally:
            if os.name == "nt":
                msvcrt = importlib.import_module("msvcrt")
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                module = importlib.import_module("fcntl")
                flock = cast(Callable[[int, int], None], vars(module)["flock"])
                flock(descriptor, int(vars(module)["LOCK_UN"]))
    finally:
        os.close(descriptor)


def place_line(lines: list[str], line: str, section: str | None) -> list[str]:
    """Die neue Zeilenfolge: ``line`` am Ende von ``section``.

    Ans **Ende** des Abschnitts und nicht an seinen Anfang, weil der Index
    chronologisch wächst — wer oben einfügt, schiebt jedes Mal den ganzen
    Abschnitt im Diff durch.
    """
    if section is None:
        return [*lines, line]

    heading = f"## {section}"
    # **Genau einmal, sonst wird nicht geraten** (Regel 21). Ein doppelter
    # Titel ist bei drei Maschinen ein realistisches Merge-Artefakt, und
    # `lines.index` nähme still den ersten — die Nachzählung unten fängt das
    # nicht, denn eine Zeile im falschen Abschnitt ist auch „genau eine dazu".
    treffer = lines.count(heading)
    if treffer != 1:
        raise IndexWriteError(
            f'Der Abschnitt „{section}" steht {treffer}-mal im Index.'
            if treffer
            else f'Der Abschnitt „{section}" steht nicht im Index.'
        )
    start = lines.index(heading)

    end = len(lines)
    for position in range(start + 1, len(lines)):
        if lines[position].startswith("## "):
            end = position
            break
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return [*lines[:end], line, *lines[end:]]


def check_only_one_line_appeared(before: list[str], after: list[str], line: str) -> None:
    """Genau eine Zeile dazu, alle übrigen unverändert — sonst kein Schreiben.

    Die Sperre schützt vor der **anderen** Sitzung. Diese Prüfung schützt vor
    dieser hier: ein Muster, das zu viel trifft, ein Abschnitt, der zweimal
    vorkommt, ein Ausrutscher beim Zusammensetzen. Verglichen wird die Liste
    ohne die neue Zeile gegen den Stand davor — Zeichen für Zeichen.
    """
    if len(after) != len(before) + 1:
        raise IndexWriteError(
            f"Der Index hätte {len(after)} Zeilen statt {len(before) + 1} — nicht geschrieben."
        )
    for position, content in enumerate(after):
        if content == line and after[:position] + after[position + 1 :] == before:
            return
    raise IndexWriteError("Neben der neuen Zeile hätte sich eine andere geändert.")


def insert(index: Path, line: str, *, section: str | None = None) -> int:
    """Fügt ``line`` ein und gibt ihre Zeilennummer zurück (1-basiert).

    Gelesen wird **unter** der Sperre. Geschrieben wird über eine Datei
    daneben und ``os.replace``: Ein Abbruch mitten im Schreiben hinterlässt
    damit den alten Index und keinen halben.
    """
    if any(zeichen in line for zeichen in "\r\n"):
        # Die Nachzählung unten zählt **Listenelemente**, zusammengefügt wird
        # danach über den Zeilenumbruch — eine Zeile mit Umbruch darin bestünde
        # die Prüfung und legte trotzdem zwei an. Ein Wagenrücklauf wäre
        # schlimmer: Er machte beim Zusammenfügen ein CRLF, und der Lauf danach
        # weigert sich, den Index überhaupt noch anzufassen — das Werkzeug
        # machte sich an der Datei unbrauchbar, die es schützen soll.
        raise IndexWriteError(
            "Die Zeile trägt einen Zeilenumbruch — das wären mehrere Zeilen, nicht eine."
        )
    if not ENTRY.search(line):
        raise IndexWriteError(
            "Die Zeile enthält keinen Verweis der Form [Titel](datei.md) — "
            "so findet tests/test_directory_docs.py sie nicht."
        )
    with index_lock(index):
        with index.open(encoding="utf-8", newline="") as source:
            raw = source.read()
        if "\r\n" in raw:
            raise IndexWriteError("Der Index trägt Wagenrückläufe — das gehört erst geklärt.")
        trailing = raw.endswith("\n")
        before = raw.split("\n")
        if trailing:
            before = before[:-1]

        after = place_line(before, line, section)
        check_only_one_line_appeared(before, after, line)

        written = "\n".join(after) + ("\n" if trailing else "")
        handle, temporary = tempfile.mkstemp(dir=str(index.parent), prefix=".memory-index-")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="") as sink:
                sink.write(written)
                # Erst auf die Platte, dann umbenennen — sonst kann der Name
                # vor den Daten dort stehen, und ein Systemabsturz lässt eine
                # leere `MEMORY.md` zurück. Fünf Stellen im Haus machen es so.
                sink.flush()
                os.fsync(sink.fileno())
            Path(temporary).replace(index)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    return after.index(line) + 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--line", required=True, help="die fertige Markdown-Zeile")
    parser.add_argument("--section", default=None, help='Überschrift ohne „## "')
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="ein anderer Index")
    options = parser.parse_args(argv)
    try:
        position = insert(options.index, options.line, section=options.section)
    except IndexWriteError as problem:
        print(f"Nicht geschrieben: {problem}", file=sys.stderr)
        return 1
    print(f"{options.index}:{position} eingefügt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
