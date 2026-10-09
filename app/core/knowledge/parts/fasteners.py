"""Bausteine für Schrauben (Bauplan §24.1, Gruppe „Verbindungen").

Hier liegen: das Schraubenloch mit seiner Senkung, die Bohrung für die
Einpressbuchse, die Mutternfalle von der Seite oder von unten, ein
druckbares Gewinde und, aus demselben Gewindekern, der Gewindebolzen.

Jedes Maß kommt aus der Normteiltabelle (§24.2) — „Loch für eine
M4-Einpressbuchse" ist ein Nachschlagen, keine Vermutung. Ein eigenes Maß
(:data:`CUSTOM_SIZE`) ist aus ihr abgeleitet und sagt das im Befund; eine
Einpressbuchse mit eigenem Maß nimmt die Werte aus ihrem Datenblatt. Was der Baustein
darauflegt, ist die Materialtoleranz aus dem Profil, und er sagt das in seiner
Dokumentation, statt es in einer Zahl zu verstecken.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Final, cast

from app.core.errors import CHANGE_SIZE, CHANGE_THIS_STEP, ValidationError
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
from app.core.registry.params import ZERO_AUTOMATIC, ZERO_NONE, ZERO_THROUGH
from app.core.types import (
    BaseParams,
    Feature,
    Finding,
    ParamPlacement,
    PartResult,
    Profile,
    Vec3,
)
from app.core.units import (
    COARSEST_PITCH,
    EPS_GEOM,
    FINEST_PITCH,
    LARGEST_THREAD,
    SMALLEST_THREAD,
    THREAD_MIN_CORE_SHARE,
    THREAD_MIN_GRIP_SHARE,
    format_length,
)
from app.i18n import TranslatableText, _

#: Die Wahl, unter der ein Baustein sein Maß selbst nennt, statt es aus der
#: Normteiltabelle zu nehmen — beim Gewinde Durchmesser und Steigung, bei
#: Schraube, Mutter und Loch den Nenndurchmesser, bei der Einpressbuchse
#: Bohrung und Länge aus dem Datenblatt.
CUSTOM_SIZE: Final = "custom_size"

_SCREWS = standards.screw_sizes()

#: Wie tief Kopf und Scheibe höchstens einsinken: der höchste Zylinderkopf und
#: die dickste Scheibe der Tabelle (M64: 64 + 10 mm). Eine feste 50 ließ die
#: Köpfe ab M56 nicht ganz versenken (Review RM-532 Runde 2, N6).
_DEEPEST_HEAD_ROOM: Final = max(standards.screw(size).head_height for size in _SCREWS) + max(
    standards.washer(size).thickness for size in standards.washer_sizes()
)
_NUTS = standards.nut_sizes()
_INSERTS = standards.insert_sizes()


def _nominal_param(doc: TranslatableText, *, placement: ParamPlacement = "front") -> Any:
    """Der Nenndurchmesser eines eigenen Maßes — je Schema ein eigenes Feld.

    Dieselben Grenzen wie beim Gewinde (``units.SMALLEST_THREAD`` bis
    ``LARGEST_THREAD``): Schraube, Mutter und Loch passen zu jedem Gewinde,
    das die Bibliothek baut.

    ``placement``: Wo vorn schon drei Felder stehen, steht das Maß hinter der
    Klappe — drei Felder vorn sind die Regel (``test_interface_limits``), und
    die Zusammenfassung der geschlossenen Klappe nennt es, sobald es wirkt.
    """
    return param(
        title=_("Nenndurchmesser"),
        default=20.0,
        unit="mm",
        minimum=SMALLEST_THREAD,
        maximum=LARGEST_THREAD,
        depends_on=("size", (CUSTOM_SIZE,)),
        placement=placement,
        doc=doc,
    )


_DERIVED_NOMINAL_DOC = _(
    "Der Durchmesser, wie die Zahl hinter dem M. Ohne Normgröße sind Löcher, Kopf "
    "und Mutter aus den Normgrößen daneben abgeleitet und nicht genormt."
)


def _screw_of(size: str, diameter: float) -> standards.Screw:
    """Die Schraube eines Bausteins: aus der Tabelle oder mit eigenem Maß abgeleitet."""
    return standards.derived_screw(diameter) if size == CUSTOM_SIZE else standards.screw(size)


def _nut_of(size: str, diameter: float) -> standards.Nut:
    """Die Mutter eines Bausteins: aus der Tabelle oder mit eigenem Maß abgeleitet."""
    return standards.derived_nut(diameter) if size == CUSTOM_SIZE else standards.nut(size)


def _washer_of(size: str, diameter: float) -> standards.Washer:
    """Die Scheibe eines Bausteins: aus der Tabelle oder mit eigenem Maß abgeleitet."""
    return standards.derived_washer(diameter) if size == CUSTOM_SIZE else standards.washer(size)


def _derived(made: PartResult, size: str, diameter: float) -> PartResult:
    """Sagt am Ergebnis, dass ein eigenes Maß abgeleitet und nicht genormt ist.

    Ein Kunde, der Ø 11 einträgt, bekommt ein Durchgangsloch von 12,25 mm, und
    das steht in keiner Norm. Der Befund nennt es, damit niemand die Zahl für
    ein Normmaß hält; trifft der Durchmesser eine Normgröße, ist es deren Maß
    und kein Befund nötig.
    """
    if size != CUSTOM_SIZE or standards.tabulated_size(diameter) is not None:
        return made
    # Ø 60 ist ein ISO-Nennmaß ohne Zylinderschraube nach DIN 912: Abgeleitet
    # treffen Steigung, Löcher, Mutter und Scheibe die Normwerte, nur der Kopf
    # nicht. „Nicht genormt“ war dort zu viel gesagt (Review RM-532 Runde 2, K-N3).
    message = (
        _(
            "Eigenes Maß Ø {diameter}: Steigung, Löcher, Mutter und Scheibe sind Normmaße; "
            "nur der Kopf ist abgeleitet, eine Zylinderschraube dieser Größe ist nicht genormt.",
            diameter=format_length(diameter),
        )
        if standards.headless_size(diameter)
        else _(
            "Eigenes Maß Ø {diameter}: Die Maße sind aus den Normgrößen daneben "
            "abgeleitet und nicht genormt.",
            diameter=format_length(diameter),
        )
    )
    made.findings.append(
        Finding(
            code="parts.derived_size",
            severity="info",
            message=message,
            values={"diameter_mm": diameter},
        )
    )
    return made


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
        choices=(*_SCREWS, CUSTOM_SIZE),
        doc=_(
            "Gewindegröße der Schraube. Alle Maße kommen aus der Normteiltabelle, bei "
            "„Eigenes Maß“ aus den Normgrößen daneben."
        ),
    )
    diameter: float = _nominal_param(_DERIVED_NOMINAL_DOC, placement="advanced")
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
        maximum=_DEEPEST_HEAD_ROOM,
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
    screw = _screw_of(params.size, params.diameter)

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
    washer = (
        _washer_of(params.size, params.diameter)
        if params.washer and not params.countersink
        else None
    )
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

    made = _derived(result(union(*parts), *features), params.size, params.diameter)
    if params.countersink and screw.countersink_derived:
        # Review RM-532 Runde 2, N3: Über M24 führt keine Norm einen Senkkopf, M18
        # und M22 führt das Maßblatt der Tabelle nicht — die Senkung ist dort
        # gerechnet, und wer eine Schraube kauft, findet womöglich keine dazu.
        # Der Satz sagt deshalb, was in allen drei Fällen belegt ist: Die
        # Normteiltabelle führt keinen Senkkopf (Review P2 N5).
        named = params.size if params.size != CUSTOM_SIZE else f"Ø {format_length(screw.nominal)}"
        made.findings.append(
            Finding(
                code="parts.countersink_derived",
                severity="info",
                message=_(
                    "Für {size} führt die Normteiltabelle keinen Senkkopf, die Senkung "
                    "Ø {diameter} ist abgeleitet. Für einen Zylinderkopf „Senkkopf“ ausschalten.",
                    size=named,
                    diameter=format_length(screw.countersink),
                ),
                values={
                    "part": "screw_hole",
                    "field": "countersink",
                    "countersink_mm": screw.countersink,
                },
                suggestions=(CHANGE_THIS_STEP,),
            )
        )
    return made


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
        choices=(*_INSERTS, CUSTOM_SIZE),
        doc=_(
            "Gewinde der Buchse, die Bohrung dazu kommt aus der Normteiltabelle. Für eine "
            "andere Buchse „Eigenes Maß“ mit den Werten ihres Datenblatts wählen."
        ),
    )
    # **Einpressbuchsen sind nicht genormt**, jeder Hersteller nennt sein Loch.
    # Wer eine Buchse hat, die nicht in der Tabelle steht, trägt Bohrung und
    # Länge aus ihrem Datenblatt ein. Den Außendurchmesser fragt der Baustein
    # nicht: Gebaut wird nur das Loch, und ein Feld ohne Wirkung steht nicht da.
    hole: float = param(
        title=_("Bohrung"),
        default=8.0,
        unit="mm",
        minimum=SMALLEST_THREAD,
        maximum=LARGEST_THREAD,
        depends_on=("size", (CUSTOM_SIZE,)),
        doc=_(
            "Das Einbauloch aus dem Datenblatt der Buchse — enger als ihr Außendurchmesser, "
            "damit sie beim Einpressen Material verdrängt."
        ),
    )
    length: float = param(
        title=_("Länge"),
        default=12.7,
        unit="mm",
        minimum=1.0,
        maximum=200.0,
        depends_on=("size", (CUSTOM_SIZE,)),
        doc=_("Länge der Buchse aus ihrem Datenblatt. Die Zusatztiefe kommt dazu."),
    )
    # Hinter der Klappe, seit vorn Bohrung und Länge eines eigenen Maßes stehen:
    # Die Fase ist eine Feinheit mit richtiger Vorgabe, und drei Felder vorn
    # sind die Regel (``test_interface_limits``).
    lead_in: bool = param(
        title=_("Einführfase"),
        default=True,
        placement="advanced",
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
    # Weiter als jedes Tabellenloch: Welche Buchse dort hineingehört, sagt nur
    # ihr Datenblatt — vorgewählt wird nichts, der Satz nennt das eigene Maß.
    return {}


def size_for_nut_trap(diameter: float) -> dict[str, Any]:
    """Die kleinste Mutter, deren Durchgangsloch die Bohrung noch aufnimmt.

    Dasselbe Verhältnis wie bei der Buchse: Das Schraubenloch der Falle tritt
    an die Stelle der vorhandenen Bohrung. Ein kleineres verschwände darin, und
    die Mutter säße in einem Loch, das weiter ist als ihr eigenes.

    Weiter als das Durchgangsloch der größten Mutter ist es dieselbe Regel mit
    eigenem Maß: der kleinste Nenndurchmesser, dessen abgeleitetes
    Durchgangsloch die Bohrung aufnimmt (:func:`custom_nut_for`).
    """
    for size in standards.screw_sizes():
        if standards.screw(size).clearance >= diameter:
            return {"size": size}
    nominal = custom_nut_for(diameter)
    return {} if nominal is None else {"size": CUSTOM_SIZE, "diameter": nominal}


def custom_nut_for(bore: float) -> float | None:
    """Der kleinste eigene Nenndurchmesser, dessen Durchgangsloch diese Bohrung ist.

    Jenseits der Tabelle wächst das abgeleitete Durchgangsloch im Verhältnis
    der größten Normgröße mit (M64: 70 auf 64), die Umkehrung ist also ein
    Dreisatz. ``None`` über dem größten Gewinde.
    """
    largest = standards.screw(standards.screw_sizes()[-1])
    nominal = bore * largest.nominal / largest.clearance
    if nominal <= largest.nominal or nominal > LARGEST_THREAD:
        return None
    return nominal


def _gripped_up_to(screw: standards.Screw) -> float:
    """Die weiteste Bohrung, in der das Innengewinde dieser Größe noch trägt.

    Das Nennmaß abzüglich des Anteils ``units.THREAD_MIN_GRIP_SHARE`` der
    Gangtiefe auf beiden Seiten — darüber fasst der Gang zu wenig Wand.
    """
    return screw.nominal - 2.0 * shapes.RIDGE_SHARE * screw.pitch * THREAD_MIN_GRIP_SHARE


def _printed_root(screw: standards.Screw) -> float:
    """Der Gangfuß des gedruckten Innengewindes dieser Größe: Nennmaß minus zwei Gangtiefen.

    Die engste Bohrung, die das Gewinde ohne Aufbohren nimmt — an derselben
    Stelle misst :func:`custom_thread_for` das eigene Maß und
    :func:`thread_at_hole` das Aufbohren (Review P2, M1). Das ISO-Bohrermaß
    ``tap`` = D - P liegt ein Zehntel der Steigung darüber.
    """
    return screw.nominal - 2.0 * shapes.RIDGE_SHARE * screw.pitch


def size_for_thread(diameter: float) -> dict[str, Any]:
    """Das Innengewinde, das in eine Bohrung dieses Durchmessers geschnitten
    werden kann — die größte Tabellengröße, sonst ein eigenes Maß.

    Für eine Tabellengröße zwei Schranken, beide fachlich und keine geratene
    Toleranz: Die Bohrung ist mindestens der Gangfuß des gedruckten Gewindes
    (:func:`_printed_root`), sonst bohrte es auf, und sie lässt dem Gang
    mindestens den Anteil ``units.THREAD_MIN_GRIP_SHARE`` seiner Tiefe
    (:func:`_gripped_up_to`, Review RM-532 Runde 2, K-N6) — knapp unter dem
    Nennmaß griffe der gedruckte Bolzen nicht. Eine Ø 6,5-Bohrung bekommt
    deshalb keine Tabellengröße — für M6 ist sie zu weit, für M8 zu eng —,
    sondern das eigene Maß Ø 7,6 x 1, dessen Kernloch sie ist.

    **Ein eigenes Maß, das eine Tabellengröße trifft, ist diese** (Review P2,
    M1): Knapp unter dem Gangfuß einer Größe läge es weniger als
    ``standards.THREAD_SIZE_REACH`` neben ihr — Ø 40 ergäbe 44,95 x 4,5, eine
    M45 bis auf 0,05 mm. Dort gilt die Normgröße, wie beim Gegenstück eines
    gemessenen Gewindes, und :func:`thread_at_hole` meldet das Aufbohren —
    sofern ihr Gang in dieser Bohrung greift; an der M1.6-Kante (Ø 1,408 bis
    1,415) bleibt das eigene Maß.

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

    **Und wo keine Tabellengröße passt, passt ein eigenes Maß**
    (:func:`custom_thread_for`): zwischen zwei Größen und über M64. Ohne Größe
    bleibt nur eine Bohrung, die enger ist als das Kernloch des kleinsten
    Gewindes (Ø 1,215), oder eine, deren Gewinde größer als
    ``units.LARGEST_THREAD`` würde (über 993,4).
    """
    fitting = [
        size
        for size in standards.screw_sizes()
        if _printed_root(standards.screw(size)) <= diameter + EPS_GEOM
        and diameter <= _gripped_up_to(standards.screw(size))
    ]
    if fitting:
        return {"size": fitting[-1], "internal": True}
    custom = custom_thread_for(diameter)
    if custom is None:
        return {"internal": True}
    near = standards.thread_size_near(*custom)
    # Die Rundung nimmt die Normgröße nur, wo ihr Gang noch greift: An der
    # M1.6 ist ``THREAD_SIZE_REACH`` weiter als 0,55 der Steigung, und Ø 1,41
    # bekäme eine M1.6, deren Gang nicht in die Wand reicht (Review P2 N3).
    if near is not None and diameter <= _gripped_up_to(standards.screw(near)):
        return {"size": near, "internal": True}
    # Die Steigung bleibt auf „automatisch": Das Maß ist so gewählt, dass die
    # Regelsteigung seines Durchmessers genau die ist, mit der es gerechnet wurde.
    return {"size": CUSTOM_SIZE, "diameter": custom[0], "pitch": 0.0, "internal": True}


def _too_wide_for(diameter: float) -> str | None:
    """Die Tabellengröße, deren Nennmaß diese Bohrung hat, die ihr aber zu weit ist.

    An Ø 3, 6, 8 und 10 erwartet man M3 bis M10; der Gang einer solchen Größe
    läge nicht mehr zur Hälfte in der Wand (:func:`_gripped_up_to`). Der Satz
    über dem Dialog nennt sie, damit niemand rätselt, wo das M6 blieb.
    """
    wide = [
        size
        for size in standards.screw_sizes()
        if _gripped_up_to(standards.screw(size)) < diameter
        and diameter <= standards.screw(size).nominal + EPS_GEOM
    ]
    return wide[-1] if wide else None


def custom_thread_for(bore: float) -> tuple[float, float] | None:
    """Das Innengewinde mit eigenem Maß, dessen Kernloch diese Bohrung ist.

    **Kernloch heißt hier der Gangfuß des Druckprofils, nicht das ISO-Kernloch.**
    Die Tabelle führt als ``tap`` den Bohrer (M6: 5,0 = D - P); ein Normgewinde
    nach ISO 68-1 hätte den Kerndurchmesser D - 1,0825 P. Das eigene Maß legt
    die Bohrung genau auf den Fuß seines gedruckten Gangs (D - 2 · ``RIDGE_SHARE``
    · P = D - 1,1 P): volle Gangtiefe in der Wand, und Bolzen und Mutter aus
    Solidon gehen zusammen. Eine Metallschraube soll es ohnehin nicht tragen
    (``caveat``); wo ein ISO-Kernloch gebohrt ist, trifft die Bohrung seit
    Tabellenversion 13 eine Tabellengröße bis M64. Der Satz über dem Dialog
    sagt, dass es kein Normgewinde ist (:func:`thread_advice`).

    Die Gangtiefe hängt an der Steigung und die Regelsteigung am Nennmaß,
    deshalb wird bis zur Ruhe nachgerechnet — Ø 60 nimmt erst die 5,5 mm der
    M56, kommt damit auf Ø 66,05, dort gilt die 6 der M64, und Ø 66,6 mit
    Steigung 6 bleibt stehen. Die Regelsteigung steigt nur und ist begrenzt,
    die Schleife endet also nach höchstens so vielen Runden, wie die Reihe
    Stufen hat. ``None``, wo selbst das kleinste Gewinde nicht hineinpasst.
    """
    pitch = standards.regular_pitch(bore)
    while True:
        nominal = bore + 2.0 * pitch * shapes.RIDGE_SHARE
        following = standards.regular_pitch(nominal)
        if following <= pitch:
            break
        pitch = following
    if nominal < SMALLEST_THREAD or nominal > LARGEST_THREAD:
        return None
    return nominal, pitch


def insert_advice(diameter: float) -> TranslatableText:
    """Der Satz über der Bohrung für die Einpressbuchse — dieselbe Größe wie
    :func:`size_for_insert`.

    Der allgemeine Satz nannte die Schraube, deren Durchgangsloch die Bohrung
    ist: An 5,20 mm stand „Passt vermutlich zu M5“, vorgewählt war die Buchse
    M4, deren Einpressloch die Bohrung aufweitet.
    """
    size = size_for_insert(diameter).get("size")
    if size is None:
        return _(
            "Keine Buchse der Normteiltabelle hat ein so weites Loch; ihre Maße unter "
            "„Eigenes Maß“ eintragen."
        )
    return _(
        "Passend ist die Einpressbuchse {size}; ihr Einpressloch weitet diese Bohrung auf.",
        size=size,
    )


def nut_trap_advice(diameter: float) -> TranslatableText:
    """Der Satz über der Bohrung für die Mutternfalle — dieselbe Größe wie
    :func:`size_for_nut_trap`; ein eigenes Maß nennt er abgeleitet."""
    values = size_for_nut_trap(diameter)
    size = values.get("size")
    if size == CUSTOM_SIZE:
        return _(
            "Passend ist eine Mutter mit eigenem Maß Ø {diameter}, abgeleitet und nicht genormt.",
            diameter=format_length(values["diameter"]),
        )
    if size is None:
        return _(
            "Keine Mutter passt: Das Schraubenloch ist weiter als das des größten Gewindes "
            "mit Ø {largest}.",
            largest=format_length(LARGEST_THREAD),
        )
    return _("Passend ist die Mutter {size}; ihr Schraubenloch nimmt diese Bohrung auf.", size=size)


def thread_advice(diameter: float) -> TranslatableText:
    """Der Satz über der Bohrung für das Innengewinde — dieselbe Größe wie
    :func:`size_for_thread`.

    Über *Druckbares Gewinde* stand „Passt vermutlich zu M5 (Durchgangsloch
    fein)“ und darunter die Vorauswahl M6 (Handbuchbild *Ein Gewinde in eine
    Bohrung*, 4). Beides stimmte, aber der Satz sprach von einem Durchgangsloch,
    und in eine 5,2-mm-Bohrung passt ein **Innengewinde** M6: Kernloch 5,0 mm
    darunter, Nennmaß 6 mm darüber. Wo keine Tabellengröße passt, nennt der
    Satz das eigene Maß, das :func:`size_for_thread` vorwählt, und dass es kein
    Normgewinde ist; eine Absage bleibt unter dem kleinsten Gewinde und dort, wo
    das Gewinde größer als ``units.LARGEST_THREAD`` würde. Ein eigenes Maß, das
    eine Tabellengröße trifft, gibt es hier nicht (:func:`size_for_thread`);
    hat die Bohrung das Nennmaß einer Größe, die ihr zu weit ist, nennt der
    Satz sie (Review P2, M1).
    """
    values = size_for_thread(diameter)
    size = values.get("size")
    if size == CUSTOM_SIZE:
        nominal, pitch = thread_measure(CUSTOM_SIZE, values["diameter"], values["pitch"])
        wide = _too_wide_for(diameter)
        if wide is not None:
            return _(
                "Für {size} zu weit, der Gang griffe nicht. Eigenes Maß: Ø {diameter}, "
                "Steigung {pitch}.",
                diameter=format_length(nominal),
                pitch=format_length(pitch),
                size=wide,
            )
        return _(
            "In diese Bohrung passt ein Innengewinde mit eigenem Maß Ø {diameter}, "
            "Steigung {pitch}, kein Normgewinde.",
            diameter=format_length(nominal),
            pitch=format_length(pitch),
        )
    if size is not None:
        return _("In diese Bohrung passt ein Innengewinde {size}.", size=size)
    if diameter > SMALLEST_THREAD:
        return _(
            "Kein Gewinde passt in diese Bohrung: Mit ihr als Kernloch wäre es größer als "
            "Ø {largest}.",
            largest=format_length(LARGEST_THREAD),
        )
    return _(
        "Kein Gewinde passt: Die Bohrung ist enger als das Kernloch des kleinsten mit "
        "Ø {smallest}.",
        smallest=format_length(SMALLEST_THREAD),
    )


#: Wie viele Strahlen je Messring die Wand um ein Gewinde messen — eine Zahl für
#: die Bausteine und *Merkmal ändern* (``prepare_ops._thread_wall``): 24 Richtungen
#: treffen die Seitenwände eines Quaders senkrecht. Dazu, an welchen Anteilen der
#: Bohrungslänge hier gemessen wird.
THREAD_WALL_RAYS: Final = 24
_WALL_RINGS: Final = (0.15, 0.5, 0.85)


def thread_at_hole(
    raw: BaseParams,
    bore: Feature,
    host: Any,
    profile: Profile | None,
    mouth: Vec3 | None = None,
    outward: Vec3 | None = None,
) -> list[Finding]:
    """Was ein Innengewinde über seine Bohrung sagt: Restwand und Aufbohren, beides.

    **Die Restwand** (Review RM-532, F2): An einem Rohr ist die Außenwand kein
    Merkmal, die Prüfung am Endstand (``relations.thinnest_sleeve``) sieht sie
    nicht. Gemessen wird deshalb hier, mit Strahlen quer zur Achse am Träger
    vor dem Schnitt, auf der Strecke, die das Gewinde von der Mündung
    (``mouth``) gegen ``outward`` einnimmt: Der erste Austritt jenseits der
    Bohrung ist die Außenwand, und was zwischen ihr und dem Grund des Gangs
    bleibt, muss die Mindestwand des Materials tragen. Ein Rohr 65/60 mit der
    M64 behielt 0,4 mm, ohne ein Wort. Die Wand hängt am Außenmaß des Gangs,
    nicht an der Steigung — der Rat nennt deshalb das kleinere Nennmaß
    (Review RM-532 Runde 2, N2).

    **Das Aufbohren** (Review RM-532, F3): An der Bohrung wählt
    :func:`size_for_thread` ein Maß, dessen Kernloch sie ist. Wer danach nur die
    Steigung feiner stellt, behält den Nenndurchmesser und damit die Tiefe in
    der Wand; das Werkzeug beginnt aber bei Nennmaß minus zwei Gangtiefen, und
    das liegt nun über der Bohrung: An einem Rohr 72/60 wurde Ø 66,6 mit
    Steigung 2 auf 64,6 aufgebohrt, 2358 mm³ mehr Abtrag. Gemeldet wird, sobald
    das Werkzeug die Bohrung um mehr als das Spiel übersteigt; der Satz nennt
    den Nenndurchmesser, mit dem sie bei dieser Steigung Kernloch bleibt.

    Beide Befunde öffnen den Schritt an dem Feld, das das Maß trägt: bei
    *Eigenes Maß* am Nenndurchmesser, sonst an der Größe.
    """
    params = cast(ThreadParams, raw)
    if not params.internal:
        return []
    own = params.size == CUSTOM_SIZE
    nominal, pitch = thread_measure(params.size, params.diameter, params.pitch)
    hole = float(bore.params["diameter"])
    depth = pitch * shapes.RIDGE_SHARE
    found: list[Finding] = []
    wall = _wall_around(bore, host, mouth, outward, params.length)
    least = profile.minimum_wall_thickness if profile is not None else None
    if wall is not None and least is not None:
        left = wall - (nominal + params.play) / 2.0
        if left < least - EPS_GEOM:
            message = _(
                "Um das Gewinde bleiben {wall} Wand, das Material braucht {least}. Ein "
                "kleineres Nennmaß mit feinerer Steigung oder ein dickeres Teil wählen.",
                wall=format_length(max(left, 0.0)),
                least=format_length(least),
            )
            found.append(
                Finding(
                    code="parts.thread_thin_wall",
                    severity="warning",
                    message=message,
                    values={
                        "part": "printed_thread",
                        "field": "diameter" if own else "size",
                        "wall_mm": left,
                        "least_mm": least,
                    },
                    suggestions=(CHANGE_SIZE,),
                )
            )
    core = nominal - 2.0 * depth + params.play
    if core > hole + params.play + EPS_GEOM:
        fitting = hole + 2.0 * depth
        message = _(
            "Das Gewinde bohrt die Bohrung von {bore} auf {core} auf. Mit Steigung {pitch} "
            "bliebe sie Kernloch für Ø {fitting}.",
            bore=format_length(hole),
            core=format_length(core),
            pitch=format_length(pitch),
            fitting=format_length(fitting),
        )
        found.append(
            Finding(
                code="parts.bore_widened",
                severity="warning",
                message=message,
                values={
                    "part": "printed_thread",
                    "field": "diameter" if own else "size",
                    "bore_mm": hole,
                    "core_mm": core,
                    "fitting_mm": fitting,
                },
                suggestions=(CHANGE_SIZE,),
            )
        )
    return found


def _wall_around(
    bore: Feature, host: Any, mouth: Vec3 | None, outward: Vec3 | None, length: float
) -> float | None:
    """Wie weit die Außenseite des Trägers von der Achse liegt, an der engsten Stelle.

    Gemessen auf der Strecke des Gewindes, von der Mündung gegen ``outward``
    (Review RM-532 Runde 2, K-N5: um die Bohrungsmitte gemessen traf der
    Strahl an einer abgesetzten Wand die falsche Stelle). Ohne Mündung um die
    Mitte der Bohrung.
    """
    import numpy as np

    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare import ray_hits_along
    from app.core.perceive.features import axis_of, centre_of
    from app.core.sketch.planes import frame_of
    from app.core.units import MAX_FACET_SAG, circle_point

    if host is None:
        return None
    if mouth is not None and outward is not None:
        axis = np.asarray(outward, dtype=np.float64)
        origins = [
            np.asarray(mouth, dtype=np.float64) - axis * (share * length) for share in _WALL_RINGS
        ]
    else:
        stated, centre = axis_of(bore), centre_of(bore)
        if stated is None or centre is None:
            return None
        axis = np.asarray(stated, dtype=np.float64)
        depth = float(bore.params.get("depth") or 0.0)
        origins = [
            np.asarray(centre, dtype=np.float64) + axis * ((share - 0.5) * depth)
            for share in _WALL_RINGS
        ]
    mesh = as_mesh_data(host)
    triangles = np.asarray(mesh.raw.triangles, dtype=np.float64)
    normals = np.asarray(mesh.raw.face_normals, dtype=np.float64)
    frame = frame_of((float(axis[0]), float(axis[1]), float(axis[2])), (0, 0, 0))
    across = np.asarray(frame.x_axis, dtype=np.float64), np.asarray(frame.y_axis, dtype=np.float64)
    radius = float(bore.params["diameter"]) / 2.0
    reach: float | None = None
    for origin in origins:
        for index in range(THREAD_WALL_RAYS):
            cosine, sine = circle_point(THREAD_WALL_RAYS, index)
            way = across[0] * cosine + across[1] * sine
            distances, hit = ray_hits_along(triangles, origin, way)
            facing = (normals[hit] * way).sum(axis=1)
            exits = distances[(facing > 0.0) & (distances > radius + MAX_FACET_SAG)]
            if len(exits):
                nearest = float(exits.min())
                reach = nearest if reach is None else min(reach, nearest)
    return reach


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
        "Ohne Lötkolben, denn die Buchse wird warm eingepresst und sprengt kalt die Wand. Dann "
        "trägt eine Mutternfalle ähnlich viel."
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
    if params.size == CUSTOM_SIZE:
        hole, length = params.hole, params.length
    else:
        entry = standards.insert(params.size)
        hole, length = entry.hole, entry.length
    depth = length + params.extra_depth

    shaft = shapes.cylinder(hole, depth + BOOLEAN_OVERLAP)
    shaft = shapes.moved(shaft, (0.0, 0.0, -depth))
    parts = [shaft]
    features = [
        bore("bore_1", hole, (0.0, 0.0, -depth / 2.0), depth=depth),
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
        lead = shapes.cone(hole, hole + 2.0 * chamfer, chamfer)
        parts.append(shapes.moved(lead, (0.0, 0.0, -chamfer)))
        features.append(
            bore("chamfer_1", hole + 2.0 * chamfer, (0.0, 0.0, -chamfer / 2.0), depth=chamfer)
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
        choices=(*_NUTS, CUSTOM_SIZE),
        doc=_(
            "Gewinde der Mutter. Schlüsselweite und Höhe kommen aus der Normteiltabelle, bei "
            "„Eigenes Maß“ aus den Normgrößen daneben."
        ),
    )
    diameter: float = _nominal_param(_DERIVED_NOMINAL_DOC, placement="advanced")
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
        "Ohne passende Sechskantmutter, denn die Tasche folgt der Normteiltabelle. Die Mutter "
        "muss erreichbar bleiben, auch nach späteren Schritten."
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
    entry = _nut_of(params.size, params.diameter)
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
        screw = _screw_of(params.size, params.diameter)
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
    return _derived(result(body, *features), params.size, params.diameter)


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


#: Version 24 betrifft drei Bausteine mit derselben Ursache: das Netz ihres
#: Gewindes (``build.threaded``). Ein gemeinsamer Eintrag, wie
#: ``PLAY_FROM_PROFILE``.
THREAD_MESH_WHOLE_TURNS = PartChange(
    version="24",
    date="2026-10-06",
    reason=(
        "Am Netz lief der Gang über eine krumme Zahl von Umläufen, und ab M12 endete der Kern "
        "in der Sehnenmitte unter dem Fuß des Gangs: Gedruckte Schraube und Mutter überdeckten "
        "sich dort, bei M20 um 0,27 mm³ (RM-532)."
    ),
    effect=_(
        "Das Gewinde wird über ganze Umläufe gebaut und auf Länge geschnitten, die Maße "
        "bleiben, nur das Netz ändert sich."
    ),
)


@op_params
class ThreadParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M6",
        choices=(*_SCREWS, CUSTOM_SIZE),
        doc=_(
            "Nenndurchmesser und Steigung. Das Profil ist druckbar abgeflacht, "
            "kein ISO-Profil — das löst ein Drucker ohnehin nicht auf."
        ),
    )
    # **Ein Gewinde endete bei M8**, weil die Größe nur aus der Schraubentabelle
    # kam (Kundenvorschlag S-20261006-c66299: ein Innengewinde in einem Rohr
    # mit 60 mm). „Eigenes Maß" nimmt jeden Durchmesser; die Steigung steht
    # hinten, denn ohne Angabe nimmt sie die Regelsteigung des Durchmessers.
    diameter: float = param(
        title=_("Nenndurchmesser"),
        default=20.0,
        unit="mm",
        minimum=SMALLEST_THREAD,
        maximum=LARGEST_THREAD,
        depends_on=("size", (CUSTOM_SIZE,)),
        doc=_(
            "Der Durchmesser über die Gänge, wie die Zahl hinter dem M. Ein Innengewinde "
            "nimmt einen Bolzen dieses Durchmessers auf."
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
    pitch: float = param(
        title=_("Steigung"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=COARSEST_PITCH,
        placement="advanced",
        depends_on=("size", (CUSTOM_SIZE,)),
        doc=_(
            "Höhenzuwachs je Umdrehung, null nimmt die Regelsteigung des Durchmessers. Eine "
            "feinere Steigung schneidet nur mit kleinerem Nenndurchmesser weniger tief in die "
            "Wand."
        ),
        zero_text=ZERO_AUTOMATIC,
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
    at_hole_check=thread_at_hole,
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
        "Wo eine Metallschraube greifen soll, denn der Kamm ist für den Drucker abgeflacht. Für "
        "tragende Verschraubungen eine Einpressbuchse oder Mutternfalle."
    ),
    changes=[
        FIRST_RELEASE,
        PLAY_FROM_PROFILE,
        FACE_GIVES_DIRECTION,
        THREAD_CUTS_INWARD,
        PRINTED_THREAD_ROOT_OVERLAPS_CORE,
        THREAD_PROFILES_MATCH,
        THREAD_OPENS_AT_BOTH_ENDS,
        THREAD_MESH_WHOLE_TURNS,
    ],
    feasible=lambda raw: _thread_reason(cast(ThreadParams, raw)),
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
    nominal, pitch = thread_measure(params.size, params.diameter, params.pitch)
    return _printed_thread(nominal, pitch, params.length, params.internal, params.play)


def thread_measure(size: str, diameter: float = 0.0, pitch: float = 0.0) -> tuple[float, float]:
    """Nenndurchmesser und Steigung eines Bausteingewindes: aus der Tabelle oder eigen.

    Bei :data:`CUSTOM_SIZE` gelten ``diameter`` und ``pitch``; eine Steigung
    von null ist die Regelsteigung des Durchmessers
    (``standards.regular_pitch``), wie sie ein Normgewinde dieser Größe hätte.
    """
    if size != CUSTOM_SIZE:
        screw = standards.screw(size)
        return screw.nominal, screw.pitch
    return diameter, pitch if pitch > 0.0 else standards.regular_pitch(diameter)


THREAD_WITHOUT_CORE = _(
    "Bei diesem Durchmesser lassen Steigung und Spiel keinen tragenden Gewindekern stehen. "
    "Eine feinere Steigung, einen größeren Durchmesser oder weniger Spiel wählen."
)


def thread_problem(nominal: float, pitch: float, play: float) -> ValidationError | None:
    """Warum ein Gewinde dieses Maßes nicht gebaut wird — oder ``None``.

    **Die eine Regel für Bau, Erklärung und Gegenstück** (``_printed_thread``,
    ``_thread_reason``, ``counterpart.thread_values_for``). Zwei Absagen:

    * eine Steigung feiner als ``units.FINEST_PITCH``: Darunter wächst das Netz
      ohne Grenze, und der Bau nimmt keinen Abbruch entgegen;
    * ein Bolzen ohne tragenden Kern: Geprüft wird **der Bolzen des Maßes**,
      auch für ein Innengewinde, denn eines, zu dem es keinen Bolzen gibt, hat
      kein Gegenstück. Sein Kern — Nennmaß minus Spiel minus zwei Gangtiefen —
      muss mehr als ``units.THREAD_MIN_CORE_SHARE`` seines Außenmaßes behalten,
      dieselbe Regel wie bei *Schraube erstellen*. Bis zum 06.10.2026 genügte
      hier jeder Kern über 10⁻⁶ mm: Ø 2 x 1,6 baute einen Bolzen mit 0,04 mm
      Kern.
    """
    if 0.0 < pitch < FINEST_PITCH - EPS_GEOM:
        return ValidationError(
            "pitch",
            _(
                "Feiner als {finest} Steigung baut kein Gewinde. Eine gröbere Steigung wählen "
                "oder null für die Regelsteigung des Durchmessers.",
                finest=format_length(FINEST_PITCH),
            ),
            values={"minimum": FINEST_PITCH, "pitch": pitch},
            constraint="finest_pitch",
        )
    major = nominal - play
    if major - 2.0 * pitch * shapes.RIDGE_SHARE <= THREAD_MIN_CORE_SHARE * major:
        return ValidationError(
            "pitch",
            THREAD_WITHOUT_CORE,
            values={
                "maximum": max(major, 0.0)
                * (1.0 - THREAD_MIN_CORE_SHARE)
                / (2.0 * shapes.RIDGE_SHARE),
                "pitch": pitch,
                "play": play,
            },
            constraint="no_core",
        )
    return None


def _thread_reason(params: ThreadParams) -> TranslatableText | str | None:
    """Die erklärte Bedingung des Gewindes, aus derselben Regel wie der Bau.

    Der Bereichsnachweis zählte ``Ø 2`` mit 20 mm Steigung als Bruch, obwohl der
    Bau dort richtig ablehnte — die Absage war nur nicht erklärt (Review RM-532,
    F1).
    """
    nominal, pitch = thread_measure(params.size, params.diameter, params.pitch)
    problem = thread_problem(nominal, pitch, params.play)
    return None if problem is None else problem.detail


def _printed_thread(
    nominal: float,
    pitch: float,
    length: float,
    internal: bool,
    play: float,
    *,
    bottom: float | None = None,
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
    problem = thread_problem(nominal, pitch, play)
    if problem is not None:
        raise problem
    # Das Innenwerkzeug ist Kern plus Spiel, und die Nut reicht von dort
    # hinaus; der Bolzen ist das Nennmaß minus Spiel.
    depth = pitch * shapes.RIDGE_SHARE
    diameter = nominal - 2.0 * depth + play if internal else nominal - play
    built = length
    if bottom is None:
        bottom = -length if internal else 0.0
        # Das Werkzeug reicht ein Hundertstel über die Mündung hinaus (§39); der
        # Gang beginnt trotzdem unten, die Phase hängt an ``bottom``.
        built = length + BOOLEAN_OVERLAP if internal else length

    # Kern plus Gang, auf Länge geschnitten — wie das entsteht, weiß ``build``
    # je Kern; die Maße stehen hier.
    body = threaded(diameter, pitch, built, internal=internal, bottom=bottom)
    return result(
        body,
        _thread_feature(nominal, pitch, play, (0.0, 0.0, bottom + length / 2.0), internal, length),
    )


def _thread_feature(
    nominal: float,
    pitch: float,
    play: float,
    centre: tuple[float, float, float],
    internal: bool,
    length: float,
) -> tuple[str, Feature]:
    """Das Merkmal eines gedruckten Gewindes: das gebaute Maß und das Nennmaß daneben.

    Jede Hälfte steht um das Spiel neben dem Nennmaß — die Mutter weiter, der
    Bolzen enger (:func:`_printed_thread`), ein gedrucktes Paar hat es also
    zweimal. Nannte das Merkmal das Nennmaß, maß die Gewindepassung eines
    frischen Paars 0,00 mm und meldete es als zu eng; ein eingelesenes
    Gewinde nennt ohnehin, was gebaut ist.

    Das Nennmaß steht als ``nominal`` daneben: Die Passungsprüfung weiß daran,
    dass diese Hälfte das Spiel des Materials trägt (``fits._thread_wanted``),
    und das Gegenstück findet sein Maß (``counterpart.thread_values_for``).
    """
    identifier, feature = thread(
        "thread_1",
        nominal + play if internal else nominal - play,
        pitch,
        centre,
        internal=internal,
        length=length,
    )
    return identifier, replace(
        feature,
        params={**feature.params, "nominal": nominal},
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
        choices=(*_SCREWS, CUSTOM_SIZE),
        doc=_("Nenndurchmesser und Steigung des passenden gedruckten Gewindes."),
    )
    diameter: float = _nominal_param(
        _(
            "Der Durchmesser, wie die Zahl hinter dem M; die Steigung ist die Regelsteigung "
            "dazu. Ohne Normgröße ist der Kopf aus den Normgrößen daneben abgeleitet."
        ),
        placement="advanced",
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
    standalone=True,
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
        "Für hohe Lasten oder häufiges Lösen. Dafür halten Metallschrauben mit Mutternfalle oder "
        "Heat-Set-Buchse besser."
    ),
    changes=[
        PRINTED_FASTENERS,
        PRINTED_SCREW_PREPARES_COUNTERSINK,
        PRINTED_SCREW_GEOMETRY_FIXED,
        THREAD_PROFILES_MATCH,
        THREAD_OPENS_AT_BOTH_ENDS,
        SEPARATE_PARTS_KEEP_THEIR_PLAY,
        THREAD_MESH_WHOLE_TURNS,
    ],
)
def printed_screw(raw: BaseParams) -> PartResult:
    """Eine Schraube, deren Gewinde und Kopf an derselben Bohrung sitzen."""
    params = cast(PrintedScrewParams, raw)
    screw = _screw_of(params.size, params.diameter)
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
        # Mit eigenem Maß ist der Kopf über die Flächen eine Schlüsselweite der
        # Reihe, keine gerechnete Zwischengröße (Review RM-532 Runde 2, K-N2).
        across = standards.wrench_size(screw.head) if params.size == CUSTOM_SIZE else screw.head
        head = shapes.moved(shapes.hexagon(across, screw.head_height), (0.0, 0.0, thread_top))

    # Die Länge meint ausdrücklich das Gewinde **unter** dem Kopf. Beim
    # Senkkopf ist dessen schmale Spitze die Trennstelle; z = 0 ist dagegen
    # der breite, bündige Rand. Vorher endete das Gewinde ebenfalls bei null
    # und lag damit um die ganze Kopfhöhe im Kopf. Bei kurzen Schrauben blieb
    # kein Gang außerhalb des Kegels, bei langen zerfiel die Vereinigung an
    # einzelnen Normgrößen. Ein kleiner Überstand verbindet beide Körper
    # robust, ohne das zugesagte Längenmaß sichtbar zu verändern.
    shank = form_of(
        _printed_thread(
            screw.nominal,
            screw.pitch,
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
    made = result(
        body,
        _thread_feature(
            screw.nominal,
            screw.pitch,
            params.play,
            (0.0, 0.0, thread_top - params.length / 2.0),
            False,
            params.length,
        ),
    )
    return _derived(made, params.size, params.diameter)


def _printed_screw_countersink(raw: BaseParams) -> PartResult | None:
    """Die zum gewählten Senkkopf passende Vorbereitung des Trägers."""
    params = cast(PrintedScrewParams, raw)
    if not params.countersunk:
        return None

    screw = _screw_of(params.size, params.diameter)
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
        choices=(*_NUTS, CUSTOM_SIZE),
        doc=_("Nenndurchmesser und Steigung des passenden gedruckten Gewindes."),
    )
    diameter: float = _nominal_param(
        _(
            "Der Durchmesser, wie die Zahl hinter dem M; die Steigung ist die Regelsteigung "
            "dazu. Ohne Normgröße sind Schlüsselweite und Höhe aus den Normgrößen daneben "
            "abgeleitet."
        )
    )
    play: float = play_param()


@register_part(
    name="printed_nut",
    standalone=True,
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
        "Für hohe Lasten oder häufiges Lösen. Dafür halten Metallschrauben mit Mutternfalle oder "
        "Heat-Set-Buchse besser."
    ),
    changes=[
        PRINTED_FASTENERS,
        PRINTED_THREAD_ROOT_OVERLAPS_CORE,
        THREAD_PROFILES_MATCH,
        THREAD_OPENS_AT_BOTH_ENDS,
        SEPARATE_PARTS_KEEP_THEIR_PLAY,
        THREAD_MESH_WHOLE_TURNS,
    ],
)
def printed_nut(raw: BaseParams) -> PartResult:
    """Eine Sechskantmutter, deren Innengewinde zum gedruckten Bolzen passt."""
    params = cast(PrintedNutParams, raw)
    nut = _nut_of(params.size, params.diameter)
    depth = nut.height + 2.0 * BOOLEAN_OVERLAP
    # Wie der Schraubenkopf steht die Mutter um das Spiel über der Fläche, auf
    # der sie sitzt (RM-276): Ohne Abstand verschweißte sie an Ort und Stelle
    # gedruckt mit dem Träger.
    lift = params.play
    # Das Werkzeug reicht ein Hundertstel unter den Boden und über die Decke hinaus.
    screw = _screw_of(params.size, params.diameter)
    cutter = form_of(
        _printed_thread(
            screw.nominal,
            screw.pitch,
            depth,
            internal=True,
            play=params.play,
            bottom=lift - BOOLEAN_OVERLAP,
        )
    )
    body = subtract(shapes.moved(shapes.hexagon(nut.width, nut.height), (0.0, 0.0, lift)), cutter)
    made = result(
        body,
        _thread_feature(
            screw.nominal,
            screw.pitch,
            params.play,
            (0.0, 0.0, lift + nut.height / 2.0),
            True,
            nut.height,
        ),
    )
    return _derived(made, params.size, params.diameter)


#: Das kürzeste Gewinde an einem Bolzenende — dieselbe Untergrenze wie die Länge
#: von *Druckbares Gewinde* (``ThreadParams.length``).
_SHORTEST_ROD_THREAD: Final = 2.0

THREADED_ROD_ADDED: Final = PartChange(
    version="1",
    date="2026-10-08",
    reason=(
        "Gewindebolzen als eigenes Teil (Robert, 08.10.2026, zu RM-562): Gewindestange oder "
        "Stiftschraube ohne Kopf, aus dem Katalog als eigener Körper."
    ),
)


@op_params
class ThreadedRodParams(BaseParams):
    size: str = param(
        title=_("Größe"),
        default="M6",
        choices=(*_SCREWS, CUSTOM_SIZE),
        doc=_("Nenndurchmesser und Steigung des passenden gedruckten Gewindes."),
    )
    diameter: float = _nominal_param(
        _(
            "Der Durchmesser über die Gänge, wie die Zahl hinter dem M. Ein Innengewinde "
            "nimmt einen Bolzen dieses Durchmessers auf."
        ),
        placement="advanced",
    )
    pitch: float = param(
        title=_("Steigung"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=COARSEST_PITCH,
        placement="advanced",
        depends_on=("size", (CUSTOM_SIZE,)),
        doc=_(
            "Höhenzuwachs je Umdrehung, null nimmt die Regelsteigung des Durchmessers. Eine "
            "feinere Steigung schneidet nur mit kleinerem Nenndurchmesser weniger tief in die "
            "Wand."
        ),
        zero_text=ZERO_AUTOMATIC,
    )
    length: float = param(
        title=_("Länge"),
        default=30.0,
        unit="mm",
        minimum=4.0,
        maximum=200.0,
        doc=_("Länge des ganzen Bolzens, von Ende zu Ende."),
    )
    thread_length: float = param(
        title=_("Gewindelänge"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=90.0,
        doc=_(
            "Länge des Gewindes an jedem Ende, mit glattem Schaft dazwischen wie bei einer "
            "Stiftschraube. Null heißt: durchgehend wie eine Gewindestange."
        ),
        zero_text=ZERO_THROUGH,
    )
    chamfer: float = param(
        title=_("Fase"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=3.0,
        placement="advanced",
        doc=_(
            "Höhe der Kuppe an beiden Enden, unter 45 Grad bis auf den Kern. Null heißt: so "
            "hoch, wie ein Gang tief ist."
        ),
        zero_text=ZERO_AUTOMATIC,
    )
    play: float = play_param()


def _rod_chamfer(chosen: float, pitch: float) -> float:
    """Die Höhe der Kuppe: eingetragen, sonst so hoch, wie ein Gang tief ist."""
    return chosen or pitch * shapes.RIDGE_SHARE


def _rod_reason(raw: BaseParams) -> TranslatableText | str | None:
    """Was zwischen den Maßen des Bolzens nicht geht — dieselben Regeln wie im Bau."""
    params = cast(ThreadedRodParams, raw)
    nominal, pitch = thread_measure(params.size, params.diameter, params.pitch)
    problem = thread_problem(nominal, pitch, params.play)
    if problem is not None:
        return problem.detail
    chamfer = _rod_chamfer(params.chamfer, pitch)
    core = nominal - params.play - 2.0 * pitch * shapes.RIDGE_SHARE
    if chamfer > core / 4.0:
        return _(
            "Die Fase von {chamfer} ist für diesen Bolzen zu groß. Wählen Sie eine kleinere Fase.",
            chamfer=format_length(chamfer),
        )
    reach = params.thread_length or params.length / 2.0
    if params.thread_length and 2.0 * params.thread_length >= params.length:
        return _(
            "Zwei Gewinde von je {thread} passen nicht in einen Bolzen von {length}. Kürzen "
            "Sie die Gewinde oder verlängern Sie den Bolzen.",
            thread=format_length(params.thread_length),
            length=format_length(params.length),
        )
    if reach - chamfer < _SHORTEST_ROD_THREAD:
        return _(
            "Neben der Fase bleibt weniger als {shortest} Gewinde. Wählen Sie eine längere "
            "Gewindelänge, einen längeren Bolzen oder null für ein durchgehendes Gewinde.",
            shortest=format_length(_SHORTEST_ROD_THREAD),
        )
    return None


@register_part(
    name="threaded_rod",
    standalone=True,
    title=_("Gewindebolzen"),
    group="fasteners",
    params=ThreadedRodParams,
    at_face=False,
    features=["thread"],
    wall=WallRequirement.not_applicable("Die Gewindekämme werden vom massiven Kern getragen."),
    doc=_(
        "Gewindestange oder Stiftschraube ohne Kopf, mit Fase an beiden Enden. Dasselbe "
        "druckbare Profil wie Gewinde und Mutter."
    ),
    caveat=_(
        "Für hohe Lasten oder häufiges Lösen. Dafür halten Metallschrauben mit Mutternfalle oder "
        "Heat-Set-Buchse besser."
    ),
    changes=[THREADED_ROD_ADDED],
    feasible=_rod_reason,
)
def threaded_rod(raw: BaseParams) -> PartResult:
    """Ein Bolzen ohne Kopf aus demselben Gewindekern wie *Druckbares Gewinde*.

    Die Gänge baut :func:`_printed_thread` — derselbe Kamm, dasselbe Spiel,
    dieselbe Phase wie beim Gewinde auf einer Fläche und bei der Mutter, die
    darauf passt; die Normmaße kommen aus :func:`thread_measure`. Eigen ist nur,
    was einen Bolzen ausmacht: die Gesamtlänge, ein glatter Schaft zwischen zwei
    Gewinden und an beiden Enden eine kegelige Kuppe bis auf den Kern.

    **Die Fase schneidet nicht durch die Gänge.** Ein Kegel quer durch die
    Wendel tessellierte am exakten Kern je nach Größe undicht (M6, M12, M24
    gemessen); die Kuppe sitzt deshalb vor dem Gewinde und geht knapp unter dem
    Kerndurchmesser in den Kern über.
    """
    params = cast(ThreadedRodParams, raw)
    problem = _rod_reason(params)
    if problem is not None:
        raise ValidationError(
            field="thread_length" if params.thread_length else "chamfer",
            detail=problem,
            suggestions=(CHANGE_THIS_STEP,),
        )
    nominal, pitch = thread_measure(params.size, params.diameter, params.pitch)
    chamfer = _rod_chamfer(params.chamfer, pitch)
    crest = nominal - params.play
    length = params.length
    if not params.thread_length:
        runs: tuple[tuple[float, float], ...] = ((chamfer, length - 2.0 * chamfer),)
        body = form_of(
            _printed_thread(nominal, pitch, runs[0][1], False, params.play, bottom=chamfer)
        )
    else:
        reach = params.thread_length
        runs = ((chamfer, reach - chamfer), (length - reach, reach - chamfer))
        lower, upper = (
            form_of(_printed_thread(nominal, pitch, run, False, params.play, bottom=bottom))
            for bottom, run in runs
        )
        shank = shapes.moved(
            shapes.cylinder(crest, length - 2.0 * reach + 2.0 * BOOLEAN_OVERLAP),
            (0.0, 0.0, reach - BOOLEAN_OVERLAP),
        )
        body = union(lower, shank, upper)
    inner = crest - 2.0 * pitch * shapes.RIDGE_SHARE - 2.0 * BOOLEAN_OVERLAP
    tip = inner - 2.0 * chamfer
    rise = chamfer + BOOLEAN_OVERLAP
    body = union(
        shapes.cone(tip, inner, rise),
        body,
        shapes.moved(shapes.cone(inner, tip, rise), (0.0, 0.0, length - rise)),
    )
    features = [
        (
            f"thread_{index}",
            replace(
                _thread_feature(
                    nominal, pitch, params.play, (0.0, 0.0, bottom + run / 2.0), False, run
                )[1],
                id=f"thread_{index}",
            ),
        )
        for index, (bottom, run) in enumerate(runs, start=1)
    ]
    return result(body, *features)
