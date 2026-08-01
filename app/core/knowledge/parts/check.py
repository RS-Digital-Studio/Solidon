"""Was gesagt werden muss, wenn ein Projekt geöffnet wird (Bauplan §24.4,
§24.5).

Die Bibliothek ist Teil der Art, wie ein Projekt gerechnet wurde. Ein
korrigierter Baustein darf ein altes Projekt darum nicht still anders
nachrechnen — Leitprinzip 4 wäre gebrochen, und niemand bemerkte es.

Also stellt das Öffnen einer Datei zwei Fragen: welche der Bausteine, die
dieses Projekt benutzt, sich seither geändert haben, und welche davon diese
Installation gar nicht hat. Das erste ist ein Hinweis mit einer Wahl, das
zweite hält die Auswertung an (§15.2).
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
    """Befunde für den Prüfbericht, wenn ein Projekt hereinkommt."""
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
    """Hält die Bibliotheksversion im Projekt fest — passiert beim
    Speichern (§16.2).
    """
    document.parts_version = LIBRARY_VERSION
