"""Ein Modell, das sagt, was man ihm aufgetragen hat (Bauplan §35, §40).

Die Agenten-Suite muss die Mechanik prüfen, nicht das Wetter: trägt der
Kontext die Auswahl, ist ein Vorschlag genau eine Transaktion, nimmt ein Undo
ihn wirklich zurück. Nichts davon braucht ein Sprachmodell, und es gegen eines
laufen zu lassen machte die Suite langsam, teuer und wackelig zugleich.

Also fährt die Suite dieses Backend. Es antwortet aus einem Skript und behält
alles, wonach es gefragt wurde — so kann ein Test behaupten, dass Steckbrief,
Prüfbericht und Regelsammlung das Modell wirklich erreicht haben.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.backends.llm import Message, Reply

Answer = Reply | Callable[[Sequence[Message]], Reply]


@dataclass(slots=True)
class ScriptedBackend:
    """Gibt vorbereitete Antworten aus und schreibt das Gespräch mit."""

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
        """Was dem Modell bei der letzten Anfrage über die Welt gesagt wurde."""
        if not self.seen:
            return ""
        return " ".join(entry.content for entry in self.seen[-1] if entry.role == "system")
