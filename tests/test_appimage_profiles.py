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
import time
import tracemalloc
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
    monkeypatch.setattr(appimage.PROFILE_COPIES, "_kept", {})
    monkeypatch.setattr(appimage.PROFILE_COPIES, "_failed", {})
    monkeypatch.setattr(appimage.PROFILE_COPIES, "root", lambda: tmp_path / "cache")
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
    assert root is not None and root.is_relative_to(appimage.PROFILE_COPIES.root())
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
    monkeypatch.setattr(appimage.PROFILE_COPIES, "_kept", {})
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
    shutil.rmtree(appimage.PROFILE_COPIES.root())
    again = appimage.profiles(image)
    assert again is not None and (again / "Acme.json").is_file()


def test_the_window_thread_never_waits_for_the_profile_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Im Fensterfaden gilt nur, was schon abgelegt ist; die Erhebung legt es an.

    Auch während ein Arbeiter gerade kopiert, antwortet der Fensterfaden sofort
    mit „noch nicht“ — er nimmt die Sperre des Kopierers nicht. Die Kopie hier
    dauert zwei Sekunden, gefragt wird mittendrin.
    """
    image = _orca(tmp_path)
    copying = threading.Event()
    original = appimage.copy_profiles

    def slow(source: Path, target: Path) -> int:
        copying.set()
        time.sleep(2.0)
        return original(source, target)

    monkeypatch.setattr(appimage, "copy_profiles", slow)
    monkeypatch.setattr(appimage, "_never_waits", None)
    appimage.never_wait_in(threading.current_thread())
    assert sp.install_root(image) is None
    assert not appimage.PROFILE_COPIES.root().exists()

    worker = threading.Thread(target=sp.install_root, args=(image,))
    worker.start()
    assert copying.wait(10.0), "der Arbeiter hat nicht zu kopieren begonnen"
    started = time.monotonic()
    during = sp.install_root(image)
    waited = time.monotonic() - started
    worker.join(60.0)

    assert during is None
    assert waited < 1.0, f"der Fensterfaden wartete {waited:.1f} s auf den Arbeiter"
    monkeypatch.setattr(appimage.PROFILE_COPIES, "_kept", {})
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
    leftovers = (
        list(appimage.PROFILE_COPIES.root().glob("*"))
        if appimage.PROFILE_COPIES.root().exists()
        else []
    )
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


@pytest.mark.parametrize("kind", [1, 2, 4, 6], ids=["gzip", "lzma", "xz", "zstd"])
def test_whatever_the_unpacker_calls_damaged_is_an_unreadable_image(kind: int) -> None:
    """Jeder Entpacker meldet einen beschädigten Strom mit seiner eigenen
    Ausnahme (``zlib.error``, ``LZMAError``, ``ZstdError``); hinaus geht für
    alle dieselbe."""
    unpack = squashfs._decompressor(kind)
    with pytest.raises(squashfs.UnreadableImageError):
        unpack(b"\x00 kein Strom dieser Kompression", 4096)


def test_an_lzma_stream_gets_no_more_memory_than_a_block_needs() -> None:
    """Der Kopf eines lzma-Stroms nennt die Größe seines Wörterbuchs, bis 4 GiB;
    beschädigt verlangt er sie, bevor ein Byte entpackt ist (§32)."""
    header = b"\x5d" + (0xFFFFFFFF).to_bytes(4, "little") + b"\xff" * 8 + bytes(64)
    with pytest.raises(squashfs.UnreadableImageError, match="limit"):
        squashfs._decompressor(2)(header, 4096)


#: Ein Bestand mit einer Datei aus ganzen Blöcken (``Big.json``): Deren erster
#: Block steht vorn im Datenbereich. Ohne sie steht dort der Block der Reste.
_BLOCKS: Tree = {"resources": {"profiles": {**ACME, "Big.json": b'{"a": "' + b"x" * 9000 + b'"}'}}}


def _damage_first_block(path: Path) -> None:
    """Den Kopf des ersten gepackten Blocks hinter dem Superblock zerstören."""
    data = bytearray(path.read_bytes())
    for at in range(IMAGE_AT + 96, IMAGE_AT + 100):
        data[at] ^= 0xFF
    path.write_bytes(bytes(data))


@pytest.mark.parametrize("compression", ["gzip", "xz", "zstd"])
@pytest.mark.parametrize("block", ["data", "fragment"])
def test_a_damaged_block_keeps_the_own_profiles_and_is_read_once(
    tmp_path: Path, compression: str, block: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein gekipptes Bit in einem gepackten Block ist ein unlesbares Abbild: kein
    Absturz, kein Zwischenordner im Cache, und die eigenen Profile des Kunden
    bleiben in der Liste. Gelesen wird das Abbild einmal je Fassung, nicht bei
    jeder Frage; eine neue Fassung der Datei wird wieder gelesen.

    Vorher entkam bei gzip (Curas Kompression) ``zlib.error``: Die ganze
    Profilliste fiel weg, und jede Frage las das Abbild erneut.
    """
    image = _orca(tmp_path, _BLOCKS if block == "data" else AROUND, compression=compression)
    _damage_first_block(image)
    reads: list[Path] = []
    original = appimage.copy_profiles

    def counted(source: Path, target: Path) -> int:
        reads.append(source)
        return original(source, target)

    monkeypatch.setattr(appimage, "copy_profiles", counted)
    own = Path(sp.config_base(image)) / "OrcaSlicer" / "user" / "default" / "process"
    own.mkdir(parents=True)
    (own / "Meine Feine.json").write_text(
        json.dumps({"name": "Meine Feine", "instantiation": "true", "layer_height": "0.12"}),
        encoding="utf-8",
    )

    with pytest.raises(squashfs.UnreadableImageError):
        original(image, tmp_path / "direkt")
    assert sp.install_root(image) is None
    assert sp.discover_printers(image, "orca") == ()
    assert [profile.name for profile in sp.find_profiles(image, "orca")] == ["Meine Feine"]
    assert reads == [image], "die Absage gilt für diese Fassung"
    root = appimage.PROFILE_COPIES.root()
    assert not root.exists() or not any(root.iterdir()), "kein halber Zwischenordner"

    _orca(tmp_path, AROUND, compression=compression)
    os.utime(image, ns=(1, 1))
    assert sp.install_root(image) is not None, "eine neue Fassung wird wieder gelesen"
    assert reads == [image, image]


def test_a_copy_that_breaks_unexpectedly_leaves_no_half_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch was niemand erwartet, bricht die Kopie ab, ohne einen Zwischenordner
    im Nutzer-Cache liegen zu lassen."""
    image = _orca(tmp_path)

    def broken(source: Path, target: Path) -> int:
        (target / "Acme").mkdir(parents=True)
        (target / "Acme.json").write_bytes(b"{}")
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(appimage, "copy_profiles", broken)
    with pytest.raises(RuntimeError):
        appimage.profiles(image)
    assert list(appimage.PROFILE_COPIES.root().iterdir()) == []


def _many(count: int) -> dict[str, bytes]:
    return {f"Profil {number:04}.json": _json({"n": number}) for number in range(count)}


@pytest.mark.parametrize("packed_metadata", [True, False], ids=["packed", "raw"])
@pytest.mark.parametrize("extended", [False, True], ids=["basic", "extended"])
def test_inodes_and_listings_run_across_metadata_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, packed_metadata: bool, extended: bool
) -> None:
    """Ein echter Bestand hat tausende Dateien: Inode-Tabelle und Verzeichnis
    laufen über die Grenze eines Metadatenblocks (8 KiB) hinaus, und ein Eintrag
    beginnt im einen Block und endet im nächsten. Jede Datei kommt trotzdem
    byte-gleich heraus."""
    profiles = _many(600)
    image_path = _orca(
        tmp_path,
        {"resources": {"profiles": profiles}},
        packed_metadata=packed_metadata,
        extended=extended,
    )
    seen: list[int] = []
    original = squashfs.SquashImage._metadata_block

    def spy(self: squashfs.SquashImage, position: int) -> tuple[bytes, int]:
        seen.append(position)
        return original(self, position)

    monkeypatch.setattr(squashfs.SquashImage, "_metadata_block", spy)
    with image_path.open("rb") as handle:
        image = squashfs.SquashImage.of(handle)
        inodes, listings = image._inode_table, image._directory_table
        top = image.find(PurePosixPath("resources/profiles"))
        assert top is not None
        count = squashfs.copy_folder(image, top, tmp_path / "copy", ".json")

    assert len({at for at in seen if inodes <= at < listings}) >= 2, "Inodes in einem Block"
    assert len({at for at in seen if at >= listings}) >= 2, "Verzeichnis in einem Block"
    assert count == len(profiles)
    for name, data in profiles.items():
        assert (tmp_path / "copy" / name).read_bytes() == data


def _deep(depth: int) -> Tree:
    tree: Tree = {"Last.json": b"{}"}
    for level in range(depth):
        tree = {f"Ebene{level}": tree}
    return tree


@pytest.mark.parametrize(
    ("limit", "value", "profiles"),
    [
        ("MAX_DEPTH", 3, _deep(5)),
        ("MAX_COPIED_FILES", 3, ACME),
        ("MAX_COPIED_BYTES", 100, ACME),
        ("MAX_LISTING", 16, ACME),
    ],
    ids=["depth", "files", "bytes", "listing"],
)
def test_every_promised_limit_makes_the_image_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit: str,
    value: int,
    profiles: Tree,
    nothing_runs: None,
) -> None:
    """Tiefe, Dateizahl, Bytezahl und Verzeichnisgröße sind begrenzt (Modulkopf,
    ``druckerwahl.md``). Wer darüber liegt, ist ein unlesbares Abbild — ohne
    Kopie und ohne Zwischenordner. Gezeigt mit herabgesetzter Grenze."""
    image = _orca(tmp_path, {"resources": {"profiles": profiles}})
    assert appimage.copy_profiles(image, tmp_path / "vorher") > 0
    monkeypatch.setattr(squashfs, limit, value)

    with pytest.raises(squashfs.UnreadableImageError):
        appimage.copy_profiles(image, tmp_path / "nachher")
    assert appimage.profiles(image) is None
    assert list(appimage.PROFILE_COPIES.root().iterdir()) == []


def test_the_byte_limit_holds_before_a_file_is_unpacked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Lücke kostet im Abbild vier Byte, entpackt einen ganzen Block: Ein
    Abbild von wenigen hundert Byte kann eine Datei von Gigabytes angeben. Die
    Grenze greift an der angegebenen Größe, bevor Speicher dafür belegt wird
    (§32)."""
    hole = 16 << 20
    image = _orca(
        tmp_path, {"resources": {"profiles": {"Hole.json": bytes(hole)}}}, block_size=1 << 20
    )
    assert image.stat().st_size < 4096
    monkeypatch.setattr(squashfs, "MAX_COPIED_BYTES", 1 << 20)

    tracemalloc.start()
    try:
        with pytest.raises(squashfs.UnreadableImageError):
            appimage.copy_profiles(image, tmp_path / "copy")
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < hole // 4, f"{peak} Byte belegt für eine Grenze von 1 MiB"


def test_the_rest_of_an_aborted_profile_copy_is_cleared_once_it_is_old(tmp_path: Path) -> None:
    """Wie bei Curas Druckern (dieselbe Verwaltung, ``ImageCopies``): Ein
    Zwischenordner ohne Marke geht erst, wenn er älter ist als
    :data:`appimage.STALE_SECONDS`; ein fremder Ordner bleibt."""
    root = appimage.PROFILE_COPIES.root()
    old = root / "0123456789abcdef-a1b2_c3d"
    young = root / "fedcba9876543210-x9y8z7w6"
    others = [root / "fremd", root / "0123456789abcdef-Abgebrochen"]
    for folder in (old, young, *others):
        (folder / "profiles").mkdir(parents=True)
    past = time.time() - appimage.STALE_SECONDS - 60
    for folder in (old, *others):
        os.utime(folder, (past, past))

    assert appimage.profiles(_orca(tmp_path)) is not None

    assert not old.exists()
    assert young.is_dir()
    assert all(folder.is_dir() for folder in others), "fremde Ordner bleiben"


@pytest.mark.parametrize("family", ["orca", "cura"])
def test_after_a_cleared_cache_both_families_read_their_image_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, family: str
) -> None:
    """Den Nutzer-Cache darf jeder leeren, auch während Solidon läuft
    (Aufräumprogramm). Die nächste Frage liest das Abbild neu, für Cura wie für
    die Orca-Familie — vorher behielt Curas Merker den gelöschten Ordner, und
    ihre Drucker fehlten bis zum Neustart, auch nach *Neu suchen*."""
    from tests.cura_fakes import appimage_cura

    copies: list[Path] = []
    mounts: list[Path] = []
    if family == "cura":
        monkeypatch.setattr(cura_linux.PRINTER_COPIES, "_kept", {})
        monkeypatch.setattr(cura_linux.PRINTER_COPIES, "_failed", {})
        monkeypatch.setattr(cura_linux.PRINTER_COPIES, "root", lambda: tmp_path / "cura-cache")
        image, _point = appimage_cura(tmp_path, monkeypatch, mounts, copies=copies)
        store, wanted = cura_linux.PRINTER_COPIES, "Creality K1 Max"
    else:
        image = _orca(tmp_path)
        store, wanted = appimage.PROFILE_COPIES, "Acme One 0.4 nozzle"

    def names() -> set[str]:
        return {profile.name for profile in sp.find_profiles(image, family, ("machine",))}

    assert wanted in names()
    shutil.rmtree(store.root())
    assert wanted in names(), "nach dem Leeren sofort wieder da"
    shutil.rmtree(store.root())
    discover.forget_cache()
    assert wanted in names(), "und nach Neu suchen ebenso"
    if family == "cura":
        assert len(copies) == 3 and not mounts


def test_a_raw_block_longer_than_a_block_is_an_unreadable_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SquashFS legt keinen Block größer als die Blockgröße ab. Ein Blockwort,
    das einen längeren rohen Block angibt, machte die Datei länger als sie ist,
    und eine folgende Lücke rechnete mit negativer Länge (``ValueError``) — die
    ganze Profilliste fiel weg, und jede Frage las das Abbild neu."""
    noise = random.Random(1).randbytes
    profiles: Tree = {**ACME, "Hole.json": noise(4096) + bytes(4096), "Noise.json": noise(16384)}
    image = _orca(tmp_path, {"resources": {"profiles": profiles}}, fragments=False)
    data = bytearray(image.read_bytes())
    (inodes,) = struct.unpack_from("<Q", data, IMAGE_AT + 64)
    (listings,) = struct.unpack_from("<Q", data, IMAGE_AT + 72)
    table = bytes(data[IMAGE_AT + inodes : IMAGE_AT + listings])
    words = struct.pack("<II", 4096 | 1 << 24, 0)
    assert table.count(words) == 1, "das Blockwort von Hole.json"
    at = IMAGE_AT + inodes + table.index(words)
    struct.pack_into("<I", data, at, 3 * 4096 | 1 << 24)
    image.write_bytes(bytes(data))
    reads: list[Path] = []
    original = appimage.copy_profiles

    def counted(source: Path, target: Path) -> int:
        reads.append(source)
        return original(source, target)

    monkeypatch.setattr(appimage, "copy_profiles", counted)

    with pytest.raises(squashfs.UnreadableImageError):
        original(image, tmp_path / "direkt")
    assert sp.install_root(image) is None
    assert sp.install_root(image) is None
    assert reads == [image], "die Absage gilt für diese Fassung"


def _refused_renames(monkeypatch: pytest.MonkeyPatch, refusals: int) -> list[Path]:
    """``Path.rename`` verweigert die ersten ``refusals`` Versuche wie ein
    Virenscanner unter Windows (``WinError 5``); gewartet wird nicht."""
    attempts: list[Path] = []
    original = Path.rename

    def rename(self: Path, target: Path) -> Path:
        attempts.append(self)
        if len(attempts) <= refusals:
            raise PermissionError(13, "Zugriff verweigert", str(self))
        return original(self, target)

    monkeypatch.setattr(Path, "rename", rename)
    monkeypatch.setattr(appimage.time, "sleep", lambda _seconds: None)
    return attempts


def test_a_rename_refused_for_a_moment_is_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hält ein Scanner die frisch geschriebenen Dateien kurz offen, gelingt
    das Umbenennen beim dritten Versuch, und die Kopie ist da."""
    image = _orca(tmp_path)
    attempts = _refused_renames(monkeypatch, 2)

    found = appimage.profiles(image)

    assert found is not None and (found / "Acme.json").is_file()
    assert len(attempts) == 3


def test_a_rename_refused_for_good_gives_up_without_a_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bleibt es verweigert, gibt die Kopie nach :data:`appimage.RENAME_ATTEMPTS`
    Versuchen auf: kein Rest im Cache, und bis *Neu suchen* wird nicht wieder
    gelesen."""
    image = _orca(tmp_path)
    attempts = _refused_renames(monkeypatch, 10**6)
    reads: list[Path] = []
    original = appimage.copy_profiles

    def counted(source: Path, target: Path) -> int:
        reads.append(source)
        return original(source, target)

    monkeypatch.setattr(appimage, "copy_profiles", counted)

    assert appimage.profiles(image) is None
    assert appimage.profiles(image) is None
    assert len(attempts) == appimage.RENAME_ATTEMPTS
    assert reads == [image]
    assert list(appimage.PROFILE_COPIES.root().iterdir()) == []


def test_only_the_orca_family_is_read_from_its_image(tmp_path: Path, nothing_runs: None) -> None:
    """PrusaSlicer liest Bündel (``.ini``), nicht diesen Bestand; ein solches
    AppImage bleibt, wie es war."""
    image = appimage_file(tmp_path / "PrusaSlicer-2.8.1+linux-x64.AppImage", AROUND)
    assert sp.install_root(image) is None
    assert not appimage.PROFILE_COPIES.root().exists()


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
