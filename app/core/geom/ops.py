"""Geometrie-Operationen (Bauplan §25, Kategorie „Transformation").

Das sind die Operationen, die der Gizmo erzeugt (§18.11): ein Ziehen im
Viewport endet als eine von ihnen, mit den Zahlen, bei denen das Ziehen
angekommen ist. Genau das macht ein Ziehen rücknehmbar wie alles andere.
"""

from __future__ import annotations

import dataclasses
from typing import Any, cast

from app.core.errors import CANCEL, CORRECT_INPUT, Action, AppError, GeometryError
from app.core.geom.align import align_matrix
from app.core.geom.attributes import used_slots
from app.core.geom.boolean import BooleanKind, boolean, without_effect
from app.core.geom.mesh import MeshData, as_mesh_data
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
from app.core.types import (
    BaseParams,
    FeatureRef,
    Finding,
    MaterialSlot,
    OpContext,
    OpResult,
    Transform,
    Vec3,
)
from app.core.units import DEGREE_UNIT, EPS_GEOM
from app.i18n import _

_AXES = tuple(AXIS_VECTORS)
#: Die Drehpunkte, die eine Transformation kennt.
#:
#: ``point`` ist der einzige, der nicht aus dem Netz kommt, sondern aus den
#: Parametern (``pivot_x``/``pivot_y``/``pivot_z``). Er ist dafür da, dass
#: **mehrere** Körper um denselben Punkt gedreht werden können: Die anderen
#: drei liest ``anchor_point`` aus dem eigenen Netz, jeder Körper drehte also
#: um sich selbst, und eine Gruppe fiele auseinander.
_ANCHORS = ("centre", "origin", "bed")

#: Dieselben drei, dazu der genannte Punkt.
#:
#: **Getrennt und nicht für alle**, weil ``fit_to_size`` und ``mirror_object``
#: ihn nicht auswerten. Stünde er auch in ihrer Auswahlliste, wäre er dort
#: eine Sackgasse (§2.1): ein Eintrag, den man wählen kann und der nichts tut.
#: Wer eine der beiden später erweitert, tauscht die Liste bewusst.
_ANCHORS_WITH_POINT = (*_ANCHORS, "point")


def named_pivot(params: Any) -> Vec3 | None:
    """Der genannte Drehpunkt aus den Parametern — oder ``None``.

    **Der Unterschied zu „nicht gesetzt" ist der Anker und nicht die Null.**
    Ein Nullpunkt ist ein gültiger Drehpunkt; wer ihn an der Zahl erkennen
    wollte, könnte „um den Ursprung" nicht von „nichts angegeben"
    unterscheiden. Deshalb entscheidet ``about``, und die drei Zahlen gelten
    nur, wenn es ``point`` sagt.

    Alte Projektdateien tragen ``about`` als ``centre``, ``origin`` oder
    ``bed`` und kommen hier nie durch — ihr Verhalten ändert sich nicht.
    """
    if getattr(params, "about", None) != "point":
        return None
    return (
        float(getattr(params, "pivot_x", 0.0)),
        float(getattr(params, "pivot_y", 0.0)),
        float(getattr(params, "pivot_z", 0.0)),
    )


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


def _stood_still(matrix: object) -> list[Finding]:
    """Eine Transformation, die den Körper stehen lässt, sagt es.

    **Der Fall ist die Vorgabe des Dialogs, nicht ein Randfall.** *Skalieren*
    öffnet mit Faktor 1,0, *Verschieben* mit 0/0/0 — wer den Dialog aufmacht
    und übernimmt, bekommt einen Schritt im Verlauf und ein Bild, das sich
    nicht bewegt hat. Im Verlauf steht etwas, im Viewport nichts, und der
    Nutzer sucht den Fehler in der Geometrie statt in seiner Eingabe.

    Dieselbe Lücke, die ``boolean.without_effect`` bei den Schnitten schließt
    (siehe dort, „Eine Operation, die nichts bewirkt hat, sagt das"). Gefragt
    wird an der Matrix und nicht am Ergebnisnetz: Sie ist die Absicht, und ein
    Vergleich zweier Netze wäre teurer und ungenauer.
    """
    import numpy as np

    if not np.allclose(np.asarray(matrix, dtype=float), np.eye(4), atol=EPS_GEOM):
        return []
    return [
        Finding(
            code="transform.without_effect",
            severity="info",
            message=_("Der Körper steht danach genau dort, wo er stand."),
        )
    ]


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
        outputs=[dataclasses.replace(source, mesh=moved)],
        transform=as_transform(matrix),
        findings=_stood_still(matrix),
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
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        doc=_("Drehwinkel gegen den Uhrzeigersinn, von der Achsspitze aus gesehen."),
    )
    about: str = param(
        title=_("Drehpunkt"),
        default="centre",
        choices=_ANCHORS_WITH_POINT,
        placement="advanced",
        doc=_(
            "Schwerpunkt des Objekts, Weltnullpunkt, Aufstandsfläche — oder "
            "ein genannter Punkt, um den mehrere Körper gemeinsam drehen."
        ),
    )
    pivot_x: float = param(
        title=_("Drehpunkt X"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Gilt nur, wenn der Drehpunkt „Genannter Punkt“ ist."),
    )
    pivot_y: float = param(
        title=_("Drehpunkt Y"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Gilt nur, wenn der Drehpunkt „Genannter Punkt“ ist."),
    )
    pivot_z: float = param(
        title=_("Drehpunkt Z"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Gilt nur, wenn der Drehpunkt „Genannter Punkt“ ist."),
    )


@register_op(
    name="rotate_object",
    title=_("Drehen"),
    category="transform",
    params=RotateParams,
    consumes=1,
    produces=1,
    shortcut="Ctrl+R",
    doc=_(
        "Dreht ein Objekt um eine Achse. Der Drehpunkt entscheidet, worum: um die "
        "eigene Mitte, um den Nullpunkt des Projekts oder um die Mitte der Platte."
    ),
)
def rotate_object(ctx: OpContext) -> OpResult:
    params = cast(RotateParams, ctx.params)
    source = ctx.inputs[0]
    # Ein genannter Punkt schlägt den Anker aus dem eigenen Netz — nur so
    # drehen mehrere Körper um dieselbe Stelle statt jeder um sich selbst.
    pivot = named_pivot(params) or anchor_point(
        as_mesh_data(source.mesh), cast(Anchor, params.about)
    )
    matrix = rotation(cast(Axis, params.axis), params.angle, pivot)
    turned = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=turned)],
        transform=as_transform(matrix),
        findings=_stood_still(matrix),
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
        choices=_ANCHORS_WITH_POINT,
        placement="advanced",
        doc=_(
            "Der Punkt, der stehen bleibt: Schwerpunkt, Nullpunkt, Aufstandsfläche "
            "— oder ein genannter Punkt, damit mehrere Körper zusammen wachsen."
        ),
    )
    pivot_x: float = param(
        title=_("Bezugspunkt X"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Gilt nur, wenn der Bezugspunkt „Genannter Punkt“ ist."),
    )
    pivot_y: float = param(
        title=_("Bezugspunkt Y"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Gilt nur, wenn der Bezugspunkt „Genannter Punkt“ ist."),
    )
    pivot_z: float = param(
        title=_("Bezugspunkt Z"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Gilt nur, wenn der Bezugspunkt „Genannter Punkt“ ist."),
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
    pivot = named_pivot(params) or anchor_point(
        as_mesh_data(source.mesh), cast(Anchor, params.about)
    )
    matrix = scaling(factors, pivot)
    scaled = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=scaled)],
        transform=as_transform(matrix),
        findings=_stood_still(matrix),
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
    shortcut="Ctrl+M",
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

    ``features={}`` in der Ausgabe heißt **nicht**, dass die Merkmale wegfallen
    — hier stand das bis zum 22.08.2026, und es war nachweislich falsch. Die
    *erkannten* Merkmale kommen aus dem Stand davor und finden sich über die
    gemeldete Matrix wieder (§21.2); nachgemessen an einer Platte: sechs Flächen
    vorher, dieselben sechs Namen nachher. Was das leere Feld tatsächlich
    kostete, waren die *erzeugten* Merkmale, und das war eine Lücke und kein
    Vorsatz — sie werden jetzt mitgenommen. Richtig ist das auch: Der Stift, den
    Op 3 gesetzt hat, ist nach der Spiegelung derselbe Stift, und eine Passung
    darauf bleibt gültig. Das Feld bleibt leer, weil diese Operation keine
    Merkmale erzeugt; wer hier etwas hineinschreibt, meldet neue.
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
    # Am Merkmal „offene Kante" angeboten: Das ist die Stelle, die der
    # Prüfbericht als „Das Modell ist an drei Stellen offen" meldet, und
    # „Schließt Löcher" ist die Antwort darauf. Ohne diese Zeile bestand das
    # Kontextmenü an einer angeklickten offenen Stelle aus Ausblenden — für
    # den häufigsten Defekt fehlte der kürzeste Weg vom Sehen zum Tun (§2.6).
    applies_to=("edge_loop",),
    shortcut="Ctrl+Shift+R",
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
    if not result.changed and not findings:
        # Ein gesundes Netz sah bisher aus wie eine Reparatur, die nicht
        # gelaufen ist: keine Meldung, kein Unterschied, ein Schritt im
        # Verlauf. Das Ergebnis „nichts zu tun" ist ein gutes und gehört
        # gesagt (§2.7).
        #
        # **Und nur, wenn sonst nichts zu sagen war.** ``changed`` allein
        # genügt nicht: Ein Netz, das offen bleibt, ohne dass ein Schritt
        # gegriffen hat, trägt bereits ``repair.still_open`` — und daneben
        # „nichts zu reparieren" zu setzen ist ein Widerspruch in derselben
        # Liste.
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


def _material_slots_after_boolean(
    ctx: OpContext, kind: BooleanKind, mesh: MeshData
) -> list[MaterialSlot]:
    """Behält die Beschreibungen aller Slots, die das Ergebnis wirklich nutzt.

    Die Flächennummern überträgt :func:`boolean`; Name, Farbe und Filamenttyp
    liegen jedoch am Szenenobjekt. Bei Vereinigung und Schnitt können Flächen
    beider Eingaben übrig bleiben, bei der Differenz nur die des ersten
    Körpers. Treffen zwei Beschreibungen dieselbe Nummer, gewinnt deshalb der
    erste Körper — er ist auch der, dessen Name und Material fortbestehen.
    """
    sources = ctx.inputs[:1] if kind == "difference" else ctx.inputs[:2]
    known: dict[int, MaterialSlot] = {}
    for entry in sources:
        for slot in entry.material_slots:
            known.setdefault(slot.index, slot)
    present = set(used_slots(mesh))
    return [known[index] for index in sorted(known) if index in present]


def _boolean_op(ctx: OpContext, kind: BooleanKind, seed: int | None) -> OpResult:
    """Zwei Körper hinein, einer heraus — mit der Rückfallkette dahinter (§17.2).

    Zwei Auskünfte kommen dazu, die dem freien ``boolean`` fehlen, weil sie erst
    an der Operation Sinn ergeben (operationen.md, „Wer Boolesches rechnet,
    fragt danach"):

    - Eine **leere Schnittmenge** ist kein Kettenfehler, sondern eine Tatsache:
      die zwei Körper treffen sich nicht. ``allow_empty`` hält die Kette davon
      ab, das viermal bis zur Voxelstufe zu bestätigen, und der Grund wird
      genannt statt „das Werkzeug deckt ihn vollständig ab".
    - **Vereinigung und Differenz, die nichts bewirken**, sagen es über
      ``without_effect`` — ein Abzugskörper neben dem Teil oder ein Körper, der
      schon ganz im anderen steckt, ließ sonst einen Schritt im Verlauf und ein
      unverändertes Bild zurück.
    """
    first, second = (as_mesh_data(entry.mesh) for entry in ctx.inputs[:2])
    outcome = boolean(
        kind,
        [first, second],
        quality=ctx.quality,
        seed=seed,
        allow_empty=kind == "intersection",
        cancelled=ctx.cancelled,
    )
    findings = list(outcome.findings)
    if kind == "intersection":
        if outcome.mesh.triangle_count == 0:
            raise GeometryError(
                _("Die Körper haben keinen gemeinsamen Bereich."),
                detail=_(
                    "Die Schnittmenge ist leer — die beiden Körper überschneiden sich "
                    "nicht. Lage und Maße prüfen, damit sie sich treffen."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
    else:
        nothing = without_effect(first, outcome.mesh, kind, ctx.profile)
        if nothing is not None:
            findings.append(nothing)
    return OpResult(
        outputs=[
            dataclasses.replace(
                ctx.inputs[0],
                mesh=outcome.mesh,
                material_slots=_material_slots_after_boolean(ctx, kind, outcome.mesh),
            )
        ],
        solver=outcome.solver,
        findings=findings,
    )


@register_op(
    name="union_objects",
    title=_("Vereinigen"),
    category="boolean",
    params=BooleanParams,
    consumes=2,
    produces=1,
    keeps_inputs=1,
    deterministic=False,
    # **Der Buchstabe kommt aus dem deutschen Titel.** So hält es der Bestand
    # seit je — *Bohrung setzen* auf Strg+B, *Drehen* auf Strg+R, *Verschieben*
    # auf Strg+T —, und daran ändert eine Übersetzung nichts: Kürzel sind keine
    # Texte, sie stehen im Register. Ist der einfache Buchstabe belegt, kommt
    # Umschalt dazu; ist auch das belegt, bleibt die Operation ohne Kürzel.
    # *Skalieren* ist der Fall: S gehört dem Speichern und Umschalt+S dem
    # Speichern unter, und ein erfundener Buchstabe wäre schlechter als keiner.
    #
    # Warum überhaupt mehr: §19.2 nennt die Befehlspalette den Universalzugang,
    # und dort steht das Kürzel neben dem Titel — „so lernt man sie nebenbei".
    # Bei sechs von sechsundachtzig war nebenbei wenig zu lernen.
    shortcut="Ctrl+Shift+V",
    doc=_(
        "Verschmilzt zwei Objekte zu einem. Das zuerst angeklickte bleibt mit "
        "seinem Namen und Material — das zweite geht darin auf."
    ),
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
    keeps_inputs=1,
    deterministic=False,
    shortcut="Ctrl+Shift+A",
    # **„Das erste" ist die Reihenfolge der Auswahl, und das stand nirgends.**
    # Die Operation hat kein einziges Feld; welcher Körper bleibt, entscheidet
    # allein, welchen der Nutzer zuerst angeklickt hat. Gemessen an einem Klotz
    # 20 x 20 x 20 und einem Stift 6 x 6 x 30: richtig herum bleiben 7280 mm³,
    # verkehrt herum 360 — und dazu kein Hinweis, nur ein Ergebnis, das den
    # Namen des Stifts trägt.
    doc=_(
        "Zieht das zweite Objekt vom ersten ab. Zuerst das Teil anklicken, das "
        "bleiben soll — dann das, was weggenommen wird."
    ),
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
    keeps_inputs=1,
    deterministic=False,
    # „Schnittmenge" beginnt mit S wie das Speichern; X ist das Zeichen für den
    # Schnitt selbst und in jedem Mengendiagramm dasselbe.
    shortcut="Ctrl+Shift+X",
    doc=_(
        "Behält nur, was beide Objekte gemeinsam haben. Das zuerst angeklickte "
        "bleibt mit seinem Namen und Material."
    ),
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
    # Der häufigste Handgriff von Weg 1: Ein heruntergeladenes Modell sitzt
    # mittig auf z = 0 und steckt zur Hälfte unter der Platte.
    shortcut="Ctrl+Shift+B",
    doc=_("Setzt das Objekt mit seiner Unterseite auf das Druckbett."),
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
        kind="feature",
        default="",
        doc=_("Bohrung oder Fläche am bewegten Objekt. Ein Klick im Fenster trägt sie ein."),
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
    # Der Stift gehört dazu: Er trägt Achse und Mitte wie die Bohrung
    # (gemessen an einem erkannten Zapfen), und Auto Split legt
    # Stift/Loch-Paare an — „den Stift ins Loch legen“ ist der
    # kanonische Fall dieser Operation. Bis zum 27.08.2026 bot ein
    # Rechtsklick auf einen Stift sie nicht einmal an.
    applies_to=["hole", "pin", "face"],
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
            detail=_(
                "Ein Ziel besteht aus dem Objekt und dem Merkmal, getrennt durch "
                "einen Doppelpunkt — etwa obj_2:hole_1."
            ),
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
            detail=_(
                "Kein Merkmal dieses Namens sitzt an den gewählten Objekten. "
                "Merkmalsnamen entstehen beim Bohren, Aushöhlen oder Einsetzen."
            ),
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
