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
liest sie einmal je Fassung aus dem Abbild, ohne das AppImage zu starten
(:mod:`squashfs`, RM-599), und legt die Ordner, die Solidon liest, im
Nutzer-Cache ab; ebenso, ob die Rechenmaschine darin vollständig ist.
Eingehängt wird nur für einen Lauf. Die Kopie verwaltet
:class:`appimage.ImageCopies` wie den Orca-Bestand; der Fensterfaden wartet
auf sie nie (:func:`appimage.never_wait_in`).
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath
from typing import IO, Final

from app.core import discover
from app.core.errors import CHOOSE_SLICER, EXPORT_ONLY, ExternalToolError
from app.core.export import appimage, squashfs
from app.core.log import get_logger
from app.core.paths import ensure_dir
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

#: Wo Curas Druckerbestand im AppDir liegt.
RESOURCES: Final = PurePosixPath("share/cura/resources")

#: Die Ordner unter ``share/cura/resources``, die Solidon aus Curas Bestand
#: liest (``slicer_profiles``: Drucker, Züge, Düsen, Qualität, Absicht,
#: Material).
RESOURCE_FOLDERS: Final = ("definitions", "extruders", "intent", "materials", "quality", "variants")

#: Wie lange das Einhängen dauern darf. Gemessen: 0,01 s.
MOUNT_SECONDS: Final = 30.0

#: Wie viel von der Fehlerausgabe des Einhängens als Grund mitreist.
REASON_BYTES: Final = 4096

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
    if not engine_complete(variables, lambda path: (here / path).is_file(), here):
        return None
    return [
        str(there / COMPAT / linker(variables)),
        "--library-path",
        library_path(variables, str(there)),
        str(there / ENGINE),
    ]


def engine_complete(
    variables: Mapping[str, str], is_file: Callable[[PurePosixPath], bool], where: object
) -> bool:
    """Trägt das AppDir, was :func:`loader_command` braucht: Lader, CuraEngine
    und einen Bibliothekspfad? ``is_file`` fragt relativ zum AppDir — im
    Ordner oder im Abbild (:func:`_read_resources`); ``where`` nennt es im
    Protokoll."""
    name = linker(variables)
    if not is_file(COMPAT / name) or not is_file(PurePosixPath(ENGINE)):
        _tell("cura below %s has no loader %s or no %s", where, name, ENGINE)
        return False
    if not library_path(variables, "/"):
        _tell("%s below %s names no library path", ENVIRONMENT, where)
        return False
    return True


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


#: Die Fassung des Kopierers für Curas Drucker. Eine neue verwirft ältere Kopien.
PRINTER_COPY_VERSION: Final = 1


def _fill_printers(executable: Path, fresh: Path) -> dict[str, object] | None:
    usable = _read_resources(executable, fresh / RESOURCES)
    return None if usable is None else {"engine": usable}


#: Die Kopien von Curas Druckerbestand, mit der Antwort, ob die Rechenmaschine
#: vollständig ist (``engine`` in der Marke).
PRINTER_COPIES: Final = appimage.ImageCopies(
    "cura-appimage", PurePosixPath("share/cura"), PRINTER_COPY_VERSION, _fill_printers, "printers"
)


def appimage_resources(executable: Path) -> Path | None:
    """``share/cura`` einer AppImage-Cura als beständige Kopie, oder ``None``.

    Die Ordner aus :data:`RESOURCE_FOLDERS`, aus dem Abbild gelesen
    (:func:`_read_resources`), ohne das AppImage zu starten; Fassung, Merker,
    Räumen und Fensterfaden wie jede Kopie aus einem AppImage
    (:meth:`appimage.ImageCopies.kept`).
    """
    found = PRINTER_COPIES.kept(executable)
    return found.folder if found is not None else None


def _known_engine(executable: Path) -> bool | None:
    """Ob die Kopie dieser Fassung eine Rechenmaschine gesehen hat; ``None``: unbekannt."""
    found = PRINTER_COPIES.known(executable)
    return bool(found.stamp.get("engine")) if found is not None else None


def _read_resources(executable: Path, target: Path) -> bool | None:
    """Curas Druckerbestand aus dem Abbild nach ``target``, ohne das AppImage zu
    starten (RM-599, Regel 11) — und ob die Rechenmaschine darin vollständig ist.

    ``None``, wenn das Abbild keinen Bestand trägt. Der Lader ist im Abbild
    eine Verknüpfung (``lib64`` → ``lib/x86_64-linux-gnu``);
    :meth:`squashfs.SquashImage.is_file` folgt ihr wie das Dateisystem eines
    eingehängten Abbilds.
    """
    with executable.open("rb") as handle:
        image = squashfs.SquashImage.of(handle)
        resources = image.find(RESOURCES)
        if resources is None or resources.kind != squashfs.DIRECTORY:
            _log.warning("%s carries no cura resources", executable.name)
            return None
        for name in RESOURCE_FOLDERS:
            found = image.find(RESOURCES / name)
            if found is not None and found.kind == squashfs.DIRECTORY:
                squashfs.copy_folder(image, found, target / name)
        environment = image.resolve(PurePosixPath(ENVIRONMENT))
        if environment is None or environment.kind != squashfs.FILE:
            _tell("no readable %s inside %s", ENVIRONMENT, executable)
            return False
        try:
            variables = read_environment(image.read(environment).decode("utf-8"))
        except UnicodeDecodeError as problem:
            _tell("no readable %s inside %s: %s", ENVIRONMENT, executable, problem)
            return False
        return engine_complete(variables, image.is_file, executable)
