"""Wie viel Speicher hält ein untätiger Hilfsprozess — frisch und nach großen Rechnungen?

Der Vorrat behält einen untätigen Hilfsprozess (``IDLE_KEPT``). Gibt der Kern
den Speicher einer großen Rechnung nicht an das System zurück, trüge die
Anwendung ihn danach unsichtbar mit — beim Kunden mit 8 GB wäre das eine Frage.

Gemessen über ``K32GetProcessMemoryInfo`` (Arbeitssatz, privater Speicher,
Spitze des Arbeitssatzes) am Hilfsprozess und an diesem Prozess:

1. frisch nach ``warm_up``;
2. nach ``_split_conforming`` am Spielwürfel, 0,05 mm (5,8 Mio. Dreiecke), untätig;
3. nach einer zweiten gleichen Rechnung (wächst er weiter?);
4. nach ``display_simplify`` am Ergebnis (die Anzeige ab §31);
5. nach ``face_components`` am Ergebnis (``component_labels`` lädt ``scipy``).

Mit ``alt`` startet der Hilfsprozess ohne ``HELPER_ENVIRONMENT`` (so wie vor
dem Einfädeln), sonst mit einem BLAS-Faden.

Aufruf (gebunden, aus dem Arbeitsbaum): python ../sonden/hilfsprozess/speicher.py <baum> [alt]
"""

if __name__ == "__main__":
    import ctypes
    import sys
    import threading
    import time
    from ctypes import wintypes
    from pathlib import Path

    TREE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    sys.path.insert(0, str(TREE))
    MODEL = Path(r"F:\3D Dateien\dice_w6_16mm_v00.stl")

    class Counters(ctypes.Structure):
        _fields_ = [  # noqa: RUF012
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.K32GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(Counters),
        wintypes.DWORD,
    )
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

    def memory(pid: int) -> str:
        handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)
        if not handle:
            return f"(nicht lesbar, Fehler {ctypes.get_last_error()})"
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        try:
            if not kernel32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return f"(nicht lesbar, Fehler {ctypes.get_last_error()})"
        finally:
            kernel32.CloseHandle(handle)
        mb = 2**20
        return (
            f"Arbeitssatz {counters.WorkingSetSize / mb:7.0f} MB, privat "
            f"{counters.PrivateUsage / mb:7.0f} MB, Spitze {counters.PeakWorkingSetSize / mb:7.0f} MB"
        )

    import os

    import trimesh

    from app.core.geom import kernel_process, mesh_ops
    from app.core.geom.mesh import MeshData

    import app

    print(f"app aus {app.__file__}", flush=True)
    if "alt" in sys.argv[2:]:
        kernel_process.HELPER_ENVIRONMENT.clear()
    print(f"Umgebung des Hilfsprozesses: {kernel_process.HELPER_ENVIRONMENT}", flush=True)
    assert kernel_process.warm_up()
    helper = kernel_process.processes()[0]
    me = os.getpid()
    time.sleep(1.0)
    print(f"1 frisch      Hilfsprozess {memory(helper.pid)}", flush=True)
    print(f"             Anwendung    {memory(me)}", flush=True)
    mesh = MeshData.of(trimesh.load(str(MODEL), force="mesh"))
    print(f"Spielwürfel: {mesh.triangle_count} Dreiecke, dicht {mesh.is_watertight}", flush=True)

    def in_a_worker(function):  # noqa: ANN001, ANN202
        box: dict[str, object] = {}

        def work() -> None:
            box["value"] = function()

        worker = threading.Thread(target=work)
        worker.start()
        worker.join()
        return box["value"]

    fine = None
    for round_number in (2, 3):
        began = time.perf_counter()
        fine = in_a_worker(
            lambda: mesh_ops._split_conforming(mesh, 0.05, None, expected=6_000_000)
        )
        took = time.perf_counter() - began
        alive = [process.pid for process in kernel_process.processes()]
        time.sleep(1.0)
        print(
            f"{round_number} nach Verfeinern ({took:.1f} s, "
            f"{fine.triangle_count if fine is not None else None} Dreiecke), untätig: "
            f"Hilfsprozesse {alive}",
            flush=True,
        )
        for pid in alive:
            print(f"             Hilfsprozess {pid} {memory(pid)}", flush=True)
        print(f"             Anwendung    {memory(me)}", flush=True)
    assert fine is not None
    in_a_worker(lambda: mesh_ops.decimate_for_display(fine, 150_000))
    alive = [process.pid for process in kernel_process.processes()]
    time.sleep(1.0)
    print(f"4 nach Anzeige-Dezimierung: Hilfsprozesse {alive}", flush=True)
    for pid in alive:
        print(f"             Hilfsprozess {pid} {memory(pid)}", flush=True)
    from app.core.geom.mesh import face_components

    parts = in_a_worker(lambda: face_components(fine.raw))
    alive = [process.pid for process in kernel_process.processes()]
    time.sleep(1.0)
    print(f"5 nach face_components ({len(parts)} Teil): Hilfsprozesse {alive}", flush=True)
    for pid in alive:
        print(f"             Hilfsprozess {pid} {memory(pid)}", flush=True)
    print(f"Zähler {kernel_process.statistics()}", flush=True)
    print(f"beendet {kernel_process.shutdown()}", flush=True)
