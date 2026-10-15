"""Ruhige Hauptwerkzeugleisten, sichtbare Zustände und unveränderte Kartenknöpfe."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyleOptionToolButton,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.style import active_fill, apply_style, make_primary
from app.ui.theme import THEMES, Theme, apply_theme
from app.ui.tool_strip import ToolStrip


def _paint(button: QToolButton, state: QStyle.StateFlag, ground: str) -> QImage:
    """Den echten Qt-Stil mit ausdrücklich gesetztem Interaktionszustand zeichnen."""
    button.ensurePolished()
    option = QStyleOptionToolButton()
    button.initStyleOption(option)
    option.state = state | QStyle.StateFlag.State_Active
    image = QImage(button.size(), QImage.Format.Format_ARGB32)
    image.fill(QColor(ground))
    painter = QPainter(image)
    try:
        button.style().drawComplexControl(
            QStyle.ComplexControl.CC_ToolButton, option, painter, button
        )
    finally:
        painter.end()
    return image


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("place", ["top", "bottom"])
def test_only_resting_toolbar_buttons_lose_their_outline(
    qt_app: QApplication, theme: Theme, place: str
) -> None:
    apply_theme(qt_app, theme)
    apply_style(qt_app, theme)
    host = QWidget()
    layout = QVBoxLayout(host)
    if place == "top":
        bar = QToolBar(host)
        bar.setObjectName("mainTools")
        action = QAction("Schichten", bar)
        action.setCheckable(True)
        bar.addAction(action)
        button = bar.widgetForAction(action)
    else:
        bar = ToolStrip(host)
        bar.setObjectName("mainToolStrip")
        bar.add("layers", "Schichten", QWidget())
        button = bar.findChild(QToolButton)
    assert isinstance(button, QToolButton)
    layout.addWidget(bar)
    host.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    host.show()
    qt_app.processEvents()
    button.resize(button.sizeHint().expandedTo(QSize(140, 36)))
    colours = THEMES[theme]
    enabled = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Raised
    try:
        size = button.sizeHint()
        rest = _paint(button, enabled, colours["window"])
        middle = rest.height() // 2
        assert rest.pixelColor(0, middle).name() == colours["window"]

        hover = _paint(button, enabled | QStyle.StateFlag.State_MouseOver, colours["window"])
        assert hover.pixelColor(0, middle).name() == colours["line"]
        assert hover.pixelColor(5, 5).name() == colours["alternate"]

        focus = _paint(button, enabled | QStyle.StateFlag.State_HasFocus, colours["window"])
        assert focus.pixelColor(0, middle).name() == colours["accent_line"]

        checked = _paint(button, enabled | QStyle.StateFlag.State_On, colours["window"])
        assert checked.pixelColor(0, middle).name() == colours["accent_line"]
        assert checked.pixelColor(5, 5).name() == active_fill(theme)
        checked_hover = _paint(
            button,
            enabled | QStyle.StateFlag.State_On | QStyle.StateFlag.State_MouseOver,
            colours["window"],
        )
        assert checked_hover.pixelColor(0, middle).name() == colours["accent_line"]
        assert checked_hover.pixelColor(5, 5) != checked.pixelColor(5, 5)

        pressed = _paint(button, enabled | QStyle.StateFlag.State_Sunken, colours["window"])
        assert pressed.pixelColor(0, middle).name() == colours["line"]

        button.setEnabled(False)
        disabled = _paint(button, QStyle.StateFlag.State_None, colours["window"])
        assert disabled.pixelColor(0, middle).name() == colours["window"]
        assert disabled != rest, "Gesperrte Beschriftung bleibt vom aktiven Text unterscheidbar"
        assert button.sizeHint() == size, (
            "Der ruhige Zustand darf die Trefferfläche nicht verkleinern"
        )
    finally:
        host.close()
        host.deleteLater()
        apply_theme(qt_app, "dark")
        apply_style(qt_app, "dark")


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_tool_cards_fields_and_primary_actions_keep_their_boundaries(
    qt_app: QApplication, theme: Theme
) -> None:
    apply_theme(qt_app, theme)
    apply_style(qt_app, theme)
    strip = ToolStrip()
    strip.setObjectName("mainToolStrip")
    card = QWidget()
    layout = QVBoxLayout(card)
    mode = QToolButton(card)
    mode.setText("Verschieben")
    field = QLineEdit("12,00 mm", card)
    primary = make_primary(QPushButton("Übernehmen", card))
    search = QPushButton("Funktion suchen …", card)
    search.setObjectName("functionSearch")
    for widget in (mode, field, primary, search):
        layout.addWidget(widget)
    strip.add("move", "Bewegen", card)
    strip.activate("move")
    strip.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    strip.show()
    qt_app.processEvents()
    colours = THEMES[theme]
    try:
        mode.resize(mode.sizeHint().expandedTo(QSize(140, 36)))
        image = _paint(mode, QStyle.StateFlag.State_Enabled, colours["window"])
        assert image.pixelColor(0, image.height() // 2).name() == colours["line"]
        field.clearFocus()
        for widget in (field, search):
            picture = widget.grab().toImage()
            assert picture.pixelColor(0, picture.height() // 2).name() == colours["line"]
        primary.clearFocus()
        picture = primary.grab().toImage()
        assert picture.pixelColor(5, 5).name() == colours["highlight"]
        # Der vorhandene Umschalter bleibt der sichtbare Rückweg aus der Karte.
        toggle = strip.findChildren(QToolButton, options=Qt.FindChildOption.FindDirectChildrenOnly)[
            0
        ]
        toggle.click()
        assert strip.active() is None
        assert card.isHidden()
    finally:
        strip.close()
        strip.deleteLater()
        apply_theme(qt_app, "dark")
        apply_style(qt_app, "dark")


def test_main_window_marks_exactly_its_two_toolbars(qt_app: QApplication) -> None:
    from app.core.bootstrap import load_operations
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    load_operations()
    window = MainWindow(Session(), UiSettings())
    try:
        assert window.toolbar.objectName() == "mainTools"
        assert window.tools.objectName() == "mainToolStrip"
        assert window.findChildren(QWidget, "mainTools") == [window.toolbar]
        assert window.findChildren(QWidget, "mainToolStrip") == [window.tools]
        assert window.function_search.objectName() == "functionSearch"
    finally:
        window.close()
        window.release()
