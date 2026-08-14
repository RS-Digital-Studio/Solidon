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
from typing import cast

from app.core.geom.mesh import MeshData
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, face, pin, result, subtract, union
from app.core.knowledge.parts.registry import PartChange, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
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
        unit="grad",
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
    features=["pin", "bore"],
    doc=_(
        "Stift oder Bohrung als Paar. Das Spiel kommt aus dem Materialprofil, damit "
        "eine spätere Kalibrierung auch alte Projekte erreicht."
    ),
    changes=[FIRST_RELEASE],
)
def dowel(raw: BaseParams) -> PartResult:
    params = cast(DowelParams, raw)
    is_pin = params.kind == "pin"
    diameter = params.diameter if is_pin else params.diameter + params.play
    # Eine Fase breiter als der Radius schnitte den Stift entzwei. Der
    # deklarierte Bereich erlaubt beides unabhängig, also hält der Baustein die
    # Grenze selbst ein.
    chamfer = min(params.chamfer, diameter / 2.0 - 0.2)

    body = _profile(params.shape, diameter, params.length)
    if chamfer > 0.0:
        lead = shapes.cone(diameter, diameter - 2.0 * chamfer, chamfer)
        if is_pin:
            body = subtract(
                body,
                shapes.moved(_ring(diameter, chamfer), (0.0, 0.0, params.length - chamfer)),
            )
        else:
            body = union(body, shapes.moved(lead, (0.0, 0.0, -chamfer)))

    if is_pin:
        return result(
            body,
            pin("pin_1", diameter, (0.0, 0.0, params.length / 2.0), length=params.length),
        )
    return result(
        body,
        bore("bore_1", diameter, (0.0, 0.0, params.length / 2.0), depth=params.length),
    )


def _profile(shape: str, diameter: float, length: float) -> MeshData:
    """Der Querschnitt eines Verbinders, auf ``length`` hochgezogen.

    ``diameter`` ist bei allen dreien das Maß über die breiteste Stelle —
    beim Sechskant die Schlüsselweite, beim Schwalbenschwanz die breite Seite.
    So bleibt die Planung dieselbe: Sie sucht Platz für einen Kreis von diesem
    Durchmesser, und was hineingelegt wird, passt in jeden Fall hinein.

    Die Fase bleibt für alle drei dieselbe Rechnung, weil sie über den
    Umkreis arbeitet (:func:`_ring`): Am Stift schneidet sie die Ecken oben
    schräg an, an der Bohrung setzt sie eine runde Einführung vor ein
    kantiges Loch. Beides ist genau das, was eine Fase tun soll.
    """
    width = diameter
    if shape == "hex":
        return shapes.hexagon(width, length)
    if shape == "dovetail":
        return shapes.dovetail(width, length)
    return shapes.cylinder(width, length)


def _ring(diameter: float, chamfer: float):  # type: ignore[no-untyped-def]
    """Das Material, das eine Fase von der Oberkante eines Zylinders nimmt."""
    outer = shapes.cylinder(diameter + 2.0 * shapes.OVERLAP, chamfer + shapes.OVERLAP)
    inner = shapes.cone(diameter, diameter - 2.0 * chamfer, chamfer)
    return subtract(outer, inner)
