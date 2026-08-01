"""Die Agentenschicht: Kontextaufbau, Werkzeuge, Transaktionskopplung (§26).

Der Agent ist kein Chatbot mit angehängtem 3D-Programm. Er arbeitet mit genau
den Operationen, die der Nutzer hat, sieht genau, was der Nutzer sieht, und
alles, was er tut, kommt als eine Transaktion an, die ein einziges Undo
zurücknimmt.
"""

from app.core.agent.apply import accept, discard, record
from app.core.agent.context import build_messages, is_discarded, system_prompt
from app.core.agent.proposal import Proposal, Question
from app.core.agent.session import AgentSession
from app.core.agent.tools import EXTRA_TOOLS, tool_schemas

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
