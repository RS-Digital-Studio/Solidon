"""Endet ein rechnender Hilfsprozess mit dem hart beendeten Elternprozess? (RM-298 d)

Im Entwicklungstor fiel ``test_active_helper_ends_with_a_killed_parent`` unter
fremder Last (Agenten-Suite, mehrere Tore) gelegentlich rot: Der Helfer war
zehn Sekunden nach dem Elternende noch da. Die Sonde fährt denselben Ablauf
wie der Test — Elternskript in einem äußeren Jobobjekt, Helfer über
``kernel_process.warm_up`` mit dem inneren Jobobjekt, Rechnung, die blockiert,
Elternprozess per ``TerminateProcess`` — und misst statt zuzusichern: wann der
Helfer fort ist und ob das Betriebssystem sein Ende eingeleitet hat
(``IsProcessDeleting`` aus ``NtQueryInformationProcess``), sofort, nach 1 s und
nach 10 s.

Varianten (verschränkt zu fahren, je Lauf ein Prozess):
  real             wie ausgeliefert: der Helfer rechnet in BELOW_NORMAL
  normal-priority  der Helfer bleibt während der Rechnung in normaler Klasse
  no-binding       ohne inneres Jobobjekt (Gegenprobe)

--crowd K: der Helfer kurz vor dem Elternende auf die logische CPU 2 gelegt,
dazu K Endlosschleifen normaler Priorität auf dieselbe CPU — örtliche Volllast,
ohne die übrigen Kerne anzufassen. --pin MASKE: Affinität der Sonde (vererbt an
Elternskript und Helfer). --observe S: Beobachtungsfrist (Vorgabe 150 s).
--hurry: lebt der Helfer am Ende der Frist noch, hebt die Sonde ihn auf normale
Klasse und misst, wie schnell das eingeleitete Ende dann abschließt.

Aufruf (Windows): python elternende.py <baum> <variante> <ergebnisdatei> [...]
Exit: 0 Helfer binnen 10 s fort, 1 später fort, 3 am Ende der Frist noch am
Leben, 2 Sondenfehler. Je Lauf eine JSON-Zeile in die Ergebnisdatei.

Abgelegt ist die gemessene Fassung mit vier Anpassungen für die Ablage: Baum als
erstes Argument statt eines festen Pfads, Importname ``elternende_helfer``,
Tempordner des Systems, und ``observe``/``hurry`` stehen in jeder Zeile. Die
Läufe in ``elternende-laeufe.jsonl`` führen die Rohdateien je Reihe zusammen
(Feld ``reihe``). Zeile 1 lief mit der ersten Fassung, die eine Meldung noch
mit einem einzelnen ``read_text`` las (daher ihr Fehler und kein
``sharing_retries``), die Zeilen 2 bis 8 vor der letzten Änderung der
gemessenen Fassung; beide Vorfassungen sind nicht abgelegt. ``observe`` und
``hurry`` der Reihen vor ``ablage`` (Zeilen 1 bis 65) stammen aus ihrem
Aufruf: Erstlauf, Gegenprobe und ``voll2-erste`` 150 s, ``voll2-anheben``
1,5 s mit ``--hurry``, alle übrigen 60 s.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core import process as process_boundary  # noqa: E402

TEST_BOUND = 10.0
OBSERVE = 150.0

k = ctypes.WinDLL("kernel32", use_last_error=True)
k.GetCurrentProcess.restype = ctypes.c_void_p
k.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
k.WaitForSingleObject.restype = ctypes.c_uint32
k.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
k.TerminateProcess.restype = ctypes.c_int
k.GetPriorityClass.argtypes = (ctypes.c_void_p,)
k.GetPriorityClass.restype = ctypes.c_uint32
k.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
k.SetPriorityClass.restype = ctypes.c_int
k.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
k.SetProcessAffinityMask.restype = ctypes.c_int
k.IsProcessInJob.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))
k.IsProcessInJob.restype = ctypes.c_int
k.GetSystemTimes.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
k.CloseHandle.argtypes = (ctypes.c_void_p,)
k.CreateToolhelp32Snapshot.argtypes = (ctypes.c_uint32, ctypes.c_uint32)
k.CreateToolhelp32Snapshot.restype = ctypes.c_void_p

ntdll = ctypes.WinDLL("ntdll")
ntdll.NtQueryInformationProcess.argtypes = (
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
)
ntdll.NtQueryInformationProcess.restype = ctypes.c_long


class _Basic(ctypes.Structure):
    _fields_ = [
        ("exit_status", ctypes.c_long),
        ("peb", ctypes.c_void_p),
        ("affinity", ctypes.c_size_t),
        ("base_priority", ctypes.c_long),
        ("pid", ctypes.c_size_t),
        ("parent_pid", ctypes.c_size_t),
    ]


class _Extended(ctypes.Structure):
    _fields_ = [("size", ctypes.c_size_t), ("basic", _Basic), ("flags", ctypes.c_uint32)]


def deleting(handle: int) -> bool | None:
    """IsProcessDeleting aus PROCESS_EXTENDED_BASIC_INFORMATION (Bit 2)."""
    info = _Extended()
    info.size = ctypes.sizeof(info)
    got = ctypes.c_uint32()
    status = ntdll.NtQueryInformationProcess(
        handle, 0, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(got)
    )
    if status != 0:
        return None
    return bool(info.flags & 0x4)


def ended(handle: int, seconds: float = 0.0) -> bool:
    return k.WaitForSingleObject(handle, int(seconds * 1000)) == 0


def threads_of(pid: int) -> int:
    class Entry(ctypes.Structure):
        _fields_ = [
            ("size", ctypes.c_uint32),
            ("usage", ctypes.c_uint32),
            ("tid", ctypes.c_uint32),
            ("owner", ctypes.c_uint32),
            ("base", ctypes.c_long),
            ("delta", ctypes.c_long),
            ("flags", ctypes.c_uint32),
        ]

    k.Thread32First.argtypes = (ctypes.c_void_p, ctypes.POINTER(Entry))
    k.Thread32Next.argtypes = (ctypes.c_void_p, ctypes.POINTER(Entry))
    snap = k.CreateToolhelp32Snapshot(4, 0)
    count = 0
    try:
        e = Entry(size=ctypes.sizeof(Entry))
        ok = k.Thread32First(snap, ctypes.byref(e))
        while ok:
            if e.owner == pid:
                count += 1
            ok = k.Thread32Next(snap, ctypes.byref(e))
    finally:
        k.CloseHandle(snap)
    return count


def system_times() -> tuple[int, int, int]:
    idle, kern, user = ctypes.c_uint64(), ctypes.c_uint64(), ctypes.c_uint64()
    k.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
    return idle.value, kern.value, user.value


def busy_percent(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    idle = b[0] - a[0]
    total = (b[1] - a[1]) + (b[2] - a[2])
    return 100.0 * (total - idle) / total if total else 0.0


PARENT = textwrap.dedent(
    """
    import os, sys, threading, traceback
    from pathlib import Path
    sys.path.insert(0, sys.argv[1])
    sys.path.insert(0, sys.argv[5])
    from app.core import process as process_boundary
    from app.core.geom import kernel_jobs, kernel_process
    import elternende_helfer as probe_helper

    def main():
        folder = Path(sys.argv[2])
        variant = sys.argv[4]
        if variant == "no-binding":
            process_boundary.bind_helper = lambda _child: None
        kernel_process._SERVE = (
            probe_helper.serve_blocked_normal
            if variant == "normal-priority"
            else probe_helper.serve_blocked
        )
        def no_local(*_a):
            raise AssertionError("muss im Helfer laufen")
        kernel_jobs.JOBS[probe_helper.JOB] = no_local
        try:
            assert kernel_process.warm_up()
            helper, = kernel_process.processes()
            probe_helper.publish(helper, int(sys.argv[3]), folder / "helper.json")
            def calculate():
                try:
                    kernel_process.run(probe_helper.JOB, {},
                        {"entered": str(folder / "entered.json")},
                        weight=kernel_process.OFFLOAD_ABOVE + 1)
                except BaseException:
                    traceback.print_exc()
                    os._exit(2)
            worker = threading.Thread(target=calculate, daemon=True)
            worker.start()
            worker.join(600.0)
        finally:
            kernel_process.shutdown()

    if __name__ == "__main__":
        main()
    """
)


def wait_file(path: Path, parent: subprocess.Popen, seconds: float) -> dict:
    deadline = time.monotonic() + seconds
    while not path.is_file():
        if parent.poll() is not None:
            raise RuntimeError(f"Elternprozess endete früh: {parent.returncode}")
        if time.monotonic() > deadline:
            raise RuntimeError(f"{path.name} kam nicht")
        time.sleep(0.02)
    while True:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError:
            SHARING_RETRIES.append(path.name)
            if time.monotonic() > deadline:
                raise
            time.sleep(0.02)


SHARING_RETRIES: list[str] = []


def main() -> int:
    variant, out = sys.argv[2], Path(sys.argv[3])
    crowd = int(sys.argv[sys.argv.index("--crowd") + 1]) if "--crowd" in sys.argv else 0
    pin = int(sys.argv[sys.argv.index("--pin") + 1], 0) if "--pin" in sys.argv else 0
    observe = float(sys.argv[sys.argv.index("--observe") + 1]) if "--observe" in sys.argv else OBSERVE
    if pin:
        k.SetProcessAffinityMask(k.GetCurrentProcess(), pin)
    record: dict = {
        "variant": variant,
        "crowd": crowd,
        "pin": hex(pin) if pin else None,
        "observe": observe,
        "hurry": "--hurry" in sys.argv,
        "started": time.strftime("%H:%M:%S"),
    }
    folder = Path(tempfile.mkdtemp(prefix="elternende-"))
    script = folder / "parent.py"
    script.write_text(PARENT, encoding="utf-8")
    log = folder / "parent.log"
    crowders: list[subprocess.Popen] = []
    code = 2
    helper = parent_real = None
    with log.open("wb") as output:
        parent = subprocess.Popen(
            [
                sys.executable,
                str(script),
                str(ROOT),
                str(folder),
                str(os.getpid()),
                variant,
                str(HERE),
            ],
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            cwd=folder,
            **process_boundary.process_group_options(no_window=True, suspended=True),
        )
        try:
            process_boundary._attach_process_boundary(parent)
            process_boundary._resume_process_boundary(parent)
            announced = wait_file(folder / "helper.json", parent, 120.0)
            helper, parent_real = announced["handle"], announced["parent_handle"]
            wait_file(folder / "entered.json", parent, 120.0)
            time.sleep(0.2)  # Zurückstellen nach dem Eintritt abwarten
            record["priority_at_kill"] = hex(k.GetPriorityClass(helper))
            record["threads_at_kill"] = threads_of(announced["pid"])
            in_job = ctypes.c_int()
            k.IsProcessInJob(helper, None, ctypes.byref(in_job))
            record["in_some_job"] = bool(in_job.value)
            record["deleting_before"] = deleting(helper)
            if crowd:
                cpu = 2
                k.SetProcessAffinityMask(helper, 1 << cpu)
                for _ in range(crowd):
                    burner = subprocess.Popen(
                        [sys.executable, "-c", "while True: pass"],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    k.SetProcessAffinityMask(int(burner._handle), 1 << cpu)  # type: ignore[attr-defined]
                    crowders.append(burner)
                time.sleep(1.0)
            before = system_times()
            t_kill = time.perf_counter()
            if not k.TerminateProcess(parent_real, 1):
                raise OSError(ctypes.get_last_error(), "TerminateProcess Eltern")  # type: ignore[attr-defined]
            if not ended(parent_real, 60.0):
                raise RuntimeError("Elternprozess endete nicht")
            t_parent = time.perf_counter()
            record["parent_end_s"] = round(t_parent - t_kill, 3)
            record["deleting_after_parent"] = deleting(helper)
            marks = {}
            helper_end = None
            while time.perf_counter() - t_parent < observe:
                if ended(helper, 0.02):
                    helper_end = time.perf_counter() - t_parent
                    break
                age = time.perf_counter() - t_parent
                for mark in (1.0, TEST_BOUND):
                    if age >= mark and mark not in marks:
                        marks[mark] = deleting(helper)
            record["deleting_at_1s"] = marks.get(1.0)
            record["deleting_at_10s"] = marks.get(TEST_BOUND)
            record["helper_end_s"] = None if helper_end is None else round(helper_end, 3)
            record["busy_pct"] = round(busy_percent(before, system_times()), 1)
            if helper_end is None:
                record["deleting_at_end"] = deleting(helper)
                code = 3
                if "--hurry" in sys.argv:
                    t_hurry = time.perf_counter()
                    record["hurry_set"] = k.SetPriorityClass(helper, 0x20)
                    record["hurry_priority"] = hex(k.GetPriorityClass(helper))
                    record["hurry_end_s"] = (
                        round(time.perf_counter() - t_hurry, 3) if ended(helper, 60.0) else None
                    )
            else:
                code = 0 if helper_end <= TEST_BOUND else 1
        except BaseException as problem:
            record["error"] = "".join(traceback.format_exception(problem))[-1500:]
            code = 2
        finally:
            for burner in crowders:
                burner.kill()
                burner.wait(30)
            if helper is not None:
                k.SetPriorityClass(helper, 0x20)
                k.TerminateProcess(helper, 1)
                record["cleanup_helper_ended"] = ended(helper, 30.0)
            process_boundary._close_windows_job(parent)
            if parent.poll() is None:
                parent.kill()
            parent.wait(30)
    tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-5:]
    record["parent_log_tail"] = tail
    record["sharing_retries"] = SHARING_RETRIES
    record["exit"] = code
    with out.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
