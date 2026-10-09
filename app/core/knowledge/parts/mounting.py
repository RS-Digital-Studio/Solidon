"""Bausteine, die etwas an etwas anderem halten (Bauplan §24.1).

Hier liegen: die Magnettasche, die Wandhalterung, die Lasche mit Loch, die
Rohrschelle, die Schlüsselloch-Aufhängung, der Lochwand-Einhänger und der
Standfuß. Manche sind Formen zum Abziehen, andere Körper zum Hinzufügen, und
der Standfuß ist beides je nach Wahl — darum sagt die Deklaration es, und
``insert_part`` muss nicht raten.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, cast

from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import bore, compound, face, result, subtract, union

# **Die Federarmregeln stehen bei der Mechanik, und dort bleiben sie.** Ein
# Federarm ist zehnmal so lang wie dick und mindestens zwei Außenwände stark —
# dieselbe Frage wie bei der Schnappverbindung, also dieselbe Zahl. Sie hier
# ein zweites Mal hinzuschreiben hieße, sie beim nächsten Nachbessern an einer
# Stelle zu ändern und an der anderen nicht.
from app.core.knowledge.parts.mechanics import SNAP_LEAD_ANGLE, SNAP_MIN_ARM, SNAP_RATIO
from app.core.knowledge.parts.registry import (
    FACE_GIVES_DIRECTION,
    FACE_ON_THE_BODY,
    MATERIAL_OF_TARGET,
    MOUTH_AT_ORIGIN,
    FeatureRequirement,
    PartChange,
    RetainingLip,
    WallRequirement,
    register_part,
)
from app.core.knowledge.parts.shapes import Form
from app.core.registry import GRIP_TITLE, op_params, param, play_param
from app.core.registry.params import ZERO_AS_CHOSEN, ZERO_AUTOMATIC, ZERO_NONE
from app.core.types import BaseParams, PartResult, Vec3
from app.core.units import is_greater
from app.i18n import TranslatableText, _

KEYHOLE_RETAINS_HEAD = PartChange(
    version="15",
    date="2026-09-06",
    reason="Der Kopfkanal war zur Mündung offen und konnte den Schraubenkopf nicht zurückhalten.",
    effect=_(
        "Über dem Haltekanal bleibt jetzt eine Lippe, die den Kopf hält, offen ist nur der "
        "Einstieg."
    ),
)

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)

WALL_MOUNT_KEEPS_HOLE_WALLS = PartChange(
    version="13",
    date="2026-08-31",
    reason=(
        "Kleine Rückplatten konnten große oder dicht gesetzte Schraubenlöcher "
        "nicht als zusammenhängenden druckbaren Körper halten."
    ),
    effect=_(
        "Die Schraubenlöcher gehen jetzt durch die Platte und liegen auf halber Höhe, die Platte "
        "wächst bei Bedarf mit."
    ),
)

_MAGNETS = standards.magnet_sizes()
_SCREWS = standards.screw_sizes()

#: Die Schrauben des Wandhalters: jede Größe der Normteiltabelle ab M2 (eine
#: M1.6 trägt an keiner Wand), bis M64. Bis RM-578 endete die Reihe bei M27,
#: weil 512 Ecken für sechzehn Größen reichten; die Grenze der mitgelieferten
#: Bibliothek richtet sich jetzt nach der Rechenzeit ihres Nachweises
#: (``range_check.LIBRARY_MAX_CORNERS``). Die Platte wächst mit der Schraube.
WALL_SCREWS: Final = tuple(size for size in _SCREWS if standards.screw(size).nominal >= 2.0)


SLOT_RUNS_DOWNWARD = PartChange(
    version="5",
    date="2026-08-25",
    reason=(
        "Der Schlitz lag quer zur Fallrichtung. ``shapes.slot`` baut seine Länge "
        "immer in X; der Code verschob danach in Y und meinte, er habe gedreht."
    ),
    effect=_(
        "Der Schlitz läuft jetzt in -Y statt in X, an der Wand also nach unten statt waagerecht."
    ),
)


LIP_GRIPS_THE_MAGNET = PartChange(
    version="5",
    date="2026-08-25",
    reason=(
        "Die Haltelippe wurde der Tasche hinzugefügt statt von ihr abgezogen — "
        "ein Volumen, das man vereinigt, kann nur weiten, nicht verengen."
    ),
    effect=_(
        "Die Haltelippe macht die Mündung jetzt enger als den Magneten, bei 6 mm sind es 5,91 "
        "statt 6,00 mm."
    ),
)

LIP_GRIP_FROM_PROFILE = PartChange(
    version="10",
    date="2026-08-26",
    reason=(
        "Das Übermaß der Haltelippe stand als feste 0,1 im Baustein. Für "
        "Übermaße führt das Materialprofil den Wert ``press`` — er wird "
        "kalibriert (§28.3), und eine Zahl daneben untergräbt genau diese "
        "Kalibrierung (Regel 7). Die Tasche las ihr Spiel längst aus dem Profil "
        "und ihr Übermaß nicht."
    ),
    effect=_(
        "Neu ist das Feld „Übermaß“, bei null kommt es aus dem Materialprofil, ohne Profil "
        "bleibt es 0,1 mm."
    ),
)

HEAD_PLAY_FROM_PROFILE = PartChange(
    version="6",
    date="2026-08-25",
    reason=(
        "Das Kopfspiel stand als feste 0,6 im Baustein und kam damit nie aus dem "
        "Materialprofil (Regel 7, §28.3)."
    ),
    effect=_(
        "Mit einem kalibrierten Profil wird das runde Ende enger oder weiter, statt "
        "bei 0,6 mm zu bleiben."
    ),
)

HEAD_PLAY_ADDS_INSTEAD_OF_REPLACING = PartChange(
    version="7",
    date="2026-08-25",
    reason=(
        "Version 6 ersetzte das Kopfspiel durch das Profilspiel, statt es "
        "dazuzurechnen — und ``ops.insert`` füllt das Spiel bei **jedem** Profil "
        "ein, nicht erst bei einem kalibrierten."
    ),
    effect=_(
        "Das runde Ende wird wieder weit genug für den Kopf, bei M4 mit PETG 7,85 statt 7,25 mm."
    ),
)

POCKET_REACHES_PAST_THE_FACE = PartChange(
    version="2",
    date="2026-08-25",
    reason=(
        "Die Fußtasche endete als einziger abziehender Baustein exakt auf der "
        "angeklickten Fläche statt einen Überlappungswert darüber hinaus (§39)."
    ),
    effect=_(
        "Kein Maß ändert sich, die Tasche reicht nur ein Stück über die Fläche hinaus, damit das "
        "Abziehen gelingt."
    ),
)

#: Wie weit die Haltelippe einer Magnettasche den Magneten unterschreitet,
#: **solange kein Profil den Baustein erreicht**.
#:
#: Hier stand das Übermaß als feste Zahl, mit der Begründung, ein Übermaß sei
#: keine Toleranz aus dem Profil — und das ist die Begründung, die Regel 7
#: gerade nicht gelten lässt: Für Übermaße führt das Materialprofil ``press``
#: (``profiles.py``, ``resolve_tolerance(value, "press", profile)``), und es ist
#: dort negativ, weil ein Pressmaß der Gegenfall zum Spiel ist. PLA und PETG
#: nennen -0,05, ABS und ASA -0,06, TPU -0,10. Ein Zehntel für alle vier
#: untergrub dieselbe Kalibrierung (§28.3), die der Baustein beim Spiel längst
#: liest: Wer sein Material misst, bekam das gemessene Spiel und ein geratenes
#: Übermaß.
#:
#: Der Weg ist derselbe wie beim Spiel — der Parameter steht auf null, und der
#: Bausteinaufruf füllt ihn aus dem Profil ein. Diese Zahl bleibt als Rückfall
#: für den Fall ohne Profil: Null hieße dort keine Lippe, und das ist die eine
#: Antwort, die der Kunde nicht gemeint haben kann.
MAGNET_LIP_GRIP = 0.1

#: Wie hoch die Haltelippe ist — der Weg, über den der Magnet sich
#: hineindrücken lässt. Kurz genug, dass sie nachgibt statt zu sperren.
MAGNET_LIP_HEIGHT = 0.4


@op_params
class MagnetPocketParams(BaseParams):
    size: str = param(
        title=_("Magnet"),
        default="8x3",
        choices=_MAGNETS,
        doc=_("Durchmesser mal Höhe des Rundmagneten, wie er im Handel heißt."),
    )
    diameter: float = param(
        title=_("Eigener Durchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        placement="advanced",
        doc=_(
            "Nur ausfüllen, wenn die passende Größe nicht in der Auswahl steht. "
            "Null verwendet die ausgewählte Größe."
        ),
        zero_text=ZERO_AS_CHOSEN,
    )
    height: float = param(
        title=_("Eigene Höhe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=30.0,
        placement="advanced",
        doc=_(
            "Nur ausfüllen, wenn die passende Größe nicht in der Auswahl steht. "
            "Null verwendet die ausgewählte Größe."
        ),
        zero_text=ZERO_AS_CHOSEN,
    )
    play: float = play_param()
    cover: float = param(
        title=_("Deckschicht"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        doc=_("Material über dem Magneten. Null lässt die Tasche offen."),
        zero_text=ZERO_NONE,
    )
    press_lip: bool = param(
        title=_("Haltelippe"),
        default=True,
        placement="advanced",
        doc=_("Ein Zehntel Verengung am Rand, damit der Magnet nicht herausfällt."),
    )
    grip: float = play_param(title=GRIP_TITLE)


@register_part(
    name="magnet_pocket",
    title=_("Magnettasche"),
    group="mounting",
    params=MagnetPocketParams,
    subtractive=True,
    features=["pocket"],
    wall=WallRequirement.not_applicable("Der Baustein ist ein abtragender Werkzeugkörper."),
    doc=_(
        "Tasche für einen Rundmagneten, auf Wunsch mit Deckschicht zum Überdrucken "
        "und einer Haltelippe am Rand."
    ),
    changes=[
        FIRST_RELEASE,
        MOUTH_AT_ORIGIN,
        FACE_GIVES_DIRECTION,
        LIP_GRIPS_THE_MAGNET,
        LIP_GRIP_FROM_PROFILE,
        MATERIAL_OF_TARGET,
    ],
    retaining_lip=lambda raw: magnet_lip(raw),
)
def magnet_pocket(raw: BaseParams) -> PartResult:
    params = cast(MagnetPocketParams, raw)
    entry = standards.magnet(params.size)
    magnet_diameter = params.diameter or entry.diameter
    magnet_height = params.height or entry.height
    diameter = magnet_diameter + params.play

    # Der Ursprung ist die Mündung, die Tasche liegt darunter (§24.1). Eine
    # Decke schiebt sie tiefer hinein, statt sie anzuheben: über der Mündung
    # ist die Luft, und dort trägt nichts ab.
    mouth = -params.cover
    # **Die Lippe verengt die Tasche, also fehlt sie ihr.** Sie stand hier als
    # eigener Kegel neben dem Taschenzylinder und wurde mit ihm vereinigt — und
    # ein Volumen, das man einem anderen hinzufügt, kann es nur weiter machen,
    # nie enger. Das Werkzeug war über die ganze Höhe zylindrisch, die Lippe
    # verschwand darin, und die Tasche hielt in keiner Einstellung: nicht bei
    # play = 0, nicht bei kalibriertem Material. Gemessen an einem
    # 6-mm-Magneten war die Öffnung 6,00 mm weit, wo 5,90 hätten stehen sollen.
    #
    # Jetzt endet der Zylinder unter der Lippe, und die letzten Zehntel
    # übernimmt der Kegel. Sein enges Ende ist der Magnet **minus** Übermaß —
    # nicht die aufgeweitete Tasche, in der das Profilspiel schon steckt.
    # Das Übermaß kommt aus dem Materialprofil, nicht aus einer Zahl im Code
    # (Regel 7): Null im Parameter heißt „aus dem Profil", genau wie beim Spiel
    # eine Zeile darüber. Wo kein Profil bis hierher kommt, bleibt
    # ``MAGNET_LIP_GRIP`` der Rückfall — null hieße dort keine Lippe.
    grip, lip_height = _lip_of(params)
    if grip and not is_greater(magnet_diameter, grip):
        raise ValidationError(
            field="diameter",
            detail=_(
                "Der eigene Durchmesser muss größer als das Übermaß der "
                "Haltelippe sein. Einen größeren Durchmesser eintragen oder "
                "die Haltelippe ausschalten."
            ),
            value=magnet_diameter,
            constraint="minimum",
            values={"minimum": grip},
        )
    narrow = magnet_diameter - grip

    pocket = shapes.cylinder(diameter, magnet_height - lip_height)
    parts = [shapes.moved(pocket, (0.0, 0.0, mouth - magnet_height))]

    if lip_height:
        parts.append(
            shapes.moved(shapes.cone(diameter, narrow, lip_height), (0.0, 0.0, mouth - lip_height))
        )

    if params.cover <= 0.0:
        # Offene Tasche: ein Haar über die Fläche hinausreichen, damit der
        # Schnitt sauber wird (§39) — und zwar so eng wie die Lippe darunter,
        # sonst risse dieser Zylinder die Verengung wieder auf.
        parts.append(
            shapes.moved(
                shapes.cylinder(narrow if lip_height else diameter, BOOLEAN_OVERLAP),
                (0.0, 0.0, mouth),
            )
        )

    body = union(*parts)
    return result(
        body,
        bore(
            "pocket_1",
            diameter,
            (0.0, 0.0, mouth - magnet_height / 2.0),
            depth=magnet_height,
        ),
    )


def _lip_of(params: MagnetPocketParams) -> tuple[float, float]:
    """Übermaß und Höhe der Haltelippe, beide null ohne Lippe."""
    grip = (params.grip or MAGNET_LIP_GRIP) if (params.press_lip and params.cover <= 0.0) else 0.0
    # Bei sehr flachen Sondergrößen darf die feste Lippenhöhe nicht den
    # Taschenboden umkehren. Mindestens die halbe Tiefe bleibt zylindrisch;
    # Standardmagnete behalten unverändert die volle Lippenhöhe.
    magnet_height = params.height or standards.magnet(params.size).height
    return grip, (min(MAGNET_LIP_HEIGHT, magnet_height / 2.0) if grip else 0.0)


#: Wie viele Punkte den Taschenrand für die Frage nach der schrägen Lippe
#: beschreiben — alle 5°; die Frage ist eine Neigung, keine Facettenkontur.
_LIP_RIM_POINTS = 72


def _circle(
    radius: float, centre: tuple[float, float] = (0.0, 0.0)
) -> tuple[tuple[float, float], ...]:
    """Ein Kreis als Umriss einer Haltelippe, ``_LIP_RIM_POINTS`` Punkte."""
    turns = [2.0 * math.pi * index / _LIP_RIM_POINTS for index in range(_LIP_RIM_POINTS)]
    return tuple(
        (centre[0] + radius * math.cos(turn), centre[1] + radius * math.sin(turn)) for turn in turns
    )


def magnet_lip(raw: BaseParams) -> RetainingLip | None:
    """Die Haltelippe der Magnettasche am Taschenrand (RM-277).

    Die Lippe reicht von der Mündung ``lip_height`` tief und ist am
    Taschenrand (Halbmesser ``R``, Magnet plus Spiel) am niedrigsten. Steht die
    Richtung schräg zur Fläche, liegt die Fläche dort um bis zu
    ``R · tan(Neigung)`` unter der Mündung; ab ``tan(Neigung) > lip_height / R``
    fehlt die Lippe auf einem Teil des Umfangs — bei 8x3 in PETG ab 5,54°.
    """
    params = cast(MagnetPocketParams, raw)
    _grip, lip_height = _lip_of(params)
    if not lip_height:
        return None
    radius = ((params.diameter or standards.magnet(params.size).diameter) + params.play) / 2.0
    return RetainingLip(name=_("Die Haltelippe"), height=lip_height, rim=_circle(radius))


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
        placement="advanced",
    )
    size: str = param(
        title=_("Schraube"),
        default="M4",
        choices=WALL_SCREWS,
        doc=_("Wofür die Löcher sind. Es sind Durchgangslöcher aus der Normteiltabelle."),
        placement="advanced",
    )
    holes: int = param(
        title=_("Löcher"),
        default=2,
        minimum=1,
        maximum=6,
        doc=_("Über die Breite verteilt."),
        placement="advanced",
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
    standalone=True,
    title=_("Wandhalter"),
    group="mounting",
    params=WallMountParams,
    features=["plate", "bore"],
    wall=WallRequirement.from_parameter("thickness"),
    doc=_(
        "Rückplatte mit Schraubenlöchern und nach vorn stehender Auflage. "
        "Die Löcher sind Durchgangslöcher aus der Normteiltabelle."
    ),
    changes=[FIRST_RELEASE, FACE_GIVES_DIRECTION, WALL_MOUNT_KEEPS_HOLE_WALLS, FACE_ON_THE_BODY],
)
def wall_mount(raw: BaseParams) -> PartResult:
    params = cast(WallMountParams, raw)
    screw = standards.screw(params.size)

    # Die Rückplatte wächst nur an unmöglichen Kombinationen: Ein Abstand von
    # anderthalb Lochdurchmessern lässt zwischen zwei Bohrungen einen halben
    # Durchmesser Material. Auch am Rand bleibt so mindestens ein Durchmesser.
    # Das skaliert mit dem gewählten Normteil und erfindet keine Profiltoleranz.
    hole_pitch = screw.clearance * 1.5
    width = max(params.width, hole_pitch * (params.holes + 1))
    height = max(params.height, screw.clearance * 2.0)

    plate = shapes.box(width, params.thickness, height)
    body = plate
    if params.lip > 0.0:
        join_depth = min(params.thickness / 2.0, params.lip)
        shelf = shapes.box(width, params.lip + join_depth, params.thickness)
        body = union(
            body,
            shapes.moved(
                shelf,
                (0.0, params.thickness / 2.0 + params.lip / 2.0 - join_depth / 2.0, 0.0),
            ),
        )

    # Die Rückseite der Platte, die an die Wand kommt — die Auflage steht nach
    # +Y, also liegt sie bei -Y und schaut dorthin.
    features = [
        face(
            "plate_1",
            width * height,
            (0.0, -params.thickness / 2.0, height / 2.0),
            (0.0, -1.0, 0.0),
        )
    ]
    spacing = width / (params.holes + 1)
    for index in range(1, params.holes + 1):
        x = -width / 2.0 + spacing * index
        z = height / 2.0
        hole = shapes.cylinder(screw.clearance, params.thickness + 2.0 * BOOLEAN_OVERLAP)
        hole = shapes.turned(hole, -90.0, (1.0, 0.0, 0.0))
        hole = shapes.moved(hole, (x, -params.thickness / 2.0 - BOOLEAN_OVERLAP, z))
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


LUG_ADDED = PartChange(
    version="1",
    date="2026-10-02",
    reason="Lasche mit Loch — im Nachbau entstand jede Lasche aus Quader, Verschieben und "
    "Bohrung (RM-398).",
)

#: Die Schrauben der Lasche: ab M3 jede Größe der Normteiltabelle (Vorgabe
#: Robert, RM-398; seit dem 06.10.2026 bis M64), soweit die Tabelle eine
#: Unterlegscheibe dazu führt — aus deren Außenmaß folgen Breite und Länge, wo
#: keine eingetragen sind.
_LUG_SCREWS: Final = tuple(
    size
    for size in _SCREWS
    if standards.screw(size).nominal >= 3.0 and size in standards.washer_sizes()
)

#: Die breiteste Lasche trägt die größte Scheibe (M64: 115 mm). Eine feste 100
#: ließ ein eingetragenes Maß die eigene Vorgabe der großen Größen nicht
#: erreichen (Review RM-532 Runde 2, N6).
_WIDEST_LUG: Final = max(standards.washer(size).outer for size in _LUG_SCREWS)

LUG_END_FOLLOWS_ITS_ROUNDING = PartChange(
    version="24",
    date="2026-10-06",
    reason=(
        "Das runde Ende hatte immer 48 Ecken; ab 42,8 mm Breite lagen seine Sehnen mehr "
        "als MAX_FACET_SAG innen, bei der Lasche für M64 0,13 mm (RM-532)."
    ),
    effect=_(
        "Laschen über 42,8 mm Breite haben ein feiner gerundetes Ende und werden bis zu "
        "0,1 mm länger."
    ),
)

LUG_TOO_NARROW = _(
    "Die Lasche ist schmaler als der Schraubenkopf. Eine größere Breite oder eine "
    "kleinere Schraube wählen."
)
LUG_TOO_SHORT = _(
    "Die Lasche ist zu kurz: Der Schraubenkopf stieße an die Fläche. Eine größere Länge "
    "oder eine kleinere Schraube wählen."
)


@op_params
class LugParams(BaseParams):
    size: str = param(
        title=_("Schraube"),
        default="M4",
        choices=_LUG_SCREWS,
        doc=_("Wofür das Loch ist. Es ist das Durchgangsloch aus der Normteiltabelle."),
    )
    width: float = param(
        title=_("Breite"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=_WIDEST_LUG,
        doc=_(
            "Quer zur Lasche gemessen. Null heißt: so breit wie die Unterlegscheibe der Schraube."
        ),
        placement="advanced",
        zero_text=ZERO_AUTOMATIC,
    )
    length: float = param(
        title=_("Länge"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=200.0,
        doc=_(
            "Wie weit die Lasche von der Fläche absteht, bis zum Scheitel des runden Endes. "
            "Null heißt: so lang, dass die Unterlegscheibe neben der Fläche Platz hat."
        ),
        placement="advanced",
        zero_text=ZERO_AUTOMATIC,
    )
    thickness: float = param(
        title=_("Dicke"),
        default=4.0,
        unit="mm",
        minimum=1.0,
        maximum=20.0,
        doc=_("Materialstärke der Lasche, in Richtung des Lochs gemessen."),
    )


def _lug_size(params: LugParams) -> tuple[float, float, float]:
    """Breite, Länge und Abstand der Lochmitte von der Fläche.

    Eine Null nimmt das Maß der Unterlegscheibe (ISO 7089) aus der
    Normteiltabelle: so breit wie sie und so lang, dass sie neben der Fläche
    Platz hat. Das Loch sitzt immer in der Mitte des runden Endes — eine Maßreihe
    je Schraube statt eines Einzelmaßes (Vorgabe Robert, RM-398).
    """
    washer = standards.washer(params.size).outer
    width = params.width or washer
    length = params.length or (width + washer) / 2.0
    return width, length, length - width / 2.0


def _lug_reason(params: LugParams) -> TranslatableText | None:
    """Die erklärte Bedingung: Der Schraubenkopf liegt auf der Lasche und neben der Fläche.

    Gemessen am Zylinderkopf aus der Tabelle (ISO 4762) — eine schmalere Lasche
    trüge ihn nicht, eine kürzere ließe ihn an die Fläche stoßen, an der sie
    ansetzt. Der Bereichstest fährt solche Ecken als erklärte Ausschlüsse.
    """
    head = standards.screw(params.size).head
    width, _length, reach = _lug_size(params)
    if is_greater(head, width):
        return LUG_TOO_NARROW
    if is_greater(head / 2.0, reach):
        return LUG_TOO_SHORT
    return None


@register_part(
    name="lug",
    title=_("Lasche mit Loch"),
    group="mounting",
    params=LugParams,
    keeps_up=True,
    features=["bore", "lug"],
    wall=WallRequirement.from_parameter("thickness"),
    doc=_(
        "Eine flache Lasche mit rundem Ende und einem Durchgangsloch aus der "
        "Normteiltabelle, die von der Fläche absteht. Sie dient zum Anschrauben an Wand, "
        "Gehäuse oder Deckel. Ohne eingetragene Breite und Länge richtet sie sich nach der "
        "Unterlegscheibe der gewählten Schraube."
    ),
    caveat=_(
        "Für Lasten, die die Lasche biegen, denn sie bricht am Ansatz. Dann eine "
        "Versteifungsrippe oder einen Eckwinkel dazusetzen."
    ),
    changes=[LUG_ADDED, LUG_END_FOLLOWS_ITS_ROUNDING],
    feasible=lambda raw: _lug_reason(cast(LugParams, raw)),
)
def lug(raw: BaseParams) -> PartResult:
    """Eine flache Lasche, die senkrecht von der Fläche absteht, mit Loch im runden Ende.

    **Die Unterseite liegt im Ansatzpunkt.** Die Lasche reicht von der Fläche
    nach +Z, ist in X so breit wie eingetragen und in Y so dick — von null nach
    -Y, und -Y ist bei ``keeps_up`` oben. An einer senkrechten Wand liegt sie
    damit flach, und wer den Ansatzpunkt an die Unterkante setzt, bekommt eine
    Lasche bündig mit der Standfläche; das Loch steht senkrecht.

    Gebaut wird sie flach — Länge in X, Breite in Y, Dicke in Z — aus der
    halben Langlochform mit echtem Bogen, und erst danach aufgestellt: Ein
    Quader mit angesetztem Zylinder berührte ihn entlang einer Linie, und
    genau dort scheitert eine Boolesche Operation (§39).
    """
    params = cast(LugParams, raw)
    screw = standards.screw(params.size)
    width, length, reach = _lug_size(params)
    reason = _lug_reason(params)
    if reason is not None:
        narrow = reason is LUG_TOO_NARROW
        raise ValidationError(
            "width" if narrow else "length",
            reason,
            constraint="feasible",
            values={"minimum": screw.head if narrow else (width + screw.head) / 2.0},
        )
    thickness = params.thickness

    eye = shapes.slot(width, 2.0 * reach + width, thickness)
    behind = shapes.moved(
        shapes.box(2.0 * length + 2.0, width + 2.0, thickness + 2.0),
        (-(length + 1.0), 0.0, -1.0),
    )
    hole = shapes.moved(
        shapes.cylinder(screw.clearance, thickness + 2.0 * BOOLEAN_OVERLAP),
        (reach, 0.0, -BOOLEAN_OVERLAP),
    )
    flat = subtract(eye, behind, hole)
    # Länge nach +Z, Breite nach X, Dicke nach Y: erst um X, dann um Y, je
    # eine Vierteldrehung — beide Kerne drehen exakt um 90 Grad.
    standing = shapes.turned(shapes.turned(flat, -90.0, (1.0, 0.0, 0.0)), -90.0, (0.0, 1.0, 0.0))
    body = shapes.moved(standing, (0.0, -thickness, 0.0))

    area = width * reach + math.pi * width**2 / 8.0 - math.pi * screw.clearance**2 / 4.0
    return result(
        body,
        bore(
            "bore_1",
            screw.clearance,
            (0.0, -thickness / 2.0, reach),
            depth=thickness,
            axis=(0.0, 1.0, 0.0),
            through=True,
        ),
        # Die Fläche, auf der Kopf und Scheibe liegen — oben, wo ``keeps_up``
        # -Y hinlegt. Ihre Mitte liegt zwischen Ansatz und Loch auf der Fläche,
        # nicht im Schwerpunkt: Der läge bei der Vorgabe im Loch.
        face(
            "lug_1",
            area,
            (0.0, -thickness, (reach - screw.clearance / 2.0) / 2.0),
            (0.0, -1.0, 0.0),
        ),
    )


PIPE_CLAMP_ADDED = PartChange(
    version="1",
    date="2026-10-02",
    reason="Rohrschelle — im Nachbau der Klemmschelle entstand der Ring aus Zylinder, "
    "Bohrung, Quader und Schlitz (RM-398).",
)

_PIPES: Final = standards.pipe_sizes()

#: Die Klemmschrauben der Rohrschelle: jede Größe ab M3, zu der die
#: Normteiltabelle Mutter und Unterlegscheibe führt, bis M64. Bis RM-578 endete
#: die Reihe bei M6, weil acht Rohre mal vier Schrauben genau 512 Ecken waren.
#: Wo die Scheibe breiter ist als die Schelle, sagt :func:`_clamp_reason` es mit
#: Vorschlag, statt die Größe zu verbieten.
_CLAMP_SCREWS: Final = tuple(
    size
    for size in _SCREWS
    if standards.screw(size).nominal >= 3.0
    and size in standards.nut_sizes()
    and size in standards.washer_sizes()
)

#: Wie weit die Klemmschraube den Ring **über das Spiel hinaus** schließen
#: kann, als Breite des Klemmspalts gemessen.
#:
#: Das Spiel aus dem Materialprofil (Regel 7) steckt schon im Spalt: Der Ring
#: ist um ``play`` weiter als das Rohr, und ``π · play`` Spalt nehmen genau
#: das wieder weg. Dieser Wert ist kein Passungsmaß, sondern der Klemmweg
#: danach: Ein Millimeter Spalt verengt den Ring um ``1 / π`` ≈ 0,32 mm im
#: Durchmesser — so weit darf ein Rohr unter seinem Nennmaß liegen und wird
#: noch gehalten. Er sorgt auch dafür, dass der Spalt ohne Profil (``play``
#: null, Vorschau und SCAD-Datei) nicht verschwindet.
CLAMP_TRAVEL = 1.0

CLAMP_TOO_NARROW = _(
    "Die Schelle ist schmaler als die Unterlegscheibe der Klemmschraube. Eine größere "
    "Breite oder eine kleinere Schraube wählen."
)


@op_params
class PipeClampParams(BaseParams):
    size: str = param(
        title=_("Rohr"),
        default="22",
        choices=_PIPES,
        doc=_("Außendurchmesser des Rohrs in Millimetern, aus der Rohrreihe der Normteiltabelle."),
    )
    diameter: float = param(
        title=_("Eigener Durchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=110.0,
        placement="advanced",
        doc=_(
            "Nur ausfüllen, wenn die passende Größe nicht in der Auswahl steht. "
            "Null verwendet die ausgewählte Größe."
        ),
        zero_text=ZERO_AS_CHOSEN,
    )
    # Bis 120 mm, damit die Scheibe der größten Klemmschraube (M64, 115 mm) ganz
    # aufliegt: Jede angebotene Schraube ist baubar (RM-578); vorher endete die
    # Breite bei 80 mm, und ab M45 wäre der Vorschlag „größere Breite“ leer gewesen.
    width: float = param(
        title=_("Breite"),
        default=15.0,
        unit="mm",
        minimum=7.0,
        maximum=120.0,
        doc=_("Wie breit die Schelle ist, längs des Rohrs gemessen."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=3.0,
        unit="mm",
        minimum=1.5,
        maximum=10.0,
        doc=_("Dicke von Ring, Fuß und Klemmohren."),
        placement="advanced",
    )
    screw_size: str = param(
        title=_("Klemmschraube"),
        default="M4",
        choices=_CLAMP_SCREWS,
        doc=_(
            "Die Schraube quer durch beide Klemmohren, mit Mutter und zwei Unterlegscheiben "
            "aus der Normteiltabelle."
        ),
    )
    play: float = play_param()


def _clamp_seat(screw_size: str) -> float:
    """Wie viel Fläche Kopf, Scheibe und Mutter an einem Klemmohr brauchen.

    Das größte der drei Maße aus der Normteiltabelle — Zylinderkopf,
    Unterlegscheibe (ISO 7089) und Mutter über Eck. Das Ohr ist so hoch und
    die Schelle mindestens so breit, damit jedes davon ganz aufliegt.
    """
    nut = standards.nut(screw_size)
    return max(
        standards.washer(screw_size).outer,
        standards.screw(screw_size).head,
        nut.width * 2.0 / math.sqrt(3.0),
    )


def _clamp_reason(params: PipeClampParams) -> TranslatableText | None:
    """Die erklärte Bedingung: Die Unterlegscheibe liegt ganz auf dem Klemmohr."""
    return CLAMP_TOO_NARROW if is_greater(_clamp_seat(params.screw_size), params.width) else None


@register_part(
    name="pipe_clamp",
    play_inside=True,
    title=_("Rohrschelle"),
    group="mounting",
    params=PipeClampParams,
    standalone=True,
    keeps_up=True,
    features=["seat", "bore"],
    wall=WallRequirement.from_parameter("wall"),
    doc=_(
        "Ein Ring um ein Rohr mit zwei Klemmohren und einer Schraube quer durch beide. "
        "Angezogen schließt sie den Spalt, und der Ring klemmt. Rohr aus der Rohrreihe der "
        "Normteiltabelle oder mit eigenem Durchmesser; das Spiel kommt aus dem "
        "Materialprofil."
    ),
    caveat=_(
        "Liegend gedruckt, wenn sie fest klemmen soll, denn die Schichten laufen dann quer durch "
        "den Ring. Die Rohrachse gehört senkrecht."
    ),
    changes=[PIPE_CLAMP_ADDED],
    feasible=lambda raw: _clamp_reason(cast(PipeClampParams, raw)),
)
def pipe_clamp(raw: BaseParams) -> PartResult:
    """Ein geschlitzter Ring auf einem Fuß, oben zwei Klemmohren mit Querschraube.

    **Der Fuß steht auf der Fläche, das Rohr läuft parallel zu ihr.** Die
    Rohrachse liegt in Y, und der Ring steht um eine Wand über der Fläche im
    Fuß, damit sein Umfang die Fläche nicht nur in einer Linie berührt — genau
    dort scheitert eine Boolesche Operation (§39). Mit ``keeps_up`` steht die
    Rohrachse an einer senkrechten Wand senkrecht, wie bei der Klemmschelle aus
    dem Nachbau.

    **Der Spalt ist das Spiel und der Klemmweg** (:data:`CLAMP_TRAVEL`): Die
    Schraube quer durch beide Ohren zieht ihn zu, und der Ring legt sich ums
    Rohr. Ihre Achse liegt über dem Ring, sodass Kopf, Scheibe und Mutter
    nirgends am Ring anstoßen und der Schaft das Rohr nicht berührt.
    """
    params = cast(PipeClampParams, raw)
    seat = _clamp_seat(params.screw_size)
    reason = _clamp_reason(params)
    if reason is not None:
        raise ValidationError("width", reason, constraint="feasible", values={"minimum": seat})
    screw = standards.screw(params.screw_size)
    pipe = params.diameter or standards.pipe(params.size).outer
    wall = params.wall
    width = params.width
    inner = (pipe + params.play) / 2.0
    outer = inner + wall
    centre = outer + wall
    foot = inner + wall / 2.0
    gap = math.pi * params.play + CLAMP_TRAVEL
    ear = gap / 2.0 + wall
    top = centre + outer + seat
    bolt = centre + outer + seat / 2.0

    def lying(diameter: float, length: float, axis: Vec3) -> Form:
        """Ein Zylinder mittig im Ursprung, um eine Vierteldrehung in X oder Y gelegt."""
        upright = shapes.moved(shapes.cylinder(diameter, length), (0.0, 0.0, -length / 2.0))
        return shapes.turned(upright, 90.0, axis)

    body = union(
        shapes.moved(lying(2.0 * outer, width, (1.0, 0.0, 0.0)), (0.0, 0.0, centre)),
        # Der Fuß reicht von der Fläche bis zur Ringmitte und endet seitlich in
        # der Ringwand — kein Berühren in einer Linie, keine Stufe.
        shapes.box(2.0 * foot, width, centre),
        shapes.moved(shapes.box(2.0 * ear, width, top - centre), (0.0, 0.0, centre)),
    )
    body = subtract(
        body,
        shapes.moved(
            lying(2.0 * inner, width + 2.0 * BOOLEAN_OVERLAP, (1.0, 0.0, 0.0)), (0.0, 0.0, centre)
        ),
        shapes.moved(
            shapes.box(gap, width + 2.0 * BOOLEAN_OVERLAP, top - centre + BOOLEAN_OVERLAP),
            (0.0, 0.0, centre),
        ),
        shapes.moved(
            lying(screw.clearance, 2.0 * ear + 2.0 * BOOLEAN_OVERLAP, (0.0, 1.0, 0.0)),
            (0.0, 0.0, bolt),
        ),
    )
    return result(
        body,
        bore(
            "seat_1",
            2.0 * inner,
            (0.0, 0.0, centre),
            depth=width,
            axis=(0.0, 1.0, 0.0),
            through=True,
        ),
        bore(
            "bore_1",
            screw.clearance,
            (0.0, 0.0, bolt),
            depth=2.0 * ear,
            axis=(1.0, 0.0, 0.0),
            through=True,
        ),
    )


#: Wie viel Luft der Schraubenkopf im runden Ende eines Schlüssellochs hat,
#: **über** das Spiel des Materialprofils hinaus.
#:
#: Der Kopf soll hindurchfallen, nicht klemmen — das ist der eine Fall, in dem
#: großzügiges Spiel richtig ist. Ein Durchgangsmaß also, kein Passungsmaß, und
#: darum wird das Profilspiel dazugerechnet und nicht dagegen ausgetauscht:
#: ``ops.insert`` füllt ``play`` bei **jedem** Profil aus
#: ``material.clearance``, nicht erst bei einem kalibrierten. Version 6 las
#: ``params.play or HEAD_CLEARANCE``, und damit bekam ein M4-Kopf von 7,00 mm
#: unter PETG eine Öffnung von 7,25 statt 7,60 — gedruckt geht er da nicht mehr
#: hindurch.
HEAD_CLEARANCE = 0.6


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
    play: float = play_param(maximum=2.0)


KEYHOLE_DROP_TOO_SHORT = _(
    "Der Einhängeweg ist zu kurz für eine Rückhaltekante. Den Einhängeweg "
    "vergrößern oder das Spiel verkleinern."
)
KEYHOLE_HEAD_ROOM_TOO_DEEP = _(
    "Die Kopftiefe muss kleiner als die Gesamttiefe sein, damit eine Rückhaltekante bleibt."
)


def _keyhole_minimum_drop(head: float, clearance: float) -> float:
    """Der Einhängeweg, ab dem über dem Kopf noch eine Kante stehen bleibt."""
    return math.sqrt(((head + clearance) / 2.0) ** 2 - (head / 2.0) ** 2)


def _keyhole_without_ledge(params: KeyholeParams) -> TranslatableText | None:
    """Die erklärte Bedingung des Schlüssellochs: eine Rückhaltekante muss übrig bleiben.

    Zwei Maße gegen zwei andere: der Einhängeweg gegen Kopf und Spiel, die
    Kopftiefe gegen die Gesamttiefe. Beides liegt innerhalb der Einzelgrenzen
    und ist trotzdem kein Schlüsselloch — deshalb steht es hier, am Vertrag,
    und der Bereichstest fährt diese Ecken als erklärten Ausschluss.
    """
    screw = standards.screw(params.size)
    if params.drop <= _keyhole_minimum_drop(screw.head, HEAD_CLEARANCE + params.play):
        return KEYHOLE_DROP_TOO_SHORT
    if params.head_room >= params.depth:
        return KEYHOLE_HEAD_ROOM_TOO_DEEP
    return None


@register_part(
    name="keyhole",
    title=_("Schlüsselloch-Aufhängung"),
    group="mounting",
    params=KeyholeParams,
    subtractive=True,
    features=["pocket", "bore"],
    wall=WallRequirement.not_applicable("Der Baustein ist ein abtragender Werkzeugkörper."),
    # Ein Schlüsselloch hat ein Oben: Der Schlitz muss senkrecht stehen, sonst
    # trägt er nicht. Dieselbe Frage wie beim Lochwand-Einhänger — und
    # ``rotation_between`` beantwortet sie an drei von vier Wänden falsch.
    keeps_up=True,
    doc=_(
        "Schlüssellochförmige Aussparung: der Kopf geht durch das runde Ende, "
        "der Schaft hält im Schlitz."
    ),
    changes=[
        FIRST_RELEASE,
        MOUTH_AT_ORIGIN,
        FACE_GIVES_DIRECTION,
        SLOT_RUNS_DOWNWARD,
        HEAD_PLAY_FROM_PROFILE,
        HEAD_PLAY_ADDS_INSTEAD_OF_REPLACING,
        KEYHOLE_RETAINS_HEAD,
    ],
    feasible=lambda raw: _keyhole_without_ledge(cast(KeyholeParams, raw)),
    retaining_lip=lambda raw: keyhole_ledge(raw),
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

    # **Gedreht, nicht nur verschoben.** ``shapes.slot`` legt seine Länge in X,
    # immer. Der Versatz in Y stand hier von Anfang an richtig, die Länge lag
    # trotzdem quer dazu: Gemessen an ``keyhole(drop=8)`` waren es 15,58 mm in X
    # und 7,60 in Y, und 15,58 ist ``head + 0,6 + drop`` — der Schlitz selbst.
    # Waagerecht hält ein Schlüsselloch nicht, die Schraube wandert seitlich
    # heraus, statt sich beim Absinken zu verklemmen.
    def falling(width: float, length: float, height: float) -> Form:
        """Ein Langloch, dessen Länge in -Y läuft — der Weg der Schraube."""
        return shapes.turned(shapes.slot(width, length, height), 90.0)

    # **Das Kopfspiel kam aus einer festen Zahl** (0,6 mm) und damit an der
    # Kalibrierung vorbei: Die Prüfung nach §28.3 überspringt genau die
    # Bausteine ohne ``play``-Feld, dieser Baustein war einer, und ein Kunde,
    # der sein Material eingemessen hat, bekam trotzdem denselben Wert wie
    # jeder andere. Regel 7 sagt es allgemeiner: keine Zahlenkonstante für
    # Toleranzen.
    #
    # **Dazu, nicht dafür.** Version 6 schrieb ``params.play or HEAD_CLEARANCE``
    # und ersetzte damit das Durchgangsmaß durch das Profilspiel — und
    # ``ops.insert`` füllt ``play`` bei jedem Profil ein, nicht erst bei einem
    # kalibrierten. Gemessen an M4 unter PETG: Öffnung 7,25 mm bei 7,00 mm
    # Kopf. Die beiden Zahlen beantworten verschiedene Fragen: „wie viel Luft
    # braucht ein Kopf, der hindurchfallen soll" und „wie viel Maß verliert
    # dieser Drucker in diesem Material". Beides gilt, also wird addiert.
    clearance = HEAD_CLEARANCE + params.play
    minimum_drop = _keyhole_minimum_drop(screw.head, clearance)
    unbuildable = _keyhole_without_ledge(params)
    if unbuildable is KEYHOLE_DROP_TOO_SHORT:
        raise ValidationError(
            "drop",
            unbuildable,
            constraint="feasible",
            values={"minimum": minimum_drop, "drop": params.drop},
        )
    if unbuildable is KEYHOLE_HEAD_ROOM_TOO_DEEP:
        raise ValidationError(
            "head_room",
            unbuildable,
            constraint="feasible",
            values={"depth": params.depth, "head_room": params.head_room},
        )
    # Nur der Einstieg reicht kopfbreit bis zur Mündung. Der Kopfkanal
    # liegt darunter; über seinem Halteende bleibt die Rückhaltekante.
    #
    # **Der Einstieg beginnt über dem Kopfkanal, nicht an dessen Boden.** Das
    # runde Ende des Kanals *ist* der Einstieg — dieselbe Achse, derselbe
    # Durchmesser. Reichten beide bis zum Boden, lagen in der Kopfzone zwei
    # Zylinderwände aufeinander, dazu die Längsseiten des Kanals tangential am
    # Einstieg; bei 60 mm Einhängeweg rundete die Mitte des Kanals um ein
    # Haar neben die Achse, und die Vereinigung hinterließ Dreiecke, die
    # einander an Punkten außerhalb ihrer Kanten berührten. Der Bereichstest
    # meldete an 21 Ecken Selbstdurchdringung — vor und nach RM-206.
    pocket_top = -params.depth + params.head_room
    entrance = shapes.cylinder(screw.head + clearance, -pocket_top + BOOLEAN_OVERLAP)
    entrance = shapes.moved(entrance, (0.0, 0.0, pocket_top))
    pocket = falling(screw.head + clearance, screw.head + clearance + params.drop, params.head_room)
    pocket = shapes.moved(pocket, (0.0, drop, -params.depth))

    # Der Schlitz, in den der Schaft gleitet, ganz hindurch.
    shaft = falling(
        screw.clearance, screw.clearance + params.drop, params.depth + 2.0 * BOOLEAN_OVERLAP
    )
    shaft = shapes.moved(shaft, (0.0, drop, -params.depth - BOOLEAN_OVERLAP))

    body = union(entrance, pocket, shaft)
    return result(
        body,
        bore(
            "pocket_1",
            screw.head + clearance,
            (0.0, 0.0, -params.depth / 2.0),
            depth=params.depth,
        ),
        bore(
            "bore_1",
            screw.clearance,
            (0.0, -params.drop, -params.depth / 2.0),
            depth=params.depth,
            through=True,
        ),
    )


def keyhole_ledge(raw: BaseParams) -> RetainingLip:
    """Die Rückhaltekante über dem eingehängten Kopf (RM-277).

    Sie ist so dick wie Tiefe minus Kopftiefe und muss rund um den Kopf
    stehen, wo er nach dem Absinken sitzt: am Ende des Schlitzes, um den
    Einhängeweg von der Einstiegsöffnung. Schräg zur Fläche gesetzt dreht
    ``keeps_up`` den Schlitz dorthin, wo die Fläche unter der Mündung liegt —
    bei den Vorgaben (M4, 8 mm Einhängeweg, 1,5 mm Kante) fehlt die Kante am
    Kopfrand ab ``atan(1,5 / 11,5)`` = 7,4°.
    """
    params = cast(KeyholeParams, raw)
    head = standards.screw(params.size).head
    return RetainingLip(
        name=_("Die Rückhaltekante"),
        height=params.depth - params.head_room,
        rim=_circle(head / 2.0, (0.0, -params.drop)),
    )


#: Wie viel Rückplatte rings um einen Zapfen steht. Kein abgeleitetes Maß:
#: Die Frage ist, wie viel Material die Platte braucht, um den Zapfen zu
#: tragen — nicht, wie breit der Schlitz ist, in dem er später steckt. Vorher
#: stand hier die Schlitzbreite, und das war dieselbe Zahl aus einer fremden
#: Frage (siehe ``.claude/rules/bausteine.md``).
PLATE_MARGIN = 3.0

PEGBOARD_HOOK_ADDED = PartChange(
    version="1",
    date="2026-08-25",
    reason="Lochwand-Einhänger — die Kundenanfrage, mit der dieses Konzept anfing.",
)

HOOK_HOLDS_WHEN_LIFTED = PartChange(
    version="8",
    date="2026-08-25",
    reason=(
        "Ein einteiliger Einhänger löste sich auf demselben Weg, auf dem er "
        "eingehängt wird — wer etwas vom Halter nimmt, hebt das Teil an und hat "
        "es in der Hand. Er bekommt eine federnde Rastzunge (Entscheidung "
        "Robert, 25.08.2026)."
    ),
    effect=_(
        "Mit „Rastzunge“ wird der Einhänger bei SKÅDIS 15,47 statt 11,25 mm hoch, ausgeschaltet "
        "bleibt er wie vorher."
    ),
)

HOOK_FEATURE_ON_A_REAL_FACE = PartChange(
    version="7",
    date="2026-08-25",
    reason=(
        "Das Merkmal ``hook_N`` lag mitten im Material: auf der Höhe der Nase, "
        "die den Querschnitt dort ausfüllt (gemessen zu 99 % innen)."
    ),
    effect=_(
        "Das Merkmal liegt jetzt auf der Rückseite der Nase, daran angesetzte Passungen oder "
        "Schritte finden es dort."
    ),
)

HOOK_BODIES_JOIN_WITH_VOLUME = PartChange(
    version="13",
    date="2026-08-31",
    reason=(
        "Zapfen und Nase überlappten nur um die Boolesche Rechenschwelle; "
        "Grenzkombinationen hinterließen dadurch sich schneidende Dreiecke."
    ),
    effect=_(
        "Außenmaße, Rastweg und Plattensitz bleiben gleich; Zapfen und Nase "
        "greifen innerhalb des Körpers jetzt über eine tragende Fläche ineinander."
    ),
)

_BOARDS = standards.board_sizes()

#: Zulässige Randdehnung eines gedruckten Federarms beim Einrasten.
#:
#: **Kein Toleranzmaß** — Regel 7 meint das Spiel einer Passung, und das kommt
#: weiter aus dem Materialprofil. Das hier ist eine Werkstoffeigenschaft: PLA
#: hat einen E-Modul um 3 GPa und fließt um 50 MPa, das sind rund 1,7 %
#: Dehnung; die Auslegungstafeln für Schnapphaken rechnen für einen einmaligen
#: Fügevorgang mit 2 %. PLA ist von den gängigen Druckmaterialien das
#: sprödeste, für PETG und ABS ist der Wert also die sichere Seite.
#:
#: Er steht hier und nicht im Profil, weil das Profil Toleranzen und
#: Druckmaße führt und keine Festigkeitswerte. Kommt dort einmal einer dazu,
#: gehört er dorthin.
LATCH_STRAIN: Final = 0.02


@dataclass(frozen=True, slots=True)
class _LatchTongue:
    """Die Maße der federnden Rastzunge — je Frage eine Zahl."""

    thickness: float
    """Stärke des Arms in Biegerichtung (Y). Zwei Außenwände, sonst federt er
    nicht, sondern reißt (``SNAP_MIN_ARM``)."""
    width: float
    """Breite quer dazu (X). Halb so breit wie der Zapfen — mehr passt nicht
    unter die Rundung des Schlitzendes, ohne dass die Ecken anstoßen."""
    gap: float
    """Der Spalt zwischen Zunge und Zapfen: der Weg, den sie ausweichen kann.

    Er ist zugleich der Abstand, den die Zunge unter der Schlitzkuppe hält: Ein
    Schlitz endet halbrund, und eine rechteckige Zunge, deren Oberkante genau
    an der Kuppe läge, stieße mit ihren Ecken an — dieselbe Falle, wegen der
    Zapfen und Nase Langlöcher sind und keine Rechtecke.
    """
    lock: float
    """Wo die Rastschulter sitzt, gemessen von der angeklickten Fläche."""
    run: float
    """Länge der Anlaufschräge, mit der sich die Zunge selbst eindrückt."""
    step: float
    """Wie weit die Schulter über die Zunge hinaussteht — das Rastmaß."""

    @property
    def stack(self) -> float:
        """Was die Zunge über der Zapfenoberkante braucht, mit Schulter."""
        return self.gap + self.thickness + self.step


def _latch_tongue(
    *,
    width: float,
    slot_width: float,
    travel: float,
    through: float,
    lip: float,
    sunk: float,
    system: str,
) -> _LatchTongue:
    """Die Zunge, gerechnet aus dem Körper, in dem der Arm sitzt.

    **Der Weg zurück ist der Weg hinein, und genau das ist das Problem.** Ein
    Einhänger wird eingeführt und abgesenkt; wer ihn anhebt und herauszieht,
    hat ihn in der Hand — bei den Originalhaken des Systems ebenso wie hier.
    Was das verhindert, muss etwas sein, das **hinter** der Platte breiter oder
    höher ist als der Schlitz und beim Einführen ausweicht.

    **Warum die Zunge oben sitzt und nach oben rastet.** Der Schlitz ist höher
    als Zapfen und Nase zusammen; dieser Rest ist der Weg zum Absinken und
    liegt über dem Zapfen. Dort — und nur dort — ist Platz für eine Zunge, die
    mit durch den Schlitz geht. Ihre Rastschulter steht darüber hinaus: Damit
    ist alles hinter der Platte zusammen **höher als der Schlitz**, und zwar in
    jeder Höhe, in der das Teil hängen kann. Angehoben löst sich die Nase, und
    das Teil kommt trotzdem nicht heraus.

    **Wo der Federweg herkommt.** Nicht aus einer Zahl daneben, sondern aus dem
    Arm: Für einen Rechteckquerschnitt ist die Randdehnung an der Wurzel
    ``ε = 3·t·δ/(2·L²)``. Das Rastmaß ``δ`` gleicht neben einer Armstärke auch
    das halbe seitliche Spiel des Zapfens aus — sonst könnte die Schulter am
    oberen Rand des erlaubten Bereichs mit durch die Schlitzrundung wandern.
    Die nötige Länge folgt unmittelbar aus der Formel. Beim kleinsten Rastmaß
    bleibt zusätzlich das seit je verwendete Verhältnis von zehn zu eins
    (``SNAP_RATIO``) die strengere Untergrenze.

    **Und der Arm hat Platz, obwohl der Zapfen zu kurz ist.** Die Durchsicht
    vom 25.08.2026 hat ihn in der *Höhe* des Zapfens gesucht — 7,38 mm bei
    0,25 mm Spiel, und ein Federarm braucht 8,0 — und geschlossen, es gehe
    nicht. In der **Tiefe** sind es Plattendicke plus Nasentiefe, bei SKÅDIS
    8,33 mm, und dorthin läuft der Arm: neben dem Zapfen durch den Schlitz.

    Was er dabei kostet, ist ehrlich zu nennen: Der Einhänger reicht um die
    fehlenden Millimeter weiter hinter die Platte, und angehoben lässt sich das
    Teil ein Stück herausziehen, bis die Schulter an der Plattenrückseite
    anschlägt. Herunterfallen kann es nicht.
    """
    thickness = SNAP_MIN_ARM
    radius = slot_width / 2.0
    # So breit wie möglich, ohne den Federweg unter eine Armstärke zu drücken.
    # Eine halbe Zapfenbreite genügte im Normalfall, glitt beim größten Spiel
    # aber mitsamt Schulter durch die Rundung des Schlitzes. Die Sehne aus dem
    # verbleibenden Kuppenraum ist die breiteste Zunge, die sich weiterhin um
    # ihr vollständiges Rastmaß einfedern lässt.
    head_room_limit = max(0.0, travel - 2.0 * thickness)
    chord_height = min(radius, head_room_limit)
    tongue = min(width, 2.0 * math.sqrt(max(radius**2 - (radius - chord_height) ** 2, 0.0)))
    head_room = radius - math.sqrt(max(radius**2 - (tongue / 2.0) ** 2, 0.0))

    # Der freie Weg über dem Zapfen gehört ganz der Zunge: Kuppenabstand,
    # Zungenstärke, Federweg. Das Rastmaß gleicht zusätzlich das halbe
    # seitliche Spiel aus: In der runden Schlitzkuppe kann der schmalere Zapfen
    # um genau diesen Betrag seitlich ausweichen, ohne dass das nominelle
    # Höhenmaß der Schulter noch sperrt.
    step = thickness + (slot_width - width) / 2.0
    gap = travel - head_room - thickness
    if gap < step:
        raise ValidationError(
            field="latch",
            detail=_(
                "In den Schlitz dieser Lochwand passt neben dem Zapfen keine "
                "federnde Zunge. Ohne sie hält der Einhänger trotzdem — er "
                "löst sich nur, wenn jemand das Teil anhebt."
            ),
            values={"board": system, "room": f"{gap:.2f}", "needed": f"{step:.2f}"},
        )

    run = thickness / math.tan(math.radians(SNAP_LEAD_ANGLE))
    # Zehn zu eins, mindestens; bei größerem Rastmaß wächst der Arm so weit,
    # dass dieselbe zulässige Randdehnung erhalten bleibt. Wo neben dem Zapfen
    # mehr Platz ist, wird er mindestens so lang wie der Zapfen tief ist und
    # die Zunge schließt bündig mit der Nase ab. Die Wurzel ist ein Block von
    # einer Armstärke — mit einer Rückplatte übernimmt die Platte sie, und der
    # Arm wird an ihrer Oberseite frei.
    root = max(sunk + thickness, 0.0)
    strain_arm = math.sqrt(3.0 * thickness * step / (2.0 * LATCH_STRAIN))
    arm = max(SNAP_RATIO * thickness, strain_arm, through + lip - run - root)
    return _LatchTongue(
        thickness=thickness,
        width=tongue,
        gap=gap,
        lock=root + arm,
        run=run,
        step=step,
    )


@op_params
class PegboardHookParams(BaseParams):
    system: str = param(
        title=_("Lochwand"),
        default="skadis",
        choices=_BOARDS,
        doc=_("An welche Platte das Teil kommt. Die Maße stehen in der Tabelle."),
        placement="advanced",
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
    steps: int = param(
        title=_("Rasterschritte"),
        default=1,
        minimum=1,
        maximum=4,
        doc=_(
            "Wie viele Löcher zwischen zwei Haken liegen. Eins heißt: jedes Loch, "
            "zwei heißt jedes zweite. Breite Teile kippen zwischen zwei Haken, die "
            "nur vierzig Millimeter auseinandersitzen — weiter außen tragen sie "
            "ruhiger."
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
    latch: bool = param(
        title=_("Rastzunge"),
        default=True,
        doc=_(
            "Eine federnde Zunge am Zapfen, die hinter der Platte einrastet: Das "
            "Teil bleibt hängen, auch wenn jemand es beim Abnehmen anhebt. Zum "
            "Lösen wird sie durch den Schlitz niedergedrückt. Abgeschaltet ist "
            "der Einhänger die einfache Form, die sich anheben und abnehmen lässt."
        ),
        placement="advanced",
    )
    plate: float = param(
        title=_("Rückplatte"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=10.0,
        doc=_(
            "Null heißt: keine. Das Teil, an dem die Haken sitzen, verbindet sie "
            "schon — eine Platte dazwischen wäre Material, das niemand braucht. "
            "Wer trotzdem eine will, bekommt sie ins Teil eingelassen, nicht aufgesetzt."
        ),
        placement="advanced",
        zero_text=ZERO_NONE,
    )
    play: float = play_param(maximum=1.5)
    lip: float = param(
        title=_("Nasentiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=6.0,
        placement="advanced",
        doc=_(
            "Wie weit die Nase hinter die Lochwand greift. Null heißt: zwei Drittel "
            "der Lochwanddicke."
        ),
        zero_text=ZERO_AUTOMATIC,
    )


@register_part(
    name="pegboard_hook",
    title=_("Lochwand-Einhänger"),
    group="mounting",
    params=PegboardHookParams,
    features=["hook", "latch"],
    wall=WallRequirement.not_applicable(
        "Die 0,8-mm-Federzunge ist absichtlich biegsam; ohne Rückplatte "
        "verbindet joined_by_host die Haken ausdrücklich erst im Wirtsbauteil."
    ),
    feature_requirements=(
        FeatureRequirement("hook"),
        FeatureRequirement("latch", when="latch"),
    ),
    keeps_up=True,
    # Ohne Rückplatte ist jeder Haken ein eigener Körper; verbunden werden sie
    # von dem Teil, an das sie kommen. Mit Rückplatte hängen sie ohnehin
    # zusammen — geprüft wird der Fall, der schwächer ist.
    joined_by_host=True,
    doc=_(
        "Haken für eine Lochwand, direkt am Teil. Von oben in die Schlitze "
        "gesteckt und heruntergezogen — die Nase greift dann hinter die Platte, "
        "und die federnde Zunge rastet ein. Gedruckt wird das Teil liegend: die "
        "Zunge in der Druckebene, damit sie über ihre Schichten federt und nicht "
        "an ihnen aufreißt."
    ),
    caveat=_(
        "Wenn ein Teil oft abgenommen wird, denn die Rastzunge muss dazu durch den Schlitz "
        "gedrückt werden. Dann „Rastzunge“ abschalten."
    ),
    changes=[
        PEGBOARD_HOOK_ADDED,
        HOOK_FEATURE_ON_A_REAL_FACE,
        HOOK_HOLDS_WHEN_LIFTED,
        HOOK_BODIES_JOIN_WITH_VOLUME,
        MATERIAL_OF_TARGET,
    ],
)
def pegboard_hook(raw: BaseParams) -> PartResult:
    """Einhänger im Raster, direkt am Teil — mit federnder Rastzunge.

    **Die Rückplatte ist die Ausnahme, nicht die Vorgabe.** Sie war einmal
    beides: Bedingung, weil zwei Haken im Vierzigerraster zwei Körper sind und
    ein Baustein einer sein muss (§24.3) — und Ballast, weil sie zwei
    Millimeter Material zwischen Träger und Lochwand legte, das niemand
    braucht. Beides zusammen ging nicht auf; seit dem 25.08.2026 hängen die
    Haken am Teil selbst, und das verbindet sie (``joined_by_host``). Wer
    trotzdem eine Platte bestellt, bekommt sie **im** Teil: Ihre Oberseite liegt
    auf null, bündig mit der angeklickten Fläche, und was darunter liegt,
    verschmilzt mit dem Träger.

    **Der Haken greift in einen Schlitz, nicht in ein Loch — und ein Schlitz
    hat runde Enden.** Bei SKÅDIS ist die Öffnung fünf Millimeter breit und
    fünfzehn hoch, mit Halbkreisen oben und unten. Ein Rechteck, das in den
    *Hüllquader* dieser Öffnung passt, passt nicht in die Öffnung: Bei
    4,75 mal 14,75 liegt jede Ecke 0,86 mm außerhalb der Rundung, und erst beim
    größten zulässigen Spiel von 1,5 mm ginge es hinein — dann wackelt der
    Zapfen. Zapfen und Nase sind deshalb selbst Langlöcher (``shapes.slot``),
    wie beim Schlüsselloch nebenan.

    **Und er braucht Weg zum Absinken.** Eingehängt wird in zwei Zügen: Zapfen
    und Nase gemeinsam durch den Schlitz stecken, dann sinken lassen, bis die
    Nase hinter dem Steg unter dem Schlitz liegt. Was der Haken dabei sinkt,
    ist genau das, was der Schlitz höher ist als Zapfen und Nase zusammen.
    Standen die beiden auf der vollen Schlitzhöhe, blieben 0,25 mm Weg, und die
    Nase griff um 0,25 mm hinter die Platte — sie hielt nichts. Die Aufteilung
    lässt deshalb ein Viertel der Höhe frei: halbe Höhe Zapfen, ein Viertel
    Nase, ein Viertel Weg.

    **Und dieses Viertel ist zugleich der Weg, auf dem er sich löst.** Wer
    etwas vom Halter nimmt, hebt das Teil an — genau die Geste, die den Haken
    aushängt. Dagegen sitzt oben auf dem Zapfen eine federnde Zunge, die beim
    Einführen einfedert und hinter der Platte ausrastet: Ihre Rastschulter
    macht alles hinter der Platte höher als der Schlitz, und zwar in jeder
    Höhe, in der das Teil hängen kann. Wie sie bemessen ist, steht bei
    :func:`_latch_tongue`; ``latch`` schaltet sie ab, und dann ist die
    Geometrie dieselbe wie vor dem 25.08.2026.

    **Gedruckt wird liegend, und das ist keine Empfehlung, sondern die
    Bedingung für die Zunge.** Ein Federarm hält, wenn er über seine Schichten
    federt, und reißt, wenn er an ihnen zieht: Die Zunge biegt in Y, also darf
    die Aufbaurichtung nicht in Y liegen. Das Teil liegt dafür auf der Seite —
    die Zapfenbreite (X) ist die Aufbaurichtung, Zunge, Zapfen und Nase liegen
    in der Druckebene. Frei schwebend beginnt dabei nichts: Die Zunge hängt mit
    ihrer Wurzel am Zapfen, und jede ihrer Lagen hat eine darunter.

    **Der Abstand ist ein Vielfaches des Rasters, nicht das Raster.** Ein
    breites Teil an zwei Haken im Vierzigerabstand kippt; dieselben zwei Haken
    im Achtzigerabstand tragen es ruhig. Mehr als das Raster hergibt geht
    nicht — die Löcher stehen, wo sie stehen.

    **Oben und unten sind hier keine Redensart.** Der Zapfen sitzt oben, die
    Nase unten; verkehrt herum fällt das Teil von der Wand. Welche Seite nach
    dem Setzen oben liegt, entscheidet aber nicht dieser Baustein, sondern die
    Drehung an die Fläche — darum ``keeps_up`` im Registereintrag.

    Im eigenen System ist oben **-Y**. Diese Fassung baute zuerst nach +Y, und
    weil ``keeps_up`` zur selben Stunde entstand, wurde daraus für einen
    Nachmittag die Regel für alle — bis das Schlüsselloch daran verkehrt herum
    hing. Die Konvention ist älter als beide Bausteine: ``axis="y"`` legt das
    eigene +Y nach unten, seit es diesen Weg gibt.
    """
    params = cast(PegboardHookParams, raw)
    board = standards.board(params.system)

    width = board.slot_width - params.play
    lip = params.lip or board.thickness * (2.0 / 3.0)

    # Die nutzbare Schlitzhöhe, aufgeteilt in Zapfen, Nase und Weg. Die Nase
    # greift am Ende so weit hinter den Steg, wie der Haken sinken konnte —
    # deshalb sind Nase und Weg gleich groß, ein Viertel jeweils.
    usable = board.slot_height - params.play
    travel = usable / 4.0
    nose = travel
    shank = usable - nose - travel

    # **Ein Rasterschritt war fest, und für breite Teile ist er zu eng.** Zwei
    # Haken im Vierzigerraster halten ein schmales Teil gegen Verdrehen; ein
    # breites kippt zwischen ihnen, weil die Last weit außerhalb der Stützweite
    # hängt. Der Abstand ist deshalb ein **Vielfaches** — jedes Loch, jedes
    # zweite, jedes dritte. Die Lochwand gibt nichts anderes her: Zwischen zwei
    # Schlitzen derselben Höhe liegen vierzig Millimeter, und was dazwischen
    # liegt, ist die versetzte Schar (`stagger`), die eine andere Höhe hat.
    reach = board.pitch * params.steps
    span = reach * (params.count - 1)
    across = 0.0 if params.upright else span
    along = span if params.upright else 0.0

    # Wie weit der Zapfen aus der Fläche herausragt: durch die Lochwand
    # hindurch, plus was die Nase dahinter braucht. Eine Rückplatte zählt nicht
    # mit — sie liegt darunter, im Teil.
    through = board.thickness + params.play
    sunk = -params.plate

    # Die federnde Zunge, wenn sie bestellt ist. Sie wächst nach oben über den
    # Zapfen hinaus; was sie dort braucht, muss die Rückplatte mit abdecken.
    tongue = (
        _latch_tongue(
            width=width,
            slot_width=board.slot_width,
            travel=travel,
            through=through,
            lip=lip,
            sunk=sunk,
            system=params.system,
        )
        if params.latch
        else None
    )
    stack = tongue.stack if tongue is not None else 0.0

    # Die Platte trägt die Haken und liegt am Teil an. Ihr Rand ist ein eigenes
    # Maß und keine abgeleitete Zahl: Er beantwortet, wie viel Material um
    # einen Zapfen stehen muss, damit die Platte ihn hält — das hat mit der
    # Breite des Schlitzes nichts zu tun, in dem der Zapfen später steckt.
    # **Ohne Rückplatte, wenn keine bestellt ist.** Sie war eine Auflage von zwei
    # Millimetern zwischen Träger und Haken — Material, das niemand braucht, und
    # zwei Millimeter mehr Abstand zur Lochwand. Bei einer Wandhalterung ist das
    # der Unterschied zwischen „sitzt an der Wand" und „steht davor" (Befund
    # Robert, 25.08.2026, am Bildschirm gesehen; Entscheidung von ihm, sie zur
    # Ausnahme zu machen statt zur Vorgabe).
    #
    # **Die Box wird ausgelassen, nicht auf null gesetzt.** ``shapes.box(…, 0.0)``
    # ist kein Volumen; die Boolesche Rückfallkette fällt darüber bis auf die
    # letzte Stufe („Not all meshes are volumes"), und was dabei einteilig
    # herauskommt, ist eine Notbremse und keine Rechnung. Gar keine Box zu bauen
    # ist etwas anderes als eine mit Höhe null.
    #
    # Wer eine bestellt, bekommt sie **im** Teil: Ihre Oberseite liegt auf z = 0,
    # bündig mit der angeklickten Fläche.
    #
    # Mit Zunge steht der Einhänger nicht mehr mittig zu ihr: Sie sitzt über dem
    # Zapfen, also wächst die Platte nach oben mit und rückt um ihre halbe Höhe
    # nach. Ohne Zunge ist ``stack`` null, und es bleibt die Platte von vorher.
    plate: Form | None = None
    if params.plate > 0.0:
        plate = shapes.box(
            across + width + 2.0 * PLATE_MARGIN,
            along + shank + nose + stack + 2.0 * PLATE_MARGIN,
            params.plate,
        )
        plate = shapes.moved(plate, (0.0, -stack / 2.0, sunk))

    # **Die Platte ist kein Merkmal mehr.** Solange sie auf dem Träger auflag,
    # war ihre Rückseite eine echte Fläche und ein sinnvoller Anhaltspunkt.
    # Eingesenkt liegt sie **im** Material, und dort ist keine Fläche — die
    # Zuordnung fand für sie zwei gleich gute Kandidaten und hielt an
    # („Die Angabe ist nicht eindeutig", an den Seitenwänden mit zwei Haken).
    # Was am Teil anliegt, ist jetzt die angeklickte Fläche selbst; die trägt
    # ihren eigenen Namen und braucht von hier keinen zweiten.
    features = []
    hooks: list[Form] = []
    for index in range(params.count):
        parts: list[Form] = []
        offset = index * reach - span / 2.0
        x = 0.0 if params.upright else offset
        y = offset if params.upright else 0.0
        # Zapfen und Nase als Langloch, in Y gelegt: ``shapes.slot`` baut seine
        # Länge in X, der Schlitz einer Lochwand steht senkrecht.
        # Der Zapfen reicht von der Plattenunterkante bis hinter die Lochwand;
        # was davon im Teil steckt, verschmilzt mit ihm.
        shaft = shapes.turned(shapes.slot(width, shank, through - sunk), 90.0)
        # Der Zapfen sitzt oben, und oben ist **-Y** (``PartSpec.keeps_up``).
        parts.append(shapes.moved(shaft, (x, y - nose / 2.0, sunk)))
        # Die Nase reicht über den Zapfen nach unten hinaus und liegt hinter
        # der Lochwand. Sie beginnt um OVERLAP früher, damit keine Fläche genau
        # auf einer anderen liegt (§39).
        hook_join = min(through / 2.0, lip / 2.0)
        catch = shapes.turned(shapes.slot(width, shank + nose, lip + hook_join), 90.0)
        parts.append(shapes.moved(catch, (x, y, through - hook_join)))
        # **Das Merkmal liegt auf der Rückseite der Nase**, und das ist die
        # einzige Fläche des Hakens, die es dort wirklich gibt. Vorher stand es
        # auf der Höhe der Plattenrückseite mitten im Zapfen — gemessen zu 99 %
        # im Material, mit der Fläche eines Rechtecks, das der Haken gar nicht
        # hat. Derselbe Fehler wie beim Plattenmerkmal dreißig Zeilen höher:
        # ein Punkt im Material ist für die Zuordnung kein Anhaltspunkt.
        features.append(
            face(
                f"hook_{index + 1}",
                _slot_area(width, shank + nose),
                (x, y, through + lip),
                (0.0, 0.0, 1.0),
            )
        )

        if tongue is None:
            hooks.append(union(*parts))
            continue

        # Die Zunge sitzt über der Oberkante des Zapfens, durch den Federweg
        # von ihr getrennt — der Spalt ist der Weg, den sie ausweichen kann.
        crown = y - nose / 2.0 - shank / 2.0
        base = crown - tongue.gap
        crest = base - tongue.thickness

        # Der Arm, von der angeklickten Fläche bis zur Rastschulter. Mit
        # Rückplatte steckt sein vorderes Stück in ihr; frei wird er an ihrer
        # Oberseite, und genau von dort rechnet ``_latch_tongue`` seine Länge.
        arm = shapes.box(tongue.width, tongue.thickness, tongue.lock - sunk)
        parts.append(shapes.moved(arm, (x, crest + tongue.thickness / 2.0, sunk)))

        # Die Wurzel schließt den Spalt am vorderen Ende und ist das, was die
        # Zunge überhaupt zu einem Teil des Hakens macht. Sie greift bis zur
        # Mitte der Zapfenkuppe hinein: Am Scheitel selbst ist das Langloch
        # unendlich schmal, dort wäre die Verbindung eine Kante und kein Körper.
        reachdown = tongue.gap + tongue.thickness + width / 2.0
        root = shapes.box(tongue.width, reachdown, tongue.thickness)
        parts.append(shapes.moved(root, (x, crest + reachdown / 2.0, sunk)))

        # Die Rastschulter mit ihrer Anlaufschräge. Der Keil steht auf der
        # Schulter und läuft nach hinten aus — beim Einführen drückt er die
        # Zunge selbst nieder, herausziehen lässt er sich nicht: Seine
        # Vorderfläche steht quer zum Zug.
        # Um Z gedreht, nicht um X: ``shapes.wedge`` baut seine Tiefe nach +Y
        # und lässt sie nach oben auslaufen; hier soll sie nach **-Y** stehen
        # und nach hinten auslaufen. Eine Drehung um X hätte die Höhe mit
        # umgelegt und die Schräge an das falsche Ende gebracht.
        barb = shapes.turned(
            shapes.wedge(tongue.width, tongue.step + BOOLEAN_OVERLAP, tongue.run), 180.0
        )
        parts.append(shapes.moved(barb, (x, crest + BOOLEAN_OVERLAP, tongue.lock)))
        features.append(
            face(
                f"latch_{index + 1}",
                tongue.width * tongue.step,
                (x, crest - tongue.step / 2.0, tongue.lock),
                (0.0, 0.0, -1.0),
            )
        )

        hooks.append(union(*parts))
    # Mit Platte hängt alles zusammen; ohne sie sind die Haken getrennte Körper, die
    # erst der Träger verbindet (``joined_by_host``) — also ein Verbund, keine
    # Vereinigung, die nichts vereinigt.
    if plate is not None:
        body = union(plate, *hooks)
    else:
        body = hooks[0] if len(hooks) == 1 else compound(*hooks)
    return result(body, *features)


def _slot_area(width: float, length: float) -> float:
    """Die Fläche eines Langlochs: Rechteck plus die beiden Halbkreise."""
    if length <= width:
        return math.pi * (width / 2.0) ** 2
    return width * (length - width) + math.pi * (width / 2.0) ** 2


#: Die Einführschräge an der Mündung einer Fußtasche. Ein fester Wert, weil
#: die Frage „wie fange ich den Fuß beim Einsetzen" eine Fase verlangt und
#: keinen Trichter — sie hängt weder an der Tiefe des Lochs noch am
#: Durchmesser des Fußes.
POCKET_LEAD = 0.6

#: Was vom schmalen Ende eines Fußes mindestens bleibt. Kein Maß aus einer
#: Tabelle, sondern die Grenze, unter der ein Kegelstumpf keine Standfläche
#: mehr hat.
MIN_FOOT_TIP = 1.0

FOOT_ADDED = PartChange(
    version="1",
    date="2026-08-25",
    reason="Standfuß — was auf dem Tisch steht, steht sonst auf seiner Druckkante.",
)

FOOT_PROFILE_FIXED = PartChange(
    version="13",
    date="2026-08-31",
    reason=(
        "Überlappende Körper hinterließen am Fasenansatz des Fußes eine "
        "Ringschulter und durchschnitten sich bei tiefen Taschen."
    ),
    effect=_("Fuß und Tasche entstehen jetzt aus je einem Drehprofil, alle Maße bleiben gleich."),
)


@op_params
class FootParams(BaseParams):
    kind: str = param(
        title=_("Art"),
        default="foot",
        choices=("foot", "pocket"),
        subtractive_on=("pocket",),
        doc=_("Ein gedruckter Fuß, oder die Tasche für einen gekauften aus Gummi."),
    )
    diameter: float = param(
        title=_("Durchmesser"),
        default=10.0,
        unit="mm",
        minimum=3.0,
        maximum=60.0,
        doc=_("Wie breit der Fuß aufsteht. Breiter kippt später."),
    )
    height: float = param(
        title=_("Höhe"),
        default=3.0,
        unit="mm",
        minimum=0.6,
        maximum=30.0,
        doc=_("Wie hoch er trägt — bei der Tasche: wie tief der Gummifuß einsinkt."),
    )
    chamfer: float = param(
        title=_("Fase"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=10.0,
        placement="advanced",
        doc=_(
            "Schräge am Rand. Null heißt beim Fuß: ein Fünftel der Höhe, genug, "
            "damit die erste Schicht nicht als Grat vorsteht. Bei der Tasche ist "
            "es eine Fase zum Einfädeln."
        ),
        zero_text=ZERO_AUTOMATIC,
    )
    play: float = play_param(maximum=2.0)


@register_part(
    name="foot",
    standalone=True,
    title=_("Standfuß"),
    group="mounting",
    params=FootParams,
    features=["foot"],
    wall=WallRequirement(
        parameter="height",
        reason="Die Taschenstellung ist ein abtragender Werkzeugkörper.",
        when="kind",
        equals="pocket",
    ),
    doc=_(
        "Ein Fuß unter einem Gehäuse — gedruckt, oder als Tasche für einen "
        "gekauften aus Gummi. Vier davon halten ein Gerät ruhig und die "
        "Unterseite vom Tisch weg."
    ),
    caveat=_(
        "Für Teile, die flach aufliegen sollen, und zum Verschrauben. Ein Fuß hebt das Teil an "
        "und hat keine Bohrung."
    ),
    changes=[FOOT_ADDED, POCKET_REACHES_PAST_THE_FACE, FOOT_PROFILE_FIXED, MATERIAL_OF_TARGET],
)
def foot(raw: BaseParams) -> PartResult:
    """Ein Kegelstumpf, der auf der schmalen Seite steht — oder ein Loch dafür.

    **Die Fase gehört ans Standende, und dort stand sie zuerst nicht.** Ein
    Zylinder mit scharfer Kante bekommt beim Drucken einen Elefantenfuß: Die
    erste Schicht quetscht breiter als die zweite und steht als Grat vor, und
    darauf wackelt das Gerät. Ein Kegelstumpf, der nach unten schmaler wird,
    hat den Grat dort, wo ohnehin Luft ist. Die erste Fassung setzte ihn ans
    **Anbau**-Ende — genau umgekehrt zu diesem Absatz, den sie schon so
    enthielt. Der Fuß stand mit der scharfen Kante auf dem Tisch, und keine
    Zahl im Test bemerkte es: Volumen, Wasserdichtheit und Hüllquader sind bei
    beiden Lagen gleich.

    Als **Tasche** ist es dieselbe Form, nur umgekehrt gelesen: Das Loch nimmt
    einen gekauften Gummifuß auf, und die Fase wird zur Einführschräge. Der
    Ursprung ist dann die Mündung und die Tiefe geht nach unten ins Material
    (§24.1, ``MOUTH_AT_ORIGIN``).

    **Eine Einführschräge weitet die Mündung, sie verengt nicht den Sitz.** Die
    erste Fassung baute den Schaft der Tasche mit ``narrow`` — dem *schmalen*
    Kegeldurchmesser. Ein Ø-10-Gummifuß fand damit ein Loch von 9,05 mm vor,
    und an der Bereichsecke (Höhe 30, Ø 10) maß der Sitz noch einen einzigen
    Millimeter. Der Schaft hat jetzt den vollen Durchmesser, und die Schräge
    sitzt darüber.
    """
    params = cast(FootParams, raw)
    cutting = params.kind == "pocket"
    wide = params.diameter + (params.play if cutting else 0.0)

    # **Die Fase wird zweimal gekappt, und die zweite Grenze fehlte zuerst.**
    # In der Höhe ist sie klar: Mehr als die halbe, und der Kegel liefe in eine
    # Spitze. In der Breite ist sie es weniger — bis ein Fuß von 30 mm Höhe und
    # 10 mm Durchmesser eine Fase von 6 mm bekam und sein schmales Ende damit
    # **minus zwei** Millimeter maß. Heraus kam ein Körper aus fünf Teilen, und
    # der Bereichstest fährt genau diese Ecke.
    # **Fuß und Tasche fragen hier nicht dasselbe.** Beim Fuß beantwortet die
    # Vorgabe „wie viel Verjüngung trägt den Elefantenfuß ab", und dafür ist
    # ein Anteil der Höhe richtig: Ein hoher Fuß darf stärker zulaufen. Bei der
    # Tasche beantwortet sie „wie fange ich den Gummifuß beim Einsetzen", und
    # das hat mit der Tiefe des Lochs nichts zu tun — dieselbe Formel machte
    # aus einer 30 mm tiefen Tasche für einen Ø-10-Fuß einen Trichter von
    # 19,5 mm Mündung. Eine Einführschräge ist eine Fase, kein Trichter.
    chamfer = params.chamfer or (POCKET_LEAD if cutting else params.height / 5.0)
    chamfer = min(chamfer, params.height / 2.0)
    if not cutting:
        # Nur der Fuß hat ein schmales Ende, das zu klein werden kann.
        chamfer = min(chamfer, (wide - MIN_FOOT_TIP) / 2.0)
    narrow = wide - 2.0 * chamfer

    if cutting:
        # Die Tasche: An der Mündung weitet eine Schräge das Loch, damit der
        # Gummifuß sich fangen lässt; darunter hat der Sitz den vollen
        # Durchmesser, sonst passt der Fuß nicht hinein, für den er gedacht ist.
        body = _pocket_profile(wide, params.height, chamfer)
        marker = bore("foot_1", wide, (0.0, 0.0, -params.height / 2.0), depth=params.height)
    else:
        # Der Fuß: Die Säule steht am Teil, die Verjüngung am Boden — dort
        # quetscht der Elefantenfuß ins Leere.
        body = _foot_profile(wide, narrow, params.height, chamfer)
        # Die Standfläche ist die äußerste, nicht die am Teil: Sie berührt den
        # Tisch, und sie schaut vom Teil weg.
        marker = face(
            "foot_1",
            math.pi * (narrow / 2.0) ** 2,
            (0.0, 0.0, params.height),
            (0.0, 0.0, 1.0),
        )

    return result(body, marker)


def _foot_profile(wide: float, narrow: float, height: float, chamfer: float) -> Form:
    """Säule und Standfase als ein geschlossenes Drehprofil.

    Zwei überlappende Körper hinterließen am Beginn der Fase eine waagerechte
    Ringschulter: Die Säule reichte um ``BOOLEAN_OVERLAP`` in den schon
    schmaler werdenden Kegel. Ein nach innen laufender Strahl traf dort diese
    Schulter statt die Unterseite und maß nur den Säulenrest. Das gemeinsame
    Profil trägt dieselbe Außenkontur ohne innere Fläche.
    """

    outline = [
        (0.0, 0.0),
        (wide / 2.0, 0.0),
        (wide / 2.0, height - chamfer),
        (narrow / 2.0, height),
        (0.0, height),
    ]
    return shapes.revolved(outline)


def _pocket_profile(wide: float, height: float, chamfer: float) -> Form:
    """Sitz und Einführfase als ein geschlossenes abtragendes Drehprofil.

    Es reicht ein Hundertstel über die Mündung hinaus (§39). Das hatte die
    Tasche seit Version 2 (``POCKET_REACHES_PAST_THE_FACE``), und das
    gemeinsame Drehprofil von Version 13 verlor es wieder: Seine Deckfläche lag
    genau in der angeklickten Fläche, bis zum 22.09.2026.
    """

    outline = [
        (0.0, BOOLEAN_OVERLAP),
        (wide / 2.0 + chamfer, BOOLEAN_OVERLAP),
        (wide / 2.0 + chamfer, 0.0),
        (wide / 2.0, -chamfer),
        (wide / 2.0, -height),
        (0.0, -height),
    ][::-1]
    return shapes.revolved(outline)
