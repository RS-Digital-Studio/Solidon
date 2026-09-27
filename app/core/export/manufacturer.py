"""Was der Hersteller vorgibt — die Grundlage jeder Übergabe (Bauplan §29).

**Konzept Herstellerprofil, 27.09.2026.** Solidon schreibt dem Slicer nur, was
vom Profil des Herstellers abweichen soll: die eigene Wahl des Kunden, den
übernommenen Vorschlag, das technisch Nötige. Damit der Druckdialog, der
Prüfbericht und die Vorschläge trotzdem mit dem rechnen, **was gedruckt
wird**, liest dieses Modul das gewählte Herstellerprofil in Solidons Felder
zurück — die Gegenrichtung zu :mod:`app.core.export.slicer_keys`.

Bis dahin rechnete Solidon mit seiner eigenen Stufe und schrieb sie über das
Profil des Herstellers: am Centauri Carbon 2 drei statt zwei Wände, Gitter
statt Baum, kein Auto-Brim, 45 statt 60 Grad Stützwinkel. Roberts
Minigolf-Druck bekam davon einen Stützfuß in Schicht 1.

Was sich nicht übersetzen lässt, wird nicht umgedeutet. Ein Füllmuster wie
``crosshatch`` hat in Solidon keinen Namen; die Grundlage behält dann
Solidons Wert *für die eigene Rechnung*, :attr:`Foundation.foreign` nennt den
Herstellerwert für die Anzeige, und geschrieben wird er nicht — der Slicer
druckt, was sein Profil sagt.

Für die Orca-Familie aus Maschine, Prozess und Filament des Herstellers, für
PrusaSlicer aus Drucker, Prozess und Filament seines Bündels
(:func:`prusa_chain`); CuraEngine bleibt bei Solidons Tabellen (Konzept,
Entscheidung C).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from app.core import discover
from app.core.errors import OPEN_PRINT_SETTINGS, ExternalToolError
from app.core.export import slicer_keys, slicer_profiles
from app.core.knowledge import print_settings as settings_table
from app.core.log import get_logger
from app.core.types import Finding, PrintSettings, Profile, QualityPreset
from app.core.units import exact_atan_degrees, is_zero
from app.i18n import _

if TYPE_CHECKING:
    from app.core.export.handover import SlicerSetup

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Foreign:
    """Ein Herstellerwert, für den Solidon keinen Namen hat — gezeigt, nicht
    übersetzt und nicht geschrieben."""

    raw: str


@dataclass(frozen=True, slots=True)
class Foundation:
    """Die Grundlage einer Übergabe und woher sie kommt."""

    settings: PrintSettings
    """Ein vollständiger Satz: das Herstellerprofil, wo es etwas sagt, sonst
    Solidons Tabellen. ``chosen`` und ``accepted`` sind leer."""
    from_profile: frozenset[str] = frozenset()
    """Die Punktpfade, die aus dem Herstellerprofil kommen — die übrigen sind
    Solidons Rückfall. Leer heißt: keine Herstellergrundlage."""
    foreign: Mapping[str, str] = field(default_factory=dict)
    """Punktpfad → Herstellerwert, den Solidon nicht übersetzen kann."""
    measured: Mapping[str, object] = field(default_factory=dict)
    """Was der Kunde an seinem Drucker gemessen hat (§28.3) und deshalb
    geschrieben wird wie eine eigene Wahl — heute der Überhangwinkel."""
    staged: frozenset[str] = frozenset()
    """Was die gewählte Stufe über den Standardprozess legt (:data:`STAGE_PATHS`)
    und deshalb geschrieben wird — „Fein" heißt 0,12 mm, auch wenn darunter
    Elegoos 0,20-mm-Prozess liegt (Entscheidung I, Rückfall)."""
    machine: str = ""
    process: str = ""
    filament: str = ""
    plate: str = ""
    """Die Druckplatte, für die die Betttemperatur gelesen wurde — der Name,
    wie die Orca-Familie ihn schreibt (``Textured PEI Plate``)."""
    plate_refuses_filament: bool = False
    """Der Hersteller nennt für diese Platte und dieses Filament 0 °C: Die
    Platte ist dafür nicht freigegeben (Orca ``Print.cpp``: „does not support
    filament")."""
    plates: Mapping[str, int] = field(default_factory=dict)
    """Die Platten, für die das Filament eine Betttemperatur nennt — Name wie
    die Orca-Familie ihn schreibt, Temperatur in °C, 0 heißt gesperrt. Die
    Auswahl im Druckdialog (Konzept, Entscheidung F)."""
    unreadable: str = ""
    """Ein gewähltes Prozessprofil, das sich nicht lesen ließ — dann ist die
    Grundlage Solidons Tabelle, und der Kunde erfährt es
    (:func:`findings`; Review Stufe A+B, H13)."""
    has_plates: bool = True
    """Kennt der Slicer Druckplatten mit eigener Betttemperatur? PrusaSlicer
    nicht: Dort steht die Betttemperatur am Filament, und eine Platte, die
    niemand nennt, ist kein Mangel."""

    @property
    def has_profile(self) -> bool:
        """Liegt ein Herstellerprofil darunter — oder nur Solidons Tabelle?"""
        return bool(self.from_profile)


# --- Lesen ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Context:
    """Was eine relative Angabe braucht: die Düse für Bahnbreiten in Prozent."""

    nozzle: float


Reader = Callable[[str, _Context], object]
"""Liest einen Rohwert: der Wert, :class:`Foreign` oder ``None`` für „nichts"."""


def _text(raw: object) -> str | None:
    """Ein Rohwert als Text; eine Liste gibt ihren ersten Eintrag, ``nil`` nichts."""
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if raw is None:
        return None
    text = str(raw).strip()
    return None if text in ("", "nil") else text


def _float(text: str) -> float | None:
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _number(text: str, _context: _Context) -> object:
    number = _float(text)
    return Foreign(text) if number is None else number


def _positive(text: str, _context: _Context) -> object:
    """Eine Zahl über null. Null heißt bei Tempo und Beschleunigung „wie die
    Maschine" — eine Angabe, die Solidon nicht als Zahl führt."""
    number = _float(text)
    return number if number is not None and number > 0.0 else Foreign(text)


def _count(text: str, _context: _Context) -> object:
    number = _float(text)
    if number is None or number < 0.0 or not number.is_integer():
        return Foreign(text)
    return int(number)


def _fraction(text: str, _context: _Context) -> object:
    """„15%" als Anteil 0,15."""
    number = _float(text.rstrip("%").strip())
    if number is None or not 0.0 <= number <= 100.0:
        return Foreign(text)
    return number / 100.0


def _width(text: str, context: _Context) -> object:
    """Eine Bahnbreite in Millimetern oder in Prozent der Düse; null heißt
    „wie die allgemeine" und ist keine eigene Angabe."""
    if text.endswith("%"):
        share = _float(text[:-1].strip())
        if share is None or share <= 0.0:
            return None
        return context.nozzle * share / 100.0
    number = _float(text)
    if number is None:
        return Foreign(text)
    return number if number > 0.0 else None


def _flag(text: str, _context: _Context) -> object:
    lowered = text.casefold()
    if lowered in ("1", "true"):
        return True
    if lowered in ("0", "false"):
        return False
    return Foreign(text)


def _choice(table: Mapping[str, object]) -> Reader:
    def read(text: str, _context: _Context) -> object:
        return table[text] if text in table else Foreign(text)

    return read


#: Füllmuster zurück: die Umkehrung von ``slicer_keys._ORCA_INFILL``.
_ORCA_INFILL_BACK: Final = {orca: solidon for solidon, orca in slicer_keys._ORCA_INFILL.items()}

#: Die Orca-Prozessschlüssel und ihre Solidon-Pfade — die Tabelle
#: ``slicer_keys.ORCA`` rückwärts, mit den Umrechnungen der Schreibseite.
#: Stützart, Stützwinkel, Stützdichte und Haftungsart hängen an mehreren
#: Schlüsseln und stehen deshalb darunter in eigenen Funktionen.
ORCA_PROCESS: Final[tuple[tuple[str, str, Reader], ...]] = (
    ("layers.layer_height", "layer_height", _positive),
    ("layers.first_layer_height", "initial_layer_print_height", _positive),
    ("layers.line_width", "line_width", _width),
    ("layers.first_layer_line_width", "initial_layer_line_width", _width),
    ("shell.wall_count", "wall_loops", _count),
    ("shell.top_layers", "top_shell_layers", _count),
    ("shell.bottom_layers", "bottom_shell_layers", _count),
    (
        "shell.outer_wall_first",
        "wall_sequence",
        _choice({"outer wall/inner wall": True, "inner wall/outer wall": False}),
    ),
    (
        "shell.seam_position",
        "seam_position",
        _choice({"aligned": "aligned", "nearest": "nearest", "random": "random", "back": "rear"}),
    ),
    (
        "shell.wall_generator",
        "wall_generator",
        _choice({"classic": "classic", "arachne": "arachne"}),
    ),
    ("shell.precise_outer_wall", "precise_outer_wall", _flag),
    ("shell.ironing", "ironing_type", _choice({"no ironing": False, "top": True})),
    ("infill.density", "sparse_infill_density", _fraction),
    ("infill.pattern", "sparse_infill_pattern", _choice(_ORCA_INFILL_BACK)),
    ("infill.angle", "infill_direction", _number),
    ("speed.outer_wall", "outer_wall_speed", _positive),
    ("speed.inner_wall", "inner_wall_speed", _positive),
    ("speed.infill", "sparse_infill_speed", _positive),
    ("speed.top_surface", "top_surface_speed", _positive),
    ("speed.travel", "travel_speed", _positive),
    ("speed.bridge", "bridge_speed", _positive),
    ("speed.acceleration", "default_acceleration", _positive),
    ("speed.outer_wall_acceleration", "outer_wall_acceleration", _positive),
    (
        "support.placement",
        "support_on_build_plate_only",
        _choice({"1": "build_plate", "0": "everywhere"}),
    ),
    ("support.z_gap", "support_top_z_distance", _number),
    ("support.interface_layers", "support_interface_top_layers", _count),
    ("adhesion.skirt_loops", "skirt_loops", _count),
    ("adhesion.skirt_distance", "skirt_distance", _number),
    ("adhesion.brim_width", "brim_width", _number),
    ("adhesion.raft_layers", "raft_layers", _count),
    ("retraction.avoid_crossing_walls", "reduce_crossing_wall", _flag),
)

#: Was die Programme der Orca-Familie einsetzen, wo die Kette des Herstellers
#: einen übersetzten Schlüssel nicht nennt. **Gemessen, nicht erinnert**: ein
#: Konsolenlauf je Programm mit vollständiger Maschine und Filament des
#: Herstellers und leerem Prozess, abgelesen im Konfigurationsblock des
#: G-Codes (27.09.2026; ElegooSlicer 1.5.3.4, OrcaSlicer 2.4.2, Bambu Studio
#: 02.08.02.61, Creality Print 7.2). Gefehlt haben in den Ketten der zwölf
#: zugeordneten Drucker nur diese vier; die übrigen Vorgaben stehen in jeder.
#: Bemerkenswert: ``wall_generator`` ist überall ``arachne`` — wer ``classic``
#: fährt, setzt es in seinem Profil.
PROGRAM_DEFAULTS: Final[Mapping[str, Mapping[str, str]]] = {
    "elegooslicer": {
        "brim_type": "auto_brim",
        "precise_outer_wall": "1",
        "wall_generator": "arachne",
        "wall_sequence": "inner wall/outer wall",
    },
    "orcaslicer": {
        "brim_type": "auto_brim",
        "precise_outer_wall": "1",
        "wall_generator": "arachne",
        "wall_sequence": "inner wall/outer wall",
    },
    "bambustudio": {
        "brim_type": "auto_brim",
        "precise_outer_wall": "0",
        "wall_generator": "arachne",
        "wall_sequence": "inner wall/outer wall",
    },
    "crealityprint": {
        "brim_type": "auto_brim",
        "precise_outer_wall": "0",
        "wall_generator": "arachne",
        "wall_sequence": "inner wall/outer wall",
    },
}

#: Welche Temperatur zu welcher Druckplatte gehört, wie die Orca-Familie sie
#: nennt. Creality Print kennt zusätzlich die Epoxidplatte.
PLATE_TEMPERATURES: Final[Mapping[str, str]] = {
    "Cool Plate": "cool_plate_temp",
    "Engineering Plate": "eng_plate_temp",
    "High Temp Plate": "hot_plate_temp",
    "Textured PEI Plate": "textured_plate_temp",
    "Supertack Plate": "supertack_plate_temp",
    "Textured Cool Plate": "textured_cool_plate_temp",
    "Epoxy Resin Plate": "epoxy_resin_plate_temp",
}

#: ``default_bed_type`` als Nummer führt nur Elegoo, und belegt ist nur „4":
#: Alle 34 mit ElegooSlicer 1.5.x gespeicherten Centauri-Projekte in
#: ``F:\\3D Dateien`` tragen ``curr_bed_type = Textured PEI Plate``, fünf davon
#: zusammen mit ``default_bed_type = 4`` (27.09.2026). Eine andere Nummer ist
#: nicht belegt und wird nicht geraten (Regel 21) — die übrigen Hersteller
#: schreiben den Namen.
_PLATE_NUMBERS: Final[Mapping[str, str]] = {"4": "Textured PEI Plate"}

#: Die Platte der Konsole, wenn niemand eine nennt — gemessen wie
#: :data:`PROGRAM_DEFAULTS`. Das Fenster nimmt die Standardplatte der Maschine,
#: die Konsole nicht; darum schreibt die Übergabe sie immer.
CONSOLE_PLATE: Final = "Cool Plate"

#: Die Platte eines Druckers, der keine Standardplatte nennt — weder im Profil
#: noch im Modell. Das sind die Geräte ohne Plattenwahl
#: (``support_multi_bed_types`` fehlt): Neptune 4, SV06, Kobra 2, die
#: Prusa-Geräte in Orca. Ihre Hersteller setzen im Filament **nur**
#: ``hot_plate_temp`` — alle 31 Filamente von Sovol im Orca-Bestand, keines
#: eine andere Platte (27.09.2026). Mit der Konsolenvorgabe „Cool Plate" druckte
#: ein SV06 PLA auf 35 °C.
SINGLE_PLATE: Final = "High Temp Plate"


def program(setup: SlicerSetup) -> str:
    """Welches Programm der Orca-Familie das ist, als Schlüssel für
    :data:`PROGRAM_DEFAULTS`."""
    return discover.program_mark(setup.executable.name)


def plate_name(value: object) -> str:
    """Eine Plattenangabe als Name: der Name selbst, oder Elegoos Nummer."""
    text = _text(value) or ""
    if text in PLATE_TEMPERATURES:
        return text
    return _PLATE_NUMBERS.get(text, "")


def offers_plates(machine: Mapping[str, Any], model: Mapping[str, Any] | None = None) -> bool:
    """Hat der Drucker eine Plattenwahl (``support_multi_bed_types``)?

    Nur ein Drucker ohne sie hat die eine Betttemperatur :data:`SINGLE_PLATE`.
    Einer mit Wahl, dessen Standardplatte niemand nennt, bekommt keine geratene
    (Regel 21), sondern einen Befund (:func:`findings`).
    """
    for source in (machine, model or {}):
        text = (_text(source.get("support_multi_bed_types")) or "").casefold()
        if text in ("1", "true"):
            return True
    return False


def plate_temperatures(filament: Mapping[str, Any]) -> dict[str, int]:
    """Je Platte die Betttemperatur, die das Filament nennt — 0 heißt gesperrt."""
    found: dict[str, int] = {}
    for plate, key in PLATE_TEMPERATURES.items():
        text = _text(filament.get(key))
        number = _float(text) if text is not None else None
        if number is not None:
            found[plate] = max(0, round(number))
    return found


def default_plate(machine: Mapping[str, Any], model: Mapping[str, Any] | None = None) -> str:
    """Die Standardplatte einer Maschine — aus ihrem Profil, sonst aus ihrem Modell.

    Elegoo schreibt ``default_bed_type`` in das Maschinenprofil, Bambu in die
    Modelldatei daneben (``"type": "machine_model"``). Wer nur die Kette des
    Profils liest, findet bei Bambu nichts und nähme die Konsolenvorgabe —
    die kalte „Cool Plate".
    """
    found = plate_name(machine.get("default_bed_type"))
    if not found and model is not None:
        found = plate_name(model.get("default_bed_type"))
    return found


def _machine_model(
    machine_file: Path, model_name: str, roots: tuple[Path, ...] = ()
) -> dict[str, Any]:
    """Die Modelldatei zu einem Maschinenprofil — im Herstellerordner daneben,
    sonst irgendwo im Bestand.

    Eine eigene Vorlage liegt unter ``user/``, das Modell ihres Druckers beim
    Hersteller. Gesucht nur neben der Vorlage, fand Solidon für „Mein P1S" keine
    Standardplatte und riet die glatte (Review Stufe A+B, R4).
    """
    if not model_name:
        return {}
    beside = _machine_model_beside(machine_file, model_name)
    if beside:
        return beside
    for folder in roots:
        for candidate in sorted(folder.glob("*/machine/**/*.json")):
            if candidate.stem != model_name:
                continue
            loaded = slicer_profiles._load(candidate)
            if (
                loaded is not None
                and loaded.get("type") == "machine_model"
                and loaded.get("name") == model_name
            ):
                return loaded
    return {}


def _machine_model_beside(machine_file: Path, model_name: str) -> dict[str, Any]:
    """Die Modelldatei im Maschinenordner neben dem Profil."""
    for parent in machine_file.parents:
        if parent.name.casefold() != "machine":
            continue
        for candidate in sorted(parent.glob("*.json")):
            loaded = slicer_profiles._load(candidate)
            if (
                loaded is not None
                and loaded.get("type") == "machine_model"
                and loaded.get("name") == model_name
            ):
                return loaded
        break
    return {}


def _read_process(
    values: Mapping[str, Any], context: _Context, defaults: Mapping[str, str]
) -> tuple[dict[str, object], dict[str, str]]:
    """Die Prozesswerte in Solidons Pfaden, dazu, was sich nicht übersetzen ließ."""
    read: dict[str, object] = {}
    foreign: dict[str, str] = {}
    for path, key, reader in ORCA_PROCESS:
        text = _text(values.get(key))
        if text is None:
            text = defaults.get(key)
        if text is None:
            continue
        value = reader(text, context)
        if isinstance(value, Foreign):
            foreign[path] = value.raw
        elif value is not None:
            read[path] = value
    first = _first_layer_speed(values, context)
    if isinstance(first, Foreign):
        foreign["speed.first_layer"] = first.raw
    elif first is not None:
        read["speed.first_layer"] = first
    style = _support_style(values)
    if style is not None:
        read["support.style"] = style
    angle = _support_angle(values)
    if angle is not None:
        read["support.threshold_angle"] = angle
    kind = _adhesion(values, defaults)
    if isinstance(kind, Foreign):
        foreign["adhesion.kind"] = kind.raw
    elif kind is not None:
        read["adhesion.kind"] = kind
    gap = _support_gap(values, read, context)
    if gap is not None:
        read["support.xy_gap"] = gap
    density = _support_density(values, read, context)
    if density is not None:
        read["support.density"] = density
    return read, foreign


def _first_layer_speed(values: Mapping[str, Any], context: _Context) -> object:
    """Das Tempo der ersten Schicht, wie sie gedruckt wird: das schnellere aus
    Wänden (``initial_layer_speed``) und Füllung (``initial_layer_infill_speed``).

    Solidons Feld schreibt beide (``slicer_keys``). Läse es nur die Wände,
    stünde am Centauri Carbon 2 „50 mm/s“ im Dialog, während der Boden mit 105
    läuft — und wer dann 50 einstellt, änderte nichts, weil der Wert schon
    dasteht. Ist keiner der beiden eine Zahl, bleibt der Wert fremd
    (:class:`Foreign`) wie jeder andere, der sich nicht übersetzen lässt.
    """
    found = [
        _positive(text, context)
        for key in ("initial_layer_speed", "initial_layer_infill_speed")
        if (text := _text(values.get(key))) is not None
    ]
    speeds = [value for value in found if isinstance(value, float)]
    if speeds:
        return max(speeds)
    return next((value for value in found if isinstance(value, Foreign)), None)


def _support_style(values: Mapping[str, Any]) -> str | None:
    """Stützen aus, oder an in der Art des Profils."""
    enabled = _text(values.get("enable_support"))
    if enabled is None:
        return None
    if enabled.casefold() in ("0", "false"):
        return "none"
    kind = (_text(values.get("support_type")) or "").casefold()
    if kind.startswith("tree"):
        return "tree"
    if kind.startswith("normal"):
        return "grid"
    return "auto"


def _support_angle(values: Mapping[str, Any]) -> float | None:
    """Der Stützwinkel gegen die Senkrechte — Orca zählt gegen die Waagerechte.

    Null heißt bei Orca: Normalstützen nehmen ``support_threshold_overlap``
    statt eines Winkels, Baumstützen fallen auf 30 zurück (``PrintConfig.cpp``).
    Für den Baum ist das eine Zahl; für die Normalstütze keine, die Solidon
    als Winkel führen könnte — dann bleibt die Grenze des Druckers.
    """
    text = _text(values.get("support_threshold_angle"))
    number = _float(text) if text is not None else None
    if number is None or not 0.0 <= number < 90.0:
        return None
    if is_zero(number):
        kind = (_text(values.get("support_type")) or "").casefold()
        return 60.0 if kind.startswith("tree") else None
    return 90.0 - number


def _adhesion(values: Mapping[str, Any], defaults: Mapping[str, str]) -> object:
    """Die Haftungsart aus ``brim_type``, Skirt- und Raft-Angaben."""
    kind = _text(values.get("brim_type")) or defaults.get("brim_type")
    if kind is None:
        return None
    if kind == "auto_brim":
        return "auto"
    if kind in ("outer_only", "inner_only", "outer_and_inner"):
        return "brim"
    if kind == "no_brim":
        raft = _float(_text(values.get("raft_layers")) or "0") or 0.0
        if raft > 0.0:
            return "raft"
        skirts = _float(_text(values.get("skirt_loops")) or "0") or 0.0
        return "skirt" if skirts > 0.0 else "none"
    return Foreign(kind)


def _support_gap(
    values: Mapping[str, Any], read: Mapping[str, object], context: _Context
) -> float | None:
    """Der seitliche Abstand in Millimetern; Anycubic und Sovol nennen ihn in
    Prozent der Bahnbreite."""
    text = _text(values.get("support_object_xy_distance"))
    if text is None:
        return None
    if text.endswith("%"):
        share = _float(text[:-1].strip())
        width = read.get("layers.line_width")
        base = float(width) if isinstance(width, int | float) else context.nozzle
        return None if share is None else base * share / 100.0
    return _float(text)


def _support_density(
    values: Mapping[str, Any], read: Mapping[str, object], context: _Context
) -> float | None:
    """Die Stützdichte aus dem Linienabstand — die Umkehrung von
    ``handover._support_spacing`` (Abstand = Bahnbreite / Dichte)."""
    text = _text(values.get("support_base_pattern_spacing"))
    spacing = _float(text) if text is not None else None
    if spacing is None or spacing < 0.0:
        return None
    if is_zero(spacing):
        return 0.0
    width = read.get("layers.line_width")
    base = float(width) if isinstance(width, int | float) else context.nozzle
    return min(1.0, base / spacing)


def _read_filament(
    filament: Mapping[str, Any], machine: Mapping[str, Any], plate: str, source: Path
) -> tuple[dict[str, object], bool]:
    """Die Filamentwerte in Solidons Pfaden — samt Rückzug der Maschine, wo das
    Filament ``nil`` sagt, und der Betttemperatur der gewählten Platte."""
    read: dict[str, object] = {}
    for solidon, native, kind in slicer_profiles.FILAMENT_READBACK:
        text = _text(filament.get(native))
        if text is None:
            continue
        number = _float(text.rstrip("%"))
        if number is None:
            continue
        if solidon == "filament.max_flow" and number <= 0.0:
            continue
        if solidon in slicer_profiles._AS_FRACTION:
            number /= 100.0
        read[solidon] = kind(number)
    refuses = False
    key = PLATE_TEMPERATURES.get(plate)
    if key is not None:
        # Die Betttemperatur gehört der Platte, die aufliegt. Aus
        # ``hot_plate_temp`` gelesen und nur überschrieben, wenn der Schlüssel
        # der Platte dasteht, zeigte die Grundlage sonst die Temperatur der
        # glatten Platte (Review Stufe A+B, H14). Fehlt er, bleibt Solidons Wert.
        read.pop("temperature.bed", None)
        read.pop("temperature.bed_first_layer", None)
        for suffix, path in (
            ("", "temperature.bed"),
            ("_initial_layer", "temperature.bed_first_layer"),
        ):
            text = _text(filament.get(key + suffix))
            number = _float(text) if text is not None else None
            if number is None:
                continue
            if number <= 0.0:
                refuses = True
                continue
            read[path] = round(number)
    # Rückzug und Z-Hop: Die Hersteller setzen sie an der Maschine und lassen
    # sie im Filament offen (``nil``). Wer nur das Filament liest, hält
    # Solidons Tabelle für die Wahrheit — am CC2 0,2 statt 0,4 mm Z-Hop.
    for path, filament_key, machine_key in (
        ("retraction.length", "filament_retraction_length", "retraction_length"),
        ("retraction.speed", "filament_retraction_speed", "retraction_speed"),
        ("retraction.z_hop", "filament_z_hop", "z_hop"),
    ):
        if path in read or _text(filament.get(filament_key)) is not None:
            continue
        number = _float(_text(machine.get(machine_key)) or "")
        if number is not None and number >= 0.0:
            read[path] = number
    wipe = _text(filament.get("filament_wipe")) or _text(machine.get("wipe"))
    if wipe is not None and wipe.casefold() in ("0", "1", "true", "false"):
        read["retraction.wipe"] = wipe.casefold() in ("1", "true")
    _log.debug("read %d filament values from %s", len(read), source.name)
    return read, refuses


# --- PrusaSlicer ------------------------------------------------------------------

#: Füllmuster zurück: die Umkehrung von ``slicer_keys._PRUSA_INFILL``.
_PRUSA_INFILL_BACK: Final = {prusa: solidon for solidon, prusa in slicer_keys._PRUSA_INFILL.items()}

#: Die Prozessschlüssel von PrusaSlicer und ihre Solidon-Pfade — die Tabelle
#: ``slicer_keys.PRUSA`` rückwärts. Tempi in Prozent eines anderen, die erste
#: Schicht, Stützart, -winkel, -abstand und -dichte, Haftungsart, Rückzug und
#: Filament hängen an mehreren Schlüsseln und stehen in :func:`_read_prusa`.
PRUSA_PROCESS: Final[tuple[tuple[str, str, Reader], ...]] = (
    ("layers.layer_height", "layer_height", _positive),
    ("layers.first_layer_height", "first_layer_height", _positive),
    ("shell.wall_count", "perimeters", _count),
    ("shell.top_layers", "top_solid_layers", _count),
    ("shell.bottom_layers", "bottom_solid_layers", _count),
    ("shell.outer_wall_first", "external_perimeters_first", _flag),
    (
        "shell.seam_position",
        "seam_position",
        _choice({"aligned": "aligned", "nearest": "nearest", "random": "random", "rear": "rear"}),
    ),
    (
        "shell.wall_generator",
        "perimeter_generator",
        _choice({"classic": "classic", "arachne": "arachne"}),
    ),
    ("shell.ironing", "ironing", _flag),
    ("infill.density", "fill_density", _fraction),
    ("infill.pattern", "fill_pattern", _choice(_PRUSA_INFILL_BACK)),
    ("infill.angle", "fill_angle", _number),
    ("speed.inner_wall", "perimeter_speed", _positive),
    ("speed.infill", "infill_speed", _positive),
    ("speed.travel", "travel_speed", _positive),
    ("speed.bridge", "bridge_speed", _positive),
    ("speed.acceleration", "default_acceleration", _positive),
    (
        "support.placement",
        "support_material_buildplate_only",
        _choice({"1": "build_plate", "0": "everywhere"}),
    ),
    ("support.z_gap", "support_material_contact_distance", _number),
    ("support.interface_layers", "support_material_interface_layers", _count),
    ("adhesion.skirt_loops", "skirts", _count),
    ("adhesion.skirt_distance", "skirt_distance", _number),
    ("adhesion.brim_width", "brim_width", _number),
    ("adhesion.raft_layers", "raft_layers", _count),
    ("retraction.avoid_crossing_walls", "avoid_crossing_perimeters", _flag),
)

#: Was PrusaSlicer einsetzt, wo die Kette eines Bündels einen gelesenen
#: Schlüssel nicht nennt: ``FullPrintConfig::defaults()``, **gemessen** mit
#: ``--save`` aus einem leeren ``--datadir`` (PrusaSlicer 2.9.6, 27.09.2026).
#: Prusas Bündel nennen fast alles selbst; offen ließen sie am MK4S, MINI und
#: XL Haftung, Bügeln und ``avoid_crossing_perimeters``, Sovols SV06 dazu
#: Wandgenerator, Stützstil und die Füllung der ersten Schicht.
PRUSA_PROGRAM_DEFAULTS: Final[Mapping[str, str]] = {
    "avoid_crossing_perimeters": "0",
    "bed_temperature": "0",
    "bottom_solid_layers": "3",
    "bridge_fan_speed": "100",
    "bridge_speed": "60",
    "brim_type": "outer_only",
    "brim_width": "0",
    "chamber_temperature": "0",
    "default_acceleration": "0",
    "disable_fan_first_layers": "3",
    "external_perimeter_acceleration": "0",
    "external_perimeter_extrusion_width": "0",
    "external_perimeter_speed": "50%",
    "external_perimeters_first": "0",
    "extrusion_multiplier": "1",
    "extrusion_width": "0",
    "fan_always_on": "0",
    "fan_below_layer_time": "60",
    "filament_density": "0",
    "filament_diameter": "1.75",
    "filament_max_volumetric_speed": "0",
    "fill_angle": "45",
    "fill_density": "20%",
    "fill_pattern": "stars",
    "first_layer_bed_temperature": "0",
    "first_layer_extrusion_width": "200%",
    "first_layer_height": "0.35",
    "first_layer_infill_speed": "0",
    "first_layer_speed": "30",
    "first_layer_temperature": "200",
    "infill_speed": "80",
    "ironing": "0",
    "layer_height": "0.3",
    "max_fan_speed": "100",
    "min_fan_speed": "35",
    "perimeter_acceleration": "0",
    "perimeter_generator": "arachne",
    "perimeter_speed": "60",
    "perimeters": "3",
    "raft_layers": "0",
    "retract_length": "2",
    "retract_lift": "0",
    "retract_speed": "40",
    "seam_position": "aligned",
    "skirt_distance": "6",
    "skirts": "1",
    "slowdown_below_layer_time": "5",
    "solid_infill_speed": "20",
    "support_material": "0",
    "support_material_auto": "1",
    "support_material_buildplate_only": "0",
    "support_material_contact_distance": "0.2",
    "support_material_interface_layers": "3",
    "support_material_spacing": "2.5",
    "support_material_style": "grid",
    "support_material_threshold": "0",
    "support_material_xy_spacing": "50%",
    "temperature": "200",
    "top_solid_infill_speed": "15",
    "top_solid_layers": "3",
    "travel_speed": "130",
    "wipe": "0",
}

#: Schlüssel eines Bündels, die ein Profil verwalten und keine Einstellung
#: sind: die Erbkette, die Verträglichkeit, frühere Namen. In eine
#: Konfiguration geschrieben, liest PrusaSlicer sie nicht oder bindet damit
#: ein Profil an Drucker, das keines mehr ist.
PRUSA_MANAGING_KEYS: Final = frozenset(
    {
        "inherits",
        "compatible_printers",
        "compatible_printers_condition",
        "compatible_prints",
        "compatible_prints_condition",
        "renamed_from",
        "alias",
    }
)


@dataclass(frozen=True, slots=True)
class PrusaChain:
    """Drucker, Prozess und Filament aus PrusaSlicers Bestand, aufgelöst.

    Das ist, was PrusaSlicer druckt, wenn man die drei im Fenster wählt: jede
    Kette über ihre Erbbasen zusammengelegt, ohne die Schlüssel, die nur das
    Profil verwalten (:data:`PRUSA_MANAGING_KEYS`). Was keine der drei nennt,
    setzt PrusaSlicer aus seinen eingebauten Vorgaben ein — gelesen wird es
    über :data:`PRUSA_PROGRAM_DEFAULTS`, geschrieben muss es nicht werden.
    """

    printer: str
    process: str
    filament: str
    """Leer, wenn kein Filament des Bestands gewählt ist; dann gilt Solidons Material."""
    values: Mapping[str, str]


def prusa_chain(profile: Profile, setup: SlicerSetup) -> PrusaChain | None:
    """Die Kette dieser Übergabe — ``None`` ohne Drucker oder Prozess des Bestands.

    Ohne Drucker gibt es keine: Ein Prozess aus Prusas Bündel ist über seine
    Bedingung an einen Drucker gebunden, und ohne dessen Profil kämen Startcode
    und Maschine aus PrusaSlicers eingebauten Vorgaben — genau das, was das
    Bündel ersetzen soll. Dann bleibt Solidons Tabelle die Grundlage, und
    :func:`app.core.export.handover.machine_missing` sagt, warum.

    Ein gewählter Prozess, der sich nicht finden oder lesen lässt, ist ein
    Fehler (:class:`ExternalToolError`), keine leere Kette — der Kunde hat ihn
    gewählt und soll erfahren, dass er nicht gilt (:func:`findings`).
    """
    from app.core.export import handover

    if setup.flavour != "prusa" or not setup.base_process:
        return None
    printer = handover.machine_for(setup, profile)
    if not printer:
        return None
    roots = handover._profile_roots(setup)
    parts: list[Mapping[str, Any]] = []
    for name, kind in ((printer, "machine"), (setup.base_process, "process")):
        source = handover.profile_source(name, setup, kind)  # type: ignore[arg-type]
        if source is None:
            raise ExternalToolError(
                tool=setup.name,
                detail=_("Das gewählte Profil ist im Bestand des Slicers nicht zu finden."),
                values={"profile": name},
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        parts.append(_prusa_resolved(source, roots))
    filament = ""
    if setup.base_filament:
        source = handover.profile_source(setup.base_filament, setup, "filament")
        if source is not None:
            parts.append(_prusa_resolved(source, roots))
            filament = setup.base_filament
    values: dict[str, str] = {}
    for part in parts:
        values.update(
            {key: str(value) for key, value in part.items() if key not in PRUSA_MANAGING_KEYS}
        )
    return PrusaChain(printer, setup.base_process, filament, values)


def _prusa_resolved(
    source: Path | slicer_profiles.SlicerProfile, roots: tuple[Path, ...]
) -> dict[str, Any]:
    """Eine Kette des Bestands, gleich ob als Abschnitt eines Bündels oder als eigene Datei."""
    if isinstance(source, slicer_profiles.SlicerProfile):
        return slicer_profiles.resolve_profile(source, roots)
    return slicer_profiles.resolve_values(source, roots)


def _prusa_first(raw: object) -> str | None:
    """Ein Wert aus einer Prusa-Konfiguration: bei einer Liste je Extruder der
    erste, ``nil`` und leer heißen nichts."""
    text = _text(raw)
    if text is None:
        return None
    first = text.split(",")[0].strip().strip('"')
    return first if first and first != "nil" else None


def _read_prusa(
    values: Mapping[str, Any], context: _Context
) -> tuple[dict[str, object], dict[str, str]]:
    """Drucker, Prozess und Filament einer Prusa-Kette in Solidons Pfaden,
    dazu, was sich nicht übersetzen ließ."""
    read: dict[str, object] = {}
    foreign: dict[str, str] = {}

    def take(path: str, value: object) -> None:
        if isinstance(value, Foreign):
            foreign[path] = value.raw
        elif value is not None:
            read[path] = value

    for path, key, reader in PRUSA_PROCESS:
        text = _prusa_first(values.get(key))
        if text is not None:
            take(path, reader(text, context))
    take("layers.line_width", _prusa_width(values.get("extrusion_width")))
    take("layers.first_layer_line_width", _prusa_width(values.get("first_layer_extrusion_width")))
    inner = read.get("speed.inner_wall")
    infill = read.get("speed.infill")
    take("speed.outer_wall", _share_of(values.get("external_perimeter_speed"), inner))
    solid = _share_of(values.get("solid_infill_speed"), infill)
    solid_speed = solid if isinstance(solid, float) else None
    take("speed.top_surface", _share_of(values.get("top_solid_infill_speed"), solid_speed))
    take("speed.first_layer", _prusa_first_layer_speed(values, solid_speed))
    take("speed.outer_wall_acceleration", _prusa_outer_wall_acceleration(values))
    take("support.style", _prusa_support_style(values))
    outer_width = _prusa_outer_width(values, context)
    take("support.threshold_angle", _prusa_support_angle(values, read, outer_width))
    take("support.xy_gap", _prusa_support_gap(values, outer_width))
    take("support.density", _prusa_support_density(values, read, context))
    take("adhesion.kind", _prusa_adhesion(values))
    read.update(_prusa_retraction(values))
    read.update(_prusa_material(values))
    return read, foreign


def _prusa_width(raw: object) -> object:
    """Eine Bahnbreite in Millimetern. Null heißt „aus der Düse abgeleitet",
    Prozent rechnet PrusaSlicer über die Schichthöhe — beides keine Breite,
    die Solidon als Zahl führt."""
    text = _prusa_first(raw)
    if text is None:
        return None
    if text.endswith("%"):
        return Foreign(text)
    number = _float(text)
    if number is None:
        return Foreign(text)
    return number if number > 0.0 else None


def _share_of(raw: object, base: object) -> object:
    """Ein Tempo in mm/s oder in Prozent eines anderen — PrusaSlicer erlaubt
    beides (die Außenwand über den Wänden, die volle Füllung über der dünnen,
    die Deckfläche über der vollen). Null heißt „automatisch" und ist keine
    Zahl, die Solidon führt."""
    text = _prusa_first(raw)
    if text is None:
        return None
    if text.endswith("%"):
        share = _float(text[:-1].strip())
        if share is None or share <= 0.0 or not isinstance(base, float):
            return Foreign(text)
        return base * share / 100.0
    number = _float(text)
    return number if number is not None and number > 0.0 else Foreign(text)


def _prusa_first_layer_speed(values: Mapping[str, Any], solid: float | None) -> object:
    """Das Tempo der ersten Schicht, wie sie gedruckt wird — dieselbe Lesart
    wie :func:`_first_layer_speed` bei der Orca-Familie.

    ``first_layer_speed`` gilt jeder Bahn der ersten Schicht,
    ``first_layer_infill_speed`` ihrer vollen Füllung: null heißt „wie die
    erste Schicht", Prozent heißen ein Anteil der vollen Füllung (Hilfe von
    PrusaSlicer 2.9.6). Am MK4S sind das 40 und 100 mm/s — gedruckt wird der
    Boden mit 100. Ein ``first_layer_speed`` in Prozent skaliert jedes Tempo
    und ist deshalb keine Zahl, die Solidon führt.
    """
    first = _prusa_first(values.get("first_layer_speed"))
    if first is None:
        return None
    speed = None if first.endswith("%") else _float(first)
    if speed is None or speed <= 0.0:
        return Foreign(first)
    infill = _share_of(values.get("first_layer_infill_speed"), solid)
    return max(speed, infill) if isinstance(infill, float) else speed


def _prusa_outer_wall_acceleration(values: Mapping[str, Any]) -> object:
    """Die Beschleunigung der Außenwand: null heißt die der Wände, deren Null
    die allgemeine (Hilfe von PrusaSlicer 2.9.6)."""
    fallback = ""
    for key in (
        "external_perimeter_acceleration",
        "perimeter_acceleration",
        "default_acceleration",
    ):
        text = _prusa_first(values.get(key))
        if text is None:
            continue
        number = _float(text)
        if number is None:
            return Foreign(text)
        if number > 0.0:
            return number
        fallback = text
    return Foreign(fallback) if fallback else None


def _prusa_support_style(values: Mapping[str, Any]) -> str | None:
    """Stützen aus, oder an in der Art des Bündels.

    Prusas Vorgabe ist ``support_material = 1`` mit ``support_material_auto =
    0``: Stützen nur an Verstärkern, die jemand gemalt hat. Solidon malt
    keine, also stützt dieser Zustand nichts — er heißt hier „aus", und wer
    Stützen einschaltet, bekommt beide Schalter (Entscheidung J).
    """
    enabled = _prusa_first(values.get("support_material"))
    if enabled is None:
        return None
    automatic = (_prusa_first(values.get("support_material_auto")) or "1").casefold()
    if enabled.casefold() in ("0", "false") or automatic in ("0", "false"):
        return "none"
    style = (_prusa_first(values.get("support_material_style")) or "").casefold()
    if style == "organic":
        return "tree"
    if style == "grid":
        return "grid"
    return "auto"


def _prusa_outer_width(values: Mapping[str, Any], context: _Context) -> float | None:
    """Die Breite der Außenwand in Millimetern — PrusaSlicer leitet sie ohne
    Angabe aus der Düse ab (1,125-fach, ``Flow::auto_extrusion_width``)."""
    for key in ("external_perimeter_extrusion_width", "extrusion_width"):
        width = _prusa_width(values.get(key))
        if isinstance(width, float):
            return width
        if isinstance(width, Foreign):
            return None
    return context.nozzle * 1.125 if context.nozzle > 0.0 else None


def _prusa_support_angle(
    values: Mapping[str, Any], read: Mapping[str, object], outer_width: float | None
) -> float | None:
    """Der Stützwinkel gegen die Senkrechte — PrusaSlicer zählt gegen die Waagerechte.

    Null heißt dort „automatisch": Überhängend ist, was mehr als die halbe
    Breite der Außenwand über die Schicht darunter ragt (``SupportMaterial.cpp``,
    ``0.5f * fw``). Als Winkel ist das ``atan(0,5 · Außenwand / Schicht)`` —
    bei 0,45 mm und 0,2 mm Schicht 48,4°.
    """
    text = _prusa_first(values.get("support_material_threshold"))
    number = _float(text) if text is not None else None
    if number is None or not 0.0 <= number < 90.0:
        return None
    if not is_zero(number):
        return 90.0 - number
    layer = read.get("layers.layer_height")
    if not isinstance(layer, float) or layer <= 0.0 or outer_width is None:
        return None
    # Genau gerechnet, nicht mit ``math.atan``: Mit diesem Winkel entscheidet
    # die Schichtanalyse über Überhänge, und dort darf die letzte Stelle nicht
    # an der Plattform hängen (RM-187, ``.claude/rules/kern.md``).
    return exact_atan_degrees(0.5 * outer_width / layer)


def _prusa_support_gap(values: Mapping[str, Any], outer_width: float | None) -> object:
    """Der seitliche Abstand in Millimetern; Prozent gelten der Außenwand."""
    text = _prusa_first(values.get("support_material_xy_spacing"))
    if text is None:
        return None
    if text.endswith("%"):
        share = _float(text[:-1].strip())
        if share is None or outer_width is None:
            return Foreign(text)
        return outer_width * share / 100.0
    number = _float(text)
    return Foreign(text) if number is None else number


def _prusa_support_density(
    values: Mapping[str, Any], read: Mapping[str, object], context: _Context
) -> float | None:
    """Die Stützdichte aus dem Linienabstand, wie bei der Orca-Familie."""
    return _support_density(
        {"support_base_pattern_spacing": _prusa_first(values.get("support_material_spacing"))},
        read,
        context,
    )


def _prusa_adhesion(values: Mapping[str, Any]) -> object:
    """Die Haftungsart: Raft, Brim oder Skirt, was davon gesetzt ist.

    PrusaSlicer hat keinen Auto-Brim; die Art folgt aus den Maßen. Prusas
    eigene Drucker legen keinen Skirt, weil ihr Startcode eine Spüllinie zieht.
    """

    def measure(key: str) -> float:
        return _float(_prusa_first(values.get(key)) or "0") or 0.0

    if measure("raft_layers") > 0.0:
        return "raft"
    brim_type = _prusa_first(values.get("brim_type")) or "outer_only"
    if measure("brim_width") > 0.0 and brim_type != "no_brim":
        return "brim"
    return "skirt" if measure("skirts") > 0.0 else "none"


def _prusa_retraction(values: Mapping[str, Any]) -> dict[str, object]:
    """Der Rückzug: am Drucker, außer das Filament sagt etwas anderes.

    ``filament_retract_length`` und seine Geschwister stehen bei den meisten
    Filamenten auf ``nil`` — dann gilt der Wert des Druckers. Am MINI sind
    das 2,5 mm für seinen Bowden-Extruder; Solidons Tabelle kannte 0,8.
    """
    read: dict[str, object] = {}
    for path, printer_key in (
        ("retraction.length", "retract_length"),
        ("retraction.speed", "retract_speed"),
        ("retraction.z_hop", "retract_lift"),
    ):
        text = _prusa_first(values.get(f"filament_{printer_key}")) or _prusa_first(
            values.get(printer_key)
        )
        number = _float(text) if text is not None else None
        if number is not None and number >= 0.0:
            read[path] = number
    wipe = _prusa_first(values.get("filament_wipe")) or _prusa_first(values.get("wipe"))
    if wipe is not None and wipe.casefold() in ("0", "1", "true", "false"):
        read["retraction.wipe"] = wipe.casefold() in ("1", "true")
    return read


def _prusa_material(values: Mapping[str, Any]) -> dict[str, object]:
    """Temperatur, Kühlung und Materialkennwerte des Filaments.

    Der untere Lüfterwert gilt nur mit ``fan_always_on``; ohne den Schalter
    läuft der Lüfter bei langen Schichten gar nicht, und das heißt in Solidon
    ein unterer Wert von null (die Schreibseite rechnet genauso,
    ``slicer_keys._positive_switch``).
    """
    read: dict[str, object] = {}
    for solidon, native, kind in slicer_profiles.PRUSA_FILAMENT_READBACK:
        if solidon.startswith("retraction."):
            continue
        text = _prusa_first(values.get(native))
        number = _float(text.rstrip("%")) if text is not None else None
        if number is None:
            continue
        if solidon == "filament.max_flow" and number <= 0.0:
            continue
        if solidon in slicer_profiles._AS_FRACTION:
            number /= 100.0
        read[solidon] = kind(number)
    always = (_prusa_first(values.get("fan_always_on")) or "0").casefold()
    if always in ("0", "false") and "cooling.minimum_fan_speed" in read:
        read["cooling.minimum_fan_speed"] = 0.0
    return read


def _measured(profile: Profile) -> dict[str, object]:
    """Was der Kunde an seinem Drucker gemessen hat und die Übergabe tragen muss."""
    measured = profile.material.overhang_angle
    if profile.has_process_calibration and measured is not None and 0.0 < measured < 90.0:
        return {"support.threshold_angle": measured}
    return {}


#: Was eine Stufe ausmacht, wenn sie über dem Standardprozess des Herstellers
#: liegt (Entscheidung I, Rückfall): Schichthöhe, erste Schicht, Wände,
#: Deckschichten und Füllung. **Tempo, Beschleunigung und Kühlung bleiben
#: beim Hersteller** — sie hängen an Drucker und Material, nicht an der Stufe;
#: Solidons Stufen skalieren sie nur mit.
STAGE_PATHS: Final = (
    "layers.layer_height",
    "layers.first_layer_height",
    "shell.wall_count",
    "shell.top_layers",
    "shell.bottom_layers",
    "infill.density",
    "infill.pattern",
)


def _stage_values(profile: Profile, quality: QualityPreset) -> dict[str, object]:
    """Wo die Stufe von Solidons Standard abweicht, in :data:`STAGE_PATHS`.

    Gemessen am Centauri Carbon 2: „Fein" sind 0,12 statt 0,20 mm Schicht, 7
    und 5 statt 5 und 4 Deckschichten, 20 % Gyroid; „Belastbar" 5 Wände und 40 %
    Würfel; „Entwurf" 0,28 mm, 2 Wände, 10 %. Die Standardstufe weicht von sich
    selbst nicht ab.
    """
    if quality == settings_table.DEFAULT_QUALITY:
        return {}
    stage = settings_table.resolve(profile, quality)
    standard = settings_table.resolve(profile, settings_table.DEFAULT_QUALITY)
    values: dict[str, object] = {}
    for path in STAGE_PATHS:
        value = settings_table.read_path(stage, path)
        if not settings_table.same_value(value, settings_table.read_path(standard, path)):
            values[path] = value
    return values


def _declared_name(path: Path) -> str:
    """Der Name, den eine Profildatei selbst trägt — sonst ihr Stamm.

    Bei eigenen Vorlagen muss der Dateiname nicht dem ``name`` gleichen
    (Review Stufe A+B, Anmerkung zu F2).
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return path.stem
    name = document.get("name") if isinstance(document, dict) else None
    return name.strip() if isinstance(name, str) and name.strip() else path.stem


def _runs_the_standard_process(process_file: Path, machine: Mapping[str, Any]) -> bool:
    """Liegt der Standardprozess der Maschine darunter?

    Nur dann legt eine Stufe ihre Werte darüber. Wer selbst einen Prozess
    gewählt hat — „0.12mm Fine" etwa —, hat damit die Stufe gewählt, und der
    Prozess bestimmt sie. Nennt die Maschine keinen Standardprozess, gilt der
    als Standard, der es im Namen trägt (wie bei der Vorwahl in
    ``slicer_profiles.match``).
    """
    chosen = _declared_name(process_file)
    standard = _text(machine.get("default_print_profile"))
    if standard:
        return chosen == standard
    return "standard" in chosen.casefold()


def base_settings(
    profile: Profile, quality: QualityPreset, setup: SlicerSetup | None
) -> Foundation:
    """Die Grundlage für diesen Drucker, dieses Material und diese Stufe.

    Mit einem Slicer der Orca-Familie und einem lesbaren Prozessprofil ist sie
    das Herstellerprofil, zurückgelesen in Solidons Felder. Sonst ist sie
    Solidons Tabelle (:func:`app.core.knowledge.print_settings.resolve`) —
    und die Übergabe schreibt sie dann vollständig.
    """
    fallback = settings_table.resolve(profile, quality)
    measured = _measured(profile)
    if setup is None or setup.flavour not in ("orca", "prusa") or not setup.base_process:
        return Foundation(fallback, measured=measured)
    if setup.flavour == "prusa":
        return _prusa_foundation(profile, quality, setup, fallback, measured)
    from app.core.export import handover

    roots = handover._profile_roots(setup)
    try:
        process_file = handover.profile_file(setup.base_process, setup, "process")
        if process_file is None:
            return Foundation(fallback, measured=measured, unreadable=setup.base_process)
        process = slicer_profiles.resolve_values(process_file, roots=roots)
        machine_name = handover.machine_for(setup, profile)
        machine_file = (
            handover.profile_file(machine_name, setup, "machine") if machine_name else None
        )
        machine = slicer_profiles.resolve_values(machine_file, roots=roots) if machine_file else {}
        filament_file = (
            handover.profile_file(setup.base_filament, setup, "filament")
            if setup.base_filament
            else None
        )
        filament = (
            slicer_profiles.resolve_values(filament_file, roots=roots) if filament_file else {}
        )
    except ExternalToolError as problem:
        # Eine Kette, die sich nicht auflösen lässt, ist keine Grundlage: dann
        # gilt Solidons Tabelle, und die Übergabe schreibt sie ganz.
        _log.warning("manufacturer profile unreadable, using Solidon's table: %s", problem)
        return Foundation(fallback, measured=measured, unreadable=setup.base_process)

    model = (
        _machine_model(machine_file, str(machine.get("printer_model", "")), roots)
        if machine_file
        else {}
    )
    plate = (
        plate_name(setup.plate)
        or default_plate(machine, model)
        or ("" if offers_plates(machine, model) else SINGLE_PLATE)
    )
    context = _Context(nozzle=profile.printer.nozzle_diameter)
    defaults = PROGRAM_DEFAULTS.get(program(setup), {})
    read, foreign = _read_process(process, context, defaults)
    refuses = False
    if filament_file is not None:
        filament_read, refuses = _read_filament(filament, machine, plate, filament_file)
        read.update(filament_read)
    read.update(measured)
    staged = (
        _stage_values(profile, quality) if _runs_the_standard_process(process_file, machine) else {}
    )

    base = fallback
    for path, value in read.items():
        base = settings_table.with_path(base, path, value)
    for path, value in staged.items():
        base = settings_table.with_path(base, path, value)
    for path in foreign:
        # Was der Hersteller anders nennt, als Solidon es kennt, bleibt für
        # Solidons eigene Rechnung beim Rückfall — aber nicht als Aussage:
        # Die Anzeige nennt den Herstellerwert.
        read.pop(path, None)
    return Foundation(
        replace(base, chosen=frozenset(), accepted=frozenset()),
        from_profile=frozenset(read) - frozenset(measured) - frozenset(staged),
        foreign=foreign,
        measured=measured,
        staged=frozenset(staged),
        machine=machine_name,
        process=setup.base_process,
        filament=setup.base_filament,
        plate=plate,
        plate_refuses_filament=refuses,
        plates=plate_temperatures(filament),
    )


def _prusa_foundation(
    profile: Profile,
    quality: QualityPreset,
    setup: SlicerSetup,
    fallback: PrintSettings,
    measured: Mapping[str, object],
) -> Foundation:
    """Die Grundlage aus Drucker, Prozess und Filament eines Prusa-Bündels.

    Dieselbe Rechnung wie für die Orca-Familie, ohne Druckplatte: PrusaSlicer
    führt die Betttemperatur am Filament. Ohne Drucker des Bestands bleibt
    Solidons Tabelle die Grundlage (:func:`prusa_chain`).
    """
    try:
        chain = prusa_chain(profile, setup)
    except ExternalToolError as problem:
        _log.warning("Prusa profile unreadable, using Solidon's table: %s", problem)
        return Foundation(
            fallback, measured=measured, unreadable=setup.base_process, has_plates=False
        )
    if chain is None:
        return Foundation(fallback, measured=measured, has_plates=False)
    context = _Context(nozzle=profile.printer.nozzle_diameter)
    read, foreign = _read_prusa({**PRUSA_PROGRAM_DEFAULTS, **chain.values}, context)
    if not chain.filament:
        # Ohne Filament des Bestands gilt Solidons Material, nicht PrusaSlicers
        # eingebaute 200 °C bei kaltem Bett.
        read = {path: value for path, value in read.items() if not _material_path(path)}
    read.update(measured)
    standard = _prusa_first(chain.values.get("default_print_profile"))
    staged = _stage_values(profile, quality) if chain.process == standard else {}

    base = fallback
    for path, value in read.items():
        base = settings_table.with_path(base, path, value)
    for path, value in staged.items():
        base = settings_table.with_path(base, path, value)
    for path in foreign:
        read.pop(path, None)
    return Foundation(
        replace(base, chosen=frozenset(), accepted=frozenset()),
        from_profile=frozenset(read) - frozenset(measured) - frozenset(staged),
        foreign=foreign,
        measured=measured,
        staged=frozenset(staged),
        machine=chain.printer,
        process=chain.process,
        filament=chain.filament,
        has_plates=False,
    )


#: Die Gruppen, die am Filament hängen — ohne Filament des Bestands bleiben
#: sie bei Solidons Material und gehen vollständig hinaus.
MATERIAL_GROUPS: Final = ("temperature", "cooling", "filament")


def _material_path(path: str) -> bool:
    """Gehört dieser Pfad dem Filament und nicht Drucker oder Prozess?"""
    return path.partition(".")[0] in MATERIAL_GROUPS


def findings(foundation: Foundation) -> list[Finding]:
    """Was der Kunde über die Grundlage wissen muss, bevor er druckt.

    Ein gewähltes Prozessprofil, das sich nicht lesen ließ (H13): Dann gehen
    Solidons Werte hinaus, und das Fenster sagte nur „Ohne Profil des
    Herstellers". Eine Platte, die niemand nennt, und eine, die der Hersteller
    für dieses Filament sperrt (R4): Die Orca-Familie bricht dann mit „does not
    support filament" ab. Der Weg ist jedes Mal derselbe: im Druckdialog
    wählen, was gilt.
    """
    if foundation.unreadable:
        return [
            Finding(
                code="slicer.process_unreadable",
                severity="warning",
                message=_("Das gewählte Prozessprofil ließ sich nicht lesen."),
                values={"profile": foundation.unreadable},
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        ]
    if not foundation.has_profile:
        return []
    if foundation.has_plates and not foundation.plate:
        return [
            Finding(
                code="slicer.plate_unknown",
                severity="warning",
                message=_("Welche Druckplatte aufliegt, sagt das Profil nicht."),
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        ]
    if foundation.plate_refuses_filament:
        return [
            Finding(
                code="slicer.plate_refuses_filament",
                severity="warning",
                message=_("Der Hersteller gibt diese Platte für dieses Filament nicht frei."),
                values={"plate": foundation.plate},
                suggestions=(OPEN_PRINT_SETTINGS,),
            )
        ]
    return []


def effective(stored: PrintSettings | None, foundation: Foundation) -> PrintSettings:
    """Was gedruckt wird: die Grundlage, darüber die eigene Wahl und die
    übernommenen Vorschläge des Projekts."""
    if stored is None:
        return foundation.settings
    return settings_table.on_base(stored, foundation.settings)


def written_paths(settings: PrintSettings, foundation: Foundation) -> frozenset[str] | None:
    """Welche Punktpfade die Übergabe schreibt — ``None`` heißt alle.

    Mit Herstellerprofil darunter nur, was abweichen soll, was gemessen ist
    und was die Stufe über den Standardprozess legt; ohne eines schreibt
    Solidon wie bisher alles (Konzept, Entscheidung D).
    """
    if not foundation.has_profile:
        return None
    return settings.explicit | frozenset(foundation.measured) | foundation.staged
