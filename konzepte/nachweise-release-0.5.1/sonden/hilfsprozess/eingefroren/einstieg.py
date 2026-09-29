"""Eingefrorener Nachweis (RM-212): startet der Hilfsprozess aus einem PyInstaller-Paket?

Der Kopf ist der von ``app/ui/app.py`` — ``import app.ui``, Absturzprotokoll
importiert, im ``__main__``-Block zuerst ``freeze_support()``. Danach rechnet
das Paket zwei Rechnungen aus einem Nebenfaden im Hilfsprozess und dieselben
im Prozess, vergleicht Byte für Byte, beendet die Hilfsprozesse und schreibt
einen Bericht nach ``argv[1]`` (eine Fensteranwendung hat keine Konsole).

Gebaut mit ``bauen.sh`` (``--windowed`` wie die Spec, ``console=False``).
"""

import app.ui  # noqa: F401
from app.core.log import install_crash_logging

if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    install_crash_logging()

# isort: split

import hashlib
import json
import sys
import threading
import time


def fingerprint(outcome):
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
    report = {"frozen": getattr(sys, "frozen", False), "executable": sys.executable}
    started = time.perf_counter()
    try:
        import numpy as np

        from app.core.geom import kernel_jobs, kernel_process

        # Ein Körper aus dem Kern selbst: eine Kugel, fein genug für eine echte Rechnung.
        import manifold3d

        sphere = manifold3d.Manifold.sphere(20.0, 256).to_mesh64()
        vertices = np.array(sphere.vert_properties[:, :3], dtype=np.float64)
        faces = np.array(sphere.tri_verts, dtype=np.int64)
        tool = manifold3d.Manifold.cylinder(60.0, 4.0, 4.0, 64).translate((0.0, 0.0, -30.0))
        cut = tool.to_mesh64()
        jobs = {
            "display_simplify": (
                {"vertices": vertices, "faces": faces},
                {
                    "target": 5000,
                    "tolerance": 0.05,
                    "growth": 4.0,
                    "steps": 6,
                    "triangles": len(faces),
                },
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
        }
        report["triangles"] = len(faces)
        here = {name: fingerprint(kernel_jobs.JOBS[name](a, dict(v), lambda: None)) for name, (a, v) in jobs.items()}
        # Wie ``app.ui.app``: der Hilfsprozess startet vorab; gemessen bis zur ersten Meldung.
        warm = time.perf_counter()
        report["warm_up"] = kernel_process.warm_up()
        report["warm_up_seconds"] = round(time.perf_counter() - warm, 3)
        kernel_process.OFFLOAD_ABOVE = 0
        there: dict = {}

        def worker() -> None:
            for name, (arrays, values) in jobs.items():
                there[name] = fingerprint(kernel_process.run(name, arrays, values, weight=len(faces)))

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(300.0)
        report["same_bytes"] = {name: here[name] == there.get(name) for name in jobs}
        report["statistics"] = kernel_process.statistics()
        helpers = kernel_process.processes()
        report["helper_pids"] = [helper.pid for helper in helpers]
        report["stopped"] = kernel_process.shutdown()
        for helper in helpers:
            helper.join(10.0)
        report["helpers_alive_after_shutdown"] = [helper.is_alive() for helper in helpers]
    except BaseException as problem:  # noqa: BLE001 — der Bericht soll den Fehler tragen
        import traceback

        report["error"] = f"{type(problem).__name__}: {problem}"
        report["traceback"] = traceback.format_exc()
    report["seconds"] = round(time.perf_counter() - started, 3)
    with open(sys.argv[1], "w", encoding="utf-8") as sink:
        json.dump(report, sink, indent=1)


if __name__ == "__main__":
    main()
