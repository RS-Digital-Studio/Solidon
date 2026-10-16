"""Ein Rechtsklick auf das Wertfeld einer Parameterzeile öffnet *Ändern …* (FD-174).

An der Beschriftung stand das Menü der Zeile, am Wertfeld Qts englisches
Textfeldmenü („&Undo“, „Cu&t“, „&Step up“) — unübersetzt und ohne den Weg zu
Grenzen, Einheit und Ausdruck. Das Wertfeld reicht den Rechtsklick jetzt an
die Zeile weiter; Ausschneiden, Kopieren und Einfügen bleiben auf der Tastatur.
"""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QAbstractSpinBox, QApplication, QLineEdit, QMenu

from app.core.types import Document, Parameter


def test_a_right_click_on_the_value_opens_the_row_menu(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ui import panels
    from app.ui.panels import ParameterPanel

    document = Document(format_version=1, app_version="0.0.1")
    document.parameters["breite"] = Parameter(name="breite", value=12.0, title="Breite")
    panel = ParameterPanel()
    try:
        panel.show_document(document)
        panel.resize(320, 300)
        panel.show()
        qt_app.processEvents()
        spin = next(
            widget
            for widget in panel.findChildren(QAbstractSpinBox)
            if widget.accessibleName() == "Breite"
        )
        editors = [spin, *spin.findChildren(QLineEdit)]
        policies = {type(editor).__name__: editor.contextMenuPolicy() for editor in editors}
        assert all(policy == Qt.ContextMenuPolicy.NoContextMenu for policy in policies.values()), (
            f"das Wertfeld zeigt sein eigenes Menü: {policies}"
        )

        shown: list[list[str]] = []

        class ShownMenu(QMenu):
            """Hält fest, was das Menü zeigen würde, statt modal zu warten."""

            def exec(self, *_args: Any) -> None:  # type: ignore[override]
                shown.append([action.objectName() for action in self.actions()])

        monkeypatch.setattr(panels, "QMenu", ShownMenu)
        line = spin.findChild(QLineEdit)
        assert line is not None
        centre = line.rect().center()
        event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, centre, line.mapToGlobal(centre))
        QApplication.sendEvent(line, event)
        qt_app.processEvents()
        assert shown == [["parameters.edit"]], shown
    finally:
        panel.deleteLater()
