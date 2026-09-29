"""Stufe F am echten Bestand: welcher Prozess je Stufe, und was kostet die Frage?

Aufruf: python stufen_echt.py <code-wurzel>
Baut die Einrichtung wie die Vorwahl des Druckdialogs (match), fragt
manufacturer.for_stage je Stufe und misst die Zeit; dazu die Grundlage mit
Schichthöhe und Stützschwelle.
"""

from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.export import handover, manufacturer, slicer_profiles  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402

CASES = (
    ("elegoo", r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe", "centauri-carbon-2"),
    ("orca", r"C:\Program Files\OrcaSlicer\orca-slicer.exe", "centauri-carbon-2"),
    ("bambu", r"C:\Program Files\Bambu Studio\bambu-studio.exe", "bambu-p1s"),
    ("creality", r"C:\Program Files\Creality\Creality Print 7.2\CrealityPrint.exe", "creality-k1"),
    ("prusa", r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe", "prusa-mk4s"),
    ("prusa", r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe", "sovol-sv06"),
)
for slicer, path, printer_id in CASES:
    exe = Path(path)
    profile = profiles.make_profile(printer_id, "pla")
    setup = handover.detect(exe)
    found = slicer_profiles.find_profiles(exe, setup.flavour, ("machine", "process"))
    machine, process = slicer_profiles.match(found, profile.printer)
    if machine is None or process is None:
        print(slicer, printer_id, "keine Vorwahl")
        continue
    setup = replace(
        setup,
        machine_profile=slicer_profiles.identity(machine),
        base_process=slicer_profiles.identity(process),
    )
    for quality in ("standard", "fine", "draft", "strong"):
        started = time.perf_counter()
        staged = manufacturer.for_stage(setup, profile, quality)
        asked = time.perf_counter() - started
        assert staged is not None
        foundation = manufacturer.base_settings(profile, quality, staged)
        chosen = Path(staged.base_process).stem if staged.flavour != "prusa" else staged.base_process
        print(
            f"{slicer:8} {printer_id:18} {quality:8} {asked * 1000:6.0f} ms  {chosen:40} "
            f"Schicht {foundation.settings.layers.layer_height:.2f}  "
            f"Stütze ab {foundation.settings.support.threshold_angle:.1f}  "
            f"überlagert {sorted(foundation.staged) if foundation.staged else '-'}",
            flush=True,
        )
