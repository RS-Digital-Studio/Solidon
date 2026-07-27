"""The ``load`` operation (Bauplan §17.1).

The input stage is an operation, not a hidden preparation step: its parameters
stay visible in the stack and can be changed afterwards. Loading the same file
with a different unit is therefore a parameter change, not a fresh import.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from app.core.errors import InternalError, ValidationError
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import IngestResult, check_limits, detect_unit, normalise
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, OpContext, OpResult, SceneObject
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
    produces=1,
    doc=_("Liest eine Modelldatei, rechnet sie in Millimeter um und bereinigt sie."),
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

    mesh = read_mesh(payload, Path(source.path).suffix)
    check_limits(len(payload), mesh.triangle_count)

    unit = _unit_for(ctx, params, mesh.bounds.diagonal)
    result: IngestResult = normalise(
        mesh,
        unit,
        weld=params.weld,
        remove_degenerate=params.remove_degenerate,
        unify_normals=params.unify_normals,
        place_on_bed=params.place_on_bed,
        progress=ctx.progress,
    )

    name = params.name or Path(source.path).stem
    return OpResult(
        outputs=[SceneObject(id="", name=name, mesh=result.mesh)],
        findings=list(result.findings),
    )


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
