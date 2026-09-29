"""Die Übergabe-3MF mit geänderten Projekteinstellungen schneiden und die ersten Schichten zählen.

Aufruf: python variante.py <übergabe.3mf> <ordner> key=wert …
Werte, die in der Datei Listen sind, bleiben Listen.
"""
# ruff: noqa: E501

import json
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import druck  # noqa: E402

source = Path(sys.argv[1])
folder = Path(sys.argv[2])
folder.mkdir(parents=True, exist_ok=True)
changes = dict(arg.split("=", 1) for arg in sys.argv[3:])
with zipfile.ZipFile(source) as src:
    cfg = json.loads(src.read("Metadata/project_settings.config"))
    for key, value in changes.items():
        cfg[key] = [value] if isinstance(cfg.get(key), list) else value
    target = folder / "in.3mf"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "Metadata/project_settings.config":
                data = json.dumps(cfg, indent=1).encode()
            dst.writestr(item, data)
run = subprocess.run([str(druck.ELEGOO), "--arrange", "0", "--slice", "0", "--outputdir", str(folder), str(target)], capture_output=True, text=True, encoding="utf-8", errors="replace")
print("Slicer-Exit", run.returncode)
data = druck.read_gcode(folder / "plate_1.gcode")
head = data["header"]
print("Zeit", head.get("estimated printing time (normal mode)"), "| Filament", head.get("filament used [g]"), "g | Stütze", data["support_m"], "m | Modell", data["model_m"], "m | Rand", data["rim_m"], "m")
for number, layer in enumerate(data["first_layers"], start=1):
    print(f"  Schicht {number} z={layer['z']}: {layer['paths']} Leerfahrten {layer['travels']} (> 2 mm: {layer['long_travels']})")
