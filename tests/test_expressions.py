"""Die Grammatik nimmt an, was sie deklariert, und lehnt alles andere
ab (§13, §32).
"""

from __future__ import annotations

import pytest

from app.core import expressions
from app.core.errors import ValidationError
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


@pytest.mark.parametrize(
    "text",
    [
        "=round(1, " + "9" * 400 + ")",
        "=round(1, " + "9" * 400 + " - " + "9" * 400 + ")",
        "=round(@width, " + "9" * 400 + ")",
    ],
)
def test_a_function_that_cannot_answer_is_a_grammar_error(text: str) -> None:
    """``round`` auf ``inf`` oder ``nan`` Stellen warf einen rohen ``OverflowError``.

    Schon beim Eintippen, in der Syntaxprüfung — vor 0.5.0 ohne Satz und ohne
    Ausweg (Regel 17).
    """
    with pytest.raises(ValidationError) as caught:
        expressions.check(text)
    assert caught.value.suggestions
    with pytest.raises(ValidationError):
        expressions.evaluate(text, {"width": 84.0})


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


def test_shifting_a_bound_value_keeps_the_binding() -> None:
    """Ein Zug am Griff eines gebundenen Bausteins hängt den Versatz an den
    Ausdruck, statt die Bindung durch eine Zahl zu ersetzen (16.09.2026).

    Das Beispielprojekt bindet die Höhe seiner Bausteine an ``@staerke``; bis
    dahin lehnte die Oberfläche dort jede Bewegung ab, und der Baustein sprang
    im Bild zurück. Der Ausdruck bleibt lesbar, rechnet weiter mit dem
    Parameter und kommt auch aus einem bloßen Verweis als Ausdruck zurück.
    """
    values = {"staerke": 6.0}

    moved = expressions.shifted("=@staerke", 5.0)
    assert moved == "=@staerke + 5"
    assert expressions.evaluate(moved, values) == pytest.approx(11.0)

    back = expressions.shifted(moved, -2.25)
    assert back == "=@staerke + 5 - 2.25"
    assert expressions.evaluate(back, values) == pytest.approx(8.75)

    assert expressions.evaluate(expressions.shifted("@staerke", 1.0), values) == pytest.approx(7.0)
    # Ein Produkt behält seinen Vorrang: (6 * 2) - 1, nicht 6 * (2 - 1).
    assert expressions.evaluate(
        expressions.shifted("=@staerke * 2", -1.0), values
    ) == pytest.approx(11.0)


# --- Getippt ohne = und @ (Durchsicht 0.5.0) -------------------------------------


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("schraube_m4 + spiel", "=@schraube_m4 + @spiel"),
        ("=schraube_m4 + spiel", "=@schraube_m4 + @spiel"),
        ("=@schraube_m4 + @spiel", "=@schraube_m4 + @spiel"),
        ("schraube_m4 * 2", "=@schraube_m4 * 2"),
        ("@spiel", "@spiel"),
        ("max(schraube_m4, 3)", "=max(@schraube_m4, 3)"),
        ("12", "=12"),
    ],
)
def test_a_known_name_is_taken_without_at_and_stored_with_it(typed: str, stored: str) -> None:
    """Die Website zeigt ``schraube_m4 + spiel``; der Auswerter wies es ab.

    Wer aus dem Slicer kommt, kennt kein ``@``. Das Formelfeld ergänzt es vor
    einem bekannten Namen, und das führende ``=`` dazu — gespeichert wird die
    Form mit beidem, und die rechnet wie getippt.
    """
    names = {"schraube_m4": 4.0, "spiel": 0.3}

    written = expressions.canonical(typed, names)

    assert written == stored
    expressions.check(written)
    assert expressions.is_expression(written)
    assert expressions.canonical(written, names) == written, "die Form ist ein Fixpunkt"


def test_a_name_that_is_also_a_function_asks_for_the_at() -> None:
    """Heißt ein Parameter ``max``, ist ``max + 1`` mehrdeutig — und wird nicht geraten.

    Die Klammer entscheidet: ``max(…)`` ist der Aufruf und bleibt einer. Ohne
    Klammer kommt eine Absage mit dem Vorschlag ``@max``.
    """
    names = {"max": 10.0}

    with pytest.raises(ValidationError) as caught:
        expressions.canonical("max + 1", names)
    assert caught.value.values["suggestion"] == "@max"
    assert caught.value.suggestions
    assert "{" not in str(caught.value.detail), "ein Fehlertext trägt keinen Platzhalter"

    assert expressions.canonical("max(@max, 1)", names) == "=max(@max, 1)"
    assert expressions.evaluate(expressions.canonical("@max + 1", names), names) == 11.0


@pytest.mark.parametrize("typed", ["import os", "__import__('os')", "breite + 1", "2 ** 3"])
def test_an_unknown_name_is_still_refused_after_the_completion(typed: str) -> None:
    """Ergänzt wird nur, was das Projekt kennt — alles andere bleibt abgelehnt (Regel 10)."""
    written = expressions.canonical(typed, {"hoehe": 5.0})

    with pytest.raises(ValidationError):
        expressions.check(written)


def test_completed_expressions_still_find_their_cycle() -> None:
    """Zwei Parameter, die einander ohne ``@`` nennen, bleiben ein Zyklus."""
    names = {"a", "b"}
    params = parameters(
        a=(0.0, expressions.canonical("b + 1", names)),
        b=(0.0, expressions.canonical("a + 1", names)),
    )

    with pytest.raises(ValidationError) as caught:
        expressions.resolve(params)
    assert caught.value.constraint == "cycle"


def test_a_completed_expression_travels_through_the_project_file(tmp_path) -> None:
    """Gespeichert, geöffnet, gerechnet: Die ergänzte Form ist die Form der Datei."""
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, load, new_project, save

    load_operations()
    project = new_project("centauri-carbon-2", "pla")
    project.document.parameters["schraube_m4"] = Parameter(name="schraube_m4", value=4.0)
    project.document.parameters["spiel"] = Parameter(name="spiel", value=0.3)
    width = expressions.canonical("schraube_m4 * 10 + spiel", project.document.parameters)
    History(project.document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": width, "depth": 10.0, "height": 5.0})],
    )

    reopened = load(save(project, tmp_path / "formel.p3d"))

    assert reopened.document.ops[-1].params["width"] == "=@schraube_m4 * 10 + @spiel"
    result = evaluate(
        reopened.document,
        profiles.make_profile("centauri-carbon-2", "pla"),
        sources=ProjectSources(reopened),
    )
    assert result.complete, result.scene.report.findings
    size = result.scene.objects["obj_1"].mesh.bounds.size
    assert float(size[0]) == pytest.approx(40.3)
