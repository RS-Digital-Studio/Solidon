"""Die Zahlenzeile der Statusleiste steht ganz da; gekürzt wird die Meldung (FD-90).

Statusmeldung und Zahlenzeile teilen sich die Statusleiste. Ein langer Satz
nahm der Zahlenzeile die Breite: Im Funktionsdurchgang stand „14 g ·“, die
Summe links abgeschnitten, die Differenz endete in „Schrit…“. Hier steht ein
langer Satz neben Material, Dauer und Differenz in einem schmalen Fenster.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from app.core.slice.estimate import Estimate
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

_LONG = (
    "Die Kette hält an Schritt 12 (Bohrung setzen) an — ein neuer Schritt dahinter "
    "würde nicht gerechnet. Der Weg weiter steht im Prüfbericht, samt allem, was dazu "
    "noch zu sagen ist, und noch etwas mehr."
)


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    built = MainWindow(Session(), UiSettings())
    built.resize(1000, 700)
    built.show()
    built._show_start_screen(False)
    qt_app.processEvents()
    yield built
    built.release()
    built.close()
    built.deleteLater()
    qt_app.processEvents()


def test_the_numbers_stand_whole_beside_a_long_message(
    window: MainWindow, qt_app: QApplication
) -> None:
    facts = window.facts
    facts.show_estimate(Estimate(material_mm3=12_000.0, grams=14.2, seconds=840.0), "p", state=1)
    facts.show_estimate(Estimate(material_mm3=10_000.0, grams=12.0, seconds=700.0), "p", state=2)
    window.announce(_LONG)
    qt_app.processEvents()
    for label in (facts.summary, facts.delta):
        assert label.text(), "beide Zeilen tragen Text"
        assert label.width() >= label.sizeHint().width(), (
            f"{label.text()!r} hat {label.width()} von {label.sizeHint().width()} px"
        )
    assert facts.isVisible() and facts.width() >= facts.sizeHint().width()
    message = window.status_message
    assert message.text() == _LONG, "der volle Satz bleibt die Auskunft"
    assert message.width() < message.fontMetrics().horizontalAdvance(_LONG), "gekürzt"
    assert message.toolTip() == _LONG, "gekürzt steht der ganze Satz in der Kurzhilfe"
    right = message.mapTo(window, message.rect().topRight()).x()
    assert right <= window.width(), "die Meldung bleibt im Fenster"
