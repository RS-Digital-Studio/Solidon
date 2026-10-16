"""Der Rückweg eines Sprachfalls holt das Fenster nach vorn, bevor er Escape drückt.

Ein nichtmodaler Operationsdialog, der nicht das aktive Fenster wurde, bekam
Escape nicht: Das Hauptfenster stand vorn, seine Taste *Auswahl leeren* nahm
den Druck, und der Dialog blieb offen. Der Sprachfall brach mit „Fenster der
vorigen Fläche blieb offen“ ab — offscreen an *Anordnen* und *Kollisionen
prüfen* (Probe FD-101). Der Kunde drückt Escape in dem Fenster, das vorn
steht; ein Fenster, das er schließen will, hat er vorn.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tools import function_language


def _flow(qt_app: Any) -> Any:
    def run_steps(label: str, steps: list[Any]) -> bool:
        for step in steps:
            step.act(None)
            for _ in range(20):
                qt_app.processEvents()
        return True

    return SimpleNamespace(
        walker=SimpleNamespace(record=lambda entry: None),
        run_steps=run_steps,
        data={"errors": []},
    )


def test_escape_closes_a_dialog_the_main_window_stands_in_front_of(qt_app: Any) -> None:
    from PySide6.QtGui import QKeySequence, QShortcut
    from PySide6.QtWidgets import QApplication, QDialog, QMainWindow

    window = QMainWindow()
    taken: list[str] = []
    # Wie *Auswahl leeren* am Hauptfenster: Escape als Taste des Fensters.
    QShortcut(QKeySequence("Escape"), window, activated=lambda: taken.append("auswahl"))
    window.resize(400, 300)
    window.show()
    dialog = QDialog(window)
    dialog.setModal(False)
    dialog.show()
    window.activateWindow()
    for _ in range(40):
        qt_app.processEvents()
    try:
        # Voraussetzung, nicht Annahme: Das Hauptfenster steht vorn.
        assert QApplication.activeWindow() is window
        flow = function_language.LanguageFlow.__new__(function_language.LanguageFlow)
        flow.window = window
        assert flow.close_surfaces(_flow(qt_app)) is True
        assert not dialog.isVisible()
        assert taken == [], "Escape ging an das Hauptfenster"
    finally:
        dialog.close()
        window.close()
        window.deleteLater()
        qt_app.processEvents()
