"""Eine gemeinsame Schwerlastspur für lokale KI-Backends.

Ollama und ComfyUI können jeweils fast die gesamte Grafikkarte belegen. Zwei
gleichzeitige Läufe drängen deshalb Speicher über WDDM in den Arbeitsspeicher
und machen nicht nur Solidon, sondern den ganzen Rechner zäh. Entfernte
Backends teilen diese Maschine nicht und werden nicht serialisiert.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.core.discover import is_local_address
from app.core.errors import CANCEL, RETRY, ExternalToolError, OperationCancelled
from app.core.types import CancelToken
from app.i18n import _, tr

Cancellation = CancelToken | Callable[[], bool] | None

_LOCAL_AI_LOCK = threading.Lock()
_WAIT_SECONDS = 0.05
MAX_WAIT_SECONDS = 600.0


class LocalAiBusyError(ExternalToolError):
    """Die gemeinsame lokale KI-Spur wurde innerhalb der Wartezeit nicht frei."""

    default_title = _("Die lokale KI ist noch belegt.")

    def __init__(self) -> None:
        super().__init__(
            detail=_(
                "Ein anderer Lauf hat die gemeinsame Grafikkarte innerhalb der Wartezeit "
                "nicht freigegeben. Lassen Sie ihn enden und versuchen Sie es erneut."
            ),
            values={"seconds": MAX_WAIT_SECONDS},
            suggestions=(RETRY, CANCEL),
        )


def _raise_if_cancelled(cancelled: Cancellation) -> None:
    if cancelled is None:
        return
    if isinstance(cancelled, CancelToken):
        cancelled.raise_if_cancelled()
        return
    if cancelled():
        raise OperationCancelled


@contextmanager
def local_ai_slot(
    url: str, cancelled: Cancellation, progress: Callable[[str], None] | None = None
) -> Iterator[None]:
    """Wartet sichtbar, abbrechbar und begrenzt auf die gemeinsame lokale KI."""
    if not is_local_address(url):
        yield
        return

    acquired = False
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    try:
        _raise_if_cancelled(cancelled)
        acquired = _LOCAL_AI_LOCK.acquire(blocking=False)
        if not acquired and progress is not None:
            progress(
                tr("Wartet auf die lokale KI — ein anderer Lauf belegt gerade die Grafikkarte.")
            )
        while not acquired:
            _raise_if_cancelled(cancelled)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LocalAiBusyError
            acquired = _LOCAL_AI_LOCK.acquire(timeout=min(_WAIT_SECONDS, remaining))
        _raise_if_cancelled(cancelled)
        yield
    finally:
        if acquired:
            _LOCAL_AI_LOCK.release()
