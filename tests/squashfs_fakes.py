"""Nachgebaute AppImages vom Typ 2: ein SquashFS-4.0-Abbild hinter einem ELF-Kopf.

Für ``app.core.export.squashfs`` und seine Leser (Orca-Bestand in
``appimage``, Curas Drucker in ``cura_linux``). Der Aufbau folgt dem Format;
dass der Leser echte Abbilder liest, belegen der Bytevergleich gegen 7-Zip und
``test_real_slicers.py`` am Linux-Runner, nicht diese Datei.
"""

from __future__ import annotations

import lzma
import struct
import zlib
from collections.abc import Callable, Mapping
from compression import zstd
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Link:
    """Eine Verknüpfung im Abbild, mit ihrem Ziel, wie es dort steht."""

    target: str


#: Ein Baum: Name auf Inhalt, Unterbaum oder Verknüpfung.
Tree = Mapping[str, "bytes | Link | Tree"]

COMPRESSORS: dict[str, tuple[int, Callable[[bytes], bytes]]] = {
    "gzip": (1, zlib.compress),
    "xz": (4, lambda data: lzma.compress(data, format=lzma.FORMAT_XZ)),
    "zstd": (6, zstd.compress),
}

#: Wo das Abbild in :func:`appimage_file` beginnt: hinter 128 Byte Laufzeit.
IMAGE_AT = 128

_NONE = 0xFFFFFFFF
_NOWHERE = 0xFFFFFFFFFFFFFFFF


def _metadata(stream: bytes, compress: Callable[[bytes], bytes] | None) -> tuple[bytes, list[int]]:
    """Metadatenblöcke aus ``stream`` und der Versatz jedes Blocks."""
    out = bytearray()
    starts: list[int] = []
    for at in range(0, len(stream), 8192):
        chunk = stream[at : at + 8192]
        starts.append(len(out))
        packed = compress(chunk) if compress is not None else chunk
        if compress is not None and len(packed) < len(chunk):
            out += struct.pack("<H", len(packed)) + packed
        else:
            out += struct.pack("<H", len(chunk) | 0x8000) + chunk
    return bytes(out), starts


def tree_of(folder: Path) -> dict[str, Any]:
    """Der Baum eines Ordners, Dateien mit ihrem Inhalt."""
    return {
        entry.name: tree_of(entry) if entry.is_dir() else entry.read_bytes()
        for entry in sorted(folder.iterdir())
    }


def appimage_file(
    path: Path,
    tree: Tree,
    *,
    compression: str = "zstd",
    block_size: int = 4096,
    extended: bool = False,
    fragments: bool = True,
    packed_metadata: bool = True,
) -> Path:
    """Ein AppImage vom Typ 2 mit ``tree`` als SquashFS 4.0, nach dessen Aufbau.

    Die Inode-Tabelle bleibt unkomprimiert, damit jeder Verweis vor dem
    Schreiben feststeht; Verzeichnis- und Fragmenttabelle werden gepackt,
    wenn ``packed_metadata`` gilt. Ein Block aus Nullen wird als Lücke
    abgelegt, ein unpackbarer roh.
    """
    kind, pack = COMPRESSORS[compression]
    nodes: list[tuple[str, Any, int]] = []  # Name, Inhalt, Elternnummer

    def collect(name: str, content: Any, parent: int) -> None:
        nodes.append((name, content, parent))
        number = len(nodes)
        if isinstance(content, Mapping):
            for child in sorted(content):
                collect(child, content[child], number)

    collect("", tree, 0)
    data = bytearray()
    files: dict[int, tuple[int, list[int], int, int]] = {}
    tails = bytearray()
    tail_blocks: list[bytes] = []
    for index, (_name, content, _parent) in enumerate(nodes):
        if not isinstance(content, bytes):
            continue
        start = 96 + len(data)
        words: list[int] = []
        whole = len(content) // block_size
        rest = content[whole * block_size :]
        chunks = [content[i * block_size : (i + 1) * block_size] for i in range(whole)]
        if rest and not fragments:
            chunks.append(rest)
        for chunk in chunks:
            if not any(chunk):
                words.append(0)
                continue
            packed = pack(chunk)
            if len(packed) < len(chunk):
                data += packed
                words.append(len(packed))
            else:
                data += chunk
                words.append(len(chunk) | 1 << 24)
        fragment, offset = _NONE, 0
        if rest and fragments:
            if len(tails) + len(rest) > block_size:
                tail_blocks.append(bytes(tails))
                tails.clear()
            fragment, offset = len(tail_blocks), len(tails)
            tails += rest
        files[index] = (start, words, fragment, offset)
    if tails:
        tail_blocks.append(bytes(tails))
    entries = bytearray()
    for block in tail_blocks:
        packed = pack(block)
        start = 96 + len(data)
        if len(packed) < len(block):
            data += packed
            entries += struct.pack("<QII", start, len(packed), 0)
        else:
            data += block
            entries += struct.pack("<QII", start, len(block) | 1 << 24, 0)

    def size_of(index: int) -> int:
        content = nodes[index][1]
        if isinstance(content, Mapping):
            return 16 + (24 if extended else 16)
        if isinstance(content, Link):
            return 16 + 8 + len(content.target.encode("utf-8")) + (4 if extended else 0)
        return 16 + (40 if extended else 16) + 4 * len(files[index][1])

    def basic_kind(content: Any) -> int:
        if isinstance(content, Mapping):
            return 1
        return 3 if isinstance(content, Link) else 2

    positions: list[int] = []
    at = 0
    for index in range(len(nodes)):
        positions.append(at)
        at += size_of(index)

    def reference(index: int) -> int:
        block, offset = divmod(positions[index], 8192)
        return (block * 8194) << 16 | offset

    children: dict[int, list[int]] = {}
    for index, (_name, _content, parent) in enumerate(nodes):
        if parent:
            children.setdefault(parent - 1, []).append(index)
    listing = bytearray()
    places: dict[int, tuple[int, int]] = {}
    for index, (_name, content, _parent) in enumerate(nodes):
        if not isinstance(content, Mapping):
            continue
        begin = len(listing)
        for child in children.get(index, []):
            name = nodes[child][0].encode("utf-8")
            listing += struct.pack("<III", 0, reference(child) >> 16, child + 1)
            child_kind = basic_kind(nodes[child][1])
            listing += struct.pack("<HhHH", positions[child] % 8192, 0, child_kind, len(name) - 1)
            listing += name
        places[index] = (begin, len(listing) - begin)
    directory_table, directory_starts = _metadata(bytes(listing), pack if packed_metadata else None)

    inodes = bytearray()
    for index, (_name, content, parent) in enumerate(nodes):
        number = index + 1
        if isinstance(content, Mapping):
            begin, length = places[index]
            where = directory_starts[begin // 8192] if length else 0
            inodes += struct.pack("<HHHHII", 8 if extended else 1, 0o755, 0, 0, 0, number)
            links = 2 + sum(isinstance(nodes[c][1], Mapping) for c in children.get(index, []))
            if extended:
                inodes += struct.pack(
                    "<IIIIHHI", links, length + 3, where, parent or 1, 0, begin % 8192, _NONE
                )
            else:
                inodes += struct.pack("<IIHHI", where, links, length + 3, begin % 8192, parent or 1)
        elif isinstance(content, Link):
            target = content.target.encode("utf-8")
            inodes += struct.pack("<HHHHII", 10 if extended else 3, 0o777, 0, 0, 0, number)
            inodes += struct.pack("<II", 1, len(target)) + target
            if extended:
                inodes += struct.pack("<I", _NONE)
        else:
            start, words, fragment, offset = files[index]
            inodes += struct.pack("<HHHHII", 9 if extended else 2, 0o644, 0, 0, 0, number)
            if extended:
                inodes += struct.pack(
                    "<QQQIIII", start, len(content), 0, 1, fragment, offset, _NONE
                )
            else:
                inodes += struct.pack("<IIII", start, fragment, offset, len(content))
            inodes += struct.pack(f"<{len(words)}I", *words)
    inode_table, _starts = _metadata(bytes(inodes), None)

    body = bytearray(data)
    inode_start = 96 + len(body)
    body += inode_table
    directory_start = 96 + len(body)
    body += directory_table
    fragment_table = _NOWHERE
    if entries:
        packed_entries, entry_starts = _metadata(bytes(entries), pack if packed_metadata else None)
        entries_at = 96 + len(body)
        body += packed_entries
        fragment_table = 96 + len(body)
        body += b"".join(struct.pack("<Q", entries_at + start) for start in entry_starts)
    ids, _id_starts = _metadata(struct.pack("<I", 0), None)
    ids_at = 96 + len(body)
    body += ids
    id_table = 96 + len(body)
    body += struct.pack("<Q", ids_at)
    used = 96 + len(body)
    superblock = b"hsqs" + struct.pack(
        "<IIIIHHHHHHQQQQQQQQ",
        len(nodes),
        0,
        block_size,
        len(tail_blocks),
        kind,
        block_size.bit_length() - 1,
        0 if fragments else 0x10,
        1,
        4,
        0,
        reference(0),
        used,
        id_table,
        _NOWHERE,
        inode_start,
        directory_start,
        fragment_table,
        _NOWHERE,
    )
    head = bytearray(IMAGE_AT)
    head[:16] = b"\x7fELF\x02\x01\x01\x00AI\x02\x00\x00\x00\x00\x00"
    struct.pack_into("<Q", head, 0x28, 64)
    struct.pack_into("<HHH", head, 0x3A, 64, 1, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(head) + superblock + bytes(body))
    return path
