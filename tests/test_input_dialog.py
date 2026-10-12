"""Eingaben im Hausstil und Erfolge am Ort (FD-22, FD-24; Konzept Funktionsdurchgang Z2, Z5).

Die Wächter oben lesen den Quelltext und laufen ohne Fenster: Im Kundenweg baut
nichts mehr ein ``QInputDialog`` oder ``QColorDialog``, ein Erfolg oder Hinweis
erscheint nicht als Meldungsfenster, und die Funktionsliste findet die neuen
Eingabefenster unter ihrem alten Kennzeichen. Die Tests darunter bauen die
Fenster und sind Fenstertests.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
UI = APP / "ui"

#: Die rohen Qt-Fenster für Eingabe und Farbe, die es im Kundenweg nicht mehr gibt.
RAW_INPUTS = frozenset({"QInputDialog", "QColorDialog"})

#: Wofür ``inform`` noch steht: ein Scheitern mit Rückweg, kein Erfolg und kein
#: Hinweis (Z2). Ein neuer Aufruf kommt hierher nur mit diesem Grund.
FAILURES_THAT_INFORM = frozenset({"message:browser_failed"})

#: Die acht Stellen aus FD-22 — Funktion und Kennzeichen, unter dem die
#: Funktionsliste sie weiter als Eingabefenster führt.
INPUT_WINDOWS = {
    "_pick_colour": "message:filament_colour",
    "_replacement_slot": "message:filament_slot",
    "_choose": "message:print_colour",
    "_choose_address": "message:service_address",
    "action_import_url": "message:model_address",
    "_assign_inventory_spool": "message:inventory_spool",
    "action_counterpart": "message:thread_counterpart",
    "change_constraint_value": "message:constraint_value",
}


def raw_inputs(root: Path) -> list[str]:
    """Jede Stelle unter ``root``, die ``QInputDialog`` oder ``QColorDialog`` nennt —
    Import, Aufruf, Unterklasse oder Typprüfung."""
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        where = path.relative_to(root).as_posix()
        for node in ast.walk(tree):
            named = ""
            if isinstance(node, ast.Name):
                named = node.id
            elif isinstance(node, ast.Attribute):
                named = node.attr
            elif isinstance(node, ast.alias):
                named = node.name
            if named in RAW_INPUTS:
                found.append(f"{where}:{getattr(node, 'lineno', 0)} {named}")
    return found


def test_no_raw_input_or_colour_window_in_the_app() -> None:
    """FD-22: Eingabe- und Farbfragen stehen im Hausstil oder am Ort, nie als
    Systemfenster — der Farbdialog von Windows, ein Textfeld mit *OK* und *Cancel*."""
    found = raw_inputs(APP)
    assert not found, "rohe Eingabe- oder Farbfenster:\n" + "\n".join(found)


def test_the_input_guard_sees_every_raw_form(tmp_path: Path) -> None:
    """Gegenprobe: Aufruf, Import, Unterklasse und Typprüfung werden gefunden."""
    (tmp_path / "probe.py").write_text(
        "from PySide6.QtWidgets import QColorDialog\n"
        "def ask(parent):\n"
        "    return QtWidgets.QInputDialog.getText(parent, 'a', 'b')\n"
        "class Own(QColorDialog):\n"
        "    pass\n"
        "def seen(widget):\n"
        "    return isinstance(widget, QInputDialog)\n",
        encoding="utf-8",
    )
    found = raw_inputs(tmp_path)
    lines = sorted(int(entry.split(":")[1].split()[0]) for entry in found)
    assert lines == [1, 3, 4, 7], found


def informed_targets(root: Path) -> list[str]:
    """Das Kennzeichen jedes ``inform(…)`` unter ``root`` — leer, wenn keines steht."""
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "message_dialog.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "inform":
                given = [word.value for word in node.keywords if word.arg == "target"]
                target = given[0] if given else None
                found.append(
                    str(target.value)
                    if isinstance(target, ast.Constant)
                    else f"{path.name}:{node.lineno}"
                )
    return found


def test_a_success_is_never_a_message_window() -> None:
    """FD-24, Z2: „Erfolg und Hinweis erscheinen nie als Meldungsfenster.“

    Freischaltung online und offline, Abmelden, gespeicherte Anfrage, der
    nicht abgelegte Schlüssel und die nicht geöffnete Seite standen als
    modales Fenster da. Sie quittieren jetzt im Dialog (``acknowledge``);
    ``inform`` bleibt für ein Scheitern mit Rückweg.
    """
    found = informed_targets(UI)
    assert found, "die Suche nach inform greift nicht"
    assert sorted(set(found) - FAILURES_THAT_INFORM) == []


def test_the_success_guard_sees_an_informed_success(tmp_path: Path) -> None:
    """Gegenprobe: ein Erfolg über ``inform`` und einer ohne Kennzeichen fallen auf."""
    (tmp_path / "probe.py").write_text(
        "def done(parent):\n"
        "    inform(parent, 'a', 'b', target='message:activated_online')\n"
        "def plain(parent):\n"
        "    inform(parent, 'a', 'b')\n"
        "def failed(parent):\n"
        "    inform(parent, 'a', 'b', target='message:browser_failed')\n",
        encoding="utf-8",
    )
    found = informed_targets(tmp_path)
    assert sorted(set(found) - FAILURES_THAT_INFORM) == ["message:activated_online", "probe.py:4"]


def test_every_input_window_keeps_its_row_and_target() -> None:
    """Die Funktionsliste führt die acht Stellen weiter als Eingabefenster, unter dem
    Kennzeichen, das sie als rohe Fenster trugen (``function_scan.MESSAGE_BUILDERS``)."""
    from tools import function_list as fl
    from tools import function_scan as fscan

    scan = fscan.scan_ui(fl.ui_sources())
    assert {name: scan.raw_targets.get(name) for name in INPUT_WINDOWS} == INPUT_WINDOWS
    assert set(INPUT_WINDOWS) <= set(fl.RAW_WINDOW_PACKAGES)
    assert "InputDialog" in scan.classes


# --- Fenster ----------------------------------------------------------------------


def modals_while(call: Callable[[], object]) -> list[str]:
    """Welche modalen Fenster aufgehen, während ``call`` läuft — jedes wird sofort
    verworfen, damit ein alter Stand rot wird, statt die Suite anzuhalten."""
    seen: list[str] = []

    def look() -> None:
        modal = QApplication.activeModalWidget()
        if modal is not None:
            seen.append(type(modal).__name__)
            if isinstance(modal, QDialog):
                modal.reject()
            else:
                modal.close()

    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(look)
    timer.start()
    try:
        call()
    finally:
        timer.stop()
    return seen


def focused(widget: Any) -> bool:
    """Ob ``widget`` den Fokus seines Fensters trägt — offscreen ist kein Fenster aktiv."""
    return bool(widget.hasFocus() or widget.window().focusWidget() is widget)


def _show(widget: Any, qt_app: QApplication) -> None:
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    widget.show()
    widget.activateWindow()
    qt_app.processEvents()


def test_the_input_dialog_wears_the_house_style(qt_app: QApplication) -> None:
    """Titel, Satz, Feld mit Fokus, ein Hauptknopf, *Abbrechen*; Enter nimmt,
    Escape bricht ab, Tab geht vom Feld zu den Knöpfen."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QInputDialog as Raw

    from app.core import guides
    from app.ui.input_dialog import InputDialog

    dialog = InputDialog(
        None,
        title="Modell aus dem Netz",
        sentence="Adresse der Modelldatei oder Modellseite:",
        target="message:model_address",
        accept="Herunterladen",
        text="https://example.org/a.stl",
    )
    try:
        _show(dialog, qt_app)
        assert not isinstance(dialog, Raw)
        assert dialog.property(guides.TARGET_PROPERTY) == "message:model_address"
        assert dialog.headline.text() == "Modell aus dem Netz"
        assert not dialog.symbol.isVisible(), "eine Frage trägt kein Symbol der Schwere"
        assert focused(dialog.field) and dialog.field.selectedText() == dialog.field.text()
        lead, cancel = dialog.buttons()
        assert lead.isDefault() and lead.font().bold(), "ein Hauptknopf, halbfett"
        assert not cancel.isDefault()
        assert lead.property(guides.TARGET_PROPERTY) == "message.button:model_address.accept"
        assert cancel.property(guides.TARGET_PROPERTY) == "message.button:model_address.cancel"
        order = [dialog.field]
        for _step in range(2):
            QTest.keyClick(dialog.focusWidget(), Qt.Key.Key_Tab)
            order.append(dialog.focusWidget())
        assert set(order[1:]) == {lead, cancel}, "Tab geht vom Feld zu beiden Knöpfen"
        dialog.field.setFocus()
        QTest.keyClick(dialog.field, Qt.Key.Key_Return)
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert dialog.clicked_button() is lead
    finally:
        dialog.deleteLater()


def test_escape_cancels_the_input_dialog(qt_app: QApplication) -> None:
    from PySide6.QtTest import QTest

    from app.ui.input_dialog import InputDialog

    dialog = InputDialog(
        None, title="Titel", sentence="Satz", target="message:sample", accept="Nehmen"
    )
    try:
        _show(dialog, qt_app)
        QTest.keyClick(dialog.field, Qt.Key.Key_Escape)
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert dialog.clicked_button() is None
    finally:
        dialog.deleteLater()


def test_a_refused_entry_keeps_the_dialog_open_with_its_reason(qt_app: QApplication) -> None:
    """Die Dienstadresse: Ein Ordner wird nicht genommen, der Grund steht unter dem
    Feld, die Eingabe bleibt stehen — derselbe Dialog, kein zweites Fenster."""
    from PySide6.QtTest import QTest

    from app.ui.input_dialog import InputDialog
    from app.ui.install_dialog import address_problem

    folder = r"C:\Users\Jemand\.ollama\models"
    dialog = InputDialog(
        None,
        title="Ollama",
        sentence="Adresse",
        target="message:service_address",
        accept="Übernehmen",
        text=folder,
        check=address_problem,
    )
    try:
        _show(dialog, qt_app)
        QTest.keyClick(dialog.field, Qt.Key.Key_Return)
        qt_app.processEvents()
        assert dialog.isVisible() and dialog.result() != QDialog.DialogCode.Accepted
        assert dialog.problem.isVisible() and "Ordner" in dialog.problem.text()
        assert dialog.field.text() == folder
        dialog.field.setText("http://localhost:11434")
        QTest.keyClick(dialog.field, Qt.Key.Key_Return)
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.deleteLater()


def test_a_choice_is_the_rule_21_question_with_its_title_and_name(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Wahl unter Gleichwertigem ist ``AskDialog`` — mit dem Titel der Sache, dem
    Kennzeichen im Wortschatz und dem Farbpunkt je Filament."""
    from PySide6.QtGui import QIcon, QPixmap

    from app.core import guides
    from app.ui import dialogs
    from app.ui.input_dialog import ask_choice

    seen: dict[str, Any] = {}

    def answer(dialog: dialogs.AskDialog) -> int:
        seen["title"] = dialog.windowTitle()
        seen["target"] = dialog.property(guides.TARGET_PROPERTY)
        seen["icons"] = [not dialog.list.item(row).icon().isNull() for row in range(2)]
        dialog.list.setCurrentRow(1)
        return int(QDialog.DialogCode.Accepted.value)

    monkeypatch.setattr(dialogs.AskDialog, "exec", answer)
    pixmap = QPixmap(8, 8)
    pixmap.fill(Qt.GlobalColor.red)
    chosen = ask_choice(
        None,
        title="Filament ersetzen",
        question="Welches?",
        choices=["1 — PLA", "2 — PETG"],
        target="message:filament_slot",
        icons=[QIcon(pixmap), QIcon(pixmap)],
    )
    assert chosen == 1
    assert seen == {
        "title": "Filament ersetzen",
        "target": "message:filament_slot",
        "icons": [True, True],
    }
    monkeypatch.setattr(dialogs.AskDialog, "exec", lambda _dialog: 0)
    assert ask_choice(None, title="t", question="q", choices=["a"], target="message:x") is None


def test_the_colour_chooser_stands_at_the_button_and_names_every_colour(
    qt_app: QApplication,
) -> None:
    """FD-22: Die Farbe der Spule wählt der eigene Farbwähler unter dem Knopf, nicht
    der Farbdialog des Systems — ohne modales Fenster, jede Farbe mit eigenem Namen."""
    from app.core import guides
    from app.ui.filament_picker import NewFilamentDialog
    from app.ui.place_popup import ColourPopup

    dialog = NewFilamentDialog(name="Probe", colour="#ff0000")
    try:
        _show(dialog, qt_app)
        button = dialog.colour_buttons[0]
        assert modals_while(button.click) == [], "kein modales Fenster beim Farbwählen"
        popup = QApplication.activePopupWidget()
        assert isinstance(popup, ColourPopup)
        assert popup.property(guides.TARGET_PROPERTY) == "message:filament_colour"
        below = button.mapToGlobal(button.rect().bottomLeft())
        assert abs(popup.geometry().top() - below.y()) <= 2, "der Wähler steht am Knopf"
        names = [swatch.accessibleName() for line in popup.swatches for swatch in line]
        assert len(names) == 27 and len(set(names)) == 27, names
        assert all(names), "jede Farbe trägt ihren Namen (Regel 18)"
        chosen = popup.swatches[1][5]
        chosen.click()
        qt_app.processEvents()
        assert dialog._colours[0] == chosen.colour
        assert button.text() == chosen.colour
        assert QApplication.activePopupWidget() is None, "die Wahl schließt den Wähler"
    finally:
        dialog.deleteLater()


def test_the_colour_chooser_takes_a_typed_value_and_the_keyboard(
    qt_app: QApplication,
) -> None:
    """Sechs Hexstellen, Enter nimmt sie; *Übernehmen* sagt, warum es ruht;
    Pfeiltasten gehen durch die Felder, Escape nimmt nichts."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget

    from app.ui.place_popup import ColourPopup

    host = QWidget()
    taken: list[str] = []
    try:
        _show(host, qt_app)
        popup = ColourPopup(host, title="Filamentfarbe", current="#123456", target="message:x")
        popup.chosen.connect(taken.append)
        popup.place_below(host)
        popup.start()
        qt_app.processEvents()
        assert focused(popup.field), "eine eigene Farbe beginnt im Farbwert"
        popup.field.setText("#12")
        assert not popup.take.isEnabled() and "Sechs Stellen" in popup.take.toolTip()
        popup.field.setText("ff8800")
        assert popup.take.isEnabled() and popup.take.toolTip() == ""
        QTest.keyClick(popup.field, Qt.Key.Key_Return)
        assert taken == ["#ff8800"]

        second = ColourPopup(host, title="Filamentfarbe", current="", target="message:x")
        second.chosen.connect(taken.append)
        second.place_below(host)
        second.start()
        qt_app.processEvents()
        start = second.swatches[1][0]
        assert focused(start), "ohne gewählte Regalfarbe beginnt die kräftige Reihe"
        QTest.keyClick(start, Qt.Key.Key_Right)
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Down)
        assert QApplication.focusWidget() is second.swatches[2][1]
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
        assert taken[-1] == second.swatches[2][1].colour

        third = ColourPopup(host, title="Filamentfarbe", current="#000000", target="message:x")
        third.chosen.connect(taken.append)
        third.place_below(host)
        third.start()
        qt_app.processEvents()
        QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
        qt_app.processEvents()
        assert len(taken) == 2, "Escape nimmt keine Farbe"
        assert sip_deleted(third) or not third.isVisible()
    finally:
        host.deleteLater()


def sip_deleted(widget: Any) -> bool:
    """Ob das Qt-Objekt hinter ``widget`` schon weg ist (``WA_DeleteOnClose``)."""
    from shiboken6 import isValid

    return not isValid(widget)


def test_the_print_colour_button_chooses_in_place_and_reports(qt_app: QApplication) -> None:
    """Der Farbknopf des Druckdialogs: Wähler am Knopf, danach steht der Wert, dann
    meldet der Knopf ihn — dieselbe Folge wie vorher, ohne Systemfenster."""
    from app.ui.place_popup import ColourPopup
    from app.ui.print_settings_dialog import _ColourButton

    button = _ColourButton("#3fae6b")
    reported: list[str] = []
    button.changed.connect(lambda value: reported.append(f"{value}/{button.value()}"))
    try:
        _show(button, qt_app)
        assert modals_while(button.click) == []
        popup = QApplication.activePopupWidget()
        assert isinstance(popup, ColourPopup)
        popup.field.setText("#4A90D9")
        popup.take.click()
        assert reported == ["#4a90d9/#4a90d9"]
        assert button.value() == "#4a90d9"
    finally:
        button.deleteLater()


def test_a_measure_changes_in_a_field_at_its_place(qt_app: QApplication) -> None:
    """FD-22: *Maß ändern* öffnet ein Feld am Ort statt eines Systemfensters; Enter setzt
    das Maß als ein Schritt, Escape lässt es stehen."""
    from PySide6.QtTest import QTest

    from app.core import guides
    from app.ui.place_popup import ValuePopup
    from app.ui.sketch_editor import SketchPanel

    panel = SketchPanel()
    try:
        _show(panel, qt_app)
        canvas = panel.canvas
        canvas.add_element("line", ((0.0, 0.0), (30.0, 0.0)))
        canvas.add_constraint("distance", (0, 1), "30")
        assert modals_while(lambda: panel.change_constraint_value(0)) == []
        popup = QApplication.activePopupWidget()
        assert isinstance(popup, ValuePopup)
        assert popup.property(guides.TARGET_PROPERTY) == "message:constraint_value"
        assert popup.field.text() == "30" and focused(popup.field)
        assert "breite/2" in popup.field.accessibleDescription()
        popup.field.setText("45")
        QTest.keyClick(popup.field, Qt.Key.Key_Return)
        assert canvas.sketch.constraints[0].value == "45"

        panel.change_constraint_value(0)
        second = QApplication.activePopupWidget()
        assert isinstance(second, ValuePopup)
        second.field.setText("")
        assert not second.take.isEnabled() and second.take.toolTip()
        QTest.keyClick(second.field, Qt.Key.Key_Escape)
        assert canvas.sketch.constraints[0].value == "45"
    finally:
        panel.deleteLater()


# --- FD-24: Erfolge am Ort --------------------------------------------------------


@pytest.fixture
def licence_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from app.core import activation
    from app.core.activation import store

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    activation.forget_cache()
    yield tmp_path
    activation.forget_cache()


def test_online_activation_acknowledges_in_the_dialog(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, licence_home: Path
) -> None:
    """FD-24: Nach der Freischaltung kein modales Fenster — die Quittung steht im
    Dialog, und *Schließen* ist der nächste Schritt, mit Akzent und Fokus."""
    from app.core import activation
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(activation, "install_certificate", lambda _answer: None)
    dialog = ActivationDialog()
    try:
        _show(dialog, qt_app)
        assert modals_while(lambda: dialog._online_completed("{}")) == []
        assert dialog.receipt.isVisible()
        assert "freigeschaltet" in dialog.receipt.text()
        assert dialog.close_button.isDefault() and focused(dialog.close_button)
        assert not dialog.online_button.isDefault(), "ein Akzentknopf je Fenster"
        assert "freigeschaltet" in dialog.close_button.accessibleDescription()
    finally:
        dialog.deleteLater()


def test_offline_activation_acknowledges_after_the_answer(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, licence_home: Path
) -> None:
    """Die eingelesene Antwort schließt den Dateiweg ohne Fenster dazwischen; die
    Quittung steht im Freischaltdialog, zu dem es zurückgeht."""
    from app.core import activation
    from app.ui import dialogs

    answer = licence_home / "antwort.solidon-activation"
    answer.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(activation, "install_certificate", lambda _answer: None)
    monkeypatch.setattr(
        dialogs.QFileDialog, "getOpenFileName", staticmethod(lambda *_a, **_k: (str(answer), ""))
    )
    offline = dialogs.OfflineActivationDialog("{}")
    try:
        assert modals_while(offline._import_answer) == []
        assert offline.result() == QDialog.DialogCode.Accepted
    finally:
        offline.deleteLater()

    monkeypatch.setattr(dialogs.OfflineActivationDialog, "exec", lambda _self: 1)
    dialog = dialogs.ActivationDialog()
    monkeypatch.setattr(dialog, "_activation_request", lambda: "{}")
    try:
        _show(dialog, qt_app)
        dialog._activate_offline()
        assert dialog.receipt.isVisible() and "freigeschaltet" in dialog.receipt.text()
        assert dialog.close_button.isDefault()
    finally:
        dialog.deleteLater()


def test_a_saved_request_names_the_next_step(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, licence_home: Path
) -> None:
    """Gespeichert steht unter Schritt 1, und Schritt 2 wird Hauptknopf mit Fokus."""
    from app.ui import dialogs
    from app.ui.style import DialogScrollArea, _hidden_height

    target = licence_home / "anfrage.solidon-request"
    monkeypatch.setattr(
        dialogs.QFileDialog, "getSaveFileName", staticmethod(lambda *_a, **_k: (str(target), ""))
    )
    dialog = dialogs.OfflineActivationDialog("{}")
    try:
        _show(dialog, qt_app)
        assert modals_while(dialog._save_request) == []
        assert target.read_text(encoding="utf-8") == "{}"
        assert dialog.receipt.isVisible() and "gespeichert" in dialog.receipt.text()
        assert dialog.page_button.isDefault() and focused(dialog.page_button)
        # Der Dialog wächst um die Quittung; Schritt 3 rutscht nicht unter den Rand.
        for _round in range(5):
            qt_app.processEvents()
        assert _hidden_height(dialog.findChild(DialogScrollArea)) == 0
    finally:
        dialog.deleteLater()


def test_a_page_that_did_not_open_says_so_in_the_dialog(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ui import dialogs

    monkeypatch.setattr(dialogs.QDesktopServices, "openUrl", staticmethod(lambda _url: False))
    dialog = dialogs.OfflineActivationDialog("{}")
    try:
        _show(dialog, qt_app)
        assert modals_while(dialog._open_page) == []
        assert dialog.receipt.isVisible() and "kopiert" in dialog.receipt.text()
        assert QApplication.clipboard().text() == dialog.PAGE_URL
    finally:
        dialog.deleteLater()


def test_deactivation_acknowledges_in_the_dialog(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, licence_home: Path
) -> None:
    from app.core import activation
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(activation, "forget_key", lambda: True)
    monkeypatch.setattr(activation, "clear_pending_deactivation", lambda: True)
    dialog = ActivationDialog()
    try:
        _show(dialog, qt_app)
        assert modals_while(dialog._deactivation_completed) == []
        assert dialog.receipt.isVisible() and "deaktiviert" in dialog.receipt.text()
        assert dialog.close_button.isDefault() and focused(dialog.close_button)
    finally:
        dialog.deleteLater()
