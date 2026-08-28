"""Das Register der Operationen (Bauplan §10): die eine Deklaration, die jede
Oberfläche liest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from app.core.lazy import install

if TYPE_CHECKING:
    from app.core.registry.params import (
        AUTO_FROM_PROFILE_DOC,
        GATHERED_KINDS,
        NAME_DOC,
        json_schema,
        op_params,
        param,
        validate,
    )
    from app.core.registry.registry import (
        CATEGORIES,
        FEATURE_KINDS,
        MENU_GROUPS,
        MENU_TWINS,
        REGISTRY,
        TWIN_TOGGLES,
        VARIABLE,
        VARIANT_GROUPS,
        MenuSection,
        OperationSpec,
        Registry,
        group_for_variant,
        group_title,
        register_op,
        variant_members,
    )
    from app.core.registry.surfaces import (
        MAX_MENU_ROWS,
        CliArgument,
        CliCommand,
        PaletteEntry,
        caveat_line,
        cli_commands,
        context_menu,
        documentation,
        folded_categories,
        group_is_flat,
        menu_path,
        menu_tree,
        palette_entries,
        tool_schemas,
    )

#: Welcher Name in welchem Untermodul steht — geladen wird erst beim
#: Zugriff, damit zwei Threads sich nicht über die Modul-Locks
#: verklemmen (:mod:`app.core.lazy`).
_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "AUTO_FROM_PROFILE_DOC": ("params", "AUTO_FROM_PROFILE_DOC"),
    "GATHERED_KINDS": ("params", "GATHERED_KINDS"),
    "NAME_DOC": ("params", "NAME_DOC"),
    "json_schema": ("params", "json_schema"),
    "op_params": ("params", "op_params"),
    "param": ("params", "param"),
    "validate": ("params", "validate"),
    "CATEGORIES": ("registry", "CATEGORIES"),
    "FEATURE_KINDS": ("registry", "FEATURE_KINDS"),
    "MENU_GROUPS": ("registry", "MENU_GROUPS"),
    "MENU_TWINS": ("registry", "MENU_TWINS"),
    "REGISTRY": ("registry", "REGISTRY"),
    "TWIN_TOGGLES": ("registry", "TWIN_TOGGLES"),
    "VARIABLE": ("registry", "VARIABLE"),
    "VARIANT_GROUPS": ("registry", "VARIANT_GROUPS"),
    "MenuSection": ("registry", "MenuSection"),
    "OperationSpec": ("registry", "OperationSpec"),
    "Registry": ("registry", "Registry"),
    "group_title": ("registry", "group_title"),
    "variant_members": ("registry", "variant_members"),
    "register_op": ("registry", "register_op"),
    "MAX_MENU_ROWS": ("surfaces", "MAX_MENU_ROWS"),
    "CliArgument": ("surfaces", "CliArgument"),
    "CliCommand": ("surfaces", "CliCommand"),
    "PaletteEntry": ("surfaces", "PaletteEntry"),
    "caveat_line": ("surfaces", "caveat_line"),
    "cli_commands": ("surfaces", "cli_commands"),
    "context_menu": ("surfaces", "context_menu"),
    "documentation": ("surfaces", "documentation"),
    "group_for_variant": ("registry", "group_for_variant"),
    "group_is_flat": ("surfaces", "group_is_flat"),
    "folded_categories": ("surfaces", "folded_categories"),
    "menu_path": ("surfaces", "menu_path"),
    "menu_tree": ("surfaces", "menu_tree"),
    "palette_entries": ("surfaces", "palette_entries"),
    "tool_schemas": ("surfaces", "tool_schemas"),
}

install(__name__, _EXPORTS)

__all__ = [
    "AUTO_FROM_PROFILE_DOC",
    "CATEGORIES",
    "FEATURE_KINDS",
    "GATHERED_KINDS",
    "MAX_MENU_ROWS",
    "MENU_GROUPS",
    "MENU_TWINS",
    "NAME_DOC",
    "REGISTRY",
    "TWIN_TOGGLES",
    "VARIABLE",
    "VARIANT_GROUPS",
    "CliArgument",
    "CliCommand",
    "MenuSection",
    "OperationSpec",
    "PaletteEntry",
    "Registry",
    "caveat_line",
    "cli_commands",
    "context_menu",
    "documentation",
    "folded_categories",
    "group_for_variant",
    "group_is_flat",
    "group_title",
    "json_schema",
    "menu_path",
    "menu_tree",
    "op_params",
    "palette_entries",
    "param",
    "register_op",
    "tool_schemas",
    "validate",
    "variant_members",
]
