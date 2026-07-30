"""B-Rep operations (Bauplan §30, §25, §10).

Declared like every other operation, so they reach the menu, the palette, the
command line and the agent from one place (§10). What is different is that they
refuse to run without the kernel — with one sentence, not with an import trace
(§36).

The category is "Netz" for the conversion and "Boolesch" for the shaping, on
purpose: somebody looking for a fillet looks where the other shaping operations
are, not under a kernel name they never chose.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import cast

from app.core.brep import edit, step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, require
from app.core.errors import InternalError, ValidationError
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, OpContext, OpResult, SceneObject
from app.i18n import _

_CHOICES = edit.EDGE_CHOICES

#: Dieselbe Auswahl bei Verrundung und Fase — deshalb steht der Satz einmal hier.
_CHOICE_DOC = _("Welche Kanten gemeint sind — senkrechte, waagerechte, oben, unten oder alle.")


@op_params
class BrepBoxParams(BaseParams):
    width: float = param(
        title=_("Breite"),
        default=40.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in X."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=30.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in Y."),
    )
    height: float = param(
        title=_("Höhe"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in Z, also nach oben."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Formwerk vergibt einen."),
    )


@register_op(
    name="create_brep_box",
    title=_("Exakten Quader anlegen"),
    category="boolean",
    params=BrepBoxParams,
    consumes=0,
    produces=1,
    doc=_(
        "Legt einen Quader als B-Rep-Körper an — mit echten Kanten, an die "
        "Fasen und Verrundungen gesetzt werden können (§30)."
    ),
)
def create_brep_box(ctx: OpContext) -> OpResult:
    params = cast(BrepBoxParams, ctx.params)
    require()
    solid = edit.box(params.width, params.depth, params.height)
    return OpResult(outputs=[_object(params.name or str(_("Quader")), solid)])


@op_params
class BrepCylinderParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Außendurchmesser. Als exakter Körper ist er wirklich rund, nicht vieleckig."),
    )
    height: float = param(
        title=_("Höhe"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Höhe nach oben, von der Standfläche aus."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Formwerk vergibt einen."),
    )


@register_op(
    name="create_brep_cylinder",
    title=_("Exakten Zylinder anlegen"),
    category="boolean",
    params=BrepCylinderParams,
    consumes=0,
    produces=1,
    doc=_("Legt einen Zylinder als B-Rep-Körper an, stehend auf Z = 0."),
)
def create_brep_cylinder(ctx: OpContext) -> OpResult:
    params = cast(BrepCylinderParams, ctx.params)
    require()
    solid = edit.cylinder(params.diameter, params.height)
    return OpResult(outputs=[_object(params.name or str(_("Zylinder")), solid)])


@op_params
class LoadStepParams(BaseParams):
    source: str = param(
        title=_("Quelle"),
        kind="source",
        doc=_("Die eingebettete STEP-Datei im Projekt."),
    )
    name: str = param(title=_("Name"), default="", doc=_("Leer übernimmt den Dateinamen."))


@register_op(
    name="load_step",
    title=_("STEP laden"),
    category="import",
    params=LoadStepParams,
    consumes=0,
    produces=1,
    doc=_(
        "Liest eine STEP-Datei als B-Rep-Körper. STEP trägt seine Einheit selbst — "
        "die Einheitenfrage entfällt (§11.1)."
    ),
)
def load_step(ctx: OpContext) -> OpResult:
    params = cast(LoadStepParams, ctx.params)
    require()
    if ctx.sources is None:
        raise InternalError(
            detail="load_step was called without access to the project sources",
            values={"source": params.source},
        )

    source = ctx.sources.describe(params.source)
    if not step.is_step(Path(source.path).suffix):
        raise ValidationError(
            field="source",
            detail=_("Diese Datei ist keine STEP-Datei."),
            value=source.path,
            constraint="not_step",
        )

    solid = step.read(ctx.sources.read(params.source))
    name = params.name or Path(source.path).stem
    entry = _object(name, solid)
    return OpResult(
        outputs=[entry],
        findings=[
            Finding(
                code="brep.loaded",
                severity="info",
                message=_("Ein exakter Körper mit benannten Flächen und Kanten (§30)."),
                values={"faces": solid.face_count, "edges": solid.edge_count},
            )
        ],
    )


@op_params
class FilletParams(BaseParams):
    radius: float = param(
        title=_("Radius"),
        default=2.0,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_(
            "Radius der Verrundung. Größer als das dünnste angrenzende Material "
            "geht nicht — dann hat der Kern keinen Platz mehr."
        ),
    )
    edges: str = param(
        title=_("Kanten"),
        default="vertical",
        choices=_CHOICES,
        doc=_("Welche Kanten gemeint sind — senkrechte, waagerechte, oben, unten oder alle."),
    )


@register_op(
    name="fillet_edges",
    title=_("Verrunden"),
    category="boolean",
    params=FilletParams,
    consumes=1,
    produces=1,
    doc=_(
        "Verrundet Kanten eines B-Rep-Körpers — geometrisch exakt, weil die "
        "Kante eine Kurve ist und keine Folge von Segmenten (§30)."
    ),
)
def fillet_edges(ctx: OpContext) -> OpResult:
    params = cast(FilletParams, ctx.params)
    source, body = _brep_input(ctx)
    solid = edit.fillet(body, params.radius, cast(edit.EdgeChoice, params.edges))
    return OpResult(outputs=[_replaced(source, solid)])


@op_params
class ChamferParams(BaseParams):
    distance: float = param(
        title=_("Breite"),
        default=1.0,
        unit="mm",
        minimum=0.01,
        maximum=100.0,
        doc=_("Wie weit die Fase die Kante zurücknimmt, auf jeder der beiden Flächen."),
    )
    edges: str = param(
        title=_("Kanten"),
        default="vertical",
        choices=_CHOICES,
        doc=_CHOICE_DOC,
    )


@register_op(
    name="chamfer_edges",
    title=_("Fase anbringen"),
    category="boolean",
    params=ChamferParams,
    consumes=1,
    produces=1,
    doc=_("Bricht Kanten eines B-Rep-Körpers unter 45 Grad."),
)
def chamfer_edges(ctx: OpContext) -> OpResult:
    params = cast(ChamferParams, ctx.params)
    source, body = _brep_input(ctx)
    solid = edit.chamfer(body, params.distance, cast(edit.EdgeChoice, params.edges))
    return OpResult(outputs=[_replaced(source, solid)])


@op_params
class ToMeshParams(BaseParams):
    deflection: float = param(
        title=_("Feinheit"),
        default=0.05,
        unit="mm",
        minimum=0.001,
        maximum=1.0,
        placement="advanced",
        doc=_("Wie weit die Dreiecke von der echten Fläche abweichen dürfen."),
    )


@register_op(
    name="brep_to_mesh",
    title=_("In ein Netz umwandeln"),
    category="mesh",
    params=ToMeshParams,
    consumes=1,
    produces=1,
    doc=_(
        "Wandelt einen B-Rep-Körper in ein Dreiecksnetz um. Der Weg zurück "
        "besteht nicht — die Kanten sind danach fort (§30)."
    ),
)
def brep_to_mesh(ctx: OpContext) -> OpResult:
    """§30: the one-way door, and it is a step in the stack so it can be undone.

    Taken back by an undo, not by a reconstruction: the operation stays in the
    history, and removing it brings the exact body back because the stack is
    recomputed, not patched.
    """
    params = cast(ToMeshParams, ctx.params)
    source, body = _brep_input(ctx)
    mesh = Solid(shape=body.shape, deflection=params.deflection).to_mesh()
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh, kind="mesh", features={})],
        findings=[
            Finding(
                code="brep.converted",
                severity="info",
                message=_("Aus dem exakten Körper wurde ein Netz. Der Rückweg besteht nicht."),
                object_id=source.id,
                values={"triangles": mesh.triangle_count},
            )
        ],
    )


def _brep_input(ctx: OpContext) -> tuple[SceneObject, Solid]:
    """The input and its exact body, or a clear sentence when it is a mesh (§33.1)."""
    require()
    source = ctx.inputs[0]
    if not isinstance(source.mesh, Solid):
        raise ValidationError(
            field="in",
            detail=_("Diese Operation braucht einen B-Rep-Körper; hier liegt ein Netz."),
            value=source.id,
            constraint="needs_brep",
        )
    return source, source.mesh


def _object(name: str, solid: Solid) -> SceneObject:
    return SceneObject(id="", name=name, mesh=solid, kind="brep", features=features_of(solid))


def _replaced(source: SceneObject, solid: Solid) -> SceneObject:
    return dataclasses.replace(source, mesh=solid, kind="brep", features=features_of(solid))


__all__ = [
    "brep_to_mesh",
    "chamfer_edges",
    "create_brep_box",
    "create_brep_cylinder",
    "fillet_edges",
    "load_step",
]
