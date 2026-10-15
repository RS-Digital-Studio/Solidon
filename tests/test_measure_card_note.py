"""Die Ablehnung eines Maßes steht am Feld und nicht noch einmal in der Maßgruppe (FD-88)."""

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

from app.ui.labels import LengthSpin
from app.ui.panels import FIELD_PROPERTY
from tests.test_measure_group_layout import language as language
from tests.test_measure_group_layout import selected_hole as selected_hole
from tests.ui_helpers import session as session
from tests.ui_helpers import settle_measure_layout
from tests.ui_helpers import window as window


def test_the_refusal_stands_once_at_the_field(selected_hole, qt_app):
    """Feld und Hinweis der Gruppe sagten denselben Satz; jetzt nur das Feld."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    field = next(
        widget
        for widget in flow._measure_group.findChildren(LengthSpin)
        if widget.property(FIELD_PROPERTY) == "diameter"
    )
    field.lineEdit().setFocus()
    field.lineEdit().selectAll()
    QTest.keyClicks(field.lineEdit(), "0,1")
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)
    sentence = field.refusal()
    assert sentence, "Voraussetzung: 0,1 mm liegt unter der Untergrenze"
    card = flow._measure_box
    shown = [
        label
        for label in card.findChildren(QLabel)
        if label.isVisibleTo(card) and sentence in label.text()
    ]
    assert len(shown) == 1, [label.objectName() for label in shown]
    assert flow._measure_group.isAncestorOf(shown[0]), "der Satz steht am Feld"
    apply = flow._measure_accept
    assert not apply.isEnabled()
    assert sentence in apply.toolTip() and sentence in apply.accessibleDescription(), (
        "der graue Knopf trägt seinen Grund weiter (Regel 18)"
    )
