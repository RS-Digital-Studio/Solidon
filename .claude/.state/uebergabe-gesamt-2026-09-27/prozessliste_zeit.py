"""Was kostet die Liste der Prozesse zu einem Drucker? (Stufe F, Ort der Zuordnung)

Aufruf: python prozessliste_zeit.py <code-wurzel>
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.export import handover, slicer_profiles  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402

CASES = (
    ("elegoo", r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe", "centauri-carbon-2"),
    ("bambu", r"C:\Program Files\Bambu Studio\bambu-studio.exe", "bambu-p1s"),
    ("prusa", r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe", "prusa-mk4s"),
)
for name, path, printer_id in CASES:
    exe = Path(path)
    flavour = handover.detect(exe).flavour
    printer = profiles.make_profile(printer_id, "pla").printer
    for round_ in (1, 2):
        started = time.perf_counter()
        found = slicer_profiles.find_profiles(exe, flavour, ("machine", "process"))
        listed = time.perf_counter()
        machine, process = slicer_profiles.match(found, printer)
        matched = time.perf_counter()
        fitting = slicer_profiles.processes(found, machine) if machine else []
        done = time.perf_counter()
        print(
            f"{name} Runde {round_}: find {listed - started:.2f}s, match {matched - listed:.2f}s, "
            f"processes {done - matched:.2f}s, {len(found)} Profile, {len(fitting)} passend",
            flush=True,
        )
