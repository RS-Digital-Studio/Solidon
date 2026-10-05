"""Welche Maschinenprofile jedes installierten Slicers Solidon nicht anbietet, und warum.

Sonde für Roberts Auftrag vom 05.10.2026 („bei jedem Slicer alle unterstützten
Drucker“). Aufruf aus der Wurzel: .venv\Scripts\python.exe .claude/.state/anycubic-2026-10-05/fehlende_drucker.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from app.core import build_area, discover
from app.core.export import slicer_profiles
from app.core.knowledge import profiles as known_profiles

SLICERS = (
    (r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe", "orca"),
    (r"C:\Program Files\OrcaSlicer\orca-slicer.exe", "orca"),
    (r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe", "orca"),
    (r"C:\Program Files\Bambu Studio\bambu-studio.exe", "orca"),
    (r"C:\Program Files\Creality\Creality Print 7.2\CrealityPrint.exe", "orca"),
    (r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe", "prusa"),
    (r"C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe", "cura"),
)


def main() -> int:
    report: dict[str, object] = {}
    for path, flavour in SLICERS:
        exe = Path(path)
        roots = slicer_profiles.profile_roots(flavour, exe)
        entries = list(slicer_profiles.find_profiles(exe, flavour, kinds=("machine",)))
        offered = {printer.title for printer in slicer_profiles.discover_printers(exe, flavour)}
        missing = []
        reasons: Counter[str] = Counter()
        for entry in entries:
            if entry.name in offered:
                continue
            try:
                values = slicer_profiles.resolve_profile(entry, roots, strict=True)
                printer = slicer_profiles._discovered_printer(
                    entry,
                    flavour,
                    values,
                    known_profiles.printer_profiles(),
                    discover.program_mark(exe.name),
                )
                reason = "Fläche leer" if build_area.printable_area(printer).is_empty else "?"
            except Exception as problem:  # noqa: BLE001 - Sonde: jeder Grund zählt
                reason = f"{type(problem).__name__}: {getattr(problem, 'field', '')} {problem}"[:160]
            reasons[reason] += 1
            missing.append({"name": entry.name, "path": str(entry.path), "reason": reason})
        report[exe.name] = {"entries": len(entries), "offered": len(offered), "missing": missing}
        print(f"{exe.name}: {len(entries)} Profile, {len(offered)} angeboten, {len(missing)} fehlen")
        for reason, count in reasons.most_common():
            print(f"   {count:3d}  {reason}")
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("fehlende_drucker.json")
    target.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
