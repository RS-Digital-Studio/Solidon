"""pytest-Erweiterung für die Jagd auf den Absturz beim Aufräumen.

    set QT_TRACE=...\\spur.txt
    .venv\\Scripts\\python.exe -m pytest -p tools.qt_trace tests/...

Der Absturz, der in `ROADMAP.md` unter „Der Absturz beim Aufräumen" steht,
kommt selten und nie an derselben Stelle: einmal in zwei Läufen über die
zweite Hälfte der Suite, und in zwölf Läufen derselben Einzeletappe gar
nicht. Wer ihn untersuchen will, braucht zwei Auskünfte, und beide gehen
ohne diese Datei verloren:

* **Was Qt zuletzt gesagt hat.** Eine Zugriffsverletzung reißt den Prozess ab,
  ohne seine Puffer zu leeren; eine Meldung auf stderr ist damit weg. Hier
  wird jede Zeile sofort geschrieben.
* **Wo es war.** ``faulthandler`` liefert den Python-Stapel, aber nur für den
  Faden, der stürzt. Die Kennung des laufenden Tests steht deshalb vor jedem
  Test in derselben Datei — nach dem Abbruch ist die letzte Zeile die Antwort.

Gefunden hat das den Stapel, der jetzt in der Roadmap steht: Der Nachfolge-
Arbeiter entsteht im ``finished``-Slot seines Vorgängers. Ob das die Ursache
ist, sagt erst ein Werkzeug, das doppelte Freigaben sieht — deshalb steht hier
ein Fänger und keine Änderung an der Auswertung (Regel 21).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_trace: Any = None


def pytest_configure(config: Any) -> None:
    """Die Spur eröffnen und Qts Meldungen umleiten."""
    global _trace
    target = Path(os.environ.get("QT_TRACE") or "qt-trace.txt")
    _trace = target.open("w", encoding="utf-8", buffering=1)
    _trace.write("--- trace opened\n")

    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    names = {
        QtMsgType.QtDebugMsg: "debug",
        QtMsgType.QtInfoMsg: "info",
        QtMsgType.QtWarningMsg: "warning",
        QtMsgType.QtCriticalMsg: "critical",
        QtMsgType.QtFatalMsg: "FATAL",
    }

    def caught(mode: Any, context: Any, message: str) -> None:
        if _trace is not None:
            _trace.write(f"[qt {names.get(mode, mode)}] {message}\n")

    qInstallMessageHandler(caught)


def pytest_runtest_logstart(nodeid: str, location: Any) -> None:
    """Vor jedem Test seine Kennung — die letzte Zeile ist die Antwort."""
    if _trace is not None:
        _trace.write(f"> {nodeid}\n")


def pytest_unconfigure(config: Any) -> None:
    """Ein regulärer Schluss steht auch dann da, wenn nichts passiert ist."""
    if _trace is not None:
        _trace.write("--- trace closed regularly\n")
        _trace.close()
