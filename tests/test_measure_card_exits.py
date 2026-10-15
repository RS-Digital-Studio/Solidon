"""Jeder Ausgang der Maßgruppe gibt den Fokus an die Ansicht zurück (FD-160)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.ui.labels import LengthSpin
from app.ui.panels import FIELD_PROPERTY
from tests.test_measure_group_layout import language as language
from tests.test_measure_group_layout import selected_hole as selected_hole
from tests.ui_helpers import session as session
from tests.ui_helpers import settle_measure_layout, wait_until
from tests.ui_helpers import window as window


def _diameter(flow) -> LengthSpin:
    return next(
        widget
        for widget in flow._measure_group.findChildren(LengthSpin)
        if widget.property(FIELD_PROPERTY) == "diameter"
    )


def _focus(qt_app):
    settle_measure_layout(qt_app)
    return QApplication.focusWidget()


@pytest.mark.parametrize("from_the_keyboard", [False, True])
def test_cancel_gives_the_focus_to_the_view(selected_hole, qt_app, from_the_keyboard):
    """Nach *Abbrechen* stand der Fokus auf dem Kartengriff „Objekte“."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    cancel = flow._measure_cancel
    if from_the_keyboard:
        cancel.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(cancel, Qt.Key.Key_Space)
    else:
        QTest.mouseClick(cancel, Qt.MouseButton.LeftButton)
    assert window.session.wait_for_idle(30_000)
    assert not flow.active
    assert _focus(qt_app) is window.viewport


def test_escape_in_a_field_gives_the_focus_to_the_view(selected_hole, qt_app):
    """Escape im Maßfeld bricht ab wie der Knopf — und der Fokus geht denselben Weg."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    field = _diameter(flow)
    field.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
    assert window.session.wait_for_idle(30_000)
    assert not flow.active
    assert _focus(qt_app) is window.viewport


def test_apply_and_undo_leave_the_focus_in_the_view(selected_hole, qt_app):
    """Übernehmen und Strg+Z enden in der Ansicht — wie Abbrechen."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    field = _diameter(flow)
    field.lineEdit().setFocus()
    field.lineEdit().selectAll()
    QTest.keyClicks(field.lineEdit(), "5,4")
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)
    steps = len(window.session.project.document.transactions)
    apply = flow._measure_accept
    assert apply.isEnabled(), apply.toolTip()
    apply.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(apply, Qt.Key.Key_Space)
    assert window.session.wait_for_idle(30_000)
    wait_until(qt_app, lambda: len(window.session.project.document.transactions) == steps + 1)
    assert _focus(qt_app) is window.viewport
    QTest.keyClick(window.viewport, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert window.session.wait_for_idle(30_000)
    assert _focus(qt_app) is window.viewport
