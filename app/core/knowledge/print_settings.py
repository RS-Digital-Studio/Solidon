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
   Bauraum gibt es keine Kammertemperatur. Kennt das Profil das Standardtempo
   seines Herstellers, gilt es für „Standard"; kein Tempo liegt danach über
   dem Volumenstrom des Filaments (:func:`flow_speed_limit`).

Was die Geometrie darüber hinaus verlangt, kommt nicht von hier, sondern aus
:mod:`app.core.slice.advise` — dort mit Begründung je Wert.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, Final, TypedDict, get_args

from app.core.errors import ValidationError
from app.core.knowledge.tables import read_table
from app.core.log import get_logger
from app.core.paths import user_profiles_dir
from app.core.types import (
    AdhesionSettings,
    AdhesionType,
    BoundingBox,
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
from app.core.units import EPS_SETTING, is_close
from app.i18n import _

_log = get_logger(__name__)

DEFAULT_QUALITY: Final[QualityPreset] = "standard"

#: Die Düse, für die der Startbestand geschrieben ist. Eine größere Düse legt
#: dickere Schichten, eine kleinere dünnere — alles andere bleibt.
REFERENCE_NOZZLE: Final = 0.4

#: Mehr als drei Viertel des Düsendurchmessers trägt keine Schicht mehr sicher
#: auf der darunterliegenden auf.
MAX_LAYER_RATIO: Final = 0.75

#: Länge der Schrägnaht-Rampe in Millimetern, wie Orca und Prusa sie vorgeben.
#: Der Rat braucht zwei Rampen im Umfang; Cura schaltet sie mit einer Länge über null ein.
SCARF_LENGTH: Final = 20.0

#: Ab diesem Verhältnis von Höhe zur kleineren Fußausdehnung gilt ein Teil
#: als schlank. Druckrat und Anordnung verwenden dieselbe geometrische Frage.
SLENDER_RATIO: Final = 4.0


def is_slender(bounds: BoundingBox) -> bool:
    """Ob die Höhe mindestens viermal die kleinere waagerechte Ausdehnung ist.

    Die tatsächliche Kontaktfläche liest der Druckrat zusätzlich aus der
    ersten Schicht; die Anordnung verändert weder Lage noch Aufstandsfläche.
    """
    size = bounds.size
    foot_width = min(size[0], size[1])
    return foot_width > 0.0 and size[2] / foot_width >= SLENDER_RATIO


#: Die Tempi, bei denen die Düse fördert, und ob sie mit den Maßen der ersten
#: Schicht rechnen. Fahrt und Brücke stehen nicht darin: Die eine fördert
#: nicht, die andere mit eigenem Fluss.
FLOW_BOUND_SPEEDS: Final = (
    ("infill", False),
    ("inner_wall", False),
    ("outer_wall", False),
    ("top_surface", False),
    ("first_layer", True),
)

#: Das Material, an dem ``PrinterProfile.flow_factor`` gemessen ist — das
#: allgemeine PLA des Herstellers — und das einzige, dessen Volumenstrom er
#: hebt. Die übrigen begrenzt das Filament, nicht das Hotend: Die allgemeinen
#: Profile der Hersteller liegen dort bei Solidons Werten (Orca-Bestand,
#: 26.09.2026: Centauri ABS 12 und PETG-CF 12, K1 PETG 9 und TPU 3 bis 3,5,
#: MK4S TPU 3, gegen Solidons 11, 9, 10 und 3,5). Mit dem Faktor des PLA
#: bekam TPU am Centauri 6,1 mm³/s und 72 mm/s statt 41 — das Doppelte dessen,
#: was Elastikfilament durch die Düse bringt.
HOTEND_FLOW_MATERIAL: Final = "pla"

_DATA_DIR: Final = Path(__file__).parent / "data"

_tables: dict[str, dict[str, dict[str, Any]]] | None = None


def caps_volumetric_speed(flavour: str | None) -> bool:
    """Ob die Slicerfamilie den Filamentdurchsatz an jeder Druckbahn begrenzt.

    Prusa und Orca verwenden ``filament_max_volumetric_speed``. Cura kennt
    diesen Filamentdeckel nicht; dort bleibt der entsprechende Tempovorschlag
    nötig, ebenso solange noch kein unterstützter Slicer gewählt ist.
    """
    return flavour in ("orca", "prusa")


def _read_table(path: Path) -> dict[str, Any]:
    # Derselbe Leser liest die mitgelieferte Datei und die des Nutzers — eine
    # handgeschriebene. Ein Tippfehler darin ist ein Satz mit Dateinamen.
    return read_table(path, title=_("Diese Einstellungsdatei lässt sich nicht lesen."))


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


#: Die Namen der Qualitätsstufen in der Oberfläche (Regel 20). Die Titel in
#: ``print_settings.toml`` gingen am Einsammler vorbei und standen in jeder
#: Sprache deutsch im Druckdialog. Mit Kontext, denn „Standard" und „Fein"
#: sind als Wörter auch anderswo zu haben.
QUALITY_TITLES: Final = {
    "draft": _("Entwurf", context="Qualitätsstufe"),
    "standard": _("Standard", context="Qualitätsstufe"),
    "fine": _("Fein", context="Qualitätsstufe"),
    "strong": _("Belastbar", context="Qualitätsstufe"),
}


def quality_presets() -> Mapping[str, str]:
    """Kennung auf Titel, für die Auswahl in der Oberfläche — übersetzt
    (:data:`QUALITY_TITLES`); eine Stufe ohne Titel dort nennt den der Tabelle."""
    return {
        key: str(QUALITY_TITLES[key]) if key in QUALITY_TITLES else str(values.get("title", key))
        for key, values in _all()["quality"].items()
    }


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


def material_temperature(material_id: str, field: str) -> int | None:
    """Was das Material selbst verlangt, **ungedeckelt** — oder nichts.

    :func:`_temperatures` gibt nur den gedeckelten Wert heraus, und damit ist
    die Kürzung von außen nicht mehr zu sehen: 80 Grad Bett auf einer Maschine
    mit 80 Grad Grenze sehen aus wie 80 Grad Wunsch. ``advise`` braucht beide
    Zahlen, um den Unterschied zu melden (§17.3) — sonst deckelt der Kern
    still, und genau das soll er nicht.

    ``None`` heißt: Dieses Material sagt zu diesem Wert nichts. Das ist etwas
    anderes als eine Null — ein Material ohne eigene Einstellungen druckt mit
    den Modellvorgaben (siehe :func:`_material_table`), und daraus einen
    Befund zu bauen hieße, eine Vorgabe für einen Wunsch zu halten.
    """
    value = _material_table(material_id).get(field)
    return int(value) if isinstance(value, int | float) else None


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


def resolve(
    profile: Profile,
    quality: QualityPreset = DEFAULT_QUALITY,
    *,
    legacy: bool = False,
) -> PrintSettings:
    """Die drei Ebenen zu einem Satz Einstellungen (§29).

    ``legacy=True`` löst so auf, wie Solidon es bis 0.5.0 tat: die Tempi aus
    der Stufe allein — ohne das Tempo des Druckers, ohne seine Leerfahrt und
    ohne den Deckel auf den Volumenstrom —, und die erste Bahn 1,07
    Bahnbreiten breit statt so breit wie beim Hersteller. All das kam erst
    danach. Gebraucht wird das nur, um ältere Dateien einzuordnen
    (:func:`legacy_choices`): Eine Datei aus 0.5.0 mit „Fein" trägt
    30/45/60 mm/s, die heutige Auflösung am Centauri Carbon 2 120/150/150, und
    „Entwurf" füllt dort mit 120 statt gedeckelten 119. Die erste Bahn war dort
    0,449 mm breit, heute 0,5 mm wie bei Elegoo.
    """
    stage = _quality_table(quality)
    stuff = _material_table(profile.material.id)
    printer = profile.printer

    def paced(key: str, printer_value: float | None) -> float:
        return _paced(stage, key, None if legacy else printer_value)

    if printer.is_resin:
        # Ein Resin-Drucker hat keine Düse, an der die Stufe ihre Schichthöhe
        # skalieren könnte: Er belichtet in der Schichthöhe seines Profils,
        # und sein kleinstes Detail ist der Bildpunkt. Alles Weitere in
        # diesem Satz — Wände, Füllung, Temperaturen — ist ein FDM-Vertrag,
        # den kein Resin-Slicer liest; der Satz bleibt vollständig, damit
        # jeder Leser einen bekommt, aber er reist nicht in eine Übergabe
        # (``handover`` übersetzt für Resin nichts, Resin-Konzept §4).
        layer_height = first_layer = printer.layer_height
        line_width = first_layer_line_width = printer.pixel_size
    else:
        scale = printer.nozzle_diameter / REFERENCE_NOZZLE
        ceiling = printer.nozzle_diameter * MAX_LAYER_RATIO
        layer_height = min(float(stage["layer_height"]) * scale, ceiling)
        first_layer = min(float(stage["first_layer_height"]) * scale, ceiling)
        line_width = printer.extrusion_width
        # Die erste Bahn so breit wie beim Hersteller, als Vielfaches der Düse
        # (``PrinterProfile.first_layer_line_factor``): 0,5 mm am Centauri
        # Carbon 2, 0,8 am Kobra 2. Solidons 1,07-fache Bahnbreite war
        # schmaler als jedes Werksprofil und bleibt der Rückfall. Die eine
        # Stelle, an der ``resolve`` für Stufe D anders rechnet: Bei Cura ist
        # dieser Satz die Grundlage, und die anderen Slicer bekommen damit den
        # Wert, den ihr Herstellerprofil ohnehin trägt. ``legacy`` rechnet wie
        # 0.5.0, sonst hielte die Einordnung einer Datei von damals ihre
        # 0,449 mm für eine eigene Wahl und schriebe sie über das Profil.
        first_layer_line_width = (
            round(printer.nozzle_diameter * printer.first_layer_line_factor, 3)
            if printer.first_layer_line_factor is not None and not legacy
            else round(printer.extrusion_width * 1.07, 3)
        )
    # Eine Probe gilt auf dem Raster, auf dem sie gedruckt wurde
    # (``Profile.has_process_calibration``): „Fein" mit 0,12 mm ist ein anderes
    # als die Probe mit 0,20 mm, und dann stützt der Slicer ab der Grenze ohne
    # Messung.
    process = (
        profile
        if printer.is_resin
        else replace(profile, printer=replace(printer, layer_height=round(layer_height, 3)))
    )

    settings = PrintSettings(
        id=f"{quality}-{profile.material.id}",
        # Der Name, unter dem der Slicer den Prozess zeigt („Solidon Fein · PLA"),
        # in der Sprache der Oberfläche.
        title=f"{quality_presets().get(quality, quality)} · {profile.material.title}",
        quality=quality,
        layers=LayerSettings(
            layer_height=round(layer_height, 3),
            first_layer_height=round(first_layer, 3),
            line_width=line_width,
            first_layer_line_width=first_layer_line_width,
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
            **fan_curve(profile.material.id, float(stuff.get("fan_speed", 1.0))),
            bridge_fan_speed=float(stuff.get("bridge_fan_speed", 1.0)),
            disable_first_layers=int(stuff.get("disable_fan_layers", 1)),
            minimum_layer_time=float(stage["minimum_layer_time"]),
        ),
        speed=SpeedSettings(
            outer_wall=paced("speed_outer_wall", printer.speed_outer_wall),
            inner_wall=paced("speed_inner_wall", printer.speed_inner_wall),
            infill=paced("speed_infill", printer.speed_infill),
            top_surface=paced("speed_top_surface", printer.speed_top_surface),
            first_layer=paced("speed_first_layer", printer.speed_first_layer),
            bridge=paced("speed_bridge", printer.speed_bridge),
            acceleration=paced("acceleration", printer.acceleration),
            outer_wall_acceleration=paced(
                "outer_wall_acceleration", printer.outer_wall_acceleration
            ),
            # Die Leerfahrt gehört dem Drucker, nicht der Stufe
            # (``PrinterProfile.travel_speed``); ohne Angabe gilt die Vorgabe.
            **({} if printer.travel_speed is None or legacy else {"travel": printer.travel_speed}),
        ),
        # Der Slicer stützt ab derselben Grenze, mit der die Schichtanalyse
        # rechnet — gemessen, sonst die des Druckers, sonst die Startregel
        # (``Profile.overhang_limit_degrees``). Bis zum 27.09.2026 stand hier
        # immer die Startregel, auch über einer Kalibrierung, und sie ersetzte
        # in jeder Übergabe den Winkel des Herstellers.
        support=SupportSettings(threshold_angle=process.overhang_limit_degrees),
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
            # Der Materialwert gilt für ein Standard-Hotend; der Drucker sagt,
            # wie viel mehr seines mit PLA fördert (``PrinterProfile.flow_factor``)
            # — und nur mit PLA, siehe :data:`HOTEND_FLOW_MATERIAL`.
            max_flow=float(stuff.get("max_flow", 12.0))
            * (printer.flow_factor if profile.material.id == HOTEND_FLOW_MATERIAL else 1.0),
        ),
    )
    return settings if legacy else _within_flow(settings)


def bead_area(settings: PrintSettings, *, first_layer: bool = False) -> float:
    """Der Querschnitt einer Bahn in mm²: Schichthöhe mal Bahnbreite.

    ``first_layer=True`` nimmt die Maße der ersten Schicht — sie ist höher und
    breiter als alle darüber und fördert je Millimeter ein Drittel mehr.
    """
    layers = settings.layers
    if first_layer:
        return layers.first_layer_height * layers.first_layer_line_width
    return layers.layer_height * layers.line_width


def flow_speed_limit(settings: PrintSettings, *, first_layer: bool = False) -> float:
    """Das schnellste ganze Tempo in mm/s, bei dem die Düse den Volumenstrom
    des Filaments hält — ``math.inf``, wo keiner gilt.

    Abgerundet und nicht gerundet: Ein aufgerundeter Wert läge wieder über
    der Grenze, um die es geht.
    """
    limit = settings.filament.max_flow
    area = bead_area(settings, first_layer=first_layer)
    if limit <= 0.0 or area <= 0.0:
        return math.inf
    return float(math.floor(limit / area))


def _within_flow(settings: PrintSettings) -> PrintSettings:
    """Kein Tempo der Auflösung fördert mehr, als das Filament fließt.

    Die Herstellertempi sind für das schnellste Filament des Herstellers
    geschrieben; der Bambu A1 fährt Innenwände mit 300 mm/s, und mit 0,2 auf
    0,42 mm sind das 25 mm³/s gegen 12 für allgemeines PLA. Der Slicer bremst
    dann selbst auf den Volumenstrom — steht das schnellere Tempo in der Datei,
    meldet die Beratung (``advise._from_flow``) an jedem Teil dieselben vier
    Warnungen, obwohl niemand etwas eingestellt hat. Unter dem kleinsten
    einstellbaren Tempo wird nichts gesetzt; das meldet die Beratung.
    """
    limits = {first: flow_speed_limit(settings, first_layer=first) for first in (False, True)}
    if min(limits.values()) < 1.0:
        return settings
    speed = settings.speed
    capped = {
        name: min(float(getattr(speed, name)), limits[first]) for name, first in FLOW_BOUND_SPEEDS
    }
    return replace(settings, speed=replace(speed, **capped))


def _paced(stage: Mapping[str, Any], key: str, printer_value: float | None) -> float:
    """Ein Tempo der Stufe — oder das des Druckers, im Verhältnis der Stufe.

    Die Stufen sind für einen allgemeinen Drucker geschrieben. Kennt das
    Druckerprofil sein Standardtempo (``PrinterProfile.speed_*``), gilt es für
    „Standard", und jede andere Stufe behält ihr Verhältnis dazu: „Fein" fährt
    die Außenwand bei Solidon mit 30 statt 40, also ein Viertel langsamer —
    am Centauri Carbon 2 dann 120 statt 160.
    """
    value = float(stage[key])
    if printer_value is None:
        return value
    standard = float(_quality_table("standard")[key])
    return round(printer_value * value / standard, 1)


class FanCurve(TypedDict):
    """Was :func:`fan_curve` über die Lüfterkurve sagt — mit den Feldnamen von
    :class:`~app.core.types.CoolingSettings`."""

    minimum_fan_speed: float
    fan_below_layer_time: float


def fan_curve(material_id: str, upper: float) -> FanCurve:
    """Unteres Ende und Schwelle der Lüfterkurve dieses Materials (§29).

    ``upper`` ist das obere Ende, und das untere steht höchstens so hoch. Ein
    Material ohne eigenen unteren Wert läuft fest auf dem oberen: Eine Kurve,
    die niemand angegeben hat, wird nicht erfunden.

    Zwei Aufrufer, eine Herleitung: :func:`resolve` für ein neues Projekt, und
    das Lesen einer Projektdatei von vor dem 23.09.2026, deren gespeicherter
    einziger Lüfterwert das obere Ende war
    (:func:`app.core.scene.serialise.print_settings_from_data`).
    """
    stuff = _material_table(material_id)
    lower = float(stuff.get("minimum_fan_speed", stuff.get("fan_speed", upper)))
    below = float(stuff.get("fan_below_layer_time", CoolingSettings().fan_below_layer_time))
    return {"minimum_fan_speed": min(lower, upper), "fan_below_layer_time": below}


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
#: die Slicer-Zuordnung benutzen dieselbe Schreibweise — und zwar diese hier:
#: ``print_settings_dialog`` baut seine Reiter daraus. Öffentlich, weil eine
#: abgeschriebene Kopie dort den Dialog beim elften Bereich still einen Reiter
#: verlieren ließe, ohne dass ein Test es merkt.
GROUPS: Final = (
    "layers",
    "shell",
    "infill",
    "filament",
    "temperature",
    "cooling",
    "speed",
    "support",
    "adhesion",
    "retraction",
)


def read_path(settings: PrintSettings, path: str) -> Any:
    """Einen Wert über seinen Punktpfad lesen, etwa ``support.style``."""
    group, _dot, name = path.partition(".")
    if not name or group not in GROUPS:
        raise ValidationError(
            field="path",
            detail=_("Dieser Pfad zeigt auf keine Einstellung."),
            values={"path": path, "groups": list(GROUPS)},
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


# --- Herkunft: eigene Wahl, Vorschlag, Grundlage -------------------------------
#
# Konzept Herstellerprofil, Entscheidung A (27.09.2026): Die Gruppen tragen
# immer einen vollständigen Satz, aber nur die Pfade in ``chosen`` und
# ``accepted`` sollen vom Profil des Herstellers abweichen. Die Funktionen
# darunter sind die einzigen, die diese Mengen setzen — ``with_path`` bleibt
# herkunftslos, denn eine Rücklesung aus dem Herstellerprofil ist keine Wahl.


def same_value(a: object, b: object) -> bool:
    """Ob zwei Einstellungswerte dasselbe sagen.

    Fließkomma nie mit ``==`` (Regel 6). Ein Wahrheitswert ist in Python eine
    Zahl: Ohne die Abfrage davor wäre ``True`` gleich ``1,0``, und ein Haken,
    den jemand gesetzt hat, sähe aus wie eine unveränderte Eins.
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, int | float) and isinstance(b, int | float):
        return is_close(float(a), float(b), EPS_SETTING)
    return bool(a == b)


def all_paths() -> tuple[str, ...]:
    """Jeder Punktpfad, den ein :class:`PrintSettings` führt, in Gruppenfolge."""
    template = PrintSettings()
    return tuple(
        f"{group}.{entry.name}" for group in GROUPS for entry in fields(getattr(template, group))
    )


def with_choice(settings: PrintSettings, path: str, value: Any) -> PrintSettings:
    """Ein Wert, den der Kunde selbst gesetzt hat — er geht zum Slicer.

    War der Pfad ein übernommener Vorschlag, wird er zur eigenen Wahl: Die
    eigene Wahl gilt der ganzen Platte, ein Vorschlag soll dem Körper gelten,
    der ihn verlangt (Entscheidung G, gebaut mit Stufe E).
    """
    changed = with_path(settings, path, value)
    changed = replace(
        changed,
        chosen=changed.chosen | {path},
        accepted=changed.accepted - {path},
        plate_choices=_without_plate_choice(changed, path),
    )
    return _with_a_measure(changed, path, with_choice)


def with_accepted(settings: PrintSettings, path: str, value: Any) -> PrintSettings:
    """Ein Wert aus einem übernommenen Vorschlag — er geht zum Slicer. Gelten
    soll er dem Körper, der ihn verlangt; bis Stufe E gilt er der Platte."""
    plate = _without_plate_choice(settings, path)
    if path in settings.chosen:
        # Die eigene Wahl bleibt der Wert der Platte (RM-289, B2).
        plate = tuple(sorted((*plate, (path, read_path(settings, path)))))
    elif (own := plate_choice(settings, path)) is not None:
        plate = tuple(sorted((*plate, (path, own[0]))))
    changed = with_path(settings, path, value)
    changed = replace(
        changed,
        accepted=changed.accepted | {path},
        chosen=changed.chosen - {path},
        plate_choices=plate,
    )
    return _with_a_measure(changed, path, with_accepted)


def plate_choice(settings: PrintSettings, path: str) -> tuple[object] | None:
    """Die eigene Wahl der Platte unter einem übernommenen Pfad — als Einertupel,
    damit auch ``None`` und ``False`` als Wert erkennbar bleiben."""
    for own, value in settings.plate_choices:
        if own == path:
            return (value,)
    return None


def _without_plate_choice(settings: PrintSettings, path: str) -> tuple[tuple[str, object], ...]:
    return tuple(entry for entry in settings.plate_choices if entry[0] != path)


def reset(settings: PrintSettings, path: str, base: PrintSettings) -> PrintSettings:
    """*Zurücksetzen* am Feld: Ein übernommener Vorschlag über einer eigenen
    Wahl kehrt zu dieser Wahl zurück, alles andere zur Grundlage (RM-289, B2)."""
    own = plate_choice(settings, path)
    if path in settings.accepted and own is not None:
        return with_choice(settings, path, own[0])
    return without_choice(settings, path, base)


def for_the_plate(settings: PrintSettings, path: str, base: PrintSettings) -> PrintSettings:
    """Was die Platte unter einem Vorschlag je Teil bekommt (RM-289, B2).

    Die eigene Wahl, die vor der Übernahme galt, sonst die Grundlage. Die
    Trennung je Teil (``handover.split_for_parts``) fragt nur hier.
    """
    own = plate_choice(settings, path)
    if own is None:
        return without_choice(settings, path, base)
    return with_choice(settings, path, own[0])


#: Die Haftungsmaße je Art — **die eine Tabelle** für Maß, Sichtbarkeit und
#: Übergabe (RM-432). Das erste ist das Maß, ohne das die Art nichts tut; der
#: Skirt-Abstand wirkt nur mit Skirt-Runden.
ADHESION_PATHS: Final[dict[str, tuple[str, ...]]] = {
    "skirt": ("adhesion.skirt_loops", "adhesion.skirt_distance"),
    "brim": ("adhesion.brim_width", "adhesion.brim_gap"),
    "raft": ("adhesion.raft_layers", "adhesion.raft_gap"),
}

#: Das Maß, ohne das eine Haftungsart nichts tut.
ADHESION_MEASURES: Final = {kind: paths[0] for kind, paths in ADHESION_PATHS.items()}


def adhesion_kinds(kind: str) -> frozenset[str]:
    """Welche Haftungsarten bei dieser Wahl mit ihren Maßen wirken.

    Der Auto-Brim der Orca-Familie misst mit der Brimbreite — die einzige
    Ausnahme, und sie steht nur hier: Sichtbarkeit im Dialog
    (:func:`inactive_paths`) und die Übergabe
    (``handover._only_chosen_adhesion``) fragen beide diese Funktion.
    """
    if kind == "auto":
        return frozenset({"brim"})
    return frozenset({kind}) & frozenset(ADHESION_PATHS)


#: Kleinster positiver Wert im ganzzahligen Prozentfeld. Null lässt sich in
#: PrusaSlicer und der Orca-Familie nicht als Stützfüllung schreiben (RM-475).
LEAST_SUPPORT_DENSITY: Final = 0.01

#: Die Detailwerte der Stützen — sie wirken nur, wenn Stützen gedruckt werden.
SUPPORT_DETAILS: Final = (
    "support.placement",
    "support.threshold_angle",
    "support.z_gap",
    "support.xy_gap",
    "support.density",
    "support.interface_layers",
    "support.bottom_interface_layers",
    "support.interface_spacing",
    "support.tree_walls",
    "support.block_channels",
    "support.spare_ledges",
    "cooling.support_interface_cooling",
)

#: Alle Haftungsmaße, in der Reihenfolge des Dialogs — abgeleitet aus
#: :data:`ADHESION_PATHS`, keine zweite Tabelle.
ADHESION_DETAILS: Final[tuple[str, ...]] = tuple(
    path for paths in ADHESION_PATHS.values() for path in paths
)


def inactive_paths(
    support_style: str, adhesion_kind: str, *, also: frozenset[str] = frozenset()
) -> frozenset[str]:
    """Welche Einstellungen bei dieser Wahl nichts tun (RM-341).

    Die eine Stelle für Sichtbarkeit, Sperre und Suche im Dialog — vorher drei
    Fassungen, und alle kannten nur „aus“: Bei *Brim* blieben Skirt- und
    Raft-Maße sichtbar, obwohl die Übergabe sie nullt, und ein Wert über der
    Grenze in einem wirkungslosen Feld sperrte *Slicen*.

    ``adhesion_kind`` ist die Art, die **übergeben** wird — bei PrusaSlicer und
    Cura heißt „Automatisch“ die Art des Materials
    (``handover.effective_adhesion``, RM-432). ``also`` sind weitere Arten, die
    die Übergabe stehen lässt (eine Prusa-Grundlage mit Skirt und Brim).
    """
    inactive = set(SUPPORT_DETAILS) if support_style == "none" else set()
    active = adhesion_kinds(adhesion_kind) | also
    inactive.update(
        path for kind, paths in ADHESION_PATHS.items() if kind not in active for path in paths
    )
    return frozenset(inactive)


def _with_a_measure(
    settings: PrintSettings,
    path: str,
    mark: Callable[[PrintSettings, str, Any], PrintSettings],
) -> PrintSettings:
    """Eine gewählte Haftungsart bekommt ihr Maß (Review Stufe A+B, F4).

    Elegoos Standardprozess führt null Skirt-Runden und null Raft-Schichten.
    Wer darauf „Raft" wählte, schrieb die Art und behielt das Maß des
    Herstellers — gedruckt wurde kein Raft. Steht das Maß auf null, gilt
    Solidons Vorgabe, mit derselben Herkunft wie die Art.
    """
    if path != "adhesion.kind":
        return settings
    measure = ADHESION_MEASURES.get(settings.adhesion.kind)
    if measure is None:
        return settings
    current = read_path(settings, measure)
    if isinstance(current, int | float) and current > 0:
        return settings
    return mark(settings, measure, read_path(PrintSettings(), measure))


def without_choice(settings: PrintSettings, path: str, base: PrintSettings) -> PrintSettings:
    """Zurück zur Grundlage: der Wert aus ``base``, keine Herkunft mehr."""
    changed = with_path(settings, path, read_path(base, path))
    return replace(
        changed,
        chosen=changed.chosen - {path},
        accepted=changed.accepted - {path},
        plate_choices=_without_plate_choice(changed, path),
    )


def on_base(stored: PrintSettings, base: PrintSettings) -> PrintSettings:
    """Die wirksamen Einstellungen: die Grundlage, darüber nur, was abweichen soll.

    ``stored`` bringt seine eigene Wahl und seine übernommenen Vorschläge mit,
    dazu alles, was keine Druckeinstellung im engeren Sinn ist — Stufe,
    Übergabeart, Spulen und Slotprofile. Jeder andere Wert kommt aus ``base``.
    Ein gespeicherter Wert ohne Herkunft war einmal Grundlage und ist es
    nicht mehr, wenn sich die Grundlage geändert hat: ein anderer Drucker,
    ein anderer Prozess, ein Update des Herstellerprofils.
    """
    result = base
    for path in sorted(stored.explicit):
        result = with_path(result, path, read_path(stored, path))
    # Kennung und Titel beschreiben Stufe und Material der Grundlage —
    # nach einem Wechsel stand sonst „Standard · PLA" über PETG-Werten
    # (Review Stufe A+B, H7), die Verwechslung, vor der die Übergabe warnt.
    carried = {
        entry.name: getattr(stored, entry.name)
        for entry in fields(PrintSettings)
        if entry.name not in GROUPS and entry.name not in ("id", "title")
    }
    return replace(result, **carried)


def own_part(settings: PrintSettings) -> tuple[object, ...]:
    """Was an diesen Einstellungen dem Projekt gehört — ohne die Grundlage.

    Die Grundlage wechselt mit dem Herstellerprofil, das gerade darunterliegt:
    ein anderer Prozess, eine andere Platte, ein Update des Slicers. Wer nur
    nachsieht, hat damit nichts am Projekt geändert. Was sich ändert, wenn
    jemand etwas **tut**, steht hier: die Werte der eigenen Wahl und der
    übernommenen Vorschläge, dazu Stufe, Übergabeart und Spulen.
    """
    carried = tuple(
        (entry.name, getattr(settings, entry.name))
        for entry in fields(PrintSettings)
        if entry.name not in GROUPS
    )
    deviating = tuple((path, read_path(settings, path)) for path in sorted(settings.explicit))
    return carried + deviating


def legacy_choices(stored: PrintSettings, *references: PrintSettings) -> frozenset[str]:
    """Welche Werte einer Datei vor Format 36 eine eigene Wahl waren (Entscheidung E).

    Eine ältere Datei kennt keine Herkunft, und ihr voller Satz belegt keine
    Entscheidung: Bis 0.5.1 schrieben die Übergabe, die Filamentzuweisung und
    das Rückgängigmachen den aufgelösten Satz ungefragt ins Projekt. Als
    eigene Wahl gilt deshalb nur, was **keinem** der ``references`` gleicht —
    der heutigen Auflösung für Drucker, Material und Stufe des Projekts und
    der, mit der die schreibende Version auflöste (``resolve(...,
    legacy=True)``) — **und auch nicht** der Vorgabe der Dataclass. So
    fallen die alten Tabellenwerte heraus: die 40 mm/s von vor dem 25.09.2026,
    die die Vorgabe der Dataclass sind (RM-256), und die Tempi der Stufen
    Fein, Entwurf und Belastbar aus 0.5.0 (Review Stufe A+B, F3). Was jemand
    selbst eingetragen hat, bleibt.
    """
    compared = (*references, PrintSettings())
    return frozenset(
        path
        for path in all_paths()
        if not any(
            same_value(read_path(stored, path), read_path(reference, path))
            for reference in compared
        )
    )
