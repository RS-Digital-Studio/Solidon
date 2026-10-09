"""Was ein Slicer wirklich druckt: Temperaturen, Lüfter, Tempo, Beschleunigung,
Rückzug, Schichten — gemessen an den Befehlen und gelesen aus der Konfiguration.

Aufruf: python einstellungen.py <ausgabe.json> <name=gcode> [<name=gcode> …]

Gemessen (Befehle): Düsen- und Betttemperatur der ersten und der übrigen
Schichten, Bauteillüfter je Schicht (M106 ohne P oder P0/P1), Beschleunigung
(M204 S/P, SET_VELOCITY_LIMIT ACCEL), Tempo je Bahnart (Median und 90 %-Wert
der Vorschübe beim Extrudieren, mm/s), Rückzug (Länge und Tempo), Z-Hub,
Schichthöhe. Gelesen (Konfiguration): eine feste Liste von Schlüsseln je
Familie, soweit vorhanden.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

TYPE = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
LAYER_CHANGE = re.compile(r"^;\s*(?:LAYER_CHANGE|CHANGE_LAYER)\b", re.IGNORECASE)
LAYER_NUMBER = re.compile(r"^;\s*LAYER\s*:\s*-?\d+", re.IGNORECASE)
WORD = re.compile(r"([A-Z])(-?(?:\d+\.?\d*|\.\d+))")
CONFIG = re.compile(r"^;\s*([a-z0-9_]+)\s*=\s*(.*)$")

#: Schlüssel, die im Bericht stehen — Orca-Familie, PrusaSlicer, Cura.
KEYS = (
    "layer_height",
    "initial_layer_print_height",
    "first_layer_height",
    "wall_loops",
    "perimeters",
    "wall_line_count",
    "sparse_infill_density",
    "fill_density",
    "infill_sparse_density",
    "sparse_infill_pattern",
    "fill_pattern",
    "infill_pattern",
    "nozzle_temperature",
    "nozzle_temperature_initial_layer",
    "temperature",
    "first_layer_temperature",
    "material_print_temperature",
    "material_print_temperature_layer_0",
    "hot_plate_temp",
    "textured_plate_temp",
    "bed_temperature",
    "first_layer_bed_temperature",
    "material_bed_temperature",
    "fan_min_speed",
    "fan_max_speed",
    "min_fan_speed",
    "max_fan_speed",
    "cool_fan_speed",
    "cool_fan_speed_max",
    "close_fan_the_first_x_layers",
    "disable_fan_first_layers",
    "fan_cooling_layer_time",
    "slow_down_layer_time",
    "slowdown_below_layer_time",
    "cool_min_layer_time",
    "slow_down_min_speed",
    "min_print_speed",
    "cool_min_speed",
    "overhang_fan_speed",
    "overhang_fan_threshold",
    "bridge_fan_speed",
    "outer_wall_speed",
    "inner_wall_speed",
    "sparse_infill_speed",
    "perimeter_speed",
    "external_perimeter_speed",
    "infill_speed",
    "speed_wall_0",
    "speed_wall_x",
    "speed_infill",
    "initial_layer_speed",
    "first_layer_speed",
    "speed_layer_0",
    "travel_speed",
    "speed_travel",
    "default_acceleration",
    "outer_wall_acceleration",
    "acceleration_print",
    "acceleration_wall_0",
    "retraction_length",
    "retract_length",
    "retraction_amount",
    "retraction_speed",
    "retract_speed",
    "z_hop",
    "retract_lift",
    "retraction_hop",
    "enable_support",
    "support_material",
    "support_enable",
    "support_type",
    "support_style",
    "support_material_style",
    "support_structure",
    "support_tree_enable",
    "support_threshold_angle",
    "support_material_threshold",
    "support_angle",
    "support_top_z_distance",
    "support_material_contact_distance",
    "support_top_distance",
    "support_on_build_plate_only",
    "support_material_buildplate_only",
    "support_type",
    "support_object_xy_distance",
    "support_material_xy_spacing",
    "support_xy_distance",
    "support_interface_top_layers",
    "support_material_interface_layers",
    "support_roof_height",
    "support_bottom_z_distance",
    "support_material_bottom_contact_distance",
    "support_bottom_distance",
    "support_interface_spacing",
    "support_material_interface_spacing",
    "support_roof_enable",
    "support_interface_enable",
    "brim_type",
    "brim_width",
    "adhesion_type",
    "seam_position",
    "z_seam_type",
    "wall_generator",
    "perimeter_generator",
    "filament_max_volumetric_speed",
    "max_volumetric_speed",
    "filament_settings_id",
    "print_settings_id",
)


def kind_of(raw: str) -> str:
    lowered = raw.lower()
    if "support" in lowered or "tree" in lowered:
        return "Stütze"
    if "external" in lowered or "outer" in lowered or lowered == "wall-outer":
        return "Außenwand"
    if "perimeter" in lowered or "inner" in lowered or "wall" in lowered:
        return "Innenwand"
    if "bridge" in lowered:
        return "Brücke"
    if "overhang" in lowered:
        return "Überhangwand"
    if "top" in lowered or "solid" in lowered or "skin" in lowered or "bottom" in lowered:
        return "Vollfläche"
    if "infill" in lowered or "fill" in lowered:
        return "Füllung"
    if "brim" in lowered or "skirt" in lowered:
        return "Rand"
    return raw


def config_of(path: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    size = path.stat().st_size
    with path.open(encoding="utf-8", errors="replace") as handle:
        head = handle.read(400_000)
        handle.seek(max(0, size - 3_000_000))
        tail = handle.read()
    for text in (head, tail):
        for line in text.splitlines():
            match = CONFIG.match(line.strip())
            if match and match.group(1) in KEYS and match.group(1) not in found:
                found[match.group(1)] = match.group(2).strip()[:80]
            if line.startswith(";SETTING_3"):
                found["_cura"] = found.get("_cura", "") + line[len(";SETTING_3 ") :]
    if "_cura" in found:
        blob = found.pop("_cura").replace("\\\\n", "\n")
        for key in KEYS:
            match = re.search(rf"\b{key}\s*=\s*([^\\\n]+)", blob)
            if match and key not in found:
                found[key] = match.group(1).strip()[:80]
    return found


def measure(path: Path) -> dict:
    layer = 0
    kind = ""
    x = y = z = 0.0
    feed = 0.0
    relative_e = False
    e_abs = 0.0
    nozzle: list[tuple[int, float]] = []
    bed: list[tuple[int, float]] = []
    fan_by_layer: dict[int, list[float]] = defaultdict(list)
    accel: Counter = Counter()
    speeds: dict[str, list[float]] = defaultdict(list)
    retracts: list[tuple[float, float]] = []
    hops: list[float] = []
    heights: Counter = Counter()
    last_z = 0.0
    fan = 0.0
    marked = False
    with path.open(encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if line.startswith(";"):
                if LAYER_CHANGE.match(line):
                    marked = True
                    layer += 1
                elif not marked and LAYER_NUMBER.match(line):
                    layer += 1
                found = TYPE.match(line)
                if found:
                    kind = kind_of(found.group(1))
                continue
            code = line.split(";", 1)[0].strip().upper()
            if not code:
                continue
            head = code.split()[0]
            words = dict(WORD.findall(code[len(head) :]))
            if head in ("M104", "M109") and float(words.get("S", 0)) > 0:
                nozzle.append((layer, float(words["S"])))
            elif head in ("M140", "M190") and float(words.get("S", 0)) > 0:
                bed.append((layer, float(words["S"])))
            elif head == "M106" and words.get("P", "0") in ("0", "1") and "S" in words:
                fan = float(words["S"])
                fan_by_layer[layer].append(fan / 2.55 if fan > 1.0 else fan * 100.0)
            elif head == "M107":
                fan_by_layer[layer].append(0.0)
            elif head == "M204":
                for letter in ("S", "P"):
                    if letter in words:
                        accel[float(words[letter])] += 1
            elif head == "SET_VELOCITY_LIMIT":
                match = re.search(r"ACCEL=(\d+\.?\d*)", code)
                if match:
                    accel[float(match.group(1))] += 1
            elif head == "M83":
                relative_e = True
            elif head == "M82":
                relative_e = False
            elif head == "G92" and "E" in words:
                e_abs = float(words["E"])
            elif head in ("G0", "G1", "G2", "G3"):
                if "F" in words:
                    feed = float(words["F"]) / 60.0
                nx = float(words.get("X", x))
                ny = float(words.get("Y", y))
                nz = float(words.get("Z", z))
                delta = 0.0
                if "E" in words:
                    e = float(words["E"])
                    delta = e if relative_e else e - e_abs
                    if not relative_e:
                        e_abs = e
                moved = nx != x or ny != y
                if delta > 1e-5 and moved and layer > 1 and kind:
                    speeds[kind].append(feed)
                elif -10.0 < delta < -1e-3 and not moved:
                    retracts.append((-delta, feed))
                if nz > z + 1e-6 and not moved and delta == 0.0:
                    hops.append(nz - z)
                if delta > 1e-5 and moved and nz != last_z:
                    heights[round(nz - last_z, 3)] += 1
                    last_z = nz
                x, y, z = nx, ny, nz

    def typical(values: list[float]) -> list[float] | None:
        if not values:
            return None
        ordered = sorted(values)
        return [
            round(statistics.median(ordered), 1),
            round(ordered[int(0.9 * (len(ordered) - 1))], 1),
        ]

    fans = {
        number: round(max(values), 0) for number, values in sorted(fan_by_layer.items()) if values
    }
    later = [value for number, value in fans.items() if number > 3]
    return {
        "nozzle_first": [value for number, value in nozzle if number <= 1][-1:] or None,
        "nozzle_later": sorted({value for number, value in nozzle if number > 1}) or None,
        "bed": sorted({value for _number, value in bed}) or None,
        "fan_layers_1_4": [fans.get(number) for number in range(1, 5)],
        "fan_later_min_max": [min(later), max(later)] if later else None,
        "accelerations": [value for value, _count in accel.most_common(6)],
        "speed_mm_s_median_p90": {name: typical(values) for name, values in sorted(speeds.items())},
        "retraction_mm_mm_s": Counter(
            (round(length, 2), round(speed, 0)) for length, speed in retracts
        ).most_common(2),
        "z_hop_mm": Counter(round(hop, 2) for hop in hops).most_common(2),
        "layer_heights": heights.most_common(3),
        "layers": layer,
    }


def main() -> int:
    out = Path(sys.argv[1])
    report = {}
    for item in sys.argv[2:]:
        name, _, path = item.partition("=")
        report[name] = {"measured": measure(Path(path)), "config": config_of(Path(path))}
        print(name, "fertig", flush=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
