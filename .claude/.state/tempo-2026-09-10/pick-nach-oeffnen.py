"""Was kostet der erste Pick, nachdem ein Modell im Bild steht?

Das Aufwärmen (:meth:`Viewport._warm_the_picker`) läuft einmal je Renderer auf
der **leeren** Szene. Diese Sonde fragt, was danach am geöffneten Modell
übrig bleibt: fünf Picks nacheinander, jeder einzeln gestoppt.
"""

import os
import sys
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WURZEL))
os.environ.pop("QT_QPA_PLATFORM", None)
LOG = Path(sys.argv[1]).open("w", encoding="utf-8", buffering=1)

from PySide6.QtCore import Qt

from app.core.bootstrap import load_operations
from app.ui.app import build_application

load_operations()
application, fenster = build_application([])
fenster.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
fenster.show()
warm = time.time()
while time.time() - warm < 1.0:
    application.processEvents()
    time.sleep(0.005)

ansicht = fenster.viewport
renderer = ansicht.renderer
LOG.write(f"Renderer: {type(renderer).__name__ if renderer else 'KEINER'}\n")
if renderer is None:
    LOG.close()
    raise SystemExit(0)

breite, hoehe = renderer.view_size()
start = time.perf_counter()
renderer.pick_surface(breite / 2.0, hoehe / 2.0)
LOG.write(f"Pick auf leerer Szene: {(time.perf_counter() - start) * 1000.0:.1f} ms\n")

fenster.open_path(WURZEL / "tests" / "data" / "projects" / "drilled_v6.p3d")
frist = time.time() + 60
while time.time() < frist and not fenster.session.last_result:
    application.processEvents()
    time.sleep(0.01)
ruhe = time.time()
while time.time() - ruhe < 1.0:
    application.processEvents()
    time.sleep(0.005)

ergebnis = fenster.session.last_result
if ergebnis is not None:
    dreiecke = sum(len(k.mesh.raw.faces) for k in ergebnis.scene.objects.values())
    LOG.write(f"Körper: {len(ergebnis.scene.objects)}, Dreiecke: {dreiecke}\n")

breite, hoehe = renderer.view_size()
werte = []
for _ in range(5):
    start = time.perf_counter()
    renderer.pick_surface(breite / 2.0, hoehe / 2.0)
    werte.append((time.perf_counter() - start) * 1000.0)
LOG.write("Picks am Modell: " + ", ".join(f"{v:.1f}" for v in werte) + " ms\n")

# Und nach einer Kamerabewegung — der Pickdurchgang ist dann ungültig.
renderer.orbit(12.0, 8.0) if hasattr(renderer, "orbit") else None
application.processEvents()
werte = []
for _ in range(3):
    start = time.perf_counter()
    renderer.pick_surface(breite / 2.0, hoehe / 2.0)
    werte.append((time.perf_counter() - start) * 1000.0)
LOG.write("Picks nach Kamerabewegung: " + ", ".join(f"{v:.1f}" for v in werte) + " ms\n")
LOG.close()
