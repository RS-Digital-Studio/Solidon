"""Wächst der Speicher mit der Bedienung? Auswahl, Griffe, Projektwechsel.

Gemessen wird der Arbeitssatz des Prozesses (RSS) nach je einer Runde, dazu
die Zahl der lebenden Python-Objekte. Ein linearer Anstieg über die Runden ist
ein Leck; ein Plateau ist keines.
"""

import gc
import os
import sys
import time
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WURZEL))
os.environ.pop("QT_QPA_PLATFORM", None)
LOG = Path(sys.argv[1]).open("w", encoding="utf-8", buffering=1)

import tracemalloc

from PySide6.QtCore import Qt

from app.core.bootstrap import load_operations
from app.ui.app import build_application
from app.ui.render.api import PointerEvent


def rss() -> float:
    """Der von Python belegte Speicher in MB — ohne fremdes Paket."""
    belegt, _hoechst = tracemalloc.get_traced_memory()
    return belegt / (1024 * 1024)


def ruhe(application, sekunden: float = 0.2) -> None:
    frist = time.time() + sekunden
    while time.time() < frist:
        application.processEvents()
        time.sleep(0.005)


tracemalloc.start()
load_operations()
application, fenster = build_application([])
fenster.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
fenster.show()
ruhe(application, 1.0)

projekt = WURZEL / "tests" / "data" / "projects" / "drilled_v6.p3d"
fenster.open_path(projekt)
frist = time.time() + 60
while time.time() < frist and not fenster.session.last_result:
    application.processEvents()
    time.sleep(0.01)
ruhe(application, 1.0)
ansicht = fenster.viewport
ergebnis = fenster.session.last_result
koerper = list(ergebnis.scene.objects) if ergebnis else []
LOG.write(f"Körper: {koerper}\n")

gc.collect()
LOG.write(f"Start: {rss():.1f} MB, {len(gc.get_objects())} Objekte\n")

# --- 1. Zwanzig Auswahlwechsel ---------------------------------------------
for runde in range(20):
    ansicht.select(koerper[0] if runde % 2 == 0 else None)
    ruhe(application, 0.02)
    if runde in (4, 9, 19):
        gc.collect()
        LOG.write(f"Auswahl {runde + 1:2d}: {rss():.1f} MB, {len(gc.get_objects())} Objekte\n")

# --- 2. Zwanzig Zeigerzyklen (drücken, ziehen, loslassen) ------------------
links = frozenset({"left"})
for runde in range(20):
    ansicht._on_pointer(PointerEvent("press", 80, 80, button="left", buttons=frozenset()))
    for schritt in range(5):
        ansicht._on_pointer(PointerEvent("move", 80 + schritt * 3, 80 + schritt, buttons=links))
    ansicht._on_pointer(PointerEvent("release", 95, 85, button="left", buttons=frozenset()))
    ruhe(application, 0.02)
    if runde in (4, 9, 19):
        gc.collect()
        LOG.write(f"Griffzyklus {runde + 1:2d}: {rss():.1f} MB, {len(gc.get_objects())} Objekte\n")

# --- 3. Zehn Projektwechsel ------------------------------------------------
zweites = WURZEL / "tests" / "data" / "projects"
kandidaten = sorted(p for p in zweites.glob("*.p3d"))[:2]
LOG.write(f"Projekte: {[p.name for p in kandidaten]}\n")
for runde in range(10):
    fenster.open_path(kandidaten[runde % len(kandidaten)])
    frist = time.time() + 60
    while time.time() < frist and not fenster.session.last_result:
        application.processEvents()
        time.sleep(0.01)
    ruhe(application, 0.2)
    if runde in (2, 5, 9):
        gc.collect()
        LOG.write(f"Projekt {runde + 1:2d}: {rss():.1f} MB, {len(gc.get_objects())} Objekte\n")

LOG.close()
