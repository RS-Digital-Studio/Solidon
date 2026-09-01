"""Eine gemeinsame Schwerlastspur für lokale KI-Backends.

Ollama und ComfyUI können jeweils fast die gesamte Grafikkarte belegen. Zwei
gleichzeitige Läufe drängen deshalb Speicher über WDDM in den Arbeitsspeicher
und machen nicht nur Solidon, sondern den ganzen Rechner zäh. Entfernte
Backends teilen diese Maschine nicht und werden nicht serialisiert.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.core.discover import is_local_address
from app.core.errors import OperationCancelled
from app.core.types import CancelToken

Cancellation = CancelToken | Callable[[], bool] | None

_LOCAL_AI_LOCK = threading.Lock()
_WAIT_SECONDS = 0.05


def _raise_if_cancelled(cancelled: Cancellation) -> None:
    if cancelled is None:
        return
    if isinstance(cancelled, CancelToken):
        cancelled.raise_if_cancelled()
        return
    if cancelled():
        raise OperationCancelled


@contextmanager
def local_ai_slot(url: str, cancelled: Cancellation) -> Iterator[None]:
    """Serialisiert GPU-schwere Arbeit, wenn ``url`` auf diesen Rechner zeigt."""
    if not is_local_address(url):
        yield
        return

    acquired = False
    try:
        while not acquired:
            _raise_if_cancelled(cancelled)
            acquired = _LOCAL_AI_LOCK.acquire(timeout=_WAIT_SECONDS)
        _raise_if_cancelled(cancelled)
        yield
    finally:
        if acquired:
            _LOCAL_AI_LOCK.release()
