"""Registerkonsistenz über die Operationen, die die Anwendung wirklich
ausliefert (§35).

Jede Operation erscheint in jeder Oberfläche, trägt ein Schema, übersetzte Texte
und einen Test; Kürzel sind eindeutig; nicht-deterministische Operationen
benutzen einen Startwert.

Solange der Katalog noch gefüllt wird, laufen diese Prüfungen über wenige
Operationen — sie beißen in dem Moment, in dem eine unvollständig hinzukommt.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from app.core.registry import (
    CATEGORIES,
    FEATURE_KINDS,
    REGISTRY,
    OperationSpec,
    cli_commands,
    documentation,
    menu_tree,
    palette_entries,
    tool_schemas,
)

TESTS_DIR = Path(__file__).parent


def registered() -> list[OperationSpec]:
    return list(REGISTRY.all())


def ids(spec: OperationSpec) -> str:
    return spec.name


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_operation_is_completely_declared(spec: OperationSpec) -> None:
    assert str(spec.title).strip(), f"{spec.name} has no title"
    assert str(spec.doc).strip(), f"{spec.name} has no documentation text"
    assert spec.category in CATEGORIES
    assert all(kind in FEATURE_KINDS for kind in spec.applies_to)
    assert spec.params.spec() is not None


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_every_parameter_says_what_it_does(spec: OperationSpec) -> None:
    """Ein Titel ist eine Beschriftung, keine Erklärung (§2.4).

    „Spiel [mm]" über einem Zahlenfeld sagt nicht, wovon dieses Spiel abgezogen
    wird und was passiert, wenn es null ist. Der Satz dahinter wird zum Tooltip
    im Dialog und zur Spalte *Bedeutung* im Handbuch — beide leer zu lassen ist
    die stille Art, eine Operation unbenutzbar zu machen.
    """
    for entry in spec.params.spec():
        text = str(entry.doc or "")
        assert text.strip(), f"{spec.name}.{entry.name} has no help text"
        assert text.strip() != str(entry.title).strip(), (
            f"{spec.name}.{entry.name} only repeats its title"
        )


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_non_deterministic_operations_use_a_seed(spec: OperationSpec) -> None:
    if spec.deterministic:
        return
    source = inspect.getsource(spec.fn)
    assert "seed" in source, f"{spec.name} is marked non-deterministic but never reads ctx.seed"


@pytest.mark.parametrize("spec", registered(), ids=ids)
def test_every_operation_has_a_test(spec: OperationSpec) -> None:
    """Eine neue Operation ohne Test ist nicht fertig (AGENTS.md, Checkliste)."""
    mentions = [
        path.name
        for path in TESTS_DIR.rglob("test_*.py")
        if path.name != Path(__file__).name and spec.name in path.read_text(encoding="utf-8")
    ]
    assert mentions, f"no test mentions {spec.name}"


def test_shortcuts_are_unique() -> None:
    shortcuts = [spec.shortcut.casefold() for spec in registered() if spec.shortcut]
    assert len(shortcuts) == len(set(shortcuts))


def test_every_operation_reaches_every_surface() -> None:
    names = {spec.name for spec in registered()}
    assert {spec.name for section in menu_tree() for spec in section.entries} == names
    assert {entry.name for entry in palette_entries()} == names
    assert {command.name for command in cli_commands()} == names
    assert {schema["name"] for schema in tool_schemas()} == names
    text = documentation()
    assert all(f"`{name}`" in text for name in names)
