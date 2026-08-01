"""Was der Agent zu sehen bekommt (Bauplan §26.1).

Fünf Dinge, jedes aus einem Grund:

* der **Steckbrief** (§23) mit Parametern und der aktuellen Auswahl — ohne die
  Auswahl zeigt „mach das Loch größer" auf nichts;
* der **Prüfbericht** samt der Rückfallstufen, die eine Operation getragen
  haben — der Agent muss wissen, worauf er steht (§17.3);
* der **Verlauf in Kurzform** — ohne ihn lässt sich „nimm das zurück" nicht
  ausführen;
* die **gültigen Chatbeiträge** (§26.3), nicht das rohe Protokoll: ein Beitrag,
  dessen Transaktion zurückgenommen wurde, reist höchstens als „verworfen" mit;
* die **Regelsammlung** in ihrer aktuellen Version (§39), im Systemprompt.

Nichts hier ist raffiniert. Es ist ein Text, und dass man ihn lesen kann, ist
der Punkt: was dem Modell gesagt wurde, muss für einen Menschen nachprüfbar
sein.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.core.backends.llm import Message
from app.core.knowledge import rules
from app.core.perceive.digest import digest
from app.core.types import ChatEntry, Document, ObjectId, Report, Scene
from app.i18n import tr

from app.core.agent.prompt import system_prompt  # isort: skip

__all__ = ["build_messages", "conversation", "system_prompt", "world_text"]

#: Wie viele Gesprächsbeiträge höchstens mitreisen.
HISTORY_LIMIT = 12


def build_messages(
    request: str,
    document: Document,
    scene: Scene,
    *,
    selection: tuple[ObjectId, str] | None = None,
    rule_set: rules.RuleSet | None = None,
) -> list[Message]:
    """Der ganze Kontext, so wie das Backend ihn nimmt."""
    messages = [
        Message(role="system", content=system_prompt(rule_set)),
        Message(role="user", content=world_text(document, scene, selection)),
    ]
    messages.extend(conversation(document.chat, document))
    messages.append(Message(role="user", content=request))
    return messages


def world_text(
    document: Document,
    scene: Scene,
    selection: tuple[ObjectId, str] | None = None,
) -> str:
    """Steckbrief, Prüfbericht und Verlauf in einem Block."""
    parts = [f"{tr('Szene und Verlauf')}:", digest(scene, document, selection)]
    report = report_text(scene.report)
    if report:
        parts.append(report)
    return "\n".join(parts)


def report_text(report: Report) -> str:
    """Die Befunde, mit der Rückfallstufe, die sie erzeugt hat (§17.3, §26.1)."""
    if not report.findings:
        return ""
    lines = [f"{tr('Prüfbericht')}:"]
    for finding in report.findings:
        marker = {"error": "!!", "warning": "!", "info": "-"}[finding.severity]
        values = ", ".join(f"{key}={value}" for key, value in finding.values.items())
        lines.append(
            f"  {marker} {finding.code}: {finding.message}" + (f" ({values})" if values else "")
        )
    return "\n".join(lines)


def conversation(entries: Sequence[ChatEntry], document: Document) -> list[Message]:
    """Die gültigen Beiträge (§26.3).

    Ein Beitrag, dessen Transaktion nicht mehr im Dokument steht, wurde
    zurückgenommen. Er fällt nicht weg — der Agent argumentierte im Kreis —,
    aber er reist als eine Zeile mit, die sagt, dass er verworfen wurde, und
    sein Inhalt bleibt draußen.
    """
    active = {transaction.id for transaction in document.transactions}
    messages: list[Message] = []
    for entry in list(entries)[-HISTORY_LIMIT:]:
        discarded = entry.transaction_id is not None and entry.transaction_id not in active
        if discarded:
            messages.append(
                Message(
                    role="assistant" if entry.role == "agent" else "user",
                    content=f"[{tr('verworfen')}]",
                )
            )
            continue
        messages.append(
            Message(role="assistant" if entry.role == "agent" else "user", content=entry.text)
        )
    return messages


def is_discarded(entry: ChatEntry, document: Document) -> bool:
    """Ob ein Beitrag zurückgenommen wurde — die Oberfläche graut ihn
    aus (§26.3).
    """
    if entry.transaction_id is None:
        return False
    return entry.transaction_id not in {transaction.id for transaction in document.transactions}
