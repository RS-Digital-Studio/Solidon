"""The ``load`` operation (Bauplan §17.1).

The input stage is an operation, not a hidden preparation step: its parameters
stay visible in the stack and can be changed afterwards. Loading the same file
with a different unit is therefore a parameter change, not a fresh import.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from app.core.errors import InternalError, ValidationError
from app.core.export import threemf
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest import outline
from app.core.ingest.loader import IngestResult, check_limits, detect_unit, normalise
from app.core.registry import VARIABLE, op_params, param, register_op
from app.core.types import BaseParams, Finding, MaterialSlot, OpContext, OpResult, SceneObject
from app.core.units import LengthUnit
from app.i18n import _

_UNIT_CHOICES = ("auto", "mm", "cm", "in", "m")


@op_params
class LoadParams(BaseParams):
    source: str = param(
        title=_("Quelle"),
        kind="source",
        doc=_("Die eingebettete oder verknüpfte Datei im Projekt."),
    )
    unit: str = param(
        title=_("Einheit"),
        default="auto",
        choices=_UNIT_CHOICES,
        doc=_("STL kennt keine Einheit. Automatisch heißt: schätzen, im Zweifel nachfragen."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        doc=_("Leer übernimmt den Dateinamen."),
    )
    place_on_bed: bool = param(
        title=_("Auf das Bett setzen"),
        default=False,
        doc=_("Setzt das Modell mit seiner Unterseite auf Z = 0."),
    )
    weld: bool = param(
        title=_("Punkte verschweißen"),
        default=True,
        placement="advanced",
    )
    remove_degenerate: bool = param(
        title=_("Entartete Dreiecke entfernen"),
        default=True,
        placement="advanced",
    )
    unify_normals: bool = param(
        title=_("Normalen vereinheitlichen"),
        default=True,
        placement="advanced",
    )


@register_op(
    name="load",
    title=_("Modell laden"),
    category="import",
    params=LoadParams,
    consumes=0,
    produces=VARIABLE,
    doc=_(
        "Liest eine Modelldatei, rechnet sie in Millimeter um und bereinigt sie. "
        "Eine 3MF-Baugruppe kommt als mehrere Objekte an, nicht als ein Klumpen."
    ),
)
def load(ctx: OpContext) -> OpResult:
    params = cast(LoadParams, ctx.params)
    if ctx.sources is None:
        raise InternalError(
            detail="the load operation was called without access to the project sources",
            values={"source": params.source},
        )

    source = ctx.sources.describe(params.source)
    payload = ctx.sources.read(params.source)
    check_limits(len(payload), 0)

    suffix = Path(source.path).suffix
    stem = Path(source.path).stem
    parts = threemf.read_objects(payload) if suffix.lower() == ".3mf" else []
    if not parts:
        mesh = read_mesh(payload, suffix)
        mesh, slots = _colour_groups(payload, suffix, mesh)
        parts = [threemf.Part(name=params.name or stem, mesh=mesh, slots=tuple(slots))]
    elif params.name and len(parts) == 1:
        parts = [dataclasses.replace(parts[0], name=params.name)]

    check_limits(len(payload), sum(part.mesh.triangle_count for part in parts))

    # One unit for the whole file. Deciding per body would let two parts of one
    # assembly come out at different scales, and the question §17.1 asks the
    # user is about the file, not about each body in it.
    unit = _unit_for(ctx, params, max(part.mesh.bounds.diagonal for part in parts))

    outputs: list[SceneObject] = []
    findings: list[Finding] = []
    for index, part in enumerate(parts):
        ctx.progress(index / len(parts), str(_("Modell laden")))
        result: IngestResult = normalise(
            part.mesh,
            unit,
            weld=params.weld,
            remove_degenerate=params.remove_degenerate,
            unify_normals=params.unify_normals,
            # An assembly is placed the way the file placed it: dropping every
            # body onto Z = 0 on its own would take a lid off its housing and
            # pile the parts on top of each other.
            place_on_bed=params.place_on_bed and len(parts) == 1,
            progress=ctx.progress,
        )
        outputs.append(
            SceneObject(id="", name=part.name, mesh=result.mesh, material_slots=list(part.slots))
        )
        findings.extend(
            _named(result.findings, part.name) if len(parts) > 1 else list(result.findings)
        )

    if len(parts) > 1:
        findings.append(
            Finding(
                code="load.assembly",
                severity="info",
                message=_("Die Datei enthält mehrere Körper — sie kommen als eigene Objekte an."),
                values={"parts": len(parts), "file": stem},
            )
        )
    return OpResult(outputs=outputs, findings=findings)


def _named(findings: Sequence[Finding], name: str) -> list[Finding]:
    """Say which body of an assembly a finding is about."""
    return [
        dataclasses.replace(entry, values={**entry.values, "object": name}) for entry in findings
    ]


@op_params
class LoadOutlineParams(BaseParams):
    source: str = param(
        title=_("Quelle"),
        kind="source",
        doc=_("Die eingebettete SVG- oder DXF-Datei im Projekt."),
    )
    height: float = param(title=_("Höhe"), default=3.0, unit="mm", minimum=0.1, maximum=500.0)
    width: float = param(
        title=_("Breite"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        doc=_("Auf diese Breite skalieren. Null nimmt die Zahlen der Datei als Millimeter."),
    )
    name: str = param(title=_("Name"), default="", placement="advanced")


@register_op(
    name="load_outline",
    title=_("Zeichnung extrudieren"),
    category="import",
    params=LoadOutlineParams,
    consumes=0,
    produces=1,
    doc=_(
        "Liest eine SVG- oder DXF-Zeichnung und gibt ihr eine Höhe. Innenliegende "
        "Konturen werden zu Löchern."
    ),
)
def load_outline(ctx: OpContext) -> OpResult:
    """§25: two dimensions plus a thickness, without a detour through Blender."""
    params = cast(LoadOutlineParams, ctx.params)
    if ctx.sources is None:
        raise InternalError(
            detail="load_outline was called without access to the project sources",
            values={"source": params.source},
        )

    source = ctx.sources.describe(params.source)
    payload = ctx.sources.read(params.source)
    check_limits(len(payload), 0)

    result = outline.extrude(payload, Path(source.path).suffix, params.height, params.width)
    name = params.name or Path(source.path).stem
    return OpResult(
        outputs=[SceneObject(id="", name=name, mesh=result.mesh)],
        findings=[
            Finding(
                code="ingest.extruded",
                severity="info",
                message=_("Aus der Zeichnung wurde ein Körper."),
                values={
                    "contours": result.contours,
                    "drawn_width": round(result.width, 2),
                    "height_mm": round(params.height, 2),
                },
            )
        ],
    )


def _colour_groups(
    payload: bytes, suffix: str, mesh: MeshData
) -> tuple[MeshData, list[MaterialSlot]]:
    """§20, import side: 3MF carries a slot per triangle, and it is kept.

    Everything else keeps the behaviour it had — STL has no colour, and a
    texture becomes slots when the user asks for it, not on the way in.
    """
    if suffix.lower() != ".3mf":
        return mesh, []
    groups = threemf.read(payload, mesh.triangle_count)
    if groups is None:
        return mesh, []
    return MeshData(raw=mesh.raw, slots=groups.slots), list(groups.materials)


def _unit_for(ctx: OpContext, params: LoadParams, diagonal: float) -> LengthUnit:
    """Take the stored unit, or run the heuristic and ask when it is not sure."""
    if params.unit != "auto":
        return cast(LengthUnit, params.unit)

    guess = detect_unit(diagonal)
    if guess.unit is not None:
        return guess.unit

    choices = [str(unit) for unit in guess.candidates]
    answer = ctx.ask(
        str(_("In welcher Einheit ist diese Datei gespeichert?")),
        choices,
    )
    if answer not in choices:
        raise ValidationError(
            field="unit",
            detail=_("Diese Einheit steht nicht zur Auswahl."),
            value=answer,
            constraint="choices",
            values={"choices": choices},
        )
    return cast(LengthUnit, answer)
