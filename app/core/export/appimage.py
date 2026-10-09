"""Der Herstellerbestand eines AppImage der Orca-Familie, ohne Start (RM-549, Regel 11).

Die Orca-Familie trägt ihren Bestand im Abbild unter ``resources/profiles``
und legt ihn erst beim ersten Start nach ``<Konfiguration>/<Programm>/system``
— wer den Slicer nie geöffnet hat, sah in Solidon keinen seiner Drucker.
:func:`profiles` liest ihn über :mod:`squashfs` aus dem Abbild und legt ihn
einmal je Fassung im Nutzer-Cache ab.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import threading
import time
from pathlib import Path, PurePosixPath
from typing import Final

from app.core import discover
from app.core.export import cura_linux, squashfs
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_cache_dir

_log = get_logger(__name__)

#: Die Fassung des Kopierers. Eine neue verwirft ältere Kopien.
COPY_VERSION: Final = 1

#: Wo im Abbild ein Slicer der Orca-Familie seinen Bestand trägt, in dieser
#: Reihenfolge gefragt. Gemessen an Orca 2.4.2, Bambu Studio 2.8.2,
#: ElegooSlicer 1.5.3.5 und Creality Print 7.3.0: alle unter ``resources``.
PROFILE_PLACES: Final = (PurePosixPath("resources/profiles"),)


def copy_profiles(appimage: Path, target: Path) -> int:
    """Die JSON-Profile aus dem Abbild nach ``target`` kopieren; ihre Zahl.

    Gesucht wird an den Stellen aus :data:`PROFILE_PLACES`; ohne Bestand ist
    das Abbild für Solidon unlesbar (:class:`squashfs.UnreadableImageError`).
    """
    with appimage.open("rb") as handle:
        image = squashfs.SquashImage.of(handle)
        top = next(
            (
                found
                for place in PROFILE_PLACES
                if (found := image.find(place)) is not None and found.kind == squashfs.DIRECTORY
            ),
            None,
        )
        if top is None:
            raise squashfs.UnreadableImageError("no resources/profiles in the image")
        count = squashfs.copy_folder(image, top, target, ".json")
        if count == 0:
            raise squashfs.UnreadableImageError("resources/profiles holds no profile")
        return count


# --- Die beständige Kopie ----------------------------------------------------------

#: Was über ein AppImage schon feststeht, je Pfad, Änderungszeit und Größe:
#: der Ordner der Kopie.
_copies: dict[tuple[str, int, int], Path] = {}
#: Fassungen, deren Kopie scheiterte, mit dem Stand der Suche — *Neu suchen*
#: (:func:`discover.forget_cache`) versucht es wieder.
_failed: dict[tuple[str, int, int], int] = {}
_building = threading.Lock()


def _key(appimage: Path) -> tuple[str, int, int] | None:
    try:
        info = appimage.stat()
    except OSError:
        return None
    return (str(appimage), info.st_mtime_ns, info.st_size)


def _cache_root() -> Path:
    return user_cache_dir() / "appimage-profiles"


def _cache_folder(appimage: Path) -> Path:
    digest = hashlib.sha256(str(appimage).encode("utf-8")).hexdigest()[:16]
    return _cache_root() / digest


def _read_stamp(folder: Path) -> dict[str, object] | None:
    try:
        stamp = json.loads((folder / cura_linux.STAMP).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    return stamp if isinstance(stamp, dict) else None


def _stamped(appimage: Path, key: tuple[str, int, int]) -> Path | None:
    folder = _cache_folder(appimage)
    stamp = _read_stamp(folder)
    if stamp is None or [
        stamp.get("source"),
        stamp.get("mtime_ns"),
        stamp.get("size"),
        stamp.get("version"),
    ] != [*key, COPY_VERSION]:
        return None
    return folder / "profiles"


def profiles(appimage: Path) -> Path | None:
    """``resources/profiles`` eines AppImage als beständige Kopie, oder ``None``.

    Einmal je Fassung (Pfad, Änderungszeit, Größe) aus dem Abbild gelesen,
    ohne das AppImage zu starten; danach liest jede Frage die Kopie, ein neues
    AppImage ersetzt sie, Kopien verschwundener AppImages werden geräumt.
    Scheitert es, bleibt es beim Nein, bis :func:`discover.forget_cache` neu
    suchen lässt. Im Fensterfaden (:func:`cura_linux.never_wait_in`) antwortet
    es nur mit dem, was schon feststeht.
    """
    key = _key(appimage)
    if key is None:
        return None
    known = _copies.get(key)
    if known is not None and known.is_dir():
        return known
    # Den Nutzer-Cache darf jeder jederzeit leeren (:func:`user_cache_dir`).
    _copies.pop(key, None)
    if not cura_linux.may_wait():
        stamped = _stamped(appimage, key)
        if stamped is not None:
            _copies[key] = stamped
        return stamped
    with _building:
        if key not in _copies and _failed.get(key) != discover.cache_generation():
            kept = _stamped(appimage, key) or _copy(appimage, key)
            if kept is None:
                _failed[key] = discover.cache_generation()
            else:
                _failed.pop(key, None)
                _copies[key] = kept
    return _copies.get(key)


def _copy(appimage: Path, key: tuple[str, int, int]) -> Path | None:
    folder = _cache_folder(appimage)
    started = time.monotonic()
    try:
        fresh = Path(tempfile.mkdtemp(prefix=f"{folder.name}-", dir=ensure_dir(folder.parent)))
    except OSError as problem:
        _log.warning("cannot keep the profiles of %s: %s", appimage.name, problem)
        return None
    try:
        count = copy_profiles(appimage, fresh / "profiles")
        stamp = {"source": key[0], "mtime_ns": key[1], "size": key[2], "version": COPY_VERSION}
        (fresh / cura_linux.STAMP).write_text(json.dumps(stamp), encoding="utf-8")
    except (OSError, squashfs.UnreadableImageError) as problem:
        shutil.rmtree(fresh, ignore_errors=True)
        _log.warning("cannot read the profiles inside %s: %s", appimage.name, problem)
        return None
    try:
        if folder.exists():
            shutil.rmtree(folder)
        fresh.rename(folder)
    except OSError as problem:
        shutil.rmtree(fresh, ignore_errors=True)
        stamped = _stamped(appimage, key)
        if stamped is None:
            _log.warning("cannot replace the profiles of %s: %s", appimage.name, problem)
        return stamped
    _log.info(
        "read %d profiles from %s in %.1f s", count, appimage.name, time.monotonic() - started
    )
    _clear_vanished(folder)
    return folder / "profiles"


def _clear_vanished(keep: Path) -> None:
    """Kopien von AppImages räumen, die es nicht mehr gibt, und Reste
    abgebrochener Kopien, die älter als :data:`cura_linux.STALE_SECONDS` sind."""
    try:
        siblings = [entry for entry in _cache_root().iterdir() if entry.is_dir() and entry != keep]
    except OSError:
        return
    for sibling in siblings:
        stamp = _read_stamp(sibling)
        source = stamp.get("source") if stamp is not None else None
        if stamp is None:
            if not cura_linux.UNFINISHED.fullmatch(sibling.name) or not _older_than(sibling):
                continue
        elif not isinstance(source, str) or Path(source).exists():
            continue
        shutil.rmtree(sibling, ignore_errors=True)
        for key, found in list(_copies.items()):
            if found.is_relative_to(sibling):
                del _copies[key]


def _older_than(folder: Path) -> bool:
    try:
        return time.time() - folder.stat().st_mtime > cura_linux.STALE_SECONDS
    except OSError:
        return False
