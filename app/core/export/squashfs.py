"""SquashFS 4.0 hinter der Laufzeit eines AppImage lesen, ohne es zu starten (Regel 11).

Ein AppImage vom Typ 2 ist eine ausführbare Laufzeit (ELF) mit einem
SquashFS-Abbild dahinter; das Abbild beginnt, wo die Abschnittstabelle der
Laufzeit endet. Solidon liest daraus, was es von einem Slicer braucht — den
Herstellerbestand der Orca-Familie (:mod:`appimage`, RM-549), Curas Drucker
und ob seine Rechenmaschine da ist (:mod:`cura_linux`, RM-599) —, mit den
Entpackern der Standardbibliothek (gzip, xz, lzma, zstd). Gestartet wird das
AppImage dafür nicht, auch nicht mit ``--appimage-extract`` oder
``--appimage-mount``.

Das Abbild ist fremde Eingabe. Jede Länge und jeder Versatz wird gegen die
Datei geprüft, jeder Block nur bis zu seiner Höchstgröße entpackt, Namen mit
Pfadtrennern verworfen, Tiefe, Dateizahl und Gesamtgröße begrenzt.
Verknüpfungen folgt nur :meth:`SquashImage.resolve`, und nur innerhalb des
Abbilds. Was davon reißt, ist ein unlesbares Abbild
(:class:`UnreadableImageError`), kein Absturz.
"""

from __future__ import annotations

import lzma
import struct
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Final

try:
    # Oben und nicht in der Funktion, damit der Paketbau ihn sieht. Ein Python
    # ohne libzstd liest zstd-Abbilder nicht; das ist ein unlesbares Abbild.
    from compression import zstd
except ImportError:
    zstd = None  # type: ignore[assignment]

#: Die Marke einer SquashFS-Version 4 (``hsqs``, klein-endian).
MAGIC: Final = b"hsqs"

#: Die Marke der Laufzeit vom Typ 2 in ihrem ELF-Kopf (Versatz 8).
TYPE_2: Final = b"AI\x02"

#: Größe des Superblocks.
SUPERBLOCK: Final = 96

#: Größte entpackte Länge eines Metadatenblocks.
METADATA_BLOCK: Final = 8192

#: Größter Datenblock, den SquashFS kennt (1 MiB).
MAX_BLOCK: Final = 1 << 20

#: Wie tief ein Verzeichnisbaum gelesen wird.
MAX_DEPTH: Final = 32

#: Wie viele Dateien eine Kopie höchstens umfasst. ElegooSlicer 1.5.3.5 trägt
#: 12 007 Profile, Cura 5.13 9 944 Dateien Druckerbestand.
MAX_COPIED_FILES: Final = 60_000

#: Wie viele Bytes eine Kopie höchstens umfasst. ElegooSlicer 1.5.3.5 trägt
#: 21 MB, Cura 5.13 8 MB.
MAX_COPIED_BYTES: Final = 1 << 30

#: Wie vielen Verknüpfungen :meth:`SquashImage.resolve` auf einem Weg folgt.
MAX_LINKS: Final = 16

#: Wie lang ein Verknüpfungsziel sein darf.
MAX_LINK: Final = 4096

#: Die Art eines Verzeichnisses im Verzeichniseintrag (:attr:`Entry.kind`).
DIRECTORY: Final = 1

#: Die Art einer Datei im Verzeichniseintrag.
FILE: Final = 2

_DIRECTORY = DIRECTORY
_FILE = FILE
_SYMLINK = 3
_EXTENDED_DIRECTORY = 8
_EXTENDED_FILE = 9
_EXTENDED_SYMLINK = 10
_UNCOMPRESSED_METADATA = 0x8000
_UNCOMPRESSED_BLOCK = 1 << 24
_NO_FRAGMENT = 0xFFFFFFFF
_FRAGMENTS_PER_BLOCK = METADATA_BLOCK // 16


class UnreadableImageError(Exception):
    """Das Abbild lässt sich nicht lesen: kein AppImage vom Typ 2, eine
    Kompression ohne Entpacker oder ein beschädigter Aufbau. Der Text nennt
    die Stelle, fürs Protokoll."""


@dataclass(frozen=True, slots=True)
class Entry:
    """Ein Eintrag des Abbilds: Verzeichnis, Datei oder etwas anderes."""

    name: str
    kind: int
    reference: int


@dataclass(frozen=True, slots=True)
class _Directory:
    block: int
    offset: int
    size: int


@dataclass(frozen=True, slots=True)
class _File:
    start: int
    size: int
    fragment: int
    fragment_offset: int
    blocks: tuple[int, ...]


def image_offset(head: bytes) -> int:
    """Wo hinter der Laufzeit eines AppImage vom Typ 2 das Abbild beginnt.

    Es folgt unmittelbar auf die Abschnittstabelle der Laufzeit:
    ``e_shoff + e_shentsize * e_shnum`` aus dem ELF-Kopf (32 oder 64 Bit).
    """
    if len(head) < 64 or head[:4] != b"\x7fELF":
        raise UnreadableImageError("no ELF runtime")
    if head[8:11] != TYPE_2:
        raise UnreadableImageError("not an AppImage of type 2")
    order = "<" if head[5] == 1 else ">"
    if head[4] == 2:
        (table,) = struct.unpack_from(f"{order}Q", head, 0x28)
        size, count = struct.unpack_from(f"{order}HH", head, 0x3A)
    elif head[4] == 1:
        (table,) = struct.unpack_from(f"{order}I", head, 0x20)
        size, count = struct.unpack_from(f"{order}HH", head, 0x2E)
    else:
        raise UnreadableImageError("unknown ELF class")
    return int(table) + int(size) * int(count)


def _decompressor(kind: int) -> Callable[[bytes, int], bytes]:
    """Der Entpacker für die Kompression ``kind`` des Superblocks.

    Er entpackt höchstens ``limit`` Bytes und verlangt einen vollständigen
    Strom; mehr oder weniger ist ein beschädigter Block.
    """
    if kind == 1:

        def gzip(data: bytes, limit: int) -> bytes:
            engine = zlib.decompressobj()
            out = engine.decompress(data, limit)
            if not engine.eof:
                raise UnreadableImageError("a gzip block does not end within its size")
            return out

        return gzip
    if kind in {2, 4}:
        form = lzma.FORMAT_ALONE if kind == 2 else lzma.FORMAT_XZ

        def xz(data: bytes, limit: int) -> bytes:
            engine = lzma.LZMADecompressor(form)
            try:
                out = engine.decompress(data, limit)
            except lzma.LZMAError as problem:
                raise UnreadableImageError(f"an xz block is damaged: {problem}") from problem
            if not engine.eof:
                raise UnreadableImageError("an xz block does not end within its size")
            return out

        return xz
    if kind == 6:
        if zstd is None:
            raise UnreadableImageError("this Python has no zstd")
        library = zstd

        def zstandard(data: bytes, limit: int) -> bytes:
            engine = library.ZstdDecompressor()
            try:
                out = engine.decompress(data, limit)
            except library.ZstdError as problem:
                raise UnreadableImageError(f"a zstd block is damaged: {problem}") from problem
            if not engine.eof:
                raise UnreadableImageError("a zstd block does not end within its size")
            return out

        return zstandard
    raise UnreadableImageError(f"compression {kind} has no reader here (lzo or lz4)")


#: Die Kompressionen, die Solidon gemessen in Slicer-AppImages vorfand: zstd
#: (Orca-Familie), gzip (Cura 5.13). Die übrigen kann es auch.
COMPRESSIONS: Final = {1: "gzip", 2: "lzma", 4: "xz", 6: "zstd"}


def readable_compressions() -> tuple[str, ...]:
    """Die Kompressionen, die dieses Python entpacken kann — der Starttest des
    Pakets verlangt unter Linux gzip und zstd (``tools/check_frozen_start.py``)."""
    found: list[str] = []
    for kind, name in COMPRESSIONS.items():
        try:
            _decompressor(kind)
        except UnreadableImageError:
            continue
        found.append(name)
    return tuple(found)


class SquashImage:
    """Ein SquashFS-Abbild in einer offenen Datei, ab ``offset`` gelesen.

    Nur lesend, und nur, was Solidon braucht: Verzeichnisse und reguläre
    Dateien. Verknüpfungen, Geräte und erweiterte Attribute bleiben ungelesen.
    """

    def __init__(self, handle: BinaryIO, offset: int, length: int) -> None:
        self._handle = handle
        self._offset = offset
        self._length = length
        head = self._read(0, SUPERBLOCK)
        if head[:4] != MAGIC:
            raise UnreadableImageError("no squashfs behind the runtime")
        (
            _inodes,
            _time,
            self.block_size,
            self._fragments,
            compression,
            block_log,
            _flags,
            _ids,
            major,
            _minor,
        ) = struct.unpack_from("<IIIIHHHHHH", head, 4)
        (
            self._root,
            used,
            _id_table,
            _xattr_table,
            self._inode_table,
            self._directory_table,
            self._fragment_table,
            _export_table,
        ) = struct.unpack_from("<QQQQQQQQ", head, 32)
        if major != 4:
            raise UnreadableImageError(f"squashfs version {major}")
        if not 4096 <= self.block_size <= MAX_BLOCK or 1 << block_log != self.block_size:
            raise UnreadableImageError(f"block size {self.block_size}")
        if used > length:
            raise UnreadableImageError("the image is longer than the file")
        self._length = used
        self._inflate = _decompressor(compression)
        self._metadata: dict[int, tuple[bytes, int]] = {}
        self._fragment_cache: dict[int, bytes] = {}

    @classmethod
    def of(cls, handle: BinaryIO) -> SquashImage:
        """Das Abbild eines AppImage vom Typ 2 in ``handle``."""
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(0)
        offset = image_offset(handle.read(64))
        if not 0 < offset < size:
            raise UnreadableImageError("the runtime points outside the file")
        return cls(handle, offset, size - offset)

    def _read(self, position: int, count: int) -> bytes:
        if position < 0 or count < 0 or position + count > self._length:
            raise UnreadableImageError(f"{count} bytes at {position} lie outside the image")
        self._handle.seek(self._offset + position)
        data = self._handle.read(count)
        if len(data) != count:
            raise UnreadableImageError(f"the file ends before {position + count}")
        return data

    def _metadata_block(self, position: int) -> tuple[bytes, int]:
        """Ein Metadatenblock ab ``position``: Inhalt und Lage des nächsten."""
        known = self._metadata.get(position)
        if known is not None:
            return known
        (header,) = struct.unpack("<H", self._read(position, 2))
        size = header & ~_UNCOMPRESSED_METADATA
        if not 0 < size <= METADATA_BLOCK:
            raise UnreadableImageError(f"a metadata block of {size} bytes")
        raw = self._read(position + 2, size)
        data = raw if header & _UNCOMPRESSED_METADATA else self._inflate(raw, METADATA_BLOCK)
        found = (data, position + 2 + size)
        if len(self._metadata) > 4096:
            self._metadata.clear()
        self._metadata[position] = found
        return found

    def _metadata_bytes(self, position: int, offset: int, count: int) -> tuple[bytes, int, int]:
        """``count`` Bytes eines Metadatenstroms ab Block ``position``, Versatz
        ``offset`` — und wo der Strom danach weitergeht."""
        out = bytearray()
        while True:
            data, following = self._metadata_block(position)
            if offset > len(data):
                raise UnreadableImageError("a metadata offset beyond its block")
            take = data[offset : offset + count - len(out)]
            out += take
            offset += len(take)
            if len(out) == count:
                return bytes(out), position, offset
            position, offset = following, 0

    def _inode(self, reference: int) -> _Directory | _File | None:
        """Das Verzeichnis oder die Datei hinter ``reference``; sonst ``None``."""
        block = self._inode_table + (reference >> 16)
        offset = reference & 0xFFFF
        head, block, offset = self._metadata_bytes(block, offset, 16)
        kind = struct.unpack_from("<H", head)[0]
        if kind == _DIRECTORY:
            body, *_ = self._metadata_bytes(block, offset, 16)
            start, _links, size, at, _parent = struct.unpack("<IIHHI", body)
            return _Directory(start, at, size)
        if kind == _EXTENDED_DIRECTORY:
            body, *_ = self._metadata_bytes(block, offset, 24)
            _links, size, start, _parent, _count, at, _xattr = struct.unpack("<IIIIHHI", body)
            return _Directory(start, at, size)
        if kind == _FILE:
            body, block, offset = self._metadata_bytes(block, offset, 16)
            start, fragment, fragment_offset, size = struct.unpack("<IIII", body)
        elif kind == _EXTENDED_FILE:
            body, block, offset = self._metadata_bytes(block, offset, 40)
            start, size, _sparse, _links, fragment, fragment_offset, _xattr = struct.unpack(
                "<QQQIIII", body
            )
        else:
            return None
        whole, rest = divmod(size, self.block_size)
        count = whole + (1 if rest and fragment == _NO_FRAGMENT else 0)
        if count * 4 > self._length:
            raise UnreadableImageError(f"a file of {size} bytes")
        sizes, *_ = self._metadata_bytes(block, offset, 4 * count)
        return _File(start, size, fragment, fragment_offset, struct.unpack(f"<{count}I", sizes))

    def root(self) -> Entry:
        """Das Wurzelverzeichnis."""
        return Entry("", _DIRECTORY, int(self._root))

    def entries(self, reference: int) -> list[Entry]:
        """Die Einträge des Verzeichnisses hinter ``reference``."""
        directory = self._inode(reference)
        if not isinstance(directory, _Directory):
            raise UnreadableImageError("not a directory")
        remaining = directory.size - 3
        if remaining <= 0:
            return []
        data, *_ = self._metadata_bytes(
            self._directory_table + directory.block, directory.offset, remaining
        )
        found: list[Entry] = []
        at = 0
        while at + 12 <= len(data):
            count, start, _base = struct.unpack_from("<III", data, at)
            at += 12
            for _ in range(count + 1):
                if at + 8 > len(data):
                    raise UnreadableImageError("a directory listing ends inside an entry")
                offset, _delta, kind, length = struct.unpack_from("<HhHH", data, at)
                at += 8
                raw = data[at : at + length + 1]
                at += length + 1
                if len(raw) != length + 1:
                    raise UnreadableImageError("a directory listing ends inside a name")
                found.append(Entry(raw.decode("utf-8", "replace"), kind, (start << 16) | offset))
        return found

    def find(self, path: PurePosixPath) -> Entry | None:
        """Der Eintrag unter ``path`` (relativ zur Wurzel), oder ``None``."""
        current: Entry | None = self.root()
        for part in path.parts:
            if current is None or current.kind != _DIRECTORY:
                return None
            current = next((e for e in self.entries(current.reference) if e.name == part), None)
        return current

    def link_target(self, entry: Entry) -> str:
        """Wohin die Verknüpfung ``entry`` zeigt, wie sie im Abbild steht."""
        block = self._inode_table + (entry.reference >> 16)
        head, block, offset = self._metadata_bytes(block, entry.reference & 0xFFFF, 16)
        if struct.unpack_from("<H", head)[0] not in {_SYMLINK, _EXTENDED_SYMLINK}:
            raise UnreadableImageError(f"{entry.name} is not a link")
        body, block, offset = self._metadata_bytes(block, offset, 8)
        _links, size = struct.unpack("<II", body)
        if not 0 < size <= MAX_LINK:
            raise UnreadableImageError(f"a link of {size} bytes")
        target, *_ = self._metadata_bytes(block, offset, size)
        return target.decode("utf-8", "replace")

    def resolve(self, path: PurePosixPath) -> Entry | None:
        """Der Eintrag unter ``path``, Verknüpfungen unterwegs gefolgt — oder ``None``.

        Gefolgt wird nur innerhalb des Abbilds: Ein absolutes Ziel zeigte im
        eingehängten AppImage auf den Rechner, ein ``..`` über die Wurzel
        hinaus ebenso; beides gilt hier als nicht vorhanden. Mehr als
        :data:`MAX_LINKS` Sprünge sind eine Schleife.
        """
        parts = list(path.parts)
        trail = [self.root()]
        hops = 0
        while parts:
            part = parts.pop(0)
            if part in {"", "."}:
                continue
            if part == "..":
                if len(trail) == 1:
                    return None
                trail.pop()
                continue
            current = trail[-1]
            if current.kind != _DIRECTORY:
                return None
            child = next((e for e in self.entries(current.reference) if e.name == part), None)
            if child is None:
                return None
            if child.kind == _SYMLINK:
                hops += 1
                if hops > MAX_LINKS:
                    raise UnreadableImageError(f"more than {MAX_LINKS} links on {path}")
                target = self.link_target(child)
                if target.startswith("/"):
                    return None
                parts = [*PurePosixPath(target).parts, *parts]
                continue
            trail.append(child)
        return trail[-1]

    def is_file(self, path: PurePosixPath) -> bool:
        """Liegt unter ``path`` eine Datei, Verknüpfungen im Abbild gefolgt?"""
        found = self.resolve(path)
        return found is not None and found.kind == _FILE

    def read(self, entry: Entry) -> bytes:
        """Der Inhalt der Datei ``entry``."""
        inode = self._inode(entry.reference)
        if not isinstance(inode, _File):
            raise UnreadableImageError(f"{entry.name} is not a file")
        out = bytearray()
        position = inode.start
        for word in inode.blocks:
            expected = min(self.block_size, inode.size - len(out))
            stored = word & ~_UNCOMPRESSED_BLOCK
            if stored == 0:
                out += bytes(expected)
                continue
            raw = self._read(position, stored)
            position += stored
            out += raw if word & _UNCOMPRESSED_BLOCK else self._inflate(raw, self.block_size)
        rest = inode.size - len(out)
        if rest > 0 and inode.fragment != _NO_FRAGMENT:
            block = self._fragment(inode.fragment)
            out += block[inode.fragment_offset : inode.fragment_offset + rest]
        if len(out) != inode.size:
            raise UnreadableImageError(f"{entry.name} reads {len(out)} of {inode.size} bytes")
        return bytes(out)

    def _fragment(self, index: int) -> bytes:
        known = self._fragment_cache.get(index)
        if known is not None:
            return known
        if index >= self._fragments:
            raise UnreadableImageError(f"fragment {index} of {self._fragments}")
        table, slot = divmod(index, _FRAGMENTS_PER_BLOCK)
        (pointer,) = struct.unpack("<Q", self._read(self._fragment_table + 8 * table, 8))
        entry, *_ = self._metadata_bytes(pointer, slot * 16, 16)
        start, word, _unused = struct.unpack("<QII", entry)
        stored = word & ~_UNCOMPRESSED_BLOCK
        raw = self._read(start, stored)
        data = raw if word & _UNCOMPRESSED_BLOCK else self._inflate(raw, self.block_size)
        if len(self._fragment_cache) > 64:
            self._fragment_cache.clear()
        self._fragment_cache[index] = data
        return data

    def files(self, top: Entry, suffix: str) -> Iterator[tuple[PurePosixPath, Entry]]:
        """Jede Datei mit Endung ``suffix`` unter ``top``, mit ihrem Pfad darunter.

        Namen mit Pfadtrennern, ``.`` und ``..`` gelten als beschädigt; ein
        Verzeichnis, das zweimal vorkommt, wird einmal gelesen.
        """
        seen: set[int] = set()

        def walk(
            entry: Entry, below: PurePosixPath, depth: int
        ) -> Iterator[tuple[PurePosixPath, Entry]]:
            if depth > MAX_DEPTH:
                raise UnreadableImageError(f"deeper than {MAX_DEPTH} folders")
            if entry.reference in seen:
                return
            seen.add(entry.reference)
            for child in self.entries(entry.reference):
                name = child.name
                if not name or name in {".", ".."} or "/" in name or "\\" in name or "\0" in name:
                    raise UnreadableImageError(f"a name {name!r}")
                if child.kind == _DIRECTORY:
                    yield from walk(child, below / name, depth + 1)
                elif child.kind == _FILE and name.casefold().endswith(suffix):
                    yield below / name, child

        if top.kind != _DIRECTORY:
            return
        yield from walk(top, PurePosixPath(), 0)


def copy_folder(image: SquashImage, top: Entry, target: Path, suffix: str = "") -> int:
    """Jede Datei mit Endung ``suffix`` unter ``top`` nach ``target``; ihre Zahl.

    Verknüpfungen werden nicht kopiert. Mehr als :data:`MAX_COPIED_FILES`
    Dateien oder :data:`MAX_COPIED_BYTES` Bytes, oder ein Name, der aus
    ``target`` hinausführte, machen das Abbild unlesbar.
    """
    count = 0
    written = 0
    for relative, entry in image.files(top, suffix):
        count += 1
        if count > MAX_COPIED_FILES:
            raise UnreadableImageError(f"more than {MAX_COPIED_FILES} files")
        data = image.read(entry)
        written += len(data)
        if written > MAX_COPIED_BYTES:
            raise UnreadableImageError(f"more than {MAX_COPIED_BYTES} bytes")
        destination = target.joinpath(*relative.parts)
        if not destination.is_relative_to(target):
            raise UnreadableImageError(f"{relative} leads out of the copy")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    return count
