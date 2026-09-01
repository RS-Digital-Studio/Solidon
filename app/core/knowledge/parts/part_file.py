"""Sicherer lokaler Import und Export von Bausteindateien.

Das Modul kennt weder Qt noch Netzwerkzugriffe. Beide Richtungen laufen durch
dieselbe geschlossene Struktur-, Ressourcen-, Quellen- und Geometrieprüfung.
Eine importierte Datei erhält nur eine unmittelbare Herkunftsquittung; ihr
Inhalt, Autor, ihre Lizenz und eingebettete Modelldaten bleiben unverändert.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any
from urllib.parse import urlsplit

from app.branding import PART_FILE_SUFFIX
from app.core.errors import CANCEL, CHOOSE, RETRY, AppError, FileWriteError, ValidationError
from app.core.knowledge import profiles
from app.core.knowledge.parts import recipe, shared
from app.core.scene.migrations import migrate
from app.core.scene.serialise import has_lone_surrogate
from app.i18n import TranslatableText, _

Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    """Die Uhr als austauschbare Abhängigkeit für Herkunftsangaben."""

    return datetime.now(UTC)


@dataclasses.dataclass(frozen=True, slots=True)
class ImportedPart:
    """Ein geprüftes Rezept mit Quittung über die exakten Eingangsbytes."""

    sha256: str
    recipe: recipe.Recipe


@dataclasses.dataclass(frozen=True, slots=True)
class InstalledPart:
    """Ein dauerhaft und kollisionsfrei in den Katalog übernommenes Rezept."""

    sha256: str
    stored_sha256: str
    recipe: recipe.Recipe
    path: Path


@dataclasses.dataclass(frozen=True, slots=True)
class PartRemovalUndo:
    """Der pfadfreie, bytegenaue Rückweg einer Bibliotheksentfernung."""

    name: str
    source: str
    sha256: str
    payload: bytes
    file_mode: int
    atime_ns: int
    mtime_ns: int


@dataclasses.dataclass(frozen=True, slots=True)
class RemovedPart:
    """Ein entfernter Baustein samt unmittelbarem Wiederherstellungstoken."""

    sha256: str
    recipe: recipe.Recipe
    undo: PartRemovalUndo


class PartFileIO:
    """Kodiert und prüft lokale Bausteindateien ohne Nebenwirkungen."""

    def __init__(self, *, clock: Clock = _utc_now) -> None:
        self._clock = clock

    def validate(self, payload: bytes) -> recipe.Recipe:
        """Prüft eine Datei vollständig, ohne Schreibzugriff."""

        return self._validated_recipe(payload)

    def export_file(self, part: recipe.Recipe) -> bytes:
        """Erzeugt eine vollständige, wieder einlesbare Austauschdatei."""

        # ``shared.rules`` leitet die erlaubten Operationen aus dem Register
        # ab. Ein frischer Prozess hat es noch nicht gefüllt; Export ist aber
        # auch dort ein vollständiger Kernweg und darf nicht von einem zuvor
        # geöffneten Fenster oder Test abhängen.
        from app.core.bootstrap import load_operations

        load_operations()
        payload = shared.for_export(part) + b"\n"
        self._validated_recipe(payload)
        return payload

    def export_to_file(self, part: recipe.Recipe, target: Path) -> Path:
        """Schreibt eine geprüfte Kundendatei vollständig und atomar.

        Der kundenseitige Name trägt immer die Solidon-Endung. Eine bereits
        vorhandene Datei wird erst ersetzt, nachdem alle neuen Bytes im selben
        Verzeichnis geschrieben und synchronisiert wurden.
        """

        destination = Path(target)
        if destination.suffix.lower() != PART_FILE_SUFFIX:
            destination = destination.with_suffix(PART_FILE_SUFFIX)
        payload = self.export_file(part)
        try:
            return recipe.publish_payload(destination, payload)
        except OSError as problem:
            raise FileWriteError(
                target=destination.name,
                detail=_(
                    "Die Bausteindatei konnte an diesem Ort nicht gespeichert werden. "
                    "Prüfen Sie den Ordnerzugriff und versuchen Sie es erneut oder "
                    "wählen Sie einen anderen Ort."
                ),
                values={"reason": "write_failed"},
            ) from problem

    def import_file(self, payload: bytes) -> ImportedPart:
        """Prüft die Datei und setzt den Nachweis ihrer unmittelbaren Herkunft."""

        parsed = self._validated_recipe(payload)
        digest = hashlib.sha256(payload).hexdigest()
        imported = dataclasses.replace(
            parsed,
            imported_origin=recipe.ImportedOrigin(
                source_sha256=digest,
                imported_at=self._origin_timestamp(),
            ),
        )
        return ImportedPart(sha256=digest, recipe=imported)

    def install_file(
        self,
        payload: bytes,
        *,
        name: str | None = None,
        parts: Any = None,
        registry: Any = None,
        directory: Path | None = None,
    ) -> InstalledPart:
        """Prüft und übernimmt eine Datei, ohne vorhandene Arbeit zu ersetzen.

        Ein anderer ``name`` ist nur der ausdrücklich gewählte Ausweg aus
        einer Kollision. Ohne diese Wahl hält der Kern an und liefert einen
        freien Vorschlag; der Aufrufer darf ihn anzeigen, aber nie still
        übernehmen.
        """

        imported = self.import_file(payload)
        part = imported.recipe
        if name is not None:
            if not re.fullmatch(shared.rules()["name_pattern"], name) or len(name) > 120:
                raise self._recipe_error(
                    _("Der Name kann nicht verwendet werden. Wählen Sie einen anderen Namen."),
                    field="name",
                )
            part = dataclasses.replace(part, name=name)
        target = (recipe.recipes_dir() if directory is None else directory) / f"{part.name}.json"
        try:
            path = recipe.install(part, parts, registry, directory)
        except OSError as problem:
            raise FileWriteError(
                target=target.name,
                detail=_(
                    "Der Baustein konnte nicht in den Katalog übernommen werden, weil "
                    "der Katalogordner nicht beschreibbar ist. Prüfen Sie den "
                    "Ordnerzugriff und versuchen Sie es erneut."
                ),
                values={"reason": "write_failed"},
            ) from problem
        return InstalledPart(
            sha256=imported.sha256,
            stored_sha256=hashlib.sha256(recipe._encoded_file(part)).hexdigest(),
            recipe=part,
            path=path,
        )

    def remove_from_library(
        self,
        name: str,
        *,
        expected_sha256: str | None = None,
        parts: Any = None,
        registry: Any = None,
        directory: Path | None = None,
    ) -> RemovedPart:
        """Entfernt ein lokales Rezept und liefert seinen exakten Rückweg.

        ``expected_sha256`` bindet insbesondere das Rückgängigmachen eines
        gerade ausgeführten Imports an genau dessen gespeicherte Bytes. Ein
        später unter demselben Namen geänderter Baustein wird nie still
        entfernt. Eingebaute und nur mit einem Dokument mitgereiste
        Bausteine gehören nicht zu diesem lokalen Dateiweg.
        """

        if expected_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise self._removal_error(
                _("Der erwartete Bausteinstand ist ungültig. Wählen Sie den Baustein erneut."),
                constraint="expected_sha256",
            )
        try:
            removed = recipe.remove_installed(
                name,
                parts,
                registry,
                directory,
                expected_sha256=expected_sha256,
                validate_payload=self._validated_recipe,
            )
        except ValueError as problem:
            reason = str(problem)
            if reason == "recipe_source_not_removable":
                raise self._removal_error(
                    _(
                        "Dieser Baustein gehört nicht zur lokalen Bibliothek und kann hier "
                        "nicht entfernt werden. Wählen Sie einen hinzugefügten oder selbst "
                        "gespeicherten Baustein."
                    ),
                    constraint="source",
                ) from problem
            if reason == "recipe_file_changed":
                raise self._removal_error(
                    _(
                        "Der Baustein wurde seit dem Hinzufügen geändert. Prüfen Sie den "
                        "aktuellen Stand und entfernen Sie ihn bei Bedarf erneut."
                    ),
                    constraint="changed",
                ) from problem
            raise self._removal_error(
                _(
                    "Der Baustein kann nicht sicher entfernt werden, weil Katalog und "
                    "gespeicherter Stand nicht zusammenpassen. Starten Sie Solidon neu "
                    "und versuchen Sie es erneut."
                ),
                constraint="library_state",
                retry=True,
            ) from problem
        except OSError as problem:
            raise self._removal_error(
                _(
                    "Der Baustein konnte nicht aus der lokalen Bibliothek entfernt werden. "
                    "Prüfen Sie den Ordnerzugriff und versuchen Sie es erneut."
                ),
                constraint="remove_failed",
                retry=True,
            ) from problem
        digest = hashlib.sha256(removed.payload).hexdigest()
        undo = PartRemovalUndo(
            name=removed.name,
            source=removed.source,
            sha256=digest,
            payload=removed.payload,
            file_mode=removed.metadata.mode,
            atime_ns=removed.metadata.atime_ns,
            mtime_ns=removed.metadata.mtime_ns,
        )
        return RemovedPart(sha256=digest, recipe=removed.recipe, undo=undo)

    def restore_to_library(
        self,
        undo: PartRemovalUndo,
        *,
        parts: Any = None,
        registry: Any = None,
        directory: Path | None = None,
    ) -> InstalledPart:
        """Stellt genau den vom Token beschriebenen Bibliotheksstand wieder her."""

        if (
            undo.source not in {recipe.RECIPE_SOURCE, recipe.IMPORTED_SOURCE}
            or not re.fullmatch(r"[0-9a-f]{64}", undo.sha256)
            or hashlib.sha256(undo.payload).hexdigest() != undo.sha256
            or undo.file_mode < 0
            or undo.file_mode > 0o7777
            or undo.atime_ns < 0
            or undo.mtime_ns < 0
        ):
            raise self._removal_error(
                _(
                    "Dieser Rückgängig-Stand ist unvollständig. Entfernen Sie den Baustein "
                    "bei Bedarf erneut."
                ),
                constraint="undo",
            )
        restored = self._validated_recipe(undo.payload)
        if restored.name != undo.name or recipe._catalog_source(restored) != undo.source:
            raise self._removal_error(
                _(
                    "Dieser Rückgängig-Stand gehört nicht zum gewählten Baustein. "
                    "Entfernen Sie den Baustein bei Bedarf erneut."
                ),
                constraint="undo",
            )
        stored = recipe.RemovedRecipeFile(
            name=undo.name,
            source=undo.source,
            payload=undo.payload,
            metadata=recipe.StoredFileMetadata(
                mode=undo.file_mode,
                atime_ns=undo.atime_ns,
                mtime_ns=undo.mtime_ns,
            ),
            recipe=restored,
        )
        try:
            path = recipe.restore_installed(stored, restored, parts, registry, directory)
        except ValidationError as problem:
            raise self._removal_error(
                _(
                    "Der Name wird inzwischen wieder von einem Baustein verwendet. "
                    "Prüfen Sie den aktuellen Stand und entfernen Sie ihn bei Bedarf erneut."
                ),
                constraint="exists",
            ) from problem
        except ValueError as problem:
            raise self._removal_error(
                _(
                    "Dieser Rückgängig-Stand passt nicht mehr zur lokalen Bibliothek. "
                    "Prüfen Sie den aktuellen Baustein und versuchen Sie es erneut."
                ),
                constraint="library_state",
                retry=True,
            ) from problem
        except OSError as problem:
            raise self._removal_error(
                _(
                    "Der Baustein konnte nicht wiederhergestellt werden. Prüfen Sie den "
                    "Ordnerzugriff und versuchen Sie es erneut."
                ),
                constraint="restore_failed",
                retry=True,
            ) from problem
        return InstalledPart(
            sha256=undo.sha256,
            stored_sha256=undo.sha256,
            recipe=restored,
            path=path,
        )

    @staticmethod
    def _removal_error(
        detail: TranslatableText | str,
        *,
        constraint: str,
        retry: bool = False,
    ) -> AppError:
        """Ein handlungsfähiger Bibliotheksfehler ohne Pfad oder Dateinamen."""

        return AppError(
            detail=detail,
            values={"reason": constraint},
            suggestions=((RETRY, CANCEL) if retry else (CANCEL,)),
        )

    def _origin_timestamp(self) -> str:
        """Die eine gespeicherte UTC-Schreibweise für Importquittungen."""

        timestamp = self._clock()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _validated_recipe(self, payload: bytes) -> recipe.Recipe:
        """Prüft die Dateiregeln und baut das Rezept einmal vollständig."""

        from app.core.bootstrap import load_operations

        load_operations()
        limits = shared.rules()
        if len(payload) > int(limits["max_file_bytes"]):
            raise self._resource_error(
                "recipe",
                len(payload),
                int(limits["max_file_bytes"]),
            )
        try:
            raw = self._decode_json(payload)
            if not isinstance(raw, dict):
                raise TypeError("recipe")
            self._resource_preflight(raw, limits)
            normalized = dict(raw)
            document = raw.get("document")
            if isinstance(document, dict):
                normalized["document"] = migrate(dict(document))
            normalized_payload = json.dumps(
                normalized,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            normalized_limits = dict(limits)
            normalized_limits["max_file_bytes"] = max(
                int(limits["max_file_bytes"]),
                len(normalized_payload),
            )
            # Die strikte Formprüfung läuft vor den sprechenden Befunden. So
            # kann kein fremder Schlüssel oder Pfad als Platzhalterwert in eine
            # spätere Fehlermeldung gelangen.
            self._strict_shape(normalized)
            findings = shared.inspect(normalized_payload, normalized_limits)
            if findings:
                raise ValidationError(
                    field="recipe",
                    detail=_(
                        "Dieser Baustein kann nicht hinzugefügt werden, weil seine Datei "
                        "unvollständig oder nicht mit dieser Solidon-Version kompatibel "
                        "ist. Wählen Sie eine andere Datei."
                    ),
                    constraint="shared_rules",
                    suggestions=(CHOOSE, CANCEL),
                )
            parsed = recipe.from_data(normalized)
        except ValidationError:
            raise
        except (
            AttributeError,
            KeyError,
            OverflowError,
            RecursionError,
            TypeError,
            ValueError,
        ) as problem:
            raise ValidationError(
                field="recipe",
                detail=_(
                    "Dieser Baustein kann nicht hinzugefügt werden, weil seine Datei "
                    "unvollständig oder nicht mit dieser Solidon-Version kompatibel "
                    "ist. Wählen Sie eine andere Datei."
                ),
                constraint="recipe_format",
                values={"reason": "invalid_recipe"},
                suggestions=(CHOOSE, CANCEL),
            ) from problem

        self._check_sources(parsed)
        recipe.build(parsed, profile=profiles.make_profile())
        return parsed

    def _resource_preflight(self, data: dict[str, Any], limits: dict[str, Any]) -> None:
        """Stoppt fremde Strukturmengen vor Base64-Dekodierung und Rezeptbau."""

        document = data.get("document")
        if isinstance(document, dict):
            self._source_id_preflight(document.get("sources"), "sources", limits)
            self._bounded_collection(
                document.get("parameters"),
                "parameters",
                int(limits["max_project_parameters"]),
            )
            self._bounded_collection(
                document.get("sources"),
                "sources",
                int(limits["max_sources"]),
            )
            operations = document.get("ops")
            self._bounded_collection(
                operations,
                "ops",
                int(limits["max_operations"]),
            )
            total_params = 0
            if isinstance(operations, list):
                for index, operation in enumerate(operations):
                    if not isinstance(operation, dict):
                        continue
                    for field, rule in (
                        ("in", "max_operation_inputs"),
                        ("out", "max_operation_outputs"),
                        ("translatable", "max_translatable_per_operation"),
                        ("matches", "max_matches_per_operation"),
                    ):
                        self._bounded_collection(
                            operation.get(field),
                            f"ops.{index}.{field}",
                            int(limits[rule]),
                        )
                    params = operation.get("params")
                    if not isinstance(params, dict):
                        continue
                    self._bounded_collection(
                        params,
                        f"ops.{index}.params",
                        int(limits["max_params_per_operation"]),
                    )
                    total_params += len(params)
                    for value in params.values():
                        self._bounded_parameter_value(
                            value,
                            f"ops.{index}.params",
                            limits,
                        )
            if total_params > int(limits["max_total_operation_params"]):
                raise self._resource_error(
                    "ops.params",
                    total_params,
                    int(limits["max_total_operation_params"]),
                )

        for field, rule in (
            ("payloads", "max_payloads"),
            ("features", "max_features"),
            ("exposed", "max_exposed"),
        ):
            self._bounded_collection(data.get(field), field, int(limits[rule]))

        report = data.get("range_report")
        if isinstance(report, dict):
            self._bounded_collection(
                report.get("failures"),
                "range_report.failures",
                int(limits["max_range_failures"]),
            )

        payloads = data.get("payloads")
        self._source_id_preflight(payloads, "payloads", limits)
        decoded_total = 0
        if isinstance(payloads, dict):
            for encoded in payloads.values():
                if not isinstance(encoded, str) or len(encoded) % 4:
                    continue
                padding = len(encoded) - len(encoded.rstrip("="))
                if padding > 2:
                    continue
                decoded_total += len(encoded) // 4 * 3 - padding
        if decoded_total > int(limits["max_decoded_payload_bytes"]):
            raise self._resource_error(
                "payloads",
                decoded_total,
                int(limits["max_decoded_payload_bytes"]),
            )

    def _source_id_preflight(
        self,
        value: Any,
        field: str,
        limits: dict[str, Any],
    ) -> None:
        """Stoppt Pfade in Quellenkennungen, bevor ein Befund sie spiegeln kann."""

        if not isinstance(value, dict):
            return
        pattern = str(limits["name_pattern"])
        if any(
            not isinstance(source_id, str)
            or len(source_id) > 120
            or not re.fullmatch(pattern, source_id)
            for source_id in value
        ):
            raise self._recipe_error(
                _("Eine Quelle des Rezepts ist ungültig."),
                field=field,
            )

    def _bounded_collection(self, value: Any, field: str, limit: int) -> None:
        """Prüft die Länge nur, wenn das Feld eine Sammlung ist."""

        if isinstance(value, dict | list) and len(value) > limit:
            raise self._resource_error(field, len(value), limit)

    def _bounded_parameter_value(
        self,
        value: Any,
        field: str,
        limits: dict[str, Any],
    ) -> None:
        """Begrenzt Zeichenketten und die einzige erlaubte Listenebene."""

        if isinstance(value, str) and len(value) > int(limits["max_value_chars"]):
            raise self._resource_error(field, len(value), int(limits["max_value_chars"]))
        if isinstance(value, list):
            if len(value) > int(limits["max_parameter_list_items"]):
                raise self._resource_error(
                    field,
                    len(value),
                    int(limits["max_parameter_list_items"]),
                )
            for item in value:
                if isinstance(item, str) and len(item) > int(limits["max_value_chars"]):
                    raise self._resource_error(
                        field,
                        len(item),
                        int(limits["max_value_chars"]),
                    )

    @staticmethod
    def _resource_error(field: str, count: int, limit: int) -> ValidationError:
        return ValidationError(
            field=field,
            detail=_(
                "Dieses Rezept überschreitet die sicheren Größen- oder "
                "Komplexitätsgrenzen. Wählen Sie einen kleineren Baustein."
            ),
            constraint="shared_resource_limit",
            values={"count": count, "limit": limit},
            suggestions=(CHOOSE, CANCEL),
        )

    def _strict_shape(self, data: dict[str, Any]) -> None:
        """Weist unbeachtete Zusatzfelder in den ausführbaren Rezeptdaten ab."""

        limits = shared.rules()
        self._known_keys(data, set(limits["recipe_keys"]), "recipe")
        for field, maximum, required in (
            ("name", 120, True),
            ("title", shared.MAX_TITLE_CHARS, True),
            ("group", 120, True),
            ("doc", shared.MAX_DOC_CHARS, False),
            ("author", shared.MAX_TITLE_CHARS, False),
            ("license", 30, False),
        ):
            value = data.get(field, "")
            if not isinstance(value, str) or len(value) > maximum or (required and not value):
                raise self._recipe_error(
                    _("Eine Grundangabe des Rezepts ist ungültig."),
                    field=field,
                )
        if not re.fullmatch(str(limits["name_pattern"]), data["name"]):
            raise self._recipe_error(_("Der interne Name des Rezepts ist ungültig."), field="name")
        if data["group"] not in limits["groups"]:
            raise self._recipe_error(_("Die Gruppe des Rezepts ist ungültig."), field="group")
        recipe_version = data.get("format_version")
        if (
            isinstance(recipe_version, bool)
            or not isinstance(recipe_version, int)
            or recipe_version not in limits["recipe_format_versions"]
        ):
            raise self._recipe_error(
                _("Die Formatversion des Rezepts ist ungültig."),
                field="format_version",
            )
        if data.get("license", "") not in {"", *recipe.RECIPE_LICENSES}:
            raise self._recipe_error(_("Die Lizenz des Rezepts ist ungültig."), field="license")
        self._validate_range_report(data.get("range_report"), limits)

        imported_origin = data.get("imported_origin")
        if imported_origin is not None:
            if not isinstance(imported_origin, dict):
                raise self._recipe_error(
                    _("Eine Grundangabe des Rezepts ist ungültig."),
                    field="imported_origin",
                )
            self._known_keys(
                imported_origin,
                {"source_sha256", "imported_at"},
                "imported_origin",
            )
            if set(imported_origin) != {"source_sha256", "imported_at"}:
                raise self._recipe_error(
                    _("Die Rezeptdaten sind unvollständig oder widersprüchlich."),
                    field="imported_origin",
                )
            if not isinstance(imported_origin["source_sha256"], str) or not re.fullmatch(
                r"[0-9a-f]{64}", imported_origin["source_sha256"]
            ):
                raise self._recipe_error(
                    _("Eine Grundangabe des Rezepts ist ungültig."),
                    field="imported_origin.source_sha256",
                )
            if not isinstance(imported_origin["imported_at"], str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                imported_origin["imported_at"],
            ):
                raise self._recipe_error(
                    _("Eine Grundangabe des Rezepts ist ungültig."),
                    field="imported_origin.imported_at",
                )

        document = data.get("document")
        if not isinstance(document, dict):
            raise self._recipe_error(_("Der Dokumentausschnitt des Rezepts fehlt."))
        self._known_keys(
            document,
            {
                "format_version",
                "app_version",
                "libs",
                "parts_version",
                "scene",
                "parameters",
                "sources",
                "fits",
                "transactions",
                "ops",
                "chat",
                "numbering",
                "print_settings",
            },
            "document",
        )
        for field in ("app_version", "parts_version"):
            value = document.get(field)
            if not isinstance(value, str) or len(value) > 120:
                raise self._recipe_error(
                    _("Eine Versionsangabe des Rezepts ist ungültig."),
                    field=f"document.{field}",
                )
        format_version = document.get("format_version")
        if isinstance(format_version, bool) or not isinstance(format_version, int):
            raise self._recipe_error(
                _("Die Dokumentversion des Rezepts ist ungültig."),
                field="document.format_version",
            )
        scene = document.get("scene", {})
        if not isinstance(scene, dict):
            raise self._recipe_error(_("Die Szenenangaben des Rezepts sind ungültig."))
        self._known_keys(scene, {"printer", "material"}, "document.scene")
        for key in ("printer", "material"):
            value = scene.get(key, "")
            if not isinstance(value, str) or len(value) > 120:
                raise self._recipe_error(
                    _("Eine Szenenangabe des Rezepts ist ungültig."),
                    field=f"document.scene.{key}",
                )

        numbering = document.get("numbering", {})
        if not isinstance(numbering, dict):
            raise self._recipe_error(_("Die Nummerierungsangaben des Rezepts sind ungültig."))
        self._known_keys(
            numbering,
            {"transaction", "op", "object"},
            "document.numbering",
        )
        for key, value in numbering.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise self._recipe_error(
                    _("Eine Nummerierungsangabe des Rezepts ist ungültig."),
                    field=f"document.numbering.{key}",
                )

        libraries = document.get("libs", {})
        if not isinstance(libraries, dict) or len(libraries) > 64:
            raise self._recipe_error(_("Die Bibliotheksangaben des Rezepts sind ungültig."))
        if any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or len(key) > 120
            or len(value) > 120
            for key, value in libraries.items()
        ):
            raise self._recipe_error(_("Eine Bibliotheksangabe des Rezepts ist ungültig."))
        for field in ("fits", "transactions", "chat"):
            if not isinstance(document.get(field), list) or document[field]:
                raise self._recipe_error(
                    _("Ein Baustein darf keine Projektverläufe, Chats oder Passungen mitführen."),
                    field=field,
                )
        if document.get("print_settings") is not None:
            raise self._recipe_error(
                _("Eine Bausteindatei darf keine Druckeinstellungen mitführen."),
                field="document.print_settings",
            )

        parameters = document.get("parameters", {})
        if not isinstance(parameters, dict):
            raise self._recipe_error(_("Die Parameterliste des Rezepts ist ungültig."))
        for name, entry in parameters.items():
            if not isinstance(name, str) or not isinstance(entry, dict):
                raise self._recipe_error(_("Ein Parameter des Rezepts ist ungültig."))
            self._known_keys(
                entry,
                {
                    "value",
                    "unit",
                    "min",
                    "max",
                    "title",
                    "title_translatable",
                    "title_context",
                    "expression",
                },
                f"parameters.{name}",
            )
            self._validate_parameter(name, entry)

        operations = document.get("ops")
        if not isinstance(operations, list):
            raise self._recipe_error(_("Die Schrittliste des Rezepts ist ungültig."))
        from app.core.registry import REGISTRY

        operation_ids: set[int] = set()
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                raise self._recipe_error(_("Ein Schritt des Rezepts ist ungültig."))
            self._known_keys(
                operation,
                {"id", "op", "in", "out", "params", "solver", "seed", "matches", "translatable"},
                f"ops.{index}",
            )
            self._validate_operation_shape(operation, index)
            identifier = operation["id"]
            if identifier in operation_ids:
                raise self._recipe_error(
                    _("Die Kennung eines Rezeptschritts kommt mehrfach vor."),
                    field=f"ops.{index}.id",
                )
            operation_ids.add(identifier)
            name = operation.get("op")
            if not isinstance(name, str) or not REGISTRY.has(name):
                raise self._recipe_error(
                    _("Ein Schritt des Rezepts ist in dieser Solidon-Version nicht bekannt."),
                    field=f"ops.{index}.op",
                )
            spec = REGISTRY.get(name)
            if spec.requires_seed and operation.get("seed") is None:
                raise self._recipe_error(
                    _("Der Startwert eines Rezeptschritts ist ungültig."),
                    field=f"ops.{index}.seed",
                )
            values = operation.get("params", {})
            if not isinstance(values, dict):
                raise self._recipe_error(_("Die Werte eines Rezeptschritts sind ungültig."))
            allowed = {entry.name for entry in spec.params.spec()}
            unknown = sorted(set(values) - allowed)
            if unknown:
                raise self._recipe_error(
                    _("Ein Rezeptschritt enthält unbekannte Einstellungen."),
                    field=f"ops.{index}.params",
                )

        sources = document.get("sources", {})
        if not isinstance(sources, dict):
            raise self._recipe_error(_("Die Quellenliste des Rezepts ist ungültig."))
        for source_id, entry in sources.items():
            if not isinstance(source_id, str) or not isinstance(entry, dict):
                raise self._recipe_error(_("Eine Quelle des Rezepts ist ungültig."))
            self._known_keys(
                entry,
                {"type", "path", "sha256", "embedded", "ingest", "origin"},
                f"sources.{source_id}",
            )
            if entry.get("type") not in {"import", "generated", "part", "image"}:
                raise self._recipe_error(
                    _("Die Art einer Rezeptquelle ist ungültig."),
                    field=f"sources.{source_id}.type",
                )
            path = entry.get("path")
            if not isinstance(path, str) or len(path) > 500:
                raise self._recipe_error(
                    _("Der Pfad einer Rezeptquelle ist ungültig."),
                    field=f"sources.{source_id}.path",
                )
            digest = entry.get("sha256")
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise self._recipe_error(
                    _("Die Prüfsumme einer Rezeptquelle ist ungültig."),
                    field=f"sources.{source_id}.sha256",
                )
            if entry.get("embedded") is not True:
                raise self._recipe_error(
                    _("Eine Quelle der Bausteindatei ist nicht eingebettet."),
                    field=f"sources.{source_id}.embedded",
                )
            ingest = entry.get("ingest", {})
            if not isinstance(ingest, dict):
                raise self._recipe_error(_("Die Einlesedaten einer Quelle sind ungültig."))
            self._known_keys(
                ingest,
                {"unit", "scale", "welded", "removed_triangles", "components"},
                f"sources.{source_id}.ingest",
            )
            self._validate_ingest(ingest, source_id)
            origin = entry.get("origin")
            if origin is not None:
                if not isinstance(origin, dict):
                    raise self._recipe_error(_("Die Herkunft einer Quelle ist ungültig."))
                self._known_keys(
                    origin,
                    {"url", "title", "author", "license", "retrieved", "prompt", "seed"},
                    f"sources.{source_id}.origin",
                )
                for key in ("url", "title", "author", "license", "retrieved", "prompt"):
                    value = origin.get(key)
                    if value is not None and (not isinstance(value, str) or len(value) > 2_000):
                        raise self._recipe_error(
                            _("Ein Textfeld der Quellenherkunft ist ungültig."),
                            field=f"sources.{source_id}.origin.{key}",
                        )
                seed = origin.get("seed")
                if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
                    raise self._recipe_error(
                        _("Der Startwert einer Quellenherkunft ist ungültig."),
                        field=f"sources.{source_id}.origin.seed",
                    )

        exposed = data.get("exposed", [])
        if not isinstance(exposed, list):
            raise self._recipe_error(_("Die freigegebenen Maße des Rezepts sind ungültig."))
        exposed_keys = {
            "name",
            "title",
            "default",
            "unit",
            "minimum",
            "maximum",
            "placement",
            "doc",
        }
        for index, entry in enumerate(exposed):
            if not isinstance(entry, dict):
                raise self._recipe_error(_("Ein freigegebenes Maß des Rezepts ist ungültig."))
            self._known_keys(entry, exposed_keys, f"exposed.{index}")
            self._validate_exposed(entry, index)
        exposed_names = [entry["name"] for entry in exposed]
        if len(set(exposed_names)) != len(exposed_names):
            raise self._recipe_error(
                _("Ein freigegebener Parameter kommt mehrfach vor."),
                field="exposed",
            )
        unknown_exposed = sorted(set(exposed_names) - set(parameters))
        if unknown_exposed:
            raise self._recipe_error(
                _("Ein freigegebenes Maß verweist auf keinen Projektparameter."),
                field="exposed",
            )

        features = data.get("features", {})
        if not isinstance(features, dict):
            raise self._recipe_error(_("Die Merkmalsliste des Rezepts ist ungültig."))
        for public, internal in features.items():
            if (
                not isinstance(public, str)
                or not isinstance(internal, str)
                or not public
                or not internal
                or len(public) > 120
                or len(internal) > 120
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,119}", public)
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,119}", internal)
            ):
                raise self._recipe_error(_("Ein benanntes Merkmal des Rezepts ist ungültig."))

    def _validate_range_report(self, report: Any, limits: dict[str, Any]) -> None:
        """Prüft den optionalen Bereichsbericht ohne weiche Konvertierung."""

        if report is None:
            return
        if not isinstance(report, dict):
            raise self._recipe_error(_("Der Bereichsbericht des Rezepts ist ungültig."))
        self._known_keys(report, {"checked", "failures"}, "range_report")
        if set(report) != {"checked", "failures"}:
            raise self._recipe_error(_("Der Bereichsbericht des Rezepts ist unvollständig."))
        checked = report["checked"]
        failures = report["failures"]
        if isinstance(checked, bool) or not isinstance(checked, int) or checked < 0:
            raise self._recipe_error(
                _("Die Zahl der Bereichsprüfungen ist ungültig."),
                field="range_report.checked",
            )
        if not isinstance(failures, list):
            raise self._recipe_error(
                _("Die Fehlerliste des Bereichsberichts ist ungültig."),
                field="range_report.failures",
            )
        if len(failures) > int(limits["max_range_failures"]):
            raise self._resource_error(
                "range_report.failures",
                len(failures),
                int(limits["max_range_failures"]),
            )
        if len(failures) > checked:
            raise self._recipe_error(
                _("Der Bereichsbericht enthält mehr Fehler als Prüfungen."),
                field="range_report",
            )
        for index, failure in enumerate(failures):
            field = f"range_report.failures.{index}"
            if not isinstance(failure, dict):
                raise self._recipe_error(_("Ein Bereichsfehler ist ungültig."), field=field)
            self._known_keys(failure, {"values", "reason"}, field)
            if set(failure) != {"values", "reason"}:
                raise self._recipe_error(_("Ein Bereichsfehler ist unvollständig."), field=field)
            values = failure["values"]
            reason = failure["reason"]
            if (
                not isinstance(values, dict)
                or len(values) > int(limits["max_exposed"])
                or any(
                    not isinstance(name, str)
                    or not name
                    or len(name) > 120
                    or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,119}", name)
                    or not self._finite_number(value)
                    for name, value in values.items()
                )
            ):
                raise self._recipe_error(
                    _("Die Werte eines Bereichsfehlers sind ungültig."),
                    field=f"{field}.values",
                )
            if not isinstance(reason, str) or not reason or len(reason) > shared.MAX_DOC_CHARS:
                raise self._recipe_error(
                    _("Die Begründung eines Bereichsfehlers ist ungültig."),
                    field=f"{field}.reason",
                )

    def _validate_parameter(self, name: str, entry: dict[str, Any]) -> None:
        """Prüft Projektparameter vor den toleranten Serializer-Konvertierungen."""

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,119}", name):
            raise self._recipe_error(
                _("Der Name eines Parameters ist ungültig."),
                field="parameters",
            )
        field = f"parameters.{name}"
        if "value" not in entry or not self._finite_number(entry["value"]):
            raise self._recipe_error(
                _("Der Wert eines Parameters ist ungültig."),
                field=f"{field}.value",
            )
        unit = entry.get("unit", "mm")
        if not isinstance(unit, str) or len(unit) > 20:
            raise self._recipe_error(
                _("Die Einheit eines Parameters ist ungültig."),
                field=f"{field}.unit",
            )
        for key in ("min", "max"):
            value = entry.get(key)
            if value is not None and not self._finite_number(value):
                raise self._recipe_error(
                    _("Eine Grenze eines Parameters ist ungültig."),
                    field=f"{field}.{key}",
                )
        minimum = entry.get("min")
        maximum = entry.get("max")
        value = entry["value"]
        if (
            (minimum is not None and maximum is not None and minimum > maximum)
            or (minimum is not None and value < minimum)
            or (maximum is not None and value > maximum)
        ):
            raise self._recipe_error(
                _("Der Parameterwert liegt außerhalb seiner Grenzen."),
                field=field,
            )
        title = entry.get("title")
        context = entry.get("title_context")
        expression = entry.get("expression")
        if title is not None and (not isinstance(title, str) or len(title) > 120):
            raise self._recipe_error(
                _("Der Titel eines Parameters ist ungültig."),
                field=f"{field}.title",
            )
        if "title_translatable" in entry and not isinstance(entry["title_translatable"], bool):
            raise self._recipe_error(
                _("Die Übersetzungsangabe eines Parameters ist ungültig."),
                field=f"{field}.title_translatable",
            )
        if context is not None and (not isinstance(context, str) or len(context) > 120):
            raise self._recipe_error(
                _("Der Übersetzungskontext eines Parameters ist ungültig."),
                field=f"{field}.title_context",
            )
        if expression is not None and (
            not isinstance(expression, str) or len(expression) > shared.MAX_VALUE_CHARS
        ):
            raise self._recipe_error(
                _("Der Ausdruck eines Parameters ist ungültig."),
                field=f"{field}.expression",
            )

    def _validate_operation_shape(self, operation: dict[str, Any], index: int) -> None:
        """Prüft Metadaten eines Schritts, bevor der Serializer sie umdeutet."""

        step = f"ops.{index}"
        required = {"id", "op", "in", "out", "params"}
        if not required <= set(operation):
            raise self._recipe_error(
                _("Ein Rezeptschritt ist unvollständig."),
                field=step,
                missing=", ".join(sorted(required - set(operation))),
            )
        identifier = operation.get("id")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier < 1:
            raise self._recipe_error(
                _("Die Kennung eines Rezeptschritts ist ungültig."),
                field=f"{step}.id",
            )
        for key in ("in", "out"):
            values = operation.get(key, [])
            limit = shared.MAX_OPERATION_INPUTS if key == "in" else shared.MAX_OPERATION_OUTPUTS
            if (
                not isinstance(values, list)
                or any(
                    not isinstance(value, str)
                    or not re.fullmatch(r"obj_[1-9][0-9]*", value)
                    or len(value) > 120
                    for value in values
                )
                or len(values) > limit
            ):
                raise self._recipe_error(
                    _("Die Objektverweise eines Rezeptschritts sind ungültig."),
                    field=f"{step}.{key}",
                )
        seed = operation.get("seed")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            raise self._recipe_error(
                _("Der Startwert eines Rezeptschritts ist ungültig."),
                field=f"{step}.seed",
            )
        translatable = operation.get("translatable", [])
        if (
            not isinstance(translatable, list)
            or any(
                not isinstance(value, str)
                or not value
                or len(value) > 120
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,119}", value)
                for value in translatable
            )
            or len(translatable) > shared.MAX_TRANSLATABLE_PER_OPERATION
        ):
            raise self._recipe_error(
                _("Die Übersetzungsangaben eines Rezeptschritts sind ungültig."),
                field=f"{step}.translatable",
            )
        parameters = operation.get("params")
        if not isinstance(parameters, dict):
            raise self._recipe_error(
                _("Die Werte eines Rezeptschritts sind ungültig."),
                field=f"{step}.params",
            )
        if len(set(translatable)) != len(translatable) or not set(translatable) <= set(parameters):
            raise self._recipe_error(
                _("Die Übersetzungsangaben passen nicht zu den Schrittwerten."),
                field=f"{step}.translatable",
            )
        self._validate_solver(operation.get("solver"), step)
        self._validate_matches(operation.get("matches", {}), step)

    def _validate_solver(self, solver: Any, step: str) -> None:
        """Prüft die optionale gespeicherte Löserauskunft eines Schritts."""

        from app.core.geom.boolean import FULL_CHAIN

        if solver is None:
            return
        if not isinstance(solver, dict):
            raise self._recipe_error(
                _("Die Löserauskunft eines Rezeptschritts ist ungültig."),
                field=f"{step}.solver",
            )
        self._known_keys(solver, {"strategy", "attempted", "seed", "note"}, f"{step}.solver")
        if (
            not isinstance(solver.get("strategy"), str)
            or not solver["strategy"]
            or solver["strategy"] not in FULL_CHAIN
        ):
            raise self._recipe_error(
                _("Die Löserstrategie eines Rezeptschritts ist ungültig."),
                field=f"{step}.solver.strategy",
            )
        attempted = solver.get("attempted", [])
        if (
            not isinstance(attempted, list)
            or any(not isinstance(value, str) or value not in FULL_CHAIN for value in attempted)
            or len(attempted) > shared.MAX_OPERATION_OUTPUTS
        ):
            raise self._recipe_error(
                _("Die Löserversuche eines Rezeptschritts ist ungültig."),
                field=f"{step}.solver.attempted",
            )
        seed = solver.get("seed")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            raise self._recipe_error(
                _("Der Löserstartwert eines Rezeptschritts ist ungültig."),
                field=f"{step}.solver.seed",
            )
        note = solver.get("note")
        if note is not None and (not isinstance(note, str) or len(note) > shared.MAX_DOC_CHARS):
            raise self._recipe_error(
                _("Der Löserhinweis eines Rezeptschritts ist ungültig."),
                field=f"{step}.solver.note",
            )

    def _validate_matches(self, matches: Any, step: str) -> None:
        """Prüft gespeicherte Antworten auf Merkmalsrückfragen."""

        from app.core.registry import FEATURE_KINDS

        if not isinstance(matches, dict) or len(matches) > shared.MAX_MATCHES_PER_OPERATION:
            raise self._recipe_error(
                _("Die Merkmalszuordnungen eines Rezeptschritts sind ungültig."),
                field=f"{step}.matches",
            )
        expected = {"kind", "relative", "axis", "diameter", "directional"}
        for name, fingerprint in matches.items():
            if (
                not isinstance(name, str)
                or not name
                or len(name) > shared.MAX_TITLE_CHARS
                or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,119}", name)
                or not isinstance(fingerprint, dict)
            ):
                raise self._recipe_error(
                    _("Eine Merkmalszuordnung eines Rezeptschritts ist ungültig."),
                    field=f"{step}.matches",
                )
            self._known_keys(fingerprint, expected, f"{step}.matches.{name}")
            if set(fingerprint) != expected:
                raise self._recipe_error(
                    _("Eine Merkmalszuordnung eines Rezeptschritts ist unvollständig."),
                    field=f"{step}.matches.{name}",
                )
            if (
                not isinstance(fingerprint["kind"], str)
                or not fingerprint["kind"]
                or fingerprint["kind"] not in FEATURE_KINDS
            ):
                raise self._recipe_error(
                    _("Die Art einer Merkmalszuordnung ist ungültig."),
                    field=f"{step}.matches.{name}.kind",
                )
            for key in ("relative", "axis"):
                vector = fingerprint[key]
                if (
                    not isinstance(vector, list)
                    or len(vector) != 3
                    or any(not self._finite_number(value) for value in vector)
                ):
                    raise self._recipe_error(
                        _("Ein Vektor einer Merkmalszuordnung ist ungültig."),
                        field=f"{step}.matches.{name}.{key}",
                    )
            if not self._finite_number(fingerprint["diameter"]) or not isinstance(
                fingerprint["directional"], bool
            ):
                raise self._recipe_error(
                    _("Eine Größenangabe der Merkmalszuordnung ist ungültig."),
                    field=f"{step}.matches.{name}",
                )

    def _validate_exposed(self, entry: dict[str, Any], index: int) -> None:
        """Prüft ein freigegebenes Maß ohne weiche Dataclass-Konvertierung."""

        field = f"exposed.{index}"
        for key in ("name", "title"):
            value = entry.get(key)
            if not isinstance(value, str) or not value or len(value) > 120:
                raise self._recipe_error(
                    _("Name oder Titel eines freigegebenen Maßes ist ungültig."),
                    field=f"{field}.{key}",
                )
        if not self._finite_number(entry.get("default")):
            raise self._recipe_error(
                _("Der Vorgabewert eines freigegebenen Maßes ist ungültig."),
                field=f"{field}.default",
            )
        for key in ("minimum", "maximum"):
            value = entry.get(key)
            if value is not None and not self._finite_number(value):
                raise self._recipe_error(
                    _("Eine Grenze des freigegebenen Maßes ist ungültig."),
                    field=f"{field}.{key}",
                )
        default = entry["default"]
        minimum = entry.get("minimum")
        maximum = entry.get("maximum")
        if (
            (minimum is not None and maximum is not None and minimum > maximum)
            or (minimum is not None and default < minimum)
            or (maximum is not None and default > maximum)
        ):
            raise self._recipe_error(
                _("Der Vorgabewert eines freigegebenen Maßes liegt außerhalb seiner Grenzen."),
                field=field,
            )
        unit = entry.get("unit", "mm")
        doc = entry.get("doc", "")
        placement = entry.get("placement", "front")
        if not isinstance(unit, str) or len(unit) > 20:
            raise self._recipe_error(
                _("Die Einheit eines freigegebenen Maßes ist ungültig."),
                field=f"{field}.unit",
            )
        if not isinstance(doc, str) or len(doc) > 2_000:
            raise self._recipe_error(
                _("Die Beschreibung eines freigegebenen Maßes ist ungültig."),
                field=f"{field}.doc",
            )
        if placement not in {"front", "advanced"}:
            raise self._recipe_error(
                _("Die Platzierung eines freigegebenen Maßes ist ungültig."),
                field=f"{field}.placement",
            )

    @staticmethod
    def _finite_number(value: Any) -> bool:
        return (
            not isinstance(value, bool) and isinstance(value, int | float) and math.isfinite(value)
        )

    def _validate_ingest(self, ingest: dict[str, Any], source_id: str) -> None:
        """Begrenzt die skalaren Angaben einer eingebetteten Quelle."""

        unit = ingest.get("unit", "mm")
        if not isinstance(unit, str) or len(unit) > 20:
            raise self._recipe_error(
                _("Die Einheit einer Rezeptquelle ist ungültig."),
                field=f"sources.{source_id}.ingest.unit",
            )
        scale = ingest.get("scale", 1.0)
        if (
            isinstance(scale, bool)
            or not isinstance(scale, int | float)
            or not math.isfinite(scale)
            or scale <= 0
        ):
            raise self._recipe_error(
                _("Der Maßstab einer Rezeptquelle ist ungültig."),
                field=f"sources.{source_id}.ingest.scale",
            )
        if not isinstance(ingest.get("welded", False), bool):
            raise self._recipe_error(
                _("Die Reparaturangabe einer Rezeptquelle ist ungültig."),
                field=f"sources.{source_id}.ingest.welded",
            )
        for key in ("removed_triangles", "components"):
            value = ingest.get(key, 0 if key == "removed_triangles" else 1)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= 10_000_000
            ):
                raise self._recipe_error(
                    _("Eine Mengenangabe der Rezeptquelle ist ungültig."),
                    field=f"sources.{source_id}.ingest.{key}",
                )

    def _check_sources(self, parsed: recipe.Recipe) -> None:
        """Erlaubt nur eingebettete, relative Quellen mit richtiger Prüfsumme."""

        from app.core.registry import REGISTRY

        source_ids = set(parsed.document.sources)
        payload_ids = set(parsed.payloads)
        if source_ids != payload_ids:
            raise self._recipe_error(
                _("Die eingebetteten Quelldaten passen nicht zur Quellenliste."),
                field="payloads",
                count=len(source_ids.symmetric_difference(payload_ids)),
            )
        referenced: set[str] = set()
        consumers: list[tuple[str, str, str]] = []
        source_pattern = str(shared.rules()["name_pattern"])
        for operation in parsed.document.ops:
            spec = REGISTRY.get(operation.op)
            for parameter in spec.params.spec():
                if parameter.kind not in {"source", "image"}:
                    continue
                source_id = operation.params.get(parameter.name)
                if source_id is None or source_id == "":
                    continue
                if (
                    not isinstance(source_id, str)
                    or len(source_id) > 120
                    or not re.fullmatch(source_pattern, source_id)
                ):
                    raise self._recipe_error(
                        _("Eine Quelle des Rezepts ist ungültig."),
                        field="sources",
                    )
                referenced.add(source_id)
                consumers.append((source_id, parameter.kind, operation.op))
        for source_id, source in parsed.document.sources.items():
            candidate = PureWindowsPath(source.path)
            if (
                not source.path
                or any(ord(char) <= 32 or ord(char) == 127 for char in source.path)
                or candidate.drive
                or candidate.is_absolute()
                or ".." in candidate.parts
                or source.path.startswith(("/", "\\"))
                or "\\" in source.path
                or ":" in source.path
            ):
                raise self._recipe_error(
                    _("Quellen in Bausteindateien müssen einen relativen Pfad verwenden."),
                    field=f"sources.{source_id}.path",
                )
            if not source.embedded:
                raise self._recipe_error(
                    _("Geteilte Bausteine müssen ihre benötigten Quelldaten einbetten."),
                    field=f"sources.{source_id}.embedded",
                )
            if not re.fullmatch(r"[0-9a-f]{64}", source.sha256):
                raise self._recipe_error(
                    _("Die Prüfsumme einer eingebetteten Quelle ist ungültig."),
                    field=f"sources.{source_id}.sha256",
                )
            if source.origin is not None and source.origin.url:
                try:
                    if any(ord(char) <= 32 or ord(char) == 127 for char in source.origin.url):
                        raise ValueError("control character")
                    origin = urlsplit(source.origin.url)
                    secure_origin = (
                        origin.scheme in {"http", "https"}
                        and bool(origin.hostname)
                        and origin.username is None
                        and origin.password is None
                        and (origin.port is None or 0 < origin.port <= 65_535)
                    )
                except (AttributeError, TypeError, ValueError):
                    secure_origin = False
                if not secure_origin:
                    raise self._recipe_error(
                        _("Eine Herkunftsadresse des Bausteins ist nicht sicher."),
                        field=f"sources.{source_id}.origin.url",
                    )
            payload = parsed.payloads[source_id]
            digest = hashlib.sha256(payload).hexdigest()
            if source.sha256 and digest != source.sha256:
                raise self._recipe_error(
                    _("Die Prüfsumme einer eingebetteten Quelle stimmt nicht."),
                    field=f"sources.{source_id}.sha256",
                )
        if referenced != source_ids:
            raise self._recipe_error(
                _(
                    "Jede eingebettete Quelle muss von einem registrierten Quellenfeld "
                    "in einem Rezeptschritt verwendet werden."
                ),
                field="sources",
            )
        for source_id, parameter_kind, operation_name in consumers:
            source = parsed.document.sources[source_id]
            if (parameter_kind == "image") != (source.kind == "image"):
                raise self._recipe_error(
                    _("Die Art einer Rezeptquelle ist ungültig."),
                    field=f"sources.{source_id}.type",
                )
            allowed = self._source_suffixes(operation_name)
            if allowed is not None and Path(source.path).suffix.lower() not in allowed:
                raise self._recipe_error(
                    _("Der Pfad einer Rezeptquelle ist ungültig."),
                    field=f"sources.{source_id}.path",
                )

    @staticmethod
    def _source_suffixes(operation_name: str) -> tuple[str, ...] | None:
        """Der Dateivertrag des registrierten Importwegs, falls er einen hat."""

        if operation_name == "load":
            from app.core.geom.mesh import READABLE_SUFFIXES

            return READABLE_SUFFIXES
        if operation_name == "load_outline":
            from app.core.ingest.outline import OUTLINE_SUFFIXES

            return OUTLINE_SUFFIXES
        if operation_name == "load_step":
            from app.core.brep.step import SUFFIXES

            return SUFFIXES
        if operation_name == "sculpt_strokes":
            return (".stl",)
        return None

    def _known_keys(
        self,
        data: dict[str, Any],
        allowed: set[str],
        field: str,
    ) -> None:
        unknown = sorted(set(data) - allowed)
        if unknown:
            raise self._recipe_error(
                _("Das Rezept enthält unbekannte Zusatzdaten."),
                field=field,
            )

    def _recipe_error(
        self, detail: Any, *, field: str = "recipe", **values: Any
    ) -> ValidationError:
        field = self._public_error_field(field)
        if field == "name":
            detail = _("Der Name kann nicht verwendet werden. Wählen Sie einen anderen Namen.")
        elif "source" in field or "payload" in field:
            detail = _(
                "Dieser Baustein kann nicht hinzugefügt werden, weil die Datei nicht "
                "alle benötigten Daten sicher enthält. Wählen Sie eine andere Datei."
            )
        else:
            detail = _(
                "Dieser Baustein kann nicht hinzugefügt werden, weil seine Datei "
                "unvollständig oder nicht mit dieser Solidon-Version kompatibel ist. "
                "Wählen Sie eine andere Datei."
            )
        return ValidationError(
            field=field,
            detail=detail,
            constraint="recipe_format",
            values=values,
            suggestions=(CHOOSE, CANCEL),
        )

    @staticmethod
    def _public_error_field(field: str) -> str:
        """Entfernt fremde Kennungen aus dem serialisierten Fehlerpfad."""

        segments = field.split(".")
        if segments[0] in {"parameters", "sources", "payloads", "features"} and len(segments) > 1:
            segments.pop(1)
        if "matches" in segments:
            position = segments.index("matches")
            if len(segments) > position + 1:
                segments.pop(position + 1)
        return ".".join(segments)

    @staticmethod
    def _reject_json_constant(value: str) -> None:
        """JSON kennt weder NaN noch Unendlich; fremde Rezepte auch nicht."""

        raise ValueError("invalid_json_constant")

    @staticmethod
    def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        """Lehnt doppelte JSON-Schlüssel ab, statt den letzten still zu nehmen."""

        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def _decode_json(self, payload: bytes) -> Any:
        """Dekodiert fremdes JSON mit Tiefen- und Schlüsselgrenzen."""

        if self._json_too_deep(payload):
            raise ValidationError(
                field="recipe",
                detail=_(
                    "Dieser Baustein kann nicht hinzugefügt werden, weil seine Datei "
                    "unvollständig oder nicht mit dieser Solidon-Version kompatibel "
                    "ist. Wählen Sie eine andere Datei."
                ),
                constraint="json_depth",
                suggestions=(CHOOSE, CANCEL),
            )
        try:
            data = json.loads(
                payload,
                parse_constant=self._reject_json_constant,
                object_pairs_hook=self._unique_object,
            )
            if has_lone_surrogate(data):
                raise ValueError("unicode_scalar")
            return data
        except (RecursionError, UnicodeDecodeError, ValueError) as problem:
            raise ValidationError(
                field="recipe",
                detail=_(
                    "Dieser Baustein kann nicht hinzugefügt werden, weil seine Datei "
                    "unvollständig oder nicht mit dieser Solidon-Version kompatibel "
                    "ist. Wählen Sie eine andere Datei."
                ),
                constraint="recipe_format",
                values={"reason": "invalid_json"},
                suggestions=(CHOOSE, CANCEL),
            ) from problem

    @staticmethod
    def _json_too_deep(payload: bytes) -> bool:
        """Misst JSON-Klammern ohne Inhalte in Zeichenketten mitzuzählen."""

        depth = 0
        in_string = False
        escaped = False
        for byte in payload:
            if in_string:
                if escaped:
                    escaped = False
                elif byte == 0x5C:  # Rückstrich
                    escaped = True
                elif byte == 0x22:  # Anführungszeichen
                    in_string = False
                continue
            if byte == 0x22:
                in_string = True
            elif byte in (0x5B, 0x7B):  # [ {
                depth += 1
                if depth > shared.MAX_PART_FILE_JSON_DEPTH:
                    return True
            elif byte in (0x5D, 0x7D):  # ] }
                depth -= 1
        return False
