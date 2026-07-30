"""Everything that is generated from the registry (Bauplan §10).

| Output                | Derived from                       |
|-----------------------|------------------------------------|
| menu entry and dialog | title, category, parameter schema  |
| context menu          | applies_to                         |
| palette and shortcut  | title, doc, shortcut               |
| command line          | name, parameter schema             |
| agent tool schema     | name, doc, JSON schema             |
| documentation section | all of it                          |

Nothing here knows about Qt: these are data structures a surface renders.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.registry.params import json_schema
from app.core.registry.registry import (
    CATEGORIES,
    REGISTRY,
    MenuSection,
    OperationSpec,
    Registry,
)
from app.core.types import ParamSpec
from app.i18n import TranslatableText


def menu_tree(registry: Registry | None = None) -> tuple[MenuSection, ...]:
    """The menu, in catalogue order (§25)."""
    source = registry or REGISTRY
    return tuple(
        MenuSection(category=category, title=CATEGORIES[category], entries=entries)
        for category, entries in source.by_category().items()
    )


def context_menu(feature_kind: str, registry: Registry | None = None) -> tuple[OperationSpec, ...]:
    """What a click on a feature offers — the shortest way from seeing to doing (§2.6)."""
    return (registry or REGISTRY).for_feature(feature_kind)


@dataclass(frozen=True, slots=True)
class PaletteEntry:
    """One line of the command palette. The shortcut is shown, so it gets learned."""

    name: str
    title: TranslatableText | str
    category: str
    doc: TranslatableText | str
    shortcut: str | None = None


def palette_entries(registry: Registry | None = None) -> tuple[PaletteEntry, ...]:
    return tuple(
        PaletteEntry(
            name=spec.name,
            title=spec.title,
            category=spec.category,
            doc=spec.doc,
            shortcut=spec.shortcut,
        )
        for spec in (registry or REGISTRY).all()
    )


@dataclass(frozen=True, slots=True)
class CliArgument:
    """One command line option, derived from a parameter."""

    flag: str
    name: str
    kind: str
    required: bool
    help: str
    choices: tuple[str, ...] = ()
    default: Any = None


@dataclass(frozen=True, slots=True)
class CliCommand:
    """One command line command, derived from an operation."""

    name: str
    help: str
    arguments: tuple[CliArgument, ...]


def _help_text(spec: ParamSpec) -> str:
    text = str(spec.doc) if spec.doc is not None else str(spec.title)
    return f"{text} [{spec.unit}]" if spec.unit else text


def cli_commands(registry: Registry | None = None) -> tuple[CliCommand, ...]:
    """Commands out of the registry (ROADMAP P0: the CLI reads the same source)."""
    commands: list[CliCommand] = []
    for spec in (registry or REGISTRY).all():
        arguments = tuple(
            CliArgument(
                flag=f"--{entry.name.replace('_', '-')}",
                name=entry.name,
                kind=entry.kind,
                required=entry.required,
                help=_help_text(entry),
                choices=entry.choices,
                default=entry.default,
            )
            for entry in spec.params.spec()
        )
        commands.append(CliCommand(name=spec.name, help=str(spec.doc), arguments=arguments))
    return tuple(commands)


def tool_schemas(registry: Registry | None = None) -> tuple[dict[str, Any], ...]:
    """Tool descriptions for the agent (§26.2). Same schema as dialog and CLI."""
    return tuple(
        {
            "name": spec.name,
            "description": str(spec.doc) or str(spec.title),
            "input_schema": json_schema(spec.params),
        }
        for spec in (registry or REGISTRY).all()
    )


def documentation(registry: Registry | None = None, category: str = "") -> str:
    """Der Referenzteil der Dokumentation — erzeugt, nie von Hand geschrieben.

    Mit ``category`` nur ein Bereich. Das Handbuchfenster zeigt eine Kategorie
    je Seite und liest denselben Text, den die Kommandozeile ausgibt: eine
    zweite Quelle wäre eine, die veraltet.
    """
    lines: list[str] = []
    for name, entries in (registry or REGISTRY).by_category().items():
        if category and name != category:
            continue
        lines.append(f"## {CATEGORIES[name]}")
        lines.append("")
        for spec in entries:
            lines.append(f"### {spec.title} (`{spec.name}`)")
            lines.append("")
            if spec.doc:
                lines.append(str(spec.doc))
                lines.append("")
            facts = [
                f"Objekte: {spec.consumes} → {spec.produces}",
                "umkehrbar" if spec.reversible else "nicht umkehrbar",
                "deterministisch" if spec.deterministic else "mit Startwert",
            ]
            if spec.shortcut:
                facts.append(f"Kürzel `{spec.shortcut}`")
            if spec.applies_to:
                facts.append("Features: " + ", ".join(spec.applies_to))
            lines.append(" · ".join(facts))
            lines.append("")
            parameters = spec.params.spec()
            if parameters:
                lines.append("| Parameter | Einheit | Vorgabe | Bereich | Bedeutung |")
                lines.append("|---|---|---|---|---|")
                for entry in parameters:
                    span = ""
                    if entry.minimum is not None or entry.maximum is not None:
                        low = "" if entry.minimum is None else f"{entry.minimum:g}"
                        high = "" if entry.maximum is None else f"{entry.maximum:g}"
                        span = f"{low} … {high}"
                    if entry.choices:
                        span = ", ".join(entry.choices)
                    default = "erforderlich" if entry.required else f"{entry.default}"
                    lines.append(
                        f"| `{entry.name}` | {entry.unit or ''} | {default} | {span} | "
                        f"{entry.title} |"
                    )
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"
