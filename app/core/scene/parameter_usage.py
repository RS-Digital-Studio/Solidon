"""Wo Projektmaße im aktuellen Stapel wirken (Bauplan §13, §15)."""

from __future__ import annotations

from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter

from app.core import expressions
from app.core.errors import ValidationError
from app.core.registry import REGISTRY, Registry
from app.core.types import Document, OpId, ParameterName
from app.i18n import _


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
