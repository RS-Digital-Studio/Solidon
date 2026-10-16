"""Ein Neuaufbau ohne Eingabe des Kunden behält den Klick, der an einer Freigabe wartet.

*Übernehmen* vor dem Bild bindet sich an die erwartete Freigabe
(``_PreviewApproval.pending_click``) und läuft, sobald die Vorschau steht.
Baut das Merkmalfenster in dieser Zeit neu auf — die Antwort des
Merkmalsarbeiters an einem großen Körper, eine wiederhergestellte Auswahl —,
räumte der Aufbau die Vorschau ab und band die Werte des Schritts neu: Der
Klick verfiel ohne Schritt und ohne Satz (Review 1, RCI-2). Während eines
solchen Aufbaus gilt die Freigabe mit dem wartenden Klick als gehalten
(``MainWindow._kept_through_rebuild``); zwei Stellen lassen sie stehen:
``_set_preview_order`` (keine neue Bindung) und ``_clear_preview`` (kein
Abräumen, die Vorschau rechnet weiter — auch ``_drop_feature_preview`` und
``PlacementFlow.start`` räumen über sie ab). Ein Halt liegt um den Aufbau aus
der Merkmalswahl, um das Abräumen davor, um die Meldung beider Merkmale einer
Bohrung mit Senkung und um die Antwort des Merkmalsarbeiters. Nach dem Halt
bindet die Maßgruppe nachgereichte Werte ohne Geste mit ``rebuilt=True``.

Gehalten wird nur, was noch gilt (``MainWindow._preview_is_current``: dasselbe
Dokument, dasselbe Ergebnis, dieselbe Auswahl). Wählt der Kunde ein anderes
Merkmal, gilt die Freigabe nicht mehr, und der Aufbau räumt wie bisher ab.

**Und der Aufbau zeigt, was wartet** (Nachprüfung, R2-2): Maßgruppe und
Merkmalfenster trugen danach die Werte des Schritts, die Statuszeile sagte
„Wird übernommen …“, und wer dem Feld glaubte und seinen Wert noch einmal
tippte, verlor den Klick. :func:`show_waiting_values` trägt die Werte des
Auftrags in beide.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any


def waiting_approval(window: Any) -> Any:
    """Die Freigabe, an der ein Klick wartet und die noch gilt — sonst ``None``."""
    approval = getattr(window, "_preview_approval", None)
    if approval is None or approval.pending_click is None:
        return None
    return approval if window._preview_is_current(approval) else None


def waiting_values(window: Any, approval: Any) -> tuple[str, Mapping[str, Any]] | None:
    """Handlung und Werte des Auftrags, an dem der Klick wartet."""
    order = approval.order
    if order.drafts:
        draft = order.drafts[0]
        return str(draft.op), dict(draft.params)
    if order.change_op is not None and order.change_values is not None:
        name = order.change_name or window.session.history.operation(order.change_op).op
        return str(name), dict(order.change_values)
    return None


def show_waiting_values(window: Any, approval: Any) -> None:
    """Die Werte des wartenden Auftrags in Maßgruppe und Merkmalfenster tragen."""
    found = waiting_values(window, approval)
    if found is None:
        return
    op, values = found
    host = getattr(window, "_quiet_host", None)
    flow = getattr(window, "_quiet_placement", None)
    if host is not None and flow is not None and flow.spec_of().name == op:
        host.take_placement(values)
    window.feature_panel.take_values(op, values, arm=False)


@contextmanager
def kept_through_rebuild(window: Any) -> Iterator[None]:
    """Hält die Freigabe mit wartendem Klick, solange das Fenster neu aufbaut."""
    # ``getattr``: Stellvertreter des Fensters in Tests tragen den Merker nicht.
    before = getattr(window, "_kept_through_rebuild", None)
    kept = waiting_approval(window) or before
    window._kept_through_rebuild = kept
    try:
        yield
        if kept is not None and kept is not before and window._preview_approval is kept:
            show_waiting_values(window, kept)
    finally:
        window._kept_through_rebuild = before
