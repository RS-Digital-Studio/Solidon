"""Agent layer: context assembly, tools, transaction coupling (§26).

The agent is not a chat bot with a 3D program attached. It works with exactly
the operations the user has, sees exactly what the user sees, and everything it
does arrives as one transaction that a single undo takes back.
"""

from app.core.agent.apply import accept, discard, record, undo
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
    "undo",
]
