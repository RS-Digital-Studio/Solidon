"""Der Doppelklick auf eine Maßänderung im Verlauf öffnet im Fenster den Maßdialog (FD-166).

Das Panel meldet ``parameterActivated`` (``test_history_parameter_rows.py``);
hier wird geprüft, dass das Fenster denselben Weg geht wie *Ändern …* an der
Parameterleiste — ``action_edit_parameter`` mit dem Namen des Maßes.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from app.core.types import Parameter
from app.ui.dialogs import ParameterDialog
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    built = MainWindow(Session(), UiSettings())
    built.resize(1920, 1080)
    built.show()
    built._show_start_screen(False)
    yield built
    built.wait_for_workers()
    built.hide()
    built.deleteLater()
    qt_app.processEvents()


def test_a_double_click_on_a_parameter_row_opens_its_dialog(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []

    def shown(dialog: ParameterDialog) -> int:
        opened.append(dialog.parameter().name)
        return int(ParameterDialog.DialogCode.Rejected)

    monkeypatch.setattr(ParameterDialog, "exec", shown)
    assert window.session.add_parameter(Parameter(name="breite", value=12.0))
    QApplication.processEvents()
    panel = window.history_panel
    row = next(
        panel.list.item(index)
        for index in range(panel.list.count())
        if "breite" in panel.list.item(index).text().casefold()
    )

    panel.list.itemDoubleClicked.emit(row)

    assert opened == ["breite"], opened


def test_a_double_click_on_a_printer_change_opens_the_print_settings(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drucker- und Materialänderungen öffnen die Druckeinstellungen (RA-6).

    Am echten Draht: Zeile doppelklicken, und der Dialog des Fensters geht auf.
    Ersetzt ist ``exec`` jedes Dialogs, nicht nur der Druckeinstellungen: Führt
    die Zeile in einen anderen Dialog, wird der Fall rot, statt modal zu hängen
    (Nachprüfung, L3).
    """
    from PySide6.QtWidgets import QDialog

    from app.core.types import DocumentChange, DocumentState, Transaction
    from app.ui import main_window

    shown: list[str] = []

    def opened(dialog: QDialog) -> int:
        shown.append(type(dialog).__name__)
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(QDialog, "exec", opened)
    monkeypatch.setattr(main_window, "ensure_print_disclosure", lambda *args: None)
    document = window.session.project.document
    document.transactions.append(
        Transaction(
            id="drucker",
            title="Drucker wechseln",
            ops=(),
            changes=DocumentChange(
                before=DocumentState(printer="alt"), after=DocumentState(printer="neu")
            ),
        )
    )
    panel = window.history_panel
    panel.show_document(document)
    row = next(
        panel.list.item(index)
        for index in range(panel.list.count())
        if "Drucker" in panel.list.item(index).text()
    )

    panel.list.itemDoubleClicked.emit(row)

    assert shown == ["PrintSettingsDialog"], shown
