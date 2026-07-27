"""Printer and material profiles (Bauplan §38).

Profiles are never hard-coded. The shipped starting set lives in ``data/*.toml``
and is read like the standard parts table; own profiles are derived from it and
read from the user configuration directory.

Tolerances are references, not numbers (AGENTS.md rule 7): an operation stores
``auto:petg`` and :func:`resolve_tolerance` looks it up, which is what makes
calibration (§28.3) reach existing projects.
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
    Tolerance,
)
from app.i18n import _

_log = get_logger(__name__)

DEFAULT_PRINTER: Final = "generic-220"
DEFAULT_MATERIAL: Final = "pla"

_DATA_DIR: Final = Path(__file__).parent / "data"

_printers: dict[str, PrinterProfile] | None = None
_materials: dict[str, MaterialProfile] | None = None


def _read_table(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


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
    return profiles


def _load_materials() -> dict[str, MaterialProfile]:
    profiles: dict[str, MaterialProfile] = {}
    for path in (_DATA_DIR / "materials.toml", user_profiles_dir() / "materials.toml"):
        if not path.is_file():
            continue
        for identifier, table in _read_table(path).items():
            profiles[identifier] = _material_from_table(identifier, table, path)
    return profiles


def printer_profiles() -> Mapping[str, PrinterProfile]:
    """All known printer profiles, shipped ones plus the user's own."""
    global _printers
    if _printers is None:
        _printers = _load_printers()
        _log.info("loaded %d printer profiles", len(_printers))
    return _printers


def material_profiles() -> Mapping[str, MaterialProfile]:
    """All known material profiles, shipped ones plus the user's own."""
    global _materials
    if _materials is None:
        _materials = _load_materials()
        _log.info("loaded %d material profiles", len(_materials))
    return _materials


def reload() -> None:
    """Drop the cache, for example after the user edited a profile."""
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
    """The pair a scene is computed for."""
    return Profile(printer=printer(printer_id), material=material(material_id))


#: Which material figure a fit kind reads (§14). Documented here, not scattered.
_FIT_FIELD: Final[dict[FitKind, str]] = {
    "clearance": "clearance",
    "press": "press",
    "thread": "hole_compensation",
    "flush": "",
}


def resolve_tolerance(value: Tolerance, kind: FitKind, profile: Profile) -> float:
    """Turn a tolerance reference into millimetres.

    A number passes through. ``auto:`` uses the scene material, ``auto:petg``
    a named one — so a project can hold a fit for a material it is not currently
    set to.
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
