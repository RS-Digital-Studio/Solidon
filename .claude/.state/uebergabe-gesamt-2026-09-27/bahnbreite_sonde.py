"""Sonde Paket 3: Gilt der Bahnbreitenvorschlag am Kobra 2 je Teil?

Aufruf: python bahnbreite_sonde.py <code-wurzel> <ausgabe.json> [drucker] [slicer]

Der Minigolf-Satz wie im Druckerplan (elegoo · anycubic-kobra-2), die Vorschläge
wie der Druckdialog (``_AdviceWorker``), dazu die Trennung der Übergabe
(``handover.split_for_parts``): Welche Pfade gehen je Teil, welche plattenweit?
"""
# ruff: noqa: E501

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TREE = sys.argv[1]
TARGET = Path(sys.argv[2])
PRINTER = sys.argv[3] if len(sys.argv) > 3 else "anycubic-kobra-2"
SLICER = sys.argv[4] if len(sys.argv) > 4 else "elegoo"
MODEL = r"F:\3D Druck\output\review\minigolf-2026-09-27\druckauftrag\solidon-0936.3mf"
sys.argv = [sys.argv[0], TREE, MODEL, str(TARGET.parent), "heim"]
sys.path.insert(0, str(HERE))
os.environ["GESAMT_AUSRICHTEN"] = "0"

# RM-530: die Matrix in tools/ — angehängt, damit ``app`` weiter aus der
# Code-Wurzel kommt, die das Skript davorgelegt hat (Review 06.10.2026, N11).
sys.path.append(str(Path(__file__).resolve().parents[3]))
from tools import matrix_unit as einheit  # noqa: E402

from app.core.export import handover, manufacturer  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.ui.print_settings_dialog import _AdviceWorker, _TargetedAdvice  # noqa: E402


def main() -> None:
    profile = profiles.make_profile(PRINTER, einheit.MATERIAL)
    setup, info = einheit.prepared(SLICER, profile)
    if setup is None:
        TARGET.write_text(json.dumps({"skip": info}, ensure_ascii=False), encoding="utf-8")
        return
    foundation = manufacturer.base_settings(profile, "standard", setup)
    settings = manufacturer.effective(None, foundation)
    objects, _findings = einheit.load(Path(MODEL))
    worker = _AdviceWorker(
        tuple(objects), settings, profile, setup, {}, (), advise.connector_diameters(objects), {},
        flavour=setup.flavour,
    )
    got: list[Any] = []
    worker.done.connect(lambda entries, _results: got.append(entries))
    worker.work()
    rows = [entry for entry in got[0] if einheit.offered(entry, setup.flavour)]
    plate_rows = [e for e in rows if not (isinstance(e, _TargetedAdvice) and e.slot is not None)]
    accepted = advise.apply(settings, plate_rows)
    split = handover.split_for_parts(accepted, profile, setup, setup.flavour)
    result = {
        "printer": PRINTER,
        "slicer": SLICER,
        "process": setup.base_process,
        "line_width_foundation": settings.layers.line_width,
        "advice": [
            {
                "path": entry.path,
                "was": str(entry.was),
                "value": str(entry.value),
                "parts": list(entry.parts) if isinstance(entry, _TargetedAdvice) else [],
                "reason": str(entry.reason)[:160],
            }
            for entry in rows
        ],
        "per_part": sorted(split.per_part),
        "unavailable": sorted(split.unavailable),
        "plate_line_width": split.plate.layers.line_width,
    }
    TARGET.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
