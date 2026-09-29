"""Was eine Druckdatei tatsächlich tut — für alle drei Slicerfamilien.

Kein Teil der Anwendung: ein Prüfwerkzeug für den Lauf „jedes Modell × jeder
Slicer“ (Robert, 27.09.2026). Die Marken sind dieselben, die Solidons eigener
Leser kennt (``app/core/slice/gcode.py``): Schichten über ``;LAYER:n``,
``;LAYER_CHANGE`` oder ``; CHANGE_LAYER`` (die Orca-Familie schreibt mit
manchen Druckern zwei Marken je Schicht — eine Schicht beginnt deshalb erst
mit der ersten Bahn nach einer Marke), Bahnarten über ``;TYPE:`` oder
``; FEATURE:``.

Gemessen wird:

* **vor der ersten Schicht** (der Startcode der Maschine): Bettvermessung,
  Referenzfahrt, Spüllinie (Extrusion vor der ersten Schichtmarke), die
  Temperaturbefehle;
* **je Schicht der ersten drei**: Bahnlänge je Art, zusammenhängende Bahnzüge
  je Art (eine Folge von Extrusionen derselben Art ohne Leerfahrt dazwischen —
  ein zerrissener Brim hat viele, ein ganzer wenige), Leerfahrten und ihre
  Länge;
* **über die ganze Datei**: Bahnlänge je Art (Modell, Stütze, Rand getrennt),
  Stütze in der ersten Schicht, Extrusion außerhalb des Betts (ohne Startcode),
  Schichtzahl, Zeit und Material aus dem Kopf, die gesetzten Temperaturen.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

LAYER_MARK = re.compile(r"^;\s*(?:LAYER\s*:\s*-?[0-9]+|LAYER_CHANGE|CHANGE_LAYER)\s*$", re.IGNORECASE)
TYPE_MARK = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(?P<type>.+?)\s*$", re.IGNORECASE)
WORD = re.compile(r"(?P<name>[A-Z])(?P<value>[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))", re.IGNORECASE)
SETTING = re.compile(r"^;\s*(?P<key>[a-z_0-9 \[\]()]+?)\s*[=:]\s*(?P<value>.*?)\s*$", re.IGNORECASE)

#: Bettvermessung und Netzladen, wie die Firmwares sie nennen.
LEVELLING = (
    re.compile(r"^G29\b", re.IGNORECASE),
    re.compile(r"^M420\s+S1\b", re.IGNORECASE),
    re.compile(r"^BED_MESH_CALIBRATE\b", re.IGNORECASE),
    re.compile(r"^BED_MESH_PROFILE\s+LOAD\b", re.IGNORECASE),
    re.compile(r"^M622\s+J1\b", re.IGNORECASE),  # Bambu: Bedingte Vermessung
    re.compile(r"^G29\.[0-9]\b", re.IGNORECASE),
)


def kind_of(raw: str) -> str:
    """Welche Rolle eine Bahnart spielt: Modell, Stütze, Rand, sonst."""
    lowered = raw.casefold()
    if "support" in lowered:
        return "support"
    if lowered in ("skirt", "brim", "skirt/brim") or "skirt" in lowered or lowered.startswith("brim"):
        return "rim"
    if lowered in ("custom", "wipe", "prime tower", "wipe tower") or "prime" in lowered or "purge" in lowered:
        return "other"
    return "model"


@dataclass
class Layer:
    z: float | None = None
    paths: dict[str, float] = field(default_factory=dict)
    runs: dict[str, int] = field(default_factory=dict)
    travels: int = 0
    travel_length: float = 0.0
    long_travels: int = 0


@dataclass
class Reading:
    header: dict[str, str] = field(default_factory=dict)
    start_levelling: list[str] = field(default_factory=list)
    start_homing: int = 0
    start_extrusion: float = 0.0
    temperatures: list[str] = field(default_factory=list)
    layers_first: list[Layer] = field(default_factory=list)
    total: dict[str, float] = field(default_factory=dict)
    layer_count: int = 0
    first_layer_support: float = 0.0
    off_bed: dict[str, int] = field(default_factory=dict)

    def summary(self) -> dict:
        support = sum(v for k, v in self.total.items() if kind_of(k) == "support")
        rim = sum(v for k, v in self.total.items() if kind_of(k) == "rim")
        model = sum(v for k, v in self.total.items() if kind_of(k) == "model")
        first = self.layers_first[0] if self.layers_first else Layer()
        return {
            "layers": self.layer_count,
            "model_m": round(model / 1000.0, 2),
            "support_m": round(support / 1000.0, 2),
            "rim_m": round(rim / 1000.0, 2),
            "paths_m": {k: round(v / 1000.0, 2) for k, v in sorted(self.total.items(), key=lambda t: -t[1])},
            "first_layer_support_m": round(self.first_layer_support / 1000.0, 2),
            "first_layer_support_share": round(
                self.first_layer_support / max(sum(first.paths.values()), 1e-9), 3
            ),
            "start_levelling": self.start_levelling,
            "start_homing": self.start_homing,
            "start_purge_mm": round(self.start_extrusion, 1),
            "temperatures": self.temperatures[:12],
            "off_bed": self.off_bed,
            "first_layers": [
                {
                    "z": layer.z,
                    "paths_mm": {k: round(v) for k, v in sorted(layer.paths.items(), key=lambda t: -t[1])},
                    "runs": dict(sorted(layer.runs.items())),
                    "travels": layer.travels,
                    "long_travels": layer.long_travels,
                    "travel_m": round(layer.travel_length / 1000.0, 2),
                }
                for layer in self.layers_first
            ],
            "header": self.header,
        }


HEADER_KEYS = (
    "estimated printing time (normal mode)",
    "estimated printing time",
    "model printing time",
    "total estimated time",
    "filament used [g]",
    "total filament used [g]",
    "filament used [mm]",
    "filament used [cm3]",
    "total layers count",
    "enable_support",
    "support_type",
    "support_material",
    "support_material_auto",
    "support_threshold_angle",
    "support_material_threshold",
    "brim_type",
    "brim_width",
    "skirt_loops",
    "skirts",
    "wall_loops",
    "perimeters",
    "sparse_infill_density",
    "fill_density",
    "layer_height",
    "initial_layer_print_height",
    "first_layer_height",
    "nozzle_temperature",
    "nozzle_temperature_initial_layer",
    "temperature",
    "first_layer_temperature",
    "curr_bed_type",
    "printer_settings_id",
    "print_settings_id",
    "filament_settings_id",
    "gcode_flavor",
    "printer_model",
)


def read(path: Path, *, bed: tuple[float, float] | None = None, keep_layers: int = 3) -> Reading:
    reading = Reading()
    kind = "?"
    x = y = 0.0
    absolute = True
    last_e = 0.0
    started = False  # nach der ersten Schichtmarke
    pending_layer = False  # Marke gesehen, erste Bahn der Schicht steht aus
    layer_index = -1
    current: Layer | None = None
    run_kind: str | None = None  # Art des laufenden Bahnzugs
    pending_z: float | None = None  # ``;Z:`` steht vor der ersten Bahn der Schicht
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(";"):
                if LAYER_MARK.match(stripped):
                    if not started:
                        started = True
                    pending_layer = True
                    continue
                typed = TYPE_MARK.match(stripped)
                if typed:
                    kind = typed.group("type")
                    run_kind = None
                    continue
                if stripped.startswith((";Z:", "; Z_HEIGHT:")) and pending_layer:
                    try:
                        pending_z = float(stripped.split(":", 1)[1])
                    except ValueError:
                        pass
                    continue
                setting = SETTING.match(stripped)
                if setting and setting.group("key").strip() in HEADER_KEYS:
                    reading.header.setdefault(setting.group("key").strip(), setting.group("value")[:160])
                continue
            code = stripped.split(";", 1)[0].strip()
            upper = code.upper()
            if not started:
                if any(pattern.match(upper) for pattern in LEVELLING):
                    reading.start_levelling.append(upper[:40])
                if upper.startswith("G28"):
                    reading.start_homing += 1
            if upper.startswith(("M104", "M109", "M140", "M190", "M141", "M191")):
                reading.temperatures.append(upper[:30])
            if upper.startswith("M83"):
                absolute = False
                continue
            if upper.startswith("M82"):
                absolute = True
                continue
            if upper.startswith("G92"):
                found = dict((m.group("name").upper(), m.group("value")) for m in WORD.finditer(code[3:]))
                if "E" in found:
                    last_e = float(found["E"])
                continue
            if not upper.startswith(("G0", "G1", "G2", "G3")) or upper.startswith(("G10", "G11", "G28", "G29")):
                continue
            words = dict((m.group("name").upper(), float(m.group("value"))) for m in WORD.finditer(code[2:]))
            nx, ny = words.get("X", x), words.get("Y", y)
            pushed = 0.0
            if "E" in words:
                e = words["E"]
                pushed = (e - last_e) if absolute else e
                if absolute:
                    last_e = e
            moved = nx != x or ny != y
            length = math.hypot(nx - x, ny - y) if moved else 0.0
            if not started:
                if pushed > 0:
                    reading.start_extrusion += pushed
                x, y = nx, ny
                continue
            if pending_layer and moved:
                pending_layer = False
                layer_index += 1
                reading.layer_count = layer_index + 1
                current = Layer(z=pending_z) if layer_index < keep_layers else None
                pending_z = None
                if current is not None:
                    reading.layers_first.append(current)
                run_kind = None
            if moved and pushed > 0:
                reading.total[kind] = reading.total.get(kind, 0.0) + length
                if layer_index == 0 and kind_of(kind) == "support":
                    reading.first_layer_support += length
                if bed is not None and kind_of(kind) != "other":
                    if not (-0.5 <= nx <= bed[0] + 0.5 and -0.5 <= ny <= bed[1] + 0.5):
                        reading.off_bed[kind] = reading.off_bed.get(kind, 0) + 1
                if current is not None:
                    current.paths[kind] = current.paths.get(kind, 0.0) + length
                    if run_kind != kind:
                        current.runs[kind] = current.runs.get(kind, 0) + 1
                        run_kind = kind
            elif moved:
                run_kind = None
                if current is not None:
                    current.travels += 1
                    current.travel_length += length
                    if length > 2.0:
                        current.long_travels += 1
            x, y = nx, ny
    return reading


def config_block(path: Path) -> dict[str, str]:
    """Der Konfigurationsblock einer Druckdatei — jeder Schlüssel, mit dem sie
    gerechnet wurde. Orca-Familie zwischen ``CONFIG_BLOCK_START`` und
    ``CONFIG_BLOCK_END``, PrusaSlicer zwischen ``prusaslicer_config = begin``
    und ``end``; CuraEngine schreibt keinen."""
    found: dict[str, str] = {}
    inside = False
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped in ("; CONFIG_BLOCK_START", "; prusaslicer_config = begin"):
                inside = True
                continue
            if stripped in ("; CONFIG_BLOCK_END", "; prusaslicer_config = end"):
                inside = False
                continue
            if inside and stripped.startswith("; ") and " = " in stripped:
                key, _sep, value = stripped[2:].partition(" = ")
                found[key.strip()] = value.strip()
    return found


#: Was eine Übergabe von Solidon ausweisen darf, auch wenn sie nichts ändern
#: soll: Namen, Objektmarken, Bindung an die Maschine, Zeitstempel.
TECHNICAL = frozenset(
    {
        "print_settings_id", "printer_settings_id", "filament_settings_id", "inherits",
        "inherits_group", "compatible_printers", "compatible_printers_condition",
        "compatible_prints", "compatible_prints_condition", "gcode_label_objects",
        "filament_colour", "filament_multi_colour", "filament_colour_type", "print_compatible_printers",
        "different_settings_to_system", "print_settings_id", "filament_ids", "filament_vendor",
        "extruder_colour", "default_filament_colour", "filament_type", "filament_is_support",
        "filament_shrink", "setting_id", "filament_id", "wipe_tower_x", "wipe_tower_y",
        "filament_self_index",
    }
)


def config_difference(reference: dict[str, str], run: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Schlüssel, in denen ``run`` vom Herstellerlauf abweicht, ohne die technischen."""
    keys = (set(reference) | set(run)) - TECHNICAL
    # Die Spülmatrix zählt erst ab zwei Filamenten. Mit einem rechnet der
    # Konsolenlauf „0", die Projektdatei ohne Matrix trägt Orcas 4×4-Vorgabe —
    # ein Unterschied des Ladewegs, kein Werkzeugwechsel.
    if all(len(block.get("filament_settings_id", "").split(";")) <= 1 for block in (reference, run)):
        keys.discard("flush_volumes_matrix")
    return {
        key: (reference.get(key, "—"), run.get(key, "—"))
        for key in sorted(keys)
        if reference.get(key) != run.get(key)
    }
