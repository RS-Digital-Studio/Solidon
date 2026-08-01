"""Einen Vorschlag annehmen und zurücknehmen (Bauplan §26.5, AGENTS.md
Regel 16).

Ein Vorschlag wird **eine** Transaktion. Alles, was er will — Operationen,
Parameter, Passungen — landet gemeinsam oder gar nicht, und ein Undo nimmt
alles davon zurück. Parameter und Passungen sind keine Operationen, also
trägt der Vorschlag mit, was sie vorher waren; genau das macht das Undo
vollständig statt beinahe vollständig.

Der Chat-Eintrag entsteht ebenfalls hier, und er benennt die Transaktion
(§26.3). Geht die Transaktion, gilt der Eintrag als verworfen — und das hält
den Agenten davon ab, mit einem Zustand zu argumentieren, den es nicht mehr
gibt.
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
    """Legt den Vorschlag als eine Transaktion ins Dokument.

    Gibt die Transaktion zurück — oder None, wenn der Vorschlag nur geantwortet
    hat.
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
    """Wirft einen Vorschlag weg. Das Gespräch behält beide Beiträge (§26.3)."""
    record(document, proposal, None, discarded=True)


def undo(proposal: Proposal, history: History, transaction_id: str | None) -> None:
    """Nimmt einen angenommenen Vorschlag vollständig zurück — auch das, was
    keine Op war.
    """
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
    """Schreibt beide Beiträge des Austauschs ins Projekt (§26.3)."""
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
    """Nimmt zurück bis einschließlich einer Transaktion. Undo ist ein
    Stapel: zu einem älteren Eintrag zu kommen heißt, die neueren mitzunehmen —
    und das zu sagen ist besser, als so zu tun, als ließe sich ein einzelner
    Eintrag aus der Mitte herauspflücken.
    """
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
