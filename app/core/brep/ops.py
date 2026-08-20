"""B-Rep-Operationen (Bauplan §30, §25, §10).

Angemeldet wie jede andere Operation, damit sie von einer Stelle aus Menü,
Palette, Kommandozeile und Agent erreichen (§10). Anders ist nur eines: ohne
den Kern laufen sie nicht — und sie sagen das mit einem Satz, nicht mit einer
Importspur (§36).

Die Kategorie heißt „Formgebung", nicht nach dem Kern: wer eine Verrundung
sucht, sucht sie neben Fase, Schale und Formschräge — nicht unter einem
Kernel-Namen, den er nie gewählt hat. Nur die Umwandlung wohnt unter „Netz",
weil sie dort endet.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import cast

from app.core.brep import edit, profiles, step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, require
from app.core.errors import InternalError, NeedsSolidError, ValidationError
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, OpContext, OpResult, SceneObject
from app.core.units import DEGREE_UNIT
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
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Solidon vergibt einen."),
    )


@register_op(
    name="create_brep_box",
    title=_("Exakten Quader anlegen"),
    category="primitive",
    params=BrepBoxParams,
    consumes=0,
    produces=1,
    doc=_(
        "Legt einen Quader als B-Rep-Körper an — mit echten Kanten, an die "
        "Fasen und Verrundungen gesetzt werden können."
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
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Solidon vergibt einen."),
    )


@register_op(
    name="create_brep_cylinder",
    title=_("Exakten Zylinder anlegen"),
    category="primitive",
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
        "die Einheitenfrage entfällt."
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
                message=_("Ein exakter Körper mit benannten Flächen und Kanten."),
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
    requires_kind="brep",
    title=_("Verrunden"),
    category="shaping",
    params=FilletParams,
    consumes=1,
    produces=1,
    doc=_(
        "Verrundet Kanten eines B-Rep-Körpers — geometrisch exakt, weil die "
        "Kante eine Kurve ist und keine Folge von Segmenten."
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
    requires_kind="brep",
    title=_("Fase anbringen"),
    category="shaping",
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
class ShellParams(BaseParams):
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.2,
        maximum=50.0,
        doc=_(
            "Wie dick die stehenbleibende Wand wird. Mehr als der halbe "
            "Körper geht nicht — dann bleibt innen nichts zum Aushöhlen."
        ),
    )


@register_op(
    name="shell_exact",
    requires_kind="brep",
    title=_("Exakt aushöhlen"),
    category="shaping",
    params=ShellParams,
    consumes=1,
    produces=1,
    doc=_(
        "Höhlt einen B-Rep-Körper mit exakter Wandstärke aus und lässt die "
        "Oberseite offen — ein Kasten aus einem Quader, in einem Schritt. Für "
        "geschlossenes Aushöhlen mit Entlüftung gibt es die Netz-Operation."
    ),
)
def shell_exact(ctx: OpContext) -> OpResult:
    params = cast(ShellParams, ctx.params)
    source, body = _brep_input(ctx)
    solid = profiles.shell_open_top(body, params.wall)
    return OpResult(outputs=[_replaced(source, solid)])


@op_params
class DraftParams(BaseParams):
    angle: float = param(
        title=_("Winkel"),
        default=2.0,
        unit=DEGREE_UNIT,
        minimum=0.1,
        maximum=30.0,
        doc=_(
            "Um wie viel Grad die senkrechten Flächen angestellt werden. Die "
            "Standfläche behält ihr Maß, nach oben wird der Körper schmaler."
        ),
    )


@register_op(
    name="draft_faces",
    requires_kind="brep",
    title=_("Formschräge anstellen"),
    category="shaping",
    params=DraftParams,
    consumes=1,
    produces=1,
    doc=_(
        "Stellt alle senkrechten Flächen eines B-Rep-Körpers um einen Winkel "
        "an — zum Entformen, oder damit ein Stapelbehälter sich stapeln lässt."
    ),
)
def draft_faces(ctx: OpContext) -> OpResult:
    params = cast(DraftParams, ctx.params)
    source, body = _brep_input(ctx)
    solid = profiles.draft_vertical(body, params.angle)
    return OpResult(outputs=[_replaced(source, solid)])


@op_params
class ThreadParams(BaseParams):
    diameter: float = param(
        title=_("Nenndurchmesser"),
        default=10.0,
        unit="mm",
        minimum=2.0,
        maximum=100.0,
        doc=_("Außendurchmesser über die Gewindespitzen — das Maß, das M10 meint."),
    )
    pitch: float = param(
        title=_("Steigung"),
        default=1.5,
        unit="mm",
        minimum=0.25,
        maximum=8.0,
        doc=_(
            "Höhenzuwachs je Umdrehung. Grob gedruckte Gewinde wollen eine "
            "grobe Steigung — unter einem Millimeter druckt kaum ein Drucker sauber."
        ),
    )
    length: float = param(
        title=_("Länge"),
        default=12.0,
        unit="mm",
        minimum=1.0,
        maximum=500.0,
        doc=_("Gewindelänge von Z = 0 nach oben, mindestens zwei Gänge."),
    )
    name: str = param(
        title=_("Name"),
        default="",
        placement="advanced",
        doc=_("Wie das Objekt im Baum heißt. Leer heißt: Solidon vergibt einen."),
    )


@register_op(
    name="thread_exact",
    title=_("Exakten Gewindebolzen erzeugen"),
    # „primitive" und nicht „shaping": Der Bolzen verbraucht nichts und
    # erzeugt einen Körper — dasselbe wie der exakte Quader und der exakte
    # Zylinder daneben. Unter *Ändern → Formgebung* war er der einzige
    # Eintrag, der auf einer leeren Szene anklickbar blieb, während alle
    # sechs Nachbarn ausgegraut waren: ein Erzeugen im Ändern-Menü.
    category="primitive",
    params=ThreadParams,
    consumes=0,
    produces=1,
    doc=_(
        "Ein Bolzen mit echtem helikalem Außengewinde — als exakter Körper, "
        "den der STEP-Export trägt. Mit Spiel vergrößert und von einem Körper "
        "abgezogen wird daraus das Innengewinde."
    ),
)
def thread_exact(ctx: OpContext) -> OpResult:
    params = cast(ThreadParams, ctx.params)
    require()
    solid = profiles.threaded_rod(params.diameter, params.pitch, params.length)
    return OpResult(outputs=[_object(params.name or str(_("Gewindebolzen")), solid)])


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
    requires_kind="brep",
    title=_("In ein Netz umwandeln"),
    category="mesh",
    params=ToMeshParams,
    consumes=1,
    produces=1,
    doc=_(
        "Wandelt einen B-Rep-Körper in ein Dreiecksnetz um. Der Weg zurück "
        "besteht nicht — die Kanten sind danach fort."
    ),
)
def brep_to_mesh(ctx: OpContext) -> OpResult:
    """§30: die Einbahntür — und ein Schritt im Stapel, damit sie sich
    zurücknehmen lässt.

    Zurückgenommen von einem Undo, nicht von einer Rekonstruktion: die
    Operation bleibt im Verlauf, und sie zu entfernen bringt den exakten
    Körper zurück, weil der Stapel neu gerechnet und nicht geflickt wird.
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
    """Die Eingabe und ihr exakter Körper — oder ein klarer Satz, wenn es ein
    Netz ist (§33.1).
    """
    require()
    source = ctx.inputs[0]
    if not isinstance(source.mesh, Solid):
        raise NeedsSolidError(
            # Ohne Platzhalter: TranslatableText löst nur den Katalog auf und
            # formatiert nicht — ein „{name}" stünde dem Nutzer wörtlich da.
            # Der Name reist wie überall in ``values``.
            detail=_(
                "Der gewählte Körper ist ein Netz. Exakte Körper kommen aus einer "
                "STEP-Datei oder aus den Grundformen, deren Name mit Exakt beginnt."
            ),
            values={"name": source.name},
            object_id=source.id,
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
    "draft_faces",
    "fillet_edges",
    "load_step",
    "shell_exact",
    "thread_exact",
]
