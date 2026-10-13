"""Der Startfall: die Anwendung über ``app.ui.app.main`` selbst (D0-P, RM-737, Zeile D12).

Eine abgelaufene Demo (``over``) startet nicht; sie ist kein Lauf je Funktion,
sondern der Startfall ihrer Zeile. :class:`StartFlow` startet ``main`` mit dem
vorbereiteten Profil, liest die Meldung, die den Grund nennt, schließt sie über
einen Klick mit Probe und hält den Ausgang von ``main`` fest. Das Starttor wird
nie umgangen. Geurteilt wird bei D0-U.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any, Final

from tools.function_checks import (
    COVERED,
)
from tools.function_protocol import unmeasured
from tools.function_walk import QtPorts, Walk, click_button

#: Wie lange der Startfall auf das Starttor wartet: Meldung oder Hauptfenster (Sekunden).
START_WAIT_S: Final = 120.0


class StartFlow:
    """Der Startfall (D12, Zustand ``over``): der echte Startweg über ``app.ui.app.main``.

    Eine abgelaufene Demo startet nicht (Demo-Konzept §2 B2): ``main`` zeigt den
    Abschied und endet mit einem eigenen Ausgang. Der Prüfstand umgeht das
    Starttor nicht — er setzt nur den Zustand über die Nahtstelle der Suite
    (:func:`apply_licence`) und ruft ``main``. Weil ``main`` die
    ``QApplication`` selbst baut, wartet ein Nebenfaden, bis es sie gibt, und
    reicht dann einen Auftrag über die Warteschlange in den Hauptfaden
    (``QMetaObject.invokeMethod``). Von dort sieht ein Zeitgeber nach: Steht die
    Meldung, wird ihr Text gelesen und sie mit einem Klick auf *Schließen*
    samt Probe geschlossen — nie *Website öffnen*. Entsteht stattdessen ein
    Hauptfenster, hat das Tor nicht gehalten; das steht im Protokoll, und der
    Lauf endet.

    Ins Protokoll: ``messages`` (Text und Knöpfe), ``modals``/``raw_windows``/
    ``windows`` aus der Wache, der Klick in ``steps`` (Phase ``start``) und in
    ``result.metrics`` der Ausgang von ``main`` (``exit_code``), ob ein
    Hauptfenster entstand (``main_window``) und ob die Meldung erschien
    (``message_shown``). Geurteilt wird bei D0-U.
    """

    def __init__(self, data: dict[str, Any], persist: Callable[[], None]) -> None:
        from tools.function_capture import ModalWatch

        self.data = data
        self.persist = persist
        self.began = time.perf_counter()
        self.ports = QtPorts(None, self.began)
        self.walker = Walk(self.ports, data["steps"], self.began)
        self.walker.phase = "start"
        self.watch = ModalWatch(self.began)
        self.seen: dict[str, Any] = {"message": False, "main_window": False, "closed": False}
        self.deadline = time.monotonic() + START_WAIT_S

    def run(self, argv: Sequence[str] = ("solidon",)) -> int:
        """Ruft ``main`` und gibt seinen Ausgang zurück; das Protokoll steht danach."""
        import threading

        from PySide6.QtCore import QMetaObject, QObject, Qt, QTimer, Slot
        from PySide6.QtWidgets import QApplication

        from app.ui import app as start

        flow = self

        class Watch(QObject):
            """Lebt im Hauptfaden, bevor es eine ``QApplication`` gibt."""

            timer: Any = None

            @Slot()
            def begin(self) -> None:
                self.timer = QTimer(self)
                self.timer.timeout.connect(flow.look)
                self.timer.start(50)

        watch = Watch()
        stop = threading.Event()

        def hand_over() -> None:
            while not stop.is_set() and time.monotonic() < flow.deadline:
                if QApplication.instance() is not None:
                    QMetaObject.invokeMethod(watch, "begin", Qt.ConnectionType.QueuedConnection)
                    return
                time.sleep(0.01)

        helper = threading.Thread(target=hand_over, name="startfall", daemon=True)
        helper.start()
        try:
            code = int(start.main(list(argv)))
        finally:
            stop.set()
            helper.join(timeout=5)
            if watch.timer is not None:
                watch.timer.stop()
        self.watch.poll()
        self.data["modals"] = self.watch.modal_entries()
        self.data["raw_windows"] = self.watch.raw_entries()
        self.data["windows"] = list(self.watch.windows)
        self.data["result"] = {
            "metrics": {
                "exit_code": code,
                "main_window": bool(self.seen["main_window"]),
                "message_shown": bool(self.seen["message"]),
            }
        }
        if not self.seen["message"]:
            unmeasured(self.data, "messages", "das Starttor zeigte keine Meldung")
        self.persist()
        return code

    def look(self) -> None:
        """Ein Takt im Hauptfaden: Hauptfenster? Meldung? Dann lesen und schließen."""
        from PySide6.QtWidgets import QAbstractButton, QApplication, QMessageBox

        from app.ui.main_window import MainWindow
        from tools.function_capture import name_of, visible_texts

        self.watch.poll()
        if any(isinstance(top, MainWindow) for top in QApplication.topLevelWidgets()):
            if not self.seen["main_window"]:
                self.data["errors"].append("Die Anwendung startete trotz abgelaufener Demo")
                self.persist()
            self.seen["main_window"] = True
            QApplication.exit(2)
            return
        if time.monotonic() > self.deadline:
            self.data["errors"].append(f"Nach {START_WAIT_S:.0f} s weder Meldung noch Fenster")
            self.persist()
            QApplication.exit(3)
            return
        box = QApplication.activeModalWidget()
        if box is None or self.seen["closed"]:
            return
        self.seen["message"] = True
        buttons = [
            button
            for button in box.findChildren(QAbstractButton)
            if button.isVisible() and name_of(button)
        ]
        closing = (
            box.button(QMessageBox.StandardButton.Close)
            if isinstance(box, QMessageBox)
            else _exit_of(box)
        )
        house = "MessageDialog" in {cls.__name__ for cls in type(box).__mro__}
        text = box.text() if isinstance(box, QMessageBox) or house else ""
        text = text or " ".join(visible_texts(box))
        entry = {
            "text": str(text),
            "actions": [
                {"label": name_of(button), "target": "", "clicked": False, "effect": None}
                for button in buttons
            ],
        }
        self.data["messages"] = [entry]
        self.seen["closed"] = True
        self.persist()
        if closing is None:
            self.data["errors"].append("Die Meldung hat keinen Knopf Schließen")
            self.ports.keys("Escape")
            return
        label = name_of(closing)
        for action in entry["actions"]:
            action["clicked"] = action["label"] == label
        self.persist()
        if not click_button(self.ports, self.walker, closing, label):
            for action in entry["actions"]:
                action["clicked"] = False
            self.data["findings"].append(
                {
                    "phase": "start",
                    "kind": COVERED,
                    "target": label,
                    "detail": str(self.data["steps"][-1].get("detail", "")),
                }
            )
            self.persist()
            self.ports.keys("Escape")


def _exit_of(box: Any) -> Any | None:
    """Der Ausgang einer Meldung im Hausstil (``MessageDialog``, FD-21): ihr Knopf mit der
    Rolle *Verwerfen* — Schließen, Escape. ``None`` für jedes andere Fenster."""
    from PySide6.QtWidgets import QDialogButtonBox

    if "MessageDialog" not in {cls.__name__ for cls in type(box).__mro__}:
        return None
    exits = QDialogButtonBox.ButtonRole.RejectRole
    return next(
        (button for button in box.buttons() if box.button_box.buttonRole(button) == exits), None
    )
