"""Geometrie-Operationen (Bauplan §25, Kategorie „Transformation").

Das sind die Operationen, die der Gizmo erzeugt (§18.11): ein Ziehen im
Viewport endet als eine von ihnen, mit den Zahlen, bei denen das Ziehen
angekommen ist. Genau das macht ein Ziehen rücknehmbar wie alles andere.
"""

from __future__ import annotations

import dataclasses
from typing import Any, cast

from app.core.errors import Action, AppError, GeometryError
from app.core.geom.align import align_matrix
from app.core.geom.boolean import BooleanKind, boolean
from app.core.geom.mesh import as_mesh_data
from app.core.geom.repair import repair
from app.core.geom.transform import (
    AXIS_VECTORS,
    Anchor,
    Axis,
    anchor_point,
    apply,
    place_on_bed,
    rotation,
    scaling,
    translation,
)
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, FeatureRef, Finding, OpContext, OpResult, Transform
from app.core.units import EPS_GEOM
from app.i18n import _

_AXES = tuple(AXIS_VECTORS)
_ANCHORS = ("centre", "origin", "bed")


def as_transform(matrix: Any) -> Transform:
    """Eine Matrix als nackte Zahlen, damit sie Cache und Datei
    übersteht (§21.2).
    """
    rows = [tuple(float(value) for value in row) for row in matrix]
    return cast(Transform, tuple(rows))


@op_params
class TranslateParams(BaseParams):
    dx: float = param(
        title=_("Verschiebung X"),
        default=0.0,
        unit="mm",
        doc=_("Um wie viel verschoben wird, nicht wohin. Positiv geht nach rechts."),
    )
    dy: float = param(
        title=_("Verschiebung Y"),
        default=0.0,
        unit="mm",
        doc=_("Positiv geht nach hinten."),
    )
    dz: float = param(
        title=_("Verschiebung Z"),
        default=0.0,
        unit="mm",
        doc=_("Positiv geht nach oben. Zum Aufsetzen gibt es *Auf das Bett setzen*."),
    )


@register_op(
    name="translate_object",
    title=_("Verschieben"),
    category="transform",
    params=TranslateParams,
    consumes=1,
    produces=1,
    shortcut="Ctrl+T",
    doc=_("Verschiebt ein Objekt um die angegebenen Millimeter."),
)
def translate_object(ctx: OpContext) -> OpResult:
    params = cast(TranslateParams, ctx.params)
    source = ctx.inputs[0]
    matrix = translation((params.dx, params.dy, params.dz))
    moved = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=moved)], transform=as_transform(matrix)
    )


@op_params
class RotateParams(BaseParams):
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=_AXES,
        doc=_("Um welche Achse gedreht wird. Z dreht auf dem Bett, X und Y kippen."),
    )
    angle: float = param(
        title=_("Winkel"),
        default=90.0,
        unit="grad",
        minimum=-360.0,
        maximum=360.0,
        doc=_("Drehwinkel gegen den Uhrzeigersinn, von der Achsspitze aus gesehen."),
    )
    about: str = param(
        title=_("Drehpunkt"),
        default="centre",
        choices=_ANCHORS,
        placement="advanced",
        doc=_("Schwerpunkt des Objekts, Weltnullpunkt oder Aufstandsfläche."),
    )


@register_op(
    name="rotate_object",
    title=_("Drehen"),
    category="transform",
    params=RotateParams,
    consumes=1,
    produces=1,
    shortcut="Ctrl+R",
    doc=_("Dreht ein Objekt um eine Achse."),
)
def rotate_object(ctx: OpContext) -> OpResult:
    params = cast(RotateParams, ctx.params)
    source = ctx.inputs[0]
    pivot = anchor_point(as_mesh_data(source.mesh), cast(Anchor, params.about))
    matrix = rotation(cast(Axis, params.axis), params.angle, pivot)
    turned = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=turned)], transform=as_transform(matrix)
    )


@op_params
class ScaleParams(BaseParams):
    # Der Faktor reicht über drei Zehnerpotenzen in beide Richtungen. Hundert
    # war zu wenig: was ein Bildmodell liefert, ist auf einen Einheitswürfel
    # normiert und misst ein bis zwei Millimeter — ein Schrank daraus braucht
    # den Faktor 141, und die Op lehnte ab. Tausend deckt den Weg vom
    # Einheitswürfel bis an jeden Bauraum ab; darüber ist keine Skalierung
    # mehr gemeint, sondern ein Tippfehler.
    factor: float = param(
        title=_("Faktor"),
        default=1.0,
        minimum=0.001,
        maximum=1000.0,
        doc=_(
            "Gleichmäßige Skalierung. Achsweise Werte stehen hinten. "
            "Wenn das Zielmaß bekannt ist, ist „Auf Maß bringen“ der kürzere Weg."
        ),
    )
    fx: float = param(
        title=_("Faktor X"),
        default=0.0,
        minimum=0.0,
        placement="advanced",
        doc=_("Nur diese Achse. Null heißt: der gleichmäßige Faktor oben gilt."),
    )
    fy: float = param(
        title=_("Faktor Y"),
        default=0.0,
        minimum=0.0,
        placement="advanced",
        doc=_("Null heißt: der gleichmäßige Faktor oben gilt."),
    )
    fz: float = param(
        title=_("Faktor Z"),
        default=0.0,
        minimum=0.0,
        placement="advanced",
        doc=_(
            "Null heißt: der gleichmäßige Faktor oben gilt. Achsweise Skalierung "
            "verzerrt Bohrungen — sie werden oval."
        ),
    )
    about: str = param(
        title=_("Bezugspunkt"),
        default="centre",
        choices=_ANCHORS,
        placement="advanced",
        doc=_("Der Punkt, der stehen bleibt: Schwerpunkt, Nullpunkt oder Aufstandsfläche."),
    )


@register_op(
    name="scale_object",
    title=_("Skalieren"),
    category="transform",
    params=ScaleParams,
    consumes=1,
    produces=1,
    doc=_("Skaliert ein Objekt gleichmäßig oder achsweise."),
)
def scale_object(ctx: OpContext) -> OpResult:
    params = cast(ScaleParams, ctx.params)
    source = ctx.inputs[0]
    # Ein Achswert von null heißt: „für diese Achse den gleichmäßigen Faktor".
    factors = (
        params.fx or params.factor,
        params.fy or params.factor,
        params.fz or params.factor,
    )
    pivot = anchor_point(as_mesh_data(source.mesh), cast(Anchor, params.about))
    matrix = scaling(factors, pivot)
    scaled = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=scaled)], transform=as_transform(matrix)
    )


@op_params
class FitToSizeParams(BaseParams):
    largest: float = param(
        title=_("Größte Kante"),
        default=100.0,
        minimum=0.1,
        maximum=1000.0,
        unit="mm",
        doc=_("Auf dieses Maß wächst die längste Kante; die anderen folgen im Verhältnis."),
    )
    about: str = param(
        title=_("Bezug"),
        default="centre",
        choices=_ANCHORS,
        placement="advanced",
        doc=_("Welcher Punkt beim Skalieren stehen bleibt."),
    )


@register_op(
    name="fit_to_size",
    title=_("Auf Maß bringen"),
    category="transform",
    params=FitToSizeParams,
    consumes=1,
    produces=1,
    doc=_(
        "Skaliert ein Objekt so, dass seine längste Kante das angegebene Maß hat. "
        "Für alles, dessen Größe man kennt, aber dessen Faktor man erst ausrechnen müsste."
    ),
)
def fit_to_size(ctx: OpContext) -> OpResult:
    """Die Zielgröße ist bekannt, der Faktor nicht — also rechnet ihn die Op.

    Der Fall, für den sie entstand: ein Bildmodell normiert seine Ausgabe auf
    einen Einheitswürfel. Was ankommt, misst ein bis zwei Millimeter, und der
    Weg zurück führt über einen Faktor von hundertvierzig — eine Zahl, die
    niemand im Kopf hat und die ``scale_object`` obendrein ablehnte.
    """
    params = cast(FitToSizeParams, ctx.params)
    source = ctx.inputs[0]
    body = as_mesh_data(source.mesh)
    current = max(body.bounds.size)
    if current <= EPS_GEOM:
        raise GeometryError(
            _("Dieser Körper hat keine Ausdehnung."),
            detail=_("Ein Maß lässt sich nur auf etwas beziehen, das eine Größe hat."),
            suggestions=(Action(id="check_input", label=_("Eingangsobjekt prüfen.")),),
        )
    factor = params.largest / current
    pivot = anchor_point(body, cast(Anchor, params.about))
    matrix = scaling((factor, factor, factor), pivot)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=apply(body, matrix))],
        transform=as_transform(matrix),
        findings=[
            Finding(
                code="transform.fitted",
                severity="info",
                message=_("Auf Maß gebracht."),
                values={"from_mm": round(current, 3), "to_mm": params.largest},
                source="internal",
            )
        ],
    )


@op_params
class MirrorParams(BaseParams):
    axis: str = param(
        title=_("Achse"),
        default="x",
        choices=_AXES,
        doc=_("Die Achse, an der gespiegelt wird — die andere Hand desselben Teils."),
    )
    about: str = param(
        title=_("Bezugspunkt"),
        default="centre",
        choices=_ANCHORS,
        placement="advanced",
        doc=_("Wo die Spiegelebene liegt: Schwerpunkt, Nullpunkt oder Aufstandsfläche."),
    )


@register_op(
    name="mirror_object",
    title=_("Spiegeln"),
    category="transform",
    params=MirrorParams,
    consumes=1,
    produces=1,
    doc=_(
        "Spiegelt ein Objekt an einer Achse. Für das Gegenstück eines Teils — "
        "linke und rechte Halterung aus derselben Konstruktion."
    ),
)
def mirror_object(ctx: OpContext) -> OpResult:
    """§25: eine Spiegelung ist eine Skalierung mit minus eins um eine Achse.

    Eine Spiegelung stülpt jedes Dreieck um, und ein Körper mit umgedrehten
    Normalen ist einer, den jede spätere Operation falsch versteht. Der Kern
    dreht den Umlaufsinn bei einer Matrix mit negativer Determinante zurück —
    der Test misst danach das Volumen, denn „das macht schon irgendwer" ist
    kein Versprechen.

    Die Merkmale fallen weg: eine Bohrung namens ``hole_1`` am rechten Teil
    ist nicht dieselbe Bohrung am linken, und die Neuerkennung benennt sie neu
    (§21.2).
    """
    params = cast(MirrorParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    factors = [1.0, 1.0, 1.0]
    factors["xyz".index(params.axis)] = -1.0
    pivot = anchor_point(mesh, cast(Anchor, params.about))
    matrix = scaling((factors[0], factors[1], factors[2]), pivot)

    return OpResult(
        outputs=[dataclasses.replace(source, mesh=apply(mesh, matrix), features={})],
        transform=as_transform(matrix),
    )


@op_params
class RepairParams(BaseParams):
    fill_holes: bool = param(
        title=_("Offene Stellen schließen"),
        default=True,
        doc=_("Schließt kleine Löcher. Fehlende Wände kann das nicht ersetzen."),
    )
    weld: bool = param(
        title=_("Punkte verschweißen"),
        default=True,
        placement="advanced",
        doc=_(
            "Führt Punkte zusammen, die praktisch aufeinanderliegen. Der häufigste "
            "Grund dafür, dass ein Netz aus mehreren Teilen zu bestehen scheint."
        ),
    )
    degenerate: bool = param(
        title=_("Entartete Dreiecke entfernen"),
        default=True,
        placement="advanced",
        doc=_("Dreiecke ohne Fläche. Sie stören jede spätere Rechnung und tragen nichts."),
    )
    normals: bool = param(
        title=_("Normalen vereinheitlichen"),
        default=True,
        placement="advanced",
        doc=_("Richtet aus, wo außen ist. Ohne das erscheinen Flächen dunkel oder verschwinden."),
    )
    small_components: bool = param(
        title=_("Kleinstteile löschen"),
        default=False,
        placement="advanced",
        doc=_("Standardmäßig aus: gelöscht wird nur, was ausdrücklich gelöscht werden soll."),
    )
    self_intersections: bool = param(
        title=_("Selbstdurchdringungen auflösen"),
        default=False,
        placement="advanced",
        doc=_(
            "Rechnet Flächen neu, die sich gegenseitig durchdringen. Hilft bei "
            "erzeugten Netzen und kostet Genauigkeit — deshalb aus, bis es gebraucht wird."
        ),
    )


@register_op(
    name="repair",
    title=_("Reparieren"),
    category="repair",
    params=RepairParams,
    consumes=1,
    produces=1,
    doc=_("Schließt Löcher, entfernt entartete Dreiecke und richtet die Flächen aus."),
)
def repair_object(ctx: OpContext) -> OpResult:
    params = cast(RepairParams, ctx.params)
    source = ctx.inputs[0]
    result = repair(
        as_mesh_data(source.mesh),
        weld=params.weld,
        degenerate=params.degenerate,
        normals=params.normals,
        holes=params.fill_holes,
        small_components=params.small_components,
        self_intersections=params.self_intersections,
    )
    findings = list(result.findings)
    if not result.changed:
        # Ein gesundes Netz sah bisher aus wie eine Reparatur, die nicht
        # gelaufen ist: keine Meldung, kein Unterschied, ein Schritt im
        # Verlauf. Das Ergebnis „nichts zu tun" ist ein gutes und gehört
        # gesagt (§2.7).
        findings.append(
            Finding(
                code="repair.nothing_to_do",
                severity="info",
                message=_("An diesem Netz war nichts zu reparieren."),
                object_id=source.id,
            )
        )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        findings=findings,
    )


@op_params
class BooleanParams(BaseParams):
    pass


def _boolean_op(ctx: OpContext, kind: BooleanKind, seed: int | None) -> OpResult:
    """Zwei Körper hinein, einer heraus — mit der Rückfallkette
    dahinter (§17.2).
    """
    first, second = (as_mesh_data(entry.mesh) for entry in ctx.inputs[:2])
    outcome = boolean(
        kind, [first, second], quality=ctx.quality, seed=seed, cancelled=ctx.cancelled
    )
    return OpResult(
        outputs=[dataclasses.replace(ctx.inputs[0], mesh=outcome.mesh)],
        solver=outcome.solver,
        findings=outcome.findings,
    )


@register_op(
    name="union_objects",
    title=_("Vereinigen"),
    category="boolean",
    params=BooleanParams,
    consumes=2,
    produces=1,
    deterministic=False,
    doc=_("Verschmilzt zwei Objekte zu einem."),
)
def union_objects(ctx: OpContext) -> OpResult:
    return _boolean_op(ctx, "union", ctx.seed)


@register_op(
    name="subtract_objects",
    title=_("Abziehen"),
    category="boolean",
    params=BooleanParams,
    consumes=2,
    produces=1,
    deterministic=False,
    doc=_("Zieht das zweite Objekt vom ersten ab."),
)
def subtract_objects(ctx: OpContext) -> OpResult:
    return _boolean_op(ctx, "difference", ctx.seed)


@register_op(
    name="intersect_objects",
    title=_("Schnittmenge"),
    category="boolean",
    params=BooleanParams,
    consumes=2,
    produces=1,
    deterministic=False,
    doc=_("Behält nur, was beide Objekte gemeinsam haben."),
)
def intersect_objects(ctx: OpContext) -> OpResult:
    return _boolean_op(ctx, "intersection", ctx.seed)


@op_params
class PlaceOnBedParams(BaseParams):
    pass


@register_op(
    name="place_on_bed",
    title=_("Auf das Bett setzen"),
    category="transform",
    params=PlaceOnBedParams,
    consumes=1,
    produces=1,
    doc=_("Setzt das Objekt mit seiner Unterseite auf Z = 0."),
)
def place_object_on_bed(ctx: OpContext) -> OpResult:
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)
    matrix = translation((0.0, 0.0, -mesh.bounds.minimum[2]))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=place_on_bed(mesh))],
        transform=as_transform(matrix),
    )


@op_params
class AlignParams(BaseParams):
    feature: str = param(
        title=_("Merkmal"),
        default="",
        doc=_("Bohrung oder Fläche am bewegten Objekt, zum Beispiel hole_1."),
    )
    target: str = param(
        title=_("Ziel"),
        default="",
        doc=_("Merkmal, auf das ausgerichtet wird, als obj_2:hole_1."),
    )
    flip: bool = param(
        title=_("Umgekehrt herum"),
        default=False,
        placement="advanced",
        doc=_("Dreht das Ergebnis um 180 Grad, wenn die andere Seite gemeint war."),
    )


@register_op(
    name="align_to_feature",
    title=_("An Merkmal ausrichten"),
    category="transform",
    params=AlignParams,
    consumes=1,
    produces=1,
    applies_to=["hole", "face"],
    doc=_("Bringt eine Bohrungsachse oder eine Fläche mit einer zweiten zur Deckung."),
)
def align_to_feature(ctx: OpContext) -> OpResult:
    """Einrasten als Operation (§18.11): die Datei sagt, was womit in Flucht
    gebracht wurde.
    """
    params = cast(AlignParams, ctx.params)
    source = ctx.inputs[0]
    reference = FeatureRef.parse(params.target) if ":" in params.target else None
    if reference is None:
        raise AppError(
            _("Das Ziel muss ein Merkmal eines Objekts benennen."),
            detail=f"malformed target {params.target!r}",
            values={"target": params.target},
            suggestions=(
                Action(id="write_target", label=_("Schreiben Sie das Ziel als obj_2:hole_1.")),
            ),
        )

    moving = source.features.get(params.feature)
    other = ctx.scene.objects.get(reference.object_id)
    wanted = other.features.get(reference.feature_id) if other is not None else None
    if moving is None or wanted is None:
        missing = params.feature if moving is None else params.target
        raise AppError(
            _("Dieses Merkmal gibt es nicht."),
            detail=f"unknown feature {missing!r}",
            values={"feature": missing},
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie das Merkmal im Objektbaum aus.")),
            ),
        )

    matrix = align_matrix(moving, wanted, flip=params.flip)
    aligned = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=aligned)], transform=as_transform(matrix)
    )
