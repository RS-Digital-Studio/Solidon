"""Ein Einheitenwechsel bei offener Parameterleiste schreibt alle Längen neu (RA-2).

``MainWindow.set_display_unit`` zog nur die Längenfelder nach. Das abgeleitete
Maß daneben blieb bei „50,80“, und eine zu große Zahl wurde mit der alten
Grenze abgelehnt: „20,0000 in liegt über der Obergrenze 254,0000 in.“ — eine
Millimeterzahl als Zoll.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QLabel

from app.core.types import Parameter
from app.ui.labels import set_display_unit
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    built = MainWindow(Session(), UiSettings())
    built.resize(1600, 1000)
    built.show()
    built._show_start_screen(False)
    yield built
    set_display_unit("mm")
    assert built.session.wait_for_idle(60_000)
    built.release()
    built.deleteLater()
    qt_app.processEvents()


def test_switching_to_inches_rewrites_derived_measures_and_limits(
    qt_app: QApplication, window: MainWindow
) -> None:
    assert window.session.add_parameter(
        Parameter(name="breite", value=25.4, title="Breite", minimum=0.0, maximum=254.0)
    )
    assert window.session.add_parameter(
        Parameter(name="doppelt", value=50.8, title="Doppelt", expression="@breite * 2")
    )
    assert window.session.wait_for_idle(60_000)
    for _round in range(10):
        qt_app.processEvents()
    panel = window.parameters
    assert "50,80" in [label.text() for label in panel.findChildren(QLabel)], "Voraussetzung"

    window.set_display_unit("in")
    for _round in range(10):
        qt_app.processEvents()

    labels = [label.text() for label in panel.findChildren(QLabel) if label.isVisibleTo(panel)]
    assert "2,0000" in labels, labels
    assert "50,80" not in labels, labels
    spin = next(
        widget
        for widget in panel.findChildren(QAbstractSpinBox)
        if widget.accessibleName() == "Breite"
    )
    assert spin.value() == pytest.approx(1.0)
    line = spin.lineEdit()
    line.setFocus()
    line.selectAll()
    QTest.keyClicks(line, "20")
    QTest.keyClick(line, Qt.Key.Key_Return)
    for _round in range(5):
        qt_app.processEvents()
    refusal = panel.refusal_text()
    assert "10,0000" in refusal and "254" not in refusal, refusal
