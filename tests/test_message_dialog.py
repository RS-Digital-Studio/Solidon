"""Meldungen im Hausstil statt roher Systemfenster (FD-21, Konzept Funktionsdurchgang Z5).

Der Wächter oben liest den Quelltext und läuft ohne Fenster: Ein ``QMessageBox``
bleibt nur für Fragen (Speicherfrage, Nachfragen nach Regel 19), eine Meldung
geht über ``app.ui.message_dialog``. Die Tests darunter bauen den Dialog und
sind Fenstertests.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

UI = Path(__file__).resolve().parent.parent / "app" / "ui"

#: Die statischen Meldungsfenster von Qt — jedes ist eine Meldung, keine Frage.
MESSAGE_FACTORIES = frozenset({"information", "warning", "critical", "about"})

#: Die Fragen, die ein ``QMessageBox`` bleiben dürfen — die Ausnahmen aus Z2 und
#: ``fenster.md``, „Rückfragen“: Speicherfrage, Löschen im Verlauf, verworfene
#: Schritte, Weitergehen trotz Befunden vor Export und Übergabe, Schließen der
#: Erzeugung mit Ergebnissen, Wiederherstellung. Eine neue Frage kommt hierher,
#: eine Meldung geht über ``app.ui.message_dialog``.
QUESTIONS = frozenset(
    {
        "confirm_unsaved",
        "confirm_discard",
        "remove_history_operations",
        "_go_on_despite",
        "confirm_generation_loss",
        "_ask_recovery",
    }
)


def _message_boxes_that_only_inform() -> list[str]:
    """Jede Stelle unter ``app/ui``, die ein ``QMessageBox`` als Meldung baut.

    Eine Meldung ist ein statischer Aufruf (``QMessageBox.information``), eine
    Unterklasse von ``QMessageBox`` oder ein ``QMessageBox(…)`` außerhalb der
    benannten Fragen (:data:`QUESTIONS`).
    """
    found: list[str] = []
    for path in sorted(UI.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        where = path.relative_to(UI).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and any(
                isinstance(base, ast.Name) and base.id == "QMessageBox" for base in node.bases
            ):
                found.append(f"{where}:{node.name}:{node.lineno} Unterklasse von QMessageBox")
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                if isinstance(call.func, ast.Name) and call.func.id == "QMessageBox":
                    if node.name not in QUESTIONS:
                        found.append(f"{where}:{node.name}:{call.lineno} QMessageBox als Meldung")
                elif (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "QMessageBox"
                    and call.func.attr in MESSAGE_FACTORIES
                ):
                    found.append(f"{where}:{node.name}:{call.lineno} QMessageBox.{call.func.attr}")
    return found


def test_a_message_is_never_a_raw_message_box() -> None:
    """Eine Meldung — Fehler, Einzelheiten, Hinweis — steht im Hausstil (FD-21).

    Jede Fehlermeldung eines ``AppError`` stand als ``QMessageBox`` mit dem
    Warndreieck des Systems da, dazu die Einzelheiten, das Protokoll des
    Slicers, der Browser-Ausfall, das Ende der Demo und die Hinweise der
    Freischaltung. Fragen bleiben, was sie sind (Konzept Funktionsdurchgang Z2).
    """
    found = _message_boxes_that_only_inform()
    assert not found, "Meldungen als rohes Systemfenster:\n" + "\n".join(found)


def test_the_guard_sees_a_message_box_that_only_informs(tmp_path: Path, monkeypatch) -> None:
    """Gegenprobe: Der Wächter findet alle drei Bauarten, eine benannte Frage lässt er stehen."""
    (tmp_path / "probe.py").write_text(
        "def tell(parent):\n"
        "    QMessageBox.information(parent, 'a', 'b')\n"
        "def shown(parent):\n"
        "    box = QMessageBox(parent)\n"
        "class Own(QMessageBox):\n"
        "    pass\n"
        "def confirm_unsaved(parent):\n"
        "    box = QMessageBox(parent)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "UI", tmp_path, raising=True)
    found = _message_boxes_that_only_inform()
    assert sorted(entry.split(":")[1] for entry in found) == ["Own", "shown", "tell"], found


def _message_dialogs_left_standing() -> list[str]:
    """Jede Meldung im Hausstil unter ``app/ui``, die nach ``exec`` am Elternteil liegen bleibt.

    ``exec`` gibt den Dialog nicht frei: Ohne ``deleteLater`` im ``finally`` hängt
    nach jeder Meldung ein verborgener Dialog mehr am Fenster (A-L1), wie es
    ``ask_text`` vormacht. Gesucht wird ``x = MessageDialog(…)`` oder eine
    Unterklasse samt ``x.exec()``, und ``MessageDialog(…).exec()`` ohne Namen.
    """
    trees = {path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted(UI.rglob("*.py"))}
    builders = {"MessageDialog"} | {
        node.name
        for tree in trees.values()
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id == "MessageDialog" for base in node.bases)
    }

    def built(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in builders
        )

    found: list[str] = []
    for path, tree in trees.items():
        where = path.relative_to(UI).as_posix()
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = {
                node.targets[0].id
                for node in ast.walk(function)
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and built(node.value)
            }
            freed = {
                (call.func.value.id, run.lineno)
                for guard in ast.walk(function)
                if isinstance(guard, ast.Try)
                for done in guard.finalbody
                for call in ast.walk(done)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "deleteLater"
                and isinstance(call.func.value, ast.Name)
                for statement in guard.body
                for run in ast.walk(statement)
                if isinstance(run, ast.Call)
                and isinstance(run.func, ast.Attribute)
                and run.func.attr == "exec"
            }
            for call in ast.walk(function):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
                    continue
                if call.func.attr != "exec":
                    continue
                if built(call.func.value):
                    found.append(f"{where}:{function.name}:{call.lineno} exec ohne Namen")
                elif (
                    isinstance(call.func.value, ast.Name)
                    and call.func.value.id in names
                    and (call.func.value.id, call.lineno) not in freed
                ):
                    found.append(f"{where}:{function.name}:{call.lineno} ohne deleteLater")
    return found


def test_a_message_is_freed_after_exec() -> None:
    """Jede Meldung im Hausstil gibt sich nach ``exec`` frei (A-L1)."""
    found = _message_dialogs_left_standing()
    assert not found, "Meldungen, die am Elternteil liegen bleiben:\n" + "\n".join(found)


def test_the_guard_sees_a_message_left_standing(tmp_path: Path, monkeypatch) -> None:
    """Gegenprobe: ohne Namen, ohne ``finally`` und eine Unterklasse fallen auf."""
    (tmp_path / "probe.py").write_text(
        "class Own(MessageDialog):\n"
        "    pass\n"
        "def bare(parent):\n"
        "    MessageDialog(parent).exec()\n"
        "def kept(parent):\n"
        "    box = Own(parent)\n"
        "    box.exec()\n"
        "def freed(parent):\n"
        "    box = MessageDialog(parent)\n"
        "    try:\n"
        "        box.exec()\n"
        "    finally:\n"
        "        box.deleteLater()\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "UI", tmp_path, raising=True)
    found = _message_dialogs_left_standing()
    assert sorted(entry.split(":")[1] for entry in found) == ["bare", "kept"], found


def _caught(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Fängt jeden Meldungsdialog vor ``exec`` und gibt die Liste zurück."""
    from app.ui.message_dialog import MessageDialog

    caught: list[Any] = []
    monkeypatch.setattr(MessageDialog, "exec", lambda dialog: caught.append(dialog) or 0)
    return caught


def test_the_error_dialog_wears_the_house_style(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Symbol aus dem eigenen Satz, Klartext, ein Hauptknopf, Ziele im Wortschatz (FD-21)."""
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QLabel, QMessageBox

    from app.core import guides
    from app.core.errors import CHOOSE_PRINTER, SCALE_TO_FIT, AppError
    from app.ui.dialogs import show_error
    from app.ui.message_dialog import SYMBOL_SIZE

    caught = _caught(monkeypatch)
    error = AppError(
        title="<b>Platte</b> zu klein",
        detail="Das Teil misst 300 mm.",
        suggestions=(SCALE_TO_FIT, CHOOSE_PRINTER),
    )
    show_error(error, handlers={SCALE_TO_FIT.id: lambda _e: None, CHOOSE_PRINTER.id: print})
    (dialog,) = caught
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    dialog.show()
    try:
        qt_app.processEvents()
        assert not isinstance(dialog, QMessageBox)
        assert dialog.property(guides.TARGET_PROPERTY) == "message:error"
        assert not dialog.symbol.pixmap().isNull()
        assert dialog.symbol.pixmap().deviceIndependentSize().width() == SYMBOL_SIZE
        assert dialog.symbol.accessibleName()
        assert dialog.headline.text() == "<b>Platte</b> zu klein"
        assert "300 mm" in dialog.body.text()
        assert all(
            label.textFormat() == Qt.TextFormat.PlainText
            for label in (dialog.headline, dialog.body)
        )
        names = [button.property(guides.TARGET_PROPERTY) for button in dialog.buttons()]
        assert names == [
            f"message.button:error.{SCALE_TO_FIT.id}",
            f"message.button:error.{CHOOSE_PRINTER.id}",
            "message.button:error.cancel",
        ]
        leading = [button for button in dialog.buttons() if button.isDefault()]
        assert [button.text() for button in leading] == [str(SCALE_TO_FIT.label)]
        assert leading[0].font().weight() >= QFont.Weight.DemiBold
        assert dialog.findChildren(QLabel)
    finally:
        dialog.hide()
        dialog.deleteLater()


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Escape])
def test_the_keyboard_answers_the_error_dialog(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, key: Qt.Key
) -> None:
    """Enter löst den Hauptknopf aus, Escape schließt ohne Handlung, Tab geht die Knöpfe ab."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton

    from app.core.errors import CANCEL, CHOOSE_PRINTER, SCALE_TO_FIT, AppError
    from app.ui.dialogs import show_error
    from app.ui.message_dialog import MessageDialog

    order: list[str] = []

    def answer(dialog: MessageDialog) -> int:
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        dialog.show()
        qt_app.processEvents()
        for _ in dialog.buttons():
            focused = dialog.focusWidget()
            order.append(focused.text() if isinstance(focused, QPushButton) else "")
            dialog.focusNextChild()
        dialog.buttons()[0].setFocus()
        QTest.keyClick(dialog, key)
        qt_app.processEvents()
        return dialog.result()

    monkeypatch.setattr(MessageDialog, "exec", answer)
    done: list[str] = []
    chosen = show_error(
        AppError(title="Probe", detail="x", suggestions=(SCALE_TO_FIT, CHOOSE_PRINTER)),
        handlers={
            SCALE_TO_FIT.id: lambda _e: done.append("scale"),
            CHOOSE_PRINTER.id: lambda _e: done.append("printer"),
        },
    )
    assert order[0] == str(SCALE_TO_FIT.label), "der Fokus steht auf dem Hauptknopf"
    assert sorted(order) == sorted(
        [str(SCALE_TO_FIT.label), str(CHOOSE_PRINTER.label), str(CANCEL.label)]
    ), f"Tab erreicht jeden Knopf genau einmal: {order}"
    if key == Qt.Key.Key_Return:
        assert chosen is SCALE_TO_FIT and done == ["scale"]
    else:
        assert chosen is None and done == []


def test_the_details_stay_readable_and_copyable(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Einzelheiten* zeigt die Angaben, *Kopieren* legt den ganzen Text ab (FD-21)."""
    from app.core.errors import AppError
    from app.ui.dialogs import show_details

    caught = _caught(monkeypatch)
    show_details(AppError(title="Probe", detail="Zeile eins", values={"count": 3}), None)
    (dialog,) = caught
    try:
        assert "Zeile eins" in dialog.details.toPlainText()
        assert dialog.details.isReadOnly()
        copy = dialog.buttons()[0]
        qt_app.clipboard().setText("")
        copy.click()
        copied = qt_app.clipboard().text()
        assert "Probe" in copied and "Zeile eins" in copied
        assert dialog.clicked_button() is None, "Kopieren lässt das Fenster offen"
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_symbol_reads_on_both_themes(qt_app: QApplication, theme: str) -> None:
    """Das Symbol trägt die Farbe der Schwere in der Lesefassung des Themas."""
    from PySide6.QtGui import QColor

    from app.ui.message_dialog import MessageDialog
    from app.ui.palette import text_colour
    from app.ui.theme import apply_theme, contrast_ratio, current_theme

    previous = current_theme()
    previous_palette = qt_app.palette()
    previous_sheet = qt_app.styleSheet()
    try:
        apply_theme(qt_app, theme)
        dialog = MessageDialog(title="T", headline="H", kind="error")
        background = dialog.palette().window().color().name()
        image = dialog.symbol.pixmap().toImage()
        drawn = {
            image.pixelColor(x, y).name()
            for x in range(image.width())
            for y in range(image.height())
            if image.pixelColor(x, y).alpha() == 255
        }
        wanted = QColor(text_colour("error", background)).name()
        assert wanted in drawn, (wanted, sorted(drawn)[:5])
        assert contrast_ratio(wanted, background) >= 3.0
        dialog.deleteLater()
    finally:
        apply_theme(qt_app, previous)
        qt_app.setPalette(previous_palette)
        qt_app.setStyleSheet(previous_sheet)


def test_the_severity_word_comes_from_the_palette(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Wort zum Symbol hat eine Quelle: ``palette.SEVERITY_ENCODING`` (A-L3)."""
    from dataclasses import replace

    from app.ui import palette
    from app.ui.message_dialog import MessageDialog

    renamed = replace(palette.SEVERITY_ENCODING["error"], label_key="Probewort")
    monkeypatch.setitem(palette.SEVERITY_ENCODING, "error", renamed)
    dialog = MessageDialog(title="T", headline="H", kind="error")
    try:
        assert dialog.symbol.accessibleName() == "Probewort"
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("kind", ["error", "warning", "info"])
def test_a_screen_reader_hears_what_went_wrong(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """Schwere, Kopfzeile und Ursache erreichen einen Bildschirmleser (A-M2).

    Ein ``QMessageBox`` meldet sich als ``AlertMessage`` mit Text und Ursache; ein
    eigener Dialog hat die Rolle ``Dialog`` und sagt von sich aus nichts. Seine
    Beschreibung trägt deshalb Wort, Kopfzeile und Satz, und ein Fehler oder eine
    Warnung meldet sich beim Zeigen mit einem ``Alert``.
    """
    from PySide6.QtGui import QAccessible, QAccessibleEvent

    from app.i18n import tr
    from app.ui.message_dialog import MessageDialog
    from app.ui.palette import SEVERITY_ENCODING

    sent: list[QAccessible.Event] = []
    real = QAccessible.updateAccessibility

    def spy(event: QAccessibleEvent) -> None:
        sent.append(event.type())
        real(event)

    monkeypatch.setattr(QAccessible, "updateAccessibility", spy)
    dialog = MessageDialog(
        title="Das hat so nicht funktioniert",
        headline="Platte zu klein",
        body="Das Teil misst 300 mm.",
        kind=kind,  # type: ignore[arg-type]
        target="message:error",
    )
    dialog.add_exit("Schließen", "message.button:error.cancel")
    dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    dialog.show()
    try:
        qt_app.processEvents()
        face = QAccessible.queryAccessibleInterface(dialog)
        assert face is not None
        described = face.text(QAccessible.Text.Description)
        assert tr(SEVERITY_ENCODING[kind].label_key) in described
        assert "Platte zu klein" in described and "300 mm" in described
        assert (QAccessible.Event.Alert in sent) == (kind != "info"), sent
    finally:
        dialog.hide()
        dialog.deleteLater()


def test_a_message_leaves_no_window_behind(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach ``exec`` hängt keine Meldung mehr am Elternteil (A-L1)."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QWidget

    from app.core.errors import RETRY, AppError
    from app.ui import dialogs, message_dialog
    from app.ui.message_dialog import MessageDialog

    monkeypatch.setattr(MessageDialog, "exec", lambda dialog: dialog.reject() or 0)
    monkeypatch.setattr("app.ui.dialogs.QDesktopServices.openUrl", lambda _url: False)
    parent = QWidget()
    try:
        for _ in range(3):
            error = AppError("Probe", "x", suggestions=(RETRY,))
            dialogs.show_error(error, parent, handlers={RETRY.id: lambda _error: None})
            dialogs.show_details(AppError("Probe", "x"), parent)
            message_dialog.inform(parent, "T", "Satz", target="message:browser_failed")
            dialogs.open_donation(parent)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert parent.findChildren(MessageDialog) == []
    finally:
        parent.deleteLater()


def test_copy_takes_the_marked_part_first(qt_app: QApplication) -> None:
    """Strg+C kopiert eine Markierung, sonst den ganzen Text — wie ``QMessageBox`` (A-L2)."""
    from PySide6.QtGui import QTextCursor
    from PySide6.QtTest import QTest

    from app.ui.message_dialog import MessageDialog

    dialog = MessageDialog(
        title="Titel",
        headline="Kopfzeile",
        details="Zeile eins\nZeile zwei",
        target="message:probe",
    )
    dialog.add_exit("Schließen", "message.button:probe.close")
    previous = qt_app.clipboard().text()
    dialog.show()
    try:
        qt_app.processEvents()
        dialog.details.setFocus()
        cursor = dialog.details.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        dialog.details.setTextCursor(cursor)
        qt_app.clipboard().setText("")
        QTest.keyClick(dialog.details, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert qt_app.clipboard().text() == "Zeile eins"

        cursor.clearSelection()
        dialog.details.setTextCursor(cursor)
        dialog.headline.setSelection(0, 4)
        QTest.keyClick(dialog.details, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert qt_app.clipboard().text() == "Kopf"

        dialog.headline.setSelection(0, 0)
        QTest.keyClick(dialog.details, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        assert qt_app.clipboard().text() == dialog.text()
    finally:
        qt_app.clipboard().setText(previous)
        dialog.hide()
        dialog.deleteLater()


def test_a_withdrawn_receipt_leaves_nothing_at_the_button(qt_app: QApplication) -> None:
    """Weicht die Quittung, weicht auch ihre Beschreibung am Knopf (A-L4).

    ``acknowledge`` legt den Satz als Beschreibung auf den nächsten Knopf, damit
    ein Bildschirmleser ihn mitliest. Der Freischaltdialog verbarg beim nächsten
    Schritt nur die Zeile, und *Schließen* las weiter „Solidon ist freigeschaltet“.
    """
    from app.ui.dialogs import ActivationDialog
    from app.ui.message_dialog import acknowledge

    dialog = ActivationDialog()
    try:
        acknowledge(dialog.receipt, "Gespeichert", "Satz", then=dialog.close_button)
        assert dialog.close_button.accessibleDescription()
        dialog.field.setPlainText("")
        dialog._remember()
        assert dialog.receipt.isHidden()
        assert dialog.receipt.accessibleDescription() == ""
        assert dialog.close_button.accessibleDescription() == ""
    finally:
        dialog.deleteLater()
