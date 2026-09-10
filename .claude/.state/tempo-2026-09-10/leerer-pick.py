"""Baut ein Pick auf der leeren Szene schon die Pipeline auf?

Wenn ja, gehört das Aufwärmen an den Programmstart und nicht an den ersten
Szenenaufbau mit Körpern — dann ist es fertig, bevor der Kunde ein Modell
überhaupt geöffnet hat.
"""

import os
import sys
import time
from pathlib import Path

# Die Projektwurzel aus dem eigenen Ort, nicht als fester Pfad: Der
# Prüfstand liegt in ``.claude/.state/<name>/``, also drei Ebenen darunter.
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
for _ in range(10):
    application.processEvents()
    time.sleep(0.01)

ansicht = fenster.viewport
renderer = ansicht.renderer
LOG.write(f"Renderer: {type(renderer).__name__ if renderer else 'KEINER'}\n")
if renderer is None:
    LOG.close()
    raise SystemExit(0)

breite, hoehe = renderer.view_size()
LOG.write(f"Bild: {breite}x{hoehe}, Körper in der Szene: 0\n")

start = time.perf_counter()
renderer.pick_surface(breite / 2.0, hoehe / 2.0)
leer = (time.perf_counter() - start) * 1000.0
LOG.write(f"Pick auf leerer Szene: {leer:.1f} ms\n")

# Jetzt das Modell öffnen und sofort picken.
fenster.open_path(WURZEL / "tests" / "data" / "projects" / "drilled_v6.p3d")
frist = time.time() + 60
while time.time() < frist and not fenster.session.last_result:
    application.processEvents()
    time.sleep(0.01)
for _ in range(20):
    application.processEvents()
    time.sleep(0.005)

breite, hoehe = renderer.view_size()
start = time.perf_counter()
renderer.pick_surface(breite / 2.0, hoehe / 2.0)
voll = (time.perf_counter() - start) * 1000.0
LOG.write(f"Pick nach dem Öffnen:  {voll:.1f} ms\n")
LOG.write("\n")
LOG.write(
    "Ist der erste Wert groß und der zweite klein, wärmt die leere Szene bereits auf.\n"
)
LOG.close()
application.quit()
