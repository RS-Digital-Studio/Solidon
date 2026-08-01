"""Kooperativer Abbruch (Bauplan §15.6, §2.8).

Alles, was rechnet, läuft in einem Arbeits-Thread mit Fortschritt und
Abbrechen-Knopf. Ein abgebrochener Lauf lässt den Stapel auf dem letzten
vollständig gerechneten Stand — halb angewandte Operationen gibt es nicht,
also wird das Token zwischen Operationen und in langen abgefragt, nie von
außen erzwungen.
"""

from __future__ import annotations

import threading

from app.core.errors import OperationCancelled


class CancelSignal:
    """Das Token, das eine Operation abfragt, und der Schalter, den die
    Oberfläche umlegt."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise OperationCancelled


class NeverCancelled:
    """Für Kommandozeilen-Läufe und Tests: hier bricht nie jemand ab."""

    @property
    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return None
