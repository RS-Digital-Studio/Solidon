"""Welche übersetzten Schlüssel fehlen in den Herstellerketten? (27.09.2026)

Je Orca-Programm und Solidon-Drucker: Maschine und Standardprozess nach
``slicer_profiles.match``, dazu das PLA nach ``match_filament``; aufgelöst.
Gelistet wird, welche Schlüssel der Rücklesung in der Kette fehlen — dort gilt
die eingebaute Vorgabe des Programms.
"""
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else r"F:\3D Druck.minigolf")
sys.path.insert(0, str(ROOT))
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT)
from app.core.export import slicer_profiles  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402

PROGRAMS = {
    "ElegooSlicer": Path(r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe"),
    "OrcaSlicer": Path(r"C:\Program Files\OrcaSlicer\orca-slicer.exe"),
    "BambuStudio": Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe"),
    "CrealityPrint": Path(r"C:\Program Files\Creality\Creality Print 7.2\CrealityPrint.exe"),
}
PROCESS_KEYS = (
    "layer_height initial_layer_print_height line_width initial_layer_line_width wall_loops "
    "top_shell_layers bottom_shell_layers wall_sequence seam_position wall_generator precise_outer_wall "
    "ironing_type sparse_infill_density sparse_infill_pattern infill_direction outer_wall_speed "
    "inner_wall_speed sparse_infill_speed top_surface_speed initial_layer_speed travel_speed bridge_speed "
    "default_acceleration outer_wall_acceleration enable_support support_type support_on_build_plate_only "
    "support_threshold_angle support_top_z_distance support_object_xy_distance support_interface_top_layers "
    "support_base_pattern_spacing brim_type skirt_loops skirt_distance brim_width raft_layers "
    "reduce_crossing_wall"
).split()
FILAMENT_KEYS = (
    "nozzle_temperature nozzle_temperature_initial_layer hot_plate_temp textured_plate_temp cool_plate_temp "
    "eng_plate_temp chamber_temperature fan_max_speed fan_min_speed fan_cooling_layer_time overhang_fan_speed "
    "close_fan_the_first_x_layers slow_down_layer_time filament_density filament_flow_ratio "
    "filament_max_volumetric_speed filament_diameter filament_retraction_length filament_retraction_speed "
    "filament_z_hop filament_wipe reduce_fan_stop_start_freq"
).split()
MACHINE_KEYS = "retraction_length retraction_speed z_hop wipe default_bed_type nozzle_diameter".split()

missing: dict[tuple[str, str], list[str]] = defaultdict(list)
for program, exe in PROGRAMS.items():
    if not exe.exists():
        found = list(exe.parent.glob("*.exe"))
        print(program, "fehlt", exe, [p.name for p in found][:6])
        continue
    everything = slicer_profiles.find_profiles(exe, "orca")
    roots = slicer_profiles.profile_roots("orca", exe)
    for printer in profiles.printer_profiles().values():
        if printer.technology != "fdm" or printer.id.startswith("generic"):
            continue
        machine, process = slicer_profiles.match(everything, printer)
        if machine is None:
            continue
        filament = slicer_profiles.match_filament(everything, machine, "PLA", roots)
        row = f"{program:13} {printer.id:22} {machine.name[:40]:40} | {process.name[:45] if process else '-':45} | {filament.name[:32] if filament else '-'}"
        print(row)
        for kind, entry, keys in (("process", process, PROCESS_KEYS), ("filament", filament, FILAMENT_KEYS), ("machine", machine, MACHINE_KEYS)):
            if entry is None:
                continue
            values = slicer_profiles.resolve_profile(entry, roots)
            for key in keys:
                raw = values.get(key)
                if isinstance(raw, list):
                    raw = raw[0] if raw else None
                if raw is None or raw == "":
                    missing[(program, kind)].append(f"{key}")
                elif raw == "nil":
                    missing[(program, kind + "-nil")].append(f"{key}")
print()
for (program, kind), keys in sorted(missing.items()):
    counts: dict[str, int] = defaultdict(int)
    for key in keys:
        counts[key] += 1
    print(program, kind, dict(sorted(counts.items())))
