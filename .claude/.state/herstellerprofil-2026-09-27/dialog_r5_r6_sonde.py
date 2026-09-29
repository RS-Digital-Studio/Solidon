"""Sonde: Review Stufe A+B — R6, F4 und R5 im Druckdialog (offscreen).

R6: Ein Stufenwechsel nimmt die eigene Wahl an der Wandzahl zurück (sie gehört
    zur Stufe) und behält die an der Düsentemperatur.
F4: „Raft" auf Elegoos Standardprozess (null Raft-Schichten) setzt das Maß mit,
    und das Feld zeigt es.
R5: Kobra 2 in OrcaSlicer — was Anycubic in Prozenten schreibt, wo Orca keine
    liest, steht als „Hersteller: …" am Feld.

Aufruf: python dialog_r5_r6_sonde.py <code-wurzel>
"""

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
scratch = Path(tempfile.mkdtemp(prefix="dialog-r5-r6-sonde-"))
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


def open_dialog(slicer: Path, printer: str) -> PrintSettingsDialog:
    discover.forget_cache()
    discover.remember_path("slicer", str(slicer))
    session = Session()
    session.change_scene_profile(printer, "pla")
    assert session.wait_for_idle()
    dialog = PrintSettingsDialog(session, UiSettings())
    assert dialog.wait_for_slicers(), "Slicersuche kam nicht zurück"
    settle(lambda: bool(dialog._profiles) and dialog._foundation is not None)
    return dialog


# --- Elegoo CC2: R6 und F4 ---------------------------------------------------------------
dialog = open_dialog(Path(r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe"), "centauri-carbon-2")
print("Grundlage:", dialog.foundation_note.text())
walls = dialog._editors["shell.wall_count"]
walls.setValue(dialog.settings.shell.wall_count + 2)
nozzle = dialog._editors["temperature.nozzle"]
nozzle.setValue(dialog.settings.temperature.nozzle + 5)
qt.processEvents()
print("vor dem Wechsel:", sorted(dialog.settings.chosen))
assert dialog.settings.chosen == {"shell.wall_count", "temperature.nozzle"}
dialog.quality.setCurrentIndex(dialog.quality.findData("fine"))
qt.processEvents()
settle(lambda: dialog._foundation is not None and bool(dialog._foundation.staged))
print("nach „Fein“:", sorted(dialog.settings.chosen), "| Wände", dialog.settings.shell.wall_count)
assert dialog.settings.chosen == {"temperature.nozzle"}, dialog.settings.chosen
assert dialog.settings.shell.wall_count == 2, "Elegoos Wände, Fein ändert sie nicht"

adhesion = dialog._editors["adhesion.kind"]
adhesion.setCurrentIndex(adhesion.findData("raft"))
qt.processEvents()
raft_field = dialog._editors["adhesion.raft_layers"]
print("Raft:", dialog.settings.adhesion.raft_layers, "| Feld zeigt", raft_field.value())
assert dialog.settings.adhesion.raft_layers == 3
assert raft_field.value() == 3
assert {"adhesion.kind", "adhesion.raft_layers"} <= dialog.settings.chosen
tip = adhesion.itemData(adhesion.findData("auto"), 3)  # Qt.ToolTipRole
print("Satz zu Automatisch:", tip)
assert tip and "Slicer" in str(tip)
dialog.done(0)
dialog.release()

# --- Kobra 2 in OrcaSlicer: R5 --------------------------------------------------------------
dialog = open_dialog(Path(r"C:\Program Files\OrcaSlicer\orca-slicer.exe"), "anycubic-kobra-2")
print("Grundlage:", dialog.foundation_note.text())
foreign = dict(dialog._foundation.foreign)
print("fremd:", foreign)
assert foreign, "an der Kobra 2 erwartet: Prozente in Feldern ohne Prozent"
for path, raw in foreign.items():
    label = dialog._foreign_notes.get(path)
    if label is None:
        continue
    print(" ", path, "→", label.text(), "| sichtbar:", not label.isHidden())
    assert not label.isHidden() and raw in label.text()
print("Sonde bestanden.")
dialog.done(0)
dialog.release()
