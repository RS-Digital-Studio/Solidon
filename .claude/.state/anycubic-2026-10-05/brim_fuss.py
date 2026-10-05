"""Woran Anycubic Slicer Next den Brim hängt: am korrigierten oder am unkorrigierten Fuß (RM-318).

Ein Würfel 20 mm, Brim nur außen 5 mm, mit und ohne Fußkorrektur 0,3 mm und
mit Brim-Abstand 0 und -0,2. Gemessen in Schicht 1 als Abstand von der
Würfelmitte (Chebyshev): innerste Brim-Bahn gegen äußerste Außenwand.
Aufruf aus der Wurzel: .venv/Scripts/python.exe .claude/.state/anycubic-2026-10-05/brim_fuss.py <ausgabeordner>
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import trimesh

from app.core.export import slicer_profiles as sp

OUT = Path(sys.argv[1])
EXE = Path(r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe")
OUT.mkdir(parents=True, exist_ok=True)
cube = OUT / "wuerfel.stl"
trimesh.creation.box(extents=(20, 20, 20)).apply_translation((125, 125, 10)).export(cube)
everything = sp.find_profiles(EXE, "orca", ("machine", "process", "filament"))
roots = sp.profile_roots("orca", EXE)
machine = next(e for e in everything if e.kind == "machine" and e.name == "Anycubic Kobra S1 0.4 nozzle")
process = next(e for e in everything if e.kind == "process" and e.name == "0.20mm Standard @Anycubic Kobra S1 0.4 nozzle")
filament = sp.match_filament(everything, machine, "PLA", roots)
machine_doc = {"type": "machine", "from": "system", "instantiation": "true", **sp.resolve_profile(machine, roots)}
machine_doc["name"] = "Probe Maschine"
filament_doc = {"type": "filament", "from": "User", "instantiation": "true", **sp.resolve_profile(filament, roots)}
filament_doc["name"] = "Probe Filament"
base_process = sp.resolve_profile(process, roots)
(OUT / "machine.json").write_text(json.dumps(machine_doc, indent=1), encoding="utf-8")
(OUT / "filament.json").write_text(json.dumps(filament_doc, indent=1), encoding="utf-8")
MOVE = re.compile(r"^G1 .*X([-0-9.]+).*Y([-0-9.]+).*E([-0-9.]+)")
results = {}
for efc, gap in ((0.0, 0.0), (0.3, 0.0), (0.3, -0.2)):
    label = f"efc{efc}_gap{gap}"
    work = OUT / label
    work.mkdir(exist_ok=True)
    doc = {
        **base_process,
        "type": "process", "from": "system", "instantiation": "true", "name": "Probe",
        "compatible_printers": ["Probe Maschine"], "inherits": "",
        "brim_type": "outer_only", "brim_width": "5", "brim_object_gap": str(gap),
        "elefant_foot_compensation": str(efc), "skirt_loops": "0",
    }
    (work / "process.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    command = [
        str(EXE), "--load-settings", f"{OUT / 'machine.json'};{work / 'process.json'}",
        "--load-filaments", str(OUT / "filament.json"), "--slice", "0", "--outputdir", str(work), str(cube),
    ]
    run = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=900)
    gcodes = sorted(work.glob("*.gcode"))
    if not gcodes:
        results[label] = {"exit": run.returncode, "fehler": run.stdout[-500:]}
        continue
    kind, layer = "", 0
    brim, wall = [], []
    block = {}
    for line in gcodes[-1].read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(";LAYER_CHANGE"):
            layer += 1
        elif line.startswith(";TYPE:"):
            kind = line[6:].strip()
        elif line.startswith("; ") and " = " in line:
            key, _eq, value = line[2:].partition(" = ")
            block[key.strip()] = value.strip()
        elif layer == 1 and (match := MOVE.match(line)) and float(match.group(3)) > 0:
            distance = max(abs(float(match.group(1)) - 125), abs(float(match.group(2)) - 125))
            (brim if kind == "Brim" else wall if kind == "Outer wall" else []).append(distance)
    results[label] = {
        "exit": run.returncode,
        "brim_object_gap": block.get("brim_object_gap"),
        "elefant_foot_compensation": block.get("elefant_foot_compensation"),
        "brim_innen": round(min(brim), 3) if brim else None,
        "wand_aussen": round(max(wall), 3) if wall else None,
        "line_width": block.get("initial_layer_line_width"),
    }
(OUT / "brim_fuss.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
print(json.dumps(results, indent=1))
