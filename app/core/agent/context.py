"""What the agent gets to see (Bauplan §26.1).

Five things, and each one for a reason:

* the **digest** (§23) with parameters and the current selection — without the
  selection "make that hole bigger" points at nothing;
* the **report** including the fallback stages that carried an operation — the
  agent has to know what it is standing on (§17.3);
* the **history in short form** — without it "take that back" cannot be acted on;
* the **valid chat turns** (§26.3), not the raw log: a turn whose transaction was
  undone travels along as "verworfen" at most;
* the **rule set** in its current version (§39), inside the system prompt.

Nothing here is clever. It is a text, and being able to read it is the point:
what the model was told has to be checkable by a person.
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

#: How many turns of the conversation travel along at most.
HISTORY_LIMIT = 12


def build_messages(
    request: str,
    document: Document,
    scene: Scene,
    *,
    selection: tuple[ObjectId, str] | None = None,
    rule_set: rules.RuleSet | None = None,
) -> list[Message]:
    """The whole context as the backend takes it."""
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
    """Digest, report and history in one block."""
    parts = [f"{tr('Szene und Verlauf')}:", digest(scene, document, selection)]
    report = report_text(scene.report)
    if report:
        parts.append(report)
    return "\n".join(parts)


def report_text(report: Report) -> str:
    """The findings, with the fallback stage that produced them (§17.3, §26.1)."""
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
    """The valid turns (§26.3).

    A turn whose transaction is no longer in the document was taken back. It is
    not dropped — the agent would argue in circles — but it travels as one line
    saying that it was discarded, and its content stays out.
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
    """Whether a turn was taken back — the surface greys it out (§26.3)."""
    if entry.transaction_id is None:
        return False
    return entry.transaction_id not in {transaction.id for transaction in document.transactions}
