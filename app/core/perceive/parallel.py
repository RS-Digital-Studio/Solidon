"""Die Fleckfragen eines großen Körpers auf mehrere Prozesse verteilt (RM-637).

Die Erkennung fragt jeden gekrümmten Fleck, welche Form auf ihn passt
(``features._Round.classify``), der Reihe nach und in einem Prozess. Jede
Antwort steht unter einem Schlüssel, der alles nennt, was sie liest
(Fleckabdruck, Körperzahlen, Zustand der Runde, Schwellen — RM-592); dieselbe
Frage gibt an jedem Körper und in jedem Prozess dieselbe Antwort. Hier rechnen
Arbeiter diese Antworten **vorab**, je einen Teil der Flecken, an einer Kopie
des Körpers. Die Erkennung läuft danach unverändert der Reihe nach und findet
sie unter ihrem Schlüssel; was sie nicht findet, rechnet sie selbst. Das
Ergebnis ist deshalb Bit für Bit das des einen Prozesses (Zwei-Wege-Vertrag,
Bauplan §11.2): Ein Arbeiter kann nur Zeit sparen, keine Antwort ändern.

Ein Arbeiter rechnet in einem eigenen Prozess (``spawn``) mit einem BLAS-Faden
wie der Hilfsprozess des Kerns (``kernel_process.HELPER_ENVIRONMENT``); die
Erkennung ruft auf ihren Wegen kein BLAS, an dem eine Antwort hinge
(``kern.md``, „Dieselbe Datei, dasselbe Teil“). Er prüft je Fleck, dass sein
Abdruck dem des Aufrufers gleicht, und lässt sonst den Fleck aus. Nach jeder
Aufgabe vergisst er Körper und Antworten: Sein Speicher wächst nicht über eine
Aufgabe hinaus.

Stirbt ein Arbeiter oder fehlt ihm Speicher, rechnet die Erkennung seine
Flecken selbst — langsamer, mit demselben Ergebnis. Ein Abbruch beendet die
Arbeiter (§2.8).
"""

from __future__ import annotations

import contextlib
import functools
import math
import multiprocessing
import multiprocessing.connection
import os
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Any, Final

import numpy as np

from app.core.log import get_logger

_log = get_logger(__name__)

#: Ab wie vielen Dreiecken die Fleckfragen verteilt werden. Darunter kostet der
#: Weg zu den Arbeitern mehr, als ihre Rechnung spart.
PARALLEL_FROM_TRIANGLES: Final = 50_000

#: Wie viele Flecken eine Aufgabe mindestens trägt; weniger lohnt den Weg nicht.
PATCHES_PER_TASK: Final = 16

#: Ab welchem Gewicht (``features._fit_weight``, Summe der Runde) die Arbeiter
#: rechnen. Gemessen im Wechsel, je ein frischer Prozess: Am Würfel (126) und am
#: Besteckkasten (109) war die Runde mit Arbeitern langsamer, am Ständer (252)
#: und am Eiffelturm (637) schneller.
AHEAD_FROM_WEIGHT: Final = 200.0

#: Wie viele Aufgaben je Arbeiter eine Runde bekommt (:func:`chunk_count`).
TASKS_PER_WORKER: Final = 3

#: Höchstens so viele Arbeiter. Die Fleckfragen eines großen Körpers füllen
#: acht Prozesse; darüber wächst der Speicher, nicht das Tempo.
MOST_WORKERS: Final = 8

#: Was ein Arbeiter je Dreieck seines Körpers ungefähr hält (Kopie, Normalen,
#: Flächen, Nachbarschaften, Lesungen), dazu sein Grundbedarf — für die Zahl der
#: Arbeiter, die der freie Speicher trägt.
WORKER_BYTES_PER_TRIANGLE: Final = 600
WORKER_BASE_BYTES: Final = 300_000_000
#: Welchen Teil des Arbeitsspeichers alle Arbeiter zusammen höchstens belegen.
WORKER_MEMORY_SHARE: Final = 0.25

#: Wie lange ein frischer Arbeiter bis zur Bereitschaft braucht, höchstens, in
#: Sekunden; wer nicht antwortet, rechnet nicht mit.
STARTUP_SECONDS: Final = 30.0

#: Wie oft beim Warten nach dem Abbruch gefragt wird, in Sekunden.
CANCEL_POLL_SECONDS: Final = 0.05

#: Die Umgebung eines Arbeiters: ein BLAS-Faden, wie der Hilfsprozess des Kerns.
WORKER_ENVIRONMENT: Final = {"OPENBLAS_NUM_THREADS": "1"}

_CONTEXT: Final = multiprocessing.get_context("spawn")
_ENVIRONMENT_LOCK: Final = threading.Lock()

#: Ob Arbeiter rechnen dürfen. Abschalten kann es nur der Testhaken
#: :func:`use_workers` — für Messbank und Suite, die beide Wege vergleichen.
_ENABLED: list[bool] = [True]

#: Höchstzahl der Arbeiter, die der Testhaken setzt; ``None`` heißt: nach Kernen
#: und Speicher.
_FORCED: list[int | None] = [None]


def use_workers(enabled: bool, *, count: int | None = None) -> tuple[bool, int | None]:
    """Testhaken: Arbeiter an- oder abschalten, wahlweise mit fester Zahl.

    Zurück kommt der vorige Zustand. Mit ``count`` rechnen die Arbeiter auch an
    kleinen Körpern (:data:`PARALLEL_FROM_TRIANGLES` gilt dann nicht) — so prüft
    die Suite den verteilten Weg an Korpusnetzen.
    """
    before = (_ENABLED[0], _FORCED[0])
    _ENABLED[0] = bool(enabled)
    _FORCED[0] = count
    return before


def least_weight() -> float:
    """Ab welchem Gewicht eine Runde zu den Arbeitern geht; mit fester Zahl (Testhaken) jede."""
    return 0.0 if _FORCED[0] is not None else AHEAD_FROM_WEIGHT


def worthwhile(triangles: int, patches: int) -> int:
    """Wie viele Arbeiter die Fleckfragen dieses Körpers bekommen — null heißt: keine."""
    if not _ENABLED[0]:
        return 0
    forced = _FORCED[0]
    if forced is not None:
        return max(0, min(forced, patches))
    if triangles < PARALLEL_FROM_TRIANGLES or patches < 2 * PATCHES_PER_TASK:
        return 0
    cores = os.cpu_count() or 1
    count = min(MOST_WORKERS, cores - 2, patches // PATCHES_PER_TASK)
    from app.core.memory import physical_memory

    memory = physical_memory()
    if memory is not None:
        each = WORKER_BASE_BYTES + WORKER_BYTES_PER_TRIANGLE * triangles
        count = min(count, int(memory * WORKER_MEMORY_SHARE // each))
    return max(0, count)


def warm_for(triangles: int) -> None:
    """Arbeiter für einen Körper dieser Größe starten, bevor seine Flecken feststehen.

    Ein frischer Arbeiter braucht eine bis zwei Sekunden, bis er bereitsteht —
    so lange sucht die Erkennung noch Ebenen und Flecken. Wie viele Flecken
    kommen, weiß sie da noch nicht; gestartet wird, was die Größe trägt.
    """
    warm(worthwhile(triangles, MOST_WORKERS * PATCHES_PER_TASK))


@dataclass(frozen=True, slots=True)
class Task:
    """Was ein Arbeiter rechnet: ein Teil einer Runde der Erkennung.

    ``kind`` nennt die Runde (``features.answered_ahead``), ``items`` ihren
    Teil in der Folge der Runde, ``shapes`` den Zustand der Runde, ``skin`` das
    Freiformurteil und ``token`` den Abdruck des Körpers: Gleicht er dem der
    letzten Aufgabe, rechnet der Arbeiter am selben Körper weiter.
    """

    kind: str
    items: tuple[Any, ...]
    shapes: frozenset[tuple[Any, ...]]
    skin: bool
    token: bytes


@contextlib.contextmanager
def _worker_environment() -> Iterator[None]:
    """:data:`WORKER_ENVIRONMENT` für die Dauer eines Starts, danach der alte Stand."""
    with _ENVIRONMENT_LOCK:
        saved = {name: os.environ.get(name) for name in WORKER_ENVIRONMENT}
        os.environ.update(WORKER_ENVIRONMENT)
        try:
            yield
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


class _Worker:
    """Ein Arbeiter und die Leitung zu ihm."""

    def __init__(self) -> None:
        from app.core import process as process_boundary

        mine, theirs = _CONTEXT.Pipe(duplex=True)
        self.process = _CONTEXT.Process(
            target=serve, args=(theirs,), name="solidon-perceive", daemon=True
        )
        self.connection = mine
        self.ready = False
        self.started = time.monotonic()
        with _worker_environment():
            self.process.start()
        theirs.close()
        try:
            process_boundary.bind_helper(self.process)
        except OSError as problem:
            _log.warning("perceive worker %s not bound to this process: %s", self.pid, problem)

    @property
    def pid(self) -> int | None:
        return self.process.pid

    def stop(self) -> None:
        with contextlib.suppress(OSError):
            self.connection.close()
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=2.0)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=2.0)


class _Pool:
    """Die Arbeiter dieses Prozesses; sie bleiben zwischen zwei Erkennungen stehen."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._workers: list[_Worker] = []

    def start(self, count: int) -> None:
        """So viele Arbeiter anlegen, dass ``count`` bereitstehen oder starten — ohne zu warten."""
        with self._lock:
            self._workers = [worker for worker in self._workers if worker.process.is_alive()]
            while len(self._workers) < count:
                try:
                    self._workers.append(_Worker())
                except OSError as problem:
                    _log.warning("perceive worker could not start: %s", problem)
                    return

    def take(self, count: int) -> list[_Worker]:
        """Bis zu ``count`` lebende Arbeiter für eine Runde; sie gehören dann dem Aufrufer."""
        with self._lock:
            alive = [worker for worker in self._workers if worker.process.is_alive()]
            taken, self._workers = alive[:count], alive[count:]
            return taken

    def give_back(self, workers: Sequence[_Worker]) -> None:
        with self._lock:
            self._workers.extend(worker for worker in workers if worker.process.is_alive())

    def tell(self, message: tuple[Any, ...]) -> None:
        """Eine Nachricht ohne Antwort an jeden stehenden Arbeiter."""
        with self._lock:
            workers = list(self._workers)
        for worker in workers:
            with contextlib.suppress(OSError):
                worker.connection.send(message)

    def shutdown(self) -> int:
        with self._lock:
            workers, self._workers = self._workers, []
        for worker in workers:
            worker.stop()
        return len(workers)

    @property
    def size(self) -> int:
        with self._lock:
            return sum(1 for worker in self._workers if worker.process.is_alive())


_POOL: Final = _Pool()

#: Was die Arbeiter in diesem Prozess getan haben — für Messbank und Suite.
_COUNTS: Final[Counter[str]] = Counter()
_COUNTS_LOCK: Final = threading.Lock()


def count(what: str, by: int = 1) -> None:
    """Zählt mit (``tasks``, ``returned``, ``answers``, ``used``, ``lost``)."""
    with _COUNTS_LOCK:
        _COUNTS[what] += by


def warm(count: int) -> None:
    """Arbeiter schon starten, während die Erkennung noch Ebenen sucht — ohne zu warten."""
    if count > 0:
        _POOL.start(count)


def prepare(arrays: Mapping[str, np.ndarray], token: bytes) -> bool:
    """Den Körper einmal in einen gemeinsamen Speicher und an jeden stehenden Arbeiter.

    Ohne zu warten; der Arbeiter liest ihn erst mit seiner ersten Aufgabe
    (``features.held_body``). Der Speicher bleibt bis :func:`release`; jede
    Runde mit demselben Abdruck liest aus ihm.
    ``False``: kein Speicher, die Runden packen dann selbst.
    """
    try:
        segment, layout = _pack(arrays)
    except (OSError, MemoryError) as problem:
        _log.warning("perceive workers get no body: %s", problem)
        return False
    with _PREPARED_LOCK:
        _close(_PREPARED[0])
        _PREPARED[0] = (token, segment, layout)
    return True


#: Der vorbereitete Körper: Abdruck, gemeinsamer Speicher, Lage der Felder.
_PREPARED: list[tuple[bytes, shared_memory.SharedMemory | None, list[Any]] | None] = [None]
_PREPARED_LOCK: Final = threading.Lock()


def _close(prepared: tuple[bytes, shared_memory.SharedMemory | None, list[Any]] | None) -> None:
    if prepared is None or prepared[1] is None:
        return
    prepared[1].close()
    with contextlib.suppress(OSError):
        prepared[1].unlink()


def prepared(token: bytes) -> bool:
    """Ob die Arbeiter gerade diesen Körper vorbereitet haben (:func:`prepare`).

    Nur dann rechnen sie mit: Eine Frage außerhalb einer Erkennung, die sie
    vorbereitet hat, packt keinen Körper und startet keine Arbeiter.
    """
    with _PREPARED_LOCK:
        return _PREPARED[0] is not None and _PREPARED[0][0] == token


def release() -> None:
    """Die stehenden Arbeiter lassen ihren Körper los — nach der letzten Runde einer Erkennung.

    Ohne das hielte jeder Arbeiter bis zur nächsten Erkennung die Kopie des
    Körpers und alles daran Gemerkte (Speicher je Prozess begrenzt, RM-637).
    Der gemeinsame Speicher des vorbereiteten Körpers geht mit.
    """
    _POOL.tell(("forget",))
    with _PREPARED_LOCK:
        _close(_PREPARED[0])
        _PREPARED[0] = None


def shutdown() -> int:
    """Alle Arbeiter beenden — beim Schließen der Anwendung und in Tests."""
    return _POOL.shutdown()


def statistics() -> dict[str, int]:
    """Wie viele Arbeiter gerade stehen und was sie bisher getan haben."""
    with _COUNTS_LOCK:
        counted = dict(_COUNTS)
    return {"workers": _POOL.size, **counted}


def bins(weights: Sequence[float], parts: int) -> list[list[int]]:
    """Höchstens ``parts`` Fächer gleichen Gewichts, jeder in aufsteigender Folge.

    Der schwerste Fleck kommt in den leichtesten Fächer, der nächste ebenso — die
    letzte Runde hängt sonst an einem Arbeiter mit allen großen Flecken. In der
    Folge der Runde, damit der Arbeiter deckungsgleiche Flecken wie hier fragt.
    """
    if not weights or parts <= 0:
        return []
    loads = [0.0] * min(parts, len(weights))
    filled: list[list[int]] = [[] for _ in loads]
    for index in sorted(range(len(weights)), key=lambda at: (-weights[at], at)):
        lightest = min(range(len(loads)), key=lambda at: (loads[at], at))
        loads[lightest] += weights[index]
        filled[lightest].append(index)
    return [sorted(part) for part in filled if part]


def split(weights: Sequence[float], parts: int) -> list[range]:
    """Die Flecken in höchstens ``parts`` zusammenhängende Teile gleichen Gewichts.

    Zusammenhängend, weil die Flecken nach Größe geordnet kommen: Deckungsgleiche
    Flecken stehen nebeneinander und landen meist bei demselben Arbeiter, der
    den Zustand der Runde dann wie der eine Prozess fortschreibt.
    """
    if not weights or parts <= 0:
        return []
    total = float(sum(weights))
    target = total / parts
    ranges: list[range] = []
    start = 0
    running = 0.0
    for index, weight in enumerate(weights):
        running += weight
        if running >= target * (len(ranges) + 1) and len(ranges) < parts - 1:
            ranges.append(range(start, index + 1))
            start = index + 1
    if start < len(weights):
        ranges.append(range(start, len(weights)))
    return [part for part in ranges if len(part)]


def run(
    arrays: Callable[[], Mapping[str, np.ndarray]],
    tasks: Sequence[Task],
    *,
    most: int,
    check_cancelled: Callable[[], None] | None = None,
    progress: Callable[[float], None] | None = None,
) -> list[dict[str, Any] | None]:
    """Jede Aufgabe bei einem Arbeiter; je Aufgabe ihre Antworten oder ``None``.

    ``None`` heißt: Dieser Teil kam nicht zurück (Arbeiter gestorben, ohne
    Speicher, nicht bereit) — die Erkennung rechnet ihn selbst. Ein Abbruch
    beendet die beteiligten Arbeiter und wirft ``OperationCancelled``.
    ``arrays`` liefert die Felder des Körpers nur, wenn er nicht schon
    vorbereitet ist (:func:`prepare`); ``most`` begrenzt die Arbeiter.
    """
    results: list[dict[str, Any] | None] = [None] * len(tasks)
    if not tasks:
        return results
    wanted = min(len(tasks), most)
    _POOL.start(wanted)
    workers = _POOL.take(wanted)
    if not workers:
        return results
    segment = None
    with _PREPARED_LOCK:
        prepared = _PREPARED[0]
    if prepared is not None and prepared[0] == tasks[0].token:
        name, layout = (prepared[1].name if prepared[1] is not None else None), prepared[2]
    else:
        try:
            segment, layout = _pack(arrays())
        except (OSError, MemoryError) as problem:
            _log.warning("perceive workers get no body: %s", problem)
            _POOL.give_back(workers)
            return results
        name = segment.name if segment is not None else None
    pending = list(range(len(tasks)))
    busy: dict[int, tuple[_Worker, int]] = {}
    lost: list[_Worker] = []
    done = 0
    try:
        while pending or busy:
            for worker in workers:
                if pending and id(worker) not in busy and worker.ready:
                    index = pending.pop(0)
                    task = tasks[index]
                    try:
                        worker.connection.send(("ask", name, layout, task))
                    except OSError as problem:
                        _log.warning("perceive worker %s refused a task: %s", worker.pid, problem)
                        lost.append(worker)
                        continue
                    busy[id(worker)] = (worker, index)
                    count("tasks")
            workers = [worker for worker in workers if worker not in lost]
            if not workers:
                break
            if check_cancelled is not None:
                check_cancelled()
            ready = multiprocessing.connection.wait(
                [worker.connection for worker in workers]
                + [worker.process.sentinel for worker in workers],
                CANCEL_POLL_SECONDS,
            )
            for worker in workers:
                if worker.connection not in ready and worker.process.sentinel not in ready:
                    if not worker.ready and time.monotonic() - worker.started > STARTUP_SECONDS:
                        _log.warning("perceive worker %s did not get ready", worker.pid)
                        lost.append(worker)
                        _drop(busy, worker, pending)
                    continue
                try:
                    message = worker.connection.recv()
                except (EOFError, OSError) as problem:
                    _log.warning("perceive worker %s is gone: %s", worker.pid, problem)
                    count("lost")
                    lost.append(worker)
                    _drop(busy, worker, pending, give_up=True, results=results)
                    continue
                kind = message[0]
                if kind == "ready":
                    worker.ready = True
                    continue
                entry = busy.pop(id(worker), None)
                if entry is None:
                    continue
                if kind == "done":
                    results[entry[1]] = message[1]
                    count("returned")
                    count("answers", sum(len(found) for found in message[1].values()))
                else:
                    _log.warning("perceive worker %s could not answer: %s", worker.pid, message[1])
                done += 1
                if progress is not None:
                    progress(done / len(tasks))
            workers = [worker for worker in workers if worker not in lost]
            if not workers and (pending or busy):
                break
    except BaseException:
        # Ein Abbruch oder ein Fehler hier: Die Arbeiter rechnen noch an ihrem
        # Teil und gehören beendet, nicht zurück in den Vorrat.
        for worker in workers:
            worker.stop()
        for worker in lost:
            worker.stop()
        raise
    finally:
        if segment is not None:
            segment.close()
            with contextlib.suppress(OSError):
                segment.unlink()
    for worker in lost:
        worker.stop()
    _POOL.give_back(workers)
    return results


def _drop(
    busy: dict[int, tuple[_Worker, int]],
    worker: _Worker,
    pending: list[int],
    *,
    give_up: bool = False,
    results: list[dict[str, Any] | None] | None = None,
) -> None:
    """Die Aufgabe eines verlorenen Arbeiters: zurück in die Reihe, oder aufgegeben."""
    entry = busy.pop(id(worker), None)
    if entry is None:
        return
    if give_up:
        if results is not None:
            results[entry[1]] = None
        return
    pending.insert(0, entry[1])


def _pack(arrays: Mapping[str, np.ndarray]) -> tuple[shared_memory.SharedMemory | None, list[Any]]:
    """Der Körper einmal in einen gemeinsamen Speicher, den jeder Arbeiter liest."""
    from app.core.geom import kernel_jobs

    return kernel_jobs.pack(arrays)


def _read(name: str | None, layout: Sequence[Any]) -> dict[str, np.ndarray]:
    """Die Felder des Körpers als eigene Kopien; der Speicher bleibt für die anderen Arbeiter."""
    if name is None:
        return {field: np.empty(shape, dtype=np.dtype(dtype)) for field, dtype, shape, _ in layout}
    segment = shared_memory.SharedMemory(name=name, track=False)
    try:
        arrays = {}
        for field, dtype, shape, offset in layout:
            view = np.ndarray(shape, dtype=np.dtype(dtype), buffer=segment.buf, offset=offset)
            arrays[field] = np.array(view, copy=True)
            del view
        return arrays
    finally:
        segment.close()


def serve(connection: Any) -> None:
    """Die Seite des Arbeiters: Aufgaben annehmen, rechnen, Antworten zurückgeben.

    Je Aufgabe ``("ask", speicher, layout, Task)``; zurück geht
    ``("done", {frage: {schlüssel: antwort}})`` oder ``("failed", grund)``.
    ``("forget",)`` lässt den gehaltenen Körper los und bekommt keine Antwort.
    Er endet, wenn die Leitung zu ist. Nichts entweicht ihm — im Fensterpaket
    unter Windows ist ``sys.stderr`` ``None`` (wie ``kernel_jobs.serve``).
    """
    try:
        from app.core.perceive import features

        features.warm_worker()
        connection.send(("ready",))
        while True:
            message = connection.recv()
            if message and message[0] == "forget":
                features.forget_worker_body()
                continue
            if not message or message[0] != "ask":
                return
            _kind, name, layout, task = message
            try:
                answers = features.answered_ahead(functools.partial(_read, name, layout), task)
            except MemoryError as problem:
                # Der Aufrufer rechnet diesen Teil dann selbst.
                features.forget_worker_body()
                connection.send(("failed", f"MemoryError: {problem}"))
                continue
            except Exception as problem:
                features.forget_worker_body()
                connection.send(("failed", f"{type(problem).__name__}: {problem}"))
                continue
            connection.send(("done", answers))
    except EOFError, OSError, KeyboardInterrupt:
        return
    except BaseException:
        return


def chunk_count(patches: int, workers: int, least: int = PATCHES_PER_TASK) -> int:
    """Wie viele Aufgaben: je Arbeiter :data:`TASKS_PER_WORKER`, nie unter ``least``
    Flecken. Mehr Aufgaben als Arbeiter, weil die Gewichte schätzen: Wer früher
    fertig ist, nimmt die nächste."""
    if workers <= 0:
        return 0
    return max(1, min(workers * TASKS_PER_WORKER, math.ceil(patches / max(1, least))))
