"""Normteilmaße (Bauplan §24.2).

„Loch für eine M4-Einpressbuchse" muss etwas sein, das man nachschlägt, nicht
etwas, das man rät. Die Zahlen stehen in ``data/standards.toml`` und werden
gelesen wie die Druckerprofile; ein korrigierter Wert braucht kein Release.

Nichts hier interpretiert. Ein Baustein fragt nach dem Durchgangsloch einer M4
und bekommt 4,5 mm; was er damit tut — die Materialtoleranz addieren, eine
Fase, ein Übermaß — ist Sache des Bausteins und bleibt dort, wo es sich testen
lässt.
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
    """Eine metrische Schraube, mit den Löchern, die zu ihr gehören."""

    size: str
    nominal: float
    clearance: float
    """Durchgangsloch, mittlere Passung."""
    tap: float
    """Kernloch zum Gewindeschneiden."""
    head: float
    head_height: float
    countersink: float
    hex: float
    pitch: float


@dataclass(frozen=True, slots=True)
class Nut:
    size: str
    width: float
    """Schlüsselweite — das Maß, aus dem eine Mutternfalle gebaut wird."""
    height: float


@dataclass(frozen=True, slots=True)
class Washer:
    size: str
    inner: float
    outer: float
    thickness: float


@dataclass(frozen=True, slots=True)
class Insert:
    """Eine Einpressbuchse und das Loch, in das sie gepresst wird."""

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
    """Eine Nut eines Aluminiumprofils."""

    size: str
    slot: float
    """Nutbreite außen — die Öffnung, durch die ein Hals muss."""
    core: float
    """Kerndurchmesser der Nut — die Kammer, in der ein Kopf sitzt."""
    lip: float
    """Stegdicke: wie dick das Material an der Öffnung ist. Halslänge."""
    depth: float
    """Kammertiefe von der Innenseite des Stegs bis zum Nutgrund. Kopfhöhe."""
    screw: str
    note: str = ""


@dataclass(frozen=True, slots=True)
class Board:
    """Eine Lochwand, wie sie an der Wand hängt (§24.2).

    Kein Normteil im engeren Sinn: Die Maße stehen in keiner Norm und werden
    vom Hersteller nicht veröffentlicht. Sie sind trotzdem hier richtig, denn
    sie sind **gegeben** — wer einen Einhänger baut, hat sie nicht zu wählen,
    sondern zu treffen. Genau dafür ist diese Tabelle da.
    """

    size: str
    slot_width: float
    """Breite des Lochs. Bei SKÅDIS ist es kein Rund-, sondern ein Langloch."""
    slot_height: float
    """Höhe desselben Lochs — der Weg, den ein Einhänger nach unten hat."""
    pitch: float
    """Rastermaß, in beide Richtungen gleich."""
    stagger: float = 0.0
    """Versatz der zweiten Lochschar. Null heißt ein einfaches Quadratraster."""
    thickness: float = 0.0
    """Plattendicke — was ein Haken hintergreifen muss."""
    note: str = ""


@dataclass(frozen=True, slots=True)
class Tube:
    size: str
    outer: float
    inner: float = 0.0
    note: str = ""


@dataclass(frozen=True, slots=True)
class Tables:
    """Alles, was die Tabelle hält, mit ihrer Version."""

    version: str
    screws: dict[str, Screw]
    nuts: dict[str, Nut]
    washers: dict[str, Washer]
    inserts: dict[str, Insert]
    magnets: dict[str, Magnet]
    bearings: dict[str, Bearing]
    profiles: dict[str, ProfileSlot]
    tubes: dict[str, Tube]
    boards: dict[str, Board]


def load(path: Path | None = None) -> Tables:
    """Liest die Tabellen. Gecacht — Bausteine fragen bei jedem Aufruf danach."""
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
        boards=_index(Board, data.get("boards", ())),
    )
    if path is None:
        _tables = tables
    _log.info("standards %s with %d screw sizes", tables.version, len(tables.screws))
    return tables


def _index(kind: type, entries: Any) -> dict[str, Any]:
    return {str(entry["size"]): kind(**entry) for entry in entries}


#: Welche Tabelle zu welcher Art gehört (§24.2). Sie steht hier, neben den
#: Tabellen, und nicht dort, wo nachgeschlagen wird: Diese Zuordnung lag in der
#: Agentenschicht, und damit hieß eine neue Tabelle zwei Dateien — von denen
#: man die zweite still vergisst. `tests/test_parts.py` hält beides zusammen.
TABLES: Final[dict[str, str]] = {
    "screw": "screws",
    "nut": "nuts",
    "washer": "washers",
    "insert": "inserts",
    "magnet": "magnets",
    "bearing": "bearings",
    "profile": "profiles",
    "tube": "tubes",
    "board": "boards",
}


def table(kind: str) -> dict[str, Any] | None:
    """Die Tabelle einer Art, oder None, wenn es die Art nicht gibt.

    Der eine Weg zu einer Tabelle über ihren Namen. Wer eine *Größe* sucht und
    einen Fehler mit Handlungsvorschlag will, nimmt den typisierten Zugriff
    darunter — :func:`screw`, :func:`profile_slot` und die anderen sechs.
    """
    field = TABLES.get(kind)
    if field is None:
        return None
    found: dict[str, Any] = getattr(load(), field)
    return found


def screw(size: str) -> Screw:
    """Eine Schraubengröße, oder ein klarer Fehler, der nennt, was bekannt ist."""
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


def board(size: str) -> Board:
    found: Board = _lookup(load().boards, size, "board")
    return found


def screw_sizes() -> tuple[str, ...]:
    """Die Größen, die ein Parameter zur Auswahl anbietet."""
    return tuple(load().screws)


def nut_sizes() -> tuple[str, ...]:
    return tuple(load().nuts)


def insert_sizes() -> tuple[str, ...]:
    return tuple(load().inserts)


def magnet_sizes() -> tuple[str, ...]:
    return tuple(load().magnets)


def profile_sizes() -> tuple[str, ...]:
    return tuple(load().profiles)


def tube_sizes() -> tuple[str, ...]:
    return tuple(load().tubes)


def board_sizes() -> tuple[str, ...]:
    return tuple(load().boards)


def _lookup(entries: dict[str, Any], size: str, what: str) -> Any:
    # ``entries`` und nicht ``table``: So hieß der Parameter, und seit es die
    # Funktion :func:`table` daneben gibt, verdeckte er sie.
    if size not in entries:
        raise ValidationError(
            field=what,
            detail=_("Diese Größe steht nicht in der Normteiltabelle."),
            values={"size": size, "known": ", ".join(sorted(entries))},
        )
    return entries[size]
