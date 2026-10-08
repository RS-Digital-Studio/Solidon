"""Kühlung kleiner Schichten und Tempo an Überhängen, gemessen an der Druckdatei.

Aufruf: python gcode_schichtzeit.py <ausgabe.json> <name=gcode> [<name=gcode> …]

Je Schicht: Zeit aus Weg durch Vorschub (ohne Beschleunigung, also eher zu
kurz), Extrusionsweg, höchster Bauteillüfter, Bahnarten. Je Bahnart der
Median-Vorschub beim Extrudieren in mm/s. Dazu die Kühl- und Überhangschlüssel
der Konfiguration am Dateiende, soweit vorhanden.
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

TYPE = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
LAYER = re.compile(r"^;\s*(?:LAYER_CHANGE|CHANGE_LAYER|LAYER\s*:\s*-?\d+)", re.IGNORECASE)
WORD = re.compile(r"([A-Z])(-?(?:\d+\.?\d*|\.\d+))")
CONFIG = re.compile(r"^;\s*([a-z0-9_]+)\s*=\s*(.*)$")

KEYS = (
    "slow_down_layer_time",
    "slow_down_min_speed",
    "slow_down_for_layer_cooling",
    "fan_cooling_layer_time",
    "fan_max_speed",
    "fan_min_speed",
    "overhang_fan_speed",
    "overhang_fan_threshold",
    "enable_overhang_speed",
    "overhang_1_4_speed",
    "overhang_2_4_speed",
    "overhang_3_4_speed",
    "overhang_4_4_speed",
    "slowdown_below_layer_time",
    "min_print_speed",
    "fan_below_layer_time",
    "max_fan_speed",
    "min_fan_speed",
    "enable_dynamic_overhang_speeds",
    "overhang_speed_0",
    "overhang_speed_1",
    "overhang_speed_2",
    "overhang_speed_3",
    "enable_dynamic_fan_speeds",
    "cool_min_layer_time",
    "cool_min_speed",
    "cool_fan_full_layer",
    "cool_fan_speed_max",
    "cool_lift_head",
    "wall_overhang_angle",
    "wall_overhang_speed_factors",
    "wall_overhang_speed_factor",
    "layer_height",
)


def measure(path: Path) -> dict[str, object]:
    position = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}
    feed = 1500.0
    relative_e = False
    feature = "?"
    fan = 0.0
    layers: list[dict[str, object]] = []
    current: dict[str, object] = {
        "time": 0.0,
        "extruded": 0.0,
        "fan": 0.0,
        "z": 0.0,
        "types": set(),
    }
    speeds: dict[str, list[tuple[float, float]]] = defaultdict(list)
    config: dict[str, str] = {}
    with path.open(encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if line.startswith(";"):
                if LAYER.match(line):
                    if float(current["time"]) > 0.0:  # type: ignore[arg-type]
                        layers.append(current)
                    current = {
                        "time": 0.0,
                        "extruded": 0.0,
                        "fan": fan,
                        "z": position["Z"],
                        "types": set(),
                    }
                    continue
                kind = TYPE.match(line)
                if kind:
                    feature = kind.group(1)
                    continue
                entry = CONFIG.match(line)
                if entry and entry.group(1) in KEYS:
                    config[entry.group(1)] = entry.group(2)[:80]
                continue
            code = line.split(";", 1)[0].strip().upper()
            if not code:
                continue
            command = code.split()[0]
            words = {key: float(value) for key, value in WORD.findall(code[len(command) :])}
            if command == "M83":
                relative_e = True
            elif command == "M82":
                relative_e = False
            elif command == "M106":
                if "P" in words and words["P"] not in (0.0, 1.0):
                    continue
                fan = words.get("S", 255.0) / 255.0 * 100.0
                current["fan"] = max(float(current["fan"]), fan)  # type: ignore[arg-type]
            elif command == "M107":
                fan = 0.0
            elif command in ("G0", "G1", "G2", "G3"):
                if "F" in words:
                    feed = words["F"]
                target = {axis: words.get(axis, position[axis]) for axis in "XYZ"}
                length = math.dist((position["X"], position["Y"]), (target["X"], target["Y"]))
                if "Z" in words:
                    current["z"] = target["Z"]
                    length = math.hypot(length, target["Z"] - position["Z"])
                extrude = 0.0
                if "E" in words:
                    extrude = words["E"] if relative_e else words["E"] - position["E"]
                    if not relative_e:
                        position["E"] = words["E"]
                if feed > 0.0 and length > 0.0:
                    current["time"] = float(current["time"]) + length / (feed / 60.0)  # type: ignore[arg-type]
                if extrude > 0.0 and length > 0.0:
                    current["extruded"] = float(current["extruded"]) + length  # type: ignore[arg-type]
                    current["types"].add(feature)  # type: ignore[union-attr]
                    speeds[feature].append((feed / 60.0, length))
                position.update(target)
            elif command == "G92" and "E" in words:
                position["E"] = words["E"]
    if float(current["time"]) > 0.0:  # type: ignore[arg-type]
        layers.append(current)
    printed = [layer for layer in layers if float(layer["extruded"]) > 0.0]  # type: ignore[arg-type]
    shortest = sorted(printed, key=lambda layer: float(layer["time"]))[:8]  # type: ignore[arg-type]
    top = printed[-12:]
    by_type = {}
    for name, entries in speeds.items():
        total = sum(length for _speed, length in entries)
        if total < 50.0:
            continue
        ordered = sorted(entries)
        running = 0.0
        median = ordered[-1][0]
        for speed, length in ordered:
            running += length
            if running >= total / 2.0:
                median = speed
                break
        by_type[name] = {"median_mm_s": round(median, 1), "length_m": round(total / 1000.0, 1)}
    return {
        "layers": len(printed),
        "shortest": [
            {
                "z": round(float(layer["z"]), 2),
                "s": round(float(layer["time"]), 1),
                "fan": round(float(layer["fan"])),
            }  # type: ignore[arg-type]
            for layer in shortest
        ],
        "top": [
            {
                "z": round(float(layer["z"]), 2),
                "s": round(float(layer["time"]), 1),
                "fan": round(float(layer["fan"])),
            }  # type: ignore[arg-type]
            for layer in top
        ],
        "median_layer_s": round(statistics.median(float(layer["time"]) for layer in printed), 1),  # type: ignore[arg-type]
        "all": [[round(float(layer["z"]), 2), round(float(layer["time"]), 2)] for layer in printed],  # type: ignore[arg-type]
        "speeds": by_type,
        "config": config,
    }


def main() -> None:
    result = {}
    for spec in sys.argv[2:]:
        name, path = spec.split("=", 1)
        result[name] = measure(Path(path))
        entry = result[name]
        print(f"== {name}: {entry['layers']} Schichten, Median {entry['median_layer_s']} s")
        print("   kürzeste:", entry["shortest"])
        print("   oben:", entry["top"][-6:])
        print(
            "   Bahnarten:", {key: value["median_mm_s"] for key, value in entry["speeds"].items()}
        )
        print("   Konfiguration:", entry["config"])
        config = entry["config"]
        limit = next(
            (
                float(config[key])
                for key in (
                    "slow_down_layer_time",
                    "slowdown_below_layer_time",
                    "cool_min_layer_time",
                )
                if key in config
            ),
            None,
        )
        if limit is not None:
            under = [(z, s) for z, s in entry["all"] if s < limit]
            print(
                f"   unter {limit} s: {len(under)} Schichten, ab z {min((z for z, _s in under), default=None)}"
            )
    Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
