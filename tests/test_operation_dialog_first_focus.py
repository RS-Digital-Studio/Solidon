"""Ein vorgegebener Text ist beim ersten Fokus markiert (FD-114).

*Umbenennen* zeigt den aktuellen Namen; wer etwas anderes will, tippt einfach,
wer nur ergänzt, drückt Ende. Ohne Markierung stand der Cursor vor dem Namen,
und jeder Buchstabe landete davor. Den Namen gibt das Fenster vor
(``MainWindow.run_operation``); hier geht es um den Dialog.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLineEdit

from app.core import bootstrap
from app.core.registry import REGISTRY
from tests.ui_helpers import wait_until


def test_a_given_name_is_selected_when_the_dialog_opens(qt_app: QApplication) -> None:
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    dialog = OperationDialog(
        REGISTRY.get("rename_object"),
        {"obj_1": "Deckel links"},
        None,
        values={"name": "Deckel links"},
    )
    try:
        dialog.show()
        dialog.activateWindow()
        line = dialog._editors["name"]
        assert isinstance(line, QLineEdit)
        wait_until(qt_app, line.hasFocus)
        qt_app.processEvents()
        assert line.text() == "Deckel links"
        assert line.selectedText() == "Deckel links", "der Name ist markiert, Tippen ersetzt ihn"
    finally:
        dialog.reject()
        dialog.deleteLater()


def test_a_text_reached_through_focus_field_is_selected_too(qt_app: QApplication) -> None:
    """Derselbe Sprung wie in ein Zahlenfeld (``focus_field``): Der Wert ist markiert."""
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    dialog = OperationDialog(
        REGISTRY.get("rename_object"), {"obj_1": "Deckel"}, None, values={"name": "Deckel"}
    )
    try:
        dialog.show()
        qt_app.processEvents()
        line = dialog._editors["name"]
        assert isinstance(line, QLineEdit)
        line.deselect()
        assert dialog.focus_field("name")
        assert line.selectedText() == "Deckel"
    finally:
        dialog.reject()
        dialog.deleteLater()
