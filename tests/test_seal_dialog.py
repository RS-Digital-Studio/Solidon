"""Sichtbare Dichtwegauswahl statt technischer Daten im Operationsdialog."""

import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit, QPushButton

from app.core.geom.seal import opening_choices
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_to_text
from app.core.types import FeatureRef
from app.ui.seal_dialog import SealPathDialog, SealPathField, selection_status
from tests.test_outline_dialog import _until
from tests.test_seal_openings import plate


def test_field_never_shows_signature_as_text_input(qt_app):
    entry = plate()
    selected = opening_choices(entry, FeatureRef(entry.id, "top"))[0]
    field = SealPathField()
    field.set_selection(
        {
            "path_sketch": "",
            "support_feature": "plate:top",
            "opening_signature": selected.signature,
            "counterface": "",
        }
    )
    assert field.valid
    assert not field.findChildren(QLineEdit)
    assert "Öffnung" in field.summary.text()
    assert field.value() == selected.signature
    field.set_selection(
        {
            "path_sketch": "",
            "support_feature": "plate:top",
            "opening_signature": "",
            "counterface": "",
        }
    )
    assert not field.valid
    field.close()


def test_two_similar_openings_need_explicit_visible_choice(qt_app):
    entry = plate()
    dialog = SealPathDialog(entry, [entry], {"support_feature": "plate:top"})
    dialog.show()
    try:
        _until(qt_app, lambda: dialog.contours.count() == 2)
        assert not dialog.accept_button.isEnabled()
        dialog.contours.setCurrentRow(1)
        _until(qt_app, dialog.accept_button.isEnabled)
        selected = dialog.values()
        assert set(selected) == {
            "path_sketch",
            "support_feature",
            "opening_signature",
            "counterface",
        }
        assert selected["opening_signature"]
        assert "Kontur 2" in dialog.status.text()
        assert dialog.contour_view.scene().selectedItems()
        QTest.mouseClick(dialog.accept_button, Qt.MouseButton.LeftButton)
        assert dialog.result() == dialog.DialogCode.Accepted
    finally:
        dialog.release()
        dialog.close()
        dialog.deleteLater()
        qt_app.processEvents()


def test_picture_click_keyboard_and_stored_selection_have_one_identity(qt_app):
    entry = plate()
    selected = opening_choices(entry, FeatureRef(entry.id, "top"))[1]
    dialog = SealPathDialog(
        entry, [entry], {"support_feature": "plate:top", "opening_signature": selected.signature}
    )
    dialog.show()
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        assert dialog.contours.currentRow() == 1
        point = dialog.contour_view.mapFromScene(dialog._items[0].path().boundingRect().center())
        QTest.mouseClick(dialog.contour_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        assert dialog.contours.currentRow() == 0
        assert "Kontur 1" in dialog.status.text()
        dialog.contours.setFocus()
        QTest.keyClick(dialog.contours, Qt.Key.Key_Down)
        assert dialog.values()["opening_signature"] == selected.signature
        assert dialog._items[1].isSelected()
    finally:
        dialog.release()
        dialog.close()
        dialog.deleteLater()
        qt_app.processEvents()


def test_unreadable_signature_offers_real_contours_for_recovery(qt_app):
    entry = plate()
    dialog = SealPathDialog(
        entry, [entry], {"support_feature": "plate:top", "opening_signature": "broken"}
    )
    try:
        _until(qt_app, lambda: dialog.contours.count() == 2)
        assert not dialog.accept_button.isEnabled()
        dialog.contours.setCurrentRow(0)
        assert dialog.accept_button.isEnabled()
        assert selection_status(dialog.values())[0]
    finally:
        dialog.release()
        dialog.close()
        dialog.deleteLater()
        qt_app.processEvents()


def test_analysis_is_off_thread_and_late_results_cannot_accept_after_cancel(qt_app, monkeypatch):
    from app.ui import seal_dialog

    entry = plate()
    entered, resume = threading.Event(), threading.Event()
    calls = []
    original = seal_dialog.opening_choices

    def delayed(*args, **kwargs):
        calls.append(threading.get_ident())
        entered.set()
        assert resume.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(seal_dialog, "opening_choices", delayed)
    dialog = SealPathDialog(entry, [entry], {"support_feature": "plate:top"})
    try:
        _until(qt_app, entered.is_set)
        assert calls == [calls[0]] and calls[0] != threading.get_ident()
        dialog.reject()
        resume.set()
        dialog.release()
        qt_app.processEvents()
        assert dialog.result() == dialog.DialogCode.Rejected
        assert not dialog.accept_button.isEnabled()
        assert not dialog.values()["opening_signature"]
    finally:
        resume.set()
        dialog.release()
        dialog.close()
        dialog.deleteLater()
        qt_app.processEvents()


def test_drawing_uses_the_existing_editor_and_returns_only_selection_values(qt_app):
    entry = plate()
    drawing = sketch_to_text(shapes.circle(10))
    dialog = SealPathDialog(entry, [entry], {"path_sketch": drawing, "groove_depth": "=@depth"})
    visited = []
    try:
        _until(qt_app, dialog.accept_button.isEnabled)

        def finish_editor():
            editor = qt_app.activeModalWidget()
            visited.append(editor.windowTitle())
            button = next(
                button
                for button in editor.findChildren(QPushButton)
                if button.text() == "Übernehmen"
            )
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)

        QTimer.singleShot(0, finish_editor)
        QTest.mouseClick(dialog.sketch_button, Qt.MouseButton.LeftButton)
        _until(qt_app, dialog.accept_button.isEnabled)
        assert visited == ["Skizze zeichnen"]
        assert dialog.values()["path_sketch"] == drawing
        assert dialog.values()["support_feature"] == ""
        assert dialog.values()["opening_signature"] == ""
        assert "groove_depth" not in dialog.values()
    finally:
        dialog.release()
        dialog.close()
        dialog.deleteLater()
        qt_app.processEvents()


def test_empty_and_malformed_drawing_are_not_a_complete_field_selection():
    assert not selection_status({})[0]
    assert not selection_status({"path_sketch": "broken"})[0]
    assert not selection_status(
        {"path_sketch": sketch_to_text(shapes.circle(10)), "support_feature": "plate:top"}
    )[0]


def test_path_choice_focus_keeps_the_outer_apply_button_primary(qt_app):
    from PySide6.QtWidgets import QDialog, QVBoxLayout

    from app.ui.style import make_primary

    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    field = SealPathField(parent=dialog)
    apply = make_primary(QPushButton("Übernehmen", dialog))
    layout.addWidget(field)
    layout.addWidget(apply)
    dialog.show()
    try:
        field.button.setFocus()
        qt_app.processEvents()
        assert apply.isDefault()
        assert not field.button.isDefault()
        assert not field.button.autoDefault()
    finally:
        dialog.close()
        dialog.deleteLater()
        qt_app.processEvents()
