"""Behälter mit passenden Deckeln, Einteilungen und herausnehmbaren Einsätzen (§25)."""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Sequence
from typing import Any, cast

from app.core.errors import CANCEL, CORRECT_INPUT, GeometryError, ValidationError
from app.core.geom import transform
from app.core.geom.boolean import BOOLEAN_OVERLAP, DRAFT_CHAIN, boolean, deepest
from app.core.geom.lid import (
    CAP_THREAD_FEATURE,
    CAVITY_FEATURE,
    COLLAR_FEATURE,
    DEFAULT_PITCH,
    NECK_THREAD_FEATURE,
    LidParams,
    ScrewLidParams,
    _helical_faces,
    _triangles,
    create_lid,
    screw_lid,
)
from app.core.geom.lid_hinge import HINGE_HOLE_FEATURE, HINGE_PIN_FEATURE, barrel_halves
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, pin
from app.core.knowledge.parts.containers import rounded_prism
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.registry.params import ZERO_AUTOMATIC, validate
from app.core.types import (
    BaseParams,
    CancelToken,
    Feature,
    Finding,
    OpContext,
    OpResult,
    SceneObject,
    SolverInfo,
)
from app.core.units import EPS_GEOM, exact_cos_degrees, exact_sin_degrees
from app.i18n import _


@op_params
class ContainerParams(BaseParams):
    shape: str = param(
        title=_("Grundform"),
        default="round",
        choices=("round", "rectangular"),
        doc=_("Runder oder rechteckiger Behälter; alle Außenmaße bleiben veränderbar."),
    )
    lid: str = param(
        title=_("Deckelart"),
        default="screw",
        choices=("screw", "push", "hinged"),
        doc=_("Schraubdeckel, Steckdeckel oder ein mitgedrucktes Klappscharnier."),
        placement="advanced",
    )
    diameter: float = param(
        title=_("Durchmesser"),
        default=60.0,
        unit="mm",
        minimum=10.0,
        maximum=2000.0,
        depends_on=("shape", ("round",)),
        doc=_("Außendurchmesser des runden Behälters."),
    )
    width: float = param(
        title=_("Breite"),
        default=80.0,
        unit="mm",
        minimum=10.0,
        maximum=2000.0,
        depends_on=("shape", ("rectangular",)),
        doc=_("Außenbreite des rechteckigen Behälters."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=60.0,
        unit="mm",
        minimum=10.0,
        maximum=2000.0,
        depends_on=("shape", ("rectangular",)),
        doc=_("Außentiefe des rechteckigen Behälters."),
    )
    height: float = param(
        title=_("Höhe"),
        default=40.0,
        unit="mm",
        minimum=2.0,
        maximum=2000.0,
        doc=_("Höhe des Behälters bis zum Rand; Hals und Deckel kommen darüber."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=3.0,
        unit="mm",
        minimum=0.4,
        maximum=100.0,
        doc=_("Dicke der Außenwand und der Trennwände."),
        placement="advanced",
    )
    floor: float = param(
        title=_("Bodenstärke"),
        default=3.0,
        unit="mm",
        minimum=0.4,
        maximum=100.0,
        placement="advanced",
        doc=_("Dicke des geschlossenen Bodens."),
    )
    radius: float = param(
        title=_("Außenradius"),
        default=8.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        placement="advanced",
        depends_on=("shape", ("rectangular",)),
        doc=_("Rundet die senkrechten Außenecken. Der Innenradius erhält die Wandstärke."),
    )
    thickness: float = param(
        title=_("Deckelstärke"),
        default=2.4,
        unit="mm",
        minimum=0.8,
        maximum=50.0,
        placement="advanced",
        doc=_("Dicke der Deckelplatte über dem Innenraum."),
    )
    collar: float = param(
        title=_("Kragentiefe"),
        default=4.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        placement="advanced",
        depends_on=("lid", ("push",)),
        doc=_("Wie weit der Steckdeckel in die Öffnung reicht."),
    )
    thread_height: float = param(
        title=_("Gewindehöhe"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=100.0,
        placement="advanced",
        depends_on=("lid", ("screw",)),
        doc=_("Höhe des Gewindehalses über dem Behälterrand."),
    )
    pitch: float = param(
        title=_("Steigung"),
        default=DEFAULT_PITCH,
        unit="mm",
        minimum=1.0,
        maximum=10.0,
        placement="advanced",
        depends_on=("lid", ("screw",)),
        doc=_("Abstand benachbarter Gewindegänge entlang der Achse."),
    )
    cap_wall: float = param(
        title=_("Wandstärke des Deckels"),
        default=2.4,
        unit="mm",
        minimum=0.8,
        maximum=20.0,
        placement="advanced",
        depends_on=("lid", ("screw",)),
        doc=_("Dicke des Rands um das Deckelgewinde."),
    )
    neck: float = param(
        title=_("Halsdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2000.0,
        placement="advanced",
        depends_on=("lid", ("screw",)),
        doc=_("Null nimmt die schmalere Seite der Öffnung."),
        zero_text=ZERO_AUTOMATIC,
    )
    rows: int = param(
        title=_("Reihen"),
        default=1,
        minimum=1,
        maximum=50,
        placement="advanced",
        doc=_("Zahl der Fächer hintereinander; eins lässt diese Richtung ungeteilt."),
    )
    columns: int = param(
        title=_("Spalten"),
        default=1,
        minimum=1,
        maximum=50,
        placement="advanced",
        doc=_("Zahl der Fächer nebeneinander; eins lässt diese Richtung ungeteilt."),
    )
    divider_height: float = param(
        title=_("Trennwandhöhe"),
        default=0.0,
        minimum=0.0,
        maximum=2000.0,
        unit="mm",
        placement="advanced",
        doc=_("Höhe über dem Innenboden. Null lässt Platz für den Deckel."),
        zero_text=ZERO_AUTOMATIC,
    )
    holes: bool = param(
        title=_("Streulöcher"),
        default=False,
        placement="advanced",
        doc=_("Bohrt einen Kreis aus Durchgangslöchern in die Deckelplatte."),
    )
    hole_diameter: float = param(
        title=_("Lochdurchmesser"),
        default=2.0,
        minimum=0.4,
        maximum=100.0,
        unit="mm",
        placement="advanced",
        depends_on=("holes", (True,)),
        doc=_("Durchmesser der Streulöcher im Deckel."),
    )
    hole_count: int = param(
        title=_("Anzahl der Streulöcher"),
        default=7,
        minimum=1,
        maximum=64,
        placement="advanced",
        depends_on=("holes", (True,)),
        doc=_("Gleichmäßig auf dem Lochkreis verteilte Durchgangslöcher."),
    )
    hole_radius: float = param(
        title=_("Lochkreisradius"),
        default=0.0,
        minimum=0.0,
        maximum=1000.0,
        unit="mm",
        placement="advanced",
        depends_on=("holes", (True,)),
        doc=_("Abstand der Löcher zur Deckelmitte. Null verwendet ein Viertel der Innenweite."),
        zero_text=ZERO_AUTOMATIC,
    )
    hinge_width: float = param(
        title=_("Scharnierbreite"),
        default=24.0,
        minimum=8.0,
        maximum=120.0,
        unit="mm",
        placement="advanced",
        depends_on=("lid", ("hinged",)),
        doc=_("Gesamtbreite über beide Laschen, längs der Achse gemessen."),
    )
    hinge_pin: float = param(
        title=_("Scharnierbolzen"),
        default=4.0,
        minimum=2.0,
        maximum=20.0,
        unit="mm",
        placement="advanced",
        depends_on=("lid", ("hinged",)),
        doc=_("Durchmesser der mitgedruckten Scharnierachse."),
    )
    hinge_reach: float = param(
        title=_("Scharnierausladung"),
        default=12.0,
        minimum=4.0,
        maximum=60.0,
        unit="mm",
        placement="advanced",
        depends_on=("lid", ("hinged",)),
        doc=_("Wie weit jede Lasche von der Achse wegsteht — der Hebel des Gelenks."),
    )
    hinge_wall: float = param(
        title=_("Scharnierwand"),
        default=2.5,
        minimum=1.0,
        maximum=15.0,
        unit="mm",
        placement="advanced",
        depends_on=("lid", ("hinged",)),
        doc=_("Materialdicke um das Scharnierauge."),
    )
    opening_angle: float = param(
        title=_("Öffnungswinkel"),
        default=180.0,
        minimum=0.0,
        maximum=180.0,
        unit="°",
        placement="advanced",
        depends_on=("lid", ("hinged",)),
        doc=_("Null schließt den Klappdeckel, 180 Grad klappt ihn vollständig auf."),
    )
    kernel: str = param(
        title=_("Geometrie"),
        default="auto",
        choices=("auto", "mesh", "brep"),
        placement="advanced",
        internal=True,
        doc=_(
            "Ob der Behälter als Dreiecksnetz oder mit echten Flächen und Kanten gerechnet wird."
        ),
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=NAME_DOC)


@op_params
class ContainerWizardParams(ContainerParams):
    insert: bool = param(
        title=_("Herausnehmbarer Einsatz"),
        default=False,
        placement="advanced",
        doc=_("Die Fächer entstehen in einem eigenen Einsatz mit Spiel zur Außenwand."),
    )


def _invalid(field: str, detail: Any) -> ValidationError:
    return ValidationError(
        field=field,
        constraint="container_dimensions",
        detail=detail,
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def _dimensions(params: ContainerParams) -> tuple[float, float]:
    width, depth = (
        (params.diameter, params.diameter)
        if params.shape == "round"
        else (params.width, params.depth)
    )
    if min(width, depth) <= 2 * params.wall + EPS_GEOM:
        raise _invalid(
            "wall",
            _(
                "Die Wandstärke lässt keinen Innenraum. Vergrößern Sie den Behälter "
                "oder verringern Sie die Wandstärke."
            ),
        )
    if params.floor >= params.height - EPS_GEOM:
        raise _invalid(
            "floor", _("Die Bodenstärke erreicht die Gesamthöhe. Verringern Sie die Bodenstärke.")
        )
    if params.shape == "rectangular" and 2 * params.radius > min(width, depth) + EPS_GEOM:
        raise _invalid("radius", _("Der Außenradius ist zu groß. Verkleinern Sie den Radius."))
    return width, depth


class _Build:
    """Eine Rückfallkette und dieselben Abbruchprüfungen für alle Teile des Entwurfs."""

    def __init__(self, ctx: OpContext, *, seed: int | None) -> None:
        self.ctx = ctx
        # Die Rückfallkette darf zufällig sein (Regel 9): Der Startwert kommt
        # ausdrücklich von der Operation, die ihn gespeichert führt.
        self.seed = seed
        self.solvers: list[SolverInfo | None] = []
        self.findings: list[Finding] = []

    def cut(self, kind: str, forms: Sequence[shapes.Form]) -> shapes.Form:
        self.ctx.cancelled.raise_if_cancelled()
        if len(forms) == 1:
            return forms[0]
        if isinstance(forms[0], MeshData):
            result = boolean(
                cast(Any, kind),
                [as_mesh_data(form) for form in forms],
                quality=self.ctx.quality,
                seed=self.seed,
                stages=DRAFT_CHAIN if self.ctx.quality == "draft" else None,
                cancelled=self.ctx.cancelled,
            )
            self.solvers.append(result.solver)
            self.findings.extend(result.findings)
            built: shapes.Form = result.mesh
        else:
            from app.core.brep.edit import boolean as exact_boolean

            built = exact_boolean(cast(Any, kind), cast(Any, list(forms)))
        self.ctx.cancelled.raise_if_cancelled()
        if not built.is_watertight or built.volume <= EPS_GEOM:
            raise GeometryError(
                detail=_(
                    "Der Behälter ergibt keinen geschlossenen Körper. "
                    "Prüfen Sie Wandstärke und Einbauten."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        return built


def _form(
    params: ContainerParams, width: float, depth: float, height: float, radius: float
) -> shapes.Form:
    if params.shape == "round":
        return shapes.cylinder(width, height)
    return rounded_prism(width, depth, height, radius)


def _housing(params: ContainerParams, build: _Build) -> tuple[shapes.Form, shapes.Form]:
    width, depth = _dimensions(params)
    outside = _form(params, width, depth, params.height, params.radius)
    cavity = shapes.moved(
        _form(
            params,
            width - 2 * params.wall,
            depth - 2 * params.wall,
            params.height - params.floor + BOOLEAN_OVERLAP,
            max(0.0, params.radius - params.wall),
        ),
        (0.0, 0.0, params.floor),
    )
    return build.cut("difference", (outside, cavity)), cavity


def _features(
    form: shapes.Form, cancelled: CancelToken, previous: dict[str, Feature] | None = None
) -> dict[str, Feature]:
    """Aktuelle Topologie plus unveränderte Passungsmaße der gezielten Innenbearbeitung."""
    carried = {
        name: dataclasses.replace(feature, face_indices=(), surface_patches=())
        for name, feature in (previous or {}).items()
        if name in (CAP_THREAD_FEATURE, CAVITY_FEATURE, COLLAR_FEATURE, NECK_THREAD_FEATURE)
    }
    if isinstance(form, MeshData):
        return carried
    from app.core.brep.features import features_of

    threads = []
    for feature in carried.values():
        if feature.kind != "thread":
            continue
        above = (
            None
            if feature.params["internal"]
            else feature.params["centre"][2] - feature.params["length"] / 2
        )
        indices = _triangles(form, _helical_faces(form, above=above))
        if not indices:
            raise GeometryError(
                detail=_(
                    "Das Deckelgewinde wurde durch die Einbauten unterbrochen. "
                    "Ändern Sie die Einbauten."
                ),
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        threads.append(dataclasses.replace(feature, face_indices=indices))
    return {
        **features_of(form, cancelled=cancelled, known_threads=threads or None),
        **{name: feature for name, feature in carried.items() if feature.kind != "thread"},
    }


def _divided(
    body: SceneObject, cavity: shapes.Form, params: ContainerParams, build: _Build, clearance: float
) -> SceneObject:
    if params.rows == 1 and params.columns == 1:
        return body
    width, depth = _dimensions(params)
    inside = (width - 2 * params.wall, depth - 2 * params.wall)
    if any(
        (span - (count - 1) * params.wall) / count <= EPS_GEOM
        for span, count in zip(inside, (params.columns, params.rows), strict=True)
    ):
        raise _invalid(
            "rows",
            _(
                "Die Trennwände lassen keine offenen Fächer. "
                "Wählen Sie weniger Fächer oder einen größeren Behälter."
            ),
        )
    maximum = (
        params.height - params.floor - clearance - (params.collar if params.lid == "push" else 0.0)
    )
    height = params.divider_height or maximum
    if height <= EPS_GEOM or height > maximum + EPS_GEOM:
        raise _invalid(
            "divider_height",
            _(
                "Die Trennwände reichen in den Deckel. "
                "Verringern Sie ihre Höhe oder erhöhen Sie den Behälter."
            ),
        )
    walls: list[shapes.Form] = []
    for count, span, across in ((params.columns, inside[0], False), (params.rows, inside[1], True)):
        for index in range(1, count):
            build.ctx.cancelled.raise_if_cancelled()
            coordinate = -span / 2 + index * (span + params.wall) / count - params.wall / 2
            wall = shapes.box(
                width if across else params.wall,
                params.wall if across else depth,
                height + BOOLEAN_OVERLAP,
            )
            wall = shapes.moved(
                wall,
                (
                    0.0 if across else coordinate,
                    coordinate if across else 0.0,
                    params.floor - BOOLEAN_OVERLAP,
                ),
            )
            walls.append(build.cut("intersection", (wall, cavity)))
    made = build.cut("union", (cast(shapes.Form, body.mesh), *walls))
    return dataclasses.replace(
        body, mesh=made, features=_features(made, build.ctx.cancelled, body.features)
    )


def _perforated(cap: SceneObject, params: ContainerParams, build: _Build) -> SceneObject:
    if not params.holes:
        return cap
    bounds = cap.mesh.bounds
    width = min(bounds.size[0], bounds.size[1])
    radius = params.hole_radius or width / 4.0
    if params.hole_count == 1 and not params.hole_radius:
        radius = 0.0
    edge = params.cap_wall if params.lid == "screw" else params.wall
    if radius + params.hole_diameter / 2.0 + edge >= width / 2.0 - EPS_GEOM:
        raise _invalid(
            "hole_radius",
            _(
                "Die Streulöcher treffen den Deckelrand. "
                "Verkleinern Sie Lochkreis oder Lochdurchmesser."
            ),
        )
    if (
        params.hole_count > 1
        and 2 * radius * exact_sin_degrees(180 / params.hole_count)
        <= params.hole_diameter + EPS_GEOM
    ):
        raise _invalid(
            "hole_count",
            _(
                "Die Streulöcher überschneiden sich. "
                "Wählen Sie weniger Löcher oder einen größeren Lochkreis."
            ),
        )
    centre = bounds.centre
    cutters = [
        shapes.moved(
            shapes.cylinder(params.hole_diameter, bounds.size[2] + 2 * BOOLEAN_OVERLAP),
            (
                centre[0] + radius * exact_cos_degrees(360 * index / params.hole_count),
                centre[1] + radius * exact_sin_degrees(360 * index / params.hole_count),
                bounds.minimum[2] - BOOLEAN_OVERLAP,
            ),
        )
        for index in range(params.hole_count)
    ]
    made = build.cut("difference", (cast(shapes.Form, cap.mesh), *cutters))
    return dataclasses.replace(
        cap, mesh=made, features=_features(made, build.ctx.cancelled, cap.features)
    )


def _hinged(
    body: SceneObject,
    cap: SceneObject,
    params: ContainerParams,
    build: _Build,
    clearance: float,
    cavity: shapes.Form,
) -> tuple[SceneObject, SceneObject]:
    """Das vorhandene Bolzenscharnier an zwei getrennten, gemeinsam drehbaren Laschen."""
    width, depth = _dimensions(params)
    gap = clearance / 2.0
    radius = params.hinge_pin / 2 + gap + params.hinge_wall
    reach = params.hinge_reach
    if params.hinge_width >= width - 2 * params.wall or reach <= radius + gap + EPS_GEOM:
        raise _invalid(
            "hinge_width",
            _(
                "Das Scharnier passt nicht an diesen Behälter. Verringern Sie die Breite "
                "oder vergrößern Sie Behälter und Ausladung."
            ),
        )
    if params.thickness <= gap + EPS_GEOM:
        raise _invalid(
            "thickness",
            _("Die Deckelplatte erreicht die Scharnierlasche nicht. Erhöhen Sie die Deckelstärke."),
        )
    # Dieselben zwei Hälften wie am Konturdeckel mit Scharnier (``lid_hinge``).
    halves = barrel_halves(
        params.hinge_pin,
        params.hinge_width,
        reach,
        params.hinge_wall,
        gap,
        cancelled=build.ctx.cancelled,
    )
    axis = (0.0, depth / 2 + radius + gap, params.height + radius + gap)
    left = shapes.moved(halves[0], (0.0, -reach, -radius))
    left = shapes.moved(shapes.turned(left, 90.0, (1.0, 0.0, 0.0)), axis)
    right = shapes.moved(halves[1], (0.0, axis[1] - reach, axis[2] - radius))
    half = (params.hinge_width - gap) / 2
    inset = params.wall
    if params.shape == "round":
        body_radius, half_width = width / 2, params.hinge_width / 2
        inset += body_radius - math.sqrt(body_radius * body_radius - half_width * half_width)
    inner, outer = depth / 2 - inset, axis[1] + radius
    height = min(params.height, reach - radius - gap)
    tab = shapes.moved(
        shapes.box(half, outer - inner, height),
        (-(params.hinge_width - half) / 2, (inner + outer) / 2, params.height - height),
    )
    # Die Lasche darf die nutzbare Öffnung nicht verkleinern. Am runden
    # Gehäuse ragt ihr rechteckiger Anschluss sonst in einen Einsatz.
    tab = build.cut("difference", (tab, cavity))
    container = build.cut("union", (cast(shapes.Form, body.mesh), tab, left))
    cover = build.cut("union", (cast(shapes.Form, cap.mesh), right))
    body_features = {
        **_features(container, build.ctx.cancelled),
        HINGE_PIN_FEATURE: pin(
            HINGE_PIN_FEATURE,
            params.hinge_pin,
            axis,
            length=params.hinge_width,
            axis=(1.0, 0.0, 0.0),
        )[1],
    }
    cap_features = {
        **_features(cover, build.ctx.cancelled),
        HINGE_HOLE_FEATURE: bore(
            HINGE_HOLE_FEATURE,
            params.hinge_pin + clearance,
            axis,
            depth=half,
            axis=(1.0, 0.0, 0.0),
            through=True,
        )[1],
    }
    body = dataclasses.replace(body, mesh=container, features=body_features)
    cap = dataclasses.replace(cap, mesh=cover, features=cap_features)
    if params.opening_angle:
        cap = transform.moved_object(
            cap,
            transform.rotation_about((1.0, 0.0, 0.0), axis, -params.opening_angle),
            cancelled=build.ctx.cancelled,
        )
    return body, cap


@register_op(
    name="create_container",
    title=_("Behälter mit Deckel"),
    category="primitive",
    params=ContainerParams,
    consumes=0,
    produces=2,
    deterministic=False,
    doc=_(
        "Erzeugt einen runden oder eckigen Behälter "
        "mit passendem Schraub-, Steck- oder Klappdeckel."
    ),
)
def create_container(ctx: OpContext) -> OpResult:
    params = cast(ContainerParams, ctx.params)
    from app.core.brep.kernel import available

    kernel = params.kernel if params.kernel != "auto" else ("brep" if available() else "mesh")
    build = _Build(ctx, seed=ctx.seed)
    clearance = ctx.profile.material.clearance
    with shapes.building(cast(shapes.Kernel, kernel)) as notes:
        form, cavity = _housing(params, build)
        source = SceneObject(
            id="",
            name=params.name or _("Behälter"),
            mesh=form,
            kind=cast(Any, kernel),
            features=_features(form, ctx.cancelled),
        )
        lid_params: BaseParams
        if params.lid == "screw":
            lid_params = validate(
                ScrewLidParams,
                {
                    "height": params.thread_height,
                    "pitch": params.pitch,
                    "thickness": params.thickness,
                    "wall": params.cap_wall,
                    "neck": params.neck,
                },
            )
            made = screw_lid(dataclasses.replace(ctx, inputs=[source], params=lid_params))
        else:
            lid_params = validate(
                LidParams,
                {
                    "thickness": params.thickness,
                    "collar": params.collar if params.lid == "push" else 0.0,
                },
            )
            made = create_lid(dataclasses.replace(ctx, inputs=[source], params=lid_params))
        body, cap = made.outputs
        body = _divided(body, cavity, params, build, clearance)
        cap = _perforated(cap, params, build)
        if params.lid == "hinged":
            body, cap = _hinged(body, cap, params, build, clearance, cavity)
        elif params.lid == "screw":
            # Der einzelne Drehdeckel entsteht am Ursprung. Im gemeinsamen
            # Entwurf sitzt seine offene Unterkante am Beginn des Halses.
            cap = transform.moved_object(
                cap, transform.translation((0.0, 0.0, params.height)), cancelled=ctx.cancelled
            )
        ctx.cancelled.raise_if_cancelled()
    return OpResult(
        outputs=[body, cap],
        solver=deepest([*build.solvers, made.solver]),
        findings=[*notes, *build.findings, *made.findings],
        answered={"kernel": kernel} if params.kernel == "auto" else {},
    )


@op_params
class ContainerInsertParams(BaseParams):
    shape: str = param(
        title=_("Grundform"),
        default="round",
        choices=("round", "rectangular"),
        doc=_("Grundform des Behälters, in den der Einsatz gehört."),
    )
    diameter: float = param(
        title=_("Durchmesser"),
        default=60.0,
        unit="mm",
        minimum=10.0,
        maximum=2000.0,
        depends_on=("shape", ("round",)),
        doc=_("Außendurchmesser des Behälters; Wand und Spiel werden abgezogen."),
    )
    width: float = param(
        title=_("Breite"),
        default=80.0,
        unit="mm",
        minimum=10.0,
        maximum=2000.0,
        depends_on=("shape", ("rectangular",)),
        doc=_("Außenbreite des Behälters; Wand und Spiel werden abgezogen."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=60.0,
        unit="mm",
        minimum=10.0,
        maximum=2000.0,
        depends_on=("shape", ("rectangular",)),
        doc=_("Außentiefe des Behälters; Wand und Spiel werden abgezogen."),
    )
    height: float = param(
        title=_("Höhe"),
        default=40.0,
        unit="mm",
        minimum=2.0,
        maximum=2000.0,
        doc=_("Behälterhöhe; Boden, Deckelraum und Spiel werden abgezogen."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=3.0,
        unit="mm",
        minimum=0.4,
        maximum=100.0,
        placement="advanced",
        doc=_("Wandstärke des Behälters und seines Einsatzes."),
    )
    floor: float = param(
        title=_("Bodenstärke"),
        default=3.0,
        unit="mm",
        minimum=0.4,
        maximum=100.0,
        placement="advanced",
        doc=_("Dicke der beiden Böden."),
    )
    radius: float = param(
        title=_("Außenradius"),
        default=8.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        placement="advanced",
        depends_on=("shape", ("rectangular",)),
        doc=_("Außenradius des Behälters; Wand und Spiel verkleinern den Einsatzradius."),
    )
    rows: int = param(
        title=_("Reihen"),
        default=1,
        minimum=1,
        maximum=50,
        placement="advanced",
        doc=_("Zahl der Fächer hintereinander; eins lässt diese Richtung ungeteilt."),
    )
    columns: int = param(
        title=_("Spalten"),
        default=1,
        minimum=1,
        maximum=50,
        placement="advanced",
        doc=_("Zahl der Fächer nebeneinander; eins lässt diese Richtung ungeteilt."),
    )
    divider_height: float = param(
        title=_("Trennwandhöhe"),
        default=0.0,
        minimum=0.0,
        maximum=2000.0,
        unit="mm",
        placement="advanced",
        doc=_("Höhe über dem Einsatzboden. Null reicht bis zum Einsatzrand."),
        zero_text=_("bis zum Rand", context="Nullwert"),
    )


@register_op(
    name="add_container_insert",
    title=_("Behältereinsatz erzeugen"),
    category="parts",
    params=ContainerInsertParams,
    consumes=2,
    produces=3,
    keeps_inputs=2,
    leaves_inputs_unchanged=True,
    deterministic=False,
    doc=_("Erzeugt einen herausnehmbaren Einsatz mit Fächern und Materialspiel zum Behälter."),
)
def add_container_insert(ctx: OpContext) -> OpResult:
    params = cast(ContainerInsertParams, ctx.params)
    clearance = ctx.profile.material.clearance
    source, cap = ctx.inputs
    raw = params.as_dict()
    for name in ("diameter", "width", "depth"):
        raw[name] = getattr(params, name) - 2 * params.wall - clearance
    # Der aktuelle Deckel ist ein eigener Eingang. Ein späterer Wechsel
    # zwischen Deckelarten ändert damit auch den Platz für den Einsatz.
    ceiling = min(params.height, cap.mesh.bounds.minimum[2])
    raw["height"] = ceiling - params.floor - clearance
    raw["radius"] = max(0.0, params.radius - params.wall - clearance / 2)
    # Die gleichen Formeln wie der Behälter; der Einsatz ist oben offen.
    raw.update(lid="push", collar=0.0)
    inside = validate(ContainerParams, raw)
    build = _Build(ctx, seed=ctx.seed)
    with shapes.building(source.kind) as notes:
        form, cavity = _housing(inside, build)
        body = SceneObject(
            id="",
            name=_("Einsatz"),
            mesh=form,
            kind=source.kind,
            features=_features(form, ctx.cancelled),
        )
        body = _divided(body, cavity, inside, build, 0.0)
        body = transform.moved_object(
            body, transform.translation((0.0, 0.0, params.floor)), cancelled=ctx.cancelled
        )
    return OpResult(
        outputs=[source, cap, body],
        solver=deepest(build.solvers),
        findings=[*notes, *build.findings],
    )
