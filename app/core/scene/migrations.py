"""Format versions and the migration chain (Bauplan §16.2).

Same version: load. Older: run the chain. Newer: decline in a friendly way
instead of loading half of it — a file from a newer release may contain
operations this one does not know.

Migration steps are never merged together (AGENTS.md, checklist "Dateiformat
ändern"): each one keeps its own function, its own test and its own checked-in
example file, so a chain from the very first version keeps working.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from app.core.errors import ValidationError
from app.core.log import get_logger
from app.i18n import _

_log = get_logger(__name__)

#: Current version of ``project.json``.
FORMAT_VERSION: Final = 3


@dataclass(frozen=True, slots=True)
class Step:
    """One step of the chain, from one version to the next."""

    from_version: int
    to_version: int
    apply: Callable[[dict[str, Any]], dict[str, Any]]


def _add_chat(data: dict[str, Any]) -> dict[str, Any]:
    """1 → 2: the conversation moved into the project (§26.3).

    A file from before the agent simply has no conversation, and an empty list
    says exactly that. Nothing else changes, which is why this step is its own
    function and stays one forever.
    """
    data.setdefault("chat", [])
    return data


def _mark_generated_sources(data: dict[str, Any]) -> dict[str, Any]:
    """2 → 3: a source carries how it was generated (§27, pillar B).

    Sources from before pillar B were all imported or built from parts, so the
    two new fields are empty for every one of them. What the step really does
    is state that on the way in, rather than leaving a file that looks like it
    lost its prompt somewhere.
    """
    for source in data.get("sources", {}).values():
        if source.get("type") == "generated":
            source.setdefault("origin", {}).setdefault("prompt", "")
    return data


#: All known steps, oldest first.
MIGRATIONS: Final[tuple[Step, ...]] = (
    Step(from_version=1, to_version=2, apply=_add_chat),
    Step(from_version=2, to_version=3, apply=_mark_generated_sources),
)


def migrate(
    data: dict[str, Any],
    target: int = FORMAT_VERSION,
    steps: Sequence[Step] = MIGRATIONS,
) -> dict[str, Any]:
    """Bring a document up to ``target``, or say why that is not possible."""
    version = int(data.get("format_version", 0))
    if version == target:
        return data
    if version > target:
        raise ValidationError(
            field="format_version",
            detail=_(
                "Diese Datei stammt aus einer neueren Fassung des Programms. Ein Update öffnet sie."
            ),
            constraint="too_new",
            values={"file_version": version, "supported": target},
        )

    by_source = {step.from_version: step for step in steps}
    current = data
    while version < target:
        step = by_source.get(version)
        if step is None:
            raise ValidationError(
                field="format_version",
                detail=_("Für diese Dateiversion fehlt der Umstellungsschritt."),
                constraint="no_migration",
                values={"file_version": version, "supported": target},
            )
        _log.info("migrating project from %d to %d", step.from_version, step.to_version)
        current = step.apply(dict(current))
        current["format_version"] = step.to_version
        version = step.to_version
    return current
