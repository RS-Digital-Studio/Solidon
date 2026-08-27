"""Druckeinstellungen laden und auflösen (Bauplan §29).

Solidon hält die Einstellungen, der externe Slicer führt sie aus. Damit das
ohne doppelte Pflege geht, entsteht ein :class:`PrintSettings` aus drei
Ebenen, die übereinander gelegt werden — dieselbe Aufteilung, die die
verbreiteten Slicer als Prozess-, Filament- und Druckerprofil führen:

1. **Qualitätsstufe** aus ``data/print_settings.toml`` — Schichthöhe, Wände,
   Füllung, Geschwindigkeit.
2. **Material** aus derselben Datei — Temperaturen, Kühlung, Rückzug, Farbe.
   Überschreibt die Stufe, wo beide etwas sagen.
3. **Drucker** aus ``printers.toml`` — Düsendurchmesser skaliert Schichthöhe
   und Linienbreite, die Temperaturgrenzen deckeln, und ohne geschlossenen
   Bauraum gibt es keine Kammertemperatur.

Was die Geometrie darüber hinaus verlangt, kommt nicht von hier, sondern aus
:mod:`app.core.slice.advise` — dort mit Begründung je Wert.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any, Final, get_args

from app.core.errors import ValidationError
from app.core.log import get_logger
from app.core.paths import user_profiles_dir
from app.core.types import (
    AdhesionSettings,
    AdhesionType,
    CoolingSettings,
    FilamentSettings,
    InfillPattern,
    InfillSettings,
    LayerSettings,
    PrintSettings,
    Profile,
    QualityPreset,
    RetractionSettings,
    ShellSettings,
    SpeedSettings,
    SupportSettings,
    TemperatureSettings,
)
from app.i18n import _

_log = get_logger(__name__)

DEFAULT_QUALITY: Final[QualityPreset] = "standard"

#: Die Düse, für die der Startbestand geschrieben ist. Eine größere Düse legt
#: dickere Schichten, eine kleinere dünnere — alles andere bleibt.
REFERENCE_NOZZLE: Final = 0.4

#: Mehr als drei Viertel des Düsendurchmessers trägt keine Schicht mehr sicher
#: auf der darunterliegenden auf.
MAX_LAYER_RATIO: Final = 0.75

_DATA_DIR: Final = Path(__file__).parent / "data"

_tables: dict[str, dict[str, dict[str, Any]]] | None = None


def _read_table(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except tomllib.TOMLDecodeError as problem:
        # Auch hier liest derselbe Leser die Datei des Nutzers — eine
        # handgeschriebene. Ein Tippfehler ist ein Satz mit Dateinamen, kein
        # Startabbruch (Regel 17).
        raise ValidationError(
            title=_("Diese Einstellungsdatei lässt sich nicht lesen."),
            field="file",
            detail=str(problem),
            constraint="toml",
            values={"file": str(path)},
        ) from problem


def _load() -> dict[str, dict[str, dict[str, Any]]]:
    """Mitgelieferte Tabelle, darüber die eigene. Je Eintrag, nicht je Datei —
    wer nur die PETG-Temperatur ändert, verliert nicht den Rest.
    """
    loaded: dict[str, dict[str, dict[str, Any]]] = {"quality": {}, "material": {}}
    for path in (_DATA_DIR / "print_settings.toml", user_profiles_dir() / "print_settings.toml"):
        if not path.is_file():
            continue
        table = _read_table(path)
        for section in ("quality", "material"):
            for identifier, values in table.get(section, {}).items():
                if not isinstance(values, dict):
                    raise ValidationError(
                        field=f"{section}.{identifier}",
                        detail=_("Dieser Eintrag muss eine Tabelle mit Werten sein."),
                        values={"file": str(path)},
                    )
                loaded[section].setdefault(identifier, {}).update(values)
    return loaded


def _all() -> dict[str, dict[str, dict[str, Any]]]:
    global _tables
    if _tables is None:
        _tables = _load()
        _log.info(
            "loaded %d quality presets and %d material settings",
            len(_tables["quality"]),
            len(_tables["material"]),
        )
    return _tables


def reload() -> None:
    """Verwirft den Cache, nachdem der Nutzer eigene Werte geschrieben hat."""
    global _tables
    _tables = None


def quality_presets() -> Mapping[str, str]:
    """Kennung auf Titel, für die Auswahl in der Oberfläche."""
    return {key: str(values.get("title", key)) for key, values in _all()["quality"].items()}


def _quality_table(quality: QualityPreset) -> dict[str, Any]:
    table = _all()["quality"]
    if quality not in table:
        raise ValidationError(
            field="quality",
            detail=_("Diese Qualitätsstufe ist nicht bekannt."),
            values={"requested": quality, "known": sorted(table)},
        )
    return table[quality]


def has_material(material_id: str) -> bool:
    """Ob die Einstellungstabelle dieses Material kennt (§29).

    Für den Befund, der dem stillen ``_log.info`` in ``_material_table``
    fehlte: ein selbst angelegtes Material bekam PLA-nahe Modellvorgaben,
    und niemand erfuhr es (Regel 21).
    """
    return material_id in _all()["material"]


def _material_table(material_id: str) -> dict[str, Any]:
    """Ein unbekanntes Material ist kein Fehler — dann gelten die Vorgaben des
    Modells, und der Nutzer stellt nach.

    Eigene Filamente sollen sich eintragen lassen, ohne dass jemand vorher eine
    Tabelle pflegt. Ein Abbruch hier hieße: neues Material, keine Einstellungen.
    """
    table = _all()["material"]
    if material_id in table:
        return table[material_id]
    _log.info("no print settings for material %s, using model defaults", material_id)
    return {}


def resolve(profile: Profile, quality: QualityPreset = DEFAULT_QUALITY) -> PrintSettings:
    """Die drei Ebenen zu einem Satz Einstellungen (§29)."""
    stage = _quality_table(quality)
    stuff = _material_table(profile.material.id)
    printer = profile.printer

    scale = printer.nozzle_diameter / REFERENCE_NOZZLE
    ceiling = printer.nozzle_diameter * MAX_LAYER_RATIO
    layer_height = min(float(stage["layer_height"]) * scale, ceiling)
    first_layer = min(float(stage["first_layer_height"]) * scale, ceiling)

    return PrintSettings(
        id=f"{quality}-{profile.material.id}",
        title=f"{stage.get('title', quality)} · {profile.material.title}",
        quality=quality,
        layers=LayerSettings(
            layer_height=round(layer_height, 3),
            first_layer_height=round(first_layer, 3),
            line_width=printer.extrusion_width,
            first_layer_line_width=round(printer.extrusion_width * 1.07, 3),
        ),
        shell=ShellSettings(
            wall_count=int(stage["wall_count"]),
            top_layers=int(stage["top_layers"]),
            bottom_layers=int(stage["bottom_layers"]),
        ),
        infill=InfillSettings(
            density=float(stage["infill_density"]),
            pattern=_pattern(stage.get("infill_pattern", "grid")),
        ),
        temperature=_temperatures(stuff, profile),
        cooling=CoolingSettings(
            fan_speed=float(stuff.get("fan_speed", 1.0)),
            bridge_fan_speed=float(stuff.get("bridge_fan_speed", 1.0)),
            disable_first_layers=int(stuff.get("disable_fan_layers", 1)),
            minimum_layer_time=float(stage["minimum_layer_time"]),
        ),
        speed=SpeedSettings(
            outer_wall=float(stage["speed_outer_wall"]),
            inner_wall=float(stage["speed_inner_wall"]),
            infill=float(stage["speed_infill"]),
            top_surface=float(stage["speed_top_surface"]),
            first_layer=float(stage["speed_first_layer"]),
            bridge=float(stage["speed_bridge"]),
            acceleration=float(stage["acceleration"]),
            outer_wall_acceleration=float(stage["outer_wall_acceleration"]),
        ),
        support=SupportSettings(),
        adhesion=AdhesionSettings(kind=_adhesion(stuff.get("adhesion", "skirt"))),
        retraction=RetractionSettings(
            length=float(stuff.get("retraction_length", 0.8)),
            speed=float(stuff.get("retraction_speed", 35.0)),
            z_hop=float(stuff.get("z_hop", 0.2)),
        ),
        filament=FilamentSettings(
            density=float(stuff.get("density", 1.24)),
            flow_ratio=float(stuff.get("flow_ratio", 1.0)),
            colour=str(stuff.get("colour", "#4A90D9")),
            max_flow=float(stuff.get("max_flow", 12.0)),
        ),
    )


def _temperatures(stuff: Mapping[str, Any], profile: Profile) -> TemperatureSettings:
    """Materialwerte, gedeckelt auf das, was der Drucker kann.

    Ein Profil, das 255 Grad verlangt, und ein Drucker, der 260 kann, passen
    zusammen; derselbe Wert auf einer Maschine mit 250 als Grenze ist ein
    stiller Schaden. Gedeckelt wird, aber ``advise`` sagt es auch.
    """
    printer = profile.printer
    return TemperatureSettings(
        nozzle=min(int(stuff.get("nozzle", 210)), printer.nozzle_temperature_max),
        nozzle_first_layer=min(
            int(stuff.get("nozzle_first_layer", 215)), printer.nozzle_temperature_max
        ),
        bed=min(int(stuff.get("bed", 60)), printer.bed_temperature_max),
        bed_first_layer=min(int(stuff.get("bed_first_layer", 60)), printer.bed_temperature_max),
        chamber=int(stuff.get("chamber", 0)) if printer.enclosed else 0,
    )


def _pattern(value: object) -> InfillPattern:
    text = str(value)
    if text not in get_args(InfillPattern):
        raise ValidationError(
            field="infill_pattern",
            detail=_("Dieses Füllmuster ist nicht bekannt."),
            values={"requested": text, "known": sorted(get_args(InfillPattern))},
        )
    return text  # type: ignore[return-value]


def _adhesion(value: object) -> AdhesionType:
    text = str(value)
    if text not in get_args(AdhesionType):
        raise ValidationError(
            field="adhesion",
            detail=_("Diese Art der Druckbetthaftung ist nicht bekannt."),
            values={"requested": text, "known": sorted(get_args(AdhesionType))},
        )
    return text  # type: ignore[return-value]


#: Wo die Punktpfade aus :class:`SettingAdvice` hinzeigen. Die Oberfläche und
#: die Slicer-Zuordnung benutzen dieselbe Schreibweise.
_GROUPS: Final = (
    "layers",
    "shell",
    "infill",
    "temperature",
    "cooling",
    "speed",
    "support",
    "adhesion",
    "retraction",
    "filament",
)


def read_path(settings: PrintSettings, path: str) -> Any:
    """Einen Wert über seinen Punktpfad lesen, etwa ``support.style``."""
    group, _dot, name = path.partition(".")
    if not name or group not in _GROUPS:
        raise ValidationError(
            field="path",
            detail=_("Dieser Pfad zeigt auf keine Einstellung."),
            values={"path": path, "groups": list(_GROUPS)},
        )
    section = getattr(settings, group)
    if not hasattr(section, name):
        raise ValidationError(
            field="path",
            detail=_("Diese Gruppe hat keine solche Einstellung."),
            values={"path": path},
        )
    return getattr(section, name)


def with_path(settings: PrintSettings, path: str, value: Any) -> PrintSettings:
    """Einen Wert über seinen Punktpfad setzen — als neue Einstellung.

    ``PrintSettings`` ist unveränderlich, damit ein Vorschlag angesehen werden
    kann, bevor er gilt. Das hier baut die geänderte Version, es ändert nichts.
    """
    group, _dot, name = path.partition(".")
    read_path(settings, path)
    section = getattr(settings, group)
    return replace(settings, **{group: replace(section, **{name: value})})
