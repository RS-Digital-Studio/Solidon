"""Kurze Dialoginhalte reservieren keine leere Mindesthöhe (FD51)."""

import pytest
from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.registry import REGISTRY
from app.core.sketch.planes import frame_for_sketch
from app.i18n import set_language
from app.i18n.catalog import available_languages, install_language
from app.ui.op_dialog import OperationDialog
from app.ui.style import NORMAL, TARGET_SIZE, DialogScrollArea, apply_style
from app.ui.theme import apply_theme


def _settle(application: QApplication) -> None:
    for _ in range(16):
        application.processEvents()


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("points", [11, 18])
def test_rename_uses_the_height_of_its_short_form(
    qt_app: QApplication, language: str, points: int
) -> None:
    """Text und Feld bestimmen den Platz; längere Übersetzungen dürfen mehr brauchen."""
    load_operations()
    install_language(language)
    set_language(language)
    apply_theme(qt_app, "light")
    previous_font = QFont(qt_app.font())
    font = QFont(previous_font)
    font.setPointSize(points)
    qt_app.setFont(font)
    apply_style(qt_app, "light")
    dialog = OperationDialog(REGISTRY.get("rename_object"), {"body": "Körper"})
    try:
        dialog.show()
        _settle(qt_app)
        scroll = dialog._scroll
        content = scroll.widget()
        assert content.font().pointSizeF() == pytest.approx(points)
        name = dialog.findChild(QLineEdit)
        assert name is not None
        assert name.font().pointSizeF() == pytest.approx(points)
        layout = content.layout()
        natural = layout.totalHeightForWidth(scroll.viewport().width())
        assert scroll.viewport().height() <= natural + NORMAL
        assert scroll.verticalScrollBar().maximum() == 0
        assert dialog.rect().contains(
            QRect(dialog._accept_button.mapTo(dialog, QPoint()), dialog._accept_button.size())
        )
        dialog.resize(dialog.width() + 30, dialog.height() + 20)
        _settle(qt_app)
        chosen = dialog.size()
        dialog.show_refusal("Hinweis\n" * 8)
        _settle(qt_app)
        assert dialog.size() == chosen
        assert scroll.verticalScrollBar().maximum() > 0
    finally:
        dialog.close()
        dialog.deleteLater()
        qt_app.setFont(previous_font)
        apply_style(qt_app, "light")


def test_a_scroll_floor_follows_text_and_font_but_stays_bounded_for_long_content(
    qt_app: QApplication,
) -> None:
    """Das Minimum wächst mit dem Inhalt; lange Formulare behalten ihre niedrige Grenze."""
    apply_theme(qt_app, "light")
    dialog = QDialog()
    outer = QVBoxLayout(dialog)
    scroll = DialogScrollArea(dialog)
    content = QWidget()
    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel("Eine Zeile")
    label.setWordWrap(True)
    layout.addWidget(label)
    layout.addStretch()
    scroll.setWidget(content)
    outer.addWidget(scroll)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    outer.addWidget(buttons)
    try:
        dialog.show()
        _settle(qt_app)
        small = scroll.minimumSizeHint().height()
        assert 0 < small < TARGET_SIZE * 2
        font = QFont(label.font())
        font.setPointSizeF(font.pointSizeF() * 2)
        label.setFont(font)
        _settle(qt_app)
        assert scroll.minimumSizeHint().height() > small
        label.setText("Eine lange Inhaltszeile\n" * 50)
        dialog.resize(380, 240)
        _settle(qt_app)
        assert scroll.minimumSizeHint().height() == TARGET_SIZE * 2
        assert scroll.minimumSizeHint().width() == TARGET_SIZE * 2
        assert scroll.verticalScrollBar().maximum() > 0
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        _settle(qt_app)
        assert (
            label.mapTo(scroll.viewport(), QPoint(0, label.height() - 1)).y()
            < scroll.viewport().height()
        )
        assert dialog.rect().contains(buttons.geometry())
        label.setText("Kurz")
        _settle(qt_app)
        assert scroll.minimumSizeHint().height() < TARGET_SIZE * 2
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize("language", available_languages())
@pytest.mark.parametrize("manual", [False, True])
def test_a_short_dialog_keeps_its_chosen_height_when_the_footer_font_changes(
    qt_app: QApplication, language: str, manual: bool
) -> None:
    """DG-04: Der Rollausschnitt gibt der größeren Knopfzeile Platz im gewählten Rahmen."""
    load_operations()
    install_language(language)
    set_language(language)
    apply_theme(qt_app, "light")
    previous_font = QFont(qt_app.font())
    font = QFont(previous_font)
    font.setPointSize(11)
    qt_app.setFont(font)
    apply_style(qt_app, "light")
    dialog = OperationDialog(REGISTRY.get("rename_object"), {"body": "Körper"})
    try:
        dialog.show()
        _settle(qt_app)
        assert dialog._height.initial_fit_done
        if manual:
            dialog.resize(dialog.width(), 136)
            _settle(qt_app)
            assert dialog.height() == 136
        chosen = dialog.size()
        with pytest.raises(ValidationError) as caught:
            frame_for_sketch("through:0,0,20;10,0,20;20,0,20")
        dialog.show_refusal(caught.value)
        _settle(qt_app)
        scroll = dialog._scroll
        label = dialog._refusal.label
        initial_viewport = scroll.viewport().height()
        initial_button = dialog._accept_button.height()
        before_font_change = dialog.size()
        retained_height = chosen.height()
        for points in (11, 18, 11):
            font.setPointSize(points)
            qt_app.setFont(font)
            apply_style(qt_app, "light")
            _settle(qt_app)
            assert label.font().pointSizeF() == pytest.approx(points)
            assert dialog._accept_button.font().pointSizeF() == pytest.approx(points)
            if manual:
                buttons = dialog.findChild(QDialogButtonBox)
                assert buttons is not None
                layout = dialog.layout()
                assert layout is not None
                margins = layout.contentsMargins()
                # Nur wenn die vollständigen äußeren Knöpfe selbst nicht mehr
                # passen, gilt ihre physische Mindesthöhe. Der ursprüngliche
                # 136-Pixel-Fall mit passenden Knöpfen bleibt unverändert.
                retained_height = max(
                    retained_height,
                    buttons.sizeHint().height()
                    + margins.top()
                    + margins.bottom()
                    + layout.spacing()
                    + scroll.widget().fontMetrics().lineSpacing(),
                )
                assert dialog.width() == chosen.width()
                assert dialog.height() == retained_height
                assert dialog._height.user == dialog.size()
                assert scroll.viewport().height() >= scroll.widget().fontMetrics().lineSpacing()
                if points == 18:
                    assert dialog._accept_button.height() > initial_button
                    assert scroll.viewport().height() < initial_viewport
            elif points == 18:
                assert dialog.height() > before_font_change.height()
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            _settle(qt_app)
            assert (
                scroll.viewport()
                .rect()
                .contains(label.mapTo(scroll.viewport(), QPoint(0, label.height() - 1)))
            )
            buttons = dialog.findChild(QDialogButtonBox)
            assert buttons is not None
            for button in buttons.buttons():
                assert button.isVisible()
                assert dialog.rect().contains(QRect(button.mapTo(dialog, QPoint()), button.size()))
        before_removal = dialog.size()
        dialog.show_refusal(None)
        _settle(qt_app)
        assert dialog.size() == before_removal
    finally:
        dialog.close()
        dialog.deleteLater()
        qt_app.setFont(previous_font)
        apply_style(qt_app, "light")
