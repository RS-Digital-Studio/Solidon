"""One proposal, one transaction (Bauplan §26.5, AGENTS.md rule 16).

Everything an agent turn wants to change is collected here and applied in one
go — or not at all. That is what makes "one undo takes it back" true instead of
aspirational, and it is why the operations are gathered rather than applied one
by one while the model is still talking.

Parameters and fits are not operations, so a transaction alone would not undo
them. The proposal therefore carries what they were before it ran, and taking
it back restores exactly that.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.scene.history import OperationDraft
from app.core.types import Finding, Fit, Origin, Parameter, ParameterName, TransactionId


@dataclass(slots=True)
class Question:
    """One thing the agent asked instead of guessing (§26.2)."""

    text: str
    options: tuple[str, ...] = ()
    answer: str | None = None


@dataclass(slots=True)
class Proposal:
    """What one request produced, before anyone accepted it."""

    request: str
    answer: str = ""
    drafts: list[OperationDraft] = field(default_factory=list)
    parameters: dict[ParameterName, Parameter] = field(default_factory=dict)
    """Parameters the proposal wants to add or change."""
    fits: list[Fit] = field(default_factory=list)
    undo_of: TransactionId | None = None
    questions: list[Question] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    """What the check after each operation found (§26.5)."""
    origin: Origin = field(default_factory=lambda: Origin(by="agent"))
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    stopped: str = ""
    """Set when a limit ended the run: ``steps`` or ``tokens`` (§26.5)."""

    previous_parameters: dict[ParameterName, Parameter | None] = field(default_factory=dict)
    previous_fits: list[Fit] | None = None

    @property
    def changes_geometry(self) -> bool:
        return bool(self.drafts)

    @property
    def empty(self) -> bool:
        """A proposal that only answered — nothing to accept, nothing to undo."""
        return not (self.drafts or self.parameters or self.fits or self.undo_of)

    @property
    def asked(self) -> bool:
        return bool(self.questions)

    def summary(self) -> str:
        """One line for the history entry and the chat."""
        if self.answer:
            return self.answer.strip().splitlines()[0]
        if self.drafts:
            return ", ".join(draft.op for draft in self.drafts)
        return ""
