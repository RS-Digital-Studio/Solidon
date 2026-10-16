"""Ein Neuaufbau ohne Eingabe des Kunden behält den Klick, der an einer Freigabe wartet.

*Übernehmen* vor dem Bild bindet sich an die erwartete Freigabe
(``_PreviewApproval.pending_click``) und läuft, sobald die Vorschau steht.
Baut das Merkmalfenster in dieser Zeit neu auf — die Antwort des
Merkmalsarbeiters an einem großen Körper, eine wiederhergestellte Auswahl —,
räumte der Aufbau die Vorschau ab und band die Werte des Schritts neu: Der
Klick verfiel ohne Schritt und ohne Satz (Review 1, RCI-2). Während eines
solchen Aufbaus gilt die Freigabe mit dem wartenden Klick als gehalten
(``MainWindow._kept_through_rebuild``); ``_set_preview_order``,
``_drop_feature_preview`` und ``_forget_preview_approval`` lassen sie stehen.

Gehalten wird nur, was noch gilt (``MainWindow._preview_is_current``: dasselbe
Dokument, dasselbe Ergebnis, dieselbe Auswahl). Wählt der Kunde ein anderes
Merkmal, gilt die Freigabe nicht mehr, und der Aufbau räumt wie bisher ab.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


def waiting_approval(window: Any) -> Any:
    """Die Freigabe, an der ein Klick wartet und die noch gilt — sonst ``None``."""
    approval = getattr(window, "_preview_approval", None)
    if approval is None or approval.pending_click is None:
        return None
    return approval if window._preview_is_current(approval) else None


@contextmanager
def kept_through_rebuild(window: Any) -> Iterator[None]:
    """Hält die Freigabe mit wartendem Klick, solange das Fenster neu aufbaut."""
    # ``getattr``: Stellvertreter des Fensters in Tests tragen den Merker nicht.
    before = getattr(window, "_kept_through_rebuild", None)
    window._kept_through_rebuild = waiting_approval(window) or before
    try:
        yield
    finally:
        window._kept_through_rebuild = before
