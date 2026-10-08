"""Native Fenster im Kindprozess: ob dieser Rechner überhaupt eines zeigt.

Wenige Tests zeigen in einem eigenen Prozess ein Fenster auf der echten
Plattform (``windows``, ``cocoa``, ``xcb``) statt offscreen. Auf dem
Intel-Mac-Läufer von GitHub (``macos-26-intel``) kommt schon ein leeres
cocoa-Fenster mit einem Eingabefeld nach ``activateWindow`` nicht mehr aus
``processEvents`` zurück — ohne Renderer und ohne eine Zeile Solidon
(Sonden 37620161097, 37620864200, 37629507477). Dieselbe VM startet das
gebaute Paket deshalb ohne Bildschirm (``build.yml``, „Anwendung im Paket
starten“). Die Tests liefen dort bis zu ihrer Frist und fielen rot, ohne
etwas über Solidon zu sagen.

:func:`require_native_window` zeigt darum einmal je Prozess ein leeres
Fenster vor. Hängt es, überspringt sich der Fall mit Grund — außerhalb der
CI und in der CI nur auf dem Intel-Mac. Auf jeder anderen Plattform der CI
ist derselbe Befund rot: Dort laufen die Fälle, und ein Skip verdeckte,
dass sie es nicht mehr tun. Ein Absturz ist kein Hängen; dann laufen die
Fälle und zeigen ihren eigenen Fehler.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import Final

import pytest

#: Frist für das leere Fenster vom Start des Prozesses bis nach
#: ``processEvents``. Wo es geht, braucht die erste Runde unter einer halben
#: Sekunde; der Rest ist der Import von PySide6 auf einem kalten Läufer.
PROBE_SECONDS: Final = 20.0

#: Das Fenster der Sonde 37629507477 ohne Renderer. Jede Stufe meldet sich,
#: damit ein Abbruch sagt, wo er stand.
_PROBE: Final = """
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget
application = QApplication([])
window = QWidget()
window.resize(320, 240)
QVBoxLayout(window).addWidget(QLineEdit(window))
window.show()
print("gezeigt", flush=True)
window.activateWindow()
print("aktiviert", flush=True)
for _ in range(5):
    application.processEvents()
print("fertig", flush=True)
window.close()
"""

#: Wo das Fenster hing, nach der letzten Meldung des Kindprozesses.
_WHERE: Final = {
    "": "beim Aufbau",
    "gezeigt": "in activateWindow",
    "aktiviert": "in processEvents",
    "fertig": "beim Beenden",
}

#: Antwort je Plattform, einmal je Prozess gefragt; ``None``: Das Fenster kam durch.
_ANSWERS: dict[str, str | None] = {}


def native_platform() -> str:
    """Die Qt-Plattform, die die Anwendung auf diesem Betriebssystem bekommt."""
    return {"win32": "windows", "darwin": "cocoa"}.get(sys.platform, "xcb")


def may_skip_here() -> bool:
    """Ob ein hängendes Fenster hier ein Skip sein darf: außerhalb der CI
    immer, in der CI nur auf dem Intel-Mac."""
    if not os.environ.get("CI"):
        return True
    return sys.platform == "darwin" and platform.machine() == "x86_64"


def window_problem(qt_platform: str) -> str | None:
    """Der Grund, aus dem hier kein natives Fenster durchkommt, oder ``None``."""
    if qt_platform not in _ANSWERS:
        _ANSWERS[qt_platform] = _probe(qt_platform)
    return _ANSWERS[qt_platform]


def found_problems() -> tuple[str, ...]:
    """Was die Vorprüfung in diesem Prozess gefunden hat, für den Schluss des Laufs."""
    return tuple(problem for problem in _ANSWERS.values() if problem)


def _probe(qt_platform: str) -> str | None:
    try:
        subprocess.run(
            [sys.executable, "-c", _PROBE],
            env={**os.environ, "QT_QPA_PLATFORM": qt_platform},
            capture_output=True,
            text=True,
            timeout=PROBE_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as hanging:
        # Nach dem Abbruch kommt die Ausgabe als Bytes, auch mit ``text=True``.
        output = hanging.stdout or b""
        text = output.decode("utf-8", "replace") if isinstance(output, bytes) else output
        stages = text.split()
        where = _WHERE.get(stages[-1] if stages else "", "beim Aufbau")
        return (
            f"dieser Läufer zeigt kein natives Fenster: ein leeres {qt_platform}-Fenster "
            f"hing {where} (Frist {PROBE_SECONDS:g} s, tests/native_window_probe.py)"
        )
    return None


def require_native_window() -> str:
    """Die Qt-Plattform für ein natives Fenster im Kindprozess — oder Skip oder Fehler mit Grund."""
    qt_platform = native_platform()
    if qt_platform == "xcb" and not os.environ.get("DISPLAY"):
        if os.environ.get("CI"):
            pytest.fail("Der native Linux-Fenstertest braucht DISPLAY, zum Beispiel durch Xvfb.")
        pytest.skip("kein X11-Display für den nativen Qt-Fensterweg")
    problem = window_problem(qt_platform)
    if problem is None:
        return qt_platform
    if may_skip_here():
        pytest.skip(problem)
    pytest.fail(
        f"{problem}. In der CI darf nur der Intel-Mac-Läufer native Fenster überspringen; "
        f"hier ({sys.platform}, {platform.machine()}) liefen sie bisher — "
        "das Protokoll des Läufers und das Runner-Bild prüfen."
    )
