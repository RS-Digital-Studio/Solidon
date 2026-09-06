"""Einen Vorschlag annehmen und zurücknehmen (Bauplan §26.5, AGENTS.md
Regel 16).

Ein Vorschlag wird **eine** Transaktion. Alles, was er will — Operationen,
Parameter, Passungen — landet gemeinsam oder gar nicht, und ein Undo nimmt
alles davon zurück.

Parameter und Passungen sind keine Operationen. Das trug hier lange eine
eigene Buchführung: der Vorschlag merkte sich, was vorher galt, und eine
eigene ``undo``-Funktion legte es zurück. Sie war richtig und wurde nie
gerufen — die Oberfläche nimmt mit ``History.undo`` zurück, und das kannte
nur Operationen. Ein angenommener Vorschlag ging also zur Hälfte zurück,
gegen Regel 16.

Jetzt trägt die Transaktion selbst, was keine Operation war (§15.5). Damit
gibt es einen Weg zurück statt zwei, und der eine ist der, den jeder nimmt.

Der Chat-Eintrag entsteht ebenfalls hier, und er benennt die Transaktion
(§26.3). Geht die Transaktion, gilt der Eintrag als verworfen — und das hält
den Agenten davon ab, mit einem Zustand zu argumentieren, den es nicht mehr
gibt.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence

from app.core.agent.proposal import Proposal
from app.core.agent.tools import runs_foreign_source
from app.core.errors import CANCEL, AppError, UserError, ValidationError
from app.core.log import get_logger
from app.core.registry import REGISTRY, Registry
from app.core.scene.history import History, change_for
from app.core.types import (
    ChatEntry,
    Document,
    DocumentChange,
    Finding,
    Transaction,
    TransactionId,
)
from app.i18n import _, tr

_log = get_logger(__name__)


def auto_acceptable(proposal: Proposal, registry: Registry | None = None) -> bool:
    """Ob ein Vorschlag ohne Nachfrage übernommen werden darf (§26.5).

    §26.5 sagt „kann automatisch laufen", Regel 19 sagt „keine Bestätigung
    vor rücknehmbaren Handlungen" — vier enge Bedingungen entscheiden:
    ausschließlich umkehrbare Operationen, nichts, was fremden Quelltext
    ausführt, keine Warnungen oder Fehler in den Befunden, keine Rückfrage und
    kein angehaltener Lauf. Parameter, Passungen und das Druckziel sind
    unschädlich: sie reisen als ``DocumentChange``, ein Undo nimmt sie mit.

    **Die zweite Bedingung fragte nach dem Namen** und verglich mit
    ``create_from_scad``. Ein Rezept mit einem solchen Schritt hieß
    ``insert_<name>`` (Regel 13) und kam damit hindurch — eingesetzt ohne
    Rückfrage, mit einem OpenSCAD-Lauf darin. Gefragt wird seither, was die
    Operation tut (:func:`~app.core.agent.tools.runs_foreign_source`).

    Seit dem OpenSCAD-Ausbau am 26.08.2026 antwortet darauf keine Operation
    mehr mit Ja. Die Bedingung bleibt die zweite von vieren: Sie kostet einen
    Aufruf, und was sie zusichert, sichert sonst nichts zu.
    """
    source = registry or REGISTRY
    if proposal.empty or proposal.questions or proposal.stopped or proposal.undo_of:
        return False
    if any(finding.severity != "info" for finding in proposal.findings):
        return False
    for draft in proposal.drafts:
        if runs_foreign_source(draft.op):
            return False
        try:
            if not source.get(draft.op).reversible:
                return False
        except AppError:
            return False
    return True


def accept(proposal: Proposal, history: History) -> Transaction | None:
    """Legt den Vorschlag als eine Transaktion ins Dokument.

    Gibt die Transaktion zurück — oder None, wenn der Vorschlag nur geantwortet
    hat.
    """
    document = history.document

    if proposal.undo_of is not None:
        _refuse_mixed(proposal)
        _undo_named(history, proposal)

    # Die Vorher-Seite kommt aus dem Dokument, in das wirklich geschrieben
    # wird, nicht aus der Arbeitskopie, auf welcher der Agent gerechnet hat:
    # zwischen Vorschlag und Annahme liegt eine Entscheidung des Nutzers, und
    # in der Zeit kann sich etwas geändert haben.
    changes: DocumentChange | None = None
    if proposal.parameters or proposal.fits or proposal.print_target:
        printer, material = proposal.print_target or (None, None)
        changes = change_for(
            document,
            parameters=proposal.parameters or None,
            fits=[*document.fits, *proposal.fits] if proposal.fits else None,
            printer=printer,
            material=material,
        )

    transaction: Transaction | None = None
    if proposal.drafts:
        _refuse_shifted_numbering(proposal, history)
    if proposal.drafts or changes is not None:
        transaction = history.apply(
            _title(proposal), proposal.drafts, origin=proposal.origin, changes=changes
        )

    record(document, proposal, transaction)
    _log.info("proposal accepted as %s", transaction.id if transaction else "no transaction")
    return transaction


def _refuse_shifted_numbering(proposal: Proposal, history: History) -> None:
    """Hält an, wenn das Dokument seit dem Vorschlag Kennungen vergeben hat.

    Der Vorschlag wurde auf einer Arbeitskopie gerechnet, und die Kennungen
    seiner neuen Körper stehen in den Entwürfen — der zweite Schritt nennt
    den Körper, den der erste anlegt. Legte der Nutzer zwischen Vorschlag und
    Annahme selbst einen an, trug der die Kennung, die der Agent für seinen
    vorgesehen hatte: Angenommen verschob der Vorschlag den Quader des
    Nutzers und ließ seinen eigenen stehen (Gesamtreview 05.09.2026,
    CORE-01). Die Kennungen werden seither übernommen, wie sie gerechnet
    wurden — und ist eine davon inzwischen vergeben, wird nichts angewandt.
    """
    if history.outputs_still_free(proposal.drafts):
        return
    raise UserError(
        title=_("Das Projekt hat sich seit diesem Vorschlag verändert."),
        detail=_(
            "Seit der Anfrage sind Körper dazugekommen, und die Schritte des Vorschlags "
            "träfen andere als die, für die er gerechnet wurde. Angewandt wurde nichts — "
            "dieselbe Anfrage noch einmal gestellt rechnet auf dem jetzigen Stand."
        ),
        suggestions=(CANCEL,),
    )


def discard(proposal: Proposal, document: Document) -> None:
    """Wirft einen Vorschlag weg. Das Gespräch behält beide Beiträge (§26.3)."""
    record(document, proposal, None, discarded=True)


def undo_applied(history: History, transaction: TransactionId) -> bool:
    """Nimmt **genau diese** Transaktion zurück — oder gar nichts (§26.5).

    Für den Weg zurück aus der Übernommen-Leiste: Ein eindeutig umkehrbarer
    Vorschlag läuft ohne Rückfrage (Regel 19), und der Knopf daneben sagt
    „Rückgängig". Er meint **einen** Schritt, nämlich den, der gerade
    dagestanden hat.

    ``History.undo`` kennt diese Frage nicht: Es nimmt zurück, was oben liegt.
    Zwischen dem Klick und dem Zug kann aber etwas Neueres angewandt worden
    sein — vom Nutzer, von einem Fernaufruf, vom nächsten Agentenzug. Dann
    nähme ein blindes ``undo`` das Falsche zurück, und der Knopf hielte sein
    Versprechen nicht.

    ``True`` heißt: zurückgenommen. ``False`` heißt: Sie liegt nicht (mehr)
    obenauf, und es wurde **nichts** angefasst — der Aufrufer sagt dann, dass
    der Weg zurück jetzt über den Verlauf geht. Kein Fehler, denn falsch
    gemacht hat niemand etwas.
    """
    known = history.document.transactions
    if not known or known[-1].id != transaction:
        return False
    history.undo()
    return True


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
        discarded=discarded,
    )
    document.chat.extend([question, answer])
    return question, answer


def _refuse_mixed(proposal: Proposal) -> None:
    """Zurücknehmen und Anlegen gehören nicht in denselben Vorschlag (§15.4,
    Regel 16).

    Verzweigungen gibt es nicht: wer nach einem Undo etwas anwendet, verwirft
    den abgeschnittenen Zweig, und ``History.apply`` tut das über
    ``_forget_undone`` endgültig. Ein Vorschlag, der beides in einem Zug täte,
    ließe sich nicht mehr vollständig zurücknehmen — ein Undo brächte nur das
    Neue weg, das Zurückgenommene bliebe verloren. Die Oberfläche fragt in
    dieser Lage über ``History.discardable`` nach; der Agent kann das nicht,
    also macht er zwei Vorschläge daraus.
    """
    if not proposal.creates_something:
        return
    raise ValidationError(
        field="undo",
        detail=_(
            "Ein Vorschlag nimmt entweder zurück oder legt an — beides in einem Zug "
            "ließe sich nicht mehr vollständig zurücknehmen."
        ),
        constraint="undo_with_changes",
        values={"transaction": proposal.undo_of or ""},
    )


def sweep_for(document: Document, transaction_id: str) -> tuple[TransactionId, ...]:
    """Welche Transaktionen eine Rücknahme wirklich erfasst — jüngste zuerst.

    Leer heißt: diese Kennung steht nicht (mehr) im Verlauf.

    Der Verlauf ist ein Stapel ohne Verzweigungen (§15.4). Das getrennte
    Löschen einer Operation aus der Mitte ist eine neue Transaktion und keine
    Rücknahme einer alten; für *diesen* Auftrag gibt es daher keine kleinere
    Antwort als „die genannte und jede jüngere". Diese Funktion ist das
    Vorher-Sagen, und beide Seiten fragen dieselbe (§26.5, Regel 16).
    """
    known = [entry.id for entry in document.transactions]
    if transaction_id not in known:
        return ()
    return tuple(reversed(known[known.index(transaction_id) :]))


def _undo_named(history: History, proposal: Proposal) -> None:
    """Nimmt zurück, was der Vorschlag angekündigt hat — und sonst nichts.

    Undo ist ein Stapel: zu einem älteren Eintrag zu kommen heißt, die neueren
    mitzunehmen. Solange das hier stillschweigend geschah, kündigte ein
    Vorschlag „nimm t1 zurück" an und leerte bei vier Transaktionen das
    Projekt — angekündigt eine, ausgeführt vier, gegen Regel 16. Der Weg
    zurück ist damit auch verstellt: ein Redo bringt nur t1 wieder, und die
    nächste Anwendung wirft t2 bis t4 endgültig weg (``_forget_undone``).

    Verhindern lässt sich das Mitnehmen nicht — herauspflücken kann der
    Verlauf nicht. Angekündigt wird es dafür: :func:`sweep_for` sagt es dem
    Modell im Zug, es steht als Befund am Vorschlag, und **hier** wird
    verglichen. Weicht der Verlauf von der Ankündigung ab, weil der Nutzer
    zwischen Vorschlag und Annahme selbst zurückgenommen oder etwas angewandt
    hat, wird nichts getan: Was angenommen wird, muss dasselbe sein, was
    dagestanden hat.
    """
    transaction_id = proposal.undo_of or ""
    sweep = sweep_for(history.document, transaction_id)
    if not sweep:
        raise ValidationError(
            field="transaction",
            detail=_("Diese Transaktion steht nicht mehr im Verlauf."),
            constraint="unknown_transaction",
            values={"transaction": transaction_id},
        )
    announced = proposal.undo_sweeps or (transaction_id,)
    if sweep != tuple(announced):
        raise ValidationError(
            field="transaction",
            detail=_(
                "Dieser Vorschlag würde andere Schritte zurücknehmen als "
                "angekündigt — der Verlauf steht anders als bei seiner "
                "Entstehung. Fragen Sie noch einmal."
            ),
            constraint="history_moved",
            values={
                "transaction": transaction_id,
                "announced": ", ".join(announced),
                "affected": ", ".join(sweep),
            },
        )
    for _step in sweep:
        history.undo()


def undo_finding(sweep: Sequence[TransactionId]) -> Finding:
    """Der Befund, der die Rücknahme ehrlich macht (§26.5, Regel 16).

    Er hängt am Vorschlag und damit in der Entscheidungszeile: Wer „nimm den
    Bohrschritt zurück" liest, soll nicht erst am leeren Projekt merken, dass
    drei jüngere Schritte mitgingen. Zwei Schweregrade, weil die Lage zwei
    verschiedene sind — die jüngste Transaktion zurückzunehmen ist genau das,
    was dasteht, und braucht keine Warnung.
    """
    if len(sweep) < 2:
        return Finding(
            code="agent.undo_single",
            severity="info",
            message=_("Der Vorschlag nimmt die zuletzt angewandte Transaktion zurück."),
            values={"transactions": ", ".join(sweep)},
        )
    return Finding(
        code="agent.undo_sweeps",
        severity="warning",
        message=_(
            "Diese Transaktion liegt nicht zuoberst. Sie zurückzunehmen nimmt "
            "auch alle jüngeren mit — der Verlauf kennt keine Verzweigungen."
        ),
        values={"count": len(sweep), "transactions": ", ".join(sweep)},
    )


def _title(proposal: Proposal) -> str:
    summary = proposal.summary()
    return f"{tr('Vorschlag')}: {summary}" if summary else tr("Vorschlag")


def _identifier() -> str:
    return f"c{secrets.token_hex(4)}"
