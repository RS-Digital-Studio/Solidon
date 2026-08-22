"""Der Druckeinstellungen-Dialog — der größte der Anwendung — in echter Größe.

Dazu die Werkzeugleisten unten (Schnitt, Messen, Analyse, Schichten, Trennen),
weil sie im Handbuch nicht vorkommen und ein Demonutzer sie als Erstes anklickt.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def wait(app, seconds: float = 1.0, rounds: int = 120) -> None:
    for _ in range(rounds):
        app.processEvents()
    time.sleep(seconds)
    for _ in range(rounds):
        app.processEvents()


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.core import examples
    from app.core.bootstrap import load_operations
    from app.ui.app import build_application

    load_operations()
    app, window = build_application([])
    window.resize(1440, 900)
    window.show()
    window.raise_()
    window.activateWindow()
    wait(app, 0.8)
    screen = QApplication.primaryScreen()

    project = examples.directory() / "weg1-halterung-anpassen.p3d"
    window.open_path(project)
    window.session.wait_for_idle()
    wait(app, 1.5, rounds=200)

    # Der Druckeinstellungen-Dialog, ohne exec (das blockiert).
    from app.ui.print_settings_dialog import PrintSettingsDialog

    dialog = PrintSettingsDialog(window.session, window.settings, parent=window)
    dialog.adjustSize()
    dialog.show()
    wait(app, 1.0)
    print(f"Dialog: {dialog.width()}x{dialog.height()} sizeHint {dialog.sizeHint().width()}x{dialog.sizeHint().height()}")
    screen.grabWindow(dialog.winId()).save(str(OUT / "print-settings.png"))
    dialog.close()

    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
