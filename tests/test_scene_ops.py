"""Die Szenen-Operationen, durch den echten Stapel und die Auswertung
gefahren (§25).
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.registry import REGISTRY, VARIABLE, Registry, op_params, param, register_op
from app.core.scene import History, OperationDraft, evaluate
from app.core.types import BaseParams, Document, OpContext, OpResult, Profile, SceneObject
from app.i18n import _
from tests.conftest import FakeMesh


@op_params
class StartParams(BaseParams):
    name: str = param(title=_("Name"), default="Halterung")


@pytest.fixture
def registry() -> Registry:
    """Die echten Szenen-Operationen plus einen Platzhalter für den
    Ladeschritt, der später P0 ist.
    """
    own = Registry()

    @register_op(
        name="make_object",
        title=_("Objekt erzeugen"),
        category="scene",
        params=StartParams,
        consumes=0,
        produces=1,
        doc=_("Platzhalter für die Eingangsstufe."),
        registry=own,
    )
    def make(ctx: OpContext) -> OpResult:
        return OpResult(
            outputs=[SceneObject(id="", name=ctx.params.name, mesh=FakeMesh())]  # type: ignore[attr-defined,arg-type]
        )

    for name in ("rename_object", "duplicate_object", "delete_object"):
        own.register(REGISTRY.get(name))
    return own


def test_rename_object_is_registered_completely() -> None:
    spec = REGISTRY.get("rename_object")
    assert spec.category == "scene"
    assert (spec.consumes, spec.produces) == (1, 1)
    assert spec.shortcut == "F2"
    assert str(spec.doc)


def test_duplicate_object_is_registered_completely() -> None:
    spec = REGISTRY.get("duplicate_object")
    assert spec.category == "scene"
    assert spec.consumes == 1
    assert spec.produces == VARIABLE, "how many depends on the count that was asked for"
    assert spec.produces_from == "count", "and the stack has to know where that is written"
    assert spec.shortcut == "Ctrl+D"
    assert str(spec.doc)


def test_renaming_keeps_the_object_and_its_geometry(
    document: Document, profile: Profile, registry: Registry
) -> None:
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    before = evaluate(document, profile, registry=registry).scene.objects["obj_1"]

    history.apply(
        _("Umbenennen"),
        [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Deckel"})],
    )
    result = evaluate(document, profile, registry=registry)

    assert result.complete
    assert list(result.scene.objects) == ["obj_1"], "renaming does not create a second object"
    assert result.scene.objects["obj_1"].name == "Deckel"
    assert result.scene.objects["obj_1"].mesh == before.mesh


def test_duplicating_yields_original_and_copy(
    document: Document, profile: Profile, registry: Registry
) -> None:
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Duplizieren"), [OperationDraft(op="duplicate_object", inputs=("obj_1",))])

    result = evaluate(document, profile, registry=registry)

    assert list(result.scene.objects) == ["obj_1", "obj_2"]
    assert result.scene.objects["obj_1"].name == "Halterung"
    assert result.scene.objects["obj_2"].name.startswith("Halterung (")
    assert result.scene.objects["obj_2"].created_by == 2


def test_the_original_keeps_the_id_it_had_before_the_copy(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """Das Duplizieren legt etwas dazu — es tauscht nicht aus.

    Der Stapel vergab für jeden Ausgang einer Operation mit ``produces_from``
    eine frische Kennung, auch für den Eingang, den die Operation unverändert
    zurückgibt. Die Auswertung räumte ihn daraufhin weg, weil er nicht mehr
    unter den Ausgaben stand: Aus ``obj_1`` wurden ``obj_2`` und ``obj_3``.

    Für den Nutzer hieß das, dass seine Auswahl das Duplizieren nicht
    überlebte — der nächste Schritt auf denselben Körper endete in „Der
    gewählte Körper ist nicht mehr da", und zwar für einen Körper, der
    unverändert vor ihm stand.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    before = evaluate(document, profile, registry=registry).scene.objects["obj_1"]

    history.apply(_("Duplizieren"), [OperationDraft(op="duplicate_object", inputs=("obj_1",))])
    result = evaluate(document, profile, registry=registry)

    assert "obj_1" in result.scene.objects, "the body the user had selected is still there"
    assert result.scene.objects["obj_1"].mesh == before.mesh

    # Und der Beweis, dass die Kennung trägt: eine Operation auf dieselbe
    # Auswahl wird angenommen, statt sie als verschwunden zurückzuweisen.
    history.apply(
        _("Umbenennen"),
        [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Deckel"})],
    )
    assert evaluate(document, profile, registry=registry).scene.objects["obj_1"].name == "Deckel"


def test_the_copy_can_be_named(document: Document, profile: Profile, registry: Registry) -> None:
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Duplizieren"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"name": "Zweites Teil"})],
    )

    result = evaluate(document, profile, registry=registry)
    assert result.scene.objects["obj_2"].name == "Zweites Teil"


def test_the_copy_carries_its_own_feature_table(
    document: Document, profile: Profile, registry: Registry
) -> None:
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Duplizieren"), [OperationDraft(op="duplicate_object", inputs=("obj_1",))])

    result = evaluate(document, profile, registry=registry)
    original = result.scene.objects["obj_1"]
    copy = result.scene.objects["obj_2"]
    assert original.features is not copy.features
    assert original.material_slots is not copy.material_slots


def test_undo_takes_the_rename_back(
    document: Document, profile: Profile, registry: Registry
) -> None:
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Umbenennen"),
        [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Deckel"})],
    )
    history.undo()

    result = evaluate(document, profile, registry=registry)
    assert result.scene.objects["obj_1"].name == "Halterung"


# --- Eine Stückzahl gehört in den Stapel, nicht in den Dateinamen ----------------


def test_ten_of_a_part_is_one_operation(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """§25: „Clippy_Filament-Clip_x10" ist eine Stückzahl, die niemand mehr
    ändern kann.

    Hier ist sie eine Zahl in einem Schritt des Stapels — zehn Objekte aus
    einer Operation, statt neun Duplizierungen, die danach niemand mehr lesen
    kann.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Vervielfachen"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 10})],
    )

    result = evaluate(document, profile, registry=registry)

    assert len(result.scene.objects) == 10
    assert len({entry.name for entry in result.scene.objects.values()}) == 10, "ten names, not one"


def test_another_count_is_also_one_step_back_and_forward(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """Sechs statt drei, auf dem langen Weg: zurücknehmen und neu anwenden.

    ``change_params`` ist der kurze Weg und tut dasselbe, wo nichts von den
    Objekten abhängt. Dieser Pfad bleibt getestet, weil er der ist, der noch
    funktioniert, wenn doch etwas abhängt.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Vervielfachen"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 3})],
    )
    assert len(evaluate(document, profile, registry=registry).scene.objects) == 3

    history.undo()
    history.apply(
        _("Vervielfachen"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 6})],
    )

    assert len(evaluate(document, profile, registry=registry).scene.objects) == 6


def test_a_count_of_one_leaves_it_at_one(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """Kein Fehler: ein Duplikat von eins ist das Objekt, und der Stapel darf
    das sagen.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Vervielfachen"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 1})],
    )

    assert len(evaluate(document, profile, registry=registry).scene.objects) == 1


def test_a_count_that_has_to_be_calculated_is_refused(
    document: Document, registry: Registry
) -> None:
    """§13: die IDs werden vergeben, bevor ein Ausdruck aufgelöst ist."""
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])

    with pytest.raises(ValidationError) as problem:
        history.apply(
            _("Vervielfachen"),
            [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": "=@n"})],
        )

    assert problem.value.constraint == "not_a_number"


# --- Eine Operation des Stapels lässt sich korrigieren (§15.4) -------------------


def test_a_parameter_can_be_changed_afterwards(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """Was den Stapel zum Stapel macht: ein Name, zwei Buchstaben anders, ist
    kein Schritt zum Zurücknehmen und Neu-Tun.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Umbenennen"),
        [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Deckel"})],
    )

    history.change_params(2, {"name": "Deckel A"})

    result = evaluate(document, profile, registry=registry)
    assert result.complete
    assert result.scene.objects["obj_1"].name == "Deckel A"


def test_only_the_named_parameters_change(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """Alles nicht Genannte behält seinen Wert — ein Dialog darf ein Feld
    schicken.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Vervielfachen"),
        [
            OperationDraft(
                op="duplicate_object", inputs=("obj_1",), params={"count": 3, "name": "Klemme"}
            )
        ],
    )

    history.change_params(2, {"count": 3})

    assert history.operation(2).params["name"] == "Klemme"


def test_an_unknown_parameter_is_refused(document: Document, registry: Registry) -> None:
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])

    with pytest.raises(ValidationError) as problem:
        history.change_params(1, {"gibtesnicht": 1})

    assert problem.value.constraint == "unknown"


def test_the_count_may_change_while_nothing_uses_the_objects(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """Zehn statt drei, auf dem letzten Schritt des Stapels: neue IDs, kein
    Schaden.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Vervielfachen"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 3})],
    )

    history.change_params(2, {"count": 10})

    assert len(evaluate(document, profile, registry=registry).scene.objects) == 10


def test_a_count_that_later_steps_depend_on_is_not_changed_silently(
    document: Document, registry: Registry
) -> None:
    """Die IDs der neuen Körper sind nicht die alten.

    Eine spätere Operation zeigte auf Objekte, die es nicht mehr gibt, und ein
    Fehler am fernen Ende des Stapels über eine Zahl, die am nahen Ende
    geändert wurde, ist einer, den niemand mit dem verbindet, was er getan hat.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Vervielfachen"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 2})],
    )
    later = history.operation(2).outputs[-1]
    history.apply(
        _("Umbenennen"),
        [OperationDraft(op="rename_object", inputs=(later,), params={"name": "Zweites"})],
    )

    with pytest.raises(ValidationError) as problem:
        history.change_params(2, {"count": 5})

    assert problem.value.constraint == "count_in_use"


def test_changing_a_parameter_discards_what_was_undone(
    document: Document, registry: Registry
) -> None:
    """§15.4: Verzweigungen gibt es nicht, und ein Redo auf einen geänderten
    Stapel wäre eine.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Umbenennen"),
        [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Deckel"})],
    )
    history.undo()
    assert history.can_redo

    history.change_params(1, {"name": "Grundplatte"})

    assert not history.can_redo


def test_an_operation_that_is_not_there_says_so(document: Document, registry: Registry) -> None:
    history = History(document, registry)

    with pytest.raises(ValidationError):
        history.change_params(99, {"name": "x"})


def test_a_count_outside_the_range_never_reaches_the_document(
    document: Document, registry: Registry
) -> None:
    """Der Fund der Durchsicht: die IDs werden vergeben, bevor der Bereich
    geprüft ist.

    Fünf Millionen waren in einer Sekunde fünf Millionen IDs im Dokument, und
    die deklarierte Grenze von hundert kam zu spät, um das zu stoppen — die
    Validierung läuft dort, wo die Szene gerechnet wird, und da hat der Stapel
    sie längst hingeschrieben.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])

    with pytest.raises(ValidationError) as problem:
        history.apply(
            _("Vervielfachen"),
            [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": 5_000_000})],
        )

    assert problem.value.constraint == "range"
    assert len(document.ops) == 1, "and nothing was written"


def test_the_declared_maximum_is_the_limit(document: Document, registry: Registry) -> None:
    """Eine Wahrheit: die Zahl in der Deklaration, keine zweite im Stapel."""
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    highest = next(
        entry.maximum
        for entry in REGISTRY.get("duplicate_object").params.spec()
        if entry.name == "count"
    )

    history.apply(
        _("Vervielfachen"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"count": int(highest)})],
    )
    assert len(history.operation(2).outputs) == int(highest)

    with pytest.raises(ValidationError):
        history.change_params(2, {"count": int(highest) + 1})


# --- Entfernen (§25) ------------------------------------------------------------


def test_delete_object_is_registered_completely() -> None:
    spec = REGISTRY.get("delete_object")
    assert spec.category == "scene"
    assert (spec.consumes, spec.produces) == (1, 0), "nimmt eines, gibt keines zurück"
    assert spec.shortcut == "Del"
    assert str(spec.doc)


def test_deleting_takes_the_object_out_of_the_scene(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """Eine Operation ohne Ausgabe: die Auswertung räumt jeden Eingang weg, der
    nicht wieder herauskommt.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    assert set(evaluate(document, profile, registry=registry).scene.objects) == {"obj_1", "obj_2"}

    history.apply(_("Entfernen"), [OperationDraft(op="delete_object", inputs=("obj_1",))])
    result = evaluate(document, profile, registry=registry)

    assert set(result.scene.objects) == {"obj_2"}
    assert result.complete, "das Entfernen ist kein Abbruch"
    assert history.operation(3).outputs == ()


def test_an_undo_brings_the_object_back(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """Der Grund, warum Entfernen eine Operation ist und kein Löschen."""
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Entfernen"), [OperationDraft(op="delete_object", inputs=("obj_1",))])
    assert evaluate(document, profile, registry=registry).scene.objects == {}

    history.undo()
    assert set(evaluate(document, profile, registry=registry).scene.objects) == {"obj_1"}


def test_a_later_operation_on_a_deleted_object_is_refused(
    document: Document, registry: Registry
) -> None:
    """Der Körper ist keine Ausgabe mehr, also kennt der Stapel ihn nicht — und
    sagt das beim Anlegen, nicht erst am fernen Ende der Kette.
    """
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Entfernen"), [OperationDraft(op="delete_object", inputs=("obj_1",))])

    with pytest.raises(ValidationError) as problem:
        history.apply(
            _("Umbenennen"),
            [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Deckel"})],
        )
    assert problem.value.constraint == "unknown_object"


def test_a_ring_that_leaves_the_build_volume_is_refused_with_advice(
    profile: Profile, registry: Registry
) -> None:
    """Die Bauraumprüfung galt nur der Reihe — der Kranz meldete stattdessen
    Einzelwarnungen der Auswertung, ohne die zwei Handlungsvorschläge (Fund
    des Gesamtreviews vom 25.08.2026). Jetzt prüft er die Hülle aller Kopien.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled

    load_operations()
    document = Document(format_version=1, app_version="test")
    history = History(document, REGISTRY)
    history.apply(
        _("Anlegen"),
        [OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 10.0})],
    )
    history.apply(
        _("Verschieben"),
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 150.0})],
    )
    history.apply(
        _("Kranz"),
        [
            OperationDraft(
                op="pattern",
                inputs=("obj_1",),
                params={"kind": "circular", "count": 8, "angle": 360.0, "axis": "z"},
            )
        ],
    )
    result = evaluate(document, profile, registry=REGISTRY)
    assert result.stopped_at is not None, "der Kranz reicht über den Bauraum hinaus"
    texts = " ".join(f"{entry.code} {entry.values}" for entry in result.scene.report.findings)
    assert "needed_mm" in texts, "der Befund nennt, wie weit es hinausreicht"

    # **Und die zwei Handlungsvorschläge, die dem Fund den Namen gaben.**
    # Geprüft an der Operation selbst, mit dem Körper und dem Profil, an denen
    # die Kette eben angehalten hat: Die Auswertung macht aus der Ausnahme eine
    # Berichtszeile, und ein ``Finding`` hat kein Feld für Handlungen — dort
    # sind sie nicht mehr zu sehen. Ohne diese Frage prüft der Test genau die
    # Hälfte dessen, was sein eigener Docstring behauptet.
    spec = REGISTRY.get("pattern")
    with pytest.raises(ValidationError) as problem:
        spec.fn(
            OpContext(
                scene=result.scene,
                inputs=[result.scene.objects["obj_1"]],
                params=spec.params(kind="circular", count=8, angle=360.0, axis="z"),
                profile=profile,
                quality="fine",
                seed=None,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=NeverCancelled(),
            )
        )
    assert {"correct_input", "split_model"} <= {
        action.id for action in problem.value.suggestions
    }, f"Regel 17: nur {[action.id for action in problem.value.suggestions]}"


def test_a_writing_op_cannot_change_the_result_scene(
    document: Document, profile: Profile, registry: Registry
) -> None:
    """Regel 3 hatte weder Schutz noch Test — die einzige der 22 Regeln:
    eine schreibende Probe-Op änderte Parameter der Ergebnisszene (Fund des
    Gesamtreviews vom 25.08.2026). Die Kontext-Szene ist jetzt eine
    Lesekopie: Wer trotzdem schreibt, ändert sie und nicht das Ergebnis.
    """
    from app.core.types import Parameter

    @register_op(
        name="probe_writes_into_the_scene",
        title=_("Schreibprobe"),
        category="scene",
        params=StartParams,
        consumes=0,
        produces=1,
        doc=_("Nur für diesen Test."),
        registry=registry,
    )
    def probe(ctx: OpContext) -> OpResult:
        ctx.scene.parameters["smuggled"] = Parameter(name="smuggled", value=1.0)
        for entry in ctx.scene.objects.values():
            entry.features["smuggled_feature"] = None  # type: ignore[assignment]
            break
        return OpResult(
            outputs=[SceneObject(id="", name="Probe", mesh=FakeMesh())]  # type: ignore[arg-type]
        )

    document.parameters["real"] = Parameter(name="real", value=5.0)
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Schreibprobe"), [OperationDraft(op="probe_writes_into_the_scene")])

    result = evaluate(document, profile, registry=registry)
    assert result.complete
    assert "smuggled" not in result.scene.parameters, (
        "ein geschriebener Parameter darf die Ergebnisszene nie erreichen"
    )
    assert all(
        "smuggled_feature" not in entry.features for entry in result.scene.objects.values()
    ), "auch ein eingeschmuggeltes Merkmal bleibt in der Lesekopie"
