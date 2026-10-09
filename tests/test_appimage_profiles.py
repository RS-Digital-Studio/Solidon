"""Der Herstellerbestand eines AppImage der Orca-Familie, gelesen ohne Start (RM-549).

Ein frisch geladenes AppImage trägt seine Profile nur im eingebetteten
SquashFS; erst sein erster Start legte sie nach ``system/``. Solidon liest das
Abbild als Datei (``app.core.export.appimage``) — gestartet wird nichts
(Regel 11).

Die Abbilder hier baut ``tests.squashfs_fakes.appimage_file`` nach dem
SquashFS-4.0-Aufbau; dazu der Leser selbst (``squashfs``: Verknüpfungen,
Entpackgrenze).
Dass der Leser auch echte Abbilder liest, belegen zwei Dinge außerhalb dieser
Datei: ``test_real_slicers.py`` an den installierten AppImages am Linux-Runner,
und der Bytevergleich gegen 7-Zip an Orca 2.4.2, Bambu Studio 2.8.2,
ElegooSlicer 1.5.3.5 und Creality Print 7.3.0 (alle 34 500 Profile gleich).
"""

from __future__ import annotations

import json
import os
import random
import shutil
import struct
import subprocess
import threading
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from app.core import discover
from app.core.export import appimage, cura_linux, squashfs
from app.core.export import slicer_profiles as sp
from tests.squashfs_fakes import COMPRESSORS, IMAGE_AT, Link, Tree, appimage_file


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
    struct.pack_into("<H", data, IMAGE_AT + 20, 3)
    path.write_bytes(bytes(data))


def _scrambled(path: Path) -> None:
    data = bytearray(path.read_bytes())
    # Die Verweise im Superblock: Inode-, Verzeichnis- und Fragmenttabelle.
    for at in (64, 72, 80):
        struct.pack_into("<Q", data, IMAGE_AT + at, 0x7FFFFFFF)
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
    with pytest.raises(squashfs.UnreadableImageError):
        appimage.copy_profiles(image, tmp_path / "copy")
    assert not (tmp_path / "b.json").exists()


@pytest.mark.parametrize("compression", ["gzip", "xz", "zstd"])
def test_a_block_never_unpacks_beyond_its_size(compression: str) -> None:
    """Ein Block, der sich größer entpackt als erlaubt, ist beschädigt — nicht teuer."""
    kind, pack = COMPRESSORS[compression]
    unpack = squashfs._decompressor(kind)
    assert unpack(pack(b"x" * 4096), 4096) == b"x" * 4096
    with pytest.raises(squashfs.UnreadableImageError):
        unpack(pack(bytes(1 << 24)), 4096)


def test_only_the_orca_family_is_read_from_its_image(tmp_path: Path, nothing_runs: None) -> None:
    """PrusaSlicer liest Bündel (``.ini``), nicht diesen Bestand; ein solches
    AppImage bleibt, wie es war."""
    image = appimage_file(tmp_path / "PrusaSlicer-2.8.1+linux-x64.AppImage", AROUND)
    assert sp.install_root(image) is None
    assert not appimage._cache_root().exists()


#: Ein AppDir mit Verknüpfungen, wie Curas: der Lader in ``lib64`` zeigt nach
#: ``lib/x86_64-linux-gnu``.
LINKED: Tree = {
    "runtime": {
        "compat": {
            "lib": {"x86_64-linux-gnu": {"ld-linux-x86-64.so.2": b"ELF"}},
            "lib64": {"ld-linux-x86-64.so.2": Link("../lib/x86_64-linux-gnu/ld-linux-x86-64.so.2")},
        }
    },
    "chain": Link("runtime/compat/lib64"),
    "host": Link("/usr/lib/ld-linux-x86-64.so.2"),
    "outside": Link("../../etc/passwd"),
    "loop": Link("loop"),
}


@pytest.mark.parametrize("extended", [False, True], ids=["basic", "extended"])
def test_links_are_followed_inside_the_image_only(tmp_path: Path, extended: bool) -> None:
    """Relativ und verkettet gefolgt; ein absolutes Ziel oder eines über die
    Wurzel hinaus zeigte auf den Rechner und gilt als nicht vorhanden; eine
    Schleife ist ein beschädigtes Abbild."""
    image_path = appimage_file(tmp_path / "Cura.AppImage", LINKED, extended=extended)
    with image_path.open("rb") as handle:
        image = squashfs.SquashImage.of(handle)
        loader = PurePosixPath("runtime/compat/lib64/ld-linux-x86-64.so.2")
        assert image.is_file(loader)
        assert image.is_file(PurePosixPath("chain/ld-linux-x86-64.so.2"))
        found = image.resolve(loader)
        assert found is not None and image.read(found) == b"ELF"
        assert not image.is_file(PurePosixPath("host"))
        assert not image.is_file(PurePosixPath("outside"))
        assert image.find(loader) is not None and image.find(loader).kind == 3
        with pytest.raises(squashfs.UnreadableImageError):
            image.resolve(PurePosixPath("loop"))


def test_a_copy_leaves_links_behind(tmp_path: Path) -> None:
    """Kopiert werden Dateien; eine Verknüpfung im Bestand führte sonst hinaus."""
    image_path = appimage_file(tmp_path / "x.AppImage", {"top": {"a.json": b"{}", **LINKED}})
    with image_path.open("rb") as handle:
        image = squashfs.SquashImage.of(handle)
        top = image.find(PurePosixPath("top"))
        assert top is not None
        count = squashfs.copy_folder(image, top, tmp_path / "copy")
    found = sorted(
        p.relative_to(tmp_path / "copy").as_posix()
        for p in (tmp_path / "copy").rglob("*")
        if p.is_file()
    )
    assert count == 2
    assert found == ["a.json", "runtime/compat/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2"]
