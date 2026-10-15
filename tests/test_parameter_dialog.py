"""Der Dialog, der ein Projektmaß anlegt oder ändert (Bauplan §13)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QLabel

from app.core.types import Parameter
from app.ui.dialogs import ParameterDialog


def test_the_parameter_action_uses_weight_as_well_as_colour(qt_app: QApplication) -> None:
    """Die Eingabetaste übernimmt; Hervorhebung trägt auch die Schrift des Knopfs."""
    dialog = ParameterDialog({})
    try:
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        action = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert action is not None
        assert action.isDefault()
        assert action.font().weight() > dialog.font().weight()
    finally:
        dialog.deleteLater()


def test_the_bounds_are_written_the_way_the_window_writes_numbers(qt_app: QApplication) -> None:
    """„Untergrenze 0.5" stand im deutschen Fenster neben „12,50 mm" im
    Wertfeld — eine Zahl, zwei Schreibweisen (`oberflaeche.md`, „Zahlen").
    Gelesen werden beide Trennzeichen, also darf das Feld zeigen, was die
    Oberfläche überall zeigt."""
    existing = Parameter(name="spiel", value=0.75, unit="mm", minimum=0.5, maximum=1.25)
    dialog = ParameterDialog({"spiel": existing}, existing=existing)
    try:
        assert dialog.minimum_field.text() == "0,5"
        assert dialog.maximum_field.text() == "1,25"
        assert dialog.validation_problem() is None
        taken = dialog.parameter()
        assert taken.minimum == pytest.approx(0.5)
        assert taken.maximum == pytest.approx(1.25)
    finally:
        dialog.deleteLater()


def test_only_name_value_and_unit_stand_in_front(qt_app: QApplication) -> None:
    """RM-359 F11: Vorn stehen Name, Wert und Einheit; die Grenzen dahinter (§2.4).

    Offen, wenn das Maß schon Grenzen hat, und sobald ein Satz eine Grenze
    meint — sonst stünde der Satz unter Feldern, die man nicht sieht.
    """
    from PySide6.QtWidgets import QLabel

    fresh = ParameterDialog({})
    bounded_parameter = Parameter(name="spiel", value=0.75, unit="mm", maximum=1.25)
    bounded = ParameterDialog({"spiel": bounded_parameter}, existing=bounded_parameter)
    try:
        fresh.show()
        bounded.show()
        QApplication.processEvents()
        front = [
            label.text()
            for label in fresh.findChildren(QLabel)
            if label.buddy() is not None or label.text() in ("Name", "Wert", "Einheit")
            if label.isVisibleTo(fresh)
        ]
        assert not fresh.minimum_field.isVisibleTo(fresh), "die Grenzen stehen hinten"
        assert not fresh.maximum_field.isVisibleTo(fresh)
        assert fresh.unit_field.isVisibleTo(fresh) and fresh.name_field.isVisibleTo(fresh)
        assert "Untergrenze" not in front
        assert bounded.maximum_field.isVisibleTo(bounded), "vorhandene Grenzen bleiben sichtbar"

        fresh.name_field.setText("wand")
        fresh.value_field.setValue(2.0)
        fresh.minimum_field.setText("5")
        fresh._accept()
        QApplication.processEvents()
        assert fresh.problem.text() == "Der Wert liegt außerhalb der eigenen Grenzen."
        assert fresh.minimum_field.isVisibleTo(fresh), "der Satz klappt die Grenzen auf"
    finally:
        fresh.deleteLater()
        bounded.deleteLater()


def _caption_of(dialog: ParameterDialog, field: object) -> QLabel:
    """Die Beschriftung, die das Feld als Ziel trägt (``QLabel.buddy``)."""
    found = [label for label in dialog.findChildren(QLabel) if label.buddy() is field]
    assert len(found) == 1, f"genau eine Beschriftung führt zu {field!r}"
    return found[0]


@pytest.mark.parametrize("editing", [False, True])
def test_every_field_says_what_it_does_on_both_halves(qt_app: QApplication, editing: bool) -> None:
    """FD-11: Name, Wert, Ausdruck, Einheit und die Grenzen ohne Satz — wofür eine
    Grenze gut ist, musste man raten. Jedes Feld trägt jetzt einen, an Feld und
    Beschriftung und am Vorleser, und der Satz wiederholt nicht den Titel."""
    existing = Parameter(name="spiel", value=0.4, unit="mm") if editing else None
    dialog = ParameterDialog({"spiel": existing} if existing else {}, existing=existing)
    try:
        for field in (
            dialog.name_field,
            dialog.value_field,
            dialog.expression_field,
            dialog.unit_field,
            dialog.minimum_field,
            dialog.maximum_field,
        ):
            caption = _caption_of(dialog, field)
            sentence = field.accessibleDescription()
            assert sentence, f"{caption.text()}: ohne Satz"
            assert field.toolTip() == sentence, f"{caption.text()}: Kurzhilfe fehlt"
            assert caption.toolTip() == sentence, f"{caption.text()}: Beschriftung ohne Satz"
            assert len(sentence.split()) >= 4, f"{caption.text()}: wiederholt nur den Titel"
            assert field.accessibleName() == caption.text(), "FD-94: Name wie die Zeile"
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize(
    ("typed", "taken", "expected"),
    [
        ("Breite Platte", set(), "Breite_Platte"),
        ("Höhe", set(), "Hoehe"),
        ("3fach", set(), "_3fach"),
        ("breite", {"breite"}, "breite_2"),
        ("breite", {"breite", "breite_2"}, "breite_3"),
        ("Länge-außen", set(), "Laenge_aussen"),
        ("—", set(), None),
    ],
)
def test_a_refused_name_gets_a_free_name_made_from_what_was_typed(
    typed: str, taken: set[str], expected: str | None
) -> None:
    """FD-155: Der Weg aus der Ablehnung ist ein Name, der geht — aus dem Getippten."""
    from app.ui.parameter_dialog import suggested_name, usable_name

    made = suggested_name(typed, taken)
    assert made == expected
    if made is not None:
        assert usable_name(made), "der Vorschlag lässt sich als @name schreiben"


def test_a_refused_name_stands_at_the_name_field_with_its_way(qt_app: QApplication) -> None:
    """FD-155: Die Ablehnung des Namens stand unter „Weitere Einstellungen“, das Feld
    war nicht markiert, eine Handlung fehlte. Jetzt steht sie direkt unter dem
    Namensfeld, das Feld hat den Fokus und ist markiert, und ein Knopf nimmt
    einen freien Namen."""
    dialog = ParameterDialog({"breite": Parameter(name="breite", value=40.0)})
    try:
        dialog.show()
        QApplication.processEvents()
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None
        assert not dialog.name_refusal.isVisibleTo(dialog), "vor dem ersten Versuch still"

        dialog.name_field.setText("Breite Platte")
        ok.click()
        QApplication.processEvents()

        sentence = dialog.name_problem()
        assert sentence is not None and "@name" in sentence
        assert dialog.name_refusal.isVisibleTo(dialog), "die Ablehnung steht da"
        assert not dialog.problem.isVisibleTo(dialog), "und nicht am Ende des Dialogs"
        assert sentence in dialog.name_note.accessibleDescription()
        assert dialog.name_field.accessibleDescription() == sentence, "das Feld sagt es vor"
        assert dialog.focusWidget() is dialog.name_field, "der Cursor steht im Feld"
        assert dialog.name_field.selectedText() == "Breite Platte", "das Feld ist markiert"
        field_bottom = dialog.name_field.mapTo(dialog, dialog.name_field.rect().bottomLeft()).y()
        refusal_top = dialog.name_refusal.mapTo(dialog, dialog.name_refusal.rect().topLeft()).y()
        value_top = dialog.value_field.mapTo(dialog, dialog.value_field.rect().topLeft()).y()
        assert field_bottom < refusal_top < value_top, "direkt unter dem Namensfeld"
        assert dialog.name_suggestion.isVisibleTo(dialog)
        assert dialog.name_suggestion.text() == "„Breite_Platte“ verwenden"

        dialog.name_suggestion.click()
        QApplication.processEvents()
        assert dialog.name_field.text() == "Breite_Platte"
        assert not dialog.name_refusal.isVisibleTo(dialog), "erledigt, also still"
        assert dialog.validation_problem() is None

        dialog.name_field.setText("breite")
        ok.click()
        QApplication.processEvents()
        assert dialog.name_suggestion.text() == "„breite_2“ verwenden", "vergeben → frei"

        dialog.name_field.setText("")
        ok.click()
        QApplication.processEvents()
        assert dialog.name_refusal.isVisibleTo(dialog)
        assert not dialog.name_suggestion.isVisibleTo(dialog), "aus nichts kein Vorschlag"
    finally:
        dialog.close()
        dialog.deleteLater()
