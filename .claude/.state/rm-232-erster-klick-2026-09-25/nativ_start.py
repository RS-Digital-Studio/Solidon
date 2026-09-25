"""Wer legt beim Start native Fenster an? WinIdChange anwendungsweit mitschreiben.

Aufruf: python nativ_start.py — schreibt nach probe-out/nativ_start/log.txt.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from pathlib import Path

threading.Timer(300.0, lambda: os._exit(9)).start()
SCRATCH = Path(__file__).resolve().parent
ROOT = Path(r"F:\3D Druck")
OUT = SCRATCH / "probe-out" / "nativ_start"
OUT.mkdir(parents=True, exist_ok=True)
LOG = open(OUT / "log.txt", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
PROFILE = SCRATCH / "probe-profile"
for variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME"):
    os.environ[variable] = str(PROFILE)
os.environ.pop("QT_QPA_PLATFORM", None)
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEvent, QObject  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

application = QApplication([])
seen: list[str] = []


class Watch(QObject):
    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() == QEvent.Type.WinIdChange and isinstance(watched, QWidget):
            chain = []
            current = watched
            while current is not None:
                chain.append(f"{type(current).__name__}:{current.objectName()}")
                current = current.parentWidget()
            stack = [
                line
                for line in traceback.format_stack(limit=30)
                if "3D Druck\app" in line or "3D Druck/app" in line
            ]
            LOG.write(f"WinId {len(seen)}: {' < '.join(chain[:6])}\n")
            if stack:
                LOG.write("    " + stack[-1].strip().splitlines()[0] + "\n")
            seen.append(chain[0])
        return False


watch = Watch()
application.installEventFilter(watch)
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.ui.app import build_application  # noqa: E402

LOG.write("--- build_application\n")
application, window = build_application([])
window.settings.first_run_done = True
LOG.write("--- showMaximized\n")
window.showMaximized()
end = time.monotonic() + 4.0
while time.monotonic() < end:
    application.processEvents()
    time.sleep(0.01)
LOG.write(f"--- fertig, {len(seen)} WinIdChange\n")
LOG.flush()
os._exit(0)
