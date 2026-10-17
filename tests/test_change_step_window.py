"""Der Änderungsweg im Fenster: *Übernehmen*, grau mit Weg bis zur ersten Änderung (FD-99).

Der Lauf öffnete über *Gewindeschritt öffnen* den Gewindedialog: Hauptknopf
„Einsetzen“, grau, und der Grund war die Absage des Stifts — nicht, was der
Kunde jetzt tun kann. Geprüft am Weg des Laufs (Szene ``gewinde_zu_kurz``,
``edit_operation`` mit dem Feld „Länge“).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core.scene.project import save
from app.i18n import tr
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import wait_until
from tools import function_scenes


@pytest.fixture
def thread_too_short(qt_app: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    path = tmp_path / "gewinde_zu_kurz.p3d"
    save(function_scenes.build_scene("gewinde_zu_kurz.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(1920, 1080)
    window.show()
    window._show_start_screen(False)
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()
    yield window
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def test_changing_the_thread_step_waits_for_a_change(
    qt_app: QApplication, thread_too_short: MainWindow
) -> None:
    from app.ui.op_dialog import OperationDialog

    window = thread_too_short
    op_id = next(
        entry.id
        for entry in window.session.project.document.ops
        if entry.op == "insert_printed_thread"
    )
    window.edit_operation(op_id, "length")
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    try:
        assert window.session.wait_for_idle(60_000)
        qt_app.processEvents()
        button = dialog._accept_button
        assert button.text() == tr("Übernehmen")
        assert not button.isEnabled()
        waiting = tr("Erst „{field}“ ändern, dann übernehmen.", field=tr("Länge"))
        assert button.toolTip() == waiting
        assert button.accessibleDescription() == waiting

        dialog._editors["length"].set_value(6.0)
        wait_until(qt_app, lambda: button.toolTip() != waiting)
    finally:
        dialog.reject()


def test_the_step_that_stops_the_chain_says_why_at_once(
    qt_app: QApplication, thread_too_short: MainWindow
) -> None:
    """Der Schritt, an dem die Kette steht, wartet nicht: Seine Absage ist der Grund.

    Gegenstück zum Gewindeschritt (``wait_for_change`` in ``edit_operation``):
    Der Stift hält die Kette selbst an, sein Knopf trägt die Absage der
    Vorschau statt des Satzes zur ersten Änderung.
    """
    from app.ui.op_dialog import OperationDialog

    window = thread_too_short
    result = window.session.last_result
    op_id = next(
        entry.id for entry in window.session.project.document.ops if entry.op == "pin_for_bore"
    )
    assert result is not None and result.stopped_at == op_id, "Voraussetzung: der Stift hält an"
    window.edit_operation(op_id)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    try:
        assert window.session.wait_for_idle(60_000)
        button = dialog._accept_button
        wait_until(qt_app, lambda: bool(window._preview_reason))
        assert button.text() == tr("Übernehmen")
        assert not dialog._waits_for_change
        assert not button.isEnabled()
        assert button.toolTip() == window._preview_reason
        assert button.accessibleDescription() == window._preview_reason
    finally:
        dialog.reject()
