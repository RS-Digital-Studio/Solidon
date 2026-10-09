"""RM-672 (3): Der zurückgestellte Hilfsprozess unter Fremdlast — zurückgestellt, wachend, normal.

Aufruf: python vorrang.py <baum> <runden>

Ein vorgewärmter Hilfsprozess rechnet ``display_simplify`` und ``boolean`` an einer
Ikosphäre (327 680 Dreiecke), aus einem Nebenfaden; der Hauptfaden tickt (2 ms)
und misst den längsten Stillstand. Je Runde im Wechsel:

* ``zurueck``: wie bis RM-672, nie gehoben (``STARVED_SHARE`` 0);
* ``wache``: der Wartende hebt ihn, wenn er verhungert (Vorgabe);
* ``normal``: gleich beim ersten Blick gehoben (Fenster 0, Anteil unendlich).

Ausgabe je Lauf eine JSON-Zeile: Wandzeit, CPU des Hilfsprozesses, Stillstand,
ob gehoben, und die Systemlast über den Lauf.
"""

from __future__ import annotations

import ctypes
import json
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path


class _FT(ctypes.Structure):
    _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]


def _systimes() -> tuple[int, int, int]:
    k32 = ctypes.WinDLL("kernel32")
    i, k, u = _FT(), _FT(), _FT()
    k32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
    return tuple((t.hi << 32) | t.lo for t in (i, k, u))  # type: ignore[return-value]


def _load(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    idle = b[0] - a[0]
    total = (b[1] - a[1]) + (b[2] - a[2])
    return round(100.0 * (1 - idle / total), 1) if total else 0.0


def main() -> None:
    tree = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(tree))
    import app

    assert tree in Path(app.__file__).resolve().parents, app.__file__
    import numpy as np
    import trimesh

    from app.core import process as boundary
    from app.core.geom import kernel_process

    rounds = int(sys.argv[2])
    sphere = trimesh.creation.icosphere(subdivisions=7, radius=20.0)
    tool = trimesh.creation.cylinder(radius=3.0, height=60.0, sections=64)
    vertices = np.asarray(sphere.vertices, dtype=np.float64)
    faces = np.asarray(sphere.faces, dtype=np.int64)
    jobs = {
        "display_simplify": (
            {"vertices": vertices, "faces": faces},
            {"target": len(faces) // 4, "tolerance": 0.01, "growth": 2.0, "steps": 8,
             "triangles": len(faces)},
        ),
        "boolean": (
            {"vertices0": vertices, "faces0": faces,
             "vertices1": np.asarray(tool.vertices, dtype=np.float64),
             "faces1": np.asarray(tool.faces, dtype=np.int64)},
            {"bodies": 2, "kind": "difference"},
        ),
    }
    modes = {
        "zurueck": (1.0, 0.0),
        "wache": (kernel_process.STARVED_WINDOW_SECONDS, kernel_process.STARVED_SHARE),
        "normal": (0.0, float("inf")),
    }
    names = list(modes)
    for round_number in range(rounds):
        order = names[round_number % 3 :] + names[: round_number % 3]
        for job, (arrays, values) in jobs.items():
            for mode in order:
                window, share = modes[mode]
                kernel_process.STARVED_WINDOW_SECONDS = window  # type: ignore[misc]
                kernel_process.STARVED_SHARE = share  # type: ignore[misc]
                kernel_process.shutdown()
                kernel_process._POOL.counts.clear()
                box: dict = {}

                def warm() -> None:
                    box["warm"] = kernel_process.warm_up()

                thread = threading.Thread(target=warm)
                thread.start()
                thread.join()
                helper = kernel_process.processes()[0]
                cpu_before = boundary.helper_cpu_seconds(helper) or 0.0
                late = [0.0]
                done = threading.Event()

                def work(j=job, a=arrays, v=values) -> None:
                    started = time.perf_counter()
                    kernel_process.run(j, a, v, weight=len(faces))
                    box["s"] = time.perf_counter() - started
                    done.set()

                system = _systimes()
                worker = threading.Thread(target=work)
                worker.start()
                while not done.is_set():
                    tick = time.perf_counter()
                    time.sleep(0.002)
                    late[0] = max(late[0], time.perf_counter() - tick - 0.002)
                worker.join()
                cpu_after = boundary.helper_cpu_seconds(helper) or 0.0
                print(
                    json.dumps(
                        {
                            "runde": round_number,
                            "rechnung": job,
                            "art": mode,
                            "s": round(box["s"], 3),
                            "cpu_hilfe": round(cpu_after - cpu_before, 2),
                            "stillstand_ms": round(late[0] * 1000, 1),
                            "gehoben": kernel_process.statistics().get("hurried", 0),
                            "last": _load(system, _systimes()),
                        }
                    ),
                    flush=True,
                )
    kernel_process.shutdown()


if __name__ == "__main__":
    main()
