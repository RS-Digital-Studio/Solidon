"""Misst das Öffnen eines Beispielprojekts im echten Fenster, in Bestandteilen.

Warum es das Werkzeug gibt: Offscreen prüft nichts, was am Aktor hängt —
``Viewport.show_scene`` kehrt dort vor dem Aktoraufbau zurück, und jede
Zusage über VTK, Aktoren oder Bildaufbau ist grün über einer leeren Menge.
Genau deshalb stand „``weg4-figur-formen`` kostet 56 Sekunden, und keine
davon liegt im Kern" monatelang ohne Messweg im Register: offscreen öffnete
dasselbe Projekt in 0,82 s. Dieses Werkzeug öffnet das Projekt so, wie der
Kunde es tut — echtes Fenster, maximiert — und zerlegt die Wartezeit in
benannte Posten (Fensterbau, Laden, Auswertung samt Bild).

    python tools/window_bench.py                          # weg4-figur-formen
    python tools/window_bench.py dose-mit-deckel          # ein anderes Beispiel
    python tools/window_bench.py --settle 8               # längere Ruhe-Schwelle

Gemessen am 30.08.2026 (maximiert, warmes Messprofil): ``weg4-figur-formen``
6,1 s · ``weg3-generiert-aufbereiten`` 5,8 s · ``dose-mit-deckel`` 4,4 s —
die 56/145/13 s vom 26.08.2026 sind mit der vektorisierten Zuordnung und den
Folgearbeiten gefallen. Eine Kontrollmessung mit 8 s Ruhe-Schwelle ergab
identische Methodenzähler: nach zwei ruhigen Sekunden kommt nichts mehr nach.

Drei Eigenheiten, alle drei aus den bekannten Prüfstand-Fallen:

* **Eigenes Messprofil** (``--profile``, Vorgabe neben dem Werkzeug): §38
  gilt auch für Messungen, und der erste Lauf in einem frischen Profil misst
  die Ersteinrichtung mit — wer vergleichbare Zahlen will, misst ab dem
  zweiten Lauf im selben Profil.
* **Modale Dialoge und Popups werden geschlossen und gezählt** — ein
  Prüfstand, der auf einen Dialog wartet, sieht aus wie ein Hänger.
* **Das Fenster läuft maximiert.** Ein winziges Fenster rendert anders und
  meldete im Versuch Framebuffer-Fehler, die es maximiert nicht gibt.

Kein Testlauf und kein Teil der Suite: Das Werkzeug öffnet ein sichtbares
Fenster auf dem Bildschirm der Maschine, auf der es läuft.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EVENT_DRAIN_ROUNDS = 20


def isolate(profile: Path) -> None:
    """Biegt die Nutzerverzeichnisse in das Messprofil um (§38)."""
    profile.mkdir(parents=True, exist_ok=True)
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "HOME",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        os.environ[variable] = str(profile)


def shutdown_window(window: Any, application: Any) -> None:
    """Beendet Arbeiter, VTK und Qt in ihrer sicheren Besitzreihenfolge.

    Das Fenster besitzt den ``QtInteractor``. Wird nur das Elternfenster
    geschlossen, räumt Python den noch lebenden VTK-Plotter erst beim
    Prozessende auf; zu diesem Zeitpunkt ist sein Qt-OpenGL-Kontext nicht mehr
    verlässlich aktuell. VTK meldet dann je nach Lauf unvollständige
    Framebuffer. Deshalb werden zuerst die Arbeiter und Sitzungsverbindungen
    gelöst, dann der Plotter bei noch lebendem Fenster geschlossen und zuletzt
    das Qt-Fenster.

    ``MainWindow.release`` schließt den Viewport absichtlich nicht: In der
    Anwendung kann im selben Prozess ein weiteres Fenster folgen. Dieser
    Prüfstand endet dagegen nach genau einem Fenster und ruft deshalb
    denselben terminalen Viewport-Weg wie ``MainWindow.closeEvent``.
    """
    window.release()
    window.viewport.release_renderer()
    window.close()
    for _ in range(EVENT_DRAIN_ROUNDS):
        application.processEvents()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("example", nargs="?", default="weg4-figur-formen")
    parser.add_argument(
        "--settle",
        type=float,
        default=2.0,
        help="Sekunden ohne Methodenarbeit, ab denen das Öffnen als fertig gilt",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "tools" / ".window-bench-profile",
        help="Messprofil für die Nutzerverzeichnisse (bleibt zwischen Läufen)",
    )
    arguments = parser.parse_args()
    isolate(arguments.profile)
    sys.path.insert(0, str(ROOT))

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    wall = time.perf_counter()
    application = QApplication([])

    from app.core import bootstrap

    since = time.perf_counter()
    bootstrap.load_operations()

    def mark(name: str, begin: float) -> float:
        now = time.perf_counter()
        print(f"{name}: {now - begin:.2f} s (Wanduhr {now - wall:.2f})", flush=True)
        return now

    since = mark("bootstrap", since)

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.viewport import Viewport

    since = mark("ui-importe", since)

    # Kumulierte Methodenzeiten: Wer trägt wie viel zur Wartezeit bei? Die
    # Ruhe-Erkennung unten hängt an denselben Zählern — solange irgendeine
    # gewrappte Methode arbeitet, ist das Öffnen nicht fertig.
    spent: dict[str, float] = {}
    calls: dict[str, int] = {}

    def wrap(cls: type, name: str) -> None:
        original = getattr(cls, name)

        def timed(self: object, *args: object, **kwargs: object) -> object:
            begin = time.perf_counter()
            try:
                return original(self, *args, **kwargs)
            finally:
                key = f"{cls.__name__}.{name}"
                spent[key] = spent.get(key, 0.0) + (time.perf_counter() - begin)
                calls[key] = calls.get(key, 0) + 1

        setattr(cls, name, timed)

    wrap(Viewport, "show_scene")
    wrap(Session, "open_project")
    wrap(Session, "evaluate_now")

    closed: list[str] = []

    def sweep() -> None:
        widget = application.activeModalWidget()
        if widget is not None:
            closed.append(type(widget).__name__)
            widget.close()
        popup = application.activePopupWidget()
        if popup is not None:
            closed.append(f"popup:{type(popup).__name__}")
            popup.close()

    sweeper = QTimer()
    sweeper.timeout.connect(sweep)
    sweeper.start(500)

    session = Session()
    window = MainWindow(session, UiSettings())
    since = mark("fensterbau", since)

    window.showMaximized()
    for _ in range(20):
        application.processEvents()
    since = mark("anzeigen", since)

    window.open_path(ROOT / "app" / "examples" / f"{arguments.example}.p3d")
    since = mark("open_path (Rückkehr)", since)

    deadline = time.perf_counter() + 240.0
    last_state = (dict(calls), dict(spent))
    quiet_since = time.perf_counter()
    while time.perf_counter() < deadline:
        application.processEvents()
        state = (dict(calls), dict(spent))
        if state != last_state:
            last_state = state
            quiet_since = time.perf_counter()
            continue
        quiet = time.perf_counter() - quiet_since
        if calls.get("Session.open_project") and quiet > arguments.settle:
            break
    mark("auswertung+bild (bis ruhig)", since)

    print("\nMethodenzeiten, kumuliert:", flush=True)
    for key in sorted(spent, key=lambda entry: spent[entry], reverse=True):
        print(f"  {key}: {spent[key]:.2f} s in {calls[key]} Aufruf(en)", flush=True)
    print(f"Geschlossene Dialoge/Popups: {', '.join(closed) or 'keine'}", flush=True)
    total = time.perf_counter() - wall
    print(f"GESAMT: {total:.2f} s (davon {arguments.settle:.0f} s Ruhe-Schwelle)", flush=True)

    shutdown_window(window, application)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
