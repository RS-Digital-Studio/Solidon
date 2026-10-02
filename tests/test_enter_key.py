"""Enter gehört dem Knopf, den die Tastatur gewählt hat (RM-334, Bauplan §19.2).

Der Zuhörer aus ``app.ui.style`` nimmt jedem Nebenknopf beim Fokus
``autoDefault``, damit kein Knopf mit dem Fokus den Akzent des Hauptknopfs
bekommt. Ohne ``autoDefault`` gab der Knopf Enter an den Dialog weiter, und der
klickte den Hauptknopf: Tab auf *Abbrechen*, Enter — und die Schritte waren
verworfen, die Projektdatei überschrieben, die Datei exportiert.

Die Entscheidung selbst prüft der erste Test ohne Fenster; die Rückfragen
laufen echt über ``exec()`` mit Tastendrücken, wie ein Kunde sie gibt.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from PySide6.QtCore import Qt

from app.ui.style import enter_belongs_to_focus

#: Wie oft Tab gedrückt wird, bis der gesuchte Knopf den Fokus hat — mehr
#: Knöpfe und Felder hat keine der Rückfragen.
TAB_LIMIT = 10


@pytest.mark.parametrize(
    ("reason", "forced", "expected"),
    [
        (Qt.FocusReason.TabFocusReason, False, True),
        (Qt.FocusReason.BacktabFocusReason, False, True),
        # Vom gesperrten oder verborgenen Knopf vertrieben: Qt meldet auch das
        # als Tab, gedrückt hat ihn niemand.
        (Qt.FocusReason.TabFocusReason, True, False),
        (Qt.FocusReason.BacktabFocusReason, True, False),
        (Qt.FocusReason.MouseFocusReason, False, False),
        (Qt.FocusReason.ActiveWindowFocusReason, False, False),
        (Qt.FocusReason.OtherFocusReason, False, False),
        (Qt.FocusReason.PopupFocusReason, False, False),
        (Qt.FocusReason.ShortcutFocusReason, False, False),
    ],
)
def test_only_the_keyboard_hands_enter_to_the_focused_button(
    reason: Qt.FocusReason, forced: bool, expected: bool
) -> None:
    assert enter_belongs_to_focus(reason, forced=forced) is expected


def _answer(
    qt_app: Any, ask: Callable[[], object], target: str | None, *, switch: bool = False
) -> object:
    """Stellt die Rückfrage mit ``exec()`` und antwortet per Tastatur.

    ``target`` ist die Beschriftung des Knopfs, auf den Tab gehen soll;
    ``None`` drückt Enter, ohne den Fokus zu bewegen. ``switch`` wechselt vor
    Enter in ein anderes Fenster und zurück (RM-415). Bleibt die Box offen
    — etwa weil Enter nichts auslöste —, schließt der Wächter sie mit
    ``reject``, und der Test sieht das als Fehler statt zu hängen.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget

    problems: list[str] = []
    elsewhere = QWidget()
    elsewhere.setWindowTitle("Anderes Fenster")

    def press() -> None:
        box = QApplication.activeModalWidget()
        if not isinstance(box, QMessageBox):
            QTimer.singleShot(20, press)
            return
        # Ohne aktives Fenster hat die Box keinen Fokus, und Tab wie Enter
        # gingen an ihr vorbei an den Default.
        box.activateWindow()
        QApplication.processEvents()
        try:
            if not box.isActiveWindow():
                problems.append("die Rückfrage wurde nicht aktiv")
                box.reject()
                return
            if target is not None:
                for _ in range(TAB_LIMIT):
                    focused = QApplication.focusWidget()
                    if isinstance(focused, QPushButton) and focused.text() == target:
                        break
                    QTest.keyClick(focused or box, Qt.Key.Key_Tab)
                focused = QApplication.focusWidget()
                if not (isinstance(focused, QPushButton) and focused.text() == target):
                    problems.append(f"Tab erreicht „{target}“ nicht")
                    box.reject()
                    return
                if focused.isDefault():
                    problems.append(f"„{target}“ trägt mit dem Fokus den Akzent")
            if switch:
                chosen = QApplication.focusWidget()
                elsewhere.show()
                elsewhere.activateWindow()
                QApplication.processEvents()
                if box.isActiveWindow():
                    problems.append("das andere Fenster wurde nicht aktiv")
                box.activateWindow()
                QApplication.processEvents()
                if not box.isActiveWindow() or QApplication.focusWidget() is not chosen:
                    problems.append("nach dem Fensterwechsel steht der Fokus woanders")
            QTest.keyClick(QApplication.focusWidget() or box, Qt.Key.Key_Return)
        finally:
            if box.isVisible():
                problems.append("Enter hat die Rückfrage nicht beantwortet")
                box.reject()

    QTimer.singleShot(0, press)
    try:
        answer = ask()
    finally:
        elsewhere.close()
        elsewhere.deleteLater()
    qt_app.processEvents()
    assert not problems, problems
    return answer


def _findings() -> list[Any]:
    from app.core.types import Finding

    return [Finding("fit.collision", "warning", "Überschneidung")]


def test_enter_on_the_tabbed_cancel_keeps_the_cut_off_steps(qt_app: Any) -> None:
    """„Abgeschnittene Schritte verwerfen?“ — Tab auf *Abbrechen*, Enter: nichts verworfen."""
    from app.ui.dialogs import confirm_discard

    assert _answer(qt_app, lambda: confirm_discard(3, ("Bohrung", "Fase")), "Abbrechen") is False
    # Gegenprobe: Ohne Tab bleibt Enter beim Hauptknopf.
    assert _answer(qt_app, lambda: confirm_discard(3, ("Bohrung", "Fase")), None) is True


@pytest.mark.parametrize(
    ("target", "expected"),
    [("Verwerfen", "discard"), ("Abbrechen", "cancel"), (None, "save")],
)
def test_enter_on_a_tabbed_button_of_unsaved_changes_does_not_save(
    qt_app: Any, target: str | None, expected: str
) -> None:
    """„Ungesicherte Änderungen“ — Enter auf dem per Tab gewählten Knopf überschreibt nichts."""
    from app.ui.dialogs import confirm_unsaved

    assert _answer(qt_app, lambda: confirm_unsaved("Halter.solidon"), target) == expected


@pytest.mark.parametrize(
    ("ask", "target", "expected"),
    [
        ("discard", "Abbrechen", False),
        ("discard", None, True),
        ("unsaved", "Abbrechen", "cancel"),
        ("unsaved", "Verwerfen", "discard"),
        ("unsaved", None, "save"),
        ("export", "Abbrechen", False),
        ("export", None, True),
    ],
)
def test_enter_keeps_the_tabbed_button_across_a_window_switch(
    qt_app: Any, ask: str, target: str | None, expected: object
) -> None:
    """Tab auf *Abbrechen*, kurz ein anderes Fenster, zurück, Enter — und die
    Rückfrage verwarf, speicherte oder exportierte trotzdem (RM-415): Der
    Fensterwechsel löschte die Wahl der Tastatur. Er ist keine neue Wahl; ohne
    Tab bleibt Enter auch nach dem Wechsel beim Hauptknopf."""
    from app.ui.dialogs import confirm_discard, confirm_export, confirm_unsaved

    questions: dict[str, Callable[[], object]] = {
        "discard": lambda: confirm_discard(3, ("Bohrung", "Fase")),
        "unsaved": lambda: confirm_unsaved("Halter.solidon"),
        "export": lambda: confirm_export(_findings()),
    }
    assert _answer(qt_app, questions[ask], target, switch=True) == expected


def test_enter_on_the_tabbed_cancel_does_not_export(qt_app: Any) -> None:
    """Vor dem Export — Tab auf *Abbrechen*, Enter: keine Datei."""
    from app.ui.dialogs import confirm_export

    assert _answer(qt_app, lambda: confirm_export(_findings()), "Abbrechen") is False
    assert _answer(qt_app, lambda: confirm_export(_findings()), None) is True


def test_enter_follows_the_keyboard_in_every_dialog_but_not_the_mouse(qt_app: Any) -> None:
    """Jeder ``QDialog``, nicht nur die Rückfragen — und die Fälle, in denen Enter
    beim Hauptknopf bleibt: Fokus per Maus und Fokus, den ein gesperrter Knopf
    abgibt.
    """
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QPushButton

    from app.ui.style import make_primary

    dialog = QDialog()
    layout = QHBoxLayout(dialog)
    primary = make_primary(QPushButton("Übernehmen", dialog))
    other = QPushButton("Vorschau", dialog)
    cancel = QPushButton("Abbrechen", dialog)
    for button in (primary, other, cancel):
        layout.addWidget(button)
    clicked: list[str] = []
    for button, name in ((primary, "Übernehmen"), (other, "Vorschau"), (cancel, "Abbrechen")):
        button.clicked.connect(lambda _checked=False, name=name: clicked.append(name))
    try:
        dialog.show()
        dialog.activateWindow()
        qt_app.processEvents()
        assert dialog.isActiveWindow(), "ohne aktives Fenster kommt kein Fokus an"

        primary.setFocus(Qt.FocusReason.OtherFocusReason)
        QTest.keyClick(primary, Qt.Key.Key_Tab)
        assert QApplication.focusWidget() is other
        assert primary.isDefault() and not other.isDefault(), "der Akzent wandert nicht"
        QTest.keyClick(other, Qt.Key.Key_Return)
        assert clicked == ["Vorschau"], "Tab, Enter klickt den fokussierten Knopf"

        clicked.clear()
        cancel.setFocus(Qt.FocusReason.MouseFocusReason)
        qt_app.processEvents()
        QTest.keyClick(cancel, Qt.Key.Key_Return)
        assert clicked == ["Übernehmen"], "nach der Maus bleibt Enter beim Hauptknopf"

        # Ein Knopf wird gesperrt, während er den Fokus hat: Qt reicht ihn mit
        # TabFocusReason weiter. Das ist kein Tastendruck.
        clicked.clear()
        other.setFocus(Qt.FocusReason.TabFocusReason)
        qt_app.processEvents()
        other.setEnabled(False)
        qt_app.processEvents()
        assert QApplication.focusWidget() is cancel
        QTest.keyClick(cancel, Qt.Key.Key_Return)
        assert clicked == ["Übernehmen"], "vertriebener Fokus nimmt dem Hauptknopf Enter nicht"
    finally:
        dialog.close()
        dialog.deleteLater()
    qt_app.processEvents()


def test_enter_after_the_generation_takes_the_result(qt_app: Any) -> None:
    """Der Anlass des Zuhörers (``2385fa72a``): Während des Laufs geht der Fokus
    vom gesperrten *Erzeugen* auf *Abbrechen*. Danach übernimmt Enter das
    Ergebnis, statt es zu verwerfen — wer dagegen selbst mit Tab auf
    *Abbrechen* geht, bricht mit Enter ab.
    """
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialogButtonBox

    from app.ui.generate_dialog import GenerateDialog
    from tests.scripted_backend import ScriptedMeshBackend

    dialog = GenerateDialog(backend=ScriptedMeshBackend(fallback=b"solid x\n"))
    make = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
    cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    clicked: list[str] = []
    make.clicked.connect(lambda: clicked.append("make"))
    cancel.clicked.connect(lambda: clicked.append("cancel"))
    try:
        dialog.show()
        dialog.activateWindow()
        assert dialog.wait_for_readiness(5000)
        dialog.prompt.setText("eine Eule")
        qt_app.processEvents()
        assert dialog.isActiveWindow(), "ohne aktives Fenster kommt kein Fokus an"

        make.setFocus(Qt.FocusReason.TabFocusReason)
        qt_app.processEvents()
        dialog._running(True)
        qt_app.processEvents()
        moved = QApplication.focusWidget()
        assert moved is not make, "der Fokus hat den gesperrten Knopf verlassen"
        dialog._running(False)
        qt_app.processEvents()
        assert make.isEnabled() and make.isDefault()
        # Der Klick auf „Erzeugen“ startete einen Lauf; gemessen wird nur, welcher
        # Knopf Enter bekommt — der Lauf selbst wird gleich angehalten.
        dialog._start = lambda: None  # type: ignore[method-assign]
        QTest.keyClick(moved or dialog, Qt.Key.Key_Return)
        assert clicked == ["make"], f"Enter nach dem Lauf klickte {clicked}"

        # Mindestens ein Tab: Der Fokus steht schon auf „Abbrechen“, aber nicht
        # durch die Tastatur. Der Erzeugen-Dialog hat mehr Felder als eine
        # Rückfrage, daher die längere Runde.
        clicked.clear()
        for _ in range(3 * TAB_LIMIT):
            QTest.keyClick(QApplication.focusWidget() or dialog, Qt.Key.Key_Tab)
            if QApplication.focusWidget() is cancel:
                break
        assert QApplication.focusWidget() is cancel, "Tab erreicht „Abbrechen“"
        QTest.keyClick(cancel, Qt.Key.Key_Return)
        assert clicked == ["cancel"], f"Tab auf „Abbrechen“, Enter klickte {clicked}"
    finally:
        dialog.wait_for_workers()
        dialog.close()
        dialog.deleteLater()
    qt_app.processEvents()
