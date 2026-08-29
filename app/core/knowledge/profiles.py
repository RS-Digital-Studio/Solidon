"""Drucker- und Materialprofile (Bauplan §38).

Profile stehen nie fest im Code. Der mitgelieferte Startbestand liegt in
``data/*.toml`` und wird gelesen wie die Normteiltabelle; eigene Profile
leiten sich daraus ab und kommen aus dem Konfigurationsverzeichnis des
Nutzers.

Toleranzen sind Verweise, keine Zahlen (AGENTS.md Regel 7): eine Operation
speichert ``auto:petg``, und :func:`resolve_tolerance` schlägt es nach — genau
das lässt die Kalibrierung (§28.3) bestehende Projekte erreichen.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from app.core.errors import ValidationError
from app.core.log import get_logger
from app.core.paths import user_profiles_dir
from app.core.types import (
    AUTO_TOLERANCE_PREFIX,
    FitKind,
    MaterialProfile,
    PrinterProfile,
    Profile,
    SceneObject,
    Tolerance,
)
from app.i18n import _, sort_key

_log = get_logger(__name__)

DEFAULT_PRINTER: Final = "generic-220"
DEFAULT_MATERIAL: Final = "pla"

_DATA_DIR: Final = Path(__file__).parent / "data"

_printers: dict[str, PrinterProfile] | None = None
_materials: dict[str, MaterialProfile] | None = None


def _read_table(path: Path) -> dict[str, dict[str, Any]]:
    try:
        with path.open("rb") as stream:
            return tomllib.load(stream)
    except tomllib.TOMLDecodeError as problem:
        # Derselbe Leser liest die mitgelieferten Tabellen und die des
        # Nutzers — und die zweiten sind von Hand geschrieben. Eine fehlende
        # Klammer war sonst ein Startabbruch mit rohem Stapelabzug, denn
        # `printer_profiles()` läuft beim Fensteraufbau (Regel 17, §33.1).
        raise ValidationError(
            title=_("Diese Profildatei lässt sich nicht lesen."),
            field="file",
            detail=str(problem),
            constraint="toml",
            values={"file": str(path)},
        ) from problem


def _printer_from_table(identifier: str, table: Mapping[str, Any], source: Path) -> PrinterProfile:
    volume = table.get("build_volume")
    if not isinstance(volume, list) or len(volume) != 3:
        raise ValidationError(
            field=f"{identifier}.build_volume",
            detail=_("Der Bauraum muss aus drei Maßen bestehen."),
            values={"file": str(source)},
        )
    nozzle = float(table.get("nozzle_diameter", 0.4))
    return PrinterProfile(
        id=identifier,
        title=str(table.get("title", identifier)),
        build_volume=(float(volume[0]), float(volume[1]), float(volume[2])),
        nozzle_diameter=nozzle,
        layer_height=float(table.get("layer_height", 0.2)),
        extrusion_width=float(table.get("extrusion_width", round(nozzle * 1.05, 3))),
        enclosed=bool(table.get("enclosed", False)),
        bed_temperature_max=int(table.get("bed_temperature_max", 100)),
        nozzle_temperature_max=int(table.get("nozzle_temperature_max", 260)),
        vendor=str(table.get("vendor", "")),
    )


def _material_from_table(
    identifier: str, table: Mapping[str, Any], source: Path
) -> MaterialProfile:
    try:
        return MaterialProfile(
            id=identifier,
            title=str(table.get("title", identifier)),
            clearance=float(table["clearance"]),
            press=float(table["press"]),
            hole_compensation=float(table["hole_compensation"]),
            elephant_foot=float(table["elephant_foot"]),
            shrinkage=float(table.get("shrinkage", 0.0)),
            calibrated=bool(table.get("calibrated", False)),
        )
    except KeyError as missing:
        raise ValidationError(
            field=f"{identifier}.{missing.args[0]}",
            detail=_("Dem Materialprofil fehlt ein Toleranzwert."),
            values={"file": str(source)},
        ) from missing


def _load_printers() -> dict[str, PrinterProfile]:
    profiles: dict[str, PrinterProfile] = {}
    for path in (_DATA_DIR / "printers.toml", user_profiles_dir() / "printers.toml"):
        if not path.is_file():
            continue
        for identifier, table in _read_table(path).items():
            profiles[identifier] = _printer_from_table(identifier, table, path)
    return _by_title(profiles)


def _load_materials() -> dict[str, MaterialProfile]:
    profiles: dict[str, MaterialProfile] = {}
    for path in (_DATA_DIR / "materials.toml", user_profiles_dir() / "materials.toml"):
        if not path.is_file():
            continue
        for identifier, table in _read_table(path).items():
            profiles[identifier] = _material_from_table(identifier, table, path)
    return _by_title(profiles)


# Drucker und Material teilen sich nur den Titel, und der genügt zum Sortieren.
def _by_title[P: (PrinterProfile, MaterialProfile)](profiles: dict[str, P]) -> dict[str, P]:
    """Nach dem Namen sortiert, den der Nutzer liest.

    In Dateireihenfolge stand die Druckerliste fast alphabetisch, mit dem
    Centauri an der Stelle, an der er nachgetragen wurde — und wer seinen
    Drucker sucht, sucht ihn dort, wo er alphabetisch hingehört. Die Ordnung
    hier statt in jeder Liste einzeln: es gibt vier, und eine davon vergisst
    es sonst.
    """
    return dict(sorted(profiles.items(), key=lambda pair: sort_key(pair[1].title)))


def printer_profiles() -> Mapping[str, PrinterProfile]:
    """Alle bekannten Druckerprofile — die mitgelieferten und die eigenen."""
    global _printers
    if _printers is None:
        _printers = _load_printers()
        _log.info("loaded %d printer profiles", len(_printers))
    return _printers


def material_profiles() -> Mapping[str, MaterialProfile]:
    """Alle bekannten Materialprofile — die mitgelieferten und die eigenen."""
    global _materials
    if _materials is None:
        _materials = _load_materials()
        _log.info("loaded %d material profiles", len(_materials))
    return _materials


def material_id_for_type(material_type: str) -> str:
    """Die eindeutige Solidon-Kennung zu einer Materialart des Slicers.

    Slicer schreiben etwa ``PETG`` oder ``TPU``, Solidon hält ``petg`` und
    ``tpu-95a``. Die Umkehrung liegt hier bei den Profilen, damit Erststart und
    Slicerübergabe dieselbe Entscheidung treffen. Leer heißt bewusst: nichts
    oder mehr als ein Profil passt — dann wird nicht geraten.
    """
    from app.core.export import slicer_keys

    wanted = material_type.strip().casefold()
    if not wanted:
        return ""
    matches = [
        identifier
        for identifier in material_profiles()
        if slicer_keys.filament_type(identifier).casefold() == wanted
    ]
    return matches[0] if len(matches) == 1 else ""


def reload() -> None:
    """Verwirft den Cache, etwa nachdem der Nutzer ein Profil bearbeitet hat."""
    global _printers, _materials
    _printers = None
    _materials = None


def printer(identifier: str) -> PrinterProfile:
    profiles = printer_profiles()
    if identifier not in profiles:
        raise ValidationError(
            field="printer",
            detail=_("Dieses Druckerprofil ist nicht bekannt."),
            values={"requested": identifier, "known": sorted(profiles)},
        )
    return profiles[identifier]


def material(identifier: str) -> MaterialProfile:
    profiles = material_profiles()
    if identifier not in profiles:
        raise ValidationError(
            field="material",
            detail=_("Dieses Materialprofil ist nicht bekannt."),
            values={"requested": identifier, "known": sorted(profiles)},
        )
    return profiles[identifier]


def make_profile(printer_id: str = DEFAULT_PRINTER, material_id: str = DEFAULT_MATERIAL) -> Profile:
    """Das Paar, für das eine Szene gerechnet wird."""
    return Profile(printer=printer(printer_id), material=material(material_id))


def for_object(profile: Profile, entry: SceneObject | None) -> Profile:
    """Das Profil, mit dem dieser eine Körper gedruckt wird (§12).

    Derselbe Drucker, das eigene Material des Körpers, wo er eines hat. Alles,
    was aus dem Material eine Länge rechnet — Spiel, Schrumpf, Elefantenfuß —
    geht hier durch statt ``profile.material`` zu lesen: eine Dichtung aus TPU
    wird also nicht gerechnet, als wäre sie das Gehäuse um sie herum.
    """
    if entry is None or entry.material is None or entry.material == profile.material.id:
        return profile
    return Profile(printer=profile.printer, material=material(entry.material))


#: Welche Materialgröße eine Passungsart liest (§14). Hier dokumentiert,
#: nicht verstreut.
_FIT_FIELD: Final[dict[FitKind, str]] = {
    "clearance": "clearance",
    "press": "press",
    "thread": "hole_compensation",
    "flush": "",
}


def resolve_tolerance(value: Tolerance, kind: FitKind, profile: Profile) -> float:
    """Macht aus einem Toleranzverweis Millimeter.

    Eine Zahl geht durch. ``auto:`` nimmt das Szenenmaterial, ``auto:petg`` ein
    benanntes — ein Projekt kann also eine Passung für ein Material halten, auf
    das es gerade nicht eingestellt ist.
    """
    if isinstance(value, int | float):
        return float(value)
    if not value.startswith(AUTO_TOLERANCE_PREFIX):
        raise ValidationError(
            field="tolerance",
            detail=_("Eine Toleranz ist entweder eine Zahl oder ein Verweis auf ein Material."),
            values={"value": value},
        )
    name = value[len(AUTO_TOLERANCE_PREFIX) :] or profile.material.id
    chosen = profile.material if name == profile.material.id else material(name)
    field_name = _FIT_FIELD[kind]
    return float(getattr(chosen, field_name)) if field_name else 0.0
