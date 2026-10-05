"""Bausteine für Schrauben (Bauplan §24.1, Gruppe „Verbindungen").

Hier liegen: das Schraubenloch mit seiner Senkung, die Bohrung für die
Einpressbuchse, die Mutternfalle von der Seite oder von unten, und ein
druckbares Gewinde.

Jedes Maß kommt aus der Normteiltabelle (§24.2) — „Loch für eine
M4-Einpressbuchse" ist ein Nachschlagen, keine Vermutung. Was der Baustein
darauflegt, ist die Materialtoleranz aus dem Profil, und er sagt das in seiner
Dokumentation, statt es in einer Zahl zu verstecken.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, cast

from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import (
    bore,
    compound,
    form_of,
    result,
    subtract,
    thread,
    threaded,
    union,
)
from app.core.knowledge.parts.registry import (
    FACE_GIVES_DIRECTION,
    MATERIAL_OF_TARGET,
    FeatureRequirement,
    PartChange,
    WallRequirement,
    register_part,
)
from app.core.registry import op_params, param, play_param
from app.core.registry.params import ZERO_NONE
from app.core.types import BaseParams, Feature, PartResult
from app.i18n import TranslatableText, _

_SCREWS = standards.screw_sizes()
_NUTS = standards.nut_sizes()
_INSERTS = standards.insert_sizes()

THREAD_PROFILES_MATCH = PartChange(
    version="15",
    date="2026-09-06",
    reason="Die innere Wendel hatte entgegengesetzte Flanken; die zugehörigen Druckgewinde "
    "überschnitten sich.",
    effect=_(
        "Innen- und Außengang laufen jetzt gleich, und das automatische Spiel folgt dem Material "
        "des Teils."
    ),
)

FIRST_RELEASE = PartChange(
    version="1", date="2026-07-28", reason="Erstbestückung der Bibliothek (§24.1)."
)

#: Version 3 betrifft zwei Bausteine mit derselben Ursache: ihr Spiel stand
#: als feste Zahl in der Vorgabe (0,2 bzw. 0,15 mm), und der Zweig, der es
#: aus dem kalibrierten Materialprofil füllt, greift nur bei null — die
#: Kalibrierung nach §28.3 erreichte beide nie (Regel 7).
PLAY_FROM_PROFILE = PartChange(
    version="3",
    date="2026-08-16",
    reason="Das Spiel kommt aus dem kalibrierten Materialprofil, nie als Zahl "
    "im Baustein (Regel 7, §28.3).",
    effect=_("Das Spiel kommt jetzt aus dem Materialprofil statt aus festen 0,2 und 0,15 mm."),
)


# --- screw hole -------------------------------------------------------------------


NUT_HEIGHT_FROM_ISO = PartChange(
    version="5",
    date="2026-08-25",
    reason=(
        "Die Mutternhöhen der Tabelle waren die der zurückgezogenen DIN 934 statt "
        "ISO 4032 — und zwar genau in den drei Größen, in denen sich beide "
        "unterscheiden."
    ),
    effect=_("Die Tasche wird bei M5, M6 und M8 tiefer, etwa bei M5 4,70 statt 4,00 mm."),
)

INSERT_LEAD_IS_ITS_OWN_SIZE = PartChange(
    version="5",
    date="2026-08-25",
    reason=(
        "Die Einführfase kam aus ``outer - hole``, und in der Tabelle steht bei "
        "allen sechs Größen zweimal die Bohrung — sie war damit konstant 0,3 mm "
        "statt der halben Wandverdrängung."
    ),
    effect=_(
        "Die Mündungsfase misst jetzt bei jeder Größe 0,5 mm, und die M2.5-Buchse wird 5,7 statt "
        "5,0 mm lang."
    ),
)


M25_INSTALLATION_HOLE = PartChange(
    version="17",
    date="2026-09-12",
    reason="Das Ruthex-Produktdatenblatt nennt für RX-M2,5x5,7 ein Einbauloch von 4,0 mm.",
    effect=_(
        "Der M2.5-Sitz wächst von 3,6 auf 4,0 mm, alte Projekte mit dieser Größe auf die "
        "Wandstärke prüfen."
    ),
)


HEAD_ROOM_CUTS_DOWNWARD = PartChange(
    version="9",
    date="2026-08-26",
    reason=(
        "Die Kopffreiheit baute ihren Zylinder bei z = 0 nach +Z — über die "
        "Mündung, in die Luft über der Fläche (§24.1). Der Baustein ist "
        "abtragend und liegt unter seiner Mündung; nach oben gebaut trug der "
        "Zylinder nichts ab, und der versenkte Kopf stand vor."
    ),
    effect=_(
        "Eine Kopftiefe über null trägt jetzt eine zylindrische Aussparung ab, und die Senkung "
        "rückt um denselben Betrag tiefer."
    ),
)

SCREW_HEADS_USE_THEIR_OWN_RECESSES = PartChange(
    version="12",
    date="2026-08-28",
    reason=(
        "Ohne Senkung nahm die zylindrische Kopfaussparung weiterhin den größeren "
        "Senkkopfdurchmesser statt des Maßes für einen Zylinderkopf. Die Maße "
        "der Unterlegscheiben standen zugleich ungenutzt in der Normteiltabelle."
    ),
    effect=_(
        "Ohne Senkkopf schneidet die Kopftiefe jetzt den Zylinderkopfdurchmesser, bei M4 also "
        "7,0 statt 8,0 mm."
    ),
)

SCREW_HOLE_ZONES = PartChange(
    version="15",
    date="2026-09-06",
    reason="Die Senkung war als zylindrische Bohrung benannt, die Kopfaussparung gar nicht. "
    "Außerdem folgte das automatische Spiel nicht dem Zielmaterial.",
    effect=_(
        "Senkung und Kopfaussparung treffen sich ohne den bisherigen 0,01-mm-Ring, und das Spiel "
        "der Scheibentasche folgt dem Material des Teils."
    ),
)


@op_params
class ScrewHoleParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M3",
        choices=_SCREWS,
        doc=_("Gewindegröße der Schraube. Alle Maße kommen aus der Normteiltabelle."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=10.0,
        unit="mm",
        minimum=1.0,
        maximum=200.0,
        doc=_("Wie tief gebohrt wird. Mehr als die Wandstärke ergibt ein Durchgangsloch."),
    )
    countersink: bool = param(
        title=_("Senkkopf"),
        default=True,
        doc=_("90-Grad-Senkung für einen Senkkopf. Aus für einen Zylinderkopf."),
    )
    washer: bool = param(
        title=_("Unterlegscheibe einlassen"),
        default=False,
        depends_on=("countersink", (False,)),
        doc=_("Schneidet eine passende Auflage für die Unterlegscheibe."),
        placement="advanced",
    )
    play: float = play_param(maximum=2.0, depends_on=("washer", (True,)))
    head_room: float = param(
        title=_("Kopftiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        placement="advanced",
        doc=_("Wie tief Schraubenkopf und Unterlegscheibe in das Bauteil einsinken."),
    )


@register_part(
    name="screw_hole",
    title=_("Schraubenloch mit Senkung"),
    group="fasteners",
    params=ScrewHoleParams,
    subtractive=True,
    features=["bore", "countersink", "washer", "head_room"],
    wall=WallRequirement.not_applicable("Der Baustein ist ein abtragender Werkzeugkörper."),
    feature_requirements=(
        FeatureRequirement("bore"),
        FeatureRequirement("countersink", when="countersink"),
        FeatureRequirement("washer", when="washer", unless="countersink"),
        FeatureRequirement("head_room", unless="head_room", unless_equals=0.0),
    ),
    doc=_(
        "Durchgangsloch zum Verschrauben mit einer metrischen Schraube, auf Wunsch "
        "mit 90-Grad-Senkung "
        "und Kopffreiheit. Maße aus der Normteiltabelle."
    ),
    changes=[
        FIRST_RELEASE,
        FACE_GIVES_DIRECTION,
        HEAD_ROOM_CUTS_DOWNWARD,
        SCREW_HEADS_USE_THEIR_OWN_RECESSES,
        SCREW_HOLE_ZONES,
    ],
)
def screw_hole(raw: BaseParams) -> PartResult:
    params = cast(ScrewHoleParams, raw)
    screw = standards.screw(params.size)

    shaft = shapes.cylinder(screw.clearance, params.depth + BOOLEAN_OVERLAP)
    shaft = shapes.moved(shaft, (0.0, 0.0, -params.depth))
    parts = [shaft]
    features = [
        bore(
            "bore_1",
            screw.clearance,
            (0.0, 0.0, -params.depth / 2.0),
            depth=params.depth,
            through=True,
        )
    ]

    # Die Kopffreiheit versenkt den Kopf: über der Senkung steht eine
    # zylindrische Aussparung in Kopfbreite (§24.1, „über der Senkung“), und die
    # Senkung rückt um denselben Betrag tiefer. Beides liegt **unter** der
    # Mündung — vorher wuchs der Zylinder bei z = 0 nach +Z in die Luft über der
    # Fläche und trug nichts ab. Ohne Kopffreiheit ist ``top`` null und alles
    # bleibt, wo es war.
    top = -params.head_room
    washer = standards.washer(params.size) if params.washer and not params.countersink else None
    washer_diameter = washer.outer + params.play if washer is not None else 0.0

    if params.countersink:
        # Eine 90-Grad-Senkung ist so tief, wie der Kopf breit ist, halbiert.
        depth = (screw.countersink - screw.clearance) / 2.0
        sink = shapes.cone(screw.clearance, screw.countersink, depth)
        parts.append(shapes.moved(sink, (0.0, 0.0, top - depth)))
        features.append(_countersink_feature(screw.countersink, top, depth))

    if params.head_room > 0.0:
        # Die volle Stirnfläche verbindet Zylinder und Kegel. Ein Überstand
        # unter den Kegelrand erzeugte einen schmalen Ringsims und trennte die
        # beiden Mantelflächen. Liegt darunter eine Unterlegscheibe, bleibt der ganze Weg so
        # breit wie die Scheibe: Eine kopfbreite Öffnung über einer größeren
        # Tasche wäre ein gedruckter Hinterschnitt, durch den sich die Scheibe
        # nicht einsetzen ließe.
        head_diameter = screw.countersink if params.countersink else screw.head
        if washer is not None:
            head_diameter = max(head_diameter, washer_diameter)
        room = shapes.cylinder(head_diameter, params.head_room + BOOLEAN_OVERLAP)
        parts.append(shapes.moved(room, (0.0, 0.0, top)))
        features.append(
            bore("head_room_1", head_diameter, (0.0, 0.0, top / 2.0), depth=params.head_room)
        )

    if washer is not None:
        recess = shapes.cylinder(washer_diameter, washer.thickness + 2.0 * BOOLEAN_OVERLAP)
        # Die Scheibe ist die Auflage des Kopfes. Wird der Kopf abgesenkt,
        # muss deshalb ihre ganze Tasche mit nach unten — sonst endet die
        # Kopfaussparung wirkungslos unter einer weiterhin bündigen Scheibe.
        washer_top = top
        parts.append(
            shapes.moved(
                recess,
                (0.0, 0.0, washer_top - washer.thickness - BOOLEAN_OVERLAP),
            )
        )
        features.append(
            bore(
                "washer_1",
                washer_diameter,
                (0.0, 0.0, washer_top - washer.thickness / 2.0),
                depth=washer.thickness,
            )
        )

    return result(union(*parts), *features)


def _countersink_feature(diameter: float, top: float, depth: float) -> tuple[str, Feature]:
    """Die benannte 90-Grad-Senkung für Schraubenloch und gedruckten Schraubenkopf."""
    identifier = "countersink_1"
    return identifier, Feature(
        id=identifier,
        kind="cone",
        provenance="generated",
        params={
            "diameter": diameter,
            "angle": 90.0,
            "axis": (0.0, 0.0, 1.0),
            "centre": (0.0, 0.0, top - depth / 2.0),
            "depth": depth,
            "recess": True,
        },
        measure_sources=dict.fromkeys(
            ("diameter", "angle", "axis", "centre", "depth"), "parameter"
        ),
    )


# --- heat-set insert ---------------------------------------------------------------


@op_params
class HeatsetParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M3",
        choices=_INSERTS,
        doc=_("Gewinde der Buchse. Der Bohrungsdurchmesser dazu kommt aus der Normteiltabelle."),
    )
    lead_in: bool = param(
        title=_("Einführfase"),
        default=True,
        doc=_("Fase am Rand, damit die Buchse beim Einpressen gerade läuft."),
    )
    extra_depth: float = param(
        title=_("Zusatztiefe"),
        default=0.5,
        unit="mm",
        minimum=0.0,
        maximum=5.0,
        placement="advanced",
        doc=_("Platz unter der Buchse für verdrängtes Material."),
    )


def size_for_insert(diameter: float) -> dict[str, Any]:
    """Die kleinste Buchse, die eine Bohrung dieses Durchmessers **aufweitet**.

    Die Buchse ersetzt die Bohrung, sie sitzt nicht auf ihr. Eine Größe, deren
    Bohrung kleiner ist als die vorhandene, schneidet vollständig innerhalb und
    trägt nichts ab — genau das geschah bis zum 23.08.2026 mit der Vorgabe M3
    (4,00 mm) an einer Ø 5,19-Bohrung.
    """
    for size in standards.insert_sizes():
        if standards.insert(size).hole >= diameter:
            return {"size": size}
    return {}


def size_for_nut_trap(diameter: float) -> dict[str, Any]:
    """Die kleinste Mutter, deren Durchgangsloch die Bohrung noch aufnimmt.

    Dasselbe Verhältnis wie bei der Buchse: Das Schraubenloch der Falle tritt
    an die Stelle der vorhandenen Bohrung. Ein kleineres verschwände darin, und
    die Mutter säße in einem Loch, das weiter ist als ihr eigenes.
    """
    for size in standards.screw_sizes():
        if standards.screw(size).clearance >= diameter:
            return {"size": size}
    return {}


def size_for_thread(diameter: float) -> dict[str, Any]:
    """Das größte Gewinde, das in eine Bohrung dieses Durchmessers geschnitten
    werden kann — und zwar als **Innengewinde**.

    Zwei Schranken, beide fachlich und keine geratene Toleranz: Unterhalb des
    Kernlochdurchmessers greift das Werkzeug nicht ins Material, oberhalb des
    Nennmaßes liegt die Bohrungswand außerhalb des Gewindes. Eine
    Ø 6,5-Bohrung bekommt deshalb **keine Größe** statt einer falschen —
    für M6 ist sie zu weit, für M8 zu eng.

    Und ``internal``: Wer eine Bohrung anklickt und „Gewinde" wählt, meint
    Gänge in der Wand. Die Schemavorgabe steht auf Außengewinde, und das ist
    für einen freistehenden Bolzen richtig — in einem Loch setzte sie einen
    zweiten Bolzen hinein.

    **Die beiden Angaben sind verschieden sicher, und deshalb hängen sie nicht
    mehr aneinander.** Die Größe ist ein Vorschlag, der fehlschlagen darf; die
    Richtung steht im angeklickten Merkmal und kann es nicht. Bis zum
    24.08.2026 gab diese Funktion bei fehlender Größe ein leeres Wörterbuch
    zurück und warf die Richtung mit weg — dann griff die Schemavorgabe, und
    aus der Bohrung wuchs ein Bolzen. Getroffen hat es nicht einen Randfall,
    sondern alles oberhalb von M8, der größten Normgröße: gemeldet von Robert
    an einer Bohrung, gemessen an zehn von 22 Durchmessern.
    """
    fitting = [
        size
        for size in standards.screw_sizes()
        if standards.screw(size).tap <= diameter <= standards.screw(size).nominal
    ]
    if not fitting:
        return {"internal": True}
    return {"size": fitting[-1], "internal": True}


def insert_advice(diameter: float) -> TranslatableText:
    """Der Satz über der Bohrung für die Einpressbuchse — dieselbe Größe wie
    :func:`size_for_insert`.

    Der allgemeine Satz nannte die Schraube, deren Durchgangsloch die Bohrung
    ist: An 5,20 mm stand „Passt vermutlich zu M5“, vorgewählt war die Buchse
    M4, deren Einpressloch die Bohrung aufweitet.
    """
    size = size_for_insert(diameter).get("size")
    if size is None:
        return _("Keine Einpressbuchse der Normteiltabelle hat ein so weites Loch.")
    return _(
        "Passend ist die Einpressbuchse {size}; ihr Einpressloch weitet diese Bohrung auf.",
        size=size,
    )


def nut_trap_advice(diameter: float) -> TranslatableText:
    """Der Satz über der Bohrung für die Mutternfalle — dieselbe Größe wie
    :func:`size_for_nut_trap`."""
    size = size_for_nut_trap(diameter).get("size")
    if size is None:
        return _("Keine Mutter der Normteiltabelle hat ein so weites Schraubenloch.")
    return _("Passend ist die Mutter {size}; ihr Schraubenloch nimmt diese Bohrung auf.", size=size)


def thread_advice(diameter: float) -> TranslatableText:
    """Der Satz über der Bohrung für das Innengewinde — dieselbe Größe wie
    :func:`size_for_thread`.

    Über *Druckbares Gewinde* stand „Passt vermutlich zu M5 (Durchgangsloch
    fein)“ und darunter die Vorauswahl M6 (Handbuchbild *Ein Gewinde in eine
    Bohrung*, 4). Beides stimmte, aber der Satz sprach von einem Durchgangsloch,
    und in eine 5,2-mm-Bohrung passt ein **Innengewinde** M6: Kernloch 5,0 mm
    darunter, Nennmaß 6 mm darüber. Wo keines passt, nennt der Satz die zwei
    Nachbarn und warum — dieselben zwei Schranken aus der Normteiltabelle.
    """
    size = size_for_thread(diameter).get("size")
    if size is not None:
        return _("In diese Bohrung passt ein Innengewinde {size}.", size=size)
    sizes = standards.screw_sizes()
    too_wide = [entry for entry in sizes if standards.screw(entry).nominal < diameter]
    too_narrow = [entry for entry in sizes if standards.screw(entry).tap > diameter]
    if too_wide and too_narrow:
        return _(
            "Kein Normgewinde passt in diese Bohrung: Für {smaller} ist sie zu weit, "
            "für {larger} zu eng.",
            smaller=too_wide[-1],
            larger=too_narrow[0],
        )
    if too_wide:
        return _(
            "Kein Normgewinde passt in diese Bohrung: Sie ist weiter als {size}.",
            size=too_wide[-1],
        )
    return _(
        "Kein Normgewinde passt in diese Bohrung: Sie ist enger als das Kernloch von {size}.",
        size=too_narrow[0],
    )


def printed_screw_advice(diameter: float) -> TranslatableText | None:
    """Der Satz über der Bohrung für die gedruckte Schraube — dieselbe Größe
    wie :func:`size_for_printed_screw`; ohne Größe der allgemeine Satz."""
    size = size_for_printed_screw(diameter).get("size")
    if size is None:
        return None
    return _("Diese Bohrung ist das Durchgangsloch einer Schraube {size}.", size=size)


def size_for_printed_screw(diameter: float) -> dict[str, Any]:
    """Die Normschraube für ein vorhandenes Durchgangsloch.

    Die Einordnung einer Bohrung als Durchgangsloch steht absichtlich einmal
    in ``scene.placement``. Das gedruckte Gegenstück benutzt dieselbe Antwort
    wie Senkung und Bohrhinweis, statt nebenan eine zweite Maßregel zu pflegen.
    """
    from app.core.scene.placement import screw_for_bore

    size = screw_for_bore(diameter)
    return {"size": size} if size is not None else {}


@register_part(
    name="heatset_m4",
    title=_("Heat-Set-Einpressbuchse"),
    group="fasteners",
    params=HeatsetParams,
    subtractive=True,
    at_hole=True,
    at_hole_values=size_for_insert,
    at_hole_advice=insert_advice,
    features=["bore", "chamfer"],
    wall=WallRequirement.not_applicable("Der Baustein ist ein abtragender Werkzeugkörper."),
    feature_requirements=(
        FeatureRequirement("bore"),
        FeatureRequirement("chamfer", when="lead_in"),
    ),
    doc=_(
        "Bohrung für eine Heat-Set-Einpressbuchse mit Einführfase. Der Durchmesser "
        "ist bewusst knapp: das Material soll beim Einpressen verdrängt werden."
    ),
    caveat=_(
        "Nicht ohne Lötkolben: Die Buchse wird warm eingepresst, und der Durchmesser "
        "ist dafür knapp gehalten. Kalt hineingedrückt sprengt sie die Wand — ohne "
        "Lötkolben trägt eine Mutternfalle ähnlich viel, und ein Schraubenloch reicht, "
        "wo die Schraube durch das Teil gehen darf."
    ),
    changes=[
        FIRST_RELEASE,
        FACE_GIVES_DIRECTION,
        INSERT_LEAD_IS_ITS_OWN_SIZE,
        M25_INSTALLATION_HOLE,
    ],
)
def heatset_insert(raw: BaseParams) -> PartResult:
    params = cast(HeatsetParams, raw)
    entry = standards.insert(params.size)
    depth = entry.length + params.extra_depth

    shaft = shapes.cylinder(entry.hole, depth + BOOLEAN_OVERLAP)
    shaft = shapes.moved(shaft, (0.0, 0.0, -depth))
    parts = [shaft]
    features = [
        bore("bore_1", entry.hole, (0.0, 0.0, -depth / 2.0), depth=depth),
    ]

    if params.lead_in:
        # **Die Fase fragt nicht, wie viel Material die Buchse verdrängt.** Sie
        # fragt, wie man sie ansetzt, ohne dass sie kippt — und das ist ein
        # eigenes Maß. Vorher stand hier ``(outer - hole) / 2 + 0,3``, also die
        # halbe Wandverdrängung; da in der damaligen Tabelle bei allen sechs
        # Größen ``outer == hole`` eingetragen war (zweimal die Bohrung, nicht
        # der Rändeldurchmesser), war die Fase in Wahrheit konstant 0,3 mm. Der
        # damalige Tabellenfehler und die falsche Ableitung deckten einander zu:
        # Wäre nur eines von beidem falsch gewesen, hätte man es gesehen.
        chamfer = INSERT_LEAD_IN
        lead = shapes.cone(entry.hole, entry.hole + 2.0 * chamfer, chamfer)
        parts.append(shapes.moved(lead, (0.0, 0.0, -chamfer)))
        features.append(
            bore("chamfer_1", entry.hole + 2.0 * chamfer, (0.0, 0.0, -chamfer / 2.0), depth=chamfer)
        )

    return result(union(*parts), *features)


# --- nut trap -----------------------------------------------------------------------


NUT_TRAP_SINKS_ON_A_FACE = PartChange(
    version="9",
    date="2026-08-26",
    reason=(
        "An eine Fläche gesetzt baute die Mutternfalle ihre Tasche nach oben in "
        "die Luft über der Fläche und trug nichts ab (§24.1). Sie ist der "
        "einzige abtragende Baustein, der nach oben baut — an einer Bohrung "
        "richtig behandelt, an einer Fläche nicht."
    ),
    effect=_(
        "An einer Fläche wird die Tasche jetzt ins Material gebaut statt darüber, an einer "
        "Bohrung ändert sich nichts."
    ),
)


@op_params
class NutTrapParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M3",
        choices=_NUTS,
        doc=_("Gewinde der Mutter. Schlüsselweite und Höhe kommen aus der Normteiltabelle."),
    )
    direction: str = param(
        title=_("Richtung"),
        default="side",
        choices=("side", "bottom"),
        doc=_("Von der Seite eingeschoben oder von unten eingelegt."),
    )
    slide: float = param(
        title=_("Einschubweg"),
        default=12.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_("Wie weit der Schlitz nach außen reicht. Null heißt: nur die Tasche."),
        zero_text=ZERO_NONE,
    )
    play: float = play_param()
    screw_hole: bool = param(
        title=_("Schraubenloch mitschneiden"),
        default=True,
        doc=_("Schneidet zusätzlich das Durchgangsloch für die Schraube durch das Teil."),
        placement="advanced",
    )


@register_part(
    name="nut_trap",
    title=_("Mutternfalle"),
    group="fasteners",
    params=NutTrapParams,
    subtractive=True,
    at_hole=True,
    at_hole_values=size_for_nut_trap,
    at_hole_advice=nut_trap_advice,
    features=["pocket", "bore"],
    wall=WallRequirement.not_applicable("Der Baustein ist ein abtragender Werkzeugkörper."),
    feature_requirements=(
        FeatureRequirement("pocket"),
        FeatureRequirement("bore", when="screw_hole"),
    ),
    doc=_(
        "Tasche für eine Sechskantmutter, seitlich eingeschoben oder von unten "
        "eingelegt, auf Wunsch mit durchgehendem Schraubenloch."
    ),
    caveat=_(
        "Nur mit passender Sechskantmutter: Die Tasche ist auf die Schlüsselweite aus "
        "der Normteiltabelle gebaut, eine beliebige Mutter wackelt darin oder geht "
        "nicht hinein. Und sie muss erreichbar bleiben — seitlich eingeschoben "
        "braucht sie eine freie Flanke, von unten eingelegt eine Öffnung, die kein "
        "späterer Schritt zubaut. Wo keine Mutter zur Hand ist, hält ein gedrucktes "
        "Gewinde leichte Lasten; für tragende Verschraubungen ist eine Einpressbuchse "
        "richtig."
    ),
    changes=[
        FIRST_RELEASE,
        PLAY_FROM_PROFILE,
        FACE_GIVES_DIRECTION,
        NUT_HEIGHT_FROM_ISO,
        NUT_TRAP_SINKS_ON_A_FACE,
        MATERIAL_OF_TARGET,
    ],
)
def nut_trap(raw: BaseParams) -> PartResult:
    params = cast(NutTrapParams, raw)
    entry = standards.nut(params.size)
    width = entry.width + params.play
    height = entry.height + params.play / 2.0

    pocket = shapes.hexagon(width, height)
    parts = [pocket]
    features = [
        bore("pocket_1", width, (0.0, 0.0, height / 2.0), depth=height),
    ]

    if params.slide > 0.0:
        # Der Schlitz, durch den die Mutter eingeschoben wird, entlang +Y zeigend.
        channel = shapes.box(width, params.slide, height)
        parts.append(shapes.moved(channel, (0.0, params.slide / 2.0, 0.0)))

    if params.screw_hole:
        screw = standards.screw(params.size)
        length = height + 20.0
        shaft = shapes.cylinder(screw.clearance, length)
        parts.append(shapes.moved(shaft, (0.0, 0.0, -10.0)))
        features.append(
            bore("bore_1", screw.clearance, (0.0, 0.0, height / 2.0), depth=length, through=True)
        )

    body = union(*parts)
    if params.direction == "bottom":
        # Gedreht, sodass die Öffnung nach unten schaut — von unten eingelegt
        # statt von der Seite eingeschoben.
        body = shapes.turned(body, 90.0, (1.0, 0.0, 0.0))
    return result(body, *features)


# --- thread --------------------------------------------------------------------------


#: Die Einführschräge am Mund einer Einpressbuchsen-Bohrung.
#:
#: Ein fester Wert, weil die Frage eine feste ist: Die Buchse soll sich fangen
#: lassen, bevor der Lötkolben sie senkrecht hält. Eine halbe Millimeter-Fase
#: reicht dafür bei M2 wie bei M6 — sie skaliert nicht mit dem Durchmesser,
#: denn die Hand, die ansetzt, tut es auch nicht.
INSERT_LEAD_IN = 0.5

THREAD_CUTS_INWARD = PartChange(
    version="5",
    date="2026-08-25",
    reason=(
        "Das Innengewinde wurde vereinigt statt abgezogen — entgegen dem "
        "eigenen Parametertext, der es seit je richtig sagt."
    ),
    effect=_(
        "Auf „Innengewinde“ wird jetzt ein Gewinde unter der Mündung geschnitten statt ein "
        "Bolzen aufgesetzt, das Außengewinde bleibt gleich."
    ),
)

PRINTED_FASTENERS = PartChange(
    version="1",
    date="2026-08-28",
    reason=(
        "Gedruckte Schraube und Mutter fehlten, obwohl ein druckbares Gewinde "
        "bereits vorhanden war."
    ),
    effect=_(
        "Eine Schraube mit Sechskant- oder Senkkopf und eine passende Mutter "
        "sind jetzt als getrennte, druckbare Bausteine verfügbar."
    ),
)

PRINTED_SCREW_PREPARES_COUNTERSINK = PartChange(
    version="2",
    date="2026-08-28",
    reason=(
        "Der Senkkopf änderte nur die Schraube. Die gewählte Bohrung blieb "
        "zylindrisch, deshalb stand der Kopf trotz aktivierter Wahl auf der Fläche."
    ),
    effect=_(
        "Mit Senkkopf schneidet derselbe Schritt jetzt eine 90-Grad-Senkung in die Bohrung und "
        "setzt den Kopf bündig hinein."
    ),
)

PRINTED_SCREW_GEOMETRY_FIXED = PartChange(
    version="13",
    date="2026-08-31",
    reason=(
        "Beim Senkkopf lagen Kopf und Gewinde auf demselben Längenabschnitt; "
        "kurze Gewinde verschwanden im Kopf, lange konnten am Übergang zerfallen. "
        "Zusätzlich berührten Gewindegang und Kern sich nur auf derselben Zylinderfläche."
    ),
    effect=_(
        "Bei Senkkopf beginnt die Gewindelänge jetzt unter der Kopfspitze, die Schraube wird "
        "also um die Kopfhöhe länger."
    ),
)

PRINTED_THREAD_ROOT_OVERLAPS_CORE = PartChange(
    version="13",
    date="2026-08-31",
    reason=(
        "Gewindegang und Kern berührten sich nur auf derselben Zylinderfläche; "
        "die Vereinigung ließ dort koplanar überdeckte Dreiecke zurück."
    ),
    effect=_(
        "Der Gang greift jetzt ein kleines Stück in den Kern, alle Maße des Gewindes bleiben "
        "gleich."
    ),
)

THREAD_OPENS_AT_BOTH_ENDS = PartChange(
    version="20",
    date="2026-09-22",
    reason=(
        "Der Gang eines Netzgewindes begann erst am unteren Ende. Ein Innengewinde "
        "hatte dort einen Umlauf Material im Gang, und eine gedruckte Schraube kam "
        "nicht durch die gedruckte Mutter — bei M8 und 0,2 mm Spiel überdeckten sich "
        "beide um 2,3 mm³."
    ),
    effect=_(
        "Der Gang läuft jetzt an beiden Enden voll aus, Mutter und Gewindeloch sind unten offen."
    ),
)


@op_params
class ThreadParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M6",
        choices=_SCREWS,
        doc=_(
            "Nenndurchmesser und Steigung. Das Profil ist druckbar abgeflacht, "
            "kein ISO-Profil — das löst ein Drucker ohnehin nicht auf."
        ),
    )
    length: float = param(
        title=_("Länge"),
        default=12.0,
        unit="mm",
        minimum=2.0,
        maximum=200.0,
        doc=_("Länge des Gewindes, nicht des Bolzens."),
    )
    internal: bool = param(
        title=_("Innengewinde (aus = Außengewinde)"),
        default=False,
        # **Der Satz stand hier, die Operation tat es nicht.** Ohne
        # ``subtractive_on`` galt der feste Wert des Registereintrags
        # (``subtractive=False``), und der Baustein wurde in *beiden*
        # Stellungen vereinigt. In ein Kernloch gesetzt wuchs damit ein Bolzen
        # hinein statt eines Gewindes: an M6 über 10 mm gemessen +190 mm³
        # statt -48. Der Docstring der Funktion nennt den Körper sogar
        # „das Werkzeug" — ein Werkzeug, das man vereinigt, ist keines.
        subtractive_on=(True,),
        doc=_(
            "Aktivieren für Innengewinde in einer Bohrung; deaktivieren für "
            "einen Gewindebolzen auf einer ebenen Außenfläche. Für einen Behälter "
            "mit passendem Schraubdeckel verwenden Sie „Drehdeckel erzeugen“."
        ),
    )
    play: float = play_param()


@register_part(
    name="printed_thread",
    title=_("Druckbares Gewinde"),
    group="fasteners",
    params=ThreadParams,
    subtractive=False,
    at_hole=True,
    at_hole_values=size_for_thread,
    at_hole_advice=thread_advice,
    features=["thread"],
    wall=WallRequirement.not_applicable(
        "Das Innengewinde ist ein abtragendes Werkzeug; beim Außengewinde "
        "werden die Gewindekämme vom massiven Kern getragen."
    ),
    doc=_(
        "Druckbares Innengewinde in einer Bohrung oder Gewindebolzen auf einer "
        "ebenen Fläche — als Wendel mit abgeflachtem Kamm. Für einen offenen "
        "Behälter mit passendem Schraubdeckel ist „Drehdeckel erzeugen“ der "
        "gemeinsame Weg."
    ),
    caveat=_(
        "Nicht, wo eine Metallschraube greifen soll: Der Kamm ist abgeflacht, damit "
        "ein Drucker ihn überhaupt auflöst — ein genormtes Gegenstück fasst darin "
        "nicht sauber. Für tragende Verschraubungen ist eine Einpressbuchse richtig, "
        "und wo kein Lötkolben zur Hand ist, eine Mutternfalle."
    ),
    changes=[
        FIRST_RELEASE,
        PLAY_FROM_PROFILE,
        FACE_GIVES_DIRECTION,
        THREAD_CUTS_INWARD,
        PRINTED_THREAD_ROOT_OVERLAPS_CORE,
        THREAD_PROFILES_MATCH,
        THREAD_OPENS_AT_BOTH_ENDS,
    ],
)
def printed_thread(raw: BaseParams) -> PartResult:
    """Ein Gewinde, und sein Gegenstück so gemessen, dass die zwei wirklich
    greifen.

    Beide werden von denselben zwei Zahlen beschrieben — Außendurchmesser und
    Steigung — und von entgegengesetzten Enden des Gangs her gebaut:

    * außen liegt der Kern zwei Gangtiefen unter dem Außendurchmesser, und die
      Helix reicht bis zu ihm hinaus;
    * innen beginnt das *Werkzeug* bei genau diesem Kerndurchmesser, und die
      Helix reicht bis zum Außendurchmesser. Vom Kern geschnitten statt vom
      Außendurchmesser — das ist der Unterschied zwischen einer Mutter und
      einem glatten Loch: eine Bohrung auf Außendurchmesser lässt nichts
      stehen, woran der Gang einer Schraube halten könnte, und die Schraube
      fällt glatt hindurch. An M6 gemessen: eine Schraube mit 5,85 außen
      reicht bis r = 2,925, und ein auf 6,15 gebohrtes Loch beginnt bei
      r = 3,075 — hundertfünfzig Mikrometer Luft.
    """
    params = cast(ThreadParams, raw)
    return _printed_thread(params.size, params.length, params.internal, params.play)


def _printed_thread(
    size: str, length: float, internal: bool, play: float, *, bottom: float | None = None
) -> PartResult:
    """Baut das Gewinde für Bausteine, die mit seinen Maßen zusammenpassen.

    ``bottom`` ist die Höhe des unteren Endes. Ohne Angabe gilt §24.1: **Ein
    Werkzeug liegt unter seiner Mündung** — das Innengewinde trägt ab, also
    gehört es in das Material unter der angeklickten Stelle (nach oben gebaut
    stünde es in der Luft und schnitte nichts); das Außengewinde setzt auf und
    wächst von null nach oben. Wer das Gewinde woanders braucht (die Schraube
    unter ihrem Kopf, die Mutter um ihre Höhe), sagt es hier, statt den
    fertigen Körper zu bewegen — exakt kostet jede Bewegung Sekunden.
    """
    screw = standards.screw(size)
    depth = screw.pitch * shapes.RIDGE_SHARE
    if internal:
        # Das Werkzeug: Kern plus Spiel, und die Nut reicht von dort hinaus.
        diameter = screw.nominal - 2.0 * depth + play
    else:
        diameter = screw.nominal - play
        if diameter <= 2.0 * depth:
            raise ValidationError(
                "play",
                _(
                    "Das Spiel lässt keinen Gewindekern stehen. Ein kleineres Spiel "
                    "oder eine größere Schraube wählen."
                ),
                values={"maximum": screw.nominal - 2.0 * depth, "play": play},
            )
    built = length
    if bottom is None:
        bottom = -length if internal else 0.0
        # Das Werkzeug reicht ein Hundertstel über die Mündung hinaus (§39); der
        # Gang beginnt trotzdem unten, die Phase hängt an ``bottom``.
        built = length + BOOLEAN_OVERLAP if internal else length

    # Kern plus Gang, auf Länge geschnitten — wie das entsteht, weiß ``build``
    # je Kern; die Maße stehen hier.
    body = threaded(diameter, screw.pitch, built, internal=internal, bottom=bottom)
    return result(
        body,
        _thread_feature(size, play, (0.0, 0.0, bottom + length / 2.0), internal, length),
    )


def _thread_feature(
    size: str, play: float, centre: tuple[float, float, float], internal: bool, length: float
) -> tuple[str, Feature]:
    """Das Merkmal eines gedruckten Gewindes: das gebaute Maß und das Nennmaß daneben.

    Jede Hälfte steht um das Spiel neben dem Nennmaß — die Mutter weiter, der
    Bolzen enger (:func:`_printed_thread`), ein gedrucktes Paar hat es also
    zweimal. Nannte das Merkmal das Nennmaß, maß die Gewindepassung eines
    frischen Paars 0,00 mm und meldete es als zu eng; ein eingelesenes
    Gewinde nennt ohnehin, was gebaut ist.

    Das Nennmaß steht als ``nominal`` daneben: Die Passungsprüfung weiß daran,
    dass diese Hälfte das Spiel des Materials trägt (``fits._thread_wanted``),
    und das Gegenstück findet seine Tabellengröße
    (``counterpart.thread_size_for``).
    """
    screw = standards.screw(size)
    identifier, feature = thread(
        "thread_1",
        screw.nominal + play if internal else screw.nominal - play,
        screw.pitch,
        centre,
        internal=internal,
        length=length,
    )
    return identifier, replace(
        feature,
        params={**feature.params, "nominal": screw.nominal},
        measure_sources={**feature.measure_sources, "nominal": "parameter"},
    )


SEPARATE_PARTS_KEEP_THEIR_PLAY = PartChange(
    version="21",
    date="2026-09-27",
    reason=(
        "Schraubenkopf und Mutter lagen ohne Abstand auf ihrem Sitz: der Senkkopf "
        "deckungsgleich in seiner Senkung, Sechskantkopf und Mutter auf der Fläche. An "
        "Ort und Stelle in einem Stück gedruckt verschweißten sie mit dem Träger (RM-276)."
    ),
    effect=_(
        "Kopf und Mutter stehen jetzt um das Spiel über ihrem Sitz, die Senkung wird um das "
        "Spiel weiter."
    ),
)


@op_params
class PrintedScrewParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M5",
        choices=_SCREWS,
        doc=_("Nenndurchmesser und Steigung des passenden gedruckten Gewindes."),
    )
    length: float = param(
        title=_("Länge"),
        default=12.0,
        unit="mm",
        minimum=2.0,
        maximum=200.0,
        doc=_("Länge des Gewindes unter dem Schraubenkopf."),
    )
    countersunk: bool = param(
        title=_("Senkkopf"),
        default=False,
        doc=_(
            "Formt einen 90-Grad-Senkkopf und senkt die gewählte Bohrung im "
            "selben rücknehmbaren Schritt passend an."
        ),
    )
    play: float = play_param()


@register_part(
    name="printed_screw",
    title=_("Schraube"),
    group="fasteners",
    params=PrintedScrewParams,
    at_hole=True,
    at_face=False,
    at_hole_mouth=True,
    at_hole_values=size_for_printed_screw,
    at_hole_advice=printed_screw_advice,
    separate_from_host=True,
    host_cut=lambda raw: _printed_screw_countersink(raw),
    features=["thread", "countersink"],
    wall=WallRequirement.not_applicable(
        "Die Gewindekämme werden vom massiven Schraubenkern getragen."
    ),
    feature_requirements=(FeatureRequirement("thread"),),
    doc=_(
        "Druckbare Schraube für eine gewählte Bohrung, mit Sechskantkopf oder "
        "automatisch bündig gesenktem Senkkopf und passendem Außengewinde."
    ),
    caveat=_(
        "Nur aus dem Material des Teils, an dem sie sitzt: Gewinde und Kopf haben dessen "
        "Spiel, dann bleibt die Schraube auch mitgedruckt lösbar. Für hohe "
        "Lasten oder häufiges Lösen sind Metallschrauben mit Mutternfalle oder "
        "Heat-Set-Buchse zuverlässiger."
    ),
    changes=[
        PRINTED_FASTENERS,
        PRINTED_SCREW_PREPARES_COUNTERSINK,
        PRINTED_SCREW_GEOMETRY_FIXED,
        THREAD_PROFILES_MATCH,
        THREAD_OPENS_AT_BOTH_ENDS,
        SEPARATE_PARTS_KEEP_THEIR_PLAY,
    ],
)
def printed_screw(raw: BaseParams) -> PartResult:
    """Eine Schraube, deren Gewinde und Kopf an derselben Bohrung sitzen."""
    params = cast(PrintedScrewParams, raw)
    screw = standards.screw(params.size)
    diameter = screw.nominal - params.play
    # **Auch der Kopf hat Spiel zu seinem Sitz** (RM-276). Er lag ohne Abstand
    # auf dem Träger, und an Ort und Stelle in einem Stück gedruckt verschweißte
    # die Berührungsfläche Kopf und Träger — lösbar war nur das Gewinde. Der
    # Sechskantkopf steht deshalb um das Spiel über der Fläche, und die ganze
    # Schraube mit ihm, damit die Gewindelänge unter dem Kopf gleich bleibt.
    # Eine ebene Fuge hat nur eine Seite: das ganze Spiel, nicht die Hälfte je
    # Flanke wie am Gewinde. Der Senkkopf bleibt bündig; bei ihm wird die
    # Senkung weiter (:func:`_printed_screw_countersink`).
    thread_top = params.play
    if params.countersunk:
        head_height = (screw.countersink - diameter) / 2.0
        thread_top = -head_height
        head = shapes.cone(diameter, screw.countersink, head_height)
        # Der breite Rand liegt bündig an der Mündung; der schmale Teil des
        # Kopfes reicht in die Bohrung. Vorher stand auch der Senkkopf auf
        # z = 0 und damit vollständig **über** der Fläche.
        head = shapes.moved(head, (0.0, 0.0, -head_height))
    else:
        head = shapes.moved(shapes.hexagon(screw.head, screw.head_height), (0.0, 0.0, thread_top))

    # Die Länge meint ausdrücklich das Gewinde **unter** dem Kopf. Beim
    # Senkkopf ist dessen schmale Spitze die Trennstelle; z = 0 ist dagegen
    # der breite, bündige Rand. Vorher endete das Gewinde ebenfalls bei null
    # und lag damit um die ganze Kopfhöhe im Kopf. Bei kurzen Schrauben blieb
    # kein Gang außerhalb des Kegels, bei langen zerfiel die Vereinigung an
    # einzelnen Normgrößen. Ein kleiner Überstand verbindet beide Körper
    # robust, ohne das zugesagte Längenmaß sichtbar zu verändern.
    shank = form_of(
        _printed_thread(
            params.size,
            params.length,
            internal=False,
            play=params.play,
            bottom=thread_top - params.length + BOOLEAN_OVERLAP,
        )
    )

    # **Der Senkkopf bleibt am exakten Kern ein Verbund** (P2.7, Befund B2):
    # Kegel und Gang berühren sich tangential, die Vereinigung machte daraus
    # zwei Körper, und die Fuzzy-Stufe, die sie zu einem verschmolz, kam aus
    # STEP ungültig zurück. Die Schraube ist ohnehin ein lösbares Teil.
    joined = compound if shapes.building_exact() and params.countersunk else union
    body = joined(head, shank)
    return result(
        body,
        _thread_feature(
            params.size,
            params.play,
            (0.0, 0.0, thread_top - params.length / 2.0),
            False,
            params.length,
        ),
    )


def _printed_screw_countersink(raw: BaseParams) -> PartResult | None:
    """Die zum gewählten Senkkopf passende Vorbereitung des Trägers."""
    params = cast(PrintedScrewParams, raw)
    if not params.countersunk:
        return None

    screw = standards.screw(params.size)
    # **Die Senkung steht um das Spiel vom Kopf ab** (RM-276): Sie war der Kopf
    # selbst — dieselbe 90°-Flanke, derselbe Außendurchmesser —, und an Ort und
    # Stelle gedruckt verschweißten beide. Die Flanke rückt jetzt senkrecht zu
    # sich um das Spiel nach außen; unter 45° sind das ``√2 · Spiel`` im Halbmesser.
    # Der Kopf bleibt bündig mit der Fläche.
    mouth = screw.countersink + 2.0 * math.sqrt(2.0) * params.play
    depth = (mouth - screw.clearance) / 2.0
    cutter = shapes.cone(screw.clearance, mouth, depth)
    cutter = shapes.moved(cutter, (0.0, 0.0, -depth))
    return result(cutter, _countersink_feature(mouth, 0.0, depth))


@op_params
class PrintedNutParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M5",
        choices=_NUTS,
        doc=_("Nenndurchmesser und Steigung des passenden gedruckten Gewindes."),
    )
    play: float = play_param()


@register_part(
    name="printed_nut",
    title=_("Gedruckte Mutter"),
    group="fasteners",
    params=PrintedNutParams,
    separate_from_host=True,
    features=["thread"],
    wall=WallRequirement.not_applicable(
        "Die Gewindekämme werden von der massiven Mutternhülle getragen."
    ),
    doc=_("Druckbare Sechskantmutter mit passendem Innengewinde."),
    caveat=_(
        "Nur aus dem Material der Schraube und des Teils, auf dem sie sitzt: Gewinde und "
        "Auflage haben dessen Spiel, dann bleibt die Mutter auch mitgedruckt lösbar. "
        "Für hohe Lasten oder häufiges Lösen sind Metallschrauben mit "
        "Mutternfalle oder Heat-Set-Buchse zuverlässiger."
    ),
    changes=[
        PRINTED_FASTENERS,
        PRINTED_THREAD_ROOT_OVERLAPS_CORE,
        THREAD_PROFILES_MATCH,
        THREAD_OPENS_AT_BOTH_ENDS,
        SEPARATE_PARTS_KEEP_THEIR_PLAY,
    ],
)
def printed_nut(raw: BaseParams) -> PartResult:
    """Eine Sechskantmutter, deren Innengewinde zum gedruckten Bolzen passt."""
    params = cast(PrintedNutParams, raw)
    nut = standards.nut(params.size)
    depth = nut.height + 2.0 * BOOLEAN_OVERLAP
    # Wie der Schraubenkopf steht die Mutter um das Spiel über der Fläche, auf
    # der sie sitzt (RM-276): Ohne Abstand verschweißte sie an Ort und Stelle
    # gedruckt mit dem Träger.
    lift = params.play
    # Das Werkzeug reicht ein Hundertstel unter den Boden und über die Decke hinaus.
    cutter = form_of(
        _printed_thread(
            params.size, depth, internal=True, play=params.play, bottom=lift - BOOLEAN_OVERLAP
        )
    )
    body = subtract(shapes.moved(shapes.hexagon(nut.width, nut.height), (0.0, 0.0, lift)), cutter)
    return result(
        body,
        _thread_feature(
            params.size, params.play, (0.0, 0.0, lift + nut.height / 2.0), True, nut.height
        ),
    )
