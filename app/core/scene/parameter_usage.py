"""Wo Projektmaße im aktuellen Stapel wirken (Bauplan §13, §15)."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter

from app.core import expressions
from app.core.errors import AppError, ValidationError
from app.core.registry import REGISTRY, Registry
from app.core.registry.params import NUMBER_KINDS
from app.core.types import Document, Operation, OpId, Parameter, ParameterName, ParamSpec
from app.core.units import EPS_GEOM, is_greater, is_less
from app.i18n import _, format_decimal


@dataclass(frozen=True, slots=True)
class ParameterUse:
    """Ein lesendes Operationsfeld, gegebenenfalls über abgeleitete Projektmaße."""

    op_id: OpId
    field: str
    direct: bool = True
    via: tuple[ParameterName, ...] = ()
    """Die am Feld direkt gelesenen Zwischenparameter, die diesen Parameter benötigen."""


def parameter_uses(
    document: Document, registry: Registry | None = None
) -> dict[ParameterName, tuple[ParameterUse, ...]]:
    """Vollständige Verwendungen je Projektmaß; ein leeres Tupel bedeutet ungenutzt.

    Ausgangspunkte sind ausschließlich Felder im aktuellen Operationsstapel.
    Eine Kette benannter Maße ohne solche Leser ist ungenutzt. Jede Fundstelle
    erscheint einmal, in Stapel- und Feldreihenfolge; ``via`` nennt die dort
    direkt gelesenen Zwischenmaße. Die Abfrage ändert das Dokument nicht.

    Ungültige Ausdrücke, unbekannte Operationen und beschädigte Sammelwerte
    werfen ``AppError``. Sie dürfen nicht als sichere Aussage „ungenutzt“
    erscheinen. Skizzen und Stellungen benutzen dieselben Sammler wie der
    Auswertungscache, hier mit strenger Fehlerweitergabe.
    """
    # Erst beim Aufruf: Die Auswertung hält die gemeinsame Zuordnung und kann
    # diese Abfrage so selbst benutzen, ohne einen Importkreis zu schließen.
    from app.core.scene.evaluate import nested_references

    graph = expressions.dependencies(document.parameters)
    defined = set(graph)
    _require_known({name for reads in graph.values() for name in reads}, defined, "parameters")
    try:
        order = tuple(
            TopologicalSorter({name: sorted(graph[name]) for name in sorted(graph)}).static_order()
        )
    except CycleError as problem:
        raise ValidationError(
            field="parameters",
            detail=_("Die Parameter verweisen im Kreis aufeinander."),
            constraint="cycle",
            values={"cycle": problem.args[1]},
        ) from problem

    ancestors: dict[str, set[str]] = {}
    for name in order:
        ancestors[name] = {name}
        for dependency in graph[name]:
            ancestors[name].update(ancestors[dependency])
    found: dict[str, list[ParameterUse]] = {name: [] for name in sorted(defined)}
    source = registry or REGISTRY
    collectors = nested_references(strict=True)
    for operation in document.ops:
        specs = {entry.name: entry for entry in source.get(operation.op).params.spec()}
        for field, value in sorted(operation.params.items()):
            if field not in specs:
                raise ValidationError(
                    field=f"ops.{operation.id}.{field}",
                    detail=_("Diesen Parameter gibt es bei dieser Operation nicht."),
                    constraint="unknown",
                    values={"op": operation.op, "known": sorted(specs)},
                )
            if expressions.is_expression(value):
                direct = expressions.references(value)
            elif collect := collectors.get(specs[field].kind):
                if value is None and specs[field].optional:
                    continue
                if not isinstance(value, str):
                    raise ValidationError(
                        field=f"ops.{operation.id}.{field}",
                        detail=_("Hier wird ein Text erwartet."),
                        constraint="type",
                        value=value,
                    )
                if not value:
                    continue
                direct = collect(value)
            else:
                continue
            _require_known(set(direct), defined, f"ops.{operation.id}.{field}")
            reached: dict[str, set[str]] = {}
            for reader in direct:
                for name in ancestors[reader]:
                    reached.setdefault(name, set()).add(reader)
            for name, readers in reached.items():
                found[name].append(
                    ParameterUse(
                        operation.id,
                        field,
                        direct=name in direct,
                        via=tuple(sorted(readers - {name})),
                    )
                )
    return {name: tuple(uses) for name, uses in found.items()}


def _require_known(references: set[str], defined: set[str], field: str) -> None:
    """Eine fehlende Definition verhindert eine verlässliche Verwendungsabfrage."""
    if missing := references - defined:
        raise ValidationError(
            field=field,
            detail=_("Ein Ausdruck verweist auf einen Parameter, den es nicht gibt."),
            constraint="unknown_parameter",
            values={"missing": sorted(missing)},
        )


def field_bounds(
    document: Document, name: ParameterName, registry: Registry | None = None
) -> tuple[float | None, float | None]:
    """Die engsten Schemagrenzen der Felder, die das Maß unverändert lesen (``=@name``).

    Die Grenzen, die eine Zahl in der Parameterleiste wirklich hat (RM-354):
    *Breite* ohne eigene Grenzen fiel dort auf ±100 000 zurück, und 5000
    wurde angenommen, obwohl *Quader* höchstens 1000 mm breit wird. Nur das
    nackte ``=@name`` gibt eine Grenze, die sich ohne Umrechnung ins Feld
    übertragen lässt; was über einen Ausdruck liest, prüft
    :func:`bounds_refusal` mit der getippten Zahl. Abgeschaltete Schritte
    rechnen nicht und zählen nicht.
    """
    low: float | None = None
    high: float | None = None
    bare = f"{expressions.EXPRESSION_PREFIX}{expressions.REFERENCE_PREFIX}{name}"
    for _operation, entry, raw in _reading_fields(document, {name}, registry):
        if raw.replace(" ", "") != bare:
            continue
        if entry.minimum is not None:
            low = entry.minimum if low is None else max(low, entry.minimum)
        if entry.maximum is not None:
            high = entry.maximum if high is None else min(high, entry.maximum)
    return low, high


def bounds_refusal(
    document: Document, name: ParameterName, value: float, registry: Registry | None = None
) -> ValidationError | None:
    """Ob ``value`` für das Maß ein lesendes Operationsfeld über seine Grenze treibt.

    Die Kette hielt sonst an ihrem ersten Schritt an, und die Ansicht stand
    leer (RM-354, *Breite* 5000 am Beispiel Weg 2). Gerechnet wird, was die
    Auswertung rechnen würde: alle Maße mit dem neuen Wert aufgelöst, jedes
    Feld, das über das Maß oder ein davon abgeleitetes liest, ausgewertet und
    gegen seine Schemagrenze gehalten. Zurück kommt die erste Verletzung als
    Satz mit Schritt, Feld und Grenze — oder ``None``. Ein Satz, der schon
    ohne diese Zahl nicht aufgeht, ist nicht ihr Problem und bleibt ``None``.
    """
    existing = document.parameters.get(name)
    if existing is None:
        return None
    changed = {**document.parameters, name: dataclasses.replace(existing, value=value)}
    return bounds_refusal_with(document, changed, name, registry)


def bounds_refusal_with(
    document: Document,
    parameters: Mapping[ParameterName, Parameter],
    name: ParameterName,
    registry: Registry | None = None,
) -> ValidationError | None:
    """Wie :func:`bounds_refusal`, mit einem ganzen neuen Satz Maße.

    Für *Parameter ändern …*: Dort ändern sich Ausdruck oder Grenzen, und
    ein neuer Ausdruck treibt ein Feld genauso über seine Grenze wie eine
    getippte Zahl. Geprüft wird alles, was ``name`` liest — direkt oder über
    ein abgeleitetes Maß.
    """
    value = parameters[name].value
    try:
        values = expressions.resolve(parameters)
        graph = expressions.dependencies(parameters)
    except AppError:
        return None
    affected = {name}
    grown = True
    while grown:
        grown = False
        for reader, reads in graph.items():
            if reader not in affected and reads & affected:
                affected.add(reader)
                grown = True
    source = registry or REGISTRY
    for operation, entry, raw in _reading_fields(document, affected, registry):
        try:
            number = float(expressions.evaluate(raw, values))
        except AppError, TypeError, ValueError:
            continue
        if entry.minimum is not None and is_less(number, entry.minimum, EPS_GEOM):
            return _beyond(operation, entry, source, number, entry.minimum, value, low=True)
        if entry.maximum is not None and is_greater(number, entry.maximum, EPS_GEOM):
            return _beyond(operation, entry, source, number, entry.maximum, value, low=False)
    return None


def _reading_fields(
    document: Document, names: set[str], registry: Registry | None
) -> list[tuple[Operation, ParamSpec, str]]:
    """Die Zahlenfelder rechnender Schritte, deren Ausdruck eines der Maße liest."""
    source = registry or REGISTRY
    found: list[tuple[Operation, ParamSpec, str]] = []
    for operation in document.ops:
        if operation.suppressed is not None:
            continue
        try:
            specs = {entry.name: entry for entry in source.get(operation.op).params.spec()}
        except AppError:
            continue
        for field, raw in sorted(operation.params.items()):
            entry = specs.get(field)
            if entry is None or entry.kind not in NUMBER_KINDS:
                continue
            if not expressions.is_expression(raw):
                continue
            try:
                if not expressions.references(raw) & names:
                    continue
            except AppError:
                continue
            found.append((operation, entry, raw))
    return found


def _beyond(
    operation: Operation,
    entry: ParamSpec,
    registry: Registry,
    result: float,
    limit: float,
    value: float,
    *,
    low: bool,
) -> ValidationError:
    """Der Satz zu einer Grenze, die das Maß über ein Feld verletzt — mit Schritt und Grenze."""
    unit = f" {entry.unit}" if entry.unit else ""
    field = str(entry.title)
    title = str(registry.get(operation.op).title)
    reached = f"{format_decimal(result)}{unit}"
    allowed = f"{format_decimal(limit)}{unit}"
    detail = (
        _(
            "Damit käme „{field}“ in Schritt {number} ({operation}) auf {result} — "
            "erlaubt sind mindestens {limit}.",
            field=field,
            number=operation.id,
            operation=title,
            result=reached,
            limit=allowed,
        )
        if low
        else _(
            "Damit käme „{field}“ in Schritt {number} ({operation}) auf {result} — "
            "erlaubt sind höchstens {limit}.",
            field=field,
            number=operation.id,
            operation=title,
            result=reached,
            limit=allowed,
        )
    )
    detail_values = {
        "field": field,
        "number": operation.id,
        "operation": title,
        "result": reached,
        "limit": allowed,
    }
    if low:
        return ValidationError(
            field=f"ops.{operation.id}.{entry.name}",
            detail=detail,
            value=value,
            constraint="minimum",
            values={"minimum": limit, **detail_values},
        )
    return ValidationError(
        field=f"ops.{operation.id}.{entry.name}",
        detail=detail,
        value=value,
        constraint="maximum",
        values={"maximum": limit, **detail_values},
    )
