"""Die Ladeanzeige und ihre Wartezeitauskunft (§2.8, §19.3).

Bauplan §2.8 staffelt die Anzeige nach Dauer, und die letzte Stufe war nie
gebaut: „über 10 s zusätzlich eine Schätzung, wenn möglich". Prozent sagt, wie
weit ein Lauf ist — nicht, wie lange man noch wartet, und genau das ist die
Frage, die jemand vor einem Fortschrittsbalken hat.

Geprüft wird über die Startzeit von Hand, nicht über echtes Warten: Ein Test,
der zehn Sekunden schläft, prüft die Uhr und nicht das Verhalten.
"""

from __future__ import annotations

import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.i18n import tr
from app.ui.loading import ESTIMATE_AFTER_S, ESTIMATE_FROM, LoadingVeil


def _running(veil: LoadingVeil, seconds: float) -> None:
    """Tut so, als liefe der Lauf schon so lange."""
    veil._started = time.monotonic() - seconds


def test_the_first_seconds_get_no_estimate(qt_app: QApplication) -> None:
    """Der Anfang eines Laufs sagt wenig über seinen Rest.

    Eine Zahl, die erst „noch 40 Sekunden" und dann „noch zwei Minuten" sagt,
    ist schlechter als keine — deshalb schweigt sie, bis sie etwas weiß.
    """
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, ESTIMATE_AFTER_S - 2.0)
        veil.step(0.5, "rechnet")

        assert veil.remaining() == ""
    finally:
        veil.deleteLater()


def test_a_run_that_has_barely_started_gets_no_estimate(qt_app: QApplication) -> None:
    """Bei drei Prozent ist der Hochrechnungsfehler größer als die Aussage."""
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, 60.0)
        veil.step(ESTIMATE_FROM / 2, "rechnet")

        assert veil.remaining() == ""
    finally:
        veil.deleteLater()


def test_the_estimate_follows_what_already_passed(qt_app: QApplication) -> None:
    """Dreißig Sekunden für die Hälfte heißt dreißig Sekunden für den Rest."""
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, 30.0)
        veil.step(0.5, "rechnet")

        assert veil.remaining() == tr("noch etwa {sekunden} s").format(sekunden=30)
    finally:
        veil.deleteLater()


def test_a_long_run_says_minutes_not_hundreds_of_seconds(qt_app: QApplication) -> None:
    """„noch etwa 270 s" ist eine Zahl, die niemand in eine Vorstellung
    übersetzt."""
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, 30.0)
        veil.step(0.1, "rechnet")

        assert tr("min") in veil.remaining()
    finally:
        veil.deleteLater()


def test_the_end_is_named_not_counted(qt_app: QApplication) -> None:
    """Unter fünf Sekunden ist eine Sekundenzahl Unruhe, kein Trost."""
    veil = LoadingVeil()
    try:
        veil.begin("Projekt öffnen")
        _running(veil, 30.0)
        veil.step(0.95, "rechnet")

        assert veil.remaining() == tr("gleich fertig")
    finally:
        veil.deleteLater()


def test_a_second_run_starts_its_own_clock(qt_app: QApplication) -> None:
    """Sonst erbt der nächste Lauf die Wartezeit des vorigen und meldet beim
    ersten Prozent, es dauere noch Stunden."""
    veil = LoadingVeil()
    try:
        veil.begin("Erster Lauf")
        _running(veil, 300.0)
        veil.end()

        veil.begin("Zweiter Lauf")
        veil.step(0.5, "rechnet")

        assert veil.remaining() == "", "die Uhr des vorigen Laufs lief weiter"
    finally:
        veil.deleteLater()
