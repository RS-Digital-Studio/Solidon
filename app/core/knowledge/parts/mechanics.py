"""Bausteine, die sich bewegen und verbinden (Bauplan §24.1, Gruppe
„Mechanik").

Vier der dreizehn: die Schnappverbindung, die Rastnase, das Filmscharnier und
das Stiftpaar. Alle vier leben von Maßen, die ein Drucker entscheidet und kein
Katalog — wie dünn ein Scharnier sein darf, wie weit ein Arm sich biegen darf,
wie viel Spiel ein Stift braucht. Diese Zahlen kommen aus dem Materialprofil,
nie als Literal (AGENTS.md Regel 7): ein Baustein deklariert ``play`` und
lässt es auf null, und ``insert_part`` füllt ein, was das kalibrierte Material
sagt.
"""

from __future__ import annotations

import math
from typing import Final, cast

from app.core.geom.mesh import MeshData
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, pin, result, subtract, union
from app.core.knowledge.parts.registry import PartChange, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.core.units import DEGREE_UNIT
from app.i18n import _

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)

#: Ein Federarm, der sich biegt, muss länger sein als dick, sonst bricht er,
#: statt zu federn. Zehn zu eins ist das Verhältnis, das PLA übersteht.
SNAP_RATIO = 10.0


@op_params
class SnapFitParams(BaseParams):
    width: float = param(
        title=_("Breite"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=60.0,
        doc=_("Breite des Arms. Breiter hält mehr aus und federt weniger weit."),
    )
    length: float = param(
        title=_("Länge"),
        default=16.0,
        unit="mm",
        minimum=4.0,
        maximum=120.0,
        doc=_(
            "Länge des Arms. Mindestens das Zehnfache der Armstärke — kürzer bricht "
            "er, statt zu federn."
        ),
    )
    thickness: float = param(
        title=_("Armstärke"),
        default=1.6,
        unit="mm",
        minimum=0.6,
        maximum=8.0,
        doc=_("Dicke des Arms. Sie bestimmt die Federkraft stärker als alles andere."),
    )
    hook: float = param(
        title=_("Hakenüberstand"),
        default=1.2,
        unit="mm",
        minimum=0.2,
        maximum=6.0,
        doc=_("Wie weit der Haken vorsteht — also wie viel Weg beim Einrasten zurückgelegt wird."),
    )
    lead_angle: float = param(
        title=_("Anlaufwinkel"),
        default=35.0,
        unit=DEGREE_UNIT,
        minimum=10.0,
        maximum=60.0,
        placement="advanced",
        doc=_("Flacher heißt leichter einrasten, steiler heißt fester halten."),
    )


@register_part(
    name="snap_fit",
    title=_("Schnappverbindung"),
    group="mechanics",
    params=SnapFitParams,
    features=["arm", "hook"],
    doc=_(
        "Federnder Arm mit Haken. Der Arm ist mindestens zehnmal so lang wie dick, "
        "sonst bricht er, statt zu federn."
    ),
    changes=[FIRST_RELEASE],
)
def snap_fit(raw: BaseParams) -> PartResult:
    params = cast(SnapFitParams, raw)
    length = max(params.length, params.thickness * SNAP_RATIO)

    arm = shapes.box(params.width, params.thickness, length)
    hook_height = params.hook / math.tan(math.radians(params.lead_angle))
    hook = shapes.wedge(params.width, params.thickness + params.hook, hook_height, params.thickness)
    hook = shapes.turned(hook, 180.0, (1.0, 0.0, 0.0))
    hook = shapes.moved(hook, (0.0, params.thickness / 2.0, length))

    body = union(arm, hook)
    return result(
        body,
        face("arm_1", params.width * length, (0.0, 0.0, length / 2.0), (0.0, -1.0, 0.0)),
        face(
            "hook_1",
            params.width * params.hook,
            (0.0, params.thickness / 2.0 + params.hook / 2.0, length - hook_height / 2.0),
            (0.0, 0.0, -1.0),
        ),
    )


@op_params
class LatchParams(BaseParams):
    # Die Untergrenzen sind, was eine Düse noch ablegen kann. Eine Rastnase von
    # zwei Zehntelmillimetern ist eine Zahl, kein Baustein (§24.3).
    width: float = param(
        title=_("Breite"),
        default=6.0,
        unit="mm",
        minimum=2.0,
        maximum=60.0,
        doc=_("Breite der Nase entlang der Kante."),
    )
    depth: float = param(
        title=_("Überstand"),
        default=1.0,
        unit="mm",
        minimum=0.4,
        maximum=6.0,
        doc=_("Wie weit die Nase vorsteht. Das ist der Weg, den das Gegenstück aufbiegen muss."),
    )
    height: float = param(
        title=_("Höhe"),
        default=3.0,
        unit="mm",
        minimum=1.0,
        maximum=30.0,
        doc=_("Höhe der Nase. Die Anlaufschräge sitzt oben, die gerade Haltefläche unten."),
    )
    negative: bool = param(
        title=_("Als Aussparung"),
        default=False,
        doc=_("Die Gegenseite: dieselbe Form, aber mit Spiel und zum Abziehen."),
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


@register_part(
    name="latch",
    title=_("Rastnase"),
    group="mechanics",
    params=LatchParams,
    features=["ramp"],
    doc=_(
        "Nase mit Anlaufschräge nach oben und gerader Haltefläche nach unten — "
        "druckt ohne Stütze und hält gegen Zug."
    ),
    changes=[FIRST_RELEASE],
)
def latch(raw: BaseParams) -> PartResult:
    params = cast(LatchParams, raw)
    grow = params.play if params.negative else 0.0

    body = shapes.wedge(params.width + 2.0 * grow, params.depth + grow, params.height + grow, 0.0)
    body = shapes.turned(body, 180.0, (1.0, 0.0, 0.0))
    body = shapes.moved(body, (0.0, 0.0, params.height + grow))

    return result(
        body,
        face(
            "ramp_1",
            params.width * params.height,
            (0.0, params.depth / 2.0, params.height / 2.0),
            (0.0, 1.0, 0.0),
        ),
    )


@op_params
class HingeParams(BaseParams):
    width: float = param(
        title=_("Breite"),
        default=30.0,
        unit="mm",
        minimum=5.0,
        maximum=300.0,
        doc=_("Länge der Scharnierachse — so breit wird der Deckel, der daran hängt."),
    )
    leaf: float = param(
        title=_("Flügellänge"),
        default=15.0,
        unit="mm",
        minimum=3.0,
        maximum=200.0,
        doc=_("Wie weit jeder der beiden Flügel vom Scharnier weg reicht."),
    )
    thickness: float = param(
        title=_("Materialstärke"),
        default=2.0,
        unit="mm",
        minimum=0.8,
        maximum=10.0,
        doc=_("Dicke der beiden Flügel — nicht der dünnen Stelle dazwischen."),
    )
    film: float = param(
        title=_("Scharnierstärke"),
        default=0.4,
        unit="mm",
        minimum=0.2,
        maximum=1.2,
        doc=_("Dünnste Stelle. Unter 0,3 mm reißt PLA, PETG hält mehr aus."),
    )
    gap: float = param(
        title=_("Scharnierbreite"),
        default=1.5,
        unit="mm",
        minimum=0.5,
        maximum=8.0,
        doc=_(
            "Breite der dünnen Stelle. Zu schmal knickt an einer Linie und bricht, "
            "zu breit lässt den Deckel schlackern."
        ),
    )


@register_part(
    name="living_hinge",
    title=_("Filmscharnier"),
    group="mechanics",
    params=HingeParams,
    features=["hinge"],
    doc=_(
        "Zwei Flügel, verbunden durch eine dünne Stelle. Die Schichten laufen quer "
        "zur Biegung, sonst bricht das Scharnier beim ersten Öffnen."
    ),
    changes=[FIRST_RELEASE],
)
def living_hinge(raw: BaseParams) -> PartResult:
    params = cast(HingeParams, raw)
    length = 2.0 * params.leaf + params.gap

    plate = shapes.box(params.width, length, params.thickness)
    groove = shapes.box(params.width + 2.0 * shapes.OVERLAP, params.gap, params.thickness)
    groove = shapes.moved(groove, (0.0, 0.0, params.film))

    body = subtract(plate, groove)
    return result(
        body,
        face("hinge_1", params.width * params.gap, (0.0, 0.0, params.film / 2.0)),
    )


@op_params
class DowelParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=4.0,
        unit="mm",
        minimum=1.0,
        maximum=30.0,
        doc=_(
            "Nenndurchmesser. Stift und Bohrung tragen denselben Wert — das Spiel "
            "dazwischen kommt aus dem Materialprofil."
        ),
    )
    length: float = param(
        title=_("Länge"),
        default=8.0,
        unit="mm",
        minimum=1.0,
        maximum=100.0,
        doc=_("Wie weit der Stift heraussteht, beziehungsweise wie tief die Bohrung geht."),
    )
    kind: str = param(
        title=_("Art"),
        default="pin",
        choices=("pin", "bore"),
        subtractive_on=("bore",),
        doc=_("Der Stift selbst oder die Bohrung dazu."),
    )
    shape: str = param(
        title=_("Form"),
        default="round",
        choices=("round", "hex", "dovetail"),
        placement="advanced",
        doc=_(
            "Der Querschnitt. Rund ist die einfachste und braucht zwei Stück gegen "
            "Verdrehen; Sechskant und Schwalbenschwanz halten schon einzeln, der "
            "Schwalbenschwanz zusätzlich gegen Auseinanderziehen."
        ),
    )
    chamfer: float = param(
        title=_("Fase"),
        default=0.6,
        unit="mm",
        minimum=0.0,
        maximum=3.0,
        placement="advanced",
        doc=_("Erleichtert das Fügen und hält die erste Schicht maßhaltig."),
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


@register_part(
    name="dowel",
    title=_("Passstift und Passbohrung"),
    group="mechanics",
    params=DowelParams,
    version="2",
    features=["pin", "bore"],
    doc=_(
        "Stift oder Bohrung als Paar. Das Spiel kommt aus dem Materialprofil, damit "
        "eine spätere Kalibrierung auch alte Projekte erreicht."
    ),
    changes=[
        FIRST_RELEASE,
        PartChange(
            version="2",
            date="2026-08-21",
            reason="Die Passbohrung trug nichts ab, sondern setzte auf (§24.1).",
            effect=(
                "Auf „Bohrung“ wird das Werkzeug jetzt abgezogen statt vereinigt, und "
                "es liegt unter seiner Mündung statt über ihr. Wer die Bohrung bisher "
                "benutzt hat, bekam einen Zapfen von "
                "Umkreis + Spiel; an dieser Stelle steht jetzt ein Loch."
            ),
        ),
    ],
)
def dowel(raw: BaseParams) -> PartResult:
    params = cast(DowelParams, raw)
    is_pin = params.kind == "pin"
    diameter = params.diameter if is_pin else params.diameter + params.play
    # Eine Fase breiter als der Radius schnitte den Stift entzwei. Der
    # deklarierte Bereich erlaubt beides unabhängig, also hält der Baustein die
    # Grenze selbst ein.
    chamfer = min(params.chamfer, diameter / 2.0 - 0.2)

    if is_pin:
        # Der Stift sitzt **auf** der Fläche: Ursprung ist der Fuß, er wächst
        # nach oben, und die Fase bricht seine Oberkante.
        body = _profile(params.shape, diameter, params.length)
        if chamfer > 0.0:
            body = subtract(
                body,
                shapes.moved(_ring(diameter, chamfer), (0.0, 0.0, params.length - chamfer)),
            )
        return result(
            body,
            pin("pin_1", diameter, (0.0, 0.0, params.length / 2.0), length=params.length),
        )

    # **Die Bohrung liegt unter ihrer Mündung (§24.1)** — wie die Magnettasche,
    # und aus demselben Grund: Der Ursprung eines Bausteins landet auf der
    # angeklickten Fläche, und über der Fläche ist Luft. Sie wuchs nach oben,
    # also nach draußen; abgetragen wurde damit nichts als die Fase, die
    # zufällig unter dem Ursprung lag. Gemessen an einem Klotz von 30 auf 30
    # auf 20: minus 28,6 mm³, wo ein Loch von 9 mm Tiefe hätte stehen sollen.
    body = shapes.moved(_profile(params.shape, diameter, params.length), (0.0, 0.0, -params.length))
    if chamfer > 0.0:
        # Eine Senkung an der Mündung, nach oben weiter werdend — das ist, was
        # eine Fase an einem Loch tut. Vorher verengte sie sich zur Mündung
        # hin, was aus einer Einführung eine Sperre gemacht hätte, wenn sie je
        # im Material gelegen hätte.
        lead = shapes.cone(diameter, diameter + 2.0 * chamfer, chamfer)
        body = union(body, shapes.moved(lead, (0.0, 0.0, -chamfer)))
    return result(
        body,
        bore("bore_1", diameter, (0.0, 0.0, -params.length / 2.0), depth=params.length),
    )


def _profile(shape: str, diameter: float, length: float) -> MeshData:
    """Der Querschnitt eines Verbinders, auf ``length`` hochgezogen.

    **``diameter`` ist immer der Umkreis**, also der Kreis, in den die Form
    hineinpasst — nicht die Schlüsselweite und nicht die breite Seite. Daran
    hängt mehr als eine Bezeichnung: Die Stiftplanung sucht Platz für einen
    Kreis dieses Durchmessers und zieht die Schnittfläche um ihn plus die
    Wandstärke ein. Eine Form, die über diesen Kreis hinausragt, frisst still
    von der Wand, die dort stehen bleiben soll.

    Gemessen war genau das der Fall, bevor diese Umrechnung hier stand: Bei
    ``diameter = 6`` kam der Sechskant auf 6,93 Umkreis und der
    Schwalbenschwanz auf 8,49 — dessen Ecke allein nahm 1,24 mm der 1,6 mm
    Wandreserve. Wer einen dickeren Verbinder will, erhöht den Durchmesser;
    er soll ihn nicht durch die Formwahl geschenkt bekommen.

    Die Fase bleibt für alle drei dieselbe Rechnung, weil sie über denselben
    Umkreis arbeitet (:func:`_ring`): Am Stift schneidet sie die Ecken oben
    schräg an, an der Bohrung setzt sie eine runde Einführung vor ein
    kantiges Loch. Beides ist genau das, was eine Fase tun soll.
    """
    if shape == "hex":
        # Schlüsselweite aus dem Umkreis: beim Sechskant ist sie das
        # √3/2-fache.
        return shapes.hexagon(diameter * math.sqrt(3.0) / 2.0, length)
    if shape == "dovetail":
        # Die weiteste Ecke des Trapezes liegt auf (b/2, t/2) — der Umkreis
        # ist also das √2-fache der breiten Seite.
        return shapes.dovetail(diameter / math.sqrt(2.0), length)
    return shapes.cylinder(diameter, length)


#: Der Anlaufwinkel des Schnapphakens, in Grad. Derselbe Wert wie die Vorgabe
#: von :class:`SnapFitParams` — flacher rastet leichter ein, steiler hält
#: fester, und beides schon einmal abgewogen zu haben genügt.
SNAP_LEAD_ANGLE: Final = 35.0

#: Was eine 0,4er Düse als tragende Wand ablegen kann: zwei Außenwände. Ein
#: Federarm darunter ist keiner — er ist eine Fahne, die beim ersten Einrasten
#: abreißt.
SNAP_MIN_ARM: Final = 0.8


@op_params
class SnapConnectorParams(BaseParams):
    # Vier Millimeter als Untergrenze, und das ist gerechnet: Unter 3,85 mm
    # bleibt bei vollem Spiel im Umkreis kein Platz mehr für einen Arm, der
    # zwei Außenwände dick ist. Die Nahtplanung fragt ohnehin nie darunter —
    # ihre Länge von 1,5 · Ø trifft die Acht-Millimeter-Grenze erst ab 5,33 mm.
    diameter: float = param(
        title=_("Durchmesser"),
        default=6.0,
        unit="mm",
        minimum=4.0,
        maximum=30.0,
        doc=_(
            "Der Kreis, in den der Verbinder hineinpasst — dasselbe Maß wie beim "
            "Passstift, damit die Nahtplanung für beide gleich rechnet."
        ),
    )
    length: float = param(
        title=_("Länge"),
        default=9.0,
        unit="mm",
        minimum=8.0,
        maximum=100.0,
        doc=_(
            "Wie weit der Arm heraussteht, beziehungsweise wie tief die Tasche geht. "
            "Sie bestimmt zugleich die Armstärke: ein Zehntel davon."
        ),
    )
    kind: str = param(
        title=_("Art"),
        default="pin",
        choices=("pin", "bore"),
        subtractive_on=("bore",),
        doc=_("Der Federarm selbst oder die Tasche mit der Rastkante dazu."),
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


@register_part(
    name="snap_connector",
    title=_("Schnappverbinder für eine Naht"),
    group="mechanics",
    params=SnapConnectorParams,
    version="4",
    features=["arm", "catch"],
    doc=_(
        "Federarm und Tasche als Paar — die Hälften rasten ein, statt geklebt zu "
        "werden. Die Armstärke ist ein Zehntel der Länge; kürzer als 8 mm gibt es "
        "ihn nicht, darunter wäre der Arm dünner, als eine Düse ihn tragfähig legt."
    ),
    changes=[
        PartChange(
            version="2",
            date="2026-08-14",
            reason="Der Schnapper als Verbinder in der Trennfuge (§25, Trennen).",
        ),
        PartChange(
            version="3",
            date="2026-08-21",
            reason="Die Rasttasche trug nichts ab, sondern setzte auf (§24.1).",
            effect=(
                "Auf „Tasche“ wird der Schlitz jetzt abgezogen statt vereinigt, und er "
                "liegt unter seiner Mündung statt über ihr. Der Docstring sagte es seit "
                "je — „was hier fehlt, bleibt im Bauteil stehen“ —, die Operation tat es "
                "nicht."
            ),
        ),
        PartChange(
            version="4",
            date="2026-08-21",
            reason="Die Rastkante lag am tiefen Ende der Tasche statt an der Mündung.",
            effect=(
                "Fassung 3 schob die ganze Tasche um ihre Tiefe nach unten — und nahm "
                "die Kerbe für die Rastkante mit ans andere Ende. Der Haken fand dort "
                "nichts, was ihn hält: Der Verbinder ging zusammen und wieder "
                "auseinander. Gebaut wird jetzt von der Mündung nach unten, Schlitz und "
                "Kante einzeln gesetzt."
            ),
        ),
    ],
)
def snap_connector(raw: BaseParams) -> PartResult:
    """Ein Schnappverbinder, wie ihn eine Trennfuge braucht.

    **Warum das ein eigener Baustein ist und kein Wert in der Formliste des
    Passstifts:** Rund, Sechskant und Schwalbenschwanz sind Querschnitte —
    dieselbe Rechnung, ein anderes Vieleck. Ein Schnapper ist ein Mechanismus.
    Er hat einen Arm, der federn muss, einen Haken, der einrastet, und in der
    Gegenseite eine Tasche mit Rastkante *und* Biegeraum. Das durch
    ``_profile`` zu schicken hieße, drei Körper als einen zu behaupten.

    **Die Maße folgen aus der Länge, nicht aus einem Regler.** Die Armstärke
    ist ``length / SNAP_RATIO`` — zehn zu eins ist das Verhältnis, das PLA
    federnd übersteht. Daraus fällt die Untergrenze der Länge von selbst:
    unter 8 mm käme ein Arm unter 0,8 mm heraus, und das ist weniger als zwei
    Außenwände einer 0,4er Düse. Der Haken steht so weit vor, wie der Arm dick
    ist; die Tasche ist entsprechend ``3 t`` tief, denn sie trägt den Arm in
    Ruhe (``t``), den Haken (``t``) und den Weg, den der Arm beim Einrasten
    zurückweicht (noch einmal ``t``).

    **Beides druckt ohne Stütze**, und das war der Einwand, an dem dieser
    Baustein eine Runde lang hing. Der Haken ist ein Keil, der nach oben
    ausläuft — jede Lage kleiner als die darunter. Die Rastkante der Tasche
    ist, wenn die Naht nach oben zeigt, eine Brücke von der Breite des
    Hakenüberstands: bei einem 6-mm-Verbinder 0,9 mm. Das ist keine
    Überhangfläche, über die ein Baustein etwas sagen müsste, sondern eine
    Brücke, die jeder Drucker legt.
    """
    params = cast(SnapConnectorParams, raw)
    is_pin = params.kind == "pin"

    # Die Tasche trägt drei Dinge nebeneinander: den Arm in Ruhe, den Haken
    # daneben und den Weg, den der Arm beim Einrasten zurückweicht — bei einem
    # Haken so tief wie der Arm dick also ``3 t``. Zusammen mit der Breite muss
    # das in den Umkreis passen, für den die Nahtplanung Wand reserviert hat.
    #
    # Daraus folgt eine Obergrenze für die Armstärke, und die *muss* geprüft
    # werden: Länge und Durchmesser sind unabhängig deklariert, und bei
    # Ø 30 mm bei 100 mm Länge käme ein 10 mm dicker Arm heraus — die Tasche stand dann
    # 30,22 mm breit in einem 30er Kreis. Nach unten zu kappen ist dabei die
    # gutmütige Richtung: ein dünnerer Arm federt weicher, ein zu dicker bricht.
    room = math.sqrt(max(params.diameter**2 - (SNAP_MIN_ARM + params.play) ** 2, 0.0))
    thickness = min(params.length / SNAP_RATIO, (room - params.play) / 3.0)
    hook = thickness

    across = 3.0 * thickness + params.play
    width = max(SNAP_MIN_ARM, math.sqrt(max(params.diameter**2 - across**2, 0.0)) - params.play)

    # Wie weit der Haken in Längsrichtung ausläuft. Der Rest der Länge ist die
    # Rastkante: dort trifft die Hakenunterseite auf die Kante der Tasche.
    run = hook / math.tan(math.radians(SNAP_LEAD_ANGLE))
    catch = params.length - run

    # Der ganze Verbinder liegt mittig im Umkreis: der Arm sitzt deshalb nicht
    # auf y = 0, sondern so weit daneben, dass Arm, Haken und Rückweg zusammen
    # symmetrisch stehen.
    rest = across / 2.0 - params.play / 2.0
    arm_centre = rest - hook - thickness / 2.0

    if is_pin:
        arm = shapes.moved(shapes.box(width, thickness, params.length), (0.0, arm_centre, 0.0))
        tip = shapes.wedge(width, hook + shapes.OVERLAP, run)
        tip = shapes.moved(tip, (0.0, arm_centre + thickness / 2.0 - shapes.OVERLAP, catch))
        body = union(arm, tip)
        return result(
            body,
            face(
                "arm_1",
                width * params.length,
                (0.0, arm_centre, params.length / 2.0),
                (0.0, -1.0, 0.0),
            ),
            face(
                "hook_1",
                width * hook,
                (0.0, arm_centre + thickness / 2.0 + hook / 2.0, catch),
                (0.0, 0.0, -1.0),
            ),
        )

    # Die Tasche: erst der ganze Schlitz, dann die Rastkante wieder hinein.
    # Herausgerechnet wird sie und nicht dazugebaut, weil dieser Körper
    # abgezogen wird — was hier fehlt, bleibt im Bauteil stehen.
    depth = params.length + shapes.SEAT_RELIEF
    # Auch diese Tasche liegt unter ihrer Mündung (§24.1) — dieselbe Rechnung
    # wie bei der Passbohrung, und derselbe Fund: nach oben gebaut lag sie
    # vollständig über der Fläche und trug nichts ab.
    #
    # **Verschieben genügt hier aber nicht**, und das ist der Unterschied zur
    # Passbohrung: Die ist bis auf ihre Fase drehsymmetrisch, diese Tasche hat
    # ein Oben und ein Unten. Den ganzen Körper um ``-depth`` zu schieben nahm
    # die Rastkante mit an das **tiefe** Ende — dorthin, wo der Haken erst
    # hinkommt, statt zwischen Mündung und Haken zu stehen. Der Schnapper hielt
    # damit nichts, und `tests/test_split_line.py` hat es gemessen. Gebaut wird
    # deshalb von der Mündung nach unten, Stück für Stück.
    slot = shapes.moved(shapes.box(width + params.play, across, depth), (0.0, 0.0, -depth))
    lip = shapes.box(width + params.play + 2.0 * shapes.OVERLAP, hook, catch)
    lip = shapes.moved(lip, (0.0, across / 2.0 - hook / 2.0, -catch))
    body = subtract(slot, lip)
    return result(
        body,
        face(
            "catch_1",
            width * hook,
            (0.0, across / 2.0 - hook / 2.0, -catch),
            (0.0, 0.0, -1.0),
        ),
    )


def _ring(diameter: float, chamfer: float):  # type: ignore[no-untyped-def]
    """Das Material, das eine Fase von der Oberkante eines Zylinders nimmt."""
    outer = shapes.cylinder(diameter + 2.0 * shapes.OVERLAP, chamfer + shapes.OVERLAP)
    inner = shapes.cone(diameter, diameter - 2.0 * chamfer, chamfer)
    return subtract(outer, inner)
