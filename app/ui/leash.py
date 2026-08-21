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

from PySide6.QtCore import QObject, QThread, QTimer, Signal

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

#: Jeder gehaltene Arbeiter, über alle Leinen hinweg.
#:
#: **Modulweit und nicht nur an der Leine**, und der Grund ist ein Absturz, den
#: die Erstinbetriebnahme sichtbar gemacht hat: Ihr Dialog startet beim Aufbau
#: eine Erhebung. Wird er freigegeben — ein Test lässt ihn fallen, ein Fenster
#: räumt ihn weg —, während der Arbeiter noch läuft oder gerade fertig wurde,
#: dann geht mit dem Dialog die Leine, mit der Leine ihre Liste und damit die
#: letzte Referenz auf den ``QThread``. Der Speicherbereiniger zerstört das
#: C++-Objekt unter einem laufenden Thread, und der Abriss kommt später und
#: ohne Zeile — genau die Sorte, gegen die es dieses Modul gibt.
#:
#: Ein Arbeiter kostet hier nichts als seinen Zeiger, und er verschwindet,
#: sobald ``isRunning`` nein sagt.
_alive: set[Any] = set()

#: Der Zeitgeber braucht einen Empfänger, der die Widgets überlebt. Ein
#: Lambda ohne Empfänger läuft ins Leere, sobald das Fenster weg ist — und
#: genau dann muss noch jemand nachsehen, ob der Thread ausgelaufen ist.
_keeper: QObject | None = None


def _keeper_object() -> QObject:
    """Das langlebige Gegenstück zu den Widgets. Beim ersten Bedarf angelegt."""
    global _keeper
    if _keeper is None:
        _keeper = QObject()
    return _keeper


def alive() -> tuple[Any, ...]:
    """Was insgesamt noch gehalten wird. Für Tests und die Fehlersuche."""
    return tuple(_alive)


class Worker(QThread):
    """Ein Arbeiter, der auch mit dem Unerwarteten zurückkommt.

    **Ein ``run``, das eine Ausnahme durchlässt, sendet sein Ergebnissignal
    nie** — und wer darauf wartet, wartet für immer. Nachgestellt am
    Einrichtungsdialog für ComfyUI: Liegt die Installation unter ``Program
    Files``, wirft das Kopieren der Knoten einen ``PermissionError``. Die
    Ausnahme landet auf stderr, wo sie kein Kunde sieht; im Fenster steht
    „Wird eingerichtet …", der Balken läuft, der Knopf sagt „Abbrechen" — und
    dabei bleibt es, bis jemand das Programm beendet.

    Von dreiundzwanzig Arbeitern in der Oberfläche fing genau **einer** eine
    unerwartete Ausnahme, und das war der Versand der Rückmeldung. Die anderen
    zweiundzwanzig konnten ihr Fenster in einen Wartezustand ohne Ausgang
    bringen.

    Erwartete Fehler gehören weiter in ``work``: Sie sind ein Ergebnis und
    werden als eines zurückgegeben (``InstallResult.reason``,
    ``pull_model`` → Satz, ``SetupFailed`` → eigenes Signal). Was hier ankommt,
    ist das, womit niemand gerechnet hat, und dafür gibt es genau eine
    Antwort: sagen, dass es passiert ist, den Wartezustand auflösen, und die
    Zeile ins Protokoll (§33.2).

    Wer erbt, schreibt :meth:`work` statt ``run`` und verbindet ``crashed`` —
    ``tests/test_leash.py`` hält beides fest.
    """

    crashed = Signal(str)
    """Was schiefging, als Text — Ausnahmeart und Meldung, für „Details"."""

    def run(self) -> None:
        try:
            self.work()
        except Exception as problem:  # genau der Sinn dieser Klasse
            _log.exception("worker %s did not come back", type(self).__name__)
            self.crashed.emit(f"{type(problem).__name__}: {problem}")

    def work(self) -> None:
        """Was der Arbeiter tut. Unterklassen setzen das."""
        raise NotImplementedError


class WorkerLeash:
    """Hält fertige und ersetzte Arbeiter, bis Qt wirklich mit ihnen durch ist.

    ``context`` ist das Widget, dem die Zeitgeber gehören: ein Lambda ohne
    Empfänger läuft weiter, wenn das Fenster längst weg ist, und greift dann
    in ein zerstörtes C++-Objekt.
    """

    def __init__(self, context: QObject) -> None:
        self._context = context
        self._held: list[Any] = []

    def start(self, worker: Any) -> None:
        """Einen Arbeiter starten — und ihn ab diesem Moment halten.

        **Der Unterschied zu :meth:`hold_until_done` ist der Zeitpunkt, und er
        ist der ganze Punkt.** Gehalten wurde bisher erst, wenn ein Arbeiter
        fertig war; solange er lief, hing er allein am Feld seines Dialogs. Ein
        Dialog, der vorher freigegeben wird — ein Fenster räumt ihn weg, ein
        Test lässt ihn fallen —, nimmt damit die letzte Referenz auf einen
        **laufenden** Thread mit. Sichtbar wurde das, als die
        Erstinbetriebnahme ihre Erhebung in einen Arbeiter bekam: Die
        Testdatei brach reproduzierbar an der Stelle ab, an der ein Dialog aus
        einem vorigen Test einging.

        Wer einen Arbeiter über diese Methode startet, muss ihn nicht mehr
        selbst am Leben halten; sein Feld ist danach nur noch die Antwort auf
        „läuft gerade einer".
        """
        if worker is None:
            return
        _alive.add(worker)
        worker.finished.connect(lambda done=worker: self.hold_until_done(done))
        worker.start()

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
        _alive.add(worker)
        # Der Empfänger überlebt das Widget (siehe :data:`_keeper`): Stirbt der
        # Dialog zuerst, muss trotzdem noch jemand nachsehen, ob der Thread
        # ausgelaufen ist — sonst bleibt er für immer gehalten.
        QTimer.singleShot(0, _keeper_object(), lambda: self._release(worker))

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
        _alive.add(worker)
        # Nicht beim Signal selbst loslassen — dieselbe Begründung wie in
        # ``hold_until_done``, und derselbe Weg hinaus, damit es nur einen
        # gibt.
        worker.finished.connect(lambda done=worker: self.hold_until_done(done))

    def _release(self, worker: Any) -> None:
        """Einen ausgelaufenen Arbeiter loslassen — und keinen, der noch läuft."""
        if worker not in _alive:
            return
        if worker.isRunning():
            QTimer.singleShot(RELEASE_RETRY_MS, _keeper_object(), lambda: self._release(worker))
            return
        _alive.discard(worker)
        if worker in self._held:
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
