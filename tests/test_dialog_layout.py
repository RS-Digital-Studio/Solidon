"""Lange Dialoge bleiben erreichbar, ohne kurze Formulare zu verkleinern."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.style import DialogScrollArea, fit_dialog_to_screen


def _settle(application: QApplication) -> None:
    for _ in range(12):
        application.processEvents()


def test_chat_setup_follows_late_status_text_without_growing_paragraph_gaps(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ui.dialogs import KeyDialog
    from app.ui.settings import UiSettings

    monkeypatch.setattr(KeyDialog, "look", lambda _self: None)
    dialog = KeyDialog(settings=UiSettings())
    try:
        dialog.show()
        _settle(qt_app)
        original = dialog.explanation.text()
        compact = dialog.height()
        compact_scroll = dialog._scroll.verticalScrollBar().maximum()
        # Eine späte Statuszeile ist eine passive Änderung: Der Rahmen wächst nur
        # um Inhalt, der sonst verdeckt läge, und gibt danach nichts zurück,
        # damit er bei wechselndem Status nicht springt (RM-487, ``fenster.md``
        # Dialoggröße nach Auslöser). Was der Bildschirm nicht fasst, rollt.
        dialog.explanation.setText(original + "\n" + "Status\n" * 5)
        _settle(qt_app)
        assert dialog.height() >= compact
        explanation = dialog.explanation
        assert dialog._scroll.verticalScrollBar().maximum() > compact_scroll or (
            explanation.height() >= explanation.heightForWidth(explanation.width())
        ), "sie steht ganz da oder rollt"
        grown = dialog.height()
        dialog.explanation.setText(original)
        _settle(qt_app)
        assert dialog.height() == grown, "zurückgegeben wird nichts"
    finally:
        dialog.close()
        dialog.release()


def test_a_long_dialog_scrolls_its_content_but_keeps_the_buttons(qt_app: QApplication) -> None:
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    content = QWidget()
    fields = QVBoxLayout(content)
    for index in range(40):
        fields.addWidget(QLabel(str(index)))
    scroll = DialogScrollArea(dialog)
    scroll.setWidget(content)
    layout.addWidget(scroll)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
    layout.addWidget(buttons)
    dialog.resize(420, 300)
    try:
        dialog.show()
        _settle(qt_app)
        assert dialog.height() <= 300
        assert scroll.verticalScrollBar().maximum() > 0
        assert dialog.rect().contains(buttons.geometry())
        assert scroll.sizeHint().height() >= content.sizeHint().height()
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        _settle(qt_app)
        last = fields.itemAt(fields.count() - 1).widget()
        assert last is not None
        assert (
            scroll.viewport().rect().contains(last.mapTo(scroll.viewport(), last.rect().center()))
        )
    finally:
        dialog.close()


@pytest.mark.parametrize("oversized", [False, True])
def test_a_dialog_keeps_its_frame_on_the_current_screen(
    qt_app: QApplication, oversized: bool
) -> None:
    dialog = QDialog()
    dialog.setWindowFlags(Qt.WindowType.Dialog)
    dialog.resize(320, 240)
    try:
        dialog.show()
        _settle(qt_app)
        room = dialog.screen().availableGeometry()
        if oversized:
            dialog.resize(room.width() + 200, room.height() + 200)
        dialog.move(room.right() - 100, room.bottom() - 100)
        _settle(qt_app)
        fit_dialog_to_screen(dialog)
        _settle(qt_app)
        assert dialog.screen().availableGeometry().contains(dialog.frameGeometry())
        if not oversized:
            assert dialog.width() == 320
            assert dialog.height() == 240
        settled = dialog.geometry()
        fit_dialog_to_screen(dialog)
        _settle(qt_app)
        assert dialog.geometry() == settled
    finally:
        dialog.close()
