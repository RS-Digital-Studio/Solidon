"""Export und die Prüfung, die davor läuft (Bauplan §29, §16.3).

Die Prüfung ist ein Bericht, keine Sperre: Wasserdichtheit, Bauraum,
Wandstärke und die Lizenz der Quellen werden genannt, und wer trotzdem
exportieren will, kann das — er weiß dann nur, was er tut.

Das Namensschema zählt mehr, als es aussieht. Wer drei Teile druckt, will auf
der Platte sehen, welches welches ist — also ist
``projekt_halterung_1von3.stl`` die Vorgabe, und Objektnamen werden
dateisystemtauglich gemacht, ohne unlesbar zu werden.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import trimesh

from app.core.errors import ValidationError
from app.core.export import threemf
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import check_build_volume
from app.core.log import get_logger
from app.core.types import BRepBody, Finding, MaterialSlot, Mesh, Profile, SceneObject, Source
from app.core.units import format_length
from app.i18n import _, tr

_log = get_logger(__name__)

ExportFormat = Literal["stl", "3mf", "obj", "ply", "step"]

#: Als was jedes Format geschrieben wird. STL bleibt binär — ASCII wäre für
#: dieselben Dreiecke fünfmal so groß.
FORMAT_SUFFIX: dict[ExportFormat, str] = {
    "stl": ".stl",
    "3mf": ".3mf",
    "obj": ".obj",
    "ply": ".ply",
    # §30: nur ein B-Rep-Objekt hat etwas, das in eine STEP-Datei gehört. Ein
    # als STEP exportiertes Netz wäre eine STEP-Datei voller Dreiecke — legal,
    # und eine Lüge über ihren Inhalt.
    "step": ".step",
}

#: Vorgabe-Namensschema (§29). ``{index}`` und ``{count}`` erscheinen nur,
#: wenn es mehr als ein Teil gibt.
DEFAULT_SCHEME = "{project}_{object}_{index}von{count}"
SINGLE_SCHEME = "{project}_{object}"

#: Bei mehr als einer Druckplatte kommt die Platte in den Namen (§25). Wer
#: die Dateien zum Drucker trägt, muss wissen, welche zusammengehören.
PLATE_SCHEME = "{project}_platte{plate}_{object}_{index}von{count}"

_UNSAFE = re.compile(r"[^\w\-. ]+", re.UNICODE)


def safe_name(text: str, fallback: str = "teil") -> str:
    """Dateisystemtauglich, ohne unkenntlich zu werden.

    Deutsche Umlaute werden transliteriert statt weggeworfen: ``Gehäuse`` wird
    ``Gehaeuse``, nicht ``Gehuse``. Das ist eine bewusste Konvention für
    deutsche Dateinamen, und sie wurde früher durchgesetzt, indem der ganze Name
    durch ASCII gezwungen wurde — und genau dort fing „unkenntlich" an, statt
    aufzuhören: ein heruntergeladenes ``埃菲尔铁塔18cm`` kam als ``18cm`` heraus,
    ein ``Соединитель`` als ``teil``. Ein Dateiname ist nicht der Ort, an dem
    entschieden wird, welche Alphabete es gibt.

    Wirklich unsicher ist eine kurze Liste — Pfadtrenner, Doppelpunkte, die
    Zeichen, die Windows sich vorbehält — und :data:`_UNSAFE` hält sich bereits
    daran: ``\w`` deckt jeden Buchstaben ab, den Unicode kennt.
    """
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
    for character, replacement in replacements.items():
        text = text.replace(character, replacement)
    text = unicodedata.normalize("NFC", text)
    text = _UNSAFE.sub("", text).strip().replace(" ", "_")
    return text or fallback


@dataclass(frozen=True, slots=True)
class ExportEntry:
    """Eine Datei, die gleich geschrieben wird."""

    object_id: str
    filename: str
    mesh: MeshData
    slots: tuple[MaterialSlot, ...] = ()
    """The material slots of the object — 3MF carries them as colour groups (§20)."""
    name: str = ""
    body: Mesh | None = None
    """The object as it is in the scene. STEP needs the exact body, not the
    triangles it was tessellated into (§30)."""
    plate: int = 0
    """Which build plate this file belongs to (§25)."""


@dataclass(frozen=True, slots=True)
class ExportPlan:
    """Was geschrieben würde, und was die Prüfung vorher gefunden hat."""

    entries: tuple[ExportEntry, ...] = ()
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def blocked(self) -> bool:
        """Nie wahr — die Prüfung berichtet, sie blockiert nicht (§29)."""
        return False


def plan_export(
    objects: list[SceneObject],
    *,
    project_name: str,
    profile: Profile,
    export_format: ExportFormat = "stl",
    scheme: str | None = None,
    sources: dict[str, Source] | None = None,
) -> ExportPlan:
    """Ermittelt die Dateinamen und führt die Prüfung vor dem Export aus."""
    if not objects:
        raise ValidationError(
            field="objects",
            detail=_("Es ist nichts zum Exportieren ausgewählt."),
            constraint="empty",
        )

    count = len(objects)
    plates = len({entry.plate for entry in objects})
    if scheme is not None:
        pattern = scheme
    elif plates > 1:
        pattern = PLATE_SCHEME
    else:
        pattern = DEFAULT_SCHEME if count > 1 else SINGLE_SCHEME
    suffix = FORMAT_SUFFIX[export_format]

    entries = tuple(
        ExportEntry(
            object_id=entry.id,
            filename=safe_name(
                pattern.format(
                    project=safe_name(project_name, "projekt"),
                    object=safe_name(entry.name),
                    index=index,
                    count=count,
                    plate=entry.plate + 1,
                )
            )
            + suffix,
            mesh=as_mesh_data(entry.mesh),
            slots=tuple(entry.material_slots),
            name=entry.name,
            body=entry.mesh,
            plate=entry.plate,
        )
        for index, entry in enumerate(objects, start=1)
    )
    return ExportPlan(
        entries=entries,
        findings=tuple(check_before_export(objects, profile, sources or {})),
    )


def check_before_export(
    objects: list[SceneObject], profile: Profile, sources: dict[str, Source]
) -> list[Finding]:
    """Ein Bericht vor dem Schreiben, keine Sperre (§29)."""
    findings: list[Finding] = []
    meshes = [as_mesh_data(entry.mesh) for entry in objects]

    for entry, mesh in zip(objects, meshes, strict=True):
        if not mesh.is_watertight:
            findings.append(
                Finding(
                    code="export.not_watertight",
                    severity="warning",
                    message=_("Das Objekt ist nicht geschlossen — der Slicer wird raten müssen."),
                    object_id=entry.id,
                )
            )
        if mesh.triangle_count == 0:
            findings.append(
                Finding(
                    code="export.empty",
                    severity="error",
                    message=_("Das Objekt hat keine Geometrie."),
                    object_id=entry.id,
                )
            )

    findings.extend(check_build_volume(meshes, profile, [entry.plate for entry in objects]))
    findings.extend(_licence_findings(sources))
    return findings


def _licence_findings(sources: dict[str, Source]) -> list[Finding]:
    """§16.3: ein sachlicher Hinweis, wenn eine Quelle eine Einschränkung
    trägt. Keine Belehrung.
    """
    restricted = [
        source for source in sources.values() if source.origin is not None and source.origin.licence
    ]
    if not restricted:
        return []
    return [
        Finding(
            code="export.source_licence",
            severity="info",
            message=_("Beteiligte Quellen stehen unter einer Lizenz."),
            values={
                "sources": ", ".join(
                    f"{source.origin.title or source.id}: {source.origin.licence}"
                    for source in restricted
                    if source.origin is not None
                )
            },
        )
    ]


def write_plan(
    plan: ExportPlan, directory: Path, export_format: ExportFormat = "stl"
) -> list[Path]:
    """Schreibt die geplanten Dateien und gibt zurück, was geschrieben wurde."""
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for entry in plan.entries:
        target = directory / entry.filename
        target.write_bytes(
            export_bytes(entry.mesh, export_format, list(entry.slots), entry.name, entry.body)
        )
        written.append(target)
    _log.info("exported %d file(s) to %s", len(written), directory)
    return written


def export_bytes(
    mesh: MeshData,
    export_format: ExportFormat = "stl",
    slots: list[MaterialSlot] | None = None,
    name: str = "",
    body: Mesh | None = None,
) -> bytes:
    """Ein Körper in einem Format.

    3MF wird hier geschrieben statt von trimesh: es ist das eine Format, das
    die Materialgruppen aus §20 trägt, und trimesh schreibt sie nicht. STEP
    wird aus dem exakten Körper geschrieben und gibt es nur, wenn es einen
    gibt (§30).
    """
    if export_format == "step":
        return _step_bytes(body)
    if export_format == "stl":
        return mesh.to_stl()
    if export_format == "3mf":
        return threemf.write(mesh, slots, name)
    data = trimesh.exchange.export.export_mesh(mesh.raw, None, file_type=export_format)
    return data if isinstance(data, bytes) else str(data).encode("utf-8")


def _step_bytes(body: Mesh | None) -> bytes:
    """STEP eines exakten Körpers — und ein klares Nein, wenn es keinen
    gibt (§30).
    """
    from app.core.brep import step as brep_step

    if body is None or not isinstance(body, BRepBody):
        raise ValidationError(
            field="format",
            detail=_(
                "STEP hält Flächen und Kanten fest. Ein Netz hat keine — dafür bleiben STL und 3MF."
            ),
            constraint="needs_brep",
        )
    return brep_step.write(body)  # type: ignore[arg-type]


def describe_plan(plan: ExportPlan) -> str:
    """Eine kurze Zusammenfassung für Statusleiste und Kommandozeile."""
    total = sum(entry.mesh.volume for entry in plan.entries) / 1000.0
    return (
        f"{len(plan.entries)} {tr('Dateien')} · "
        f"{format_length(sum(entry.mesh.bounds.size[2] for entry in plan.entries))} · "
        f"{total:.1f} cm³"
    )
