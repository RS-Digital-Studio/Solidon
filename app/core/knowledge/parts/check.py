"""What has to be said when a project is opened (Bauplan §24.4, §24.5).

The library is part of the way a project was computed. A corrected part must
therefore not quietly recompute an old project differently — Leitprinzip 4 would
be broken and nobody would notice.

So opening a file asks two questions: which of the parts this project uses have
changed since, and which of them does this installation not have at all. The
first is a note with a choice, the second stops the evaluation (§15.2).
"""

from __future__ import annotations

from app.core.knowledge.parts.registry import (
    LIBRARY_VERSION,
    PARTS,
    PartRegistry,
    changed_since_library,
    used_parts,
)
from app.core.log import get_logger
from app.core.types import Document, Finding
from app.i18n import _

_log = get_logger(__name__)


def check(document: Document, registry: PartRegistry | None = None) -> list[Finding]:
    """Findings for the report when a project comes in."""
    source = registry or PARTS
    used = used_parts(document.ops)
    if not used:
        return []

    findings: list[Finding] = []
    missing = tuple(name for name in used if not source.has(name))
    if missing:
        findings.append(
            Finding(
                code="parts.missing",
                severity="error",
                message=_("Dieses Projekt benutzt Bausteine, die es hier nicht gibt."),
                values={"parts": ", ".join(missing)},
            )
        )

    changed = changed_since_library(document.parts_version, used, source)
    if changed:
        findings.append(
            Finding(
                code="parts.changed",
                severity="info",
                message=_("Seit dem Speichern haben sich benutzte Bausteine geändert."),
                values={
                    "parts": ", ".join(changed),
                    "saved": document.parts_version,
                    "now": LIBRARY_VERSION,
                },
            )
        )
    if findings:
        _log.info("part check: %d findings", len(findings))
    return findings


def stamp(document: Document) -> None:
    """Record the library version in the project — done on saving (§16.2)."""
    document.parts_version = LIBRARY_VERSION
