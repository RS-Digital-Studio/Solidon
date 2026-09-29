"""RM-252: Stürzt ElegooSlicer auch an der Originaldatei ab, wenn Stützen an sind?

    python besteck_original.py <arbeitsordner>

Die Datei ist ein ElegooSlicer-Projekt für den Centauri Carbon 2 mit zwei
Filamenten und Reinigungsturm. Sie wird zweimal geschnitten, mit dem eigenen
Projekt und ohne Solidon: so, wie sie ist (Stützen aus), und mit
``enable_support = 1`` in ``project_settings.config``.
"""

import json
import subprocess
import sys
import zipfile
from pathlib import Path

SOURCE = Path("F:/3D Dateien/Modern++Cutlery+Organizer+with+Divider.3mf")
SLICER = r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe"
work = Path(sys.argv[1])
work.mkdir(parents=True, exist_ok=True)

for label, support in (("aus", "0"), ("an", "1")):
    target = work / f"besteck_{label}.3mf"
    with zipfile.ZipFile(SOURCE) as source, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        for entry in source.namelist():
            data = source.read(entry)
            if entry == "Metadata/project_settings.config":
                settings = json.loads(data)
                settings["enable_support"] = support
                data = json.dumps(settings, indent=4).encode("utf-8")
            out.writestr(entry, data)
    folder = work / f"out_{label}"
    folder.mkdir(exist_ok=True)
    done = subprocess.run(
        [SLICER, "--slice", "0", "--outputdir", str(folder), str(target)],
        capture_output=True,
        timeout=900,
    )
    code = done.returncode
    signed = code - (1 << 32) if code >= (1 << 31) else code
    written = sorted(path.name for path in folder.glob("*.gcode"))
    tail = (done.stdout + done.stderr).decode("utf-8", "replace").strip().splitlines()[-3:]
    print(f"Stützen {label}: Rückgabe {signed} (0x{code & 0xFFFFFFFF:08X}), Druckdateien {written}, Ende {tail}", flush=True)
