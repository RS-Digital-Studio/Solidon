"""A model that says what it was told to say (Bauplan §35, §40).

The agent suite has to check the harness, not the weather: does the context
carry the selection, is a proposal exactly one transaction, does an undo really
take it back. None of that needs a language model, and running it against one
would make the suite slow, expensive and flaky at the same time.

So the suite drives this backend. It answers from a script and keeps everything
it was asked, which is how a test can assert that the digest, the report and the
rule set actually reached the model.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.backends.llm import Message, Reply

Answer = Reply | Callable[[Sequence[Message]], Reply]


@dataclass(slots=True)
class ScriptedBackend:
    """Hands out prepared answers and records the conversation."""

    answers: list[Answer] = field(default_factory=list)
    model: str = "scripted"
    seen: list[list[Message]] = field(default_factory=list)
    """Every request, in order — the suite reads the context out of this."""
    tools_seen: list[tuple[str, ...]] = field(default_factory=list)

    @property
    def id(self) -> str:
        return "scripted"

    @property
    def available(self) -> bool:
        return True

    def complete(
        self,
        messages: Sequence[Message],
        tools: Sequence[dict[str, Any]] = (),
        *,
        temperature: float = 0.0,
    ) -> Reply:
        self.seen.append(list(messages))
        self.tools_seen.append(tuple(str(entry.get("name", "")) for entry in tools))
        if not self.answers:
            return Reply(text="", model=self.model, stop_reason="end_turn")
        answer = self.answers.pop(0)
        reply = answer(messages) if callable(answer) else answer
        return Reply(
            text=reply.text,
            tool_calls=reply.tool_calls,
            model=reply.model or self.model,
            stop_reason=reply.stop_reason or ("tool_use" if reply.tool_calls else "end_turn"),
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
        )

    @property
    def last_system_prompt(self) -> str:
        """What the model was told about the world on the last request."""
        if not self.seen:
            return ""
        return " ".join(entry.content for entry in self.seen[-1] if entry.role == "system")
