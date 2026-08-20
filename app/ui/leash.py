"""Die Halteleine für Arbeiter-Threads.

Ein ``QThread`` bekommt hier keinen Qt-Elternteil; ihn hält allein die
Python-Referenz. Fällt sie weg, während der Thread noch läuft, zerstört der
Speicherbereiniger das C++-Objekt unter ihm — eine Zugriffsverletzung ohne
Zeile, irgendwann später und selten reproduzierbar.

Das Hauptfenster hatte dieses Muster (``_retire``/``_hold_until_done``), die
Dialoge nicht: fünf Stellen schrieben ``self._worker = None`` direkt im
``finished``-Slot — zu früh, denn ``finished`` heißt „``run`` ist zurück",
nicht „das Objekt darf weg" —, und ein Lambda, das blind ``None`` schreibt,
trifft obendrein den Nachfolger, wenn der Vorgänger später fertig wird. Die
Gebietsregel beschreibt beides; hier steht es einmal statt sechsmal.
"""

from __future__ import annotations

from typing import Any, Final

from PySide6.QtCore import QObject, QTimer

from app.core.log import get_logger

_log = get_logger(__name__)

#: Wie lange bis zum nächsten Blick, wenn ein fertiger Arbeiter beim ersten
#: noch lief. Der eine Versuch von früher ließ ihn dauerhaft in der Liste,
#: und ``wait_all`` lief ihn bei jedem Aufruf mit ab.
RELEASE_RETRY_MS: Final = 50

#: Wie lange am Fensterende auf einen Arbeiter gewartet wird. Er hat ein
#: Abbruch-Token und sollte längst zurück sein; die Grenze ist für den Fall,
#: dass er es nicht ist — ein Fenster, das beim Schließen unbegrenzt wartet,
#: ist eingefroren und sagt es nicht.
WAIT_TIMEOUT_MS: Final = 2000


class WorkerLeash:
    """Hält fertige und ersetzte Arbeiter, bis Qt wirklich mit ihnen durch ist.

    ``context`` ist das Widget, dem die Zeitgeber gehören: ein Lambda ohne
    Empfänger läuft weiter, wenn das Fenster längst weg ist, und greift dann
    in ein zerstörtes C++-Objekt.
    """

    def __init__(self, context: QObject) -> None:
        self._context = context
        self._held: list[Any] = []

    def hold_until_done(self, worker: Any) -> None:
        """Den fertigen Arbeiter halten, bis ``isRunning`` nein sagt.

        Wer sein Feld leeren will, tut das im eigenen Slot davor und **nur
        für seinen eigenen Arbeiter** — siehe Gebietsregel.

        ``None`` geht durch, wie bei :meth:`retire`: Ein Slot, der sein Feld
        leert und den alten Inhalt hierherreicht, bekommt None, wenn schon
        jemand vor ihm aufgeräumt hat. Ohne diese Zeile landete None in der
        Liste, und der Zeitgeber danach fragte es nach ``isRunning`` — ein
        AttributeError im Teardown, weit weg von seiner Ursache.
        """
        if worker is None:
            return
        if worker not in self._held:
            self._held.append(worker)
        QTimer.singleShot(0, self._context, lambda: self._release(worker))

    def retire(self, worker: Any) -> None:
        """Hält einen ersetzten Arbeiter fest, bis er ausgelaufen ist.

        Sein Ergebnis will niemand mehr — aber sein Thread läuft noch, und
        ohne Referenz zerstört der Speicherbereiniger das QThread-Objekt
        unter ihm.
        """
        if worker is None or not worker.isRunning():
            return
        if worker in self._held:
            # Zweimal zurückgestellt heißt nicht zweimal gehalten: sonst stünde
            # er doppelt in der Liste, ``_release`` nähme nur das erste
            # Vorkommen heraus, und an ``finished`` hinge eine zweite Leitung,
            # die dasselbe noch einmal tut.
            return
        self._held.append(worker)
        # Nicht beim Signal selbst loslassen — dieselbe Begründung wie in
        # ``hold_until_done``, und derselbe Weg hinaus, damit es nur einen
        # gibt.
        worker.finished.connect(lambda done=worker: self.hold_until_done(done))

    def _release(self, worker: Any) -> None:
        """Einen ausgelaufenen Arbeiter loslassen — und keinen, der noch läuft."""
        if worker not in self._held:
            return
        if worker.isRunning():
            QTimer.singleShot(RELEASE_RETRY_MS, self._context, lambda: self._release(worker))
            return
        self._held.remove(worker)

    def pending(self) -> tuple[Any, ...]:
        """Was gerade gehalten wird — für das Warten am Fensterende."""
        return tuple(self._held)

    def wait_all(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Auf alle gehaltenen Arbeiter warten — am Ende eines Fensters.

        Ein Thread, der sein Fenster überlebt, nimmt den Prozess mit. Genau
        dieser Fall stand hier stumm: ``wait`` gibt ``False`` zurück, wenn die
        Frist reißt, und der Rückgabewert wurde nicht angesehen. Der Abriss kam
        dann später und ohne Zeile — dieselbe Sorte Absturz, gegen die es
        dieses Modul überhaupt gibt.

        Erzwungen wird nichts: ``terminate`` bricht einen Thread mitten im
        Rechnen ab und hinterlässt genau die halb freigegebenen Objekte, die
        den Absturz ausmachen. Was hier steht, ist die Zeile im Protokoll, die
        den nächsten Abriss erklärt.
        """
        for worker in self.pending():
            if worker.isRunning() and not worker.wait(timeout_ms):
                _log.warning(
                    "worker %s did not finish within %d ms — the process may crash on exit",
                    type(worker).__name__,
                    timeout_ms,
                )
