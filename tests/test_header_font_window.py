"""Die Kopfzeile folgt einem Schriftwechsel wie ein frisch geöffnetes Fenster (L1, FD-194).

Die Kopfzeile maß den Knopf *Filamente* in beiden Formen nur beim Bau. Nach
9 → 14 pt rechnete sie mit der alten Breite, nahm dem Knopf zu wenig Platz ab
und kürzte Projektname, Maße und Drucker, die ein frisch bei 14 pt geöffnetes
Fenster ganz zeigt (Review 2 Restpaket A, L1). Geprüft ohne ``apply_style``
nach dem Wechsel — so kommt eine Systemänderung an.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.scene.project import save
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.style import apply_style
from app.ui.theme import apply_theme
from tests.bundled_fonts import bundled_font
from tools import function_scenes


def _rounds(qt_app: QApplication, count: int = 60) -> None:
    for _ in range(count):
        qt_app.processEvents()
        time.sleep(0.005)


def _opened(qt_app: QApplication, path: Path, width: int) -> MainWindow:
    window = MainWindow(Session(), UiSettings())
    window.resize(width, 1080)
    window.show()
    window._show_start_screen(False)
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    _rounds(qt_app)
    return window


def _closed(qt_app: QApplication, window: MainWindow) -> None:
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def _header(window: MainWindow) -> dict[str, tuple[str, str, int]]:
    """Gezeigter und voller Text jeder Angabe, dazu ihre Mindestbreite.

    Die Mindestbreite hält das geschützte Ende; nach dem Wechsel muss sie die
    der neuen Schrift sein, sonst kürzt ein schmaleres Fenster falsch (L1).
    """
    header = window.header
    return {
        name: (
            getattr(header, name).text(),
            getattr(header, name).full_text(),
            getattr(header, name).minimumWidth(),
        )
        for name in ("title", "bounds", "printer")
    }


def _button_widths(window: MainWindow) -> tuple[list[int], list[int]]:
    """Die gemerkten Breiten des Knopfs *Filamente* (Zeichen, Wort) und die echten."""
    header = window.header
    button = header.filament_button
    style = button.toolButtonStyle()
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    sign = button.sizeHint().width()
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    words = button.sizeHint().width()
    button.setToolButtonStyle(style)
    return [header._filament_sign, header._filament_words], [sign, words]


@pytest.mark.parametrize("width", (1366, 1920))
def test_the_header_after_a_font_change_matches_a_fresh_window(
    qt_app: QApplication, tmp_path: Path, width: int
) -> None:
    path = tmp_path / "bohrung.p3d"
    save(function_scenes.build_scene("erkannte_bohrung.netz"), path)
    with bundled_font(qt_app, 14) as font:
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        fresh = _opened(qt_app, path, width)
        try:
            wanted = _header(fresh)
            wanted_style = fresh.header.filament_button.toolButtonStyle()
            assert all(shown == full for shown, full, _least in wanted.values()), (
                "Voraussetzung: frisch bei 14 pt steht alles ganz",
                wanted,
            )
        finally:
            _closed(qt_app, fresh)

        font.setPointSize(9)
        qt_app.setFont(font)
        apply_style(qt_app, "light")
        changed = _opened(qt_app, path, width)
        try:
            # Der Wechsel, wie das System ihn schickt — ohne ``apply_style``.
            font.setPointSize(14)
            qt_app.setFont(font)
            _rounds(qt_app, 80)
            assert _header(changed) == wanted, (_header(changed), wanted)
            assert changed.header.filament_button.toolButtonStyle() == wanted_style
            # Die Breiten, mit denen die Zeile rechnet, sind die der neuen Schrift
            # (Nachprüfung, L1: gemerkt 107 statt 147).
            remembered, real = _button_widths(changed)
            assert remembered == real, (remembered, real)
        finally:
            _closed(qt_app, changed)
    apply_style(qt_app, "light")
