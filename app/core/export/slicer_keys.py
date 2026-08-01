"""Wie eine Formwerk-Einstellung in jedem Slicer heißt (Bauplan §29).

Formwerk hält die Einstellungen an einer Stelle (:class:`PrintSettings`), die
Slicer nennen dieselbe Sache verschieden: die Wandzahl ist bei PrusaSlicer
``perimeters``, bei Orca ``wall_loops`` und bei CuraEngine
``wall_line_count``. Diese Datei ist das Wörterbuch dazwischen — Daten, keine
Logik, damit ein weiterer Slicer eine Tabelle kostet und keinen Eingriff.

Drei Familien decken die verbreiteten Programme ab:

``prusa``   PrusaSlicer und SuperSlicer — ``key = value`` in einer ``.ini``
``orca``    OrcaSlicer und Bambu Studio — JSON, aus PrusaSlicer hervorgegangen
``cura``    CuraEngine — ``-s key=value`` auf der Kommandozeile

Was in einer Tabelle fehlt, bleibt beim Grundprofil des Slicers stehen. Das
ist Absicht: Formwerk überschreibt, was es versteht, und lässt den Rest in
Ruhe (§29).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, Literal

SlicerFlavour = Literal["prusa", "orca", "cura"]

#: Ein Eintrag: Punktpfad in :class:`PrintSettings`, Name beim Slicer, und wie
#: der Wert geschrieben wird.
Entry = tuple[str, str, Callable[[object], str]]


def _plain(value: object) -> str:
    return str(value)


def _number(value: object) -> str:
    """Ohne nachlaufende Nullen — ``0.2`` statt ``0.20000000000000001``."""
    return f"{float(value):g}"  # type: ignore[arg-type]


def _integer(value: object) -> str:
    return str(int(value))  # type: ignore[call-overload]


def _percent(value: object) -> str:
    """Anteil zu Prozentzahl. Formwerk rechnet in 0…1, die Slicer in 0…100."""
    return f"{float(value) * 100.0:g}"  # type: ignore[arg-type]


def _percent_suffix(value: object) -> str:
    """PrusaSlicer will die Füllung mit Prozentzeichen — ohne es gilt sie als
    absolutes Maß."""
    return f"{float(value) * 100.0:g}%"  # type: ignore[arg-type]


def _flag(value: object) -> str:
    return "1" if value else "0"


def _boolean(value: object) -> str:
    """Nur für CuraEngine. Prusa und Orca schreiben ``0``/``1`` — siehe
    :func:`_flag`, und die Verwechslung ist geräuschlos: ein ``true`` im
    falschen Profil schaltet nichts ein und meldet auch nichts."""
    return "true" if value else "false"


def _mapped(table: dict[str, str], fallback: str = "") -> Callable[[object], str]:
    """Für Aufzählungen, deren Namen auseinandergehen."""

    def convert(value: object) -> str:
        return table.get(str(value), fallback or str(value))

    return convert


def _support_on(value: object) -> str:
    return "0" if str(value) == "none" else "1"


def _support_on_boolean(value: object) -> str:
    """Dasselbe für CuraEngine — vergleiche :func:`_support_on`."""
    return "false" if str(value) == "none" else "true"


# --- PrusaSlicer und SuperSlicer ------------------------------------------------

_PRUSA_INFILL: Final = {
    "grid": "grid",
    "gyroid": "gyroid",
    "honeycomb": "honeycomb",
    "cubic": "cubic",
    "lines": "rectilinear",
    "triangles": "triangles",
}

_PRUSA_SUPPORT_STYLE: Final = {"grid": "grid", "tree": "organic", "none": "grid"}

PRUSA: Final[tuple[Entry, ...]] = (
    ("layers.layer_height", "layer_height", _number),
    ("layers.first_layer_height", "first_layer_height", _number),
    ("layers.line_width", "extrusion_width", _number),
    ("layers.first_layer_line_width", "first_layer_extrusion_width", _number),
    ("shell.wall_count", "perimeters", _integer),
    ("shell.top_layers", "top_solid_layers", _integer),
    ("shell.bottom_layers", "bottom_solid_layers", _integer),
    ("shell.outer_wall_first", "external_perimeters_first", _flag),
    ("shell.seam_position", "seam_position", _plain),
    ("infill.density", "fill_density", _percent_suffix),
    ("infill.pattern", "fill_pattern", _mapped(_PRUSA_INFILL, "grid")),
    ("infill.angle", "fill_angle", _number),
    ("temperature.nozzle", "temperature", _integer),
    ("temperature.nozzle_first_layer", "first_layer_temperature", _integer),
    ("temperature.bed", "bed_temperature", _integer),
    ("temperature.bed_first_layer", "first_layer_bed_temperature", _integer),
    ("temperature.chamber", "chamber_temperature", _integer),
    ("cooling.fan_speed", "max_fan_speed", _percent),
    ("cooling.fan_speed", "min_fan_speed", _percent),
    ("cooling.bridge_fan_speed", "bridge_fan_speed", _percent),
    ("cooling.disable_first_layers", "disable_fan_first_layers", _integer),
    ("cooling.minimum_layer_time", "slowdown_below_layer_time", _integer),
    ("speed.outer_wall", "external_perimeter_speed", _number),
    ("speed.inner_wall", "perimeter_speed", _number),
    ("speed.infill", "infill_speed", _number),
    ("speed.top_surface", "top_solid_infill_speed", _number),
    ("speed.first_layer", "first_layer_speed", _number),
    ("speed.travel", "travel_speed", _number),
    ("support.style", "support_material", _support_on),
    ("support.style", "support_material_style", _mapped(_PRUSA_SUPPORT_STYLE, "grid")),
    ("support.threshold_angle", "support_material_threshold", _integer),
    ("support.z_gap", "support_material_contact_distance", _number),
    ("support.xy_gap", "support_material_xy_spacing", _number),
    ("support.interface_layers", "support_material_interface_layers", _integer),
    ("adhesion.skirt_loops", "skirts", _integer),
    ("adhesion.skirt_distance", "skirt_distance", _number),
    ("adhesion.brim_width", "brim_width", _number),
    ("adhesion.raft_layers", "raft_layers", _integer),
    ("retraction.length", "retract_length", _number),
    ("retraction.speed", "retract_speed", _number),
    ("retraction.z_hop", "retract_lift", _number),
    ("retraction.wipe", "wipe", _flag),
    ("filament.diameter", "filament_diameter", _number),
    ("filament.density", "filament_density", _number),
    ("filament.flow_ratio", "extrusion_multiplier", _number),
    ("filament.colour", "filament_colour", _plain),
    ("filament.cost_per_kg", "filament_cost", _number),
    ("filament.max_flow", "filament_max_volumetric_speed", _number),
)

# --- OrcaSlicer und Bambu Studio ------------------------------------------------

#: Orca benennt zwei Muster anders als sein Vorfahre: es gibt dort weder
#: ``line`` noch ``honeycomb``. Ein unbekannter Name fällt still auf die
#: Vorgabe zurück — die Füllung wäre dann eine andere als die eingestellte.
#: Abgelesen am ausgelieferten Profilbestand, nicht aus der Erinnerung.
_ORCA_INFILL: Final = {
    "grid": "grid",
    "gyroid": "gyroid",
    "honeycomb": "3dhoneycomb",
    "cubic": "cubic",
    "lines": "rectilinear",
    "triangles": "triangles",
}

_ORCA_SUPPORT_TYPE: Final = {
    "grid": "normal(auto)",
    "tree": "tree(auto)",
    "none": "normal(auto)",
}

_ORCA_SEAM: Final = {
    "aligned": "aligned",
    "nearest": "nearest",
    "random": "random",
    "rear": "back",
}

ORCA: Final[tuple[Entry, ...]] = (
    ("layers.layer_height", "layer_height", _number),
    ("layers.first_layer_height", "initial_layer_print_height", _number),
    ("layers.line_width", "line_width", _number),
    ("layers.first_layer_line_width", "initial_layer_line_width", _number),
    ("shell.wall_count", "wall_loops", _integer),
    ("shell.top_layers", "top_shell_layers", _integer),
    ("shell.bottom_layers", "bottom_shell_layers", _integer),
    (
        "shell.outer_wall_first",
        "wall_sequence",
        _mapped({"True": "outer wall/inner wall"}, "inner wall/outer wall"),
    ),
    ("shell.seam_position", "seam_position", _mapped(_ORCA_SEAM, "aligned")),
    ("infill.density", "sparse_infill_density", _percent_suffix),
    ("infill.pattern", "sparse_infill_pattern", _mapped(_ORCA_INFILL, "grid")),
    ("infill.angle", "infill_direction", _number),
    ("temperature.nozzle", "nozzle_temperature", _integer),
    ("temperature.nozzle_first_layer", "nozzle_temperature_initial_layer", _integer),
    ("temperature.bed", "hot_plate_temp", _integer),
    ("temperature.bed_first_layer", "hot_plate_temp_initial_layer", _integer),
    ("temperature.chamber", "chamber_temperature", _integer),
    ("cooling.fan_speed", "fan_max_speed", _percent),
    ("cooling.fan_speed", "fan_min_speed", _percent),
    ("cooling.bridge_fan_speed", "overhang_fan_speed", _percent),
    ("cooling.disable_first_layers", "close_fan_the_first_x_layers", _integer),
    ("cooling.minimum_layer_time", "slow_down_layer_time", _integer),
    ("speed.outer_wall", "outer_wall_speed", _number),
    ("speed.inner_wall", "inner_wall_speed", _number),
    ("speed.infill", "sparse_infill_speed", _number),
    ("speed.top_surface", "top_surface_speed", _number),
    ("speed.first_layer", "initial_layer_speed", _number),
    ("speed.travel", "travel_speed", _number),
    # Orca hat PrusaSlicer als Vorfahren und schreibt Wahrheitswerte wie es:
    # "0" und "1", nicht "true" und "false". Ein "true" hier bleibt still
    # wirkungslos — der Slicer meldet nichts, er stützt bloß nicht.
    ("support.style", "enable_support", _support_on),
    ("support.style", "support_type", _mapped(_ORCA_SUPPORT_TYPE, "normal(auto)")),
    ("support.placement", "support_on_build_plate_only", _mapped({"build_plate": "1"}, "0")),
    ("support.threshold_angle", "support_threshold_angle", _integer),
    ("support.z_gap", "support_top_z_distance", _number),
    ("support.xy_gap", "support_object_xy_distance", _number),
    ("support.interface_layers", "support_interface_top_layers", _integer),
    ("adhesion.kind", "brim_type", _mapped({"brim": "outer_only"}, "no_brim")),
    ("adhesion.skirt_loops", "skirt_loops", _integer),
    ("adhesion.skirt_distance", "skirt_distance", _number),
    ("adhesion.brim_width", "brim_width", _number),
    ("adhesion.raft_layers", "raft_layers", _integer),
    ("retraction.length", "retraction_length", _number),
    ("retraction.speed", "retraction_speed", _number),
    ("retraction.z_hop", "z_hop", _number),
    ("retraction.wipe", "wipe", _flag),
    ("filament.diameter", "filament_diameter", _number),
    ("filament.density", "filament_density", _number),
    ("filament.flow_ratio", "filament_flow_ratio", _number),
    ("filament.colour", "filament_colour", _plain),
    ("filament.cost_per_kg", "filament_cost", _number),
    ("filament.max_flow", "filament_max_volumetric_speed", _number),
)

# --- CuraEngine -----------------------------------------------------------------

_CURA_INFILL: Final = {
    "grid": "grid",
    "gyroid": "gyroid",
    "honeycomb": "trihexagon",
    "cubic": "cubic",
    "lines": "lines",
    "triangles": "triangles",
}

CURA: Final[tuple[Entry, ...]] = (
    ("layers.layer_height", "layer_height", _number),
    ("layers.first_layer_height", "layer_height_0", _number),
    ("layers.line_width", "line_width", _number),
    ("layers.first_layer_line_width", "initial_layer_line_width_factor", _number),
    ("shell.wall_count", "wall_line_count", _integer),
    ("shell.top_layers", "top_layers", _integer),
    ("shell.bottom_layers", "bottom_layers", _integer),
    ("shell.outer_wall_first", "outer_inset_first", _boolean),
    ("infill.density", "infill_sparse_density", _percent),
    ("infill.pattern", "infill_pattern", _mapped(_CURA_INFILL, "grid")),
    ("infill.angle", "infill_angles", _number),
    ("temperature.nozzle", "material_print_temperature", _integer),
    ("temperature.nozzle_first_layer", "material_print_temperature_layer_0", _integer),
    ("temperature.bed", "material_bed_temperature", _integer),
    ("temperature.bed_first_layer", "material_bed_temperature_layer_0", _integer),
    ("cooling.fan_speed", "cool_fan_speed", _percent),
    ("cooling.disable_first_layers", "cool_fan_full_layer", _integer),
    ("cooling.minimum_layer_time", "cool_min_layer_time", _integer),
    ("speed.outer_wall", "speed_wall_0", _number),
    ("speed.inner_wall", "speed_wall_x", _number),
    ("speed.infill", "speed_infill", _number),
    ("speed.top_surface", "speed_topbottom", _number),
    ("speed.first_layer", "speed_layer_0", _number),
    ("speed.travel", "speed_travel", _number),
    ("support.style", "support_enable", _support_on_boolean),
    ("support.placement", "support_type", _mapped({"build_plate": "buildplate"}, "everywhere")),
    ("support.threshold_angle", "support_angle", _integer),
    ("support.z_gap", "support_z_distance", _number),
    ("support.xy_gap", "support_xy_distance", _number),
    ("support.density", "support_infill_rate", _percent),
    ("support.interface_layers", "support_interface_height", _integer),
    ("adhesion.kind", "adhesion_type", _mapped({"none": "none"}, "")),
    ("adhesion.skirt_loops", "skirt_line_count", _integer),
    ("adhesion.skirt_distance", "skirt_gap", _number),
    ("adhesion.brim_width", "brim_width", _number),
    ("adhesion.raft_layers", "raft_surface_layers", _integer),
    ("retraction.length", "retraction_amount", _number),
    ("retraction.speed", "retraction_speed", _number),
    ("retraction.z_hop", "retraction_hop", _number),
    ("filament.diameter", "material_diameter", _number),
    ("filament.flow_ratio", "material_flow", _percent),
)

TABLES: Final[dict[SlicerFlavour, tuple[Entry, ...]]] = {
    "prusa": PRUSA,
    "orca": ORCA,
    "cura": CURA,
}

#: Woran der Dateiname verrät, welche Familie da liegt. Die längeren Namen
#: zuerst, damit ``bambu-studio`` nicht an ``studio`` hängen bleibt.
FLAVOUR_BY_NAME: Final[tuple[tuple[str, SlicerFlavour], ...]] = (
    ("prusa-slicer-console", "prusa"),
    ("prusaslicer", "prusa"),
    ("prusa-slicer", "prusa"),
    ("superslicer", "prusa"),
    ("orcaslicer", "orca"),
    ("orca-slicer", "orca"),
    ("bambustudio", "orca"),
    ("bambu-studio", "orca"),
    ("elegooslicer", "orca"),
    ("elegoo-slicer", "orca"),
    ("curaengine", "cura"),
    ("cura", "cura"),
)


def flavour_of(name: str) -> SlicerFlavour | None:
    """Welche Familie ein Programm dieses Namens ist, oder ``None``.

    Über den Dateinamen und nicht über einen Versionsaufruf: die Erkennung
    läuft auch, wenn das Programm gerade nicht startbar ist, und ein
    umbenanntes Programm ist ein Fall für die Einstellungen, nicht für eine
    Rateroutine.
    """
    lowered = name.casefold()
    for fragment, flavour in FLAVOUR_BY_NAME:
        if fragment in lowered:
            return flavour
    return None
