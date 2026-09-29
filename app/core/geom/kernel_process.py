"""Große Aufrufe des Netzkerns in einem eigenen Prozess (RM-212).

Entschieden hat Robert am 27.09.2026, vor dem Tag v0.5.1.

``manifold3d`` gibt den Interpreter während seiner Aufrufe nie her
(:mod:`app.core.geom.kernel_jobs`). Solange der Kern im Prozess der Anwendung
rechnet, steht deshalb das Fenster, auch wenn ein Arbeiterfaden ihn ruft:
Beim Übernehmen von *Kanten verfeinern* am Spielwürfel (0,05 mm, 5,8 Mio.
Dreiecke) stand der Hauptfaden 15,0 und 22,7 s am Stück, beide Male in
``refine_to_length`` (Sonde ``fenster_uebernehmen.py``, 27.09.2026). Es gab zwei
Wege — ein Hilfsprozess oder ein Kern, der den Interpreter hergibt —, und
entschieden ist der Hilfsprozess.

:func:`run` rechnet eine Rechnung aus ``kernel_jobs.JOBS`` entweder hier oder
in einem Hilfsprozess, mit denselben Bytes an beiden Orten:

* **Hier**, wenn sie klein ist (:data:`OFFLOAD_ABOVE`), wenn der Hauptfaden
  fragt — er wartete auf den Hilfsprozess genauso wie auf den Kern selbst —
  oder wenn kein Hilfsprozess zustande kommt.
* **Im Hilfsprozess** sonst. Gestartet wird mit ``spawn``, wie Windows und
  macOS es ohnehin tun; im eingefrorenen Paket startet ``sys.executable`` die
  Anwendung selbst, und ``multiprocessing.freeze_support()`` am Einstieg
  (``app/ui/app.py``) macht daraus den Hilfsprozess. Die Felder reisen über
  gemeinsamen Speicher (``kernel_jobs.pack``), durch die Leitung gehen nur
  Namen und Zahlen.

Abbrechen beendet den Hilfsprozess wirklich — ein Kernaufruf lässt sich nicht
anders anhalten. Stirbt er während einer Rechnung, kommt
:class:`KernelHelperLostError` mit Handlungsvorschlag (Regel 17); startet er nicht
oder nimmt er eine Rechnung nicht an, rechnet der Aufrufer hier weiter. Beim
Beenden der Anwendung räumt :func:`shutdown` auf, und unter Windows beendet
das Jobobjekt jeden Hilfsprozess mit dem Elternprozess (``process.bind_helper``).
"""

from __future__ import annotations

import multiprocessing
import multiprocessing.connection
import os
import pickle
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from typing import Any, Final

import numpy as np

from app.core import process as process_boundary
from app.core.errors import InternalError, OperationCancelled
from app.core.geom import kernel_jobs
from app.core.geom.kernel_jobs import Outcome, Values
from app.core.log import get_logger
from app.core.types import CancelToken
from app.i18n import _

_log = get_logger(__name__)

#: Ab wie vielen Dreiecken eine Rechnung in den Hilfsprozess geht — gemessen
#: (``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/schwelle.py``,
#: 27.09.2026, gebunden, unter Last):
#: Im Prozess hielt eine Rechnung den Hauptfaden so lange an, wie sie rechnete,
#: 12 bis 16 ms an 5 120 Dreiecken, 16 bis 18 ms an 12 736, 26 bis 27 ms an
#: 20 480, 52 bis 57 ms an 81 920 und 178 ms an 327 680. Der Hilfsprozess
#: kostete dagegen 1 bis 3 ms Stillstand und an Laufzeit höchstens 3 ms mehr bis
#: 20 480 Dreiecke, 8 bis 46 ms darüber (Kopieren, Leitung). Unter der Schwelle
#: bleibt der Stillstand innerhalb eines Bildes bei 60 Hz; dort kauft das
#: Kopieren nichts Sichtbares.
OFFLOAD_ABOVE: int = 10_000

#: Wie lange ein frisch gestarteter Hilfsprozess bis zu seiner ersten Meldung
#: brauchen darf, in Sekunden. Danach gilt er als hängend und wird beendet.
STARTUP_SECONDS: Final = 30.0

#: Wie lange ein Hilfsprozess eine Rechnung bis zur Annahme brauchen darf. Er
#: nimmt an, bevor er rechnet; wer das nicht tut, hängt.
ACCEPT_SECONDS: Final = 10.0

#: Wie oft der wartende Faden nach dem Abbruch fragt, in Sekunden.
CANCEL_POLL_SECONDS: Final = 0.05

#: Wie viele Hilfsprozesse höchstens zugleich leben. Mehr Aufrufer warten auf
#: einen freien — in ihrem Faden, abbrechbar.
MOST_HELPERS: Final = 3

#: Wie viele untätige Hilfsprozesse auf die nächste Rechnung warten.
IDLE_KEPT: Final = 1

#: Wie lange ein untätiger Hilfsprozess nach dem Schließen der Leitung selbst
#: enden darf, bevor er beendet wird, in Sekunden (:meth:`_Helper.stop`).
#: Gemessen endet er in 32 bis 45 ms (28.09.2026, unter Last,
#: ``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/sanft_enden.py``);
#: die Frist lässt das Zehnfache, und so lange
#: wartet das Beenden der Anwendung höchstens.
GRACEFUL_SECONDS: Final = 0.5

#: Wie viele Starts hintereinander scheitern dürfen, bevor diese Sitzung ohne
#: Hilfsprozess weiterrechnet. Einer: Bereit ist ein Hilfsprozess nach 0,4 bis
#: 0,8 s, aus dem Quellbaum wie aus dem Paket; wer in :data:`STARTUP_SECONDS`
#: nicht antwortet, antwortet nicht (etwa ein Paket ohne ``freeze_support``),
#: und ein zweiter Versuch kostete den Kunden die Frist noch einmal.
STARTS_BEFORE_GIVING_UP: Final = 1

#: Was ein Hilfsprozess in seiner Umgebung anders sieht als die Anwendung.
#: OpenBLAS, das ``numpy`` und ``scipy`` je einmal mitbringen, legt beim Laden
#: für jeden Rechenkern einen Puffer an: gemessen 758 MB privater Speicher je
#: Bibliothek an 32 Kernen, mit einem Faden 19 MB (28.09.2026,
#: ``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/privat.py``) — ein
#: untätiger Hilfsprozess trug nach der ersten
#: Zusammenhangsrechnung 1,5 GB davon. Eine Rechnung in ``kernel_jobs`` ruft
#: kein BLAS (``test_the_jobs_call_no_blas``), der eine Faden kostet sie also
#: nichts und ändert kein Byte.
HELPER_ENVIRONMENT: Final = {"OPENBLAS_NUM_THREADS": "1"}

_ENVIRONMENT_LOCK: Final = threading.Lock()

_CONTEXT: Final = multiprocessing.get_context("spawn")

#: Was ein Hilfsprozess nach dem Start ausführt. Ein Name, damit die Suite einen
#: Hilfsprozess nachstellen kann, der nicht antwortet oder stirbt.
_SERVE: Callable[[Any], None] = kernel_jobs.serve


class KernelHelperLostError(InternalError):
    """Der Hilfsprozess ist während einer Rechnung gestorben.

    Im Prozess der Anwendung hätte derselbe Absturz sie mitgerissen; hier bleibt
    das Modell stehen, und der Schritt hält mit diesem Satz an.
    """

    default_detail = _(
        "Die Rechnung an diesem großen Netz ist mittendrin abgebrochen; das Modell ist "
        "unverändert. Versuchen Sie den Schritt noch einmal, etwa mit weniger Dreiecken. "
        "Hilft das nicht, erstellen Sie einen Fehlerbericht."
    )


class _HelperLostError(Exception):
    """Der Hilfsprozess lebt nicht mehr oder die Leitung ist zu."""


class _HelperSilentError(Exception):
    """Der Hilfsprozess hat in seiner Frist nicht geantwortet."""


class _HelperCancelledError(Exception):
    """Der Aufrufer hat abgebrochen, während der Hilfsprozess rechnete."""


class _HelperRefusedError(Exception):
    """Die Rechnung kam nicht in den Hilfsprozess oder ihr Ergebnis nicht heraus.

    Sie wird dann hier gerechnet (Durchsicht RM-212, B2). ``lasting`` heißt:
    Der Grund bleibt — ein gemeinsamer Speicher, der sich nicht anlegen oder
    öffnen lässt —, und die Sitzung rechnet ohne Hilfsprozess weiter. Ein
    Hilfsprozess, der vor der Annahme starb, ist kein bleibender Grund.
    """

    def __init__(self, why: str, *, lasting: bool) -> None:
        super().__init__(why)
        self.lasting = lasting


#: Was ein breiter Fang um einen Kernaufruf durchlässt (``except Exception``):
#: ein Abbruch und ein verlorener Hilfsprozess. Beides ist kein Kern, der auf
#: seine Art aufgegeben hat. Ohne das nahm die Boolesche Kette nach einem
#: gestorbenen Hilfsprozess still die nächste Stufe — dreimal gestartet, das
#: Ergebnis aus der Voxelstufe, in der Vorschau der Rat, das Modell zu
#: reparieren (Durchsicht RM-212, B3).
NOT_A_KERNEL_FAILURE: Final = (OperationCancelled, KernelHelperLostError)


@contextmanager
def _helper_environment() -> Iterator[None]:
    """:data:`HELPER_ENVIRONMENT` für die Dauer eines Starts, danach der alte Stand.

    Ein Kindprozess erbt die Umgebung, wenn er entsteht, und liest sie, bevor
    er ``numpy`` lädt; die Anwendung selbst hat ihr OpenBLAS da längst geladen.
    Unter einem Schloss, damit zwei Starts einander den alten Wert nicht
    überschreiben.
    """
    with _ENVIRONMENT_LOCK:
        saved = {name: os.environ.get(name) for name in HELPER_ENVIRONMENT}
        os.environ.update(HELPER_ENVIRONMENT)
        try:
            yield
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


class _Helper:
    """Ein Hilfsprozess und die Leitung zu ihm. Gehört immer genau einem Faden."""

    def __init__(self) -> None:
        mine, theirs = _CONTEXT.Pipe(duplex=True)
        self.process = _CONTEXT.Process(
            target=_SERVE, args=(theirs,), name="solidon-kernel", daemon=True
        )
        with _helper_environment():
            self.process.start()
        theirs.close()
        self.connection = mine
        self.started = time.monotonic()
        self.ready = False
        try:
            process_boundary.bind_helper(self.process)
        except OSError as problem:
            # Ohne Jobobjekt endet er erst mit seiner Rechnung, nicht mit uns.
            _log.warning("kernel helper %s not bound to this process: %s", self.pid, problem)

    @property
    def pid(self) -> int | None:
        return self.process.pid

    @property
    def alive(self) -> bool:
        return self.process.is_alive()

    def wait_ready(self, cancelled: CancelToken | None) -> None:
        """Wartet auf die erste Meldung.

        Wirft ``_HelperLostError``, ``_HelperSilentError`` oder ``_HelperCancelledError``.
        """
        while not self.ready:
            message = self._receive(cancelled, self.started + STARTUP_SECONDS)
            if message[0] == "ready":
                self.ready = True

    def call(
        self,
        job: str,
        arrays: Mapping[str, np.ndarray],
        values: Values,
        cancelled: CancelToken | None,
    ) -> Outcome:
        """Eine Rechnung im Hilfsprozess; seine Ausnahmen kommen hier wieder heraus.

        Kam sie nicht hinein oder ihr Ergebnis nicht heraus, kommt
        ``_HelperRefusedError``, und der Aufrufer rechnet hier (Durchsicht
        RM-212, B2): Ein gemeinsamer Speicher ließ sich nicht anlegen oder
        öffnen, oder der Hilfsprozess starb vor der Annahme. Bis dahin kam das
        als roher ``OSError``, ``PermissionError`` oder ``BrokenPipeError``
        beim Kunden an. Reicht der Speicher nicht, kommt ``MemoryError`` wie
        aus einer Rechnung im Prozess — und mit ihm der Hinweis der Operation.
        """
        try:
            segment, layout = kernel_jobs.pack(arrays)
        except OSError as unmade:
            raise _HelperRefusedError(f"shared memory: {unmade}", lasting=True) from unmade
        try:
            try:
                self.connection.send(
                    ("job", job, segment.name if segment is not None else None, layout, values)
                )
            except OSError as broken:
                raise _HelperRefusedError(f"send: {broken}", lasting=False) from broken
            try:
                reply = self._receive(cancelled, time.monotonic() + ACCEPT_SECONDS)
            except _HelperLostError as lost:
                raise _HelperRefusedError(f"lost before accepting: {lost}", lasting=False) from lost
            if reply[0] == "accepted":
                reply = self._receive(cancelled, None)
        finally:
            if segment is not None:
                segment.close()
                segment.unlink()
        if reply[0] == "refused":
            problem = pickle.loads(reply[1])
            if isinstance(problem, MemoryError):
                problem.add_note(f"im Hilfsprozess des Kerns ({self.pid}):\n{reply[2]}")
                raise problem
            raise _HelperRefusedError(f"refused: {problem!r}", lasting=True)
        if reply[0] == "error":
            problem = pickle.loads(reply[1])
            problem.add_note(f"im Hilfsprozess des Kerns ({self.pid}):\n{reply[2]}")
            raise problem
        if reply[0] != "done":
            raise _HelperLostError(f"unexpected reply {reply[0]!r}")
        _kind, name, out_layout, reported = reply
        try:
            result = kernel_jobs.copied(name, out_layout)
        except OSError as problem:
            # Der Speicher ist fort — nur, wenn der Hilfsprozess nach seiner
            # Antwort gestorben ist.
            raise _HelperLostError(str(problem)) from problem
        finally:
            if name is not None:
                with suppress(OSError):
                    self.connection.send(("ack",))
        return result, reported

    def _receive(self, cancelled: CancelToken | None, deadline: float | None) -> tuple[Any, ...]:
        """Die nächste Meldung — ohne je still zu warten.

        Gewartet wird auf Leitung und Prozess zugleich: Ein gestorbener
        Hilfsprozess meldet sich sofort, nicht erst nach einer Frist. Zwischen
        zwei Blicken fragt der Faden nach dem Abbruch.
        """
        while True:
            try:
                if self.connection.poll(0):
                    return tuple(self.connection.recv())
            except (EOFError, OSError) as problem:
                raise _HelperLostError(str(problem)) from problem
            if cancelled is not None and cancelled.is_cancelled:
                raise _HelperCancelledError
            now = time.monotonic()
            if deadline is not None and now >= deadline:
                raise _HelperSilentError
            timeout = (
                CANCEL_POLL_SECONDS
                if deadline is None
                else min(CANCEL_POLL_SECONDS, deadline - now)
            )
            ready = multiprocessing.connection.wait(
                [self.connection, self.process.sentinel], timeout
            )
            if self.process.sentinel in ready:
                try:
                    if self.connection.poll(0):
                        continue
                except EOFError, OSError:
                    pass
                raise _HelperLostError(f"exit code {self.process.exitcode}")

    def stop(self, *, graceful: bool = False) -> None:
        """Beendet den Hilfsprozess und wartet, bis er fort ist.

        ``graceful`` gilt einem untätigen: Er sieht das Ende der Leitung und
        endet selbst, auf dem gewöhnlichen Weg samt ``atexit`` — erst nach
        :data:`GRACEFUL_SECONDS` wird er beendet. Einer, der rechnet, endet
        sofort; einen Kernaufruf hält nichts anderes an.
        """
        with suppress(OSError):
            self.connection.close()
        if graceful and self.ready:
            self.process.join(timeout=GRACEFUL_SECONDS)
        if self.process.is_alive():
            self.process.kill()
        self.process.join(timeout=5.0)
        with suppress(OSError):
            process_boundary.release_helper(self.process)


class _Pool:
    """Die Hilfsprozesse dieser Sitzung: untätige, beschäftigte, und wann Schluss ist."""

    def __init__(self) -> None:
        self._lock = threading.Condition()
        self._idle: list[_Helper] = []
        self._busy: set[_Helper] = set()
        self._failed_starts = 0
        self.disabled = False
        self.counts: dict[str, int] = {}

    def count(self, what: str, by: int = 1) -> None:
        with self._lock:
            self._bump(what, by)

    def _bump(self, what: str, by: int = 1) -> None:
        """Zählt unter dem Schloss, das der Rufer schon hält."""
        self.counts[what] = self.counts.get(what, 0) + by

    def take(self, cancelled: CancelToken | None) -> _Helper | None:
        """Ein bereiter Hilfsprozess für diesen Faden — ``None``, wenn es keinen gibt."""
        helper = self._reserve(cancelled)
        if helper is None:
            return None
        if helper.ready:
            return helper
        try:
            helper.wait_ready(cancelled)
        except _HelperCancelledError:
            # Er startet weiter und dient dem nächsten Aufrufer.
            self.give_back(helper)
            raise
        except (_HelperLostError, _HelperSilentError) as problem:
            self.discard(helper)
            self._start_failed(f"{type(problem).__name__}: {problem}")
            return None
        with self._lock:
            self._failed_starts = 0
        return helper

    def _reserve(self, cancelled: CancelToken | None) -> _Helper | None:
        """Ein untätiger Hilfsprozess, ein frischer — oder beim Deckel der nächste freie."""
        with self._lock:
            while True:
                if self.disabled:
                    return None
                while self._idle:
                    helper = self._idle.pop()
                    if helper.alive:
                        self._busy.add(helper)
                        return helper
                    self._stopped_quietly(helper)
                if len(self._busy) < MOST_HELPERS:
                    break
                if cancelled is not None and cancelled.is_cancelled:
                    raise _HelperCancelledError
                self._lock.wait(CANCEL_POLL_SECONDS)
        try:
            helper = _Helper()
        except (OSError, ValueError, RuntimeError, pickle.PicklingError) as problem:
            self._start_failed(f"{type(problem).__name__}: {problem}")
            return None
        with self._lock:
            self._busy.add(helper)
            self._bump("started")
        return helper

    def disable(self, why: str) -> None:
        """Diese Sitzung rechnet ab jetzt ohne Hilfsprozess — der Grund bleibt."""
        with self._lock:
            self.disabled = True
        _log.warning("kernel helper disabled for this session (%s)", why)

    def _start_failed(self, why: str) -> None:
        with self._lock:
            self._failed_starts += 1
            if self._failed_starts >= STARTS_BEFORE_GIVING_UP:
                self.disabled = True
        _log.warning("kernel helper did not start (%s); computing in this process", why)

    def _stopped_quietly(self, helper: _Helper) -> None:
        """Räumt einen Toten aus dem Vorrat — unter dem Schloss, ohne Warten."""
        helper.stop()
        self._bump("stopped")

    def give_back(self, helper: _Helper) -> None:
        """Der Faden ist fertig; der Hilfsprozess wartet auf den nächsten oder geht."""
        keep = False
        with self._lock:
            self._busy.discard(helper)
            if helper.alive and len(self._idle) < IDLE_KEPT:
                self._idle.append(helper)
                keep = True
            self._lock.notify_all()
        if not keep:
            self.discard(helper, graceful=True)

    def discard(self, helper: _Helper, *, graceful: bool = False) -> None:
        """Beendet einen Hilfsprozess, den niemand mehr braucht oder der nichts mehr taugt.

        ``graceful``: Er ist untätig und darf selbst enden (:meth:`_Helper.stop`).
        """
        with self._lock:
            self._busy.discard(helper)
            if helper in self._idle:
                self._idle.remove(helper)
        helper.stop(graceful=graceful)
        with self._lock:
            self._bump("stopped")
            self._lock.notify_all()

    def shutdown(self) -> int:
        """Beendet jeden Hilfsprozess; die nächste Rechnung startet frisch."""
        with self._lock:
            idle, busy = list(self._idle), list(self._busy)
            self._idle.clear()
            self._busy.clear()
            self._failed_starts = 0
            self.disabled = False
        for helper in idle:
            helper.stop(graceful=True)
        for helper in busy:
            helper.stop()
        helpers = [*idle, *busy]
        with self._lock:
            self._bump("stopped", len(helpers))
            self._lock.notify_all()
        return len(helpers)

    def processes(self) -> list[Any]:
        with self._lock:
            return [helper.process for helper in (*self._idle, *self._busy)]


_POOL: Final = _Pool()


def _unchecked() -> None:
    """Ohne Abbruchsignal gibt es nichts zu fragen."""


def offloaded(weight: int) -> bool:
    """Ob eine Rechnung dieses Gewichts in diesem Faden in den Hilfsprozess ginge."""
    return (
        weight > OFFLOAD_ABOVE
        and threading.current_thread() is not threading.main_thread()
        and not _POOL.disabled
    )


def run(
    job: str,
    arrays: Mapping[str, np.ndarray],
    values: Mapping[str, Any],
    *,
    weight: int,
    cancelled: CancelToken | None = None,
) -> Outcome:
    """Rechnet ``job`` aus ``kernel_jobs.JOBS`` — hier oder im Hilfsprozess, mit denselben Bytes.

    ``weight`` ist die Zahl der Dreiecke, an der die Wahl hängt: die des
    Eingangs, bei einer Verfeinerung die erwartete des Ergebnisses. Abbruch
    wirft ``OperationCancelled`` und beendet einen rechnenden Hilfsprozess;
    was die Rechnung selbst wirft (``ValueError`` des Kerns, ``MemoryError``),
    kommt unverändert heraus.
    """
    function = kernel_jobs.JOBS[job]
    plain = dict(values)
    check = cancelled.raise_if_cancelled if cancelled is not None else _unchecked
    if not offloaded(weight):
        _POOL.count("in_process")
        return function(arrays, plain, check)
    try:
        helper = _POOL.take(cancelled)
    except _HelperCancelledError:
        _POOL.count("cancelled")
        raise OperationCancelled from None
    if helper is None:
        _POOL.count("fallback")
        return function(arrays, plain, check)
    try:
        outcome = helper.call(job, arrays, plain, cancelled)
    except _HelperCancelledError:
        _POOL.discard(helper)
        _POOL.count("cancelled")
        raise OperationCancelled from None
    except _HelperSilentError:
        _POOL.discard(helper)
        _POOL.count("fallback")
        _log.warning(
            "kernel helper %s did not accept %s; computing in this process", helper.pid, job
        )
        return function(arrays, plain, check)
    except _HelperRefusedError as refused:
        _POOL.discard(helper)
        if refused.lasting:
            _POOL.disable(str(refused))
        _POOL.count("fallback")
        _log.warning(
            "kernel helper %s refused %s (%s); computing in this process", helper.pid, job, refused
        )
        return function(arrays, plain, check)
    except _HelperLostError as lost:
        _POOL.discard(helper)
        _POOL.count("lost")
        _log.error(
            "kernel helper %s died during %s (%d triangles): %s", helper.pid, job, weight, lost
        )
        # Welche Rechnung, steht im Protokoll darüber; der Kunde liest die Größe.
        raise KernelHelperLostError(values={"triangles": weight}) from lost
    except MemoryError:
        # Der Speicher des Hilfsprozesses kommt mit seinem Ende zurück, nicht früher.
        _POOL.discard(helper)
        raise
    except BaseException:
        _POOL.give_back(helper)
        raise
    _POOL.give_back(helper)
    _POOL.count("helper")
    _POOL.count(f"helper:{job}")
    return outcome


def warm_up() -> bool:
    """Startet einen Hilfsprozess im Voraus, damit die erste große Rechnung nicht wartet.

    Gerufen von einem Arbeiter, sobald das Fenster steht (``app/ui/app.py``):
    Der Start kostete 0,4 bis 0,8 s bis zur ersten Antwort, aus dem Quellbaum
    wie aus dem gebauten Paket (``schwelle.py``, ``eingefroren/voll_treiber.py``,
    27./28.09.2026) — genau die Zeit, um die sonst die erste grobe Vorschau
    eines großen Modells später stünde. Wartet im rufenden Faden; ``True``, wenn
    danach ein bereiter Hilfsprozess untätig wartet.
    """
    helper = _POOL.take(None)
    if helper is None:
        return False
    _POOL.give_back(helper)
    return helper.alive


def shutdown() -> int:
    """Beendet jeden Hilfsprozess — beim Beenden der Anwendung und in Tests.

    Gibt zurück, wie viele es waren. Eine Rechnung danach startet einen neuen.
    """
    return _POOL.shutdown()


def statistics() -> dict[str, int]:
    """Wie oft wo gerechnet wurde, wie oft gestartet, abgebrochen, verloren."""
    with _POOL._lock:
        known = dict.fromkeys(
            ("in_process", "helper", "started", "stopped", "cancelled", "lost", "fallback"), 0
        )
        return {**known, **_POOL.counts}


def processes() -> list[Any]:
    """Die lebenden Hilfsprozesse (``multiprocessing.Process``) — für Tests und die Sonde."""
    return _POOL.processes()
