"""Korrigiert die Abwicklungsinformation der OpenCASCADE-Bibliotheken auf macOS Intel (RM-768).

**Der Fehler im Rad.** In ``cadquery-ocp-novtk`` für ``macosx_x86_64`` beginnt
jede Funktion mit mehr als 4 KB Stapelrahmen mit einer Stapelprobe::

    push <Register>…; [push rax;] mov eax, imm32; call ___chkstk_darwin;
    sub rsp, rax; [pop rax]

Ihr Eintrag in ``__unwind_info`` ist ``UNWIND_X86_64_MODE_STACK_IND``: Die
Rahmengröße steht als 32-Bit-Wert an einem Versatz in der Funktion, plus
``8 · adj``. Der Versatz wurde aber für ``sub rsp, imm32`` direkt hinter den
Pushes berechnet (3 + Pushbytes) und zeigt deshalb ein Byte (mit
``push rax``) oder zwei Byte (ohne) hinter das Immediate des ``mov eax``.
libunwind liest dort z. B. ``0xe800001b`` statt ``0x1b58`` als Rahmengröße,
und jede C++-Ausnahme, die einen solchen Rahmen verlässt, endet mit einem
Bus-Fehler — beim Kunden das Ende der Anwendung, sobald etwa eine Verrundung
an einer Ecke scheitert. ``adj`` stimmt in beiden Formen.

**Was das Werkzeug tut.** Es liest nur Bytes, es führt nichts aus (§32): Je
``STACK_IND``-Eintrag prüft es den Prolog Byte für Byte — Pushes passend zu
Zahl und Reihenfolge der Register im Eintrag, ``push rax`` genau bei gerader
Registerzahl, ``mov eax, imm32``, ``call`` auf den Stub von
``___chkstk_darwin``, ``sub rsp, rax``, ``pop rax`` genau nach ``push rax``,
``adj`` gleich Registerzahl plus eins, Rahmen auf 16 Byte ausgerichtet — und
setzt den Versatz auf das Immediate. Ein Eintrag, der nicht genau so
aussieht, bleibt unverändert und wird gemeldet (Regel 21).

Liegt jeder falsche Eintrag in einer regulären Seite (volle Kodierung je
Eintrag), wird nur das Wort ersetzt. In komprimierten Seiten teilen sich
falsche und richtige Funktionen dasselbe Kodierungswort, und die Seiten sind
voll; dann wird ``__unwind_info`` mit denselben Einträgen, derselben
Kopfzeile, denselben gemeinsamen Kodierungen und Personalities neu gepackt
(nur komprimierte Seiten). Passt das Ergebnis nicht in den Abschnitt, bricht
das Werkzeug ab. Jede geänderte Tabelle wird danach wie von libunwind
nachgeschlagen — für jeden Funktionsanfang Kodierung, Ende und LSDA — und
muss genau die erwartete Abbildung ergeben.

**Wann es läuft.** In der CI auf jedem macOS-x86_64-Läufer direkt nach der
Installation, mit ``--codesign`` (Ad-hoc-Neusignatur der geänderten
Bibliotheken); der Paketbau signiert danach wie bisher. Es kennt genau die
festgelegte Radversion (:data:`EXPECTED`) und je Bibliothek die Zahl der
Korrekturen; eine andere Version oder eine andere Zahl hält es an, damit ein
Versionswechsel die Korrektur neu prüfen lässt — und sie entfällt, sobald ein
behobenes Rad erscheint (RM-768, gemeldet als
https://github.com/CadQuery/ocp-build-system/issues/67). Ein zweiter Lauf
ändert nichts. Nach dem Paketbau belegt ``--check`` am Bündel, dass das
ausgelieferte Paket die korrigierten Bibliotheken trägt.

Aufruf::

    python tools/fix_unwind_info.py [--codesign] [--dry-run]
    python tools/fix_unwind_info.py --check --package dist
    python tools/fix_unwind_info.py --root <ausgepacktes Rad> --version 8.0.1.1.0
    python tools/fix_unwind_info.py --scan <Rad.whl oder Ordner>
"""

from __future__ import annotations

import argparse
import struct
import subprocess
import sys
import zipfile
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

# Als Skript gestartet (``python tools/fix_unwind_info.py``) steht nur
# ``tools/`` im Suchpfad; ``package_root`` holt ``tools.make_sbom`` aus der Wurzel.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DESCRIPTION: Final = (
    "Abwicklungsinformation der OpenCASCADE-Bibliotheken auf macOS Intel korrigieren"
)

#: Stand der Korrektur, den die Lizenzbeilage als Datum der Änderung nennt
#: (LGPL-2.1 §2 b). Ändert sich, was das Werkzeug schreibt, ändert sich dieses Datum.
CHANGED_ON: Final = "10.10.2026"

#: Das Rad, dessen Bibliotheken korrigiert werden.
WHEEL: Final = "cadquery-ocp-novtk"

#: Je bekannter Radversion und Bibliothek die Zahl der falschen Einträge
#: (Scan über das Rad von PyPI, ``macosx_11_0_x86_64``, 10.10.2026). Andere
#: Bibliotheken des Rads haben keinen.
EXPECTED: Final[dict[str, dict[str, int]]] = {
    "8.0.1.1.0": {
        "libTKBO.8.0.1.dylib": 2,
        "libTKBRep.8.0.1.dylib": 3,
        "libTKBool.8.0.1.dylib": 13,
        "libTKDEGLTF.8.0.1.dylib": 2,
        "libTKDESTEP.8.0.1.dylib": 1,
        "libTKDESTL.8.0.1.dylib": 1,
        "libTKDEVRML.8.0.1.dylib": 2,
        "libTKFeat.8.0.1.dylib": 24,
        "libTKFillet.8.0.1.dylib": 37,
        "libTKG3d.8.0.1.dylib": 1,
        "libTKGeomAlgo.8.0.1.dylib": 77,
        "libTKGeomBase.8.0.1.dylib": 34,
        "libTKHLR.8.0.1.dylib": 12,
        "libTKMath.8.0.1.dylib": 35,
        "libTKOffset.8.0.1.dylib": 16,
        "libTKOpenGl.8.0.1.dylib": 1,
        "libTKService.8.0.1.dylib": 2,
        "libTKShHealing.8.0.1.dylib": 7,
        "libTKTopAlgo.8.0.1.dylib": 32,
        "libTKernel.8.0.1.dylib": 7,
    },
}

#: Mach-O, 64 Bit, little endian; Prozessortyp x86_64.
MH_MAGIC_64: Final = 0xFEEDFACF
FAT_MAGIC: Final = 0xCAFEBABE
FAT_MAGIC_64: Final = 0xCAFEBABF
CPU_TYPE_X86_64: Final = 0x01000007
LC_SEGMENT_64: Final = 0x19
LC_SYMTAB: Final = 0x2
LC_DYSYMTAB: Final = 0xB
INDIRECT_SYMBOL_LOCAL: Final = 0x80000000
INDIRECT_SYMBOL_ABS: Final = 0x40000000

#: Felder der x86_64-Kodierung (``compact_unwind_encoding.h``).
MODE_MASK: Final = 0x0F000000
MODE_STACK_IND: Final = 0x03000000
SIZE_MASK: Final = 0x00FF0000
ADJUST_SHIFT: Final = 13
COUNT_SHIFT: Final = 10
PERMUTATION_MASK: Final = 0x3FF
HAS_LSDA: Final = 0x40000000

REGULAR_PAGE: Final = 2
COMPRESSED_PAGE: Final = 3
#: Größe einer zweiten Seite, wie der Linker sie schreibt.
PAGE_LIMIT: Final = 4096

#: Push-Bytes je Register in der Zählung der Kodierung (rbx=1 … rbp=6).
_PUSHES: Final = {
    b"\x53": 1,
    b"\x41\x54": 2,
    b"\x41\x55": 3,
    b"\x41\x56": 4,
    b"\x41\x57": 5,
    b"\x55": 6,
}
_PUSH_RAX: Final = b"\x50"
_POP_RAX: Final = b"\x58"
_MOV_EAX: Final = b"\xb8"
_CALL: Final = b"\xe8"
_SUB_RSP_RAX: Final = b"\x48\x29\xc4"
_SUB_RSP_IMM32: Final = b"\x48\x81\xec"
#: Der Symbolname in der Mach-O-Tabelle (C-Name `___chkstk_darwin` mit Unterstrich davor).
_PROBE: Final = "____chkstk_darwin"


class UnwindError(RuntimeError):
    """Eine Bibliothek oder ein Rad, das nicht dem erwarteten Bild entspricht."""


# --- Mach-O lesen --------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    name: str
    address: int
    size: int
    offset: int
    reserved1: int
    reserved2: int


@dataclass
class Image:
    """Die Teile einer x86_64-Bibliothek, die das Werkzeug braucht."""

    data: bytearray
    text_address: int
    text_offset: int
    sections: dict[str, Section]
    symbols: list[tuple[str, int]]  # Name und Wert je Symboltabelleneintrag
    indirect: list[int]

    def code(self, address: int, count: int) -> bytes:
        start = address - self.text_address + self.text_offset
        return bytes(self.data[start : start + count])


def x86_64_slice(data: bytes) -> bytes:
    """Die x86_64-Scheibe einer universellen Datei; eine dünne Datei bleibt, wie sie ist.

    Nur für ``--scan``: Andere Räder (Qt) sind ``universal2``. Das OCP-Rad ist
    dünn, und die Korrektur schreibt nur dünne Dateien.
    """
    if len(data) < 8:
        return data
    magic, count = struct.unpack_from(">II", data, 0)
    if magic not in (FAT_MAGIC, FAT_MAGIC_64):
        return data
    width = 20 if magic == FAT_MAGIC else 32
    for number in range(count):
        at = 8 + width * number
        if magic == FAT_MAGIC:
            cputype, _sub, offset, size, _align = struct.unpack_from(">iiIII", data, at)
        else:
            cputype, _sub, offset, size, _align, _reserved = struct.unpack_from(">iiQQII", data, at)
        if cputype == CPU_TYPE_X86_64:
            return data[offset : offset + size]
    return b""


def read_image(data: bytes) -> Image | None:
    """Liest eine dünne x86_64-Bibliothek; ``None`` für alles andere."""
    if len(data) < 32:
        return None
    magic, cputype, _sub, _filetype, ncmds, _size, _flags, _reserved = struct.unpack_from(
        "<IiiIIIII", data, 0
    )
    if magic != MH_MAGIC_64 or cputype != CPU_TYPE_X86_64:
        return None
    offset = 32
    sections: dict[str, Section] = {}
    text: tuple[int, int] | None = None
    symtab: tuple[int, int, int, int] | None = None
    dysymtab: tuple[int, int] | None = None
    for _ in range(ncmds):
        command, size = struct.unpack_from("<II", data, offset)
        if command == LC_SEGMENT_64:
            segment = bytes(data[offset + 8 : offset + 24]).rstrip(b"\0").decode()
            vmaddr, _vmsize, fileoff, _filesize = struct.unpack_from("<QQQQ", data, offset + 24)
            if segment == "__TEXT":
                text = (vmaddr, fileoff)
            count = struct.unpack_from("<I", data, offset + 64)[0]
            for number in range(count):
                base = offset + 72 + number * 80
                name = bytes(data[base : base + 16]).rstrip(b"\0").decode()
                owner = bytes(data[base + 16 : base + 32]).rstrip(b"\0").decode()
                address, length, position = struct.unpack_from("<QQI", data, base + 32)
                first, second = struct.unpack_from("<II", data, base + 68)
                if owner == "__TEXT":
                    sections[name] = Section(name, address, length, position, first, second)
        elif command == LC_SYMTAB:
            symtab = struct.unpack_from("<IIII", data, offset + 8)
        elif command == LC_DYSYMTAB:
            values = struct.unpack_from("<18I", data, offset + 8)
            dysymtab = (values[12], values[13])  # indirectsymoff, nindirectsyms
        offset += size
    if text is None:
        return None
    symbols: list[tuple[str, int]] = []
    if symtab is not None:
        symoff, nsyms, stroff, _strsize = symtab
        for number in range(nsyms):
            strx, _type, _sect, _desc, value = struct.unpack_from(
                "<IBBhQ", data, symoff + 16 * number
            )
            end = data.index(b"\0", stroff + strx)
            symbols.append((bytes(data[stroff + strx : end]).decode(errors="replace"), value))
    indirect: list[int] = []
    if dysymtab is not None:
        start, count = dysymtab
        indirect = list(struct.unpack_from(f"<{count}I", data, start))
    return Image(bytearray(data), text[0], text[1], sections, symbols, indirect)


def stub_name(image: Image, target: int) -> str | None:
    """Der Name hinter einem Stub in ``__stubs``; ``None``, wenn ``target`` keiner ist."""
    stubs = image.sections.get("__stubs")
    if stubs is None or stubs.reserved2 == 0:
        return None
    if not stubs.address <= target < stubs.address + stubs.size:
        return None
    distance = target - stubs.address
    if distance % stubs.reserved2:
        return None
    position = stubs.reserved1 + distance // stubs.reserved2
    if position >= len(image.indirect):
        return None
    symbol = image.indirect[position]
    if symbol & (INDIRECT_SYMBOL_LOCAL | INDIRECT_SYMBOL_ABS) or symbol >= len(image.symbols):
        return None
    return image.symbols[symbol][0]


# --- __unwind_info lesen und schreiben ---------------------------------------------


@dataclass
class Table:
    """Eine entpackte ``__unwind_info``: Einträge, LSDAs und was unverändert bleibt."""

    version: int
    common: list[int]
    personalities: list[int]
    #: Funktionsanfang (relativ zur Bildbasis) und Kodierung, aufsteigend.
    entries: list[tuple[int, int]]
    #: Funktionsanfang und LSDA-Versatz, aufsteigend.
    lsdas: list[tuple[int, int]]
    #: ``functionOffset`` des Schlusseintrags im Index (Ende des Codes).
    end: int
    #: Je Seite ihre Art und die Einträge darin, in der Reihenfolge der Tabelle.
    pages: list[tuple[int, list[int]]] = field(default_factory=list)


def read_table(blob: bytes) -> Table:
    """Entpackt ``__unwind_info`` vollständig; jede Seite muss lesbar sein."""
    version, common_at, common_count, personal_at, personal_count, index_at, index_count = (
        struct.unpack_from("<7I", blob, 0)
    )
    if version != 1 or index_count < 1:
        raise UnwindError(f"__unwind_info Version {version} mit {index_count} Indexeinträgen")
    common = list(struct.unpack_from(f"<{common_count}I", blob, common_at))
    personalities = list(struct.unpack_from(f"<{personal_count}I", blob, personal_at))
    index = [struct.unpack_from("<III", blob, index_at + 12 * i) for i in range(index_count)]
    entries: list[tuple[int, int]] = []
    pages: list[tuple[int, list[int]]] = []
    for base, page, _lsda in index[:-1]:
        kind = struct.unpack_from("<I", blob, page)[0]
        first = len(entries)
        if kind == REGULAR_PAGE:
            _kind, at, count = struct.unpack_from("<IHH", blob, page)
            for number in range(count):
                entries.append(struct.unpack_from("<II", blob, page + at + 8 * number))
        elif kind == COMPRESSED_PAGE:
            _kind, at, count, encodings_at, encodings_count = struct.unpack_from(
                "<IHHHH", blob, page
            )
            local = struct.unpack_from(f"<{encodings_count}I", blob, page + encodings_at)
            for number in range(count):
                word = struct.unpack_from("<I", blob, page + at + 4 * number)[0]
                choice = word >> 24
                if choice < common_count:
                    encoding = common[choice]
                elif choice - common_count < encodings_count:
                    encoding = local[choice - common_count]
                else:
                    raise UnwindError(f"Kodierungsindex {choice} außerhalb der Seite")
                entries.append((base + (word & 0xFFFFFF), encoding))
        else:
            raise UnwindError(f"unbekannte Seitenart {kind}")
        pages.append((kind, list(range(first, len(entries)))))
    lsda_start, lsda_end = index[0][2], index[-1][2]
    lsdas = [struct.unpack_from("<II", blob, at) for at in range(lsda_start, lsda_end, 8)]
    if [start for start, _ in entries] != sorted({start for start, _ in entries}):
        raise UnwindError("Einträge nicht streng aufsteigend")
    if [start for start, _ in lsdas] != sorted({start for start, _ in lsdas}):
        raise UnwindError("LSDA-Einträge nicht streng aufsteigend")
    return Table(version, common, personalities, entries, lsdas, index[-1][0], pages)


def write_table(table: Table, size: int) -> bytes:
    """Packt die Tabelle neu: gleicher Kopf, nur komprimierte Seiten, höchstens ``size`` Byte."""
    common_index = {encoding: number for number, encoding in enumerate(table.common)}
    pages: list[tuple[int, list[tuple[int, int]], list[int]]] = []  # Basis, Einträge, lokal
    position = 0
    while position < len(table.entries):
        base = table.entries[position][0]
        taken: list[tuple[int, int]] = []
        local: list[int] = []
        while position < len(table.entries):
            start, encoding = table.entries[position]
            if start - base >= 1 << 24:
                break
            fresh = encoding not in common_index and encoding not in local
            local_count = len(local) + (1 if fresh else 0)
            if len(table.common) + local_count > 256:
                break
            if 12 + 4 * (len(taken) + 1) + 4 * local_count > PAGE_LIMIT:
                break
            if fresh:
                local.append(encoding)
            taken.append((start, encoding))
            position += 1
        if not taken:
            raise UnwindError("ein Eintrag passt in keine Seite")
        pages.append((base, taken, local))

    common_at = 28
    personal_at = common_at + 4 * len(table.common)
    index_at = personal_at + 4 * len(table.personalities)
    lsda_at = index_at + 12 * (len(pages) + 1)
    pages_at = lsda_at + 8 * len(table.lsdas)
    blobs: list[bytes] = []
    for base, taken, local in pages:
        words = []
        for start, encoding in taken:
            choice = common_index.get(encoding)
            if choice is None:
                choice = len(table.common) + local.index(encoding)
            words.append((choice << 24) | (start - base))
        head = struct.pack(
            "<IHHHH", COMPRESSED_PAGE, 12, len(words), 12 + 4 * len(words), len(local)
        )
        blobs.append(
            head + struct.pack(f"<{len(words)}I", *words) + struct.pack(f"<{len(local)}I", *local)
        )
    total = pages_at + sum(len(blob) for blob in blobs)
    if total > size:
        raise UnwindError(f"neu gepackt {total} Byte, der Abschnitt hat {size}")

    out = bytearray(size)
    struct.pack_into(
        "<7I",
        out,
        0,
        table.version,
        common_at,
        len(table.common),
        personal_at,
        len(table.personalities),
        index_at,
        len(pages) + 1,
    )
    struct.pack_into(f"<{len(table.common)}I", out, common_at, *table.common)
    struct.pack_into(f"<{len(table.personalities)}I", out, personal_at, *table.personalities)
    for number, (start, lsda) in enumerate(table.lsdas):
        struct.pack_into("<II", out, lsda_at + 8 * number, start, lsda)
    at = pages_at
    for number, ((base, _taken, _local), blob) in enumerate(zip(pages, blobs, strict=True)):
        first_lsda = next(
            (i for i, (start, _) in enumerate(table.lsdas) if start >= base), len(table.lsdas)
        )
        struct.pack_into("<III", out, index_at + 12 * number, base, at, lsda_at + 8 * first_lsda)
        out[at : at + len(blob)] = blob
        at += len(blob)
    struct.pack_into(
        "<III", out, index_at + 12 * len(pages), table.end, 0, lsda_at + 8 * len(table.lsdas)
    )
    return bytes(out)


def look_up(blob: bytes, target: int) -> tuple[int, int, int, int | None] | None:
    """Wie libunwind: Anfang, Ende, Kodierung und LSDA der Funktion an ``target``."""
    _v, common_at, common_count, _pa, _pc, index_at, index_count = struct.unpack_from(
        "<7I", blob, 0
    )

    def index(number: int) -> tuple[int, int, int]:
        return struct.unpack_from("<III", blob, index_at + 12 * number)

    low, high, last = 0, index_count, index_count - 1
    while low < high:
        middle = (low + high) // 2
        if index(middle)[0] <= target:
            if middle == last or index(middle + 1)[0] > target:
                low = middle
                break
            low = middle + 1
        else:
            high = middle
    if low >= last:
        return None
    base, page, lsda_from = index(low)
    following, _page, lsda_to = index(low + 1)
    kind = struct.unpack_from("<I", blob, page)[0]
    if kind == REGULAR_PAGE:
        _kind, at, count = struct.unpack_from("<IHH", blob, page)
        rows = [struct.unpack_from("<II", blob, page + at + 8 * n) for n in range(count)]
    else:
        _kind, at, count, encodings_at, encodings_count = struct.unpack_from("<IHHHH", blob, page)
        rows = []
        for n in range(count):
            word = struct.unpack_from("<I", blob, page + at + 4 * n)[0]
            choice = word >> 24
            if choice >= common_count + encodings_count:
                raise UnwindError(f"Kodierungsindex {choice} außerhalb der Seite")
            encoding = (
                struct.unpack_from("<I", blob, common_at + 4 * choice)[0]
                if choice < common_count
                else struct.unpack_from(
                    "<I", blob, page + encodings_at + 4 * (choice - common_count)
                )[0]
            )
            rows.append((base + (word & 0xFFFFFF), encoding))
    found = bisect_right([start for start, _ in rows], target) - 1
    if found < 0:
        return None
    start, encoding = rows[found]
    end = rows[found + 1][0] if found + 1 < len(rows) else following
    if not start <= target < end:
        return None
    lsda = None
    if encoding & HAS_LSDA:
        # Binär wie libunwind: Eine falsch geordnete Liste fände dort nichts.
        low, high = 0, (lsda_to - lsda_from) // 8
        while low < high:
            middle = (low + high) // 2
            function, offset = struct.unpack_from("<II", blob, lsda_from + 8 * middle)
            if function == start:
                lsda = offset
                break
            if function < start:
                low = middle + 1
            else:
                high = middle
        if lsda is None:
            raise UnwindError(f"Funktion {start:#x} mit LSDA-Bit ohne LSDA-Eintrag")
    return start, end, encoding, lsda


def verify(blob: bytes, table: Table) -> None:
    """Jeder Funktionsanfang (und das Byte danach) muss genau die erwartete Antwort geben."""
    lsda_of = dict(table.lsdas)
    for number, (start, encoding) in enumerate(table.entries):
        end = table.entries[number + 1][0] if number + 1 < len(table.entries) else table.end
        expected = (start, end, encoding, lsda_of.get(start) if encoding & HAS_LSDA else None)
        for target in {start, min(start + 1, end - 1)}:
            if look_up(blob, target) != expected:
                raise UnwindError(
                    f"Nachschlag an {target:#x}: {look_up(blob, target)} statt {expected}"
                )


# --- Prolog prüfen ---------------------------------------------------------------------


def saved_registers(encoding: int) -> list[int]:
    """Die geretteten Register eines rahmenlosen Eintrags, wie libunwind sie dekodiert."""
    count = (encoding >> COUNT_SHIFT) & 0x7
    permutation = encoding & PERMUTATION_MASK
    divisors = {
        6: (120, 24, 6, 2, 1),
        5: (120, 24, 6, 2, 1),
        4: (60, 12, 3, 1),
        3: (20, 4, 1),
        2: (5, 1),
        1: (1,),
    }
    if count not in divisors:
        return []
    digits = []
    for divisor in divisors[count]:
        digits.append(permutation // divisor)
        permutation -= digits[-1] * divisor
    if count == 6:
        digits.append(0)
    used: set[int] = set()
    registers = []
    for digit in digits[:count]:
        free = [number for number in range(1, 7) if number not in used]
        if digit >= len(free):
            return []
        used.add(free[digit])
        registers.append(free[digit])
    return registers


@dataclass(frozen=True)
class Verdict:
    """Was ein ``STACK_IND``-Eintrag ist.

    ``right`` (``sub rsp, imm32``), ``wrong`` (mit Korrektur), ``fixed`` (schon
    korrigiert) oder ``foreign`` (unbekannter Prolog, bleibt stehen).
    """

    kind: str
    encoding: int
    reason: str = ""


def judge(image: Image, start: int, encoding: int) -> Verdict:
    """Prüft einen ``STACK_IND``-Eintrag gegen seinen Prolog."""
    where = (encoding & SIZE_MASK) >> 16
    if image.code(start + where - 3, 3) == _SUB_RSP_IMM32:
        return Verdict("right", encoding)
    head = image.code(start, 64)
    pushed: list[int] = []
    at = 0
    while True:
        for pattern, register in _PUSHES.items():
            if head.startswith(pattern, at):
                pushed.append(register)
                at += len(pattern)
                break
        else:
            break
    count = (encoding >> COUNT_SHIFT) & 0x7
    adjust = (encoding >> ADJUST_SHIFT) & 0x7
    if not pushed or saved_registers(encoding) != pushed[::-1] or len(pushed) != count:
        return Verdict("foreign", encoding, "Pushes passen nicht zu den Registern des Eintrags")
    buggy = at + 3
    rax = head.startswith(_PUSH_RAX, at)
    if rax != (count % 2 == 0):
        return Verdict("foreign", encoding, "push rax passt nicht zur Ausrichtung")
    at += len(_PUSH_RAX) if rax else 0
    if not head.startswith(_MOV_EAX, at):
        return Verdict("foreign", encoding, "kein mov eax, imm32")
    immediate_at = at + 1
    immediate = struct.unpack_from("<I", head, immediate_at)[0]
    at = immediate_at + 4
    if not head.startswith(_CALL, at):
        return Verdict("foreign", encoding, "kein Aufruf nach mov eax")
    relative = struct.unpack_from("<i", head, at + 1)[0]
    if stub_name(image, start + at + 5 + relative) != _PROBE:
        return Verdict("foreign", encoding, "Aufruf geht nicht an ___chkstk_darwin")
    at += 5
    if not head.startswith(_SUB_RSP_RAX, at):
        return Verdict("foreign", encoding, "kein sub rsp, rax")
    at += len(_SUB_RSP_RAX)
    if rax and not head.startswith(_POP_RAX, at):
        return Verdict("foreign", encoding, "push rax ohne pop rax")
    if adjust != count + 1:
        return Verdict("foreign", encoding, "adj ist nicht Registerzahl plus eins")
    if (immediate + 8 * adjust) % 16:
        return Verdict("foreign", encoding, "Rahmen nicht auf 16 Byte ausgerichtet")
    corrected = (encoding & ~SIZE_MASK) | (immediate_at << 16)
    if where == immediate_at:
        return Verdict("fixed", encoding)
    if where != buggy:
        return Verdict("foreign", encoding, f"Versatz {where} weder {buggy} noch {immediate_at}")
    return Verdict("wrong", corrected)


# --- eine Bibliothek ---------------------------------------------------------------------


@dataclass
class Outcome:
    """Ergebnis je Bibliothek."""

    corrected: int = 0
    already: int = 0
    foreign: list[str] = field(default_factory=list)
    repacked: bool = False
    data: bytes | None = None  # neue Bytes, wenn sich etwas ändert


def fix_library(data: bytes) -> Outcome:
    """Prüft und korrigiert eine Bibliothek im Speicher; schreibt nichts."""
    image = read_image(data)
    outcome = Outcome()
    if image is None or "__unwind_info" not in image.sections:
        return outcome
    section = image.sections["__unwind_info"]
    blob = bytes(image.data[section.offset : section.offset + section.size])
    table = read_table(blob)
    fixes: dict[int, int] = {}
    for number, (start, encoding) in enumerate(table.entries):
        if encoding & MODE_MASK != MODE_STACK_IND:
            continue
        verdict = judge(image, start + image.text_address, encoding)
        if verdict.kind == "wrong":
            fixes[number] = verdict.encoding
        elif verdict.kind == "fixed":
            outcome.already += 1
        elif verdict.kind == "foreign":
            outcome.foreign.append(f"{start:#x}: {verdict.reason}")
    if not fixes:
        return outcome
    expected = Table(
        table.version,
        table.common,
        table.personalities,
        [
            (start, fixes.get(number, encoding))
            for number, (start, encoding) in enumerate(table.entries)
        ],
        table.lsdas,
        table.end,
    )
    in_regular_pages = {
        number for kind, members in table.pages if kind == REGULAR_PAGE for number in members
    }
    if set(fixes) <= in_regular_pages:
        new = bytearray(blob)
        positions = _regular_word_positions(blob)
        for number, encoding in fixes.items():
            struct.pack_into("<I", new, positions[number], encoding)
        new_blob = bytes(new)
    else:
        new_blob = write_table(expected, section.size)
        outcome.repacked = True
    verify(new_blob, expected)
    patched = bytearray(image.data)
    patched[section.offset : section.offset + section.size] = new_blob
    outcome.corrected = len(fixes)
    outcome.data = bytes(patched)
    return outcome


def _regular_word_positions(blob: bytes) -> dict[int, int]:
    """Je Eintrag regulärer Seiten die Stelle seines Kodierungsworts in ``blob``."""
    _v, _ca, _cc, _pa, _pc, index_at, index_count = struct.unpack_from("<7I", blob, 0)
    positions: dict[int, int] = {}
    number = 0
    for i in range(index_count - 1):
        page = struct.unpack_from("<III", blob, index_at + 12 * i)[1]
        kind = struct.unpack_from("<I", blob, page)[0]
        if kind == REGULAR_PAGE:
            _kind, at, count = struct.unpack_from("<IHH", blob, page)
            for n in range(count):
                positions[number + n] = page + at + 8 * n + 4
        else:
            count = struct.unpack_from("<IHH", blob, page)[2]
        number += count
    return positions


# --- das Rad --------------------------------------------------------------------------


def installed_wheel() -> tuple[str, list[Path]]:
    """Version und native Bibliotheken des installierten Rads — ohne es zu importieren."""
    from importlib import metadata

    distribution = metadata.distribution(WHEEL)
    files = [
        Path(str(distribution.locate_file(entry)))
        for entry in distribution.files or ()
        if str(entry).endswith((".dylib", ".so"))
    ]
    return distribution.version, files


def libraries_under(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.suffix in {".dylib", ".so"})


def package_root(dist: Path, *, platform: str = sys.platform) -> Path:
    """Das Artefakt, das der Kunde bekommt — auf macOS die .app.

    Der COLLECT-Ordner daneben trägt dieselben Bibliotheken, wird aber nicht
    ausgeliefert; geprüft wird, was reist. Name und Lage kommen aus derselben
    Quelle wie die Stückliste (make_sbom.artifact_root).
    """
    from tools.make_sbom import artifact_root

    return artifact_root(dist, platform=platform)


def bundle_libraries(root: Path, version: str) -> list[Path]:
    """Die OCC-Bibliotheken des Rads unter ``root``, jede Datei einmal.

    Für ein gebautes Paket oder ein ausgepacktes Rad: gezählt werden nur die
    Bibliotheken aus :data:`EXPECTED` — ein Paket trägt daneben fremde, etwa
    Pillows ``libavif`` mit demselben Fehler (RM-770). Verknüpfungen auf
    dieselbe Datei zählen einmal, echte Kopien (Ordner und ``.app``) je für sich.
    """
    names = set(EXPECTED.get(version, {}))
    found: dict[Path, Path] = {}
    for path in libraries_under(root):
        if path.name in names and path.is_file():
            found.setdefault(path.resolve(), path)
    return sorted(found.values())


def run(
    version: str,
    libraries: Iterable[Path],
    *,
    write: bool,
    codesign: bool,
    check: bool = False,
) -> tuple[list[str], list[Path]]:
    """Prüft alle Bibliotheken gegen :data:`EXPECTED`, schreibt erst, wenn alles stimmt.

    ``check`` schreibt nie und verlangt, dass jede Kopie schon korrigiert ist.
    """
    expected = EXPECTED.get(version)
    if expected is None:
        raise UnwindError(f"{WHEEL} {version} ist nicht geprüft (bekannt: {', '.join(EXPECTED)})")
    lines: list[str] = []
    pending: list[tuple[Path, bytes]] = []
    seen: dict[str, list[int]] = {}
    images = 0
    for path in libraries:
        data = path.read_bytes()
        if read_image(data) is None:
            continue
        images += 1
        outcome = fix_library(data)
        seen.setdefault(path.name, []).append(outcome.corrected + outcome.already)
        if outcome.corrected or outcome.already or outcome.foreign:
            lines.append(
                f"{path}: korrigiert {outcome.corrected}, schon korrigiert "
                f"{outcome.already}, fremd {len(outcome.foreign)}"
                + (" (Tabelle neu gepackt)" if outcome.repacked else "")
            )
        lines.extend(f"    fremd {entry}" for entry in outcome.foreign)
        if outcome.data is not None:
            pending.append((path, outcome.data))
    if not images:
        raise UnwindError("keine x86_64-Mach-O-Bibliothek gefunden — nur für macOS Intel")
    wrong = {
        name: (counts, count)
        for name, count in {**dict.fromkeys(seen, 0), **expected}.items()
        if (counts := seen.get(name, [0])) and any(value != count for value in counts)
    }
    if wrong:
        detail = ", ".join(
            f"{name} {'/'.join(map(str, got))} statt {want}"
            for name, (got, want) in sorted(wrong.items())
        )
        raise UnwindError(f"Korrekturen weichen vom geprüften Rad ab: {detail}")
    if check and pending:
        detail = ", ".join(str(path) for path, _data in pending)
        raise UnwindError(f"{len(pending)} Bibliotheken tragen noch falsche Einträge: {detail}")
    changed: list[Path] = []
    if write and not check:
        for path, data in pending:
            temporary = path.with_name(path.name + ".unwind-tmp")
            temporary.write_bytes(data)
            temporary.chmod(path.stat().st_mode)
            temporary.replace(path)
            changed.append(path)
        if codesign:
            for path in changed:
                subprocess.run(["codesign", "--force", "--sign", "-", str(path)], check=True)
    total = sum(sum(counts) for counts in seen.values())
    written = "geändert" if write else "zu ändern"
    tail = "alle schon korrigiert" if check else f"{len(pending)} Bibliotheken {written}"
    lines.append(
        f"{WHEEL} {version}: {total} Einträge richtig in {images} Bibliotheken, {tail}"
        + (", ad hoc neu signiert" if write and codesign and changed else "")
    )
    return lines, changed


# --- der Scan eines beliebigen Rads -----------------------------------------------------


def members(source: Path) -> Iterable[tuple[str, bytes]]:
    """Name und Bytes jeder nativen Bibliothek in einem Rad (``.whl``) oder Ordner."""
    if source.is_file():
        with zipfile.ZipFile(source) as archive:
            for name in sorted(archive.namelist()):
                if name.endswith((".dylib", ".so")) or ".framework/Versions/" in name:
                    yield name, archive.read(name)
        return
    for path in libraries_under(source):
        yield str(path.relative_to(source)), path.read_bytes()


def scan(source: Path) -> tuple[list[str], int]:
    """Zählt je x86_64-Bibliothek die ``STACK_IND``-Einträge nach Urteil; schreibt nie.

    Für jedes Rad, auch eine noch nicht geprüfte OCP-Version (RM-768): ``falsch``
    sind Einträge mit genau dem Fehler aus diesem Werkzeug. Universelle Dateien
    werden an ihrer x86_64-Scheibe gelesen.
    """
    lines: list[str] = []
    totals = {"right": 0, "wrong": 0, "fixed": 0, "foreign": 0}
    for name, data in members(source):
        image = read_image(x86_64_slice(data))
        if image is None or "__unwind_info" not in image.sections:
            continue
        section = image.sections["__unwind_info"]
        table = read_table(bytes(image.data[section.offset : section.offset + section.size]))
        counts = dict.fromkeys(totals, 0)
        for start, encoding in table.entries:
            if encoding & MODE_MASK == MODE_STACK_IND:
                counts[judge(image, start + image.text_address, encoding).kind] += 1
        for kind, value in counts.items():
            totals[kind] += value
        if any(counts.values()):
            lines.append(
                f"{name}: STACK_IND {sum(counts.values())}, richtig {counts['right']}, "
                f"falsch {counts['wrong']}, schon korrigiert {counts['fixed']}, "
                f"fremd {counts['foreign']}"
            )
    lines.append(
        f"{source.name}: STACK_IND {sum(totals.values())}, richtig {totals['right']}, "
        f"falsch {totals['wrong']}, schon korrigiert {totals['fixed']}, "
        f"fremd {totals['foreign']}"
    )
    return lines, totals["wrong"]


#: Was nach einem Abbruch zu tun ist (Regel 17 sinngemäß).
WAY_OUT: Final = (
    "Nichts geschrieben. Das Rad mit `python tools/fix_unwind_info.py --scan <Rad>` "
    "prüfen (RM-768, " + "https://github.com/CadQuery/ocp-build-system/issues/67): "
    "Trägt es keinen falschen Eintrag mehr, entfallen Werkzeug, Workflowschritte und "
    "der Abschnitt der Lizenzbeilage; sonst EXPECTED aus dem Scan nachziehen."
)


#: Was zu tun ist, wenn ein gebautes Paket unkorrigierte Bibliotheken trägt.
CHECK_WAY_OUT: Final = (
    "Nichts geschrieben. Das Paket trägt nicht die korrigierten Bibliotheken: Prüfen, ob "
    "der Schritt „Abwicklungsinformation von OpenCASCADE korrigieren (Intel-Mac)“ direkt "
    "nach der Installation lief und PyInstaller die Bibliotheken aus diesem Python nahm "
    "(RM-768)."
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        "--root", type=Path, help="gebautes Paket oder ausgepacktes Rad statt der Installation"
    )
    parser.add_argument(
        "--package",
        type=Path,
        metavar="DIST",
        help="das ausgelieferte Artefakt unter DIST (auf macOS die .app, nicht der COLLECT-Ordner)",
    )
    parser.add_argument("--version", help="Radversion zu --root (Vorgabe: die installierte)")
    parser.add_argument("--dry-run", action="store_true", help="nur prüfen, nichts schreiben")
    parser.add_argument(
        "--check",
        action="store_true",
        help="nichts schreiben; Fehler, solange ein Eintrag noch falsch ist",
    )
    parser.add_argument(
        "--codesign", action="store_true", help="geänderte Bibliotheken ad hoc signieren"
    )
    parser.add_argument(
        "--scan", type=Path, metavar="RAD", help="ein Rad oder einen Ordner nur zählen"
    )
    arguments = parser.parse_args(argv)
    if arguments.codesign and sys.platform != "darwin":
        parser.error("--codesign gibt es nur auf macOS")
    if arguments.codesign and (arguments.check or arguments.dry_run):
        parser.error("--codesign schreibt; mit --check oder --dry-run gibt es nichts zu signieren")
    if arguments.package is not None:
        if arguments.root is not None:
            parser.error("--package und --root schließen einander aus")
        arguments.root = package_root(arguments.package)
        if not arguments.root.is_dir():
            parser.error(f"kein Artefakt unter {arguments.root}")
    if arguments.version is not None and arguments.root is None:
        parser.error("--version gehört zu --root")
    try:
        if arguments.scan is not None:
            lines, _wrong = scan(arguments.scan)
            print("\n".join(lines))
            return 0
        if arguments.root is not None:
            version = arguments.version or installed_wheel()[0]
            libraries = bundle_libraries(arguments.root, version)
        else:
            version, libraries = installed_wheel()
        lines, _changed = run(
            version,
            libraries,
            write=not (arguments.dry_run or arguments.check),
            codesign=arguments.codesign,
            check=arguments.check,
        )
    except UnwindError as error:
        way_out = CHECK_WAY_OUT if arguments.check else WAY_OUT
        print(f"fix_unwind_info: {error}\n{way_out}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
