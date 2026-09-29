"""Sonde: der Druckdialog auf dem Herstellerprofil (Konzept Herstellerprofil, Stufe A).

Kein Test — die Fenstertests laufen beim Release. Die Sonde baut den Dialog
offscreen, mit ElegooSlicer als gemerktem Slicer und einem Projekt auf dem
Centauri Carbon 2, und prüft am echten Profilbestand:

1. Nach der Profilsuche zeigen die Felder Elegoos Werte (2 Wände, erste
   Schicht 0,2 mm), nicht Solidons Stufe.
2. Eine Eingabe wird eigene Wahl: fette Beschriftung, Knopf sichtbar.
3. *Zurücksetzen* nimmt den Wert des Profils zurück und die Herkunft mit.
4. Wer nur nachsieht, ändert nichts am Projekt (``has_changes``).

Aufruf: python dialog_sonde.py <code-wurzel>
"""

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Die Nutzerverzeichnisse umbiegen wie die Suite — die Sonde soll Roberts
# Einstellungen weder lesen noch schreiben.
scratch = Path(tempfile.mkdtemp(prefix="dialog-sonde-"))
os.environ["APPDATA"] = str(scratch / "appdata")
os.environ["LOCALAPPDATA"] = str(scratch / "local")

import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import discover  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402

load_operations()
from app.core.scene.project import new_project  # noqa: E402
from app.ui.print_settings_dialog import PrintSettingsDialog  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

ELEGOO = Path(r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe")
qt = QApplication.instance() or QApplication([])
discover.remember_path("slicer", str(ELEGOO))

session = Session()
session.change_scene_profile("centauri-carbon-2", "pla")
assert session.wait_for_idle()
dialog = PrintSettingsDialog(session, UiSettings())
assert dialog.wait_for_slicers(), "Slicersuche kam nicht zurück"
deadline = time.monotonic() + 120
while (not dialog._profiles or dialog._foundation is None) and time.monotonic() < deadline:
    qt.processEvents()
    time.sleep(0.05)
print("Profile gefunden:", len(dialog._profiles))
print("Maschine:", dialog.machine_choice.currentText())
print("Prozess:", dialog.process_choice.currentText())
print("Filament:", dialog._filament_title)
print("Grundlage:", dialog.foundation_note.text())
settings = dialog.settings
print("Wände", settings.shell.wall_count, "| Boden", settings.shell.bottom_layers,
      "| erste Schicht", settings.layers.first_layer_height, settings.layers.first_layer_line_width,
      "| Generator", settings.shell.wall_generator, "| Stützwinkel", settings.support.threshold_angle,
      "| Haftung", settings.adhesion.kind, "| Z-Hop", settings.retraction.z_hop)
assert settings.shell.wall_count == 2, "Elegoos zwei Wände"
assert abs(settings.layers.first_layer_height - 0.2) < 1e-9, "Elegoos erste Schicht"
assert not settings.explicit, "ohne Eingabe keine eigene Wahl"
assert not dialog.has_changes(), "wer nur nachsieht, ändert nichts"

editor = dialog._editors["shell.wall_count"]
editor.setValue(4)
qt.processEvents()
assert dialog.settings.shell.wall_count == 4
assert dialog.settings.chosen == {"shell.wall_count"}, dialog.settings.chosen
reset = dialog._resets["shell.wall_count"]
print("Knopf sichtbar:", not reset.isHidden(), "|", reset.toolTip())
assert not reset.isHidden()
assert dialog._labels["shell.wall_count"].font().bold()
assert dialog.has_changes()

reset.click()
qt.processEvents()
assert dialog.settings.shell.wall_count == 2, dialog.settings.shell.wall_count
assert not dialog.settings.explicit
assert reset.isHidden()
assert not dialog.has_changes(), "zurückgesetzt heißt: wie vorher"
print("Sonde bestanden.")
dialog.done(0)
dialog.release()
