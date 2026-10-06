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
import math
from typing import Any, cast

from app.core.brep import edit, profiles
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, require
from app.core.errors import (
    CANCEL,
    CORRECT_INPUT,
    Action,
    GeometryError,
    InternalError,
    ValidationError,
)
from app.core.geom.boolean import fell_apart, without_effect
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.sketch import planes, shapes
from app.core.sketch.planes import (
    feature_plane_parts,
    frame_for,
    frame_for_sketch,
    frame_of,
    height_to,
    is_derived_plane,
    is_feature_plane,
)
from app.core.sketch.profile import (
    PROFILE_REVISION,
    Profile,
    ProfileSegment,
    arc_through,
    bounds_of,
    crosses_itself,
    path_of,
    profile_of,
    regions_of,
    scaled,
    shifted,
    signed_area,
    spline_controls,
)
from app.core.sketch.serialize import sketch_from_text
from app.core.sketch.solver import solve_sketch
from app.core.types import (
    BaseParams,
    CancelToken,
    Finding,
    OpContext,
    OpResult,
    PlaneFrame,
    Point2,
    SceneObject,
    SolvedSketch,
    SolverInfo,
)
from app.core.units import DEGREE_UNIT, EPS_GEOM, is_close, positive_axis
from app.i18n import _

#: Ein Satz, den drei Parameterschemata teilen — deshalb steht er einmal hier.
_LENGTH_DOC = _(
    "Länge in X. Beim Kreis und beim Vieleck ist das der Durchmesser, "
    "beim Langloch die Gesamtlänge über die runden Enden."
)
#: Derselbe Satz, wo auch die Lochbilder zur Wahl stehen — sie nehmen dasselbe Feld.
_PATTERN_LENGTH_DOC = _(
    "Länge in X. Beim Kreis und beim Vieleck ist das der Durchmesser, "
    "beim Langloch die Gesamtlänge über die runden Enden, beim Lochkreis der "
    "Teilkreisdurchmesser und beim Lochraster der Abstand von Mitte zu Mitte."
)
_WIDTH_DOC = _("Breite in Y. Beim Kreis und beim Vieleck ohne Wirkung.")
_SHAPE_DOC = _("Rechteck, Langloch, Kreis oder Vieleck — die Maße stehen darunter.")
#: Wo die zwei Muster zur Wahl stehen, nennt der Satz sie mit.
_SHAPE_AND_PATTERN_DOC = _(
    "Rechteck, Langloch, Kreis, Vieleck — oder ein Lochbild: Lochkreis und "
    "Lochraster geben so viele Löcher, wie darunter eingestellt sind."
)
_CORNERS_DOC = _("Zahl der Ecken, nur beim Vieleck.")
_COUNT_DOC = _("Zahl der Löcher auf dem Teilkreis, nur beim Lochkreis.")
_COLUMNS_DOC = _("Löcher in x-Richtung, nur beim Lochraster.")
_ROWS_DOC = _("Löcher in y-Richtung, nur beim Lochraster.")
_HOLE_DIAMETER_DOC = _("Durchmesser jedes einzelnen Lochs, beim Lochkreis und beim Lochraster.")
_SKETCH_DOC = _(
    "Eine gezeichnete Skizze anstelle der Grundform. Leer heißt: die Grundform oben gilt."
)
#: Was die drei Schnitte mit Werkzeug an einem eingelesenen Netz anders machen.
#: Ein Satz für alle drei, weil es für alle drei derselbe Unterschied ist: Das
#: Werkzeug wird mit ``units.MAX_FACET_SAG`` vernetzt, derselben Grenze, mit
#: der der exakte Kern tesselliert (``operationen.md``: ein Unterschied, den
#: man benennt, ist eine Eigenschaft).
_MESH_CUT_CAVEAT = _(
    "An einem eingelesenen Netz besteht der Schnitt aus geraden Stücken statt aus "
    "Kurven. Sie weichen um weniger ab, als eine Düse auflöst; wer echte Kurven braucht, "
    "arbeitet an einem exakten Körper weiter."
)
#: Die drei Koordinaten eines Achspunkts sagen dasselbe — ein Satz für alle drei.
_AXIS_POINT_DOC = _(
    "Ein Punkt auf der Drehachse; auf seiner Höhe entlang der Achse beginnt der "
    "Querschnitt. Mit einem gewählten Merkmal zählt nur noch diese Höhe."
)


@dataclasses.dataclass(frozen=True)
class _Pattern:
    """Die Zahlen eines Lochbilds — was Lochkreis und Lochraster zusätzlich brauchen.

    Sie reisen zusammen, weil sie zusammen gebraucht werden: ``_regions_for``
    trägt schon acht Stellen, und vier weitere Zahlen einzeln durchzureichen
    hieße, drei Aufrufe anzufassen, die von Lochbildern nichts wissen.
    """

    count: int
    columns: int
    rows: int
    hole_diameter: float


def _pattern_of(params: RaisedOutlineParams | SketchPocketParams) -> _Pattern:
    """Die vier Lochbildzahlen aus dem Schema, das sie trägt."""
    return _Pattern(params.count, params.columns, params.rows, params.hole_diameter)


def _pattern_profiles(shape: str, length: float, pattern: _Pattern) -> list[Profile]:
    """Ein Lochbild — jedes Loch ein eigener Umriss, keiner im anderen.

    ``length`` trägt auch hier das Hauptmaß: beim Lochkreis den
    Teilkreisdurchmesser, beim Raster den Abstand von Mitte zu Mitte. Dasselbe
    Feld, in dem beim Kreis der Durchmesser steht — ein zweites daneben wäre
    ein zweiter Ort für dieselbe Sache.
    """
    if shape == "bolt_circle":
        sketch = shapes.bolt_circle(length, pattern.count, pattern.hole_diameter)
    else:
        sketch = shapes.hole_grid(pattern.columns, pattern.rows, length, pattern.hole_diameter)
    return list(regions_of(solve_sketch(sketch)))


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


def _parameter_values(ctx: OpContext) -> dict[str, float]:
    """Die aufgelösten Projektparameter — für die Maße der Zeichnung und ihre Ebene."""
    return {name: entry.value for name, entry in ctx.scene.parameters.items()}


#: Bedingungen, die ein **Maß** tragen — Länge, Radius, Durchmesser, Winkel.
#: Deckung, Richtung und Gleichheit sind Beziehungen und keine Maße.
_MEASURE_KINDS = frozenset({"distance", "radius", "diameter", "angle"})


def _solved_drawing(ctx: OpContext, sketch_text: str, findings: list[Finding]) -> SolvedSketch:
    """Löst eine Zeichnung einmal und nimmt ihre freien Maße in den Bericht mit.

    **Nur an einer bemaßten Zeichnung** (KUNDE-08, entschieden in der
    Durchsicht v0.5.1): Wer kein einziges Maß angelegt hat, zeichnet frei und
    druckt, was er sieht — genau das, was der Satz verspricht. Nach jeder
    freien Zeichnung stand er sonst im Prüfbericht und las sich wie ein
    Mangel. Wer bemaßt hat, will eine bestimmte Form; ihm sagt er, dass noch
    etwas wandern kann. Der Skizzeneditor zeigt die offenen Maße ohnehin.
    """
    values = _parameter_values(ctx)
    sketch = sketch_from_text(sketch_text)
    solved = solve_sketch(sketch, values)
    measured = any(
        entry.kind in _MEASURE_KINDS and str(entry.value).strip() for entry in sketch.constraints
    )
    if solved.free_dof > 0 and measured:
        findings.append(
            Finding(
                code="sketch.underconstrained",
                severity="info",
                message=_(
                    "Nicht jedes Maß der Zeichnung ist festgelegt, gedruckt wird sie wie "
                    "gezeichnet. Feste Maße setzt der Skizzeneditor."
                ),
                values={"free_dof": solved.free_dof},
            )
        )
    return solved


def _drawn_profile(ctx: OpContext, sketch_text: str, findings: list[Finding]) -> Profile:
    """Der Umriss der gezeichneten Skizze, gelöst gegen die Projektparameter.

    Ein Maß wie ``=@breite/2`` rechnet hier mit denselben Werten wie überall
    (§13, §30.1)."""
    return profile_of(_solved_drawing(ctx, sketch_text, findings))


def _plane_of(sketch_text: str) -> str:
    """Auf welcher Ebene eine gezeichnete Skizze liegt.

    Ohne gezeichnete Skizze gilt XY: die Grundformen liegen dort, und eine
    Operation ohne Skizze hat keine Ebene zu wählen."""
    if not sketch_text:
        return "plane:xy"
    return sketch_from_text(sketch_text).plane


def _frame_of(ctx: OpContext, plane: str) -> PlaneFrame | None:
    """Der Rahmen jeder Ebene, die der B-Rep-Kern nicht selbst kennt.

    ``None`` heißt nicht „unbekannt", sondern „eine der drei Hauptebenen" —
    die kennt der B-Rep-Kern selbst, und ihm die Szene zu reichen, damit er
    nachschlägt, was feststeht, wäre eine Abhängigkeit ohne Gegenwert.

    **Eine abgeleitete Ebene gehört ausdrücklich dazu** (§30.1): Sie steht in
    keiner Tabelle des Kerns, und ohne diesen Rahmen läge die Zeichnung auf
    der Grundebene statt zwanzig Millimeter darüber — der Vertrag wäre eine
    Angabe, die niemand einlöst. Ihr Abstand darf ein Projektparameter sein,
    deshalb reisen die Werte mit."""
    if not (is_feature_plane(plane) or is_derived_plane(plane)):
        return None
    return frame_for_sketch(plane, ctx.scene.objects.values(), _parameter_values(ctx))


def _regions_for(
    ctx: OpContext,
    sketch_text: str,
    shape: str,
    length: float,
    width: float,
    corners: int,
    region: int,
    findings: list[Finding],
    pattern: _Pattern | None = None,
) -> list[Profile]:
    """Die Umrisse, die extrudiert werden — einer, oder alle nebeneinander.

    Eine Grundform hat genau einen; eine gezeichnete Skizze kann mehrere
    haben, und dann ist die Frage berechtigt, welcher gemeint ist. Null heißt
    alle: zwei Stege eines Halters sind ein Körper, und wer sie einzeln
    extrudieren müsste, hätte zwei Operationen für eine Handlung (E11).

    Löcher sind keine Regionen — sie hängen an ihrer Außenkontur und wandern
    mit ihr. Eine Nummer zählt deshalb nur die Umrisse, die für sich stehen.

    Ein **Lochbild** ist der dritte Fall: Es kommt ohne Zeichnung und bringt
    trotzdem viele Umrisse mit. ``pattern`` reichen nur die zwei Operationen
    herein, die damit umgehen — Hochziehen und Tasche.
    """
    if not sketch_text:
        if pattern is not None and shape in shapes.PATTERN_CHOICES:
            return _pattern_profiles(shape, length, pattern)
        return [_sketch_profile(shape, length, width, corners)]
    found = regions_of(_solved_drawing(ctx, sketch_text, findings))
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


def _along(point: tuple[float, float, float], normal: tuple[float, float, float]) -> float:
    """Wo ein Punkt entlang einer Normalen liegt — das Lot auf die Achse."""
    return point[0] * normal[0] + point[1] * normal[1] + point[2] * normal[2]


def _span_along(body: Any, normal: tuple[float, float, float]) -> tuple[float, float]:
    """Wie weit ein Körper entlang dieser Normalen reicht.

    Aus den acht Ecken des Hüllquaders — für die Tasche genügt das: Sie
    braucht eine Ober- und eine Durchstoßgrenze, keine exakte Silhouette.

    **Beide Arten von Körper.** Der exakte kennt seine Grenzen über den Kern,
    ein Netz über ``bounds``; die Rechnung darüber ist dieselbe, und die Tasche
    hat keinen Grund, sie zweimal zu führen.
    """
    if isinstance(body, Solid):
        xmin, ymin, zmin, xmax, ymax, zmax = profiles.bounds(body)
    else:
        box = body.bounds
        (xmin, ymin, zmin), (xmax, ymax, zmax) = box.minimum, box.maximum
    marks = [
        _along((x, y, z), normal) for x in (xmin, xmax) for y in (ymin, ymax) for z in (zmin, zmax)
    ]
    return min(marks), max(marks)


def _is_the_drawing_face(plane: str, up_to: str) -> bool:
    """Ob „Bis zur Fläche" die Fläche nennt, auf der die Zeichnung liegt.

    Verglichen werden Körper und Merkmal der beiden Angaben; eine alte Angabe
    ohne Körper (``face_7``) trifft jede gleichnamige Fläche, so wie
    :func:`~app.core.sketch.planes.frame_for` sie liest.
    """
    if not is_feature_plane(plane):
        return False
    drawn_on, drawn_face = feature_plane_parts(plane)
    target_on, target_face = feature_plane_parts(f"feature:{up_to}")
    if drawn_face != target_face:
        return False
    return not drawn_on or not target_on or drawn_on == target_on


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
    if _is_the_drawing_face(plane, up_to):
        # **Die Zeichenfläche ist kein Ziel** (Bedienabnahme Zeichnen, F1).
        # Von der eigenen Fläche aus gibt es kein Vorwärts; der Satz über eine
        # Fläche „hinter der Skizze" nannte eine Lage, die der Kunde nie
        # gewählt hatte — er hatte auf ihr gezeichnet.
        raise ValidationError(
            "up_to",
            _(
                "Das Ziel ist die Fläche, auf der gezeichnet wird. "
                "Tragen Sie eine Höhe ein oder wählen Sie eine andere Fläche."
            ),
            value=up_to,
            constraint="drawing_face",
            suggestions=[
                Action(
                    id="sketch.clear_up_to",
                    label=_("Die Höhe wieder als Zahl eintragen"),
                    primary=True,
                ),
                Action(id="sketch.pick_face", label=_("Eine andere Zielfläche wählen")),
            ],
        )
    if frame is None:
        # Die Normalen der drei Hauptebenen stehen in ``profiles.PLANES`` — sie
        # hier noch einmal aufzuschreiben hieße, zwei Wahrheiten zu führen.
        # Nur in diesem Zweig nachschlagen: bei einer Flächenebene steht dort
        # nichts, und ein Zugriff davor endete mit einem KeyError.
        frame = frame_of(profiles.PLANES[plane][1], (0.0, 0.0, 0.0))
    target = frame_for(
        f"feature:{up_to}",
        ctx.scene.objects.values(),
        field="up_to",
        suggestions=[
            Action(id="sketch.pick_face", label=_("Eine andere Zielfläche wählen"), primary=True),
            Action(id="sketch.clear_up_to", label=_("Die Höhe wieder als Zahl eintragen")),
        ],
    )
    return height_to(frame, target)


def _profile_for(
    ctx: OpContext,
    sketch_text: str,
    shape: str,
    length: float,
    width: float,
    corners: int,
    findings: list[Finding],
) -> Profile:
    """Gezeichnete Skizze, wenn eine da ist — sonst die Grundform."""
    if sketch_text:
        return _drawn_profile(ctx, sketch_text, findings)
    return _sketch_profile(shape, length, width, corners)


def _created(
    name: str,
    fallback: str,
    solid: Solid,
    *,
    cancelled: CancelToken,
    findings: list[Finding],
) -> SceneObject:
    """Das Ergebnis als Szenenobjekt — nachdem feststeht, dass eines da ist.

    Alle vier Erzeuger-Ops laufen hier durch. Ein Ergebnis ohne Körper wurde
    vorher trotzdem Objekt: unsichtbar, Volumen null, und jeder spätere
    Schritt darauf scheiterte weit weg von der Ursache (Gesamtreview D-8).

    **Ein undichter Körper wird genannt** (RM-391). Ein gestreckter Linienzug
    kam undicht heraus, und der Prüfbericht sprach nur von offenen Maßen; der
    Kunde fand es erst im Slicer. Die Kennung ist dieselbe wie nach jeder
    anderen Operation (``mesh.not_watertight``) — mit denselben zwei Wegen und
    gestrichen, sobald ein späterer Schritt den Körper schließt.
    """
    if solid.solid_count < 1 or solid.volume <= EPS_GEOM:
        raise GeometryError(
            _("Aus dieser Skizze wird kein Körper."),
            _(
                "Das Ergebnis hat kein Volumen — meist ist der Umriss zu klein "
                "oder in sich zusammengefallen."
            ),
            suggestions=(
                Action("open_sketch", _("Skizze ansehen"), primary=True),
                CORRECT_INPUT,
            ),
        )
    if not solid.is_watertight:
        findings.append(
            Finding(
                code="mesh.not_watertight",
                severity="warning",
                message=_(
                    "Der Körper aus der Zeichnung ist nicht geschlossen — "
                    "„Reparieren“ schließt die offenen Stellen."
                ),
                values={"triangles": solid.triangle_count},
            )
        )
    return SceneObject(
        id="",
        name=name or fallback,
        mesh=solid,
        kind="brep",
        features=features_of(solid, cancelled=cancelled),
    )


@op_params
class RaisedOutlineParams(BaseParams):
    """Was beim Hochziehen eines Umrisses gilt — gleich, ob daraus ein neuer
    Körper wird (``sketch_extrude``) oder ob er an einen vorhandenen wächst
    (``sketch_join``). Öffentlich aus demselben Grund wie
    ``PositionedPrimitiveParams``: Der Umschalter zwischen beiden Arten im
    Dialog darf keine Zahl verlieren, und das hält nur ein gemeinsames Schema.
    """

    shape: str = param(
        title=_("Grundform"),
        default="rectangle",
        choices=shapes.SHAPE_AND_PATTERN_CHOICES,
        doc=_SHAPE_AND_PATTERN_DOC,
        placement="advanced",
    )
    length: float = param(
        title=_("Länge"),
        default=40.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_PATTERN_LENGTH_DOC,
        placement="advanced",
    )
    width: float = param(
        title=_("Breite"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
        placement="advanced",
    )
    height: float = param(
        title=_("Höhe"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Wie hoch der Körper gezogen wird, vom Druckbett nach oben."),
    )
    count: int = param(
        title=_("Löcher"),
        default=6,
        minimum=2,
        maximum=200,
        doc=_COUNT_DOC,
        depends_on=("shape", ("bolt_circle",)),
        placement="advanced",
    )
    columns: int = param(
        title=_("Spalten"),
        default=4,
        minimum=1,
        maximum=100,
        doc=_COLUMNS_DOC,
        depends_on=("shape", ("hole_grid",)),
        placement="advanced",
    )
    rows: int = param(
        title=_("Zeilen"),
        default=3,
        minimum=1,
        maximum=100,
        doc=_ROWS_DOC,
        depends_on=("shape", ("hole_grid",)),
        placement="advanced",
    )
    hole_diameter: float = param(
        title=_("Loch-Ø"),
        default=4.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_HOLE_DIAMETER_DOC,
        depends_on=("shape", ("bolt_circle", "hole_grid")),
        placement="advanced",
    )
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
        depends_on=("shape", ("polygon",)),
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
        zero_text=_("alle", context="Nullwert"),
    )
    up_to: str = param(
        title=_("Bis zur Fläche"),
        default="",
        placement="advanced",
        targets_feature=True,
        doc=_(
            "Statt der Höhe: bis auf die Höhe dieser Fläche. Leer heißt, die "
            "Höhe darüber gilt. Eine angeklickte Fläche trägt sich selbst ein."
        ),
    )
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )


@op_params
class SketchExtrudeParams(RaisedOutlineParams):
    name: str = param(title=_("Name"), default="", placement="advanced", doc=NAME_DOC)


@register_op(
    name="sketch_extrude",
    title=_("Grundform hochziehen"),
    category="sketch",
    cache_version=PROFILE_REVISION,
    params=SketchExtrudeParams,
    consumes=0,
    produces=1,
    doc=_(
        "Zieht eine Grundform oder eine Zeichnung senkrecht zu einem Körper hoch. "
        "Rundungen bleiben echte Kurven — ein Kreis ist wirklich rund."
    ),
)
def sketch_extrude(ctx: OpContext) -> OpResult:
    params = cast(SketchExtrudeParams, ctx.params)
    findings: list[Finding] = []
    require()
    plane = _plane_of(params.sketch)
    frame = _frame_of(ctx, plane)
    height = _height_of(ctx, params.height, plane, frame, params.up_to)
    chosen = _regions_for(
        ctx,
        params.sketch,
        params.shape,
        params.length,
        params.width,
        params.corners,
        params.region,
        findings,
        _pattern_of(params),
    )
    bodies = [profiles.extrude(one, height, plane, frame) for one in chosen]
    solid = bodies[0] if len(bodies) == 1 else edit.boolean("union", bodies)
    return OpResult(
        outputs=[
            _created(
                params.name, str(_("Grundform")), solid, cancelled=ctx.cancelled, findings=findings
            )
        ],
        findings=findings,
    )


@op_params
class SketchJoinParams(RaisedOutlineParams):
    """Dieselben Felder wie beim Hochziehen, ohne Namen: Der Körper, an den
    angefügt wird, behält seinen."""


@register_op(
    name="sketch_join",
    title=_("An Körper anfügen"),
    category="sketch",
    params=SketchJoinParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
    doc=_(
        "Zieht den Umriss hoch und verbindet ihn mit dem gewählten Körper — "
        "ein Körper, ein Schritt. Ein exakter Körper bleibt exakt, ein "
        "eingelesenes Netz bleibt ein Netz."
    ),
    caveat=_(
        "Nicht für ein eigenes Teil: Soll das Hochgezogene ein zweiter Körper werden, "
        "nehmen Sie „Grundform hochziehen“."
    ),
)
def sketch_join(ctx: OpContext) -> OpResult:
    """Der Zapfen auf der Platte als **ein** Körper (Bedienabnahme Zeichnen, E4).

    ``sketch_extrude`` erzeugt immer einen neuen Körper; ein Zapfen auf einer
    Platte war danach ein zweiter, überlappender, und wer einen wollte, musste
    *Vereinigen* finden. Fusion bietet „Verbinden" im selben Dialog — hier ist
    es die zweite Art derselben Gruppe, mit derselben Rechnung für den
    Umriss und dem Eingang, den ``sketch_pocket`` auch hat.
    """
    params = cast(SketchJoinParams, ctx.params)
    findings: list[Finding] = []
    plane = _plane_of(params.sketch)
    frame = _frame_of(ctx, plane)
    height = _height_of(ctx, params.height, plane, frame, params.up_to)
    chosen = _regions_for(
        ctx,
        params.sketch,
        params.shape,
        params.length,
        params.width,
        params.corners,
        params.region,
        findings,
        _pattern_of(params),
    )
    source = ctx.inputs[0]
    body = source.mesh
    solver: Any = None
    if isinstance(body, Solid):
        tools = []
        for one in chosen:
            ctx.cancelled.raise_if_cancelled()
            tools.append(profiles.extrude(one, height, plane, frame))
        joined: Any = edit.boolean("union", [body, *tools])
        output = dataclasses.replace(
            source,
            mesh=joined,
            kind="brep",
            features=features_of(joined, cancelled=ctx.cancelled),
        )
    else:
        on = frame if frame is not None else planes.frame_for_plane(plane)
        assert on is not None, f"{plane} steht in PLANES, aber nicht in frame_for_plane"
        output, solver, chain = _join_in_mesh(ctx, source, chosen, on, height)
        findings.extend(chain)
        joined = output.mesh
    apart = fell_apart(
        body,
        joined,
        applies=True,
        code="sketch.join_apart",
        message=lambda _loose: _(
            "Der Umriss berührt den Körper nicht und steht als loses Stück daneben. "
            "Zeichnen Sie auf einer Fläche des Körpers oder nehmen Sie "
            "„Grundform hochziehen“."
        ),
    )
    nothing = without_effect(body, joined, "union", ctx.profile)
    return OpResult(
        outputs=[output],
        findings=[*findings, *(entry for entry in (apart, nothing) if entry is not None)],
        solver=solver,
    )


def _join_in_mesh(
    ctx: OpContext,
    source: SceneObject,
    regions: list[Profile],
    frame: PlaneFrame,
    height: float,
) -> tuple[SceneObject, Any, list[Finding]]:
    """Dasselbe Anfügen an einem Netz — über die Boolesche Rückfallkette.

    **Das Werkzeug beginnt ein Stück im Körper.** Ein Zapfen, der genau auf
    der Fläche aufsitzt, berührt sie nur; die Vereinigung zweier Netze, die
    sich in einer Ebene treffen, ist dort nicht entschieden und ließ je nach
    Stufe eine Naht oder zwei Teile stehen. ``BOOLEAN_OVERLAP`` in den Körper
    hinein ändert am Ergebnis nichts, was man sieht oder druckt — dasselbe
    Maß, mit dem die Tasche durchgehend durchtrennt.
    """
    from app.core.geom import boolean as mesh_boolean
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.geom.mesh import MeshData
    from app.core.geom.sketch_solid import extrude_profile

    sunk = dataclasses.replace(
        frame,
        origin=(
            frame.origin[0] - frame.normal[0] * BOOLEAN_OVERLAP,
            frame.origin[1] - frame.normal[1] * BOOLEAN_OVERLAP,
            frame.origin[2] - frame.normal[2] * BOOLEAN_OVERLAP,
        ),
    )
    tools = []
    for one in regions:
        ctx.cancelled.raise_if_cancelled()
        try:
            tools.append(MeshData.of(extrude_profile(one, height + BOOLEAN_OVERLAP, sunk)))
        except ValueError as problem:
            raise GeometryError(
                detail=_("Aus diesem Umriss entsteht kein Körper."),
                suggestions=(CORRECT_INPUT,),
                values={"reason": str(problem)},
            ) from problem
    if not tools:
        raise GeometryError(
            detail=_("Die Zeichnung enthält keinen geschlossenen Umriss."),
            suggestions=(CORRECT_INPUT,),
        )
    outcome = mesh_boolean.boolean(
        "union",
        # Der Aufrufer hat an der Weiche geprüft, dass hier kein exakter Körper liegt.
        [cast(MeshData, source.mesh), *tools],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )
    # Leeres Wörterbuch, nicht die alten Merkmale: Der Aufsatz hat Flächen
    # verändert, auf die sie zeigten.
    output = dataclasses.replace(source, mesh=outcome.mesh, features={})
    return output, outcome.solver, list(outcome.findings)


@op_params
class SketchPocketParams(BaseParams):
    shape: str = param(
        title=_("Grundform"),
        default="rectangle",
        choices=shapes.SHAPE_AND_PATTERN_CHOICES,
        doc=_SHAPE_AND_PATTERN_DOC,
        placement="advanced",
    )
    length: float = param(
        title=_("Länge"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_PATTERN_LENGTH_DOC,
        placement="advanced",
    )
    width: float = param(
        title=_("Breite"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
        placement="advanced",
    )
    # Vor der Tiefe und vorn: Der Haken schaltet sie aus (``depends_on``).
    through: bool = param(
        title=_("Durchgehend"),
        default=False,
        doc=_("Schneidet durch die ganze Höhe des Körpers — die Tiefe zählt dann nicht."),
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
    count: int = param(
        title=_("Löcher"),
        default=6,
        minimum=2,
        maximum=200,
        doc=_COUNT_DOC,
        depends_on=("shape", ("bolt_circle",)),
        placement="advanced",
    )
    columns: int = param(
        title=_("Spalten"),
        default=4,
        minimum=1,
        maximum=100,
        doc=_COLUMNS_DOC,
        depends_on=("shape", ("hole_grid",)),
        placement="advanced",
    )
    rows: int = param(
        title=_("Zeilen"),
        default=3,
        minimum=1,
        maximum=100,
        doc=_ROWS_DOC,
        depends_on=("shape", ("hole_grid",)),
        placement="advanced",
    )
    hole_diameter: float = param(
        title=_("Loch-Ø"),
        default=4.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_HOLE_DIAMETER_DOC,
        depends_on=("shape", ("bolt_circle", "hole_grid")),
        placement="advanced",
    )
    # **Die drei Zahlen gelten in der Zeichenebene, nicht in der Welt.**
    # ``x`` und ``y`` verschieben den Umriss über ``shifted`` in den
    # Koordinaten der Ebene, ``z`` misst entlang ihrer Normalen — auf
    # ``plane:xy`` ist beides dasselbe, auf einer Seitenwand nicht. Die
    # ``doc``-Sätze sagten „X", „Y" und „Oberseite des Körpers" und lasen sich
    # damit als Weltkoordinaten.
    x: float = param(
        title=_("X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_(
            "Mitte der Grundform in der Zeichenebene, in deren x-Richtung. "
            "Eine gezeichnete Skizze liegt schon an ihrem Ort."
        ),
    )
    y: float = param(
        title=_("Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_(
            "Mitte der Grundform in der Zeichenebene, in deren y-Richtung. "
            "Eine gezeichnete Skizze liegt schon an ihrem Ort."
        ),
    )
    z: float = param(
        title=_("Oberkante"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_(
            "Wo die Tasche oben beginnt, gemessen senkrecht zur Zeichenebene. "
            "Null heißt: an der Oberseite des Körpers."
        ),
    )
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
        depends_on=("shape", ("polygon",)),
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
        zero_text=_("alle", context="Nullwert"),
    )
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )


def _pocket_in_mesh(
    ctx: OpContext,
    source: SceneObject,
    regions: list[Profile],
    frame: PlaneFrame,
    top: float,
    depth: float,
    through: bool,
) -> OpResult:
    """Dieselbe Tasche in einem Netz — über die Boolesche Rückfallkette.

    **Der Weg, den ein heruntergeladenes Modell nimmt.** Ein eingelesenes STL
    hat keine Flächen im CAD-Sinn, und bis zum 30.08.2026 endete das Abtragen
    dort an einem Satz: „Der gewählte Körper besteht bereits aus festen
    Dreiecken." In Fusion geht es, und es ist der häufigste aller Fälle
    (Robert, 30.08.2026).

    Gerechnet wird wie jede andere Mesh-Operation: Umriss aufziehen
    (:func:`app.core.geom.sketch_solid.extrude_profile`), Werkzeuge vereinen,
    abziehen. Was entsteht, ist ein Netz — der Verlauf trägt denselben Schritt,
    das Ergebnis hat nur keine einzeln bearbeitbaren Flächen mehr, und das
    hatte der Eingang auch nicht.
    """
    from dataclasses import replace as _replace

    from app.core.geom import boolean as mesh_boolean
    from app.core.geom.boolean import BOOLEAN_OVERLAP
    from app.core.geom.mesh import MeshData
    from app.core.geom.sketch_solid import extrude_profile

    # **Die Tiefe zählt von der Oberkante nach unten**, wie im exakten Weg.
    # ``through`` greift über den ganzen Körper hinaus, damit die Differenz
    # sicher durchtrennt statt eine hauchdünne Haut stehen zu lassen.
    reach = depth if not through else depth + 2.0 * BOOLEAN_OVERLAP
    # ``top`` ist eine Weltprojektion; der Rahmen trägt seinen Höhenanteil
    # bereits. Nur die Differenz verschiebt ihn auf die Schnittoberkante.
    rise = top - sum(a * b for a, b in zip(frame.origin, frame.normal, strict=True))
    # Ausgeschrieben statt als ``tuple(...)`` über einen Bereich:
    # ``PlaneFrame`` verlangt genau drei Zahlen, und eine Folge unbekannter
    # Länge ist etwas anderes — mypy sagt das zu Recht.
    lifted = _replace(
        frame,
        origin=(
            frame.origin[0] + frame.normal[0] * rise,
            frame.origin[1] + frame.normal[1] * rise,
            frame.origin[2] + frame.normal[2] * rise,
        ),
    )

    tools = []
    for one in regions:
        ctx.cancelled.raise_if_cancelled()
        try:
            tools.append(MeshData.of(extrude_profile(one, -reach, lifted)))
        except ValueError as problem:
            raise GeometryError(
                detail=_("Aus diesem Umriss entsteht kein Körper."),
                suggestions=(CORRECT_INPUT,),
                values={"reason": str(problem)},
            ) from problem
    if not tools:
        raise GeometryError(
            detail=_("Die Zeichnung enthält keinen geschlossenen Umriss."),
            suggestions=(CORRECT_INPUT,),
        )

    # **Die Vereinigung ist ein eigener Lauf der Kette.** Ihre Stufe und ihre
    # Befunde fielen weg, und damit meldete eine Tasche aus einem geglätteten
    # Werkzeug ``direct`` — der Abbruch fehlte hier ebenso.
    joined = (
        mesh_boolean.boolean(
            "union", tools, quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled
        )
        if len(tools) > 1
        else None
    )
    tool = tools[0] if joined is None else joined.mesh
    outcome = mesh_boolean.boolean(
        "difference",
        # Der Aufrufer kommt aus der Weiche in ``sketch_pocket`` und hat dort
        # geprüft, dass hier kein exakter Körper liegt.
        [cast(MeshData, source.mesh), tool],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )
    nothing = without_effect(source.mesh, outcome.mesh, "difference", ctx.profile)
    # **Die benutzte Rückfallstufe reist mit** (Regel: sie wird in die Operation
    # geschrieben) — und die Befunde der Kette ebenso, sonst verschwiegen sie
    # eine Notlösung.
    return OpResult(
        # Leeres Wörterbuch, nicht die alten Merkmale: Die Kanten, auf die sie
        # zeigten, hat der Schnitt gerade verändert.
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={})],
        findings=[
            *(joined.findings if joined is not None else []),
            *outcome.findings,
            *([nothing] if nothing is not None else []),
        ],
        solver=mesh_boolean.deepest(
            [joined.solver if joined is not None else None, outcome.solver]
        ),
    )


@register_op(
    name="sketch_pocket",
    title=_("Tasche schneiden"),
    category="sketch",
    # Am Netz schneidet eine gezeichnete Kurve seit dem 22.09.2026 entlang der
    # Kurve statt entlang ihrer Stützpunkte, und ein Kreis trägt die Ecken der
    # plattformgleichen Tafel (``sketch_solid.outline_points``) — ältere
    # Ergebnisse dürfen nicht aus dem Cache kommen.
    # Seit dem 23.09.2026 verschiebt X/Y eine gezeichnete Kontur nicht mehr
    # (F2) — ein Ergebnis mit gesetztem X/Y und Zeichnung stammt vom alten Weg.
    cache_version=f"spline-curve-circle-table-1+drawing-keeps-its-place-1+{PROFILE_REVISION}",
    params=SketchPocketParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
    doc=_(
        "Schneidet eine Grundform als Tasche in einen Körper — von der "
        "Oberkante senkrecht nach unten, auf Wunsch durchgehend. Ein Klick auf "
        "eine Fläche trägt den Ort vorab ein. An einem exakten Körper bleiben "
        "Flächen und Kanten erhalten; an einem eingelesenen Netz entsteht ein "
        "Netz."
    ),
)
def sketch_pocket(ctx: OpContext) -> OpResult:
    params = cast(SketchPocketParams, ctx.params)
    findings: list[Finding] = []
    # **Die Ebene der Zeichnung zählt** — wie bei ``sketch_extrude``, dessen
    # Fix hier fehlte: Auf einer Seitenwand gezeichnet schnitt die Tasche
    # trotzdem von oben (Welt-Z), und eine falsche Ebene sah aus wie eine
    # erfüllte Zusage (Gesamtreview D-2). Gerechnet wird entlang der
    # Ebenen-Normalen; auf XY ist das Welt-Z, und dort ändert sich nichts.
    plane = _plane_of(params.sketch)
    # Alle Umrisse, wie beim Extrudieren: Zwei Taschen in einer Zeichnung sind
    # eine Handlung. Vorher lehnte die Tasche dieselbe Skizze ab, die das
    # Extrudieren rechnete (Gesamtreview D-15).
    # **Eine Zeichnung hat ihren Ort** (Bedienabnahme Zeichnen, F2). X und Y
    # setzen die Grundform aus dem Dialog; eine gezeichnete Kontur liegt schon
    # in ihrer Ebene — auf einer Fläche in deren Rahmen, mit der Flächenmitte
    # als Ursprung. Sie noch einmal um X/Y zu verschieben hieß, den Ort
    # zweimal zu nehmen: Auf jeder Fläche, deren Mitte nicht im Weltursprung
    # lag, schnitt die Tasche daneben.
    shift = (0.0, 0.0) if params.sketch else (params.x, params.y)
    chosen = [
        shifted(one, *shift)
        for one in _regions_for(
            ctx,
            params.sketch,
            params.shape,
            params.length,
            params.width,
            params.corners,
            params.region,
            findings,
            _pattern_of(params),
        )
    ]
    result = cut_regions(ctx, chosen, plane, depth=params.depth, through=params.through, z=params.z)
    return dataclasses.replace(result, findings=[*findings, *result.findings])


@dataclasses.dataclass(frozen=True)
class _CutSpan:
    """Wo ein Schnitt von einer Zeichenebene aus beginnt und wie weit der Körper reicht.

    Alle Zahlen entlang der Normalen der Zeichenebene gemessen: ``low`` und
    ``high`` sind die Enden des Körpers, ``top`` die Oberkante des Schnitts,
    ``plane_s`` die Lage der Ebene selbst. *Tasche schneiden* und *Durch
    Überblenden schneiden* fragen dieselbe Frage — eine Antwort (P6.5c).
    """

    frame: PlaneFrame | None
    normal: tuple[float, float, float]
    plane_s: float
    low: float
    high: float
    top: float


def _cut_span(ctx: OpContext, body: Any, plane: str, z: float) -> _CutSpan:
    """Die Oberkante eines Schnitts von dieser Ebene aus, und die Spanne des Körpers."""
    frame = _frame_of(ctx, plane)
    if frame is not None:
        normal = frame.normal
        plane_s = _along(frame.origin, normal)
    else:
        _, normal = profiles.PLANES[plane]
        plane_s = 0.0
    low_s, high_s = _span_along(body, normal)
    # Mit Rahmen liegt die Skizze auf der Fläche — dort beginnt die Tasche;
    # ein Welt-Z vom Klick hat auf einer schrägen Fläche keine Bedeutung.
    if frame is not None:
        top = plane_s
    elif abs(z) > EPS_GEOM:
        top = z
    else:
        top = high_s
    return _CutSpan(frame, normal, plane_s, low_s, high_s, top)


def cut_regions(
    ctx: OpContext,
    regions: list[Profile],
    plane: str,
    *,
    depth: float,
    through: bool,
    z: float = 0.0,
) -> OpResult:
    """Gemeinsamer Taschenschnitt aus aufgelösten Profilen, ohne Zwischenserialisierung.

    Eine Flächenebene beginnt an ihrer Fläche; auf einer Grundebene bedeutet
    z=0 weiterhin die Körperoberkante. Durchgehend reicht über die vollständige
    Körperspanne. Mesh und B-Rep behalten den bisherigen Schnittweg.
    """
    source = ctx.inputs[0]
    body = source.mesh
    findings: list[Finding] = []
    chosen = regions
    span = _cut_span(ctx, body, plane, z)
    frame, normal, plane_s = span.frame, span.normal, span.plane_s
    low_s, high_s, top = span.low, span.high, span.top
    if through:
        bottom, reach = low_s - 1.0, (high_s - low_s) + 2.0
    else:
        bottom, reach = top - depth, depth
    # Die Prüfung steht hier und nicht oben als Wahrheitswert: So verengt sie
    # den Typ für alles, was darunter folgt — der exakte Zweig rechnet danach
    # mit einem ``Solid`` und muss es nicht behaupten.
    if not isinstance(body, Solid):
        # **Der Mesh-Weg beginnt hier**, mit denselben Zahlen: Oberkante und
        # Tiefe sind oben schon entschieden, und ob der Körper exakt ist,
        # ändert daran nichts.
        # **Ohne Flächenklick gibt es keinen Rahmen** — dann steht die Ebene
        # nur als Name da, und ``frame_for_plane`` macht daraus denselben
        # Rahmen, den der exakte Weg über ``profiles.PLANES`` benutzt.
        #
        # Dass dabei etwas herauskommt, ist keine Hoffnung: Beide Wörterbücher
        # tragen dieselben drei Standardebenen, und ein unbekannter Name wäre
        # oben an ``profiles.PLANES[plane]`` schon aufgeschlagen. Kein eigener
        # Fehlertext also — er wäre für eine Lage geschrieben, die es nicht
        # gibt. ``test_sketch_solid`` hält die beiden Listen deckungsgleich.
        on = frame if frame is not None else planes.frame_for_plane(plane)
        assert on is not None, f"{plane} steht in PLANES, aber nicht in frame_for_plane"
        result = _pocket_in_mesh(ctx, source, chosen, on, top, top - bottom, through)
        return dataclasses.replace(result, findings=[*findings, *result.findings])

    lifted = bottom - plane_s
    tools = []
    for one in chosen:
        ctx.cancelled.raise_if_cancelled()
        tools.append(
            edit.moved(
                profiles.extrude(one, reach, plane, frame),
                (normal[0] * lifted, normal[1] * lifted, normal[2] * lifted),
            )
        )
    tool = tools[0] if len(tools) == 1 else edit.boolean("union", tools)
    solid = edit.boolean("difference", [body, tool])
    if solid.solid_count >= 1 and solid.volume > EPS_GEOM and not profiles.is_sound(solid):
        # **Und die Tasche liefert keinen ungültigen Körper aus** (RM-227): Die
        # Schnitte mit Werkzeug rechnen dann am Netz weiter und sagen es
        # (``sketch.exact_cut_unsound``); *Tasche schneiden* gab denselben
        # ungültigen Körper am Teppichclip still zurück. Derselbe Weg hier —
        # der exakte Versuch dort wiederholt sich, das kostet nur im Fehlerfall.
        return _cut_with_tool(ctx, tool, findings, seed=ctx.seed)
    # Eine Tasche, die den Körper verfehlt, lief stumm durch: im Verlauf ein
    # Schritt, im Bild dasselbe Teil, und keine Zeile, die das erklärt.
    # Gemessen an vier Fällen — Oberkante unter dem Körper, Ort daneben —, und
    # in allen vieren sagte niemand etwas. Denselben Satz bekommt seit je, wer
    # eine Magnettasche daneben setzt (`geom/boolean.without_effect`).
    nothing = without_effect(body, solid, "difference", ctx.profile)
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=solid,
                kind="brep",
                features=features_of(solid, cancelled=ctx.cancelled),
            )
        ],
        findings=[*findings, *([nothing] if nothing is not None else [])],
    )


#: Wo ein gezeichneter Querschnitt so liegt, wie der Rotationskörper ihn liest:
#: stehend, mit der Waagerechten als Abstand zur senkrechten Achse.
_UPRIGHT_PLANES: frozenset[str] = frozenset({"plane:xz", "plane:yz"})


@op_params
class SketchRevolveParams(BaseParams):
    shape: str = param(
        title=_("Grundform"),
        default="rectangle",
        choices=shapes.SHAPE_CHOICES,
        doc=_SHAPE_DOC,
        placement="advanced",
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
        placement="advanced",
    )
    width: float = param(
        title=_("Breite"),
        default=8.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Höhe des Querschnitts entlang der Achse. Beim Kreis und beim Vieleck ohne Wirkung."),
        # **Wie bei den Geschwistern, und das stand hier anders.** Der
        # Kommentar an dieser Stelle behauptete, die Angabe wirke „auch beim
        # Vieleck", weil der ``doc``-Satz allein den Kreis ausschließt.
        # Gemessen am 24.08.2026 wirkt sie dort nicht: Ein Sechseck mit
        # ``length=20`` liefert bei ``width=5`` und ``width=20`` dasselbe
        # Volumen (32648,3886), ein Rechteck dagegen 12566 gegen 50265.
        #
        # Der Grund liegt zwei Ebenen tiefer und in **beiden** Zweigen:
        # ``_sketch_profile`` baut das Vieleck aus ``length`` und ``corners``
        # (``shapes.polygon``) und sieht ``width`` nicht, und der Versatz zur
        # Achse nimmt bei Kreis *und* Vieleck ``length / 2`` statt
        # ``width / 2``. Ein aktives Feld, das nichts tut, ist genau der Fall,
        # den `.claude/rules/oberflaeche.md` unter „Gestufte Tiefe" („ein Feld
        # ohne Wirkung steht nicht da") verbietet — und ein Kommentar, der
        # eine Wirkung behauptet, ohne
        # sie gemessen zu haben, ist der Grund, aus dem er zwei Jahre stehen
        # bleibt.
        #
        # Der ``doc``-Satz bleibt vorerst, wie er ist: Er ist ein Katalogtext
        # in fünf Sprachen, und beim Vieleck steht ohnehin der Grund der
        # Sperre an der Zeile statt seiner (``_explain`` in ``op_dialog.py``).
        depends_on=("shape", ("rectangle", "slot")),
        placement="advanced",
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
    name: str = param(title=_("Name"), default="", placement="advanced", doc=NAME_DOC)
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
        depends_on=("shape", ("polygon",)),
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
    cache_version=PROFILE_REVISION,
    params=SketchRevolveParams,
    consumes=0,
    produces=1,
    doc=_(
        "Dreht einen Querschnitt um die senkrechte Achse: ein Rechteck wird "
        "zur Hülse, ein Kreis zum Ring. Der Körper steht auf dem Druckbett."
    ),
)
def sketch_revolve(ctx: OpContext) -> OpResult:
    params = cast(SketchRevolveParams, ctx.params)
    findings: list[Finding] = []
    require()
    placed = _revolve_section(ctx, params, findings)
    if params.sketch:
        drawn_on = _plane_of(params.sketch)
        if drawn_on not in _UPRIGHT_PLANES:
            # **Gedreht wird aufrecht, gleich wo gezeichnet wurde** — und das
            # wird gesagt, statt still umgedeutet (Regel 21). Auf der
            # Vorder- oder Seitenansicht steht der Körper genau dort, wo die
            # Zeichnung liegt; auf der Draufsicht, einer Fläche oder einer
            # abgeleiteten Ebene läge die Zeichnung flach und der Körper
            # stünde trotzdem — ohne diesen Satz sähe das aus wie ein Fehler
            # der Operation. Nur beim Erzeuger: Der Schnitt dreht um die
            # gewählte Achse, und dort ist „senkrecht" nicht die Achse.
            findings.append(
                Finding(
                    code="sketch.revolve_upright",
                    severity="info",
                    message=_(
                        "Der Querschnitt liegt auf keiner Vorder- oder Seitenansicht und wird "
                        "trotzdem aufrecht um die senkrechte Achse gedreht."
                    ),
                    values={"plane": drawn_on},
                )
            )
    solid = profiles.revolve(placed, params.angle)
    return OpResult(
        outputs=[
            _created(
                params.name,
                str(_("Rotationskörper")),
                solid,
                cancelled=ctx.cancelled,
                findings=findings,
            )
        ],
        findings=findings,
    )


def _revolve_section(
    ctx: OpContext,
    params: SketchRevolveParams | SketchRevolveCutParams,
    findings: list[Finding],
) -> Profile:
    """Der Querschnitt eines Drehkörpers, so gelegt, wie die Achse ihn braucht.

    **Eine Stelle für Erzeuger und Schnitt** (P6.5a): Die Nut ist derselbe
    Drehkörper, nur abgezogen statt hingestellt. Zwei Herleitungen der Lage
    liefen beim nächsten Fund auseinander — so wie hier einmal der Versatz
    beim Vieleck (unten).
    """
    if params.sketch:
        # Wie gezeichnet: die Skizze kennt ihren Abstand zur Achse selbst.
        return _drawn_profile(ctx, params.sketch, findings)
    profile = _sketch_profile(params.shape, params.length, params.width, params.corners)
    # **Der gemessene Bereich statt einer Formel je Grundform.** Hier stand
    # ``offset + length/2`` waagerecht und ``length/2`` beziehungsweise
    # ``width/2`` senkrecht. Beides ist der halbe **Umkreis**durchmesser
    # und trifft nur, wo die Form genauso um den Ursprung liegt —
    # Rechteck, Langloch, Kreis. Ein Vieleck liegt anders, weil seine
    # untere Kante waagerecht steht:
    #
    # * Dreieck, ``length=20``: x reicht bis ±8,66, y von -5 bis +10. Es
    #   schwebte 5,00 mm über dem Bett, und seine Innenkante stand
    #   1,34 mm weiter draußen als der Abstand sagt.
    # * Sechseck, ``length=20``: x stimmt (±10), y reicht nur ±8,66 — der
    #   Abstand traf, das Bett um 1,34 mm nicht.
    #
    # ``bounds_of`` ist bei allen vier Formen exakt (bei Langloch und
    # Kreis liegt der Scheitel jedes Bogens auf seinem Stützpunkt), und
    # für Rechteck, Langloch und Kreis kommt dieselbe Verschiebung heraus
    # wie vorher. Denselben Weg geht ``sketch_loft`` mit der gezeichneten
    # Skizze.
    low, _high = bounds_of(profile)
    return shifted(profile, params.offset - low[0], -low[1])


@op_params
class SketchSweepParams(BaseParams):
    shape: str = param(
        title=_("Grundform"),
        default="circle",
        choices=shapes.SHAPE_CHOICES,
        doc=_SHAPE_DOC,
        placement="advanced",
    )
    length: float = param(
        title=_("Länge"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_LENGTH_DOC,
        placement="advanced",
    )
    width: float = param(
        title=_("Breite"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
        placement="advanced",
    )
    along: str = param(
        title=_("Bahn"),
        default="arc",
        choices=("arc", "drawn"),
        doc=_(
            "Woran der Querschnitt entlangläuft: an einem Bogen aus zwei Zahlen "
            "oder an einer gezeichneten Bahn. Ein Rohrbogen braucht keine "
            "Zeichnung; ein Kanal um zwei Ecken schon."
        ),
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
        depends_on=("along", ("arc",)),
    )
    bend_angle: float = param(
        title=_("Bogenwinkel"),
        default=90.0,
        unit=DEGREE_UNIT,
        minimum=1.0,
        maximum=180.0,
        doc=_("Wie weit der Bogen führt — 90 Grad ist ein rechtwinkliger Rohrbogen."),
        depends_on=("along", ("arc",)),
        placement="advanced",
    )
    # **Vorn, sobald die Bahn gezeichnet wird** (RM-183): Sie ist dann die
    # Eingabe, auf die es ankommt, und ``depends_on`` nimmt sie beim Bogen aus
    # dem Dialog. Hinter „Weitere Einstellungen" suchte sie niemand — gefahren
    # am 22.09.2026: „Bahn: gezeichnet" gewählt, und kein Knopf zum Zeichnen
    # zu sehen. Die Ebenen sagen dem Editor, wo die Bahn liegen darf.
    path_sketch: str = param(
        title=_("Gezeichnete Bahn"),
        default="",
        kind="sketch",
        sketch_planes=tuple(sorted(profiles.PATH_PLANES)),
        doc=_(
            "Der Verlauf, dem der Querschnitt folgt — offen gezeichnet, auf der "
            "Vorder- oder Seitenansicht und am Anfang senkrecht nach oben oder unten. "
            "Ihr Anfang kommt in den Ursprung: Die Bahn beschreibt einen Verlauf, keinen Ort."
        ),
        depends_on=("along", ("drawn",)),
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=NAME_DOC)
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
        depends_on=("shape", ("polygon",)),
    )
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )


@register_op(
    name="sketch_sweep",
    title=_("Entlang eines Bogens führen"),
    category="sketch",
    # ``self-check``: Eine Bahn, die sich kreuzt, zu eng biegt oder mit ihrer
    # Röhre an sich selbst stößt, gibt seit P6.5 eine Absage statt eines
    # selbstdurchdringenden Körpers — ein alter Cachetreffer brächte ihn zurück.
    cache_version=f"profile-holes-normal-start-self-check-2+{PROFILE_REVISION}",
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
    findings: list[Finding] = []
    solid, _upward = _swept(ctx, params, findings)
    fallback = _("Bahn") if params.along == "drawn" else _("Bogen")
    return OpResult(
        outputs=[
            _created(params.name, str(fallback), solid, cancelled=ctx.cancelled, findings=findings)
        ],
        findings=findings,
    )


def _swept(
    ctx: OpContext,
    params: SketchSweepParams | SketchSweepCutParams,
    findings: list[Finding],
) -> tuple[Solid, bool]:
    """Der geführte Körper, am Ursprung beginnend und senkrecht startend —
    und ob er nach oben beginnt.

    Der Bogen beginnt immer nach oben; eine gezeichnete Bahn darf nach oben
    oder nach unten beginnen (``profiles.sweep_path``). Der Schnitt braucht
    die Richtung, um den Kanal in den Körper statt aus ihm heraus zu führen.

    **Eine Stelle für Erzeuger und Schnitt** (P6.5b), und mit ihr die
    Prüfungen, die beide brauchen: Eine Bahn, die sich kreuzt, enger biegt
    als der Querschnitt breit ist oder mit ihrer Röhre an sich selbst
    anstößt, ergab bis hierher einen Körper, der sich selbst durchdringt —
    beim Erzeuger still ausgeliefert, beim Schnitt ein Werkzeug, das nicht das
    Gezeichnete wegnimmt.
    """
    # **Der Bogen läuft entlang X und Z — das ist seine Definition**, nicht
    # eine vergessene Ebene: Eine Skizze auf einer anderen Ebene wurde bisher
    # stillschweigend wie auf XY gerechnet (Gesamtreview D-2). Abgelehnt
    # statt übergangen (Regel 21).
    sweep_plane = _plane_of(params.sketch)
    if sweep_plane != "plane:xy":
        raise ValidationError(
            "sketch",
            _(
                "Der Bogen führt den Querschnitt entlang X und Z — diese "
                "Zeichnung liegt auf einer anderen Ebene."
            ),
            constraint="sweep_needs_xy",
            values={"plane": sweep_plane},
            suggestions=[
                Action(
                    id="sketch.use_global_plane",
                    label=_("Auf der Grundebene (XY) zeichnen"),
                    primary=True,
                )
            ],
        )
    require()
    profile = _profile_for(
        ctx, params.sketch, params.shape, params.length, params.width, params.corners, findings
    )
    if params.along != "drawn":
        return profiles.sweep_arc(profile, params.bend_radius, params.bend_angle), True
    # **Die gezeichnete Bahn** (E3, RM-147): Bis hierher kannte der Sweep
    # genau eine Kurve — den Kreisbogen aus Radius und Winkel. Alles, was
    # zweimal abbiegt oder ungleichmäßig krümmt (ein Kabelkanal um zwei
    # Ecken, ein Griff mit einer Kehle), war damit nicht zu bauen.
    if not params.path_sketch:
        raise ValidationError(
            "path_sketch",
            _(
                "Für die Bahn fehlt die Zeichnung. Zeichnen Sie sie, oder "
                "führen Sie den Querschnitt an einem Bogen entlang."
            ),
            constraint="empty",
            suggestions=(CORRECT_INPUT,),
        )
    path = path_of(_solved_drawing(ctx, params.path_sketch, findings))
    path_plane = _plane_of(params.path_sketch)
    _check_path(profile, path, path_plane)
    solid = profiles.sweep_path(profile, path, path_plane)
    ctx.cancelled.raise_if_cancelled()
    if profiles.intersects_itself(solid):
        raise GeometryError(
            detail=_(
                "Entlang dieser Bahn trifft der Querschnitt auf sich selbst — zwei "
                "Stücke der Bahn liegen enger beieinander, als er breit ist. "
                "Ziehen Sie die Bahn weiter auseinander oder wählen Sie einen "
                "schmaleren Querschnitt."
            ),
            suggestions=(Action("open_sketch", _("Skizze ansehen"), primary=True), CORRECT_INPUT),
            values={"reason": "tool_intersects_itself"},
        )
    return solid, _tangent_at(path.segments[0], 0.0)[1] > 0.0


#: Wie viele Stellen je kubischem Splinestück nach seiner Krümmung gefragt
#: werden. Eine Vorprüfung für einen verständlichen Satz, keine Zusage: Was sie
#: zwischen zwei Stellen übersieht, findet danach die Selbstschnittprüfung des
#: Kerns (``profiles.intersects_itself``) — nur mit dem allgemeineren Satz.
_BEND_SAMPLES = 32


def _check_path(profile: Profile, path: Profile, plane: str) -> None:
    """Hält eine Bahn an, bevor der Kern daraus einen kaputten Körper baut.

    **Zwei Fälle, die man benennen kann:** Die Bahn kreuzt sich selbst, oder
    sie biegt enger, als der Querschnitt zur Innenseite des Bogens reicht.
    Der zweite ist tückisch, weil OpenCASCADE daraus einen Körper baut, den
    seine eigene Gültigkeitsprüfung durchlässt.

    **Welche Seite des Querschnitts zählt,** folgt aus der Bahn: Der
    Querschnitt liegt am Anfang in XY, und seine Achse in der Bahnebene (x
    bei einer Bahn auf XZ, y auf YZ) wandert mit der Bahn mit, ohne sich zu
    verdrehen. Biegt die Bahn nach links, liegt die Mitte des Bogens links
    der Laufrichtung — am Anfang nach oben ist das die negative Seite dieser
    Achse, nach unten die positive. Gemessen wird der Querschnitt an seinem
    Hüllrechteck (``bounds_of``); das liegt nie weiter draußen als der
    Umriss, die Vorprüfung hält also nur an, wo es sicher nicht geht.
    """
    heading = _tangent_at(path.segments[0], 0.0)
    if abs(heading[0]) > EPS_GEOM * math.hypot(heading[0], heading[1]):
        # Ein schräger Anfang ist der grundlegendere Fehler, und ohne
        # senkrechten Anfang gibt es keine Seite, an der sich die Biegung
        # messen ließe. Den Satz dazu sagt ``profiles.sweep_path`` an der
        # exakten Kurve.
        return
    if crosses_itself(path):
        raise ValidationError(
            "path_sketch",
            _(
                "Die Bahn kreuzt sich selbst. Zeichnen Sie sie so, dass kein Stück "
                "ein anderes schneidet."
            ),
            constraint="path_crosses",
            suggestions=(CORRECT_INPUT,),
        )
    across = 0 if plane == "plane:xz" else 1
    low, high = bounds_of(profile)
    reach = {1.0: high[across], -1.0: -low[across]}
    # Links der Laufrichtung, auf die Querschnittsachse gelegt: -ty bei der
    # Anfangsrichtung (tx, ty). Für eine Linkskurve liegt die Mitte dort.
    left = -1.0 if heading[1] > 0.0 else 1.0
    for segment in path.segments:
        for radius, turns_left in _bends(segment):
            side = left if turns_left else -left
            if radius <= reach[side] + EPS_GEOM:
                raise ValidationError(
                    "path_sketch",
                    _(
                        "Die Bahn biegt enger, als der Querschnitt breit ist — die "
                        "Innenseite des Bogens schnitte sich selbst. Vergrößern Sie den "
                        "Bogenradius oder wählen Sie einen schmaleren Querschnitt."
                    ),
                    value=radius,
                    constraint="tight_bend",
                    values={"radius_mm": round(radius, 4), "needed_mm": round(reach[side], 4)},
                    suggestions=(CORRECT_INPUT,),
                )


def _tangent_at(segment: ProfileSegment, at: float) -> tuple[float, float]:
    """Die Laufrichtung eines Bahnstücks an seinem Anfang (0) oder Ende (1)."""
    if segment.kind == "arc" and segment.via is not None:
        turn = arc_through(segment.start, segment.via, segment.end)
        if turn is not None:
            (cx, cy), _radius, sweep = turn
            point = segment.start if at == 0.0 else segment.end
            dx, dy = point[0] - cx, point[1] - cy
            return (-dy, dx) if sweep > 0.0 else (dy, -dx)
    if segment.kind == "spline":
        pieces = spline_controls(segment.through or (segment.start, segment.end))
        piece = pieces[0] if at == 0.0 else pieces[-1]
        velocity, _curve = _bezier_derivatives(piece, at)
        return velocity
    return (segment.end[0] - segment.start[0], segment.end[1] - segment.start[1])


def _bends(segment: ProfileSegment) -> list[tuple[float, bool]]:
    """Die Krümmungsradien eines Bahnstücks, je mit „biegt nach links".

    Eine Strecke biegt nicht; ein Bogen hat einen Radius, und das Vorzeichen
    seiner Weite sagt die Richtung (``arc_through``: positiv gegen den
    Uhrzeigersinn, also links herum). Ein Spline wird an
    :data:`_BEND_SAMPLES` Stellen je Stück gefragt.
    """
    if segment.kind == "arc" and segment.via is not None:
        turn = arc_through(segment.start, segment.via, segment.end)
        return [] if turn is None else [(turn[1], turn[2] > 0.0)]
    if segment.kind != "spline":
        return []
    found: list[tuple[float, bool]] = []
    for piece in spline_controls(segment.through or (segment.start, segment.end)):
        for step in range(_BEND_SAMPLES + 1):
            velocity, curve = _bezier_derivatives(piece, step / _BEND_SAMPLES)
            speed = math.hypot(velocity[0], velocity[1])
            cross = velocity[0] * curve[1] - velocity[1] * curve[0]
            if speed <= EPS_GEOM or abs(cross) <= EPS_GEOM:
                continue
            found.append((speed**3 / abs(cross), cross > 0.0))
    return found


def _bezier_derivatives(
    piece: tuple[Point2, ...], t: float
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Erste und zweite Ableitung eines kubischen Bézierstücks an der Stelle ``t``."""
    p0, p1, p2, p3 = piece
    u = 1.0 - t
    velocity = [
        3.0 * (u * u * (p1[k] - p0[k]) + 2.0 * u * t * (p2[k] - p1[k]) + t * t * (p3[k] - p2[k]))
        for k in (0, 1)
    ]
    curve = [
        6.0 * (u * (p2[k] - 2.0 * p1[k] + p0[k]) + t * (p3[k] - 2.0 * p2[k] + p1[k]))
        for k in (0, 1)
    ]
    return (velocity[0], velocity[1]), (curve[0], curve[1])


@op_params
class SketchLoftParams(BaseParams):
    shape: str = param(
        title=_("Grundform"),
        default="rectangle",
        choices=shapes.SHAPE_CHOICES,
        doc=_SHAPE_DOC,
        placement="advanced",
    )
    length: float = param(
        title=_("Länge"),
        default=40.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_LENGTH_DOC,
        placement="advanced",
    )
    width: float = param(
        title=_("Breite"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
        placement="advanced",
    )
    height: float = param(
        title=_("Höhe"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Abstand zwischen unterem und oberem Umriss."),
    )
    top: str = param(
        title=_("Oberer Umriss"),
        default="scaled",
        choices=("scaled", "drawn"),
        doc=_(
            "Woher der obere Umriss kommt: aus dem unteren gerechnet oder als "
            "eigene Zeichnung. Ein Kegelstumpf braucht nur eine Zahl; ein "
            "Übergang von rund auf eckig braucht zwei Umrisse."
        ),
        placement="advanced",
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
        depends_on=("top", ("scaled",)),
        placement="advanced",
    )
    # Hinten wie die Wahl „Oberer Umriss“, und gleich unter ihr (RM-513): Wer
    # „gezeichnet“ wählt, findet den Zeichenknopf dort, wo er gewählt hat —
    # die Lehre der Sweep-Bahn (RM-183).
    top_sketch: str = param(
        title=_("Obere Zeichnung"),
        default="",
        kind="sketch",
        doc=_(
            "Der zweite Umriss, frei gezeichnet — auf derselben Ebene wie der "
            "untere, und um die Höhe darüber aufgespannt."
        ),
        depends_on=("top", ("drawn",)),
        placement="advanced",
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=NAME_DOC)
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
        depends_on=("shape", ("polygon",)),
    )
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )


@register_op(
    name="sketch_loft",
    title=_("Zwischen zwei Umrissen aufspannen"),
    category="sketch",
    cache_version=PROFILE_REVISION,
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
    findings: list[Finding] = []
    require()
    plane, pairs = _loft_outlines(ctx, params, findings)
    frame = _frame_of(ctx, plane)
    bodies = [profiles.loft(below, above, params.height, plane, frame) for below, above in pairs]
    solid = bodies[0] if len(bodies) == 1 else edit.boolean("union", bodies)
    return OpResult(
        outputs=[
            _created(
                params.name, str(_("Übergang")), solid, cancelled=ctx.cancelled, findings=findings
            )
        ],
        findings=findings,
    )


def _loft_outlines(
    ctx: OpContext,
    params: SketchLoftParams | SketchLoftCutParams,
    findings: list[Finding],
) -> tuple[str, list[tuple[Profile, Profile]]]:
    """Die Ebene und die Umrisspaare eines Übergangs — unten mit oben.

    **Eine Stelle für Erzeuger und Schnitt** (P6.5c). Drei Wege führen zu
    den Paaren, und jeder bleibt, wie er war:

    * **Zwei Grundformen**, die zweite kleiner gerechnet. Der Weg des
      Katalogs; die Grundformen liegen um den Ursprung zentriert und die
      Maße kommen direkt aus den Parametern — daran ist nichts zu skalieren.
    * **Die gezeichnete Skizze und ihre verkleinerte Kopie.** Skaliert wird
      um den **Mittelpunkt des Umrisses**, nicht um den Ursprung: Eine
      Grundform liegt zentriert, eine Zeichnung liegt irgendwo, und um den
      Ursprung verkleinert wanderte sie beim Schrumpfen zum Nullpunkt — aus
      einem Pyramidenstumpf würde ein schiefer Keil. (Diese Operation war die
      einzige der fünf ohne Skizzenfeld, und der Fertig-Dialog bot sie
      trotzdem an: Wer nach dem Zeichnen „Zwischen zwei Umrissen aufspannen"
      wählte, bekam einen internen Fehler statt eines Körpers.)
    * **Zwei Zeichnungen** (:func:`_drawn_pairs`).
    """
    if params.top == "drawn":
        return _drawn_pairs(ctx, params, findings)
    if not params.sketch:
        bottom = _sketch_profile(params.shape, params.length, params.width, params.corners)
        top = _sketch_profile(
            params.shape,
            params.length * params.top_scale,
            params.width * params.top_scale,
            params.corners,
        )
        return "plane:xy", [(bottom, top)]
    chosen = _regions_for(
        ctx, params.sketch, params.shape, params.length, params.width, params.corners, 0, findings
    )
    pairs = []
    for one in chosen:
        low, high = bounds_of(one)
        centre = ((low[0] + high[0]) / 2.0, (low[1] + high[1]) / 2.0)
        pairs.append((one, scaled(one, params.top_scale, centre)))
    return _plane_of(params.sketch), pairs


def _drawn_pairs(
    ctx: OpContext,
    params: SketchLoftParams | SketchLoftCutParams,
    findings: list[Finding],
) -> tuple[str, list[tuple[Profile, Profile]]]:
    """Der Übergang zwischen **zwei gezeichneten** Umrissen (E2, RM-147).

    Bis hierher konnte diese Operation nur eine Zeichnung und ihre verkleinerte
    Kopie: ein Kegel- oder Pyramidenstumpf. Der Fall, für den es einen Loft in
    jedem CAD gibt, ging nicht — rund unten, eckig oben; ein Adapter von einem
    Rohr auf einen Kanal.

    Der Kern konnte es die ganze Zeit: :func:`brep.profiles.loft` nimmt zwei
    unabhängige Profile. Was fehlte, war der Weg dorthin.

    **Die Topologie wird vorher geprüft**, und zwar an drei Stellen, weil jede
    für sich einen anderen Fehler ergäbe:

    * Beide Zeichnungen liegen auf **derselben Ebene**. Die obere wird um die
      Höhe entlang der Ebenennormalen gehoben; läge sie auf einer anderen
      Ebene, hätte diese Hebung keine Bedeutung, und der Körper stünde
      irgendwo — stillschweigend verdreht (Regel 21).
    * Beide tragen **gleich viele getrennte Umrisse**. Sonst wäre nicht
      entschieden, was mit was verbunden wird; ``zip`` nähme still die ersten
      und ließe den Rest fallen.
    * Und dieselbe Frage eine Ebene tiefer beantwortet der Kern selbst: gleich
      viele **Löcher** je Umrisspaar.

    Verbunden wird in der Reihenfolge, in der :func:`regions_of` die Umrisse
    liefert — dieselbe für beide Zeichnungen. Bei einem Paar ist das die
    einzige Möglichkeit; bei mehreren ist es eine Zusage, die der Satz im
    Dialog nennt.
    """
    if not params.top_sketch:
        raise ValidationError(
            "top_sketch",
            _(
                "Für den oberen Umriss fehlt die Zeichnung. Zeichnen Sie sie, oder "
                "rechnen Sie den Umriss aus dem unteren."
            ),
            constraint="empty",
            suggestions=(CORRECT_INPUT,),
        )
    plane = _plane_of(params.sketch)
    if _plane_of(params.top_sketch) != plane:
        raise ValidationError(
            "top_sketch",
            _(
                "Die beiden Zeichnungen liegen auf verschiedenen Ebenen. Der obere "
                "Umriss wird um die Höhe angehoben; dafür müssen beide auf derselben "
                "Ebene liegen."
            ),
            constraint="other_plane",
            suggestions=(CORRECT_INPUT,),
        )
    lower = _regions_for(
        ctx, params.sketch, params.shape, params.length, params.width, params.corners, 0, findings
    )
    upper = _regions_for(
        ctx,
        params.top_sketch,
        params.shape,
        params.length,
        params.width,
        params.corners,
        0,
        findings,
    )
    if len(lower) != len(upper):
        raise ValidationError(
            "top_sketch",
            _(
                "Die beiden Zeichnungen tragen verschieden viele getrennte Umrisse — "
                "dann steht nicht fest, was womit verbunden wird."
            ),
            constraint="region_count",
            values={"lower_outlines": len(lower), "upper_outlines": len(upper)},
            suggestions=(CORRECT_INPUT,),
        )
    return plane, list(zip(lower, upper, strict=True))


# --- Schneiden mit den drei Werkzeugen (CAD-Konzept P6.5a bis c) ---------------
#
# **Eigene Operationen und kein Umschalter an den Erzeugern**, entschieden an
# der Zwillingsregel (`grenzen.md`: eine Operation je Handlung, nicht je
# Variante). Einen Körper *erzeugen* und aus einem Körper *herausschneiden*
# sind zwei Handlungen, und das Register sagt es selbst: Ein Erzeuger nimmt
# nichts (`consumes=0`) und setzt einen neuen Körper; ein Schnitt nimmt den
# gewählten und gibt ihn verändert unter seiner Kennung zurück
# (`consumes=1`). Die Eingangszahl steht je Operation fest, und der Stapel
# vergibt die Kennungen, bevor etwas rechnet (§11) — ein Feld „Hinzufügen/
# Abziehen" müsste sie je nach Wert ändern. Dasselbe Paar gibt es seit je:
# *Grundform hochziehen* und *Tasche schneiden*.
#
# **Und trotzdem kein zweiter Menüeintrag** (Konzept §10: „Revolve-Cut wird
# kein zweiter Eintrag, sondern ein Feld im Dialog"): Die drei stehen in der
# Variantengruppe *Aus Skizze erzeugen …* direkt hinter ihrem Erzeuger — das
# Feld ist die Art. Werkzeug und Querschnitt kommen aus denselben Helfern wie
# beim Erzeuger (`_revolve_section`, `_swept`, `_loft_outlines`); was dazukommt,
# ist die Lage am Zielkörper und die Differenz in beiden Kernen.


@op_params
class SketchRevolveCutParams(BaseParams):
    shape: str = param(
        title=_("Grundform"),
        default="rectangle",
        choices=shapes.SHAPE_CHOICES,
        doc=_SHAPE_DOC,
        placement="advanced",
    )
    length: float = param(
        title=_("Länge"),
        default=2.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_(
            "Ausdehnung des Querschnitts von der Achse weg — bei einer Ringnut ihre "
            "Tiefe. Beim Kreis und beim Vieleck ist das der Durchmesser."
        ),
        placement="advanced",
    )
    width: float = param(
        title=_("Breite"),
        default=3.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_(
            "Höhe des Querschnitts entlang der Achse — bei einer Ringnut ihre Breite. "
            "Beim Kreis und beim Vieleck ohne Wirkung."
        ),
        depends_on=("shape", ("rectangle", "slot")),
        placement="advanced",
    )
    offset: float = param(
        title=_("Abstand zur Achse"),
        default=8.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        doc=_(
            "Abstand der Innenkante des Querschnitts von der Drehachse — bei einer "
            "Ringnut an einer Welle der Radius des Nutgrunds."
        ),
    )
    angle: float = param(
        title=_("Winkel"),
        default=360.0,
        unit=DEGREE_UNIT,
        minimum=1.0,
        maximum=360.0,
        placement="advanced",
        doc=_(
            "Wie weit um die Achse geschnitten wird. 360 läuft ganz herum, weniger "
            "gibt eine Teilnut."
        ),
    )
    start_angle: float = param(
        title=_("Beginn"),
        default=0.0,
        unit=DEGREE_UNIT,
        minimum=0.0,
        maximum=360.0,
        placement="advanced",
        doc=_("Wo eine Teilnut beginnt, um die Achse gemessen. Bei 360 Grad ohne Wirkung."),
    )
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=("z", "x", "y"),
        placement="advanced",
        doc=_(
            "In welche Richtung die Drehachse zeigt. Ist ein rundes Merkmal gewählt, gilt "
            "dessen Achse."
        ),
    )
    axis_x: float = param(
        title=_("Achspunkt X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_AXIS_POINT_DOC,
    )
    axis_y: float = param(
        title=_("Achspunkt Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_AXIS_POINT_DOC,
    )
    axis_z: float = param(
        title=_("Achspunkt Z"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_AXIS_POINT_DOC,
    )
    axis_feature: str = param(
        title=_("Achse von"),
        default="",
        kind="feature",
        placement="advanced",
        doc=_(
            "Eine Bohrung oder ein Zapfen des Körpers, dessen Achse die Drehachse wird. "
            "Ein Klick auf das Merkmal trägt es ein; leer heißt: die Achse oben gilt."
        ),
    )
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
        depends_on=("shape", ("polygon",)),
    )
    sketch: str = param(
        title=_("Skizze"),
        default="",
        kind="sketch",
        placement="advanced",
        doc=_(
            "Eine gezeichnete Skizze als Querschnitt: x ist der Abstand von der Achse, y "
            "die Lage entlang der Achse ab dem Achspunkt — der Abstand oben gilt dann nicht."
        ),
    )


@register_op(
    name="sketch_revolve_cut",
    title=_("Durch Drehen schneiden"),
    cache_version=PROFILE_REVISION,
    category="sketch",
    params=SketchRevolveCutParams,
    consumes=1,
    produces=1,
    deterministic=False,
    caveat=_MESH_CUT_CAVEAT,
    doc=_(
        "Dreht einen Querschnitt um eine Achse und nimmt, was er dabei überstreicht, aus "
        "dem gewählten Körper heraus. So entsteht eine Ringnut in einer Welle oder in "
        "einer Bohrung, ganz herum oder als Teilstück."
    ),
)
def sketch_revolve_cut(ctx: OpContext) -> OpResult:
    params = cast(SketchRevolveCutParams, ctx.params)
    findings: list[Finding] = []
    require()
    from app.core.geom.transform import rotation_about, rotation_between, translation

    tool = profiles.revolve(_revolve_section(ctx, params, findings), params.angle)
    origin, direction = _revolve_axis(ctx.inputs[0], params)
    # Der Drehkörper des Erzeugers steht um die Z-Achse durch den Ursprung.
    # Erst um die eigene Achse auf den Beginn gedreht, dann auf die gewählte
    # Achse gelegt — beides aus den exakten Winkelfunktionen (RM-187), damit
    # ein rechter Winkel auf jeder Maschine dieselben Bits trägt.
    matrix = (
        translation(origin)
        @ rotation_between((0.0, 0.0, 1.0), direction)
        @ rotation_about((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), params.start_angle)
    )
    return _cut_with_tool(ctx, _placed(tool, matrix, ctx.cancelled), findings, seed=ctx.seed)


#: Die drei Hauptrichtungen, die eine Drehachse ohne gewähltes Merkmal haben kann.
_AXIS_DIRECTIONS: dict[str, tuple[float, float, float]] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


def _revolve_axis(
    source: SceneObject, params: SketchRevolveCutParams
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Punkt und Richtung der Drehachse — aus den Feldern oder aus einem runden Merkmal.

    **Mit Merkmal gilt seine Achse, und der Achspunkt wird auf sie gelegt.**
    Er sagt dann nur noch, wo entlang der Achse der Querschnitt beginnt: Wer
    an einer stehenden Welle „Achspunkt Z = 18" einträgt, bekommt die Nut auf
    18 mm Höhe, gleich wo die Welle in X und Y steht. Das Vorzeichen der Achse
    kommt aus :func:`app.core.units.positive_axis` — dieselbe Wahl, die beide
    Kerne für Bohrungen treffen.
    """
    point = (params.axis_x, params.axis_y, params.axis_z)
    if not params.axis_feature:
        return point, _AXIS_DIRECTIONS[params.axis]
    feature = source.features.get(params.axis_feature)
    raw_axis = feature.params.get("axis") if feature is not None else None
    raw_centre = feature.params.get("centre") if feature is not None else None
    if feature is None or raw_axis is None or raw_centre is None:
        raise ValidationError(
            "axis_feature",
            _(
                "Dieses Merkmal hat keine Achse. Wählen Sie eine Bohrung oder einen Zapfen, "
                "oder lassen Sie das Feld leer und geben die Achse von Hand an."
            ),
            value=params.axis_feature,
            constraint="no_axis",
            suggestions=(
                Action("sketch.pick_round_feature", _("Ein rundes Merkmal wählen"), primary=True),
                Action("sketch.clear_axis_feature", _("Die Achse von Hand angeben")),
            ),
        )
    direction = positive_axis([float(value) for value in raw_axis])
    centre = [float(value) for value in raw_centre]
    along = sum((point[k] - centre[k]) * direction[k] for k in range(3))
    return (
        (
            centre[0] + along * direction[0],
            centre[1] + along * direction[1],
            centre[2] + along * direction[2],
        ),
        direction,
    )


@op_params
class SketchSweepCutParams(BaseParams):
    shape: str = param(
        title=_("Grundform"),
        default="circle",
        choices=shapes.SHAPE_CHOICES,
        doc=_SHAPE_DOC,
        placement="advanced",
    )
    length: float = param(
        title=_("Länge"),
        default=4.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_LENGTH_DOC,
        placement="advanced",
    )
    width: float = param(
        title=_("Breite"),
        default=4.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
        placement="advanced",
    )
    along: str = param(
        title=_("Bahn"),
        default="arc",
        choices=("arc", "drawn"),
        doc=_(
            "Woran der Querschnitt entlangläuft: an einem Bogen aus zwei Zahlen oder an "
            "einer gezeichneten Bahn. Ein gebogener Kanal braucht keine Zeichnung; einer um "
            "zwei Ecken schon."
        ),
    )
    bend_radius: float = param(
        title=_("Bogenradius"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_(
            "Radius des Pfades, dem der Querschnitt folgt. Er muss größer sein "
            "als der halbe Querschnitt, sonst knickt die Innenseite."
        ),
        depends_on=("along", ("arc",)),
    )
    bend_angle: float = param(
        title=_("Bogenwinkel"),
        default=90.0,
        unit=DEGREE_UNIT,
        minimum=1.0,
        maximum=180.0,
        doc=_("Wie weit der Bogen führt — 90 Grad lenkt den Kanal von senkrecht auf waagerecht."),
        depends_on=("along", ("arc",)),
        placement="advanced",
    )
    # **Die Skizze steht vor der Bahn**, anders als beim Erzeuger: Wer frei
    # zeichnet und „Fertig" wählt, hat einen geschlossenen Umriss gezeichnet,
    # und der ist der Querschnitt (``main_window._sketch_param``).
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )
    path_sketch: str = param(
        title=_("Gezeichnete Bahn"),
        default="",
        kind="sketch",
        doc=_(
            "Der Verlauf, dem der Querschnitt folgt — offen gezeichnet, auf der "
            "Vorder- oder Seitenansicht und am Anfang senkrecht nach oben oder unten. "
            "Ihr Anfang kommt in den Ursprung: Die Bahn beschreibt einen Verlauf, keinen Ort."
        ),
        depends_on=("along", ("drawn",)),
    )
    heading: str = param(
        title=_("Anfangsrichtung"),
        default="down",
        choices=("down", "up"),
        placement="advanced",
        doc=_(
            "Ob der Kanal von oben nach unten in den Körper läuft oder von unten nach oben. "
            "Eine Bahn, die schon so beginnt, bleibt, wie sie ist; sonst wird sie als Ganzes "
            "umgedreht."
        ),
    )
    x: float = param(
        title=_("X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Wo der Kanal beginnt, in X."),
    )
    y: float = param(
        title=_("Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Wo der Kanal beginnt, in Y."),
    )
    z: float | None = param(
        title=_("Z"),
        default=None,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        optional=True,
        placement="advanced",
        doc=_(
            "Auf welcher Höhe der Kanal beginnt. Leer heißt: an der Oberseite des Körpers, "
            "wenn er nach unten läuft, an der Unterseite, wenn er nach oben läuft."
        ),
    )
    turn: float = param(
        title=_("Drehung"),
        default=0.0,
        unit=DEGREE_UNIT,
        minimum=0.0,
        maximum=360.0,
        placement="advanced",
        doc=_(
            "Dreht die Bahn um die Senkrechte durch ihren Anfang. Bei null biegt ein Bogen "
            "nach +X ab, bei 90 nach +Y."
        ),
    )
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
        depends_on=("shape", ("polygon",)),
    )


@register_op(
    name="sketch_sweep_cut",
    title=_("Entlang einer Bahn schneiden"),
    cache_version=PROFILE_REVISION,
    category="sketch",
    params=SketchSweepCutParams,
    consumes=1,
    produces=1,
    deterministic=False,
    caveat=_MESH_CUT_CAVEAT,
    doc=_(
        "Führt einen Querschnitt entlang eines Bogens oder einer gezeichneten Bahn und "
        "nimmt ihn aus dem gewählten Körper heraus. Das ergibt einen geführten Kanal, der oben "
        "beginnt und seitlich austreten kann."
    ),
)
def sketch_sweep_cut(ctx: OpContext) -> OpResult:
    params = cast(SketchSweepCutParams, ctx.params)
    findings: list[Finding] = []
    tool, upward = _swept(ctx, params, findings)
    from app.core.geom.transform import rotation_about, translation

    # Der geführte Körper des Erzeugers beginnt im Ursprung, senkrecht nach oben
    # oder — bei einer so gezeichneten Bahn — nach unten. Zeigt er anders als
    # gewünscht, wird er um die Achse gedreht, die in seiner Bahnebene quer
    # liegt: X bei Bogen und Vorderansicht, Y bei der Seitenansicht. So bleibt
    # die Bahn in ihrer Ebene und biegt weiter zur selben Seite ab; gespiegelt
    # wird nur der Querschnitt quer zur Bahnebene. Dann um die Senkrechte, dann
    # an den Anfang.
    down = params.heading == "down"
    across = (
        (0.0, 1.0, 0.0)
        if params.along == "drawn" and _plane_of(params.path_sketch) == "plane:yz"
        else (1.0, 0.0, 0.0)
    )
    low, high = _span_along(ctx.inputs[0].mesh, (0.0, 0.0, 1.0))
    start_z = params.z if params.z is not None else (high if down else low)
    matrix = (
        translation((params.x, params.y, start_z))
        @ rotation_about((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), params.turn)
        @ rotation_about(across, (0.0, 0.0, 0.0), 180.0 if down == upward else 0.0)
    )
    return _cut_with_tool(ctx, _placed(tool, matrix, ctx.cancelled), findings, seed=ctx.seed)


@op_params
class SketchLoftCutParams(BaseParams):
    shape: str = param(
        title=_("Grundform"),
        default="rectangle",
        choices=shapes.SHAPE_CHOICES,
        doc=_SHAPE_DOC,
        placement="advanced",
    )
    length: float = param(
        title=_("Länge"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_LENGTH_DOC,
        placement="advanced",
    )
    width: float = param(
        title=_("Breite"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
        placement="advanced",
    )
    # Vor der Tiefe und vorn: Der Haken schaltet sie aus (``depends_on``).
    through: bool = param(
        title=_("Durchgehend"),
        default=False,
        doc=_(
            "Reicht von der Oberkante bis zur gegenüberliegenden Seite des Körpers — der "
            "untere Umriss liegt dann genau dort, die Tiefe zählt nicht."
        ),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Wie tief der Übergang von der Oberkante aus reicht; dort liegt der untere Umriss."),
        depends_on=("through", (False,)),
    )
    top: str = param(
        title=_("Unterer Umriss"),
        default="scaled",
        choices=("scaled", "drawn"),
        doc=_(
            "Woher der Umriss am Ende des Übergangs kommt: aus dem oberen gerechnet oder "
            "als eigene Zeichnung. Ein Trichter braucht nur eine Zahl; ein Übergang von "
            "eckig auf rund braucht zwei Umrisse."
        ),
        placement="advanced",
    )
    top_scale: float = param(
        title=_("Verjüngung"),
        default=0.5,
        minimum=0.05,
        maximum=2.0,
        doc=_(
            "Größe des unteren Umrisses im Verhältnis zum oberen. 0,5 halbiert ihn — ein "
            "Trichter; über 1 wird der Übergang nach unten weiter."
        ),
        depends_on=("top", ("scaled",)),
        placement="advanced",
    )
    top_sketch: str = param(
        title=_("Untere Zeichnung"),
        default="",
        kind="sketch",
        doc=_(
            "Der Umriss am Ende des Übergangs, frei gezeichnet — auf derselben Ebene wie der "
            "obere und um die Tiefe darunter aufgespannt."
        ),
        depends_on=("top", ("drawn",)),
        placement="advanced",
    )
    x: float = param(
        title=_("X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Mitte des Übergangs in der Zeichenebene, in deren x-Richtung."),
    )
    y: float = param(
        title=_("Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Mitte des Übergangs in der Zeichenebene, in deren y-Richtung."),
    )
    z: float = param(
        title=_("Oberkante"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        doc=_(
            "Wo der Übergang oben beginnt, gemessen senkrecht zur Zeichenebene. Null heißt: "
            "an der Oberseite des Körpers."
        ),
    )
    twist: str = param(
        title=_("Drehsinn"),
        default="ask_twist",
        choices=("ask_twist", "counterclockwise", "clockwise"),
        placement="advanced",
        doc=_(
            "Nur wenn der untere Umriss genau zwischen zwei Ecken des oberen verdreht ist: "
            "in welche Richtung der Übergang dreht. Sonst verbinden sich die nächsten Ecken."
        ),
    )
    corners: int = param(
        title=_("Ecken"),
        default=6,
        minimum=3,
        maximum=64,
        placement="advanced",
        doc=_CORNERS_DOC,
        depends_on=("shape", ("polygon",)),
    )
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )


@register_op(
    name="sketch_loft_cut",
    title=_("Durch Überblenden schneiden"),
    cache_version=PROFILE_REVISION,
    category="sketch",
    params=SketchLoftCutParams,
    consumes=1,
    produces=1,
    deterministic=False,
    caveat=_MESH_CUT_CAVEAT,
    doc=_(
        "Nimmt einen Übergang zwischen zwei Umrissen aus dem gewählten Körper heraus. Oben "
        "liegt die Grundform oder Zeichnung, in der Tiefe ihre verkleinerte Kopie oder eine "
        "zweite Zeichnung: ein Trichter, ein Kanal von eckig auf rund."
    ),
)
def sketch_loft_cut(ctx: OpContext) -> OpResult:
    params = cast(SketchLoftCutParams, ctx.params)
    findings: list[Finding] = []
    require()
    plane, pairs = _loft_outlines(ctx, params, findings)
    answered: dict[str, Any] = {}
    span = _cut_span(ctx, ctx.inputs[0].mesh, plane, params.z)
    # Durchgehend reicht **genau** von Fläche zu Fläche und nicht darüber
    # hinaus wie bei der Tasche: Die beiden Umrisse sollen dort liegen, wo der
    # Körper aufhört — sonst stünde an der Fläche ein Zwischenquerschnitt statt
    # des gezeichneten.
    bottom = span.low if params.through else span.top - params.depth
    reach = span.top - bottom
    lift = bottom - span.plane_s
    tools = []
    for entry, end in pairs:
        ctx.cancelled.raise_if_cancelled()
        entry_at = shifted(entry, params.x, params.y)
        end_at, aligned = _paired_corners(
            entry_at, shifted(end, params.x, params.y), params.twist, ctx, answered
        )
        body = profiles.loft(end_at, entry_at, reach, plane, span.frame, compatible=not aligned)
        normal = span.normal
        tools.append(edit.moved(body, (normal[0] * lift, normal[1] * lift, normal[2] * lift)))
    tool = tools[0] if len(tools) == 1 else edit.boolean("union", tools)
    ctx.cancelled.raise_if_cancelled()
    if profiles.intersects_itself(tool):
        raise GeometryError(
            detail=_(
                "Zwischen diesen beiden Umrissen verdreht sich der Übergang so, dass er sich "
                "selbst schneidet. Zeichnen Sie den unteren Umriss näher am oberen oder mit "
                "gleich vielen Ecken."
            ),
            suggestions=(Action("open_sketch", _("Skizze ansehen"), primary=True), CORRECT_INPUT),
            values={"reason": "tool_intersects_itself"},
        )
    result = _cut_with_tool(ctx, tool, findings, seed=ctx.seed)
    return dataclasses.replace(result, answered=answered)


def _paired_corners(
    entry: Profile,
    end: Profile,
    twist: str,
    ctx: OpContext,
    answered: dict[str, Any],
) -> tuple[Profile, bool]:
    """Ordnet die Ecken des unteren Umrisses denen des oberen zu — ohne zu raten.

    **Die Zuordnung ist die Verdrehung.** Zwei Vielecke mit gleich vielen
    Ecken lassen sich auf so viele Arten verbinden, wie sie Ecken haben; der
    Übergang dreht sich dabei jedes Mal anders. Welche Ecke zuerst gezeichnet
    wurde und in welcher Richtung, ist Zufall der Klickreihenfolge — daraus
    wird nichts gelesen. Verbunden werden die **nächsten** Ecken, gemessen
    um die Mitte jedes Umrisses (eine versetzte Öffnung dreht nicht).

    **Stehen zwei Zuordnungen gleich nah**, sagt die Zeichnung nicht, welche
    gemeint ist: ein Quadrat über einem um 45 Grad gedrehten dreht links- oder
    rechtsherum, und beide Körper sind Spiegelbilder. Dann wird gefragt
    (Regel 21), und die Antwort reist mit dem Schritt (``answered``).
    OpenCASCADE entschiede den Gleichstand selbst — nach der letzten Stelle
    einer Summe, also auf verschiedenen Maschinen womöglich verschieden.

    Zurück kommt der untere Umriss in der gewählten Zuordnung und ob sie
    gesetzt ist; für Kreise, Bögen, Splines und ungleiche Eckenzahl ordnet
    weiter der Kern (``profiles.loft(compatible=True)``).
    """
    if not (_is_polygon(entry) and _is_polygon(end)) or len(entry.segments) != len(end.segments):
        return end, False
    upper = [segment.start for segment in entry.segments]
    lower = [segment.start for segment in end.segments]
    if (signed_area(entry) >= 0.0) != (signed_area(end) >= 0.0):
        lower.reverse()
    upper_mid, lower_mid = _mean_point(upper), _mean_point(lower)
    count = len(upper)
    candidates = []
    for shift in range(count):
        squares = []
        turns = []
        for index in range(count):
            a = (upper[index][0] - upper_mid[0], upper[index][1] - upper_mid[1])
            b = lower[(index + shift) % count]
            b = (b[0] - lower_mid[0], b[1] - lower_mid[1])
            squares.append((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
            turns.append(math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1]))
        candidates.append((math.sqrt(math.fsum(squares) / count), math.fsum(turns) / count, shift))
    nearest = min(candidate[0] for candidate in candidates)
    tied = [candidate for candidate in candidates if is_close(candidate[0], nearest)]
    if len(tied) == 1:
        chosen = tied[0]
    else:
        sense = twist
        if sense == "ask_twist":
            choices = [
                str(_("Linksherum, gegen den Uhrzeigersinn")),
                str(_("Rechtsherum, im Uhrzeigersinn")),
            ]
            answer = ctx.ask(
                str(
                    _(
                        "Der untere Umriss steht genau zwischen zwei Ecken des oberen. In "
                        "welche Richtung soll der Übergang drehen — von oben auf die "
                        "Zeichenebene gesehen?"
                    )
                ),
                choices,
            )
            if answer not in choices:
                raise InternalError(detail="the twist question returned an unknown choice")
            sense = "counterclockwise" if answer == choices[0] else "clockwise"
            answered["twist"] = sense
        pick = max if sense == "counterclockwise" else min
        chosen = pick(tied, key=lambda candidate: candidate[1])
    shift = chosen[2]
    ordered = [lower[(index + shift) % count] for index in range(count)]
    segments = tuple(
        ProfileSegment("line", ordered[index], ordered[(index + 1) % count])
        for index in range(count)
    )
    return Profile(segments=segments, holes=end.holes), True


def _is_polygon(profile: Profile) -> bool:
    """Ein Umriss aus lauter Strecken — nur dessen Ecken lassen sich abzählen."""
    return (
        profile.circle is None
        and len(profile.segments) >= 3
        and all(segment.kind == "line" for segment in profile.segments)
    )


def _mean_point(points: list[Point2]) -> Point2:
    """Der Eckenmittelpunkt, über ``math.fsum`` auf jeder Maschine dieselbe Zahl."""
    return (
        math.fsum(point[0] for point in points) / len(points),
        math.fsum(point[1] for point in points) / len(points),
    )


def _placed(tool: Solid, matrix: Any, cancelled: CancelToken) -> Solid:
    """Das Werkzeug an seinem Ort — über denselben geprüften Weg wie jede Bewegung."""
    from app.core.geom.ops import as_transform

    return edit.transformed(tool, as_transform(matrix), cancelled=cancelled)


def _cut_with_tool(
    ctx: OpContext, tool: Solid, findings: list[Finding], *, seed: int | None
) -> OpResult:
    """Zieht das Werkzeug vom gewählten Körper ab — exakt, wo er exakt ist, sonst am Netz.

    **Beide Kerne, und keiner wird umgedeutet.** Ein exakter Körper bleibt
    exakt (``brep.edit.boolean``); ein eingelesenes Netz geht über die
    Boolesche Rückfallkette (§17.2) gegen das mit ``units.MAX_FACET_SAG``
    vernetzte Werkzeug — dieselbe Grenze, mit der der exakte Kern tesselliert.
    Die erreichte Stufe steht in ``solver``, die Befunde der Kette reisen mit;
    ``seed`` ist der gespeicherte Startwert der Operation für die gestörte
    Stufe (Regel 9) — ausdrücklich durchgereicht, damit jede der drei
    Operationen sichtbar sagt, dass sie ihn liest.

    **Nichts übrig** ist eine Absage mit Weg, kein Körper ohne Volumen, und
    **nichts abgetragen** ein Befund mit Vorschlag: Das Werkzeug lag neben
    dem Körper, und der Kunde soll nicht in der Geometrie suchen, was an der
    Lage liegt.

    **Und ein ungültiges exaktes Ergebnis wird nicht ausgeliefert**
    (``profiles.is_sound``): Dann rechnet derselbe Schnitt am Netz des
    Körpers weiter, mit dem Befund ``sketch.exact_cut_unsound``; die
    Umwandlung selbst meldet die Auswertung vor der Übernahme.
    """
    from app.core.geom import boolean as mesh_boolean
    from app.core.geom.boolean import NOTHING_LEFT_DETAIL, NOTHING_LEFT_TITLE
    from app.core.geom.mesh import as_mesh_data

    source = ctx.inputs[0]
    body = source.mesh
    ctx.cancelled.raise_if_cancelled()
    output: SceneObject | None = None
    solver: SolverInfo | None = None
    if isinstance(body, Solid):
        solid = edit.boolean("difference", [body, tool])
        ctx.cancelled.raise_if_cancelled()
        if solid.solid_count < 1 or solid.volume <= EPS_GEOM:
            raise GeometryError(
                title=NOTHING_LEFT_TITLE,
                detail=NOTHING_LEFT_DETAIL,
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        if profiles.is_sound(solid):
            output = dataclasses.replace(
                source,
                mesh=solid,
                kind="brep",
                features=features_of(solid, cancelled=ctx.cancelled),
            )
            solver = SolverInfo(strategy="direct", attempted=("direct",))
        else:
            # **Kein ungültiger Körper, auch kein exakter.** Der Schnitt wird
            # dann am Netz des Körpers gerechnet — dieselbe Form, eine andere
            # Darstellung —, und das steht im Bericht: hier der Grund, daneben
            # die Umwandlung, die die Auswertung vor der Übernahme zeigt
            # (``evaluate.exact_became_mesh``). Rückgängig bringt den exakten
            # Körper zurück.
            findings = [
                *findings,
                Finding(
                    code="sketch.exact_cut_unsound",
                    severity="warning",
                    message=_(
                        "Mit Flächen und Kanten ließ sich dieser Schnitt nicht schließen, "
                        "gerechnet wurde am Netz. Strg+Z stellt den Körper wieder her."
                    ),
                    object_id=source.id,
                    suggestions=(CORRECT_INPUT,),
                ),
            ]
    if output is None:
        outcome = mesh_boolean.boolean(
            "difference",
            [as_mesh_data(body), tool.mesh],
            quality=ctx.quality,
            seed=seed,
            allow_empty=True,
            cancelled=ctx.cancelled,
        )
        if outcome.mesh.triangle_count == 0:
            raise GeometryError(
                title=NOTHING_LEFT_TITLE,
                detail=NOTHING_LEFT_DETAIL,
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        findings = [*findings, *outcome.findings]
        # Leeres Wörterbuch, nicht die alten Merkmale: Die Flächen, auf die sie
        # zeigten, hat der Schnitt gerade verändert — wie bei der Tasche.
        output = dataclasses.replace(source, mesh=outcome.mesh, kind="mesh", features={})
        solver = outcome.solver
    nothing = without_effect(body, output.mesh, "difference", ctx.profile)
    if nothing is not None:
        findings = [
            *findings,
            dataclasses.replace(
                nothing,
                object_id=source.id,
                suggestions=(
                    Action("sketch.check_position", _("Lage des Werkzeugs prüfen"), primary=True),
                    CORRECT_INPUT,
                ),
            ),
        ]
    return OpResult(outputs=[output], findings=findings, solver=solver)
