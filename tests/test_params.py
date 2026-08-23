"""Ein Schema validiert Dialog, Kommandozeile und Agentenaufruf (Bauplan
§10).
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.registry import json_schema, op_params, param, validate
from app.core.types import BaseParams
from app.i18n import _


@op_params
class SampleParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"), default=5.0, unit="mm", minimum=0.5, maximum=50.0
    )
    count: int = param(title=_("Anzahl"), default=1, minimum=1, maximum=8)
    through: bool = param(title=_("Durchgehend"), default=True)
    mode: str = param(title=_("Art"), default="subtract", choices=("subtract", "add"))
    target: str = param(title=_("Ziel"), kind="feature", placement="advanced")


def test_schema_is_derived_from_the_declaration() -> None:
    by_name = {spec.name: spec for spec in SampleParams.spec()}
    assert by_name["diameter"].kind == "float"
    assert by_name["diameter"].unit == "mm"
    assert by_name["count"].kind == "int"
    assert by_name["through"].kind == "bool"
    assert by_name["mode"].kind == "enum"
    assert by_name["target"].kind == "feature"
    assert by_name["target"].placement == "advanced", "rarely used values belong on the back side"
    assert by_name["target"].required
    assert not by_name["diameter"].required


def test_defaults_fill_in_what_the_caller_left_out() -> None:
    params = validate(SampleParams, {"target": "hole_3"})
    assert params.diameter == pytest.approx(5.0)
    assert params.count == 1
    assert params.through is True
    assert params.mode == "subtract"


def test_bounds_are_enforced_on_both_sides() -> None:
    with pytest.raises(ValidationError) as too_small:
        validate(SampleParams, {"target": "hole_3", "diameter": 0.1})
    assert too_small.value.constraint == "minimum"
    assert too_small.value.suggestions

    with pytest.raises(ValidationError) as too_large:
        validate(SampleParams, {"target": "hole_3", "diameter": 500.0})
    assert too_large.value.constraint == "maximum"


def test_types_are_checked_and_bool_is_not_a_number() -> None:
    with pytest.raises(ValidationError):
        validate(SampleParams, {"target": "hole_3", "diameter": "5"})
    with pytest.raises(ValidationError):
        validate(SampleParams, {"target": "hole_3", "diameter": True})
    with pytest.raises(ValidationError):
        validate(SampleParams, {"target": "hole_3", "count": 1.5})
    with pytest.raises(ValidationError):
        validate(SampleParams, {"target": "hole_3", "through": 1})


def test_an_integer_is_accepted_where_a_length_is_expected() -> None:
    params = validate(SampleParams, {"target": "hole_3", "diameter": 4})
    assert isinstance(params.diameter, float)


def test_choices_are_closed() -> None:
    with pytest.raises(ValidationError) as caught:
        validate(SampleParams, {"target": "hole_3", "mode": "intersect"})
    assert caught.value.constraint == "choices"


def test_unknown_and_missing_parameters_are_reported() -> None:
    with pytest.raises(ValidationError) as unknown:
        validate(SampleParams, {"target": "hole_3", "depth": 2.0})
    assert unknown.value.constraint == "unknown"

    with pytest.raises(ValidationError) as missing:
        validate(SampleParams, {})
    assert missing.value.constraint == "required"
    assert missing.value.field == "target"
    # **Und der Kunde muss lesen können, welcher.** Im Prüfbericht stand
    # „Dieser Parameter fehlt." und sonst nichts — gemessen an „Relief
    # auflegen" ohne Bild, wo die Auswertung genau daran anhält. Der Name
    # steht in ``values`` und nicht im Satz: Ein ``{platzhalter}`` im
    # ``detail`` bleibt stehen, wie er dasteht.
    assert str(missing.value.values.get("parameter")) == str(
        next(spec.title for spec in SampleParams.spec() if spec.name == "target")
    ), "the report must name the missing parameter the way the dialog labels it"


def test_parameter_sets_are_frozen() -> None:
    params = validate(SampleParams, {"target": "hole_3"})
    with pytest.raises(AttributeError):
        params.diameter = 9.0  # type: ignore[misc]


def test_json_schema_carries_bounds_units_and_choices() -> None:
    schema = json_schema(SampleParams)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["target"]
    diameter = schema["properties"]["diameter"]
    assert diameter["type"] == "number"
    assert diameter["minimum"] == pytest.approx(0.5)
    assert diameter["maximum"] == pytest.approx(50.0)
    assert "[mm]" in diameter["description"]
    assert schema["properties"]["mode"]["enum"] == ["subtract", "add"]
    assert schema["properties"]["count"]["type"] == "integer"
