"""Die Statuszeile wiederholt keine Ablehnung, die schon am Feld steht (FD-88).

Lehnt ein Feld der Maßgruppe eine Zahl ab, steht der Satz darunter, samt Weg.
Die Karte wiederholt ihn nicht mehr (``test_measure_card_note.py``); die
Statuszeile tat es noch, sobald Eingabetaste oder *Übernehmen* die Felder
lasen (``MainWindow`` → ``read_fields(interpret=True)`` → ``announce``).
"""

from PySide6.QtTest import QTest

from app.ui.labels import LengthSpin
from app.ui.panels import FIELD_PROPERTY
from tests.test_measure_group_layout import language as language
from tests.test_measure_group_layout import selected_hole as selected_hole
from tests.ui_helpers import session as session
from tests.ui_helpers import settle_measure_layout
from tests.ui_helpers import window as window


def _refused_diameter(selected_hole, qt_app):
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
    return window, flow, field, sentence


def test_reading_a_refused_field_does_not_repeat_it_in_the_status_line(selected_hole, qt_app):
    window, flow, field, sentence = _refused_diameter(selected_hole, qt_app)
    window.status_message.setText("")

    assert not flow._interpret_active_fields(), "die abgelehnte Zahl wird nicht übernommen"
    settle_measure_layout(qt_app)

    assert flow.measure_group is not None and flow.measure_group.isAncestorOf(field)
    assert sentence not in window.status_message.text(), "der Satz steht schon am Feld"
    assert field.lineEdit().hasFocus() or field.hasFocus(), "die Tastatur steht im Feld"
