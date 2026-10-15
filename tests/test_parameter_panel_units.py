"""Die Parameterleiste zeigt Längen in der Anzeigeeinheit (FD-125, Zwilling der Leiste).

*Parameter anlegen …* zeigt eine Länge seit F2b in Zoll, wenn Zoll eingestellt
ist; die Leiste daneben zeigte dieselbe *Breite* weiter als „25,40“ mit „mm“.
Jetzt steht sie in der Anzeigeeinheit, gespeichert und gemeldet wird weiter in
Millimetern, und ein unberührtes Feld bringt keinen Rundungsrest mit.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QComboBox, QLabel

from app.core.types import Document, Parameter
from app.ui.labels import set_display_unit
from app.ui.parameter_length import value_mm


def test_a_length_row_speaks_inches_and_stores_millimetres(qt_app: QApplication) -> None:
    from app.ui.panels import ParameterPanel

    set_display_unit("in")
    document = Document(format_version=1, app_version="0.0.1")
    document.parameters["breite"] = Parameter(
        name="breite", value=25.4, title="Breite", minimum=0.0, maximum=254.0
    )
    document.parameters["doppelt"] = Parameter(
        name="doppelt", value=50.8, title="Doppelt", expression="@breite * 2"
    )
    panel = ParameterPanel()
    edits: list[tuple[str, float]] = []
    panel.parameterEdited.connect(lambda name, value: edits.append((name, value)))
    try:
        panel.show_document(document)
        panel.show()
        qt_app.processEvents()
        spin = next(
            widget
            for widget in panel.findChildren(QAbstractSpinBox)
            if widget.accessibleName() == "Breite"
        )
        assert spin.value() == pytest.approx(1.0), "die Zahl steht in Zoll"
        assert value_mm(spin) == 25.4, "unberührt ohne Rundungsrest"
        assert spin.maximum() == pytest.approx(10.0), "die Grenze in Zoll"
        unit = next(
            box
            for box in panel.findChildren(QComboBox)
            if box.property("parameterName") == "breite"
        )
        assert unit._compact_text() == "in", "die Einheit daneben sagt Zoll"
        derived = [label.text() for label in panel.findChildren(QLabel) if label.text() == "2,0000"]
        assert derived, "auch das abgeleitete Maß in Zoll"

        line = spin.lineEdit()
        line.selectAll()
        QTest.keyClicks(line, "2")
        QTest.keyClick(line, Qt.Key.Key_Return)
        qt_app.processEvents()
        qt_app.processEvents()
        assert edits and edits[-1][0] == "breite"
        assert edits[-1][1] == pytest.approx(50.8), "gemeldet in Millimetern"
    finally:
        panel.deleteLater()
        set_display_unit("mm")
