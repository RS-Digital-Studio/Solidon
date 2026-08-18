"""Die Grammatik nimmt an, was sie deklariert, und lehnt alles andere
ab (§13, §32).
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.scene import expressions
from app.core.types import Parameter


def parameters(**entries: tuple[float, str | None]) -> dict[str, Parameter]:
    return {
        name: Parameter(name=name, value=value, expression=expression)
        for name, (value, expression) in entries.items()
    }


def test_numbers_and_the_four_operations() -> None:
    values = {"width": 84.0, "wall": 2.4}
    assert expressions.evaluate("=1 + 2 * 3", values) == pytest.approx(7.0)
    assert expressions.evaluate("=(1 + 2) * 3", values) == pytest.approx(9.0)
    assert expressions.evaluate("=@width/2 - @wall", values) == pytest.approx(39.6)
    assert expressions.evaluate("=-@wall", values) == pytest.approx(-2.4)
    assert expressions.evaluate("@width", values) == pytest.approx(84.0)


def test_the_four_permitted_functions() -> None:
    values = {"a": 3.0, "b": 8.0}
    assert expressions.evaluate("=min(@a, @b)", values) == pytest.approx(3.0)
    assert expressions.evaluate("=max(@a, @b, 12)", values) == pytest.approx(12.0)
    assert expressions.evaluate("=abs(0 - @a)", values) == pytest.approx(3.0)
    assert expressions.evaluate("=round(2.345, 1)", values) == pytest.approx(2.3)
    assert expressions.evaluate("=round(2.6)", values) == pytest.approx(3.0)


@pytest.mark.parametrize(
    "text",
    [
        "=__import__('os')",
        "=open('secret')",
        "=width",
        "=@width.real",
        "=@width ** 2",
        "=@width // 2",
        "=@width % 2",
        "=@width & 2",
        "=@width > 2",
        "=[1, 2]",
        "={'a': 1}",
        "=lambda: 1",
        "=1;2",
        "=1 +",
        "=(1 + 2",
        "=1 2",
        "=@",
        "=sqrt(4)",
        "=min(1)",
        "=round(1, 2, 3)",
        "=1e3",
        "=0x10",
        "",
    ],
)
def test_everything_outside_the_grammar_is_rejected(text: str) -> None:
    with pytest.raises(ValidationError):
        expressions.check(text)


def test_rejection_carries_a_suggestion() -> None:
    with pytest.raises(ValidationError) as caught:
        expressions.check("=@width ** 2")
    assert caught.value.suggestions
    assert caught.value.constraint == "grammar"


def test_division_by_zero_is_a_user_error() -> None:
    with pytest.raises(ValidationError):
        expressions.evaluate("=@width / 0", {"width": 84.0})


def test_division_by_a_parameter_reference_passes_the_check() -> None:
    """Die Prüfung parst mit Platzhalter-Nullen — ob durch null geteilt wird,
    weiß erst die Auswertung. `=@width/@count` war deshalb überall abgelehnt,
    obwohl §13 genau diese Form als Vorlagen-Mechanik vorsieht."""
    expressions.check("=@width/@count")
    assert expressions.references("=100/@width") == {"width"}
    resolved = expressions.resolve(parameters(a=(4.0, None), b=(0.0, "=100/@a")))
    assert resolved["b"] == pytest.approx(25.0)


def test_division_by_a_parameter_that_is_zero_fails_at_evaluation() -> None:
    """Der Divisionsschutz gehört zur Auswertung mit echten Werten — dort
    bleibt er scharf, auch wenn die Prüfung den Ausdruck durchlässt."""
    expressions.check("=1/@count")
    with pytest.raises(ValidationError):
        expressions.evaluate("=1/@count", {"count": 0.0})
    with pytest.raises(ValidationError):
        expressions.resolve(parameters(n=(0.0, None), q=(0.0, "=1/@n")))


def test_division_by_a_literal_zero_is_rejected_at_check() -> None:
    """Eine Literal-Null im Nenner ist immer ein Fehler, unabhängig von
    Parameterwerten — die Prüfung lehnt sie weiter ab."""
    with pytest.raises(ValidationError):
        expressions.check("=@width/0")
    with pytest.raises(ValidationError):
        expressions.check("=@width/(2-2)")


def test_deep_nesting_stops_before_the_recursion_limit() -> None:
    with pytest.raises(ValidationError):
        expressions.check("=" + "(" * 200 + "1" + ")" * 200)


def test_references_are_reported_without_values() -> None:
    assert expressions.references("=@width/2 - @wall") == frozenset({"width", "wall"})
    assert expressions.references("=1 + 2") == frozenset()


def test_unknown_parameter_is_named() -> None:
    with pytest.raises(ValidationError) as caught:
        expressions.evaluate("=@depth", {"width": 84.0})
    assert caught.value.values["parameter"] == "depth"


def test_resolution_follows_the_dependencies() -> None:
    values = expressions.resolve(
        parameters(
            width=(84.0, None),
            wall=(2.4, None),
            inner=(0.0, "=@width - 2*@wall"),
            half=(0.0, "=@inner/2"),
        )
    )
    assert values["inner"] == pytest.approx(79.2)
    assert values["half"] == pytest.approx(39.6)


def test_cycles_are_rejected_with_the_cycle_named() -> None:
    with pytest.raises(ValidationError) as caught:
        expressions.resolve(parameters(a=(0.0, "=@b + 1"), b=(0.0, "=@a + 1")))
    assert caught.value.constraint == "cycle"
    assert set(caught.value.values["cycle"]) == {"a", "b"}

    with pytest.raises(ValidationError):
        expressions.resolve(parameters(a=(0.0, "=@a")))


def test_a_reference_to_a_missing_parameter_is_rejected_early() -> None:
    with pytest.raises(ValidationError) as caught:
        expressions.resolve(parameters(a=(0.0, "=@nowhere")))
    assert caught.value.values["missing"] == ["nowhere"]


def test_operation_parameters_are_resolved_before_validation() -> None:
    values = {"height": 22.0}
    resolved = expressions.resolve_params(
        {"position": "=@height/2", "axis": "z", "count": 3}, values
    )
    assert resolved["position"] == pytest.approx(11.0)
    assert resolved["axis"] == "z"
    assert resolved["count"] == 3


def test_used_parameters_reports_what_a_stack_entry_depends_on() -> None:
    assert expressions.used_parameters(["=@height/2", "z", 3, "@width"]) == frozenset(
        {"height", "width"}
    )


def test_a_plain_number_is_not_an_expression() -> None:
    assert not expressions.is_expression(5.0)
    assert not expressions.is_expression("subtract")
    assert expressions.is_expression("=1+1")
    assert expressions.is_expression("@width")
