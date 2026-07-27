"""Document to data and back (Bauplan §12).

The keys written here are the file format. They are English, they are stable,
and they match the example in §12 — including ``in``/``out``, which are Python
keywords and therefore called ``inputs``/``outputs`` in the code.

Two indirections survive the round trip untouched, because that is the point of
them: ``auto:<material>`` for tolerances and ``=@name`` for parameters (§13).
"""

from __future__ import annotations

from typing import Any

from app.core.types import (
    Document,
    FeatureRef,
    Finding,
    Fit,
    IngestInfo,
    Operation,
    Origin,
    Parameter,
    Report,
    SolverInfo,
    Source,
    SourceOrigin,
    Transaction,
)


def _without_none(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


# --- Parameters ----------------------------------------------------------------


def parameter_to_data(parameter: Parameter) -> dict[str, Any]:
    return _without_none(
        {
            "value": parameter.value,
            "unit": parameter.unit,
            "min": parameter.minimum,
            "max": parameter.maximum,
            "title": str(parameter.title) if parameter.title is not None else None,
            "expression": parameter.expression,
        }
    )


def parameter_from_data(name: str, data: dict[str, Any]) -> Parameter:
    return Parameter(
        name=name,
        value=float(data.get("value", 0.0)),
        unit=data.get("unit", "mm"),
        title=data.get("title"),
        minimum=data.get("min"),
        maximum=data.get("max"),
        expression=data.get("expression"),
    )


# --- Fits ----------------------------------------------------------------------


def fit_to_data(fit: Fit) -> dict[str, Any]:
    return {
        "name": fit.name,
        "a": str(fit.a),
        "b": str(fit.b),
        "type": fit.kind,
        "tolerance": fit.tolerance,
    }


def fit_from_data(data: dict[str, Any]) -> Fit:
    return Fit(
        name=data["name"],
        a=FeatureRef.parse(data["a"]),
        b=FeatureRef.parse(data["b"]),
        kind=data.get("type", "clearance"),
        tolerance=data.get("tolerance", "auto:"),
    )


# --- Sources -------------------------------------------------------------------


def source_to_data(source: Source) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": source.kind,
        "path": source.path,
        "sha256": source.sha256,
        "embedded": source.embedded,
        "ingest": {
            "unit": source.ingest.unit,
            "scale": source.ingest.scale,
            "welded": source.ingest.welded,
            "removed_triangles": source.ingest.removed_triangles,
            "components": source.ingest.components,
        },
    }
    if source.origin is not None:
        data["origin"] = _without_none(
            {
                "url": source.origin.url,
                "title": source.origin.title,
                "author": source.origin.author,
                "license": source.origin.licence,
                "retrieved": source.origin.retrieved,
            }
        )
    return data


def source_from_data(source_id: str, data: dict[str, Any]) -> Source:
    ingest = data.get("ingest", {})
    origin = data.get("origin")
    return Source(
        id=source_id,
        kind=data.get("type", "import"),
        path=data["path"],
        sha256=data.get("sha256", ""),
        embedded=bool(data.get("embedded", True)),
        ingest=IngestInfo(
            unit=ingest.get("unit", "mm"),
            scale=float(ingest.get("scale", 1.0)),
            welded=bool(ingest.get("welded", False)),
            removed_triangles=int(ingest.get("removed_triangles", 0)),
            components=int(ingest.get("components", 1)),
        ),
        origin=(
            SourceOrigin(
                url=origin.get("url"),
                title=origin.get("title"),
                author=origin.get("author"),
                licence=origin.get("license"),
                retrieved=origin.get("retrieved"),
            )
            if origin
            else None
        ),
    )


# --- Stack ---------------------------------------------------------------------


def origin_to_data(origin: Origin) -> dict[str, Any]:
    return _without_none(
        {
            "by": origin.by,
            "model": origin.model,
            "prompt_version": origin.prompt_version,
            "rules_version": origin.rules_version,
            "temperature": origin.temperature,
        }
    )


def origin_from_data(data: dict[str, Any] | None) -> Origin:
    if not data:
        return Origin(by="user")
    return Origin(
        by=data.get("by", "user"),
        model=data.get("model"),
        prompt_version=data.get("prompt_version"),
        rules_version=data.get("rules_version"),
        temperature=data.get("temperature"),
    )


def transaction_to_data(transaction: Transaction) -> dict[str, Any]:
    """The title is stored as the text the user saw, not as a translation key:
    a history entry is a record of what happened, and the user may rename it."""
    return {
        "id": transaction.id,
        "title": str(transaction.title),
        "origin": origin_to_data(transaction.origin),
        "ops": list(transaction.ops),
    }


def transaction_from_data(data: dict[str, Any]) -> Transaction:
    return Transaction(
        id=data["id"],
        title=data.get("title", ""),
        ops=tuple(int(entry) for entry in data.get("ops", ())),
        origin=origin_from_data(data.get("origin")),
    )


def solver_to_data(solver: SolverInfo) -> dict[str, Any]:
    return _without_none(
        {
            "strategy": solver.strategy,
            "attempted": list(solver.attempted) or None,
            "seed": solver.seed,
            "note": str(solver.note) if solver.note is not None else None,
        }
    )


def solver_from_data(data: dict[str, Any] | None) -> SolverInfo | None:
    if not data:
        return None
    return SolverInfo(
        strategy=data["strategy"],
        attempted=tuple(data.get("attempted", ())),
        seed=data.get("seed"),
        note=data.get("note"),
    )


def operation_to_data(operation: Operation) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": operation.id,
        "op": operation.op,
        "in": list(operation.inputs),
        "out": list(operation.outputs),
        "params": dict(operation.params),
    }
    if operation.solver is not None:
        data["solver"] = solver_to_data(operation.solver)
    if operation.seed is not None:
        data["seed"] = operation.seed
    return data


def operation_from_data(data: dict[str, Any]) -> Operation:
    return Operation(
        id=int(data["id"]),
        op=data["op"],
        inputs=tuple(data.get("in", ())),
        outputs=tuple(data.get("out", ())),
        params=dict(data.get("params", {})),
        solver=solver_from_data(data.get("solver")),
        seed=data.get("seed"),
    )


# --- Report --------------------------------------------------------------------


def finding_to_data(finding: Finding) -> dict[str, Any]:
    return _without_none(
        {
            "code": finding.code,
            "severity": finding.severity,
            "message": str(finding.message),
            "object_id": finding.object_id,
            "op_id": finding.op_id,
            "feature_ids": list(finding.feature_ids) or None,
            "values": dict(finding.values) or None,
            "location": list(finding.location) if finding.location else None,
            "source": finding.source,
        }
    )


def finding_from_data(data: dict[str, Any]) -> Finding:
    location = data.get("location")
    return Finding(
        code=data["code"],
        severity=data.get("severity", "info"),
        message=data.get("message", ""),
        object_id=data.get("object_id"),
        op_id=data.get("op_id"),
        feature_ids=tuple(data.get("feature_ids", ())),
        values=data.get("values", {}),
        location=(location[0], location[1], location[2]) if location else None,
        source=data.get("source", "internal"),
    )


def report_to_data(report: Report) -> dict[str, Any]:
    return {"findings": [finding_to_data(entry) for entry in report.findings]}


def report_from_data(data: dict[str, Any]) -> Report:
    return Report(tuple(finding_from_data(entry) for entry in data.get("findings", ())))


# --- Document ------------------------------------------------------------------


def document_to_data(document: Document) -> dict[str, Any]:
    return {
        "format_version": document.format_version,
        "app_version": document.app_version,
        "libs": dict(document.libs),
        "parts_version": document.parts_version,
        "scene": {"printer": document.printer, "material": document.material},
        "parameters": {
            name: parameter_to_data(parameter) for name, parameter in document.parameters.items()
        },
        "sources": {
            source_id: source_to_data(source) for source_id, source in document.sources.items()
        },
        "fits": [fit_to_data(entry) for entry in document.fits],
        "transactions": [transaction_to_data(entry) for entry in document.transactions],
        "ops": [operation_to_data(entry) for entry in document.ops],
    }


def document_from_data(data: dict[str, Any]) -> Document:
    scene = data.get("scene", {})
    return Document(
        format_version=int(data["format_version"]),
        app_version=data.get("app_version", ""),
        libs=dict(data.get("libs", {})),
        parts_version=str(data.get("parts_version", "0")),
        printer=scene.get("printer", ""),
        material=scene.get("material", ""),
        parameters={
            name: parameter_from_data(name, entry)
            for name, entry in data.get("parameters", {}).items()
        },
        sources={
            source_id: source_from_data(source_id, entry)
            for source_id, entry in data.get("sources", {}).items()
        },
        fits=[fit_from_data(entry) for entry in data.get("fits", ())],
        transactions=[transaction_from_data(entry) for entry in data.get("transactions", ())],
        ops=[operation_from_data(entry) for entry in data.get("ops", ())],
    )
