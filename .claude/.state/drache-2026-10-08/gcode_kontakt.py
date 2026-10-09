"""Wo die Stütze das Modell berührt: Abstand und Trennschichten, gemessen im G-Code (RM-583).

Aufruf: python gcode_kontakt.py <aus.json> <name=gcode[@x0,x1,y0,y1]> …

Je Druckdatei ein Raster von 0,5 mm in der Aufsicht, wahlweise nur im Bereich
``@x0,x1,y0,y1`` (ein Körper einer Platte mit zweien). Je Zelle die Schichten
mit Modellbahn, Stützbahn und Trennschicht. Oben: eine Schicht nur mit Modell
über einer Schicht nur mit Stütze — Abstand = Unterkante der Modellschicht minus
Oberkante der Stützschicht, dazu die Trennschichten direkt darunter. Unten: eine
Schicht nur mit Stütze über einer nur mit Modell. Als Kontakt zählt höchstens
:data:`CONTACT` Luft; mehr ist Stütze neben dem Modell, nicht darunter.
Gemeldet werden Mediane, Anzahl der Kontaktzellen und die Konfigurationswerte,
die das Programm in die Datei schrieb (Orca-Familie und PrusaSlicer als
Kommentarblock, Cura im ``;SETTING_3``-Block).
"""

from __future__ import annotations

import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

CELL = 0.5
CONTACT = 1.0
INTERFACE = ("support interface", "support material interface", "support-interface")
SUPPORT = ("support", "support material")
SKIPPED = ("skirt", "brim", "custom", "prime tower", "wipe tower")
KEYS = (
    "layer_height",
    "support_top_z_distance",
    "support_bottom_z_distance",
    "support_interface_top_layers",
    "support_interface_bottom_layers",
    "support_interface_spacing",
    "support_material_interface_fan_speed",
    "independent_support_layer_height",
    "support_material_contact_distance",
    "support_material_bottom_contact_distance",
    "support_material_interface_layers",
    "support_material_bottom_interface_layers",
    "support_material_interface_spacing",
    "support_z_distance",
    "support_top_distance",
    "support_bottom_distance",
    "support_roof_height",
    "support_bottom_height",
    "support_bottom_enable",
    "support_roof_line_distance",
    "support_fan_enable",
    "support_supported_skin_fan_speed",
)
MOVE = re.compile(r"^G[01]\b")
#: Bambu Studio schreibt ``; FEATURE:``, die übrigen ``;TYPE:``.
TYPED = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$")
#: PrusaSlicer schreibt Koordinaten ohne führende Null („Z.2“).
NUMBER = re.compile(r"([XYZEF])(-?\d*\.?\d+)")


def kind_of(name: str) -> str | None:
    lowered = name.strip().lower()
    if lowered in INTERFACE:
        return "interface"
    if lowered in SUPPORT:
        return "support"
    if lowered in SKIPPED:
        return None
    return "model"


def cura_settings(chunks: list[str]) -> dict[str, str]:
    """Die Werte aus Curas ``;SETTING_3``-Block, je Schlüssel der letzte."""
    found: dict[str, str] = {}
    try:
        block = json.loads("".join(chunks))
    except json.JSONDecodeError:
        return found
    texts = [block.get("global_quality", "")] + list(block.get("extruder_quality", []))
    for text in texts:
        for line in str(text).split("\n"):
            key, _, value = line.partition(" = ")
            if key.strip() in KEYS:
                found[key.strip()] = value.strip()
    return found


def _heights(levels: set[float]) -> dict[float, float]:
    ordered = sorted(levels)
    return {
        level: round(level - (ordered[index - 1] if index else 0.0), 3)
        for index, level in enumerate(ordered)
    }


def measure(path: Path, area: tuple[float, float, float, float] | None) -> dict[str, object]:
    cells: dict[tuple[int, int], dict[float, set[str]]] = defaultdict(lambda: defaultdict(set))
    x = y = z = e = 0.0
    kind: str | None = None
    relative_e = False
    config: dict[str, str] = {}
    cura: list[str] = []
    interface_length: dict[float, float] = defaultdict(float)
    printed: dict[str, set[float]] = defaultdict(set)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            typed = TYPED.match(line)
            if typed:
                kind = kind_of(typed.group(1))
                continue
            if line.startswith(";SETTING_3 "):
                cura.append(line[len(";SETTING_3 ") :].rstrip("\r\n"))
                continue
            if line.startswith("; ") and " = " in line:
                key, _, value = line[2:].partition(" = ")
                if key in KEYS:
                    config[key] = value.strip()
                continue
            if line.startswith("M83"):
                relative_e = True
            elif line.startswith("M82"):
                relative_e = False
            if not MOVE.match(line):
                continue
            values = {key: float(number) for key, number in NUMBER.findall(line.split(";")[0])}
            new_x, new_y = values.get("X", x), values.get("Y", y)
            if "Z" in values:
                z = values["Z"]
            extruded = "E" in values and (values["E"] > 0.0 if relative_e else values["E"] > e)
            if "E" in values and not relative_e:
                e = values["E"]
            if extruded and kind is not None:
                level = round(z, 3)
                printed[kind].add(level)
                middle_x, middle_y = (x + new_x) / 2.0, (y + new_y) / 2.0
                if kind == "interface" and (new_x, new_y) != (x, y) and (
                    area is None
                    or (area[0] <= middle_x <= area[1] and area[2] <= middle_y <= area[3])
                ):
                    interface_length[level] += math.hypot(new_x - x, new_y - y)
                length = max(abs(new_x - x), abs(new_y - y))
                steps = max(1, int(length / CELL))
                for step in range(steps + 1):
                    px = x + (new_x - x) * step / steps
                    py = y + (new_y - y) * step / steps
                    if area is not None and not (
                        area[0] <= px <= area[1] and area[2] <= py <= area[3]
                    ):
                        continue
                    cells[(int(px // CELL), int(py // CELL))][level].add(kind)
            x, y = new_x, new_y
    config.update(cura_settings(cura))
    # Die Schichthöhe aus den Druckebenen derselben Art, nicht aus der letzten
    # Z-Bewegung: Ein Z-Hop davor hätte sie negativ gemacht.
    model_height = _heights(printed["model"])
    support_height = _heights(printed["support"] | printed["interface"])

    top_gaps: list[float] = []
    top_layers: list[int] = []
    bottom_gaps: list[float] = []
    bottom_layers: list[int] = []
    carried = {"support", "interface"}
    for column in cells.values():
        levels = sorted(column)
        for index in range(1, len(levels)):
            here, below = column[levels[index]], column[levels[index - 1]]
            top_gap = round(levels[index] - model_height.get(levels[index], 0.2) - levels[index - 1], 3)
            bottom_gap = round(
                levels[index] - support_height.get(levels[index], 0.2) - levels[index - 1], 3
            )
            # Oben: die oberste Trennschicht, über der das Modell beginnt — ohne
            # Trennschicht darunter ist es ein Ast neben einer schrägen Wand.
            if (
                "model" in here
                and not here & carried
                and "interface" in below
                and top_gap <= CONTACT
            ):
                top_gaps.append(top_gap)
                count = 0
                for lower in reversed(levels[:index]):
                    if "interface" in column[lower]:
                        count += 1
                    else:
                        break
                top_layers.append(count)
            # Unten: die unterste Stützschicht, die auf dem Modell steht.
            if here & carried and "model" in below and not below & carried and bottom_gap <= CONTACT:
                bottom_gaps.append(bottom_gap)
                count = 0
                for upper in levels[index:]:
                    if "interface" in column[upper]:
                        count += 1
                    else:
                        break
                bottom_layers.append(count)

    def median(values: list[float] | list[int]) -> float | None:
        return round(statistics.median(values), 3) if values else None

    def spread(values: list[float]) -> dict[str, int]:
        counted: dict[str, int] = {}
        for value in values:
            counted[f"{value:.2f}"] = counted.get(f"{value:.2f}", 0) + 1
        return dict(sorted(counted.items()))

    return {
        "config": config,
        "top_spread": spread(top_gaps),
        "bottom_spread": spread(bottom_gaps),
        "top_cells": len(top_gaps),
        "top_gap": median(top_gaps),
        "top_interface_layers": median(top_layers),
        "bottom_cells": len(bottom_gaps),
        "bottom_gap": median(bottom_gaps),
        "bottom_interface_layers": median(bottom_layers),
        "interface_levels": len(interface_length),
        "interface_mm_per_level": median(list(interface_length.values())),
    }


def main() -> None:
    out = Path(sys.argv[1])
    report = {}
    for argument in sys.argv[2:]:
        name, _, rest = argument.partition("=")
        gcode, _, box = rest.partition("@")
        area = tuple(float(value) for value in box.split(",")) if box else None
        report[name] = measure(Path(gcode), area)  # type: ignore[arg-type]
        print(name, json.dumps(report[name], ensure_ascii=False), flush=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
