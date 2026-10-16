"""Der Schrittautomat des Prüfstands und seine Zeitgeber (B6, D0-P, RM-737).

Ein Klick, der einen Dialog über ``exec()`` öffnet, kehrt erst nach dessen Ende
zurück; ein linear geschriebener Ablauf bliebe dort stehen. :class:`StepMachine`
plant deshalb den nächsten Schritt über einen Zeitgeber **vor** der Handlung,
und er läuft in der verschachtelten Schleife des Dialogs weiter (Muster
``make_web_images.while_open``). Am Fenster ist der Zeitgeber
:func:`qt_schedule`, im Test ein nachgestellter.

Falle: **Gelesen wird erst nach der Wirkung.** ``Step.settle_ms`` ist die Ruhe
**nach** einem Schritt, nicht davor. Vor jedem Leseschritt steht deshalb ein
Warteschritt auf den erwarteten Zustand (:func:`until_step`, am Funktionsfall
``FunctionFlow.still_step`` für eine Fläche, die stillstehen muss) — sonst liest
der Prüfstand den Stand vor der Handlung (Review M1).

Ein Fund unterwegs ist :class:`BenchFinding`; der Automat hält an und das
Protokoll sagt warum.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Final

#: Takt des Schrittautomaten in Millisekunden.
TICK_MS: Final = 15

#: Wie oft der Automat ein offen gebliebenes Fenster mit Escape zu schließen
#: versucht, bevor er notiert, dass es klemmt (Review L12).
MOST_UNSTICKS: Final = 8

#: Ruhe nach einem Klick, bevor der nächste gerechnet wird: Ein Reiter, ein Menü
#: oder eine Klappe steht nach einer Ereignisrunde; die Karte setzt ihre Höhe
#: über einen Nullzeitgeber (``fenster.md``, „Wie die Karten ihre Höhe teilen“).
SETTLE_MS: Final = 120

#: Wie lange ein Schritt auf seine Voraussetzung wartet (Sekunden).
STEP_TIMEOUT_S: Final = 180.0

#: Wie lange eine ganze Phase eines Funktionsfalls dauern darf (Sekunden).
PHASE_TIMEOUT_S: Final = 900.0


class BenchFinding(Exception):  # noqa: N818 - ein Fund, kein Fehler des Prüfstands
    """Ein Fund unterwegs: Der Weg endet hier, und das Protokoll sagt warum."""

    def __init__(self, kind: str, target: str, detail: str) -> None:
        super().__init__(f"{kind}: {target} — {detail}")
        self.kind = kind
        self.target = target
        self.detail = detail


@dataclass(slots=True)
class Step:
    """Ein Schritt des Automaten: warten, bis ``ready`` gilt, dann ``act``.

    ``act`` darf blockieren — ein Klick, der einen Dialog über ``exec()`` öffnet,
    kehrt erst nach dessen Ende zurück. Der Automat hat den nächsten Schritt dann
    schon geplant (:meth:`StepMachine._tick`). ``settle_ms`` ist die Ruhe danach.
    """

    name: str
    act: Callable[[StepMachine], object]
    ready: Callable[[], bool] | None = None
    settle_ms: int = TICK_MS
    timeout_s: float = STEP_TIMEOUT_S
    #: Was eine abgelaufene Frist bedeutet, wenn sie ein Fund ist und kein Fehler
    #: des Prüfstands — „keine Rückmeldung“ nach dem Übernehmen (Prüfpunkt 6).
    on_timeout: Callable[[], BenchFinding] | None = None


class StepMachine:
    """Ereignisgetriebener Ablauf über einen Zeitgeber, auch durch modale Schleifen (B6).

    ``schedule(ms, rückruf)`` ist am Fenster ``QTimer.singleShot``, im Test ein
    nachgestellter Zeitgeber. Je Takt prüft der Automat die Voraussetzung des
    nächsten Schritts; ist sie erfüllt, plant er den folgenden Takt **und dann**
    erst die Handlung. So läuft der nächste Schritt in der Schleife eines
    Dialogs, den diese Handlung geöffnet hat. Fertig ist der Automat, wenn kein
    Schritt mehr wartet und keine Handlung mehr läuft (:attr:`done`).
    """

    def __init__(
        self,
        schedule: Callable[[int, Callable[[], None]], None],
        clock: Callable[[], float],
        *,
        tick_ms: int = TICK_MS,
        unstick: Callable[[], None] | None = None,
        on_stuck: Callable[[], None] | None = None,
        nested: Callable[[], bool] | None = None,
    ) -> None:
        self._schedule = schedule
        self._clock = clock
        self._tick_ms = tick_ms
        self._unstick = unstick
        self._on_stuck = on_stuck
        #: Ob eine modale Schleife läuft, die keine Handlung dieses Automaten
        #: öffnete — ein Arbeiter fragte, eine Absage kam als Meldung. Dann kehrt
        #: auch ``drive`` nicht zurück, und der Automat räumt sie ab wie eine
        #: eigene (FD-101: fünf Minuten in ``show_error`` und ``_on_ask``).
        self._nested = nested
        #: Nach :data:`MOST_UNSTICKS` Versuchen mit Escape einmal ``on_stuck`` —
        #: nicht alle 120 ms Escape bis zur Frist des Elternprozesses (Review L12).
        self.stuck = False
        self.queue: list[Step] = []
        self.index = 0
        self.depth = 0
        self.stopped = False
        self.error: str | None = None
        self.finding: BenchFinding | None = None
        self.log: list[dict[str, Any]] = []
        self.unsticks = 0
        self.deadline: float | None = None
        self._waiting_since: float | None = None

    def start(self, steps: Iterable[Step], timeout_s: float | None = None) -> None:
        self.queue = list(steps)
        self.index = 0
        self._waiting_since = None
        self.deadline = None if timeout_s is None else self._clock() + timeout_s
        self._schedule(0, self._tick)

    def insert(self, steps: Iterable[Step]) -> None:
        """Schritte vor den nächsten wartenden — für einen Weg, der unterwegs wächst."""
        self.queue[self.index : self.index] = list(steps)

    @property
    def finished(self) -> bool:
        return self.stopped or self.index >= len(self.queue)

    @property
    def done(self) -> bool:
        """Kein Schritt wartet mehr, und keine Handlung steht noch auf dem Stapel."""
        return self.finished and self.depth == 0

    def stop(self, *, error: str | None = None, finding: BenchFinding | None = None) -> None:
        if not self.stopped:
            self.stopped = True
            self.error = error
            self.finding = finding

    def _tick(self) -> None:
        now = self._clock()
        if not self.finished and self.deadline is not None and now > self.deadline:
            self.log.append({"step": "phase", "event": "timeout", "t": now})
            self.stop(error="Zeitgrenze der Phase überschritten")
        if self.finished:
            # Steht noch eine Handlung in einer modalen Schleife, kehrt sie erst
            # zurück, wenn ihr Fenster schließt — am Fenster mit Escape, höchstens
            # MOST_UNSTICKS Mal; dann einmal ``on_stuck``, das notiert, welches
            # Fenster es war, und es noch auf anderem Weg versucht.
            blocked = self.depth > 0 or (self._nested is not None and self._nested())
            if blocked and self._unstick is not None:
                if self.unsticks < MOST_UNSTICKS:
                    self.unsticks += 1
                    self.log.append({"step": "unstick", "event": "act", "t": now})
                    self._unstick()
                elif not self.stuck:
                    self.stuck = True
                    self.log.append({"step": "unstick", "event": "stuck", "t": now})
                    if self._on_stuck is not None:
                        self._on_stuck()
                self._schedule(max(SETTLE_MS, self._tick_ms), self._tick)
            return
        step = self.queue[self.index]
        if self._waiting_since is None:
            self._waiting_since = now
        if step.ready is not None:
            try:
                ready = step.ready()
            except Exception:
                self.log.append({"step": step.name, "event": "ready-error", "t": now})
                self.stop(error=f"{step.name}: {traceback.format_exc()}")
                self._schedule(self._tick_ms, self._tick)
                return
            if not ready:
                if now - self._waiting_since > step.timeout_s:
                    self.log.append({"step": step.name, "event": "timeout", "t": now})
                    if step.on_timeout is not None:
                        self.stop(finding=step.on_timeout())
                    else:
                        reason = f"{step.name}: Zeitgrenze von {step.timeout_s:.0f} s überschritten"
                        self.stop(error=reason)
                # Auch nach einer Absage tickt der Abbau weiter: Die auslösende
                # Handlung kann noch in ihrer modalen Schleife stehen.
                self._schedule(self._tick_ms, self._tick)
                return
        self.index += 1
        self._waiting_since = None
        self.log.append({"step": step.name, "event": "act", "t": now})
        # Erst planen, dann handeln: Blockiert die Handlung in einer modalen
        # Schleife, läuft der nächste Takt darin.
        self._schedule(max(step.settle_ms, self._tick_ms), self._tick)
        self.depth += 1
        try:
            step.act(self)
        except BenchFinding as finding:
            self.log.append({"step": step.name, "event": "finding", "t": self._clock()})
            self.stop(finding=finding)
        except Exception:
            self.log.append({"step": step.name, "event": "error", "t": self._clock()})
            self.stop(error=f"{step.name}: {traceback.format_exc()}")
        finally:
            self.depth -= 1
            self.log.append({"step": step.name, "event": "returned", "t": self._clock()})


def drive(
    machine: StepMachine,
    steps: Iterable[Step],
    pump: Callable[[], None],
    clock: Callable[[], float],
    timeout_s: float = PHASE_TIMEOUT_S,
) -> None:
    """Fährt den Automaten, bis er fertig ist; ``pump`` lässt die Ereignisse laufen.

    Am Fenster ist ``pump`` ``processEvents`` mit kurzem Schlaf — nie
    ``QTest.qWait``, das den GIL hält (``tests.md``, „Beim Schreiben“). Die
    Zeitgrenze prüft der Automat selbst in jedem Takt, auch in einer modalen
    Schleife, in der diese Schleife hier gerade nicht läuft; danach räumt er
    über ``unstick`` ab, bis keine Handlung mehr auf dem Stapel steht.
    """
    machine.start(steps, timeout_s)
    while not machine.done:
        pump()
        if machine.deadline is not None and clock() > machine.deadline + timeout_s:
            # Der Automat hat seine Frist und eine zweite dazu verpasst — dann
            # tickt er nicht mehr, und diese Schleife ist die letzte Wache.
            machine.stop(error=f"Phase nach {2 * timeout_s:.0f} s nicht fertig")
            return


def qt_schedule(milliseconds: int, callback: Callable[[], None]) -> None:
    """Der Zeitgeber des Automaten am Fenster; er feuert auch in ``exec()``-Schleifen."""
    from PySide6.QtCore import QTimer

    QTimer.singleShot(milliseconds, callback)


def nested_since_now() -> Callable[[], bool]:
    """Die Frage ``StepMachine.nested`` am Fenster: läuft eine tiefere Schleife als jetzt?

    Gemessen an ``QThread.loopLevel`` beim Anlegen des Automaten. Tiefer
    geschachtelt ist ein Fenster, das während ``pump`` aufging — ein Arbeiter
    fragte, eine Absage kam als Meldung; ohne diese Frage stand ``drive`` in
    dessen Schleife bis zur Frist des Elternprozesses. Funktionsfall
    (FD-172) und Dateifall (FD-173) fragen dasselbe.
    """
    from PySide6.QtCore import QThread

    level = QThread.currentThread().loopLevel()
    return lambda: QThread.currentThread().loopLevel() > level


def until_step(
    name: str, condition: Callable[[], bool], at_most_s: float, clock: Callable[[], float]
) -> Step:
    """Warten, bis ``condition`` gilt — höchstens ``at_most_s``, dann geht es ohne weiter.

    Die Ruhe eines Schritts (``settle_ms``) liegt **nach** ihm (Review M1): Ein
    Leseschritt mit Ruhe liest sofort und wartet danach. Wer lesen will, stellt
    diesen Schritt davor. Kein Fehler, wenn die Frist verstreicht: Was dann zu
    lesen ist, ist die Antwort (etwa „keine Wirkung“).
    """
    since: dict[str, float | None] = {"t": None}

    def ready() -> bool:
        now = clock()
        if since["t"] is None:
            since["t"] = now
        return condition() or now - since["t"] >= at_most_s

    return Step(name, lambda machine: None, ready=ready, timeout_s=at_most_s + STEP_TIMEOUT_S)
