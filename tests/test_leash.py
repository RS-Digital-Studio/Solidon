"""Die Halteleine für Arbeiter-Threads (`app/ui/leash.py`).

Ein ``QThread`` hat hier keinen Qt-Elternteil; ihn hält allein die
Python-Referenz. Fällt sie weg, während der Thread noch läuft, zerstört der
Speicherbereiniger das C++-Objekt unter ihm — eine Zugriffsverletzung ohne
Zeile, irgendwann später und selten reproduzierbar. Genau deshalb hat die
Leine eigene Tests: Was sie falsch macht, fällt nicht dort auf, wo es
passiert.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import QApplication

from app.ui.leash import WorkerLeash


class _Schlaefer(QThread):
    """Ein Arbeiter, der lange genug lebt, um beim Halten noch zu laufen."""

    def run(self) -> None:
        self.msleep(120)


def test_a_worker_that_is_none_goes_through_quietly(qt_app: QApplication) -> None:
    """``None`` ist kein Arbeiter, und die Leine soll daran nicht ersticken.

    Ein Slot, der sein Feld leert und den alten Inhalt an die Leine reicht,
    bekommt ``None``, wenn vor ihm schon jemand aufgeräumt hat — beim
    Aufräumen einer Sitzung passiert genau das. Ohne die Prüfung landete
    ``None`` in der Liste, und der Zeitgeber danach fragte es nach
    ``isRunning``: ein ``AttributeError`` im Teardown, weit weg von seiner
    Ursache. ``retire`` fing den Fall seit jeher ab, ``hold_until_done``
    nicht.
    """
    leine = WorkerLeash(QObject())

    leine.hold_until_done(None)
    leine.retire(None)

    assert leine.pending() == (), "None gehört nicht in die Halteliste"


def test_a_finished_worker_is_held_until_it_really_stopped(qt_app: QApplication) -> None:
    """``finished`` heißt „``run`` ist zurück", nicht „das Objekt darf weg"."""
    leine = WorkerLeash(QObject())
    arbeiter = _Schlaefer()
    arbeiter.start()

    leine.hold_until_done(arbeiter)
    assert arbeiter in leine.pending(), "der laufende Arbeiter wird nicht gehalten"

    leine.wait_all()
    assert not arbeiter.isRunning()


def test_two_workers_are_held_side_by_side(qt_app: QApplication) -> None:
    """Eine Liste, kein Feld — das ist der ganze Unterschied.

    Die Sitzung hielt je Arbeiterart genau einen, und der nächste löste ihn
    ab. Bei einer Kette geht das schief: ``_on_thread_done`` startet bei
    ``_rerun_pending`` sofort den nächsten Lauf, und wird der schnell fertig,
    überschreibt er das Feld, während Qt den Vorgänger noch abräumt.
    """
    leine = WorkerLeash(QObject())
    erster, zweiter = _Schlaefer(), _Schlaefer()
    erster.start()
    zweiter.start()

    leine.hold_until_done(erster)
    leine.hold_until_done(zweiter)

    assert set(leine.pending()) == {erster, zweiter}, "der zweite hat den ersten verdrängt"
    leine.wait_all()


# --- gehalten ab dem Start, nicht ab dem Ende -----------------------------------


def test_a_worker_is_held_from_the_moment_it_starts(qt_app: QApplication) -> None:
    """Der Absturz, den die Erstinbetriebnahme sichtbar gemacht hat.

    Gehalten wurde bisher erst, wenn ein Arbeiter fertig war; solange er lief,
    hing er allein am Feld seines Dialogs. Ein Dialog, der vorher freigegeben
    wird, nahm damit die letzte Referenz auf einen **laufenden** Thread mit —
    und der Speicherbereiniger zerstörte das C++-Objekt darunter.
    """
    import app.ui.leash as leash_module

    leine = WorkerLeash(QObject())
    arbeiter = _Schlaefer()

    leine.start(arbeiter)
    try:
        assert arbeiter in leash_module.alive(), "gehalten, während er läuft"
    finally:
        arbeiter.wait(2000)


def test_a_started_worker_is_let_go_after_it_stopped(qt_app: QApplication) -> None:
    """Und wieder losgelassen — sonst wäre die Menge ein Leck."""
    import app.ui.leash as leash_module

    leine = WorkerLeash(QObject())
    arbeiter = _Schlaefer()

    leine.start(arbeiter)
    arbeiter.wait(2000)
    for _ in range(100):
        qt_app.processEvents()
        if arbeiter not in leash_module.alive():
            break
        arbeiter.msleep(10)

    assert arbeiter not in leash_module.alive()


def test_a_worker_survives_the_death_of_its_leash(qt_app: QApplication) -> None:
    """Der eigentliche Fall: Der Halter geht, der Thread läuft weiter.

    Die Menge ist modulweit und nicht an der Leine, und der Zeitgeber hängt an
    einem Objekt, das die Widgets überlebt. Ohne beides bliebe hier ein
    laufender Thread ohne Referenz zurück.
    """
    import gc

    import app.ui.leash as leash_module

    arbeiter = _Schlaefer()
    besitzer = QObject()
    WorkerLeash(besitzer).start(arbeiter)

    del besitzer
    gc.collect()

    assert arbeiter in leash_module.alive(), "die modulweite Menge hält ihn"
    arbeiter.wait(2000)
    for _ in range(100):
        qt_app.processEvents()
        if arbeiter not in leash_module.alive():
            break
        arbeiter.msleep(10)
    assert arbeiter not in leash_module.alive(), "und lässt ihn danach los"
