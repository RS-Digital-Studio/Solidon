"""Parts for screws (Bauplan §24.1, group "Verbindungen").

Four of the thirteen: the screw hole with its countersink, the heat-set insert
bore, the nut trap from the side or from below, and a printable thread.

Every dimension comes from the standard table (§24.2) — "hole for an M4
heat-set insert" is a lookup, not a guess. What the part adds on top is the
material tolerance from the profile, and it says so in its documentation rather
than hiding it in a number.
"""

from __future__ import annotations

from typing import cast

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, result, thread, union
from app.core.knowledge.parts.registry import PartChange, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.i18n import _

_SCREWS = standards.screw_sizes()
_NUTS = standards.nut_sizes()
_INSERTS = standards.insert_sizes()

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)


# --- screw hole -------------------------------------------------------------------


@op_params
class ScrewHoleParams(BaseParams):
    size: str = param(title=_("Größe"), default="M3", choices=_SCREWS)
    depth: float = param(title=_("Tiefe"), default=10.0, unit="mm", minimum=1.0, maximum=200.0)
    countersink: bool = param(title=_("Senkung"), default=True)
    head_room: float = param(
        title=_("Kopffreiheit"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        placement="advanced",
        doc=_("Zylindrische Aussparung über der Senkung, für einen versenkten Kopf."),
    )


@register_part(
    name="screw_hole",
    title=_("Schraubenloch mit Senkung"),
    group="fasteners",
    params=ScrewHoleParams,
    subtractive=True,
    features=["bore", "countersink"],
    doc=_(
        "Durchgangsloch für eine metrische Schraube, auf Wunsch mit 90-Grad-Senkung "
        "und Kopffreiheit. Maße aus der Normteiltabelle."
    ),
    changes=[FIRST_RELEASE],
)
def screw_hole(raw: BaseParams) -> PartResult:
    params = cast(ScrewHoleParams, raw)
    screw = standards.screw(params.size)

    shaft = shapes.cylinder(screw.clearance, params.depth + shapes.OVERLAP)
    shaft = shapes.moved(shaft, (0.0, 0.0, -params.depth))
    parts = [shaft]
    features = [
        bore(
            "bore_1",
            screw.clearance,
            (0.0, 0.0, -params.depth / 2.0),
            depth=params.depth,
            through=True,
        )
    ]

    if params.countersink:
        # A 90 degree countersink is as deep as the head is wide, halved.
        depth = (screw.countersink - screw.clearance) / 2.0
        sink = shapes.cone(screw.clearance, screw.countersink, depth)
        parts.append(shapes.moved(sink, (0.0, 0.0, -depth)))
        features.append(
            bore("countersink_1", screw.countersink, (0.0, 0.0, -depth / 2.0), depth=depth)
        )

    if params.head_room > 0.0:
        room = shapes.cylinder(screw.countersink, params.head_room + shapes.OVERLAP)
        parts.append(room)

    return result(union(*parts), *features)


# --- heat-set insert ---------------------------------------------------------------


@op_params
class HeatsetParams(BaseParams):
    size: str = param(title=_("Größe"), default="M3", choices=_INSERTS)
    lead_in: bool = param(
        title=_("Einführfase"),
        default=True,
        doc=_("Fase am Rand, damit die Buchse beim Einpressen gerade läuft."),
    )
    extra_depth: float = param(
        title=_("Zusatztiefe"),
        default=0.5,
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        placement="advanced",
        doc=_("Platz unter der Buchse für verdrängtes Material."),
    )


@register_part(
    name="heatset_m4",
    title=_("Heat-Set-Einpressbuchse"),
    group="inserts",
    params=HeatsetParams,
    subtractive=True,
    features=["bore", "chamfer"],
    doc=_(
        "Bohrung für eine Heat-Set-Einpressbuchse mit Einführfase. Der Durchmesser "
        "ist bewusst knapp: das Material soll beim Einpressen verdrängt werden."
    ),
    changes=[FIRST_RELEASE],
)
def heatset_insert(raw: BaseParams) -> PartResult:
    params = cast(HeatsetParams, raw)
    entry = standards.insert(params.size)
    depth = entry.length + params.extra_depth

    shaft = shapes.cylinder(entry.hole, depth + shapes.OVERLAP)
    shaft = shapes.moved(shaft, (0.0, 0.0, -depth))
    parts = [shaft]
    features = [
        bore("bore_1", entry.hole, (0.0, 0.0, -depth / 2.0), depth=depth),
    ]

    if params.lead_in:
        chamfer = (entry.outer - entry.hole) / 2.0 + 0.3
        lead = shapes.cone(entry.hole, entry.hole + 2.0 * chamfer, chamfer)
        parts.append(shapes.moved(lead, (0.0, 0.0, -chamfer)))
        features.append(
            bore("chamfer_1", entry.hole + 2.0 * chamfer, (0.0, 0.0, -chamfer / 2.0), depth=chamfer)
        )

    return result(union(*parts), *features)


# --- nut trap -----------------------------------------------------------------------


@op_params
class NutTrapParams(BaseParams):
    size: str = param(title=_("Größe"), default="M3", choices=_NUTS)
    direction: str = param(
        title=_("Richtung"),
        default="side",
        choices=("side", "bottom"),
        doc=_("Von der Seite eingeschoben oder von unten eingelegt."),
    )
    slide: float = param(
        title=_("Einschubweg"),
        default=12.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_("Wie weit der Schlitz nach außen reicht. Null heißt: nur die Tasche."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.2,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_("Zuschlag auf die Schlüsselweite."),
    )
    screw_hole: bool = param(title=_("Schraubenloch mitschneiden"), default=True)


@register_part(
    name="nut_trap",
    title=_("Mutternfalle"),
    group="fasteners",
    params=NutTrapParams,
    subtractive=True,
    features=["pocket", "bore"],
    doc=_(
        "Tasche für eine Sechskantmutter, seitlich eingeschoben oder von unten "
        "eingelegt, auf Wunsch mit durchgehendem Schraubenloch."
    ),
    changes=[FIRST_RELEASE],
)
def nut_trap(raw: BaseParams) -> PartResult:
    params = cast(NutTrapParams, raw)
    entry = standards.nut(params.size)
    width = entry.width + params.play
    height = entry.height + params.play / 2.0

    pocket = shapes.hexagon(width, height)
    parts = [pocket]
    features = [
        bore("pocket_1", width, (0.0, 0.0, height / 2.0), depth=height),
    ]

    if params.slide > 0.0:
        # The slot the nut is pushed in through, pointing along +Y.
        channel = shapes.box(width, params.slide, height)
        parts.append(shapes.moved(channel, (0.0, params.slide / 2.0, 0.0)))

    if params.screw_hole:
        screw = standards.screw(params.size)
        length = height + 20.0
        shaft = shapes.cylinder(screw.clearance, length)
        parts.append(shapes.moved(shaft, (0.0, 0.0, -10.0)))
        features.append(
            bore("bore_1", screw.clearance, (0.0, 0.0, height / 2.0), depth=length, through=True)
        )

    body = union(*parts)
    if params.direction == "bottom":
        # Turned so the opening faces down — laid in from below rather than
        # pushed in from the side.
        body = shapes.turned(body, 90.0, (1.0, 0.0, 0.0))
    return result(body, *features)


# --- thread --------------------------------------------------------------------------


@op_params
class ThreadParams(BaseParams):
    size: str = param(title=_("Größe"), default="M6", choices=_SCREWS)
    length: float = param(title=_("Länge"), default=12.0, unit="mm", minimum=2.0, maximum=200.0)
    internal: bool = param(
        title=_("Innengewinde"),
        default=False,
        doc=_("Innengewinde wird abgezogen, Außengewinde wird angesetzt."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.15,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_("Der Druck fällt enger aus, als die Datei sagt."),
    )


@register_part(
    name="printed_thread",
    title=_("Gewinde"),
    group="fasteners",
    params=ThreadParams,
    subtractive=False,
    features=["thread"],
    doc=_(
        "Druckbares Gewinde als Wendel mit abgeflachtem Kamm — kein ISO-Profil, "
        "weil ein Drucker es ohnehin nicht auflöst."
    ),
    changes=[FIRST_RELEASE],
)
def printed_thread(raw: BaseParams) -> PartResult:
    params = cast(ThreadParams, raw)
    screw = standards.screw(params.size)
    diameter = screw.nominal + (params.play if params.internal else -params.play)

    ridge = shapes.thread_body(diameter, screw.pitch, params.length, internal=params.internal)
    core = shapes.cylinder(
        diameter if params.internal else diameter - 2.0 * screw.pitch * 0.55,
        params.length,
    )
    body = union(core, ridge)
    # The helix ends a little above the nominal length; cut it back so the part
    # is exactly as long as it says it is.
    limit = shapes.cylinder(diameter * 2.0 + 4.0, params.length)
    body = _intersect(body, limit)

    return result(
        body,
        thread(
            "thread_1",
            screw.nominal,
            screw.pitch,
            (0.0, 0.0, params.length / 2.0),
            internal=params.internal,
        ),
    )


def _intersect(first: MeshData, second: MeshData) -> MeshData:
    return boolean("intersection", [first, second], quality="fine").mesh
