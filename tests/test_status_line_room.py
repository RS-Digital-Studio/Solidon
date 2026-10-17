"""Die Zahlenzeile der Statusleiste steht ganz da; gekürzt wird die Meldung (FD-90).

Statusmeldung und Zahlenzeile teilen sich die Statusleiste. Ein langer Satz
nahm der Zahlenzeile die Breite: Im Funktionsdurchgang stand „14 g ·“, die
Summe links abgeschnitten, die Differenz endete in „Schrit…“. Hier steht ein
langer Satz neben Material, Dauer und Differenz in einem schmalen Fenster.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget

from app.core.slice.estimate import Estimate
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import MESHES

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


def _whole(widget: QWidget) -> str:
    """Leer, wenn das Feld so breit steht, wie es verlangt; sonst die Zahlen."""
    if widget.width() >= widget.sizeHint().width():
        return ""
    return f"{type(widget).__name__} {widget.width()} von {widget.sizeHint().width()} px"


def test_the_numbers_stand_whole_the_moment_they_arrive_after_opening(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Weg des Funktionsdurchgangs: Szene öffnen, erste Auswertung, die Zahlen kommen.

    Die Breite hing an nachgereichten ``LayoutRequest``-Ereignissen — erst des
    Knopfs, dann der Leiste. Bis dahin stand die Zahl in der Breite der leeren
    Zeile, und am echten Fenster blieb es dabei: „3,5 ç“ statt
    „3,5 g · 6 min“ im ersten Bild (Schlusslauf L4, Fall 002).
    """
    from app.ui.facts import PrintFacts

    facts = window.facts
    seen: list[str] = []
    shown = PrintFacts.show_estimate

    def watched(self: PrintFacts, *args: object, **kwargs: object) -> None:
        shown(self, *args, **kwargs)  # type: ignore[arg-type]
        if self is facts and self.summary.text():
            seen.extend(filter(None, (_whole(self), _whole(self.summary), _whole(self.delta))))

    monkeypatch.setattr(PrintFacts, "show_estimate", watched)
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    assert facts.summary.text(), "Voraussetzung: die Zahlen sind da"
    assert not seen, seen


def _facts(window: MainWindow, grown: bool) -> tuple[QWidget, ...]:
    estimate = (
        Estimate(material_mm3=120_000.0, grams=142.0, seconds=36_000.0)
        if grown
        else Estimate(material_mm3=1_000.0, grams=1.0, seconds=60.0)
    )
    window.facts.show_estimate(estimate, "p", state=1, basis=grown)
    return window.facts, window.facts.summary


def _alerts(window: MainWindow, grown: bool) -> tuple[QWidget, ...]:
    window.right_column.hide()
    window._mark_status_alerts(12_345 if grown else 1)
    return (window.alert_button,)


def _trial(window: MainWindow, grown: bool) -> tuple[QWidget, ...]:
    from app.core import activation

    state = activation.Activation(damaged=True) if grown else activation.Activation(days_left=2)
    activation._cached = state
    window._trial_status_line()
    return (window.trial_line,)


def _booking(window: MainWindow, grown: bool) -> tuple[QWidget, ...]:
    notice = window.usage_notice
    notice.show()
    if grown:
        notice._declined.add(notice.choice.currentData())
    notice._sync_review()
    return notice, notice.review


@pytest.mark.parametrize("field", [_facts, _alerts, _trial, _booking])
def test_a_lost_layout_request_does_not_keep_a_field_narrow(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, field
) -> None:
    """Geht die nachgereichte Anfrage verloren, bleibt kein Feld der Leiste schmal.

    So stand es am echten Fenster: Die Zahlenzeile blieb über Sekunden und
    viele Ereignisrunden in der Breite der leeren Zeile. Dieselbe Bauart haben
    die Felder, deren Text nach dem Aufbau wächst: Befundzähler,
    Testzeitraumzeile, Filamentbuchung. Je Feld allein, denn ein anderes,
    das erscheint, legt die Leiste nebenbei neu.
    """
    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation._cached)
    window.resize(4200, 700)
    field(window, False)
    for _round in range(3):
        qt_app.processEvents()

    widgets = field(window, True)
    QCoreApplication.removePostedEvents(None, QEvent.Type.LayoutRequest)
    qt_app.processEvents()

    assert all(widget.isVisible() for widget in widgets), "Voraussetzung: das Feld steht da"
    assert not [said for widget in widgets if (said := _whole(widget))]
