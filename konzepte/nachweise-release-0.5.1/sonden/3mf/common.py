"""Gemeinsamer Unterbau der Sonden des Pakets 3mf (Kopie aus sonden/fenster).

Baut das Fenster wie ``app.ui.app.main``: ``load_operations``,
``build_application``, Qt-Übersetzungen, ``start``. Der Baum kommt aus
``SONDE_TREE`` (Vorgabe: wt-3mf) und steht als erster Suchpfad; ``app``
muss aus ihm geladen sein. Nutzerordner in einem Temp-Ordner, harte Frist
über ``SONDE_FRIST`` (Vorgabe 240 s), Ausgabe selbst in eine Datei.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

_FRIST = float(os.environ.get("SONDE_FRIST", "240"))
_WATCH = threading.Timer(_FRIST, lambda: os._exit(9))
_WATCH.daemon = True
_WATCH.start()

TREE = os.environ.get("SONDE_TREE", r"F:\3D Druck.review-051\wt-3mf")
sys.path.insert(0, TREE)
_ISOLATED = tempfile.mkdtemp(prefix="sonde-3mf-")
for _variable in ("APPDATA", "LOCALAPPDATA"):
    os.environ[_variable] = _ISOLATED
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import app  # noqa: E402

if not str(Path(app.__file__).resolve()).lower().startswith(str(Path(TREE).resolve()).lower()):
    raise SystemExit(f"app aus falschem Baum: {app.__file__}")

OUT_DIR = Path(__file__).resolve().parent / "out"
OUT_DIR.mkdir(exist_ok=True)


class Log:
    """Schreibt jede Zeile sofort in die Datei (``os._exit`` leert keine Puffer)."""

    def __init__(self, name: str) -> None:
        self.path = OUT_DIR / name
        self._stream = self.path.open("w", encoding="utf-8", buffering=1)
        self.started = time.monotonic()

    def __call__(self, *parts: object) -> None:
        stamp = f"[{time.monotonic() - self.started:7.2f}]"
        self._stream.write(" ".join((stamp, *map(str, parts))) + "\n")
        self._stream.flush()


def build():
    """Anwendung und Fenster wie ``main`` — ohne Ladebildschirm und Ereignisschleife."""
    from app.core.bootstrap import load_operations

    load_operations()
    # Wie ``main``: Das Umschaltintervall setzt der Start, nicht
    # ``build_application`` (RM-258). Der Stand davor kennt die Funktion nicht.
    from app.ui import leash

    if hasattr(leash, "configure_gil_switching"):
        leash.configure_gil_switching()
    from PySide6.QtCore import Qt

    from app.ui.app import build_application

    application, window = build_application([])
    # Kein Erststart-Dialog und keine Update-Frage: Beides ist modal und nicht
    # Gegenstand der Sonden.
    import app.ui.first_run as first_run_module

    first_run_module.should_run = lambda _settings: False
    window.settings.check_for_updates = False
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.resize(1600, 1000)
    window.show()
    return application, window


def pump(application, seconds: float) -> None:
    """Ereignisse für ``seconds`` Sekunden verarbeiten, gemessen an der Uhr."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        application.processEvents()
        time.sleep(0.005)


def wait_until(application, condition, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        application.processEvents()
        if condition():
            return True
        time.sleep(0.005)
    return bool(condition())


class GapMeter:
    """Die längste Lücke zwischen zwei 5-ms-Takten im Hauptthread."""

    def __init__(self, application) -> None:
        from PySide6.QtCore import QTimer

        self.application = application
        self.timer = QTimer()
        self.timer.setInterval(5)
        self.timer.timeout.connect(self._tick)
        self.last = time.monotonic()
        self.longest = 0.0

    def _tick(self) -> None:
        now = time.monotonic()
        self.longest = max(self.longest, now - self.last)
        self.last = now

    def start(self) -> None:
        self.last = time.monotonic()
        self.longest = 0.0
        self.timer.start()

    def stop(self) -> float:
        self.timer.stop()
        return self.longest


class Watchdog:
    """Ein Wachhund für modale Dialoge — genau einer, mit Riegel.

    ``handler(dialog)`` bekommt jeden aktiven modalen Dialog oder jedes Popup
    des eigenen Fensters und gibt ``True`` zurück, wenn es ihn bedient hat;
    sonst wird er abgelehnt und protokolliert.
    """

    def __init__(self, application, window, log, handler=None) -> None:
        from PySide6.QtCore import QTimer

        self.application, self.window, self.log = application, window, log
        self.handler = handler
        self.seen: list[str] = []
        self._busy = False
        self.timer = QTimer()
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._look)
        self.timer.start()

    def _look(self) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            dialog = self.application.activeModalWidget() or self.application.activePopupWidget()
            if dialog is None:
                return
            if dialog.window() is not dialog or (
                dialog.parentWidget() is not None and dialog.parentWidget().window() is not self.window
            ):
                pass
            title = dialog.windowTitle()
            self.seen.append(title)
            if self.handler is not None and self.handler(dialog):
                return
            self.log("  WACHHUND lehnt ab:", type(dialog).__name__, repr(title))
            if hasattr(dialog, "reject"):
                dialog.reject()
            else:
                dialog.close()
        finally:
            self._busy = False


def report_rows(window) -> list[tuple[str, str, str, list[str]]]:
    """Jede Zeile des Prüfberichts: Kennung, Schwere, Text, angebotene Knöpfe.

    Die Knöpfe liest die Sonde aus der Knopfzeile unter der gewählten Zeile —
    dort, wo der Kunde sie sieht.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QPushButton

    panel = window.report
    rows = []
    previous = panel.list.currentRow()
    for index in range(panel.list.count()):
        item = panel.list.item(index)
        finding = item.data(Qt.ItemDataRole.UserRole)
        panel.list.setCurrentRow(index)
        # Neue Knöpfe zeigt Qt erst in der nächsten Ereignisrunde.
        for _round in range(3):
            QApplication.processEvents()
        buttons = [
            button.text()
            for button in panel._offers.findChildren(QPushButton)
            if not button.isHidden()
        ]
        rows.append(
            (
                getattr(finding, "code", "?"),
                getattr(finding, "severity", "?"),
                item.text().replace("\n", " / "),
                buttons if panel._offers.isVisibleTo(panel) else [],
            )
        )
    panel.list.setCurrentRow(previous)
    return rows


def click_offer(window, code: str, label: str) -> bool:
    """Die Zeile mit ``code`` wählen und ihren Knopf ``label`` klicken."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QPushButton

    panel = window.report
    for index in range(panel.list.count()):
        finding = panel.list.item(index).data(Qt.ItemDataRole.UserRole)
        if getattr(finding, "code", None) != code:
            continue
        panel.list.setCurrentRow(index)
        for _round in range(3):
            QApplication.processEvents()
        for button in panel._offers.findChildren(QPushButton):
            if not button.isHidden() and button.text() == label:
                button.click()
                return True
    return False


class StallSampler:
    """Hält den Stapel des Hauptfadens fest, wenn er länger als ``limit`` steht.

    Ein Beobachterfaden sieht alle 50 ms nach dem Takt des :class:`GapMeter`;
    steht der länger als ``limit`` Sekunden, wird der Stapel des Hauptfadens
    gezählt. So nennt die Sonde die Zeilen, an denen der Hauptfaden steht.
    """

    def __init__(self, meter: GapMeter, limit: float = 0.3) -> None:
        import collections

        self.meter, self.limit = meter, limit
        self.main = threading.main_thread().ident
        self.counts: collections.Counter[str] = collections.Counter()
        self._stop = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        import traceback

        while not self._stop:
            time.sleep(0.05)
            if time.monotonic() - self.meter.last < self.limit:
                continue
            frame = sys._current_frames().get(self.main)
            if frame is None:
                continue
            stack = traceback.extract_stack(frame)
            own = [
                f"{Path(entry.filename).name}:{entry.lineno} {entry.name}" for entry in stack
            ][-9:]
            self.counts[" <- ".join(reversed(own))] += 1

    def stop(self):
        self._stop = True
        return self.counts.most_common(12)
