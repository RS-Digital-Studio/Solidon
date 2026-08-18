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
