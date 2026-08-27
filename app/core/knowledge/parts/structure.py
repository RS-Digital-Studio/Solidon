"""Bausteine, die etwas versteifen, hindurchführen oder anbinden (Bauplan §24.1).

Hier liegen: die Versteifungsrippe, die Kabeldurchführung mit Zugentlastung,
die Nutfeder für Aluprofil, der Kabelclip und der Eckwinkel. Das ist die Sorte
Sache, die hundertmal von Hand gezeichnet und in der Hälfte der Fälle falsch
wird — eine Rippe, die dicker ist als die Wand, die sie versteift, zeichnet sich
durch; eine Durchführung ohne Zugentlastung reißt den Draht aus der Lötstelle.

Später dazugekommen ist die **Nutfeder für Aluprofil**. Sie schließt eine Lücke,
die anders lag als die beiden: Die Nutmaße standen seit der Erstbestückung in der
Normteiltabelle (§24.2), und gelesen hat sie kein Baustein — nachschlagen konnte
man sie, verbauen nicht.
"""

from __future__ import annotations

from typing import cast

from app.core.geom.mesh import MeshData
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

#: Was von der Öffnung eines Clips mindestens bleibt, wenn die Verengung sie
#: rechnerisch schließen würde. Kein Maß aus einer Tabelle, sondern die Grenze,
#: unter der ein Quader keine Breite mehr hat.
MIN_GAP = 0.2

THIN_WALL_KEEPS_THE_RIB_PRINTABLE = PartChange(
    version="5",
    date="2026-08-25",
    reason=(
        "Die abgeleitete Dicke fiel an dünnen Wänden unter das Druckbare: Zwei "
        "Drittel einer 0,4-mm-Wand sind 0,264 mm und damit schmaler als eine "
        "Bahn der Düse; auch 0,8 mm Wand ergaben mit 0,528 mm weniger als die "
        "Mindestwandstärke eines PETG-Profils. Unterhalb von 1,2 mm Wand ist "
        "die Rippe jetzt so dick wie die Wand selbst."
    ),
    effect=(
        "Nur bei einer Wandstärke unter 1,2 mm und nur, wenn die Dicke nicht von "
        "Hand gesetzt ist: Statt zwei Dritteln der Wand steht dort jetzt die volle "
        "Wandstärke. Aus 0,264 mm werden 0,4 mm, aus 0,528 mm werden 0,8 mm. Ab "
        "1,2 mm Wand ändert sich kein Maß — dort war die Zwei-Drittel-Regel schon "
        "immer die größere der beiden Zahlen."
    ),
)

THIN_WALL_KEEPS_THE_GUSSET_PRINTABLE = PartChange(
    version="2",
    date="2026-08-25",
    reason=(
        "Die abgeleitete Dicke fiel an dünnen Wänden unter das Druckbare: Zwei "
        "Drittel einer 0,4-mm-Wand sind 0,264 mm und damit schmaler als eine "
        "Bahn der Düse; auch 0,8 mm Wand ergaben mit 0,528 mm weniger als die "
        "Mindestwandstärke eines PETG-Profils. Unterhalb von 1,2 mm Wand ist "
        "die Rippe jetzt so dick wie die Wand selbst."
    ),
    effect=(
        "Nur bei einer Wandstärke unter 1,2 mm und nur, wenn die Dicke nicht von "
        "Hand gesetzt ist: Statt zwei Dritteln der Wand steht dort jetzt die volle "
        "Wandstärke. Aus 0,264 mm werden 0,4 mm, aus 0,528 mm werden 0,8 mm. Ab "
        "1,2 mm Wand ändert sich kein Maß — dort war die Zwei-Drittel-Regel schon "
        "immer die größere der beiden Zahlen."
    ),
)

RIB_MEETS_THE_MINIMUM_WALL = PartChange(
    version="10",
    date="2026-08-26",
    reason=(
        "Die Untergrenze der Rippendicke lag mit 0,8 mm unter der "
        "Mindestwandstärke, die jedes ausgelieferte Profil meldet (zwei "
        "Extrusionsbreiten, also 0,84 mm bei einer 0,42er Bahn). Eine 1,0-mm-Wand "
        "bekam damit eine 0,80-mm-Rippe — unter dem Maß, das Version 5 selbst als "
        "Kriterium nennt."
    ),
    effect=(
        "Nur zwischen 0,8 und 1,27 mm Wandstärke und nur, wenn die Dicke nicht von "
        "Hand gesetzt ist: Aus 0,80 mm werden 0,84 mm. Darüber war die "
        "Zwei-Drittel-Regel schon immer die größere der beiden Zahlen, darunter "
        "ist die Rippe so dick wie die Wand."
    ),
)

#: Zwei Anlässe, ein Eintrag: Ein Änderungsverlauf trägt je Stand **eine**
#: Zahl, und zwei Einträge mit derselben stiegen nicht (``test_every_change_log
#: _climbs``). Beide fallen auf denselben Tag und denselben Baustein.
GUSSET_MEASURES_AND_NAMES_ITS_FACE = PartChange(
    version="10",
    date="2026-08-26",
    reason=(
        "Zwei Dinge am Eckwinkel. Erstens leitet er seine Dicke aus derselben "
        "Regel ab wie die Rippe und erbte damit deren zu niedrige Untergrenze von "
        "0,8 mm — unter der Mindestwandstärke, die jedes ausgelieferte Profil "
        "meldet. Zweitens nannte das Merkmal ``gusset_1`` als Mitte seiner "
        "Auflagefläche den Ursprung, und der ist bei diesem Keil die vordere "
        "**Kante**: Die Unterseite läuft von y = 0 bis y = Schenkel (§24.1)."
    ),
    effect=(
        "Die Dicke ändert sich nur zwischen 0,8 und 1,27 mm Wandstärke und nur, "
        "wenn sie nicht von Hand gesetzt ist: Aus 0,80 mm werden 0,84 mm. Wer "
        "einen weiteren Baustein oder eine Operation an ``gusset_1`` ausrichtet, "
        "trifft jetzt die Mitte der Auflagefläche statt ihrer Vorderkante — das "
        "sind ein halber Schenkel, bei der Vorgabe also 6 mm."
    ),
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

#: Was von einer abgeleiteten Rippendicke mindestens bleibt.
#:
#: Die Zwei-Drittel-Regel beantwortet, wie dick eine Rippe sein darf, ohne sich
#: auf der Sichtseite abzuzeichnen — sie schützt vor einer **Einfallstelle**.
#: An einer Wand, die selbst schon an der Grenze des Druckbaren liegt, gibt es
#: keine Einfallstelle mehr, wohl aber eine Rippe, die niemand drucken kann:
#: Bei einer 0,4-mm-Wand kamen zwei Drittel davon heraus, also 0,264 mm, und
#: das ist schmaler als eine einzige Bahn der Düse. Auch 0,8 mm Wand ergaben
#: mit 0,528 mm noch weniger als die Mindestwandstärke. Unterhalb dieser
#: Schwelle ist die Rippe deshalb so dick wie die Wand, an der sie sitzt —
#: dicker zu werden als die Wand hilft ihr nicht.
#:
#: **Der Wert ist die Mindestwandstärke selbst, nicht ein Wert knapp darunter.**
#: Er stand auf 0,8, und das ist genau der Fehler, vor dem der Absatz darüber
#: warnt: ``Profile.minimum_wall_thickness`` ist zwei Extrusionsbreiten (§39),
#: also 0,84 mm bei den 0,42er-Düsen, die fünfzehn der sechzehn ausgelieferten
#: Druckerprofile führen. Eine 1,0-mm-Wand bekam damit eine 0,80-mm-Rippe —
#: unter dem Maß, das der Änderungstext von Version 5 selbst als Kriterium
#: nennt.
#:
#: **Warum eine Zahl und kein Profilverweis.** Ein ``.py``-Baustein bekommt kein
#: Profil: ``PartSpec.fn`` nimmt nur seine Parameter, und den profilbewussten
#: Weg (``build_with_profile``) gibt es bisher allein für Rezepte. Eine Zahl,
#: die sich beim Import aus dem Standardprofil holt, wäre schlechter als diese:
#: Sie sähe profilbewusst aus, folgte aber dem Drucker, den der Kunde *nicht*
#: eingestellt hat, und ein überschriebenes Profil verschöbe Maße, ohne dass
#: ``parts_version`` es je bemerkt (§24.4). Die drei Prusa-Profile mit 0,45er
#: Bahn liegen mit 0,90 mm darüber; dort bleibt die Rippe eine Bahnbreite unter
#: ihrer Mindestwand, und das ist der Rest, den erst ein Profil im Baustein
#: schließt.
MIN_RIB = 0.84


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
    changes=[
        FIRST_RELEASE,
        FACE_GIVES_DIRECTION,
        THIN_WALL_KEEPS_THE_RIB_PRINTABLE,
        RIB_MEETS_THE_MINIMUM_WALL,
    ],
)
def rib(raw: BaseParams) -> PartResult:
    params = cast(RibParams, raw)
    thickness = params.thickness or max(params.wall * RIB_SHARE, min(params.wall, MIN_RIB))

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
        doc=AUTO_FROM_PROFILE_DOC,
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
    changes=[FIRST_RELEASE, MOUTH_AT_ORIGIN, FACE_GIVES_DIRECTION],
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
        doc=AUTO_FROM_PROFILE_DOC,
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
    changes=[PROFILE_TONGUE_ADDED, FACE_GIVES_DIRECTION],
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


CABLE_CLIP_ADDED = PartChange(
    version="1",
    date="2026-08-24",
    reason="Kabelclip — die dünnste Gruppe des Katalogs war die meistgefragte.",
)


@op_params
class CableClipParams(BaseParams):
    size: str = param(
        title=_("Kabel"),
        default="cable-5",
        choices=_TUBES,
        doc=_("Was der Clip halten soll — Kabel oder Schlauch aus der Tabelle."),
    )
    width: float = param(
        title=_("Breite"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=40.0,
        doc=_("Wie breit der Bügel ist, längs des Kabels gemessen."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.8,
        maximum=10.0,
        doc=_("Dicke des Bügels. Zu dünn federt er auf, zu dick federt er nicht."),
    )
    grip: float = param(
        title=_("Verengung"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        doc=_(
            "Wie weit die Öffnung je Seite enger ist als das Kabel — das ist es, "
            "was den Clip halten lässt. Null heißt: ein Fünftel des Durchmessers."
        ),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=AUTO_FROM_PROFILE_DOC,
    )


@register_part(
    name="cable_clip",
    title=_("Kabelclip"),
    group="routing",
    params=CableClipParams,
    features=["seat"],
    doc=_(
        "Ein Bügel, der auf eine Fläche kommt und ein Kabel hält. Die Öffnung ist "
        "enger als das Kabel: Man drückt es hinein, und es bleibt."
    ),
    caveat=_(
        "Nicht für Kabel, die unter Zug stehen — dafür ist die Kabeldurchführung "
        "mit Zugentlastung da. Ein Clip führt, er hält nicht fest."
    ),
    changes=[CABLE_CLIP_ADDED],
)
def cable_clip(raw: BaseParams) -> PartResult:
    """Ein liegender C-Bügel auf einem Sockel.

    Der Sockel trägt zwei Aufgaben, und die zweite ist die wichtigere: Er gibt
    dem Kabel eine Auflage, und er gibt dem Bügel eine **Fläche** zum Aufsetzen.
    Ein Ring, der die Modelloberfläche nur tangential berührt, träfe sie in
    einer Linie — genau der Fall, an dem eine Boolesche Operation zuverlässig
    scheitert (§39). Die untere Hälfte des Rings steckt deshalb im Sockel.
    """
    params = cast(CableClipParams, raw)
    entry = standards.tube(params.size)

    inner = entry.outer + params.play
    outer = inner + 2.0 * params.wall
    base = params.wall
    centre = base + inner / 2.0

    # **Die Verengung wird gekappt, nicht abgelehnt.** Der Bereichstest fährt
    # genau diese Ecke: Bei ``grip`` = 5 und einem 4-mm-Schlauch bliebe eine
    # Öffnung von minus sechs Millimetern, und ein Quader mit negativer Breite
    # ist kein Fehler des Nutzers, sondern einer der Grenze. Was bleibt, ist
    # ein Clip, der ganz geschlossen ist — unbrauchbar, aber baubar, und die
    # Grenzen des Feldes sagen es vorher.
    grip = params.grip or inner / 5.0
    gap = max(inner - 2.0 * grip, MIN_GAP)

    def lying(diameter: float, length: float) -> MeshData:
        """Ein Zylinder mit der Achse in Y — das Kabel läuft längs, nicht quer."""
        upright = shapes.cylinder(diameter, length)
        centred = shapes.moved(upright, (0.0, 0.0, -length / 2.0))
        return shapes.turned(centred, 90.0, (1.0, 0.0, 0.0))

    ring = subtract(
        shapes.moved(lying(outer, params.width), (0.0, 0.0, centre)),
        shapes.moved(lying(inner, params.width + 2.0 * shapes.OVERLAP), (0.0, 0.0, centre)),
    )
    # Der Schnitt beginnt in der Ringmitte und geht nach oben hinaus: Was
    # darunter liegt, trägt das Kabel, was darüber lag, ist die Öffnung.
    mouth = shapes.moved(
        shapes.box(gap, params.width + 2.0 * shapes.OVERLAP, outer),
        (0.0, 0.0, centre),
    )
    body = union(
        shapes.box(outer, params.width, base),
        subtract(ring, mouth),
    )

    return result(
        body,
        # Die Auflage des Kabels: die Oberseite des Sockels, innerhalb des
        # Bügels. Nach oben gerichtet, denn dort liegt, was sie trägt.
        face("seat_1", inner * params.width, (0.0, 0.0, base), (0.0, 0.0, 1.0)),
    )


GUSSET_ADDED = PartChange(
    version="1",
    date="2026-08-25",
    reason="Eckwinkel — die Rippe verstärkt eine Wand, die Ecke zwischen zweien blieb offen.",
)


@op_params
class GussetParams(BaseParams):
    legs: float = param(
        title=_("Schenkel"),
        default=12.0,
        unit="mm",
        minimum=2.0,
        maximum=100.0,
        doc=_("Wie weit der Winkel an beiden Wänden entlangreicht."),
    )
    thickness: float = param(
        title=_("Dicke"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=20.0,
        doc=_(
            "Wie dick der Winkel ist, längs der Kante gemessen. Null heißt: so "
            "dick wie die Rippe es täte — zwei Drittel der Wand."
        ),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.4,
        maximum=20.0,
        placement="advanced",
        doc=_("Die Wand, an der er sitzt — sie bestimmt die Vorgabe für die Dicke."),
    )


@register_part(
    name="gusset",
    title=_("Eckwinkel"),
    group="structure",
    params=GussetParams,
    features=["gusset"],
    doc=_(
        "Dreieck in einer Innenecke: Es hält zwei Wände im rechten Winkel, wo sie "
        "sonst aufklappen. Der Klassiker gegen eine Ecke, die beim Anfassen federt."
    ),
    caveat=_(
        "Nicht in eine Ecke, durch die etwas hindurchmuss — er füllt sie diagonal. "
        "Für eine Wand, die für sich zu weich ist, ist die Versteifungsrippe da."
    ),
    changes=[
        GUSSET_ADDED,
        THIN_WALL_KEEPS_THE_GUSSET_PRINTABLE,
        GUSSET_MEASURES_AND_NAMES_ITS_FACE,
    ],
)
def gusset(raw: BaseParams) -> PartResult:
    """Ein dreieckiges Prisma, das in der Ecke steht.

    **Die Ecke ist die Kante, nicht die Fläche.** Der Baustein wird an eine
    Fläche gesetzt und wächst von ihr weg (+Z) und an ihr entlang (+Y) — die
    zweite Wand steht dort, wo er endet. Wer ihn in die Mitte einer Fläche
    setzt, bekommt eine Rampe; das ist nicht falsch, nur nutzlos, und der
    ``caveat`` sagt es.

    Gebaut wird er aus ``shapes.wedge``, demselben Keil, aus dem die Rippe
    ihren Auslauf nimmt. Eine zweite Form für dieselbe Sache wäre eine, die
    irgendwann anders aussieht.

    **Drei Parameter, nicht vier.** Hier standen zuerst *Breite* und *Dicke*
    nebeneinander, und beide meinten dasselbe Maß — wie viel Material längs der
    Kante steht. Ein Feld, das ein zweites wiederholt, ist kein zusätzlicher
    Freiheitsgrad, sondern eine Frage, auf die zwei Antworten möglich sind und
    nur eine wirkt. Geblieben ist *Dicke*, weil das Wort sagt, worum es geht.
    """
    params = cast(GussetParams, raw)
    thickness = params.thickness or max(params.wall * RIB_SHARE, min(params.wall, MIN_RIB))

    # ``wedge(width, depth, height, tip)`` liegt in X breit, läuft in Y tief
    # und steht in Z hoch. Für die Ecke heißt das: die Breite ist die Kante,
    # Tiefe und Höhe sind die zwei Schenkel.
    body = shapes.wedge(thickness, params.legs, params.legs, 0.0)

    return result(
        body,
        # Die Fläche, mit der er an der ersten Wand liegt: unten, so lang wie
        # der Schenkel und so dick wie er selbst.
        #
        # **Ihre Mitte, nicht ihre Kante.** Der Keil steht in x über die Dicke
        # zentriert und läuft in y von 0 bis zum Schenkel — der Ursprung ist
        # damit die Vorderkante dieser Fläche. Hier stand er trotzdem, und wer
        # einen Baustein an ``gusset_1`` ausrichtete, setzte ihn einen halben
        # Schenkel daneben (bei der Vorgabe 6 mm). Ein Merkmal ist eine Zusage
        # an den nächsten Schritt (§24.1), und „centre" ist darin kein Wort für
        # den Anfang.
        face(
            "gusset_1",
            params.legs * thickness,
            (0.0, params.legs / 2.0, 0.0),
            (0.0, 0.0, -1.0),
        ),
    )
