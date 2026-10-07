"""CuraEngine aus Curas Linux-Paketen starten (§29, RM-521).

Cura für Linux ist ein AppImage aus appimage-builder, und Flathub packt
dasselbe AppDir unter ``/app/cura`` aus. ``CuraEngine`` darin nennt seinen
Lader relativ (``lib64/ld-linux-x86-64.so.2``); der liegt unter
``runtime/compat`` samt Curas eigener glibc und findet seine Bibliotheken nur
über den Pfad aus ``AppRun.env``. Gestartet wird deshalb der Lader, mit
CuraEngine als Argument (Entscheidung Robert, 06.10.2026):

* **Flatpak:** ``flatpak run --command=/app/cura/runtime/compat/<Lader>
  com.ultimaker.cura --library-path <Pfad> /app/cura/CuraEngine slice …``.
  Das Paket gibt ``home``, ``/media`` und ``/run/media`` frei; der
  Arbeitsordner kommt als ``--filesystem`` dazu, weil ein Nutzer-Cache auch
  außerhalb von ``$HOME`` liegen kann.
* **AppImage:** für die Dauer des Laufs eingehängt (``--appimage-mount``),
  dann derselbe Aufruf mit den Pfaden des Einhängepunkts. Läuft Solidon selbst
  in einem Flatpak, sieht es das ``/tmp`` des Rechners nicht; die Laufzeit des
  AppImage beachtet ``TMPDIR``, und der Einhängepunkt kommt unter
  :func:`discover.exchange_dir`, den beide sehen (gemessen am Runner, Lauf
  37504088443).

Findet Solidon Lader, ``AppRun.env`` oder CuraEngine nicht, rechnet es mit
dieser Cura nicht, sondern öffnet die Datei nur in ihrem Fenster
(:data:`WINDOW_ONLY`); den Grund schreibt es ins Protokoll.

Die Drucker einer AppImage-Cura liegen im Abbild. :func:`appimage_resources`
hängt es einmal je Fassung kurz ein und legt die Ordner, die Solidon liest, im
Nutzer-Cache ab — beständig, denn jeder Einhängepunkt heißt anders, und eine
Profilliste darf nicht in einen verschwundenen Ordner zeigen. Der Fensterfaden
wartet darauf nie (:func:`never_wait_in`).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath
from typing import IO, Final

from app.core import discover
from app.core.errors import CHOOSE_SLICER, EXPORT_ONLY, ExternalToolError
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_cache_dir
from app.core.process import (
    process_group_options,
    terminate_process_tree,
    trusted_cwd,
    trusted_environment,
)
from app.core.types import CancelToken
from app.i18n import _

_log = get_logger(__name__)

#: Die Rechenmaschine im AppDir.
ENGINE: Final = "CuraEngine"

#: Die Umgebung, die Curas ``AppRun`` vor dem Start setzt.
ENVIRONMENT: Final = "AppRun.env"

#: Wo Curas eigener Lader samt glibc liegt, relativ zum AppDir.
COMPAT: Final = PurePosixPath("runtime/compat")

#: Der Lader, den ``CuraEngine`` verlangt, wenn ``AppRun.env`` keinen nennt.
DEFAULT_LINKER: Final = "lib64/ld-linux-x86-64.so.2"

#: Wo ein Flatpak seine Installation sieht; das AppDir liegt darunter in dem
#: Ordner, der ``share/cura`` trägt (bei Cura 5.13 ``/app/cura``).
FLATPAK_ROOT: Final = PurePosixPath("/app")

#: Die zwei Bibliothekspfade aus ``AppRun.env``, in dieser Reihenfolge: erst
#: Curas glibc, dann seine übrigen Bibliotheken. Gekürzt fand CuraEngine die
#: ``libstdc++`` des Rechners und scheiterte an ``GLIBC_2.38``.
LIBRARY_VARIABLES: Final = ("APPDIR_LIBC_LIBRARY_PATH", "APPDIR_LIBRARY_PATH")

#: Die Ordner unter ``share/cura/resources``, die Solidon aus Curas Bestand
#: liest (``slicer_profiles``: Drucker, Züge, Düsen, Qualität, Absicht,
#: Material).
RESOURCE_FOLDERS: Final = ("definitions", "extruders", "intent", "materials", "quality", "variants")

#: Wie lange das Einhängen dauern darf. Gemessen: 0,01 s.
MOUNT_SECONDS: Final = 30.0

#: Wie viel von der Fehlerausgabe des Einhängens als Grund mitreist.
REASON_BYTES: Final = 4096

#: Die Marke einer abgelegten Kopie: Quelle, Stand und ob die Rechenmaschine da ist.
STAMP: Final = "stamp.json"

#: Ab wann ein Zwischenordner ohne Marke als Rest einer abgebrochenen Kopie gilt.
#: Eine Kopie dauert Sekunden (am Runner 3,3 s); eine Stunde lässt jedem
#: langsamen Rechner Luft.
STALE_SECONDS: Final = 3600.0

#: Der Name eines Zwischenordners, wie ``_copy_resources`` ihn anlegt: die
#: Kennung (16 Hex-Zeichen aus ``_cache_folder``), Bindestrich und die acht
#: Zeichen, die ``tempfile.mkdtemp`` anhängt (``_RandomNameSequence``:
#: Kleinbuchstaben, Ziffern, Unterstrich). Nur diese Form wird geräumt; ein
#: fremder Ordner bleibt.
UNFINISHED: Final = re.compile(r"[0-9a-f]{16}-[a-z0-9_]{8}")

#: Der Satz für Druckdialog und Absage, wenn Solidon mit dieser Cura nicht
#: rechnen kann. Er nennt keine Ursache (Regel 21): Lader, ``AppRun.env``,
#: CuraEngine oder eine für Solidon unsichtbare Installation — welche es war,
#: steht im Protokoll.
WINDOW_ONLY: Final = _(
    "Mit dieser Cura-Installation kann Solidon nicht selbst slicen. "
    "Öffnen Sie die Datei in Curas Fenster."
)

#: Die Absage, wenn sich das AppImage nicht einhängen ließ.
NOT_MOUNTED: Final = _(
    "Curas AppImage ließ sich nicht einhängen. Prüfen Sie, ob Cura selbst startet, "
    "oder wählen Sie einen anderen Slicer."
)


#: Was :func:`_tell` schon gesagt hat, je Stand der Suche. Der Druckdialog
#: fragt bei jeder Feldänderung; eine Ursache gehört einmal ins Protokoll.
_told: dict[str, int] = {}


def _tell(message: str, *args: object) -> None:
    """Eine Ursache einmal je Stand der Suche protokollieren (``discover.forget_cache``)."""
    text = message % args
    generation = discover.cache_generation()
    if _told.get(text) != generation:
        _told[text] = generation
        _log.info(message, *args)


def is_appimage(executable: Path) -> bool:
    """Ist das ein AppImage? Gefunden werden sie nur an ihrer Endung (``discover``)."""
    return executable.suffix.casefold() == ".appimage"


def read_environment(text: str) -> dict[str, str]:
    """Die Zeilen ``NAME=WERT`` aus ``AppRun.env``, unausgewertet."""
    found: dict[str, str] = {}
    for line in text.splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip():
            found[name.strip()] = value.strip()
    return found


def linker(variables: Mapping[str, str]) -> str:
    """Der Lader relativ zu :data:`COMPAT`.

    ``APPDIR_LIBC_LINKER_PATH`` steht als Python-Menge darin
    (``{'lib64/ld-linux-x86-64.so.2'}``). Ein absoluter Pfad oder einer mit
    ``..`` führte aus dem AppDir hinaus und gilt nicht.
    """
    raw = variables.get("APPDIR_LIBC_LINKER_PATH", "")
    for entry in raw.strip("{}[]() ").split(","):
        name = entry.strip().strip("'\"")
        path = PurePosixPath(name)
        if name and not path.is_absolute() and ".." not in path.parts:
            return name
    return DEFAULT_LINKER


def library_path(variables: Mapping[str, str], appdir: str) -> str:
    """Der Bibliothekspfad für den Lader, mit ``appdir`` statt ``$APPDIR``.

    Einträge mit einer anderen Variable bleiben weg — gefragt vor dem
    Einsetzen, denn ein ``$`` im AppDir selbst ist kein Verweis. Doppelte
    zählen einmal.
    """
    seen: list[str] = []
    for name in LIBRARY_VARIABLES:
        for entry in variables.get(name, "").split(":"):
            if not entry or "$" in entry.replace("${APPDIR}", "").replace("$APPDIR", ""):
                continue
            expanded = entry.replace("${APPDIR}", appdir).replace("$APPDIR", appdir)
            expanded = expanded.rstrip("/") or "/"
            if expanded not in seen:
                seen.append(expanded)
    return ":".join(seen)


def loader_command(here: Path, there: PurePath) -> list[str] | None:
    """Lader, Bibliothekspfad und CuraEngine — oder ``None``, wenn etwas fehlt.

    ``here`` ist das AppDir, wie Solidon es liest; ``there``, wie der Prozess es
    sieht (``/app/cura`` im Flatpak, beim AppImage derselbe Einhängepunkt).
    """
    try:
        variables = read_environment((here / ENVIRONMENT).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as problem:
        _tell("no readable %s below %s: %s", ENVIRONMENT, here, problem)
        return None
    name = linker(variables)
    if not (here / COMPAT / name).is_file() or not (here / ENGINE).is_file():
        _tell("cura below %s has no loader %s or no %s", here, name, ENGINE)
        return None
    libraries = library_path(variables, str(there))
    if not libraries:
        _tell("%s below %s names no library path", ENVIRONMENT, here)
        return None
    return [str(there / COMPAT / name), "--library-path", libraries, str(there / ENGINE)]


def flatpak_appdir(app_id: str) -> tuple[Path, PurePosixPath] | None:
    """Curas AppDir im Flatpak ``app_id``: wie Solidon es liest und wie Cura es sieht.

    Es ist der Ordner unter ``files``, der ``share/cura`` trägt — dieselbe Stelle,
    an der :func:`slicer_profiles.install_root` Curas Bestand findet, denn sie
    fragt hier. Ohne Sicht auf die Installation (eine Freigabe fehlt) sagt es
    das Protokoll.
    """
    files = discover.flatpak_files(app_id)
    if files is None:
        _tell("the installation of %s is not visible from here", app_id)
        return None
    try:
        inner = sorted(entry for entry in files.iterdir() if entry.is_dir())
    except OSError:
        inner = []
    for folder in (files, *inner):
        if (folder / "share" / "cura").is_dir():
            return folder, FLATPAK_ROOT.joinpath(*folder.relative_to(files).parts)
    _tell("%s carries no share/cura below %s", app_id, files)
    return None


def needs_loader(executable: Path) -> bool:
    """Rechnet diese Cura nur über ihren Lader — Flatpak oder AppImage?"""
    return bool(discover.flatpak_app(executable)) or is_appimage(executable)


def engine_missing(executable: Path) -> bool:
    """Fehlt dieser Cura, was zum Rechnen nötig ist (:data:`WINDOW_ONLY`)?

    Beim Flatpak wird nachgesehen. Beim AppImage antwortet nur, was das
    Einlesen der Drucker schon festgestellt hat (:func:`appimage_resources`) —
    der Druckdialog fragt im Hauptfaden und hängt dafür nichts ein. Unbekannt
    heißt nein; dann sagt es der Lauf.
    """
    app = discover.flatpak_app(executable)
    if app:
        appdir = flatpak_appdir(app)
        return appdir is None or loader_command(*appdir) is None
    if is_appimage(executable):
        return _known_engine(executable) is False
    return False


def still_unknown(executable: Path) -> bool:
    """Steht bei einer AppImage-Cura noch aus, ob sie rechnen kann?

    Wahr, bis ihre Druckerkopie eine Marke hat. Der Druckdialog hält *Slicen*
    so lange mit einem Grund an, statt auf eine Vermutung zu wirken.
    """
    return is_appimage(executable) and _known_engine(executable) is None


def window_only(tool: str) -> ExternalToolError:
    """Die Absage, wenn Solidon mit dieser Cura nicht rechnen kann."""
    return ExternalToolError(
        tool=tool, detail=WINDOW_ONLY, suggestions=(CHOOSE_SLICER, EXPORT_ONLY)
    )


@contextmanager
def engine(
    executable: Path, workspace: Path, tool: str, cancelled: CancelToken | None = None
) -> Iterator[list[str] | None]:
    """Der Programmteil eines CuraEngine-Aufrufs vor ``slice``, für die Dauer des Laufs.

    ``None``, wenn das gewählte Programm selbst rechnet — CuraEngine unter
    Windows, im Mac-Bündel oder aus dem Paketverwalter. Fehlt einer Flatpak-
    oder AppImage-Cura der Lader, endet es mit :func:`window_only`; ein
    AppImage bleibt bis zum Ende des Blocks eingehängt.
    """
    app = discover.flatpak_app(executable)
    if app:
        appdir = flatpak_appdir(app)
        command = loader_command(*appdir) if appdir is not None else None
        if command is None:
            raise window_only(tool)
        loader, *rest = command
        yield ["flatpak", "run", f"--filesystem={workspace}", f"--command={loader}", app, *rest]
        return
    if not is_appimage(executable):
        yield None
        return
    with mounted(executable, cancelled) as mount:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if mount.point is None:
            raise ExternalToolError(
                tool=tool,
                detail=NOT_MOUNTED,
                values={"reason": mount.reason} if mount.reason else {},
                suggestions=(CHOOSE_SLICER, EXPORT_ONLY),
            )
        command = loader_command(mount.point, mount.point)
        if command is None:
            raise window_only(tool)
        yield command


def mount_command(appimage: Path) -> list[str]:
    """``--appimage-mount`` so, dass das Einhängen mit Solidon endet.

    Aus Solidons Flatpak heraus läuft es über ``flatpak-spawn --host``;
    ``--watch-bus`` hängt auch dann aus, wenn ``flatpak-spawn`` ohne Signal
    stirbt, ein SIGTERM reicht es selbst weiter (gemessen am Runner). Draußen
    startet es in eigener Prozessgruppe, und stirbt Solidon hart, erreichte es
    kein Signal: ``setpriv --pdeathsig TERM`` schickt eines, wenn ``setpriv``
    da ist (util-linux). Das Signal gilt dem Faden, der startet — er hält den
    Block bis zum Ende.
    """
    if discover.in_flatpak():
        place = ensure_dir(discover.exchange_dir())
        return [
            "flatpak-spawn",
            "--host",
            "--watch-bus",
            f"--env=TMPDIR={place}",
            str(appimage),
            "--appimage-mount",
        ]
    guard = shutil.which("setpriv")
    prefix = [guard, "--pdeathsig", "TERM", "--"] if guard else []
    return [*prefix, str(appimage), "--appimage-mount"]


@dataclass(frozen=True, slots=True)
class Mount:
    """Ein Einhängen: der Punkt, solange der Block läuft, oder der Grund, warum keiner kam."""

    point: Path | None
    reason: str = ""


@contextmanager
def mounted(appimage: Path, cancelled: CancelToken | None = None) -> Iterator[Mount]:
    """Das eingehängte AppImage, solange der Block läuft.

    Die Laufzeit schreibt den Einhängepunkt als erste Zeile und wartet; endet
    der Prozess, hängt sie aus und räumt den Ordner (gemessen für SIGTERM und
    SIGKILL). Beendet wird beim Verlassen des Blocks in jedem Fall, auch bei
    Abbruch und Fehler; stirbt Solidon selbst, sorgt :func:`mount_command`
    dafür. Gestartet wird im Austauschordner: Aus dem Flatpak reicht
    ``flatpak-spawn`` den Arbeitsordner an den Rechner weiter, und
    Solidons ``/app`` gibt es dort nicht.
    """
    cwd = ensure_dir(discover.exchange_dir()) if discover.in_flatpak() else trusted_cwd()
    with _mounted(mount_command(appimage), cancelled, cwd=cwd) as mount:
        yield mount


@contextmanager
def _mounted(
    command: Sequence[str],
    cancelled: CancelToken | None,
    *,
    cwd: Path | None = None,
    seconds: float | None = None,
) -> Iterator[Mount]:
    try:
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd or trusted_cwd(),
            env=trusted_environment(),
            **process_group_options(no_window=True),
        )
    except OSError as problem:
        _log.warning("cannot mount with %s: %s", " ".join(command), problem)
        yield Mount(None, str(problem))
        return
    errors = bytearray()
    drain = threading.Thread(
        target=_collect, args=(process.stderr, errors), daemon=True, name="appimage-errors"
    )
    drain.start()
    try:
        line = _first_line(process, MOUNT_SECONDS if seconds is None else seconds, cancelled)
        point = Path(line) if line else None
        if cancelled is not None and cancelled.is_cancelled:
            yield Mount(None, "cancelled")
        elif point is None or not point.is_absolute() or not point.is_dir():
            reason = _reason(process, drain, errors)
            _log.warning("the appimage gave no usable mount point %r: %s", line, reason)
            yield Mount(None, reason)
        else:
            yield Mount(point)
    finally:
        terminate_process_tree(process)
        drain.join(1.0)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def _collect(stream: IO[bytes] | None, into: bytearray) -> None:
    """Die Fehlerausgabe lesen, bis sie endet; behalten wird der Anfang.

    ``read1`` wie ``process._drain``: ``read`` kehrte erst nach vollem Puffer
    oder am Ende zurück, und ein hängendes Einhängen verlor seinen Satz.
    """
    if stream is None:
        return
    read = getattr(stream, "read1", stream.read)
    for chunk in iter(lambda: read(1024), b""):
        if len(into) < REASON_BYTES:
            into.extend(chunk[: REASON_BYTES - len(into)])


def _reason(process: subprocess.Popen[bytes], drain: threading.Thread, errors: bytearray) -> str:
    """Was das Einhängen dazu gesagt hat: Fehlerausgabe und Rückgabewert, wenn es endete."""
    try:
        code = process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        code = None
    drain.join(1.0)
    text = bytes(errors).decode("utf-8", errors="replace").strip()
    ended = f"exit code {code}" if code is not None else "no answer"
    return f"{text} ({ended})" if text else ended


def _first_line(
    process: subprocess.Popen[bytes], seconds: float, cancelled: CancelToken | None
) -> str:
    """Die erste Zeile der Ausgabe, abbrechbar und mit Zeitgrenze; leer ohne sie."""
    stream = process.stdout
    if stream is None:
        return ""
    box: list[bytes] = []
    reader = threading.Thread(
        target=lambda: box.append(stream.readline()), daemon=True, name="appimage-mount"
    )
    reader.start()
    deadline = time.monotonic() + seconds
    while reader.is_alive():
        if cancelled is not None and cancelled.is_cancelled:
            return ""
        if time.monotonic() >= deadline:
            _log.info("the appimage did not mount within %.0f s", seconds)
            return ""
        reader.join(0.05)
    return box[0].decode("utf-8", errors="replace").strip() if box else ""


#: Was über eine AppImage-Cura schon feststeht, je Pfad, Änderungszeit und Größe:
#: der Ordner ``share/cura`` der Kopie und ob die Rechenmaschine da ist.
_resources: dict[tuple[str, int, int], tuple[Path, bool]] = {}
#: Fassungen, deren Kopie scheiterte, mit dem Stand der Suche
#: (:func:`discover.cache_generation`): *Neu suchen* versucht es wieder.
_failed: dict[tuple[str, int, int], int] = {}
_building = threading.Lock()
#: Der Faden, der nie auf Einhängen und Kopie wartet (:func:`never_wait_in`).
_never_waits: threading.Thread | None = None


def never_wait_in(thread: threading.Thread | None) -> None:
    """Dieser Faden wartet nie auf eine Druckerkopie — die Oberfläche nennt ihren Fensterfaden.

    Dort antwortet :func:`appimage_resources` nur mit dem, was schon feststeht;
    die Kopie legen Arbeiter an (``print_settings_dialog._CuraPrinterWorker``).
    Ohne Angabe wartet jeder Faden, und die Kommandozeile kopiert selbst.
    """
    global _never_waits
    _never_waits = thread


def _key(appimage: Path) -> tuple[str, int, int] | None:
    try:
        info = appimage.stat()
    except OSError:
        return None
    return (str(appimage), info.st_mtime_ns, info.st_size)


def _cache_root() -> Path:
    return user_cache_dir() / "cura-appimage"


def _cache_folder(appimage: Path) -> Path:
    digest = hashlib.sha256(str(appimage).encode("utf-8")).hexdigest()[:16]
    return _cache_root() / digest


def appimage_resources(appimage: Path) -> Path | None:
    """``share/cura`` einer AppImage-Cura als beständige Kopie, oder ``None``.

    Einmal je Fassung (Pfad, Änderungszeit, Größe): einhängen, die Ordner aus
    :data:`RESOURCE_FOLDERS` in den Nutzer-Cache kopieren, aushängen. Danach
    liest jede Frage die Kopie; ein neues AppImage ersetzt sie, und Kopien
    verschwundener AppImages werden geräumt. Scheitert es, bleibt es beim
    Nein, bis :func:`discover.forget_cache` neu suchen lässt. Im Faden aus
    :func:`never_wait_in` antwortet es nur mit dem, was schon feststeht.
    """
    key = _key(appimage)
    if key is None:
        return None
    known = _resources.get(key)
    if known is not None:
        return known[0]
    if threading.current_thread() is _never_waits:
        stamped = _stamped(appimage, key)
        if stamped is None:
            return None
        _resources[key] = stamped
        return stamped[0]
    with _building:
        if key not in _resources and _failed.get(key) != discover.cache_generation():
            stamped = _stamped(appimage, key) or _copy_resources(appimage, key)
            if stamped is None:
                _failed[key] = discover.cache_generation()
            else:
                _failed.pop(key, None)
                _resources[key] = stamped
    known = _resources.get(key)
    return known[0] if known is not None else None


def _known_engine(appimage: Path) -> bool | None:
    """Ob die Kopie dieser Fassung eine Rechenmaschine gesehen hat; ``None``: unbekannt."""
    key = _key(appimage)
    if key is None:
        return None
    known = _resources.get(key)
    if known is None:
        known = _stamped(appimage, key)
        if known is not None:
            _resources[key] = known
    return known[1] if known is not None else None


def _stamped(appimage: Path, key: tuple[str, int, int]) -> tuple[Path, bool] | None:
    """Die abgelegte Kopie, wenn ihre Marke zu dieser Fassung passt."""
    folder = _cache_folder(appimage)
    stamp = _read_stamp(folder)
    if stamp is None or [stamp.get("source"), stamp.get("mtime_ns"), stamp.get("size")] != list(
        key
    ):
        return None
    return folder / "share" / "cura", bool(stamp.get("engine"))


def _read_stamp(folder: Path) -> dict[str, object] | None:
    try:
        stamp = json.loads((folder / STAMP).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    return stamp if isinstance(stamp, dict) else None


def _copy_resources(appimage: Path, key: tuple[str, int, int]) -> tuple[Path, bool] | None:
    folder = _cache_folder(appimage)
    started = time.monotonic()
    with mounted(appimage) as mount:
        if mount.point is None:
            return None
        resources = mount.point / "share" / "cura" / "resources"
        if not resources.is_dir():
            _log.warning("%s carries no cura resources", appimage.name)
            return None
        try:
            fresh = Path(tempfile.mkdtemp(prefix=f"{folder.name}-", dir=ensure_dir(folder.parent)))
        except OSError as problem:
            _log.warning("cannot keep the printers of %s: %s", appimage.name, problem)
            return None
        try:
            target = fresh / "share" / "cura" / "resources"
            for name in RESOURCE_FOLDERS:
                if (resources / name).is_dir():
                    shutil.copytree(resources / name, target / name)
            usable = loader_command(mount.point, mount.point) is not None
            stamp = {"source": key[0], "mtime_ns": key[1], "size": key[2], "engine": usable}
            (fresh / STAMP).write_text(json.dumps(stamp), encoding="utf-8")
        except OSError as problem:
            shutil.rmtree(fresh, ignore_errors=True)
            _log.warning("cannot keep the printers of %s: %s", appimage.name, problem)
            return None
    kept = _replace(folder, fresh, appimage, key)
    if kept is not None:
        _log.info(
            "kept the printers of %s in %.1f s (engine %s)",
            appimage.name,
            time.monotonic() - started,
            "found" if usable else "missing",
        )
        _clear_vanished(folder)
    return kept


def _replace(
    folder: Path, fresh: Path, appimage: Path, key: tuple[str, int, int]
) -> tuple[Path, bool] | None:
    """Die neue Kopie an die Stelle der alten — oder die eines zweiten Solidon, wenn sie passt."""
    try:
        if folder.exists():
            shutil.rmtree(folder)
        fresh.rename(folder)
    except OSError as problem:
        shutil.rmtree(fresh, ignore_errors=True)
        stamped = _stamped(appimage, key)
        if stamped is None:
            _log.warning(
                "cannot replace the printers of %s at %s: %s", appimage.name, folder, problem
            )
        return stamped
    stamp = _read_stamp(folder) or {}
    return folder / "share" / "cura", bool(stamp.get("engine"))


def _clear_vanished(keep: Path) -> None:
    """Kopien von AppImages räumen, die es nicht mehr gibt — ein Update trägt die
    Version im Dateinamen, und jede Kopie wiegt rund 26 MB.

    Dazu die Zwischenordner abgebrochener Kopien (:data:`UNFINISHED`, ohne Marke),
    sobald sie älter als :data:`STALE_SECONDS` sind; eine jüngere kann gerade ein
    zweiter Solidon füllen. Was geräumt ist, verlässt auch den Merker — kommt
    das AppImage zurück (ein Stick), wird neu kopiert.
    """
    try:
        siblings = [entry for entry in _cache_root().iterdir() if entry.is_dir() and entry != keep]
    except OSError:
        return
    for sibling in siblings:
        stamp = _read_stamp(sibling)
        source = stamp.get("source") if stamp is not None else None
        if stamp is None:
            if not UNFINISHED.fullmatch(sibling.name) or not _older_than(sibling, STALE_SECONDS):
                continue
        elif not isinstance(source, str) or Path(source).exists():
            continue
        try:
            shutil.rmtree(sibling)
        except OSError as problem:
            _log.warning("cannot clear the old printers at %s: %s", sibling, problem)
            continue
        _log.info("cleared the printers at %s (%s)", sibling, source or "unfinished copy")
        for key, (found, _usable) in list(_resources.items()):
            if found.is_relative_to(sibling):
                del _resources[key]


def _older_than(folder: Path, seconds: float) -> bool:
    try:
        return time.time() - folder.stat().st_mtime > seconds
    except OSError:
        return False
