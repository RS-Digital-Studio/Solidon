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


@pytest.mark.parametrize("fields", [("missing",), ("diameter",), ("liner", "liner")])
def test_material_dependencies_name_distinct_material_fields(fields: tuple[str, ...]) -> None:
    """Eine falsch deklarierte Profilabhängigkeit darf keine Cachezusage vortäuschen."""

    @op_params
    class MaterialParams(BaseParams):
        liner: str = param(title=_("Material"), kind="material", default="")
        diameter: float = param(title=_("Durchmesser"), default=5.0)

    with pytest.raises(InternalError, match="material profile parameters"):
        register_op(
            name="material_probe",
            title=_("Prüfkörper"),
            category="primitive",
            params=MaterialParams,
            consumes=0,
            material_params=fields,
            registry=Registry(),
        )(lambda ctx: OpResult(outputs=[]))


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


@pytest.mark.parametrize("consumes, minimum", [(VARIABLE, -1), (0, 2), (1, 2)])
def test_an_invalid_input_minimum_is_rejected(
    registry: Registry, consumes: int, minimum: int
) -> None:
    """Eine Untergrenze darf den deklarativen Vertrag nicht widersprüchlich machen."""
    from dataclasses import replace

    original = registry.get("scatter_pins")
    registry.remove(original.name)
    with pytest.raises(InternalError):
        registry.register(replace(original, consumes=consumes, minimum_inputs=minimum))


def test_variable_counts_are_readable_in_the_reference(registry: Registry) -> None:
    """Die interne Markierung -1 ist keine Körperzahl für den Nutzer."""
    from dataclasses import replace

    original = registry.get("scatter_pins")
    registry.remove(original.name)
    registry.register(replace(original, consumes=VARIABLE, minimum_inputs=2, produces=VARIABLE))
    reference = documentation(registry)
    assert "Objekte: ≥ 2 → …" in reference
    assert "Objekte: -1" not in reference


def test_customer_documentation_keeps_the_controls_without_the_api(registry: Registry) -> None:
    """Die Bedienhilfe erklärt die Handlung, ohne ihre Aufrufschlüssel zu zeigen."""
    text = documentation(registry, technical=False)

    assert "### Bohrung ändern\n" in text
    assert "Ändert den Durchmesser einer erkannten Bohrung." in text
    assert "**Ort:**" in text
    assert "Kürzel `Ctrl+Shift+B`" in text
    assert "Gilt für: Bohrung" in text
    assert "Durchmesser" in text and "0,1" in text and "mm" in text
    for internal in (
        "resize_hole",
        "diameter",
        "Objekte:",
        "umkehrbar",
        "ohne Zufall",
        "Startwert",
    ):
        assert internal not in text


def test_documentation_remains_technical_by_default(registry: Registry) -> None:
    """CLI und technische Aufrufer behalten ihre vollständige Referenz."""
    text = documentation(registry)

    assert text == documentation(registry, technical=True)
    assert "### Bohrung ändern (`resize_hole`)" in text
    assert "Durchmesser `diameter`" in text
    assert "Objekte: 1 → 1" in text
    assert "umkehrbar" in text and "mit Startwert" in text


@pytest.mark.parametrize(
    "description",
    [
        "# Stifte verteilen\n\nZusätzlicher Hinweis.",
        "## Stifte verteilen\n\nZusätzlicher Hinweis.",
        "### Stifte verteilen\n\nZusätzlicher Hinweis.",
        "  ### Stifte verteilen\n\nZusätzlicher Hinweis.",
        "Stifte verteilen\n===\n\nZusätzlicher Hinweis.",
        "Stifte verteilen\n---\n\nZusätzlicher Hinweis.",
    ],
)
def test_customer_description_headings_stay_below_the_operation(
    registry: Registry, description: str
) -> None:
    """Rezeptbeschreibungen dürfen keinen anderen Referenzeintrag vortäuschen."""
    import re
    from dataclasses import replace

    from app.core import markup

    first = registry.get("resize_hole")
    second = registry.get("scatter_pins")
    registry.remove(first.name)
    registry.remove(second.name)
    registry.register(replace(first, doc=description))
    registry.register(replace(second, category=first.category))
    customer = documentation(registry, technical=False)
    assert re.findall(r"^### (.+)$", customer, re.MULTILINE) == [
        "Bohrung ändern",
        "Stifte verteilen",
    ]
    assert "#### Stifte verteilen" in customer
    assert "Zusätzlicher Hinweis." in customer
    html = markup.to_html(customer)
    assert html.count("<h4>Stifte verteilen</h4>") == 1
    assert "<h5>Stifte verteilen</h5>" in html
    assert description in documentation(registry), "technische Ausgabe bleibt unverändert"


def test_description_heading_levels_keep_their_order_and_leave_code_alone() -> None:
    """Unterpunkte bleiben Unterpunkte; Codebeispiele werden nicht umgeschrieben."""
    from app.core import markup

    body = "# Eins\n\n## Zwei\n\n### Drei\n\n```text\n### Beispiel\n```\n"
    shown = markup.below_heading(body, 3)
    assert "#### Eins" in shown and "##### Zwei" in shown and "###### Drei" in shown
    assert "```text\n### Beispiel\n```" in shown
    html = markup.to_html(shown)
    assert "<pre><code>### Beispiel</code></pre>" in html
    assert "<h4>Beispiel</h4>" not in html
    assert markup.below_heading("Mehrzeiliger\nHinweis\n===", 3) == "#### Mehrzeiliger Hinweis"
    assert markup.below_heading("Ein Absatz.\n\n---", 3) == "Ein Absatz.\n\n---"


def test_customer_parameter_table_names_choices_and_their_conditions() -> None:
    """Vorgabe, Auswahl und abhängige Felder sprechen wie derselbe Dialog."""
    from app.core.registry.surfaces import parameter_table
    from app.core.types import ParamSpec

    schema = (
        ParamSpec("kind", "enum", "Art", default="circular", choices=("linear", "circular")),
        ParamSpec("enabled", "bool", "Nutzen", default=True, depends_on=("kind", ("circular",))),
        ParamSpec(
            "span",
            "float",
            "Abstand",
            default=2.5,
            unit="mm",
            minimum=0.2,
            doc="Von Mitte zu Mitte.",
            depends_on=("enabled", (True,)),
        ),
        ParamSpec("armature", "armature", "Skelett", default="", placement="advanced"),
        ParamSpec("faces", "features", "Flächen", default=()),
    )
    customer = "\n".join(parameter_table(schema, technical=False))
    technical = "\n".join(parameter_table(schema))

    assert "Kreisförmig" in customer
    assert "Geradlinig, Kreisförmig" in customer
    assert "Gilt bei Art = Kreisförmig." in customer
    assert "Gilt bei angehaktem Nutzen." in customer
    assert "Von Mitte zu Mitte." in customer
    assert "2,5" in customer and "0,2" in customer and "mm" in customer
    assert "| Skelett |" in customer, "ein wirklicher Editor ist kein internes Übergabefeld"
    assert "`" not in customer and "circular" not in customer and "linear" not in customer
    assert "()" not in customer
    assert "Art `kind`" in technical and "linear, circular" in technical
    assert "Flächen `faces`" in technical and "()" in technical
    assert "Gilt bei Art = circular." in technical


def test_choice_names_are_shared_and_measurements_keep_the_ui_formatter() -> None:
    """Eine Tabelle, aber im Fenster weiterhin dessen Einheit und Zahlenschreibweise."""
    from app.core.registry import surfaces

    pytest.importorskip("PySide6")
    from app.ui import labels

    assert labels._CHOICE_NAMES is surfaces._CHOICE_NAMES
    assert surfaces.choice_label("circular") == labels.choice_label("circular") == "Kreisförmig"
    assert surfaces.choice_label("M4") == "M4"
    assert surfaces.choice_label("608") == "608 · 8,00 × 22,00 × 7,00 mm"

    previous = labels.display_unit()
    try:
        labels.set_display_unit("in")
        assert labels.choice_label("608") == (
            f"608 · {labels.length(8.0, with_unit=False)} × "
            f"{labels.length(22.0, with_unit=False)} × {labels.length(7.0)}"
        )
    finally:
        labels.set_display_unit(previous)


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


def test_the_twin_rule_takes_the_set_itself_as_its_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Zwilling ohne seinen Partner in der Menge bleibt darin stehen.

    Die Regel stand am 07.09.2026 dreimal in zwei Fassungen — bedingt in
    ``ObjectTree.operations_for_feature``, unbedingt (``spec.name not in
    MENU_TWINS``) in ``operations_for_object`` und zweimal in
    ``selection_operations``. Die bedingte trug die Begründung im eigenen
    Docstring: „Ein Zwilling, dessen Partner für diese Merkmalsart gar nicht
    gilt, wäre sonst spurlos weg statt zusammengelegt."

    **Dass heute keine Handlung verschwindet, war gemessen und kein Beweis für
    die Regel:** Bei allen vier Paaren ist der sichtbare Partner entweder
    ebenfalls draußen (Erzeuger, ``consumes = 0``) oder in derselben Klasse
    und damit dabei. Ein Test über den heutigen Registerstand könnte den
    Unterschied deshalb nicht sehen. Gepflanzt wird er hier: ein fünftes Paar,
    dessen sichtbarer Partner in der Menge fehlt.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import MENU_TWINS, shown_of_twins

    load_operations()
    drill = REGISTRY.get("drill_hole")
    hollow = REGISTRY.get("hollow_object")

    # Ohne Zwillingseintrag bleiben beide.
    assert {spec.name for spec in shown_of_twins((drill, hollow))} == {
        "drill_hole",
        "hollow_object",
    }

    # Mit Partner in der Menge fällt der versteckte heraus — das ist der Fall,
    # für den es die Tabelle gibt.
    monkeypatch.setitem(MENU_TWINS, "drill_hole", "hollow_object")
    assert {spec.name for spec in shown_of_twins((drill, hollow))} == {"hollow_object"}

    # **Und ohne Partner bleibt er stehen.** Die unbedingte Fassung hätte ihn
    # hier weggelassen, und die Handlung wäre spurlos verschwunden statt
    # zusammengelegt.
    monkeypatch.setitem(MENU_TWINS, "drill_hole", "gibt_es_in_dieser_menge_nicht")
    assert {spec.name for spec in shown_of_twins((drill, hollow))} == {
        "drill_hole",
        "hollow_object",
    }


@pytest.mark.parametrize(
    "sizes, limit, fixed, keep, ranking, expected",
    [
        ({"only": 20}, 12, 0, (), {}, []),
        ({"only": 20}, 12, 1, (), {}, ["only"]),
        ({"a": 1, "b": 1}, 1, 0, (), {}, []),
        ({"a": 5, "b": 4}, 9, 0, (), {}, []),
        ({"a": 5, "b": 4}, 8, 0, (), {"a": 0, "b": 1}, ["b"]),
        ({"a": 5, "b": 4}, 8, 0, ("b",), {"a": 0, "b": 1}, ["a"]),
        ({"a": 5, "b": 4}, 8, 0, (), {}, ["a"]),
        ({"b": 5, "a": 5}, 9, 0, (), {}, ["a"]),
        ({"a": 5, "b": 5, "c": 5}, 8, 0, (), {"a": 0, "b": 1, "c": 2}, ["c", "b"]),
        ({"a": 5, "b": 5, "c": 5}, 8, 0, ("c",), {"a": 0, "b": 1, "c": 2}, ["b", "a"]),
        ({"b": 5, "a": 5, "c": 4}, 6, 0, (), {}, ["a", "b"]),
    ],
)
def test_menu_folding_keeps_rank_ties_and_protected_groups(
    sizes: dict[str, int],
    limit: int,
    fixed: int,
    keep: tuple[str, ...],
    ranking: dict[str, int],
    expected: list[str],
) -> None:
    """Die kleinste nötige Faltung bleibt bei Rang, Gleichstand und Schutz eindeutig."""
    from app.core.registry.surfaces import folded_groups

    assert (
        folded_groups(sizes, limit, fixed, keep, rank=lambda name: ranking.get(name, 0)) == expected
    )
