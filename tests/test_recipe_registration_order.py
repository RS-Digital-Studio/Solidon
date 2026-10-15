"""Rezeptwechsel erhalten die Folge der übrigen Registereinträge (CS-17, W13 Fund 7)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.core.bootstrap import load_operations
from app.core.knowledge.parts import ops as part_ops
from app.core.knowledge.parts import recipe
from app.core.knowledge.parts.registry import PartRegistry
from app.core.registry.registry import Registry
from tests.helpers import recipe_document_seed


@pytest.mark.parametrize("action", ["install", "replace", "remove", "restore"])
def test_recipe_changes_keep_registration_order(tmp_path: Path, action: str) -> None:
    """Die Dateihandlung kopiert beide Register in ihrer Einfügefolge, nicht alphabetisch.

    Zwei Einträge gegen das Alphabet machen den Unterschied sichtbar. Ein neuer
    oder ersetzter Eintrag steht hinten; das Entfernen lässt die übrigen stehen.
    Die Wiederherstellung bekommt ihren Rücknahmestand aus einem eigenen Register,
    damit eine falsche Entfernung ihre Eingangsreihenfolge nicht schon verändert.
    """
    load_operations()
    parts, operations = PartRegistry(), Registry()
    made = recipe.Recipe(
        name="m_probe",
        title="Probe",
        group="structure",
        document=recipe_document_seed(),
        features={"top": "face_top"},
    )
    for name in ("z_probe", "a_probe"):
        recipe.register(dataclasses.replace(made, name=name), parts, operations)

    if action == "install":
        recipe.install(made, parts, operations, tmp_path)
    elif action in {"replace", "remove"}:
        recipe.save(made, tmp_path)
        recipe.register(made, parts, operations)
        if action == "replace":
            recipe.replace(
                dataclasses.replace(made, doc="Neuer Stand"), parts, operations, tmp_path
            )
        else:
            recipe.remove_installed(made.name, parts, operations, tmp_path)
    else:
        removed_parts, removed_operations = PartRegistry(), Registry()
        recipe.save(made, tmp_path)
        recipe.register(made, removed_parts, removed_operations)
        removed = recipe.remove_installed(made.name, removed_parts, removed_operations, tmp_path)
        recipe.restore_installed(removed, made, parts, operations, tmp_path)

    expected = ["z_probe", "a_probe"]
    if action != "remove":
        expected.append("m_probe")
    assert [spec.name for spec in parts.in_registration_order()] == expected
    assert [spec.name for spec in operations.in_registration_order()] == [
        operation
        for name in expected
        for operation in (part_ops.op_name(name), part_ops.creator_name(name))
    ]
    assert [spec.name for spec in parts.all()] == sorted(expected)
    assert [spec.name for spec in operations.all()] == sorted(
        spec.name for spec in operations.in_registration_order()
    )
