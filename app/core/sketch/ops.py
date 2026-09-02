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
from typing import Any, cast

from app.core.brep import edit, profiles
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, require
from app.core.errors import CORRECT_INPUT, Action, GeometryError, NeedsSolidError, ValidationError
from app.core.geom.boolean import without_effect
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.sketch import planes, shapes
from app.core.sketch.planes import frame_for, frame_of, height_to, is_feature_plane
from app.core.sketch.profile import (
    Profile,
    bounds_of,
    profile_of,
    regions_of,
    scaled,
    shifted,
)
from app.core.sketch.serialize import sketch_from_text
from app.core.sketch.solver import solve_sketch
from app.core.types import BaseParams, OpContext, OpResult, PlaneFrame, SceneObject
from app.core.units import DEGREE_UNIT, EPS_GEOM
from app.i18n import _

#: Ein Satz, den drei Parameterschemata teilen — deshalb steht er einmal hier.
_LENGTH_DOC = _(
    "Länge in X. Beim Kreis und beim Vieleck ist das der Durchmesser, "
    "beim Langloch die Gesamtlänge über die runden Enden."
)
_WIDTH_DOC = _("Breite in Y. Beim Kreis und beim Vieleck ohne Wirkung.")
_SHAPE_DOC = _("Rechteck, Langloch, Kreis oder Vieleck — die Maße stehen darunter.")
_CORNERS_DOC = _("Zahl der Ecken, nur beim Vieleck.")
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
    ctx: OpContext, sketch_text: str, shape: str, length: float, width: float, corners: int
) -> Profile:
    """Gezeichnete Skizze, wenn eine da ist — sonst die Grundform."""
    if sketch_text:
        return _drawn_profile(ctx, sketch_text)
    return _sketch_profile(shape, length, width, corners)


def _created(name: str, fallback: str, solid: Solid) -> SceneObject:
    """Das Ergebnis als Szenenobjekt — nachdem feststeht, dass eines da ist.

    Alle vier Erzeuger-Ops laufen hier durch. Ein Ergebnis ohne Körper wurde
    vorher trotzdem Objekt: unsichtbar, Volumen null, und jeder spätere
    Schritt darauf scheiterte weit weg von der Ursache (Gesamtreview D-8).
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

    **Für die Tasche gilt dieser Fall seit dem 30.08.2026 nicht mehr:**
    ``sketch_pocket`` schneidet auch in ein Netz und ruft diese Funktion nicht
    mehr. Was hier bleibt, sind die Operationen, die wirklich einzeln
    bearbeitbare Flächen brauchen — ``push_face`` und seinesgleichen.
    """
    require()
    source = ctx.inputs[0]
    if not isinstance(source.mesh, Solid):
        raise NeedsSolidError(
            # Ohne Platzhalter: TranslatableText löst nur den Katalog auf und
            # formatiert nicht. Der Name reist wie überall in ``values``.
            detail=_(
                "Der gewählte Körper besteht bereits aus festen Dreiecken. Dieses "
                "Werkzeug braucht einzeln bearbeitbare Flächen und Kanten. Aktiviere "
                "dafür bei einer Grundform oder beim Aushöhlen „Flächen und Kanten "
                "später bearbeiten“ oder öffne eine STEP-Datei."
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
        title=_("Breite"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
    )
    height: float = param(
        title=_("Höhe"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_("Wie hoch der Körper gezogen wird, vom Druckbett nach oben."),
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
    name: str = param(title=_("Name"), default="", placement="advanced", doc=NAME_DOC)
    sketch: str = param(
        title=_("Skizze"), default="", kind="sketch", placement="advanced", doc=_SKETCH_DOC
    )


@register_op(
    name="sketch_extrude",
    title=_("Grundform hochziehen"),
    category="sketch",
    params=SketchExtrudeParams,
    consumes=0,
    produces=1,
    doc=_(
        "Zieht eine Grundform senkrecht hoch, bis ein Körper daraus wird. Der Umriss kommt "
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
        title=_("Breite"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
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
            "Mitte der Tasche in der Zeichenebene, in deren x-Richtung. Eine "
            "angeklickte Fläche trägt den Ort selbst ein."
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
            "Mitte der Tasche in der Zeichenebene, in deren y-Richtung. Eine "
            "angeklickte Fläche trägt den Ort selbst ein."
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
    # Ausgeschrieben statt als ``tuple(...)`` über einen Bereich:
    # ``PlaneFrame`` verlangt genau drei Zahlen, und eine Folge unbekannter
    # Länge ist etwas anderes — mypy sagt das zu Recht.
    lifted = _replace(
        frame,
        origin=(
            frame.origin[0] + frame.normal[0] * top,
            frame.origin[1] + frame.normal[1] * top,
            frame.origin[2] + frame.normal[2] * top,
        ),
    )

    tools = []
    for one in regions:
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
    source = ctx.inputs[0]
    # **Der Körper ist in beiden Fällen derselbe Wert.** ``_span_along`` fragt
    # ihn nach seinen Grenzen und weiß mit beiden Arten umzugehen; ihn hier
    # wegzuwerfen, nur weil er kein ``Solid`` ist, nähme der Rechnung darunter
    # die Spanne, aus der Oberkante und Durchstoß entstehen.
    body = source.mesh
    # **Die Ebene der Zeichnung zählt** — wie bei ``sketch_extrude``, dessen
    # Fix hier fehlte: Auf einer Seitenwand gezeichnet schnitt die Tasche
    # trotzdem von oben (Welt-Z), und eine falsche Ebene sah aus wie eine
    # erfüllte Zusage (Gesamtreview D-2). Gerechnet wird entlang der
    # Ebenen-Normalen; auf XY ist das Welt-Z, und dort ändert sich nichts.
    plane = _plane_of(params.sketch)
    frame = _frame_of(ctx, plane)
    # Alle Umrisse, wie beim Extrudieren: Zwei Taschen in einer Zeichnung sind
    # eine Handlung. Vorher lehnte die Tasche dieselbe Skizze ab, die das
    # Extrudieren rechnete (Gesamtreview D-15).
    chosen = [
        shifted(one, params.x, params.y)
        for one in _regions_for(
            ctx,
            params.sketch,
            params.shape,
            params.length,
            params.width,
            params.corners,
            params.region,
        )
    ]
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
    elif abs(params.z) > EPS_GEOM:
        top = params.z
    else:
        top = high_s
    if params.through:
        bottom, reach = low_s - 1.0, (high_s - low_s) + 2.0
    else:
        bottom, reach = top - params.depth, params.depth + 1.0
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
        return _pocket_in_mesh(ctx, source, chosen, on, top, top - bottom, params.through)

    lifted = bottom - plane_s
    tools = [
        edit.moved(
            profiles.extrude(one, reach, plane, frame),
            (normal[0] * lifted, normal[1] * lifted, normal[2] * lifted),
        )
        for one in chosen
    ]
    tool = tools[0] if len(tools) == 1 else edit.boolean("union", tools)
    solid = edit.boolean("difference", [body, tool])
    # Eine Tasche, die den Körper verfehlt, lief stumm durch: im Verlauf ein
    # Schritt, im Bild dasselbe Teil, und keine Zeile, die das erklärt.
    # Gemessen an vier Fällen — Oberkante unter dem Körper, Ort daneben —, und
    # in allen vieren sagte niemand etwas. Denselben Satz bekommt seit je, wer
    # eine Magnettasche daneben setzt (`geom/boolean.without_effect`).
    nothing = without_effect(body, solid, "difference", ctx.profile)
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
        # den `.claude/rules/oberflaeche.md` unter „Ein Feld ohne Wirkung sagt
        # es" verbietet — und ein Kommentar, der eine Wirkung behauptet, ohne
        # sie gemessen zu haben, ist der Grund, aus dem er zwei Jahre stehen
        # bleibt.
        #
        # Der ``doc``-Satz bleibt vorerst, wie er ist: Er ist ein Katalogtext
        # in fünf Sprachen, und beim Vieleck steht ohnehin der Grund der
        # Sperre an der Zeile statt seiner (``_explain`` in ``op_dialog.py``).
        depends_on=("shape", ("rectangle", "slot")),
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
    require()
    if params.sketch:
        # Wie gezeichnet: die Skizze kennt ihren Abstand zur Achse selbst.
        placed = _drawn_profile(ctx, params.sketch)
    else:
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
        placed = shifted(profile, params.offset - low[0], -low[1])
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
        title=_("Breite"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
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
        title=_("Breite"),
        default=20.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        doc=_WIDTH_DOC,
        depends_on=("shape", ("rectangle", "slot")),
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
    if not params.sketch:
        # Der Weg des Katalogs: zwei Grundformen, die zweite kleiner gerechnet.
        # Er bleibt, weil die Grundformen um den Ursprung zentriert liegen und
        # die Maße direkt aus den Parametern kommen — daran ist nichts zu
        # skalieren.
        bottom = _sketch_profile(params.shape, params.length, params.width, params.corners)
        top = _sketch_profile(
            params.shape,
            params.length * params.top_scale,
            params.width * params.top_scale,
            params.corners,
        )
        solid = profiles.loft(bottom, top, params.height)
        return OpResult(outputs=[_created(params.name, str(_("Übergang")), solid)])

    # **Die gezeichnete Skizze, und ihre eigene verkleinerte Kopie darüber.**
    # Diese Operation war die einzige der fünf ohne Skizzenfeld, und der
    # Fertig-Dialog bot sie trotzdem an: Wer nach dem Zeichnen „Zwischen zwei
    # Umrissen aufspannen" wählte, bekam einen internen Fehler statt eines
    # Körpers.
    #
    # Skaliert wird um den **Mittelpunkt des Umrisses**, nicht um den
    # Ursprung: Eine Grundform liegt zentriert, eine Zeichnung liegt irgendwo,
    # und um den Ursprung verkleinert wanderte sie beim Schrumpfen zum
    # Nullpunkt — aus einem Pyramidenstumpf würde ein schiefer Keil.
    plane = _plane_of(params.sketch)
    frame = _frame_of(ctx, plane)
    chosen = _regions_for(
        ctx, params.sketch, params.shape, params.length, params.width, params.corners, 0
    )
    bodies = []
    for one in chosen:
        low, high = bounds_of(one)
        centre = ((low[0] + high[0]) / 2.0, (low[1] + high[1]) / 2.0)
        bodies.append(
            profiles.loft(one, scaled(one, params.top_scale, centre), params.height, plane, frame)
        )
    solid = bodies[0] if len(bodies) == 1 else edit.boolean("union", bodies)
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
    # ``features_of`` wie bei jeder anderen B-Rep-Op: Mit ``features={}``
    # hatte der Körper nach „Fläche versetzen" keine anklickbaren Flächen
    # mehr — „Auf dieser Fläche zeichnen", die exakte Bohrung und jede
    # Passung liefen ins Leere (Gesamtreview D-5).
    return OpResult(outputs=[dataclasses.replace(source, mesh=moved, features=features_of(moved))])
