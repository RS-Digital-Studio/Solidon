"""Primitive und OpenSCAD-Körper (Bauplan §25, Kategorie „Boolesch").

Säule A beginnt hier: ohne einen Weg, einen ersten Körper in eine leere Szene
zu setzen, hat „bau mir eine Halterung" nichts, worauf es stehen könnte. Drei
Primitive genügen dafür — alles andere ist eine Boolesche Op daraus und ein
Baustein aus der Bibliothek, und genau diese Reihenfolge verlangt die
Regelsammlung (§39: Bausteine vor Primitiven).

Der OpenSCAD-Körper ist die Rückfallebene (§24.1) und bleibt optional: der
Quelltext wird vor dem Lauf geprüft (§32), und ohne Installation sagt die
Operation das, statt auf halbem Weg zu scheitern.
"""

from __future__ import annotations

from typing import cast

from app.core.backends import openscad
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import apply, translation
from app.core.knowledge.parts.build import face
from app.core.knowledge.parts.shapes import SEGMENTS, box, cylinder
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Feature, OpContext, OpResult, SceneObject
from app.i18n import _

_ANCHORS = ("centre", "corner")


@op_params
class BoxParams(BaseParams):
    width: float = param(
        title=_("Breite"),
        default=40.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in X. Darf ein Ausdruck sein, etwa =breite*2."),
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
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Ausdehnung in Z, also nach oben."),
    )
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="centre",
        choices=_ANCHORS,
        placement="advanced",
        doc=_("Mittig auf dem Ursprung oder mit der Ecke darauf."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Formwerk vergibt einen."),
    )


@register_op(
    name="create_box",
    title=_("Quader anlegen"),
    category="boolean",
    params=BoxParams,
    consumes=0,
    produces=1,
    doc=_("Legt einen Quader an. Erst in der Bausteinbibliothek suchen (§39)."),
)
def create_box(ctx: OpContext) -> OpResult:
    params = cast(BoxParams, ctx.params)
    mesh = box(params.width, params.depth, params.height)
    if params.anchor == "corner":
        mesh = apply(mesh, translation((params.width / 2.0, params.depth / 2.0, 0.0)))
    return OpResult(outputs=[_object(params.name or "Quader", mesh, params.height)])


@op_params
class CylinderParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Außendurchmesser. Der Zylinder steht auf Z = 0."),
    )
    height: float = param(
        title=_("Höhe"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Höhe nach oben, von der Standfläche aus."),
    )
    segments: int = param(
        title=_("Segmente"),
        default=SEGMENTS,
        minimum=8,
        maximum=256,
        placement="advanced",
        doc=_("Mehr Segmente heißt runder und langsamer."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Formwerk vergibt einen."),
    )


@register_op(
    name="create_cylinder",
    title=_("Zylinder anlegen"),
    category="boolean",
    params=CylinderParams,
    consumes=0,
    produces=1,
    doc=_("Legt einen Zylinder an, stehend auf Z = 0."),
)
def create_cylinder(ctx: OpContext) -> OpResult:
    params = cast(CylinderParams, ctx.params)
    mesh = cylinder(params.diameter, params.height, segments=params.segments)
    return OpResult(outputs=[_object(params.name or "Zylinder", mesh, params.height)])


@op_params
class SphereParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Außendurchmesser. Die Kugel sitzt auf Z = 0 auf."),
    )
    segments: int = param(
        title=_("Segmente"),
        default=32,
        minimum=8,
        maximum=128,
        placement="advanced",
        doc=_("Mehr Segmente heißt runder und langsamer."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Formwerk vergibt einen."),
    )


@register_op(
    name="create_sphere",
    title=_("Kugel anlegen"),
    category="boolean",
    params=SphereParams,
    consumes=0,
    produces=1,
    doc=_("Legt eine Kugel an, aufsitzend auf Z = 0."),
)
def create_sphere(ctx: OpContext) -> OpResult:
    import trimesh

    params = cast(SphereParams, ctx.params)
    body = trimesh.creation.icosphere(
        subdivisions=max(1, params.segments // 12), radius=params.diameter / 2.0
    )
    body.apply_translation([0.0, 0.0, params.diameter / 2.0])
    mesh = MeshData.of(body)
    return OpResult(outputs=[_object(params.name or "Kugel", mesh, params.diameter)])


@op_params
class ScadParams(BaseParams):
    source: str = param(
        title=_("Quelltext"),
        default="",
        doc=_("OpenSCAD-Quelltext. Wird vor dem Lauf geprüft (§32)."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Formwerk vergibt einen."),
    )


@register_op(
    name="create_from_scad",
    title=_("OpenSCAD-Teil anheften"),
    category="boolean",
    params=ScadParams,
    consumes=0,
    produces=1,
    doc=_(
        "Baut einen Körper aus OpenSCAD-Quelltext. Rückfallebene für Formen, für die "
        "es keinen Baustein gibt — braucht eine Installation und wird vorher geprüft."
    ),
)
def create_from_scad(ctx: OpContext) -> OpResult:
    """§24.1: die Rückfallebene. Die Prüfung aus §32 läuft, bevor irgendetwas
    ausgeführt wird.
    """
    params = cast(ScadParams, ctx.params)
    result = openscad.render(params.source)
    mesh = read_mesh(result.stl, ".stl")
    entry = _object(params.name or "OpenSCAD", mesh, float(mesh.bounds.size[2]))
    return OpResult(outputs=[entry], findings=result.findings)


def _object(name: str, mesh: MeshData, height: float) -> SceneObject:
    """Ein frischer Körper mit dem einen Merkmal, das er ehrlich versprechen
    kann: seiner Oberseite.
    """
    size = mesh.bounds.size
    features: dict[str, Feature] = dict(
        [
            face(
                "face_top",
                float(size[0] * size[1]),
                (0.0, 0.0, float(mesh.bounds.maximum[2])),
                (0.0, 0.0, 1.0),
            )
        ]
    )
    return SceneObject(id="", name=name, mesh=mesh, features=features)
