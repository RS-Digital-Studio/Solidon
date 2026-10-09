"""RM-672 (1): Rechnung im Prozess gegen einen frisch startenden Hilfsprozess.

Aufruf: python schwelle_start.py <baum> <runden>

Je Größe (Ikosphäre 81 920 / 327 680 / 1 310 720 Dreiecke) und Rechnung
(``component_labels``, ``display_simplify``, ``boolean``) im Wechsel:

* ``hier``: im Prozess aus einem Nebenfaden, der Hauptfaden tickt (2 ms) und
  misst den längsten Stillstand;
* ``kalt``: der Pool ist leer (``shutdown``), die Rechnung startet einen
  Hilfsprozess und wartet auf Start, Vorbereitung und Rechnung — das, was die
  Auswertung heute tut, wenn das Vorwärmen noch läuft.

Wandzeit und Stillstand je Lauf als JSON-Zeile auf stdout.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path


def main() -> None:
    tree = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(tree))
    import app

    assert tree in Path(app.__file__).resolve().parents, app.__file__
    import numpy as np
    import trimesh

    from app.core.geom import kernel_jobs, kernel_process

    rounds = int(sys.argv[2])

    def inputs(subdivisions: int) -> dict[str, tuple[dict, dict]]:
        sphere = trimesh.creation.icosphere(subdivisions=subdivisions, radius=20.0)
        tool = trimesh.creation.cylinder(radius=3.0, height=60.0, sections=64)
        vertices = np.asarray(sphere.vertices, dtype=np.float64)
        faces = np.asarray(sphere.faces, dtype=np.int64)
        return {
            "component_labels": (
                {"edges": np.asarray(sphere.face_adjacency, dtype=np.int64)},
                {"count": len(faces)},
            ),
            "display_simplify": (
                {"vertices": vertices, "faces": faces},
                {
                    "target": len(faces) // 4,
                    "tolerance": 0.01,
                    "growth": 2.0,
                    "steps": 8,
                    "triangles": len(faces),
                },
            ),
            "boolean": (
                {
                    "vertices0": vertices,
                    "faces0": faces,
                    "vertices1": np.asarray(tool.vertices, dtype=np.float64),
                    "faces1": np.asarray(tool.faces, dtype=np.int64),
                },
                {"bodies": 2, "kind": "difference"},
            ),
        }

    def in_worker(work):
        late = [0.0]
        done = threading.Event()
        out: list[float] = []

        def job() -> None:
            started = time.perf_counter()
            work()
            out.append(time.perf_counter() - started)
            done.set()

        time.sleep(0.02)
        worker = threading.Thread(target=job)
        worker.start()
        while not done.is_set():
            started = time.perf_counter()
            time.sleep(0.002)
            late[0] = max(late[0], time.perf_counter() - started - 0.002)
        worker.join()
        return out[0], late[0]

    for round_number in range(rounds):
        for subdivisions in (6, 7, 8):
            jobs = inputs(subdivisions)
            for job, (arrays, values) in jobs.items():
                weight = len(arrays.get("faces", arrays.get("faces0", arrays.get("edges"))))
                if job == "component_labels":
                    weight = int(values["count"])
                order = ("hier", "kalt") if round_number % 2 == 0 else ("kalt", "hier")
                for where in order:
                    if where == "hier":
                        kernel_process.shutdown()
                        # Wie im Prozess der Anwendung nach dem Vorwärmen: geladen.
                        for prepare in kernel_jobs.PREPARATIONS.values():
                            prepare()
                        seconds, stall = in_worker(
                            lambda j=job, a=arrays, v=values: kernel_jobs.JOBS[j](
                                a, dict(v), lambda: None
                            )
                        )
                    else:
                        kernel_process.shutdown()
                        seconds, stall = in_worker(
                            lambda j=job, a=arrays, v=values, w=weight: kernel_process.run(
                                j, a, v, weight=w
                            )
                        )
                    print(
                        json.dumps(
                            {
                                "runde": round_number,
                                "dreiecke": weight,
                                "rechnung": job,
                                "wo": where,
                                "s": round(seconds, 3),
                                "stillstand_ms": round(stall * 1000, 1),
                            }
                        ),
                        flush=True,
                    )
    kernel_process.shutdown()


if __name__ == "__main__":
    main()
