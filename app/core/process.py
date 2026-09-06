"""Sichere Prozessgrenze für externe Programme (§29, §32).

Ein Unterprozess erbt sonst still die ganze Umgebung von Solidon — darunter
API-Schlüssel, die ein Slicer oder Paketmanager nicht braucht. Ebenso beendet
``Popen.kill`` nur den unmittelbaren Prozess, nicht die von ihm gestarteten
Helfer. Dieses Modul hält die gemeinsame Zusage an einer Stelle:

* nur die für Betriebssystem, Oberfläche und Benutzerordner nötige Umgebung;
* ein ausdrücklicher Arbeitsordner und geschlossene Dateideskriptoren;
* eine eigene Prozessgruppe für jeden Start;
* begrenzte Laufzeit und Ausgabe für Aufrufe, auf deren Antwort Solidon wartet;
* Abbruch der ganzen Prozessgruppe statt nur ihres ersten Prozesses.

Losgelöste Fenster, Dienste und Installationsprogramme benutzen nur Umgebung,
Arbeitsordner und Prozessgruppe. Sie haben absichtlich keine Zeitgrenze: Mit
dem Start geht ihre Bedienung an den Nutzer über.
"""

from __future__ import annotations

import codecs
import ctypes
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import urlsplit, urlunsplit

#: Nur Werte, die ein gewöhnliches lokales Programm für Betriebssystem,
#: Sprache, Benutzerordner, grafische Sitzung oder den Weg ins Netz braucht.
#: Proxy-Zugangsdaten, API-Schlüssel, Python-Suchpfade und Loader-Eingriffe
#: reisen nicht mit.
_ENVIRONMENT_NAMES: Final = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "USER",
    "USERNAME",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMDATA",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "XDG_DATA_DIRS",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "__CF_USER_TEXT_ENCODING",
    # **Wie der Rechner ins Netz kommt** — ohne diese Namen erreicht im
    # Firmennetz weder ``pip`` noch ``winget`` seinen Server, und die
    # Nachinstallation (§36) endet an einem Zeitlimit ohne Grund. Die
    # Kleinschreibung steht daneben, weil sie auf Unix die übliche ist und
    # ``pip`` beide liest; wer nur die großen mitgibt, hat den Fehler auf
    # Linux und macOS behoben gelassen.
    #
    # **Zugangsdaten reisen trotzdem nicht mit**: Was wie eine Adresse
    # aussieht, geht durch :func:`_without_credentials`.
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "PIP_INDEX_URL",
)

#: Welche dieser Werte eine Adresse sind und damit ``benutzer:kennwort@``
#: tragen können. ``NO_PROXY`` steht nicht dabei — es ist eine Liste von
#: Rechnernamen, und ein ``@`` darin bedeutet nichts.
_URL_ENVIRONMENT_NAMES: Final = frozenset(
    {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "PIP_INDEX_URL",
    }
)

#: Nur Programme, deren Oberfläche der Nutzer ausdrücklich übernimmt,
#: bekommen die Sitzungskanäle zum Displayserver und Desktop-Bus. Begrenzte
#: Werkzeuge rechnen oder liefern Text und brauchen diese Befugnisse nicht.
_GRAPHICAL_ENVIRONMENT_NAMES: Final = (
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
    "XDG_RUNTIME_DIR",
    "DBUS_SESSION_BUS_ADDRESS",
)

#: Was ein Aufruf braucht, der den Sandkasten verlässt — und sonst niemand.
#:
#: Läuft Solidon selbst als Flatpak, legt ``discover.on_host`` vor jeden Start
#: ein ``flatpak-spawn --host``. Das spricht über den Sitzungsbus mit dem
#: Flatpak-Dienst: Ohne die Adresse des Busses und das Laufzeitverzeichnis, in
#: dem sein Socket liegt, kommt der Aufruf nicht heraus und meldet, den Portal
#: nicht zu finden. Beide Namen stehen zwar auch in den grafischen Befugnissen
#: — nur bekommt die kein begrenzter Lauf, und genau die begrenzten Läufe sind
#: es, die im Linux-Paket Slicer, Paketmanager und Suchläufe starten.
#:
#: **Zugangsdaten sind das keine**: der eine Wert ist eine Socket-Adresse, der
#: andere ein Pfad.
_SANDBOX_BRIDGE_NAMES: Final = (
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_RUNTIME_DIR",
)

DEFAULT_OUTPUT_LIMIT: Final = 1024 * 1024
PROCESS_POLL_SECONDS: Final = 0.05
PROCESS_STOP_SECONDS: Final = 0.5
_READ_SIZE: Final = 64 * 1024
_WINDOWS_CREATE_SUSPENDED: Final = 0x00000004
#: Die Windows-Namen fehlen in den ctypes-Stubs anderer Plattformen. Zur
#: Laufzeit werden sie ausschließlich hinter ``os.name == "nt"`` benutzt.
_windows_ctypes: Any = ctypes


class ProcessOutputLimitExceeded(subprocess.SubprocessError):
    """Ein Prozess hat mehr Ausgabe erzeugt, als sicher gesammelt wird."""

    def __init__(self, command: Sequence[str], limit: int) -> None:
        self.command = tuple(command)
        self.limit = limit
        super().__init__(f"Die Prozessausgabe überschreitet {limit} Bytes.")


class ProcessCancelled(subprocess.SubprocessError):
    """Der Aufrufer hat den begrenzten Prozesslauf abgebrochen."""


def _without_credentials(value: str) -> str:
    """Dieselbe Adresse, aber ohne ``benutzer:kennwort@``.

    Ein Firmenproxy steht regelmäßig als ``http://name:kennwort@proxy:8080`` in
    der Umgebung. Die **Adresse** braucht das fremde Programm, die Zugangsdaten
    nicht — und ein Unterprozess ist genau der Ort, an dem sie sonst hängen
    bleiben: in der Prozessliste, im Absturzbericht und im Protokoll des
    fremden Programms.

    Was keine Adresse ist, bleibt unverändert.
    """
    parts = urlsplit(value)
    if not parts.scheme or "@" not in parts.netloc:
        return value
    host = parts.netloc.rsplit("@", 1)[1]
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def _in_sandbox() -> bool:
    """Läuft Solidon selbst in einem Flatpak?

    Der Import steht im Rumpf, weil ``discover`` dieses Modul benutzt — oben
    wäre es ein Kreis. Zur Aufrufzeit ist es geladen.
    """
    from app.core.discover import in_flatpak

    return in_flatpak()


def trusted_environment(
    source: Mapping[str, str] | None = None,
    *,
    graphical: bool = False,
) -> dict[str, str]:
    """Die kleinste gemeinsame Umgebung für lokale Fremdprogramme.

    Im eigenen Flatpak kommen die zwei Namen dazu, ohne die kein Aufruf den
    Sandkasten verlässt (:data:`_SANDBOX_BRIDGE_NAMES`). Adressen werden dabei
    von Zugangsdaten befreit (:func:`_without_credentials`).
    """
    available = os.environ if source is None else source
    names = _ENVIRONMENT_NAMES + (_GRAPHICAL_ENVIRONMENT_NAMES if graphical else ())
    if _in_sandbox():
        names += _SANDBOX_BRIDGE_NAMES
    chosen: dict[str, str] = {}
    for name in names:
        if name not in available:
            continue
        value = available[name]
        chosen[name] = _without_credentials(value) if name in _URL_ENVIRONMENT_NAMES else value
    return chosen


def trusted_cwd() -> Path:
    """Ein bestehender, installationsnaher Arbeitsordner ohne Projekteingaben."""
    folder = Path(sys.executable).resolve().parent
    return folder if folder.is_dir() else Path.cwd().resolve()


def process_group_options(
    *,
    detached: bool = False,
    no_window: bool = False,
    suspended: bool = False,
) -> dict[str, Any]:
    """Plattformspezifische Optionen für eine eigene Prozessgruppe."""
    options: dict[str, Any] = {"close_fds": True}
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if detached:
            flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        if no_window:
            flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if suspended:
            flags |= _WINDOWS_CREATE_SUSPENDED
        options["creationflags"] = flags
    else:
        options["start_new_session"] = True
    return options


def detached_process_options(
    *,
    cwd: Path | None = None,
    no_window: bool = True,
    graphical: bool = False,
) -> dict[str, Any]:
    """Vollständige Optionen für einen bewusst losgelösten Prozess."""
    return {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": cwd or trusted_cwd(),
        "env": trusted_environment(graphical=graphical),
        **process_group_options(detached=True, no_window=no_window),
    }


def _taskkill(process_id: int, *, force: bool) -> None:
    """Beendet unter Windows einen Prozess samt Nachkommen."""
    system_root = os.environ.get("SYSTEMROOT") or os.environ.get("WINDIR")
    executable = Path(system_root, "System32", "taskkill.exe") if system_root else Path("taskkill")
    command = [str(executable), "/PID", str(process_id), "/T"]
    if force:
        command.append("/F")
    try:
        subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=trusted_cwd(),
            env=trusted_environment(),
            timeout=PROCESS_STOP_SECONDS,
            check=False,
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError, subprocess.SubprocessError:
        return


def _attach_windows_job(process: subprocess.Popen[Any]) -> None:
    """Bindet einen Windows-Prozess an ein Jobobjekt, das er nicht verlassen kann.

    **Ohne Speichergrenze** (Entscheidung Robert, 03.09.2026). Bis 0.2.2 gab
    es hier gar keine; die am 02.09.2026 eingebaute deckelte jeden fremden
    Prozess und war für den Mac tödlich — ``setrlimit(RLIMIT_AS)`` lehnt der
    Darwin-Kern ab, ``subprocess`` verschluckt die Ursache, und das Kind
    startet nie. Sie ist deshalb überall gefallen: Ein Slicer, der viel
    Speicher braucht, gehört dem Nutzer und nicht uns. Was bleibt, ist das
    Jobobjekt selbst — es beendet die Nachkommen mit dem Elternprozess, und
    das hat mit Speicher nichts zu tun.
    """

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("read_operations", ctypes.c_uint64),
            ("write_operations", ctypes.c_uint64),
            ("other_operations", ctypes.c_uint64),
            ("read_bytes", ctypes.c_uint64),
            ("write_bytes", ctypes.c_uint64),
            ("other_bytes", ctypes.c_uint64),
        ]

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("per_process_user_time", ctypes.c_int64),
            ("per_job_user_time", ctypes.c_int64),
            ("limit_flags", ctypes.c_uint32),
            ("minimum_working_set", ctypes.c_size_t),
            ("maximum_working_set", ctypes.c_size_t),
            ("active_process_limit", ctypes.c_uint32),
            ("affinity", ctypes.c_size_t),
            ("priority_class", ctypes.c_uint32),
            ("scheduling_class", ctypes.c_uint32),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("basic", BasicLimits),
            ("io", IoCounters),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        ]

    kernel32 = _windows_ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = ctypes.c_void_p
    kernel32.SetInformationJobObject.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    kernel32.SetInformationJobObject.restype = ctypes.c_int
    kernel32.AssignProcessToJobObject.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    kernel32.AssignProcessToJobObject.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(
            _windows_ctypes.get_last_error(),
            "Windows-Jobobjekt konnte nicht angelegt werden",
        )
    limits = ExtendedLimits()
    # Nur KILL_ON_JOB_CLOSE (0x2000). JOB_OBJECT_LIMIT_JOB_MEMORY (0x200) mit
    # ``job_memory`` ist mit der Speichergrenze gefallen (siehe Docstring).
    limits.basic.limit_flags = 0x00002000
    if not kernel32.SetInformationJobObject(
        job,
        9,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    ):
        error = _windows_ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise OSError(error, "Windows-Jobgrenzen konnten nicht gesetzt werden")
    process_handle = ctypes.c_void_p(int(process._handle))  # type: ignore[attr-defined]
    if not kernel32.AssignProcessToJobObject(job, process_handle):
        error = _windows_ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise OSError(error, "Prozess konnte nicht an das Windows-Jobobjekt gebunden werden")
    process._solidon_job = int(job)  # type: ignore[attr-defined]


def _attach_process_boundary(process: subprocess.Popen[Any]) -> None:
    if os.name == "nt":
        _attach_windows_job(process)


def _resume_windows_process(process_id: int) -> None:
    """Setzt den ersten Thread eines sicher gebunden gestarteten Prozesses fort."""

    class ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("size", ctypes.c_uint32),
            ("usage", ctypes.c_uint32),
            ("thread_id", ctypes.c_uint32),
            ("owner_process_id", ctypes.c_uint32),
            ("base_priority", ctypes.c_long),
            ("delta_priority", ctypes.c_long),
            ("flags", ctypes.c_uint32),
        ]

    kernel32 = _windows_ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = (ctypes.c_uint32, ctypes.c_uint32)
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel32.Thread32First.argtypes = (ctypes.c_void_p, ctypes.POINTER(ThreadEntry))
    kernel32.Thread32First.restype = ctypes.c_int
    kernel32.Thread32Next.argtypes = (ctypes.c_void_p, ctypes.POINTER(ThreadEntry))
    kernel32.Thread32Next.restype = ctypes.c_int
    kernel32.OpenThread.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.OpenThread.restype = ctypes.c_void_p
    kernel32.ResumeThread.argtypes = (ctypes.c_void_p,)
    kernel32.ResumeThread.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)

    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)
    if snapshot in (None, ctypes.c_void_p(-1).value):
        raise OSError(
            _windows_ctypes.get_last_error(),
            "Prozess-Thread konnte nicht ermittelt werden",
        )
    try:
        entry = ThreadEntry(size=ctypes.sizeof(ThreadEntry))
        found = bool(kernel32.Thread32First(snapshot, ctypes.byref(entry)))
        while found:
            if entry.owner_process_id == process_id:
                thread = kernel32.OpenThread(0x0002, False, entry.thread_id)
                if not thread:
                    raise OSError(
                        _windows_ctypes.get_last_error(),
                        "Prozess-Thread konnte nicht geöffnet werden",
                    )
                try:
                    if kernel32.ResumeThread(thread) == 0xFFFFFFFF:
                        raise OSError(
                            _windows_ctypes.get_last_error(),
                            "Prozess-Thread konnte nicht fortgesetzt werden",
                        )
                finally:
                    kernel32.CloseHandle(thread)
                return
            found = bool(kernel32.Thread32Next(snapshot, ctypes.byref(entry)))
    finally:
        kernel32.CloseHandle(snapshot)
    raise OSError("Der angehaltene Prozess besaß keinen auffindbaren Thread")


def _resume_process_boundary(process: subprocess.Popen[Any]) -> None:
    if os.name == "nt":
        _resume_windows_process(process.pid)


def _close_windows_job(process: subprocess.Popen[Any]) -> bool:
    job = getattr(process, "_solidon_job", None)
    if job is None:
        return False
    delattr(process, "_solidon_job")
    kernel32 = _windows_ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int
    kernel32.CloseHandle(ctypes.c_void_p(job))
    return True


def _kill_process_group(process_id: int, *, force: bool) -> None:
    """Sendet auf POSIX das gewählte Signal an die gesamte Prozessgruppe."""
    kill_group = cast(Callable[[int, int], None], vars(os)["killpg"])
    signal_name = "SIGKILL" if force else "SIGTERM"
    kill_group(process_id, int(getattr(signal, signal_name)))


def _group_alive(process_id: int) -> bool:
    """Ob in der Prozessgruppe noch jemand lebt — Signal 0 fragt nur nach."""
    kill_group = cast(Callable[[int, int], None], vars(os)["killpg"])
    try:
        kill_group(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _finish_process_group(process_id: int, grace_seconds: float) -> None:
    """Wartet die Schonfrist auf die Nachkommen und beendet, was sie übersteht."""
    deadline = time.monotonic() + grace_seconds
    while _group_alive(process_id):
        if time.monotonic() >= deadline:
            with suppress(ProcessLookupError):
                _kill_process_group(process_id, force=True)
            return
        time.sleep(PROCESS_POLL_SECONDS)


def _stop_remaining_descendants(process: subprocess.Popen[Any]) -> None:
    """Schließt nach normalem Elternende ebenfalls den zugehörigen Prozessbaum."""
    if os.name == "nt":
        _close_windows_job(process)
        return
    with suppress(ProcessLookupError):
        _kill_process_group(process.pid, force=False)
    time.sleep(PROCESS_POLL_SECONDS)
    with suppress(ProcessLookupError):
        _kill_process_group(process.pid, force=True)


def terminate_process_tree(
    process: subprocess.Popen[Any],
    *,
    grace_seconds: float = PROCESS_STOP_SECONDS,
) -> None:
    """Beendet die beim Start angelegte Prozessgruppe vollständig."""
    if os.name == "nt":
        if _close_windows_job(process):
            try:
                process.wait(timeout=grace_seconds)
                return
            except subprocess.TimeoutExpired:
                pass
        # Windows kennt für Konsolenprozesse kein verlässliches höfliches
        # Signal an den ganzen Baum. ``taskkill /T /F`` trifft die Nachkommen,
        # solange der Elternprozess noch da ist; erst den Elternprozess allein
        # zu beenden würde sie zu Waisen machen und die Baumkante verlieren.
        _taskkill(process.pid, force=True)
        try:
            process.wait(timeout=grace_seconds)
            return
        except subprocess.TimeoutExpired:
            pass
    else:
        with suppress(ProcessLookupError):
            _kill_process_group(process.pid, force=False)
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                _kill_process_group(process.pid, force=True)
        else:
            # **Der Elternprozess ist weg — seine Gruppe nicht unbedingt.** Ein
            # Nachkomme, der SIGTERM abfängt oder länger aufräumt, überlebte
            # den zugesagten Abbruch, weil hier nach dem Ende des Elternteils
            # sofort zurückgekehrt wurde (Gesamtreview 05.09.2026, CORE-23).
            # Gewartet wird auf die Gruppe, und wer die Schonfrist übersteht,
            # bekommt SIGKILL.
            _finish_process_group(process.pid, grace_seconds)
            return
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        # Letzter Rückfall für eine Plattform, auf der die Gruppenbeendigung
        # nicht verfügbar war. Der Normalweg oben trifft den ganzen Baum.
        process.kill()
        process.wait(timeout=grace_seconds)


def _drain(
    stream: Any,
    target: bytearray,
    state: dict[str, int],
    lock: threading.Lock,
    exceeded: threading.Event,
    limit: int,
) -> None:
    """Leert ein Prozessrohr, speichert aber nie mehr als die Gesamtgrenze."""
    try:
        while True:
            read = getattr(stream, "read1", stream.read)
            chunk = read(_READ_SIZE)
            if not chunk:
                return
            with lock:
                remaining = max(0, limit - state["size"])
                if remaining:
                    target.extend(chunk[:remaining])
                    state["size"] += min(len(chunk), remaining)
                if len(chunk) > remaining:
                    exceeded.set()
    except OSError, ValueError:
        return


def _feed_chunks(
    stream: Any,
    feed: queue.Queue[bytes | None],
    stopped: threading.Event,
) -> None:
    """Liest ein gemeinsames Ausgaberohr in festen, speicherbegrenzten Stücken."""
    try:
        read = getattr(stream, "read1", stream.read)
        while not stopped.is_set() and (chunk := read(_READ_SIZE)):
            while not stopped.is_set():
                try:
                    feed.put(chunk, timeout=PROCESS_POLL_SECONDS)
                    break
                except queue.Full:
                    continue
    except OSError, ValueError:
        pass
    finally:
        while not stopped.is_set():
            try:
                feed.put(None, timeout=PROCESS_POLL_SECONDS)
                break
            except queue.Full:
                continue


def _emit_lines(text: str, callback: Callable[[str], None]) -> str:
    """Meldet vollständige Zeilen und gibt den noch unvollständigen Rest zurück."""
    normalized = text.replace("\r", "\n")
    *complete, pending = normalized.split("\n")
    for raw in complete:
        line = raw.strip()
        if line:
            callback(line)
    return pending


class _CancellationWatcher:
    """Fragt einen möglicherweise blockierenden Abbruchmelder nebenläufig ab."""

    def __init__(self, callback: Callable[[], bool] | None) -> None:
        self.cancelled = threading.Event()
        self.stopped = threading.Event()
        self.problem: BaseException | None = None
        self._callback = callback
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._callback is None:
            return
        self._thread = threading.Thread(
            target=self._watch,
            daemon=True,
            name="process-cancellation",
        )
        self._thread.start()

    def _watch(self) -> None:
        assert self._callback is not None
        while not self.stopped.is_set():
            try:
                if self._callback():
                    self.cancelled.set()
                    return
            except BaseException as problem:
                self.problem = problem
                return
            self.stopped.wait(PROCESS_POLL_SECONDS)

    def stop(self) -> None:
        self.stopped.set()
        if self._thread is not None:
            self._thread.join(PROCESS_STOP_SECONDS)


class _LineDispatcher:
    """Führt Fortschrittsrückrufe aus, ohne die Sicherheitsuhr anzuhalten."""

    def __init__(self, callback: Callable[[str], None], output_limit: int) -> None:
        self._callback = callback
        # Selbst beim ungünstigsten gültigen Strom ``x\n`` entstehen nicht
        # mehr als halb so viele Zeilen wie erlaubte Bytes. Damit ist die
        # Warteschlange ausdrücklich begrenzt, ohne einen schnellen Prozess
        # nur wegen eines kurzen Scheduling-Abstands abzubrechen.
        self._feed: queue.Queue[str | None] = queue.Queue(maxsize=output_limit // 2 + 2)
        self.done = threading.Event()
        self.problem: BaseException | None = None
        self._thread = threading.Thread(
            target=self._dispatch,
            daemon=True,
            name="process-callback",
        )

    def start(self) -> None:
        self._thread.start()

    def submit(self, line: str) -> None:
        self._feed.put_nowait(line)

    def finish(self) -> None:
        self._feed.put_nowait(None)

    def _dispatch(self) -> None:
        try:
            while (line := self._feed.get()) is not None:
                self._callback(line)
        except BaseException as problem:
            self.problem = problem
        finally:
            self.done.set()


def run_limited(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
    output_limit: int = DEFAULT_OUTPUT_LIMIT,
    cancelled: Callable[[], bool] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Führt einen Befehl mit Zeit-, Ausgabe- und Prozessbaumgrenze aus."""
    if timeout <= 0:
        raise ValueError("timeout")
    if output_limit <= 0:
        raise ValueError("output_limit")

    launched = list(command)
    process = subprocess.Popen(
        launched,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        env=trusted_environment(),
        **process_group_options(no_window=True, suspended=True),
    )
    assert process.stdout is not None
    assert process.stderr is not None
    try:
        _attach_process_boundary(process)
        _resume_process_boundary(process)
    except BaseException:
        terminate_process_tree(process)
        process.stdout.close()
        process.stderr.close()
        raise

    stdout = bytearray()
    stderr = bytearray()
    state = {"size": 0}
    lock = threading.Lock()
    exceeded = threading.Event()
    readers = (
        threading.Thread(
            target=_drain,
            args=(process.stdout, stdout, state, lock, exceeded, output_limit),
            daemon=True,
            name="process-stdout",
        ),
        threading.Thread(
            target=_drain,
            args=(process.stderr, stderr, state, lock, exceeded, output_limit),
            daemon=True,
            name="process-stderr",
        ),
    )
    for reader in readers:
        reader.start()

    deadline = time.monotonic() + timeout
    problem: BaseException | None = None
    cancellation = _CancellationWatcher(cancelled)
    cancellation.start()
    while process.poll() is None:
        if cancellation.problem is not None:
            problem = cancellation.problem
            break
        if cancellation.cancelled.is_set():
            problem = ProcessCancelled()
            break
        if exceeded.is_set():
            problem = ProcessOutputLimitExceeded(launched, output_limit)
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            problem = subprocess.TimeoutExpired(launched, timeout)
            break
        time.sleep(min(PROCESS_POLL_SECONDS, remaining))

    cancellation.stop()
    if problem is not None or exceeded.is_set():
        terminate_process_tree(process)
    else:
        _stop_remaining_descendants(process)
    for reader in readers:
        reader.join(PROCESS_STOP_SECONDS)
    for stream in (process.stdout, process.stderr):
        stream.close()

    if problem is not None:
        raise problem
    if exceeded.is_set():
        raise ProcessOutputLimitExceeded(launched, output_limit)
    return subprocess.CompletedProcess(launched, process.returncode, bytes(stdout), bytes(stderr))


def run_stream_limited(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
    output_limit: int,
    on_line: Callable[[str], None],
    cancelled: Callable[[], bool] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Führt einen Befehl begrenzt aus und reicht vollständige Ausgabezeilen weiter."""
    if timeout <= 0:
        raise ValueError("timeout")
    if output_limit <= 0:
        raise ValueError("output_limit")

    launched = list(command)
    process = subprocess.Popen(
        launched,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=trusted_environment(),
        **process_group_options(no_window=True, suspended=True),
    )
    assert process.stdout is not None
    try:
        _attach_process_boundary(process)
        _resume_process_boundary(process)
    except BaseException:
        terminate_process_tree(process)
        process.stdout.close()
        raise
    feed: queue.Queue[bytes | None] = queue.Queue(maxsize=16)
    stopped = threading.Event()
    reader = threading.Thread(
        target=_feed_chunks,
        args=(process.stdout, feed, stopped),
        daemon=True,
        name="process-output",
    )
    reader.start()
    dispatcher = _LineDispatcher(on_line, output_limit)
    dispatcher.start()
    cancellation = _CancellationWatcher(cancelled)
    cancellation.start()

    output = bytearray()
    pending = ""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    deadline = time.monotonic() + timeout
    problem: BaseException | None = None
    finished = False
    dispatcher_finished = False
    try:
        while not finished:
            if cancellation.problem is not None:
                problem = cancellation.problem
                break
            if cancellation.cancelled.is_set():
                problem = ProcessCancelled()
                break
            if dispatcher.problem is not None:
                problem = dispatcher.problem
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                problem = subprocess.TimeoutExpired(launched, timeout)
                break
            try:
                chunk = feed.get(timeout=min(PROCESS_POLL_SECONDS, remaining))
            except queue.Empty:
                continue
            if chunk is None:
                pending += decoder.decode(b"", final=True)
                finished = True
                continue
            if len(output) + len(chunk) > output_limit:
                problem = ProcessOutputLimitExceeded(launched, output_limit)
                break
            output.extend(chunk)
            decoded = decoder.decode(chunk)
            pending = _emit_lines(pending + decoded, dispatcher.submit)
        if problem is None:
            tail = pending.strip()
            if tail:
                dispatcher.submit(tail)
            dispatcher.finish()
            dispatcher_finished = True
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not dispatcher.done.wait(remaining):
                problem = subprocess.TimeoutExpired(launched, timeout)
            elif dispatcher.problem is not None:
                problem = dispatcher.problem
    finally:
        cancellation.stop()
        if not dispatcher_finished:
            dispatcher.finish()
        stopped.set()
        if problem is not None:
            terminate_process_tree(process)
        else:
            try:
                process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired as expired:
                problem = expired
                terminate_process_tree(process)
            else:
                _stop_remaining_descendants(process)
        reader.join(PROCESS_STOP_SECONDS)
        process.stdout.close()

    if problem is not None:
        raise problem
    return subprocess.CompletedProcess(launched, process.returncode, bytes(output), b"")
