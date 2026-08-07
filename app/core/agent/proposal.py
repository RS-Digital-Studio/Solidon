"""Ein Vorschlag, eine Transaktion (Bauplan §26.5, AGENTS.md Regel 16).

Alles, was ein Agentenzug ändern will, wird hier gesammelt und in einem Zug
angewandt — oder gar nicht. Genau das macht „ein Undo nimmt es zurück" wahr
statt bloß gewollt, und darum werden die Operationen gesammelt, statt einzeln
angewandt zu werden, während das Modell noch redet.

Parameter und Passungen sind keine Operationen, eine Transaktion allein nähme
sie also nicht zurück. Der Vorschlag trägt darum mit, was sie vorher waren,
und ihn zurückzunehmen stellt genau das wieder her.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.scene.history import OperationDraft
from app.core.types import Finding, Fit, Origin, Parameter, ParameterName, TransactionId


@dataclass(slots=True)
class Question:
    """Eine Sache, die der Agent gefragt hat, statt zu raten (§26.2)."""

    text: str
    options: tuple[str, ...] = ()
    answer: str | None = None


@dataclass(slots=True)
class Proposal:
    """Was eine Anfrage erzeugt hat, bevor jemand sie angenommen hat."""

    request: str
    answer: str = ""
    drafts: list[OperationDraft] = field(default_factory=list)
    parameters: dict[ParameterName, Parameter] = field(default_factory=dict)
    """Parameters the proposal wants to add or change."""
    fits: list[Fit] = field(default_factory=list)
    undo_of: TransactionId | None = None
    questions: list[Question] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    """Was die Prüfung nach jeder Operation gefunden hat (§26.5)."""
    origin: Origin = field(default_factory=lambda: Origin(by="agent"))
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    stopped: str = ""
    """Gesetzt, wenn eine Grenze den Lauf beendet hat: ``steps`` oder ``tokens`` (§26.5)."""

    @property
    def changes_geometry(self) -> bool:
        return bool(self.drafts)

    @property
    def empty(self) -> bool:
        """Ein Vorschlag, der nur geantwortet hat — nichts anzunehmen, nichts
        zurückzunehmen.
        """
        return not (self.drafts or self.parameters or self.fits or self.undo_of)

    @property
    def asked(self) -> bool:
        return bool(self.questions)

    def summary(self) -> str:
        """Eine Zeile für den Verlaufseintrag und den Chat."""
        if self.answer:
            return self.answer.strip().splitlines()[0]
        if self.drafts:
            return ", ".join(draft.op for draft in self.drafts)
        return ""
