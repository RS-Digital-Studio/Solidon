"""Ein Wechsel der Anwendungsschrift erreicht Stil, Knöpfe und offene Dialoge sofort (FD-194).

Qt setzt bei einem Wechsel der Systemschrift die neue Schrift der Anwendung und
schickt ``ApplicationFontChange``. Das Stylesheet trägt die Schriftgrößen aber
fest (``style.stylesheet``) und wurde nur beim Themenwechsel neu gesetzt: Nach
9 → 14 pt blieben Titel, Abschnitt und Knöpfe bei der alten Größe, bis Solidon
neu startete. Geprüft wird ohne ``apply_style`` nach dem Wechsel — genau das
fehlt bei einer Systemänderung.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.ui.op_dialog import OperationDialog
from app.ui.style import apply_style, set_level
from app.ui.theme import apply_theme
from tests.bundled_fonts import bundled_font


def _rounds(qt_app: QApplication, count: int = 30) -> None:
    for _ in range(count):
        qt_app.processEvents()
        time.sleep(0.005)


def _sizes(heading: QLabel, section: QLabel) -> tuple[float, float]:
    return heading.font().pointSizeF(), section.font().pointSizeF()


@pytest.fixture
def surface(qt_app: QApplication) -> Iterator[tuple[QWidget, QLabel, QLabel, QPushButton]]:
    holder = QWidget()
    column = QVBoxLayout(holder)
    heading = QLabel("Titel", holder)
    set_level(heading, "title")
    section = QLabel("Abschnitt", holder)
    set_level(section, "section")
    button = QPushButton("Übernehmen", holder)
    for widget in (heading, section, button):
        column.addWidget(widget)
    yield holder, heading, section, button
    holder.hide()
    holder.deleteLater()


def test_a_font_change_reaches_the_style_without_a_restart(
    qt_app: QApplication, surface: tuple[QWidget, QLabel, QLabel, QPushButton]
) -> None:
    holder, heading, section, button = surface
    with bundled_font(qt_app, 14) as font:
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        holder.show()
        _rounds(qt_app)
        at_14 = _sizes(heading, section)
        font.setPointSize(9)
        qt_app.setFont(font)
        apply_style(qt_app, "light")
        _rounds(qt_app)
        at_9 = _sizes(heading, section)
        assert at_9 != at_14, "Voraussetzung: die Stufen hängen an der Schrift"

        # Der Wechsel, wie das System ihn schickt — ohne ``apply_style``.
        font.setPointSize(14)
        qt_app.setFont(font)
        _rounds(qt_app)
        assert _sizes(heading, section) == at_14, "größer, ohne Neustart"
        assert button.font().pointSizeF() == 14, "der Knopf trägt die neue Schrift"
        assert button.minimumHeight() >= button.sizeHint().height(), "der Knopf folgt"

        font.setPointSize(9)
        qt_app.setFont(font)
        _rounds(qt_app)
        assert _sizes(heading, section) == at_9, "und wieder zurück"
        assert button.font().pointSizeF() == 9
    apply_style(qt_app, "light")


def test_an_open_operation_dialog_follows_the_font(qt_app: QApplication) -> None:
    """Ein offener Dialog übernimmt die Schrift, und sein Knopf bleibt im Fenster."""
    load_operations()
    with bundled_font(qt_app, 9) as font:
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        dialog = OperationDialog(REGISTRY.get("create_box"), {})
        dialog.show()
        try:
            _rounds(qt_app)
            before = dialog._accept_button.font().pointSizeF()
            font.setPointSize(14)
            qt_app.setFont(font)
            _rounds(qt_app, 60)
            button = dialog._accept_button
            assert button.font().pointSizeF() > before
            assert dialog.rect().contains(QRect(button.mapTo(dialog, QPoint()), button.size()))
            assert button.height() >= button.sizeHint().height()
        finally:
            dialog.close()
            dialog.deleteLater()
    previous = QFont(qt_app.font())
    qt_app.setFont(previous)
    apply_style(qt_app, "light")
