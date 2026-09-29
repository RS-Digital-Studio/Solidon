"""Sonde: Review Stufe A+B, R7 — die Grundlage im Arbeiter, am Hauptfenster (offscreen).

1. Ein erster Aufruf von ``effective_print_settings`` kehrt sofort zurück, mit
   Solidons Tabelle, und startet den ``_FoundationWorker``.
2. Kommt seine Antwort, gilt Elegoos Profil (zwei Wände), und die Zahlenzeile
   ist erneuert.
3. Der Plattenrand der Sitzung (``split_margin``) rechnet mit derselben Quelle.

Aufruf: python fenster_grundlage_sonde.py <code-wurzel>
"""

import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
scratch = Path(tempfile.mkdtemp(prefix="fenster-grundlage-"))
os.environ["APPDATA"] = str(scratch / "appdata")
os.environ["LOCALAPPDATA"] = str(scratch / "local")

import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__
import app.ui  # noqa: E402,F401
from PySide6.QtWidgets import QApplication  # noqa: E402

application = QApplication([])

from app.core import discover  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.core.split import bed_margin  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

ELEGOO = Path(r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe")
discover.remember_path("slicer", str(ELEGOO))
settings = replace(
    UiSettings(),
    slicer_machine_profile="Elegoo Centauri Carbon 2 0.4 nozzle",
    slicer_base_process="0.20mm Standard @Elegoo CC2 0.4 nozzle",
    slicer_profile_printer="centauri-carbon-2",
)
session = Session()
window = MainWindow(session, settings)
window.open_path(ROOT / "tests" / "data" / "meshes" / "plate_holes.stl")
assert window.session.wait_for_idle()
if window.session.profile.printer.id != "centauri-carbon-2":
    window.session.change_scene_profile("centauri-carbon-2", "pla")
    assert window.session.wait_for_idle()
print("Drucker:", window.session.profile.printer.id, window.session.profile.material.id)

started = time.perf_counter()
first = window.effective_print_settings()
took = time.perf_counter() - started
print(f"erster Aufruf: {took * 1000:.0f} ms, Wände {first.shell.wall_count}")
deadline = time.monotonic() + 120
while window._foundation_pending is not None and time.monotonic() < deadline:
    application.processEvents()
    time.sleep(0.02)
assert window._foundation_pending is None, "der Arbeiter kam nicht zurück"
foundation = window._foundation_cache[1]
print("Grundlage:", foundation.process, "| aus dem Profil:", len(foundation.from_profile))
after = window.effective_print_settings()
print("danach: Wände", after.shell.wall_count, "| erste Schicht", after.layers.first_layer_height)
assert foundation.has_profile, "Elegoos Profil hätte die Grundlage sein sollen"
assert after.shell.wall_count == 2
margin = window.session.split_margin()
print("Plattenrand der Sitzung:", margin, "| aus dem wirksamen Satz:", bed_margin(after))
assert abs(margin - bed_margin(after)) < 1e-9
print("Sonde bestanden.")
window.close()
