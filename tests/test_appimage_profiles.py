"""Der Herstellerbestand eines AppImage der Orca-Familie, gelesen ohne Start (RM-549).

Ein frisch geladenes AppImage trägt seine Profile nur im eingebetteten
SquashFS; erst sein erster Start legte sie nach ``system/``. Solidon liest das
Abbild als Datei (``app.core.export.appimage``) — gestartet wird nichts
(Regel 11).

Die Abbilder hier baut :func:`appimage_file` nach dem SquashFS-4.0-Aufbau.
Dass der Leser auch echte Abbilder liest, belegen zwei Dinge außerhalb dieser
Datei: ``test_real_slicers.py`` an den installierten AppImages am Linux-Runner,
und der Bytevergleich gegen 7-Zip an Orca 2.4.2, Bambu Studio 2.8.2,
ElegooSlicer 1.5.3.5 und Creality Print 7.3.0 (alle 34 500 Profile gleich).
"""

from __future__ import annotations

import json
import lzma
import os
import random
import shutil
import struct
import subprocess
import threading
import zlib
from collections.abc import Callable, Mapping
from compression import zstd
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from app.core import discover
from app.core.export import appimage, cura_linux
from app.core.export import slicer_profiles as sp

#: Ein Baum: Name auf Inhalt oder Unterbaum.
Tree = Mapping[str, "bytes | Tree"]

_COMPRESSORS: dict[str, tuple[int, Callable[[bytes], bytes]]] = {
    "gzip": (1, zlib.compress),
    "xz": (4, lambda data: lzma.compress(data, format=lzma.FORMAT_XZ)),
    "zstd": (6, zstd.compress),
}

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
    kind, pack = _COMPRESSORS[compression]
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
        if isinstance(content, Mapping):
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
        return 16 + (40 if extended else 16) + 4 * len(files[index][1])

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
            child_kind = 1 if isinstance(nodes[child][1], Mapping) else 2
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
    head = bytearray(128)
    head[:16] = b"\x7fELF\x02\x01\x01\x00AI\x02\x00\x00\x00\x00\x00"
    struct.pack_into("<Q", head, 0x28, 64)
    struct.pack_into("<HHH", head, 0x3A, 64, 1, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(head) + superblock + bytes(body))
    return path


def _json(document: Mapping[str, object]) -> bytes:
    return json.dumps(document).encode("utf-8")


#: Ein Drucker der Orca-Familie, wie er im Abbild unter ``resources/profiles``
#: liegt: Herstellerindex, Erbbasis und Maschine.
ACME: Tree = {
    "Acme.json": _json({"name": "Acme", "version": "1"}),
    "Acme": {
        "machine": {
            "base.json": _json(
                {
                    "name": "Acme base",
                    "instantiation": "false",
                    "printable_area": ["0x0", "220x0", "220x220", "0x220"],
                    "printable_height": "250",
                    "nozzle_diameter": ["0.4"],
                }
            ),
            "Acme One 0.4 nozzle.json": _json(
                {
                    "name": "Acme One 0.4 nozzle",
                    "instantiation": "true",
                    "type": "machine",
                    "printer_model": "Acme One",
                    "inherits": "Acme base",
                }
            ),
        },
        "process": {
            "0.20mm Standard @Acme.json": _json(
                {
                    "name": "0.20mm Standard @Acme",
                    "instantiation": "true",
                    "type": "process",
                    "layer_height": "0.2",
                    "compatible_printers": ["Acme One 0.4 nozzle"],
                }
            )
        },
    },
}

#: Die übrige Ablage eines echten Abbilds, die Solidon nicht liest.
AROUND: Tree = {
    "AppRun": b"#!/bin/sh\nexit 1\n",
    "bin": {"orca-slicer": b"\x7fELF"},
    "resources": {"images": {"logo.png": b"\x89PNG"}, "profiles": ACME},
}


@pytest.fixture(autouse=True)
def _fresh_copies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Kein Test erbt, was ein anderer schon kopiert oder verworfen hat."""
    monkeypatch.setattr(appimage, "_copies", {})
    monkeypatch.setattr(appimage, "_failed", {})
    monkeypatch.setattr(appimage, "_cache_root", lambda: tmp_path / "cache")
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(sp, "config_base", lambda _executable: str(tmp_path / "config"))


@pytest.fixture
def nothing_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regel 11: Wer hier einen Prozess startet, startet das AppImage."""

    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Das AppImage darf zum Lesen nicht gestartet werden")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)


def _orca(tmp_path: Path, tree: Tree = AROUND, **options: Any) -> Path:
    return appimage_file(
        tmp_path / "Downloads" / "OrcaSlicer_Linux_AppImage_Ubuntu2404_V2.4.2.AppImage",
        tree,
        **options,
    )


#: Die Wurzel eines Baums.
_TOP = PurePosixPath()


def _flatten(tree: Tree, below: PurePosixPath = _TOP) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for name, content in tree.items():
        if isinstance(content, Mapping):
            found.update(_flatten(content, below / name))
        else:
            found[(below / name).as_posix()] = content
    return found


@pytest.mark.parametrize("compression", ["gzip", "xz", "zstd"])
@pytest.mark.parametrize("extended", [False, True], ids=["basic", "extended"])
@pytest.mark.parametrize("fragments", [True, False], ids=["fragments", "tail-blocks"])
@pytest.mark.parametrize("packed_metadata", [True, False], ids=["packed", "raw"])
def test_the_profiles_come_out_of_the_image_byte_for_byte(
    tmp_path: Path,
    compression: str,
    extended: bool,
    fragments: bool,
    packed_metadata: bool,
) -> None:
    """Mehrere Blöcke, Lücke, roher Block, Fragmentrest, tiefe Ordner — jede
    Datei kommt so heraus, wie sie hineinging, und nur die Profile."""
    noise = random.Random(549).randbytes(5000)
    profiles: Tree = {
        **ACME,
        "Big.json": b'{"a": "' + b"x" * 9000 + b'"}',
        "Hole.json": b"{" + bytes(8191) + b"}" + b" " * 300,
        "Noise.json": noise,
        "Deep": {"a": {"b": {"c": {"Last.json": b"{}"}}}},
        "Empty": {},
        "cover.png": b"\x89PNG",
    }
    image = _orca(
        tmp_path,
        {"resources": {"profiles": profiles}},
        compression=compression,
        extended=extended,
        fragments=fragments,
        packed_metadata=packed_metadata,
    )
    target = tmp_path / "copy"
    count = appimage.copy_profiles(image, target)
    wanted = {name: data for name, data in _flatten(profiles).items() if name.endswith(".json")}
    found = {
        path.relative_to(target).as_posix(): path.read_bytes()
        for path in target.rglob("*")
        if path.is_file()
    }
    assert count == len(wanted)
    assert found == wanted


def test_a_fresh_orca_appimage_offers_the_printers_of_its_maker(
    tmp_path: Path, nothing_runs: None
) -> None:
    """Nie gestartet, kein ``system/`` — trotzdem die Drucker des Herstellers.

    Vorher fand Solidon über einem AppImage keinen Bestand, bis der Slicer
    einmal gelaufen war (RM-549).
    """
    image = _orca(tmp_path)
    assert not (Path(sp.config_base(image)) / "OrcaSlicer").exists()

    found = sp.discover_printers(image, "orca")

    assert [printer.title for printer in found] == ["Acme One 0.4 nozzle"]
    assert found[0].build_volume == pytest.approx((220, 220, 250))
    root = sp.install_root(image)
    assert root is not None and root.is_relative_to(appimage._cache_root())
    names = {profile.name for profile in sp.find_profiles(image, "orca")}
    assert names == {"Acme One 0.4 nozzle", "0.20mm Standard @Acme"}


def test_the_copy_is_made_once_per_version_and_cleared_with_the_appimage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[Path] = []
    original = appimage.copy_profiles

    def counted(image: Path, target: Path) -> int:
        reads.append(image)
        return original(image, target)

    monkeypatch.setattr(appimage, "copy_profiles", counted)
    image = _orca(tmp_path)
    first = appimage.profiles(image)
    assert first is not None
    # Ein zweiter Solidon, oder dieser nach einem Neustart: die Marke genügt.
    monkeypatch.setattr(appimage, "_copies", {})
    assert appimage.profiles(image) == first
    assert reads == [image]

    # Ein Update unter neuem Namen: eigene Kopie, die alte geht mit ihrer Datei.
    newer = image.with_name("OrcaSlicer_Linux_AppImage_Ubuntu2404_V2.4.3.AppImage")
    image.rename(newer)
    second = appimage.profiles(newer)
    assert second is not None and second != first
    assert not first.parent.exists()

    # Dieselbe Datei in neuer Fassung ersetzt ihre Kopie.
    appimage_file(newer, {"resources": {"profiles": {"Other.json": b"{}"}}})
    os.utime(newer, ns=(1, 1))
    third = appimage.profiles(newer)
    assert third == second
    assert third is not None
    assert [path.name for path in third.rglob("*.json")] == ["Other.json"]
    assert reads == [image, newer, newer]


def test_a_cleared_cache_is_read_again(tmp_path: Path) -> None:
    """Den Nutzer-Cache darf jeder leeren; die nächste Frage legt die Kopie neu an."""
    image = _orca(tmp_path)
    first = appimage.profiles(image)
    assert first is not None
    shutil.rmtree(appimage._cache_root())
    again = appimage.profiles(image)
    assert again is not None and (again / "Acme.json").is_file()


def test_the_window_thread_never_waits_for_the_profile_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Im Fensterfaden gilt nur, was schon abgelegt ist; die Erhebung legt es an."""
    image = _orca(tmp_path)
    monkeypatch.setattr(cura_linux, "_never_waits", None)
    cura_linux.never_wait_in(threading.current_thread())
    assert sp.install_root(image) is None
    assert not appimage._cache_root().exists()

    worker = threading.Thread(target=sp.install_root, args=(image,))
    worker.start()
    worker.join(60.0)

    monkeypatch.setattr(appimage, "_copies", {})
    root = sp.install_root(image)
    assert root is not None and (root / "Acme.json").is_file()


def _not_elf(path: Path) -> None:
    path.write_bytes(b"#!/bin/sh\n" + bytes(200))


def _type_one(path: Path) -> None:
    data = bytearray(path.read_bytes())
    data[10] = 1
    path.write_bytes(bytes(data))


def _cut(path: Path) -> None:
    data = path.read_bytes()
    path.write_bytes(data[: len(data) * 2 // 3])


def _lzo(path: Path) -> None:
    data = bytearray(path.read_bytes())
    struct.pack_into("<H", data, 128 + 20, 3)
    path.write_bytes(bytes(data))


def _scrambled(path: Path) -> None:
    data = bytearray(path.read_bytes())
    # Die Verweise im Superblock: Inode-, Verzeichnis- und Fragmenttabelle.
    for at in (64, 72, 80):
        struct.pack_into("<Q", data, 128 + at, 0x7FFFFFFF)
    path.write_bytes(bytes(data))


@pytest.mark.parametrize(
    "damage",
    [_not_elf, _type_one, _cut, _lzo, _scrambled],
    ids=["not-elf", "type-1", "truncated", "lzo", "scrambled"],
)
def test_an_unreadable_appimage_leaves_the_list_empty_without_failing(
    tmp_path: Path, damage: Callable[[Path], None], nothing_runs: None
) -> None:
    """Kein Absturz, kein Start, keine halbe Kopie — und der erste Start hilft.

    Ohne Bestand sagt der Druckdialog, was hilft: den Slicer einmal öffnen
    (``_profiles_found``). Danach liest Solidon ``system/`` wie bisher.
    """
    image = _orca(tmp_path)
    damage(image)

    assert sp.install_root(image) is None
    assert sp.discover_printers(image, "orca") == ()
    leftovers = list(appimage._cache_root().glob("*")) if appimage._cache_root().exists() else []
    assert leftovers == []

    folder = Path(sp.config_base(image)) / "OrcaSlicer"
    (folder / "user" / "default").mkdir(parents=True)
    for name, data in _flatten(ACME).items():
        (folder / "system" / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / "system" / name).write_bytes(data)
    discover.forget_cache()
    assert [printer.title for printer in sp.discover_printers(image, "orca")] == [
        "Acme One 0.4 nozzle"
    ]


@pytest.mark.parametrize("name", ["..", ".", "a/b.json", "a\\..\\b.json"])
def test_a_name_that_leaves_its_folder_is_a_damaged_image(tmp_path: Path, name: str) -> None:
    image = _orca(tmp_path, {"resources": {"profiles": {**ACME, name: b"{}"}}})
    with pytest.raises(appimage.UnreadableImageError):
        appimage.copy_profiles(image, tmp_path / "copy")
    assert not (tmp_path / "b.json").exists()


@pytest.mark.parametrize("compression", ["gzip", "xz", "zstd"])
def test_a_block_never_unpacks_beyond_its_size(compression: str) -> None:
    """Ein Block, der sich größer entpackt als erlaubt, ist beschädigt — nicht teuer."""
    kind, pack = _COMPRESSORS[compression]
    unpack = appimage._decompressor(kind)
    assert unpack(pack(b"x" * 4096), 4096) == b"x" * 4096
    with pytest.raises(appimage.UnreadableImageError):
        unpack(pack(bytes(1 << 24)), 4096)


def test_only_the_orca_family_is_read_from_its_image(tmp_path: Path, nothing_runs: None) -> None:
    """PrusaSlicer liest Bündel (``.ini``), nicht diesen Bestand; ein solches
    AppImage bleibt, wie es war."""
    image = appimage_file(tmp_path / "PrusaSlicer-2.8.1+linux-x64.AppImage", AROUND)
    assert sp.install_root(image) is None
    assert not appimage._cache_root().exists()
