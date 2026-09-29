"""RM-252: Stürzt der Slicer am Originalprojekt ab, sobald normale Autostützen an sind?

    python nachstellung.py <arbeitsordner>

Das Originalprojekt (ElegooSlicer, Centauri Carbon 2, zwei Filamente,
Reinigungsturm) wird nur gelesen. Je Slicer drei Kopien: wie es ist,
``enable_support = 1`` mit der Stützart des Projekts (``tree(auto)``) und
``enable_support = 1`` mit ``support_type = normal(auto)`` — der kleinste Satz
aus der Bisektion vom 26.09.2026.
"""

import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

SOURCE = Path("F:/3D Dateien/Modern++Cutlery+Organizer+with+Divider.3mf")
SLICERS = {
    "elegoo": r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe",
    "orca": r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
}
CASES = {
    "original": {},
    "stuetzen_baum": {"enable_support": "1"},
    "stuetzen_normal": {"enable_support": "1", "support_type": "normal(auto)"},
}

work = Path(sys.argv[1])
work.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(SOURCE) as source:
    original = json.loads(source.read("Metadata/project_settings.config"))
print(
    "Original:",
    {key: original.get(key) for key in ("enable_support", "support_type", "printer_model")},
    flush=True,
)

for label, changes in CASES.items():
    target = work / f"besteck_{label}.3mf"
    with (
        zipfile.ZipFile(SOURCE) as source,
        zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out,
    ):
        for entry in source.namelist():
            data = source.read(entry)
            if entry == "Metadata/project_settings.config" and changes:
                settings = json.loads(data)
                settings.update(changes)
                data = json.dumps(settings, indent=4).encode("utf-8")
            out.writestr(entry, data)
    for slicer, executable in SLICERS.items():
        folder = work / f"out_{slicer}_{label}"
        folder.mkdir(exist_ok=True)
        began = time.monotonic()
        try:
            done = subprocess.run(
                [executable, "--slice", "0", "--outputdir", str(folder), str(target)],
                capture_output=True,
                timeout=1200,
            )
            code = done.returncode & 0xFFFFFFFF
            tail = (done.stdout + done.stderr).decode("utf-8", "replace").strip().splitlines()[-2:]
        except subprocess.TimeoutExpired:
            code, tail = None, ["FRIST"]
        written = sorted(path.name for path in folder.glob("*.gcode"))
        shown = "FRIST" if code is None else f"0x{code:08X}"
        print(
            f"{slicer:7} {label:16} Rückgabe {shown}, G-Code {written}, "
            f"{time.monotonic() - began:.0f} s, Ende {tail}",
            flush=True,
        )
