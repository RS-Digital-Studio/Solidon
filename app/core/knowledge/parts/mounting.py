"""Bausteine, die etwas an etwas anderem halten (Bauplan §24.1).

Hier liegen: die Magnettasche, die Wandhalterung, die
Schlüsselloch-Aufhängung, der Lochwand-Einhänger und der Standfuß. Manche sind
Formen zum Abziehen, andere Körper zum Hinzufügen, und der Standfuß ist beides
je nach Wahl — darum sagt die Deklaration es, und ``insert_part`` muss nicht
raten.
"""

from __future__ import annotations

import math
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

_MAGNETS = standards.magnet_sizes()
_SCREWS = standards.screw_sizes()


SLOT_RUNS_DOWNWARD = PartChange(
    version="5",
    date="2026-08-25",
    reason=(
        "Der Schlitz lag quer zur Fallrichtung. ``shapes.slot`` baut seine Länge "
        "immer in X; der Code verschob danach in Y und meinte, er habe gedreht."
    ),
    effect=(
        "Der Schlitz läuft jetzt in -Y statt in X — also dorthin, wohin der "
        "Docstring seit jeher zeigt. Wer die Aufhängung bisher an einer Wand "
        "benutzt hat, bekam einen waagerechten Schlitz: Die Schraube wanderte "
        "seitlich, statt sich beim Absinken zu verklemmen. Die Maße ändern sich "
        "nicht, nur ihre Richtung. Alte Projekte rechnen den Schlitz neu, und das "
        "ist beabsichtigt."
    ),
)


LIP_GRIPS_THE_MAGNET = PartChange(
    version="5",
    date="2026-08-25",
    reason=(
        "Die Haltelippe wurde der Tasche hinzugefügt statt von ihr abgezogen — "
        "ein Volumen, das man vereinigt, kann nur weiten, nicht verengen."
    ),
    effect=(
        "Die Mündung ist jetzt ein Zehntel enger als der Magnet, statt genauso "
        "weit wie die Tasche. An einem 6-mm-Magneten gemessen: 5,91 mm statt "
        "6,00 bei kalibriertem Material sogar 6,35. Wer die Lippe bisher "
        "eingeschaltet hatte, bekam keine — der Magnet fiel bei jedem Material "
        "heraus, sobald das Teil kopfüber lag."
    ),
)

HEAD_PLAY_FROM_PROFILE = PartChange(
    version="6",
    date="2026-08-25",
    reason=(
        "Das Kopfspiel stand als feste 0,6 im Baustein und kam damit nie aus dem "
        "Materialprofil (Regel 7, §28.3)."
    ),
    effect=(
        "Mit einem kalibrierten Profil wird das runde Ende enger oder weiter, "
        "statt bei 0,6 mm zu bleiben. Ohne Kalibrierung ändert sich nichts: Der "
        "Vorgabewert ist derselbe."
    ),
)

POCKET_REACHES_PAST_THE_FACE = PartChange(
    version="2",
    date="2026-08-25",
    reason=(
        "Die Fußtasche endete als einziger abziehender Baustein exakt auf der "
        "angeklickten Fläche statt einen Überlappungswert darüber hinaus (§39)."
    ),
    effect=(
        "Kein Maß am fertigen Teil ändert sich — die Tasche ist gleich tief und "
        "gleich weit. Der Schnitt trifft nur nicht mehr Fläche auf Fläche, und "
        "das ist der Fall, an dem eine Boolesche Operation bricht."
    ),
)

#: Wie weit die Haltelippe einer Magnettasche den Magneten unterschreitet.
#:
#: Kein Toleranzmaß aus dem Profil, sondern ein Übermaß: Die Lippe **soll**
#: klemmen. Ein Zehntel Millimeter ist wenig genug, dass der Magnet sich
#: hineindrücken lässt, und genug, dass er nicht von selbst herausfällt — so
#: steht es auch im Text des Parameters.
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
    changes=[FIRST_RELEASE, MOUTH_AT_ORIGIN, FACE_GIVES_DIRECTION, LIP_GRIPS_THE_MAGNET],
)
def magnet_pocket(raw: BaseParams) -> PartResult:
    params = cast(MagnetPocketParams, raw)
    entry = standards.magnet(params.size)
    diameter = entry.diameter + params.play

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
    grip = MAGNET_LIP_GRIP if (params.press_lip and params.cover <= 0.0) else 0.0
    narrow = entry.diameter - grip
    lip_height = MAGNET_LIP_HEIGHT if grip else 0.0

    pocket = shapes.cylinder(diameter, entry.height - lip_height)
    parts = [shapes.moved(pocket, (0.0, 0.0, mouth - entry.height))]

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
                shapes.cylinder(narrow if lip_height else diameter, shapes.OVERLAP),
                (0.0, 0.0, mouth),
            )
        )

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


#: Wie viel Luft der Schraubenkopf im runden Ende eines Schlüssellochs hat,
#: solange das Materialprofil nichts anderes sagt.
#:
#: Der Kopf soll hindurchfallen, nicht klemmen — das ist der eine Fall, in dem
#: großzügiges Spiel richtig ist. Ein kalibriertes Profil überschreibt den Wert
#: über den Parameter ``Spiel``.
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
    name="keyhole",
    title=_("Schlüsselloch-Aufhängung"),
    group="mounting",
    params=KeyholeParams,
    subtractive=True,
    features=["pocket", "bore"],
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
    ],
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
    def falling(width: float, length: float, height: float) -> MeshData:
        """Ein Langloch, dessen Länge in -Y läuft — der Weg der Schraube."""
        return shapes.turned(shapes.slot(width, length, height), 90.0)

    # **Das Kopfspiel kam aus einer festen Zahl** (0,6 mm) und damit an der
    # Kalibrierung vorbei: Die Prüfung nach §28.3 überspringt genau die
    # Bausteine ohne ``play``-Feld, dieser Baustein war einer, und ein Kunde,
    # der sein Material eingemessen hat, bekam trotzdem denselben Wert wie
    # jeder andere. Regel 7 sagt es allgemeiner: keine Zahlenkonstante für
    # Toleranzen.
    clearance = params.play or HEAD_CLEARANCE

    # Die Tasche, in die der Kopf versinkt: am Eingang rund, dann ein Schlitz.
    pocket = falling(screw.head + clearance, screw.head + clearance + params.drop, params.head_room)
    pocket = shapes.moved(pocket, (0.0, drop, -params.head_room))

    # Der Schlitz, in den der Schaft gleitet, ganz hindurch.
    shaft = falling(
        screw.clearance, screw.clearance + params.drop, params.depth + 2.0 * shapes.OVERLAP
    )
    shaft = shapes.moved(shaft, (0.0, drop, -params.depth - shapes.OVERLAP))

    body = union(pocket, shaft)
    return result(
        body,
        bore(
            "pocket_1",
            screw.head + clearance,
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
            "Wie weit die Nase hinter die Lochwand greift. Null heißt: zwei Drittel "
            "der Lochwanddicke."
        ),
    )


@register_part(
    name="pegboard_hook",
    title=_("Lochwand-Einhänger"),
    group="mounting",
    params=PegboardHookParams,
    features=["plate", "hook"],
    keeps_up=True,
    doc=_(
        "Haken für eine Lochwand, auf einer Rückplatte. Von oben in die Schlitze "
        "gesteckt und heruntergezogen — die Nase greift dann hinter die Platte."
    ),
    caveat=_(
        "Die Lochmaße veröffentlicht IKEA nirgends — weder auf der Produktseite "
        "noch in der Montageanleitung. Sie stammen aus einer Sammlung, die selbst "
        "dazuschreibt, dass sie gemessen und nicht amtlich ist. Vor einer größeren "
        "Auflage lohnt ein Prüfdruck."
    ),
    changes=[PEGBOARD_HOOK_ADDED],
)
def pegboard_hook(raw: BaseParams) -> PartResult:
    """Einhänger im Raster, auf einer gemeinsamen Rückplatte.

    **Die Platte ist nicht Zierde, sondern Bedingung.** Zwei Haken im
    Vierzigerraster sind zwei Körper; ein Baustein muss einer sein (§24.3), und
    der Kunde will ohnehin keine zwei losen Haken, sondern ein Teil, das hängt.

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

    span = board.pitch * (params.count - 1)
    across = 0.0 if params.upright else span
    along = span if params.upright else 0.0

    # Die Platte trägt die Haken und liegt am Teil an. Ihr Rand ist ein eigenes
    # Maß und keine abgeleitete Zahl: Er beantwortet, wie viel Material um
    # einen Zapfen stehen muss, damit die Platte ihn hält — das hat mit der
    # Breite des Schlitzes nichts zu tun, in dem der Zapfen später steckt.
    plate = shapes.box(
        across + width + 2.0 * PLATE_MARGIN,
        along + shank + nose + 2.0 * PLATE_MARGIN,
        params.plate,
    )

    # Wie hoch der Zapfen aus der Rückplatte herausragt: durch die Lochwand
    # hindurch, plus was die Nase dahinter braucht.
    through = params.plate + board.thickness + params.play

    parts = [plate]
    features = [
        # Die Rückseite der Platte: was am Teil anliegt. Nach unten gerichtet,
        # denn dort ist das Material, das sie trägt.
        face(
            "plate_1",
            (across + width + 2.0 * PLATE_MARGIN) * (along + shank + nose + 2.0 * PLATE_MARGIN),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, -1.0),
        )
    ]
    for index in range(params.count):
        offset = index * board.pitch - span / 2.0
        x = 0.0 if params.upright else offset
        y = offset if params.upright else 0.0
        # Zapfen und Nase als Langloch, in Y gelegt: ``shapes.slot`` baut seine
        # Länge in X, der Schlitz einer Lochwand steht senkrecht.
        shaft = shapes.turned(shapes.slot(width, shank, through), 90.0)
        # Der Zapfen sitzt oben, und oben ist **-Y** (``PartSpec.keeps_up``).
        parts.append(shapes.moved(shaft, (x, y - nose / 2.0, 0.0)))
        # Die Nase reicht über den Zapfen nach unten hinaus und liegt hinter
        # der Lochwand. Sie beginnt um OVERLAP früher, damit keine Fläche genau
        # auf einer anderen liegt (§39).
        catch = shapes.turned(shapes.slot(width, shank + nose, lip), 90.0)
        parts.append(shapes.moved(catch, (x, y, through - shapes.OVERLAP)))
        # Der Zapfen als benanntes Merkmal: Wer die Haken nachmisst, misst sie
        # hier und nicht an einer Formel über den Hüllquader.
        features.append(
            face(f"hook_{index + 1}", width * shank, (x, y - nose / 2.0, through), (0.0, 0.0, 1.0))
        )

    return result(union(*parts), *features)


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
            "Schräge am Rand. Null heißt beim Fuß: ein Fünftel der Höhe, genug "
            "damit die erste Schicht nicht als Grat vorsteht. Bei der Tasche ist "
            "es eine Fase zum Einfädeln."
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
    name="foot",
    title=_("Standfuß"),
    group="mounting",
    params=FootParams,
    features=["foot"],
    doc=_(
        "Ein Fuß unter einem Gehäuse — gedruckt, oder als Tasche für einen "
        "gekauften aus Gummi. Vier davon halten ein Gerät ruhig und die "
        "Unterseite vom Tisch weg."
    ),
    caveat=_(
        "Nicht für Teile, die auf der Fläche aufliegen sollen — ein Fuß hebt sie ab. "
        "Und nicht zum Verschrauben gedacht: Er hat keine Bohrung, und eine "
        "hineingesetzt stünde die Schraube auf dem Tisch."
    ),
    changes=[FOOT_ADDED, POCKET_REACHES_PAST_THE_FACE],
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
        mouth = shapes.cone(wide, wide + 2.0 * chamfer, chamfer)
        shaft = shapes.cylinder(wide, params.height - chamfer + shapes.OVERLAP)
        # Ein Haar über die Fläche hinaus, wie bei jedem anderen abziehenden
        # Baustein: Zwei Volumen, die sich nur in einer Fläche berühren, sind
        # der Fall, an dem eine Boolesche Operation bricht (§39). Die Tasche
        # endete als einzige exakt auf z = 0 — gemessen ohne Schaden, aber der
        # Fall tritt nicht bei jedem Netz auf, und darauf beruht die Regel.
        rim = shapes.cylinder(wide + 2.0 * chamfer, 2.0 * shapes.OVERLAP)
        body = union(
            shapes.moved(mouth, (0.0, 0.0, -chamfer)),
            shapes.moved(shaft, (0.0, 0.0, -params.height)),
            shapes.moved(rim, (0.0, 0.0, -shapes.OVERLAP)),
        )
        marker = bore("foot_1", wide, (0.0, 0.0, -params.height / 2.0), depth=params.height)
    else:
        # Der Fuß: Die Säule steht am Teil, die Verjüngung am Boden — dort
        # quetscht der Elefantenfuß ins Leere.
        column = shapes.cylinder(wide, params.height - chamfer + shapes.OVERLAP)
        taper = shapes.cone(wide, narrow, chamfer)
        body = union(column, shapes.moved(taper, (0.0, 0.0, params.height - chamfer)))
        # Die Standfläche ist die äußerste, nicht die am Teil: Sie berührt den
        # Tisch, und sie schaut vom Teil weg.
        marker = face(
            "foot_1",
            math.pi * (narrow / 2.0) ** 2,
            (0.0, 0.0, params.height),
            (0.0, 0.0, 1.0),
        )

    return result(body, marker)
