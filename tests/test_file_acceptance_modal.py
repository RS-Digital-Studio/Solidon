"""Ein Fenster, das im Ereignisdurchlauf eines Dateifalls aufgeht, hält ihn nicht an (FD-173).

Zwilling zu FD-172: Fragt ein Arbeiter oder kommt eine Absage als Meldung, geht
das modale Fenster in ``pump`` auf, nicht in einem Schritt. ``WindowFlow.drive``
baute seinen Automaten ohne die Frage nach einer solchen Schleife: Der Automat
war fertig und tickte nicht mehr, ``drive`` stand in der Schleife des Fensters
bis zur Frist des Elternprozesses. Jetzt fragt er wie der Funktionsfall
(``function_machine.nested_since_now``) und räumt das Fenster mit Escape ab.

Ein Wachhund schließt das Fenster nach :data:`WATCHDOG_MS`, damit der alte
Hänger den Lauf nicht anhält; musste er es schließen, ist der Test rot.
Offscreen, kein natives Fenster.
"""

from __future__ import annotations

from typing import Any

#: Wann der Wachhund ein noch offenes Fenster schließt (Millisekunden) — weit über
#: dem Takt, in dem der Automat es mit Escape abräumt (``SETTLE_MS``).
WATCHDOG_MS = 5_000


def test_a_window_opened_during_the_pump_is_closed_by_the_machine(
    qt_app: Any, tmp_path: Any
) -> None:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog, QMainWindow

    from tools.file_acceptance import WindowFlow
    from tools.function_machine import Step

    window = QMainWindow()
    asked = QDialog(window)
    state = {"shown": False, "watchdog": False}

    def ask() -> None:
        # Wie ``show_error`` oder ``_on_ask``: ein ``exec()`` aus einem Ereignis.
        state["shown"] = True
        asked.exec()

    def watchdog() -> None:
        if asked.isVisible():
            state["watchdog"] = True
            asked.reject()

    flow = WindowFlow(qt_app, window, None, tmp_path, {"errors": [], "steps": []}, lambda: None)
    QTimer.singleShot(WATCHDOG_MS, watchdog)
    try:
        flow.drive(
            "probe",
            [
                Step("klick", lambda machine: QTimer.singleShot(0, ask)),
                Step("antwort", lambda machine: None, ready=lambda: state["shown"]),
            ],
            timeout=60.0,
        )
        assert state["shown"]
        assert not state["watchdog"], "der Wachhund musste das Fenster schließen — der Fall hing"
        assert not asked.isVisible()
    finally:
        asked.deleteLater()
        window.deleteLater()
        qt_app.processEvents()  # type: ignore[attr-defined]
