"""Operationen für die Druckvorbereitung (Bauplan §25).

Bohren, Teilen, Anordnen und die Kollisionsprüfung. Die letzte ändert gar
keine Geometrie — sie meldet nur, und das ist eine völlig gute Sache für eine
Operation, wenn die Alternative eine Überraschung am Drucker ist.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final, Literal, cast

import numpy as np
from numpy.typing import NDArray

from app.core import units
from app.core.deferred import trimesh
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    CHOOSE_PRINTER,
    CORRECT_INPUT,
    RECOUNT_AND_RETRY,
    REPAIR_AND_RETRY,
    RESIZE_THE_WIDENING,
    SHOW_LOCATION,
    SPLIT_AND_RETRY,
    SPLIT_MODEL,
    BooleanFailedError,
    GeometryError,
    InternalError,
    ValidationError,
)
from app.core.geom import lathe, transform
from app.core.geom.boolean import (
    BOOLEAN_OVERLAP,
    DRAFT_CHAIN,
    NOTHING_LEFT_DETAIL,
    NOTHING_LEFT_TITLE,
    BooleanKind,
    BooleanOutcome,
    boolean,
    deepest,
    shared_volume,
    without_effect,
)
from app.core.geom.hollow import VENT_DIAMETER, HollowResult, below_printable_wall, hollow
from app.core.geom.mesh import MeshData, as_mesh_data, face_components, ray_hits
from app.core.geom.ops import as_transform
from app.core.geom.orient import NoFittingOrientationError, orient_for_print, ranked_orientations
from app.core.geom.pins import (
    PIN_COUNT,
    PIN_MAX,
    FeatureSide,
    PinnedPair,
    add_pins,
    connector_glue_finding,
    feature_side,
    next_connector_index,
    plan_pins,
)
from app.core.geom.prepare import (
    BORE_SECTIONS,
    FEATURE_OVERLAP,
    MAX_PLATES,
    Arrangement,
    BoreAnchor,
    arrange_on_bed,
    bore_diameter,
    bore_geometry_error,
    check_build_volume,
    check_collisions,
    check_join_path,
    compensate_elephant_foot,
    compensation_findings,
    countersink,
    drill,
    edge_findings,
    is_round_length,
    mouth_over_the_edge,
    named_for,
    over_the_edge_along,
    plug,
    plug_placement,
    resize_bore,
    shell,
    shortest_slot,
    sink_placement,
    slot_bore,
    slot_travel,
    split_at_plane,
    split_findings,
    surface_index_of,
)
from app.core.geom.section import AXIS_NORMALS, SectionPlane, cut
from app.core.geom.transform import Axis, composed, moved_object, place_on_bed, translation
from app.core.knowledge.profiles import analysis_limits, for_object, material
from app.core.registry import VARIABLE, op_params, param, play_param, register_op
from app.core.scene.placement import SIDE_KEYS, side_of
from app.core.slice.orientation import DEFAULT_CANDIDATES, search
from app.core.types import (
    BaseParams,
    CancelToken,
    Feature,
    FeatureContinuation,
    FeatureId,
    FeatureRef,
    Finding,
    Mesh,
    OpContext,
    OpResult,
    PlaneFrame,
    Profile,
    ProgressFn,
    Quality,
    SceneObject,
    SolverInfo,
    Vec3,
    is_a_cavity,
    thread_is_left_handed,
    thread_is_tapered,
    vec3_or_none,
)
from app.core.units import (
    DEGREE_UNIT,
    EPS_DISPLAY,
    EPS_GEOM,
    MAX_FACET_SAG,
    format_length,
    is_close,
    is_zero,
)
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.perceive.patterns import Field
    from app.core.perceive.relations import CavityState

_AXES = tuple(AXIS_NORMALS)

#: Erklärungen, die für jede Bohrung dieselben sind. Einmal geschrieben, damit
#: dieselbe Zahl nicht an drei Stellen unterschiedlich erklärt wird.
_WHERE_X = _(
    "Mitte der Bohrung im Koordinatensystem des Objekts. Eine angeklickte "
    "Fläche trägt die drei Werte selbst ein."
)
_WHERE_Y = _("Zweite Achse der Position — siehe Position X.")
_WHERE_Z = _("Dritte Achse der Position — siehe Position X.")
_ALONG = _(
    "Richtung, in die gebohrt wird. Z ist senkrecht von oben, X und Y bohren durch eine Seitenwand."
)

#: Was die Position bedeutet. „mouth" ist die Vorgabe, weil eine angeklickte
#: Fläche die Mündung ist und nicht die Mitte des Lochs dahinter; „centre" gibt
#: es, weil Dateien bis Formatversion 6 es so gemeint haben.
_ANCHORS = ("mouth", "centre")

#: Was ein Verbinder sein kann. Die ersten drei sind Querschnitte: dieselbe
#: Rechnung, ein anderes Vieleck. Rund ist die Vorgabe und der einfachste
#: Druck; die kantigen sichern gegen Verdrehen, der Schwalbenschwanz zusätzlich
#: gegen Auseinanderziehen quer zur Naht.
#:
#: Der Schnapper ist kein Querschnitt, sondern ein Mechanismus mit eigenem
#: Baustein (``snap_connector``) — er steht hier trotzdem in derselben Liste,
#: weil er für den Nutzer dieselbe Entscheidung ist: *womit* halten die Hälften
#: zusammen. Wo eine Naht ihm zu schmal ist, wird rund daraus, und der
#: Prüfbericht sagt es (``split.snap_too_small``).
CONNECTOR_SHAPES = ("round", "hex", "dovetail", "snap")

_CONNECTOR_DOC = _(
    "Womit die Hälften zusammenhalten. Rund druckt am saubersten und braucht "
    "zwei Stück gegen Verdrehen; Sechskant und Schwalbenschwanz halten schon "
    "einzeln, der Schwalbenschwanz auch gegen Auseinanderziehen. Der Schnapper "
    "rastet ein und hält ohne Kleber — er braucht eine Naht, die mindestens "
    "5,4 mm hergibt."
)


#: Was eine Hälfte von der anderen unterscheidet, sobald verstiftet wurde,
#: und das Zeichen davor.
_HALF_MARK = " · "
_PIN_NOTE = _("Stifte")
_BORE_NOTE = _("Löcher")

#: Dieselben zwei Zusätze als **ganzer** Name, mit dem Stamm als Wert. Der
#: Stamm gehört dem Nutzer und bleibt eine Zeichenkette; der Zusatz gehört der
#: Anwendung und wandert mit der Sprache. Vorher war der ganze Name eine feste
#: Zeichenkette in der Sprache, die beim Trennen eingestellt war.
#:
#: Das Trennzeichen steht hier ausgeschrieben und nicht als ``_HALF_MARK``:
#: Der Einsammler liest die Message-ID als **Literal** aus dem ``_()``-Aufruf,
#: und ein zusammengesetzter Ausdruck ist für ihn keine. Zwei Sprachdateien mit
#: einem Schlüssel, den niemand mehr füllt, wären der Preis dafür.
_HALF_IDS = frozenset({"{name} · Stifte", "{name} · Löcher"})


@lru_cache(maxsize=1)
def _own_notes() -> frozenset[str]:
    """Die beiden Zusätze in jeder ausgelieferten Sprache.

    Gebraucht, um den *eigenen* Zusatz von einem fremden Namensteil zu
    unterscheiden. Ein bloßes Abschneiden am letzten „ · " war zu grob:
    „Halter · Sonderanfertigung" verlor beim Teilen sein zweites Wort —
    stiller Verlust an einem Namen, den jemand selbst vergeben hat.

    Über alle Sprachen und nicht nur über die aktive, weil ein Teil auf
    Deutsch geteilt und danach auf Englisch weitergeteilt werden kann. Ohne
    das stapelten sich zwei Zusätze in zwei Sprachen.

    Gemerkt, und das ist keine vorbeugende Optimierung: Der Aufruf liest fünf
    Katalogdateien und kostet gemessen 9,6 ms — für den Vergleich von zwei
    Wörtern, einmal je Schnitt. Die Antwort hängt an den ausgelieferten
    Dateien und nicht an der eingestellten Sprache, kann also nicht veralten.
    """
    from app.i18n.catalog import available_languages, read_catalog

    notes = {str(_PIN_NOTE), str(_BORE_NOTE), _PIN_NOTE.msgid, _BORE_NOTE.msgid}
    for language in available_languages():
        catalog = read_catalog(language)
        for note in (_PIN_NOTE, _BORE_NOTE):
            translated = catalog.get(note.msgid)
            if translated:
                notes.add(translated)
    return frozenset(notes)


def half_names(
    base: TranslatableText | str, *, pinned: bool, pins_on_b: bool = False
) -> tuple[TranslatableText | str, TranslatableText | str]:
    """Wie die beiden Stücke heißen.

    „A" und „B" allein beantworten die Frage nicht, die man beim Zusammenbauen
    hat — und beim Export ist der Dateiname die einzige Auskunft darüber,
    welches der beiden Teile die Stifte trägt. Deshalb steht sie im Namen.

    Ein **eigener** Zusatz wird ersetzt, nicht ergänzt: Wer eine Hälfte noch
    einmal teilt, bekommt sonst „Halter A · Stifte A · Stifte". Der
    Buchstabenpfad bleibt dabei stehen — er zeigt, aus welchem Stück welches
    geworden ist. Ein fremder Namensteil hinter demselben Zeichen bleibt, wo
    er ist (:func:`_own_notes`).

    Der Rückgabetyp ist geteilt: Ohne Stifte ist der Name reiner Nutzertext und
    bleibt eine Zeichenkette; mit Stiften trägt er den Zusatz der Anwendung und
    ist übersetzbar. Wer ihn anzeigt, nimmt ``str(...)``; wer ihn in einen
    Dateinamen schreibt, ``source_text``.

    ``pins_on_b`` sagt, dass B die Stifte trägt (RM-005) — dann tauschen die
    Zusätze, die Buchstaben bleiben, wo die Hälften liegen.
    """
    # Ab hier wörtlich: Wie die Hälften heißen, entsteht beim Trennen, und was
    # dabei entsteht, gehört dem Nutzer — dieselbe Regel wie beim Namen einer
    # Kopie (:func:`app.core.scene.ops._copy_name`). Genommen wird die Fassung,
    # die er beim Trennen gesehen hat.
    if isinstance(base, TranslatableText) and base.msgid in _HALF_IDS:
        # Eine Hälfte, die dieselbe Anwendung benannt hat: Der Stamm steht
        # als Wert daneben und muss nicht aus dem Text zurückgelesen werden.
        stem = str((base.values or {}).get("name", ""))
    else:
        stem = str(base)
        head, mark, tail = stem.rpartition(_HALF_MARK)
        if mark and tail in _own_notes():
            stem = head
    if not pinned:
        return f"{stem} A", f"{stem} B"
    if pins_on_b:
        return (
            _("{name} · Löcher", name=f"{stem} A"),
            _("{name} · Stifte", name=f"{stem} B"),
        )
    return (
        _("{name} · Stifte", name=f"{stem} A"),
        _("{name} · Löcher", name=f"{stem} B"),
    )


@op_params
class DrillParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        maximum=200.0,
        doc=_(
            "Nenndurchmesser der Bohrung. Für eine Schraube gibt es *Schraubenloch* "
            "in den Bausteinen — dort kommen die Maße aus der Normteiltabelle."
        ),
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z, placement="advanced"
    )
    axis: str = param(
        title=_("Achse"), default="z", choices=_AXES, doc=_ALONG, placement="advanced"
    )
    nx: float = param(
        title=_("Richtung X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Freie Richtung aus der gewählten Fläche. "
            "Null in allen drei Feldern verwendet die Achse."
        ),
    )
    ny: float = param(
        title=_("Richtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Weitere Achse der Richtung — siehe Richtung X."),
    )
    nz: float = param(
        title=_("Richtung Z"),
        default=0.0,
        placement="advanced",
        doc=_("Weitere Achse der Richtung — siehe Richtung X."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_("Null bohrt durch das ganze Teil."),
    )
    slotted: bool = param(
        title=_("Langloch"),
        default=False,
        placement="front",
        doc=_(
            "Zieht die Bohrung zu einem Langloch auseinander — für Schrauben, "
            "die sich nach dem Festziehen noch ausrichten lassen sollen."
        ),
    )
    slot_length: float = param(
        title=_("Länge des Langlochs"),
        # Das Doppelte des vorgegebenen Durchmessers: Wer den Haken setzt und
        # sonst nichts anfasst, bekommt ein gültiges Langloch und keine Absage.
        # Eine Null stünde hier als Vorgabe, die beim ersten Klick abgelehnt
        # wird — und ein Feld, das mit einer Absage begrüßt, ist keine.
        default=10.0,
        minimum=0.0,
        unit="mm",
        placement="front",
        depends_on=("slotted", (True,)),
        doc=_(
            "Gesamtlänge über beide runden Enden. Der Weg, den eine Schraube "
            "darin hat, ist diese Länge minus dem Durchmesser."
        ),
    )
    slot_angle: float = param(
        title=_("Richtung des Langlochs"),
        default=0.0,
        minimum=-180.0,
        maximum=180.0,
        unit=DEGREE_UNIT,
        placement="front",
        depends_on=("slotted", (True,)),
        doc=_("Dreht das Langloch in der angeklickten Fläche. Die Vorschau zeigt die Lage mit."),
    )
    widening_diameter: float = param(
        title=_("Durchmesser der Aufweitung"),
        default=0.0,
        minimum=0.0,
        unit="mm",
        placement="advanced",
        # Die drei Aufweitungsfelder hängen am **abgewählten** Langloch, und
        # zwar aus einem Grund, der im Kern noch einmal steht
        # (:data:`prepare.SLOT_AND_WIDENING`): Eine Senkung über einem
        # Langloch wäre entweder rund oder selbst ein Langloch, und welche
        # der beiden Längen dann gemeint ist, hat noch niemand gesagt.
        #
        # **Weitergegeben werden zwei von ihnen** (:func:`bore_shape`), und das
        # ist kein Versehen: ``transition_angle`` beschreibt den Übergang
        # *zwischen* Bohrung und Aufweitung, und ohne eine Aufweitung liest ihn
        # ``drill_outline`` gar nicht. Ihn mitzunullen hieße, einen Wert
        # zurückzusetzen, den der Kunde beim nächsten Runden wiederhaben will.
        depends_on=("slotted", (False,)),
        doc=_(
            "Null lässt die Bohrung gerade. Ein größerer Durchmesser "
            "schafft Platz über ihrer Mündung."
        ),
    )
    widening_depth: float = param(
        title=_("Tiefe der Aufweitung"),
        default=0.0,
        minimum=0.0,
        unit="mm",
        placement="advanced",
        depends_on=("slotted", (False,)),
        doc=_("Tiefe des breiteren geraden Abschnitts, gemessen ab der angeklickten Fläche."),
    )
    transition_angle: float = param(
        title=_("Übergangswinkel"),
        default=90.0,
        minimum=5.0,
        maximum=180.0,
        unit=DEGREE_UNIT,
        placement="advanced",
        depends_on=("slotted", (False,)),
        doc=_(
            "Voller Winkel zwischen Bohrung und Aufweitung. 180 Grad erzeugt eine flache Schulter."
        ),
    )
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="mouth",
        choices=_ANCHORS,
        placement="advanced",
        doc=_(
            "Was die Position bedeutet: die Mündung, an der die Bohrung anfängt, "
            "oder ihre Mitte. Eine Aufweitung beginnt an der Mündung."
        ),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=True,
        placement="advanced",
        doc=_("Vergrößert die Bohrung um den Wert aus dem Materialprofil."),
    )


#: Der Haken steht, die Länge nicht — und der Satz nennt beide Auswege.
#:
#: Er sagt ausdrücklich auch den zweiten: Wer den Haken versehentlich gesetzt
#: hat, soll ihn herausnehmen können, ohne den Fehler zweimal zu lesen. Der
#: allgemeine Satz aus dem Kern (:data:`prepare.SLOT_TOO_SHORT`) kennt keinen
#: Haken — er gilt auch dort, wo es keinen gibt.
#:
#: **„Deutlich über" und nicht „über"**, seit die Grenze eine gemessene ist
#: (:func:`prepare.shortest_slot`): Ein Langloch knapp über seinem Durchmesser
#: erkennt niemand mehr als eines. Die Zahl selbst steht in ``values`` und
#: darunter im Dialog — ein Platzhalter im Satz bliebe dem Kunden wörtlich
#: stehen.
SLOT_NEEDS_A_LENGTH: Final = _(
    "Ein Langloch braucht eine Länge deutlich über seinem Durchmesser. Tragen Sie "
    "mindestens die Länge ein, die darunter steht, oder nehmen Sie den Haken heraus, "
    "wenn die Bohrung rund bleiben soll."
)

#: Nach dem Zug steht kein Langloch mehr da — und das ist keine Ausnahme.
#:
#: Ein Schnitt quer über sich selbst kann ein Kreuz erzeugen. Eine eindeutige
#: Randöffnung bleibt dagegen als offenes Langloch erhalten.
#: Wie genau die gemessene Länge eines Langlochs die eingetragene treffen muss,
#: damit es das gezogene ist — ein Prozent. Das Netz tastet die Bögen ab und
#: liegt damit ein Zehntelprozent daneben (20,0147 mm für 20); der exakte
#: Kern trifft auf die vierte Stelle. Ein Prozent lässt beiden Raum und trennt
#: trotzdem 20 von 26.
_SAME_LENGTH: Final = 0.01

#: Zwischen der Breite und der kürzesten Länge gibt es kein Loch, das die
#: Erkennung hält — und die Absage nennt beide Auswege: genau die Breite für
#: eine runde Bohrung, mindestens die Länge darunter für ein Langloch.
NEITHER_ROUND_NOR_SLOT: Final = _(
    "Zwischen rund und Langloch gibt es keine Länge. Tragen Sie genau den Durchmesser "
    "für eine runde Bohrung ein oder mindestens die Länge darunter für ein Langloch."
)

SLOT_FEATURE_LOST: Final = _(
    "Nach dem Zug lässt sich der verbleibende Ausschnitt an dieser Stelle nicht mehr "
    "eindeutig als Langloch erkennen. Spätere Schritte, die auf dieses Langloch "
    "verweisen, verlieren ihren Bezug. "
    "Mit Strg+Z kommen Sie zum vorherigen Stand zurück."
)


@dataclasses.dataclass(frozen=True, slots=True)
class BoreShape:
    """Was aus den Feldern des Bohrdialogs wirklich geschnitten wird."""

    slot_length: float
    slot_angle: float
    widening_diameter: float
    widening_depth: float


def bore_shape(params: DrillParams, *, within: Mesh | None = None) -> BoreShape:
    """Die Felder, die der Haken *Langloch* gegeneinander abschaltet.

    ``depends_on`` graut sie im Dialog aus, und ein abhängiges Feld wird von
    der Operation übergangen (:attr:`app.core.types.ParamSpec.depends_on`).
    Hier steht, was das für die Bohrung heißt — an einer Stelle, weil beide
    Kerne dieses Schema teilen und weil Chat und Kommandozeile den Dialog gar
    nicht erst sehen: Über sie kämen Langloch und Aufweitung sonst zusammen an,
    und der Kern müsste eine Frage beantworten, die niemand gestellt hat.

    **Und ein gesetzter Haken ohne Länge ist eine Absage, keine runde Bohrung.**
    ``slot_travel`` liest die Null als „rund" — das ist der richtige Vertrag für
    einen direkten Aufruf, aber nicht für diesen Haken: Wer *Langloch* anhakt
    und die Länge stehen lässt, bekäme ein rundes Loch und ein Häkchen, das das
    Gegenteil behauptet. Das ist genau die stille Wahl, die Regel 21 ausschließt.

    ``within`` ist der Körper, in den gebohrt wird. Mit ihm läuft die Länge
    durch dieselbe Schranke wie bei *Zum Langloch ziehen*
    (:func:`_reject_oversized`): ``slot_length`` trägt im Schema keine
    Obergrenze, und ohne diese Zeile nahm *Bohrung setzen* hunderttausend
    Millimeter an, wo der Zwilling sie ablehnt (Fund des Reviews,
    11.09.2026). Die Vorschau ruft ohne Körper — sie zeichnet, was da ist.
    """
    if params.slotted:
        shortest = shortest_slot(params.diameter)
        if params.slot_length < shortest - EPS_GEOM:
            raise ValidationError(
                field="slot_length",
                constraint="slot_proportion",
                detail=SLOT_NEEDS_A_LENGTH,
                value=params.slot_length,
                values={
                    "diameter": format_length(params.diameter),
                    "shortest": format_length(shortest),
                },
            )
        if within is not None:
            _reject_oversized("slot_length", params.slot_length, within, kind="length")
        return BoreShape(params.slot_length, params.slot_angle, 0.0, 0.0)
    return BoreShape(0.0, 0.0, params.widening_diameter, params.widening_depth)


@register_op(
    name="drill_hole",
    title=_("Bohrung setzen"),
    category="holes",
    params=DrillParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    touches_features=True,
    deterministic=False,
    shortcut="Ctrl+B",
    doc=_(
        "Bohrt ein rundes Loch oder ein Langloch — auf Wunsch um die Materialtoleranz vergrößert."
    ),
)
def drill_hole(ctx: OpContext) -> OpResult:
    params = cast(DrillParams, ctx.params)
    source = ctx.inputs[0]
    if source.kind == "brep":
        # **Die Weiche statt des Hakens** (P2.8, Konzept §10.1): Ein exakter
        # Körper bleibt exakt, und das entscheidet der Körper, nicht ein Feld
        # im Dialog. Dasselbe Schema, derselbe Schritt im Verlauf; der
        # Zwilling bleibt für alte Projekte und ``change_kernel`` registriert.
        from app.core.brep.ops import drill_brep_hole

        return drill_brep_hole(ctx)
    shape = bore_shape(params, within=source.mesh)
    result = drill(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        normal=(params.nx, params.ny, params.nz),
        diameter=params.diameter,
        depth=params.depth,
        widening_diameter=shape.widening_diameter,
        widening_depth=shape.widening_depth,
        transition_angle=params.transition_angle,
        anchor=cast(BoreAnchor, params.anchor),
        profile=for_object(ctx.profile, source),
        compensate=params.compensate,
        quality=ctx.quality,
        seed=ctx.seed,
        slot_length=shape.slot_length,
        slot_angle=shape.slot_angle,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        solver=result.solver,
        findings=result.findings,
    )


# --- Erkannte Merkmale versetzen (§25, Kundenumfrage vom 03.09.2026) ---------------
#
# **Eine Maschine mit mehreren Ausgängen, nicht mehrere Operationen.** Vier der
# neun Merkmalsarten beschreiben ihren eigenen Körper vollständig, und ``recess``
# sagt, ob er ein Hohlraum ist oder Materie:
#
#     hole     axis, centre, depth, diameter, through
#     pin      axis, centre, depth, diameter
#     cone     axis, centre, diameter, angle, recess
#     sphere   centre, diameter, recess
#
# Damit sind Verschieben, Ändern und Löschen dasselbe Paar aus Vereinen und
# Abziehen — an der alten Stelle das Gegenteil dessen, was das Merkmal ist, an
# der neuen das Merkmal selbst.
#
# Die drei übrigen Arten bleiben draußen, und zwar begründet: Eine ``face``
# gehört zur Oberfläche des Körpers (dafür gibt es ``push_face``), ein
# ``edge_loop`` ist ein Netzfehler und kein Körper, und ein ``fillet`` hängt an
# seiner Kante — versetzt man ihn allein, bleibt die Kante scharf und die
# Rundung liegt daneben.

#: Die Arten, deren Kennzahlen das Merkmal **genau** beschreiben.
#:
#: **Genau heißt: Der gebaute Körper ist das Merkmal und nicht mehr.** Bei einer
#: Bohrung stimmt das — ``centre``, ``axis``, ``depth`` und ``through`` spannen
#: den Zylinder auf, der genau das Loch ist. Bei einem Zapfen ebenso: ``depth``
#: ist seine Höhe über der Grundfläche.
#:
#: Bei ``cone`` und ``sphere`` stimmt es **nicht**, und das ist gemessen: Die
#: erkannte Mitte einer Kuppe liegt in der Fläche, auf der sie sitzt — der halbe
#: Grundkörper steckt im Material. Wer den ganzen abzieht, gräbt eine Mulde in
#: die Platte. An einer Kuppe Ø 12 auf einer 10 mm starken Platte kostete das
#: 445 mm³ von 24 449, und der Körper war danach wasserdicht und still falsch.
#:
#: Der Weg dorthin ist bekannt und gehört in einen eigenen Schritt: Die
#: Merkmalsflächen (``face_indices``) begrenzen die Kuppe genau, und ihr
#: Randring liegt auf der Grundfläche — gedeckelt ergibt er den Körper, der
#: wirklich das Merkmal ist. Bis dahin sagt die Operation, warum sie es nicht
#: tut, statt es falsch zu tun (Regel 21).
#: ``void`` steht hier aus demselben Grund wie ``sphere``, und der Beleg lag
#: schon vor der Art: ``test_a_cavity_inside_the_body_moves_without_losing_material``
#: versetzt seit dem 03.09.2026 eine Kugelhöhle in einem Würfel, und das
#: Volumen des Ganzen bleibt dabei auf die Stelle genau gleich. Ein
#: eingeschlossener Hohlraum ist für :func:`_feature_body` der **einfachste**
#: Fall — seine Fläche hat gar keinen Randring, sie ist bereits der Körper.
#:
#: **Und er ist nicht immer ein Defekt.** Eine Aussparung für einen
#: eingegossenen Magneten und ein vergessener Negativkörper sind topologisch
#: dieselbe Sache; welche von beiden vorliegt, weiß nur der Kunde. Ihn zu
#: benennen ist Auskunft, ihn zu sperren wäre ein Urteil (Entscheidung Robert,
#: 10.09.2026).
#:
#: **Das Langloch seit dem 11.09.2026** (RM-153). Sein Werkzeugkörper kommt aus
#: :func:`_feature_solid` wie der einer Bohrung — aufgezogen statt rotiert —,
#: und was ihm bis dahin fehlte, war keine Geometrie, sondern eine Antwort:
#: :func:`app.core.types.is_a_cavity` kannte es nicht und hielt es für
#: Materie. Gemessen an beiden Kernen: versetzt nach (25|15) auf die Stelle,
#: gedreht von 30 auf 75 Grad, verdoppelt, entfernt — das Volumen des Ganzen
#: bleibt jeweils auf ein Zehntausendstel gleich.
MOVABLE_KINDS: Final = ("hole", "pin", "cone", "sphere", "void", "slot", "torus")

#: Was sich zu **verdoppeln** lohnt — dasselbe ohne den Einschluss.
#:
#: Geometrisch ginge es: Der Merkmalskörper eines Hohlraums ist gebaut und
#: abgezogen wie jeder andere. Es will nur niemand. Eine zweite Luftblase im
#: Material ist keine Konstruktion, sondern ein zweiter Fehler — und wo ein
#: eingeschlossener Hohlraum Absicht ist (die Aussparung für einen
#: eingegossenen Magneten), legt man die zweite über den Baustein an, mit
#: Maßen, und nicht als Kopie einer gemessenen Fläche (Robert, 10.09.2026:
#: „verdoppeln ist aber bei Hohlräumen sinnlos").
DUPLICABLE_KINDS: Final = ("hole", "pin", "cone", "sphere", "slot", "torus")

#: Die Arten, deren Kennzahlen den Körper genau beschreiben.
#:
#: Für sie baut :func:`_feature_solid` ihn daraus, und das ist auch der
#: einzige Weg, der eine **durchgehende** Bohrung trägt: Ihr Flächenausschnitt
#: hat zwei Randringe, und ein Deckel aus einem Fächer schließt nur einen.
#:
#: **Das Langloch gehört seit dem 11.09.2026 dazu.** Es ist aus Mitte, Achse,
#: Durchmesser, Tiefe, Länge und Richtung vollständig beschrieben — genau wie
#: eine Bohrung, nur mit zwei Bogenmittelpunkten statt einem. Ohne den Eintrag
#: fiel `_tool_for` auf `_feature_body`, bekam aus dem Flächenausschnitt keinen
#: geschlossenen Körper und endete in der Absage über Senkungen: Wer ein
#: vorhandenes Langloch versetzen wollte, las einen Satz über einen Fall, den es
#: dort nicht gibt (Fund des Reviews, 11.09.2026).
PARAMETRIC_KINDS: Final = ("hole", "pin", "slot")

#: Wie viele Seiten ein gebauter Zylinder oder Kegel bekommt. Dieselbe Zahl wie
#: beim Bohren — ein Stopfen mit anderer Auflösung träfe die Bohrungswand in
#: einer fast zusammenfallenden Fläche, und das ist der eine Fall, den eine
#: Boolesche zuverlässig bricht (§39).
FEATURE_SECTIONS: Final = BORE_SECTIONS

#: Ab welchem Anteil der Proben vor einem Rand im Material eine Mündung als
#: zugedeckt gilt (:func:`_mouth_covered`): Eine Haut liegt vor dem ganzen
#: Ring, eine falsch antwortende Kantenprobe vor einem Punkt von 32.
COVERED_SHARE: Final = 0.5

#: Wie weit der Rand eines Hohlraums im Mittel neben seiner Ausgleichsebene
#: liegen darf, damit der Stopfen ihn noch mit einem Fächer schließt — als
#: Anteil seines Durchmessers (:func:`_body_from_faces`, ``curved_rims``). Eine
#: Zylindersenkung Ø 11 in einer schrägen Fläche des Gartenschlauchhalters
#: schwankt um ±0,4 mm; ein Zwanzigstel des Durchmessers lässt sie zu und
#: hält den Deckel nah genug an der Fläche, dass kein Stopfen über sie steht.
CURVED_RIM: Final = 0.05

#: Wie weit der Öffnungswinkel eines am Netz gemessenen Kegels vom gesetzten
#: abweichen darf, damit er noch derselbe ist — in Grad, über den ganzen Winkel.
#: Die Erkennung passt einen glatten Kegel in Facetten, und die liegen innerhalb
#: des gemeinten: Eine um 30° gekippte 90°-Senkung aus einem Werkzeug mit
#: :data:`FEATURE_SECTIONS` Ecken kam als 89,80° zurück (RM-220, 25.09.2026).
#: Die Normwinkel von Senkungen liegen mindestens acht Grad auseinander; Spitze
#: und Achse müssen ohnehin treffen (:func:`_same_cone`).
FACETED_CONE_ANGLE: Final = 1.0

# Wieviel größer der Körper gebaut wird, der ein Merkmal ausfüllt oder abträgt,
# steht in :data:`app.core.geom.prepare.FEATURE_OVERLAP` und wird hier nur
# gelesen. Die Zahl stand am 10.09.2026 an zwei Stellen mit demselben Wert und
# derselben Begründung — einmal hier, einmal als ``SLOT_OVERLAP`` daneben; die
# zweite ist gefallen.


def _slot_angle_in_frame(feature: Feature, direction: Any) -> float:
    """Die Richtung eines erkannten Langlochs, gezählt gegen seinen Rahmen.

    Dieselbe Frage, die :func:`slot_angle_of` beantwortet — hier mit der Achse,
    die der Aufrufer gerade verwendet, denn beim Drehen ist sie eine andere als
    die gemessene.
    """
    axis = (float(direction[0]), float(direction[1]), float(direction[2]))
    return slot_angle_of(feature, axis)


def _feature_solid(
    feature: Feature,
    centre: Vec3,
    scale: float = 1.0,
    axis: Vec3 | None = None,
    *,
    oversize: float = FEATURE_OVERLAP,
) -> MeshData:
    """Der Körper, den dieses Merkmal einnimmt — an ``centre`` gesetzt.

    ``scale`` skaliert die Querschnittsmaße; ``1.0`` baut das Merkmal, wie es
    gemessen wurde. ``axis`` überschreibt seine Richtung; ``None`` nimmt die
    gemessene. Beide zusammen sind der Grund, warum Versetzen, Drehen und
    Ändern **eine** Maschine sind und nicht drei: Zwischen den zwei Booleschen
    steht jeweils nur ein anderer Wert.

    Der Körper wird um ``oversize`` größer gebaut als gemessen, damit keine
    Boolesche auf zusammenfallende Flächen trifft (§39) — beim Ausfüllen wie
    beim Abtragen. Die Vorgabe ist :data:`FEATURE_OVERLAP`; **null** baut ihn
    exakt, und das braucht genau ein Aufrufer: ein Werkzeug, das eine Bohrung
    wiederherstellt, muss so weit sein wie sie war, sonst steht danach ein
    zweites, um die Zugabe weiteres Loch im Baum (:func:`_measured_section`).
    Die **Länge** bekommt ihre Zugabe in jedem Fall — ein Werkzeug, das genau
    an der Außenfläche endet, schneidet dort nicht durch.
    """
    diameter = float(feature.params.get("diameter", 0.0)) * scale + oversize
    if diameter <= EPS_GEOM:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal hat kein Maß, aus dem sich ein Körper bauen ließe."),
            values={"feature": feature.id},
            constraint="no_size",
        )

    if feature.kind == "sphere":
        body = trimesh.creation.icosphere(radius=diameter / 2.0)
        body.apply_translation(np.asarray(centre, dtype=float))
        return MeshData.of(body)

    wanted = axis if axis is not None else feature.params.get("axis", (0.0, 0.0, 1.0))
    given = np.asarray(wanted, dtype=float)
    length = float(np.linalg.norm(given))
    direction = given / length if length > EPS_GEOM else np.array([0.0, 0.0, 1.0])
    # **Ganz durch und nicht nur so tief wie gemessen.** Eine Bohrung, die als
    # 12 mm tief erkannt wurde, muss beim Ausfüllen auch die 12 mm treffen —
    # und eine, die durchgeht, den ganzen Körper. Die gemessene Tiefe ist die
    # Untergrenze, die Zugabe an beiden Enden deckt die Messungenauigkeit.
    depth = float(feature.params.get("depth", 0.0))
    height = (depth if depth > EPS_GEOM else diameter) + 2.0 * FEATURE_OVERLAP

    if feature.kind == "cone":
        # Über ``lathe`` und nicht ``trimesh.creation.cone``: Dessen Ecken
        # kommen aus ``np.cos``, und das rechnet je CPU anders (RM-187).
        body = lathe.revolve(
            [[0.0, 0.0], [diameter / 2.0, 0.0], [0.0, height]], sections=FEATURE_SECTIONS
        )
        # ``cone`` steht mit der Spitze oben auf z=0; für einen Hohlraum zeigt
        # sie ins Material, also entlang der Achse.
        body.apply_translation((0.0, 0.0, -height / 2.0))
    elif feature.kind == "slot":
        # **Ein Langloch ist eine Bohrung mit zwei Bogenmittelpunkten.** Der
        # Umriss kommt aus derselben Funktion, die auch schneidet
        # (`prepare.slot_profile`), und wird aufgezogen statt rotiert — ein
        # Zylinder träfe seine geraden Flanken nicht. Aufgezogen wird in der
        # **lokalen** Ebene; die Drehung in die Achse macht der gemeinsame
        # Schluss unten, wie bei Zylinder und Kegel auch.
        from app.core.geom.prepare import slot_profile
        from app.core.geom.sketch_solid import extrude_profile

        measured = float(feature.params.get("diameter", 0.0)) * scale
        travel = max(0.0, float(feature.params.get("length", 0.0)) - measured)
        if travel <= EPS_GEOM:
            body = lathe.cylinder(radius=diameter / 2.0, height=height, sections=FEATURE_SECTIONS)
        else:
            body = extrude_profile(
                slot_profile(
                    radius=diameter / 2.0,
                    travel=travel,
                    angle_deg=_slot_angle_in_frame(feature, direction),
                ),
                height,
                PlaneFrame(
                    origin=(0.0, 0.0, -height / 2.0),
                    x_axis=(1.0, 0.0, 0.0),
                    y_axis=(0.0, 1.0, 0.0),
                    normal=(0.0, 0.0, 1.0),
                ),
            )
    else:
        body = lathe.cylinder(radius=diameter / 2.0, height=height, sections=FEATURE_SECTIONS)

    turn = transform.rotation_between([0.0, 0.0, 1.0], direction)
    transform.moved(body, turn)
    body.apply_translation(np.asarray(centre, dtype=float))
    return MeshData.of(body)


#: Wie flach ein Randring sein muss, damit ein Deckel aus einem Fächer trägt.
#:
#: Ein Fächer vom Schwerpunkt zu jeder Randkante ist genau dann eine Fläche,
#: wenn der Ring in einer Ebene liegt. Bei einer Kuppe auf einer Platte ist die
#: Spanne gemessen **null**; die Grenze fängt die Tesselierung einer schwach
#: gekrümmten Grundfläche mit und lehnt alles darüber ab, statt einen
#: verdrehten Deckel zu bauen.
#:
#: **Diese Zahl ist an einem einzigen Körper gemessen, und das ist ihr
#: schwächster Punkt.** Sie hält, weil die Grenze mit der Wurzel der
#: Randknotenzahl mitwächst — die abgelehnten Fälle liegen um Größenordnungen
#: darüber (15,2 gegen 0,51 an einer Senkung über einer Bohrung, gemessen am
#: 03.09.2026). Wer sie anfasst, messe an **mehr als einem** Körper: 3d-druck-7b
#: hat am selben Tag zwei Schranken aus je einem Messwert gesetzt, und beide
#: standen zu eng — 5 Grad aus einer Messung von 2,2, und der zweite Fall lag
#: bei 5,74. Eine Schranke aus einem Wert ist geraten, nicht gemessen; der Fall
#: steht ausgeschrieben in ``.claude/memory/schranke-aus-einem-messwert-ist-geraten.md``.
FLAT_RIM: Final = 0.05


def _feature_body(mesh: MeshData, feature: Feature, *, alone: bool = False) -> MeshData | None:
    """Der Körper, den dieses Merkmal wirklich einnimmt — aus seinen Flächen.

    **Warum nicht aus den Kennzahlen.** Für Bohrung und Zapfen beschreiben
    ``centre``, ``axis``, ``depth`` und ``diameter`` den Körper genau, und
    :func:`_feature_solid` baut ihn daraus. Für eine Kuppe oder einen Kegel tun
    sie das nicht: Die erkannte Mitte liegt **in** der Fläche, auf der sie
    sitzen, der halbe Grundkörper steckt im Material. Gemessen am 03.09.2026
    kostete das Versetzen einer Kuppe Ø 12 auf einer 10-mm-Platte 445 mm³ von
    24 449 — der Körper blieb wasserdicht und war still falsch.

    Die Merkmalsflächen sagen es genau: Sie begrenzen die Kuppe, ihr Randring
    liegt auf der Grundfläche, und mit einem Deckel darüber entsteht der
    Körper, der wirklich das Merkmal ist. Gemessen: 448,5 mm³ gegen 452,4 der
    analytischen Halbkugel — die Differenz ist die Tesselierung der Vorlage.

    ``None``, wenn der Bau nicht sicher ist: keine Flächen, mehr als ein
    Randring, oder ein Ring, der nicht in einer Ebene liegt. Dann ist ein
    Deckel aus einem Fächer keine Fläche, und ein verdrehter Deckel wäre
    schlimmer als eine Absage (Regel 21).

    **Warum ein zweiter Randring die Absage wert ist**, gemessen am 03.09.2026
    an einer 10 mm starken Platte mit durchgehender Bohrung Ø 6 und Senkung Ø 12:
    Die Kegelfläche der Senkung hat zwei Ringe — Ø 12 auf der Oberseite und
    Ø 6 dort, wo sie in die Bohrung übergeht. Mit einem Deckel je Ring entsteht
    ein sauberer Kegelstumpf von 196,65 mm³, wasserdicht und der analytischen
    Rechnung entsprechend. Er ist trotzdem das falsche Werkzeug: Beim Auffüllen
    an der alten Stelle wuchs der Körper um alle 196,65 mm³, obwohl nur 113,1
    davon Senkung waren — der Rest war die **Bohrung**, und ein Querschnitt bei
    z = 3,5 hatte danach kein Loch mehr. Wer die Senkung versetzt, hätte seine
    Bohrung verloren.

    Ein zweiter Ring heißt also: Dieses Merkmal geht in ein anderes über, und
    sein Hohlraum gehört nicht ihm allein. Allein bleibt die Absage richtig;
    :func:`_paired_cavity_body` nimmt die erkannte Nachbarschaft dazu und baut
    erst daraus den gemeinsamen Körper.

    **Und ``alone`` ist der Fall, in dem derselbe zweite Ring das Gegenteil
    bedeutet** (09.09.2026). Die Zahl der Ringe ändert sich nicht, wenn die
    Bohrung unter der Senkung verschlossen wird — die Kegelfläche endet dann
    an einer Kreisscheibe aus Material statt an einer Bohrungswand. Gemessen an
    ``plate_countersunk.stl``: vorher zwei Ringe zu 48 Ecken, nach dem
    Entfernen der Bohrung zwei zu 65 und 48. Wer die Ringe zählt, liest beide
    Male dasselbe; die Absage galt danach einem Nachbarn, den es nicht mehr
    gab, und die Senkung war nicht mehr zu löschen (Befund Robert,
    09.09.2026: „wenn wir die Bohrung löschen, können wir die Senkung nicht
    mehr löschen").

    Wer ``alone`` setzt, hat die Frage anderswo beantwortet — an derselben
    Kette, aus der auch der gemeinsame Körper entsteht
    (:func:`_stands_alone`). Derselbe belegte Alleinstand gilt beim Versetzen,
    Kopieren und in der Platzierungsvorschau.

    Ein vorhandener Senkungsboden gehört mit seinen echten Dreiecken dazu:
    Ein neuer Fächer durch denselben Rand läge bei einem quantisierten Netz
    neben dem Boden und ließe beim Füllen eine dünne innere Schale stehen.
    Seine eindeutige Zugehörigkeit liest :func:`_cavity_floor` am ganzen
    gemeinsamen Rand, wie für die fortgeführte Bodenkennung einer Bohrung.
    """
    rings = (0, 1, 2) if alone else (0, 1)
    indices = feature.face_indices
    if alone and feature.kind == "cone" and is_a_cavity(feature):
        from app.core.perceive.features import detect

        floor = _cavity_floor(mesh, feature, detect(mesh), None)
        if floor is not None:
            indices = (*indices, *floor.face_indices)
    return _body_from_faces(mesh, indices, allowed_rings=rings)


def _stands_alone(mesh: MeshData, feature: Feature, features: Mapping[str, Feature]) -> bool:
    """Ob dieser Hohlraum keinem Nachbarn gehört — die Frage hinter ``alone``.

    Zwei Auskünfte aus einer Quelle (``cavity_chain_state_at``): eine Kette
    heißt, das Merkmal ist ein Abschnitt von mehreren; ein berührter fremder
    Rand heißt, die Nachbarschaft ist da und nur nicht eindeutig. Erst wenn
    **beides** verneint ist, gehört der Hohlraum dem Merkmal allein.

    Gemessen an ``plate_countersunk.stl``: mit der Bohrung Kette
    ``[hole_1, cone_1]`` und berührter Rand, nach ihrem Entfernen keine Kette
    und kein berührter Rand.
    """
    from app.core.perceive.relations import cavity_chain_state_at, cavity_is_shared

    return not cavity_is_shared(cavity_chain_state_at(feature, features, mesh))


def _body_from_faces(
    mesh: MeshData,
    face_indices: Sequence[int],
    *,
    allowed_rings: tuple[int, ...],
    curved_rims: bool = False,
) -> MeshData | None:
    """Einen Flächenausschnitt an seinen ebenen Randringen schließen.

    Ein einzelnes Merkmal darf höchstens einen Ring haben. Bohrung und
    Senkung zusammen haben genau zwei: die weite Mündung der Senkung und die
    andere Mündung beziehungsweise den Boden der Bohrung. Die Zahl kommt vom
    Aufrufer, damit ein zweiter Ring nie wieder still dieselbe Bedeutung für
    zwei verschiedene Geometrien bekommt.

    ``curved_rims`` nimmt auch einen Ring, der nur fast eben ist — bis
    :data:`CURVED_RIM` seines Durchmessers neben seiner Ausgleichsebene, im
    Mittel. Der Deckel ist dann ein Fächer vom Mittelpunkt an den Ring und
    folgt ihm; das braucht nur der Stopfen (:func:`_cavity_plug`), nie ein
    Werkzeug, das bündig schneiden muss.
    """
    if not face_indices:
        return None

    raw = mesh.raw
    chosen = np.unique(np.asarray(face_indices, dtype=np.int64))
    if chosen.size == 0 or int(chosen.max()) >= len(raw.faces):
        return None

    patch = trimesh.Trimesh(
        vertices=raw.vertices, faces=np.asarray(raw.faces)[chosen], process=False
    )
    patch.remove_unreferenced_vertices()
    patch.merge_vertices()

    # Eine Randkante gehört genau einem Dreieck des Ausschnitts. Alles andere
    # liegt innen und braucht keinen Deckel. ``edges`` und ``edges_sorted``
    # stehen Zeile für Zeile gleich; die gerichtete Fassung trägt den
    # Umlaufsinn des Dreiecks, zu dem die Kante gehört.
    edges = patch.edges_sorted
    single = trimesh.grouping.group_rows(  # type: ignore[no-untyped-call]
        edges, require_count=1
    )
    rim = edges[single]
    rim_directed = np.asarray(patch.edges, dtype=np.int64)[single]
    points = np.asarray(patch.vertices, dtype=float)

    rings = list(trimesh.graph.connected_components(rim)) if len(rim) else []
    if len(rings) not in allowed_rings:
        return None

    if not rings:
        # Ein Ausschnitt ohne Rand ist schon geschlossen — ein Hohlraum ganz im
        # Material. Er braucht keinen Deckel und ist der Körper selbst.
        closed = patch
    else:
        vertices = [points]
        faces = [np.asarray(patch.faces, dtype=np.int64)]
        next_index = len(points)
        for component in rings:
            members = np.asarray(component, dtype=np.int64)
            belongs = np.isin(rim[:, 0], members) & np.isin(rim[:, 1], members)
            ring_edges = rim[belongs]
            if len(ring_edges) < 3:
                return None
            ring = points[members]
            # **Nicht ``ring.mean(axis=0)``** (RM-187): Dieser Punkt wird gleich
            # als echter Eckpunkt ins Netz geschrieben, und NumPys Summation
            # gruppiert nach SIMD-Breite — auf ARM anders als auf x86. Das
            # letzte Bit des Deckelmittelpunkts entschied damit über die
            # Triangulierung des ganzen Werkzeugs.
            hub = np.array(units.exact_centre(ring.tolist()), dtype=np.float64)
            # Flach in **irgendeiner** Richtung, nicht nur in Z: Eine Kuppe an
            # einer Seitenwand hat ihren Ring in der YZ-Ebene.
            spread = ring - hub
            limit = FLAT_RIM
            if curved_rims:
                reach = float(np.max(np.linalg.norm(spread, axis=1)))
                limit = max(limit, CURVED_RIM * 2.0 * reach)
            if float(np.linalg.svd(spread, compute_uv=False)[-1]) > limit * len(ring) ** 0.5:
                return None
            # Der Deckel läuft gegen die Randkanten des Ausschnitts: Jede
            # Kante wird von der anderen Seite geschlossen, und der Körper ist
            # von Anfang an gleichsinnig gewickelt (siehe unten).
            directed = rim_directed[belongs]
            cap = np.column_stack(
                [
                    directed[:, 1],
                    directed[:, 0],
                    np.full(len(ring_edges), next_index, dtype=np.int64),
                ]
            )
            vertices.append(hub.reshape(1, 3))
            faces.append(cap)
            next_index += 1
        closed = trimesh.Trimesh(
            vertices=np.vstack(vertices),
            faces=np.vstack(faces),
            process=True,
        )
    # **Gleichsinnig gewickelt heißt: nur noch die Richtung prüfen.**
    # ``fix_normals`` läuft in trimesh Dreieck für Dreieck durch Python: Am
    # Hohlraum einer Senkbohrung der fünfmal unterteilten Senkplatte (199 680
    # Dreiecke) kostete das 23,6 von 30 s der Vorschau einer
    # Durchmesseränderung (22.09.2026). Ein Ausschnitt aus einem sauberen Netz
    # mit gegenläufigen Deckeln ist schon gleichsinnig; dann genügt es, ihn
    # umzudrehen, wenn er nach innen zeigt. Nur ein Netz, das schon vorher
    # durcheinander gewickelt war, geht den langen Weg.
    if closed.is_winding_consistent:
        if closed.volume < 0.0:
            closed.invert()
    else:
        trimesh.repair.fix_normals(closed)  # type: ignore[no-untyped-call]
    if not closed.is_watertight or closed.volume <= EPS_GEOM:
        return None
    return MeshData.of(closed)


def _paired_cavity_body(mesh: MeshData, *features: Feature) -> MeshData | None:
    """Der gemeinsame Hohlraum aller topologisch verbundenen Abschnitte.

    Die Kegelfläche allein hat zwei Randringe und darf deshalb nicht als
    eigener Körper verschoben werden. Zusammen mit der Bohrungswand bleiben
    genau die beiden äußeren Ränder des **ganzen** Hohlraums. Mit zwei Deckeln
    entsteht das Volumen, das an der alten Stelle gefüllt und an der neuen
    ausgeschnitten werden muss — ohne Maße oder Winkel nachzubauen.
    """
    from app.core.perceive.relations import cavity_surface_indices

    return _body_from_faces(
        mesh,
        cavity_surface_indices(mesh, features),
        allowed_rings=(2,),
    )


def _inner_sections(chain: Sequence[Feature], feature: Feature) -> tuple[Feature, ...]:
    """Die Abschnitte, die **hinter** diesem liegen — sie brauchen einen Durchgang.

    Die Kette kommt geordnet von der engsten Bohrung her (``_ordered_cavity``);
    was auf der Seite des Abschnitts davor steht, liegt tiefer im Material und
    erreicht die Außenwelt nur durch den gewählten Abschnitt hindurch. Weitet
    sich die Bohrung an beiden Enden, zählt nur die eigene Seite
    (``relations.cavity_sides``, RM-245): Die Erweiterung am anderen Ende hat
    ihre eigene Mündung. Für den innersten Abschnitt selbst ist die Menge leer
    — dann gilt der bekannte Weg über den Werkzeugkörper.
    """
    from app.core.perceive.relations import cavity_sides

    for side in cavity_sides(chain):
        position = next((index for index, entry in enumerate(side) if entry.id == feature.id), None)
        if position is not None:
            return tuple(side[:position])
    return ()


def _outward_axis(chain: Sequence[Feature], feature: Feature) -> NDArray[np.float64]:
    """Die Achse dieses Abschnitts, gerichtet **weg** von dem, was hinter ihm liegt.

    Die gemessene Achse ist vorzeichenfrei — eine Senkung unter ihrer Bohrung
    gibt es genauso wie darüber. Wo die Außenwelt ist, sagt der Nachbar.
    """
    axis = np.asarray(_feature_direction(feature), dtype=np.float64)
    inner = _inner_sections(chain, feature)
    if not inner:
        return axis
    outward = np.asarray(feature.params["centre"], dtype=np.float64) - np.asarray(
        inner[-1].params["centre"], dtype=np.float64
    )
    return -axis if float(outward @ axis) < 0.0 else axis


def _measured_section(
    chain: Sequence[Feature], feature: Feature, *, outward: float = 0.0
) -> MeshData | None:
    """Der Abschnitt aus seinen **Kennzahlen**, wo seine Flächen keinen Körper hergeben.

    **Der Fall, für den es das braucht** (Robert, 10.09.2026): An einer
    eingelesenen Halterung ließ sich weder die Senkung noch die ganze Bohrung
    entfernen — beide Wege bauen den Hohlraum aus seinen Flächen, und dieser
    Ausschnitt gibt keinen geschlossenen Körper her. Gemessen an
    ``weg1-halterung-anpassen``: Ringe sauber und flach, aber nach dem
    Verschweißen hängen vier Kanten an je vier Dreiecken, und der Deckelbau
    endet nicht wasserdicht. Das ist eine Eigenschaft des Netzes und nicht der
    Sache — die Erkennung hatte den Hohlraum längst vollständig vermessen:
    Zylinder Ø 5,193 von z 0 bis 5,420, Kegelstumpf darauf bis Ø 10,360 bei
    89,877°.

    Die Kennzahlen beschreiben beides genau, also wird es daraus gebaut. Die
    Höhe des Stumpfes folgt aus den zwei Durchmessern und dem Winkel; der
    kleine ist der des Nachbarn weiter innen, und ohne einen solchen läuft der
    Kegel in seine Spitze.

    **Der Querschnitt bleibt exakt.** Dieser Körper schneidet wieder aus, was
    nach dem Füllen bleiben soll, und muss deshalb genau so weit sein wie das
    Merkmal, das er wiederherstellt: Ein Zylinder mit der üblichen Zugabe ließ
    ein zweites, um 0,02 mm weiteres Loch über der Bohrung stehen, und der
    Objektbaum zeigte danach zwei Bohrungen (Robert, 10.09.2026). Die **Länge**
    bekommt ihre Zugabe weiterhin — sonst bleibt an der Außenfläche eine Haut.
    Gefüllt wird nicht hiermit, sondern mit :func:`_chain_plug`.

    ``outward`` führt einen **Kegel** über seine Mündung hinaus weiter, mit
    demselben Winkel — der Überstand, den eine gekippte Senkung braucht
    (:func:`_chain_tool`). Null ist der Abschnitt, wie er gemessen wurde.

    ``None`` heißt: Diese Art oder diese Maße geben keinen Körper her.
    """
    centre = cast(Vec3, tuple(float(value) for value in feature.params["centre"]))
    if feature.kind != "cone":
        # Das erkannte Kreismaß kommt aus Konturecken. Eine zusätzliche
        # Vieleckkorrektur vergrößerte diesen Umkreis bei jedem Neuaufbau.
        return _feature_solid(feature, centre, oversize=0.0)

    wide = float(feature.params.get("diameter", 0.0))
    angle = float(feature.params.get("angle", 0.0))
    inner = _inner_sections(chain, feature)
    narrow = float(inner[-1].params.get("diameter", 0.0)) if inner else 0.0
    if wide <= narrow + EPS_GEOM or angle <= EPS_GEOM or angle >= 180.0:
        return None
    height = (wide - narrow) / 2.0 / math.tan(math.radians(angle / 2.0))
    if height <= EPS_GEOM:
        return None

    # Der Umriss in der Halbebene, von der Achse aus: Boden, kleiner Rand,
    # großer Rand, zurück zur Achse. ``revolve`` dreht ihn um die lokale
    # Z-Achse, und die zeigt nach dem Ausrichten nach außen — der Stumpf liegt
    # also unter der Mündung im Material.
    beyond = max(0.0, outward)
    outline = [
        [0.0, -height - FEATURE_OVERLAP],
        [narrow / 2.0, -height - FEATURE_OVERLAP],
        [wide / 2.0 + beyond * math.tan(math.radians(angle / 2.0)), beyond + FEATURE_OVERLAP],
        [0.0, beyond + FEATURE_OVERLAP],
    ]
    body = lathe.revolve(outline, sections=FEATURE_SECTIONS)
    transform.moved(
        body,
        transform.rotation_between([0.0, 0.0, 1.0], _outward_axis(chain, feature)),
    )
    body.apply_translation(np.asarray(centre, dtype=float))
    return MeshData.of(body) if body.is_watertight and body.volume > EPS_GEOM else None


def _chain_plug(
    mesh: MeshData,
    chain: Sequence[Feature],
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
) -> MeshData | None:
    """Ein Stopfen über die **ganze** Kette — derselbe Weg, den der Absagetext nennt.

    „Verschließen Sie beides in einem Zug: ein Stopfen mit dem Durchmesser der
    Senkung über die volle Wandstärke" steht seit dem 04.09.2026 in
    :data:`NO_OWN_BODY`, und ``test_the_way_out_of_a_countersink_is_the_one_
    the_message_names`` misst ihn: 24 000,000 mm³, wasserdicht, kein Merkmal
    übrig. Was der Kunde von Hand tun sollte, tut die Operation jetzt selbst.

    **Warum ein Zylinder und nicht die Form des Hohlraums.** Ein Füllkörper,
    der die Kegelwand nachbildet, endet auf ihr — und die Vereinigung lässt
    zwei kegelige Flächen nebeneinander stehen, statt eine Fläche zu machen.
    Gemessen an der Halterung: zwei erkannte Senkungen (Ø 10,34 und Ø 10,36)
    und eine Oberseite, der ihr Trichterstück weiterhin fehlte. Ein Zylinder
    ist überall breiter als der Hohlraum, seine Mantelfläche liegt im vollen
    Material, und übrig bleibt genau eine ebene Fläche — dieselbe Bauart wie
    beim Stopfen einer Bohrung (:func:`_closed_at`).

    Die Maße kommen aus den **Flächen** der Kette: ihre Ausdehnung entlang der
    Achse ist die Tiefe, ihr größter Abstand von der Achse der Radius. Gebaut
    wird er mit Zugabe an den Enden und danach an
    :func:`~app.core.geom.prepare.shell` gekappt — sonst stünde die Zugabe als
    Beule auf der Fläche.

    **Gekappt wird an der Hülle und nicht an einem eigenen Zylinder**, und das
    ist gemessen und nicht gewählt: Beide Wege enden in derselben Ebene, aber
    der Schnitt an der Hülle erzeugt Deckel, die mit der Außenfläche
    verschmelzen — der an einem zweiten Zylinder nicht. An der Halterung stand
    danach oben **und** unten ein Kreisring von 63,6 mm² als eigene Fläche
    neben der Platte (3836,60 statt 3900,19 mm²).

    Dass die Hülle an einem U-Profil zu großzügig ist (:func:`_between_the_mouths`
    nennt den gemessenen Fall), trägt hier nicht: Ein Netz mit sauberen
    Hohlraumflächen kommt gar nicht bis zum Stopfen — es wird aus seinen Flächen
    gefüllt. ``test_no_plug_stands_proud_into_a_hollow`` hält diesen Weg fest.
    """
    from app.core.perceive.relations import cavity_surface_indices

    indices = np.unique(np.asarray(cavity_surface_indices(mesh, chain), dtype=np.int64))
    if not indices.size:
        return None
    raw = mesh.raw
    points = np.asarray(raw.vertices, dtype=float)[np.unique(np.asarray(raw.faces)[indices])]
    outer = chain[-1]
    axis = np.asarray(_feature_direction(outer), dtype=float)
    centre = np.asarray([float(value) for value in outer.params["centre"]], dtype=float)
    along = (points - centre) @ axis
    reach = float(along.max() - along.min())
    across = points - centre - np.outer(along, axis)
    radius = (
        float(np.linalg.norm(across, axis=1).max()) + FEATURE_OVERLAP
    ) / units.inscribed_ratio(FEATURE_SECTIONS)
    if reach <= EPS_GEOM or radius <= EPS_GEOM:
        return None

    plug = lathe.cylinder(
        radius=radius, height=reach + 2.0 * FEATURE_OVERLAP, sections=FEATURE_SECTIONS
    )
    transform.moved(
        plug,
        transform.rotation_between(np.array([0.0, 0.0, 1.0]), axis),
    )
    plug.apply_translation(centre + axis * float(along.min() + along.max()) / 2.0)
    return boolean(
        "intersection",
        [MeshData.of(plug), shell(mesh)],
        quality=quality,
        seed=seed,
        cancelled=cancelled,
    ).mesh


def _cavity_plug(
    mesh: MeshData,
    sections: Sequence[Feature],
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
) -> MeshData | None:
    """Der Körper, der diesen Hohlraum **füllt** — aus seinen Flächen oder als Stopfen.

    Die Flächen zuerst: Ein daraus geschlossener Körper trifft die Facettierung
    des Netzes und füllt bitgenau, was ausgeschnitten wurde. Ein eingelesenes
    Netz gibt ihn aber nicht immer her — an der Halterung aus
    ``weg1-halterung-anpassen`` sind die Randringe sauber und flach, und
    trotzdem hängen nach dem Verschweißen vier Kanten an je vier Dreiecken; der
    Deckelbau endet nicht wasserdicht, und **beide** Wege des Entfernens sagten
    ab (Robert, 10.09.2026). Dann kommt der Stopfen (:func:`_chain_plug`).
    """
    from app.core.perceive.relations import cavity_surface_indices

    indices = cavity_surface_indices(mesh, sections)
    built = _body_from_faces(mesh, indices, allowed_rings=(1, 2))
    if built is not None:
        return built
    # **Ein Rand in einer schrägen, leicht gekrümmten Fläche** (25.09.2026): Am
    # Gartenschlauchhalter mündet eine Zylindersenkung Ø 11 in eine Fläche, die
    # 30° gegen ihre Achse steht und 0,4 mm um ihre Ebene schwankt. Der
    # Zylinderstopfen reicht bis an den äußersten Punkt des Rands und füllte die
    # Luft vor dem Rest der Mündung — eine Beule: um 5° gekippt 58 mm³ Material
    # mehr als vorher, um 15° 148. Ein Fächerdeckel am Ring füllt den Hohlraum
    # bis auf dessen Abweichung von der Ebene.
    built = _body_from_faces(mesh, indices, allowed_rings=(1, 2), curved_rims=True)
    if built is not None:
        return built
    return _chain_plug(mesh, sections, quality=quality, seed=seed, cancelled=cancelled)


def _cavity_tool(
    mesh: MeshData,
    chain: Sequence[Feature],
    sections: Sequence[Feature],
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
) -> MeshData | None:
    """Der Körper, der diese Abschnitte wieder **ausschneidet** — exakt in ihren Maßen.

    Dasselbe Paar wie beim Füllen, nur mit der anderen Aufgabe: erst die
    Flächen, sonst die Kennzahlen (:func:`_measured_section`). Und ohne Zugabe
    im Querschnitt — was hier entsteht, soll genau das Merkmal sein, das nach
    dem Füllen wieder dastehen muss.
    """
    from app.core.perceive.relations import cavity_surface_indices

    built = _body_from_faces(mesh, cavity_surface_indices(mesh, sections), allowed_rings=(1, 2))
    if built is not None:
        return built
    bodies: list[MeshData] = []
    for entry in sections:
        part = _measured_section(chain, entry)
        if part is None:
            return None
        bodies.append(part)
    if len(bodies) == 1:
        return bodies[0]
    return boolean("union", bodies, quality=quality, seed=seed, cancelled=cancelled).mesh


def _section_closed(
    mesh: MeshData,
    chain: Sequence[Feature],
    feature: Feature,
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
    extend_inner: bool = True,
) -> BooleanOutcome | None:
    """**Einen** Abschnitt eines Hohlraums schließen — der Rest bleibt offen.

    **Robert am 10.09.2026:** „wenn ich bei einer Bohrung mit senkung nur die
    senkung entfernen will geht das nicht, also es soll dann nur die senkung
    weg, die Bohrung aber bleiben." Gefragt hat der Kern das längst
    (:func:`_asked_about_sections`); für den Abschnitt allein gab es bis dahin
    keinen Weg, sondern die Absage :data:`NO_OWN_BODY`.

    **Zuerst zu, dann wieder auf** — und diese Reihenfolge ist nicht Geschmack,
    sondern gemessen. Der Abschnitt hat einen eigenen Körper: Die Kegelfläche
    hat zwei Randringe und wird mit zwei Deckeln ein Kegelstumpf. Der füllt auf
    seiner Höhe aber **auch den Bohrungsschlauch** (an einer Platte 60 x 40 x 10
    mit Bohrung Ø 8 und Senkung Ø 16 sind das 27,8 mm³ von 24 000, ein
    Tausendstel im Volumen — und eine Bohrung, die oben zu ist). Ihn vorher zu
    erleichtern und das Ergebnis dann anzufügen, ergibt einen Füllkörper mit
    einer Innenwand, die auf der Bohrungswand liegt; die Vereinigung fiel damit
    bis auf die Voxelstufe zurück und ließ rund einen Millimeter Material im
    Schlauch stehen. Erst den Trichter schließen und danach den Durchgang aus
    dem vollen Material schneiden hält beide Schritte auf ``direct`` — gemessen
    bitgenau der Zustand vor dem Senken.

    Der Durchgang gilt den Abschnitten, die **weiter innen** liegen: Die Kette
    kommt geordnet von der engsten Bohrung her (``_ordered_cavity``), alles vor
    dem gewählten Abschnitt liegt hinter ihm und verlöre sonst seinen Weg nach
    außen — bei einem Sackloch mit Senkung wäre das ein eingeschlossener
    Hohlraum, den kein Drucker füllen kann. Sein Körper wird entlang der Achse
    zur Mündung hin fortgesetzt; ein Zylinder bleibt dabei ein Zylinder, und
    der Querschnitt stimmt mit dem überein, was darunter liegt. Fortgesetzt
    wird in so vielen Schritten, wie seine eigene Länge verlangt — sonst bliebe
    zwischen zwei Kopien eine Scheibe Material stehen.

    Beim Größenändern setzt ``extend_inner=False`` die übrigen Abschnitte nur
    in ihren bisherigen Grenzen zurück. Die neue Bohrung liefert ihren eigenen
    Weg zur Mündung; ein breiterer innerer Kegel darf unter einer schmaleren
    Plansenkung als Hinterschnitt erhalten bleiben.

    ``None`` heißt: Dieser Abschnitt gibt keinen eigenen Körper her; dann gilt
    :data:`NO_OWN_BODY` wie bisher.
    """
    filled = _cavity_plug(mesh, chain, quality=quality, seed=seed, cancelled=cancelled)
    if filled is None:
        return None
    keep = tuple(entry for entry in chain if entry.id != feature.id)
    tools: list[MeshData] = []
    for entry in keep:
        tool = _cavity_tool(mesh, chain, (entry,), quality=quality, seed=seed, cancelled=cancelled)
        if tool is None:
            return None
        tools.append(tool)

    shut = boolean("union", [mesh, filled], quality=quality, seed=seed, cancelled=cancelled)
    body = shut.mesh
    findings = list(shut.findings)
    stages: list[SolverInfo | None] = [shut.solver]

    # **Was bleibt, wird frisch geschnitten** — an seiner Stelle, und für die
    # Abschnitte weiter innen zusätzlich durch den gefüllten hindurch, sonst
    # verlören sie ihren Weg nach außen (bei einem Sackloch mit Senkung wäre
    # das ein eingeschlossener Hohlraum, den kein Drucker füllen kann).
    #
    # Dass der ganze Hohlraum zuerst zugeht, ist der Punkt: Ein Füllkörper, der
    # nur den einen Abschnitt schließt, endet auf der Wand des Nachbarn, und
    # die Vereinigung lässt dort zwei Flächen nebeneinander stehen — im Baum
    # standen danach zwei Bohrungen und zwei Senkungen, und der Oberseite
    # fehlte das Stück, das der Trichter aus ihr geschnitten hatte (Robert,
    # 10.09.2026). Aus vollem Material geschnitten ist die Bohrung **eine**
    # Fläche, wie an jeder anderen Stelle auch.
    axis = _outward_axis(chain, feature)
    # Die Länge entlang der Achse elementweise, nicht über ``@`` (BLAS): Aus
    # ihr wird gleich der Weg, um den das Werkzeug verschoben wird (RM-187).
    reach = float(np.ptp(transform.along(filled.raw.vertices, axis))) + FEATURE_OVERLAP
    inner = _inner_sections(chain, feature)
    for entry, tool in zip(keep, tools, strict=True):
        span = float(np.ptp(transform.along(tool.raw.vertices, axis)))
        steps = 0
        if extend_inner and any(entry.id == section.id for section in inner):
            steps = max(1, math.ceil(reach / span)) if span > EPS_GEOM else 1
        for step in range(steps + 1):
            moved = tool.raw.copy()
            if step:
                moved.apply_translation(axis * (reach * step / steps))
            cut = boolean(
                "difference",
                [body, MeshData.of(moved)],
                quality=quality,
                seed=seed,
                cancelled=cancelled,
            )
            body = cut.mesh
            findings.extend(cut.findings)
            stages.append(cut.solver)
    return BooleanOutcome(mesh=body, solver=deepest(stages) or shut.solver, findings=findings)


def _feature_direction(feature: Feature, axis: Vec3 | None = None) -> Vec3:
    """Die Richtung dieses Merkmals als Einheitsvektor.

    ``axis`` überschreibt die gemessene; ohne beides gilt Z.
    """
    wanted = axis if axis is not None else feature.params.get("axis", (0.0, 0.0, 1.0))
    given = np.asarray(wanted, dtype=float)
    # ``math.hypot`` statt ``np.linalg.norm`` (BLAS): Die Richtung trägt jedes
    # Werkzeug, das an diesem Merkmal gesetzt wird (RM-187).
    length = math.hypot(float(given[0]), float(given[1]), float(given[2]))
    unit = given / length if length > EPS_GEOM else np.array([0.0, 0.0, 1.0])
    return (float(unit[0]), float(unit[1]), float(unit[2]))


def _no_longer_through(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
    tool: MeshData | None = None,
) -> bool:
    """Steht im Schlauch dieser Bohrung wieder Material?

    **Der Fall, den niemand ansagt.** Das Werkzeug eines Merkmals ist aus
    seinen gemessenen Kennzahlen gebaut und wandert mit: Eine Bohrung, die als
    durchgehend erkannt wurde, ist nach dem Versetzen genau so lang wie vorher.
    Wandert sie entlang ihrer eigenen Achse oder trifft sie an der neuen Stelle
    auf dickeres Material, geht sie nicht mehr durch. Gemessen am 03.09.2026 an
    einer 10 mm starken Platte, Bohrung Ø 16, um 5 mm in Z versetzt: Unten
    blieben 1,985 mm Material stehen, 398 mm³, und der Körper war wasserdicht
    und einteilig. Geometrisch richtig, für den Kunden eine Überraschung.

    Gemessen wird am **Ergebnis** und nicht an einer Rechnung über Hüllmaße:
    Ein Zylinder im Durchmesser der Bohrung, lang genug für das ganze Teil,
    gegen den fertigen Körper verschnitten. Bleibt dort Volumen, steht Material
    im Schlauch. Ein Vergleich von Hüllmaßen hätte an jedem nicht
    quaderförmigen Teil falschen Alarm gegeben.

    **Mit ``tool`` zählt nur, was unmittelbar hinter dem Schnitt steht.** Die
    lange Säule kreuzt an einem verwinkelten Teil hinter der Wand wieder
    Material: Am Schraubenhalter mit Wabenmuster ging eine um 15° gekippte
    Befestigungsbohrung sauber durch die Rückwand, und die Säule traf 43 bis
    112 mm weiter die Waben — „geht nicht mehr durch" (RM-133, 23.09.2026).
    Ein Rest, der erst jenseits des Werkzeugendes beginnt, liegt hinter Luft
    (:func:`_behind_the_cut`); die Bohrung ist durch ihre Wand hindurch.

    **Und die Säule liegt im Werkzeug** (25.09.2026). Eine Bohrung aus einer
    STL-Datei ist ein Vieleck, versetzt wird ihr Flächenkörper: An einer
    Furnierplatte, 0,6 mm dick, Bohrungen Ø 6,1 als 32-Eck, reichte die Säule
    mit 0,02 mm unter dem Durchmesser über dessen Innenkreis hinaus, und an jeder Sehne blieb
    ein Splitter von 0,0001 mm³ in ihr — „geht nicht mehr durch" nach 1,5 mm
    quer, bei unverändertem Volumen. Mit ``tool`` nimmt die Säule deshalb
    höchstens den Innenkreis seiner Wand (:func:`_inscribed_radius`).
    """
    diameter = float(feature.params.get("diameter", 0.0)) - FEATURE_OVERLAP
    if tool is not None:
        inscribed = _inscribed_radius(tool, centre, _feature_direction(feature))
        if inscribed is not None:
            diameter = min(diameter, 2.0 * inscribed - FEATURE_OVERLAP)
    if diameter <= EPS_GEOM:
        return False
    reach = float(np.linalg.norm(mesh.bounds.size)) * 2.0
    column = lathe.cylinder(radius=diameter / 2.0, height=reach, sections=FEATURE_SECTIONS)
    transform.moved(
        column,
        transform.rotation_between(
            np.array([0.0, 0.0, 1.0]), np.asarray(_feature_direction(feature), dtype=float)
        ),
    )
    column.apply_translation(np.asarray(centre, dtype=float))
    left = boolean(
        "intersection",
        [MeshData.of(column), mesh],
        quality=quality,
        seed=seed,
        allow_empty=True,
        cancelled=cancelled,
    )
    # **Der leere Schnitt ist der gute Fall, und er darf nicht rechnen.** Geht
    # die Bohrung noch durch, bleibt vom Verschnitt nichts übrig — und ein Netz
    # ohne Dreiecke nach seinem Volumen zu fragen teilt in ``trimesh`` durch
    # null (``RuntimeWarning: invalid value encountered in divide``). Die Suite
    # macht daraus einen Fehler (``filterwarnings = ["error"]``), und gemessen
    # am 03.09.2026 riss genau daran der erste Lauf des Verdoppelns.
    remaining = left.mesh.raw
    if len(remaining.faces) == 0:
        return False
    if not bool(remaining.volume > EPS_GEOM):
        return False
    if tool is None:
        return True
    return not _behind_the_cut(remaining, tool, centre, _feature_direction(feature))


def _inscribed_radius(tool: MeshData, centre: Vec3, direction: Vec3) -> float | None:
    """Der kleinste Abstand einer Wandfläche des Werkzeugs von seiner Achse —
    der Innenkreis seines Vielecks; ``None`` ohne Wand längs der Achse.

    Gezählt werden die Dreiecke, deren Normale quer zur Achse steht: die Wand
    eines Zylinders. Senkungen und Deckel stehen schräg oder quer und zählen
    nicht; an einer Kette gibt so die engste Bohrung das Maß. **Ein Dreieck
    ohne Fläche zählt nie** (Durchsicht seit 0.5.0): Seine Normale ist null,
    stand damit „quer" und im Abstand null, und die Säule schrumpfte auf
    nichts. Die Normalen kommen aus ``stable_normals`` (RM-187), denn aus dem
    Abstand wird die Säule, an der „geht nicht mehr durch" hängt.
    """
    from app.core.geom.mesh import stable_normals

    raw = tool.raw
    if not len(raw.faces):
        return None
    axis = np.asarray(direction, dtype=np.float64)
    axis /= math.hypot(*(float(value) for value in axis))
    normals, areas = stable_normals(raw)
    along = normals[:, 0] * axis[0] + normals[:, 1] * axis[1] + normals[:, 2] * axis[2]
    wall = (np.abs(along) < _WALL_ACROSS) & (areas > 0.0)
    if not bool(wall.any()):
        return None
    corners = np.asarray(raw.triangles, dtype=np.float64)[wall, 0] - np.asarray(centre)
    facing = normals[wall]
    distances = np.abs(
        corners[:, 0] * facing[:, 0] + corners[:, 1] * facing[:, 1] + corners[:, 2] * facing[:, 2]
    )
    return float(distances.min())


#: Wie weit die Normale eines Wanddreiecks von der Querrichtung abweichen darf,
#: als Kosinus zur Achse: Die Wand eines Zylinders steht quer (0), der Kegel
#: einer 120°-Senkung bei 0,5 — ein Zehntel trennt beide.
_WALL_ACROSS: Final = 0.1


def _behind_the_cut(remaining: Any, tool: MeshData, centre: Vec3, direction: Vec3) -> bool:
    """Ob jeder Rest in der Säule erst jenseits des Werkzeugs beginnt — hinter Luft.

    Je Seite gilt das Werkzeugende als Grenze, gemessen entlang der Achse von
    ``centre``. Ein Rest, der dort ansetzt, ist Wand, durch die das Werkzeug
    nicht kam; einer, der erst dahinter beginnt, hat zwischen sich und dem
    Schnitt etwas, das nicht Material ist — die Bohrung hat ihre Wand dort
    schon verlassen. Die Zugabe ist die des Werkzeugs (``FEATURE_OVERLAP``):
    Näher als sie liegt nichts, was man Luft nennen könnte.
    """
    axis = np.asarray(direction, dtype=np.float64)
    origin = np.asarray(centre, dtype=np.float64)
    cut = (np.asarray(tool.raw.vertices, dtype=np.float64) - origin) @ axis
    forward = float(cut.max()) + FEATURE_OVERLAP + EPS_GEOM
    backward = float(cut.min()) - FEATURE_OVERLAP - EPS_GEOM
    for piece in remaining.split(only_watertight=False):
        if not bool(abs(float(piece.volume)) > EPS_GEOM):
            continue
        along = (np.asarray(piece.vertices, dtype=np.float64) - origin) @ axis
        if float(along.min()) > forward or float(along.max()) < backward:
            continue
        return False
    return True


def _edge_findings(body: MeshData, placed: Iterable[Feature]) -> list[Finding]:
    """Ob eine gesetzte Bohrung seitlich über den Körper hinausragt — für
    Versetzen und Verdoppeln dieselbe Frage wie beim Bohren.

    *Bohren*, *Bohrung ändern* und *Zum Langloch ziehen* sagen es seit dem
    09.09.2026 (``prepare.over_the_edge_along``, geprüft am Netz und nicht am
    Hüllquader); *Versetzen* und *Verdoppeln* setzen eine Bohrung genauso an
    eine neue Stelle und schwiegen. Gemessen an der Fahne eines Minigolf-Satzes
    (15.09.2026): 2 mm zur Seite, plus 8,5 Prozent Volumen, weil der Pfropfen
    die ganze Bohrung füllte und das Messer nur noch teilweise traf — im
    Bericht stand nichts. Gefragt wird je Abschnitt des Hohlraums an seiner
    neuen Mitte, mit seinem Durchmesser und seiner Achse; gemeldet wird
    höchstens einmal, wie an einem Langloch. ``body`` ist der Körper **vor**
    dem Schnitt an der neuen Stelle — beim Versetzen der gefüllte, damit die
    alte Stelle keine offene Flanke vortäuscht.
    """
    for feature in placed:
        if not is_a_cavity(feature) or feature.kind not in ("hole", "cone", "slot"):
            continue
        diameter = float(feature.params.get("diameter", 0.0))
        if diameter <= EPS_GEOM:
            continue
        centre = np.asarray(feature.params["centre"], dtype=np.float64)
        # Gefragt wird an der Mitte **und** an beiden Austritten: Wo die Achse
        # den Hüllquader verlässt, liegt die Mündung einer gekippten Bohrung,
        # und die Vorprüfung am Hüllquader sieht nur die Scheibe an dem Punkt,
        # den sie bekommt — an der Mitte einer um 60° gedrehten Bohrung war
        # alles im Kasten, ihr unterer Austritt lag 2,3 mm neben der Platte.
        exits = _axis_exits(body, centre, _feature_direction(feature))
        cone = None
        if feature.kind == "cone":
            # **Eine Senkung mündet nur an ihrem weiten Ende** (RM-220): Am
            # engen geht die Bohrung weiter, und die fragt ihren eigenen
            # Durchmesser. Mit dem weiten gefragt, lag die Ellipse einer um 30°
            # gekippten Senkung Ø 10 an der Unterseite über der Nachbarbohrung
            # 10 mm daneben — „über die Kante", an beiden Kernen.
            exits = exits[:1]
            # **Und dort mit ihrem Kegel** (Durchsicht seit 0.5.0): Der Kranz ist
            # der Schnitt des Kegels mit der Fläche, nicht der Kreis seines
            # weiten Endes (``prepare.mouth_over_the_edge``).
            cone = _sink_cone(feature)
        for exit_point, inward in exits:
            found = mouth_over_the_edge(
                body,
                cast(Vec3, tuple(float(value) for value in exit_point)),
                cast(Vec3, tuple(float(value) for value in inward)),
                diameter,
                cone=cone,
            )
            if found:
                return found
        if cone is not None:
            # **Die Senkung fragt nur ihre Mündung.** Der Kranz über die ganze
            # Länge (``over_the_edge_along``) ist der Kreis des weiten Endes und
            # bleibt es bis in jede Tiefe; der Kegel wird aber zur Spitze hin
            # enger. Eine um 35° gekippte Senkung Ø 8 einen Millimeter vor der
            # Seitenfläche hieß damit „über die Kante", obwohl keine Seite Fläche
            # verlor. Der Kegel unter der Mündung ist die Hülle aus ihrem Schnitt
            # und der Spitze; liegen beide in einem konvexen Körper, liegt er es
            # auch.
            continue
        positions = [centre]
        if feature.kind == "slot":
            # Ein Langloch reißt an einem Ende auf, während seine Mitte tief im
            # Material steckt — gefragt wird an beiden Enden (``prepare.slot_ends``).
            direction = np.asarray(
                feature.params.get("direction", (1.0, 0.0, 0.0)), dtype=np.float64
            )
            stretch = max(0.0, float(feature.params.get("length", 0.0)) - diameter) / 2.0
            if float(np.linalg.norm(direction)) > EPS_GEOM and stretch > EPS_GEOM:
                direction /= float(np.linalg.norm(direction))
                positions = [centre - direction * stretch, centre + direction * stretch]
        # **Mit ihrer Länge** (RM-249): Bleibt die Scheibe im Hüllquader, fragt
        # die Prüfung am Netz über die eigene Tiefe des Merkmals nach — eine
        # Kopie über einer Seite, die schmaler ist als die Hülle, sagte sonst
        # nichts.
        depth = _depth_of(feature)
        reach = depth / 2.0 if depth > EPS_GEOM else diameter / 2.0
        for position in positions:
            found = over_the_edge_along(
                body,
                cast(Vec3, tuple(float(value) for value in position)),
                _feature_direction(feature),
                diameter,
                body=body,
                reach=reach,
            )
            if found:
                return found
    return []


def _sink_cone(feature: Feature) -> tuple[Vec3, float] | None:
    """Spitze und halber Öffnungswinkel eines Kegelmerkmals — ``None`` ohne Maß.

    Die Mitte eines Kegels liegt an seinem weiten Ende, seine Achse zeigt
    von der Spitze dorthin (an beiden Kernen gemessen); die Spitze liegt um
    ``r / tan(halber Winkel)`` dahinter. Die Winkelfunktionen kommen aus
    ``units`` (RM-187), denn aus der Spitze wird der Kranz eines Befunds.
    """
    half = float(feature.params.get("angle", 0.0)) / 2.0
    radius = float(feature.params.get("diameter", 0.0)) / 2.0
    if radius <= EPS_GEOM or not EPS_DISPLAY < half < 90.0 - EPS_DISPLAY:
        return None
    outward = np.asarray(_feature_direction(feature), dtype=np.float64)
    reach = radius * units.exact_cos_degrees(half) / units.exact_sin_degrees(half)
    apex = np.asarray(feature.params["centre"], dtype=np.float64) - outward * reach
    return (float(apex[0]), float(apex[1]), float(apex[2])), half


def _axis_exits(
    body: MeshData, centre: np.ndarray, direction: Vec3
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Die zwei Punkte, an denen die Gerade durch ``centre`` entlang ``direction``
    den Körper verlässt, je mit der Richtung von dort in den Körper — leer,
    wenn die Mitte außerhalb des Hüllquaders liegt oder die Richtung keine ist.

    **Wo die Achse den Körper verlässt, nicht wo sie den Hüllquader verlässt**
    (RM-220, 25.09.2026). Der Hüllquader reicht über jeden Vorsprung: An einer
    Platte mit Rippe über der Senkung trat die Achse einer um 30° gekippten
    Bohrung erst 6 mm über der Oberseite aus dem Quader, auf der Rippe, und
    deren Kante stand halb im Kranz — „über die Kante", wo die Bohrung sauber
    in der Platte mündete. Am Schraubenhalter mit Wabenmuster kam derselbe
    Satz bei 20° und 30°. Der Austritt ist deshalb der erste Durchstoß der
    Achse durch die Oberfläche (:func:`~app.core.geom.mesh.ray_hits`), von der
    Mitte aus — ein Treffer, dessen Flächennormale mit dem Strahl läuft —, und
    höchstens der Rand des Quaders. Trifft der Strahl nichts,
    liegt die Mitte selbst auf der Oberfläche — die einer Senkung in ihrer
    Mündung — und ist in dieser Richtung ihr eigener Austritt.

    **Je Achse Eintritt und Austritt, nicht der kleinste von sechs Schnitten.**
    Hier stand der kleinste positive Abstand zu irgendeiner der sechs Ebenen,
    und das stimmt nur, solange die Mitte echt innen liegt. Eine Senkung hat
    ihre Mitte an der Mündung, also **auf** der Oberseite: Der Abstand dorthin
    ist null und fiel heraus, und übrig blieb der Schnitt mit einer
    Seitenebene über die Rauschkomponente der Achse — bei einer Achse von
    (-3·10⁻¹⁷, 6·10⁻¹⁷, 1) ein Austritt bei z = 3·10¹⁷. Was die Mündungsprüfung
    an einem solchen Punkt antwortet, ist Rechenmüll, und er fiel je Plattform
    anders: Auf macOS meldete eine auf Ø 8 geänderte Senkung, die mit 19 mm
    in einer 20 mm breiten Platte liegt, „über die Kante" (CI, 22.09.2026).
    Mit Eintritt und Austritt je Achse liefert eine Rauschkomponente nur
    ±10¹⁷ und gewinnt nie, und eine Mitte auf der Fläche ist ihr eigener
    Austritt.
    """
    axis = np.asarray(direction, dtype=np.float64)
    length = float(np.linalg.norm(axis))
    if length <= EPS_GEOM:
        return []
    axis /= length
    lower = np.asarray(body.bounds.minimum, dtype=np.float64)
    upper = np.asarray(body.bounds.maximum, dtype=np.float64)
    if bool(np.any(centre < lower - EPS_GEOM)) or bool(np.any(centre > upper + EPS_GEOM)):
        return []
    with np.errstate(divide="ignore", invalid="ignore"):
        to_lower = (lower - centre) / axis
        to_upper = (upper - centre) / axis
    # Eine Achse, zu der die Richtung genau parallel läuft, begrenzt nichts:
    # Die Mitte liegt in ihrer Schicht, und die Division gibt ±inf oder nan.
    bounded = np.isfinite(to_lower) & np.isfinite(to_upper)
    if not bool(bounded.any()):
        return []
    forward = max(float(np.maximum(to_lower, to_upper)[bounded].min()), 0.0)
    backward = max(-float(np.minimum(to_lower, to_upper)[bounded].max()), 0.0)
    triangles = np.asarray(body.raw.triangles, dtype=np.float64)
    normals = np.asarray(body.raw.face_normals, dtype=np.float64)
    exits = []
    for ray, box in ((axis, forward), (-axis, backward)):
        travel = box
        if len(triangles):
            # Ein Dreieck unter einer Mitte auf der Oberfläche ist kein Austritt
            # in diese Richtung; der Strahl zählt erst ab ``EPS_GEOM``.
            distances, hit = ray_hits(triangles, centre, ray, minimum_travel=EPS_GEOM)
            # Elementweise und nicht über ``@`` (RM-187): Der Austritt wird zum
            # Befund, und der soll auf jeder Maschine derselbe sein.
            facing = normals[hit]
            leaving = facing[:, 0] * ray[0] + facing[:, 1] * ray[1] + facing[:, 2] * ray[2] > 0.0
            travel = min(box, float(distances[leaving].min())) if bool(leaving.any()) else 0.0
        exits.append((centre + ray * travel, -ray))
    return exits


def _throughness_lost(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    op: str,
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
    tool: MeshData | None = None,
) -> list[Finding]:
    """Der Befund dazu — leer, wenn die Bohrung weiter durchgeht.

    Ein Hinweis und keine Ausnahme: Das Ergebnis ist richtig gerechnet, es ist
    nur nicht das, was der Kunde erwartet hat. Der Satz nennt deshalb, woran es
    liegt, und nicht nur, dass es so ist (§2.7).
    """
    if not feature.params.get("through"):
        return []
    if not _no_longer_through(
        mesh, feature, centre, quality=quality, seed=seed, cancelled=cancelled, tool=tool
    ):
        return []
    return [_through_lost_finding(op, feature, centre)]


def _between_the_mouths(mesh: MeshData, feature: Feature, centre: Vec3) -> MeshData | None:
    """Ein Schnittkörper, der genau so weit reicht wie das Merkmal selbst.

    **Warum die konvexe Hülle dafür nicht genügt.** ``plug`` beschneidet seinen
    Stopfen an :func:`~app.core.geom.prepare.shell`, und für einen massiven
    Körper ist das richtig: Die Hülle *ist* er. Für ein U-Profil ist sie der
    volle Kasten — gemessen 72 000 gegen 27 000 mm³ —, und ein Überstand, der
    in die Nut ragt, liegt **innerhalb** der Hülle. Genau das hat Robert am
    03.09.2026 an einem Kundenteil gesehen: ein erhabener Kranz um die alte
    Stelle. Nachgebaut an einem U-Profil mit 5 mm Bodenwand und einer Bohrung
    Ø 7,98: **76,4 mm³** standen nach dem Versetzen im Nutraum, vorher null.

    Die Merkmalsfläche weiß es besser als jede Hülle: Sie **ist** die Wand des
    Hohlraums, ihre Ausdehnung entlang der Merkmalsachse ist seine Tiefe, und
    ihre Ränder liegen in den Mündungen. Der Schnittkörper ist deshalb ein
    Zylinder um die Achse, der genau von der einen Mündung zur anderen reicht —
    breit genug für jedes Werkzeug, das hier hineingeht, und in der Länge
    genau.

    ``None``, wenn das Merkmal keine Flächen führt. Dann bleibt es beim
    Hüllschnitt, der für massive Körper trägt.
    """
    if not feature.face_indices:
        return None
    raw = mesh.raw
    chosen = np.asarray(feature.face_indices, dtype=np.int64)
    if chosen.size == 0 or int(chosen.max()) >= len(raw.faces):
        return None

    points = np.asarray(raw.vertices, dtype=float)[np.unique(np.asarray(raw.faces)[chosen])]
    direction = np.asarray(_feature_direction(feature), dtype=float)
    measured = np.asarray([float(value) for value in feature.params["centre"]], dtype=float)
    along = (points - measured) @ direction
    reach = float(along.max() - along.min())
    if reach <= EPS_GEOM:
        return None

    # Breit genug für alles, was als Werkzeug hineingeht — geschnitten wird nur
    # in der Länge. Der Radius kommt aus der Ausdehnung der Fläche quer zur
    # Achse, damit auch eine Senkung hineinpasst, die weiter ist als ihr Loch.
    across = points - measured - np.outer(along, direction)
    radius = (
        float(np.linalg.norm(across, axis=1).max()) + FEATURE_OVERLAP * 2.0
    ) / units.inscribed_ratio(FEATURE_SECTIONS)

    cut = lathe.cylinder(radius=radius, height=reach, sections=FEATURE_SECTIONS)
    transform.moved(
        cut,
        transform.rotation_between(np.array([0.0, 0.0, 1.0]), direction),
    )
    middle = float(along.min() + along.max()) / 2.0
    cut.apply_translation(np.asarray(centre, dtype=float) + direction * middle)
    return MeshData.of(cut)


def _without_old_triangles(
    features: Mapping[FeatureId, Feature], *, without: Iterable[FeatureId] = ()
) -> dict[FeatureId, Feature]:
    """Die durchgereichten Merkmale, wie ein neu gebautes Netz sie trägt: ohne Dreiecksnummern.

    Eine Boolesche nummeriert die Dreiecke neu, und :func:`_without_scars`
    vernetzt die Deckflächen danach ganz neu. Flächennummern und Teilträger
    eines Merkmals, das die Operation nur weiterreicht, bezeichnen am Ergebnis
    fremde Dreiecke: An der Lochplatte hielt ``cavity_chain_state_at`` die
    verbliebene Bohrung danach für unlesbar, und das Verdoppeln sagte ab
    (``test_prepare``, 21.09.2026). Eine Operation gibt nur Merkmale ihres
    Ausgangsnetzes zurück — Ort und Maß bleiben, die Oberfläche gibt ihnen die
    Auswertung an der neuen Erkennung zurück (``evaluate._with_features``, „Der
    Name bleibt, die aktuelle Oberfläche geht mit"). Dieselbe Regel gilt in
    ``parts.ops._merged_features`` für den Wirt eines Bausteins. ``without``
    nennt, was die Operation entfernt hat.
    """
    gone = set(without)
    return {
        name: (
            dataclasses.replace(feature, face_indices=(), surface_patches=())
            if feature.face_indices or feature.surface_patches
            else feature
        )
        for name, feature in features.items()
        if name not in gone
    }


def _closed_at(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    cavity: bool,
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
    alone: bool = False,
) -> BooleanOutcome:
    """Das Merkmal an dieser Stelle schließen: gefüllt, wenn es ein Hohlraum
    ist, abgetragen, wenn es Material ist.

    **Ein Werkzeug, das beim Abtragen richtig ist, ist beim Auffüllen zu
    groß.** Der Körper eines Merkmals wird absichtlich etwas größer gebaut, als
    gemessen wurde (:data:`FEATURE_OVERLAP`), und eine durchgehende Bohrung
    bekommt mindestens ihren Durchmesser als Länge, damit sie das Material auf
    jeden Fall trifft — sonst stünde eine Boolesche vor zusammenfallenden
    Flächen (§39). Beim Ausschneiden macht dieser Überstand nichts. Beim
    Vereinen trägt er außen auf.

    **Gemessen am 03.09.2026**, gefunden von Robert am eigenen Kundenmodell
    („die Bohrung wird richtig verschoben, aber an der alten Stelle steht das
    Material dann oben und unten über") und nachgebaut an einer 10 mm starken
    Platte mit durchgehender Bohrung Ø 16: Nach dem Versetzen war das
    Teil **16,03 mm hoch statt 10**, der Stopfen stand oben und unten drei
    Millimeter über, und das Volumen wuchs von 21 995 auf 23 600 mm³. Der
    Körper blieb dabei wasserdicht.

    :func:`~app.core.geom.prepare.plug` löst dasselbe seit langem mit einer
    Zeile: erst mit der Hülle verschneiden, dann vereinen. Genau die fehlte
    hier, an vier Stellen — Versetzen, Entfernen, Drehen und Ändern schließen
    alle nach demselben Muster.

    Abgetragen wird ohne Schnitt: Ein Zapfen, der über die Hülle hinausragt,
    **ist** das Teil an dieser Stelle, und ein zu großes Messer schneidet nur
    Luft.
    """
    tool = _tool_for(
        mesh, feature, centre, alone=alone, quality=quality, seed=seed, cancelled=cancelled
    )
    # **Wo die Bohrung wirklich endet, sagen ihre Randringe** (22.09.2026). Ein
    # Stopfen aus Kennzahlen hat Deckel quer zu seiner Achse; eine schräge
    # Bohrung mündet aber in den Plattenflächen, und die Achsspanne ihrer Wand
    # reicht an der einen Seite der Ellipse über die Fläche hinaus. Begrenzt an
    # ``_between_the_mouths`` stand der Stopfen dort über: *Merkmal entfernen*
    # an einer um 45° gekippten Bohrung durch eine 10-mm-Platte ergab 18,5 mm
    # Höhe und 171 mm³ zu viel. Mit den Ebenen der Randringe endet er genau in
    # den Flächen, aus denen die Bohrung kommt — und darf dafür zuerst länger
    # gebaut werden, denn geschnitten wird danach.
    planes = _rim_planes(mesh, feature) if cavity else ()
    if planes and feature.kind == "slot":
        tool = _feature_solid(_longer(feature), centre)
    # **Und für den Zapfen gilt dasselbe wie für die Bohrung**, nur andersherum:
    # Beim Abtragen muss das Werkzeug das Vieleck des Zapfens umschreiben,
    # sonst bleiben zwischen seinen Facetten und denen des Werkzeugs Splitter
    # stehen. Gemessen an der Nabe eines Uhrenrads (Ø 11,3, 48 Segmente, gegen
    # 64 des Werkzeugs; 15.09.2026): 48 Reste von 0,003 mm³, einer je Facette.
    if feature.kind in ("hole", "pin"):
        # Der Innenkreis des Stopfens muss alle ursprünglichen Eckpunkte
        # einschließen, auch wenn deren Tessellierung eine andere Teilung hat.
        radius = _bore_number(feature, "diameter") / 2.0
        if feature.face_indices:
            points = np.asarray(mesh.raw.triangles)[list(feature.face_indices)].reshape(-1, 3)
            axis = np.asarray(_bore_vector(feature, "axis"))
            axis /= np.linalg.norm(axis)
            relative = points - centre
            radius = max(
                radius,
                float(np.linalg.norm(relative - np.outer(relative @ axis, axis), axis=1).max()),
            )
        diameter = 2.0 * radius / units.inscribed_ratio(FEATURE_SECTIONS)
        tool = _feature_solid(
            _longer(feature) if planes else feature,
            centre,
            oversize=diameter - _bore_number(feature, "diameter") + FEATURE_OVERLAP,
        )
        # **Ein Zapfen geht mit seinen eigenen Flächen** (22.09.2026). Der
        # Zylinder aus Kennzahlen trug die Zugabe aus §39 an beiden Enden und
        # schnitt damit 0,02 mm in die Grundfläche: Nach jedem Versetzen stand
        # an der alten Stelle eine Delle vom Durchmesser des Zapfens. Aus den
        # Flächen geschlossen ist der Körper genau der Zapfen, und
        # :func:`_past_the_mouths` gibt ihm die Zugabe nur dort, wo Luft ist —
        # an der Spitze, nicht am Fuß. Die Facetten sind dieselben wie am
        # Netz; umschreiben muss der Körper nichts, er deckt sich.
        own = _pin_body(mesh, feature) if feature.kind == "pin" else None
        if own is not None:
            tool = _past_the_mouths(mesh, own)
    clipped = _cut_at_the_rims(tool, planes) if planes else None
    if clipped is not None:
        tool = clipped
    elif cavity:
        # **Erst an den Mündungen, sonst an der Hülle.** Die Merkmalsfläche
        # kennt die Tiefe des Hohlraums genau; die konvexe Hülle kennt nur den
        # Umriss des ganzen Teils und lässt einen Überstand stehen, der in eine
        # Nut oder einen Innenraum ragt (siehe :func:`_between_the_mouths`).
        limit = _between_the_mouths(mesh, feature, centre) or shell(mesh)
        tool = boolean(
            "intersection", [tool, limit], quality=quality, seed=seed, cancelled=cancelled
        ).mesh
    if cavity and feature.params.get("open"):
        # Die axiale Begrenzung kennt den seitlichen Außenrand nicht.
        mouth = np.asarray(_bore_vector(feature, "mouth_centre"))
        outward = np.asarray(_bore_vector(feature, "opening_normal"))
        reach = mesh.bounds.diagonal * 2.0
        envelope = trimesh.creation.box(extents=(reach * 2.0, reach * 2.0, reach))
        envelope.apply_translation((0.0, 0.0, -reach / 2.0))
        transform.moved(
            envelope,
            transform.rotation_between([0.0, 0.0, 1.0], outward),
        )
        envelope.apply_translation(mouth)
        tool = boolean(
            "intersection",
            [tool, MeshData.of(envelope)],
            quality=quality,
            seed=seed,
            cancelled=cancelled,
        ).mesh
    outcome = boolean(
        "union" if cavity else "difference",
        [mesh, tool],
        quality=quality,
        seed=seed,
        cancelled=cancelled,
    )
    return _without_scars(outcome) if cavity else outcome


def _rim_planes(mesh: Mesh, feature: Feature) -> tuple[SectionPlane, ...]:
    """Die Ebenen, in denen eine Bohrung oder ein Langloch endet — oder nichts.

    Dieselbe Messung, mit der *Bohrung ändern* sein Werkzeug begrenzt
    (:func:`_bore_end_planes`, ohne Zugabe): die zwei Randringe der Wand, je
    einer flach. Ein Sackloch nennt so seinen Boden, eine durchgehende Bohrung
    beide Mündungen — schräg oder quer zur Achse, wie sie liegen. Eine Wand
    mit anderen Rändern (angeschnitten, gewölbte Mündung) hat keine solchen
    Ebenen, und dann bleibt es beim bisherigen Weg. Für beide Kerne gefragt,
    am exakten Körper an seinem Netz-Zwilling.
    """
    if feature.kind not in ("hole", "slot") or not feature.face_indices:
        return ()
    body = as_mesh_data(mesh)
    if int(max(feature.face_indices)) >= len(body.raw.faces):
        return ()
    planes = _bore_end_planes(body, feature, {feature.id: feature}, grows=False)
    return planes if len(planes) == 2 else ()


def _longer(feature: Feature) -> Feature:
    """Dasselbe Merkmal mit einer Tiefe, die über jede schräge Mündung hinausreicht.

    Geschnitten wird danach an den Randebenen (:func:`_rim_planes`); bis dahin
    muss der Körper sie an jeder Stelle seines Umfangs überragen. Die Wand
    einer schrägen Bohrung ist in der Achsspanne gemessen, und ein Durchmesser
    mehr deckt jede Neigung, unter der eine Wand noch zwei Mündungen hat.
    """
    depth = float(feature.params.get("depth", 0.0))
    reach = float(feature.params.get("length", 0.0)) or float(feature.params.get("diameter", 0.0))
    return dataclasses.replace(feature, params={**feature.params, "depth": depth + 2.0 * reach})


def _cut_at_the_rims(tool: MeshData, planes: Sequence[SectionPlane]) -> MeshData | None:
    """Ein Werkzeug an einer oder zwischen zwei Randebenen — oder ``None``, wo das
    keinen Körper ergibt."""
    clipped = cut(tool, planes[0], planes[1] if len(planes) > 1 else None)
    body = clipped.mesh
    if not clipped.capped or not body.is_watertight or body.volume <= EPS_GEOM:
        return None
    return body


def _without_scars(outcome: BooleanOutcome) -> BooleanOutcome:
    """Die koplanaren Narben eines Stopfens entfernen — nur, wenn das Netz es hält.

    Ein Stopfen, der eine Bohrung schließt, endet an der Hülle des Teils in
    den Deckelflächen; die Vereinigung lässt dort seine Kappen als Dreiecke
    in der Ebene stehen. Je Versetzen blieben so rund 270 Dreiecke zurück —
    796, 1042, 1308, 1576, 1852 an der Lochplatte nach vier Zügen (Review,
    21.09.2026) — und mit ihnen wuchs jeder spätere Schritt.

    ``Manifold.simplify`` legt koplanare Dreiecke zusammen. Übernommen wird
    das wie in ``boolean._tidied`` nur unter der Zusicherung von ``repair()``:
    Das Netz bleibt dicht, das Volumen ändert sich nicht (``EPS_GEOM``), und
    es werden wirklich weniger Dreiecke. Sonst bleibt die rohe Vereinigung —
    dieselbe Vorsicht, aus der ``_tidied`` das Werkzeug meidet: Es vernetzt
    ebene Flächen neu, und wo es eine Haut stehen ließe, sagt das Volumen es.
    Die Slots gehen danach wie nach jeder Booleschen von der nächsten
    Eingangsfläche auf die neuen Dreiecke über.
    """
    import manifold3d

    from app.core.geom.attributes import transfer

    joined = outcome.mesh
    raw = joined.raw
    if len(raw.faces) == 0 or not raw.is_watertight:
        return outcome
    try:
        body = manifold3d.Manifold(
            manifold3d.Mesh64(
                np.require(raw.vertices, dtype=np.float64, requirements=("C", "W")),
                np.require(raw.faces, dtype=np.uint64, requirements=("C", "W")),
            )
        )
        if body.status() != manifold3d.Error.NoError:
            return outcome
        built = body.simplify(EPS_GEOM).to_mesh64()
    except Exception:  # Der Kern hat eigene Fehlerklassen; die rohe Vereinigung bleibt.
        return outcome
    candidate = trimesh.Trimesh(
        vertices=np.array(built.vert_properties[:, :3], dtype=np.float64, copy=True),
        faces=np.array(built.tri_verts, dtype=np.int64, copy=True),
        process=False,
    )
    # **Ein Volumen wird nicht mit einer Längentoleranz geprüft.** Hier stand
    # ``is_close``, und das vergleicht auf ``EPS_GEOM`` genau — einen
    # Mikrometer, gegen einen Körper von 21 190 Kubikmillimetern gehalten.
    # Die Volumensumme über 66 000 Dreiecke rauscht stärker: Beim Entfernen
    # eines Wabenmusters lagen rohe Vereinigung und zusammengelegtes Netz
    # 7·10⁻⁶ mm³ auseinander, und verworfen wurde dabei ausgerechnet das
    # **genauere** von beiden — es traf das Zylindervolumen exakt, die rohe
    # Vereinigung nicht (gemessen am 22.09.2026). Geprüft wird deshalb am
    # Rauschen der Summe — ``units.VOLUME_SUM_NOISE``, dieselbe Schranke, mit
    # der ``mesh_ops._exactly_flattened`` sein Vorspiel abnimmt; was eine
    # stehengebliebene Haut kostet, liegt um Größenordnungen darüber.
    noise = max(abs(joined.volume), 1.0) * units.VOLUME_SUM_NOISE
    if (
        len(candidate.faces) == 0
        or len(candidate.faces) >= len(raw.faces)
        or not candidate.is_watertight
        or abs(float(candidate.volume) - joined.volume) > noise
    ):
        return outcome
    simplified = transfer(MeshData.of(candidate), [joined])
    return dataclasses.replace(outcome, mesh=simplified)


def _tool_for(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    scale: float = 1.0,
    axis: Vec3 | None = None,
    *,
    alone: bool = False,
    rooted: bool = False,
    quality: Quality = "fine",
    seed: int | None = None,
    cancelled: CancelToken | None = None,
    oversize: float = FEATURE_OVERLAP,
) -> MeshData:
    """Der Werkzeugkörper dieses Merkmals, an ``centre`` gesetzt.

    Bei einer Bohrung wird der tatsächliche Wandmantel an seinen beiden
    Randringen geschlossen. Sonst baut :func:`_feature_solid` parametrische
    Merkmale aus ihren Kennzahlen; übrige Formen kommen aus
    :func:`_feature_body`. Der Körper wird anschließend verschoben, gedreht
    und skaliert.

    ``rooted`` gibt einem **konvexen** Körper aus den Flächen einen Sockel um
    :data:`FEATURE_OVERLAP` in seine Grundfläche (:func:`_rooted`) — für das
    Werkzeug, das an der neuen Stelle **vereinigt** wird. Das Werkzeug, das
    an der alten Stelle **abträgt**, bekommt ihn nicht: Es schnitte sonst eine
    Schicht aus der Grundfläche.

    Baut sich der Körper nicht sicher, endet der Aufruf mit einem Satz, der
    den **heutigen** Grund nennt und nicht den von gestern — siehe
    :data:`NO_OWN_BODY`.
    """
    if feature.kind == "hole" and not hole_is_clear(mesh, feature):
        # Im Zylinder steht Material: eine Radinnenwand mit Speichen oder ein
        # Topf mit Zapfen, kein Bohrungsmantel. Ob die Flächen einen Körper
        # hergeben, ist dann gleich — der Pfropfen schlösse den Zapfen ein,
        # und der Zylinder an der neuen Stelle nähme die Speichen mit. Gefragt
        # wird vor dem Flächenkörper, der hier umsonst gebaut würde.
        raise ValidationError(
            field="at_feature",
            detail=HOLE_IS_NOT_EMPTY,
            values={"feature": feature.id, "kind": feature.kind},
            constraint="not_movable",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    # Beim Versetzen zählt der vorhandene Sehnenzug, nicht der Radius durch
    # die Dreiecksmitten. Sonst schrumpft eine fremd tessellierte Bohrung.
    # Und der Körper aus den Flächen endet bündig in den Oberflächen — als
    # Messer bekommt er an seinen Mündungen den Kragen aus §39
    # (:func:`_past_the_mouths`), damit keine Haut stehen bleibt; als Pfropfen
    # ersetzt ihn :func:`_closed_at` ohnehin durch den Zylinder aus Kennzahlen.
    built = (
        _body_from_faces(mesh, feature.face_indices, allowed_rings=(2,))
        if feature.kind == "hole"
        else None
    )
    if built is not None:
        built = _past_the_mouths(mesh, built)
    if feature.kind == "pin" and rooted:
        # **Ein gesetzter Zapfen ist so hoch wie der gemessene** (22.09.2026).
        # Unverändert kommt er aus seinen Flächen und bekommt unten einen
        # Sockel (:func:`_rooted`); breiter oder gekippt aus Kennzahlen, die
        # Spitze genau auf der alten Höhe und der Fuß so weit in der
        # Grundfläche, wie die Neigung verlangt (:func:`_pin_solid`). Der
        # Zylinder aus Kennzahlen stand vorher 0,02 mm zu hoch und hob gekippt
        # an der hohen Seite von der Platte ab.
        if is_close(scale, 1.0) and axis is None:
            built = _pin_body(mesh, feature)
        else:
            solid = _pin_solid(mesh, feature, centre, scale=scale, axis=axis)
            if solid is not None:
                return solid
    if built is None and feature.kind in PARAMETRIC_KINDS:
        return _feature_solid(feature, centre, scale=scale, axis=axis, oversize=oversize)
    if built is None and feature.kind == "torus":
        # Der Ring am Schaft beschnitten — der Wulst ohne den Schaft, die Kehle
        # nur darin; ein Sockel wäre hier der Schaft selbst.
        built = _torus_tool_mesh(mesh, feature)
        rooted = False

    if built is None:
        built = _feature_body(mesh, feature, alone=alone)
    if built is None:
        raise ValidationError(
            field="at_feature",
            detail=NO_BODY_FROM_FACES if alone else NO_OWN_BODY,
            values={"feature": feature.id, "kind": feature.kind},
            constraint="not_movable",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    if rooted and not is_a_cavity(feature):
        built = _rooted(mesh, feature, built, quality=quality, seed=seed, cancelled=cancelled)

    measured = [float(value) for value in feature.params["centre"]]
    matrix = np.eye(4)
    if axis is not None:
        from_axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
        matrix = np.asarray(
            transform.rotation_between(from_axis, np.asarray(axis, dtype=np.float64)),
            dtype=np.float64,
        )
    body = built.raw.copy()
    body.apply_translation(-np.asarray(measured, dtype=float))
    if not is_close(scale, 1.0):
        body.apply_scale(scale)  # type: ignore[no-untyped-call]
    transform.moved(body, matrix)
    body.apply_translation(np.asarray(centre, dtype=float))
    return MeshData.of(body)


def _pin_body(mesh: MeshData, feature: Feature) -> MeshData | None:
    """Der Zapfen aus seinen eigenen Flächen — Mantel mit Fuß- und Kopfring gedeckelt."""
    if feature.kind != "pin" or not feature.face_indices:
        return None
    return _body_from_faces(mesh, feature.face_indices, allowed_rings=(1, 2))


def _toward_the_air(mesh: MeshData, feature: Feature) -> NDArray[np.float64] | None:
    """Die Achsrichtung vom Material zur Luft: vom Fuß eines Zapfens zu seiner
    Spitze, vom Boden eines Sacklochs zu seiner Mündung.

    Die gemessene Achse trägt kein Vorzeichen, das etwas sagt (sie ist auf
    „größte Komponente positiv" normiert). Gefragt wird der Körper: Hinter dem
    Fuß — dem Boden — liegt Material, hinter der Spitze — der Mündung — Luft;
    dieselbe Probe wie in :func:`_feature_mount`. ``None``, wo beide Enden
    gleich antworten: an einer Durchgangsbohrung und an einem eingeschlossenen
    Hohlraum.
    """
    from app.core.geom.mesh import on_surface

    axis = np.asarray(_feature_direction(feature), dtype=np.float64)
    centre = np.asarray(_bore_vector(feature, "centre"), dtype=np.float64)
    depth = float(feature.params.get("depth", 0.0))
    if depth <= EPS_GEOM:
        return None
    ends = centre + np.array([-1.0, 1.0])[:, None] * axis * (depth / 2.0 + 2.0 * FEATURE_OVERLAP)
    closest, _distance, faces = on_surface(mesh.raw, ends)
    signed = np.einsum("ij,ij->i", ends - closest, np.asarray(mesh.raw.face_normals)[faces])
    inside = signed < -EPS_GEOM
    if bool(inside[0]) == bool(inside[1]):
        return None
    return np.asarray(axis if inside[0] else -axis, dtype=np.float64)


def _pin_solid(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    *,
    scale: float = 1.0,
    axis: Vec3 | None = None,
) -> MeshData | None:
    """Ein Zapfen aus Kennzahlen: die Spitze genau, der Fuß in der Grundfläche.

    Dasselbe wie ``_exact_pin_tool`` am exakten Körper: Gekippt um seine Mitte
    reicht der Zylinder unter die Mitte so weit, wie
    :func:`_reach_past_a_tilted_face` verlangt, und dazu die Zugabe aus §39 —
    alles unterhalb der Grundfläche verschluckt die Vereinigung. Oben endet er
    auf der halben Höhe über der Mitte, wie gemessen. ``None``, wo sich nicht
    sagen lässt, wo der Fuß ist.
    """
    outward = _toward_the_air(mesh, feature)
    if outward is None:
        return None
    measured = np.asarray(_feature_direction(feature), dtype=np.float64)
    turned = measured if axis is None else np.asarray(_feature_direction(feature, axis))
    sign = 1.0 if float(outward @ measured) > 0.0 else -1.0
    tip = turned * sign
    tilt = math.degrees(math.acos(min(1.0, abs(float(measured @ turned)))))
    radius = _bore_number(feature, "diameter") * scale / 2.0
    depth = _bore_number(feature, "depth")
    below = (
        _reach_past_a_tilted_face(depth / 2.0, radius, tilt, at_most=float(mesh.bounds.diagonal))
        + FEATURE_OVERLAP
    )
    body = lathe.cylinder(radius=radius, height=below + depth / 2.0, sections=FEATURE_SECTIONS)
    body.apply_translation((0.0, 0.0, (depth / 2.0 - below) / 2.0))
    transform.moved(body, transform.rotation_between([0.0, 0.0, 1.0], tip))
    body.apply_translation(np.asarray(centre, dtype=float))
    return MeshData.of(body)


def _placing_tool(
    ctx: OpContext,
    body: MeshData,
    source: SceneObject,
    feature: Feature,
    centre: Vec3,
    cavity: bool,
    *,
    scale: float = 1.0,
    axis: Vec3 | None = None,
    alone: bool = True,
) -> MeshData:
    """Das Werkzeug, das ein Merkmal an seiner (neuen) Stelle setzt.

    Ein Hohlraum wird ausgeschnitten, wie gemessen. Ein konvexes Merkmal wird
    vereinigt — mit Sockel in die Grundfläche (:func:`_rooted`) und ohne die
    Hohlräume, die durch es laufen (:func:`_without_cavities`). Beides gilt
    nur dem **Setzen**; das Abtragen an der alten Stelle geht über
    :func:`_closed_at`.
    """
    tool = _tool_for(
        body,
        feature,
        centre,
        scale=scale,
        axis=axis,
        alone=alone,
        rooted=not cavity,
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        oversize=0.0 if feature.kind in {"hole", "pin", "slot"} else FEATURE_OVERLAP,
    )
    if cavity:
        return tool
    return _without_cavities(
        tool,
        source.features,
        feature.id,
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )


def _rooted(
    mesh: MeshData,
    feature: Feature,
    built: MeshData,
    *,
    quality: Quality = "fine",
    seed: int | None = None,
    cancelled: CancelToken | None = None,
) -> MeshData:
    """Ein konvexer Körper aus den Flächen reicht in seine Grundfläche hinein.

    **Gemessen am 15.09.2026 an einem Uhrenteil:** *Merkmal ändern* an einem
    kegeligen Zapfen (90°, Ø 10 auf einer Platte) ließ zwei Komponenten
    zurück — Lauf vollständig, Netz dicht. Der Deckel des gemessenen
    Kegelstumpfs (:func:`_body_from_faces`) liegt **genau** in der
    Grundfläche, und die Vereinigung traf eine zusammenfallende Fläche (§39):
    zwei Schalen, die einander berühren. Bohrung und Zapfen bekommen ihren
    Überstand in :func:`_feature_solid`; die Formen aus den Flächen bekamen
    keinen.

    Der Sockel ist ein Prisma über dem Ring, der auf der Grundfläche liegt
    (:func:`_feature_mount` findet sie: der Materialrand liegt **außerhalb**
    des Rings), um :data:`FEATURE_OVERLAP` in das Material verschoben — nicht
    der ganze Körper verschoben, denn das machte einen aufgeweiteten Kegel
    breiter. Findet sich kein solcher Ring, bleibt der Körper, wie er war.
    """
    from app.core.perceive.relations import boundary_rings, ring_in_order

    try:
        frame = _feature_mount(mesh, feature, (feature,), built)
    except ValidationError:
        return built
    normal = np.asarray(frame.normal, dtype=float)
    origin = np.asarray(frame.origin, dtype=float)
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    for ring in boundary_rings(mesh.raw, feature) or []:
        ordered = ring_in_order(ring)
        if len(ordered) < 3:
            continue
        points = vertices[ordered]
        if float(np.max(np.abs((points - origin) @ normal))) > FLAT_RIM * len(points) ** 0.5:
            continue
        shifted = points - normal * FEATURE_OVERLAP
        count = len(points)
        index = np.arange(count)
        following = (index + 1) % count
        top_hub, bottom_hub = 2 * count, 2 * count + 1
        prism = trimesh.Trimesh(
            vertices=np.vstack(
                (
                    points,
                    shifted,
                    # Diese zwei Mitten werden Eckpunkte — exakt summiert
                    # (RM-187), sonst entscheidet die SIMD-Breite mit.
                    np.array([units.exact_centre(points.tolist())], dtype=np.float64),
                    np.array([units.exact_centre(shifted.tolist())], dtype=np.float64),
                )
            ),
            faces=np.vstack(
                (
                    np.column_stack((index, following, following + count)),
                    np.column_stack((index, following + count, index + count)),
                    np.column_stack((index, following, np.full(count, top_hub))),
                    np.column_stack((index + count, following + count, np.full(count, bottom_hub))),
                )
            ),
            process=True,
        )
        trimesh.repair.fix_normals(prism)  # type: ignore[no-untyped-call]
        if not prism.is_watertight or prism.volume <= EPS_GEOM:
            return built
        return boolean(
            "union", [built, MeshData.of(prism)], quality=quality, seed=seed, cancelled=cancelled
        ).mesh
    return built


def _without_cavities(
    tool: MeshData,
    features: Mapping[str, Feature],
    skip: str,
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
) -> MeshData:
    """Die Hohlräume, die durch ein konvexes Werkzeug laufen, bleiben offen.

    Ein Zapfen oder Kegel, der an seiner neuen Stelle vereinigt wird, ist
    massiv — und eine Bohrung, die durch ihn läuft, wäre danach zu. Gemessen
    am selben Uhrenteil wie in :func:`_rooted`: Die Bohrung Ø 2 durch Platte
    und Kegel war nach *Merkmal ändern* ein Sackloch. Jede Bohrung und jedes
    Langloch, dessen Achse das Werkzeug trifft, wird deshalb aus dem Werkzeug
    herausgeschnitten, bevor es vereinigt wird — mit seinem gemessenen Maß
    (``oversize=0``), damit kein zweites, um die Zugabe weiteres Loch entsteht.
    """
    from app.core.geom.mesh import on_surface

    if not tool.raw.is_watertight:
        return tool
    for identifier, other in features.items():
        if identifier == skip or other.kind not in ("hole", "slot"):
            continue
        centre = other.params.get("centre")
        direction = other.params.get("axis")
        if not isinstance(centre, list | tuple) or not isinstance(direction, list | tuple):
            continue
        axis = np.asarray(direction, dtype=float)
        length = float(np.linalg.norm(axis))
        if length <= EPS_GEOM:
            continue
        axis /= length
        middle = np.asarray(centre, dtype=float)
        reach = float(other.params.get("depth", 0.0) or other.params.get("diameter", 0.0))
        samples = middle + np.linspace(-0.5, 0.5, _CAVITY_AXIS_SAMPLES)[:, None] * reach * axis
        # Innen heißt: der nächste Punkt der Werkzeughaut liegt in Richtung
        # ihrer Normale — derselbe Weg wie in :func:`_feature_mount`, ohne
        # einen Strahlenschnitt, der eine weitere Abhängigkeit bräuchte.
        closest, _distances, faces = on_surface(tool.raw, samples)
        signed = np.einsum("ij,ij->i", samples - closest, np.asarray(tool.raw.face_normals)[faces])
        if not bool(np.any(signed < -EPS_GEOM)):
            continue
        # **Durch das Werkzeug, nicht um es herum.** Ein Zapfen, der in einer
        # großen Bohrung steht (Hemmungsrad 06: Zapfen Ø 9 in der Bohrung
        # Ø 22), hat deren Achse ebenfalls in sich — die Bohrung läuft aber
        # nicht durch ihn, sie umschließt ihn, und der Schneider nähme das
        # ganze Werkzeug mit: „Von dem Körper bleibt nichts übrig."
        relative = np.asarray(tool.raw.vertices, dtype=float) - middle
        along = relative @ axis
        radial = np.linalg.norm(relative - np.outer(along, axis), axis=1)
        if float(other.params.get("diameter", 0.0)) / 2.0 >= float(radial.max()):
            continue
        # Der Schneider reicht über das ganze Werkzeug entlang der Achse — nicht
        # nur über die gemessene Tiefe des Hohlraums: Ein Kegel, der größer
        # wird, wird auch höher, und ein Schneider von gestern ließe oben eine
        # Haut stehen (gemessen 0,05 mm, und die Bohrung war ein Sackloch).
        low, high = float(along.min()), float(along.max())
        mid = middle + axis * (low + high) / 2.0
        cutter = _feature_solid(
            dataclasses.replace(other, params={**other.params, "depth": high - low}),
            (float(mid[0]), float(mid[1]), float(mid[2])),
            oversize=0.0,
        )
        tool = boolean(
            "difference", [tool, cutter], quality=quality, seed=seed, cancelled=cancelled
        ).mesh
    return tool


@dataclasses.dataclass(frozen=True, slots=True)
class FeaturePlacementGeometry:
    """Das vollständige Merkmal im lokalen Mund-/Basisrahmen der Platzierung."""

    mesh: MeshData
    frame: PlaneFrame
    selected_offset: Vec3
    related: tuple[Feature, ...]
    cavity: bool


def _feature_mount(
    mesh: MeshData, feature: Feature, related: tuple[Feature, ...], tool: MeshData
) -> PlaneFrame:
    """Mündung oder Basis aus dem äußeren Rand und seiner angrenzenden Materialfläche.

    Ein Verschlussdeckel des Zapfens oder der Boden eines Sacklochs ist keine
    Ansatzfläche: seine Nachbarflächen liegen innerhalb des Randrings. Der
    Materialrand liegt außerhalb. Bei zwei gleich großen Durchgangsmündungen
    entscheidet die bereits gespeicherte Merkmalsachse die äquivalente Seite.
    """
    from shapely.geometry import Point, Polygon

    from app.core.perceive.relations import boundary_rings, cavity_surface_indices
    from app.core.sketch.planes import frame_of

    # Innere Ringschultern gehören zur Hohlraumhaut. Ohne sie würde ihr
    # größerer Rand eine tiefer liegende Ansatzfläche vortäuschen.
    indices = (
        cavity_surface_indices(mesh, related) if len(related) > 1 else tuple(feature.face_indices)
    )
    combined = dataclasses.replace(feature, face_indices=indices)
    rings = boundary_rings(mesh.raw, combined)
    outward = np.asarray(_feature_direction(feature), dtype=np.float64)
    candidates: list[tuple[float, float, PlaneFrame]] = []
    if rings:
        owners: dict[tuple[int, int], list[int]] = {}
        for index, face in enumerate(mesh.raw.faces):
            for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
                owners.setdefault((min(int(a), int(b)), max(int(a), int(b))), []).append(index)
        selected = set(indices)
        for ring in rings:
            neighbours: dict[int, list[int]] = {}
            adjacent: set[int] = set()
            for a, b in ring:
                neighbours.setdefault(a, []).append(b)
                neighbours.setdefault(b, []).append(a)
                adjacent.update(index for index in owners.get((a, b), ()) if index not in selected)
            first = min(neighbours)
            ordered = [first]
            previous, current = -1, first
            while True:
                following = next(value for value in neighbours[current] if value != previous)
                if following == first:
                    break
                ordered.append(following)
                previous, current = current, following
            points = np.asarray(mesh.raw.vertices, dtype=np.float64)[ordered]
            origin = np.array(units.exact_centre(points.tolist()), dtype=np.float64)
            _, _, directions = np.linalg.svd(points - origin, full_matrices=False)
            normal = directions[-1]
            if np.max(np.abs((points - origin) @ normal)) > EPS_GEOM:
                continue
            trial = frame_of(
                cast(Vec3, tuple(float(value) for value in normal)),
                cast(Vec3, tuple(float(value) for value in origin)),
            )
            xy = np.column_stack(
                ((points - origin) @ trial.x_axis, (points - origin) @ trial.y_axis)
            )
            polygon = Polygon(xy)
            if not polygon.is_valid or polygon.area <= EPS_GEOM:
                continue
            for index in sorted(adjacent):
                other_normal = np.asarray(mesh.raw.face_normals[index], dtype=np.float64)
                if abs(float(other_normal @ normal)) < 1.0 - EPS_GEOM:
                    continue
                centre = np.asarray(mesh.raw.triangles_center[index]) - origin
                if polygon.covers(
                    Point(float(centre @ trial.x_axis), float(centre @ trial.y_axis))
                ):
                    continue
                # Randpunkte sind nicht gleichmäßig verteilt: zusätzliche
                # Dreiecke an einer Seite dürfen den Anschluss nicht versetzen.
                # Rotationsformen verwenden ihren Achsschnitt mit der Ebene;
                # freie Formen den Flächenschwerpunkt des tatsächlichen Rings.
                centroid = polygon.centroid
                mount = (
                    origin
                    + centroid.x * np.asarray(trial.x_axis)
                    + centroid.y * np.asarray(trial.y_axis)
                )
                alignment = float(outward @ other_normal)
                if feature.kind in PARAMETRIC_KINDS and abs(alignment) > EPS_GEOM:
                    axis_centre = np.asarray(feature.params["centre"], dtype=np.float64)
                    mount = (
                        axis_centre
                        + outward * float((origin - axis_centre) @ other_normal) / alignment
                    )
                frame = frame_of(
                    cast(Vec3, tuple(float(value) for value in other_normal)),
                    cast(Vec3, tuple(float(value) for value in mount)),
                )
                candidates.append((float(polygon.area), float(other_normal @ outward), frame))
                break
    if candidates:
        largest = max(area for area, _, _ in candidates)
        return max(
            (entry for entry in candidates if entry[0] >= largest - EPS_GEOM),
            key=lambda entry: entry[1],
        )[2]
    if feature.kind not in PARAMETRIC_KINDS:
        # **Ein Einschluss scheitert hier aus einem anderen Grund**, und
        # :data:`NO_OWN_BODY` benennt ihn falsch: „Dieses Merkmal geht in ein
        # anderes über — eine Senkung über einer Bohrung etwa". Ein Hohlraum
        # ohne Weg nach außen geht in gar nichts über; er hat nur keine
        # Mündung, an der die Platzierung ihn im Bild aufsetzen könnte. Der
        # Weg bleibt trotzdem offen — über die Zahlen im Dialog (gemessen
        # 10.09.2026: Volumen auf 0,000000 mm³ genau erhalten).
        detail = _NO_MOUTH_TO_GRIP if feature.kind == "void" else NO_OWN_BODY
        raise ValidationError(field="at_feature", detail=detail, constraint="not_movable")
    # Parametrische Altmerkmale können ohne Dreieckszuordnung vorliegen. Die
    # Materialseite ihrer beiden Enden entscheidet auch bei einem Zapfen an
    # der Unterseite. Eine freie Form bekommt diesen Ersatz nie.
    centre = np.asarray(feature.params["centre"], dtype=np.float64)
    depth = float(feature.params.get("depth", 0.0))
    if depth <= EPS_GEOM:
        projected = (np.asarray(tool.raw.vertices) - centre) @ outward
        depth = float(np.ptp(projected))
    from app.core.geom.mesh import on_surface

    ends = centre + np.array([-1.0, 1.0])[:, None] * outward * (depth / 2.0 + EPS_GEOM * 16.0)
    closest, _, faces = on_surface(mesh.raw, ends)
    signed = np.einsum("ij,ij->i", ends - closest, np.asarray(mesh.raw.face_normals)[faces])
    inside = signed < -EPS_GEOM
    if inside.all():
        raise ValidationError(field="at_feature", detail=NO_OWN_BODY, constraint="not_movable")
    if inside[1] and not inside[0]:
        outward = -outward
    origin = centre + outward * depth / 2.0 * (1.0 if is_a_cavity(feature) else -1.0)
    return frame_of(
        cast(Vec3, tuple(float(value) for value in outward)),
        cast(Vec3, tuple(float(value) for value in origin)),
    )


def feature_placement_geometry(
    source: SceneObject, feature: Feature, operation: str
) -> FeaturePlacementGeometry:
    """Eine einzelne belegte Form oder ihre vollständige zusammenhängende Bohrkette."""
    from app.core.perceive.relations import cavity_chain_state_at

    feature = _movable_feature(source, feature.id, operation)
    body = as_mesh_data(source.mesh)
    state = cavity_chain_state_at(feature, source.features, body)
    chain = state.chain
    if (refused := cavity_refusal(state)) is not None:
        raise ValidationError(field="at_feature", detail=refused, constraint="not_movable")
    centre = cast(Vec3, tuple(float(value) for value in feature.params["centre"]))
    related = chain or (feature,)
    built = (
        _paired_cavity_body(body, *chain)
        if chain
        else _tool_for(body, feature, centre, alone=True, rooted=True)
    )
    if built is None:
        raise ValidationError(field="at_feature", detail=NO_OWN_BODY, constraint="not_movable")
    frame = _feature_mount(body, feature, related, built)
    rotation = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    to_local = np.eye(4)
    to_local[:3, :3] = rotation.T
    to_local[:3, 3] = -rotation.T @ np.asarray(frame.origin)
    local = built.raw.copy()
    transform.moved(local, to_local)
    offset = rotation.T @ (np.asarray(centre) - frame.origin)
    return FeaturePlacementGeometry(
        MeshData.of(local),
        frame,
        cast(Vec3, tuple(float(value) for value in offset)),
        related,
        is_a_cavity(feature),
    )


def _place_oriented_feature(ctx: OpContext, *, duplicate: bool) -> OpResult:
    """Der freie Platzierungsweg; alte Nullnormalen bleiben im bisherigen Ablauf."""
    from app.core.sketch.planes import frame_of

    params = cast(MoveFeatureParams | DuplicateFeatureParams, ctx.params)
    source = ctx.inputs[0]
    operation = "duplicate_feature" if duplicate else "move_feature"
    feature = _movable_feature(source, params.at_feature, operation)
    geometry = feature_placement_geometry(source, feature, operation)
    target = np.asarray((params.x, params.y, params.z), dtype=np.float64)
    frame = frame_of((params.nx, params.ny, params.nz), (params.x, params.y, params.z))
    new_rotation = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    old_rotation = np.column_stack(
        (geometry.frame.x_axis, geometry.frame.y_axis, geometry.frame.normal)
    )
    delta_rotation = new_rotation @ old_rotation.T
    old_centre = np.asarray(feature.params["centre"], dtype=np.float64)
    to_world = np.eye(4)
    to_world[:3, :3] = new_rotation
    to_world[:3, 3] = target - new_rotation @ np.asarray(geometry.selected_offset)
    if np.allclose(delta_rotation, np.eye(3), atol=EPS_GEOM, rtol=0.0) and np.allclose(
        target, old_centre, atol=EPS_GEOM, rtol=0.0
    ):
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code=f"{operation}.unchanged",
                    severity="info",
                    message=_("Das Merkmal liegt schon dort — nichts zu versetzen."),
                    feature_ids=(feature.id,),
                )
            ],
        )
    tool = geometry.mesh.raw.copy()
    transform.moved(tool, to_world)
    body = as_mesh_data(source.mesh)
    findings: list[Finding] = []
    closed_solver = None
    if not duplicate:
        if len(geometry.related) > 1:
            old_matrix = np.eye(4)
            old_matrix[:3, :3] = old_rotation
            old_matrix[:3, 3] = geometry.frame.origin
            old_tool = geometry.mesh.raw.copy()
            transform.moved(old_tool, old_matrix)
            closed = boolean(
                "union",
                [body, MeshData.of(old_tool)],
                quality=ctx.quality,
                seed=ctx.seed,
                cancelled=ctx.cancelled,
            )
        else:
            closed = _closed_at(
                body,
                feature,
                cast(Vec3, tuple(float(value) for value in old_centre)),
                geometry.cavity,
                quality=ctx.quality,
                seed=ctx.seed,
                cancelled=ctx.cancelled,
                alone=True,
            )
        body, closed_solver = closed.mesh, closed.solver
        findings.extend(closed.findings)
    kind: BooleanKind = "difference" if geometry.cavity else "union"
    placing = MeshData.of(tool)
    if not geometry.cavity:
        placing = _without_cavities(
            placing,
            source.features,
            feature.id,
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
    placed = boolean(
        kind, [body, placing], quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled
    )
    findings.extend(placed.findings)
    if duplicate:
        nothing = without_effect(source.mesh, placed.mesh, kind, ctx.profile)
        if nothing is not None:
            findings.append(nothing)
    features = _without_old_triangles(source.features)
    reserved = {*source.reserved_feature_ids, *source.features}
    set_features: list[Feature] = []
    for related in geometry.related:
        centre = target + delta_rotation @ (
            np.asarray(related.params["centre"], dtype=np.float64) - old_centre
        )
        values = {**related.params, "centre": tuple(float(value) for value in centre)}
        for name in ("axis", "normal"):
            if name in related.params:
                vector = delta_rotation @ np.asarray(related.params[name], dtype=np.float64)
                values[name] = tuple(float(value) for value in vector)
        identifier = related.id
        if duplicate:
            identifier = _free_feature_id(
                dataclasses.replace(
                    source, features=features, reserved_feature_ids=tuple(sorted(reserved))
                ),
                related.kind,
            )
        moved = dataclasses.replace(
            related,
            id=identifier,
            params=values,
            face_indices=(),
            surface_patches=(),
            provenance="generated",
        )
        lost = _throughness_lost(
            placed.mesh,
            moved,
            values["centre"],
            operation,
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
            tool=placing,
        )
        findings.extend(lost)
        if lost:
            moved = dataclasses.replace(moved, params={**values, "through": False})
        features[identifier] = moved
        reserved.add(identifier)
        set_features.append(moved)
    findings.extend(_edge_findings(body, set_features))
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features=features,
                reserved_feature_ids=tuple(sorted(reserved)),
            )
        ],
        solver=deepest((closed_solver, placed.solver)),
        findings=findings,
    )


@op_params
class FeaturePlacementParams(BaseParams):
    """Freie Zielrichtung; ein Nullvektor bewahrt die bisherige reine Verschiebung."""

    nx: float = param(
        title=_("Richtung X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Freie Richtung am neuen Ort. Null in allen drei Feldern erhält die bisherige Richtung."
        ),
    )
    ny: float = param(
        title=_("Richtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Weitere Achse der Richtung — siehe Richtung X."),
    )
    nz: float = param(
        title=_("Richtung Z"),
        default=0.0,
        placement="advanced",
        doc=_("Weitere Achse der Richtung — siehe Richtung X."),
    )


@op_params
class MoveFeatureParams(FeaturePlacementParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_(
            "Das erkannte Merkmal, das versetzt wird. Ein Klick darauf im Objektbaum "
            "oder in der Ansicht wählt es aus."
        ),
    )
    x: float = param(
        title=_("X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_("Die neue Mitte des Merkmals. Beim Anklicken steht hier seine heutige."),
    )
    y: float = param(
        title=_("Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_("Die neue Mitte des Merkmals. Beim Anklicken steht hier seine heutige."),
    )
    z: float = param(
        title=_("Z"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_("Die neue Mitte des Merkmals. Beim Anklicken steht hier seine heutige."),
    )


def _movable_feature(source: SceneObject, name: str, op: str) -> Feature:
    """Das gewählte Merkmal — oder ein Satz, warum es nicht geht (Regel 17).

    **Gefragt wird das Register, und zwar nach der aufrufenden Operation.**
    ``applies_to`` sagt je Operation, welche Merkmalsarten sie annimmt, und es
    stand bis zum 03.09.2026 nur im Menü und im Panel: Wer eine Operation über
    Chat oder Kommandozeile rief, kam daran vorbei. Gemessen an jenem Tag
    kostete das zwei stille Falschergebnisse — ``resize_feature`` änderte eine
    **Bohrung** am exakten Kern und an der Materialkompensation vorbei
    (46 997,6 auf 45 737,0 mm³), und ``rotate_feature`` kippte eine **Kuppel**,
    die keine Lage hat, und nahm dabei 112 von 24 448 mm³ mit. Beide Male blieb
    der Körper wasserdicht, und nichts wurde rot.

    Der Satz dazu kommt aus derselben Tabelle, aus der das Panel seine
    ausgegraute Zeile beschriftet — ``perceive.actions.reason_against``.
    """
    from app.core.perceive.actions import cone_piece_blocked, reason_against

    feature = source.features.get(name)
    if feature is None:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
            values={"feature": name, "object": source.id},
            constraint="unknown_feature",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    # Ein Kegelstück ohne eigenen Körper: derselbe Satz wie im Panel, bevor
    # ``_body_from_faces`` an seinem Rand scheitert.
    against = cone_piece_blocked(feature) or reason_against(op, feature.kind)
    if against is None:
        return feature
    raise ValidationError(
        field="at_feature",
        detail=against,
        values={"feature": name, "kind": feature.kind, "op": op},
        constraint="not_movable",
    )


#: Wenn die Flächen eines beweglichen Merkmals es nicht als eigenen Körper
#: begrenzen.
#:
#: Hier stand bis zum 03.09.2026 eine zweite Ausgabe der Gründetabelle aus
#: ``perceive.actions`` — dieselben fünf Sätze, zweimal im Programm, und in
#: beiden dieselben zwei veraltet. Was den Kunden erreicht, kommt jetzt aus
#: einer Quelle; hier bleibt der eine Fall, den das Panel nicht kennt, weil er
#: nicht an der Merkmalsart hängt, sondern am Netz.
#:
#: ``move_feature`` fängt die erkannte Kette aus Bohrung und Senkungen vor
#: ``_tool_for`` ab und versetzt ihren gemeinsamen Hohlraum. Dieser Satz
#: bleibt für Netze, auf denen die Beziehung nicht eindeutig erkannt werden
#: kann, und für die Handlungen, die keinen eigenen Werkzeugkörper finden.
#: Dort trägt weiter nur der gemessene Weg über Zahlen: ein Stopfen mit dem
#: Durchmesser der Senkung über die volle Wandstärke schließt beides in einem
#: Zug.
#: Warum an einem Ring nichts einzeln geht: Seine Ringfläche ist der ganze
#: Körper — ein Ring als eigener Körper, kein Wulst auf einem Schaft.
TORUS_IS_THE_BODY: Final = _("Dieser Ring ist der ganze Körper. Bewegen Sie den Körper.")

#: Und der Fall daneben: Die Ringfläche hat Ränder, aber der Körper geht
#: hinter ihr nicht weiter — ein Torusstück, hinter dem sich die Nachbarn
#: nicht treffen (exakt: das Defeaturing gibt auf), oder Randringe, die keine
#: zwei gleichen Kreise um die Achse sind (am Netz).
TORUS_NOT_SEPARABLE: Final = _(
    "Diese Ringfläche lässt sich nicht vom Körper trennen. "
    "Wählen Sie den ganzen Wulst oder die ganze Kehle."
)

TORUS_TUBE_TOO_WIDE: Final = _("Der Rohrdurchmesser muss kleiner als der Ringdurchmesser sein.")

#: Das Bausteingewinde ist rechtsgängig (``shapes.thread_body``); ein linkes
#: neu zu schneiden hieße, es zu spiegeln — das tut hier niemand still.
THREAD_LEFT_HANDED: Final = _(
    "Ein linksgängiges Gewinde lässt sich hier nicht neu schneiden. Setzen Sie es als Baustein neu."
)

#: Die Gangtiefe ist ``RIDGE_SHARE`` Steigungen; über dem halben Nennmaß bliebe außen
#: kein Kern und innen keine Bohrung — dieselbe Ungleichung für beide Seiten.
THREAD_PITCH_TOO_STEEP: Final = _(
    "Die Steigung passt nicht zum Durchmesser. Wählen Sie eine kleinere Steigung."
)

#: Ein Gewinde ohne bewendelte Strecke hat keinen Ort, an dem ein Werkzeug ansetzt.
THREAD_WITHOUT_LENGTH: Final = _(
    "Dieses Gewinde nennt keine Strecke. Ändern Sie den Schritt, der es erzeugt hat, "
    "oder setzen Sie es als Baustein neu."
)

#: Ein Ring oder Gewinde ohne gemessene Achse hat keine Lage, an der ein
#: Werkzeug ansetzen könnte — bis zum 21.09.2026 stand dann still die Z-Achse
#: da, und der Ring wurde an einer Stelle bearbeitet, die niemand gemessen hat.
FEATURE_WITHOUT_AXIS: Final = _(
    "Dieses Merkmal nennt keine Achse. Wählen Sie ein erkanntes Merkmal mit gemessener "
    "Achse oder erkennen Sie die Merkmale neu."
)

#: Das Bausteingewinde hat einen Gang je Umlauf (``build.threaded``); ein zweigängiges
#: neu zu schneiden machte still ein eingängiges daraus — dieselbe Absage wie links.
THREAD_MULTI_START: Final = _(
    "Ein mehrgängiges Gewinde lässt sich hier nicht neu schneiden. Setzen Sie es als Baustein neu."
)

#: Die Werkzeuge der Gewindehandlungen sind Zylinder (Hülle, Kern, Füllung).
#: An einem kegeligen Gewinde (P2.5, Rohrgewinde) trügen sie ein Ende ab und
#: ließen das andere stehen — dann lieber die Absage.
THREAD_TAPERED: Final = _(
    "Ein kegeliges Gewinde lässt sich hier weder ändern noch entfernen. "
    "Wählen Sie ein anderes Merkmal."
)

NO_OWN_BODY: Final = _(
    "Dieses Merkmal geht in einen anderen Hohlraum über, etwa eine Senkung in ihre "
    "Bohrung. Verschließen Sie beide zusammen mit „Bohrung verschließen“ und setzen "
    "Sie es dann neu."
)

#: Und der Satz für den Fall daneben: Die Ränder des Merkmals ergeben keine
#: Ringe — veraltete Flächennummern, eine Naht mit drei Dreiecken, ein Fleck
#: ohne Rand (``relations.CavityState``, ``cavity_topology_unavailable``). Ob
#: ein Nachbar den Hohlraum teilt, weiß dann niemand, und „geht in einen
#: anderen Hohlraum über" wäre eine Behauptung. Dasselbe Wort steht im
#: Merkmalfenster an der Gruppenzeile.
CAVITY_TOPOLOGY_UNKNOWN: Final = _(
    "Die Ränder dieses Merkmals sind nicht sicher erkannt. Reparieren Sie das Netz und "
    "wählen Sie das Merkmal danach neu."
)


def cavity_refusal(state: CavityState) -> TranslatableText | None:
    """Der Satz, mit dem eine Körperhandlung an diesem Hohlraum absagt — oder ``None``.

    Eine Kette ist keine Absage: Versetzen, Drehen und Verdoppeln nehmen sie
    mit. Ohne Kette entscheidet der Grund aus :func:`cavity_chain_state_at`.
    """
    if state.chain is not None or not state.touches_other:
        return None
    if state.reason == "cavity_topology_unavailable":
        return CAVITY_TOPOLOGY_UNKNOWN
    return NO_OWN_BODY


#: Warum ein Kegel oder eine Kuppel aus ihren Flächen kein Werkzeug hergibt: Der
#: Rand hat mehr Ringe als ein einzelnes Merkmal oder liegt in keiner Ebene
#: (``_body_from_faces``) — ein Kegelstumpf mit einer Querbohrung durch seinen
#: Mantel etwa (Uhrenteil 16, 15.09.2026). Der Satz steht in der Operation und
#: in der grauen Zeile des Panels (``perceive.actions.no_own_body``).
NO_BODY_FROM_FACES: Final = _(
    "Aus den Flächen dieses Merkmals entsteht kein eigener Körper; sein Rand ist "
    "nicht eindeutig. Ändern Sie den Schritt, aus dem es stammt."
)


#: Warum eine „Bohrung", in der Material steht, sich nicht als Bohrung
#: bearbeiten lässt: Die Innenwand eines Rades mit Speichen und Nabe hat
#: dieselbe Gestalt wie ein Bohrungsmantel, aber ihre Flächen schließen sich
#: zu keinem Körper — und das Werkzeug aus Kennzahlen wäre ein voller
#: Zylinder, der die Speichen mitnimmt (Uhrenteil 06, Ø 66,8: minus 49
#: Prozent Volumen und drei lose Teile nach einem Versetzen um 1,5 mm,
#: gemessen 15.09.2026). Der Satz steht in der Operation (``_tool_for``) und
#: in der grauen Zeile des Panels (``perceive.actions.no_own_body``).
HOLE_IS_NOT_EMPTY: Final = _(
    "In dieser Bohrung steht Material; sie ist eine Wand, keine Bohrung. "
    "Bearbeiten Sie ihre Flächen einzeln."
)

#: Wie weit innerhalb des gemessenen Radius :func:`hole_is_clear` nach
#: Dreiecksmitten sucht — die eigene Wand liegt auf dem Radius, ein Steg,
#: eine Nabe oder ein Zapfen deutlich darunter.
_CLEARANCE_MARGIN: Final = 0.02

#: Wie viele Punkte :func:`_without_cavities` entlang der Achse eines fremden
#: Hohlraums über dessen Tiefe verteilt, um zu fragen, ob er das Werkzeug
#: durchläuft.
_CAVITY_AXIS_SAMPLES: Final = 9


def hole_is_clear(mesh: MeshData, feature: Feature) -> bool:
    """Ob der Zylinder dieser Bohrung leer ist — oder ob darin Material steht.

    Material im Zylinder hat eine Oberfläche im Zylinder: Gesucht werden
    Dreiecksmitten des Körpers, die entlang der Achse zwischen den Mündungen
    und quer dazu innerhalb des Radius liegen — abzüglich der eigenen
    Mantelflächen und eines schmalen Saums am Radius, auf dem die Wand selbst
    steht. Der Boden eines Sacklochs liegt auf der Mündungsebene — bis auf die
    Zugabe aus §39, denn ein float32-Netz trifft die Ebene nicht auf den
    Nanometer — und zählt nicht. Eine Stichprobe von Punkten hatte zuerst hier gestanden und
    die zwölf radialen Stege im Becher eines Minigolf-Satzes zwischen ihren
    Winkeln durchgelassen (3 719 mm³ Material im Zylinder, gemessen
    15.09.2026); die Dreiecksmitten übersehen keinen Steg, und sie kosten
    eine Rechnung über das Netz statt einer Suche je Punkt.

    Ohne Maße gilt die Bohrung als leer — dann entscheidet der Körper aus
    ihren Flächen.

    **Gemerkt je Körper und Bohrung** (``features.remembered``): Das
    Merkmalfenster fragt es bei jedem Klick auf eine Bohrung zweimal
    (``actions.no_own_body``), und jede Antwort kostete an der Lochplatte mit
    360 000 Dreiecken 90 ms — die Endebenen verschweißen dafür eine Kopie des
    Netzes. Die Antwort ist eine reine Funktion aus Netz, Flächen, Achse, Mitte
    und Maßen; sie stirbt mit dem Körper.
    """
    radius = float(feature.params.get("diameter", 0.0)) / 2.0
    depth = float(feature.params.get("depth", 0.0))
    if radius <= EPS_GEOM or depth <= EPS_GEOM:
        return True
    from app.core.perceive.features import remembered

    centre = tuple(float(value) for value in feature.params["centre"])
    axis = tuple(float(value) for value in feature.params.get("axis", (0.0, 0.0, 1.0)))
    clear: bool = remembered(
        "hole_is_clear",
        mesh.raw,
        feature.face_indices,
        lambda: _hole_is_clear_read(mesh, feature, radius, depth),
        extra=(feature.kind, centre, axis, radius, depth),
    )
    return clear


def _hole_is_clear_read(mesh: MeshData, feature: Feature, radius: float, depth: float) -> bool:
    """Der Rumpf von :func:`hole_is_clear` — die Rechnung über die Dreiecksmitten."""
    centre = np.asarray(feature.params["centre"], dtype=np.float64)
    axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 1.0)), dtype=np.float64)
    axis /= max(float(np.linalg.norm(axis)), EPS_GEOM)
    raw = mesh.raw
    middles = np.asarray(raw.triangles_center, dtype=np.float64) - centre
    along = middles @ axis
    low, high = -depth / 2.0, depth / 2.0
    if feature.face_indices:
        chosen = np.asarray(feature.face_indices, dtype=np.int64)
        if chosen.size and int(chosen.max()) < len(raw.faces):
            rim = (
                np.asarray(raw.vertices, dtype=np.float64)[np.unique(np.asarray(raw.faces)[chosen])]
                - centre
            ) @ axis
            low, high = float(rim.min()), float(rim.max())
    radial = np.linalg.norm(middles - np.outer(along, axis), axis=1)
    slack = FEATURE_OVERLAP
    inside = (
        (along > low + slack)
        & (along < high - slack)
        & (radial < radius * (1.0 - _CLEARANCE_MARGIN))
    )
    planes = _bore_end_planes(mesh, feature, {feature.id: feature}, grows=False)
    if planes:
        inside = radial < radius * (1.0 - _CLEARANCE_MARGIN)
        for plane in planes:
            inside &= (
                np.asarray(raw.triangles_center) @ np.asarray(plane.normal) < plane.position - slack
            )
    if feature.face_indices:
        own = np.asarray(feature.face_indices, dtype=np.int64)
        inside[own[own < len(inside)]] = False
    return not bool(inside.any())


def has_own_body(mesh: MeshData, feature: Feature, *, alone: bool) -> bool:
    """Ob aus den Flächen dieses Merkmals ein Körper entsteht — die Frage, die
    :func:`_tool_for` stellt, für das Panel vorab beantwortet.

    **Gemerkt je Körper, Flächen und ``alone``** (``features.remembered``),
    wie :func:`hole_is_clear`: Das Merkmalfenster fragt es bei jedem Klick auf
    einen Kegel oder eine Kuppel, und jeder Bau richtete die Flächen neu aus
    (``fix_normals``) — am Sieb aus ``Siebhalter+X1C.3mf`` mit 1 484
    Dreiecken 200 ms je Klick (RM-181, gemessen am 22.09.2026). Die Antwort
    hängt allein an Netz, Flächen und ``alone`` (:func:`_feature_body`).
    """
    from app.core.perceive.features import remembered

    own: bool = remembered(
        "has_own_body",
        mesh.raw,
        feature.face_indices,
        lambda: _feature_body(mesh, feature, alone=alone) is not None,
        extra=alone,
    )
    return own


#: Warum *Zum Langloch ziehen* an einem geteilten Hohlraum absagt — an der
#: Bohrung wie an ihrer Senkung (``slot_hole``). Das Merkmalfenster sagt es an
#: der Zeile (``perceive.actions``), bevor jemand klickt — derselbe Satz wie
#: hier beim Rechnen. Der Weg, den er nennt, führt zum Ziel: Ohne Senkung ist
#: die Bohrung ein Hohlraum für sich, und der lässt sich ziehen; die Senkung
#: kommt danach wieder darauf. *Drehen* und *Verdoppeln* standen bis zum
#: 15.09.2026 mit auf dieser Liste; seither nehmen sie die Kette mit
#: (:func:`_rotate_cavity_chain`, :func:`_duplicate_cavity_chain`, RM-172).
NEEDS_A_PLAIN_BORE: Final = _(
    "Diese Bohrung ist mit weiteren Hohlraumabschnitten verbunden. "
    "Entfernen Sie zuerst die Senkung, oder wählen Sie eine Bohrung ohne Senkung."
)

#: Und warum ein **Einschluss** dieselbe Stelle trifft, aber aus anderem Grund.
#:
#: Die Platzierung setzt ein Werkzeug auf einer Mündung auf; ein Hohlraum ohne
#: Weg nach außen hat keine. Das ist keine Absage an die Handlung — sie geht
#: über die Zahlen im Dialog, gemessen am 10.09.2026 mit einer Volumendifferenz
#: von 0,000000 mm³ —, sondern nur an den Weg über den Klick ins Bild.
_NO_MOUTH_TO_GRIP: Final = _(
    "Dieser Hohlraum liegt ganz im Material und hat keine Mündung, an der er "
    "sich im Bild anfassen ließe. Tragen Sie die neue Stelle als Zahlen in den "
    "Dialog ein — versetzt wird er dabei vollständig."
)


@register_op(
    name="move_feature",
    # 2: eine schräge Bohrung schließt an ihren Randebenen (22.09.2026).
    # 3: die Kette schließt ohne Narben, der Sackboden reist mit, und eine
    # gekippte Sackbohrung bleibt über ihrem Boden (23.09.2026).
    cache_version="3",
    title=_("Merkmal verschieben"),
    category="holes",
    params=MoveFeatureParams,
    consumes=1,
    produces=1,
    applies_to=list(MOVABLE_KINDS),
    touches_features=True,
    deterministic=False,
    doc=_(
        "Versetzt ein erkanntes Merkmal an eine andere Stelle: Bohrung, Langloch, "
        "Zapfen, Senkung, Verjüngung, Kuppel, Pfanne, Wulst, Kehle oder Lufteinschluss."
    ),
)
def move_feature(ctx: OpContext) -> OpResult:
    """Ein erkanntes Merkmal an eine andere Stelle — in einem Schritt.

    **Der Kunde hat es verlangt, und der Umweg war schlecht.** „Move existing
    holes and other recognised details/features" war bei 1 von 5 der einzige
    konkrete Punkt der Umfrage vom 03.09.2026. Möglich war es vorher nur über
    zwei Schritte: verschließen und an neuen Zahlen neu bohren. Das ergibt
    dieselbe Geometrie und ein **anderes** Merkmal — jede Passung, die auf die
    alte Kennung zeigte, verlor ihren Bezug (``fit.missing_feature``).

    **Innen ist es dasselbe Paar wie beim Löschen und beim Ändern**: An der
    alten Stelle das Gegenteil dessen, was das Merkmal ist, an der neuen das
    Merkmal selbst. Ein Hohlraum wird also gefüllt und neu ausgeschnitten, ein
    Zapfen abgetragen und neu angesetzt. Eine Bohrung mit Senkung bildet dabei
    einen gemeinsamen, aus allen verbundenen Flächengruppen geschlossenen
    Hohlraum; unabhängig vom gewählten Abschnitt reisen alle Kennungen und
    Mittelpunkte mit.
    Alle Wege gehen über die Boolesche Rückfallkette, und die benutzte Stufe
    steht im Ergebnis (§39).

    Die Kennung reist mit: Sie ist das Einzige, was den Unterschied zum Umweg
    von Hand ausmacht.
    """
    params = cast(MoveFeatureParams, ctx.params)
    if np.linalg.norm((params.nx, params.ny, params.nz)) > EPS_GEOM:
        return _place_oriented_feature(ctx, duplicate=False)
    source = ctx.inputs[0]
    feature = _movable_feature(source, params.at_feature, "move_feature")
    from app.core.perceive.relations import cavity_chain_state_at

    # **Erst in eine Liste, dann drei Werte einzeln.** Ein Generatorausdruck über
    # die Achsen hat für mypy keine feste Länge; ``Vec3`` verlangt genau drei.
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])
    target: Vec3 = (params.x, params.y, params.z)

    if all(is_close(a, b) for a, b in zip(centre, target, strict=True)):
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="move_feature.unchanged",
                    severity="info",
                    message=_("Das Merkmal liegt schon dort — nichts zu versetzen."),
                    feature_ids=(feature.id,),
                )
            ],
        )

    body = as_mesh_data(source.mesh)
    state = cavity_chain_state_at(feature, source.features, body)
    chain = state.chain
    if (refused := cavity_refusal(state)) is not None:
        raise ValidationError(
            field="at_feature",
            detail=refused,
            values={"feature": feature.id},
            constraint="not_movable",
        )
    if feature.kind == "torus":
        return _move_torus(ctx, source, feature, centre, target)
    if source.kind == "brep" and chain is None and feature.kind in EXACT_CAVITY_KINDS:
        return _exact_move_cavity(ctx, source, feature, centre, target)
    if source.kind == "brep" and chain is not None:
        return _exact_move_chain(ctx, source, feature, chain, target)
    if source.kind == "brep" and feature.kind in EXACT_FACE_KINDS:
        return _exact_move_by_faces(
            ctx, source, feature, centre, target, cavity=is_a_cavity(feature)
        )
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    travel = np.asarray(target, dtype=float) - np.asarray(centre, dtype=float)
    if chain is not None:
        bore, widening = chain[0], chain[-1]
        # **Wo die Flächen keinen Körper hergeben, gelten die Kennzahlen** — wie
        # beim Verdoppeln und beim Kippen derselben Kette (25.09.2026). Am
        # Gartenschlauchhalter kippten zwei Senkbohrungen, und dieselben zwei
        # ließen sich nicht versetzen: „geht in einen anderen Hohlraum über".
        # Gefüllt wird mit dem Stopfen (:func:`_cavity_plug`), geschnitten mit
        # dem Werkzeug der Kopie (:func:`_chain_copy_tool`); wo die Flächen
        # tragen, sind beide der Flächenkörper wie bisher.
        cavity_body = _cavity_plug(
            body, chain, quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled
        )
        if cavity_body is None:
            raise ValidationError(
                field="at_feature",
                detail=NO_OWN_BODY,
                values={"feature": feature.id, "bore": bore.id, "widening": widening.id},
                constraint="not_movable",
            )
        # Ohne Narben (:func:`_without_scars`): Die Kappen des Stopfens blieben
        # sonst als Dreiecke in der Oberseite stehen — an der Senkbohrung
        # 304 → 470 Dreiecke beim ersten Versetzen, und nach dem Entfernen
        # trug eine Platte aus zwölf Dreiecken 374 (gemessen 23.09.2026).
        closed = _without_scars(
            boolean(
                "union",
                [body, cavity_body],
                quality=ctx.quality,
                seed=ctx.seed,
                cancelled=ctx.cancelled,
            )
        )
        # **Mit Zugabe an den Mündungen, nicht bündig** (§39). Der exakte
        # Hohlraum endet genau in den Oberflächen, und die Differenz ließ an
        # der neuen Stelle eine Haut von 5 µm über der Mündung stehen — die
        # Bohrung meldete sich als nicht mehr durchgehend (gemessen 15.09.2026
        # beim Bau von RM-172: 0,25 mm³ im Schlauch bei z = 4,995 … 5,0). Das
        # Werkzeug aus Kennzahlen, das den Tag lang hier stand, nahm dafür
        # den Umkreis seines Vielecks mit und trug je Versetzen bis zu einem
        # Kubikmillimeter mehr ab, als der Pfropfen zurückgab (sieben Tests
        # der Senkungsübergänge rot). Verlängert wird deshalb der exakte
        # Körper selbst — nur an den Mündungen, nie am Boden.
        shifted_cavity = _chain_copy_tool(ctx, body, feature, chain).raw.copy()
        shifted_cavity.apply_translation(travel)
        cutting = MeshData.of(shifted_cavity)
        ctx.progress(0.6, str(_("Das Merkmal wird an seiner neuen Stelle gesetzt …")))
        placed = boolean(
            "difference",
            [closed.mesh, cutting],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        features = _without_old_triangles(source.features)
        for related in chain:
            related_centre = np.asarray(related.params["centre"], dtype=float) + travel
            features[related.id] = dataclasses.replace(
                features[related.id],
                params={
                    **related.params,
                    "centre": tuple(float(value) for value in related_centre),
                },
                provenance="generated",
            )
        floor = _floor_carried(body, bore, source.features, translation(travel))
        if floor is not None:
            features[floor.id] = floor
        through_feature = bore
        set_features = [features[related.id] for related in chain]
        features.update(
            _measured_on(
                placed.mesh, set_features, check_cancelled=ctx.cancelled.raise_if_cancelled
            )
        )
        bore_target = np.asarray(bore.params["centre"], dtype=float) + travel
        through_target: Vec3 = (
            float(bore_target[0]),
            float(bore_target[1]),
            float(bore_target[2]),
        )
    else:
        cavity = is_a_cavity(feature)
        closed = _closed_at(
            body,
            feature,
            centre,
            cavity,
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
            alone=True,
        )
        ctx.progress(0.6, str(_("Das Merkmal wird an seiner neuen Stelle gesetzt …")))
        cutting = _placing_tool(ctx, body, source, feature, target, cavity)
        placed = boolean(
            "difference" if cavity else "union",
            [closed.mesh, cutting],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        features = _without_old_triangles(source.features)
        moved = dataclasses.replace(
            features[feature.id],
            params={**feature.params, "centre": target},
            provenance="generated",
        )
        features[feature.id] = moved
        if cavity:
            features.update(
                _measured_on(placed.mesh, [moved], check_cancelled=ctx.cancelled.raise_if_cancelled)
            )
        floor = _floor_carried(body, feature, source.features, translation(travel))
        if floor is not None:
            features[floor.id] = floor
        through_feature = feature
        through_target = target
        set_features = [moved]

    findings = [*closed.findings, *placed.findings]
    findings += _edge_findings(closed.mesh, set_features)
    # Auch quer kann die Wand dicker werden. Die tatsächliche Zielgeometrie
    # entscheidet; die Bewegungsrichtung allein beweist keinen Durchgang.
    lost = _throughness_lost(
        placed.mesh,
        through_feature,
        through_target,
        "move_feature",
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        tool=cutting,
    )
    findings += lost
    if lost:
        updated = features[through_feature.id]
        features[through_feature.id] = dataclasses.replace(
            updated, params={**updated.params, "through": False}
        )
    if is_a_cavity(through_feature):
        findings += _mouth_covered(
            "move_feature", body, placed.mesh, through_feature, source.features, travel, findings
        )
        # **Und die Nachbarwand, wie beim Kippen und beim Neuschnitt an neuer
        # Stelle** (25.09.2026): Eine Bohrung Ø 6, um 4,5 mm auf die Bohrung
        # 10 mm daneben zu versetzt, riss die Trennwand auf, und an keinem Kern
        # sagte der Schritt etwas.
        findings += _without_opened_twice(
            _neighbour_bore_findings(source, feature, cutting, ctx, moved=True), findings
        )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features=features,
            )
        ],
        findings=findings,
        solver=deepest((closed.solver, placed.solver)),
    )


def _free_feature_id(source: SceneObject, kind: str) -> FeatureId:
    """Eine Kennung, die es an diesem Körper noch nicht gibt.

    Dieselbe Form, die die Erkennung vergibt (``hole_1``, ``pin_2``), damit
    Kopie und Original im Objektbaum nebeneinander gleich aussehen.

    **Gezählt wird über die höchste vergebene Zahl, nicht in die Lücke.** Hier
    stand das Gegenteil, mit dem Argument, eine Lücke verweise auf eine Zählung,
    die niemand sieht. Gemessen am 03.09.2026 kostet das Füllen der Lücke zwei
    Dinge, und beide wiegen schwerer:

    * **Die Kennung wird recycelt.** Wer ``hole_3`` löscht und danach eine
      Bohrung verdoppelt, bekommt wieder ``hole_3`` — und jeder Prüfbefund,
      jede Passung und jeder Bericht, der auf die alte zeigte, zeigt jetzt auf
      eine andere. Eine Kennung ist das, woran Verweise hängen (§21.2); sie
      darf ihre Bedeutung nicht wechseln.
    * **Die Reihenfolge im Objektbaum kippt.** Ein neues Merkmal steht am Ende
      des Wörterbuchs, also hinter den Flächen. Mit der kleinsten freien Zahl
      stand dort „Bohrung 3" unter „Fläche 6", während 1, 2, 4 und 5 darüber
      standen — genau das Bild, das Robert am 03.09.2026 gemeldet hat. Mit der
      höchsten Zahl liest sich dieselbe Stelle als das, was sie ist: die
      jüngste.
    """
    return _free_id_among((*source.features, *source.reserved_feature_ids), kind)


def _free_id_among(taken: Iterable[str], kind: str) -> FeatureId:
    """Dieselbe Zählung über eine beliebige Menge vergebener Namen.

    Eine Kette bringt mehrere Kopien auf einmal — Bohrung und Senkung —, und die
    zweite darf die Nummer der ersten nicht noch einmal ziehen. Der Aufrufer
    führt die Menge mit und legt jede neue Kennung hinein.
    """
    highest = 0
    for name in taken:
        head, _, tail = name.rpartition("_")
        if head == kind and tail.isdigit():
            highest = max(highest, int(tail))
    return f"{kind}_{highest + 1}"


@op_params
class DuplicateFeatureParams(FeaturePlacementParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_(
            "Das erkannte Merkmal, das ein zweites Mal entsteht. Ein Klick darauf im "
            "Objektbaum oder in der Ansicht wählt es aus."
        ),
    )
    x: float = param(
        title=_("X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte der Kopie. Beim Anklicken steht hier die alte, um einen "
            "Durchmesser versetzt."
        ),
    )
    y: float = param(
        title=_("Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte der Kopie. Beim Anklicken steht hier die alte, um einen "
            "Durchmesser versetzt."
        ),
    )
    z: float = param(
        title=_("Z"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte der Kopie. Beim Anklicken steht hier die alte, um einen "
            "Durchmesser versetzt."
        ),
    )


@register_op(
    name="duplicate_feature",
    # 2: der Rückfall aus Kennzahlen schneidet ein Sackloch nicht mehr um die
    # Zugabe unter seinen Boden (23.09.2026).
    cache_version="2",
    title=_("Merkmal verdoppeln"),
    category="holes",
    params=DuplicateFeatureParams,
    reversible=True,
    consumes=1,
    produces=1,
    # **Nicht** :data:`MOVABLE_KINDS` — der Einschluss fehlt hier mit Absicht,
    # und die Begründung steht an :data:`DUPLICABLE_KINDS`.
    applies_to=list(DUPLICABLE_KINDS),
    deterministic=False,
    doc=_(
        "Legt ein erkanntes Merkmal ein zweites Mal an: Bohrung, Langloch, Zapfen, "
        "Senkung, Verjüngung, Kuppel, Pfanne, Wulst oder Kehle."
    ),
)
def duplicate_feature(ctx: OpContext) -> OpResult:
    """Ein erkanntes Merkmal ein zweites Mal — die halbe Bewegung des Versetzens.

    **Der weiteste Weg von allen war das** (gemessen 3d-druck-d4, 03.09.2026):
    Wer eine zweite Bohrung wie die erste wollte, rief *Bohrung setzen* und
    tippte Durchmesser, Tiefe, Achse und drei Koordinaten von Hand ab — obwohl
    Solidon alle vier Werte gemessen hat und im Merkmalspanel anzeigt. Vier
    abgeschriebene Zahlen sind vier Gelegenheiten für einen Tippfehler, und
    keine davon ist nötig.

    Innen ist es die zweite Hälfte von :func:`move_feature` ohne die erste: An
    der alten Stelle bleibt alles, an der neuen entsteht dasselbe Merkmal. Ein
    Hohlraum wird also geschnitten, ein Zapfen angesetzt.

    **Die Kopie bekommt eine eigene Kennung**, und das ist der Unterschied zum
    Versetzen: Dort reist die Kennung mit, weil es dasselbe Merkmal bleibt;
    hier gibt es hinterher zwei, und Passungen, die auf das Original zeigen,
    dürfen davon nichts merken.
    """
    params = cast(DuplicateFeatureParams, ctx.params)
    if np.linalg.norm((params.nx, params.ny, params.nz)) > EPS_GEOM:
        return _place_oriented_feature(ctx, duplicate=True)
    source = ctx.inputs[0]
    feature = _movable_feature(source, params.at_feature, "duplicate_feature")
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])
    target: Vec3 = (params.x, params.y, params.z)

    if all(is_close(a, b) for a, b in zip(centre, target, strict=True)):
        # Kein Fehler, sondern ein Hinweis: Die Boolesche liefe auf sich selbst
        # und ließe den Körper, wie er ist. Regel 19 — was zurücknehmbar ist,
        # bekommt keine Nachfrage, und was nichts tut, keine Ausnahme.
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="duplicate_feature.unchanged",
                    severity="info",
                    message=_(
                        "Ein zweites Merkmal an derselben Stelle ist dasselbe Merkmal — "
                        "nichts verdoppelt."
                    ),
                    feature_ids=(feature.id,),
                )
            ],
        )

    body = as_mesh_data(source.mesh)
    cavity = is_a_cavity(feature)
    from app.core.perceive.relations import cavity_chain_state_at

    state = cavity_chain_state_at(feature, source.features, body)
    chain = state.chain
    if (refused := cavity_refusal(state)) is not None:
        raise ValidationError(
            field="at_feature",
            detail=refused,
            values={"feature": feature.id},
            constraint="not_movable",
        )
    if feature.kind == "torus":
        return _duplicate_torus(ctx, source, feature, target)
    if source.kind == "brep" and chain is not None:
        return _exact_duplicate_chain(ctx, source, feature, chain, target)
    if chain is not None:
        return _duplicate_cavity_chain(ctx, source, feature, chain, target)
    if source.kind == "brep" and feature.kind in EXACT_CAVITY_KINDS:
        return _exact_duplicate_cavity(ctx, source, feature, target)
    if source.kind == "brep" and feature.kind in EXACT_FACE_KINDS:
        return _exact_duplicate_by_faces(ctx, source, feature, centre, target, cavity=cavity)
    ctx.progress(0.2, str(_("Das Merkmal wird an der neuen Stelle angelegt …")))
    change: BooleanKind = "difference" if cavity else "union"
    cutting = _placing_tool(ctx, body, source, feature, target, cavity)
    placed = boolean(
        change,
        [body, cutting],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    findings = [*placed.findings]
    # **Eine Kopie, die nichts geschnitten hat, ist die stille Variante des
    # Fehlers**, den Robert heute am Stopfen gefunden hat: Im Verlauf steht ein
    # Schritt, im Bild liegt dasselbe Teil. Wer eine Bohrung neben den Körper
    # verdoppelt, soll es lesen und nicht suchen.
    #
    # **Und diese Prüfung gehört hierher und ausdrücklich nicht zu den anderen
    # vier.** Sie vergleicht das Volumen davor und danach, und beim Verdoppeln
    # ist die Differenz genau das Merkmal. Versetzen, Drehen und Ändern führen
    # **zwei** Boolesche aus, die sich gegenseitig aufheben — ein gelungenes
    # Versetzen ändert das Volumen um nichts. Dort eingebaut würde derselbe
    # Aufruf bei **jedem** Erfolg anschlagen; gemessen am 03.09.2026 bleibt das
    # Volumen einer versetzten Bohrung auf die Stelle genau gleich.
    nothing = without_effect(source.mesh, placed.mesh, change, ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    lost = _throughness_lost(
        placed.mesh,
        feature,
        target,
        "duplicate_feature",
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        tool=cutting,
    )
    findings += lost

    copy = dataclasses.replace(
        feature,
        id=_free_feature_id(source, feature.kind),
        params={**feature.params, "centre": target},
        provenance="generated",
        face_indices=(),
        surface_patches=(),
    )
    findings += _edge_findings(body, [copy])
    kept: dict[FeatureId, Feature] = {copy.id: copy}
    if cavity:
        travel = np.asarray(target, dtype=float) - np.asarray(centre, dtype=float)
        kept, missing = _copies_found(
            "duplicate_feature", placed.mesh, kept, check_cancelled=ctx.cancelled.raise_if_cancelled
        )
        findings += missing
        findings += _mouth_covered(
            "duplicate_feature", body, placed.mesh, feature, source.features, travel, findings
        )
        findings += _without_opened_twice(
            _neighbour_bore_findings(source, feature, cutting, ctx, moved=True, copy=True),
            findings,
        )
    if lost and copy.id in kept:
        # Wie beim Versetzen: Der Satz sagt „geht nicht mehr durch", und die
        # Kopie sagt es auch — hier blieb sie ``through=True`` (RM-220).
        found = kept[copy.id]
        kept[copy.id] = dataclasses.replace(found, params={**found.params, "through": False})
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**_without_old_triangles(source.features), **kept},
                reserved_feature_ids=tuple(
                    sorted({*source.reserved_feature_ids, *source.features, copy.id})
                ),
            )
        ],
        findings=findings,
        solver=placed.solver,
    )


def _duplicate_cavity_chain(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    chain: Sequence[Feature],
    target: Vec3,
) -> OpResult:
    """Eine gesenkte Bohrung ein zweites Mal — Bohrung **und** Senkung (RM-172).

    Bis zum 15.09.2026 sagte das Verdoppeln an einem geteilten Hohlraum ab,
    und davor setzte es einen Stumpf ohne Senkung (gemessen 14.09.2026: die
    Bohrung gewählt, kopiert wurde nur der Abschnitt unter der Senkung). Der
    Hohlraum ist aber einer, und der Kunde meint ihn ganz — so, wie
    :func:`move_feature` ihn seit dem 09.09.2026 ganz versetzt.

    Das Werkzeug ist dasselbe wie beim Versetzen: der exakte Hohlraum aus den
    Flächen, an seinen Mündungen um die Zugabe aus §39 verlängert
    (:func:`_past_the_mouths`) — bündig ließ er eine Haut von 5 µm stehen, das
    Werkzeug aus Kennzahlen (:func:`_chain_tool`) nahm mit dem Umkreis seines
    Vielecks bis zu 0,9 mm³ zu viel (gemessen 15.09.2026, siehe
    :func:`move_feature`). Die Kennzahlen bleiben der Rückfall, wo die Flächen
    keinen Körper hergeben, und :func:`_cavity_tool` der letzte. Verschoben um denselben Weg wie die
    gewählte Mitte, und jede Kopie bekommt ihre eigene Kennung; das Original
    behält seine.
    """
    body = as_mesh_data(source.mesh)
    measured = np.asarray(feature.params["centre"], dtype=float)
    travel = np.asarray(target, dtype=float) - measured
    tool = _chain_copy_tool(ctx, body, feature, chain)
    shifted = tool.raw.copy()
    shifted.apply_translation(travel)
    cutting = MeshData.of(shifted)
    ctx.progress(0.2, str(_("Der ganze Hohlraum wird an der neuen Stelle angelegt …")))
    placed = boolean(
        "difference",
        [body, cutting],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    findings = [*placed.findings]
    nothing = without_effect(source.mesh, placed.mesh, "difference", ctx.profile)
    if nothing is not None:
        findings.append(nothing)

    taken: set[str] = {*source.reserved_feature_ids, *source.features}
    copies: dict[FeatureId, Feature] = {}
    for member in chain:
        moved = np.asarray(member.params["centre"], dtype=float) + travel
        name = _free_id_among(taken, member.kind)
        taken.add(name)
        copies[name] = dataclasses.replace(
            member,
            id=name,
            params={**member.params, "centre": tuple(float(value) for value in moved)},
            provenance="generated",
            face_indices=(),
            surface_patches=(),
        )
    findings += _edge_findings(body, list(copies.values()))
    bore = next(iter(copies.values()))
    bore_centre = cast(Vec3, tuple(float(value) for value in bore.params["centre"]))
    lost = _throughness_lost(
        placed.mesh,
        bore,
        bore_centre,
        "duplicate_feature",
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        tool=cutting,
    )
    findings += lost
    copies, missing = _copies_found(
        "duplicate_feature", placed.mesh, copies, check_cancelled=ctx.cancelled.raise_if_cancelled
    )
    findings += missing
    if lost and bore.id in copies:
        measured_bore = copies[bore.id]
        copies[bore.id] = dataclasses.replace(
            measured_bore, params={**measured_bore.params, "through": False}
        )
    findings += _mouth_covered(
        "duplicate_feature", body, placed.mesh, chain[0], source.features, travel, findings
    )
    findings += _without_opened_twice(
        _neighbour_bore_findings(source, feature, cutting, ctx, moved=True, copy=True), findings
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**_without_old_triangles(source.features), **copies},
                reserved_feature_ids=tuple(sorted(taken)),
            )
        ],
        findings=findings,
        solver=placed.solver,
    )


# --- Merkmalsmuster (P6.7) --------------------------------------------------------

#: Wie viele Plätze ein Merkmalsmuster höchstens hat, die Quelle mitgezählt.
#: Dieselbe Grenze und derselbe Grund wie bei den Körperkopien
#: (``scene.ops.MAX_PATTERN``): darüber ist es ein Tippfehler.
MOST_FEATURE_PLACES: Final = 100

#: Die drei Arten eines Merkmalsmusters — eine Operation, drei Arten.
FEATURE_PATTERN_KINDS: Final = ("linear", "circular", "mirror")


@op_params
class PatternFeatureParams(BaseParams):
    at_features: tuple[str, ...] = param(
        title=_("Merkmale"),
        default=(),
        kind="features",
        required=True,
        feature_kinds=DUPLICABLE_KINDS,
        placement="front",
        doc=_(
            "Die Merkmale, die sich wiederholen — ein Klick trägt eines ein. Sie bleiben "
            "die Quelle: Ändert sich ihr Maß im Verlauf, folgen alle Kopien."
        ),
    )
    kind: str = param(
        title=_("Art"),
        default="linear",
        choices=FEATURE_PATTERN_KINDS,
        doc=_(
            "Linear reiht die Kopien in eine Richtung, kreisförmig legt sie um eine "
            "Achse, gespiegelt setzt eine Kopie jenseits einer Ebene."
        ),
    )
    count: int = param(
        title=_("Anzahl"),
        default=3,
        minimum=2,
        maximum=MOST_FEATURE_PLACES,
        depends_on=("kind", ("linear", "circular")),
        doc=_("Wie viele Plätze das Muster hat, die Quelle mitgezählt."),
    )
    spacing: float = param(
        title=_("Abstand"),
        default=10.0,
        unit="mm",
        minimum=0.1,
        maximum=1000.0,
        depends_on=("kind", ("linear",)),
        doc=_("Von Mitte zu Mitte zweier benachbarter Plätze."),
    )
    angle: float = param(
        title=_("Winkel"),
        default=360.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        depends_on=("kind", ("circular",)),
        doc=_(
            "Über welchen Bogen die Plätze verteilt werden. Volle 360 Grad "
            "schließen den Kranz, ohne dass zwei Plätze aufeinanderfallen."
        ),
    )
    skip: str = param(
        title=_("Auslassen"),
        default="",
        depends_on=("kind", ("linear", "circular")),
        doc=_(
            "Plätze, die frei bleiben, als Nummern mit Komma. Die Quelle ist Platz 1 "
            "und bleibt immer."
        ),
    )
    dx: float = param(
        title=_("Richtung X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Bei einer Reihe ihre Richtung, beim Kreis seine Achse, beim Spiegeln die "
            "Senkrechte der Ebene. Null in allen drei Feldern heißt: Reihe längs X, "
            "Kreis um Z, gespiegelt an der YZ-Ebene."
        ),
    )
    dy: float = param(
        title=_("Richtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Zweite Achse der Richtung — siehe Richtung X."),
    )
    dz: float = param(
        title=_("Richtung Z"),
        default=0.0,
        placement="advanced",
        doc=_("Dritte Achse der Richtung — siehe Richtung X."),
    )
    cx: float = param(
        title=_("Punkt X"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        depends_on=("kind", ("circular", "mirror")),
        doc=_("Ein Punkt auf der Achse des Kreises oder in der Spiegelebene."),
    )
    cy: float = param(
        title=_("Punkt Y"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        depends_on=("kind", ("circular", "mirror")),
        doc=_("Zweite Koordinate des Punkts — siehe Punkt X."),
    )
    cz: float = param(
        title=_("Punkt Z"),
        default=0.0,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="advanced",
        depends_on=("kind", ("circular", "mirror")),
        doc=_("Dritte Koordinate des Punkts — siehe Punkt X."),
    )


@dataclasses.dataclass(frozen=True, slots=True)
class _PatternUnit:
    """Eine Quelle des Musters: das gewählte Merkmal und alles, was mit ihm geht.

    Eine Bohrung mit Senkung ist **ein** Hohlraum (RM-172) und wiederholt sich
    als Ganzes — ``members`` ist dann die Kette, sonst das Merkmal allein.
    """

    feature: Feature
    members: tuple[Feature, ...]
    chain: tuple[Feature, ...] | None


@dataclasses.dataclass(slots=True)
class _PatternPlace:
    """Ein Platz des Musters: welche Quelle, welche Nummer, welche Bewegung."""

    unit: _PatternUnit
    number: int
    matrix: NDArray[np.float64]
    probe: MeshData
    copies: list[Feature] = dataclasses.field(default_factory=list)


@register_op(
    name="pattern_feature",
    title=_("Merkmal vervielfachen"),
    category="holes",
    params=PatternFeatureParams,
    consumes=1,
    produces=1,
    applies_to=list(DUPLICABLE_KINDS),
    deterministic=False,
    doc=_(
        "Wiederholt erkannte Merkmale in einer Reihe, auf einem Kreis oder gespiegelt: "
        "Bohrung, Senkung, Langloch, Zapfen, Verjüngung, Kuppel, Wulst oder Kehle. Die "
        "Quelle bleibt maßgebend — ändert sich ihr Maß im Verlauf, folgen die Kopien."
    ),
)
def pattern_feature(ctx: OpContext) -> OpResult:
    """Merkmale linear, kreisförmig oder gespiegelt wiederholen — ein Schritt (P6.7).

    **Nicht** :func:`app.core.scene.ops.pattern`: Das kopiert ganze Körper.
    Hier bleibt es ein Körper, und nur das Merkmal wiederholt sich — der
    Kundenweg aus Konzept §13.9 verlangt ausdrücklich „keine versehentliche
    Kopie des gesamten Körpers".

    **Die Quelle bleibt maßgebend**, und zwar durch die Bauart: Der Schritt
    nennt die Quelle beim Namen und liest sie bei jeder Auswertung neu. Ändert
    jemand ihr Maß in dem Schritt, der sie gesetzt hat, rechnet das Muster mit
    dem neuen Maß; ein Undo nimmt das ganze Muster, denn es ist ein Schritt.

    **Jede Instanz ist die Quelle, bewegt.** Das Werkzeug entsteht einmal an
    der Stelle der Quelle — derselbe Körper wie beim Verdoppeln — und wird je
    Platz mit der Bewegung des Musters versetzt, gedreht oder gespiegelt; so
    drehen auch Achsen radialer Bohrungen und Richtungen von Langlöchern mit.
    Vor dem Schneiden wird jeder Platz geprüft: Überschneidet er die Quelle
    oder einen schon gesetzten Platz, oder trifft er kein Material, entsteht
    er nicht, und ein Befund nennt ihn beim Platz (Regel 17).
    """
    params = cast(PatternFeatureParams, ctx.params)
    source = ctx.inputs[0]
    body = as_mesh_data(source.mesh)
    units = _pattern_units(source, params.at_features, body)
    places, left_out = _pattern_places(params, _pattern_default_axis(params))
    ctx.progress(0.1, str(_("Die Plätze des Musters werden geprüft …")))
    probes = {unit.feature.id: _pattern_probe(ctx, body, source, unit) for unit in units}
    candidates: list[_PatternPlace] = []
    for unit in units:
        for number, matrix in places:
            ctx.cancelled.raise_if_cancelled()
            moved = probes[unit.feature.id].raw.copy()
            transform.moved(moved, matrix)
            candidates.append(_PatternPlace(unit, number, matrix, MeshData.of(moved)))
    kept, overlapping, missing = _checked_places(ctx, body, candidates, list(probes.values()))
    _name_copies(source, kept)
    findings: list[Finding] = []
    if overlapping:
        findings.append(_places_overlap(overlapping, len(units)))
    if missing:
        findings.append(_places_miss(missing, len(units)))
    findings.append(
        Finding(
            code="pattern_feature.done",
            severity="info",
            message=_("Das Muster steht."),
            values={
                "placed": len(kept),
                "skipped": left_out * len(units),
                "sources": len(units),
            },
        )
    )
    if not kept:
        return OpResult(
            outputs=[source],
            findings=[dataclasses.replace(entry, object_id=source.id) for entry in findings],
        )
    ctx.progress(0.4, str(_("Die Merkmale werden an ihren Plätzen angelegt …")))
    if source.kind == "brep":
        return _exact_pattern_result(ctx, source, kept, findings)
    return _mesh_pattern_result(ctx, source, body, kept, findings, seed=ctx.seed)


def _pattern_units(source: SceneObject, names: Sequence[str], body: MeshData) -> list[_PatternUnit]:
    """Die Quellen des Musters, jede mit ihrer Kette — oder ein Satz, warum nicht.

    Dieselben Fragen wie beim Verdoppeln (``_movable_feature``, die Kette aus
    ``cavity_chain_state_at``), dazu eine, die ein Muster schärfer stellt:
    **Ein erkanntes Merkmal braucht belegte Flächen.** Das Werkzeug jeder
    Instanz entsteht aus ihnen; ein Merkmal ohne Flächen, das nicht ein
    Baustein mit seinen Kennzahlen gesetzt hat, wäre an jedem Platz eine
    Vermutung (Konzept §13.2, „Importmerkmale brauchen belegte Träger").
    Zwei gewählte Abschnitte derselben Kette sind eine Quelle, nicht zwei.
    """
    from app.core.perceive.actions import cone_piece_blocked, reason_against
    from app.core.perceive.relations import cavity_chain_state_at

    chosen = tuple(dict.fromkeys(names))
    if not chosen:
        raise ValidationError(
            field="at_features",
            detail=_("Wählen Sie mindestens ein Merkmal, das sich wiederholen soll."),
            constraint="required",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    units: list[_PatternUnit] = []
    covered: set[str] = set()
    for name in chosen:
        feature = source.features.get(name)
        if feature is None:
            raise ValidationError(
                field="at_features",
                detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
                values={"feature": name, "object": source.id},
                constraint="unknown_feature",
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        against = cone_piece_blocked(feature) or reason_against("pattern_feature", feature.kind)
        if against is not None:
            raise ValidationError(
                field="at_features",
                detail=against,
                values={"feature": name, "kind": feature.kind},
                constraint="not_movable",
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        if feature.id in covered:
            continue
        if feature.provenance != "generated" and not feature.face_indices:
            raise ValidationError(
                field="at_features",
                detail=_(
                    "Dieses Merkmal ist an keinen Flächen des Körpers belegt, und ohne sie "
                    "entsteht kein Werkzeug für seine Kopien. Erkennen Sie die Merkmale neu "
                    "oder wählen Sie ein anderes."
                ),
                values={"feature": name},
                constraint="not_evidenced",
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        state = cavity_chain_state_at(feature, source.features, body)
        if (refused := cavity_refusal(state)) is not None:
            raise ValidationError(
                field="at_features",
                detail=refused,
                values={"feature": name},
                constraint="not_movable",
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        chain = tuple(state.chain) if state.chain is not None else None
        members = chain if chain is not None else (feature,)
        covered.update(member.id for member in members)
        units.append(_PatternUnit(feature, members, chain))
    return units


def _pattern_default_axis(params: PatternFeatureParams) -> NDArray[np.float64]:
    """Die Richtung des Musters als Einheitsvektor — ohne Angabe die dokumentierte.

    Null in allen drei Feldern ist keine Richtung, und geraten wird sie nicht:
    Das Schema nennt, was dann gilt (Reihe längs X, Kreis um Z, Spiegeln an
    der YZ-Ebene) — dieselbe Vorgabe wie bei *Kopien in Reihe oder Kreis*.
    """
    direction = np.asarray((params.dx, params.dy, params.dz), dtype=np.float64)
    length = math.sqrt(math.fsum(float(value) * float(value) for value in direction))
    if length <= EPS_GEOM:
        return np.asarray(
            (0.0, 0.0, 1.0) if params.kind == "circular" else (1.0, 0.0, 0.0), dtype=np.float64
        )
    return direction / length


def _pattern_places(
    params: PatternFeatureParams, direction: NDArray[np.float64]
) -> tuple[list[tuple[int, NDArray[np.float64]]], int]:
    """Die Plätze außer der Quelle, je mit Nummer und Bewegung — und wie viele ausgelassen.

    Linear: Platz *k* liegt um k - 1 Abstände in der Richtung. Kreisförmig:
    Ein voller Kranz teilt durch die Anzahl, ein Teilbogen durch die
    Zwischenräume — sonst fielen bei 360 Grad der erste und der letzte Platz
    aufeinander (dieselbe Regel wie beim Körpermuster). Gespiegelt: ein Platz,
    die Spiegelung an der Ebene durch den Punkt mit der Richtung als
    Senkrechte; eine Spiegelung ist eine Bewegung mit Determinante -1, und
    Werkzeug wie Merkmal drehen dabei ihren Umlaufsinn mit.
    """
    point = np.asarray((params.cx, params.cy, params.cz), dtype=np.float64)
    if params.kind == "mirror":
        # Elementweise, nicht über BLAS (RM-187): An einer Achsnormalen stehen
        # dann exakt null und eins in der Matrix, und die Kopie liegt auf jeder
        # Maschine auf denselben Bits.
        reflection = np.eye(4)
        reflection[:3, :3] -= 2.0 * np.outer(direction, direction)
        distance = math.fsum(float(a) * float(b) for a, b in zip(point, direction, strict=True))
        reflection[:3, 3] = 2.0 * distance * direction
        return [(2, reflection)], 0
    if params.count < 2:
        raise ValidationError(
            "count",
            _("Ein Muster braucht mindestens zwei Plätze."),
            value=params.count,
            constraint="pattern_count",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    left_out = _left_out_places(params.skip, params.count)
    places: list[tuple[int, NDArray[np.float64]]] = []
    if params.kind == "linear":
        for number in range(2, params.count + 1):
            if number in left_out:
                continue
            travel = direction * params.spacing * (number - 1)
            places.append((number, np.asarray(translation(cast(Vec3, tuple(travel))))))
        return places, len(left_out)
    full = is_close(abs(params.angle), 360.0)
    divisor = params.count if full else params.count - 1
    axis = cast(Vec3, tuple(float(value) for value in direction))
    about = cast(Vec3, tuple(float(value) for value in point))
    for number in range(2, params.count + 1):
        if number in left_out:
            continue
        degrees = params.angle * (number - 1) / divisor
        places.append((number, np.asarray(transform.rotation_about(axis, about, degrees))))
    return places, len(left_out)


def _left_out_places(text: str, count: int) -> set[int]:
    """Die ausgelassenen Plätze aus „3, 5" — oder ein Satz, warum das keine sind."""
    numbers: set[int] = set()
    for word in text.replace(";", ",").replace(" ", ",").split(","):
        word = word.strip()
        if not word:
            continue
        if not word.isdigit() or not 2 <= int(word) <= count:
            raise ValidationError(
                "skip",
                _(
                    "Ausgelassen werden Plätze des Musters, als Nummern mit Komma von 2 bis "
                    "zur Anzahl. Die Quelle ist Platz 1 und bleibt."
                ),
                value=text,
                constraint="pattern_skip",
                values={"count": count},
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        numbers.add(int(word))
    return numbers


def _pattern_probe(
    ctx: OpContext, body: MeshData, source: SceneObject, unit: _PatternUnit
) -> MeshData:
    """Das Werkzeug einer Instanz an der Stelle der Quelle, als Netz.

    Derselbe Körper, den *Merkmal verdoppeln* setzt: die Kette aus
    :func:`_chain_copy_tool`, ein einzelnes Merkmal aus :func:`_placing_tool`
    (ein Zapfen mit Sockel in der Grundfläche), der Ring aus seinen Kennzahlen.
    Am Netz ist es das Werkzeug selbst, am exakten Körper die Probe, an der
    Überschneidung und Ziel geprüft werden, bevor exakt geschnitten wird.
    """
    feature = unit.feature
    centre = cast(Vec3, tuple(float(value) for value in feature.params["centre"]))
    if unit.chain is not None:
        return _chain_copy_tool(ctx, body, feature, unit.chain)
    if feature.kind == "torus":
        ring, tube = _torus_measures(feature, None, None)
        axis = _torus_axis(feature)
        return _torus_ring_mesh(centre, cast(Vec3, tuple(float(v) for v in axis)), ring, tube)
    return _placing_tool(ctx, body, source, feature, centre, is_a_cavity(feature))


def _checked_places(
    ctx: OpContext,
    body: MeshData,
    candidates: Sequence[_PatternPlace],
    sources: Sequence[MeshData],
) -> tuple[list[_PatternPlace], list[_PatternPlace], list[_PatternPlace]]:
    """Welche Plätze entstehen — und welche nicht, weil sie überschneiden oder nichts treffen.

    **Überschneidung:** Das Werkzeug des Platzes teilt Volumen mit einer Quelle
    oder einem schon angenommenen Platz. Zwei Bohrungen, die ineinander
    laufen, sind keine zwei Bohrungen mehr, und ein Muster, das sie trotzdem
    schneidet, hinterließe ein Langloch, das niemand bestellt hat.

    **Kein Ziel:** Das Werkzeug teilt kein Volumen mit dem Körper — eine
    Bohrung neben dem Teil schnitte nichts, ein Zapfen stünde in der Luft.
    Der Zapfen trägt seinen Sockel (:func:`_rooted`) und berührt eine Fläche,
    auf der er sitzt, also mit Volumen.

    Kontakt zählt nicht, gemessen an der Druckgrenze wie bei
    :func:`without_effect`. Die Hüllquader sortieren vor.
    """
    least = ctx.profile.smallest_printable_volume if ctx.profile is not None else EPS_GEOM
    occupied = [entry.raw for entry in sources]
    kept: list[_PatternPlace] = []
    overlapping: list[_PatternPlace] = []
    missing: list[_PatternPlace] = []
    for place in candidates:
        ctx.cancelled.raise_if_cancelled()
        tool = place.probe.raw
        if any(
            _boxes_meet(tool, other) and shared_volume(tool, other) > least for other in occupied
        ):
            overlapping.append(place)
            continue
        if not _boxes_meet(tool, body.raw) or shared_volume(tool, body.raw) <= least:
            missing.append(place)
            continue
        occupied.append(tool)
        kept.append(place)
    return kept, overlapping, missing


def _boxes_meet(first: Any, second: Any) -> bool:
    """Überlappen die Hüllquader zweier Netze — die billige Vorfrage."""
    low = np.maximum(first.bounds[0], second.bounds[0])
    high = np.minimum(first.bounds[1], second.bounds[1])
    return bool(np.all(low < high))


def _name_copies(source: SceneObject, kept: Sequence[_PatternPlace]) -> None:
    """Jede Kopie bekommt ihre Lage aus der Bewegung und einen eigenen Namen.

    Die Lage führt :func:`~app.core.perceive.matching.transformed_features`
    nach — derselbe Weg, auf dem eine Spiegelung oder Drehung des ganzen
    Körpers seine Merkmale mitnimmt (P0.0): Mitte, Achse, Richtung und
    Öffnung drehen und spiegeln mit. Die Namen zählt dieselbe Regel wie beim
    Verdoppeln weiter (:func:`_free_id_among`), über die höchste vergebene
    Zahl und an den reservierten vorbei.
    """
    from app.core.perceive.matching import transformed_features

    taken: set[str] = {*source.reserved_feature_ids, *source.features}
    for place in kept:
        moved = transformed_features(
            {member.id: member for member in place.unit.members}, as_transform(place.matrix)
        ).candidates
        for member in place.unit.members:
            name = _free_id_among(taken, member.kind)
            taken.add(name)
            place.copies.append(
                dataclasses.replace(
                    moved[member.id],
                    id=name,
                    provenance="generated",
                    face_indices=(),
                    surface_patches=(),
                    created_by=None,
                )
            )


def _place_list(places: Sequence[_PatternPlace], sources: int) -> str:
    """„2, 3" — oder bei mehreren Quellen „hole_1: 2, 3; pin_2: 4"."""
    if sources <= 1:
        return ", ".join(str(place.number) for place in places)
    grouped: dict[str, list[int]] = {}
    for place in places:
        grouped.setdefault(place.unit.feature.id, []).append(place.number)
    return "; ".join(
        f"{name}: {', '.join(str(number) for number in numbers)}"
        for name, numbers in grouped.items()
    )


def _places_overlap(places: Sequence[_PatternPlace], sources: int) -> Finding:
    """Plätze, die in die Quelle oder einen anderen Platz schneiden würden — sie fehlen."""
    return Finding(
        code="pattern_feature.overlap",
        severity="warning",
        message=_(
            "Einige Plätze des Musters überschneiden die Quelle oder einen anderen Platz "
            "und sind ausgelassen. Welche, steht in „instances“."
        ),
        feature_ids=tuple(dict.fromkeys(place.unit.feature.id for place in places)),
        values={"instances": _place_list(places, sources)},
        suggestions=(
            dataclasses.replace(CORRECT_INPUT, label=_("Abstand vergrößern oder Platz auslassen")),
            CANCEL,
        ),
    )


def _places_miss(places: Sequence[_PatternPlace], sources: int) -> Finding:
    """Plätze ohne Material: neben dem Teil, oder ein Zapfen in der Luft — sie fehlen."""
    return Finding(
        code="pattern_feature.no_target",
        severity="warning",
        message=_(
            "Einige Plätze des Musters treffen kein Material — sie lägen neben dem Teil "
            "oder in der Luft und sind ausgelassen. Welche, steht in „instances“."
        ),
        feature_ids=tuple(dict.fromkeys(place.unit.feature.id for place in places)),
        values={"instances": _place_list(places, sources)},
        suggestions=(
            dataclasses.replace(CORRECT_INPUT, label=_("Anzahl, Abstand oder Richtung ändern")),
            CANCEL,
        ),
    )


def _mesh_pattern_result(
    ctx: OpContext,
    source: SceneObject,
    body: MeshData,
    kept: Sequence[_PatternPlace],
    findings: list[Finding],
    *,
    seed: int | None,
) -> OpResult:
    """Das Muster am Netz: alle Werkzeuge in einer Booleschen je Richtung.

    Materie zuerst, dann die Hohlräume — dieselbe Reihenfolge, in der eine
    Bohrung durch einen neuen Zapfen hindurch ihren Weg behält. Die Plätze
    überschneiden einander nicht (:func:`_checked_places`), also ist eine
    Boolesche mit allen Werkzeugen dasselbe wie eine je Platz.
    """
    material = [place.probe for place in kept if not is_a_cavity(place.unit.feature)]
    hollow_tools = [place.probe for place in kept if is_a_cavity(place.unit.feature)]
    stages: list[SolverInfo | None] = []
    placed = body
    for change, tools in (("union", material), ("difference", hollow_tools)):
        if not tools:
            continue
        outcome = boolean(
            cast(BooleanKind, change),
            [placed, *tools],
            quality=ctx.quality,
            seed=seed,
            cancelled=ctx.cancelled,
        )
        placed = outcome.mesh
        findings.extend(outcome.findings)
        stages.append(outcome.solver)
    copies: dict[FeatureId, Feature] = {}
    for place in kept:
        ctx.cancelled.raise_if_cancelled()
        findings.extend(_edge_findings(body, place.copies))
        for copy in place.copies:
            if copy.params.get("through"):
                lost = _throughness_lost(
                    placed,
                    copy,
                    cast(Vec3, tuple(float(value) for value in copy.params["centre"])),
                    "pattern_feature",
                    quality=ctx.quality,
                    seed=seed,
                    cancelled=ctx.cancelled,
                )
                findings.extend(lost)
                if lost:
                    copy = dataclasses.replace(copy, params={**copy.params, "through": False})
            copies[copy.id] = copy
    copies, missing = _copies_found(
        "pattern_feature", placed, copies, check_cancelled=ctx.cancelled.raise_if_cancelled
    )
    findings.extend(missing)
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed,
                features={**_without_old_triangles(source.features), **copies},
                reserved_feature_ids=tuple(
                    sorted({*source.reserved_feature_ids, *source.features, *copies})
                ),
            )
        ],
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in findings],
        solver=deepest(stages),
    )


def _exact_pattern_result(
    ctx: OpContext,
    source: SceneObject,
    kept: Sequence[_PatternPlace],
    findings: list[Finding],
) -> OpResult:
    """Das Muster am exakten Körper: exakte Werkzeuge, dieselben Plätze.

    Je Art das Werkzeug, das die exakte Verdoppelung benutzt, an den Platz
    gebracht: Bohrung und Langloch aus ihren Maßen an der bewegten Mitte und
    Achse (:func:`_exact_cavity_tool`), die Kette als Drehkörper ihrer Profile
    an den bewegten Randebenen, Zapfen, Kuppel und Kegel aus ihren nativen
    Flächen bewegt (``edit.transformed``), der Ring aus seinen Kennzahlen.
    Das Ende ist das der Verdoppelung (:func:`_exact_copy_result`): erkennen,
    benennen, Durchgang und verlorene Merkmale melden.
    """
    from app.core.brep import edit

    solid = _exact_body(source)
    faces_bodies: dict[str, Any] = {}
    material: list[Any] = []
    for place in kept:
        ctx.cancelled.raise_if_cancelled()
        if not is_a_cavity(place.unit.feature):
            material.append(_exact_place_tool(source, solid, place, faces_bodies))
    placed = solid
    if material:
        placed = edit.unified(edit.boolean("union", [placed, *material]))
    hollow = [place for place in kept if is_a_cavity(place.unit.feature)]
    if hollow:
        # Alle Hohlräume in einer Differenz, wie bisher — und wie beim
        # Verdoppeln wiederholt, wenn sie still scheitert
        # (:func:`_exact_chain_cut_holding`).
        base = placed
        placed, _tools = _exact_chain_cut_holding(
            base,
            lambda overlap: _pattern_hollow_tool(
                source, solid, hollow, faces_bodies, overlap=overlap
            ),
        )
    copies = [copy for place in kept for copy in place.copies]
    findings.extend(_edge_findings(as_mesh_data(solid), copies))
    # Die Kopien stehen in der Reihenfolge der Glieder (:func:`_name_copies`);
    # die äußeren Zylinder einer Kette sind entlang der Achse frei.
    mouths = frozenset(
        copy.id
        for place in kept
        if place.unit.chain is not None
        for member, copy in zip(place.unit.members, place.copies, strict=True)
        if member.id in _chain_mouths(place.unit.chain)
    )
    result = _exact_copy_result(
        ctx, source, placed, copies, findings, op="pattern_feature", mouths=mouths
    )
    result.findings = [dataclasses.replace(entry, object_id=source.id) for entry in result.findings]
    return result


def _pattern_hollow_tool(
    source: SceneObject,
    solid: Any,
    places: Sequence[_PatternPlace],
    faces_bodies: dict[str, Any],
    *,
    overlap: float,
) -> Any:
    """Die Werkzeuge aller Hohlraumplätze eines Musters als ein Körper."""
    from app.core.brep import edit

    tools = [
        _exact_place_tool(source, solid, place, faces_bodies, overlap=overlap) for place in places
    ]
    return edit.boolean("union", tools) if len(tools) > 1 else tools[0]


def _exact_place_tool(
    source: SceneObject,
    solid: Any,
    place: _PatternPlace,
    faces_bodies: dict[str, Any],
    *,
    overlap: float = FEATURE_OVERLAP,
) -> Any:
    """Das exakte Werkzeug eines Platzes — je Art dasselbe wie bei der Verdoppelung."""
    from app.core.brep import edit

    feature = place.unit.feature
    if place.unit.chain is not None:
        entrance = _exact_chain_entrance(source, place.unit.chain)
        return _exact_chain_tool_placed(solid, entrance, place.matrix, overlap=overlap)
    copy = place.copies[0]
    centre = cast(Vec3, tuple(float(value) for value in copy.params["centre"]))
    if feature.kind == "torus":
        axis = cast(Vec3, tuple(float(value) for value in copy.params["axis"]))
        return _exact_torus_tool(feature, centre, axis)
    if feature.kind in EXACT_CAVITY_KINDS:
        axis = cast(Vec3, tuple(float(value) for value in copy.params["axis"]))
        return _exact_cavity_tool(solid, copy, centre, axis)
    if feature.id not in faces_bodies:
        faces_bodies[feature.id] = _exact_body_from_faces(source, feature)
    return edit.transformed(faces_bodies[feature.id], as_transform(place.matrix))


def _chain_copy_tool(
    ctx: OpContext, body: MeshData, feature: Feature, chain: Sequence[Feature]
) -> MeshData:
    """Das Werkzeug einer Kopie der ganzen Kette, an der Stelle der Quelle.

    Der exakte Hohlraum aus den Flächen, an den Mündungen um die Zugabe aus
    §39 verlängert (:func:`_past_the_mouths`); wo die Flächen keinen Körper
    hergeben, die Kennzahlen (:func:`_chain_tool`) und zuletzt
    :func:`_cavity_tool`. Eine Stelle für *Merkmal verdoppeln* und das
    Merkmalsmuster: Beide bewegen dasselbe Werkzeug nur verschieden.
    """
    measured = np.asarray(feature.params["centre"], dtype=float)
    exact = _paired_cavity_body(body, *chain)
    tool = (
        _past_the_mouths(body, exact)
        if exact is not None
        else _chain_tool(body, chain, pivot=measured, tilt=0.0)
        or _cavity_tool(
            body, chain, chain, quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled
        )
    )
    if tool is None:
        raise ValidationError(
            field="at_feature",
            detail=NO_OWN_BODY,
            values={"feature": feature.id, "bore": chain[0].id, "widening": chain[-1].id},
            constraint="not_movable",
        )
    return tool


def _cavity_chain_of(
    mesh: MeshData, feature: Feature, features: Mapping[str, Feature]
) -> tuple[Feature, ...] | None:
    """Die übrigen Abschnitte desselben Hohlraums — oder ``None``, wenn er allein steht.

    Dieselbe Kette, aus der :func:`move_feature` seinen gemeinsamen Körper
    baut und der Objektbaum seine Schachtelung nimmt. Eine Kette von einem
    Glied ist keine: Es gibt dann nichts mitzunehmen und nichts zu fragen.
    """
    from app.core.perceive.relations import cavity_chain_at

    chain = cavity_chain_at(feature, features, mesh)
    return chain if chain is not None and len(chain) > 1 else None


#: Die zwei Antworten auf die Frage nach den übrigen Abschnitten.
#:
#: Sie stehen als Registerwerte fest, damit die Antwort in den Schritt
#: geschrieben werden kann (``OpResult.answered``) und die nächste Auswertung
#: nicht erneut fragt — derselbe Weg, den ``load`` mit der Einheit geht.
SECTIONS_TOGETHER: Final = "chain"
SECTIONS_ALONE: Final = "single"


def _asked_about_sections(ctx: OpContext, chain: Sequence[Feature]) -> str:
    """Fragen, ob die übrigen Abschnitte mitgehen (Regel 21).

    **Eine Mehrdeutigkeit und keine Bestätigung.** Regel 19 verbietet die
    Rückfrage vor einer rücknehmbaren Handlung; hier gibt es aber zwei
    sinnvolle Ergebnisse, und keines davon ist das offensichtliche: Wer eine
    Bohrung mit Senkung löscht, meint meistens beides — und manchmal will er
    die Senkung behalten und nur die Bohrung schließen (Robert, 09.09.2026:
    „bei der Bohrung auch eine Frage, ob man die Senkung mit löschen will,
    wäre sinnvoll").

    Gefragt wird **nur**, wenn es etwas zu fragen gibt: Steht das Merkmal
    allein, kommt diese Funktion nicht vor.
    """
    question = str(
        _(
            "Dieses Merkmal ist ein Abschnitt eines größeren Hohlraums — einer Bohrung "
            "mit ihrer Senkung etwa. Sollen alle {count} Abschnitte zusammen entfernt "
            "werden?"
        )
    ).format(count=len(chain))
    choices = [str(_("Den ganzen Hohlraum entfernen")), str(_("Nur das gewählte Merkmal"))]
    answer = ctx.ask(question, choices)
    if answer not in choices:
        raise InternalError(detail="the cavity section question returned an unknown choice")
    return SECTIONS_TOGETHER if answer == choices[0] else SECTIONS_ALONE


@op_params
class RemoveFeatureParams(BaseParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_("Das erkannte Merkmal, das entfernt wird."),
    )
    sections: str = param(
        title=_("Zusammenhängende Abschnitte"),
        default="ask",
        choices=("ask", "chain", "single"),
        placement="advanced",
        doc=_(
            "Was mit den übrigen Abschnitten eines Hohlraums geschieht — einer Senkung "
            "über der gewählten Bohrung etwa. „Nachfragen“ entscheidet der Nutzer, "
            "sobald der Fall auftritt."
        ),
    )


@register_op(
    name="remove_feature",
    # 5: eine schräge Bohrung schließt an ihren Randebenen (22.09.2026).
    # 6: ein geschlossener Hohlraum hinterlässt keine Narben (23.09.2026).
    # 7: ein Musterstopfen um einen Zylinder füllt auch Taschen mit
    # parallelen Wänden bis zum Boden (``patterns.plug_for``, 23.09.2026).
    # 8: derselbe Stopfen wird an den Facettengrenzen konform geteilt und
    # endet an den Stirnflächen des Stifts (23.09.2026).
    cache_version="8",
    title=_("Merkmal entfernen"),
    category="holes",
    params=RemoveFeatureParams,
    consumes=1,
    produces=1,
    applies_to=[*MOVABLE_KINDS, "fillet", "thread", "pattern"],
    touches_features=True,
    deterministic=False,
    doc=_(
        "Entfernt ein erkanntes Merkmal: Bohrung, Langloch, Zapfen, Senkung, "
        "Verjüngung, Kuppel, Pfanne, Wulst, Kehle, Gewinde, Rundung oder Muster — und "
        "füllt einen Lufteinschluss mit Material."
    ),
)
def remove_feature(ctx: OpContext) -> OpResult:
    """Ein erkanntes Merkmal wegnehmen — die halbe Bewegung des Versetzens.

    „Ich will die auch löschen können, also jede Operation" (Robert,
    03.09.2026). Für ein erkanntes Merkmal ist das derselbe Motor wie
    :func:`move_feature`, nur mit einem Gang: An der alten Stelle steht das
    Gegenteil dessen, was das Merkmal ist, und danach nichts mehr. Eine
    Bohrung wird gefüllt, ein Zapfen abgetragen.

    **Die Kennung geht mit und bleibt nicht als Verweis stehen.** Ein Merkmal,
    das im Objekt weiterlebt, obwohl seine Geometrie fort ist, ist genau der
    Zustand, den ``fit.missing_feature`` später als Verletzung meldet — und
    dann sucht der Kunde an einem Teil, das in Ordnung ist. Ein Befund sagt es
    stattdessen sofort.
    """
    params = cast(RemoveFeatureParams, ctx.params)
    source = ctx.inputs[0]
    if _is_a_fillet(source, params.at_feature):
        return _drop_the_fillet(ctx, source, params.at_feature)
    feature = _movable_feature(source, params.at_feature, "remove_feature")
    if feature.kind == "pattern":
        # Vor der Hohlraumkette: Ein Muster hat keine, und seine Mitte liegt
        # auf der Trägerebene, nicht in einem Hohlraum.
        return _remove_pattern(ctx, source, feature)
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])

    body = as_mesh_data(source.mesh)
    cavity = is_a_cavity(feature)
    chain = _cavity_chain_of(body, feature, source.features)
    if feature.kind == "torus":
        return _remove_torus(ctx, source, feature)
    if feature.kind == "thread":
        return _remove_thread(ctx, source, feature)
    if source.kind == "brep" and chain is None and feature.kind in EXACT_CAVITY_KINDS:
        return _exact_remove_cavity(ctx, source, feature)
    if source.kind == "brep" and chain is None and feature.kind in EXACT_FACE_KINDS:
        return _exact_remove_by_faces(ctx, source, feature, cavity=cavity)
    answered: dict[str, Any] = {}
    together = False
    if chain is not None:
        choice = params.sections
        if choice == "ask":
            choice = _asked_about_sections(ctx, chain)
            answered["sections"] = choice
        together = choice == "chain"

    if together and chain is not None and source.kind == "brep":
        result = _exact_remove_chain(ctx, source, feature, chain)
        return dataclasses.replace(result, answered=answered)
    if chain is not None and source.kind == "brep":
        result = _exact_remove_section(ctx, source, feature, chain)
        return dataclasses.replace(result, answered=answered)
    if together and chain is not None:
        ctx.progress(0.2, str(_("Der ganze Hohlraum wird geschlossen …")))
        # Erst der gemeinsame Körper aus den Flächen; wo das Netz ihn nicht
        # hergibt, dieselben Abschnitte aus ihren Kennzahlen (Robert,
        # 10.09.2026 — an der eingelesenen Halterung ging beides nicht).
        filled = _cavity_plug(
            body, chain, quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled
        )
        if filled is None:
            raise ValidationError(
                field="at_feature",
                detail=NO_OWN_BODY,
                values={"feature": feature.id},
                constraint="not_movable",
            )
        closed = _without_scars(
            boolean(
                "union",
                [body, filled],
                quality=ctx.quality,
                seed=ctx.seed,
                cancelled=ctx.cancelled,
            )
        )
        gone = tuple(section.id for section in chain)
    elif chain is not None and _inner_sections(chain, feature):
        # **Nur dieser Abschnitt — und der Rest des Hohlraums bleibt offen.**
        # Der eigene Körper des Abschnitts füllte sonst auch den Schlauch
        # darunter zu, und die Bohrung ginge nicht mehr durch (Robert,
        # 10.09.2026). :func:`_section_closed` schneidet ihn danach wieder frei.
        ctx.progress(0.2, str(_("Der Abschnitt wird geschlossen …")))
        section = _section_closed(
            body,
            chain,
            feature,
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        if section is None:
            raise ValidationError(
                field="at_feature",
                detail=NO_OWN_BODY,
                values={"feature": feature.id},
                constraint="not_movable",
            )
        # Erst nach dem Neuschnitt ohne Narben: Davor legte ``_without_scars``
        # die Flächen neu, die der Neuschnitt danach trifft, und an einer
        # gedrehten Senkbohrung fand die Erkennung die Senkung nicht wieder.
        closed = _without_scars(section)
        gone = (feature.id,)
    else:
        # **Steht der Hohlraum allein, ist sein zweiter Randring sein Boden.** Nach
        # dem Verschließen der Bohrung darunter ist die Senkung ein Kegelstumpf mit
        # Material unter sich; die Ringzahl allein sagt das nicht (:func:`_stands_alone`).
        stands_alone = _stands_alone(body, feature, source.features)
        ctx.progress(0.2, str(_("Das Merkmal wird geschlossen …")))
        closed = _closed_at(
            body,
            feature,
            centre,
            cavity,
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
            alone=stands_alone,
        )
        gone = (feature.id,)

    remaining = _without_old_triangles(source.features, without=gone)
    findings = [
        *closed.findings,
        Finding(
            code="remove_feature.gone",
            severity="info",
            message=(
                _(
                    "Der Hohlraum ist mit allen seinen Abschnitten entfernt. Spätere "
                    "Schritte und Passungen, die auf sie verweisen, finden sie nicht mehr."
                )
                if len(gone) > 1
                else _(
                    "Das Merkmal ist entfernt. Spätere Schritte und Passungen, die auf es "
                    "verweisen, finden es nicht mehr."
                )
            ),
            feature_ids=gone,
            values={"feature": feature.id, "kind": feature.kind, "removed": len(gone)},
        ),
    ]
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=closed.mesh,
                features=remaining,
                reserved_feature_ids=tuple(
                    sorted({*source.reserved_feature_ids, *source.features})
                ),
            )
        ],
        findings=findings,
        solver=closed.solver,
        answered=answered,
    )


@op_params
class RotateFeatureParams(BaseParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_("Das erkannte Merkmal, das gedreht wird."),
    )
    axis: Axis = param(
        title=_("Achse"),
        default="x",
        choices=("x", "y", "z"),
        placement="front",
        doc=_("Um welche Achse gedreht wird. Gedreht wird um die Mitte des Merkmals."),
    )
    angle: float = param(
        title=_("Winkel"),
        default=90.0,
        unit=DEGREE_UNIT,
        minimum=-360.0,
        maximum=360.0,
        placement="front",
        doc=_("Wie weit gedreht wird, in Grad."),
    )


@register_op(
    name="rotate_feature",
    # 2: eine schräge Bohrung schließt an ihren Randebenen (22.09.2026).
    # 3: die Kette schließt ohne Narben, der Sackboden reist mit, und eine
    # gekippte Sackbohrung bleibt über ihrem Boden (23.09.2026).
    cache_version="3",
    title=_("Merkmal drehen"),
    category="holes",
    params=RotateFeatureParams,
    consumes=1,
    produces=1,
    # **Ohne die Kugel.** Sie hat keine Lage, die sich drehen ließe — gedreht
    # sähe sie aus wie vorher, und eine Handlung ohne Wirkung ist schlechter
    # als keine (Roberts „alles, was bei den jeweiligen sinnvoll ist").
    # Das Langloch dreht dabei seine Mittellinie mit (``_with_turned_direction``).
    applies_to=["hole", "pin", "cone", "slot", "torus"],
    touches_features=True,
    deterministic=False,
    doc=_(
        "Kippt ein erkanntes Merkmal um seine Mitte: Bohrung, Langloch, Zapfen, "
        "Senkung, Verjüngung, Wulst oder Kehle."
    ),
)
def rotate_feature(ctx: OpContext) -> OpResult:
    """Ein erkanntes Merkmal kippen — dieselbe Maschine, eine Matrix dazwischen.

    **Achse und Winkel, wie bei** :func:`rotate_object`. Das Register spricht
    diese Sprache schon, und wer einen Körper um Z gedreht hat, sucht für eine
    Bohrung nicht nach einer anderen Bedienung.

    **Gedreht wird um die Mitte des Merkmals**, nicht um den Ursprung: Eine
    Bohrung, die beim Kippen davonwandert, ist keine gekippte Bohrung, sondern
    zwei Änderungen, von denen der Kunde eine wollte.

    Eine Kugel bekommt diese Operation nicht: Sie hat keine Lage, die sich
    drehen ließe. Das steht in :data:`MOVABLE_KINDS` noch nicht getrennt, weil
    ``sphere`` dort ohnehin nicht steht — kommt sie dazu, gehört hier eine
    eigene Liste hin.
    """
    params = cast(RotateFeatureParams, ctx.params)
    source = ctx.inputs[0]
    feature = _movable_feature(source, params.at_feature, "rotate_feature")
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])

    if abs(params.angle) <= EPS_DISPLAY:
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="rotate_feature.unchanged",
                    severity="info",
                    message=_("Ohne Winkel bleibt alles, wie es ist."),
                    feature_ids=(feature.id,),
                )
            ],
        )

    turned_axis = _turned(feature, params.axis, params.angle)
    # **Ein Langloch hat neben der Achse eine Richtung, und die dreht mit.**
    # Eine Bohrung um ihre eigene Achse zu drehen ändert nichts; ein Langloch
    # dreht dabei seine Mittellinie. Gemessen am 11.09.2026 ohne diese Zeile:
    # 45 Grad um Z an einem Langloch unter 30 Grad — das Werkzeug stand mit
    # der alten Richtung wieder in der alten Öffnung, am Netz blieb eine
    # Verrundung stehen, am exakten Körper geschah nichts. **Geschlossen wird
    # mit der alten Richtung, gesetzt mit der neuen** — wer beides mit der
    # neuen tut, füllt neben dem Loch und schneidet ein Kreuz hinein.
    spun = _with_turned_direction(feature, params.axis, params.angle)
    cavity = is_a_cavity(feature)
    body = as_mesh_data(source.mesh)
    from app.core.perceive.relations import cavity_chain_state_at

    state = cavity_chain_state_at(feature, source.features, body)
    chain = state.chain
    if (refused := cavity_refusal(state)) is not None:
        raise ValidationError(
            field="at_feature",
            detail=refused,
            values={"feature": feature.id},
            constraint="not_movable",
        )
    if feature.kind == "torus":
        return _rotate_torus(ctx, source, feature, centre, turned_axis)
    if source.kind == "brep" and chain is not None:
        return _exact_rotate_chain(ctx, source, feature, chain, params.axis, params.angle)
    if chain is not None:
        return _rotate_cavity_chain(ctx, source, feature, chain, params.axis, params.angle)
    if source.kind == "brep" and feature.kind in EXACT_CAVITY_KINDS:
        return _exact_rotate_cavity(ctx, source, feature, spun, centre, turned_axis)
    if source.kind == "brep" and feature.kind == "pin":
        return _exact_rotate_pin(ctx, source, feature, centre, turned_axis)
    if source.kind == "brep" and feature.kind == "cone":
        return _exact_rotate_cone(ctx, source, feature, centre, turned_axis, cavity=cavity)
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    closed = _closed_at(
        body,
        feature,
        centre,
        cavity,
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        alone=True,
    )
    ctx.progress(0.6, str(_("Das Merkmal wird gedreht gesetzt …")))
    tool = _turned_through_bore(body, feature, spun, centre, turned_axis)
    if tool is None and cavity and feature.kind == "cone":
        tool = _turned_open_cone(
            body,
            feature,
            np.asarray(transform.rotation(params.axis, params.angle, centre), dtype=np.float64),
            params.angle,
        )
    if tool is not None:
        tool = _within_the_old_rims(
            tool, _old_rim_caps(body, feature, source.features), cancelled=ctx.cancelled
        )
    else:
        tool = _placing_tool(ctx, body, source, spun, centre, cavity, axis=turned_axis)
    placed = boolean(
        "difference" if cavity else "union",
        [closed.mesh, tool],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    moved = dataclasses.replace(
        spun,
        params={**spun.params, "axis": turned_axis},
        provenance="generated",
        face_indices=(),
        surface_patches=(),
    )
    # **Derselbe Befund wie beim Versetzen, und er fehlte hier.** Eine gekippte
    # Bohrung trifft die Gegenseite nicht mehr: Gemessen am 03.09.2026 an einer
    # 12 mm starken Wand mit einer durchgehenden Bohrung Ø 6 blieben nach 30°
    # **86,8 mm³** im alten Schlauch stehen, nach 60° **158,1** — und keiner der
    # beiden Läufe sagte etwas. Gefragt wird mit der **gedrehten** Achse, sonst
    # misst die Prüfung den Schlauch von vorher. Und eine gekippte Bohrung tritt
    # seitlich aus, wo die gerade noch Material hatte — derselbe Kantenbefund
    # wie beim Versetzen, mit der gedrehten Achse.
    findings = [*closed.findings, *placed.findings]
    findings += _edge_findings(closed.mesh, [moved])
    lost = _throughness_lost(
        placed.mesh,
        moved,
        centre,
        "rotate_feature",
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        tool=tool,
    )
    findings += lost
    # **Und die Nachbarwand, wie beim Versetzen mit Senkung und beim Vergrößern.**
    # Um 40° gekippt verband sich eine Bohrung Ø 6 mit der Bohrung 10 mm
    # daneben, und der Bericht schwieg (RM-133, 23.09.2026) — eine Folge, die der
    # Kunde ändern kann, anders als die bloße Volumenänderung.
    if cavity and feature.kind in {"hole", "cone"}:
        findings += _without_opened_twice(
            _neighbour_bore_findings(source, feature, tool, ctx, turned=True), findings
        )
    carried = {**_without_old_triangles(source.features), feature.id: moved}
    if cavity:
        carried.update(
            _measured_on(placed.mesh, [moved], check_cancelled=ctx.cancelled.raise_if_cancelled)
        )
    if lost:
        # Wie beim Versetzen und an der Kette: Der Satz sagt „geht nicht mehr
        # durch", und das Merkmal sagt es auch — hier stand danach weiter
        # ``through=True`` (RM-220).
        turned_bore = carried[feature.id]
        carried[feature.id] = dataclasses.replace(
            turned_bore, params={**turned_bore.params, "through": False}
        )
    floor = _floor_carried(
        body,
        feature,
        source.features,
        np.asarray(transform.rotation(params.axis, params.angle, centre), dtype=np.float64),
    )
    if floor is not None:
        carried[floor.id] = floor
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=placed.mesh, features=carried)],
        findings=findings,
        # Beide Schritte, wie beim Versetzen: Fiel das Schließen an der alten
        # Stelle zurück, gilt diese Stufe samt Startwert für das Ergebnis (§17.2).
        solver=deepest((closed.solver, placed.solver)),
    )


def _rotate_cavity_chain(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    chain: Sequence[Feature],
    axis: Axis,
    angle: float,
) -> OpResult:
    """Eine gesenkte Bohrung kippen — Bohrung und Senkung zusammen (RM-172).

    Gemessen am 14.09.2026 an einer 10-mm-Platte, Bohrung Ø 8 mit Senkung Ø 16,
    die Bohrung gewählt, 30° um X: *Drehen* kippte nur den Stumpf unter der
    Senkung (Mitte z = -2, ``no_longer_through``), die Senkung blieb senkrecht
    stehen. Seit dem 14.09. sagte die Operation ab; seit dem 15.09. nimmt sie
    die Kette mit.

    **Warum der exakte Hohlraum dafür nicht reicht.** Aus seinen Flächen
    geschlossen endet er an den Oberflächen — gedreht um die Bohrungsmitte lag
    seine Decke 0,9 mm **unter** der Platte, ein Einschluss statt einer
    gekippten Senkung. Das Werkzeug braucht Überstand an beiden Enden
    (:func:`_chain_tool`): die Bohrung über ihre Mündung hinaus, die Senkung
    als **größerer Kegel** nach oben — derselbe Kegel, weitergeführt, bis er
    die gekippte Oberfläche überall verlässt. Wie weit, sagt die Neigung:
    :func:`_reach_past_a_tilted_face` rechnet je Ende, was ein Zylinder oder
    Kegel braucht, um eine Fläche, die vorher quer zur Achse stand, nach dem
    Kippen noch zu durchstoßen. Was darüber hinausgeht, schnitte Luft — oder
    eine Wand, die niemand gemeint hat.

    Gedreht wird um die Mitte des **gewählten** Abschnitts, wie bei jedem
    Merkmal: an der Bohrung um deren Mitte, an der Senkung um die Mündung.
    Alle Abschnitte bekommen die gedrehte Achse und ihre gedrehte Mitte, und
    die Bohrung meldet wie beim Versetzen, wenn sie nicht mehr durchgeht.
    Abnahme (Register RM-172): 30° an der gesenkten Bohrung ergibt eine
    gekippte Senkung über einer gekippten, durchgehenden Bohrung, und die
    Erkennung findet beide mit derselben Achse.
    """
    body = as_mesh_data(source.mesh)
    pivot = np.asarray(feature.params["centre"], dtype=float)
    matrix = np.asarray(
        transform.rotation(axis, angle, cast(Vec3, tuple(float(value) for value in pivot))),
        dtype=np.float64,
    )
    old_axis = np.asarray(_feature_direction(chain[0]), dtype=float)
    new_axis = matrix[:3, :3] @ old_axis
    tilt = math.degrees(math.acos(min(1.0, abs(float(old_axis @ new_axis)))))
    _sinks_must_close(chain, tilt, angle)

    ctx.progress(0.1, str(_("Der ganze Hohlraum wird geschlossen …")))
    filled = _cavity_plug(body, chain, quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled)
    tool = _chain_tool(body, chain, pivot=pivot, tilt=tilt)
    if filled is None or tool is None:
        raise ValidationError(
            field="at_feature",
            detail=NO_OWN_BODY,
            values={"feature": feature.id, "bore": chain[0].id, "widening": chain[-1].id},
            constraint="not_movable",
        )
    closed = _without_scars(
        boolean(
            "union",
            [body, filled],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
    )
    turned = tool.raw.copy()
    transform.moved(turned, matrix)
    turned_tool = _within_the_old_rims(
        MeshData.of(turned),
        _old_rim_caps(body, chain[0], source.features, chain),
        cancelled=ctx.cancelled,
    )
    ctx.progress(0.6, str(_("Der Hohlraum wird gedreht gesetzt …")))
    placed = boolean(
        "difference",
        [closed.mesh, turned_tool],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    features = _without_old_triangles(source.features)
    for member in chain:
        spun = _with_turned_direction(member, axis, angle)
        centre = matrix[:3, :3] @ (np.asarray(member.params["centre"], dtype=float) - pivot) + pivot
        features[member.id] = dataclasses.replace(
            spun,
            params={
                **spun.params,
                "centre": tuple(float(value) for value in centre),
                "axis": _turned(member, axis, angle),
            },
            provenance="generated",
            face_indices=(),
            surface_patches=(),
        )
    floor = _floor_carried(body, chain[0], source.features, matrix)
    if floor is not None:
        features[floor.id] = floor
    bore = features[chain[0].id]
    bore_centre = cast(Vec3, tuple(float(value) for value in bore.params["centre"]))
    findings = [*closed.findings, *placed.findings]
    findings += _edge_findings(closed.mesh, [features[member.id] for member in chain])
    lost = _throughness_lost(
        placed.mesh,
        bore,
        bore_centre,
        "rotate_feature",
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        tool=turned_tool,
    )
    findings += lost
    features.update(
        _measured_on(
            placed.mesh,
            [features[member.id] for member in chain],
            check_cancelled=ctx.cancelled.raise_if_cancelled,
        )
    )
    if lost:
        measured_bore = features[bore.id]
        features[bore.id] = dataclasses.replace(
            measured_bore, params={**measured_bore.params, "through": False}
        )
    findings += _without_opened_twice(
        _neighbour_bore_findings(source, feature, turned_tool, ctx, turned=True), findings
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=placed.mesh, features=features)],
        findings=findings,
        solver=deepest((closed.solver, placed.solver)),
    )


def _old_rim_caps(
    body: MeshData,
    feature: Feature,
    features: Mapping[FeatureId, Feature],
    chain: Sequence[Feature] | None = None,
) -> tuple[SectionPlane, ...]:
    """Die Ebenen, an denen ein gekipptes Werkzeug endet: die alten Ränder des
    Hohlraums, soweit dort eine Fläche liegt, die nicht mitkippt.

    **Was über eine Mündung hinausreicht, schneidet nur, was davor steht**
    (RM-220, 25.09.2026). Damit eine gekippte Bohrung durchgeht und eine
    gekippte Senkung die Fläche überall verlässt, verlängern
    :func:`_reach_past_a_tilted_face` und :func:`_cone_past_a_tilted_face` das
    Werkzeug über die Mündungen hinaus — eine 90°-Senkung unter 30° als Kegel
    fast doppelt so weit wie ihr Durchmesser, der exakte Kern eine
    Durchgangsbohrung über die ganze Hülle. Vor der Fläche liegt sonst Luft; wo
    dort Material steht, nahm die Verlängerung es mit. Am Schraubenhalter mit
    Wabenmuster lagen von 714 mm³ Abtrag 314 vor der Rückwand, in den Waben
    davor; an einer Platte mit Rippe über der Senkung waren es an beiden Kernen
    rund 740 mm³, und der exakte Kern bohrte eine gekippte Durchgangsbohrung
    durch Rippe und Fuß, wo das Netz vor ihnen endete.

    Gekappt wird an den echten Randringen der Kette bis zur äußeren Mündung
    (:func:`_bore_end_planes`), an offenen Mündungen um die Zugabe aus §39
    davor. **Die äußere Ebene gilt immer**, auch unter einem Deckel: Eine
    Senkung, deren Rand unter der Oberfläche liegt, reicht gekippt bis an den
    Deckel und nicht durch ihn hindurch. **Die ferne nur bei einer
    Durchgangsbohrung** — am Sackloch ist sie der Boden, und der kippt mit
    (``_chain_tool``: dort gibt es keine Verlängerung). Wo die Ränder keine
    flachen Ringe sind, gibt es keine Ebenen, und das Werkzeug bleibt, wie es
    ist. Beide Kerne fragen dasselbe — der exakte an seinem Netz-Zwilling.

    **Weitet sich die Bohrung an beiden Enden** (RM-245), sind beide Ränder
    Mündungen einer Erweiterung, und beide Ebenen gelten — wie an einer
    Durchgangsbohrung.
    """
    from app.core.perceive.relations import cavity_sides

    rims = _bore_end_planes(body, feature, features, grows=True)
    if not rims:
        return ()
    if feature.params.get("through") or (chain is not None and len(cavity_sides(chain)) == 2):
        return rims if len(rims) == 2 else ()
    if chain is not None and len(chain) >= 2:
        towards = np.asarray(chain[-1].params["centre"], dtype=float) - np.asarray(
            feature.params["centre"], dtype=float
        )
    elif feature.kind == "cone":
        # Eine Senkung ohne Bohrung weitet sich entlang ihrer Achse nach außen.
        towards = np.asarray(_feature_direction(feature), dtype=float)
    else:
        return ()
    return tuple(plane for plane in rims if units.dot3(plane.normal, towards) > 0.0)


def _within_the_old_rims(
    tool: MeshData, caps: Sequence[SectionPlane], *, cancelled: CancelToken | None
) -> MeshData:
    """Ein gekipptes Netzwerkzeug an den Ebenen aus :func:`_old_rim_caps` gekappt.

    **Scheitert der ebene Schnitt, kappen Quader** (25.09.2026). An der Öffnung
    eines Mini-Topfs — Ø 28 in einer 0,3 mm dünnen Wand, die Ebenen 0,44 mm
    auseinander — kam das gekippte Werkzeug aus :func:`_cut_at_the_rims` ohne
    geschlossenen Deckel zurück, und hier stand dann das ungekappte: 59 mm³
    Abtrag vor den alten Mündungen, genau der Fehler, den die Kappe verhindert.
    Je Ebene ein Quader auf ihrer Innenseite, groß genug für das ganze
    Werkzeug, über die Boolesche Kette geschnitten; erst wenn auch das nichts
    Geschlossenes hergibt, bleibt das Werkzeug, wie es ist.
    """
    if not caps:
        return tool
    clipped = _cut_at_the_rims(tool, caps)
    if clipped is not None:
        return clipped
    return _boxed_in(tool, caps, cancelled=cancelled) or tool


def _boxed_in(
    tool: MeshData, planes: Sequence[SectionPlane], *, cancelled: CancelToken | None
) -> MeshData | None:
    """``tool`` auf der Innenseite jeder Ebene — ``None``, wo das keinen
    geschlossenen Körper ergibt.

    **Nur auf den verlustfreien Stufen** (``DRAFT_CHAIN``, in jeder Qualität).
    Die Kappe begrenzt ein Werkzeug, das ohne sie schon rechnet; gestört oder
    auf Voxeln gerechnet, veränderte sie seine Form still — der Befund dazu
    ginge mit dem Werkzeug verloren, und die Stufe stünde nicht im Schritt
    (§17.2). Bis zum 25.09.2026 lief die Schnittmenge in feiner Qualität über
    alle vier Stufen, mit dem Startwert null statt dem des Schritts und ohne
    Abbruchmarke; hielt keine Stufe, brach der ganze Schritt ab, statt beim
    ungekappten Werkzeug zu bleiben.
    """
    size = 4.0 * float(tool.bounds.diagonal) + 1.0
    middle = np.asarray(tool.bounds.centre, dtype=np.float64)
    boxes = []
    for plane in planes:
        normal = np.asarray(plane.normal, dtype=np.float64)
        normal /= math.hypot(*(float(value) for value in normal))
        # Der Fußpunkt der Werkzeugmitte auf der Ebene: Dort liegt die obere
        # Fläche des Quaders, und er reicht nach innen und nach allen Seiten
        # über das Werkzeug hinaus.
        foot = middle - normal * (units.dot3(normal, middle) - plane.position)
        box = trimesh.creation.box(extents=(size, size, size))
        transform.moved(box, transform.rotation_between([0.0, 0.0, 1.0], normal))
        box.apply_translation(foot - normal * (size / 2.0))
        boxes.append(MeshData.of(box))
    try:
        outcome = boolean(
            "intersection",
            [tool, *boxes],
            stages=DRAFT_CHAIN,
            allow_empty=True,
            cancelled=cancelled,
        )
    except BooleanFailedError:
        # Der dokumentierte Rückfall: Das Werkzeug bleibt ungekappt
        # (:func:`_within_the_old_rims`). Ein Abbruch ist keine solche Absage
        # und geht als ``OperationCancelled`` weiter.
        return None
    body = outcome.mesh
    if not len(body.raw.faces) or not body.is_watertight or body.volume <= EPS_GEOM:
        return None
    return body


def _turned_open_cone(
    body: MeshData, feature: Feature, matrix: NDArray[np.float64], angle: float
) -> MeshData | None:
    """Das Werkzeug einer gekippten Senkung ohne Bohrung — ``None``, wo ihre
    Flächen kein Maß hergeben.

    Gedreht wird um die Mitte des weiten Endes, wie am exakten Körper
    (``_exact_rotate_cone``): Der gemessene Hohlraum, gekippt, sank auf der
    einen Seite unter die Fläche und behielt dort eine Decke — um 20° gekippt
    trug er 6 mm³ ab und gab 17 zurück, am exakten Körper waren es 22 mm³
    (RM-220, 25.09.2026). Deshalb wie dort und wie an der Kette
    (:func:`_chain_tool`): derselbe Kegel aus seinen Kennzahlen, über das weite
    Ende hinaus so weit weitergeführt, wie die Neigung verlangt
    (:func:`_cone_past_a_tilted_face`), am engen Ende genau so tief wie
    gemessen — dort liegt sein Boden, und der kippt mit. Gekappt wird danach
    an der alten Randebene (:func:`_old_rim_caps`).
    """
    wide = float(feature.params.get("diameter", 0.0)) / 2.0
    half = float(feature.params.get("angle", 0.0)) / 2.0
    if wide <= EPS_GEOM or not EPS_GEOM < half < 90.0 - EPS_GEOM or not feature.face_indices:
        return None
    outward = np.asarray(_feature_direction(feature), dtype=np.float64)
    outward /= math.hypot(*(float(value) for value in outward))
    turned = matrix[:3, :3] @ outward
    tilt = math.degrees(math.acos(min(1.0, abs(float(units.dot3(outward, turned))))))
    _sink_must_close(feature, tilt, angle)
    centre = np.asarray(feature.params["centre"], dtype=np.float64)
    raw = body.raw
    valid = [index for index in feature.face_indices if 0 <= index < len(raw.faces)]
    if not valid:
        return None
    points = np.asarray(raw.vertices, dtype=np.float64)[np.unique(raw.faces[valid])]
    relative = points - centre
    along = relative[:, 0] * outward[0] + relative[:, 1] * outward[1] + relative[:, 2] * outward[2]
    depth = -float(along.min())
    if depth <= EPS_GEOM:
        return None
    slope = math.tan(math.radians(half))
    narrow = max(0.0, wide - depth * slope)
    beyond = _cone_past_a_tilted_face(0.0, wide, half, tilt, at_most=float(body.bounds.diagonal))
    # Das obere Ende samt Zugabe liegt auf derselben Flanke: Mit dem Radius der
    # Weiterführung ohne Zugabe lief der Mantel über die ganze Länge steiler als
    # der gemessene Kegel — an einer 90°-Senkung 0,02 mm am oberen Rand.
    top = beyond + FEATURE_OVERLAP
    outline = [
        [0.0, -depth],
        [narrow, -depth],
        [wide + top * slope, top],
        [0.0, top],
    ]
    solid = lathe.revolve(outline, sections=FEATURE_SECTIONS)
    transform.moved(solid, transform.rotation_between([0.0, 0.0, 1.0], outward))
    solid.apply_translation(centre)
    transform.moved(solid, matrix)
    return MeshData.of(solid) if solid.is_watertight and solid.volume > EPS_GEOM else None


def _turned_through_bore(
    body: MeshData, feature: Feature, spun: Feature, centre: Vec3, turned_axis: Vec3
) -> MeshData | None:
    """Das Werkzeug einer gekippten **Durchgangsbohrung** — lang genug, dass sie
    durchgehend bleibt; ``None`` für alles andere.

    Das übliche Werkzeug ist die gemessene Bohrung selbst (``_tool_for``) und
    endet, gekippt, vor den Oberflächen: Gemessen an einer 12 mm starken Wand
    blieben nach 30° **86,8 mm³** im Schlauch, nach 60° **158,1**, und der
    Befund ``no_longer_through`` war alles, was der Kunde bekam. Eine gekippte
    Durchgangsbohrung soll durchgehen — so tun es die gesenkte Bohrung
    (:func:`_rotate_cavity_chain`, RM-172) und der exakte Kern
    (``_through_bore_depth``) seit ihrem Bau (RM-133, 23.09.2026). Wie weit,
    rechnet :func:`_reach_past_a_tilted_face` aus Wandstärke, Radius und
    Neigung, mit derselben Obergrenze wie die Kette; darüber hinaus schnitte das
    Werkzeug Luft oder eine Wand, die niemand gemeint hat. Bleibt trotzdem
    Material im Schlauch — an einer schrägen Wand etwa —, sagt es
    ``_throughness_lost`` wie bisher.
    """
    if feature.kind != "hole" or not feature.params.get("through"):
        return None
    old_axis = np.asarray(_feature_direction(feature), dtype=np.float64)
    new_axis = np.asarray(turned_axis, dtype=np.float64)
    tilt = math.degrees(math.acos(min(1.0, abs(float(old_axis @ new_axis)))))
    if tilt <= EPS_DISPLAY:
        return None
    diameter = float(feature.params.get("diameter", 0.0))
    depth = float(feature.params.get("depth", 0.0))
    if diameter <= EPS_GEOM or depth <= EPS_GEOM:
        return None
    reach = _reach_past_a_tilted_face(
        depth / 2.0, diameter / 2.0, tilt, at_most=float(body.bounds.diagonal)
    )
    stretched = dataclasses.replace(spun, params={**spun.params, "depth": 2.0 * reach})
    return _feature_solid(stretched, centre, axis=turned_axis, oversize=0.0)


def _sink_must_close(cone: Feature, tilt: float, angle: float) -> None:
    """Sagt ab, wo eine gekippte Senkung sich auf ihrer Fläche nicht mehr schließt.

    Kippt eine Senkung um ihren halben Öffnungswinkel oder mehr, liegt ihre
    Flanke flacher als die Fläche, aus der sie kommt, und verlässt sie nie
    (:func:`_cone_past_a_tilted_face` gibt dann die Obergrenze). Gekappt an
    der alten Randebene, lief sie als Rinne bis an den Rand des Körpers: eine
    90°-Senkung Ø 10 in einer Platte 30 x 24 x 12, um 45° gekippt, trug 671 mm³
    ab, acht Prozent der Platte, und hieß danach „über die Kante" (RM-220,
    25.09.2026). Das ist keine Senkung mehr, und der Satz nennt den größten
    Winkel, unter dem sie eine bleibt. ``tilt`` ist der Winkel zwischen alter
    und neuer Achse, ``angle`` der eingegebene Drehwinkel.
    """
    half = float(cone.params.get("angle", 0.0)) / 2.0
    if half <= EPS_DISPLAY or tilt + half < 90.0 - EPS_DISPLAY:
        return
    raise ValidationError(
        "angle",
        _(
            "Um diesen Winkel gekippt, schließt sich die Senkung auf ihrer Fläche nicht mehr "
            "— sie liefe als Rinne über das Teil. Kippen Sie sie um weniger als "
            "{largest:.1f} Grad.",
            largest=90.0 - half,
        ),
        value=angle,
        constraint="sink_runs_out",
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def _sinks_must_close(chain: Sequence[Feature], tilt: float, angle: float) -> None:
    """:func:`_sink_must_close` an der äußeren Senkung jeder Seite einer Kette.

    Eine Bohrung, die sich an beiden Enden weitet, hat zwei Mündungen
    (``relations.cavity_sides``, RM-245); jede Senkung darunter muss sich auf
    ihrer Fläche schließen. Gefragt wird die mit dem größeren Öffnungswinkel
    zuerst: Sie erlaubt die kleinere Neigung, und der Satz nennt diese.
    """
    from app.core.perceive.relations import cavity_sides

    outer = [side[-1] for side in cavity_sides(chain) if side[-1].kind == "cone"]
    for cone in sorted(outer, key=lambda sink: -float(sink.params.get("angle", 0.0))):
        _sink_must_close(cone, tilt, angle)


def _reach_past_a_tilted_face(
    distance: float, radius: float, tilt: float, *, at_most: float
) -> float:
    """Wie weit ein Zylinder vom Drehpunkt aus reichen muss, um eine Fläche
    zu durchstoßen, die vor dem Kippen quer zu seiner Achse stand.

    ``distance`` ist der Abstand des Drehpunkts zu dieser Fläche entlang der
    alten Achse, ``radius`` der des Zylinders, ``tilt`` der Winkel zwischen
    alter und neuer Achse. Nach dem Kippen liegt der Durchstoß bei
    ``distance / cos(tilt)``, und der ferne Rand des Zylinders braucht dazu
    ``radius · tan(tilt)`` — bei 30° an einer Bohrung Ø 8, 5 mm über dem
    Drehpunkt, sind das 5,8 + 2,3 statt 5. Ab 90° gibt es keinen Durchstoß
    durch diese Fläche mehr; dann gilt die Obergrenze, und die ist der
    Körper selbst (``at_most``).
    """
    if tilt >= 90.0 - EPS_DISPLAY:
        return at_most
    needed = distance / units.exact_cos_degrees(tilt) + radius * math.tan(math.radians(tilt))
    return max(distance, min(needed, at_most))


def _cone_past_a_tilted_face(
    distance: float, radius: float, half_angle: float, tilt: float, *, at_most: float
) -> float:
    """Wie weit ein Kegel über seine Mündung hinaus weitergeführt werden muss,
    damit er nach dem Kippen die Oberfläche überall verlässt.

    Die Mündung mit Radius ``radius`` liegt ``distance`` über dem Drehpunkt;
    ``half_angle`` ist der halbe Öffnungswinkel. Gekippt um ``tilt`` sinkt die
    Mündungsmitte auf ``distance · cos(tilt)``, und der tiefe Rand des Kegels
    steigt je Millimeter Weiterführung nur um ``cos(tilt) - tan(half) ·
    sin(tilt)`` — bei einer 90°-Senkung unter 30° um 0,366. Für die gemessene
    Platte (Mündung 7 mm über der Bohrungsmitte, Ø 16) heißt das 13,5 mm; ohne
    sie blieb ein Einschluss unter der Decke. Ist die Flanke flacher als die
    gekippte Fläche, kommt der Kegel nie mehr heraus — dann gilt ``at_most``.
    """
    cos_tilt = units.exact_cos_degrees(tilt)
    sin_tilt = units.exact_sin_degrees(tilt)
    climb = cos_tilt - math.tan(math.radians(half_angle)) * sin_tilt
    if climb <= EPS_GEOM:
        return at_most
    needed = (distance * (1.0 - cos_tilt) + radius * sin_tilt) / climb
    return max(0.0, min(needed, at_most))


def _welded(mesh: MeshData) -> Any:
    """Die verschweißte Kopie eines Körpers — einmal je Körper, und nur gelesen.

    Randringe und Schulterprobe der Bohrungskette (``bore_entrance``,
    ``_bore_end_planes``) lesen Ecken, die an unverschweißten STL-Dreiecken
    geometrisch zusammenfallen. Je Frage eine Kopie zu verschweißen kostete am
    Gartenschlauchhalter mit 392 532 Dreiecken 73 ms, und das Merkmalfenster
    fragte je Klick auf eine gesenkte Bohrung bis zu fünfmal (RM-181, gemessen
    am 22.09.2026). Die Antwort hängt allein am Körper; niemand verändert sie.
    """
    from app.core.perceive.features import remembered

    def weld() -> Any:
        body = mesh.raw.copy()
        body.merge_vertices()
        return body

    return remembered("merged_copy", mesh.raw, (), weld)


def _mouth_is_open(mesh: MeshData, edge: NDArray[np.float64], normal: NDArray[np.float64]) -> bool:
    """Vor dem gesamten Rand liegt Luft; ein Sacklochboden bleibt geschlossen."""
    # Ein Anteil aus Zählungen, nie negativ — gefragt wird „keine Probe im
    # Material", ohne Gleichheit auf Fließkomma (Regel 6).
    return _share_in_material(mesh, edge, normal) <= 0.0


def _share_in_material(
    mesh: MeshData, edge: NDArray[np.float64], normal: NDArray[np.float64]
) -> float:
    """Welcher Anteil der Proben knapp vor dem Rand im Material liegt — die Probe
    von :func:`_mouth_is_open`, gezählt statt nur gefragt."""
    from app.core.geom.mesh import on_surface

    inward = edge.mean(axis=0) - edge
    inward /= np.maximum(np.linalg.norm(inward, axis=1), EPS_GEOM)[:, None]
    probes = edge + inward * FEATURE_OVERLAP + normal * FEATURE_OVERLAP
    closest, _, at = on_surface(mesh.raw, probes, index=surface_index_of(mesh))
    body_normals = np.asarray(mesh.raw.face_normals, dtype=np.float64)
    signed = np.einsum("ij,ij->i", probes - closest, body_normals[at])
    return float(np.count_nonzero(signed <= EPS_GEOM)) / float(max(len(signed), 1))


def _past_the_mouths(mesh: MeshData, cavity: MeshData) -> MeshData:
    """Der exakte Hohlraumkörper, an seinen Mündungen um ``FEATURE_OVERLAP``
    über die Oberfläche hinaus verlängert — das Werkzeug für die Differenz (§39).

    Ein Hohlraum aus seinen Flächen (:func:`_body_from_faces`) endet bündig
    in der Oberfläche, und eine bündige Differenz lässt eine Haut stehen. Das
    Werkzeug aus Kennzahlen wäre der Ausweg, kann aber eine andere
    Facettierung tragen als der Pfropfen aus den Originalflächen. Hier bleibt es bei den echten
    Dreiecken: Jeder ebene Deckel des Körpers, hinter dem **kein Material**
    liegt, ist eine Mündung und bekommt einen Kragen — der Ring wird um die
    Zugabe nach außen kopiert, die Wand dazwischen ergänzt, der Deckel wandert
    mit. Was über die Oberfläche hinausragt, trifft kein Material und ändert
    kein Volumen. Ein Deckel, hinter dem Material liegt, ist der Boden eines
    Sacklochs und bleibt, wo er ist — ein Kragen dort machte die Bohrung tiefer.

    Ob hinter einem Deckel Material liegt, sagt die nächste Oberfläche des
    Körpers zu Punkten knapp vor ihm (``on_surface``, dieselbe Probe wie in
    :func:`_frame_from_material`) — **entlang seines Rands**, nicht in seiner
    Mitte: An einer Ringstufe endet die Zylindersenkung Ø 11,5 über einem
    Kegel Ø 11, und vor der Mitte ihres Deckels liegt der leere Kegel, vor
    seinem Rand aber der Ring aus Material. Geprüft an der Mitte bekam die
    Stufe einen Kragen und wurde um die Zugabe abgetragen (0,18 mm³, gemessen
    15.09.2026). Kommt kein geschlossener Körper heraus, bleibt das Werkzeug
    der unveränderte Hohlraum.
    """
    raw = cavity.raw
    points = np.asarray(raw.vertices, dtype=np.float64)
    faces = np.asarray(raw.faces, dtype=np.int64).copy()
    normals = np.asarray(raw.face_normals, dtype=np.float64)
    added: list[NDArray[np.float64]] = [points]
    collars: list[NDArray[np.int64]] = []
    next_index = len(points)
    for facet in raw.facets:
        # Wandstreifen sind Paare von Dreiecken; ein Deckel ist ein Fächer.
        if len(facet) < 3:
            continue
        cap = faces[facet]
        normal = normals[int(facet[0])]
        members = np.unique(cap)
        directed = np.vstack([cap[:, [0, 1]], cap[:, [1, 2]], cap[:, [2, 0]]])
        _, inverse, counts = np.unique(
            np.sort(directed, axis=1), axis=0, return_inverse=True, return_counts=True
        )
        rim = directed[counts[inverse.ravel()] == 1]
        if len(rim) < 3:
            continue
        # Die Probe: je Randpunkt ein wenig zur Mitte und um die Zugabe vor den
        # Deckel — erst wenn dort überall Luft ist, ist der Deckel eine Mündung.
        if not _mouth_is_open(mesh, points[rim[:, 0]], normal):
            continue
        lifted = np.full(int(members.max()) + 1, -1, dtype=np.int64)
        lifted[members] = np.arange(next_index, next_index + len(members))
        added.append(points[members] + normal * FEATURE_OVERLAP)
        next_index += len(members)
        faces[facet] = lifted[cap]
        first, second = rim[:, 0], rim[:, 1]
        collars.append(np.column_stack([first, second, lifted[second]]))
        collars.append(np.column_stack([first, lifted[second], lifted[first]]))
    if not collars:
        return cavity
    widened = trimesh.Trimesh(
        vertices=np.vstack(added), faces=np.vstack([faces, *collars]), process=False
    )
    if not widened.is_watertight or widened.volume <= raw.volume - EPS_GEOM:
        return cavity
    return MeshData.of(widened)


def _chain_tool(
    mesh: MeshData, chain: Sequence[Feature], *, pivot: NDArray[np.float64], tilt: float
) -> MeshData | None:
    """Der Hohlraum einer Kette als Werkzeug — aus Kennzahlen, mit Überstand an
    beiden Enden, in der **alten** Lage gebaut; gedreht wird er danach.

    Die Bohrung (``chain[0]``) reicht über ihre ferne Mündung hinaus, die
    äußere Erweiterung (``chain[-1]``) über ihre — ein Kegel als größerer
    Kegel, ein Zylinder als längerer. Was dazwischen liegt, kommt exakt aus
    :func:`_measured_section`. Wie weit die Enden reichen, rechnen
    :func:`_reach_past_a_tilted_face` und :func:`_cone_past_a_tilted_face`
    aus der Neigung; ohne Neigung ist der Überstand null, und das Werkzeug ist
    der Hohlraum in seinen Maßen — plus der Zugabe an den Enden, die jede
    Boolesche braucht (§39).

    **Weitet sich die Bohrung an beiden Enden** (RM-245), hat sie selbst keine
    Mündung: Sie steht in ihren Maßen da, und jede Seite reicht über ihre
    eigene äußere Erweiterung hinaus (``relations.cavity_sides``).

    ``None``, wenn ein Abschnitt aus seinen Kennzahlen keinen Körper hergibt.
    """
    from app.core.perceive.relations import cavity_sides

    at_most = float(mesh.bounds.diagonal)
    sides = cavity_sides(chain)
    bore = chain[0]
    bore_axis = np.asarray(_feature_direction(bore), dtype=np.float64)
    bore_centre = np.asarray(bore.params["centre"], dtype=np.float64)

    bodies: list[MeshData] = []
    if len(sides) == 1:
        towards = np.asarray(chain[1].params["centre"], dtype=np.float64) - bore_centre
        away = -bore_axis if float(towards @ bore_axis) > 0.0 else bore_axis
        diameter = float(bore.params.get("diameter", 0.0))
        depth = float(bore.params.get("depth", 0.0))
        half = (depth if depth > EPS_GEOM else diameter) / 2.0
        mouth = float((bore_centre + away * half - pivot) @ away)
        extension = _reach_past_a_tilted_face(mouth, diameter / 2.0, tilt, at_most=at_most) - mouth
        # **Ein Sackloch hat am fernen Ende keine Mündung, sondern seinen Boden**
        # (23.09.2026): Dort gibt es keine gekippte Fläche zu durchstoßen, und jede
        # Verlängerung — auch die Zugabe aus §39 — schnitte unter den Boden. An
        # einer gesenkten Sackbohrung, um 10° gekippt, trug das Netz so 18,3 mm³
        # zu viel ab, 0,6 mm unter den gedrehten Boden.
        blind = not bore.params.get("through", False)
        stretched = _stretched_section(bore, away, 0.0 if blind else extension, closed_end=blind)
    else:
        stretched = _stretched_section(bore, bore_axis, 0.0)
    if stretched is None:
        return None
    bodies.append(stretched)

    for side in sides:
        for member in side[1:-1]:
            part = _measured_section(side, member)
            if part is None:
                return None
            bodies.append(part)

        outer = side[-1]
        outward = _outward_axis(side, outer)
        outer_centre = np.asarray(outer.params["centre"], dtype=np.float64)
        if outer.kind == "cone":
            wide = float(outer.params.get("diameter", 0.0))
            half_angle = float(outer.params.get("angle", 0.0)) / 2.0
            rise = float((outer_centre - pivot) @ outward)
            beyond = _cone_past_a_tilted_face(rise, wide / 2.0, half_angle, tilt, at_most=at_most)
            part = _measured_section(side, outer, outward=beyond)
        else:
            diameter = float(outer.params.get("diameter", 0.0))
            depth = float(outer.params.get("depth", 0.0))
            half = (depth if depth > EPS_GEOM else diameter) / 2.0
            mouth = float((outer_centre + outward * half - pivot) @ outward)
            beyond = _reach_past_a_tilted_face(mouth, diameter / 2.0, tilt, at_most=at_most) - mouth
            part = _stretched_section(outer, outward, beyond)
        if part is None:
            return None
        bodies.append(part)
    return boolean("union", bodies, quality="fine", seed=None).mesh


def _stretched_section(
    feature: Feature,
    outward: NDArray[np.float64],
    extension: float,
    *,
    closed_end: bool = False,
) -> MeshData | None:
    """Ein zylindrischer Abschnitt aus seinen Kennzahlen, um ``extension``
    über sein Ende hinaus verlängert — in Richtung ``outward``.

    Ohne Verlängerung ist es der Körper aus :func:`_feature_solid` mit exaktem
    Querschnitt: so weit wie gemessen, mit der Zugabe an
    beiden Enden. ``closed_end`` sagt, dass das Ende in Richtung ``outward``
    ein Boden ist: Dort endet der Körper genau, ohne Zugabe und ohne
    Verlängerung.
    """
    if feature.kind == "cone":
        return None
    diameter = float(feature.params.get("diameter", 0.0))
    if diameter <= EPS_GEOM:
        return None
    depth = float(feature.params.get("depth", 0.0))
    # Am Boden wird die Zugabe zurückgenommen statt verlängert.
    extension = -FEATURE_OVERLAP if closed_end else max(0.0, extension)
    height = (depth if depth > EPS_GEOM else diameter) + 2.0 * FEATURE_OVERLAP
    body = lathe.cylinder(
        radius=diameter / 2.0, height=height + extension, sections=FEATURE_SECTIONS
    )
    body.apply_translation((0.0, 0.0, extension / 2.0))
    transform.moved(
        body,
        transform.rotation_between([0.0, 0.0, 1.0], outward),
    )
    body.apply_translation(np.asarray(feature.params["centre"], dtype=float))
    return MeshData.of(body)


def _turned(feature: Feature, axis: Axis, angle: float) -> Vec3:
    """Die Achse des Merkmals, um ``axis`` um ``angle`` Grad gedreht."""
    return _turned_vector(feature.params.get("axis", (0.0, 0.0, 1.0)), axis, angle)


def _turned_vector(vector: Any, axis: Axis, angle: float) -> Vec3:
    """Ein Richtungsvektor, um ``axis`` um ``angle`` Grad gedreht und normiert."""
    direction = np.asarray(vector, dtype=float)
    # Aus den exakten Winkelfunktionen (``transform.rotation``, RM-187): Ein
    # rechter Winkel dreht exakt, sonst trug die Achse einer um 90° gekippten
    # Bohrung ``math.cos(π/2)`` = 6·10⁻¹⁷ als Rest.
    matrix = transform.rotation(axis, angle)
    spun = np.asarray(matrix, dtype=float)[:3, :3] @ direction
    length = float(np.linalg.norm(spun)) or 1.0
    spun = spun / length
    return (float(spun[0]), float(spun[1]), float(spun[2]))


def _with_turned_direction(feature: Feature, axis: Axis, angle: float) -> Feature:
    """Das Merkmal mit mitgedrehter Mittellinie — oder unverändert, wenn es keine hat.

    Nur das Langloch trägt eine ``direction``; Bohrung, Zapfen und Kegel sind
    um ihre Achse symmetrisch und brauchen keine.
    """
    direction = feature.params.get("direction")
    if direction is None:
        return feature
    return dataclasses.replace(
        feature, params={**feature.params, "direction": _turned_vector(direction, axis, angle)}
    )


#: Wie weit ein neuer Durchmesser über die Diagonale des Körpers hinausgehen
#: darf, bevor er kein Merkmal mehr ist, sondern ein Speicherproblem: Die
#: Felder tragen absichtlich keine feste Obergrenze — ein gemessenes Maß von
#: 250 mm darf nicht beim bloßen Übernehmen geklemmt werden —, aber ein
#: Werkzeug von tausend Metern baut niemand absichtlich (Review 06.09.2026,
#: dieselbe Familie wie G-09 und G-13).
OVERSIZE_FACTOR = 4.0


def _reject_oversized(field: str, diameter: float, mesh: Mesh, *, kind: str = "diameter") -> None:
    """Lehnt ein Maß ab, das ein Vielfaches des ganzen Körpers misst.

    ``kind`` sagt, **was** der Kunde eingetippt hat. Der Satz nannte immer
    einen Durchmesser; seit ein Langloch seine Länge durch dieselbe Schranke
    schickt, wäre das die falsche Auskunft über die richtige Zahl — wer 2000
    statt 20 tippt, soll lesen, welches seiner Felder gemeint ist (Regel 17).
    """
    limit = OVERSIZE_FACTOR * max(float(mesh.bounds.diagonal), 1.0)
    if diameter > limit:
        raise ValidationError(
            field,
            (
                _(
                    "Ein Durchmesser von {given} übersteigt den Körper um ein Vielfaches. "
                    "Wählen Sie höchstens {limit}.",
                    given=format_length(diameter),
                    limit=format_length(limit),
                )
                if kind == "diameter"
                else _(
                    "Eine Länge von {given} übersteigt den Körper um ein Vielfaches. "
                    "Wählen Sie höchstens {limit}.",
                    given=format_length(diameter),
                    limit=format_length(limit),
                )
            ),
            value=diameter,
            constraint="maximum",
            values={"maximum": limit},
        )


@op_params
class ResizeFeatureParams(BaseParams):
    at_feature: str = param(
        title=_("Merkmal"),
        default="",
        kind="feature",
        required=True,
        placement="front",
        doc=_("Das erkannte Merkmal, dessen Maß geändert wird."),
    )
    diameter: float = param(
        title=_("Durchmesser"),
        default=8.0,
        unit="mm",
        minimum=0.5,
        placement="front",
        doc=_("Der neue Durchmesser. Beim Anklicken steht hier sein gemessener."),
    )
    tube_diameter: float = param(
        title=_("Rohrdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_(
            "Nur an einem Ring: die Dicke des Wulstes oder die Breite der Kehle. "
            "Null lässt sie unverändert."
        ),
    )
    pitch: float = param(
        title=_("Steigung"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_(
            "An einem Gewinde die neue Steigung, an einem Muster die neue Teilung — der "
            "Abstand von Zelle zu Zelle. Null lässt sie unverändert."
        ),
    )
    cell_width: float = param(
        title=_("Zellbreite"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_(
            "Nur an einem Muster: die neue Breite einer Zelle — Schlüsselweite der Wabe, "
            "Breite der Rippe, Durchmesser der Noppe. Null lässt sie unverändert."
        ),
    )
    cell_depth: float = param(
        title=_("Zelltiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_(
            "Nur an einem Muster: wie tief die Zellen werden, vertieft wie erhaben. "
            "Null lässt sie unverändert."
        ),
    )
    style: str = param(
        title=_("Musterstil"),
        default="other",
        # „other" steht für ein Muster, das Solidon nicht selbst zeichnet — so
        # heißt es in der Erkennung (``perceive.patterns.STYLES``), und so
        # steht es vorbelegt da, bis jemand einen der acht Stile wählt.
        choices=(
            "other",
            "rib",
            "wave",
            "knurl_straight",
            "knurl_diamond",
            "hexagon",
            "dimple",
            "voronoi",
            "noise",
        ),
        placement="advanced",
        doc=_(
            "Nur an einem Muster: der Stil, mit dem es neu gezeichnet wird. Ein fremdes "
            "Muster bekommt so einen der acht Stile von Solidon, auf derselben Fläche und "
            "mit der gemessenen Teilung."
        ),
    )


@register_op(
    name="resize_feature",
    # Kein ``result_kind="mesh"`` mehr (22.09.2026): Zapfen, Kuppe und Kegel
    # ändern sich am exakten Körper exakt (``_exact_resize_by_faces``), Ring,
    # Gewinde und Rundung taten es schon. Ein Muster gibt es an einem exakten
    # Körper nicht — es entsteht als Netz (``apply_texture``). 7 seit dem
    # 23.09.2026: Ein Muster kann den Stil wechseln (``style``), sein Stopfen
    # um einen Zylinder füllt die Tasche bis zum Boden, und zwei Zweige haben
    # am selben Tag unabhängig auf 6 erhöht. 8: Der Stopfen wird an den
    # Facettengrenzen konform geteilt und endet an den Stirnflächen des Stifts.
    cache_version="8",
    title=_("Merkmal ändern"),
    category="holes",
    params=ResizeFeatureParams,
    consumes=1,
    produces=1,
    # **Nicht ``hole``** — dafür gibt es ``resize_hole`` mit eigenem Weg durch
    # den exakten Kern und einer Materialkompensation, die für ein Loch gilt und
    # für einen Zapfen andersherum liefe. Die beiden überschneiden sich deshalb
    # nicht, und ``perceive.actions`` legt sie zu **einer** Zeile zusammen.
    applies_to=["pin", "cone", "sphere", "fillet", "torus", "thread", "pattern"],
    touches_features=True,
    deterministic=False,
    doc=_(
        "Ändert den Durchmesser eines erkannten Merkmals: Zapfen, Senkung, "
        "Verjüngung, Kuppel, Pfanne, Wulst oder Kehle — den Durchmesser und die "
        "Steigung eines Gewindes, den Radius einer Rundung, Teilung, Zellbreite und "
        "Tiefe eines Musters."
    ),
)
def resize_feature(ctx: OpContext) -> OpResult:
    """Den Durchmesser eines erkannten Merkmals ändern — Zapfen, Kegel, Kugel.

    **Warum das nicht** :func:`resize_hole` **mit erweitertem ``applies_to``
    ist.** Die Bohrung hat einen eigenen Weg durch den exakten Kern
    (``edit.resize_bore``) und eine Materialkompensation, die für ein Loch
    gilt und für einen Zapfen genau andersherum liefe: Ein Loch wird beim
    Drucken enger, ein Zapfen dicker. Zwei Operationen, eine Zeile im Panel —
    ``perceive.actions`` legt sie zusammen, und der Kunde sieht *Größe ändern*
    und nicht zwei Einträge, von denen einer immer grau ist.

    Sonst ist es derselbe Motor: an der alten Stelle abtragen, mit dem neuen
    Maß wieder ansetzen.
    """
    params = cast(ResizeFeatureParams, ctx.params)
    source = ctx.inputs[0]
    if _is_a_fillet(source, params.at_feature):
        return _reshape_the_fillet(ctx, source, params.at_feature, params.diameter / 2.0)
    feature = _movable_feature(source, params.at_feature, "resize_feature")
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])
    previous = float(feature.params.get("diameter", 0.0))
    _reject_oversized("diameter", params.diameter, source.mesh)
    if feature.kind == "torus":
        return _resize_torus(ctx, source, feature, centre, params.diameter, params.tube_diameter)
    if feature.kind == "thread":
        return _resize_thread(ctx, source, feature, params.diameter, params.pitch)
    if feature.kind == "pattern":
        return _resize_pattern(
            ctx,
            source,
            feature,
            params.pitch,
            params.cell_width,
            params.cell_depth,
            style=params.style,
        )

    if is_close(params.diameter, previous):
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="resize_feature.unchanged",
                    severity="info",
                    message=_("Das Merkmal hat dieses Maß schon."),
                    feature_ids=(feature.id,),
                )
            ],
        )

    scale = params.diameter / previous if previous > EPS_GEOM else 1.0
    cavity = is_a_cavity(feature)
    if source.kind == "brep" and feature.kind in ("pin", "cone", "sphere"):
        return _exact_resize_by_faces(ctx, source, feature, centre, params.diameter, scale)
    stands_alone = _stands_alone(as_mesh_data(source.mesh), feature, source.features)
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    closed = _closed_at(
        as_mesh_data(source.mesh),
        feature,
        centre,
        cavity,
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        alone=stands_alone,
    )
    ctx.progress(0.6, str(_("Das Merkmal wird mit dem neuen Maß gesetzt …")))
    placed = boolean(
        "difference" if cavity else "union",
        [
            closed.mesh,
            _placing_tool(
                ctx,
                as_mesh_data(source.mesh),
                source,
                feature,
                centre,
                cavity,
                scale=scale,
                alone=stands_alone,
            ),
        ],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    changed = dataclasses.replace(
        feature,
        params={**feature.params, "diameter": params.diameter},
        provenance="generated",
        face_indices=(),
        surface_patches=(),
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**_without_old_triangles(source.features), feature.id: changed},
            )
        ],
        findings=[
            *closed.findings,
            *placed.findings,
            *_widening_findings(source, feature, params.diameter),
            # Ein größerer Durchmesser an derselben Mitte läuft über die Kante,
            # wo der alte noch Material hatte.
            *_edge_findings(closed.mesh, [changed]),
        ],
        solver=placed.solver,
    )


@op_params
class ResizeHoleParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        placement="front",
        doc=_(
            "Neuer fertiger Durchmesser der erkannten Bohrung. Beim Anklicken steht "
            "hier zuerst ihr gemessenes Maß."
        ),
    )
    at_feature: str = param(
        title=_("Bohrung"),
        default="",
        kind="feature",
        required=True,
        # Vorn, nicht hinter der Klappe: Ein Pflichtfeld ohne „— keines —"
        # steht vorausgewählt auf der ersten Bohrung, und zugeklappt wäre das
        # eine stille Wahl (Regel 21) — über das Menü geöffnet sah der Kunde
        # nur den Durchmesser.
        placement="front",
        doc=_(
            "Die erkannte Bohrung, deren Durchmesser geändert wird. Ein Klick auf "
            "die Bohrung trägt sie ein."
        ),
    )
    entrance_mode: Literal["keep", "follow"] = param(
        title=_("Änderungsumfang"),
        default="keep",
        choices=("keep", "follow"),
        placement="front",
        doc=_(
            "Nur den Bohrungsdurchmesser ändern oder den eindeutigen Einlauf mitnehmen. "
            "Beim Mitnehmen bleiben Einführbreite, Senkungswinkel und Stufentiefen erhalten."
        ),
    )
    x: float | None = param(
        title=_("X"),
        default=None,
        optional=True,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte der Bohrung. Beim Anklicken steht hier ihre heutige; "
            "leer heißt, sie bleibt, wo sie ist."
        ),
    )
    y: float | None = param(
        title=_("Y"),
        default=None,
        optional=True,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte der Bohrung. Beim Anklicken steht hier ihre heutige; "
            "leer heißt, sie bleibt, wo sie ist."
        ),
    )
    z: float | None = param(
        title=_("Z"),
        default=None,
        optional=True,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte der Bohrung. Beim Anklicken steht hier ihre heutige; "
            "leer heißt, sie bleibt, wo sie ist."
        ),
    )
    # **Die Tiefe ist ein Feld** (Sollliste der Durchsicht vor 0.5.0): An einer
    # erkannten Bohrung stand sie bis zum 23.09.2026 nur als Auskunft
    # („Gemessene Tiefe"), die Website zeigte sie als Feld. Leer heißt wie
    # bei der Stelle „lass sie" — über Chat und Kommandozeile nennt sie
    # niemand, der nur den Durchmesser meint.
    depth: float | None = param(
        title=_("Tiefe"),
        default=None,
        optional=True,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Wie tief die Bohrung von ihrer Mündung aus ins Material reicht. Null bohrt "
            "ganz durch; leer lässt die Tiefe, wie sie ist."
        ),
    )
    open_side: str = param(
        title=_("Offene Seite"),
        default="ask_side",
        choices=("ask_side", *(key for pair in SIDE_KEYS for key in pair)),
        placement="advanced",
        doc=_(
            "Welche Seite offen bleibt, wenn aus einer Durchgangsbohrung ein Sackloch "
            "wird. „Nachfragen“ entscheidet der Nutzer, sobald der Fall auftritt."
        ),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=False,
        placement="advanced",
        doc=_(
            "Vergrößert das gewählte Fertigmaß um den Wert aus dem Materialprofil. "
            "Aus bleibt das gemessene Maß unverändert."
        ),
    )


#: Wie weit eine eingetragene Tiefe von der gemessenen abweichen darf und
#: dieselbe bleibt: eine halbe Anzeigestelle. Das Feld zeigt die gemessene
#: Tiefe gerundet, und wer sie unverändert übernimmt, meint keinen Neuschnitt
#: um Tausendstel.
_SAME_DEPTH: Final = EPS_DISPLAY / 2.0

#: Wo die Strahlen der Tiefenmessung den Bohrungsquerschnitt treffen: die Achse
#: und vier Punkte auf halbem Radius. Einer allein läge an einer Platte, deren
#: Mitte auf der Bohrachse liegt, genau auf der Diagonale zweier Dreiecke.
_DEPTH_RAYS: Final = ((0.0, 0.0), (0.5, 0.0), (0.0, 0.5), (-0.5, 0.0), (0.0, -0.5))


@dataclasses.dataclass(frozen=True, slots=True)
class _DepthWish:
    """Was der Kunde an der Tiefe will, bevor die alte Bohrung zugeht."""

    wanted: float
    """Die eingetragene Tiefe; null heißt „ganz durch"."""
    mouth: Vec3
    """Wo die Bohrung beginnt: die Mitte ihres offenen Rands."""
    outward: Vec3
    """Aus dem Material heraus, entlang der Achse."""
    length: float
    """Die heutige Länge der Bohrung."""
    was_through: bool
    answered: dict[str, str]


@dataclasses.dataclass(frozen=True, slots=True)
class _DepthPlan:
    """Die neue Bohrung, gemessen am verschlossenen Körper."""

    centre: Vec3
    depth: float
    through: bool
    findings: tuple[Finding, ...]
    floor_shift: Vec3
    """Wie weit der alte Boden wandert — null, wo es keinen alten oder neuen gibt."""


def bore_depth_is_unchanged(feature: Feature, depth: float | None) -> bool:
    """Ob die Eingabe dieselbe Bohrtiefe meint, einschließlich „ganz durch“ und Anzeigerundung."""
    if depth is None:
        return True
    wanted = float(depth)
    length = _bore_number(feature, "depth")
    if feature.params.get("through", False):
        return wanted <= EPS_GEOM or wanted >= length - _SAME_DEPTH
    return wanted > EPS_GEOM and abs(wanted - length) <= _SAME_DEPTH


def _depth_wish(
    ctx: OpContext, source: SceneObject, feature: Feature, params: ResizeHoleParams
) -> _DepthWish | Finding | None:
    """Liest die gewünschte Tiefe — ``None`` heißt: sie bleibt.

    Eine Durchgangsbohrung, die durch bleiben soll, gibt die Auskunft
    ``bore.already_through`` zurück statt eines Wunschs. Wird aus ihr ein
    Sackloch, fragt der Kern, welche Seite offen bleibt (Regel 21): Beide
    Enden sind Mündungen, und welche gemeint ist, sagt die Geometrie nicht.
    """
    if params.depth is None:
        return None
    wanted = float(params.depth)
    unit = np.asarray(_feature_direction(feature), dtype=np.float64)
    centre = np.asarray(_bore_vector(feature, "centre"), dtype=np.float64)
    length = _bore_number(feature, "depth")
    through = bool(feature.params.get("through", False))
    answered: dict[str, str] = {}
    if bore_depth_is_unchanged(feature, params.depth):
        if through:
            return Finding(
                code="bore.already_through",
                severity="info",
                message=_("Die Bohrung geht bereits ganz durch."),
                feature_ids=(feature.id,),
            )
        return None
    if through:
        outward = _kept_open(ctx, params, unit, answered)
    else:
        air = _toward_the_air(as_mesh_data(source.mesh), feature)
        if air is None:
            raise ValidationError(
                field="depth",
                detail=_(
                    "An dieser Bohrung lässt sich nicht bestimmen, welche Seite offen ist. "
                    "Lassen Sie die Tiefe leer, oder ändern Sie sie an dem Schritt, der "
                    "die Bohrung angelegt hat."
                ),
                value=wanted,
                constraint="open_side_unknown",
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        outward = air
    mouth = centre + outward * (length / 2.0)
    return _DepthWish(
        wanted=wanted,
        mouth=(float(mouth[0]), float(mouth[1]), float(mouth[2])),
        outward=(float(outward[0]), float(outward[1]), float(outward[2])),
        length=length,
        was_through=through,
        answered=answered,
    )


def _kept_open(
    ctx: OpContext, params: ResizeHoleParams, unit: NDArray[np.float64], answered: dict[str, str]
) -> NDArray[np.float64]:
    """Welches Ende einer Durchgangsbohrung offen bleibt — erfragt oder genannt."""
    ends = (unit, -unit)
    sides = [side_of((float(end[0]), float(end[1]), float(end[2]))) for end in ends]
    choice = params.open_side
    if choice == "ask_side":
        names = [str(name) for _key, name in sides]
        answer = ctx.ask(
            str(_("Aus der Durchgangsbohrung wird ein Sackloch. Welche Seite soll offen bleiben?")),
            names,
        )
        if answer not in names:
            raise InternalError(detail="the open side question returned an unknown choice")
        choice = sides[names.index(answer)][0]
        answered["open_side"] = choice
    for end, (key, _name) in zip(ends, sides, strict=True):
        if key == choice:
            return end
    raise ValidationError(
        field="open_side",
        detail=_(
            "Diese Bohrung tritt an dieser Seite nicht aus. Wählen Sie eine der beiden "
            "Seiten, an denen sie austritt, oder „Nachfragen“."
        ),
        value=choice,
        constraint="not_an_end",
        values={"ends": ", ".join(str(name) for _key, name in sides)},
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def _exits_below(
    mesh: MeshData, mouth: NDArray[np.float64], inward: NDArray[np.float64], radius: float
) -> list[NDArray[np.float64]]:
    """Je Messstrahl die Abstände ab der Mündung, an denen er Material verlässt.

    Gemessen am **verschlossenen** Körper: Die alte Bohrung ist zu, und was
    der Strahl dann sieht, ist das Material, in das die neue schneidet. Ein
    Austritt ist ein Treffer, dessen Flächennormale mit dem Strahl läuft.
    """
    from app.core.geom.mesh import ray_hits
    from app.core.sketch.planes import frame_of

    triangles = np.asarray(mesh.raw.triangles, dtype=np.float64)
    normals = np.asarray(mesh.raw.face_normals, dtype=np.float64)
    frame = frame_of((float(inward[0]), float(inward[1]), float(inward[2])), (0.0, 0.0, 0.0))
    across = np.asarray(frame.x_axis, dtype=np.float64), np.asarray(frame.y_axis, dtype=np.float64)
    back = MAX_FACET_SAG
    rays = []
    for u, v in _DEPTH_RAYS:
        start = mouth - inward * back + (across[0] * u + across[1] * v) * radius
        distances, hit = ray_hits(triangles, start, inward)
        leaving = normals[hit] @ inward > 0.0
        exits = np.sort(distances[leaving]) - back
        exits = exits[exits > EPS_GEOM]
        if len(exits):
            rays.append(exits)
    return rays


def _depth_plan(closed: MeshData, wish: _DepthWish, profile: Profile, radius: float) -> _DepthPlan:
    """Die neue Bohrung am verschlossenen Körper: Mitte, Länge, durch oder nicht.

    Die Befunde sagen, was die Tiefe dem Material antut: Sie reicht durch das
    ganze Teil (``bore.now_through`` — Auskunft, wo null bestellt war, sonst
    eine Warnung mit der größten Tiefe, die einen Boden lässt), sie tritt auf
    der anderen Seite aus, ohne ganz durchzugehen (``bore.breaks_out``), oder
    sie lässt unter dem Boden weniger Material, als das Profil verlangt
    (``bore.floor_thin``). Die Nachbarwand fragt der Aufrufer mit dem
    Werkzeug.
    """
    mouth = np.asarray(wish.mouth, dtype=np.float64)
    outward = np.asarray(wish.outward, dtype=np.float64)
    rays = _exits_below(closed, mouth, -outward, radius)
    minimum = profile.minimum_wall_thickness
    wanted = wish.wanted
    furthest = max((float(ray[-1]) for ray in rays), default=None)
    nearest_far_side = min((float(ray[-1]) for ray in rays), default=None)
    findings: list[Finding] = []
    if wanted <= EPS_GEOM or (furthest is not None and wanted >= furthest - _SAME_DEPTH):
        exact_wish = wanted <= EPS_GEOM or (
            nearest_far_side is not None and abs(wanted - nearest_far_side) <= EPS_DISPLAY
        )
        if not wish.was_through:
            largest = max(0.0, (nearest_far_side or 0.0) - minimum)
            findings.append(
                Finding(
                    code="bore.now_through",
                    severity="info" if exact_wish else "warning",
                    message=(
                        _("Die Bohrung geht jetzt ganz durch.")
                        if exact_wish
                        else _(
                            "Diese Tiefe reicht durch das ganze Teil, die Bohrung geht "
                            "jetzt durch. Ein Sackloch ist hier höchstens {largest} tief.",
                            largest=format_length(largest),
                        )
                    ),
                    values={"largest": round(largest, 3)},
                    suggestions=(CORRECT_INPUT,) if not exact_wish else (),
                )
            )
        centre = mouth - outward * (wish.length / 2.0)
        return _DepthPlan(
            centre=(float(centre[0]), float(centre[1]), float(centre[2])),
            depth=furthest if furthest is not None else wish.length,
            through=True,
            findings=tuple(findings),
            floor_shift=(0.0, 0.0, 0.0),
        )
    first_exit = min((float(ray[0]) for ray in rays), default=None)
    if first_exit is not None and wanted >= first_exit - EPS_GEOM:
        findings.append(
            Finding(
                code="bore.breaks_out",
                severity="warning",
                message=_(
                    "Bei dieser Tiefe tritt die Bohrung auf der anderen Seite des Materials "
                    "aus. Wählen Sie eine geringere Tiefe, wenn sie geschlossen bleiben soll."
                ),
                values={"largest": round(max(0.0, first_exit - minimum), 3)},
                suggestions=(CORRECT_INPUT,),
            )
        )
    else:
        beyond = [float(ray[ray > wanted][0]) - wanted for ray in rays if np.any(ray > wanted)]
        thickness = min(beyond, default=None)
        if thickness is not None and thickness < minimum - EPS_GEOM:
            findings.append(
                Finding(
                    code="bore.floor_thin",
                    severity="warning",
                    message=_(
                        "Unter dem Boden der Bohrung bleiben nur {thickness:.2f} mm Material. "
                        "Das Materialprofil verlangt mindestens {minimum:.2f} mm. Wählen Sie "
                        "eine geringere Tiefe.",
                        thickness=thickness,
                        minimum=minimum,
                    ),
                    values={"thickness": round(thickness, 3), "minimum": minimum},
                    suggestions=(CORRECT_INPUT,),
                )
            )
    centre = mouth - outward * (wanted / 2.0)
    shift = np.zeros(3) if wish.was_through else -outward * (wanted - wish.length)
    return _DepthPlan(
        centre=(float(centre[0]), float(centre[1]), float(centre[2])),
        depth=wanted,
        through=False,
        findings=tuple(findings),
        floor_shift=(float(shift[0]), float(shift[1]), float(shift[2])),
    )


def _with_new_depth(feature: Feature, plan: _DepthPlan) -> Feature:
    """Das Merkmal, nach dem nach dem Neuschnitt gesucht wird: neue Mitte, Länge, Art."""
    return dataclasses.replace(
        feature,
        params={
            **feature.params,
            "centre": plan.centre,
            "depth": plan.depth,
            "through": plan.through,
        },
    )


def _bore_tool_mesh(centre: Vec3, axis: Vec3, diameter: float, depth: float) -> MeshData:
    """Der Zylinder einer Bohrung als Netz — für die Nachbarprüfung am exakten Körper."""
    body = lathe.cylinder(radius=diameter / 2.0, height=depth, sections=BORE_SECTIONS)
    transform.moved(body, transform.rotation_between([0.0, 0.0, 1.0], list(axis)))
    body.apply_translation(np.asarray(centre, dtype=float))
    return MeshData.of(body)


def _without_opened_twice(neighbours: list[Finding], already: Sequence[Finding]) -> list[Finding]:
    """Ein Austritt in einen Nachbarhohlraum ist der Nachbarbefund, nicht beides.

    ``bore.breaks_out`` sieht nur, dass der Strahl das Material verlässt; ob
    dahinter ein Nachbar liegt, weiß der Nachbarbefund. Steht er da, fällt
    der allgemeinere Satz — die Liste des Aufrufers wird dafür geändert.
    **Ebenso ``bore.over_the_edge``** (25.09.2026): Eine um 30° zur Nachbarin
    gekippte Senkung mündete in deren Mündung, die Kantenprüfung sah dort Luft
    und meldete „ragt seitlich über den Körper hinaus", an beiden Kernen neben
    dem Nachbarbefund.
    """
    if any(entry.code == "bore.neighbour_opened" for entry in neighbours):
        kept = [
            entry
            for entry in already
            if entry.code not in ("bore.breaks_out", "bore.over_the_edge")
        ]
        if isinstance(already, list) and len(kept) != len(already):
            already[:] = kept
    return neighbours


def _deepened_after_resizing(ctx: OpContext, resized: OpResult, feature: Feature) -> OpResult:
    """Erst der Einlauf mit dem neuen Durchmesser, dann die neue Tiefe am Schaft.

    Dieselbe Reihenfolge wie beim Versetzen nach dem Neuschnitt
    (:func:`_moved_after_resizing`): Der Einlauf ändert Schaft und Senkung
    gemeinsam; die Tiefe betrifft danach nur den Schaft, dessen Mündung unter
    der Senkung liegt. Der zweite Schritt ist *Bohrung ändern* selbst, mit dem
    Durchmesser, den der Schaft jetzt hat.
    """
    params = cast(ResizeHoleParams, ctx.params)
    body = resized.outputs[0]
    shaft = body.features.get(feature.id)
    if shaft is None:
        raise GeometryError(
            title=_("Die Tiefe ließ sich nach dem Ändern nicht einstellen."),
            detail=_(
                "Nach dem Neuschnitt des Einlaufs wurde die Bohrung nicht wiedererkannt. "
                "Ändern Sie zuerst den Durchmesser und danach die Tiefe."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    inner = dataclasses.replace(
        ctx,
        inputs=[body],
        params=dataclasses.replace(
            cast(Any, params),
            diameter=_bore_number(shaft, "diameter"),
            compensate=False,
            entrance_mode="keep",
            x=None,
            y=None,
            z=None,
        ),
        progress=lambda fraction, text: ctx.progress(0.5 + fraction / 2.0, text),
    )
    deepened = resize_hole(inner)
    return OpResult(
        outputs=deepened.outputs,
        solver=deepest((resized.solver, deepened.solver)),
        findings=[*resized.findings, *deepened.findings],
        answered={**resized.answered, **deepened.answered},
        feature_continuations=_continued_through(ctx.inputs[0], resized, deepened),
    )


#: Der exakte Kern hat gerechnet, und heraus kam ein Körper, der nicht mehr
#: geschlossen ist. Für den Kunden ist das kein Ergebnis — im Objektbaum stünde
#: ein Körper, der sich nicht drucken lässt, und gesagt hätte es erst der Export.
OPEN_BODY_TITLE: Final = _("Die geänderte Bohrung ließ den Körper offen.")
OPEN_BODY_DETAIL: Final = _(
    "Der exakte Kern konnte die neue Wand nicht mit dem Körper schließen. "
    "Der Körper bleibt, wie er war."
)


@register_op(
    name="resize_hole",
    # 7: ``follow`` mit Stelle bewegt um die Differenz zur alten Mitte und
    # trägt die Befunde des neuen Orts (22.09.2026).
    # 8: eine schräge Bohrung schließt beim Versetzen an ihren Randebenen.
    # 9: die Tiefe ist ein Wert (``depth``, ``open_side``, 23.09.2026).
    cache_version="9",
    title=_("Bohrung ändern"),
    category="holes",
    params=ResizeHoleParams,
    consumes=1,
    produces=1,
    # **Auch am Langloch** (RM-156): Dort ist der Durchmesser seine Breite, und
    # die Länge folgt daraus — der Weg bleibt, die Enden wachsen mit. Die Zeile
    # in ``NOT_APPLICABLE_HERE``, die das als „noch nicht gebaut" auswies, ist
    # mit ihrer Lücke gefallen.
    applies_to=["hole", "slot"],
    touches_features=True,
    deterministic=False,
    doc=_(
        "Ändert Durchmesser und Tiefe einer erkannten Bohrung — an einem Langloch "
        "seine Breite; der Weg der Schraube bleibt, die Enden wachsen mit."
    ),
)
def resize_hole(ctx: OpContext) -> OpResult:
    """Der gemeinsame Kundenweg für STL-Netze und exakte STEP-Körper."""
    params = cast(ResizeHoleParams, ctx.params)
    source = ctx.inputs[0]
    feature = _chosen_bore(source, params.at_feature, op="resize_hole")
    # **Auch das Ändern führt eine Stelle** (Robert, 10.09.2026: „auch beim
    # ändern einer bohrung"). Damit bekommt *Bohrung ändern* dieselbe
    # Flächenplatzierung wie *Bohrung setzen*: Die Maße zu Kanten und Mitten
    # stehen in der Szene und lassen sich dort ändern. Drei Nullen heißen „lass
    # sie, wo sie ist" — dieselbe Lesart wie bei *Zum Langloch ziehen*, und aus
    # demselben Grund: Über Chat und Kommandozeile nennt niemand eine Stelle.
    measured_centre = _bore_vector(feature, "centre")
    # **„Nicht gesagt" steht als ``None`` da und nicht als Null** (RM-154).
    # Hier stand ``not all(is_zero(value) for value in placed)``, und damit ließ
    # sich das Loch in jede Stelle versetzen außer in den Ursprung — an einer
    # mittig gelegten Platte also ausgerechnet in die Mitte des Teils.
    centre = _named_place(params.x, params.y, params.z, measured_centre) or measured_centre
    named_a_place = centre is not measured_centre
    # **Versetzt ist erst, wer wirklich woanders landet.** Wer die heutige
    # Mitte noch einmal einträgt, nennt eine Stelle und wechselt keine; das
    # Loch dafür zu schließen und neu zu bohren wäre Arbeit ohne Wirkung.
    moved_hole = named_a_place and not all(
        is_close(a, b) for a, b in zip(centre, measured_centre, strict=True)
    )
    axis = _bore_vector(feature, "axis")
    previous = _bore_number(feature, "diameter")
    depth = _bore_number(feature, "depth")
    _reject_oversized("diameter", params.diameter, source.mesh)
    through = bool(feature.params.get("through", False))
    cut = bore_diameter(params.diameter, ctx.profile, params.compensate)
    wish = _depth_wish(ctx, source, feature, params)
    same_diameter = bore_is_unchanged(feature, params.diameter, ctx.profile, params.compensate)
    if isinstance(wish, Finding):
        # Eine Durchgangsbohrung, die durch bleiben soll: Die Tiefe ändert nichts.
        if same_diameter and not moved_hole:
            return OpResult(outputs=[source], findings=[wish])
        wish = None
    if same_diameter and not moved_hole and wish is None:
        return OpResult(
            outputs=[source], findings=[_unchanged_bore(cut, with_depth=params.depth is not None)]
        )
    if params.entrance_mode == "follow" and not (same_diameter and not moved_hole):
        entrance = bore_entrance(source.mesh, feature, source.features)
        if entrance is not None:
            resized = _resize_bore_entrance(ctx, feature, entrance, cut)
            if moved_hole:
                resized = _moved_after_resizing(
                    ctx, resized, feature, entrance, centre, measured_centre
                )
            if wish is None:
                return resized
            return _deepened_after_resizing(ctx, resized, feature)
    # **Am Langloch ist der Durchmesser die Breite, und die Länge folgt daraus**
    # (RM-156). Gerechnet wird über den **Weg** und nicht über die Länge: Er ist
    # der Grund, aus dem es Langlöcher gibt, und wer ihn beim Verbreitern
    # verlöre, bekäme ein anderes Bauteil. Ø 6 auf 20 wird damit zu Ø 8 auf 22.
    slot_travel_now = _bore_number(feature, "travel") if feature.kind == "slot" else 0.0
    slot_length_now = slot_travel_now + cut if feature.kind == "slot" else 0.0
    # **Gesucht wird danach, wo das Merkmal jetzt sitzt.** Beide Kerne ordnen
    # die neue Geometrie über Maß *und* Lage wieder ihrem Namen zu; mit der
    # alten Mitte findet keiner von beiden das versetzte Loch — der Netz-Weg
    # meldete es als verloren, der exakte warf einen Programmfehler.
    looked_for = (
        dataclasses.replace(feature, params={**feature.params, "centre": centre})
        if moved_hole
        else feature
    )
    # **Eine neue Tiefe ist ein Neuschnitt an derselben Mündung** (23.09.2026):
    # dieselbe Paarung wie beim Versetzen — alte Bohrung zu, neue aus vollem
    # Material auf —, nur wandert die Mitte entlang der Achse, und die Länge
    # ist die neue. Tiefer schneidet damit nach, flacher füllt vom Grund her
    # auf, und beide Kerne teilen einen Weg, der für die Stelle längst trägt.
    redrilled = moved_hole or wish is not None
    depth_findings: list[Finding] = []
    answered: dict[str, Any] = dict(wish.answered) if wish is not None else {}
    floor_shift: Vec3 = (0.0, 0.0, 0.0)

    if source.kind == "brep":
        from app.core.brep import edit
        from app.core.brep.features import features_of
        from app.core.brep.kernel import Solid

        if not isinstance(source.mesh, Solid):
            raise InternalError(
                detail="a scene object marked as brep does not carry a Solid",
                values={"object": source.id},
            )
        # **Wer versetzt, schließt die alte Stelle** — dieselbe Paarung wie am
        # Netz (`_closed_at` weiter unten), nur exakt gerechnet. Bis zum
        # 10.09.2026 stand hier eine Absage; der Kern konnte kein Loch füllen.
        #
        # **Und an der neuen Stelle wird gebohrt, nicht geändert.** Dort ist
        # nichts, was ein neues Maß bekommen könnte; `resize_bore` ließe ein
        # unverändertes Maß ohnehin liegen und gäbe den gefüllten Körper zurück.
        filled = (
            _exact_cavity_filled(source.mesh, feature)
            if redrilled or feature.kind == "slot"
            else None
        )
        if wish is not None and filled is not None:
            plan = _depth_plan(as_mesh_data(filled), wish, ctx.profile, cut / 2.0)
            centre, depth, through = plan.centre, plan.depth, plan.through
            depth_findings = list(plan.findings)
            floor_shift = plan.floor_shift
            looked_for = _with_new_depth(looked_for, plan)
        if feature.kind == "slot" and filled is not None:
            # **Ein Langloch wird gefüllt und neu geschnitten, in beide
            # Richtungen** (RM-156). Beim Verbreitern deckte der neue Umriss den
            # alten zwar mit ab; beim Verschmälern bliebe ohne das Füllen die
            # alte Breite stehen, und das Maß im Objektbaum wäre eine Behauptung
            # über Material, das nicht mehr da ist. Ein Weg für beide Fälle ist
            # billiger als zwei, die sich in einem unterscheiden.
            angle_now = slot_angle_of(feature, axis)
            solid = edit.slot_bore(
                filled,
                position=centre,
                direction=axis,
                diameter=cut,
                depth=_through_bore_depth(source.mesh, centre, axis) if through else depth,
                length=slot_length_now,
                angle_deg=angle_now,
                overlap=0.0,
            )
        elif filled is not None:
            solid = edit.cut_bore(
                filled,
                position=centre,
                direction=axis,
                diameter=cut,
                depth=_through_bore_depth(source.mesh, centre, axis) if through else depth,
            )
        else:
            solid = edit.resize_bore(
                source.mesh,
                position=centre,
                direction=axis,
                previous_diameter=previous,
                diameter=cut,
                depth=depth,
            )
        if solid.volume <= EPS_GEOM or solid.face_count == 0:
            raise GeometryError(
                title=NOTHING_LEFT_TITLE,
                detail=NOTHING_LEFT_DETAIL,
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        # **Ob der Körper noch geschlossen ist, gehört zum Erfolg dazu.** An der
        # Teppichklammer (Datei 19 der Durchsicht vom 05.09.2026) kam ein
        # Körper mit offener Tessellation zurück, und weder ``IsDone`` der
        # Booleschen Operation noch die zwei Prüfungen darüber sagten ein Wort:
        # Volumen war da, Flächen waren da. Der Kunde sah es erst im Export.
        # Die Ursache — ein Schneidzylinder neben der Achse — ist in
        # ``brep.features`` behoben; die Frage bleibt, weil sie zum Vertrag
        # gehört und nicht zu einer Ursache.
        if not solid.is_closed:
            raise GeometryError(
                title=OPEN_BODY_TITLE,
                detail=OPEN_BODY_DETAIL,
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        findings: list[Finding] = list(depth_findings)
        if not redrilled:
            # **Beim Versetzen sagt das Volumen nichts.** Eine Bohrung, die
            # ihre Stelle wechselt und ihr Maß behält, lässt genau so viel
            # Material stehen wie vorher — `without_effect` las das als „hat
            # nichts hinzugefügt". Dass hier etwas geschehen ist, steht schon
            # fest: `moved_hole` ist erst wahr, wenn die Mitte wirklich wandert.
            change: BooleanKind = "difference" if cut > previous else "union"
            nothing = without_effect(source.mesh, solid, change, ctx.profile)
            if nothing is not None:
                findings.append(nothing)
        from app.core.sketch.planes import frame_of

        findings.extend(
            edge_findings(
                source.mesh,
                position=centre,
                frame=frame_of(axis, centre),
                diameter=cut,
                travel=slot_travel_now,
                angle_deg=slot_angle_of(feature, axis) if feature.kind == "slot" else 0.0,
                body=as_mesh_data(source.mesh),
                reach=depth / 2.0,
            )
        )
        findings.extend(compensation_findings(params.diameter, cut, params.compensate))
        # Nur wo der Durchmesser sich ändert: Eine neue Tiefe lässt die Senkung,
        # wie sie war, und ein Satz über sie wäre ohne Anlass.
        if not same_diameter:
            findings.extend(_widening_findings(source, feature, params.diameter))
        # **Die Nachbarwand fragt auch der exakte Kern** — bis zum 23.09.2026
        # nur das Netz; eine Vergrößerung an einem STEP-Teil riss eine
        # Trennwand auf, und der Bericht schwieg.
        if cut > previous or redrilled:
            findings.extend(
                _without_opened_twice(
                    _neighbour_bore_findings(
                        source,
                        feature,
                        _bore_tool_mesh(
                            centre,
                            axis,
                            cut,
                            _through_bore_depth(source.mesh, centre, axis) if through else depth,
                        ),
                        ctx,
                        moved=moved_hole,
                        deeper=wish is not None and not moved_hole,
                    ),
                    findings,
                )
            )
        exact_features, recognised, continued = _preserved_exact_features(
            source.features,
            features_of(solid, cancelled=ctx.cancelled),
            looked_for,
            cut,
            solid,
            original=source.mesh if not moved_hole else None,
            check_cancelled=ctx.cancelled.raise_if_cancelled,
            floor_shift=floor_shift,
        )
        if not recognised:
            findings.append(_bore_no_longer_a_feature(feature, cut))
        return OpResult(
            outputs=[
                dataclasses.replace(
                    source,
                    mesh=solid,
                    kind="brep",
                    features=exact_features,
                )
            ],
            findings=findings,
            answered=answered,
            # Der Beleg für die bewusst geänderte Bohrung und ihren Boden reist
            # mit dem Ergebnis: Die Auswertung darf ihn weder aus dem Namen der
            # Operation noch aus gleichen Kennungen erraten (§21.2).
            feature_continuations=(
                tuple(
                    FeatureContinuation(FeatureRef(source.id, old_id), new_id)
                    for old_id, new_id in continued
                ),
            ),
        )

    body = as_mesh_data(source.mesh)
    original_body = body
    # **Die Tiefe wird am Original gemessen, nicht am gestopften Körper.**
    # `_mesh_bore_depth` liest die Dreiecke, die `feature.face_indices`
    # benennt, und die gelten für das Netz, in dem das Merkmal erkannt wurde.
    # Nach einer Booleschen Operation zeigen sie irgendwohin — an der Platte
    # von 60 x 40 x 10 fällt das nicht auf (gemessen 10.09.2026: 10,0 vor und
    # 10,0 nach dem Verschließen, am Sackloch 6,0 und 6,0), weil der Fallback
    # denselben Wert trägt. Auffallen muss es aber auch nicht: Die Frage ist
    # an dieser Stelle beantwortbar, und danach ist sie es nicht mehr.
    exact_depth = _mesh_bore_depth(body, feature, axis, depth)
    closed_first: list[Finding] = []
    closing_solver: SolverInfo | None = None
    # **Ein Langloch geht immer zu, bevor es neu geschnitten wird** (RM-156) —
    # auch ohne Versatz. Beim Verbreitern deckte der neue Umriss den alten mit
    # ab; beim Verschmälern bliebe die alte Breite stehen, und das Maß im
    # Objektbaum wäre eine Behauptung über Material, das nicht mehr da ist.
    if redrilled or feature.kind == "slot":
        # Dieselbe Paarung wie beim Versetzen: alte Stelle zu, neue auf. Ohne
        # sie bliebe die Bohrung stehen und die geänderte entstünde daneben.
        closing = _closed_at(
            body,
            feature,
            measured_centre,
            True,
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        body = closing.mesh
        closed_first = list(closing.findings)
        closing_solver = closing.solver
        if wish is not None:
            plan = _depth_plan(body, wish, ctx.profile, cut / 2.0)
            centre, exact_depth, through = plan.centre, plan.depth, plan.through
            depth_findings = list(plan.findings)
            floor_shift = plan.floor_shift
            looked_for = _with_new_depth(looked_for, plan)
    if feature.kind == "slot":
        # **Das Langloch wird neu geschnitten, mit der neuen Breite und der
        # Länge, die aus seinem Weg folgt** (RM-156). Die Zugabe entfällt: Sie
        # hält den Werkzeugkörper von der alten Bohrungswand fern, und die ist
        # eben zugegangen — mit ihr wüchse die Breite bei jedem Zug.
        result = slot_bore(
            body,
            position=centre,
            direction=axis,
            diameter=cut,
            depth=exact_depth,
            through=through,
            length=slot_length_now,
            angle_deg=slot_angle_of(feature, axis),
            profile=ctx.profile,
            quality=ctx.quality,
            seed=ctx.seed,
            overlap=0.0,
        )
    elif redrilled:
        # **An der neuen Stelle wird gebohrt, nicht geändert.** Die alte ist
        # eben zugegangen; dort, wo die Bohrung hinsoll, ist volles Material.
        # `resize_bore` verglich stattdessen die zwei Durchmesser, fand sie
        # gleich und gab den Körper unverändert zurück — gemessen am
        # 10.09.2026: Loch weiterhin bei (-20 | -10), Volumen unverändert,
        # dazu der Satz „Die Bohrung hat bereits diesen Durchmesser".
        #
        # Der Umkreis ist bereits das gemessene Konturmaß; eine zusätzliche
        # Vieleckzugabe würde es bei jedem Versetzen weiter vergrößern.
        # ``compensate`` steht dabei auf ``False`` — die Materialtoleranz ist
        # in ``cut`` schon drin, ein zweites Mal wäre sie zweimal drauf.
        result = drill(
            body,
            position=centre,
            axis="z",
            normal=axis,
            diameter=cut,
            depth=0.0 if through else exact_depth,
            anchor="centre",
            profile=ctx.profile,
            compensate=False,
            quality=ctx.quality,
            seed=ctx.seed,
        )
    else:
        from app.core.perceive.relations import cavity_chain_at

        end_planes = _bore_end_planes(original_body, feature, source.features, grows=True)
        rebuilt = cut < previous and bool(end_planes)
        if rebuilt:
            # Ein Ring trifft am quantisierten Sacklochboden fast koplanare
            # Dreiecke und erzeugt dort numerische Haut. Der vorhandene
            # Abschnittsweg stellt zunächst die übrigen Flächen wieder her;
            # anschließend bekommt die neue Bohrung ihre eigene saubere Wand.
            chain = cavity_chain_at(feature, source.features, original_body) or (feature,)
            section_closing = _section_closed(
                original_body,
                chain,
                feature,
                quality=ctx.quality,
                seed=ctx.seed,
                cancelled=ctx.cancelled,
                extend_inner=False,
            )
            if section_closing is None:
                raise bore_geometry_error(feature.id)
            body = section_closing.mesh
            closed_first = list(section_closing.findings)
            closing_solver = section_closing.solver
        result = resize_bore(
            body,
            position=centre,
            direction=axis,
            previous_diameter=0.0 if rebuilt else previous,
            diameter=params.diameter,
            depth=exact_depth,
            through=through,
            profile=ctx.profile,
            compensate=params.compensate,
            quality=ctx.quality,
            seed=ctx.seed,
            end_planes=end_planes,
        )
    if result.solver is None:
        return OpResult(outputs=[source], findings=result.findings, answered=answered)
    # **Und die Toleranz wird auch beim Versetzen gemeldet.** `drill` erzeugt
    # den Befund nur bei `compensate=True`, und der Aufruf oben setzt `False`,
    # weil `cut` sie schon trägt — ohne diese Zeile verschwände die Auskunft
    # „Die Bohrung wurde um die Materialtoleranz vergrößert" still, sobald das
    # Loch die Stelle wechselt (Fund des Reviews, 11.09.2026).
    moved_findings = (
        compensation_findings(params.diameter, cut, params.compensate) if redrilled else []
    )
    expected_diameter = cut if redrilled else result.diameter
    detected = _detect_resized_bores(
        result.mesh,
        {looked_for.id: _expected_bore(looked_for, expected_diameter)},
        check_cancelled=ctx.cancelled.raise_if_cancelled,
    )
    resized_feature = _recognised_resized_feature(
        result.mesh,
        looked_for,
        expected_diameter,
        original=original_body if not redrilled and feature.kind == "hole" else None,
        known=detected,
        check_cancelled=ctx.cancelled.raise_if_cancelled,
    )
    if resized_feature is not None and result.solver.strategy in ("direct", "welded"):
        resized_feature = _with_nominal_bore(
            result.mesh, resized_feature, looked_for, cut if redrilled else result.diameter
        )
    carried = {
        name: entry
        for name, entry in _without_old_triangles(source.features).items()
        if entry.provenance == "generated" and name != feature.id
    }
    # Findet sich die geänderte Bohrung nicht wieder, bleibt der Körper und
    # das Merkmal geht — mit einem Satz darüber. Ihn zu behalten wäre eine
    # Behauptung über etwas, das die Erkennung gerade nicht bestätigt.
    features = (
        {**carried, feature.id: resized_feature} if resized_feature is not None else dict(carried)
    )
    if resized_feature is not None and not moved_hole:
        features.update(
            _resized_bore_floor(
                original_body,
                feature,
                source.features,
                result.mesh,
                resized_feature,
                detected,
                check_cancelled=ctx.cancelled.raise_if_cancelled,
                shift=floor_shift,
            )
        )
    findings = [*closed_first, *depth_findings, *result.findings, *moved_findings]
    if not same_diameter:
        findings.extend(_widening_findings(source, feature, params.diameter))
    # Auch eine versetzte Bohrung kann eine Nachbarwand aufreißen — bis zum
    # 22.09.2026 fragte nur die Vergrößerung, und ``drill`` gab sein Werkzeug
    # nicht heraus (Review, A3). Eine tiefere ebenso (23.09.2026).
    if result.cutting_tool is not None and (cut > previous or redrilled):
        findings.extend(
            _without_opened_twice(
                _neighbour_bore_findings(
                    source,
                    feature,
                    result.cutting_tool,
                    ctx,
                    moved=moved_hole,
                    deeper=wish is not None and not moved_hole,
                ),
                findings,
            )
        )
    if resized_feature is None:
        findings.append(_bore_no_longer_a_feature(feature, result.diameter))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features=features)],
        solver=deepest([closing_solver, result.solver]),
        findings=findings,
        answered=answered,
    )


@op_params
class SlotHoleParams(BaseParams):
    slot_length: float = param(
        title=_("Länge des Langlochs"),
        # **Nicht fünf, und der Grund ist ein gefahrener Weg** (Robert,
        # 10.09.2026): Fünf Millimeter sind der Durchmesser einer gewöhnlichen
        # Bohrung, und ein Langloch muss länger sein als seiner. Wer den Dialog
        # öffnete und übernahm, legte damit einen Schritt an, der bei **jeder**
        # Auswertung anhält — auch bei jedem späteren Öffnen des Projekts.
        # Zwanzig Millimeter gehen an jeder Bohrung durch, die kleiner ist als
        # M20; darüber sagt es die Absage, und im Bild sagt es der Griff, bevor
        # jemand loslässt (``app.ui.slot_handle``).
        #
        # Die **richtige** Vorgabe ist der gemessene Durchmesser mal zwei, und
        # die steht am angeklickten Merkmal (``perceive.actions._SHIFTED_BY``).
        # Sie gilt dort, wo eine Bohrung gewählt ist; hier steht die Zahl für
        # den Weg ohne Merkmal — Kommandozeile, Chat, Palette.
        default=20.0,
        unit="mm",
        minimum=0.2,
        placement="front",
        # Die Bedingung steht im Satz, nicht nur in der Absage: Über Chat und
        # Kommandozeile gibt es kein Anklicken und keine Vorbelegung, und wer
        # den Durchmesser der Bohrung nicht mitdenkt, bekommt eine Absage
        # statt eines Langlochs.
        doc=_(
            "Gesamtlänge über beide runden Enden — größer als der Durchmesser "
            "der Bohrung, oder genau der Durchmesser für eine runde Bohrung. "
            "Beim Anklicken steht hier sein Doppeltes: ein Langloch, in dem "
            "sich eine Schraube um einen Durchmesser verschieben lässt."
        ),
    )
    slot_angle: float = param(
        title=_("Richtung des Langlochs"),
        default=0.0,
        minimum=-180.0,
        maximum=180.0,
        unit=DEGREE_UNIT,
        placement="front",
        doc=_("Dreht das Langloch um die Achse der Bohrung. Die Bohrung bleibt seine Mitte."),
    )
    at_feature: str = param(
        title=_("Bohrung"),
        default="",
        kind="feature",
        required=True,
        # Vorn, aus demselben Grund wie bei *Bohrung ändern*: Ein Pflichtfeld
        # ohne „— keines —" steht vorausgewählt auf der ersten Bohrung, und
        # zugeklappt wäre das eine stille Wahl (Regel 21).
        placement="front",
        doc=_(
            "Die erkannte Bohrung, die zum Langloch wird. Ein Klick auf die Bohrung trägt sie ein."
        ),
    )
    x: float | None = param(
        title=_("X"),
        default=None,
        optional=True,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte des Langlochs. Beim Anklicken steht hier die heutige "
            "der Bohrung; leer heißt, sie bleibt, wo sie ist."
        ),
    )
    y: float | None = param(
        title=_("Y"),
        default=None,
        optional=True,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte des Langlochs. Beim Anklicken steht hier die heutige "
            "der Bohrung; leer heißt, sie bleibt, wo sie ist."
        ),
    )
    z: float | None = param(
        title=_("Z"),
        default=None,
        optional=True,
        unit="mm",
        minimum=-1000.0,
        maximum=1000.0,
        placement="front",
        doc=_(
            "Die Mitte des Langlochs. Beim Anklicken steht hier die heutige "
            "der Bohrung; leer heißt, sie bleibt, wo sie ist."
        ),
    )
    diameter: float | None = param(
        title=_("Breite"),
        default=None,
        optional=True,
        unit="mm",
        minimum=0.2,
        placement="front",
        doc=_(
            "Die Breite des Langlochs. Leer heißt: so breit wie die Bohrung gemessen "
            "ist. Mit einer Zahl wird das Langloch in einem Schritt gezogen und auf "
            "diese Breite gebracht."
        ),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=False,
        placement="advanced",
        doc=_(
            "Vergrößert das gewählte Fertigmaß um den Wert aus dem Materialprofil. "
            "Aus bleibt das gemessene Maß unverändert."
        ),
    )


#: Die Arten, aus denen ein Langloch werden kann.
#:
#: Ein **Langloch** steht dabei, und das ist keine Verlegenheit: Die Operation
#: zieht ein rundes Loch auseinander und ändert ein vorhandenes in beide
#: Richtungen. Ohne diesen Eintrag wäre ein erkanntes Langloch eine Sackgasse —
#: ein Merkmal, an dem der Klick in einem Menü aus *Ausblenden* endet (§2.6).
SLOT_FROM: Final[tuple[str, ...]] = ("hole", "slot")

#: Was aus der Bohrung geworden ist — und unter welchem Namen sie weiterlebt.
#:
#: **Der Satz hat sich mit der Erkennung geändert.** Solange sie nur Zylinder
#: kannte, zerfiel ein Langloch ihr in zwei Verrundungen, und hier stand, das
#: Merkmal sei fort. Seit :mod:`app.core.perceive.slots` es zusammensetzt, ist
#: es da — nur unter einem anderen Namen und einer anderen Art. Das ist eine
#: gute Nachricht und trotzdem eine Auskunft: Wer auf ``hole_1`` verwiesen hat,
#: findet dort jetzt ``slot_1``.
SLOT_FEATURE_RENAMED: Final = _(
    "Aus der Bohrung ist ein Langloch geworden. Im Objektbaum steht sie ab "
    "jetzt als Langloch; ein früherer Schritt, der auf die Bohrung verwiesen "
    "hat, fragt beim nächsten Öffnen nach."
)


@register_op(
    name="slot_hole",
    # 5: die Breite als eigener Parameter (22.09.2026).
    # 6: der erste Zug schließt die runde Bohrung und schneidet ohne Zugabe.
    # 7: ein verkürztes Langloch schließt zuerst seinen alten Umriss.
    # 8: genau die Breite als Länge schneidet wieder eine runde Bohrung.
    cache_version="8",
    # **Kein „Bohrung zum Langloch".** Der Titel stand so, solange die
    # Operation nur an einer Bohrung galt; seit die Erkennung Langlöcher findet
    # (:mod:`app.core.perceive.slots`), gilt sie auch an einem und hieße dort
    # „Bohrung zum Langloch" an etwas, das keine Bohrung mehr ist. „Ziehen"
    # trifft beides: aus einem runden Loch ein langes, die Länge eines
    # vorhandenen Langlochs in beiden Richtungen ändern.
    title=_("Zum Langloch ziehen"),
    category="holes",
    params=SlotHoleParams,
    consumes=1,
    produces=1,
    applies_to=list(SLOT_FROM),
    touches_features=True,
    deterministic=False,
    doc=_(
        "Zieht eine erkannte Bohrung zu einem Langloch auseinander oder ändert Länge, "
        "Breite und Richtung eines vorhandenen Langlochs. Die Länge lässt sich "
        "vergrößern und verkleinern, bis zurück auf die Breite — dann ist es wieder "
        "eine runde Bohrung. Ohne neue Breite bleibt der gemessene Durchmesser."
    ),
)
def slot_hole(ctx: OpContext) -> OpResult:
    """Dieselbe Formänderung für Netze und für exakte Körper.

    Der Durchmesser bleibt, wie er gemessen wurde; eingetragen werden Länge und
    Richtung — **und wahlweise die Breite** (Entscheidung Robert, 22.09.2026:
    „Ja eine transaktion"). Wer an den Knöpfen zieht und daneben einen neuen
    Durchmesser eintippt, bekommt beides als **einen** Schritt: Die alte
    Öffnung wird geschlossen und das Langloch in der neuen Breite geschnitten,
    ein Strg+Z nimmt beides. Zwei Schritte gingen nicht: Das Langloch heißt
    nach dem ersten Zug neu (``SLOT_FEATURE_RENAMED``), und einen zweiten
    Schritt an einen Namen zu hängen, den erst die Auswertung vergibt, wäre
    Raten (Regel 21).

    **Ein bestehendes Langloch geht denselben Weg.** Seine Mitte, seine Achse
    und seine Breite stehen im Merkmal wie bei einer Bohrung; was dazukommt,
    ist die Richtung, in der es schon liegt — und die wird zur Vorgabe, damit
    ein Zug an der Länge es nicht quer stellt.

    **Und eine andere Richtung dreht es, statt es zu kreuzen** (Robert,
    15.09.2026: „habe ich 2 langlöcher"). Bis dahin schnitt der Zug mit
    neuem Winkel ein zweites Langloch quer über das erste — richtig gerechnet,
    mit einer Warnung, und trotzdem das Gegenteil dessen, was der Ring am
    Griff verspricht. Jetzt geht ein gedrehtes Langloch denselben Weg wie ein
    versetztes: Die alte Öffnung wird geschlossen, die neue geschnitten.
    """
    params = cast(SlotHoleParams, ctx.params)
    source = ctx.inputs[0]
    feature = _chosen_bore(source, params.at_feature, op="slot_hole")
    from app.core.perceive.relations import cavity_chain_state_at, cavity_is_shared

    body = as_mesh_data(source.mesh)
    neighbours = source.features
    selected = feature
    if source.kind == "brep":
        # Der exakte Merkmalsbaum beschreibt Kegelflächen noch nicht als Senkung.
        # Die Netz-Erkennung ergänzt sie; dieselben Dreiecke benennen die Bohrung.
        from app.core.perceive.features import detect

        neighbours = detect(body)
        faces = set(feature.face_indices)
        matching = [
            entry
            for entry in neighbours.values()
            if entry.kind == feature.kind and faces.intersection(entry.face_indices)
        ]
        if len(matching) == 1:
            selected = matching[0]
    if cavity_is_shared(cavity_chain_state_at(selected, neighbours, body)):
        raise ValidationError(
            field="at_feature",
            constraint="slot_and_widening",
            value=feature.id,
            detail=NEEDS_A_PLAIN_BORE,
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    # **Die Stelle kommt aus den Feldern, wo welche stehen** (Robert,
    # 10.09.2026: „einfach wie wenn ich eine bohrung setze"). Damit ist *Zum
    # Langloch ziehen* dieselbe Bedienung wie *Bohrung setzen*: Die
    # Flächenplatzierung schreibt die Maße zu den Kanten in x, y und z, und wer
    # eines davon ändert, verschiebt das Loch.
    #
    # **Drei Nullen heißen „lass es, wo es ist".** Das Panel und die
    # Platzierung belegen die Felder mit der gemessenen Mitte; über Chat und
    # Kommandozeile sagt sie niemand, und dort wäre der Ursprung die falsche
    # Antwort — ein Langloch wanderte in die Ecke des Bauraums, weil niemand
    # eine Stelle genannt hat. Der Ursprung als *gewollte* Zielmitte ist der
    # seltenere Fall, und für ihn steht ein Tausendstel daneben.
    measured = _bore_vector(feature, "centre")
    centre = _named_place(params.x, params.y, params.z, measured) or measured
    axis = _bore_vector(feature, "axis")
    measured_diameter = _bore_number(feature, "diameter")
    diameter = measured_diameter
    if params.diameter is not None:
        _reject_oversized("diameter", params.diameter, source.mesh)
        diameter = bore_diameter(params.diameter, ctx.profile, params.compensate)
    # Eine andere Breite schließt die alte Öffnung wie ein Versetzen — sonst
    # bliebe ein schmaleres Langloch in der weiteren Bohrung stehen.
    widened = not is_close(diameter, measured_diameter)
    depth = _bore_number(feature, "depth")
    through = bool(feature.params.get("through", False))
    # **Genau die Breite heißt rund** (Robert, 24.09.2026): Wer ein Langloch
    # bis auf seine Breite zurückzieht, meint die Bohrung, aus der es kam. Die
    # Breite ist die eingetragene, nicht die mit der Materialtoleranz — gegen
    # sie rastet auch der Griff (:func:`prepare.is_round_length`). Der
    # geschnittene Durchmesser gilt ebenso: Mit Toleranzausgleich rastet der
    # Griff auf ihn, denn er zeigt das Loch, das entsteht.
    width = params.diameter if params.diameter is not None else measured_diameter
    rounded = is_round_length(params.slot_length, width) or is_round_length(
        params.slot_length, diameter
    )
    # **Gefragt wird gegen den gemessenen Durchmesser**, denn gegen ihn misst
    # auch die Erkennung — und sie ist es, die entscheidet, ob nachher ein
    # Langloch im Objektbaum steht (:func:`prepare.shortest_slot`).
    shortest = shortest_slot(diameter)
    if not rounded and params.slot_length < shortest - EPS_GEOM:
        raise ValidationError(
            field="slot_length",
            constraint="slot_proportion",
            detail=NEITHER_ROUND_NOR_SLOT,
            value=params.slot_length,
            values={
                "diameter": format_length(width),
                "shortest": format_length(shortest),
            },
        )
    # Beim Verkürzen liegt das Werkzeug im vorhandenen Hohlraum. Deshalb muss
    # zuerst der alte Umriss geschlossen werden, wie bei einer anderen Breite.
    shortened = (
        feature.kind == "slot" and params.slot_length < _bore_number(feature, "length") - EPS_GEOM
    )
    _reject_oversized("slot_length", params.slot_length, source.mesh, kind="length")
    # Die Vorbelegung am Merkmal liefert dessen Richtung. Jeder übergebene
    # Winkel gilt unverändert, auch null; sonst widerspricht der Schnitt dem Griff.
    angle = params.slot_angle
    # Die Merkmale, die bleiben — ohne das, aus dem gerade ein Langloch wird.
    carried = {
        name: entry
        for name, entry in _without_old_triangles(source.features).items()
        if entry.provenance == "generated" and name != feature.id
    }
    # **Nur beim ersten Zug.** Aus einem Langloch wird kein Langloch — es wird
    # länger, und dabei behält es Art und Kennung. Der Satz stünde dort über
    # einer Umbenennung, die nicht stattfindet.
    said: list[Finding] = []
    if feature.kind == "hole" and not rounded:
        said.append(
            Finding(
                code="slot_hole.feature_renamed",
                severity="info",
                message=SLOT_FEATURE_RENAMED,
                feature_ids=(feature.id,),
                # ``_mm`` statt einer fertigen Zeichenkette: Die Oberfläche
                # schreibt die Einheit selbst und schaltet auf Zoll um (§19.3).
                values={"feature": feature.id, "length_mm": params.slot_length},
            )
        )
    # Ein rundes Loch hat keine Richtung, in die es gedreht wäre.
    turning = None if rounded else _slot_turned(feature, axis, angle)
    if turning is not None:
        said.append(turning)

    # **Wer versetzt, schließt die alte Stelle** — sonst steht die Bohrung noch
    # da und daneben ein Langloch (gemessen 10.09.2026: `hole_1` und `slot_1`
    # im selben Körper). Dieselbe Paarung wie bei *Merkmal verschieben*: an der
    # alten Stelle das Gegenteil des Merkmals, an der neuen das Merkmal selbst.
    # **Und wer dreht, ebenso**: Ein Langloch in neuer Richtung über dem alten
    # war ein Kreuz (gemessen 15.09.2026 an der Platte: 397 mm³ mehr abgetragen,
    # kein Langloch mehr erkannt). Geschlossen wird die Öffnung, wie sie liegt.
    moved = not all(is_close(a, b) for a, b in zip(centre, measured, strict=True))
    # **Und wer aus einer runden Bohrung ein Langloch zieht, auch** (22.09.2026).
    # Bis dahin schnitt der erste Zug mit der Zugabe aus §39 über die runde
    # Wand — der Körper legte sich sonst entlang zweier Linien an sie — und
    # das Langloch kam um genau diese Zugabe zu breit und zu lang heraus:
    # 5,020 x 20,020, wo *Bohrung setzen* mit dem Haken *Langloch* 5,000 x
    # 20,000 schneidet, an beiden Kernen gleich (Übertrag der Durchsicht
    # v0.4.1). Zwei Wege zu demselben Auftrag, zwei Maße. Geschlossen gibt es
    # die runde Wand nicht mehr, und das Werkzeug schneidet ohne Zugabe in
    # volles Material — dasselbe Loch wie beim Bohren.
    closes_the_old = moved or turning is not None or widened or shortened or feature.kind == "hole"
    if rounded and feature.kind == "hole" and not moved and not widened:
        # Eine runde Bohrung auf ihre eigene Breite gezogen: Geschnitten und
        # gefüllt würde dasselbe Loch, und der Satz sagt, dass nichts geschah.
        return OpResult(outputs=[source], findings=[_already_round(feature)])
    # Die Länge, mit der geschnitten wird. Rund heißt: genau der geschnittene
    # Durchmesser — :func:`prepare.slot_bore` schneidet dann einen Zylinder.
    cut_length = diameter if rounded else params.slot_length
    # **Ohne Zugabe, an jedem Zug.** An einem Langloch, das schon eines ist,
    # liegen die Flanken des Werkzeugs auf denen des Lochs, und das rechnen
    # beide Kerne robust; mit Zugabe wuchs es bei **jedem** Zug (gemessen
    # 11.09.2026: 5,2057 → 5,2213 → 5,2371 an einer Bohrung von 5,1901).
    overlap = 0.0
    if params.diameter is not None:
        said.extend(compensation_findings(params.diameter, diameter, params.compensate))

    if source.kind == "brep":
        from app.core.brep import edit
        from app.core.brep.features import features_of
        from app.core.brep.kernel import Solid

        if not isinstance(source.mesh, Solid):
            raise InternalError(
                detail="a scene object marked as brep does not carry a Solid",
                values={"object": source.id},
            )
        started = source.mesh
        if closes_the_old:
            # Bis zum 10.09.2026 stand hier eine Absage: „Am exakten Körper
            # lässt sich ein Loch noch nicht versetzen." Sie hatte einen
            # Grund — der Kern konnte kein Loch füllen —, und der ist mit
            # `edit.fill_bore` weg. Zwischen den beiden Kernen soll kein
            # Unterschied bleiben (Robert, 10.09.2026).
            # Derselbe Stopfen wie beim Versetzen (:func:`_exact_cavity_filled`):
            # an den Randebenen begrenzt, damit eine schräge Mündung keine
            # Beule über der Fläche zurücklässt.
            started = _exact_cavity_filled(started, feature)
        cut_depth = _through_bore_depth(started, centre, axis) if through else depth
        if rounded:
            solid = edit.unified(
                edit.cut_bore(
                    started, position=centre, direction=axis, diameter=diameter, depth=cut_depth
                )
            )
        else:
            solid = edit.slot_bore(
                started,
                position=centre,
                direction=axis,
                diameter=diameter,
                depth=cut_depth,
                length=params.slot_length,
                angle_deg=angle,
                overlap=overlap,
            )
        if solid.volume <= EPS_GEOM or solid.face_count == 0:
            raise GeometryError(
                title=NOTHING_LEFT_TITLE,
                detail=NOTHING_LEFT_DETAIL,
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        if not solid.is_closed:
            raise GeometryError(
                title=OPEN_BODY_TITLE,
                detail=OPEN_BODY_DETAIL,
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        findings: list[Finding] = list(said)
        # Gegen den gefüllten Körper, wie am Netz (``prepare.slot_bore``): Ein
        # Versetzen oder Verkürzen mit neuer Breite trägt oft gleich viel ab,
        # wie es füllt, und hieß gegen das Original „nichts abgetragen"
        # (Review 24.09.2026).
        nothing = without_effect(started, solid, "difference", ctx.profile)
        if nothing is not None:
            findings.append(nothing)
        # Die Kantenfrage gilt beiden Bogenmittelpunkten, wie beim Verbreitern.
        from app.core.sketch.planes import frame_of

        findings.extend(
            edge_findings(
                source.mesh,
                position=centre,
                frame=frame_of(axis, centre),
                diameter=diameter,
                travel=0.0 if rounded else slot_travel(diameter=diameter, length=cut_length),
                angle_deg=angle,
                body=as_mesh_data(source.mesh),
                reach=_depth_of(feature) / 2.0,
            )
        )
        findings.extend(split_findings(source.mesh, solid))
        exact_features = features_of(solid, cancelled=ctx.cancelled)
        if rounded:
            findings.extend(
                _round_neighbour_findings(
                    source,
                    feature,
                    centre,
                    axis,
                    diameter,
                    cut_depth,
                    ctx,
                    moved,
                    widened,
                    findings,
                )
            )
            findings.extend(
                _round_outcome(
                    feature,
                    _recognised_round(
                        exact_features,
                        feature,
                        centre=centre,
                        diameter=diameter,
                        diagonal=solid.bounds.diagonal,
                        body_centre=solid.bounds.centre,
                        check_cancelled=ctx.cancelled.raise_if_cancelled,
                    ),
                    diameter,
                )
            )
            return OpResult(
                outputs=[
                    dataclasses.replace(source, mesh=solid, kind="brep", features=exact_features)
                ],
                findings=findings,
            )
        # **Dieselbe Auskunft wie am Netz** (Robert, 10.09.2026: „zwischen den
        # beiden soll es keinen unterschied geben bei garnichts"). Wer über den
        # Rand zieht, behält eine erkennbare Randöffnung als Langloch. Ein
        # Kreuz über dem eigenen Schnitt kann dagegen seinen Bezug verlieren.
        #
        # **Gesucht wird das eine, nicht irgendeines.** Hier stand ``any(kind
        # == "slot")``, und das schwieg, sobald ein zweites Langloch im Körper
        # stand (Fund des Reviews, 11.09.2026).
        pulled_exact = _recognised_slot(
            exact_features,
            feature,
            centre=centre,
            diameter=diameter,
            length=params.slot_length,
            diagonal=solid.bounds.diagonal,
            body_centre=solid.bounds.centre,
            angle=angle,
            check_cancelled=ctx.cancelled.raise_if_cancelled,
        )
        if pulled_exact is None:
            findings.append(_slot_no_longer_a_feature(feature, params.slot_length))
        # **Neu erkannt und nicht mitgetragen.** Hier stand ``dict(carried)``,
        # und das war am exakten Kern immer leer: ``carried`` behält, was
        # ``provenance == "generated"`` trägt, und ``brep.features.features_of``
        # vergibt ausschließlich ``"detected"``. Gemessen an einem Quader mit
        # einer Bohrung — acht Merkmale, davon behalten: null. Nach *Zum
        # Langloch ziehen* stand der Objektbaum eines eingelesenen STEP-Körpers
        # leer da: keine Fläche, keine Kante, nichts mehr zum Anklicken, und
        # damit auch keine Fase und keine Verrundung mehr.
        #
        # Eine Rückzuordnung wie in ``resize_hole`` gibt es hier nicht zu
        # retten — aus der Bohrung wird eine andere Art, und ``matching``
        # sucht nach Art. Also derselbe Weg wie bei jeder anderen Ausgabe des
        # exakten Kerns (``geom/ops.py``, ``brep/ops.py``): frisch erkennen.
        return OpResult(
            outputs=[dataclasses.replace(source, mesh=solid, kind="brep", features=exact_features)],
            findings=findings,
        )

    body = as_mesh_data(source.mesh)
    # Am Original gemessen, nicht am gestopften Körper — die Begründung steht
    # bei derselben Zeile in `resize_hole`.
    exact_depth = _mesh_bore_depth(body, feature, axis, depth)
    filled: list[Finding] = []
    closing_solver = None
    if closes_the_old:
        closing = _closed_at(
            body,
            feature,
            measured,
            True,
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        body = closing.mesh
        filled = list(closing.findings)
        closing_solver = closing.solver
    mesh_depth = _through_bore_depth(body, centre, axis) if through else exact_depth
    result = slot_bore(
        body,
        position=centre,
        direction=axis,
        diameter=diameter,
        depth=mesh_depth,
        through=through,
        length=cut_length,
        angle_deg=angle,
        profile=ctx.profile,
        quality=ctx.quality,
        seed=ctx.seed,
        overlap=overlap,
    )
    if rounded:
        from app.core.perceive.features import detect

        found = _recognised_round(
            detect(result.mesh, check_cancelled=ctx.cancelled.raise_if_cancelled),
            feature,
            centre=centre,
            diameter=diameter,
            diagonal=result.mesh.bounds.diagonal,
            body_centre=result.mesh.bounds.centre,
            check_cancelled=ctx.cancelled.raise_if_cancelled,
        )
        # Eine Bohrung, die rund bleibt, behält ihren Namen; aus einem
        # Langloch wird eine Bohrung, und die bekommt einen neuen.
        kept = {feature.id: found} if found is not None and feature.kind == "hole" else {}
        # ``said`` wie im exakten Zweig: Die Materialtoleranz meldet sich an
        # beiden Kernen (Review 24.09.2026, am Netz fehlte sie).
        round_findings = [*said, *filled, *result.findings]
        round_findings.extend(
            _round_neighbour_findings(
                source,
                feature,
                centre,
                axis,
                diameter,
                mesh_depth,
                ctx,
                moved,
                widened,
                round_findings,
            )
        )
        round_findings.extend(_round_outcome(feature, found, diameter))
        return OpResult(
            outputs=[dataclasses.replace(source, mesh=result.mesh, features={**carried, **kept})],
            solver=deepest((closing_solver, result.solver)),
            findings=round_findings,
        )
    # **Gesucht wird das Langloch, das gerade entstanden ist** — für zwei
    # verschiedene Antworten. Findet es sich nicht, sagt es der Befund unten
    # (Regel 17), statt dass das Merkmal still verschwindet.
    #
    # Findet es sich, behält es seinen Namen — aber nur, wenn es schon eines
    # war. Beim **ersten** Zug wird ``hole_1`` zu ``slot_1``, und das ist
    # zugesagt: ``SLOT_FEATURE_RENAMED`` sagt es dem Kunden ausdrücklich. Beim
    # **zweiten** wird ein Langloch länger und behält Art und Kennung; hier
    # stand ``dict(carried)`` und sonst nichts, und wie es danach hieß,
    # entschied die Zählung der Erkennung. Solange genau ein Langloch im Körper
    # steht, fällt das nicht auf — sobald es mehrere sind, wandert die Auswahl
    # des Kunden auf ein fremdes Loch. Dieselbe Zuordnung wie in
    # ``resize_hole``, nur gegen ein Langloch statt gegen eine Bohrung.
    from app.core.perceive.features import detect

    pulled_feature = _recognised_slot(
        detect(result.mesh, check_cancelled=ctx.cancelled.raise_if_cancelled),
        feature,
        centre=centre,
        diameter=diameter,
        length=params.slot_length,
        diagonal=result.mesh.bounds.diagonal,
        body_centre=result.mesh.bounds.centre,
        angle=angle,
        check_cancelled=ctx.cancelled.raise_if_cancelled,
    )
    features = (
        {**carried, feature.id: pulled_feature}
        if pulled_feature is not None and feature.kind == "slot"
        else dict(carried)
    )
    findings = [
        *said,
        *filled,
        *result.findings,
    ]
    if pulled_feature is None:
        findings.append(_slot_no_longer_a_feature(feature, params.slot_length))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features=features)],
        solver=deepest((closing_solver, result.solver)),
        findings=findings,
    )


def _neighbour_bore_findings(
    source: SceneObject,
    feature: Feature,
    tool: MeshData,
    ctx: OpContext,
    *,
    moved: bool = False,
    deeper: bool = False,
    turned: bool = False,
    copy: bool = False,
) -> list[Finding]:
    """Nur eine durch diese Vergrößerung — oder diese Stelle — geschwächte
    Nachbarwand melden.

    ``moved`` sagt, dass das Werkzeug an einer neuen Stelle steht; der Satz
    nennt dann die Stelle als Ausweg, nicht den Durchmesser. ``deeper`` sagt
    dasselbe für eine neue Tiefe, ``turned``, dass es gekippt steht (*Merkmal
    drehen*); dann ist der Ausweg ein anderer Winkel. ``copy`` sagt, dass das
    Werkzeug eine Kopie setzt (*Merkmal verdoppeln*): Dann ist die Vorlage
    selbst eine Nachbarin, und vorher gab es keine Wand, die dünner werden
    konnte — jede zu dünne zählt.

    Der Hüllquader sortiert entfernte Kandidaten aus. Den Abstand bestimmen
    die echten, an ihren Endringen geschlossenen Hohlräume und das tatsächlich
    verwendete Werkzeug. So werden weder schräge Achsen noch unterschiedliche
    Tiefen zu einem bloßen Abstand im Grundriss vereinfacht.
    """
    from app.core.geom.measure import surface_gap
    from app.core.perceive.relations import cavity_chains

    mesh = as_mesh_data(source.mesh)
    chains = cavity_chains(source.features, mesh)
    grouped = {section.id: chain for chain in chains for section in chain}
    own = grouped.get(feature.id, (feature,))
    old = None if copy else _paired_cavity_body(mesh, *own)
    if old is None and not copy:
        return []
    seen = set() if copy else {section.id for section in own}
    threshold = ctx.profile.minimum_wall_thickness
    tool_bounds = np.asarray(tool.raw.bounds)
    findings = []
    for candidate in source.features.values():
        if (
            candidate.id in seen
            or candidate.kind not in {"hole", "cone"}
            or not is_a_cavity(candidate)
        ):
            continue
        ctx.cancelled.raise_if_cancelled()
        neighbours = grouped.get(candidate.id, (candidate,))
        seen.update(section.id for section in neighbours)
        indices = tuple(index for section in neighbours for index in section.face_indices)
        if not indices or min(indices) < 0 or max(indices) >= len(mesh.raw.faces):
            continue
        points = np.asarray(mesh.raw.vertices)[np.unique(np.asarray(mesh.raw.faces)[list(indices)])]
        bounds = np.stack((points.min(axis=0), points.max(axis=0)))
        separation = np.maximum(
            np.maximum(bounds[0] - tool_bounds[1], tool_bounds[0] - bounds[1]), 0.0
        )
        if float(np.linalg.norm(separation)) >= threshold:
            continue
        other = _paired_cavity_body(mesh, *neighbours)
        if other is None:
            continue
        after_gap = surface_gap(tool, other, threshold)
        if after_gap is None or after_gap >= threshold - EPS_GEOM:
            continue
        before_gap = None if old is None else surface_gap(old, other, threshold)
        if old is not None and (before_gap is None or before_gap <= after_gap + EPS_GEOM):
            continue
        opened = after_gap <= EPS_GEOM
        neighbour = neighbours[0]
        findings.append(
            Finding(
                code="bore.neighbour_opened" if opened else "bore.neighbour_wall_thin",
                severity="warning",
                message=_neighbour_message(
                    opened, moved, after_gap, threshold, deeper=deeper, turned=turned
                ),
                feature_ids=(feature.id, neighbour.id),
                values={
                    "thickness": after_gap,
                    "minimum": threshold,
                    **({} if before_gap is None else {"previous": before_gap}),
                },
                suggestions=(CORRECT_INPUT,),
            )
        )
    return findings


def _neighbour_message(
    opened: bool,
    moved: bool,
    thickness: float,
    minimum: float,
    *,
    deeper: bool = False,
    turned: bool = False,
) -> TranslatableText:
    """Der Satz zur Nachbarwand: was sie schwächt, und was der Kunde ändern kann."""
    if turned and opened:
        return _(
            "In dieser Neigung verbindet sich die Bohrung mit einem benachbarten Hohlraum. "
            "Wählen Sie einen anderen Winkel, um die Trennwand zu erhalten."
        )
    if turned:
        return _(
            "In dieser Neigung bleiben zum benachbarten Hohlraum nur {thickness:.2f} mm "
            "Wand. Das Materialprofil verlangt mindestens {minimum:.2f} mm. Wählen Sie "
            "einen anderen Winkel.",
            thickness=thickness,
            minimum=minimum,
        )
    if deeper and opened:
        return _(
            "Bei dieser Tiefe verbindet sich die Bohrung mit einem benachbarten Hohlraum. "
            "Wählen Sie eine geringere Tiefe, um die Trennwand zu erhalten."
        )
    if deeper:
        return _(
            "Bei dieser Tiefe bleiben zum benachbarten Hohlraum nur {thickness:.2f} mm "
            "Wand. Das Materialprofil verlangt mindestens {minimum:.2f} mm. Wählen Sie "
            "eine geringere Tiefe.",
            thickness=thickness,
            minimum=minimum,
        )
    if moved and opened:
        return _(
            "An dieser Stelle verbindet sich die Bohrung mit einem benachbarten Hohlraum. "
            "Wählen Sie eine andere Stelle, um die Trennwand zu erhalten."
        )
    if moved:
        return _(
            "An dieser Stelle bleiben zum benachbarten Hohlraum nur {thickness:.2f} mm "
            "Wand. Das Materialprofil verlangt mindestens {minimum:.2f} mm. Wählen Sie "
            "eine andere Stelle.",
            thickness=thickness,
            minimum=minimum,
        )
    if opened:
        return _(
            "Diese Vergrößerung verbindet die Bohrung mit einem benachbarten "
            "Hohlraum. Wählen Sie einen kleineren Durchmesser, um die Trennwand "
            "zu erhalten."
        )
    return _(
        "Durch diese Vergrößerung bleiben zum benachbarten Hohlraum nur "
        "{thickness:.2f} mm Wand. Das Materialprofil verlangt mindestens "
        "{minimum:.2f} mm. Wählen Sie einen kleineren Durchmesser.",
        thickness=thickness,
        minimum=minimum,
    )


def _widening_findings(source: SceneObject, feature: Feature, diameter: float) -> list[Finding]:
    """Sagt es, wenn über der geänderten Bohrung eine Senkung sitzt.

    **Der Fall, der diese Funktion veranlasst hat.** Robert hat am 04.09.2026
    an einem heruntergeladenen Halter den Durchmesser einer Bohrung geändert;
    über ihr saß eine Senkung Ø 8,16, und die blieb stehen. Im Teil entstand
    eine Stufe, und gesagt wurde nichts — ``resize_hole`` und
    ``resize_feature`` ändern genau ein Merkmal und kennen seine Nachbarschaft
    nicht.

    **Zwei Härten, und der Unterschied ist der Schaden.** Wächst die Bohrung
    bis an die Senkung heran, ist die Senkung weg: Ein Kegel, der enger ist
    als sein Loch, hat keine Fläche mehr. Das ist eine Warnung. Bleibt sie
    enger, ist die Senkung noch da, sitzt aber nicht mehr im gemessenen
    Verhältnis — das ist ein Hinweis, und wer ihn nicht braucht, überliest ihn.

    Beide tragen dieselbe Handlung (:data:`RESIZE_THE_WIDENING`), weil beide
    denselben Ausweg haben, und beide nennen die Zahlen: Ohne sie müsste der
    Kunde die Senkung erst suchen, um zu wissen, wovon die Rede ist (§2.7).
    """
    # Der Import steht hier und nicht oben: ``perceive`` zieht die Erkennung
    # mit, und die kostet beim Laden des Moduls Zeit, die eine Operation ohne
    # Senkung nie braucht — dieselbe Aufteilung wie bei ``detect`` weiter unten.
    from app.core.perceive.relations import (
        cavity_chain_at,
        cavity_sides,
        widening_at_the_mouth,
    )

    mesh = as_mesh_data(source.mesh)
    chain = cavity_chain_at(feature, source.features, mesh)
    if chain is not None and len(chain) > 2:
        # Der nächste Abschnitt nach außen, auf jeder Seite, auf der das Merkmal
        # liegt — an einer Bohrung mit Erweiterungen an beiden Enden sind es
        # zwei (``relations.cavity_sides``, RM-245).
        swallowed = False
        for side in cavity_sides(chain):
            names = [section.id for section in side]
            if feature.id not in names or names.index(feature.id) + 1 >= len(side):
                continue
            wider = side[names.index(feature.id) + 1]
            swallowed = swallowed or diameter >= float(wider.params["diameter"]) - EPS_GEOM
        return [
            Finding(
                code="resize.cavity_sections_kept",
                severity="warning" if swallowed else "info",
                message=_(
                    "Die Bohrung und ihre Senkungen bilden einen gemeinsamen Hohlraum. "
                    "Geändert wurde nur dieser Durchmesser. Prüfen Sie die übrigen "
                    "Abschnitte oder korrigieren Sie die Eingabe."
                ),
                feature_ids=tuple(section.id for section in chain),
                values={"diameter": diameter, "previous": float(feature.params["diameter"])},
                suggestions=(CORRECT_INPUT,),
            )
        ]
    widening = widening_at_the_mouth(feature, source.features, mesh=mesh)
    if widening is None:
        return []
    outer = float(widening.params.get("diameter") or 0.0)
    values: dict[str, float | str | TranslatableText] = {
        "widening": widening.id,
        "outer": outer,
        "diameter": diameter,
        # Das **alte** Maß der Bohrung, damit „Senkung mitziehen" den Rand
        # ausrechnen kann, den die Senkung bisher gelassen hat. Ohne diese Zahl
        # müsste die Oberfläche ihn schätzen oder ein Verhältnis erfinden.
        "previous": float(feature.params.get("diameter") or 0.0),
    }
    if diameter >= outer - EPS_GEOM:
        return [
            Finding(
                code="resize.widening_swallowed",
                severity="warning",
                message=_(
                    "Über dieser Bohrung sitzt eine Senkung mit {outer:.2f} mm. Mit "
                    "{diameter:.2f} mm ist die Bohrung nicht mehr enger als sie — die "
                    "Senkung verschwindet. Ziehen Sie die Senkung mit, oder bleiben Sie "
                    "unter ihrem Maß.",
                    outer=outer,
                    diameter=diameter,
                ),
                feature_ids=(feature.id, widening.id),
                values=values,
                suggestions=(RESIZE_THE_WIDENING, CORRECT_INPUT),
            )
        ]
    return [
        Finding(
            code="resize.widening_kept",
            severity="info",
            message=_(
                "Über dieser Bohrung sitzt eine Senkung mit {outer:.2f} mm. Sie ist "
                "stehen geblieben und sitzt jetzt nicht mehr im gemessenen Verhältnis "
                "zur Bohrung.",
                outer=outer,
            ),
            feature_ids=(feature.id, widening.id),
            values=values,
            suggestions=(RESIZE_THE_WIDENING,),
        )
    ]


#: Ab welchem Unterschied ein Zug nicht mehr in Richtung des bestehenden
#: Langlochs geht.
#:
#: **Ein halbes Grad, und die Zahl ist gemessen.** Hier standen erst fünf Grad
#: mit der Begründung, darunter setze die Erkennung beide Züge wieder zu einem
#: Langloch zusammen. Das war geraten und falsch: An einem Langloch Ø 6 auf
#: 20 mm, auf 28 mm nachgezogen, bleibt es bis 0,5 Grad **ein** Merkmal und
#: zerfällt bei 0,75 Grad in zwei Verrundungen, bei einem Grad in vier.
#:
#: Wo genau es kippt, hängt von Länge und Breite ab — und deshalb steht die
#: Zahl hier gerade **nicht** dafür. Sie deckt, was :func:`slot_angle_of` an
#: Rundung erzeugt, und sonst nichts; alles darüber ist eine Richtungsänderung
#: und wird gesagt.
SLOT_ACROSS_LIMIT: Final = 0.5


def _slot_turned(
    feature: Feature, axis: tuple[float, float, float], angle: float
) -> Finding | None:
    """Sagt es, wenn der Zug das vorhandene Langloch in eine andere Richtung dreht.

    **Gefunden am gefahrenen Weg und nicht im Code** (10.09.2026): Ein
    bestehendes Langloch mit 90 Grad noch einmal gezogen ergab ein Kreuz, im
    Objektbaum standen danach vier Hohlkehlen, und gesagt hatte es niemand.
    Der Befund hieß deshalb ``slot_hole.crosses`` und warnte vor dem Kreuz.

    **Seit dem 15.09.2026 gibt es das Kreuz nicht mehr** (Robert: „habe ich 2
    langlöcher"): Die Operation schließt die alte Richtung, bevor sie die neue
    schneidet — derselbe Weg wie beim Versetzen. Was bleibt, ist die Auskunft:
    Das Loch liegt jetzt anders, und wer nur verlängern wollte, sieht hier,
    woran es lag. Ab einem halben Grad (:data:`SLOT_ACROSS_LIMIT`, das ist die
    Rundung von :func:`slot_angle_of`), denn darunter ist es dieselbe Richtung.
    """
    if feature.kind != "slot":
        return None
    standing = slot_angle_of(feature, axis)
    turned = abs((angle - standing + 180.0) % 360.0 - 180.0)
    # Auch 180 Grad sind dieselbe Richtung: Ein Langloch hat keine Vorder- und
    # keine Rückseite.
    if min(turned, abs(180.0 - turned)) <= SLOT_ACROSS_LIMIT:
        return None
    return Finding(
        code="slot_hole.turned",
        severity="info",
        message=_(
            "Das Langloch liegt jetzt {angle:.1f} Grad anders als vorher; die alte "
            "Richtung ist geschlossen. Wollten Sie es nur verlängern, lassen Sie "
            "die Richtung, wie sie stand.",
            angle=turned,
        ),
        feature_ids=(feature.id,),
        values={"feature": feature.id, "angle_deg": turned},
        suggestions=(CORRECT_INPUT,),
    )


def slot_angle_of(feature: Feature, axis: tuple[float, float, float]) -> float:
    """Der Winkel, unter dem ein erkanntes Langloch schon liegt.

    Die Umkehrung von :func:`app.core.geom.prepare.slot_profile` — gemessen
    gegen dieselbe x-Achse desselben Rahmens, damit ein unverändert
    übernommener Wert dieselbe Lage ergibt.

    **Öffentlich, weil die Ansicht dieselbe Frage stellt.** Der Langlochgriff
    (``app.ui.slot_handle``) belegt seine Knöpfe mit der Richtung, in der das
    Loch schon liegt, und schickt beim Loslassen eine neue zurück; rechnete er
    sie selbst, hinge der Griff um einen Winkel neben dem Schnitt.

    Ohne Richtung im Merkmal bleibt es bei null: Ein Langloch ohne Richtung
    gibt es nicht, aber eine Projektdatei aus einer älteren Fassung könnte
    eines tragen, und ein Fehler wäre dort die falsche Antwort auf eine Frage
    nach der Vorbelegung.
    """
    from app.core.sketch.planes import frame_of

    along = feature.params.get("direction")
    if not isinstance(along, tuple | list) or len(along) != 3:
        return 0.0
    frame = frame_of(axis, (0.0, 0.0, 0.0))
    direction = np.asarray(along, dtype=float)
    length = float(np.linalg.norm(direction))
    if length <= EPS_GEOM:
        return 0.0
    direction = direction / length
    return math.degrees(
        math.atan2(
            float(direction @ np.asarray(frame.y_axis, dtype=float)),
            float(direction @ np.asarray(frame.x_axis, dtype=float)),
        )
    )


def _chosen_bore(source: SceneObject, name: str, *, op: str = "") -> Feature:
    """Die angeklickte Bohrung oder eine Korrekturmöglichkeit statt Raten.

    **Gefragt wird der Registereintrag der aufrufenden Operation**, nicht eine
    Liste hier im Modul — dasselbe wie bei :func:`_movable_feature` und aus
    demselben Grund: *Bohrung ändern* nimmt nur eine Bohrung, *Zum Langloch
    ziehen* auch ein Langloch, und wo diese Menge steht, ist ``applies_to``.
    Eine zweite Aufzählung daneben wüsste beim nächsten Zuwachs die Hälfte, und
    der Satz für den Kunden käme aus einer zweiten Quelle
    (``.claude/rules/operationen.md``, „Und die zweite Hürde muss es wirklich
    geben").

    Ohne ``op`` bleibt es beim engeren Fall — der Bohrung. Das ist kein
    Rückfall aus Bequemlichkeit: Es gibt Aufrufer, die kein Merkmal aus einem
    Register heraus wählen, und für sie ist die Bohrung die richtige Antwort.
    """
    feature = source.features.get(name)
    if feature is None:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
            value=name,
            constraint="unknown_feature",
            values={"known": ", ".join(sorted(source.features))},
        )
    if op:
        from app.core.perceive.actions import reason_against

        against = reason_against(op, feature.kind)
        if against is None:
            return feature
        raise ValidationError(
            field="at_feature",
            detail=against,
            value=name,
            constraint="not_a_hole",
            values={"kind": feature.kind, "op": op},
        )
    if feature.kind != "hole":
        raise ValidationError(
            field="at_feature",
            detail=_("Zum Ändern des Durchmessers muss eine Bohrung gewählt sein."),
            value=name,
            constraint="not_a_hole",
            values={"kind": feature.kind},
        )
    return feature


def _named_place(x: float | None, y: float | None, z: float | None, measured: Vec3) -> Vec3 | None:
    """Die genannte Stelle — oder nichts, wenn keine genannt wurde (RM-154).

    **Drei Nullen waren einmal die Antwort auf beides.** ``x/y/z`` lasen sich
    als „lass das Loch, wo es ist", sobald alle drei null waren; damit ließ es
    sich in jede Stelle versetzen außer in den Ursprung — und Solidon legt einen
    Quader **um** den Ursprung, an einer mittig gelegten Platte ist (0 | 0 | 0)
    also die Mitte des Teils und kein Randfall.

    Seit die drei Felder ``optional`` tragen, steht „nicht gesagt" als ``None``
    da. Genannt ist eine Stelle, sobald **eine** der drei Achsen eine Zahl
    trägt — wer eine Achse nennt, beschreibt einen Ort und keine Verschiebung.

    **Eine ungenannte Achse behält dabei ihren gemessenen Wert.** Sie fiel bis
    zum 14.09.2026 auf null zurück, und damit sagte ein ``x=20`` aus Chat,
    Kommandozeile oder Agent zweierlei: „setz das Loch auf x = 20" und „setz es
    in y und z auf null". An einer mittig gelegten Platte sprang es damit in
    die Mitte des Teils, während das Feld daneben zusagt, eine leere Achse
    bleibe, wo sie ist. Der Dialog merkte davon nichts — er belegt alle drei
    Felder mit der gemessenen Mitte vor, dort ist keine Achse je ungenannt.
    """
    if x is None and y is None and z is None:
        return None
    return (
        float(measured[0] if x is None else x),
        float(measured[1] if y is None else y),
        float(measured[2] if z is None else z),
    )


def _bore_vector(feature: Feature, name: str) -> tuple[float, float, float]:
    """Eine gespeicherte Dreierkoordinate mit einem verständlichen Fehler."""
    value = feature.params.get(name)
    if (
        not isinstance(value, tuple | list)
        or len(value) != 3
        or not all(isinstance(entry, int | float) and math.isfinite(entry) for entry in value)
    ):
        raise bore_geometry_error(feature.id)
    if name == "axis" and math.hypot(*value) <= EPS_GEOM:
        raise bore_geometry_error(feature.id)
    return (float(value[0]), float(value[1]), float(value[2]))


def _bore_number(feature: Feature, name: str) -> float:
    """Ein positives Bohrungsmaß aus der Erkennung."""
    value = feature.params.get(name)
    if not isinstance(value, int | float) or not math.isfinite(value) or float(value) <= EPS_GEOM:
        raise bore_geometry_error(feature.id)
    return float(value)


@dataclasses.dataclass(frozen=True, slots=True)
class _EntranceSection:
    """Nominales radiales Profil und die wirklichen Grenzen eines Abschnitts.

    ``curved`` sagt, dass die Mündung dieses Abschnitts in einer gekrümmten
    Fläche liegt (:func:`_curved_mouth_planes`): ``upper`` ist dann die Ebene
    quer zur Achse durch ihren weitesten Punkt, und gefüllt wird die Kette aus
    ihren Flächen (:func:`_exact_chain_plug`).
    """

    feature: Feature
    lower: SectionPlane
    upper: SectionPlane
    start: float
    end: float
    inner_radius: float
    outer_radius: float
    shoulder: bool = False
    curved: bool = False


@dataclasses.dataclass(frozen=True, slots=True)
class _BoreEntrance:
    """Eine eindeutige, nach außen weiter werdende Bohrungsfolge.

    ``open`` sagt, ob das äußere Ende eine Mündung ist. Eine Senkung, deren
    Mündung unter der Oberfläche liegt, ist ein vergrabener Hohlraum mit einem
    Deckel aus Material — und ein Werkzeug, das dort um die Zugabe aus §39
    über die Ebene hinausreicht, trägt bei jedem Versetzen ein Scheibchen ab
    (1,33 mm³ an Ø 9,2, Review 21.09.2026).

    **Weitet sich die Bohrung an beiden Enden** (RM-245), liest ``back`` die
    zweite Seite: ihre Abschnitte entlang ``-axis``, die Bohrung vorn in dieser
    Richtung gelesen, ``back_open`` für deren Mündung. Leer ist ``back`` an
    jeder Kette mit einer Seite (``relations.cavity_sides``).
    """

    chain: tuple[Feature, ...]
    origin: Vec3
    axis: Vec3
    sections: tuple[_EntranceSection, ...]
    open: bool = True
    back: tuple[_EntranceSection, ...] = ()
    back_open: bool = True

    def sides(self) -> tuple[tuple[Vec3, tuple[_EntranceSection, ...], bool], ...]:
        """Je Seite ihre Richtung nach außen, ihre Abschnitte mit der Bohrung vorn
        und ob ihr Ende eine Mündung ist."""
        front = ((self.axis, self.sections, self.open),)
        if not self.back:
            return front
        away: Vec3 = (-self.axis[0], -self.axis[1], -self.axis[2])
        return (*front, (away, self.back, self.back_open))


def _entrance_error() -> ValidationError:
    """Ein gekoppelter Umfang braucht einen belegbaren Eintritt."""
    return ValidationError(
        field="entrance_mode",
        detail=_(
            "Dieser Einlauf lässt sich nicht eindeutig gemeinsam ändern. Wählen Sie "
            "„Nur Bohrungsdurchmesser“ und bearbeiten Sie weitere Abschnitte einzeln."
        ),
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def bore_entrance(
    body: Mesh,
    feature: Feature,
    features: Mapping[FeatureId, Feature],
    *,
    cavity: tuple[Feature, ...] | None = None,
    touches_other: bool = False,
) -> _BoreEntrance | None:
    """Liest denselben belegten Änderungsumfang für Operation und Handlungsvorgabe.

    Ein einzelner Zylinder hat keinen Einlauf, den er mitnehmen müsste.
    Doppelte Ränder, Hinterschnitte und unbestimmte Profile geben dagegen
    keine stillschweigende Erlaubnis zum Ändern nur eines Abschnitts.
    Eine mitgebrachte Kettenauskunft gilt auch hier; die leere Folge belegt
    einen einzelnen Hohlraum und verhindert eine zweite Topologieabfrage.

    Eine Bohrung mit Erweiterungen an beiden Enden liest beide Seiten
    (RM-245): die erste entlang der Achse, die zweite dagegen, jede mit
    denselben Prüfungen (:func:`_entrance_side`).
    """
    from app.core.perceive.relations import cavity_chain_state_at, cavity_sides

    mesh = as_mesh_data(body)
    if cavity is None and not touches_other:
        state = cavity_chain_state_at(feature, features, mesh)
        chain, touches = state.chain, state.touches_other
    else:
        chain, touches = cavity or None, touches_other
    if feature.kind != "hole" or (chain is None and touches):
        raise _entrance_error()
    if chain is None:
        return None
    if chain[0].id != feature.id:
        raise _entrance_error()
    welded = _welded(mesh)
    origin = _bore_vector(feature, "centre")
    direction = np.asarray(_bore_vector(feature, "axis"), dtype=float)
    direction /= np.linalg.norm(direction)
    sides = cavity_sides(chain)
    if float((np.asarray(sides[0][-1].params["centre"]) - origin) @ direction) < 0.0:
        direction = -direction
    axis: Vec3 = (float(direction[0]), float(direction[1]), float(direction[2]))
    exact_axes = all("residual" not in entry.params for entry in chain)
    read = [
        _entrance_side(mesh, welded, features, side, origin, way, exact_axes)
        for side, way in zip(sides, (direction, -direction), strict=False)
    ]
    return _BoreEntrance(
        chain,
        origin,
        axis,
        read[0],
        _entrance_is_open(mesh, origin, direction, read[0][-1]),
        read[1] if len(read) > 1 else (),
        _entrance_is_open(mesh, origin, -direction, read[1][-1]) if len(read) > 1 else True,
    )


def _entrance_side(
    mesh: MeshData,
    welded: Any,
    features: Mapping[FeatureId, Feature],
    side: Sequence[Feature],
    origin: Vec3,
    direction: NDArray[np.float64],
    exact_axes: bool,
) -> tuple[_EntranceSection, ...]:
    """Die Abschnitte einer Seite, von der Bohrung aus entlang ``direction``
    gelesen — mit allen Prüfungen, die :func:`bore_entrance` verspricht."""
    sections: list[_EntranceSection] = []
    for entry in side:
        shoulder = False
        curved = False
        if exact_axes or entry.kind == "hole":
            entry_axis = np.asarray(_feature_direction(entry), dtype=float)
            centre_offset = np.asarray(entry.params["centre"], dtype=float) - origin
            lateral = np.linalg.norm(centre_offset - float(centre_offset @ direction) * direction)
            tolerance = EPS_GEOM if exact_axes else MAX_FACET_SAG
            if float(lateral) > tolerance or (
                exact_axes and float(np.linalg.norm(np.cross(direction, entry_axis))) > EPS_GEOM
            ):
                raise _entrance_error()
        planes = _bore_end_planes(mesh, entry, features, grows=False)
        if len(planes) != 2 and entry.kind == "hole" and len(side) > 1 and entry.id == side[-1].id:
            # **Die äußere Stufe darf in eine gekrümmte Fläche münden** (RM-245):
            # An der unteren Schraubbohrung von ``pegboard-gs-100-v2.step`` läuft
            # die Zylindersenkung Ø 10 hinten in eine Rundung aus vier
            # BSpline-Flächen, ihr Rand streut 1 mm entlang der Achse, und jede
            # Kettenhandlung sagte am exakten Kern mit dem Satz des Einlaufs ab.
            planes = _curved_mouth_planes(mesh, entry, direction)
            curved = len(planes) == 2
        if len(planes) != 2 or entry.params.get("partial", False):
            raise _entrance_error()
        if any(abs(float(np.dot(plane.normal, direction))) <= EPS_GEOM for plane in planes):
            raise _entrance_error()
        ends = sorted(
            (
                (plane.position - float(np.dot(plane.normal, origin)))
                / float(np.dot(plane.normal, direction)),
                plane,
            )
            for plane in planes
        )
        (start, lower), (end, upper) = ends
        if end <= start + EPS_GEOM:
            raise _entrance_error()
        if float(np.dot(lower.normal, direction)) > 0.0:
            lower = lower.flipped()
        if float(np.dot(upper.normal, direction)) < 0.0:
            upper = upper.flipped()
        if sections and abs(start - sections[-1].end) > FLAT_RIM:
            raise _entrance_error()
        if entry.kind == "hole":
            inner = outer = float(entry.params["diameter"]) / 2.0
            if sections and inner < sections[-1].outer_radius - MAX_FACET_SAG:
                raise _entrance_error()
        elif entry.kind == "cone" and sections and sections[-1].feature.kind == "hole":
            angle = float(entry.params.get("angle", 0.0))
            if not EPS_GEOM < angle < 180.0 - EPS_GEOM:
                raise _entrance_error()
            inner = sections[-1].outer_radius
            slope = math.tan(math.radians(angle / 2.0))
            previous_indices = welded.faces[sections[-1].feature.face_indices, :]
            indices = welded.faces[entry.face_indices, :]
            shoulder = not bool(np.intersect1d(previous_indices, indices).size)
            if shoulder:
                # Eine vollständige Ringschulter ist eine echte radiale Stufe.
                # Ihre Kegelkante liegt nicht auf dem Radius des inneren Schafts.
                points = np.asarray(welded.vertices[np.unique(indices)]) - origin
                along = points @ direction
                radii = np.linalg.norm(points - np.outer(along, direction), axis=1)
                inner = float(np.max(radii - (along - start) * slope))
                if inner < sections[-1].outer_radius - MAX_FACET_SAG:
                    raise _entrance_error()
            outer = inner + (end - start) * slope
        else:
            raise _entrance_error()
        sections.append(
            _EntranceSection(entry, lower, upper, start, end, inner, outer, shoulder, curved)
        )
    return tuple(sections)


def _curved_mouth_planes(
    mesh: MeshData, feature: Feature, direction: NDArray[np.float64]
) -> tuple[SectionPlane, ...]:
    """Die Grenzen eines äußeren Zylinders, der in eine gekrümmte Fläche mündet —
    leer, wo er das nicht tut.

    Innen ist es sein ebener Ring, außen die Ebene quer zur Achse durch den
    weitesten Punkt seines Rands: bis dorthin reicht er, und bis dorthin
    reicht auch das Werkzeug des Netzkerns, das seine gemessene Tiefe nimmt
    (:func:`_stretched_section`). Der Rand muss eine **offene** Mündung sein —
    ein gekrümmter Boden wäre Material, das die Ebene abtrüge — und so eben,
    wie der Fächerdeckel des Netzkerns es zulässt (:data:`CURVED_RIM`,
    ``_body_from_faces``).
    """
    from app.core.perceive.relations import boundary_rings

    body = _welded(mesh)
    rings = boundary_rings(body, feature)
    if rings is None or len(rings) != 2:
        return ()
    points = np.asarray(body.vertices, dtype=np.float64)
    way = np.asarray(direction, dtype=np.float64)
    ends = [points[sorted({vertex for edge in ring for vertex in edge})] for ring in rings]
    ends.sort(key=lambda ring: units.dot3(units.exact_centre(ring.tolist()), way))
    inner, outer = ends
    hub, normal, spread = units.plane_fit(inner.tolist())
    if spread > FLAT_RIM * math.sqrt(len(inner)):
        return ()
    centre = np.asarray(units.exact_centre(outer.tolist()), dtype=np.float64)
    reach = max(math.dist(point, centre) for point in outer.tolist())
    _middle, _normal, bend = units.plane_fit(outer.tolist())
    if bend > max(FLAT_RIM, CURVED_RIM * 2.0 * reach) * math.sqrt(len(outer)):
        return ()
    if not _mouth_is_open(mesh, outer, way):
        return ()
    far = max(units.dot3(point, way) for point in outer.tolist())
    return (
        SectionPlane(
            normal=(normal[0] + 0.0, normal[1] + 0.0, normal[2] + 0.0),
            position=units.dot3(hub, normal),
        ),
        SectionPlane(
            normal=(float(way[0]) + 0.0, float(way[1]) + 0.0, float(way[2]) + 0.0),
            position=far,
        ),
    )


def _entrance_is_open(
    mesh: MeshData, origin: Vec3, direction: NDArray[np.float64], last: _EntranceSection
) -> bool:
    """Ob das äußere Ende der Kette eine Mündung ist — dieselbe Probe wie an den
    Deckeln des Flächenkörpers (`_mouth_is_open`): Luft vor dem ganzen Rand.

    Der Rand liegt **auf der Randebene**, nicht auf einem Kreis quer zur
    Achse: Eine Mündung in einer schrägen Fläche ist eine Ellipse, und ein
    Kegel wird zum Rand hin weiter. Je Umfangsrichtung schneidet die Mantel-
    linie die Ebene an genau einer Stelle.
    """
    from app.core.sketch.planes import frame_of

    frame = frame_of((float(direction[0]), float(direction[1]), float(direction[2])), origin)
    angles = np.linspace(0.0, 2.0 * math.pi, BORE_SECTIONS, endpoint=False)
    radial = np.outer(np.cos(angles), np.asarray(frame.x_axis, dtype=float)) + np.outer(
        np.sin(angles), np.asarray(frame.y_axis, dtype=float)
    )
    normal = np.asarray(last.upper.normal, dtype=float)
    normal /= np.linalg.norm(normal)
    anchor = np.asarray(origin, dtype=float)
    # Radius entlang der Achse: r(t) = a + b·t — beim Zylinder fest, beim
    # Kegel mit seiner Steigung.
    slope = 0.0
    if last.feature.kind == "cone" and last.end > last.start + EPS_GEOM:
        slope = (last.outer_radius - last.inner_radius) / (last.end - last.start)
    offset = last.outer_radius - slope * last.end
    along_normal = float(normal @ direction)
    radial_normal = radial @ normal
    denominator = along_normal + slope * radial_normal
    if np.any(np.abs(denominator) <= EPS_GEOM):
        return True
    t = (last.upper.position - float(normal @ anchor) - offset * radial_normal) / denominator
    rim = anchor + np.outer(t, direction) + radial * (offset + slope * t)[:, None]
    return _mouth_is_open(mesh, rim, normal)


def _entrance_tools(
    entrance: _BoreEntrance,
    diameter: float,
    reach: float,
    *,
    filling: bool = False,
    overlap: float = FEATURE_OVERLAP,
) -> list[tuple[list[tuple[float, float]], tuple[SectionPlane, ...]]]:
    """Beide Kerne erhalten dieselben Radien, Profile und Randebenen.

    Die Umrisse stehen in der Halbebene um ``entrance.axis``: Radius und Lage
    entlang der Achse ab ``entrance.origin``. Zuerst der Schaft, dann die
    Erweiterungen der ersten Seite, dann die der zweiten (RM-245). Deren
    Umrisse entstehen entlang ihrer eigenen Richtung und werden in die
    Halbebene der ersten gespiegelt — ein Drehkörper um dieselbe Achse; die
    Randebenen stehen ohnehin im Raum. ``overlap`` ist die Zugabe über offene
    Mündungen (§39, :func:`_exact_chain_cut_holding`).
    """
    delta = diameter / 2.0 - entrance.sections[0].inner_radius
    tools = _side_tools(
        entrance.sections,
        entrance.open,
        delta,
        reach,
        filling=filling,
        back=entrance.back,
        back_open=entrance.back_open,
        overlap=overlap,
    )
    if entrance.back:
        for outline, planes in _side_tools(
            entrance.back, entrance.back_open, delta, reach, filling=filling, overlap=overlap
        )[1:]:
            tools.append(([(radius, -along) for radius, along in reversed(outline)], planes))
    return tools


def _side_tools(
    sections: Sequence[_EntranceSection],
    open_end: bool,
    delta: float,
    reach: float,
    *,
    filling: bool,
    back: Sequence[_EntranceSection] = (),
    back_open: bool = True,
    overlap: float = FEATURE_OVERLAP,
) -> list[tuple[list[tuple[float, float]], tuple[SectionPlane, ...]]]:
    """Die Werkzeuge einer Seite in ihrer eigenen Halbebene: der Schaft zuerst,
    dann jede Erweiterung. Mit ``back`` reicht der Schaft bis an deren Mündung."""
    first, last = sections[0], sections[-1]
    # Der Schaft öffnet auch den Hals unter einer schräg beschnittenen Senkung.
    shaft = dataclasses.replace(first, upper=last.upper, end=last.end)
    if back:
        # **Und an beiden Enden** (RM-245): Seine untere Grenze ist die Mündung
        # der zweiten Seite, deren Ebene schon nach außen zeigt.
        shaft = dataclasses.replace(shaft, lower=back[-1].upper, start=-back[-1].end)
    members = [shaft, *sections[1:]]
    tools: list[tuple[list[tuple[float, float]], tuple[SectionPlane, ...]]] = []
    for index, section in enumerate(members):
        radius = section.inner_radius + delta
        lower = section.lower
        upper = section.upper
        if not filling and open_end and (index == 0 or index == len(members) - 1):
            upper = dataclasses.replace(upper, position=upper.position + overlap)
        if not filling and back and back_open and index == 0:
            lower = dataclasses.replace(lower, position=lower.position + overlap)
        if section.feature.kind == "cone":
            slope = (section.outer_radius - section.inner_radius) / (section.end - section.start)
            start = section.start - radius / slope
            end = section.end + reach
            outer = radius + (end - section.start) * slope
            outline = [(0.0, start), (outer, end), (0.0, end), (0.0, start)]
            # Der Kegel beginnt im vorherigen Zylinder. Dessen Boden begrenzt
            # ihn, während der gemeinsame kreisrunde Hals ohne Ringstufe bleibt.
            if not section.shoulder:
                lower = sections[index - 1].lower
        else:
            start, end = section.start - reach, section.end + reach
            outline = [(0.0, start), (radius, start), (radius, end), (0.0, end), (0.0, start)]
        if radius <= EPS_GEOM:
            raise _entrance_error()
        tools.append((outline, (lower, upper)))
    return tools


def _entrance_mesh_tool(
    entrance: _BoreEntrance, diameter: float, reach: float, ctx: OpContext
) -> BooleanOutcome:
    """Die gemeinsame Profilfolge mit der vorhandenen Netz-Rückfallkette schneiden."""
    from app.core.geom.section import cut
    from app.core.sketch.planes import frame_of

    frame = frame_of(entrance.axis, entrance.origin)
    rotation = np.asarray([frame.x_axis, frame.y_axis, frame.normal]).T
    tools = []
    for outline, planes in _entrance_tools(entrance, diameter, reach):
        ctx.cancelled.raise_if_cancelled()
        raw = lathe.revolve(outline, sections=BORE_SECTIONS)
        raw.vertices = np.asarray(raw.vertices) @ rotation.T + entrance.origin
        tool = MeshData.of(raw)
        for plane in planes:
            tool = cut(tool, plane).mesh
        if not tool.is_watertight or tool.volume <= EPS_GEOM:
            raise _entrance_error()
        tools.append(tool)
    return boolean("union", tools, quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled)


#: Befunde des Einlauf-Neuschnitts, die den **alten** Ort beschreiben —
#: Nachbarwand, Rand, Zerfall. Nach dem Versetzen steht dort Material, und für
#: die neue Stelle gilt eine eigene Messung (Review 22.09.2026: „dünne Wand"
#: gemeldet, wo die Bohrungen am neuen Ort ineinander übergingen).
PLACE_BOUND_FINDINGS: Final = frozenset(
    {
        "bore.neighbour_opened",
        "bore.neighbour_wall_thin",
        "bore.over_the_edge",
        "bore.splits_the_body",
    }
)


def bore_is_unchanged(
    feature: Feature, diameter: float, profile: Profile, compensate: bool
) -> bool:
    """Ob dieser Durchmesser die Bohrung so lässt, wie sie ist — die Frage,
    mit der *Bohrung ändern* absagt („hat bereits diesen Durchmesser").

    Gestellt wird sie nach der Toleranzkorrektur (``bore_diameter``) und mit
    der Geometrietoleranz, denn so entscheidet die Operation. Das Fenster
    fragt hier dieselbe Antwort ab, bevor es einen wartenden Langlochzug dem
    Übernehmen zurechnet: Bis zum 22.09.2026 verglich es den rohen Feldwert
    mit der Anzeigetoleranz, und mit eingeschalteter Korrektur sagte es
    „gleich", wo der Kern „anders" sagte (Review).
    """
    cut = bore_diameter(diameter, profile, compensate)
    return is_close(cut, _bore_number(feature, "diameter"))


def _moved_after_resizing(
    ctx: OpContext,
    resized: OpResult,
    feature: Feature,
    entrance: _BoreEntrance,
    centre: Vec3,
    measured: Vec3,
) -> OpResult:
    """Den neu geschnittenen Einlauf samt Kette an die genannte Stelle bringen.

    **Bis zum 22.09.2026 sagte *Bohrung ändern* hier ab** („Ändern Sie zuerst
    den Durchmesser mit Einlauf. Verschieben Sie das Merkmal danach über
    *Merkmal verschieben*") — und die Maßfelder im Bild luden zu genau dieser
    Bewegung ein: Wer an Roberts Schraubendreherhalter bei „Senkung und Stufen
    mitnehmen" ein Kantenmaß änderte, bekam keine Vorschau und keinen Grund.
    Ein Umweg, den die Oberfläche selbst anbietet, ist keine Absage wert.

    Der Weg ist die Reihenfolge, die der alte Satz dem Kunden zumutete, nur in
    einem Schritt: erst der Einlauf mit dem neuen Durchmesser an der alten
    Stelle, dann die ganze Hohlraumkette — Schaft und Senkung — über dieselbe
    Maschinerie wie *Merkmal verschieben* an die neue. Kennungen und Passungen
    reisen mit, die tiefste Stufe beider Läufe steht im Ergebnis (§17.2).

    Vier Dinge, die der erste Wurf nicht tat (Review 22.09.2026):

    - **Die Bewegung ist die Differenz zur alten Mitte.** Der Neuschnitt misst
      die Bohrung neu, und an einer schrägen Mündung wandert ihre Mitte axial;
      wer die genannten Zahlen als Ziel nähme, schöbe die Kette um diese
      Wanderung mit — 0,245 mm an der schrägen Senkbohrung, ungefragt.
    - **Die ganze Kette muss wiedererkannt sein**, sonst versetzte der zweite
      Schritt den Schaft allein oder gar nichts, und die genannte Stelle
      wäre still verworfen (Regel 21).
    - **Befunde über den alten Ort fallen**, die Nachbarwand wird am neuen
      gemessen — wie beim Versetzen ohne Einlauf.
    - **Der Übergang reist mit** (§21.2): Der exakte Kern belegt beim
      Versetzen, dass ``hole_1`` und ``cone_1`` weiterleben; ohne diesen
      Beleg hielt der nächste Schritt, der die Bohrung braucht, die Kette an.
    """
    body = resized.outputs[0]
    missing = [entry.id for entry in entrance.chain if entry.id not in body.features]
    if missing:
        raise GeometryError(
            title=_("Die Bohrung ließ sich nach dem Ändern nicht versetzen."),
            detail=_(
                "Nach dem Neuschnitt des Einlaufs wurde die Hohlraumkette nicht "
                "vollständig wiedererkannt. Ändern Sie den Durchmesser ohne Stelle "
                "und versetzen Sie danach mit „Merkmal verschieben“."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
            values={"missing": missing},
        )
    travel = np.asarray(centre, dtype=float) - np.asarray(measured, dtype=float)
    now = np.asarray(body.features[feature.id].params["centre"], dtype=float) + travel
    inner = dataclasses.replace(
        ctx,
        inputs=[body],
        params=cast(Any, MoveFeatureParams)(
            at_feature=feature.id, x=float(now[0]), y=float(now[1]), z=float(now[2])
        ),
        # Der Neuschnitt meldet keinen Fortschritt; der zweite Schritt füllt
        # die zweite Hälfte statt bei einem Zehntel neu anzufangen.
        progress=lambda fraction, text: ctx.progress(0.5 + fraction / 2.0, text),
    )
    moved = move_feature(inner)
    result = moved.outputs[0]
    findings = [entry for entry in resized.findings if entry.code not in PLACE_BOUND_FINDINGS]
    findings.extend(moved.findings)
    source = ctx.inputs[0]
    cavity = _paired_cavity_body(
        as_mesh_data(body.mesh), *(body.features[entry.id] for entry in entrance.chain)
    )
    if cavity is not None:
        shifted = cavity.raw.copy()
        shifted.apply_translation(travel)
        findings.extend(
            _neighbour_bore_findings(source, feature, MeshData.of(shifted), ctx, moved=True)
        )
    findings.extend(split_findings(as_mesh_data(source.mesh), as_mesh_data(result.mesh)))
    return OpResult(
        outputs=moved.outputs,
        solver=deepest((resized.solver, moved.solver)),
        findings=findings,
        # Nur der Neuschnitt könnte gefragt haben; eine Antwort des inneren
        # Schritts hieße einen Parameter von *Merkmal verschieben* und gehört
        # nicht in den Stapel von *Bohrung ändern* (§15.7).
        answered=dict(resized.answered),
        feature_continuations=_continued_through(source, resized, moved),
    )


def _continued_through(
    source: SceneObject, first: OpResult, second: OpResult
) -> tuple[tuple[FeatureContinuation, ...], ...]:
    """Die belegten Übergänge zweier Schritte hintereinander, als einer.

    Was der erste Schritt belegt, wird über den zweiten weitergeführt; was
    nur der zweite belegt, gilt für Merkmale, die schon am Eingang standen —
    die Auswertung kennt nur diese (``_checked_continuations``). Belegt keiner
    etwas, bleibt es leer: Der Netzkern stellt keine Übergänge aus.
    """
    known = source.features
    final = second.outputs[0].features
    onward = {
        entry.source.feature_id: entry.target
        for entries in second.feature_continuations
        for entry in entries
    }
    continued: list[FeatureContinuation] = []
    sources: set[FeatureId] = set()
    targets: set[FeatureId] = set()
    for entries in first.feature_continuations:
        for entry in entries:
            old_id = entry.source.feature_id
            target = onward.get(entry.target, entry.target)
            if old_id in known and target in final and target not in targets:
                continued.append(FeatureContinuation(FeatureRef(source.id, old_id), target))
                sources.add(old_id)
                targets.add(target)
    for old_id, new_id in onward.items():
        if old_id in known and old_id not in sources and new_id in final and new_id not in targets:
            continued.append(FeatureContinuation(FeatureRef(source.id, old_id), new_id))
            sources.add(old_id)
            targets.add(new_id)
    if not continued:
        return ()
    return (tuple(continued),)


def _resize_bore_entrance(
    ctx: OpContext, feature: Feature, entrance: _BoreEntrance, diameter: float
) -> OpResult:
    """Schaft und nach außen eindeutigen Einlauf als eine Änderung neu schneiden."""
    source = ctx.inputs[0]
    original = as_mesh_data(source.mesh)
    reach = original.bounds.diagonal
    ctx.cancelled.raise_if_cancelled()
    stages: list[SolverInfo | None] = []
    findings: list[Finding] = []
    delta = diameter - float(feature.params["diameter"])
    targets: dict[FeatureId, Feature] = {}
    found: Mapping[FeatureId, Feature]
    # Je Seite entlang ihrer eigenen Richtung (RM-245); die Bohrung steht in
    # jeder vorn und wird einmal gezählt.
    for number, (way, sections, _open) in enumerate(entrance.sides()):
        for section in sections[1:] if number else sections:
            old = section.feature
            height = (section.start + section.end) / 2.0 if old.kind == "hole" else section.end
            outer_radius = section.outer_radius + delta / 2.0
            if old.kind == "cone":
                # Der Erkenner beschreibt einen schräg begrenzten Kegel am
                # weitesten Rand, nicht am Achsenschnitt seiner Mündungsebene.
                # Beide Stellen liegen auf derselben analytischen Kegelfläche.
                normal = np.asarray(section.upper.normal)
                axis = np.asarray(way)
                tilt = float(np.linalg.norm(np.cross(normal, axis)))
                slope = math.tan(math.radians(float(old.params["angle"]) / 2.0))
                denominator = float(normal @ axis) - tilt * slope
                if denominator <= EPS_GEOM:
                    raise _entrance_error()
                shift = tilt * outer_radius / denominator
                height += shift
                outer_radius += shift * slope
            centre = np.asarray(entrance.origin) + height * np.asarray(way)
            targets[old.id] = dataclasses.replace(
                old,
                params={
                    **old.params,
                    "axis": way,
                    "centre": tuple(float(v) for v in centre),
                    "diameter": outer_radius * 2.0,
                },
            )
    if source.kind == "brep":
        from app.core.brep import edit
        from app.core.brep.features import features_of
        from app.core.brep.kernel import Solid
        from app.core.sketch.planes import frame_of

        if not isinstance(source.mesh, Solid):
            raise InternalError(detail="a scene object marked as brep does not carry a Solid")
        frame = frame_of(entrance.axis, entrance.origin)
        exact_tools = [
            edit.clipped_bore_tool(edit.revolved_bore_tool(outline, frame), planes)
            for outline, planes in _entrance_tools(entrance, diameter, reach)
        ]
        tool_solid = edit.boolean("union", exact_tools)
        filled_body = _exact_chain_filled(source, entrance)
        exact_changed = edit.boolean("difference", [filled_body, tool_solid])
        if not exact_changed.is_closed:
            raise GeometryError(detail=OPEN_BODY_DETAIL, suggestions=(CORRECT_INPUT, CANCEL))
        changed: Mesh = exact_changed
        found = features_of(exact_changed, cancelled=ctx.cancelled)
        tool = as_mesh_data(tool_solid)
        before_cut = as_mesh_data(filled_body)
    else:
        tool_outcome = _entrance_mesh_tool(entrance, diameter, reach, ctx)
        tool = tool_outcome.mesh
        # Ein kurzer Senkungsabschnitt allein enthält nicht den Abschluss
        # seines langen Schafts. Das bereits vollständig konstruierte und
        # an den echten Mündungen begrenzte Werkzeug belegt den gemeinsamen
        # Suchumfang. Eine beliebige Sammlung alter Merkmale tut das nicht.
        points = np.asarray(tool.raw.vertices)
        targets = {
            name: dataclasses.replace(
                target,
                params={
                    **target.params,
                    "local_search_radius": max(
                        float(target.params.get("local_search_radius") or 0.0),
                        float(
                            np.linalg.norm(
                                points - np.asarray(target.params["centre"]), axis=1
                            ).max()
                        ),
                    ),
                },
            )
            for name, target in targets.items()
        }
        plug = _cavity_plug(
            original, entrance.chain, quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled
        )
        if plug is None:
            raise _entrance_error()
        filled_mesh = boolean(
            "union", [original, plug], quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled
        )
        cut_mesh = boolean(
            "difference",
            [filled_mesh.mesh, tool],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        changed = cut_mesh.mesh
        before_cut = filled_mesh.mesh
        stages.extend((tool_outcome.solver, filled_mesh.solver, cut_mesh.solver))
        findings.extend((*tool_outcome.findings, *filled_mesh.findings, *cut_mesh.findings))
        found = _detect_resized_bores(
            cut_mesh.mesh, targets, check_cancelled=ctx.cancelled.raise_if_cancelled
        )
    # Jeder Abschnitt wird an der neuen echten Geometrie wiedergefunden.
    # Die Bohrungsmitte darf durch eine schräge Mündung axial wandern.
    changed_ids = {entry.id for entry in entrance.chain}
    preserved = {
        name: entry
        for name, entry in _without_old_triangles(source.features).items()
        if entry.provenance == "generated" and name not in changed_ids
    }
    for target in targets.values():
        expected = float(target.params["diameter"])
        recognised = _recognised_resized_feature(
            as_mesh_data(changed),
            target,
            expected,
            original=original,
            known=found,
            check_cancelled=ctx.cancelled.raise_if_cancelled,
        )
        if recognised is not None:
            solver = deepest(stages)
            if solver is None or solver.strategy in ("direct", "welded"):
                recognised = _with_nominal_bore(as_mesh_data(changed), recognised, target, expected)
            preserved[target.id] = dataclasses.replace(recognised, id=target.id)
            preserved.update(
                _resized_bore_floor(
                    original,
                    source.features[target.id],
                    source.features,
                    as_mesh_data(changed),
                    recognised,
                    found,
                    check_cancelled=ctx.cancelled.raise_if_cancelled,
                )
            )
        elif target.id == feature.id:
            findings.append(_bore_no_longer_a_feature(feature, diameter))
    findings.extend(_neighbour_bore_findings(source, feature, tool, ctx))
    findings.extend(_entrance_edge_findings(before_cut, entrance, diameter))
    findings.extend(split_findings(original, as_mesh_data(changed)))
    params = cast(ResizeHoleParams, ctx.params)
    findings.extend(compensation_findings(params.diameter, diameter, params.compensate))
    if source.kind == "brep":
        preserved = _exact_rest_carried(
            source.features, found, preserved, changed_ids, as_mesh_data(changed)
        )
    # Der Beleg für die bewusst geänderten Abschnitte reist mit dem Ergebnis
    # (§21.2) — wie beim Ändern ohne Einlauf. Ohne ihn hielt am exakten Körper
    # der nächste Schritt, der die Bohrung braucht, die Kette an
    # (``NativeReferenceLost``, Review 22.09.2026). Am Netz belegt die
    # Zuordnung die Kennungen selbst.
    continued = (
        tuple(
            FeatureContinuation(FeatureRef(source.id, name), name)
            for name in targets
            if name in preserved and name in source.features
        )
        if source.kind == "brep"
        else ()
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=changed, features=preserved)],
        findings=findings,
        solver=deepest(stages),
        feature_continuations=(continued,) if continued else (),
    )


def _exact_rest_carried(
    previous: Mapping[FeatureId, Feature],
    detected: Mapping[FeatureId, Feature],
    kept: Mapping[FeatureId, Feature],
    changed_ids: set[FeatureId],
    body: MeshData,
) -> dict[FeatureId, Feature]:
    """Die Merkmale des exakten Körpers, die der Einlauf-Neuschnitt nicht
    berührt hat — Flächen, Kanten, Verrundungen —, unter ihren alten Namen.

    ``_resize_bore_entrance`` baut den exakten Körper neu und behielt nur die
    erzeugten Merkmale und die wiedererkannte Kette: Die sechs Flächen einer
    Platte waren nach *Bohrung ändern* mit Einlauf aus dem Objektbaum
    verschwunden, und mit Stelle kamen sie über *Merkmal verschieben* zurück
    — zwei Fassungen desselben Schritts, zwei Merkmalskarten (Review
    22.09.2026, A2). Der Weg ohne Einlauf ordnet die frische Topologie zu
    (``_preserved_exact_features``); hier dasselbe für alles, was nicht auf
    den Dreiecken der Kette liegt.
    """
    from app.core.perceive.matching import apply_mapping, match

    covered = {index for entry in kept.values() for index in entry.face_indices}
    rest = {
        name: entry
        for name, entry in detected.items()
        if not covered.intersection(entry.face_indices)
    }
    if not rest:
        return dict(kept)
    known = {
        name: entry
        for name, entry in previous.items()
        if name not in changed_ids and name not in kept and entry.provenance == "detected"
    }
    matched = match(known, rest, body.bounds.centre, body.bounds.diagonal)
    merged = dict(kept)
    for name, entry in apply_mapping(rest, matched, previous=known).items():
        target = name
        number = 1
        while target in merged:
            target = FeatureId(f"{entry.kind}_{number}")
            number += 1
        merged[target] = dataclasses.replace(entry, id=target)
    return merged


def _entrance_edge_findings(
    body: MeshData, entrance: _BoreEntrance, diameter: float
) -> list[Finding]:
    """Die belegten Abschnittsenden prüfen, nicht Austritte aus der Gesamthülle.

    Ein höherer Nachbarkörper macht aus einer kurzen schrägen Sackbohrung
    keinen Durchgang bis zu seiner Oberkante. Die tatsächlichen Randebenen
    begrenzen hier bereits alle Profile und damit auch die Flankenprüfung.
    """
    delta = diameter / 2.0 - entrance.sections[0].inner_radius
    for way, sections, _open in entrance.sides():
        axis = np.asarray(way)
        for section in sections:
            for height, radius, sign in (
                (section.start, section.inner_radius, 1.0),
                (section.end, section.outer_radius, -1.0),
            ):
                centre = np.asarray(entrance.origin) + height * axis
                found = mouth_over_the_edge(
                    body,
                    cast(Vec3, tuple(float(v) for v in centre)),
                    cast(Vec3, tuple(float(v) for v in sign * axis)),
                    (radius + delta) * 2.0,
                )
                if found:
                    return found
    return []


def _cavity_floor(
    mesh: MeshData,
    bore: Feature,
    features: Mapping[FeatureId, Feature],
    check_cancelled: Callable[[], None] | None,
    *,
    combine: bool = False,
) -> Feature | None:
    """Genau eine ebene Scheibe schließt einen ganzen echten Wandrand.

    Ringförmige Schultern, Außenflächen mit Loch und getrennte gleich hohe
    Böden besitzen diesen gemeinsamen Einzelrand nicht. Ihre Nähe oder
    Flächengröße belegt deshalb keine Zugehörigkeit.
    """
    from app.core.perceive.features import _one_body
    from app.core.perceive.relations import boundary_rings, cavity_surface_indices

    if (
        bore.kind not in ("hole", "cone")
        or not is_a_cavity(bore)
        or not bore.recognised
        or not bore.face_indices
    ):
        return None
    if check_cancelled is not None:
        check_cancelled()
    body = _one_body(mesh).raw
    indices = cavity_surface_indices(mesh, (bore,))
    rings = boundary_rings(body, dataclasses.replace(bore, face_indices=indices))
    if not rings or len(rings) != 2:
        return None
    wall = set(indices)
    candidates = []
    for feature in features.values():
        if check_cancelled is not None:
            check_cancelled()
        if (
            feature.kind != "face"
            or not feature.recognised
            or not feature.face_indices
            or not wall.isdisjoint(feature.face_indices)
        ):
            continue
        edges = boundary_rings(body, feature)
        if edges is not None and len(edges) == 1 and edges[0] in rings:
            candidates.append(feature)
    if candidates or not combine:
        return candidates[0] if len(candidates) == 1 else None
    # Ein exakter Schnitt darf die Bodenebene in Scheibe und Ring teilen.
    # Nur eine vollständig belegte, zusammenhängende planare Facette mit
    # genau dem ganzen Wandrand darf diese neuen Teilflächen zusammenfassen.
    for facet in body.facets:
        if check_cancelled is not None:
            check_cancelled()
        patch = {int(index) for index in facet}
        if not wall.isdisjoint(patch):
            continue
        joined = dataclasses.replace(bore, face_indices=tuple(sorted(patch)))
        edges = boundary_rings(body, joined)
        if edges is None or len(edges) != 1 or edges[0] not in rings:
            continue
        parts = [
            feature
            for feature in features.values()
            if feature.kind == "face"
            and feature.recognised
            and feature.face_indices
            and set(feature.face_indices) <= patch
        ]
        if (
            len(parts) < 2
            or sum(len(part.face_indices) for part in parts) != len(patch)
            or {index for part in parts for index in part.face_indices} != patch
        ):
            continue
        area = sum(float(part.params["area"]) for part in parts)
        if area <= EPS_GEOM:
            continue
        centre = (
            sum(
                (np.asarray(part.params["centre"]) * float(part.params["area"]) for part in parts),
                start=np.zeros(3),
            )
            / area
        )
        candidates.append(
            dataclasses.replace(
                parts[0],
                face_indices=joined.face_indices,
                surface_patches=tuple(
                    surface for part in parts for surface in part.surface_patches
                ),
                params={
                    **parts[0].params,
                    "area": area,
                    "centre": tuple(float(value) for value in centre),
                },
            )
        )
    return candidates[0] if len(candidates) == 1 else None


def _floor_carried(
    mesh: Mesh,
    bore: Feature,
    features: Mapping[FeatureId, Feature],
    motion: NDArray[np.float64],
) -> Feature | None:
    """Der Sackboden einer versetzten oder gedrehten Bohrung, an seinem neuen Ort erwartet.

    **Der Boden ist eine eigene Fläche mit eigener Kennung** — eine Skizze
    oder eine Passung kann auf ihm stehen. Beim Ändern des Durchmessers führt
    ihn :func:`_resized_bore_floor` fort; beim Versetzen und Drehen reiste er
    nicht mit (gemessen 23.09.2026 an einer Senkbohrung mit Sackboden: Netz
    ``face_7`` → ``face_8`` mit ``perceive.orphaned``, exakter Körper still
    ``face_8``). Die Operation kennt die Bewegung (``motion``, 4 x 4) und sagt
    der Zuordnung, wo er jetzt liegt — wie für Bohrung und Senkung selbst.
    """
    floor = _cavity_floor(as_mesh_data(mesh), bore, features, None)
    if floor is None:
        return None
    params = dict(floor.params)
    turn, shift = motion[:3, :3], motion[:3, 3]
    centre = turn @ np.asarray(params["centre"], dtype=np.float64) + shift
    params["centre"] = (float(centre[0]), float(centre[1]), float(centre[2]))
    if isinstance(params.get("normal"), tuple | list):
        normal = turn @ np.asarray(params["normal"], dtype=np.float64)
        params["normal"] = (float(normal[0]), float(normal[1]), float(normal[2]))
    return dataclasses.replace(
        floor, params=params, provenance="generated", face_indices=(), surface_patches=()
    )


def _resized_bore_floor(
    original: MeshData,
    before: Feature,
    previous: Mapping[FeatureId, Feature],
    changed: MeshData,
    after: Feature,
    detected: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
    shift: Vec3 = (0.0, 0.0, 0.0),
) -> dict[FeatureId, Feature]:
    """Den belegten Sackboden mit neuen Maßen unter seiner alten Kennung führen.

    Eine bewusste Durchmesseränderung ändert dessen Fläche quadratisch. Die
    allgemeine Zuordnung soll größere Flächensprünge weiterhin ablehnen;
    hier belegen gemeinsame Vollränder und dieselbe reale Ebene die Absicht.

    ``shift`` ist die bewusste Verschiebung des Bodens entlang der Achse —
    eine neue Tiefe (23.09.2026). Dann liegt der neue Boden auf der um genau
    diesen Weg verschobenen Ebene, und nur dort.
    """
    from app.core.units import weld_tolerance

    old = _cavity_floor(original, before, previous, check_cancelled)
    if old is None:
        return {}
    new = _cavity_floor(changed, after, detected, check_cancelled, combine=True)
    if new is None:
        return {}
    old_indices, new_indices = list(old.face_indices), list(new.face_indices)
    old_points = np.asarray(original.raw.vertices)[original.raw.faces[old_indices]].reshape(-1, 3)
    new_points = np.asarray(changed.raw.vertices)[changed.raw.faces[new_indices]].reshape(-1, 3)
    normal = np.asarray(original.raw.face_normals)[old_indices[0]]
    new_normals = np.asarray(changed.raw.face_normals)[new_indices]
    tolerance = weld_tolerance(max(original.bounds.diagonal, changed.bounds.diagonal))
    origin = old_points[0]
    moved_origin = origin + np.asarray(shift, dtype=np.float64)
    if (
        float(np.linalg.norm(normal)) <= EPS_GEOM
        or not np.all(np.abs((old_points - origin) @ normal) <= tolerance)
        or not np.all(np.abs((new_points - moved_origin) @ normal) <= tolerance)
        or not np.all(new_normals @ normal > 0.0)
    ):
        return {}
    return {
        old.id: dataclasses.replace(
            new, id=old.id, provenance="generated", created_by=old.created_by
        )
    }


def _bore_end_planes(
    mesh: MeshData,
    feature: Feature,
    features: Mapping[FeatureId, Feature],
    *,
    grows: bool,
) -> tuple[SectionPlane, ...]:
    """Die echten Endringe begrenzen das Werkzeug bis zur äußeren Mündung.

    ``grows`` bestimmt den Umfang des abziehenden Werkzeugs: durch die weiteren
    Senkungsabschnitte bis zum äußeren Rand. Das gilt auch für den Neuschnitt
    nach dem Verschließen einer zu verkleinernden Bohrung. Ein Füllring darf
    nur die bisherigen Abschnittsgrenzen verwenden. Eine Luftprobe verlängert
    ausschließlich offene Mündungen; Böden und Schultern bleiben.
    """
    return tuple(rim.plane for rim in _bore_end_rims(mesh, feature, features, grows=grows))


@dataclasses.dataclass(frozen=True, slots=True)
class _Rim:
    """Ein Endring eines Hohlraums: seine Ebene, ob davor Luft liegt, seine Punkte."""

    plane: SectionPlane
    open: bool
    points: NDArray[np.float64]


def _bore_end_rims(
    mesh: MeshData,
    feature: Feature,
    features: Mapping[FeatureId, Feature],
    *,
    grows: bool,
) -> tuple[_Rim, ...]:
    """Die Endringe aus :func:`_bore_end_planes`, je mit Luftprobe und Punkten —
    leer, wo die Ränder keine zwei flachen Ringe sind.

    Die Luftprobe läuft nur mit ``grows``; ohne gilt jeder Ring als geschlossen.
    **Ein Kegel darf einen einzigen Ring haben**: Eine spitze Senkung ohne
    Bohrung läuft in ihre Spitze, und ihr Ring ist die Mündung am weiten Ende.
    Ohne ihn blieb ihr gekipptes Werkzeug ungekappt und schnitt 82 mm³ aus einer
    Rippe vor der Fläche (RM-220, 25.09.2026).
    """
    from app.core.perceive.relations import (
        boundary_rings,
        cavity_chain_at,
        cavity_sides,
        cavity_surface_indices,
    )

    scope: tuple[Feature, ...] = (feature,)
    chain = cavity_chain_at(feature, features, mesh) if grows else None
    if chain is not None and chain[0].id == feature.id:
        scope = chain
    elif chain is not None:
        # Von einer Erweiterung aus reicht der Umfang bis zur Mündung **ihrer**
        # Seite; die andere Seite einer beidseitig geweiteten Bohrung hat ihre
        # eigene (``relations.cavity_sides``, RM-245).
        for side in cavity_sides(chain):
            names = [section.id for section in side]
            if feature.id in names:
                scope = side[names.index(feature.id) :]
    indices = cavity_surface_indices(mesh, scope) if grows else feature.face_indices
    # Auch unverschweißte STL-Dreiecke teilen geometrisch dieselben Ränder.
    # Verschweißen ändert hier weder Flächenreihenfolge noch Eingangsmodell.
    body = _welded(mesh)
    rings = boundary_rings(body, dataclasses.replace(feature, face_indices=tuple(indices)))
    if rings is None or not (len(rings) == 2 or (len(rings) == 1 and feature.kind == "cone")):
        return ()
    points = np.asarray(body.vertices, dtype=np.float64)
    ends = [points[sorted({vertex for edge in ring for vertex in edge})] for ring in rings]
    axis = _feature_direction(feature)
    ends.sort(key=lambda ring: units.dot3(units.exact_centre(ring.tolist()), axis))
    found: list[_Rim] = []
    # Der einzelne Ring eines Kegels ist das äußere Ende, wie der zweite von zweien.
    for index, edge in enumerate(ends, start=2 - len(ends)):
        # **Die Ebene eines Rands ohne LAPACK** (RM-187, 22.09.2026). Hier
        # stand ``np.linalg.svd``, und ihre letzte Stelle entschied über jede
        # Ecke des Werkzeugs: Accelerate auf dem Mac und OpenBLAS auf Windows
        # und Linux runden verschieden, und das geänderte Netz des
        # Änderungswegs trug auf jeder Plattform einen anderen Fingerabdruck.
        # Dieselbe Frage beantwortet ``units.plane_fit`` in Grundrechenarten,
        # und das Skalarprodukt geht nicht durch BLAS.
        hub, normal, spread = units.plane_fit(edge.tolist())
        if spread > FLAT_RIM * math.sqrt(len(edge)):
            return ()
        along = units.dot3(normal, axis)
        if along * (1.0 if index else -1.0) < 0.0:
            normal, along = (-normal[0], -normal[1], -normal[2]), -along
        if abs(along) <= EPS_GEOM:
            return ()
        opened = grows and _mouth_is_open(mesh, edge, np.asarray(normal))
        overlap = FEATURE_OVERLAP if opened else 0.0
        found.append(
            _Rim(
                SectionPlane(
                    normal=(normal[0] + 0.0, normal[1] + 0.0, normal[2] + 0.0),
                    position=units.dot3(hub, normal) + overlap,
                ),
                opened,
                edge,
            )
        )
    return tuple(found)


def _mouth_covered(
    op: str,
    before: MeshData,
    after: MeshData,
    feature: Feature,
    features: Mapping[FeatureId, Feature],
    travel: NDArray[np.float64],
    findings: Sequence[Finding],
) -> list[Finding]:
    """Ob eine Mündung, die vorher offen war, an der neuen Stelle unter Material liegt.

    **Versetzt wird starr** — so ist es entschieden, und eine Bohrung, die
    danach nicht mehr durchgeht, sagt es (``no_longer_through``). Eine
    Sackbohrung und eine gesenkte Sackbohrung sagten nichts: An einer
    schrägen Außenfläche (z = 18 + 0,08·x) um 3 mm quer versetzt, lag die
    Mündung der Senkung 0,24 mm unter der Fläche, zugedeckt von einer Haut aus
    Material — eine Druckschicht, und die Senkung war von außen zu (RM-220,
    25.09.2026). Gefragt wird mit derselben Luftprobe wie an der alten Stelle
    (:func:`_share_in_material`), am Ring der alten Mündung, um ``travel``
    verschoben. Wo schon ``no_longer_through`` steht, ist das gesagt.

    **Zugedeckt heißt: vor mindestens der Hälfte des Rands Material**
    (:data:`COVERED_SHARE`). Eine Haut liegt vor dem ganzen Ring; eine einzelne
    Probe an einer Kante antwortet dagegen mit dem Vorzeichen der falschen
    Fläche — an einer Furnierplatte meldete eine glatt durchgeschnittene Kopie
    so „unter Material", weil einer von 32 Punkten daneben lag.
    """
    if any(finding.code == f"{op}.no_longer_through" for finding in findings):
        return []
    for rim in _bore_end_rims(before, feature, features, grows=True):
        if not rim.open:
            continue
        normal = np.asarray(rim.plane.normal, dtype=np.float64)
        moved = rim.points + _seated(travel, normal)
        if _share_in_material(after, moved, normal) < COVERED_SHARE:
            continue
        return [
            Finding(
                code=f"{op}.mouth_covered",
                severity="warning",
                message=_(
                    "An der neuen Stelle liegt die Mündung unter Material — von außen "
                    "ist die Bohrung zu. Legen Sie die Stelle auf die Fläche, von der "
                    "sie ausgeht."
                ),
                feature_ids=(feature.id,),
                # Der Satz nennt die Handlung, und sie steht als Knopf daneben
                # (Regel 17): Der Schritt geht wieder auf, und die Stelle wird
                # neu gewählt.
                suggestions=(CORRECT_INPUT,),
            )
        ]
    return []


def _moved_rims(
    mesh: MeshData,
    feature: Feature,
    features: Mapping[FeatureId, Feature],
    travel: NDArray[np.float64],
) -> tuple[SectionPlane, ...]:
    """Die Randebenen eines Hohlraums, starr um ``travel`` mitbewegt — mit der
    Zugabe aus §39 an offenen Mündungen, leer, wo die Ränder nicht flach sind."""
    moved = []
    for plane in _bore_end_planes(mesh, feature, features, grows=True):
        normal = np.asarray(plane.normal, dtype=np.float64)
        shift = _seated(travel, normal)
        moved.append(
            dataclasses.replace(plane, position=plane.position + units.dot3(normal, shift))
        )
    return tuple(moved)


def _seated(travel: NDArray[np.float64], normal: NDArray[np.float64]) -> NDArray[np.float64]:
    """Die Bewegung einer Mündung mit Normale ``normal`` — ohne ein Einrücken ins
    Material, das kleiner ist als die Messgenauigkeit ihrer Mitte.

    Die Mitte einer Bohrung ist gemessen, am exakten Körper an seinem
    Netz-Zwilling: An einer um 17,5° gekippten Durchgangsbohrung durch eine
    10-mm-Platte lag sie bei z = 4,9576, und wer sie auf z = 5 versetzte, rückte
    die untere Mündung um 0,042 mm ins Material — starr genommen eine Haut von
    0,022 mm über der ganzen Mündung, 0,66 mm³, und eine Bohrung, die nicht
    mehr durchging (RM-220, 25.09.2026). Bis zur Facettengrenze
    (:data:`~app.core.units.MAX_FACET_SAG`) ist das Messrauschen und keine
    Bewegung entlang der Achse; darüber gilt die starre Bewegung, und der
    Befund sagt es.
    """
    unit = np.asarray(normal, dtype=np.float64)
    shift = units.dot3(unit, travel)
    if -MAX_FACET_SAG <= shift < 0.0:
        return np.asarray(travel, dtype=np.float64) - unit * shift
    return np.asarray(travel, dtype=np.float64)


def _mesh_bore_depth(
    mesh: MeshData,
    feature: Feature,
    axis: tuple[float, float, float],
    fallback: float,
) -> float:
    """Liest die volle Zylinderlänge aus den gewählten Wanddreiecken.

    Die Merkmalswerte sind für Auswahl und Anzeige stabil quantisiert. Für
    das Werkzeug zählt dagegen jeder vorhandene Eckpunkt: Ein um wenige
    Zehntausendstel verkürzter Ring kann ein Sackloch bei der nächsten
    Erkennung fälschlich als durchgehend erscheinen lassen.
    """
    span = _mesh_bore_span(mesh, feature, axis)
    return span[1] - span[0] if span is not None else fallback


def _mesh_bore_span(mesh: MeshData, feature: Feature, axis: Vec3) -> tuple[float, float] | None:
    """Die beiden axialen Grenzen einer tatsächlich belegten Merkmalsfläche."""
    raw = mesh.raw
    valid = [index for index in feature.face_indices if 0 <= index < len(raw.faces)]
    length = math.sqrt(sum(value * value for value in axis))
    if not valid or length <= EPS_GEOM:
        return None
    unit = tuple(value / length for value in axis)
    vertices = raw.vertices[raw.faces[valid].reshape(-1)]
    along = vertices[:, 0] * unit[0] + vertices[:, 1] * unit[1] + vertices[:, 2] * unit[2]
    lower, upper = float(along.min()), float(along.max())
    return (lower, upper) if math.isfinite(upper - lower) and upper - lower > EPS_GEOM else None


def _unchanged_bore(diameter: float, *, with_depth: bool = False) -> Finding:
    """Die gemeinsame Auskunft für Netz und exakten Körper."""
    return Finding(
        code="bore.resize_unchanged",
        severity="info",
        message=(
            _("Die Bohrung hat bereits diesen Durchmesser und diese Tiefe.")
            if with_depth
            else _("Die Bohrung hat bereits diesen Durchmesser.")
        ),
        values={"diameter": format_length(diameter)},
    )


def _expected_bore(feature: Feature, diameter: float) -> Feature:
    """Das alte Merkmal mit dem einen Maß, das diese Operation bewusst ändert."""
    return dataclasses.replace(
        feature,
        params={**feature.params, "diameter": diameter},
    )


def _through_bore_depth(body: Mesh, centre: Vec3, axis: Vec3) -> float:
    """Ein symmetrischer Schneidkörper, der die gesamte Zielhülle durchdringt."""
    unit = np.asarray(axis, dtype=float)
    unit /= np.linalg.norm(unit)
    bounds = body.bounds
    offset = abs(float((np.asarray(bounds.centre) - centre) @ unit))
    half_span = float(np.asarray(bounds.size) @ np.abs(unit)) / 2.0
    return 2.0 * (offset + half_span + BOOLEAN_OVERLAP)


def _bore_match_id(
    detected: Mapping[str, Feature],
    expected: Feature,
    body_centre: Vec3,
    diagonal: float,
    *,
    check_cancelled: Callable[[], None] | None = None,
    mouth: bool = False,
) -> str | None:
    """Vergleicht Durchgänge entlang ihrer Achse, Sacklöcher an ihrer Mitte —
    und den äußeren Zylinder einer Kette wie einen Durchgang (``mouth``,
    :func:`_free_along_the_axis`)."""
    from app.core.perceive.matching import match

    opened = [
        name
        for name, candidate in detected.items()
        if candidate.params.get("open")
        and _sits_at(candidate, expected, diagonal, mouth=mouth)
        and abs(_bore_number(candidate, "diameter") - _bore_number(expected, "diameter"))
        <= max(FEATURE_OVERLAP, _bore_number(expected, "diameter") * _SAME_LENGTH)
    ]
    if len(opened) == 1:
        return opened[0]
    candidates: dict[str, Feature] = {}
    for name, candidate in detected.items():
        if candidate.kind != expected.kind or not _sits_at(
            candidate, expected, diagonal, mouth=mouth
        ):
            continue
        # Eine dickere Zielwand verschiebt die Mitte entlang derselben Achse.
        # Nur für Durchgänge ist diese Koordinate frei (:func:`_free_along_the_axis`);
        # Nachbarlöcher und voneinander getrennte Sacklöcher bleiben unterscheidbar.
        if _free_along_the_axis(candidate, expected, mouth=mouth):
            axis = np.asarray(_bore_vector(expected, "axis"), dtype=float)
            axis /= np.linalg.norm(axis)
            centre = np.asarray(_bore_vector(candidate, "centre"), dtype=float)
            offset = float((centre - _bore_vector(expected, "centre")) @ axis)
            candidate = dataclasses.replace(
                candidate,
                params={
                    **candidate.params,
                    "centre": tuple(float(v) for v in centre - offset * axis),
                },
            )
        candidates[name] = candidate
    return match(
        {expected.id: expected},
        candidates,
        body_centre,
        diagonal,
        check_cancelled=check_cancelled,
    ).mapping.get(expected.id)


def _detect_resized_bores(
    mesh: MeshData,
    expected: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> Mapping[FeatureId, Feature]:
    """Große Netze nur um die geometrisch erwarteten neuen Merkmale untersuchen."""
    from app.core.perceive.features import detect
    from app.core.perceive.local import FEATURE_LIMIT_TRIANGLES, detect_known

    if mesh.triangle_count > FEATURE_LIMIT_TRIANGLES:
        return detect_known(mesh, expected, check_cancelled=check_cancelled)
    return detect(mesh, check_cancelled=check_cancelled)


def _measured_on(
    mesh: MeshData,
    expected: Sequence[Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, Feature]:
    """Eben versetzte oder gekippte Bohrungen und Senkungen, am Ergebnis
    gemessen — unter ihren Namen.

    **Die Erklärung kommt aus dem Ergebnis, nicht aus den Parametern**
    (RM-220, 25.09.2026). Am Schraubenhalter wanderte eine gesenkte Bohrung
    1 mm entlang ihrer Achse; die Senkung stand danach laut Merkmal mit
    Ø 8,8 einen Millimeter vor der Fläche, am Körper aber mit Ø 6,8 in ihr.
    Eine gekippte Senkung trifft die Oberseite schräg, und ihr weitester Rand
    liegt an anderer Stelle als vorher. Der exakte Kern misst seit je nach
    (``_exact_features_after``); das Netz trug die alten Maße weiter.

    Gesucht wird jedes Merkmal wie dort an seiner Stelle (``_bore_match_id``,
    beim Kegel über seine Spitze, ``_same_cone``). Wo die Wand das gesetzte
    Maß trägt, bleibt es (:func:`_with_nominal_bore`); der Facettenfehler der
    Messung ersetzt es nicht. Was sich nicht wiederfindet, fehlt in der
    Antwort und bleibt beim Aufrufer, wie es war — die Auswertung meldet es
    dann als nicht wiedererkannt.
    """
    wanted = [feature for feature in expected if feature.kind in ("hole", "cone")]
    if not wanted:
        return {}
    detected = _detect_resized_bores(
        mesh, {feature.id: feature for feature in wanted}, check_cancelled=check_cancelled
    )
    measured: dict[FeatureId, Feature] = {}
    taken: set[str] = set()
    for want in wanted:
        free = {name: entry for name, entry in detected.items() if name not in taken}
        found = _bore_match_id(
            free, want, mesh.bounds.centre, mesh.bounds.diagonal, check_cancelled=check_cancelled
        )
        if found is None and want.kind == "cone":
            found = _same_cone(free, want, mesh.bounds.diagonal, angle_tolerance=FACETED_CONE_ANGLE)
        diameter = want.params.get("diameter")
        if found is None or not isinstance(diameter, int | float):
            continue
        taken.add(found)
        seen = detected[found]
        nominal = _with_nominal_bore(mesh, seen, want, float(diameter))
        measured[want.id] = dataclasses.replace(
            want,
            params={**want.params, **nominal.params},
            face_indices=seen.face_indices,
            surface_patches=seen.surface_patches,
        )
    return measured


def _copies_found(
    op: str,
    mesh: MeshData,
    copies: Mapping[FeatureId, Feature],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[dict[FeatureId, Feature], list[Finding]]:
    """Die Kopien am Ergebnis nachgemessen — und was sich nicht wiederfindet,
    gemeldet und weggelassen, wie am exakten Kern (``_exact_copy_result``).

    **Eine Kopie, die es nicht gibt, sagt es an beiden Kernen** (RM-249,
    26.09.2026). An der Lochplatte ``pegboard-gs-100-v2`` lief eine um 12 mm
    quer verdoppelte Schraubbohrung über die Seite; frisch erkannt fand sich an
    der Stelle an keinem Kern mehr als ein Kegelstück. Der exakte Kern meldete
    die Bohrungskopien als verloren, das Netz trug sie ungeprüft mit ihren
    Maßen weiter — und das Merkmalfenster zeigte zwei Bohrungen, die nicht
    da sind. Nachgemessen wird mit :func:`_measured_on`; Kopien anderer Art
    reichen durch, wie sie sind.

    **Wiedergefunden heißt: auf ihrer Achse.** Die Messung am Netz nimmt auch
    einen angeschnittenen Zylinder als Bohrung; an der Kopie über der Seite lag
    seine Mitte 0,75 bis 1,25 mm zur Materialseite hin, und die Auswertung
    verwarf ihn danach still als verwaist. Eine starr gesetzte Kopie steht
    seitlich genau dort, wo sie hin sollte — mehr als die Facettengrenze
    daneben (:data:`~app.core.units.MAX_FACET_SAG`) ist sie nicht mehr diese
    Kopie.
    """
    cavities = [
        copy for copy in copies.values() if copy.kind in ("hole", "cone") and is_a_cavity(copy)
    ]
    measured = _measured_on(mesh, cavities, check_cancelled=check_cancelled)
    kept: dict[FeatureId, Feature] = {}
    findings: list[Finding] = []
    wanted = {copy.id for copy in cavities}
    for name, copy in copies.items():
        found = measured.get(name)
        if name in wanted and (found is None or _beside_its_axis(found, copy)):
            findings.append(_cavity_lost_finding(op, copy))
            continue
        kept[name] = found or copy
    return kept, findings


def _beside_its_axis(found: Feature, expected: Feature) -> bool:
    """Ob ein nachgemessenes Merkmal seitlich neben der Achse liegt, auf die es
    gesetzt wurde — weiter als die Facettengrenze (:func:`_copies_found`)."""
    axis = np.asarray(_feature_direction(expected), dtype=np.float64)
    axis /= math.hypot(float(axis[0]), float(axis[1]), float(axis[2]))
    offset = np.asarray(found.params["centre"], dtype=np.float64) - np.asarray(
        expected.params["centre"], dtype=np.float64
    )
    across = offset - axis * units.dot3(offset, axis)
    return math.hypot(float(across[0]), float(across[1]), float(across[2])) > MAX_FACET_SAG


def _recognised_resized_feature(
    mesh: MeshData,
    feature: Feature,
    diameter: float,
    *,
    original: MeshData | None = None,
    known: Mapping[FeatureId, Feature] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> Feature | None:
    """Findet die eben erzeugte Wand und hängt den bestehenden Namen daran.

    Die allgemeine Zuordnung darf einen Sprung von Ø 3 auf Ø 30 nicht
    stillschweigend für dasselbe Merkmal halten. Hier ist er dagegen die
    ausdrückliche Operation. Darum wird genau für diesen Vergleich das neue
    Sollmaß eingesetzt, statt die globale Toleranz aufzuweichen.

    **Findet sie sich nicht wieder, ist das kein Programmfehler.** Hier stand
    ein ``InternalError`` mit „Erstellen Sie einen Fehlerbericht" — und er warf
    das fertig gerechnete Ergebnis mit weg, weil eine geworfene Ausnahme das
    ganze ``OpResult`` nimmt. Gemessen an ``spool-bearing-holder-p1stp.stl``
    aus dem Kundenbestand: Wer die 3,4-mm-Bohrung auf 0,2 mm verkleinert,
    bekommt genau die 11,75 mm³ Material zurück, die die Rechnung verlangt —
    und danach die Absage, weil ein Loch von 0,2 mm keines mehr ist, das die
    Erkennung findet. Die Auswertung hielt an, die richtige Geometrie war
    verworfen, und der Kunde las von einem unerwarteten Fehler.

    Der Rückgabewert ist deshalb ``None``, wenn die Zuordnung nicht greift.
    Der Aufrufer behält den Körper und meldet, dass das Merkmal fort ist —
    das ist die Wahrheit über die Lage und nicht über das Programm.
    """
    expected = _expected_bore(feature, diameter)
    detected = (
        _detect_resized_bores(mesh, {expected.id: expected}, check_cancelled=check_cancelled)
        if known is None
        else known
    )
    comparison = detected
    if original is not None:
        # Der größere Kreis trifft eine schräge Mündung an anderer Höhe. Nur
        # die axiale Mitte darf sich deshalb beim Ändern an derselben Stelle
        # bewegen. Der alte Mittelpunkt muss weiterhin in der tatsächlichen
        # Längenausdehnung liegen; ein getrenntes koaxiales Sackloch scheidet aus.
        axis = np.asarray(_bore_vector(expected, "axis"), dtype=float)
        axis /= np.linalg.norm(axis)
        centre = np.asarray(_bore_vector(expected, "centre"), dtype=float)
        direction: Vec3 = (float(axis[0]), float(axis[1]), float(axis[2]))
        old_span = _mesh_bore_span(original, feature, direction)
        middle = (old_span[0] + old_span[1]) / 2.0 if old_span is not None else float(centre @ axis)
        comparison = {}
        for identifier, candidate in detected.items():
            if candidate.kind != expected.kind:
                continue
            span = _mesh_bore_span(mesh, candidate, direction)
            if span is None or not span[0] - EPS_GEOM <= middle <= span[1] + EPS_GEOM:
                continue
            params = dict(candidate.params)
            for name in ("centre", "arc_centre"):
                if name in params:
                    point = np.asarray(params[name], dtype=float)
                    params[name] = tuple(
                        float(v) for v in point - float((point - centre) @ axis) * axis
                    )
            comparison[identifier] = dataclasses.replace(candidate, params=params)
    found_id = _bore_match_id(
        comparison,
        expected,
        mesh.bounds.centre,
        mesh.bounds.diagonal,
        check_cancelled=check_cancelled,
    )
    if found_id is None:
        return None
    # **Und die Zuordnung wird nachgeprüft** — derselbe Fund wie an
    # ``_recognised_slot``, nur zwei Wochen älter: Wer eine Bohrung über den
    # Rand versetzt, hat danach einen offenen Ausschnitt statt einer Bohrung.
    # ``match`` traf dann die Nachbarbohrung acht Millimeter daneben, die trug
    # von da an die Kennung der versetzten, und ``resize_hole.feature_lost``
    # blieb aus (gemessen 11.09.2026 an zwei Ø-4-Bohrungen bei y = 46 und 54,
    # die obere auf 59,5 versetzt: `hole_2` stand danach bei 46).
    if not _sits_at(comparison[found_id], expected, mesh.bounds.diagonal):
        return None
    return dataclasses.replace(
        detected[found_id],
        id=feature.id,
        provenance="generated",
        created_by=None,
    )


def _with_nominal_bore(
    mesh: MeshData,
    found: Feature,
    expected: Feature,
    diameter: float,
    *,
    sections: int = BORE_SECTIONS,
) -> Feature:
    """Bekannte Operationsmaße bleiben erhalten, wenn die tatsächliche Wand sie trägt.

    Der Zylinderfit misst Dreiecksschwerpunkte innerhalb des Umkreises. Diese
    Messung darf den gesetzten Durchmesser nicht beim nächsten Ändern ersetzen.
    Geprüft werden alle zugeordneten Wandpunkte gegen Kreis beziehungsweise
    Kegel und die aus der Werkzeugunterteilung folgende Sehnenabweichung.
    """
    from app.core.units import weld_tolerance

    if found.kind not in ("hole", "cone") or not found.face_indices:
        return found
    axis = np.asarray(_feature_direction(expected), dtype=float)
    axis /= np.linalg.norm(axis)
    origin = np.asarray(expected.params["centre"], dtype=float)
    points = np.asarray(mesh.raw.vertices[np.unique(mesh.raw.faces[found.face_indices, :])])
    relative = points - origin
    along = relative @ axis
    radii = np.linalg.norm(relative - np.outer(along, axis), axis=1)
    wanted = np.full(len(points), diameter / 2.0)
    if found.kind == "cone":
        wanted += along * math.tan(math.radians(float(expected.params["angle"]) / 2.0))
    tolerance = weld_tolerance(mesh.bounds.diagonal)
    if np.any(radii > wanted + tolerance) or np.any(
        radii < wanted * units.inscribed_ratio(sections) - tolerance
    ):
        return found
    params = dict(found.params)
    centre = np.asarray(params["centre"])
    # Die Mitte, die das Merkmal danach trägt, auf jeder Maschine dieselbe
    # (RM-187): Skalarprodukt über ``units.dot3``, nicht über ``@``.
    params["centre"] = tuple(float(v) for v in origin + units.dot3(centre - origin, axis) * axis)
    params["axis"] = tuple(float(v) for v in axis)
    if found.kind == "hole":
        params["diameter"] = diameter
    else:
        params["angle"] = expected.params["angle"]
    return dataclasses.replace(found, params=params)


#: Die Hohlraumarten, die der exakte Kern ohne Vernetzung versetzt, verdoppelt,
#: dreht und entfernt (P2.4). Ketten aus Bohrung und Senkung, Zapfen, Kegel,
#: Kugeln und Einschlüsse folgen in eigenen Schritten; bis dahin gehen sie am
#: exakten Körper den Netzweg, und ``evaluate.exact_became_mesh`` sagt es.
EXACT_CAVITY_KINDS: Final = ("hole", "slot")


def _exact_body(source: SceneObject) -> Any:
    """Der exakte Körper eines als ``brep`` geführten Objekts — oder ein Programmfehler."""
    from app.core.brep.kernel import Solid

    if not isinstance(source.mesh, Solid):
        raise InternalError(
            detail="a scene object marked as brep does not carry a Solid",
            values={"object": source.id},
        )
    return source.mesh


def _exact_cavity_filled(solid: Any, feature: Feature) -> Any:
    """Eine erkannte Bohrung oder ein Langloch exakt schließen — mit den gemessenen Maßen.

    Dieselbe Paarung wie am Netz (``_closed_at``), nur ohne Vieleck: Der
    Füllkörper kommt aus ``edit.fill_bore`` und greift radial um ``EPS_GEOM``
    ins Material, axial bleibt er exakt. Ein offenes Langloch endet an seiner
    Außenwand, damit beim Versetzen kein Stopfen neben dem Teil steht.
    """
    from app.core.brep import edit

    centre = _bore_vector(feature, "centre")
    axis = _bore_vector(feature, "axis")
    diameter = _bore_number(feature, "diameter")
    # **Begrenzt an den Randebenen, wo es sie gibt** — dieselbe Frage wie am
    # Netz (``_closed_at``, :func:`_rim_planes`): Die Deckel des Stopfens stehen
    # quer zur Achse, die Mündungen einer schrägen Bohrung nicht.
    planes = _rim_planes(solid, feature)
    depth = _bore_number(_longer(feature) if planes else feature, "depth")
    # Ohne Randebenen begrenzt die konvexe Hülle, wie am Netz ``shell``: Ein
    # Stopfen darf nicht aus dem Körper herauswachsen, den er füllt.
    within = None if planes else edit.convex_hull(solid)
    if feature.kind == "slot":
        opening = (
            (_bore_vector(feature, "mouth_centre"), _bore_vector(feature, "opening_normal"))
            if feature.params.get("open")
            else None
        )
        return edit.fill_bore(
            solid,
            position=centre,
            direction=axis,
            diameter=diameter,
            depth=depth,
            length=_bore_number(feature, "length"),
            angle_deg=slot_angle_of(feature, axis),
            opening=opening,
            planes=planes,
            within=within,
        )
    return edit.fill_bore(
        solid,
        position=centre,
        direction=axis,
        diameter=diameter,
        depth=depth,
        planes=planes,
        within=within,
    )


def _exact_cavity_cut(solid: Any, feature: Feature, centre: Vec3, axis: Vec3) -> Any:
    """Dasselbe Merkmal an ``centre`` entlang ``axis`` exakt ausschneiden.

    Eine durchgehende Bohrung bekommt die ganze Zielhülle als Tiefe
    (``_through_bore_depth``), eine blinde ihre gemessene; ein Langloch
    trägt seine Richtung im Rahmen der neuen Achse (``_slot_angle_in_frame``).
    """
    from app.core.brep import edit

    tool = _exact_cavity_tool(solid, feature, centre, axis)
    cut = edit.boolean("difference", [solid, tool])
    # Beim Langloch liegen die Flanken des Werkzeugs in der Ebene alter
    # Flanken; ihre Teilungsnähte gehören nicht zum Mantel (``slot_bore``).
    return edit.unified(cut) if feature.kind == "slot" else cut


def _exact_cavity_tool(solid: Any, feature: Feature, centre: Vec3, axis: Vec3) -> Any:
    """Das Werkzeug von :func:`_exact_cavity_cut` — für das Muster, das viele
    davon zugleich schneidet. Dieselben Maße: durchgehend über die ganze
    Zielhülle, blind in der gemessenen Tiefe, das Langloch in seiner Richtung.
    """
    from app.core.brep import edit

    diameter = _bore_number(feature, "diameter")
    depth = (
        _through_bore_depth(solid, centre, axis)
        if feature.params.get("through")
        else _bore_number(feature, "depth")
    )
    if feature.kind == "slot":
        return edit._slot_tool(
            centre,
            axis,
            diameter,
            depth,
            _bore_number(feature, "length"),
            _slot_angle_in_frame(feature, axis),
            0.0,
        )
    return edit._centred_bore(centre, axis, diameter, depth, 0.0)


def _exact_body_checked(solid: Any) -> Any:
    """Ob nach dem Schnitt noch ein geschlossener Körper da ist — dieselben zwei
    Fragen wie in ``resize_hole``, mit denselben Sätzen."""
    if solid.volume <= EPS_GEOM or solid.face_count == 0:
        raise GeometryError(
            title=NOTHING_LEFT_TITLE,
            detail=NOTHING_LEFT_DETAIL,
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if not solid.is_closed:
        raise GeometryError(
            title=OPEN_BODY_TITLE,
            detail=OPEN_BODY_DETAIL,
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return solid


def _same_cone(
    detected: Mapping[str, Feature],
    wanted: Feature,
    diagonal: float,
    *,
    angle_tolerance: float = EPS_DISPLAY,
) -> str | None:
    """Derselbe Kegel, auch wo sein Rand an einer anderen Stelle gemessen wird.

    Mitte und Durchmesser eines Kegels beschreiben seinen **weitesten Rand**,
    und der hängt an der Fläche, die ihn schneidet. Eine gekippte Senkung
    trifft die Oberseite schräg; der exakte Kern maß danach Ø 12,37 bei
    z = 13,08, wo die Drehung Ø 10 bei z = 11,91 erwartete — dieselbe
    Kegelfläche, und die Operation meldete sie als verloren (gemessen
    23.09.2026, Senkbohrung um 10° gekippt). Verglichen wird deshalb, was vom
    Rand nicht abhängt: Achse, Öffnungswinkel und Spitze. Am exakten Körper
    trifft der Winkel auf die Anzeigestelle, am Netz auf
    ``angle_tolerance`` (:data:`FACETED_CONE_ANGLE`).
    """
    from app.core.units import match_tolerance

    def apexes(feature: Feature) -> list[NDArray[np.float64]] | None:
        angle = float(feature.params.get("angle", 0.0))
        diameter = float(feature.params.get("diameter", 0.0))
        if not 0.0 < angle < 180.0 or diameter <= EPS_GEOM:
            return None
        axis = np.asarray(_feature_direction(feature), dtype=np.float64)
        centre = np.asarray(feature.params["centre"], dtype=np.float64)
        reach = diameter / 2.0 / math.tan(math.radians(angle / 2.0))
        return [centre + axis * reach, centre - axis * reach]

    wanted_apexes = apexes(wanted)
    if wanted_apexes is None:
        return None
    axis = np.asarray(_feature_direction(wanted), dtype=np.float64)
    tolerance = match_tolerance(diagonal)
    found = []
    for name, candidate in detected.items():
        if candidate.kind != "cone":
            continue
        own = apexes(candidate)
        if own is None:
            continue
        if abs(float(candidate.params["angle"]) - float(wanted.params["angle"])) > angle_tolerance:
            continue
        other = np.asarray(_feature_direction(candidate), dtype=np.float64)
        if abs(float(axis @ other)) < units.exact_cos_degrees(0.5):
            continue
        if any(np.linalg.norm(a - b) <= tolerance for a in wanted_apexes for b in own):
            found.append(name)
    return found[0] if len(found) == 1 else None


def _exact_features_after(
    source: SceneObject,
    solid: Any,
    *,
    expected: Feature | Sequence[Feature] | None,
    gone: Sequence[str] = (),
    cancelled: CancelToken,
    mouths: frozenset[str] = frozenset(),
) -> tuple[dict[str, Feature], tuple[tuple[str, str], ...], tuple[str, ...]]:
    """Die Merkmale des neu gebauten exakten Körpers unter ihren fortgeführten Namen.

    Die native Erkennung nummeriert frisch; ein Bezug gilt nur belegt
    (P1.4c.2). ``expected`` sind die bewusst versetzten, gedrehten oder
    verdoppelten Merkmale mit ihren neuen Werten — eines oder die ganze
    Kette: Jedes wird an seiner Stelle gesucht (``_bore_match_id``) und unter
    dem alten Namen fortgeführt; alles andere ordnet ``match`` zu. ``gone``
    nennt, was die Operation entfernt hat. Zurück kommen die Merkmale, die
    belegten Übergänge und die Namen der erwarteten Merkmale, die **nicht**
    wiederzufinden waren. ``mouths`` sind die äußeren Zylinder einer Kette
    (:func:`_chain_mouths`).
    """
    from app.core.brep.features import features_of
    from app.core.perceive.matching import apply_mapping, match

    detected = features_of(solid, cancelled=cancelled)
    previous = {name: entry for name, entry in source.features.items() if name not in gone}
    bounds = solid.bounds
    intended: dict[str, str] = {}
    wanted = (
        [] if expected is None else [expected] if isinstance(expected, Feature) else list(expected)
    )
    lost: list[str] = []
    for want in wanted:
        previous.pop(want.id, None)
    for want in wanted:
        free = {name: entry for name, entry in detected.items() if name not in intended.values()}
        found_id = _bore_match_id(
            free,
            want,
            bounds.centre,
            bounds.diagonal,
            check_cancelled=cancelled.raise_if_cancelled,
            mouth=want.id in mouths,
        )
        if found_id is None and want.kind == "cone":
            found_id = _same_cone(free, want, bounds.diagonal)
        if found_id is None:
            lost.append(want.id)
            continue
        previous[want.id] = dataclasses.replace(detected[found_id], id=want.id)
        intended[want.id] = found_id
    matched = match(
        previous,
        detected,
        bounds.centre,
        bounds.diagonal,
        check_cancelled=cancelled.raise_if_cancelled,
    )
    if lost:
        matched.orphaned = (*matched.orphaned, *lost)
    continued = tuple(
        (old_id, old_id)
        for old_id, new_id in intended.items()
        if matched.mapping.get(old_id) == new_id and old_id not in matched.ambiguous
    )
    features = apply_mapping(detected, matched, previous=source.features)
    return features, continued, tuple(lost)


def _through_lost_finding(op: str, feature: Feature, centre: Vec3) -> Finding:
    """Der Satz, wenn eine durchgehende Bohrung an der neuen Stelle nicht mehr durchgeht."""
    return Finding(
        code=f"{op}.no_longer_through",
        severity="warning",
        message=_(
            "Diese Bohrung ging durch das Teil und tut es an der neuen Stelle "
            "nicht mehr — ihre Achse durchquert das Material dort nicht ganz."
        ),
        feature_ids=(feature.id,),
        location=centre,
        # Regel 17: Stelle und Tiefe stehen im Schritt, der Ort fliegt mit.
        suggestions=(CORRECT_INPUT, SHOW_LOCATION),
    )


def _cavity_lost_finding(op: str, feature: Feature) -> Finding:
    """Das Merkmal ist gesetzt, aber am Ergebnis nicht mehr als Merkmal auffindbar —
    am exakten Körper nach seiner Erkennung, am Netz nach dem Nachmessen
    (:func:`_copies_found`)."""
    return Finding(
        code=f"{op}.feature_lost",
        severity="warning",
        message=_(
            "Das Merkmal wurde gesetzt, lässt sich am Ergebnis aber nicht mehr als "
            "Merkmal wiederfinden. Die Geometrie stimmt; spätere Schritte, die auf "
            "es verweisen, verlieren ihren Bezug."
        ),
        feature_ids=(feature.id,),
        values={"feature": feature.id, "kind": feature.kind},
    )


def _exact_cavity_result(
    ctx: OpContext,
    source: SceneObject,
    solid: Any,
    *,
    op: str,
    expected: Feature | Sequence[Feature] | None,
    gone: Sequence[str] = (),
    findings: list[Finding],
    reserve: bool = False,
    mouths: frozenset[str] = frozenset(),
) -> OpResult:
    """Das gemeinsame Ende der vier exakten Hohlraumhandlungen: prüfen, erkennen,
    Namen fortführen, Durchgang melden, Bezüge belegen."""
    checked = _exact_body_checked(solid)
    features, continued, lost = _exact_features_after(
        source, checked, expected=expected, gone=gone, cancelled=ctx.cancelled, mouths=mouths
    )
    wanted = (
        [] if expected is None else [expected] if isinstance(expected, Feature) else list(expected)
    )
    for want in wanted:
        if want.id in lost and want.kind == "face":
            # Ein mitgeführter Sackboden, der sich nicht wiederfindet, ist kein
            # verlorener Hohlraum; die Auswertung meldet die Fläche als
            # nicht wiederzuerkennen, wie jede andere.
            continue
        if want.id in lost:
            findings.append(_cavity_lost_finding(op, want))
        elif want.params.get("through") and not features[want.id].params.get("through"):
            findings.append(_through_lost_finding(op, want, _bore_vector(want, "centre")))
    reserved = source.reserved_feature_ids
    if reserve:
        reserved = tuple(sorted({*source.reserved_feature_ids, *source.features}))
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=checked,
                kind="brep",
                features=features,
                reserved_feature_ids=reserved,
            )
        ],
        findings=findings,
        feature_continuations=(
            tuple(
                FeatureContinuation(FeatureRef(source.id, old_id), new_id)
                for old_id, new_id in continued
            ),
        ),
    )


def _exact_move_cavity(
    ctx: OpContext, source: SceneObject, feature: Feature, centre: Vec3, target: Vec3
) -> OpResult:
    """Bohrung oder Langloch am exakten Körper versetzen: schließen, neu schneiden (P2.4).

    Bis zum 20.09.2026 lief das Versetzen am exakten Körper über das Netz, und
    der Körper kam als Netz zurück — Fase, Formschräge und STEP-Export waren
    danach fort. Jetzt bleibt er exakt: Die alte Stelle schließt
    ``edit.fill_bore``, die neue schneidet ``edit.cut_bore`` beziehungsweise
    ``edit.slot_bore``, und die Kennung reist belegt mit
    (``FeatureContinuation``), wie die Auswertung es verlangt (P1.4c.2).
    """
    solid = _exact_body(source)
    axis = _bore_vector(feature, "axis")
    travel = np.asarray(target, dtype=float) - np.asarray(centre, dtype=float)
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    filled = _exact_cavity_filled(solid, feature)
    ctx.progress(0.6, str(_("Das Merkmal wird an seiner neuen Stelle gesetzt …")))
    placed, tool = _exact_rigid_cut(source, filled, feature, target, axis, travel)
    expected = dataclasses.replace(
        feature, params={**feature.params, "centre": target}, provenance="generated"
    )
    findings = _edge_findings(as_mesh_data(filled), [expected])
    findings += _without_opened_twice(
        _neighbour_bore_findings(source, feature, as_mesh_data(tool), ctx, moved=True), findings
    )
    result = _exact_cavity_result(
        ctx, source, placed, op="move_feature", expected=expected, findings=findings
    )
    return _exact_mouth_checked(result, "move_feature", source, feature, travel)


def _exact_duplicate_cavity(
    ctx: OpContext, source: SceneObject, feature: Feature, target: Vec3
) -> OpResult:
    """Bohrung oder Langloch am exakten Körper ein zweites Mal schneiden (P2.4).

    Die Kopie bekommt eine eigene Kennung nach derselben Zählung wie am Netz
    (``_free_feature_id``); das Original bleibt, und die Zuordnung führt es
    unter seinem Namen weiter.
    """
    solid = _exact_body(source)
    axis = _bore_vector(feature, "axis")
    travel = np.asarray(target, dtype=float) - np.asarray(feature.params["centre"], dtype=float)
    ctx.progress(0.2, str(_("Das Merkmal wird an der neuen Stelle angelegt …")))
    placed, tool = _exact_rigid_cut(source, solid, feature, target, axis, travel)
    copy = dataclasses.replace(
        feature,
        id=_free_feature_id(source, feature.kind),
        params={**feature.params, "centre": target},
        provenance="generated",
    )
    findings = _edge_findings(as_mesh_data(solid), [copy])
    findings += _without_opened_twice(
        _neighbour_bore_findings(source, feature, as_mesh_data(tool), ctx, moved=True, copy=True),
        findings,
    )
    nothing = without_effect(solid, placed, "difference", ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    result = _exact_copy_result(ctx, source, placed, [copy], findings)
    return _exact_mouth_checked(result, "duplicate_feature", source, feature, travel)


def _exact_copy_result(
    ctx: OpContext,
    source: SceneObject,
    placed: Any,
    copies: Sequence[Feature],
    findings: list[Finding],
    *,
    op: str = "duplicate_feature",
    mouths: frozenset[str] = frozenset(),
) -> OpResult:
    """Das gemeinsame Ende der vier exakten Verdoppelungen — Hohlraum, Kette,
    Flächenkörper und Ring: prüfen, erkennen, der Kopie ihren Namen geben,
    Durchgang melden, Bezüge belegen.

    Die Kopie ist die frische Erkennung an der Zielstelle; sie bekommt den
    Namen, den die Zählung freigibt — nicht den, den die Erkennung zufällig
    vergab, und keinen, der reserviert ist. Bis zum 21.09.2026 stand dieser
    Block viermal wörtlich da, und nur einer der vier fragte nach dem
    verlorenen Durchgang. Das Merkmalsmuster endet hier ebenfalls, mit allen
    Instanzen auf einmal; ``op`` gibt den Befunden seinen Namen. ``mouths``
    nennt die Kopien, die äußere Zylinder einer Kette sind (:func:`_chain_mouths`).

    **Erst zugeordnet, dann benannt** (RM-245, 25.09.2026). Die frische
    Erkennung vergibt ihre Namen nach eigener Zählung, und die trifft die
    Namen der Kopien — an der Kopie einer Bohrung mit Zylindersenkung und Fase
    hieß die neue Senkung ``hole_3``, genau wie die Kopie der Bohrung. Bis
    dahin blieb ein so benannter Fund aus der Suche, die Kopie der Bohrung
    fand nichts und las dann die Senkung unter ihrem Namen: „geht nicht mehr
    durch", bei genau dem Volumen, das die Kette hat. Jetzt gilt jeder Fund
    als frei, der nicht schon vorher da war; wer keiner Kopie gehört und
    einen ihrer Namen trägt, bekommt einen freien.
    """
    checked = _exact_body_checked(placed)
    features, continued, _lost = _exact_features_after(
        source, checked, expected=None, cancelled=ctx.cancelled
    )
    diagonal = checked.bounds.diagonal
    copy_ids = {copy.id for copy in copies}
    fresh = {name: entry for name, entry in features.items() if name not in source.features}
    claimed: dict[str, str] = {}
    for copy in copies:
        found = [
            name
            for name, entry in fresh.items()
            if name not in claimed
            and entry.kind == copy.kind
            and _sits_at(entry, copy, diagonal, mouth=copy.id in mouths)
        ]
        if len(found) > 1:
            # **Zwei Abschnitte derselben Kette an einer Stelle**: Entlang der
            # Achse frei, liegt an der Kopie einer Bohrung auch ihre
            # Zylindersenkung am Rand des gemeinsam überdeckten Abschnitts. Das
            # Maß entscheidet.
            wanted = float(copy.params.get("diameter") or 0.0)
            found = [
                name
                for name in found
                if abs(float(fresh[name].params.get("diameter") or 0.0) - wanted)
                <= max(FEATURE_OVERLAP, wanted * _SAME_LENGTH)
            ]
        if len(found) == 1:
            claimed[found[0]] = copy.id
        elif not found:
            findings.append(_cavity_lost_finding(op, copy))
    taken: set[str] = {*source.reserved_feature_ids, *source.features, *copy_ids, *features}
    named: dict[str, Feature] = {}
    for name, entry in features.items():
        target = claimed.get(name, name)
        if name not in claimed and name in fresh and name in copy_ids:
            target = _free_id_among(taken, entry.kind)
            taken.add(target)
        named[target] = entry if target == name else dataclasses.replace(entry, id=target)
    features = named
    for copy in copies:
        if (
            copy.id in features
            and copy.params.get("through")
            and not features[copy.id].params.get("through")
        ):
            findings.append(_through_lost_finding(op, copy, _bore_vector(copy, "centre")))
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=checked,
                kind="brep",
                features=features,
                reserved_feature_ids=tuple(
                    sorted({*source.reserved_feature_ids, *source.features, *copy_ids})
                ),
            )
        ],
        findings=findings,
        feature_continuations=(
            tuple(
                FeatureContinuation(FeatureRef(source.id, old_id), new_id)
                for old_id, new_id in continued
            ),
        ),
    )


def _exact_rotate_cavity(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    spun: Feature,
    centre: Vec3,
    turned_axis: Vec3,
) -> OpResult:
    """Bohrung oder Langloch am exakten Körper kippen: schließen, gedreht schneiden (P2.4).

    Geschlossen wird mit der gemessenen Achse und Richtung, gesetzt mit der
    gedrehten — dieselbe Regel wie am Netz: Wer beides mit der neuen tut,
    füllt neben dem Loch und schneidet ein Kreuz hinein.

    Eine Durchgangsbohrung schneidet die ganze Zielhülle
    (``_through_bore_depth``) und endet deshalb an den alten Rändern
    (:func:`_old_rim_caps`) — wie am Netz, wo ``_turned_through_bore`` sie
    nur so weit verlängert, wie die Neigung verlangt. Ohne die Kappe bohrte sie
    durch jede Wand auf ihrer Linie (RM-220). Und wie am Netz fragt die
    Bohrung danach die Nachbarwand.
    """
    from app.core.brep import edit

    solid = _exact_body(source)
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    filled = _exact_cavity_filled(solid, feature)
    ctx.progress(0.6, str(_("Das Merkmal wird gedreht gesetzt …")))
    expected = dataclasses.replace(
        spun, params={**spun.params, "axis": turned_axis}, provenance="generated"
    )
    # **Erst die Kante, dann die Nachbarwand** — dieselbe Reihenfolge wie am
    # Netz (``rotate_feature``): ``_without_opened_twice`` streicht „über die
    # Kante" nur aus dem, was schon in der Liste steht. Stand der Kantenbefund
    # erst danach darin, meldete der exakte Körper eine in die Nachbarin
    # gekippte Bohrung zweimal (Durchsicht seit 0.5.0, 25.09.2026).
    findings = _edge_findings(as_mesh_data(filled), [expected])
    if feature.kind == "hole":
        tool = _exact_cavity_tool(filled, spun, centre, turned_axis)
        if feature.params.get("through"):
            caps = _old_rim_caps(as_mesh_data(source.mesh), feature, source.features)
            if caps:
                tool = edit.clipped_bore_tool(tool, caps)
        placed = edit.boolean("difference", [filled, tool])
        findings += _without_opened_twice(
            _neighbour_bore_findings(source, feature, as_mesh_data(tool), ctx, turned=True),
            findings,
        )
    else:
        placed = _exact_cavity_cut(filled, spun, centre, turned_axis)
    return _exact_cavity_result(
        ctx, source, placed, op="rotate_feature", expected=expected, findings=findings
    )


def _exact_remove_cavity(ctx: OpContext, source: SceneObject, feature: Feature) -> OpResult:
    """Bohrung oder Langloch am exakten Körper schließen — und die Kennung geht mit (P2.4)."""
    solid = _exact_body(source)
    ctx.progress(0.2, str(_("Das Merkmal wird geschlossen …")))
    filled = _exact_cavity_filled(solid, feature)
    findings = [
        Finding(
            code="remove_feature.gone",
            severity="info",
            message=_(
                "Das Merkmal ist entfernt. Spätere Schritte und Passungen, die auf es "
                "verweisen, finden es nicht mehr."
            ),
            feature_ids=(feature.id,),
            values={"feature": feature.id, "kind": feature.kind, "removed": 1},
        )
    ]
    return _exact_cavity_result(
        ctx,
        source,
        filled,
        op="remove_feature",
        expected=None,
        gone=(feature.id,),
        findings=findings,
        reserve=True,
    )


def _chain_mouths(chain: Sequence[Feature]) -> frozenset[str]:
    """Die äußeren Zylinder einer Kette — der letzte Abschnitt jeder Seite, wo er
    eine Bohrung ist (``relations.cavity_sides``).

    Ihre Lage entlang der Achse gibt die Fläche vor, in die sie münden, und
    der exakte Kern sucht sie danach frei entlang der Achse
    (:func:`_free_along_the_axis`). Eine Senkung sucht er an ihrer Spitze
    (:func:`_same_cone`), und die Bohrung einer Kette hat keine Mündung, die
    ihr gehört.
    """
    from app.core.perceive.relations import cavity_sides

    return frozenset(
        side[-1].id for side in cavity_sides(chain) if len(side) > 1 and side[-1].kind == "hole"
    )


def _exact_chain_entrance(source: SceneObject, chain: Sequence[Feature]) -> _BoreEntrance:
    """Der Einlauf einer Kette am exakten Körper — von ihrer Bohrung aus gelesen.

    ``bore_entrance`` liest Abschnitte, Radien und die wirklichen Randebenen
    für beide Kerne; hier wird er für jede Kettenhandlung gebraucht, nicht nur
    fürs Ändern. Gibt der Hohlraum keinen eindeutigen Einlauf her, sagt die
    Operation ab — **mit ihrem eigenen Satz** (RM-245, 25.09.2026). Bis dahin
    kam der des Einlaufs, und der riet über *Merkmal versetzen*, *drehen* und
    *verdoppeln* zu „Nur Bohrungsdurchmesser" — einem Feld, das diese drei gar
    nicht haben.
    """
    try:
        entrance = bore_entrance(
            source.mesh, chain[0], source.features, cavity=tuple(chain), touches_other=False
        )
    except ValidationError as error:
        raise _chain_not_readable(chain) from error
    if entrance is None:
        raise _chain_not_readable(chain)
    return entrance


#: Der Satz, mit dem eine Kettenhandlung am exakten Körper absagt, wenn sich die
#: Abschnitte nicht zu einem Einlauf lesen lassen (:func:`_exact_chain_entrance`).
CHAIN_NOT_READABLE: Final = _(
    "Dieser Hohlraum lässt sich an diesem Körper nicht als eine Bohrung lesen: Ein Rand "
    "ist nicht eben, oder eine Stufe wird nach außen enger. Ändern Sie den Schritt, aus "
    "dem er stammt."
)


def _chain_not_readable(chain: Sequence[Feature]) -> ValidationError:
    """Die Absage aus :func:`_exact_chain_entrance`, mit den Namen der Kette."""
    return ValidationError(
        field="at_feature",
        detail=CHAIN_NOT_READABLE,
        values={"bore": chain[0].id},
        constraint="not_movable",
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def _plane_turned(
    plane: SectionPlane, matrix: NDArray[np.float64], pivot: NDArray[np.float64], shift: float
) -> SectionPlane:
    """Dieselbe Ebene, um ``matrix`` gedreht (um ``pivot``) und um ``shift`` entlang
    ihrer gedrehten Normalen nach außen geschoben."""
    normal = np.asarray(plane.normal, dtype=float)
    point = normal * plane.position
    turned_normal = matrix[:3, :3] @ normal
    turned_point = matrix[:3, :3] @ (point - pivot) + pivot
    position = float(turned_normal @ turned_point) + shift
    return SectionPlane(
        normal=(float(turned_normal[0]), float(turned_normal[1]), float(turned_normal[2])),
        position=position,
    )


def _exact_chain_solid(
    entrance: _BoreEntrance,
    reach: float,
    *,
    filling: bool,
    frame: PlaneFrame,
    planes_of: Callable[[int, SectionPlane, SectionPlane], tuple[SectionPlane, ...]],
    overlap: float = FEATURE_OVERLAP,
) -> Any:
    """Der Hohlraum einer Kette als exakter Körper — Stopfen oder Werkzeug.

    Dieselben Profile und Randebenen wie ``resize_hole`` (``_entrance_tools``),
    als Rotationskörper um ``frame`` und an den Ebenen begrenzt, die
    ``planes_of`` je Abschnitt nennt: unverschoben für den Stopfen an der
    alten Stelle, verschoben oder gedreht für das Werkzeug an der neuen.
    """
    from app.core.brep import edit

    diameter = entrance.sections[0].inner_radius * 2.0
    parts = []
    for index, (outline, (lower, upper)) in enumerate(
        _entrance_tools(entrance, diameter, reach, filling=filling, overlap=overlap)
    ):
        tool = edit.revolved_bore_tool(outline, frame)
        parts.append(edit.clipped_bore_tool(tool, planes_of(index, lower, upper)))
    return edit.boolean("union", parts) if len(parts) > 1 else parts[0]


def _exact_chain_filled(source: SceneObject, entrance: _BoreEntrance) -> Any:
    """Die ganze Kette am exakten Körper schließen — mit :func:`_exact_chain_plug`."""
    from app.core.brep import edit

    solid = _exact_body(source)
    plug = _exact_chain_plug(source, entrance)
    filled = edit.unified(edit.boolean("union", [solid, plug]))
    # Ein Stopfen aus den eigenen Flächen des Körpers teilt mit ihm jede
    # Kante; eine Vereinigung, die ihn still fallen ließe, bliebe sonst
    # unbemerkt — der Hohlraum stünde an der alten Stelle weiter offen.
    if filled.volume < solid.volume + plug.volume * (1.0 - _SAME_LENGTH):
        raise _chain_not_readable(entrance.chain)
    return filled


def _exact_chain_plug(source: SceneObject, entrance: _BoreEntrance) -> Any:
    """Der Körper, der eine Kette am exakten Körper füllt.

    Aus ihren Profilen, an den wirklichen Randebenen begrenzt — dieselben wie
    beim Ändern (``_entrance_tools``). **Mündet ein Abschnitt in eine
    gekrümmte Fläche** (``_EntranceSection.curved``, RM-245), gäbe das Profil
    bis zur Ebene durch ihren weitesten Punkt Material vor die Fläche: An der
    Lochplatte ``pegboard-gs-100-v2.step`` 33 mm³ vor einer Rundung, deren
    BSpline-Flächen genau auf ihren Rand beschnitten sind und unter dem Loch
    nicht weiterlaufen. Dann kommt der Stopfen aus den nativen Flächen der
    Kette, und die gekrümmte Mündung bekommt einen Fächer vom Mittelpunkt ihres
    Rands (``edit.solid_from_faces``, ``fan_caps``) — derselbe Deckel wie am
    Netz (:func:`_cavity_plug`), dort aus Dreiecken.
    """
    from app.core.brep import edit
    from app.core.perceive.relations import cavity_surface_indices
    from app.core.sketch.planes import frame_of

    solid = _exact_body(source)
    curved = any(
        section.curved for _way, sections, _open in entrance.sides() for section in sections
    )
    if not curved:
        return _exact_chain_solid(
            entrance,
            solid.bounds.diagonal,
            filling=True,
            frame=frame_of(entrance.axis, entrance.origin),
            planes_of=lambda _index, lower, upper: (lower, upper),
        )
    native = solid.faces_of_triangles(
        cavity_surface_indices(as_mesh_data(source.mesh), entrance.chain)
    )
    plug = (
        edit.solid_from_faces(solid, native, allowed_rings=(1, 2), fan_caps=True)
        if native
        else None
    )
    if plug is None:
        raise _chain_not_readable(entrance.chain)
    return plug


def _exact_chain_cut_moved(
    solid: Any, entrance: _BoreEntrance, travel: NDArray[np.float64]
) -> tuple[Any, Any]:
    """Die Kette an der um ``travel`` verschobenen Stelle exakt ausschneiden —
    das Ergebnis und das Werkzeug, an dem der Durchgang danach gemessen wird."""
    matrix = np.asarray(translation(cast(Vec3, tuple(float(v) for v in travel))), dtype=float)
    return _exact_chain_cut_holding(
        solid, lambda overlap: _exact_chain_tool_placed(solid, entrance, matrix, overlap=overlap)
    )


def _exact_chain_cut_holding(solid: Any, tool_with: Callable[[float], Any]) -> tuple[Any, Any]:
    """``solid`` minus dem Werkzeug aus ``tool_with`` — und eine Differenz, die
    still gescheitert ist, wird mit weiterem Mündungsüberstand wiederholt.

    **OpenCASCADE sagt nicht immer, wenn es nicht schneiden konnte**
    (26.09.2026). An der Lochplatte ``pegboard-gs-100-v2.step`` kam die untere
    Schraubbohrung, um 1,5 mm nach oben versetzt, mit genau dem Volumen des
    gefüllten Körpers zurück: 57 statt 50 Flächen, der Netz-Zwilling undicht
    mit 5 176 mm³ zu viel, und ``BRepCheck`` nannte alles gültig. Körper minus
    Werkzeug ergab dort „leer", die Schnittmenge null — die Lage und nicht das
    Werkzeug war der Grund: Mit 0,02 mm Überstand über die offenen Mündungen
    scheiterten +1,5 und +2,0 mm, mit 0,04 und 0,06 mm hielt jede Lage, mit
    0,1 mm scheiterte es wieder. Ein Ergebnis gilt deshalb nur mit dichtem
    Zwilling, und sonst schneidet dasselbe Werkzeug mit dem doppelten und dann
    dem dreifachen Überstand (:data:`CUT_OVERLAPS`). Der Überstand liegt vor
    offenen Mündungen, in der Luft; er ändert den Abtrag nur, wo die Fläche an
    der neuen Stelle weiter hinausreicht — an der Lochplatte um 0,4 mm³. Hält
    keiner, sagt die Handlung ab, statt einen kaputten Körper zu liefern.
    """
    from app.core.brep import edit

    for factor in CUT_OVERLAPS:
        tool = tool_with(FEATURE_OVERLAP * factor)
        placed = edit.unified(edit.boolean("difference", [solid, tool]))
        if as_mesh_data(placed).is_watertight:
            return placed, tool
    raise GeometryError(
        title=_("Der Hohlraum lässt sich an dieser Stelle nicht sauber ausschneiden."),
        detail=CUT_DID_NOT_HOLD,
        suggestions=(CORRECT_INPUT, CANCEL),
    )


#: Die Vielfachen von :data:`FEATURE_OVERLAP`, mit denen
#: :func:`_exact_chain_cut_holding` eine gescheiterte Differenz wiederholt.
CUT_OVERLAPS: Final = (1.0, 2.0, 3.0)

#: Der Satz, wenn keine Wiederholung einen dichten Körper ergibt.
CUT_DID_NOT_HOLD: Final = _(
    "Das Ergebnis bliebe dort offen, auch nach zwei weiteren Versuchen. Setzen Sie die "
    "Stelle um einen Bruchteil eines Millimeters anders und versuchen Sie es erneut."
)


def _exact_chain_tool_placed(
    solid: Any,
    entrance: _BoreEntrance,
    matrix: NDArray[np.float64],
    *,
    overlap: float = FEATURE_OVERLAP,
) -> Any:
    """Das Werkzeug der Kette, mit einer starren Bewegung an einen neuen Platz gebracht.

    Der Drehkörper ihrer Profile steht auf der bewegten Achse, die Randebenen
    wandern mit (:func:`_plane_placed`). Eine Spiegelung ist erlaubt: Der
    Drehkörper ist um seine Achse symmetrisch, und die Ebenen spiegeln mit.
    Verschieben (*Merkmal verdoppeln*) ist der Sonderfall ohne Drehung, das
    Merkmalsmuster der allgemeine.
    """
    from app.core.sketch.planes import frame_of

    origin = _moved_point(np.asarray(entrance.origin, dtype=float), matrix)
    axis = _vector_placed(np.asarray(entrance.axis, dtype=float), matrix)
    return _exact_chain_solid(
        entrance,
        solid.bounds.diagonal,
        filling=False,
        frame=frame_of(
            (float(axis[0]), float(axis[1]), float(axis[2])),
            (float(origin[0]), float(origin[1]), float(origin[2])),
        ),
        planes_of=lambda _index, lower, upper: (
            _plane_placed(lower, matrix),
            _plane_placed(upper, matrix),
        ),
        overlap=overlap,
    )


def _plane_placed(plane: SectionPlane, matrix: NDArray[np.float64]) -> SectionPlane:
    """Dieselbe Ebene nach einer starren Bewegung — auch einer Spiegelung.

    Für eine orthogonale Drehung ist die Normale ein Vektor wie jeder andere;
    der Abstand vom Ursprung kommt aus einem bewegten Punkt der Ebene.
    """
    normal = np.asarray(plane.normal, dtype=float)
    turned = _vector_placed(normal, matrix)
    point = _moved_point(normal * plane.position, matrix)
    return SectionPlane(
        normal=(float(turned[0]), float(turned[1]), float(turned[2])),
        position=math.fsum(float(a) * float(b) for a, b in zip(turned, point, strict=True)),
    )


def _moved_point(point: NDArray[np.float64], matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    """Ein Punkt nach einer 4x4-Bewegung — elementweise über
    :func:`~app.core.geom.transform.moved_points`, nicht über BLAS (RM-187)."""
    return cast(
        NDArray[np.float64],
        transform.moved_points(np.asarray([point], dtype=np.float64), matrix)[0],
    )


def _vector_placed(vector: NDArray[np.float64], matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    """Eine Richtung nach einer 4x4-Bewegung: nur deren Drehung, ohne Verschiebung."""
    turn = np.eye(4)
    turn[:3, :3] = np.asarray(matrix, dtype=np.float64)[:3, :3]
    return _moved_point(vector, turn)


def _exact_chain_tool_turned(
    solid: Any,
    entrance: _BoreEntrance,
    matrix: NDArray[np.float64],
    pivot: NDArray[np.float64],
    tilt: float,
    caps: Sequence[SectionPlane],
    *,
    overlap: float = FEATURE_OVERLAP,
) -> Any:
    """Das Werkzeug der gekippten Kette — mit dem Überstand, den die Neigung verlangt.

    Die Randebenen drehen mit; die Mündungen — die äußere der Senkung und
    die ferne einer durchgehenden Bohrung — rücken um so viel nach außen, wie
    ein Zylinder beziehungsweise Kegel braucht, um die vorher quer stehende
    Oberfläche nach dem Kippen noch zu durchstoßen
    (``_reach_past_a_tilted_face``, ``_cone_past_a_tilted_face``, dieselben
    Zahlen wie am Netz). Der Boden eines Sacklochs bleibt, wo er ist. Was
    dabei über die alten Ränder hinausragt, kappen ``caps``
    (:func:`_old_rim_caps`, RM-220).

    Weitet sich die Bohrung an beiden Enden (RM-245), sind beide Mündungen
    die äußeren Enden ihrer Seite: Die zweite rückt entlang ihrer eigenen
    Richtung nach außen, und der Schaft dazwischen hat keine eigene.
    """
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    at_most = float(solid.bounds.diagonal)
    axis = np.asarray(entrance.axis, dtype=float)
    turned_axis = matrix[:3, :3] @ axis
    origin = np.asarray(entrance.origin, dtype=float)
    turned_origin = matrix[:3, :3] @ (origin - pivot) + pivot
    first, last = entrance.sections[0], entrance.sections[-1]
    through = bool(first.feature.params.get("through")) and not entrance.back
    # Die Werkzeuge kommen als Schaft, die Erweiterungen der ersten Seite und
    # die der zweiten (``_entrance_tools``); das letzte jeder Seite trägt ihre
    # Mündung.
    front_mouth = len(entrance.sections) - 1
    back_mouth = front_mouth + len(entrance.back) - 1 if entrance.back else -1

    def outward(
        section: _EntranceSection, at: float, *, cone: bool, way: NDArray[np.float64]
    ) -> float:
        distance = abs(at - float((pivot - origin) @ way))
        if cone:
            half_angle = float(section.feature.params.get("angle", 0.0)) / 2.0
            return _cone_past_a_tilted_face(
                distance, section.outer_radius, half_angle, tilt, at_most=at_most
            )
        return (
            _reach_past_a_tilted_face(distance, section.outer_radius, tilt, at_most=at_most)
            - distance
        )

    def planes_of(index: int, lower: SectionPlane, upper: SectionPlane) -> tuple[SectionPlane, ...]:
        low_shift = (
            outward(first, first.start, cone=False, way=axis) if index == 0 and through else 0.0
        )
        high_shift = 0.0
        if index == front_mouth:
            high_shift = outward(last, last.end, cone=last.feature.kind == "cone", way=axis)
        elif index == back_mouth:
            far = entrance.back[-1]
            high_shift = outward(far, far.end, cone=far.feature.kind == "cone", way=-axis)
        return (
            _plane_turned(lower, matrix, pivot, low_shift),
            _plane_turned(upper, matrix, pivot, high_shift),
        )

    tool = _exact_chain_solid(
        entrance,
        at_most,
        filling=False,
        frame=frame_of(
            (float(turned_axis[0]), float(turned_axis[1]), float(turned_axis[2])),
            (float(turned_origin[0]), float(turned_origin[1]), float(turned_origin[2])),
        ),
        planes_of=planes_of,
        overlap=overlap,
    )
    return edit.clipped_bore_tool(tool, caps) if caps else tool


def _exact_move_chain(
    ctx: OpContext, source: SceneObject, feature: Feature, chain: Sequence[Feature], target: Vec3
) -> OpResult:
    """Bohrung samt Senkung am exakten Körper versetzen (P2.4)."""
    entrance = _exact_chain_entrance(source, chain)
    travel = np.asarray(target, dtype=float) - np.asarray(feature.params["centre"], dtype=float)
    ctx.progress(0.1, str(_("Der ganze Hohlraum wird geschlossen …")))
    filled = _exact_chain_filled(source, entrance)
    ctx.progress(0.6, str(_("Das Merkmal wird an seiner neuen Stelle gesetzt …")))
    placed, tool = _exact_chain_cut_moved(filled, entrance, travel)
    expected = [
        dataclasses.replace(
            related,
            params={
                **related.params,
                "centre": tuple(
                    float(v) for v in np.asarray(related.params["centre"], dtype=float) + travel
                ),
            },
            provenance="generated",
        )
        for related in chain
    ]
    findings = _edge_findings(as_mesh_data(filled), expected)
    findings += _without_opened_twice(
        _neighbour_bore_findings(source, feature, as_mesh_data(tool), ctx, moved=True), findings
    )
    floor = _floor_carried(
        source.mesh, chain[0], source.features, translation((travel[0], travel[1], travel[2]))
    )
    result = _exact_cavity_result(
        ctx,
        source,
        placed,
        op="move_feature",
        expected=[*expected, *([floor] if floor is not None else [])],
        findings=findings,
        mouths=_chain_mouths(chain),
    )
    result = _exact_through_checked(ctx, result, chain[0].id, tool, "move_feature")
    return _exact_mouth_checked(result, "move_feature", source, chain[0], travel)


def _exact_duplicate_chain(
    ctx: OpContext, source: SceneObject, feature: Feature, chain: Sequence[Feature], target: Vec3
) -> OpResult:
    """Bohrung samt Senkung am exakten Körper ein zweites Mal schneiden (P2.4)."""
    entrance = _exact_chain_entrance(source, chain)
    solid = _exact_body(source)
    travel = np.asarray(target, dtype=float) - np.asarray(feature.params["centre"], dtype=float)
    ctx.progress(0.2, str(_("Das Merkmal wird an der neuen Stelle angelegt …")))
    placed, tool = _exact_chain_cut_moved(solid, entrance, travel)
    taken: set[str] = {*source.reserved_feature_ids, *source.features}
    copies = []
    for related in chain:
        name = _free_id_among(taken, related.kind)
        taken.add(name)
        copies.append(
            dataclasses.replace(
                related,
                id=name,
                params={
                    **related.params,
                    "centre": tuple(
                        float(v) for v in np.asarray(related.params["centre"], dtype=float) + travel
                    ),
                },
                provenance="generated",
            )
        )
    findings = _edge_findings(as_mesh_data(solid), copies)
    findings += _without_opened_twice(
        _neighbour_bore_findings(source, feature, as_mesh_data(tool), ctx, moved=True, copy=True),
        findings,
    )
    nothing = without_effect(solid, placed, "difference", ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    result = _exact_copy_result(
        ctx,
        source,
        placed,
        copies,
        findings,
        mouths=_chain_mouths(copies),
    )
    result = _exact_through_checked(ctx, result, copies[0].id, tool, "duplicate_feature")
    return _exact_mouth_checked(result, "duplicate_feature", source, chain[0], travel)


def _exact_rotate_chain(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    chain: Sequence[Feature],
    axis: Axis,
    angle: float,
) -> OpResult:
    """Bohrung samt Senkung am exakten Körper kippen — um die Mitte des gewählten
    Abschnitts (P2.4)."""

    entrance = _exact_chain_entrance(source, chain)
    pivot = np.asarray(feature.params["centre"], dtype=float)
    matrix = np.asarray(
        transform.rotation(axis, angle, cast(Vec3, tuple(float(value) for value in pivot))),
        dtype=np.float64,
    )
    old_axis = np.asarray(entrance.axis, dtype=float)
    new_axis = matrix[:3, :3] @ old_axis
    tilt = math.degrees(math.acos(min(1.0, abs(float(old_axis @ new_axis)))))
    _sinks_must_close(chain, tilt, angle)
    ctx.progress(0.1, str(_("Der ganze Hohlraum wird geschlossen …")))
    filled = _exact_chain_filled(source, entrance)
    ctx.progress(0.6, str(_("Das Merkmal wird gedreht gesetzt …")))
    caps = _old_rim_caps(as_mesh_data(source.mesh), chain[0], source.features, chain)
    placed, tool = _exact_chain_cut_holding(
        filled,
        lambda overlap: _exact_chain_tool_turned(
            filled, entrance, matrix, pivot, tilt, caps, overlap=overlap
        ),
    )
    expected = []
    for related in chain:
        centre = np.asarray(related.params["centre"], dtype=float)
        turned_centre = matrix[:3, :3] @ (centre - pivot) + pivot
        params = {
            **related.params,
            "centre": tuple(float(v) for v in turned_centre),
            "axis": _turned(related, axis, angle),
        }
        expected.append(dataclasses.replace(related, params=params, provenance="generated"))
    findings = _edge_findings(as_mesh_data(filled), expected)
    # Dieselbe Nachbarwandprüfung wie am Netz (``_rotate_cavity_chain``) —
    # am exakten Körper fehlte sie (RM-220), und der Bericht schwieg, wo die
    # gekippte Senkung in die Bohrung daneben lief.
    findings += _without_opened_twice(
        _neighbour_bore_findings(source, feature, as_mesh_data(tool), ctx, turned=True), findings
    )
    floor = _floor_carried(source.mesh, chain[0], source.features, matrix)
    if floor is not None:
        expected.append(floor)
    result = _exact_cavity_result(
        ctx,
        source,
        placed,
        op="rotate_feature",
        expected=expected,
        findings=findings,
        mouths=_chain_mouths(chain),
    )
    return _exact_through_checked(ctx, result, chain[0].id, tool, "rotate_feature")


def _exact_through_checked(
    ctx: OpContext, result: OpResult, bore_id: FeatureId, tool: Any, op: str
) -> OpResult:
    """Am exakten Körper dieselbe Frage wie am Netz: Steht im Schlauch der
    Bohrung einer Kette wieder Material?

    Die Erkennung nennt eine Bohrung durchgehend, deren beide Enden offen sind
    — auch ein Ende in eine Senkung, die unter einem Deckel liegt. Um 1 mm
    entlang der Achse ins Material versetzt, lag die Senkung einer
    Durchgangsbohrung unter 0,98 mm Material; das Netz sagte „geht nicht mehr
    durch" (``_throughness_lost``), der exakte Körper nichts, und das Merkmal
    blieb durchgehend (RM-220, 25.09.2026). Gefragt wird deshalb hier dieselbe
    Säule am Netz-Zwilling des Ergebnisses, mit dem tatsächlichen Werkzeug als
    Grenze, und nur dort, wo die Erkennung noch „durchgehend" sagt.

    **Die Säule ist um die Facettengrenze schlanker.** Der Zwilling tesselliert
    die Bohrungswand mit Sehnen bis :data:`~app.core.units.MAX_FACET_SAG`
    innerhalb des Kreises; eine Säule mit dem Maß des Netzwegs traf sie und
    meldete an einer glatt gekippten Senkbohrung Material im Schlauch.
    """
    output = result.outputs[0]
    bore = output.features.get(bore_id)
    code = f"{op}.no_longer_through"
    if (
        bore is None
        or not bore.params.get("through")
        or any(finding.code == code for finding in result.findings)
    ):
        return result
    slim = dataclasses.replace(
        bore,
        params={
            **bore.params,
            "diameter": _bore_number(bore, "diameter") - 2.0 * MAX_FACET_SAG,
        },
    )
    lost = _throughness_lost(
        as_mesh_data(output.mesh),
        slim,
        _bore_vector(bore, "centre"),
        op,
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        tool=as_mesh_data(tool),
    )
    if not lost:
        return result
    features = {
        **output.features,
        bore_id: dataclasses.replace(bore, params={**bore.params, "through": False}),
    }
    return dataclasses.replace(
        result,
        outputs=[dataclasses.replace(output, features=features)],
        findings=[*result.findings, *lost],
    )


def _exact_mouth_checked(
    result: OpResult,
    op: str,
    source: SceneObject,
    feature: Feature,
    travel: NDArray[np.float64],
) -> OpResult:
    """:func:`_mouth_covered` am Netz-Zwilling des exakten Ergebnisses."""
    covered = _mouth_covered(
        op,
        as_mesh_data(source.mesh),
        as_mesh_data(result.outputs[0].mesh),
        feature,
        source.features,
        travel,
        result.findings,
    )
    if not covered:
        return result
    return dataclasses.replace(result, findings=[*result.findings, *covered])


def _exact_rigid_cut(
    source: SceneObject,
    solid: Any,
    feature: Feature,
    target: Vec3,
    axis: Vec3,
    travel: NDArray[np.float64],
) -> tuple[Any, Any]:
    """Bohrung oder Langloch am exakten Körper an ``target`` schneiden — starr
    mitbewegt, wie am Netz. Zurück kommen Ergebnis und Werkzeug.

    Eine Durchgangsbohrung bekommt dafür die ganze Zielhülle als Tiefe
    (``_exact_cavity_tool``) und endet an ihren alten Randebenen, um ``travel``
    mitbewegt (:func:`_moved_rims`). Ohne das bohrte sie an der neuen Stelle
    durch jede Wand auf ihrer Linie und blieb auch dort durchgehend, wo das Netz
    „geht nicht mehr durch" sagt — entlang ihrer Achse versetzt oder in
    dickeres Material (RM-220, 25.09.2026). Ohne flache Ränder bleibt es beim
    Hüllschnitt.
    """
    from app.core.brep import edit

    tool = _exact_cavity_tool(solid, feature, target, axis)
    if feature.params.get("through"):
        rims = _moved_rims(as_mesh_data(source.mesh), feature, source.features, travel)
        if len(rims) == 2:
            tool = edit.clipped_bore_tool(tool, rims)
    cut = edit.boolean("difference", [solid, tool])
    # Beim Langloch liegen die Flanken des Werkzeugs in der Ebene alter Flanken
    # (``_exact_cavity_cut``).
    return (edit.unified(cut) if feature.kind == "slot" else cut), tool


def _exact_remove_chain(
    ctx: OpContext, source: SceneObject, feature: Feature, chain: Sequence[Feature]
) -> OpResult:
    """Die ganze Kette am exakten Körper schließen (P2.4)."""
    entrance = _exact_chain_entrance(source, chain)
    ctx.progress(0.2, str(_("Der ganze Hohlraum wird geschlossen …")))
    filled = _exact_chain_filled(source, entrance)
    gone = tuple(section.id for section in chain)
    findings = [
        Finding(
            code="remove_feature.gone",
            severity="info",
            message=_(
                "Der Hohlraum ist mit allen seinen Abschnitten entfernt. Spätere "
                "Schritte und Passungen, die auf sie verweisen, finden sie nicht mehr."
            ),
            feature_ids=gone,
            values={"feature": feature.id, "kind": feature.kind, "removed": len(gone)},
        )
    ]
    return _exact_cavity_result(
        ctx,
        source,
        filled,
        op="remove_feature",
        expected=None,
        gone=gone,
        findings=findings,
        reserve=True,
    )


def _exact_chain_cut_kept(solid: Any, entrance: _BoreEntrance, removed: Feature) -> Any:
    """Die übrigen Abschnitte einer geschlossenen Kette frisch schneiden — exakt.

    Dieselben Werkzeuge wie beim Ändern (``_entrance_tools``), ohne das des
    entfernten Abschnitts. Was **hinter** ihm liegt, geht bis zur Mündung
    durch, sonst verlöre es seinen Weg nach außen; ein Kegel wird dabei über
    seinem Ende zum Zylinder seines weiten Radius — dasselbe, was der entlang
    der Achse gestapelte Abschnitt am Netz ergibt (``_section_closed``). Was
    **vor** ihm liegt, beginnt an seiner eigenen Randebene: Der entfernte
    Abschnitt darunter ist voll, und ein Kegel läuft nicht mehr in ihn hinein.

    Weitet sich die Bohrung an beiden Enden (RM-245), gilt das auf der Seite
    des entfernten Abschnitts, und der Schaft geht bis zu deren Mündung; die
    andere Seite wird geschnitten, wie sie war. Ihre Umrisse entstehen wie in
    :func:`_entrance_tools` entlang ihrer eigenen Richtung und werden danach
    gespiegelt.
    """
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    reach = float(solid.bounds.diagonal)
    frame = frame_of(entrance.axis, entrance.origin)
    parts = []
    for number, (_way, sections, open_end) in enumerate(entrance.sides()):
        names = [section.feature.id for section in sections]
        position = names.index(removed.id) if removed.id in names else None
        mouth = dataclasses.replace(
            sections[-1].upper, position=sections[-1].upper.position + FEATURE_OVERLAP
        )
        tools = _side_tools(
            sections,
            open_end,
            0.0,
            reach,
            filling=False,
            back=entrance.back if number == 0 else (),
            back_open=entrance.back_open,
        )
        for index, (outline, (lower, upper)) in enumerate(tools):
            if number and index == 0:
                # Der Schaft steht einmal da, bei der ersten Seite.
                continue
            if index == position:
                continue
            section = sections[index]
            if position is not None and index < position:
                upper = mouth
                if section.feature.kind == "cone":
                    wide, far = section.outer_radius, section.end + reach
                    outline = [outline[0], (wide, section.end), (wide, far), (0.0, far), outline[0]]
            elif position is not None:
                lower = section.lower
            elif index == 0 and entrance.back:
                # Entfernt wird auf der zweiten Seite: Der Schaft geht bis zu
                # deren Mündung durch, wie hier bis zur ersten.
                other = entrance.back[-1].upper
                lower = dataclasses.replace(other, position=other.position + FEATURE_OVERLAP)
            if number:
                outline = [(radius, -along) for radius, along in reversed(outline)]
            tool = edit.revolved_bore_tool(outline, frame)
            parts.append(edit.clipped_bore_tool(tool, (lower, upper)))
    tool = edit.boolean("union", parts) if len(parts) > 1 else parts[0]
    return edit.unified(edit.boolean("difference", [solid, tool]))


def _exact_remove_section(
    ctx: OpContext, source: SceneObject, feature: Feature, chain: Sequence[Feature]
) -> OpResult:
    """**Einen** Abschnitt einer Kette am exakten Körper schließen — der Rest bleibt offen (P2.4).

    Dieselbe Reihenfolge wie am Netz (``_section_closed``), aus denselben
    Gründen: Liegt etwas hinter dem Abschnitt, geht erst der ganze Hohlraum
    zu, und die übrigen Abschnitte werden aus dem vollen Material frisch
    geschnitten — die hinteren bis zur Mündung durch. Der innerste Abschnitt
    hat nichts hinter sich: Er wird aus seinen nativen Flächen gefüllt, und
    was vor ihm liegt, steht danach so, wie es stand — die Senkung über der
    gefüllten Bohrung ist ein Kegelstumpf mit ebenem Boden.
    """
    from app.core.brep import edit

    solid = _exact_body(source)
    inner = _inner_sections(chain, feature)
    ctx.progress(0.2, str(_("Der Abschnitt wird geschlossen …")))
    expected: list[Feature] = []
    if not inner:
        body = _exact_body_from_faces(source, feature)
        closed = edit.unified(edit.boolean("union", [solid, body]))
        # **Ohne die Bohrung geht keiner der übrigen Abschnitte mehr durch** —
        # sie war ihr Durchgang, und das ist der Sinn des Schritts. Die
        # Erkennung nennt eine Zylindersenkung aber bald durchgehend, bald
        # nicht (:func:`_free_along_the_axis`), und an einer Platte mit Stufen
        # an beiden Enden meldete der exakte Kern die obere danach „geht nicht
        # mehr durch" (RM-245, 25.09.2026); das Netz sagte nichts.
        expected.extend(
            dataclasses.replace(
                other,
                params={**other.params, "through": False},
                provenance="generated",
            )
            for other in chain
            if other.id != feature.id
        )
    else:
        entrance = _exact_chain_entrance(source, chain)
        filled = _exact_chain_filled(source, entrance)
        closed = _exact_chain_cut_kept(filled, entrance, feature)
        # Die Seite des entfernten Abschnitts (RM-245); die Abschnitte der
        # anderen stehen danach, wie sie standen.
        way, sections, _open = next(
            side
            for side in entrance.sides()
            if any(section.feature.id == feature.id for section in side[1])
        )
        position = next(
            index for index, section in enumerate(sections) if section.feature.id == feature.id
        )
        mouth_end = sections[-1].end
        origin = np.asarray(entrance.origin, dtype=float)
        axis = np.asarray(way, dtype=float)
        expected.extend(
            dataclasses.replace(other, provenance="generated")
            for other in chain
            if all(other.id != section.feature.id for section in sections)
        )
        for index, section in enumerate(sections):
            kept = section.feature
            if index == position:
                continue
            if index < position:
                if kept.kind != "hole":
                    # Ein Kegel hinter dem entfernten Abschnitt bekommt einen
                    # Zylinder über sich; was die Erkennung daraus macht, ordnet
                    # ``match`` zu — hier wird nichts vorweggenommen.
                    continue
                middle = origin + axis * (section.start + mouth_end) / 2.0
                kept = dataclasses.replace(
                    kept,
                    params={
                        **kept.params,
                        "centre": (float(middle[0]), float(middle[1]), float(middle[2])),
                        "depth": mouth_end - section.start,
                    },
                )
            expected.append(dataclasses.replace(kept, provenance="generated"))
    findings = [
        Finding(
            code="remove_feature.gone",
            severity="info",
            message=_(
                "Das Merkmal ist entfernt. Spätere Schritte und Passungen, die auf es "
                "verweisen, finden es nicht mehr."
            ),
            feature_ids=(feature.id,),
            values={"feature": feature.id, "kind": feature.kind, "removed": 1},
        )
    ]
    return _exact_cavity_result(
        ctx,
        source,
        closed,
        op="remove_feature",
        expected=expected,
        gone=(feature.id,),
        findings=findings,
        reserve=True,
    )


#: Die Merkmale, deren Körper der exakte Kern aus ihren nativen Flächen baut
#: (``brep.edit.solid_from_faces``) und so ohne Vernetzung versetzt, verdoppelt
#: und entfernt (P2.4): Zapfen, Kuppe und Kegelstumpf als Material, Senkung und
#: Pfanne als Hohlraum — was von beiden, sagt die Erkennung in ``recess``.
#: Gekippt werden Zapfen und Kegel (``_exact_rotate_pin``, ``_exact_rotate_cone``):
#: Der Körper reicht dabei in die Grundfläche hinein — die Senkung ins Freie —,
#: statt neben ihr zu schweben. Die Kugel hat keine Lage. Der Einschluss ist
#: immer Luft und hat keinen Rand: Sein Körper sind seine Schalen
#: (``brep.edit.void_body``), versetzt und gefüllt wie jeder Hohlraum.
EXACT_FACE_KINDS: Final = ("pin", "cone", "sphere", "void")


def _exact_body_from_faces(source: SceneObject, feature: Feature) -> Any:
    """Der Körper eines Merkmals aus seinen nativen Flächen — oder die Absage.

    Das exakte Gegenstück zu ``_body_from_faces``: ein Zapfen, eine Kuppe, ein
    Kegelstumpf — oder eine Senkung und eine Pfanne, die allein stehen. Bei
    einem Hohlraum ist der zweite Ring sein Boden; steht er nicht allein,
    kommt diese Funktion nicht vor (die Kette geht ihren eigenen Weg). Ein
    Einschluss hat keinen Rand: Seine Schalen sind sein Körper
    (``edit.void_body``), die Inseln darin ausgenommen.
    """
    from app.core.brep import edit

    solid = _exact_body(source)
    native = solid.faces_of_triangles(feature.face_indices) if feature.face_indices else ()
    body = None
    if native:
        body = (
            edit.void_body(solid, native)
            if feature.kind == "void"
            else edit.solid_from_faces(solid, native, allowed_rings=(1, 2))
        )
    if body is None:
        raise ValidationError(
            field="at_feature",
            detail=NO_BODY_FROM_FACES,
            values={"feature": feature.id, "kind": feature.kind},
            constraint="not_movable",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    return body


def _exact_pin_tool(feature: Feature, centre: Vec3, axis: Vec3, *, reach_below: float) -> Any:
    """Ein Zapfen aus seinen Kennzahlen, von der Spitze bis ``reach_below`` unter die Mitte.

    Beim Kippen um seine Mitte höbe die Zylinderbasis auf einer Seite von der
    Grundfläche ab; deshalb reicht der Körper unter der Mitte so weit, wie die
    Neigung verlangt (``_reach_past_a_tilted_face``), und die Vereinigung
    verschluckt, was im Material liegt.
    """
    from app.core.brep.edit import _oriented_cylinder

    diameter = _bore_number(feature, "diameter")
    depth = _bore_number(feature, "depth")
    unit = np.asarray(axis, dtype=float)
    unit /= float(np.linalg.norm(unit))
    start = np.asarray(centre, dtype=float) - unit * reach_below
    return _oriented_cylinder(
        (float(start[0]), float(start[1]), float(start[2])),
        (float(unit[0]), float(unit[1]), float(unit[2])),
        diameter / 2.0,
        reach_below + depth / 2.0,
    )


def _exact_move_by_faces(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    centre: Vec3,
    target: Vec3,
    *,
    cavity: bool,
) -> OpResult:
    """Ein Merkmal aus seinen Flächen am exakten Körper versetzen (P2.4).

    Dasselbe Paar wie am Netz: An der alten Stelle das Gegenteil dessen, was
    das Merkmal ist, an der neuen das Merkmal selbst — ein Zapfen wird
    abgetragen und angesetzt, eine Senkung gefüllt und geschnitten.
    """
    from app.core.brep import edit

    solid = _exact_body(source)
    body = _exact_body_from_faces(source, feature)
    travel: Vec3 = (target[0] - centre[0], target[1] - centre[1], target[2] - centre[2])
    ctx.progress(
        0.1,
        str(_("Das Merkmal wird an seiner alten Stelle geschlossen …"))
        if cavity
        else str(_("Das Merkmal wird an seiner alten Stelle abgetragen …")),
    )
    cleared = edit.unified(edit.boolean("union" if cavity else "difference", [solid, body]))
    ctx.progress(0.6, str(_("Das Merkmal wird an seiner neuen Stelle gesetzt …")))
    placed = edit.unified(
        edit.boolean("difference" if cavity else "union", [cleared, edit.moved(body, travel)])
    )
    expected = dataclasses.replace(
        feature, params={**feature.params, "centre": target}, provenance="generated"
    )
    # Dieselbe Frage wie am Netz (``move_feature`` mit ``_edge_findings``): Eine
    # Senkung, die über die Kante wandert, sagt es — bis zum 22.09.2026 gab der
    # Weg aus den Flächen hier keinen Befund zurück.
    findings = _edge_findings(as_mesh_data(cleared), [expected])
    return _exact_cavity_result(
        ctx, source, placed, op="move_feature", expected=expected, findings=findings
    )


def _exact_duplicate_by_faces(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    centre: Vec3,
    target: Vec3,
    *,
    cavity: bool,
) -> OpResult:
    """Ein Merkmal aus seinen Flächen am exakten Körper ein zweites Mal setzen (P2.4)."""
    from app.core.brep import edit

    solid = _exact_body(source)
    body = _exact_body_from_faces(source, feature)
    travel: Vec3 = (target[0] - centre[0], target[1] - centre[1], target[2] - centre[2])
    change: BooleanKind = "difference" if cavity else "union"
    ctx.progress(0.2, str(_("Das Merkmal wird an der neuen Stelle angelegt …")))
    placed = edit.unified(edit.boolean(change, [solid, edit.moved(body, travel)]))
    copy = dataclasses.replace(
        feature,
        id=_free_feature_id(source, feature.kind),
        params={**feature.params, "centre": target},
        provenance="generated",
    )
    findings: list[Finding] = _edge_findings(as_mesh_data(solid), [copy])
    nothing = without_effect(solid, placed, change, ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    return _exact_copy_result(ctx, source, placed, [copy], findings)


def _exact_resize_by_faces(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    centre: Vec3,
    diameter: float,
    scale: float,
) -> OpResult:
    """Zapfen, Kuppe oder Kegel am exakten Körper im neuen Maß (22.09.2026).

    Bis dahin ging *Merkmal ändern* an diesen drei Arten über das Netz, und
    der exakte Körper kam als Netz zurück — die Zusage aus P2.4, dass am
    exakten Körper keine Merkmalshandlung mehr vernetzt, stimmte an dieser
    einen Stelle nicht (die Paritätstabelle führte ``resize_feature`` als
    ``MESH``). Derselbe Weg wie am Netz: an der alten Stelle der Körper aus
    den nativen Flächen abgetragen beziehungsweise gefüllt, an derselben Stelle
    das Merkmal im neuen Maß gesetzt. Der Zapfen kommt aus Kennzahlen, mit
    derselben Höhe und dem Fuß in der Grundfläche (``_exact_pin_tool``);
    Kuppe und Kegel werden um ihre gemessene Mitte gestreckt, und die liegt in
    der Grundfläche beziehungsweise an der Mündung — dieselbe Streckung wie am
    Netz (``_tool_for`` mit ``scale``).
    """
    from app.core.brep import edit

    solid = _exact_body(source)
    cavity = is_a_cavity(feature)
    body = _exact_body_from_faces(source, feature)
    ctx.progress(
        0.1,
        str(_("Das Merkmal wird an seiner alten Stelle geschlossen …"))
        if cavity
        else str(_("Das Merkmal wird an seiner alten Stelle abgetragen …")),
    )
    ctx.cancelled.raise_if_cancelled()
    cleared = edit.unified(edit.boolean("union" if cavity else "difference", [solid, body]))
    ctx.cancelled.raise_if_cancelled()
    ctx.progress(0.6, str(_("Das Merkmal wird mit dem neuen Maß gesetzt …")))
    if feature.kind == "pin":
        outward = _toward_the_air(as_mesh_data(solid), feature)
        if outward is None:
            raise ValidationError(
                field="at_feature",
                detail=NO_BODY_FROM_FACES,
                values={"feature": feature.id, "kind": feature.kind},
                constraint="not_movable",
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        wider = dataclasses.replace(feature, params={**feature.params, "diameter": diameter})
        tool = _exact_pin_tool(
            wider,
            centre,
            cast(Vec3, tuple(float(value) for value in outward)),
            reach_below=_bore_number(feature, "depth") / 2.0,
        )
    else:
        tool = edit.transformed(
            body, as_transform(transform.scaling((scale, scale, scale), about=centre))
        )
    placed = edit.unified(edit.boolean("difference" if cavity else "union", [cleared, tool]))
    changed = dataclasses.replace(
        feature, params={**feature.params, "diameter": diameter}, provenance="generated"
    )
    findings = [
        *_widening_findings(source, feature, diameter),
        *_edge_findings(as_mesh_data(cleared), [changed]),
    ]
    return _exact_cavity_result(
        ctx, source, placed, op="resize_feature", expected=changed, findings=findings
    )


def _exact_remove_by_faces(
    ctx: OpContext, source: SceneObject, feature: Feature, *, cavity: bool
) -> OpResult:
    """Ein Merkmal aus seinen Flächen am exakten Körper wegnehmen (P2.4): ein Zapfen
    wird abgetragen, eine Senkung gefüllt."""
    from app.core.brep import edit

    solid = _exact_body(source)
    body = _exact_body_from_faces(source, feature)
    ctx.progress(
        0.2,
        str(_("Das Merkmal wird geschlossen …"))
        if cavity
        else str(_("Das Merkmal wird abgetragen …")),
    )
    cleared = edit.unified(edit.boolean("union" if cavity else "difference", [solid, body]))
    findings = [
        Finding(
            code="remove_feature.gone",
            severity="info",
            message=_(
                "Das Merkmal ist entfernt. Spätere Schritte und Passungen, die auf es "
                "verweisen, finden es nicht mehr."
            ),
            feature_ids=(feature.id,),
            values={"feature": feature.id, "kind": feature.kind, "removed": 1},
        )
    ]
    return _exact_cavity_result(
        ctx,
        source,
        cleared,
        op="remove_feature",
        expected=None,
        gone=(feature.id,),
        findings=findings,
        reserve=True,
    )


# --- Wulst und Kehle: ein Ring am Schaft, in beiden Kernen (P2.6) --------------------------
#
# Ein Torusmerkmal ist ein Wulst (Material) oder eine Kehle (Hohlraum) auf
# einem Schaft. Sein Werkzeug ist der **volle Ring** aus seinen Kennzahlen:
# vereinigt für den Wulst, abgezogen für die Kehle — was vom Ring im Schaft
# liegt, ist dort ohnehin Material oder wird ohnehin weggenommen. Nur das
# **Schließen an der alten Stelle** braucht mehr: Der volle Ring nähme dem
# Schaft eine Rille (Wulst) beziehungsweise setzte ihm einen Ring auf (Kehle).
# Exakt nimmt ``edit.defeatured`` die Ringfläche weg und lässt den Schaft
# weiterlaufen; am Netz wird der Ring an den Randringen der Ringfläche
# beschnitten (``_torus_tool_mesh``). Gemessen am Schaft Ø 20 mal 40 mit Wulst
# und Kehle R 10 / r 3: Entfernen trifft das Schaftvolumen auf 10⁻¹⁶,
# Versetzen um -8 das alte Volumen auf 10⁻¹⁶, in beiden Kernen (21.09.2026).
#
# Ein Ring, der der ganze Körper ist, hat keinen Schaft: Das Defeaturing gibt
# ihn unverändert zurück, am Netz hat seine Fläche keinen Rand — dann sagt die
# Absage, dass der Körper zu bewegen ist. Ein Torusstück, hinter dem sich die
# Nachbarn nicht treffen, ist nicht abzutrennen (Konzept §13.2: „ein nicht
# abtrennbarer Torusanteil ist kein vollständiges Ringwerkzeug").


def _torus_refusal(feature: Feature, *, whole: bool) -> ValidationError:
    return ValidationError(
        field="at_feature",
        detail=TORUS_IS_THE_BODY if whole else TORUS_NOT_SEPARABLE,
        values={"feature": feature.id, "kind": feature.kind},
        constraint="not_movable",
        suggestions=(CHANGE_SELECTION, CANCEL),
    )


def _torus_axis(feature: Feature, axis: Vec3 | None = None) -> np.ndarray:
    """Die Einheitsachse des Rings oder Gewindes — ohne gemessene Achse die Absage.

    Wie `_thread_frame` bei einer fehlenden Strecke: Eine Achse, die niemand
    gemessen hat, wird nicht geraten (Regel 21).
    """
    direction = np.asarray(axis if axis is not None else _bore_vector(feature, "axis"), dtype=float)
    length = float(np.linalg.norm(direction))
    if not math.isfinite(length) or length <= EPS_GEOM:
        raise ValidationError(
            field="at_feature",
            detail=FEATURE_WITHOUT_AXIS,
            values={"feature": feature.id, "kind": feature.kind},
            constraint="not_movable",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    return direction / length


def _torus_measures(
    feature: Feature, ring_diameter: float | None, tube_diameter: float | None
) -> tuple[float, float]:
    """Ring- und Rohrdurchmesser — die genannten oder die des Merkmals, geprüft."""
    ring = ring_diameter or _bore_number(feature, "diameter")
    tube = tube_diameter or _bore_number(feature, "tube_diameter")
    if tube <= EPS_GEOM or tube >= ring - EPS_GEOM:
        raise ValidationError(
            field="tube_diameter",
            detail=TORUS_TUBE_TOO_WIDE,
            values={"feature": feature.id, "diameter": ring, "tube_diameter": tube},
            constraint="torus_tube",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return ring, tube


def _torus_rims(
    mesh: MeshData, feature: Feature
) -> tuple[Any, np.ndarray, list[np.ndarray], list[list[int]]]:
    """Der Ausschnitt der Ringfläche, seine Randkanten und die zwei Randringe als Umläufe.

    Wulst und Kehle enden in zwei Kreisen auf dem Schaft, beide quer zur
    Achse und mit demselben Radius. Ohne Rand ist die Ringfläche der ganze
    Körper; mit anderen Rändern ist der Ring nicht abzutrennen — dann wird
    nichts geraten. Zurück kommen der Ausschnitt (mit eigenen Eckpunkten),
    seine Randkanten, je Ring die Randkanten und je Ring der Umlauf seiner
    Eckpunkte in Kantenfolge.
    """
    from app.core.perceive.relations import ring_in_order

    raw = mesh.raw
    chosen = np.unique(np.asarray(feature.face_indices, dtype=np.int64))
    if chosen.size == 0 or int(chosen.max()) >= len(raw.faces):
        raise _torus_refusal(feature, whole=False)
    patch = trimesh.Trimesh(
        vertices=raw.vertices, faces=np.asarray(raw.faces)[chosen], process=False
    )
    patch.remove_unreferenced_vertices()
    patch.merge_vertices()
    edges = patch.edges_sorted
    single = trimesh.grouping.group_rows(  # type: ignore[no-untyped-call]
        edges, require_count=1
    )
    rim = edges[single]
    rings = list(trimesh.graph.connected_components(rim)) if len(rim) else []
    if not rings:
        raise _torus_refusal(feature, whole=True)
    if len(rings) != 2:
        raise _torus_refusal(feature, whole=False)
    axis = _torus_axis(feature)
    centre = np.asarray(_bore_vector(feature, "centre"), dtype=float)
    points = np.asarray(patch.vertices, dtype=float)
    ring_edges: list[np.ndarray] = []
    loops: list[list[int]] = []
    radii: list[float] = []
    for component in rings:
        members = np.asarray(component, dtype=np.int64)
        belongs = np.isin(rim[:, 0], members) & np.isin(rim[:, 1], members)
        own = rim[belongs]
        if len(own) < 3:
            raise _torus_refusal(feature, whole=False)
        relative = points[members] - centre
        along = relative @ axis
        radial = np.linalg.norm(relative - np.outer(along, axis), axis=1)
        if (
            float(along.max() - along.min()) > FLAT_RIM
            or float(radial.max() - radial.min()) > FLAT_RIM
        ):
            raise _torus_refusal(feature, whole=False)
        loop = ring_in_order([(int(a), int(b)) for a, b in own])
        if len(loop) != len(members):
            raise _torus_refusal(feature, whole=False)
        ring_edges.append(own)
        loops.append(loop)
        radii.append(float(units.exact_mean(radial.tolist())))
    if abs(radii[0] - radii[1]) > FLAT_RIM:
        raise _torus_refusal(feature, whole=False)
    return patch, rim, ring_edges, loops


def _torus_ring_mesh(
    centre: Vec3, axis: Vec3, ring_diameter: float, tube_diameter: float
) -> MeshData:
    """Der volle Ring als Netz — das Werkzeug zum Setzen, wie ``brep.edit.torus``.

    Über ``lathe`` und den Rohrquerschnitt aus ``units.circle_point`` — nicht
    ``trimesh.creation.torus``, dessen Ecken ``np.cos`` je CPU anders rundet
    (RM-187).
    """
    body = ring_of_revolution(
        ring_diameter / 2.0, tube_diameter / 2.0, 2 * FEATURE_SECTIONS, FEATURE_SECTIONS
    )
    direction = np.asarray(axis, dtype=float)
    transform.moved(body, np.asarray(transform.rotation_between((0.0, 0.0, 1.0), direction)))
    body.apply_translation(np.asarray(centre, dtype=float))
    return MeshData.of(body)


def ring_of_revolution(major: float, minor: float, sections: int, tube_sections: int) -> Any:
    """Ein Ring um die Z-Achse, mittig im Ursprung — die Ecken auf jeder Maschine gleich.

    Der Rohrquerschnitt ist ein regelmäßiges Vieleck aus ``units.circle_point``,
    gedreht wird er über ``lathe.revolve``; dieselbe Topologie wie
    ``trimesh.creation.torus`` (geschlossene Kontur, ``tube_sections`` Stücke).
    """
    table = units.circle_cos_sin(int(tube_sections))
    outline = [[major + minor * cos, minor * sin] for cos, sin in table]
    outline.append(outline[0])
    return lathe.revolve(np.asarray(outline, dtype=np.float64), sections=int(sections))


def _torus_shaft_core(
    patch: Any, ring_edges: list[np.ndarray], loops: list[list[int]], axis: np.ndarray
) -> MeshData:
    """Der Schaftkern zwischen den Randringen: ein Band zwischen den Umläufen, je Ring ein Deckel.

    Das Band ist der Schaft, wo ihn die Ringfläche verdeckt — unsichtbar, also
    darf es ein Reißverschluss zwischen zwei Umläufen mit verschiedener
    Eckenzahl sein. Die Deckel sind dieselben Fächer wie in
    :func:`_body_from_faces`, damit sie sich in der Booleschen gegenseitig
    aufheben.
    """
    points = np.asarray(patch.vertices, dtype=float)
    hubs = [np.array(units.exact_centre(points[loop].tolist()), dtype=np.float64) for loop in loops]
    vertices = [points, hubs[0].reshape(1, 3), hubs[1].reshape(1, 3)]
    hub_index = [len(points), len(points) + 1]
    faces: list[np.ndarray] = []
    for edges, hub in zip(ring_edges, hub_index, strict=True):
        faces.append(np.column_stack([edges[:, 0], edges[:, 1], np.full(len(edges), hub)]))
    # Der Reißverschluss: beide Umläufe nach dem Winkel um die Achse geordnet
    # und Kante für Kante verbunden.
    into_frame = np.asarray(transform.rotation_between(axis, (0.0, 0.0, 1.0)))[:3, :3]
    ordered: list[list[int]] = []
    for loop, middle in zip(loops, hubs, strict=True):
        local = (into_frame @ (points[loop] - middle).T).T
        angles = np.arctan2(local[:, 1], local[:, 0])
        order = np.argsort(angles)
        ordered.append([loop[int(i)] for i in order])
    first, second = ordered
    band: list[list[int]] = []
    i = j = 0
    n1, n2 = len(first), len(second)
    angle_of = {}
    for loop, middle in zip(loops, hubs, strict=True):
        local = (into_frame @ (points[loop] - middle).T).T
        for index, angle in zip(loop, np.arctan2(local[:, 1], local[:, 0]), strict=True):
            angle_of[int(index)] = float(angle)
    while i < n1 or j < n2:
        a, b = first[i % n1], second[j % n2]
        next_a, next_b = first[(i + 1) % n1], second[(j + 1) % n2]
        angle_a = angle_of[next_a] + (2.0 * math.pi if i + 1 >= n1 else 0.0)
        angle_b = angle_of[next_b] + (2.0 * math.pi if j + 1 >= n2 else 0.0)
        if i < n1 and (j >= n2 or angle_a <= angle_b):
            band.append([a, next_a, b])
            i += 1
        else:
            band.append([a, next_b, b])
            j += 1
    faces.append(np.asarray(band, dtype=np.int64))
    core = trimesh.Trimesh(vertices=np.vstack(vertices), faces=np.vstack(faces), process=True)
    trimesh.repair.fix_normals(core)  # type: ignore[no-untyped-call]
    return MeshData.of(core)


def _torus_tool_mesh(mesh: MeshData, feature: Feature) -> MeshData:
    """Wulst oder Kehle als Netzwerkzeug an ihrer Stelle — aus den eigenen Dreiecken.

    Ein parametrischer Ring deckt sich nie mit der vorhandenen Ringfläche
    (andere Tessellierung) und hinterließe Splitter. Der Wulst ist deshalb der
    Körper aus den Dreiecken der Ringfläche mit zwei Deckeln
    (:func:`_body_from_faces`) **ohne** den Schaftkern zwischen den Randringen,
    die Kehle der Schaftkern **ohne** diesen Körper (:func:`_torus_shaft_core`).
    Beschnitten wird nur zum Schließen an der alten Stelle; gesetzt wird der
    volle Ring (:func:`_torus_ring_mesh`), wie im exakten Kern.
    """
    patch, _rim, ring_edges, loops = _torus_rims(mesh, feature)
    own = _body_from_faces(mesh, feature.face_indices, allowed_rings=(2,))
    if own is None:
        raise _torus_refusal(feature, whole=False)
    core = _torus_shaft_core(patch, ring_edges, loops, _torus_axis(feature))
    if not core.is_watertight or core.component_count != 1:
        raise _torus_refusal(feature, whole=False)
    cavity = is_a_cavity(feature)
    return boolean("difference", [core, own] if cavity else [own, core], quality="fine").mesh


def _exact_without_torus(source: SceneObject, feature: Feature) -> Any:
    """Der exakte Körper ohne Wulst oder Kehle — der Schaft läuft durch."""
    from app.core.brep import edit

    solid = _exact_body(source)
    native = solid.faces_of_triangles(feature.face_indices) if feature.face_indices else ()
    healed = edit.defeatured(solid, native) if native else None
    if healed is None:
        whole = bool(native) and len(set(native)) == solid.face_count
        raise _torus_refusal(feature, whole=whole)
    return healed


def _exact_torus_tool(
    feature: Feature,
    centre: Vec3,
    axis: Vec3 | None = None,
    *,
    ring_diameter: float | None = None,
    tube_diameter: float | None = None,
) -> Any:
    from app.core.brep import edit

    ring, tube = _torus_measures(feature, ring_diameter, tube_diameter)
    direction = _torus_axis(feature, axis)
    return edit.torus(
        centre, (float(direction[0]), float(direction[1]), float(direction[2])), ring, tube
    )


def _torus_closed_mesh(ctx: OpContext, source: SceneObject, feature: Feature) -> BooleanOutcome:
    """Das Netz ohne Wulst oder Kehle: der beschnittene Ring abgetragen beziehungsweise gefüllt."""
    body = as_mesh_data(source.mesh)
    tool = _torus_tool_mesh(body, feature)
    return boolean(
        "union" if is_a_cavity(feature) else "difference",
        [body, tool],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )


def _torus_placed_mesh(
    ctx: OpContext,
    base: MeshData,
    feature: Feature,
    centre: Vec3,
    axis: Vec3 | None = None,
    *,
    ring_diameter: float | None = None,
    tube_diameter: float | None = None,
) -> BooleanOutcome:
    """Der volle Ring an ``centre`` mit ``axis`` — Wulst vereinigt, Kehle abgezogen."""
    ring, tube = _torus_measures(feature, ring_diameter, tube_diameter)
    direction = _torus_axis(feature, axis)
    tool = _torus_ring_mesh(
        centre, (float(direction[0]), float(direction[1]), float(direction[2])), ring, tube
    )
    return boolean(
        "difference" if is_a_cavity(feature) else "union",
        [base, tool],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )


def _torus_result(
    source: SceneObject,
    placed: BooleanOutcome,
    features: dict[str, Feature],
    findings: list[Finding],
    *,
    reserve: bool = False,
    copy_id: str | None = None,
) -> OpResult:
    reserved = source.reserved_feature_ids
    if reserve or copy_id is not None:
        reserved = tuple(
            sorted(
                {*source.reserved_feature_ids, *source.features, *([copy_id] if copy_id else [])}
            )
        )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features=_without_old_triangles(features),
                reserved_feature_ids=reserved,
            )
        ],
        findings=findings,
        solver=placed.solver,
    )


def _move_torus(
    ctx: OpContext, source: SceneObject, feature: Feature, centre: Vec3, target: Vec3
) -> OpResult:
    """Wulst oder Kehle versetzen: an der alten Stelle der Schaft, an der neuen der Ring."""
    from app.core.brep import edit

    cavity = is_a_cavity(feature)
    moved = dataclasses.replace(
        feature, params={**feature.params, "centre": target}, provenance="generated"
    )
    ctx.progress(
        0.1,
        str(_("Das Merkmal wird an seiner alten Stelle geschlossen …"))
        if cavity
        else str(_("Das Merkmal wird an seiner alten Stelle abgetragen …")),
    )
    if source.kind == "brep":
        healed = _exact_without_torus(source, feature)
        ctx.progress(0.6, str(_("Das Merkmal wird an seiner neuen Stelle gesetzt …")))
        exact = edit.unified(
            edit.boolean(
                "difference" if cavity else "union", [healed, _exact_torus_tool(feature, target)]
            )
        )
        return _exact_cavity_result(
            ctx, source, exact, op="move_feature", expected=moved, findings=[]
        )
    closed = _torus_closed_mesh(ctx, source, feature)
    ctx.progress(0.6, str(_("Das Merkmal wird an seiner neuen Stelle gesetzt …")))
    placed = _torus_placed_mesh(ctx, closed.mesh, feature, target)
    return _torus_result(
        source,
        placed,
        {**source.features, feature.id: moved},
        [*closed.findings, *placed.findings],
    )


def _duplicate_torus(
    ctx: OpContext, source: SceneObject, feature: Feature, target: Vec3
) -> OpResult:
    """Wulst oder Kehle ein zweites Mal setzen — der volle Ring an der neuen Stelle."""
    from app.core.brep import edit

    cavity = is_a_cavity(feature)
    copy = dataclasses.replace(
        feature,
        id=_free_feature_id(source, feature.kind),
        params={**feature.params, "centre": target},
        provenance="generated",
    )
    ctx.progress(0.2, str(_("Das Merkmal wird an der neuen Stelle angelegt …")))
    change: BooleanKind = "difference" if cavity else "union"
    if source.kind == "brep":
        solid = _exact_body(source)
        placed_solid = edit.unified(
            edit.boolean(change, [solid, _exact_torus_tool(feature, target)])
        )
        findings: list[Finding] = []
        nothing = without_effect(solid, placed_solid, change, ctx.profile)
        if nothing is not None:
            findings.append(nothing)
        return _exact_copy_result(ctx, source, placed_solid, [copy], findings)
    body = as_mesh_data(source.mesh)
    placed = _torus_placed_mesh(ctx, body, feature, target)
    findings = [*placed.findings]
    nothing = without_effect(source.mesh, placed.mesh, change, ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    return _torus_result(
        source, placed, {**source.features, copy.id: copy}, findings, copy_id=copy.id
    )


def _rotate_torus(
    ctx: OpContext, source: SceneObject, feature: Feature, centre: Vec3, turned_axis: Vec3
) -> OpResult:
    """Wulst oder Kehle kippen — um die eigene Achse gedreht bleibt ein Ring, was er ist."""
    from app.core.brep import edit

    old_axis = _torus_axis(feature)
    new_axis = _torus_axis(feature, turned_axis)
    if abs(float(old_axis @ new_axis)) >= 1.0 - EPS_GEOM:
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="rotate_feature.unchanged",
                    severity="info",
                    message=_("Um seine eigene Achse gedreht sieht ein Ring aus wie vorher."),
                    feature_ids=(feature.id,),
                )
            ],
        )
    cavity = is_a_cavity(feature)
    turned = dataclasses.replace(
        feature, params={**feature.params, "axis": turned_axis}, provenance="generated"
    )
    ctx.progress(
        0.1,
        str(_("Das Merkmal wird an seiner alten Stelle geschlossen …"))
        if cavity
        else str(_("Das Merkmal wird an seiner alten Stelle abgetragen …")),
    )
    if source.kind == "brep":
        healed = _exact_without_torus(source, feature)
        ctx.progress(0.6, str(_("Das Merkmal wird gedreht gesetzt …")))
        exact = edit.unified(
            edit.boolean(
                "difference" if cavity else "union",
                [healed, _exact_torus_tool(feature, centre, turned_axis)],
            )
        )
        return _exact_cavity_result(
            ctx, source, exact, op="rotate_feature", expected=turned, findings=[]
        )
    closed = _torus_closed_mesh(ctx, source, feature)
    ctx.progress(0.6, str(_("Das Merkmal wird gedreht gesetzt …")))
    placed = _torus_placed_mesh(ctx, closed.mesh, feature, centre, turned_axis)
    return _torus_result(
        source,
        placed,
        {**source.features, feature.id: turned},
        [*closed.findings, *placed.findings],
    )


def _remove_torus(ctx: OpContext, source: SceneObject, feature: Feature) -> OpResult:
    """Wulst abtragen oder Kehle füllen — der Schaft läuft durch."""
    cavity = is_a_cavity(feature)
    ctx.progress(
        0.2,
        str(_("Das Merkmal wird geschlossen …"))
        if cavity
        else str(_("Das Merkmal wird abgetragen …")),
    )
    findings = [
        Finding(
            code="remove_feature.gone",
            severity="info",
            message=_(
                "Das Merkmal ist entfernt. Spätere Schritte und Passungen, die auf es "
                "verweisen, finden es nicht mehr."
            ),
            feature_ids=(feature.id,),
            values={"feature": feature.id, "kind": feature.kind, "removed": 1},
        )
    ]
    if source.kind == "brep":
        healed = _exact_without_torus(source, feature)
        return _exact_cavity_result(
            ctx,
            source,
            healed,
            op="remove_feature",
            expected=None,
            gone=(feature.id,),
            findings=findings,
            reserve=True,
        )
    closed = _torus_closed_mesh(ctx, source, feature)
    remaining = {name: entry for name, entry in source.features.items() if name != feature.id}
    return _torus_result(source, closed, remaining, [*closed.findings, *findings], reserve=True)


def _resize_torus(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    centre: Vec3,
    ring_diameter: float,
    tube_diameter: float,
) -> OpResult:
    """Ring- oder Rohrdurchmesser ändern: der alte Ring geht, der neue kommt."""
    from app.core.brep import edit

    ring, tube = _torus_measures(feature, ring_diameter, tube_diameter)
    if is_close(ring, _bore_number(feature, "diameter")) and is_close(
        tube, _bore_number(feature, "tube_diameter")
    ):
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="resize_feature.unchanged",
                    severity="info",
                    message=_("Das Merkmal hat dieses Maß schon."),
                    feature_ids=(feature.id,),
                )
            ],
        )
    cavity = is_a_cavity(feature)
    changed = dataclasses.replace(
        feature,
        params={**feature.params, "diameter": ring, "tube_diameter": tube},
        provenance="generated",
    )
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    if source.kind == "brep":
        healed = _exact_without_torus(source, feature)
        ctx.progress(0.6, str(_("Das Merkmal wird mit dem neuen Maß gesetzt …")))
        exact = edit.unified(
            edit.boolean(
                "difference" if cavity else "union",
                [
                    healed,
                    _exact_torus_tool(feature, centre, ring_diameter=ring, tube_diameter=tube),
                ],
            )
        )
        return _exact_cavity_result(
            ctx, source, exact, op="resize_feature", expected=changed, findings=[]
        )
    closed = _torus_closed_mesh(ctx, source, feature)
    ctx.progress(0.6, str(_("Das Merkmal wird mit dem neuen Maß gesetzt …")))
    placed = _torus_placed_mesh(
        ctx, closed.mesh, feature, centre, ring_diameter=ring, tube_diameter=tube
    )
    return _torus_result(
        source,
        placed,
        {**source.features, feature.id: changed},
        [*closed.findings, *placed.findings],
    )


# --- Gewinde: ändern und verschließen, in beiden Kernen (P2.6) --------------------------------
#
# Ein Gewinde ist eine bewendelte Strecke auf einem Schaft (außen) oder in
# einer Bohrung (innen), mit Mitte, Achse, Durchmesser, Steigung und Länge.
# Gearbeitet wird mit demselben Bausteingewinde wie beim Einsetzen
# (``build.threaded``, ``shapes.ridge_profile``), je Kern: **außen** nimmt
# das Entfernen den Gang zwischen Fuß- und Kammradius weg und lässt den Kern
# als glatten Schaft stehen; das Ändern nimmt die ganze Strecke als
# Hüllzylinder weg und vereinigt das neue Gewinde auf derselben Achse.
# **Innen** füllt das Entfernen die Strecke mit einem Zylinder über dem
# Kammradius — „Gewinde verschließen“ —, das Ändern füllt und schneidet mit
# dem neuen Innenwerkzeug. Gemessen an einer Platte 40 auf 40 auf 10 mit
# einem M6 mal 1 darauf und darin (21.09.2026): Gang weg auf 5 · 10⁻¹⁰,
# Hülle weg exakt, M8 mal 1,25 gesetzt auf 5 · 10⁻⁶ (das ist die
# Nähgenauigkeit des Gewindes
# selbst), Loch verschlossen exakt, auf M8 geschnitten auf 10⁻⁸; am Netz
# dieselben Schritte auf 3 · 10⁻⁴ gegen exakt, und beide Kerne erkennen das
# neue Gewinde danach mit 8,0 / 1,25.
#
# **Die Enden sind je nach Nachbarschaft anders.** Hinter einem Ende liegt
# Material (der Sockel eines aufgesetzten Gewindes, der Schaft eines Bolzens)
# oder Luft (die freie Spitze, die Mündung eines Gewindelochs). Ein
# aufgesetztes Bausteingewinde ist um ``BOOLEAN_OVERLAP`` in seinen Sockel
# eingesunken: Dort endet das äußere Werkzeug diese Spanne vor dem Sockel,
# sonst bliebe im Sockel ein Ring von einem Hundertstel. Wo Luft ist, reicht
# das äußere Werkzeug darüber hinaus (keine Haut an der Spitze), das innere
# **nicht** (kein Zapfen an der Mündung — dieselbe Lehre wie bei ``fill_bore``).


def _thread_frame(feature: Feature) -> tuple[np.ndarray, np.ndarray, float]:
    """Mitte, Einheitsachse und bewendelte Länge — oder die Absage ohne Strecke.

    Und die Absage am Kegel: Ändern und Entfernen gehen beide hier durch, und
    ihre Werkzeuge sind Zylinder.
    """
    if thread_is_tapered(feature):
        raise ValidationError(
            field="at_feature",
            detail=THREAD_TAPERED,
            values={"feature": feature.id},
            constraint="tapered",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    raw_length = feature.params.get("length", 0.0)
    length = float(raw_length) if isinstance(raw_length, int | float) else 0.0
    if not math.isfinite(length) or length <= EPS_GEOM:
        raise ValidationError(
            field="at_feature",
            detail=THREAD_WITHOUT_LENGTH,
            values={"feature": feature.id, "kind": feature.kind},
            constraint="not_movable",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    centre = np.asarray(_bore_vector(feature, "centre"), dtype=float)
    return centre, _torus_axis(feature), length


def _thread_corners(feature: Feature, source: SceneObject) -> tuple[np.ndarray, np.ndarray] | None:
    """Die Ecken der eigenen Dreiecke eines erkannten Netzgewindes: entlang der Achse, radial.

    Der Netzleser nennt Durchmesser, Steigung, Mitte und Strecke aus einem
    Fit über Dreiecksmitten — und der liegt am ISO-Korpus radial um die
    Sehnenhöhe innerhalb der Kammecken und axial um 0,08 mm neben der Stange
    (21.09.2026: 51 Kammsplitter, dann eine Scheibe am unteren Ende). Die
    Ecken sagen, wo das Gewinde wirklich ist. Ein exakter Körper und ein
    erzeugtes Gewinde brauchen das nicht: Dort sind die Zahlen die Wahrheit.
    """
    if source.kind == "brep" or not feature.face_indices:
        return None
    raw = as_mesh_data(source.mesh).raw
    corners = np.unique(np.asarray(raw.faces)[list(feature.face_indices)])
    relative = np.asarray(raw.vertices)[corners] - np.asarray(
        _bore_vector(feature, "centre"), dtype=float
    )
    axis = _torus_axis(feature)
    along = relative @ axis
    return along, np.linalg.norm(relative - np.outer(along, axis), axis=1)


def _thread_bounds(feature: Feature, source: SceneObject) -> tuple[float, float]:
    """Innerer und äußerer Radius der Gänge: gemessen, sonst aus dem Profil.

    Sortiert, nicht benannt: Der exakte Leser nennt am Innengewinde den
    Grund ``root`` und die Bohrung ``crest`` — gegenläufig zu
    ``shapes.ridge_profile``, wo innen der Fuß auf der Bohrung liegt. Wer
    „Fuß“ allein nähme, hätte je Quelle einen anderen Radius.

    Am Netz kommen die Grenzen eines **erkannten** Gewindes aus seinen eigenen
    Ecken, nicht aus dem Fit: Der misst an Dreiecksmitten, und die liegen um
    die Sehnenhöhe innerhalb der Kammecken — eine Hülle auf dem gemessenen
    Kamm ließ am ISO-Korpus 51 Kammsplitter außerhalb stehen (21.09.2026).
    """
    from app.core.knowledge.parts import shapes

    params = feature.params
    if "root_radius" in params and "crest_radius" in params:
        radii = (float(params["root_radius"]), float(params["crest_radius"]))
    else:
        profile = shapes.ridge_profile(
            _tool_diameter(
                _bore_number(feature, "diameter"),
                _bore_number(feature, "pitch"),
                internal=bool(params.get("internal", False)),
            ),
            _bore_number(feature, "pitch"),
            internal=bool(params.get("internal", False)),
        )
        radii = (profile[0][0], max(radial for radial, _axial in profile))
    inner, outer = min(radii), max(radii)
    corners = _thread_corners(feature, source)
    if corners is not None:
        along, radial = corners
        outer = max(outer, float(radial.max()))
        # Der Talgrund: nur Ecken, die eine Steigung von den Enden entfernt
        # liegen — die Stirnflächen der Stange zählen ihre Ecken sonst mit,
        # und ihr innerster Ring lag am ISO-Korpus bei 1,70 statt 2,39.
        clear = (float(along.max()) - float(along.min())) / 2.0 - _bore_number(feature, "pitch")
        middle = (float(along.max()) + float(along.min())) / 2.0
        deep = radial[np.abs(along - middle) < clear]
        if deep.size and float(deep.min()) > EPS_GEOM:
            inner = min(inner, float(deep.min()))
    return inner, outer


def _tool_diameter(diameter: float, pitch: float, *, internal: bool) -> float:
    """Das Maß, in dem ``build.threaded`` rechnet: außen der Kamm, innen die Bohrung.

    Ein Merkmal nennt innen die **Gewindebezeichnung**, also den Grund-Ø der
    Gänge — so schreibt es der Baustein (``fasteners._printed_thread`` baut mit
    ``nominal minus zwei Tiefen`` und meldet ``nominal``), so liest es der exakte
    Kern (``2·max(crest, root)``), so misst es das Netz. Das Werkzeug will die
    Bohrung darunter. Ohne diese Umrechnung wurde aus einer M6-Mutter beim
    Ändern der Steigung eine mit Bohrung Ø 6 (Review, 21.09.2026).
    """
    from app.core.knowledge.parts import shapes

    return diameter - 2.0 * pitch * shapes.RIDGE_SHARE if internal else diameter


def _thread_checked(feature: Feature, diameter: float, pitch: float) -> tuple[float, float]:
    """Der neue Durchmesser und die neue Steigung — die genannten oder die des Gewindes, geprüft."""
    from app.core.knowledge.parts import shapes

    if thread_is_left_handed(feature):
        raise ValidationError(
            field="at_feature",
            detail=THREAD_LEFT_HANDED,
            values={"feature": feature.id, "handedness": feature.params.get("handedness")},
            constraint="left_handed",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    starts = feature.params.get("starts", 1)
    if isinstance(starts, int | float) and starts > 1:
        raise ValidationError(
            field="at_feature",
            detail=THREAD_MULTI_START,
            values={"feature": feature.id, "starts": int(starts)},
            constraint="multi_start",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    wanted_pitch = pitch or _bore_number(feature, "pitch")
    if wanted_pitch <= EPS_GEOM or wanted_pitch * shapes.RIDGE_SHARE >= diameter / 2.0 - EPS_GEOM:
        raise ValidationError(
            field="pitch",
            detail=THREAD_PITCH_TOO_STEEP,
            values={"feature": feature.id, "diameter": diameter, "pitch": wanted_pitch},
            constraint="thread_pitch",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return diameter, wanted_pitch


def _material_at(source: SceneObject, point: np.ndarray) -> bool:
    """Liegt dieser Punkt im Material des Körpers — je Kern gefragt.

    Am Netz über ``mesh.on_surface`` und die Normale des nächsten Dreiecks —
    nicht ``trimesh.contains``, das durch ``rtree`` führt (die Lehre von
    ``prepare._flank_is_open``).
    """
    if source.kind == "brep":
        from OCP.BRepClass3d import BRepClass3d_SolidClassifier
        from OCP.gp import gp_Pnt
        from OCP.TopAbs import TopAbs_IN, TopAbs_ON

        classifier = BRepClass3d_SolidClassifier(
            _exact_body(source).shape, gp_Pnt(*(float(v) for v in point)), EPS_GEOM
        )
        return classifier.State() in (TopAbs_IN, TopAbs_ON)
    from app.core.geom.mesh import on_surface

    raw = as_mesh_data(source.mesh).raw
    flat = np.asarray(point, dtype=float).reshape(1, 3)
    closest, _distance, triangle = on_surface(raw, flat)
    outward = float(np.dot(flat[0] - closest[0], np.asarray(raw.face_normals)[triangle[0]]))
    return outward <= EPS_GEOM


def _thread_span(
    source: SceneObject, feature: Feature, *, outside: bool, internal: bool
) -> tuple[np.ndarray, np.ndarray, float, float, float, float]:
    """Mitte, Achse, Anfang und Ende der Gänge und die Enden des Werkzeugs — alles entlang
    der Achse, relativ zur Mitte.

    ``outside`` sagt, ob das Werkzeug abträgt (Gang weg, Hülle weg, neu
    schneiden) oder füllt; ``internal``, ob das Gewinde in einer Bohrung sitzt.
    Hinter einem Ende mit **Material** endet nur das abtragende Werkzeug eines
    aufgesetzten Bausteingewindes um ``BOOLEAN_OVERLAP`` früher — es ist um
    diese Spanne in seinen Sockel eingesunken, und darüber hinaus schnitte es
    ihn an; jedes andere abtragende Werkzeug endet dort bündig, und ein
    Stopfen greift um die Spanne ins Material, sonst bleibt eine Scheibe der
    Gänge als eingeschlossener Hohlraum stehen (Review, 21.09.2026: 0,28 mm³
    in zwei Teilen). Hinter **Luft** reicht das abtragende Werkzeug hinaus, der
    Stopfen nicht (kein Zapfen an der Mündung — die Lehre von ``fill_bore``).
    """
    centre, axis, length = _thread_frame(feature)
    low, high = -length / 2.0, length / 2.0
    corners = _thread_corners(feature, source)
    if corners is not None:
        # Die Strecke aus den Ecken: Der Fit legt Mitte und Länge daneben —
        # am ISO-Korpus 0,08 mm über das obere Ende hinaus.
        along = corners[0]
        low, high = float(along.min()), float(along.max())
    sunk = feature.provenance == "generated" and not internal
    ends = []
    for sign, edge in ((-1.0, low), (1.0, high)):
        probe = centre + axis * (edge + sign * 2.0 * BOOLEAN_OVERLAP)
        material = _material_at(source, probe)
        if material:
            reach = (-BOOLEAN_OVERLAP if sunk else 0.0) if outside else BOOLEAN_OVERLAP
        else:
            reach = BOOLEAN_OVERLAP if outside else 0.0
        ends.append(edge + sign * reach)
    return centre, axis, low, high, ends[0], ends[1]


def _along_axis(centre: np.ndarray, axis: np.ndarray, body: Any, start: float) -> Any:
    """Einen entlang Z ab null gebauten Körper auf die Achse legen, mit dem Anfang bei ``start``."""
    from app.core.geom.ops import as_transform

    turn = np.asarray(transform.rotation_between((0.0, 0.0, 1.0), axis), dtype=float)
    origin = centre + axis * start
    matrix = translation((float(origin[0]), float(origin[1]), float(origin[2]))) @ turn
    if isinstance(body, MeshData):
        raw = body.raw.copy()
        transform.moved(raw, matrix)
        return MeshData.of(raw)
    from app.core.brep import edit

    return edit.transformed(body, as_transform(matrix))


def _shapes_moved(body: Any, along: float) -> Any:
    """Ein Werkzeug entlang Z verschoben — die Netzseite von ``edit.moved``."""
    from app.core.knowledge.parts import shapes

    return shapes.moved(body, (0.0, 0.0, along))


def _thread_cylinder(diameter: float, height: float, kind: str) -> Any:
    """Ein Zylinder ab null entlang Z, je Kern — Hülle, Stopfen oder Kernstab eines Gewindes."""
    from app.core.knowledge.parts import shapes

    if kind == "brep":
        with shapes.building("brep"):
            return shapes.cylinder(diameter, height)
    return shapes.cylinder(diameter, height)


def _thread_body(diameter: float, pitch: float, length: float, *, internal: bool, kind: str) -> Any:
    """Kern und Gang des Bausteingewindes ab null entlang Z, je Kern."""
    from app.core.knowledge.parts import build, shapes

    if kind == "brep":
        with shapes.building("brep"):
            return build.threaded(diameter, pitch, length, internal=internal)
    return build.threaded(diameter, pitch, length, internal=internal)


def _combined(
    source: SceneObject,
    ctx: OpContext,
    kind: BooleanKind,
    base: Any,
    tool: Any,
    *,
    allow_empty: bool = False,
) -> Any:
    """Eine Boolesche je Kern: exakt über ``edit``, am Netz über die Rückfallkette."""
    if source.kind == "brep":
        from app.core.brep import edit

        return edit.unified(edit.boolean(kind, [base, tool]))
    return boolean(
        kind,
        [base, tool],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
        allow_empty=allow_empty,
    )


def _thread_result(
    ctx: OpContext,
    source: SceneObject,
    body: Any,
    feature: Feature,
    changed: Feature | None,
    findings: list[Finding],
) -> OpResult:
    """Das Ende beider Gewindehandlungen: prüfen, Merkmale fortführen, das neue benennen.

    Am exakten Körper sucht ``_exact_features_after`` das geänderte Gewinde an
    seiner Stelle und stellt den Übergang nur aus, wenn es dort steht — ein
    behaupteter Übergang ließ die native Erkennung daneben ein zweites
    Gewinde unter frischem Namen anlegen (Review, 21.09.2026: ``thread_1``
    erkannt neben ``thread_2`` gesetzt). Gefunden trägt es die gesetzten
    Zahlen weiter, nicht die gelesenen: Provenienz schlägt Erkennung (§21.2).
    """
    if source.kind == "brep":
        checked = _exact_body_checked(body)
        features, continued, lost = _exact_features_after(
            source, checked, expected=changed, gone=(feature.id,), cancelled=ctx.cancelled
        )
        if changed is not None:
            if changed.id in lost:
                findings.append(_cavity_lost_finding("resize_feature", changed))
            else:
                features = {**features, changed.id: changed}
        return OpResult(
            outputs=[
                dataclasses.replace(
                    source,
                    mesh=checked,
                    kind="brep",
                    features=features,
                    reserved_feature_ids=tuple(
                        sorted({*source.reserved_feature_ids, *source.features})
                    ),
                )
            ],
            findings=findings,
            feature_continuations=(
                tuple(
                    FeatureContinuation(FeatureRef(source.id, old_id), new_id)
                    for old_id, new_id in continued
                ),
            ),
        )
    features = {name: entry for name, entry in source.features.items() if name != feature.id}
    if changed is not None:
        features[changed.id] = changed
    return _torus_result(source, body, features, [*body.findings, *findings], reserve=True)


def _remove_thread(ctx: OpContext, source: SceneObject, feature: Feature) -> OpResult:
    """Gewinde entfernen: außen auf den Kern zurück, innen die Bohrung schließen."""
    internal = bool(feature.params.get("internal", False))
    centre, axis, _low, _high, start, stop = _thread_span(
        source, feature, outside=not internal, internal=internal
    )
    inner, outer = _thread_bounds(feature, source)
    reach = stop - start
    base = _exact_body(source) if source.kind == "brep" else as_mesh_data(source.mesh)
    if internal:
        ctx.progress(0.2, str(_("Das Merkmal wird geschlossen …")))
        # Der Stopfen greift um den Überlapp ins Material: Bündig mit dem Kamm
        # der Gänge zerfiel die Vereinigung am Netz in 454 Splitter (21.09.2026).
        plug = _thread_cylinder(2.0 * outer + 2.0 * BOOLEAN_OVERLAP, reach, source.kind)
        body = _combined(source, ctx, "union", base, _along_axis(centre, axis, plug, start))
    else:
        ctx.progress(0.2, str(_("Das Merkmal wird abgetragen …")))
        # Ein **gemessener** Fußradius trägt die Unsicherheit des Lesers: Ein
        # Kernwerkzeug genau darauf ließ am ISO-Korpus exakt eine Rille von der
        # Tiefe dieser Unsicherheit stehen und am Netz 52 Splitter zwischen
        # Sehne und Talgrund (21.09.2026). Der Kern bleibt deshalb um den
        # Überlapp unter dem gemessenen Fuß; ein gesetzter Fuß ist exakt.
        core_radius = inner if feature.provenance == "generated" else inner - BOOLEAN_OVERLAP
        sleeve = _thread_cylinder(2.0 * outer + 2.0 * BOOLEAN_OVERLAP, reach, source.kind)
        core = _thread_cylinder(2.0 * core_radius, reach + 2.0 * BOOLEAN_OVERLAP, source.kind)
        if source.kind == "brep":
            from app.core.brep import edit

            ring: Any = edit.boolean(
                "difference", [sleeve, edit.moved(core, (0.0, 0.0, -BOOLEAN_OVERLAP))]
            )
        else:
            ring = boolean(
                "difference",
                [sleeve, _shapes_moved(core, -BOOLEAN_OVERLAP)],
                quality=ctx.quality,
                seed=ctx.seed,
                cancelled=ctx.cancelled,
            ).mesh
        body = _combined(source, ctx, "difference", base, _along_axis(centre, axis, ring, start))
    findings = [
        Finding(
            code="remove_feature.gone",
            severity="info",
            message=_(
                "Das Gewinde ist entfernt: außen bleibt der Kern, innen ist die Bohrung "
                "geschlossen. Spätere Schritte, die auf es verweisen, finden es nicht mehr."
            ),
            feature_ids=(feature.id,),
            values={"feature": feature.id, "kind": feature.kind, "removed": 1},
        )
    ]
    return _thread_result(ctx, source, body, feature, None, findings)


#: Was ein Muster, das Solidon nicht selbst zeichnet, zum Ändern braucht.
#:
#: Bis zum 22.09.2026 war das eine Absage („lassen sich nicht neu setzen"),
#: und die Zeile stand grau. Seither ersetzt *Merkmal ändern* ein fremdes
#: Muster durch einen der eigenen Stile — der Satz nennt das Feld dafür.
PATTERN_NOT_DRAWABLE: Final = _(
    "Dieses Muster ist keines, das Solidon zeichnet. Wählen Sie unter „Musterstil“ "
    "Wabe, Rändel, Rippe, Welle, Noppe, Voronoi oder Rauschen — dann wird es damit "
    "auf derselben Fläche neu gesetzt; „Merkmal entfernen“ füllt es."
)

#: Warum die Zellen eines Musters am Netz nicht nachgezeichnet werden konnten.
PATTERN_NOT_READABLE: Final = _(
    "Die Zellen dieses Musters lassen sich am Netz nicht nachzeichnen — ihre Ränder "
    "schließen sich nicht zu Umrissen. Reparieren Sie das Netz und versuchen Sie es "
    "dann noch einmal."
)


def _pattern_plug(source: SceneObject, feature: Feature) -> MeshData:
    """Der Körper, der die Zellen eines Musters füllt oder abträgt — oder der Satz dazu."""
    from app.core.perceive.patterns import plug_for

    plug = plug_for(as_mesh_data(source.mesh), feature, source.features)
    if plug is None:
        # Der Satz nennt das Reparieren — dann steht es auch als Handlung da,
        # wie an jeder anderen Stelle, die das Netz nicht lesen konnte.
        raise ValidationError(
            field="at_feature",
            detail=PATTERN_NOT_READABLE,
            values={"feature": feature.id},
            constraint="not_movable",
            suggestions=(REPAIR_AND_RETRY, CANCEL),
        )
    return plug


def _pattern_cleared(ctx: OpContext, source: SceneObject, feature: Feature) -> BooleanOutcome:
    """Der Körper ohne sein Muster: vertiefte Zellen gefüllt, erhabene abgetragen.

    Am Netz, auch an einem exakten Körper — wie ``apply_texture`` selbst, das
    ein Muster nur als Netz aufbringt (``result_kind="mesh"``): Was als Netz
    kam, geht als Netz.
    """
    engraved = feature.params.get("mode") != "raised"
    ctx.progress(
        0.2,
        str(_("Die Zellen werden gefüllt …") if engraved else _("Die Zellen werden abgetragen …")),
    )
    # **Die Narben müssen weg, sonst wächst das Netz beim Aufräumen.** Ein
    # Muster hat viele Zellen, und jede hinterlässt beim Schließen ihre
    # Schnittkanten: Gemessen am Noppenfeld um den Griff 26 094 Dreiecke mit
    # Muster und 66 522 ohne — das Entfernen machte das Netz zweieinhalbmal
    # so groß wie das Aufbringen. Mit dem Zusammenlegen sind es 380, und der
    # rohe Zylinder hatte 384. Das ist nicht nur eine Zahl: An 66 522
    # Dreiecken zerlegte die Merkmalserkennung denselben Mantel auf Linux in
    # 46 Flecken und auf Windows in einen Zapfen (CI seit `2061def3`).
    return _without_scars(
        boolean(
            "union" if engraved else "difference",
            [as_mesh_data(source.mesh), _pattern_plug(source, feature)],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
    )


def _remove_pattern(ctx: OpContext, source: SceneObject, feature: Feature) -> OpResult:
    """Ein Muster entfernen: jede Zelle an ihrer Mündung schließen (§21.1, RM-207)."""
    cleared = _pattern_cleared(ctx, source, feature)
    count = int(feature.params.get("count", 0)) + int(feature.params.get("partial", 0))
    findings = [
        *cleared.findings,
        Finding(
            code="remove_feature.gone",
            severity="info",
            message=_(
                "Das Muster ist entfernt: {count} Zellen sind geschlossen. Spätere Schritte "
                "und Passungen, die auf es verweisen, finden es nicht mehr.",
                count=count,
            ),
            feature_ids=(feature.id,),
            values={"feature": feature.id, "kind": feature.kind, "removed": 1, "cells": count},
        ),
    ]
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=cleared.mesh,
                features=_without_old_triangles(source.features, without=(feature.id,)),
                reserved_feature_ids=tuple(
                    sorted({*source.reserved_feature_ids, *source.features})
                ),
            )
        ],
        findings=findings,
        solver=cleared.solver,
    )


def _pattern_anchor(feature: Feature, field: Field) -> tuple[float, float] | None:
    """Die Mitte einer gelesenen Zelle in den Achsen des Feldes — wohin eine neue Zelle kommt."""
    anchor = feature.params.get("anchor")
    if anchor is None:
        return None
    return field.flat(anchor)


def _resize_pattern(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    pitch: float,
    cell_width: float,
    cell_depth: float,
    *,
    style: str = "other",
) -> OpResult:
    """Ein Muster mit neuer Teilung, Zellbreite oder Tiefe: schließen, dann neu zeichnen.

    Derselbe Weg wie beim Gewinde — an der alten Stelle schließen, mit dem
    neuen Maß setzen —, und das Neue zeichnet dieselbe Funktion, die
    ``apply_texture`` benutzt (``texture_ops.flat_tool``): Ein gelesenes
    Muster wird mit seinem Stil, seinem Feld, seiner Drehung und seiner
    Zellbreite wieder erzeugt, nicht mit den Vorgaben der Operation, und das
    Feld legt es ab, wo es lag — auf der Ebene oder um den Zylinder
    (``patterns.Field.placed``). Null in einem Feld heißt: so lassen, wie
    gemessen.

    **Und ``style`` wechselt den Stil** — auch den eines fremden Musters, das
    Solidon selbst nicht zeichnet (``other``): Seine Zellen gehen zu, und auf
    derselben Fläche entsteht der gewählte Stil mit der gemessenen Teilung. Ein
    Schritt, ein Undo — bis zum 22.09.2026 war ein fremdes Muster nur
    entfernbar. Ohne gewählten Stil sagt die Operation, was fehlt, statt einen
    zu raten (Regel 21). Die Zellbreite gehört zum alten Stil; wer wechselt,
    bekommt die des neuen, solange er keine nennt.
    """
    from app.core.geom.texture_ops import (
        STRIP_PATTERNS,
        cell_width_for,
        check_printable,
        flat_tool,
        wrap_pitch,
    )
    from app.core.perceive.patterns import GENERATOR_OF, field_outline

    read_style = str(feature.params.get("style", "other"))
    wanted_style = style if style and style != "other" else read_style
    generator = GENERATOR_OF.get(wanted_style)
    if generator is None:
        raise ValidationError(
            field="style",
            detail=PATTERN_NOT_DRAWABLE,
            values={"feature": feature.id, "style": read_style},
            constraint="pattern_style",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    restyled = wanted_style != read_style
    measured_pitch = float(feature.params.get("pitch", 0.0))
    measured_width = float(feature.params.get("cell_width", 0.0))
    measured_depth = float(feature.params.get("cell_depth", 0.0))
    new_pitch = pitch if pitch > 0.0 else measured_pitch
    new_width: float | None = (
        cell_width if cell_width > 0.0 else (None if restyled else measured_width)
    )
    new_depth = cell_depth if cell_depth > 0.0 else measured_depth
    if (
        not restyled
        and is_close(new_pitch, measured_pitch)
        and is_close(new_width or 0.0, measured_width)
        and is_close(new_depth, measured_depth)
    ):
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="resize_feature.unchanged",
                    severity="info",
                    message=_("Das Merkmal hat dieses Maß schon."),
                    feature_ids=(feature.id,),
                )
            ],
        )
    _reject_oversized("pitch", new_pitch, source.mesh, kind="length")
    # Voronoi und Rauschen kennen keine Zellbreite — ihre Zellen sind so groß,
    # wie die Dichte sie macht (``texture_ops.pattern_shapes``). Und eine
    # Breite, die die Teilung nicht hergibt, wird begrenzt und gesagt: Die
    # Wand zwischen zwei Zellen bleibt so breit wie das kleinste Detail des
    # Druckers (E1: die Bahn bei FDM, der Bildpunkt bei Resin) — dünner
    # druckt sie nicht, und ``check_printable`` fragt nur nach dem Steg der
    # Vorgabe, nicht nach der gemessenen Zelle.
    printer = ctx.profile.printer
    detail = printer.smallest_detail
    drawn_width = cell_width_for(generator, new_pitch, new_width, wall=detail)
    limited = (
        drawn_width is not None and new_width is not None and not is_close(drawn_width, new_width)
    )
    if drawn_width is not None and drawn_width < detail:
        raise ValidationError(
            "cell_width",
            # Das Maß steht in den Einzelheiten als „Düse" — nicht als Schlüssel
            # im Satz (Durchsicht 0.5.0).
            _(
                "Bei dieser Zellbreite sind die Zellen schmaler als ein Bildpunkt — sie "
                "werden nicht belichtet."
            )
            if printer.is_resin
            else _(
                "Bei dieser Zellbreite sind die Zellen schmaler als die Düse — sie werden "
                "nicht gedruckt."
            ),
            value=drawn_width,
            constraint="nozzle_width",
            values={"nozzle_mm": detail, "cell_width": drawn_width},
            suggestions=[dataclasses.replace(CORRECT_INPUT, label=_("Zellbreite vergrößern"))],
        )
    # Dieselbe Frage wie beim Aufbringen (E1), mit der gezeichneten Zelle:
    # Steg oder Rille, je nachdem, was an diesem Stil schmaler ist.
    check_printable(generator, new_pitch, new_depth, ctx.profile.printer, cell=drawn_width)

    cleared = _pattern_cleared(ctx, source, feature)
    ctx.progress(0.6, str(_("Das Muster wird mit dem neuen Maß gesetzt …")))
    field = field_outline(as_mesh_data(source.mesh), feature, source.features)
    if field.around > 0.0:
        # Einmal um den Zylinder geht die Teilung im Umfang auf — wie beim
        # Aufbringen (``texture_ops.wrap_pitch``), sonst träfe an der Naht
        # die letzte Zelle auf die erste.
        new_pitch = wrap_pitch(generator, new_pitch, field.around / math.pi, field.around)
    engraved = feature.params.get("mode") != "raised"
    through = bool(feature.params.get("through", False))
    anchor = _pattern_anchor(feature, field)
    # Durchgehend bleibt es nur mit der gemessenen Tiefe — die ist die Dicke
    # des Körpers. Wer an einem durchgehenden Muster eine Tiefe setzt, macht
    # es blind, und das Merkmal sagt das danach auch.
    still_through = through and cell_depth <= 0.0
    flat = flat_tool(
        field.outline,
        pattern=generator,
        pitch=new_pitch,
        # Eine durchgehende Zelle wird durch die Rückseite hindurch
        # geschnitten: Ein Werkzeug, das bündig mit ihr endet, ließe dort eine
        # Haut stehen, sobald die Rechnung nicht mehr exakt ist. Anders als der
        # Stopfen darf das Schneidwerkzeug über den Körper hinausreichen.
        depth=new_depth + BOOLEAN_OVERLAP if still_through else new_depth,
        mode="engraved" if engraved else "raised",
        seed=ctx.seed or 0,
        # Die gezeichnete Breite, nicht die verlangte: Aus ihr rechnet
        # ``tool_in_outline`` die Wand, um die ganze Zellen vom Rand
        # wegbleiben — mit 9 mm verlangt bei 6 mm Teilung wäre die Wand
        # negativ, also keine, und die Zellen schnitten die Seitenwand an.
        cell=drawn_width,
        wall=detail,
        # Ganze Zellen, wo das Muster nur ganze hatte — und immer, wo es
        # durchgeht: Eine angeschnittene wäre dort eine Kerbe (Review,
        # 22.09.2026: ein blindes Feld nahe der Kante kerbte beim Neuzeichnen
        # mit weiterer Teilung die Seitenwände). Nicht bei Streifen: Ihre
        # Länge ist die des Feldes, und ein Steg, der am Feldrand endet, ist
        # ganz — als ganze Zelle im Umriss gefordert, entstünde keiner.
        whole_cells=generator not in STRIP_PATTERNS
        and (through or int(feature.params.get("partial", 0)) == 0),
        anchor=anchor,
        clearance=field.frame.clearance,
        around=field.around,
    )
    # Wo das Feld bis an eine Stirnfläche des Stifts reicht, schneidet ein
    # vertieftes Muster über sie hinaus — aus demselben Grund wie die
    # durchgehende Zelle oben (``Field.placed``).
    tool = field.placed(flat, beyond=BOOLEAN_OVERLAP if engraved else 0.0)
    placed = boolean(
        "difference" if engraved else "union",
        [cleared.mesh, tool],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )
    params_after = {
        **feature.params,
        "style": wanted_style,
        "pitch": new_pitch,
        "cell_depth": new_depth,
        "through": still_through,
    }
    sources_after = {
        **feature.measure_sources,
        "pitch": "parameter",
        "cell_depth": "parameter",
        "style": "parameter",
    }
    if drawn_width is not None:
        params_after["cell_width"] = drawn_width
        sources_after["cell_width"] = "parameter"
    changed = dataclasses.replace(
        feature,
        params=params_after,
        measure_sources=sources_after,
        face_indices=(),
        surface_patches=(),
    )
    findings = [
        *cleared.findings,
        *placed.findings,
        Finding(
            code="resize_feature.pattern",
            severity="info",
            message=(
                _(
                    "Das Muster ist neu gesetzt: Teilung {pitch}, Zellbreite {width}, "
                    "Tiefe {depth}.",
                    pitch=format_length(new_pitch),
                    width=format_length(drawn_width),
                    depth=format_length(new_depth),
                )
                if drawn_width is not None
                else _(
                    "Das Muster ist neu gesetzt: Teilung {pitch}, Tiefe {depth}.",
                    pitch=format_length(new_pitch),
                    depth=format_length(new_depth),
                )
            ),
            feature_ids=(feature.id,),
            values={"feature": feature.id, "pitch": new_pitch},
        ),
    ]
    if limited and drawn_width is not None:
        findings.append(
            Finding(
                code="resize_feature.cell_width_limited",
                severity="info",
                message=_(
                    "Die Zellbreite ist auf {width} begrenzt: Bei dieser Teilung bliebe sonst "
                    "keine Wand zwischen den Zellen.",
                    width=format_length(drawn_width),
                ),
                feature_ids=(feature.id,),
                values={"feature": feature.id, "cell_width": drawn_width},
            )
        )
    remaining = _without_old_triangles(source.features, without=(feature.id,))
    remaining[feature.id] = changed
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=placed.mesh, features=remaining)],
        findings=findings,
        solver=placed.solver,
    )


def _resize_thread(
    ctx: OpContext, source: SceneObject, feature: Feature, diameter: float, pitch: float
) -> OpResult:
    """Gewinde ändern: die Strecke leeren beziehungsweise füllen, dann neu schneiden."""
    internal = bool(feature.params.get("internal", False))
    diameter, pitch = _thread_checked(feature, diameter, pitch)
    if is_close(diameter, _bore_number(feature, "diameter")) and is_close(
        pitch, _bore_number(feature, "pitch")
    ):
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="resize_feature.unchanged",
                    severity="info",
                    message=_("Das Merkmal hat dieses Maß schon."),
                    feature_ids=(feature.id,),
                )
            ],
        )
    centre, axis, low, high, start, stop = _thread_span(
        source, feature, outside=not internal, internal=internal
    )
    length = high - low
    _inner, outer = _thread_bounds(feature, source)
    reach = stop - start
    base = _exact_body(source) if source.kind == "brep" else as_mesh_data(source.mesh)
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    if internal:
        # Der Stopfen greift um den Überlapp ins Material: Bündig mit dem Kamm
        # der Gänge zerfiel die Vereinigung am Netz in 454 Splitter (21.09.2026).
        plug = _thread_cylinder(2.0 * outer + 2.0 * BOOLEAN_OVERLAP, reach, source.kind)
        cleared = _combined(source, ctx, "union", base, _along_axis(centre, axis, plug, start))
        ctx.progress(0.6, str(_("Das Merkmal wird mit dem neuen Maß gesetzt …")))
        # Das Innenwerkzeug reicht an einer Mündung um die Überlappung hinaus,
        # damit dort keine Haut bleibt; an einem Grund endet es bündig. Und es
        # rechnet in der Bohrung, nicht in der Bezeichnung (``_tool_diameter``).
        _c, _a, _lo, _hi, tap_start, tap_stop = _thread_span(
            source, feature, outside=True, internal=True
        )
        tap = _thread_body(
            _tool_diameter(diameter, pitch, internal=True),
            pitch,
            tap_stop - tap_start,
            internal=True,
            kind=source.kind,
        )
        base_after = cleared.mesh if source.kind != "brep" else cleared
        body = _combined(
            source, ctx, "difference", base_after, _along_axis(centre, axis, tap, tap_start)
        )
    else:
        envelope = _thread_cylinder(2.0 * outer + 2.0 * BOOLEAN_OVERLAP, reach, source.kind)
        # Ein Gewinde kann der ganze Körper sein — eine Gewindestange, ein
        # eingelesener Bolzen ohne Kopf. Dann nimmt die Hülle alles, und das
        # neue Gewinde ist danach allein der Körper (gemessen am ISO-Korpus,
        # 21.09.2026: am Netz „Es bleibt kein Körper übrig“, exakt ein leerer).
        cleared = _combined(
            source,
            ctx,
            "difference",
            base,
            _along_axis(centre, axis, envelope, start),
            allow_empty=True,
        )
        ctx.progress(0.6, str(_("Das Merkmal wird mit dem neuen Maß gesetzt …")))
        fresh = _along_axis(
            centre,
            axis,
            _thread_body(diameter, pitch, length, internal=False, kind=source.kind),
            low,
        )
        if source.kind != "brep" and cleared.mesh.triangle_count == 0:
            body = BooleanOutcome(
                mesh=fresh, solver=cleared.solver, findings=list(cleared.findings)
            )
        else:
            base_after = cleared.mesh if source.kind != "brep" else cleared
            body = _combined(source, ctx, "union", base_after, fresh)
    changed = dataclasses.replace(
        feature,
        params={
            key: value
            for key, value in {
                **feature.params,
                "diameter": diameter,
                "pitch": pitch,
                "lead": pitch,
                "handedness": "right",
            }.items()
            if key not in ("root_radius", "crest_radius", "depth", "turns", "uncertainty", "starts")
        },
        measure_sources={
            **dict.fromkeys(("diameter", "pitch", "centre", "axis", "length"), "parameter")
        },
        provenance="generated",
        face_indices=(),
        surface_patches=(),
    )
    findings: list[Finding] = []
    if source.kind != "brep":
        findings.extend(cleared.findings)
    return _thread_result(ctx, source, body, feature, changed, findings)


def _exact_rotate_pin(
    ctx: OpContext, source: SceneObject, feature: Feature, centre: Vec3, turned_axis: Vec3
) -> OpResult:
    """Einen Zapfen am exakten Körper kippen — abtragen, gekippt ansetzen (P2.4).

    Der gekippte Zylinder reicht unter die Mitte so weit, wie die Neigung
    verlangt, sonst schwebte seine Basis auf einer Seite über der Grundfläche.
    """
    from app.core.brep import edit

    solid = _exact_body(source)
    body = _exact_body_from_faces(source, feature)
    old_axis = np.asarray(_bore_vector(feature, "axis"), dtype=float)
    new_axis = np.asarray(turned_axis, dtype=float)
    tilt = math.degrees(math.acos(min(1.0, abs(float(old_axis @ new_axis)))))
    depth = _bore_number(feature, "depth")
    reach = _reach_past_a_tilted_face(
        depth / 2.0, _bore_number(feature, "diameter") / 2.0, tilt, at_most=solid.bounds.diagonal
    )
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle abgetragen …")))
    cleared = edit.unified(edit.boolean("difference", [solid, body]))
    ctx.progress(0.6, str(_("Das Merkmal wird gedreht gesetzt …")))
    tool = _exact_pin_tool(feature, centre, turned_axis, reach_below=reach)
    placed = edit.unified(edit.boolean("union", [cleared, tool]))
    # Sichtbar bleibt vom gekippten Zylinder, was über der Grundfläche steht:
    # von der Spitze (``depth/2`` über der Mitte) bis zum tiefsten Punkt der
    # schrägen Schnittellipse (``reach`` darunter). Die native Erkennung nennt
    # die Mitte dieser Spanne — und genau dort wird das Merkmal wiedergesucht.
    unit = new_axis / float(np.linalg.norm(new_axis))
    middle = np.asarray(centre, dtype=float) + unit * (depth / 2.0 - reach) / 2.0
    expected = dataclasses.replace(
        feature,
        params={
            **feature.params,
            "axis": turned_axis,
            "centre": (float(middle[0]), float(middle[1]), float(middle[2])),
            "depth": depth / 2.0 + reach,
        },
        provenance="generated",
    )
    return _exact_cavity_result(
        ctx, source, placed, op="rotate_feature", expected=expected, findings=[]
    )


def _exact_rotate_cone(
    ctx: OpContext,
    source: SceneObject,
    feature: Feature,
    centre: Vec3,
    turned_axis: Vec3,
    *,
    cavity: bool,
) -> OpResult:
    """Einen Kegelstumpf oder eine Senkung am exakten Körper kippen (P2.4).

    Gedreht wird um die Mitte des weiten Endes, und dort liegt die
    Grundfläche: Um sie gekippt höbe der Stumpf auf einer Seite von der Platte
    ab, und die Senkung behielte eine Decke. Deshalb wird der Kegel über sein
    weites Ende hinaus so weit weitergeführt, wie ``_cone_past_a_tilted_face``
    verlangt — mit derselben Flanke, ins Material beim Stumpf, ins Freie bei
    der Senkung. Höhe und schmalen Radius nennt die native Fläche
    (``edit.cone_extent``); die Erkennung beschreibt den gekippten Kegel
    danach an seinem weitesten Rand, und das ist das Ende dieser
    Weiterführung — dort wird er wiedergesucht.
    """
    from app.core.brep import edit
    from app.core.brep.edit import _oriented_cone

    solid = _exact_body(source)
    body = _exact_body_from_faces(source, feature)
    extent = edit.cone_extent(solid, solid.faces_of_triangles(feature.face_indices))
    if extent is None:
        raise ValidationError(
            field="at_feature",
            detail=NO_BODY_FROM_FACES,
            values={"feature": feature.id, "kind": feature.kind},
            constraint="not_movable",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    old_axis = np.asarray(_bore_vector(feature, "axis"), dtype=float)
    new_axis = np.asarray(turned_axis, dtype=float)
    tilt = math.degrees(math.acos(min(1.0, abs(float(old_axis @ new_axis)))))
    if cavity:
        _sink_must_close(feature, tilt, cast(RotateFeatureParams, ctx.params).angle)
    reach = _cone_past_a_tilted_face(
        0.0, extent.wide_radius, extent.half_angle, tilt, at_most=solid.bounds.diagonal
    )
    matrix = np.asarray(transform.rotation_between(old_axis, new_axis), dtype=float)[:3, :3]
    turned = matrix @ np.asarray(extent.direction, dtype=float)
    base = np.asarray(centre, dtype=float) - turned * reach
    base_radius = extent.wide_radius + reach * math.tan(math.radians(extent.half_angle))
    ctx.progress(
        0.1,
        str(_("Das Merkmal wird an seiner alten Stelle geschlossen …"))
        if cavity
        else str(_("Das Merkmal wird an seiner alten Stelle abgetragen …")),
    )
    cleared = edit.unified(edit.boolean("union" if cavity else "difference", [solid, body]))
    ctx.progress(0.6, str(_("Das Merkmal wird gedreht gesetzt …")))
    tool = _oriented_cone(
        (float(base[0]), float(base[1]), float(base[2])),
        (float(turned[0]), float(turned[1]), float(turned[2])),
        base_radius,
        extent.narrow_radius,
        reach + extent.height,
    )
    findings: list[Finding] = []
    if cavity:
        # **Und die Kante, wie am Netz** (``rotate_feature``, an derselben Mitte
        # mit der gekippten Achse): Hier fehlte die Frage ganz, und eine
        # Senkung, die gekippt aus der Seitenfläche lief, blieb am exakten
        # Körper still (Durchsicht seit 0.5.0, 25.09.2026).
        tilted = dataclasses.replace(
            feature, params={**feature.params, "axis": turned_axis}, provenance="generated"
        )
        findings += _edge_findings(as_mesh_data(cleared), [tilted])
        # Wie an der Kette: Was über die Mündung hinausragt, endet an der alten
        # Randebene, und die Nachbarwand wird gefragt (RM-220). Ohne die Kappe
        # schnitt die um 30° gekippte Senkung 80 mm³ aus einer Rippe davor.
        caps = _old_rim_caps(as_mesh_data(source.mesh), feature, source.features)
        if caps:
            tool = edit.clipped_bore_tool(tool, caps)
        findings += _without_opened_twice(
            _neighbour_bore_findings(source, feature, as_mesh_data(tool), ctx, turned=True),
            findings,
        )
    placed = edit.unified(edit.boolean("difference" if cavity else "union", [cleared, tool]))
    expected = dataclasses.replace(
        feature,
        params={
            **feature.params,
            "axis": turned_axis,
            "centre": (float(base[0]), float(base[1]), float(base[2])),
            "diameter": 2.0 * base_radius,
        },
        provenance="generated",
    )
    return _exact_cavity_result(
        ctx, source, placed, op="rotate_feature", expected=expected, findings=findings
    )


def _sits_at(
    candidate: Feature, expected: Feature, diagonal: float, *, mouth: bool = False
) -> bool:
    """Liegt das gefundene Merkmal dort, wo die Operation es hingesetzt hat?

    ``match`` nimmt ein Merkmal an, solange Lage und Durchmesser unter seiner
    Schwelle liegen — acht Prozent der Modelldiagonale, an einer Platte von
    200 mm also sechzehn Millimeter. Das ist die richtige Großzügigkeit für
    eine Zuordnung über eine fremde Operation hinweg und die falsche für eine,
    die die Stelle selbst genannt hat: Die gehört auf ``match_tolerance``
    genau getroffen, sonst ist es ein anderes Loch.

    ``mouth`` sagt, dass das Erwartete der äußere Abschnitt einer Kette ist
    (:func:`_chain_mouths`); dann ist es entlang der Achse frei wie ein
    Durchgang (:func:`_free_along_the_axis`).
    """
    from app.core.units import match_tolerance

    tolerance = match_tolerance(diagonal)
    if candidate.params.get("open"):
        axis = np.asarray(_bore_vector(expected, "axis"), dtype=float)
        axis /= np.linalg.norm(axis)
        arc = np.asarray(_bore_vector(candidate, "arc_centre"))
        middle = np.asarray(_bore_vector(expected, "centre"))
        travel = (
            max(0.0, float(expected.params.get("length", 0.0)) - _bore_number(expected, "diameter"))
            if expected.kind == "slot"
            else 0.0
        )
        direction = np.asarray(expected.params.get("direction", (1.0, 0.0, 0.0)))
        for sign in (-1.0, 1.0):
            offset = arc - (middle + sign * travel / 2.0 * direction)
            if _free_along_the_axis(candidate, expected, mouth=mouth):
                offset -= float(offset @ axis) * axis
            if np.linalg.norm(offset) <= tolerance:
                return True
        return False
    offset = np.asarray(_bore_vector(candidate, "centre")) - _bore_vector(expected, "centre")
    if _free_along_the_axis(candidate, expected, mouth=mouth):
        axis = np.asarray(_bore_vector(expected, "axis"), dtype=float)
        axis /= np.linalg.norm(axis)
        offset -= float(offset @ axis) * axis
    return bool(np.all(np.abs(offset) <= tolerance))


def _free_along_the_axis(candidate: Feature, expected: Feature, *, mouth: bool = False) -> bool:
    """Ob ein Fund entlang der Achse gegen das Erwartete verschoben sein darf.

    Bei einem Durchgang ist die Mitte entlang der Achse eine Frage der
    Wandstärke an der neuen Stelle, nicht der Lage. Das gilt auch, wo er dort
    nicht mehr durchgeht: Eine gekippte Bohrung, deren Mündung auf eine Rippe
    trifft, endet an der alten Randebene (RM-220) und kommt als Sackloch
    zurück — dieselbe Bohrung, nur kürzer, und die Operation meldete sie als
    verloren statt als nicht mehr durchgehend. Ein Sackloch gilt deshalb als
    derselbe Durchgang, solange es im Abschnitt der Achse liegt, den beide
    zusammen überdecken; ein getrenntes koaxiales Sackloch jenseits davon
    bleibt ein anderes.

    **Und der äußere Zylinder einer Kette** (``mouth``, RM-245): Sein inneres
    Ende ist die Schulter, sein äußeres die Fläche, in die er mündet — wie weit
    er reicht, sagt die Fläche und nicht die Operation. An einer Platte mit
    Zylindersenkung Ø 10 unten und Fase oben, um 15° gekippt, lag die Mitte
    der Senkung 0,82 mm tiefer auf der Achse, als die gekippte alte Mitte
    sagt, und sie maß 7,64 statt 6 mm Tiefe: Die schräg geschnittene Mündung
    verlängert die Wand auf der einen Seite. Die Erkennung nennt eine solche
    Senkung bald durchgehend, bald nicht — die obere Stufe derselben Platte
    ``through=True``, die untere ``False`` —, und der exakte Kern meldete die
    untere als verloren, das Netz nicht. Deshalb dieselbe Regel wie am
    Sackloch hinter einer Rippe: frei im gemeinsam überdeckten Abschnitt.
    """
    if not expected.params.get("through") and not mouth:
        return False
    if candidate.params.get("through"):
        return True
    # Ohne BLAS (RM-187): Die Antwort entscheidet, welcher Fund das Merkmal ist.
    axis = np.asarray(_bore_vector(expected, "axis"), dtype=float)
    axis /= math.hypot(float(axis[0]), float(axis[1]), float(axis[2]))
    along = units.dot3(
        np.asarray(_bore_vector(candidate, "centre")) - _bore_vector(expected, "centre"), axis
    )
    reach = (_depth_of(expected) + _depth_of(candidate)) / 2.0
    return abs(along) <= reach


def _depth_of(feature: Feature) -> float:
    """Die gemessene Tiefe eines Merkmals — null, wo keine gemessen ist."""
    value = feature.params.get("depth")
    if not isinstance(value, int | float) or isinstance(value, bool) or not math.isfinite(value):
        return 0.0
    return max(0.0, float(value))


def _recognised_slot(
    detected: Mapping[str, Feature],
    feature: Feature,
    *,
    centre: Vec3,
    diameter: float,
    length: float,
    diagonal: float,
    body_centre: Vec3,
    angle: float,
    check_cancelled: Callable[[], None] | None = None,
) -> Feature | None:
    """Sucht das eben gezogene Langloch und hängt den bestehenden Namen daran.

    Das Geschwister von :func:`_recognised_resized_feature`, und aus demselben
    Grund: Die allgemeine Zuordnung vergleicht Art und Maß, und *Zum Langloch
    ziehen* ändert beides mit Absicht. Gesucht wird deshalb nach dem, was die
    Operation gerade gemacht hat — Art ``slot``, an der genannten Stelle, mit
    der eingetragenen Länge.

    **Und die Zuordnung wird nachgeprüft.** ``match`` nimmt ein Merkmal an,
    solange Lage und Durchmesser unter seiner Schwelle liegen — acht Prozent
    der Modelldiagonale, an einer Platte von 108 mm also 8,6 mm. Stünde das
    gezogene Langloch nicht mehr da, träfe die Zuordnung ein zweites daneben:
    Das fremde Loch bekäme die Kennung des gezogenen, und der Befund darunter
    bliebe aus (Fund des Reviews, 11.09.2026). Genommen wird deshalb nur, was
    an der genannten Mitte liegt und die eingetragene Länge trägt.

    ``detected`` sind die erkannten Merkmale des Ergebnisses — am Netz aus
    :func:`perceive.features.detect`, am exakten Körper aus
    :func:`brep.features.features_of` —, damit beide Kerne dieselbe Frage
    stellen.

    ``None`` heißt, dass der Schnitt keine eindeutige Langlochform mehr hat,
    etwa nach dem Kreuzen mit sich selbst. Ein zum Rand offener Ausschnitt
    bleibt dagegen anhand seines verbliebenen Innenbogens zuordenbar.
    """
    from app.core.sketch.planes import frame_of

    frame = frame_of(_bore_vector(feature, "axis"), centre)
    direction = tuple(
        units.exact_cos_degrees(angle) * frame.x_axis[i]
        + units.exact_sin_degrees(angle) * frame.y_axis[i]
        for i in range(3)
    )
    expected = dataclasses.replace(
        feature,
        kind="slot",
        params={
            **feature.params,
            "centre": centre,
            "diameter": diameter,
            "length": length,
            "direction": direction,
        },
    )
    found_id = _bore_match_id(
        detected, expected, body_centre, diagonal, check_cancelled=check_cancelled
    )
    if found_id is None:
        return None
    candidate = detected[found_id]
    if candidate.kind != "slot" or not _sits_at(candidate, expected, diagonal):
        return None
    found_length = _bore_number(candidate, "length")
    if not candidate.params.get("open") and abs(found_length - length) > max(
        EPS_DISPLAY, length * _SAME_LENGTH
    ):
        return None
    return dataclasses.replace(candidate, id=feature.id, provenance="generated", created_by=None)


def _recognised_round(
    detected: Mapping[str, Feature],
    feature: Feature,
    *,
    centre: Vec3,
    diameter: float,
    diagonal: float,
    body_centre: Vec3,
    check_cancelled: Callable[[], None] | None = None,
) -> Feature | None:
    """Sucht die runde Bohrung, zu der ein Langloch zurückgezogen wurde.

    Das Geschwister von :func:`_recognised_slot`: Art ``hole`` an der
    genannten Mitte, mit dem geschnittenen Durchmesser — und nachgeprüft, aus
    demselben Grund wie dort. ``detected`` kommt am Netz aus
    :func:`perceive.features.detect`, am exakten Körper aus
    :func:`brep.features.features_of`.
    """
    expected = dataclasses.replace(
        feature,
        kind="hole",
        params={**feature.params, "centre": centre, "diameter": diameter},
    )
    found_id = _bore_match_id(
        detected, expected, body_centre, diagonal, check_cancelled=check_cancelled
    )
    if found_id is None:
        return None
    candidate = detected[found_id]
    if candidate.kind != "hole" or not _sits_at(candidate, expected, diagonal):
        return None
    return dataclasses.replace(candidate, id=feature.id, provenance="generated", created_by=None)


def _round_outcome(feature: Feature, found: Feature | None, diameter: float) -> list[Finding]:
    """Wieder rund, oder der Bezug ist fort — beide Kerne, ein Satz."""
    if found is None:
        return [_bore_no_longer_a_feature(feature, diameter)]
    if feature.kind != "slot":
        return []
    return [
        Finding(
            code="slot_hole.round_again",
            severity="info",
            message=_("Aus dem Langloch ist wieder eine runde Bohrung geworden."),
            feature_ids=(feature.id,),
            values={"feature": feature.id},
        )
    ]


def _round_neighbour_findings(
    source: SceneObject,
    feature: Feature,
    centre: Vec3,
    axis: Vec3,
    diameter: float,
    depth: float,
    ctx: OpContext,
    moved: bool,
    widened: bool,
    already: list[Finding],
) -> list[Finding]:
    """Die Nachbarwand fragen, wenn die runde Bohrung breiter oder woanders steht.

    Derselbe Prüfumfang wie *Bohrung ändern* (``resize_hole``) und *Merkmal
    verschieben*: Zwei Wege zu demselben Loch, und nur einer sagte, dass die
    Wand zur Nachbarbohrung dünn wird oder aufreißt (Review 24.09.2026).
    Ohne neue Breite und Stelle liegt die Bohrung im alten Umriss und nimmt
    keiner Wand etwas.
    """
    if not (moved or widened):
        return []
    return _without_opened_twice(
        _neighbour_bore_findings(
            source, feature, _bore_tool_mesh(centre, axis, diameter, depth), ctx, moved=moved
        ),
        already,
    )


def _already_round(feature: Feature) -> Finding:
    """Eine runde Bohrung, auf ihre eigene Breite gezogen, bleibt, wie sie ist."""
    return Finding(
        code="slot_hole.already_round",
        severity="info",
        message=_(
            "Die Bohrung ist schon rund. Ziehen Sie sie länger, um ein Langloch daraus zu machen."
        ),
        feature_ids=(feature.id,),
        # Der Weg, den der Satz nennt, steht als Knopf daneben: Der Schritt geht
        # mit dem Cursor in der Länge auf (Regel 17).
        values={"feature": feature.id, "field": "slot_length"},
        suggestions=(CORRECT_INPUT,),
    )


def _slot_no_longer_a_feature(feature: Feature, length: float) -> Finding:
    """Der Zug ist gefahren, aber ein Langloch steht danach nicht mehr da.

    Der Satz sagt beides — die Geometrie ist geschnitten, der Bezug ist fort —
    und nennt den Rückweg. Eine gekreuzte Aussparung ist weiterhin gültige
    Geometrie, trägt aber nicht unbedingt einen eindeutigen Langlochbezug.
    """
    return Finding(
        code="slot_hole.feature_lost",
        severity="warning",
        message=SLOT_FEATURE_LOST,
        feature_ids=(feature.id,),
        values={"feature": feature.id, "length": format_length(length)},
    )


def _bore_no_longer_a_feature(feature: Feature, diameter: float) -> Finding:
    """Die geänderte Bohrung ist da, aber nicht mehr als Merkmal auffindbar.

    Der Satz sagt beides — die Geometrie stimmt, der Bezug ist fort —, weil
    aus dem einen das andere folgt: Wer später auf diese Bohrung verweist,
    findet sie nicht mehr, und das ist die Auskunft, die er braucht.
    """
    return Finding(
        code="resize_hole.feature_lost",
        severity="warning",
        message=_(
            "Die Bohrung wurde geändert, lässt sich in dieser Größe aber nicht mehr "
            "als Merkmal wiederfinden. Die Geometrie stimmt; spätere Schritte, die "
            "auf sie verweisen, verlieren ihren Bezug."
        ),
        feature_ids=(feature.id,),
        values={"feature": feature.id, "diameter": format_length(diameter)},
    )


def _preserved_exact_features(
    previous: dict[str, Feature],
    detected: dict[str, Feature],
    feature: Feature,
    diameter: float,
    solid: Mesh,
    *,
    original: Mesh | None = None,
    check_cancelled: Callable[[], None] | None = None,
    floor_shift: Vec3 = (0.0, 0.0, 0.0),
) -> tuple[dict[str, Feature], bool, tuple[tuple[str, str], ...]]:
    """Ordnet die exakte Topologie neu zu, mit dem gewählten Maß als Absicht.

    Zurück kommen die Merkmale unter ihren fortgeführten Namen, ob die
    Bohrung wiedergefunden wurde, und **welche Übergänge belegt sind**: Paare
    aus altem und neuem Namen für die bewusst geänderte Bohrung und ihren
    Boden — nur die, die der gemeinsame Anspruchsschluss tatsächlich
    freigegeben hat. Ein Kandidat aus ``_bore_match_id`` allein ist noch kein
    Beleg; erst die Zuordnung ohne Konkurrenz macht ihn dazu.
    """
    from app.core.perceive.matching import apply_mapping, match

    bounds = solid.bounds
    wanted = _expected_bore(feature, diameter)
    found_id = _bore_match_id(
        detected, wanted, bounds.centre, bounds.diagonal, check_cancelled=check_cancelled
    )
    expected = {name: entry for name, entry in previous.items() if name != feature.id}
    intended: dict[str, str] = {}
    if found_id is not None:
        expected[feature.id] = dataclasses.replace(detected[found_id], id=feature.id)
        intended[feature.id] = found_id
        if original is not None:
            floors = _resized_bore_floor(
                as_mesh_data(original),
                feature,
                previous,
                as_mesh_data(solid),
                detected[found_id],
                detected,
                check_cancelled=check_cancelled,
                shift=floor_shift,
            )
            for floor in floors.values():
                patch = set(floor.face_indices)
                parts = [
                    name
                    for name, entry in detected.items()
                    if entry.kind == "face"
                    and entry.face_indices
                    and set(entry.face_indices) <= patch
                ]
                detected = {name: entry for name, entry in detected.items() if name not in parts}
                detected[parts[0]] = dataclasses.replace(floor, id=parts[0])
                intended[floor.id] = parts[0]
            expected.update(floors)
    matched = match(
        expected,
        detected,
        bounds.centre,
        bounds.diagonal,
        check_cancelled=check_cancelled,
    )
    if found_id is None:
        matched.orphaned = (*matched.orphaned, feature.id)
    # Belegt ist ein Übergang erst, wenn die Zuordnung genau den erwarteten
    # Nachfolger freigibt — ohne Konkurrenz um ihn und ohne, dass er einem
    # anderen alten Anspruch zugefallen wäre. Der Alias wird dann unter dem
    # alten Namen veröffentlicht, und genau dieser Name ist das Ziel.
    continued = tuple(
        (old_id, old_id)
        for old_id, new_id in intended.items()
        if matched.mapping.get(old_id) == new_id and old_id not in matched.ambiguous
    )
    return apply_mapping(detected, matched, previous=previous), found_id is not None, continued


def _both_halves_or_stop(first: MeshData, second: MeshData, position: float) -> None:
    """Hält an, wenn die Ebene den Körper gar nicht getroffen hat.

    Ohne das kam eine Hälfte mit null Dreiecken heraus, und der Stapel legte
    sie als Objekt an: ein Eintrag im Baum, den man ansehen, umbenennen und
    exportieren kann und der nichts ist. Der Fall ist häufiger als er klingt —
    der Dialog belegt ``position = 0`` vor, und ein Körper steht mit seiner
    Unterseite oft genau dort.
    """
    if first.triangle_count and second.triangle_count:
        return
    raise ValidationError(
        field="position",
        detail=_("Diese Ebene teilt das Objekt nicht."),
        value=position,
        constraint="no_split",
    )


@op_params
class CountersinkParams(BaseParams):
    diameter: float = param(
        title=_("Kopfdurchmesser"),
        default=8.4,
        unit="mm",
        minimum=0.5,
        maximum=100.0,
        doc=_(
            "Durchmesser des Schraubenkopfes, nicht der Bohrung darunter. Eine "
            "angeklickte Bohrung trägt den Kopf der passenden Schraube ein — "
            "nie ihr eigenes, gemessenes Maß."
        ),
    )
    angle: float = param(
        title=_("Winkel"),
        default=90.0,
        unit=DEGREE_UNIT,
        minimum=30.0,
        maximum=170.0,
        # Hinten, weil 90 Grad die Norm ist und nicht eine Wahl: Der eigene
        # doc-Satz sagt es. Damit hat die Senkung dieselbe Vorderseite wie
        # `drill_hole` und `plug_hole` — Durchmesser, Position, Achse — und war
        # vorher die einzige Operation mit sechs Werten und leerer Rückseite
        # (§2.4: vorn die zwei bis drei, die man tatsächlich ändert).
        placement="advanced",
        doc=_("Voller Kopfwinkel — 90 Grad bei metrischen Senkschrauben."),
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z, placement="advanced"
    )
    axis: str = param(
        title=_("Achse"), default="z", choices=_AXES, doc=_ALONG, placement="advanced"
    )
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="mouth",
        choices=_ANCHORS,
        placement="advanced",
        doc=_(
            "Was die Position bedeutet: die Mündung der Bohrung, in der gesenkt "
            "wird, oder die Stelle selbst. Eine angeklickte Bohrung meldet ihre "
            "Mitte — dort gesenkt entsteht ein Hohlraum statt einer Fase."
        ),
    )


@register_op(
    name="countersink_hole",
    title=_("Senken"),
    category="holes",
    params=CountersinkParams,
    consumes=1,
    produces=1,
    # Auch auf eine **vorhandene** Senkung: Ein angeklickter Kegel bietet damit
    # „Senken" an, und das heißt dort „anders senken" — tiefer, weiter, anderer
    # Winkel. Ohne diesen Eintrag wäre der Kegel ein Merkmal, das man sehen und
    # anklicken kann und an dem das Kontextmenü leer bleibt (§2.6).
    applies_to=["hole", "cone"],
    doc=_("Senkt die Mündung einer Bohrung an, damit ein Schraubenkopf bündig sitzt."),
)
def countersink_hole(ctx: OpContext) -> OpResult:
    params = cast(CountersinkParams, ctx.params)
    source = ctx.inputs[0]
    if source.kind == "brep":
        return _exact_countersink(ctx, source, params)
    result = countersink(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        angle=params.angle,
        anchor=cast(BoreAnchor, params.anchor),
        profile=ctx.profile,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class PlugParams(BaseParams):
    at_feature: str = param(
        title=_("Bohrung"),
        default="",
        kind="feature",
        placement="front",
        doc=_(
            "Die erkannte Bohrung, die verschlossen wird. Ein Klick darauf trägt sie "
            "ein; ohne sie gelten die Werte unter „Mehr“."
        ),
    )
    diameter: float = param(
        title=_("Durchmesser"),
        default=5.0,
        unit="mm",
        minimum=0.2,
        maximum=200.0,
        doc=_("Durchmesser der Bohrung, die zugemacht wird — etwas mehr schadet nicht."),
    )
    x: float = param(
        title=_("Position X"), default=0.0, unit="mm", doc=_WHERE_X, placement="advanced"
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z, placement="advanced"
    )
    axis: str = param(
        title=_("Achse"), default="z", choices=_AXES, doc=_ALONG, placement="advanced"
    )
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1000.0,
        placement="advanced",
        doc=_("Null füllt durch das ganze Teil."),
    )
    anchor: str = param(
        title=_("Bezugspunkt"),
        default="mouth",
        choices=_ANCHORS,
        placement="advanced",
        doc=_(
            "Was die Position bedeutet: die Mündung, an der der Stopfen anfängt, "
            "oder seine Mitte. Bei einem durchgehenden Stopfen ändert es nichts."
        ),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=True,
        placement="advanced",
        doc=_(
            "Füllt so weit, wie *Bohrung setzen* mit derselben Einstellung schneidet — "
            "sonst bleibt rings um den Stopfen der Spalt stehen, um den die Bohrung "
            "aufgeweitet wurde."
        ),
    )


@register_op(
    name="plug_hole",
    # 2: eine schräge Bohrung schließt an ihren Randebenen (22.09.2026).
    cache_version="2",
    title=_("Bohrung verschließen"),
    category="holes",
    params=PlugParams,
    consumes=1,
    produces=1,
    applies_to=["hole"],
    doc=_("Füllt eine Bohrung wieder auf — etwa wenn ein fremdes Teil eine zu viel hat."),
)
def plug_hole(ctx: OpContext) -> OpResult:
    """Eine Bohrung wieder auffüllen — am erkannten Merkmal oder an Zahlen.

    **Der Weg über das Merkmal ist der genaue.** Ohne ihn baut
    :func:`~app.core.geom.prepare.plug` den Stopfen aus Position, Achse und
    Tiefe und beschneidet ihn an der **konvexen Hülle** des Teils. Für einen
    massiven Körper ist das richtig — die Hülle *ist* er. Für ein Teil mit Nut
    oder Innenraum ist sie es nicht, und ein Stopfen, der nach innen ragt,
    liegt darin. Gemessen am 03.09.2026 an einem U-Profil mit einer Nut und
    5 mm starker Bodenwand, Bohrung Ø 7,98:

    ==================================== ============ =============
    Lauf                                  Volumen      im Nutraum
    ==================================== ============ =============
    ohne Bohrung (Soll)                   27 000,00    —
    mit Bohrung                           26 749,39    0,000
    gestopft, durchgehend                 28 259,32    1007,460
    gestopft, Tiefe genau die Wandstärke  27 001,25    251,865
    ==================================== ============ =============

    Die 1007 sind die Länge, die 252 sind die Form: Der Stopfen setzt an der
    Mündung an und ragt mit seiner Überlappung darüber hinaus. Beides behebt
    derselbe Schnitt, weil er nicht fragt, wie lang das Werkzeug ist, sondern
    **wo das Merkmal aufhört** — und die Mündungen kennt nur die Merkmalsfläche.

    **Der alte Weg bleibt, und zwar nicht aus Rücksicht auf alte Dateien
    allein.** Ohne Merkmal gibt es keine Mündung, an der sich schneiden ließe;
    wer eine Bohrung an Zahlen verschließt, die die Erkennung nicht kennt, kann
    nur die Hülle bekommen. Dass alte Projektdateien weiter öffnen, ist die
    zweite Zusage und gemessen: Ein gespeicherter Schritt ohne ``at_feature``
    bekommt die leere Vorgabe, und leer heißt hier der Weg über die Zahlen
    (``test_prepare.py``).
    """
    params = cast(PlugParams, ctx.params)
    source = ctx.inputs[0]
    if source.kind == "brep":
        return _exact_plug(ctx, source, params)
    if params.at_feature:
        feature = _movable_feature(source, params.at_feature, "plug_hole")
        measured = [float(value) for value in feature.params["centre"]]
        centre: Vec3 = (measured[0], measured[1], measured[2])
        filled = _closed_at(
            as_mesh_data(source.mesh),
            feature,
            centre,
            True,
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        remaining = _without_old_triangles(source.features, without=(feature.id,))
        return OpResult(
            outputs=[dataclasses.replace(source, mesh=filled.mesh, features=remaining)],
            solver=filled.solver,
            findings=filled.findings,
        )
    result = plug(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        depth=params.depth,
        anchor=cast(BoreAnchor, params.anchor),
        profile=ctx.profile,
        compensate=params.compensate,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features={})],
        solver=result.solver,
        findings=result.findings,
    )


def _exact_countersink(ctx: OpContext, source: SceneObject, params: CountersinkParams) -> OpResult:
    """Senken am exakten Körper (P2.4): derselbe Kegel, exakt geschnitten.

    Mündung und Materialseite kommen aus :func:`sink_placement`, gemessen am
    Netz-Zwilling — dieselbe Antwort wie am Netz. Der Kegel selbst ist exakt
    und trägt seinen Durchmesser **an der Mündung**: Über sie hinaus geht er
    um ``FEATURE_OVERLAP`` mit derselben Flanke weiter, damit keine Fläche mit
    der Oberfläche zusammenfällt; am Netz wird er stattdessen angehoben, und
    dort ist die Mündung um den Überstand mal Flanke enger — das ist der
    Sehnenfehler des Netzwegs, nicht das Maß.
    """
    from app.core.brep import edit
    from app.core.brep.edit import _oriented_cone

    solid = _exact_body(source)
    axis = cast(Axis, params.axis)
    placement = sink_placement(
        as_mesh_data(source.mesh),
        axis,
        (params.x, params.y, params.z),
        params.diameter,
        cast(BoreAnchor, params.anchor),
    )
    half_angle = params.angle / 2.0
    radius = params.diameter / 2.0
    depth = radius / math.tan(math.radians(half_angle))
    outward = np.asarray(AXIS_NORMALS[axis], dtype=float) * placement.outward
    base = np.asarray(placement.position, dtype=float) + outward * FEATURE_OVERLAP
    tool = _oriented_cone(
        (float(base[0]), float(base[1]), float(base[2])),
        (float(-outward[0]), float(-outward[1]), float(-outward[2])),
        radius + FEATURE_OVERLAP * math.tan(math.radians(half_angle)),
        0.0,
        depth + FEATURE_OVERLAP,
    )
    ctx.progress(0.3, str(_("Die Senkung wird geschnitten …")))
    sunk = edit.unified(edit.boolean("difference", [solid, tool]))
    findings = list(placement.findings)
    nothing = without_effect(solid, sunk, "difference", ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    # Dieselbe Kantenfrage wie am Netz (``prepare.countersink``).
    findings.extend(
        mouth_over_the_edge(
            as_mesh_data(source.mesh),
            placement.position,
            cast(Vec3, tuple(float(-value) for value in outward)),
            params.diameter,
        )
    )
    return _exact_cavity_result(
        ctx, source, sunk, op="countersink_hole", expected=None, findings=findings
    )


def _exact_plug(ctx: OpContext, source: SceneObject, params: PlugParams) -> OpResult:
    """Eine Bohrung am exakten Körper verschließen (P2.4) — am Merkmal oder an Zahlen.

    Am Merkmal ist es der Stopfen aus den gemessenen Maßen
    (:func:`_exact_cavity_filled`), und die Kennung geht mit, wie beim
    Entfernen. An Zahlen gilt, was :func:`~app.core.geom.prepare.plug` am Netz
    tut: Mitte und Länge aus :func:`plug_placement`, der Zylinder um die
    Materialtoleranz weiter, beschnitten an der konvexen Hülle
    (``edit.convex_hull``), damit ein durchgehender Stopfen nicht aus dem
    Teil herauswächst.
    """
    from app.core.brep import edit
    from app.core.brep.edit import _oriented_cylinder

    solid = _exact_body(source)
    if params.at_feature:
        feature = _movable_feature(source, params.at_feature, "plug_hole")
        ctx.progress(0.3, str(_("Das Merkmal wird geschlossen …")))
        filled = edit.unified(_exact_cavity_filled(solid, feature))
        findings: list[Finding] = []
        nothing = without_effect(solid, filled, "union", ctx.profile)
        if nothing is not None:
            findings.append(nothing)
        return _exact_cavity_result(
            ctx,
            source,
            filled,
            op="plug_hole",
            expected=None,
            gone=(feature.id,),
            findings=findings,
            reserve=True,
        )
    axis = cast(Axis, params.axis)
    centre, height = plug_placement(
        as_mesh_data(source.mesh),
        axis,
        (params.x, params.y, params.z),
        params.depth,
        cast(BoreAnchor, params.anchor),
    )
    filled_diameter = bore_diameter(params.diameter, ctx.profile, params.compensate)
    unit = np.asarray(AXIS_NORMALS[axis], dtype=float)
    start = np.asarray(centre, dtype=float) - unit * (height / 2.0)
    cylinder = _oriented_cylinder(
        (float(start[0]), float(start[1]), float(start[2])),
        (float(unit[0]), float(unit[1]), float(unit[2])),
        filled_diameter / 2.0 + EPS_GEOM,
        height,
    )
    ctx.progress(0.3, str(_("Die Bohrung wird verschlossen …")))
    inside = edit.boolean("intersection", [cylinder, edit.convex_hull(solid)])
    plugged = edit.unified(edit.boolean("union", [solid, inside]))
    findings = []
    nothing = without_effect(solid, plugged, "union", ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    return _exact_cavity_result(
        ctx, source, plugged, op="plug_hole", expected=None, findings=findings
    )


@op_params
class HollowParams(BaseParams):
    wall: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        # **Die Zahl ist eine Rechengrenze, keine Toleranz mehr.** Hier stand
        # 0,4 mit dem Satz „zwei Extrusionsbreiten sind das Minimum" daneben —
        # und setzte ihn nicht um: Zwei Extrusionsbreiten sind am Centauri
        # 0,84 mm, an einer 0,6er Düse 1,2. Die Regel trägt jetzt
        # ``below_printable_wall`` gegen das Profil (§39, Regel 7); was hier
        # steht, ist nur noch, was der Kern überhaupt rechnen kann, und dieselbe
        # Zahl wie beim exakten Zwilling.
        minimum=0.2,
        maximum=50.0,
        doc=_("Was stehen bleibt. Zwei Extrusionsbreiten sind das Minimum."),
    )
    open_top: bool = param(
        title=_("Oben öffnen"),
        default=False,
        doc=_(
            "Nimmt die Decke über dem Hohlraum weg. Aus dem hohlen Körper wird "
            "eine Dose, und *Deckel erzeugen* findet die Öffnung, die es braucht."
        ),
    )
    openings: tuple[str, ...] = param(
        title=_("Öffnungen"),
        default=(),
        kind="features",
        # Flächen des Körpers, der ausgehöhlt wird — eine Bohrung trägt sich
        # beim Anklicken nicht ein (``values_for``), und die Operation prüft
        # dieselbe Menge (P6.3).
        feature_kinds=("face", "curved_face"),
        doc=_(
            "Die Flächen, die offen bleiben — jede angeklickte Fläche kommt dazu. "
            "Die übrigen Flächen bleiben geschlossen. Leer heißt: geschlossen "
            "oder oben offen."
        ),
    )
    wall_side: str = param(
        title=_("Richtung"),
        default="inside",
        choices=("inside", "outside"),
        doc=_(
            "Innen behält das Teil seine Außenmaße, und die Wand wächst nach innen. "
            "Außen wird das Teil selbst zum Hohlraum, und die Wand legt sich darum."
        ),
    )
    open_at: str = param(
        title=_("Öffnen an Fläche"),
        default="",
        # **Ein Ziel, kein Ort** — dieselbe Bauart wie ``up_to`` an der
        # Skizze. Seit P6.3 (23.09.2026) die ältere der zwei Öffnungen: Sie
        # öffnet in die **Achsrichtung** der Fläche über den ganzen Querschnitt
        # des Hohlraums (RM-087), und gespeicherte Schritte hängen an genau
        # dieser Bedeutung. Ein Klick trägt sich seither unter ``openings``
        # ein; hier nur noch, wer das Feld ausdrücklich wählt.
        targets_feature=True,
        placement="advanced",
        doc=_(
            "Öffnet den Hohlraum zu der Seite, in die diese Fläche zeigt, über seinen "
            "ganzen Querschnitt. Genau die gewählten Flächen öffnet „Öffnungen“."
        ),
    )
    vents: int = param(
        title=_("Entlüftungen"),
        default=1,
        minimum=0,
        maximum=6,
        doc=_(
            "Null heißt geschlossener Hohlraum — beim FDM-Druck drückt der die "
            "Decke hoch. Eine offene Dose braucht keine."
        ),
    )
    vent_diameter: float = param(
        title=_("Entlüftungsdurchmesser"),
        default=VENT_DIAMETER,
        unit="mm",
        minimum=1.0,
        maximum=20.0,
        placement="advanced",
        doc=_("Weite der Öffnungen. Groß genug, dass nicht verbrauchtes Material herauskommt."),
    )
    exact_fallback: str = param(
        title=_("Wenn es exakt nicht geht"),
        default="ask",
        choices=("ask", "raster", "unchanged"),
        placement="advanced",
        doc=_(
            "Findet der exakte Kern für diese Form keine gleichmäßige Innenwand, entsteht "
            "die Wand am Dreiecksmodell über das Raster — oder das Teil bleibt, wie es "
            "ist. „Nachfragen“ entscheidet, sobald der Fall eintritt."
        ),
    )


@register_op(
    name="hollow_object",
    # 2: gewählte Öffnungsflächen, Wand außen, erfragter Rückfall; an den
    # bisherigen Wegen neu der Befund ``hollow.closed_cavities`` (P6.3,
    # 23.09.2026). Die Geometrie gespeicherter Schritte ist unverändert.
    cache_version="2",
    title=_("Aushöhlen"),
    category="prepare",
    params=HollowParams,
    consumes=1,
    produces=1,
    doc=_(
        "Höhlt ein Objekt aus, mit Entlüftungen oder mit gewählten offenen Flächen. "
        "Spart Material und Zeit; am Dreiecksmodell stimmt die Wand im Rahmen des "
        "Rasters. Ein Körper mit bearbeitbaren Flächen bleibt exakt, wenn gewählte "
        "Flächen oder die Oberseite offen bleiben."
    ),
    caveat=_(
        "Nicht ohne Entlüftung, wenn im Slicer Stützen entstehen: Der Hohlraum füllt "
        "sich sonst mit Material, das niemand mehr herausbekommt. Und nicht bei "
        "Teilen, die Kräfte aufnehmen — eine dünne Hülle bricht anders als ein "
        "gefüllter Körper."
    ),
    shortcut="Ctrl+H",
)
def hollow_object(ctx: OpContext) -> OpResult:
    params = cast(HollowParams, ctx.params)
    source = ctx.inputs[0]
    outward = params.wall_side == "outside"
    openings = tuple(dict.fromkeys(params.openings))
    if openings:
        # **Gewählte Öffnungsflächen** (P6.3, Konzept §13.2): exakt über
        # ``BRepOffsetAPI_MakeThickSolidByJoin``, am Netz über das Raster mit
        # einem Öffnungswerkzeug je Fläche. Der ältere Achsweg ``open_at``
        # bedeutet etwas anderes und wird nicht still mit ihm vermischt.
        if str(params.open_at).strip():
            raise ValidationError(
                field="open_at",
                detail=_(
                    "„Öffnen an Fläche“ gilt nur ohne gewählte Öffnungen. Tragen Sie die "
                    "Fläche unter „Öffnungen“ ein und leeren Sie dieses Feld."
                ),
                value=params.open_at,
                constraint="opening_twice",
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        if source.kind == "brep":
            return _exact_hollow_open(ctx, source, openings, outward=outward)
        return _mesh_hollow_open(ctx, source, openings, outward=outward)
    if source.kind == "brep" and exactly_hollowable(params):
        if outward:
            return _exact_hollow_open(ctx, source, (), outward=True)
        # **Die Entscheidungstabelle** (P2.8, Konzept §10.1): Der exakte Weg
        # öffnet immer die Oberseite und kennt weder eine andere Öffnung noch
        # Entlüftungen. Genau dieser Auftrag bleibt exakt; jeder andere geht
        # den Netzweg, und ``evaluate.exact_became_mesh`` sagt es vor der
        # Übernahme im Vorschauband.
        from app.core.brep.ops import shell_exact

        return shell_exact(ctx)
    result = hollow(
        as_mesh_data(source.mesh),
        params.wall,
        vents=params.vents,
        vent_diameter=params.vent_diameter,
        open_top=params.open_top,
        open_towards=_opening_direction(source, params.open_at),
        outward=outward,
        quality=ctx.quality,
        progress=ctx.progress,
        cancelled=ctx.cancelled,
    )
    return _mesh_hollow_result(ctx, source, result)


def _mesh_hollow_result(ctx: OpContext, source: SceneObject, result: HollowResult) -> OpResult:
    """Das gemeinsame Ende der Netzwege des Aushöhlens: Körper, Stufe, Befunde."""
    params = cast(HollowParams, ctx.params)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features={})],
        # Aushöhlen fährt bis zu sechs Boolesche Schnitte und meldete keine
        # Stufe. Wer hinterher fragt, was die Wandstärke wert ist, liest sie
        # hier (§17.2).
        solver=result.solver,
        # Die Geometriefunktion kennt keine Kennungen — sie rechnet auf einem
        # Netz. Verorten kann die Operation, und sie muss es: zwei ausgehöhlte
        # Körper meldeten zweimal denselben Satz, und im Bericht standen zwei
        # Zeilen, die aussahen wie ein Fehler in der Anwendung.
        findings=[
            dataclasses.replace(entry, object_id=source.id)
            # **Die Druckbarkeit fragt das Profil, nicht das Schema.** Hier
            # stand ``minimum=0.4`` — richtig für eine 0,4er Düse und für jede
            # andere falsch: Am Centauri sind zwei Extrusionsbreiten 0,84 mm,
            # die Grenze ließ dort das Doppelte an zu dünner Wand durch.
            for entry in [*result.findings, below_printable_wall(params.wall, ctx.profile)]
            if entry is not None
        ],
    )


def _opening_faces(source: SceneObject, openings: Sequence[str]) -> list[Feature]:
    """Die gewählten Öffnungsflächen — oder ein Satz, warum eine nicht geht (Regel 17).

    Dieselben Fragen wie am älteren ``open_at``: Gibt es die Fläche an
    **diesem** Körper, und ist sie eine Fläche. Welche Arten zählen, sagt der
    Parameter selbst (``feature_kinds``) — derselbe, nach dem ein Klick im
    Fenster sich einträgt. Ob sie eben sein muss, entscheidet der Kern, der
    rechnet: am Netz ja, am exakten Körper nicht.
    """
    from app.core.sketch.planes import feature_plane_parts

    allowed = next(entry.feature_kinds for entry in HollowParams.spec() if entry.name == "openings")
    faces: list[Feature] = []
    for name in openings:
        object_id, feature_id = feature_plane_parts(f"feature:{name}")
        if object_id and object_id != source.id:
            raise ValidationError(
                field="openings",
                detail=_(
                    "Diese Fläche gehört zu einem anderen Körper — geöffnet wird "
                    "an einer Fläche des Körpers, der ausgehöhlt wird."
                ),
                value=name,
                constraint="foreign_feature",
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        feature = source.features.get(feature_id)
        if feature is None:
            raise ValidationError(
                field="openings",
                detail=_("Diese Fläche gibt es an diesem Objekt nicht mehr."),
                value=name,
                constraint="unknown_feature",
                values={"known": ", ".join(sorted(source.features))},
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        if feature.kind not in allowed:
            raise ValidationError(
                field="openings",
                detail=_("Geöffnet wird an einer Fläche — dieses Merkmal ist keine."),
                value=name,
                constraint="not_a_face",
                values={"kind": feature.kind},
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        faces.append(feature)
    return faces


def _mesh_hollow_open(
    ctx: OpContext, source: SceneObject, openings: Sequence[str], *, outward: bool
) -> OpResult:
    """Aushöhlen mit gewählten Flächen am Netz — Raster und Öffnungswerkzeug (P6.3).

    Am Netz bleibt nur eine **ebene** Fläche offen: Ihr Umriss in ihrer Ebene
    ist das Werkzeug. Eine gewölbte Fläche sagt ab und nennt den Weg dorthin.
    """
    from app.core.geom.hollow import Opening, opening_plane

    params = cast(HollowParams, ctx.params)
    mesh = as_mesh_data(source.mesh)
    chosen: list[Opening] = []
    for feature in _opening_faces(source, openings):
        triangles = tuple(int(index) for index in feature.face_indices)
        if feature.kind != "face" or opening_plane(mesh, triangles) is None:
            raise ValidationError(
                field="openings",
                detail=_(
                    "Am Dreiecksmodell bleibt nur eine ebene Fläche offen. Wählen Sie "
                    "eine ebene Fläche, oder arbeiten Sie an einem Körper mit "
                    "bearbeitbaren Flächen."
                ),
                value=feature.id,
                constraint="not_planar",
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        chosen.append(Opening(triangles=triangles, name=feature.id))
    if params.open_top:
        top = _top_triangles(mesh)
        if top and not any(set(top) == set(entry.triangles) for entry in chosen):
            chosen.append(Opening(triangles=top))
    result = hollow(
        mesh,
        params.wall,
        openings=tuple(chosen),
        outward=outward,
        quality=ctx.quality,
        progress=ctx.progress,
        cancelled=ctx.cancelled,
    )
    return _mesh_hollow_result(ctx, source, result)


def _top_triangles(mesh: MeshData) -> tuple[int, ...]:
    """Die Dreiecke der Oberseite — dieselbe Frage wie ``profiles.top_faces_of``
    am exakten Körper: nach oben gerichtet und auf der höchsten Ebene."""
    raw = mesh.raw
    normals = np.asarray(raw.face_normals, dtype=np.float64)
    centres = np.asarray(raw.triangles_center, dtype=np.float64)
    top = float(mesh.bounds.maximum[2])
    chosen = np.flatnonzero((normals[:, 2] > 0.9) & (np.abs(centres[:, 2] - top) <= 1e-4))
    return tuple(int(index) for index in chosen)


def _exact_hollow_open(
    ctx: OpContext, source: SceneObject, openings: Sequence[str], *, outward: bool
) -> OpResult:
    """Aushöhlen mit gewählten Flächen am exakten Körper (P6.3).

    ``BRepOffsetAPI_MakeThickSolidByJoin`` mit genau diesen Flächen, nach innen
    oder nach außen; *Oben öffnen* legt die Oberseite dazu. Gibt OpenCASCADE
    keinen brauchbaren Körper, bleibt das Teil, wie es war, und der Befund sagt
    warum: Findet das Raster innen keinen Platz, ist die Wand zu dick; findet
    es welchen, schneiden sich die Innenwände an dieser Form
    (``hollow.walls_collide``). Das Raster wird nur in diesem Fall gefragt.
    """
    from app.core.brep.profiles import shell_open_at, top_faces_of
    from app.core.geom.hollow import erosion_steps, has_room_inside, hollowed, too_thin

    params = cast(HollowParams, ctx.params)
    solid = _exact_body(source)
    faces = _opening_faces(source, openings)
    indices: set[int] = set()
    for feature in faces:
        indices.update(solid.complete_faces_of_triangles(tuple(feature.face_indices)))
    if params.open_top:
        indices.update(top_faces_of(solid, cancelled=ctx.cancelled))
    ctx.progress(0.2, str(_("Hohlraum ausschneiden")))
    shelled = shell_open_at(
        solid, params.wall, sorted(indices), outward=outward, cancelled=ctx.cancelled
    )
    findings: list[Finding] = []
    if shelled is None:
        tessellated = as_mesh_data(solid)
        if not outward and not has_room_inside(tessellated, params.wall):
            findings.append(dataclasses.replace(too_thin(params.wall), suggestions=_THINNER))
            return OpResult(
                outputs=[source],
                findings=[dataclasses.replace(entry, object_id=source.id) for entry in findings],
            )
        choice, answered = _exact_fallback_choice(ctx, params)
        if choice == "raster":
            # **Derselbe Auftrag, am Dreiecksmodell** — dieselben Flächen, dieselbe
            # Wand, im Rahmen des Rasters. Die Umwandlung meldet die Auswertung vor
            # der Übernahme (``evaluate.exact_became_mesh``); der Satz hier sagt,
            # warum es sie gibt. Gefragt wurde einmal, die Antwort steht im Schritt.
            meshed = dataclasses.replace(source, mesh=tessellated, kind="mesh")
            result = _mesh_hollow_open(ctx, meshed, openings, outward=outward)
            result.findings.insert(
                0, dataclasses.replace(_exact_gave_way(params.wall), object_id=source.id)
            )
            result.answered.update(answered)
            return result
        steps, pitch = erosion_steps(params.wall)
        findings.append(_walls_collide(params.wall, steps * pitch))
        return OpResult(
            outputs=[source],
            findings=[dataclasses.replace(entry, object_id=source.id) for entry in findings],
            answered=answered,
        )
    findings.append(hollowed(params.wall, float(solid.volume) - float(shelled.volume)))
    thin = below_printable_wall(params.wall, ctx.profile)
    if thin is not None:
        findings.append(thin)
    features, _continued, _lost = _exact_features_after(
        source,
        shelled,
        expected=None,
        gone=tuple(feature.id for feature in faces),
        cancelled=ctx.cancelled,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=shelled, kind="brep", features=features)],
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in findings],
    )


def _exact_fallback_choice(ctx: OpContext, params: HollowParams) -> tuple[str, dict[str, Any]]:
    """Was geschieht, wenn der exakte Kern keine Innenwand findet — gefragt oder gespeichert.

    Regel 21: Der Rückfall auf das Raster ist keine stille Entscheidung. Steht
    ``exact_fallback`` auf „Nachfragen", fragt die Operation einmal
    (``ctx.ask``), und die Antwort reist als Parameter in den Stapel
    (``OpResult.answered``) — dieselbe Datei rechnet danach ohne Frage gleich.
    """
    if params.exact_fallback != "ask":
        return params.exact_fallback, {}
    choices = [str(_("Am Dreiecksmodell aushöhlen")), str(_("Teil unverändert lassen"))]
    answer = ctx.ask(
        str(
            _(
                "Der exakte Kern findet für diese Form keine gleichmäßige Innenwand. Soll "
                "die Wand am Dreiecksmodell entstehen — dieselben Öffnungen, die Wand im "
                "Rahmen des Rasters?"
            )
        ),
        choices,
    )
    if answer not in choices:
        raise InternalError(detail="the hollowing fallback question returned an unknown choice")
    choice = "raster" if answer == choices[0] else "unchanged"
    return choice, {"exact_fallback": choice}


def _exact_gave_way(wall: float) -> Finding:
    """Die Wand entstand am Dreiecksmodell, weil der exakte Kern sie nicht fand."""
    return Finding(
        code="hollow.exact_fallback",
        severity="warning",
        message=_(
            "Der exakte Kern fand für diese Form keine gleichmäßige Innenwand. Die Wand "
            "entstand am Dreiecksmodell über das Raster; das Teil ist danach ein "
            "Dreiecksmodell."
        ),
        values={"wall_mm": round(wall, 2)},
    )


#: Die Auswege, wenn die Wand für diesen Körper zu dick ist: eine dünnere
#: eintragen, oder es lassen.
_THINNER: Final = (
    dataclasses.replace(CORRECT_INPUT, label=_("Dünnere Wand eintragen")),
    CANCEL,
)


def _walls_collide(wall: float, eroded: float) -> Finding:
    """Der exakte Kern findet keine gleichmäßige Innenwand, und das Teil bleibt.

    Der konkave Fall aus P6.3: An einer Rippe, einem Absatz oder einer engen
    Kehle finden die versetzten Flächen keinen gemeinsamen Verlauf, obwohl das
    Teil dick genug ist — und an verrundeten Kundenteilen aus STEP scheitert
    ``MakeThickSolidByJoin`` in jeder gemessenen Einstellung (Sonde vom
    23.09.2026, Bericht P6.3). Gesagt wird deshalb, was feststeht: Der exakte
    Kern hat es nicht geschafft; nicht, dass die Form es verbietet. Gilt, wenn
    ``exact_fallback`` das Raster ausschlägt.
    """
    return Finding(
        code="hollow.walls_collide",
        severity="warning",
        message=_(
            "Der exakte Kern findet für diese Form keine gleichmäßige Innenwand. Das Teil "
            "bleibt, wie es war. Eine dünnere Wand oder andere offene Flächen wählen, "
            "oder am Dreiecksmodell aushöhlen."
        ),
        values={"wall_mm": round(wall, 2), "eroded_mm": round(eroded, 3)},
        suggestions=(*_THINNER[:1], CHANGE_SELECTION, CANCEL),
    )


def exactly_hollowable(params: HollowParams) -> bool:
    """Trifft dieser Auftrag den exakten Weg — Oberseite offen, keine andere Öffnung, keine
    Entlüftung? Die Tabelle aus Konzept §10.1, an einer Stelle für Operation und Vorschau."""
    return bool(params.open_top) and not str(params.open_at).strip() and int(params.vents) == 0


def _opening_direction(source: SceneObject, open_at: str) -> Vec3 | None:
    """Die Achsrichtung, in die *Aushöhlen* an dieser Fläche öffnet (RM-087).

    Leer heißt: keine Fläche gewählt, es gilt der Haken *Oben öffnen*. Die
    Fläche muss zu **diesem** Körper gehören — ein Rezept, das die Vorderseite
    eines anderen Teils nennt, öffnet hier nichts —, sie muss eine Fläche sein
    und nach einer Achse zeigen: Das Raster des Aushöhlens ist achsparallel,
    und eine Öffnung entlang einer schrägen Fläche wäre eine andere, als der
    Klick versprochen hat. Jede Absage nennt, was stattdessen geht (Regel 17).
    """
    if not open_at:
        return None
    from app.core.scene.placement import dominant_axis
    from app.core.sketch.planes import feature_plane_parts

    object_id, feature_id = feature_plane_parts(f"feature:{open_at}")
    if object_id and object_id != source.id:
        raise ValidationError(
            field="open_at",
            detail=_(
                "Diese Fläche gehört zu einem anderen Körper — geöffnet wird "
                "an einer Fläche des Körpers, der ausgehöhlt wird."
            ),
            value=open_at,
            constraint="foreign_feature",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    feature = source.features.get(feature_id)
    if feature is None:
        raise ValidationError(
            field="open_at",
            detail=_("Diese Fläche gibt es an diesem Objekt nicht mehr."),
            value=open_at,
            constraint="unknown_feature",
            values={"known": ", ".join(sorted(source.features))},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if feature.kind != "face":
        raise ValidationError(
            field="open_at",
            detail=_("Geöffnet wird an einer Fläche — dieses Merkmal ist keine."),
            value=open_at,
            constraint="not_a_face",
            values={"kind": feature.kind},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    normal = vec3_or_none(feature.params.get("normal"))
    axis = dominant_axis(normal) if normal is not None else None
    if normal is None or axis is None:
        raise ValidationError(
            field="open_at",
            detail=_(
                "Diese Fläche ist schräg. Geöffnet wird entlang einer Achse — "
                "wählen Sie eine gerade Seite, oder öffnen Sie oben."
            ),
            value=open_at,
            constraint="not_axis_aligned",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    index = "xyz".index(axis)
    sign = 1.0 if normal[index] > 0.0 else -1.0
    direction = [0.0, 0.0, 0.0]
    direction[index] = sign
    return (direction[0], direction[1], direction[2])


@op_params
class ElephantFootParams(BaseParams):
    height: float = param(
        title=_("Höhe"),
        default=0.6,
        unit="mm",
        minimum=0.1,
        maximum=5.0,
        doc=_("Über wie viel Höhe eingezogen wird — etwa die ersten drei Schichten."),
    )
    amount: float = play_param(title=_("Betrag"), maximum=2.0)


@register_op(
    name="compensate_first_layer",
    result_kind="mesh",
    title=_("Elefantenfuß ausgleichen"),
    category="prepare",
    params=ElephantFootParams,
    consumes=1,
    produces=1,
    doc=_(
        "Zieht die ersten Schichten um den Betrag ein, um den sie beim Drucken "
        "breitlaufen. Der Wert kommt aus dem Materialprofil."
    ),
)
def compensate_first_layer(ctx: OpContext) -> OpResult:
    params = cast(ElephantFootParams, ctx.params)
    source = ctx.inputs[0]
    if ctx.profile is None:
        raise InternalError(detail="the elephant foot compensation needs a profile")

    mesh, findings, solver = compensate_elephant_foot(
        as_mesh_data(source.mesh),
        # Das Auseinanderlaufen gehört zum Material, und dieser Körper ist
        # vielleicht nicht im Material des Projekts (§12) — eine TPU-Dichtung
        # läuft weiter als das PETG um sie herum.
        for_object(ctx.profile, source),
        height=params.height,
        amount=params.amount or None,
        quality=ctx.quality,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh)], findings=findings, solver=solver
    )


@op_params
class MaterialParams(BaseParams):
    material: str = param(
        title=_("Material"),
        kind="material",
        default="",
        doc=_("Welches Material dieses Teil ist. Leer heißt: das des Projekts."),
    )


@register_op(
    name="set_material",
    title=_("Material festlegen"),
    category="prepare",
    params=MaterialParams,
    consumes=1,
    produces=1,
    doc=_(
        "Gibt diesem Körper ein eigenes Material. Toleranzen, Schwund und "
        "Elefantenfuß werden dann damit gerechnet und nicht mit dem des Projekts."
    ),
)
def set_material(ctx: OpContext) -> OpResult:
    """§12: eine Szene, mehr als ein Material.

    Ein Gehäuse in PETG mit einer Dichtung in TPU ist ein Projekt und zwei
    Materialien. Ohne das würden Spiel, Schrumpf und erste Schicht der Dichtung
    aus dem Material des Gehäuses gerechnet — Zahlen, die nicht ungefähr sind,
    sondern falsch, und falsch in der Richtung, die einen Druck zu Ausschuss
    macht.

    Die Kennung wird hier geprüft statt als feste Liste angeboten: zu den
    bekannten Materialien gehören die eigenen Profile des Nutzers, und die
    erscheinen, nachdem dieses Modul importiert wurde.
    """
    params = cast(MaterialParams, ctx.params)
    source = ctx.inputs[0]
    chosen = params.material.strip()
    if chosen:
        material(chosen)  # wirft mit der Liste der bekannten, wenn es keines ist

    return OpResult(
        outputs=[dataclasses.replace(source, material=chosen or None)],
        findings=[
            Finding(
                code="prepare.material",
                severity="info",
                message=_("Dieser Körper wird in einem eigenen Material gerechnet."),
                # **Ohne `str()`.** Der Aufruf löste den Namen in der Sprache
                # von jetzt auf und schrieb ihn fest: Im englischen Fenster
                # stand hier weiter „Deckel", während der Körper daneben im
                # Objektbaum „Lid" hieß — zwei Namen für dasselbe Teil in einem
                # Blick. Ein übersetzbarer Text wandert mit; aufgelöst wird
                # erst beim Anzeigen und beim Speichern.
                values={"object": source.name, "material": chosen or "-"},
            )
        ]
        if chosen
        else [],
    )


@op_params
class TestPieceParams(BaseParams):
    size: float = param(
        title=_("Kantenlänge"),
        default=20.0,
        unit="mm",
        minimum=2.0,
        maximum=200.0,
        doc=_("Wie groß der Ausschnitt wird. Groß genug, dass die Passung Material hat."),
    )
    x: float = param(
        title=_("Position X"),
        default=0.0,
        unit="mm",
        doc=_("Mitte des Ausschnitts — die Stelle, um die es geht."),
        placement="advanced",
    )
    y: float = param(
        title=_("Position Y"), default=0.0, unit="mm", doc=_WHERE_Y, placement="advanced"
    )
    z: float = param(
        title=_("Position Z"), default=0.0, unit="mm", doc=_WHERE_Z, placement="advanced"
    )
    on_bed: bool = param(
        title=_("Auf das Bett setzen"),
        default=True,
        doc=_("Legt das Prüfstück flach hin, damit es ohne Stützen druckt."),
    )


@register_op(
    name="test_piece",
    result_kind="mesh",
    # 2 seit dem 22.09.2026: Der Name bleibt übersetzbar (``Scene.unused_name``)
    # statt in der Sprache der Rechnung im Ergebnis-Cache zu stehen.
    cache_version="2",
    title=_("Prüfstück erzeugen"),
    category="prepare",
    params=TestPieceParams,
    consumes=1,
    produces=1,
    applies_to=["hole", "pin", "face"],
    doc=_(
        "Schneidet einen Würfel um eine Stelle heraus, um sie zu drucken und "
        "auszuprobieren — zwei Minuten statt zwei Stunden."
    ),
)
def test_piece(ctx: OpContext) -> OpResult:
    """§28.3, aus der Praxis: eine Passung prüft man am Ausschnitt, nicht am Teil.

    Der Ausschnitt ist eine Verschneidung mit einem Würfel — heraus kommt also
    die echte Geometrie mit den echten Toleranzen, keine nachgebaute Näherung
    davon. Ein Prüfstück, das anders druckt als das Teil, für das es steht,
    wäre schlechter als gar kein Test.
    """
    params = cast(TestPieceParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    window = trimesh.creation.box(extents=(params.size, params.size, params.size))
    window.apply_translation((params.x, params.y, params.z))
    # Ein Fenster über leerem Raum ist eine Antwort, keine gescheiterte
    # Operation: ohne ``allow_empty`` probierte die Kette drei weitere Stufen
    # und würfe dann — und der Nutzer läse etwas über den Voxel-Solver statt
    # über das Loch, auf das er gezielt hat.
    outcome = boolean(
        "intersection", [mesh, mesh.replacing(window)], quality=ctx.quality, allow_empty=True
    )

    piece = outcome.mesh
    if not piece.triangle_count or is_zero(piece.volume):
        raise ValidationError(
            field="size",
            detail=_("An dieser Stelle ist kein Material — der Ausschnitt bleibt leer."),
            constraint="empty",
            values={"size_mm": round(params.size, 2)},
        )
    if params.on_bed:
        piece = place_on_bed(piece)

    share = abs(piece.volume) / max(abs(mesh.volume), EPS_GEOM)
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=piece,
                # Wie beim Deckel: kein Quellbezug, kein eingefrorenes Wort.
                name=ctx.scene.unused_name(_("Prüfstück")),
                features={},
            )
        ],
        solver=outcome.solver,
        findings=[
            *outcome.findings,
            Finding(
                code="prepare.test_piece",
                severity="info",
                message=_("Ein Ausschnitt zum Ausprobieren — die Maße sind die des Teils."),
                object_id=source.id,
                values={"share_percent": round(share * 100.0, 1), "size_mm": params.size},
            ),
        ],
    )


@op_params
class SplitPinnedParams(BaseParams):
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=_AXES,
        doc=_("Senkrecht zu welcher Achse geschnitten wird. Z legt einen waagerechten Schnitt."),
    )
    position: float = param(
        title=_("Position"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wo die Schnittebene liegt, auf dieser Achse gemessen. Die Zahl bleibt "
            "änderbar: ein Doppelklick auf den Schritt verschiebt den Schnitt."
        ),
    )
    pins: int = param(
        title=_("Passstifte"),
        default=PIN_COUNT,
        minimum=0,
        maximum=6,
        doc=_("Null heißt: nur schneiden. Zwei halten die Hälften gegen Verdrehen."),
    )
    shape: str = param(
        title=_("Stiftform"),
        default="round",
        choices=CONNECTOR_SHAPES,
        placement="advanced",
        doc=_CONNECTOR_DOC,
    )
    glue_hint: bool = param(
        title=_("Kleben empfohlen"),
        default=False,
        placement="advanced",
        doc=_(
            "Automatisch teilen schaltet dies ein, wenn weder Schwalbenschwanz noch "
            "Schnapper zur Naht passen."
        ),
    )
    diameter: float = param(
        title=_("Stiftdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=PIN_MAX,
        placement="advanced",
        doc=_("Null heißt: aus der Schnittfläche ableiten."),
    )
    play: float = play_param()
    pins_on_b: bool = param(
        title=_("Stifte an Hälfte B"),
        default=False,
        placement="advanced",
        doc=_(
            "Welche Hälfte die Stifte trägt: A liegt auf der kleineren Seite der Ebene, "
            "B auf der größeren. Automatisch teilen wählt die Seite, deren Hälften "
            "zusammen weniger Stützen brauchen."
        ),
    )


@op_params
class SplitBodiesParams(BaseParams):
    count: int = param(
        title=_("Anzahl"),
        default=2,
        minimum=2,
        maximum=64,
        doc=_(
            "In wie viele Objekte zerlegt wird. Die Zahl steht hier und nicht "
            "erst im Ergebnis, weil der Stapel die Kennungen seiner Ausgänge "
            "vergibt, bevor gerechnet wird. Wie viele Teile der Körper "
            "tatsächlich hat, sagt der Prüfbericht — und diese Operation "
            "nennt die Zahl, wenn sie nicht passt."
        ),
    )
    keep_tiny: bool = param(
        title=_("Splitter behalten"),
        default=False,
        doc=_(
            "Auch Bruchstücke unter einem Prozent des größten Teils behalten. "
            "Aus Scans kommen oft einzelne lose Dreiecke — die will man selten "
            "als eigenes Modell."
        ),
    )


def _gap_between(one: Any, other: Any) -> float:
    """Der Abstand zweier Hüllquader — null, wo sie sich überlappen.

    Für die Frage, welchem Teil ein überzähliges am nächsten liegt, genügt
    das: Der Punkt über dem i steht seinem Strich näher als dem l daneben,
    weil ihre Quader in x überlappen und nur die Lücke darüber zählt. Ein
    Schwerpunktabstand sähe das anders — der Strich ist lang, sein
    Schwerpunkt weit unten, und das l gewönne.
    """
    low = np.maximum(np.asarray(one.bounds[0]), np.asarray(other.bounds[0]))
    high = np.minimum(np.asarray(one.bounds[1]), np.asarray(other.bounds[1]))
    return float(np.linalg.norm(np.maximum(low - high, 0.0)))


#: Ein loses Teil eines Körpers: sein Netz, sein Volumen und die Slots seiner
#: Dreiecke — leer, wo der Körper keine trug.
LoosePart = tuple[Any, float, tuple[int, ...]]


def _loose_parts(mesh: MeshData, *, keep_tiny: bool) -> tuple[list[LoosePart], int]:
    """Die losen Teile eines Körpers samt Volumen und Slots, größte zuerst —
    und wie viele Splitter dabei wegfielen.

    Die eine Zählung für *In Einzelteile zerlegen* und für die Absage des
    Ausrichtens, die diese Zerlegung vorschlägt: Ohne ``keep_tiny`` fällt
    weg, was unter einem Prozent des größten Teils liegt, und eine Stückzahl,
    die die Splitter mitzählte, ließe die Zerlegung an ihrer eigenen Prüfung
    scheitern.

    **Je Teil reisen die Slots seiner Dreiecke mit** (Robert, 11.09.2026:
    „Filamente auch nicht"): Ein Schriftzug, dem *Filament zuweisen* Slot 7
    gegeben hatte, kam nach der Zerlegung beim Slicer auf einem zweiten
    Filament „Slot 0" an, das orangene daneben unbenutzt. ``Trimesh.split``
    kennt Solidons Slot je Dreieck nicht, und ``MeshData.replacing`` lässt
    eine Liste fallen, die nicht mehr zur Dreieckszahl passt — die Teile
    hatten damit keine, und der Export ergänzte den neutralen Platzhalter.
    Gezählt wird deshalb über :func:`face_components` — dieselbe Frage, die
    der Prüfbericht mit „besteht aus N Teilen" beantwortet, also auch dieselbe
    Zahl —, und aus den Dreiecksnummern jedes Teils kommt sein Stück der
    Slotliste.
    """
    groups = face_components(mesh.raw)
    # ``append=False`` gibt eine Liste, ein Netz je Gruppe — der Typ von
    # ``submesh`` kennt beide Formen, der Aufruf hier nur die eine.
    bodies = cast(
        "list[Any]",
        mesh.raw.submesh(groups, only_watertight=False, append=False) if groups else [],
    )
    painted = np.asarray(mesh.slots, dtype=np.int32) if mesh.slots else None
    found: list[LoosePart] = [
        (
            body,
            abs(float(body.volume)),
            tuple(int(value) for value in painted[group]) if painted is not None else (),
        )
        for body, group in zip(bodies, groups, strict=True)
    ]
    largest = max((volume for _body, volume, _slots in found), default=0.0) or 1.0
    kept = [entry for entry in found if keep_tiny or entry[1] >= largest * 0.01]
    kept.sort(key=lambda entry: (-round(entry[1] / largest, _SAME_SIZE), _where_it_sits(entry[0])))
    return kept, len(found) - len(kept)


#: Ab welcher Stelle zwei Teile als **gleich groß** gelten — relativ zum
#: größten, nicht absolut, denn ein Volumen von 20 000 mm³ und eines von 2 mm³
#: rauschen verschieden stark.
#:
#: **Neun Stellen, und die Zahl ist gemessen** (12.09.2026 an *Solidon3D*): Die
#: beiden `o` sind Punkt auf Punkt gleich groß, ihre gerechneten Volumina
#: unterschieden sich bei 110 mm um 1e-10 von 19 559 — fünf Größenordnungen
#: unter der letzten Stelle einer doppelten Genauigkeit, also Rauschen aus der
#: Tessellierung und keine Aussage über die Form. Neun Stellen liegen weit über
#: diesem Rauschen und weit unter jedem echten Unterschied: Die nächsten zwei
#: wirklich verschiedenen Buchstaben desselben Schriftzugs trennen zehn
#: Prozent.
_SAME_SIZE = 9


def _where_it_sits(body: Any) -> tuple[float, float, float]:
    """Die Mitte des Hüllquaders — das Zweitkriterium beim Sortieren.

    **Zwei gleich große Teile hatten keine Ordnung** (gemessen am 12.09.2026 an
    *Solidon3D* über acht Schriftgrößen): Die beiden `o` sind gleich groß, und
    bei Gleichstand entschied, in welcher Reihenfolge :func:`face_components`
    sie liefert. Bei 110 und 120 mm tauschten `obj_5` und `obj_6` ihre Nummer,
    bei 100, 130 und 150 nicht.

    Bei zwei gleichen Teilen ist der Tausch folgenlos — aber **jeder spätere
    Schritt hängt an der Objektkennung**, und nach einer Parameteränderung
    griffe er am anderen Teil: eine Filamentzuweisung, eine Bohrung, ein Zug
    am Griff. Die Lage entscheidet das eindeutig und übersteht eine
    Größenänderung: Skaliert der ganze Schriftzug, skalieren alle Mitten mit
    demselben Faktor um denselben Punkt, und ihre Ordnung bleibt.

    Nur der **Gleichstand** wird damit festgenagelt, nicht die Sortierung
    selbst — die bleibt das Volumen, denn sie entscheidet, welche Teile bei
    einer zu kleinen Stückzahl einzeln stehen (siehe :data:`_SAME_SIZE` dazu,
    ab wann zwei Volumina als gleich gelten).
    """
    centre = body.bounds.mean(axis=0)
    return (float(centre[0]), float(centre[1]), float(centre[2]))


#: Warum *In Einzelteile zerlegen* an einem Stück nichts tut — derselbe Satz
#: im Menü (``requires_body="parts"``, ``labels.body_requirement``).
ONE_PIECE: Final = _("Der Körper besteht aus einem Stück; es gibt nichts zu zerlegen.")


@register_op(
    name="split_bodies",
    result_kind="mesh",
    title=_("In Einzelteile zerlegen"),
    category="prepare",
    params=SplitBodiesParams,
    consumes=1,
    produces=VARIABLE,
    produces_from="count",
    requires_body="parts",
    doc=_(
        "Macht aus einem Körper, der aus mehreren nicht verbundenen Teilen "
        "besteht, je ein eigenes Objekt. Was nicht zusammenhängt, ist nicht "
        "ein Teil — eine STL weiß das nicht, die Geometrie schon."
    ),
    caveat=_(
        "Nur was sich nicht berührt, wird getrennt. Zwei Teile, die an einer "
        "Fläche aneinanderliegen, sind für die Geometrie eines — dort hilft "
        "Teilen an einer Ebene."
    ),
)
def split_bodies(ctx: OpContext) -> OpResult:
    """Je Zusammenhangskomponente ein Objekt.

    **Der Ausgang bleibt, was er war.** Material, Filamentzuweisung und die
    erkannten Merkmale gehen mit; getrennt wird die Geometrie, nicht die
    Beschreibung. Die Merkmale wandern zu dem Teil, dessen Dreiecke sie
    tragen — ein Merkmal, dessen Flächen auf zwei Teile fielen, gäbe es nicht,
    denn dann hingen die Teile zusammen.
    """
    source = ctx.inputs[0]
    params = cast(SplitBodiesParams, ctx.params)
    mesh = as_mesh_data(source.mesh)
    kept, dropped = _loose_parts(mesh, keep_tiny=params.keep_tiny)

    # **Genau so viele, wie die Stückzahl sagt.** Der Stapel vergibt die
    # Kennungen der Ausgänge, bevor gerechnet wird (§15.2); eine Operation, die
    # nachher eine andere Zahl liefert, hält die ganze Kette an. Ist zu wenig
    # da, wird das gesagt statt geraten — mit der Zahl, die passen würde.
    found = len(kept)
    if found < params.count:
        raise ValidationError(
            field="count",
            detail=(
                ONE_PIECE
                if found <= 1
                # **Ohne Platzhalter.** Ein Fehlertext wird nirgends
                # nachformatiert — `show_details` zeigt ihn, wie er ist, und
                # hängt `values` als eigene Zeilen darunter. Ein `{found}`
                # stünde beim Kunden mit geschweiften Klammern da.
                else _("Der Körper hat weniger Teile, als die Stückzahl verlangt.")
            ),
            constraint="too_many_parts",
            values={"count": str(params.count), "found": str(found)},
            # Mit der gemessenen Zahl ist es ein Klick (``recount_and_retry``);
            # aus einem Stück wird auch mit einer anderen Zahl nichts.
            suggestions=(
                (RECOUNT_AND_RETRY, CORRECT_INPUT, CANCEL)
                if found >= 2
                else (CORRECT_INPUT, CANCEL)
            ),
        )

    # **Mehr Teile als verlangt: Jedes überzählige schlägt sich dem nächsten
    # zu.** Die ``count`` größten stehen einzeln, und was übrig ist, geht zu
    # dem von ihnen, das ihm am nächsten liegt — der Punkt bleibt bei seinem
    # i. Bis zum 11.09.2026 blieb der Rest als *ein* Objekt beieinander, nach
    # Volumen gewählt: Bei einem Schriftzug mit neun Buchstaben und zehn
    # Teilen war das Punkt und i-Strich, bis ein Schriftwechsel andere zwei
    # zu den kleinsten machte — die lagen einen halben Meter auseinander, und
    # das Ausrichten fand für das Paar keine Lage (Robert: „die anzahl hat
    # sich ja nicht verändert"). Die Nähe ändert sich mit der Schrift nicht.
    surplus = found - params.count
    if surplus:
        anchors = [[entry] for entry in kept[: params.count]]
        for entry in kept[params.count :]:
            nearest = min(
                range(len(anchors)), key=lambda i: _gap_between(entry[0], anchors[i][0][0])
            )
            anchors[nearest].append(entry)
        # ``concatenate`` hängt die Dreiecke in der Reihenfolge der Teile
        # aneinander — die Slots in derselben Reihenfolge dazu.
        kept = [
            (
                group[0][0]
                if len(group) == 1
                else cast("Any", trimesh.util.concatenate([entry[0] for entry in group])),
                sum(entry[1] for entry in group),
                tuple(value for entry in group for value in entry[2]),
            )
            for group in anchors
        ]

    outputs = []
    for number, (part, _volume, slots) in enumerate(kept, start=1):
        outputs.append(
            dataclasses.replace(
                source,
                # Nicht ``mesh.replacing(part)``: Das behielte die Slots nur
                # bei gleicher Dreieckszahl, und die hat kein Teil.
                mesh=MeshData.of(part, slots),
                name=f"{source.name} {number}",
                # Die Merkmale des Ausgangs zeigen auf dessen Dreiecke; nach
                # der Trennung zählt jedes Teil eigene. Sie neu zu erkennen ist
                # Sache der Erkennung, nicht dieser Operation — sie mitzugeben
                # wäre eine Behauptung über Flächen, die es so nicht mehr gibt.
                features={},
            )
        )

    findings = []
    if surplus:
        findings.append(
            Finding(
                code="split_bodies.surplus",
                # Eine Warnung, kein Hinweis (Robert, 11.09.2026: „eine warnung
                # bei in einzelteile zerlegen" ): Die Stückzahl sagt etwas
                # anderes als der Körper, und der Weg dahin ist ein Klick.
                severity="warning",
                # **Gefüllt vom Übersetzer** (``_(…, count=…)``): Einen Befund
                # formatiert niemand nach, und der Kunde las „{count} weitere
                # Teile" mit geschweiften Klammern (Bildschirmfoto Robert,
                # 11.09.2026).
                message=_(
                    "{count} weitere Teile wurden dem jeweils nächsten Teil zugeschlagen.",
                    count=surplus,
                ),
                values={"count": str(surplus), "found": str(found), "object": str(source.name)},
                suggestions=(RECOUNT_AND_RETRY,),
            )
        )
    if dropped:
        findings.append(
            Finding(
                code="split_bodies.tiny",
                severity="info",
                message=_("{count} Splitter unter einem Prozent wurden verworfen.", count=dropped),
                # Die Splitter gehörten dem ganzen Körper, nicht seinem größten
                # Teil: Der Name des Ausgangs steht in der Zeile, eine Kennung
                # hat er nach der Zerlegung nicht mehr.
                values={"count": str(dropped), "object": str(source.name)},
            )
        )
    return OpResult(outputs=outputs, findings=findings)


@register_op(
    name="split_pinned",
    result_kind="mesh",
    # Nicht mehr „Teilen und verstiften": Seit *An Ebene teilen* in dieser
    # Operation aufgegangen ist (Formatversion 11), ist es die eine Zeile für
    # beides — mit Stiften und ohne. Ein Titel, der die Stifte verspricht,
    # wäre für die Hälfte der Fälle falsch; das Feld *Passstifte* sagt,
    # welcher Fall gilt, und seine Null ist der ganze Unterschied.
    title=_("Teilen"),
    category="prepare",
    params=SplitPinnedParams,
    consumes=1,
    produces=2,
    doc=_(
        "Teilt ein Objekt an einer Ebene, auf Wunsch mit Passstiften in der "
        "Schnittfläche. Das Spiel kommt aus dem Materialprofil; null Stifte heißt: "
        "nur schneiden."
    ),
    caveat=_(
        "Nicht bei Teilen, deren Schnittfläche sichtbar bleibt: Die Naht liegt an "
        "einer Ebene und ist es danach auch. Wo sie stören würde, lieber die Lage "
        "ändern oder eine Stelle wählen, an der ohnehin eine Kante läuft."
    ),
)
def split_pinned(ctx: OpContext) -> OpResult:
    """§25: der Schnitt und die Stifte in einem Schritt, denn sie gehören
    zusammen.

    Eine Naht ohne Stifte ist eine Naht, die jemand von Hand ausrichten muss,
    während der Kleber greift; ein Stift ohne Naht ist nichts. Beides in einer
    Operation heißt außerdem: ein Undo nimmt das Ganze zurück.
    """
    params = cast(SplitPinnedParams, ctx.params)
    plane = SectionPlane(normal=AXIS_NORMALS[cast(Axis, params.axis)], position=params.position)
    return _cut_and_pin(
        ctx,
        plane,
        pins=params.pins,
        shape=params.shape,
        glue_hint=params.glue_hint,
        diameter=params.diameter,
        play=params.play,
        pins_on_b=params.pins_on_b,
    )


def _cut_and_pin(
    ctx: OpContext,
    plane: SectionPlane,
    *,
    pins: int,
    shape: str,
    glue_hint: bool,
    diameter: float,
    play: float,
    pins_on_b: bool = False,
) -> OpResult:
    """Der gemeinsame Teil von *Teilen* und *An Linie trennen*.

    Die beiden unterscheiden sich einzig darin, **woher die Ebene kommt** —
    aus einer Achse und einer Zahl oder aus zwei angeklickten Punkten. Alles
    danach ist dasselbe, und zweimal geschrieben wäre es beim ersten Nachbessern
    an einer Stelle anders.
    """
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)
    connector_start = next_connector_index(source.features)

    first, second, findings = split_at_plane(mesh, plane)
    # **Verorten kann nur die Operation** (RM-039). `split_at_plane` rechnet auf
    # einem Netz und kennt keine Kennungen; eine Berichtshandlung liest ihr Ziel
    # aber aus dem Befund und nicht aus der Auswahl — ohne den Körper führte
    # *Reparieren und erneut versuchen* ins Leere. Dieselbe Aufteilung wie beim
    # Aushöhlen, und derselbe Satz steht dort.
    findings = [dataclasses.replace(entry, object_id=source.id) for entry in findings]
    _both_halves_or_stop(first, second, plane.position)

    # **Der Wunschdurchmesser geht in die Planung hinein**, nicht hinterher in
    # ihr Ergebnis. Bis zum 02.09.2026 stand hier ein ``dataclasses.replace``
    # auf dem fertigen Plan: Es tauschte das eine Feld und ließ Sitzpuffer,
    # Materialtiefe, Länge und Formwahl stehen, wie sie für den *abgeleiteten*
    # Durchmesser gerechnet waren. Ein 8-mm-Stift in einer 10 mm starken Platte
    # ließ damit 0,875 mm Wand stehen statt der geforderten 1,6 und band 4,5 mm
    # ein statt der nötigen 6,0 — ohne einen einzigen Befund.
    plan = (
        plan_pins(mesh, plane, count=pins, shape=shape, diameter=diameter or None) if pins else None
    )

    # **``ctx.profile`` ist nach §9 keine Option**, und die zweite Bedingung
    # hier war es doch: ``plan is not None and ctx.profile is not None``. Der
    # ``else``-Zweig dahinter konnte nie laufen — und er warf die Befunde des
    # Stiftplans weg, also genau die Sätze, die sagen, *warum* aus zwei
    # verlangten Stiften keiner wurde. Ein toter Zweig, der im Ernstfall das
    # Falsche getan hätte; mypy nennt ihn seit ``warn_unreachable`` beim Namen.
    #
    # Beide Hälften kommen aus diesem einen Körper, das Spiel ist also das
    # seines Materials.
    #
    # **Welche Hälfte die Stifte trägt, ist ein Wert** (RM-005): Die Stifte
    # stehen über die Naht hinaus, und die Hälfte mit ihnen kann nicht mehr
    # auf der Naht liegen. *Automatisch teilen* vergleicht beide Zuordnungen am
    # fertigen Stützvolumen und schreibt die bessere hierher. B trägt die
    # Stifte über denselben Plan mit umgedrehter Normale — die Stellen sind
    # dieselben, sie liegen auf der Ebene.
    carrier, drilled = (second, first) if pins_on_b else (first, second)
    placed_plan = (
        dataclasses.replace(plan, normal=_reversed(plan.normal))
        if plan is not None and pins_on_b
        else plan
    )
    pair = (
        add_pins(
            carrier,
            drilled,
            placed_plan,
            for_object(ctx.profile, source),
            start=connector_start,
            play=play or None,
            quality=ctx.quality,
            cancelled=ctx.cancelled,
        )
        if placed_plan is not None
        else PinnedPair(first=carrier, second=drilled)
    )
    if glue_hint and plan is not None and plan.count and plan.shape == "round":
        pair.findings.append(connector_glue_finding())

    first_features, second_features = _features_after_split(source.features, plane, source.mesh)
    first_name, second_name = half_names(
        source.name, pinned=bool(pair.pin_features), pins_on_b=pins_on_b
    )
    first_mesh, second_mesh = (pair.second, pair.first) if pins_on_b else (pair.first, pair.second)
    first_added, second_added = (
        (pair.bore_features, pair.pin_features)
        if pins_on_b
        else (pair.pin_features, pair.bore_features)
    )
    return OpResult(
        solver=pair.solver,
        outputs=[
            dataclasses.replace(
                source,
                mesh=first_mesh,
                name=first_name,
                features={**first_features, **first_added},
            ),
            dataclasses.replace(
                source,
                mesh=second_mesh,
                name=second_name,
                features={**second_features, **second_added},
            ),
        ],
        findings=[*findings, *pair.findings, _halves_still_together(source)],
    )


def _reversed(normal: Vec3) -> Vec3:
    """Dieselbe Richtung, umgedreht."""
    return (-normal[0], -normal[1], -normal[2])


def _features_after_split(
    features: dict[str, Feature], plane: SectionPlane, mesh: Mesh | None = None
) -> tuple[dict[str, Feature], dict[str, Feature]]:
    """Nimmt bestehende Merkmale auf die geometrisch richtige Hälfte mit.

    Ein Merkmal genau auf dem neuen Schnitt wird selbst getrennt und kann
    deshalb nicht unverändert weitergelten. Ohne Mittelpunkt bleibt das alte
    Verhalten erhalten: Es reist mit der ersten Hälfte, statt geraten zu
    werden.

    **Liegt die ganze Fläche eines Merkmals auf einer Seite, entscheidet sie**
    (:func:`_surface_side`), nicht sein Mittelpunkt: Der einer Verrundung ist
    ein Punkt ihrer Achse, und die liegt bei einer Kehle außerhalb des
    Materials — am Besenhalter jenseits der Ebene, während die ganze gerundete
    Fläche diesseits lag (RM-217, Durchsicht 0.5.1). Verbinder behalten ihre
    eigene Regel; was die Ebene quert, entscheidet weiter der Mittelpunkt.
    """
    first: dict[str, Feature] = {}
    second: dict[str, Feature] = {}
    for feature_id, feature in features.items():
        connector = feature_id.startswith(("pin_", "bore_"))
        side = None if connector else _surface_side(feature, plane, mesh)
        if side is None:
            side = feature_side(feature, plane, connector=connector)
        if side in (-1, None):
            first[feature_id] = feature
        elif side == 1:
            second[feature_id] = feature
    return first, second


def _surface_side(feature: Feature, plane: SectionPlane, mesh: Mesh | None) -> FeatureSide | None:
    """Auf welcher Seite der Ebene jedes Dreieck eines Merkmals liegt — oder ``None``.

    ``None`` heißt: kein Netz, keine gültigen Dreiecke, oder die Fläche quert
    die Ebene beziehungsweise berührt sie. Gerechnet wird mit
    Grundrechenarten (RM-187), verglichen mit ``EPS_GEOM``.
    """
    if not isinstance(mesh, MeshData) or not feature.face_indices:
        return None
    faces = np.asarray(feature.face_indices, dtype=np.int64)
    if int(faces.min()) < 0 or int(faces.max()) >= mesh.triangle_count:
        return None
    normal = np.asarray(plane.normal, dtype=float)
    length = math.sqrt(float((normal * normal).sum()))
    if length <= EPS_GEOM:
        return None
    corners = np.asarray(mesh.raw.vertices, dtype=float)[
        np.asarray(mesh.raw.faces, dtype=np.int64)[faces].ravel()
    ]
    distances = (corners * (normal / length)).sum(axis=1) - plane.position
    if bool((distances < -EPS_GEOM).all()):
        return -1
    if bool((distances > EPS_GEOM).all()):
        return 1
    return None


@op_params
class CutAwayParams(BaseParams):
    axis: str = param(
        title=_("Achse"),
        default="z",
        choices=_AXES,
        doc=_("Senkrecht zu welcher Achse geschnitten wird. Z legt einen waagerechten Schnitt."),
    )
    position: float = param(
        title=_("Position"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wo die Schnittebene liegt, auf dieser Achse gemessen. Die Zahl bleibt "
            "änderbar: ein Doppelklick auf den Schritt verschiebt den Schnitt."
        ),
    )
    keep: str = param(
        title=_("Bleibt"),
        default="below",
        choices=("below", "above"),
        doc=_("Welche Seite der Ebene stehen bleibt. Die andere fällt weg."),
    )


@register_op(
    name="cut_away",
    result_kind="mesh",
    # 2 seit dem 22.09.2026: Eine offene Schnittfläche wird gemeldet
    # (``cut_away.uncapped``) — ein Ergebnis aus dem Cache trüge den Befund nicht.
    cache_version="2",
    title=_("Abschneiden"),
    category="prepare",
    params=CutAwayParams,
    consumes=1,
    produces=1,
    doc=_(
        "Schneidet ein Objekt an einer Ebene ab und behält eine Seite — die "
        "Schnittfläche wird geschlossen. Für eine Rückwand, die bündig werden soll, "
        "oder Wände, die auf eine Höhe kommen: erst abschneiden, dann die neue "
        "Fläche versetzen."
    ),
    caveat=_(
        "Was auf der anderen Seite lag, ist danach fort — auch Bohrungen und "
        "Bausteine dort. Wer beide Teile braucht, nimmt Teilen."
    ),
)
def cut_away(ctx: OpContext) -> OpResult:
    """Ein Schnitt, eine Seite — das halbe Teilen, das der Halter braucht.

    *Teilen* liefert zwei Körper, und wer nur einen wollte, löschte den
    anderen: zwei Schritte für eine Absicht, viermal an einem Halter mit
    Becher (Robert, 16.09.2026: „warum haben wir das alles so kompliziert").
    Die Schnittfläche kommt geschlossen zurück und lässt sich danach als
    ebene Fläche versetzen — der Weg, Wände auf eine Höhe zu bringen.
    """
    params = cast(CutAwayParams, ctx.params)
    plane = SectionPlane(normal=AXIS_NORMALS[cast(Axis, params.axis)], position=params.position)
    if params.keep == "above":
        plane = plane.flipped()
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)
    kept = cut(mesh, plane)
    if not kept.mesh.triangle_count or kept.mesh.triangle_count == mesh.triangle_count:
        # Nichts übrig oder nichts weggenommen: beides ist eine Ebene, die das
        # Objekt nicht trifft — dieselbe Absage wie beim Teilen, mit dem Feld.
        raise ValidationError(
            field="position",
            detail=_("Diese Ebene schneidet nichts vom Objekt ab."),
            value=params.position,
            constraint="no_split",
        )
    features, _dropped = _features_after_split(source.features, plane, source.mesh)
    # **Eine offene Schnittfläche wird gesagt, nicht verschwiegen.** *Teilen*
    # meldet sie seit je (``split.uncapped``); *Abschneiden* ging denselben
    # Schnitt bis zum 22.09.2026 ohne ein Wort, und der Körper kam mit offener
    # Schnittfläche zurück. ``capped`` ist die Wasserdichtheit der Eingabe —
    # das Modell war schon vorher offen, und der Weg nach vorn ist dasselbe
    # Reparieren wie dort.
    findings = (
        []
        if kept.capped
        else [
            Finding(
                code="cut_away.uncapped",
                severity="warning",
                message=_(
                    "Die Schnittfläche bleibt offen: Das Modell ist schon vor dem Schnitt "
                    "nicht geschlossen. Reparieren Sie es und schneiden Sie danach erneut."
                ),
                object_id=source.id,
                suggestions=(REPAIR_AND_RETRY,),
            )
        ]
    )
    return OpResult(
        outputs=[
            dataclasses.replace(source, mesh=kept.mesh, features=_without_old_triangles(features))
        ],
        findings=findings,
    )


def _halves_still_together(source: SceneObject) -> Finding:
    """Zwei Hälften an ihrem Platz sehen aus wie ein Körper.

    Das Teilen setzt beide Stücke dorthin, wo sie im ganzen Teil lagen —
    richtig so, denn erst damit passen sie noch zusammen, und die Passstifte
    sitzen aufeinander. Im Bild ist das Ergebnis aber von der Ausgangslage
    nicht zu unterscheiden: ein Schritt im Verlauf, zwei Zeilen im Baum, und
    davor ein Körper, der aussieht wie vorher (Fund 27, 27.08.2026).

    Der Nachbarbefund ``arrange.bodies_in_one_place`` greift hier **nicht**:
    Er sucht Körper, die sich in Hüllquader und Volumen gleichen, und zwei
    komplementäre Hälften tun genau das nicht. Deshalb sagt es die Operation
    selbst — sie ist die einzige Stelle, die weiß, dass die zwei Körper
    zusammengehören.

    Ein Hinweis und keine Warnung: Nichts ist schiefgegangen, und wer gleich
    exportiert, bekommt zwei richtige Dateien. Die Handlung daneben ist
    *Auf dem Bett anordnen* — dieselbe, die auch die Nachbarbefunde tragen.
    """
    return Finding(
        code="prepare.halves_in_place",
        severity="info",
        message=_(
            "Die zwei Hälften liegen noch aneinander — im Bild sieht das aus wie ein Teil. "
            "Zum Drucken nebeneinander legen."
        ),
        object_id=source.id,
    )


@op_params
class SplitLineParams(BaseParams):
    """Die Trennebene aus einer gezeichneten Linie.

    Was der Nutzer tut, ist zwei Punkte anklicken; was gespeichert wird, ist
    die Ebene, die daraus folgt. Beides ist dieselbe Angabe — nur ist die
    Ebene die, die sich hinterher noch verschieben lässt, und ein Punktpaar
    wäre eine Zahlenkolonne, an der niemand etwas nachbessert.
    """

    position: float = param(
        title=_("Lage"),
        default=0.0,
        unit="mm",
        doc=_(
            "Wie weit die Trennebene vom Nullpunkt entfernt liegt, in Trennrichtung "
            "gemessen. Die gezeichnete Linie trägt die Zahl ein; nachträglich "
            "verschiebt sie den Schnitt, ohne ihn zu drehen."
        ),
    )
    pins: int = param(
        title=_("Passstifte"),
        default=PIN_COUNT,
        minimum=0,
        maximum=6,
        doc=_(
            "Stifte auf der einen Hälfte, Bohrungen auf der anderen — sie halten die "
            "Teile beim Kleben in Deckung. Null heißt: nur trennen."
        ),
    )
    normal_x: float = param(
        title=_("Trennrichtung X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Richtung, in der die Ebene steht. Die gezeichnete Linie trägt sie ein — "
            "von Hand gesetzt ergeben die drei Zahlen zusammen einen Pfeil senkrecht "
            "zur Schnittfläche."
        ),
    )
    normal_y: float = param(
        title=_("Trennrichtung Y"),
        default=0.0,
        placement="advanced",
        doc=_("Zweite Achse der Trennrichtung — siehe Trennrichtung X."),
    )
    normal_z: float = param(
        title=_("Trennrichtung Z"),
        default=1.0,
        placement="advanced",
        doc=_("Dritte Achse der Trennrichtung — siehe Trennrichtung X."),
    )
    shape: str = param(
        title=_("Stiftform"),
        default="round",
        choices=CONNECTOR_SHAPES,
        placement="advanced",
        doc=_CONNECTOR_DOC,
    )
    diameter: float = param(
        title=_("Stiftdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=PIN_MAX,
        placement="advanced",
        doc=_("Null heißt: aus der Schnittfläche ableiten."),
    )
    play: float = play_param()
    pins_on_b: bool = param(
        title=_("Stifte an Hälfte B"),
        default=False,
        placement="advanced",
        doc=_(
            "Welche Hälfte die Stifte trägt: A liegt auf der kleineren Seite der Ebene, "
            "B auf der größeren. Automatisch teilen wählt die Seite, deren Hälften "
            "zusammen weniger Stützen brauchen."
        ),
    )
    glue_hint: bool = param(
        title=_("Kleben empfohlen"),
        default=False,
        placement="advanced",
        doc=_(
            "Automatisch teilen schaltet dies ein, wenn weder Schwalbenschwanz noch "
            "Schnapper zur Naht passen."
        ),
    )


@register_op(
    name="split_line",
    result_kind="mesh",
    title=_("An gezeichneter Linie trennen"),
    category="prepare",
    params=SplitLineParams,
    consumes=1,
    produces=2,
    icon="split",
    doc=_(
        "Trennt ein Objekt entlang einer im Bild gezeichneten Linie und setzt auf "
        "Wunsch Passstifte in die Schnittfläche."
    ),
    caveat=_(
        "Der Schnitt ist eine Ebene, keine Kurve: Die Linie legt fest, wo und wie "
        "schräg getrennt wird, und die Ebene läuft von dort gerade durch das Teil. "
        "Wer um eine Rundung herum trennen will, teilt zweimal."
    ),
)
def split_line(ctx: OpContext) -> OpResult:
    """§25: derselbe Schnitt wie *Teilen und verstiften*, nur mit einer Ebene,
    die nicht an einer Achse hängt.

    Zwei Punkte auf dem Körper und die Blickrichtung spannen sie auf — das ist
    die Rechnung, die das Fenster macht, bevor es hier ankommt. Hier steht nur
    noch die fertige Ebene, und das ist Absicht: Eine Operation, die von der
    Kamerastellung abhinge, wäre beim zweiten Auswerten eine andere (§11.2).
    """
    params = cast(SplitLineParams, ctx.params)
    normal = (params.normal_x, params.normal_y, params.normal_z)
    if _length(normal) <= EPS_GEOM:
        raise ValidationError(
            field="normal_z",
            detail=_("Ohne Trennrichtung gibt es keine Ebene."),
            value=0.0,
            constraint="no_normal",
        )
    return _cut_and_pin(
        ctx,
        SectionPlane(normal=normal, position=params.position),
        pins=params.pins,
        shape=params.shape,
        glue_hint=params.glue_hint,
        diameter=params.diameter,
        play=params.play,
        pins_on_b=params.pins_on_b,
    )


def _length(vector: tuple[float, float, float]) -> float:
    return float(sum(entry * entry for entry in vector) ** 0.5)


def _share_of(progress: ProgressFn | None, number: int, total: int) -> ProgressFn | None:
    """Ein Fortschritt, der nur seinen Abschnitt des Ganzen meldet.

    Bei mehreren Körpern liefe der Balken sonst je Körper von vorn — vier Teile
    ergäben vier volle Läufe, und der Kunde sähe nicht, wie weit der Auftrag
    wirklich ist.
    """
    if progress is None or total <= 1:
        return progress

    def share(fraction: float, text: str = "") -> None:
        progress((number + max(0.0, min(1.0, fraction))) / total, text)

    return share


#: Derselbe Umschalter an beiden Anordnungen, mit demselben Satz — wer ihn an
#: einer Stelle liest, soll ihn an der anderen wiedererkennen. Was er tut,
#: entscheidet der Drucker mit (:func:`_filament_groups`).
BY_MATERIAL_DOC = _(
    "Legt Teile aus verschiedenen Filamenten auf verschiedene Platten. "
    "Eine Düse spült bei jedem Wechsel; hat der Drucker genug Düsen für alle "
    "Filamente, bleibt alles zusammen."
)


def _filament_groups(ctx: OpContext, objects: Sequence[SceneObject]) -> dict[str, int] | None:
    """Welches Teil zu welchem Filament gehört — oder ``None``, wenn der Drucker
    die Trennung nicht braucht (Entscheidung Robert, 19.09.2026: „kein
    Reinigen, wenn der Drucker nicht mehr Düsen hat").

    Eine Düse mit Wechselstation spült bei jedem Filamentwechsel, und zwei
    Filamente auf einer Platte kosten das je gemeinsamer Schicht. Zwei Düsen
    drucken zwei Filamente ohne Spülgang: Erst wenn mehr Filamente auf dem
    Bett liegen, als der Drucker Düsen hat (:attr:`PrinterProfile.nozzles`),
    lohnt sich eine Platte je Filament. Ein Teil, das selbst mehrere
    Filamente trägt, bleibt ohnehin zusammen (``plates_by_material``).
    """
    from app.core.export.writer import plates_by_material

    groups = plates_by_material(list(objects))
    if len(set(groups.values())) <= max(1, ctx.profile.printer.nozzles):
        return None
    return groups


def _arranged_in_filament_groups(
    ctx: OpContext,
    objects: Sequence[SceneObject],
    groups: Mapping[str, int],
    spacing: float,
    plates: int,
    occupied: Sequence[tuple[MeshData, int]] = (),
) -> Arrangement:
    """Erst nach Filament gruppieren, dann jede Gruppe für sich anordnen.

    Den Vorschlag rechnet :func:`app.core.export.writer.plates_by_material`
    schon lange — er war nur von nirgends aus erreichbar. Hier ist er eine
    Handlung, und zwar dieselbe für *Auf dem Bett anordnen* und *Druckoptimal
    ausrichten*: dieselbe Handlung mit einer anderen Vorgabe, wer neben wem
    liegt.

    Jede Gruppe bekommt ihre eigenen Platten, hintereinander weg. Die Grenze
    aus ``plates`` gilt dabei für die ganze Szene, nicht je Gruppe — sonst
    hätte ein Projekt mit drei Filamenten unversehens dreimal so viele
    Platten, wie jemand eingestellt hat. ``occupied`` sind Körper, die liegen
    bleiben und ihren Platz belegen (ein gespeicherter Auftrag von gestern
    trägt seine damalige Teilmenge); sie stehen jeder Gruppe im Weg.
    """
    order: list[int] = []
    for entry in objects:
        group = groups[entry.id]
        if group not in order:
            order.append(group)

    meshes: dict[str, MeshData] = {}
    assigned: dict[str, int] = {}
    findings: list[Finding] = []
    next_plate = 0

    for group in order:
        members = [entry for entry in objects if groups[entry.id] == group]
        # Sind die Platten aufgebraucht, teilt sich diese Gruppe die letzte mit
        # der vorigen — dieselbe Regel, die `arrange_on_bed` innerhalb einer
        # Gruppe befolgt: die letzte Platte nimmt den Rest, und der Bericht
        # sagt, dass sie übervoll ist. Ein Teil, das still aus der Anordnung
        # fiele, wäre ein Teil, das nie gedruckt wird.
        start = min(next_plate, plates - 1)
        arranged = arrange_on_bed(
            [as_mesh_data(entry.mesh) for entry in members],
            ctx.profile,
            spacing,
            plates - start,
            # Mit Kennungen: Der Bauraum-Befund soll den Körper beim Namen
            # nennen, nicht beim laufenden Index (Roberts Foto, 30.08.2026).
            object_ids=[entry.id for entry in members],
            # Die belegten Plätze in der Zählung dieser Gruppe: Was auf der
            # Szenenplatte ``start + k`` steht, steht für sie auf Platte ``k``.
            occupied=[(mesh, plate - start) for mesh, plate in occupied if plate >= start],
        )
        findings.extend(arranged.findings)
        for entry, mesh, plate in zip(members, arranged.meshes, arranged.plates, strict=True):
            meshes[entry.id] = mesh
            assigned[entry.id] = start + plate
        next_plate = start + arranged.plate_count

    return Arrangement(
        meshes=[meshes[entry.id] for entry in objects],
        plates=[assigned[entry.id] for entry in objects],
        findings=findings,
    )


@op_params
class OrientParams(BaseParams):
    thorough: bool = param(
        title=_("Gründlich suchen"),
        default=True,
        doc=_(
            "Prüft geometrisch begründete Lagen und vergleicht die besten mit der Schichtanalyse. "
            "Aus heißt: schnelle Heuristik über die Flächen."
        ),
    )
    candidates: int = param(
        title=_("Kandidaten"),
        default=DEFAULT_CANDIDATES,
        minimum=8,
        maximum=2000,
        placement="advanced",
        doc=_(
            "Wie viele Hüllflächen als Grundfläche geprüft werden. "
            "Die besten Lagen werden anschließend mit der Schichtanalyse verglichen."
        ),
        depends_on=("thorough", (True,)),
    )
    arrange: bool = param(
        title=_("Danach auf dem Bett anordnen"),
        default=True,
        doc=_(
            "Ein hingelegter Körper braucht mehr Fläche als ein stehender. "
            "Aus heißt: jeder bleibt, wo er stand — auch wenn er dann im Nachbarn steckt."
        ),
    )
    spacing: float = param(
        title=_("Abstand"),
        default=5.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        placement="advanced",
        doc=_("Luft zwischen den Teilen beim Anordnen."),
        depends_on=("arrange", (True,)),
    )
    plates: int = param(
        title=_("Druckplatten"),
        default=MAX_PLATES,
        minimum=1,
        maximum=MAX_PLATES,
        placement="advanced",
        doc=_("Passt nicht alles auf eine Platte, wandert der Rest auf die nächste."),
        depends_on=("arrange", (True,)),
    )
    by_material: bool = param(
        title=_("Nach Filament trennen"),
        default=True,
        doc=BY_MATERIAL_DOC,
        depends_on=("arrange", (True,)),
    )


@register_op(
    name="orient_for_print",
    title=_("Druckoptimal ausrichten"),
    category="transform",
    params=OrientParams,
    # **Die ganze Szene** (Entscheidung Robert, 10.09.2026: „druckoptimal
    # ausrichten alle körper"). Zwei Schritte hierher: ``consumes=1`` nahm den
    # ersten Körper und ließ die übrigen liegen — wer vier Teile wählte und
    # deren erstes schon richtig lag, sah überhaupt keine Wirkung (07.09.2026);
    # ``VARIABLE`` nahm die gewählten und musste den übrigen ausweichen, was
    # jede Zentrierung verhindert (§29): Der gedrehte Körper landete in der
    # hinteren linken Ecke, weil die freie Mitte einem Nachbarn gehörte.
    #
    # Es ist dieselbe Bauart wie bei *Auf dem Bett anordnen* daneben, und aus
    # demselben Grund: Wer ein Druckbett optimiert, meint das Bett und nicht
    # eine Markierung darauf.
    consumes=0,
    whole_scene=True,
    produces=VARIABLE,
    # **Und sie liest trotzdem an ihren Eingängen vorbei.** Die Oberfläche gibt
    # ihr heute alles, ein **gespeicherter** Auftrag von gestern trägt aber
    # seine damalige Teilmenge — der liest die übrigen aus ``ctx.scene``, und
    # ohne diese Zeile bliebe sein Ergebnis im Cache gültig, nachdem jemand
    # einen von ihnen verschoben hat.
    reads_other_bodies=True,
    deterministic=True,
    doc=_(
        "Sucht für jeden Körper der Szene die Lage mit dem geringsten "
        "Stützbedarf und ordnet danach das Bett neu. Jeder bekommt seine "
        "eigene Lage — die beste folgt aus der Geometrie des einzelnen Teils."
    ),
)
def orient_for_print_op(ctx: OpContext) -> OpResult:
    """Gründlich heißt, die Schichtanalyse urteilt; sonst tut es die
    P2-Heuristik.
    """
    params = cast(OrientParams, ctx.params)

    outputs = []
    findings: list[Finding] = []
    last_matrix = None
    # **Jeder Körper trägt seine eigene Bewegung.** Gemeldet wird unten nur
    # eine, und nur wenn es eine gibt; mitnehmen muss die Operation die
    # Merkmale aber für jeden einzelnen.
    matrices: list[Any] = []
    for number, entry in enumerate(ctx.inputs):
        mesh = as_mesh_data(entry.mesh)
        try:
            if params.thorough:
                found = search(
                    mesh,
                    count=params.candidates,
                    seed=ctx.seed,
                    profile=ctx.profile,
                    overhang_angle=analysis_limits(ctx.profile, entry)[1],
                    # Der Fortschritt gehört dem ganzen Auftrag, nicht dem
                    # einzelnen Körper: Bei vier Teilen liefe der Balken sonst
                    # viermal von vorn.
                    progress=_share_of(ctx.progress, number, len(ctx.inputs)),
                    cancelled=ctx.cancelled,
                )
                # **Gedreht wird der echte Körper, nicht das Urteil.**
                # ``search`` arbeitet auf Dreiecken; ein exakter Körper käme
                # als Netz zurück, und danach ist kein Verrunden mehr möglich.
                # ``moved_object`` führt mit derselben Matrix auch die Merkmale nach.
                matrix = found.transform
                findings.extend(found.findings)
            else:
                result = orient_for_print(
                    mesh, printer=ctx.profile.printer, cancelled=ctx.cancelled
                )
                matrix = result.transform
                findings.extend(result.findings)
        except NoFittingOrientationError as refusal:
            raise _the_way_out_of(refusal, mesh, entry, ctx) from None
        outputs.append(moved_object(entry, matrix, cancelled=ctx.cancelled))
        matrices.append(matrix)
        last_matrix = matrix

    if params.arrange:
        outputs, shifts = _laid_out_after_turning(ctx, params, outputs, findings)
        # **Und dann ist die gemeldete Bewegung die Drehung *und* der Weg zum
        # neuen Platz.** Sie ist die Auskunft für Vorschau und Gizmo, und die
        # muss den Eingang genau auf den Ausgang legen: erst gedreht, dann
        # verschoben. Der Versatz allein zeigte den Körper ungedreht am neuen
        # Ort, die Drehung allein gedreht am alten — beides war er nie.
        matrices = [composed(shift, matrix) for shift, matrix in zip(shifts, matrices, strict=True)]
        if matrices:
            last_matrix = matrices[-1]

    # **Die Bewegung wird nur bei einem einzigen Körper gemeldet.** Sie ist die
    # Auskunft für Vorschau und Gizmo, und die kennt genau eine Matrix; bei
    # mehreren hat jeder Körper seine eigene, und eine davon zu nennen wäre
    # eine Angabe über die anderen, die nicht stimmt.
    return OpResult(
        outputs=outputs,
        findings=findings,
        transform=as_transform(last_matrix) if len(outputs) == 1 else None,
    )


def _the_way_out_of(
    refusal: NoFittingOrientationError, mesh: MeshData, entry: SceneObject, ctx: OpContext
) -> NoFittingOrientationError:
    """Die Absage „passt in keinen Bauraum" mit dem Ausweg, den lose Teile haben.

    **Der Anlass** (Robert, 11.09.2026: „das druckoptimal ausrichten klappt
    nicht, es werden nicht mehr platten angelegt"): Ein Schriftzug *Solidon3D*
    in 200 mm ist einen Meter breit und passt in keiner Lage auf das Bett —
    seine elf losen Teile passen alle, und angeordnet lägen sie auf zwei
    Platten. Die Operation darf sie nicht selbst zerlegen: Ihre Ausgänge
    stehen fest, bevor gerechnet wird, und eine andere Zahl hält die Kette an
    (§15.2). Also sagt sie, was ginge, und das Fenster tut es auf einen Klick
    — *In Einzelteile zerlegen* vor diesen Schritt, danach derselbe Schritt
    noch einmal (``History.split_and_retry``), wie bei *Reparieren und erneut
    versuchen* (Regel 17).

    **Vorgeschlagen wird nur, was hält.** Gezählt wird, wie ``split_bodies``
    zählt — Splitter fallen weg, mehr als seine Stückzahl erlaubt gibt es
    nicht —, und jedes Teil muss für sich in eine Lage passen; sonst hielte
    die Kette nach dem Klick am selben Schritt noch einmal an. Ein Körper aus
    einem Stück behält die Absage, wie sie war: Dort gibt es nichts zu
    zerlegen, und der Vorschlag heißt Teilen.
    """
    limit = next(
        int(spec.maximum or 0) for spec in SplitBodiesParams.spec() if spec.name == "count"
    )
    kept, _dropped = _loose_parts(mesh, keep_tiny=False)
    # Ein einziges Teil ist der Körper selbst, und der hat gerade nicht
    # gepasst — die Untergrenze erspart nur, ihn ein zweites Mal zu prüfen.
    each_fits = 2 <= len(kept) <= limit and all(
        ranked_orientations(
            mesh.replacing(part), limit=1, cancelled=ctx.cancelled, printer=ctx.profile.printer
        )
        for part, _volume, _slots in kept
    )
    if not each_fits:
        refusal.object_id = entry.id
        return refusal
    return NoFittingOrientationError(
        detail=_(
            "Der Körper passt als Ganzes in keiner Lage auf das Bett; "
            "seine losen Teile passen einzeln."
        ),
        suggestions=(SPLIT_AND_RETRY, SPLIT_MODEL, CHOOSE_PRINTER, CANCEL),
        values={"name": entry.name, "count": len(kept)},
        object_id=entry.id,
    )


def _laid_out_after_turning(
    ctx: OpContext,
    params: OrientParams,
    turned: list[SceneObject],
    findings: list[Finding],
) -> tuple[list[SceneObject], list[Any]]:
    """Legt hin, was das Drehen umgeworfen hat — und lässt den Rest liegen.

    **Der Anlass** (Robert, 09.09.2026: „bei druckoptimal ausrichten, werden
    verschiedene modelle überlagert ohne abstand"). Ein Körper, der sich
    hinlegt, braucht mehr Fläche als vorher; gemessen an zwei Türmen
    20 x 20 x 90 mit 15 mm Luft standen sie hinterher 55 mm ineinander. Die
    Drehung allein ist damit kein brauchbares Ergebnis.

    Angeordnet wird über dieselbe Funktion, die *Auf dem Bett anordnen*
    benutzt, mit denselben Werten für Abstand und Plattenzahl — was nicht mehr
    passt, wandert auf die nächste Platte, und wo keine übrig ist, neben das
    Bett samt Befund (Roberts Ansage: „neues druckbett oder neben dem bett
    anordnen je nachdem wie viele druckplatten ausgewählt waren").

    **Fremde Körper bleiben liegen und belegen ihren Platz.** Über die
    Oberfläche gibt es keine: Die Operation bekommt die ganze Szene
    (``whole_scene``), und dann wird der Verband am Ende zentriert. Ein
    **gespeicherter** Auftrag trägt dagegen die Teilmenge von damals; die
    übrigen liest sie aus ``ctx.scene``, und lesen darf sie (Regel 3).
    """
    chosen = {entry.id for entry in turned}
    standing = [
        (as_mesh_data(other.mesh), other.plate)
        for key, other in ctx.scene.objects.items()
        if key not in chosen
    ]
    # **Und je Filament eine Platte, wo der Drucker sonst spülen müsste**
    # (Robert, 19.09.2026: „Druckoptimal ausrichten mehrere Filamente über
    # Platten aufteilen, kein Reinigen wenn Drucker nicht mehr Düsen"). Es ist
    # dieselbe Regel wie bei *Auf dem Bett anordnen*, und sie fragt den
    # Drucker: Mit genug Düsen bleibt alles zusammen.
    groups = _filament_groups(ctx, turned) if params.by_material else None
    if groups is not None:
        arrangement = _arranged_in_filament_groups(
            ctx, turned, groups, params.spacing, params.plates, occupied=standing
        )
    else:
        arrangement = arrange_on_bed(
            [as_mesh_data(entry.mesh) for entry in turned],
            ctx.profile,
            params.spacing,
            params.plates,
            object_ids=[entry.id for entry in turned],
            occupied=standing,
        )
    findings.extend(arrangement.findings)
    for plate in range(arrangement.plate_count):
        together = [
            (mesh, entry)
            for mesh, entry, at in zip(arrangement.meshes, turned, arrangement.plates, strict=True)
            if at == plate
        ]
        findings.extend(
            named_for(
                check_collisions([mesh for mesh, _entry in together]),
                [entry for _mesh, entry in together],
            )
        )

    laid: list[SceneObject] = []
    shifts: list[Any] = []
    for entry, mesh, plate in zip(turned, arrangement.meshes, arrangement.plates, strict=True):
        # Der Versatz statt des Netzes — dieselbe Begründung wie bei
        # ``arrange_bed``: Ein exakter Körper käme sonst als Netz zurück.
        step = translation(
            (
                mesh.bounds.minimum[0] - entry.mesh.bounds.minimum[0],
                mesh.bounds.minimum[1] - entry.mesh.bounds.minimum[1],
                mesh.bounds.minimum[2] - entry.mesh.bounds.minimum[2],
            )
        )
        laid.append(
            dataclasses.replace(moved_object(entry, step, cancelled=ctx.cancelled), plate=plate)
        )
        shifts.append(step)
    return laid, shifts


@op_params
class ArrangeParams(BaseParams):
    spacing: float = param(
        title=_("Abstand"),
        default=5.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_(
            "Luft zwischen den Teilen. Genug, dass ein Elefantenfuß zwei Teile "
            "nicht am Rand zusammenwachsen lässt."
        ),
    )
    plates: int = param(
        title=_("Druckplatten"),
        # **Die Vorgabe war 1, und damit hielt der Satz daneben nicht.** „Der
        # Rest wandert auf die nächste" — bei einer erlaubten Platte gibt es
        # keine nächste, und der Rest landet **neben** dem Bett, wo er nicht
        # druckbar ist. Gemessen am 03.09.2026 mit neun Klötzen von 120 mm:
        # erlaubt 1 ergab eine Platte und acht daneben, erlaubt 12 ergab neun
        # Platten und keinen daneben. Bei **einem** Teil bleibt es in beiden
        # Fällen bei einer Platte — die höhere Vorgabe legt also keine Platten
        # auf Vorrat an, sie hört nur auf, den Rest fallen zu lassen.
        #
        # Wer genau eine Platte will, stellt sie ein; wer nichts einstellt,
        # bekommt, was der Satz verspricht. Entscheidung Robert, 03.09.2026:
        # „nicht den satz sondern die logik anpassen."
        default=MAX_PLATES,
        minimum=1,
        maximum=MAX_PLATES,
        doc=_("Passt nicht alles auf eine Platte, wandert der Rest auf die nächste."),
    )
    by_material: bool = param(
        title=_("Nach Filament trennen"),
        # **An, nicht aus** (Entscheidung Robert, 19.09.2026): Die Vorgabe soll
        # das druckbare Ergebnis sein, und ob die Trennung überhaupt nötig
        # ist, entscheidet der Drucker (``_filament_groups``) — mit einem
        # Filament oder genug Düsen ändert der Schalter nichts.
        default=True,
        doc=BY_MATERIAL_DOC,
    )


@register_op(
    name="arrange_bed",
    title=_("Auf dem Bett anordnen"),
    category="scene",
    params=ArrangeParams,
    consumes=0,
    produces=VARIABLE,
    whole_scene=True,
    doc=_("Legt alle Objekte nebeneinander auf das Druckbett."),
    shortcut="Ctrl+Shift+O",
)
def arrange_bed(ctx: OpContext) -> OpResult:
    params = cast(ArrangeParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    groups = _filament_groups(ctx, ctx.inputs) if params.by_material else None
    if groups is not None:
        result = _arranged_in_filament_groups(
            ctx, ctx.inputs, groups, params.spacing, params.plates
        )
    else:
        result = arrange_on_bed(
            meshes,
            ctx.profile,
            params.spacing,
            params.plates,
            object_ids=[entry.id for entry in ctx.inputs],
        )
    findings = list(result.findings)

    # Kollisionen werden je Platte geprüft: zwei Teile an derselben Stelle auf
    # verschiedenen Platten treffen sich nie.
    #
    # **Und mit Namen.** ``check_collisions`` kennt nur die Reihenfolge seiner
    # Liste und schreibt sie in den Befund; ohne ``named_for`` stand im Bericht
    # „Zwei Objekte überschneiden sich — 0 · 1". Hier war es doppelt irre, denn
    # die Liste ist je Platte gefiltert: die 1 der zweiten Platte ist nicht das
    # zweite Objekt der Szene. Die Einträge werden deshalb mitgefiltert und
    # zusammen weitergegeben. Die Zwillings-Op darunter macht es seit je so.
    for plate in range(result.plate_count):
        on_plate = [
            (mesh, entry)
            for mesh, entry, at in zip(result.meshes, ctx.inputs, result.plates, strict=True)
            if at == plate
        ]
        findings.extend(
            named_for(
                check_collisions([mesh for mesh, _entry in on_plate]),
                [entry for _mesh, entry in on_plate],
            )
        )

    # **Wenn nichts zu verschieben war, sagt die Operation es.** Sonst ist ein
    # zweiter Klick von einer kaputten Anwendung nicht zu unterscheiden: Der
    # Dialog geht auf, OK rechnet dasselbe Ergebnis, im Verlauf steht ein
    # Schritt, und das Bild bleibt, wie es war. Robert am 24.08.2026, nachdem
    # er es zum zweiten Mal geklickt hatte: „das an druckbett ausrichten
    # funktioniert nicht mehr" — es lag schon alles, wo es liegen sollte.
    #
    # Ein Befund und kein Fehler: Die Operation ist gelungen, das Ergebnis ist
    # nur dasselbe wie vorher. Regel 17 gilt für Ausnahmen; hier gibt es keine,
    # und ein Dialog wäre eine Bestätigung ohne Entscheidung (Regel 19).
    if not _has_moved(ctx.inputs, result):
        findings.append(
            Finding(
                code="arrange.already_arranged",
                severity="info",
                message=_("Die Teile liegen schon so — es war nichts zu verschieben."),
            )
        )

    return OpResult(
        outputs=[
            # **Der Versatz statt des Netzes.** ``arrange_on_bed`` rechnet auf
            # Dreiecken und gibt verschobene Netze zurück; ein exakter Körper
            # käme so als Netz heraus, und danach ist kein Verrunden mehr
            # möglich. Das Anordnen verschiebt nur — der Versatz steht in den
            # Hüllquadern; ``moved_object`` führt Körper und Merkmale gemeinsam nach.
            dataclasses.replace(
                moved_object(
                    entry,
                    translation(
                        (
                            mesh.bounds.minimum[0] - entry.mesh.bounds.minimum[0],
                            mesh.bounds.minimum[1] - entry.mesh.bounds.minimum[1],
                            mesh.bounds.minimum[2] - entry.mesh.bounds.minimum[2],
                        )
                    ),
                    cancelled=ctx.cancelled,
                ),
                plate=plate,
            )
            for entry, mesh, plate in zip(ctx.inputs, result.meshes, result.plates, strict=True)
        ],
        findings=findings,
    )


def _has_moved(entries: Sequence[SceneObject], result: Arrangement) -> bool:
    """Ob die Anordnung überhaupt einen Körper bewegt hat.

    Gegen ``EPS_DISPLAY`` und nicht gegen ``EPS_GEOM`` (§11.2, Regel 6): Die
    Frage ist nicht, ob zwei Netze rechnerisch gleich liegen, sondern ob jemand
    den Unterschied **sieht**. Ein Hundertstelmillimeter ist im Fenster
    dasselbe Bild, und eine Meldung „verschoben", die nichts zeigt, wäre
    genauso irre wie die Stille, gegen die sie steht.

    Die Platte zählt mit: Zwei Platten liegen in der Szene an derselben Stelle,
    weil jede einzeln gedruckt wird (§25). Ein Körper, der auf die nächste
    wandert, behält damit seine Koordinaten und ist trotzdem woanders.
    """
    for entry, mesh, plate in zip(entries, result.meshes, result.plates, strict=True):
        if plate != entry.plate:
            return True
        before = as_mesh_data(entry.mesh).bounds.minimum
        after = mesh.bounds.minimum
        if any(abs(a - b) > EPS_DISPLAY for a, b in zip(before, after, strict=True)):
            return True
    return False


@op_params
class CollisionParams(BaseParams):
    clearance: float = param(
        title=_("Mindestabstand"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=50.0,
        doc=_(
            "Ab wann zwei Teile als zu nah gelten. Null meldet nur echte "
            "Überschneidungen; ein Wert darüber meldet auch knappe Stellen."
        ),
    )


@register_op(
    name="check_collisions",
    # „Überschneidungen" statt „Kollisionen": Der Kunde denkt bei Kollision an
    # einen Zusammenstoß, gemeint ist, dass zwei Teile ineinanderstecken.
    title=_("Überschneidungen prüfen"),
    category="scene",
    params=CollisionParams,
    consumes=0,
    produces=VARIABLE,
    whole_scene=True,
    doc=_("Meldet Überschneidungen und was über den Bauraum hinaussteht."),
)
def check_collisions_op(ctx: OpContext) -> OpResult:
    params = cast(CollisionParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    findings = check_collisions(meshes, params.clearance)
    findings.extend(check_build_volume(meshes, ctx.profile))
    # Ändert nichts: die Objekte gehen unberührt hindurch, die Befunde sind das
    # Ergebnis.
    return OpResult(outputs=list(ctx.inputs), findings=named_for(findings, ctx.inputs))


@op_params
class JoinPathParams(BaseParams):
    axis: str = param(
        title=_("Richtung"),
        default="x",
        choices=("x", "y", "z"),
        doc=_("Die Achse, entlang der das erste Teil in das zweite geschoben wird."),
    )
    reverse: bool = param(
        title=_("Entgegengesetzt"),
        default=False,
        doc=_("Schiebt entgegen der Achsrichtung, also von der anderen Seite her."),
    )
    distance: float = param(
        title=_("Fügeweg"),
        default=25.0,
        unit="mm",
        minimum=0.1,
        maximum=500.0,
        doc=_(
            "Wie weit vor der Endlage geprüft wird. So lang wie die Stelle, an der "
            "die Teile ineinandergreifen, plus etwas Anlauf."
        ),
    )
    steps: int = param(
        title=_("Schritte"),
        default=24,
        minimum=2,
        maximum=200,
        placement="advanced",
        doc=_(
            "In wie viele Stellen der Weg geteilt wird. Mehr findet engere Stellen, "
            "kostet aber je Schritt einen Schnitt durch beide Körper."
        ),
    )


@register_op(
    name="check_join_path",
    title=_("Fügeweg prüfen"),
    category="scene",
    params=JoinPathParams,
    consumes=2,
    produces=2,
    reversible=True,
    doc=_(
        "Prüft, ob zwei Teile in ihre Lage gelangen — nicht nur, ob sie dort "
        "zusammenpassen. Das erste gewählte Teil wird in das zweite geschoben."
    ),
    caveat=_(
        "Beide Teile stehen dabei in ihrer Endlage; geprüft wird der Weg davor. "
        "Ein offener Körper hat kein Innen und lässt sich so nicht messen."
    ),
)
def check_join_path_op(ctx: OpContext) -> OpResult:
    """Der Weg in die Endlage, nicht die Endlage selbst.

    **Warum das eine eigene Operation ist und keine Erweiterung von
    „Überschneidungen prüfen":** Jene fragt nach einem Zustand und braucht
    dafür nichts als die Szene. Diese fragt nach einer Bewegung und braucht
    eine Richtung, eine Strecke und die Angabe, welches der beiden Teile sich
    bewegt. Das sind vier Angaben mehr, und sie in die andere zu legen hieße,
    sie jedem aufzudrängen, der nur wissen will, ob etwas ineinandersteckt.

    Der Anlass steht in :func:`check_join_path`: eine Rinne, deren Segmente
    seitlich passten und in der Höhe stirnseitig aufeinanderstießen.
    """
    params = cast(JoinPathParams, ctx.params)
    moving = as_mesh_data(ctx.inputs[0].mesh)
    fixed = as_mesh_data(ctx.inputs[1].mesh)
    vector = list(AXIS_NORMALS[cast(Axis, params.axis)])
    if params.reverse:
        vector = [-value for value in vector]
    findings = check_join_path(
        moving,
        fixed,
        (vector[0], vector[1], vector[2]),
        params.distance,
        steps=params.steps,
    )
    # Wie „Überschneidungen prüfen": Die Körper gehen unberührt hindurch, die
    # Befunde sind das Ergebnis.
    return OpResult(outputs=list(ctx.inputs), findings=named_for(findings, ctx.inputs))


def _is_a_fillet(source: SceneObject, name: str) -> bool:
    """Ob der Merkmalsverweis auf eine erkannte Rundung zeigt."""
    feature = source.features.get(name)
    return feature is not None and feature.kind == "fillet"


def _drop_the_fillet(ctx: OpContext, source: SceneObject, name: str) -> OpResult:
    """Eine erkannte Rundung wegnehmen — die scharfe Kante kommt zurück.

    **Eine Weiche und kein Sonderfall im Motor.** Der Weg darunter füllt
    Hohlräume und trägt Zapfen ab; eine Rundung ist keins von beidem, sondern
    ein Zwickel an einer Kante. Was sie braucht, steht neben dem Verrunden
    selbst — dieselbe Rechnung, andere Richtung.

    Und wieder zwei Kerne: Der exakte nimmt die Rundungsfläche als Ding
    (``BRepAlgoAPI_Defeaturing``), das Netz legt den Zwickel dazu.
    """
    if source.features[name].params.get("tangent", False):
        from app.core.perceive.actions import WALL_BLENDS_INTO_ITS_NEIGHBOURS

        raise GeometryError(WALL_BLENDS_INTO_ITS_NEIGHBOURS, suggestions=(CORRECT_INPUT, CANCEL))
    if source.features[name].params.get("radial", False):
        raise GeometryError(
            _(
                "Diese runde Wand ist keine abgerundete Kante. Ändern Sie "
                "ihren Radius über „Merkmal ändern“."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if source.kind == "brep":
        return _exact_fillet(ctx, source, name, None)
    from app.core.geom.edges import unround

    outcome = unround(
        as_mesh_data(source.mesh),
        source.features[name],
        quality=ctx.quality,
        features=source.features,
        cancelled=ctx.cancelled,
    )
    return _after_the_fillet(source, name, outcome)


def _reshape_the_fillet(
    ctx: OpContext,
    source: SceneObject,
    name: str,
    radius: float,
) -> OpResult:
    """Den Radius einer erkannten Rundung ändern."""
    if is_close(radius, float(source.features[name].params["radius"])):
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="resize_feature.unchanged",
                    severity="info",
                    message=_("Das Merkmal hat dieses Maß schon."),
                    feature_ids=(name,),
                )
            ],
        )
    if source.features[name].params.get("tangent", False):
        from app.core.perceive.actions import WALL_BLENDS_INTO_ITS_NEIGHBOURS

        raise GeometryError(WALL_BLENDS_INTO_ITS_NEIGHBOURS, suggestions=(CORRECT_INPUT, CANCEL))
    if source.kind == "brep":
        return _exact_fillet(ctx, source, name, radius)
    from app.core.geom.edges import reround

    outcome = reround(
        as_mesh_data(source.mesh),
        source.features[name],
        radius,
        quality=ctx.quality,
        features=source.features,
        cancelled=ctx.cancelled,
    )
    return _after_the_fillet(source, name, outcome, radius=radius, ctx=ctx)


def _exact_fillet(ctx: OpContext, source: SceneObject, name: str, radius: float | None) -> OpResult:
    """Wegnehmen oder Ändern am exakten Körper — träge geholt (§36).

    **Warum nicht einfach der Netz-Weg auch hier**: Er bekäme die Tessellation
    und gäbe ein Netz zurück, das sich weiter ``brep`` nennt. Der Kunde
    verlöre die bearbeitbaren Flächen still, mitten in einer Handlung, die
    davon gar nicht spricht.
    """
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.brep.ops import brep_input

    exact, body = brep_input(ctx)
    feature = source.features[name]
    measured = [float(value) for value in feature.params["centre"]]
    spot: Vec3 = (measured[0], measured[1], measured[2])
    was = float(feature.params.get("radius", 0.0))
    ctx.cancelled.raise_if_cancelled()
    # Die gewählte Rundungsfläche geht am aktuellen Eigentümer in beide Wege:
    # Entfernen und Radiuswechsel arbeiten an genau dieser Fläche, nicht an
    # der nächsten zur alten Mitte (P1.4c).
    selected_faces = body.complete_faces_of_triangles(feature.face_indices)
    ctx.cancelled.raise_if_cancelled()
    if radius is None:
        solid = edit.unround(
            body, spot, was, selected_faces=selected_faces, cancelled=ctx.cancelled
        )
    else:
        solid = edit.reround(
            body, spot, was, radius, selected_faces=selected_faces, cancelled=ctx.cancelled
        )
    return OpResult(
        outputs=[
            dataclasses.replace(
                exact, mesh=solid, kind="brep", features=features_of(solid, cancelled=ctx.cancelled)
            )
        ]
    )


def _after_the_fillet(
    source: SceneObject,
    name: str,
    outcome: Any,
    *,
    radius: float | None = None,
    ctx: OpContext | None = None,
) -> OpResult:
    """Das Ergebnis, und die Kennung geht mit — beim Entfernen fort, beim Ändern weiter.

    Dieselbe Zusage wie bei jedem anderen Merkmal: Ein Verweis, der stehen
    bleibt, obwohl die Geometrie fort ist, wird später als Passungsfehler
    gemeldet — und dann sucht der Kunde an einem Teil, das in Ordnung ist.

    **Eine geänderte Rundung ist dieselbe Rundung** (22.09.2026). Hier stand
    für beide Wege dasselbe Streichen, und die Auswertung vergab der neuen
    Rundung einen neuen Namen: ``fillet_1`` hieß danach ``fillet_5``, und ein
    zweites *Merkmal ändern* an ``fillet_1`` hielt an („Dieses Merkmal gibt es
    an diesem Objekt nicht"). Der exakte Kern führte den Namen weiter. Jetzt
    sucht der Netzweg die Rundung im neuen Maß an ihrer Stelle — dieselbe
    Frage wie ``_recognised_resized_feature`` an einer Bohrung — und gibt ihr
    den alten Namen.
    """
    kept = _without_old_triangles(source.features, without=(name,))
    findings = [dataclasses.replace(entry, object_id=source.id) for entry in outcome.findings]
    if radius is not None:
        found = _refound_fillet(
            outcome.mesh,
            source.features[name],
            radius,
            check_cancelled=ctx.cancelled.raise_if_cancelled if ctx is not None else None,
        )
        if found is not None:
            kept[name] = found
        else:
            findings.append(
                dataclasses.replace(
                    _cavity_lost_finding("resize_feature", source.features[name]),
                    object_id=source.id,
                )
            )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features=kept)],
        solver=outcome.solver,
        findings=findings,
    )


def _refound_fillet(
    mesh: MeshData,
    feature: Feature,
    radius: float,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> Feature | None:
    """Die Rundung im neuen Maß an der Stelle der alten — oder ``None``.

    Die Mitte einer Rundung ist die Achse ihres Bogens, und die wandert mit
    dem Radius entlang der Winkelhalbierenden, um ``ΔR / sin(θ/2)`` — an einem
    Quader von R 2 auf R 3 um 1,41 mm. Gesucht wird deshalb im Umkreis der
    Zuordnungstoleranz plus des Vierfachen der Radiusänderung (Winkel ab 29°)
    und genommen die Rundung, deren Achse zur alten parallel liegt, deren
    Radius auf fünf Prozent trifft — so genau misst der Fit an einem Sehnenzug
    (2,9772 an einer Rundung von 3,0) — und die der alten Mitte am nächsten ist.
    """
    from app.core.perceive.features import detect
    from app.core.units import match_tolerance

    old_axis = np.asarray(_feature_direction(feature), dtype=np.float64)
    old_centre = np.asarray(_bore_vector(feature, "centre"), dtype=np.float64)
    limit = match_tolerance(mesh.bounds.diagonal) + 4.0 * abs(
        radius - float(feature.params.get("radius", radius))
    )
    best: tuple[float, Feature] | None = None
    for candidate in detect(mesh, check_cancelled=check_cancelled).values():
        if candidate.kind != "fillet":
            continue
        found_radius = float(candidate.params.get("radius", 0.0))
        if abs(found_radius - radius) > 0.05 * radius:
            continue
        axis = np.asarray(_feature_direction(candidate), dtype=np.float64)
        if abs(float(axis @ old_axis)) < 1.0 - 1e-3:
            continue
        distance = float(np.linalg.norm(np.asarray(candidate.params["centre"]) - old_centre))
        if distance <= limit and (best is None or distance < best[0]):
            best = (distance, candidate)
    if best is None:
        return None
    return dataclasses.replace(
        best[1], id=feature.id, provenance="generated", created_by=feature.created_by
    )
