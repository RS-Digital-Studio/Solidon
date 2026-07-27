"""Operation registry (Bauplan §10): the single declaration every surface reads."""

from app.core.registry.params import json_schema, op_params, param, validate
from app.core.registry.registry import (
    CATEGORIES,
    FEATURE_KINDS,
    REGISTRY,
    MenuSection,
    OperationSpec,
    Registry,
    register_op,
)
from app.core.registry.surfaces import (
    CliArgument,
    CliCommand,
    PaletteEntry,
    cli_commands,
    context_menu,
    documentation,
    menu_tree,
    palette_entries,
    tool_schemas,
)

__all__ = [
    "CATEGORIES",
    "FEATURE_KINDS",
    "REGISTRY",
    "CliArgument",
    "CliCommand",
    "MenuSection",
    "OperationSpec",
    "PaletteEntry",
    "Registry",
    "cli_commands",
    "context_menu",
    "documentation",
    "json_schema",
    "menu_tree",
    "op_params",
    "palette_entries",
    "param",
    "register_op",
    "tool_schemas",
    "validate",
]
