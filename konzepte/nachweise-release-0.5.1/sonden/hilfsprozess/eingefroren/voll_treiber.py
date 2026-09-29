"""Das gebaute Solidon3D.exe als Hilfsprozess des Kerns (RM-212, Paketnachweis).

Im Paket startet ``multiprocessing`` mit ``spawn`` die Anwendung selbst:
``Solidon3D.exe --multiprocessing-fork parent_pid=… pipe_handle=…``. Dieser
Treiber stellt genau das nach, ohne die Anwendung zu starten: Er ist der
Elternprozess, nennt ``Solidon3D.exe`` als ausführbare Datei, gibt während des
Starts ``sys.frozen`` und den Suchpfad des Pakets an (so baut ``spawn`` die
Kommandozeile des Pakets und der Hilfsprozess lädt aus ``_internal``), und
rechnet dann zwei Rechnungen dort und im Prozess.

Belegt ist damit: Der Einstieg des gebauten Pakets (``app/ui/app.py``) gibt den
Start an ``freeze_support`` ab, bevor Qt oder ein Fenster entsteht, der
Hilfsprozess lädt ``kernel_jobs`` und ``manifold3d`` aus dem Paket und rechnet
bitgleich. Nicht belegt: der Start aus einem gebauten Elternprozess heraus —
das tut die Anwendung, und ihr Weg dorthin ist derselbe ``spawn``.

Aufruf (gebunden, aus dem Arbeitsbaum): python ../sonden/hilfsprozess/eingefroren/voll_treiber.py <baum> <bericht.json>
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXE = HERE / "voll" / "dist" / "Solidon3D" / "Solidon3D.exe"


def fingerprint(outcome) -> str:
    arrays, values = outcome
    digest = hashlib.sha256()
    for name in sorted(arrays):
        array = arrays[name]
        digest.update(name.encode())
        digest.update(array.dtype.str.encode())
        digest.update(repr(array.shape).encode())
        digest.update(array.tobytes())
    digest.update(repr(sorted(values.items())).encode())
    return digest.hexdigest()


def main() -> None:
    tree = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(tree))
    report: dict = {"exe": str(EXE), "exists": EXE.is_file()}
    import manifold3d
    import numpy as np

    import app
    from app.core.geom import kernel_jobs, kernel_process

    report["app"] = app.__file__
    internal = EXE.parent / "_internal"
    frozen_path = [str(internal / "base_library.zip"), str(internal / "lib-dynload"), str(internal)]
    kernel_process._CONTEXT.set_executable(str(EXE))
    saved_path = list(sys.path)
    sys.frozen = True  # type: ignore[attr-defined]
    sys.path[:] = frozen_path
    try:
        started = time.perf_counter()
        report["warm_up"] = kernel_process.warm_up()
        report["warm_up_seconds"] = round(time.perf_counter() - started, 3)
    finally:
        del sys.frozen  # type: ignore[attr-defined]
        sys.path[:] = saved_path
    helpers = kernel_process.processes()
    report["helper_pids"] = [helper.pid for helper in helpers]
    import subprocess

    report["helper_images"] = [
        subprocess.run(
            ["tasklist", "/FI", f"PID eq {helper.pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split(",")[0].strip('"')
        for helper in helpers
    ]

    sphere = manifold3d.Manifold.sphere(20.0, 256).to_mesh64()
    vertices = np.array(sphere.vert_properties[:, :3], dtype=np.float64)
    faces = np.array(sphere.tri_verts, dtype=np.int64)
    cut = manifold3d.Manifold.cylinder(60.0, 4.0, 4.0, 64).translate((0.0, 0.0, -30.0)).to_mesh64()
    jobs = {
        "display_simplify": (
            {"vertices": vertices, "faces": faces},
            {"target": 5000, "tolerance": 0.05, "growth": 4.0, "steps": 6, "triangles": len(faces)},
        ),
        "boolean": (
            {
                "vertices0": vertices,
                "faces0": faces,
                "vertices1": np.array(cut.vert_properties[:, :3], dtype=np.float64),
                "faces1": np.array(cut.tri_verts, dtype=np.int64),
            },
            {"bodies": 2, "kind": "difference"},
        ),
        "refine_conforming": (
            {"vertices": vertices, "faces": faces},
            {"edge": 0.3, "most": 8_000_000, "passes": 12, "slack": 1e-6},
        ),
    }
    here = {
        name: fingerprint(kernel_jobs.JOBS[name](arrays, dict(values), lambda: None))
        for name, (arrays, values) in jobs.items()
    }
    kernel_process.OFFLOAD_ABOVE = 0
    there: dict = {}

    def worker() -> None:
        for name, (arrays, values) in jobs.items():
            there[name] = fingerprint(kernel_process.run(name, arrays, values, weight=len(faces)))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(600.0)
    report["same_bytes"] = {name: here[name] == there.get(name) for name in jobs}
    report["statistics"] = kernel_process.statistics()
    report["helper_pids_after"] = [helper.pid for helper in kernel_process.processes()]
    report["stopped"] = kernel_process.shutdown()
    for helper in helpers:
        helper.join(10.0)
    report["helpers_alive_after_shutdown"] = [helper.is_alive() for helper in helpers]
    Path(sys.argv[2]).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
