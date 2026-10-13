"""Ohne Freischaltung graut jeder Zugang zu einer ändernden Handlung mit Grund aus (FD-5, FD-26).

In der Demo und ohne Geräteaktivierung stand *Auf das Bett setzen* im
Prüfbericht bedienbar da, und der Klick endete im Meldungsfenster „Das hat so
nicht funktioniert“. Menü, Suche und Karte grauten aus; Prüfbericht,
Merkmalfenster, Kontextmenüs, Filamentwähler und der Operationsdialog fragten
den Zustand nicht, *Parameter anlegen …*, die Parameterleiste, *Bewegen*,
*Teilen* und die Maßgruppe im Bild auch nicht. Alle fragen jetzt
``app.ui.change_lock``, und dieser Test geht jeden Zugang ab — gesperrt in
beiden Zuständen, offen im Kontrollfall und wieder offen nach dem
Freischalten, ohne neue Wahl. Jeder graue Zugang nennt den Grund in Kurzhilfe
und zugänglicher Beschreibung (FD-27).

Die Fläche ist die kleinste, für die Solidon gebaut ist: 1920 × 1080 logisch.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from app.core import activation, guides
from app.core.activation import store
from app.core.errors import LicenceRequired
from app.core.scene.history import OperationDraft
from app.core.scene.project import save
from app.core.types import Parameter
from app.i18n import tr
from app.ui import change_lock
from app.ui.dialogs import ParameterDialog, licence_lock_line, show_error
from app.ui.guide_targets import menu_entries, menubar_entries
from app.ui.main_window import MainWindow
from app.ui.message_dialog import MessageDialog
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import wait_for_print_findings
from tools import function_scenes, function_setup

#: Die kleinste Arbeitsfläche (Festlegung Robert, Bauplan §19.3).
SMALLEST = (1920, 1080)

MESHES = Path(__file__).parent / "data" / "meshes"

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


def _catch_messages(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Jedes Meldungsfenster wird notiert statt gezeigt — beide Bauarten.

    Fehler kommen seit FD-21 im Hausstil (``MessageDialog``); wer nur
    ``QMessageBox`` abfängt, sieht sie nicht und hinge bei einem Rückfall im
    modalen ``exec`` (Durchsicht welle4 L6).
    """
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(box.text()) or 0)
    monkeypatch.setattr(MessageDialog, "exec", lambda dialog: shown.append(dialog.text()) or 0)
    return shown


def test_the_catch_sees_both_kinds_of_message(
    qt_app: QApplication, below_the_bed: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gegenprobe zu L6: Ein Fehler im Hausstil und ein ``QMessageBox`` landen beide im Fang."""
    shown = _catch_messages(monkeypatch)
    show_error(LicenceRequired(action=activation.CHANGE), below_the_bed)
    box = QMessageBox(below_the_bed)
    box.setText("Kasten")
    box.exec()
    box.deleteLater()
    assert len(shown) == 2 and shown[1] == "Kasten", shown
    assert "Lizenzschlüssel" in shown[0], shown


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
    shown = _catch_messages(monkeypatch)
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

    # Merkmalfenster an einer Fläche: Zeichnen und Übernehmen grau. Der Grund
    # steht **einmal** sichtbar im Reiter, unter dem Suchfeld (FD-32); das
    # Merkmalfenster trägt ihn an seinen grauen Elementen.
    entry = next(iter(window.session.last_result.scene.objects.values()))
    face = next(key for key, feature in entry.features.items() if feature.kind == "face")
    window.object_tree.select_feature(entry.id, face)
    qt_app.processEvents()
    panel = window.feature_panel
    assert panel._locked == reason
    lines = [
        label
        for label in window.feature_dock.findChildren(QLabel)
        if reason in label.text() and label.isVisibleTo(window.feature_dock)
    ]
    assert lines == [window.selection_operations._nothing], [line.text() for line in lines]
    assert panel._apply.toolTip() == reason and panel._apply.accessibleDescription() == reason
    drawing = [
        child
        for child in panel.findChildren(QPushButton)
        if child.text() in ("Hier zeichnen", "Loch oder Aussparung zeichnen …")
    ]
    assert len(drawing) == 2 and not any(child.isEnabled() for child in drawing)

    # Filament an der Fläche: eine Zuweisung ist ein Schritt.
    assert not window.quick_filament.picker.isEnabled()
    assert window.quick_filament.picker.toolTip() == reason
    # Das Lager liest nur und bleibt offen, wie der Menüeintrag (Durchsicht welle4 L5).
    assert window.quick_filament.inventory_button.isEnabled()

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


def _open_changes(window: MainWindow, reason: str) -> list[str]:
    """Jeder ändernde Fensterbefehl, der gesperrt offen steht oder seinen Grund nicht nennt.

    Was ändert, sagt ``change_lock`` unter dem Namen des Wortschatzes: die
    Menüleiste ohne die lesenden Menüs, die Aktionen am Fenster, die
    Werkzeugleiste ohne Neu, Öffnen und Speichern, jeder Treffer der Suche, die
    Umschalter der Werkzeugzeile und jedes Feld der Parameterleiste (FD-26).
    """
    found: list[str] = []

    def check(name: str, enabled: bool, said: str) -> None:
        if enabled or reason not in said:
            found.append(f"{name}: {'offen' if enabled else repr(said)}")

    changing = change_lock.changing_commands(window)
    assert len(changing) > 50, f"nur {len(changing)} ändernde Befehle — die Suche greift nicht"
    for action in changing:
        check(action.objectName() or action.text(), action.isEnabled(), action.toolTip())
    rows = {name for top in window.menuBar().actions() for name, _m, _a in menu_entries(top.menu())}
    assert "menubar.parameter_anlegen" in rows, "die Menüleiste wurde nicht gelesen"
    reading = {str(tr("Neues Projekt")), str(tr("Öffnen")), str(tr("Speichern"))}
    for action in window.toolbar.actions():
        if action.text() and action.text() not in reading:
            check(f"toolbar:{action.text()}", action.isEnabled(), action.toolTip())
    for key in window.window_commands():
        action = window._command_actions.get(key)
        if action in changing if action is not None else bool(change_lock.command_refusal(key)):
            usable, why = window._extra_availability(key)
            check(f"search:{key}", usable, why)
    for key, button in window.tools._buttons.items():
        if change_lock.command_refusal(f"tool.{key}"):
            check(f"tool:{key}", button.isEnabled(), button.accessibleDescription())
    for widget in window.parameters.findChildren(QWidget):
        if change_lock._is_input(widget):
            name = widget.objectName() or type(widget).__name__
            check(f"parameters:{name}", widget.isEnabled(), widget.accessibleDescription())
    return found


@pytest.mark.parametrize("state", LOCKED)
def test_no_window_command_that_changes_stays_open(
    qt_app: QApplication,
    below_the_bed: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
) -> None:
    """FD-26: *Parameter anlegen …* stand ohne Freischaltung offen und endete im Dialog.

    Das Fenster hielt die Aktion nicht fest, und keine Zeile in
    ``_update_actions`` kannte sie; ebenso *Modell aus dem Netz*, *Zeichnen*
    unter *Erzeugen*, *Zahlen an Maße binden*, die Parameterleiste und Alt+3 und
    Alt+7. Jetzt graut jeder Befehl, den ``change_lock`` nicht als lesend führt,
    und Lesendes bleibt offen.
    """
    window = below_the_bed
    # Ein Maß in der Leiste, solange es noch geht: Seine Zahl ist ein Schritt.
    assert window.session.add_parameter(Parameter(name="hoehe", value=8.0, unit="mm"))
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()
    assert window.parameters.findChildren(QAbstractSpinBox), "Voraussetzung: ein Zahlenfeld"
    reason = _set_licence(monkeypatch, state)
    window._update_actions()
    found = _open_changes(window, reason)
    assert found == [], "\n".join(found)

    rows = {name: action for name, _menus, action in menubar_entries(window)}
    for name in ("menubar.speichern", "menubar.einstellungen", "menubar.bausteinkatalog"):
        assert rows[name].isEnabled(), f"{name} liest nur und bleibt offen"
    assert window.tools.usable("measure") == (True, "")

    # Der Weg an der grauen Zeile vorbei: kein Dialog, der Satz in der Statuszeile.
    opened: list[Any] = []
    monkeypatch.setattr(ParameterDialog, "exec", lambda dialog: opened.append(dialog) or 0)
    window.action_add_parameter()
    assert opened == [], "der Dialog ging trotz Sperre auf"
    assert window.status_message.text() == reason
    # Alt+3 öffnet *Bewegen* nicht, sondern sagt den Grund.
    window.status_message.setText("")
    window.tools.press("transform")
    assert window.tools.active() is None
    assert window.status_message.text() == reason


def test_the_guard_sees_a_window_command_left_open(
    qt_app: QApplication, below_the_bed: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gegenprobe zu FD-26: Ohne die Sperre der Fensterbefehle meldet der Wächter die Zeile."""
    window = below_the_bed
    reason = _set_licence(monkeypatch, "sale_without_trial")
    monkeypatch.setattr(change_lock, "close_commands", lambda window: [])
    window._update_actions()
    found = _open_changes(window, reason)
    assert "menubar.parameter_anlegen: offen" in found, found


def test_after_activation_every_window_command_comes_back(
    qt_app: QApplication, below_the_bed: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kontrollfall zu FD-26: Freigeschaltet geht, was nur die Sperre grau hielt, mit Satz."""
    window = below_the_bed
    rows = {name: action for name, _menus, action in menubar_entries(window)}
    adding = rows["menubar.parameter_anlegen"]
    own = adding.toolTip()
    _set_licence(monkeypatch, "needs_activation")
    window._update_actions()
    assert not adding.isEnabled()
    assert not window.parameters.add_button.isEnabled()

    assert _set_licence(monkeypatch, "licensed") == ""
    window._update_actions()
    assert adding.isEnabled() and adding.toolTip() == own
    assert window.parameters.add_button.isEnabled()
    assert window.tools.usable("transform") == (True, "")


def test_a_finding_action_waiting_for_the_calculation_names_its_end(
    qt_app: QApplication, below_the_bed: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FD-27 und FD-30: Während der Rechnung las ein Bildschirmleser die Nebenfolge.

    Die graue Befundhandlung trägt den Sperrgrund in Kurzhilfe **und**
    Beschreibung, und der Satz sagt, dass die Sperre mit der Berechnung fällt.
    """
    window = below_the_bed
    _set_licence(monkeypatch, "licensed")
    window._update_actions()
    _choose_the_finding(window)
    window.report._show_running(True)
    qt_app.processEvents()
    try:
        button = _bed_button(window)
        waiting = change_lock.computing_refusal()
        assert not button.isEnabled()
        assert button.toolTip() == waiting
        assert button.accessibleDescription() == waiting
    finally:
        window.report._show_running(False)
        qt_app.processEvents()
    button = _bed_button(window)
    assert button.isEnabled() and button.accessibleDescription() != waiting


@pytest.fixture
def with_a_hole(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> Iterator[MainWindow]:
    """Eine Platte mit Bohrungen, die Bohrung gewählt und ihre Maße im Bild (freigeschaltet)."""
    from tests.render_fakes import RecordingRenderer

    _set_licence(monkeypatch, "licensed")
    window = MainWindow(Session(), UiSettings())
    window.resize(*SMALLEST)
    window.show()
    window._show_start_screen(False)
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(60_000)
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    window.object_tree.select_feature(object_id, hole)
    window.feature_panel._in_view.click()
    assert window.session.wait_for_idle(30_000)
    for _ in range(40):
        qt_app.processEvents()
    flow = window._quiet_placement
    assert flow is not None and flow.active and flow.measure_group is not None, "Voraussetzung"
    yield window
    assert window.session.wait_for_idle(60_000)
    window.wait_for_workers()
    window.hide()
    window.deleteLater()
    qt_app.processEvents()


def test_the_measure_group_says_what_comes_before_apply(
    qt_app: QApplication, with_a_hole: MainWindow
) -> None:
    """FD-31: *Übernehmen* der Maßgruppe war vor der ersten Eingabe grau ohne Grund.

    Der Satz nennt das erste Feld der Gruppe, wie der Kunde es liest, in
    Kurzhilfe und Beschreibung; nach der ersten Eingabe fällt er.
    """
    flow = with_a_hole._quiet_placement
    assert flow is not None and flow.measure_group is not None
    apply = flow._measure_accept
    first = next(
        widget
        for widget in flow.measure_group.findChildren(QAbstractSpinBox)
        if widget.accessibleName()
    )
    title = first.accessibleName().rsplit(" — ", 1)[-1]
    said = tr("Erst „{field}“ ändern, dann übernehmen.", field=title)
    assert not apply.isEnabled(), "Voraussetzung: vor der ersten Eingabe grau"
    assert apply.toolTip() == said and apply.accessibleDescription() == said
    QTest.keyClick(first.lineEdit(), Qt.Key.Key_End)
    qt_app.processEvents()
    assert flow.dialog.begun, "die Taste im Feld beginnt den Entwurf"
    assert said not in (apply.toolTip(), apply.accessibleDescription())


@pytest.mark.parametrize("state", LOCKED)
def test_the_measure_group_takes_no_input_without_a_licence(
    qt_app: QApplication, with_a_hole: MainWindow, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """FD-28: Die Maßgruppe nahm gesperrt Zahlen an; nur *Übernehmen* war grau.

    Eingang und Knopf sperren mit dem Satz aus ``change_lock``, der Satz steht
    sichtbar in der Gruppe und nennt die Menüzeile der Freischaltung; nach dem
    Freischalten nimmt sie wieder an.
    """
    window = with_a_hole
    flow = window._quiet_placement
    assert flow is not None
    group = flow.measure_group
    assert group is not None
    fields = [
        widget
        for widget in group.findChildren(QWidget)
        if change_lock._is_input(widget) and widget.isEnabled()
    ]
    assert fields, "die Maßgruppe trug kein offenes Feld — der Test prüfte nichts"

    reason = _set_licence(monkeypatch, state)
    window._update_actions()
    qt_app.processEvents()
    for field in fields:
        assert not field.isEnabled(), field.accessibleName()
        assert field.toolTip() == reason and field.accessibleDescription() == reason
    apply = flow._measure_accept
    assert not apply.isEnabled()
    assert apply.toolTip() == reason and apply.accessibleDescription() == reason
    assert reason in flow._measure_note.text() and not flow._measure_note.isHidden()
    assert "Solidon freischalten" in reason, "der Satz nennt den Weg (FD-30)"
    assert flow.dialog.blocked_reason == reason and not flow.dialog.can_accept()
    viewport = window.viewport
    assert viewport._gizmo is None and viewport._slot_handle is None, "kein Griff an der Bohrung"
    assert viewport._placement_grip_item is None, "kein Griff an der Maßgruppe"

    _set_licence(monkeypatch, "licensed")
    window._update_actions()
    qt_app.processEvents()
    still = [
        field.accessibleName() or type(field).__name__ for field in fields if not field.isEnabled()
    ]
    assert not still, f"nach dem Freischalten blieb gesperrt: {still}"
    assert all(field.toolTip() != reason for field in fields)


@pytest.mark.parametrize("state", LOCKED)
def test_the_keys_and_the_drag_in_the_history_say_why(
    qt_app: QApplication, below_the_bed: MainWindow, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """Durchsicht welle4 M1: Die Tasten des Verlaufs fragten die Freischaltung nicht.

    Das Kontextmenü war grau, aber Leertaste und Alt+Pfeil endeten im
    Meldungsfenster, Einfg öffnete die Einfügemarke und Entf stellte die
    Löschfrage. Jetzt sind die Tasten grau mit Grund, und jeder der fünf Wege —
    auch das Ablegen nach einem Zug — sagt den Grund in der Statuszeile und
    ändert nichts.
    """
    window = below_the_bed
    assert window.session.apply("Quader", [OperationDraft(op="create_box", params={})])
    assert window.session.wait_for_idle(60_000)
    qt_app.processEvents()
    shown = _catch_messages(monkeypatch)
    reason = _set_licence(monkeypatch, state)
    window._update_actions()
    history = window.history_panel
    keys = (
        history.remove_action,
        history.insert_action,
        history.up_action,
        history.down_action,
        history.toggle_action,
    )
    assert not any(action.isEnabled() for action in keys), "eine Taste des Verlaufs blieb offen"
    assert all(action.toolTip() == reason for action in keys)

    steps = [entry.id for entry in window.session.project.document.ops]
    last = steps[-1]
    for way in (
        lambda: history.suppressRequested.emit([last]),  # Leertaste
        lambda: history.moveRequested.emit([last], steps[0]),  # Alt+Pfeil und Ablegen
        lambda: history.insertRequested.emit(last),  # Einfg
        lambda: history.removalRequested.emit([last]),  # Entf
    ):
        window.status_message.setText("")
        way()
        assert window.session.wait_for_idle(60_000)
        qt_app.processEvents()
        assert window.status_message.text() == reason
    assert shown == [], f"ein Meldungsfenster kam doch: {shown}"
    assert [entry.id for entry in window.session.project.document.ops] == steps
    assert window.session.inserting is None, "die Einfügemarke ging trotz Sperre auf"
