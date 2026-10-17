"""Die Handlungsknöpfe im Prüfbericht stehen bei jeder Schriftgröße ganz da (FD-185).

Bei 18 Punkt waren die Knöpfe unter einem gewählten Befund auf 26 Bildpunkte
gestaucht, ihre Mindesthöhe ist 38: Die Beschriftung war oben und unten
abgeschnitten, auch bei 11 Punkt fehlten zwei Bildpunkte. Geprüft am echten
Weg — ein Projekt, dessen Kette an einem Befund mit Handlungen anhält, im
Fenster in Prüfschrift geöffnet, der Befund im Bericht gewählt. Das Fenster ist
so niedrig, dass der Bericht enger ist als sein Wunschmaß: Erst dort zeigt sich,
dass das Stylesheet eine ausdrückliche Mindesthöhe von 26 Punkten setzt, die die
Höhe der Schrift schlägt (``button_floor``).

Dazu ein Knopf ohne Bericht: Er folgt einem Wechsel der Schriftgröße in beide
Richtungen, und ein Knopf mit kleinerer Höchsthöhe bleibt, wie er ist.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton

from app.core.scene.project import save
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.style import apply_style
from app.ui.theme import apply_theme
from tests.bundled_fonts import bundled_font
from tools import function_scenes

#: Höchsthöhe eines Knopfs, der absichtlich kleiner ist als seine Schrift.
SMALL_ON_PURPOSE = 20


def _rounds(qt_app: QApplication, count: int = 40) -> None:
    for _ in range(count):
        qt_app.processEvents()
        time.sleep(0.005)


@pytest.fixture(params=[11, 18], ids=["11pt", "18pt"])
def halted_report(
    qt_app: QApplication, tmp_path: Path, request: pytest.FixtureRequest
) -> Iterator[MainWindow]:
    """Das Fenster in Prüfschrift, der Bericht vorn, der haltende Befund gewählt."""
    path = tmp_path / "halt.p3d"
    save(function_scenes.build_scene("halt"), path)
    with bundled_font(qt_app, int(request.param)):
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        window = MainWindow(Session(), UiSettings())
        window.resize(1920, 700)
        window.show()
        window._show_start_screen(False)
        try:
            window.open_path(path)
            assert window.session.wait_for_idle(120_000)
            _rounds(qt_app)
            result = window.session.last_result
            assert result is not None and result.stopped_at is not None, "Voraussetzung: Halt"
            window._focus_report(force=True)
            _rounds(qt_app)
            listing = window.report.list
            rows = [listing.item(row) for row in range(listing.count())]
            halting = [
                item
                for item in rows
                if (found := item.data(Qt.ItemDataRole.UserRole)) is not None
                and found.op_id == result.stopped_at
                and found.suggestions
            ]
            assert halting, "Voraussetzung: der haltende Befund steht im Bericht"
            listing.setCurrentItem(halting[0])
            halting[0].setSelected(True)
            _rounds(qt_app)
            yield window
        finally:
            assert window.session.wait_for_idle(120_000)
            window.wait_for_workers()
            window.hide()
            window.deleteLater()
            qt_app.processEvents()
    apply_style(qt_app, "light")


def test_every_offer_button_gets_at_least_its_minimum_height(
    qt_app: QApplication, halted_report: MainWindow
) -> None:
    report = halted_report.report
    buttons = [
        button for button in report._offers.findChildren(QPushButton) if button.isVisibleTo(report)
    ]
    assert buttons, "Voraussetzung: der Befund bietet Handlungen an"
    squeezed = [
        (button.text(), button.height(), button.minimumSizeHint().height())
        for button in buttons
        if button.height() < button.minimumSizeHint().height()
    ]
    assert not squeezed, squeezed
    narrow = [
        (button.text(), button.width(), button.minimumSizeHint().width())
        for button in buttons
        if button.width() < button.minimumSizeHint().width()
    ]
    assert not narrow, narrow


def test_a_button_follows_the_font_both_ways(
    qt_app: QApplication,
) -> None:
    """Größer und wieder kleiner; ein absichtlich kleiner Knopf bleibt klein."""
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from app.ui.button_floor import text_height

    holder = QWidget()
    column = QVBoxLayout(holder)
    plain = QPushButton("Eingabe korrigieren", holder)
    small_on_purpose = QPushButton("i", holder)
    small_on_purpose.setMaximumHeight(SMALL_ON_PURPOSE)
    column.addWidget(plain)
    column.addWidget(small_on_purpose)
    try:
        with bundled_font(qt_app, 11) as font:
            apply_style(qt_app, "light")
            holder.show()
            _rounds(qt_app)
            small = plain.minimumHeight()
            assert small >= plain.sizeHint().height()
            font.setPointSize(18)
            qt_app.setFont(font)
            apply_style(qt_app, "light")
            _rounds(qt_app)
            big = plain.minimumHeight()
            assert big >= plain.sizeHint().height() > small
            holder.resize(holder.width(), 10)
            _rounds(qt_app)
            assert plain.height() >= plain.sizeHint().height(), "nicht gestaucht"
            # Nicht über seine Höchsthöhe gehoben; die 26 Punkte setzt Qt aus dem Stylesheet.
            assert small_on_purpose.minimumHeight() < text_height(small_on_purpose)
            font.setPointSize(11)
            qt_app.setFont(font)
            apply_style(qt_app, "light")
            _rounds(qt_app)
            assert plain.minimumHeight() == text_height(plain) < big, "wieder klein"
    finally:
        holder.close()
        holder.deleteLater()
        apply_style(qt_app, "light")
