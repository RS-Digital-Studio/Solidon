"""Parameterschemata der Operationen (Bauplan §10).

Eine Deklaration trägt Grenzen, Einheit, Vorgabe und die Vorderseiten-Zuordnung
aus §2.4, und dieselbe Definition validiert Dialog, Kommandozeile und
Agentenaufruf.

Als Dataclass deklariert, damit keine Abhängigkeit nötig ist::

    @op_params
    class ResizeHoleParams(BaseParams):
        diameter: float = param(title=_("Durchmesser"), default=5.0, unit="mm", minimum=0.1)

Parameterausdrücke ("=@width/2", §13) löst die Szene auf, bevor eine Operation
läuft; was hier ankommt, ist immer ein nackter Wert.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, dataclass, field, fields
from typing import Any, Final

from app.core.errors import InternalError, ValidationError
from app.core.types import BaseParams, ParamKind, ParamPlacement, ParamSpec
from app.core.units import EPS_GEOM, is_greater, is_less
from app.i18n import TranslatableText, _

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
    """Deklariert einen Parameter. Alles, was die Oberflächen brauchen, sitzt
    an einer Stelle.
    """
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


def op_params[P: BaseParams](cls: type[P]) -> type[P]:
    """Macht aus einer Deklaration einen eingefrorenen Parametersatz mit
    abgeleitetem Schema.

    Nur Schlüsselwörter, damit die Reihenfolge der Deklaration frei bleibt:
    Pflichtparameter dürfen auf welche mit Vorgabe folgen, und übergeben wird
    nie positionell.
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
    """Prüft einen Wert gegen seinen Schemaeintrag und gibt ihn in Kernform
    zurück.
    """
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


def validate[P: BaseParams](params_class: type[P], values: Mapping[str, Any]) -> P:
    """Baut einen validierten Parametersatz — oder scheitert mit einem
    korrigierbaren Fehler.
    """
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
    "strokes": "string",
    "armature": "string",
}

#: Parameterarten, die eine unbegrenzte Zahl von Nutzergesten sammeln (Regel 2).
#: Der Agent sieht sie nicht — er verweist auf Merkmale und benutzt Maße, er
#: erzeugt keine Koordinaten (Leitprinzip 5). ``tests/test_gesture_ops.py``
#: prüft diese Menge gegen dieselbe Liste auf der anderen Seite.
#: Parameterarten, die Gesten sammeln (§30.1). Der Agent bekommt sie nicht
#: angeboten — und `agent/session.py` weist sie auch ab, wenn ein Modell sie
#: rät. Beide Stellen lesen diese Menge; eine zweite Liste wäre am Tag nach
#: der nächsten Geste falsch.
GATHERED_KINDS: Final[frozenset[str]] = frozenset({"sketch", "strokes", "armature"})


def json_schema(params_class: type[BaseParams]) -> dict[str, Any]:
    """JSON-Schema für die Werkzeugbeschreibung des Agenten (§10, §26.2)."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for spec in params_class.spec():
        if spec.kind in GATHERED_KINDS:
            # §26, Leitprinzip 5: der Agent erzeugt Skizzen ausschließlich über
            # benannte Grundformen und Maße, nie über rohe Punktlisten — den
            # Skizzentext bekommt er gar nicht erst angeboten. Für Pinselstriche
            # gilt dasselbe schärfer: ein Strich *ist* eine Koordinate.
            continue
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
