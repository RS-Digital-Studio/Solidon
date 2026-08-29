"""Auto Split als Transaktion (Bauplan §25, §14, §22.3).

Die Suche entscheidet, *wo* geschnitten wird; hier entscheidet sich, *was auf
den Stapel kommt*. Eine ``split_pinned``-Operation je Schnitt, in der
Reihenfolge, in der die Suche sie gemacht hat — so bleibt jede Trennebene eine
Zahl, die jemand nachträglich ändern kann, und ein Undo nimmt die ganze
Teilung zurück.

Die Passungspaare entstehen auch hier, und das ist der Grund, warum das nicht
einfach die Operation selbst ist: Passungen leben im Dokument (§14), die
Auswertung ist eine reine Funktion und schreibt nicht hinein (§15.1). Auto
Split ist die Stelle, an der Stift und Bohrung sich treffen, also gehören die
Paare hierher — §14 sagt genau das.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from app.core.geom.autosplit import SplitOutcome, split_to_fit
from app.core.geom.mesh import MeshData
from app.core.geom.pins import PIN_COUNT, feature_side, next_connector_index, plan_pins
from app.core.geom.section import SectionPlane
from app.core.log import get_logger
from app.core.scene.history import History, OperationDraft, change_for
from app.core.types import (
    CancelToken,
    Document,
    Feature,
    FeatureId,
    FeatureRef,
    Finding,
    Fit,
    ObjectId,
    Origin,
    Profile,
    TransactionId,
)
from app.i18n import _

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SplitPlan:
    """Was Auto Split tun würde, bevor irgendetwas angewandt ist."""

    drafts: tuple[OperationDraft, ...]
    outcome: SplitOutcome
    seated: tuple[int, ...] = ()
    """Wie viele Stifte je Schnitt wirklich sitzen — siehe :func:`fitting_pins`.

    Leer heißt: nicht gerechnet, dann gilt die gewünschte Zahl. Das betrifft
    nur von Hand gebaute Pläne in Tests; ``plan_split`` füllt sie immer."""
    connector_start: int = 1
    """Erste freie Verbinderkennung des ausgewählten Ausgangskörpers."""

    @property
    def cuts(self) -> int:
        return len(self.drafts)

    def pins_at(self, index: int, wanted: int) -> int:
        """Die Stiftzahl des ``index``-ten Schnitts, mit der gewünschten als
        Rückfall."""
        return self.seated[index] if index < len(self.seated) else wanted


@dataclass(slots=True)
class SplitApplied:
    """Was es getan hat: die Stücke, die Passungspaare, und was zu melden ist."""

    object_ids: list[ObjectId]
    fits: list[Fit] = field(default_factory=list)
    transaction: TransactionId | None = None
    findings: list[Finding] = field(default_factory=list)


def plan_split(
    mesh: MeshData,
    object_id: ObjectId,
    profile: Profile,
    *,
    features: Mapping[FeatureId, Feature] | None = None,
    pins: int = PIN_COUNT,
    cancelled: CancelToken | None = None,
) -> SplitPlan:
    """Sucht die Schnitte und macht Operationen daraus.

    Die Objekt-IDs, auf die die Schnitte wirken, sind noch nicht bekannt — die
    vergibt der Verlauf. Bekannt ist die *Reihenfolge*, und die genügt: die
    Eingabe des nächsten Schnitts ist eines der zwei Stücke, die der vorige
    gemacht hat.
    """
    outcome = split_to_fit(mesh, profile, pins=pins, cancelled=cancelled)
    drafts = [
        OperationDraft(
            op="split_pinned",
            inputs=(object_id,),
            params={"axis": step.plane.axis, "position": step.plane.position, "pins": pins},
        )
        for step in outcome.cuts
    ]
    return SplitPlan(
        drafts=tuple(drafts),
        outcome=outcome,
        seated=tuple(fitting_pins(step.source, step.plane.plane, pins) for step in outcome.cuts),
        connector_start=next_connector_index(features or {}),
    )


def fitting_pins(
    mesh: MeshData | None, plane: SectionPlane, wanted: int, *, shape: str = "round"
) -> int:
    """Wie viele Stifte an dieser Naht wirklich sitzen werden.

    Nicht dasselbe wie die gewünschte Zahl: Ist die Schnittfläche zu schmal,
    setzt ``plan_pins`` keinen einzigen und sagt das als Befund. Ein
    Passungspaar entstand hier trotzdem — ein `Fit`, dessen beide Seiten auf
    Merkmale zeigen, die es nie gab. Die Passungsprüfung meldet das später als
    Verletzung, und der Nutzer sucht einen Fehler an einem Teil, das in
    Ordnung ist.

    Gerechnet wird dieselbe Planung, die die Operation gleich noch einmal
    macht. Sie ist deterministisch, also stimmen beide Antworten überein; und
    sie kostet einen Querschnitt, während der Schnitt daneben ein ganzes Netz
    zerlegt.

    **Ohne Körper gilt die gewünschte Zahl.** Ist nichts bekannt, ist auch
    nichts widerlegt — und stumm auf null zu gehen wäre kein Vorsichtsmaß,
    sondern der Verlust der Passungen, die es vor dieser Änderung gab. Der
    Fall tritt auf, wenn noch keine Auswertung vorliegt.
    """
    if not wanted:
        return 0
    if mesh is None:
        return wanted
    return plan_pins(mesh, plane, count=wanted, shape=shape).count


def apply_split(
    document: Document,
    mesh: MeshData,
    object_id: ObjectId,
    profile: Profile,
    *,
    features: Mapping[FeatureId, Feature] | None = None,
    pins: int = PIN_COUNT,
) -> SplitApplied:
    """Schneidet, bis es passt, und hält jede Naht als Passungspaar fest (§14)."""
    plan = plan_split(mesh, object_id, profile, features=features, pins=pins)
    return apply_planned(document, plan, object_id, profile, pins=pins)


def apply_planned(
    document: Document,
    plan: SplitPlan,
    object_id: ObjectId,
    profile: Profile,
    *,
    pins: int = PIN_COUNT,
) -> SplitApplied:
    """Wendet einen fertigen Plan an — getrennt vom Suchen.

    Die Suche ist der teure Teil (Schichtanalysen über jede Kandidatenebene)
    und darf abseits des Oberflächen-Threads laufen (§2.8). Das Anwenden
    mutiert das Dokument und gehört in den Thread, dem das Dokument gehört —
    deshalb sind es zwei Funktionen und nicht eine mit einem Schalter.
    """
    if not plan.drafts:
        return SplitApplied(object_ids=[object_id], findings=list(plan.outcome.findings))

    history = History(document)
    pieces: list[ObjectId] = [object_id]
    existing = list(document.fits)  # Passungen aus früheren Transaktionen
    created: list[Fit] = []  # was dieser Lauf angelegt hat und noch lebt
    dropped: list[Fit] = []
    connector_starts: dict[ObjectId, int] = {object_id: plan.connector_start}
    transaction = None

    for index, (step, draft) in enumerate(zip(plan.outcome.cuts, plan.drafts, strict=True)):
        target = pieces[step.part_index]
        # Ein Stück, das ein späterer Schnitt desselben Laufs noch einmal teilt,
        # ist danach zwei — die Passungen, die es benennen, zeigen ins Leere.
        # Sie entfallen, gleich ob sie vor diesem Lauf im Dokument standen oder
        # ein früherer Schnitt sie eben erst angelegt hat. **Beide Listen
        # werden geprüft:** ``change_for`` schreibt die vollständige neue Liste,
        # und eine tote Passung aus dem eigenen Lauf käme sonst über den
        # Akkumulator erneut ins Dokument — der Prüfbericht meldete danach je
        # verwaister Naht ein ``fit.missing_feature`` (§14). Umgehängt wird
        # nichts: der zweite Schnitt vergibt wieder ``pin_1``, ein Verweis
        # darauf zeigte auf einen anderen Stift als gemeint (:func:`_fits_without`).
        existing, gone_old = _partition_fits(existing, target)
        created, gone_new = _partition_fits(created, target)
        dropped.extend(gone_old)
        dropped.extend(gone_new)
        feature_start = connector_starts.pop(target, 1)
        made: list[ObjectId] = []

        # Die Schleifenvariablen wandern als Vorgabewerte hinein: Ein
        # Abschluss, der sie erst beim Aufruf liest, läse den Stand der
        # letzten Runde.
        def change(
            planned: Sequence[Any],
            made: list[ObjectId] = made,
            existing: list[Fit] = existing,
            created: list[Fit] = created,
            seated: int = plan.pins_at(index, pins),
            feature_start: int = feature_start,
        ) -> Any:
            made.extend(planned[0].outputs)
            next_start = feature_start + seated
            connector_starts[made[0]] = next_start
            connector_starts[made[1]] = next_start
            # So viele Paare, wie Stifte sitzen — nicht so viele, wie
            # gewünscht waren. Eine zu schmale Schnittfläche bekommt keinen
            # Stift und deshalb auch keine Passung, die auf ihn zeigt.
            created.extend(
                _pairs(
                    made[0],
                    made[1],
                    seated,
                    profile,
                    len(existing) + len(created),
                    feature_start=feature_start,
                )
            )
            return change_for(document, fits=[*existing, *created])

        applied = history.apply(
            _("Teilen und verstiften"),
            [OperationDraft(op=draft.op, inputs=(target,), params=dict(draft.params))],
            Origin(by="user"),
            changes=change,
        )
        transaction = applied.id
        pieces[step.part_index : step.part_index + 1] = list(made)

    _log.info("split into %d part(s) with %d fit pair(s)", len(pieces), len(created))
    return SplitApplied(
        object_ids=pieces,
        fits=created,
        transaction=transaction,
        findings=[*plan.outcome.findings, *(_fit_dropped(fit) for fit in dropped)],
    )


def apply_line_split(
    document: Document,
    object_id: ObjectId,
    plane: SectionPlane,
    profile: Profile,
    *,
    mesh: MeshData | None = None,
    features: Mapping[FeatureId, Feature] | None = None,
    pins: int = PIN_COUNT,
    shape: str = "round",
) -> SplitApplied:
    """Ein einzelner Schnitt an einer gezeichneten Linie — mit Passungspaaren.

    Warum das nicht die Operation selbst tut, steht im Modulkopf: Passungen
    leben im Dokument, die Auswertung schreibt nicht hinein. Der Unterschied zu
    Auto Split ist nur die Zahl der Schnitte — einer, den jemand gezeigt hat,
    statt so vieler, wie der Bauraum verlangt.

    ``mesh`` ist der Körper, wie die Auswertung ihn zuletzt gerechnet hat. Er
    entscheidet, wie viele Stifte wirklich sitzen (:func:`fitting_pins`) —
    ohne ihn gilt die gewünschte Zahl, und das ist die alte, ungenauere
    Antwort.
    """
    seated = fitting_pins(mesh, plane, pins, shape=shape)
    kept, moving = _partition_fits(list(document.fits), object_id)
    dropped: list[Fit] = []
    if features is None:
        dropped.extend(moving)
        moving = []
    feature_start = next_connector_index(features or {})
    made: list[ObjectId] = []
    fits: list[Fit] = []

    def change(planned: Sequence[Any]) -> Any:
        """Die Passungen dieser Naht — und die, die dabei entfallen.

        In der Transaktion und nicht daneben: Ein Undo, das die Teilung
        zurücknimmt, muss auch die Passungen zurücknehmen, und ein Redo muss
        sie wiederbringen. Gebildet wird das erst hier, weil die Paare die
        Körper benennen, die es beim Aufruf noch nicht gab.
        """
        made.extend(planned[0].outputs)
        remapped, lost = _retarget_fits(
            moving,
            object_id,
            made[0],
            made[1],
            features or {},
            plane,
        )
        dropped.extend(lost)
        surviving = [*kept, *remapped]
        fits.extend(
            _pairs(
                made[0],
                made[1],
                seated,
                profile,
                len(surviving),
                feature_start=feature_start,
            )
        )
        return change_for(document, fits=[*surviving, *fits])

    history = History(document)
    applied = history.apply(
        _("An gezeichneter Linie trennen"),
        [
            OperationDraft(
                op="split_line",
                inputs=(object_id,),
                params={
                    "normal_x": plane.normal[0],
                    "normal_y": plane.normal[1],
                    "normal_z": plane.normal[2],
                    "position": plane.position,
                    "pins": pins,
                    "shape": shape,
                },
            )
        ],
        Origin(by="user"),
        changes=change,
    )
    _log.info("split along a drawn line into %d part(s)", len(made))
    return SplitApplied(
        object_ids=list(made),
        fits=fits,
        transaction=applied.id,
        findings=[_fit_dropped(fit) for fit in dropped],
    )


def _partition_fits(fits: list[Fit], consumed: ObjectId) -> tuple[list[Fit], list[Fit]]:
    """Teilt eine Passungsliste in die, die bleiben, und die, deren Teil
    verschwindet.

    Auto Split braucht sie über die Paare, die es im selben Lauf schon
    angelegt hat; die gezeichnete Teilung hängt die zweite Gruppe anschließend
    anhand ihrer Merkmale um.
    """
    kept = [fit for fit in fits if consumed not in (fit.a.object_id, fit.b.object_id)]
    gone = [fit for fit in fits if consumed in (fit.a.object_id, fit.b.object_id)]
    return kept, gone


def _retarget_fits(
    fits: list[Fit],
    consumed: ObjectId,
    first: ObjectId,
    second: ObjectId,
    features: Mapping[FeatureId, Feature],
    plane: SectionPlane,
) -> tuple[list[Fit], list[Fit]]:
    """Hängt Passungen an das Kindstück, das ihr Merkmal geerbt hat.

    Nur ein Mittelpunkt abseits der Schnittebene ist eindeutig. Fehlt er oder
    wird der Verbinder selbst durchschnitten, entfällt die Passung mit dem
    bestehenden Hinweis — Regel 21 verbietet, eine Seite zu raten.
    """
    kept: list[Fit] = []
    dropped: list[Fit] = []
    for fit in fits:
        refs: list[FeatureRef] = []
        for reference in (fit.a, fit.b):
            if reference.object_id != consumed:
                refs.append(reference)
                continue
            feature = features.get(reference.feature_id)
            side = (
                feature_side(
                    feature,
                    plane,
                    connector=reference.feature_id.startswith(("pin_", "bore_")),
                )
                if feature is not None
                else None
            )
            if side not in (-1, 1):
                break
            refs.append(FeatureRef(first if side == -1 else second, reference.feature_id))
        if len(refs) == 2:
            kept.append(replace(fit, a=refs[0], b=refs[1]))
        else:
            dropped.append(fit)
    return kept, dropped


def _fit_dropped(fit: Fit) -> Finding:
    return Finding(
        code="split.fit_dropped",
        severity="info",
        message=_(
            "Eine Passung ist entfallen — ihr Teil wurde noch einmal geteilt. Die "
            "neuen Nahtstellen haben ihre eigenen."
        ),
        values={"fit": fit.name},
    )


def _pairs(
    first: ObjectId,
    second: ObjectId,
    pins: int,
    profile: Profile,
    made_so_far: int,
    *,
    feature_start: int = 1,
) -> list[Fit]:
    """Ein Paar je Stift: der Stift auf der einen Hälfte, die Bohrung auf der
    anderen.

    Die Toleranz ist ein Verweis ins Materialprofil, nie die Zahl selbst
    (AGENTS.md Regel 7) — eine Kalibrierung danach muss ein Teil erreichen,
    das vor ihr geteilt wurde.
    """
    return [
        Fit(
            name=f"stift_{made_so_far + offset + 1}",
            a=FeatureRef(first, f"pin_{index}"),
            b=FeatureRef(second, f"bore_{index}"),
            kind="clearance",
            tolerance=f"auto:{profile.material.id}",
        )
        for offset, index in enumerate(range(feature_start, feature_start + pins))
    ]
