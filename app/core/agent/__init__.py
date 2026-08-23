"""Die Agentenschicht: Kontextaufbau, Werkzeuge, Transaktionskopplung (§26).

Der Agent ist kein Chatbot mit angehängtem 3D-Programm. Er arbeitet mit genau
den Operationen, die der Nutzer hat, sieht genau, was der Nutzer sieht, und
alles, was er tut, kommt als eine Transaktion an, die ein einziges Undo
zurücknimmt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from app.core.lazy import install

if TYPE_CHECKING:
    from app.core.agent.apply import accept, discard, record
    from app.core.agent.context import build_messages, is_discarded, system_prompt
    from app.core.agent.proposal import Proposal, Question
    from app.core.agent.session import AgentSession
    from app.core.agent.tools import EXTRA_TOOLS, tool_schemas

#: Welcher Name in welchem Untermodul steht — geladen wird erst beim
#: Zugriff, damit zwei Threads sich nicht über die Modul-Locks
#: verklemmen (:mod:`app.core.lazy`).
_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "accept": ("apply", "accept"),
    "discard": ("apply", "discard"),
    "record": ("apply", "record"),
    "build_messages": ("context", "build_messages"),
    "is_discarded": ("context", "is_discarded"),
    "system_prompt": ("context", "system_prompt"),
    "Proposal": ("proposal", "Proposal"),
    "Question": ("proposal", "Question"),
    "AgentSession": ("session", "AgentSession"),
    "EXTRA_TOOLS": ("tools", "EXTRA_TOOLS"),
    "tool_schemas": ("tools", "tool_schemas"),
}

install(__name__, _EXPORTS)

__all__ = [
    "EXTRA_TOOLS",
    "AgentSession",
    "Proposal",
    "Question",
    "accept",
    "build_messages",
    "discard",
    "is_discarded",
    "record",
    "system_prompt",
    "tool_schemas",
]
