"""Ohne Freischaltung graut jeder Zugang zu einer ändernden Handlung mit Grund aus (FD-5).

In der Demo und ohne Geräteaktivierung stand *Auf das Bett setzen* im
Prüfbericht bedienbar da, und der Klick endete im Meldungsfenster „Das hat so
nicht funktioniert“. Menü, Suche und Karte grauten aus; Prüfbericht,
Merkmalfenster, Kontextmenüs, Filamentwähler und der Operationsdialog fragten
den Zustand nicht. Alle fragen jetzt ``app.ui.change_lock``, und dieser Test
geht jeden Zugang ab — gesperrt in beiden Zuständen, offen im Kontrollfall und
wieder offen nach dem Freischalten, ohne neue Wahl.

Die Fläche ist die kleinste, für die Solidon gebaut ist: 1920 × 1080 logisch.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from app.core import activation, guides
from app.core.activation import store
from app.core.scene.project import save
from app.ui.dialogs import licence_lock_line
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import wait_for_print_findings
from tools import function_scenes, function_setup

#: Die kleinste Arbeitsfläche (Festlegung Robert, Bauplan §19.3).
SMALLEST = (1920, 1080)

#: Die zwei gesperrten Zustände aus Prüfpunkt 18 des Funktionsdurchgangs.
LOCKED = ("sale_without_trial", "needs_activation")


@pytest.fixture
def below_the_bed(qt_app: QApplication, tmp_path: Path) -> Iterator[MainWindow]:
    """Der Würfel halb unter dem Bett, gezeigt, mit dem Befund im Bericht."""
    path = tmp_path / "unter_dem_bett.p3d"
    save(function_scenes.build_scene("unter_dem_bett.netz"), path)
    window = MainWindow(Session(), UiSettings())
    window.resize(*SMALLEST)
    window.show()
    window._show_start_screen(False)
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    wait_for_print_findings(window)
    qt_app.processEvents()
    yield window
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def _set_licence(monkeypatch: pytest.MonkeyPatch, state: str) -> str:
    """Den Zustand über die Nahtstelle der Suite setzen; zurück kommt der Sperrgrund."""
    monkeypatch.setattr(store, "DEMO_UNTIL", None)
    if state == "sale_without_trial":
        monkeypatch.setattr(store, "TRIAL_FROM", None)
    cached = function_setup.licence_activation(state, date.today())
    assert getattr(cached, state), f"der Zustand {state} ließ sich nicht herstellen"
    monkeypatch.setattr(activation, "_cached", cached)
    return "" if cached.unlocked else licence_lock_line(cached)


def _choose_the_finding(window: MainWindow) -> QPushButton:
    """Reiter *Prüfbericht*, Liste auf, Befundzeile gewählt — die Knopfzeile darunter."""
    tabs = window.right
    tabs.setCurrentIndex(next(i for i in range(tabs.count()) if tabs.widget(i) is window.report))
    report = window.report
    if not report.list_toggle.isChecked():
        report.list_toggle.click()
    row = next(
        report.list.item(i)
        for i in range(report.list.count())
        if report.list.item(i).data(Qt.ItemDataRole.UserRole).code == "arrange.below_bed"
    )
    report.list.setCurrentItem(row)
    QApplication.processEvents()
    return _bed_button(window)


def _bed_button(window: MainWindow) -> QPushButton:
    return next(
        entry
        for entry in window.report.findChildren(QPushButton)
        if entry.property(guides.TARGET_PROPERTY) == "finding.action:place_on_bed"
        and entry.isVisibleTo(window.report)
    )


def _ops(window: MainWindow) -> list[str]:
    return [entry.op for entry in window.session.project.document.ops]


@pytest.mark.parametrize("state", LOCKED)
def test_every_offer_of_a_change_is_grey_with_its_reason(
    qt_app: QApplication,
    below_the_bed: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    window = below_the_bed
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(box.text()) or 0)
    reason = _set_licence(monkeypatch, state)
    assert reason
    # Wie nach dem Freischaltdialog: Das Fenster stellt seine Einträge neu.
    window._update_actions()

    # Prüfbericht: Knopf und Kontextmenü grau, der Grund am Knopf; der Klick tut nichts.
    button = _choose_the_finding(window)
    assert not button.isEnabled()
    assert button.toolTip() == reason and button.accessibleDescription() == reason
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert window.session.wait_for_idle(60_000)
    assert _ops(window) == ["load"] and not shown, "der graue Knopf führte ins Meldungsfenster"

    # Baum: *Objekt entfernen* grau mit Grund; *Ausblenden* liest nur und bleibt.
    body = next(iter(window.session.last_result.scene.objects))
    window.object_tree.select_object(body)
    menu = window.object_tree.context_menu()
    assert menu is not None
    entries = {action.objectName(): action for action in menu.actions() if action.objectName()}
    assert not entries["delete_object"].isEnabled()
    assert entries["delete_object"].toolTip() == reason
    assert any(action.isEnabled() for action in menu.actions() if not action.isSeparator()), (
        "Lesendes am Körper bleibt bedienbar"
    )
    menu.deleteLater()

    # Verlauf: jeder Eintrag ändert den Verlauf — alle grau, alle mit Grund.
    history = window.history_panel
    history_menu = history.context_menu(history.list.item(0))
    assert history_menu is not None
    steps = [action for action in history_menu.actions() if not action.isSeparator()]
    assert steps, "das Verlaufsmenü kam leer — der Test prüfte nichts"
    assert all(not action.isEnabled() and action.toolTip() == reason for action in steps)
    history_menu.deleteLater()

    # Merkmalfenster an einer Fläche: Grund als Zeile, Zeichnen und Übernehmen grau.
    entry = next(iter(window.session.last_result.scene.objects.values()))
    face = next(key for key, feature in entry.features.items() if feature.kind == "face")
    window.object_tree.select_feature(entry.id, face)
    qt_app.processEvents()
    panel = window.feature_panel
    assert panel._locked == reason
    assert panel._lock_note.text() == reason
    drawing = [
        child
        for child in panel.findChildren(QPushButton)
        if child.text() in ("Hier zeichnen", "Loch oder Aussparung zeichnen …")
    ]
    assert len(drawing) == 2 and not any(child.isEnabled() for child in drawing)

    # Filament an der Fläche: eine Zuweisung ist ein Schritt.
    assert not window.quick_filament.picker.isEnabled()
    assert window.quick_filament.picker.toolTip() == reason

    # Operationsdialog über den Verlauf: zum Ansehen offen, Übernehmen grau mit Grund.
    window.edit_operation(window.session.project.document.ops[0].id)
    qt_app.processEvents()
    dialog = window._op_dialog
    assert dialog is not None
    try:
        assert not dialog._accept_button.isEnabled()
        assert dialog._accept_button.toolTip() == reason
        assert not dialog.can_accept()
    finally:
        dialog.reject()
        qt_app.processEvents()
    assert not shown, f"ein Meldungsfenster kam doch: {shown}"


def test_after_activation_the_offers_come_back_without_a_new_choice(
    qt_app: QApplication, below_the_bed: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kontrollfall und Rückweg: freigeschaltet ist alles bedienbar, auch ohne neue Wahl."""
    window = below_the_bed
    _set_licence(monkeypatch, "needs_activation")
    window._update_actions()
    assert not _choose_the_finding(window).isEnabled()

    assert _set_licence(monkeypatch, "licensed") == ""
    window._update_actions()
    # Ein neues Kind eines sichtbaren Elternteils zeigt Qt in der nächsten Runde.
    qt_app.processEvents()
    button = _bed_button(window)
    assert button.isEnabled(), "nach dem Freischalten blieb die Befundhandlung grau"
    assert window.feature_panel._locked == ""
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert window.session.wait_for_idle(60_000)
    assert _ops(window) == ["load", "place_on_bed"]
