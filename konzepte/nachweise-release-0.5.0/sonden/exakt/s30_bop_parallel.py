"""Boolesche des exakten Kerns mit und ohne ``SetRunParallel`` (Review 23.09.2026).

Abwechselnd im selben Prozess, Median über die Läufe; jeder Fall prüft, dass
beide Wege dasselbe Volumen liefern. Fälle: Cat_3-Gehäuse plus Gewindehals,
Gewindebolzen M3 x 0,5 x 60 auf Länge geschnitten, Bohrung in build_tray_v3,
Quader minus Zylinder (klein).
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

TREE = r"F:\3D Druck.review-050\wt-exakt"
sys.path.insert(0, TREE)
import app  # noqa: E402

print(app.__file__)
import app.core.brep.kernel as kernel  # noqa: E402
from app.core.brep import edit, profiles, step  # noqa: E402
from app.core.knowledge.parts.build import threaded  # noqa: E402
from app.core.knowledge.parts.shapes import building  # noqa: E402

original = kernel.boolean_builder
PARALLEL = {"on": False}


def builder(kind, first, second, *, tolerance=None):
    operation = original(kind, first, second, tolerance=tolerance)
    operation.SetRunParallel(PARALLEL["on"])
    return operation


kernel.boolean_builder = builder
edit.boolean_builder = builder  # type: ignore[attr-defined]
profiles.boolean_builder = builder  # type: ignore[attr-defined]

cat = step.read((Path(r"F:\3D Dateien") / "Cat_3.stp").read_bytes())
tray = step.read((Path(r"F:\3D Dateien") / "build_tray_v3.step").read_bytes())
with building("brep"):
    rod = threaded(40.08, 3.0, 8.0, bottom=float(cat.bounds.maximum[2]))
neck = edit.moved(rod, (-15.0, -37.0, 0.0))
long_rod = profiles.helical_thread(1.5 - 0.3, 0.5, 124, ((1.2, 0.0), (1.5, 0.125), (1.5, 0.275), (1.2, 0.4)), start=-0.5)
bar = edit.box(100.0, 100.0, 60.0)
bore = edit.moved(edit.cylinder(20.0, 80.0), (60.0, 100.0, -5.0))

cases = {
    "cat+neck": lambda: edit.boolean("union", [cat, neck]),
    "rod-cut": lambda: edit.boolean("intersection", [long_rod, bar]),
    "tray-bore": lambda: edit.boolean("difference", [tray, bore]),
    "box-cyl": lambda: edit.boolean("difference", [edit.box(20, 20, 20), edit.cylinder(5, 30)]),
}
for name, case in cases.items():
    times = {False: [], True: []}
    volumes = {}
    for _round in range(4):
        for flag in (False, True):
            PARALLEL["on"] = flag
            started = time.perf_counter()
            result = case()
            times[flag].append(time.perf_counter() - started)
            volumes[flag] = result.volume
    serial, parallel = statistics.median(times[False]), statistics.median(times[True])
    print(
        f"{name}: serial {serial:.3f} s parallel {parallel:.3f} s factor {serial / parallel:.2f} "
        f"volume {volumes[False]:.6f} / {volumes[True]:.6f}"
    )
