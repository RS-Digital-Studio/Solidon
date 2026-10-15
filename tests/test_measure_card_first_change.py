"""Vor der ersten Änderung ist Übernehmen grau und nennt ein offenes Feld als Weg (FD-31)."""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractSpinBox

from app.ui.labels import LengthSpin
from app.ui.panels import FIELD_PROPERTY
from tests.test_measure_group_layout import language as language
from tests.test_measure_group_layout import selected_hole as selected_hole
from tests.ui_helpers import session as session
from tests.ui_helpers import settle_measure_layout, wait_until
from tests.ui_helpers import window as window
from tools.function_capture import names_a_way_out, surface_field_titles


def _field(flow, name: str) -> LengthSpin:
    return next(
        widget
        for widget in flow._measure_group.findChildren(LengthSpin)
        if widget.property(FIELD_PROPERTY) == name
    )


def _says_a_way_out(apply) -> bool:
    """So liest der Funktionsdurchgang einen Sperrgrund (``function_capture``)."""
    return names_a_way_out(apply.toolTip(), [], [], fields=surface_field_titles(apply))


def test_the_sentence_names_the_first_open_field_of_the_card(selected_hole, qt_app):
    """Der Satz kommt aus der gemeinsamen Quelle und nennt ein Feld, das offen dasteht."""
    from app.ui.first_change import first_change_sentence

    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    apply = flow._measure_accept
    group = flow._measure_group
    assert not flow.dialog.begun and not apply.isEnabled()
    said = first_change_sentence(group.findChildren(QAbstractSpinBox), group)
    assert said and apply.toolTip() == said
    assert apply.accessibleDescription() == said and apply.statusTip() == said
    assert _says_a_way_out(apply), "der Prüfstand zählt das Feld als Ausweg"


def test_a_hidden_first_field_is_not_the_way(selected_hole, qt_app):
    """Ein verborgenes Feld ist kein Weg — der Satz nannte es trotzdem."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    diameter, depth = _field(flow, "diameter"), _field(flow, "depth")
    diameter.hide()
    flow._refresh_measure_actions()
    apply = flow._measure_accept
    title = depth.accessibleName().rsplit(" — ", 1)[-1]
    assert f"„{title}“" in apply.toolTip(), apply.toolTip()
    assert _says_a_way_out(apply), apply.toolTip()


def test_a_focus_alone_is_no_change(selected_hole, qt_app):
    """Der Fokus im Feld beginnt den Entwurf, ändert aber nichts.

    Bis hierher war *Übernehmen* danach offen, und sein Klick legte keinen
    Schritt an — ein Knopf ohne Wirkung. Jetzt bleibt er grau mit dem Satz,
    bis ein Wert sich ändert.
    """
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    apply = flow._measure_accept
    said = apply.toolTip()
    diameter = _field(flow, "diameter")
    diameter.setFocus(Qt.FocusReason.TabFocusReason)
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)
    assert flow.dialog.begun, "der Fokus bindet den Entwurf und die Auswahl"
    assert not apply.isEnabled() and apply.toolTip() == said
    QTest.keyClick(diameter, Qt.Key.Key_Up)
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)
    assert apply.isEnabled(), apply.toolTip()
    transactions = len(window.session.project.document.transactions)
    QTest.mouseClick(apply, Qt.MouseButton.LeftButton)
    assert window.session.wait_for_idle(30_000)
    wait_until(
        qt_app, lambda: len(window.session.project.document.transactions) == transactions + 1
    )


def test_the_scope_alone_is_a_change(selected_hole, qt_app):
    """Der Sammelhaken ändert den Umfang und keinen Wert — und gibt Übernehmen frei."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    apply, scope = flow._measure_accept, flow._measure_scope
    assert scope is not None and scope.isVisibleTo(flow._measure_box)
    QTest.mouseClick(scope, Qt.MouseButton.LeftButton)
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)
    assert scope.isChecked() and flow.dialog.begun
    assert apply.isEnabled(), apply.toolTip()
    QTest.mouseClick(scope, Qt.MouseButton.LeftButton)
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)
    assert not apply.isEnabled(), "zurückgeschaltet ist wieder nichts geändert"
