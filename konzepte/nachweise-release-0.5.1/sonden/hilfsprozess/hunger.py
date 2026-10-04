"""Hänger oder Rechenzeit? Der Hilfsprozess auf Kernen ohne freie Zeit (RM-380).

Im Entwicklungstor kamen drei Fälle aus ``tests/test_kernel_process.py`` unter
Last in 120 s nicht zurück, allein gefahren in einer Sekunde — alle drei rechnen
``component_labels`` im Hilfsprozess, und das lud dort ``trimesh.graph`` nach,
nachdem er sich unter Windows eine Klasse tiefer gestellt hatte.

Die Sonde bindet sich und alles, was sie startet, an die Kerne 30 und 31
(Prozessaffinität wird vererbt, auch an den Hilfsprozess) und lastet diese mit
vier Python-Schleifen normaler Priorität aus — die Lage des Tors auf einer
belegten Maschine, ohne die übrigen dreißig Kerne anzufassen. Dann rechnet sie
aus einem Nebenfaden über ``kernel_process.run``, je Fall mit frischem
Hilfsprozess:

1. ``component_labels`` wie ausgeliefert (Vorbereitung in normaler Klasse,
   ``kernel_jobs.PREPARATIONS``),
2. ``component_labels`` ohne Vorbereitung — der Stand vor RM-380,
3. ``component_labels`` ohne Zurückstellen,
4. ``simplify_closed`` wie ausgeliefert (lädt nichts nach).

Je Fall alle fünf Sekunden die CPU-Zeit und Prioritätsklasse des Hilfsprozesses
(``GetProcessTimes``, ``GetPriorityClass``): Wächst sie, rechnet er; steht sie
bei laufender Uhr, wartet er auf den Planer. Obergrenze je Fall 300 s.

Aufruf (Windows): python hunger.py <baum> [ohne-last]
Ausgabe zeilenweise auf stdout.
"""

from __future__ import annotations

from typing import Any

#: Die Kerne der Sonde: 30 und 31.
CORES = (1 << 30) | (1 << 31)
LOAD_PROCESSES = 4
CAP_SECONDS = 300.0


def serve_as_shipped(connection: Any) -> None:
    """Der Hilfsprozess, wie die Anwendung ihn startet."""
    from app.core.geom import kernel_jobs

    kernel_jobs.serve(connection)


def serve_without_preparation(connection: Any) -> None:
    """Der Stand vor RM-380: Die Rechnung lädt erst zurückgestellt nach."""
    from app.core.geom import kernel_jobs

    kernel_jobs.PREPARATIONS = {}  # type: ignore[misc]
    kernel_jobs.serve(connection)


def serve_without_lowering(connection: Any) -> None:
    """Ein Hilfsprozess, der für seine Rechnungen nicht zurückgeht."""
    from app.core.geom import kernel_jobs

    kernel_jobs.PREPARATIONS = {}  # type: ignore[misc]
    kernel_jobs._yield_to_the_window = lambda: None
    kernel_jobs.serve(connection)


if __name__ == "__main__":
    import ctypes
    import subprocess
    import sys
    import threading
    import time
    from ctypes import wintypes
    from pathlib import Path

    TREE = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(TREE))
    with_load = "ohne-last" not in sys.argv[2:]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.SetProcessAffinityMask.argtypes = (wintypes.HANDLE, ctypes.c_size_t)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (
        ctypes.POINTER(wintypes.FILETIME),
    ) * 4
    kernel32.GetProcessAffinityMask.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    )
    kernel32.GetPriorityClass.argtypes = (wintypes.HANDLE,)

    def seconds(value: Any) -> float:
        return ((value.dwHighDateTime << 32) | value.dwLowDateTime) / 1e7

    def looked_at(pid: int) -> tuple[float, int, int]:
        """CPU-Zeit, Affinität und Prioritätsklasse eines Prozesses."""
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return -1.0, 0, 0
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times))
            mask, system = ctypes.c_size_t(), ctypes.c_size_t()
            kernel32.GetProcessAffinityMask(handle, ctypes.byref(mask), ctypes.byref(system))
            return seconds(times[2]) + seconds(times[3]), mask.value, kernel32.GetPriorityClass(handle)
        finally:
            kernel32.CloseHandle(handle)

    def components_case() -> tuple[dict[str, Any], dict[str, Any]]:
        import numpy as np
        import trimesh

        from app.core.geom.mesh import MeshData, _adjacency_by_place

        body = MeshData.of(
            trimesh.load(str(TREE / "tests/data/meshes/two_components.stl"), force="mesh")
        )
        edges = np.asarray(_adjacency_by_place(body.raw), dtype=np.int64).reshape(-1, 2)
        return {"edges": edges}, {"count": body.triangle_count}

    def closed_case() -> tuple[dict[str, Any], dict[str, Any]]:
        import numpy as np
        import trimesh

        from app.core.geom.mesh import MeshData

        body = MeshData.of(trimesh.load(str(TREE / "tests/data/meshes/plate_holes.stl"), force="mesh"))
        return {
            "vertices": np.asarray(body.raw.vertices),
            "faces": np.asarray(body.raw.faces),
        }, {"tolerance": 1e-6}

    def measure(name: str, job: str, case: Any, serve: Any) -> None:
        from app.core.geom import kernel_process

        kernel_process.shutdown()
        kernel_process._POOL.counts.clear()
        kernel_process.OFFLOAD_ABOVE = 0
        kernel_process._SERVE = serve
        arrays, values = case()
        box: dict[str, Any] = {}

        def work() -> None:
            try:
                box["value"] = kernel_process.run(job, arrays, values, weight=1)
            except BaseException as problem:
                box["error"] = problem

        start = time.perf_counter()
        worker = threading.Thread(target=work, name="kernel-test")
        worker.start()
        shown = False
        while worker.is_alive() and time.perf_counter() - start < CAP_SECONDS:
            worker.join(5.0)
            helpers = kernel_process.processes()
            if helpers and helpers[0].pid:
                cpu, mask, priority = looked_at(helpers[0].pid)
                if not shown:
                    print(f"  Hilfsprozess {helpers[0].pid}, Affinität 0x{mask:x}", flush=True)
                    shown = True
                print(
                    f"    {time.perf_counter() - start:6.1f} s  CPU {cpu:5.2f} s  "
                    f"Klasse 0x{priority:x}",
                    flush=True,
                )
        elapsed = time.perf_counter() - start
        done = not worker.is_alive()
        counts = kernel_process.statistics()
        outcome = f"Fehler {box['error']!r}" if "error" in box else "Ergebnis"
        print(
            f"{name}: {'fertig' if done else 'NICHT fertig'} nach {elapsed:.1f} s ({outcome}, "
            f"helper={counts.get('helper')}, fallback={counts.get('fallback')})",
            flush=True,
        )
        kernel_process.shutdown()
        worker.join(30.0)

    if not kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), CORES):
        raise OSError(ctypes.get_last_error(), "SetProcessAffinityMask")
    load: list[Any] = []
    try:
        if with_load:
            for _ in range(LOAD_PROCESSES):
                load.append(subprocess.Popen([sys.executable, "-c", "while True: pass"]))
            time.sleep(2.0)
            _cpu, mask, priority = looked_at(load[0].pid)
            print(
                f"Last: {LOAD_PROCESSES} Schleifen, Affinität 0x{mask:x}, Klasse 0x{priority:x}",
                flush=True,
            )
        else:
            print("ohne eigene Last (die Kerne teilen sich weiter mit der Maschine)", flush=True)
        measure("1 component_labels, wie ausgeliefert", "component_labels", components_case, serve_as_shipped)
        measure(
            "2 component_labels, ohne Vorbereitung",
            "component_labels",
            components_case,
            serve_without_preparation,
        )
        measure(
            "3 component_labels, nicht zurückgestellt",
            "component_labels",
            components_case,
            serve_without_lowering,
        )
        measure("4 simplify_closed, wie ausgeliefert", "simplify_closed", closed_case, serve_as_shipped)
    finally:
        for process in load:
            process.kill()
            process.wait(10.0)
