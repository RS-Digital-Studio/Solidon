"""Der Dialog, der ein Projektmaß anlegt oder ändert (Bauplan §13)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

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
