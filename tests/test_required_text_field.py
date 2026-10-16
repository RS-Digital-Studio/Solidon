"""Ein leerer Pflichttext ist ein Hinweis am Feld, kein Fehler (FD-134).

*Schriftzug als Körper* rechnete beim Öffnen eine Vorschau mit leerem Text,
und der Kern sagte „Ohne Text gibt es nichts anzulegen.“ als Absage samt
*Details anzeigen* — bevor der Kunde etwas getan hatte. Die Geschwister
(*Text aufbringen*, *Text einlegen*) warten auf die Stelle und zeigten
dasselbe nicht; ihr Knopf stand dafür mit leerem Text offen. Jetzt gilt für
jeden Pflichttext dasselbe wie für ein Pflichtbild: keine Vorschau, solange
er fehlt, der Knopf grau mit dem Satz, der das Feld nennt, und im Feld der
Hinweis, dass es gebraucht wird.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QLineEdit

from app.core import bootstrap
from app.core.registry import REGISTRY
from app.core.scene.project import save
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import wait_until
from tools import function_scenes

#: Die Operationen mit einem Pflichtfeld aus freiem Text.
REQUIRED_TEXT = {
    "create_label": "text",
    "label_text": "text",
    "inlay_text": "text",
    "rename_object": "name",
}


def test_an_empty_required_text_holds_the_button_with_a_sentence(qt_app: QApplication) -> None:
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    for operation, field in REQUIRED_TEXT.items():
        spec = REGISTRY.get(operation)
        title = str(next(entry for entry in spec.params.spec() if entry.name == field).title)
        dialog = OperationDialog(spec, {"obj_1": "Quader"}, None)
        try:
            button = dialog._accept_button
            line = dialog._editors[field]
            assert isinstance(line, QLineEdit)
            assert line.placeholderText(), f"{operation}: kein Hinweis im leeren Feld"
            assert dialog.source_missing(), f"{operation}: die Vorschau rechnete mit leerem Text"
            assert not button.isEnabled(), operation
            assert title in button.toolTip(), f"{operation}: {button.toolTip()!r}"
            assert button.accessibleDescription() == button.toolTip()

            line.setText("A")
            assert not dialog.source_missing(), operation
            assert title not in button.toolTip(), operation
            line.setText("   ")
            assert dialog.source_missing(), f"{operation}: Leerzeichen sind kein Text"
        finally:
            dialog.deleteLater()


def test_opening_a_label_body_shows_no_refusal(qt_app: QApplication, tmp_path: Path) -> None:
    """Der Weg wie im Lauf: leeres Projekt, über das Fenster geöffnet, ohne
    Fehlerblock im Dialog und ohne Absage im Band."""
    from app.ui.op_dialog import OperationDialog

    path = tmp_path / "leer.p3d"
    save(function_scenes.build_scene("leer"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(1920, 1080)
    window.show()
    window._show_start_screen(False)
    try:
        window.open_path(path)
        assert window.session.wait_for_idle(60_000)
        qt_app.processEvents()
        window.run_operation(REGISTRY.get("create_label"))
        dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
        assert window.session.wait_for_idle(60_000)
        for _round in range(20):
            qt_app.processEvents()
        assert window.session.wait_for_idle(60_000)
        qt_app.processEvents()
        assert not dialog._refusal.isVisible(), dialog._refusal.text()
        assert not window._preview_reason, window._preview_reason
        assert not dialog._accept_button.isEnabled()

        line = dialog._editors["text"]
        assert isinstance(line, QLineEdit)
        line.setText("Solidon")
        wait_until(qt_app, dialog._accept_button.isEnabled)
        dialog.reject()
    finally:
        window.wait_for_workers()
        window.hide()
        window.deleteLater()
        qt_app.processEvents()
