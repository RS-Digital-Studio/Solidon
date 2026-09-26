"""Eine gemeinsame Schwerlastspur für lokale KI-Backends.

Ollama und ComfyUI können jeweils fast die gesamte Grafikkarte belegen. Zwei
gleichzeitige Läufe drängen deshalb Speicher über WDDM in den Arbeitsspeicher
und machen nicht nur Solidon, sondern den ganzen Rechner zäh. Entfernte
Backends teilen diese Maschine nicht und werden nicht serialisiert.

**Ein Modell darf nach seinem Lauf geladen bleiben — bis ein anderer die Karte
braucht** (:func:`keep_warm`, Entscheidung nach Roberts Vorgabe vom
25.09.2026). Bis dahin entlud Ollama nach jedem Chat-Zug, und jeder nächste
Zug zahlte den Modellstart neu: gemessen 3 bis 314 Sekunden je nach Lage der
Karte (RM-081). Wer die Spur betritt, gibt vorher jedes warm gehaltene Modell
frei außer dem eigenen; der Absturz vom 01.09.2026 kam von zwei Modellen
gleichzeitig auf der Karte, und genau das bleibt ausgeschlossen.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from app.core.discover import is_local_address
from app.core.errors import CANCEL, RETRY, ExternalToolError, OperationCancelled
from app.core.log import get_logger
from app.core.types import CancelToken
from app.i18n import _, tr

Cancellation = CancelToken | Callable[[], bool] | None

_log = get_logger(__name__)

_LOCAL_AI_LOCK = threading.Lock()

#: Was nach seinem Lauf geladen geblieben ist — Kennung und der Weg, es frei
#: zu geben. Eigenes Schloss: :func:`keep_warm` läuft am Ende eines Laufs, noch
#: innerhalb der Spur.
_WARM: dict[str, Callable[[], None]] = {}
_WARM_LOCK = threading.Lock()
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


def keep_warm(holder: str, release: Callable[[], None]) -> None:
    """``holder`` bleibt geladen, bis ein anderer Lauf die Spur betritt.

    ``release`` gibt es dann frei — dieselbe Funktion, die sonst am Ende des
    Laufs stünde. Ein zweiter Eintrag unter derselben Kennung ersetzt den
    ersten: dasselbe Modell ist einmal geladen, nicht zweimal.
    """
    with _WARM_LOCK:
        _WARM[holder] = release


def release_warm(*, keep: str = "") -> None:
    """Jedes warm gehaltene Modell freigeben — außer ``keep``.

    Ein Freigeben, das scheitert, hält niemanden auf: Es ist Aufräumen, und
    der Lauf danach bekommt seine Karte auch, wenn der Dienst schon fort ist.
    """
    with _WARM_LOCK:
        leaving = [(holder, release) for holder, release in _WARM.items() if holder != keep]
        for holder, _release in leaving:
            del _WARM[holder]
    for holder, release in leaving:
        try:
            release()
        except (OSError, ValueError, ExternalToolError) as problem:
            _log.warning("warm gehaltenes Modell %s nicht freigegeben: %s", holder, problem)


#: Wie lange das Beenden der Anwendung höchstens auf die Freigabe wartet.
#: Ollama antwortet erst, wenn das Modell entladen ist: gemessen 0,3 bis 0,6 s
#: für qwen3:14b auf freier Karte, unmittelbar nach einem Zug an einer vollen
#: Karte über zwei Sekunden (Durchsicht 0.5.1). Endet die Anwendung vorher,
#: stirbt der Faden mit ihr, und das Modell hielte seine drei Minuten doch.
#: Antwortet der Dienst gar nicht, geht das Fenster nach dieser Frist trotzdem
#: zu, und das Modell fällt nach seinem ``keep_alive`` von selbst.
RELEASE_AT_EXIT_SECONDS = 5.0


def release_warm_before_exit(seconds: float = RELEASE_AT_EXIT_SECONDS) -> bool:
    """Jedes warm gehaltene Modell freigeben, weil die Anwendung endet.

    **Seit dem Warmhalten (25.09.2026) blieb das Modell nach dem Beenden
    liegen**: Freigegeben wurde es nur, wenn ein anderer Lauf die Spur betrat,
    und nach dem Beenden betritt sie keiner mehr. Wer Solidon schloss und ein
    Spiel oder den Slicer startete, hatte drei Minuten lang bis zu 13,6 GB
    Grafikspeicher weniger (Durchsicht 0.5.1). Bis 0.5.0 wurde nach jedem Zug
    entladen, und das Problem gab es nicht.

    In einem eigenen Faden mit Frist: Ein hängender Dienst darf das Beenden
    nicht aufhalten. ``True``, wenn die Freigabe in der Frist fertig wurde.
    """
    if not warm_holders():
        return True
    worker = threading.Thread(target=release_warm, name="release-warm-models", daemon=True)
    worker.start()
    worker.join(seconds)
    return not worker.is_alive()


def warm_holders() -> tuple[str, ...]:
    """Wer gerade warm gehalten wird — für Tests und die Diagnose."""
    with _WARM_LOCK:
        return tuple(_WARM)


@contextmanager
def local_ai_slot(
    url: str,
    cancelled: Cancellation,
    progress: Callable[[str], None] | None = None,
    *,
    holder: str = "",
) -> Iterator[None]:
    """Wartet sichtbar, abbrechbar und begrenzt auf die gemeinsame lokale KI.

    Wer die Spur hat, gibt zuerst jedes warm gehaltene Modell frei, das nicht
    ``holder`` ist (:func:`release_warm`) — ein ComfyUI-Lauf nennt keines und
    räumt damit die Karte ganz, ein zweiter Chat-Zug desselben Modells behält
    es geladen.
    """
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
        release_warm(keep=holder)
        yield
    finally:
        if acquired:
            _LOCAL_AI_LOCK.release()
