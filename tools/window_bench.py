"""Misst das Öffnen eines Beispielprojekts im echten Fenster, in Bestandteilen.

Warum es das Werkzeug gibt: Offscreen prüft nichts, was am Aktor hängt —
``Viewport.show_scene`` kehrt dort vor dem Aktoraufbau zurück, und jede
Zusage über Renderer, Aktoren oder Bildaufbau ist grün über einer leeren Menge.
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

**Und seit dem 05.09.2026 misst es den Renderer**: nach dem Öffnen den
Arbeitsspeicher des Prozesses, dann ``--drag-frames`` Kamerastellungen rund
um den Blickpunkt über ``Viewport.set_camera_pose`` — jede mit Bild, Schatten
und Ereignissen, also das, was ein Zug am Körper je Bildpunkt kostet — als
Median und Maximum je Bild, und zuletzt ein Bild ohne Kameraänderung. Mit
dieser Tabelle fiel am 06.09.2026 die Entscheidung für pygfx; der
VTK-Renderer ist seither ausgebaut.

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


def working_set_mb() -> float:
    """Der Arbeitsspeicher dieses Prozesses in MiB — Windows über psapi, sonst
    über ``/proc``; ohne beides eine Zahl, die keiner ist."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        if not psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            return float("nan")
        return float(counters.WorkingSetSize) / 2**20
    try:
        with Path("/proc/self/status").open(encoding="utf-8") as status:
            for line in status:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except OSError:
        pass
    return float("nan")


def drag_frames(window: Any, application: Any, count: int) -> list[float]:
    """``count`` Kamerastellungen rund um den Blickpunkt, je eine mit Bild.

    Über ``Viewport.set_camera_pose`` — denselben Weg, den die 3D-Maus und
    die Kameravorgaben gehen: Bild, Schattenwurf, ``cameraMoved`` und die
    Qt-Ereignisse danach zählen mit. Zurück kommt die Zeit je Stellung.
    """
    import math

    view = window.viewport
    if view.renderer is None or count <= 0:
        return []
    position, focal, _up, _scale = view.camera_pose()
    offset = tuple(p - f for p, f in zip(position, focal, strict=True))
    radius = math.hypot(offset[0], offset[1])
    height = offset[2]
    base = math.atan2(offset[1], offset[0])
    times: list[float] = []
    for step in range(count):
        angle = base + 2.0 * math.pi * (step + 1) / count
        moved = (
            focal[0] + radius * math.cos(angle),
            focal[1] + radius * math.sin(angle),
            focal[2] + height,
        )
        begin = time.perf_counter()
        view.set_camera_pose(moved, focal, (0.0, 0.0, 1.0))
        application.processEvents()
        times.append(time.perf_counter() - begin)
    view.set_camera_pose(position, focal, (0.0, 0.0, 1.0))
    application.processEvents()
    return times


def shutdown_window(window: Any, application: Any) -> None:
    """Beendet Arbeiter, Renderer und Qt in ihrer sicheren Besitzreihenfolge.

    Das Fenster besitzt die Grafikfläche des Renderers. Wird nur das
    Elternfenster geschlossen, räumt Python den noch lebenden Renderer erst
    beim Prozessende auf; zu diesem Zeitpunkt ist sein Grafikkontext nicht
    mehr verlässlich aktuell (mit VTK hieß das je nach Lauf „unvollständige
    Framebuffer"). Deshalb werden zuerst die Arbeiter und
    Sitzungsverbindungen gelöst, dann der Renderer bei noch lebendem Fenster
    geschlossen und zuletzt das Qt-Fenster.

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
        "--drag-frames",
        type=int,
        default=90,
        help="Kamerastellungen nach dem Öffnen, je eine mit Bild (0: keine)",
    )
    parser.add_argument(
        "--shot",
        type=Path,
        default=None,
        help="Bildschirmaufnahme des Fensters nach dem Öffnen (PNG) — was der Kunde sieht",
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
        # Ohne die Pause frisst diese Schleife den Interpreter, und der
        # Arbeiter, der die Auswertung rechnet, kommt nicht an den GIL — das
        # Öffnen stand dann bei „Quader anlegen 0 %" (05.09.2026).
        time.sleep(0.002)
        state = (dict(calls), dict(spent))
        if state != last_state:
            last_state = state
            quiet_since = time.perf_counter()
            continue
        quiet = time.perf_counter() - quiet_since
        # Fertig ist das Öffnen erst, wenn die Ansicht einmal gezeichnet hat:
        # ``open_project`` kehrt vor der Auswertung zurück, und unter Last
        # vergingen mehr als zwei ruhige Sekunden, bevor der erste Aufbau kam
        # — die Aufnahme zeigte dann „Projekt wird geladen" (05.09.2026).
        result = getattr(session, "last_result", None)
        loaded = result is not None and bool(getattr(result.scene, "objects", None))
        if calls.get("Session.open_project") and loaded and quiet > arguments.settle:
            break
    mark("auswertung+bild (bis ruhig)", since)
    renderer = getattr(window.viewport, "renderer", None)
    print(f"Renderer: {type(renderer).__name__}", flush=True)
    if arguments.shot is not None:
        # Vom Bildschirm, nicht aus dem Widget: ``grab()`` sähe an einer
        # nativen Grafikfläche nur Schwarz, gleich was darauf steht.
        screen = application.primaryScreen()
        picture = screen.grabWindow(int(window.winId()))
        arguments.shot.parent.mkdir(parents=True, exist_ok=True)
        picture.save(str(arguments.shot))
        image = picture.toImage()
        view = window.viewport
        origin = view.mapTo(window, view.rect().topLeft())
        ratio = float(picture.devicePixelRatio()) or 1.0
        samples = []
        for fx, fy in ((0.5, 0.5), (0.25, 0.25), (0.75, 0.75), (0.5, 0.2), (0.5, 0.8)):
            px = int((origin.x() + view.width() * fx) * ratio)
            py = int((origin.y() + view.height() * fy) * ratio)
            colour = image.pixelColor(px, py)
            samples.append((colour.red(), colour.green(), colour.blue()))
        print(f"Bildschirm ({arguments.shot.name}): Ansicht-Bildpunkte {samples}", flush=True)
    print(f"Arbeitsspeicher nach dem Öffnen: {working_set_mb():.0f} MiB", flush=True)
    frames = drag_frames(window, application, arguments.drag_frames)
    if frames:
        ordered = sorted(frames)
        print(
            f"Zug: {len(frames)} Stellungen, je Bild Median "
            f"{ordered[len(ordered) // 2] * 1000:.1f} ms, "
            f"Maximum {ordered[-1] * 1000:.1f} ms, gesamt {sum(frames):.2f} s",
            flush=True,
        )
        still = time.perf_counter()
        for _ in range(30):
            if renderer is not None:
                renderer.render()
            application.processEvents()
        print(
            f"Bild ohne Kameraänderung: {(time.perf_counter() - still) / 30 * 1000:.1f} ms",
            flush=True,
        )
        print(f"Arbeitsspeicher nach dem Zug: {working_set_mb():.0f} MiB", flush=True)

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
