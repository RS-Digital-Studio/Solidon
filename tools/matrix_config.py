"""Gemeinsame Auswahl der sieben installierten Slicer für die Matrix."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

SLICERS: dict[str, str] = {
    "elegoo": r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe",
    "bambu": r"C:\Program Files\Bambu Studio\bambu-studio.exe",
    "creality": r"C:\Program Files\Creality\Creality Print 7.2\CrealityPrint.exe",
    "orca": r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
    "prusa": r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe",
    "cura": r"C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe",
    "superslicer": str(
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "SuperSlicer" / "SuperSlicer.exe"
    ),
}

SLICER_FLAVOURS: dict[str, Literal["orca", "prusa", "cura"]] = {
    "elegoo": "orca",
    "bambu": "orca",
    "creality": "orca",
    "orca": "orca",
    "prusa": "prusa",
    "cura": "cura",
    "superslicer": "prusa",
}

HOME: dict[str, str] = {
    "elegoo": "centauri-carbon-2",
    "bambu": "bambu-p1s",
    "creality": "creality-k1",
    "orca": "anycubic-kobra-2",
    "prusa": "prusa-mk4s",
    "cura": "sovol-sv06",
    "superslicer": "prusa-mini",
}
