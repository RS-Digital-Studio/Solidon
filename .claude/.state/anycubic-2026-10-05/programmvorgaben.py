"""Die eingebauten Vorgaben von Anycubic Slicer Next für die übersetzten Prozessschlüssel.

Wie ``herstellerprofil-2026-09-27/programmvorgaben.py``: vollständige Maschine
und Filament des Herstellers, **leerer** Prozess; was im Konfigurationsblock
steht, ist die Vorgabe des Programms. Dazu Platte und Stützfuß.
Aufruf aus der Wurzel: .venv/Scripts/python.exe .claude/.state/anycubic-2026-10-05/programmvorgaben.py <ausgabeordner>
"""

import json
import subprocess
import sys
from pathlib import Path

import trimesh

from app.core.export import slicer_profiles as sp

OUT = Path(sys.argv[1])
EXE = Path(r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe")
MACHINE = sys.argv[2] if len(sys.argv) > 2 else "Anycubic Kobra S1 0.4 nozzle"
KEYS = (
    "layer_height initial_layer_print_height line_width initial_layer_line_width wall_loops "
    "top_shell_layers bottom_shell_layers wall_sequence seam_position wall_generator precise_outer_wall "
    "ironing_type sparse_infill_density sparse_infill_pattern infill_direction outer_wall_speed "
    "inner_wall_speed sparse_infill_speed top_surface_speed initial_layer_speed travel_speed bridge_speed "
    "default_acceleration outer_wall_acceleration enable_support support_type support_on_build_plate_only "
    "support_threshold_angle support_top_z_distance support_object_xy_distance support_interface_top_layers "
    "support_base_pattern_spacing brim_type skirt_loops skirt_distance brim_width brim_object_gap raft_layers "
    "reduce_crossing_wall curr_bed_type initial_layer_acceleration raft_first_layer_expansion "
    "brim_use_efc_outline raft_contact_distance"
).split()
OUT.mkdir(parents=True, exist_ok=True)
cube = OUT / "wuerfel.stl"
trimesh.creation.box(extents=(20, 20, 20)).apply_translation((125, 125, 10)).export(cube)
everything = sp.find_profiles(EXE, "orca", ("machine", "process", "filament"))
roots = sp.profile_roots("orca", EXE)
machine = next(entry for entry in everything if entry.kind == "machine" and entry.name == MACHINE)
filament = sp.match_filament(everything, machine, "PLA", roots)
machine_doc = {"type": "machine", "from": "system", "instantiation": "true"}
machine_doc.update(sp.resolve_profile(machine, roots))
machine_doc["name"] = "Probe Maschine"
process_doc = {
    "type": "process",
    "from": "system",
    "instantiation": "true",
    "name": "Probe leer",
    "compatible_printers": ["Probe Maschine"],
}
filament_doc = {"type": "filament", "from": "User", "instantiation": "true"}
filament_doc.update(
    sp.resolve_profile(filament, roots)
)
filament_doc["name"] = "Probe Filament"
for name, doc in (("machine", machine_doc), ("process", process_doc), ("filament", filament_doc)):
    (OUT / f"{name}.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
command = [
    str(EXE), "--load-settings", f"{OUT / 'machine.json'};{OUT / 'process.json'}",
    "--load-filaments", str(OUT / "filament.json"), "--slice", "0", "--outputdir", str(OUT), str(cube),
]
run = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=900)
gcodes = sorted(OUT.glob("*.gcode"))
found = {}
if gcodes:
    for line in gcodes[-1].read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("; ") and " = " in line:
            key, _eq, value = line[2:].partition(" = ")
            if key.strip() in KEYS:
                found[key.strip()] = value.strip()
summary = {
    "machine": machine.name,
    "filament": filament.name if filament else None,
    "exit": run.returncode,
    "gcode": str(gcodes[-1]) if gcodes else None,
    "values": found,
    "missing_in_output": [k for k in KEYS if k not in found],
    "stdout": run.stdout[-1500:],
    "stderr": run.stderr[-1500:],
}
(OUT / "vorgaben.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary, indent=1, ensure_ascii=False)[:6000])
