"""Der Starttest des fertigen Pakets: starten, stehen, sauber beenden.

Kein Test der Suite startet das ausgelieferte Programm. 0.5.1 lief durch jede
Prüfung und beendete sich auf jedem Mac 20 bis 40 Sekunden nach dem Start
(Suche nach der 3D-Maus, ``spacemouse._SearchThread``). Deshalb startet jeder
Release-Lauf jedes Kundenpaket einmal (``tools/check_frozen_start.py``).

Ist :data:`REPORT_VARIABLE` gesetzt, wartet die Anwendung nach dem sichtbaren
Fenster :data:`SECONDS` lang — durch den Erstlauf, die ersten Suchen nach der
3D-Maus, das Laden im Hintergrund und den Start des Hilfsprozesses —,
schreibt dann ihren Zustand als JSON in die genannte Datei und schließt sich,
wie ein Mensch es täte: offene Dialoge abbrechen, dann alle Fenster
schließen. Ob sie danach ordentlich endet, prüft das Werkzeug von außen.

Qt wird erst in den Funktionen geladen: Das Werkzeug liest die Namen hier
auch dort, wo nur ein nacktes Python liegt.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

#: Die Umgebungsvariable mit dem Pfad der Berichtsdatei.
REPORT_VARIABLE: Final = "SOLIDON3D_START_CHECK"

#: Wie lange die Anwendung nach dem sichtbaren Fenster steht, in Sekunden.
#: Die 3D-Maus wird 1,5 s nach dem Fenster gesucht, dann nach 2, 4 und 8 s
#: (``spacemouse.SCAN_FIRST_MS``, ``SCAN_MS``); 0.5.1 brach bei der zweiten
#: Suche ab. Bis hierher laufen vier Suchen.
SECONDS: Final = 25.0

#: Wie oft das Schließen nachsieht, ob noch ein Dialog offen ist, in Millisekunden.
DIALOG_RETRY_MS: Final = 200

#: Fassung des Berichts; das Werkzeug lehnt eine andere ab.
FORMAT: Final = 1


def requested() -> Path | None:
    """Die Berichtsdatei, wenn der Starttest verlangt ist — sonst ``None``."""
    value = os.environ.get(REPORT_VARIABLE, "").strip()
    return Path(value) if value else None


def arm(report: Path, window: Callable[[], Any]) -> None:
    """Hängt den Starttest an die laufende Anwendung.

    ``window`` liefert das Hauptfenster zum Zeitpunkt des Berichts: Ein
    Sprachwechsel im Erstlauf ersetzt es.
    """
    from PySide6.QtCore import QTimer

    started = time.monotonic()
    QTimer.singleShot(round(SECONDS * 1000), lambda: _finish(report, window(), started))


def _finish(report: Path, window: Any, started: float) -> None:
    # Auch ohne Bericht wird geschlossen: Das Werkzeug meldet ihn dann als
    # fehlend, und der Grund steht im Protokoll — statt einer stehenden
    # Anwendung, die erst die Frist beendet.
    try:
        report.write_text(
            json.dumps(describe(window, time.monotonic() - started), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    finally:
        _close_everything()


def describe(window: Any, seconds: float) -> dict[str, Any]:
    """Der Zustand der Anwendung, wie das Werkzeug ihn prüft."""
    import multiprocessing

    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    from app.branding import APP_VERSION
    from app.core.export.squashfs import readable_compressions
    from app.core.log import install_crash_logging, log_path
    from app.ui.qt_platform import input_modules

    return {
        "format": FORMAT,
        "version": APP_VERSION,
        "platform": QGuiApplication.platformName(),
        "executable": sys.executable,
        "seconds": round(seconds, 1),
        "window": {"visible": bool(window.isVisible()), "title": window.windowTitle()},
        "dialogs": [
            widget.windowTitle()
            for widget in QApplication.topLevelWidgets()
            if widget is not window and widget.isVisible()
        ],
        "renderer": _renderer(window),
        "log": str(log_path()),
        # Gibt die eigene Datei zurück; eingerichtet ist sie seit dem Start.
        "crash_file": str(install_crash_logging() or ""),
        "helpers": [child.pid for child in multiprocessing.active_children()],
        # Was der Paketbau an Eingabemodulen mitnahm (RM-062): Ohne IBus-Modul
        # tippt ein Fcitx-Nutzer unter Linux ins Leere, und die Abhilfe in
        # ``qt_platform`` schaltet sich still ab.
        "input_modules": list(input_modules()),
        # Was das Paket aus einem Slicer-AppImage entpacken kann (RM-549, RM-599):
        # Ohne ``_zstd`` sieht ein Kunde unter Linux keinen Drucker der Orca-Familie.
        "image_compressions": list(readable_compressions()),
    }


def _renderer(window: Any) -> dict[str, Any]:
    """Ob die 3D-Ansicht zeichnet: ein Bild auf der Grafikkarte, zurückgelesen."""
    renderer = getattr(getattr(window, "viewport", None), "renderer", None)
    if renderer is None:
        return {"present": False}
    try:
        image = renderer.screenshot()
    except Exception as problem:
        return {"present": True, "kind": type(renderer).__name__, "error": repr(problem)}
    return {
        "present": True,
        "kind": type(renderer).__name__,
        "size": [int(image.shape[1]), int(image.shape[0])],
        "brightest": int(image.max()),
    }


def _close_everything() -> None:
    """Wie ein Mensch: erst offene Dialoge abbrechen, dann die Fenster schließen.

    Geschlossen wird erst in der Hauptschleife — der Erstlauf steht in einer
    eigenen (``QDialog.exec``), und ein letztes Fenster, das dort zugeht,
    beendet eine Schleife, die noch gar nicht läuft.
    """
    from PySide6.QtCore import QThread, QTimer
    from PySide6.QtWidgets import QApplication, QDialog

    modal = QApplication.activeModalWidget()
    if modal is not None:
        if isinstance(modal, QDialog):
            modal.reject()
        else:
            modal.close()
        QTimer.singleShot(DIALOG_RETRY_MS, _close_everything)
        return
    if QThread.currentThread().loopLevel() != 1:
        QTimer.singleShot(DIALOG_RETRY_MS, _close_everything)
        return
    QApplication.closeAllWindows()
