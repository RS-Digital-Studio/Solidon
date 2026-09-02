"""Der Projektcontainer (Bauplan §16.1).

::

    projekt.p3d           (ZIP)
      project.json        # Stapel, Parameter, Passungen, Transaktionen
      sources/            # eingebettete Quellnetze
      report.json         # letzter Prüfbericht
      thumb.png           # Vorschau für Dateidialoge

Drei Regeln, die der Container erzwingt statt annimmt:

* **Keine absoluten Pfade** (§32). Ein Projekt reist zwischen Rechnern und
  Leuten; ein Pfad aus dem Container hinaus wird beim Schreiben wie beim
  Lesen abgelehnt.
* **Prüfsummen auf jeder Quelle**, verifiziert beim Laden (§16.1).
* **Atomar geschrieben.** Ein Absturz beim Speichern darf nicht die Datei
  kosten, die vorher da war — darum liegt auch der Autosave-Container (§38)
  daneben.
"""

from __future__ import annotations

import ctypes
import dataclasses
import hashlib
import json
import math
import os
import sys
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any, Final

from app.branding import APP_VERSION, PROJECT_SUFFIX
from app.core import examples
from app.core.errors import PROGRAMMING_ERRORS, ValidationError
from app.core.ingest.loader import MAX_FILE_BYTES
from app.core.knowledge.parts import check as part_check
from app.core.knowledge.parts import recipe as part_recipes
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_data_dir
from app.core.scene.gathered import GATHERED_DIR, externalise, gathered_path, inline, references
from app.core.scene.migrations import FORMAT_VERSION, migrate
from app.core.scene.serialise import (
    document_from_data,
    document_to_data,
    has_lone_surrogate,
    report_from_data,
    report_to_data,
)
from app.core.types import Document, Finding, Report, Source, SourceId
from app.i18n import TranslatableText, _

_windows_ctypes: Any = ctypes
_windows_msvcrt: Any = None
if os.name == "nt":
    import msvcrt as _native_msvcrt

    _windows_msvcrt = _native_msvcrt

_log = get_logger(__name__)

PROJECT_ENTRY: Final = "project.json"
REPORT_ENTRY: Final = "report.json"
THUMBNAIL_ENTRY: Final = "thumb.png"
SOURCE_FOLDER: Final = "sources"
AUTOSAVE_SUFFIX: Final = ".autosave"

#: Grenzen für fremde Projektcontainer (§32). Die Nutzlast folgt derselben
#: Obergrenze wie ein direkter Modellimport; die äußere Datei bekommt nur den
#: notwendigen Spielraum für ZIP-Verzeichnis und Kompressionskopfzeilen.
MAX_ARCHIVE_ENTRY_BYTES: Final = MAX_FILE_BYTES
MAX_ARCHIVE_UNPACKED_BYTES: Final = MAX_FILE_BYTES
MAX_PROJECT_FILE_BYTES: Final = MAX_FILE_BYTES + 16 * 1024 * 1024
MAX_ARCHIVE_ENTRIES: Final = 4096

#: Strukturierte Beilagen sind um Größenordnungen kleiner als ein Quellnetz.
#: Eigene Grenzen halten manipulierte Dateien vor JSON-Decodierung,
#: Rezeptaufnahme und Vorschauverarbeitung an.
MAX_PROJECT_JSON_BYTES: Final = 16 * 1024 * 1024
MAX_GATHERED_BYTES: Final = 16 * 1024 * 1024
MAX_RECIPE_BYTES: Final = 4 * 1024 * 1024
MAX_REPORT_BYTES: Final = 16 * 1024 * 1024
MAX_THUMBNAIL_BYTES: Final = 32 * 1024 * 1024

#: Auch syntaktisch kleines JSON darf nicht durch extreme Verschachtelung
#: oder hunderttausende Kleinstobjekte unverhältnismäßig viel Arbeit und
#: Speicher binden. Die Einzelgrenzen darunter beschreiben das aktuelle
#: Projektschema; die generischen Grenzen gelten zusätzlich für unbekannte
#: additive Felder künftiger Fassungen.
MAX_JSON_DEPTH: Final = 64
MAX_JSON_NODES: Final = 500_000
MAX_JSON_COLLECTION_ITEMS: Final = 100_000
MAX_JSON_STRING_CHARS: Final = MAX_GATHERED_BYTES
MAX_PROJECT_OBJECTS: Final = 10_000
MAX_PROJECT_OPERATIONS: Final = 100_000
MAX_PROJECT_PARAMETERS: Final = 10_000
MAX_PROJECT_SOURCES: Final = 10_000
MAX_PROJECT_FITS: Final = 100_000
MAX_PROJECT_TRANSACTIONS: Final = 100_000
MAX_PROJECT_CHAT_ENTRIES: Final = 100_000
MAX_REPORT_FINDINGS: Final = 100_000
MAX_LINKED_SOURCE_BYTES: Final = MAX_FILE_BYTES

#: Ein sehr kleines, gut komprimierbares JSON darf ein hohes Verhältnis
#: haben. Ab einem MiB ist ein Verhältnis über 250 dagegen kein sinnvoller
#: Projektinhalt mehr, sondern ein Dekompressionsangriff.
MIN_RATIO_ENTRY_BYTES: Final = 1024 * 1024
MAX_COMPRESSION_RATIO: Final = 250.0


@dataclass(slots=True)
class Project:
    """Was eine ``.p3d``-Datei hält."""

    document: Document
    sources: dict[SourceId, bytes] = field(default_factory=dict)
    """Inhalt der eingebetteten Quellen, gleich geschlüsselt wie
    ``document.sources``."""
    report: Report = field(default_factory=Report)
    thumbnail: bytes | None = None


@dataclass(slots=True)
class ProjectSources:
    """Lesezugriff auf die Quellen eines Projekts, für die ``load``-Operation.

    Eingebettete Quellen kommen aus dem Container, verknüpfte über einen Pfad
    relativ zum Projektordner — nie über einen absoluten (§32).
    """

    project: Project
    base_dir: Path | None = None
    _identities: dict[SourceId, str] = field(default_factory=dict)
    """Gemerkte Inhaltsprüfsummen für Quellen, die noch keine haben."""

    def identity(self, source_id: SourceId) -> str:
        """Die Inhaltsprüfsumme dieser Quelle (§15, Cache-Schlüssel).

        **Warum nicht einfach ``source.sha256``:** Das Feld wird beim Speichern
        gefüllt, nicht beim Import. Ein Projekt, das noch nie gespeichert wurde,
        trägt dort einen leeren Text — und genau dort wäre der Schlüssel wieder
        blind. Also wird sie gerechnet, wo sie fehlt, und gemerkt: Ein
        eingebetteter Inhalt ändert sich innerhalb einer Sitzung nicht.

        Eine **verknüpfte** Quelle ohne Prüfsumme wird jedes Mal gelesen, und
        das ist Absicht: Sie liegt als Datei draußen und kann sich zwischen zwei
        Auswertungen geändert haben. Ein gemerkter Wert wäre dann die falsche
        Antwort auf die einzige Frage, die diese Funktion hat.
        """
        source = self.describe(source_id)
        if not source.embedded:
            # Der gespeicherte Wert ist nur eine Behauptung über eine Datei,
            # die außerhalb des Containers liegt. ``read`` prüft sie vor
            # jedem Cache-Schlüssel erneut; sonst könnte eine ausgetauschte
            # Datei unter dem alten Schlüssel ein altes Ergebnis erhalten.
            return checksum(self.read(source_id))
        if source.sha256:
            return source.sha256
        known = self._identities.get(source_id)
        if known is None:
            known = checksum(self.read(source_id))
            self._identities[source_id] = known
        return known

    def describe(self, source_id: SourceId) -> Source:
        source = self.project.document.sources.get(source_id)
        if source is None:
            raise ValidationError(
                field="source",
                detail=_("Diese Quelle gibt es im Projekt nicht."),
                constraint="unknown_source",
                values={"source": source_id},
            )
        return source

    def read(self, source_id: SourceId) -> bytes:
        source = self.describe(source_id)
        if source.embedded:
            payload = self.project.sources.get(source_id)
            if payload is None:
                raise ValidationError(
                    field="source",
                    detail=_("Der Inhalt dieser Quelle fehlt im Projekt."),
                    constraint="missing_payload",
                    values={"source": source_id},
                )
            return payload

        _check_relative(source.path, "source.path")
        if self.base_dir is None:
            raise ValidationError(
                field="source",
                detail=_("Verknüpfte Quellen brauchen einen gespeicherten Projektordner."),
                constraint="no_base_dir",
                values={"source": source_id},
            )
        return _read_linked_source(
            source,
            self.base_dir,
            field="source",
            values={"source": source_id},
        )


def new_project(printer: str = "", material: str = "") -> Project:
    """Ein leeres Projekt auf der aktuellen Formatversion."""
    return Project(
        document=Document(
            format_version=FORMAT_VERSION,
            app_version=APP_VERSION,
            printer=printer,
            material=material,
        )
    )


def checksum(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_linked_source(
    source: Source,
    base_dir: Path,
    *,
    field: str,
    values: dict[str, object],
    require_checksum: bool = True,
) -> bytes:
    """Liest und prüft eine verknüpfte Quelle mit derselben Grenze wie den
    direkten Import.

    Die Größenabfrage liegt vor dem Lesen; der gedeckelte Lesezug schließt die
    Lücke, falls die Datei zwischen beiden Schritten wächst.
    """
    if require_checksum and (
        len(source.sha256) != 64
        or any(character not in "0123456789abcdef" for character in source.sha256)
    ):
        raise ValidationError(
            field=field,
            detail=_("Eine Quelle stimmt nicht mit ihrer Prüfsumme überein."),
            constraint="checksum",
            values={**values, "path": source.path},
        )

    linked = base_dir / source.path
    try:
        resolved_base = base_dir.resolve(strict=True)
        resolved_link = linked.resolve(strict=True)
    except FileNotFoundError as problem:
        raise ValidationError(
            field=field,
            detail=_("Die verknüpfte Datei wurde nicht gefunden."),
            constraint="missing_link",
            values={**values, "path": source.path},
        ) from problem
    try:
        resolved_link.relative_to(resolved_base)
    except ValueError as problem:
        # Ein relativer Text ist noch keine sichere Verknüpfung: Symlinks und
        # Windows-Junctions können ihn nach außerhalb des Projektordners
        # auflösen. Geöffnet wird anschließend der geprüfte kanonische Pfad,
        # damit ein Austausch der letzten Verknüpfung nicht um die Prüfung
        # herumführt.
        raise ValidationError(
            field=field,
            detail=_("In Projektdateien stehen keine absoluten Pfade."),
            constraint="absolute_path",
            values={**values, "path": source.path},
        ) from problem
    try:
        with resolved_link.open("rb") as stream:
            opened_path = _opened_file_path(stream)
            try:
                opened_path.relative_to(resolved_base)
            except ValueError as problem:
                raise ValidationError(
                    field=field,
                    detail=_("In Projektdateien stehen keine absoluten Pfade."),
                    constraint="absolute_path",
                    values={**values, "path": source.path},
                ) from problem
            size = os.fstat(stream.fileno()).st_size
            if size > MAX_FILE_BYTES:
                raise ValidationError(
                    field=field,
                    detail=_("Die Datei ist größer, als diese Anwendung verarbeitet."),
                    constraint="file_too_large",
                    values={
                        **values,
                        "path": source.path,
                        "size": size,
                        "limit": MAX_FILE_BYTES,
                    },
                )
            payload = stream.read(MAX_FILE_BYTES + 1)
    except OSError as problem:
        raise ValidationError(
            field=field,
            detail=_("Die Datei lässt sich nicht öffnen; sie ist beschädigt."),
            constraint="unreadable",
            values={**values, "path": source.path},
        ) from problem
    if len(payload) > MAX_FILE_BYTES:
        raise ValidationError(
            field=field,
            detail=_("Die Datei ist größer, als diese Anwendung verarbeitet."),
            constraint="file_too_large",
            values={
                **values,
                "path": source.path,
                "size": len(payload),
                "limit": MAX_FILE_BYTES,
            },
        )
    actual = checksum(payload)
    if source.sha256 and actual != source.sha256:
        raise ValidationError(
            field=field,
            detail=_("Eine Quelle stimmt nicht mit ihrer Prüfsumme überein."),
            constraint="checksum",
            values={**values, "path": source.path},
        )
    return payload


def _opened_file_path(stream: Any) -> Path:
    """Ermittelt den kanonischen Pfad des bereits geöffneten Dateihandles."""
    if os.name == "nt":
        kernel32 = _windows_ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetFinalPathNameByHandleW.argtypes = (
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
        )
        kernel32.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
        handle = ctypes.c_void_p(_windows_msvcrt.get_osfhandle(stream.fileno()))
        length = kernel32.GetFinalPathNameByHandleW(handle, None, 0, 0)
        if not length:
            raise OSError(
                _windows_ctypes.get_last_error(),
                "Dateipfad konnte nicht geprüft werden",
            )
        buffer = ctypes.create_unicode_buffer(length + 1)
        written = kernel32.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not written or written >= len(buffer):
            raise OSError(
                _windows_ctypes.get_last_error(),
                "Dateipfad konnte nicht geprüft werden",
            )
        name = buffer.value
        if name.startswith("\\\\?\\UNC\\"):
            name = "\\\\" + name[8:]
        elif name.startswith("\\\\?\\"):
            name = name[4:]
        return Path(name).resolve(strict=True)

    for descriptor_root in (Path("/proc/self/fd"), Path("/dev/fd")):
        descriptor = descriptor_root / str(stream.fileno())
        if descriptor.exists():
            return descriptor.resolve(strict=True)
    if sys.platform == "darwin":
        import fcntl

        raw = fcntl.fcntl(stream.fileno(), 50, b"\0" * 4096)
        return Path(raw.split(b"\0", 1)[0].decode()).resolve(strict=True)
    raise OSError("Der geöffnete Dateipfad lässt sich auf dieser Plattform nicht prüfen")


def embedded_source_path(filename: str, source_id: str) -> str:
    """Wo eine eingebettete Quelle im Container liegt — immer relativ.

    Die Kennung gehört in den Pfad: Zwei Quellen mit demselben Dateinamen
    (``bracket.stl`` aus zwei Ordnern) bekamen sonst denselben Containerpfad,
    die zweite überschrieb die erste, und beim Wiederöffnen hieß es
    „Prüfsumme stimmt nicht" — die Datei war heil geschrieben und trotzdem
    verloren (Fund des Gesamtreviews vom 25.08.2026). Alte Projektdateien
    bleiben lesbar: Der Pfad steht im Dokument und wird beim Laden gelesen,
    nicht neu gebildet.

    **Als Ordner, nicht als Namenspräfix.** Der erste Wurf hängte die Kennung
    vor den Dateinamen — und aus dem Stamm dieses Pfads leitet ``load`` den
    Objektnamen ab: Im Fenstertitel stand „src_1-cube_clean (ungespeichert)"
    (gefunden von 3d-druck-43, 25.08.2026). Ein Unterordner je Quelle macht
    den Pfad genauso eindeutig und lässt den Namen in Ruhe.
    """
    return f"{SOURCE_FOLDER}/{source_id}/{Path(filename).name}"


def _check_relative(path: str, where: str) -> None:
    # Geurteilt wird über beide Konventionen zugleich: eine Projektdatei reist
    # zwischen Plattformen, und „C:/…" muss auch dort abgelehnt werden, wo es
    # für Path nur ein Ordnername ist (Regel 12). PureWindowsPath kennt beide
    # Trennzeichen, also sieht sie auch „..\…" — der Plattform-Path auf POSIX
    # nicht.
    candidate = PureWindowsPath(path)
    if (
        candidate.drive
        or candidate.is_absolute()
        or ".." in candidate.parts
        or path.startswith(("/", "\\"))
    ):
        raise ValidationError(
            field=where,
            detail=_("In Projektdateien stehen keine absoluten Pfade."),
            constraint="absolute_path",
            values={"path": path},
        )


def _entry_limit(name: str) -> int:
    """Die Inhaltsgrenze für einen Eintrag des Projektcontainers."""
    if name == PROJECT_ENTRY:
        return MAX_PROJECT_JSON_BYTES
    if name == REPORT_ENTRY:
        return MAX_REPORT_BYTES
    if name == THUMBNAIL_ENTRY:
        return MAX_THUMBNAIL_BYTES
    if name.startswith(f"{GATHERED_DIR}/"):
        return MAX_GATHERED_BYTES
    if name.startswith(part_recipes.CONTAINER_PREFIX):
        return MAX_RECIPE_BYTES
    return MAX_ARCHIVE_ENTRY_BYTES


def _too_large(detail: TranslatableText, **values: object) -> ValidationError:
    """Einheitliche, handlungsfähige Absage für Containergrenzen."""
    return ValidationError(
        field="container",
        detail=detail,
        constraint="file_too_large",
        values=values,
    )


def _check_outer_size(path: Path) -> None:
    """Prüft die gepackte Datei, bevor das ZIP-Verzeichnis geöffnet wird."""
    size = path.stat().st_size
    if size > MAX_PROJECT_FILE_BYTES:
        raise _too_large(
            _("Die Datei ist größer, als diese Anwendung verarbeitet."),
            path=path.name,
            size=size,
            limit=MAX_PROJECT_FILE_BYTES,
        )


def _preflight_archive(container: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    """Prüft das ZIP-Verzeichnis vollständig vor dem ersten Inhaltslesezug."""
    infos = container.infolist()
    if len(infos) > MAX_ARCHIVE_ENTRIES:
        raise _too_large(
            _("Die Datei ist größer, als diese Anwendung verarbeitet."),
            entries=len(infos),
            limit=MAX_ARCHIVE_ENTRIES,
        )

    by_name: dict[str, zipfile.ZipInfo] = {}
    unpacked = 0
    compressed = 0
    for info in infos:
        _check_relative(info.filename, "container")
        if info.filename in by_name:
            raise ValidationError(
                field="container",
                detail=_("Der Projektinhalt ist beschädigt."),
                constraint="exists",
                values={"entry": info.filename},
            )
        by_name[info.filename] = info
        compressed += info.compress_size

        limit = _entry_limit(info.filename)
        if info.file_size > limit:
            raise _too_large(
                _("Die Datei ist größer, als diese Anwendung verarbeitet."),
                entry=info.filename,
                size=info.file_size,
                limit=limit,
            )
        unpacked += info.file_size
        if unpacked > MAX_ARCHIVE_UNPACKED_BYTES:
            raise _too_large(
                _("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
                unpacked=unpacked,
                limit=MAX_ARCHIVE_UNPACKED_BYTES,
            )

        if info.file_size < MIN_RATIO_ENTRY_BYTES:
            continue
        ratio = info.file_size / max(info.compress_size, 1)
        if ratio > MAX_COMPRESSION_RATIO:
            raise _too_large(
                _("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
                entry=info.filename,
                ratio=round(ratio, 1),
                limit=MAX_COMPRESSION_RATIO,
            )
    if unpacked >= MIN_RATIO_ENTRY_BYTES:
        ratio = unpacked / max(compressed, 1)
        if ratio > MAX_COMPRESSION_RATIO:
            raise _too_large(
                _("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
                ratio=round(ratio, 1),
                limit=MAX_COMPRESSION_RATIO,
            )
    return by_name


def _read_archive_entry(
    container: zipfile.ZipFile,
    info: zipfile.ZipInfo,
) -> bytes:
    """Liest höchstens die erlaubte Eintragsgröße plus ein Prüfbyte."""
    limit = _entry_limit(info.filename)
    try:
        with container.open(info, "r") as stream:
            payload = stream.read(limit + 1)
    except (EOFError, NotImplementedError, RuntimeError) as problem:
        raise ValidationError(
            field="container",
            detail=_("Der Projektinhalt ist beschädigt."),
            constraint="damaged",
            values={"entry": info.filename},
        ) from problem
    if len(payload) > limit:
        raise _too_large(
            _("Die Datei ist größer, als diese Anwendung verarbeitet."),
            entry=info.filename,
            size=len(payload),
            limit=limit,
        )
    if len(payload) != info.file_size:
        raise ValidationError(
            field="container",
            detail=_("Der Projektinhalt ist beschädigt."),
            constraint="damaged",
            values={"entry": info.filename},
        )
    return payload


def _payload_size(payload: str | bytes) -> int:
    return len(payload.encode("utf-8")) if isinstance(payload, str) else len(payload)


def _check_output_entries(entries: list[tuple[str, str | bytes]]) -> None:
    """Verhindert, dass Solidon selbst einen später unlesbaren Container baut."""
    if len(entries) > MAX_ARCHIVE_ENTRIES:
        raise _too_large(
            _("Die Datei ist größer, als diese Anwendung verarbeitet."),
            entries=len(entries),
            limit=MAX_ARCHIVE_ENTRIES,
        )
    seen: set[str] = set()
    unpacked = 0
    for name, payload in entries:
        _check_relative(name, "container")
        if name in seen:
            raise ValidationError(
                field="container",
                detail=_("Der Projektinhalt ist beschädigt."),
                constraint="exists",
                values={"entry": name},
            )
        seen.add(name)
        size = _payload_size(payload)
        limit = _entry_limit(name)
        if size > limit:
            raise _too_large(
                _("Die Datei ist größer, als diese Anwendung verarbeitet."),
                entry=name,
                size=size,
                limit=limit,
            )
        unpacked += size
        if unpacked > MAX_ARCHIVE_UNPACKED_BYTES:
            raise _too_large(
                _("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
                unpacked=unpacked,
                limit=MAX_ARCHIVE_UNPACKED_BYTES,
            )


def _validate_json_tree(value: object) -> None:
    """Begrenzt einen decodierten JSON-Baum iterativ und verlangt endliche Zahlen."""
    stack: list[tuple[object, int]] = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise ValueError("json_nodes")
        if depth > MAX_JSON_DEPTH:
            raise ValueError("json_depth")
        if isinstance(current, float) and not math.isfinite(current):
            raise ValueError("non_finite_number")
        if isinstance(current, str):
            if len(current) > MAX_JSON_STRING_CHARS:
                raise ValueError("json_string")
            continue
        if isinstance(current, dict):
            if len(current) > MAX_JSON_COLLECTION_ITEMS:
                raise ValueError("json_collection")
            for key, child in current.items():
                if not isinstance(key, str) or len(key) > MAX_JSON_STRING_CHARS:
                    raise ValueError("json_key")
                stack.append((child, depth + 1))
            continue
        if isinstance(current, list):
            if len(current) > MAX_JSON_COLLECTION_ITEMS:
                raise ValueError("json_collection")
            stack.extend((child, depth + 1) for child in current)


def _mapping(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"schema:{name}")
    return value


def _records(data: dict[str, Any], name: str) -> list[dict[str, Any]]:
    value = data.get(name, [])
    if not isinstance(value, list) or any(not isinstance(entry, dict) for entry in value):
        raise ValueError(f"schema:{name}")
    return value


def _check_schema_count(name: str, size: int, limit: int) -> None:
    if size > limit:
        raise _too_large(
            _("Die Datei entpackt sich größer, als diese Anwendung verarbeitet."),
            field=name,
            size=size,
            limit=limit,
        )


def _validate_project_schema(data: object) -> dict[str, Any]:
    """Prüft Form und Mengen des aktuellen Projekts vor der Deserialisierung."""
    _validate_json_tree(data)
    if not isinstance(data, dict):
        raise ValueError("schema:project")
    version = data.get("format_version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError("schema:format_version")

    for name in ("scene", "libs", "parameters", "sources", "numbering"):
        _mapping(data, name)
    parameters = _mapping(data, "parameters")
    sources = _mapping(data, "sources")
    fits = _records(data, "fits")
    transactions = _records(data, "transactions")
    operations = _records(data, "ops")
    chat = _records(data, "chat")
    if any(not isinstance(entry, dict) for entry in parameters.values()):
        raise ValueError("schema:parameters")
    if any(not isinstance(entry, dict) for entry in sources.values()):
        raise ValueError("schema:sources")

    _check_schema_count("parameters", len(parameters), MAX_PROJECT_PARAMETERS)
    _check_schema_count("sources", len(sources), MAX_PROJECT_SOURCES)
    _check_schema_count("fits", len(fits), MAX_PROJECT_FITS)
    _check_schema_count("transactions", len(transactions), MAX_PROJECT_TRANSACTIONS)
    _check_schema_count("ops", len(operations), MAX_PROJECT_OPERATIONS)
    _check_schema_count("chat", len(chat), MAX_PROJECT_CHAT_ENTRIES)

    objects: set[str] = set()
    for operation in operations:
        if (
            isinstance(operation.get("id"), bool)
            or not isinstance(operation.get("id"), int)
            or not isinstance(operation.get("op"), str)
        ):
            raise ValueError("schema:op")
        for name in ("in", "out"):
            references = operation.get(name, [])
            if not isinstance(references, list) or any(
                not isinstance(reference, str) for reference in references
            ):
                raise ValueError(f"schema:op.{name}")
            if name == "out":
                objects.update(references)
        if not isinstance(operation.get("params", {}), dict):
            raise ValueError("schema:op.params")
        if operation.get("solver") is not None and not isinstance(operation["solver"], dict):
            raise ValueError("schema:op.solver")
        matches = operation.get("matches", {})
        if not isinstance(matches, dict) or any(
            not isinstance(entry, dict) for entry in matches.values()
        ):
            raise ValueError("schema:op.matches")
        translatable = operation.get("translatable", [])
        if not isinstance(translatable, list) or any(
            not isinstance(entry, str) for entry in translatable
        ):
            raise ValueError("schema:op.translatable")
    _check_schema_count("objects", len(objects), MAX_PROJECT_OBJECTS)
    return data


def _validate_report_schema(data: object) -> dict[str, Any]:
    """Prüft den Bericht mit denselben Strukturgrenzen wie das Dokument."""
    _validate_json_tree(data)
    if not isinstance(data, dict):
        raise ValueError("schema:report")
    findings = data.get("findings", [])
    if not isinstance(findings, list) or any(not isinstance(entry, dict) for entry in findings):
        raise ValueError("schema:report.findings")
    _check_schema_count("findings", len(findings), MAX_REPORT_FINDINGS)
    for finding in findings:
        suggestions = finding.get("suggestions", [])
        if suggestions is not None and (
            not isinstance(suggestions, list)
            or any(not isinstance(entry, dict) for entry in suggestions)
        ):
            raise ValueError("schema:report.suggestions")
        if not isinstance(finding.get("values", {}), dict):
            raise ValueError("schema:report.values")
    return data


# --- Schreiben -------------------------------------------------------------------


def _next_gathered(data: dict[str, Any]) -> int:
    """Die nächste freie Nummer für einen ausgelagerten Wert.

    Aus den **Daten**, nicht aus ``document.sources``: Dort steht nie eine
    gathered-Quelle — die Verweise leben in den Op-Parametern, und die alte
    Fassung war eine Buchführung, die nichts führte (Fund des Gesamtreviews
    vom 25.08.2026). Im Normalfall ist die Liste leer, denn ``inline()`` hat
    beim Laden alles zurückgeholt; bleibt ein Verweis stehen — eine von Hand
    bearbeitete Datei —, nummeriert das Speichern darüber hinweg, statt den
    Eintrag zu überschreiben.
    """
    used = [
        int(source_id.rsplit("_", 1)[-1])
        for source_id in references(data)
        if source_id.rsplit("_", 1)[-1].isdigit()
    ]
    return max(used, default=0) + 1


#: Der Zeitstempel, den jeder Eintrag im Container trägt.
#:
#: **Warum ein fester und nicht die Uhr.** Ein ZIP schreibt je Eintrag ein
#: Änderungsdatum, und damit unterscheiden sich zwei Speicherungen desselben
#: Projekts in ihren Bytes, obwohl ihr Inhalt Zeichen für Zeichen gleich ist.
#: Für einen Kunden ist das folgenlos — er sieht das Datum der Datei, nicht das
#: der Einträge darin. Für alles, was Dateien *vergleicht*, ist es Rauschen:
#: Jeder Lauf von ``tools/make_examples.py`` erzeugte neun geänderte Dateien,
#: auch wenn sich an keinem Beispiel etwas geändert hatte, und wer sie
#: mitcommittete, schrieb neun Zeilen Verlauf ohne Inhalt.
#:
#: Der Wert ist der früheste, den das ZIP-Format kennt (1980-01-01). Er ist
#: nicht als Datum gemeint, sondern als *kein* Datum — wer ihn liest, soll
#: sehen, dass hier keine Uhr gelaufen ist.
CONTAINER_TIMESTAMP: Final = (1980, 1, 1, 0, 0, 0)


def _write(container: zipfile.ZipFile, name: str, payload: str | bytes) -> None:
    """Ein Eintrag mit festem Zeitstempel statt der Uhr."""
    info = zipfile.ZipInfo(name, date_time=CONTAINER_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    container.writestr(info, payload)


def save(project: Project, path: Path) -> Path:
    """Schreibt den Container, atomar. Gibt den geschriebenen Pfad zurück.

    **Zweimal speichern ergibt zweimal dieselbe Datei** — siehe
    :data:`CONTAINER_TIMESTAMP`. Das ist dieselbe Zusage, die §15.1 der
    Auswertung macht, eine Ebene tiefer: Gleiche Eingaben, gleiches Ergebnis,
    Byte für Byte.
    """
    document = project.document
    document.format_version = FORMAT_VERSION
    document.app_version = APP_VERSION
    # §24.4: der Stand der Bausteinbibliothek gehört zu der Art, wie das
    # gerechnet wurde. Für die **eigenen** Bausteine reicht die Version nicht —
    # sie bewegt sich nicht, wenn der Nutzer seine Datei ändert (§24.5). Darum
    # nicht mehr die Zeile von Hand, sondern der Weg, der zusätzlich je
    # benutztem eigenen Baustein einen Abdruck seiner Datei mitschreibt.
    part_check.stamp(document)

    # Zusicherung gegen den Altbestand: In Dateien von vor dem 26.08.2026
    # können zwei Quellen denselben Containerpfad tragen — beim Schreiben
    # überschriebe die zweite die erste, und das Wiederöffnen endete an der
    # Prüfsumme. Besser vor dem Schreiben anhalten als heil aussehend
    # verlieren.
    taken: dict[str, str] = {}
    for source_id, source in document.sources.items():
        if not source.embedded:
            continue
        first = taken.setdefault(source.path, source_id)
        if first != source_id:
            raise ValidationError(
                field=f"sources.{source_id}",
                detail=_(
                    "Zwei eingebettete Quellen zeigen auf denselben Ort in "
                    "der Projektdatei. Entfernen Sie eine der beiden und "
                    "betten Sie sie neu ein."
                ),
                constraint="exists",
                values={"path": source.path, "sources": f"{first}, {source_id}"},
            )

    for source_id, source in list(document.sources.items()):
        _check_relative(source.path, f"sources.{source_id}.path")
        if not source.embedded:
            linked_payload = _read_linked_source(
                source,
                path.parent,
                field=f"sources.{source_id}",
                values={"source": source_id},
                require_checksum=False,
            )
            # Ein neuer Link darf ohne Abdruck im Arbeitsspeicher entstehen;
            # spätestens die erste Speicherung bindet ihn an genau die Datei,
            # die dabei vorlag. Einen vorhandenen, falschen Abdruck hat der
            # Leser davor bereits abgelehnt.
            document.sources[source_id] = dataclasses.replace(
                source,
                sha256=checksum(linked_payload),
            )
            continue
        embedded_payload = project.sources.get(source_id)
        if embedded_payload is None:
            raise ValidationError(
                field=f"sources.{source_id}",
                detail=_("Eine eingebettete Quelle hat keinen Inhalt."),
                constraint="missing_payload",
                values={"source": source_id},
            )
        # Die Prüfsumme ist Teil des Dokuments, also füllt das Speichern sie
        # ein (§16.1).
        document.sources[source_id] = dataclasses.replace(
            source,
            sha256=checksum(embedded_payload),
        )

    # §9: Was ein Editor gesammelt hat, kann groß werden — eine
    # Sculpting-Sitzung mit viertausend Zügen ist ein halbes Megabyte Zahlen in
    # einer Zeile. Ab der Grenze wandert der Wert in eine eigene Datei im
    # Container, und im Dokument steht ein Verweis. Gearbeitet wird auf der
    # frisch serialisierten Kopie: Das Dokument im Speicher bleibt, was es ist.
    data = document_to_data(document)
    _validate_project_schema(data)
    if has_lone_surrogate(data):
        raise ValidationError(
            field="container",
            detail=_("Der Projektinhalt ist beschädigt."),
            constraint="damaged",
            values={"reason": "unicode_scalar"},
        )
    gathered_payloads = externalise(data, _next_gathered(data))

    report_data = report_to_data(project.report)
    _validate_report_schema(report_data)
    if has_lone_surrogate(report_data):
        raise ValidationError(
            field="container",
            detail=_("Der Projektinhalt ist beschädigt."),
            constraint="damaged",
            values={"reason": "unicode_scalar"},
        )

    entries: list[tuple[str, str | bytes]] = [
        (PROJECT_ENTRY, json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False))
    ]
    entries.extend(
        (gathered_path(source_id), payload) for source_id, payload in gathered_payloads.items()
    )
    entries.extend(
        (source.path, project.sources[source_id])
        for source_id, source in document.sources.items()
        if source.embedded
    )
    entries.append(
        (
            REPORT_ENTRY,
            json.dumps(report_data, indent=2, ensure_ascii=False, allow_nan=False),
        )
    )
    # Ein Rezept reist mit jedem Projekt, das es benutzt (Entscheidung
    # Robert, 24.08.2026; Konzept Befestigungssysteme §17.1). Daten, kein
    # Code — die Sicherheitslage ist die der ``project.json`` selbst.
    # Zusätzliche Einträge, kein Formatschritt: Eine ältere Version liest
    # den Container weiter und hält wie bisher bei ``parts.missing`` an.
    entries.extend(
        (part_recipes.container_entry(part_name), payload_text)
        for part_name, payload_text in part_recipes.for_container(document).items()
    )
    if project.thumbnail is not None:
        entries.append((THUMBNAIL_ENTRY, project.thumbnail))
    _check_output_entries(entries)

    ensure_dir(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".part",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w+b") as stream:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as container:
                for name, entry_payload in entries:
                    _write(container, name, entry_payload)
            stream.flush()
            os.fsync(stream.fileno())
            size = os.fstat(stream.fileno()).st_size
        if size > MAX_PROJECT_FILE_BYTES:
            raise _too_large(
                _("Die Datei ist größer, als diese Anwendung verarbeitet."),
                path=path.name,
                size=size,
                limit=MAX_PROJECT_FILE_BYTES,
            )
        if os.name == "posix":
            # ``mkstemp`` legt mit 0600 an, und das Umbenennen trägt die
            # Rechte mit: Das Projekt gehörte danach allein dem Nutzer, auch
            # wo seine Umask etwas anderes sagt — ein Wechsel des Rechners
            # oder eine gemeinsame Gruppe kam nicht mehr an die Datei. Also
            # bekommt sie vor dem Wechsel die Rechte, die eine normal
            # angelegte Datei hätte. Die Umask lässt sich nur lesen, indem man
            # sie setzt; Windows kennt weder sie noch diese Bits.
            mask = os.umask(0)
            os.umask(mask)
            temporary.chmod(0o666 & ~mask)
        # Das zufällige, exklusiv angelegte Ziel liegt im selben Ordner; der
        # Wechsel bleibt damit atomar, ohne ein vorhersagbares ``.part``-Ziel
        # zu öffnen oder einer dort vorbereiteten Verknüpfung zu folgen.
        temporary.replace(path)
    finally:
        with suppress(FileNotFoundError):
            temporary.unlink()
    _log.info("saved project %s", path.name)
    return path


# --- Lesen ---------------------------------------------------------------------


def load(path: Path) -> Project:
    """Liest einen Container — migriert und verifiziert unterwegs (§16.2)."""
    if not path.is_file():
        raise ValidationError(
            field="path",
            detail=_("Diese Projektdatei gibt es nicht."),
            constraint="missing_file",
            values={"path": path.name},
        )
    _check_outer_size(path)
    try:
        with zipfile.ZipFile(path) as container:
            infos = _preflight_archive(container)
            names = set(infos)
            if PROJECT_ENTRY not in names:
                raise ValidationError(
                    field="container",
                    detail=_("Der Datei fehlt der Projektinhalt."),
                    constraint="not_a_project",
                    values={"path": path.name},
                )
            data = json.loads(_read_archive_entry(container, infos[PROJECT_ENTRY]))
            if has_lone_surrogate(data):
                raise ValueError("unicode_scalar")
            data = _validate_project_schema(data)
            data = migrate(data)
            # Die ausgelagerten Sammelwerte zurück ins Dokument, bevor daraus
            # eines wird: Ein Verweis, den niemand auflöst, wäre für jede
            # Operation dahinter ein Text ohne Inhalt und ein leeres Ergebnis
            # ohne Fehlermeldung.
            inline(
                data,
                {
                    source_id: _read_archive_entry(container, infos[gathered_path(source_id)])
                    for source_id in references(data)
                    if gathered_path(source_id) in names
                },
            )
            data = _validate_project_schema(data)
            document = document_from_data(data)

            # Mitgereiste Rezepte aufnehmen, bevor irgendetwas rechnet: Die
            # Auswertung braucht ihre Operationen, sonst hält sie bei
            # ``parts.missing`` an, obwohl die Datei alles mitbringt.
            # „Lokal schlägt mitgereist, immer" entscheidet ``adopt``
            # (Konzept §17.1); eine kaputte Beilage ist ein Befund, kein
            # Abbruch, und die Befunde landen im Bericht der Datei.
            arrived: list[Finding] = []
            for entry_name in sorted(names):
                if not entry_name.startswith(part_recipes.CONTAINER_PREFIX):
                    continue
                if not entry_name.endswith(".json"):
                    continue
                # Gelesen wird **in** ``adopt_payload``: Stand das
                # ``json.loads`` hier, lief eine abgeschnittene Beilage am
                # ``try`` des Aufnehmens vorbei und ließ das ganze Projekt mit
                # „Der Projektinhalt ist beschädigt" abbrechen — obwohl das
                # Dokument heil war.
                arrived.extend(
                    part_recipes.adopt_payload(
                        _read_archive_entry(container, infos[entry_name]),
                        entry_name,
                    )
                )

            payloads: dict[SourceId, bytes] = {}
            linked_bytes = 0
            for source_id, source in document.sources.items():
                if not source.embedded:
                    linked_payload = _read_linked_source(
                        source,
                        path.parent,
                        field=f"sources.{source_id}",
                        values={"source": source_id},
                    )
                    linked_bytes += len(linked_payload)
                    if linked_bytes > MAX_LINKED_SOURCE_BYTES:
                        raise _too_large(
                            _("Die Datei ist größer, als diese Anwendung verarbeitet."),
                            sources=linked_bytes,
                            limit=MAX_LINKED_SOURCE_BYTES,
                        )
                    continue
                if source.path not in names:
                    raise ValidationError(
                        field=f"sources.{source_id}",
                        detail=_("Eine eingebettete Quelle fehlt im Container."),
                        constraint="missing_payload",
                        values={"source": source_id, "path": source.path},
                    )
                payload = _read_archive_entry(container, infos[source.path])
                if not source.sha256 or checksum(payload) != source.sha256:
                    raise ValidationError(
                        field=f"sources.{source_id}",
                        detail=_("Eine Quelle stimmt nicht mit ihrer Prüfsumme überein."),
                        constraint="checksum",
                        values={"source": source_id},
                    )
                payloads[source_id] = payload

            if REPORT_ENTRY in names:
                report_data = json.loads(_read_archive_entry(container, infos[REPORT_ENTRY]))
                if has_lone_surrogate(report_data):
                    raise ValueError("unicode_scalar")
                report_data = _validate_report_schema(report_data)
                report = report_from_data(report_data)
            else:
                report = Report()
            if arrived:
                # Was beim Aufnehmen schiefging, steht im Bericht der Datei —
                # sichtbar, bis die erste Auswertung ihn ersetzt, und die
                # scheitert an einem fehlenden Baustein dann mit eigener
                # Meldung (§15.2).
                report = Report(findings=(*report.findings, *arrived))
            thumbnail = (
                _read_archive_entry(container, infos[THUMBNAIL_ENTRY])
                if THUMBNAIL_ENTRY in names
                else None
            )
    except zipfile.BadZipFile as problem:
        raise ValidationError(
            field="container",
            detail=_("Die Datei lässt sich nicht öffnen; sie ist beschädigt."),
            constraint="damaged",
            values={"path": path.name},
        ) from problem
    except json.JSONDecodeError as problem:
        raise ValidationError(
            field="container",
            detail=_("Der Projektinhalt ist beschädigt."),
            constraint="damaged",
            values={"path": path.name},
        ) from problem
    except PROGRAMMING_ERRORS:
        # **Ein falscher Aufruf ist keine kaputte Datei.** ``TypeError`` und
        # ``AttributeError`` standen in der Sammelliste darunter, und damit
        # las der Kunde „Der Projektinhalt ist beschädigt" über einem Fehler
        # in unserem Code — ohne Fehlerbericht, und auf jedem Rechner
        # dasselbe (`errors.PROGRAMMING_ERRORS`).
        raise
    except (
        KeyError,
        OverflowError,
        RecursionError,
        UnicodeError,
        ValueError,
    ) as problem:
        # Syntaktisch gültiges, strukturell kaputtes JSON: ein fehlender
        # Pflichtschlüssel, eine Zeichenkette, wo eine Zahl stehen muss.
        # Fünf solcher Wege verließen ``load()`` als rohe Ausnahme ohne
        # Handlungsvorschlag (Regel 17; Fund des Gesamtreviews vom
        # 25.08.2026). Ein ``ValidationError`` von tiefer unten — etwa die
        # unbekannte Passungsart — läuft hier unverändert durch: er ist
        # keiner dieser fünf Typen.
        raise ValidationError(
            field="container",
            detail=_("Der Projektinhalt ist beschädigt."),
            constraint="damaged",
            values={"path": path.name, "reason": str(problem)[:200]},
        ) from problem

    _log.info("opened project %s", path.name)
    return Project(document=document, sources=payloads, report=report, thumbnail=thumbnail)


# --- Autosave und Absturz-Wiederherstellung (§38) --------------------------------


def _recovery_dir() -> Path:
    return ensure_dir(user_data_dir() / "recovery")


def autosave_path(path: Path | None) -> Path:
    """Neben dem Projekt — oder im Nutzerverzeichnis, solange es noch keinen
    Namen hat.

    **Ein Beispiel bekommt seines nie daneben.** Beispiele liegen in der
    Installation (§37.2); dort zu schreiben ist unter „Programme" schlicht
    nicht erlaubt und im Entwicklerbaum eine Verschmutzung, die niemand sucht.
    Genau das war der Fall: zwei Sicherungen neben zwei Beispielen ließen den
    Tour-Test in einem Wiederherstellungsdialog hängen, und ein Test, der
    hängt, sagt nicht, warum.
    """
    if path is None:
        return _recovery_dir() / f"unsaved{PROJECT_SUFFIX}{AUTOSAVE_SUFFIX}"
    if path.parent == examples.directory():
        return _recovery_dir() / f"{path.name}{AUTOSAVE_SUFFIX}"
    return path.with_name(path.name + AUTOSAVE_SUFFIX)


def write_autosave(project: Project, path: Path | None) -> Path:
    return save(project, autosave_path(path))


def find_recovery(path: Path | None) -> Path | None:
    """Ein Autosave, das sein Projekt überlebt hat, wird beim nächsten Start
    angeboten.

    **Bei Gleichstand wird angeboten.** Die Dateizeit hat auf dieser Plattform
    eine Auflösung von rund 16 Millisekunden, und ein Projekt zu speichern und
    danach zu sichern dauert weniger — beide Dateien tragen dann dieselbe Zeit,
    bis aufs letzte Bit. Wer daraus „das Autosave ist nicht neuer" schließt,
    hat nicht gemessen, sondern die Auflösung der Uhr abgelesen.

    Entschieden wird deshalb zur sicheren Seite: Ein Angebot, das der Nutzer
    ablehnt, kostet einen Klick; ein Autosave, das nicht angeboten wird, kostet
    seine Arbeit. Ausgeschlossen bleibt nur, was **nachweislich** älter ist —
    dort hat jemand nach der Sicherung gespeichert, und dann gilt das
    Gespeicherte.
    """
    candidate = autosave_path(path)
    if not candidate.is_file():
        return None
    if path is not None and path.is_file() and candidate.stat().st_mtime < path.stat().st_mtime:
        return None
    return candidate


def clear_autosave(path: Path | None) -> None:
    """Die Sicherung ist erledigt — nach dem Speichern und nach dem Verwerfen.

    Der Docstring nannte lange nur den ersten Fall, und dabei blieb es nicht:
    Seit „Verworfen heißt verworfen" räumt auch der Weg über ``_may_discard``
    hier auf, und der läuft im ``closeEvent``.

    **Deshalb wirft die Funktion nicht.** Eine ``.autosave``, die im selben
    Augenblick von einem Virenscanner gehalten wird, ist auf Windows kein
    seltener Fall — und ein ``PermissionError`` mitten im Schließen wäre ein
    Fenster, das sich nicht schließen lässt, wegen einer Datei, die niemanden
    mehr interessiert. Bleibt sie liegen, kostet das eine überflüssige Frage
    beim nächsten Öffnen; das ist die kleinere Störung, und sie steht im
    Protokoll.
    """
    candidate = autosave_path(path)
    if not candidate.is_file():
        return
    try:
        candidate.unlink()
    except OSError as problem:
        _log.warning("could not remove the autosave %s: %s", candidate.name, problem)


def project_data(path: Path) -> dict[str, Any]:
    """Das rohe ``project.json`` eines Containers — für Diagnose und
    Migrationstests."""
    _check_outer_size(path)
    with zipfile.ZipFile(path) as container:
        infos = _preflight_archive(container)
        if PROJECT_ENTRY not in infos:
            raise ValidationError(
                field="container",
                detail=_("Der Datei fehlt der Projektinhalt."),
                constraint="not_a_project",
                values={"path": path.name},
            )
        result: dict[str, Any] = json.loads(_read_archive_entry(container, infos[PROJECT_ENTRY]))
        return result
