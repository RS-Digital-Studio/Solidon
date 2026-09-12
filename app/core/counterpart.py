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

from app.core.errors import CORRECT_INPUT, ValidationError
from app.core.log import get_logger
from app.core.scene.fits import active_fits
from app.core.scene.history import History, OperationDraft, change_for
from app.core.types import (
    Document,
    FeatureRef,
    Finding,
    Fit,
    FitKind,
    ObjectId,
    OpId,
    Origin,
    Scene,
    TransactionId,
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
    _log.info("counterpart %s: %s and %s in one transaction", pair.key, *made[:2] or ("?", "?"))
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
                    "und tragen Sie die Passung bei Bedarf im Merkmalfenster ein."
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
                    "finden. Sie lässt sich im Merkmalfenster nachtragen."
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
    for name, feature in entry.features.items():
        if feature.created_by != op_id:
            continue
        if any(name == stem or name.startswith(f"{stem}_") for stem in stems):
            return name
    return None


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
