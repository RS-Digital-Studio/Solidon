"""Örtliche Filamentspulen und ihr Buchungsjournal (§20).

Die Kennung gehört zur physischen Spule, der Name ist ein mehrfach erlaubtes
Etikett. Projektwerte bleiben in den Materialslots. Katalog und Journal werden
unter derselben Prozesssperre gelesen, geprüft und atomar ersetzt. Fehlende
Mengen bleiben unbekannt; beschädigte Dateien werden niemals überschrieben.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, date, datetime
from pathlib import Path, PureWindowsPath
from time import monotonic, sleep
from typing import Any, Final, Literal
from uuid import uuid4

from app.core.errors import RETRY, FileWriteError, ValidationError
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_config_dir
from app.i18n import _, sort_key

_log = get_logger(__name__)
CATALOGUE_FILE: Final = "filaments.json"
FORMAT_VERSION: Final = 1
_COLOUR_PATTERN: Final = re.compile(r"^#[0-9a-fA-F]{6}$")
_LOCK_TIMEOUT_SECONDS: Final = 10.0
_LOCK_RETRY_SECONDS: Final = 0.05
BookingSource = Literal["internal", "gcode", "manual"]


@dataclass(frozen=True, slots=True)
class CatalogueFilament:
    """Eine Spule mit optionalen Angaben; keine Angabe ist keine Vorgabemenge."""

    name: str
    colour: str
    material_type: str = ""
    slicer_profile: str = ""
    identifier: str = ""
    diameter_mm: float | None = None
    spool_grams: float | None = None
    remaining_grams: float | None = None
    location: str = ""
    opened_on: str = ""
    bought_on: str = ""
    price: float | None = None
    currency: str = ""
    note: str = ""
    archived: bool = False
    revision: int = 0
    """Schützt eine geöffnete Bearbeitung vor späteren Änderungen."""
    stock_revision: int = 0
    """Die letzte Bestandsfeststellung; Buchungen erhöhen nur revision."""


@dataclass(frozen=True, slots=True)
class BookingPosition:
    """Bestätigter Verbrauch einer Spule mit seiner unverwechselbaren Herkunft."""

    spool_identifier: str
    grams: float
    source: BookingSource = "internal"
    note: str = ""
    position_identifier: str = ""
    """Optional für mehrere Positionen derselben Spule, etwa je Platte."""
    stock_revision: int = 0
    """Beim Buchen gesetzt; eine jüngere Feststellung sperrt Korrektur/Rücknahme."""
    filament_key: str = ""
    """Die kanonische Druckfilamentidentität bleibt unabhängig von der Spule."""

    @property
    def key(self) -> tuple[str, str]:
        """Eine ausdrücklich benannte Position oder Spule plus Druckfilament."""
        return (
            (self.position_identifier, "")
            if self.position_identifier
            else (self.spool_identifier, self.filament_key)
        )


@dataclass(frozen=True, slots=True)
class BookingCorrection:
    """Eine dokumentierte Ersetzung, deren Differenz den Bestand verändert."""

    created_at: str
    previous_positions: tuple[BookingPosition, ...]
    positions: tuple[BookingPosition, ...]


@dataclass(frozen=True, slots=True)
class PreservedStockCount:
    """Bei ausdrücklicher Rücknahme bewahrte, jüngere manuelle Bestandsfeststellung."""

    spool_identifier: str
    grams: float | None
    stock_revision: int


@dataclass(frozen=True, slots=True)
class InventoryBooking:
    """Ein ganzer Druckvorgang einschließlich Korrekturen und Rücknahme."""

    operation_id: str
    fingerprint: str
    positions: tuple[BookingPosition, ...]
    created_at: str
    updated_at: str
    project_name: str = ""
    reversed_at: str = ""
    corrections: tuple[BookingCorrection, ...] = ()
    preserved_counts: tuple[PreservedStockCount, ...] = ()


@dataclass
class _Inventory:
    """Ein unter Sperre gelesener Stand, niemals ein dauerhafter Speichercache."""

    identifier: str
    spools: dict[str, CatalogueFilament] = field(default_factory=dict)
    counts: dict[str, float | None] = field(default_factory=dict)
    journal: dict[str, InventoryBooking] = field(default_factory=dict)
    dirty: bool = False


def catalogue_path() -> Path:
    """Die gemeinsame Datei von Spulen, Bestandsfeststellungen und Journal."""
    return user_config_dir() / CATALOGUE_FILE


def profile_name(value: str) -> str:
    """Ein portabler Slicer-Profilname — niemals ein Dateipfad (Regel 12)."""
    cleaned = value.strip()
    if not cleaned:
        return ""
    candidate = PureWindowsPath(cleaned)
    if (
        candidate.drive
        or candidate.is_absolute()
        or len(candidate.parts) != 1
        or cleaned == ".."
        or cleaned.startswith(("/", "\\"))
    ):
        raise ValidationError(
            field="slicer_profile",
            detail=_(
                "Ein Slicer-Profil wird über seinen Namen gewählt, nicht über einen Dateipfad."
            ),
            value=value,
            constraint="format",
        )
    return cleaned


def _catalogue_profile_name(value: str) -> str:
    """Ein Altpfad kostet nur die unportable Profilbindung, niemals die Spule."""
    try:
        return profile_name(value)
    except ValidationError:
        _log.warning("filament catalogue contains a profile path; ignoring it")
        return ""


def _amount(value: float | None, name: str, *, positive: bool = False) -> None:
    """Unbekannt bleibt erlaubt, bekannte Mengen müssen endlich und gültig sein."""
    if value is not None and (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or value < 0.0
        or (positive and value <= 0.0)
    ):
        raise ValidationError(
            field=name,
            value=value,
            constraint="range",
            detail=_("Tragen Sie eine gültige Menge ein oder lassen Sie die Angabe leer."),
        )


def _validated(entry: CatalogueFilament) -> CatalogueFilament:
    """Prüft Eingaben, bevor ein Lagerstand verändert werden darf."""
    for name in (
        "name",
        "colour",
        "material_type",
        "slicer_profile",
        "identifier",
        "location",
        "opened_on",
        "bought_on",
        "currency",
        "note",
    ):
        if not isinstance(getattr(entry, name), str):
            raise ValidationError(field=name, constraint="format")
    if not entry.name.strip():
        raise ValidationError(
            title=_("Ein Filament braucht einen Namen."),
            field="name",
            detail=_("Tragen Sie ein, wie die Spule heißt — etwa das Material und die Farbe."),
            value=entry.name,
            constraint="empty",
        )
    if not _COLOUR_PATTERN.fullmatch(entry.colour):
        raise ValidationError(
            title=_("Diese Farbe lässt sich nicht lesen."),
            field="colour",
            detail=_("Eine Filamentfarbe ist sechsstellig: #RRGGBB, etwa #d02020."),
            value=entry.colour,
            constraint="colour",
        )
    for name in ("remaining_grams", "price", "diameter_mm", "spool_grams"):
        _amount(getattr(entry, name), name, positive=name in ("diameter_mm", "spool_grams"))
    for name in ("opened_on", "bought_on"):
        value = getattr(entry, name)
        if value:
            try:
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError(value)
            except ValueError as problem:
                raise ValidationError(
                    field=name,
                    constraint="format",
                    detail=_("Wählen Sie ein gültiges Datum aus."),
                ) from problem
    currency = entry.currency.strip().upper()
    if (entry.price is not None and not currency) or (
        currency and not re.fullmatch(r"[A-Z]{3}", currency)
    ):
        raise ValidationError(
            field="currency",
            constraint="format",
            detail=_("Wählen Sie zum Preis eine Währung aus, etwa EUR oder USD."),
        )
    if not isinstance(entry.archived, bool) or any(
        type(getattr(entry, name)) is not int or getattr(entry, name) < 0
        for name in ("revision", "stock_revision")
    ):
        raise ValidationError(field="revision", constraint="format")
    return replace(
        entry,
        name=entry.name.strip(),
        colour=entry.colour.lower(),
        material_type=entry.material_type.strip(),
        slicer_profile=profile_name(entry.slicer_profile),
        location=entry.location.strip(),
        currency=currency,
    )


def _same_amount(left: float | None, right: float | None) -> bool:
    """Vergleicht die optionale Menge ohne einen unbekannten Wert zu erfinden."""
    if left is None or right is None:
        return left is right
    return math.isclose(left, right)


@contextmanager
def _catalogue_lock() -> Iterator[None]:
    """Ein Betriebssystemschloss umfasst Lesen, Prüfung und atomaren Dateitausch."""
    ensure_dir(catalogue_path().parent)
    descriptor = os.open(catalogue_path().with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    native = importlib.import_module("msvcrt" if os.name == "nt" else "fcntl")
    acquired = False
    try:
        deadline = monotonic() + _LOCK_TIMEOUT_SECONDS
        while not acquired:
            try:
                if os.name == "nt":
                    native.locking(descriptor, native.LK_NBLCK, 1)
                else:
                    native.flock(descriptor, native.LOCK_EX | native.LOCK_NB)
                acquired = True
            except OSError as problem:
                if monotonic() >= deadline:
                    raise FileWriteError(
                        detail=_(
                            "Das Filamentlager wird gerade geändert. Versuchen Sie es erneut."
                        ),
                        suggestions=(RETRY,),
                    ) from problem
                sleep(_LOCK_RETRY_SECONDS)
        yield
    finally:
        try:
            if acquired:
                if os.name == "nt":
                    native.locking(descriptor, native.LK_UNLCK, 1)
                else:
                    native.flock(descriptor, native.LOCK_UN)
        finally:
            os.close(descriptor)


def _parse_positions(data: Any) -> tuple[BookingPosition, ...]:
    """Liest ein vollständiges Journal; ungültige Zeilen werden nicht übersprungen."""
    if not isinstance(data, list):
        raise ValueError("positions")
    positions = tuple(BookingPosition(**entry) for entry in data)
    _validate_positions(positions)
    return positions


def _parse_booking(data: Any) -> InventoryBooking:
    """Stellt die unveränderlichen Journalwerte aus ihren JSON-Werten her."""
    value = dict(data)
    value["positions"] = _parse_positions(value["positions"])
    value["corrections"] = tuple(
        BookingCorrection(
            created_at=correction["created_at"],
            previous_positions=_parse_positions(correction["previous_positions"]),
            positions=_parse_positions(correction["positions"]),
        )
        for correction in value.get("corrections", [])
    )
    value["preserved_counts"] = tuple(
        PreservedStockCount(**count) for count in value.get("preserved_counts", [])
    )
    booking = InventoryBooking(**value)
    if (
        any(
            not isinstance(getattr(booking, name), str)
            for name in (
                "operation_id",
                "fingerprint",
                "created_at",
                "updated_at",
                "project_name",
                "reversed_at",
            )
        )
        or not booking.operation_id
        or not booking.fingerprint
    ):
        raise ValueError("booking")
    for count in booking.preserved_counts:
        _amount(count.grams, "preserved_counts")
        if not isinstance(count.spool_identifier, str) or type(count.stock_revision) is not int:
            raise ValueError("preserved_counts")
    return booking


def _migrate_list(data: list[Any]) -> _Inventory:
    """Listenkatalog → Version 1: eigene Kennungen, alle fehlenden Mengen unbekannt."""
    state = _Inventory(identifier=uuid4().hex, dirty=True)
    for value in data:
        entry = _validated(
            CatalogueFilament(
                name=value["name"],
                colour=value["colour"],
                material_type=value.get("material_type", ""),
                slicer_profile=_catalogue_profile_name(value.get("slicer_profile", "")),
                identifier=uuid4().hex,
                revision=1,
            )
        )
        state.spools[entry.identifier] = entry
        state.counts[entry.identifier] = None
    return state


def _read() -> _Inventory:
    """Liest streng: beschädigte und neuere Dateien bleiben vollständig unangetastet."""
    try:
        data = json.loads(catalogue_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _Inventory(identifier=uuid4().hex)
    except (OSError, ValueError) as problem:
        raise _unreadable() from problem
    try:
        if isinstance(data, list):
            return _migrate_list(data)
        if (
            not isinstance(data, dict)
            or type(data.get("format_version")) is not int
            or data["format_version"] != FORMAT_VERSION
        ):
            raise ValueError("format_version")
        state = _Inventory(identifier=data["inventory_identifier"])
        if not isinstance(state.identifier, str) or not state.identifier:
            raise ValueError("inventory_identifier")
        if not isinstance(data["spools"], list) or not isinstance(data["bookings"], list):
            raise ValueError("inventory")
        if not isinstance(data["stock_counts"], dict):
            raise ValueError("stock_counts")
        for value in data["spools"]:
            entry = _validated(CatalogueFilament(**value))
            if not entry.identifier or entry.identifier in state.spools:
                raise ValueError("spool identifier")
            state.spools[entry.identifier] = entry
        state.counts = dict(data["stock_counts"])
        if set(state.counts) != set(state.spools):
            raise ValueError("stock_counts")
        for count in state.counts.values():
            _amount(count, "stock_counts")
        for value in data["bookings"]:
            booking = _parse_booking(value)
            if booking.operation_id in state.journal:
                raise ValueError("operation_id")
            for position in booking.positions:
                spool = state.spools.get(position.spool_identifier)
                if spool is None or position.stock_revision > spool.stock_revision:
                    raise ValueError("stock_revision")
            state.journal[booking.operation_id] = booking
        for entry in state.spools.values():
            if not _same_amount(entry.remaining_grams, _remaining(state, entry)):
                raise ValueError("remaining_grams")
        return state
    except (ValueError, TypeError, KeyError, AttributeError, ValidationError) as problem:
        raise _unreadable() from problem


def _unreadable() -> ValidationError:
    """Ein Lesefehler erklärt zugleich, warum Speichern gesperrt bleibt."""
    return ValidationError(
        field="catalogue",
        constraint="unreadable",
        detail=_(
            "Das Filamentlager lässt sich nicht lesen. Die Datei bleibt unverändert. "
            "Stellen Sie eine Sicherung wieder her oder prüfen Sie die Datei filaments.json."
        ),
    )


def _write(state: _Inventory) -> None:
    """Alle Spulen und das Journal gemeinsam; erst die fertige Datei ersetzt den Stand."""
    target = catalogue_path()
    scratch = target.with_name(target.name + ".tmp")
    data = {
        "format_version": FORMAT_VERSION,
        "inventory_identifier": state.identifier,
        "spools": [asdict(entry) for entry in state.spools.values()],
        "stock_counts": state.counts,
        "bookings": [asdict(booking) for booking in state.journal.values()],
    }
    try:
        with scratch.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        scratch.replace(target)
    finally:
        scratch.unlink(missing_ok=True)


@contextmanager
def _transaction() -> Iterator[_Inventory]:
    """Auch eine Migration wird unter derselben Sperre genau einmal gespeichert."""
    try:
        with _catalogue_lock():
            state = _read()
            yield state
            if state.dirty:
                _write(state)
    except OSError as problem:
        raise FileWriteError(detail=str(problem)) from problem


def _sorted(state: _Inventory, include_archived: bool = False) -> tuple[CatalogueFilament, ...]:
    """Namen werden sprachgerecht sortiert, gleiche Etiketten behalten ihre Kennung."""
    return tuple(
        sorted(
            (entry for entry in state.spools.values() if include_archived or not entry.archived),
            key=lambda entry: (sort_key(entry.name), entry.identifier),
        )
    )


def catalogue(
    include_archived: bool = False, *, strict: bool = False
) -> tuple[CatalogueFilament, ...]:
    """Alle aktiven Spulen; strict meldet Lesefehler für die Lageransicht.

    Die Vorwahl darf beim Programmstart leer bleiben. Jeder Schreibweg liest
    dagegen streng neu und verweigert das Überschreiben einer beschädigten Datei.
    """
    try:
        with _transaction() as state:
            return _sorted(state, include_archived)
    except (ValidationError, FileWriteError) as problem:
        if strict:
            raise
        _log.warning("filament inventory unreadable: %s", problem)
        return ()


def inventory_identifier() -> str:
    """Die beständige örtliche Lagerkennung wird vor der ersten Rückgabe gespeichert."""
    with _transaction() as state:
        state.dirty = True
        return state.identifier


def get(identifier: str) -> CatalogueFilament | None:
    """Auch eine archivierte Spule ist über ihre Kennung eindeutig erreichbar."""
    with _transaction() as state:
        return state.spools.get(identifier)


def _required(state: _Inventory, identifier: str) -> CatalogueFilament:
    """Fehlende Kennungen werden niemals auf gleichnamige Spulen umgelenkt."""
    if identifier not in state.spools:
        raise ValidationError(
            field="spool_identifier",
            value=identifier,
            constraint="missing",
            detail=_("Diese Spule fehlt im örtlichen Lager. Wählen Sie eine andere Spule."),
        )
    return state.spools[identifier]


def _save(state: _Inventory, entry: CatalogueFilament) -> CatalogueFilament:
    """Speichert eine bereits validierte Eingabe innerhalb des gesperrten Standes."""
    if entry.identifier:
        current = _required(state, entry.identifier)
        if entry.revision != current.revision:
            raise ValidationError(
                field="revision",
                constraint="conflict",
                detail=_(
                    "Die Spule wurde inzwischen geändert. Laden Sie ihren aktuellen Stand neu."
                ),
            )
        counted = not _same_amount(entry.remaining_grams, current.remaining_grams)
        stored = replace(
            entry,
            revision=current.revision + 1,
            stock_revision=current.stock_revision + int(counted),
        )
    else:
        counted = True
        stored = replace(entry, identifier=uuid4().hex, revision=1, stock_revision=1)
    state.spools[stored.identifier] = stored
    if counted:
        state.counts[stored.identifier] = stored.remaining_grams
    state.dirty = True
    return stored


def save(entry: CatalogueFilament) -> CatalogueFilament:
    """Leere Kennung legt neu an; Bearbeiten erhält die Kennung und prüft den Lesestand."""
    entry = _validated(entry)
    with _transaction() as state:
        return _save(state, entry)


def set_remaining(identifier: str, grams: float | None) -> CatalogueFilament:
    """Eine ausdrückliche Bestandsfeststellung gilt auch bei derselben Grammzahl neu."""
    _amount(grams, "remaining_grams")
    with _transaction() as state:
        current = _required(state, identifier)
        stored = replace(
            current,
            remaining_grams=grams,
            stock_revision=current.stock_revision + 1,
            revision=current.revision + 1,
        )
        state.spools[identifier] = stored
        state.counts[identifier] = grams
        state.dirty = True
        return stored


def duplicate(identifier: str) -> CatalogueFilament:
    """Noch eine davon: neues Exemplar, unbekannter Rest, keine eigene Buchung."""
    with _transaction() as state:
        current = _required(state, identifier)
        return _save(
            state,
            replace(
                current,
                identifier="",
                remaining_grams=None,
                opened_on="",
                bought_on="",
                archived=False,
            ),
        )


def _set_archived(identifier: str, archived: bool) -> CatalogueFilament:
    """Archivieren bewahrt alle Bestands- und Journalinformationen."""
    with _transaction() as state:
        current = _required(state, identifier)
        if current.archived is archived:
            return current
        return _save(state, replace(current, archived=archived))


def archive(identifier: str) -> CatalogueFilament:
    """Nimmt eine Spule aus der aktiven Auswahl, ohne ihren Verlauf zu löschen."""
    return _set_archived(identifier, True)


def restore(identifier: str) -> CatalogueFilament:
    """Stellt dieselbe Spule mit derselben Kennung wieder zur Wahl."""
    return _set_archived(identifier, False)


def _legacy_match(
    state: _Inventory, name: str, profile: str = "", colour: str = ""
) -> CatalogueFilament | None:
    """Der alte Namensweg darf nur eine tatsächlich eindeutige Spule bearbeiten."""
    candidates = [
        entry for entry in state.spools.values() if not entry.archived and entry.name == name
    ]
    if not candidates and profile:
        candidates = [
            entry
            for entry in state.spools.values()
            if not entry.archived
            and (entry.slicer_profile.casefold(), entry.colour.casefold())
            == (profile.casefold(), colour.casefold())
        ]
    if len(candidates) > 1:
        raise ValidationError(
            field="spool_identifier",
            constraint="ambiguous",
            detail=_("Mehrere Spulen tragen diesen Namen. Wählen Sie die gewünschte Spule aus."),
        )
    return candidates[0] if candidates else None


def remember(
    name: str, colour: str, material_type: str = "", slicer_profile: str = ""
) -> CatalogueFilament:
    """Kompatibler Namensweg; neue Oberflächen speichern ausschließlich nach Kennung."""
    entry = _validated(CatalogueFilament(name, colour, material_type, slicer_profile))
    with _transaction() as state:
        current = _legacy_match(state, entry.name)
        if current is not None:
            entry = replace(
                current,
                name=entry.name,
                colour=entry.colour,
                material_type=entry.material_type,
                slicer_profile=entry.slicer_profile,
            )
        return _save(state, entry)


def synchronise(entries: list[CatalogueFilament]) -> tuple[CatalogueFilament, ...]:
    """Explizite Profilübernahme; eindeutige Alteinträge werden ohne Mengenverlust erneuert."""
    with _transaction() as state:
        for supplied in entries:
            if not supplied.name.strip() or not _COLOUR_PATTERN.fullmatch(supplied.colour):
                continue
            entry = _validated(
                replace(supplied, slicer_profile=_catalogue_profile_name(supplied.slicer_profile))
            )
            current = (
                _required(state, entry.identifier)
                if entry.identifier
                else _legacy_match(state, entry.name, entry.slicer_profile, entry.colour)
            )
            if current is not None:
                entry = replace(
                    current,
                    name=entry.name,
                    colour=entry.colour,
                    material_type=entry.material_type,
                    slicer_profile=entry.slicer_profile,
                )
            else:
                entry = replace(entry, remaining_grams=None)
            _save(state, entry)
        return _sorted(state)


def forget(name: str) -> bool:
    """Kompatibler Namensweg archiviert eindeutig statt Identität und Verlauf zu löschen."""
    with _transaction() as state:
        current = _legacy_match(state, name)
        if current is None:
            return False
        _save(state, replace(current, archived=True))
        return True


def _validate_positions(positions: Sequence[BookingPosition]) -> None:
    """Jede Position ist vollständig, endlich, nicht negativ und eindeutig bezeichnet."""
    keys: set[tuple[str, str]] = set()
    if not positions:
        raise ValidationError(field="positions", constraint="empty")
    for position in positions:
        _amount(position.grams, "grams")
        if (
            position.grams is None
            or position.source not in ("internal", "gcode", "manual")
            or not isinstance(position.spool_identifier, str)
            or not position.spool_identifier
            or not isinstance(position.position_identifier, str)
            or not isinstance(position.note, str)
            or not isinstance(position.filament_key, str)
            or type(position.stock_revision) is not int
            or position.stock_revision < 0
            or position.key in keys
        ):
            raise ValidationError(field="positions", constraint="format")
        keys.add(position.key)


def bookings(spool_identifier: str | None = None) -> tuple[InventoryBooking, ...]:
    """Verlauf in Buchungsreihenfolge, wahlweise mit allen Positionen eines Spulenvorgangs."""
    with _transaction() as state:
        return tuple(
            booking
            for booking in state.journal.values()
            if spool_identifier is None
            or any(
                position.spool_identifier == spool_identifier
                for positions in (
                    booking.positions,
                    *(one.previous_positions for one in booking.corrections),
                )
                for position in positions
            )
        )


def _remaining(state: _Inventory, entry: CatalogueFilament) -> float | None:
    """Rechnet ab der jüngsten Feststellung; Unterdeckung bleibt klärungsbedürftig."""
    counted = state.counts[entry.identifier]
    if counted is None:
        return None
    consumed = math.fsum(
        position.grams
        for booking in state.journal.values()
        if not booking.reversed_at
        for position in booking.positions
        if position.spool_identifier == entry.identifier
        and position.stock_revision == entry.stock_revision
    )
    remaining = counted - consumed
    return remaining if remaining >= 0.0 else None


def _refresh_stock(
    state: _Inventory, identifiers: set[str], *, allow_unverified_stock: bool
) -> None:
    """Alle betroffenen Bestände prüfen, bevor ein gemeinsamer Stand geschrieben wird."""
    for identifier in identifiers:
        current = _required(state, identifier)
        remaining = _remaining(state, current)
        if remaining is None and not allow_unverified_stock:
            raise ValidationError(
                field="remaining_grams",
                constraint="stock",
                detail=_(
                    "Der Bestand ist unbekannt oder reicht nicht aus. Korrigieren Sie den Bestand, "
                    "wählen Sie eine andere Spule oder bestätigen Sie den Abzug ausdrücklich."
                ),
            )
        state.spools[identifier] = replace(
            current, remaining_grams=remaining, revision=current.revision + 1
        )
    state.dirty = True


def _check_counts(state: _Inventory, booking: InventoryBooking) -> None:
    """Eine jüngere manuelle Feststellung darf durch einen alten Vorgang nicht verschwinden."""
    for position in booking.positions:
        if _required(state, position.spool_identifier).stock_revision != position.stock_revision:
            raise ValidationError(
                field="remaining_grams",
                constraint="stock_conflict",
                detail=_(
                    "Der Bestand wurde danach neu festgestellt. Prüfen Sie den aktuellen Bestand. "
                    "Eine Rücknahme muss diesen neueren Stand ausdrücklich erhalten."
                ),
            )


def _same_positions(left: Sequence[BookingPosition], right: Sequence[BookingPosition]) -> bool:
    """Die Zustellung ist unabhängig von der Reihenfolge ihrer Positionen idempotent."""
    old = {position.key: position for position in left}
    return len(left) == len(right) and all(
        position.key in old
        and old[position.key].spool_identifier == position.spool_identifier
        and old[position.key].filament_key == position.filament_key
        and _same_amount(old[position.key].grams, position.grams)
        and old[position.key].source == position.source
        and old[position.key].note == position.note
        for position in right
    )


def _booking_conflict() -> ValidationError:
    """Eine neue Druckabsicht braucht eine neue Kennung statt anderer Daten derselben."""
    return ValidationError(
        field="operation_id",
        constraint="conflict",
        detail=_(
            "Dieser Vorgang wurde bereits mit anderen Angaben gebucht. "
            "Öffnen Sie seinen Verlauf oder legen Sie ausdrücklich einen Wiederholungsdruck an."
        ),
    )


def book(
    operation_id: str,
    fingerprint: str,
    positions: Sequence[BookingPosition],
    *,
    allow_unverified_stock: bool = False,
    project_name: str = "",
    correct_manual_allocation: bool = False,
) -> InventoryBooking:
    """Bucht einen ganzen Druck genau einmal oder ersetzt seine Schätzung durch G-Code.

    Ein neuer Vorgang mit demselben Fingerabdruck bedeutet einen ausdrücklich
    wiederholten Druck. Die Ausgabeoberfläche ordnet die Vorbereitung vorher zu.
    Unzureichender Bestand wird nur mit ausdrücklicher Bestätigung unbekannt.
    """
    _validate_positions(positions)
    if (
        not isinstance(operation_id, str)
        or not operation_id.strip()
        or not isinstance(fingerprint, str)
        or not fingerprint.strip()
    ):
        raise ValidationError(field="operation_id", constraint="empty")
    if not isinstance(project_name, str):
        raise ValidationError(field="project_name", constraint="format")
    with _transaction() as state:
        previous = state.journal.get(operation_id)
        if previous is not None:
            if previous.fingerprint != fingerprint:
                raise _booking_conflict()
            if _same_positions(previous.positions, positions):
                return previous
            if previous.reversed_at:
                raise _booking_conflict()
            old = {position.key: position for position in previous.positions}
            manual_correction = correct_manual_allocation and (
                any(position.source == "manual" for position in (*previous.positions, *positions))
                and all(position.source in ("manual", "gcode") for position in positions)
                and {position.filament_key for position in previous.positions}
                == {position.filament_key for position in positions}
            )
            if not manual_correction and (
                set(old) != {position.key for position in positions}
                or any(
                    old[position.key].spool_identifier != position.spool_identifier
                    or old[position.key].filament_key != position.filament_key
                    for position in positions
                )
            ):
                raise _booking_conflict()
            # Verspätete Zustellung der ursprünglichen Schätzung bucht nichts.
            if not manual_correction and any(
                _same_positions(correction.previous_positions, positions)
                for correction in previous.corrections
            ):
                return previous
            if not manual_correction and any(
                not _same_positions((old[position.key],), (position,))
                and (old[position.key].source, position.source) != ("internal", "gcode")
                for position in positions
            ):
                raise _booking_conflict()
            _check_counts(state, previous)
        confirmed: list[BookingPosition] = []
        for position in positions:
            spool = _required(state, position.spool_identifier)
            if spool.archived and (
                previous is None
                or position.spool_identifier
                not in {one.spool_identifier for one in previous.positions}
            ):
                raise ValidationError(
                    field="spool_identifier",
                    constraint="archived",
                    detail=_(
                        "Diese Spule ist archiviert. Stellen Sie sie wieder her "
                        "oder wählen Sie eine andere."
                    ),
                )
            confirmed.append(replace(position, stock_revision=spool.stock_revision))
        now = datetime.now(UTC).isoformat()
        booking = InventoryBooking(
            operation_id, fingerprint, tuple(confirmed), now, now, project_name
        )
        if previous is not None:
            booking = replace(
                previous,
                positions=tuple(confirmed),
                updated_at=now,
                corrections=(
                    *previous.corrections,
                    BookingCorrection(now, previous.positions, tuple(confirmed)),
                ),
            )
        state.journal[operation_id] = booking
        _refresh_stock(
            state,
            {position.spool_identifier for position in confirmed}
            | (
                {position.spool_identifier for position in previous.positions}
                if previous
                else set()
            ),
            allow_unverified_stock=allow_unverified_stock,
        )
        return booking


def reverse_booking(operation_id: str, *, preserve_newer_counts: bool = False) -> InventoryBooking:
    """Nimmt alle Positionen und Korrekturen genau einmal zurück; nie ein Projekt-Undo."""
    with _transaction() as state:
        if operation_id not in state.journal:
            raise ValidationError(field="operation_id", constraint="missing")
        previous = state.journal[operation_id]
        if previous.reversed_at:
            return previous
        if not preserve_newer_counts:
            _check_counts(state, previous)
        preserved: list[PreservedStockCount] = []
        stock_revisions = {
            position.spool_identifier: position.stock_revision for position in previous.positions
        }
        for identifier, stock_revision in stock_revisions.items():
            spool = _required(state, identifier)
            if spool.stock_revision != stock_revision:
                preserved.append(
                    PreservedStockCount(identifier, spool.remaining_grams, spool.stock_revision)
                )
        now = datetime.now(UTC).isoformat()
        booking = replace(
            previous, reversed_at=now, updated_at=now, preserved_counts=tuple(preserved)
        )
        state.journal[operation_id] = booking
        _refresh_stock(
            state,
            {position.spool_identifier for position in booking.positions},
            allow_unverified_stock=True,
        )
        return booking
