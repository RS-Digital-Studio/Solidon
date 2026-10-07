"""Echte Prozesseigenschaften des Kernelhelfers, ohne Fenster oder Leistungsbudget.

RM-298(d): Ein aktiver Kernaufruf liest weder Leitung noch Elternzustand.
Sein Ende mit einem hart beendeten Elternprozess muss daher unter Windows
vom Jobobjekt kommen. Zugesichert wird, dass das Betriebssystem dieses Ende
eingeleitet hat, nicht wie schnell es abgeschlossen ist: Der rechnende Helfer
steht eine Klasse tiefer, und unter fremder Volllast bekommen seine Fäden die
Zeitscheibe, die jedes Ende braucht, erst nach Sekunden (RM-474). Die Priorität
wird nach dem wirklichen ``serve``-Start beim Betriebssystem abgefragt, statt
nur den Aufruf des Setzers zu zählen.

Nur für die negativen Gegenproben setzt der Aufrufer
``SOLIDON_TEST_KERNEL_LIFECYCLE_FAULT`` auf ``no-binding`` oder ``no-priority``.
Beide Varianten lassen dieselben Zusicherungen absichtlich scheitern; sie
verändern ausschließlich das Test-Elternskript beziehungsweise den Testhelfer.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from app.core import process as process_boundary
from app.core.geom import kernel_jobs, kernel_process

_ROOT = Path(__file__).resolve().parent.parent
_START_SECONDS = 30.0
_STOP_SECONDS = 10.0
_BLOCK_SECONDS = 120.0
_FAULT = "SOLIDON_TEST_KERNEL_LIFECYCLE_FAULT"
_BLOCK_JOB = "test_lifecycle_blocked"
_PRIORITY_JOB = "test_lifecycle_priority"
_PRIORITY_BEFORE: int | None = None


def _windows_api() -> Any:
    """Die benötigten Windows-Funktionen mit Griffen in voller Zeigerbreite."""
    windows: Any = ctypes
    kernel32 = windows.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = ()
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.DuplicateHandle.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint32,
    )
    kernel32.DuplicateHandle.restype = ctypes.c_int
    kernel32.GetProcessId.argtypes = (ctypes.c_void_p,)
    kernel32.GetProcessId.restype = ctypes.c_uint32
    kernel32.GetPriorityClass.argtypes = (ctypes.c_void_p,)
    kernel32.GetPriorityClass.restype = ctypes.c_uint32
    kernel32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.SetPriorityClass.restype = ctypes.c_int
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.TerminateProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int
    return kernel32


def _windows_error(message: str) -> OSError:
    windows: Any = ctypes
    return OSError(windows.get_last_error(), message)


class _BasicInformation(ctypes.Structure):
    """``PROCESS_BASIC_INFORMATION``, Felder in voller Zeigerbreite."""

    _fields_ = [
        ("exit_status", ctypes.c_long),
        ("peb", ctypes.c_void_p),
        ("affinity", ctypes.c_size_t),
        ("base_priority", ctypes.c_long),
        ("pid", ctypes.c_size_t),
        ("parent_pid", ctypes.c_size_t),
    ]


class _ExtendedInformation(ctypes.Structure):
    """``PROCESS_EXTENDED_BASIC_INFORMATION``; ``flags`` Bit 2 ist ``IsProcessDeleting``."""

    _fields_ = [("size", ctypes.c_size_t), ("basic", _BasicInformation), ("flags", ctypes.c_uint32)]


#: ``IsProcessDeleting``: Das Betriebssystem hat das Ende des Prozesses
#: eingeleitet (Jobobjekt, ``TerminateProcess``); fort ist er, sobald jeder
#: seiner Fäden es abgeschlossen hat.
_PROCESS_DELETING = 0x4


def _process_deleting(handle: int) -> bool:
    """Liest ``IsProcessDeleting`` über ``NtQueryInformationProcess`` (Klasse 0, erweitert)."""
    windows: Any = ctypes
    ntdll = windows.WinDLL("ntdll")
    ntdll.NtQueryInformationProcess.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    )
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long
    information = _ExtendedInformation()
    information.size = ctypes.sizeof(information)
    written = ctypes.c_uint32()
    status = ntdll.NtQueryInformationProcess(
        handle, 0, ctypes.byref(information), ctypes.sizeof(information), ctypes.byref(written)
    )
    if status != 0 or written.value != ctypes.sizeof(information):
        raise OSError(f"NtQueryInformationProcess meldete {status & 0xFFFFFFFF:#010x}.")
    return bool(information.flags & _PROCESS_DELETING)


def _priority_class(kernel32: Any, handle: int | None) -> int:
    priority = int(kernel32.GetPriorityClass(handle))
    if not priority:
        raise _windows_error("Die Prozesspriorität konnte nicht gelesen werden.")
    return priority


class _HeldWindowsProcess:
    """Ein duplizierter Prozessgriff statt einer erneut aufzulösenden PID."""

    def __init__(self, kernel32: Any, handle: int) -> None:
        self._api = kernel32
        self._handle = handle

    @property
    def pid(self) -> int:
        pid = int(self._api.GetProcessId(self._handle))
        if not pid:
            raise _windows_error("Der gehaltene Prozessgriff konnte nicht geprüft werden.")
        return pid

    def ended(self, seconds: float = 0.0) -> bool:
        result = int(self._api.WaitForSingleObject(self._handle, int(seconds * 1000)))
        if result == 0:
            return True
        if result == 0x00000102:  # WAIT_TIMEOUT
            return False
        raise _windows_error("Das Prozessende konnte nicht abgefragt werden.")

    def ending(self) -> bool:
        """Ob das Betriebssystem das Ende eingeleitet hat — oder es schon vorüber ist."""
        return self.ended() or _process_deleting(self._handle)

    def stop(self) -> None:
        """Beendet exakt diesen Prozess; am Helfer ausschließlich beim Testabbau.

        Vorher in normaler Klasse wie ``process.hurry_helper``: Ein Ende braucht
        für jeden Faden eine Zeitscheibe, und ein zurückgestellter Helfer bekommt
        sie unter Volllast erst nach Sekunden (RM-474).
        """
        if self.ended():
            return
        self._api.SetPriorityClass(self._handle, 0x00000020)  # NORMAL_PRIORITY_CLASS
        if not self._api.TerminateProcess(self._handle, 1):
            problem = _windows_error("Der Testprozess konnte nicht beendet werden.")
            # Ein schon eingeleitetes Ende (Jobobjekt) lehnt TerminateProcess
            # mit 5 ab, bis der Griff signalisiert ist.
            if not self.ended(_STOP_SECONDS):
                raise problem
        assert self.ended(_STOP_SECONDS), "Der Testprozess blieb beim Abbau am Leben."

    def close(self) -> None:
        if not self._api.CloseHandle(self._handle):
            raise _windows_error("Der gehaltene Prozessgriff konnte nicht geschlossen werden.")


def publish_process_handles_for_test(helper: Any, receiver_pid: int, path: Path) -> None:
    """Übergibt wirkliche Eltern-/Helfergriffe vom Test-Elternprozess an seinen Prüfer.

    Der Empfänger lebt während der ganzen Probe. Die PID dient nur dazu,
    dessen Griffbereich zu öffnen. Elternprozess und Helfer werden nie über
    eine PID wiedergefunden. Dupliziert werden Prozessgriffe, niemals der Griff
    des Jobobjekts. Der echte Elternprozess kann sich vom ``.venv``-Launcher
    unterscheiden, den ``Popen`` gestartet hat.
    """
    kernel32 = _windows_api()
    receiver = kernel32.OpenProcess(0x00000040, False, receiver_pid)  # PROCESS_DUP_HANDLE
    if not receiver:
        raise _windows_error("Der Testprozess konnte keinen Helfergriff empfangen.")
    made: list[int] = []
    try:
        try:
            for handle in (helper.sentinel, kernel32.GetCurrentProcess()):
                duplicate = ctypes.c_void_p()
                # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
                # | PROCESS_SET_INFORMATION (Klasse beim Abbau) | PROCESS_TERMINATE.
                if not kernel32.DuplicateHandle(
                    kernel32.GetCurrentProcess(),
                    handle,
                    receiver,
                    ctypes.byref(duplicate),
                    0x00101201,
                    False,
                    0,
                ):
                    raise _windows_error(
                        "Der wirkliche Prozessgriff konnte nicht dupliziert werden."
                    )
                assert duplicate.value is not None
                made.append(int(duplicate.value))
            _write_mark(
                path,
                {
                    "handle": made[0],
                    "pid": helper.pid,
                    "parent_handle": made[1],
                    "parent_pid": os.getpid(),
                },
            )
        except BaseException:
            # Noch nicht veröffentlichte Griffe bleiben beim Absender:
            # DUPLICATE_CLOSE_SOURCE schließt den Griff im Empfängerprozess.
            for handle in made:
                kernel32.DuplicateHandle(receiver, handle, None, None, 0, False, 1)
            raise
    finally:
        kernel32.CloseHandle(receiver)


def _write_mark(path: Path, values: dict[str, int]) -> None:
    """Veröffentlicht kleine Meldungen vollständig, ohne gepuffertes Ausgaberohr."""
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(values), encoding="utf-8")
    pending.replace(path)


def _blocked_job(_arrays: Any, values: Any, _check: Any) -> tuple[dict, dict]:
    """Ein gestarteter Kernaufruf ohne Elternprüfung oder Rückkehr zur Leitung."""
    _write_mark(Path(values["entered"]), {"pid": os.getpid(), "parent": os.getppid()})
    threading.Event().wait(_BLOCK_SECONDS)
    return {}, {}


def serve_blocked_lifecycle_probe(connection: Any) -> None:
    """Registriert nur die Testrechnung und geht dann in den echten Helferdienst."""
    kernel_jobs.JOBS[_BLOCK_JOB] = _blocked_job
    kernel_jobs.serve(connection)


_PARENT = textwrap.dedent(
    """
    import os
    import sys
    import threading
    import traceback
    from pathlib import Path

    sys.path.insert(0, sys.argv[1])
    from app.core import process as process_boundary
    from app.core.geom import kernel_jobs, kernel_process
    from tests.test_kernel_process_lifecycle import (
        publish_process_handles_for_test,
        serve_blocked_lifecycle_probe,
    )

    def main():
        folder = Path(sys.argv[2])
        if sys.argv[4] == "no-binding":
            process_boundary.bind_helper = lambda _child: None

        def no_local_fallback(*_args):
            raise AssertionError("Die Testrechnung muss im wirklichen Helfer laufen.")

        kernel_process._SERVE = serve_blocked_lifecycle_probe
        kernel_jobs.JOBS["test_lifecycle_blocked"] = no_local_fallback
        try:
            assert kernel_process.warm_up(), "Der echte Helfer muss bereit sein."
            helper, = kernel_process.processes()
            publish_process_handles_for_test(helper, int(sys.argv[3]), folder / "helper.json")

            def calculate():
                try:
                    kernel_process.run(
                        "test_lifecycle_blocked", {},
                        {"entered": str(folder / "entered.json")},
                        weight=kernel_process.OFFLOAD_ABOVE + 1,
                    )
                except BaseException:
                    traceback.print_exc()
                    os._exit(2)

            worker = threading.Thread(target=calculate, daemon=True)
            worker.start()
            worker.join(120.0)
        finally:
            kernel_process.shutdown()

    if __name__ == "__main__":
        main()
    """
)


def _read_mark(path: Path, deadline: float) -> dict[str, int]:
    """Liest eine Meldung, auch während ihr Umbenennen noch nicht ganz abgeschlossen ist.

    Gleich nach ``Path.replace`` lehnt Windows das Öffnen des neuen Namens
    gelegentlich mit einer Freigabeverletzung (32) ab, als ``PermissionError``
    — gemessen in drei von acht Läufen 2 bis 30 von 3000 Öffnungen
    (``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/elternende_umbenennen.py``).
    """
    while True:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def _wait_mark(path: Path, parent: subprocess.Popen, diagnostics: Path) -> dict[str, int]:
    """Wartet begrenzt auf die vollständige Meldung und erkennt frühen Elternabbruch."""
    deadline = time.monotonic() + _START_SECONDS
    while not path.is_file():
        assert parent.poll() is None, diagnostics.read_text(encoding="utf-8", errors="replace")
        assert time.monotonic() < deadline, f"Die Testmeldung {path.name} kam nicht an."
        time.sleep(0.02)
    return _read_mark(path, deadline)


@pytest.mark.skipif(os.name != "nt", reason="Der aktive Todesfall prüft das Windows-Jobobjekt.")
def test_active_helper_ends_with_a_killed_parent(tmp_path: Path) -> None:
    """Nach bestätigtem Recheneintritt beendet nur das innere Jobobjekt den Helfer.

    Das äußere Jobobjekt bleibt bis nach der Zusicherung beim Test geöffnet:
    Es sichert ausschließlich den Abbau auch bei Start- und Prüfungsfehlern.
    Die Blockierfrist liegt weit jenseits aller Start-/Endefristen der Probe.

    Zugesichert wird das eingeleitete Ende (``IsProcessDeleting``), nicht sein
    Abschluss in einer Frist: Unter fremder Volllast war der Helfer in
    ``BELOW_NORMAL`` bis zu 19,5 s nach dem Elternende noch da, in 21 von 23
    Läufen über 9 s; in normaler Klasse unter einer Sekunde, auf ruhiger
    Maschine in beiden nach Millisekunden. Eingeleitet war das Ende in jedem
    Lauf, sobald der Elternprozess signalisiert war, 06.10.2026
    (``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/elternende.py``).
    Ohne inneres Jobobjekt bleibt das Merkmal aus.
    """
    kernel32 = _windows_api()
    script = tmp_path / "parent.py"
    script.write_text(_PARENT, encoding="utf-8")
    diagnostics = tmp_path / "parent.log"
    helper: _HeldWindowsProcess | None = None
    controlled_parent: _HeldWindowsProcess | None = None
    with diagnostics.open("wb") as output:
        parent = subprocess.Popen(
            [
                sys.executable,
                str(script),
                str(_ROOT),
                str(tmp_path),
                str(os.getpid()),
                os.environ.get(_FAULT, ""),
            ],
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=tmp_path,
            **process_boundary.process_group_options(no_window=True, suspended=True),
        )
        try:
            process_boundary._attach_process_boundary(parent)
            process_boundary._resume_process_boundary(parent)
            announced = _wait_mark(tmp_path / "helper.json", parent, diagnostics)
            helper = _HeldWindowsProcess(kernel32, announced["handle"])
            controlled_parent = _HeldWindowsProcess(kernel32, announced["parent_handle"])
            assert helper.pid == announced["pid"]
            assert controlled_parent.pid == announced["parent_pid"]
            assert helper.pid != controlled_parent.pid
            entered = _wait_mark(tmp_path / "entered.json", parent, diagnostics)
            assert entered == {"pid": helper.pid, "parent": controlled_parent.pid}
            assert not helper.ended(), "Die Testrechnung muss beim Elternende noch laufen."
            assert getattr(parent, "_solidon_job", None), "Der Abbaugriff bleibt beim Test."

            controlled_parent.stop()
            parent.wait(_STOP_SECONDS)
            # Das Jobobjekt schließt mit dem Griff, den das Elternende abräumt;
            # die Frist begrenzt nur das Warten der Gegenprobe ohne Bindung.
            deadline = time.monotonic() + _STOP_SECONDS
            while not helper.ending() and time.monotonic() < deadline:
                time.sleep(0.02)
            ending = helper.ending()
            _write_mark(
                tmp_path / "finished.json",
                {"helper_ending": int(ending), "helper_ended": int(helper.ended())},
            )
            assert ending, (
                "Der aktive Helfer überlebt das harte Elternende; das innere Jobobjekt fehlt."
            )
        finally:
            try:
                process_boundary._close_windows_job(parent)
                if parent.poll() is None:
                    parent.kill()
                parent.wait(_STOP_SECONDS)
            finally:
                if helper is None and (tmp_path / "helper.json").is_file():
                    announced = _read_mark(
                        tmp_path / "helper.json", time.monotonic() + _STOP_SECONDS
                    )
                    helper = _HeldWindowsProcess(kernel32, announced["handle"])
                    controlled_parent = _HeldWindowsProcess(kernel32, announced["parent_handle"])
                try:
                    if helper is not None:
                        try:
                            helper.stop()
                            _write_mark(tmp_path / "cleanup.json", {"helper_ended": 1})
                        finally:
                            helper.close()
                finally:
                    if controlled_parent is not None:
                        try:
                            controlled_parent.stop()
                        finally:
                            controlled_parent.close()


def _current_priority() -> int:
    if os.name == "nt":
        kernel32 = _windows_api()
        return _priority_class(kernel32, kernel32.GetCurrentProcess())
    return os.getpriority(os.PRIO_PROCESS, 0)


def _priority_job(_arrays: Any, _values: Any, _check: Any) -> tuple[dict, dict]:
    return {}, {"pid": os.getpid(), "before": _PRIORITY_BEFORE, "during": _current_priority()}


def _serve_priority_probe(connection: Any) -> None:
    """Behält die Anfangspriorität und registriert eine kleine wirkliche Rechnung."""
    global _PRIORITY_BEFORE
    _PRIORITY_BEFORE = _current_priority()
    if os.environ.get(_FAULT) == "no-priority":
        kernel_jobs._yield_to_the_window = lambda: None
    kernel_jobs.JOBS[_PRIORITY_JOB] = _priority_job
    kernel_jobs.serve(connection)


@pytest.mark.skipif(
    os.name != "nt" and not (hasattr(os, "nice") and hasattr(os, "getpriority")),
    reason="Die Plattform stellt keine abfragbare Prozesspriorität bereit.",
)
def test_helper_has_lower_os_priority_after_serve(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der normale Helferdienst stellt den tatsächlichen Rechenprozess zurück.

    Unter Windows nur, während er rechnet (RM-474): Untätig antwortet er in
    normaler Klasse, sonst verhungern Annahme und Ende unter fremder Volllast.
    """
    parent_priority = _current_priority()
    if os.name == "nt" and parent_priority in (0x00000040, 0x00004000):
        pytest.skip("Der Testprozess läuft selbst schon unter normaler Windows-Priorität.")
    if os.name != "nt" and parent_priority == 19:
        pytest.skip("Die geerbte Priorität ist schon die niedrigste POSIX-Priorität.")
    pool = kernel_process._Pool()
    monkeypatch.setattr(kernel_process, "_POOL", pool)
    monkeypatch.setattr(kernel_process, "_SERVE", _serve_priority_probe)
    monkeypatch.setitem(kernel_jobs.JOBS, _PRIORITY_JOB, _priority_job)
    result: list[Any] = []
    problems: list[BaseException] = []

    def calculate() -> None:
        try:
            result.append(
                kernel_process.run(_PRIORITY_JOB, {}, {}, weight=kernel_process.OFFLOAD_ABOVE + 1)
            )
        except BaseException as problem:
            problems.append(problem)

    worker = threading.Thread(target=calculate, daemon=True)
    helper: Any = None
    try:
        worker.start()
        worker.join(_START_SECONDS)
        assert not worker.is_alive(), "Die kleine Prioritätsprobe muss begrenzt antworten."
        if problems:
            raise problems[0]
        assert len(result) == 1
        arrays, reported = result[0]
        assert not arrays and reported["pid"] != os.getpid(), "run muss wirklich auslagern."
        (helper,) = kernel_process.processes()
        assert helper.pid == reported["pid"] and helper.is_alive()
        before, during = reported["before"], reported["during"]
        assert isinstance(before, int) and isinstance(during, int)
        if os.name == "nt":
            actual = _priority_class(_windows_api(), helper.sentinel)
        else:
            actual = os.getpriority(os.PRIO_PROCESS, helper.pid)
        _write_mark(
            tmp_path / "priority.json",
            {
                "pid": helper.pid,
                "parent_pid": os.getpid(),
                "parent_priority": parent_priority,
                "before": before,
                "during": during,
                "actual": actual,
            },
        )
        if os.name == "nt":
            assert during == 0x00004000, (
                "Der rechnende Helfer muss BELOW_NORMAL_PRIORITY_CLASS besitzen."
            )
            assert actual == 0x00000020, "Der untätige Helfer antwortet in normaler Klasse."
            assert parent_priority in (0x00000020, 0x00008000, 0x00000080, 0x00000100)
        else:
            assert actual > before and actual > parent_priority, (
                "Der wirkliche Helfer muss nach serve einen höheren nice-Wert als vorher "
                "und als sein Elternprozess besitzen."
            )
    finally:
        try:
            kernel_process.shutdown()
            worker.join(_STOP_SECONDS)
            assert not worker.is_alive(), "Der Rechenfaden blieb nach dem Helferabbau hängen."
        finally:
            if helper is not None and not helper.is_alive():
                helper.close()
                _write_mark(tmp_path / "cleanup.json", {"helper_ended": 1})
