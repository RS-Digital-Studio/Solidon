"""Parameter schemas of operations (Bauplan §10).

One declaration carries bounds, unit, default and the front/advanced placement
from §2.4, and the same definition validates dialog, command line and agent call.

Declared as a dataclass so no dependency is needed::

    @op_params
    class ResizeHoleParams(BaseParams):
        diameter: float = param(title=_("Durchmesser"), default=5.0, unit="mm", minimum=0.1)

Parameter expressions ("=@width/2", §13) are resolved by the scene before an
operation runs; what arrives here is always a plain value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, dataclass, field, fields
from typing import Any, TypeVar

from app.core.errors import InternalError, ValidationError
from app.core.types import BaseParams, ParamKind, ParamPlacement, ParamSpec
from app.core.units import EPS_GEOM, is_greater, is_less
from app.i18n import TranslatableText, _

P = TypeVar("P", bound=BaseParams)

_METADATA_KEY = "param"

_KIND_BY_ANNOTATION: dict[str, ParamKind] = {
    "float": "float",
    "int": "int",
    "bool": "bool",
    "str": "str",
}


def param(
    *,
    title: TranslatableText | str,
    default: Any = MISSING,
    kind: ParamKind | None = None,
    unit: str | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    choices: tuple[str, ...] = (),
    placement: ParamPlacement = "front",
    doc: TranslatableText | str | None = None,
) -> Any:
    """Declare one parameter. Everything the surfaces need sits in one place."""
    metadata = {
        _METADATA_KEY: {
            "title": title,
            "kind": kind,
            "unit": unit,
            "minimum": minimum,
            "maximum": maximum,
            "choices": tuple(choices),
            "placement": placement,
            "doc": doc,
        }
    }
    if default is MISSING:
        return field(metadata=metadata)
    return field(default=default, metadata=metadata)


def _kind_of(annotation: Any, declared: ParamKind | None, choices: tuple[str, ...]) -> ParamKind:
    if declared is not None:
        return declared
    if choices:
        return "enum"
    name = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")
    kind = _KIND_BY_ANNOTATION.get(name)
    if kind is None:
        raise InternalError(
            detail=f"parameter type {name!r} needs an explicit kind",
            values={"annotation": str(annotation)},
        )
    return kind


def op_params(cls: type[P]) -> type[P]:
    """Turn a declaration into a frozen parameter set with a derived schema.

    Keyword-only, so declaration order stays free: required parameters may follow
    ones that carry a default, and nothing is ever passed positionally.
    """
    data_class = dataclass(frozen=True, slots=True, kw_only=True)(cls)
    specs: list[ParamSpec] = []
    for entry in fields(data_class):  # type: ignore[arg-type]
        metadata = entry.metadata.get(_METADATA_KEY)
        if metadata is None:
            raise InternalError(
                detail=f"{cls.__name__}.{entry.name} was declared without param()",
                values={"params": cls.__name__, "field": entry.name},
            )
        choices: tuple[str, ...] = metadata["choices"]
        has_default = entry.default is not MISSING
        specs.append(
            ParamSpec(
                name=entry.name,
                kind=_kind_of(entry.type, metadata["kind"], choices),
                title=metadata["title"],
                default=entry.default if has_default else None,
                required=not has_default,
                unit=metadata["unit"],
                minimum=metadata["minimum"],
                maximum=metadata["maximum"],
                choices=choices,
                placement=metadata["placement"],
                doc=metadata["doc"],
            )
        )
    data_class.__param_spec__ = tuple(specs)  # type: ignore[attr-defined]
    return data_class


def _coerce(spec: ParamSpec, value: Any) -> Any:
    """Check one value against its schema entry and return it in core form."""
    if spec.kind == "bool":
        if not isinstance(value, bool):
            raise ValidationError(
                field=spec.name,
                detail=_("Hier wird ja oder nein erwartet."),
                value=value,
                constraint="type",
            )
        return value

    if spec.kind in ("float", "int"):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValidationError(
                field=spec.name,
                detail=_("Hier wird eine Zahl erwartet."),
                value=value,
                constraint="type",
            )
        if spec.kind == "int" and not float(value).is_integer():
            raise ValidationError(
                field=spec.name,
                detail=_("Hier wird eine ganze Zahl erwartet."),
                value=value,
                constraint="type",
            )
        number = float(value) if spec.kind == "float" else int(value)
        if spec.minimum is not None and is_less(float(number), spec.minimum, EPS_GEOM):
            raise ValidationError(
                field=spec.name,
                detail=_("Der Wert liegt unter dem zulässigen Mindestwert."),
                value=value,
                constraint="minimum",
                values={"minimum": spec.minimum},
            )
        if spec.maximum is not None and is_greater(float(number), spec.maximum, EPS_GEOM):
            raise ValidationError(
                field=spec.name,
                detail=_("Der Wert liegt über dem zulässigen Höchstwert."),
                value=value,
                constraint="maximum",
                values={"maximum": spec.maximum},
            )
        return number

    if not isinstance(value, str):
        raise ValidationError(
            field=spec.name,
            detail=_("Hier wird ein Text erwartet."),
            value=value,
            constraint="type",
        )
    if spec.kind == "enum" and value not in spec.choices:
        raise ValidationError(
            field=spec.name,
            detail=_("Dieser Wert steht nicht zur Auswahl."),
            value=value,
            constraint="choices",
            values={"choices": list(spec.choices)},
        )
    return value


def validate(params_class: type[P], values: Mapping[str, Any]) -> P:
    """Build a validated parameter set, or fail with a correctable error."""
    specs = params_class.spec()
    known = {spec.name for spec in specs}
    unknown = sorted(set(values) - known)
    if unknown:
        raise ValidationError(
            field=unknown[0],
            detail=_("Diesen Parameter gibt es bei dieser Operation nicht."),
            constraint="unknown",
            values={"known": sorted(known)},
        )

    arguments: dict[str, Any] = {}
    for spec in specs:
        if spec.name in values:
            arguments[spec.name] = _coerce(spec, values[spec.name])
        elif spec.required:
            raise ValidationError(
                field=spec.name,
                detail=_("Dieser Parameter fehlt."),
                constraint="required",
            )
        else:
            arguments[spec.name] = spec.default
    return params_class(**arguments)


_JSON_TYPE: dict[ParamKind, str] = {
    "float": "number",
    "int": "integer",
    "bool": "boolean",
    "str": "string",
    "enum": "string",
    "object": "string",
    "feature": "string",
    "part": "string",
    "source": "string",
    "sketch": "string",
}


def json_schema(params_class: type[BaseParams]) -> dict[str, Any]:
    """JSON schema for the agent tool description (§10, §26.2)."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for spec in params_class.spec():
        entry: dict[str, Any] = {"type": _JSON_TYPE[spec.kind]}
        description = str(spec.doc) if spec.doc is not None else str(spec.title)
        if spec.unit:
            description = f"{description} [{spec.unit}]"
        entry["description"] = description
        if spec.minimum is not None:
            entry["minimum"] = spec.minimum
        if spec.maximum is not None:
            entry["maximum"] = spec.maximum
        if spec.choices:
            entry["enum"] = list(spec.choices)
        if not spec.required:
            entry["default"] = spec.default
        properties[spec.name] = entry
        if spec.required:
            required.append(spec.name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
