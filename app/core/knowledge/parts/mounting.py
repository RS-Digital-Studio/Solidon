"""Bausteine, die etwas an etwas anderem halten (Bauplan §24.1).

Drei der dreizehn: die Magnettasche, die Wandhalterung und die
Schlüsselloch-Aufhängung. Zwei davon sind Formen zum Abziehen, eine ist ein
Körper zum Hinzufügen — darum sagt die Deklaration es, und ``insert_part`` muss
nicht raten.
"""

from __future__ import annotations

from typing import cast

from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, result, subtract, union
from app.core.knowledge.parts.registry import (
    FACE_GIVES_DIRECTION,
    MOUTH_AT_ORIGIN,
    PartChange,
    register_part,
)
from app.core.registry import AUTO_FROM_PROFILE_DOC, op_params, param
from app.core.types import BaseParams, PartResult
from app.i18n import _

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)

_MAGNETS = standards.magnet_sizes()
_SCREWS = standards.screw_sizes()


@op_params
class MagnetPocketParams(BaseParams):
    size: str = param(
        title=_("Magnet"),
        default="8x3",
        choices=_MAGNETS,
        doc=_("Durchmesser mal Höhe des Rundmagneten, wie er im Handel heißt."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=AUTO_FROM_PROFILE_DOC,
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
    changes=[FIRST_RELEASE, MOUTH_AT_ORIGIN, FACE_GIVES_DIRECTION],
)
def magnet_pocket(raw: BaseParams) -> PartResult:
    params = cast(MagnetPocketParams, raw)
    entry = standards.magnet(params.size)
    diameter = entry.diameter + params.play

    # Der Ursprung ist die Mündung, die Tasche liegt darunter (§24.1). Eine
    # Decke schiebt sie tiefer hinein, statt sie anzuheben: über der Mündung
    # ist die Luft, und dort trägt nichts ab.
    mouth = -params.cover
    pocket = shapes.cylinder(diameter, entry.height)
    parts = [shapes.moved(pocket, (0.0, 0.0, mouth - entry.height))]

    if params.cover <= 0.0:
        # Offene Tasche: ein Haar über die Fläche hinausreichen, damit der Schnitt
        # sauber wird (§39).
        parts.append(shapes.moved(shapes.cylinder(diameter, shapes.OVERLAP), (0.0, 0.0, mouth)))
    if params.press_lip and params.cover <= 0.0:
        lip = shapes.cone(diameter, diameter - 0.2, 0.4)
        parts.append(shapes.moved(lip, (0.0, 0.0, mouth - 0.4)))

    body = union(*parts)
    return result(
        body,
        bore(
            "pocket_1",
            diameter,
            (0.0, 0.0, mouth - entry.height / 2.0),
            depth=entry.height,
        ),
    )


@op_params
class WallMountParams(BaseParams):
    width: float = param(
        title=_("Breite"),
        default=30.0,
        unit="mm",
        minimum=8.0,
        maximum=300.0,
        doc=_("Breite der Rückplatte, die an die Wand kommt."),
    )
    height: float = param(
        title=_("Höhe"),
        default=25.0,
        unit="mm",
        minimum=8.0,
        maximum=300.0,
        doc=_("Höhe der Rückplatte. Die Auflage steht davon nach vorn ab."),
    )
    thickness: float = param(
        title=_("Wandstärke"),
        default=3.0,
        unit="mm",
        minimum=1.0,
        maximum=20.0,
        doc=_("Dicke von Rückplatte und Auflage. Unter zwei Millimetern biegt sich der Halter."),
    )
    size: str = param(
        title=_("Schraube"),
        default="M4",
        choices=_SCREWS,
        doc=_("Wofür die Löcher sind. Es sind Durchgangslöcher aus der Normteiltabelle."),
    )
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
    changes=[FIRST_RELEASE, FACE_GIVES_DIRECTION],
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
    size: str = param(
        title=_("Schraube"),
        default="M4",
        choices=_SCREWS,
        doc=_(
            "Die Schraube in der Wand. Ihr Kopf geht durch das runde Ende, ihr "
            "Schaft hält im Schlitz."
        ),
    )
    drop: float = param(
        title=_("Einhängeweg"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=60.0,
        doc=_("Wie weit das Teil nach dem Einhängen absinkt."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=4.0,
        unit="mm",
        minimum=1.0,
        maximum=40.0,
        doc=_("Wie tief die Aussparung ins Material geht."),
    )
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
    changes=[FIRST_RELEASE, MOUTH_AT_ORIGIN, FACE_GIVES_DIRECTION],
)
def keyhole(raw: BaseParams) -> PartResult:
    params = cast(KeyholeParams, raw)
    screw = standards.screw(params.size)

    # Der Ursprung ist die Mündung, die Tiefe geht nach unten ins Material
    # (§24.1) — wie bei jedem anderen abziehenden Baustein. Vorher lag beides
    # in Y: an eine Wand gesetzt zeigte der Schlitz nach unten statt nach oben,
    # und auf eine waagerechte Fläche geklickt traf er gar nichts.
    #
    # Der Schlitz läuft in -Y, damit er nach dem Umlegen auf eine senkrechte
    # Wand (``axis="y"``) aufwärts zeigt: das Teil fällt, die Schraube steht
    # relativ dazu höher.
    drop = -params.drop / 2.0

    # Die Tasche, in die der Kopf versinkt: am Eingang rund, dann ein Schlitz.
    pocket = shapes.slot(screw.head + 0.6, screw.head + 0.6 + params.drop, params.head_room)
    pocket = shapes.moved(pocket, (0.0, drop, -params.head_room))

    # Der Schlitz, in den der Schaft gleitet, ganz hindurch.
    shaft = shapes.slot(
        screw.clearance, screw.clearance + params.drop, params.depth + 2.0 * shapes.OVERLAP
    )
    shaft = shapes.moved(shaft, (0.0, drop, -params.depth - shapes.OVERLAP))

    body = union(pocket, shaft)
    return result(
        body,
        bore(
            "pocket_1",
            screw.head + 0.6,
            (0.0, 0.0, -params.head_room / 2.0),
            depth=params.head_room,
        ),
        bore(
            "bore_1",
            screw.clearance,
            (0.0, -params.drop, -params.depth / 2.0),
            depth=params.depth,
            through=True,
        ),
    )


PEGBOARD_HOOK_ADDED = PartChange(
    version="1",
    date="2026-08-25",
    reason="Lochwand-Einhänger — die Kundenanfrage, mit der dieses Konzept anfing.",
)

_BOARDS = standards.board_sizes()


@op_params
class PegboardHookParams(BaseParams):
    system: str = param(
        title=_("Lochwand"),
        default="skadis",
        choices=_BOARDS,
        doc=_("An welche Platte das Teil kommt. Die Maße stehen in der Tabelle."),
    )
    count: int = param(
        title=_("Einhänger"),
        default=2,
        minimum=1,
        maximum=6,
        doc=_(
            "Wie viele Haken. Zwei nebeneinander halten ein Teil gegen Verdrehen; "
            "einer genügt für Leichtes."
        ),
    )
    upright: bool = param(
        title=_("Übereinander"),
        default=False,
        doc=_(
            "Setzt die Haken senkrecht statt nebeneinander — für schmale Teile, "
            "die sonst über das Raster hinausragen."
        ),
    )
    plate: float = param(
        title=_("Rückplatte"),
        default=2.0,
        unit="mm",
        minimum=1.0,
        maximum=10.0,
        doc=_("Dicke der Platte, die die Haken trägt und am Teil sitzt."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.5,
        placement="advanced",
        doc=AUTO_FROM_PROFILE_DOC,
    )
    lip: float = param(
        title=_("Nasentiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=6.0,
        placement="advanced",
        doc=_(
            "Wie weit die Nase hinter die Platte greift. Null heißt: zwei Drittel der Plattendicke."
        ),
    )


@register_part(
    name="pegboard_hook",
    title=_("Lochwand-Einhänger"),
    group="mounting",
    params=PegboardHookParams,
    features=["plate"],
    doc=_(
        "Haken für eine Lochwand, auf einer Rückplatte. Von oben in die Schlitze "
        "gesteckt und heruntergezogen — die Nase greift dann hinter die Platte."
    ),
    caveat=_(
        "Die Lochmaße veröffentlicht IKEA nicht; sie sind aus zwei unabhängigen "
        "Sammlungen übernommen. Vor einer größeren Auflage lohnt ein Prüfdruck."
    ),
    changes=[PEGBOARD_HOOK_ADDED],
)
def pegboard_hook(raw: BaseParams) -> PartResult:
    """Einhänger im Raster, auf einer gemeinsamen Rückplatte.

    **Die Platte ist nicht Zierde, sondern Bedingung.** Zwei Haken im
    Vierzigerraster sind zwei Körper; ein Baustein muss einer sein (§24.3), und
    der Kunde will ohnehin keine zwei losen Haken, sondern ein Teil, das hängt.

    **Und der Haken greift in einen Schlitz, nicht in ein Loch.** Bei SKÅDIS
    ist die Öffnung fünf Millimeter breit und fünfzehn hoch; das ist der Weg,
    den der Haken nach unten hat, und daraus folgt seine Form: Zapfen und Nase
    zusammen müssen durch die Höhe passen, sonst kommt er gar nicht erst
    hinein.
    """
    params = cast(PegboardHookParams, raw)
    board = standards.board(params.system)

    width = board.slot_width - params.play
    lip = params.lip or board.thickness * (2.0 / 3.0)
    # Zapfen und Nase zusammen müssen durch den Schlitz passen — sonst hängt
    # das Teil nicht, es liegt daneben. Die Nase bekommt ein Drittel.
    reach = board.slot_height - params.play
    nose = reach / 3.0
    shank = reach - nose

    span = board.pitch * (params.count - 1)
    across = 0.0 if params.upright else span
    along = span if params.upright else 0.0

    # Die Platte trägt alle Haken und liegt am Teil an. Sie reicht rings um
    # den Schlitz herum, damit sie den Haken hält und nicht nur berührt.
    margin = board.slot_width
    plate = shapes.box(across + width + 2.0 * margin, along + reach + 2.0 * margin, params.plate)

    parts = [plate]
    for index in range(params.count):
        offset = index * board.pitch - span / 2.0
        x = 0.0 if params.upright else offset
        y = offset if params.upright else 0.0
        # Der Zapfen geht durch die Platte, die Nase hinter sie. Beide fangen
        # um OVERLAP früher an, damit keine Fläche auf einer anderen liegt (§39).
        shaft = shapes.box(width, shank, params.plate + board.thickness + params.play)
        parts.append(shapes.moved(shaft, (x, y + nose / 2.0, 0.0)))
        catch = shapes.box(width, nose + shank, lip)
        parts.append(
            shapes.moved(
                catch,
                (x, y, params.plate + board.thickness + params.play - shapes.OVERLAP),
            )
        )

    return result(
        union(*parts),
        # Die Rückseite der Platte: was am Teil anliegt. Nach unten gerichtet,
        # denn dort ist das Material, das sie trägt.
        face(
            "plate_1",
            (across + width + 2.0 * margin) * (along + reach + 2.0 * margin),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, -1.0),
        ),
    )
