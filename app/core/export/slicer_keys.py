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
from typing import Final, Literal, NamedTuple

SlicerFlavour = Literal["prusa", "orca", "cura"]

#: In welches Profil des Slicers ein Wert gehört.
#:
#: Die Orca-Familie führt getrennte Profile und nimmt einen Wert **nur an,
#: wenn er im richtigen steht**. Eine Düsentemperatur im Prozessprofil wird
#: stillschweigend übergangen: kein Fehler, keine Warnung, gedruckt wird mit
#: dem, was zuletzt im Slicer eingestellt war. Für ``prusa`` und ``cura`` hat
#: die Angabe keine Bedeutung — beide nehmen alles in einem Satz entgegen.
#:
#: Ein Maschinenprofil schreibt Formwerk nicht: dort steht die Kinematik, und
#: was Formwerk von der Maschine berührt — der Rückzug — lässt sich über die
#: ``filament_*``-Entsprechungen setzen, ohne in das Profil hineinzureden
#: (§29). Das passt auch zur Herkunft: bei Formwerk kommt der Rückzug aus dem
#: Material, nicht aus dem Drucker.
ProfileSection = Literal["process", "filament"]


class Entry(NamedTuple):
    """Eine Zuordnung: Formwerk-Pfad, Name beim Slicer, Schreibweise, Profil."""

    path: str
    key: str
    write: Callable[[object], str]
    section: ProfileSection = "process"


#: Wie die Tabellen unten geschrieben sind: das Profil darf fehlen, dann gilt
#: ``process``. Das hält die Tabellen als das lesbar, was sie sind — Daten.
Row = (
    tuple[str, str, Callable[[object], str]]
    | tuple[str, str, Callable[[object], str], ProfileSection]
)


def _plain(value: object) -> str:
    return str(value)


def _number(value: object) -> str:
    """Ohne nachlaufende Nullen — ``0.2`` statt ``0.20000000000000001``."""
    return f"{float(value):g}"  # type: ignore[arg-type]


def _integer(value: object) -> str:
    return str(int(value))  # type: ignore[call-overload]


def _number_or_silent(value: object) -> str:
    """Wie :func:`_number`, aber Null heißt „unbekannt" und wird nicht
    geschrieben.

    Der Preis je Kilogramm steht in Formwerk auf 0, wenn ihn niemand
    eingetragen hat — der eigene Docstring sagt das so. Übergeben überschreibt
    diese Null im Filamentprofil des Herstellers einen echten Wert, und der
    Slicer rechnet den ganzen Druck als kostenlos. Eine Nicht-Aussage darf
    keine Aussage werden; das ist dieselbe Unterscheidung, die
    :func:`app.core.export.handover.profile_differences` beim ``nil`` des
    Herstellers trifft, nur auf der Schreibseite.
    """
    number = float(value)  # type: ignore[arg-type]
    return "" if abs(number) < 1e-9 else f"{number:g}"


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

PRUSA: Final[tuple[Row, ...]] = (
    ("layers.layer_height", "layer_height", _number),
    ("layers.first_layer_height", "first_layer_height", _number),
    ("layers.line_width", "extrusion_width", _number),
    ("layers.first_layer_line_width", "first_layer_extrusion_width", _number),
    ("shell.wall_count", "perimeters", _integer),
    ("shell.top_layers", "top_solid_layers", _integer),
    ("shell.bottom_layers", "bottom_solid_layers", _integer),
    ("shell.outer_wall_first", "external_perimeters_first", _flag),
    ("shell.seam_position", "seam_position", _plain),
    ("shell.wall_generator", "perimeter_generator", _plain),
    # PrusaSlicer kennt keine gesonderte „genaue Außenwand" — dort heißt die
    # Sache Kompensation der Bahnbreite und ist immer an. Kein Eintrag ist
    # hier richtiger als eine Zuordnung auf etwas Ähnliches.
    ("shell.ironing", "ironing", _flag),
    ("speed.bridge", "bridge_speed", _number),
    ("speed.acceleration", "default_acceleration", _number),
    ("speed.outer_wall_acceleration", "external_perimeter_acceleration", _number),
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
    ("retraction.avoid_crossing_walls", "avoid_crossing_perimeters", _flag),
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
    ("filament.cost_per_kg", "filament_cost", _number_or_silent),
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

ORCA: Final[tuple[Row, ...]] = (
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
    ("shell.wall_generator", "wall_generator", _plain),
    ("shell.precise_outer_wall", "precise_outer_wall", _flag),
    # Orca kennt vier Stufen des Bügelns; Formwerk entscheidet nur, **ob** —
    # wie stark und mit welchem Abstand weiß der Slicer besser.
    ("shell.ironing", "ironing_type", _mapped({"True": "top"}, "no ironing")),
    ("speed.bridge", "bridge_speed", _number),
    ("speed.acceleration", "default_acceleration", _number),
    ("speed.outer_wall_acceleration", "outer_wall_acceleration", _number),
    ("infill.density", "sparse_infill_density", _percent_suffix),
    ("infill.pattern", "sparse_infill_pattern", _mapped(_ORCA_INFILL, "grid")),
    ("infill.angle", "infill_direction", _number),
    # Temperatur und Kühlung hängen am Filament, nicht am Prozess — das ist
    # die Aufteilung des Slicers, nicht unsere Wahl.
    ("temperature.nozzle", "nozzle_temperature", _integer, "filament"),
    ("temperature.nozzle_first_layer", "nozzle_temperature_initial_layer", _integer, "filament"),
    ("temperature.bed", "hot_plate_temp", _integer, "filament"),
    ("temperature.bed_first_layer", "hot_plate_temp_initial_layer", _integer, "filament"),
    ("temperature.chamber", "chamber_temperature", _integer, "filament"),
    ("cooling.fan_speed", "fan_max_speed", _percent, "filament"),
    ("cooling.fan_speed", "fan_min_speed", _percent, "filament"),
    ("cooling.bridge_fan_speed", "overhang_fan_speed", _percent, "filament"),
    ("cooling.disable_first_layers", "close_fan_the_first_x_layers", _integer, "filament"),
    ("cooling.minimum_layer_time", "slow_down_layer_time", _integer, "filament"),
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
    # Der Rückzug steht in der Orca-Familie am Drucker, nicht am Prozess —
    # ``retraction_length`` im Prozessprofil bleibt wirkungslos. Geschrieben
    # wird deshalb die Filament-Entsprechung: sie überschreibt den Wert der
    # Maschine, ohne dass Formwerk deren Profil anfassen muss.
    # Fahrwege um die Wände herum statt quer über die Öffnung. Der Schalter
    # heißt in der Orca-Familie „Wände nicht kreuzen" und steht im Prozess,
    # nicht am Filament — er beschreibt den Weg, nicht das Material.
    ("retraction.avoid_crossing_walls", "reduce_crossing_wall", _flag),
    ("retraction.length", "filament_retraction_length", _number, "filament"),
    ("retraction.speed", "filament_retraction_speed", _number, "filament"),
    ("retraction.z_hop", "filament_z_hop", _number, "filament"),
    ("retraction.wipe", "filament_wipe", _flag, "filament"),
    ("filament.diameter", "filament_diameter", _number, "filament"),
    ("filament.density", "filament_density", _number, "filament"),
    ("filament.flow_ratio", "filament_flow_ratio", _number, "filament"),
    ("filament.colour", "filament_colour", _plain, "filament"),
    ("filament.cost_per_kg", "filament_cost", _number_or_silent, "filament"),
    ("filament.max_flow", "filament_max_volumetric_speed", _number, "filament"),
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

CURA: Final[tuple[Row, ...]] = (
    ("layers.layer_height", "layer_height", _number),
    ("layers.first_layer_height", "layer_height_0", _number),
    ("layers.line_width", "line_width", _number),
    ("layers.first_layer_line_width", "initial_layer_line_width_factor", _number),
    ("shell.wall_count", "wall_line_count", _integer),
    ("shell.top_layers", "top_layers", _integer),
    ("shell.bottom_layers", "bottom_layers", _integer),
    ("shell.outer_wall_first", "outer_inset_first", _boolean),
    ("shell.ironing", "ironing_enabled", _boolean),
    # CuraEngine hat keinen umschaltbaren Wandgenerator und keine gesonderte
    # genaue Außenwand: es rechnet ohnehin mit variabler Bahnbreite. Was es
    # nicht kennt, bekommt keinen Eintrag — eine Zuordnung auf das
    # Nächstbeste wäre eine Einstellung, die woanders landet.
    ("speed.bridge", "bridge_wall_speed", _number),
    ("speed.acceleration", "acceleration_print", _number),
    ("speed.outer_wall_acceleration", "acceleration_wall_0", _number),
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
    # CuraEngine nennt dasselbe „Combing": der Kopf kämmt innerhalb des Teils
    # statt geradeaus zu fahren. ``noskin`` hält ihn zusätzlich von der
    # Oberfläche fern, wo eine Schleifspur sichtbar bliebe.
    ("retraction.avoid_crossing_walls", "retraction_combing", _mapped({"True": "noskin"}, "off")),
    ("filament.diameter", "material_diameter", _number),
    ("filament.flow_ratio", "material_flow", _percent),
)

#: Welche Schlüssel zu welcher Haftungsart gehören. Die Slicer lesen sie als
#: unabhängige Maße, gemeint ist aber genau eine Art: wer Skirt eingestellt hat
#: und trotzdem ``raft_layers`` mitschickt, bekommt beides.
#: Wie ein Material beim Slicer heißt. Fast immer die Formwerk-Kennung in
#: Großbuchstaben — nur wo die Schreibweisen auseinandergehen, steht ein
#: Eintrag. Ein unbekannter Typ ist kein Abbruch: der Slicer nimmt ihn als
#: eigenen Namen und rechnet mit den Vorgaben seiner Familie.
FILAMENT_TYPES: Final[dict[str, str]] = {"tpu-95a": "TPU"}


def filament_type(material_id: str) -> str:
    """Der Materialbezeichner in der Schreibweise des Slicers."""
    return FILAMENT_TYPES.get(material_id, material_id.upper())


ADHESION_KEYS: Final[dict[SlicerFlavour, dict[str, tuple[str, ...]]]] = {
    "prusa": {
        "skirt": ("skirts",),
        "brim": ("brim_width",),
        "raft": ("raft_layers",),
    },
    "orca": {
        "skirt": ("skirt_loops",),
        "brim": ("brim_width",),
        "raft": ("raft_layers",),
    },
    "cura": {
        "skirt": ("skirt_line_count",),
        "brim": ("brim_width",),
        "raft": ("raft_surface_layers",),
    },
}


def _entries(rows: tuple[Row, ...]) -> tuple[Entry, ...]:
    """Aus den Rohzeilen der Tabellen die benannten Einträge."""
    return tuple(Entry(*row) for row in rows)


TABLES: Final[dict[SlicerFlavour, tuple[Entry, ...]]] = {
    "prusa": _entries(PRUSA),
    "orca": _entries(ORCA),
    "cura": _entries(CURA),
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
