"""Bausteine, die sich bewegen und verbinden (Bauplan §24.1, Gruppe
„Mechanik").

Hier liegen: die Schnappverbindung, die Rastnase, das Filmscharnier, das
Stiftpaar, der Schnappverbinder für eine Naht, die Scharniere und der
Lagersitz. Das Nennmaß eines Kugellagers kommt aus der Normteiltabelle; was
der Drucker daraus machen muss — Spiel oder Presssitz — aus dem
Materialprofil. Diese Zahlen stehen nie als Literal im Baustein (AGENTS.md
Regel 7): ein Baustein deklariert ``play`` oder ``grip`` und lässt es auf
null, und ``insert_part`` füllt ein, was das kalibrierte Material sagt.
"""

from __future__ import annotations

import math
from typing import Final, cast

from app.core import units
from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, compound, face, pin, result, subtract, union
from app.core.knowledge.parts.registry import (
    FACE_GIVES_DIRECTION,
    FACE_ON_THE_BODY,
    MATERIAL_OF_TARGET,
    FeatureRequirement,
    PartChange,
    WallRequirement,
    register_part,
)
from app.core.knowledge.parts.shapes import Form
from app.core.registry import GRIP_TITLE, op_params, param, play_param
from app.core.types import BaseParams, PartResult
from app.core.units import DEGREE_UNIT, EPS_GEOM
from app.i18n import TranslatableText, _

SNAP_ARM_ANCHOR_ON_SURFACE = PartChange(
    version="15",
    date="2026-09-06",
    reason="Der Anker der Federarmfläche lag in der Mitte des Arms.",
    effect="Der Anker liegt auf der bezeichneten Außenfläche bei minus halber Armdicke.",
)

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)

BEARING_SEAT_ADDED = PartChange(
    version="12",
    date="2026-08-28",
    reason=(
        "Die Kugellagermaße standen in der Normteiltabelle, ließen sich aber in "
        "keinem Baustein verwenden."
    ),
    effect=(
        "Der Katalog kann jetzt eine passgenaue Lageraufnahme schneiden. Alte "
        "Projekte ändern sich nicht, weil sie den neuen Baustein nicht enthalten."
    ),
)

DOWEL_CHAMFER_WITHIN_LENGTH = PartChange(
    version="20",
    date="2026-09-22",
    reason=(
        "Eine Fase länger als der Stift schrumpfte dessen Fuß, und an der Bohrung "
        "reichte die Einführung tiefer als die Bohrung selbst."
    ),
    effect=(
        "Die Fase ist höchstens so lang wie Stift oder Bohrung. Nur Stifte und "
        "Bohrungen, die kürzer sind als ihre Fase, ändern sich: Der Fuß behält seinen "
        "Durchmesser, die Bohrung ihre Tiefe."
    ),
)

DOWEL_DOVETAIL_PROFILE_FIXED = PartChange(
    version="13",
    date="2026-08-31",
    reason=(
        "Der trapezförmige Schwalbenschwanz verlor bei der Umrechnung auf den "
        "Nenn-Umkreis fast ein Drittel seiner druckbaren Querschnittstiefe."
    ),
    effect=(
        "Der Schwalbenschwanz folgt jetzt dem Nenn-Umkreis mit einer gerundeten "
        "Außenseite und einer formschlüssigen Sehne. Sein Umkreis bleibt gleich, "
        "der kleinste Stift hält aber wieder zwei Extrusionsbahnen."
    ),
)

_BEARINGS = standards.bearing_sizes()

#: Ein Federarm, der sich biegt, muss länger sein als dick, sonst bricht er,
#: statt zu federn. Zehn zu eins ist das Verhältnis, das PLA übersteht.
SNAP_RATIO = 10.0


#: Der Anlaufwinkel eines Schnapphakens, in Grad. Flacher rastet leichter
#: ein, steiler hält fester.
#:
#: **Zwei Bausteine, eine Abwägung.** Der Schnapphaken lässt sie einstellen
#: (:class:`SnapFitParams`), der Rundverbinder nicht — er hat keinen
#: solchen Parameter. Die Zahl stand deshalb zweimal da, einmal als
#: Vorgabe und einmal als Konstante, mit „derselbe Wert wie die Vorgabe"
#: im Kommentar daneben. Ein Verweis wandert nicht mit: Wer die Vorgabe
#: eines Tages nachjustiert, hätte den Verbinder zurückgelassen
#: (27.08.2026).
SNAP_LEAD_ANGLE: Final = 35.0

SNAP_FIT_HOOK_FIXED = PartChange(
    version="13",
    date="2026-08-31",
    reason="Der Schnapphaken ragte zur falschen Seite in den Federarm hinein.",
    effect=(
        "Der Haken steht jetzt um den angegebenen Überstand aus dem Arm heraus. "
        "Damit stimmen Geometrie und benannte Hakenfläche überein, und die kleinste "
        "Parameterkombination schneidet sich nicht mehr selbst."
    ),
)

SNAP_FIT_RAMP_AT_THE_TIP = PartChange(
    version="20",
    date="2026-09-22",
    reason=(
        "Der Haken stand verkehrt herum: Die Anlaufschräge zeigte zum Fuß des Arms, "
        "die gerade Fläche zur Spitze. Beim Einschieben traf das Gegenstück zuerst "
        "die gerade Fläche, und der Arm federte nicht aus."
    ),
    effect=(
        "Die Schräge beginnt jetzt an der Spitze und läuft zum Fuß hinaus, die gerade "
        "Haltefläche liegt darunter und zeigt zum Fuß — so, wie die benannte "
        "Hakenfläche es immer sagte. Länge, Armstärke und Hakenüberstand bleiben gleich; "
        "die Hakenfläche sitzt um die halbe Keilhöhe tiefer."
    ),
)


@op_params
class BearingSeatParams(BaseParams):
    size: str = param(
        title=_("Kugellager"),
        default="608",
        choices=_BEARINGS,
        doc=_(
            "Die Nummer steht auf dem Lager. Daneben zeigt Solidon Innenmaß, Außenmaß und Breite."
        ),
    )
    removable: bool = param(
        title=_("Herausnehmbar"),
        default=False,
        doc=_("An heißt: Das Lager lässt sich wechseln. Aus heißt: Es wird fest eingepresst."),
    )
    extra_depth: float = param(
        title=_("Zusatztiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        placement="advanced",
        doc=_("Zusätzlicher Platz hinter dem Lager."),
    )
    play: float = play_param(maximum=2.0, depends_on=("removable", (True,)))
    grip: float = play_param(title=GRIP_TITLE, maximum=2.0, depends_on=("removable", (False,)))


@register_part(
    name="bearing_seat",
    title=_("Kugellager einsetzen"),
    group="mechanics",
    params=BearingSeatParams,
    subtractive=True,
    at_hole=True,
    features=["seat"],
    wall=WallRequirement.not_applicable("Der Baustein ist ein abtragender Werkzeugkörper."),
    doc=_(
        "Schneidet eine passende Tasche für ein Kugellager. Außenmaß und Breite "
        "kommen aus der Tabelle, die Passung aus dem eingestellten Material."
    ),
    caveat=_(
        "Für eine durchgehende Welle zuerst ein Loch setzen und den Lagersitz darauf platzieren."
    ),
    changes=[BEARING_SEAT_ADDED, MATERIAL_OF_TARGET],
)
def bearing_seat(raw: BaseParams) -> PartResult:
    """Eine zylindrische Aufnahme, bündig unter ihrer gewählten Fläche."""
    params = cast(BearingSeatParams, raw)
    entry = standards.bearing(params.size)
    diameter = entry.outer + params.play if params.removable else entry.outer - params.grip
    depth = entry.width + params.extra_depth

    pocket = shapes.cylinder(diameter, depth + BOOLEAN_OVERLAP)
    pocket = shapes.moved(pocket, (0.0, 0.0, -depth))
    return result(
        pocket,
        bore("seat_1", diameter, (0.0, 0.0, -depth / 2.0), depth=depth),
    )


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
        default=SNAP_LEAD_ANGLE,
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
    wall=WallRequirement.not_applicable(
        "Federarm und auslaufender Anlaufkeil dürfen laut Parameterschema bewusst "
        "unter der Profilgrenze liegen und werden an ihren benannten Maßen geprüft."
    ),
    doc=_(
        "Federnder Arm mit Haken zum Einrasten zweier Teile. Der Arm ist "
        "mindestens zehnmal so lang wie dick, sonst bricht er, statt zu federn."
    ),
    changes=[
        FIRST_RELEASE,
        FACE_GIVES_DIRECTION,
        SNAP_FIT_HOOK_FIXED,
        SNAP_ARM_ANCHOR_ON_SURFACE,
        SNAP_FIT_RAMP_AT_THE_TIP,
    ],
)
def snap_fit(raw: BaseParams) -> PartResult:
    params = cast(SnapFitParams, raw)
    hook_height = params.hook / math.tan(math.radians(params.lead_angle))
    # Wie die Federstärke darf auch der Anlaufkeil die wirksame Armlänge
    # erhöhen. Sonst wächst ein großer Haken mit flachem Winkel unter Z = 0
    # durch die Ansatzfläche, statt vollständig auf dem Arm zu liegen.
    length = snap_arm_length(params)
    body = _snap_fit_body(params.width, length, params.thickness, params.hook, hook_height)
    return result(
        body,
        face(
            "arm_1",
            params.width * length,
            (0.0, -params.thickness / 2.0, length / 2.0),
            (0.0, -1.0, 0.0),
        ),
        # Die Haltefläche unter der Schräge, zum Fuß des Arms gerichtet.
        face(
            "hook_1",
            params.width * params.hook,
            (0.0, params.thickness / 2.0 + params.hook / 2.0, length - hook_height),
            (0.0, 0.0, -1.0),
        ),
    )


def snap_arm_length(params: SnapFitParams) -> float:
    """Wirksame Armlänge aus denselben Grenzen wie der gebaute Federkörper."""
    hook_height = params.hook / math.tan(math.radians(params.lead_angle))
    return max(params.length, params.thickness * SNAP_RATIO, hook_height)


def _snap_fit_body(
    width: float,
    length: float,
    thickness: float,
    hook: float,
    hook_height: float,
) -> Form:
    """Federarm und Haken als ein einziger extrudierter Umriss.

    Zwei überlappende Prismen ließen bei extrem langen, dünnen Armen trotz
    Boolescher Vereinigung innere Dreiecke zurück. Der gemeinsame Seitenriss
    enthält dieselbe Form ohne innere Grenzfläche.

    **Die Schräge zeigt zur Spitze.** Das Gegenstück kommt beim Einschieben von
    der Spitze her, gleitet über die Schräge und drückt den Arm zurück; hinter
    ihr rastet es an der geraden Haltefläche ein, die zum Fuß zeigt. Bis zum
    22.09.2026 stand der Haken umgekehrt — gerade Fläche an der Spitze, Schräge
    zum Fuß —, und die benannte Hakenfläche, nach unten gerichtet, beschrieb
    eine Form, die es nicht gab. Der Schnappverbinder nebenan baut seinen
    Haken seit je so.
    """
    half = thickness / 2.0
    catch = length - hook_height
    # Reicht die Schräge bis zum Fuß, gibt es keine Haltefläche über der
    # Ansatzfläche: Dann ist der Umriss ein Viereck, und ein doppelter
    # Polygonpunkt machte dort entartete Dreiecke.
    if catch > EPS_GEOM:
        points = [(-half, 0.0), (half, 0.0), (half, catch), (half + hook, catch)]
    else:
        points = [(-half, 0.0), (half + hook, 0.0)]
    points.extend(((half, length), (-half, length)))
    return shapes.prism_across(points, width)


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
        # Die Gegenseite trägt ab. Ohne diese Angabe galt der feste Wert des
        # Registereintrags, und die Aussparung wurde **vereinigt**: an einer
        # Wand gemessen +12,3 mm³ statt einer Tasche (22.09.2026) — derselbe
        # Fehler, den das Innengewinde am 25.08.2026 hatte.
        subtractive_on=(True,),
        doc=_("Die Gegenseite: dieselbe Form, aber mit Spiel und zum Abziehen."),
    )
    play: float = play_param()


LATCH_STANDS_ON_ITS_BASE = PartChange(
    version="20",
    date="2026-09-22",
    reason=(
        "Die Rastnase stand auf ihrer Spitze: Sie berührte ihre Fläche nur an einer "
        "Kante (6 mm mal 0,005 mm), wuchs um ihre Höhe statt um ihren Überstand hinaus, "
        "und als Aussparung wurde sie aufgesetzt statt abgezogen."
    ),
    effect=(
        "Die Nase liegt jetzt mit ihrer ganzen Grundfläche auf: entlang der Fläche so "
        "hoch wie angegeben, so weit hinaus wie der Überstand, oben die Anlaufschräge, "
        "unten die gerade Haltefläche. An einer Wand richtet sie sich selbst auf. Die "
        "Aussparung trägt ab und lässt ringsum das Spiel. Lage und Maße prüfen."
    ),
)


def _latch_outline(height: float, depth: float, play: float) -> list[tuple[float, float]]:
    """Der Seitenriss der Nase, in YZ, oder ihrer Aussparung vor dem Spiegeln.

    Die Nase: Grundfläche auf z = 0 von y = -height bis 0 — oben ist **-Y**
    (``keeps_up``) —, die Haltefläche bei y = 0 senkrecht hinaus bis zum
    Überstand, die Anlaufschräge von dort zurück zum oberen Ende der Grundfläche.

    Die Aussparung hält um ``play`` Abstand von Haltefläche, Schräge und Spitze.
    Die Schräge wird dafür um ``play`` entlang ihrer Normalen versetzt; die
    spitze obere Ecke eines Versatzes liefe bei einem steilen Keil weit hinaus
    (bei Höhe 1 und Überstand 6 um drei Millimeter), und so tief muss die
    Tasche nicht sein — sie endet eben ``play`` über der Spitze der Nase.
    """
    if play <= EPS_GEOM:
        return [(0.0, 0.0), (0.0, depth), (-height, 0.0)]
    slope = math.hypot(height, depth)
    return [
        (play, 0.0),
        (play, depth + play),
        (play * (height - slope) / depth, depth + play),
        (-height - play * slope / depth, 0.0),
    ]


@register_part(
    name="latch",
    title=_("Rastnase"),
    group="mechanics",
    params=LatchParams,
    features=["ramp"],
    wall=WallRequirement.not_applicable(
        "Die Rastnase läuft funktionsbedingt spitz aus; als Aussparung ist sie zudem "
        "ein abtragender Werkzeugkörper."
    ),
    # Oben ist die Anlaufschräge, unten die Haltefläche: An einer Wand muss die
    # Nase wissen, wo oben ist (``PartSpec.keeps_up``).
    keeps_up=True,
    doc=_(
        "Nase zum Einrasten, mit Anlaufschräge nach oben und gerader "
        "Haltefläche nach unten — "
        "druckt ohne Stütze und hält gegen Zug."
    ),
    changes=[FIRST_RELEASE, FACE_GIVES_DIRECTION, MATERIAL_OF_TARGET, LATCH_STANDS_ON_ITS_BASE],
)
def latch(raw: BaseParams) -> PartResult:
    """Die Nase auf ihrer Grundfläche — oder die Tasche, in die sie einrastet.

    **Sie stand bis zum 22.09.2026 auf ihrer Spitze.** Der Keil wurde um X
    umgedreht und hochgeschoben; heraus kam ein Körper, der seine Fläche nur an
    einer Kante berührte und um seine *Höhe* hinausragte statt um seinen
    Überstand. Nach dem Einsinken um ``BOOLEAN_OVERLAP`` hing die Nase an einem
    Streifen von fünf Tausendstel Millimetern.

    Die Aussparung liegt unter ihrer Mündung (§24.1): der Seitenriss der Nase,
    um das Spiel geweitet und in Z gespiegelt, und ein Hundertstel über die
    Mündung hinaus, damit der Schnitt nicht Fläche auf Fläche trifft (§39).
    Gespiegelt passt sie auf die Nase eines Gegenstücks, dessen Fläche ihr
    gegenübersteht — Haltefläche unten, Schräge oben, wie dort.
    """
    params = cast(LatchParams, raw)
    play = params.play if params.negative else 0.0
    width = params.width + 2.0 * play
    outline = _latch_outline(params.height, params.depth, play)
    slope = math.hypot(params.height, params.depth)
    ramp = (outline[-1], outline[-2])
    centre = ((ramp[0][0] + ramp[1][0]) / 2.0, (ramp[0][1] + ramp[1][1]) / 2.0)
    # Die Schräge der Nase zeigt nach oben (-Y) und hinaus (+Z), vom Körper weg.
    normal = (0.0, -params.depth / slope, params.height / slope)
    if params.negative:
        mouth = outline[0][0], outline[-1][0]
        outline = [
            (mouth[0], BOOLEAN_OVERLAP),
            *((y, -z) for y, z in outline[1:-1]),
            (mouth[1], 0.0),
            (mouth[1], BOOLEAN_OVERLAP),
        ]
        centre = (centre[0], -centre[1])
        # In der Tasche ist die Schräge eine Fläche des Trägers und zeigt in die
        # Tasche hinein, wie bei jedem abtragenden Baustein.
        normal = (0.0, params.depth / slope, params.height / slope)
    body = shapes.prism_across(outline, width)
    return result(
        body,
        # Die Anlaufschräge — die Fläche, über die das Gegenstück gleitet.
        face("ramp_1", width * math.dist(ramp[0], ramp[1]), (0.0, *centre), normal),
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


HINGE_FILM_TOO_THICK = _(
    "Die Scharnierstärke muss kleiner als die Materialstärke der Flügel sein. "
    "Verringern Sie die Scharnierstärke oder verstärken Sie die Flügel."
)


def _hinge_feasible(raw: BaseParams) -> TranslatableText | None:
    """Eine Scharnierzone muss gegenüber beiden Flügeln tatsächlich dünner sein."""
    params = cast(HingeParams, raw)
    return HINGE_FILM_TOO_THICK if params.film >= params.thickness else None


@register_part(
    name="living_hinge",
    title=_("Filmscharnier"),
    group="mechanics",
    params=HingeParams,
    feasible=_hinge_feasible,
    features=["hinge"],
    wall=WallRequirement.not_applicable(
        "Folie und Flügel dürfen laut Parameterschema bewusst unter der Profilgrenze "
        "liegen und werden an ihren benannten Maßen geprüft."
    ),
    lies_flat=True,
    doc=_(
        "Zwei Flügel, verbunden durch eine dünne Stelle. Die Schichten laufen quer "
        "zur Biegung, sonst bricht das Scharnier beim ersten Öffnen."
    ),
    caveat=_(
        "Nicht für ein Teil, das aufrecht gedruckt wird: Die dünne Stelle hält nur, "
        "solange die Schichten quer zur Biegung laufen. Steht das Scharnier "
        "senkrecht auf der Platte, bricht es beim ersten Öffnen."
    ),
    changes=[
        FIRST_RELEASE,
        FACE_GIVES_DIRECTION,
        PartChange(
            version="16",
            date="2026-09-08",
            reason="Scharnierfolie mindestens so dick wie der Flügel ergab eine massive Platte.",
            effect="Diese unbrauchbaren Kombinationen werden mit Änderungsvorschlag abgewiesen; "
            "alle tatsächlich dünneren Scharnierfolien behalten ihre Maße.",
        ),
        FACE_ON_THE_BODY,
    ],
)
def living_hinge(raw: BaseParams) -> PartResult:
    params = cast(HingeParams, raw)
    if _hinge_feasible(params) is not None:
        raise ValidationError("film", HINGE_FILM_TOO_THICK, constraint="feasible")
    length = 2.0 * params.leaf + params.gap

    plate = shapes.box(params.width, length, params.thickness)
    groove = shapes.box(params.width + 2.0 * BOOLEAN_OVERLAP, params.gap, params.thickness)
    groove = shapes.moved(groove, (0.0, 0.0, params.film))

    body = subtract(plate, groove)
    return result(
        body,
        # Die Oberseite der Folie, der Boden der Scharnierrille.
        face("hinge_1", params.width * params.gap, (0.0, 0.0, params.film)),
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
    play: float = play_param()


@register_part(
    name="dowel",
    title=_("Passstift und Passbohrung"),
    group="mechanics",
    params=DowelParams,
    features=["pin", "bore"],
    wall=WallRequirement(
        when="kind",
        equals="bore",
        reason="Die Bohrungsstellung ist ein abtragender Werkzeugkörper.",
    ),
    feature_requirements=(
        FeatureRequirement("pin", when="kind", equals="pin"),
        FeatureRequirement("bore", when="kind", equals="bore"),
    ),
    doc=_(
        "Stift oder Bohrung als Paar, zum Zusammenstecken zweier Teile. Das Spiel "
        "kommt aus dem Materialprofil, damit "
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
        FACE_GIVES_DIRECTION,
        DOWEL_DOVETAIL_PROFILE_FIXED,
        MATERIAL_OF_TARGET,
        DOWEL_CHAMFER_WITHIN_LENGTH,
    ],
)
def dowel(raw: BaseParams) -> PartResult:
    params = cast(DowelParams, raw)
    is_pin = params.kind == "pin"
    diameter = params.diameter if is_pin else params.diameter + params.play
    # Eine Fase breiter als der Radius schnitte den Stift entzwei, eine längere
    # als der Stift verschöbe seine Maße: Am Stift schrumpfte der Fuß (Ø 30,
    # Länge 1, Fase 3: Fuß Ø 26), an der Bohrung wurde sie tiefer als verlangt
    # (drei statt einem Millimeter). Der deklarierte Bereich erlaubt alle drei
    # Maße unabhängig, also hält der Baustein beide Grenzen selbst ein.
    chamfer = min(params.chamfer, diameter / 2.0 - 0.2, params.length)

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
    # Ein Hundertstel über die Mündung hinaus, wie jedes abtragende Werkzeug
    # (§39): Sonst schnitte die Deckfläche genau in der angeklickten Fläche.
    body = shapes.moved(
        _profile(params.shape, diameter, params.length + BOOLEAN_OVERLAP),
        (0.0, 0.0, -params.length),
    )
    if chamfer > 0.0:
        # Eine Senkung an der Mündung, nach oben weiter werdend — das ist, was
        # eine Fase an einem Loch tut. Vorher verengte sie sich zur Mündung
        # hin, was aus einer Einführung eine Sperre gemacht hätte, wenn sie je
        # im Material gelegen hätte. Ein Drehprofil samt Überstand, damit
        # zwischen Kegel und Überstand keine innere Fläche liegt.
        mouth = diameter / 2.0 + chamfer
        lead = shapes.revolved(
            [
                (0.0, -chamfer),
                (diameter / 2.0, -chamfer),
                (mouth, 0.0),
                (mouth, BOOLEAN_OVERLAP),
                (0.0, BOOLEAN_OVERLAP),
            ]
        )
        body = union(body, lead)
    return result(
        body,
        bore("bore_1", diameter, (0.0, 0.0, -params.length / 2.0), depth=params.length),
    )


def _profile(shape: str, diameter: float, length: float) -> Form:
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
        return shapes.rounded_dovetail(diameter, length)
    return shapes.cylinder(diameter, length)


#: Was eine 0,4er Düse als tragende Wand ablegen kann: zwei Außenwände. Ein
#: Federarm darunter ist keiner — er ist eine Fahne, die beim ersten Einrasten
#: abreißt.
SNAP_MIN_ARM: Final = 0.8

SNAP_CONNECTOR_FEATURES_FIXED = PartChange(
    version="13",
    date="2026-08-31",
    reason="Der Haken war im Ergebnis benannt, aber nicht im Register deklariert.",
    effect=(
        "Arm und Haken sind jetzt ausschließlich für den Stift, die Rastkante "
        "ausschließlich für die Tasche als Merkmale deklariert. Die Geometrie bleibt gleich."
    ),
)


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
    play: float = play_param()


@register_part(
    name="snap_connector",
    title=_("Schnappverbinder für eine Naht"),
    group="mechanics",
    params=SnapConnectorParams,
    features=["arm", "hook", "catch"],
    wall=WallRequirement.not_applicable(
        "Der Federarm ist ausdrücklich bis zu zwei Extrusionsbahnen dünn; die "
        "Buchsenstellung ist ein abtragender Werkzeugkörper."
    ),
    feature_requirements=(
        FeatureRequirement("arm", when="kind", equals="pin"),
        FeatureRequirement("hook", when="kind", equals="pin"),
        FeatureRequirement("catch", when="kind", equals="bore"),
    ),
    doc=_(
        "Federarm und Tasche als Paar — die Hälften rasten ein, statt geklebt zu "
        "werden. Die Armstärke ist ein Zehntel der Länge; kürzer als 8 mm gibt es "
        "ihn nicht, darunter wäre der Arm dünner, als eine Düse ihn tragfähig legt."
    ),
    caveat=_(
        "Nicht für kurze Nähte: Der Arm ist ein Zehntel seiner Länge dick, und unter "
        "acht Millimetern legt eine Düse ihn nicht mehr tragfähig. Für kleine "
        "Teile hält eine Rastnase besser."
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
                "Version 3 schob die ganze Tasche um ihre Tiefe nach unten — und nahm "
                "die Kerbe für die Rastkante mit ans andere Ende. Der Haken fand dort "
                "nichts, was ihn hält: Der Verbinder ging zusammen und wieder "
                "auseinander. Gebaut wird jetzt von der Mündung nach unten, Schlitz und "
                "Kante einzeln gesetzt."
            ),
        ),
        # **Ein eigener Eintrag, weil der Stand schon bei 4 lag.**
        # ``FACE_GIVES_DIRECTION`` trägt die Version 4 und passt damit zu den
        # fünf anderen Bausteinen, die ihn führen — dieser hier stand aber
        # bereits auf 4, und zwei gleiche Zahlen hintereinander heißen für
        # ``changed_since``: nichts hat sich geändert. Die Flächenrichtung
        # änderte sein Maß trotzdem, und ein Projekt vom 22.08. erfuhr es nie.
        PartChange(
            version="5",
            date="2026-08-23",
            reason=FACE_GIVES_DIRECTION.reason,
            effect=FACE_GIVES_DIRECTION.effect,
        ),
        SNAP_CONNECTOR_FEATURES_FIXED,
        MATERIAL_OF_TARGET,
        FACE_ON_THE_BODY,
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
        tip = shapes.wedge(width, hook + BOOLEAN_OVERLAP, run)
        tip = shapes.moved(tip, (0.0, arm_centre + thickness / 2.0 - BOOLEAN_OVERLAP, catch))
        body = union(arm, tip)
        return result(
            body,
            face(
                "arm_1",
                width * params.length,
                # Die Rückseite des Arms, wie beim Schnapphaken nebenan.
                (0.0, arm_centre - thickness / 2.0, params.length / 2.0),
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
    slot = shapes.moved(
        shapes.box(width + params.play, across, depth + BOOLEAN_OVERLAP), (0.0, 0.0, -depth)
    )
    lip = shapes.box(width + params.play + 2.0 * BOOLEAN_OVERLAP, hook, catch)
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
    outer = shapes.cylinder(diameter + 2.0 * BOOLEAN_OVERLAP, chamfer + BOOLEAN_OVERLAP)
    inner = shapes.cone(diameter, diameter - 2.0 * chamfer, chamfer)
    return subtract(outer, inner)


HINGE_EYE_ADDED = PartChange(
    version="1",
    date="2026-08-25",
    reason="Scharnierauge — das Filmscharnier biegt, dieses hier dreht.",
)

HINGE_EYE_FACET_WALL_FIXED = PartChange(
    version="13",
    date="2026-08-31",
    reason="Die polygonale Kreisannäherung unterschritt die zugesagte Augenwand.",
    effect=(
        "Der Außendurchmesser wächst um die analytische Facettenkorrektur. "
        "Bohrung und Spiel bleiben unverändert; die kleinste Wand hält jetzt ihr Nennmaß."
    ),
)


@op_params
class HingeEyeParams(BaseParams):
    pin: float = param(
        title=_("Stift"),
        default=3.0,
        unit="mm",
        minimum=1.0,
        maximum=20.0,
        doc=_("Durchmesser des Bolzens, der durchgeht — ein Passstift oder eine Schraube."),
    )
    width: float = param(
        title=_("Breite"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=60.0,
        doc=_("Wie breit das Auge ist, längs der Drehachse gemessen."),
    )
    reach: float = param(
        title=_("Abstand"),
        default=8.0,
        unit="mm",
        # Nicht null: Bei null hat die Lasche keine Länge, und ein Quader ohne
        # Tiefe ist kein Körper — der Bereichstest fand drei Teile statt einem.
        # Ein Auge, das auf der Fläche aufsitzt, wäre ohnehin kein Drehpunkt.
        minimum=1.0,
        maximum=60.0,
        doc=_("Wie weit die Achse von der Fläche wegsteht — das ist der Drehpunkt."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.8,
        maximum=15.0,
        doc=_("Material rings um die Bohrung. Zu dünn reißt beim ersten Zug auf."),
    )
    play: float = play_param(maximum=2.0)


@register_part(
    name="hinge_eye",
    title=_("Scharnierauge"),
    group="mechanics",
    params=HingeEyeParams,
    features=["eye"],
    wall=WallRequirement.from_parameter("wall"),
    doc=_(
        "Eine Lasche mit Bohrung, die sich um einen Bolzen dreht. Zwei davon an "
        "zwei Teilen und ein Passstift dazwischen ergeben ein Scharnier, das "
        "hält — anders als das Filmscharnier, das nur biegt."
    ),
    caveat=_(
        "Ein halbes Scharnier: Das zweite Auge gehört an das Gegenstück, der "
        "Bolzen kommt aus der Bibliothek (Passstift) oder aus dem Handel."
    ),
    changes=[HINGE_EYE_ADDED, HINGE_EYE_FACET_WALL_FIXED, MATERIAL_OF_TARGET],
)
def hinge_eye(raw: BaseParams) -> PartResult:
    """Lasche mit Auge, die Achse liegt parallel zur Fläche.

    **Warum ein halbes Scharnier und kein ganzes.** Ein Scharnier, das schon
    beim Drucken beweglich ist, besteht aus zwei Teilen, die sich gegeneinander
    drehen — und ein Baustein dieser Bibliothek muss **ein** Körper sein
    (`tests/test_parts.py`, „falls apart"). Die beiden Forderungen schließen
    sich aus, und das ist keine Lücke im Test: Ein Baustein wird *angebaut*,
    und was angebaut wird, hängt am Träger. Wer ein Gelenk will, setzt zwei
    Augen und steckt einen Stift durch; den Stift gibt es als ``dowel``.

    Die offene Frage dahinter — ob die Bibliothek erklärt-mehrteilige Bausteine
    kennen soll, also print-in-place-Mechanik — steht im Register und nicht
    hier. Sie ist größer als dieser Baustein.
    """
    params = cast(HingeEyeParams, raw)

    bore_width = params.pin + params.play
    # Ein Kreis mit ``SEGMENTS`` Ecken hat zwischen zwei Eckradien nur den
    # Apothem. Außen- und Bohrungszylinder sind gleich ausgerichtet; ihre
    # gemessene Wand ist deshalb ``wall * cos(pi / SEGMENTS)``. Der
    # Kehrwert gleicht ausschließlich diese Repräsentationsabweichung aus;
    # zwei Geometrietoleranzen halten die Boolesche Rundung innerhalb des
    # zugesagten Nennmaßes.
    # Exakt ist der Kreis ein Kreis, und die Wand ist genau ``wall``
    # (Bericht P2.7, Abschnitt 5.2); die Korrektur gilt dem Netz allein.
    wall = params.wall
    if not shapes.building_exact():
        wall = (params.wall + 2.0 * EPS_GEOM) / units.inscribed_ratio(shapes.SEGMENTS)
    outer = bore_width + 2.0 * wall

    def lying(diameter: float, length: float) -> Form:
        """Ein Zylinder mit der Achse in X — die Drehachse des Scharniers."""
        upright = shapes.cylinder(diameter, length)
        centred = shapes.moved(upright, (0.0, 0.0, -length / 2.0))
        return shapes.turned(centred, 90.0, (0.0, 1.0, 0.0))

    eye_body = shapes.moved(lying(outer, params.width), (0.0, params.reach, outer / 2.0))
    # Die Lasche reicht bis in die Mitte des Auges hinein: Zwei Körper, die sich
    # nur berühren, sind der Fall, an dem eine Boolesche Operation bricht (§39).
    lug = shapes.box(params.width, params.reach, outer)
    body = union(eye_body, shapes.moved(lug, (0.0, params.reach / 2.0, 0.0)))
    body = subtract(
        body,
        shapes.moved(
            lying(bore_width, params.width + 2.0 * BOOLEAN_OVERLAP),
            (0.0, params.reach, outer / 2.0),
        ),
    )

    return result(
        body,
        # Die Drehachse als Bohrung benannt: Wer das Gegenstück setzt, richtet
        # es daran aus.
        bore(
            "eye_1",
            bore_width,
            (0.0, params.reach, outer / 2.0),
            depth=params.width,
            # Die Drehachse liegt in X: ``lying()`` legt den Zylinder um. Ohne
            # diese Angabe gilt die Vorgabe (0, 0, 1), und ein Passstift, an
            # ``eye_1`` ausgerichtet, stünde senkrecht aus dem Auge heraus
            # statt hindurch. ``wall_mount`` macht es genauso.
            axis=(1.0, 0.0, 0.0),
            through=True,
        ),
    )


BARREL_HINGE_ADDED = PartChange(
    version="1",
    date="2026-08-27",
    reason="Bolzenscharnier — das erste erklärt mehrteilige Teil (§24.3).",
)

BARREL_HINGE_CLEARANCE_FIXED = PartChange(
    version="13",
    date="2026-08-31",
    reason="Die Augenwand wurde fälschlich vor dem Druckspalt bemessen.",
    effect=(
        "Der Außendurchmesser wächst jetzt zusätzlich um zweimal das gewählte Spiel. "
        "Damit bleibt die angegebene Wandstärke auch um die bewegliche Bohrung erhalten."
    ),
)


@op_params
class BarrelHingeParams(BaseParams):
    pin: float = param(
        title=_("Bolzen"),
        default=4.0,
        unit="mm",
        minimum=2.0,
        maximum=20.0,
        doc=_("Durchmesser der Achse. Sie wird mitgedruckt und nicht eingesteckt."),
    )
    width: float = param(
        title=_("Breite"),
        default=24.0,
        unit="mm",
        minimum=8.0,
        maximum=120.0,
        doc=_("Gesamtbreite über beide Laschen, längs der Achse gemessen."),
    )
    reach: float = param(
        title=_("Ausladung"),
        default=12.0,
        unit="mm",
        minimum=4.0,
        maximum=60.0,
        doc=_("Wie weit jede Lasche von der Achse wegsteht — der Hebel des Gelenks."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=2.5,
        unit="mm",
        minimum=1.0,
        maximum=15.0,
        doc=_("Material rings um den Bolzen. Zu dünn reißt beim ersten Zug auf."),
    )
    play: float = play_param(maximum=2.0)


@register_part(
    name="barrel_hinge",
    title=_("Bolzenscharnier"),
    group="mechanics",
    params=BarrelHingeParams,
    # **Der erste Baustein, der zwei Körper erklärt** (§24.3, Entscheidung
    # Robert vom 25.08.2026). Er ist der Anlass, aus dem die Frage überhaupt
    # gestellt wurde: Ein Scharnier, das schon beim Drucken beweglich ist,
    # besteht aus zwei Teilen, und der Bereichstest verlangte einen.
    bodies=2,
    features=["hinge"],
    wall=WallRequirement.from_parameter("wall"),
    doc=_(
        "Ein Scharnier, das aus dem Drucker schon beweglich kommt: zwei Laschen "
        "um einen mitgedruckten Bolzen, dazwischen der Druckspalt. Nichts "
        "zusammenzusetzen, nichts einzustecken."
    ),
    caveat=_(
        "Der Spalt entscheidet: Zu eng verschweißt beim Drucken, zu weit "
        "schlackert. Er kommt aus dem kalibrierten Material — wer das Material "
        "wechselt, druckt ein Prüfstück, bevor er zwanzig Scharniere druckt."
    ),
    changes=[BARREL_HINGE_ADDED, BARREL_HINGE_CLEARANCE_FIXED, MATERIAL_OF_TARGET],
)
def barrel_hinge(raw: BaseParams) -> PartResult:
    """Zwei Laschen um einen mitgedruckten Bolzen, Achse parallel zur Fläche.

    **Der Baustein, an dem §24.3 aufgemacht wurde.** Bis zum 25.08.2026
    verlangte der Bereichstest genau einen Körper, und ein print-in-place-
    Scharnier hat zwei — das ging nicht zusammen. Gebaut wurde deshalb erst das
    halbe Scharnier (``hinge_eye``): ein Auge, und wer ein Gelenk wollte, nahm
    zwei davon und einen Passstift. Nützlich, aber nicht dasselbe: Ein
    Bolzenscharnier kommt fertig aus dem Drucker.

    **Die Bauart ist die einfachste, die trägt.** Die linke Lasche trägt den
    Bolzen angeformt; die rechte hat eine Bohrung darum, die um das Spiel
    weiter ist. Getrennt sind sie durch denselben Spalt, axial wie radial —
    zwei Körper, die einander nicht berühren und sich deshalb drehen können.

    Ein Kranz aus drei Augen (außen zwei, innen eines) hielte seitliche Kräfte
    besser aus, braucht aber zwei Spalte statt einem und damit die doppelte
    Genauigkeit vom Drucker. Das ist der nächste Schritt, wenn dieser trägt.

    **Das Spiel ist der ganze Baustein.** Es kommt aus dem Materialprofil
    (``play`` bleibt auf null, ``insert_part`` füllt es) — eine Zahl im Code
    wäre für PLA richtig und für TPU falsch, und das Scharnier ist genau der
    Fall, in dem das den Unterschied zwischen beweglich und verschweißt macht.
    """
    params = cast(BarrelHingeParams, raw)

    gap = max(params.play, BOOLEAN_OVERLAP)
    # Die rechte Bohrung ist radial um ``gap`` weiter als der Bolzen. Der
    # Außendurchmesser muss deshalb erst **danach** die zugesagte Wand tragen;
    # andernfalls wird aus ``wall`` bei großem Spiel null oder ein Restkörper.
    outer = params.pin + 2.0 * (gap + params.wall)
    # Die Lücke liegt in der Mitte: Jede Lasche bekommt die Hälfte der Breite
    # abzüglich des halben Spalts.
    half = (params.width - gap) / 2.0

    def lying(diameter: float, length: float, x: float) -> Form:
        """Ein Zylinder mit der Achse in X — die Drehachse des Scharniers."""
        upright = shapes.cylinder(diameter, length)
        centred = shapes.moved(upright, (0.0, 0.0, -length / 2.0))
        turned = shapes.turned(centred, 90.0, (0.0, 1.0, 0.0))
        return shapes.moved(turned, (x, params.reach, outer / 2.0))

    def lug(length: float, x: float) -> Form:
        """Die Lasche unter einem Auge, bis in dessen Mitte hinein.

        Bis in die Mitte, nicht bis an den Rand: Zwei Körper, die sich nur
        berühren, sind der Fall, an dem eine Boolesche Operation bricht (§39).
        """
        body = shapes.box(length, params.reach, outer)
        return shapes.moved(body, (x, params.reach / 2.0, 0.0))

    # Links: Lasche und Auge, dazu der Bolzen über die volle Breite.
    left = union(
        lying(outer, half, -(params.width - half) / 2.0), lug(half, -(params.width - half) / 2.0)
    )
    left = union(left, lying(params.pin, params.width, 0.0))

    # Rechts: Lasche und Auge, aus dem der Bolzen samt Spiel wieder heraus muss.
    right = union(
        lying(outer, half, (params.width - half) / 2.0), lug(half, (params.width - half) / 2.0)
    )
    right = subtract(
        right, lying(params.pin + 2.0 * gap, params.width + 2.0 * BOOLEAN_OVERLAP, 0.0)
    )

    # Zwei Körper, die einander nicht berühren — erklärt (``bodies=2``), also
    # ein Verbund und keine Vereinigung, die nichts vereinigt.
    return result(
        compound(left, right),
        # Die Drehachse als Bohrung benannt, wie beim Scharnierauge: Wer etwas
        # daran ausrichtet, meint die Achse und nicht die Lasche.
        bore(
            "hinge_1",
            params.pin,
            (0.0, params.reach, outer / 2.0),
            depth=params.width,
            axis=(1.0, 0.0, 0.0),
            through=True,
        ),
    )
