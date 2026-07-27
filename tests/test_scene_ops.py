"""The scene operations, run through the real stack and evaluation (§25)."""

from __future__ import annotations

import pytest

from app.core.registry import REGISTRY, Registry, op_params, param, register_op
from app.core.scene import History, OperationDraft, evaluate
from app.core.types import BaseParams, Document, OpContext, OpResult, Profile, SceneObject
from app.i18n import _
from tests.conftest import FakeMesh


@op_params
class StartParams(BaseParams):
    name: str = param(title=_("Name"), default="Halterung")


@pytest.fixture
def registry() -> Registry:
    """The real scene operations plus a stand-in for the load step, which is P0 later."""
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

    for name in ("rename_object", "duplicate_object"):
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
    assert (spec.consumes, spec.produces) == (1, 2)
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

    assert list(result.scene.objects) == ["obj_2", "obj_3"]
    assert result.scene.objects["obj_2"].name == "Halterung"
    assert result.scene.objects["obj_3"].name.startswith("Halterung (")
    assert result.scene.objects["obj_3"].created_by == 2


def test_the_copy_can_be_named(document: Document, profile: Profile, registry: Registry) -> None:
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Duplizieren"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={"name": "Zweites Teil"})],
    )

    result = evaluate(document, profile, registry=registry)
    assert result.scene.objects["obj_3"].name == "Zweites Teil"


def test_the_copy_carries_its_own_feature_table(
    document: Document, profile: Profile, registry: Registry
) -> None:
    history = History(document, registry)
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Duplizieren"), [OperationDraft(op="duplicate_object", inputs=("obj_1",))])

    result = evaluate(document, profile, registry=registry)
    original = result.scene.objects["obj_2"]
    copy = result.scene.objects["obj_3"]
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
