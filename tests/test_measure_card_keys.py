"""Die Tabulatortaste bleibt in der Maßgruppe und geht denselben Weg wie das Auge (FD-86)."""

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from app.ui.labels import LengthSpin
from app.ui.panels import FIELD_PROPERTY
from tests.test_measure_group_layout import language as language
from tests.test_measure_group_layout import selected_hole as selected_hole
from tests.ui_helpers import measure_more_heading, settle_measure_layout
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def _field(flow, name: str) -> LengthSpin:
    return next(
        widget
        for widget in flow._measure_group.findChildren(LengthSpin)
        if widget.property(FIELD_PROPERTY) == name
    )


def _stops(qt_app, start: QWidget, key: Qt.Key, count: int) -> list[QWidget | None]:
    """Wo der Fokus nach jedem Tastendruck steht — ``count`` Halte ab ``start``."""
    start.setFocus(Qt.FocusReason.TabFocusReason)
    qt_app.processEvents()
    seen = []
    for _ in range(count):
        QTest.keyClick(QApplication.focusWidget(), key)
        qt_app.processEvents()
        seen.append(QApplication.focusWidget())
    return seen


def _top(flow, widget: QWidget) -> int:
    return widget.mapTo(flow._measure_box, QPoint()).y()


def test_tab_walks_fields_more_scope_apply_cancel_and_closes_at_the_card(selected_hole, qt_app):
    """Felder → Weitere Werte → Sammelhaken → Übernehmen → Abbrechen → erstes Feld.

    Qt reihte die später gebauten Felder hinter die Knöpfe; nach „Weitere
    Werte“ ging es zum Kartengriff „Objekte“, Haken und Knöpfe kamen nie.
    """
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    diameter, depth = _field(flow, "diameter"), _field(flow, "depth")
    more = measure_more_heading(flow)
    scope = flow._measure_scope
    assert scope is not None and scope.isVisibleTo(flow._measure_box), "Voraussetzung: Sammelhaken"
    apply, cancel = flow._measure_accept, flow._measure_cancel

    # Ein grauer Knopf ist kein Halt; ob Übernehmen schon offen ist, sagt die
    # Regel vor der ersten Änderung (FD-31), nicht die Tabulatortaste.
    diameter.setFocus(Qt.FocusReason.TabFocusReason)
    settle_measure_layout(qt_app)
    buttons = [apply, cancel] if apply.isEnabled() else [cancel]
    expected = [depth, more, scope, *buttons, diameter]
    assert _stops(qt_app, diameter, Qt.Key.Key_Tab, len(expected)) == expected
    backward = [cancel, apply if apply.isEnabled() else scope]
    assert _stops(qt_app, diameter, Qt.Key.Key_Backtab, 2) == backward

    # Nach der ersten Eingabe ist Übernehmen offen und ein Halt vor Abbrechen.
    diameter.lineEdit().setFocus()
    diameter.lineEdit().selectAll()
    QTest.keyClicks(diameter.lineEdit(), "5,4")
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)
    assert apply.isEnabled(), apply.toolTip()
    expected = [depth, more, scope, apply, cancel, diameter]
    assert _stops(qt_app, diameter, Qt.Key.Key_Tab, len(expected)) == expected


def test_the_scope_stands_where_tab_reaches_it_before_the_buttons(selected_hole, qt_app):
    """Das Auge liest den Haken vor den Knöpfen, wie im Merkmalfenster (``_settle_tab_order``)."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    scope = flow._measure_scope
    assert scope is not None and scope.isVisibleTo(flow._measure_box)
    assert _top(flow, measure_more_heading(flow)) < _top(flow, scope)
    assert _top(flow, scope) < _top(flow, flow._measure_accept)
    assert _top(flow, flow._measure_accept) == _top(flow, flow._measure_cancel)


@pytest.mark.parametrize("opened", [False, True])
def test_the_values_behind_more_stand_between_more_and_the_scope(selected_hole, qt_app, opened):
    """Aufgeklappt reihen sich die Felder hinter „Weitere Werte“ vor den Haken."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    more = measure_more_heading(flow)
    if opened:
        QTest.mouseClick(more, Qt.MouseButton.LeftButton)
        settle_measure_layout(qt_app)
    assert more.isChecked() is opened
    stops = _stops(qt_app, more, Qt.Key.Key_Tab, 12)
    scope = stops.index(flow._measure_scope)
    behind = stops[:scope]
    assert all(flow._measure_group.isAncestorOf(widget) for widget in behind)
    assert bool(behind) is opened, [widget.objectName() for widget in behind]
    assert all(flow._measure_box.isAncestorOf(widget) for widget in stops)
