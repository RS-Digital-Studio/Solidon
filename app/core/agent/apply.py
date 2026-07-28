"""Accepting and taking back a proposal (Bauplan §26.5, AGENTS.md rule 16).

A proposal becomes **one** transaction. Everything it wants — operations,
parameters, fits — lands together or not at all, and one undo takes all of it
back. Parameters and fits are not operations, so the proposal carries what they
were before it ran; that is what makes the undo complete rather than nearly
complete.

The chat entry is written here as well, and it names the transaction (§26.3).
When the transaction goes, the entry counts as discarded — which is what keeps
the agent from arguing with a state that no longer exists.
"""

from __future__ import annotations

import secrets

from app.core.agent.proposal import Proposal
from app.core.log import get_logger
from app.core.scene.history import History
from app.core.types import ChatEntry, Document, Transaction
from app.i18n import tr

_log = get_logger(__name__)


def accept(proposal: Proposal, history: History) -> Transaction | None:
    """Put the proposal into the document as one transaction.

    Returns the transaction, or None when the proposal only answered.
    """
    document = history.document

    if proposal.undo_of is not None:
        _undo_named(history, proposal.undo_of)

    for name, parameter in proposal.parameters.items():
        proposal.previous_parameters.setdefault(name, document.parameters.get(name))
        document.parameters[name] = parameter

    if proposal.fits:
        if proposal.previous_fits is None:
            proposal.previous_fits = list(document.fits)
        for fit in proposal.fits:
            document.fits.append(fit)

    transaction: Transaction | None = None
    if proposal.drafts:
        transaction = history.apply(_title(proposal), proposal.drafts, origin=proposal.origin)

    record(document, proposal, transaction)
    _log.info("proposal accepted as %s", transaction.id if transaction else "no transaction")
    return transaction


def discard(proposal: Proposal, document: Document) -> None:
    """Throw a proposal away. The conversation keeps both turns (§26.3)."""
    record(document, proposal, None, discarded=True)


def undo(proposal: Proposal, history: History, transaction_id: str | None) -> None:
    """Take an accepted proposal back completely — including what was not an op."""
    document = history.document
    if transaction_id is not None:
        _undo_named(history, transaction_id)

    for name, previous in proposal.previous_parameters.items():
        if previous is None:
            document.parameters.pop(name, None)
        else:
            document.parameters[name] = previous
    if proposal.previous_fits is not None:
        document.fits[:] = list(proposal.previous_fits)


def record(
    document: Document,
    proposal: Proposal,
    transaction: Transaction | None,
    discarded: bool = False,
) -> tuple[ChatEntry, ChatEntry]:
    """Write both turns of the exchange into the project (§26.3)."""
    question = ChatEntry(id=_identifier(), role="user", text=proposal.request)
    answer = ChatEntry(
        id=_identifier(),
        role="agent",
        text=proposal.answer or proposal.summary(),
        transaction_id=None if discarded else (transaction.id if transaction else None),
        origin=proposal.origin,
    )
    document.chat.extend([question, answer])
    return question, answer


def _undo_named(history: History, transaction_id: str) -> None:
    """Undo back to and including one transaction. Undo is a stack, so getting
    to an older entry means taking the newer ones with it — and saying so is
    better than pretending a single entry can be plucked out of the middle."""
    while history.document.transactions:
        last = history.document.transactions[-1]
        history.undo()
        if last.id == transaction_id:
            return


def _title(proposal: Proposal) -> str:
    summary = proposal.summary()
    return f"{tr('Vorschlag')}: {summary}" if summary else tr("Vorschlag")


def _identifier() -> str:
    return f"c{secrets.token_hex(4)}"
