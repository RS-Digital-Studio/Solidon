"""Beständige Kopien aus AppImages, ohne sie zu starten (Regel 11) — für Cura und die Orca-Familie.

Was Solidon von einem Slicer als AppImage braucht, liegt in dessen Abbild:
Curas Drucker (:mod:`cura_linux`, RM-599) und der Herstellerbestand der
Orca-Familie, den der Slicer erst beim ersten Start nach
``<Konfiguration>/<Programm>/system`` legt (RM-549). :class:`ImageCopies`
liest es einmal je Fassung über :mod:`squashfs` und legt es im Nutzer-Cache
ab, für beide gleich: Marke, Merker, Absage bis *Neu suchen*, Austausch über
einen Zwischenordner, Räumen verschwundener AppImages und abgebrochener
Kopien, und der Fensterfaden wartet nie (:func:`never_wait_in`). Jeder
Slicer bringt nur mit, was er aus dem Abbild liest. :func:`profiles` ist der
Orca-Bestand.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from app.core import discover
from app.core.export import squashfs
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_cache_dir

_log = get_logger(__name__)

#: Die Marke einer abgelegten Kopie: Quelle, Stand, Fassung des Kopierers und
#: was der Slicer dazu festhält.
STAMP: Final = "stamp.json"

#: Ab wann ein Zwischenordner ohne Marke als Rest einer abgebrochenen Kopie gilt.
#: Eine Kopie dauert Sekunden (am Runner 3,3 s); eine Stunde lässt jedem
#: langsamen Rechner Luft.
STALE_SECONDS: Final = 3600.0

#: Der Name eines Zwischenordners: die Kennung (16 Hex-Zeichen aus
#: ``ImageCopies._folder``), Bindestrich und die acht Zeichen, die
#: ``tempfile.mkdtemp`` anhängt (``_RandomNameSequence``: Kleinbuchstaben,
#: Ziffern, Unterstrich). Nur diese Form wird geräumt; ein fremder Ordner bleibt.
UNFINISHED: Final = re.compile(r"[0-9a-f]{16}-[a-z0-9_]{8}")

#: Wie oft der fertige Zwischenordner an seinen Platz gebracht wird (:func:`_rename`).
RENAME_ATTEMPTS: Final = 5

#: Die Fassung des Orca-Kopierers. Eine neue verwirft ältere Kopien.
PROFILE_COPY_VERSION: Final = 1

#: Wo im Abbild ein Slicer der Orca-Familie seinen Bestand trägt, in dieser
#: Reihenfolge gefragt. Gemessen an Orca 2.4.2, Bambu Studio 2.8.2,
#: ElegooSlicer 1.5.3.5 und Creality Print 7.3.0: alle unter ``resources``.
PROFILE_PLACES: Final = (PurePosixPath("resources/profiles"),)

#: Der Faden, der nie auf eine Kopie wartet (:func:`never_wait_in`).
_never_waits: threading.Thread | None = None


def never_wait_in(thread: threading.Thread | None) -> None:
    """Dieser Faden wartet nie auf eine Kopie aus einem AppImage — die
    Oberfläche nennt ihren Fensterfaden.

    Dort antwortet :meth:`ImageCopies.kept` nur mit dem, was schon feststeht;
    die Kopie legen Arbeiter an (Druckdialog, Druckererhebung, Filamentsuche).
    Ohne Angabe wartet jeder Faden, und die Kommandozeile kopiert selbst.
    """
    global _never_waits
    _never_waits = thread


def may_wait() -> bool:
    """Darf dieser Faden auf eine Kopie aus einem AppImage warten?"""
    return threading.current_thread() is not _never_waits


#: Eine Fassung eines AppImage: Pfad, Änderungszeit, Größe.
Key = tuple[str, int, int]


def _key(appimage: Path) -> Key | None:
    try:
        info = appimage.stat()
    except OSError:
        return None
    return (str(appimage), info.st_mtime_ns, info.st_size)


def _read_stamp(folder: Path) -> dict[str, object] | None:
    try:
        stamp = json.loads((folder / STAMP).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    return stamp if isinstance(stamp, dict) else None


@dataclass(frozen=True, slots=True)
class Kept:
    """Eine abgelegte Kopie: der Ordner, den der Slicer liest, und ihre Marke."""

    folder: Path
    stamp: Mapping[str, object]


class ImageCopies:
    """Die Kopien eines Slicers aus seinen AppImages, je Fassung eine.

    ``fill`` liest aus dem Abbild in einen frischen Ordner und gibt zurück,
    was zusätzlich in die Marke gehört — ``None``, wenn das Abbild nichts
    Brauchbares trägt. Ein unlesbares Abbild meldet es mit
    :class:`squashfs.UnreadableImageError`. Gelesen wird danach ``inner``
    darunter.
    """

    def __init__(
        self,
        name: str,
        inner: PurePosixPath,
        version: int,
        fill: Callable[[Path, Path], Mapping[str, object] | None],
        what: str,
    ) -> None:
        self.name = name
        self.inner = inner
        self.version = version
        self.what = what
        self._fill = fill
        #: Was über eine Fassung schon feststeht.
        self._kept: dict[Key, Kept] = {}
        #: Fassungen, deren Kopie scheiterte, mit dem Stand der Suche
        #: (:func:`discover.cache_generation`): *Neu suchen* versucht es wieder.
        self._failed: dict[Key, int] = {}
        self._building = threading.Lock()

    def root(self) -> Path:
        """Der Ordner im Nutzer-Cache, unter dem die Kopien liegen."""
        return user_cache_dir() / self.name

    def kept(self, appimage: Path) -> Kept | None:
        """Die Kopie dieser Fassung, oder ``None``.

        Einmal je Fassung (Pfad, Änderungszeit, Größe) aus dem Abbild gelesen;
        danach liest jede Frage die Kopie, ein neues AppImage ersetzt sie.
        Den Nutzer-Cache darf jeder jederzeit leeren (``paths``, §38):
        Fehlt der Ordner, wird neu gelesen. Scheitert es, bleibt es für diese
        Fassung beim Nein, bis :func:`discover.forget_cache` neu suchen lässt.
        Im Faden aus :func:`never_wait_in` antwortet es nur mit dem, was schon
        feststeht, und nimmt keine Sperre.
        """
        key = _key(appimage)
        if key is None:
            return None
        found = self._known(appimage, key)
        if found is not None or not may_wait():
            return found
        with self._building:
            found = self._known(appimage, key)
            if found is None and self._failed.get(key) != discover.cache_generation():
                found = self._copy(appimage, key)
                if found is None:
                    self._failed[key] = discover.cache_generation()
                else:
                    self._failed.pop(key, None)
                    self._kept[key] = found
        return found

    def known(self, appimage: Path) -> Kept | None:
        """Die Kopie dieser Fassung, wenn sie schon da ist — gelesen wird nie."""
        key = _key(appimage)
        return None if key is None else self._known(appimage, key)

    def _known(self, appimage: Path, key: Key) -> Kept | None:
        found = self._kept.get(key)
        if found is not None and found.folder.is_dir():
            return found
        self._kept.pop(key, None)
        found = self._stamped(appimage, key)
        if found is not None:
            self._kept[key] = found
        return found

    def _folder(self, appimage: Path) -> Path:
        digest = hashlib.sha256(str(appimage).encode("utf-8")).hexdigest()[:16]
        return self.root() / digest

    def _stamped(self, appimage: Path, key: Key) -> Kept | None:
        """Die abgelegte Kopie, wenn ihre Marke zu dieser Fassung passt."""
        folder = self._folder(appimage)
        stamp = _read_stamp(folder)
        if stamp is None or [
            stamp.get("source"),
            stamp.get("mtime_ns"),
            stamp.get("size"),
            stamp.get("version"),
        ] != [*key, self.version]:
            return None
        inner = folder.joinpath(*self.inner.parts)
        return Kept(inner, stamp) if inner.is_dir() else None

    def _copy(self, appimage: Path, key: Key) -> Kept | None:
        """Aus dem Abbild in einen Zwischenordner lesen und ihn erst vollständig
        an seinen Platz bringen. Was dabei abbricht — auch unerwartet —,
        hinterlässt keinen Zwischenordner."""
        folder = self._folder(appimage)
        started = time.monotonic()
        try:
            fresh = Path(tempfile.mkdtemp(prefix=f"{folder.name}-", dir=ensure_dir(folder.parent)))
        except OSError as problem:
            _log.warning("cannot keep the %s of %s: %s", self.what, appimage.name, problem)
            return None
        extra: Mapping[str, object] | None = None
        stamp: dict[str, object] | None = None
        try:
            extra = self._fill(appimage, fresh)
            if extra is not None:
                fresh.joinpath(*self.inner.parts).mkdir(parents=True, exist_ok=True)
                marked = {
                    **extra,
                    "source": key[0],
                    "mtime_ns": key[1],
                    "size": key[2],
                    "version": self.version,
                }
                (fresh / STAMP).write_text(json.dumps(marked), encoding="utf-8")
                stamp = marked
        except (OSError, squashfs.UnreadableImageError) as problem:
            _log.warning("cannot read the %s inside %s: %s", self.what, appimage.name, problem)
        finally:
            if stamp is None:
                shutil.rmtree(fresh, ignore_errors=True)
        if extra is None or stamp is None:
            return None
        try:
            if folder.exists():
                shutil.rmtree(folder)
            _rename(fresh, folder)
        except OSError as problem:
            shutil.rmtree(fresh, ignore_errors=True)
            # Ein zweiter Solidon hat dieselbe Fassung vielleicht schon abgelegt.
            found = self._stamped(appimage, key)
            if found is None:
                _log.warning(
                    "cannot replace the %s of %s at %s: %s",
                    self.what,
                    appimage.name,
                    folder,
                    problem,
                )
            return found
        _log.info(
            "kept the %s of %s in %.1f s (%s)",
            self.what,
            appimage.name,
            time.monotonic() - started,
            ", ".join(f"{name} {value}" for name, value in sorted(extra.items())),
        )
        self._clear_vanished(folder)
        return Kept(folder.joinpath(*self.inner.parts), stamp)

    def _clear_vanished(self, keep: Path) -> None:
        """Kopien von AppImages räumen, die es nicht mehr gibt — ein Update trägt
        die Version im Dateinamen, und eine Kopie wiegt bis zu einigen zehn MB.

        Dazu die Zwischenordner abgebrochener Kopien (:data:`UNFINISHED`, ohne
        Marke), sobald sie älter als :data:`STALE_SECONDS` sind; eine jüngere
        kann gerade ein zweiter Solidon füllen. Was geräumt ist, verlässt auch
        den Merker — kommt das AppImage zurück (ein Stick), wird neu kopiert.
        """
        try:
            siblings = [
                entry for entry in self.root().iterdir() if entry.is_dir() and entry != keep
            ]
        except OSError:
            return
        for sibling in siblings:
            stamp = _read_stamp(sibling)
            source = stamp.get("source") if stamp is not None else None
            if stamp is None:
                if not UNFINISHED.fullmatch(sibling.name) or not _older_than(sibling):
                    continue
            elif not isinstance(source, str) or Path(source).exists():
                continue
            try:
                shutil.rmtree(sibling)
            except OSError as problem:
                _log.warning("cannot clear the old %s at %s: %s", self.what, sibling, problem)
                continue
            _log.info("cleared the %s at %s (%s)", self.what, sibling, source or "unfinished copy")
            for key, found in list(self._kept.items()):
                if found.folder.is_relative_to(sibling):
                    del self._kept[key]


def _rename(fresh: Path, folder: Path) -> None:
    """``fresh`` wird ``folder``. Unter Windows hält ein Virenscanner frisch
    geschriebene Dateien kurz offen, und der Ordner darüber lässt sich so lange
    nicht umbenennen (``WinError 5``, gemessen an der Testsuite); ein paar
    Versuche im Abstand von Zehntelsekunden genügen."""
    for attempt in range(RENAME_ATTEMPTS):
        try:
            fresh.rename(folder)
            return
        except PermissionError:
            if attempt == RENAME_ATTEMPTS - 1:
                raise
            time.sleep(0.1)


def _older_than(folder: Path) -> bool:
    try:
        return time.time() - folder.stat().st_mtime > STALE_SECONDS
    except OSError:
        return False


# --- Der Orca-Bestand ----------------------------------------------------------------


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


def _fill_profiles(appimage: Path, fresh: Path) -> dict[str, object]:
    return {"profiles": copy_profiles(appimage, fresh / "profiles")}


#: Die Kopien des Orca-Bestands.
PROFILE_COPIES: Final = ImageCopies(
    "appimage-profiles", PurePosixPath("profiles"), PROFILE_COPY_VERSION, _fill_profiles, "profiles"
)


def profiles(appimage: Path) -> Path | None:
    """``resources/profiles`` eines AppImage der Orca-Familie als beständige
    Kopie (:meth:`ImageCopies.kept`), oder ``None``.

    ``None`` heißt: im Fensterfaden noch nicht kopiert, oder das Abbild ist
    unlesbar. Dann gilt, was der Slicer nach seinem ersten Start unter
    ``system/`` ablegt (``slicer_profiles.find_profiles``).
    """
    found = PROFILE_COPIES.kept(appimage)
    return found.folder if found is not None else None
