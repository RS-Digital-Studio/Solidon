"""Bausteine, die etwas versteifen oder hindurchführen (Bauplan §24.1).

Die letzten zwei der dreizehn: die Versteifungsrippe und die
Kabeldurchführung mit Zugentlastung. Beides ist die Sorte Sache, die hundertmal
von Hand gezeichnet und in der Hälfte der Fälle falsch wird — eine Rippe, die
dicker ist als die Wand, die sie versteift, zeichnet sich durch; eine
Durchführung ohne Zugentlastung reißt den Draht aus der Lötstelle.
"""

from __future__ import annotations

from typing import cast

from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, result, union
from app.core.knowledge.parts.registry import PartChange, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.i18n import _

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)

_TUBES = standards.tube_sizes()

#: Eine Rippe dicker als etwa zwei Drittel der Wand zeichnet sich auf der
#: anderen Seite als Einfallstelle ab. Keine Druckregel, sondern eine aus dem
#: Spritzguss — sie gilt hier genauso, weil die Abkühlung ebenso ungleichmäßig
#: ist.
RIB_SHARE = 0.66


@op_params
class RibParams(BaseParams):
    length: float = param(
        title=_("Länge"),
        default=20.0,
        unit="mm",
        minimum=2.0,
        maximum=300.0,
        doc=_("Wie weit die Rippe an der Wand entlangläuft."),
    )
    height: float = param(
        title=_("Höhe"),
        default=10.0,
        unit="mm",
        minimum=1.0,
        maximum=200.0,
        doc=_("Wie weit sie von der Wand absteht. Das ist es, was die Steifigkeit bringt."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.4,
        maximum=20.0,
        doc=_("Die Wand, an der die Rippe sitzt — sie bestimmt die Rippenstärke."),
    )
    thickness: float = param(
        title=_("Rippenstärke"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=20.0,
        placement="advanced",
        doc=_("Null heißt: zwei Drittel der Wandstärke, sonst zeichnet sie sich ab."),
    )
    fillet: float = param(
        title=_("Anlauf"),
        default=2.0,
        unit="mm",
        minimum=0.0,
        maximum=20.0,
        doc=_("Schräger Auslauf am Fuß statt einer scharfen Kante."),
    )


@register_part(
    name="rib",
    title=_("Versteifungsrippe"),
    group="structure",
    params=RibParams,
    features=["rib"],
    doc=_(
        "Rippe mit schrägem Auslauf. Sie bleibt dünner als die Wand, an der sie "
        "sitzt — sonst zeichnet sie sich auf der anderen Seite ab."
    ),
    changes=[FIRST_RELEASE],
)
def rib(raw: BaseParams) -> PartResult:
    params = cast(RibParams, raw)
    thickness = params.thickness or params.wall * RIB_SHARE

    body = shapes.box(thickness, params.length, params.height)
    if params.fillet > 0.0:
        ramp = shapes.wedge(thickness, params.fillet, params.fillet, 0.0)
        body = union(
            body,
            shapes.moved(ramp, (0.0, params.length / 2.0, 0.0)),
            shapes.moved(shapes.turned(ramp, 180.0), (0.0, -params.length / 2.0, 0.0)),
        )

    return result(
        body,
        face(
            "rib_1", params.length * params.height, (0.0, 0.0, params.height / 2.0), (1.0, 0.0, 0.0)
        ),
    )


@op_params
class CableGlandParams(BaseParams):
    size: str = param(
        title=_("Kabel"),
        default="cable-5",
        choices=_TUBES,
        doc=_("Außendurchmesser des Kabels — die Zahl, die auf dem Mantel steht."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=3.0,
        unit="mm",
        minimum=1.0,
        maximum=30.0,
        doc=_("Dicke der Wand, durch die die Durchführung geht."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )
    strain_relief: bool = param(
        title=_("Zugentlastung"),
        default=True,
        doc=_("Zwei Stege, die das Kabel klemmen, damit nicht am Lötpunkt gezogen wird."),
    )
    relief_gap: float = param(
        title=_("Klemmspalt"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=20.0,
        placement="advanced",
        doc=_("Null heißt: vier Fünftel des Kabeldurchmessers."),
    )


@register_part(
    name="cable_gland",
    title=_("Kabeldurchführung mit Zugentlastung"),
    group="routing",
    params=CableGlandParams,
    subtractive=True,
    features=["bore", "relief"],
    doc=_(
        "Durchführung für ein Rundkabel, mit einer Klemmstelle dahinter. Ohne die "
        "zieht jeder Ruck am Kabel direkt an der Lötstelle."
    ),
    changes=[FIRST_RELEASE],
)
def cable_gland(raw: BaseParams) -> PartResult:
    params = cast(CableGlandParams, raw)
    entry = standards.tube(params.size)
    diameter = entry.outer + params.play

    through = shapes.cylinder(diameter, params.wall + 2.0 * shapes.OVERLAP)
    through = shapes.moved(through, (0.0, 0.0, -shapes.OVERLAP))
    parts = [through]
    features = [
        bore("bore_1", diameter, (0.0, 0.0, params.wall / 2.0), depth=params.wall, through=True)
    ]

    if params.strain_relief:
        gap = params.relief_gap or diameter * 0.8
        # Der Kanal hinter der Wand, auf den Klemmspalt verengt: das Kabel geht
        # durch das runde Loch hinein und wird im Schlitz dahinter gehalten.
        channel = shapes.box(gap, diameter * 2.5, diameter)
        parts.append(shapes.moved(channel, (0.0, 0.0, params.wall)))
        features.append(
            face(
                "relief_1",
                gap * diameter,
                (0.0, 0.0, params.wall + diameter / 2.0),
                (1.0, 0.0, 0.0),
            )
        )

    return result(union(*parts), *features)
