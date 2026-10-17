"""Die Statuszeile wiederholt keine Ablehnung, die schon am Feld steht (FD-88).

Lehnt ein Feld der Maßgruppe eine Zahl ab, steht der Satz darunter, samt Weg.
Die Karte wiederholt ihn nicht mehr (``test_measure_card_note.py``); die
Statuszeile tat es noch, sobald Eingabetaste oder *Übernehmen* die Felder
lasen (``MainWindow`` → ``read_fields(interpret=True)`` → ``announce``).

Ein zweiter Weg lief an ``announce`` vorbei: Der graue Knopf *Übernehmen* trug
den Sperrgrund auch als ``statusTip``, und wer auf ihn zeigte, las ihn unten
links noch einmal (Schlusslauf L4, Fall 001). Statustipps tragen nur
Menüaktionen (RM-509, ``test_text_length.py``).
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from app.ui.labels import LengthSpin
from app.ui.panels import FIELD_PROPERTY
from tests.test_measure_group_layout import language as language
from tests.test_measure_group_layout import selected_hole as selected_hole
from tests.ui_helpers import session as session
from tests.ui_helpers import settle_measure_layout
from tests.ui_helpers import window as window


def _diameter(flow) -> LengthSpin:
    return next(
        widget
        for widget in flow._measure_group.findChildren(LengthSpin)
        if widget.property(FIELD_PROPERTY) == "diameter"
    )


def _refused_diameter(selected_hole, qt_app):
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    field = _diameter(flow)
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


def test_pointing_at_the_grey_apply_does_not_repeat_the_refusal(selected_hole, qt_app):
    """Der Weg des Funktionsdurchgangs (Fehlfall ``resize_hole``): Feld anklicken,
    alles markieren, „0,1“ tippen, auf das graue *Übernehmen* zeigen und klicken.

    Unter dem Feld steht der Satz mit dem Weg zum Entfernen (FD-36); die
    Statuszeile — eigene Zeile wie Meldung von ``QStatusBar`` — sagt ihn nicht
    ein zweites Mal. Kurzhilfe und Beschreibung des Knopfs tragen den Grund
    weiter (Regel 18).
    """
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    field = _diameter(flow)
    line = field.lineEdit()
    QTest.mouseClick(line, Qt.MouseButton.LeftButton, pos=line.rect().center())
    QTest.keySequence(line, QKeySequence(QKeySequence.StandardKey.SelectAll))
    QTest.keyClicks(line, "0,1")
    QApplication.processEvents()
    sentence = field.refusal()
    assert sentence, "Voraussetzung: 0,1 mm liegt unter der Untergrenze"
    window.status_message.setText("")
    window.statusBar().clearMessage()

    apply = flow._measure_accept
    assert not apply.isEnabled(), "Voraussetzung: Übernehmen steht grau"
    QTest.mouseMove(apply, apply.rect().center())
    QTest.mouseClick(apply, Qt.MouseButton.LeftButton, pos=apply.rect().center())
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)

    under_field = [
        label.text()
        for label in flow.measure_group.findChildren(QLabel)
        if sentence in label.text() and label.isVisibleTo(flow.measure_group)
    ]
    assert under_field and any(text != sentence for text in under_field), (
        "der Satz steht am Feld, mit dem Weg zum Entfernen dahinter (FD-36)"
    )
    assert sentence not in window.statusBar().currentMessage(), "der Satz steht schon am Feld"
    assert sentence not in window.status_message.text(), "der Satz steht schon am Feld"
    assert apply.toolTip() == sentence and apply.accessibleDescription() == sentence
    assert not apply.statusTip(), "Statustipps nur an Menüaktionen (RM-509)"
