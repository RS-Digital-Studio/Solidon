"""Bausteine, die etwas versteifen, hindurchführen oder anbinden (Bauplan §24.1).

Die letzten zwei der dreizehn aus der Erstbestückung: die Versteifungsrippe und
die Kabeldurchführung mit Zugentlastung. Beides ist die Sorte Sache, die
hundertmal von Hand gezeichnet und in der Hälfte der Fälle falsch wird — eine
Rippe, die dicker ist als die Wand, die sie versteift, zeichnet sich durch; eine
Durchführung ohne Zugentlastung reißt den Draht aus der Lötstelle.

Später dazugekommen ist die **Nutfeder für Aluprofil**. Sie schließt eine Lücke,
die anders lag als die beiden: Die Nutmaße standen seit der Erstbestückung in der
Normteiltabelle (§24.2), und gelesen hat sie kein Baustein — nachschlagen konnte
man sie, verbauen nicht.
"""

from __future__ import annotations

from typing import cast

from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, result, union
from app.core.knowledge.parts.registry import MOUTH_AT_ORIGIN, PartChange, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.i18n import _

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)

PROFILE_TONGUE_ADDED = PartChange(
    version="1",
    date="2026-08-20",
    reason=(
        "Die Aluprofil-Nutmaße lagen seit der Erstbestückung in der Tabelle, "
        "ohne dass ein Baustein sie las (§24.2)."
    ),
)

_TUBES = standards.tube_sizes()
_PROFILES = standards.profile_sizes()

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
        "Rippe mit schrägem Auslauf: Sie verstärkt eine Wand, ohne sie dicker zu "
        "machen. Sie bleibt dünner als die Wand, an der sie sitzt — sonst "
        "zeichnet sie sich auf der anderen Seite ab."
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
    changes=[FIRST_RELEASE, MOUTH_AT_ORIGIN],
)
def cable_gland(raw: BaseParams) -> PartResult:
    params = cast(CableGlandParams, raw)
    entry = standards.tube(params.size)
    diameter = entry.outer + params.play

    # Der Ursprung ist die Mündung auf der Außenseite, das Loch geht nach unten
    # durch die Wand (§24.1). Vorher wuchs es nach oben — wer die angeklickte
    # Fläche als Position übernahm, bekam ein Loch in der Luft darüber.
    through = shapes.cylinder(diameter, params.wall + 2.0 * shapes.OVERLAP)
    through = shapes.moved(through, (0.0, 0.0, -params.wall - shapes.OVERLAP))
    parts = [through]
    features = [
        bore("bore_1", diameter, (0.0, 0.0, -params.wall / 2.0), depth=params.wall, through=True)
    ]

    if params.strain_relief:
        gap = params.relief_gap or diameter * 0.8
        # Der Kanal hinter der Wand, auf den Klemmspalt verengt: das Kabel geht
        # durch das runde Loch hinein und wird im Schlitz dahinter gehalten.
        channel = shapes.box(gap, diameter * 2.5, diameter)
        parts.append(shapes.moved(channel, (0.0, 0.0, -params.wall - diameter)))
        features.append(
            face(
                "relief_1",
                gap * diameter,
                (0.0, 0.0, -params.wall - diameter / 2.0),
                (1.0, 0.0, 0.0),
            )
        )

    return result(union(*parts), *features)


@op_params
class ProfileTongueParams(BaseParams):
    size: str = param(
        title=_("Profil"),
        default="2020",
        choices=_PROFILES,
        doc=_("Die Nutgröße der Schiene — bei den üblichen Profilen die Zahl im Namen."),
    )
    length: float = param(
        title=_("Länge"),
        default=20.0,
        unit="mm",
        minimum=6.0,
        maximum=200.0,
        doc=_("Wie weit die Feder in der Nut entlangläuft. Länger hält mehr."),
    )
    lead_in: float = param(
        title=_("Einführschräge"),
        default=1.5,
        unit="mm",
        minimum=0.0,
        maximum=6.0,
        doc=_(
            "Die Enden laufen über diese Länge auf Halsbreite zu, damit sich die "
            "Feder einschieben lässt statt an der ersten Kante zu klemmen."
        ),
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
    head: float = param(
        title=_("Kopfhöhe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=8.0,
        placement="advanced",
        doc=_(
            "Null heißt: so hoch, dass der Kopf die Kammer ausfüllt und den "
            "Nutgrund nicht berührt. Mehr als die Kammertiefe passt nicht hinein."
        ),
    )


@register_part(
    name="profile_tongue",
    title=_("Nutfeder für Aluprofil"),
    group="structure",
    params=ProfileTongueParams,
    features=["tongue"],
    doc=_(
        "Ein T-förmiger Fuß, der von der Stirnseite in die Nut einer Aluschiene "
        "geschoben wird und dort hält. Hals und Kopf kommen aus der "
        "Normteiltabelle. Zum Drucken liegt die Feder am besten mit der "
        "Nutrichtung flach — steht sie senkrecht, ist die Schulter unter dem "
        "Kopf ein Überhang."
    ),
    changes=[PROFILE_TONGUE_ADDED],
)
def profile_tongue(raw: BaseParams) -> PartResult:
    params = cast(ProfileTongueParams, raw)
    entry = standards.profile_slot(params.size)

    # Alle vier Maße aus der Tabelle, keines im Code (§24.2). Das Spiel geht
    # jeweils von der Feder ab, nie auf die Nut auf: Die Nut ist gegeben.
    neck_width = entry.slot - params.play
    head_width = entry.core - params.play
    # Der Hals überbrückt den Steg. Das Spiel kommt hier *dazu*, damit der Kopf
    # unter der Stegunterseite gleiten kann statt an ihr zu schleifen; unter
    # Zug wandert die Feder um dieses Maß und trägt dann.
    neck_height = entry.lip + params.play
    # Zweimal das Spiel: einmal hat es der Hals nach unten verbraucht, einmal
    # bleibt es als Luft über dem Nutgrund. Mit nur einem Abzug kürzte sich das
    # Spiel in der Gesamttiefe weg — die Feder war genau `lip + depth` hoch und
    # stieß mit null Luft auf, also klemmte der gedruckte Kopf, bevor er am
    # Steg trug. Eine Passung wird an der Differenz gemessen und nicht daran,
    # dass beide Hälften für sich stimmen.
    head_height = params.head or entry.depth - 2.0 * params.play

    # Die Schräge kann nicht länger sein als ein Drittel der Feder — bei 6 mm
    # Länge und 6 mm Schräge bliebe nichts, was noch trägt. Gekappt und nicht
    # abgelehnt: Der Bereichstest fährt genau diese Ecke, und eine Ausnahme
    # dort wäre ein Baustein, der an seiner eigenen Grenze nicht baut.
    lead_in = min(params.lead_in, params.length / 3.0)

    # Der Hals reicht um OVERLAP in den Kopf hinein (§39). Er ist schmaler,
    # also wächst dadurch keine Außenkante — es verschwindet nur die
    # zusammenfallende Fläche zwischen beiden, an der eine Boolesche Operation
    # bricht.
    neck = shapes.box(neck_width, params.length, neck_height + shapes.OVERLAP)
    head = shapes.tapered_bar(head_width, neck_width, params.length, head_height, lead_in)
    body = union(neck, shapes.moved(head, (0.0, 0.0, neck_height)))

    return result(
        body,
        # Die tragende Fläche: die Unterseite des Kopfes links und rechts des
        # Halses, die sich gegen den Steg legt. Nach unten gerichtet, denn dort
        # liegt das Material, das sie hält — die Fläche des eigenen Teils zeigt
        # nach oben.
        face(
            "tongue_1",
            (head_width - neck_width) * params.length,
            (0.0, 0.0, neck_height),
            (0.0, 0.0, -1.0),
        ),
    )
