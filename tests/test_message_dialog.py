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
