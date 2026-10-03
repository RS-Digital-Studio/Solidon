"""Startet den Hilfsprozess des Kerns aus dem gebauten Paket (RM-212, Rauchtest im Paketjob).

Im Paket ist ``sys.executable`` die Anwendung selbst: ``multiprocessing``
startet für den Hilfsprozess (``core.geom.kernel_process``) genau sie noch
einmal, und ihr Einstieg gibt den Start an ``freeze_support`` ab. Ob das auf
der Zielplattform hält — Einstieg, Laufzeithaken, das Modul im Archiv, der
Aufbau des Bundles —, sieht keine Suite: Sie rechnet aus dem Quellbaum.

Dieses Werkzeug ist der Elternprozess. Es nennt die gebaute Anwendung als
ausführbare Datei, startet den Hilfsprozess, wie die Anwendung es tut, rechnet
eine Boolesche Operation dort und hier und verlangt:

* der Hilfsprozess ist die gebaute Anwendung und antwortet;
* dieselben Bytes wie die Rechnung im Prozess;
* nach ``shutdown`` lebt kein Hilfsprozess mehr;
* sein Temp-Verzeichnis ist danach leer (Durchsicht RM-212, B4: der frühere
  Laufzeithaken für matplotlib legte dort je Prozess einen Ordner an);
* unter Linux bleibt kein gemeinsamer Speicher in ``/dev/shm``.

Belegt ist die Seite des Hilfsprozesses im Paket; den eingefrorenen
Elternprozess stellt es nicht nach. Suchpfad und Hauptmodul dieses Werkzeugs
reisen nicht mit — der Hilfsprozess nimmt die seines Pakets, wie unter der
Anwendung.

Aufruf (im Paketjob direkt nach dem Bauen): ``python tools/check_frozen_helper.py dist``
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

#: Wie lange der Hilfsprozess des Pakets bis zur ersten Antwort braucht, höchstens,
#: in Sekunden. Die Anwendung wartet 30 s; ein Runner startet ein frisch gebautes
#: Programm langsamer als ein Kundengerät (macOS prüft es beim ersten Start).
STARTUP_SECONDS = 120.0

#: Wie lange die Rechnung im Hilfsprozess höchstens dauert, in Sekunden.
JOB_SECONDS = 120.0

#: Prüfspielraum für das freiwillige Ende des Pakets, in Sekunden.
#: Die Produktfrist bleibt 0,5 s; hier wird der Lebenszyklus geprüft.
END_SECONDS = 30.0


def application(dist: Path, name: str) -> Path:
    """Die gebaute Anwendung, wie sie beim Kunden liegt — je Plattform."""
    if sys.platform == "darwin":
        return dist / f"{name}.app" / "Contents" / "MacOS" / name
    if sys.platform == "win32":
        return dist / name / f"{name}.exe"
    return dist / name / name


def image_of(pid: int) -> str | None:
    """Welche ausführbare Datei ein Prozess ist — ``None``, wenn das System es nicht sagt."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            size = wintypes.DWORD(32_768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return None
            return buffer.value
        finally:
            kernel32.CloseHandle(handle)
    elif sys.platform == "linux":
        try:
            return str(Path(f"/proc/{pid}/exe").readlink())
        except OSError:
            return None
    else:
        found = subprocess.run(
            ["ps", "-o", "comm=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        return found.stdout.strip() or None


def is_the_application(image: str, executable: Path) -> bool:
    """Ob ``image`` die gebaute Anwendung ist; nennt das System nur einen Namen, zählt der."""
    try:
        return Path(image).resolve().samefile(executable)
    except OSError:
        return Path(image).name == executable.name


def shared_memory_names() -> set[str]:
    """Die gemeinsamen Speicher von ``multiprocessing`` unter Linux; anderswo nicht aufzählbar."""
    folder = Path("/dev/shm")
    if sys.platform != "linux" or not folder.is_dir():
        return set()
    return {entry.name for entry in folder.iterdir() if entry.name.startswith("psm_")}


@contextmanager
def as_the_package(executable: Path) -> Iterator[None]:
    """Startet Kindprozesse, wie die eingefrorene Anwendung es täte.

    Mit ``sys.frozen`` baut ``spawn`` die Kommandozeile des Pakets
    (``--multiprocessing-fork parent_pid=… pipe_handle=…``) und startet die
    genannte Datei. Suchpfad und Hauptmodul bleiben aus den Startdaten: Der
    Hilfsprozess behält die seines Pakets, wie unter der Anwendung, deren
    Laufzeithaken ``ORIGINAL_DIR`` dafür leert. Unter POSIX ist die gebaute
    Datei auch ``argv[0]``; unter Windows nicht — dort leitete ``spawn`` eine
    ``sys.executable`` gleiche Datei einer venv auf deren Python um.
    """
    import multiprocessing.spawn as spawn

    from app.core.geom import kernel_process

    prepared = spawn.get_preparation_data

    def packaged(name: str) -> dict[str, Any]:
        data = dict(prepared(name))
        for key in ("sys_path", "init_main_from_path", "init_main_from_name"):
            data.pop(key, None)
        return data

    original = sys.executable
    kernel_process._CONTEXT.set_executable(str(executable))
    spawn.get_preparation_data = packaged
    sys.frozen = True
    if sys.platform != "win32":
        sys.executable = str(executable)
    try:
        yield
    finally:
        del sys.frozen
        sys.executable = original
        spawn.get_preparation_data = prepared
        kernel_process._CONTEXT.set_executable(original)


def boolean_case() -> tuple[dict[str, Any], dict[str, Any]]:
    """Eine Kugel minus ein Zylinder quer hindurch — 8 444 Dreiecke, beide geschlossen."""
    import manifold3d
    import numpy as np

    sphere = manifold3d.Manifold.sphere(20.0, 128).to_mesh64()
    cut = manifold3d.Manifold.cylinder(60.0, 4.0, 4.0, 64).translate((0.0, 0.0, -30.0)).to_mesh64()
    arrays = {
        "vertices0": np.array(sphere.vert_properties[:, :3], dtype=np.float64),
        "faces0": np.array(sphere.tri_verts, dtype=np.int64),
        "vertices1": np.array(cut.vert_properties[:, :3], dtype=np.float64),
        "faces1": np.array(cut.tri_verts, dtype=np.int64),
    }
    return arrays, {"bodies": 2, "kind": "difference"}


def in_a_worker(work: Callable[[], Any], seconds: float) -> Any:
    """``work`` in einem Nebenfaden — im Hauptfaden rechnete ``kernel_process`` hier."""
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["value"] = work()
        except BaseException as problem:
            box["error"] = problem

    worker = threading.Thread(target=run, name="helper-check", daemon=True)
    worker.start()
    worker.join(seconds)
    if worker.is_alive():
        raise TimeoutError(f"keine Antwort in {seconds:.0f} s")
    if "error" in box:
        raise box["error"]
    return box["value"]


def same_bytes(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Ob zwei Felderverzeichnisse Byte für Byte gleich sind."""
    return first.keys() == second.keys() and all(
        first[name].dtype == second[name].dtype
        and first[name].shape == second[name].shape
        and first[name].tobytes() == second[name].tobytes()
        for name in first
    )


def check(executable: Path, temp: Path, report: dict[str, Any]) -> list[str]:
    """Startet, rechnet, beendet und räumt nach — die Befunde als Sätze, leer heißt grün."""
    from app.core.geom import kernel_jobs, kernel_process

    problems: list[str] = []
    if os.name == "posix":
        # Der Aufräumprozess von ``multiprocessing`` startet mit dem ersten
        # Kindprozess, und zwar aus der eingestellten Datei — aus dem Paket
        # ginge die Umleitung seines Laufzeithakens an den Schaltern dieses
        # Interpreters vorbei. Er kommt deshalb vorher aus diesem Python.
        from multiprocessing import resource_tracker

        resource_tracker.ensure_running()
    arrays, values = boolean_case()
    weight = len(arrays["faces0"]) + len(arrays["faces1"])
    expected, reported = kernel_jobs.JOBS["boolean"](arrays, dict(values), lambda: None)
    report["triangles"] = weight
    shared_before = shared_memory_names()
    kernel_process.OFFLOAD_ABOVE = 0
    vars(kernel_process)["STARTUP_SECONDS"] = STARTUP_SECONDS
    vars(kernel_process)["GRACEFUL_SECONDS"] = END_SECONDS
    began = time.perf_counter()
    with as_the_package(executable):
        ready = kernel_process.warm_up()
    report["ready_seconds"] = round(time.perf_counter() - began, 2)
    helpers = kernel_process.processes()
    report["helper_pids"] = [helper.pid for helper in helpers]
    if not ready or len(helpers) != 1:
        problems.append(
            "Der Hilfsprozess aus dem Paket hat nicht geantwortet. Einstieg (freeze_support "
            "in app/ui/app.py) und PyInstaller-Laufzeithaken prüfen."
        )
    else:
        image = image_of(int(helpers[0].pid or 0))
        report["helper_image"] = image
        if image is not None and not is_the_application(image, executable):
            problems.append(f"Der Hilfsprozess ist {image}, nicht die gebaute Anwendung.")
        try:
            got, got_reported = in_a_worker(
                lambda: kernel_process.run("boolean", arrays, values, weight=weight),
                JOB_SECONDS,
            )
        except Exception as problem:
            problems.append(f"Die Rechnung im Hilfsprozess scheiterte: {problem!r}")
        else:
            report["same_bytes"] = same_bytes(expected, got) and got_reported == reported
            if not report["same_bytes"]:
                problems.append("Der Hilfsprozess rechnet andere Bytes als der Prozess.")
    statistics = kernel_process.statistics()
    report["statistics"] = statistics
    if statistics.get("helper:boolean") != 1 or statistics["fallback"] or statistics["lost"]:
        problems.append(f"Gerechnet hat nicht der Hilfsprozess des Pakets: {statistics}")
    # Hart beendet, wie beim Abbrechen: Auch dann darf nichts liegen bleiben.
    for helper in helpers:
        helper.kill()
        helper.join(10.0)
    kernel_process.shutdown()
    problems.extend(ended(helpers, temp, "hart beendet", report))
    # Und sanft, wie beim Schließen der Anwendung: Der untätige endet selbst.
    with as_the_package(executable):
        kernel_process.warm_up()
    second = kernel_process.processes()
    kernel_process.shutdown()
    problems.extend(ended(second, temp, "beim Schließen", report))
    if any(helper.exitcode != 0 for helper in second):
        problems.append("Ein untätiger Hilfsprozess endete beim Schließen nicht selbst.")
    shared_after = sorted(shared_memory_names() - shared_before)
    report["shared_memory_leftovers"] = shared_after
    if shared_after:
        problems.append(f"Gemeinsamer Speicher blieb liegen: {shared_after}")
    return problems


def ended(helpers: list[Any], temp: Path, how: str, report: dict[str, Any]) -> list[str]:
    """Ob die Hilfsprozesse fort sind und ihr Temp-Verzeichnis leer ist.

    Was liegen blieb, wird danach weggeräumt: Der nächste Abschnitt zählt nur,
    was er selbst hinterlässt.
    """
    problems: list[str] = []
    for helper in helpers:
        helper.join(10.0)
    report[f"exit_codes ({how})"] = [helper.exitcode for helper in helpers]
    if any(helper.is_alive() for helper in helpers):
        problems.append(f"Ein Hilfsprozess lebt noch ({how}).")
    leftovers = sorted(str(entry.relative_to(temp)) for entry in temp.rglob("*"))
    report[f"temp_leftovers ({how})"] = leftovers
    if leftovers:
        problems.append(
            f"Im Temp-Verzeichnis des Hilfsprozesses blieb etwas liegen ({how}): {leftovers}"
        )
    for entry in temp.iterdir():
        shutil.rmtree(entry, ignore_errors=True)
    return problems


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("Aufruf: python tools/check_frozen_helper.py <dist>", file=sys.stderr)
        return 2
    # Aus diesem Baum, nicht aus einer editierbaren Installation daneben.
    sys.path.insert(0, str(ROOT))
    from app.branding import APP_NAME

    executable = application(Path(arguments[0]).resolve(), APP_NAME)
    report: dict[str, Any] = {"executable": str(executable)}
    if not executable.is_file():
        print(f"::error::Die gebaute Anwendung fehlt: {executable}")
        return 1
    scratch = Path(tempfile.mkdtemp(prefix="solidon-helper-check-"))
    temp = scratch / "temp"
    temp.mkdir()
    # Der Hilfsprozess erbt sein Temp-Verzeichnis; dieser Prozess hat seines
    # mit ``mkdtemp`` schon festgelegt.
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(temp)
    try:
        problems = check(executable, temp, report)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    print(json.dumps(report, indent=1, ensure_ascii=False))
    for problem in problems:
        print(f"::error::{problem}")
    if not problems:
        print("Der Hilfsprozess startet aus dem Paket, rechnet bitgleich und hinterlässt nichts.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
