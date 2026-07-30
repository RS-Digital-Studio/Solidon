"""Export and the check that runs before it (Bauplan §29, §16.3).

The check is a report, not a barrier: watertightness, build volume, wall
thickness and the licence of the sources are stated, and whoever wants to export
anyway can — they just know what they are doing.

The naming scheme matters more than it looks. Someone printing three parts wants
to see which is which on the plate, so ``projekt_halterung_1von3.stl`` is the
default, and object names are made file-system-safe without becoming unreadable.
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

#: What each format is written as. STL stays binary — ASCII would be five times
#: the size for the same triangles.
FORMAT_SUFFIX: dict[ExportFormat, str] = {
    "stl": ".stl",
    "3mf": ".3mf",
    "obj": ".obj",
    "ply": ".ply",
    # §30: only a B-Rep object has anything to put in a STEP file. A mesh
    # exported as STEP would be a STEP file full of triangles — legal, and a
    # lie about what it contains.
    "step": ".step",
}

#: Default naming scheme (§29). ``{index}`` and ``{count}`` only appear when
#: there is more than one part.
DEFAULT_SCHEME = "{project}_{object}_{index}von{count}"
SINGLE_SCHEME = "{project}_{object}"

#: With more than one build plate the plate goes into the name (§25). Whoever
#: takes the files to the printer needs to know which ones belong together.
PLATE_SCHEME = "{project}_platte{plate}_{object}_{index}von{count}"

_UNSAFE = re.compile(r"[^\w\-. ]+", re.UNICODE)


def safe_name(text: str, fallback: str = "teil") -> str:
    """File-system-safe without becoming unrecognisable.

    German umlauts are transliterated rather than dropped: ``Gehäuse`` becomes
    ``Gehaeuse``, not ``Gehuse``. That is a deliberate convention for German file
    names, and it used to be followed by forcing the whole name through ASCII —
    which is where "unrecognisable" started rather than stopped: a downloaded
    ``埃菲尔铁塔18cm`` came out as ``18cm``, and a ``Соединитель`` as ``teil``.
    A file name is not the place to decide which alphabets exist.

    What is actually unsafe is a short list — path separators, colons, the
    characters Windows reserves — and :data:`_UNSAFE` already keeps to it: ``\\w``
    under ``re.UNICODE`` covers every script. So the name survives, and ``Boîtier``
    keeps its accent as well.
    """
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
    for character, replacement in replacements.items():
        text = text.replace(character, replacement)
    text = unicodedata.normalize("NFC", text)
    text = _UNSAFE.sub("", text).strip().replace(" ", "_")
    return text or fallback


@dataclass(frozen=True, slots=True)
class ExportEntry:
    """One file about to be written."""

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
    """What would be written, and what the check found first."""

    entries: tuple[ExportEntry, ...] = ()
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def blocked(self) -> bool:
        """Never true — the check reports, it does not block (§29)."""
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
    """Work out the file names and run the pre-export check."""
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
    """A report before writing, not a barrier (§29)."""
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
    """§16.3: one factual note when a source carries a restriction. No lecture."""
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
    """Write the planned files and return what was written."""
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
    """One body in one format.

    3MF is written here rather than by trimesh: it is the one format that
    carries the material groups of §20, and trimesh does not write them. STEP
    is written from the exact body, and only exists when there is one (§30).
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
    """STEP of an exact body — and a clear no when there is none (§30)."""
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
    """A short summary for the status bar and the command line."""
    total = sum(entry.mesh.volume for entry in plan.entries) / 1000.0
    return (
        f"{len(plan.entries)} {tr('Dateien')} · "
        f"{format_length(sum(entry.mesh.bounds.size[2] for entry in plan.entries))} · "
        f"{total:.1f} cm³"
    )
