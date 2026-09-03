"""Wie eine Solidon-Einstellung in jedem Slicer heißt (Bauplan §29).

Solidon hält die Einstellungen an einer Stelle (:class:`PrintSettings`), die
Slicer nennen dieselbe Sache verschieden: die Wandzahl ist bei PrusaSlicer
``perimeters``, bei Orca ``wall_loops`` und bei CuraEngine
``wall_line_count``. Diese Datei ist das Wörterbuch dazwischen — Daten, keine
Logik, damit ein weiterer Slicer eine Tabelle kostet und keinen Eingriff.

Drei Familien decken die verbreiteten Programme ab:

``prusa``   PrusaSlicer und SuperSlicer — ``key = value`` in einer ``.ini``
``orca``    OrcaSlicer und Bambu Studio — JSON, aus PrusaSlicer hervorgegangen
``cura``    CuraEngine — ``-s key=value`` auf der Kommandozeile

Was in einer Tabelle fehlt, bleibt beim Grundprofil des Slicers stehen. Das
ist Absicht: Solidon überschreibt, was es versteht, und lässt den Rest in
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
#: Ein Maschinenprofil schreibt Solidon nicht: dort steht die Kinematik, und
#: was Solidon von der Maschine berührt — der Rückzug — lässt sich über die
#: ``filament_*``-Entsprechungen setzen, ohne in das Profil hineinzureden
#: (§29). Das passt auch zur Herkunft: bei Solidon kommt der Rückzug aus dem
#: Material, nicht aus dem Drucker.
ProfileSection = Literal["process", "filament"]


class Entry(NamedTuple):
    """Eine Zuordnung: Solidon-Pfad, Name beim Slicer, Schreibweise, Profil."""

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

    Der Preis je Kilogramm steht in Solidon auf 0, wenn ihn niemand
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
    """Anteil zu Prozentzahl. Solidon rechnet in 0…1, die Slicer in 0…100."""
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


def _positive_flag(value: object) -> str:
    """Der Schalter zu einem Maß, das ohne ihn nicht gilt (CuraEngine).

    ``retraction_hop`` ist dort ein Millimeterwert **und** ein Schalter, und
    der Schalter steht auf ``false``. Ein Sprung von 0,6 mm war damit
    geschrieben und wirkungslos: gemessen an zwei Läufen desselben Würfels,
    null Z-Sprünge gegen fünf.
    """
    return "true" if float(value) > 0.0 else "false"  # type: ignore[arg-type]


def _angle_from_horizontal(value: object) -> str:
    """Stützwinkel in die Zählweise von PrusaSlicer und der Orca-Familie.

    Solidon misst **gegen die Senkrechte** — 0° stützt jeden Überhang, 90°
    keinen. Das ist Curas Zählweise. Die beiden anderen messen gegen die
    **Horizontale** und drehen die Bedeutung damit um: PrusaSlicer stützt
    „overhangs whose slope angle (90° = vertical) is above the given
    threshold" nicht, Orca stützt, „whose slope angle is below the threshold".

    Gemessen an einem Keil mit 30° Neigung zur Horizontalen — also 60° zur
    Senkrechten: Prusa und Orca kippen zwischen 20 und 40, Cura zwischen 50
    und 70. Beide haben recht, sie zählen nur von der anderen Seite. Wer
    ihnen dieselbe Zahl schickt, kehrt an den Rändern die Absicht um: 20 heißt
    in Solidon „stütze fast alles" und kam bei PrusaSlicer als „stütze fast
    nichts" an.

    Die Null am Rand ist abgefangen: Solidons 90° heißen „stütze nichts", eine
    geschriebene 0 heißt bei beiden aber „such dir den Winkel selbst" —
    PrusaSlicer nennt es automatische Erkennung, Orca fällt beim Baum auf 30
    zurück. Aus der Absicht würde damit ihr Gegenteil, also steht dort eine 1:
    gestützt wird nur, was flacher als ein Grad liegt, und das ist nichts.
    """
    return str(max(round(90.0 - float(value)), 1))  # type: ignore[arg-type]


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
    ("support.placement", "support_material_buildplate_only", _mapped({"build_plate": "1"}, "0")),
    ("support.threshold_angle", "support_material_threshold", _angle_from_horizontal),
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
    # Orca kennt vier Stufen des Bügelns; Solidon entscheidet nur, **ob** —
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
    ("support.threshold_angle", "support_threshold_angle", _angle_from_horizontal),
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
    # Maschine, ohne dass Solidon deren Profil anfassen muss.
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

#: Wo CuraEngine die Naht ansetzt. Die vier Werte heißen dort ``back``
#: („User Specified", also der Punkt aus ``z_seam_x``/``z_seam_y``),
#: ``shortest``, ``random`` und ``sharpest_corner``.
#:
#: Für Solidons ``aligned`` gibt es kein genaues Gegenstück — Cura kennt keine
#: Naht, die von Schicht zu Schicht auf derselben Kante bleibt. ``sharpest_corner``
#: kommt der Absicht am nächsten: die Naht sitzt an einer Kante statt irgendwo,
#: und sie sitzt in jeder Schicht an derselben.
_CURA_SEAM: Final = {
    "aligned": "sharpest_corner",
    "nearest": "shortest",
    "random": "random",
    "rear": "back",
}

CURA: Final[tuple[Row, ...]] = (
    ("layers.layer_height", "layer_height", _number),
    ("layers.first_layer_height", "layer_height_0", _number),
    ("layers.line_width", "line_width", _number),
    ("layers.first_layer_line_width", "initial_layer_line_width_factor", _number),
    ("shell.wall_count", "wall_line_count", _integer),
    ("shell.top_layers", "top_layers", _integer),
    ("shell.bottom_layers", "bottom_layers", _integer),
    # ``inset_direction`` und nicht ``outer_inset_first``: den alten Namen
    # kennt Cura 5 nicht mehr, und ein unbekannter ``-s``-Wert wird
    # stillschweigend verworfen. Gemessen an einem Würfel: null von fünfzig
    # Lagen begannen außen, mit dem richtigen Namen neunundvierzig.
    ("shell.outer_wall_first", "inset_direction", _mapped({"True": "outside_in"}, "inside_out")),
    ("shell.seam_position", "z_seam_type", _mapped(_CURA_SEAM, "sharpest_corner")),
    ("shell.ironing", "ironing_enabled", _boolean),
    # CuraEngine hat keinen umschaltbaren Wandgenerator und keine gesonderte
    # genaue Außenwand: es rechnet ohnehin mit variabler Bahnbreite. Was es
    # nicht kennt, bekommt keinen Eintrag — eine Zuordnung auf das
    # Nächstbeste wäre eine Einstellung, die woanders landet.
    #
    # Beide Brückenwege, Wand wie Fläche: Cura trennt sie, Solidon kennt eine
    # Brückengeschwindigkeit. Wirksam werden sie erst mit
    # ``bridge_settings_enabled`` — den setzt die Ableitungsstufe.
    ("speed.bridge", "bridge_wall_speed", _number),
    ("speed.bridge", "bridge_skin_speed", _number),
    ("speed.acceleration", "acceleration_print", _number),
    ("speed.outer_wall_acceleration", "acceleration_wall_0", _number),
    ("infill.density", "infill_sparse_density", _percent),
    ("infill.pattern", "infill_pattern", _mapped(_CURA_INFILL, "grid")),
    ("infill.angle", "infill_angles", _number),
    ("temperature.nozzle", "material_print_temperature", _integer),
    ("temperature.nozzle_first_layer", "material_print_temperature_layer_0", _integer),
    ("temperature.bed", "material_bed_temperature", _integer),
    ("temperature.bed_first_layer", "material_bed_temperature_layer_0", _integer),
    ("temperature.chamber", "build_volume_temperature", _integer),
    ("cooling.fan_speed", "cool_fan_speed", _percent),
    ("cooling.bridge_fan_speed", "bridge_fan_speed", _percent),
    ("cooling.disable_first_layers", "cool_fan_full_layer", _integer),
    ("cooling.minimum_layer_time", "cool_min_layer_time", _integer),
    ("speed.outer_wall", "speed_wall_0", _number),
    ("speed.inner_wall", "speed_wall_x", _number),
    # Curas Sammelgeschwindigkeit. Solidon hat keine — aber alles, was Cura
    # nicht einzeln bekommt (Stützen, Prime Tower), rechnet daraus, und ohne
    # sie bleibt es bei 60 mm/s aus der Definition.
    ("speed.inner_wall", "speed_print", _number),
    ("speed.infill", "speed_infill", _number),
    ("speed.top_surface", "speed_topbottom", _number),
    ("speed.first_layer", "speed_layer_0", _number),
    ("speed.travel", "speed_travel", _number),
    ("support.style", "support_enable", _support_on_boolean),
    # Und die Art dazu: `support_structure` steht in der fdmprinter-Definition
    # (nachgeschlagen, nicht angenommen). Ohne den Eintrag bekam Cura nur das
    # An/Aus — wer Baumstützen einstellte, druckte Gitterstützen, und
    # `verify()` sah nichts, weil der Schlüssel nie geschrieben wurde.
    ("support.style", "support_structure", _mapped({"tree": "tree"}, "normal")),
    ("support.placement", "support_type", _mapped({"build_plate": "buildplate"}, "everywhere")),
    # Hier **ohne** Umrechnung: Cura zählt gegen die Senkrechte, so wie
    # Solidon. Die beiden anderen Familien drehen die Zählweise um, siehe
    # :func:`_angle_from_horizontal`.
    ("support.threshold_angle", "support_angle", _integer),
    ("support.z_gap", "support_z_distance", _number),
    ("support.xy_gap", "support_xy_distance", _number),
    ("support.density", "support_infill_rate", _percent),
    # Curas Schnittstelle ist eine **Höhe**, keine Schichtzahl — und sie
    # entsteht nur, wenn ``support_interface_enable`` sie einschaltet. Beides
    # rechnet die Ableitungsstufe: ohne sie wurden aus zwei Schichten zwei
    # Millimeter, das Zehnfache bei 0,2er Schichten.
    ("adhesion.kind", "adhesion_type", _mapped({"none": "none"}, "")),
    ("adhesion.skirt_loops", "skirt_line_count", _integer),
    ("adhesion.skirt_distance", "skirt_gap", _number),
    ("adhesion.brim_width", "brim_width", _number),
    ("adhesion.raft_layers", "raft_surface_layers", _integer),
    ("retraction.length", "retraction_amount", _number),
    ("retraction.speed", "retraction_speed", _number),
    ("retraction.z_hop", "retraction_hop", _number),
    ("retraction.z_hop", "retraction_hop_enabled", _positive_flag),
    # CuraEngine nennt dasselbe „Combing": der Kopf kämmt innerhalb des Teils
    # statt geradeaus zu fahren. ``noskin`` hält ihn zusätzlich von der
    # Oberfläche fern, wo eine Schleifspur sichtbar bliebe.
    ("retraction.avoid_crossing_walls", "retraction_combing", _mapped({"True": "noskin"}, "off")),
    ("filament.diameter", "material_diameter", _number),
    ("filament.flow_ratio", "material_flow", _percent),
    ("filament.max_flow", "material_max_flowrate", _number),
)

#: Was ``CuraEngine`` aus einem geschriebenen Wert **nicht** selbst ableitet.
#:
#: In ``fdmprinter.def.json`` trägt jede abgeleitete Einstellung zweierlei:
#: einen ``value``-Ausdruck und einen ``default_value``. Das Fenster wertet den
#: Ausdruck aus, die Rechenmaschine dahinter nimmt den Vorgabewert — sie löst
#: keine Vererbung auf (siehe :func:`app.core.export.handover._machine_keys`).
#: Was Solidon schreibt, bleibt damit an seinem Schlüssel stehen und erreicht
#: die nicht, aus denen gerechnet wird.
#:
#: Gemessen an einem 20-mm-Würfel, zweimal derselbe Lauf: 1100 mm Filament
#: gegen 818, 753 Sekunden gegen 660. Der größte Posten war die Füllung —
#: ``infill_line_distance`` blieb bei 2 mm, wo 5,6 gemeint waren.
#:
#: Hier stehen nur die **reinen Kopien**; was Cura rechnet, rechnet
#: :func:`app.core.export.handover._cura_dependants` nach. Absichtlich nicht
#: dabei: ``acceleration_travel`` (Cura leitet sie nur beim Spiralisieren aus
#: der Druckbeschleunigung ab, sonst sind es feste 5000) und alles am Prime
#: Tower, den ein Lauf mit einem Extruder nie baut.
CURA_MIRRORED: Final[dict[str, tuple[str, ...]]] = {
    "acceleration_print": (
        "acceleration_flooring",
        "acceleration_infill",
        "acceleration_ironing",
        "acceleration_layer_0",
        "acceleration_print_layer_0",
        "acceleration_roofing",
        "acceleration_skirt_brim",
        "acceleration_support",
        "acceleration_support_bottom",
        "acceleration_support_infill",
        "acceleration_support_interface",
        "acceleration_support_roof",
        "acceleration_topbottom",
        "acceleration_wall",
        "acceleration_wall_x",
        "acceleration_wall_x_flooring",
        "acceleration_wall_x_roofing",
        "raft_acceleration",
        "raft_base_acceleration",
        "raft_interface_acceleration",
        "raft_surface_acceleration",
    ),
    "acceleration_wall_0": ("acceleration_wall_0_flooring", "acceleration_wall_0_roofing"),
    "bottom_layers": ("initial_bottom_layers",),
    "bridge_fan_speed": ("skin_support_fan_speed",),
    "bridge_skin_speed": ("bridge_skin_speed_2", "bridge_skin_speed_3", "skin_support_speed"),
    "cool_fan_speed": ("cool_fan_speed_max", "cool_fan_speed_min"),
    "cool_min_layer_time": ("cool_min_layer_time_overhang",),
    "inset_direction": ("initial_layer_inset_direction",),
    "layer_height": (
        "infill_sparse_thickness",
        "raft_surface_thickness",
        "support_infill_sparse_thickness",
    ),
    "line_width": (
        "flooring_line_width",
        "infill_line_width",
        "raft_surface_line_spacing",
        "raft_surface_line_width",
        "roofing_line_width",
        "skin_line_width",
        "skirt_brim_line_width",
        "support_bottom_line_width",
        "support_interface_line_width",
        "support_line_width",
        "support_roof_line_width",
        "wall_line_width",
        "wall_line_width_0",
        "wall_line_width_x",
        "wall_transition_length",
    ),
    "material_flow": (
        "flooring_material_flow",
        "infill_material_flow",
        "roofing_material_flow",
        "skin_material_flow",
        "skirt_brim_material_flow",
        "support_bottom_material_flow",
        "support_interface_material_flow",
        "support_material_flow",
        "support_roof_material_flow",
        "wall_0_material_flow",
        "wall_0_material_flow_flooring",
        "wall_0_material_flow_roofing",
        "wall_material_flow",
        "wall_x_material_flow",
        "wall_x_material_flow_flooring",
        "wall_x_material_flow_roofing",
    ),
    # Ohne diesen bleibt die Mindesttemperatur bei 0 °C: Cura senkt bis dorthin
    # ab, wenn eine Schicht die Mindestzeit unterschreitet.
    "material_print_temperature": ("cool_min_temperature",),
    "retraction_amount": ("retraction_extrusion_window",),
    "retraction_hop": ("retraction_hop_after_extruder_switch_height",),
    "retraction_speed": ("retraction_prime_speed", "retraction_retract_speed"),
    "speed_layer_0": ("skirt_brim_speed", "speed_print_layer_0"),
    "speed_print": ("speed_support", "speed_support_infill"),
    "speed_topbottom": ("speed_flooring", "speed_roofing"),
    "speed_wall_0": ("speed_wall_0_flooring", "speed_wall_0_roofing"),
    "speed_wall_x": ("speed_wall_x_flooring", "speed_wall_x_roofing"),
    "support_angle": ("seam_overhang_angle",),
    "support_z_distance": ("support_bottom_distance", "support_top_distance"),
    "machine_height": ("gantry_height",),
    "min_wall_line_width": (
        "min_bead_width",
        "min_even_wall_line_width",
        "min_odd_wall_line_width",
    ),
    "skin_preshrink": ("bottom_skin_preshrink", "top_skin_preshrink"),
    "expand_skins_expand_distance": (
        "bottom_skin_expand_distance",
        "top_skin_expand_distance",
    ),
    "support_line_distance": ("support_initial_layer_line_distance",),
    "support_interface_height": ("support_bottom_height", "support_roof_height"),
}

#: Dasselbe mit einem Faktor davor — Curas Formel, als Zahl statt als Satz.
#:
#: Die Reihenfolge trägt: ``raft_base_speed`` rechnet auf ``raft_speed``, und
#: das steht darüber. Eine Abbildung wäre hier eine Falle, ein Tupel ist eine
#: Reihenfolge.
CURA_SCALED: Final[tuple[tuple[str, str, float], ...]] = (
    ("retraction_min_travel", "line_width", 2.0),
    ("support_z_seam_min_distance", "line_width", 2.0),
    ("brim_inside_margin", "line_width", 4.0),
    ("raft_interface_line_width", "line_width", 2.0),
    ("infill_wipe_dist", "line_width", 0.25),
    ("min_feature_size", "line_width", 0.25),
    ("small_skin_width", "line_width", 2.0),
    ("raft_base_line_width", "machine_nozzle_size", 2.0),
    ("raft_base_line_spacing", "machine_nozzle_size", 4.0),
    ("wall_0_wipe_dist", "machine_nozzle_size", 0.5),
    ("support_xy_distance_overhang", "machine_nozzle_size", 0.5),
    ("retraction_combing_avoid_distance", "machine_nozzle_size", 1.5),
    ("wall_transition_filter_deviation", "machine_nozzle_size", 0.25),
    ("raft_interface_thickness", "layer_height", 1.5),
    ("raft_base_thickness", "layer_height_0", 1.2),
    ("support_tree_tip_diameter", "support_line_width", 2.0),
    ("speed_wall", "speed_print", 0.5),
    ("raft_speed", "speed_print", 0.5),
    ("raft_base_speed", "raft_speed", 0.75),
    ("raft_interface_speed", "raft_speed", 0.75),
    ("raft_surface_speed", "raft_speed", 1.0),
    ("support_tree_angle_slow", "support_tree_angle", 2.0 / 3.0),
)

#: Was ``CuraEngine`` ableiten würde und trotzdem nicht geschrieben wird —
#: mit dem Grund daneben, damit die Liste eine Entscheidung bleibt und nicht
#: zu einer Sammelstelle für Vergessenes wird.
#:
#: ``tests/test_print_settings.py`` hält sie ehrlich: was in der Definition
#: von einem geschriebenen Wert abhängt und weder gesetzt noch hier begründet
#: ist, lässt den Lauf rot werden.
CURA_UNTOUCHED: Final[dict[str, str]] = {
    "acceleration_prime_tower": "Prime Tower — ein Lauf mit einem Extruder baut keinen.",
    "prime_tower_base_height": "wie oben",
    "prime_tower_base_size": "wie oben",
    "prime_tower_brim_enable": "wie oben",
    "prime_tower_flow": "wie oben",
    "prime_tower_line_width": "wie oben",
    "prime_tower_position_x": "wie oben",
    "prime_tower_position_y": "wie oben",
    "prime_tower_raft_base_line_spacing": "wie oben",
    "speed_prime_tower": "wie oben",
    "wipe_hop_amount": "Düse abstreifen zwischen den Schichten — steht auf aus.",
    "wipe_hop_enable": "wie oben",
    "wipe_retraction_amount": "wie oben",
    "wipe_retraction_prime_speed": "wie oben",
    "wipe_retraction_retract_speed": "wie oben",
    "wipe_retraction_speed": "wie oben",
    "material_break_preparation_temperature": "Stützmaterial zum Abbrechen — kennt Solidon nicht.",
    "interlocking_beam_width": "Verzahnung zweier Materialien — braucht zwei Extruder.",
    "multi_material_paint_depth": "wie oben",
    "multi_material_paint_resolution": "wie oben",
    "cross_infill_pocket_size": "Muster ``cross`` — bietet Solidon nicht an.",
    "sub_div_rad_add": "Muster ``cubicsubdiv`` — bietet Solidon nicht an.",
    "wall_thickness": "gilt nur beim Spiralisieren, und das schaltet Solidon nicht ein.",
    "layer_start_x": "gilt nur mit ``layer_start_at_z_seam``, und das steht auf aus.",
    "layer_start_y": "wie oben",
    "build_fan_full_layer": "Gehäuselüfter — keine Einstellung in Solidon.",
    "cool_fan_full_at_height": "nur Elternwert von ``cool_fan_full_layer``, das direkt kommt.",
    "skin_outline_count": "wird 1 für jedes Muster, das Solidon anbietet — also die Vorgabe.",
    "min_skin_width_for_expansion": "wird 0, solange der Öffnungswinkel bei 90° steht.",
    "adhesion_extruder_nr": "Extrudernummer — bei einem Extruder ist die Vorgabe richtig.",
    "raft_base_extruder_nr": "wie oben",
    "raft_interface_extruder_nr": "wie oben",
    "raft_surface_extruder_nr": "wie oben",
    "skirt_brim_extruder_nr": "wie oben",
    "raft_base_infill_overlap_mm": "die Überlappung dahinter steht auf 0, gerechnet bleibt 0.",
    "raft_interface_infill_overlap_mm": "wie oben",
    "raft_surface_infill_overlap_mm": "wie oben",
    "acceleration_travel": "Cura leitet sie nur beim Spiralisieren ab; sonst sind es feste 5000.",
    "zig_zaggify_infill": "wird falsch für jedes Muster, das Solidon anbietet — die Vorgabe.",
}

#: Wie oft ein Füllmuster seine Linien kreuzt. Aus derselben Formel wie
#: ``infill_line_distance`` in der Cura-Definition — ein Gitter legt zwei
#: Linienscharen übereinander, also darf jede den doppelten Abstand haben.
CURA_INFILL_CROSSINGS: Final[dict[str, float]] = {
    "grid": 2.0,
    "trihexagon": 3.0,
    "cubic": 3.0,
    "triangles": 3.0,
    "lines": 1.0,
    "gyroid": 1.0,
}

#: Dasselbe für die Stützfüllung. Solidon schreibt ``support_pattern`` nicht,
#: es bleibt bei Curas ``zigzag`` — einer Linienschar.
CURA_SUPPORT_CROSSINGS: Final = 1.0

#: Wie ein Material beim Slicer heißt. Fast immer die Solidon-Kennung in
#: Großbuchstaben — nur wo die Schreibweisen auseinandergehen, steht ein
#: Eintrag. Ein unbekannter Typ ist kein Abbruch: der Slicer nimmt ihn als
#: eigenen Namen und rechnet mit den Vorgaben seiner Familie.
FILAMENT_TYPES: Final[dict[str, str]] = {"tpu-95a": "TPU"}


def filament_type(material_id: str) -> str:
    """Der Materialbezeichner in der Schreibweise des Slicers."""
    return FILAMENT_TYPES.get(material_id, material_id.upper())


#: Welche Schlüssel zu welcher Haftungsart gehören. Die Slicer lesen sie als
#: unabhängige Maße, gemeint ist aber genau eine Art: wer Skirt eingestellt hat
#: und trotzdem ``raft_layers`` mitschickt, bekommt beides.
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


def keys_for(path: str) -> tuple[str, ...]:
    """Unter welchen Namen dieser Wert in den Slicern steht, ohne Doppelte.

    Die Gegenrichtung der Tabellen oben, und sie hat einen Kunden: Wer aus
    einem Slicer kommt, sucht seine Einstellung unter dem Namen, den er dort
    gelernt hat. ``perimeters`` heißt bei uns *Wandbahnen*, und wer das eine
    tippt, soll das andere finden.

    Die Namen sind englische Schlüssel und keine Oberflächentexte — sie werden
    nicht übersetzt, so wie ``skirt`` und ``brim`` im Dialog auch nicht
    übersetzt werden: Der Kunde findet sie unter genau diesem Wort in seinem
    Slicer wieder.
    """
    seen: list[str] = []
    for entries in TABLES.values():
        for entry in entries:
            if entry.path == path and entry.key not in seen:
                seen.append(entry.key)
    return tuple(seen)


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


#: Einstellungen, die dieser Slicer nicht entgegennimmt (§29).
#:
#: **Gemessen, nicht aus den Tabellen geschlossen** — und der Unterschied ist
#: der ganze Punkt: Ein Wert kann auf drei Wegen ankommen. Über eine Zeile in
#: :data:`TABLES`, über :data:`ADHESION_KEYS`, oder weil ``handover`` ihn
#: verrechnet: ``support.density`` steht in keiner Prusa-Zeile und wird
#: trotzdem übergeben, weil daraus ein Linienabstand wird. Wer nur die Tabelle
#: liest, sperrt ein Feld, das sehr wohl wirkt — beim ersten Anlauf am
#: 03.09.2026 waren es drei falsche bei Prusa und zwei bei Cura.
#:
#: Gemessen wird über ``values_for``: Wert ändern, übersetzte Werte zweimal
#: bauen, vergleichen. Und über **vier Haftungsarten**, denn
#: ``_only_chosen_adhesion`` nullt die Maße der nicht gewählten — „Skirt-Runden"
#: bei eingestelltem Brim ist eine Abhängigkeit und kein toter Wert.
#:
#: ``tests/test_print_settings_ui.py`` hält die Liste gegen diese Messung.
NOT_TAKEN_BY: Final[dict[SlicerFlavour, frozenset[str]]] = {
    "prusa": frozenset({"shell.precise_outer_wall"}),
    "orca": frozenset(),
    "cura": frozenset(
        {
            "shell.wall_generator",
            "shell.precise_outer_wall",
            "retraction.wipe",
            "filament.density",
            "filament.cost_per_kg",
        }
    ),
}


def takes(flavour: SlicerFlavour, path: str) -> bool:
    """Nimmt dieser Slicer diese Einstellung überhaupt entgegen (§29)?

    Ein Feld, an dem man dreht, ohne dass etwas geschieht, ist eine Attrappe —
    und schlimmer noch ist ein **Vorschlag** darauf, denn er verspricht eine
    Wirkung. Die Oberfläche graut damit aus und begründet, statt den Kunden an
    einem Regler ziehen zu lassen, der bei seinem Slicer nichts tut.

    Die Antwort steht in :data:`NOT_TAKEN_BY` und ist gemessen; warum sie
    nicht aus den Tabellen kommen kann, steht dort.
    """
    return path not in NOT_TAKEN_BY[flavour]


def wants_bed_coordinates(flavour: SlicerFlavour) -> bool:
    """Misst dieser Slicer von der Ecke der Platte statt von ihrer Mitte?

    Nur die Orca-Familie tut das. Solidon rechnet um den Ursprung, und für die
    beiden anderen schreibt die Übergabe genau diese Welt: Cura bekommt
    ``machine_center_is_zero``, PrusaSlicer eine Bettform von ``-128`` bis
    ``128``. Wer ihnen trotzdem Bettkoordinaten schickt, verschiebt den Druck
    um den halben Bauraum — gemessen im G-Code, und bei PrusaSlicer endet es
    in „All objects are outside of the print volume".
    """
    return flavour == "orca"


# --- Was eine Familie kann, und was sie von uns braucht -------------------------
#
# Die Prädikate hier unten sind der **eine Ort**, an dem eine Eigenschaft einer
# Slicer-Familie zugeordnet wird. Sie stehen hier und nicht als Vergleich an
# ihrer Verwendungsstelle, weil ein Vergleich gegen den Namen die Eigenschaft
# nur im Kommentar nennt — und Kommentare wandern nicht mit, wenn eine vierte
# Familie dazukommt.
#
# Gemessen am 27.08.2026: 26 Verzweigungen nach Familie in ``app/`` und
# ``tools/``, elf davon gegen ``"orca"``, und jede meinte etwas anderes. Was
# hier **nicht** hingehört, sind die Dreiwege-Fälle — ``write_config`` schreibt
# INI, JSON oder gar nichts, ``_command`` baut drei verschiedene
# Kommandozeilen. Die haben keine gemeinsame Eigenschaft, die man benennen
# könnte, sondern drei verschiedene Formate; ein Prädikat davor wäre ein Name
# ohne Aussage.
#
# Der Familienschnitt selbst trägt: ``FLAVOUR_BY_NAME`` bildet ElegooSlicer,
# Bambu Studio und SuperSlicer auf die drei ab, und am echten ElegooSlicer
# gemessen findet Solidon damit 3887 Profile und den richtigen Drucker. Wer
# hier eine vierte Familie einführen will, sollte zuerst nachsehen, ob es
# nicht eine dieser Eigenschaften ist, die er eigentlich meint.


def has_user_profile_tree(flavour: SlicerFlavour) -> bool:
    """Legt dieser Slicer die selbst angelegten Profile unter seinem Namen ab?

    Die Orca-Familie tut es: ``%APPDATA%/<Programmname>/user/<Konto>``, und der
    Programmname ist der der ausführbaren Datei ohne Trenner — ``elegoo-slicer.exe``
    schreibt nach ``ElegooSlicer``. Daran hängen zwei Auskünfte, die Solidon
    sonst nirgends bekommt: welche Profile der Nutzer selbst angelegt hat und
    welche Maschine er zuletzt eingestellt hatte.

    PrusaSlicer und Cura haben so einen Baum nicht (oder keinen, den Solidon
    liest) — dort bleibt es bei der Vorgabe, und das ist richtig: Eine falsche
    Vorauswahl sieht aus wie eine Entscheidung (§29).
    """
    return flavour == "orca"


def has_filament_profiles(flavour: SlicerFlavour) -> bool:
    """Kennt dieser Slicer das Filament als eigenes Profil, je Spule?

    Nur die Orca-Familie. Für sie *ist* ein Materialslot ein Filament — zwei
    Farben sind zwei Spulen, und die fahren verschieden: eigene Temperatur,
    eigener Fluss, eigene Trocknung. Daran hängt beides, was Solidon dazu
    sagen kann: der Abgleich gegen das hinterlegte Profil (§22.5) und die
    Meldung, dass Werte je Spule bei den anderen beiden gar nicht ankommen.

    PrusaSlicer und Cura führen das Material als Teil des Prozesses. Ein Wert
    je Spule ist dort kein Fehler des Nutzers — der Slicer kann es nicht —,
    aber eine Auskunft schon (Regel 17).
    """
    return flavour == "orca"


def takes_a_machine_profile(flavour: SlicerFlavour) -> bool:
    """Lädt dieser Slicer seine Maschine als eigenes Profil aus seinem Bestand?

    Nur die Orca-Familie, und aus demselben Grund wie bei
    :func:`has_filament_profiles`: Dort ist die Maschine eine Datei, die
    Startcode, Schichtwechselcode und Maschinengrenzen trägt — Angaben, die nur
    der Hersteller kennt und die Solidon nicht erfindet.

    Cura und PrusaSlicer bekommen ihre Maschinenseite dagegen von Solidon
    selbst (:func:`_machine_keys`): Bauraum, Düse und Bettform aus dem eigenen
    Druckerprofil, und für PrusaSlicer ist eine ``.ini`` damit eigenständig
    lauffähig. Dass dort kein fremdes Profil steht, ist die Bauart und kein
    Mangel — wer es als Mangel meldet, warnt bei jedem Export ohne Anlass
    (:func:`machine_missing`).
    """
    return flavour == "orca"


def reads_settings_from_project_file(flavour: SlicerFlavour) -> bool:
    """Nimmt dieser Slicer seine Einstellungen aus der übergebenen Datei?

    Die Orca-Familie liest eine Beilage in der 3MF
    (``Metadata/project_settings.config``, JSON). PrusaSlicer liest zwar auch
    eine (``Metadata/Slic3r_PE.config``), aber beim *Lauf* bekommt es seine
    Werte über ``--load``; Cura bekommt sie ausschließlich über die
    Kommandozeile, denn seine 3MF-Seite sitzt im Fenster und nicht in der
    Rechenmaschine dahinter.

    Nicht zu verwechseln mit dem, was eine **exportierte** Datei mitträgt:
    Eine 3MF soll man drucken können, ohne sie einzurichten, und dafür legt
    ``writer`` beiden Familien ihre Beilage bei (siehe `.claude/rules/dateiformat.md`).
    Hier geht es um den Weg, auf dem der Slicer beim Slicen selbst liest.
    """
    return flavour == "orca"


def names_its_own_output(flavour: SlicerFlavour) -> bool:
    """Bestimmt der Slicer den Namen der Druckdatei selbst?

    Die Orca-Familie tut es und lässt sich nicht hineinreden; für sie gilt
    deshalb die jüngste Datei im Zielordner. Prusa und Cura schreiben dorthin,
    wohin die Kommandozeile zeigt, und dann ist der Name der, den Solidon
    vergeben hat.
    """
    return flavour == "orca"


def has_readable_profiles(flavour: SlicerFlavour) -> bool:
    """Gibt es Profildateien, die Solidon lesen und anbieten kann?

    Für ``prusa`` nicht, und das ist kein Mangel: Eine PrusaSlicer-``.ini``
    läuft eigenständig, sobald Düse und Bettform darin stehen, und die
    schreibt Solidon selbst (§29). Es gibt dort also nichts auszuwählen.
    """
    return flavour != "prusa"


def reads_assembly_file(flavour: SlicerFlavour) -> bool:
    """Liest dieser Slicer eine 3MF-Baugruppe — mit Namen und Materialslots?

    ``CuraEngine`` nicht. Die 3MF-Seite von Cura sitzt in seinem Fenster, nicht
    in der Rechenmaschine dahinter, und ein übergebenes 3MF endete dort in „Der
    Slicer hat keine Druckdatei geschrieben", ohne dass irgendwo stand, warum.
    Es bekommt ein STL mit allen Teilen der Platte; Namen und Materialslots
    liest es ohnehin nicht, und seine Einstellungen kommen über die
    Kommandozeile.
    """
    return flavour != "cura"


def has_key_definitions(flavour: SlicerFlavour) -> bool:
    """Liegt neben dem Programm eine Datei, die jeden gültigen Schlüssel nennt?

    Nur bei Cura (``fdmprinter.def.json``), und sie ist dort die einzige
    Gegenprobe, die es gibt: CuraEngine schreibt seine wirksame Konfiguration
    **nicht** in den G-Code — null von 47 Schlüsseln —, während Prusa und Orca
    sie vollständig hineinschreiben und sich damit selbst prüfen lassen
    (:func:`verify`). In genau dieser Lücke saß ``outer_inset_first``: ein Name
    aus Cura 4, in Cura 5 verworfen, ohne Fehler und ohne Warnung — null von
    fünfzig Lagen begannen außen, obwohl der Wert geschrieben war.
    """
    return flavour == "cura"
