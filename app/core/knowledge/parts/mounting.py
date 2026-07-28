"""Parts that hold something to something else (Bauplan §24.1).

Three of the thirteen: the magnet pocket, the wall mount and the keyhole
hanger. Two of them are shapes to subtract, one is a body to add — which is why
the declaration says so and ``insert_part`` does not have to guess.
"""

from __future__ import annotations

from typing import cast

from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, result, subtract, union
from app.core.knowledge.parts.registry import PartChange, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.i18n import _

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)

_MAGNETS = standards.magnet_sizes()
_SCREWS = standards.screw_sizes()


@op_params
class MagnetPocketParams(BaseParams):
    size: str = param(title=_("Magnet"), default="8x3", choices=_MAGNETS)
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )
    cover: float = param(
        title=_("Deckschicht"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        doc=_("Material über dem Magneten. Null lässt die Tasche offen."),
    )
    press_lip: bool = param(
        title=_("Haltelippe"),
        default=True,
        placement="advanced",
        doc=_("Ein Zehntel Verengung am Rand, damit der Magnet nicht herausfällt."),
    )


@register_part(
    name="magnet_pocket",
    title=_("Magnettasche"),
    group="mounting",
    params=MagnetPocketParams,
    subtractive=True,
    features=["pocket"],
    doc=_(
        "Tasche für einen Rundmagneten, auf Wunsch mit Deckschicht zum Überdrucken "
        "und einer Haltelippe am Rand."
    ),
    changes=[FIRST_RELEASE],
)
def magnet_pocket(raw: BaseParams) -> PartResult:
    params = cast(MagnetPocketParams, raw)
    entry = standards.magnet(params.size)
    diameter = entry.diameter + params.play

    pocket = shapes.cylinder(diameter, entry.height)
    parts = [shapes.moved(pocket, (0.0, 0.0, params.cover))]

    if params.cover <= 0.0:
        # Open pocket: reach a hair past the surface so the cut is clean (§39).
        parts.append(
            shapes.moved(shapes.cylinder(diameter, shapes.OVERLAP), (0.0, 0.0, entry.height))
        )
    if params.press_lip and params.cover <= 0.0:
        lip = shapes.cone(diameter, diameter - 0.2, 0.4)
        parts.append(shapes.moved(lip, (0.0, 0.0, entry.height - 0.4)))

    body = union(*parts)
    return result(
        body,
        bore(
            "pocket_1",
            diameter,
            (0.0, 0.0, params.cover + entry.height / 2.0),
            depth=entry.height,
        ),
    )


@op_params
class WallMountParams(BaseParams):
    width: float = param(title=_("Breite"), default=30.0, unit="mm", minimum=8.0, maximum=300.0)
    height: float = param(title=_("Höhe"), default=25.0, unit="mm", minimum=8.0, maximum=300.0)
    thickness: float = param(
        title=_("Wandstärke"), default=3.0, unit="mm", minimum=1.0, maximum=20.0
    )
    size: str = param(title=_("Schraube"), default="M4", choices=_SCREWS)
    holes: int = param(
        title=_("Löcher"), default=2, minimum=1, maximum=6, doc=_("Über die Breite verteilt.")
    )
    lip: float = param(
        title=_("Auflage"),
        default=12.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_("Nach vorn stehender Steg, auf dem das Gerät sitzt."),
    )


@register_part(
    name="wall_mount",
    title=_("Wandhalter"),
    group="mounting",
    params=WallMountParams,
    features=["plate", "bore"],
    doc=_(
        "Rückplatte mit Schraubenlöchern und nach vorn stehender Auflage. "
        "Die Löcher sind Durchgangslöcher aus der Normteiltabelle."
    ),
    changes=[FIRST_RELEASE],
)
def wall_mount(raw: BaseParams) -> PartResult:
    params = cast(WallMountParams, raw)
    screw = standards.screw(params.size)

    plate = shapes.box(params.width, params.thickness, params.height)
    body = plate
    if params.lip > 0.0:
        shelf = shapes.box(params.width, params.lip, params.thickness)
        body = union(
            body, shapes.moved(shelf, (0.0, params.thickness / 2.0 + params.lip / 2.0, 0.0))
        )

    features = [face("plate_1", params.width * params.height, (0.0, 0.0, params.height / 2.0))]
    spacing = params.width / (params.holes + 1)
    for index in range(1, params.holes + 1):
        x = -params.width / 2.0 + spacing * index
        z = params.height * 0.75
        hole = shapes.cylinder(screw.clearance, params.thickness + 2.0 * shapes.OVERLAP)
        hole = shapes.turned(hole, -90.0, (1.0, 0.0, 0.0))
        hole = shapes.moved(hole, (x, params.thickness / 2.0 + shapes.OVERLAP, z))
        body = subtract(body, hole)
        features.append(
            bore(
                f"bore_{index}",
                screw.clearance,
                (x, 0.0, z),
                depth=params.thickness,
                axis=(0.0, 1.0, 0.0),
                through=True,
            )
        )

    return result(body, *features)


@op_params
class KeyholeParams(BaseParams):
    size: str = param(title=_("Schraube"), default="M4", choices=_SCREWS)
    drop: float = param(
        title=_("Einhängeweg"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=60.0,
        doc=_("Wie weit das Teil nach dem Einhängen absinkt."),
    )
    depth: float = param(title=_("Tiefe"), default=4.0, unit="mm", minimum=1.0, maximum=40.0)
    head_room: float = param(
        title=_("Kopftiefe"),
        default=2.5,
        unit="mm",
        minimum=0.5,
        maximum=20.0,
        placement="advanced",
        doc=_("Wie tief der Schraubenkopf einsinkt."),
    )


@register_part(
    name="keyhole",
    title=_("Schlüsselloch-Aufhängung"),
    group="mounting",
    params=KeyholeParams,
    subtractive=True,
    features=["pocket", "bore"],
    doc=_(
        "Schlüssellochförmige Aussparung: der Kopf geht durch das runde Ende, "
        "der Schaft hält im Schlitz."
    ),
    changes=[FIRST_RELEASE],
)
def keyhole(raw: BaseParams) -> PartResult:
    params = cast(KeyholeParams, raw)
    screw = standards.screw(params.size)

    # The pocket the head sinks into: round at the bottom, a slot upwards.
    pocket = shapes.slot(screw.head + 0.6, screw.head + 0.6 + params.drop, params.head_room)
    pocket = shapes.turned(pocket, 90.0, (1.0, 0.0, 0.0))
    pocket = shapes.moved(pocket, (0.0, params.head_room, params.drop / 2.0))

    # The slot the shaft slides in, all the way through.
    shaft = shapes.slot(
        screw.clearance, screw.clearance + params.drop, params.depth + 2.0 * shapes.OVERLAP
    )
    shaft = shapes.turned(shaft, 90.0, (1.0, 0.0, 0.0))
    shaft = shapes.moved(shaft, (0.0, params.depth + shapes.OVERLAP, params.drop / 2.0))

    body = union(pocket, shaft)
    return result(
        body,
        bore(
            "pocket_1",
            screw.head + 0.6,
            (0.0, params.head_room / 2.0, 0.0),
            depth=params.head_room,
            axis=(0.0, 1.0, 0.0),
        ),
        bore(
            "bore_1",
            screw.clearance,
            (0.0, params.depth / 2.0, params.drop),
            depth=params.depth,
            axis=(0.0, 1.0, 0.0),
            through=True,
        ),
    )
