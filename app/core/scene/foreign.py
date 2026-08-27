"""Was eine fremde Projektdatei mitbringt, das nicht nur Geometrie ist
(Bauplan §32).

Projektdateien wandern zwischen Leuten — als Fehlerbericht (§37.2), als
Beispiel, als Auftrag. Zwei Dinge darin sind mehr als Zahlen: **Quelltext**,
der beim Auswerten ein fremdes Programm startet, und **Verweise nach außen**
auf Dateien, die nicht im Container liegen.

Ein Pfad aus dem Container hinaus wird beim Lesen abgelehnt. Was §32
zusätzlich verlangt, ist das hier: dass jemand es **erfährt**, bevor er die
Datei rechnen lässt — wer eine Datei aus einer E-Mail öffnet, soll nicht erst
im Verlauf entdecken, was darin steckt.

**Die erste Hälfte davon ist seit dem 26.08.2026 gegenstandslos, und das ist
eine gute Nachricht.** Bis dahin durfte eine Projektdatei Quelltext tragen,
der beim Auswerten OpenSCAD startete; geprüft war er (Regel 11), angesagt war
er auch, aber eine geprüfte Ausführung ist immer noch eine Ausführung. Mit dem
OpenSCAD-Ausbau ist die einzige Operation entfallen, die das tat. Die
Maschinerie dafür bleibt trotzdem stehen — siehe :data:`SCRIPTED_OPS`.

Der Hinweis ist ein Befund, kein Riegel: Solidon stellt sich nicht zwischen
den Nutzer und seine eigene Datei (Regel 19). Er sagt, was drin ist und wo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.core.types import Document, Finding
from app.i18n import _

if TYPE_CHECKING:
    from app.core.knowledge.parts.registry import PartRegistry

#: Operationen, die beim Auswerten ein fremdes Programm starten.
#:
#: **Heute keine, und das ist der Zweck dieser Zeile.** Bis zum 26.08.2026
#: stand hier ``create_from_scad``; mit dem OpenSCAD-Ausbau ist sie entfallen,
#: und damit hat eine Projektdatei keinen Weg mehr, etwas auszuführen.
#:
#: Eine leere Menge sieht nach totem Code aus, und die Versuchung ist, alles
#: darunter mitzunehmen. Dagegen stehen drei Gründe. Erstens ist die Aussage
#: eine über den **Bestand**, nicht über das **Format**: Ein Parameterwert ist
#: eine Zeichenkette, und was einmal Quelltext war, kann es wieder werden —
#: der Weg zurück ist eine Zeile im Register. Zweitens hängen drei Sperren
#: daran (:func:`runs_foreign_source`), und sie neu zu erfinden kostet mehr,
#: als sie stehen zu lassen. Drittens ist die Rekursion darunter teuer
#: erarbeitet: Sie geht durch Rezepte hindurch, weil ein Rezept einen solchen
#: Schritt tragen durfte und dann ``insert_<name>`` hieß.
#:
#: Was sich damit umkehrt, ist die **Prüfung**. Vorher hielt
#: ``test_every_op_that_runs_openscad_is_named`` die Liste an das Register
#: gebunden; heute sichert ``test_no_operation_runs_foreign_source`` zu, dass
#: sie leer **bleibt**, und die Maschinerie darunter wird an einer Attrappe
#: geprüft statt an einer echten Operation. Eine leere Menge prüft sonst
#: nichts mehr und meldet trotzdem grün.
SCRIPTED_OPS: frozenset[str] = frozenset()


def runs_foreign_source(name: str, parts: PartRegistry | None = None) -> bool:
    """Ob diese Operation beim Auswerten fremden Quelltext ausführt (§32).

    **Gefragt wird, was eine Operation tut, nicht wie sie heißt.** Ein
    **Rezept** durfte einen ``create_from_scad``-Schritt tragen (Regel 13), und
    es hieß dann ``insert_<name>`` — wer nur den Namen verglich, sah daran
    vorbei. Seit dem OpenSCAD-Ausbau ist :data:`SCRIPTED_OPS` leer und die
    Antwort überall ``False``; warum die Frage trotzdem gestellt wird, steht
    dort.

    **Und die Frage geht beliebig tief.** ``recipe.capture`` nimmt beliebige
    registrierte Operationen auf, also auch ein ``insert_A``: Rezept B trägt
    den Quelltext dann mittelbar, und seine eigene Schrittliste nennt nur
    ``insert_A``. Eine Prüfung über genau eine Ebene bot es über die Leitung
    an (:mod:`app.core.agent.remote`), ließ es ohne Rückfrage übernehmen
    (:func:`~app.core.agent.apply.auto_acceptable`) und schwieg im
    Prüfbericht.

    Der Zyklenwächter über die besuchten Namen ist kein Zierat: Zwei Rezepte,
    die einander einsetzen, sind eine Datei, die ankommen kann — hier hinge
    sonst das Öffnen.

    Regel 11 bleibt davon unberührt, der Quelltext wird vor jedem Lauf
    geprüft. Regel 13 sagt aber, dass die zwei Regeln nur zusammen halten: Was
    fremden Code startet, wird angesagt und nicht ferngesteuert, gleich unter
    welchem Namen es im Register steht.

    Die **eine** Stelle für diese Frage. Drei Aufrufer hängen daran —
    :func:`findings_for` für eine Projektdatei, ``knowledge.parts.check`` für
    einen benutzten Baustein und ``agent.tools.runs_foreign_source`` für die
    beiden Sperren der Agentenschicht; drei Kopien wären am Tag nach der
    nächsten Verschachtelung wieder auseinander.
    """
    return _scripted(name, parts, set())


def _scripted(name: str, parts: PartRegistry | None, seen: set[str]) -> bool:
    """Der rekursive Teil — ``seen`` hält den Weg fest, den wir schon gingen."""
    if name in SCRIPTED_OPS:
        return True
    if name in seen:
        return False
    seen.add(name)
    steps = _recipe_steps(name, parts)
    return any(_scripted(str(entry.get("op", "")), parts, seen) for entry in steps)


def _recipe_steps(name: str, parts: PartRegistry | None) -> tuple[Any, ...]:
    """Die Schritte des Rezepts hinter einem Operationsnamen.

    Leer für alles, was kein Rezept ist: Ein Baustein ohne Rezeptdaten rechnet
    gegen ``manifold3d`` und trägt keinen Quelltext (Checkliste „neuer
    Baustein"). Der Präfix kommt aus ``ops.op_name`` selbst — eine zweite
    Kopie von ``"insert_"`` wäre eine zweite Wahrheit.
    """
    from app.core.knowledge.parts.ops import op_name
    from app.core.knowledge.parts.registry import PARTS

    source = parts if parts is not None else PARTS
    prefix = op_name("")
    if not name.startswith(prefix):
        return ()
    part = name[len(prefix) :]
    if not source.has(part):
        return ()
    data = source.get(part).recipe_data
    if data is None:
        return ()
    steps = dict(data).get("document", {}).get("ops", ())
    return tuple(entry for entry in steps if isinstance(entry, dict))


def findings_for(document: Document) -> list[Finding]:
    """Was an dieser Datei erklärt gehört, bevor sie gerechnet wird (§32).

    Leere Liste heißt: nichts als Geometrie und Zahlen.
    """
    findings: list[Finding] = []

    scripted = [operation for operation in document.ops if runs_foreign_source(operation.op)]
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
