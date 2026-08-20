"""Die Skizzen-Operationen (Bauplan §30.1, §25 Kategorie „Skizze").

Grundform wählen, Maße eintragen, Körper bekommen: extrudiert, als Tasche,
rotiert, entlang eines Bogens oder zwischen zwei Umrissen. Jede Operation
läuft denselben Weg — Grundform als Skizze (Leitprinzip 5: nie rohe
Punktlisten), Solver bestätigt die Maße, der Umriss geht als exakte Kurve in
den B-Rep-Kern. Ohne OpenCASCADE sagen sie das in einem Satz (§30).

Die Grundformen sind teils bewusst unterbestimmt (der Randpunkt eines Kreises
darf auf seinem Kreis wandern). Das ist hier kein Befund: konstruiert wird
exakt, und ein Hinweis, der bei jeder Grundform erschiene, wäre keiner mehr.
Der Befund über Freiheitsgrade gehört zur gezeichneten Skizze des Editors.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from app.core.brep import edit, profiles
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, require
from app.core.errors import Action, NeedsSolidError, ValidationError
from app.core.geom.boolean import without_effect
from app.core.registry import op_params, param, register_op
from app.core.sketch import shapes
from app.core.sketch.planes import frame_for, frame_of, height_to, is_feature_plane
from app.core.sketch.profile import Profile, profile_of, regions_of, shifted
from app.core.sketch.serialize import sketch_from_text
from app.core.sketch.solver import solve_sketch
from app.core.types import BaseParams, OpContext, OpResult, PlaneFrame, SceneObject
from app.core.units import DEGREE_UNIT
from app.i18n import _

#: Ein Satz, den drei Parameterschemata teilen — deshalb steht er einmal hier.
_LENGTH_DOC = _(
    "Länge in X. Beim Kreis und beim Vieleck ist das der Durchmesser, "
    "beim Langloch die Gesamtlänge über die runden Enden."
)
_WIDTH_DOC = _("Breite in Y. Beim Kreis und beim Vieleck ohne Wirkung.")
_SHAPE_DOC = _("Rechteck, Langloch, Kreis oder Vieleck — die Maße stehen darunter.")
_CORNERS_DOC = _("Zahl der Ecken, nur beim Vieleck.")
_NAME_DOC = _("Wie das Objekt im Baum heißt. Leer heißt: Solidon vergibt einen.")
_SKETCH_DOC = _(
    "Eine gezeichnete Skizze anstelle der Grundform. Leer heißt: die Grundform oben gilt."
)


def _sketch_profile(shape: str, length: float, width: float, corners: int) -> Profile:
    """Grundform → Skizze → Solver → Umriss. Der eine Weg für alle Ops."""
    if shape == "rectangle":
        sketch = shapes.rectangle(length, width)
    elif shape == "slot":
        sketch = shapes.slot(length, width)
    elif shape == "circle":
        sketch = shapes.circle(length)
    elif shape == "polygon":
        sketch = shapes.polygon(length, corners)
    else:
        raise ValidationError(
            "shape",
            _("Diese Grundform gibt es nicht."),
            value=shape,
            constraint="unknown_shape",
        )
    return profile_of(solve_sketch(sketch))


def _drawn_profile(ctx: OpContext, sketch_text: str) -> Profile:
    """Der Umriss der gezeichneten Skizze, gelöst gegen die Projektparameter.

    Ein Maß wie ``=@breite/2`` rechnet hier mit denselben Werten wie überall
    (§13, §30.1)."""
    values = {name: entry.value for name, entry in ctx.scene.parameters.items()}
    return profile_of(solve_sketch(sketch_from_text(sketch_text), values))


def _plane_of(sketch_text: str) -> str:
    """Auf welcher Ebene eine gezeichnete Skizze liegt.

    Ohne gezeichnete Skizze gilt XY: die Grundformen liegen dort, und eine
    Operation ohne Skizze hat keine Ebene zu wählen."""
    if not sketch_text:
        return "plane:xy"
    return sketch_from_text(sketch_text).plane


def _frame_of(ctx: OpContext, plane: str) -> PlaneFrame | None:
    """Der Rahmen einer Flächenebene, sonst nichts.

    ``None`` heißt nicht „unbekannt", sondern „eine der drei Hauptebenen" —
    die kennt der B-Rep-Kern selbst, und ihm die Szene zu reichen, damit er
    nachschlägt, was feststeht, wäre eine Abhängigkeit ohne Gegenwert."""
    if not is_feature_plane(plane):
        return None
    return frame_for(plane, ctx.scene.objects.values())


def _regions_for(
    ctx: OpContext,
    sketch_text: str,
    shape: str,
    length: float,
    width: float,
    corners: int,
    region: int,
) -> list[Profile]:
    """Die Umrisse, die extrudiert werden — einer, oder alle nebeneinander.

    Eine Grundform hat genau einen; eine gezeichnete Skizze kann mehrere
    haben, und dann ist die Frage berechtigt, welcher gemeint ist. Null heißt
    alle: zwei Stege eines Halters sind ein Körper, und wer sie einzeln
    extrudieren müsste, hätte zwei Operationen für eine Handlung (E11).

    Löcher sind keine Regionen — sie hängen an ihrer Außenkontur und wandern
    mit ihr. Eine Nummer zählt deshalb nur die Umrisse, die für sich stehen.
    """
    if not sketch_text:
        return [_sketch_profile(shape, length, width, corners)]
    values = {name: entry.value for name, entry in ctx.scene.parameters.items()}
    found = regions_of(solve_sketch(sketch_from_text(sketch_text), values))
    if region == 0:
        return list(found)
    if region > len(found):
        raise ValidationError(
            "region",
            _("So viele getrennte Umrisse hat diese Skizze nicht."),
            value=region,
            constraint="unknown_region",
            values={"regions": len(found)},
            suggestions=[
                Action(id="sketch.use_all_regions", label=_("Alle Umrisse nehmen"), primary=True)
            ],
        )
    return [found[region - 1]]


def _height_of(
    ctx: OpContext,
    height: float,
    plane: str,
    frame: PlaneFrame | None,
    up_to: str,
) -> float:
    """Die eingetragene Höhe — oder die, die bis zur Zielfläche reicht (D14).

    Zwanzig Millimeter abzumessen und einzutippen ist Arbeit, die die Anwendung
    übernehmen kann, und das Ergebnis hält: wächst der Körper darunter, wächst
    dieser mit. Die Höhe bleibt trotzdem ein eigener Parameter — ohne
    Zielfläche gilt sie, und eine Operation, die zwei Wege je nach Belegung
    geht, ist immer noch **eine** Operation (E11).
    """
    if not up_to:
        return height
    if frame is None:
        # Die Normalen der drei Hauptebenen stehen in ``profiles.PLANES`` — sie
        # hier noch einmal aufzuschreiben hieße, zwei Wahrheiten zu führen.
        # Nur in diesem Zweig nachschlagen: bei einer Flächenebene steht dort
        # nichts, und ein Zugriff davor endete mit einem KeyError.
        frame = frame_of(profiles.PLANES[plane][1], (0.0, 0.0, 0.0))
    target = frame_for(f"feature:{up_to}", ctx.scene.objects.values())
    return height_to(frame, target)


def _profile_for(
    ctx: OpContext, sketch_text: str, shape: str, length: float, width: float, corners: int
) -> Profile:
    """Gezeichnete Skizze, wenn eine da ist — sonst die Grundform."""
    if sketch_text:
        return _drawn_profile(ctx, sketch_text)
    return _sketch_profile(shape, length, width, corners)


def _created(name: str, fallback: str, solid: Solid) -> SceneObject:
    return SceneObject(
        id="", name=name or fallback, mesh=solid, kind="brep", features=features_of(solid)
    )


def _brep_input(ctx: OpContext) -> tuple[SceneObject, Solid]:
    """Die Eingabe und ihr exakter Körper — oder ein Satz, der weiterhilft.

    Kein ``ValidationError``: dessen Titel lautet „Ein Wert liegt außerhalb des
    zulässigen Bereichs", und hier ist kein Wert außerhalb eines Bereichs —
    hier hat der Körper die falsche Art. Im Prüfbericht stand deshalb eine
    Fehlermeldung über Zahlen an einer Stelle, an der keine Zahl schuld war.
    Denselben Weg sind ``brep/ops.py`` und ``export/writer.py`` schon gegangen;
    diese Stelle war beim Umstellen übersehen worden.

    Aufgefallen an ``puppenhaus_fertig``: dort höhlt ``hollow_object`` den
    exakten Körper aus und gibt ein Netz zurück, und die drei Taschen danach
    liefen ins Leere. Der Satz nennt jetzt den Ausweg — ``shell_exact`` hätte
    den Körper exakt gelassen.
    """
    require()
    source = ctx.inputs[0]
    if not isinstance(source.mesh, Solid):
        raise NeedsSolidError(
            # Ohne Platzhalter: TranslatableText löst nur den Katalog auf und
            # formatiert nicht. Der Name reist wie überall in ``values``.
            detail=_(
                "Der gewählte Körper ist ein Netz. Exakte Körper kommen aus einer "
                "STEP-Datei oder aus den Grundformen, deren Name mit Exakt beginnt; "
                "wer aushöhlen muss, nimmt Exakt aushöhlen statt Aushöhlen."
            ),
            values={"name": source.name, "field": "in", "constraint": "needs_brep"},
            object_id=source.id,
        )
    return source, source.mesh


@op_params
class SketchExtrudeParams(BaseParams):
    shape: str = param(
        title=_("Grundform"), default="rectangle", choices=shapes.SHAPE_CHOICES, doc=_SHAPE_DOC
    )
    length: float = param(
        title=_("Länge"), default=40.0, unit="mm", minimum=0.1, maximum=1000.0, doc=_LENGTH_DOC
    )
    width: float = param(
        title=_("Breite"), default=20.0, unit="mm", minimum=0.1, maximum=1000.0, doc=_WIDTH_DOC
    )
    height: float = param(
        title=_("Höhe"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Wie hoch der Körper aufgezogen wird, von Z = 0 nach oben."),
    )
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
    )
    region: int = param(
        title=_("Region"),
        default=0,
        minimum=0,
        maximum=64,
        placement="advanced",
        doc=_(
            "Bei einer Skizze mit mehreren getrennten Umrissen: welcher davon. "
            "Null heißt alle — sie werden zu einem Körper vereinigt."
        ),
    )
    up_to: str = param(
        title=_("Bis zur Fläche"),
        default="",
        placement="advanced",
        doc=_(
            "Statt der Höhe: bis auf die Höhe dieser Fläche. Leer heißt, die "
            "Höhe darüber gilt. Eine angeklickte Fläche trägt sich selbst ein."
        ),
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=_NAME_DOC)
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )


@register_op(
    name="sketch_extrude",
    title=_("Grundform extrudieren"),
    category="sketch",
    params=SketchExtrudeParams,
    consumes=0,
    produces=1,
    doc=_(
        "Zieht eine Grundform senkrecht zu einem Körper auf. Der Umriss kommt "
        "aus einer gelösten Skizze und geht als exakte Kurve in den Kern "
        "— ein Kreis ist wirklich rund."
    ),
)
def sketch_extrude(ctx: OpContext) -> OpResult:
    params = cast(SketchExtrudeParams, ctx.params)
    require()
    plane = _plane_of(params.sketch)
    frame = _frame_of(ctx, plane)
    height = _height_of(ctx, params.height, plane, frame, params.up_to)
    chosen = _regions_for(
        ctx, params.sketch, params.shape, params.length, params.width, params.corners, params.region
    )
    bodies = [profiles.extrude(one, height, plane, frame) for one in chosen]
    solid = bodies[0] if len(bodies) == 1 else edit.boolean("union", bodies)
    return OpResult(outputs=[_created(params.name, str(_("Grundform")), solid)])


@op_params
class SketchPocketParams(BaseParams):
    shape: str = param(
        title=_("Grundform"), default="rectangle", choices=shapes.SHAPE_CHOICES, doc=_SHAPE_DOC
    )
    length: float = param(
        title=_("Länge"), default=20.0, unit="mm", minimum=0.1, maximum=1000.0, doc=_LENGTH_DOC
    )
    width: float = param(
        title=_("Breite"), default=10.0, unit="mm", minimum=0.1, maximum=1000.0, doc=_WIDTH_DOC
    )
    depth: float = param(
        title=_("Tiefe"),
        default=5.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Wie tief die Tasche von ihrer Oberkante nach unten schneidet."),
        depends_on=("through", (False,)),
    )
    through: bool = param(
        title=_("Durchgehend"),
        default=False,
        placement="advanced",
        doc=_("Schneidet durch die ganze Höhe des Körpers — die Tiefe zählt dann nicht."),
    )
    x: float = param(
        title=_("X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Mitte der Tasche in X. Eine angeklickte Fläche trägt den Ort selbst ein."),
    )
    y: float = param(
        title=_("Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Mitte der Tasche in Y. Eine angeklickte Fläche trägt den Ort selbst ein."),
    )
    z: float = param(
        title=_("Oberkante"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Wo die Tasche oben beginnt. Null heißt: an der Oberseite des Körpers."),
    )
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
    )
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )


@register_op(
    name="sketch_pocket",
    requires_kind="brep",
    title=_("Tasche schneiden"),
    category="sketch",
    params=SketchPocketParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
    doc=_(
        "Schneidet eine Grundform als Tasche in einen B-Rep-Körper — von der "
        "Oberkante senkrecht nach unten, auf Wunsch durchgehend. Ein Klick auf "
        "eine Fläche trägt den Ort vorab ein."
    ),
)
def sketch_pocket(ctx: OpContext) -> OpResult:
    params = cast(SketchPocketParams, ctx.params)
    source, body = _brep_input(ctx)
    profile = shifted(
        _profile_for(ctx, params.sketch, params.shape, params.length, params.width, params.corners),
        params.x,
        params.y,
    )
    _, _, zmin, _, _, zmax = profiles.bounds(body)
    top = params.z if abs(params.z) > 1e-9 else zmax
    if params.through:
        bottom, reach = zmin - 1.0, (zmax - zmin) + 2.0
    else:
        bottom, reach = top - params.depth, params.depth + 1.0
    tool = edit.moved(profiles.extrude(profile, reach), (0.0, 0.0, bottom))
    solid = edit.boolean("difference", [body, tool])
    # Eine Tasche, die den Körper verfehlt, lief stumm durch: im Verlauf ein
    # Schritt, im Bild dasselbe Teil, und keine Zeile, die das erklärt.
    # Gemessen an vier Fällen — Oberkante unter dem Körper, Ort daneben —, und
    # in allen vieren sagte niemand etwas. Denselben Satz bekommt seit je, wer
    # eine Magnettasche daneben setzt (`geom/boolean.without_effect`).
    nothing = without_effect(body, solid, "difference")
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=solid, kind="brep", features=features_of(solid))],
        findings=[nothing] if nothing is not None else [],
    )


@op_params
class SketchRevolveParams(BaseParams):
    shape: str = param(
        title=_("Grundform"), default="rectangle", choices=shapes.SHAPE_CHOICES, doc=_SHAPE_DOC
    )
    length: float = param(
        title=_("Länge"),
        default=5.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_(
            "Ausdehnung des Querschnitts von der Achse weg. Beim Kreis und "
            "Vieleck ist das der Durchmesser."
        ),
    )
    width: float = param(
        title=_("Breite"),
        default=8.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Höhe des Querschnitts entlang der Achse. Beim Kreis ohne Wirkung."),
    )
    offset: float = param(
        title=_("Abstand zur Achse"),
        default=10.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        doc=_(
            "Abstand der Innenkante des Querschnitts von der Drehachse. "
            "Null macht den Körper voll bis zur Mitte."
        ),
    )
    angle: float = param(
        title=_("Winkel"),
        default=360.0,
        unit=DEGREE_UNIT,
        minimum=1.0,
        maximum=360.0,
        placement="advanced",
        doc=_("Wie weit um die Achse gedreht wird. 360 schließt den Körper."),
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=_NAME_DOC)
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
    )
    sketch: str = param(
        title=_("Skizze"),
        default="",
        kind="sketch",
        placement="advanced",
        doc=_(
            "Eine gezeichnete Skizze als Querschnitt, benutzt wie gezeichnet: "
            "x ist der Abstand von der Achse, y die Höhe — der Abstand oben "
            "gilt dann nicht."
        ),
    )


@register_op(
    name="sketch_revolve",
    title=_("Rotationskörper aufziehen"),
    category="sketch",
    params=SketchRevolveParams,
    consumes=0,
    produces=1,
    doc=_(
        "Dreht einen Querschnitt um die senkrechte Achse: ein Rechteck wird "
        "zur Hülse, ein Kreis zum Ring. Der Körper steht auf Z = 0."
    ),
)
def sketch_revolve(ctx: OpContext) -> OpResult:
    params = cast(SketchRevolveParams, ctx.params)
    require()
    if params.sketch:
        # Wie gezeichnet: die Skizze kennt ihren Abstand zur Achse selbst.
        placed = _drawn_profile(ctx, params.sketch)
    else:
        profile = _sketch_profile(params.shape, params.length, params.width, params.corners)
        rise = params.length / 2.0 if params.shape in ("circle", "polygon") else params.width / 2.0
        placed = shifted(profile, params.offset + params.length / 2.0, rise)
    solid = profiles.revolve(placed, params.angle)
    return OpResult(outputs=[_created(params.name, str(_("Rotationskörper")), solid)])


@op_params
class SketchSweepParams(BaseParams):
    shape: str = param(
        title=_("Grundform"), default="circle", choices=shapes.SHAPE_CHOICES, doc=_SHAPE_DOC
    )
    length: float = param(
        title=_("Länge"), default=10.0, unit="mm", minimum=0.1, maximum=1000.0, doc=_LENGTH_DOC
    )
    width: float = param(
        title=_("Breite"), default=10.0, unit="mm", minimum=0.1, maximum=1000.0, doc=_WIDTH_DOC
    )
    bend_radius: float = param(
        title=_("Bogenradius"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_(
            "Radius des Pfades, dem der Querschnitt folgt. Er muss größer sein "
            "als der halbe Querschnitt, sonst knickt die Innenseite."
        ),
    )
    bend_angle: float = param(
        title=_("Bogenwinkel"),
        default=90.0,
        unit=DEGREE_UNIT,
        minimum=1.0,
        maximum=180.0,
        doc=_("Wie weit der Bogen führt — 90 Grad ist ein rechtwinkliger Rohrbogen."),
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=_NAME_DOC)
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
    )
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )


@register_op(
    name="sketch_sweep",
    title=_("Entlang eines Bogens führen"),
    category="sketch",
    params=SketchSweepParams,
    consumes=0,
    produces=1,
    doc=_(
        "Führt einen Querschnitt entlang eines Bogens: senkrecht startend, mit "
        "dem Bogenradius zur Seite kippend — ein Rohrbogen in einem Schritt."
    ),
)
def sketch_sweep(ctx: OpContext) -> OpResult:
    params = cast(SketchSweepParams, ctx.params)
    require()
    profile = _profile_for(
        ctx, params.sketch, params.shape, params.length, params.width, params.corners
    )
    solid = profiles.sweep_arc(profile, params.bend_radius, params.bend_angle)
    return OpResult(outputs=[_created(params.name, str(_("Bogen")), solid)])


@op_params
class SketchLoftParams(BaseParams):
    shape: str = param(
        title=_("Grundform"), default="rectangle", choices=shapes.SHAPE_CHOICES, doc=_SHAPE_DOC
    )
    length: float = param(
        title=_("Länge"), default=40.0, unit="mm", minimum=0.1, maximum=1000.0, doc=_LENGTH_DOC
    )
    width: float = param(
        title=_("Breite"), default=20.0, unit="mm", minimum=0.1, maximum=1000.0, doc=_WIDTH_DOC
    )
    height: float = param(
        title=_("Höhe"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Abstand zwischen unterem und oberem Umriss."),
    )
    top_scale: float = param(
        title=_("Verjüngung"),
        default=0.5,
        minimum=0.05,
        maximum=2.0,
        doc=_(
            "Größe des oberen Umrisses im Verhältnis zum unteren. 0,5 halbiert "
            "ihn — ein Pyramiden- oder Kegelstumpf; über 1 wird es oben weiter."
        ),
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=_NAME_DOC)
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
    )


@register_op(
    name="sketch_loft",
    title=_("Zwischen zwei Umrissen aufspannen"),
    category="sketch",
    params=SketchLoftParams,
    consumes=0,
    produces=1,
    doc=_(
        "Spannt einen Körper zwischen der Grundform und ihrer verkleinerten "
        "Kopie in der Höhe auf — Pyramidenstumpf, Kegelstumpf, Trichter."
    ),
)
def sketch_loft(ctx: OpContext) -> OpResult:
    params = cast(SketchLoftParams, ctx.params)
    require()
    bottom = _sketch_profile(params.shape, params.length, params.width, params.corners)
    top = _sketch_profile(
        params.shape,
        params.length * params.top_scale,
        params.width * params.top_scale,
        params.corners,
    )
    solid = profiles.loft(bottom, top, params.height)
    return OpResult(outputs=[_created(params.name, str(_("Übergang")), solid)])


# --- Fläche versetzen (Konzept P15 §7 Etappe 6, D10) ----------------------------


@op_params
class PushFaceParams(BaseParams):
    distance: float = param(
        title=_("Weg"),
        default=2.0,
        unit="mm",
        doc=_(
            "Wie weit die Fläche wandert. Positiv nach außen, negativ hinein — "
            "dasselbe Werkzeug für beides."
        ),
    )
    nx: float = param(
        title=_("Richtung X"),
        default=0.0,
        doc=_(
            "Welche Flächen bewegt werden: die, deren Normale hierhin zeigt. Eine "
            "angeklickte Fläche trägt die Richtung selbst ein."
        ),
    )
    ny: float = param(
        title=_("Richtung Y"),
        default=0.0,
        doc=_("Zweite Achse der Richtung — siehe Richtung X."),
    )
    nz: float = param(
        title=_("Richtung Z"),
        default=1.0,
        doc=_("Dritte Achse der Richtung. Vorgabe ist nach oben."),
    )


@register_op(
    name="push_face",
    requires_kind="brep",
    title=_("Fläche versetzen"),
    category="shaping",
    params=PushFaceParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
    doc=_(
        "Greift eine Fläche und verschiebt sie entlang ihrer Normalen; die "
        "Nachbarwände wachsen mit. Der Weg, eine Wand zu ändern, ohne die "
        "Operation zu suchen, die sie erzeugt hat — bei einem importierten STEP "
        "gibt es keine."
    ),
)
def push_face(ctx: OpContext) -> OpResult:
    """Press/Pull auf dem exakten Kern."""
    params = cast(PushFaceParams, ctx.params)
    source, solid = _brep_input(ctx)
    moved = profiles.push_faces(solid, (params.nx, params.ny, params.nz), params.distance)
    return OpResult(outputs=[dataclasses.replace(source, mesh=moved, features={})])
