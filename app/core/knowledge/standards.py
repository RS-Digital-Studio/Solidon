"""Standard part dimensions (Bauplan §24.2).

"Hole for an M4 heat-set insert" has to be something one looks up, not
something one guesses. The numbers live in ``data/standards.toml`` and are read
like the printer profiles; a corrected value needs no release.

Nothing here interprets. A part asks for the clearance hole of an M4 and gets
4.5 mm; what it does with that — adding the material tolerance, a chamfer, an
oversize — is the part's business and stays where it can be tested.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from app.core.errors import ValidationError
from app.core.log import get_logger
from app.i18n import _

_log = get_logger(__name__)

_DATA_FILE: Final = Path(__file__).parent / "data" / "standards.toml"

_tables: Tables | None = None


@dataclass(frozen=True, slots=True)
class Screw:
    """One metric screw, with the holes that belong to it."""

    size: str
    nominal: float
    clearance: float
    """Through hole, medium fit."""
    tap: float
    """Core hole for cutting a thread."""
    head: float
    head_height: float
    countersink: float
    hex: float
    pitch: float


@dataclass(frozen=True, slots=True)
class Nut:
    size: str
    width: float
    """Across the flats — the dimension a nut trap is built from."""
    height: float


@dataclass(frozen=True, slots=True)
class Washer:
    size: str
    inner: float
    outer: float
    thickness: float


@dataclass(frozen=True, slots=True)
class Insert:
    """A heat-set insert and the hole it is pressed into."""

    size: str
    outer: float
    length: float
    hole: float
    note: str = ""


@dataclass(frozen=True, slots=True)
class Magnet:
    size: str
    diameter: float
    height: float


@dataclass(frozen=True, slots=True)
class Bearing:
    size: str
    inner: float
    outer: float
    width: float


@dataclass(frozen=True, slots=True)
class ProfileSlot:
    """An aluminium extrusion slot."""

    size: str
    slot: float
    core: float
    screw: str


@dataclass(frozen=True, slots=True)
class Tube:
    size: str
    outer: float
    inner: float = 0.0
    note: str = ""


@dataclass(frozen=True, slots=True)
class Tables:
    """Everything the table holds, with its version."""

    version: str
    screws: dict[str, Screw]
    nuts: dict[str, Nut]
    washers: dict[str, Washer]
    inserts: dict[str, Insert]
    magnets: dict[str, Magnet]
    bearings: dict[str, Bearing]
    profiles: dict[str, ProfileSlot]
    tubes: dict[str, Tube]


def load(path: Path | None = None) -> Tables:
    """Read the tables. Cached — parts ask for them on every call."""
    global _tables
    if _tables is not None and path is None:
        return _tables

    with (path or _DATA_FILE).open("rb") as stream:
        data: dict[str, Any] = tomllib.load(stream)

    tables = Tables(
        version=str(data.get("version", "0")),
        screws=_index(Screw, data.get("screws", ())),
        nuts=_index(Nut, data.get("nuts", ())),
        washers=_index(Washer, data.get("washers", ())),
        inserts=_index(Insert, data.get("inserts", ())),
        magnets=_index(Magnet, data.get("magnets", ())),
        bearings=_index(Bearing, data.get("bearings", ())),
        profiles=_index(ProfileSlot, data.get("profiles", ())),
        tubes=_index(Tube, data.get("tubes", ())),
    )
    if path is None:
        _tables = tables
    _log.info("standards %s with %d screw sizes", tables.version, len(tables.screws))
    return tables


def _index(kind: type, entries: Any) -> dict[str, Any]:
    return {str(entry["size"]): kind(**entry) for entry in entries}


def screw(size: str) -> Screw:
    """One screw size, or a clear error naming what is known."""
    found: Screw = _lookup(load().screws, size, "screw")
    return found


def nut(size: str) -> Nut:
    found: Nut = _lookup(load().nuts, size, "nut")
    return found


def washer(size: str) -> Washer:
    found: Washer = _lookup(load().washers, size, "washer")
    return found


def insert(size: str) -> Insert:
    found: Insert = _lookup(load().inserts, size, "insert")
    return found


def magnet(size: str) -> Magnet:
    found: Magnet = _lookup(load().magnets, size, "magnet")
    return found


def bearing(size: str) -> Bearing:
    found: Bearing = _lookup(load().bearings, size, "bearing")
    return found


def profile_slot(size: str) -> ProfileSlot:
    found: ProfileSlot = _lookup(load().profiles, size, "profile")
    return found


def tube(size: str) -> Tube:
    found: Tube = _lookup(load().tubes, size, "tube")
    return found


def screw_sizes() -> tuple[str, ...]:
    """The sizes a parameter offers as choices."""
    return tuple(load().screws)


def nut_sizes() -> tuple[str, ...]:
    return tuple(load().nuts)


def insert_sizes() -> tuple[str, ...]:
    return tuple(load().inserts)


def magnet_sizes() -> tuple[str, ...]:
    return tuple(load().magnets)


def tube_sizes() -> tuple[str, ...]:
    return tuple(load().tubes)


def _lookup(table: dict[str, Any], size: str, what: str) -> Any:
    if size not in table:
        raise ValidationError(
            field=what,
            detail=_("Diese Größe steht nicht in der Normteiltabelle."),
            values={"size": size, "known": ", ".join(sorted(table))},
        )
    return table[size]
