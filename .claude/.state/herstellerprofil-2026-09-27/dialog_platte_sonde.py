"""Sonde: Review Stufe A+B, R4 — die Plattenwahl im Druckdialog (offscreen).

Bambu Studio, P1S, Bambu PLA Basic: Die Wahl zeigt die Platten, für die das
Filament eine Betttemperatur nennt, wählt Bambus Standardplatte vor, und eine
andere Wahl ändert Grundlage, Betttemperatur und Satz.

Aufruf: python dialog_platte_sonde.py <code-wurzel>
"""

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
scratch = Path(tempfile.mkdtemp(prefix="dialog-platte-sonde-"))
os.environ["APPDATA"] = str(scratch / "appdata")
os.environ["LOCALAPPDATA"] = str(scratch / "local")

import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import discover  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.ui.print_settings_dialog import PrintSettingsDialog  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

qt = QApplication.instance() or QApplication([])


def settle(check, seconds: float = 120.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + seconds
    while not check() and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.05)
    assert check(), "Zeitlimit"


discover.remember_path("slicer", r"C:\Program Files\Bambu Studio\bambu-studio.exe")
session = Session()
session.change_scene_profile("bambu-p1s", "pla")
assert session.wait_for_idle()
dialog = PrintSettingsDialog(session, UiSettings())
assert dialog.wait_for_slicers()
settle(lambda: bool(dialog._profiles) and dialog._foundation is not None)
box = dialog.bed_plate_choice
items = [(box.itemText(i), box.itemData(i)) for i in range(box.count())]
print("Platten:", items)
print("vorgewählt:", box.currentData(), "| sichtbar:", not box.isHidden())
print("Grundlage:", dialog.foundation_note.text(), "| Bett", dialog.settings.temperature.bed)
assert not box.isHidden() and box.count() > 1
before = dialog.settings.temperature.bed
index = box.findData("Cool Plate")
assert index >= 0, "Bambu PLA nennt die kühle Platte"
box.setCurrentIndex(index)
box.activated.emit(index)
qt.processEvents()
settle(lambda: dialog._foundation is not None and dialog._foundation.plate == "Cool Plate")
print("nach der Wahl:", dialog.foundation_note.text(), "| Bett", dialog.settings.temperature.bed)
assert dialog.settings.temperature.bed != before
assert "Kühle Platte" in dialog.foundation_note.text()
assert dialog._current_setup().plate == "Cool Plate"
print("Sonde bestanden.")
dialog.done(0)
dialog.release()
