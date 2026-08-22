"""Die echte Anwendung starten und aufnehmen — Startbildschirm und leeres Projekt.

Kein Testaufbau: derselbe Weg wie ``python -m app.ui.app``, nur ohne
Ereignisschleife am Ende. Gemessen wird auch die Zeit bis zum Fenster.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\rober\Documents\Solidon")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

BEGIN = time.perf_counter()


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from app.ui.app import build_application

    steps: list[tuple[str, float]] = []

    def progress(text: str, share: float) -> None:
        steps.append((text, time.perf_counter() - BEGIN))

    app, window = build_application([], progress=progress)
    built = time.perf_counter() - BEGIN
    window.show()
    for _ in range(60):
        app.processEvents()
    shown = time.perf_counter() - BEGIN
    print(f"gebaut nach {built:.2f} s, sichtbar nach {shown:.2f} s")
    for text, when in steps:
        print(f"  {when:5.2f} s  {text}")
    print(f"Fenstergroesse: {window.width()}x{window.height()}")

    window.grab().save(str(OUT / "app-start.png"))

    # Neues Projekt: der leere Zustand, den ein Demonutzer als Erstes sieht.
    window.start_empty()
    for _ in range(80):
        app.processEvents()
    time.sleep(0.5)
    for _ in range(80):
        app.processEvents()
    window.grab().save(str(OUT / "app-leer.png"))
    print("leeres Projekt aufgenommen")

    QApplication.processEvents()
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
