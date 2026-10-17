"""Im neuen Projekt sind die leeren Sätze der linken Karte so hoch wie ihr Text (D1 zu FD-133).

Der Folger aus FD-133 pinnte nur die Mindesthöhe. Die Karte misst ihre Panels
aber nach dem Größenwunsch, und ``QLabel.sizeHint`` rechnet an Qts Schätzbreite:
Im neuen Projekt standen „Noch keine Objekte …“ und „Noch keine Schritte …“ in
de, es, fr, it und pt eine Zeile höher als ihr Text (Review 2 F2a/D, D1). Der
Test des Zwillings maß einen einzeln aufgezogenen Baum, in dem das Layout dem
Satz seine Breitenhöhe gibt; hier misst das Hauptfenster, wie der Kunde es
sieht.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from app.i18n import get_language, set_language
from app.i18n.catalog import available_languages, install_language
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.style import apply_style
from app.ui.theme import apply_theme
from tests.bundled_fonts import bundled_font

#: So viele Punkte darf ein Satz höher sein als sein Text — Rundung.
SLACK = 1


def _needed(label: QLabel) -> int:
    """Was der Text in der Breite des Satzes braucht, ohne gepinnte Höhen."""
    least, most = label.minimumHeight(), label.maximumHeight()
    label.setMinimumHeight(0)
    label.setMaximumHeight(16_777_215)
    try:
        return max(label.heightForWidth(label.width()), 0)
    finally:
        label.setMinimumHeight(least)
        label.setMaximumHeight(most)


def _settle(qt_app: QApplication) -> None:
    end = time.monotonic() + 1.0
    while time.monotonic() < end:
        qt_app.processEvents()
        time.sleep(0.005)


@pytest.mark.parametrize("language", available_languages())
def test_the_empty_sentences_of_a_new_project_hold_no_spare_line(
    qt_app: QApplication, language: str
) -> None:
    spoken = get_language()
    install_language(language)
    set_language(language)
    try:
        with bundled_font(qt_app, 9):
            apply_theme(qt_app, "light")
            apply_style(qt_app, "light")
            window = MainWindow(Session(), UiSettings())
            try:
                window.show()
                window.resize(1920, 1032)
                window._show_start_screen(False)
                _settle(qt_app)
                found = []
                for label in (window.object_tree._empty, window.history_panel._empty):
                    assert label.isVisible(), label.text()
                    spare = label.height() - _needed(label)
                    if abs(spare) > SLACK:
                        found.append(
                            f"{label.text()[:40]!r}: {label.height()} hoch bei "
                            f"{label.width()} breit, der Text braucht {_needed(label)}"
                        )
                assert not found, found
            finally:
                window.close()
                window.deleteLater()
                qt_app.processEvents()
    finally:
        apply_style(qt_app, "light")
        install_language(spoken)
        set_language(spoken)
