"""Was eine fremde Projektdatei mitbringt, das nicht nur Geometrie ist
(Bauplan §32).

Projektdateien wandern zwischen Leuten — als Fehlerbericht (§33.3), als
Beispiel, als Auftrag. Zwei Dinge darin sind mehr als Zahlen: **Quelltext**,
der beim Auswerten ein fremdes Programm startet, und **Verweise nach außen**
auf Dateien, die nicht im Container liegen.

Beides ist erlaubt und beides ist geprüft — der OpenSCAD-Quelltext läuft nur
nach :func:`app.core.backends.openscad.check_source`, und ein Pfad aus dem
Container hinaus wird beim Lesen abgelehnt. Was §32 zusätzlich verlangt, ist
das hier: dass jemand es **erfährt**, bevor er die Datei rechnen lässt. Eine
geprüfte Ausführung ist immer noch eine Ausführung, und wer eine Datei aus
einer E-Mail öffnet, soll nicht erst im Verlauf entdecken, dass darin ein
Programm steckt.

Der Hinweis ist ein Befund, kein Riegel: Solidon stellt sich nicht zwischen
den Nutzer und seine eigene Datei (Regel 19). Er sagt, was drin ist und wo.
"""

from __future__ import annotations

from app.core.types import Document, Finding
from app.i18n import _

#: Operationen, die beim Auswerten ein fremdes Programm starten.
#:
#: Heute genau eine — dieselbe, die :mod:`app.core.agent.remote` aus demselben
#: Grund von der Fernbedienung ausschließt. Kommt eine zweite dazu, gehört sie
#: hierher; ``test_every_scripted_op_is_named`` hält die Liste an das Register
#: gebunden, damit sie nicht still veraltet.
SCRIPTED_OPS: frozenset[str] = frozenset({"create_from_scad"})


def findings_for(document: Document) -> list[Finding]:
    """Was an dieser Datei erklärt gehört, bevor sie gerechnet wird (§32).

    Leere Liste heißt: nichts als Geometrie und Zahlen.
    """
    findings: list[Finding] = []

    scripted = [operation for operation in document.ops if operation.op in SCRIPTED_OPS]
    if scripted:
        findings.append(
            Finding(
                code="project.scripted_source",
                severity="warning",
                message=_(
                    "Dieses Projekt enthält Quelltext, der beim Berechnen ein "
                    "externes Programm ausführt."
                ),
                values={
                    "operations": ", ".join(str(operation.id) for operation in scripted),
                    "count": len(scripted),
                },
            )
        )

    if document.chat:
        findings.append(
            Finding(
                code="project.carried_chat",
                severity="warning",
                message=_(
                    "Dieses Projekt bringt ein gespeichertes Gespräch mit. Es wird dem "
                    "Assistenten als Vorgeschichte gezeigt und kann Anweisungen enthalten, "
                    "die nicht von Ihnen stammen."
                ),
                values={"entries": len(document.chat)},
            )
        )

    external = [source for source in document.sources.values() if not source.embedded]
    if external:
        findings.append(
            Finding(
                code="project.external_source",
                severity="warning",
                message=_(
                    "Dieses Projekt verweist auf Dateien außerhalb des Containers. "
                    "Fehlt eine davon, hält die Auswertung an."
                ),
                values={
                    "sources": ", ".join(sorted(external_names(document))),
                    "count": len(external),
                },
            )
        )

    return findings


def external_names(document: Document) -> list[str]:
    """Die Namen der Quellen, die nicht im Container liegen."""
    return [identifier for identifier, source in document.sources.items() if not source.embedded]
