"""Normteilmaße (Bauplan §24.2).

„Loch für eine M4-Einpressbuchse" muss etwas sein, das man nachschlägt, nicht
etwas, das man rät. Die Zahlen stehen in ``data/standards.toml`` und werden
gelesen wie die Druckerprofile; ein korrigierter Wert braucht keine
Codeänderung.

Nichts hier interpretiert. Ein Baustein fragt nach dem Durchgangsloch einer M4
und bekommt 4,5 mm; was er damit tut — die Materialtoleranz addieren, eine
Fase, ein Übermaß — ist Sache des Bausteins und bleibt dort, wo es sich testen
lässt.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from itertools import pairwise
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
    note: str = ""


@dataclass(frozen=True, slots=True)
class Insert:
    """Eine Einpressbuchse und das Loch, in das sie gepresst wird."""

    size: str
    thread: str
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
    note: str = ""


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

    source = path or _DATA_FILE
    try:
        with source.open("rb") as stream:
            data: dict[str, Any] = tomllib.load(stream)
    except tomllib.TOMLDecodeError as problem:
        raise _invalid("file", "", "toml", source) from problem

    tables = Tables(
        version=str(data.get("version", "0")),
        screws=_index(Screw, data.get("screws", ()), "screws", source),
        nuts=_index(Nut, data.get("nuts", ()), "nuts", source),
        washers=_index(Washer, data.get("washers", ()), "washers", source),
        inserts=_index(Insert, data.get("inserts", ()), "inserts", source),
        magnets=_index(Magnet, data.get("magnets", ()), "magnets", source),
        bearings=_index(Bearing, data.get("bearings", ()), "bearings", source),
        profiles=_index(ProfileSlot, data.get("profiles", ()), "profiles", source),
        tubes=_index(Tube, data.get("tubes", ()), "tubes", source),
        boards=_index(Board, data.get("boards", ()), "boards", source),
    )
    _validate(tables, source)
    if path is None:
        _tables = tables
    _log.info("standards %s with %d screw sizes", tables.version, len(tables.screws))
    return tables


def _index(kind: type, entries: Any, table_name: str, source: Path) -> dict[str, Any]:
    """Baut einen Index, ohne doppelte Größen still zu überschreiben."""
    indexed: dict[str, Any] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise _invalid(table_name, "", "entry", source)
        size = str(raw.get("size", "")).strip()
        if not size or size in indexed:
            raise _invalid(table_name, size, "unique_size", source)
        values = {**raw, "size": size}
        try:
            indexed[size] = kind(**values)
        except (TypeError, ValueError) as problem:
            raise _invalid(table_name, size, "fields", source) from problem
    return indexed


def _invalid(table_name: str, size: str, constraint: str, source: Path) -> ValidationError:
    """Ein Tabellenfehler mit Fundstelle und einem meldbaren Ausweg."""
    return ValidationError(
        field=f"{table_name}.{size}.{constraint}".strip("."),
        detail=_("Die Normteiltabelle enthält einen widersprüchlichen Eintrag."),
        constraint="toml",
        values={"file": str(source), "size": size, "reason": constraint},
    )


def _finite_positive(
    value: Any,
    table_name: str,
    size: str,
    field: str,
    source: Path,
    *,
    zero: bool = False,
) -> float:
    """Prüft ein Maß, bevor daraus Geometrie entsteht."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(table_name, size, f"{field}_number", source)
    number = float(value)
    below_limit = number < 0.0 if zero else number <= 0.0
    if not math.isfinite(number) or below_limit:
        raise _invalid(table_name, size, f"{field}_positive", source)
    return number


def _ordered(
    values: tuple[float, ...], table_name: str, size: str, constraint: str, source: Path
) -> None:
    if any(left >= right for left, right in pairwise(values)):
        raise _invalid(table_name, size, constraint, source)


def _validate(tables: Tables, source: Path) -> None:
    """Prüft Beziehungen, die ein einzelner Datentyp nicht ausdrückt."""
    for screw in tables.screws.values():
        measures = {
            field: _finite_positive(getattr(screw, field), "screws", screw.size, field, source)
            for field in (
                "nominal",
                "clearance",
                "tap",
                "head",
                "head_height",
                "countersink",
                "hex",
                "pitch",
            )
        }
        _ordered(
            (measures["tap"], measures["nominal"], measures["clearance"]),
            "screws",
            screw.size,
            "tap_nominal_clearance",
            source,
        )
        if measures["head"] < measures["nominal"] or measures["countersink"] < measures["head"]:
            raise _invalid("screws", screw.size, "head_diameters", source)

    for nut in tables.nuts.values():
        _finite_positive(nut.width, "nuts", nut.size, "width", source)
        _finite_positive(nut.height, "nuts", nut.size, "height", source)

    for washer in tables.washers.values():
        inner = _finite_positive(washer.inner, "washers", washer.size, "inner", source)
        outer = _finite_positive(washer.outer, "washers", washer.size, "outer", source)
        _finite_positive(washer.thickness, "washers", washer.size, "thickness", source)
        _ordered((inner, outer), "washers", washer.size, "inner_outer", source)

    for insert in tables.inserts.values():
        hole = _finite_positive(insert.hole, "inserts", insert.size, "hole", source)
        outer = _finite_positive(insert.outer, "inserts", insert.size, "outer", source)
        _finite_positive(insert.length, "inserts", insert.size, "length", source)
        if hole >= outer:
            raise _invalid("inserts", insert.size, "hole_outer", source)
        if insert.thread not in tables.screws:
            raise _invalid("inserts", insert.size, "known_thread", source)

    for magnet in tables.magnets.values():
        _finite_positive(magnet.diameter, "magnets", magnet.size, "diameter", source)
        _finite_positive(magnet.height, "magnets", magnet.size, "height", source)

    for bearing in tables.bearings.values():
        inner = _finite_positive(bearing.inner, "bearings", bearing.size, "inner", source)
        outer = _finite_positive(bearing.outer, "bearings", bearing.size, "outer", source)
        _finite_positive(bearing.width, "bearings", bearing.size, "width", source)
        _ordered((inner, outer), "bearings", bearing.size, "inner_outer", source)

    for profile in tables.profiles.values():
        slot = _finite_positive(profile.slot, "profiles", profile.size, "slot", source)
        core = _finite_positive(profile.core, "profiles", profile.size, "core", source)
        _finite_positive(profile.lip, "profiles", profile.size, "lip", source)
        _finite_positive(profile.depth, "profiles", profile.size, "depth", source)
        _ordered((slot, core), "profiles", profile.size, "slot_core", source)
        if profile.screw not in tables.screws:
            raise _invalid("profiles", profile.size, "known_screw", source)

    for tube in tables.tubes.values():
        outer = _finite_positive(tube.outer, "tubes", tube.size, "outer", source)
        inner = _finite_positive(tube.inner, "tubes", tube.size, "inner", source, zero=True)
        if inner >= outer:
            raise _invalid("tubes", tube.size, "inner_outer", source)

    for board in tables.boards.values():
        _finite_positive(board.slot_width, "boards", board.size, "slot_width", source)
        _finite_positive(board.slot_height, "boards", board.size, "slot_height", source)
        _finite_positive(board.pitch, "boards", board.size, "pitch", source)
        _finite_positive(board.stagger, "boards", board.size, "stagger", source, zero=True)
        _finite_positive(board.thickness, "boards", board.size, "thickness", source)


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


def lookup(kind: str, size: str) -> Any:
    """Schlägt eine Größe unabhängig von Schreibweise und Leerraum nach.

    Dieser untypisierte Zugang ist für Oberflächen gedacht, die ihre
    Tabellenart erst zur Laufzeit kennen — etwa das Agentenwerkzeug. Bausteine
    verwenden weiter :func:`screw`, :func:`bearing` und die anderen
    typisierten Zugänge darunter.
    """
    entries = table(kind)
    if entries is None:
        raise ValidationError(
            field="kind",
            detail=_("Diese Tabelle gibt es nicht"),
            values={"kind": kind, "known": ", ".join(TABLES)},
        )
    return _lookup(entries, size, kind)


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


def washer_sizes() -> tuple[str, ...]:
    return tuple(load().washers)


def magnet_sizes() -> tuple[str, ...]:
    return tuple(load().magnets)


def bearing_sizes() -> tuple[str, ...]:
    return tuple(load().bearings)


def profile_sizes() -> tuple[str, ...]:
    return tuple(load().profiles)


def tube_sizes() -> tuple[str, ...]:
    return tuple(load().tubes)


def board_sizes() -> tuple[str, ...]:
    return tuple(load().boards)


def _lookup(entries: dict[str, Any], size: str, what: str) -> Any:
    # ``entries`` und nicht ``table``: So hieß der Parameter, und seit es die
    # Funktion :func:`table` daneben gibt, verdeckte er sie.
    wanted = size.strip()
    found = entries.get(wanted) or entries.get(wanted.upper()) or entries.get(wanted.lower())
    if found is None:
        raise ValidationError(
            field=what,
            detail=_("Diese Größe steht nicht in der Normteiltabelle."),
            values={"size": wanted, "known": ", ".join(sorted(entries))},
        )
    return found
