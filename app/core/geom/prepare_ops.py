"""Operationen für die Druckvorbereitung (Bauplan §25).

Bohren, Teilen, Anordnen und die Kollisionsprüfung. Die letzte ändert gar
keine Geometrie — sie meldet nur, und das ist eine völlig gute Sache für eine
Operation, wenn die Alternative eine Überraschung am Drucker ist.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any, Final, cast

import numpy as np
from numpy.typing import NDArray

from app.core.deferred import trimesh
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    CHOOSE_PRINTER,
    CORRECT_INPUT,
    RECOUNT_AND_RETRY,
    RESIZE_THE_WIDENING,
    SPLIT_AND_RETRY,
    SPLIT_MODEL,
    GeometryError,
    InternalError,
    ValidationError,
)
from app.core.geom.boolean import (
    BOOLEAN_OVERLAP,
    NOTHING_LEFT_DETAIL,
    NOTHING_LEFT_TITLE,
    BooleanKind,
    BooleanOutcome,
    boolean,
    deepest,
    without_effect,
)
from app.core.geom.hollow import VENT_DIAMETER, below_printable_wall, hollow
from app.core.geom.mesh import MeshData, as_mesh_data, face_components
from app.core.geom.ops import as_transform
from app.core.geom.orient import NoFittingOrientationError, orient_for_print, ranked_orientations
from app.core.geom.pins import (
    PIN_COUNT,
    PIN_MAX,
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
    SLOT_NOT_SHORTER,
    SLOT_TOO_SHORT,
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
    named_for,
    plug,
    resize_bore,
    shell,
    shortest_slot,
    slot_bore,
    slot_travel,
    split_at_plane,
)
from app.core.geom.section import AXIS_NORMALS, SectionPlane
from app.core.geom.transform import Axis, moved_body, place_on_bed, translation
from app.core.knowledge.profiles import analysis_limits, for_object, material
from app.core.registry import VARIABLE, op_params, param, play_param, register_op
from app.core.slice.orientation import DEFAULT_CANDIDATES, search
from app.core.types import (
    BaseParams,
    CancelToken,
    Feature,
    FeatureId,
    Finding,
    Mesh,
    OpContext,
    OpResult,
    PlaneFrame,
    ProgressFn,
    Quality,
    SceneObject,
    SolverInfo,
    Vec3,
    is_a_cavity,
)
from app.core.units import DEGREE_UNIT, EPS_DISPLAY, EPS_GEOM, format_length, is_close, is_zero
from app.i18n import TranslatableText, _

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
    base: TranslatableText | str, *, pinned: bool
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
        title=_("Normale X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Freie Richtung aus der gewählten Fläche. "
            "Null in allen drei Feldern verwendet die Achse."
        ),
    )
    ny: float = param(
        title=_("Normale Y"),
        default=0.0,
        placement="advanced",
        doc=_("Weitere Achse der Richtung — siehe Normale X."),
    )
    nz: float = param(
        title=_("Normale Z"),
        default=0.0,
        placement="advanced",
        doc=_("Weitere Achse der Richtung — siehe Normale X."),
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
#: stehen (siehe :data:`prepare.SLOT_NOT_SHORTER`).
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
MOVABLE_KINDS: Final = ("hole", "pin", "cone", "sphere", "void", "slot")

#: Was sich zu **verdoppeln** lohnt — dasselbe ohne den Einschluss.
#:
#: Geometrisch ginge es: Der Merkmalskörper eines Hohlraums ist gebaut und
#: abgezogen wie jeder andere. Es will nur niemand. Eine zweite Luftblase im
#: Material ist keine Konstruktion, sondern ein zweiter Fehler — und wo ein
#: eingeschlossener Hohlraum Absicht ist (die Aussparung für einen
#: eingegossenen Magneten), legt man die zweite über den Baustein an, mit
#: Maßen, und nicht als Kopie einer gemessenen Fläche (Robert, 10.09.2026:
#: „verdoppeln ist aber bei Hohlräumen sinnlos").
DUPLICABLE_KINDS: Final = ("hole", "pin", "cone", "sphere", "slot")

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
        body = trimesh.creation.cone(
            radius=diameter / 2.0, height=height, sections=FEATURE_SECTIONS
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
            body = trimesh.creation.cylinder(
                radius=diameter / 2.0, height=height, sections=FEATURE_SECTIONS
            )
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
        body = trimesh.creation.cylinder(
            radius=diameter / 2.0, height=height, sections=FEATURE_SECTIONS
        )

    turn = trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
        [0.0, 0.0, 1.0], direction
    )
    body.apply_transform(turn)
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
    """
    rings = (0, 1, 2) if alone else (0, 1)
    return _body_from_faces(mesh, feature.face_indices, allowed_rings=rings)


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
    from app.core.perceive.relations import cavity_chain_state_at

    chain, touches_other = cavity_chain_state_at(feature, features, mesh)
    return chain is None and not touches_other


def _body_from_faces(
    mesh: MeshData, face_indices: Sequence[int], *, allowed_rings: tuple[int, ...]
) -> MeshData | None:
    """Einen Flächenausschnitt an seinen ebenen Randringen schließen.

    Ein einzelnes Merkmal darf höchstens einen Ring haben. Bohrung und
    Senkung zusammen haben genau zwei: die weite Mündung der Senkung und die
    andere Mündung beziehungsweise den Boden der Bohrung. Die Zahl kommt vom
    Aufrufer, damit ein zweiter Ring nie wieder still dieselbe Bedeutung für
    zwei verschiedene Geometrien bekommt.
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
    # liegt innen und braucht keinen Deckel.
    edges = patch.edges_sorted
    single = trimesh.grouping.group_rows(  # type: ignore[no-untyped-call]
        edges, require_count=1
    )
    rim = edges[single]
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
            hub = ring.mean(axis=0)
            # Flach in **irgendeiner** Richtung, nicht nur in Z: Eine Kuppe an
            # einer Seitenwand hat ihren Ring in der YZ-Ebene.
            spread = ring - hub
            if float(np.linalg.svd(spread, compute_uv=False)[-1]) > FLAT_RIM * len(ring) ** 0.5:
                return None
            cap = np.column_stack(
                [
                    ring_edges[:, 0],
                    ring_edges[:, 1],
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
    was davor steht, liegt tiefer im Material und erreicht die Außenwelt nur
    durch den gewählten Abschnitt hindurch. Für den innersten Abschnitt selbst
    ist die Menge leer — dann gilt der bekannte Weg über den Werkzeugkörper.
    """
    position = next((index for index, entry in enumerate(chain) if entry.id == feature.id), 0)
    return tuple(chain[:position])


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


def _polygon_gain(feature: Feature) -> float:
    """Was ein Vieleck an seinen Flanken verliert — als Zugabe auf den Durchmesser.

    ``trimesh.creation.cylinder`` baut ein **eingeschriebenes** Vieleck: Sein
    Umkreis ist der angegebene Durchmesser, sein Innenkreis ist um
    ``cos(π/sections)`` kleiner. Wer aus einem gemessenen Maß ein Werkzeug baut,
    das dieses Maß wiederherstellen soll, rechnet den Unterschied dazu — sonst
    schrumpft die Bohrung bei jedem Zyklus.
    """
    return _polygon_gain_for(float(feature.params.get("diameter", 0.0)))


def _polygon_gain_for(diameter: float) -> float:
    """Dieselbe Zugabe für ein Maß, das an keinem Merkmal steht.

    Beim Versetzen darf der Kunde die Bohrung gleichzeitig ändern; dann gilt
    der Verlust für den **neuen** Durchmesser und nicht für den gemessenen.
    """
    return diameter * (1.0 / math.cos(math.pi / FEATURE_SECTIONS) - 1.0)


def _measured_section(chain: Sequence[Feature], feature: Feature) -> MeshData | None:
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

    ``None`` heißt: Diese Art oder diese Maße geben keinen Körper her.
    """
    centre = cast(Vec3, tuple(float(value) for value in feature.params["centre"]))
    if feature.kind != "cone":
        # **Der Innenkreis muss stimmen, nicht der Umkreis.** Ein Zylinder mit
        # ``FEATURE_SECTIONS`` Seiten ist ein eingeschriebenes Vieleck: Aus dem
        # gemessenen Durchmesser gebaut ist er an seinen Flanken um
        # eins minus cos(pi/48) enger, und die Erkennung misst danach 7,9696 statt
        # 7,9848 — die Bohrung verlöre bei jedem solchen Zyklus 0,017 mm. Die
        # übrigen Aufrufer merken davon nichts, weil ihre Zugabe (§39) zufällig
        # dieselbe Größenordnung hat und den Verlust überdeckt.
        return _feature_solid(feature, centre, oversize=_polygon_gain(feature))

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
    outline = [
        [0.0, -height - FEATURE_OVERLAP],
        [narrow / 2.0, -height - FEATURE_OVERLAP],
        [wide / 2.0, FEATURE_OVERLAP],
        [0.0, FEATURE_OVERLAP],
    ]
    body = trimesh.creation.revolve(outline, sections=FEATURE_SECTIONS)
    body.apply_transform(
        trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
            [0.0, 0.0, 1.0], _outward_axis(chain, feature)
        )
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
    :data:`_NO_OWN_BODY`, und ``test_the_way_out_of_a_countersink_is_the_one_
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
    radius = (float(np.linalg.norm(across, axis=1).max()) + FEATURE_OVERLAP) / math.cos(
        math.pi / FEATURE_SECTIONS
    )
    if reach <= EPS_GEOM or radius <= EPS_GEOM:
        return None

    plug = trimesh.creation.cylinder(
        radius=radius, height=reach + 2.0 * FEATURE_OVERLAP, sections=FEATURE_SECTIONS
    )
    plug.apply_transform(
        trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
            np.array([0.0, 0.0, 1.0]), axis
        )
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

    built = _body_from_faces(mesh, cavity_surface_indices(mesh, sections), allowed_rings=(1, 2))
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
) -> BooleanOutcome | None:
    """**Einen** Abschnitt eines Hohlraums schließen — der Rest bleibt offen.

    **Robert am 10.09.2026:** „wenn ich bei einer Bohrung mit senkung nur die
    senkung entfernen will geht das nicht, also es soll dann nur die senkung
    weg, die Bohrung aber bleiben." Gefragt hat der Kern das längst
    (:func:`_asked_about_sections`); für den Abschnitt allein gab es bis dahin
    keinen Weg, sondern die Absage :data:`_NO_OWN_BODY`.

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

    ``None`` heißt: Dieser Abschnitt gibt keinen eigenen Körper her; dann gilt
    :data:`_NO_OWN_BODY` wie bisher.
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
    reach = float(np.ptp(np.asarray(filled.raw.vertices) @ axis)) + FEATURE_OVERLAP
    inner = _inner_sections(chain, feature)
    for entry, tool in zip(keep, tools, strict=True):
        span = float(np.ptp(np.asarray(tool.raw.vertices) @ axis))
        steps = 0
        if any(entry.id == section.id for section in inner):
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
    length = float(np.linalg.norm(given))
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
    """
    diameter = float(feature.params.get("diameter", 0.0)) - FEATURE_OVERLAP
    if diameter <= EPS_GEOM:
        return False
    reach = float(np.linalg.norm(mesh.bounds.size)) * 2.0
    column = trimesh.creation.cylinder(
        radius=diameter / 2.0, height=reach, sections=FEATURE_SECTIONS
    )
    column.apply_transform(
        trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
            np.array([0.0, 0.0, 1.0]), np.asarray(_feature_direction(feature), dtype=float)
        )
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
    return bool(remaining.volume > EPS_GEOM)


def _throughness_lost(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    op: str,
    *,
    quality: Quality,
    seed: int | None,
    cancelled: CancelToken | None,
) -> list[Finding]:
    """Der Befund dazu — leer, wenn die Bohrung weiter durchgeht.

    Ein Hinweis und keine Ausnahme: Das Ergebnis ist richtig gerechnet, es ist
    nur nicht das, was der Kunde erwartet hat. Der Satz nennt deshalb, woran es
    liegt, und nicht nur, dass es so ist (§2.7).
    """
    if not feature.params.get("through"):
        return []
    if not _no_longer_through(
        mesh, feature, centre, quality=quality, seed=seed, cancelled=cancelled
    ):
        return []
    return [
        Finding(
            code=f"{op}.no_longer_through",
            severity="warning",
            message=_(
                "Diese Bohrung ging durch das Teil und tut es an der neuen Stelle "
                "nicht mehr — ihre Achse durchquert das Material dort nicht ganz."
            ),
            feature_ids=(feature.id,),
            location=centre,
        )
    ]


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
    radius = (float(np.linalg.norm(across, axis=1).max()) + FEATURE_OVERLAP * 2.0) / math.cos(
        math.pi / FEATURE_SECTIONS
    )

    cut = trimesh.creation.cylinder(radius=radius, height=reach, sections=FEATURE_SECTIONS)
    cut.apply_transform(
        trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
            np.array([0.0, 0.0, 1.0]), direction
        )
    )
    middle = float(along.min() + along.max()) / 2.0
    cut.apply_translation(np.asarray(centre, dtype=float) + direction * middle)
    return MeshData.of(cut)


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
    tool = _tool_for(mesh, feature, centre, alone=alone)
    if cavity and feature.kind == "hole":
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
        diameter = 2.0 * radius / math.cos(math.pi / FEATURE_SECTIONS)
        tool = _feature_solid(
            feature, centre, oversize=diameter - _bore_number(feature, "diameter") + FEATURE_OVERLAP
        )
    if cavity:
        # **Erst an den Mündungen, sonst an der Hülle.** Die Merkmalsfläche
        # kennt die Tiefe des Hohlraums genau; die konvexe Hülle kennt nur den
        # Umriss des ganzen Teils und lässt einen Überstand stehen, der in eine
        # Nut oder einen Innenraum ragt (siehe :func:`_between_the_mouths`).
        limit = _between_the_mouths(mesh, feature, centre) or shell(mesh)
        tool = boolean(
            "intersection", [tool, limit], quality=quality, seed=seed, cancelled=cancelled
        ).mesh
        if feature.params.get("open"):
            # Die axiale Begrenzung kennt den seitlichen Außenrand nicht.
            mouth = np.asarray(_bore_vector(feature, "mouth_centre"))
            outward = np.asarray(_bore_vector(feature, "opening_normal"))
            reach = mesh.bounds.diagonal * 2.0
            envelope = trimesh.creation.box(extents=(reach * 2.0, reach * 2.0, reach))
            envelope.apply_translation((0.0, 0.0, -reach / 2.0))
            envelope.apply_transform(
                trimesh.geometry.align_vectors([0.0, 0.0, 1.0], outward)  # type: ignore[no-untyped-call]
            )
            envelope.apply_translation(mouth)
            tool = boolean(
                "intersection",
                [tool, MeshData.of(envelope)],
                quality=quality,
                seed=seed,
                cancelled=cancelled,
            ).mesh
    return boolean(
        "union" if cavity else "difference",
        [mesh, tool],
        quality=quality,
        seed=seed,
        cancelled=cancelled,
    )


def _tool_for(
    mesh: MeshData,
    feature: Feature,
    centre: Vec3,
    scale: float = 1.0,
    axis: Vec3 | None = None,
    *,
    alone: bool = False,
) -> MeshData:
    """Der Werkzeugkörper dieses Merkmals, an ``centre`` gesetzt.

    Bei einer Bohrung wird der tatsächliche Wandmantel an seinen beiden
    Randringen geschlossen. Sonst baut :func:`_feature_solid` parametrische
    Merkmale aus ihren Kennzahlen; übrige Formen kommen aus
    :func:`_feature_body`. Der Körper wird anschließend verschoben, gedreht
    und skaliert.

    Baut sich der Körper nicht sicher, endet der Aufruf mit einem Satz, der
    den **heutigen** Grund nennt und nicht den von gestern — siehe
    :data:`_NO_OWN_BODY`.
    """
    # Beim Versetzen zählt der vorhandene Sehnenzug, nicht der Radius durch
    # die Dreiecksmitten. Sonst schrumpft eine fremd tessellierte Bohrung.
    built = (
        _body_from_faces(mesh, feature.face_indices, allowed_rings=(2,))
        if feature.kind == "hole"
        else None
    )
    if built is None and feature.kind in PARAMETRIC_KINDS:
        return _feature_solid(feature, centre, scale=scale, axis=axis)

    if built is None:
        built = _feature_body(mesh, feature, alone=alone)
    if built is None:
        raise ValidationError(
            field="at_feature",
            detail=_NO_OWN_BODY,
            values={"feature": feature.id, "kind": feature.kind},
            constraint="not_movable",
        )

    measured = [float(value) for value in feature.params["centre"]]
    matrix = np.eye(4)
    if axis is not None:
        from_axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
        matrix = np.asarray(
            trimesh.geometry.align_vectors(  # type: ignore[no-untyped-call]
                from_axis, np.asarray(axis, dtype=np.float64)
            ),
            dtype=np.float64,
        )
    body = built.raw.copy()
    body.apply_translation(-np.asarray(measured, dtype=float))
    if not is_close(scale, 1.0):
        body.apply_scale(scale)  # type: ignore[no-untyped-call]
    body.apply_transform(matrix)
    body.apply_translation(np.asarray(centre, dtype=float))
    return MeshData.of(body)


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

    from app.core.perceive.relations import _boundary_rings, cavity_surface_indices
    from app.core.sketch.planes import frame_of

    # Innere Ringschultern gehören zur Hohlraumhaut. Ohne sie würde ihr
    # größerer Rand eine tiefer liegende Ansatzfläche vortäuschen.
    indices = (
        cavity_surface_indices(mesh, related) if len(related) > 1 else tuple(feature.face_indices)
    )
    combined = dataclasses.replace(feature, face_indices=indices)
    rings = _boundary_rings(mesh.raw, combined)
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
            origin = points.mean(axis=0)
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
        # :data:`_NO_OWN_BODY` benennt ihn falsch: „Dieses Merkmal geht in ein
        # anderes über — eine Senkung über einer Bohrung etwa". Ein Hohlraum
        # ohne Weg nach außen geht in gar nichts über; er hat nur keine
        # Mündung, an der die Platzierung ihn im Bild aufsetzen könnte. Der
        # Weg bleibt trotzdem offen — über die Zahlen im Dialog (gemessen
        # 10.09.2026: Volumen auf 0,000000 mm³ genau erhalten).
        detail = _NO_MOUTH_TO_GRIP if feature.kind == "void" else _NO_OWN_BODY
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
        raise ValidationError(field="at_feature", detail=_NO_OWN_BODY, constraint="not_movable")
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
    chain, touches_other = cavity_chain_state_at(feature, source.features, body)
    if chain is None and touches_other:
        raise ValidationError(field="at_feature", detail=_NO_OWN_BODY, constraint="not_movable")
    centre = cast(Vec3, tuple(float(value) for value in feature.params["centre"]))
    related = chain or (feature,)
    built = (
        _paired_cavity_body(body, *chain) if chain else _tool_for(body, feature, centre, alone=True)
    )
    if built is None:
        raise ValidationError(field="at_feature", detail=_NO_OWN_BODY, constraint="not_movable")
    frame = _feature_mount(body, feature, related, built)
    rotation = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    to_local = np.eye(4)
    to_local[:3, :3] = rotation.T
    to_local[:3, 3] = -rotation.T @ np.asarray(frame.origin)
    local = built.raw.copy()
    local.apply_transform(to_local)
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
    tool.apply_transform(to_world)
    body = as_mesh_data(source.mesh)
    findings: list[Finding] = []
    closed_solver = None
    if not duplicate:
        if len(geometry.related) > 1:
            old_matrix = np.eye(4)
            old_matrix[:3, :3] = old_rotation
            old_matrix[:3, 3] = geometry.frame.origin
            old_tool = geometry.mesh.raw.copy()
            old_tool.apply_transform(old_matrix)
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
    placed = boolean(
        kind, [body, MeshData.of(tool)], quality=ctx.quality, seed=ctx.seed, cancelled=ctx.cancelled
    )
    findings.extend(placed.findings)
    if duplicate:
        nothing = without_effect(source.mesh, placed.mesh, kind, ctx.profile)
        if nothing is not None:
            findings.append(nothing)
    features = dict(source.features)
    reserved = {*source.reserved_feature_ids, *source.features}
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
            related, id=identifier, params=values, face_indices=(), provenance="generated"
        )
        lost = _throughness_lost(
            placed.mesh,
            moved,
            values["centre"],
            operation,
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        findings.extend(lost)
        if lost:
            moved = dataclasses.replace(moved, params={**values, "through": False})
        features[identifier] = moved
        reserved.add(identifier)
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
        title=_("Normale X"),
        default=0.0,
        placement="advanced",
        doc=_(
            "Freie Richtung am neuen Ort. Null in allen drei Feldern erhält die bisherige Richtung."
        ),
    )
    ny: float = param(
        title=_("Normale Y"),
        default=0.0,
        placement="advanced",
        doc=_("Weitere Achse der Richtung — siehe Normale X."),
    )
    nz: float = param(
        title=_("Normale Z"),
        default=0.0,
        placement="advanced",
        doc=_("Weitere Achse der Richtung — siehe Normale X."),
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
    from app.core.perceive.actions import reason_against

    feature = source.features.get(name)
    if feature is None:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
            values={"feature": name, "object": source.id},
            constraint="unknown_feature",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    against = reason_against(op, feature.kind)
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
#: bleibt für die anderen Handlungen und für Netze, auf denen die Beziehung
#: nicht eindeutig erkannt werden kann. Dort trägt weiter nur der gemessene
#: Weg über Zahlen: ein Stopfen mit dem Durchmesser der Senkung über die volle
#: Wandstärke schließt beides in einem Zug.
_NO_OWN_BODY: Final = _(
    "Dieses Merkmal geht in ein anderes über — eine Senkung über einer "
    "Bohrung etwa —, und sein Hohlraum gehört nicht ihm allein. Eine einzelne "
    "Bearbeitung würde die Bohrung darunter mit verschließen. Verschließen Sie beides in einem "
    "Zug: „Bohrung verschließen“ ohne Merkmal, mit dem Durchmesser der Senkung "
    "und der vollen Wandstärke — danach setzen Sie es an der neuen Stelle neu."
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
    title=_("Merkmal verschieben"),
    category="holes",
    params=MoveFeatureParams,
    consumes=1,
    produces=1,
    applies_to=list(MOVABLE_KINDS),
    touches_features=True,
    deterministic=False,
    doc=_(
        "Versetzt ein erkanntes Merkmal an eine andere Stelle: Bohrung, Zapfen, "
        "Senkung, Verjüngung, Kuppel oder Pfanne."
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
    chain, touches_other = cavity_chain_state_at(feature, source.features, body)
    if chain is None and touches_other:
        raise ValidationError(
            field="at_feature",
            detail=_NO_OWN_BODY,
            values={"feature": feature.id},
            constraint="not_movable",
        )
    ctx.progress(0.1, str(_("Das Merkmal wird an seiner alten Stelle geschlossen …")))
    travel = np.asarray(target, dtype=float) - np.asarray(centre, dtype=float)
    if chain is not None:
        bore, widening = chain[0], chain[-1]
        cavity_body = _paired_cavity_body(body, *chain)
        if cavity_body is None:
            raise ValidationError(
                field="at_feature",
                detail=_NO_OWN_BODY,
                values={"feature": feature.id, "bore": bore.id, "widening": widening.id},
                constraint="not_movable",
            )
        closed = boolean(
            "union",
            [body, cavity_body],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        shifted_cavity = cavity_body.raw.copy()
        shifted_cavity.apply_translation(travel)
        ctx.progress(0.6, str(_("Das Merkmal wird an seiner neuen Stelle gesetzt …")))
        placed = boolean(
            "difference",
            [closed.mesh, MeshData.of(shifted_cavity)],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        features = dict(source.features)
        for related in chain:
            related_centre = np.asarray(related.params["centre"], dtype=float) + travel
            features[related.id] = dataclasses.replace(
                related,
                params={
                    **related.params,
                    "centre": tuple(float(value) for value in related_centre),
                },
                provenance="generated",
            )
        through_feature = bore
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
        placed = boolean(
            "difference" if cavity else "union",
            [closed.mesh, _tool_for(body, feature, target, alone=True)],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        moved = dataclasses.replace(
            feature,
            params={**feature.params, "centre": target},
            provenance="generated",
        )
        features = {**source.features, feature.id: moved}
        through_feature = feature
        through_target = target

    findings = [*closed.findings, *placed.findings]
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
    )
    findings += lost
    if lost:
        updated = features[through_feature.id]
        features[through_feature.id] = dataclasses.replace(
            updated, params={**updated.params, "through": False}
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
    highest = 0
    for name in (*source.features, *source.reserved_feature_ids):
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
        "Legt ein erkanntes Merkmal ein zweites Mal an: Bohrung, Zapfen, Senkung, "
        "Verjüngung, Kuppel oder Pfanne."
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
    ctx.progress(0.2, str(_("Das Merkmal wird an der neuen Stelle angelegt …")))
    change: BooleanKind = "difference" if cavity else "union"
    placed = boolean(
        change,
        [
            body,
            _tool_for(body, feature, target, alone=_stands_alone(body, feature, source.features)),
        ],
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
    findings += _throughness_lost(
        placed.mesh,
        feature,
        target,
        "duplicate_feature",
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    copy = dataclasses.replace(
        feature,
        id=_free_feature_id(source, feature.kind),
        params={**feature.params, "centre": target},
        provenance="generated",
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**source.features, copy.id: copy},
                reserved_feature_ids=tuple(
                    sorted({*source.reserved_feature_ids, *source.features, copy.id})
                ),
            )
        ],
        findings=findings,
        solver=placed.solver,
    )


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
    cache_version="3",
    title=_("Merkmal entfernen"),
    category="holes",
    params=RemoveFeatureParams,
    consumes=1,
    produces=1,
    applies_to=[*MOVABLE_KINDS, "fillet"],
    touches_features=True,
    deterministic=False,
    doc=_(
        "Entfernt ein erkanntes Merkmal: Bohrung, Zapfen, Senkung, Verjüngung, "
        "Kuppel, Pfanne oder Rundung."
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
    measured = [float(value) for value in feature.params["centre"]]
    centre: Vec3 = (measured[0], measured[1], measured[2])

    body = as_mesh_data(source.mesh)
    cavity = is_a_cavity(feature)
    chain = _cavity_chain_of(body, feature, source.features)
    answered: dict[str, Any] = {}
    together = False
    if chain is not None:
        choice = params.sections
        if choice == "ask":
            choice = _asked_about_sections(ctx, chain)
            answered["sections"] = choice
        together = choice == "chain"

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
                detail=_NO_OWN_BODY,
                values={"feature": feature.id},
                constraint="not_movable",
            )
        closed = boolean(
            "union",
            [body, filled],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
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
                detail=_NO_OWN_BODY,
                values={"feature": feature.id},
                constraint="not_movable",
            )
        closed = section
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

    remaining = {name: entry for name, entry in source.features.items() if name not in gone}
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
    title=_("Merkmal drehen"),
    category="holes",
    params=RotateFeatureParams,
    consumes=1,
    produces=1,
    # **Ohne die Kugel.** Sie hat keine Lage, die sich drehen ließe — gedreht
    # sähe sie aus wie vorher, und eine Handlung ohne Wirkung ist schlechter
    # als keine (Roberts „alles, was bei den jeweiligen sinnvoll ist").
    # Das Langloch dreht dabei seine Mittellinie mit (``_with_turned_direction``).
    applies_to=["hole", "pin", "cone", "slot"],
    touches_features=True,
    deterministic=False,
    doc=_("Kippt ein erkanntes Merkmal um seine Mitte: Bohrung, Zapfen, Senkung oder Verjüngung."),
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
    ctx.progress(0.6, str(_("Das Merkmal wird gedreht gesetzt …")))
    placed = boolean(
        "difference" if cavity else "union",
        [
            closed.mesh,
            _tool_for(
                as_mesh_data(source.mesh), spun, centre, axis=turned_axis, alone=stands_alone
            ),
        ],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    moved = dataclasses.replace(
        spun,
        params={**spun.params, "axis": turned_axis},
        provenance="generated",
    )
    # **Derselbe Befund wie beim Versetzen, und er fehlte hier.** Eine gekippte
    # Bohrung trifft die Gegenseite nicht mehr: Gemessen am 03.09.2026 an einer
    # 12 mm starken Wand mit einer durchgehenden Bohrung Ø 6 blieben nach 30°
    # **86,8 mm³** im alten Schlauch stehen, nach 60° **158,1** — und keiner der
    # beiden Läufe sagte etwas. Gefragt wird mit der **gedrehten** Achse, sonst
    # misst die Prüfung den Schlauch von vorher.
    findings = [*closed.findings, *placed.findings]
    findings += _throughness_lost(
        placed.mesh,
        moved,
        centre,
        "rotate_feature",
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**source.features, feature.id: moved},
            )
        ],
        findings=findings,
        solver=placed.solver,
    )


def _turned(feature: Feature, axis: Axis, angle: float) -> Vec3:
    """Die Achse des Merkmals, um ``axis`` um ``angle`` Grad gedreht."""
    return _turned_vector(feature.params.get("axis", (0.0, 0.0, 1.0)), axis, angle)


def _turned_vector(vector: Any, axis: Axis, angle: float) -> Vec3:
    """Ein Richtungsvektor, um ``axis`` um ``angle`` Grad gedreht und normiert."""
    direction = np.asarray(vector, dtype=float)
    matrix = trimesh.transformations.rotation_matrix(  # type: ignore[no-untyped-call]
        math.radians(angle), AXIS_NORMALS[axis]
    )
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


@register_op(
    name="resize_feature",
    cache_version="4",
    title=_("Merkmal ändern"),
    category="holes",
    params=ResizeFeatureParams,
    consumes=1,
    produces=1,
    # **Nicht ``hole``** — dafür gibt es ``resize_hole`` mit eigenem Weg durch
    # den exakten Kern und einer Materialkompensation, die für ein Loch gilt und
    # für einen Zapfen andersherum liefe. Die beiden überschneiden sich deshalb
    # nicht, und ``perceive.actions`` legt sie zu **einer** Zeile zusammen.
    applies_to=["pin", "cone", "sphere", "fillet"],
    touches_features=True,
    deterministic=False,
    doc=_(
        "Ändert den Durchmesser eines erkannten Merkmals: Zapfen, Senkung, "
        "Verjüngung, Kuppel, Pfanne — oder den Radius einer Rundung."
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
            _tool_for(as_mesh_data(source.mesh), feature, centre, scale=scale, alone=stands_alone),
        ],
        quality=ctx.quality,
        seed=ctx.seed,
        cancelled=ctx.cancelled,
    )

    changed = dataclasses.replace(
        feature,
        params={**feature.params, "diameter": params.diameter},
        provenance="generated",
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=placed.mesh,
                features={**source.features, feature.id: changed},
            )
        ],
        findings=[
            *closed.findings,
            *placed.findings,
            *_widening_findings(source, feature, params.diameter),
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
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=False,
        placement="advanced",
        doc=_(
            "Vergrößert das gewählte Fertigmaß um den Wert aus dem Materialprofil. "
            "Aus bleibt das gemessene Maß unverändert."
        ),
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
    cache_version="4",
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
    doc=_("Ändert den Durchmesser einer erkannten Bohrung."),
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
    centre = _named_place(params.x, params.y, params.z) or measured_centre
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
    if is_close(cut, previous) and not moved_hole:
        return OpResult(outputs=[source], findings=[_unchanged_bore(cut)])
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
        if feature.kind == "slot":
            # **Ein Langloch wird gefüllt und neu geschnitten, in beide
            # Richtungen** (RM-156). Beim Verbreitern deckte der neue Umriss den
            # alten zwar mit ab; beim Verschmälern bliebe ohne das Füllen die
            # alte Breite stehen, und das Maß im Objektbaum wäre eine Behauptung
            # über Material, das nicht mehr da ist. Ein Weg für beide Fälle ist
            # billiger als zwei, die sich in einem unterscheiden.
            angle_now = slot_angle_of(feature, axis)
            solid = edit.slot_bore(
                edit.fill_bore(
                    source.mesh,
                    position=measured_centre,
                    direction=axis,
                    diameter=previous,
                    depth=depth,
                    length=_bore_number(feature, "length"),
                    angle_deg=angle_now,
                ),
                position=centre,
                direction=axis,
                diameter=cut,
                depth=_through_bore_depth(source.mesh, centre, axis) if through else depth,
                length=slot_length_now,
                angle_deg=angle_now,
                overlap=0.0,
            )
        elif moved_hole:
            solid = edit.cut_bore(
                edit.fill_bore(
                    source.mesh,
                    position=measured_centre,
                    direction=axis,
                    diameter=previous,
                    depth=depth,
                ),
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
        findings: list[Finding] = []
        if not moved_hole:
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
            )
        )
        findings.extend(compensation_findings(params.diameter, cut, params.compensate))
        findings.extend(_widening_findings(source, feature, params.diameter))
        exact_features, recognised = _preserved_exact_features(
            source.features,
            features_of(solid),
            looked_for,
            cut,
            solid,
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
        )

    body = as_mesh_data(source.mesh)
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
    # **Ein Langloch geht immer zu, bevor es neu geschnitten wird** (RM-156) —
    # auch ohne Versatz. Beim Verbreitern deckte der neue Umriss den alten mit
    # ab; beim Verschmälern bliebe die alte Breite stehen, und das Maß im
    # Objektbaum wäre eine Behauptung über Material, das nicht mehr da ist.
    if moved_hole or feature.kind == "slot":
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
    elif moved_hole:
        # **An der neuen Stelle wird gebohrt, nicht geändert.** Die alte ist
        # eben zugegangen; dort, wo die Bohrung hinsoll, ist volles Material.
        # `resize_bore` verglich stattdessen die zwei Durchmesser, fand sie
        # gleich und gab den Körper unverändert zurück — gemessen am
        # 10.09.2026: Loch weiterhin bei (-20 | -10), Volumen unverändert,
        # dazu der Satz „Die Bohrung hat bereits diesen Durchmesser".
        #
        # **Und die Vieleckzugabe gehört dazu**, denn das Maß hier ist ein
        # gemessenes: Ein eingeschriebenes 48-Eck ist schmaler als sein
        # Umkreis, und ohne die Zugabe schrumpfte die Bohrung bei jedem
        # Versetzen (gemessen 10.09.2026: 7,9848 vorher, 7,9696 danach).
        # ``compensate`` steht dabei auf ``False`` — die Materialtoleranz ist
        # in ``cut`` schon drin, ein zweites Mal wäre sie zweimal drauf.
        result = drill(
            body,
            position=centre,
            axis="z",
            normal=axis,
            diameter=cut + _polygon_gain_for(cut),
            depth=0.0 if through else exact_depth,
            anchor="centre",
            profile=ctx.profile,
            compensate=False,
            quality=ctx.quality,
            seed=ctx.seed,
        )
    else:
        result = resize_bore(
            body,
            position=centre,
            direction=axis,
            previous_diameter=previous,
            diameter=params.diameter,
            depth=exact_depth,
            through=through,
            profile=ctx.profile,
            compensate=params.compensate,
            quality=ctx.quality,
            seed=ctx.seed,
        )
    if result.solver is None:
        return OpResult(outputs=[source], findings=result.findings)
    # **Und die Toleranz wird auch beim Versetzen gemeldet.** `drill` erzeugt
    # den Befund nur bei `compensate=True`, und der Aufruf oben setzt `False`,
    # weil `cut` sie schon trägt — ohne diese Zeile verschwände die Auskunft
    # „Die Bohrung wurde um die Materialtoleranz vergrößert" still, sobald das
    # Loch die Stelle wechselt (Fund des Reviews, 11.09.2026).
    moved_findings = (
        compensation_findings(params.diameter, cut, params.compensate) if moved_hole else []
    )
    resized_feature = _recognised_resized_feature(
        result.mesh, looked_for, cut if moved_hole else result.diameter
    )
    carried = {
        name: entry
        for name, entry in source.features.items()
        if entry.provenance == "generated" and name != feature.id
    }
    # Findet sich die geänderte Bohrung nicht wieder, bleibt der Körper und
    # das Merkmal geht — mit einem Satz darüber. Ihn zu behalten wäre eine
    # Behauptung über etwas, das die Erkennung gerade nicht bestätigt.
    features = (
        {**carried, feature.id: resized_feature} if resized_feature is not None else dict(carried)
    )
    findings = [*closed_first, *result.findings, *moved_findings]
    findings.extend(_widening_findings(source, feature, params.diameter))
    if resized_feature is None:
        findings.append(_bore_no_longer_a_feature(feature, result.diameter))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh, features=features)],
        solver=result.solver,
        findings=findings,
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
            "der Bohrung. Beim Anklicken steht hier sein Doppeltes: ein "
            "Langloch, in dem sich eine Schraube um einen Durchmesser "
            "verschieben lässt."
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


#: Die Arten, aus denen ein Langloch werden kann.
#:
#: Ein **Langloch** steht dabei, und das ist keine Verlegenheit: Die Operation
#: zieht ein rundes Loch auseinander, und eines, das schon lang ist, noch
#: weiter. Ohne diesen Eintrag wäre ein erkanntes Langloch eine Sackgasse —
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
    cache_version="4",
    # **Kein „Bohrung zum Langloch".** Der Titel stand so, solange die
    # Operation nur an einer Bohrung galt; seit die Erkennung Langlöcher findet
    # (:mod:`app.core.perceive.slots`), gilt sie auch an einem und hieße dort
    # „Bohrung zum Langloch" an etwas, das keine Bohrung mehr ist. „Ziehen"
    # trifft beides: aus einem runden Loch ein langes, aus einem langen ein
    # längeres.
    title=_("Zum Langloch ziehen"),
    category="holes",
    params=SlotHoleParams,
    consumes=1,
    produces=1,
    applies_to=list(SLOT_FROM),
    touches_features=True,
    deterministic=False,
    doc=_(
        "Zieht eine erkannte Bohrung zu einem Langloch auseinander. Der "
        "Durchmesser bleibt, wie er gemessen wurde — eingetragen werden nur "
        "Länge und Richtung."
    ),
)
def slot_hole(ctx: OpContext) -> OpResult:
    """Dieselbe Formänderung für Netze und für exakte Körper.

    Der Durchmesser bleibt, wie er gemessen wurde; eingetragen werden Länge und
    Richtung.

    **Ein bestehendes Langloch geht denselben Weg.** Seine Mitte, seine Achse
    und seine Breite stehen im Merkmal wie bei einer Bohrung; was dazukommt,
    ist die Richtung, in der es schon liegt — und die wird zur Vorgabe, damit
    ein Zug an der Länge es nicht quer stellt.
    """
    params = cast(SlotHoleParams, ctx.params)
    source = ctx.inputs[0]
    feature = _chosen_bore(source, params.at_feature, op="slot_hole")
    from app.core.perceive.relations import cavity_chain_state_at

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
    chain, touches_other = cavity_chain_state_at(selected, neighbours, body)
    if touches_other or (chain is not None and len(chain) > 1):
        raise ValidationError(
            field="at_feature",
            constraint="slot_and_widening",
            value=feature.id,
            detail=_(
                "Diese Bohrung ist mit weiteren Hohlraumabschnitten verbunden. "
                "Entfernen Sie zuerst die Senkung, oder wählen Sie eine Bohrung ohne Senkung."
            ),
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
    centre = _named_place(params.x, params.y, params.z) or _bore_vector(feature, "centre")
    axis = _bore_vector(feature, "axis")
    diameter = _bore_number(feature, "diameter")
    depth = _bore_number(feature, "depth")
    through = bool(feature.params.get("through", False))
    # **Gefragt wird gegen den gemessenen Durchmesser**, denn gegen ihn misst
    # auch die Erkennung — und sie ist es, die entscheidet, ob nachher ein
    # Langloch im Objektbaum steht (:func:`prepare.shortest_slot`).
    shortest = shortest_slot(diameter)
    if params.slot_length < shortest - EPS_GEOM:
        raise ValidationError(
            field="slot_length",
            constraint="slot_proportion",
            detail=SLOT_TOO_SHORT,
            value=params.slot_length,
            values={
                "diameter": format_length(diameter),
                "shortest": format_length(shortest),
            },
        )
    # **Und an einem Langloch wird gegen seine Länge gefragt, nicht gegen die
    # Breite.** Die Prüfung darüber deckt den ersten Zug; sie lässt am zweiten
    # jede Zahl durch, die größer als der Durchmesser ist — auch eine kleinere
    # als die vorhandene Länge. Gemessen an 20,016 mm mit der Eingabe 12:
    # abgetragen 0,87 mm³ (der Toleranzrand), kein Befund, das Langloch danach
    # unverändert. Ein Schritt im Verlauf, der nichts tut und nichts sagt.
    #
    # **Echt kürzer, nicht „nicht länger".** Hier stand `<= current`, und das
    # traf die eigene Vorbelegung: `perceive.actions._slot_value` setzt das Feld
    # auf die **gemessene** Länge des Langlochs — ausdrücklich, damit kein Feld
    # mit einer Absage begrüßt. Wer anklickte und OK drückte, las „Dieses
    # Langloch ist bereits länger als die eingetragene Länge" und darunter
    # zweimal dieselbe Zahl. Und reines **Drehen** war damit unerreichbar: Ein
    # Winkel bei unveränderter Länge kam nie bis zur Geometrie (Fund der
    # Nachkontrolle, 11.09.2026).
    if feature.kind == "slot":
        current = _bore_number(feature, "length")
        if params.slot_length < current - EPS_GEOM:
            raise ValidationError(
                field="slot_length",
                constraint="slot_growth",
                detail=SLOT_NOT_SHORTER,
                value=params.slot_length,
                values={
                    "previous": format_length(current),
                    "wanted": format_length(params.slot_length),
                },
            )
    _reject_oversized("slot_length", params.slot_length, source.mesh, kind="length")
    # Die Vorbelegung am Merkmal liefert dessen Richtung. Jeder übergebene
    # Winkel gilt unverändert, auch null; sonst widerspricht der Schnitt dem Griff.
    angle = params.slot_angle
    # Die Merkmale, die bleiben — ohne das, aus dem gerade ein Langloch wird.
    carried = {
        name: entry
        for name, entry in source.features.items()
        if entry.provenance == "generated" and name != feature.id
    }
    # **Nur beim ersten Zug.** Aus einem Langloch wird kein Langloch — es wird
    # länger, und dabei behält es Art und Kennung. Der Satz stünde dort über
    # einer Umbenennung, die nicht stattfindet.
    said: list[Finding] = []
    if feature.kind == "hole":
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
    crossing = _slot_across_a_slot(feature, axis, angle)
    if crossing is not None:
        said.append(crossing)

    # **Wer versetzt, schließt die alte Stelle** — sonst steht die Bohrung noch
    # da und daneben ein Langloch (gemessen 10.09.2026: `hole_1` und `slot_1`
    # im selben Körper). Dieselbe Paarung wie bei *Merkmal verschieben*: an der
    # alten Stelle das Gegenteil des Merkmals, an der neuen das Merkmal selbst.
    measured = _bore_vector(feature, "centre")
    moved = not all(is_close(a, b) for a, b in zip(centre, measured, strict=True))
    # **Die Zugabe gilt dem ersten Zug.** Sie hält den Langlochkörper von der
    # runden Bohrungswand fern, an die er sich sonst entlang zweier Linien
    # legte (:data:`prepare.FEATURE_OVERLAP`). An einem Langloch, das schon
    # eines ist, gibt es diese Wand nicht mehr — die Flanken des Werkzeugs
    # liegen auf den Flanken des Lochs, und das rechnen beide Kerne robust.
    # Mit der Zugabe wurde das Loch dagegen bei **jedem** Zug breiter:
    # gemessen 11.09.2026 am Netz 5,2057 → 5,2213 → 5,2371 an einer Bohrung
    # von 5,1901, am exakten Körper je Zug genau die Zugabe (Fund des
    # Reviews). Wer ein Langloch dreimal nachzieht, soll dieselbe Schraube
    # hindurchbekommen wie nach dem ersten Mal.
    overlap = FEATURE_OVERLAP if feature.kind == "hole" else 0.0

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
        if moved:
            # Bis zum 10.09.2026 stand hier eine Absage: „Am exakten Körper
            # lässt sich ein Loch noch nicht versetzen." Sie hatte einen
            # Grund — der Kern konnte kein Loch füllen —, und der ist mit
            # `edit.fill_bore` weg. Zwischen den beiden Kernen soll kein
            # Unterschied bleiben (Robert, 10.09.2026).
            started = edit.fill_bore(
                started,
                position=measured,
                direction=axis,
                diameter=diameter,
                depth=depth,
                length=_bore_number(feature, "length") if feature.kind == "slot" else 0.0,
                angle_deg=slot_angle_of(feature, axis) if feature.kind == "slot" else 0.0,
                opening=(
                    _bore_vector(feature, "mouth_centre"),
                    _bore_vector(feature, "opening_normal"),
                )
                if feature.params.get("open")
                else None,
            )
        solid = edit.slot_bore(
            started,
            position=centre,
            direction=axis,
            diameter=diameter,
            depth=_through_bore_depth(started, centre, axis) if through else depth,
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
        nothing = without_effect(source.mesh, solid, "difference", ctx.profile)
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
                travel=slot_travel(diameter=diameter, length=params.slot_length),
                angle_deg=angle,
                body=as_mesh_data(source.mesh),
            )
        )
        exact_features = features_of(solid)
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
    if moved:
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
    result = slot_bore(
        body,
        position=centre,
        direction=axis,
        diameter=diameter,
        depth=_through_bore_depth(body, centre, axis) if through else exact_depth,
        through=through,
        length=params.slot_length,
        angle_deg=angle,
        profile=ctx.profile,
        quality=ctx.quality,
        seed=ctx.seed,
        overlap=overlap,
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
        detect(result.mesh),
        feature,
        centre=centre,
        diameter=diameter,
        length=params.slot_length,
        diagonal=result.mesh.bounds.diagonal,
        body_centre=result.mesh.bounds.centre,
        angle=angle,
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
        solver=result.solver,
        findings=findings,
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
    from app.core.perceive.relations import cavity_chain_at, widening_at_the_mouth

    mesh = as_mesh_data(source.mesh)
    chain = cavity_chain_at(feature, source.features, mesh)
    if chain is not None and len(chain) > 2:
        position = next(index for index, section in enumerate(chain) if section.id == feature.id)
        swallowed = (
            position + 1 < len(chain)
            and diameter >= float(chain[position + 1].params["diameter"]) - EPS_GEOM
        )
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


def _slot_across_a_slot(
    feature: Feature, axis: tuple[float, float, float], angle: float
) -> Finding | None:
    """Sagt es, wenn der Zug nicht in Richtung des vorhandenen Langlochs geht.

    **Gefunden am gefahrenen Weg und nicht im Code** (10.09.2026): Ein
    bestehendes Langloch mit 90 Grad noch einmal gezogen ergab ein Kreuz, im
    Objektbaum standen danach vier Hohlkehlen, und gesagt hatte es niemand. Das
    Ergebnis ist richtig gerechnet — nur wollte es kaum jemand, und wer es
    wollte, hört den Satz einmal und überliest ihn.

    Der Satz spricht deshalb nicht vom Kreuz: Bei einem Grad Unterschied
    entsteht keines, und trotzdem ist die Öffnung danach keine gerade mehr
    (gemessen, siehe :data:`SLOT_ACROSS_LIMIT`). Er nennt den Winkel und den
    Weg zurück, und beides stimmt bei einem Grad wie bei neunzig.
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
        code="slot_hole.crosses",
        severity="warning",
        message=_(
            "Das neue Langloch steht {angle:.1f} Grad gegen das vorhandene. "
            "Beide zusammen sind keine gerade Öffnung mehr; wollten Sie es nur "
            "verlängern, lassen Sie die Richtung auf null.",
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


def _named_place(x: float | None, y: float | None, z: float | None) -> Vec3 | None:
    """Die genannte Stelle — oder nichts, wenn keine genannt wurde (RM-154).

    **Drei Nullen waren einmal die Antwort auf beides.** ``x/y/z`` lasen sich
    als „lass das Loch, wo es ist", sobald alle drei null waren; damit ließ es
    sich in jede Stelle versetzen außer in den Ursprung — und Solidon legt einen
    Quader **um** den Ursprung, an einer mittig gelegten Platte ist (0 | 0 | 0)
    also die Mitte des Teils und kein Randfall.

    Seit die drei Felder ``optional`` tragen, steht „nicht gesagt" als ``None``
    da. Genannt ist eine Stelle, sobald **eine** der drei Achsen eine Zahl
    trägt; die übrigen fallen auf null zurück, denn wer eine Achse nennt,
    beschreibt einen Ort und keine Verschiebung.
    """
    if x is None and y is None and z is None:
        return None
    return (float(x or 0.0), float(y or 0.0), float(z or 0.0))


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
    raw = mesh.raw
    valid = [index for index in feature.face_indices if 0 <= index < len(raw.faces)]
    length = math.sqrt(sum(value * value for value in axis))
    if not valid or length <= EPS_GEOM:
        return fallback
    unit = tuple(value / length for value in axis)
    vertices = raw.vertices[raw.faces[valid].reshape(-1)]
    along = vertices[:, 0] * unit[0] + vertices[:, 1] * unit[1] + vertices[:, 2] * unit[2]
    span = float(along.max() - along.min())
    return span if math.isfinite(span) and span > EPS_GEOM else fallback


def _unchanged_bore(diameter: float) -> Finding:
    """Die gemeinsame Auskunft für Netz und exakten Körper."""
    return Finding(
        code="bore.resize_unchanged",
        severity="info",
        message=_("Die Bohrung hat bereits diesen Durchmesser."),
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
) -> str | None:
    """Vergleicht Durchgänge entlang ihrer Achse, Sacklöcher an ihrer Mitte."""
    from app.core.perceive.matching import match

    opened = [
        name
        for name, candidate in detected.items()
        if candidate.params.get("open")
        and _sits_at(candidate, expected, diagonal)
        and abs(_bore_number(candidate, "diameter") - _bore_number(expected, "diameter"))
        <= max(FEATURE_OVERLAP, _bore_number(expected, "diameter") * _SAME_LENGTH)
    ]
    if len(opened) == 1:
        return opened[0]
    candidates: dict[str, Feature] = {}
    for name, candidate in detected.items():
        if candidate.kind != expected.kind or not _sits_at(candidate, expected, diagonal):
            continue
        # Eine dickere Zielwand verschiebt die Mitte entlang derselben Achse.
        # Nur für belegte Durchgänge ist diese Koordinate frei; Nachbarlöcher
        # und voneinander getrennte Sacklöcher bleiben unterscheidbar.
        if expected.params.get("through") and candidate.params.get("through"):
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
    return match({expected.id: expected}, candidates, body_centre, diagonal).mapping.get(
        expected.id
    )


def _recognised_resized_feature(
    mesh: MeshData, feature: Feature, diameter: float
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
    from app.core.perceive.features import detect

    detected = detect(mesh)
    expected = _expected_bore(feature, diameter)
    found_id = _bore_match_id(detected, expected, mesh.bounds.centre, mesh.bounds.diagonal)
    if found_id is None:
        return None
    # **Und die Zuordnung wird nachgeprüft** — derselbe Fund wie an
    # ``_recognised_slot``, nur zwei Wochen älter: Wer eine Bohrung über den
    # Rand versetzt, hat danach einen offenen Ausschnitt statt einer Bohrung.
    # ``match`` traf dann die Nachbarbohrung acht Millimeter daneben, die trug
    # von da an die Kennung der versetzten, und ``resize_hole.feature_lost``
    # blieb aus (gemessen 11.09.2026 an zwei Ø-4-Bohrungen bei y = 46 und 54,
    # die obere auf 59,5 versetzt: `hole_2` stand danach bei 46).
    if not _sits_at(detected[found_id], expected, mesh.bounds.diagonal):
        return None
    return dataclasses.replace(
        detected[found_id],
        id=feature.id,
        provenance="generated",
        created_by=None,
    )


def _sits_at(candidate: Feature, expected: Feature, diagonal: float) -> bool:
    """Liegt das gefundene Merkmal dort, wo die Operation es hingesetzt hat?

    ``match`` nimmt ein Merkmal an, solange Lage und Durchmesser unter seiner
    Schwelle liegen — acht Prozent der Modelldiagonale, an einer Platte von
    200 mm also sechzehn Millimeter. Das ist die richtige Großzügigkeit für
    eine Zuordnung über eine fremde Operation hinweg und die falsche für eine,
    die die Stelle selbst genannt hat: Die gehört auf ``match_tolerance``
    genau getroffen, sonst ist es ein anderes Loch.
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
            if expected.params.get("through") and candidate.params.get("through"):
                offset -= float(offset @ axis) * axis
            if np.linalg.norm(offset) <= tolerance:
                return True
        return False
    offset = np.asarray(_bore_vector(candidate, "centre")) - _bore_vector(expected, "centre")
    if expected.params.get("through") and candidate.params.get("through"):
        axis = np.asarray(_bore_vector(expected, "axis"), dtype=float)
        axis /= np.linalg.norm(axis)
        offset -= float(offset @ axis) * axis
    return bool(np.all(np.abs(offset) <= tolerance))


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
        math.cos(math.radians(angle)) * frame.x_axis[i]
        + math.sin(math.radians(angle)) * frame.y_axis[i]
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
    found_id = _bore_match_id(detected, expected, body_centre, diagonal)
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
) -> tuple[dict[str, Feature], bool]:
    """Ordnet die exakte Topologie neu zu, mit dem gewählten Maß als Absicht."""
    from app.core.perceive.matching import apply_mapping, match

    bounds = solid.bounds
    wanted = _expected_bore(feature, diameter)
    found_id = _bore_match_id(detected, wanted, bounds.centre, bounds.diagonal)
    expected = {name: entry for name, entry in previous.items() if name != feature.id}
    if found_id is not None:
        expected[feature.id] = dataclasses.replace(detected[found_id], id=feature.id)
    matched = match(expected, detected, bounds.centre, bounds.diagonal)
    if found_id is None:
        matched.orphaned = (*matched.orphaned, feature.id)
    return apply_mapping(detected, matched, previous=previous), found_id is not None


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
        remaining = {name: found for name, found in source.features.items() if name != feature.id}
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


@register_op(
    name="hollow_object",
    title=_("Aushöhlen"),
    category="prepare",
    params=HollowParams,
    consumes=1,
    produces=1,
    doc=_(
        "Höhlt ein Objekt aus und setzt Entlüftungen. Spart Material und Zeit; "
        "die Wandstärke stimmt im Rahmen des Rasters."
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
    result = hollow(
        as_mesh_data(source.mesh),
        params.wall,
        vents=params.vents,
        vent_diameter=params.vent_diameter,
        open_top=params.open_top,
        quality=ctx.quality,
        progress=ctx.progress,
        cancelled=ctx.cancelled,
    )
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
                name=ctx.scene.unused_name(str(_("Prüfstück"))),
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


@register_op(
    name="split_bodies",
    title=_("In Einzelteile zerlegen"),
    category="prepare",
    params=SplitBodiesParams,
    consumes=1,
    produces=VARIABLE,
    produces_from="count",
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
                _("Der Körper besteht aus einem Stück; es gibt nichts zu zerlegen.")
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
    pair = (
        add_pins(
            first,
            second,
            plan,
            for_object(ctx.profile, source),
            start=connector_start,
            play=play or None,
            quality=ctx.quality,
            cancelled=ctx.cancelled,
        )
        if plan is not None
        else PinnedPair(first=first, second=second)
    )
    if glue_hint and plan is not None and plan.count and plan.shape == "round":
        pair.findings.append(connector_glue_finding())

    first_features, second_features = _features_after_split(source.features, plane)
    first_name, second_name = half_names(source.name, pinned=bool(pair.pin_features))
    return OpResult(
        solver=pair.solver,
        outputs=[
            dataclasses.replace(
                source,
                mesh=pair.first,
                name=first_name,
                features={**first_features, **pair.pin_features},
            ),
            dataclasses.replace(
                source,
                mesh=pair.second,
                name=second_name,
                features={**second_features, **pair.bore_features},
            ),
        ],
        findings=[*findings, *pair.findings, _halves_still_together(source)],
    )


def _features_after_split(
    features: dict[str, Feature], plane: SectionPlane
) -> tuple[dict[str, Feature], dict[str, Feature]]:
    """Nimmt bestehende Merkmale auf die geometrisch richtige Hälfte mit.

    Ein Merkmal genau auf dem neuen Schnitt wird selbst getrennt und kann
    deshalb nicht unverändert weitergelten. Ohne Mittelpunkt bleibt das alte
    Verhalten erhalten: Es reist mit der ersten Hälfte, statt geraten zu
    werden.
    """
    first: dict[str, Feature] = {}
    second: dict[str, Feature] = {}
    for feature_id, feature in features.items():
        side = feature_side(
            feature,
            plane,
            connector=feature_id.startswith(("pin_", "bore_")),
        )
        if side in (-1, None):
            first[feature_id] = feature
        elif side == 1:
            second[feature_id] = feature
    return first, second


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


@register_op(
    name="split_line",
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
        glue_hint=False,
        diameter=params.diameter,
        play=params.play,
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
                # Dieselbe Matrix legt ``moved_body`` exakt auf den Eingang.
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
        outputs.append(dataclasses.replace(entry, mesh=moved_body(entry.mesh, matrix)))
        last_matrix = matrix

    if params.arrange:
        outputs, moved_after = _laid_out_after_turning(ctx, params, outputs, findings)
        # **Und dann ist die gemeldete Bewegung die Drehung *und* der Weg zum
        # neuen Platz.** Sie ist die Auskunft für Vorschau und Gizmo, und die
        # muss den Eingang genau auf den Ausgang legen: erst gedreht, dann
        # verschoben. Der Versatz allein zeigte den Körper ungedreht am neuen
        # Ort, die Drehung allein gedreht am alten — beides war er nie.
        if moved_after is not None and last_matrix is not None:
            last_matrix = moved_after @ last_matrix

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
) -> tuple[list[SceneObject], Any]:
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
    shift = None
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
        laid.append(dataclasses.replace(entry, mesh=moved_body(entry.mesh, step), plate=plate))
        shift = step
    return laid, shift


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
        default=False,
        doc=_(
            "Legt Teile aus verschiedenen Filamenten auf verschiedene Platten. "
            "Zwei Filamente auf einer Platte kosten je gemeinsamer Schicht "
            "einen Wechsel samt Spülgang."
        ),
    )


def _arranged_by_material(ctx: OpContext, params: ArrangeParams) -> Arrangement:
    """Erst nach Filament gruppieren, dann jede Gruppe für sich anordnen.

    Den Vorschlag rechnet :func:`app.core.export.writer.plates_by_material`
    schon lange — er war nur von nirgends aus erreichbar. Hier wird er zu einer
    Handlung, und zwar als Umschalter an der bestehenden Operation statt als
    zweite daneben: es ist dieselbe Handlung mit einer anderen Vorgabe, wer
    neben wem liegt.

    Jede Gruppe bekommt ihre eigenen Platten, hintereinander weg. Die Grenze
    aus ``plates`` gilt dabei für die ganze Szene, nicht je Gruppe — sonst
    hätte ein Projekt mit drei Filamenten unversehens dreimal so viele
    Platten, wie jemand eingestellt hat.
    """
    from app.core.export.writer import plates_by_material

    groups = plates_by_material(list(ctx.inputs))
    order: list[int] = []
    for entry in ctx.inputs:
        group = groups[entry.id]
        if group not in order:
            order.append(group)

    meshes: dict[str, MeshData] = {}
    assigned: dict[str, int] = {}
    findings: list[Finding] = []
    next_plate = 0

    for group in order:
        members = [entry for entry in ctx.inputs if groups[entry.id] == group]
        # Sind die Platten aufgebraucht, teilt sich diese Gruppe die letzte mit
        # der vorigen — dieselbe Regel, die `arrange_on_bed` innerhalb einer
        # Gruppe befolgt: die letzte Platte nimmt den Rest, und der Bericht
        # sagt, dass sie übervoll ist. Ein Teil, das still aus der Anordnung
        # fiele, wäre ein Teil, das nie gedruckt wird.
        start = min(next_plate, params.plates - 1)
        arranged = arrange_on_bed(
            [as_mesh_data(entry.mesh) for entry in members],
            ctx.profile,
            params.spacing,
            params.plates - start,
            # Mit Kennungen: Der Bauraum-Befund soll den Körper beim Namen
            # nennen, nicht beim laufenden Index (Roberts Foto, 30.08.2026).
            object_ids=[entry.id for entry in members],
        )
        findings.extend(arranged.findings)
        for entry, mesh, plate in zip(members, arranged.meshes, arranged.plates, strict=True):
            meshes[entry.id] = mesh
            assigned[entry.id] = start + plate
        next_plate = start + arranged.plate_count

    return Arrangement(
        meshes=[meshes[entry.id] for entry in ctx.inputs],
        plates=[assigned[entry.id] for entry in ctx.inputs],
        findings=findings,
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
    if params.by_material:
        result = _arranged_by_material(ctx, params)
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
            # Hüllquadern, und ``moved_body`` legt ihn exakt auf den Eingang.
            dataclasses.replace(
                entry,
                mesh=moved_body(
                    entry.mesh,
                    translation(
                        (
                            mesh.bounds.minimum[0] - entry.mesh.bounds.minimum[0],
                            mesh.bounds.minimum[1] - entry.mesh.bounds.minimum[1],
                            mesh.bounds.minimum[2] - entry.mesh.bounds.minimum[2],
                        )
                    ),
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

    outcome = unround(as_mesh_data(source.mesh), source.features[name], quality=ctx.quality)
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
    if source.kind == "brep":
        return _exact_fillet(ctx, source, name, radius)
    from app.core.geom.edges import reround

    outcome = reround(as_mesh_data(source.mesh), source.features[name], radius, quality=ctx.quality)
    return _after_the_fillet(source, name, outcome)


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
    solid = (
        edit.unround(body, spot, was) if radius is None else edit.reround(body, spot, was, radius)
    )
    return OpResult(
        outputs=[dataclasses.replace(exact, mesh=solid, kind="brep", features=features_of(solid))]
    )


def _after_the_fillet(source: SceneObject, name: str, outcome: Any) -> OpResult:
    """Das Ergebnis, und die Kennung geht mit.

    Dieselbe Zusage wie bei jedem anderen Merkmal: Ein Verweis, der stehen
    bleibt, obwohl die Geometrie fort ist, wird später als Passungsfehler
    gemeldet — und dann sucht der Kunde an einem Teil, das in Ordnung ist.
    """
    kept = {key: value for key, value in source.features.items() if key != name}
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features=kept)],
        solver=outcome.solver,
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in outcome.findings],
    )
