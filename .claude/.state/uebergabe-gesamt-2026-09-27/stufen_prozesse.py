"""Stufe F vorbereiten: Welche Prozesse führt jeder Hersteller je Drucker?

Aufruf: python stufen_prozesse.py <code-wurzel> <ausgabe.json>
Je installiertem Slicer der Orca-Familie und PrusaSlicer, je Drucker aus
printers.toml: die vorgewählte Maschine, ihr Standardprozess und alle
verträglichen Prozesse mit der Schichthöhe aus dem Namen.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.export import handover, slicer_profiles  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402

SLICERS = {
    "elegoo": r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe",
    "bambu": r"C:\Program Files\Bambu Studio\bambu-studio.exe",
    "creality": r"C:\Program Files\Creality\Creality Print 7.2\CrealityPrint.exe",
    "orca": r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
    "prusa": r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe",
}
# Optional drittes Argument: nur diese Slicer, durch Komma getrennt.
if len(sys.argv) > 3:
    SLICERS = {key: SLICERS[key] for key in sys.argv[3].split(",")}

report: dict[str, object] = {}
for slicer, path in SLICERS.items():
    exe = Path(path)
    if not exe.exists():
        report[slicer] = {"skip": "nicht installiert"}
        continue
    setup = handover.detect(exe)
    found = list(slicer_profiles.find_profiles(exe, setup.flavour, ("machine", "process")))
    rows: dict[str, object] = {}
    for printer_id in sorted(profiles.printer_profiles()):
        printer = profiles.make_profile(printer_id, "pla").printer
        if printer.is_resin:
            continue
        machine, process = slicer_profiles.match(found, printer)
        if machine is None:
            continue
        fitting = slicer_profiles.processes(found, machine)
        rows[printer_id] = {
            "machine": machine.name,
            "default": machine.default_process,
            "chosen": process.name if process else "",
            "printer_layer": printer.layer_height,
            "processes": [entry.name for entry in fitting],
        }
    report[slicer] = rows
    print(slicer, len(rows), flush=True)

Path(sys.argv[2]).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
