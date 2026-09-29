"""Die eingebauten Vorgaben der Orca-Familie für die übersetzten Prozessschlüssel.

Je Programm ein Lauf mit vollständiger Maschine und Filament des Herstellers,
aber einem **leeren** Prozess: Was dann im Konfigurationsblock des G-Codes
steht, ist die Vorgabe des Programms. Aufruf:
python programmvorgaben.py <code-wurzel> <ausgabeordner>
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT)
import trimesh  # noqa: E402

from app.core.export import slicer_profiles as sp  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402

KEYS = (
    "layer_height initial_layer_print_height line_width initial_layer_line_width wall_loops "
    "top_shell_layers bottom_shell_layers wall_sequence seam_position wall_generator precise_outer_wall "
    "ironing_type sparse_infill_density sparse_infill_pattern infill_direction outer_wall_speed "
    "inner_wall_speed sparse_infill_speed top_surface_speed initial_layer_speed travel_speed bridge_speed "
    "default_acceleration outer_wall_acceleration enable_support support_type support_on_build_plate_only "
    "support_threshold_angle support_top_z_distance support_object_xy_distance support_interface_top_layers "
    "support_base_pattern_spacing brim_type skirt_loops skirt_distance brim_width raft_layers "
    "reduce_crossing_wall curr_bed_type initial_layer_acceleration"
).split()
RUNS = {
    "ElegooSlicer": (Path(r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe"), "centauri-carbon-2", "PLA"),
    "OrcaSlicer": (Path(r"C:\Program Files\OrcaSlicer\orca-slicer.exe"), "centauri-carbon-2", "PLA"),
    "BambuStudio": (Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe"), "bambu-a1", "PLA"),
    "CrealityPrint": (Path(r"C:\Program Files\Creality\Creality Print 7.2\CrealityPrint.exe"), "creality-k1", "PLA"),
}
OUT.mkdir(parents=True, exist_ok=True)
cube = OUT / "wuerfel.stl"
trimesh.creation.box(extents=(20, 20, 20)).apply_translation((0, 0, 10)).export(cube)
summary = {}
for program, (exe, printer_id, material) in RUNS.items():
    work = OUT / program
    work.mkdir(exist_ok=True)
    everything = sp.find_profiles(exe, "orca", ("machine", "process", "filament"))
    roots = sp.profile_roots("orca", exe)
    machine, _process = sp.match(everything, profiles.printer(printer_id))
    filament = sp.match_filament(everything, machine, material, roots)
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
    filament_doc.update({k: (v if isinstance(v, list) else [v]) for k, v in sp.resolve_profile(filament, roots).items()})
    filament_doc["name"] = "Probe Filament"
    for name, doc in (("machine", machine_doc), ("process", process_doc), ("filament", filament_doc)):
        (work / f"{name}.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    command = [
        str(exe), "--load-settings", f"{work / 'machine.json'};{work / 'process.json'}",
        "--load-filaments", str(work / "filament.json"), "--slice", "0", "--outputdir", str(work), str(cube),
    ]
    run = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=600)
    gcodes = sorted(work.glob("*.gcode"))
    found = {}
    if gcodes:
        for line in gcodes[-1].read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("; ") and " = " in line:
                key, _eq, value = line[2:].partition(" = ")
                if key.strip() in KEYS:
                    found[key.strip()] = value.strip()
    summary[program] = {
        "machine": machine.name,
        "filament": filament.name if filament else None,
        "exit": run.returncode,
        "gcode": str(gcodes[-1]) if gcodes else None,
        "values": found,
        "missing_in_output": [k for k in KEYS if k not in found],
        "stderr": run.stderr[-600:],
    }
    print(program, machine.name, "exit", run.returncode, "gcode", bool(gcodes), len(found))
(OUT / "vorgaben.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
