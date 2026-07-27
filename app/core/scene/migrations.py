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
FORMAT_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class Step:
    """One step of the chain, from one version to the next."""

    from_version: int
    to_version: int
    apply: Callable[[dict[str, Any]], dict[str, Any]]


#: All known steps, oldest first. Empty until the format changes for the first time.
MIGRATIONS: Final[tuple[Step, ...]] = ()


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
