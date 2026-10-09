"""Wie eine Solidon-Einstellung in jedem Slicer heißt (Bauplan §29).

Solidon hält die Einstellungen an einer Stelle (:class:`PrintSettings`), die
Slicer nennen dieselbe Sache verschieden: die Wandzahl ist bei PrusaSlicer
``perimeters``, bei Orca ``wall_loops`` und bei CuraEngine
``wall_line_count``. Diese Datei ist das Wörterbuch dazwischen — Daten, keine
Logik, damit ein weiterer Slicer eine Tabelle kostet und keinen Eingriff.

Drei Familien übersetzen die verbreiteten Programme:

``prusa``   PrusaSlicer und SuperSlicer — ``key = value`` in einer ``.ini``
``orca``    OrcaSlicer, Bambu Studio, ElegooSlicer und Creality Print ab
            Version 6 — JSON, aus PrusaSlicer hervorgegangen
``cura``    CuraEngine — ``-s key=value`` auf der Kommandozeile

Die vierte, ``other``, übersetzt nichts: Ein Programm ohne Familie bekommt
die Datei und keinen Wert (§29, zweite Übergabeart).

Was in einer Tabelle fehlt, bleibt beim Grundprofil des Slicers stehen. Das
ist Absicht: Solidon überschreibt, was es versteht, und lässt den Rest in
Ruhe (§29).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, NamedTuple

from app.core.knowledge.print_settings import SCARF_LENGTH
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.types import PrintSettings, SettingAdvice

SlicerFlavour = Literal["prusa", "orca", "cura", "other"]
"""Die Familie eines Slicers — und ``other`` für jedes Programm, dessen
Einstellungen Solidon nicht übersetzt.

``other`` ist die zweite Übergabeart aus §29 in Reinform: Das Programm
bekommt die geschriebene Datei in sein Fenster und sonst nichts — kein
Profil, keine Konfiguration, kein Konsolenlauf, kein Rücklesen. Bis zum
22.09.2026 verlangte schon das bloße Öffnen eine Familie, die übersetzt, und
ein Resin-Slicer (ChituBox, Lychee, die Hersteller-Slicer) scheiterte daran,
obwohl er dafür nichts brauchte (Resin-Konzept §4). Jedes Prädikat unten
antwortet für ``other`` mit „nein“, und :func:`app.core.export.handover.slice_model`
sagt, dass dieser Weg dort nicht führt.
"""

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


def _optional_number(value: object) -> str:
    """Eine unbekannte Vorgabe bleibt beim Slicer; die Zahl null bleibt eine Zahl."""
    return "" if value is None else _number(value)


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


def _positive_switch(value: object) -> str:
    """Der Schalter zu einem Anteil, der nur mit ihm gilt — ``0``/``1`` wie
    :func:`_flag`, für Prusa und die Orca-Familie.

    Der untere Lüfterwert ist so einer: Ohne ``reduce_fan_stop_start_freq``
    (Orca) oder ``fan_always_on`` (PrusaSlicer) nehmen beide ihn nur innerhalb
    der Schwelle und schalten den Lüfter bei längeren Schichten **ganz aus**.
    Gemessen am ElegooSlicer ohne Herstellerprofil, dessen Vorgabe hier 0 ist:
    PLA mit ``M106 S0`` in jeder Schicht über 60 s. Ein unterer Wert von null
    meint beides gleich, der Schalter steht dann auf 0.
    """
    return "1" if float(value) > 0.0 else "0"  # type: ignore[arg-type]


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


def _only(table: dict[str, str]) -> Callable[[object], str]:
    """Für die genannten Werte eine Angabe, sonst Schweigen.

    :func:`_mapped` gibt ohne Treffer den Wert selbst weiter; hier bleibt der
    Text leer, und ein leerer Text geht nicht hinaus (``handover.as_mapping``)
    — der Wert des Herstellers gilt dann weiter.
    """

    def convert(value: object) -> str:
        return table.get(str(value), "")

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

#: Nur die ausdrücklichen Arten. ``auto`` und ``none`` schweigen: Dann gilt
#: der Stil des Prusa-Profils (``snug``), und ausgeschaltete Stützen haben
#: keinen Stil, den jemand gewählt hätte (Entscheidung J, 27.09.2026).
_PRUSA_SUPPORT_STYLE: Final = {"grid": "grid", "tree": "organic"}

PRUSA: Final[tuple[Row, ...]] = (
    ("layers.layer_height", "layer_height", _number),
    ("layers.first_layer_height", "first_layer_height", _number),
    ("layers.line_width", "extrusion_width", _number),
    ("layers.line_width", "external_perimeter_extrusion_width", _number),
    ("layers.line_width", "perimeter_extrusion_width", _number),
    ("layers.line_width", "infill_extrusion_width", _number),
    ("layers.line_width", "solid_infill_extrusion_width", _number),
    ("layers.line_width", "top_infill_extrusion_width", _number),
    ("layers.line_width", "support_material_extrusion_width", _number),
    ("layers.first_layer_line_width", "first_layer_extrusion_width", _number),
    ("shell.wall_count", "perimeters", _integer),
    ("shell.top_layers", "top_solid_layers", _integer),
    ("shell.bottom_layers", "bottom_solid_layers", _integer),
    ("shell.outer_wall_first", "external_perimeters_first", _flag),
    ("shell.seam_position", "seam_position", _plain),
    ("shell.scarf_seam", "scarf_seam_placement", _mapped({"True": "contours"}, "nowhere")),
    ("shell.scarf_seam", "scarf_seam_length", _only({"True": f"{SCARF_LENGTH:g}"})),
    ("shell.scarf_seam", "scarf_seam_only_on_smooth", _only({"True": "1"})),
    ("shell.scarf_seam", "scarf_seam_on_inner_perimeters", _only({"True": "0"})),
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
    # Zwei Enden einer Kurve über der Schichtzeit, nicht ein Wert zweimal:
    # Bis zum 23.09.2026 stand hier ``cooling.fan_speed`` auch unter
    # ``min_fan_speed``, und der Lüfter lief fest (Befund Robert).
    ("cooling.fan_speed", "max_fan_speed", _percent),
    ("cooling.minimum_fan_speed", "min_fan_speed", _percent),
    ("cooling.minimum_fan_speed", "fan_always_on", _positive_switch),
    ("cooling.fan_below_layer_time", "fan_below_layer_time", _integer),
    ("cooling.bridge_fan_speed", "bridge_fan_speed", _percent),
    ("cooling.disable_first_layers", "disable_fan_first_layers", _integer),
    ("cooling.minimum_layer_time", "slowdown_below_layer_time", _integer),
    ("cooling.minimum_speed", "min_print_speed", _number),
    ("speed.outer_wall", "external_perimeter_speed", _number),
    ("speed.inner_wall", "perimeter_speed", _number),
    ("speed.infill", "infill_speed", _number),
    # **Die innere volle Füllung und die Lückenfüllung** (RM-191). Ohne die
    # beiden Zeilen fuhr PrusaSlicer seine eingebauten 20 mm/s — für die
    # größte Rolle einer Regalplatte, die volle Füllung zwischen den Böden.
    # Gemessen am Gewürzregal (Durchsicht 0.5.0): 48 532 s gegen 23 655 s bei
    # Orca für dieselbe Platte. Die Füllung ist eine Geschwindigkeit, ob
    # dünn oder voll; die Lücke zwischen den Wänden fährt wie die Wand.
    ("speed.infill", "solid_infill_speed", _number),
    ("speed.inner_wall", "gap_fill_speed", _number),
    ("speed.top_surface", "top_solid_infill_speed", _number),
    ("speed.first_layer", "first_layer_speed", _number),
    # Die Füllung der ersten Schicht hat bei PrusaSlicer ein eigenes Tempo, das
    # ``first_layer_speed`` nicht erreicht — wie bei Orca, siehe dort.
    ("speed.first_layer", "first_layer_infill_speed", _number),
    ("speed.travel", "travel_speed", _number),
    ("retraction.avoid_crossing_walls", "avoid_crossing_perimeters", _flag),
    ("support.style", "support_material", _support_on),
    ("support.style", "support_material_style", _only(_PRUSA_SUPPORT_STYLE)),
    # „Gitter" heißt Gitter: Das Muster des Herstellers ist bei der Orca-Familie
    # und bei PrusaSlicer oft ``rectilinear`` — Linien, die in jeder Schicht in
    # dieselbe Richtung laufen und als freistehende Wände umkippen. Gemessen an
    # der Waschschüssel (25.09.2026) mit Elegoos Muster: ab Schicht 2 lose
    # Einzellinien im Abstand von 2,8 mm, und im Druck verschoben sie sich.
    # ``rectilinear-grid`` wechselt die Richtung je Schicht und steht. Für
    # Bäume schweigt die Zeile: Dort gilt das Muster des Herstellers.
    ("support.style", "support_material_pattern", _only({"grid": "rectilinear-grid"})),
    ("support.placement", "support_material_buildplate_only", _mapped({"build_plate": "1"}, "0")),
    ("support.threshold_angle", "support_material_threshold", _angle_from_horizontal),
    ("support.z_gap", "support_material_contact_distance", _number),
    ("support.xy_gap", "support_material_xy_spacing", _number),
    ("support.interface_layers", "support_material_interface_layers", _integer),
    ("adhesion.skirt_loops", "skirts", _integer),
    ("adhesion.skirt_distance", "skirt_distance", _number),
    ("adhesion.brim_width", "brim_width", _number),
    ("adhesion.brim_gap", "brim_separation", _number),
    ("adhesion.raft_layers", "raft_layers", _integer),
    ("adhesion.raft_gap", "raft_contact_distance", _optional_number),
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

#: Nur die ausdrücklichen Arten (Entscheidung J, 27.09.2026). Hier stand
#: auch ``"none": "normal(auto)"`` — ausgeschaltete Stützen schrieben Gitter
#: über Elegoos und Bambus Baum, und wer sie im Slicerfenster einschaltete,
#: bekam Gitter. ``auto`` heißt: Stützen an, die Art des Herstellerprofils.
_ORCA_SUPPORT_TYPE: Final = {
    "grid": "normal(auto)",
    "tree": "tree(auto)",
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
    # **Die Bahnbreite gilt jeder Rolle** (RM-191). ``line_width`` allein
    # erreichte nur, was das Herstellerprofil nicht selbst setzt — beim
    # Centauri Carbon 2 fuhren Innenwand und Füllung weiter mit 0,45 mm, alle
    # anderen mit Solidons 0,42. PrusaSlicer leitet seine Breiten aus der einen
    # ab, Cura spiegelt sie (``CURA_MIRRORED``); hier stehen sie ausdrücklich.
    ("layers.line_width", "outer_wall_line_width", _number),
    ("layers.line_width", "inner_wall_line_width", _number),
    ("layers.line_width", "sparse_infill_line_width", _number),
    ("layers.line_width", "internal_solid_infill_line_width", _number),
    ("layers.line_width", "top_surface_line_width", _number),
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
    # **Die Schrägnaht braucht ihre Länge.** Elegoos Basisprozess führt
    # ``seam_slope_min_length = 0``, und dann setzt ElegooSlicer keine Rampe:
    # gemessen am Minigolf-Schaft 0 von 1000 Außenschleifen, mit 20 mm 997.
    # Nur die Außenwand und nur glatte Schleifen — eine Schleife mit Ecke
    # versteckt die Naht selbst, und schräg angesetzte Innenwände kosten Zeit,
    # die niemand sieht (dort 1:22 h statt 8 min je Schaft).
    ("shell.scarf_seam", "seam_slope_type", _mapped({"True": "external"}, "none")),
    ("shell.scarf_seam", "seam_slope_min_length", _only({"True": f"{SCARF_LENGTH:g}"})),
    ("shell.scarf_seam", "seam_slope_conditional", _only({"True": "1"})),
    ("shell.scarf_seam", "seam_slope_inner_walls", _only({"True": "0"})),
    # Bambu Studio führt die Schrägnaht auch im Filament
    # (``filament_scarf_seam_type``), und das Filament sticht Prozess und
    # Objekt, solange dieser Schalter aus ist: gemessen am P1S, Objektwert
    # geschrieben und keine einzige Rampe.
    ("shell.scarf_seam", "override_filament_scarf_seam_setting", _only({"True": "1"})),
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
    # Die Lüfterkurve wie bei PrusaSlicer, darüber. Gemessen am ElegooSlicer
    # mit Elegoo PLA @ECC2 (50 bis 100 %, 80 s): ``M106 S255`` in jeder
    # Schicht, solange ``fan_min_speed`` den oberen Wert bekam.
    ("cooling.fan_speed", "fan_max_speed", _percent, "filament"),
    ("cooling.minimum_fan_speed", "fan_min_speed", _percent, "filament"),
    ("cooling.minimum_fan_speed", "reduce_fan_stop_start_freq", _positive_switch, "filament"),
    ("cooling.fan_below_layer_time", "fan_cooling_layer_time", _integer, "filament"),
    ("cooling.bridge_fan_speed", "overhang_fan_speed", _percent, "filament"),
    ("cooling.disable_first_layers", "close_fan_the_first_x_layers", _integer, "filament"),
    ("cooling.minimum_layer_time", "slow_down_layer_time", _integer, "filament"),
    ("cooling.minimum_speed", "slow_down_min_speed", _number, "filament"),
    ("speed.outer_wall", "outer_wall_speed", _number),
    ("speed.inner_wall", "inner_wall_speed", _number),
    ("speed.infill", "sparse_infill_speed", _number),
    # Dieselben zwei wie bei PrusaSlicer (RM-191): Ohne sie fuhr die
    # Orca-Familie die volle Füllung und die Lücken mit den 250 mm/s des
    # Herstellerprofils, während Wände und dünne Füllung Solidons Werte
    # bekamen — ein Auftrag aus zwei Geschwindigkeitswelten.
    ("speed.infill", "internal_solid_infill_speed", _number),
    ("speed.inner_wall", "gap_infill_speed", _number),
    ("speed.top_surface", "top_surface_speed", _number),
    ("speed.first_layer", "initial_layer_speed", _number),
    # **Die erste Schicht ist die ganze erste Schicht.** Orca fährt ihre
    # Füllung eigens: am Centauri Carbon 2 mit 105 mm/s, Wände und Brim mit
    # 50. Solidons Feld erreichte die Füllung nicht, und am Minigolf-Satz
    # rissen genau die kurzen Bodenbahnen der schmalen Stege (27.09.2026).
    ("speed.first_layer", "initial_layer_infill_speed", _number),
    ("speed.travel", "travel_speed", _number),
    # Orca hat PrusaSlicer als Vorfahren und schreibt Wahrheitswerte wie es:
    # "0" und "1", nicht "true" und "false". Ein "true" hier bleibt still
    # wirkungslos — der Slicer meldet nichts, er stützt bloß nicht.
    ("support.style", "enable_support", _support_on),
    ("support.style", "support_type", _only(_ORCA_SUPPORT_TYPE)),
    # Dasselbe Kreuzmuster wie bei PrusaSlicer, siehe dort.
    ("support.style", "support_base_pattern", _only({"grid": "rectilinear-grid"})),
    ("support.placement", "support_on_build_plate_only", _mapped({"build_plate": "1"}, "0")),
    ("support.threshold_angle", "support_threshold_angle", _angle_from_horizontal),
    ("support.z_gap", "support_top_z_distance", _number),
    ("support.xy_gap", "support_object_xy_distance", _number),
    ("support.interface_layers", "support_interface_top_layers", _integer),
    # ``auto`` ist Orcas ``auto_brim`` (``advise.AUTO_BRIM_FLAVOURS``) und die
    # Vorgabe jedes Herstellerprofils. Bis zum 27.09.2026 kannte Solidon es
    # nicht und schrieb ``no_brim`` darüber.
    (
        "adhesion.kind",
        "brim_type",
        _mapped({"brim": "outer_only", "auto": "auto_brim"}, "no_brim"),
    ),
    ("adhesion.skirt_loops", "skirt_loops", _integer),
    ("adhesion.skirt_distance", "skirt_distance", _number),
    ("adhesion.brim_width", "brim_width", _number),
    ("adhesion.brim_gap", "brim_object_gap", _number),
    ("adhesion.raft_layers", "raft_layers", _integer),
    ("adhesion.raft_gap", "raft_contact_distance", _optional_number),
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
    # Cura setzt die Schrägnaht nur an die Außenwand und kennt kein „nur an
    # glatten Schleifen“; eine Länge von null schaltet sie aus.
    (
        "shell.scarf_seam",
        "scarf_joint_seam_length",
        _mapped({"True": f"{SCARF_LENGTH:g}"}, "0"),
    ),
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
    # Curas „Regular Fan Speed" ist das untere Ende, die Schwelle heißt
    # „Regular/Maximum Fan Speed Threshold" — dieselbe Kurve wie bei den
    # anderen beiden. Das obere Ende spiegelt ``CURA_MIRRORED`` aus
    # ``cool_fan_speed``, das untere stand dort bis zum 23.09.2026 mit.
    ("cooling.fan_speed", "cool_fan_speed", _percent),
    ("cooling.minimum_fan_speed", "cool_fan_speed_min", _percent),
    ("cooling.fan_below_layer_time", "cool_min_layer_time_fan_speed_max", _integer),
    ("cooling.bridge_fan_speed", "bridge_fan_speed", _percent),
    ("cooling.minimum_layer_time", "cool_min_layer_time", _integer),
    ("cooling.minimum_speed", "cool_min_speed", _number),
    ("speed.outer_wall", "speed_wall_0", _number),
    ("speed.inner_wall", "speed_wall_x", _number),
    # Curas Sammelgeschwindigkeit. Solidon hat keine — aber alles, was Cura
    # nicht einzeln bekommt (Stützen, Prime Tower), rechnet daraus, und ohne
    # sie bleibt es bei 60 mm/s aus der Definition.
    ("speed.inner_wall", "speed_print", _number),
    ("speed.infill", "speed_infill", _number),
    ("speed.infill", "speed_topbottom", _number),
    ("speed.top_surface", "speed_roofing", _number),
    ("speed.first_layer", "speed_layer_0", _number),
    ("speed.travel", "speed_travel", _number),
    ("support.style", "support_enable", _support_on_boolean),
    # Und die Art dazu: `support_structure` steht in der fdmprinter-Definition
    # (nachgeschlagen, nicht angenommen). Ohne den Eintrag bekam Cura nur das
    # An/Aus — wer Baumstützen einstellte, druckte Gitterstützen, und
    # `verify()` sah nichts, weil der Schlüssel nie geschrieben wurde.
    ("support.style", "support_structure", _mapped({"tree": "tree"}, "normal")),
    # **Kein ``support_pattern``.** Curas Vorgabe ``zigzag`` verbindet ihre
    # Linien und kippt nicht; das Kreuzmuster darüber gilt Orcas und Prusas
    # unverbundenem ``rectilinear`` (Waschschüssel, 25.09.2026). Alle
    # Werksprofile in Cura fahren ``zigzag`` (Prüfbericht Cura, B4).
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
    # Vier Namen, und sie stimmen mit Curas eigenen überein — deshalb stand
    # hier eine Abbildung mit leerem Rückfallwert, also eine Durchleitung
    # (``fallback or str(value)``). Sie war die einzige Stelle der Cura-Tabelle,
    # an der ein Wert aus der Projektdatei wörtlich in ein ``-s``-Argument
    # gelangte. Ausgeschrieben ist es nicht länger, aber es ist eine
    # Positivliste: Was nicht darin steht, wird die Vorgabe aus
    # :data:`app.core.types.AdhesionSettings` und nicht der fremde Text.
    (
        "adhesion.kind",
        "adhesion_type",
        _mapped({"none": "none", "skirt": "skirt", "brim": "brim", "raft": "raft"}, "skirt"),
    ),
    ("adhesion.skirt_loops", "skirt_line_count", _integer),
    ("adhesion.skirt_distance", "skirt_gap", _number),
    ("adhesion.brim_width", "brim_width", _number),
    ("adhesion.brim_gap", "brim_gap", _number),
    ("adhesion.raft_layers", "raft_surface_layers", _integer),
    ("adhesion.raft_gap", "raft_airgap", _optional_number),
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
    # **Kein ``material_max_flowrate``.** CuraEngine liest den Schlüssel nicht
    # (null Treffer in ``CuraEngine.exe`` 5.13, in ``fdmprinter`` abgeschaltet);
    # den Volumenstrom hält Solidon über die Tempi (``print_settings._within_flow``).
)

#: Jerk-Beziehungen aus Curas Grund- und Herstellerdefinitionen. Der Profilauflöser
#: übernimmt sie nur, wenn der native Wert genau diesen Verweis trägt.
CURA_JERK_LINKS: Final = {
    "jerk_travel": "jerk_print",
    "jerk_infill": "jerk_print",
    "jerk_wall": "jerk_print",
    "jerk_wall_0": "jerk_wall",
    "jerk_wall_x": "jerk_wall",
    "jerk_wall_0_roofing": "jerk_wall_0",
    "jerk_wall_0_flooring": "jerk_wall_0",
    "jerk_wall_x_roofing": "jerk_wall_x",
    "jerk_wall_x_flooring": "jerk_wall_x",
    "jerk_topbottom": "jerk_print",
    "jerk_roofing": "jerk_topbottom",
    "jerk_flooring": "jerk_topbottom",
    "jerk_ironing": "jerk_topbottom",
    "jerk_support": "jerk_print",
    "jerk_support_infill": "jerk_support",
    "jerk_support_interface": "jerk_support",
    "jerk_prime_tower": "jerk_print",
    "jerk_layer_0": "jerk_print",
    "jerk_print_layer_0": "jerk_layer_0",
    "jerk_skirt_brim": "jerk_layer_0",
    "raft_jerk": "jerk_print",
    "raft_base_jerk": "raft_jerk",
    "raft_interface_jerk": "raft_jerk",
    "raft_surface_jerk": "raft_jerk",
}

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
#: dabei: alles am Prime Tower, den ein Lauf mit einem Extruder nie baut.
#:
#: **Zwei Zeilen folgen nicht Curas Formel, sondern den Werksprofilen**
#: (Stufe D, 27.09.2026). ``acceleration_travel`` leitet Cura nur beim
#: Spiralisieren aus der Druckbeschleunigung ab, sonst fährt es feste 5000 —
#: Elegoo setzt in Cura dieselbe Formel ohne Bedingung, Orca fährt am
#: Ender-3 V3 12 000. Und die erste Schicht hat eine eigene Beschleunigung
#: (``acceleration_layer_0`` aus ``PrinterProfile.first_layer_acceleration``,
#: gesetzt in ``handover._for_speeds``); die Raft-Basis gehört zu ihr, denn
#: sie ist die erste Schicht.
CURA_MIRRORED: Final[dict[str, tuple[str, ...]]] = {
    "acceleration_print": (
        "acceleration_flooring",
        "acceleration_infill",
        "acceleration_ironing",
        "acceleration_roofing",
        "acceleration_support",
        "acceleration_support_bottom",
        "acceleration_support_infill",
        "acceleration_support_interface",
        "acceleration_support_roof",
        "acceleration_topbottom",
        "acceleration_travel",
        "acceleration_wall",
        "acceleration_wall_x",
        "acceleration_wall_x_flooring",
        "acceleration_wall_x_roofing",
        "raft_acceleration",
        "raft_interface_acceleration",
        "raft_surface_acceleration",
    ),
    "acceleration_layer_0": (
        "acceleration_print_layer_0",
        "acceleration_skirt_brim",
        "raft_base_acceleration",
    ),
    "acceleration_wall_0": ("acceleration_wall_0_flooring", "acceleration_wall_0_roofing"),
    "bottom_layers": ("initial_bottom_layers",),
    "bridge_fan_speed": ("skin_support_fan_speed",),
    "bridge_skin_speed": ("bridge_skin_speed_2", "bridge_skin_speed_3", "skin_support_speed"),
    "cool_fan_speed": ("cool_fan_speed_max",),
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
    "speed_topbottom": ("speed_flooring",),
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

#: Wie ein Material beim Slicer heißt. Fast immer die Solidon-Kennung in
#: Großbuchstaben — nur wo die Schreibweisen auseinandergehen, steht ein
#: Eintrag. Ein unbekannter Typ ist kein Abbruch: der Slicer nimmt ihn als
#: eigenen Namen und rechnet mit den Vorgaben seiner Familie.
FILAMENT_TYPES: Final[dict[str, str]] = {"tpu-95a": "TPU"}


#: Die Materialart je Familie. PET und PETG bleiben verschiedene Materialien;
#: Prusas Bündel führen beide, flexible Filamente dagegen als FLEX.
FILAMENT_TYPES_BY_FLAVOUR: Final[dict[SlicerFlavour, dict[str, str]]] = {
    "prusa": {"TPU": "FLEX"},
}


def normalise_filament_type(material_type: str) -> str:
    """Eine native Materialart in Solidons familienübergreifende Schreibweise lesen."""
    wanted = material_type.strip().upper()
    for names in FILAMENT_TYPES_BY_FLAVOUR.values():
        for common, native in names.items():
            if wanted == native:
                return common
    return wanted


def filament_type(material_id: str, flavour: SlicerFlavour = "other") -> str:
    """Die Materialart schreiben; ohne Familie gilt die Schreibweise in Solidon."""
    common = normalise_filament_type(FILAMENT_TYPES.get(material_id, material_id))
    return FILAMENT_TYPES_BY_FLAVOUR.get(flavour, {}).get(common, common)


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
    "other": {},
}


def _entries(rows: tuple[Row, ...]) -> tuple[Entry, ...]:
    """Aus den Rohzeilen der Tabellen die benannten Einträge."""
    return tuple(Entry(*row) for row in rows)


TABLES: Final[dict[SlicerFlavour, tuple[Entry, ...]]] = {
    "prusa": _entries(PRUSA),
    "orca": _entries(ORCA),
    "cura": _entries(CURA),
    "other": (),
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
    # Was als Geometrie reist, hat keinen Wertschlüssel, aber einen Namen im
    # Slicer (:data:`GEOMETRY_KEYS`).
    seen += [key for key in GEOMETRY_KEYS.get(path, ()) if key not in seen]
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
    # Creality Print ab Version 6 ist ein Orca-Abkömmling: Profilbaum mit
    # ``machine_list``/``sub_path``, Filamente je Drucker, dieselben
    # Schlüsselnamen. Gemessen an Version 7.2 auf dieser Maschine findet
    # Solidon darin 4234 Profile — 459 Maschinen, 1240 Prozesse, 2535
    # Filamente — und die Übergabedatei ist dieselbe wie für OrcaSlicer.
    ("crealityprint", "orca"),
    ("creality-print", "orca"),
    # Anycubic Slicer Next baut auf OrcaSlicer auf: derselbe Profilbaum, nur
    # mit dem Hersteller Anycubic; Windows, macOS und das Linux-Paket nennen
    # die Programmdatei gleich.
    ("anycubicslicernext", "orca"),
    ("curaengine", "cura"),
    ("cura", "cura"),
)


def flavour_of(name: str) -> SlicerFlavour | None:
    """Welche Familie ein Programm dieses Namens ist, oder ``None``.

    Über den Dateinamen und nicht über einen Versionsaufruf: die Erkennung
    läuft auch, wenn das Programm gerade nicht startbar ist, und ein
    umbenanntes Programm ist ein Fall für die Einstellungen, nicht für eine
    Rateroutine.

    **Auch ohne Trenner verglichen**, wie :func:`program_of`: Bambu Studio
    verteilt sein AppImage als „Bambu_Studio_linux_….AppImage“, und mit dem
    Unterstrich fand keiner der Namen oben es — die Suche bot es an, gerechnet
    hat es nie (Review RM-601, 08.10.2026).
    """
    lowered = name.casefold()
    plain = "".join(character for character in lowered if character.isalnum())
    for fragment, flavour in FLAVOUR_BY_NAME:
        if fragment in lowered or fragment.replace("-", "") in plain:
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
            # Den Volumenstrom liest CuraEngine nicht; er wirkt nur über die
            # Tempi, die Solidon danach deckelt.
            "filament.max_flow",
        }
    ),
    "other": frozenset(),
}

#: Einstellungen, die nicht als Wert reisen, sondern als **Geometrie**
#: (``writer.write_assembly``) — die Messung über ``values_for`` sieht sie
#: deshalb nicht. ``support.block_channels`` und ``support.spare_ledges``
#: werden die Stützsperre: in der
#: 3MF-Baugruppe für PrusaSlicer und die Orca-Familie (:func:`helpers_as_parts`),
#: für CuraEngine als eigenes Netz mit ``anti_overhang_mesh``
#: (:func:`takes_mesh_settings`).
AS_GEOMETRY: Final[frozenset[str]] = frozenset({"support.block_channels", "support.spare_ledges"})

#: Die Namen, unter denen diese Geometrie im Slicer steht: die Teilart der
#: Orca-Familie, die Bereichsart von PrusaSlicer und Curas Netzwert. Die
#: Übergabe schreibt sie von hier, und die Suche im Druckdialog findet das
#: Feld unter ihnen (:func:`keys_for`) — wer aus seinem Slicer „support
#: blocker“ kennt, sucht danach.
ORCA_SUPPORT_BLOCKER: Final = "support_blocker"
PRUSA_SUPPORT_BLOCKER: Final = "SupportBlocker"
CURA_SUPPORT_BLOCKER: Final = "anti_overhang_mesh"
GEOMETRY_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "support.block_channels": (ORCA_SUPPORT_BLOCKER, CURA_SUPPORT_BLOCKER),
    "support.spare_ledges": (ORCA_SUPPORT_BLOCKER, CURA_SUPPORT_BLOCKER),
}


#: Einstellungen, die ankommen, aber je nach Wert nur angenähert. Dazu
#: nennt :func:`limitation` einen Satz, sobald der Wert wirklich abweicht —
#: nicht bei jeder Übergabe.
LIMITED: Final[dict[SlicerFlavour, frozenset[str]]] = {
    "prusa": frozenset(),
    "orca": frozenset(),
    "cura": frozenset({"cooling.disable_first_layers"}),
    "other": frozenset(),
}


#: Was ein **Programm** seiner Familie nicht kennt — Schlüssel der
#: Programmmarke (``discover.program_mark``). Gleiche Familie heißt nicht
#: gleicher Stand: SuperSlicer 2.5.59.13 kennt die Schrägnaht aus PrusaSlicer
#: 2.9 nicht, und sein 3MF-Leser stürzt ab zwei unbekannten Schlüsseln mit
#: 0xC0000005 ab (RM-459, gemessen je Schlüssel der Beilage).
NOT_TAKEN_BY_PROGRAM: Final[dict[str, frozenset[str]]] = {
    "superslicer": frozenset({"shell.scarf_seam"}),
}

#: Diese Programme lesen die Werte nur für die Platte. Gemessen mit zwei
#: Körpern, unverändertem Herstellerprofil und getrennten Bahnen (RM-317).
#: Ein fehlender Rollenwert ist keine fehlende Objektfähigkeit.
PLATE_ONLY_BY_PROGRAM: Final[dict[str, frozenset[str]]] = {
    "prusaslicer": frozenset(
        {
            "speed.acceleration",
            "speed.outer_wall_acceleration",
        }
    ),
    "superslicer": frozenset({"speed.acceleration", "speed.outer_wall_acceleration"}),
    "bambustudio": frozenset({"speed.acceleration", "speed.outer_wall_acceleration"}),
    # Die regulären Rollenbreiten gehen je Netz, der Erstschichtfaktor nur
    # je Extruder. Unterschiedliche Breiten würden die unabhängige absolute
    # Erstschichtbreite am anderen Körper verändern (Cura 5.13, RM-317).
    "cura": frozenset({"layers.line_width"}),
}

#: Eigene Druckbeschleunigungen überlagern die Grundbeschleunigung. Nur
#: vorhandene höhere Rollen werden begrenzt; Anfahrt und Leerfahrt bleiben
#: eigenständig. Eine ausdrücklich gewählte Außenwand bleibt ebenfalls eigen.
ACCELERATION_ROLES: Final[dict[SlicerFlavour, tuple[str, ...]]] = {
    "prusa": (
        "external_perimeter_acceleration",
        "perimeter_acceleration",
        "infill_acceleration",
        "solid_infill_acceleration",
        "top_solid_infill_acceleration",
        "bridge_acceleration",
        "support_material_acceleration",
        "support_material_interface_acceleration",
    ),
    "orca": (
        "outer_wall_acceleration",
        "inner_wall_acceleration",
        "sparse_infill_acceleration",
        "internal_solid_infill_acceleration",
        "top_surface_acceleration",
        "bridge_acceleration",
    ),
    "cura": (),
    "other": (),
}

#: Schlüssel, die ein Programm nur als alten Namen kennt, mit den heutigen —
#: die Konsole übersetzt sie, der 3MF-Leser von SuperSlicer nicht (RM-459).
#: ``external_fill_pattern`` steht in SuperSlicers eigenem Prusa-Bündel.
PROGRAM_ALIASES: Final[dict[str, dict[str, tuple[str, ...]]]] = {
    "superslicer": {"external_fill_pattern": ("top_fill_pattern", "bottom_fill_pattern")},
}


#: Bambu behält den Plural; die übrige Orca-Familie führt den Singular.
PROGRAM_KEYS: Final[dict[str, dict[str, str]]] = {
    "bambustudio": {"chamber_temperature": "chamber_temperatures"},
}


def native_key(key: str, program: str) -> str:
    """Der Schlüssel im Zielprogramm, auch für Profilgruppe und Gegenprobe."""
    return PROGRAM_KEYS.get(program, {}).get(key, key)


#: Was ein Programm annimmt, aber nicht in den Konfigurationsblock seiner
#: Druckdatei schreibt — je Programmmarke Schlüssel und die Werte, bei denen er
#: fehlt (``None``: immer). Die Gegenprobe meldet sonst „nicht übernommen“.
#: Gemessen im Konfigurationsblock: ``override_filament_scarf_seam_setting``
#: kennt nur Bambu Studio, die Verwandten schreiben ihre Nahtwerte unmittelbar
#: (03.10.2026; Anycubic Slicer Next 2.0.0.3 am 05.10.2026). Anycubic Slicer
#: Next führt ``ironing_type`` nur, wenn gebügelt wird; „no ironing“ nimmt es
#: an (``s_keys_map_IroningType``) und lässt die Zeile weg.
OMITTED_FROM_GCODE: Final[dict[str, dict[str, frozenset[str] | None]]] = {
    "orcaslicer": {"override_filament_scarf_seam_setting": None},
    "elegooslicer": {"override_filament_scarf_seam_setting": None},
    "crealityprint": {"override_filament_scarf_seam_setting": None},
    "anycubicslicernext": {
        "override_filament_scarf_seam_setting": None,
        "ironing_type": frozenset({"no ironing"}),
    },
}


#: Filamentschlüssel, die ein **Programm** zusätzlich je Düsenart führt. Beim
#: Schneiden ersetzt es den Grundwert durch die Fassung der Maschinendüse
#: (``nozzle_type``); fehlt sie oder ist sie leer, bleibt der Grundwert.
#: Anycubic Slicer Next 2.0.0.3 trägt genau diese zwölf Zeichenketten in
#: ``AnycubicSlicer.dll``, der öffentliche Quelltext und OrcaSlicer nicht.
#: Gemessen am 05.10.2026 im Konfigurationsblock: ``brass``, ``undefine`` und
#: eine Maschine ohne Angabe drucken ``_BRASS``, ``hardened_steel`` und
#: ``stainless_steel`` drucken ``_HS``; ein ``nil`` in der Fassung bricht den Lauf ab.
NOZZLE_KIND_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "anycubicslicernext": (
        "nozzle_temperature",
        "nozzle_temperature_initial_layer",
        "fan_max_speed",
        "fan_min_speed",
        "fan_cooling_layer_time",
        "slow_down_layer_time",
    ),
}

#: Die Fassungen je Programm und welche Düsenart sie druckt; ``None`` gilt für
#: jede Düse, die keine Fassung eigens nennt.
NOZZLE_KIND_SUFFIXES: Final[dict[str, dict[str, tuple[str | None, ...]]]] = {
    "anycubicslicernext": {
        "_BRASS": (None, "brass", "undefine"),
        "_HS": ("hardened_steel", "stainless_steel"),
    },
}


def nozzle_kind_keys(key: str, program: str) -> tuple[str, ...]:
    """Die Düsenart-Fassungen eines Filamentschlüssels — leer, wo das Programm keine führt."""
    if key not in NOZZLE_KIND_KEYS.get(program, ()):
        return ()
    return tuple(f"{key}{suffix}" for suffix in NOZZLE_KIND_SUFFIXES[program])


def printed_key(key: str, program: str, nozzle_type: str) -> str | None:
    """Die Fassung, die das Programm an dieser Maschinendüse statt ``key`` druckt."""
    if key not in NOZZLE_KIND_KEYS.get(program, ()):
        return None
    suffixes = NOZZLE_KIND_SUFFIXES[program]
    kind = nozzle_type.strip().casefold()
    chosen = next((suffix for suffix, kinds in suffixes.items() if kind in kinds), None)
    if chosen is None:
        chosen = next(suffix for suffix, kinds in suffixes.items() if None in kinds)
    return f"{key}{chosen}"


def for_the_nozzle(
    values: Mapping[str, object], program: str, nozzle_type: str
) -> dict[str, object]:
    """Die Filamentwerte, wie das Programm sie an dieser Düse druckt.

    Steht die Fassung der Maschinendüse da und ist nicht leer, gilt sie statt
    des Grundwerts — so liest die Grundlage den Wert, der gedruckt wird, und
    nicht Anycubics Platzhalter (Kobra S1 PLA: Grund 205 °C, Messing 210 °C).
    """
    result = dict(values)
    for key in NOZZLE_KIND_KEYS.get(program, ()):
        variant = printed_key(key, program, nozzle_type)
        value = values.get(variant) if variant is not None else None
        first = value[0] if isinstance(value, list) and value else value
        if first is None or isinstance(first, list) or str(first).strip() in ("", "nil"):
            continue
        result[key] = value
    return result


def with_nozzle_kinds(
    values: Mapping[str, object], program: str, own: Collection[str]
) -> dict[str, object]:
    """Die Düsenart-Fassungen, die den geschriebenen Grundwert tragen müssen.

    Ein eigener Wert (``own``) geht in jede Fassung. Sonst überstimmt die
    geerbte Fassung des Herstellers jede eigene oder übernommene Temperatur,
    Lüfter- und Schichtzeitwahl: Am Kobra S1 0,4 schrieb Solidon 235 °C, und
    der Slicer druckte die 210 °C der Messingdüse. Eine fehlende Fassung
    bekommt den Grundwert, den der Slicer ohnehin nähme; sonst füllte der
    Abgleich mehrerer Spulen sie mit dem Wert einer anderen Spule. Geerbte
    Fassungen bleiben, wie der Hersteller sie setzt.
    """
    return {
        variant: values[key]
        for key in NOZZLE_KIND_KEYS.get(program, ())
        if key in values
        for variant in nozzle_kind_keys(key, program)
        if key in own or variant not in values
    }


class ConsoleLimit(NamedTuple):
    """Was die Konsole eines Programms an einem Schlüssel annimmt."""

    lowest: float
    highest: float
    default: str
    """Die Vorgabe des Programms — was es nähme, wenn kein Profil den Schlüssel nennt."""
    nil: bool = False
    """Ob ``nil`` hier gilt (eine Gleitkommaoption, die das Programm leer erlaubt)."""


_ORCA_LIMITS: Final[dict[str, ConsoleLimit]] = {
    "retraction_distances_when_cut": ConsoleLimit(10.0, 18.0, "18"),
    "filament_flush_temp": ConsoleLimit(0.0, 1500.0, "0"),
    "extruder_printable_height": ConsoleLimit(0.0, 1000.0, "0"),
    "fan_max_speed": ConsoleLimit(0.0, 100.0, "100"),
    "tree_support_wall_count": ConsoleLimit(0.0, 2.0, "0"),
}

#: Grenzen, an denen die **Konsole** eines Programms die geladenen Werte prüft
#: (``DynamicPrintConfig::validate`` beim Start, „Param values in 3mf/config
#: error … not in range“), bei Bambu Studio mit Rückgabe -18. Das Fenster lädt
#: seine Systemprofile ungeprüft und eine 3MF mit der Warnung „Invalid values
#: found in the 3MF“ (OrcaSlicer 2.4.2, ``Plater::load_files``). Eine
#: Ganzzahlliste mit ``nil`` reißt jede Obergrenze; ``nil`` in einer
#: Gleitkommaoption nur, wo sie nicht leer sein darf.
#:
#: Aufgenommen ist, was Herstellerprofile der installierten Bestände wirklich
#: verletzen — Anycubic Kobra S1 Max (``retraction_distances_when_cut = 0``,
#: ``filament_flush_temp = nil``), Creality K2 und SPARKX i7 in Orca (28 und
#: 30), SeeMeCNC BOSSdelta (``extruder_printable_height = 2100``), E3NG-TPU
#: (``fan_max_speed = 1000``), Bambus ``tree_support_wall_count = -1`` in
#: Creality Print —, Grenzen und Vorgaben aus dem Quelltext des Programms, je
#: Wert an der Konsole gemessen (05.10.2026: OrcaSlicer 2.4.2, ElegooSlicer
#: 1.5.3, Bambu Studio 2.3, Creality Print 7.3). Anycubic Slicer Next 2.0.0.3
#: prüft nicht; es nahm jeden dieser Werte an.
CONSOLE_LIMITS: Final[dict[str, dict[str, ConsoleLimit]]] = {
    "orcaslicer": _ORCA_LIMITS,
    "elegooslicer": _ORCA_LIMITS,
    "bambustudio": {
        "retraction_distances_when_cut": ConsoleLimit(10.0, 18.0, "18", nil=True),
        "filament_flush_temp": ConsoleLimit(0.0, 1500.0, "0"),
        "extruder_printable_height": ConsoleLimit(0.0, 1000.0, "0", nil=True),
        "fan_max_speed": ConsoleLimit(0.0, 100.0, "100"),
        "tree_support_wall_count": ConsoleLimit(-1.0, 2.0, "-1"),
    },
    "crealityprint": {
        "retraction_distances_when_cut": ConsoleLimit(10.0, 30.0, "18"),
        "fan_max_speed": ConsoleLimit(0.0, 100.0, "100"),
        "tree_support_wall_count": ConsoleLimit(0.0, 2.0, "0"),
    },
}

#: Wie genau die Programme an der Grenze vergleichen (``is_value_valid``, vier Stellen).
_LIMIT_PRECISION: Final = 1e-4


def _console_takes(text: str, limit: ConsoleLimit) -> bool:
    """Ob die Konsole diesen einen Eintrag annimmt."""
    if text == "nil":
        return limit.nil
    try:
        number = float(text.rstrip("%"))
    except ValueError:
        return True
    if math.isnan(number):  # „nan“ liest das Programm als nil
        return limit.nil
    return limit.lowest - _LIMIT_PRECISION <= number <= limit.highest + _LIMIT_PRECISION


def console_replacements(
    values: Mapping[str, object], program: str
) -> dict[str, tuple[object, object]]:
    """Herstellerwerte, die die Konsole ablehnt, mit dem, was an ihrer Stelle hinausgeht.

    Ein abgelehnter Eintrag wird die Vorgabe des Programms — das, was es ohne
    die Angabe nähme; die übrigen Einträge einer Liste bleiben, die Länge
    auch. Schlüssel → (Herstellerwert, Ersatz).
    """
    replaced: dict[str, tuple[object, object]] = {}
    for key, limit in CONSOLE_LIMITS.get(program, {}).items():
        value = values.get(key)
        if value is None:
            continue
        entries = value if isinstance(value, list) else [value]
        fixed = [
            entry if _console_takes(str(entry).strip().strip('"'), limit) else limit.default
            for entry in entries
        ]
        if fixed != entries:
            replaced[key] = (value, fixed if isinstance(value, list) else fixed[0])
    return replaced


def omitted_from_gcode(key: str, value: str, program: str) -> bool:
    """Ob das Programm diesen Wert annimmt, ohne ihn in die Druckdatei zu schreiben."""
    values = OMITTED_FROM_GCODE.get(program, {})
    if key not in values:
        return False
    omitted = values[key]
    return omitted is None or value.strip().strip('"') in omitted


def normalise_chamber(values: Mapping[str, object], program: str) -> dict[str, object]:
    """Ein Kammername pro Profil, mit derselben Aliasfolge wie beim Slicer.

    Orcas alter Plural überschreibt beim Laden den Singular. Er wird vor
    Solidons Abweichungen aufgelöst, damit geerbte 0 °C keine eigene Wahl
    aushebeln. Listen bleiben vollständig, auch bei mehreren Spulen.
    """
    result = dict(values)
    native = native_key("chamber_temperature", program)
    value = result.pop("chamber_temperatures", result.get("chamber_temperature"))
    result.pop("chamber_temperature", None)
    if value is not None:
        result[native] = value
    return result


#: Aufzählungswerte, die ein **Programm** anders führt als seine Familie — je
#: Programmmarke, darunter Schlüssel des Slicers und geschriebener Wert → Wert
#: dieses Programms. Ein unbekannter Wert fällt im Slicer still auf seine
#: Vorgabe: ``rectilinear`` druckten Bambu Studio als ``cubic`` und Creality
#: Print als ``grid``, beide führen dieselben Linien als ``zig-zag``; Orca und
#: ElegooSlicer lesen ``zig-zag`` als ``rectilinear`` (RM-461). SuperSlicer
#: führt die nächstgelegene Naht als ``cost`` (RM-480).
#:
#: Gemessen am Bestand der installierten Fassung
#: (``tests/data/slicer_values.json``: Prusa-Familie über ``--help-fff``,
#: Orca-Familie über die Rundreise durch den Konfigurationsblock, Cura über
#: die Definitionen); der Wächter hält jede Aufzählungszeile dagegen.
PROGRAM_VALUES: Final[dict[str, dict[str, dict[str, str]]]] = {
    "superslicer": {"seam_position": {"nearest": "cost"}},
    "bambustudio": {"sparse_infill_pattern": {"rectilinear": "zig-zag"}},
    "crealityprint": {"sparse_infill_pattern": {"rectilinear": "zig-zag"}},
}


class Substitute(NamedTuple):
    """Was ein Programm statt einer Wahl druckt, die es nicht kennt — und der Satz dazu."""

    value: object
    reason: TranslatableText


#: Wahlen in Solidon, die ein **Programm** nicht kennt, mit dem, was es
#: stattdessen bekommt. Der Druckdialog bietet sie dort nicht an, der Rat
#: schlägt den Ersatz vor, und eine schon getroffene Wahl geht als Ersatz
#: hinaus, mit Hinweis (RM-480). SuperSlicer 2.5.59.13 kennt nur ``grid`` und
#: ``snug``; mit ``organic`` stürzte sein 3MF-Leser neben einem unbekannten
#: Schlüssel ab (``0xC0000005``), allein wurde still Gitter daraus — mit
#: PrusaSlicers unverbundenem Linienmuster statt Solidons Kreuzgitter.
NOT_OFFERED_BY_PROGRAM: Final[dict[str, dict[str, dict[object, Substitute]]]] = {
    "superslicer": {
        "support.style": {
            "tree": Substitute(
                "grid", _("SuperSlicer kennt keine Baumstützen und stützt mit Gitter.")
            ),
        },
    },
}


def substitute(path: str, value: object, program: str) -> Substitute | None:
    """Was dieses Programm statt dieser Wahl bekommt — ``None``, wenn es sie kennt."""
    return NOT_OFFERED_BY_PROGRAM.get(program, {}).get(path, {}).get(value)


def offered(advice: Sequence[SettingAdvice], program: str) -> list[SettingAdvice]:
    """Der Rat in den Wahlen, die dieses Programm kennt.

    Ein Vorschlag auf eine Wahl aus :data:`NOT_OFFERED_BY_PROGRAM` wird zu
    ihrem Ersatz — SuperSlicer bekommt statt der Baumstütze Gitter angeboten
    (RM-480). Ist der Ersatz schon eingestellt, bleibt nichts vorzuschlagen.
    """
    shown: list[SettingAdvice] = []
    for entry in advice:
        replaced = substitute(entry.path, entry.value, program)
        if replaced is None:
            shown.append(entry)
        elif replaced.value != entry.was:
            shown.append(replace(entry, value=replaced.value, reason=replaced.reason))
    return shown


def program_value(key: str, value: str, program: str) -> str:
    """Ein geschriebener Aufzählungswert in der Sprache dieses Programms.

    Die Übersetzung steht in :data:`PROGRAM_VALUES`; ohne Eintrag bleibt der
    Wert der Familie.
    """
    return PROGRAM_VALUES.get(program, {}).get(key, {}).get(value, value)


def program_of(executable: str | Path) -> str:
    """Die Programmmarke; ohne Treffer bleibt der bereinigte Dateiname stehen."""
    from app.core import discover

    name = Path(executable).name
    return discover.program_mark(name) if name else ""


def takes(flavour: SlicerFlavour, path: str, program: str = "") -> bool:
    """Nimmt dieser Slicer diese Einstellung überhaupt entgegen (§29)?

    Ein Feld, an dem man dreht, ohne dass etwas geschieht, ist eine Attrappe —
    und schlimmer noch ist ein **Vorschlag** darauf, denn er verspricht eine
    Wirkung. Die Oberfläche graut damit aus und begründet, statt den Kunden an
    einem Regler ziehen zu lassen, der bei seinem Slicer nichts tut.

    Die Antwort steht in :data:`NOT_TAKEN_BY` und ist gemessen; warum sie
    nicht aus den Tabellen kommen kann, steht dort. ``program`` ist die Marke
    des Programms (:func:`program_of`); was es seiner Familie nicht kennt,
    steht in :data:`NOT_TAKEN_BY_PROGRAM`. Ein Programm ohne Familie nimmt
    nichts entgegen — es bekommt die Datei und keinen Wert.
    """
    if flavour == "other":
        return False
    return path not in NOT_TAKEN_BY[flavour] | NOT_TAKEN_BY_PROGRAM.get(program, frozenset())


def for_program(values: Mapping[str, str], flavour: SlicerFlavour, program: str) -> dict[str, str]:
    """Die Schlüssel, die dieses Programm lesen kann (RM-459).

    Was es nicht kennt (:data:`NOT_TAKEN_BY_PROGRAM`), fällt heraus; ein alter
    Name (:data:`PROGRAM_ALIASES`) wird zu den heutigen, wo diese nicht schon
    stehen. Ein Abkömmling stürzt an einem fremden Schlüssel ab, statt ihn zu
    übergehen — die Beilage einer Schrägnaht genügte bei SuperSlicer.
    """
    dropped = NOT_TAKEN_BY_PROGRAM.get(program, frozenset())
    unknown = {entry.key for entry in TABLES[flavour] if entry.path in dropped}
    kept = {key: value for key, value in values.items() if key not in unknown}
    for old, new in PROGRAM_ALIASES.get(program, {}).items():
        if old not in kept:
            continue
        value = kept.pop(old)
        for key in new:
            kept.setdefault(key, value)
    return kept


def caps_volumetric_speed(flavour: SlicerFlavour) -> bool:
    """Deckelt dieser Slicer das Tempo selbst nach dem Volumenstrom des Filaments?

    PrusaSlicer und die Orca-Familie tun es mit dem Wert, den Solidon ihnen
    als ``filament_max_volumetric_speed`` schreibt: Jede Bahn fährt höchstens
    so schnell, wie das Filament fördert. Ein Tempodeckel als Vorschlag
    (``advise.limits_flow``) ändert dort nichts am Druck. Cura liest den Wert
    nicht (:data:`NOT_TAKEN_BY`) und deckelt nicht; dort ist der Vorschlag der
    einzige Deckel.
    """
    from app.core.knowledge.print_settings import caps_volumetric_speed as caps_flow

    return caps_flow(flavour)


def limitation(
    flavour: SlicerFlavour, path: str, settings: PrintSettings | None = None, program: str = ""
) -> TranslatableText | None:
    """Eine abweichende Bedeutung, die ein gleich benannter Wert verdecken würde.

    Cura hat für den Lüfter keine Abschaltphase, nur einen Hochlauf vom
    Anfangslüfter null (``handover._cura_fan_start``). Für null und eine
    Schicht ohne Lüfter ist das dieselbe Pause; ab zwei laufen die Schichten
    dazwischen schon an — nur dann gibt es vorher einen Satz. Dass Cura kurze
    Schichten auch in der Pause kühlt, zeigt erst die Druckdatei
    (``handover.fan_in_off_layers``); darum behauptet der Satz nicht, der
    Lüfter bleibe in Schicht 1 aus.

    Ebenso eine Wahl, die das Programm nicht kennt und ersetzt
    (:data:`NOT_OFFERED_BY_PROGRAM`) — der Satz kommt nur, solange sie steht.
    """
    if settings is not None and program:
        group, name = path.split(".", 1)
        replaced = substitute(path, getattr(getattr(settings, group), name), program)
        if replaced is not None:
            return replaced.reason
    if flavour == "cura" and path == "cooling.disable_first_layers":
        if settings is None or settings.cooling.disable_first_layers < 2:
            return None
        return _(
            "Cura kennt keine Lüfterpause und fährt den Lüfter bis Schicht {layer} "
            "schrittweise hoch.",
            layer=settings.cooling.disable_first_layers + 1,
        )
    return None


def arranges_on_cli(flavour: SlicerFlavour, program: str = "") -> bool:
    """Ordnet die Konsole dieses Programms eine ungeordnete Platte selbst an?

    Die vier Orca-Programme tun es. PrusaSlicer, SuperSlicer und CuraEngine
    brauchen eine fertige Anordnung. Ohne Programmmarke gilt die Familie.
    """
    programs = {
        "orcaslicer": True,
        "bambustudio": True,
        "elegooslicer": True,
        "crealityprint": True,
        "prusaslicer": False,
        "superslicer": False,
        "cura": False,
    }
    return programs.get(program, flavour == "orca")


def wants_bed_coordinates(flavour: SlicerFlavour) -> bool:
    """Schreibt diese Familie G-Code mit dem Ursprung an der Bettecke?

    Die Gegenprobe prüft Maschinenkoordinaten. Die Verschiebung der
    Eingabegeometrie ist davon getrennt: CuraEngine führt sie selbst aus.
    Eine einzelne Cura-Maschine kann ihren Ursprung in die Bettmitte legen
    (``machine_center_is_zero``); das ist eine Eigenschaft der Maschine, nicht
    der Familie, und reist als ``handover.CuraMachine.origin_at_centre``.
    """
    return True


def needs_bed_translation(flavour: SlicerFlavour) -> bool:
    """Muss Solidon die Eingabe vor der Übergabe zur Bettecke verschieben?

    CuraEngine verschiebt ein zentriertes STL selbst um die halbe Bettgröße;
    Prusa- und Orca-Projekte erhalten bereits Maschinenkoordinaten. Ein
    Programm, das Solidon nur öffnet, bekommt die Teile um den Ursprung: Es
    ordnet beim Laden selbst an, und ein Bauraum, den Solidon nicht kennt,
    hat auch keine Ecke, zu der sich verschieben ließe.
    """
    return flavour not in {"cura", "other"}


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
    """Trifft für diese Familie beides zu: eigenes Maschinenprofil, zwei Dateien?

    Zwei Fragen fallen hier zusammen, und nur, weil bislang eine einzige
    Familie beide bejaht:

    1. **Lädt der Slicer seine Maschine als eigenes Profil aus seinem
       Bestand?** Nur die Orca-Familie, und aus demselben Grund wie bei
       :func:`has_filament_profiles`: Dort ist die Maschine eine Datei, die
       Startcode, Schichtwechselcode und Maschinengrenzen trägt — Angaben, die
       nur der Hersteller kennt und die Solidon nicht erfindet.
    2. **Kommt die Konfiguration als Maschinen- plus Prozessdatei, statt als
       eine einzige?** So fragt ``handover.py`` an den Aufrufstellen in
       :func:`write_config` und :func:`_command`: Dort entsteht neben der
       Prozessdatei eine zweite — ``solidon_machine.json``, geschrieben aus
       :func:`_orca_machine` mit **Solidons eigenen** Werten, ausgeschrieben
       statt geerbt, nicht das Profil des Herstellers —, und die Kommandozeile
       reicht beide zusammen mit einem Semikolon getrennt weiter.

    PrusaSlicer bekommt seine Maschine aus dem Druckerprofil seines Bündels,
    aufgelöst in dieselbe eine ``.ini`` wie Prozess und Filament
    (``handover.prusa_values``); ohne Druckerprofil schreibt Solidon Bauraum,
    Düse und Bettform selbst (:func:`_machine_keys`) — eine Datei, keine
    zwei. Cura bekommt seine aus einer Druckerdefinition seiner Installation
    (:func:`machine_from_definition`).

    **Beide Fragen fallen heute zusammen, aber nicht aus Notwendigkeit:** Eine
    künftige Familie mit eigenem Maschinenbestand, aber einer einzigen
    Konfigurationsdatei (etwa Maschine und Prozess in einem Dokument
    zusammengefasst), bejahte die erste und verneinte die zweite. Käme sie
    hinzu, trennte sich dieses Prädikat in zwei — eines für den Bestand,
    eines für die Dateizahl.
    """
    return flavour == "orca"


def machine_from_definition(flavour: SlicerFlavour) -> bool:
    """Kommt die Maschine dieses Slicers aus einer Druckerdefinition seiner Installation?

    Nur bei CuraEngine. Solidon wählt dort die Definition des Druckers
    (``PrinterProfile.cura_definition``), CuraEngine löst ihre Erbkette
    selbst auf, und Start- und Endcode kommen mit gefüllten Platzhaltern als
    eigene Werte dazu (``handover._cura_machine``). Führt die Installation den
    Drucker nicht, bleibt es bei ``fdmprinter`` — und das ist ein Mangel, den
    ``handover.machine_missing`` benennt: Der Druck beginnt ohne den Startcode
    des Herstellers, ohne Spüllinie und ohne Bettnetz.

    Die Orca-Familie lädt ihre Maschine als Profil
    (:func:`takes_a_machine_profile`), PrusaSlicer bekommt sie aus seinem
    Bündel in Solidons ``.ini``.
    """
    return flavour == "cura"


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

    Für ``prusa`` seit Stufe C des Konzepts Herstellerprofil: Drucker, Prozess
    und Filament kommen aus seinen Bündeln, und ohne sie druckte PrusaSlicer
    mit seinen eingebauten Vorgaben — ohne Bettvermessung und Spüllinie. Für
    ``other`` nicht — Solidon kennt den Bestand dieses Programms nicht und
    liest ihn nicht.
    """
    return flavour in {"orca", "prusa", "cura"}


def reads_assembly_file(flavour: SlicerFlavour) -> bool:
    """Liest dieser Slicer eine 3MF-Baugruppe — mit Namen und Materialslots?

    ``CuraEngine`` nicht. Die 3MF-Seite von Cura sitzt in seinem Fenster, nicht
    in der Rechenmaschine dahinter, und ein übergebenes 3MF endete dort in „Der
    Slicer hat keine Druckdatei geschrieben", ohne dass irgendwo stand, warum.
    Es bekommt ein STL mit allen Teilen der Platte; Namen und Materialslots
    liest es ohnehin nicht, und seine Einstellungen kommen über die
    Kommandozeile.

    Ein Programm, das Solidon nur öffnet, bekommt aus demselben Grund STL:
    Es ist das eine Format, das jeder Slicer liest — auch der rudimentäre
    Hersteller-Slicer eines Resin-Druckers, dessen 3MF-Seite niemand kennt.
    """
    return flavour not in {"cura", "other"}


def helpers_as_parts(flavour: SlicerFlavour) -> bool:
    """Liest dieser Slicer ein Hilfsteil wie die Stützsperre als eigenes Teil?

    Zwei Schreibweisen für dieselbe Sache, und jede Familie liest nur ihre:
    Die Orca-Familie führt es als Komponente, die ``model_settings.config``
    als ``support_blocker`` nennt; PrusaSlicer als Dreiecksbereich im Netz des
    Objekts, den ``Slic3r_PE_model.config`` benennt. Gemessen an der
    Waschschüssel (26.09.2026): Mit dem Bereich druckte der ElegooSlicer die
    Sperre als Kunststoff (+22,8 g), mit der Komponente PrusaSlicer (+38,8 g);
    in der eigenen Schreibweise blieb die Modellbahn gleich (ElegooSlicer
    bitgleich, PrusaSlicer auf 0,1 %).
    """
    return flavour == "orca"


def takes_mesh_settings(flavour: SlicerFlavour) -> bool:
    """Bekommt dieser Slicer jedes Teil als eigenes Netz, mit Werten nur für dieses Netz?

    Nur CuraEngine: Ein ``-s`` nach ``-l`` gilt dem zuletzt geladenen Netz
    (``CommandLine.cpp``). So reist die Stützsperre als eigenes Netz mit
    ``anti_overhang_mesh`` — gemessen im Prüfbericht Cura (Abschnitt 1.5): 18 476
    Stützbewegungen wurden 0, die Modellbahn blieb gleich —, und Stufe E des
    Konzepts setzt dort ``support_enable`` je Teil. Die Orca-Familie und
    PrusaSlicer tragen dasselbe in ihrer 3MF-Beilage (:func:`helpers_as_parts`).
    """
    return flavour == "cura"


def knows_plates(flavour: SlicerFlavour) -> bool:
    """Trägt eine Projektdatei dieser Familie mehrere Druckplatten?

    Die Orca-Familie: je Platte ein ``plate``-Block in ``model_settings.config``
    und die Teile plattenweise im Raster (``threemf.plate_origin``) — so
    schreibt sie ihre eigenen Projekte, und so liest sie eine von Solidon.
    PrusaSlicer und Cura kennen eine Platte je Datei: Für sie bleibt es bei
    einer Datei je Platte.

    **Der Anlass** (Robert, 11.09.2026: „jede platte öffnet ein weiteres
    Slicerfenster, statt alle platten in einem zum öffnen"): Vier Platten
    hießen vier Dateien und vier Fenster des ElegooSlicers — und die vier
    Starts auf einmal rissen sich um dieselbe Filamentbibliothek, bis einer
    mit „remove_all: Zugriff verweigert" abbrach.
    """
    return flavour == "orca"


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
