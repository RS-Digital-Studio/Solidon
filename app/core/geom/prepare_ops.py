"""Operationen für die Druckvorbereitung (Bauplan §25).

Bohren, Teilen, Anordnen und die Kollisionsprüfung. Die letzte ändert gar
keine Geometrie — sie meldet nur, und das ist eine völlig gute Sache für eine
Operation, wenn die Alternative eine Überraschung am Drucker ist.
"""

from __future__ import annotations

import dataclasses
from typing import cast

import trimesh

from app.core.errors import InternalError, ValidationError
from app.core.geom.autosplit import Candidate
from app.core.geom.boolean import boolean
from app.core.geom.hollow import VENT_DIAMETER, hollow
from app.core.geom.mesh import as_mesh_data
from app.core.geom.orient import orient_for_print
from app.core.geom.pins import PIN_COUNT, PIN_MAX, PinnedPair, add_pins, plan_pins
from app.core.geom.prepare import (
    MAX_PLATES,
    arrange_on_bed,
    check_build_volume,
    check_collisions,
    compensate_elephant_foot,
    countersink,
    drill,
    named_for,
    plug,
    split_at_plane,
)
from app.core.geom.section import AXIS_NORMALS, SectionPlane
from app.core.geom.transform import Axis, place_on_bed
from app.core.knowledge.profiles import for_object, material
from app.core.registry import VARIABLE, op_params, param, register_op
from app.core.slice.orientation import DEFAULT_CANDIDATES, search
from app.core.types import BaseParams, Finding, OpContext, OpResult
from app.core.units import EPS_GEOM
from app.i18n import _

_AXES = tuple(AXIS_NORMALS)

#: Erklärungen, die für jede Bohrung dieselben sind. Einmal geschrieben, damit
#: dieselbe Zahl nicht an drei Stellen unterschiedlich erklärt wird.
_WHERE_X = _(
    "Mitte der Bohrung im Koordinatensystem des Objekts. Eine angeklickte "
    "Fläche trägt die drei Werte selbst ein."
)
_WHERE_Y = _("Zweite Achse der Position — siehe Position X.")
_WHERE_Z = _("Dritte Achse der Position — siehe Position X.")
_ALONG = _(
    "Richtung, in die gebohrt wird. Z ist senkrecht von oben, X und Y bohren durch eine Seitenwand."
)


@op_params
class DrillParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        maximum=200.0,
        doc=_(
            "Nenndurchmesser der Bohrung. Für eine Schraube gibt es *Schraubenloch* "
            "in den Bausteinen — dort kommen die Maße aus der Normteiltabelle."
        ),
    )
    x: float = param(title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X)
    y: float = param(title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y)
    z: float = param(title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z)
    axis: str = param(title=_("Achse"), default="z", choices=_AXES, doc=_ALONG)
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_("Null bohrt durch das ganze Teil."),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=True,
        placement="advanced",
        doc=_("Vergrößert die Bohrung um den Wert aus dem Materialprofil."),
    )


@register_op(
    name="drill_hole",
    title=_("Bohrung setzen"),
    category="holes",
    params=DrillParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    touches_features=True,
    deterministic=False,
    shortcut="Ctrl+B",
    doc=_("Bohrt ein rundes Loch — auf Wunsch um die Materialtoleranz vergrößert."),
)
def drill_hole(ctx: OpContext) -> OpResult:
    params = cast(DrillParams, ctx.params)
    source = ctx.inputs[0]
    result = drill(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        depth=params.depth,
        profile=ctx.profile,
        compensate=params.compensate,
        quality=ctx.quality,
        seed=ctx.seed,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class SplitPlaneParams(BaseParams):
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=_AXES,
        doc=_("Senkrecht zu welcher Achse geschnitten wird. Z legt einen waagerechten Schnitt."),
    )
    position: float = param(
        title=_("Position"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wo die Schnittebene liegt, auf dieser Achse gemessen. Die Zahl bleibt "
            "änderbar: ein Doppelklick auf den Schritt verschiebt den Schnitt."
        ),
    )


@register_op(
    name="split_plane",
    title=_("An Ebene teilen"),
    category="prepare",
    params=SplitPlaneParams,
    consumes=1,
    produces=2,
    doc=_("Teilt ein Objekt an einer Ebene in zwei Hälften mit geschlossenen Schnittflächen."),
)
def split_plane(ctx: OpContext) -> OpResult:
    params = cast(SplitPlaneParams, ctx.params)
    source = ctx.inputs[0]
    plane = SectionPlane(normal=AXIS_NORMALS[cast(Axis, params.axis)], position=params.position)
    first, second, findings = split_at_plane(as_mesh_data(source.mesh), plane)
    return OpResult(
        outputs=[
            dataclasses.replace(source, mesh=first, name=f"{source.name} A"),
            dataclasses.replace(source, mesh=second, name=f"{source.name} B", features={}),
        ],
        findings=findings,
    )


@op_params
class CountersinkParams(BaseParams):
    diameter: float = param(
        title=_("Kopfdurchmesser"),
        default=8.4,
        unit="mm",
        minimum=0.5,
        maximum=100.0,
        doc=_(
            "Durchmesser des Schraubenkopfes, nicht der Bohrung darunter. Eine "
            "angeklickte Bohrung trägt ihn deshalb bewusst nicht ein."
        ),
    )
    angle: float = param(
        title=_("Winkel"),
        default=90.0,
        unit="grad",
        minimum=30.0,
        maximum=170.0,
        doc=_("Voller Kopfwinkel — 90 Grad bei metrischen Senkschrauben."),
    )
    x: float = param(title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X)
    y: float = param(title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y)
    z: float = param(title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z)
    axis: str = param(title=_("Achse"), default="z", choices=_AXES, doc=_ALONG)


@register_op(
    name="countersink_hole",
    title=_("Senken"),
    category="holes",
    params=CountersinkParams,
    consumes=1,
    produces=1,
    applies_to=["hole"],
    doc=_("Senkt die Mündung einer Bohrung an, damit ein Schraubenkopf bündig sitzt."),
)
def countersink_hole(ctx: OpContext) -> OpResult:
    params = cast(CountersinkParams, ctx.params)
    source = ctx.inputs[0]
    result = countersink(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        angle=params.angle,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class PlugParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        maximum=200.0,
        doc=_("Durchmesser der Bohrung, die zugemacht wird — etwas mehr schadet nicht."),
    )
    x: float = param(title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X)
    y: float = param(title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y)
    z: float = param(title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z)
    axis: str = param(title=_("Achse"), default="z", choices=_AXES, doc=_ALONG)
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Null füllt durch das ganze Teil."),
    )


@register_op(
    name="plug_hole",
    title=_("Bohrung verschließen"),
    category="holes",
    params=PlugParams,
    consumes=1,
    produces=1,
    applies_to=["hole"],
    doc=_("Füllt eine Bohrung wieder auf — etwa wenn ein fremdes Teil eine zu viel hat."),
)
def plug_hole(ctx: OpContext) -> OpResult:
    params = cast(PlugParams, ctx.params)
    source = ctx.inputs[0]
    result = plug(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        depth=params.depth,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features={})],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class HollowParams(BaseParams):
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.4,
        maximum=50.0,
        doc=_("Was stehen bleibt. Zwei Extrusionsbreiten sind das Minimum (§39)."),
    )
    vents: int = param(
        title=_("Entlüftungen"),
        default=1,
        minimum=0,
        maximum=6,
        doc=_("Null heißt geschlossener Hohlraum — beim FDM-Druck drückt der die Decke hoch."),
    )
    vent_diameter: float = param(
        title=_("Entlüftungsdurchmesser"),
        default=VENT_DIAMETER,
        unit="mm",
        minimum=1.0,
        maximum=20.0,
        placement="advanced",
        doc=_("Weite der Öffnungen. Groß genug, dass nicht verbrauchtes Material herauskommt."),
    )


@register_op(
    name="hollow_object",
    title=_("Aushöhlen"),
    category="prepare",
    params=HollowParams,
    consumes=1,
    produces=1,
    doc=_(
        "Höhlt ein Objekt aus und setzt Entlüftungen. Spart Material und Zeit; "
        "die Wandstärke stimmt im Rahmen des Rasters."
    ),
)
def hollow_object(ctx: OpContext) -> OpResult:
    params = cast(HollowParams, ctx.params)
    source = ctx.inputs[0]
    result = hollow(
        as_mesh_data(source.mesh),
        params.wall,
        vents=params.vents,
        vent_diameter=params.vent_diameter,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features={})],
        findings=result.findings,
    )


@op_params
class ElephantFootParams(BaseParams):
    height: float = param(
        title=_("Höhe"),
        default=0.6,
        unit="mm",
        minimum=0.1,
        maximum=5.0,
        doc=_("Über wie viel Höhe eingezogen wird — etwa die ersten drei Schichten."),
    )
    amount: float = param(
        title=_("Betrag"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )


@register_op(
    name="compensate_first_layer",
    title=_("Elefantenfuß ausgleichen"),
    category="prepare",
    params=ElephantFootParams,
    consumes=1,
    produces=1,
    doc=_(
        "Zieht die ersten Schichten um den Betrag ein, um den sie beim Drucken "
        "breitlaufen. Der Wert kommt aus dem Materialprofil."
    ),
)
def compensate_first_layer(ctx: OpContext) -> OpResult:
    params = cast(ElephantFootParams, ctx.params)
    source = ctx.inputs[0]
    if ctx.profile is None:
        raise InternalError(detail="the elephant foot compensation needs a profile")

    mesh, findings = compensate_elephant_foot(
        as_mesh_data(source.mesh),
        # Das Auseinanderlaufen gehört zum Material, und dieser Körper ist
        # vielleicht nicht im Material des Projekts (§12) — eine TPU-Dichtung
        # läuft weiter als das PETG um sie herum.
        for_object(ctx.profile, source),
        height=params.height,
        amount=params.amount or None,
    )
    return OpResult(outputs=[dataclasses.replace(source, mesh=mesh)], findings=findings)


@op_params
class MaterialParams(BaseParams):
    material: str = param(
        title=_("Material"),
        default="",
        doc=_("Kennung eines Materialprofils, etwa „tpu-95a“. Leer heißt: das des Projekts."),
    )


@register_op(
    name="set_material",
    title=_("Material festlegen"),
    category="prepare",
    params=MaterialParams,
    consumes=1,
    produces=1,
    doc=_(
        "Gibt diesem Körper ein eigenes Material. Toleranzen, Schwund und "
        "Elefantenfuß werden dann damit gerechnet und nicht mit dem des Projekts."
    ),
)
def set_material(ctx: OpContext) -> OpResult:
    """§12: eine Szene, mehr als ein Material.

    Ein Gehäuse in PETG mit einer Dichtung in TPU ist ein Projekt und zwei
    Materialien. Ohne das würden Spiel, Schrumpf und erste Schicht der Dichtung
    aus dem Material des Gehäuses gerechnet — Zahlen, die nicht ungefähr sind,
    sondern falsch, und falsch in der Richtung, die einen Druck zu Ausschuss
    macht.

    Die Kennung wird hier geprüft statt als feste Liste angeboten: zu den
    bekannten Materialien gehören die eigenen Profile des Nutzers, und die
    erscheinen, nachdem dieses Modul importiert wurde.
    """
    params = cast(MaterialParams, ctx.params)
    source = ctx.inputs[0]
    chosen = params.material.strip()
    if chosen:
        material(chosen)  # wirft mit der Liste der bekannten, wenn es keines ist

    return OpResult(
        outputs=[dataclasses.replace(source, material=chosen or None)],
        findings=[
            Finding(
                code="prepare.material",
                severity="info",
                message=_("Dieser Körper wird in einem eigenen Material gerechnet."),
                values={"object": source.name, "material": chosen or "-"},
            )
        ]
        if chosen
        else [],
    )


@op_params
class TestPieceParams(BaseParams):
    size: float = param(
        title=_("Kantenlänge"),
        default=20.0,
        unit="mm",
        minimum=2.0,
        maximum=200.0,
        doc=_("Wie groß der Ausschnitt wird. Groß genug, dass die Passung Material hat."),
    )
    x: float = param(
        title=_("Position X"),
        default=0.0,
        unit="mm",
        doc=_("Mitte des Ausschnitts — die Stelle, um die es geht."),
    )
    y: float = param(title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y)
    z: float = param(title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z)
    on_bed: bool = param(
        title=_("Auf das Bett setzen"),
        default=True,
        doc=_("Legt das Prüfstück flach hin, damit es ohne Stützen druckt."),
    )


@register_op(
    name="test_piece",
    title=_("Prüfstück erzeugen"),
    category="prepare",
    params=TestPieceParams,
    consumes=1,
    produces=1,
    applies_to=["hole", "pin", "face"],
    doc=_(
        "Schneidet einen Würfel um eine Stelle heraus, um sie zu drucken und "
        "auszuprobieren — zwei Minuten statt zwei Stunden."
    ),
)
def test_piece(ctx: OpContext) -> OpResult:
    """§28.3, aus der Praxis: eine Passung prüft man am Ausschnitt, nicht am Teil.

    Der Ausschnitt ist eine Verschneidung mit einem Würfel — heraus kommt also
    die echte Geometrie mit den echten Toleranzen, keine nachgebaute Näherung
    davon. Ein Prüfstück, das anders druckt als das Teil, für das es steht,
    wäre schlechter als gar kein Test.
    """
    params = cast(TestPieceParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    window = trimesh.creation.box(extents=(params.size, params.size, params.size))
    window.apply_translation((params.x, params.y, params.z))
    # Ein Fenster über leerem Raum ist eine Antwort, keine gescheiterte
    # Operation: ohne ``allow_empty`` probierte die Kette drei weitere Stufen
    # und würfe dann — und der Nutzer läse etwas über den Voxel-Solver statt
    # über das Loch, auf das er gezielt hat.
    outcome = boolean(
        "intersection", [mesh, mesh.replacing(window)], quality=ctx.quality, allow_empty=True
    )

    piece = outcome.mesh
    if not piece.triangle_count or abs(piece.volume) <= EPS_GEOM:
        raise ValidationError(
            field="size",
            detail=_("An dieser Stelle ist kein Material — der Ausschnitt bleibt leer."),
            constraint="empty",
            values={"size_mm": round(params.size, 2)},
        )
    if params.on_bed:
        piece = place_on_bed(piece)

    share = abs(piece.volume) / max(abs(mesh.volume), EPS_GEOM)
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=piece,
                name=f"{source.name} {_('Prüfstück').translate()}",
                features={},
            )
        ],
        solver=outcome.solver,
        findings=[
            *outcome.findings,
            Finding(
                code="prepare.test_piece",
                severity="info",
                message=_("Ein Ausschnitt zum Ausprobieren — die Maße sind die des Teils."),
                object_id=source.id,
                values={"share_percent": round(share * 100.0, 1), "size_mm": params.size},
            ),
        ],
    )


@op_params
class SplitPinnedParams(BaseParams):
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=_AXES,
        doc=_("Senkrecht zu welcher Achse geschnitten wird. Z legt einen waagerechten Schnitt."),
    )
    position: float = param(
        title=_("Position"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wo die Schnittebene liegt, auf dieser Achse gemessen. Die Zahl bleibt "
            "änderbar: ein Doppelklick auf den Schritt verschiebt den Schnitt."
        ),
    )
    pins: int = param(
        title=_("Passstifte"),
        default=PIN_COUNT,
        minimum=0,
        maximum=6,
        doc=_("Null heißt: nur schneiden. Zwei halten die Hälften gegen Verdrehen."),
    )
    diameter: float = param(
        title=_("Stiftdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=PIN_MAX,
        placement="advanced",
        doc=_("Null heißt: aus der Schnittfläche ableiten."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )


@register_op(
    name="split_pinned",
    title=_("Teilen und verstiften"),
    category="prepare",
    params=SplitPinnedParams,
    consumes=1,
    produces=2,
    doc=_(
        "Teilt ein Objekt an einer Ebene und setzt Passstifte in die Schnittfläche. "
        "Das Spiel kommt aus dem Materialprofil."
    ),
)
def split_pinned(ctx: OpContext) -> OpResult:
    """§25: der Schnitt und die Stifte in einem Schritt, denn sie gehören
    zusammen.

    Eine Naht ohne Stifte ist eine Naht, die jemand von Hand ausrichten muss,
    während der Kleber greift; ein Stift ohne Naht ist nichts. Beides in einer
    Operation heißt außerdem: ein Undo nimmt das Ganze zurück.
    """
    params = cast(SplitPinnedParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)
    candidate = Candidate(
        axis=cast(Axis, params.axis),
        position=params.position,
        area=0.0,
        contours=1,
        score=0.0,
    )

    first, second, findings = split_at_plane(mesh, candidate.plane)
    if not (first.triangle_count and second.triangle_count):
        raise ValidationError(
            field="position",
            detail=_("Diese Ebene teilt das Objekt nicht."),
            value=params.position,
            constraint="no_split",
        )

    plan = plan_pins(mesh, candidate, count=params.pins) if params.pins else None
    if plan is not None and params.diameter:
        plan = dataclasses.replace(plan, diameter=params.diameter)

    pair = (
        # Beide Hälften kommen aus diesem einen Körper, das Spiel ist also das
        # seines Materials.
        add_pins(first, second, plan, for_object(ctx.profile, source), play=params.play or None)
        if plan is not None and ctx.profile is not None
        else PinnedPair(first=first, second=second)
    )

    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=pair.first,
                name=f"{source.name} A",
                features={**source.features, **pair.pin_features},
            ),
            dataclasses.replace(
                source,
                mesh=pair.second,
                name=f"{source.name} B",
                features=dict(pair.bore_features),
            ),
        ],
        findings=[*findings, *pair.findings],
    )


@op_params
class OrientParams(BaseParams):
    thorough: bool = param(
        title=_("Gründlich suchen"),
        default=True,
        doc=_(
            "Rechnet hunderte Lagen mit der Schichtanalyse durch. "
            "Aus heißt: schnelle Heuristik über die Flächen."
        ),
    )
    candidates: int = param(
        title=_("Kandidaten"),
        default=DEFAULT_CANDIDATES,
        minimum=8,
        maximum=2000,
        placement="advanced",
        doc=_(
            "Wie viele Lagen durchgerechnet werden. Mehr findet feinere "
            "Verbesserungen und dauert entsprechend länger."
        ),
    )


@register_op(
    name="orient_for_print",
    title=_("Druckoptimal ausrichten"),
    category="transform",
    params=OrientParams,
    consumes=1,
    produces=1,
    deterministic=False,
    doc=_("Sucht die Lage mit dem geringsten Stützbedarf."),
)
def orient_for_print_op(ctx: OpContext) -> OpResult:
    """Gründlich heißt, die Schichtanalyse urteilt; sonst tut es die
    P2-Heuristik.
    """
    params = cast(OrientParams, ctx.params)
    mesh = as_mesh_data(ctx.inputs[0].mesh)

    if params.thorough:
        found = search(
            mesh,
            count=params.candidates,
            seed=ctx.seed,
            progress=ctx.progress,
            cancelled=ctx.cancelled,
        )
        return OpResult(
            outputs=[dataclasses.replace(ctx.inputs[0], mesh=found.mesh)],
            findings=found.findings,
        )

    result = orient_for_print(mesh)
    return OpResult(
        outputs=[dataclasses.replace(ctx.inputs[0], mesh=result.mesh)],
        findings=result.findings,
    )


@op_params
class ArrangeParams(BaseParams):
    spacing: float = param(
        title=_("Abstand"),
        default=5.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_(
            "Luft zwischen den Teilen. Genug, dass ein Elefantenfuß zwei Teile "
            "nicht am Rand zusammenwachsen lässt."
        ),
    )
    plates: int = param(
        title=_("Druckplatten"),
        default=1,
        minimum=1,
        maximum=MAX_PLATES,
        doc=_("Passt nicht alles auf eine Platte, wandert der Rest auf die nächste."),
    )


@register_op(
    name="arrange_bed",
    title=_("Auf dem Bett anordnen"),
    category="scene",
    params=ArrangeParams,
    consumes=0,
    produces=VARIABLE,
    whole_scene=True,
    doc=_("Legt alle Objekte nebeneinander auf das Druckbett."),
)
def arrange_bed(ctx: OpContext) -> OpResult:
    params = cast(ArrangeParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    result = arrange_on_bed(meshes, ctx.profile, params.spacing, params.plates)
    findings = list(result.findings)

    # Kollisionen werden je Platte geprüft: zwei Teile an derselben Stelle auf
    # verschiedenen Platten treffen sich nie.
    for plate in range(result.plate_count):
        on_plate = [
            mesh for mesh, entry in zip(result.meshes, result.plates, strict=True) if entry == plate
        ]
        findings.extend(check_collisions(on_plate))

    return OpResult(
        outputs=[
            dataclasses.replace(entry, mesh=mesh, plate=plate)
            for entry, mesh, plate in zip(ctx.inputs, result.meshes, result.plates, strict=True)
        ],
        findings=findings,
    )


@op_params
class CollisionParams(BaseParams):
    clearance: float = param(
        title=_("Mindestabstand"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        doc=_(
            "Ab wann zwei Teile als zu nah gelten. Null meldet nur echte "
            "Überschneidungen; ein Wert darüber meldet auch knappe Stellen."
        ),
    )


@register_op(
    name="check_collisions",
    title=_("Kollisionen prüfen"),
    category="scene",
    params=CollisionParams,
    consumes=0,
    produces=VARIABLE,
    whole_scene=True,
    doc=_("Meldet Überschneidungen und was über den Bauraum hinaussteht."),
)
def check_collisions_op(ctx: OpContext) -> OpResult:
    params = cast(CollisionParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    findings = check_collisions(meshes, params.clearance)
    findings.extend(check_build_volume(meshes, ctx.profile))
    # Ändert nichts: die Objekte gehen unberührt hindurch, die Befunde sind das
    # Ergebnis.
    return OpResult(outputs=list(ctx.inputs), findings=named_for(findings, ctx.inputs))
