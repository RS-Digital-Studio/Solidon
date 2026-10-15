"""Ein Operationsdialog öffnet so hoch wie sein Inhalt (FD-45).

*Merkmal vervielfachen* öffnete mit einem leeren Streifen über den Knöpfen:
Die Anfangsmessung las das Formular, bevor es einmal in seiner Breite lag,
und der umbrochene Hinweis der Merkmalsliste zählte eine Zeile zu viel. Das
passive Nachmessen gibt nie Höhe zurück (``fenster.md``, RM-487), also blieb
der Streifen für die Lebensdauer des Dialogs stehen.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QApplication

from app.core import bootstrap
from app.core.registry import REGISTRY

#: So viele Punkte darf der Rollbereich höher sein als sein Inhalt — Rundung.
SLACK = 1

FEATURES = {"hole_1": "Bohrung 1 · Ø5,20 mm · eingepasst"}


def _settle(app: QApplication, seconds: float = 0.5) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()


@pytest.mark.parametrize("operation", ["pattern_feature", "group_pattern", "hollow_object"])
def test_the_dialog_opens_without_an_empty_strip(qt_app: QApplication, operation: str) -> None:
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    spec = REGISTRY.get(operation)
    field = "openings" if operation == "hollow_object" else "at_features"
    dialog = OperationDialog(
        spec, {"obj_1": "Quader"}, None, features=FEATURES, values={field: ["hole_1"]}
    )
    try:
        dialog.show()
        _settle(qt_app)
        scroll = dialog._scroll
        content = scroll.widget()
        layout = content.layout()
        assert layout is not None
        needed = layout.totalHeightForWidth(scroll.viewport().width())
        empty = scroll.viewport().height() - needed
        assert empty <= SLACK, f"{operation}: {empty} Punkte leer über den Knöpfen"
        assert scroll.verticalScrollBar().maximum() == 0, f"{operation}: der Inhalt rollt"
    finally:
        dialog.reject()
        dialog.deleteLater()
