"""Ab welcher Größe lohnt der Hilfsprozess? (RM-212, Schwelle ``OFFLOAD_ABOVE``)

Je Größe (der Spielwürfel, vom Kern auf die Zielzahl vereinfacht) zwei
Rechnungen, wie die Vorschau sie stellt: ``display_simplify`` (grobe Vorschau,
Anzeige) und ``boolean`` (Differenz mit einem Zylinder). Jede einmal im Prozess
und einmal im warmen Hilfsprozess, beide aus einem Nebenfaden — und im
Hauptfaden misst ein 2-ms-Takt den längsten Stillstand. Dazu: Kaltstart des
Hilfsprozesses bis zur ersten Antwort und sein Speicher untätig.

Aufruf (gebunden, aus dem Arbeitsbaum): python ../sonden/hilfsprozess/schwelle.py <baum>
Alles Rechnen unter ``__main__`` (der Hilfsprozess lädt das Hauptmodul neu).
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

TREE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
sys.path.insert(0, str(TREE))

SIZES = (2_000, 5_000, 10_000, 20_000, 50_000, 100_000, 250_488)
REPEAT = 3


class Ticker:
    def __init__(self) -> None:
        self.late = 0.0
        self.done = threading.Event()

    def run(self) -> None:
        while not self.done.is_set():
            started = time.perf_counter()
            time.sleep(0.002)
            self.late = max(self.late, time.perf_counter() - started - 0.002)


def in_worker(work):
    """``work`` in einem Nebenfaden; der Hauptfaden tickt. -> (Sekunden, Stillstand)"""
    ticker = Ticker()
    out: list[float] = []

    def job() -> None:
        started = time.perf_counter()
        work()
        out.append(time.perf_counter() - started)
        ticker.done.set()

    time.sleep(0.02)
    worker = threading.Thread(target=job)
    worker.start()
    ticker.run()
    worker.join()
    return out[0], ticker.late


def memory_mb(pid: int) -> float:
    listing = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH", "/FI", f"PID eq {pid}"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    field = listing.strip().split('","')[-1].strip('"').replace("\xa0", "").replace(".", "")
    digits = "".join(ch for ch in field if ch.isdigit())
    return int(digits) / 1024.0 if digits else float("nan")


def main() -> None:
    import numpy as np
    import trimesh

    import app

    assert str(Path(app.__file__).resolve()).startswith(str(TREE)), app.__file__
    from app.core.geom import kernel_jobs, kernel_process
    from app.core.geom.mesh import MeshData
    dice = MeshData.of(trimesh.load(r"F:\3D Dateien\dice_w6_16mm_v00.stl", force="mesh"))
    plate = trimesh.load(str(TREE / "tests" / "data" / "meshes" / "plate_holes.stl"), force="mesh")

    def plate_times(times: int) -> MeshData:
        vertices, faces = np.asarray(plate.vertices), np.asarray(plate.faces)
        for _ in range(times):
            vertices, faces = trimesh.remesh.subdivide(vertices, faces)
        return MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))

    def sphere(level: int) -> MeshData:
        return MeshData.of(trimesh.creation.icosphere(subdivisions=level, radius=20.0))

    bodies = [
        ("Kugel 5 120", sphere(4)),
        ("Lochplatte x2 12 736", plate_times(2)),
        ("Kugel 20 480", sphere(5)),
        ("Lochplatte x3 50 944", plate_times(3)),
        ("Kugel 81 920", sphere(6)),
        ("Lochplatte x4 203 776", plate_times(4)),
        ("Würfel 250 488", dice),
        ("Kugel 327 680", sphere(7)),
    ]

    # Kaltstart: Schwelle null, eine kleine Rechnung aus einem Nebenfaden.
    kernel_process.OFFLOAD_ABOVE = 0
    tiny = MeshData.of(trimesh.creation.icosphere(subdivisions=2))
    seconds, late = in_worker(
        lambda: kernel_process.run(
            "display_simplify",
            {"vertices": np.asarray(tiny.raw.vertices), "faces": np.asarray(tiny.raw.faces)},
            {"target": 100, "tolerance": 0.05, "growth": 4.0, "steps": 6, "triangles": 320},
            weight=320,
        )
    )
    pid = kernel_process.processes()[0].pid
    print(f"Kaltstart bis zur ersten Antwort: {seconds:.2f} s, Stillstand {late * 1000:.0f} ms", flush=True)
    time.sleep(1.0)
    print(f"Speicher des untätigen Hilfsprozesses: {memory_mb(pid):.0f} MB (Arbeitssatz)", flush=True)

    print(
        f"{'Körper':<22} {'Rechnung':<17} {'im Prozess':>22} {'Hilfsprozess':>22}  (s / längster Stillstand ms)",
        flush=True,
    )
    for label, body in bodies:
        size = body.triangle_count
        vertices = np.asarray(body.raw.vertices)
        faces = np.asarray(body.raw.faces)
        low, high = body.bounds.minimum, body.bounds.maximum
        tool = trimesh.creation.cylinder(radius=2.0, height=float(high[2] - low[2]) + 4.0, sections=48)
        tool.apply_translation([(low[i] + high[i]) / 2.0 for i in range(3)])
        jobs = {
            "display_simplify": (
                {"vertices": vertices, "faces": faces},
                {
                    "target": max(500, body.triangle_count // 4),
                    "tolerance": 0.05,
                    "growth": 4.0,
                    "steps": 6,
                    "triangles": body.triangle_count,
                },
            ),
            "boolean": (
                {
                    "vertices0": vertices,
                    "faces0": faces,
                    "vertices1": np.asarray(tool.vertices),
                    "faces1": np.asarray(tool.faces),
                },
                {"bodies": 2, "kind": "difference"},
            ),
        }
        for name, (arrays, values) in jobs.items():
            here: list[tuple[float, float]] = []
            there: list[tuple[float, float]] = []
            for _ in range(REPEAT):
                kernel_process.OFFLOAD_ABOVE = 10**12
                here.append(
                    in_worker(lambda a=arrays, v=values, n=name: kernel_process.run(n, a, v, weight=size))
                )
                kernel_process.OFFLOAD_ABOVE = 0
                there.append(
                    in_worker(lambda a=arrays, v=values, n=name: kernel_process.run(n, a, v, weight=size))
                )
            best_here = min(here)
            best_there = min(there)
            print(
                f"{label:<22} {name:<17} "
                f"{best_here[0]:8.3f} s {max(h[1] for h in here) * 1000:8.0f} ms "
                f"{best_there[0]:8.3f} s {max(t[1] for t in there) * 1000:8.0f} ms",
                flush=True,
            )
    print("Hilfsprozess:", kernel_process.statistics(), flush=True)
    kernel_process.shutdown()
    del kernel_jobs


if __name__ == "__main__":
    main()
