"""Warum gelten fremde Prusa-Prozesse als verträglich mit dem MK4S HF0.4?

Aufruf: python prusa_bedingungen.py <code-wurzel>
Liest die Einträge über Solidons eigenen Weg und zeigt je Prozess Liste,
Bedingung und das Urteil von _prusa_fits.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.export import prusa_conditions, slicer_profiles  # noqa: E402

EXE = Path(r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe")
found = list(slicer_profiles.find_profiles(EXE, "prusa", ("machine", "process")))
machine = next(entry for entry in found if entry.name == "Original Prusa MK4S HF0.4 nozzle")
values = dict(machine.variables)
print("Maschine:", machine.name, "| Variablen:", len(values))
for key in ("printer_notes", "printer_model", "nozzle_diameter", "nozzle_high_flow", "printer_vendor"):
    print(f"  {key} = {str(values.get(key))[:160]!r}")
print("from_user:", machine.from_user, "section:", machine.section)
for name in (
    "0.12mm DETAIL @BIBO2",
    "0.14mm DETAIL @lulzbot",
    "0.1 Layer - 0,4 Nozzle",
    "0.20mm @Zonestar SINGLE",
    "0.20mm STRUCTURAL @MK4S 0.4",
    "0.20mm SPEED @MK4S HF0.4",
    "0.25mm STRUCTURAL @MK4S HF0.4",
):
    entry = next((item for item in found if item.name == name and item.kind == "process"), None)
    if entry is None:
        print(name, "-> nicht gefunden")
        continue
    try:
        verdict = prusa_conditions.holds(entry.condition, values)
    except prusa_conditions.ConditionError as problem:
        verdict = f"Fehler: {problem}"
    print(f"{name}\n  path={entry.path} section={entry.section!r} user={entry.from_user}")
    print(f"  list={entry.compatible_printers!r}\n  condition={entry.condition!r}\n  holds={verdict}")
