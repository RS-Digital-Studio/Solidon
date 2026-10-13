"""P12 liest die markierten Feldträger samt tatsächlichem Zahlen- und Auswahlwert."""

from PySide6.QtWidgets import QComboBox, QVBoxLayout, QWidget

from app.core import guides
from app.core.types import ParamSpec
from app.ui.op_dialog import ValueField
from tools.function_capture import field_values


def test_revision_reads_the_marked_value_field_not_its_unmarked_spin(qt_app):
    """Die Zahl sitzt innen, ihr Wortschatzname und Kernwert am ValueField außen."""
    root = QWidget()
    layout = QVBoxLayout(root)
    field = ValueField(
        ParamSpec(name="diameter", title="Durchmesser", kind="float", default=8.0, unit="mm"),
        8.0,
        parent=root,
    )
    field.setProperty(guides.TARGET_PROPERTY, "field:diameter")
    layout.addWidget(field)
    choice = QComboBox(root)
    choice.addItem("Nur Bohrungsdurchmesser", "keep")
    choice.setProperty(guides.TARGET_PROPERTY, "field:entrance_mode")
    layout.addWidget(choice)
    values = field_values(root)
    assert values["diameter"] == 8.0
    assert values["entrance_mode"] == "keep"
    root.close()
