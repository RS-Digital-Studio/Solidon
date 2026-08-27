"""Declared once, generated everywhere (Bauplan §10, Leitprinzip 3)."""

from __future__ import annotations

import pytest

from app.core.errors import InternalError
from app.core.registry import (
    REGISTRY,
    VARIABLE,
    OperationSpec,
    Registry,
    cli_commands,
    context_menu,
    documentation,
    menu_tree,
    op_params,
    palette_entries,
    param,
    register_op,
    tool_schemas,
)
from app.core.types import BaseParams, OpContext, OpResult
from app.i18n import _


@op_params
class ResizeHoleParams(BaseParams):
    diameter: float = param(title=_("Durchmesser"), default=5.0, unit="mm", minimum=0.1)


@op_params
class ScatterParams(BaseParams):
    count: int = param(title=_("Anzahl"), default=3, minimum=1)


@pytest.fixture
def registry() -> Registry:
    """Ein eigenes Register, damit Tests nie von der Ladereihenfolge abhängen."""
    own = Registry()

    @register_op(
        name="resize_hole",
        title=_("Bohrung ändern"),
        category="holes",
        params=ResizeHoleParams,
        applies_to=["hole"],
        touches_features=True,
        shortcut="Ctrl+Shift+B",
        doc=_("Ändert den Durchmesser einer erkannten Bohrung."),
        registry=own,
    )
    def resize_hole(ctx: OpContext) -> OpResult:
        return OpResult(outputs=list(ctx.inputs))

    @register_op(
        name="scatter_pins",
        title=_("Stifte verteilen"),
        category="prepare",
        params=ScatterParams,
        deterministic=False,
        doc=_("Verteilt Passstifte auf der Trennebene."),
        registry=own,
    )
    def scatter_pins(ctx: OpContext) -> OpResult:
        _unused = ctx.seed
        return OpResult(outputs=list(ctx.inputs))

    return own


def test_declaration_lands_in_the_registry(registry: Registry) -> None:
    spec = registry.get("resize_hole")
    assert isinstance(spec, OperationSpec)
    assert spec.category == "holes"
    assert spec.applies_to == ("hole",)
    assert spec.reversible
    assert spec.requires_seed is False
    assert registry.get("scatter_pins").requires_seed is True


def test_every_operation_reaches_every_surface(registry: Registry) -> None:
    """Die Tabelle aus §10: eine Deklaration, sechs Ausgaben."""
    names = {spec.name for spec in registry.all()}

    in_menu = {spec.name for section in menu_tree(registry) for spec in section.entries}
    in_palette = {entry.name for entry in palette_entries(registry)}
    in_cli = {command.name for command in cli_commands(registry)}
    in_tools = {schema["name"] for schema in tool_schemas(registry)}
    text = documentation(registry)

    assert in_menu == names
    assert in_palette == names
    assert in_cli == names
    assert in_tools == names
    for name in names:
        assert f"`{name}`" in text


def test_context_menu_follows_applies_to(registry: Registry) -> None:
    assert [spec.name for spec in context_menu("hole", registry)] == ["resize_hole"]
    assert context_menu("face", registry) == ()


def test_menu_keeps_catalogue_order(registry: Registry) -> None:
    assert [section.category for section in menu_tree(registry)] == ["holes", "prepare"]


def test_cli_arguments_are_derived_from_the_schema(registry: Registry) -> None:
    command = next(entry for entry in cli_commands(registry) if entry.name == "resize_hole")
    argument = command.arguments[0]
    assert argument.flag == "--diameter"
    assert argument.kind == "float"
    assert not argument.required
    assert "[mm]" in argument.help


def test_tool_schema_is_the_same_schema(registry: Registry) -> None:
    schema = next(entry for entry in tool_schemas(registry) if entry["name"] == "resize_hole")
    assert schema["input_schema"]["properties"]["diameter"]["minimum"] == pytest.approx(0.1)
    assert schema["description"]


def test_a_second_registration_of_the_same_name_fails(registry: Registry) -> None:
    with pytest.raises(InternalError):

        @register_op(
            name="resize_hole",
            title=_("Nochmal"),
            category="holes",
            params=ResizeHoleParams,
            registry=registry,
        )
        def duplicate(ctx: OpContext) -> OpResult:
            return OpResult(outputs=[])


def test_a_duplicate_shortcut_fails(registry: Registry) -> None:
    with pytest.raises(InternalError):

        @register_op(
            name="other_op",
            title=_("Andere"),
            category="holes",
            params=ResizeHoleParams,
            shortcut="ctrl+shift+b",
            registry=registry,
        )
        def other(ctx: OpContext) -> OpResult:
            return OpResult(outputs=[])


def test_unknown_category_and_feature_kind_fail(registry: Registry) -> None:
    with pytest.raises(InternalError):

        @register_op(
            name="odd_category",
            title=_("Seltsam"),
            category="does-not-exist",
            params=ResizeHoleParams,
            registry=registry,
        )
        def odd(ctx: OpContext) -> OpResult:
            return OpResult(outputs=[])

    with pytest.raises(InternalError):

        @register_op(
            name="odd_feature",
            title=_("Seltsam"),
            category="holes",
            params=ResizeHoleParams,
            applies_to=["sprocket"],
            registry=registry,
        )
        def odd_feature(ctx: OpContext) -> OpResult:
            return OpResult(outputs=[])


def test_names_stay_lower_snake_case(registry: Registry) -> None:
    with pytest.raises(InternalError):

        @register_op(
            name="ResizeHole",
            title=_("Falsch"),
            category="holes",
            params=ResizeHoleParams,
            registry=registry,
        )
        def wrong_name(ctx: OpContext) -> OpResult:
            return OpResult(outputs=[])


def test_parameters_must_be_a_schema(registry: Registry) -> None:
    with pytest.raises(InternalError):

        @register_op(
            name="no_schema",
            title=_("Ohne Schema"),
            category="holes",
            params=dict,  # type: ignore[arg-type]
            registry=registry,
        )
        def no_schema(ctx: OpContext) -> OpResult:
            return OpResult(outputs=[])


def test_unknown_operation_is_an_internal_error(registry: Registry) -> None:
    with pytest.raises(InternalError):
        registry.get("nothing_like_this")
    assert not registry.has("nothing_like_this")


# --- Die Deklarationen des echten Registers müssen zueinander passen -------------


def test_no_declaration_of_the_real_registry_contradicts_itself() -> None:
    """§10: die Deklaration ist die eine Quelle, sie darf also nicht zwei Dinge
    sagen.

    Drei Felder kamen hinzu, die einander widersprechen können, und ein
    Widerspruch zwischen ihnen ist in keinem einzelnen von ihnen zu sehen: eine
    Ausgabezahl, die einen Parameter benennt, den die Operation nicht hat, eine
    Anzahl ohne variable Ausgabe, oder eine Operation, die die ganze Szene
    nimmt *und* ein bestimmtes Objekt.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    for spec in REGISTRY.all():
        names = {entry.name for entry in spec.params.spec()}
        if spec.produces_from:
            assert spec.produces == VARIABLE, f"{spec.name}: a stated count needs a variable output"
            assert spec.produces_from in names, f"{spec.name}: names {spec.produces_from}"
        if spec.whole_scene:
            assert not spec.consumes, f"{spec.name}: the whole scene is not one object"
            assert spec.produces == VARIABLE, f"{spec.name}: hands them all back"


def test_a_feature_parameter_is_declared_as_one() -> None:
    """§21.3 prüft die Verweise, von denen ihm erzählt wird — nach Art, nicht
    nach Namen.

    Achtzehn Operationen benennen ein Merkmal, und bevor sie das sagten, lief
    die Verwaisten-Prüfung an jeder einzelnen vorbei.

    **Die Zusicherung lief einmal in beide Richtungen und war dadurch zu
    scharf.** ``named == declared`` verlangte nicht nur, dass jedes
    ``at_feature`` sich deklariert — es verbot auch, dass ein Merkmalsfeld
    anders heißt. Genau daran ist *An Merkmal ausrichten* hängengeblieben: Ihr
    Feld heißt ``feature``, und um es der Verwaisten-Prüfung sichtbar zu
    machen, musste dieser Test erst nachgeben. Ein Test, der einen Fehler am
    Beheben hindert, prüft die Gewohnheit und nicht die Zusage.

    Was die Gegenrichtung geschützt hat, übernimmt jetzt die zweite
    Zusicherung unten: Ein Merkmalsverweis wird mit dem Eingangsobjekt
    aufgelöst (``orphans.references`` nimmt ``operation.inputs[0]``), also
    zeigt er ins Leere, wenn es keines gibt.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    named = {
        (spec.name, entry.name)
        for spec in REGISTRY.all()
        for entry in spec.params.spec()
        if entry.name == "at_feature"
    }
    declared = {
        (spec.name, entry.name)
        for spec in REGISTRY.all()
        for entry in spec.params.spec()
        if entry.kind == "feature"
    }

    assert named, "otherwise this test proves nothing"
    assert named <= declared, "a parameter that names a feature declares kind='feature'"

    without_input = sorted(
        spec.name
        for spec in REGISTRY.all()
        if spec.consumes < 1 and any(entry.kind == "feature" for entry in spec.params.spec())
    )
    assert not without_input, "a feature reference is resolved against the input object"
