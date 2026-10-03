"""Geometrie-Operationen (Bauplan §25, Kategorie „Transformation").

Das sind die Operationen, die der Gizmo erzeugt (§18.11): ein Ziehen im
Viewport endet als eine von ihnen, mit den Zahlen, bei denen das Ziehen
angekommen ist. Genau das macht ein Ziehen rücknehmbar wie alles andere.
"""

from __future__ import annotations

import dataclasses
from typing import Any, cast

from app.core.errors import (
    CANCEL,
    CHANGE_SIZE,
    CHANGE_THIS_STEP,
    CHOOSE,
    CORRECT_INPUT,
    Action,
    AppError,
    GeometryError,
)
from app.core.geom.align import align_matrix
from app.core.geom.attributes import used_slots
from app.core.geom.boolean import (
    NOTHING_LEFT_DETAIL,
    NOTHING_LEFT_TITLE,
    BooleanKind,
    boolean,
    without_effect,
)
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import (
    free_spot_param,
    placed_at_free_spot,
    spot_param,
    spot_plate_param,
)
from app.core.geom.repair import repair
from app.core.geom.transform import (
    AXIS_VECTORS,
    Anchor,
    Axis,
    absolute_rotation,
    anchor_point,
    composed,
    moved_object,
    pattern_centre,
    pattern_centre_param,
    reference_point,
    rotation,
    scaling,
    translation,
)
from app.core.registry import VARIABLE, op_params, param, register_op
from app.core.types import (
    BaseParams,
    FeatureRef,
    Finding,
    MaterialSlot,
    OpContext,
    OpResult,
    SceneObject,
    SolverInfo,
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


def _keeping_on_bed(*, relative_only: bool = False) -> Any:
    """Der Parameter, der einen bewegten Körper auf der Druckfläche hält.

    **Die Vorgabe ist aus, und das ist der ganze Unterschied.** Ein getippter
    Wert ist eine *Ansage* — „um 150 mm nach rechts" —, und die führt Solidon
    aus, auch wenn das Teil dabei vom Bett läuft; der Bauraumbefund sagt es
    danach. Ein Zug am Griff ist ein *Zeigen*, und wer zeigt, meint einen
    Platz. Deshalb setzt das Fenster den Haken beim Ziehen (`MainWindow.
    _on_transform_dragged`), und ein Rezept, das dieselbe Operation mit Zahlen
    füllt, bekommt ihn nicht.

    Der Unterschied ist nicht theoretisch: Das Galerieteil *gehaeuse* schiebt
    seinen Deckel um 135 mm zur Seite und graviert danach bei x = 135. Eine
    Rückholung dieses Schrittes ließe die Gravur ins Leere greifen, und
    „SOLIDON" fiele in sieben lose Buchstaben.

    Dreimal derselbe Wortlaut an drei Klassen — einmal geschrieben, damit die
    drei Dialoge nicht auseinanderlaufen. Ein Feld-Objekt darf nicht geteilt
    werden, deshalb eine Fabrik und keine Konstante.
    """
    return param(
        title=_("Auf dem Bett halten"),
        default=False,
        depends_on=("mode", ("relative",)) if relative_only else None,
        placement="advanced",
        doc=_(
            "Bringt die Bewegung den Körper über den Rand der Druckfläche, "
            "wird er "
            "zurückgeholt — so wenig wie möglich, und wenn dort ein anderer steht, "
            "an die nächste freie Stelle. Ein Zug am Griff setzt das von selbst: "
            "Wer zieht, zeigt auf einen Platz. Getippte Werte führt Solidon aus, "
            "wie sie dastehen."
        ),
    )


def _held_on_bed(
    ctx: OpContext, source: SceneObject, moved: SceneObject, matrix: Any
) -> tuple[SceneObject, Any, list[Finding]]:
    """Hält bewegte Körper auf der Druckfläche (§29).

    **Und nur dort.** Bis zum 18.09.2026 hielt diese Bindung zwei
    Bedingungen — innerhalb der Fläche *und* ohne Überschneidung —, und
    damit war das Zusammenschieben zweier Teile über den Griff nicht mehr
    zu machen. Zwei Körper am selben Ort sind eine Absicht; ein Körper
    neben dem Bett ist es nie.

    **Warum eine Regel und nicht ein Befund** (Robert, 12.09.2026: „das ist
    aber zu kompliziert für den Kunden, wie können wir das automatisieren?").
    Ein Zug am Gizmo speichert einen *Weg*; gemeint war ein *Platz*. Wer
    danach einen Parameter weiter oben ändert, lässt *Druckoptimal ausrichten*
    neu anordnen — der Körper startet woanders, derselbe Weg wird trotzdem
    daraufgerechnet, und er liegt neben dem Bett. Aufräumen hieß bis hierher:
    den Schritt im Verlauf finden und löschen. Das ist ein Urteil, das der
    Kunde nicht fällen kann.

    **Wer schon daneben stand, wird nicht eingefangen.** Geprüft wird der
    *Eingang*: Lag er nicht auf der Fläche, ist seine Lage eine Absicht und
    keine Panne — ein geparkter Körper bleibt geparkt, so oft man ihn noch
    schiebt.

    **Und getippt wird ausgeführt, gezogen wird gezeigt.** Der Haken kommt vom
    Zug am Griff und nicht von der Vorgabe (siehe :func:`_keeping_on_bed`);
    ein Rezept mit `dx = 150` läuft weiter über den Bauraum hinaus und meldet
    es, statt still zurückzurücken.

    Die Regel steht als Parameter in der Operation und nicht in der
    Auswertung (Bauplan §17.1: „Beides steht als Parameter in der Op, nicht
    als Regel bei der Auswertung"). Wer neben das Bett legen will, nimmt den
    Haken heraus; der Befund nennt ihn.

    **Die gemeldete Matrix wird nachgeführt.** Sie ist die Auskunft für
    Vorschau und Gizmo und muss den Eingang genau auf den Ausgang legen —
    erst die Bewegung, dann die Rückholung. Dieselbe Rechnung wie bei
    *Druckoptimal ausrichten*, wenn es nach dem Drehen anordnet.
    """
    from app.core.build_area import fits_xy, printable_area
    from app.core.geom.prepare import back_onto_bed

    printer = getattr(ctx.profile, "printer", None)
    if printer is None or not getattr(ctx.params, "keep_on_bed", False):
        return moved, matrix, []
    # **Wer schon daneben stand, wird nicht eingefangen** — geprüft am Eingang.
    if not fits_xy(source.mesh, printable_area(printer)):
        return moved, matrix, []
    # Um die Körper der Platte, auf der er ankommt — nach einem Wechsel ist
    # das nicht mehr die, von der er kam.
    others = [
        as_mesh_data(other.mesh)
        for key, other in ctx.scene.objects.items()
        if key != source.id and other.plate == moved.plate
    ]
    offset, findings = back_onto_bed(moved.mesh, others, ctx.profile)
    if max(abs(value) for value in offset) <= EPS_GEOM:
        return moved, matrix, findings
    correction = translation(offset)
    return (
        moved_object(moved, correction, cancelled=ctx.cancelled),
        composed(correction, matrix),
        findings,
    )


@op_params
class TranslateParams(BaseParams):
    mode: str = param(
        title=_("Verschieben"),
        default="relative",
        choices=("relative", "absolute"),
        doc=_("Um einen Weg verschieben oder einen Bezugspunkt auf eine feste Lage setzen."),
    )
    dx: float = param(
        title=_("Verschiebung X"),
        default=0.0,
        unit="mm",
        doc=_("Um wie viel verschoben wird, nicht wohin. Positiv geht nach rechts."),
        depends_on=("mode", ("relative",)),
    )
    dy: float = param(
        title=_("Verschiebung Y"),
        default=0.0,
        unit="mm",
        doc=_("Positiv geht nach hinten."),
        depends_on=("mode", ("relative",)),
    )
    dz: float = param(
        title=_("Verschiebung Z"),
        default=0.0,
        unit="mm",
        doc=_("Positiv geht nach oben. Zum Aufsetzen gibt es *Auf das Bett setzen*."),
        depends_on=("mode", ("relative",)),
    )
    x: float = param(
        title=_("Ziel X"),
        default=0.0,
        unit="mm",
        depends_on=("mode", ("absolute",)),
        doc=_("X-Lage des gewählten Bezugspunkts."),
    )
    y: float = param(
        title=_("Ziel Y"),
        default=0.0,
        unit="mm",
        depends_on=("mode", ("absolute",)),
        doc=_("Y-Lage des gewählten Bezugspunkts."),
    )
    z: float = param(
        title=_("Ziel Z"),
        default=0.0,
        unit="mm",
        depends_on=("mode", ("absolute",)),
        doc=_("Z-Lage des gewählten Bezugspunkts."),
    )
    reference: str = param(
        title=_("Bezugspunkt"),
        default="bed",
        placement="advanced",
        choices=(
            "bed",
            "centre",
            "corner_000",
            "corner_001",
            "corner_010",
            "corner_011",
            "corner_100",
            "corner_101",
            "corner_110",
            "corner_111",
            "feature",
        ),
        depends_on=("mode", ("absolute",)),
        doc=_(
            "Bei mehreren Körpern gilt der gemeinsame Hüllquader. "
            "Das Merkmal gehört zum ersten Körper."
        ),
    )
    reference_feature: str = param(
        title=_("Bezugsmerkmal"),
        default="",
        kind="feature",
        placement="advanced",
        depends_on=("reference", ("feature",)),
        doc=_("Kennung des Merkmals, dessen Mittelpunkt die Zielstelle erreicht."),
    )
    keep_on_bed: bool = _keeping_on_bed(relative_only=True)
    plate: int = param(
        title=_("Auf Platte"),
        # **Null heißt: auf seiner Platte.** Die Platten zählen wie im
        # Plattenwähler ab eins; jeder Schritt von vor diesem Feld bleibt so,
        # wie er war. Das Fenster setzt es, wenn ein Zug auf einem anderen Bett
        # endet (``MainWindow._on_transform_dragged``).
        default=0,
        minimum=0,
        placement="advanced",
        doc=_(
            "Auf welche Druckplatte der Körper wandert, gezählt wie im Plattenwähler; "
            "die Verschiebung gilt dann dort. Null lässt ihn auf seiner."
        ),
    )


def _too_small_to_print(mesh: object, profile: object) -> list[Finding]:
    """Sagt, wenn nach dem Skalieren nichts Druckbares übrig ist.

    Für „zu groß" gibt es ``arrange.out_of_build_volume``; die Gegenrichtung
    hatte niemanden. Gemessen beim Durchfahren der Schieber über ihren ganzen
    Bereich: ``scale_object`` mit dem Faktor 0,001 und ``fit_to_size`` mit
    0,1 mm machen aus einem Halter ein Teil von Hundertstelmillimetern —
    Volumen 0,0 in der Anzeige, **kein einziger Befund**, und im Verlauf steht
    ein Schritt, der etwas getan zu haben scheint.

    Die Grenze kommt aus dem Profil und nicht aus dem Code (Regel 7):
    ``smallest_printable_volume`` ist ein Stück Extrusionsbahn von einer
    Bahnbreite Länge — am Centauri mit 0,4er Düse sind das 0,035 mm³. Was
    darunter liegt, hinterlässt dieser Drucker nicht, und an einer 0,8er Düse
    ist die Antwort eine andere.

    Ein Hinweis und keine Absage: Wer ein Modell absichtlich klein rechnet, um
    es später wieder zu vergrößern, tut nichts Verbotenes — er soll nur wissen,
    dass dabei gerade kein Teil mehr steht.
    """
    volume = getattr(mesh, "volume", None)
    limit = getattr(profile, "smallest_printable_volume", None)
    if volume is None or limit is None or volume >= limit:
        return []
    return [
        Finding(
            code="transform.below_printable",
            severity="warning",
            message=_(
                "Der Körper ist danach kleiner als das, was dieser Drucker "
                "hinterlässt. Gedruckt entstünde daraus nichts."
            ),
            values={"volume_mm3": round(float(volume), 6)},
            # Regel 17: Der Maßstab steht im Schritt.
            suggestions=(CORRECT_INPUT,),
        )
    ]


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
            # Die Vorgabe des Dialogs übernommen: Der Weg ist derselbe Schritt
            # mit anderen Werten (RM-374).
            suggestions=(CHANGE_THIS_STEP,),
        )
    ]


@register_op(
    name="translate_object",
    # Liest keinen Prozesswert (Beleg: ``_STEPS_WITHOUT_PROCESS`` in tests/test_cache.py).
    reads_process=False,
    cache_version="4",
    title=_("Verschieben"),
    category="transform",
    params=TranslateParams,
    consumes=VARIABLE,
    minimum_inputs=1,
    produces=VARIABLE,
    shortcut="Ctrl+T",
    # ``keep_on_bed`` sucht den freien Platz um die **übrigen** Körper herum;
    # kein Parameter benennt sie, also steht die Lesart am Register
    # (`.claude/rules/operationen.md`, „Eine Operation, die an ihren eigenen
    # Eingängen vorbei liest"). Ohne das behielte eine verschobene Kopie ihre
    # Rückholung, nachdem der Nachbar längst woanders steht.
    reads_other_bodies=True,
    doc=_("Verschiebt ein Objekt um die angegebenen Millimeter."),
)
def translate_object(ctx: OpContext) -> OpResult:
    params = cast(TranslateParams, ctx.params)
    if params.mode == "absolute":
        point = reference_point(ctx.inputs, params.reference, params.reference_feature)
        matrix = translation((params.x - point[0], params.y - point[1], params.z - point[2]))
        outputs = [moved_object(source, matrix, cancelled=ctx.cancelled) for source in ctx.inputs]
        if params.plate > 0:
            outputs = [dataclasses.replace(body, plate=params.plate - 1) for body in outputs]
        return OpResult(
            outputs=outputs, transform=as_transform(matrix), findings=_stood_still(matrix)
        )
    if len(ctx.inputs) > 1:
        outputs = []
        findings = []
        for source in ctx.inputs:
            single = translate_object(dataclasses.replace(ctx, inputs=[source]))
            outputs.extend(single.outputs)
            findings.extend(single.findings)
        return OpResult(outputs=outputs, findings=findings)
    source = ctx.inputs[0]
    matrix = translation((params.dx, params.dy, params.dz))
    moved = moved_object(source, matrix, cancelled=ctx.cancelled)
    # **Die Platte wechselt, die Koordinaten nicht** (Robert, 29.09.2026: „wenn
    # ich sie auf eine andere platte verschieben will springen sie auch"). Im
    # Bild stehen die Betten nebeneinander, in der Szene übereinander; ein Zug
    # hinüber ist deshalb ein kurzer Weg auf einer anderen Platte und kein
    # langer auf der eigenen, den *Auf dem Bett halten* zurückholen müsste.
    changed = params.plate > 0 and params.plate - 1 != source.plate
    if changed:
        moved = dataclasses.replace(moved, plate=params.plate - 1)
    moved, matrix, held = _held_on_bed(ctx, source, moved, matrix)
    return OpResult(
        outputs=[moved],
        transform=as_transform(matrix),
        findings=[*([] if changed else _stood_still(matrix)), *held],
    )


@op_params
class RotateParams(BaseParams):
    mode: str = param(
        title=_("Drehen"),
        default="relative",
        choices=("relative", "absolute"),
        doc=_("Um einen Winkel drehen oder die Ausgangsachsen auf Zielwinkel setzen."),
    )
    angle_x: float = param(
        title=_("Zielwinkel X"),
        default=0.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        depends_on=("mode", ("absolute",)),
        doc=_("Zielwinkel zur Ausgangslage: erst X, dann Y, dann Z um die Weltachsen."),
    )
    angle_y: float = param(
        title=_("Zielwinkel Y"),
        default=0.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        depends_on=("mode", ("absolute",)),
        doc=_("Zielwinkel zur Ausgangslage: erst X, dann Y, dann Z um die Weltachsen."),
    )
    angle_z: float = param(
        title=_("Zielwinkel Z"),
        default=0.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        depends_on=("mode", ("absolute",)),
        doc=_("Zielwinkel zur Ausgangslage: erst X, dann Y, dann Z um die Weltachsen."),
    )
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=_AXES,
        depends_on=("mode", ("relative",)),
        doc=_("Um welche Achse gedreht wird. Z dreht auf dem Bett, X und Y kippen."),
    )
    angle: float = param(
        title=_("Winkel"),
        default=90.0,
        depends_on=("mode", ("relative",)),
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        doc=_("Drehwinkel gegen den Uhrzeigersinn, von der Achsspitze aus gesehen."),
    )
    about: str = param(
        title=_("Drehpunkt"),
        default="centre",
        choices=(*_ANCHORS_WITH_POINT, *(f"corner_{index:03b}" for index in range(8)), "feature"),
        placement="advanced",
        doc=_(
            "Mitte des Objekts, Ursprung oder Druckbett — oder ein genannter Punkt, "
            "um den mehrere Körper gemeinsam drehen."
        ),
    )
    reference_feature: str = param(
        title=_("Bezugsmerkmal"),
        default="",
        kind="feature",
        placement="advanced",
        depends_on=("about", ("feature",)),
        doc=_("Kennung des Merkmals, dessen Mittelpunkt die Zielstelle erreicht."),
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
    keep_on_bed: bool = _keeping_on_bed(relative_only=True)


@register_op(
    name="rotate_object",
    # Liest keinen Prozesswert (Beleg: ``_STEPS_WITHOUT_PROCESS`` in tests/test_cache.py).
    reads_process=False,
    cache_version="4",
    title=_("Drehen"),
    category="transform",
    params=RotateParams,
    consumes=VARIABLE,
    minimum_inputs=1,
    produces=VARIABLE,
    shortcut="Ctrl+R",
    # Wie bei *Verschieben*: ``keep_on_bed`` liest die übrigen Körper.
    reads_other_bodies=True,
    doc=_(
        "Dreht ein Objekt um eine Achse. Der Drehpunkt entscheidet, worum: um die "
        "eigene Mitte, um den Nullpunkt des Projekts oder um die Mitte der Platte."
    ),
)
def rotate_object(ctx: OpContext) -> OpResult:
    params = cast(RotateParams, ctx.params)
    source = ctx.inputs[0]
    if params.mode == "absolute":
        pivot = named_pivot(params)
        if pivot is None:
            pivot = (
                (0.0, 0.0, 0.0)
                if params.about == "origin"
                else reference_point(ctx.inputs, params.about, params.reference_feature)
            )
        matrix = absolute_rotation(source, (params.angle_x, params.angle_y, params.angle_z), pivot)
        return OpResult(
            outputs=[moved_object(body, matrix, cancelled=ctx.cancelled) for body in ctx.inputs],
            transform=as_transform(matrix),
            findings=_stood_still(matrix),
        )
    if len(ctx.inputs) > 1:
        results = [rotate_object(dataclasses.replace(ctx, inputs=[body])) for body in ctx.inputs]
        return OpResult(
            outputs=[body for result in results for body in result.outputs],
            findings=[finding for result in results for finding in result.findings],
        )
    # Ein genannter Punkt schlägt den Anker aus dem eigenen Netz — nur so
    # drehen mehrere Körper um dieselbe Stelle statt jeder um sich selbst.
    pivot = named_pivot(params)
    if pivot is None:
        pivot = (
            (0.0, 0.0, 0.0)
            if params.about == "origin"
            else reference_point([source], params.about, params.reference_feature)
        )
    matrix = rotation(cast(Axis, params.axis), params.angle, pivot)
    turned = moved_object(source, matrix, cancelled=ctx.cancelled)
    turned, matrix, held = _held_on_bed(ctx, source, turned, matrix)
    return OpResult(
        outputs=[turned],
        transform=as_transform(matrix),
        findings=[*_stood_still(matrix), *held],
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
            "Der Punkt, der stehen bleibt: Mitte des Objekts, Ursprung oder Druckbett "
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
    keep_on_bed: bool = _keeping_on_bed()


@register_op(
    name="scale_object",
    cache_version="4",
    title=_("Skalieren"),
    category="transform",
    params=ScaleParams,
    consumes=1,
    produces=1,
    # Wie bei *Verschieben*: ``keep_on_bed`` liest die übrigen Körper. Hier
    # wiegt es schwerer als dort — ein Körper, der wächst, verlässt die Fläche,
    # ohne dass jemand ihn geschoben hätte.
    reads_other_bodies=True,
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
    pivot = named_pivot(params) or anchor_point(source.mesh, cast(Anchor, params.about))
    matrix = scaling(factors, pivot)
    scaled = moved_object(source, matrix, cancelled=ctx.cancelled)
    scaled, matrix, held = _held_on_bed(ctx, source, scaled, matrix)
    return OpResult(
        outputs=[scaled],
        transform=as_transform(matrix),
        findings=[
            *_stood_still(matrix),
            *_too_small_to_print(scaled.mesh, ctx.profile),
            *held,
        ],
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
    #: Weg 3 setzt ihn: Ein erzeugtes Modell ist ein weiteres Modell und wird
    #: erst am fertigen Maß gelegt — dieselbe Regel wie ``load.free_spot``.
    #: Vorgabe aus, damit ein älterer Schritt liegen bleibt, wo er stand.
    free_spot: bool = free_spot_param(
        _(
            "Setzt das Modell nach dem Skalieren auf und legt es neben die Teile, die schon "
            "im Projekt liegen: so nah an der Plattenmitte wie möglich, auf der ersten "
            "Platte mit Platz."
        ),
        placement="advanced",
    )
    spot_x: float | None = spot_param("x")
    spot_y: float | None = spot_param("y")
    spot_plate: int = spot_plate_param()


@register_op(
    name="fit_to_size",
    cache_version="5",
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
    body = source.mesh
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
    fitted = moved_object(source, matrix, cancelled=ctx.cancelled)
    placed: list[Finding] = []
    answered: dict[str, Any] = {}
    if params.free_spot:
        # Gelegt wird am fertigen Maß, nicht am Einheitswürfel des Generators;
        # der eigene Eingang belegt keinen Platz neben sich selbst. Die Stelle
        # wird einmal gerechnet und festgehalten (``answered``, §15.7).
        spot = placed_at_free_spot(
            fitted.mesh.bounds,
            ctx.profile,
            ctx.scene,
            spot=(params.spot_x, params.spot_y, params.spot_plate),
            ignore={source.id},
            objects=[fitted],
        )
        matrix = composed(translation(spot.offset), matrix)
        fitted = dataclasses.replace(
            moved_object(source, matrix, cancelled=ctx.cancelled), plate=spot.plate
        )
        placed.extend(spot.findings)
        answered.update(spot.answered)
    return OpResult(
        outputs=[fitted],
        transform=as_transform(matrix),
        findings=[
            Finding(
                code="transform.fitted",
                severity="info",
                message=_("Auf Maß gebracht."),
                # Das Maß ist eine Vorgabe — beim Generatorwürfel die
                # Arbeitsgröße —, und der Weg zum gemeinten ist dieser Schritt
                # (RM-374): *Größe ändern* öffnet ihn mit dem Cursor im Maß.
                values={"from_mm": round(current, 3), "to_mm": params.largest, "field": "largest"},
                suggestions=(CHANGE_SIZE,),
                source="internal",
            ),
            *placed,
            *_too_small_to_print(fitted.mesh, ctx.profile),
        ],
        answered=answered,
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
        internal=True,
        doc=_(
            "Wo die Spiegelebene liegt: in der Mitte des Objekts, im Ursprung oder am Druckbett."
        ),
    )
    follow_anchor: bool = param(
        title=_("Bezugspunkt"),
        default=False,
        internal=True,
        doc=_(
            "Wo die Spiegelebene liegt: in der Mitte des Objekts, im Ursprung oder am Druckbett."
        ),
    )
    cx: float | None = pattern_centre_param("x")
    cy: float | None = pattern_centre_param("y")
    cz: float | None = pattern_centre_param("z")


@register_op(
    name="mirror_object",
    cache_version="2",
    # Liest keinen Prozesswert (Beleg: ``_STEPS_WITHOUT_PROCESS`` in tests/test_cache.py).
    reads_process=False,
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

    Die Merkmale reisen mit ihren tatsächlichen Ergebnisflächen. Namen und
    Erzeuger bleiben erhalten; gerichtete Angaben werden gespiegelt.
    """
    params = cast(MirrorParams, ctx.params)
    source = ctx.inputs[0]

    factors = [1.0, 1.0, 1.0]
    factors["xyz".index(params.axis)] = -1.0
    pivot, answered = pattern_centre(
        source,
        params.cx,
        params.cy,
        params.cz,
        anchor=cast(Anchor, params.about),
        follow_anchor=params.follow_anchor,
    )
    matrix = scaling((factors[0], factors[1], factors[2]), pivot)

    return OpResult(
        outputs=[moved_object(source, matrix, cancelled=ctx.cancelled)],
        transform=as_transform(matrix),
        answered=answered,
    )


@op_params
class RepairParams(BaseParams):
    """Was *Reparieren* tut.

    **Vorn steht, was nach dem Einlesen noch etwas ändert** (Durchsicht
    24.09.2026). Verschweißen, leere Dreiecke und Außenseiten erledigt schon
    der Import; vorn stand allein das Lochfüllen, das er ebenfalls fährt, und
    die zwei Schalter, die danach noch wirken, lagen hinter der Klappe.
    """

    fill_holes: bool = param(
        title=_("Offene Stellen schließen"),
        default=True,
        doc=_("Schließt Löcher. Große Öffnungen nennt der Prüfbericht."),
    )
    #: Der Rückweg *Offen lassen* an einer großen Öffnung (RM-241): Die kleinen
    #: Löcher gehen weiter zu, nur die große bleibt, wie sie war. Vorgabe an —
    #: ein älterer Schritt ohne den Wert schließt, wie er immer geschlossen hat.
    wide_holes: bool = param(
        title=_("Große Öffnungen schließen"),
        default=True,
        placement="advanced",
        depends_on=("fill_holes", (True,)),
        doc=_("Schließt auch Öffnungen, die eine neue große Fläche brauchen. Aus lässt sie offen."),
    )
    #: **Vorgabe an** (Entscheidung Robert, 24.09.2026). Die Suche läuft beim
    #: Reparieren ohnehin; aufgelöst wird nur, was die Nachprüfung als
    #: schnittfrei belegt, sonst bleibt das Teil unverändert. Ältere Schritte
    #: ohne diesen Wert behalten über die Migration 34 → 35 „aus".
    self_intersections: bool = param(
        title=_("Überschneidungen auflösen"),
        default=True,
        doc=_(
            "Verschmilzt Teile, die ineinanderstecken. Was nicht sicher geht, bleibt unverändert."
        ),
    )
    small_components: bool = param(
        title=_("Kleinstteile entfernen"),
        default=False,
        # Offene Splitter gehen beim Löcherschließen ohnehin; der Haken nimmt
        # auch geschlossene Kleinstteile (Review R18).
        doc=_("Entfernt auch geschlossene Teile, die viel kleiner sind als das Hauptteil."),
    )
    weld: bool = param(
        title=_("Doppelte Punkte zusammenführen"),
        default=True,
        placement="advanced",
        doc=_(
            "Führt Punkte zusammen, die praktisch aufeinanderliegen. Der häufigste "
            "Grund dafür, dass ein Netz aus mehreren Teilen zu bestehen scheint."
        ),
    )
    degenerate: bool = param(
        title=_("Leere Dreiecke entfernen"),
        default=True,
        placement="advanced",
        doc=_("Dreiecke ohne Fläche. Sie stören jede spätere Rechnung und tragen nichts."),
    )
    normals: bool = param(
        title=_("Außenseiten angleichen"),
        default=True,
        placement="advanced",
        doc=_("Richtet aus, wo außen ist. Ohne das erscheinen Flächen dunkel oder verschwinden."),
    )


@register_op(
    name="repair",
    cache_version="3",
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
    doc=_(
        "Schließt Löcher, entfernt fehlerhafte Dreiecke, gleicht die Außenseiten an und "
        "löst Überschneidungen auf."
    ),
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
        wide_holes=params.wide_holes,
        small_components=params.small_components,
        self_intersections=params.self_intersections,
        inspect_intersections=True,
        cancelled=ctx.cancelled,
        progress=ctx.progress,
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
    # **Was nicht repariert wurde, bleibt, was es war.** Ein exakter Körper
    # ging bis zum 21.09.2026 auch dann als Netz zurück, wenn die Reparatur
    # nichts zu tun fand — Strg+Umschalt+R an einem STEP machte aus dem
    # Körper Dreiecke und sagte „nichts zu reparieren" (Review, tests-3).
    # Geändert hat die Reparatur nur, was sie geändert hat; der Eingang
    # behält Kern und Merkmale.
    return OpResult(
        outputs=[
            source
            if not result.changed
            else dataclasses.replace(source, mesh=result.mesh, features={})
        ],
        findings=findings,
        solver=result.solver,
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
    aller Eingaben übrig bleiben, bei der Differenz nur die des ersten
    Körpers. Treffen zwei Beschreibungen dieselbe Nummer, gewinnt deshalb der
    erste Körper — er ist auch der, dessen Name und Material fortbestehen.
    """
    sources = ctx.inputs[:1] if kind == "difference" else ctx.inputs
    known: dict[int, MaterialSlot] = {}
    for entry in sources:
        for slot in entry.material_slots:
            known.setdefault(slot.index, slot)
    present = set(used_slots(mesh))
    return [known[index] for index in sorted(known) if index in present]


def _boolean_op(ctx: OpContext, kind: BooleanKind, seed: int | None) -> OpResult:
    """Mindestens zwei Körper hinein, einer heraus — mit der Rückfallkette dahinter (§17.2).

    Zwei Auskünfte kommen dazu, die dem freien ``boolean`` fehlen, weil sie erst
    an der Operation Sinn ergeben (operationen.md, „Wer Boolesches rechnet,
    fragt danach"):

    - Eine **leere Schnittmenge** ist kein Kettenfehler, sondern eine Tatsache:
      die gewählten Körper treffen sich nicht. ``allow_empty`` hält die Kette davon
      ab, das viermal bis zur Voxelstufe zu bestätigen, und der Grund wird
      genannt statt „das Werkzeug deckt ihn vollständig ab". Ebenso ist
      vollständiges Abziehen eine gültige Leerauskunft des Kerns; eine
      gestörte Ersatzgeometrie darf daraus keine dünne Resthaut erzeugen.
    - **Vereinigung und Differenz, die nichts bewirken**, sagen es über
      ``without_effect`` — ein Abzugskörper neben dem Teil oder ein Körper, der
      schon ganz im anderen steckt, ließ sonst einen Schritt im Verlauf und ein
      unverändertes Bild zurück.
    """
    # **Alle Eingänge, nicht die ersten zwei.** „man sollte es schon mit allen
    # können" (Robert, 06.09.2026): Vier Laschen an einen Kasten zu schweißen
    # waren vier Verlaufsschritte, weil die Operation genau zwei Körper nahm —
    # und der Dialog sagte „Erwartet: 2, Vorhanden: 5", nachdem der Nutzer alle
    # fünf gewählt hatte. Der Kern rechnet die Liste ohnehin am Stück
    # (``_kernel`` reicht sie an manifold3d durch); begrenzt hat sie nur das
    # Register. Beim Abziehen gilt dieselbe Lesart wie bei zweien: Der erste
    # Körper bleibt, alle weiteren gehen von ihm ab.
    if len(ctx.inputs) < 2:
        raise GeometryError(
            _("Diese Operation braucht mindestens zwei Objekte."),
            detail=_("Wählen Sie im Objektbaum oder im Bild einen zweiten Körper dazu."),
            suggestions=(CHOOSE, CANCEL),
        )
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid
    from app.core.geom.prepare_ops import union_bore_findings

    exact = [entry.mesh for entry in ctx.inputs if isinstance(entry.mesh, Solid)]
    if len(exact) == len(ctx.inputs):
        # Exakte Eingänge bleiben exakt. Gemischte Eingänge verwenden unten
        # weiterhin die Netz-Kette; eine Rückwandlung wird nicht behauptet.
        ctx.cancelled.raise_if_cancelled()
        solid = edit.boolean(kind, exact)
        ctx.cancelled.raise_if_cancelled()
        if solid.face_count == 0 or solid.volume <= EPS_GEOM:
            if kind == "intersection":
                raise GeometryError(
                    _("Die Körper haben keinen gemeinsamen Bereich."),
                    detail=_(
                        "Die Schnittmenge ist leer — die gewählten Körper überschneiden sich "
                        "nicht. Lage und Maße prüfen, damit sie sich treffen."
                    ),
                    suggestions=(CORRECT_INPUT, CANCEL),
                )
            raise GeometryError(
                title=NOTHING_LEFT_TITLE,
                detail=NOTHING_LEFT_DETAIL,
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        nothing = (
            without_effect(exact[0], solid, kind, ctx.profile) if kind != "intersection" else None
        )
        return OpResult(
            outputs=[
                dataclasses.replace(
                    ctx.inputs[0],
                    mesh=solid,
                    kind="brep",
                    features=features_of(solid, cancelled=ctx.cancelled),
                    material_slots=_material_slots_after_boolean(ctx, kind, as_mesh_data(solid)),
                )
            ],
            solver=SolverInfo(strategy="direct", attempted=("direct",)),
            findings=([nothing] if nothing is not None else [])
            + (union_bore_findings(ctx, solid) if kind == "union" else []),
        )
    bodies = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    outcome = boolean(
        kind,
        bodies,
        quality=ctx.quality,
        seed=seed,
        allow_empty=kind in ("intersection", "difference"),
        cancelled=ctx.cancelled,
        object_ids=tuple(entry.id for entry in ctx.inputs),
    )
    findings = list(outcome.findings)
    if outcome.mesh.triangle_count == 0:
        if kind == "intersection":
            raise GeometryError(
                _("Die Körper haben keinen gemeinsamen Bereich."),
                detail=_(
                    "Die Schnittmenge ist leer — die gewählten Körper überschneiden sich "
                    "nicht. Lage und Maße prüfen, damit sie sich treffen."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        raise GeometryError(
            title=NOTHING_LEFT_TITLE,
            detail=NOTHING_LEFT_DETAIL,
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if kind != "intersection":
        nothing = without_effect(bodies[0], outcome.mesh, kind, ctx.profile)
        if nothing is not None:
            findings.append(nothing)
    if kind == "union":
        findings.extend(union_bore_findings(ctx, outcome.mesh))
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
    cache_version="2",
    title=_("Vereinigen"),
    category="boolean",
    params=BooleanParams,
    consumes=VARIABLE,
    minimum_inputs=2,
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
        "Verschmilzt die gewählten Objekte zu einem. Das zuerst angeklickte bleibt "
        "mit seinem Namen und Material — die übrigen gehen darin auf."
    ),
)
def union_objects(ctx: OpContext) -> OpResult:
    return _boolean_op(ctx, "union", ctx.seed)


@register_op(
    name="subtract_objects",
    cache_version="2",
    title=_("Abziehen"),
    category="boolean",
    params=BooleanParams,
    consumes=VARIABLE,
    minimum_inputs=2,
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
        "Zieht alle danach gewählten Objekte vom ersten ab. Zuerst das Teil "
        "anklicken, das bleiben soll — dann alles, was weggenommen wird."
    ),
)
def subtract_objects(ctx: OpContext) -> OpResult:
    return _boolean_op(ctx, "difference", ctx.seed)


@register_op(
    name="intersect_objects",
    title=_("Schnittmenge"),
    category="boolean",
    params=BooleanParams,
    consumes=VARIABLE,
    minimum_inputs=2,
    produces=1,
    keeps_inputs=1,
    deterministic=False,
    # „Schnittmenge" beginnt mit S wie das Speichern; X ist das Zeichen für den
    # Schnitt selbst und in jedem Mengendiagramm dasselbe.
    shortcut="Ctrl+Shift+X",
    doc=_(
        "Behält nur den Bereich, den alle gewählten Objekte gemeinsam haben. "
        "Das zuerst angeklickte bleibt mit seinem Namen und Material."
    ),
)
def intersect_objects(ctx: OpContext) -> OpResult:
    return _boolean_op(ctx, "intersection", ctx.seed)


@op_params
class PlaceOnBedParams(BaseParams):
    pass


@register_op(
    name="place_on_bed",
    # Liest keinen Prozesswert (Beleg: ``_STEPS_WITHOUT_PROCESS`` in tests/test_cache.py).
    reads_process=False,
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
    return _place_inputs_on_bed(ctx)


@register_op(
    name="place_group_on_bed",
    # Liest keinen Prozesswert (Beleg: ``_STEPS_WITHOUT_PROCESS`` in tests/test_cache.py).
    reads_process=False,
    title=_("Gemeinsam auf das Bett setzen"),
    category="transform",
    params=PlaceOnBedParams,
    consumes=VARIABLE,
    minimum_inputs=2,
    produces=VARIABLE,
    doc=_(
        "Setzt die ausgewählten Körper gemeinsam auf das Druckbett und erhält ihre relative Lage."
    ),
)
def place_group_on_bed(ctx: OpContext) -> OpResult:
    """Die gespeicherten Eingaben behalten bei jeder Auswertung ihre relative Lage."""
    return _place_inputs_on_bed(ctx)


def _place_inputs_on_bed(ctx: OpContext) -> OpResult:
    """Einzelkörper und Gruppe erhalten denselben aus aktuellen Grenzen berechneten Versatz."""
    lowest = float("inf")
    for source in ctx.inputs:
        ctx.cancelled.raise_if_cancelled()
        lowest = min(lowest, source.mesh.bounds.minimum[2])
    matrix = translation((0.0, 0.0, -lowest))
    return OpResult(
        outputs=[moved_object(source, matrix, cancelled=ctx.cancelled) for source in ctx.inputs],
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
        # **Pflicht, trotz Vorgabe.** Ohne Ziel lehnt die Operation unten ab —
        # bis zum 14.09.2026 stand ihr Wähler trotzdem auf „— keines —", und
        # das Band antwortete mit dem Formatfehler („obj_2:hole_1"), einer
        # Zeichenkette, die in keiner Oberfläche vorkommt (Bedienweg-
        # Durchsicht). Die Vorgabe bleibt der leere Wert, den ein Klick
        # ersetzt (§21.3); eine Vorgabe macht ein Feld nicht optional.
        required=True,
        # Ein Merkmal als **Ziel** auf einem fremden Körper: Der Cache-Schlüssel
        # muss dessen Hash kennen, sonst bleibt der ausgerichtete Körper an der
        # alten Lage, wenn das Ziel verschoben wird — der Schlüssel sah nur
        # ``feature`` und nie dieses Feld (Gesamtreview 05.09.2026, CORE-13).
        targets_feature=True,
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
    if not params.target.strip():
        # **Noch nichts gewählt ist keine falsche Schreibweise.** Der Satz
        # darunter erklärt die Schreibweise ``obj_2:hole_1`` — richtig für
        # die Kommandozeile und für eine von Hand bearbeitete Datei, falsch
        # für den, der den Dialog gerade geöffnet hat: Gemessen am 14.09.2026
        # stand er im Band über der Vorschau, sobald das Fenster aufging.
        # Zwei Lagen, zwei Sätze (Regel 17).
        raise AppError(
            _("Zu dieser Handlung gehört ein zweites Merkmal."),
            detail=_("Wählen Sie das Merkmal, an dem ausgerichtet werden soll."),
            values={"target": params.target},
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie das Merkmal im Objektbaum aus.")),
            ),
        )

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
    # **Eine starre Bewegung wie Verschieben und Drehen** — und wie dort
    # bewegt ``moved_object`` den Körper samt Merkmalen. Bis zum 22.09.2026
    # stand hier ``apply`` am Netz: Ein exakter Körper kam als Dreiecksmodell
    # zurück, danach war kein Verrunden mehr möglich, und seine Merkmale
    # blieben an der alten Stelle stehen.
    return OpResult(
        outputs=[moved_object(source, matrix, cancelled=ctx.cancelled)],
        transform=as_transform(matrix),
    )
