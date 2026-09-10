"""Wo geht die Zeit beim Bewegen hin?

Robert, 09.09.2026: „ein bisschen performanceprobleme beim [bewegen] haben wir
auch noch". Gemessen wird am **echten** Fenster — offscreen gibt es keinen
Renderer, und dann misst man den Rückfall statt der Sache. ``WA_DontShowOnScreen``
hält es dabei von Roberts Bildschirm fern.

Gemessen wird je Zeigerereignis, getrennt nach Weg: die Kamera drehen, die
Kamera schieben, und die blosse Bewegung ohne Taste (Hover).
"""

import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# Die Projektwurzel aus dem eigenen Ort, nicht als fester Pfad: Der
# Prüfstand liegt in ``.claude/.state/<name>/``, also drei Ebenen darunter.
WURZEL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WURZEL))
os.environ.pop("QT_QPA_PLATFORM", None)

LOG = Path(sys.argv[1]).open("w", encoding="utf-8", buffering=1)


def sag(text: str = "") -> None:
    LOG.write(text + "\n")


from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.ui.app import build_application
from app.ui.render.api import PointerEvent

load_operations()

zeiten: dict[str, list[float]] = defaultdict(list)


def messe(name, fn):
    """Legt eine Stoppuhr um eine Methode."""

    def gemessen(*args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            zeiten[name].append((time.perf_counter() - start) * 1000.0)

    return gemessen


application, fenster = build_application([])
fenster.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
fenster.show()
for _ in range(10):
    application.processEvents()
    time.sleep(0.01)

projekt = WURZEL / "tests" / "data" / "projects" / "drilled_v6.p3d"
sag(f"Projekt: {projekt.name}")
fenster.open_path(projekt)
frist = time.time() + 60
while time.time() < frist and not fenster.session.last_result:
    application.processEvents()
    time.sleep(0.01)

ansicht = fenster.viewport
sag(f"Renderer: {type(ansicht.renderer).__name__ if ansicht.renderer else 'KEINER'}")
ergebnis = fenster.session.last_result
if ergebnis is not None:
    koerper = list(ergebnis.scene.objects.values())
    dreiecke = sum(len(k.mesh.raw.faces) for k in koerper)
    sag(f"Körper: {len(koerper)}, Dreiecke: {dreiecke}")

# Die Stoppuhren an die Stellen, die jede Bewegung durchläuft.
ansicht._on_pointer = messe("Viewport._on_pointer", ansicht._on_pointer)
ansicht._draw = messe("Viewport._draw", ansicht._draw)
ansicht._note_pointer = messe("Viewport._note_pointer", ansicht._note_pointer)
ansicht._order_by_depth = messe("Viewport._order_by_depth", ansicht._order_by_depth)
ansicht._redraw_shadows = messe("Viewport._redraw_shadows", ansicht._redraw_shadows)
if ansicht._navigator is not None:
    ansicht._navigator.handle = messe("Navigator.handle", ansicht._navigator.handle)
ansicht._aim_rotation = messe("Viewport._aim_rotation", ansicht._aim_rotation)
ansicht.centre_hit = messe("Viewport.centre_hit", ansicht.centre_hit)
ansicht._world_at = messe("Viewport._world_at", ansicht._world_at)
if ansicht.renderer is not None:
    ansicht.renderer.render = messe("Renderer.render", ansicht.renderer.render)
    for name in ("pick_surface", "pick_item", "view_size"):
        wenn = getattr(ansicht.renderer, name, None)
        if wenn is not None:
            setattr(ansicht.renderer, name, messe(f"Renderer.{name}", wenn))


def fahre(name: str, kind_folge, taste=None):
    """Eine Geste über die Mitte des Bildes, Ereignis für Ereignis."""
    zeiten.clear()
    for x, y, kind, buttons in kind_folge:
        ansicht._on_pointer(
            PointerEvent(kind, x, y, button=taste, buttons=buttons)
        )
        application.processEvents()
    sag("")
    sag(f"--- {name} ---")
    for schluessel in sorted(zeiten, key=lambda s: -sum(zeiten[s])):
        werte = sorted(zeiten[schluessel])
        gesamt = sum(werte)
        mitte = werte[len(werte) // 2]
        sag(
            f"  {schluessel:28s} {len(werte):4d}x  "
            f"Median {mitte:7.2f} ms  Höchst {werte[-1]:7.2f} ms  Summe {gesamt:8.1f} ms"
        )


SCHRITTE = 40
links = frozenset({"left"})
rechts = frozenset({"right"})


def dreh_folge():
    return (
        [(400, 300, "press", frozenset())]
        + [(400 + i * 4, 300 + i, "move", rechts) for i in range(SCHRITTE)]
        + [(400 + SCHRITTE * 4, 300 + SCHRITTE, "release", frozenset())]
    )


def einzeln(name: str, folge, taste=None):
    """Jede Zeit einzeln — ein Ausreißer beim ersten Ereignis ist ein Aufwärmen,
    einer in der Mitte ist ein Fehler."""
    zeiten.clear()
    for x, y, kind, buttons in folge:
        ansicht._on_pointer(PointerEvent(kind, x, y, button=taste, buttons=buttons))
        application.processEvents()
    werte = zeiten.get("Viewport._on_pointer", [])
    auffaellig = [(i, w) for i, w in enumerate(werte) if w > 5.0]
    sag(f"  {name}: {len(werte)} Ereignisse, über 5 ms: {auffaellig}")


# **Eine Sekunde hinsehen, bevor die erste Geste kommt.** So schnell ist kein
# Mensch — und genau in dieser Spanne soll das Aufwärmen laufen.
warm_start = time.time()
while time.time() - warm_start < 1.0:
    application.processEvents()
    time.sleep(0.005)

# **Der erste Klick vor jeder Drehung** — trägt er dieselbe Bremse?
zeiten.clear()
ansicht._on_pointer(PointerEvent("press", 400, 300, button="left", buttons=frozenset()))
ansicht._on_pointer(PointerEvent("release", 400, 300, button="left", buttons=frozenset()))
application.processEvents()
sag("")
sag("--- Der allererste Klick ---")
for schluessel in sorted(zeiten, key=lambda s: -sum(zeiten[s])):
    werte = zeiten[schluessel]
    sag(f"  {schluessel:28s} {len(werte):3d}x  Summe {sum(werte):8.1f} ms")

sag("")
sag("--- Drei Drehgesten nacheinander (Zeiten je Ereignis) ---")
for runde in range(3):
    einzeln(f"Runde {runde + 1}", dreh_folge(), taste="right")


# 1. Nur bewegen, keine Taste — der Hover-Weg.
folge = [(400 + i * 4, 300, "move", frozenset()) for i in range(SCHRITTE)]
fahre("Zeiger bewegen (ohne Taste)", folge)

# 2. Drehen: rechte Taste gedrückt ziehen.
folge = (
    [(400, 300, "press", frozenset())]
    + [(400 + i * 4, 300 + i, "move", rechts) for i in range(SCHRITTE)]
    + [(400 + SCHRITTE * 4, 300 + SCHRITTE, "release", frozenset())]
)
fahre("Kamera drehen (rechts ziehen)", folge, taste="right")

# 3. Schieben: linke Taste gedrückt ziehen.
folge = (
    [(400, 300, "press", frozenset())]
    + [(400 + i * 4, 300 + i, "move", links) for i in range(SCHRITTE)]
    + [(400 + SCHRITTE * 4, 300 + SCHRITTE, "release", frozenset())]
)
fahre("Kamera schieben (links ziehen)", folge, taste="left")

sag("")
sag("Fertig.")
LOG.close()
QTimer.singleShot(0, application.quit)
application.quit()
