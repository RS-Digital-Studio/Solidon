"""Gegenstücke auf zwei Körpern als **eine** Handlung (RM-147 E1, §14, §24).

Ein Passstift ist ohne seine Bohrung nichts, und eine Einpressbuchse ohne das
Durchgangsloch gegenüber auch nicht. Die Bibliothek kennt beide Hälften seit je
— sie zu setzen waren bis hierher drei Schritte: den Stift an Körper A, die
Bohrung an Körper B, und die Maße dabei ein zweites Mal eintippen. Drei
Rücknahmen für etwas, das zusammen gedacht ist, und zwei Zahlenreihen, die
auseinanderlaufen, sobald jemand eine davon ändert.

**Ein Ablauf und keine Operation**, aus demselben Grund wie bei
:mod:`app.core.lid_flow`: Eine Op bekommt ihre Szene nur lesend (Regel 3), und
die Auswertung ist eine reine Funktion (§15.1) — sie darf keine Passung ins
Dokument schreiben, sonst käme bei jedem Neurechnen eine dazu. Der Ablauf legt
beide Bausteinschritte in **eine** Transaktion, und die Passung wandert als
``DocumentChange`` in dieselbe; ein Undo nimmt alles drei zurück.

**Die gemeinsamen Maße stehen einmal.** Was beide Hälften teilen — Durchmesser,
Länge, Spiel —, geht als ein Satz Werte in beide Schritte. Das ist der Kern der
Sache: Ein Stift von 6 mm in einer Bohrung von 5 mm ist kein Paar, und die
einzige Stelle, an der so etwas entsteht, ist die zweite Eingabe.

**Und die Passung wird nachgetragen, nicht vorausgesagt.** Die Kennung eines
erzeugten Merkmals entsteht bei der Auswertung (``evaluate._renamed``), nicht
beim Anlegen des Schritts: Ein zweiter Stift am selben Körper heißt
``dowel_pin_2``. Wer sie vorher hinschreibt, schreibt eine Vermutung — gemessen
am ersten Anlauf dieses Moduls, der ``pin_1`` erwartete und ``dowel_pin_1``
bekam. Deshalb sind es zwei Schritte: :func:`apply_counterpart` legt die
Geometrie an, :func:`attach_fit` liest die Kennungen aus der gerechneten Szene
und hängt die Passung an dieselbe Transaktion.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from app.core.errors import CANCEL, CHANGE_SELECTION, CORRECT_INPUT, ValidationError
from app.core.knowledge import standards
from app.core.log import get_logger
from app.core.scene.fits import active_fits, numbered_name
from app.core.scene.history import History, OperationDraft, change_for
from app.core.types import (
    Document,
    Feature,
    FeatureRef,
    Finding,
    Fit,
    FitKind,
    ObjectId,
    Operation,
    OpId,
    Origin,
    Profile,
    Scene,
    TransactionId,
    thread_is_left_handed,
    thread_is_tapered,
)
from app.core.units import (
    COARSEST_PITCH,
    FINEST_PITCH,
    LARGEST_THREAD,
    SMALLEST_THREAD,
    format_length,
    is_close,
)
from app.i18n import _

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Pair:
    """Ein Bausteinpaar: was an das eine Teil kommt und was an das andere.

    ``shared`` sind die Parameter, die **beide** Hälften tragen — sie werden
    einmal eingegeben und in beide Schritte geschrieben. ``first``/``second``
    sind die Werte, die die Hälften unterscheiden; beim Passstift ist das
    ``kind``, bei Schraube und Mutter der Baustein selbst.

    ``feature_a``/``feature_b`` sind die Merkmale, zwischen denen die Passung
    steht (§14). Sie müssen die Bausteine wirklich versprechen — was hier
    steht und dort fehlt, ergäbe eine Passung ins Leere; ein Test hält beides
    gegen ``PartSpec.features``.
    """

    key: str
    title: Any
    part_a: str
    part_b: str
    feature_a: str
    feature_b: str
    kind: FitKind = "clearance"
    first: Mapping[str, Any] = field(default_factory=dict)
    second: Mapping[str, Any] = field(default_factory=dict)
    shared: tuple[str, ...] = ()
    doc: Any = ""


#: Die Paare, die Solidon als Gegenstücke kennt. Jedes ist eine Aussage über
#: zwei Bausteine der Bibliothek und über das Merkmal, an dem sie sich treffen.
#:
#: **Drei, und keine Liste um der Liste willen.** Der Passstift ist der Fall,
#: für den es das Wort „Gegenstück" gibt; Schraube und Mutter sind der zweite,
#: der ohne gemeinsame Steigung nicht funktioniert; Buchse und Durchgangsloch
#: sind der häufigste überhaupt — zwei Platten verschrauben. Wer ein viertes
#: dazunimmt, prüft dabei dreierlei: dass beide Bausteine die genannten
#: Merkmale wirklich führen, dass die gemeinsamen Parameter in beiden Schemata
#: gleich heißen, und dass die Passungsart die Sache trifft.
PAIRS: Final[tuple[Pair, ...]] = (
    Pair(
        key="dowel",
        title=_("Passstift und Passbohrung"),
        part_a="dowel",
        part_b="dowel",
        feature_a="pin",
        feature_b="bore",
        kind="clearance",
        first={"kind": "pin"},
        second={"kind": "bore"},
        shared=("diameter", "length", "shape", "play", "chamfer"),
        doc=_(
            "Der Stift steht am ersten Teil, die Bohrung sitzt im zweiten. "
            "Beide bekommen dasselbe Maß und dasselbe Spiel."
        ),
    ),
    Pair(
        key="screw_and_nut",
        title=_("Gedruckte Schraube und Mutter"),
        part_a="printed_screw",
        part_b="printed_nut",
        feature_a="thread",
        feature_b="thread",
        kind="thread",
        shared=("size", "play"),
        doc=_(
            "Die Schraube gehört an das erste Teil, die Mutter an das zweite. "
            "Größe und Spiel müssen dieselben sein, sonst greift kein Gewinde; "
            "die Steigung kommt für beide aus der Normteiltabelle."
        ),
    ),
    Pair(
        key="heatset_and_screw_hole",
        title=_("Einpressbuchse und Durchgangsloch"),
        part_a="heatset_m4",
        part_b="screw_hole",
        feature_a="bore",
        feature_b="bore",
        kind="clearance",
        shared=("size",),
        doc=_(
            "Die Buchse kommt in das erste Teil, das Loch für die Schraube in "
            "das zweite. Dieselbe Größe für beide — sonst greift die Schraube "
            "nicht oder klemmt im Durchgang."
        ),
    ),
)


def pair_named(key: str) -> Pair:
    """Das Paar zu diesem Schlüssel — oder ein Satz mit den bekannten (Regel 17)."""
    for entry in PAIRS:
        if entry.key == key:
            return entry
    raise ValidationError(
        field="pair",
        detail=_("Dieses Gegenstückpaar gibt es nicht."),
        value=key,
        constraint="unknown_pair",
        values={"known": ", ".join(one.key for one in PAIRS)},
        suggestions=(CORRECT_INPUT,),
    )


@dataclass(slots=True)
class CounterpartApplied:
    """Was der Ablauf hinterlassen hat — für Fenster und Tests."""

    object_ids: list[ObjectId] = field(default_factory=list)
    op_ids: tuple[OpId, ...] = ()
    """Die zwei Schritte, in der Reihenfolge des Paares. :func:`attach_fit`
    findet über sie die Merkmale, die gerade entstanden sind."""
    fit: Fit | None = None
    transaction: TransactionId | None = None
    findings: list[Finding] = field(default_factory=list)


def drafts_for(
    pair: Pair,
    first_object: ObjectId,
    second_object: ObjectId,
    shared: Mapping[str, Any],
    first_place: Mapping[str, Any],
    second_place: Mapping[str, Any],
) -> list[OperationDraft]:
    """Die zwei Schritte des Paares, mit denselben Maßen in beiden.

    Getrennt vom Anwenden, damit sich nachsehen lässt, **was** entstünde, ohne
    dass etwas entsteht — die Vorschau geht diesen Weg, und ein Test kann die
    Werte lesen, statt sie aus einem Dokument zurückzurechnen.

    Der Ort ist je Hälfte ein eigener: Der Stift steht auf einer Fläche des
    ersten Teils, die Bohrung sitzt in einer des zweiten. Was sie teilen, sind
    die Maße und nicht die Stelle.
    """
    common = {name: shared[name] for name in pair.shared if name in shared}
    return [
        OperationDraft(
            op=f"insert_{pair.part_a}",
            inputs=(first_object,),
            params={**common, **dict(pair.first), **dict(first_place)},
        ),
        OperationDraft(
            op=f"insert_{pair.part_b}",
            inputs=(second_object,),
            params={**common, **dict(pair.second), **dict(second_place)},
        ),
    ]


def apply_counterpart(
    document: Document,
    pair: Pair,
    first_object: ObjectId,
    second_object: ObjectId,
    shared: Mapping[str, Any],
    first_place: Mapping[str, Any],
    second_place: Mapping[str, Any],
    *,
    origin: Origin | None = None,
) -> CounterpartApplied:
    """Setzt beide Hälften in **einer** Transaktion (E1).

    Die Passung kommt erst mit :func:`attach_fit` dazu, nach der Auswertung —
    vorher steht die Kennung der erzeugten Merkmale nicht fest. Wer nur die
    Geometrie will (die Kommandozeile, ein Test), bleibt bei dieser Funktion.
    """
    if first_object == second_object:
        raise ValidationError(
            field="second_object",
            detail=_(
                "Ein Gegenstück braucht zwei verschiedene Teile — Stift und Bohrung "
                "im selben Körper wären ein Loch neben einem Zapfen."
            ),
            value=str(second_object),
            constraint="same_object",
            suggestions=(CORRECT_INPUT,),
        )

    history = History(document)
    applied = history.apply(
        pair.title,
        drafts_for(pair, first_object, second_object, shared, first_place, second_place),
        origin or Origin(by="user"),
    )
    steps = document.ops[-2:]
    made = [step.outputs[0] for step in steps if step.outputs]
    _log.info("counterpart %s: %s in one transaction", pair.key, ", ".join(made) or "?")
    return CounterpartApplied(
        object_ids=made,
        op_ids=tuple(step.id for step in steps),
        transaction=applied.id,
    )


def attach_fit(
    document: Document, applied: CounterpartApplied, pair: Pair, scene: Scene
) -> CounterpartApplied:
    """Hängt die Passung an die Transaktion, die die Geometrie gebracht hat (§14).

    **Die Kennungen werden gelesen, nicht geraten**: Welches Merkmal ein
    Bausteinschritt erzeugt hat, steht in ``Feature.created_by`` — dieselbe
    Auskunft, aus der das Kontextmenü seinen Eintrag *Diesen Schritt ändern*
    baut (§21.2). Der erste Anlauf hier hat ``pin_1`` erwartet und
    ``dowel_pin_1`` bekommen; eine Passung auf einen erfundenen Namen wäre
    still ins Leere gegangen.

    Die Passung reist als ``DocumentChange`` mit und nicht als eigener Schritt
    (§15.5): Ein Undo, das die Geometrie nimmt und die Passung stehen lässt,
    hinterließe einen Verweis auf ein Merkmal, das es nicht mehr gibt.

    **Die Toleranz ist ein Verweis und nie die Zahl** (Regel 7): ``auto:`` holt
    sie aus dem Materialprofil, damit eine spätere Kalibrierung (§28.3) auch
    ein Paar erreicht, das vor ihr entstanden ist.
    """
    if len(applied.object_ids) < 2 or len(applied.op_ids) < 2:
        # Ein Schritt ohne Körper gibt es am Bausteinweg nicht; käme er, wäre
        # eine Passung ins Leere schlechter als keine.
        _log.info("counterpart: %d output(s), no fit", len(applied.object_ids))
        return applied

    last = document.transactions[-1] if document.transactions else None
    if last is None or last.id != applied.transaction:
        applied.findings.append(
            Finding(
                code="parts.counterpart_unpaired",
                severity="warning",
                message=_(
                    "Der Verlauf hat sich seit dem Einsetzen geändert, deshalb fehlt die "
                    "Passung. Rechts unter Auswahl lässt sie sich nachtragen."
                ),
                values={"pair": pair.key},
            )
        )
        return applied

    first = _made_feature(
        scene, applied.object_ids[0], applied.op_ids[0], pair.part_a, pair.feature_a
    )
    second = _made_feature(
        scene, applied.object_ids[1], applied.op_ids[1], pair.part_b, pair.feature_b
    )
    if first is None or second is None:
        applied.findings.append(
            Finding(
                code="parts.counterpart_unpaired",
                severity="info",
                message=_(
                    "Ein Merkmal ist unter seinem Namen nicht zu finden, deshalb fehlt die "
                    "Passung. Rechts unter Auswahl lässt sie sich nachtragen."
                ),
                values={"pair": pair.key},
            )
        )
        _log.info("counterpart %s: features %s/%s not found", pair.key, first, second)
        return applied

    fit = Fit(
        name=numbered_name(document.fits, pair.key),
        a=FeatureRef(applied.object_ids[0], first),
        b=FeatureRef(applied.object_ids[1], second),
        kind=pair.kind,
        tolerance="auto:",
    )
    changes = change_for(document, fits=[*document.fits, fit])
    document.transactions[-1] = dataclasses.replace(last, changes=changes)
    document.fits.append(fit)

    applied.fit = fit if fit in active_fits(document) else None
    applied.findings.append(
        Finding(
            code="parts.counterpart_fit",
            severity="info",
            message=_(
                "Beide Hälften sind als Passung eingetragen — sie werden zusammen "
                "geprüft, und der Slicer bekommt dafür die genauere Außenwand."
            ),
            values={"fit": fit.name, "tolerance": str(fit.tolerance)},
        )
    )
    _log.info("counterpart %s: %s ↔ %s as fit %s", pair.key, first, second, fit.name)
    return applied


# --- Das Gegenstück zu einem Gewinde, das schon da ist (P2.6, Entscheidung 15) ---------------
#
# Die drei Paare oben setzen **beide** Hälften neu. Ein eingelesener Bolzen
# oder ein gedrucktes Gewinde hat seine Hälfte schon: Was fehlt, ist das
# Gegenstück am anderen Teil — zum Außengewinde das Innengewinde, zum
# Innengewinde der Bolzen —, und die Passung dazwischen. Das Maß kommt aus dem
# Gewinde selbst: eine Tabellengröße, wo es eine trifft, sonst sein eigenes
# Maß. Ein Gewinde Ø 6,4 mit Steigung 1,1 wird nicht still zu M6
# (Konzept §13.4), sondern bekommt ein Gegenstück Ø 6,4 mit Steigung 1,1.

#: Wie nah Durchmesser und Steigung an einem Tabellenmaß liegen müssen —
#: beides deutlich unter dem halben Abstand zweier Nachbargrößen der Tabelle
#: (M2 → M2.5: 0,5 im Durchmesser, 0,05 in der Steigung), damit kein Maß
#: zwei Größen trifft; ``tests/test_thread_counterpart.py`` hält das gegen die
#: Tabelle. Keine Fertigungstoleranz, sondern eine Erkennungsgrenze wie
#: ``units.match_tolerance``.
THREAD_SIZE_REACH: Final = (0.2, 0.02)


def thread_values_for(feature: Feature) -> dict[str, Any]:
    """Die Größe des Bausteingewindes, das zu diesem Gewinde passt.

    Trifft es eine Tabellengröße in Durchmesser und Steigung, ist es diese —
    ein gemessenes M6 bleibt ein M6. Sonst nimmt das Gegenstück das eigene Maß
    des Gewindes (``fasteners.CUSTOM_SIZE``). Bis zum 06.10.2026 endete die
    Antwort an der Tabelle: über M8 und zwischen zwei Größen gab es kein
    Gegenstück, nur einen Satz. Abgesagt wird, was kein Bausteingewinde baut —
    jenseits der gemeinsamen Grenzen oder ohne tragenden Kern
    (``fasteners.thread_problem``), und zwar vor dem Schritt, nicht erst in der
    Auswertung an einem Schritt, den der Kunde nicht eingegeben hat.
    """
    return _matched_thread(feature)[0]


def thread_size_note(feature: Feature) -> Finding | None:
    """Was das Gegenstück über die Wahl seines Maßes sagt — oder ``None``.

    Dieselbe Entscheidung wie :func:`thread_values_for`, als Satz für den Kunden.
    """
    return _matched_thread(feature)[1]


def _thread_tolerance(feature: Feature) -> tuple[float, float]:
    """Wie weit ein Gewinde von einer Tabellengröße liegen darf, um sie zu meinen.

    Die Erkennungsgrenze ``THREAD_SIZE_REACH`` plus das, was die Messung über
    sich selbst sagt: die Wendelabweichung (``uncertainty``) für die Steigung.
    Einen Kreisfehler (``fit_error``) trägt ein Gewindemerkmal nicht — den
    haben nur Zylinder, Kegel, Kugel und Torus (Review RM-532 Runde 2, U-N1).
    Ein erzeugtes Gewinde trägt auch keine Wendelabweichung und wird genau
    verglichen.
    """
    pitch_error = feature.params.get("uncertainty")
    pitch_extra = (
        abs(float(pitch_error))
        if isinstance(pitch_error, int | float) and not isinstance(pitch_error, bool)
        else 0.0
    )
    return THREAD_SIZE_REACH[0], THREAD_SIZE_REACH[1] + pitch_extra


def _matched_thread(feature: Feature) -> tuple[dict[str, Any], Finding | None]:
    """Maß und Begründung des Gegenstücks — die eine Entscheidung für beide.

    **Knapp neben einer Tabellengröße ist es die Tabellengröße, und der Befund
    sagt es** (Review RM-532, R5). Bis dahin wurde ein gemessenes Ø 6,0 x 1,03
    still ein eigenes Maß mit 1,03 Steigung — über 20 mm Länge 0,6 mm Phase
    neben einem wirklichen M6 x 1, und die Passungsprüfung verglich danach
    gemessen gegen gemessen. Liegt die Abweichung innerhalb dessen, was die
    Messung selbst als Unsicherheit nennt, kann sie M6 x 1 und 6 x 1,03 nicht
    unterscheiden, und gemeint ist fast immer das Normteil. Gefragt wird nicht:
    Der Kunde wüsste es nicht besser als die Messung, und der Befund nennt beide
    Maße, sodass *Merkmal ändern* das gemessene setzt, wo es wirklich so ist.
    Außerhalb dieser Unsicherheit bleibt das gemessene Maß, und der Befund sagt,
    dass es keine Normgröße ist.
    """
    from app.core.knowledge.parts.fasteners import CUSTOM_SIZE, thread_problem

    # Ein gedrucktes Gewinde nennt sein Nennmaß neben dem gebauten
    # (``build.thread``); das gebaute liegt um das Spiel daneben, bei TPU weiter
    # als die Erkennungsgrenze.
    named = feature.params.get("nominal")
    if isinstance(named, int | float) and not isinstance(named, bool) and named > 0.0:
        diameter = float(named)
    else:
        diameter = float(feature.params.get("diameter", 0.0))
    pitch = float(feature.params.get("pitch", 0.0))
    for size in standards.screw_sizes():
        screw = standards.screw(size)
        if (
            abs(screw.nominal - diameter) <= THREAD_SIZE_REACH[0]
            and abs(screw.pitch - pitch) <= THREAD_SIZE_REACH[1]
        ):
            return {"size": size}, None
    diameter_reach, pitch_reach = _thread_tolerance(feature)
    near = [
        size
        for size in standards.screw_sizes()
        if abs(standards.screw(size).nominal - diameter) <= diameter_reach
        and abs(standards.screw(size).pitch - pitch) <= pitch_reach
    ]
    if near:
        size = min(near, key=lambda entry: abs(standards.screw(entry).pitch - pitch))
        return {"size": size}, Finding(
            code="parts.counterpart_standard_size",
            severity="info",
            message=_(
                "Gemessen sind Ø {diameter}, Steigung {pitch}: das ist {size} innerhalb der "
                "Messunsicherheit. Ein anderes Maß setzt „Merkmal ändern“ am Gegenstück.",
                diameter=format_length(diameter),
                pitch=format_length(pitch),
                size=size,
            ),
            values={"size": size, "diameter_mm": diameter, "pitch_mm": pitch},
        )
    problem = (
        thread_problem(diameter, pitch, 0.0)
        if SMALLEST_THREAD <= diameter <= LARGEST_THREAD and 0.0 < pitch <= COARSEST_PITCH
        else None
    )
    if (
        not (SMALLEST_THREAD <= diameter <= LARGEST_THREAD and 0.0 < pitch <= COARSEST_PITCH)
        or problem is not None
    ):
        raise ValidationError(
            field="at_feature",
            detail=_(
                "Ein Gegenstück aus der Bibliothek reicht von Ø {smallest} bis Ø {largest}, "
                "Steigung {finest} bis {coarsest}, und braucht einen tragenden Kern. Dieses "
                "Gewinde liegt außerhalb.",
                smallest=format_length(SMALLEST_THREAD),
                largest=format_length(LARGEST_THREAD),
                finest=format_length(FINEST_PITCH),
                coarsest=format_length(COARSEST_PITCH),
            ),
            values={"feature": feature.id, "diameter": diameter, "pitch": pitch},
            constraint="beyond_threads",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    note = None
    if feature.provenance != "generated":
        note = Finding(
            code="parts.counterpart_own_measure",
            severity="info",
            message=_(
                "Gemessen sind Ø {diameter} mit Steigung {pitch} — keine Normgröße. Das "
                "Gegenstück nimmt dieses eigene Maß.",
                diameter=format_length(diameter),
                pitch=format_length(pitch),
            ),
            values={"diameter_mm": diameter, "pitch_mm": pitch},
        )
    return {"size": CUSTOM_SIZE, "diameter": diameter, "pitch": pitch}, note


def thread_counterpart_draft(
    feature: Feature, second_object: ObjectId, second_place: Mapping[str, Any]
) -> OperationDraft:
    """Der eine Schritt: das gegengleiche Bausteingewinde am anderen Teil, im passenden Maß."""
    if feature.kind != "thread":
        raise ValidationError(
            field="at_feature",
            detail=_("Das Gegenstück zum Gewinde braucht ein Gewinde als Ausgang."),
            value=feature.id,
            constraint="not_a_thread",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    if thread_is_left_handed(feature):
        raise ValidationError(
            field="at_feature",
            detail=_(
                "Ein Rechtsgewinde und ein Linksgewinde greifen nicht ineinander. Ein Gegenstück "
                "zu einem Linksgewinde gibt es aus der Bibliothek nicht."
            ),
            value=feature.id,
            constraint="left_handed",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    # **Die Gangzahl gehört zur Frage.** Ein zweigängiges Gewinde ist kein
    # eingängiges mit anderem Maß: Bis zum 22.09.2026 hieß es an
    # ``zweigaengig.step`` „kein Normmaß, nächstes M8", und träfen Durchmesser
    # und Teilung zufällig eine Tabellengröße, entstünde still ein eingängiges
    # Gegengewinde, das nicht greift.
    starts = feature.params.get("starts", 1)
    if isinstance(starts, int | float) and not isinstance(starts, bool) and starts > 1:
        raise ValidationError(
            field="at_feature",
            detail=_(
                "Ein mehrgängiges Gewinde hat kein Gegenstück aus der Bibliothek — deren "
                "Gewinde sind eingängig."
            ),
            value=feature.id,
            values={"feature": feature.id, "starts": int(starts)},
            constraint="multi_start",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    # **Und ebenso wenig zu einem kegeligen.** Das Bibliotheksgewinde ist
    # zylindrisch; sein Gegenstück zu einem kegeligen Rohrgewinde hätte einen
    # festen Durchmesser — beide Teile hätten gepasst, bis jemand sie
    # zusammenschraubt (P2.5, 22.09.2026).
    if thread_is_tapered(feature):
        raise ValidationError(
            field="at_feature",
            detail=_(
                "Ein Gegenstück aus der Bibliothek ist zylindrisch. Zu einem kegeligen "
                "Gewinde passt es nicht."
            ),
            value=feature.id,
            constraint="thread_shape",
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    length = float(feature.params.get("length", 0.0))
    params: dict[str, Any] = {
        **thread_values_for(feature),
        "internal": not bool(feature.params.get("internal", False)),
        **dict(second_place),
    }
    if length > 0.0:
        params["length"] = length
    return OperationDraft(op="insert_printed_thread", inputs=(second_object,), params=params)


def apply_thread_counterpart(
    document: Document,
    feature: Feature,
    first_object: ObjectId,
    second_object: ObjectId,
    second_place: Mapping[str, Any],
    *,
    origin: Origin | None = None,
) -> CounterpartApplied:
    """Setzt das Gegenstück zu einem vorhandenen Gewinde — ein Schritt, eine Transaktion.

    Wie :func:`apply_counterpart`, nur dass die erste Hälfte schon steht: Es
    entsteht ein Bausteingewinde am zweiten Teil, und :func:`attach_thread_fit`
    hängt danach die Passung zwischen dem vorhandenen und dem neuen Gewinde an
    dieselbe Transaktion.
    """
    if first_object == second_object:
        raise ValidationError(
            field="second_object",
            detail=_(
                "Ein Gegenstück braucht zwei verschiedene Teile — Stift und Bohrung "
                "im selben Körper wären ein Loch neben einem Zapfen."
            ),
            value=str(second_object),
            constraint="same_object",
            suggestions=(CORRECT_INPUT,),
        )
    draft = thread_counterpart_draft(feature, second_object, second_place)
    history = History(document)
    applied = history.apply(_("Gegenstück zum Gewinde"), [draft], origin or Origin(by="user"))
    step = document.ops[-1]
    made = [step.outputs[0]] if step.outputs else []
    _log.info("thread counterpart for %s/%s: %s", first_object, feature.id, ", ".join(made) or "?")
    note = thread_size_note(feature)
    return CounterpartApplied(
        object_ids=[first_object, *made],
        op_ids=(step.id,),
        transaction=applied.id,
        findings=[note] if note is not None else [],
    )


def attach_thread_fit(
    document: Document, applied: CounterpartApplied, feature: Feature, scene: Scene
) -> CounterpartApplied:
    """Die Passung zwischen dem vorhandenen Gewinde und dem neuen — nach der Auswertung."""
    if len(applied.object_ids) < 2 or not applied.op_ids:
        _log.info("thread counterpart: %d output(s), no fit", len(applied.object_ids))
        return applied
    last = document.transactions[-1] if document.transactions else None
    if last is None or last.id != applied.transaction:
        applied.findings.append(
            Finding(
                code="parts.counterpart_unpaired",
                severity="warning",
                message=_(
                    "Der Verlauf hat sich seit dem Einsetzen geändert, deshalb fehlt die "
                    "Passung. Rechts unter Auswahl lässt sie sich nachtragen."
                ),
                values={"pair": "thread"},
            )
        )
        return applied
    first_object, second_object = applied.object_ids[0], applied.object_ids[1]
    made = _made_feature(scene, second_object, applied.op_ids[0], "printed_thread", "thread")
    existing = scene.objects.get(first_object)
    if made is None or existing is None or feature.id not in existing.features:
        applied.findings.append(
            Finding(
                code="parts.counterpart_unpaired",
                severity="info",
                message=_(
                    "Ein Merkmal ist unter seinem Namen nicht zu finden, deshalb fehlt die "
                    "Passung. Rechts unter Auswahl lässt sie sich nachtragen."
                ),
                values={"pair": "thread"},
            )
        )
        return applied
    fit = Fit(
        name=numbered_name(document.fits, "thread"),
        a=FeatureRef(first_object, feature.id),
        b=FeatureRef(second_object, made),
        kind="thread",
        tolerance="auto:",
    )
    changes = change_for(document, fits=[*document.fits, fit])
    document.transactions[-1] = dataclasses.replace(last, changes=changes)
    document.fits.append(fit)
    applied.fit = fit if fit in active_fits(document) else None
    applied.findings.append(
        Finding(
            code="parts.counterpart_fit",
            severity="info",
            message=_(
                "Beide Hälften sind als Passung eingetragen — sie werden zusammen "
                "geprüft, und der Slicer bekommt dafür die genauere Außenwand."
            ),
            values={"fit": fit.name, "tolerance": str(fit.tolerance)},
        )
    )
    _log.info("thread counterpart: %s ↔ %s as fit %s", feature.id, made, fit.name)
    return applied


def coupled_thread_drafts(
    document: Document,
    scene: Scene,
    profile: Profile,
    object_id: ObjectId,
    params: Mapping[str, Any],
) -> tuple[OperationDraft, ...]:
    """Die Schritte am Gegengewinde, wenn ein Gewinde in einer Passung sein Maß ändert.

    *Merkmal ändern* an einem Gewinde (``resize_feature``) ändert genau ein
    Teil. Steht das Gewinde in einer aktiven Gewindepassung, passt die andere
    Hälfte danach nicht mehr — die Schraube greift nicht in die größere Mutter,
    und der Prüfbericht meldet es erst hinterher. Deshalb geht die andere
    Hälfte mit, **in derselben Transaktion**: dieselbe Steigung, und der
    Durchmesser, den die Passung verlangt (``fits.target`` — das Spiel aus dem
    Material des Lochs, §12). Innen das Spiel weiter, außen enger. Gefragt
    wird das Spiel für zwei Gewinde, die so gebaut sind, wie sie dastehen
    (``as_stated``): Genau so setzt *Merkmal ändern* beide Hälften.

    Kein Schritt, wo nichts gekoppelt ist: kein Gewinde, keine Passung, eine
    Passung, die sich nicht messen lässt (die meldet der Prüfbericht selbst),
    oder ein Gegenstück, das schon das verlangte Maß hat.
    """
    from app.core.scene.fits import resolve, target

    entry = scene.objects.get(object_id)
    feature_id = str(params.get("at_feature", ""))
    feature = entry.features.get(feature_id) if entry is not None else None
    if feature is None or feature.kind != "thread":
        return ()
    # Ein Ausdruck (``=@gewinde``) steht erst nach der Auswertung fest; dann
    # koppelt nichts, und die Passungsprüfung meldet, was nicht mehr passt.
    named_diameter, named_pitch = params.get("diameter"), params.get("pitch", 0.0)
    if not isinstance(named_diameter, int | float) or not isinstance(named_pitch, int | float):
        return ()
    diameter = float(named_diameter)
    pitch = float(named_pitch) or float(feature.params.get("pitch", 0.0))
    if diameter <= 0.0 or pitch <= 0.0:
        return ()
    own = FeatureRef(object_id, feature_id)
    drafts: list[OperationDraft] = []
    for fit in active_fits(document):
        if fit.kind != "thread" or own not in (fit.a, fit.b):
            continue
        other_ref = fit.b if fit.a == own else fit.a
        other = resolve(scene, other_ref)
        if other is None or other.kind != "thread" or other_ref.object_id == object_id:
            continue
        try:
            wanted, _materials = target(scene, fit, profile, as_stated=True)
        except ValueError:
            continue
        inner = bool(feature.params.get("internal", False))
        partner = diameter - wanted if inner else diameter + wanted
        if is_close(partner, float(other.params.get("diameter", 0.0))) and is_close(
            pitch, float(other.params.get("pitch", 0.0))
        ):
            continue
        drafts.append(
            OperationDraft(
                op="resize_feature",
                inputs=(other_ref.object_id,),
                params={"at_feature": other_ref.feature_id, "diameter": partner, "pitch": pitch},
            )
        )
    return tuple(drafts)


def with_coupled_threads(
    document: Document, scene: Scene, profile: Profile, drafts: Sequence[OperationDraft]
) -> list[OperationDraft]:
    """Die Entwürfe, ergänzt um das Gegengewinde jedes geänderten Gewindes.

    Die eine Stelle für Fenster (Vorschau und Übernehmen) und Kommandozeile.
    Ein Gegenstück, das schon ein eigener Entwurf ändert, bleibt bei dessen
    Werten; keines kommt zweimal.
    """
    targeted = {
        (draft.inputs[0], draft.params.get("at_feature"))
        for draft in drafts
        if draft.op == "resize_feature" and draft.inputs
    }
    coupled: list[OperationDraft] = []
    for draft in drafts:
        if draft.op != "resize_feature" or len(draft.inputs) != 1:
            continue
        for partner in coupled_thread_drafts(
            document, scene, profile, draft.inputs[0], draft.params
        ):
            key = (partner.inputs[0], partner.params.get("at_feature"))
            if key not in targeted:
                targeted.add(key)
                coupled.append(partner)
    return [*drafts, *coupled]


@dataclass(frozen=True, slots=True)
class StepCoupling:
    """Was am Gegengewinde mitgeht, wenn ein gespeicherter Gewindeschritt sich ändert.

    ``edits`` nennt je Schritt des Gegenstücks seine vollständigen neuen Werte,
    ``drafts`` die Schritte, die neu ans Ende kommen — beides geht mit der
    Änderung in **eine** Transaktion (``History.change_params``).
    """

    edits: dict[OpId, dict[str, Any]]
    drafts: tuple[OperationDraft, ...] = ()


def coupled_step_change(
    document: Document,
    scene: Scene,
    profile: Profile,
    op_id: OpId,
    params: Mapping[str, Any],
) -> StepCoupling | None:
    """Das Gegengewinde einer Gewindepassung, wenn ein bestehender Gewindeschritt sich ändert.

    Das Gegenstück zu :func:`with_coupled_threads` für den gespeicherten
    Schritt (*Diesen Schritt ändern*, Verlauf, Merkmalfenster): Ohne es
    entstünde still eine Passung, die nicht mehr passt (Regel 21). Zwei Arten
    von Gewindeschritten:

    * **Gedrucktes Gewinde** (``insert_printed_thread``) mit neuer Größe: Ist
      das Gegengewinde ebenfalls ein gedrucktes Gewinde und danach nicht mehr
      geändert worden, bekommt es dieselbe Größe — die Tabelle oder dasselbe
      eigene Maß hält beide Hälften zusammen (:func:`_printed_size`).
    * **Merkmal ändern** am Gewinde: Der Partnerschritt am Gegenstück (der
      zuletzt gesetzte, bevorzugt aus derselben Transaktion) bekommt die
      Steigung und den Durchmesser, den die Passung verlangt; gibt es keinen,
      kommt einer ans Ende.

    Gekoppelt wird nur, wo der geänderte Schritt das Gewinde am Ende bestimmt —
    ändert ein späterer Schritt es noch einmal, gälte die Kopplung einem Maß,
    das es so nicht gibt. Gefragt wird an der zuletzt gerechneten Szene, denn
    Passungen nennen die Merkmale des Endstands.
    """
    from app.core.scene.fits import resolve, target

    entry = next((step for step in document.ops if step.id == op_id), None)
    if entry is None or len(entry.inputs) != 1:
        return None
    new = {**entry.params, **params}
    body = entry.inputs[0]
    if entry.op == "resize_feature":
        own = FeatureRef(body, str(new.get("at_feature", "")))
    elif entry.op == "insert_printed_thread" and not _same_printed_size(new, entry.params):
        made = scene.objects.get(body)
        name = next(
            (
                key
                for key, feature in (made.features.items() if made is not None else ())
                if feature.kind == "thread" and feature.created_by == op_id
            ),
            None,
        )
        if name is None:
            return None
        own = FeatureRef(body, name)
    else:
        return None
    if _later_resizes(document, own, after=op_id):
        return None
    own_feature = resolve(scene, own)
    if own_feature is None or own_feature.kind != "thread":
        return None

    edits: dict[OpId, dict[str, Any]] = {}
    drafts: list[OperationDraft] = []
    for fit in active_fits(document):
        if fit.kind != "thread" or own not in (fit.a, fit.b):
            continue
        other = fit.b if fit.a == own else fit.a
        partner = resolve(scene, other)
        if partner is None or partner.kind != "thread":
            continue
        resizes = _later_resizes(document, other, after=0)
        if entry.op == "insert_printed_thread":
            creator = next((step for step in document.ops if step.id == partner.created_by), None)
            if not resizes and creator is not None and creator.op == entry.op:
                edits[creator.id] = {
                    **creator.params,
                    **{key: new[key] for key in _PRINTED_SIZE_FIELDS if key in new},
                }
            continue
        diameter, pitch = new.get("diameter"), new.get("pitch", 0.0)
        if not isinstance(diameter, int | float) or not isinstance(pitch, int | float):
            continue
        pitch = float(pitch) or float(own_feature.params.get("pitch", 0.0))
        try:
            wanted, _materials = target(scene, fit, profile, as_stated=True)
        except ValueError:
            continue
        inner = bool(own_feature.params.get("internal", False))
        values = {
            "at_feature": other.feature_id,
            "diameter": float(diameter) - wanted if inner else float(diameter) + wanted,
            "pitch": pitch,
        }
        if resizes:
            together = _transaction_of(document, op_id)
            chosen = next((step for step in resizes if step.id in together), resizes[-1])
            edits[chosen.id] = {**chosen.params, **values}
        else:
            drafts.append(
                OperationDraft(op="resize_feature", inputs=(other.object_id,), params=values)
            )
    return StepCoupling(edits, tuple(drafts)) if edits or drafts else None


#: Die Felder, die das Maß eines gedruckten Gewindes bestimmen.
_PRINTED_SIZE_FIELDS: Final = ("size", "diameter", "pitch")


def _printed_size(params: Mapping[str, Any]) -> tuple[Any, ...]:
    """Was an einem gedruckten Gewinde das Maß bestimmt.

    Die Größe, beim eigenen Maß dazu Durchmesser und Steigung — an einer
    Tabellengröße ändern die beiden Felder nichts, und ein Schritt, der nur sie
    ändert, ist keiner, den das Gegenstück mitmachen müsste.
    """
    from app.core.knowledge.parts.fasteners import CUSTOM_SIZE

    size = params.get("size")
    if size != CUSTOM_SIZE:
        return (size,)
    return (size, params.get("diameter"), params.get("pitch", 0.0))


def _same_printed_size(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    """Ob zwei Parametersätze dasselbe Gewindemaß bauen — Zahlen nie mit ``==`` (Regel 6).

    Ø 66,6 und 66,6 + 10⁻¹² sind dasselbe Maß; mit ``!=`` über das Tupel
    koppelte der zweite Schritt den Partner, der danach gleich blieb.
    """
    left, right = _printed_size(first), _printed_size(second)
    if len(left) != len(right) or left[0] != right[0]:
        return False
    return all(
        is_close(float(a), float(b))
        if isinstance(a, int | float) and isinstance(b, int | float)
        else a == b
        for a, b in zip(left[1:], right[1:], strict=True)
    )


def _later_resizes(document: Document, ref: FeatureRef, *, after: OpId) -> list[Operation]:
    """Die *Merkmal ändern*-Schritte an diesem Gewinde nach ``after``, in Stapelfolge."""
    return [
        step
        for step in document.ops
        if step.id > after
        and step.op == "resize_feature"
        and step.suppressed is None
        and step.inputs == (ref.object_id,)
        and step.params.get("at_feature") == ref.feature_id
    ]


def _transaction_of(document: Document, op_id: OpId) -> tuple[OpId, ...]:
    """Die Schritte der Transaktion, die diesen Schritt angelegt hat."""
    return next((entry.ops for entry in document.transactions if op_id in entry.ops), (op_id,))


def _made_feature(
    scene: Scene, object_id: ObjectId, op_id: OpId, part: str, wanted: str
) -> str | None:
    """Die Kennung des Merkmals, das dieser Schritt an diesem Körper erzeugt hat.

    Gesucht wird über zwei Angaben zusammen: die Herkunft (``created_by``, also
    der Schritt) und den Namen. Die Herkunft allein genügt nicht — ein Baustein
    bringt mehrere Merkmale mit (die Passbohrung ihre Fase, das Schraubenloch
    seine Senkung), und gemeint ist genau eines.

    **Der Name ist nicht durchnummeriert, sondern angehängt.** Gemessen an zwei
    Paaren nacheinander: Der erste Stift heißt ``dowel_pin_1``, der zweite
    ``dowel_pin_1_2`` — ``evaluate._renamed`` hängt an den ganzen bisherigen
    Namen an, statt seine Zahl hochzuzählen. Eine Suche nach dem Stamm ohne die
    letzte Zahl trifft damit ``dowel_pin_1`` und nicht ``pin``, und das zweite
    Paar bliebe ohne Passung: Der erste Anlauf hier hat genau das getan.

    Verglichen wird deshalb am **Anfang** des Namens, mit dem Trennstrich
    dahinter — mit Bausteinpräfix, wie die Bibliothek es vergibt, und ohne, für
    den Fall, dass ein Baustein sein Merkmal selbst schon so benennt.
    """
    entry = scene.objects.get(object_id)
    if entry is None:
        return None
    stems = (f"{part}_{wanted}", wanted)
    found = [
        (name, feature)
        for name, feature in entry.features.items()
        if feature.created_by == op_id
        and any(name == stem or name.startswith(f"{stem}_") for stem in stems)
    ]
    # **Das erzeugte Merkmal, nicht das daneben erkannte.** Ein gedrucktes
    # Gewinde am Netz trägt neben dem Merkmal des Bausteins auch das, was die
    # Erkennung über denselben Gängen liest — gleicher Schritt, gleicher
    # Stamm, gemessene Zahlen statt der gesetzten (P2.6, 21.09.2026).
    for name, feature in found:
        if feature.provenance == "generated":
            return name
    return found[0][0] if found else None
