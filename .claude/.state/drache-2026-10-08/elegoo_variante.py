"""Eine Elegoo-Übergabe mit geänderten Prozesswerten neu schneiden.

Aufruf: python elegoo_variante.py <übergabe.3mf> <ausgabeordner> <schlüssel=wert> [...]

Kopiert die 3MF, ersetzt die Werte in ``Metadata/project_settings.config`` und
schneidet sie mit dem installierten ElegooSlicer ohne weitere Profile.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

SLICER = Path(r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe")

source = Path(sys.argv[1])
output = Path(sys.argv[2])
changes = dict(item.split("=", 1) for item in sys.argv[3:])
output.mkdir(parents=True, exist_ok=True)
target = output / source.name
with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as new:
    for item in old.infolist():
        data = old.read(item.filename)
        if item.filename == "Metadata/project_settings.config":
            settings = json.loads(data)
            for key, value in changes.items():
                settings[key] = value
            data = json.dumps(settings, indent=4).encode("utf-8")
        new.writestr(item, data)
run = subprocess.run(
    [str(SLICER), "--slice", "0", "--outputdir", str(output), str(target)],
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=1800,
)
print("Exit", run.returncode, (run.stderr or run.stdout)[-400:])
for gcode in output.glob("*.gcode"):
    print(gcode, gcode.stat().st_size)
shutil.copy2(source, output / ("vorher-" + source.name))
