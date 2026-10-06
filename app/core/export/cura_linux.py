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
(:data:`WINDOW_ONLY`).

Die Drucker einer AppImage-Cura liegen im Abbild. :func:`appimage_resources`
hängt es einmal je Fassung kurz ein und legt die Ordner, die Solidon liest, im
Nutzer-Cache ab — beständig, denn jeder Einhängepunkt heißt anders, und eine
Profilliste darf nicht in einen verschwundenen Ordner zeigen.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path, PurePath, PurePosixPath
from typing import Final

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

#: Wo das Flatpak ``com.ultimaker.cura`` sein AppDir sieht — und unter welchem
#: Ordner seines ``/app`` es auf dem Rechner liegt.
FLATPAK_APPDIR: Final = PurePosixPath("/app/cura")
FLATPAK_FOLDER: Final = "cura"

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

#: Die Marke einer abgelegten Kopie: Quelle, Stand und ob die Rechenmaschine da ist.
STAMP: Final = "stamp.json"

#: Der Satz für Druckdialog und Absage, wenn Solidon mit dieser Cura nicht rechnen kann.
WINDOW_ONLY: Final = _(
    "Mit dieser Cura-Installation kann Solidon nicht selbst slicen, weil ihr Lader für "
    "CuraEngine fehlt. Öffnen Sie die Datei in Curas Fenster."
)


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

    Einträge mit einer anderen Variable bleiben weg; doppelte zählen einmal.
    """
    seen: list[str] = []
    for name in LIBRARY_VARIABLES:
        for entry in variables.get(name, "").split(":"):
            expanded = entry.replace("${APPDIR}", appdir).replace("$APPDIR", appdir)
            if not expanded or "$" in expanded:
                continue
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
        _log.info("no readable %s below %s: %s", ENVIRONMENT, here, problem)
        return None
    name = linker(variables)
    if not (here / COMPAT / name).is_file() or not (here / ENGINE).is_file():
        _log.info("cura below %s has no loader %s or no %s", here, name, ENGINE)
        return None
    libraries = library_path(variables, str(there))
    if not libraries:
        return None
    return [str(there / COMPAT / name), "--library-path", libraries, str(there / ENGINE)]


def flatpak_appdir(app_id: str) -> Path | None:
    """Curas AppDir in seiner Flatpak-Installation, wie Solidon es liest."""
    files = discover.flatpak_files(app_id)
    folder = files / FLATPAK_FOLDER if files is not None else None
    return folder if folder is not None and folder.is_dir() else None


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
        return appdir is None or loader_command(appdir, FLATPAK_APPDIR) is None
    if is_appimage(executable):
        return _known_engine(executable) is False
    return False


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
    oder AppImage-Cura der Lader, endet es mit :func:`window_only`.
    """
    app = discover.flatpak_app(executable)
    if app:
        appdir = flatpak_appdir(app)
        command = loader_command(appdir, FLATPAK_APPDIR) if appdir is not None else None
        if command is None:
            raise window_only(tool)
        loader, *rest = command
        yield ["flatpak", "run", f"--filesystem={workspace}", f"--command={loader}", app, *rest]
        return
    if not is_appimage(executable):
        yield None
        return
    with mounted(executable, cancelled) as point:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if point is None:
            raise ExternalToolError(
                tool=tool,
                detail=_(
                    "Curas AppImage ließ sich nicht einhängen. Prüfen Sie, ob Cura selbst "
                    "startet, oder wählen Sie einen anderen Slicer."
                ),
                suggestions=(CHOOSE_SLICER, EXPORT_ONLY),
            )
        command = loader_command(point, point)
        if command is None:
            raise window_only(tool)
        yield command


def mount_command(appimage: Path) -> list[str]:
    """``--appimage-mount``, aus Solidons Flatpak heraus auf dem Rechner.

    ``--watch-bus`` beendet das Einhängen auch dann, wenn ``flatpak-spawn``
    ohne Signal stirbt; ein SIGTERM reicht es selbst weiter.
    """
    if not discover.in_flatpak():
        return [str(appimage), "--appimage-mount"]
    place = ensure_dir(discover.exchange_dir())
    return [
        "flatpak-spawn",
        "--host",
        "--watch-bus",
        f"--env=TMPDIR={place}",
        str(appimage),
        "--appimage-mount",
    ]


@contextmanager
def mounted(appimage: Path, cancelled: CancelToken | None = None) -> Iterator[Path | None]:
    """Das eingehängte AppImage, solange der Block läuft — oder ``None``.

    Die Laufzeit schreibt den Einhängepunkt als erste Zeile und wartet; endet
    der Prozess, hängt sie aus und räumt den Ordner (gemessen für SIGTERM und
    SIGKILL). Beendet wird in jedem Fall, auch bei Abbruch und Fehler.
    """
    with _mounted(mount_command(appimage), cancelled) as point:
        yield point


@contextmanager
def _mounted(
    command: Sequence[str], cancelled: CancelToken | None, seconds: float = MOUNT_SECONDS
) -> Iterator[Path | None]:
    try:
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=trusted_cwd(),
            env=trusted_environment(),
            **process_group_options(no_window=True),
        )
    except OSError as problem:
        _log.info("cannot mount with %s: %s", " ".join(command), problem)
        yield None
        return
    try:
        line = _first_line(process, seconds, cancelled)
        point = Path(line) if line else None
        if point is None or not point.is_absolute() or not point.is_dir():
            _log.info("the appimage gave no usable mount point: %r", line)
            point = None
        yield point
    finally:
        terminate_process_tree(process)
        if process.stdout is not None:
            process.stdout.close()


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
#: der Ordner ``share/cura`` der Kopie (oder ``None``) und ob die Rechenmaschine da ist.
_resources: dict[tuple[str, int, int], tuple[Path | None, bool | None]] = {}
_building = threading.Lock()


def _key(appimage: Path) -> tuple[str, int, int] | None:
    try:
        info = appimage.stat()
    except OSError:
        return None
    return (str(appimage), info.st_mtime_ns, info.st_size)


def _cache_folder(appimage: Path) -> Path:
    digest = hashlib.sha256(str(appimage).encode("utf-8")).hexdigest()[:16]
    return user_cache_dir() / "cura-appimage" / digest


def appimage_resources(appimage: Path) -> Path | None:
    """``share/cura`` einer AppImage-Cura als beständige Kopie, oder ``None``.

    Einmal je Fassung (Pfad, Änderungszeit, Größe): einhängen, die Ordner aus
    :data:`RESOURCE_FOLDERS` in den Nutzer-Cache kopieren, aushängen. Danach
    liest jede Frage die Kopie; ein neues AppImage ersetzt sie. Scheitert es,
    bleibt es in dieser Sitzung beim Nein, statt bei jeder Frage neu zu starten.
    """
    key = _key(appimage)
    if key is None:
        return None
    if key in _resources:
        return _resources[key][0]
    with _building:
        if key not in _resources:
            _resources[key] = _stamped(appimage, key) or _copy_resources(appimage, key)
    return _resources[key][0]


def _known_engine(appimage: Path) -> bool | None:
    """Ob die Kopie dieser Fassung eine Rechenmaschine gesehen hat; ``None``: unbekannt."""
    key = _key(appimage)
    if key is None:
        return None
    if key not in _resources:
        stamped = _stamped(appimage, key)
        if stamped is None:
            return None
        _resources[key] = stamped
    return _resources[key][1]


def _stamped(appimage: Path, key: tuple[str, int, int]) -> tuple[Path, bool] | None:
    """Die abgelegte Kopie, wenn ihre Marke zu dieser Fassung passt."""
    folder = _cache_folder(appimage)
    try:
        stamp = json.loads((folder / STAMP).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    if not isinstance(stamp, dict) or [
        stamp.get("source"),
        stamp.get("mtime_ns"),
        stamp.get("size"),
    ] != list(key):
        return None
    return folder / "share" / "cura", bool(stamp.get("engine"))


def _copy_resources(appimage: Path, key: tuple[str, int, int]) -> tuple[Path | None, bool | None]:
    folder = _cache_folder(appimage)
    started = time.monotonic()
    with mounted(appimage) as point:
        if point is None:
            return None, None
        resources = point / "share" / "cura" / "resources"
        if not resources.is_dir():
            _log.info("%s carries no cura resources", appimage.name)
            return None, None
        try:
            fresh = Path(tempfile.mkdtemp(prefix=f"{folder.name}-", dir=ensure_dir(folder.parent)))
        except OSError as problem:
            _log.warning("cannot keep the printers of %s: %s", appimage.name, problem)
            return None, None
        try:
            target = fresh / "share" / "cura" / "resources"
            for name in RESOURCE_FOLDERS:
                if (resources / name).is_dir():
                    shutil.copytree(resources / name, target / name)
            usable = loader_command(point, point) is not None
            stamp = {"source": key[0], "mtime_ns": key[1], "size": key[2], "engine": usable}
            (fresh / STAMP).write_text(json.dumps(stamp), encoding="utf-8")
        except OSError as problem:
            shutil.rmtree(fresh, ignore_errors=True)
            _log.warning("cannot keep the printers of %s: %s", appimage.name, problem)
            return None, None
    shutil.rmtree(folder, ignore_errors=True)
    try:
        fresh.rename(folder)
    except OSError:
        # Ein zweiter Solidon war schneller; seine Kopie gilt, wenn sie passt.
        shutil.rmtree(fresh, ignore_errors=True)
        stamped = _stamped(appimage, key)
        return stamped if stamped is not None else (None, None)
    _log.info(
        "kept the printers of %s in %.1f s (engine %s)",
        appimage.name,
        time.monotonic() - started,
        "found" if usable else "missing",
    )
    return folder / "share" / "cura", usable
