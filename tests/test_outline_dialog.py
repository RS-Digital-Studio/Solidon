"""Konturbild, Tastatur und bestätigte Extrusion verwenden dieselbe Auswahl."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton

from app.core.ingest import outline
from app.ui.outline_dialog import ContourField, OutlineDialog
from tests.test_outline_profiles import SOURCE


def _until(app: QApplication, condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 10
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        # QTest.qWait hält hier den GIL; der kalte SciPy-Import im Arbeiter
        # käme zwischen den kurzen Python-Takten sonst nicht weiter.
        time.sleep(0.01)
    assert condition(), "dialog did not reach the expected state"


def _dispose(dialog: OutlineDialog, app: QApplication) -> None:
    dialog.release()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_image_keyboard_and_real_result_share_selected_profiles(qt_app: QApplication) -> None:
    dialog = OutlineDialog(SOURCE, ".svg")
    dialog.show()
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        assert dialog.profiles.count() == 2
        assert dialog.result_preview.mesh.volume == pytest.approx((140 + 48) * 3)
        QTest.mouseClick(dialog.select_none, Qt.MouseButton.LeftButton)
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert json.loads(dialog.values()["contours"]) == []
        dialog.profiles.setCurrentRow(0)
        dialog.profiles.setFocus()
        QTest.keyClick(dialog.profiles, Qt.Key.Key_Space)
        _until(qt_app, dialog.accept_button.isEnabled)
        chosen = json.loads(dialog.values()["contours"])
        assert len(chosen) == 1
        assert dialog.result_preview.mesh.is_watertight
        original = dialog.result_preview.mesh.volume
        dialog._fields["height"].set_value_mm(6)
        assert not dialog.accept_button.isEnabled()
        _until(qt_app, dialog.accept_button.isEnabled)
        assert dialog.result_preview.mesh.volume == pytest.approx(original * 2)
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        _dispose(dialog, qt_app)


def test_click_in_outline_picture_toggles_its_profile(qt_app: QApplication) -> None:
    dialog = OutlineDialog(SOURCE, ".svg")
    dialog.show()
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        entry = dialog._profiles[0]
        point = dialog.contour_view.mapFromScene(entry.label_at)
        QTest.mouseClick(dialog.contour_view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        _until(qt_app, dialog.accept_button.isEnabled)
        assert entry.profile.id not in json.loads(dialog.values()["contours"])
        assert len(json.loads(dialog.values()["contours"])) == 1
    finally:
        _dispose(dialog, qt_app)


def test_saved_choice_and_unknown_choice_are_not_replaced(qt_app: QApplication) -> None:
    profiles = outline.read_profiles(SOURCE, ".svg")
    chosen = profiles[1].id
    for identifiers in ([chosen], ["removed"]):
        dialog = OutlineDialog(
            SOURCE,
            ".svg",
            values={
                "contours": json.dumps(identifiers),
                "height": 7,
                "width": 32,
            },
        )
        try:
            _until(qt_app, lambda current=dialog: current.profiles.count() == 2)
            assert json.loads(dialog.values()["contours"]) == (
                identifiers if identifiers == [chosen] else []
            )
            if identifiers == [chosen]:
                _until(qt_app, dialog.accept_button.isEnabled)
                assert dialog.result_preview.mesh.bounds.size[0] == pytest.approx(32)
                assert dialog.result_preview.mesh.bounds.size[2] == pytest.approx(7)
            else:
                assert not dialog.accept_button.isEnabled()
        finally:
            _dispose(dialog, qt_app)


def test_profile_work_and_projection_run_outside_main_thread(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.ui.outline_dialog as module

    main_thread = threading.get_ident()
    calls: list[tuple[str, int]] = []
    read, project = outline.read_profiles, module.drawing.project

    def reading(*args: object, **kwargs: object) -> object:
        calls.append(("read", threading.get_ident()))
        return read(*args, **kwargs)

    def projecting(*args: object, **kwargs: object) -> object:
        calls.append(("project", threading.get_ident()))
        return project(*args, **kwargs)

    monkeypatch.setattr(outline, "read_profiles", reading)
    monkeypatch.setattr(module.drawing, "project", projecting)
    dialog = OutlineDialog(SOURCE, ".svg")
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        assert {name for name, _ in calls} == {"read", "project"}
        assert all(identifier != main_thread for _, identifier in calls)
    finally:
        _dispose(dialog, qt_app)


def test_cancel_during_read_discards_late_result(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = threading.Event()
    entered = threading.Event()
    read = outline.read_profiles

    def slow_read(*args: object, **kwargs: object) -> object:
        entered.set()
        gate.wait(5)
        return read(*args, **kwargs)

    monkeypatch.setattr(outline, "read_profiles", slow_read)
    dialog = OutlineDialog(SOURCE, ".svg")
    try:
        _until(qt_app, entered.is_set)
        dialog.reject()
        gate.set()
        dialog.release()
        qt_app.processEvents()
        assert dialog.profiles.count() == 0
        assert dialog.result_preview is None
        assert not dialog.accept_button.isEnabled()
    finally:
        gate.set()
        _dispose(dialog, qt_app)


def test_invalid_profile_stays_visible_with_reason(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reason = "Diese Kontur ist zu dünn oder flächenlos. Wählen Sie eine andere Kontur."
    original = outline.profile_reason

    def checked(entry: outline.OutlineProfile) -> str:
        return reason if entry.polygon.interiors else original(entry)

    monkeypatch.setattr(outline, "profile_reason", checked)
    dialog = OutlineDialog(SOURCE, ".svg")
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        assert dialog.profiles.count() == 2
        row = next(index for index, entry in enumerate(dialog._profiles) if entry.reason)
        item = dialog.profiles.item(row)
        assert "Nicht extrudierbar" in item.text()
        assert not item.flags() & Qt.ItemFlag.ItemIsUserCheckable
        dialog.profiles.setCurrentRow(row)
        assert dialog.detail.text() == reason
        assert len(json.loads(dialog.values()["contours"])) == 1
    finally:
        _dispose(dialog, qt_app)


def test_old_preview_cannot_overwrite_new_values_or_enable_acceptance(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered, gate = threading.Event(), threading.Event()
    calculate = outline.extrude_profiles
    heights: list[float] = []

    def delayed(profiles: object, height: float, *args: object, **kwargs: object) -> object:
        heights.append(height)
        if len(heights) == 1:
            entered.set()
            gate.wait(5)
        return calculate(profiles, height, *args, **kwargs)

    monkeypatch.setattr(outline, "extrude_profiles", delayed)
    dialog = OutlineDialog(SOURCE, ".svg")
    try:
        _until(qt_app, entered.is_set)
        dialog._fields["height"].set_value_mm(5)
        dialog._fields["height"].set_value_mm(8)
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        gate.set()
        _until(qt_app, dialog.accept_button.isEnabled)
        assert heights == [3, 8]
        assert dialog.result_preview.mesh.bounds.size[2] == pytest.approx(8)
        assert dialog._ready_revision == dialog._revision
    finally:
        gate.set()
        _dispose(dialog, qt_app)


def test_preview_failure_keeps_previous_image_and_recovers(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.errors import ValidationError

    calculate = outline.extrude_profiles
    dialog = OutlineDialog(SOURCE, ".svg")
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        previous = dialog.result_preview

        def refused(*args: object, **kwargs: object) -> object:
            raise ValidationError("height", "Wählen Sie eine andere Höhe.")

        monkeypatch.setattr(outline, "extrude_profiles", refused)
        dialog._fields["height"].set_value_mm(4)
        _until(qt_app, lambda: "andere Höhe" in dialog.state.text())
        assert dialog.result_preview is previous
        assert dialog.preview.renderer().isValid()
        assert not dialog.accept_button.isEnabled()
        monkeypatch.setattr(outline, "extrude_profiles", calculate)
        dialog._fields["height"].set_value_mm(6)
        _until(qt_app, dialog.accept_button.isEnabled)
        assert dialog.result_preview.mesh.bounds.size[2] == pytest.approx(6)
    finally:
        _dispose(dialog, qt_app)


def test_operation_dialog_uses_contour_field_and_preserves_dimension_expressions(
    qt_app: QApplication,
) -> None:
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import OperationDialog

    given = {"source": "src_1", "contours": '["first"]', "height": "=@thickness", "width": "=@span"}
    dialog = OperationDialog(
        REGISTRY.get("load_outline"),
        {},
        values=given,
        sources={"src_1": "profile.svg"},
        parameter_values={"thickness": 4, "span": 80},
    )
    try:
        field = dialog._editors["contours"]
        assert isinstance(field, ContourField)
        assert not field.findChildren(QLineEdit)
        events: list[str] = []
        field.choiceRequested.connect(lambda: events.append("choose"))
        dialog.valuesChanged.connect(lambda: events.append("changed"))
        QTest.mouseClick(field.button, Qt.MouseButton.LeftButton)
        assert "choose" in events
        field.set_value('["first","second"]')
        assert "changed" in events
        assert "2" in field.summary.text()
        assert dialog.values()["contours"] == '["first","second"]'
        assert dialog.values()["height"] == "=@thickness"
        assert dialog.values()["width"] == "=@span"
        field.set_value("[]")
        assert not dialog._accept_button.isEnabled()
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        field.set_value('["first"]')
        assert dialog._accept_button.isEnabled()
    finally:
        dialog.close()
        dialog.deleteLater()
        qt_app.processEvents()


def test_selection_only_dialog_keeps_dimensions_read_only(qt_app: QApplication) -> None:
    dialog = OutlineDialog(SOURCE, ".svg", values={"height": 8, "width": 96}, selection_only=True)
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        assert all(not field.isEnabled() for field in dialog._fields.values())
        assert dialog.values()["height"] == pytest.approx(8)
        assert dialog.values()["width"] == pytest.approx(96)
        assert dialog.result_preview.mesh.bounds.size == pytest.approx((96, 20, 8))
    finally:
        _dispose(dialog, qt_app)


def test_focused_secondary_button_keeps_the_primary_and_selection_clear(
    qt_app: QApplication,
) -> None:
    dialog = OutlineDialog(SOURCE, ".svg")
    dialog.show()
    try:
        _until(qt_app, dialog.accept_button.isEnabled)
        for button in dialog.findChildren(QPushButton):
            button.setFocus()
            qt_app.processEvents()
            assert dialog.accept_button.isDefault()
            if button is not dialog.accept_button:
                assert not button.isDefault()
        dialog.profiles.setCurrentRow(1)
        assert "Wird extrudiert" in dialog.profiles.currentItem().text()
        assert dialog.profiles.currentItem().checkState() == Qt.CheckState.Checked
        QTest.mouseClick(dialog.select_none, Qt.MouseButton.LeftButton)
        assert "Nicht ausgewählt" in dialog.profiles.currentItem().text()
    finally:
        _dispose(dialog, qt_app)
