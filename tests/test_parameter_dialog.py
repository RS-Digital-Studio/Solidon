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
