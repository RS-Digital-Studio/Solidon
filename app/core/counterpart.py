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
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final

from app.core.errors import CANCEL, CHANGE_SELECTION, CORRECT_INPUT, ValidationError
from app.core.knowledge import standards
from app.core.log import get_logger
from app.core.scene.fits import active_fits
from app.core.scene.history import History, OperationDraft, change_for
from app.core.types import (
    Document,
    Feature,
    FeatureRef,
    Finding,
    Fit,
    FitKind,
    ObjectId,
    OpId,
    Origin,
    Scene,
    TransactionId,
    thread_is_left_handed,
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
                    "Der Verlauf hat sich seit dem Einsetzen geändert. Die Passung wurde "
                    "nicht nachgetragen. Prüfen Sie die beiden Hälften im aktuellen Modell "
                    "und tragen Sie die Passung bei Bedarf im Auswahlfenster ein."
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
                    "Die beiden Hälften stehen, eine Passung dazwischen gibt es "
                    "nicht: Eines der Merkmale ist unter seinem Namen nicht zu "
                    "finden. Sie lässt sich im Auswahlfenster nachtragen."
                ),
                values={"pair": pair.key},
            )
        )
        _log.info("counterpart %s: features %s/%s not found", pair.key, first, second)
        return applied

    fit = Fit(
        name=_unused_name(document, pair.key),
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
# Gewinde selbst, und weil das Bausteingewinde nach der Normteiltabelle baut
# (§24.2), muss es ein Tabellenmaß treffen: Ein Gewinde Ø 6,4 mit Steigung 1,1
# wird nicht still zu M6 (Konzept §13.4).

#: Wie nah Durchmesser und Steigung an einem Tabellenmaß liegen müssen —
#: beides deutlich unter dem halben Abstand zweier Nachbargrößen der Tabelle
#: (M2 → M2.5: 0,5 im Durchmesser, 0,05 in der Steigung), damit kein Maß
#: zwei Größen trifft; ``tests/test_thread_counterpart.py`` hält das gegen die
#: Tabelle. Keine Fertigungstoleranz, sondern eine Erkennungsgrenze wie
#: ``units.match_tolerance``.
THREAD_SIZE_REACH: Final = (0.2, 0.02)


def thread_size_for(feature: Feature) -> str:
    """Das Normmaß zu einem Gewinde — oder die Absage, die die nächste Größe nennt."""
    diameter = float(feature.params.get("diameter", 0.0))
    pitch = float(feature.params.get("pitch", 0.0))
    nearest: tuple[float, str] | None = None
    for size in standards.screw_sizes():
        screw = standards.screw(size)
        if (
            abs(screw.nominal - diameter) <= THREAD_SIZE_REACH[0]
            and abs(screw.pitch - pitch) <= THREAD_SIZE_REACH[1]
        ):
            return size
        distance = abs(screw.nominal - diameter) + abs(screw.pitch - pitch)
        if nearest is None or distance < nearest[0]:
            nearest = (distance, size)
    raise ValidationError(
        field="at_feature",
        detail=_(
            "Zu diesem Gewinde passt kein Normmaß aus der Tabelle. "
            "Setzen Sie das Gegenstück als Baustein mit der nächsten Größe."
        ),
        values={
            "feature": feature.id,
            "diameter": diameter,
            "pitch": pitch,
            "nearest": nearest[1] if nearest is not None else "",
        },
        constraint="no_standard_size",
        suggestions=(CHANGE_SELECTION, CANCEL),
    )


def thread_counterpart_draft(
    feature: Feature, second_object: ObjectId, second_place: Mapping[str, Any]
) -> OperationDraft:
    """Der eine Schritt: das gegengleiche Bausteingewinde am anderen Teil, im Tabellenmaß."""
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
    size = thread_size_for(feature)
    length = float(feature.params.get("length", 0.0))
    params: dict[str, Any] = {
        "size": size,
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
    return CounterpartApplied(
        object_ids=[first_object, *made],
        op_ids=(step.id,),
        transaction=applied.id,
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
                    "Der Verlauf hat sich seit dem Einsetzen geändert. Die Passung wurde "
                    "nicht nachgetragen. Prüfen Sie die beiden Hälften im aktuellen Modell "
                    "und tragen Sie die Passung bei Bedarf im Auswahlfenster ein."
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
                    "Die beiden Hälften stehen, eine Passung dazwischen gibt es "
                    "nicht: Eines der Merkmale ist unter seinem Namen nicht zu "
                    "finden. Sie lässt sich im Auswahlfenster nachtragen."
                ),
                values={"pair": "thread"},
            )
        )
        return applied
    fit = Fit(
        name=_unused_name(document, "thread"),
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


def _unused_name(document: Document, key: str) -> str:
    """Ein Passungsname, den es noch nicht gibt.

    Zwei Passungen mit gleichem Namen wären eine, und die zweite Verbindung
    fiele still aus der Prüfung — wer zwei Stifte setzt, hat zwei Paare.
    """
    used = {entry.name for entry in document.fits}
    number = 1
    while f"{key}_{number}" in used:
        number += 1
    return f"{key}_{number}"
