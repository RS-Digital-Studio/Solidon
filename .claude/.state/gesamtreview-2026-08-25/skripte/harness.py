"""Gemeinsames Gerüst, um die Oberfläche ohne Menschen zu fahren.

Drei Vorkehrungen, ohne die jeder Lauf hängt oder leere Kästchen fotografiert
(siehe `.claude/rules/oberflaeche.md` und die Skripte der vorigen Durchsicht):

* **Echte Qt-Plattform**, kein ``offscreen`` — dort hat Qt auf dieser Maschine
  null Schriftfamilien.
* **Ein Wachhund** räumt modale Dialoge *und* Popup-Menüs weg; ein
  ``QMenu.exec()`` blockiert wie ein modaler Dialog, ist aber keiner.
* **Ausgabe in eine Datei**, ungepuffert — bei einem Hänger sieht man durch
  eine Pipe gar nichts.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(r"F:\3D Druck")
STATE = Path(__file__).resolve().parent.parent
SHOTS = STATE / "aufnahmen"

sys.path.insert(0, str(ROOT))

# §38: der Lauf hinterlässt nichts in Roberts Profil.
_ISOLATED = tempfile.mkdtemp(prefix="solidon-durchsicht-")
for _variable in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED

_log: Any = None


def open_log(name: str) -> None:
    """Schreibt ab jetzt zusätzlich in eine Datei, Zeile für Zeile."""
    global _log
    _log = (STATE / name).open("w", encoding="utf-8", buffering=1)  # noqa: SIM115


def say(*parts: object) -> None:
    line = " ".join(str(part) for part in parts)
    print(line, flush=True)
    if _log is not None:
        _log.write(line + "\n")


class Watchdog:
    """Klickt weg, was den Lauf sonst anhält — und protokolliert es.

    Was hier auftaucht, ist selbst ein Befund: ein Dialog, den ein Ablauf
    nicht braucht, fällt hier auf, weil er im Protokoll steht.
    """

    def __init__(self) -> None:
        self.seen: list[str] = []
        self._timer: Any = None

    def start(self, app: Any) -> None:
        from PySide6.QtCore import QTimer

        self._timer = QTimer()
        self._timer.timeout.connect(lambda: self._sweep(app))
        self._timer.start(250)

    def _sweep(self, app: Any) -> None:
        from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

        popup = QApplication.activePopupWidget()
        if popup is not None:
            self.seen.append(f"popup: {type(popup).__name__}")
            popup.close()
            return

        modal = QApplication.activeModalWidget()
        if modal is None:
            return
        title = modal.windowTitle()
        self.seen.append(f"modal: {type(modal).__name__} — {title!r}")
        if isinstance(modal, QMessageBox):
            # „Ungesicherte Änderungen" hat drei Knöpfe; ohne den richtigen
            # liest der Aufrufer „Abbrechen" und das Öffnen findet nie statt.
            for button in modal.buttons():
                if modal.buttonRole(button) == QMessageBox.ButtonRole.DestructiveRole:
                    button.click()
                    return
            modal.accept()
            return
        if isinstance(modal, QDialog):
            modal.reject()
            return
        modal.close()


def settle(app: Any, seconds: float = 0.8) -> None:
    for _ in range(80):
        app.processEvents()
    time.sleep(seconds)
    for _ in range(80):
        app.processEvents()


def build(maximised: bool = True, dog: Watchdog | None = None) -> tuple[Any, Any, Watchdog]:
    """Fenster wie beim ersten Start: bildschirmfüllend, Register geladen.

    **Genau ein Wachhund.** Zwei davon nehmen einander die Dialoge weg, und
    was der eine wegklickt, hat der andere nie gesehen — die Messung wird dann
    nicht falsch, sondern zufällig.
    """
    from PySide6.QtWidgets import QApplication

    from app.core.bootstrap import load_operations
    from app.ui.app import build_application

    load_operations()
    app, window = build_application([])
    dog = dog or Watchdog()
    dog.start(app)
    if maximised:
        window.setGeometry(QApplication.primaryScreen().availableGeometry())
    window.show()
    if maximised:
        window.showMaximized()
    window.raise_()
    window.activateWindow()
    settle(app, 1.2)
    window.start()
    settle(app, 1.2)
    return app, window, dog


def shot(window: Any, name: str) -> Path:
    """Aufnahme über den Bildschirm — OpenGL kommt in kein ``QWidget.grab``."""
    from PySide6.QtWidgets import QApplication

    SHOTS.mkdir(parents=True, exist_ok=True)
    path = SHOTS / name
    QApplication.primaryScreen().grabWindow(window.winId()).save(str(path))
    return path


def findings_of(window: Any) -> list[Any]:
    result = window.session.last_result
    return list(result.scene.report.findings) if result else []


def show_findings(window: Any, indent: str = "    ") -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings_of(window):
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
        say(f"{indent}[{finding.severity}] {finding.code}: {finding.message}")
    return counts


def rebuild() -> tuple[Any, Any]:
    """Ein zweites Fenster in derselben Anwendung — wie ein Neustart, ohne
    einen zweiten Prozess. ``build_application`` nimmt die vorhandene
    ``QApplication``, wenn es eine gibt."""
    from PySide6.QtWidgets import QApplication

    from app.ui.app import build_application

    app, window = build_application([])
    window.setGeometry(QApplication.primaryScreen().availableGeometry())
    window.show()
    window.showMaximized()
    window.raise_()
    window.activateWindow()
    settle(app, 1.0)
    return app, window
