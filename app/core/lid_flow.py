"""Deckel erzeugen als Ablauf, nicht als einzelne Operation (Bauplan §14, §25).

Die Operation baut den Körper. Was ihr fehlte, ist das Paar: ein Deckel und
die Schachtel, in die er gehört, sind eine **Passung** — und die lebt im
Dokument, nicht in der Geometrie (§14). Ohne sie greifen die drei Regeln aus
``slice/advise.py`` nie, die genau für Passungen da sind: genaue Außenwand,
gebremste Beschleunigung, Bügeln. Ausgerechnet am Deckel, wo das Zusammenspiel
der Zweck ist, druckte Solidon also wie an jeder beliebigen Wand.

**Warum ein Ablauf und nicht die Operation selbst.** Eine Op bekommt ihre
Szene nur lesend (Regel 3), und die Auswertung ist eine reine Funktion
(§15.1): sie darf keine Passung ins Dokument schreiben, sonst käme bei jedem
Neurechnen eine dazu. Der Ablauf steht deshalb daneben, wie
``split.apply_split`` beim Verstiften — er wendet die Operation an und trägt
die Passung in derselben Transaktion ein, die auch die Geometrie gebracht hat.
Ein Undo nimmt beides zusammen zurück.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.geom.lid import (
    CAP_THREAD_FEATURE,
    CAVITY_FEATURE,
    COLLAR_FEATURE,
    NECK_THREAD_FEATURE,
)
from app.core.log import get_logger
from app.core.scene.fits import active_fits
from app.core.scene.history import ChangeFn, History, OperationDraft, change_for
from app.core.types import (
    AUTO_TOLERANCE_PREFIX,
    Document,
    DocumentChange,
    FeatureRef,
    Finding,
    Fit,
    ObjectId,
    Operation,
    Origin,
    Parameter,
    ParamSpec,
    TransactionId,
)
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Wie die Passung heißt, wenn sie die erste ihres Namens ist.
FIT_NAME = "deckel"


@dataclass(slots=True)
class LidApplied:
    """Was der Ablauf hinterlassen hat."""

    object_ids: list[ObjectId] = field(default_factory=list)
    fit: Fit | None = None
    transaction: TransactionId | None = None
    findings: list[Finding] = field(default_factory=list)


def unique_name(document: Document, wanted: str = FIT_NAME) -> str:
    """Ein Name, den es im Dokument noch nicht gibt.

    Eine Schachtel mit zwei Fächern bekommt zwei Deckel, und zwei Passungen
    desselben Namens wären eine, die die andere verdeckt.
    """
    return _unused_name(document.fits, wanted)


def _unused_name(fits: Sequence[Fit], wanted: str) -> str:
    taken = {fit.name for fit in fits}
    if wanted not in taken:
        return wanted
    number = 2
    while f"{wanted}_{number}" in taken:
        number += 1
    return f"{wanted}_{number}"


def fit_for_lid(operation: Operation, existing: Sequence[Fit]) -> Fit:
    """Die gemeinsame Beziehung für den Ablauf und belegte alte Deckelschritte.

    Die Toleranz nennt kein Material (``auto:``): Kragen und Gewinde rechnen
    ihr Spiel aus dem Material, in dem Dose und Deckel gedruckt werden, und
    die Passung prüft gegen dasselbe. Bis zur Durchsicht 0.5.0 stand hier das
    Projektmaterial des Augenblicks, und ein späterer Materialwechsel machte
    aus einem passenden Deckel einen verletzten.
    """
    threaded = operation.op == "screw_lid"
    return Fit(
        name=_unused_name(existing, FIT_NAME),
        a=FeatureRef(operation.outputs[0], NECK_THREAD_FEATURE if threaded else CAVITY_FEATURE),
        b=FeatureRef(operation.outputs[1], CAP_THREAD_FEATURE if threaded else COLLAR_FEATURE),
        kind="clearance",
        tolerance=AUTO_TOLERANCE_PREFIX,
        when_positive=None if threaded else (operation.id, "collar"),
    )


def apply_lid(
    document: Document,
    object_id: ObjectId,
    params: dict[str, object],
    *,
    op: str = "create_lid",
    origin: Origin | None = None,
) -> LidApplied:
    """Erzeugt den Deckel und hält ihn als Passung fest (§14).

    Die Toleranz ist ein Verweis ins Materialprofil und nie die Zahl selbst
    (Regel 7) — dieselbe Entscheidung wie beim Verstiften, und aus demselben
    Grund: eine Kalibrierung nach §28.3 muss einen Deckel erreichen, der vor
    ihr entstanden ist.
    """
    history = History(document)
    title = _("Drehdeckel erzeugen") if op == "screw_lid" else _("Deckel erzeugen")
    applied = history.apply(
        title,
        [OperationDraft(op=op, inputs=(object_id,), params=dict(params))],
        origin or Origin(by="user"),
    )

    made = document.ops[-1].outputs
    if len(made) < 2:
        # Die Operation hat keinen zweiten Körper geliefert — dann gibt es
        # nichts zu paaren, und ein Fit ins Leere wäre schlimmer als keiner.
        _log.info("lid flow: the operation produced %d output(s), no fit", len(made))
        return LidApplied(object_ids=list(made), transaction=applied.id)

    box_id, lid_id = made[0], made[1]
    fit = fit_for_lid(document.ops[-1], document.fits)
    # Die Passung gehört in dieselbe Transaktion wie die Geometrie: sie ist
    # keine Operation, also reist sie als DocumentChange mit (§15.5). Ohne das
    # ließe ein Undo den Deckel verschwinden und die Passung stehen — sie
    # zeigte dann auf ein Objekt, das es nicht mehr gibt.
    #
    # Nachgetragen und nicht mitgegeben, weil erst der Verlauf die Objekt-IDs
    # vergibt: vor ``apply`` gibt es nichts, worauf ein ``FeatureRef`` zeigen
    # könnte.
    changes = change_for(document, fits=[*document.fits, fit])
    document.fits.append(fit)
    document.transactions[-1] = dataclasses.replace(applied, changes=changes)

    _log.info("lid flow: %s ↔ %s as fit %s", box_id, lid_id, fit.name)
    return LidApplied(
        object_ids=list(made),
        fit=fit if fit in active_fits(document) else None,
        transaction=applied.id,
        findings=[
            Finding(
                code="parts.lid_fit",
                severity="info",
                message=_(
                    "Deckel und Schachtel sind als Passung eingetragen — "
                    "der Slicer bekommt dafür die genauere Außenwand."
                ),
                values={"fit": fit.name, "tolerance": str(fit.tolerance)},
            )
        ]
        if fit in active_fits(document)
        else [],
    )


__all__ = [
    "FIT_NAME",
    "ContainerEdit",
    "ContainerPlan",
    "LidApplied",
    "apply_lid",
    "change_for_container_edit",
    "fit_for_container",
    "fit_for_lid",
    "plan_container",
    "plan_container_edit",
    "unique_name",
]


@dataclass(frozen=True, slots=True)
class ContainerPlan:
    """Ein reiner Entwurf; erst History.apply veröffentlicht Maße, Körper und Passung."""

    title: TranslatableText | str
    drafts: tuple[OperationDraft, ...]
    parameters: Mapping[str, Parameter]
    changes: ChangeFn
    document_change: DocumentChange


@dataclass(frozen=True, slots=True)
class ContainerEdit:
    """Werte und Begleitänderung eines historischen Behälterschritts, gemeinsam übernehmen."""

    values: Mapping[str, Any]
    document_change: DocumentChange


def _container_dimensions(values: Mapping[str, Any]) -> tuple[ParamSpec, ...]:
    """Nur wirksame Hauptmaße werden automatisch zu Projektparametern."""
    from app.core.geom.container_ops import ContainerParams
    from app.core.registry.params import inactive_dependency

    schema = ContainerParams.spec()
    return tuple(
        spec
        for spec in schema
        if spec.unit == "mm"
        and spec.placement == "front"
        and inactive_dependency(spec, schema, values) is None
    )


def plan_container(document: Document, values: Mapping[str, Any]) -> ContainerPlan:
    """Den Behälter-Assistenten als eine Transaktion mit benannten Hauptmaßen planen.

    Die Vorlage wird nicht verändert. Ausdrücke bleiben als Abhängigkeiten
    der neuen Projektmaße erhalten. Neue Kennungen werden auf einer Kopie
    geplant; eine inzwischen geänderte Szene lehnt History ausdrücklich ab.
    """
    import copy

    from app.core import expressions
    from app.core.brep.kernel import available
    from app.core.geom.container_ops import (
        ContainerInsertParams,
        ContainerWizardParams,
    )
    from app.core.registry.params import validate

    resolved = expressions.resolve_params(values, expressions.resolve(document.parameters))
    params = validate(ContainerWizardParams, resolved)
    raw = params.as_dict()
    raw.update(
        (name, value)
        for name, value in values.items()
        if name in raw and expressions.is_expression(value)
    )
    raw.pop("insert")
    if raw["kernel"] == "auto":
        raw["kernel"] = "brep" if available() else "mesh"
    suffix = ""
    number = 1
    while any(name.startswith(f"container{suffix}_") for name in document.parameters):
        number += 1
        suffix = f"_{number}"
    parameters: dict[str, Parameter] = {}
    for spec in _container_dimensions(params.as_dict()):
        name = f"container{suffix}_{spec.name}"
        original = values.get(spec.name)
        parameters[name] = Parameter(
            name=name,
            value=float(getattr(params, spec.name)),
            title=spec.title,
            minimum=spec.minimum,
            maximum=spec.maximum,
            expression=str(original) if expressions.is_expression(original) else None,
        )
        raw[spec.name] = f"=@{name}"
    divisions = {name: raw[name] for name in ("rows", "columns")}
    if params.insert:
        raw.update(rows=1, columns=1)
    scratch = copy.deepcopy(document)
    history = History(scratch)
    history.apply(
        _("Behälter mit Deckel"),
        [OperationDraft("create_container", params=raw)],
        changes=change_for(scratch, parameters=parameters),
    )
    first = scratch.ops[-1]
    drafts = [OperationDraft(first.op, params=raw, outputs=tuple(first.outputs), seed=first.seed)]
    if params.insert:
        inserted = {
            spec.name: raw.get(spec.name, getattr(params, spec.name, spec.default))
            for spec in ContainerInsertParams.spec()
        }
        inserted.update(divisions)
        draft = OperationDraft("add_container_insert", inputs=tuple(first.outputs), params=inserted)
        history.apply(_("Einsatz"), [draft])
        drafts.append(
            dataclasses.replace(
                draft, outputs=tuple(scratch.ops[-1].outputs), seed=scratch.ops[-1].seed
            )
        )

    def changes(operations: Sequence[Operation]) -> DocumentChange:
        fit = fit_for_container(operations[0], document.fits)
        return change_for(document, parameters=parameters, fits=[*document.fits, fit])

    return ContainerPlan(
        _("Behälter mit Deckel"),
        tuple(drafts),
        parameters,
        changes,
        changes(scratch.ops[-len(drafts) :]),
    )


def fit_for_container(operation: Operation, existing: Sequence[Fit]) -> Fit:
    """Das Passungspaar der aktuellen Deckelart, aus den echten Ausgabekennungen."""
    from app.core.geom.container_ops import HINGE_HOLE_FEATURE, HINGE_PIN_FEATURE

    pairs = {
        "screw": (NECK_THREAD_FEATURE, CAP_THREAD_FEATURE),
        "push": (CAVITY_FEATURE, COLLAR_FEATURE),
        "hinged": (HINGE_PIN_FEATURE, HINGE_HOLE_FEATURE),
    }
    lid = str(operation.params.get("lid", "screw"))
    left, right = pairs[lid]
    old = next((fit for fit in existing if _belongs_to_container(fit, operation)), None)
    return Fit(
        name=old.name if old is not None else _unused_name(existing, FIT_NAME),
        a=FeatureRef(operation.outputs[0], left),
        b=FeatureRef(operation.outputs[1], right),
        kind=old.kind if old is not None else "clearance",
        tolerance=old.tolerance if old is not None else AUTO_TOLERANCE_PREFIX,
        when_positive=(operation.id, "collar") if lid == "push" else None,
    )


def _belongs_to_container(fit: Fit, operation: Operation) -> bool:
    from app.core.geom.container_ops import HINGE_HOLE_FEATURE, HINGE_PIN_FEATURE

    return (
        len(operation.outputs) >= 2
        and fit.a.object_id == operation.outputs[0]
        and fit.b.object_id == operation.outputs[1]
        and (fit.a.feature_id, fit.b.feature_id)
        in (
            (NECK_THREAD_FEATURE, CAP_THREAD_FEATURE),
            (CAVITY_FEATURE, COLLAR_FEATURE),
            (HINGE_PIN_FEATURE, HINGE_HOLE_FEATURE),
        )
    )


def change_for_container_edit(
    document: Document, operation: Operation, values: Mapping[str, Any]
) -> DocumentChange:
    """Den Wechsel der Deckelart mit seiner bestehenden Passung gemeinsam zurücknehmen.

    Für `History.change_params(..., changes=...)` und denselben Vorschauweg.
    Fremde Passungen bleiben unverändert; Namen und Kundentoleranzen des
    Behälterpaars erhalten sich. Der Einsatz liest beide Körper als Eingänge
    und folgt dadurch auch einer geänderten Kragentiefe.
    """
    proposed = dataclasses.replace(operation, params={**operation.params, **values})
    fits = [
        fit_for_container(proposed, (fit,)) if _belongs_to_container(fit, operation) else fit
        for fit in document.fits
    ]
    if not any(_belongs_to_container(fit, operation) for fit in document.fits):
        fits.append(fit_for_container(proposed, fits))
    change = change_for(document, fits=fits)
    old_inserts: dict[int, Operation] = {}
    new_inserts: dict[int, Operation] = {}
    shared = ("shape", "diameter", "width", "depth", "height", "wall", "floor", "radius")
    for entry in document.ops:
        if entry.op != "add_container_insert" or tuple(entry.inputs) != tuple(operation.outputs):
            continue
        # Nur weiterhin gekoppelte Werte folgen dem Behälter. Ein vom Kunden
        # eigens überschriebenes Einsatzmaß bleibt seine eigene Entscheidung.
        followed = {
            name: proposed.params[name]
            for name in shared
            if name in proposed.params and entry.params.get(name) == operation.params.get(name)
        }
        updated = {**entry.params, **followed}
        if updated != entry.params:
            old_inserts[entry.id] = entry
            new_inserts[entry.id] = dataclasses.replace(entry, params=updated)
    return dataclasses.replace(
        change,
        before=dataclasses.replace(change.before, edited_ops=old_inserts or None),
        after=dataclasses.replace(change.after, edited_ops=new_inserts or None),
    )


def plan_container_edit(
    document: Document, operation: Operation, values: Mapping[str, Any]
) -> ContainerEdit:
    """Neu wirksame Hauptmaße samt Passung und Einsatz in einer Transaktion planen.

    Bereits benannte Maße und manuelle Ausdrücke behalten ihre Bindung. Alte
    Projektparameter werden weder gelöscht noch überschrieben; Namenskollisionen
    bekommen einen freien Namen. Die geplanten ``values`` gehören zusammen mit
    ``document_change`` in Vorschau und ``History.change_params``.
    """
    import re

    from app.core import expressions
    from app.core.geom.container_ops import ContainerParams
    from app.core.registry.params import validate

    known = expressions.resolve(document.parameters)
    raw = {**operation.params, **values}
    params = validate(ContainerParams, expressions.resolve_params(raw, known))
    previous = validate(ContainerParams, expressions.resolve_params(operation.params, known))
    raw = {**params.as_dict(), **raw}
    earlier = {spec.name for spec in _container_dimensions(previous.as_dict())}
    prefix = "container_"
    for spec in _container_dimensions(previous.as_dict()):
        found = re.fullmatch(
            r"=@(container(?:_\d+)?_)" + re.escape(spec.name),
            str(operation.params.get(spec.name, "")),
        )
        if found is not None:
            prefix = found.group(1)
            break
    parameters: dict[str, Parameter] = {}
    for spec in _container_dimensions(params.as_dict()):
        if spec.name in earlier or expressions.is_expression(raw[spec.name]):
            continue
        base = f"{prefix}{spec.name}"
        name, number = base, 1
        while name in document.parameters or name in parameters:
            number += 1
            name = f"{base}_{number}"
        parameters[name] = Parameter(
            name=name,
            value=float(getattr(params, spec.name)),
            title=spec.title,
            minimum=spec.minimum,
            maximum=spec.maximum,
        )
        raw[spec.name] = f"=@{name}"
    change = change_for_container_edit(document, operation, raw)
    if parameters:
        dimensions = change_for(document, parameters=parameters)
        change = dataclasses.replace(
            change,
            before=dataclasses.replace(change.before, parameters=dimensions.before.parameters),
            after=dataclasses.replace(change.after, parameters=dimensions.after.parameters),
        )
    return ContainerEdit(raw, change)
