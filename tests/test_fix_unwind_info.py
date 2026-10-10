"""Die Korrektur der Abwicklungsinformation (``tools/fix_unwind_info.py``, RM-768).

Jeder Fall baut eine kleine x86_64-Bibliothek aus Bytes: Funktionen mit
Stapelprobe (falsch kodiert, mit und ohne ``push rax``), eine richtig
kodierte mit ``sub rsp, imm32`` und fremde Prologe, dazu Stubs, Symbol- und
indirekte Tabelle und ``__unwind_info`` als reguläre oder volle komprimierte
Seite. Plattformunabhängig — gelesen und geschrieben werden nur Bytes.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

import pytest

from tools import fix_unwind_info as tool

ROOT = Path(__file__).resolve().parent.parent

#: Funktionsadressen in der Bibliothek; ``__TEXT`` beginnt bei 0.
TEXT_AT = 0x1000
STUBS_AT = 0x1800
UNWIND_AT = 0x1900
FUNCTIONS = (0x1000, 0x1100, 0x1200, 0x1300, 0x1400)
END = 0x1500

SIX = b"\x55\x41\x57\x41\x56\x41\x55\x41\x54\x53"  # rbp r15 r14 r13 r12 rbx
FIVE = b"\x41\x57\x41\x56\x41\x55\x41\x54\x53"  # r15 r14 r13 r12 rbx


def _encoding(where: int, adjust: int, count: int, *, lsda: bool = False) -> int:
    """``STACK_IND`` mit Versatz, ``adj``, Registerzahl und Permutation 0 (Pushes wie oben)."""
    value = tool.MODE_STACK_IND | (where << 16) | (adjust << 13) | (count << 10)
    return value | (tool.HAS_LSDA if lsda else 0)


def _call(at: int, stub: int) -> bytes:
    return b"\xe8" + struct.pack("<i", stub - (at + 5))


def _probe(start: int, pushes: bytes, size: int, *, rax: bool, stub: int = STUBS_AT) -> bytes:
    """Prolog mit Stapelprobe: Pushes, [push rax], mov eax, call, sub rsp, rax, [pop rax]."""
    code = pushes + (b"\x50" if rax else b"") + b"\xb8" + struct.pack("<I", size)
    code += _call(start + len(code), stub) + b"\x48\x29\xc4" + (b"\x58" if rax else b"")
    return code + b"\xc3"


@dataclass
class Library:
    data: bytes
    encodings: dict[int, int]


def _library(
    *,
    compressed: bool = False,
    slack: int = 64,
    probe: bytes | None = None,
    probe_encoding: int | None = None,
) -> Library:
    """Eine Bibliothek mit fünf Funktionen; ``probe`` ersetzt die erste (Gegenproben)."""
    first = probe if probe is not None else _probe(FUNCTIONS[0], SIX, 0x1B58, rax=True)
    codes = [
        first,
        _probe(FUNCTIONS[1], FIVE, 0x1010, rax=False),
        SIX + b"\x48\x81\xec" + struct.pack("<I", 0x1238) + b"\xc3",  # richtig: sub rsp, imm32
        _probe(FUNCTIONS[3], SIX, 0x1B58, rax=True, stub=STUBS_AT + 6),  # ruft memcpy
        b"\x53\xc3",  # STACK_IMMD
    ]
    shared = _encoding(13, 7, 6, lsda=True)
    encodings = {
        FUNCTIONS[0]: probe_encoding if probe_encoding is not None else shared,
        FUNCTIONS[1]: _encoding(12, 6, 5),
        FUNCTIONS[2]: shared,
        FUNCTIONS[3]: _encoding(13, 7, 6),
        FUNCTIONS[4]: 0x02020400,
    }
    entries = [(start, encodings[start]) for start in FUNCTIONS]
    lsdas = [(FUNCTIONS[0], 0x4000), (FUNCTIONS[2], 0x4100)]
    # Wie im Rad teilen sich die falsche und die richtige Funktion ein gemeinsames Wort.
    common = [shared, 0x02020400]
    unwind = _unwind(entries, lsdas, common, compressed=compressed)
    size = len(unwind) + slack
    unwind += bytes(slack)

    symbols = [b"____chkstk_darwin", b"_memcpy"]
    strings = b"\0" + b"\0".join(symbols) + b"\0"
    commands = bytearray()
    sections = [
        (b"__text", TEXT_AT, STUBS_AT - TEXT_AT, 0, 0),
        (b"__stubs", STUBS_AT, 12, 0, 6),
        (b"__unwind_info", UNWIND_AT, size, 0, 0),
    ]
    segment_end = UNWIND_AT + size
    symtab_at = (segment_end + 15) // 16 * 16
    strings_at = symtab_at + 16 * len(symbols)
    indirect_at = strings_at + len(strings)
    segment = struct.pack(
        "<II16sQQQQiiII",
        0x19,
        72 + 80 * len(sections),
        b"__TEXT",
        0,
        segment_end,
        0,
        segment_end,
        5,
        5,
        len(sections),
        0,
    )
    for name, address, length, first_indirect, stub_size in sections:
        segment += struct.pack(
            "<16s16sQQIIIIIIII",
            name,
            b"__TEXT",
            address,
            length,
            address,
            4,
            0,
            0,
            0,
            first_indirect,
            stub_size,
            0,
        )
    commands += segment
    commands += struct.pack("<IIIIII", 0x2, 24, symtab_at, len(symbols), strings_at, len(strings))
    dysymtab = [0] * 18
    dysymtab[12], dysymtab[13] = indirect_at, 2
    commands += struct.pack("<II18I", 0xB, 80, *dysymtab)
    header = struct.pack(
        "<IiiIIIII", tool.MH_MAGIC_64, tool.CPU_TYPE_X86_64, 3, 6, 3, len(commands), 0, 0
    )

    data = bytearray(indirect_at + 8)
    data[: len(header)] = header
    data[len(header) : len(header) + len(commands)] = commands
    for start, code in zip(FUNCTIONS, codes, strict=True):
        data[start : start + len(code)] = code
    data[STUBS_AT : STUBS_AT + 12] = b"\xff\x25\0\0\0\0" * 2
    data[UNWIND_AT : UNWIND_AT + size] = unwind
    offset = 1
    for number, name in enumerate(symbols):
        struct.pack_into("<IBBhQ", data, symtab_at + 16 * number, offset, 0x01, 0, 0, 0)
        offset += len(name) + 1
    data[strings_at : strings_at + len(strings)] = strings
    struct.pack_into("<II", data, indirect_at, 0, 1)
    return Library(bytes(data), encodings)


def _unwind(
    entries: list[tuple[int, int]],
    lsdas: list[tuple[int, int]],
    common: list[int],
    *,
    compressed: bool,
) -> bytes:
    """``__unwind_info`` mit einer Seite: regulär oder komprimiert."""
    index_at = 28 + 4 * len(common) + 4
    lsda_at = index_at + 24
    page_at = lsda_at + 8 * len(lsdas)
    if compressed:
        local = list(dict.fromkeys(enc for _start, enc in entries if enc not in common))
        words = []
        for start, encoding in entries:
            choice = (
                common.index(encoding)
                if encoding in common
                else len(common) + local.index(encoding)
            )
            words.append((choice << 24) | (start - entries[0][0]))
        page = struct.pack("<IHHHH", 3, 12, len(words), 12 + 4 * len(words), len(local))
        page += struct.pack(f"<{len(words)}I", *words) + struct.pack(f"<{len(local)}I", *local)
    else:
        page = struct.pack("<IHH", 2, 8, len(entries))
        page += b"".join(struct.pack("<II", start, encoding) for start, encoding in entries)
    blob = struct.pack("<7I", 1, 28, len(common), 28 + 4 * len(common), 1, index_at, 2)
    blob += struct.pack(f"<{len(common)}I", *common) + struct.pack("<I", 0x10)
    blob += struct.pack("<III", entries[0][0], page_at, lsda_at)
    blob += struct.pack("<III", END, 0, lsda_at + 8 * len(lsdas))
    blob += b"".join(struct.pack("<II", start, offset) for start, offset in lsdas)
    return blob + page


def _table(data: bytes) -> tuple[tool.Image, bytes]:
    image = tool.read_image(data)
    assert image is not None
    section = image.sections["__unwind_info"]
    return image, data[section.offset : section.offset + section.size]


def _found(data: bytes) -> dict[int, tuple[int, int, int, int | None]]:
    """Was libunwind je Funktion nachschlägt."""
    _image, blob = _table(data)
    found = {}
    for start in FUNCTIONS:
        looked = tool.look_up(blob, start)
        assert looked is not None
        found[start] = looked
    return found


@pytest.mark.parametrize("compressed", [False, True], ids=["regular", "compressed"])
def test_the_probe_offset_moves_onto_the_immediate_and_nothing_else_changes(compressed):
    library = _library(compressed=compressed)
    before = _found(library.data)
    outcome = tool.fix_library(library.data)
    assert outcome.corrected == 2
    assert outcome.repacked is compressed
    assert [entry.split(": ")[1] for entry in outcome.foreign] == [
        "Aufruf geht nicht an ___chkstk_darwin"
    ]
    assert outcome.data is not None and len(outcome.data) == len(library.data)
    after = _found(outcome.data)
    # Mit push rax steht das Immediate an 12 statt 13, ohne an 10 statt 12.
    expected = dict(before)
    for start, where in ((FUNCTIONS[0], 12), (FUNCTIONS[1], 10)):
        begin, end, encoding, lsda = before[start]
        expected[start] = (begin, end, (encoding & ~tool.SIZE_MASK) | (where << 16), lsda)
    assert after == expected
    assert after[FUNCTIONS[0]][3] == 0x4000  # die LSDA reist mit
    # Gelesen wird jetzt die Rahmengröße: 0x1b58 + 8 · 7 und 0x1010 + 8 · 6.
    image, _blob = _table(outcome.data)
    for start, size in ((FUNCTIONS[0], 0x1B58 + 56), (FUNCTIONS[1], 0x1010 + 48)):
        encoding = after[start][2]
        where = (encoding & tool.SIZE_MASK) >> 16
        adjust = (encoding >> tool.ADJUST_SHIFT) & 7
        assert struct.unpack("<I", image.code(start + where, 4))[0] + 8 * adjust == size
    # Außerhalb von __unwind_info bleibt jedes Byte.
    section = image.sections["__unwind_info"]
    span = slice(section.offset, section.offset + section.size)
    assert bytes(outcome.data[: span.start]) == library.data[: span.start]
    assert bytes(outcome.data[span.stop :]) == library.data[span.stop :]


@pytest.mark.parametrize("compressed", [False, True], ids=["regular", "compressed"])
def test_a_second_run_changes_nothing(compressed):
    first = tool.fix_library(_library(compressed=compressed).data)
    assert first.data is not None
    second = tool.fix_library(first.data)
    assert (second.corrected, second.already, second.data) == (0, 2, None)


def test_a_repacked_table_that_does_not_fit_stops():
    # Die falsche Funktion braucht ein eigenes lokales Wort; ohne freie Bytes passt es nicht.
    with pytest.raises(tool.UnwindError, match="neu gepackt"):
        tool.fix_library(_library(compressed=True, slack=0).data)


def _without(code: bytes, old: bytes, new: bytes) -> bytes:
    assert code.count(old) == 1
    return code.replace(old, new)


_GOOD = _probe(FUNCTIONS[0], SIX, 0x1B58, rax=True)


@pytest.mark.parametrize(
    ("probe", "encoding", "reason"),
    [
        (_without(_GOOD, b"\x48\x29\xc4\x58", b"\x48\x29\xc4\x90"), None, "push rax ohne pop rax"),
        (_without(_GOOD, b"\x48\x29\xc4", b"\x48\x01\xc4"), None, "kein sub rsp, rax"),
        (_probe(FUNCTIONS[0], SIX, 0x1B50, rax=True), None, "Rahmen nicht auf 16 Byte"),
        (_probe(FUNCTIONS[0], SIX, 0x1B58, rax=False), None, "push rax passt nicht"),
        (_GOOD, _encoding(13, 6, 6), "adj ist nicht"),
        (_GOOD, _encoding(13, 7, 5), "Pushes passen nicht"),
        (_GOOD, _encoding(11, 7, 6), "Versatz 11 weder 13 noch 12"),
    ],
    ids=["no-pop", "no-sub", "unaligned", "no-push-rax", "adj", "registers", "offset"],
)
def test_a_prolog_that_is_not_exactly_the_probe_stays_and_is_reported(probe, encoding, reason):
    library = _library(probe=probe, probe_encoding=encoding)
    outcome = tool.fix_library(library.data)
    assert outcome.corrected == 1  # nur die zweite Funktion
    assert any(entry.startswith(f"{FUNCTIONS[0]:#x}: {reason}") for entry in outcome.foreign)
    assert outcome.data is not None
    assert _found(outcome.data)[FUNCTIONS[0]][2] == _found(library.data)[FUNCTIONS[0]][2]


def _wheel(folder: Path, library: Library) -> Path:
    path = folder / "OCP" / ".dylibs" / "libTKFillet.8.0.1.dylib"
    path.parent.mkdir(parents=True)
    path.write_bytes(library.data)
    return path


def test_an_unexpected_count_writes_nothing(tmp_path, monkeypatch):
    library = _library()
    path = _wheel(tmp_path, library)
    monkeypatch.setitem(tool.EXPECTED, "9.9", {"libTKFillet.8.0.1.dylib": 3})
    with pytest.raises(tool.UnwindError, match=r"libTKFillet.8.0.1.dylib 2 statt 3"):
        tool.run("9.9", tool.libraries_under(tmp_path), write=True, codesign=False)
    assert path.read_bytes() == library.data


def test_the_expected_count_writes_and_the_second_run_finds_it_done(tmp_path, monkeypatch):
    path = _wheel(tmp_path, _library())
    monkeypatch.setitem(tool.EXPECTED, "9.9", {"libTKFillet.8.0.1.dylib": 2})
    _lines, changed = tool.run("9.9", tool.libraries_under(tmp_path), write=True, codesign=False)
    assert changed == [path]
    lines, changed = tool.run("9.9", tool.libraries_under(tmp_path), write=True, codesign=False)
    assert changed == []
    assert f"{path}: korrigiert 0, schon korrigiert 2, fremd 1" in lines


def test_an_unchecked_wheel_version_stops(tmp_path):
    _wheel(tmp_path, _library())
    with pytest.raises(tool.UnwindError, match="nicht geprüft"):
        tool.run("0.0.1", tool.libraries_under(tmp_path), write=False, codesign=False)


def test_a_folder_without_intel_libraries_stops(tmp_path):
    (tmp_path / "libTKernel.so").write_bytes(b"\x7fELF" + bytes(64))
    with pytest.raises(tool.UnwindError, match="nur für macOS Intel"):
        tool.run(
            next(iter(tool.EXPECTED)), tool.libraries_under(tmp_path), write=False, codesign=False
        )


def test_the_pinned_wheel_is_the_checked_one():
    """Ein Versionswechsel in ``constraints.txt`` verlangt einen neuen ``--scan`` (RM-768)."""
    text = (ROOT / "constraints.txt").read_text(encoding="utf-8")
    pinned = re.search(rf"(?m)^{re.escape(tool.WHEEL)}==(\S+)$", text)
    assert pinned is not None
    assert pinned.group(1) in tool.EXPECTED
    assert sum(tool.EXPECTED[pinned.group(1)].values()) == 309


def test_the_registers_decode_like_libunwind():
    # Permutation 0 heißt: von der niedrigsten Adresse aufwärts rbx, r12 … rbp.
    assert tool.saved_registers(_encoding(13, 7, 6)) == [1, 2, 3, 4, 5, 6]
    assert tool.saved_registers(_encoding(12, 6, 5)) == [1, 2, 3, 4, 5]
    # Zwei Register, Permutation 5·1 + 0: erst r13 (Index 2 der Restliste), dann rbx.
    assert tool.saved_registers(tool.MODE_STACK_IND | (2 << 10) | 10) == [3, 1]


def test_the_lookup_check_rejects_a_table_that_answers_differently():
    """Die Nachprüfung jedes Funktionsanfangs ist der Schutz gegen einen Packfehler."""
    outcome = tool.fix_library(_library(compressed=True).data)
    assert outcome.data is not None
    _image, blob = _table(outcome.data)
    table = tool.read_table(blob)
    tool.verify(blob, table)
    start, encoding = table.entries[1]
    table.entries[1] = (start, encoding ^ (1 << 16))
    with pytest.raises(tool.UnwindError, match="Nachschlag"):
        tool.verify(blob, table)


def _many_entries(count: int = 3000) -> tool.Table:
    """Viele Funktionen mit vielen verschiedenen Kodierungen und LSDAs, eine Lücke über 24 Bit."""
    entries = []
    lsdas = []
    start = 0x1000
    for number in range(count):
        if number == count // 2:
            start += 1 << 24  # zwingt eine Seitengrenze über den 24-Bit-Versatz
        encoding = 0x02000000 | ((number % 250) << 16) | (((number // 250) % 6) << 10)
        if number % 7 == 0:
            encoding |= tool.HAS_LSDA
            lsdas.append((start, 0x9000 + 16 * number))
        entries.append((start, encoding))
        start += 0x40
    common = sorted({encoding for _start, encoding in entries})[:40]
    return tool.Table(1, common, [0x10], entries, lsdas, start)


def test_a_repacked_table_spans_pages_and_answers_every_function():
    """Seitengrenzen aus 4 KB, 256 Kodierungen und 24-Bit-Versatz; LSDAs über mehrere Seiten."""
    table = _many_entries()
    blob = tool.write_table(table, 200_000)
    pages = struct.unpack_from("<7I", blob, 0)[6] - 1
    assert pages >= 4
    tool.verify(blob, table)
    again = tool.read_table(blob)
    assert again.entries == table.entries and again.lsdas == table.lsdas
    assert {kind for kind, _members in again.pages} == {tool.COMPRESSED_PAGE}


def test_the_lookup_check_covers_every_entry_and_every_lsda():
    """Auch ein Eintrag ohne ``STACK_IND`` und eine LSDA müssen stimmen."""
    table = _many_entries()
    blob = tool.write_table(table, 200_000)
    start, encoding = table.entries[1501]
    assert encoding & tool.MODE_MASK != tool.MODE_STACK_IND
    table.entries[1501] = (start, encoding ^ (1 << 16))
    with pytest.raises(tool.UnwindError, match="Nachschlag"):
        tool.verify(blob, table)
    table = _many_entries()
    function, offset = table.lsdas[300]
    table.lsdas[300] = (function, offset + 4)
    with pytest.raises(tool.UnwindError, match="Nachschlag"):
        tool.verify(blob, table)


def test_a_regular_and_a_compressed_page_read_and_look_up_across_their_border():
    """Gemischte Seiten wie im Rad: Das letzte Ende der ersten Seite ist die Basis der zweiten."""
    first = [(0x1000, 0x02010000), (0x1040, 0x02020000)]
    second = [(0x2000, 0x02030000 | tool.HAS_LSDA), (0x2080, 0x02010000)]
    common = [0x02010000]
    index_at = 28 + 4 * len(common) + 4
    lsda_at = index_at + 36
    regular_at = lsda_at + 8
    regular = struct.pack("<IHH", 2, 8, 2) + b"".join(struct.pack("<II", *row) for row in first)
    compressed_at = regular_at + len(regular)
    words = [(1 << 24) | 0, (0 << 24) | 0x80]
    compressed = struct.pack("<IHHHH", 3, 12, 2, 20, 1) + struct.pack("<2I", *words)
    compressed += struct.pack("<I", 0x02030000 | tool.HAS_LSDA)
    blob = struct.pack("<7I", 1, 28, 1, 28 + 4, 1, index_at, 3) + struct.pack(
        "<II", common[0], 0x10
    )
    blob += struct.pack("<III", 0x1000, regular_at, lsda_at)
    blob += struct.pack("<III", 0x2000, compressed_at, lsda_at)
    blob += struct.pack("<III", 0x2100, 0, lsda_at + 8)
    blob += struct.pack("<II", 0x2000, 0x7000) + regular + compressed
    table = tool.read_table(blob)
    assert table.entries == first + second
    assert [kind for kind, _members in table.pages] == [tool.REGULAR_PAGE, tool.COMPRESSED_PAGE]
    assert tool.look_up(blob, 0x1FFF) == (0x1040, 0x2000, 0x02020000, None)
    assert tool.look_up(blob, 0x2000) == (0x2000, 0x2080, 0x02030000 | tool.HAS_LSDA, 0x7000)
    assert tool.look_up(blob, 0x20FF) == (0x2080, 0x2100, 0x02010000, None)
    tool.verify(blob, table)


def test_the_check_writes_nothing_and_fails_until_every_copy_is_corrected(tmp_path, monkeypatch):
    """``--check`` am gebauten Paket: jede Kopie zählt, fremde Bibliotheken nicht (M-1)."""
    monkeypatch.setitem(tool.EXPECTED, "9.9", {"libTKFillet.8.0.1.dylib": 2})
    library = _library()
    for folder in ("Solidon3D", "Solidon3D.app/Contents/Frameworks"):
        path = tmp_path / folder / "OCP" / ".dylibs" / "libTKFillet.8.0.1.dylib"
        path.parent.mkdir(parents=True)
        path.write_bytes(library.data)
    (tmp_path / "Solidon3D" / "libavif.16.dylib").write_bytes(library.data)
    copies = tool.bundle_libraries(tmp_path, "9.9")
    assert [path.name for path in copies] == ["libTKFillet.8.0.1.dylib"] * 2
    with pytest.raises(tool.UnwindError, match="tragen noch falsche"):
        tool.run("9.9", copies, write=True, codesign=False, check=True)
    assert all(path.read_bytes() == library.data for path in copies)
    tool.run("9.9", copies[:1], write=True, codesign=False)
    with pytest.raises(tool.UnwindError, match="tragen noch falsche"):
        tool.run("9.9", copies, write=False, codesign=False, check=True)
    tool.run("9.9", copies[1:], write=True, codesign=False)
    lines, changed = tool.run("9.9", copies, write=True, codesign=False, check=True)
    assert changed == [] and lines[-1].endswith("alle schon korrigiert")


def test_the_scan_reads_the_intel_slice_of_a_universal_wheel(tmp_path):
    """``--scan`` für jedes Rad: zählt, schreibt nie, liest universelle Dateien an x86_64."""
    import zipfile

    library = _library().data
    fat = struct.pack(">II", tool.FAT_MAGIC, 1)
    fat += struct.pack(">iiIII", tool.CPU_TYPE_X86_64, 3, 4096, len(library), 12)
    fat = fat.ljust(4096, b"\0") + library
    wheel = tmp_path / "Fremd-1.0-py3-none-macosx_11_0_universal2.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("Fremd/Qt/lib/Fremd.framework/Versions/A/Fremd", fat)
        archive.writestr("Fremd/.dylibs/libfremd.dylib", library)
    before = wheel.read_bytes()
    lines, wrong = tool.scan(wheel)
    assert wrong == 4
    assert lines[-1].endswith("STACK_IND 8, richtig 2, falsch 4, schon korrigiert 0, fremd 2")
    assert wheel.read_bytes() == before
